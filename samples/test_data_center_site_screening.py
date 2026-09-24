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


if __name__ == "__main__":
    test_headroom_below_thermal_limit()
    test_n11_pair_cap()
    test_screening_json_shape()
    print("test_data_center_site_screening: OK")
