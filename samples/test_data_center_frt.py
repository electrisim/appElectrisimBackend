"""Data-centre fault ride-through: STATCOM sizing with FRT, STATCOM in ANDES, UPS behaviour.

The network is the utility pocket of the data-centre tutorial, cut down: a 138 kV grid feeds the
POI over two lines, a 400 MVA transformer feeds the 34.5 kV campus with a 300 MW data centre
(computational load, 85 % IT behind a UPS) and a 150 Mvar STATCOM.

(a) Grid-forming STATCOM sizing, fault ride-through duty: dIq = k dU, checked against the converter.
(b) Transient Stability (ANDES): the STATCOM is a converter (REGCA1 + REECA1, P = 0) that injects
    reactive current during the dip.
(c) Transient Stability (ANDES): the IT share is constant power behind a UPS that transfers to its
    battery in a dip, walks back in after it, and loses the IT load when the hold-up time runs out.

Run with ``python samples/test_data_center_frt.py``.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import math
import os
import sys
import warnings

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import grid_forming_statcom_electrisim as gfm  # noqa: E402


def data_centre_network(statcom=True, it_share="85", hold_s="10", walk_in_s="2"):
    net = {
        "0": {"typ": "PowerFlowPandaPower Parameters", "frequency": "60", "algorithm": "nr",
              "calculate_voltage_angles": "auto", "initialization": "auto", "user_email": "t@e.com"},
        "1": {"typ": "Bus0", "name": "b_util", "id": "b_util", "vn_kv": "138", "userFriendlyName": "Utility_138"},
        "2": {"typ": "Bus1", "name": "b_poi", "id": "b_poi", "vn_kv": "138", "userFriendlyName": "POI_138"},
        "3": {"typ": "Bus2", "name": "b_campus", "id": "b_campus", "vn_kv": "34.5", "userFriendlyName": "Campus_34.5"},
        "4": {"typ": "External Grid0", "name": "eg", "id": "eg", "userFriendlyName": "Utility_Grid", "bus": "b_util",
              "vm_pu": "1.02", "va_degree": "0", "s_sc_max_mva": "8000", "s_sc_min_mva": "4000",
              "rx_max": "0.1", "rx_min": "0.1", "r0x0_max": "0.1", "x0x_max": "1", "r0x0_min": "0.1",
              "x0x_min": "1", "in_service": "true"},
        "5": {"typ": "Line0", "name": "line_a", "id": "line_a", "userFriendlyName": "Line_A", "busFrom": "b_util",
              "busTo": "b_poi", "length_km": "20", "parallel": "1", "df": "1", "in_service": "true",
              "r_ohm_per_km": "0.05", "x_ohm_per_km": "0.4", "c_nf_per_km": "9", "g_us_per_km": "0",
              "max_i_ka": "2", "type": "ol", "endtemp_degree": "250"},
        "6": {"typ": "Line1", "name": "line_b", "id": "line_b", "userFriendlyName": "Line_B", "busFrom": "b_util",
              "busTo": "b_poi", "length_km": "20", "parallel": "1", "df": "1", "in_service": "true",
              "r_ohm_per_km": "0.05", "x_ohm_per_km": "0.4", "c_nf_per_km": "9", "g_us_per_km": "0",
              "max_i_ka": "2", "type": "ol", "endtemp_degree": "250"},
        "7": {"typ": "Transformer0", "name": "tr_poi", "id": "tr_poi", "userFriendlyName": "POI_Transformer",
              "hv_bus": "b_poi", "lv_bus": "b_campus", "sn_mva": "400", "vn_hv_kv": "138", "vn_lv_kv": "34.5",
              "vkr_percent": "0.3", "vk_percent": "12", "pfe_kw": "0", "i0_percent": "0", "vector_group": "YNyn",
              "shift_degree": "0", "tap_side": "hv", "tap_pos": "0", "tap_neutral": "0", "tap_max": "8",
              "tap_min": "-8", "tap_step_percent": "1.25", "parallel": "1", "in_service": "true"},
        "8": {"typ": "Load0", "name": "dc_load", "id": "dc_load", "userFriendlyName": "DataCenter_Load", "bus": "b_campus",
              "p_mw": "300", "q_mvar": "60", "const_z_percent": "50", "const_i_percent": "0", "sn_mva": "0",
              "scaling": "1", "type": "wye", "in_service": "true",
              "dc_computational_enabled": "true", "dc_it_share_percent": it_share, "dc_ups_hold_s": hold_s,
              "dc_ups_transfer_pu": "0.85", "dc_ups_return_pu": "0.9", "dc_ups_walk_in_s": walk_in_s,
              "dc_ride_through_csv": "0,0\n0.15,0\n0.15,0.7\n2,0.85\n3,0.9"},
    }
    if statcom:
        net["9"] = {"typ": "SSC0", "name": "ssc", "id": "ssc", "userFriendlyName": "Campus_STATCOM", "bus": "b_campus",
                    "r_ohm": "0", "x_ohm": "0.6", "set_vm_pu": "1.0", "vm_internal_pu": "1", "va_internal_degree": "0",
                    "controllable": "true", "q_max_mvar": "150", "q_min_mvar": "-150", "in_service": "true",
                    "dyn_statcom_kqv": "2", "dyn_statcom_deadband_percent": "10", "dyn_statcom_imax_pu": "1.0"}
    return net


# --------------------------------------------------------------------------- (a) sizing

FRT_ONLY = {"duty_inertia": "false", "duty_phase_jump": "false", "duty_damping": "false",
            "duty_frequency_support": "false", "duty_frt": "true", "frt_k_factor": "2",
            "frt_deadband_percent": "10", "frt_iq_max_pu": "1.0", "frt_statcom_share_percent": "100"}


def test_frt_formula():
    frt = gfm.read_frt(dict(FRT_ONLY, frt_retained_pu="0.7"))
    out = gfm.frt_requirement(frt, 300.0, 150.0, 20.0, 1.0, 34.5)
    # step characteristic: dU = 0.3 leaves the 10 % deadband, so dIq = 2 * 0.3 = 0.6 p.u. of 300 MVA
    assert abs(out["delta_iq_pu"] - 0.6) < 1e-9 and abs(out["delta_iq_mva"] - 180.0) < 1e-6
    assert abs(out["iq_total_mva"] - 200.0) < 1e-6           # 20 Mvar before the dip on top
    assert abs(out["iq_total_ka"] - 200.0 / (math.sqrt(3) * 34.5)) < 1e-3
    assert out["rating_ok"] is False and abs(out["required_rating_mva"] - 200.0) < 1e-6
    cont = gfm.frt_requirement(gfm.read_frt(dict(FRT_ONLY, frt_retained_pu="0.7", frt_characteristic="continuous")),
                               300.0, 150.0, 20.0, 1.0, 34.5)
    assert abs(cont["delta_iq_pu"] - 0.4) < 1e-9          # 2 * (0.3 - 0.1)
    # a dip inside the deadband asks for nothing more than the current before it
    small = gfm.frt_requirement(gfm.read_frt(dict(FRT_ONLY, frt_retained_pu="0.95")), 300.0, 150.0, -30.0, 1.0, 34.5)
    assert small["delta_iq_pu"] == 0.0 and abs(small["iq_total_mva"] - 30.0) < 1e-9
    # deepest dip: k * dU = 2 is limited to 1 p.u.; a higher short-time current makes the converter enough
    # 150 MVA with 20 Mvar before the dip covers dips down to 1 - (150 - 20) / (2 * 300) = 0.783 p.u.
    assert abs(out["covers_down_to_pu"] - (1 - 130 / 600)) < 1e-3, out["covers_down_to_pu"]
    deep = gfm.frt_requirement(gfm.read_frt(dict(FRT_ONLY, frt_retained_pu="0")), 300.0, 150.0, 0.0, 2.0, 34.5)
    assert deep["delta_iq_limited"] and abs(deep["iq_total_mva"] - 300.0) < 1e-6
    assert deep["rating_ok"] is True and abs(deep["required_rating_mva"] - 150.0) < 1e-6
    assert deep["covers_down_to_pu"] == 0.0
    # half of it from the STATCOM (the rest from other units)
    half = gfm.frt_requirement(gfm.read_frt(dict(FRT_ONLY, frt_retained_pu="0", frt_statcom_share_percent="50")),
                               300.0, 150.0, 0.0, 1.0, 34.5)
    assert abs(half["iq_total_mva"] - 150.0) < 1e-6 and half["rating_ok"] is True


def _post(data, **params):
    import app
    study = {"typ": "GridFormingStatcomSizing Parameters", "frequency": "60", "user_email": "t@e.com"}
    study.update(params)
    data = copy.deepcopy(data)
    data["0"] = study
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=data)
    assert response.status_code == 200, response.get_data(as_text=True)[:300]
    return json.loads(response.get_data(as_text=True))


def test_sizing_for_a_data_centre():
    out = _post(data_centre_network(), requirement_set="data_centre_frt", frt_retained_pu="0.5", **FRT_ONLY)
    assert out.get("study") == "grid_forming_statcom_sizing", out
    # no Static Generators: the computational load is the facility
    assert out["plant"]["kind"] == "load" and out["plant"]["name"] == "DataCenter_Load", out["plant"]
    assert abs(out["plant"]["p_mw"] - 300.0) < 1e-6
    frt = out["frt"]
    assert frt["enabled"] and abs(frt["base_mva"] - math.hypot(300, 60)) < 0.1
    assert abs(frt["delta_iq_pu"] - 1.0) < 1e-9             # 2 * 0.5
    assert out["storage_needed"] is False and out["bank"] is None
    # 306 MVA of reactive current is more than a 150 MVA converter can carry
    assert frt["rating_ok"] is False and out["statcom"]["rating_ok"] is False
    assert out["statcom"]["required_rating_mva"] >= frt["iq_total_mva"] - 0.1
    items = [row["item"] for row in out["checklist"]]
    assert items[:4] == ["FRT 1", "FRT 2", "FRT 3", "Energy storage"], items
    # the STATCOM already carries the reactive power of the load before the dip
    assert 50.0 < frt["iq_pre_mva"] < 75.0, frt["iq_pre_mva"]
    # a shallower dip with 1.2 p.u. short-time current fits: (63 + 0.3 * 306) / 1.2 < 150
    ok = _post(data_centre_network(), requirement_set="data_centre_frt", frt_retained_pu="0.85", overload_pu="1.2",
               **FRT_ONLY)
    assert ok["frt"]["rating_ok"] is True and ok["statcom"]["rating_ok"] is True, ok["frt"]
    # an explicit load choice, and the FRT duty off: the old behaviour
    off = _post(data_centre_network(), facility_id="dc_load", duty_inertia="false", duty_phase_jump="false",
                duty_damping="false")
    assert off["frt"] == {"enabled": False} and off["plant"]["kind"] == "load"


# --------------------------------------------------------------------------- (b), (c) ANDES

def _ae():
    try:
        import andes_electrisim as ae
    except ImportError:
        return None
    return ae if ae._HAS_ANDES else None


def test_ups_state_machine():
    ae = _ae()
    if ae is None:
        print("SKIP: ANDES is not installed.")
        return
    # the UPS stays on its battery during the return delay, so the hold-up must cover it
    ups = ae._UpsState(hold_s=5.0, transfer_pu=0.85, return_pu=0.9, return_delay_s=1.0, walk_in_s=2.0)
    assert ups.update(0.0, 1.0) == 1.0
    assert ups.update(1.0, 0.5) == 0.0 and ups.state == "battery"
    assert ups.update(1.5, 0.95) == 0.0                     # back above return, waiting for the delay
    assert ups.update(2.5, 0.95) == 0.0 and ups.state == "walk_in"
    assert abs(ups.update(3.5, 1.0) - 0.5) < 1e-9          # half way through the 2 s walk-in
    assert ups.update(4.5, 1.0) == 1.0 and ups.state == "grid"
    lost = ae._UpsState(hold_s=0.5, transfer_pu=0.85, return_pu=0.9, return_delay_s=0.0, walk_in_s=0.0)
    lost.update(1.0, 0.3)
    lost.update(1.4, 0.3)
    assert lost.state == "battery"
    assert lost.update(1.6, 0.3) == 0.0 and lost.state == "lost"
    assert lost.update(3.0, 1.0) == 0.0                    # the IT load stays off
    # no UPS: the power supplies bridge one cycle, then the IT load is lost
    short = ae._UpsState(hold_s=0.0, transfer_pu=0.85, return_pu=0.9, return_delay_s=1.0, walk_in_s=5.0)
    short.update(1.0, 0.5)
    assert short.update(1.01, 1.0) == 1.0 and short.state == "grid"
    long = ae._UpsState(hold_s=0.0, transfer_pu=0.85, return_pu=0.9, return_delay_s=1.0, walk_in_s=5.0)
    long.update(1.0, 0.5)
    assert long.update(1.05, 0.5) == 0.0 and long.state == "lost"


def test_ride_curve_from_the_disturbance():
    ae = _ae()
    if ae is None:
        return
    pts = ae._ride_curve("0,0\n0.15,0\n0.15,0.7\n2,0.85\n3,0.9")
    assert ae._curve_vmin(pts, -1.0) == 0.9                 # before the disturbance: continuous limit
    assert ae._curve_vmin(pts, 0.1) == 0.0
    assert ae._curve_vmin(pts, 0.15) == 0.0                 # vertical step: the lower value at the instant
    assert abs(ae._curve_vmin(pts, 0.1501) - 0.7) < 1e-3
    assert abs(ae._curve_vmin(pts, 1.075) - 0.775) < 1e-9
    assert ae._curve_vmin(pts, 10.0) == 0.9


def _tds(net, **extra):
    ae = _ae()
    params = {"frequency": "60", "sn_mva": "100", "tf": "6", "poi_bus": "b_poi"}
    params.update(extra)
    out = json.loads(ae.run_tds(net, params))
    assert not out.get("error"), out.get("message")
    assert out.get("converged"), out.get("warnings")
    return out


BOLTED_POI = {"fault_bus": "b_poi", "fault_enabled": "true", "fault_tf": "1.0", "fault_tc": "1.15"}
REMOTE = {"fault_bus": "b_util", "fault_enabled": "true", "fault_tf": "1.0", "fault_tc": "1.15", "fault_xf": "0.05"}


def _at(out, series, t_s):
    k = min(range(len(out["time"])), key=lambda i: abs(out["time"][i] - t_s))
    return series[k]


def _campus(out):
    return next(s for s in out["bus_voltage"] if s["name"] == "Campus_34.5")["values"]


def test_statcom_in_transient_stability():
    ae = _ae()
    if ae is None:
        return
    ss, meta = ae.build_system(data_centre_network(), {"frequency": "60", "sn_mva": "100"}, grid_behind_impedance=True)
    assert ss.REGCA1.n == 1 and ss.REECA1.n == 1 and meta["n_statcoms"] == 1, meta["defaults_applied"]
    assert any("STATCOM 'Campus_STATCOM'" in d for d in meta["defaults_applied"])
    # a STATCOM the dynamic model cannot reach from the grid is left out with a warning
    island = data_centre_network()
    island["10"] = {"typ": "Bus3", "name": "b_island", "id": "b_island", "vn_kv": "34.5", "userFriendlyName": "Island"}
    island["9"]["bus"] = "b_island"
    ss_i, meta_i = ae.build_system(island, {"frequency": "60", "sn_mva": "100"}, grid_behind_impedance=True)
    assert ss_i.REGCA1.n == 0 and any("not connected to the External Grid" in w for w in meta_i["warnings"])
    out = _tds(data_centre_network(), **BOLTED_POI)
    st = out["statcoms"][0]
    assert 50 < st["q_mvar_pre"] < 75, st["q_mvar_pre"]       # the reactive power of the load flow
    assert abs(st["iq_pu_peak"] - 1.0) < 0.02, st["iq_pu_peak"]  # full reactive current, not more
    # the campus bus recovers after the bolted fault on the POI (it used to stay at 0 V)
    campus = _campus(out)
    assert _at(out, campus, 1.07) < 0.05 and campus[-1] > 0.97, (_at(out, campus, 1.07), campus[-1])
    # in a remote fault the STATCOM holds the campus voltage up
    with_statcom = _at(_tds(data_centre_network(), **REMOTE), _campus(_tds(data_centre_network(), **REMOTE)), 1.1)
    no_statcom_out = _tds(data_centre_network(statcom=False), **REMOTE)
    without = _at(no_statcom_out, _campus(no_statcom_out), 1.1)
    assert with_statcom > without + 0.02, (with_statcom, without)


def test_data_centre_ups_in_transient_stability():
    ae = _ae()
    if ae is None:
        return
    out = _tds(data_centre_network(hold_s="10", walk_in_s="2"), **BOLTED_POI)
    dc = out["data_centres"][0]
    assert dc["verdict"] == "ups_transfer", dc
    assert dc["load_drop_mw"] > 250 and abs(dc["p_mw_pre"] - 300) < 1, dc
    assert dc["p_mw"][-1] > 290, dc["p_mw"][-1]                   # back after the walk-in
    assert 1.0 < dc["recovery_s"] < 5.0, dc["recovery_s"]
    assert [e["event"] for e in dc["events"]] == [
        "UPS on battery", "UPS back on the grid, walk-in starts", "IT load fully back on the grid"]
    # 0 V for 0.15 s is inside the envelope, so the facility must ride through. The UPS waits 1 s and
    # walks in over 2 s: the power is back about 2.8 s after the voltage, later than the 1 s allowed.
    assert out["ride_through"]["pass"] is True and out["ride_through"]["verdict"] == "slow_recovery"
    assert out["ride_through"]["t_event_s"] == 1.0
    assert 2.0 < dc["recovery_after_voltage_s"] < 3.5 and dc["recovered_in_time"] is False, dc
    assert 1.1 < dc["voltage_back_t_s"] < 1.3, dc["voltage_back_t_s"]
    # a UPS that returns after 0.1 s and walks in over 0.5 s brings the power back in time
    fast_net = data_centre_network(hold_s="10", walk_in_s="0.5")
    fast_net["8"]["dc_ups_return_delay_s"] = "0.1"
    fast = _tds(fast_net, **BOLTED_POI)
    fdc = fast["data_centres"][0]
    assert fdc["verdict"] == "ups_transfer" and fdc["recovered_in_time"] is True, fdc
    assert fdc["recovery_after_voltage_s"] < 1.0 and fast["ride_through"]["verdict"] == "pass"
    # the frequency of the external grid settles back once the load has returned
    f = fast["frequency_hz"]
    assert max(f) > 60.005 and abs(f[-1] - 60.0) < 0.005, (max(f), f[-1])
    # without a UPS the IT load is lost; only the cooling stays
    lost_out = _tds(data_centre_network(hold_s="0"), **BOLTED_POI)
    lost = lost_out["data_centres"][0]
    assert lost["verdict"] == "it_lost" and lost["p_mw"][-1] < 0.2 * 300, lost["p_mw"][-1]
    assert lost["recovered_in_time"] is None and lost_out["ride_through"]["verdict"] == "load_lost"
    # a line trip leaves the voltage above the transfer voltage: the data centre rides through
    trip = _tds(data_centre_network(), toggle_line="line_a", toggle_t="1.0")
    assert trip["data_centres"][0]["verdict"] == "rides_through" and trip["ride_through"]["verdict"] == "pass"
    # a grid with only the data centre (no generator, no STATCOM) is a valid study
    alone = _tds(data_centre_network(statcom=False), **BOLTED_POI)
    assert alone["data_centres"][0]["verdict"] == "ups_transfer"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("All data-centre fault ride-through tests passed.")
