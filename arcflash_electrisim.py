# -*- coding: utf-8 -*-
"""
Arc Flash analysis for Electrisim (IEEE 1584-2018).

Runs a 3-phase maximum short-circuit study with pandapower, then applies the
IEEE 1584-2018 empirical model (via arcflash-calc) at each bus. Voltages above
15 kV use the Ralph Lee method and are flagged in the response.
"""
from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandapower as pp
import pandapower.shortcircuit as sc

try:
    from arcflash.ieee_1584.cubicle import Cubicle
    from arcflash.ieee_1584.calculation import Calculation
    from arcflash.ieee_1584.units import kV, kA, mm, ms, cal_per_sq_cm
    _HAS_ARCFLASH = True
except ImportError:
    Cubicle = None  # type: ignore
    Calculation = None  # type: ignore
    _HAS_ARCFLASH = False


VALID_ELECTRODE_CONFIGS = ("VCB", "VCBB", "HCB", "VOA", "HOA")


def _ppe_category(ie_cal: float) -> str:
    """Map incident energy (cal/cm²) to NFPA 70E PPE category label."""
    if ie_cal is None or (isinstance(ie_cal, float) and math.isnan(ie_cal)):
        return "N/A"
    if ie_cal < 1.2:
        return "0"
    if ie_cal < 4.0:
        return "1"
    if ie_cal < 8.0:
        return "2"
    if ie_cal < 25.0:
        return "3"
    if ie_cal < 40.0:
        return "4"
    return "Dangerous"


def _bus_display_name(net, bus_row, bus_idx) -> str:
    """Prefer Electrisim dialog / user-friendly name over mxCell object id."""
    internal = bus_row["name"] if "name" in bus_row.index and bus_row["name"] is not None else str(bus_idx)
    internal_s = str(internal)
    uf = getattr(net, "user_friendly_names", None) or {}
    for key in (
        internal_s,
        internal_s.replace("#", "_"),
        internal_s.replace("_", "#"),
    ):
        friendly = uf.get(key)
        if friendly not in (None, ""):
            return str(friendly)
    return internal_s


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


def _ralph_lee(ibf_ka: float, voc_kv: float, working_distance_mm: float, clearing_time_s: float) -> Tuple[float, float]:
    """
    Ralph Lee method for systems above 15 kV.
    E (cal/cm²) = 2.142e6 * V(kV) * Ibf(kA) * t(s) / D(mm)^2
    AFB solved for E = 1.2 cal/cm².
    """
    if working_distance_mm <= 0 or clearing_time_s <= 0 or ibf_ka <= 0 or voc_kv <= 0:
        return float("nan"), float("nan")
    ie = 2.142e6 * voc_kv * ibf_ka * clearing_time_s / (working_distance_mm ** 2)
    afb = math.sqrt(2.142e6 * voc_kv * ibf_ka * clearing_time_s / 1.2)
    return ie, afb


def _ieee1584_bus(
    ibf_ka: float,
    voc_kv: float,
    electrode: str,
    gap_mm: float,
    working_distance_mm: float,
    height_mm: float,
    width_mm: float,
    depth_mm: float,
    clearing_time_s: float,
    clearing_time_min_s: Optional[float] = None,
) -> Dict[str, Any]:
    """Compute IEEE 1584-2018 results for one bus. Returns dict of result fields."""
    if not _HAS_ARCFLASH:
        raise RuntimeError(
            "arcflash-calc is not installed. Install with: pip install arcflash-calc"
        )

    t_full_ms = clearing_time_s * 1000.0
    t_min_ms = (clearing_time_min_s if clearing_time_min_s is not None else clearing_time_s) * 1000.0

    cubicle = Cubicle(
        V_oc=voc_kv * kV,
        EC=electrode,
        G=gap_mm * mm,
        D=working_distance_mm * mm,
        height=height_mm * mm,
        width=width_mm * mm,
        depth=depth_mm * mm,
    )

    full = Calculation(cubicle, ibf_ka * kA, "full")
    full.calculate_I_arc()
    full.calculate_E_AFB(t_full_ms * ms)

    reduced = Calculation(cubicle, ibf_ka * kA, "reduced")
    reduced.calculate_I_arc()
    reduced.calculate_E_AFB(t_min_ms * ms)

    e_full = float(full.E.to(cal_per_sq_cm).magnitude)
    e_red = float(reduced.E.to(cal_per_sq_cm).magnitude)
    afb_full = float(full.AFB.magnitude)
    afb_red = float(reduced.AFB.magnitude)

    # Worst-case (max) incident energy and corresponding AFB / arcing current
    if e_red >= e_full:
        ie = e_red
        afb = afb_red
        ia = float(reduced.I_arc.magnitude)
        t_used = t_min_ms / 1000.0
    else:
        ie = e_full
        afb = afb_full
        ia = float(full.I_arc.magnitude)
        t_used = t_full_ms / 1000.0

    return {
        "ia_ka": ia,
        "ia_full_ka": float(full.I_arc.magnitude),
        "ia_min_ka": float(reduced.I_arc.magnitude),
        "incident_energy_cal_cm2": ie,
        "arc_flash_boundary_mm": afb,
        "ppe_category": _ppe_category(ie),
        "method": "IEEE1584-2018",
        "clearing_time_used_s": t_used,
        "cf": float(cubicle.CF.magnitude) if cubicle.CF is not None else None,
    }


def arcflash(net, in_data, in_data_full=None):
    """
    Run short-circuit then IEEE 1584-2018 (or Ralph Lee) per bus.

    Expected keys in in_data:
      electrode_config: VCB|VCBB|HCB|VOA|HOA (default VCB)
      working_distance_mm (default 455)
      conductor_gap_mm (default 25)
      enclosure_height_mm / enclosure_width_mm / enclosure_depth_mm (default 508)
      clearing_time_s (default 0.2)
      clearing_time_min_s (optional; defaults to clearing_time_s)
    """
    if not _HAS_ARCFLASH:
        return json.dumps({
            "error": True,
            "message": "Arc flash library not available on the server. Install arcflash-calc.",
            "exception": "ImportError: arcflash-calc",
        })

    electrode = str(in_data.get("electrode_config", "VCB") or "VCB").upper().strip()
    if electrode not in VALID_ELECTRODE_CONFIGS:
        electrode = "VCB"

    working_distance_mm = float(in_data.get("working_distance_mm", 455) or 455)
    conductor_gap_mm = float(in_data.get("conductor_gap_mm", 25) or 25)
    height_mm = float(in_data.get("enclosure_height_mm", 508) or 508)
    width_mm = float(in_data.get("enclosure_width_mm", 508) or 508)
    depth_mm = float(in_data.get("enclosure_depth_mm", 508) or 508)
    clearing_time_s = float(in_data.get("clearing_time_s", 0.2) or 0.2)
    clearing_time_min_s = in_data.get("clearing_time_min_s")
    if clearing_time_min_s is None or clearing_time_min_s == "":
        clearing_time_min_s = clearing_time_s
    else:
        clearing_time_min_s = float(clearing_time_min_s)

    if working_distance_mm < 305:
        working_distance_mm = 305.0
    if clearing_time_s <= 0:
        clearing_time_s = 0.2
    if clearing_time_min_s <= 0:
        clearing_time_min_s = clearing_time_s

    # Ensure SC parameter present on sgens
    if hasattr(net, "sgen") and not net.sgen.empty:
        if "k" not in net.sgen.columns:
            net.sgen["k"] = 1.1
        else:
            net.sgen["k"] = net.sgen["k"].fillna(1.1)

    try:
        sc.calc_sc(
            net,
            fault="3ph",
            case="max",
            ip=False,
            ith=False,
            kappa_method="C",
            branch_results=False,
            return_all_currents=False,
        )
    except Exception as e:
        return json.dumps({
            "error": True,
            "message": "Short-circuit calculation failed (required for arc flash).",
            "exception": str(e),
        })

    if not hasattr(net, "res_bus_sc") or net.res_bus_sc is None or net.res_bus_sc.empty:
        return json.dumps({
            "error": True,
            "message": "No short-circuit bus results available for arc flash.",
            "exception": "Empty res_bus_sc",
        })

    results: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for bus_idx, bus_row in net.bus.iterrows():
        if bus_idx not in net.res_bus_sc.index:
            continue

        ikss = net.res_bus_sc.at[bus_idx, "ikss_ka"]
        if ikss is None or (isinstance(ikss, float) and (math.isnan(ikss) or ikss <= 0)):
            continue

        voc_kv = float(bus_row["vn_kv"])
        internal_name = bus_row["name"] if "name" in bus_row.index else str(bus_idx)
        name = _bus_display_name(net, bus_row, bus_idx)
        bus_id = bus_row["id"] if "id" in bus_row.index else str(bus_idx)

        entry: Dict[str, Any] = {
            "name": _clean(name),
            "id": _clean(bus_id),
            "object_id": _clean(internal_name),
            "vn_kv": _clean(voc_kv),
            "ikss_ka": _clean(float(ikss)),
            "electrode_config": electrode,
            "working_distance_mm": working_distance_mm,
            "conductor_gap_mm": conductor_gap_mm,
            "clearing_time_s": clearing_time_s,
        }

        # Outside IEEE 1584 range: Ralph Lee (>15 kV) or skip/warn (<0.208 kV)
        if voc_kv > 15.0:
            ie, afb = _ralph_lee(float(ikss), voc_kv, working_distance_mm, clearing_time_s)
            entry.update({
                "ia_ka": _clean(float(ikss)),  # Ralph Lee uses bolted current
                "incident_energy_cal_cm2": _clean(ie),
                "arc_flash_boundary_mm": _clean(afb),
                "ppe_category": _ppe_category(ie),
                "method": "RalphLee",
                "note": "Voltage > 15 kV: IEEE 1584-2018 not applicable; Ralph Lee method used.",
            })
            warnings.append(f"Bus {name}: Ralph Lee method used (V={voc_kv} kV > 15 kV).")
            results.append(entry)
            continue

        if voc_kv < 0.208:
            entry.update({
                "ia_ka": None,
                "incident_energy_cal_cm2": None,
                "arc_flash_boundary_mm": None,
                "ppe_category": "N/A",
                "method": "skipped",
                "note": "Voltage < 0.208 kV: below IEEE 1584-2018 applicability range.",
            })
            warnings.append(f"Bus {name}: skipped (V={voc_kv} kV < 0.208 kV).")
            results.append(entry)
            continue

        # Clamp Ibf to model ranges with a soft warning (library raises otherwise)
        ibf = float(ikss)
        if voc_kv <= 0.6:
            if ibf < 0.5:
                warnings.append(f"Bus {name}: Ibf={ibf:.3f} kA below LV model min 0.5 kA; clamped.")
                ibf = 0.5
            elif ibf > 106.0:
                warnings.append(f"Bus {name}: Ibf={ibf:.3f} kA above LV model max 106 kA; clamped.")
                ibf = 106.0
        else:
            if ibf < 0.2:
                warnings.append(f"Bus {name}: Ibf={ibf:.3f} kA below MV model min 0.2 kA; clamped.")
                ibf = 0.2
            elif ibf > 65.0:
                warnings.append(f"Bus {name}: Ibf={ibf:.3f} kA above MV model max 65 kA; clamped.")
                ibf = 65.0

        try:
            af = _ieee1584_bus(
                ibf_ka=ibf,
                voc_kv=voc_kv,
                electrode=electrode,
                gap_mm=conductor_gap_mm,
                working_distance_mm=working_distance_mm,
                height_mm=height_mm,
                width_mm=width_mm,
                depth_mm=depth_mm,
                clearing_time_s=clearing_time_s,
                clearing_time_min_s=clearing_time_min_s,
            )
            entry.update({k: _clean(v) for k, v in af.items()})
        except Exception as e:
            entry.update({
                "ia_ka": None,
                "incident_energy_cal_cm2": None,
                "arc_flash_boundary_mm": None,
                "ppe_category": "N/A",
                "method": "error",
                "note": str(e),
            })
            warnings.append(f"Bus {name}: arc flash calculation failed: {e}")

        results.append(entry)

    payload = {
        "arc_flash": results,
        "parameters": {
            "electrode_config": electrode,
            "working_distance_mm": working_distance_mm,
            "conductor_gap_mm": conductor_gap_mm,
            "enclosure_height_mm": height_mm,
            "enclosure_width_mm": width_mm,
            "enclosure_depth_mm": depth_mm,
            "clearing_time_s": clearing_time_s,
            "clearing_time_min_s": clearing_time_min_s,
            "fault": "3ph",
            "case": "max",
        },
    }
    if warnings:
        payload["warnings"] = warnings

    return json.dumps(payload, allow_nan=False)
