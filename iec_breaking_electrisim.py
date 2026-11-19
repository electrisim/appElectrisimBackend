# -*- coding: utf-8 -*-
"""
Breaking duty for the IEC 60909 short circuit, and the IEC 62271-100 circuit-breaker check.

pandapower's calc_sc gives Ik", ip and Ith. A circuit breaker is also sized by what flows
at the instant its contacts part, t_min (relay time plus the breaker's minimum opening time):

* the DC component, IEC 60909-0 4.4:
      i_DC = sqrt(2) * Ik" * exp(-2 pi f t R/X)
  R/X comes from method C: the network is solved at an equivalent frequency fc, with
  fc/f = 0.27, 0.15, 0.092 or 0.055 for f*t below 1, 2.5, 5 or 12.5. The peak factor kappa uses
  fc = 20 Hz instead, so in a meshed network the DC decay is not the one behind kappa. In a
  radial network both give the X/R of the fault point. Converters (current sources) carry no
  DC component.
* the symmetrical breaking current Ib, IEC 60909-0 4.5. Three-phase faults use the formula for
  meshed networks, which also covers a single-fed fault:
      Ib = Ik" - sum_i dU"_Gi/(c Un/sqrt3) (1 - mu_i) I"_kGi - sum_j dU"_Mj/(c Un/sqrt3) (1 - mu_j q_j) I"_kMj
  over the synchronous machines i and asynchronous machines j. The partial currents and the
  voltages at the machine terminals come from the same impedance matrix as Ik". mu depends on
  I"_kG / I_rG and t_min; q on the rated power per pole pair (one pole pair is assumed, the
  largest q). External grids, converters and doubly fed generators keep their initial current.
  For unbalanced faults IEC 60909-0 takes Ib = Ik".

From these: the asymmetrical breaking current Ib,asym = sqrt(Ib^2 + i_DC^2) and the DC
percentage p = i_DC / (sqrt(2) Ib), which iec_breaker_duties compares with each circuit
breaker's rated making current, short-circuit breaking current Isc and rated DC component.

The module only needs numpy and pandapower, so the Python export carries a copy of it.
"""
import math
from copy import deepcopy

import numpy as np

from pandapower.auxiliary import _add_ppc_options, _add_sc_options
from pandapower.pypower.idx_brch import BR_X
from pandapower.pypower.idx_bus import BASE_KV, BS, GS
from pandapower.pypower.idx_bus_sc import (
    BS_GEN, C_MAX, C_MIN, GS_GEN, IKSS1, IKSS2, K_G, K_SG, R_EQUIV, X_EQUIV,
)
from pandapower.results import init_results
from pandapower.shortcircuit.currents import _calc_ikss
from pandapower.shortcircuit.impedance import _calc_rx, _calc_ybus, _calc_zbus
from pandapower.shortcircuit.ppc_conversion import _create_k_updated_ppci, _get_is_ppci_bus, _init_ppc
from scipy.sparse.linalg import splu

try:
    from pandapower.pf.makeYbus_numba import makeYbus
except ImportError:  # pragma: no cover - numba is optional in pandapower
    from pandapower.pypower.makeYbus import makeYbus

SQRT2 = math.sqrt(2.0)
SQRT3 = math.sqrt(3.0)

#: IEC 60909-0 4.4: fc/f for the DC component, by the product f*t (upper bounds).
DC_FC_TABLE = ((1.0, 0.27), (2.5, 0.15), (5.0, 0.092), (12.5, 0.055))

#: IEC 60909-0 4.5: mu = a + b exp(-c I"kG/IrG) at t_min = 0.02, 0.05, 0.10 and >= 0.25 s.
MU_CURVES = ((0.02, 0.84, 0.26, 0.26), (0.05, 0.71, 0.51, 0.30),
             (0.10, 0.62, 0.72, 0.32), (0.25, 0.56, 0.94, 0.38))

#: IEC 60909-0 4.5: q = a + b ln(m), m = rated active power per pole pair in MW.
Q_CURVES = ((0.02, 1.03, 0.12), (0.05, 0.79, 0.12), (0.10, 0.57, 0.12), (0.25, 0.26, 0.10))

#: IEC 62271-100: rated DC time constant of a standard circuit breaker, and the special cases.
STANDARD_DC_TIME_CONSTANT_MS = 45.0
SPECIAL_DC_TIME_CONSTANTS_MS = (60.0, 75.0, 120.0)


def dc_equivalent_frequency_ratio(f_hz, t_s):
    """fc/f of method C for the DC component at time t_s (IEC 60909-0 4.4)."""
    ft = float(f_hz) * max(float(t_s), 0.0)
    for limit, ratio in DC_FC_TABLE:
        if ft < limit:
            return ratio
    return DC_FC_TABLE[-1][1]


def _interpolate_curves(curves, t_s, value_at):
    """A factor of the IEC curves at t_s.

    The listed curves are used as they are; between two of them the value is interpolated
    linearly in t_min, beyond 0.25 s the 0.25 s curve applies, and below 0.02 s the value runs
    linearly to 1 at t = 0, where nothing has decayed yet.
    """
    t = max(float(t_s), 0.0)
    if t >= curves[-1][0]:
        return value_at(curves[-1])
    if t <= curves[0][0]:
        first = value_at(curves[0])
        return 1.0 + (first - 1.0) * t / curves[0][0]
    for lo, hi in zip(curves, curves[1:]):
        if lo[0] <= t <= hi[0]:
            w = (t - lo[0]) / (hi[0] - lo[0])
            return value_at(lo) + (value_at(hi) - value_at(lo)) * w
    return value_at(curves[-1])


def mu_factor(ikg_over_irg, t_s):
    """IEC 60909-0 decay factor mu of a machine's AC current at t_min; 1 up to I"kG/IrG = 2."""
    ratio = float(ikg_over_irg)
    if not math.isfinite(ratio) or ratio <= 2.0:
        return 1.0
    mu = _interpolate_curves(MU_CURVES, t_s, lambda c: c[1] + c[2] * math.exp(-c[3] * ratio))
    return min(1.0, max(0.0, mu))


def mu_factors(ratios, t_s):
    """mu_factor for an array of I"kG/IrG values."""
    r = np.asarray(ratios, dtype=float).ravel()
    out = np.ones_like(r)
    decays = np.isfinite(r) & (r > 2.0)
    if np.any(decays):
        rd = r[decays]
        mu = _interpolate_curves(MU_CURVES, t_s, lambda c: c[1] + c[2] * np.exp(-c[3] * rd))
        out[decays] = np.clip(mu, 0.0, 1.0)
    return out


def q_factor(m_mw, t_s):
    """IEC 60909-0 factor q of an asynchronous machine with rated power m_mw per pole pair."""
    m = float(m_mw)
    if not math.isfinite(m) or m <= 0.0:
        return 1.0
    q = _interpolate_curves(Q_CURVES, t_s, lambda c: c[1] + c[2] * math.log(m))
    return min(1.0, max(0.0, q))


def _as_float(value, default=float("nan")):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _sc_options(net, fault, case, lv_tol_percent, r_fault_ohm, x_fault_ohm):
    """The options pandapower's calc_sc sets for this study."""
    net["_options"] = {}
    _add_ppc_options(net, calculate_voltage_angles=False, trafo_model="pi", check_connectivity=True,
                     mode="sc", switch_rx_ratio=2, init_vm_pu="flat", init_va_degree="flat",
                     enforce_q_lims=False, recycle=None)
    _add_sc_options(net, fault=fault, case=case, lv_tol_percent=lv_tol_percent, tk_s=1.0,
                    topology="auto", r_fault_ohm=r_fault_ohm, x_fault_ohm=x_fault_ohm, kappa=False,
                    ip=False, ith=False, branch_results=False, kappa_method="C",
                    return_all_currents=False, inverse_y=True, use_pre_fault_voltage=False)
    init_results(net, "sc")


def _machine_groups(net, ppci, ps_bus=None):
    """Machines whose AC current decays, one group per ppci bus and kind.

    Each group: (ppci bus, admittance in pu on baseMVA, rated current kA, kind, m in MW).
    ``kind`` is "sync" (generators) or "async" (motors and induction generators).
    The admittances are the ones pandapower put into this ppci, including K_G / K_SG.
    pandapower sets, not adds, the shunt of a bus with an induction or doubly fed
    generator, so other machines on such a bus are not in its network; they are left out here.
    """
    lookup = net._pd2ppc_lookups["bus"]
    in_service_buses = set(int(b) for b in net._is_elements_final["bus_is_idx"])
    n_ppci = ppci["bus"].shape[0]

    def ppci_bus(pd_bus):
        """The machine's bus in this ppci, or None when its bus is not part of the solved network."""
        pd_bus = int(pd_bus)
        if pd_bus not in in_service_buses:
            return None
        b = int(lookup[pd_bus])
        return b if 0 <= b < n_ppci else None

    base_mva = float(ppci["baseMVA"])
    groups = []
    induction_buses = set()
    sgen = net.sgen
    if len(sgen) and "generator_type" in sgen.columns:
        live = sgen[sgen.in_service.astype(bool)]
        for gtype in ("async", "async_doubly_fed"):
            for pd_bus in live.loc[live.generator_type == gtype, "bus"].values:
                b = ppci_bus(pd_bus)
                if b is not None:
                    induction_buses.add(b)
        asyn = live[live.generator_type == "async"]
        for _, row in asyn.iterrows():
            b = ppci_bus(row.bus)
            if b is None:
                continue
            vn = float(ppci["bus"][b, BASE_KV])
            sn = _as_float(row.get("sn_mva"), 0.0)
            lrc = _as_float(row.get("lrc_pu"), 0.0)
            rx = _as_float(row.get("rx"), 0.0)
            if sn <= 0 or lrc <= 0:
                continue
            z_pu = 1.0 / lrc * vn ** 2 / sn / vn ** 2 * base_mva  # pandapower _add_sgen_sc_z
            x = z_pu / math.sqrt(1.0 + rx ** 2)
            groups.append((b, 1.0 / complex(rx * x, x), sn / (SQRT3 * vn), "async", sn))

    gen_table = net.gen
    if len(gen_table):
        is_gen = net._is_elements_final["gen"] if "gen" in net._is_elements_final else gen_table.in_service.values
        gens = gen_table[np.asarray(is_gen, dtype=bool)]
        rated = {}
        for _, row in gens.iterrows():
            b = ppci_bus(row.bus)
            if b is None:
                continue
            rated[b] = rated.get(b, 0.0) + _as_float(row.sn_mva, 0.0) / (SQRT3 * _as_float(row.vn_kv, 1.0))
        for b, ir_ka in rated.items():
            if b in induction_buses or ir_ka <= 0:
                continue
            y_mva = complex(ppci["bus"][b, GS_GEN], ppci["bus"][b, BS_GEN])
            if not np.isfinite(y_mva) or y_mva == 0:
                continue
            k_sg = ppci["bus"][b, K_SG]
            k = ppci["bus"][b, K_G] if (np.isnan(k_sg) or b == ps_bus) else k_sg
            if not np.isfinite(k) or k <= 0:
                continue
            groups.append((b, y_mva / k / base_mva, ir_ka, "sync", float("nan")))

    if net._options.get("case") == "max" and len(net.motor):
        live = net.motor[net.motor.in_service.astype(bool)]
        for _, row in live.iterrows():
            b = ppci_bus(row.bus)
            if b is None or b in induction_buses:
                continue
            p_mech = _as_float(row.pn_mech_mw, 0.0)
            eff = _as_float(row.efficiency_n_percent, 0.0) / 100.0
            cos_phi = _as_float(row.cos_phi_n, 0.0)
            lrc = _as_float(row.lrc_pu, 0.0)
            vn_motor = _as_float(row.vn_kv, 0.0)
            if min(p_mech, eff, cos_phi, lrc, vn_motor) <= 0:
                continue
            vn = float(ppci["bus"][b, BASE_KV])
            s_motor = p_mech / (eff * cos_phi)
            z_pu = 1.0 / lrc * vn_motor ** 2 / s_motor / vn ** 2 * base_mva  # pandapower motor model
            rx = _as_float(row.rx, 0.0)
            x = z_pu / math.sqrt(1.0 + rx ** 2)
            groups.append((b, 1.0 / complex(rx * x, x), s_motor / (SQRT3 * vn_motor), "async", p_mech))
    return groups


def _method_c_rx(ppci, buses, fc_ratio, z_fault_pu):
    """R/X at ``buses`` with the network solved at fc = fc_ratio * f (IEC 60909-0 method C).

    Series reactances and inductive shunts scale with fc/f, capacitive shunts with f/fc.
    Returns R/X referred to the system frequency: (Rc/Xc) * (fc/f).
    """
    bus = ppci["bus"].copy()
    branch = ppci["branch"].copy()
    branch[:, BR_X] *= fc_ratio
    y = bus[:, GS] + 1j * bus[:, BS]
    nz = np.abs(y) > 1e-12
    if np.any(nz):
        z = 1.0 / y[nz]
        x = np.where(z.imag >= 0, z.imag * fc_ratio, z.imag / fc_ratio)
        y_c = 1.0 / (z.real + 1j * x)
        bus[nz, GS] = y_c.real
        bus[nz, BS] = y_c.imag
    ybus = makeYbus(ppci["baseMVA"], bus, branch)[0]
    lu = splu(ybus.tocsc())
    n = ybus.shape[0]
    zc = np.empty(len(buses), dtype=complex)
    for start in range(0, len(buses), 256):
        chunk = np.asarray(buses[start:start + 256], dtype=np.int64)
        rhs = np.zeros((n, len(chunk)), dtype=complex)
        rhs[chunk, np.arange(len(chunk))] = 1.0
        sol = lu.solve(rhs)
        zc[start:start + len(chunk)] = sol[chunk, np.arange(len(chunk))]
    zf = z_fault_pu.real + 1j * z_fault_pu.imag * fc_ratio
    zc = zc + zf
    with np.errstate(divide="ignore", invalid="ignore"):
        rx = np.where(zc.imag > 1e-15, zc.real / zc.imag * fc_ratio, np.inf)
    return rx


def _ppci_results(net, ppci, buses, times_s, f_hz, case, ps_bus=None, with_machines=True):
    """Ik" parts, method-C R/X for each DC frequency and Ib at each time, for ppci ``buses``."""
    _calc_ybus(ppci)
    _calc_zbus(net, ppci)
    _calc_rx(net, ppci, buses)
    _calc_ikss(net, ppci, buses)
    base_mva = float(ppci["baseMVA"])
    base_kv = ppci["bus"][buses, BASE_KV]
    i_base_ka = base_mva / (SQRT3 * base_kv)
    ikss_vs = np.nan_to_num(ppci["bus"][buses, IKSS1].astype(float))
    ikss_cs = np.nan_to_num(ppci["bus"][buses, IKSS2].astype(float))
    z_kk = ppci["bus"][buses, R_EQUIV] + 1j * ppci["bus"][buses, X_EQUIV]
    z_fault = z_kk - np.diag(ppci["internal"]["Zbus"])[buses]
    c = ppci["bus"][buses, C_MAX if case == "max" else C_MIN]

    rx_by_ratio = {}
    for t in times_s:
        ratio = dc_equivalent_frequency_ratio(f_hz, t)
        if ratio not in rx_by_ratio:
            rx_by_ratio[ratio] = _method_c_rx(ppci, buses, ratio, z_fault)

    reduction = {t: np.zeros(len(buses)) for t in times_s}
    if with_machines:
        zbus = ppci["internal"]["Zbus"]
        for g, y_pu, ir_ka, kind, m_mw in _machine_groups(net, ppci, ps_bus=ps_bus):
            # Terminal voltage of the machine during the fault, as a fraction of c Un/sqrt3 (pu).
            v_rel = np.abs(zbus[g, buses] / z_kk)
            i_pu = np.abs(y_pu) * c * v_rel
            i_ka = i_pu * base_mva / (SQRT3 * float(ppci["bus"][g, BASE_KV]))
            x_pu = abs((1.0 / y_pu).imag)
            du_rel = i_pu * x_pu / c  # dU"/(c Un/sqrt3): voltage across the machine reactance
            ratio = i_ka / ir_ka
            for t in times_s:
                keep = mu_factors(ratio, t)
                if kind == "async":
                    keep = keep * q_factor(m_mw, t)
                reduction[t] += du_rel * (1.0 - keep) * i_pu * i_base_ka
    out = []
    for pos, b in enumerate(buses):
        entry = {"ppci_bus": int(b), "ikss_vs_ka": float(ikss_vs[pos]), "ikss_cs_ka": float(ikss_cs[pos]),
                 "rx_dc": {}, "ib_ka": {}}
        for ratio, rx in rx_by_ratio.items():
            entry["rx_dc"][ratio] = float(rx[pos])
        for t in times_s:
            entry["ib_ka"][t] = float(max(ikss_vs[pos] - reduction[t][pos], 0.0) + ikss_cs[pos])
        out.append(entry)
    return out


def iec_breaking_by_bus(net, fault="3ph", case="max", bus=None, lv_tol_percent=10, r_fault_ohm=0.0,
                        x_fault_ohm=0.0, times_s=(0.05,)):
    """Per pandapower bus: voltage-source and converter parts of Ik", DC R/X and Ib at each time.

    Runs on a copy of ``net`` (which must be ready for calc_sc, as Electrisim prepares it), with
    the same options calc_sc uses. ``fault`` "1ph" is solved as "3ph": only R/X is used then.
    Returns {bus index: {"ikss_vs_ka", "ikss_cs_ka", "rx_dc": {fc/f: R/X}, "ib_ka": {t: Ib}}}.
    """
    times = tuple(sorted({round(max(float(t), 0.0), 6) for t in times_s}))
    work = deepcopy(net)
    solve_fault = fault if fault in ("3ph", "2ph") else "3ph"
    _sc_options(work, solve_fault, case, lv_tol_percent, r_fault_ohm, x_fault_ohm)
    _, ppci = _init_ppc(work)
    if bus is None:
        pd_buses = work.bus.index.values
    else:
        pd_buses = np.array([bus]).ravel()
    pd_buses = np.asarray(pd_buses, dtype=np.int64)
    ppci_bus = _get_is_ppci_bus(work, pd_buses)
    if ppci_bus.size == 0:
        return {}
    base_buses, base_ppci, ps_ppcis = _create_k_updated_ppci(work, ppci, ppci_bus=ppci_bus)
    f_hz = float(getattr(work, "f_hz", 50.0) or 50.0)
    with_machines = solve_fault == "3ph"
    by_ppci = {}
    if len(base_buses):
        for entry in _ppci_results(work, base_ppci, base_buses, times, f_hz, case, None, with_machines):
            by_ppci[entry["ppci_bus"]] = entry
    for ps_bus, ps_ppci in ps_ppcis.items():
        for entry in _ppci_results(work, ps_ppci, np.array([ps_bus]), times, f_hz, case, ps_bus, with_machines):
            by_ppci[entry["ppci_bus"]] = entry
    lookup = work._pd2ppc_lookups["bus"]
    in_service = set(int(b) for b in work._is_elements_final["bus_is_idx"])
    out = {}
    for b in pd_buses:
        if int(b) not in in_service:
            continue
        entry = by_ppci.get(int(lookup[int(b)]))
        if entry is not None:
            out[int(b)] = entry
    return out


def breaking_quantities(ikss_ka, entry, fault, f_hz, t_s):
    """Ib, i_DC, Ib,asym, DC percentage and the DC X/R and time constant at t_s for one bus."""
    ratio = dc_equivalent_frequency_ratio(f_hz, t_s)
    rx = entry["rx_dc"].get(ratio, float("inf"))
    total = entry["ikss_vs_ka"] + entry["ikss_cs_ka"]
    if fault == "3ph":
        # Scale with the final Ik" (Electrisim may correct it after calc_sc).
        scale = ikss_ka / total if total > 1e-12 else 0.0
        ib = entry["ib_ka"].get(t_s, total) * scale
        dc_base = entry["ikss_vs_ka"] * scale
    elif fault == "2ph":
        ib = ikss_ka
        dc_base = ikss_ka * (entry["ikss_vs_ka"] / total if total > 1e-12 else 1.0)
    else:
        # As for ip of a single-phase fault: the three-phase R/X on the whole Ik1".
        ib = ikss_ka
        dc_base = ikss_ka
    decay = math.exp(-2.0 * math.pi * f_hz * t_s * rx) if math.isfinite(rx) else 0.0
    idc = SQRT2 * dc_base * decay
    xr = 1.0 / rx if rx > 1e-12 else float("inf")
    return {
        "ib_ka": ib,
        "idc_ka": idc,
        "ib_asym_ka": math.sqrt(ib ** 2 + idc ** 2),
        "dc_percent": 100.0 * idc / (SQRT2 * ib) if ib > 1e-12 else None,
        "xr_dc": xr if math.isfinite(xr) else None,
        "tau_dc_ms": 1000.0 * xr / (2.0 * math.pi * f_hz) if math.isfinite(xr) else None,
        "t_ms": 1000.0 * t_s,
    }


def rated_making_factor(f_hz, tau_ms):
    """IEC 62271-100 rated making current / Isc: 2.5 (50 Hz) or 2.6 (60 Hz) at 45 ms, else 2.7."""
    if tau_ms is not None and tau_ms > STANDARD_DC_TIME_CONSTANT_MS + 1e-9:
        return 2.7
    return 2.6 if float(f_hz) >= 55.0 else 2.5


def iec_breaker_duties(net, bus_values, breaking_at, f_hz, t_min_s):
    """IEC 62271-100 making and breaking check of each circuit breaker.

    ``bus_values`` maps pandapower bus -> {"ikss_ka", "ip_ka"}; ``breaking_at(bus, t_s)`` returns
    breaking_quantities for that bus and time. A breaker is checked against the fault at its
    bus (for a bus coupler, the larger of its two buses): the full bus current, which is the
    conservative duty. Its contacts part at contact_parting_ms, else at the study's t_min.
    Ratings: interrupting_rating_ka = Isc; momentary_rating_ka = rated making current (peak),
    derived from Isc when empty; dc_time_constant_ms (45 ms when empty); rated_dc_percent,
    derived as 100 exp(-t/tau) at the contact parting time when empty.
    """
    sw = getattr(net, "switch", None)
    if sw is None or sw.empty:
        return []
    duties = []
    for idx, row in sw.iterrows():
        sw_type = str(row.get("type", "") or "").upper()
        isc = _as_float(row.get("interrupting_rating_ka"), 0.0)
        if sw_type != "CB" and isc <= 0:
            continue
        candidates = [int(row.bus)]
        if str(row.get("et", "")) == "b":
            candidates.append(int(row.element))
        candidates = [b for b in candidates if b in bus_values and bus_values[b].get("ikss_ka") is not None]
        if not candidates:
            continue
        bus = max(candidates, key=lambda b: bus_values[b]["ikss_ka"])
        t_ms = _as_float(row.get("contact_parting_ms"), 0.0)
        t_s = t_ms / 1000.0 if t_ms > 0 else float(t_min_s)
        q = breaking_at(bus, t_s)
        if q is None:
            continue
        ip = bus_values[bus].get("ip_ka")
        tau_ms = _as_float(row.get("dc_time_constant_ms"), 0.0)
        tau_ms = tau_ms if tau_ms > 0 else STANDARD_DC_TIME_CONSTANT_MS
        making = _as_float(row.get("momentary_rating_ka"), 0.0)
        making_source = "entered"
        if making <= 0 and isc > 0:
            making = rated_making_factor(f_hz, tau_ms) * isc
            making_source = "derived"
        dc_rated = _as_float(row.get("rated_dc_percent"), 0.0)
        dc_rated_source = "entered"
        if dc_rated <= 0:
            dc_rated = 100.0 * math.exp(-1000.0 * t_s / tau_ms)
            dc_rated_source = "derived"
        isc_asym = isc * math.sqrt(1.0 + 2.0 * (dc_rated / 100.0) ** 2) if isc > 0 else None

        making_pass = (ip <= making * 1.0001) if (making > 0 and ip is not None) else None
        breaking_pass = (q["ib_ka"] <= isc * 1.0001) if isc > 0 else None
        asym_pass = (q["ib_asym_ka"] <= isc_asym * 1.0001) if isc_asym else None
        dc_status = None
        if isc > 0 and q["dc_percent"] is not None:
            if q["dc_percent"] <= dc_rated + 1e-6:
                dc_status = "pass"
            elif asym_pass:
                dc_status = "check"
            else:
                dc_status = "fail"
        statuses = [making_pass, breaking_pass]
        if any(s is False for s in statuses) or dc_status == "fail":
            overall = "fail"
        elif dc_status == "check":
            overall = "check"
        elif any(s is True for s in statuses):
            overall = "pass"
        else:
            overall = "not_rated"
        duties.append({
            "name": row.get("name"),
            "id": row.get("id", row.get("name", str(idx))),
            "bus": net.bus.at[bus, "name"] if "name" in net.bus.columns else str(bus),
            "bus_id": net.bus.at[bus, "id"] if "id" in net.bus.columns else None,
            "vn_kv": float(net.bus.at[bus, "vn_kv"]),
            "closed": bool(row.get("closed", True)),
            "standard": "IEC 62271-100",
            "t_cp_ms": 1000.0 * t_s,
            "t_cp_source": "breaker" if t_ms > 0 else "study",
            "ikss_ka": bus_values[bus]["ikss_ka"],
            "ip_ka": ip,
            "ib_ka": q["ib_ka"],
            "idc_ka": q["idc_ka"],
            "dc_percent": q["dc_percent"],
            "ib_asym_ka": q["ib_asym_ka"],
            "xr_dc": q["xr_dc"],
            "tau_dc_ms": q["tau_dc_ms"],
            "breaking_rating_ka": isc if isc > 0 else None,
            "making_rating_ka": making if making > 0 else None,
            "making_rating_source": making_source if making > 0 else None,
            "dc_time_constant_ms": tau_ms,
            "rated_dc_percent": dc_rated if isc > 0 else None,
            "rated_dc_percent_source": dc_rated_source if isc > 0 else None,
            "breaking_asym_rating_ka": isc_asym,
            "making_pass": making_pass,
            "breaking_pass": breaking_pass,
            "dc_status": dc_status,
            "asym_pass": asym_pass,
            "making_margin_ka": (making - ip) if (making > 0 and ip is not None) else None,
            "breaking_margin_ka": (isc - q["ib_ka"]) if isc > 0 else None,
            "status": overall,
        })
    return duties


def electrisim_iec_breaking(net, fault="3ph", case="max", bus=None, lv_tol_percent=10, r_fault_ohm=0.0,
                            x_fault_ohm=0.0, t_min_s=0.05):
    """Add Ib, i_DC, Ib,asym and the DC percentage at t_min to net.res_bus_sc; check breakers.

    Electrisim runs this after calc_sc and its own corrections of Ik", ip and Ith, so the
    columns follow the final Ik". New res_bus_sc columns: ib_ka, idc_ka, ib_asym_ka,
    dc_percent, xr_dc, tau_dc_ms. Returns the list of IEC 62271-100 breaker duties.
    """
    res = net.res_bus_sc
    if res is None or res.empty:
        return []
    f_hz = float(getattr(net, "f_hz", 50.0) or 50.0)
    t_min_s = max(float(t_min_s), 0.0)
    times = {round(t_min_s, 6)}
    sw = getattr(net, "switch", None)
    if sw is not None and not sw.empty and "contact_parting_ms" in sw.columns:
        for value in sw["contact_parting_ms"].values:
            v = _as_float(value, 0.0)
            if v > 0:
                times.add(round(v / 1000.0, 6))
    studied = [int(b) for b in res.index[res["ikss_ka"].notna()]]
    by_bus = iec_breaking_by_bus(net, fault=fault, case=case, bus=studied if bus is not None else None,
                                 lv_tol_percent=lv_tol_percent, r_fault_ohm=r_fault_ohm,
                                 x_fault_ohm=x_fault_ohm, times_s=sorted(times))

    def breaking_at(b, t_s):
        entry = by_bus.get(int(b))
        ik = _as_float(res.at[b, "ikss_ka"]) if b in res.index else float("nan")
        if entry is None or not math.isfinite(ik):
            return None
        return breaking_quantities(ik, entry, fault, f_hz, round(t_s, 6))

    columns = ("ib_ka", "idc_ka", "ib_asym_ka", "dc_percent", "xr_dc", "tau_dc_ms")
    values = {c: [] for c in columns}
    for b in res.index:
        q = breaking_at(b, t_min_s)
        for c in columns:
            values[c].append(np.nan if q is None or q[c] is None else q[c])
    for c in columns:
        res[c] = values[c]

    bus_values = {}
    for b in res.index:
        ik = _as_float(res.at[b, "ikss_ka"])
        if math.isfinite(ik):
            ip = _as_float(res.at[b, "ip_ka"]) if "ip_ka" in res.columns else float("nan")
            bus_values[int(b)] = {"ikss_ka": ik, "ip_ka": ip if math.isfinite(ip) else None}
    return iec_breaker_duties(net, bus_values, breaking_at, f_hz, t_min_s)
