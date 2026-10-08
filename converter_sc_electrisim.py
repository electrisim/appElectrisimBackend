# -*- coding: utf-8 -*-
"""Full-converter short-circuit contribution for Electrisim IEC 60909 studies.

PowerFactory reports Ik\" on the high-voltage side of the unit transformer.
pandapower injects a current source

    Ik = k * Sn / (sqrt(3) * Un)

so

    k = Ik_kA * sqrt(3) * U_ref_kV / Sn_MVA

Negative-sequence r2/x2 is a shunt on a copy of the positive-sequence Ybus and
is used only for two-phase and single-phase faults. The positive-sequence
network is left unchanged.
"""
from __future__ import annotations

import copy
import logging
import math

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_IK_COLUMN = {
    "3ph": "ikss_3ph_ka",
    "2ph": "ikss_2ph_ka",
    "1ph": "ikss_1ph_ka",
}
_DEFAULT_K = 1.1
_SC_COLUMNS = (
    "k_dialog",
    "ikss_3ph_ka",
    "ikss_2ph_ka",
    "ikss_1ph_ka",
    "sc_ref_vn_kv",
    "r2_pu",
    "x2_pu",
)


def _float(value, default=0.0) -> float:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except TypeError:
        pass
    if isinstance(value, str) and value.strip().lower() in ("", "none", "null", "nan"):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return number


def _in_service(row) -> bool:
    raw = row.get("in_service") if hasattr(row, "get") else True
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return True
    if isinstance(raw, str):
        return raw.strip().lower() not in ("false", "0", "no", "off")
    return bool(raw)


def _is_current_source(row) -> bool:
    gtype = str(row.get("generator_type") or "").strip().lower()
    if gtype in ("async", "async_doubly_fed"):
        return False
    if gtype == "current_source":
        return True
    raw = row.get("current_source")
    if isinstance(raw, str):
        return raw.strip().lower() in ("true", "1", "yes", "on")
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return True
    return bool(raw)


def k_from_ik(ik_ka, sn_mva, u_ref_kv):
    """Return k = Ik * sqrt(3) * U / Sn, or None when the inputs cannot define it."""
    ik = _float(ik_ka)
    sn = _float(sn_mva)
    voltage = _float(u_ref_kv)
    if ik <= 0 or sn <= 0 or voltage <= 0:
        return None
    return ik * math.sqrt(3.0) * voltage / sn


def _reference_voltage_kv(net, row) -> float:
    voltage = _float(row.get("sc_ref_vn_kv"))
    if voltage > 0:
        return voltage
    try:
        bus = int(row["bus"])
        return _float(net.bus.at[bus, "vn_kv"])
    except (KeyError, TypeError, ValueError):
        return 0.0


def _user_k(row):
    """Dialog k, when the row still knows it. None means an older sgen without k_dialog."""
    if "k_dialog" not in getattr(row, "index", ()):
        return None
    raw = row.get("k_dialog")
    try:
        if raw is None or pd.isna(raw):
            return None
    except TypeError:
        if raw is None:
            return None
    return _float(raw, 0.0)


def resolved_k(net, row, fault="3ph") -> float:
    """k for one static generator and one fault type."""
    if not _is_current_source(row):
        existing = _float(row.get("k"))
        return existing if existing > 0 else _DEFAULT_K

    column = _IK_COLUMN.get(fault, "ikss_3ph_ka")
    ik = _float(row.get(column)) if column else 0.0
    computed = k_from_ik(ik, row.get("sn_mva"), _reference_voltage_kv(net, row))
    if computed is not None:
        return computed

    dialog_k = _user_k(row)
    if dialog_k is not None:
        return dialog_k if dialog_k > 0 else _DEFAULT_K

    existing = _float(row.get("k"))
    return existing if existing > 0 else _DEFAULT_K


def attach_converter_sc_inputs(net, sgen_idx, payload) -> None:
    """Store dialog short-circuit inputs on the sgen row. k itself is chosen later, per fault."""
    if payload is None:
        payload = {}
    values = {
        "k_dialog": _float(payload.get("k"), 0.0),
        "ikss_3ph_ka": _float(payload.get("ikss_3ph_ka"), 0.0),
        "ikss_2ph_ka": _float(payload.get("ikss_2ph_ka"), 0.0),
        "ikss_1ph_ka": _float(payload.get("ikss_1ph_ka"), 0.0),
        "sc_ref_vn_kv": _float(payload.get("sc_ref_vn_kv"), 0.0),
        "r2_pu": _float(payload.get("r2_pu"), 0.0),
        "x2_pu": _float(payload.get("x2_pu"), 0.0),
    }
    for column in _SC_COLUMNS:
        if column not in net.sgen.columns:
            net.sgen[column] = 0.0
        net.sgen.at[sgen_idx, column] = values[column]


def apply_converter_short_circuit_k(net, fault="3ph") -> None:
    """Set net.sgen.k from Ik\" for this fault, otherwise the dialog k, otherwise 1.1."""
    if not hasattr(net, "sgen") or net.sgen is None or net.sgen.empty:
        return
    if fault not in _IK_COLUMN:
        fault = "3ph"
    if "k" not in net.sgen.columns:
        net.sgen["k"] = np.nan
    for idx, row in net.sgen.iterrows():
        if not _in_service(row):
            continue
        k_value = resolved_k(net, row, fault)
        net.sgen.at[idx, "k"] = k_value
        if _is_current_source(row):
            column = _IK_COLUMN[fault]
            ik = _float(row.get(column)) if column in net.sgen.columns else 0.0
            if k_from_ik(ik, row.get("sn_mva"), _reference_voltage_kv(net, row)) is not None:
                net.sgen.at[idx, "current_source"] = True


def sgen_k_export_lines(net, fault="3ph"):
    """Python statements that reproduce converter k for a standalone pandapower script."""
    if not hasattr(net, "sgen") or net.sgen is None or net.sgen.empty:
        return []
    if fault not in _IK_COLUMN:
        fault = "3ph"
    lines = [
        "# Converter k from Ik\" at the reference voltage when that current is set;",
        "# otherwise the dialog k; otherwise 1.1. r2/x2 are applied inside Electrisim",
        "# for two-phase and single-phase faults.",
    ]
    for idx, row in net.sgen.iterrows():
        k_value = resolved_k(net, row, fault)
        index_literal = str(int(idx)) if isinstance(idx, (int, np.integer)) else repr(idx)
        lines.append(f"net.sgen.at[{index_literal}, 'k'] = {float(k_value)!r}")
        if _is_current_source(row):
            lines.append(f"net.sgen.at[{index_literal}, 'current_source'] = True")
    return lines


def _negative_sequence_shunts(net):
    """Admittance in pu on net.sn_mva, keyed by pandapower bus. Empty when x2 is not set."""
    if not hasattr(net, "sgen") or net.sgen is None or net.sgen.empty:
        return {}
    if "x2_pu" not in net.sgen.columns:
        return {}
    sbase = _float(getattr(net, "sn_mva", 1.0), 1.0) or 1.0
    shunts = {}
    for _, row in net.sgen.iterrows():
        if not _in_service(row) or not _is_current_source(row):
            continue
        x2 = _float(row.get("x2_pu"))
        if x2 <= 0:
            continue
        sn = _float(row.get("sn_mva"))
        if sn <= 0:
            continue
        r2 = _float(row.get("r2_pu"))
        z_sys = (r2 + 1j * x2) * (sbase / sn)
        if abs(z_sys) < 1e-12:
            continue
        try:
            bus = int(row["bus"])
        except (TypeError, ValueError):
            continue
        shunts[bus] = shunts.get(bus, 0j) + (1.0 / z_sys)
    return shunts


def _invert_y(ybus):
    return np.linalg.inv(np.asarray(ybus, dtype=np.complex128))


def _bus_lookup_ppc(net, bus_idx):
    lookup = net["_pd2ppc_lookups"]["bus"]
    try:
        ppc_bus = int(lookup[int(bus_idx)])
    except (IndexError, KeyError, TypeError, ValueError):
        return None
    if ppc_bus < 0:
        return None
    return ppc_bus


def _sequence_z(ppci, shunts, net):
    """Return Z1 and Z2. Z2 is Z1 with the converter negative-sequence shunts added."""
    from pandapower.shortcircuit.impedance import _calc_ybus

    _calc_ybus(ppci)
    y1 = ppci["internal"]["Ybus"].toarray().astype(np.complex128)
    y2 = y1.copy()
    n = y2.shape[0]
    for bus, admittance in shunts.items():
        ppc_bus = _bus_lookup_ppc(net, bus)
        if ppc_bus is None or ppc_bus >= n:
            continue
        y2[ppc_bus, ppc_bus] += admittance
    return _invert_y(y1), _invert_y(y2)


def _fault_impedance_pu(vn_kv, sbase, r_ohm, x_ohm):
    if r_ohm == 0 and x_ohm == 0:
        return 0j
    if vn_kv <= 0 or sbase <= 0:
        return 0j
    base_z = (vn_kv * vn_kv) / sbase
    if base_z <= 0:
        return 0j
    return (r_ohm + 1j * x_ohm) / base_z


def _voltage_source_ikss(fault, c_factor, sbase, vn_kv, z1, z2, z0):
    """Initial current from the voltage-source network, in kA."""
    if vn_kv <= 0 or sbase <= 0:
        return None
    if fault == "2ph":
        z_old = z1 + z1
        z_new = z1 + z2
        if abs(z_old) < 1e-15 or abs(z_new) < 1e-15:
            return None
        old = abs(c_factor * sbase / (vn_kv * z_old))
        new = abs(c_factor * sbase / (vn_kv * z_new))
        return old, new
    if fault == "1ph":
        z_old = 2.0 * z1 + z0
        z_new = z1 + z2 + z0
        if abs(z_old) < 1e-15 or abs(z_new) < 1e-15:
            return None
        scale = math.sqrt(3.0) * c_factor * sbase / vn_kv
        return scale / abs(z_old), scale / abs(z_new)
    return None


def apply_negative_sequence_ikss(
    net,
    fault,
    case="max",
    lv_tol_percent=10,
    r_fault_ohm=0.0,
    x_fault_ohm=0.0,
    bus=None,
) -> None:
    """Replace the voltage-source part of bus ikss using Z2 from r2/x2.

    The current-source term already stored by pandapower is kept. Branch
    currents stay on pandapower's Z2 = Z1 solution. ip and ith on each bus
    are scaled with the ikss ratio.
    """
    if fault not in ("2ph", "1ph"):
        return
    if not hasattr(net, "res_bus_sc") or net.res_bus_sc is None or net.res_bus_sc.empty:
        return
    shunts = _negative_sequence_shunts(net)
    if not shunts:
        return

    try:
        _apply_negative_sequence_ikss(
            net, fault, case, int(lv_tol_percent), float(r_fault_ohm), float(x_fault_ohm), bus, shunts
        )
    except Exception:
        logger.exception("Negative-sequence r2/x2 correction skipped")


def _apply_negative_sequence_ikss(net, fault, case, lv_tol_percent, r_fault_ohm, x_fault_ohm, bus, shunts):
    from pandapower.auxiliary import _add_ppc_options, _add_sc_options
    from pandapower.pd2ppc_zero import _pd2ppc_zero
    from pandapower.pypower.idx_brch_sc import K_ST
    from pandapower.pypower.idx_bus import BASE_KV
    from pandapower.pypower.idx_bus_sc import C_MAX, C_MIN
    from pandapower.shortcircuit.impedance import _calc_ybus
    from pandapower.shortcircuit.ppc_conversion import (
        _create_k_updated_ppci,
        _get_is_ppci_bus,
        _init_ppc,
    )

    work = copy.deepcopy(net)
    work["_options"] = {}
    _add_ppc_options(
        work,
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
        work,
        fault=fault,
        case=case if case in ("max", "min") else "max",
        lv_tol_percent=lv_tol_percent,
        tk_s=1.0,
        topology="auto",
        r_fault_ohm=r_fault_ohm,
        x_fault_ohm=x_fault_ohm,
        kappa=False,
        ip=False,
        ith=False,
        branch_results=False,
        kappa_method="C",
        return_all_currents=False,
        inverse_y=True,
        use_pre_fault_voltage=False,
    )

    studied = list(net.res_bus_sc.index)
    if bus is not None:
        bus_list = np.atleast_1d(bus).astype(int)
        studied = [b for b in studied if int(b) in set(bus_list.tolist())]
    if not studied:
        return

    ppc, ppci = _init_ppc(work)
    ppci_bus = _get_is_ppci_bus(work, np.array(studied, dtype=int))
    if ppci_bus.size == 0:
        return
    non_ps_bus, ppci_k, ps_map = _create_k_updated_ppci(work, ppci, ppci_bus)
    variants = [(ppci_k, np.atleast_1d(non_ps_bus))]
    for ps_bus, ps_ppci in ps_map.items():
        variants.append((ps_ppci, np.array([ps_bus])))

    z0_diag = None
    if fault == "1ph":
        _ppc0, ppci0 = _pd2ppc_zero(work, ppc["branch"][:, K_ST])
        _calc_ybus(ppci0)
        z0 = _invert_y(ppci0["internal"]["Ybus"].toarray())
        z0_diag = np.diag(z0)

    sbase = _float(getattr(work, "sn_mva", 1.0), 1.0) or 1.0
    c_column = C_MIN if case == "min" else C_MAX
    # ppci bus -> (ik_old, ik_new) from the variant pandapower would use for that bus
    correction = {}
    for variant, buses in variants:
        if buses.size == 0:
            continue
        z1, z2 = _sequence_z(variant, shunts, work)
        z1_diag = np.diag(z1)
        z2_diag = np.diag(z2)
        n = z1_diag.shape[0]
        for ppc_bus in np.atleast_1d(buses):
            ppc_bus = int(ppc_bus)
            if ppc_bus < 0 or ppc_bus >= n:
                continue
            vn = _float(variant["bus"][ppc_bus, BASE_KV])
            c_factor = _float(variant["bus"][ppc_bus, c_column], 1.1 if case != "min" else 1.0)
            if c_factor <= 0:
                c_factor = 1.1 if case != "min" else 1.0
            z_fault = _fault_impedance_pu(vn, sbase, r_fault_ohm, x_fault_ohm)
            z1_b = z1_diag[ppc_bus] + z_fault
            z2_b = z2_diag[ppc_bus] + z_fault
            z0_b = 0j
            if z0_diag is not None and ppc_bus < z0_diag.shape[0]:
                z0_b = z0_diag[ppc_bus] + z_fault
            pair = _voltage_source_ikss(fault, c_factor, sbase, vn, z1_b, z2_b, z0_b)
            if pair is not None:
                correction[ppc_bus] = pair

    for pp_bus in studied:
        ppc_bus = _bus_lookup_ppc(work, pp_bus)
        if ppc_bus is None or ppc_bus not in correction:
            continue
        ik_old, ik_new = correction[ppc_bus]
        if ik_old is None or ik_new is None or not math.isfinite(ik_old) or not math.isfinite(ik_new):
            continue
        current = _float(net.res_bus_sc.at[pp_bus, "ikss_ka"], float("nan"))
        if not math.isfinite(current):
            continue
        updated = current + (ik_new - ik_old)
        if updated < 0:
            updated = 0.0
        if current > 1e-12:
            ratio = updated / current
            for column in ("ip_ka", "ith_ka"):
                if column not in net.res_bus_sc.columns:
                    continue
                peak = _float(net.res_bus_sc.at[pp_bus, column], float("nan"))
                if math.isfinite(peak):
                    net.res_bus_sc.at[pp_bus, column] = peak * ratio
        net.res_bus_sc.at[pp_bus, "ikss_ka"] = updated
