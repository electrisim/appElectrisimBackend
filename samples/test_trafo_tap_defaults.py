"""Transformer taps and line parallel counts sent as "null" or as whole-number floats.

safe_int fell back to 1 for "null" and for "-1.0", so an imported transformer with no tap
position but a tap step got tap 1 (one step off nominal), "-1.0" became +1, and a line with
parallel "2.0" was built as a single circuit. A missing tap position now means the neutral tap.

Run with ``python samples/test_trafo_tap_defaults.py``.
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


def network(tap_fields, parallel="1"):
    trafo = {"typ": "Transformer0", "name": "mxCell_t", "id": "t1", "hv_bus": "mxCell_b1", "lv_bus": "mxCell_b2",
             "userFriendlyName": "T1", "sn_mva": "40", "vn_hv_kv": "110", "vn_lv_kv": "20", "vkr_percent": "0.3",
             "vk_percent": "12", "pfe_kw": "0", "i0_percent": "0", "vector_group": "Yy", "shift_degree": "0",
             "parallel": "1", "tap_side": "hv", "tap_step_percent": "2.5", "tap_step_degree": "0",
             "in_service": "true", **tap_fields}
    return {
        "0": {"typ": "PowerFlowPandaPower Parameters", "frequency": "50", "algorithm": "nr",
              "calculate_voltage_angles": "auto", "initialization": "auto", "exportPython": False,
              "user_email": "test@example.com"},
        "1": {"typ": "Bus0", "name": "mxCell_b1", "id": "b1", "vn_kv": "110", "userFriendlyName": "B1"},
        "2": {"typ": "Bus1", "name": "mxCell_b2", "id": "b2", "vn_kv": "20", "userFriendlyName": "B2"},
        "3": {"typ": "Bus2", "name": "mxCell_b3", "id": "b3", "vn_kv": "20", "userFriendlyName": "B3"},
        "4": {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_b1",
              "vm_pu": "1.0", "va_degree": "0", "in_service": "true", "userFriendlyName": "Grid",
              "s_sc_max_mva": "1000", "s_sc_min_mva": "800", "rx_max": "0.1", "rx_min": "0.1",
              "r0x0_max": "0.1", "x0x_max": "1.0"},
        "5": trafo,
        "6": {"typ": "Line0", "name": "mxCell_l", "id": "l1", "busFrom": "mxCell_b2", "busTo": "mxCell_b3",
              "userFriendlyName": "L1", "length_km": "10", "parallel": parallel, "df": "1",
              "r_ohm_per_km": "0.2", "x_ohm_per_km": "0.4", "c_nf_per_km": "0", "g_us_per_km": "0",
              "max_i_ka": "0.4", "type": "ol", "in_service": "true"},
        "7": {"typ": "Load0", "name": "mxCell_ld", "id": "ld", "bus": "mxCell_b3", "p_mw": "8", "q_mvar": "2",
              "scaling": "1", "const_z_percent": "0", "const_i_percent": "0", "sn_mva": "0", "type": "wye",
              "in_service": "true", "userFriendlyName": "Load"},
    }


def run(tap_fields, parallel="1"):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=network(tap_fields, parallel))
    assert response.status_code == 200, response.data[:300]
    data = json.loads(response.data)
    assert not data.get("error"), data.get("message") or data.get("error")
    vm = {b["name"]: float(b["vm_pu"]) for b in data["busbars"]}
    loading = next(float(ln["loading_percent"]) for ln in data["lines"])
    return vm["mxCell_b2"], loading


def main() -> None:
    neutral, _ = run({"tap_pos": "0", "tap_neutral": "0", "tap_min": "-9", "tap_max": "9"})
    unset, _ = run({"tap_pos": "null", "tap_neutral": "0", "tap_min": "null", "tap_max": "null"})
    assert abs(unset - neutral) < 1e-9, (unset, neutral)
    all_null, _ = run({"tap_pos": "null", "tap_neutral": "null", "tap_min": "null", "tap_max": "null"})
    assert abs(all_null - neutral) < 1e-9, (all_null, neutral)

    minus_one, _ = run({"tap_pos": "-1", "tap_neutral": "0", "tap_min": "-9", "tap_max": "9"})
    minus_one_float, _ = run({"tap_pos": "-1.0", "tap_neutral": "0.0", "tap_min": "-9.0", "tap_max": "9.0"})
    assert abs(minus_one - minus_one_float) < 1e-9, (minus_one, minus_one_float)
    # An HV-side tap below neutral lowers the HV turns, so the LV voltage rises by about one 2.5 % step.
    assert 0.015 < minus_one - neutral < 0.035, (minus_one, neutral)

    _, one_circuit = run({"tap_pos": "0", "tap_neutral": "0"}, parallel="1")
    _, two_float = run({"tap_pos": "0", "tap_neutral": "0"}, parallel="2.0")
    _, two_int = run({"tap_pos": "0", "tap_neutral": "0"}, parallel="2")
    assert abs(two_float - two_int) < 1e-9, (two_float, two_int)
    assert two_int < 0.6 * one_circuit, (two_int, one_circuit)
    print(f"tap defaults OK: neutral {neutral:.4f} pu, tap -1 {minus_one:.4f} pu; "
          f"line loading 1 circuit {one_circuit:.1f} %, 2 circuits {two_int:.1f} %")


if __name__ == "__main__":
    main()
