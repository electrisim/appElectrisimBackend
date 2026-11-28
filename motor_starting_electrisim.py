# -*- coding: utf-8 -*-
"""
Motor Starting analysis for Electrisim.

Steady-state: three pandapower load-flow snapshots (before / during / after)
with locked-rotor current scaled by starting method (DOL, soft-start, star-delta,
autotransformer, reactor).

Dynamic: ANDES Motor3 + Toggle startup (DOL native; soft-start approximated).

Both modes model the sources alike. Before the start every source holds the voltage of the
load flow. From the start on, each External Grid is a fixed voltage behind its short-circuit
impedance (S"k min or max, the study's ``grid_sc_case``), so its bus dips with the current it
supplies. Synchronous generators are their own dynamic model in ANDES; in the steady-state
locked-rotor snapshot each is a fixed voltage behind its transient reactance xd' (its voltage
regulator has not acted yet), and it controls its voltage again after the start.
"""
from __future__ import annotations

import cmath
import contextlib
import json
import math
import re
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

# Time step of the dynamic (ANDES) motor start: dips and run-up times change by under 1 % below it.
_TDS_STEP_S = 0.005

# A synchronous generator's transient reactance xd' when none is entered: the GENROU default of
# the dynamic model (andes_electrisim._DEFAULT_GENROU["xd1"]), on the generator's rating.
_GEN_XD1_DEFAULT = 0.3
# Smallest grid source impedance, in pu on the study's system base (sn_mva, 100 MVA by default),
# as the ANDES grid source: S"k is capped at sn_mva / 1e-4 (1e6 MVA on 100 MVA).
_Z_SOURCE_MIN_PU = 1e-4
# Short-circuit power assumed for an External Grid with none set, as the ANDES grid source.
_S_SC_DEFAULT_MVA = 10000.0


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


def _grid_sc_case(params: Dict[str, Any]) -> str:
    """The External Grid impedance comes from S"k min ("min", the deeper dip, default) or S"k max."""
    return "max" if str(params.get("grid_sc_case") or "min").strip().lower() == "max" else "min"


def _grid_source_notes(grid_sources: List[Dict[str, Any]]) -> List[str]:
    """Warnings for External Grids whose impedance did not come from the requested S"k
    (worded as the External Grid dialog names the fields)."""
    notes = []
    for g in grid_sources:
        if g.get("default_s_sc"):
            notes.append(f"External Grid '{g['name']}': no Short Circuit Power is set; its impedance uses "
                         f"{g['s_sc_mva']:.0f} MVA.")
        elif g.get("case_used") != g.get("case_requested"):
            notes.append(f"External Grid '{g['name']}': Min Short Circuit Power is not set; its impedance uses "
                         f"the Max Short Circuit Power, {g['s_sc_mva']:.0f} MVA.")
    return notes


def _generator_transient_impedance(el: Dict[str, Any], bus_vn_kv: float, sn_base: float) -> Tuple[complex, float, float]:
    """(ra + j xd' on the system base at the bus voltage, xd' pu, rating MVA) of a synchronous generator.

    The same machine data, defaults and bases as the generator of the dynamic (ANDES) model.
    """
    def _value(keys: Tuple[str, ...], default: float, positive: bool) -> float:
        for key in keys:
            raw = el.get(key)
            if raw is None or str(raw).strip().lower() in ("", "none", "null"):
                continue
            v = _sf(raw, default)
            if positive and not v > 0:
                continue
            return v
        return default

    machine = str(el.get("dyn_machine_model") or el.get("machine_model") or "GENROU").strip().upper()
    xd1_keys = ("dyn_xd1", "xd1", "xdss_pu") if machine == "GENCLS" else ("dyn_xd1", "xd1")
    xd1 = _value(xd1_keys, _GEN_XD1_DEFAULT, True)
    ra = max(_value(("dyn_ra", "ra"), 0.0, False), 0.0)
    sn = _sf(el.get("sn_mva"), 0.0)
    if sn <= 0:
        sn = max(abs(_sf(el.get("p_mw")) * _sf(el.get("scaling"), 1.0)) * 1.25, 100.0)
    vn = _sf(el.get("vn_kv"), 0.0)
    if vn <= 0 or (bus_vn_kv > 0 and abs(vn - bus_vn_kv) / bus_vn_kv > 0.5):
        vn = bus_vn_kv
    scale = sn_base / sn * ((vn / bus_vn_kv) ** 2 if bus_vn_kv > 0 else 1.0)
    return complex(ra, xd1) * scale, xd1, sn


def _source_emfs(net, in_data: Dict[str, Any], case: str, warnings: List[str],
                 sn_study_mva: float = 100.0) -> Dict[str, List[Dict[str, Any]]]:
    """The voltage behind each source's impedance, from the pre-start load flow in ``net.res_*``.

    External Grid: its short-circuit impedance |Z| = U^2 / S"k (``case``), split by R/X, the
    source of the dynamic mode (whose system base is ``sn_study_mva``). Synchronous generator:
    ra + j xd'. E = V + Z I with V and I of the load flow, so the network is unchanged until the
    start draws more current.
    """
    sb = float(net.sn_mva)  # pandapower's own base (1 MVA by default), not the study's
    out: Dict[str, List[Dict[str, Any]]] = {"grids": [], "generators": []}

    def _v(bus: int) -> complex:
        return float(net.res_bus.at[bus, "vm_pu"]) * cmath.exp(1j * math.radians(float(net.res_bus.at[bus, "va_degree"])))

    def _emf(bus: int, p_mw: Any, q_mvar: Any, z: complex) -> Optional[complex]:
        p, q = _sf(p_mw, float("nan")), _sf(q_mvar, float("nan"))
        if math.isnan(p) or math.isnan(q) or bus not in net.res_bus.index:
            return None
        v = _v(bus)
        return v + z * (complex(p, q) / sb / v).conjugate() if abs(v) > 0 else None

    names = getattr(net, "user_friendly_names", None) or {}
    for idx, row in net.ext_grid.iterrows():
        if not _sb(row.get("in_service"), True) or idx not in net.res_ext_grid.index:
            continue
        name = str(names.get(row.get("name"), row.get("name")))
        case_used = case
        s_sc = _sf(row.get(f"s_sc_{case}_mva"), 0.0)
        if s_sc <= 0 and case == "min":
            case_used = "max"
            s_sc = _sf(row.get("s_sc_max_mva"), 0.0)
        default_s_sc = s_sc <= 0
        if default_s_sc:
            s_sc = _S_SC_DEFAULT_MVA
        rx = max(_sf(row.get(f"rx_{case_used}"), 0.0), 0.0)
        z_abs = sb / min(s_sc, sn_study_mva / _Z_SOURCE_MIN_PU)
        x = z_abs / math.sqrt(1.0 + rx * rx)
        bus = int(row["bus"])
        z = complex(rx * x, x)
        e = _emf(bus, net.res_ext_grid.at[idx, "p_mw"], net.res_ext_grid.at[idx, "q_mvar"], z)
        if e is None:
            warnings.append(f"External Grid '{name}': no load-flow result; it stays an ideal source.")
            continue
        out["grids"].append({"index": idx, "bus": bus, "z": z, "e": e, "name": name, "case_requested": case,
                             "case_used": case_used, "s_sc_mva": s_sc, "rx": rx, "default_s_sc": default_s_sc})

    if hasattr(net, "gen") and net.gen is not None and not net.gen.empty:
        # Only the diagram's synchronous generators: a STATCOM's voltage-source stand-in stays as it is.
        machines = {str(el.get("name")): el for el in in_data.values()
                    if isinstance(el, dict) and str(el.get("typ", "")).startswith("Generator")
                    and "Asymmetric" not in str(el.get("typ")) and "1ph" not in str(el.get("typ"))}
        for idx, row in net.gen.iterrows():
            el = machines.get(str(row.get("name")))
            if el is None or not _sb(row.get("in_service"), True) or idx not in net.res_gen.index:
                continue
            bus = int(row["bus"])
            name = str(el.get("userFriendlyName") or el.get("name"))
            z, xd1, sn = _generator_transient_impedance(el, float(net.bus.at[bus, "vn_kv"]), sb)
            e = _emf(bus, net.res_gen.at[idx, "p_mw"], net.res_gen.at[idx, "q_mvar"], z)
            if e is None:
                warnings.append(f"Generator '{name}': no load-flow result; it keeps its voltage during the start.")
                continue
            out["generators"].append({"index": idx, "bus": bus, "z": z, "e": e, "name": name, "xd1_pu": xd1,
                                      "sn_mva": sn})
    return out


@contextlib.contextmanager
def _sources_behind_impedance(net, sources: Dict[str, List[Dict[str, Any]]], generators: bool):
    """Within the block each External Grid (and, with ``generators``, each synchronous generator)
    is a fixed voltage behind its impedance: the source sits on a helper bus at its EMF and the
    impedance joins that bus to its own. The tables are put back as they were on exit (the
    load-flow results of the block stay, for the buses and branches of the diagram)."""
    saved = {name: net[name].copy() for name in ("bus", "ext_grid", "gen", "impedance")}

    def _behind(src: Dict[str, Any]) -> int:
        aux = pp.create_bus(net, vn_kv=float(net.bus.at[src["bus"], "vn_kv"]), name=f"__motor_start_emf_{src['name']}")
        pp.create_impedance(net, aux, src["bus"], rft_pu=src["z"].real, xft_pu=src["z"].imag,
                            sn_mva=float(net.sn_mva), name=f"__motor_start_z_{src['name']}")
        return aux

    try:
        for g in sources["grids"]:
            idx = g["index"]
            net.ext_grid.at[idx, "bus"] = _behind(g)
            net.ext_grid.at[idx, "vm_pu"] = abs(g["e"])
            net.ext_grid.at[idx, "va_degree"] = math.degrees(cmath.phase(g["e"]))
        if generators:
            for g in sources["generators"]:
                aux = _behind(g)
                net.gen.at[g["index"], "in_service"] = False
                pp.create_ext_grid(net, aux, vm_pu=abs(g["e"]), va_degree=math.degrees(cmath.phase(g["e"])),
                                   name=f"__motor_start_emf_{g['name']}")
        yield
    finally:
        for name, table in saved.items():
            net[name] = table


def _source_model_notes(sources: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    notes = [
        f"External Grid '{g['name']}': a fixed voltage behind its short-circuit impedance during and after the "
        f"start ({g['case_used']} short-circuit power {g['s_sc_mva']:.0f} MVA, R/X {g['rx']:g})."
        for g in sources["grids"]
    ]
    notes += [
        f"Generator '{g['name']}': a fixed voltage behind its transient reactance xd' = {g['xd1_pu']:g} pu "
        f"({g['sn_mva']:g} MVA) during the start; it controls its voltage again after it."
        for g in sources["generators"]
    ]
    return notes


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
        }

    selected = _select_motor_indices(net, motor_ids)
    if not selected:
        return {
            "error": True,
            "message": "No motors selected for starting. Select at least one motor.",
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

    # From the start on, the sources are their voltage behind impedance from this load flow
    # (the External Grid's short-circuit impedance, a generator's xd'), as in dynamic mode.
    grid_case = _grid_sc_case(params)
    sn_study = _sf(params.get("sn_mva"), 100.0)
    sources = _source_emfs(net, in_data, grid_case, warnings, sn_study if sn_study > 0 else 100.0)
    warnings.extend(_grid_source_notes(sources["grids"]))

    # --- During: each starting motor is its locked-rotor impedance ---
    # A locked rotor is an impedance, so it is a shunt drawing the locked-rotor P and Q at the
    # motor's rated voltage: its current follows the voltage the motor sees. (A constant-power
    # load sized at rated voltage overstated the current whenever the voltage sagged, so dips
    # came out too deep and simultaneous starts had no load-flow solution.)
    starts: List[Dict[str, Any]] = []
    for idx in selected:
        row = net.motor.loc[idx]
        bus = int(row["bus"])
        bus_vn = float(net.bus.at[bus, "vn_kv"]) if bus in net.bus.index else 0.4
        rated = _motor_rated(row, bus_vn)
        k_m, method_meta = _method_factor(method, params, rated["lrc_pu"])
        i_lr = rated["lrc_pu"] * rated["i_n_ka"]
        s_lr = math.sqrt(3.0) * rated["vn_kv"] * i_lr if rated["vn_kv"] > 0 else 0.0
        mid, name = _row_id_name(row, idx)
        if s_lr <= 0:
            warnings.append(f"Motor '{name}': zero starting power (check pn_mech_mw, vn_kv, lrc_pu).")
        # k is the starter's current at rated voltage relative to DOL. Star-delta, autotransformer
        # and reactor are passive, so they scale the locked-rotor admittance by k. A soft starter
        # holds its current limit k x I_lr whatever the voltage (re-sized after the load flow).
        constant_current = method_meta.get("method") == "soft_start"
        shunt_idx = pp.create_shunt(
            net,
            bus=bus,
            p_mw=k_m * s_lr * rated["cos_lr"],
            q_mvar=k_m * s_lr * rated["sin_lr"],
            vn_kv=rated["vn_kv"],
            name=f"__motor_start_lr_{name}",
            in_service=True,
        )
        starts.append({
            "idx": idx, "bus": bus, "bus_vn": bus_vn, "rated": rated, "k_m": k_m, "i_lr": i_lr,
            "s_lr": s_lr, "shunt": shunt_idx, "constant_current": constant_current,
            "id": mid, "name": name, "meta": method_meta,
        })

    def _remove_start_shunts() -> None:
        drop = [s["shunt"] for s in starts if s["shunt"] in net.shunt.index]
        if drop:
            net.shunt.drop(drop, inplace=True)

    # The generators' voltage regulators have not acted yet: each is a voltage behind xd'.
    with _sources_behind_impedance(net, sources, generators=True):
        err = _run_pp(net)
        soft = [s for s in starts if s["constant_current"] and s["s_lr"] > 0]
        for _ in range(30 if soft and not err else 0):
            worst = 0.0
            for s in soft:
                v_kv = float(net.res_bus.at[s["bus"], "vm_pu"]) * s["bus_vn"]
                if v_kv <= 0:
                    continue
                vn = s["rated"]["vn_kv"]
                # The shunt that draws the limit at this voltage, but never more than the motor's own
                # locked-rotor admittance (a soft starter fully on is DOL).
                s_ref = min(math.sqrt(3.0) * vn * s["k_m"] * s["i_lr"] * vn / v_kv, s["s_lr"])
                s_old = math.hypot(float(net.shunt.at[s["shunt"], "p_mw"]), float(net.shunt.at[s["shunt"], "q_mvar"]))
                worst = max(worst, abs(s_ref - s_old) / s["s_lr"])
                net.shunt.at[s["shunt"], "p_mw"] = s_ref * s["rated"]["cos_lr"]
                net.shunt.at[s["shunt"], "q_mvar"] = s_ref * s["rated"]["sin_lr"]
            if worst < 1e-9:
                break
            err = _run_pp(net)
            if err:
                break

    if err:
        _remove_start_shunts()
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

    # I start is the current at the voltage the motor actually sees during the start.
    motor_results: List[Dict[str, Any]] = []
    for s in starts:
        rated = s["rated"]
        v_kv = float(net.res_bus.at[s["bus"], "vm_pu"]) * s["bus_vn"]
        p_mw = float(net.res_shunt.at[s["shunt"], "p_mw"])
        q_mvar = float(net.res_shunt.at[s["shunt"], "q_mvar"])
        i_start = math.hypot(p_mw, q_mvar) / (math.sqrt(3.0) * v_kv) if v_kv > 0 else 0.0
        v_start = v_kv / rated["vn_kv"] if rated["vn_kv"] > 0 else None
        if s["constant_current"] and s["i_lr"] > 0 and i_start < s["k_m"] * s["i_lr"] * (1.0 - 1e-6):
            warnings.append(
                f"Motor '{s['name']}': the soft starter cannot hold its current limit at "
                f"{v_start:.3f} pu; it is fully on and the motor starts as DOL."
            )
        motor_results.append({
            "id": s["id"],
            "name": s["name"],
            "bus": str(net.bus.at[s["bus"], "id"]) if "id" in net.bus.columns else str(s["bus"]),
            "bus_name": str(net.bus.at[s["bus"], "name"]) if "name" in net.bus.columns else str(s["bus"]),
            "method": s["meta"].get("method", method),
            "k_method": _clean(s["k_m"]),
            "i_start_ka": _clean(i_start),
            "v_start_pu": _clean(v_start),
            "i_rated_ka": _clean(rated["i_n_ka"]),
            "lrc_pu": _clean(rated["lrc_pu"]),
            "p_start_mw": _clean(p_mw),
            "q_start_mvar": _clean(q_mvar),
            "sn_mva": _clean(rated["sn_mva"]),
            "vn_kv": _clean(rated["vn_kv"]),
            **{k: _clean(v) for k, v in s["meta"].items() if k != "method"},
        })

    # Remove the locked-rotor shunts
    _remove_start_shunts()

    # --- After: motors online at original loading ---
    for idx, v in orig_in_service.items():
        net.motor.at[idx, "in_service"] = v
    for idx, v in orig_loading.items():
        net.motor.at[idx, "loading_percent"] = v
    # Ensure starting motors are in service after start
    for idx in selected:
        net.motor.at[idx, "in_service"] = True

    # After the start the generators control their voltage again; the External Grid stays a
    # voltage behind its impedance, so its bus settles a little lower with the motor running.
    with _sources_behind_impedance(net, sources, generators=False):
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
            "grid_sc_case": grid_case,
        },
        "timeseries": None,
        "warnings": warnings,
        "defaults_applied": _source_model_notes(sources),
    }


def _motor_el_from_in_data(in_data: Dict[str, Any], motor_ids: Optional[Set[str]]) -> List[Dict[str, Any]]:
    motors = []
    for _, el in in_data.items():
        if not isinstance(el, dict):
            continue
        typ = str(el.get("typ", ""))
        # The study's own settings entry ("MotorStartingPandaPower Parameters") is not a motor.
        if not typ.startswith("Motor") or "Parameters" in typ:
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
    # Hm is on the motor rating (ANDES converts it with Sn). An explicit 0 for a load-torque
    # coefficient is a value, not "unset".
    hm = _first_set(el, ("Hm", "hm"), 0.5)
    if hm <= 0:
        hm = 0.5
    c1 = _first_set(el, ("tm_c1", "c1"), 0.0)
    c2 = _first_set(el, ("tm_c2", "c2"), 0.0)
    c3 = _first_set(el, ("tm_c3", "c3"), 1.0)
    # Load torque Tm(w) = t_load * (c1 + c2 w + c3 w^2), with t_load the motor's torque at its
    # loading: rated torque is Pn / Sn = efficiency x cos phi on the Sn base. So c3 = 1 is a fan
    # or pump that takes the motor's loading at full speed.
    loading = _sf(el.get("loading_percent"), 100.0)
    if loading <= 0:
        loading = 100.0
    t_load = loading / 100.0 * eff / 100.0 * cos_n
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
        "t_load": t_load,
        "lrc_pu": lrc,
        "name": name,
    }


def _first_set(el: Dict[str, Any], keys: Tuple[str, ...], default: float) -> float:
    """The first of ``keys`` that holds a number (0 included)."""
    for key in keys:
        raw = el.get(key)
        if raw is None or str(raw).strip().lower() in ("", "none", "null", "nan"):
            continue
        return _sf(raw, default)
    return default


def _motor3_torque(mp: Dict[str, Any], v: float, s: float) -> float:
    """Steady-state electrical torque of the Motor3 equivalent circuit (motor base) at slip ``s``."""
    z_m = complex(0.0, mp["xm"])
    z_r = complex(mp["rr1"] / s, mp["xr1"])
    i_s = v / (complex(mp["rs"], mp["xs"]) + z_m * z_r / (z_m + z_r))
    i_r = i_s * z_m / (z_m + z_r)
    return abs(i_r) ** 2 * mp["rr1"] / s


def _load_torque(mp: Dict[str, Any], s: float) -> float:
    w = 1.0 - s
    return mp["t_load"] * (mp["c1"] + mp["c2"] * w + mp["c3"] * w * w)


def _running_slip(mp: Dict[str, Any], v: float) -> Optional[float]:
    """Slip at which the motor carries its load at voltage ``v`` (pu of its rating).

    None when the load torque exceeds the motor's pull-out torque at that voltage.
    """
    if v <= 0:
        return None
    # Pull-out (breakdown) slip from the Thevenin equivalent seen by the rotor branch.
    z_m = complex(0.0, mp["xm"])
    z_s = complex(mp["rs"], mp["xs"])
    z_th = z_s * z_m / (z_s + z_m)
    s_bd = min(1.0, mp["rr1"] / abs(z_th + complex(0.0, mp["xr1"])))
    lo, hi = 1e-9, s_bd
    if _motor3_torque(mp, v, lo) >= _load_torque(mp, lo):
        return 0.0
    if _motor3_torque(mp, v, hi) < _load_torque(mp, hi):
        return None
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if _motor3_torque(mp, v, mid) >= _load_torque(mp, mid):
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def _andes_load_torque(ss, mp: Dict[str, Any], t_base: float, warnings: List[str]) -> Tuple[float, float, float]:
    """Motor3 c1..c3 for Tm(w) = t_base * (c1 + c2 w + c3 w^2), with t_base on the system base.

    ANDES does not convert c1..c3 to the system base. Motor3 in ANDES 1.10 also builds
    Tm(slip) = (c1 + c2 + c3) + (-c2 - 2 c3) slip + c2 slip^2, with c2 where c3 belongs, so the
    coefficients are chosen to give the intended curve through that formula.
    """
    c1, c2, c3 = mp["c1"] * t_base, mp["c2"] * t_base, mp["c3"] * t_base
    v_str = str(getattr(getattr(ss.Motor3, "tm", None), "v_str", "") or "")
    slip2 = re.search(r"\b(c[123])\s*\*\s*slip\s*\*\s*slip\b", v_str)
    if slip2 is None or not re.search(r"\baa\s*\+\s*bb\s*\*\s*slip\b", v_str):
        warnings.append(f"Motor3 load torque formula not recognised ('{v_str}'); c1..c3 passed as given.")
        return c1, c2, c3
    if slip2.group(1) == "c3":
        return c1, c2, c3
    # Intended Tm(slip) = a + b slip + c slip^2; ANDES gives c' slip^2 with c' its own c2.
    a, b, c = c1 + c2 + c3, -c2 - 2.0 * c3, c3
    c2_andes = c
    c3_andes = (-b - c2_andes) / 2.0
    return a - c2_andes - c3_andes, c2_andes, c3_andes


class _StartAtStandstill:
    """TDS hook (``TDS.callpert``): the motors wait for their Toggle at rest.

    Motor3 initialises its slip as 1.0 * u, so a motor that is off (u = 0) sat at slip 0 and its
    "start" began at synchronous speed. Before the first step this sets every switched-off motor
    to slip 1 with no current and no rotor flux; with u = 0 nothing moves until the Toggle.
    """

    def __init__(self, motor_model, then=None):
        self.model = motor_model
        self.then = then  # a hook that was already set runs after this one
        self.done = False

    def __call__(self, t, system):
        if not self.done:
            self.done = True
            self._at_rest(system)
        if self.then is not None:
            self.then(t, system)

    def _at_rest(self, system):
        m = self.model
        off = np.asarray(m.u.v, dtype=float) == 0
        if not off.any():
            return
        dae = system.dae
        dae.x[np.asarray(m.slip.a)[off]] = 1.0
        for var in (m.e1d, m.e1q):
            dae.x[np.asarray(var.a)[off]] = 0.0
        for var in (m.Id, m.Iq, m.te, m.tm, m.p, m.q):
            dae.y[np.asarray(var.a)[off]] = 0.0
        system.vars_to_models()


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
        warnings.extend(_grid_source_notes(meta.get("grid_sources") or []))
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
        # A starting motor's rotor flux turns at slip x 50 Hz. ANDES's default 1/30 s step does not
        # resolve it: the current and the dip during the run-up came out about 10 % high.
        tstep = _sf(params.get("tstep"), 0.0)
        ss.TDS.config.tstep = tstep if tstep > 0 else _TDS_STEP_S
        # Power flow
        ss.PFlow.run()
        if not ss.PFlow.converged:
            return {
                "error": True,
                "message": "ANDES power flow did not converge (required before motor-start TDS).",
                "exception": "PFlow not converged",
                "warnings": warnings,
            }
        if hasattr(ss, "Motor3") and ss.Motor3.n > 0:
            ss.TDS.callpert = _StartAtStandstill(ss.Motor3, then=ss.TDS.callpert)
        ss.TDS.run()
        stored = np.asarray(ss.dae.ts.t, dtype=float)
        t_last = float(stored[-1]) if stored.size else 0.0
        if t_last < t_end - 1e-6:
            warnings.append(
                f"The time-domain simulation stopped at {t_last:.3f} s instead of {t_end:g} s"
                + (f": {ss.TDS.err_msg}" if getattr(ss.TDS, "err_msg", "") else " (no convergence).")
            )
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
            values = andes_electrisim.tds_values(ss, vvar)
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
    # The start is complete when the motor is within this slip of its running speed.
    slip_thresh = _sf(params.get("slip_threshold"), 0.02)

    try:
        if hasattr(ss, "Motor3") and ss.Motor3.n > 0:
            m = ss.Motor3
            sb = float(meta.get("sn_mva") or 100.0)
            bus_vn = {str(b): float(vn) for b, vn in zip(ss.Bus.idx.v, ss.Bus.Vn.v)}
            bus_col = {str(b): k for k, b in enumerate(ss.Bus.idx.v)}
            v_all = andes_electrisim.tds_values(ss, ss.Bus.v)
            t_arr = np.asarray(t, dtype=float)
            # The sample at the connect time is recorded before the Toggle switches the motor on.
            after = np.nonzero(t_arr > t_start + 1e-9)[0]

            def _series(var_name):
                if not hasattr(m, var_name):
                    return None
                return andes_electrisim.tds_values(ss, getattr(m, var_name))

            id_vals = _series("Id")
            iq_vals = _series("Iq")
            slip_vals = _series("slip")
            te_vals = _series("te")

            for i in range(m.n):
                midx = str(m.idx.v[i])
                info = motor_map.get(midx, {"id": midx, "name": str(m.name.v[i])})
                mp = info.get("model")
                bus = str(m.bus.v[i])
                vb = bus_vn.get(bus) or info.get("vn_kv") or 1.0
                vn = info.get("vn_kv") or vb
                sn = info.get("sn_mva") or sb
                # ANDES currents and torques are on the system base; report them on the motor rating.
                i_rated_ka = sn / (math.sqrt(3.0) * vn)
                i_ka = np.hypot(id_vals[:, i], iq_vals[:, i]) * sb / (math.sqrt(3.0) * vb)
                i_pu = i_ka / i_rated_ka
                slip = np.asarray(slip_vals[:, i], dtype=float)
                v_term = np.asarray(v_all[:, bus_col[bus]], dtype=float) * vb / vn if bus in bus_col else None

                start_time_s = i_start_pu = i_start_ka = v_start = s_run = None
                stalled = False
                note = info.get("note")
                if len(after) and mp is not None and v_term is not None:
                    first = after[0]
                    i_start_pu, i_start_ka, v_start = i_pu[first], i_ka[first], v_term[first]
                    s_run = _running_slip(mp, float(v_term[-1]))
                    s_done = s_run + slip_thresh * (1.0 - s_run) if s_run is not None else slip_thresh
                    reached = after[slip[after] <= s_done]
                    if len(reached):
                        start_time_s = float(t_arr[reached[0]]) - t_start
                    if start_time_s is None or slip[-1] > s_done:
                        # Not running at the end. Still gaining speed over the last fifth of the run
                        # is a slow start (not started yet); otherwise the motor stalled.
                        t_check = t_arr[-1] - 0.2 * (t_arr[-1] - t_start)
                        before_end = after[t_arr[after] <= t_check]
                        accelerating = (start_time_s is None and len(before_end) > 0
                                        and slip[-1] < slip[before_end[-1]] - 0.005)
                        stalled = not accelerating
                        if start_time_s is not None:
                            why = (f"reached running speed {start_time_s:.2f} s after the start, then slowed "
                                   f"down to slip {slip[-1]:.2f} by the end of the simulation.")
                            start_time_s = None
                        elif accelerating:
                            why = (f"still accelerating at the end of the simulation (slip {slip[-1]:.2f}); "
                                   f"extend the end time.")
                        else:
                            why = (f"stalled at slip {slip[-1]:.2f} ({(1.0 - slip[-1]) * 100.0:.0f} % speed): "
                                   f"its torque cannot overcome the load at the voltage it gets.")
                        note = f"Not started: {why}" + (f" {note}" if note else "")
                        warnings.append(f"Motor '{info.get('name')}' {why}")

                motor_series[info["id"]] = {
                    "id": info["id"],
                    "name": info.get("name"),
                    "i_pu": [_clean(x) for x in i_pu.tolist()],
                    "slip": [_clean(x) for x in slip.tolist()],
                    "te": [_clean(x) for x in (np.asarray(te_vals[:, i], dtype=float) * sb / sn).tolist()]
                    if te_vals is not None else None,
                }
                motor_results.append({
                    "id": info["id"],
                    "name": info.get("name"),
                    "method": info.get("method", method),
                    "start_time_s": _clean(start_time_s),
                    "i_start_pu": _clean(i_start_pu),
                    "i_start_ka": _clean(i_start_ka),
                    "i_rated_ka": _clean(i_rated_ka),
                    "v_start_pu": _clean(v_start),
                    "lrc_pu": _clean(info.get("lrc_pu")),
                    "sn_mva": _clean(sn),
                    "vn_kv": _clean(vn),
                    "running_slip": _clean(s_run),
                    "slip_end": _clean(slip[-1]) if len(slip) else None,
                    "stalled": stalled,
                    "note": note,
                    "pass": start_time_s is not None and not stalled,
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
            "grid_sc_case": _grid_sc_case(params),
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
        # The motors are the dynamics here. Each External Grid is a source behind its
        # short-circuit impedance (S"k and R/X of the study's grid_sc_case), with or without a
        # generator in the network, as in steady-state mode.
        ss, meta = andes_electrisim.build_system(in_data, params, grid_behind_impedance=True,
                                                 dynamic_loads=True, grid_sc_case=_grid_sc_case(params))
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
        sn_rated = mparams["Sn"]
        sn_model = sn_rated
        if method == "soft_start":
            i_limit = _sf(params.get("i_limit_pu"), 3.0)
            if lrc > 0 and i_limit > 0:
                scale = min(1.0, i_limit / lrc)
                # A motor (inertia and load included) scaled to the limit draws the limit at standstill.
                sn_model = sn_rated * scale
                note = ("Soft start approximated by a motor (with its load) scaled to the current limit: "
                        "I start is the limit, but the run-up time is the DOL one and the current after "
                        "it is scaled down too.")
                applied_method = "soft_start"
                warnings.append(f"Motor '{mname}': {note}")
        elif method not in ("dol", "soft_start"):
            note = f"Method '{method}' uses DOL dynamics in ANDES; use steady-state mode for exact method factors."
            warnings.append(f"Motor '{mname}': {note}")

        # The load torque is on the motor rating; Motor3 takes c1..c3 on the system base.
        sb = float(meta.get("sn_mva") or 100.0)
        c1, c2, c3 = _andes_load_torque(ss, mparams, mparams["t_load"] * sn_model / sb, warnings)
        midx = f"Motor_{mid}"
        ss.add(
            "Motor3",
            idx=midx,
            name=mname,
            bus=bus_idx,
            u=0,
            Sn=sn_model,
            Vn=mparams["Vn"],
            # Motor3 defaults to 60 Hz; use the network frequency so 50 Hz systems are right.
            fn=float(meta.get("frequency") or 50.0),
            rs=mparams["rs"],
            xs=mparams["xs"],
            rr1=mparams["rr1"],
            xr1=mparams["xr1"],
            xm=mparams["xm"],
            Hm=mparams["Hm"],
            c1=c1,
            c2=c2,
            c3=c3,
        )
        toggle_i += 1
        # "model" is also System.add's first parameter, so Toggle's fields go in param_dict.
        ss.add("Toggle", {
            "idx": f"Toggle_Motor_{toggle_i}",
            "model": "Motor3",
            "dev": midx,
            "t": t_start,
        })
        motor_map[midx] = {
            "id": mid,
            "name": mname,
            "bus": bus_key,
            "method": applied_method,
            "note": note,
            "lrc_pu": lrc,
            "sn_mva": sn_rated,
            "sn_model_mva": sn_model,
            "vn_kv": mparams["Vn"],
            "model": mparams,
        }

    # ss is a SystemNoSetup, whose setup() is the no-op used above; run the real one now
    # that the motors and their start toggles are in.
    original_system.setup(ss)
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
