# -*- coding: utf-8 -*-
"""
Motor Starting analysis for Electrisim.

Steady-state: three pandapower load-flow snapshots (before / during / after)
with locked-rotor current scaled by starting method (DOL, soft-start, star-delta,
autotransformer, reactor).

Dynamic: ANDES Motor3 + Toggle startup (DOL native; soft-start approximated).
"""
from __future__ import annotations

import json
import math
import traceback
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandapower as pp

try:
    import andes
    import andes_electrisim

    _HAS_ANDES = True
except ImportError:
    andes = None  # type: ignore
    andes_electrisim = None  # type: ignore
    _HAS_ANDES = False


VALID_METHODS = ("dol", "soft_start", "star_delta", "autotransformer", "reactor")


def _sf(value: Any, default: float = 0.0) -> float:
    if value is None or value == "" or str(value).lower() in ("none", "null", "nan"):
        return default
    try:
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            return default
        return v
    except (TypeError, ValueError):
        return default


def _sb(value: Any, default: bool = True) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("true", "1", "yes")


def _clean(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (float, np.floating)):
        if math.isnan(float(v)) or math.isinf(float(v)):
            return None
        return float(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    return v


def _parse_motor_ids(params: Dict[str, Any]) -> Optional[Set[str]]:
    raw = params.get("motor_ids") or params.get("motors")
    if raw is None or raw == "" or raw == "all":
        return None
    if isinstance(raw, str):
        # JSON array string or comma-separated
        raw = raw.strip()
        if raw.startswith("["):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = [x.strip() for x in raw.split(",") if x.strip()]
        else:
            raw = [x.strip() for x in raw.split(",") if x.strip()]
    if isinstance(raw, (list, tuple, set)):
        ids = {str(x) for x in raw if x is not None and str(x) != ""}
        return ids or None
    return None


def _method_factor(method: str, params: Dict[str, Any], lrc_pu: float) -> Tuple[float, Dict[str, Any]]:
    """Return (k_m current multiplier vs locked-rotor, meta)."""
    method = (method or "dol").lower().replace("-", "_").replace(" ", "_")
    meta: Dict[str, Any] = {"method": method}
    if method not in VALID_METHODS:
        method = "dol"
        meta["method"] = "dol"
        meta["note"] = "Unknown method; used DOL."

    if method == "dol":
        return 1.0, meta

    if method == "soft_start":
        i_limit = _sf(params.get("i_limit_pu"), 3.0)
        if i_limit <= 0:
            i_limit = 3.0
        meta["i_limit_pu"] = i_limit
        if lrc_pu <= 0:
            return 1.0, meta
        return min(1.0, i_limit / lrc_pu), meta

    if method == "star_delta":
        return 1.0 / 3.0, meta

    if method == "autotransformer":
        tap = _sf(params.get("at_tap_pu"), 0.8)
        if tap <= 0 or tap > 1.0:
            tap = 0.8
        meta["at_tap_pu"] = tap
        # Motor current ≈ (tap)^2 * I_lr; grid current ≈ tap * I_motor = tap^3 * I_lr
        # For voltage dip we inject motor-side current seen from bus ≈ tap^2 * I_lr
        return tap * tap, meta

    if method == "reactor":
        x_r = _sf(params.get("reactor_x_pu"), 0.25)
        if x_r < 0:
            x_r = 0.25
        meta["reactor_x_pu"] = x_r
        return 1.0 / (1.0 + x_r), meta

    return 1.0, meta


def _motor_rated(row: Any, bus_vn_kv: float) -> Dict[str, float]:
    pn = _sf(row.get("pn_mech_mw") if hasattr(row, "get") else row["pn_mech_mw"], 0.0)
    eff_n = _sf(
        row.get("efficiency_n_percent") if hasattr(row, "get") else row["efficiency_n_percent"],
        90.0,
    )
    if eff_n <= 0:
        eff_n = 90.0
    cos_n = _sf(row.get("cos_phi_n") if hasattr(row, "get") else (row["cos_phi_n"] if "cos_phi_n" in row.index else None), 0.0)
    if cos_n <= 0:
        cos_n = _sf(row.get("cos_phi") if hasattr(row, "get") else row["cos_phi"], 0.85)
    if cos_n <= 0:
        cos_n = 0.85
    vn = _sf(row.get("vn_kv") if hasattr(row, "get") else row["vn_kv"], 0.0)
    if vn <= 0:
        vn = bus_vn_kv if bus_vn_kv > 0 else 0.4
    p_elec_mw = pn / (eff_n / 100.0) if pn > 0 else 0.0
    sn_mva = p_elec_mw / cos_n if cos_n > 0 else p_elec_mw
    i_n_ka = sn_mva / (math.sqrt(3.0) * vn) if vn > 0 and sn_mva > 0 else 0.0
    lrc = _sf(row.get("lrc_pu") if hasattr(row, "get") else row["lrc_pu"], 6.0)
    if lrc <= 0:
        lrc = 6.0
    rx = _sf(row.get("rx") if hasattr(row, "get") else row["rx"], 0.15)
    if rx < 0:
        rx = 0.15
    # Locked-rotor PF from R/X
    cos_lr = rx / math.sqrt(1.0 + rx * rx) if rx >= 0 else 0.2
    sin_lr = 1.0 / math.sqrt(1.0 + rx * rx) if rx >= 0 else math.sqrt(1.0 - cos_lr * cos_lr)
    return {
        "pn_mech_mw": pn,
        "sn_mva": sn_mva,
        "vn_kv": vn,
        "i_n_ka": i_n_ka,
        "lrc_pu": lrc,
        "rx": rx,
        "cos_lr": cos_lr,
        "sin_lr": sin_lr,
        "cos_phi_n": cos_n,
        "efficiency_n_percent": eff_n,
    }


def _row_id_name(row: Any, idx: Any) -> Tuple[str, str]:
    name = str(row["name"]) if "name" in row.index and row["name"] is not None else str(idx)
    mid = str(row["id"]) if "id" in row.index and row["id"] is not None else name
    return mid, name


def _select_motor_indices(net, motor_ids: Optional[Set[str]]) -> List[Any]:
    if not hasattr(net, "motor") or net.motor is None or net.motor.empty:
        return []
    selected = []
    for idx, row in net.motor.iterrows():
        mid, name = _row_id_name(row, idx)
        if motor_ids is None:
            if _sb(row.get("in_service") if hasattr(row, "get") else row["in_service"], True):
                selected.append(idx)
            continue
        if mid in motor_ids or name in motor_ids or str(idx) in motor_ids:
            selected.append(idx)
    return selected


def _snapshot_bus_vm(net) -> Dict[Any, float]:
    out = {}
    if not hasattr(net, "res_bus") or net.res_bus is None or net.res_bus.empty:
        return out
    for idx in net.bus.index:
        if idx in net.res_bus.index:
            out[idx] = float(net.res_bus.at[idx, "vm_pu"])
    return out


def _branch_loadings(net) -> List[Dict[str, Any]]:
    results = []
    if hasattr(net, "line") and not net.line.empty and hasattr(net, "res_line") and not net.res_line.empty:
        for idx, row in net.line.iterrows():
            if idx not in net.res_line.index:
                continue
            loading = _sf(net.res_line.at[idx, "loading_percent"], float("nan"))
            mid, name = _row_id_name(row, idx)
            results.append({
                "id": mid,
                "name": name,
                "element": "line",
                "loading_during_percent": _clean(loading),
                "max_i_ka": _clean(_sf(row.get("max_i_ka") if hasattr(row, "get") else row["max_i_ka"], float("nan"))),
                "i_ka": _clean(_sf(net.res_line.at[idx, "i_from_ka"] if "i_from_ka" in net.res_line.columns else None, float("nan"))),
            })
    if hasattr(net, "trafo") and not net.trafo.empty and hasattr(net, "res_trafo") and not net.res_trafo.empty:
        for idx, row in net.trafo.iterrows():
            if idx not in net.res_trafo.index:
                continue
            loading = _sf(net.res_trafo.at[idx, "loading_percent"], float("nan"))
            mid, name = _row_id_name(row, idx)
            results.append({
                "id": mid,
                "name": name,
                "element": "trafo",
                "loading_during_percent": _clean(loading),
                "max_i_ka": None,
                "i_ka": _clean(_sf(net.res_trafo.at[idx, "i_lv_ka"] if "i_lv_ka" in net.res_trafo.columns else None, float("nan"))),
            })
    return results


def _run_pp(net) -> Optional[str]:
    try:
        pp.runpp(net, calculate_voltage_angles=True, init="auto")
        return None
    except Exception as e:
        return str(e)


def _steady_state_start(net, params: Dict[str, Any], in_data: Dict[str, Any]) -> Dict[str, Any]:
    warnings: List[str] = []
    method = str(params.get("starting_method") or params.get("method") or "dol")
    voltage_limit = _sf(params.get("voltage_limit_percent"), 15.0)
    thermal_limit = _sf(params.get("thermal_limit_percent"), 100.0)
    motor_ids = _parse_motor_ids(params)

    if not hasattr(net, "motor") or net.motor is None or net.motor.empty:
        return {
            "error": True,
            "message": "No motors found in the network. Place Motor elements before running Motor Starting.",
            "exception": "empty net.motor",
        }

    selected = _select_motor_indices(net, motor_ids)
    if not selected:
        return {
            "error": True,
            "message": "No motors selected for starting. Select at least one motor.",
            "exception": "empty selection",
        }

    # Remember original motor state
    orig_in_service = {idx: bool(net.motor.at[idx, "in_service"]) for idx in net.motor.index}
    orig_loading = {idx: float(net.motor.at[idx, "loading_percent"]) for idx in net.motor.index}

    # --- Before: starting motors offline ---
    for idx in selected:
        net.motor.at[idx, "in_service"] = False

    err = _run_pp(net)
    if err:
        # restore
        for idx, v in orig_in_service.items():
            net.motor.at[idx, "in_service"] = v
        for idx, v in orig_loading.items():
            net.motor.at[idx, "loading_percent"] = v
        return {
            "error": True,
            "message": "Load flow failed for pre-start (before) snapshot.",
            "exception": err,
        }
    vm_before = _snapshot_bus_vm(net)

    # --- During: locked-rotor loads ---
    motor_results: List[Dict[str, Any]] = []
    lr_load_indices: List[Any] = []

    for idx in selected:
        row = net.motor.loc[idx]
        bus = int(row["bus"])
        bus_vn = float(net.bus.at[bus, "vn_kv"]) if bus in net.bus.index else 0.4
        rated = _motor_rated(row, bus_vn)
        k_m, method_meta = _method_factor(method, params, rated["lrc_pu"])
        i_start = rated["lrc_pu"] * rated["i_n_ka"] * k_m
        # S = √3 V I ; P = S cosφ ; Q = S sinφ  (at rated voltage)
        s_mva = math.sqrt(3.0) * rated["vn_kv"] * i_start if rated["vn_kv"] > 0 else 0.0
        p_mw = s_mva * rated["cos_lr"]
        q_mvar = s_mva * rated["sin_lr"]
        mid, name = _row_id_name(row, idx)
        if s_mva <= 0:
            warnings.append(f"Motor '{name}': zero starting power (check pn_mech_mw, vn_kv, lrc_pu).")
        load_idx = pp.create_load(
            net,
            bus=bus,
            p_mw=p_mw,
            q_mvar=q_mvar,
            name=f"__motor_start_lr_{name}",
            in_service=True,
        )
        lr_load_indices.append(load_idx)
        motor_results.append({
            "id": mid,
            "name": name,
            "bus": str(net.bus.at[bus, "id"]) if "id" in net.bus.columns else str(bus),
            "bus_name": str(net.bus.at[bus, "name"]) if "name" in net.bus.columns else str(bus),
            "method": method_meta.get("method", method),
            "k_method": _clean(k_m),
            "i_start_ka": _clean(i_start),
            "i_rated_ka": _clean(rated["i_n_ka"]),
            "lrc_pu": _clean(rated["lrc_pu"]),
            "p_start_mw": _clean(p_mw),
            "q_start_mvar": _clean(q_mvar),
            "sn_mva": _clean(rated["sn_mva"]),
            "vn_kv": _clean(rated["vn_kv"]),
            **{k: _clean(v) for k, v in method_meta.items() if k != "method"},
        })

    err = _run_pp(net)
    if err:
        for li in lr_load_indices:
            if li in net.load.index:
                net.load.drop(li, inplace=True)
        for idx, v in orig_in_service.items():
            net.motor.at[idx, "in_service"] = v
        for idx, v in orig_loading.items():
            net.motor.at[idx, "loading_percent"] = v
        return {
            "error": True,
            "message": "Load flow failed for locked-rotor (during) snapshot.",
            "exception": err,
        }
    vm_during = _snapshot_bus_vm(net)
    branches = _branch_loadings(net)

    # Remove LR loads
    for li in lr_load_indices:
        if li in net.load.index:
            net.load.drop(li, inplace=True)

    # --- After: motors online at original loading ---
    for idx, v in orig_in_service.items():
        net.motor.at[idx, "in_service"] = v
    for idx, v in orig_loading.items():
        net.motor.at[idx, "loading_percent"] = v
    # Ensure starting motors are in service after start
    for idx in selected:
        net.motor.at[idx, "in_service"] = True

    err = _run_pp(net)
    if err:
        warnings.append(f"Post-start (after) load flow failed: {err}")
        vm_after = {}
    else:
        vm_after = _snapshot_bus_vm(net)

    bus_results: List[Dict[str, Any]] = []
    worst_dip = 0.0
    n_fail_v = 0
    for bidx, brow in net.bus.iterrows():
        vb = vm_before.get(bidx)
        vd = vm_during.get(bidx)
        va = vm_after.get(bidx)
        dip = None
        passed = True
        if vb is not None and vd is not None and vb > 0:
            dip = (vb - vd) / vb * 100.0
            worst_dip = max(worst_dip, dip)
            passed = dip <= voltage_limit
            if not passed:
                n_fail_v += 1
        bid = str(brow["id"]) if "id" in brow.index and brow["id"] is not None else str(bidx)
        bname = str(brow["name"]) if "name" in brow.index and brow["name"] is not None else str(bidx)
        bus_results.append({
            "id": bid,
            "name": bname,
            "vn_kv": _clean(float(brow["vn_kv"])),
            "vm_before": _clean(vb),
            "vm_during": _clean(vd),
            "vm_after": _clean(va),
            "dip_percent": _clean(dip),
            "pass": passed if dip is not None else True,
        })

    n_fail_th = 0
    for br in branches:
        loading = br.get("loading_during_percent")
        ok = True
        if loading is not None:
            ok = float(loading) <= thermal_limit
            if not ok:
                n_fail_th += 1
        br["pass"] = ok
        br["thermal_limit_percent"] = thermal_limit

    return {
        "mode": "steady",
        "buses": bus_results,
        "motors": motor_results,
        "branches": branches,
        "summary": {
            "worst_dip_percent": _clean(worst_dip),
            "n_fail_voltage": n_fail_v,
            "n_fail_thermal": n_fail_th,
            "voltage_limit_percent": voltage_limit,
            "thermal_limit_percent": thermal_limit,
            "starting_method": (method or "dol").lower().replace("-", "_"),
            "n_motors_started": len(selected),
        },
        "parameters": {
            "mode": "steady",
            "starting_method": method,
            "voltage_limit_percent": voltage_limit,
            "thermal_limit_percent": thermal_limit,
            "i_limit_pu": _sf(params.get("i_limit_pu"), 3.0),
            "at_tap_pu": _sf(params.get("at_tap_pu"), 0.8),
            "reactor_x_pu": _sf(params.get("reactor_x_pu"), 0.25),
        },
        "timeseries": None,
        "warnings": warnings,
    }


def _motor_el_from_in_data(in_data: Dict[str, Any], motor_ids: Optional[Set[str]]) -> List[Dict[str, Any]]:
    motors = []
    for _, el in in_data.items():
        if not isinstance(el, dict):
            continue
        typ = str(el.get("typ", ""))
        if not typ.startswith("Motor"):
            continue
        mid = str(el.get("id") or el.get("name") or "")
        name = str(el.get("name") or mid)
        if motor_ids is not None and mid not in motor_ids and name not in motor_ids and str(el.get("userFriendlyName", "")) not in motor_ids:
            continue
        if motor_ids is None and not _sb(el.get("in_service"), True):
            continue
        motors.append(el)
    return motors


def _derive_motor3_params(el: Dict[str, Any], warnings: List[str]) -> Dict[str, Any]:
    name = str(el.get("userFriendlyName") or el.get("name") or "Motor")
    pn = _sf(el.get("pn_mech_mw"), 0.0)
    eff = _sf(el.get("efficiency_n_percent"), 90.0)
    if eff <= 0:
        eff = 90.0
    cos_n = _sf(el.get("cos_phi_n"), 0.0) or _sf(el.get("cos_phi"), 0.85)
    if cos_n <= 0:
        cos_n = 0.85
    sn = (pn / (eff / 100.0) / cos_n) if pn > 0 else 1.0
    if sn <= 0:
        sn = 1.0
        warnings.append(f"Motor '{name}': invalid Sn, used 1 MVA.")
    vn = _sf(el.get("vn_kv"), 0.4)
    if vn <= 0:
        vn = 0.4
    lrc = _sf(el.get("lrc_pu"), 6.0)
    if lrc <= 0:
        lrc = 6.0
    rx = _sf(el.get("rx"), 0.15)
    if rx < 0:
        rx = 0.15
    # Z_lr ≈ 1/lrc on motor base; split via rx
    z_lr = 1.0 / lrc
    xs_eq = z_lr / math.sqrt(1.0 + rx * rx)
    rs = rx * xs_eq
    # Split leakage roughly 50/50 stator/rotor; magnetizing typical
    xs = max(xs_eq * 0.5, 0.05)
    xr1 = max(xs_eq * 0.5, 0.05)
    rr1 = max(rs * 0.8, 0.01)
    rs_use = max(rs * 0.2, 0.005)
    xm = _sf(el.get("xm"), 3.0)
    if xm <= 0:
        xm = 3.0
    hm = _sf(el.get("Hm") or el.get("hm"), 0.5)
    if hm <= 0:
        hm = 0.5
    c1 = _sf(el.get("tm_c1") or el.get("c1"), 0.0)
    c2 = _sf(el.get("tm_c2") or el.get("c2"), 0.0)
    c3 = _sf(el.get("tm_c3") or el.get("c3"), 1.0)
    # ANDES uses aa, bb, c2 for tm = aa + bb*slip + c2*slip^2 in some docs;
    # Motor3 params: c1, c2, c3 for Tm(w)
    return {
        "Sn": sn,
        "Vn": vn,
        "rs": rs_use,
        "xs": xs,
        "rr1": rr1,
        "xr1": xr1,
        "xm": xm,
        "Hm": hm,
        "c1": c1,
        "c2": c2,
        "c3": c3,
        "lrc_pu": lrc,
        "name": name,
    }


def _dynamic_start(params: Dict[str, Any], in_data: Dict[str, Any]) -> Dict[str, Any]:
    if not _HAS_ANDES:
        return {
            "error": True,
            "message": "ANDES is not installed on the backend (required for dynamic motor starting).",
            "exception": "pip install andes",
        }

    warnings: List[str] = []
    method = str(params.get("starting_method") or params.get("method") or "dol").lower().replace("-", "_")
    voltage_limit = _sf(params.get("voltage_limit_percent"), 15.0)
    thermal_limit = _sf(params.get("thermal_limit_percent"), 100.0)
    motor_ids = _parse_motor_ids(params)
    t_start = _sf(params.get("t_start"), 0.1)
    t_end = _sf(params.get("t_end"), 5.0)
    if t_end <= t_start:
        t_end = t_start + 5.0

    motors = _motor_el_from_in_data(in_data, motor_ids)
    if not motors:
        return {
            "error": True,
            "message": "No motors selected for dynamic starting.",
            "exception": "empty motor list",
        }

    return _dynamic_start_rebuild(
        params, in_data, motors, method, voltage_limit, thermal_limit, t_start, t_end, warnings
    )


def _dynamic_start_rebuild(
    params: Dict[str, Any],
    in_data: Dict[str, Any],
    motors: List[Dict[str, Any]],
    method: str,
    voltage_limit: float,
    thermal_limit: float,
    t_start: float,
    t_end: float,
    warnings: List[str],
) -> Dict[str, Any]:
    """Build ANDES system, add Motor3 devices BEFORE setup by patching build flow."""
    dyn_params = dict(params)
    dyn_params["fault_enabled"] = False
    dyn_params["fault_bus"] = ""
    dyn_params["toggle_line"] = ""
    # Prevent fault/toggle in build_system
    dyn_params.pop("fault_bus_name", None)

    try:
        andes.config_logger(stream_level=40)
        # Monkey-patch: build_system always setups. Rebuild by copying approach —
        # call build_system then create a NEW system... Better: use andes_electrisim.build_system
        # but we need motors before setup. Implement local build using andes_electrisim internals
        # by temporarily injecting motors into in_data as a side channel.

        # Practical approach: modify build_system usage — build, then create fresh System
        # from the same in_data by calling a helper that adds motors before setup.
        ss, meta, motor_map = _build_system_with_motors(in_data, dyn_params, motors, method, t_start, warnings)
        warnings.extend(meta.get("warnings") or [])
    except Exception as e:
        return {
            "error": True,
            "message": "Failed to build ANDES system with motors.",
            "exception": str(e),
            "traceback": traceback.format_exc(),
            "warnings": warnings,
        }

    try:
        try:
            ss.TDS.config.noprint = True
        except Exception:
            pass
        ss.TDS.config.tf = t_end
        # Power flow
        ss.PFlow.run()
        if not ss.PFlow.converged:
            return {
                "error": True,
                "message": "ANDES power flow did not converge (required before motor-start TDS).",
                "exception": "PFlow not converged",
                "warnings": warnings,
            }
        ss.TDS.run()
    except Exception as e:
        return {
            "error": True,
            "message": "ANDES time-domain motor starting simulation failed.",
            "exception": str(e),
            "traceback": traceback.format_exc(),
            "warnings": warnings,
        }

    # Extract time and series
    try:
        t = np.asarray(ss.dae.ts.t, dtype=float).tolist()
    except Exception:
        t = []

    bus_series: Dict[str, List[Any]] = {}
    bus_name_by_idx = meta.get("bus_name_by_idx") or {}
    bus_map_inv = {str(v): k for k, v in (meta.get("bus_map") or {}).items()}
    try:
        if hasattr(ss, "Bus") and ss.Bus.n > 0:
            vvar = ss.Bus.v
            addrs = list(vvar.a)
            values = np.asarray(ss.TDS.plt.get_values(addrs), dtype=float)
            for i, addr in enumerate(addrs):
                col = values[:, i] if values.ndim == 2 else values
                bidx = ss.Bus.idx.v[i]
                electrisim_name = bus_name_by_idx.get(str(bidx), str(ss.Bus.name.v[i]))
                # Prefer electrisim id from bus_map reverse via name
                eid = electrisim_name
                for ename, aidx in (meta.get("bus_map") or {}).items():
                    if aidx == bidx:
                        eid = ename
                        break
                bus_series[str(eid)] = {
                    "id": str(eid),
                    "name": electrisim_name,
                    "v": [_clean(x) for x in col.tolist()],
                }
    except Exception as e:
        warnings.append(f"Could not extract bus voltage series: {e}")

    motor_series: Dict[str, Any] = {}
    motor_results: List[Dict[str, Any]] = []
    slip_thresh = _sf(params.get("slip_threshold"), 0.02)

    try:
        if hasattr(ss, "Motor3") and ss.Motor3.n > 0:
            m = ss.Motor3
            # currents
            def _series(var_name):
                if not hasattr(m, var_name):
                    return None
                var = getattr(m, var_name)
                addrs = list(var.a)
                vals = np.asarray(ss.TDS.plt.get_values(addrs), dtype=float)
                return vals

            id_vals = _series("Id")
            iq_vals = _series("Iq")
            slip_vals = _series("slip")
            te_vals = _series("te")
            tm_vals = _series("tm")
            p_vals = _series("p")
            q_vals = _series("q")

            for i in range(m.n):
                midx = str(m.idx.v[i])
                info = motor_map.get(midx, {"id": midx, "name": str(m.name.v[i])})
                i_mag = None
                if id_vals is not None and iq_vals is not None:
                    idi = id_vals[:, i] if id_vals.ndim == 2 else id_vals
                    iqi = iq_vals[:, i] if iq_vals.ndim == 2 else iq_vals
                    i_mag = np.sqrt(np.asarray(idi, dtype=float) ** 2 + np.asarray(iqi, dtype=float) ** 2)

                slip_list = None
                if slip_vals is not None:
                    sli = slip_vals[:, i] if slip_vals.ndim == 2 else slip_vals
                    slip_list = [_clean(x) for x in np.asarray(sli, dtype=float).tolist()]

                start_time_s = None
                if slip_list and t:
                    for ti, s in zip(t, slip_list):
                        if s is not None and abs(s) <= slip_thresh and ti >= t_start:
                            start_time_s = float(ti) - t_start
                            break

                i_list = [_clean(x) for x in i_mag.tolist()] if i_mag is not None else None
                i_start_pu = None
                if i_list:
                    # first sample after t_start
                    for ti, iv in zip(t, i_list):
                        if ti >= t_start and iv is not None:
                            i_start_pu = iv
                            break

                te_list = None
                if te_vals is not None:
                    tei = te_vals[:, i] if te_vals.ndim == 2 else te_vals
                    te_list = [_clean(x) for x in np.asarray(tei, dtype=float).tolist()]

                motor_series[info["id"]] = {
                    "id": info["id"],
                    "name": info.get("name"),
                    "i_pu": i_list,
                    "slip": slip_list,
                    "te": te_list,
                }
                motor_results.append({
                    "id": info["id"],
                    "name": info.get("name"),
                    "method": info.get("method", method),
                    "start_time_s": _clean(start_time_s),
                    "i_start_pu": _clean(i_start_pu),
                    "note": info.get("note"),
                    "pass": start_time_s is not None,
                })
    except Exception as e:
        warnings.append(f"Could not extract motor series: {e}")

    # Bus dip from min voltage after t_start vs pre-start
    bus_results: List[Dict[str, Any]] = []
    worst_dip = 0.0
    n_fail_v = 0
    for eid, ser in bus_series.items():
        v = ser.get("v") or []
        if not v or not t:
            continue
        # before: average of samples before t_start
        before_vals = [vv for ti, vv in zip(t, v) if ti < t_start and vv is not None]
        during_vals = [vv for ti, vv in zip(t, v) if ti >= t_start and vv is not None]
        vb = float(np.mean(before_vals)) if before_vals else (v[0] if v[0] is not None else None)
        vd = float(np.min(during_vals)) if during_vals else None
        va = during_vals[-1] if during_vals else None
        dip = None
        passed = True
        if vb is not None and vd is not None and vb > 0:
            dip = (vb - vd) / vb * 100.0
            worst_dip = max(worst_dip, dip)
            passed = dip <= voltage_limit
            if not passed:
                n_fail_v += 1
        bus_results.append({
            "id": ser["id"],
            "name": ser["name"],
            "vm_before": _clean(vb),
            "vm_during": _clean(vd),
            "vm_after": _clean(va),
            "dip_percent": _clean(dip),
            "pass": passed if dip is not None else True,
        })

    return {
        "mode": "dynamic",
        "buses": bus_results,
        "motors": motor_results,
        "branches": [],
        "summary": {
            "worst_dip_percent": _clean(worst_dip),
            "n_fail_voltage": n_fail_v,
            "n_fail_thermal": 0,
            "voltage_limit_percent": voltage_limit,
            "thermal_limit_percent": thermal_limit,
            "starting_method": method,
            "n_motors_started": len(motor_map),
            "t_start": t_start,
            "t_end": t_end,
        },
        "parameters": {
            "mode": "dynamic",
            "starting_method": method,
            "voltage_limit_percent": voltage_limit,
            "thermal_limit_percent": thermal_limit,
            "t_start": t_start,
            "t_end": t_end,
            "i_limit_pu": _sf(params.get("i_limit_pu"), 3.0),
        },
        "timeseries": {
            "t": [_clean(x) for x in t],
            "buses": {k: v for k, v in bus_series.items()},
            "motors": motor_series,
        },
        "warnings": warnings,
        "defaults_applied": meta.get("defaults_applied") or [],
    }


def _build_system_with_motors(
    in_data: Dict[str, Any],
    params: Dict[str, Any],
    motors: List[Dict[str, Any]],
    method: str,
    t_start: float,
    warnings: List[str],
):
    """
    Build ANDES system like andes_electrisim.build_system but insert Motor3 + Toggle
    before ss.setup().
    """
    # Strategy: temporarily wrap andes.System.add / use build then reconstruct.
    # Cleanest reliable way: copy build_system source flow by calling it after
    # monkeypatching System.setup to no-op, add motors, then setup.

    real_setup = None
    setup_calls = []

    class _SystemProxy:
        pass

    # Use andes_electrisim.build_system with patched setup
    original_system = andes.System

    class SystemNoSetup(original_system):
        def setup(self, *args, **kwargs):
            setup_calls.append(self)
            return self

    andes.System = SystemNoSetup
    try:
        ss, meta = andes_electrisim.build_system(in_data, params)
    finally:
        andes.System = original_system

    bus_map = meta["bus_map"]
    motor_map: Dict[str, Dict[str, Any]] = {}
    toggle_i = 0

    for el in motors:
        bus_key = el.get("bus")
        bus_idx = bus_map.get(bus_key)
        if bus_idx is None:
            for bname, bidx in bus_map.items():
                if str(bname) == str(bus_key):
                    bus_idx = bidx
                    break
        if bus_idx is None:
            warnings.append(f"Motor '{el.get('name')}': bus '{bus_key}' not found; skipped.")
            continue

        mparams = _derive_motor3_params(el, warnings)
        mid = str(el.get("id") or el.get("name"))
        mname = mparams.pop("name")
        lrc = mparams.pop("lrc_pu")
        note = None
        applied_method = "dol"
        if method == "soft_start":
            i_limit = _sf(params.get("i_limit_pu"), 3.0)
            if lrc > 0 and i_limit > 0:
                scale = min(1.0, i_limit / lrc)
                mparams["Sn"] = mparams["Sn"] * scale
                note = "Soft-start approximated by scaling motor Sn so initial current ≈ I_limit_pu."
                applied_method = "soft_start"
                warnings.append(f"Motor '{mname}': {note}")
        elif method not in ("dol", "soft_start"):
            note = f"Method '{method}' uses DOL dynamics in ANDES; use steady-state mode for exact method factors."
            warnings.append(f"Motor '{mname}': {note}")

        midx = f"Motor_{mid}"
        ss.add(
            "Motor3",
            idx=midx,
            name=mname,
            bus=bus_idx,
            u=0,
            Sn=mparams["Sn"],
            Vn=mparams["Vn"],
            rs=mparams["rs"],
            xs=mparams["xs"],
            rr1=mparams["rr1"],
            xr1=mparams["xr1"],
            xm=mparams["xm"],
            Hm=mparams["Hm"],
            c1=mparams["c1"],
            c2=mparams["c2"],
            c3=mparams["c3"],
        )
        toggle_i += 1
        ss.add(
            "Toggle",
            idx=f"Toggle_Motor_{toggle_i}",
            model="Motor3",
            dev=midx,
            t=t_start,
        )
        motor_map[midx] = {
            "id": mid,
            "name": mname,
            "bus": bus_key,
            "method": applied_method,
            "note": note,
            "lrc_pu": lrc,
        }

    ss.setup()
    return ss, meta, motor_map


def motor_starting(net, params: Dict[str, Any], in_data: Dict[str, Any]) -> str:
    """Entry point. Returns JSON string."""
    try:
        mode = str(params.get("mode") or "steady").lower().strip()
        if mode in ("dynamic", "transient", "tds", "andes"):
            payload = _dynamic_start(params, in_data)
        else:
            payload = _steady_state_start(net, params, in_data)
        return json.dumps(payload, allow_nan=False)
    except Exception as e:
        return json.dumps({
            "error": True,
            "message": "Motor starting calculation failed.",
            "exception": str(e),
            "traceback": traceback.format_exc(),
        })
