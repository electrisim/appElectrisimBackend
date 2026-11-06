"""Steady-state motor starting, in the payload format the app sends.

The study's settings entry is typed "MotorStartingPandaPower Parameters". It starts with
"Motor", so the element builder used to treat it as a motor and failed with KeyError 'bus'
on every diagram. A motor dropped from the palette also holds 0 for cos phi and efficiency,
which made the load flow diverge; those zeros are now read as "not set".

Run with ``python samples/test_motor_starting_steady.py``.
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


def payload(**motor):
    m = {"typ": "Motor0", "name": "mxCell_m", "id": "m", "userFriendlyName": "Motor", "bus": "mxCell_lv",
         "pn_mech_mw": "0.075", "cos_phi": "0", "efficiency_percent": "0", "loading_percent": "0",
         "scaling": "1", "cos_phi_n": "0", "efficiency_n_percent": "0", "lrc_pu": "0", "rx": "0",
         "vn_kv": "0", "in_service": "true"}
    m.update(motor)
    return {
        "0": {"typ": "MotorStartingPandaPower Parameters", "mode": "steady", "motor_ids": "all",
              "starting_method": "dol", "voltage_limit_percent": "15", "thermal_limit_percent": "100",
              "frequency": "50", "sn_mva": "100", "user_email": "test@example.com"},
        "1": {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_hv", "vm_pu": "1",
              "va_degree": "0", "s_sc_max_mva": "500", "s_sc_min_mva": "400", "rx_max": "0.1", "rx_min": "0.1",
              "r0x0_max": "0.1", "x0x_max": "1", "in_service": "true"},
        "2": {"typ": "Bus0", "name": "mxCell_hv", "id": "hv", "vn_kv": "20", "userFriendlyName": "HV"},
        "3": {"typ": "Bus1", "name": "mxCell_lv", "id": "lv", "vn_kv": "0.4", "userFriendlyName": "LV"},
        "4": {"typ": "Transformer0", "name": "mxCell_tr", "id": "tr", "hv_bus": "mxCell_hv", "lv_bus": "mxCell_lv",
              "sn_mva": "0.63", "vn_hv_kv": "20", "vn_lv_kv": "0.4", "vkr_percent": "1.2", "vk_percent": "6",
              "pfe_kw": "0", "i0_percent": "0", "shift_degree": "150", "tap_pos": "0", "tap_neutral": "0",
              "tap_max": "2", "tap_min": "-2", "tap_step_percent": "2.5", "tap_side": "hv", "parallel": "1",
              "in_service": "true", "userFriendlyName": "TR"},
        "5": {"typ": "Load0", "name": "mxCell_ld", "id": "ld", "bus": "mxCell_lv", "p_mw": "0.2", "q_mvar": "0.05",
              "const_z_percent": "0", "const_i_percent": "0", "sn_mva": "null", "scaling": "1", "type": "wye",
              "in_service": "true"},
        "6": m,
    }


def solve(data):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=data)
    assert response.status_code == 200, response.data[:400]
    result = json.loads(response.data)
    assert not result.get("error"), result
    return result


def main() -> None:
    # Fields left as the palette sets them (zeros).
    result = solve(payload())
    dip = {b["id"]: b["dip_percent"] for b in result["buses"]}
    print(f"default motor: LV dip {dip['lv']:.2f} %")
    assert 1.0 < dip["lv"] < 15.0, dip
    assert result["motors"][0]["vn_kv"] == 0.4, "a zero rated voltage takes the bus voltage"

    # A filled-in motor.
    result = solve(payload(cos_phi="0.85", cos_phi_n="0.85", efficiency_percent="95",
                           efficiency_n_percent="95", loading_percent="100", lrc_pu="7", vn_kv="0.4"))
    motor = result["motors"][0]
    assert abs(motor["lrc_pu"] - 7.0) < 1e-9, motor
    assert abs(motor["i_start_ka"] / motor["i_rated_ka"] - 7.0) < 1e-6, motor
    print("motor starting (steady) OK")


if __name__ == "__main__":
    main()
