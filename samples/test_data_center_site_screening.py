#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tests for data-center site screening (headroom, N-1-1 cap)."""
from __future__ import annotations

import json
import os
import sys

import pandapower as pp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import data_center_site_screening_electrisim as dcs


def _two_bus_with_load():
    net = pp.create_empty_network(sn_mva=100, f_hz=60)
    b1 = pp.create_bus(net, vn_kv=138.0, name="B1")
    b2 = pp.create_bus(net, vn_kv=138.0, name="B2")
    pp.create_ext_grid(net, bus=b1, vm_pu=1.0)
    pp.create_line_from_parameters(
        net,
        from_bus=b1,
        to_bus=b2,
        length_km=10.0,
        r_ohm_per_km=0.1,
        x_ohm_per_km=0.4,
        c_nf_per_km=10.0,
        max_i_ka=0.35,
        name="TightLine",
    )
    pp.create_load(net, bus=b2, p_mw=10.0, q_mvar=2.0, name="SiteLoad", id="load_site_1")
    pp.runpp(net)
    return net


def test_headroom_below_thermal_limit():
    net = _two_bus_with_load()
    idx = net.load.index[0]
    limits = {
        "voltage_limits": True,
        "thermal_limits": True,
        "min_vm_pu": 0.95,
        "max_vm_pu": 1.05,
        "max_loading_percent": 100.0,
    }
    snap = {idx: (float(net.load.loc[idx, "p_mw"]), float(net.load.loc[idx, "q_mvar"]))}
    hr = dcs._headroom_mw(net, idx, [idx], snap, 0.95, limits)
    assert 0 < hr < 80, f"expected finite headroom below line rating, got {hr}"


def test_n11_pair_cap():
    net = _two_bus_with_load()
    for i in range(4):
        pp.create_line_from_parameters(
            net,
            from_bus=net.bus.index[0],
            to_bus=net.bus.index[1],
            length_km=5.0 + i,
            r_ohm_per_km=0.05,
            x_ohm_per_km=0.3,
            c_nf_per_km=8.0,
            max_i_ka=2.0,
            name=f"Extra_{i}",
        )
    pairs = dcs._build_n11_cases(net, "line")
    assert len(pairs) <= dcs.N11_MAX_CASES
    assert len(pairs) > 0


def test_screening_json_shape():
    net = _two_bus_with_load()
    raw = dcs.site_screening_analysis(
        net,
        {
            "site_load_ids": "load_site_1",
            "mw_sizes": "5,20",
            "include_n11": "false",
            "power_factor": "0.95",
        },
    )
    data = json.loads(raw)
    assert "screening_results" in data
    assert len(data["screening_results"]) == 2
    notes = []
    dcs.site_screening_analysis(
        net,
        {
            "site_load_ids": "load_site_1",
            "mw_sizes": "5",
            "include_n11": "false",
            "power_factor": "0.95",
            "_progress_callback": notes.append,
        },
    )
    assert any("N-1" in m for m in notes)
    assert any("headroom" in m for m in notes)
    row = data["screening_results"][0]
    assert "headroom_mw" in row and "upgrade_likely" in row


def test_new_or_worse_rule():
    base = dcs._violation_map([
        {"kind": "Bus", "index": 1, "value": 0.930, "side": "low", "text": "0.930 pu"},
        {"kind": "Line", "index": 4, "value": 110.0, "side": "over", "text": "110.0% loaded"},
    ])
    tols = (0.005, 1.0)
    now = [
        {"kind": "Bus", "index": 1, "value": 0.928, "side": "low", "text": "0.928 pu"},   # within margin
        {"kind": "Line", "index": 4, "value": 112.5, "side": "over", "text": "112.5% loaded"},  # worse
        {"kind": "Bus", "index": 7, "value": 0.940, "side": "low", "text": "0.940 pu"},   # new
    ]
    out = dcs._new_or_worse(now, base, tols)
    assert [(d["kind"], d["index"], d["change"]) for d in out] == [("Line", 4, "worse"), ("Bus", 7, "new")]
    assert out[0]["baseline_text"] == "110.0% loaded"
    # No reference case: everything counts.
    assert len(dcs._new_or_worse(now, None, tols)) == 3


def _net_with_existing_n1_problem():
    """B2 already drops below 0.95 pu when one of its two lines trips; B3 is a strong site."""
    net = pp.create_empty_network(sn_mva=100, f_hz=50)
    b1 = pp.create_bus(net, vn_kv=138.0, name="B1")
    b2 = pp.create_bus(net, vn_kv=138.0, name="B2")
    b3 = pp.create_bus(net, vn_kv=138.0, name="B3")
    pp.create_ext_grid(net, bus=b1, vm_pu=1.0)
    for i in range(2):
        pp.create_line_from_parameters(
            net, from_bus=b1, to_bus=b2, length_km=30.0, r_ohm_per_km=0.1, x_ohm_per_km=0.4,
            c_nf_per_km=10.0, max_i_ka=1.0, name=f"B1_B2_{i}",
        )
        pp.create_line_from_parameters(
            net, from_bus=b1, to_bus=b3, length_km=5.0, r_ohm_per_km=0.05, x_ohm_per_km=0.3,
            c_nf_per_km=10.0, max_i_ka=1.0, name=f"B1_B3_{i}",
        )
    pp.create_load(net, bus=b2, p_mw=150.0, q_mvar=50.0, name="Existing")
    pp.create_load(net, bus=b2, p_mw=0.0, q_mvar=0.0, name="SiteWeak", id="site_weak")
    pp.create_load(net, bus=b3, p_mw=0.0, q_mvar=0.0, name="SiteFar", id="site_far")
    return net


def test_preexisting_n1_violation_not_charged_to_project():
    net = _net_with_existing_n1_problem()
    data = json.loads(dcs.site_screening_analysis(net, {
        "site_load_ids": "site_weak,site_far",
        "mw_sizes": "20",
        "include_n11": "true",
        "power_factor": "0.95",
    }))
    assert "error" not in data, data.get("error")
    summary = data["summary"]
    assert summary["comparison"] == "new_or_worse_vs_0_mw"
    assert summary["baseline_n1_cases_with_violations"] >= 1
    rows = {r["site_name"]: r for r in data["screening_results"]}

    far = rows["SiteFar"]
    assert far["worst_n1_violations_all"] >= 1, "the existing problem is still visible in the plain count"
    assert far["worst_n1_violations"] == 0
    assert far["upgrade_likely"] is False, far

    weak = rows["SiteWeak"]
    assert weak["worst_n1_violations"] >= 1
    assert any(d.get("change") == "worse" for d in weak["n1_violation_details"])
    assert weak["upgrade_likely"] is True


if __name__ == "__main__":
    test_headroom_below_thermal_limit()
    test_n11_pair_cap()
    test_screening_json_shape()
    test_new_or_worse_rule()
    test_preexisting_n1_violation_not_charged_to_project()
    print("test_data_center_site_screening: OK")
