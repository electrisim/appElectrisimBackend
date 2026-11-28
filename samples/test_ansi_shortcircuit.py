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


def test_pre_post_ansi_delta():
    """Post-project gen increases fault level vs pre-project out-of-service."""
    net = pp.create_empty_network(sn_mva=100, f_hz=60)
    b = pp.create_bus(net, vn_kv=13.8, name="POI")
    pp.create_ext_grid(net, bus=b, vm_pu=1.0, s_sc_max_mva=500.0, rx_max=0.1, rx_min=0.1)
    pp.create_gen(
        net,
        bus=b,
        p_mw=0.0,
        vm_pu=1.0,
        sn_mva=50.0,
        vn_kv=13.8,
        name="Backup_Gen",
        xdss_pu=0.15,
        rdss_pu=0.01,
    )
    params = dict(PARAMS)
    params["compare_pre_post"] = "true"
    params["project_element_ids"] = "Backup_Gen"
    out = json.loads(ansi_sc.shortcircuit_with_optional_pre_post(net, params))
    assert out.get("pre_post_comparison") is True
    cmp_rows = out.get("bus_comparison") or []
    assert len(cmp_rows) >= 1
    row = cmp_rows[0]
    pre = float(row["i_first_sym_pre_ka"])
    post = float(row["i_first_sym_post_ka"])
    assert post > pre + 0.01, f"expected post > pre, got pre={pre} post={post}"
    print(f"PASS pre/post SC delta pre={pre:.3f} post={post:.3f} kA")


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


def _grid_z(vn_kv, s_sc_mva, rx):
    x = (vn_kv * vn_kv / s_sc_mva) / math.sqrt(1.0 + rx * rx)
    return complex(rx * x, x)


def _trafo_z(vk_percent, vkr_percent, vn_kv, sn_mva):
    zb = vn_kv * vn_kv / sn_mva
    r = vkr_percent / 100.0 * zb
    return complex(r, math.sqrt((vk_percent / 100.0 * zb) ** 2 - r * r))


def _dyn_test_net(vk, vkr):
    net = pp.create_empty_network(sn_mva=100, f_hz=60)
    hv = pp.create_bus(net, vn_kv=13.8, name="HV")
    lv = pp.create_bus(net, vn_kv=0.48, name="LV")
    pp.create_ext_grid(net, bus=hv, vm_pu=1.0, s_sc_max_mva=500.0, rx_max=0.1, rx_min=0.1,
                       x0x_max=2.0, r0x0_max=0.2, x0x_min=2.0, r0x0_min=0.2)
    pp.create_transformer_from_parameters(
        net, hv_bus=hv, lv_bus=lv, sn_mva=2.5, vn_hv_kv=13.8, vn_lv_kv=0.48,
        vk_percent=vk, vkr_percent=vkr, pfe_kw=0.0, i0_percent=0.0,
        vk0_percent=vk, vkr0_percent=vkr, mag0_percent=100.0, mag0_rx=0.0,
        si0_hv_partial=0.9, vector_group="Dyn", name="T1")
    return net


def test_transformer_nameplate_impedance():
    """IEEE C37.010 uses the nameplate transformer impedance, not IEC 60909's K_T.

    pandapower multiplies transformer impedances by K_T = 0.95 c / (1 + 0.6 x_T) as it builds
    them, so the study used to read 7 % high behind a 20 % transformer and 1 % low behind a
    5.75 % one (the earlier 5 % tolerance hid it).
    """
    for vk, vkr in ((5.75, 1.0), (12.0, 0.5), (20.0, 0.4)):
        net = _dyn_test_net(vk, vkr)
        z = _grid_z(0.48, 500.0, 0.1) + _trafo_z(vk, vkr, 0.48, 2.5)
        i_hand = 0.48 / (math.sqrt(3) * abs(z))
        got = _by_name(_run(net)["busbars"])["LV"]["i_first_sym_ka"]
        assert abs(got / i_hand - 1) < 1e-3, f"vk={vk} %: LV I={got} expected {i_hand}"

    net = pp.create_empty_network(sn_mva=100, f_hz=60)
    hv = pp.create_bus(net, vn_kv=110.0, name="HV")
    mv = pp.create_bus(net, vn_kv=20.0, name="MV")
    lv = pp.create_bus(net, vn_kv=10.0, name="LV")
    pp.create_ext_grid(net, bus=hv, vm_pu=1.0, s_sc_max_mva=5000.0, rx_max=0.1, rx_min=0.1)
    pp.create_transformer3w_from_parameters(
        net, hv_bus=hv, mv_bus=mv, lv_bus=lv, vn_hv_kv=110.0, vn_mv_kv=20.0, vn_lv_kv=10.0,
        sn_hv_mva=40.0, sn_mv_mva=40.0, sn_lv_mva=40.0, vk_hv_percent=12.0, vk_mv_percent=8.0,
        vk_lv_percent=18.0, vkr_hv_percent=0.4, vkr_mv_percent=0.4, vkr_lv_percent=0.4,
        pfe_kw=0.0, i0_percent=0.0, name="T3")
    # vk_lv_percent is the HV-LV pair, so the LV fault sees the grid plus that impedance.
    z = _grid_z(10.0, 5000.0, 0.1) + _trafo_z(18.0, 0.4, 10.0, 40.0)
    i_hand = 10.0 / (math.sqrt(3) * abs(z))
    got = _by_name(_run(net)["busbars"])["LV"]["i_first_sym_ka"]
    assert abs(got / i_hand - 1) < 1e-3, f"three-winding LV I={got} expected {i_hand}"
    print(f"PASS nameplate transformer impedance (no K_T): three-winding LV I={got:.4f} kA "
          f"(hand {i_hand:.4f})")


def test_single_line_to_ground_sequence_networks():
    """Line to ground: I = 3E / |2 Z1 + Z0| with pandapower's zero-sequence network.

    The Dyn transformer's delta winding cuts the zero-sequence path, so the HV bus only sees
    the grid's Z0 and the LV bus only the transformer's.
    """
    vk, vkr = 5.75, 1.0
    net = _dyn_test_net(vk, vkr)
    zs1 = _grid_z(13.8, 500.0, 0.1)
    zs0 = complex(0.2 * 2.0 * zs1.imag, 2.0 * zs1.imag)  # x0x = 2, r0x0 = 0.2
    zt = _trafo_z(vk, vkr, 0.48, 2.5)
    zs1_lv = zs1 * (0.48 / 13.8) ** 2
    cases = {
        "HV": (13.8, 2 * zs1 + zs0),
        "LV": (0.48, 2 * (zs1_lv + zt) + zt),
    }
    rows = _by_name(_run(net, fault_type="1ph")["busbars"])
    for name, (vn, z_loop) in cases.items():
        i_hand = 3 * vn / math.sqrt(3) / abs(z_loop)
        xr_hand = z_loop.imag / z_loop.real
        got = rows[name]
        assert abs(got["i_first_sym_ka"] / i_hand - 1) < 1e-3, \
            f"{name}: I_SLG={got['i_first_sym_ka']} expected {i_hand}"
        assert abs(got["xr_first"] / xr_hand - 1) < 5e-3, \
            f"{name}: X/R={got['xr_first']} expected {xr_hand}"
    print(f"PASS line-to-ground: HV {rows['HV']['i_first_sym_ka']:.4f} kA, "
          f"LV {rows['LV']['i_first_sym_ka']:.4f} kA, LV X/R {rows['LV']['xr_first']:.3f}")


def test_line_to_ground_on_unearthed_network_is_capacitive():
    """Behind a YNd transformer the 20 kV system has no earth, so a line-to-ground fault only
    drives the cable's charging current, I = 3E / |2 Z1 + Z0| with Z0 the zero-sequence
    capacitance (about sqrt(3) w C0 U). The earlier model put every line's zero-sequence
    impedance to earth and reported kiloamperes here."""
    def build(c0_nf_per_km, f_hz=60):
        net = pp.create_empty_network(sn_mva=100, f_hz=f_hz)
        hv = pp.create_bus(net, vn_kv=110.0, name="HV")
        mv = pp.create_bus(net, vn_kv=20.0, name="MV")
        far = pp.create_bus(net, vn_kv=20.0, name="FAR")
        pp.create_ext_grid(net, bus=hv, vm_pu=1.0, s_sc_max_mva=5000.0, rx_max=0.1, rx_min=0.1,
                           x0x_max=1.0, r0x0_max=0.1)
        pp.create_transformer_from_parameters(
            net, hv_bus=hv, lv_bus=mv, sn_mva=40.0, vn_hv_kv=110.0, vn_lv_kv=20.0,
            vk_percent=12.0, vkr_percent=0.4, pfe_kw=0.0, i0_percent=0.0,
            vk0_percent=12.0, vkr0_percent=0.4, mag0_percent=100.0, mag0_rx=0.0,
            si0_hv_partial=0.9, vector_group="YNd", name="T1")
        pp.create_line_from_parameters(
            net, from_bus=mv, to_bus=far, length_km=10.0, r_ohm_per_km=0.1, x_ohm_per_km=0.12,
            c_nf_per_km=0.0, max_i_ka=0.5, r0_ohm_per_km=0.4, x0_ohm_per_km=1.0,
            c0_nf_per_km=c0_nf_per_km, name="CABLE")
        return net

    net = build(250.0)
    rows = _by_name(_run(net, fault_type="1ph")["busbars"])
    i3 = _by_name(_run(net)["busbars"])["MV"]["i_first_sym_ka"]
    z1 = _grid_z(20.0, 5000.0, 0.1) + _trafo_z(12.0, 0.4, 20.0, 40.0)
    y_half = 1j * 2 * math.pi * 60 * 250e-9 * 10.0 / 2
    z_line0 = complex(0.4 * 10.0, 1.0 * 10.0)
    z0 = 1 / (y_half + 1 / (z_line0 + 1 / y_half))
    i_hand = 3 * 20.0 / math.sqrt(3) / abs(2 * z1 + z0)
    got = rows["MV"]["i_first_sym_ka"]
    assert abs(got / i_hand - 1) < 5e-3, f"MV I_SLG={got} expected {i_hand} (charging current)"
    assert got < 0.01 * i3, f"MV I_SLG={got} kA should be far below I_3ph={i3} kA"

    # app.py builds every network at pandapower's default 50 Hz: the study frequency from the
    # dialog has to reach the line charging, or a 60 Hz study reports 50/60 of the current.
    as_app = _by_name(_run(build(250.0, f_hz=50), fault_type="1ph")["busbars"])["MV"]["i_first_sym_ka"]
    assert abs(as_app / got - 1) < 1e-9, f"50 Hz network, 60 Hz study: I_SLG={as_app} kA, expected {got} kA"

    open_rows = _by_name(_run(build(0.0), fault_type="1ph")["busbars"])
    for name in ("MV", "FAR"):
        assert open_rows[name]["i_first_sym_ka"] < 1e-4, \
            f"{name}: no zero-sequence path, got I_SLG={open_rows[name]['i_first_sym_ka']} kA"
    print(f"PASS unearthed line-to-ground: MV {got * 1000:.2f} A (hand {i_hand * 1000:.2f} A), "
          f"I_3ph {i3:.3f} kA")


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
    test_pre_post_ansi_delta()
    test_two_phase_fault_ratio()
    test_transformer_nameplate_impedance()
    test_single_line_to_ground_sequence_networks()
    test_line_to_ground_on_unearthed_network_is_capacitive()
    print("\nAll ANSI short-circuit tests passed.")
