# -*- coding: utf-8 -*-
"""
ANDES transient stability (TDS) and eigenvalue (EIG) analysis for Electrisim.

Builds an ANDES System directly from Electrisim JSON (no pandapower→ANDES converter).
Applies default GENROU + EXDC2 + TGOV1 dynamics when generator fields are missing.
"""
from __future__ import annotations

import json
import math
import traceback
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import andes

    _HAS_ANDES = True
except ImportError:
    andes = None  # type: ignore
    _HAS_ANDES = False


# Textbook GENROU defaults (device base, Kundur-like)
_DEFAULT_GENROU = {
    "M": 12.0,  # 2H
    "D": 0.0,
    "ra": 0.0,
    "xl": 0.15,
    "xd": 1.8,
    "xq": 1.7,
    "xd1": 0.3,
    "xq1": 0.55,
    "xd2": 0.25,
    "xq2": 0.25,
    "Td10": 8.0,
    "Td20": 0.03,
    "Tq10": 0.4,
    "Tq20": 0.05,
}

_EXCITER_DEFAULTS: Dict[str, Dict[str, float]] = {
    "EXDC2": {
    "TR": 0.01,
    "TA": 0.2,
    "TC": 1.0,
    "TB": 10.0,
    "TE": 0.314,
    "TF1": 1.0,
    "KF1": 0.063,
    "KA": 20.0,
    "KE": 1.0,
    "VRMAX": 5.0,
    "VRMIN": -5.0,
    "E1": 3.1,
    "SE1": 0.33,
    "E2": 2.3,
    "SE2": 0.1,
    },
    "SEXS": {"TATB": 0.1, "TB": 10.0, "K": 100.0, "TE": 0.05, "EMIN": -4.0, "EMAX": 4.0},
    # The remaining parameters deliberately use ANDES model defaults. These common
    # parameters provide useful, conservative starting values when supplied by UI.
    "IEEEX1": {"TR": 0.01, "KA": 50.0, "TA": 0.05, "VRMAX": 5.0, "VRMIN": -5.0},
    "ESDC2A": {"TR": 0.01, "KA": 20.0, "TA": 0.2, "VRMAX": 5.0, "VRMIN": -5.0},
    "EXST1": {"TR": 0.01, "KA": 100.0, "TA": 0.05, "VRMAX": 5.0, "VRMIN": -5.0},
    "ESST1A": {"TR": 0.01, "KA": 100.0, "TA": 0.05, "VRMAX": 5.0, "VRMIN": -5.0},
    "AC8B": {"TR": 0.01, "KA": 40.0, "TA": 0.05, "VRMAX": 5.0, "VRMIN": -5.0},
}

_GOVERNOR_DEFAULTS: Dict[str, Dict[str, float]] = {
    "TGOV1": {
    "R": 0.05,
    "T1": 0.5,
    "T2": 1.0,
    "T3": 1.0,
    "VMAX": 1.2,
    "VMIN": 0.0,
    "Dt": 0.0,
    },
    "IEEEG1": {"R": 0.05, "T1": 0.5, "T2": 1.0, "T3": 1.0, "VMAX": 1.2, "VMIN": 0.0},
    "IEESGO": {"T1": 0.1, "T2": 0.1, "T3": 0.1, "T4": 0.1, "T5": 0.1, "T6": 0.1},
    "GAST": {"R": 0.05, "T1": 0.4, "T2": 0.1, "T3": 0.1, "VMAX": 1.2, "VMIN": 0.0},
    "HYGOV": {"R": 0.05, "T1": 0.5, "T2": 1.0, "T3": 1.0, "VMAX": 1.2, "VMIN": 0.0},
}

# MODE (input signal) is mandatory in ANDES. 1 = rotor speed, as in the ANDES Kundur IEEEST
# example; it needs no extra frequency-measurement bus. Override with dyn_pss_MODE.
_PSS_DEFAULTS = {"IEEEST": {"MODE": 1.0, "A1": 0.1, "A2": 0.1, "A3": 0.1, "A4": 0.1, "A5": 0.1, "A6": 0.1}}

_RENEWABLE_DEFAULTS: Dict[str, Dict[str, float]] = {
    "REGCA1": {"Tg": 0.02, "Lvplsw": 1.0, "Volim": 1.2, "Lvpnt0": 0.4, "Iolim": -1.5},
    # PFFLAG/VFLAG/QFLAG/PFLAG/PQFLAG have no ANDES default and are mandatory: without them
    # REECA1 is silently dropped. Defaults keep the power-flow reactive power (QFLAG 0, PFFLAG 0:
    # constant Q, or the REPCA1 plant-controller Q when present), no speed dependency (PFLAG 0)
    # and reactive-current priority (PQFLAG 0). Override per element with dyn_ree_<FLAG>.
    "REECA1": {"PFFLAG": 0.0, "VFLAG": 0.0, "QFLAG": 0.0, "PFLAG": 0.0, "PQFLAG": 0.0,
               "Vref0": 1.0, "dbd1": -0.02, "dbd2": 0.02},
    # VCFlag/RefFlag/Fflag are mandatory in ANDES (no default). Defaults: droop with PF control,
    # Q control, frequency control off. Kp is listed so the dialog's dyn_repca_Kp is honoured
    # (only keys listed here are read from the element); 1.0 is the ANDES default.
    "REPCA1": {"VCFlag": 0.0, "RefFlag": 0.0, "Fflag": 0.0, "Kp": 1.0, "dbd1": -0.02, "dbd2": 0.02},
    "WTDTA1": {"H": 3.0, "DAMP": 0.0, "Htfrac": 0.5, "Freq1": 1.0, "Dshaft": 1.0},
    "WTARA1": {},
    "WTPTA1": {},
    # Tflag is mandatory in ANDES (0 = speed-error, 1 = power-error torque control).
    "WTTQA1": {"Tflag": 0.0},
    # pqflag has no ANDES default and is mandatory: without it PVD1/ESD1 are never added.
    # 0 = reactive-current priority, as for REECA1 PQFLAG. Override with dyn_dg_pqflag.
    "PVD1": {"pqflag": 0.0},
    "ESD1": {"pqflag": 0.0},
}


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


def _dyn_value(el: Dict[str, Any], key: str, default: float) -> float:
    """Read a Dynamics attribute while preserving blank → model default behavior."""
    value = el.get(key)
    if value is None or str(value).strip().lower() in ("", "none", "null"):
        return default
    return _sf(value, default)


def tds_has_output(ss: Any) -> bool:
    """True when the last ``ss.TDS.run()`` recorded at least one time step."""
    try:
        return len(np.asarray(ss.dae.ts.t)) > 0
    except Exception:
        return False


def tds_values(ss: Any, var: Any) -> np.ndarray:
    """Recorded time series of an ANDES variable: shape (n_steps, n_devices).

    Read straight from ``ss.dae.ts``: states (v_code "x") live in ``ts.x`` and
    algebraic variables in ``ts.y``, both indexed by the variable address ``var.a``.
    The plotter route (``ss.TDS.plt.get_values(var.a)``) is wrong twice over: ANDES
    only creates the plotter in notebooks, and its columns start with time and put
    the algebraic block after all states, so a raw address selects another variable.
    """
    addrs = np.asarray(var.a, dtype=int)
    block = ss.dae.ts.x if getattr(var, "v_code", "y") == "x" else ss.dae.ts.y
    return np.asarray(block, dtype=float)[:, addrs]


def _repca_measured_line(ss: Any, el: Dict[str, Any]) -> Optional[str]:
    """ANDES idx of the Line named by ``dyn_repca_line``, or None if there is no such line.

    Accepts the line's displayed name (as typed in the dialog) or its diagram id.
    """
    wanted = str(el.get("dyn_repca_line") or "").strip()
    if not wanted or wanted.lower() in ("none", "null"):
        return None
    line_model = getattr(ss, "Line", None)
    if line_model is None or not line_model.n:
        return None
    idxs = [str(i) for i in line_model.idx.v]
    for candidate in (wanted, f"Line_{wanted}"):
        if candidate in idxs:
            return candidate
    by_name = [idx for idx, name in zip(idxs, line_model.name.v)
               if str(name).strip().lower() == wanted.lower()]
    return by_name[0] if len(by_name) == 1 else None


def _add_model_safe(ss: Any, model: str, defaults_applied: List[str], label: str, **kwargs: Any) -> Optional[str]:
    """
    Add an optional ANDES model without making a diagram unusable on another ANDES
    release. ANDES validates both model availability and parameter names in ss.add().
    """
    # ANDES checks mandatory parameters only after it has started appending the device, so a
    # failed add leaves a half-built device that later crashes System.setup(). Check first.
    mdl = getattr(ss, "models", {}).get(model)
    if mdl is not None:
        missing = [
            key for key, par in mdl.params.items()
            if (getattr(par, "property", None) or {}).get("mandatory") and kwargs.get(key) is None
        ]
        if missing:
            defaults_applied.append(
                f"{label}: could not add {model} (missing {', '.join(missing)}); "
                "continuing without that optional dynamic model."
            )
            return None
    try:
        ss.add(model, **kwargs)
        return str(kwargs["idx"])
    except Exception as exc:
        defaults_applied.append(
            f"{label}: could not add {model} ({exc}); continuing without that optional dynamic model."
        )
        return None


def _model_kwargs(
    el: Dict[str, Any],
    attr_prefix: str,
    defaults: Dict[str, float],
) -> Dict[str, float]:
    """Build only the documented key parameters; unset fields use per-model defaults."""
    return {
        key: _dyn_value(el, f"{attr_prefix}{key}", default)
        for key, default in defaults.items()
    }


def _clean_num(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (float, np.floating)):
        fv = float(v)
        if math.isnan(fv) or math.isinf(fv):
            return None
        return fv
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, complex):
        return {"re": _clean_num(v.real), "im": _clean_num(v.imag)}
    return v


def _downsample(arr: np.ndarray, max_points: int = 800) -> np.ndarray:
    n = len(arr)
    if n <= max_points:
        return arr
    idx = np.linspace(0, n - 1, max_points).astype(int)
    return arr[idx]


def _z_base_ohm(vn_kv: float, sn_mva: float) -> float:
    if vn_kv <= 0 or sn_mva <= 0:
        return 1.0
    return (vn_kv ** 2) / sn_mva


def _iter_elements(in_data: Dict[str, Any]):
    for key in sorted(in_data.keys(), key=lambda k: int(k) if str(k).isdigit() else str(k)):
        el = in_data[key]
        if not isinstance(el, dict):
            continue
        typ = el.get("typ") or ""
        if "Parameters" in typ:
            continue
        yield key, el, typ


def build_system(
    in_data: Dict[str, Any],
    params: Optional[Dict[str, Any]] = None,
) -> Tuple[Any, Dict[str, Any]]:
    """
    Build an ANDES System from Electrisim JSON.

    Returns (ss, meta) where meta includes bus_map, line_map, gen_map, defaults_applied, warnings.
    """
    if not _HAS_ANDES:
        raise RuntimeError("ANDES is not installed. Install with: pip install andes")

    params = params or {}
    freq = _sf(params.get("frequency"), 50.0)
    sn_base = _sf(params.get("sn_mva"), 100.0)
    if sn_base <= 0:
        sn_base = 100.0

    defaults_applied: List[str] = []
    warnings: List[str] = []
    bus_map: Dict[str, Any] = {}  # electrisim name -> andes bus idx
    bus_vn: Dict[Any, float] = {}
    bus_name_by_idx: Dict[Any, str] = {}
    line_map: Dict[str, Any] = {}
    gen_map: Dict[str, Dict[str, Any]] = {}  # electrisim gen name -> {static_idx, syn_idx, ...}
    friendly: Dict[str, str] = {}

    ss = andes.System()
    ss.config.freq = freq
    ss.config.mva = sn_base
    # Avoid writing report files into the server cwd
    try:
        ss.files.no_output = True
    except Exception:
        pass

    # --- Buses ---
    bus_counter = 1
    for _, el, typ in _iter_elements(in_data):
        if "DC Bus" in typ:
            warnings.append(f"Skipped DC Bus '{el.get('userFriendlyName', el.get('name'))}' (not supported in ANDES MVP).")
            continue
        if "Bus" not in typ:
            continue
        name = el.get("name")
        if not name:
            continue
        vn = _sf(el.get("vn_kv"), 0.0)
        if vn <= 0:
            vn = 110.0
            defaults_applied.append(f"Bus '{el.get('userFriendlyName', name)}': vn_kv missing, used 110 kV.")
        idx = bus_counter
        bus_counter += 1
        u = 1 if _sb(el.get("in_service"), True) else 0
        ss.add(
            "Bus",
            idx=idx,
            name=str(el.get("userFriendlyName") or name),
            Vn=vn,
            u=u,
            v0=1.0,
            a0=0.0,
        )
        bus_map[name] = idx
        ufn = el.get("userFriendlyName")
        if ufn and str(ufn) != str(name):
            bus_map[str(ufn)] = idx
        bus_vn[idx] = vn
        bus_name_by_idx[idx] = str(el.get("userFriendlyName") or name)
        friendly[name] = str(el.get("userFriendlyName") or name)

    if not bus_map:
        raise ValueError("No buses found in the diagram. Place Bus elements before running stability analysis.")

    # --- Lines ---
    for _, el, typ in _iter_elements(in_data):
        if not typ.startswith("Line") or typ.startswith("Load"):
            continue
        if "DC" in typ:
            warnings.append(f"Skipped DC Line '{el.get('userFriendlyName', el.get('name'))}' (AC lines only in MVP).")
            continue
        name = el.get("name")
        bus1 = bus_map.get(el.get("busFrom"))
        bus2 = bus_map.get(el.get("busTo"))
        if bus1 is None or bus2 is None:
            warnings.append(f"Skipped Line '{el.get('userFriendlyName', name)}': missing bus connection.")
            continue
        length = _sf(el.get("length_km"), 1.0)
        if length <= 0:
            length = 1.0
        vn1 = bus_vn.get(bus1, 110.0)
        vn2 = bus_vn.get(bus2, vn1)
        zb = _z_base_ohm(vn1, sn_base)
        r_ohm = _sf(el.get("r_ohm_per_km")) * length
        x_ohm = _sf(el.get("x_ohm_per_km")) * length
        c_nf = _sf(el.get("c_nf_per_km")) * length
        g_us = _sf(el.get("g_us_per_km")) * length
        r_pu = r_ohm / zb if zb else 0.0
        x_pu = x_ohm / zb if zb else 0.01
        # B (S) = 2*pi*f*C; C in F = c_nf * 1e-9; b_pu = B * Zb
        b_siemens = 2.0 * math.pi * freq * (c_nf * 1e-9)
        b_pu = b_siemens * zb if zb else 0.0
        g_pu = (g_us * 1e-6) * zb if zb else 0.0
        if x_pu == 0 and r_pu == 0:
            x_pu = 0.01
            defaults_applied.append(f"Line '{el.get('userFriendlyName', name)}': zero impedance, used x=0.01 pu.")
        line_idx = f"Line_{name}"
        u = 1 if _sb(el.get("in_service"), True) else 0
        ss.add(
            "Line",
            idx=line_idx,
            name=str(el.get("userFriendlyName") or name),
            bus1=bus1,
            bus2=bus2,
            r=r_pu,
            x=x_pu,
            b=b_pu,
            g=g_pu,
            Vn1=vn1,
            Vn2=vn2,
            Sn=sn_base,
            fn=freq,
            u=u,
        )
        line_map[name] = line_idx
        ufn = el.get("userFriendlyName")
        if ufn:
            line_map[str(ufn)] = line_idx

    # --- Two-winding transformers as ANDES Line with trans=1 ---
    for _, el, typ in _iter_elements(in_data):
        if not (
            (typ.startswith("Transformer") or typ.startswith("Two Winding Transformer"))
            and not typ.startswith("Three Winding Transformer")
        ):
            continue
        name = el.get("name")
        bus1 = bus_map.get(el.get("hv_bus"))
        bus2 = bus_map.get(el.get("lv_bus"))
        if bus1 is None or bus2 is None:
            warnings.append(f"Skipped Transformer '{el.get('userFriendlyName', name)}': missing HV/LV bus.")
            continue
        sn_t = _sf(el.get("sn_mva"), sn_base)
        if sn_t <= 0:
            sn_t = sn_base
        vk = _sf(el.get("vk_percent"), 6.0)
        vkr = _sf(el.get("vkr_percent"), 1.0)
        # Impedance on transformer base → system base
        z_t = vk / 100.0
        r_t = vkr / 100.0
        x_t = math.sqrt(max(z_t ** 2 - r_t ** 2, 0.0)) if z_t >= r_t else z_t
        scale = sn_base / sn_t
        r_pu = r_t * scale
        x_pu = x_t * scale if x_t > 0 else 0.06 * scale
        vn1 = _sf(el.get("vn_hv_kv"), bus_vn.get(bus1, 110.0))
        vn2 = _sf(el.get("vn_lv_kv"), bus_vn.get(bus2, 11.0))
        tap = 1.0
        # Approximate tap from tap_pos * tap_step_percent
        tap_pos = _sf(el.get("tap_pos"), 0.0)
        tap_step = _sf(el.get("tap_step_percent"), 0.0)
        if tap_step != 0:
            tap = 1.0 + (tap_pos * tap_step / 100.0)
        line_idx = f"Trafo_{name}"
        u = 1 if _sb(el.get("in_service"), True) else 0
        ss.add(
            "Line",
            idx=line_idx,
            name=str(el.get("userFriendlyName") or name),
            bus1=bus1,
            bus2=bus2,
            r=r_pu,
            x=x_pu,
            b=0.0,
            g=0.0,
            Vn1=vn1,
            Vn2=vn2,
            Sn=sn_base,
            fn=freq,
            trans=1,
            tap=tap,
            phi=0.0,
            u=u,
        )
        line_map[name] = line_idx

    for _, el, typ in _iter_elements(in_data):
        if typ.startswith("Three Winding Transformer"):
            warnings.append(
                f"Skipped Three Winding Transformer '{el.get('userFriendlyName', el.get('name'))}' "
                "(simplified mapping not included in MVP)."
            )

    # --- Loads (PQ) ---
    pq_i = 0
    for _, el, typ in _iter_elements(in_data):
        if not typ.startswith("Load") or typ.startswith("Load DC"):
            continue
        if "Asymmetric" in typ:
            warnings.append(f"Skipped Asymmetric Load '{el.get('userFriendlyName', el.get('name'))}'.")
            continue
        bus = bus_map.get(el.get("bus"))
        if bus is None:
            continue
        pq_i += 1
        scaling = _sf(el.get("scaling"), 1.0)
        p_mw = _sf(el.get("p_mw")) * scaling
        q_mvar = _sf(el.get("q_mvar")) * scaling
        u = 1 if _sb(el.get("in_service"), True) else 0
        ss.add(
            "PQ",
            idx=f"PQ_{pq_i}",
            name=str(el.get("userFriendlyName") or el.get("name") or f"PQ_{pq_i}"),
            bus=bus,
            p0=p_mw / sn_base,
            q0=q_mvar / sn_base,
            Vn=bus_vn.get(bus, 110.0),
            u=u,
        )

    # --- Shunts / capacitors ---
    sh_i = 0
    for _, el, typ in _iter_elements(in_data):
        is_shunt = typ.startswith("Shunt") or typ.startswith("Capacitor") or "Shunt Reactor" in typ
        if not is_shunt:
            continue
        bus = bus_map.get(el.get("bus"))
        if bus is None:
            continue
        sh_i += 1
        q_mvar = _sf(el.get("q_mvar"))
        # ANDES Shunt: g, b in pu (positive b = capacitive)
        b_pu = q_mvar / sn_base
        if "Reactor" in typ:
            b_pu = -abs(b_pu)
        u = 1 if _sb(el.get("in_service"), True) else 0
        ss.add(
            "Shunt",
            idx=f"Sh_{sh_i}",
            name=str(el.get("userFriendlyName") or el.get("name") or f"Sh_{sh_i}"),
            bus=bus,
            g=0.0,
            b=b_pu,
            Vn=bus_vn.get(bus, 110.0),
            u=u,
        )

    # --- External grids → Slack (no SynGen) ---
    slack_count = 0
    ext_grid_slacks: List[Tuple[str, Any, float, Dict[str, Any]]] = []  # (slack idx, bus, Vn, element)
    for _, el, typ in _iter_elements(in_data):
        if not (typ.startswith("External Grid") or typ.startswith("ExternalGrid")):
            continue
        bus = bus_map.get(el.get("bus"))
        if bus is None:
            continue
        if not _sb(el.get("in_service"), True):
            continue
        slack_count += 1
        idx = f"Slack_EG_{slack_count}"
        vm = _sf(el.get("vm_pu"), 1.0)
        if vm <= 0:
            vm = 1.0
        if vm > 1.5:
            vn = bus_vn.get(bus, 0)
            if vn > 0:
                vm = vm / vn
        va = _sf(el.get("va_degree"), 0.0)
        ss.add(
            "Slack",
            idx=idx,
            name=str(el.get("userFriendlyName") or el.get("name") or idx),
            bus=bus,
            Vn=bus_vn.get(bus, 110.0),
            Sn=sn_base,
            v0=vm,
            a0=va * math.pi / 180.0,
            p0=0.0,
        )
        ext_grid_slacks.append((idx, bus, bus_vn.get(bus, 110.0), el))

    # --- Generators → PV/Slack + SynGen + Exciter + Governor ---
    gen_count = 0
    for _, el, typ in _iter_elements(in_data):
        if not typ.startswith("Generator") or typ.startswith("Static Generator") or typ.startswith("Wind Turbine"):
            continue
        if "Asymmetric" in typ or "1ph" in typ:
            continue
        bus = bus_map.get(el.get("bus"))
        if bus is None:
            warnings.append(f"Skipped Generator '{el.get('userFriendlyName', el.get('name'))}': not connected.")
            continue
        if not _sb(el.get("in_service"), True):
            continue

        gen_count += 1
        name = el.get("name")
        ufname = str(el.get("userFriendlyName") or name or f"Gen_{gen_count}")
        p_mw = _sf(el.get("p_mw")) * _sf(el.get("scaling"), 1.0)
        vm = _sf(el.get("vm_pu"), 1.0)
        if vm <= 0:
            vm = 1.0
        if vm > 1.5:
            vn_bus = bus_vn.get(bus, 0)
            if vn_bus > 0:
                vm = vm / vn_bus
        sn_mva = _sf(el.get("sn_mva"), 0.0)
        if sn_mva <= 0:
            sn_mva = max(abs(p_mw) * 1.25, 100.0)
            defaults_applied.append(f"Generator '{ufname}': sn_mva missing/zero, used {sn_mva:.3g} MVA.")
        vn = _sf(el.get("vn_kv"), 0.0)
        bus_v = bus_vn.get(bus, 20.0)
        # Prefer bus nominal voltage when machine vn is missing or clearly mismatched
        # (common Electrisim diagrams leave vn_kv=0 or set generator terminal kV without a unit trafo).
        if vn <= 0:
            vn = bus_v
        elif bus_v > 0 and abs(vn - bus_v) / bus_v > 0.5:
            defaults_applied.append(
                f"Generator '{ufname}': vn_kv={vn} differs from bus {bus_v} kV; "
                f"using bus voltage for ANDES SynGen (add an explicit transformer for step-up)."
            )
            vn = bus_v

        is_slack = _sb(el.get("slack"), False)
        static_idx = f"{'Slack' if is_slack else 'PV'}_G_{gen_count}"
        static_model = "Slack" if is_slack else "PV"
        static_kw = dict(
            idx=static_idx,
            name=ufname,
            bus=bus,
            Vn=vn,
            Sn=sn_mva,
            p0=p_mw / sn_base,
            v0=vm,
            q0=0.0,
        )
        if is_slack:
            static_kw["a0"] = 0.0
            if slack_count == 0 and gen_count == 1:
                pass
        ss.add(static_model, **static_kw)
        if is_slack:
            slack_count += 1

        # Machine model
        machine = (el.get("dyn_machine_model") or el.get("machine_model") or "GENROU").strip().upper()
        if machine not in ("GENROU", "GENCLS"):
            machine = "GENROU"
            defaults_applied.append(f"Generator '{ufname}': unknown machine model, used GENROU.")

        syn_idx = f"{machine}_{gen_count}"
        used_defaults = False

        def _dyn(key: str, default: float, aliases: Tuple[str, ...] = ()) -> float:
            nonlocal used_defaults
            # Reactances, time constants and inertia must be positive. The Generator dialog
            # holds 0 in xdss_pu (an alias of xd2 / xd1) until it is filled in, and a zero
            # xd2 makes GENROU initialisation fail with NaN, so 0 is read as "not set".
            must_be_positive = key.startswith(("dyn_x", "dyn_T", "dyn_M"))
            for k in (key,) + aliases:
                if el.get(k) is not None and str(el.get(k)).strip() not in ("", "none", "null"):
                    value = _sf(el.get(k), default)
                    if must_be_positive and not value > 0:
                        continue
                    return value
            used_defaults = True
            return default

        if machine == "GENCLS":
            M = _dyn("dyn_M", _DEFAULT_GENROU["M"], ("M", "H"))
            # If user provided H instead of M and M missing, M=2H
            if el.get("dyn_H") is not None and el.get("dyn_M") in (None, "", "null"):
                M = 2.0 * _sf(el.get("dyn_H"), M / 2.0)
                used_defaults = False
            D = _dyn("dyn_D", 0.0, ("D",))
            ra = _dyn("dyn_ra", 0.0, ("ra",))
            xd1 = _dyn("dyn_xd1", 0.3, ("xd1", "xdss_pu"))
            ss.add(
                "GENCLS",
                idx=syn_idx,
                name=ufname,
                bus=bus,
                gen=static_idx,
                Sn=sn_mva,
                Vn=vn,
                fn=freq,
                M=M,
                D=D,
                ra=ra,
                xd1=xd1,
            )
        else:
            M = _dyn("dyn_M", _DEFAULT_GENROU["M"], ("M",))
            if el.get("dyn_H") is not None and el.get("dyn_M") in (None, "", "null"):
                M = 2.0 * _sf(el.get("dyn_H"), M / 2.0)
                used_defaults = False
            kw = dict(
                idx=syn_idx,
                name=ufname,
                bus=bus,
                gen=static_idx,
                Sn=sn_mva,
                Vn=vn,
                fn=freq,
                M=M,
                D=_dyn("dyn_D", _DEFAULT_GENROU["D"], ("D",)),
                ra=_dyn("dyn_ra", _DEFAULT_GENROU["ra"], ("ra",)),
                xl=_dyn("dyn_xl", _DEFAULT_GENROU["xl"], ("xl",)),
                xd=_dyn("dyn_xd", _DEFAULT_GENROU["xd"], ("xd",)),
                xq=_dyn("dyn_xq", _DEFAULT_GENROU["xq"], ("xq",)),
                xd1=_dyn("dyn_xd1", _DEFAULT_GENROU["xd1"], ("xd1",)),
                xq1=_dyn("dyn_xq1", _DEFAULT_GENROU["xq1"], ("xq1",)),
                xd2=_dyn("dyn_xd2", _DEFAULT_GENROU["xd2"], ("xd2", "xdss_pu")),
                xq2=_dyn("dyn_xq2", _DEFAULT_GENROU["xq2"], ("xq2",)),
                Td10=_dyn("dyn_Td10", _DEFAULT_GENROU["Td10"], ("Td10",)),
                Td20=_dyn("dyn_Td20", _DEFAULT_GENROU["Td20"], ("Td20",)),
                Tq10=_dyn("dyn_Tq10", _DEFAULT_GENROU["Tq10"], ("Tq10",)),
                Tq20=_dyn("dyn_Tq20", _DEFAULT_GENROU["Tq20"], ("Tq20",)),
            )
            ss.add("GENROU", **kw)

        if used_defaults:
            defaults_applied.append(f"Generator '{ufname}': applied default {machine} parameters.")

        # Exciter. The model-specific dictionaries intentionally expose only key
        # parameters; all other ANDES parameters retain their library defaults.
        exc_model = (el.get("dyn_exciter_model") or "EXDC2").strip().upper()
        if exc_model in ("", "NONE", "OFF"):
            defaults_applied.append(f"Generator '{ufname}': no exciter.")
            exc_idx = None
        else:
            if exc_model not in _EXCITER_DEFAULTS:
                exc_model = "EXDC2"
                defaults_applied.append(f"Generator '{ufname}': unknown exciter, used EXDC2.")
            exc_idx = f"{exc_model}_{gen_count}"
            exc_idx = _add_model_safe(
                ss, exc_model, defaults_applied, f"Generator '{ufname}'",
                idx=exc_idx, name=f"{exc_model}_{ufname}", syn=syn_idx,
                **_model_kwargs(el, "dyn_exc_", _EXCITER_DEFAULTS[exc_model]),
            )
            if all(el.get(k) in (None, "", "null") for k in ("dyn_exciter_model", "dyn_exc_KA", "dyn_exc_K")):
                defaults_applied.append(f"Generator '{ufname}': applied default {exc_model} exciter.")

        # Governor
        gov_model = (el.get("dyn_governor_model") or "TGOV1").strip().upper()
        if gov_model in ("", "NONE", "OFF"):
            gov_idx = None
            defaults_applied.append(f"Generator '{ufname}': no governor.")
        else:
            if gov_model not in _GOVERNOR_DEFAULTS:
                gov_model = "TGOV1"
                defaults_applied.append(f"Generator '{ufname}': unknown governor, used TGOV1.")
            gov_idx = _add_model_safe(
                ss, gov_model, defaults_applied, f"Generator '{ufname}'",
                idx=f"{gov_model}_{gen_count}", name=f"{gov_model}_{ufname}", syn=syn_idx,
                **_model_kwargs(el, "dyn_gov_", _GOVERNOR_DEFAULTS[gov_model]),
            )
            if all(el.get(k) in (None, "", "null") for k in ("dyn_governor_model", "dyn_gov_R")):
                defaults_applied.append(f"Generator '{ufname}': applied default {gov_model} governor.")

        pss_model = (el.get("dyn_pss_model") or "NONE").strip().upper()
        pss_idx = None
        if pss_model == "IEEEST" and not exc_idx:
            defaults_applied.append(
                f"Generator '{ufname}': IEEEST stabilizer needs an exciter to act on; PSS omitted."
            )
        elif pss_model == "IEEEST":
            # IEEEST attaches to the exciter (avr), not to the machine.
            pss_idx = _add_model_safe(
                ss, "IEEEST", defaults_applied, f"Generator '{ufname}'",
                idx=f"IEEEST_{gen_count}", name=f"IEEEST_{ufname}", avr=exc_idx,
                **_model_kwargs(el, "dyn_pss_", _PSS_DEFAULTS["IEEEST"]),
            )
        elif pss_model not in ("", "NONE", "OFF"):
            defaults_applied.append(f"Generator '{ufname}': unknown PSS '{pss_model}', omitted.")

        gen_map[name] = {
            "static_idx": static_idx,
            "syn_idx": syn_idx,
            "machine": machine,
            "exc_idx": exc_idx,
            "gov_idx": gov_idx,
            "pss_idx": pss_idx,
            "name": ufname,
            "bus": bus,
        }

    # Static generators can supply renewable / inverter dynamics. They remain
    # ANDES PV devices: unlike synchronous machines they deliberately have no SynGen.
    renewable_count = 0
    static_count = 0
    for _, el, typ in _iter_elements(in_data):
        if not (typ.startswith("Static Generator") or typ.startswith("Wind Turbine")):
            continue
        bus = bus_map.get(el.get("bus"))
        if bus is None or not _sb(el.get("in_service"), True):
            continue
        # Wind Turbine: derive p_mw from power curve when present
        if typ.startswith("Wind Turbine"):
            raw = el.get("wind_power_curve_json")
            if raw is not None and (not isinstance(raw, str) or str(raw).strip()):
                try:
                    points = json.loads(raw) if isinstance(raw, str) else raw
                    if isinstance(points, list) and len(points) >= 2:
                        v = float(el.get("wind_speed_ms"))
                        knots = sorted(
                            ((float(pt["v_ms"]), float(pt["p_mw"])) for pt in points if isinstance(pt, dict)),
                            key=lambda x: x[0],
                        )
                        if len(knots) >= 2:
                            if v <= knots[0][0]:
                                el["p_mw"] = knots[0][1]
                            elif v >= knots[-1][0]:
                                el["p_mw"] = knots[-1][1]
                            else:
                                for i in range(len(knots) - 1):
                                    v0, p0 = knots[i]
                                    v1, p1 = knots[i + 1]
                                    if v0 <= v <= v1:
                                        span = v1 - v0
                                        el["p_mw"] = p0 if abs(span) < 1e-12 else p0 + (v - v0) / span * (p1 - p0)
                                        break
                except (json.JSONDecodeError, TypeError, ValueError, KeyError):
                    pass
        plant_kind = (el.get("dyn_plant_kind") or "NONE").strip().upper()
        if plant_kind in ("", "NONE", "OFF"):
            warnings.append(
                f"Static Generator '{el.get('userFriendlyName', el.get('name'))}' "
                "has no ANDES dynamic plant model (omitted from dynamic models)."
            )
            continue
        if plant_kind not in ("IBR", "WIND", "PVD1", "ESD1"):
            defaults_applied.append(
                f"Static Generator '{el.get('userFriendlyName', el.get('name'))}': "
                f"unknown plant kind '{plant_kind}', omitted."
            )
            continue

        static_count += 1
        name = el.get("name") or f"SGen_{static_count}"
        ufname = str(el.get("userFriendlyName") or name)
        sn_mva = _sf(el.get("dyn_Sn", el.get("sn_mva")), 0.0)
        if sn_mva <= 0:
            sn_mva = max(abs(_sf(el.get("p_mw")) * _sf(el.get("scaling"), 1.0)) * 1.25, 100.0)
            defaults_applied.append(f"Static Generator '{ufname}': dyn_Sn/sn_mva missing, used {sn_mva:.3g} MVA.")
        static_idx = f"PV_SG_{static_count}"
        ss.add(
            "PV", idx=static_idx, name=ufname, bus=bus, Vn=bus_vn.get(bus, 110.0),
            Sn=sn_mva, p0=_sf(el.get("p_mw")) * _sf(el.get("scaling"), 1.0) / sn_base,
            q0=_sf(el.get("q_mvar")) * _sf(el.get("scaling"), 1.0) / sn_base, v0=1.0,
        )

        model_ids: Dict[str, Optional[str]] = {}
        if plant_kind in ("IBR", "WIND"):
            reg_idx = _add_model_safe(
                ss, "REGCA1", defaults_applied, f"Static Generator '{ufname}'",
                idx=f"REGCA1_{static_count}", name=f"REGCA1_{ufname}", bus=bus, gen=static_idx, Sn=sn_mva,
                **_model_kwargs(el, "dyn_reg_", _RENEWABLE_DEFAULTS["REGCA1"]),
            )
            model_ids["reg_idx"] = reg_idx
            if reg_idx:
                ree_idx = _add_model_safe(
                    ss, "REECA1", defaults_applied, f"Static Generator '{ufname}'",
                    idx=f"REECA1_{static_count}", name=f"REECA1_{ufname}", reg=reg_idx,
                    **_model_kwargs(el, "dyn_ree_", _RENEWABLE_DEFAULTS["REECA1"]),
                )
                model_ids["ree_idx"] = ree_idx
                if ree_idx:
                    # REPCA1 reads a measured line (ExtParam), so it can only exist when that line does.
                    repca_line = _repca_measured_line(ss, el)
                    if repca_line is None:
                        model_ids["repca_idx"] = None
                        asked = str(el.get("dyn_repca_line") or "").strip()
                        defaults_applied.append(
                            f"Static Generator '{ufname}': plant controller REPCA1 not modelled; "
                            + (f"measured line '{asked}' was not found among the diagram's lines."
                               if asked and asked.lower() not in ("none", "null") else
                               "set 'REPCA1 measured line' to the name of the Line from this plant to include it.")
                        )
                    else:
                        model_ids["repca_idx"] = _add_model_safe(
                            ss, "REPCA1", defaults_applied, f"Static Generator '{ufname}'",
                            idx=f"REPCA1_{static_count}", name=f"REPCA1_{ufname}", ree=ree_idx,
                            line=repca_line,
                            **_model_kwargs(el, "dyn_repca_", _RENEWABLE_DEFAULTS["REPCA1"]),
                        )
                    if plant_kind == "WIND":
                        wt_idx = _add_model_safe(
                            ss, "WTDTA1", defaults_applied, f"Static Generator '{ufname}'",
                            idx=f"WTDTA1_{static_count}", name=f"WTDTA1_{ufname}", ree=ree_idx,
                            **_model_kwargs(el, "dyn_wt_", _RENEWABLE_DEFAULTS["WTDTA1"]),
                        )
                        model_ids["wtdta_idx"] = wt_idx
                        if wt_idx:
                            rea_idx = _add_model_safe(
                                ss, "WTARA1", defaults_applied, f"Static Generator '{ufname}'",
                                idx=f"WTARA1_{static_count}", name=f"WTARA1_{ufname}", rego=wt_idx,
                                **_model_kwargs(el, "dyn_wta_", _RENEWABLE_DEFAULTS["WTARA1"]),
                            )
                            model_ids["wtara_idx"] = rea_idx
                            if rea_idx:
                                pitch_idx = _add_model_safe(
                                    ss, "WTPTA1", defaults_applied, f"Static Generator '{ufname}'",
                                    idx=f"WTPTA1_{static_count}", name=f"WTPTA1_{ufname}", rea=rea_idx,
                                    **_model_kwargs(el, "dyn_wtp_", _RENEWABLE_DEFAULTS["WTPTA1"]),
                                )
                                model_ids["wtpta_idx"] = pitch_idx
                                if pitch_idx:
                                    model_ids["wttqa_idx"] = _add_model_safe(
                                        ss, "WTTQA1", defaults_applied, f"Static Generator '{ufname}'",
                                        idx=f"WTTQA1_{static_count}", name=f"WTTQA1_{ufname}", rep=pitch_idx,
                                        **_model_kwargs(el, "dyn_wtt_", _RENEWABLE_DEFAULTS["WTTQA1"]),
                                    )
        else:
            dg_model = plant_kind
            dg_kwargs = _model_kwargs(el, "dyn_dg_", _RENEWABLE_DEFAULTS[dg_model])
            # The dialog's "DG Tg" is the converter current-lag time constant, which PVD1/ESD1
            # call tip (active) and tiq (reactive). Blank keeps the ANDES default of 0.02 s.
            dg_tg = _dyn_value(el, "dyn_dg_Tg", 0.0)
            if dg_tg > 0:
                dg_kwargs.setdefault("tip", dg_tg)
                dg_kwargs.setdefault("tiq", dg_tg)
            model_ids["dg_idx"] = _add_model_safe(
                ss, dg_model, defaults_applied, f"Static Generator '{ufname}'",
                idx=f"{dg_model}_{static_count}", name=f"{dg_model}_{ufname}", bus=bus, gen=static_idx, Sn=sn_mva,
                # PVD1/ESD1 default to 60 Hz; their frequency droop must use the network frequency.
                fn=freq,
                **dg_kwargs,
            )

        if any(model_ids.values()):
            renewable_count += 1
        gen_map[name] = {
            "static_idx": static_idx, "syn_idx": None, "plant_kind": plant_kind,
            "name": ufname, "bus": bus, **model_ids,
        }

    if renewable_count > 0 and ss.GENROU.n + ss.GENCLS.n == 0:
        # With no synchronous machine ANDES fails at the first switching event (fault, toggle)
        # with "list index out of range" in its island bookkeeping. Put a classical source
        # behind each External Grid: reactance from its short-circuit power, very large
        # inertia, so it behaves like the stiff grid the Slack represents in power flow.
        for slack_idx, eg_bus, eg_vn, eg_el in ext_grid_slacks:
            s_sc = _sf(eg_el.get("s_sc_max_mva"), 0.0)
            used_default_ssc = s_sc <= 0
            if used_default_ssc:
                s_sc = 10000.0
            xd1 = min(max(sn_base / s_sc, 1e-4), 1.0)  # on the source's own base Sn = sn_base
            ss.add(
                "GENCLS",
                idx=f"GENCLS_EG_{slack_idx}",
                name=f"{eg_el.get('userFriendlyName') or eg_el.get('name') or slack_idx} (grid source)",
                bus=eg_bus,
                gen=slack_idx,
                Sn=sn_base,
                Vn=eg_vn,
                fn=freq,
                M=2.0 * 1000.0,
                D=0.0,
                ra=0.0,
                xd1=xd1,
            )
            ufname = eg_el.get("userFriendlyName") or eg_el.get("name") or slack_idx
            defaults_applied.append(
                f"External Grid '{ufname}': modelled as a stiff source (H=1000 s, "
                f"S_sc={s_sc:.0f} MVA{' default' if used_default_ssc else ''}) because the network "
                "has no synchronous generator."
            )

    if gen_count + renewable_count == 0:
        raise ValueError(
            "Transient / eigenvalue analysis requires at least one synchronous Generator "
            "or renewable dynamic plant. External Grid alone is not sufficient."
        )

    if slack_count == 0:
        # Promote first PV to Slack for power flow
        # Find first PV and convert by adding a Slack with same setpoints is hard post-add;
        # instead require a slack — auto-fix first generator as Slack was already handled if slack flag set.
        # If still no slack, rebuild is too costly; raise clear error.
        raise ValueError(
            "No slack bus found. Mark one Generator as slack=true or add an External Grid."
        )

    # --- Disturbances (TDS) ---
    fault_bus_name = params.get("fault_bus") or params.get("fault_bus_name") or ""
    fault_enabled = _sb(params.get("fault_enabled"), True) if params.get("fault_enabled") is not None else bool(fault_bus_name)
    if fault_enabled and fault_bus_name:
        fbus = bus_map.get(fault_bus_name)
        if fbus is None:
            # try friendly name match
            for bname, bidx in bus_map.items():
                if str(friendly.get(bname, bname)) == str(fault_bus_name) or str(bname) == str(fault_bus_name):
                    fbus = bidx
                    break
        if fbus is not None:
            ss.add(
                "Fault",
                idx="Fault_1",
                bus=fbus,
                tf=_sf(params.get("fault_tf"), 1.0),
                tc=_sf(params.get("fault_tc"), 1.1),
                xf=_sf(params.get("fault_xf"), 0.0001),
                rf=_sf(params.get("fault_rf"), 0.0),
            )
        else:
            warnings.append(f"Fault bus '{fault_bus_name}' not found; no Fault applied.")

    toggle_line = params.get("toggle_line") or params.get("line_outage") or ""
    toggle_t = _sf(params.get("toggle_t"), 2.0)
    if toggle_line:
        lidx = line_map.get(toggle_line)
        if lidx is None:
            for lname, lid in line_map.items():
                if str(lname) == str(toggle_line):
                    lidx = lid
                    break
        if lidx is not None:
            # Toggle has a parameter named "model", which clashes with System.add(model, ...)
            # as a keyword, so its parameters go in param_dict.
            ss.add("Toggle", {"idx": "Toggle_1", "model": "Line", "dev": lidx, "t": toggle_t})
        else:
            warnings.append(f"Line outage target '{toggle_line}' not found; no Toggle applied.")

    toggle_gen = params.get("toggle_gen") or params.get("generator_trip") or ""
    toggle_gen_t = _sf(params.get("toggle_gen_t"), toggle_t)
    if toggle_gen:
        syn_dev = None
        gm = gen_map.get(toggle_gen)
        if gm and gm.get("syn_idx"):
            syn_dev = gm["syn_idx"]
        else:
            for gname, ginfo in gen_map.items():
                if str(gname) == str(toggle_gen) or str(ginfo.get("name")) == str(toggle_gen):
                    syn_dev = ginfo.get("syn_idx")
                    break
        if syn_dev:
            ss.add("Toggle", {"idx": "Toggle_Gen_1", "model": "SynGen", "dev": syn_dev, "t": toggle_gen_t})
        else:
            warnings.append(f"Generator trip target '{toggle_gen}' not found; no Toggle applied.")

    ss.setup()

    meta = {
        "bus_map": bus_map,
        "bus_name_by_idx": {str(k): v for k, v in bus_name_by_idx.items()},
        "line_map": line_map,
        "gen_map": gen_map,
        "defaults_applied": defaults_applied,
        "warnings": warnings,
        "frequency": freq,
        "sn_mva": sn_base,
        "n_generators": gen_count,
        "n_renewable_plants": renewable_count,
        "n_buses": len(bus_name_by_idx),
    }
    return ss, meta


def _extract_syn_series(ss, model_name: str, var_name: str, names: List[str]) -> List[Dict[str, Any]]:
    if not hasattr(ss, model_name):
        return []
    model = getattr(ss, model_name)
    if model.n == 0 or not hasattr(model, var_name):
        return []
    var = getattr(model, var_name)
    addrs = list(var.a)
    if not addrs:
        return []
    try:
        values = tds_values(ss, var)
    except Exception:
        return []
    series = []
    for i, addr in enumerate(addrs):
        col = values[:, i] if values.ndim == 2 else values
        label = names[i] if i < len(names) else f"{model_name}_{i}"
        try:
            label = str(model.name.v[i]) if hasattr(model, "name") else label
        except Exception:
            pass
        series.append({"id": str(model.idx.v[i]), "name": label, "values": [_clean_num(x) for x in col.tolist()]})
    return series


def _syn_names(ss) -> Tuple[List[str], List[str]]:
    """Return (model_list for each machine instance flattened is hard) — names per GENROU then GENCLS."""
    names = []
    models = []
    for mname in ("GENROU", "GENCLS"):
        if hasattr(ss, mname) and getattr(ss, mname).n > 0:
            m = getattr(ss, mname)
            for i in range(m.n):
                try:
                    names.append(str(m.name.v[i]))
                except Exception:
                    names.append(f"{mname}_{i}")
                models.append(mname)
    return names, models


def run_tds(in_data: Dict[str, Any], params: Dict[str, Any]) -> str:
    """Run power flow + time-domain simulation; return JSON string."""
    try:
        if not _HAS_ANDES:
            return json.dumps({
                "error": True,
                "message": "ANDES is not installed on the backend.",
                "exception": "pip install andes",
            })

        andes.config_logger(stream_level=40)
        ss, meta = build_system(in_data, params)

        # Suppress file outputs
        try:
            ss.TDS.config.noprint = True
        except Exception:
            pass

        pf_ok = bool(ss.PFlow.run())
        if not pf_ok:
            return json.dumps({
                "error": True,
                "message": "Power flow did not converge. Check network data and generator setpoints.",
                "defaults_applied": meta["defaults_applied"],
                "warnings": meta["warnings"],
            })

        tf = _sf(params.get("tf"), 10.0)
        tstep = _sf(params.get("tstep"), 0.0)
        ss.TDS.config.tf = tf
        if tstep > 0:
            try:
                ss.TDS.config.tstep = tstep
            except Exception:
                pass

        try:
            tds_ok = bool(ss.TDS.run())
        except IndexError:
            # ANDES re-checks connectivity at each switching event and fails with a bare
            # IndexError when a Toggle leaves part of the network without a slack bus.
            if params.get("toggle_line") or params.get("line_outage") or params.get("toggle_gen")                     or params.get("generator_trip"):
                return json.dumps({
                    "error": True,
                    "message": "The line outage or generator trip splits the network into an island "
                               "that ANDES cannot simulate (no slack/reference in that part). "
                               "Choose an element whose outage keeps the network connected.",
                    "exception": traceback.format_exc(),
                    "defaults_applied": meta["defaults_applied"],
                    "warnings": meta["warnings"],
                })
            raise
        # A run that stopped early (e.g. the system went unstable) still has the series up to
        # that point; they are returned with converged=False so the user can see what happened.
        if not tds_has_output(ss):
            return json.dumps({
                "error": True,
                "message": "Transient simulation produced no output (ANDES did not complete the run). "
                           "Check the fault timing, the disturbance settings and the network data.",
                "converged": False,
                "power_flow_converged": pf_ok,
                "defaults_applied": meta["defaults_applied"],
                "warnings": meta["warnings"],
            })
        t = np.asarray(ss.dae.ts.t, dtype=float)
        max_pts = int(_sf(params.get("max_points"), 800))
        t_ds = _downsample(t, max_pts)
        # indices for downsample of series
        if len(t) > max_pts:
            idx = np.linspace(0, len(t) - 1, max_pts).astype(int)
        else:
            idx = np.arange(len(t))

        def _series_for(model_name: str, var_name: str) -> List[Dict[str, Any]]:
            if not hasattr(ss, model_name):
                return []
            model = getattr(ss, model_name)
            if model.n == 0 or not hasattr(model, var_name):
                return []
            var = getattr(model, var_name)
            addrs = list(var.a)
            if not addrs:
                return []
            values = tds_values(ss, var)
            out = []
            for i in range(len(addrs)):
                col = values[:, i] if values.ndim == 2 else values
                col = col[idx]
                try:
                    label = str(model.name.v[i])
                    mid = str(model.idx.v[i])
                except Exception:
                    label = f"{model_name}_{i}"
                    mid = label
                out.append({
                    "id": mid,
                    "name": label,
                    "model": model_name,
                    "values": [_clean_num(float(x)) for x in col.tolist()],
                })
            return out

        omega = _series_for("GENROU", "omega") + _series_for("GENCLS", "omega")
        delta = _series_for("GENROU", "delta") + _series_for("GENCLS", "delta")

        # Bus voltages
        bus_v = []
        if ss.Bus.n > 0 and hasattr(ss.Bus, "v"):
            addrs = list(ss.Bus.v.a)
            values = tds_values(ss, ss.Bus.v)
            for i in range(len(addrs)):
                col = values[:, i] if values.ndim == 2 else values
                col = col[idx]
                bidx = ss.Bus.idx.v[i]
                bus_v.append({
                    "id": str(bidx),
                    "name": meta["bus_name_by_idx"].get(str(bidx), str(ss.Bus.name.v[i])),
                    "values": [_clean_num(float(x)) for x in col.tolist()],
                })

        # Frequency estimate from mean omega (pu → Hz)
        freq_hz = None
        if omega:
            mean_w = np.mean([np.asarray(s["values"], dtype=float) for s in omega], axis=0)
            freq_hz = (mean_w * meta["frequency"]).tolist()

        poi_bus_key = params.get("poi_bus") or params.get("poi_bus_name") or ""
        poi_v_min = None
        poi_v_series = None
        if poi_bus_key and bus_v:
            for s in bus_v:
                if s.get("id") == poi_bus_key or s.get("name") == poi_bus_key:
                    poi_v_series = s.get("values") or []
                    if poi_v_series:
                        poi_v_min = min(poi_v_series)
                    break

        freq_nadir = None
        freq_settling = None
        if freq_hz:
            arr = np.asarray(freq_hz, dtype=float)
            freq_nadir = float(np.min(arr))
            if len(arr) > 10:
                freq_settling = float(arr[-1])

        ride_csv = params.get("ride_through_csv") or ""
        if not ride_csv:
            for _, el, typ in _iter_elements(in_data):
                if not typ.startswith("Load") or typ.startswith("Load DC"):
                    continue
                if str(el.get("dc_computational_enabled", "")).lower() in ("true", "1", "yes"):
                    ride_csv = el.get("dc_ride_through_csv") or "0,0.9\n10,0.9"
                    break
        ride_pts = []
        for line in str(ride_csv).strip().splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.replace(";", ",").split(",")
            if len(parts) >= 2:
                ride_pts.append((_sf(parts[0]), _sf(parts[1])))
        ride_pts.sort(key=lambda p: p[0])

        def _vmin_curve(t_val: float) -> float:
            if not ride_pts:
                return 0.0
            if t_val <= ride_pts[0][0]:
                return ride_pts[0][1]
            for i in range(len(ride_pts) - 1):
                t0, v0 = ride_pts[i]
                t1, v1 = ride_pts[i + 1]
                if t0 <= t_val <= t1:
                    if t1 <= t0:
                        return v0
                    return v0 + (v1 - v0) * (t_val - t0) / (t1 - t0)
            return ride_pts[-1][1]

        ride_pass = None
        ride_fail_t = None
        ride_fail_v = None
        if poi_v_series and ride_pts and t_ds is not None:
            ride_pass = True
            for ti, vi in zip(t_ds.tolist(), poi_v_series):
                vmin = _vmin_curve(float(ti))
                if float(vi) < vmin - 1e-5:
                    ride_pass = False
                    ride_fail_t = float(ti)
                    ride_fail_v = float(vi)
                    break

        result = {
            "error": False,
            "routine": "tds",
            "converged": tds_ok,
            "power_flow_converged": pf_ok,
            "time": [_clean_num(float(x)) for x in t_ds.tolist()],
            "omega": omega,
            "delta": delta,
            "bus_voltage": bus_v,
            "frequency_hz": [_clean_num(float(x)) for x in freq_hz] if freq_hz is not None else None,
            "tf": tf,
            "n_points": int(len(t_ds)),
            "defaults_applied": meta["defaults_applied"],
            "warnings": meta["warnings"],
            "n_generators": meta["n_generators"],
            "n_buses": meta["n_buses"],
            "frequency_base_hz": meta["frequency"],
            "sn_mva": meta["sn_mva"],
            "events": {
                "fault_bus": params.get("fault_bus") or params.get("fault_bus_name"),
                "fault_tf": params.get("fault_tf"),
                "fault_tc": params.get("fault_tc"),
                "toggle_line": params.get("toggle_line") or params.get("line_outage"),
                "toggle_t": params.get("toggle_t"),
                "toggle_gen": params.get("toggle_gen") or params.get("generator_trip"),
                "toggle_gen_t": params.get("toggle_gen_t"),
            },
            "poi_metrics": {
                "poi_bus": poi_bus_key or None,
                "v_min_pu": _clean_num(poi_v_min) if poi_v_min is not None else None,
                "frequency_nadir_hz": _clean_num(freq_nadir) if freq_nadir is not None else None,
                "frequency_final_hz": _clean_num(freq_settling) if freq_settling is not None else None,
            },
            "ride_through": {
                "enabled": bool(ride_pts),
                "pass": ride_pass,
                "fail_time_s": _clean_num(ride_fail_t) if ride_fail_t is not None else None,
                "fail_voltage_pu": _clean_num(ride_fail_v) if ride_fail_v is not None else None,
                "curve_points": [{"t_s": a, "v_min_pu": b} for a, b in ride_pts],
            },
        }
        return json.dumps(result)
    except Exception as e:
        return json.dumps({
            "error": True,
            "message": str(e),
            "exception": traceback.format_exc(),
        })


def _eig_clamped_pitch_state_names(ss, x_names):
    """Indices of WTPTA1 states whose turbine sits at minimum pitch (pitch loop inactive)."""
    try:
        mod = getattr(ss, "WTPTA1", None)
        if mod is None or not mod.n:
            return set()
        theta = np.asarray(mod.theta.v, dtype=float)
        thmin = np.asarray(mod.thmin.v, dtype=float)
        if np.nanmax(np.abs(thmin)) > 2 * math.pi:  # stored in degrees
            thmin = np.radians(thmin)
        at_min = theta <= thmin + 1e-6
        if not at_min.any():
            return set()
        idx = []
        for j, name in enumerate(x_names):
            parts = str(name).split()
            if len(parts) >= 3 and parts[-2] == "WTPTA1":
                try:
                    k = int(parts[-1]) - 1
                except ValueError:
                    k = -1
                if (0 <= k < len(at_min) and at_min[k]) or (k < 0 and at_min.all()):
                    idx.append(j)
        return set(idx)
    except Exception:
        return set()


def run_eig(in_data: Dict[str, Any], params: Dict[str, Any]) -> str:
    """Run power flow + eigenvalue analysis; return JSON string."""
    try:
        if not _HAS_ANDES:
            return json.dumps({
                "error": True,
                "message": "ANDES is not installed on the backend.",
                "exception": "pip install andes",
            })

        andes.config_logger(stream_level=40)
        # Fresh system without TDS disturbances for clean linearization
        eig_params = dict(params or {})
        eig_params["fault_enabled"] = False
        eig_params["fault_bus"] = ""
        eig_params["fault_bus_name"] = ""
        eig_params["toggle_line"] = ""
        eig_params["line_outage"] = ""

        ss, meta = build_system(in_data, eig_params)
        pf_ok = bool(ss.PFlow.run())
        if not pf_ok:
            return json.dumps({
                "error": True,
                "message": "Power flow did not converge. Check network data and generator setpoints.",
                "defaults_applied": meta["defaults_applied"],
                "warnings": meta["warnings"],
            })

        eig_ok = bool(ss.EIG.run())
        mu = np.asarray(ss.EIG.mu, dtype=complex)

        eigenvalues = []
        for i, lam in enumerate(mu):
            re = float(lam.real)
            im = float(lam.imag)
            f_hz = abs(im) / (2.0 * math.pi) if im != 0 else 0.0
            damp = None
            if abs(lam) > 1e-12:
                damp = -re / abs(lam)
            eigenvalues.append({
                "index": i,
                "real": _clean_num(re),
                "imag": _clean_num(im),
                "freq_hz": _clean_num(f_hz),
                "damping_ratio": _clean_num(damp),
            })

        # Sort oscillatory modes by least damping (ascending damping ratio among im!=0)
        osc = [e for e in eigenvalues if abs(e["imag"] or 0) > 1e-6]
        osc_sorted = sorted(
            osc,
            key=lambda e: (e["damping_ratio"] if e["damping_ratio"] is not None else -1e9),
        )
        n_highlight = int(_sf(params.get("n_modes"), 10))
        least_damped = osc_sorted[: max(n_highlight, 0)]

        n_pos = int(getattr(ss.EIG, "n_positive", sum(1 for e in eigenvalues if (e["real"] or 0) > 1e-6)))
        n_zero = int(getattr(ss.EIG, "n_zeros", sum(1 for e in eigenvalues if abs(e["real"] or 0) <= 1e-6 and abs(e["imag"] or 0) <= 1e-6)))
        n_neg = int(getattr(ss.EIG, "n_negative", len(eigenvalues) - n_pos - n_zero))

        x_names = getattr(ss.EIG, "x_name", None)
        x_names = [str(n) for n in x_names] if x_names is not None else []
        try:
            pf_abs = np.abs(np.asarray(ss.EIG.pfactors))
        except Exception:
            pf_abs = None

        # Positive modes carried by wind-turbine pitch control that sits at its minimum pitch
        # (below rated wind): the anti-windup limiter keeps that loop inactive, but the
        # linearisation ignores limiters, so these modes do not describe the real system.
        notes = []
        n_pos_at_limit = 0
        clamped = _eig_clamped_pitch_state_names(ss, x_names)
        if n_pos > 0 and clamped and pf_abs is not None and pf_abs.ndim == 2:
            positive = [i for i, lam in enumerate(mu) if lam.real > 1e-6 and i < pf_abs.shape[1]]
            pitch_modes = []
            for i in positive:
                col = pf_abs[:, i]
                total = float(col.sum())
                share = float(sum(col[j] for j in clamped if j < len(col))) / total if total > 0 else 0.0
                if share >= 0.6:
                    pitch_modes.append(mu[i])
            # Identical turbines give repeated eigenvalues whose participation is split arbitrarily
            # between the copies, so an eigenvalue equal to a pitch mode is that same mode.
            n_pos_at_limit = sum(
                1 for i in positive
                if any(abs(mu[i] - m) <= 1e-3 * max(abs(m), 1e-6) for m in pitch_modes))
            n_pos_at_limit = min(n_pos_at_limit, n_pos)
            if n_pos_at_limit:
                notes.append(
                    f"{n_pos_at_limit} positive eigenvalue(s) belong to wind-turbine pitch control held at its "
                    "minimum pitch angle (below rated wind). The pitch limiter keeps that loop inactive, so they "
                    "are not counted as unstable modes. Confirm with a Transient Stability run if in doubt.")
                n_pos -= n_pos_at_limit

        if n_pos > 0:
            verdict = "unstable"
        elif any((e["damping_ratio"] is not None and e["damping_ratio"] < 0.03 and abs(e["imag"] or 0) > 1e-6) for e in eigenvalues):
            verdict = "marginally_stable"
        else:
            verdict = "stable"

        # Participation factors for least-damped modes (optional)
        participation = []
        try:
            pf = pf_abs if pf_abs is not None else np.abs(np.asarray(ss.EIG.pfactors))
            for mode in least_damped[:5]:
                mi = mode["index"]
                if pf.ndim == 2 and mi < pf.shape[1]:
                    col = np.abs(pf[:, mi])
                    order = np.argsort(col)[::-1][:5]
                    participation.append({
                        "mode_index": mi,
                        "states": [
                            {
                                "state": x_names[j] if j < len(x_names) else str(j),
                                "factor": _clean_num(float(col[j])),
                            }
                            for j in order
                        ],
                    })
        except Exception:
            participation = []

        result = {
            "error": False,
            "routine": "eig",
            "converged": eig_ok,
            "power_flow_converged": pf_ok,
            "verdict": verdict,
            "n_positive": n_pos,
            "n_positive_at_limit": n_pos_at_limit,
            "notes": notes,
            "n_zeros": n_zero,
            "n_negative": n_neg,
            "eigenvalues": eigenvalues,
            "least_damped_modes": least_damped,
            "participation": participation,
            "defaults_applied": meta["defaults_applied"],
            "warnings": meta["warnings"],
            "n_generators": meta["n_generators"],
            "n_buses": meta["n_buses"],
            "frequency_base_hz": meta["frequency"],
            "sn_mva": meta["sn_mva"],
        }
        return json.dumps(result)
    except Exception as e:
        return json.dumps({
            "error": True,
            "message": str(e),
            "exception": traceback.format_exc(),
        })
