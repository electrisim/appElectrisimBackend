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

_DEFAULT_EXDC2 = {
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
}

_DEFAULT_TGOV1 = {
    "R": 0.05,
    "T1": 0.5,
    "T2": 1.0,
    "T3": 1.0,
    "VMAX": 1.2,
    "VMIN": 0.0,
    "Dt": 0.0,
}

_DEFAULT_SEXS = {
    "TATB": 0.1,
    "TB": 10.0,
    "K": 100.0,
    "TE": 0.05,
    "EMIN": -4.0,
    "EMAX": 4.0,
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

    # --- Generators → PV/Slack + SynGen + Exciter + Governor ---
    gen_count = 0
    for _, el, typ in _iter_elements(in_data):
        if not typ.startswith("Generator") or typ.startswith("Static Generator"):
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
            for k in (key,) + aliases:
                if el.get(k) is not None and str(el.get(k)).strip() not in ("", "none", "null"):
                    return _sf(el.get(k), default)
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

        # Exciter
        exc_model = (el.get("dyn_exciter_model") or "EXDC2").strip().upper()
        if exc_model in ("", "NONE", "OFF"):
            defaults_applied.append(f"Generator '{ufname}': no exciter.")
            exc_idx = None
        else:
            if exc_model not in ("EXDC2", "SEXS"):
                exc_model = "EXDC2"
                defaults_applied.append(f"Generator '{ufname}': unknown exciter, used EXDC2.")
            exc_idx = f"{exc_model}_{gen_count}"
            if exc_model == "SEXS":
                ss.add(
                    "SEXS",
                    idx=exc_idx,
                    name=f"SEXS_{ufname}",
                    syn=syn_idx,
                    TATB=_dyn("dyn_exc_TATB", _DEFAULT_SEXS["TATB"]),
                    TB=_dyn("dyn_exc_TB", _DEFAULT_SEXS["TB"]),
                    K=_dyn("dyn_exc_K", _DEFAULT_SEXS["K"]),
                    TE=_dyn("dyn_exc_TE", _DEFAULT_SEXS["TE"]),
                    EMIN=_dyn("dyn_exc_EMIN", _DEFAULT_SEXS["EMIN"]),
                    EMAX=_dyn("dyn_exc_EMAX", _DEFAULT_SEXS["EMAX"]),
                )
            else:
                ss.add(
                    "EXDC2",
                    idx=exc_idx,
                    name=f"EXDC2_{ufname}",
                    syn=syn_idx,
                    TR=_dyn("dyn_exc_TR", _DEFAULT_EXDC2["TR"]),
                    TA=_dyn("dyn_exc_TA", _DEFAULT_EXDC2["TA"]),
                    TC=_dyn("dyn_exc_TC", _DEFAULT_EXDC2["TC"]),
                    TB=_dyn("dyn_exc_TB", _DEFAULT_EXDC2["TB"]),
                    TE=_dyn("dyn_exc_TE", _DEFAULT_EXDC2["TE"]),
                    TF1=_dyn("dyn_exc_TF1", _DEFAULT_EXDC2["TF1"]),
                    KF1=_dyn("dyn_exc_KF1", _DEFAULT_EXDC2["KF1"]),
                    KA=_dyn("dyn_exc_KA", _DEFAULT_EXDC2["KA"]),
                    KE=_dyn("dyn_exc_KE", _DEFAULT_EXDC2["KE"]),
                    VRMAX=_dyn("dyn_exc_VRMAX", _DEFAULT_EXDC2["VRMAX"]),
                    VRMIN=_dyn("dyn_exc_VRMIN", _DEFAULT_EXDC2["VRMIN"]),
                    E1=_dyn("dyn_exc_E1", _DEFAULT_EXDC2["E1"]),
                    SE1=_dyn("dyn_exc_SE1", _DEFAULT_EXDC2["SE1"]),
                    E2=_dyn("dyn_exc_E2", _DEFAULT_EXDC2["E2"]),
                    SE2=_dyn("dyn_exc_SE2", _DEFAULT_EXDC2["SE2"]),
                )
            if all(el.get(k) in (None, "", "null") for k in ("dyn_exciter_model", "dyn_exc_KA", "dyn_exc_K")):
                defaults_applied.append(f"Generator '{ufname}': applied default {exc_model} exciter.")

        # Governor
        gov_model = (el.get("dyn_governor_model") or "TGOV1").strip().upper()
        if gov_model in ("", "NONE", "OFF"):
            gov_idx = None
            defaults_applied.append(f"Generator '{ufname}': no governor.")
        else:
            if gov_model != "TGOV1":
                gov_model = "TGOV1"
                defaults_applied.append(f"Generator '{ufname}': unknown governor, used TGOV1.")
            gov_idx = f"TGOV1_{gen_count}"
            ss.add(
                "TGOV1",
                idx=gov_idx,
                name=f"TGOV1_{ufname}",
                syn=syn_idx,
                R=_dyn("dyn_gov_R", _DEFAULT_TGOV1["R"]),
                T1=_dyn("dyn_gov_T1", _DEFAULT_TGOV1["T1"]),
                T2=_dyn("dyn_gov_T2", _DEFAULT_TGOV1["T2"]),
                T3=_dyn("dyn_gov_T3", _DEFAULT_TGOV1["T3"]),
                VMAX=_dyn("dyn_gov_VMAX", _DEFAULT_TGOV1["VMAX"]),
                VMIN=_dyn("dyn_gov_VMIN", _DEFAULT_TGOV1["VMIN"]),
                Dt=_dyn("dyn_gov_Dt", _DEFAULT_TGOV1["Dt"]),
            )
            if all(el.get(k) in (None, "", "null") for k in ("dyn_governor_model", "dyn_gov_R")):
                defaults_applied.append(f"Generator '{ufname}': applied default TGOV1 governor.")

        gen_map[name] = {
            "static_idx": static_idx,
            "syn_idx": syn_idx,
            "machine": machine,
            "exc_idx": exc_idx,
            "gov_idx": gov_idx,
            "name": ufname,
            "bus": bus,
        }

    # Static generators — skip SynGen in MVP
    for _, el, typ in _iter_elements(in_data):
        if typ.startswith("Static Generator"):
            warnings.append(
                f"Static Generator '{el.get('userFriendlyName', el.get('name'))}' "
                "has no SynGen dynamics in MVP (treated as omitted from dynamic models)."
            )

    if gen_count == 0:
        raise ValueError(
            "Transient / eigenvalue analysis requires at least one synchronous Generator "
            "with dynamic models. External Grid alone is not sufficient."
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
            ss.add("Toggle", idx="Toggle_1", model="Line", dev=lidx, t=toggle_t)
        else:
            warnings.append(f"Line outage target '{toggle_line}' not found; no Toggle applied.")

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
        values = np.asarray(ss.TDS.plt.get_values(addrs), dtype=float)
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

        tds_ok = bool(ss.TDS.run())
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
            addrs = list(getattr(model, var_name).a)
            if not addrs:
                return []
            values = np.asarray(ss.TDS.plt.get_values(addrs), dtype=float)
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
            values = np.asarray(ss.TDS.plt.get_values(addrs), dtype=float)
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
            },
        }
        return json.dumps(result)
    except Exception as e:
        return json.dumps({
            "error": True,
            "message": str(e),
            "exception": traceback.format_exc(),
        })


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

        if n_pos > 0:
            verdict = "unstable"
        elif any((e["damping_ratio"] is not None and e["damping_ratio"] < 0.03 and abs(e["imag"] or 0) > 1e-6) for e in eigenvalues):
            verdict = "marginally_stable"
        else:
            verdict = "stable"

        # Participation factors for least-damped modes (optional)
        participation = []
        try:
            pf = np.asarray(ss.EIG.pfactors)
            x_names = list(getattr(ss.EIG, "x_name", []) or [])
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
