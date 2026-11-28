# -*- coding: utf-8 -*-
"""Smoke tests for POI fault study package."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app  # noqa: E402,F401  (installs Electrisim's pandapower fixes)
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


def _unearthed_cable_net(f_hz):
    """110 kV POI, YNd transformer, 10 km 20 kV cable: the 20 kV side has no earth."""
    net = pp.create_empty_network(f_hz=f_hz)
    poi = pp.create_bus(net, vn_kv=110.0, name="POI")
    mv = pp.create_bus(net, vn_kv=20.0, name="MV")
    far = pp.create_bus(net, vn_kv=20.0, name="FAR")
    pp.create_ext_grid(net, bus=poi, s_sc_max_mva=5000, s_sc_min_mva=4000, rx_max=0.1, rx_min=0.1,
                       x0x_max=1.0, r0x0_max=0.1, x0x_min=1.0, r0x0_min=0.1)
    pp.create_transformer_from_parameters(
        net, hv_bus=poi, lv_bus=mv, sn_mva=40.0, vn_hv_kv=110.0, vn_lv_kv=20.0, vk_percent=12.0,
        vkr_percent=0.4, pfe_kw=0.0, i0_percent=0.0, vk0_percent=12.0, vkr0_percent=0.4,
        mag0_percent=100.0, mag0_rx=0.0, si0_hv_partial=0.9, vector_group="YNd", name="T1")
    pp.create_line_from_parameters(
        net, from_bus=mv, to_bus=far, length_km=10.0, r_ohm_per_km=0.1, x_ohm_per_km=0.12,
        c_nf_per_km=250.0, max_i_ka=0.5, r0_ohm_per_km=0.4, x0_ohm_per_km=1.0, c0_nf_per_km=250.0,
        endtemp_degree=80.0, name="CABLE")
    return net


def _single_phase_currents(out):
    rows = {(r["bus_name"], r["case"]): r for r in out["coordination"] if r["fault_type"] == "1ph"}
    assert all(not r.get("error") for r in rows.values()), rows
    return {k: float(r["ikss_ka"]) for k, r in rows.items()}, float(out["grounding"][0]["slg_i_ka_lv"])


def test_study_frequency_reaches_the_zero_sequence():
    """app.py builds the network at pandapower's default 50 Hz. On the unearthed 20 kV side a
    single-phase fault only drives the cable charging current, so a 60 Hz study has to give the
    60 Hz current (6/5 of the 50 Hz one), whatever frequency the network was built with."""
    ref_rows, ref_slg = _single_phase_currents(
        json.loads(poi_study.run_poi_fault_study(_unearthed_cable_net(60), {"frequency_hz": 60})))
    as_app = _unearthed_cable_net(50)
    rows, slg = _single_phase_currents(json.loads(poi_study.run_poi_fault_study(as_app, {"frequency_hz": 60})))
    assert as_app.f_hz == 50, "the study must not change the caller's network"
    for key, ik in ref_rows.items():
        assert abs(rows[key] / ik - 1) < 1e-9, (key, rows[key], ik)
    assert abs(slg / ref_slg - 1) < 1e-9, (slg, ref_slg)
    rows50, slg50 = _single_phase_currents(
        json.loads(poi_study.run_poi_fault_study(_unearthed_cable_net(50), {"frequency_hz": 50})))
    assert abs(slg / slg50 - 1.2) < 0.01, f"60 Hz {slg} kA vs 50 Hz {slg50} kA: charging current ratio"
    # A frequency typed as 59.94 Hz: IEC 60909 takes 60 Hz, ANSI the value as typed.
    _single_phase_currents(json.loads(poi_study.run_poi_fault_study(_unearthed_cable_net(50),
                                                                    {"frequency_hz": 59.94})))
    print(f"PASS study frequency: MV SLG {slg * 1000:.1f} A at 60 Hz, {slg50 * 1000:.1f} A at 50 Hz")


if __name__ == "__main__":
    test_poi_study_runs()
    test_over_duty_flag()
    test_study_frequency_reaches_the_zero_sequence()
