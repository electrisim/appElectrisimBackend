"""Motor Starting runs at the system frequency chosen in the dialog.

The steady-state mode built its pandapower network at the default 50 Hz whatever the request
said, so on a 60 Hz system the load flows before, during and after the start carried only 5/6 of
the cable charging. The dynamic (ANDES) mode reads the frequency from the same request; it is
checked here too, because the Motor3 rated frequency sets the synchronous speed the slip is
measured from (Motor3 defaults to 60 Hz when it is not given).

Network: 20 kV grid (1.0 pu), 20 km cable with C = 300 nF/km, a 1 MW motor at the far end. The
requests go through the Flask route, as the frontend sends them.

Run with ``python samples/test_motor_starting_frequency.py``.
"""
from __future__ import annotations

import contextlib
import gzip
import io
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app  # noqa: E402
import motor_starting_electrisim as ms  # noqa: E402


def payload(mode, frequency=None):
    params = {"typ": "MotorStartingPandaPower Parameters", "mode": mode, "motor_ids": "all",
              "starting_method": "dol", "i_limit_pu": "3", "at_tap_pu": "0.8", "reactor_x_pu": "0.25",
              "voltage_limit_percent": "15", "thermal_limit_percent": "100", "t_start": "0.1",
              "t_end": "1", "sn_mva": "100", "user_email": "t@e.com"}
    if frequency is not None:
        params["frequency"] = frequency
    if mode == "dynamic":
        # ANDES needs a synchronous machine; the generator is the slack of the dynamic model.
        source = {"typ": "Generator", "name": "mxCell_gen", "id": "gen", "bus": "mxCell_src",
                  "p_mw": "2", "vm_pu": "1.0", "sn_mva": "200", "scaling": "1", "vn_kv": "20",
                  "slack": "true", "userFriendlyName": "Gen"}
    else:
        source = {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_src",
                  "vm_pu": "1.0", "va_degree": "0", "s_sc_max_mva": "500", "s_sc_min_mva": "400",
                  "rx_max": "0.1", "rx_min": "0.1", "r0x0_max": "0.1", "x0x_max": "1",
                  "in_service": "true"}
    return {
        "0": params,
        "1": {"typ": "Bus0", "name": "mxCell_src", "id": "src", "vn_kv": "20", "userFriendlyName": "SRC"},
        "2": {"typ": "Bus1", "name": "mxCell_far", "id": "far", "vn_kv": "20", "userFriendlyName": "FAR"},
        "3": source,
        "4": {"typ": "Line0", "name": "mxCell_cable", "id": "cable", "userFriendlyName": "CABLE",
              "busFrom": "mxCell_src", "busTo": "mxCell_far", "length_km": "20", "parallel": "1",
              "df": "1", "in_service": "true", "r_ohm_per_km": "0.1", "x_ohm_per_km": "0.12",
              "c_nf_per_km": "300", "g_us_per_km": "0", "max_i_ka": "0.4", "type": "cs"},
        "5": {"typ": "Motor0", "name": "mxCell_motor", "id": "motor", "userFriendlyName": "Pump",
              "bus": "mxCell_far", "pn_mech_mw": "1.0", "cos_phi": "0.88", "cos_phi_n": "0.88",
              "efficiency_n_percent": "95", "efficiency_percent": "95", "loading_percent": "100",
              "scaling": "1", "lrc_pu": "6", "rx": "0.3", "vn_kv": "20", "in_service": "true"},
    }


def run(mode, frequency=None):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=payload(mode, frequency))
    assert response.status_code == 200, response.data[:400]
    body = response.data
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    data = json.loads(body)
    assert not data.get("error"), data.get("message") or data
    return data


def far_bus(data):
    return {b["id"]: b for b in data["buses"]}["far"]


def steady_state_cable_charging() -> None:
    at50, at60 = run("steady", "50"), run("steady", "60")
    # The grid holds the source bus at 1.0 pu. Before the start the motor is off and the cable
    # is open-ended, so the far end rises by about B/2 * X, and B = 2 pi f C is 6/5 at 60 Hz.
    rise50 = far_bus(at50)["vm_before"] - 1.0
    rise60 = far_bus(at60)["vm_before"] - 1.0
    assert rise50 > 1e-3, f"expected a Ferranti rise at the open cable end, got {rise50:.5f} pu"
    assert abs(rise60 / rise50 - 1.2) < 0.01, f"rise {rise60:.6f} pu at 60 Hz vs {rise50:.6f} pu at 50 Hz"
    assert at50["summary"]["frequency_hz"] == 50.0, at50["summary"]
    assert at60["summary"]["frequency_hz"] == 60.0, at60["summary"]
    # Requests without a frequency (older frontends, saved API calls) keep 50 Hz.
    no_frequency = run("steady")
    assert no_frequency["summary"]["frequency_hz"] == 50.0, no_frequency["summary"]
    assert abs(far_bus(no_frequency)["vm_before"] - far_bus(at50)["vm_before"]) < 1e-12
    print(f"steady: cable end rises {rise50 * 100:.3f} % at 50 Hz, {rise60 * 100:.3f} % at 60 Hz")


def dynamic_motor3_frequency() -> None:
    if not ms._HAS_ANDES:
        print("SKIP dynamic: ANDES is not installed.")
        return
    built = []
    original = ms._build_system_with_motors

    def capture(*args, **kwargs):
        ss, meta, motor_map = original(*args, **kwargs)
        built.append(ss)
        return ss, meta, motor_map

    ms._build_system_with_motors = capture
    try:
        for frequency, expected in (("60", 60.0), ("50", 50.0), (None, 50.0)):
            built.clear()
            data = run("dynamic", frequency)
            assert len(built) == 1, built
            ss = built[0]
            assert [float(f) for f in ss.Motor3.fn.v] == [expected], (frequency, list(ss.Motor3.fn.v))
            assert float(ss.config.freq) == expected, (frequency, ss.config.freq)
            assert data["summary"]["frequency_hz"] == expected, (frequency, data["summary"])
    finally:
        ms._build_system_with_motors = original
    print("dynamic: ANDES system and Motor3 at 60 Hz / 50 Hz as requested, 50 Hz without a frequency")


if __name__ == "__main__":
    steady_state_cable_charging()
    dynamic_motor3_frequency()
    print("motor starting frequency OK")
