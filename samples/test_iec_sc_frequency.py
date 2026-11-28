"""The IEC 60909 short circuit runs at the system frequency chosen in the dialog.

app.py built every IEC short-circuit network at pandapower's default 50 Hz and the dialog had
no frequency, so a 60 Hz system got:
* the DC time constant and DC component of the breaking current at 50 Hz (tau = X/R / (2 pi f)),
* the line charging (C0) of the zero sequence at 50 Hz: on an unearthed system a single-phase
  fault only drives that charging current, which came out at 50/60 of the right value.

Network: 110 kV grid, YNd 110/20 kV transformer (the 20 kV side has no earth), 10 km 20 kV
cable with C0 = 250 nF/km. The request goes through the Flask route, as the frontend sends it.

Run with ``python samples/test_iec_sc_frequency.py``.
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


def payload(fault, frequency=None, export_python=False):
    params = {"typ": "ShortCircuitPandaPower Parameters", "fault_type": fault, "fault_location": "max",
              "fault_bus_mode": "all", "fault_bus_ids": [], "fault_bus_names": [], "fault_impedance": "6",
              "topology": "auto", "tk_s": "1", "t_min_ms": "50", "r_fault_ohm": "0", "x_fault_ohm": "0",
              "inverse_y": "True", "exportPython": export_python, "exportPandapowerResults": False,
              "exportPdfReport": False, "user_email": "t@e.com"}
    if frequency is not None:
        params["frequency"] = frequency
    return {
        "0": params,
        "1": {"typ": "Bus0", "name": "mxCell_hv", "id": "hv", "vn_kv": "110", "userFriendlyName": "HV"},
        "2": {"typ": "Bus1", "name": "mxCell_mv", "id": "mv", "vn_kv": "20", "userFriendlyName": "MV"},
        "3": {"typ": "Bus2", "name": "mxCell_far", "id": "far", "vn_kv": "20", "userFriendlyName": "FAR"},
        "4": {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_hv", "vm_pu": "1.0",
              "va_degree": "0", "s_sc_max_mva": "5000", "s_sc_min_mva": "4000", "rx_max": "0.1",
              "rx_min": "0.1", "r0x0_max": "0.1", "x0x_max": "1.0", "r0x0_min": "0.1", "x0x_min": "1.0",
              "in_service": "true"},
        "5": {"typ": "Transformer0", "name": "mxCell_t1", "id": "t1", "userFriendlyName": "T1",
              "hv_bus": "mxCell_hv", "lv_bus": "mxCell_mv", "sn_mva": "40", "vn_hv_kv": "110",
              "vn_lv_kv": "20", "vkr_percent": "0.4", "vk_percent": "12", "pfe_kw": "0", "i0_percent": "0",
              "vector_group": "YNd", "vk0_percent": "12", "vkr0_percent": "0.4", "mag0_percent": "100",
              "si0_hv_partial": "0.9", "parallel": "1", "shift_degree": "150", "tap_side": "hv",
              "tap_pos": "0", "tap_neutral": "0", "tap_max": "9", "tap_min": "-9",
              "tap_step_percent": "1.5", "tap_step_degree": "0", "tap_phase_shifter": "false",
              "in_service": "true"},
        "6": {"typ": "Line0", "name": "mxCell_l1", "id": "l1", "userFriendlyName": "CABLE",
              "busFrom": "mxCell_mv", "busTo": "mxCell_far", "length_km": "10", "parallel": "1", "df": "1",
              "in_service": "true", "r_ohm_per_km": "0.1", "x_ohm_per_km": "0.12", "c_nf_per_km": "250",
              "g_us_per_km": "0", "max_i_ka": "0.5", "type": "cs", "r0_ohm_per_km": "0.4",
              "x0_ohm_per_km": "1.0", "c0_nf_per_km": "250", "endtemp_degree": "250"},
    }


def run(fault, frequency=None, export_python=False):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=payload(fault, frequency, export_python))
    assert response.status_code == 200, response.data[:400]
    data = json.loads(response.data)
    assert not data.get("error"), data
    return data


def buses(data):
    return {b["name"]: b for b in data["busbars"]}


def three_phase_dc_decay() -> None:
    at50, at60 = run("3ph", "50"), run("3ph", "60")
    assert at50["study_params"]["frequency_hz"] == 50.0, at50["study_params"]
    assert at60["study_params"]["frequency_hz"] == 60.0, at60["study_params"]
    b50, b60 = buses(at50), buses(at60)
    for name in b50:
        assert abs(b60[name]["ikss_ka"] / b50[name]["ikss_ka"] - 1) < 1e-9, (name, b50[name], b60[name])
        # Same X/R, so the DC time constant X/R / (2 pi f) is 5/6 as long at 60 Hz ...
        assert abs(b60[name]["tau_dc_ms"] / b50[name]["tau_dc_ms"] - 5 / 6) < 1e-9, (name, b50[name], b60[name])
        # ... and the DC component left at t_min = 50 ms is smaller.
        assert b60[name]["idc_ka"] < b50[name]["idc_ka"], (name, b50[name], b60[name])
    hv50, hv60 = b50["mxCell_hv"], b60["mxCell_hv"]
    print(f"3ph HV: tau {hv50['tau_dc_ms']:.2f} ms at 50 Hz, {hv60['tau_dc_ms']:.2f} ms at 60 Hz; "
          f"Idc(50 ms) {hv50['idc_ka']:.3f} -> {hv60['idc_ka']:.3f} kA")


def single_phase_charging_current() -> None:
    i50 = buses(run("1ph", "50"))["mxCell_mv"]["ikss_ka"]
    i60 = buses(run("1ph", "60"))["mxCell_mv"]["ikss_ka"]
    assert i50 < 0.1, f"unearthed 20 kV: expected charging current only, got {i50} kA"
    assert abs(i60 / i50 - 1.2) < 0.01, f"60 Hz {i60} kA vs 50 Hz {i50} kA: charging current is 6/5 at 60 Hz"
    print(f"1ph MV (unearthed): {i50 * 1000:.1f} A at 50 Hz, {i60 * 1000:.1f} A at 60 Hz")


def defaults_and_python_export() -> None:
    # Requests without a frequency (older frontends, saved API calls) keep 50 Hz.
    assert run("3ph")["study_params"]["frequency_hz"] == 50.0
    # IEC 60909 defines 50 and 60 Hz systems (kappa method C: fc = 20 or 24 Hz).
    assert run("3ph", "59.94")["study_params"]["frequency_hz"] == 60.0
    code = run("3ph", "60", export_python=True).get("pandapower_python") or ""
    assert "create_empty_network(f_hz=60.0)" in code, code[:400]
    print("no frequency -> 50 Hz, 59.94 Hz -> 60 Hz, Python export at 60 Hz")


if __name__ == "__main__":
    three_phase_dc_decay()
    single_phase_charging_current()
    defaults_and_python_export()
    print("IEC short-circuit frequency OK")
