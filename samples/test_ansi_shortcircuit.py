#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Regression tests for the ANSI/IEEE C37 short-circuit engine.

The network solution is checked against closed-form hand calculations rather
than loose bounds: an earlier revision returned 1.089 kA where the correct
answer was 20.92 kA and still passed a "> 0.5 kA" style assertion.

Run from appElectrisimBackend:
  python samples/test_ansi_shortcircuit.py
"""
from __future__ import annotations

import json
import math
import os
import sys

import pandapower as pp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ansi_shortcircuit_electrisim as ansi_sc

PARAMS = {"fault_type": "3ph", "frequency_hz": 60,
          "prefault_v_pu": 1.0, "contact_parting_cycles": 3}


def _run(net, **overrides):
    params = dict(PARAMS)
    params.update(overrides)
    return json.loads(ansi_sc.shortcircuit_ansi(net, params))


def _by_name(rows):
    return {r["name"]: r for r in rows}


def build_radial_test_net():
    """13.8 kV utility -> 480 V via transformer; motor on LV bus."""
    net = pp.create_empty_network(sn_mva=100, f_hz=60)
    hv = pp.create_bus(net, vn_kv=13.8, name="HV_Bus")
    lv = pp.create_bus(net, vn_kv=0.48, name="LV_Bus")
    pp.create_ext_grid(net, bus=hv, vm_pu=1.0, s_sc_max_mva=500.0,
                       rx_max=0.1, rx_min=0.1)
    pp.create_transformer_from_parameters(
        net, hv_bus=hv, lv_bus=lv, sn_mva=2.5, vn_hv_kv=13.8, vn_lv_kv=0.48,
        vk_percent=5.75, vkr_percent=1.0, pfe_kw=0.0, i0_percent=0.0, name="T1")
    pp.create_motor(
        net, bus=lv, pn_mech_mw=0.5, cos_phi=0.85, cos_phi_n=0.85,
        efficiency_n_percent=92.0, lrc_pu=6.0, rx=0.15,
        vn_kv=0.48, name="M1")
    return net


def test_source_only_exact():
    """Single ext grid: I = V/(sqrt(3)*|Z|) and X/R = 1/rx_max, exactly."""
    net = pp.create_empty_network(sn_mva=100, f_hz=60)
    pp.create_bus(net, vn_kv=13.8, name="B1")
    pp.create_ext_grid(net, bus=0, vm_pu=1.0, s_sc_max_mva=500.0,
                       rx_max=0.1, rx_min=0.1)

    z = 13.8 ** 2 / 500.0
    i_hand = 13.8 / (math.sqrt(3) * z)
    row = _by_name(_run(net)["busbars"])["B1"]

    assert abs(row["i_first_sym_ka"] / i_hand - 1) < 1e-3, \
        f"I={row['i_first_sym_ka']} expected {i_hand}"
    assert abs(row["xr_first"] - 10.0) < 0.05, f"X/R={row['xr_first']} expected 10"
    print(f"PASS source only: I={row['i_first_sym_ka']:.4f} kA "
          f"(hand {i_hand:.4f}), X/R={row['xr_first']:.3f}")


def test_series_line_exact():
    """Downstream of a line, compare to the complex series impedance."""
    net = pp.create_empty_network(sn_mva=100, f_hz=60)
    b1 = pp.create_bus(net, vn_kv=20.0, name="B1")
    b2 = pp.create_bus(net, vn_kv=20.0, name="B2")
    pp.create_ext_grid(net, bus=b1, vm_pu=1.0, s_sc_max_mva=400.0,
                       rx_max=0.1, rx_min=0.1)
    pp.create_line_from_parameters(net, from_bus=b1, to_bus=b2, length_km=5.0,
                                   r_ohm_per_km=0.15, x_ohm_per_km=0.35,
                                   c_nf_per_km=0.0, max_i_ka=0.5, name="L1")

    vn, s_sc, rx = 20.0, 400.0, 0.1
    x_src = (vn * vn / s_sc) / math.sqrt(1.0 + rx * rx)
    z_src = complex(rx * x_src, x_src)
    z_tot = z_src + complex(0.15 * 5.0, 0.35 * 5.0)

    rows = _by_name(_run(net)["busbars"])
    for name, z in (("B1", z_src), ("B2", z_tot)):
        i_hand = vn / (math.sqrt(3) * abs(z))
        xr_hand = z.imag / z.real
        got = rows[name]
        assert abs(got["i_first_sym_ka"] / i_hand - 1) < 5e-3, \
            f"{name}: I={got['i_first_sym_ka']} expected {i_hand}"
        assert abs(got["xr_first"] / xr_hand - 1) < 5e-3, \
            f"{name}: X/R={got['xr_first']} expected {xr_hand}"
    print(f"PASS series line: B2 I={rows['B2']['i_first_sym_ka']:.4f} kA, "
          f"X/R={rows['B2']['xr_first']:.3f}")


def test_transformer_magnitude():
    """LV bus behind a 2.5 MVA 5.75 % transformer, within 5 % of closed form."""
    net = pp.create_empty_network(sn_mva=100, f_hz=60)
    hv = pp.create_bus(net, vn_kv=13.8, name="HV")
    lv = pp.create_bus(net, vn_kv=0.48, name="LV")
    pp.create_ext_grid(net, bus=hv, vm_pu=1.0, s_sc_max_mva=500.0,
                       rx_max=0.1, rx_min=0.1)
    pp.create_transformer_from_parameters(
        net, hv_bus=hv, lv_bus=lv, sn_mva=2.5, vn_hv_kv=13.8, vn_lv_kv=0.48,
        vk_percent=5.75, vkr_percent=1.0, pfe_kw=0.0, i0_percent=0.0, name="T1")

    z_tot_pu = 100.0 / 500.0 + 0.0575 * (100.0 / 2.5)
    i_hand = (100.0 / (math.sqrt(3) * 0.48)) / z_tot_pu
    got = _by_name(_run(net)["busbars"])["LV"]["i_first_sym_ka"]

    assert abs(got / i_hand - 1) < 0.05, f"LV I={got} expected ~{i_hand}"
    print(f"PASS transformer: LV I={got:.4f} kA (hand {i_hand:.4f})")


def test_hv_bus_not_degraded_by_downstream():
    """The HV bus must still match the source-only value with a trafo attached."""
    net = build_radial_test_net()
    rows = _by_name(_run(net)["busbars"])
    i_hand = 13.8 / (math.sqrt(3) * (13.8 ** 2 / 500.0))
    hv = rows["HV_Bus"]["i_first_sym_ka"]
    # Downstream elements raise it only marginally (motor through the trafo).
    assert i_hand * 0.98 < hv < i_hand * 1.05, f"HV I={hv} expected ~{i_hand}"
    print(f"PASS HV bus: {hv:.4f} kA (source-only hand calc {i_hand:.4f})")


def test_lv_exceeds_hv_in_amps():
    """A 480 V bus must carry far more fault current than the 13.8 kV bus."""
    net = build_radial_test_net()
    rows = _by_name(_run(net)["busbars"])
    hv = rows["HV_Bus"]["i_first_sym_ka"]
    lv = rows["LV_Bus"]["i_first_sym_ka"]
    assert lv > hv * 1.5, f"LV {lv} kA should exceed HV {hv} kA"
    print(f"PASS step-down: HV={hv:.3f} kA, LV={lv:.3f} kA")


def test_motor_across_three_networks():
    """Motor contributes to first-cycle and is absent from the 30-cycle network."""
    net = pp.create_empty_network(sn_mva=100, f_hz=60)
    b = pp.create_bus(net, vn_kv=0.48, name="B1")
    pp.create_ext_grid(net, bus=b, vm_pu=1.0, s_sc_max_mva=20.0,
                       rx_max=0.1, rx_min=0.1)
    with_motor = pp.create_empty_network(sn_mva=100, f_hz=60)
    b2 = pp.create_bus(with_motor, vn_kv=0.48, name="B1")
    pp.create_ext_grid(with_motor, bus=b2, vm_pu=1.0, s_sc_max_mva=20.0,
                       rx_max=0.1, rx_min=0.1)
    pp.create_motor(with_motor, bus=b2, pn_mech_mw=0.5, cos_phi=0.85,
                    cos_phi_n=0.85, efficiency_n_percent=92.0, lrc_pu=6.0,
                    rx=0.15, vn_kv=0.48, name="M1")

    bare = _by_name(_run(net)["busbars"])["B1"]
    mot = _by_name(_run(with_motor)["busbars"])["B1"]

    assert mot["i_first_sym_ka"] > bare["i_first_sym_ka"] * 1.02, \
        "motor must raise first-cycle current"
    assert abs(mot["i_steady_ka"] / bare["i_steady_ka"] - 1) < 0.02, \
        "induction motor must not contribute at 30 cycles"
    assert mot["i_first_peak_ka"] > mot["i_first_sym_ka"], \
        "peak must exceed symmetrical"
    print(f"PASS motor networks: first {bare['i_first_sym_ka']:.3f} -> "
          f"{mot['i_first_sym_ka']:.3f} kA, 30-cycle unchanged")


def test_peak_multiplier_formula():
    """ip/Isym = sqrt(2)*(1+exp(-pi/(X/R))), monotonic and bounded by 2*sqrt(2)."""
    for xr, expected in ((1.0, 1.4142 * (1 + math.exp(-math.pi))),
                         (4.0, 1.4142 * (1 + math.exp(-math.pi / 4))),
                         (17.0, 1.4142 * (1 + math.exp(-math.pi / 17)))):
        mf = ansi_sc._peak_multiplier_remote(xr, 60.0)
        assert abs(mf - expected) < 0.01, f"X/R={xr}: {mf} vs {expected}"

    limit = 2.0 * math.sqrt(2.0)
    prev = 0.0
    for xr in (0.1, 0.5, 1, 2, 3, 3.9, 4.0, 4.1, 6, 10, 17, 40, 100, 1000):
        mf = ansi_sc._peak_multiplier_remote(xr, 60.0)
        assert 1.0 <= mf <= limit + 1e-9, f"X/R={xr} gives MF={mf}, limit {limit}"
        assert mf >= prev - 1e-9, f"MF not monotonic at X/R={xr}"
        prev = mf
    print(f"PASS peak MF: X/R=4 -> {ansi_sc._peak_multiplier_remote(4.0, 60.0):.4f}, "
          f"monotonic and bounded by {limit:.4f}")


def test_interrupting_multiplier_bounds():
    """Symmetrically rated duty must never fall below 1.0 nor exceed sqrt(3)."""
    for xr in (0.5, 1, 4, 10, 17, 30, 100):
        mf = ansi_sc._interrupting_multiplier_remote(xr, 3.0, 60.0)
        s = ansi_sc._symmetry_factor_s(3.0, 60.0)
        assert 1.0 <= mf <= math.sqrt(3.0) + 1e-9, f"X/R={xr}: total MF={mf}"
        assert max(1.0, mf / s) <= math.sqrt(3.0), f"X/R={xr}: symm MF={mf/s}"
    s = ansi_sc._symmetry_factor_s(3.0, 60.0)
    expected_s = math.sqrt(1 + 2 * math.exp(-0.05 / (17.0 / (2 * math.pi * 60))) ** 2)
    assert abs(s - expected_s) < 1e-6, f"S={s} vs {expected_s}"
    print(f"PASS interrupting MF bounded; S(3 cyc, 60 Hz) = {s:.4f}")


def test_bus_peak_within_physical_bound():
    """Every bus peak must sit between 1x and 2*sqrt(2)x the symmetrical value."""
    net = build_radial_test_net()
    limit = 2.0 * math.sqrt(2.0)
    for row in _run(net)["busbars"]:
        ratio = row["i_first_peak_ka"] / row["i_first_sym_ka"]
        assert 1.0 <= ratio <= limit + 1e-6, \
            f"{row['name']}: peak/sym = {ratio}, X/R = {row['xr_first']}"
    print("PASS bus peak/sym ratios within [1, 2*sqrt(2)]")


def test_no_double_counting_of_prebuilt_shunts():
    """_init_ansi_ppc must clear the shunts pandapower pre-builds in sc mode."""
    from pandapower.pypower.idx_bus import GS, BS

    net = build_radial_test_net()
    work = ansi_sc.copy.deepcopy(net)
    _, ppci = ansi_sc._init_ansi_ppc(work, 1.0)
    assert not ppci["bus"][:, GS].any(), f"GS not cleared: {ppci['bus'][:, GS]}"
    assert not ppci["bus"][:, BS].any(), f"BS not cleared: {ppci['bus'][:, BS]}"
    print("PASS no double counting: pre-built GS/BS cleared")


def test_line_currents_exact_radial():
    """On a radial feeder every line carries the downstream fault current."""
    net = pp.create_empty_network(sn_mva=100, f_hz=60)
    b1 = pp.create_bus(net, vn_kv=20.0, name="B1")
    b2 = pp.create_bus(net, vn_kv=20.0, name="B2")
    b3 = pp.create_bus(net, vn_kv=20.0, name="B3")
    pp.create_ext_grid(net, bus=b1, vm_pu=1.0, s_sc_max_mva=400.0,
                       rx_max=0.1, rx_min=0.1)
    pp.create_line_from_parameters(net, from_bus=b1, to_bus=b2, length_km=5.0,
                                   r_ohm_per_km=0.15, x_ohm_per_km=0.35,
                                   c_nf_per_km=0.0, max_i_ka=0.5, name="L1")
    pp.create_line_from_parameters(net, from_bus=b2, to_bus=b3, length_km=3.0,
                                   r_ohm_per_km=0.15, x_ohm_per_km=0.35,
                                   c_nf_per_km=0.0, max_i_ka=0.5, name="L2")

    vn, s_sc, rx = 20.0, 400.0, 0.1
    x_src = (vn * vn / s_sc) / math.sqrt(1.0 + rx * rx)
    z = complex(rx * x_src, x_src)
    z_l1 = complex(0.15 * 5.0, 0.35 * 5.0)
    z_l2 = complex(0.15 * 3.0, 0.35 * 3.0)
    # Worst case for L1 is a fault at B2, for L2 a fault at B3.
    i_l1 = vn / (math.sqrt(3) * abs(z + z_l1))
    i_l2 = vn / (math.sqrt(3) * abs(z + z_l1 + z_l2))

    data = _run(net)
    assert "lines_sc" in data, "payload must carry lines_sc"
    lines = _by_name(data["lines_sc"])
    assert len(lines) == 2, f"expected 2 lines, got {list(lines)}"
    for name, expected in (("L1", i_l1), ("L2", i_l2)):
        got = lines[name]["i_first_sym_ka"]
        assert abs(got / expected - 1) < 5e-3, \
            f"{name}: I={got} expected {expected}"
    print(f"PASS line currents: L1={lines['L1']['i_first_sym_ka']:.4f} kA "
          f"(hand {i_l1:.4f}), L2={lines['L2']['i_first_sym_ka']:.4f} kA "
          f"(hand {i_l2:.4f})")


def test_line_peak_within_physical_bound():
    net = build_radial_test_net()
    limit = 2.0 * math.sqrt(2.0)
    rows = _run(net)["lines_sc"] + _run(net)["trafos_sc"]
    assert rows, "expected at least one branch row"
    for row in rows:
        if not row["i_first_sym_ka"]:
            continue
        ratio = row["i_first_peak_ka"] / row["i_first_sym_ka"]
        assert 1.0 <= ratio <= limit + 1e-6, \
            f"{row['name']}: branch peak/sym = {ratio}"
    print(f"PASS branch peak/sym ratios within [1, {limit:.3f}]")


def test_transformer_branch_results():
    """A transformer must report both HV and LV side currents."""
    net = build_radial_test_net()
    trafos = _by_name(_run(net)["trafos_sc"])
    assert trafos, "expected trafos_sc rows"
    t1 = trafos["T1"]
    assert t1["i_hv_ka"] > 0 and t1["i_lv_ka"] > 0, t1
    # A step-down transformer carries far more current on the LV side.
    assert t1["i_lv_ka"] > t1["i_hv_ka"] * 5, t1
    print(f"PASS trafo branch: HV={t1['i_hv_ka']:.4f} kA, "
          f"LV={t1['i_lv_ka']:.4f} kA")


def test_line_mapping_with_out_of_service_branch():
    """An out-of-service line must not shift the results of the others.

    ppci drops out-of-service branches, so the pandapower -> ppci branch mapping
    has to go through branch_is rather than assuming identity.
    """
    def net_with(l2_in_service):
        net = pp.create_empty_network(sn_mva=100, f_hz=60)
        b1 = pp.create_bus(net, vn_kv=20.0, name="B1")
        b2 = pp.create_bus(net, vn_kv=20.0, name="B2")
        b3 = pp.create_bus(net, vn_kv=20.0, name="B3")
        pp.create_ext_grid(net, bus=b1, vm_pu=1.0, s_sc_max_mva=400.0,
                           rx_max=0.1, rx_min=0.1)
        # L1 is out of service; L3 feeds B3 so the network stays connected.
        pp.create_line_from_parameters(net, from_bus=b2, to_bus=b3, length_km=4.0,
                                       r_ohm_per_km=0.15, x_ohm_per_km=0.35,
                                       c_nf_per_km=0.0, max_i_ka=0.5, name="L_OOS",
                                       in_service=l2_in_service)
        pp.create_line_from_parameters(net, from_bus=b1, to_bus=b2, length_km=5.0,
                                       r_ohm_per_km=0.15, x_ohm_per_km=0.35,
                                       c_nf_per_km=0.0, max_i_ka=0.5, name="L_LIVE")
        return net

    rows = _by_name(_run(net_with(False))["lines_sc"])
    assert "L_LIVE" in rows, f"live line missing: {list(rows)}"

    vn, s_sc, rx = 20.0, 400.0, 0.1
    x_src = (vn * vn / s_sc) / math.sqrt(1.0 + rx * rx)
    z = complex(rx * x_src, x_src) + complex(0.15 * 5.0, 0.35 * 5.0)
    i_hand = vn / (math.sqrt(3) * abs(z))

    got = rows["L_LIVE"]["i_first_sym_ka"]
    assert abs(got / i_hand - 1) < 5e-3, \
        f"L_LIVE I={got} expected {i_hand} (branch mapping shifted?)"
    print(f"PASS out-of-service mapping: L_LIVE={got:.4f} kA (hand {i_hand:.4f})")


def test_two_phase_fault_ratio():
    """A line-to-line fault is sqrt(3)/2 of the three-phase value."""
    net = pp.create_empty_network(sn_mva=100, f_hz=60)
    pp.create_bus(net, vn_kv=13.8, name="B1")
    pp.create_ext_grid(net, bus=0, vm_pu=1.0, s_sc_max_mva=500.0,
                       rx_max=0.1, rx_min=0.1)
    i3 = _by_name(_run(net, fault_type="3ph")["busbars"])["B1"]["i_first_sym_ka"]
    i2 = _by_name(_run(net, fault_type="2ph")["busbars"])["B1"]["i_first_sym_ka"]
    ratio = i2 / i3
    assert abs(ratio - math.sqrt(3) / 2) < 5e-3, \
        f"I2/I3 = {ratio}, expected {math.sqrt(3)/2}"
    print(f"PASS 2ph/3ph ratio = {ratio:.4f} (sqrt(3)/2 = {math.sqrt(3)/2:.4f})")


if __name__ == "__main__":
    test_peak_multiplier_formula()
    test_interrupting_multiplier_bounds()
    test_no_double_counting_of_prebuilt_shunts()
    test_source_only_exact()
    test_series_line_exact()
    test_transformer_magnitude()
    test_hv_bus_not_degraded_by_downstream()
    test_lv_exceeds_hv_in_amps()
    test_motor_across_three_networks()
    test_bus_peak_within_physical_bound()
    test_line_currents_exact_radial()
    test_line_peak_within_physical_bound()
    test_transformer_branch_results()
    test_line_mapping_with_out_of_service_branch()
    test_two_phase_fault_ratio()
    print("\nAll ANSI short-circuit tests passed.")
