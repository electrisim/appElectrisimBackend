"""
Data-center site screening: MW sweep, headroom, N-1 and capped N-1-1 (pandapower).
"""

from __future__ import annotations

import json
import math
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import pandapower as pp
from pandapower import topology as top

from pandapower_electrisim import _contingency_friendly_name, _json_serialize_default

N11_MAX_CASES = 400
HEADROOM_SEARCH_MAX_MW = 5000.0
HEADROOM_STEPS = 22


class SiteScreeningCancelled(Exception):
    """Raised when the user stops a streaming site-screening run."""


def _progress(params: Dict[str, Any], message: str) -> None:
    if not isinstance(params, dict):
        return
    cancel = params.get("_cancel_event")
    if cancel is not None and getattr(cancel, "is_set", lambda: False)():
        raise SiteScreeningCancelled("Stopped by user")
    cb = params.get("_progress_callback")
    if callable(cb):
        cb(str(message))


def _parse_float_list(text: str, default: List[float]) -> List[float]:
    if not text or not str(text).strip():
        return default
    out = []
    for part in str(text).replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(float(part))
        except ValueError:
            continue
    return out or default


def _parse_id_list(text: str) -> List[str]:
    if not text:
        return []
    if isinstance(text, list):
        return [str(x).strip() for x in text if str(x).strip()]
    return [p.strip() for p in str(text).replace(";", ",").split(",") if p.strip()]


def _load_indices_for_ids(net, load_ids: List[str]) -> List[int]:
    want = set(load_ids)
    found = []
    ufn = getattr(net, "user_friendly_names", None) or {}
    for idx in net.load.index:
        lid = str(net.load.loc[idx, "id"]) if "id" in net.load.columns else ""
        name = str(net.load.loc[idx, "name"])
        friendly = str(ufn.get(name, name))
        if lid in want or name in want or friendly in want:
            found.append(idx)
    return found


def _set_load_mw(net, load_idx: int, p_mw: float, power_factor: float) -> None:
    pf = max(min(power_factor, 1.0), 0.01)
    q = p_mw * math.tan(math.acos(pf))
    net.load.loc[load_idx, "p_mw"] = max(p_mw, 0.0)
    net.load.loc[load_idx, "q_mvar"] = max(q, 0.0)


def _named(net, table, idx):
    raw = str(table.loc[idx, "name"]) if "name" in table.columns else str(idx)
    return raw, _contingency_friendly_name(net, raw)


def _count_violations(
    net,
    voltage_limits: bool,
    thermal_limits: bool,
    min_vm_pu: float,
    max_vm_pu: float,
    max_loading_percent: float,
) -> Tuple[int, List[Dict[str, Any]]]:
    violations = []
    if voltage_limits and hasattr(net, "res_bus") and not net.res_bus.empty:
        bad = net.res_bus[(net.res_bus.vm_pu < min_vm_pu) | (net.res_bus.vm_pu > max_vm_pu)]
        for bus_idx, row in bad.iterrows():
            raw, nm = _named(net, net.bus, bus_idx)
            vm = float(row.vm_pu)
            violations.append({
                "kind": "Bus",
                "id": raw,
                "name": nm,
                "text": f"{vm:.3f} pu",
                "limit": f"{min_vm_pu:.2f}–{max_vm_pu:.2f} pu",
            })
    if thermal_limits:
        if hasattr(net, "res_line") and not net.res_line.empty:
            ol = net.res_line[net.res_line.loading_percent > max_loading_percent]
            for li, row in ol.iterrows():
                raw, nm = _named(net, net.line, li)
                ld = float(row.loading_percent)
                violations.append({
                    "kind": "Line",
                    "id": raw,
                    "name": nm,
                    "text": f"{ld:.1f}% loaded",
                    "limit": f"{max_loading_percent:.0f}%",
                })
        if hasattr(net, "res_trafo") and not net.res_trafo.empty:
            ot = net.res_trafo[net.res_trafo.loading_percent > max_loading_percent]
            for ti, row in ot.iterrows():
                raw, nm = _named(net, net.trafo, ti)
                ld = float(row.loading_percent)
                violations.append({
                    "kind": "Transformer",
                    "id": raw,
                    "name": nm,
                    "text": f"{ld:.1f}% loaded",
                    "limit": f"{max_loading_percent:.0f}%",
                })
    return len(violations), violations


def _site_marker(net, load_idx) -> Dict[str, Any]:
    raw, nm = _named(net, net.load, load_idx)
    p = float(net.load.at[load_idx, "p_mw"]) if "p_mw" in net.load.columns else 0.0
    q = float(net.load.at[load_idx, "q_mvar"]) if "q_mvar" in net.load.columns else 0.0
    return {"id": raw, "name": nm, "p_mw": round(p, 3), "q_mvar": round(q, 3)}


def _dashboard_snapshot(net, title: str, site_load: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compact load-flow payload for the Network Health Dashboard."""
    buses, lines, trafos, loads, gens = [], [], [], [], []

    def fnum(row, key):
        try:
            v = float(row[key])
        except Exception:
            return None
        if not math.isfinite(v):
            return None
        return round(v, 4)

    if hasattr(net, "res_bus") and not net.res_bus.empty:
        for idx, row in net.res_bus.iterrows():
            raw, nm = _named(net, net.bus, idx)
            buses.append({"id": raw, "name": nm, "vm_pu": fnum(row, "vm_pu"), "p_mw": fnum(row, "p_mw") or 0})
    if hasattr(net, "res_line") and not net.res_line.empty:
        for idx, row in net.res_line.iterrows():
            raw, nm = _named(net, net.line, idx)
            lines.append({
                "id": raw,
                "name": nm,
                "loading_percent": fnum(row, "loading_percent"),
                "p_from_mw": fnum(row, "p_from_mw"),
                "pl_mw": fnum(row, "pl_mw"),
            })
    if hasattr(net, "res_trafo") and not net.res_trafo.empty:
        for idx, row in net.res_trafo.iterrows():
            raw, nm = _named(net, net.trafo, idx)
            trafos.append({
                "id": raw,
                "name": nm,
                "loading_percent": fnum(row, "loading_percent"),
                "p_hv_mw": fnum(row, "p_hv_mw"),
                "pl_mw": fnum(row, "pl_mw"),
            })
    if hasattr(net, "res_load") and not net.res_load.empty:
        for idx, row in net.res_load.iterrows():
            raw, nm = _named(net, net.load, idx)
            loads.append({"id": raw, "name": nm, "p_mw": fnum(row, "p_mw") or 0, "q_mvar": fnum(row, "q_mvar") or 0})
    if hasattr(net, "res_gen") and not net.res_gen.empty:
        for idx, row in net.res_gen.iterrows():
            raw, nm = _named(net, net.gen, idx)
            gens.append({"id": raw, "name": nm, "p_mw": fnum(row, "p_mw") or 0})
    ext = []
    if hasattr(net, "res_ext_grid") and not net.res_ext_grid.empty:
        for idx, row in net.res_ext_grid.iterrows():
            raw, nm = _named(net, net.ext_grid, idx)
            ext.append({"id": raw, "name": nm, "p_mw": fnum(row, "p_mw") or 0})
    return {
        "study_label": title,
        "busbars": buses,
        "lines": lines,
        "transformers": trafos,
        "loads": loads,
        "generators": gens,
        "externalgrids": ext,
        "site_load": site_load,
    }


def _run_pf(net) -> bool:
    try:
        pp.runpp(net, algorithm="nr", calculate_voltage_angles=True)
        return True
    except Exception:
        return False


def _apply_outage(net_cont, case: Dict[str, Any]) -> None:
    if case["type"] == "line":
        net_cont.line.loc[case["element_idx"], "in_service"] = False
    elif case["type"] == "trafo":
        net_cont.trafo.loc[case["element_idx"], "in_service"] = False
    elif case["type"] == "gen":
        net_cont.gen.loc[case["element_idx"], "in_service"] = False


def _build_n1_cases(net, element_type: str) -> List[Dict[str, Any]]:
    cases = []
    if element_type in ("line", "all"):
        for line_idx in net.line.index:
            if net.line.loc[line_idx, "in_service"]:
                nm = _contingency_friendly_name(net, net.line.loc[line_idx, "name"])
                cases.append(
                    {"name": f"Line_{nm}", "type": "line", "element_idx": line_idx, "tier": "N-1"}
                )
    if element_type in ("transformer", "all"):
        for trafo_idx in net.trafo.index:
            if net.trafo.loc[trafo_idx, "in_service"]:
                nm = _contingency_friendly_name(net, net.trafo.loc[trafo_idx, "name"])
                cases.append(
                    {"name": f"Trafo_{nm}", "type": "trafo", "element_idx": trafo_idx, "tier": "N-1"}
                )
    if element_type in ("generator", "all"):
        for gen_idx in net.gen.index:
            if net.gen.loc[gen_idx, "in_service"]:
                nm = _contingency_friendly_name(net, net.gen.loc[gen_idx, "name"])
                cases.append(
                    {"name": f"Gen_{nm}", "type": "gen", "element_idx": gen_idx, "tier": "N-1"}
                )
    return cases


def _build_n11_cases(net, element_type: str) -> List[Dict[str, Any]]:
    """Pairwise line + line / line + trafo outages (capped)."""
    base = []
    if element_type in ("line", "all"):
        base.extend(
            ("line", i)
            for i in net.line.index
            if net.line.loc[i, "in_service"]
        )
    trafos = []
    if element_type in ("transformer", "all"):
        trafos = [i for i in net.trafo.index if net.trafo.loc[i, "in_service"]]

    pairs: List[Dict[str, Any]] = []
    for i, (t1, e1) in enumerate(base):
        for t2, e2 in base[i + 1 :]:
            if len(pairs) >= N11_MAX_CASES:
                return pairs
            n1 = _contingency_friendly_name(
                net,
                net.line.loc[e1, "name"] if t1 == "line" else net.trafo.loc[e1, "name"],
            )
            n2 = _contingency_friendly_name(
                net,
                net.line.loc[e2, "name"] if t2 == "line" else net.trafo.loc[e2, "name"],
            )
            pairs.append(
                {
                    "name": f"N11_{n1}+{n2}",
                    "outages": [(t1, e1), (t2, e2)],
                    "tier": "N-1-1",
                }
            )
        for e2 in trafos:
            if len(pairs) >= N11_MAX_CASES:
                return pairs
            n1 = _contingency_friendly_name(
                net, net.line.loc[e1, "name"] if t1 == "line" else net.trafo.loc[e1, "name"]
            )
            n2 = _contingency_friendly_name(net, net.trafo.loc[e2, "name"])
            pairs.append(
                {
                    "name": f"N11_{n1}+Trafo_{n2}",
                    "outages": [(t1, e1), ("trafo", e2)],
                    "tier": "N-1-1",
                }
            )
    return pairs


def _headroom_mw(
    net_template,
    active_load_idx: int,
    site_load_indices: List[int],
    load_snapshot: Dict[int, Tuple[float, float]],
    power_factor: float,
    limits: Dict[str, Any],
    on_step=None,
) -> float:
    lo, hi = 0.0, HEADROOM_SEARCH_MAX_MW
    best = 0.0
    for step in range(HEADROOM_STEPS):
        if on_step and (step == 0 or step == HEADROOM_STEPS - 1 or (step + 1) % 5 == 0):
            on_step(step + 1, HEADROOM_STEPS)
        mid = (lo + hi) / 2.0
        net = deepcopy(net_template)
        for idx in site_load_indices:
            p0, q0 = load_snapshot[idx]
            net.load.loc[idx, "p_mw"] = 0.0
            net.load.loc[idx, "q_mvar"] = 0.0
        _set_load_mw(net, active_load_idx, mid, power_factor)
        if not _run_pf(net):
            hi = mid
            continue
        n_v, _ = _count_violations(net, **limits)
        if n_v == 0:
            best = mid
            lo = mid
        else:
            hi = mid
    return round(best, 2)


def _run_contingency_batch(
    net_template,
    cases: List[Dict[str, Any]],
    limits: Dict[str, Any],
    on_step=None,
    site_load: Optional[Dict[str, Any]] = None,
) -> Tuple[int, str, int, List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    worst = 0
    worst_name = ""
    worst_details: List[Dict[str, Any]] = []
    worst_snap = None
    failed = 0
    total = len(cases)
    for i, case in enumerate(cases, 1):
        if on_step and (i == 1 or i == total or i % 10 == 0):
            on_step(i, total)
        net_c = deepcopy(net_template)
        if case.get("outages"):
            for typ, eidx in case["outages"]:
                _apply_outage(net_c, {"type": typ, "element_idx": eidx})
        else:
            _apply_outage(net_c, case)
        if not _run_pf(net_c):
            failed += 1
            continue
        n_v, details = _count_violations(net_c, **limits)
        if n_v > worst:
            worst = n_v
            worst_name = case.get("name", "")
            worst_details = details
            worst_snap = _dashboard_snapshot(net_c, worst_name or "Contingency", site_load)
    return worst, worst_name, failed, worst_details, worst_snap


def site_screening_analysis(net, params: Dict[str, Any]) -> str:
    try:
        load_ids = _parse_id_list(params.get("site_load_ids", ""))
        if not load_ids:
            raise ValueError("No site load IDs specified. Select at least one Load on the diagram.")

        mw_sizes = _parse_float_list(params.get("mw_sizes", ""), [300.0, 500.0, 1000.0])
        power_factor = float(params.get("power_factor", 0.95))
        include_n11 = str(params.get("include_n11", "true")).lower() in ("true", "1", "yes")
        element_type = params.get("element_type", "all")
        voltage_limits = str(params.get("voltage_limits", "true")).lower() == "true"
        thermal_limits = str(params.get("thermal_limits", "true")).lower() == "true"
        min_vm_pu = float(params.get("min_vm_pu", 0.95))
        max_vm_pu = float(params.get("max_vm_pu", 1.05))
        max_loading_percent = float(params.get("max_loading_percent", 100))

        limits = {
            "voltage_limits": voltage_limits,
            "thermal_limits": thermal_limits,
            "min_vm_pu": min_vm_pu,
            "max_vm_pu": max_vm_pu,
            "max_loading_percent": max_loading_percent,
        }

        _progress(params, "Checking connectivity…")
        isolated = top.unsupplied_buses(net)
        if len(isolated) > 0:
            raise ValueError(f"Isolated buses: {list(isolated)}")

        load_indices = _load_indices_for_ids(net, load_ids)
        if not load_indices:
            raise ValueError(f"No loads matched IDs: {load_ids}")
        size_label = ", ".join(f"{mw:g}" for mw in mw_sizes)
        _progress(params, f"Sites: {len(load_indices)}. Sizes: {size_label} MW.")

        load_snapshot = {
            idx: (float(net.load.loc[idx, "p_mw"]), float(net.load.loc[idx, "q_mvar"]))
            for idx in load_indices
        }

        _progress(params, "Preparing N-1 cases…")
        n1_cases = _build_n1_cases(net, element_type)
        if include_n11:
            _progress(params, "Preparing N-1-1 cases…")
            n11_cases = _build_n11_cases(net, element_type)
        else:
            n11_cases = []
        _progress(params, f"Contingencies ready: {len(n1_cases)} N-1, {len(n11_cases)} N-1-1.")

        rows = []
        n_sites = len(load_indices)
        for site_i, load_idx in enumerate(load_indices, 1):
            site_name = _contingency_friendly_name(net, net.load.loc[load_idx, "name"])
            site_id = str(net.load.loc[load_idx, "id"]) if "id" in net.load.columns else site_name
            _progress(params, f"{site_name} ({site_i}/{n_sites}) — intact system")

            # Baseline violations at 0 MW project load
            net0 = deepcopy(net)
            for idx in load_indices:
                net0.load.loc[idx, "p_mw"] = 0.0
                net0.load.loc[idx, "q_mvar"] = 0.0
            base_violations = 0
            base_details: List[Dict[str, Any]] = []
            base_snap = None
            if _run_pf(net0):
                base_violations, base_details = _count_violations(net0, **limits)
                base_snap = _dashboard_snapshot(net0, f"{site_name} — intact system, 0 MW", _site_marker(net0, load_idx))

            for mw in mw_sizes:
                label = f"{site_name} · {mw:g} MW"
                _progress(params, f"{label} — base case")
                net_case = deepcopy(net)
                for idx in load_indices:
                    net_case.load.loc[idx, "p_mw"] = 0.0
                    net_case.load.loc[idx, "q_mvar"] = 0.0
                _set_load_mw(net_case, load_idx, mw, power_factor)
                if not _run_pf(net_case):
                    rows.append(
                        {
                            "site_id": site_id,
                            "site_name": site_name,
                            "requested_mw": mw,
                            "headroom_mw": 0.0,
                            "base_violations": base_violations,
                            "worst_n1_violations": -1,
                            "worst_n11_violations": -1,
                            "n1_worst_case": "",
                            "n11_worst_case": "",
                            "n1_failed_cases": 0,
                            "n11_failed_cases": 0,
                            "upgrade_likely": True,
                            "notes": "Base load flow did not converge at requested MW.",
                            "base_violation_details": base_details,
                            "base_snapshot": base_snap,
                            "case_violations": -1,
                            "case_violation_details": [],
                            "case_snapshot": None,
                            "n1_violation_details": [],
                            "n1_snapshot": None,
                            "n11_violation_details": [],
                            "n11_snapshot": None,
                        }
                    )
                    continue

                headroom = _headroom_mw(
                    net, load_idx, load_indices, load_snapshot, power_factor, limits,
                    on_step=lambda i, n, label=label: _progress(params, f"{label} — headroom {i}/{n}"),
                )
                case_n, case_details = _count_violations(net_case, **limits)
                case_snap = _dashboard_snapshot(net_case, f"{label} — intact", _site_marker(net_case, load_idx))
                site_mark = _site_marker(net_case, load_idx)
                w_n1, n1_name, n1_fail, n1_details, n1_snap = _run_contingency_batch(
                    net_case, n1_cases, limits,
                    on_step=lambda i, n, label=label: _progress(params, f"{label} — N-1 {i}/{n}"),
                    site_load=site_mark,
                )
                w_n11, n11_name, n11_fail, n11_details, n11_snap = (
                    _run_contingency_batch(
                        net_case, n11_cases, limits,
                        on_step=lambda i, n, label=label: _progress(params, f"{label} — N-1-1 {i}/{n}"),
                        site_load=site_mark,
                    )
                    if n11_cases else (0, "", 0, [], None)
                )
                _progress(params, f"{label} — headroom {headroom:g} MW")

                upgrade = headroom < mw or w_n1 > 0 or w_n11 > 0
                if base_violations == 0 and (w_n1 > 0 or w_n11 > 0):
                    upgrade = True

                rows.append(
                    {
                        "site_id": site_id,
                        "site_name": site_name,
                        "requested_mw": mw,
                        "headroom_mw": headroom,
                        "base_violations": base_violations,
                        "worst_n1_violations": w_n1,
                        "worst_n11_violations": w_n11,
                        "n1_worst_case": n1_name,
                        "n11_worst_case": n11_name,
                        "n1_failed_cases": n1_fail,
                        "n11_failed_cases": n11_fail,
                        "upgrade_likely": upgrade,
                        "notes": "",
                        "base_violation_details": base_details,
                        "base_snapshot": base_snap,
                        "case_violations": case_n,
                        "case_violation_details": case_details,
                        "case_snapshot": case_snap,
                        "n1_violation_details": n1_details,
                        "n1_snapshot": n1_snap,
                        "n11_violation_details": n11_details,
                        "n11_snapshot": n11_snap,
                    }
                )

        summary = {
            "sites_analyzed": len(load_indices),
            "mw_sizes": mw_sizes,
            "include_n11": include_n11,
            "n1_cases": len(n1_cases),
            "n11_cases": len(n11_cases),
            "upgrade_likely_count": sum(1 for r in rows if r.get("upgrade_likely")),
        }

        _progress(params, "Screening finished.")
        return json.dumps(
            {"study": "data_center_site_screening", "summary": summary, "screening_results": rows},
            default=_json_serialize_default,
            allow_nan=False,
            separators=(",", ":"),
        )
    except SiteScreeningCancelled:
        raise
    except Exception as e:
        return json.dumps({"error": str(e), "screening_results": []})
