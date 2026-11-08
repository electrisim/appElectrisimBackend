"""A failed OPF says why when nothing is controllable.

The onshore wind farm template holds the grid at 1.1 pu with every bus limited to 1.1 pu, and its
turbines are not controllable, so OPF could only check a point that is above 1.1 pu. The user saw
"did not converge" with generic tips; the message now names the broken voltage limits.

Run with ``python samples/test_opf_infeasible_hint.py``.
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
        "0": {"typ": "OptimalPowerFlowPandaPower Parameters", "opf_type": "ac", "frequency": "50",
              "ac_algorithm": "pypower", "dc_algorithm": "pypower", "calculate_voltage_angles": "auto",
              "init": "pf", "delta": "1e-16", "trafo_model": "t", "trafo_loading": "current",
              "ac_line_model": "pi", "numba": True, "suppress_warnings": True, "cost_function": "none",
              "user_email": "t@e.com"},
        "1": {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_a", "vm_pu": "1.1",
              "va_degree": "0", "s_sc_max_mva": "1000", "max_p_mw": "0", "min_p_mw": "0", "max_q_mvar": "0",
              "min_q_mvar": "0", "controllable": "false", "userFriendlyName": "Grid"},
        "2": {"typ": "Bus0", "name": "mxCell_a", "id": "a", "vn_kv": "30", "min_vm_pu": "0.9", "max_vm_pu": "1.1"},
        "3": {"typ": "Bus1", "name": "mxCell_b", "id": "b", "vn_kv": "30", "min_vm_pu": "0.9", "max_vm_pu": "1.1"},
        "4": {"typ": "Line0", "name": "mxCell_l", "id": "l", "busFrom": "mxCell_a", "busTo": "mxCell_b",
              "r_ohm_per_km": "0.15", "x_ohm_per_km": "0.17", "c_nf_per_km": "100", "g_us_per_km": "0",
              "length_km": "10", "max_i_ka": "0.6", "type": "cs", "parallel": "1", "df": "1",
              "max_loading_percent": "0", "userFriendlyName": "L"},
        "5": {"typ": "Static Generator0", "name": "mxCell_sg", "id": "sg", "bus": "mxCell_b", "p_mw": "20",
              "q_mvar": "5", "sn_mva": "25", "scaling": "1", "type": "wye", "k": "0", "rx": "0",
              "generator_type": "current_source", "lrc_pu": "0", "max_ik_ka": "0", "kappa": "0",
              "current_source": "true", "in_service": "true", "userFriendlyName": "Park"},
    }


def main() -> None:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=network())
    data = json.loads(response.data)
    assert data.get("error"), "OPF of this fixed, over-voltage point must fail"
    text = data.get("exception", "")
    assert "Likely cause" in text and "controllable" in text, text
    assert "above their voltage limit" in text, text
    print("OPF infeasibility hint OK")


if __name__ == "__main__":
    main()
