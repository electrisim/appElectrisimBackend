"""Diagram fields sent as JSON null must not crash a study.

Template cells (e.g. the BESS utility-scale HV template) can lack optional attributes, and
the app then sends null. BESS Sizing on that template failed with "float() argument must
be a string or a real number, not 'NoneType'" because a Line had g_us_per_km = null.

Run with ``python samples/test_null_fields.py``.
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


def network():
    return {
        "1": {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_poc", "vm_pu": "1",
              "va_degree": "0", "s_sc_max_mva": "10000", "s_sc_min_mva": None, "rx_max": None, "rx_min": None,
              "r0x0_max": None, "x0x_max": None, "in_service": "true", "userFriendlyName": "Grid"},
        "2": {"typ": "Bus0", "name": "mxCell_poc", "id": "poc", "vn_kv": "33", "userFriendlyName": "POC"},
        "3": {"typ": "Bus1", "name": "mxCell_mv", "id": "mv", "vn_kv": "33", "userFriendlyName": "MV"},
        "4": {"typ": "Line0", "name": "mxCell_l", "id": "l", "busFrom": "mxCell_poc", "busTo": "mxCell_mv",
              "length_km": "0.3", "parallel": "1", "df": "1.0", "in_service": "true", "r_ohm_per_km": "0.08",
              "x_ohm_per_km": "0.12", "c_nf_per_km": None, "g_us_per_km": None, "max_i_ka": "0.5", "type": None,
              "userFriendlyName": "Cable"},
        "5": {"typ": "Load0", "name": "mxCell_ld", "id": "aux", "bus": "mxCell_mv", "p_mw": "0.5", "q_mvar": "0.1",
              "const_z_percent": None, "const_i_percent": None, "sn_mva": "1", "scaling": None, "type": None,
              "in_service": "true", "userFriendlyName": "Aux"},
        "6": {"typ": "Storage0", "name": "mxCell_st", "id": "storage_0", "bus": "mxCell_mv", "p_mw": "0",
              "q_mvar": "0", "max_e_mwh": "24", "min_e_mwh": None, "soc_percent": None, "sn_mva": "15",
              "scaling": None, "type": None, "in_service": "true", "max_p_mw": "12", "min_p_mw": "-12",
              "max_q_mvar": "9", "min_q_mvar": "-9", "userFriendlyName": "BESS"},
    }


def post(payload):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=payload)
    assert response.status_code == 200, response.data[:400]
    return json.loads(response.data)


def main() -> None:
    sizing = network()
    sizing["bess_sizing_params"] = {
        "typ": "BessSizingPandaPower", "storageId": "storage_0", "pocBusbarId": "poc", "calculationMode": "single",
        "tolerance": 0.001, "maxIterations": 50, "kpP": 0.5, "kpQ": 0.5, "frequency": 50, "algorithm": "nr",
        "targetP": 8, "targetQ": 2, "user_email": "t@e.com"}
    data = post(sizing)
    assert data.get("converged") is True, data
    assert abs(float(data["achieved_p_mw"]) - 8.0) < 0.05, data
    print(f"BESS sizing with null fields OK: {float(data['bess_p_mw']):.2f} MW")

    lf = network()
    lf["0"] = {"typ": "PowerFlowPandaPower Parameters", "frequency": "50", "algorithm": "nr",
               "calculate_voltage_angles": "auto", "initialization": "auto", "user_email": "t@e.com"}
    # The IEEE LV European template's Asymmetric Loads carry sn_mva "null" (every study failed
    # with "could not convert string to float: 'null'").
    lf["8"] = {"typ": "Asymmetric Load0", "name": "mxCell_al", "id": "al", "bus": "mxCell_mv",
               "p_a_mw": "0.01", "p_b_mw": "0", "p_c_mw": "0", "q_a_mvar": "0.002", "q_b_mvar": "0",
               "q_c_mvar": "0", "sn_mva": "null", "scaling": None, "type": None, "in_service": "true",
               "userFriendlyName": "House"}
    data = post(lf)
    assert not data.get("error"), data.get("error") or data.get("message")
    assert [ln["id"] for ln in data.get("lines", [])] == ["l"], data.get("lines")
    print("load flow with null fields OK")
    del lf["8"]

    # A line with a loose end is left out, and the user is told (it used to vanish silently).
    lf["7"] = dict(lf["4"], typ="Line1", name="mxCell_l2", id="l2", busTo=None, userFriendlyName="Loose")
    data = post(lf)
    assert not data.get("error"), data.get("error")
    assert any("Line 'Loose'" in w for w in data.get("warnings") or []), data.get("warnings")
    print("loose line warning OK")

    # An empty diagram, or one with no source, gets a plain message instead of a pandapower KeyError.
    data = post({"0": lf["0"]})
    assert data.get("error") and "no buses" in data.get("message", ""), data
    sc_params = {"typ": "ShortCircuitPandaPower Parameters", "fault_type": "3ph", "fault_location": "max",
                 "fault_bus_mode": "all", "tk_s": "1", "r_fault_ohm": "0", "x_fault_ohm": "0",
                 "user_email": "t@e.com"}
    data = post({"0": sc_params})
    assert data.get("error") and "no buses" in data.get("message", ""), data
    sourceless = {k: v for k, v in network().items() if not v["typ"].startswith("External Grid")}
    sourceless["0"] = sc_params
    data = post(sourceless)
    assert data.get("error") and "no in-service source" in data.get("message", ""), data
    print("empty / sourceless diagram messages OK")


if __name__ == "__main__":
    main()
