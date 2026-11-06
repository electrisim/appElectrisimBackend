"""Contingency analysis must report buses an outage cuts off.

Disconnected buses get no voltage (NaN) from the load flow, so the voltage-limit check
never flagged them: an outage that tripped a generator or dropped a load showed as clean.

Network: grid at A, a meshed pair of lines A-B, and a radial line B-C feeding a load and
a generator at C. Losing either A-B line is fine; losing B-C islands bus C.

Run with ``python samples/test_contingency_islanding.py``.
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


def line(key, name, a, b):
    return {"typ": f"Line{key}", "name": name, "id": name, "busFrom": a, "busTo": b,
            "r_ohm_per_km": "0.06", "x_ohm_per_km": "0.4", "c_nf_per_km": "9", "g_us_per_km": "0",
            "length_km": "20", "max_i_ka": "0.6", "type": "ol", "parallel": "1", "df": "1",
            "in_service": "true", "userFriendlyName": name}


def main() -> None:
    payload = {
        "0": {"typ": "ContingencyAnalysisPandaPower Parameters", "contingency_type": "N-1", "element_type": "all",
              "elements_to_analyze": "all", "voltage_limits": "true", "thermal_limits": "true",
              "min_vm_pu": "0.9", "max_vm_pu": "1.1", "max_loading_percent": "100", "user_email": "t@e.com"},
        "1": {"typ": "Bus0", "name": "mxCell_a", "id": "a", "vn_kv": "110", "userFriendlyName": "A"},
        "2": {"typ": "Bus1", "name": "mxCell_b", "id": "b", "vn_kv": "110", "userFriendlyName": "B"},
        "3": {"typ": "Bus2", "name": "mxCell_c", "id": "c", "vn_kv": "110", "userFriendlyName": "C"},
        "4": {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_a", "vm_pu": "1.0",
              "va_degree": "0", "s_sc_max_mva": "1000", "s_sc_min_mva": "800", "rx_max": "0.1", "rx_min": "0.1",
              "r0x0_max": "0.1", "x0x_max": "1.0", "in_service": "true"},
        "5": line(0, "AB1", "mxCell_a", "mxCell_b"),
        "6": line(1, "AB2", "mxCell_a", "mxCell_b"),
        "7": line(2, "BC", "mxCell_b", "mxCell_c"),
        "8": {"typ": "Load0", "name": "mxCell_ld", "id": "ld", "bus": "mxCell_c", "p_mw": "20", "q_mvar": "5",
              "scaling": "1", "const_z_percent": "0", "const_i_percent": "0", "sn_mva": "0", "type": "wye",
              "in_service": "true", "userFriendlyName": "Load"},
        "9": {"typ": "Static Generator0", "name": "mxCell_sg", "id": "sg", "bus": "mxCell_c", "p_mw": "8",
              "q_mvar": "0", "sn_mva": "10", "scaling": "1", "type": "wye", "k": "1.2", "rx": "0.1",
              "generator_type": "async", "lrc_pu": "1", "max_ik_ka": "0", "kappa": "1", "current_source": "true",
              "in_service": "true", "userFriendlyName": "PV"},
    }
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=payload)
    assert response.status_code == 200, response.data[:400]
    data = json.loads(response.data)
    assert not data.get("error"), data.get("error")

    cases = {c["description"]: c for c in data["contingency_results"]}
    bc = next(c for d, c in cases.items() if "BC" in d)
    islanding = [v for v in bc["violations"] if v["type"] == "islanding"]
    assert islanding, bc["violations"]
    text = islanding[0]["description"]
    print("BC outage:", text)
    assert "1 bus(es) disconnected: C" in text, text
    assert "20.0 MW load" in text and "8.0 MW generation" in text, text
    assert any(c["name"] == bc["name"] for c in data["summary"]["critical_contingencies"])

    ab1 = next(c for d, c in cases.items() if "AB1" in d)
    assert not any(v["type"] == "islanding" for v in ab1["violations"]), ab1["violations"]
    print("contingency islanding OK")


if __name__ == "__main__":
    main()
