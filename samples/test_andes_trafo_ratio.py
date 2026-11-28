"""ANDES sees the same transformer ratio and impedance as the pandapower load flow.

Every two-winding transformer became an ANDES Line with tap = 1 + tap_pos * tap_step_percent / 100
and its impedance referred to the HV winding. Rated voltages that differ from the bus voltages
were ignored, and so were the tap side, tap_neutral and the parallel count. On the "Industrial
plant 6 kV with motors" template (TR-1 110/6.3 kV on a 6 kV bus) the 6 kV bus sat at 1.006 pu in
ANDES and 1.057 pu in pandapower before any motor started, and the transformer impedance was
(6.3/6)^2 = 10 % low. Transient Stability, eigenvalue analysis and dynamic Motor Starting all
started from that operating point.

Now the transformer is the branch pandapower builds: the rated voltages, after the tap moves its
own side, give the off-nominal ratio (vn_hv / V_HV bus) / (vn_lv / V_LV bus), and the impedance is
referred to the LV bus by (vn_lv / V_LV bus)^2 and divided by the parallel count.

The test network has off-nominal ratings on both windings, taps on the HV and the LV side, a
tap_neutral that is not 0, two parallel units, and a tap that also turns the phase in a meshed
part of the network. The ANDES power flow must give the pandapower bus voltages (magnitude and
angle), and a Transient Stability run without events must start, and stay, at them.

Run with ``python samples/test_andes_trafo_ratio.py``.
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

import app  # noqa: E402
import andes_electrisim as ae  # noqa: E402

CLIENT = app.app.test_client()

# Both power flows solve the same equations to their own tolerance (they agree to ~1e-8 pu).
V_TOL_PU = 1e-4
A_TOL_DEG = 0.01

BUSES = [
    ("mxCell_b110", "Grid 110 kV", 110),
    ("mxCell_b20", "MV 20 kV", 20),
    ("mxCell_b20f", "Feeder end 20 kV", 20),
    ("mxCell_b04", "LV 0.4 kV", 0.4),
    ("mxCell_b6", "Plant 6 kV", 6),
    ("mxCell_bg", "Generator 10.5 kV", 10.5),
]


def bus(k, name, label, vn):
    return {"typ": f"Bus{k}", "name": name, "id": name, "vn_kv": str(vn), "userFriendlyName": label}


def trafo(k, label, hv, lv, sn, vn_hv, vn_lv, vk, vkr, **tap):
    el = {"typ": f"Transformer{k}", "name": f"mxCell_t{k}", "id": f"t{k}", "userFriendlyName": label,
          "hv_bus": hv, "lv_bus": lv, "sn_mva": str(sn), "vn_hv_kv": str(vn_hv), "vn_lv_kv": str(vn_lv),
          "vk_percent": str(vk), "vkr_percent": str(vkr), "pfe_kw": "0", "i0_percent": "0",
          "vector_group": "Yy", "shift_degree": "0", "parallel": "1", "tap_side": "hv", "tap_pos": "0",
          "tap_neutral": "0", "tap_min": "-10", "tap_max": "10", "tap_step_percent": "1.5",
          "tap_step_degree": "0", "tap_changer_type": "Ratio", "in_service": "true"}
    el.update({key: str(value) for key, value in tap.items()})
    return el


def load(k, bus_name, p, q):
    return {"typ": f"Load{k}", "name": f"mxCell_ld{k}", "id": f"ld{k}", "userFriendlyName": f"Load {k}",
            "bus": bus_name, "p_mw": str(p), "q_mvar": str(q), "scaling": "1", "const_z_percent": "0",
            "const_i_percent": "0", "sn_mva": "0", "type": "wye", "in_service": "true"}


# Second infeed that closes a loop over the 20 kV cable: a tap that turns the phase changes how
# the load shares the two paths. Default: HV tap step of 1 % turned by 60 degrees.
T2_TAP = {"tap_pos": 4, "tap_step_percent": 1.0, "tap_step_degree": 60}
T2_VARIANTS = [
    ("LV tap, 1 % per step turned by 60 deg", {"tap_side": "lv", "tap_pos": -3}),
    ("ideal phase shifter, 1 % per step", {"tap_changer_type": "Ideal", "tap_step_degree": 0}),
    # Degrees only: the load flow gives a tap range without a step size 1.5 %, so no range here.
    ("ideal phase shifter, 0.5 deg per step", {"tap_changer_type": "Ideal", "tap_step_percent": 0,
                                               "tap_step_degree": 0.5, "tap_pos": -4, "tap_max": 0}),
]


def elements(t2_tap=None):
    els = [bus(k, *b) for k, b in enumerate(BUSES)]
    els += [
        {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_b110", "vm_pu": "1.02",
         "va_degree": "0", "s_sc_max_mva": "5000", "s_sc_min_mva": "4000", "rx_max": "0.1", "rx_min": "0.1",
         "in_service": "true", "userFriendlyName": "Utility"},
        # 115/21 kV on 110/20 kV buses, HV tap +3 x 1.25 %.
        trafo(0, "T1 115/21 kV", "mxCell_b110", "mxCell_b20", 40, 115, 21, 12, 0.4,
              tap_pos=3, tap_step_percent=1.25),
        trafo(1, "T2 115/21 kV phase-turning tap", "mxCell_b110", "mxCell_b20f", 25, 115, 21, 11, 0.4,
              **dict(T2_TAP, **(t2_tap or {}))),
        {"typ": "Line0", "name": "mxCell_l1", "id": "l1", "userFriendlyName": "Cable 20 kV",
         "busFrom": "mxCell_b20", "busTo": "mxCell_b20f", "length_km": "4", "parallel": "1", "df": "1",
         "r_ohm_per_km": "0.16", "x_ohm_per_km": "0.35", "c_nf_per_km": "10", "g_us_per_km": "0",
         "max_i_ka": "0.6", "type": "cs", "in_service": "true"},
        # 20.5/0.42 kV, LV tap -2 x 2.5 %: the tap moves the LV rating, so the impedance too.
        trafo(2, "T3 20.5/0.42 kV LV tap", "mxCell_b20f", "mxCell_b04", 2.5, 20.5, 0.42, 6, 1.0,
              tap_side="lv", tap_pos=-2, tap_step_percent=2.5, tap_changer_type="Symmetrical"),
        # Two parallel 10 MVA 20/6.3 kV units at tap 4 with the neutral tap at 2.
        trafo(3, "T4 2 x 10 MVA 20/6.3 kV", "mxCell_b20", "mxCell_b6", 10, 20, 6.3, 8, 0.6,
              tap_pos=4, tap_neutral=2, parallel=2),
        # Generator step-up 22/10.5 kV on 20/10.5 kV buses, LV tap +1 x 2 %.
        trafo(4, "T5 22/10.5 kV step-up", "mxCell_b20", "mxCell_bg", 12, 22, 10.5, 10, 0.5,
              tap_side="lv", tap_pos=1, tap_step_percent=2.0),
        {"typ": "Generator", "name": "mxCell_g1", "id": "g1", "bus": "mxCell_bg", "userFriendlyName": "G1",
         "p_mw": "8", "vm_pu": "1.01", "sn_mva": "12", "scaling": "1", "slack": "false", "vn_kv": "10.5",
         "xdss_pu": "0.2", "rdss_ohm": "0.001", "cos_phi": "0.85", "pg_percent": "0",
         "power_station_trafo": "0", "in_service": "true"},
        load(0, "mxCell_b20f", 6, 2.5),
        load(1, "mxCell_b04", 1.8, 0.6),
        load(2, "mxCell_b6", 14, 6),
    ]
    return els


def payload(settings, t2_tap=None):
    data = {"0": settings}
    for k, el in enumerate(elements(t2_tap), start=1):
        data[str(k)] = el
    return data


def post(data):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = CLIENT.post("/", json=data)
    assert response.status_code == 200, response.data[:400]
    out = json.loads(response.data)
    assert not out.get("error"), out.get("message") or out.get("error")
    return out


def pandapower_load_flow(t2_tap=None):
    out = post(payload({"typ": "PowerFlowPandaPower Parameters", "frequency": "50", "algorithm": "nr",
                        "calculate_voltage_angles": "auto", "initialization": "auto", "exportPython": False,
                        "enforce_q_lims": "False", "user_email": "test@example.com"}, t2_tap))
    return {b["name"]: (float(b["vm_pu"]), float(b["va_degree"])) for b in out["busbars"]}


def andes_power_flow(t2_tap=None):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        ss, meta = ae.build_system(payload({"typ": "TransientStabilityAndes Parameters"}, t2_tap),
                                   {"frequency": 50, "sn_mva": 100})
        converged = ss.PFlow.run()
    assert converged, "ANDES power flow did not converge"
    by_idx = {idx: (float(v), math.degrees(float(a))) for idx, v, a in zip(ss.Bus.idx.v, ss.Bus.v.v, ss.Bus.a.v)}
    return {name: by_idx[meta["bus_map"][name]] for name, _, _ in BUSES}


def compare(pp_result, andes_result, show=False):
    worst_v = worst_a = 0.0
    for name, label, _ in BUSES:
        (vm_pp, va_pp), (vm_an, va_an) = pp_result[name], andes_result[name]
        if show:
            print(f"  {label:20s} pandapower {vm_pp:.6f} pu {va_pp:8.4f} deg   "
                  f"ANDES {vm_an:.6f} pu {va_an:8.4f} deg")
        worst_v = max(worst_v, abs(vm_an - vm_pp))
        worst_a = max(worst_a, abs(va_an - va_pp))
    print(f"  worst difference {worst_v:.1e} pu, {worst_a:.1e} deg")
    assert worst_v < V_TOL_PU, f"ANDES bus voltages differ from pandapower by up to {worst_v:.4f} pu"
    assert worst_a < A_TOL_DEG, f"ANDES bus angles differ from pandapower by up to {worst_a:.4f} deg"


def test_power_flow(pp_result):
    compare(pp_result, andes_power_flow(), show=True)
    for label, t2_tap in T2_VARIANTS:
        print(f"T2 with {label}:")
        compare(pandapower_load_flow(t2_tap), andes_power_flow(t2_tap))


def test_transient_start(pp_result):
    # No event: the simulation starts from the load-flow voltages and stays there.
    out = post(payload({"typ": "TransientStabilityAndes Parameters", "frequency": "50", "sn_mva": "100",
                        "tf": "1", "tstep": "0", "fault_bus": "", "fault_enabled": "false",
                        "toggle_line": "", "toggle_gen": "", "poi_bus": "", "user_email": "test@example.com"}))
    assert out["converged"], out.get("warnings")
    series = {s["name"]: s["values"] for s in out["bus_voltage"]}
    worst = 0.0
    for name, label, _ in BUSES:
        values = series[label]
        worst = max(worst, max(abs(v - pp_result[name][0]) for v in values))
    print(f"  Transient Stability without events: bus voltages within {worst:.1e} pu of the load flow")
    assert worst < V_TOL_PU, worst


def main() -> None:
    if not ae._HAS_ANDES:
        print("SKIP: ANDES is not installed.")
        return
    pp_result = pandapower_load_flow()
    print("ANDES power flow vs pandapower load flow:")
    test_power_flow(pp_result)
    test_transient_start(pp_result)
    print("ANDES transformer ratio OK")


if __name__ == "__main__":
    main()
