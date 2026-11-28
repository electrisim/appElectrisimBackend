"""Protection Coordination runs its short circuits at the system frequency chosen in the dialog.

app.py built the protection network at pandapower's default 50 Hz and the dialog had no
frequency. On an unearthed (or high-resistance-earthed) system a single-phase fault drives only
the charging current of the cables, which is 6/5 as large at 60 Hz, and that is the current an
earth-fault relay is set against: at 50 Hz a 60 Hz system looked 1/6 weaker than it is, so a
relay set between the two currents was reported as not picking up.

Network: 110 kV grid, YNd 110/20 kV transformer (the 20 kV side has no earth), two 20 kV cables
with C0 = 250 nF/km, an earth-fault relay at the head of each feeder. The request goes through
the Flask route, as the frontend sends it.

Run with ``python samples/test_protection_frequency.py``.
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


def cable(cell, name, bus_from, bus_to, length_km):
    return {"typ": f"Line{cell}", "name": f"mxCell_{name}", "id": name, "userFriendlyName": name.upper(),
            "busFrom": bus_from, "busTo": bus_to, "length_km": length_km, "parallel": "1", "df": "1",
            "in_service": "true", "r_ohm_per_km": "0.1", "x_ohm_per_km": "0.12", "c_nf_per_km": "250",
            "g_us_per_km": "0", "max_i_ka": "0.4", "type": "cs", "r0_ohm_per_km": "0.4",
            "x0_ohm_per_km": "1.0", "c0_nf_per_km": "250", "endtemp_degree": "250"}


def earth_fault_relay(cell, name, line, pickup_a):
    return {"typ": f"Switch{cell}", "id": name, "name": f"mxCell_{name}", "userFriendlyName": name,
            "et": "l", "type": "CB", "closed": "true", "z_ohm": "0", "in_ka": "0.63",
            "bus": "mxCell_mv", "element": line, "protection_type": "earth_fault",
            "I_e_a": str(pickup_a), "t_e": "0.5"}


def payload(frequency=None, pickup_a=1.0):
    params = {"typ": "ProtectionCoordinationPandaPower", "user_email": "t@e.com", "fault_type": "1ph",
              "case": "max", "fault_location_mode": "bus", "fault_bus_id": "fa", "sc_line_id": "all",
              "sc_fraction": 0.5, "grading_mode": "auto", "curve_type": "standard_inverse",
              "t_diff": 0.3, "t_g": 0.5, "t_gg": 0.07, "tms": 1.0, "t_grade": 0.5,
              "overload_factor": 1.25, "ct_current_factor": 1.2, "safety_factor": 1.0,
              "export_results": False}
    if frequency is not None:
        params["frequency"] = frequency
    return {
        "0": params,
        "1": {"typ": "Bus0", "name": "mxCell_hv", "id": "hv", "vn_kv": "110", "userFriendlyName": "HV"},
        "2": {"typ": "Bus1", "name": "mxCell_mv", "id": "mv", "vn_kv": "20", "userFriendlyName": "MV"},
        "3": {"typ": "Bus2", "name": "mxCell_fa", "id": "fa", "vn_kv": "20", "userFriendlyName": "FA"},
        "4": {"typ": "Bus3", "name": "mxCell_fb", "id": "fb", "vn_kv": "20", "userFriendlyName": "FB"},
        "5": {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_hv", "vm_pu": "1.0",
              "va_degree": "0", "s_sc_max_mva": "5000", "s_sc_min_mva": "4000", "rx_max": "0.1",
              "rx_min": "0.1", "r0x0_max": "0.1", "x0x_max": "1.0", "r0x0_min": "0.1", "x0x_min": "1.0",
              "in_service": "true"},
        "6": {"typ": "Transformer0", "name": "mxCell_t1", "id": "t1", "userFriendlyName": "T1",
              "hv_bus": "mxCell_hv", "lv_bus": "mxCell_mv", "sn_mva": "40", "vn_hv_kv": "110",
              "vn_lv_kv": "20", "vkr_percent": "0.4", "vk_percent": "12", "pfe_kw": "0", "i0_percent": "0",
              "vector_group": "YNd", "vk0_percent": "12", "vkr0_percent": "0.4", "mag0_percent": "100",
              "si0_hv_partial": "0.9", "parallel": "1", "shift_degree": "150", "tap_side": "hv",
              "tap_pos": "0", "tap_neutral": "0", "tap_max": "9", "tap_min": "-9",
              "tap_step_percent": "1.5", "tap_step_degree": "0", "tap_phase_shifter": "false",
              "in_service": "true"},
        "7": cable(0, "la", "mxCell_mv", "mxCell_fa", "5"),
        "8": cable(1, "lb", "mxCell_mv", "mxCell_fb", "10"),
        "9": earth_fault_relay(0, "EF-A", "mxCell_la", pickup_a),
        "10": earth_fault_relay(1, "EF-B", "mxCell_lb", pickup_a),
    }


def run(frequency=None, pickup_a=1.0):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=payload(frequency, pickup_a))
    assert response.status_code == 200, response.data[:400]
    body = response.data
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    data = json.loads(body)
    assert not data.get("error"), data.get("message") or data
    assert len(data["scenarios"]) == 1 and not data["scenarios"][0].get("error"), data["scenarios"]
    return data


def fault_current_ka(data):
    return data["scenarios"][0]["short_circuit"]["ikss_ka"]


def relay(data, name):
    rows = [t for t in data["scenarios"][0]["trip"] if t.get("user_friendly_name") == name]
    assert len(rows) == 1, data["scenarios"][0]["trip"]
    return rows[0]


def single_phase_charging_current() -> None:
    at50, at60 = run("50"), run("60")
    i50, i60 = fault_current_ka(at50), fault_current_ka(at60)
    # 15 km of cable at 250 nF/km: c * 3 * w * C0 * U / sqrt(3) is about 45 A at 50 Hz.
    assert 0.02 < i50 < 0.1, f"unearthed 20 kV: expected charging current only, got {i50} kA"
    assert abs(i60 / i50 - 1.2) < 0.01, f"60 Hz {i60} kA vs 50 Hz {i50} kA: charging current is 6/5 at 60 Hz"
    assert at50["summary"]["frequency_hz"] == 50.0, at50["summary"]
    assert at60["summary"]["frequency_hz"] == 60.0, at60["summary"]
    print(f"1ph fault at FA (unearthed 20 kV): {i50 * 1000:.1f} A at 50 Hz, {i60 * 1000:.1f} A at 60 Hz")


def earth_fault_relay_pickup() -> None:
    # The relay of the faulted feeder, set 10 % above the current it measures at 50 Hz, picks the
    # fault up only on a 60 Hz system.
    i_relay_50 = 1000.0 * relay(run("50"), "EF-A")["ikss_ka"]
    pickup = 1.1 * i_relay_50
    at50 = relay(run("50", pickup), "EF-A")
    at60 = relay(run("60", pickup), "EF-A")
    assert not at50["tripped"], at50
    assert at60["tripped"] and at60["t_trip_s"] == 0.5, at60
    print(f"EF-A set at {pickup:.1f} A: no trip at 50 Hz, trips at 60 Hz "
          f"({1000.0 * at60['ikss_ka']:.1f} A)")


def defaults() -> None:
    # Requests without a frequency (older frontends, saved API calls) keep 50 Hz.
    no_frequency = run()
    assert no_frequency["summary"]["frequency_hz"] == 50.0, no_frequency["summary"]
    assert abs(fault_current_ka(no_frequency) / fault_current_ka(run("50")) - 1) < 1e-9
    # IEC 60909 defines 50 and 60 Hz systems (kappa method C: fc = 20 or 24 Hz).
    assert run("59.94")["summary"]["frequency_hz"] == 60.0
    print("no frequency -> 50 Hz, 59.94 Hz -> 60 Hz")


if __name__ == "__main__":
    single_phase_charging_current()
    earth_fault_relay_pickup()
    defaults()
    print("protection coordination frequency OK")
