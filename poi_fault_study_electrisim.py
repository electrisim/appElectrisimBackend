# -*- coding: utf-8 -*-
"""
POI fault study package for Electrisim: breaker duty, on-site source contribution,
SLG / NGR grounding, and IEC min/max coordination (close-in vs remote).
"""
from __future__ import annotations

import copy
import json
import math
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple

import pandapower as pp
from pandapower import shortcircuit as sc

import ansi_shortcircuit_electrisim as ansi_sc
from converter_sc_electrisim import (
    apply_converter_short_circuit_k,
    apply_negative_sequence_ikss,
)


def _f(v, default=0.0) -> float:
    return ansi_sc._f(v, default)


def _clean(v: Any) -> Any:
    return ansi_sc._clean(v)


def _display_name(net, internal_name: str, row_id: Any = None) -> str:
    return ansi_sc._display_name(net, internal_name, row_id)


def find_poi_bus_index(net) -> Optional[int]:
    if not hasattr(net, "ext_grid") or net.ext_grid.empty:
        return None
    row = net.ext_grid[net.ext_grid.in_service]
    if row.empty:
        row = net.ext_grid
    return int(row.iloc[0]["bus"])


def _build_adjacency(net) -> Dict[int, Set[int]]:
    adj: Dict[int, Set[int]] = {int(b): set() for b in net.bus.index}
    if not net.line.empty:
        for _, row in net.line[net.line.in_service].iterrows():
            a, b = int(row["from_bus"]), int(row["to_bus"])
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)
    if not net.trafo.empty:
        for _, row in net.trafo[net.trafo.in_service].iterrows():
            a, b = int(row["hv_bus"]), int(row["lv_bus"])
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)
    return adj


def classify_buses(net, poi_idx: int) -> Tuple[List[int], List[int], List[int]]:
    """Return (poi_only, close_in, remote) bus indices."""
    adj = _build_adjacency(net)
    dist: Dict[int, int] = {poi_idx: 0}
    q = deque([poi_idx])
    while q:
        u = q.popleft()
        for v in adj.get(u, ()):
            if v in dist:
                continue
            dist[v] = dist[u] + 1
            q.append(v)
    if not dist:
        return [poi_idx], [poi_idx], [poi_idx]
    max_d = max(dist.values())
    close_in = [b for b, d in dist.items() if d <= 1]
    remote = [b for b, d in dist.items() if d == max_d and max_d >= 2]
    if not remote:
        remote = [b for b, d in dist.items() if d == max_d]
    return [poi_idx], sorted(set(close_in)), sorted(set(remote))


def apply_ngr_to_net(net) -> None:
    """Fold transformer rn_ohm / xn_ohm into vk0_percent for zero-sequence studies."""
    if not hasattr(net, "trafo") or net.trafo.empty:
        return
    for idx, row in net.trafo.iterrows():
        rn = _f(row.get("rn_ohm"), 0.0)
        xn = _f(row.get("xn_ohm"), 0.0)
        if rn <= 0 and xn <= 0:
            continue
        zn = math.sqrt(rn * rn + xn * xn)
        sn = _f(row.get("sn_mva"), 1.0) or 1.0
        vn_hv = _f(row.get("vn_hv_kv"), 20.0) or 20.0
        z_base = (vn_hv ** 2) / sn
        if z_base <= 0:
            continue
        extra_pct = 100.0 * (3.0 * zn) / z_base
        vk0 = _f(row.get("vk0_percent"), _f(row.get("vk_percent"), 6.0))
        net.trafo.at[idx, "vk0_percent"] = math.sqrt(vk0 * vk0 + extra_pct * extra_pct)


def _set_table_out_of_service(net, attr: str, indices: Optional[Set[int]] = None, out: bool = True) -> None:
    if not hasattr(net, attr):
        return
    df = getattr(net, attr)
    if df is None or df.empty:
        return
    if indices is None:
        for idx in df.index:
            df.at[idx, "in_service"] = not out
    else:
        for idx in df.index:
            if int(idx) in indices:
                df.at[idx, "in_service"] = not out


def set_all_onsite_out_of_service(net, out: bool = True) -> None:
    """Disable gen, sgen, storage (on-site sources). Ext grid stays in service."""
    for attr in ("gen", "sgen", "storage"):
        _set_table_out_of_service(net, attr, None, out)


def _onsite_source_rows(net) -> List[dict]:
    rows: List[dict] = []
    for attr, kind in (("gen", "generator"), ("sgen", "static_generator"), ("storage", "storage")):
        if not hasattr(net, attr):
            continue
        df = getattr(net, attr)
        if df is None or df.empty:
            continue
        for idx, row in df.iterrows():
            rows.append({
                "table": attr,
                "index": int(idx),
                "kind": kind,
                "name": _display_name(net, _clean(row.get("name", str(idx)))),
                "id": _clean(row.get("id", row.get("name", str(idx)))),
            })
    return rows


def _poi_ikss_ansi(net, poi_idx: int, freq_hz: float, fault: str = "3ph") -> float:
    bus_name = net.bus.at[poi_idx, "name"]
    bus_id = net.bus.at[poi_idx, "id"] if "id" in net.bus.columns else bus_name
    params = {
        "fault_type": fault,
        "frequency_hz": freq_hz,
        "prefault_v_pu": 1.0,
        "contact_parting_cycles": 3,
        "fault_bus_mode": "selection",
        "fault_bus_ids": [str(bus_id), str(bus_name)],
    }
    raw = json.loads(ansi_sc.shortcircuit_ansi(net, params))
    for b in raw.get("busbars", []):
        bid = b.get("id")
        bname = b.get("name")
        if str(bname) == str(bus_name) or str(bid) == str(bus_name) or str(bid) == str(bus_id):
            return _f(b.get("i_first_sym_ka"), 0.0)
    for b in raw.get("busbars", []):
        return _f(b.get("i_first_sym_ka"), 0.0)
    return 0.0


def _merge_duty_pre_post(pre: dict, post: dict) -> List[dict]:
    pre_map = {str(d.get("name")): d for d in pre.get("device_duties", [])}
    out = []
    for d in post.get("device_duties", []):
        pd = pre_map.get(str(d.get("name")), {})
        over_int = d.get("interrupting_pass") is False
        over_mom = d.get("momentary_pass") is False
        out.append({
            **d,
            "pre_duty_interrupting_ka": pd.get("duty_interrupting_ka"),
            "pre_duty_momentary_ka": pd.get("duty_momentary_ka"),
            "pre_interrupting_pass": pd.get("interrupting_pass"),
            "pre_momentary_pass": pd.get("momentary_pass"),
            "over_duty": bool(over_int or over_mom),
            "over_duty_pre": bool(
                pd.get("interrupting_pass") is False or pd.get("momentary_pass") is False
            ),
        })
    return out


def _source_contributions(net, poi_idx: int, freq_hz: float) -> List[dict]:
    apply_ngr_to_net(net)
    base_net = copy.deepcopy(net)
    set_all_onsite_out_of_service(base_net, True)
    i_utility = _poi_ikss_ansi(base_net, poi_idx, freq_hz, "3ph")
    i_total = _poi_ikss_ansi(net, poi_idx, freq_hz, "3ph")

    rows = []
    for src in _onsite_source_rows(net):
        one_out = copy.deepcopy(net)
        df = getattr(one_out, src["table"])
        if df is not None and src["index"] in df.index:
            df.at[src["index"], "in_service"] = False
        i_without = _poi_ikss_ansi(one_out, poi_idx, freq_hz, "3ph")
        delta = max(0.0, i_total - i_without)
        rows.append({
            "name": src["name"],
            "id": src["id"],
            "kind": src["kind"],
            "delta_i_first_sym_ka_poi": _clean(delta),
            "i_with_source_ka_poi": _clean(i_total),
            "i_without_source_ka_poi": _clean(i_without),
        })
    rows.append({
        "name": "Utility (ext grid)",
        "id": "utility",
        "kind": "ext_grid",
        "delta_i_first_sym_ka_poi": _clean(max(0.0, i_utility)),
        "i_with_source_ka_poi": _clean(i_utility),
        "i_without_source_ka_poi": _clean(0.0),
    })
    return rows


def _iec_bus_sc(
    net,
    bus_idx: int,
    fault: str,
    case: str,
    tk_s: float = 1.0,
) -> dict:
    work = copy.deepcopy(net)
    apply_ngr_to_net(work)
    apply_converter_short_circuit_k(work, fault)
    from pandapower_electrisim import ensure_ext_grid_zero_sequence_min

    ensure_ext_grid_zero_sequence_min(work)
    try:
        sc.calc_sc(
            work,
            fault=fault,
            case=case,
            bus=int(bus_idx),
            ip=True,
            ith=True,
            tk_s=tk_s,
            kappa_method="C",
            check_connectivity=False,
            branch_results=False,
            return_all_currents=False,
        )
        apply_negative_sequence_ikss(work, fault=fault, case=case, bus=int(bus_idx))
    except Exception as e:
        return {"error": str(e), "ikss_ka": None, "ip_ka": None, "ith_ka": None}
    row = work.res_bus_sc.loc[bus_idx]
    return {
        "ikss_ka": _clean(row.get("ikss_ka")),
        "ip_ka": _clean(row.get("ip_ka")),
        "ith_ka": _clean(row.get("ith_ka")),
        "rk_ohm": _clean(row.get("rk_ohm")),
        "xk_ohm": _clean(row.get("xk_ohm")),
    }


def _grounding_rows(net, slg_target_a: float, freq_hz: float) -> List[dict]:
    rows = []
    if not hasattr(net, "trafo") or net.trafo.empty:
        return rows
    for idx, tr in net.trafo.iterrows():
        lv = int(tr["lv_bus"])
        hv = int(tr["hv_bus"])
        rn = _f(tr.get("rn_ohm"), 0.0)
        xn = _f(tr.get("xn_ohm"), 0.0)
        vn_lv = _f(net.bus.at[lv, "vn_kv"], 0.69)
        slg = _iec_bus_sc(net, lv, "1ph", "max")
        i_slg = _f(slg.get("ikss_ka"), 0.0)
        i_neutral = i_slg
        v_rn = rn * i_slg * 1000.0 if rn > 0 else None
        v_phase = vn_lv * 1000.0 / math.sqrt(3.0)
        rn_suggest = None
        if slg_target_a > 0 and i_slg > 0:
            rn_suggest = v_phase / slg_target_a
        rows.append({
            "trafo_name": _display_name(net, _clean(tr.get("name", idx))),
            "trafo_id": _clean(tr.get("id", tr.get("name", idx))),
            "lv_bus": _clean(net.bus.at[lv, "name"]),
            "hv_bus": _clean(net.bus.at[hv, "name"]),
            "rn_ohm": _clean(rn) if rn > 0 else None,
            "xn_ohm": _clean(xn) if xn > 0 else None,
            "slg_i_ka_lv": _clean(i_slg),
            "neutral_i_ka": _clean(i_neutral),
            "rn_voltage_v": _clean(v_rn),
            "suggested_rn_ohm": _clean(rn_suggest),
            "slg_target_a": _clean(slg_target_a) if slg_target_a > 0 else None,
            "note": "SLG at LV bus; use i_first_sym from ANSI 1ph at POI for HV POI studies",
        })
    poi = find_poi_bus_index(net)
    if poi is not None:
        slg_poi = _poi_ikss_ansi(net, poi, freq_hz, "1ph")
        if rows:
            rows[0]["slg_i_ka_poi_ansi"] = _clean(slg_poi)
    return rows


def _coordination_table(net, close_in: List[int], remote: List[int]) -> List[dict]:
    out = []
    for label, buses in (("close_in", close_in), ("remote", remote)):
        for bus_idx in buses:
            bname = net.bus.at[bus_idx, "name"]
            bid = net.bus.at[bus_idx, "id"] if "id" in net.bus.columns else bname
            for fault in ("3ph", "1ph"):
                for case in ("max", "min"):
                    sc_row = _iec_bus_sc(net, bus_idx, fault, case)
                    out.append({
                        "location_class": label,
                        "bus_name": _display_name(net, _clean(bname)),
                        "bus_id": _clean(bid),
                        "fault_type": fault,
                        "case": case,
                        **sc_row,
                    })
    return out


def run_poi_fault_study(net, in_data: dict, in_data_full=None) -> str:
    freq_hz = _f(in_data.get("frequency_hz", net.f_hz if hasattr(net, "f_hz") else 50), 50.0)
    if freq_hz <= 0:
        freq_hz = 50.0
    cp_cycles = _f(in_data.get("contact_parting_cycles", 3), 3.0)
    slg_target_a = _f(in_data.get("slg_target_ground_i_a", 0), 0.0)

    poi_idx = find_poi_bus_index(net)
    if poi_idx is None:
        return json.dumps({"error": True, "message": "No external grid (POI) found in the network."})

    _, close_in, remote = classify_buses(net, poi_idx)

    ansi_params = {
        "fault_type": "3ph",
        "frequency_hz": freq_hz,
        "prefault_v_pu": _f(in_data.get("prefault_v_pu", 1.0), 1.0),
        "contact_parting_cycles": cp_cycles,
        "fault_bus_mode": "all",
    }

    net_post = copy.deepcopy(net)
    apply_ngr_to_net(net_post)
    post_ansi = json.loads(ansi_sc.shortcircuit_ansi(net_post, ansi_params))

    net_pre = copy.deepcopy(net)
    set_all_onsite_out_of_service(net_pre, True)
    apply_ngr_to_net(net_pre)
    pre_ansi = json.loads(ansi_sc.shortcircuit_ansi(net_pre, ansi_params))

    breaker_duties = _merge_duty_pre_post(pre_ansi, post_ansi)
    sources = _source_contributions(net, poi_idx, freq_hz)
    grounding = _grounding_rows(net, slg_target_a, freq_hz)
    coordination = _coordination_table(net, close_in, remote)

    poi_name = net.bus.at[poi_idx, "name"]
    result = {
        "study": "poi_fault_study",
        "engine": "mixed_ansi_iec",
        "poi_bus": {
            "name": _clean(poi_name),
            "id": _clean(net.bus.at[poi_idx, "id"] if "id" in net.bus.columns else poi_name),
            "index": int(poi_idx),
            "userFriendlyName": _display_name(net, poi_name, poi_idx),
        },
        "close_in_bus_names": [_clean(net.bus.at[b, "name"]) for b in close_in],
        "remote_bus_names": [_clean(net.bus.at[b, "name"]) for b in remote],
        "frequency_hz": freq_hz,
        "breaker_duties": breaker_duties,
        "source_contributions": sources,
        "grounding": grounding,
        "coordination": coordination,
        "ansi_post_busbars": post_ansi.get("busbars", []),
        "disclaimer": (
            "POI fault study combines ANSI C37 breaker duty (beta) with IEC 60909 coordination "
            "currents. Verify results against utility requirements."
        ),
    }
    return json.dumps(result, separators=(",", ":"))


def poi_fault_study(net, in_data, in_data_full=None) -> str:
    return run_poi_fault_study(net, in_data, in_data_full)
