"""Short circuit on a diagram with an asynchronous Motor.

The Motor's rated power factor (Rated Power Factor in the dialog, cos_phi_n) was never passed
to pandapower, so every IEC and ANSI short circuit with a motor failed with
"cos_phi_n needs to be specified for all motors in net.motor.cos_phi_n", whatever the user
typed. A motor left at 0 now falls back to its running cos phi.

Run with ``python samples/test_sc_motor.py``.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app  # noqa: E402


def payload(study="iec", motor_in_service="true", **motor):
    if study == "iec":
        settings = {"typ": "ShortCircuitPandaPower Parameters", "fault_type": "3ph", "fault_location": "max",
                    "fault_bus_mode": "all", "fault_bus_ids": [], "fault_bus_names": [], "fault_impedance": "6",
                    "topology": "auto", "tk_s": "1", "r_fault_ohm": "0", "x_fault_ohm": "0",
                    "inverse_y": "True", "exportPython": False, "user_email": "t@e.com"}
    else:
        settings = {"typ": "ShortCircuitAnsi Parameters", "fault_type": "3ph", "frequency_hz": "60",
                    "prefault_v_pu": "1.0", "user_email": "t@e.com"}
    # Motor as in the user's report: 13.8 kV, cos phi 0.7, LRC 6 p.u., R/X 2.
    m = {"typ": "Motor0", "name": "mxCell_m", "id": "m", "userFriendlyName": "M1", "bus": "mxCell_mv",
         "pn_mech_mw": "2", "cos_phi": "0.7", "efficiency_percent": "95", "loading_percent": "100",
         "scaling": "1", "cos_phi_n": "0.7", "efficiency_n_percent": "95", "lrc_pu": "6", "rx": "2",
         "vn_kv": "13.8", "in_service": motor_in_service}
    m.update(motor)
    return {
        "0": settings,
        "1": {"typ": "Bus0", "name": "mxCell_hv", "id": "hv", "vn_kv": "115", "userFriendlyName": "HV"},
        "2": {"typ": "Bus1", "name": "mxCell_mv", "id": "mv", "vn_kv": "13.8", "userFriendlyName": "MV"},
        "3": {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_hv", "vm_pu": "1",
              "va_degree": "0", "s_sc_max_mva": "2000", "s_sc_min_mva": "1500", "rx_max": "0.1",
              "rx_min": "0.1", "r0x0_max": "0.1", "x0x_max": "1", "r0x0_min": "0.1", "x0x_min": "1",
              "in_service": "true", "userFriendlyName": "Grid"},
        "4": {"typ": "Transformer0", "name": "mxCell_tr", "id": "tr", "hv_bus": "mxCell_hv", "lv_bus": "mxCell_mv",
              "sn_mva": "20", "vn_hv_kv": "115", "vn_lv_kv": "13.8", "vkr_percent": "0.5", "vk_percent": "10",
              "pfe_kw": "0", "i0_percent": "0", "shift_degree": "0", "tap_pos": "0", "tap_neutral": "0",
              "tap_max": "2", "tap_min": "-2", "tap_step_percent": "2.5", "tap_side": "hv", "parallel": "1",
              "in_service": "true", "userFriendlyName": "TR"},
        "5": m,
    }


def solve(*args, **kw):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=payload(*args, **kw))
    assert response.status_code == 200, response.data[:400]
    data = json.loads(response.data)
    assert not data.get("error"), data.get("message") or data
    return data


def ikss(data, bus_id="mv"):
    bus = next(b for b in data["busbars"] if b["id"] == bus_id)
    return float(bus.get("ikss_ka") if bus.get("ikss_ka") is not None else bus["i_first_sym_ka"])


def main() -> None:
    for study in ("iec", "ansi"):
        with_motor = ikss(solve(study))
        without = ikss(solve(study, motor_in_service="false"))
        print(f"{study}: Ik at MV = {with_motor:.3f} kA (no motor {without:.3f} kA)")
        assert with_motor > without + 0.05, f"{study}: the motor must feed the fault"

    # Rated power factor left at 0 (a new motor's dialog value) falls back to cos_phi.
    zero = ikss(solve("iec", cos_phi_n="0"))
    assert abs(zero - ikss(solve("iec"))) < 1e-6, zero

    # The rated power factor is what sizes the motor, not the running one.
    assert ikss(solve("iec", cos_phi_n="0.9")) < ikss(solve("iec")), "higher cos_phi_n -> smaller Sn"
    assert ikss(solve("ansi", cos_phi="0.9")) == ikss(solve("ansi")), "ANSI must use cos_phi_n"
    print("ok")


if __name__ == "__main__":
    main()
