"""Text fields on SVC / TCSC / SSC / Ward / Extended Ward are converted before pandapower sees them.

- "controllable": "false" reached pandapower as a non-empty string, which counts as True, so an
  SVC the user set to fixed still regulated its bus voltage.
- Empty or "null" numeric fields crashed the study ("could not convert string to float").

Run with ``python samples/test_facts_ward_fields.py``.
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


def network(controllable):
    return {
        "0": {"typ": "PowerFlowPandaPower Parameters", "frequency": "50", "algorithm": "nr",
              "calculate_voltage_angles": "auto", "initialization": "auto", "user_email": "t@e.com"},
        "1": {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_a", "vm_pu": "1",
              "va_degree": "0", "s_sc_max_mva": "1000", "in_service": "true", "userFriendlyName": "Grid"},
        "2": {"typ": "Bus0", "name": "mxCell_a", "id": "a", "vn_kv": "110", "userFriendlyName": "A"},
        "3": {"typ": "Bus1", "name": "mxCell_b", "id": "b", "vn_kv": "110", "userFriendlyName": "B"},
        "4": {"typ": "Line0", "name": "mxCell_l", "id": "l", "busFrom": "mxCell_a", "busTo": "mxCell_b",
              "r_ohm_per_km": "0.06", "x_ohm_per_km": "0.4", "c_nf_per_km": "9", "g_us_per_km": "0",
              "length_km": "30", "max_i_ka": "0.6", "type": "ol", "parallel": "1", "df": "1",
              "in_service": "true", "userFriendlyName": "L"},
        "5": {"typ": "Load0", "name": "mxCell_ld", "id": "ld", "bus": "mxCell_b", "p_mw": "60", "q_mvar": "30",
              "const_z_percent": "0", "const_i_percent": "0", "sn_mva": "null", "scaling": "1", "type": "wye",
              "in_service": "true", "userFriendlyName": "Load"},
        "6": {"typ": "SVC0", "name": "mxCell_svc", "id": "svc", "bus": "mxCell_b", "x_l_ohm": "1",
              "x_cvar_ohm": "-10", "set_vm_pu": "1.0", "thyristor_firing_angle_degree": "145",
              "controllable": controllable, "min_angle_degree": "90", "max_angle_degree": "180",
              "in_service": "true", "userFriendlyName": "SVC"},
        # Ward with optional fields left empty / null.
        "7": {"typ": "Ward0", "name": "mxCell_w", "id": "w", "bus": "mxCell_b", "ps_mw": "1", "qs_mvar": "",
              "pz_mw": None, "qz_mvar": "null", "in_service": "true", "userFriendlyName": "Ward"},
    }


def vm_b(controllable):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=network(controllable))
    data = json.loads(response.data)
    assert response.status_code == 200 and not data.get("error"), data.get("message") or data
    return next(b["vm_pu"] for b in data["busbars"] if b["id"] == "b")


def main() -> None:
    regulated = vm_b("true")
    fixed = vm_b("false")
    print(f"SVC controllable: V(B) = {regulated:.4f} pu; fixed: V(B) = {fixed:.4f} pu")
    assert abs(regulated - 1.0) < 1e-3, "a controllable SVC holds its set point"
    assert abs(fixed - 1.0) > 5e-3, "an SVC set to fixed must not regulate"
    print("FACTS / ward text fields OK")


if __name__ == "__main__":
    main()
