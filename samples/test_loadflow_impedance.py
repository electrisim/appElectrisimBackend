"""Load flow through an Impedance element.

The diagram stores an Impedance as r_pu/x_pu, but the load flow sent rft_pu/xft_pu read
from attributes that do not exist, so every load flow with an Impedance failed with
"*ft_pu parameters are missing". The backend now accepts either name.

Run with ``python samples/test_loadflow_impedance.py``.
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


def network(impedance_fields):
    return {
        "0": {"typ": "PowerFlowPandaPower Parameters", "frequency": "50", "algorithm": "nr",
              "calculate_voltage_angles": "auto", "initialization": "auto", "exportPython": False,
              "user_email": "test@example.com"},
        "1": {"typ": "Bus0", "name": "mxCell_b1", "id": "b1", "vn_kv": "20", "userFriendlyName": "B1"},
        "2": {"typ": "Bus1", "name": "mxCell_b2", "id": "b2", "vn_kv": "20", "userFriendlyName": "B2"},
        "3": {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_b1",
              "vm_pu": "1.0", "va_degree": "0", "in_service": "true", "userFriendlyName": "Grid",
              "s_sc_max_mva": "1000", "s_sc_min_mva": "800", "rx_max": "0.1", "rx_min": "0.1",
              "r0x0_max": "0.1", "x0x_max": "1.0"},
        "4": {"typ": "Impedance0", "name": "mxCell_z", "id": "z1", "busFrom": "mxCell_b1", "busTo": "mxCell_b2",
              "sn_mva": "10", "in_service": "true", "userFriendlyName": "Z1", **impedance_fields},
        "5": {"typ": "Load0", "name": "mxCell_ld", "id": "ld", "bus": "mxCell_b2", "p_mw": "5", "q_mvar": "1",
              "scaling": "1", "const_z_percent": "0", "const_i_percent": "0", "sn_mva": "0", "type": "wye",
              "in_service": "true", "userFriendlyName": "Load"},
    }


def vm_b2(impedance_fields):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=network(impedance_fields))
    assert response.status_code == 200, response.data[:300]
    data = json.loads(response.data)
    assert not data.get("error"), data.get("error")
    return next(float(b["vm_pu"]) for b in data["busbars"] if b["name"] == "mxCell_b2")


def main() -> None:
    by_diagram_name = vm_b2({"r_pu": "0.01", "x_pu": "0.05"})
    by_payload_name = vm_b2({"rft_pu": "0.01", "xft_pu": "0.05"})
    assert abs(by_diagram_name - by_payload_name) < 1e-9
    # 5 MW + 1 Mvar through 0.01 + j0.05 pu on a 10 MVA base drops the voltage by a few percent.
    assert 0.9 < by_diagram_name < 0.99, by_diagram_name
    print(f"Impedance load flow OK: B2 at {by_diagram_name:.4f} pu")


if __name__ == "__main__":
    main()
