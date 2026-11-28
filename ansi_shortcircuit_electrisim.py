# -*- coding: utf-8 -*-
"""
ANSI/IEEE C37 short-circuit analysis for Electrisim.

Implements first-cycle (1/2-cycle), interrupting (1.5-4 cycle), and 30-cycle
symmetrical networks with IEEE C37.010 / C37.13 / UL 489 / C37.013 duty
factors. Uses the pandapower network model but does NOT call IEC 60909 calc_sc.

Beta: engineering implementation for review. Verify against utility
requirements before using results for equipment ratings.
"""
from __future__ import annotations

import copy
import json
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import pandapower as pp
from pandapower.auxiliary import _add_auxiliary_elements
from pandapower.pd2ppc import _pd2ppc, _ppc2ppci
from pandapower.pypower.idx_bus import BASE_KV, BS, GS
from pandapower.pypower.idx_bus_sc import C_MAX, C_MIN
from pandapower.pypower.idx_brch_sc import K_T, K_ST
from pandapower.shortcircuit.impedance import _calc_ybus, _calc_zbus

from sc_fault_location import (
    collect_fault_bus_refs,
    normalize_fault_bus_mode,
    resolve_pp_fault_bus_indices,
)

try:
    from pandapower.pf.makeYbus_numba import makeYbus
except ImportError:
    from pandapower.pypower.makeYbus import makeYbus

NETWORK_FIRST = "first_cycle"
NETWORK_INT = "interrupting"
NETWORK_30 = "steady_state"

ANSI_MACHINE_TYPES = ("turbo", "hydro_amortisseur", "hydro", "sync_motor")
DEVICE_CLASSES = ("auto", "hv_c37_010", "lv_c37_013", "mccb_ul_489", "generator_c37_013")


def _f(v, default=0.0) -> float:
    try:
        if v is None or v == "" or str(v).lower() in ("null", "none", "nan"):
            return float(default)
        return float(v)
    except (TypeError, ValueError):
        return float(default)


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


def _display_name(net, internal_name: str, row_id: Any = None) -> str:
    uf = getattr(net, "user_friendly_names", None) or {}
    for key in (internal_name, str(internal_name).replace("#", "_"), str(internal_name).replace("_", "#")):
        if key in uf and uf[key]:
            return str(uf[key])
    return str(internal_name) if internal_name else (str(row_id) if row_id is not None else "")


# ---------------------------------------------------------------------------
# IEEE C37.010 multiplying factors (60 Hz primary; 50 Hz adjusted)
# ---------------------------------------------------------------------------

def _dc_decay(xr: float, t_s: float, freq_hz: float) -> float:
    """DC component as a fraction of the initial value after t_s seconds.

    The DC time constant is tau = (X/R) / (2*pi*f), so the decay depends only on
    X/R and the elapsed time expressed in cycles.
    """
    xr = max(float(xr), 1e-6)
    return math.exp(-2.0 * math.pi * float(freq_hz) * float(t_s) / xr)


def _peak_multiplier_remote(xr: float, freq_hz: float = 60.0) -> float:
    """First-cycle peak (crest) current as a multiple of the symmetrical rms.

    ip / Isym = sqrt(2) * (1 + exp(-pi / (X/R))), the first peak of a fully
    offset wave half a cycle after fault inception. Bounded by 2*sqrt(2) as
    X/R -> infinity. Frequency independent, because both the DC time constant
    and the half-cycle time scale with 1/f.
    """
    dc = _dc_decay(xr, 1.0 / (2.0 * float(freq_hz)), freq_hz)
    return math.sqrt(2.0) * (1.0 + dc)


def _interrupting_multiplier_remote(xr: float, cp_cycles: float, freq_hz: float = 60.0) -> float:
    """Total asymmetrical rms at contact parting, as a multiple of symmetrical.

    Itotal = sqrt(Iac^2 + Idc^2) with Idc = sqrt(2) * Isym * decay, giving
    sqrt(1 + 2 * decay^2).
    """
    dc = _dc_decay(xr, float(cp_cycles) / float(freq_hz), freq_hz)
    return math.sqrt(1.0 + 2.0 * dc * dc)


def _symmetry_factor_s(cp_cycles: float, freq_hz: float = 60.0) -> float:
    """Asymmetrical rms already covered by a symmetrically rated breaker.

    IEEE C37.010 rates breakers on a test circuit with X/R = 17, so the duty a
    symmetrically rated device tolerates is the asymmetrical rms of that circuit
    at contact parting. The system duty is divided by this value.
    """
    dc = _dc_decay(17.0, float(cp_cycles) / float(freq_hz), freq_hz)
    return math.sqrt(1.0 + 2.0 * dc * dc)


def _interrupting_multiplier_symm(xr: float, cp_cycles: float, freq_hz: float = 60.0) -> float:
    """Interrupting multiplier for a symmetrically rated breaker.

    A symmetrically rated breaker already withstands the X/R = 17 test
    asymmetry, so only the excess counts; never credit below 1.0.
    """
    mf_int = _interrupting_multiplier_remote(xr, cp_cycles, freq_hz)
    s_factor = _symmetry_factor_s(cp_cycles, freq_hz)
    return max(1.0, mf_int / s_factor) if s_factor > 0 else mf_int


def _lv_test_xr(device_class: str) -> float:
    if device_class == "mccb_ul_489":
        return 4.9
    return 6.6


def _lv_extra_multiplier(xr: float, device_class: str, freq_hz: float = 60.0) -> float:
    """Derating when the system X/R exceeds the LV device's test X/R.

    LV devices are tested on a circuit with a specified X/R (6.6 for C37.13
    power circuit breakers, 4.9 for UL 489 moulded case), so the duty is scaled
    by the ratio of first-cycle peak asymmetry factors. Never below 1.0.
    """
    test_xr = _lv_test_xr(device_class)
    if xr <= test_xr:
        return 1.0
    return _peak_multiplier_remote(xr, freq_hz) / _peak_multiplier_remote(test_xr, freq_hz)


def close_latch_factor(device_class: str, freq_hz: float = 60.0) -> float:
    """Close-and-latch (momentary) peak as a multiple of the symmetrical interrupting rating.

    IEEE C37.04 rates an HV breaker's closing and latching current at 2.6 x its rated
    short-circuit current at 60 Hz (2.5 x at 50 Hz, as IEC 62271-100); IEEE C37.013 rates a
    generator breaker at 2.74 x. Low-voltage breakers (C37.13, UL 489) have no separate rating:
    their peak capability is the first-cycle peak of the test circuit, at the test X/R.
    """
    if device_class == "generator_c37_013":
        return 2.74
    if device_class in ("lv_c37_013", "mccb_ul_489"):
        return _peak_multiplier_remote(_lv_test_xr(device_class), freq_hz)
    return 2.5 if float(freq_hz) < 55.0 else 2.6


def _machine_x_multiplier(network: str, machine_kind: str, hp: float = 0.0) -> float:
    """ANSI reactance multiplier on subtransient base."""
    if network == NETWORK_FIRST:
        return 1.0
    if network == NETWORK_INT:
        if machine_kind == "motor":
            if hp > 0 and hp < 50.0:
                return 0.0
            return 4.5
        return 1.5
    if network == NETWORK_30:
        if machine_kind == "motor":
            return 0.0
        return 1.5
    return 1.0


def _motor_hp(pn_mech_mw: float) -> float:
    if pn_mech_mw <= 0:
        return 0.0
    return pn_mech_mw * 1000.0 / 0.746


# ---------------------------------------------------------------------------
# PPC / Ybus for ANSI (no IEC c-factor, no K_G, no K_T)
# ---------------------------------------------------------------------------

# The voltage factor c_max that _init_ansi_ppc leaves on every bus while pandapower builds the
# branches (case "max", 10 % LV tolerance), and that pandapower puts into K_T.
_IEC_C_MAX_BUILD = 1.1


def _kt_cancel_scale(vk_percent, vkr_percent, psu=None) -> np.ndarray:
    """Scale for vk and vkr that makes pandapower's K_T product come out at the nameplate value.

    pandapower multiplies the transformer impedance by K_T = 0.95 c / (1 + 0.6 x_T), with x_T
    taken from the same vk and vkr. With both scaled by s = 1 / (0.95 c - 0.6 x_T), K_T from the
    scaled data is exactly 1 / s. Power station unit transformers have K_T = 1 and keep s = 1.
    """
    vk = pd.to_numeric(pd.Series(vk_percent), errors="coerce").fillna(0.0).to_numpy(dtype=float)
    vkr = pd.to_numeric(pd.Series(vkr_percent), errors="coerce").fillna(0.0).to_numpy(dtype=float)
    xt = np.sqrt(np.clip((vk / 100.0) ** 2 - (vkr / 100.0) ** 2, 0.0, None))
    den = 0.95 * _IEC_C_MAX_BUILD - 0.6 * xt
    scale = np.where(den > 0.05, 1.0 / np.where(den > 0.05, den, 1.0), 1.0)
    if psu is not None:
        is_psu = pd.Series(psu).fillna(False).astype(bool).to_numpy()
        scale = np.where(is_psu, 1.0, scale)
    return scale


def _cancel_transformer_correction_factor(net) -> None:
    """Take the IEC 60909 factor K_T back out of the transformer impedances.

    In short-circuit mode pandapower multiplies each transformer's positive- and
    zero-sequence impedance by K_T while it builds the branches, before _init_ansi_ppc can
    reset the K_T column, so the ANSI study ran 7 % high behind a 20 % transformer and 1 % low
    behind a 5.75 % one. IEEE C37.010 uses the nameplate impedance. ``net`` is the study's
    working copy; its vk, vkr, vk0 and vkr0 are scaled so that pandapower's product gives the
    nameplate values (and mag0_percent the other way, as pandapower takes the zero-sequence
    magnetising impedance from the scaled vk0 before K_T).
    """
    trafo = net.get("trafo")
    if trafo is not None and not trafo.empty and "vk_percent" in trafo.columns:
        psu = trafo["power_station_unit"] if "power_station_unit" in trafo.columns else None
        s = _kt_cancel_scale(trafo["vk_percent"].values, trafo.get("vkr_percent", 0.0), psu)
        for col in ("vk_percent", "vkr_percent", "vk0_percent", "vkr0_percent"):
            if col in trafo.columns:
                trafo[col] = pd.to_numeric(trafo[col], errors="coerce").astype(float) * s
        if "mag0_percent" in trafo.columns:
            trafo["mag0_percent"] = pd.to_numeric(trafo["mag0_percent"], errors="coerce").astype(float) / s

    t3 = net.get("trafo3w")
    if t3 is not None and not t3.empty:
        psu = t3["power_station_unit"] if "power_station_unit" in t3.columns else None
        for side in ("hv", "mv", "lv"):
            vk_col, vkr_col = f"vk_{side}_percent", f"vkr_{side}_percent"
            if vk_col not in t3.columns:
                continue
            s = _kt_cancel_scale(t3[vk_col].values, t3.get(vkr_col, 0.0), psu)
            for col in (vk_col, vkr_col, f"vk0_{side}_percent", f"vkr0_{side}_percent"):
                if col in t3.columns:
                    t3[col] = pd.to_numeric(t3[col], errors="coerce").astype(float) * s


def _init_ansi_ppc(net, prefault_v: float = 1.0):
    """Build ppc/ppci for ANSI study without IEC 60909 corrections."""
    from pandapower.auxiliary import _add_ppc_options, _add_sc_options
    net["_options"] = {}
    _add_ppc_options(
        net,
        calculate_voltage_angles=False,
        trafo_model="pi",
        check_connectivity=False,
        mode="sc",
        switch_rx_ratio=2,
        init_vm_pu="flat",
        init_va_degree="flat",
        enforce_q_lims=False,
        recycle=None,
    )
    _add_sc_options(
        net,
        fault="3ph",
        case="max",
        lv_tol_percent=10,
        tk_s=1.0,
        topology="auto",
        r_fault_ohm=0.0,
        x_fault_ohm=0.0,
        kappa=False,
        ip=False,
        ith=False,
        branch_results=False,
        kappa_method="C",
        return_all_currents=False,
        inverse_y=True,
        use_pre_fault_voltage=False,
    )
    _add_auxiliary_elements(net)
    ppc, _ = _pd2ppc(net)
    ppci = _ppc2ppci(ppc, net)
    # In sc mode _pd2ppc pre-builds the ext_grid and motor short-circuit impedances
    # into the bus shunt columns using IEC voltage factors. ANSI needs to own the
    # source model so it can apply per-network machine multipliers (first-cycle,
    # interrupting, 30-cycle), so clear those shunts and let the _add_*_ansi
    # helpers rebuild them. Nothing legitimate is discarded: sc mode never calls
    # _calc_shunts_and_add_on_ppc, so capacitors, reactors and wards are absent,
    # and load impedances are only added when use_pre_fault_voltage is set.
    ppci["bus"][:, GS] = 0.0
    ppci["bus"][:, BS] = 0.0
    ppci["bus"][:, C_MAX] = prefault_v
    ppci["bus"][:, C_MIN] = prefault_v
    if ppci["branch"].shape[1] > K_T:
        ppci["branch"][:, K_T] = 1.0
    if ppci["branch"].shape[1] > K_ST:
        ppci["branch"][:, K_ST] = 1.0
    # _calc_ybus / _calc_zbus repopulate "internal", but branch_is comes from
    # _ppc2ppci and is what maps pandapower branches onto ppci rows once
    # out-of-service branches have been dropped, so carry it across.
    branch_is = ppci["internal"].get("branch_is") if ppci.get("internal") else None
    ppci["internal"] = {} if branch_is is None else {"branch_is": branch_is}
    return ppc, ppci


def _y_add_shunt(ppci, bus_ppc: int, y_pu: complex):
    """Inject a per-unit shunt admittance at a ppc bus.

    makeYbus rebuilds the shunt as Ysh = (GS + j*BS) / baseMVA, so the values
    stored in those columns must carry the admittance scaled by baseMVA.
    """
    ppci["bus"][bus_ppc, GS] += y_pu.real * ppci["baseMVA"]
    ppci["bus"][bus_ppc, BS] += y_pu.imag * ppci["baseMVA"]


def _z_to_y_pu(r_ohm: float, x_ohm: float, base_z_ohm: float) -> complex:
    """Per-unit admittance of an ohmic impedance: y_pu = 1 / (z_ohm / base_z)."""
    z = complex(r_ohm, x_ohm)
    if abs(z) < 1e-12:
        z = 1e-6 + 1e-6j
    return base_z_ohm / z


def _ppc_bus(net, pp_bus_idx) -> Optional[int]:
    bus_lookup = net["_pd2ppc_lookups"]["bus"]
    try:
        return int(bus_lookup[pp_bus_idx])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _add_ext_grid_ansi(net, ppci, prefault_v: float):
    if net.ext_grid.empty:
        return
    for _, row in net.ext_grid[net.ext_grid.in_service].iterrows():
        bus = int(row["bus"])
        bus_ppc = _ppc_bus(net, bus)
        if bus_ppc is None:
            continue
        vn = float(net.bus.at[bus, "vn_kv"])
        s_sc = _f(row.get("s_sc_max_mva"), 10000.0)
        if s_sc <= 0:
            s_sc = 10000.0
        rx = _f(row.get("rx_max"), 0.1)
        z_abs = vn * vn / s_sc
        # rx_max is R/X, so X = |Z|/sqrt(1+(R/X)^2) and R = (R/X)*X.
        x = z_abs / math.sqrt(1.0 + rx * rx)
        r = rx * x
        base_z = vn * vn / ppci["baseMVA"]
        _y_add_shunt(ppci, bus_ppc, _z_to_y_pu(r, x, base_z))


def _add_gen_ansi(net, ppci, network: str, gen_meta: Dict[int, dict]):
    if net.gen.empty:
        return
    for idx, row in net.gen[net.gen.in_service].iterrows():
        bus = int(row["bus"])
        bus_ppc = _ppc_bus(net, bus)
        if bus_ppc is None:
            continue
        vn_bus = float(net.bus.at[bus, "vn_kv"])
        vn_gen = _f(row.get("vn_kv"), vn_bus) or vn_bus
        sn = _f(row.get("sn_mva"), 100.0) or 100.0
        xdss = _f(row.get("xdss_pu"), 0.2) or 0.2
        rdss = _f(row.get("rdss_ohm"), 0.0)
        mtype = str(row.get("ansi_machine_type", "turbo") or "turbo").lower()
        if mtype not in ANSI_MACHINE_TYPES:
            mtype = "turbo"
        mult = _machine_x_multiplier(network, "gen")
        if mult <= 0:
            continue
        x_ohm = xdss * mult * (vn_gen * vn_gen) / sn
        r_ohm = rdss if rdss > 0 else 0.05 * x_ohm
        base_z = vn_bus * vn_bus / ppci["baseMVA"]
        _y_add_shunt(ppci, bus_ppc, _z_to_y_pu(r_ohm, x_ohm, base_z))
        gen_meta[idx] = {"bus_ppc": bus_ppc, "x_ohm": x_ohm, "bus": bus}


def _add_motor_ansi(net, ppci, network: str):
    if not hasattr(net, "motor") or net.motor.empty:
        return
    for _, row in net.motor[net.motor.in_service].iterrows():
        bus = int(row["bus"])
        bus_ppc = _ppc_bus(net, bus)
        if bus_ppc is None:
            continue
        pn = _f(row.get("pn_mech_mw"), 0.0)
        hp = _motor_hp(pn)
        mult = _machine_x_multiplier(network, "motor", hp)
        if mult <= 0:
            continue
        vn = _f(row.get("vn_kv"), float(net.bus.at[bus, "vn_kv"])) or float(net.bus.at[bus, "vn_kv"])
        lrc = _f(row.get("lrc_pu"), 0.0)
        if lrc <= 0:
            continue
        rx = _f(row.get("rx"), 0.0)
        cos_phi = _f(row.get("cos_phi_n"), 0.0) or _f(row.get("cos_phi"), 0.85) or 0.85
        eff = _f(row.get("efficiency_n_percent"), 90.0) or 90.0
        sn = pn / (cos_phi * eff / 100.0) if cos_phi > 0 and eff > 0 else pn
        if sn <= 0:
            sn = pn if pn > 0 else 1.0
        z_base = vn * vn / sn
        z_lr = z_base / lrc
        x_ohm = mult * z_lr / math.sqrt(1.0 + rx * rx)
        r_ohm = x_ohm * rx
        base_z = vn * vn / ppci["baseMVA"]
        _y_add_shunt(ppci, bus_ppc, _z_to_y_pu(r_ohm, x_ohm, base_z))


def _add_sgen_ansi(net, ppci, network: str):
    if net.sgen.empty or "generator_type" not in net.sgen.columns:
        return
    for _, row in net.sgen[net.sgen.in_service].iterrows():
        gtype = str(row.get("generator_type", "") or "").lower()
        bus = int(row["bus"])
        bus_ppc = _ppc_bus(net, bus)
        if bus_ppc is None:
            continue
        vn = float(net.bus.at[bus, "vn_kv"])
        base_z = vn * vn / ppci["baseMVA"]
        if network == NETWORK_30:
            continue
        if gtype in ("async", "async_doubly_fed"):
            if network == NETWORK_INT:
                continue
            sn = _f(row.get("sn_mva"), 0.0)
            lrc = _f(row.get("lrc_pu"), 0.0)
            if sn <= 0 or lrc <= 0:
                continue
            rx = _f(row.get("rx"), 0.0)
            z_lr = (vn * vn / sn) / lrc
            x_ohm = z_lr / math.sqrt(1.0 + rx * rx)
            r_ohm = x_ohm * rx
            _y_add_shunt(ppci, bus_ppc, _z_to_y_pu(r_ohm, x_ohm, base_z))
        elif row.get("current_source") or gtype == "current_source":
            max_ik = _f(row.get("max_ik_ka"), 0.0)
            if max_ik <= 0:
                continue
            rx = _f(row.get("rx"), 0.1) or 0.1
            z_ohm = vn / (math.sqrt(3) * max_ik)
            x_ohm = z_ohm / math.sqrt(1.0 + rx * rx)
            r_ohm = x_ohm * rx
            _y_add_shunt(ppci, bus_ppc, _z_to_y_pu(r_ohm, x_ohm, base_z))


def _add_storage_ansi(net, ppci, network: str):
    if not hasattr(net, "storage") or net.storage.empty:
        return
    if network == NETWORK_30:
        return
    for _, row in net.storage[net.storage.in_service].iterrows():
        max_ik = _f(row.get("max_ik_ka"), 0.0)
        cs = row.get("current_source")
        if not (cs in (True, "true", "True", 1, "1") or max_ik > 0):
            continue
        if max_ik <= 0:
            continue
        bus = int(row["bus"])
        bus_ppc = _ppc_bus(net, bus)
        if bus_ppc is None:
            continue
        vn = float(net.bus.at[bus, "vn_kv"])
        base_z = vn * vn / ppci["baseMVA"]
        rx = _f(row.get("rx"), 0.1) or 0.1
        z_ohm = vn / (math.sqrt(3) * max_ik)
        x_ohm = z_ohm / math.sqrt(1.0 + rx * rx)
        r_ohm = x_ohm * rx
        _y_add_shunt(ppci, bus_ppc, _z_to_y_pu(r_ohm, x_ohm, base_z))


# Zero-sequence impedance of a bus with no path to earth (pandapower's open-path value).
_Z0_OPEN = 1e20 * (1.0 + 1.0j)

_IMPEDANCE_Z0_FROM_Z1 = (("rft0_pu", "rft_pu"), ("xft0_pu", "xft_pu"), ("rtf0_pu", "rtf_pu"),
                         ("xtf0_pu", "xtf_pu"), ("gf0_pu", "gf_pu"), ("bf0_pu", "bf_pu"),
                         ("gt0_pu", "gt_pu"), ("bt0_pu", "bt_pu"))


def _impedance_zero_sequence_from_positive(net0) -> List[str]:
    """Give each Impedance without zero-sequence data Z0 = Z1, on the zero-sequence copy.

    pandapower reads rft0_pu ... bt0_pu, which Electrisim did not write, and stopped with
    KeyError 'rft0_pu'. Z0 = Z1 is the IEC 60909-0 value for a current-limiting reactor and keeps
    the earthing paths of the positive sequence. Values that are set are kept.
    """
    imp = net0.get("impedance")
    if imp is None or imp.empty:
        return []
    filled = pd.Series(False, index=imp.index)
    for zero_col, pos_col in _IMPEDANCE_Z0_FROM_Z1:
        pos = pd.to_numeric(imp[pos_col], errors="coerce") if pos_col in imp.columns else 0.0
        if zero_col in imp.columns:
            current = pd.to_numeric(imp[zero_col], errors="coerce")
        else:
            current = pd.Series(np.nan, index=imp.index)
        missing = current.isna()
        if zero_col.startswith(("rft0", "xft0", "rtf0", "xtf0")):
            filled |= missing
        imp[zero_col] = current.where(~missing, pos).fillna(0.0).astype(float)
    labels = [_display_name(net0, str(imp.at[i, "name"]) if "name" in imp.columns else str(i), i)
              for i in imp.index[filled.to_numpy()]]
    if not labels:
        return []
    shown = ", ".join(f"'{label}'" for label in labels[:5])
    if len(labels) > 5:
        shown += f" and {len(labels) - 5} more"
    noun = "Impedance" if len(labels) == 1 else "Impedances"
    return [f"{noun} {shown}: no zero-sequence data, used Z0 = Z1 (R0 = R1, X0 = X1) "
            f"for the line-to-ground fault."]


def _drop_extended_wards_from_zero_sequence(net0) -> None:
    """Leave Extended Wards out of the zero-sequence copy, as pandapower does for a plain Ward.

    An Extended Ward is a positive-sequence equivalent without zero-sequence data. pandapower
    3.3 reserves a zero-sequence branch for it but never fills it (R = X = 0), so the build
    divided by zero. Its internal bus is a dead end in every sequence, so dropping it from the
    zero-sequence network changes no other bus.
    """
    xward = net0.get("xward")
    if xward is not None and not xward.empty:
        net0["xward"] = xward.iloc[0:0].copy()


def _zero_sequence_z_diag(net, n_bus: int, n_branch: int) -> Tuple[np.ndarray, List[str]]:
    """Zero-sequence driving-point impedance (per unit) of every bus, for line-to-ground faults.

    Uses pandapower's zero-sequence model: transformer vector groups and earthed neutrals
    (YN / D windings, vk0), line R0 / X0 / C0 and the External Grid X0/X and R0/X0. A part of
    the network that has no earth of its own (behind a delta winding) stays open, so a fault
    there carries only its capacitive current. The IEC 60909 correction factors are left out
    (K_ST = 1) and the grid impedance is |Z| = Un^2 / S"k as in the positive sequence.

    The earlier model ignored every transformer and put each line's zero-sequence impedance
    from both ends to earth, so an unearthed 6 kV switchboard showed a larger line-to-ground
    current than its three-phase current.

    ``net`` is the network prepared by ``_init_ansi_ppc``; it is not changed. Returns the
    impedances indexed like the positive-sequence ppci buses, and notes on the data used.
    """
    from pandapower.pd2ppc_zero import _pd2ppc_zero
    from pandapower_electrisim import (
        ensure_ext_grid_zero_sequence_ratios,
        ensure_line_zero_sequence_data,
        ensure_trafo3w_zero_sequence_data,
    )
    from sc_zero_sequence_zbus import electrisim_calc_zbus

    work0 = copy.deepcopy(net)
    work0.warnings = []
    notes = list(ensure_ext_grid_zero_sequence_ratios(work0, "1ph"))
    notes += ensure_trafo3w_zero_sequence_data(work0, "1ph")
    notes += ensure_line_zero_sequence_data(work0, "1ph")
    notes += _impedance_zero_sequence_from_positive(work0)
    _drop_extended_wards_from_zero_sequence(work0)
    if not work0.ext_grid.empty:
        s_sc = pd.to_numeric(work0.ext_grid["s_sc_max_mva"], errors="coerce")
        s_sc = s_sc.where(s_sc > 0, 10000.0)  # the default of _add_ext_grid_ansi
        rx = pd.to_numeric(work0.ext_grid.get("rx_max", 0.1), errors="coerce")
        work0.ext_grid["rx_max"] = rx.where(rx >= 0, 0.1).fillna(0.1)
        # pandapower multiplies the grid impedance by the voltage factor c of the bus, which
        # _init_ansi_ppc sets to 1.1 (case max, 10 % LV tolerance); this cancels it.
        work0.ext_grid["s_sc_max_mva"] = s_sc * 1.1
    _, ppci0 = _pd2ppc_zero(work0, np.ones(n_branch))
    _calc_ybus(ppci0)
    electrisim_calc_zbus(work0, ppci0)
    zbus0 = ppci0["internal"]["Zbus"]

    z0 = np.full(n_bus, _Z0_OPEN, dtype=np.complex128)
    for pp_bus in net.bus.index:
        b1 = _ppc_bus(net, int(pp_bus))
        b0 = _ppc_bus(work0, int(pp_bus))
        if b1 is None or b0 is None or b1 >= n_bus or b0 >= zbus0.shape[0]:
            continue
        z0[b1] = zbus0[b0, b0]
    return z0, notes


def _fault_currents_ka(
    ppci,
    z0_diag,
    fault: str,
    prefault_v: float,
    r_fault_ohm: float,
    x_fault_ohm: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (i_sym_ka, r_ohm, x_ohm) per ppci bus index.

    r_ohm / x_ohm describe the fault loop that sets the X/R ratio: Z1 + Zf for a three-phase
    fault, (Z1 + Z2 + Zf) / 2 line to line and (Z1 + Z2 + Z0 + 3 Zf) / 3 line to ground
    (IEEE C37.010: X/R of a line-to-ground fault from 2 X1 + X0 and 2 R1 + R0).
    """
    n = ppci["bus"].shape[0]
    z_diag = np.diag(ppci["internal"]["Zbus"]).astype(np.complex128)
    base_kv = ppci["bus"][:, BASE_KV]
    base_mva = ppci["baseMVA"]
    base_z = base_kv ** 2 / base_mva
    # Base current in kA. pandapower stores the reciprocal of this as "baseI"
    # (BASE_KV * sqrt(3) / baseMVA) and divides per-unit currents by it.
    base_i = base_mva / (math.sqrt(3) * base_kv)

    i_sym = np.zeros(n, dtype=float)
    r_eq = np.zeros(n, dtype=float)
    x_eq = np.zeros(n, dtype=float)

    for b in range(n):
        z1 = z_diag[b]
        z_f = complex(r_fault_ohm, x_fault_ohm) / base_z[b] if (r_fault_ohm > 0 or x_fault_ohm > 0) else 0j
        v = prefault_v
        if fault == "2ph":
            # Line-to-line fault: I = sqrt(3) E / |Z1 + Z2 + Zf| in this per-unit system,
            # with Z2 = Z1.
            z_loop = 2.0 * z1 + z_f
            i_pu = math.sqrt(3.0) * v / max(abs(z_loop), 1e-12)
            z_eq = z_loop / 2.0
        elif fault == "1ph":
            # Line-to-ground fault: I = 3 E / |Z1 + Z2 + Z0 + 3 Zf|.
            z0 = z0_diag[b] if z0_diag is not None and b < len(z0_diag) else _Z0_OPEN
            z_loop = 2.0 * z1 + z0 + 3.0 * z_f
            i_pu = 3.0 * v / max(abs(z_loop), 1e-12)
            z_eq = z_loop / 3.0
        else:
            z_eq = z1 + z_f
            i_pu = v / max(abs(z_eq), 1e-12)
        r_eq[b] = z_eq.real * base_z[b]
        x_eq[b] = z_eq.imag * base_z[b]
        i_sym[b] = abs(i_pu) * base_i[b]
    return i_sym, r_eq, x_eq


def _branch_currents_ka(
    ppci,
    fault: str,
    prefault_v: float,
    r_fault_ohm: float,
    x_fault_ohm: float,
    fault_ppc_indices: Optional[List[int]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Worst-case branch end currents in kA, per ppci branch row.

    Superposition on the Zbus: a bolted fault at bus f draws I_f = V0 / Z_ff and
    leaves the bus voltages at V = V0 - Zbus[:, f] * I_f. The branch end currents
    then follow from the Yf / Yt incidence admittance matrices, which already
    carry transformer tap ratios and phase shifts. Each branch keeps the largest
    magnitude over all fault locations, matching the convention pandapower uses
    for branch_results with return_all_currents=False.

    Only the positive-sequence network is used, so this is meaningful for 3ph and
    2ph faults. Single-phase branch flows would need the full zero-sequence
    branch model, which this module only approximates, so the caller skips them.
    """
    branch = ppci["branch"]
    n_br = branch.shape[0]
    if n_br == 0:
        return np.zeros(0), np.zeros(0)

    zbus = ppci["internal"]["Zbus"]
    yf = ppci["internal"]["Yf"]
    yt = ppci["internal"]["Yt"]
    n_bus = ppci["bus"].shape[0]
    base_kv = ppci["bus"][:, BASE_KV]
    base_mva = ppci["baseMVA"]
    base_z = base_kv ** 2 / base_mva
    base_i = base_mva / (math.sqrt(3) * base_kv)

    fb = np.real(branch[:, 0]).astype(np.int64)
    tb = np.real(branch[:, 1]).astype(np.int64)
    z_extra = complex(r_fault_ohm, x_fault_ohm)
    # Same driving-voltage basis as _fault_currents_ka so bus and branch duties
    # stay comparable.
    scale = math.sqrt(3.0) / 2.0 if fault == "2ph" else 1.0

    max_f = np.zeros(n_br)
    max_t = np.zeros(n_br)
    v0 = np.full(n_bus, prefault_v, dtype=np.complex128)

    if fault_ppc_indices is None:
        fault_iter = range(n_bus)
    else:
        fault_iter = [int(i) for i in fault_ppc_indices if 0 <= int(i) < n_bus]

    for f in fault_iter:
        z_ff = zbus[f, f]
        if z_extra != 0:
            z_ff = z_ff + z_extra / base_z[f]
        if abs(z_ff) < 1e-12:
            continue
        i_f = (prefault_v * scale) / z_ff
        v = v0 - zbus[:, f] * i_f
        np.maximum(max_f, np.abs(yf.dot(v)) * base_i[fb], out=max_f)
        np.maximum(max_t, np.abs(yt.dot(v)) * base_i[tb], out=max_t)
    return max_f, max_t


def _ppci_branch_rows(net, ppci, element: str) -> Dict[int, int]:
    """Map pandapower element index -> ppci branch row for a branch element.

    The pd2ppc branch lookup gives a contiguous [start, stop) range of *ppc*
    rows, while ppci keeps only the in-service ones. branch_is is the mask that
    relates the two.
    """
    try:
        start, stop = net["_pd2ppc_lookups"]["branch"][element]
    except (KeyError, TypeError, ValueError):
        return {}
    table = net.get(element)
    if table is None or table.empty:
        return {}

    branch_is = ppci["internal"].get("branch_is")
    if branch_is is None or len(branch_is) == 0:
        ppc_to_ppci = {i: i for i in range(int(start), int(stop))}
    else:
        ppci_row = np.cumsum(branch_is) - 1
        ppc_to_ppci = {
            i: int(ppci_row[i])
            for i in range(int(start), min(int(stop), len(branch_is)))
            if branch_is[i]
        }

    out: Dict[int, int] = {}
    for pos, elm_idx in enumerate(table.index):
        row = ppc_to_ppci.get(int(start) + pos)
        if row is not None and row >= 0:
            out[int(elm_idx)] = row
    return out


def _xr_ratio(r_ohm: float, x_ohm: float) -> float:
    r = max(abs(r_ohm), 1e-6)
    x = max(abs(x_ohm), 1e-6)
    return x / r


def _resolve_device_class(vn_kv: float, switch_row: pd.Series) -> str:
    dc = str(switch_row.get("ansi_device_class", "auto") or "auto").lower()
    if switch_row.get("generator_cb") in (True, "true", "True", 1, "1"):
        return "generator_c37_013"
    if dc != "auto":
        return dc
    if vn_kv < 1.0:
        sw_type = str(switch_row.get("type", "CB") or "CB").upper()
        if sw_type in ("CB", "LS", "LBS"):
            return "lv_c37_013"
        return "mccb_ul_489"
    return "hv_c37_010"


def _compute_device_duties(
    net,
    bus_results: Dict[int, dict],
    freq_hz: float,
    cp_cycles: float,
) -> List[dict]:
    duties = []
    if not hasattr(net, "switch") or net.switch.empty:
        return duties

    for idx, sw in net.switch.iterrows():
        if not sw.get("closed", True):
            continue
        bus = int(sw["bus"])
        br = bus_results.get(bus)
        if not br:
            continue
        vn = float(net.bus.at[bus, "vn_kv"])
        dc = _resolve_device_class(vn, sw)
        # in_ka is the switch's rated (continuous) current, not a short-circuit rating, so it is
        # never used for the interrupting check.
        int_rating = _f(sw.get("interrupting_rating_ka"), 0.0)
        mom_rating = _f(sw.get("momentary_rating_ka"), 0.0)
        mom_source = "entered" if mom_rating > 0 else None
        if mom_rating <= 0 and int_rating > 0:
            # The momentary duty is a peak current and the interrupting rating a symmetrical
            # r.m.s. value: without an entered close-and-latch rating, use the peak the device
            # standard ties to the interrupting rating.
            mom_rating = int_rating * close_latch_factor(dc, freq_hz)
            mom_source = "derived"

        xr_fc = br.get("xr_first", 15.0) or 15.0
        xr_int = br.get("xr_interrupting", xr_fc) or xr_fc
        i_fc_sym = br.get("i_first_sym_ka", 0.0) or 0.0
        i_fc_peak = br.get("i_first_peak_ka", 0.0) or 0.0
        i_30 = br.get("i_steady_ka", 0.0) or 0.0

        # The interrupting duty depends on when this breaker's contacts part,
        # so apply the multiplier at the device's own time, not the study time.
        dev_cp = _f(sw.get("contact_parting_cycles"), cp_cycles)
        if dev_cp <= 0:
            dev_cp = cp_cycles
        i_int_sym = br.get("i_interrupting_sym_ka")
        if i_int_sym is None:
            i_int = br.get("i_interrupting_ka", 0.0) or 0.0
        else:
            i_int = i_int_sym * _interrupting_multiplier_symm(xr_int, dev_cp, freq_hz)

        duty_int = i_int
        duty_mom = i_fc_peak
        std = "IEEE C37.010"
        if dc == "lv_c37_013":
            std = "IEEE C37.13"
            duty_int = i_fc_sym * _lv_extra_multiplier(xr_fc, dc, freq_hz)
            duty_mom = i_fc_peak
        elif dc == "mccb_ul_489":
            std = "UL 489"
            duty_int = i_fc_sym * _lv_extra_multiplier(xr_fc, dc, freq_hz)
            duty_mom = i_fc_peak
        elif dc == "generator_c37_013":
            std = "IEEE C37.013"
            duty_int = i_int
            duty_mom = i_fc_peak

        int_pass = int_rating <= 0 or duty_int <= int_rating * 1.0001
        mom_pass = mom_rating <= 0 or duty_mom <= mom_rating * 1.0001
        margin_int = (int_rating - duty_int) if int_rating > 0 else None
        margin_mom = (mom_rating - duty_mom) if mom_rating > 0 else None

        sw_id = sw.get("id", sw.get("name", str(idx)))
        duties.append({
            "name": _clean(sw.get("name", str(idx))),
            "id": _clean(sw_id),
            "bus": _clean(net.bus.at[bus, "name"] if bus in net.bus.index else bus),
            "vn_kv": _clean(vn),
            "device_class": dc,
            "standard": std,
            "duty_interrupting_ka": _clean(duty_int),
            "duty_momentary_ka": _clean(duty_mom),
            "duty_steady_ka": _clean(i_30),
            "interrupting_rating_ka": _clean(int_rating) if int_rating > 0 else None,
            "momentary_rating_ka": _clean(mom_rating) if mom_rating > 0 else None,
            "momentary_rating_source": mom_source,
            "interrupting_pass": int_pass if int_rating > 0 else None,
            "momentary_pass": mom_pass if mom_rating > 0 else None,
            "margin_interrupting_ka": _clean(margin_int),
            "margin_momentary_ka": _clean(margin_mom),
            "xr_interrupting": _clean(xr_int),
            "contact_parting_cycles": _clean(dev_cp),
        })
    return duties


def _solve_network(
    net,
    network: str,
    fault: str,
    prefault_v: float,
    r_fault_ohm: float,
    x_fault_ohm: float,
    gen_meta: Dict[int, dict],
    fault_pp_buses: Optional[List[int]] = None,
    zero_sequence: Optional[dict] = None,
    f_hz: Optional[float] = None,
) -> Dict[str, dict]:
    """Solve one ANSI network.

    ``zero_sequence`` (a dict) keeps the zero-sequence bus impedances between the three
    networks of one study: machines are not earthed, so they are the same in all three. The
    notes on the zero-sequence data used are left in it under "notes".

    ``f_hz`` is the study frequency. app.py builds the network at pandapower's default 50 Hz,
    and the line charging (C0) of the zero-sequence network follows the network frequency.

    Returns {"bus": {pp_bus: (i_sym_ka, r_ohm, x_ohm)},
             "line": {pp_line: (i_from_ka, i_to_ka)},
             "trafo": {pp_trafo: (i_hv_ka, i_lv_ka)}}.
    """
    work = copy.deepcopy(net)
    if f_hz:
        work.f_hz = float(f_hz)
    if hasattr(work, "gen") and not work.gen.empty and "ansi_machine_type" not in work.gen.columns:
        work.gen["ansi_machine_type"] = "turbo"
    _cancel_transformer_correction_factor(work)
    ppc, ppci = _init_ansi_ppc(work, prefault_v)
    _add_ext_grid_ansi(work, ppci, prefault_v)
    _add_gen_ansi(work, ppci, network, gen_meta)
    _add_motor_ansi(work, ppci, network)
    _add_sgen_ansi(work, ppci, network)
    _add_storage_ansi(work, ppci, network)
    _calc_ybus(ppci)
    _calc_zbus(work, ppci)
    z0_diag = None
    if fault == "1ph":
        cache = zero_sequence if zero_sequence is not None else {}
        if cache.get("z0") is None or len(cache["z0"]) != ppci["bus"].shape[0]:
            cache["z0"], cache["notes"] = _zero_sequence_z_diag(
                work, ppci["bus"].shape[0], ppc["branch"].shape[0])
        z0_diag = cache["z0"]
    i_sym, r_eq, x_eq = _fault_currents_ka(ppci, z0_diag, fault, prefault_v, r_fault_ohm, x_fault_ohm)

    buses: Dict[int, Tuple[float, float, float]] = {}
    for pp_bus in work.bus.index:
        ppc_b = _ppc_bus(work, int(pp_bus))
        if ppc_b is None or ppc_b >= len(i_sym):
            continue
        buses[int(pp_bus)] = (float(i_sym[ppc_b]), float(r_eq[ppc_b]), float(x_eq[ppc_b]))

    lines: Dict[int, Tuple[float, float]] = {}
    trafos: Dict[int, Tuple[float, float]] = {}
    if fault != "1ph":
        fault_ppc = None
        if fault_pp_buses is not None:
            fault_ppc = []
            for b in fault_pp_buses:
                ppc_b = _ppc_bus(work, int(b))
                if ppc_b is not None:
                    fault_ppc.append(ppc_b)
        i_f, i_t = _branch_currents_ka(
            ppci, fault, prefault_v, r_fault_ohm, x_fault_ohm, fault_ppc_indices=fault_ppc
        )
        for element, target in (("line", lines), ("trafo", trafos)):
            for elm_idx, row in _ppci_branch_rows(work, ppci, element).items():
                if row < len(i_f):
                    target[elm_idx] = (float(i_f[row]), float(i_t[row]))

    return {"bus": buses, "line": lines, "trafo": trafos}


def _branch_result_rows(
    net,
    element: str,
    bus_cols: Tuple[str, str],
    end_keys: Tuple[str, str],
    sol_first: Dict[str, dict],
    sol_int: Dict[str, dict],
    sol_30: Dict[str, dict],
    bus_results: Dict[int, dict],
) -> List[dict]:
    """Assemble per-branch ANSI duties for one branch element table.

    Each branch reports the larger of its two end currents for the first-cycle,
    interrupting and 30-cycle networks. Asymmetry multipliers are taken from the
    worse of the branch's two terminal buses, since the worst-case end current
    can come from a fault at either end.
    """
    table = net.get(element)
    if table is None or table.empty:
        return []

    first = sol_first.get(element, {})
    interrupting = sol_int.get(element, {})
    steady = sol_30.get(element, {})
    if not first:
        return []

    rows: List[dict] = []
    for idx in table.index:
        i = int(idx)
        if i not in first:
            continue
        i_f, i_t = first[i]
        i_first = max(i_f, i_t)
        i_int_sym = max(interrupting.get(i, (0.0, 0.0)))
        i_steady = max(steady.get(i, (0.0, 0.0)))

        mf_peak = 0.0
        mf_int = 0.0
        for col in bus_cols:
            try:
                b = int(table.at[idx, col])
            except (KeyError, TypeError, ValueError):
                continue
            br = bus_results.get(b)
            if not br:
                continue
            mf_peak = max(mf_peak, _f(br.get("mf_peak"), 0.0))
            mf_int = max(mf_int, _f(br.get("mf_interrupting"), 0.0))

        internal_name = table.at[idx, "name"] if "name" in table.columns else str(idx)
        cell_id = table.at[idx, "id"] if "id" in table.columns else internal_name
        rows.append({
            "name": _clean(internal_name),
            "id": _clean(cell_id),
            "userFriendlyName": _display_name(net, internal_name, cell_id),
            end_keys[0]: _clean(i_f),
            end_keys[1]: _clean(i_t),
            "i_first_sym_ka": _clean(i_first),
            "i_first_peak_ka": _clean(i_first * mf_peak if mf_peak > 0 else i_first),
            "i_interrupting_ka": _clean(i_int_sym * mf_int if mf_int > 0 else i_int_sym),
            "i_steady_ka": _clean(i_steady),
        })
    return rows


def shortcircuit_ansi(net, in_data, in_data_full=None) -> str:
    """Run ANSI/IEEE C37 short-circuit study; returns compact JSON string."""
    from pandapower_electrisim import network_not_ready_message
    not_ready = network_not_ready_message(net, "ANSI short circuit", needs='source')
    if not_ready:
        return json.dumps({"error": True, "message": not_ready})
    fault = str(in_data.get("fault_type", in_data.get("fault", "3ph")) or "3ph").lower()
    if fault not in ("3ph", "2ph", "1ph"):
        fault = "3ph"
    from pandapower_electrisim import trafo3w_vector_group_problem
    trafo3w_group_problem = trafo3w_vector_group_problem(net, fault, in_data_full)
    if trafo3w_group_problem:
        return json.dumps({"error": True, "message": trafo3w_group_problem})
    freq_hz = _f(in_data.get("frequency_hz", in_data.get("frequency", 60)), 60.0)
    if freq_hz <= 0:
        freq_hz = 60.0
    prefault_v = _f(in_data.get("prefault_v_pu", 1.0), 1.0)
    if prefault_v <= 0:
        prefault_v = 1.0
    cp_cycles = _f(in_data.get("contact_parting_cycles", 3), 3.0)
    r_fault = _f(in_data.get("r_fault_ohm", 0), 0.0)
    x_fault = _f(in_data.get("x_fault_ohm", 0), 0.0)
    fault_bus_mode = normalize_fault_bus_mode(in_data)
    fault_pp_buses = resolve_pp_fault_bus_indices(net, in_data)

    gen_meta: Dict[int, dict] = {}
    zero_sequence: dict = {}
    sol_first = _solve_network(net, NETWORK_FIRST, fault, prefault_v, r_fault, x_fault, gen_meta, fault_pp_buses,
                               zero_sequence, f_hz=freq_hz)
    sol_int = _solve_network(net, NETWORK_INT, fault, prefault_v, r_fault, x_fault, gen_meta, fault_pp_buses,
                             zero_sequence, f_hz=freq_hz)
    sol_30 = _solve_network(net, NETWORK_30, fault, prefault_v, r_fault, x_fault, gen_meta, fault_pp_buses,
                            zero_sequence, f_hz=freq_hz)
    rx_first, rx_int, rx_30 = sol_first["bus"], sol_int["bus"], sol_30["bus"]

    busbar_list = []
    bus_results: Dict[int, dict] = {}

    for bus_idx in net.bus[net.bus.in_service].index:
        bi = int(bus_idx)
        if fault_pp_buses is not None and bi not in fault_pp_buses:
            continue
        if bi not in rx_first:
            continue
        i_fc_sym, r_ohm, x_ohm = rx_first[bi]
        i_fc_int_sym = rx_int.get(bi, (0.0, 0.0, 0.0))[0]
        i_steady = rx_30.get(bi, (0.0, 0.0, 0.0))[0]
        r_i, x_i = rx_int.get(bi, (r_ohm, x_ohm))[1], rx_int.get(bi, (r_ohm, x_ohm))[2]

        xr_fc = _xr_ratio(r_ohm, x_ohm)
        xr_int = _xr_ratio(r_i, x_i)

        mf_peak = _peak_multiplier_remote(xr_fc, freq_hz)
        mf_int_symm = _interrupting_multiplier_symm(xr_int, cp_cycles, freq_hz)

        i_fc_peak = i_fc_sym * mf_peak
        i_interrupting = i_fc_int_sym * mf_int_symm

        vn = float(net.bus.at[bus_idx, "vn_kv"])
        br = {
            "i_first_sym_ka": i_fc_sym,
            "i_first_peak_ka": i_fc_peak,
            "i_interrupting_ka": i_interrupting,
            "i_interrupting_sym_ka": i_fc_int_sym,
            "i_steady_ka": i_steady,
            "xr_first": xr_fc,
            "xr_interrupting": xr_int,
            "mf_peak": mf_peak,
            "mf_interrupting": mf_int_symm,
        }
        bus_results[int(bus_idx)] = br

        internal_name = net.bus.at[bus_idx, "name"]
        cell_id = net.bus.at[bus_idx, "id"] if "id" in net.bus.columns else internal_name
        busbar_list.append({
            "name": _clean(internal_name),
            "id": _clean(cell_id),
            "userFriendlyName": _display_name(net, internal_name, cell_id),
            "vn_kv": _clean(vn),
            "i_first_sym_ka": _clean(i_fc_sym),
            "i_first_peak_ka": _clean(i_fc_peak),
            "i_interrupting_ka": _clean(i_interrupting),
            "i_steady_ka": _clean(i_steady),
            "xr_first": _clean(xr_fc),
            "xr_interrupting": _clean(xr_int),
            # a line-to-ground fault in a part with no earth has an open loop (no current)
            "rk_ohm": _clean(r_ohm) if abs(r_ohm) < 1e12 else None,
            "xk_ohm": _clean(x_ohm) if abs(x_ohm) < 1e12 else None,
            "mf_peak": _clean(mf_peak),
            "mf_interrupting": _clean(mf_int_symm),
        })

    device_duties = _compute_device_duties(net, bus_results, freq_hz, cp_cycles)

    lines_sc = _branch_result_rows(
        net, "line", ("from_bus", "to_bus"), ("i_from_ka", "i_to_ka"),
        sol_first, sol_int, sol_30, bus_results)
    trafos_sc = _branch_result_rows(
        net, "trafo", ("hv_bus", "lv_bus"), ("i_hv_ka", "i_lv_ka"),
        sol_first, sol_int, sol_30, bus_results)

    result = {
        "standard": "ANSI/IEEE C37",
        "beta": True,
        "fault_type": fault,
        "frequency_hz": freq_hz,
        "prefault_v_pu": prefault_v,
        "contact_parting_cycles": cp_cycles,
        "disclaimer": (
            "ANSI/IEEE C37 is in beta. Engineering implementation for North American "
            "studies — verify against utility requirements before using for equipment "
            "ratings. Do not mix with IEC 60909-rated equipment without verification."
        ),
        "busbars": busbar_list,
        "device_duties": device_duties,
        "lines_sc": lines_sc,
        "trafos_sc": trafos_sc,
        "warnings": list(zero_sequence.get("notes") or []),
        "study": "shortcircuit",
        "engine": "ansi",
        "study_params": {
            "fault_type": fault,
            "fault_bus_mode": fault_bus_mode,
            "fault_bus_ids": collect_fault_bus_refs(in_data) if fault_bus_mode == "selection" else [],
            "fault_bus_names": list(in_data.get("fault_bus_names") or []) if fault_bus_mode == "selection" else [],
            "frequency_hz": freq_hz,
            "prefault_v_pu": prefault_v,
            "contact_parting_cycles": cp_cycles,
            "standard": "ansi_c37",
        },
    }
    return json.dumps(result, separators=(",", ":"))


def _parse_id_list(text) -> set:
    if not text:
        return set()
    if isinstance(text, list):
        return {str(x).strip() for x in text if str(x).strip()}
    return {p.strip() for p in str(text).replace(";", ",").split(",") if p.strip()}


def _set_project_out_of_service(net, element_ids) -> None:
    """Disable loads/gens/sgen/storage matching diagram ids (pre-project case)."""
    want = _parse_id_list(element_ids)
    if not want:
        return
    for attr in ("load", "gen", "sgen", "storage"):
        if not hasattr(net, attr):
            continue
        df = getattr(net, attr)
        if df.empty:
            continue
        for idx in df.index:
            lid = str(df.loc[idx, "id"]) if "id" in df.columns else ""
            name = str(df.loc[idx, "name"])
            if lid in want or name in want:
                df.loc[idx, "in_service"] = False


def _merge_pre_post_ansi(pre: dict, post: dict) -> dict:
    pre_by = {str(b.get("id") or b.get("name")): b for b in pre.get("busbars", [])}
    comparison = []
    for bus in post.get("busbars", []):
        key = str(bus.get("id") or bus.get("name"))
        pb = pre_by.get(key, {})
        row = {
            "name": bus.get("userFriendlyName") or bus.get("name"),
            "id": bus.get("id"),
            "vn_kv": bus.get("vn_kv"),
            "fault_type": post.get("fault_type"),
            "i_first_sym_pre_ka": pb.get("i_first_sym_ka"),
            "i_first_sym_post_ka": bus.get("i_first_sym_ka"),
            "i_first_peak_pre_ka": pb.get("i_first_peak_ka"),
            "i_first_peak_post_ka": bus.get("i_first_peak_ka"),
            "i_interrupting_pre_ka": pb.get("i_interrupting_ka"),
            "i_interrupting_post_ka": bus.get("i_interrupting_ka"),
            "slg_note": "Use i_first_sym for 1ph SLG / NGR sizing at POI" if post.get("fault_type") == "1ph" else "",
        }
        comparison.append(row)

    duties_pre = {d.get("name"): d for d in pre.get("device_duties", [])}
    duty_comparison = []
    for d in post.get("device_duties", []):
        pd = duties_pre.get(d.get("name"), {})
        duty_comparison.append({**d, "pre_duty_interrupting_ka": pd.get("duty_interrupting_ka"), "pre_interrupting_pass": pd.get("interrupting_pass")})

    merged = dict(post)
    merged["pre_post_comparison"] = True
    merged["bus_comparison"] = comparison
    merged["device_duties"] = duty_comparison
    merged["pre_project"] = {"busbars": pre.get("busbars", []), "device_duties": pre.get("device_duties", [])}
    return merged


def shortcircuit_with_optional_pre_post(net, in_data, in_data_full=None) -> str:
    compare = str(in_data.get("compare_pre_post", "false")).lower() in ("true", "1", "yes")
    project_ids = in_data.get("project_element_ids", "")
    if compare and _parse_id_list(project_ids):
        from copy import deepcopy

        net_pre = deepcopy(net)
        _set_project_out_of_service(net_pre, project_ids)
        pre = json.loads(shortcircuit_ansi(net_pre, {**in_data, "compare_pre_post": "false"}, in_data_full))
        post = json.loads(shortcircuit_ansi(net, {**in_data, "compare_pre_post": "false"}, in_data_full))
        return json.dumps(_merge_pre_post_ansi(pre, post), separators=(",", ":"))
    return shortcircuit_ansi(net, in_data, in_data_full)


def shortcircuit(net, in_data, in_data_full=None) -> str:
    """Alias used by app.py routing."""
    return shortcircuit_with_optional_pre_post(net, in_data, in_data_full)
