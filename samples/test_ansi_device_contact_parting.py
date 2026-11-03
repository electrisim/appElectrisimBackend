#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Regression tests: each breaker's interrupting duty must use its own
contact-parting time, not the study-wide one.

Before the fix, a breaker with a 4-cycle contact time in a 2-cycle study was
checked against the 2-cycle duty (27.71 kA) and passed a 28.5 kA rating, while
the 4-cycle duty is 29.60 kA and fails.

Run from appElectrisimBackend:
  python samples/test_ansi_device_contact_parting.py
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
import poi_fault_study_electrisim as poi_study


def _hand_duty(i_sym, xr, cp, f):
    """Hand calculation of the symmetrical-basis interrupting duty."""
    def asym(x):
        dc = math.exp(-2.0 * math.pi * cp / x)
        return math.sqrt(1.0 + 2.0 * dc * dc)
    return i_sym * max(1.0, asym(xr) / asym(17.0))


def _net(device_cp=None, xr=100.0, f_hz=60, rating=28.5, extra_breakers=()):
    """13.8 kV, 500 MVA source with one breaker per (name, cp) entry."""
    net = pp.create_empty_network(sn_mva=100, f_hz=f_hz)
    b0 = pp.create_bus(net, vn_kv=13.8, name="HV")
    b1 = pp.create_bus(net, vn_kv=13.8, name="Feeder")
    pp.create_ext_grid(net, bus=b0, vm_pu=1.0, s_sc_max_mva=500.0,
                       rx_max=1.0 / xr, rx_min=1.0 / xr,
                       r0x0_max=0.1, x0x_max=1.0)
    li = pp.create_line_from_parameters(
        net, from_bus=b0, to_bus=b1, length_km=0.1, r_ohm_per_km=0.01,
        x_ohm_per_km=0.1, c_nf_per_km=0.0, max_i_ka=1.0, name="L1")
    breakers = [("CB1", device_cp)] + list(extra_breakers)
    for name, cp in breakers:
        sw = pp.create_switch(net, bus=b0, element=li, et="l", closed=True,
                              type="CB", name=name)
        for col, val in (("interrupting_rating_ka", rating),
                         ("momentary_rating_ka", 100.0),
                         ("contact_parting_cycles", float("nan"))):
            if col not in net.switch.columns:
                net.switch[col] = float("nan")
            net.switch.at[sw, col] = val
        if cp is not None:
            net.switch.at[sw, "contact_parting_cycles"] = float(cp)
    return net


def _run(net, study_cp, f_hz=60):
    return json.loads(ansi_sc.shortcircuit_ansi(net, {
        "fault_type": "3ph", "frequency_hz": f_hz, "prefault_v_pu": 1.0,
        "contact_parting_cycles": study_cp}))


def _duty(out, name="CB1"):
    return {d["name"]: d for d in out["device_duties"]}[name]


def _bus(out, name="HV"):
    return {b["name"]: b for b in out["busbars"]}[name]


I_SYM = 500.0 / (math.sqrt(3) * 13.8)


def test_reported_case_now_fails():
    """Study 2 cycles, breaker 4 cycles: the breaker is over duty."""
    d = _duty(_run(_net(device_cp=4), study_cp=2))
    hand = _hand_duty(I_SYM, 100.0, 4, 60)
    assert d["contact_parting_cycles"] == 4
    assert abs(d["duty_interrupting_ka"] / hand - 1) < 2e-3, (d["duty_interrupting_ka"], hand)
    assert abs(d["duty_interrupting_ka"] - 29.596) < 0.05
    assert d["interrupting_pass"] is False
    assert d["margin_interrupting_ka"] < 0
    print(f"PASS 2/4: duty={d['duty_interrupting_ka']:.4f} kA (hand {hand:.4f}) -> fail")


def test_reversed_case_now_passes():
    """Study 4 cycles, breaker 2 cycles: the breaker is within duty."""
    d = _duty(_run(_net(device_cp=2), study_cp=4))
    hand = _hand_duty(I_SYM, 100.0, 2, 60)
    assert abs(d["duty_interrupting_ka"] / hand - 1) < 2e-3
    assert d["interrupting_pass"] is True
    assert d["margin_interrupting_ka"] > 0
    print(f"PASS 4/2: duty={d['duty_interrupting_ka']:.4f} kA -> pass")


def test_matching_times_equal_bus_value():
    out = _run(_net(device_cp=3), study_cp=3)
    assert abs(_duty(out)["duty_interrupting_ka"] - _bus(out)["i_interrupting_ka"]) < 1e-9
    print("PASS matching times equal bus interrupting current")


def test_missing_device_time_uses_study_time():
    out = _run(_net(device_cp=None), study_cp=2)
    d = _duty(out)
    assert d["contact_parting_cycles"] == 2
    assert abs(d["duty_interrupting_ka"] - _bus(out)["i_interrupting_ka"]) < 1e-9
    print("PASS missing device time falls back to study time")


def test_bus_results_keep_study_basis():
    """Busbar values and momentary/steady duties do not depend on device time."""
    a = _run(_net(device_cp=4), study_cp=2)
    b = _run(_net(device_cp=None), study_cp=2)
    assert a["busbars"] == b["busbars"]
    for key in ("duty_momentary_ka", "duty_steady_ka"):
        assert _duty(a)[key] == _duty(b)[key]
    assert "i_interrupting_sym_ka" not in _bus(a)
    print("PASS bus results and momentary/steady duties unchanged")


def test_mixed_breaker_times():
    net = _net(device_cp=2, extra_breakers=[("CB2", 5), ("CB3", None)])
    out = _run(net, study_cp=3)
    for name, cp in (("CB1", 2), ("CB2", 5), ("CB3", 3)):
        d = _duty(out, name)
        hand = _hand_duty(I_SYM, 100.0, cp, 60)
        assert d["contact_parting_cycles"] == cp
        assert abs(d["duty_interrupting_ka"] / hand - 1) < 2e-3, (name, d["duty_interrupting_ka"], hand)
    print("PASS mixed breaker timings in one study")


def test_xr_and_frequency_variants():
    for xr in (30.0, 100.0):
        for f in (50, 60):
            d = _duty(_run(_net(device_cp=5, xr=xr, f_hz=f), study_cp=2, f_hz=f))
            i_sym = 500.0 / (math.sqrt(3) * 13.8)
            hand = _hand_duty(i_sym, xr, 5, f)
            assert abs(d["duty_interrupting_ka"] / hand - 1) < 3e-3, (xr, f, d["duty_interrupting_ka"], hand)
    print("PASS X/R 30/100 and 50/60 Hz")


def test_poi_study_propagates_device_time():
    net = _net(device_cp=4)
    out = json.loads(poi_study.run_poi_fault_study(
        net, {"frequency_hz": 60, "contact_parting_cycles": 2}))
    rows = [d for d in out.get("breaker_duties") or [] if d.get("name") == "CB1"]
    assert rows, "expected CB1 in POI breaker duties"
    assert any(r.get("over_duty") for r in rows), rows
    print("PASS POI study flags the 2/4 breaker as over duty")


if __name__ == "__main__":
    test_reported_case_now_fails()
    test_reversed_case_now_passes()
    test_matching_times_equal_bus_value()
    test_missing_device_time_uses_study_time()
    test_bus_results_keep_study_basis()
    test_mixed_breaker_times()
    test_xr_and_frequency_variants()
    test_poi_study_propagates_device_time()
    print("\nAll device contact-parting tests passed.")
