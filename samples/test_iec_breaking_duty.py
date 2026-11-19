"""IEC 60909 breaking duty: DC component, breaking current Ib, and the circuit-breaker check.

The IEC short circuit reported Ik", ip and Ith only. A breaker is chosen by what flows when its
contacts part (t_min), so the study now adds, per bus: the DC component i_DC (IEC 60909-0 4.4,
R/X from method C at the equivalent frequency for f*t), the symmetrical breaking current Ib
(IEC 60909-0 4.5: mu for generators, mu*q for motors), Ib,asym = sqrt(Ib^2 + i_DC^2) and the DC
percentage. Each circuit breaker is checked against its making current, Isc and rated DC
component (IEC 62271-100).

The ANSI study compared the first-cycle peak against the symmetrical interrupting rating when
the momentary rating was left empty (a false FAIL), and used the switch's rated current in_ka as
an interrupting rating. A blank momentary rating now gets the peak the device standard ties to
the interrupting rating, and in_ka is never used for duty.

Run with ``python samples/test_iec_breaking_duty.py``.
"""
from __future__ import annotations

import contextlib
import io
import json
import math
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandapower as pp  # noqa: E402

import ansi_shortcircuit_electrisim as ansi_sc  # noqa: E402
import iec_breaking_electrisim as brk  # noqa: E402
import pandapower_electrisim as pe  # noqa: E402

F = 50.0


def quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args, **kwargs)


def run_iec(net, **settings):
    data = {"fault_type": "3ph", "fault_location": "max", "fault_impedance": "10"}
    data.update(settings)
    out = json.loads(quiet(pe.shortcircuit, net, data, Busbars={}))
    assert not out.get("error"), out
    assert not any("could not be calculated" in w for w in out.get("warnings", [])), out.get("warnings")
    return out


def bus_row(out, name):
    return {b["name"]: b for b in out["busbars"]}[name]


def ids(net):
    for table in ("bus", "ext_grid", "line", "trafo", "gen", "motor", "switch"):
        if len(net[table]):
            net[table]["id"] = [f"{table}{i}" for i in range(len(net[table]))]
    return net


def radial():
    net = pp.create_empty_network(f_hz=F)
    hv = pp.create_bus(net, 110, name="HV")
    mv = pp.create_bus(net, 20, name="MV")
    pp.create_ext_grid(net, hv, s_sc_max_mva=3000, rx_max=0.1, s_sc_min_mva=2000, rx_min=0.1)
    pp.create_transformer_from_parameters(net, hv, mv, sn_mva=40, vn_hv_kv=110, vn_lv_kv=20, vk_percent=12,
                                          vkr_percent=0.4, pfe_kw=0, i0_percent=0, name="T1")
    return ids(net)


def test_radial_matches_hand_calculation():
    out = run_iec(radial(), t_min_ms="50")
    assert out["study_params"]["t_min_ms"] == 50.0 and out["study_params"]["frequency_hz"] == F
    for name in ("HV", "MV"):
        b = bus_row(out, name)
        xr = b["xk_ohm"] / b["rk_ohm"]  # radial: method C gives the fault-point X/R
        idc = math.sqrt(2) * b["ikss_ka"] * math.exp(-2 * math.pi * F * 0.05 / xr)
        assert abs(b["xr_dc"] - xr) < 1e-6 * xr, (name, b["xr_dc"], xr)
        assert abs(b["idc_ka"] - idc) < 1e-6 * idc, (name, b["idc_ka"], idc)
        assert abs(b["ib_ka"] - b["ikss_ka"]) < 1e-9, "no machines: Ib = Ik\""
        assert abs(b["ib_asym_ka"] - math.hypot(b["ib_ka"], idc)) < 1e-9
        assert abs(b["dc_percent"] - 100 * idc / (math.sqrt(2) * b["ib_ka"])) < 1e-9
        assert abs(b["tau_dc_ms"] - 1000 * xr / (2 * math.pi * F)) < 1e-6
    # A later contact parting leaves less DC.
    later = bus_row(run_iec(radial(), t_min_ms="100"), "MV")
    assert later["idc_ka"] < bus_row(out, "MV")["idc_ka"]
    # Unset or invalid t_min falls back to 50 ms.
    assert run_iec(radial(), t_min_ms="")["study_params"]["t_min_ms"] == 50.0
    print("PASS radial: Ib = Ik\", i_DC from the fault-point X/R")


def test_meshed_uses_equivalent_frequency_for_dc():
    """Two paths with X/R 10 and 1: the DC R/X is the parallel impedance at fc, not at 20 Hz or 50 Hz."""
    net = pp.create_empty_network(f_hz=F)
    a = pp.create_bus(net, 20, name="A")
    b = pp.create_bus(net, 20, name="B")
    pp.create_ext_grid(net, a, s_sc_max_mva=1e6, rx_max=0.1)
    pp.create_line_from_parameters(net, a, b, 1, r_ohm_per_km=0.1, x_ohm_per_km=1.0, c_nf_per_km=0, max_i_ka=1)
    pp.create_line_from_parameters(net, a, b, 1, r_ohm_per_km=1.0, x_ohm_per_km=1.0, c_nf_per_km=0, max_i_ka=1)
    ids(net)
    t_ms = 30.0  # f*t = 1.5 -> fc/f = 0.15
    out = run_iec(net, t_min_ms=str(t_ms))
    k = brk.dc_equivalent_frequency_ratio(F, t_ms / 1000)
    assert k == 0.15
    zg = 1.1 * 20 ** 2 / 1e6  # grid impedance, ohm, R/X = 0.1
    xg = zg / math.sqrt(1 + 0.01)
    z1, z2 = complex(0.1, 1.0 * k), complex(1.0, 1.0 * k)
    zc = complex(0.1 * xg, xg * k) + z1 * z2 / (z1 + z2)
    xr_hand = 1 / (zc.real / zc.imag * k)
    row = bus_row(out, "B")
    assert abs(row["xr_dc"] - xr_hand) < 1e-6 * xr_hand, (row["xr_dc"], xr_hand)
    xr_50hz = row["xk_ohm"] / row["rk_ohm"]
    assert abs(row["xr_dc"] - xr_50hz) > 0.5, "meshed: the DC X/R differs from the 50 Hz fault-point value"
    print(f"PASS meshed: DC X/R {row['xr_dc']:.3f} at fc/f = {k} (50 Hz fault point {xr_50hz:.3f})")


def test_generator_breaking_current_mu():
    """A fault at the terminals of a lone generator: Ib = mu * Ik" (IEC 60909-0 4.5)."""
    xd, sn, vn = 0.15, 50.0, 10.5
    for t in (0.02, 0.05, 0.10, 0.25):
        net = pp.create_empty_network(f_hz=F)
        g = pp.create_bus(net, vn, name="G")
        pp.create_gen(net, g, p_mw=40, vn_kv=vn, sn_mva=sn, xdss_pu=xd, rdss_ohm=0.07 * xd * vn ** 2 / sn,
                      cos_phi=0.8, slack=True)
        out = run_iec(ids(net), t_min_ms=str(1000 * t))
        row = bus_row(out, "G")
        mu = brk.mu_factor(row["ikss_ka"] / (sn / (math.sqrt(3) * vn)), t)
        assert mu < 0.9
        assert abs(row["ib_ka"] - mu * row["ikss_ka"]) < 2e-3 * row["ikss_ka"], (t, row["ib_ka"], mu * row["ikss_ka"])
    # Between the IEC curves mu is interpolated linearly in t_min; at most 1; 1 up to I"kG/IrG = 2.
    assert abs(brk.mu_factor(6, 0.075) - (brk.mu_factor(6, 0.05) + brk.mu_factor(6, 0.10)) / 2) < 1e-12
    assert brk.mu_factor(2.0, 0.1) == 1.0 and brk.mu_factor(50, 0.0) == 1.0
    assert abs(brk.mu_factor(7.25, 0.1) - (0.62 + 0.72 * math.exp(-0.32 * 7.25))) < 1e-12
    assert abs(brk.q_factor(5.0, 0.1) - (0.57 + 0.12 * math.log(5.0))) < 1e-12
    assert brk.q_factor(500.0, 0.02) == 1.0 and brk.q_factor(0.001, 0.25) == 0.0
    print("PASS generator: Ib = mu Ik\" at 20, 50, 100 and 250 ms")


def test_grid_generator_motor_formula_75():
    """Grid, generator and motor feed one 20 kV bus: Ib from the partial currents (IEC 60909-0 4.5, meshed networks)."""
    net = pp.create_empty_network(f_hz=F)
    hv, b, g, m = (pp.create_bus(net, v, name=n) for v, n in ((110, "HV"), (20, "B"), (10.5, "G"), (6, "M")))
    pp.create_ext_grid(net, hv, s_sc_max_mva=2000, rx_max=0.1)
    for lv, sn, vk, vkr, vlv in ((b, 40, 12, 0.4, 20), (g, 50, 10, 0.3, 10.5), (m, 10, 8, 0.6, 6)):
        hv_bus, vhv = (hv, 110) if lv == b else (b, 20)
        pp.create_transformer_from_parameters(net, hv_bus, lv, sn_mva=sn, vn_hv_kv=vhv, vn_lv_kv=vlv,
                                              vk_percent=vk, vkr_percent=vkr, pfe_kw=0, i0_percent=0)
    pp.create_gen(net, g, p_mw=40, vn_kv=10.5, sn_mva=50, xdss_pu=0.15, rdss_ohm=0.07 * 0.15 * 10.5 ** 2 / 50,
                  cos_phi=0.8)
    pp.create_motor(net, m, pn_mech_mw=5, cos_phi=0.88, cos_phi_n=0.88, efficiency_n_percent=95, lrc_pu=5.5,
                    rx=0.1, vn_kv=6)
    ids(net)
    t = 0.1
    row = bus_row(run_iec(net, t_min_ms="100"), "B")
    # Partial currents at the machine terminals: pandapower's own unit-transformer currents.
    import pandapower.shortcircuit as sc
    sc_net = pe.deepcopy(net)
    quiet(sc.calc_sc, sc_net, bus=1, branch_results=True)
    i_gen = float(sc_net.res_trafo_sc.ikss_lv_ka.iloc[1])
    i_mot = float(sc_net.res_trafo_sc.ikss_lv_ka.iloc[2])
    ir_gen = 50 / (math.sqrt(3) * 10.5)
    s_mot = 5 / (0.95 * 0.88)
    ir_mot = s_mot / (math.sqrt(3) * 6)
    mu_g = brk.mu_factor(i_gen / ir_gen, t)
    muq_m = brk.mu_factor(i_mot / ir_mot, t) * brk.q_factor(5, t)
    # dU"/(c Un/sqrt3) at each machine: partial current times machine reactance (generator with K_G).
    k_g = 1.1 / (1 + 0.15 * 0.6)
    du_g = i_gen * math.sqrt(3) * 0.15 * 10.5 ** 2 / 50 * k_g / (1.1 * 10.5)
    x_mot = 1 / 5.5 * 6 ** 2 / s_mot / math.sqrt(1 + 0.1 ** 2)
    du_m = i_mot * math.sqrt(3) * x_mot / (1.1 * 6)
    # IEC 60909-0 4.5 for meshed networks, the partial currents referred to 20 kV.
    ib_hand = row["ikss_ka"] - du_g * (1 - mu_g) * i_gen * 10.5 / 20 - du_m * (1 - muq_m) * i_mot * 6 / 20
    assert row["ib_ka"] < row["ikss_ka"]
    assert abs(row["ib_ka"] - ib_hand) < 2e-3 * row["ikss_ka"], (row["ib_ka"], ib_hand)
    print(f"PASS meshed-network Ib: Ib {row['ib_ka']:.3f} kA (hand {ib_hand:.3f}), Ik\" {row['ikss_ka']:.3f} kA")


def test_out_of_service_bus():
    """A machine on an out-of-service bus is not in the network; the others still decay."""
    net = pp.create_empty_network(f_hz=F)
    hv = pp.create_bus(net, 110, name="HV")
    off = pp.create_bus(net, 33, name="Off", in_service=False)
    mv = pp.create_bus(net, 20, name="MV")
    g = pp.create_bus(net, 10.5, name="G")
    pp.create_ext_grid(net, hv, s_sc_max_mva=2000, rx_max=0.1)
    pp.create_transformer_from_parameters(net, hv, mv, sn_mva=40, vn_hv_kv=110, vn_lv_kv=20, vk_percent=12,
                                          vkr_percent=0.4, pfe_kw=0, i0_percent=0)
    pp.create_transformer_from_parameters(net, mv, g, sn_mva=50, vn_hv_kv=20, vn_lv_kv=10.5, vk_percent=10,
                                          vkr_percent=0.3, pfe_kw=0, i0_percent=0)
    pp.create_gen(net, g, p_mw=40, vn_kv=10.5, sn_mva=50, xdss_pu=0.15, rdss_ohm=0.07 * 0.15 * 10.5 ** 2 / 50,
                  cos_phi=0.8)
    pp.create_motor(net, off, pn_mech_mw=5, cos_phi=0.88, cos_phi_n=0.88, efficiency_n_percent=95, lrc_pu=5.5,
                    rx=0.1, vn_kv=33)
    out = run_iec(ids(net), t_min_ms="50")
    assert bus_row(out, "Off")["ib_ka"] is None
    row = bus_row(out, "G")
    assert row["ib_ka"] < 0.9 * row["ikss_ka"], "the generator's own decay is still there"
    print("PASS out-of-service bus: its machines are left out, the rest is calculated")


def test_breaker_quantities_of_the_question():
    """The example that started this: 18.2 kA, ip 47.5 kA, X/R 17.9, contacts part at 50 ms."""
    entry = {"ikss_vs_ka": 18.2, "ikss_cs_ka": 0.0, "rx_dc": {brk.dc_equivalent_frequency_ratio(F, 0.05): 1 / 17.9},
             "ib_ka": {0.05: 18.2}}
    q = brk.breaking_quantities(18.2, entry, "3ph", F, 0.05)
    assert abs(q["dc_percent"] - 41.6) < 0.1 and abs(q["ib_asym_ka"] - 21.1) < 0.05, q
    assert abs(q["tau_dc_ms"] - 57.0) < 0.1
    import pandas as pd
    net = pp.create_empty_network(f_hz=F)
    bus = pp.create_bus(net, 20, name="B")
    line_bus = pp.create_bus(net, 20, name="L")
    li = pp.create_line_from_parameters(net, bus, line_bus, 1, 0.1, 0.1, 0, 1)
    rows = [("CB20", 20.0, None, None, None), ("CB16", 16.0, None, None, None),
            ("CB20_tau60", 20.0, None, 60.0, None), ("CB25", 25.0, None, None, None),
            ("CB_none", None, None, None, None), ("CB20_100ms", 20.0, None, None, 100.0)]
    for name, isc, mom, tau, tcp in rows:
        sw = pp.create_switch(net, bus, li, et="l", type="CB", name=name)
        for col, val in (("interrupting_rating_ka", isc), ("momentary_rating_ka", mom),
                         ("dc_time_constant_ms", tau), ("contact_parting_ms", tcp)):
            if col not in net.switch.columns:
                net.switch[col] = float("nan")
            net.switch.at[sw, col] = float("nan") if val is None else val
    net.switch["id"] = net.switch.name
    bus_values = {bus: {"ikss_ka": 18.2, "ip_ka": 47.5}}
    entry["ib_ka"][0.1] = 18.2
    entry["rx_dc"][brk.dc_equivalent_frequency_ratio(F, 0.1)] = 1 / 17.9

    def at(b, t):
        return brk.breaking_quantities(18.2, entry, "3ph", F, round(t, 6))

    duties = {d["name"]: d for d in brk.iec_breaker_duties(net, bus_values, at, F, 0.05)}
    d = duties["CB20"]
    assert d["making_rating_ka"] == 50.0 and d["making_rating_source"] == "derived" and d["making_pass"]
    assert abs(d["rated_dc_percent"] - 100 * math.exp(-50 / 45)) < 1e-9 and d["breaking_pass"]
    assert d["dc_status"] == "check" and d["asym_pass"] and d["status"] == "check", d
    assert abs(d["breaking_asym_rating_ka"] - 20 * math.sqrt(1 + 2 * math.exp(-100 / 45))) < 1e-9
    assert duties["CB16"]["status"] == "fail" and duties["CB16"]["making_pass"] is False  # 40 kA < 47.5
    assert duties["CB20_tau60"]["making_rating_ka"] == 54.0  # 2.7 x Isc for a special time constant
    assert duties["CB20_tau60"]["dc_status"] == "pass" and duties["CB20_tau60"]["status"] == "pass"
    assert duties["CB25"]["status"] == "check"  # 41.6 % DC is above the 32.9 % of any 45 ms breaker
    assert duties["CB_none"]["status"] == "not_rated" and duties["CB_none"]["ib_ka"] == 18.2
    slow = duties["CB20_100ms"]
    assert slow["t_cp_ms"] == 100.0 and slow["t_cp_source"] == "breaker" and slow["dc_percent"] < d["dc_percent"]
    assert pd.DataFrame(list(duties.values())).shape[0] == 6
    print("PASS breaker check: 18.2 kA example, 20 kA breaker making OK, DC above 45 ms rating -> CHECK")


def test_breakers_through_the_study():
    net = radial()
    mv = 1
    lv = pp.create_bus(net, 20, name="Feeder")
    li = pp.create_line_from_parameters(net, mv, lv, 1, 0.1, 0.1, 0, 1, name="L1")
    for name, isc in (("Q1", 25.0), ("Q2", 8.0)):
        sw = pp.create_switch(net, mv, li, et="l", type="CB", name=name)
        for col in ("interrupting_rating_ka", "momentary_rating_ka", "contact_parting_ms",
                    "dc_time_constant_ms", "rated_dc_percent"):
            if col not in net.switch.columns:
                net.switch[col] = float("nan")
        net.switch.at[sw, "interrupting_rating_ka"] = isc
    ids(net)
    out = run_iec(net, t_min_ms="60")
    duties = {d["name"]: d for d in out["breaker_duties"]}
    mv_row = bus_row(out, "MV")
    assert set(duties) == {"Q1", "Q2"}
    for d in duties.values():
        assert d["standard"] == "IEC 62271-100" and d["t_cp_ms"] == 60.0
        assert abs(d["ib_ka"] - mv_row["ib_ka"]) < 1e-9 and abs(d["ip_ka"] - mv_row["ip_ka"]) < 1e-9
    assert duties["Q1"]["breaking_pass"] and duties["Q2"]["breaking_pass"] is False
    assert duties["Q2"]["status"] == "fail"
    print("PASS study: each breaker checked at its bus, results in breaker_duties")


def test_ansi_blank_momentary_rating():
    """A blank momentary rating must not compare the peak against the symmetrical rating."""
    net = pp.create_empty_network(sn_mva=100, f_hz=60)
    b0 = pp.create_bus(net, vn_kv=13.8, name="HV")
    b1 = pp.create_bus(net, vn_kv=13.8, name="Feeder")
    pp.create_ext_grid(net, bus=b0, vm_pu=1.0, s_sc_max_mva=500.0, rx_max=0.05, rx_min=0.05,
                       r0x0_max=0.1, x0x_max=1.0)
    li = pp.create_line_from_parameters(net, b0, b1, 0.1, 0.01, 0.1, 0.0, 1.0, name="L1")
    for name, rating, in_ka in (("CB1", 28.5, float("nan")), ("CB_in_only", float("nan"), 1.2)):
        sw = pp.create_switch(net, bus=b0, element=li, et="l", closed=True, type="CB", name=name, in_ka=in_ka)
        for col in ("interrupting_rating_ka", "momentary_rating_ka", "contact_parting_cycles"):
            if col not in net.switch.columns:
                net.switch[col] = float("nan")
        net.switch.at[sw, "interrupting_rating_ka"] = rating
    out = json.loads(quiet(ansi_sc.shortcircuit_ansi, net, {
        "fault_type": "3ph", "frequency_hz": 60, "prefault_v_pu": 1.0, "contact_parting_cycles": 3}))
    duties = {d["name"]: d for d in out["device_duties"]}
    d = duties["CB1"]
    assert abs(d["momentary_rating_ka"] - 2.6 * 28.5) < 1e-9 and d["momentary_rating_source"] == "derived", d
    assert d["duty_momentary_ka"] > 28.5, "the peak is above the symmetrical rating (the old false FAIL)"
    assert d["momentary_pass"] is True, d
    assert duties["CB_in_only"]["interrupting_rating_ka"] is None, "in_ka is a rated current, not a duty rating"
    assert duties["CB_in_only"]["interrupting_pass"] is None and duties["CB_in_only"]["momentary_pass"] is None
    assert ansi_sc.close_latch_factor("hv_c37_010", 50) == 2.5
    assert ansi_sc.close_latch_factor("generator_c37_013", 60) == 2.74
    assert abs(ansi_sc.close_latch_factor("lv_c37_013", 60) - math.sqrt(2) * (1 + math.exp(-math.pi / 6.6))) < 1e-12
    print("PASS ANSI: blank momentary rating derived (2.6 x Isc), in_ka not used")


def main() -> None:
    test_radial_matches_hand_calculation()
    test_meshed_uses_equivalent_frequency_for_dc()
    test_generator_breaking_current_mu()
    test_grid_generator_motor_formula_75()
    test_out_of_service_bus()
    test_breaker_quantities_of_the_question()
    test_breakers_through_the_study()
    test_ansi_blank_momentary_rating()
    print("IEC breaking duty OK")


if __name__ == "__main__":
    main()
