# -*- coding: utf-8 -*-
"""Smoke tests for POI fault study package."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandapower as pp
import poi_fault_study_electrisim as poi_study


def _mini_net():
    net = pp.create_empty_network(f_hz=50)
    b0 = pp.create_bus(net, vn_kv=20.0, name="POI")
    b1 = pp.create_bus(net, vn_kv=20.0, name="Plant")
    pp.create_ext_grid(net, bus=b0, s_sc_max_mva=350, rx_max=0.1, r0x0_max=0.1, x0x_max=1.0)
    pp.create_line_from_parameters(
        net, from_bus=b0, to_bus=b1, length_km=0.5,
        r_ohm_per_km=0.1, x_ohm_per_km=0.15, c_nf_per_km=200, max_i_ka=0.5, name="Feeder",
    )
    li = net.line.index[0]
    pp.create_switch(
        net, bus=b0, element=li, et="l", closed=True, type="CB", name="CB1",
        interrupting_rating_ka=5.0, momentary_rating_ka=8.0,
    )
    pp.create_gen(
        net, bus=b1, p_mw=0, vm_pu=1.0, sn_mva=2, vn_kv=20, xdss_pu=0.15, rdss_ohm=0.01, name="Backup",
    )
    return net


def test_poi_study_runs():
    net = _mini_net()
    out = json.loads(poi_study.run_poi_fault_study(net, {"frequency_hz": 50, "slg_target_ground_i_a": 100}))
    assert out.get("study") == "poi_fault_study"
    assert out.get("breaker_duties"), "expected breaker duties"
    assert out.get("coordination"), "expected coordination rows"
    close = [r for r in out["coordination"] if r["location_class"] == "close_in" and r["fault_type"] == "3ph" and r["case"] == "max"]
    remote = [r for r in out["coordination"] if r["location_class"] == "remote" and r["fault_type"] == "3ph" and r["case"] == "max"]
    assert close and remote
    ik_close = max(float(r["ikss_ka"] or 0) for r in close)
    ik_remote = max(float(r["ikss_ka"] or 0) for r in remote)
    assert ik_close >= ik_remote, "close-in Ik should be >= remote Ik"
    print("PASS poi study structure and close-in vs remote")


def test_over_duty_flag():
    net = _mini_net()
    out = json.loads(poi_study.run_poi_fault_study(net, {"frequency_hz": 50}))
    duties = out.get("breaker_duties") or []
    assert any(d.get("over_duty") for d in duties), "expected at least one over-duty with 5 kA rating"
    print("PASS over-duty detection")


if __name__ == "__main__":
    test_poi_study_runs()
    test_over_duty_flag()
