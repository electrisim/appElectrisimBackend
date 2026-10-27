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

# Violations are judged against the same case with the project at 0 MW. A violation that is
# already there at 0 MW counts again only if the project deepens it by more than these margins.
WORSE_TOL_VM_PU = 0.005
WORSE_TOL_LOADING_PERCENT = 1.0


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
                "index": int(bus_idx),
                "id": raw,
                "name": nm,
                "value": vm,
                "side": "low" if vm < min_vm_pu else "high",
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
                    "index": int(li),
                    "id": raw,
                    "name": nm,
                    "value": ld,
                    "side": "over",
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
                    "index": int(ti),
                    "id": raw,
                    "name": nm,
                    "value": ld,
                    "side": "over",
                    "text": f"{ld:.1f}% loaded",
                    "limit": f"{max_loading_percent:.0f}%",
                })
    return len(violations), violations


def _violation_map(details: List[Dict[str, Any]]) -> Dict[Tuple[str, int], Dict[str, Any]]:
    return {(d["kind"], d["index"]): d for d in details}


def _new_or_worse(
    details: List[Dict[str, Any]],
    baseline_map: Optional[Dict[Tuple[str, int], Dict[str, Any]]],
    tols: Tuple[float, float],
) -> List[Dict[str, Any]]:
    """Keep violations that are absent at 0 MW, or deeper than at 0 MW by more than the margin.

    ``baseline_map`` is None when there is no 0 MW reference (it did not converge): then every
    violation counts as new.
    """
    if baseline_map is None:
        return [dict(d, change="new") for d in details]
    tol_vm_pu, tol_loading = tols
    out = []
    for d in details:
        b = baseline_map.get((d["kind"], d["index"]))
        if b is None or b.get("side") != d.get("side"):
            out.append(dict(d, change="new"))
            continue
        tol = tol_vm_pu if d["kind"] == "Bus" else tol_loading
        worse_by = (b["value"] - d["value"]) if d["side"] == "low" else (d["value"] - b["value"])
        if worse_by > tol:
            out.append(dict(d, change="worse", baseline_text=b["text"]))
    return out


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
    baseline_map: Optional[Dict[Tuple[str, int], Dict[str, Any]]] = None,
    tols: Tuple[float, float] = (WORSE_TOL_VM_PU, WORSE_TOL_LOADING_PERCENT),
    relative_to_baseline: bool = False,
) -> float:
    """Largest project MW with no violations (or, when ``relative_to_baseline``, none new or worse than at 0 MW)."""
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
        n_v, details = _count_violations(net, **limits)
        if relative_to_baseline:
            n_v = len(_new_or_worse(details, baseline_map, tols))
        if n_v == 0:
            best = mid
            lo = mid
        else:
            hi = mid
    return round(best, 2)


def _outage_net(net_template, case: Dict[str, Any]):
    net_c = deepcopy(net_template)
    if case.get("outages"):
        for typ, eidx in case["outages"]:
            _apply_outage(net_c, {"type": typ, "element_idx": eidx})
    else:
        _apply_outage(net_c, case)
    return net_c


def _contingency_baseline(
    net0,
    cases: List[Dict[str, Any]],
    limits: Dict[str, Any],
    on_step=None,
) -> List[Optional[Dict[Tuple[str, int], Dict[str, Any]]]]:
    """Violations of every outage case with the project at 0 MW (None where it does not converge)."""
    out: List[Optional[Dict[Tuple[str, int], Dict[str, Any]]]] = []
    total = len(cases)
    for i, case in enumerate(cases, 1):
        if on_step and (i == 1 or i == total or i % 10 == 0):
            on_step(i, total)
        net_c = _outage_net(net0, case)
        if not _run_pf(net_c):
            out.append(None)
            continue
        _, details = _count_violations(net_c, **limits)
        out.append(_violation_map(details))
    return out


def _run_contingency_batch(
    net_template,
    cases: List[Dict[str, Any]],
    limits: Dict[str, Any],
    on_step=None,
    site_load: Optional[Dict[str, Any]] = None,
    baseline: Optional[List[Optional[Dict[Tuple[str, int], Dict[str, Any]]]]] = None,
    tols: Tuple[float, float] = (WORSE_TOL_VM_PU, WORSE_TOL_LOADING_PERCENT),
) -> Dict[str, Any]:
    """Run outage cases at the project size.

    ``worst`` / ``worst_details`` count only violations that are new or worse than the same
    outage at 0 MW (``baseline``, aligned with ``cases``). ``worst_all`` keeps the plain count.
    ``new_failed`` counts outages that do not converge with the project but do at 0 MW.
    """
    res: Dict[str, Any] = {
        "worst": 0, "worst_name": "", "worst_details": [], "worst_snap": None,
        "worst_all": 0, "worst_all_name": "",
        "failed": 0, "new_failed": 0,
    }
    total = len(cases)
    for i, case in enumerate(cases, 1):
        if on_step and (i == 1 or i == total or i % 10 == 0):
            on_step(i, total)
        net_c = _outage_net(net_template, case)
        has_ref = baseline is not None and baseline[i - 1] is not None
        if not _run_pf(net_c):
            res["failed"] += 1
            if baseline is None or has_ref:
                res["new_failed"] += 1
            continue
        n_all, details = _count_violations(net_c, **limits)
        if n_all > res["worst_all"]:
            res["worst_all"] = n_all
            res["worst_all_name"] = case.get("name", "")
        counted = _new_or_worse(details, baseline[i - 1] if has_ref else None, tols)
        if len(counted) > res["worst"]:
            res["worst"] = len(counted)
            res["worst_name"] = case.get("name", "")
            res["worst_details"] = counted
            res["worst_snap"] = _dashboard_snapshot(net_c, res["worst_name"] or "Contingency", site_load)
    return res


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
        tols = (
            float(params.get("worse_tol_vm_pu", WORSE_TOL_VM_PU)),
            float(params.get("worse_tol_loading_percent", WORSE_TOL_LOADING_PERCENT)),
        )

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

        # 0 MW reference: every site load at zero. It is the same for all sites, so run it once and
        # judge each project size only on violations that are new or worse than here.
        _progress(params, "Reference case at 0 MW — intact system")
        net0 = deepcopy(net)
        for idx in load_indices:
            net0.load.loc[idx, "p_mw"] = 0.0
            net0.load.loc[idx, "q_mvar"] = 0.0
        base_converged = _run_pf(net0)
        base_violations = 0
        base_details: List[Dict[str, Any]] = []
        if base_converged:
            base_violations, base_details = _count_violations(net0, **limits)
        base_map = _violation_map(base_details) if base_converged else None
        n1_base = _contingency_baseline(
            net0, n1_cases, limits,
            on_step=lambda i, n: _progress(params, f"Reference case at 0 MW — N-1 {i}/{n}"),
        ) if base_converged else None
        n11_base = _contingency_baseline(
            net0, n11_cases, limits,
            on_step=lambda i, n: _progress(params, f"Reference case at 0 MW — N-1-1 {i}/{n}"),
        ) if (base_converged and n11_cases) else None
        n1_base_with_viol = sum(1 for m in (n1_base or []) if m)
        n11_base_with_viol = sum(1 for m in (n11_base or []) if m)
        n1_base_failed = sum(1 for m in (n1_base or []) if m is None)
        n11_base_failed = sum(1 for m in (n11_base or []) if m is None)
        if base_converged:
            _progress(
                params,
                f"At 0 MW: {base_violations} intact violations, {n1_base_with_viol} N-1 cases already "
                f"outside limits. These are not counted against the project unless it makes them worse.",
            )

        rows = []
        n_sites = len(load_indices)
        for site_i, load_idx in enumerate(load_indices, 1):
            site_name = _contingency_friendly_name(net, net.load.loc[load_idx, "name"])
            site_id = str(net.load.loc[load_idx, "id"]) if "id" in net.load.columns else site_name
            _progress(params, f"{site_name} ({site_i}/{n_sites}) — intact system")
            base_snap = (
                _dashboard_snapshot(net0, f"{site_name} — intact system, 0 MW", _site_marker(net0, load_idx))
                if base_converged else None
            )

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
                            "n1_new_failed_cases": 0,
                            "n11_new_failed_cases": 0,
                            "worst_n1_violations_all": -1,
                            "worst_n11_violations_all": -1,
                            "n1_worst_case_all": "",
                            "n11_worst_case_all": "",
                            "case_new_violations": -1,
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
                    baseline_map=base_map, tols=tols, relative_to_baseline=True,
                )
                case_n, case_details = _count_violations(net_case, **limits)
                case_new = _new_or_worse(case_details, base_map, tols)
                case_snap = _dashboard_snapshot(net_case, f"{label} — intact", _site_marker(net_case, load_idx))
                site_mark = _site_marker(net_case, load_idx)
                n1 = _run_contingency_batch(
                    net_case, n1_cases, limits,
                    on_step=lambda i, n, label=label: _progress(params, f"{label} — N-1 {i}/{n}"),
                    site_load=site_mark, baseline=n1_base, tols=tols,
                )
                n11 = (
                    _run_contingency_batch(
                        net_case, n11_cases, limits,
                        on_step=lambda i, n, label=label: _progress(params, f"{label} — N-1-1 {i}/{n}"),
                        site_load=site_mark, baseline=n11_base, tols=tols,
                    )
                    if n11_cases else _run_contingency_batch(net_case, [], limits)
                )
                _progress(params, f"{label} — headroom {headroom:g} MW")

                # Only what the project adds counts: new or worse violations, and outages that
                # stop converging with the project although they converge at 0 MW.
                upgrade = (
                    headroom < mw
                    or n1["worst"] > 0 or n11["worst"] > 0
                    or n1["new_failed"] > 0 or n11["new_failed"] > 0
                )
                notes = []
                if n1["new_failed"]:
                    notes.append(f"{n1['new_failed']} N-1 outage(s) do not converge with the project but do at 0 MW.")
                if n11["new_failed"]:
                    notes.append(f"{n11['new_failed']} N-1-1 outage(s) do not converge with the project but do at 0 MW.")

                rows.append(
                    {
                        "site_id": site_id,
                        "site_name": site_name,
                        "requested_mw": mw,
                        "headroom_mw": headroom,
                        "base_violations": base_violations,
                        "worst_n1_violations": n1["worst"],
                        "worst_n11_violations": n11["worst"],
                        "n1_worst_case": n1["worst_name"],
                        "n11_worst_case": n11["worst_name"],
                        "worst_n1_violations_all": n1["worst_all"],
                        "worst_n11_violations_all": n11["worst_all"],
                        "n1_worst_case_all": n1["worst_all_name"],
                        "n11_worst_case_all": n11["worst_all_name"],
                        "n1_failed_cases": n1["failed"],
                        "n11_failed_cases": n11["failed"],
                        "n1_new_failed_cases": n1["new_failed"],
                        "n11_new_failed_cases": n11["new_failed"],
                        "upgrade_likely": upgrade,
                        "notes": " ".join(notes),
                        "base_violation_details": base_details,
                        "base_snapshot": base_snap,
                        "case_violations": case_n,
                        "case_new_violations": len(case_new),
                        "case_violation_details": case_details,
                        "case_snapshot": case_snap,
                        "n1_violation_details": n1["worst_details"],
                        "n1_snapshot": n1["worst_snap"],
                        "n11_violation_details": n11["worst_details"],
                        "n11_snapshot": n11["worst_snap"],
                    }
                )

        summary = {
            "sites_analyzed": len(load_indices),
            "mw_sizes": mw_sizes,
            "include_n11": include_n11,
            "n1_cases": len(n1_cases),
            "n11_cases": len(n11_cases),
            "upgrade_likely_count": sum(1 for r in rows if r.get("upgrade_likely")),
            "comparison": "new_or_worse_vs_0_mw" if base_converged else "absolute",
            "worse_tol_vm_pu": tols[0],
            "worse_tol_loading_percent": tols[1],
            "baseline_intact_violations": base_violations if base_converged else -1,
            "baseline_n1_cases_with_violations": n1_base_with_viol,
            "baseline_n11_cases_with_violations": n11_base_with_viol,
            "baseline_n1_failed_cases": n1_base_failed,
            "baseline_n11_failed_cases": n11_base_failed,
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
