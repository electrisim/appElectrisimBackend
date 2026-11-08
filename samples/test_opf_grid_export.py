"""OPF lets the External Grid take power back when its P limits are not set.

Every template leaves the External Grid at min/max P = 0 / 0 (not set). The backend read that as
"import only" (min_p_mw = 0), so any network that exports, such as a wind farm or the multivoltage
example with its 100 MW generator, had no feasible OPF point. Limits the user does set are kept.

Run with ``python samples/test_opf_grid_export.py``.
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


def network(eg_min="0", eg_max="0"):
    return {
        "0": {"typ": "OptimalPowerFlowPandaPower Parameters", "opf_type": "ac", "frequency": "50",
              "ac_algorithm": "pypower", "dc_algorithm": "pypower", "calculate_voltage_angles": "auto",
              "init": "pf", "delta": "1e-16", "trafo_model": "t", "trafo_loading": "current",
              "ac_line_model": "pi", "numba": True, "suppress_warnings": True, "cost_function": "none",
              "user_email": "t@e.com"},
        "1": {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_a", "vm_pu": "1.0",
              "va_degree": "0", "s_sc_max_mva": "1000", "max_p_mw": eg_max, "min_p_mw": eg_min,
              "max_q_mvar": "0", "min_q_mvar": "0", "controllable": "false", "userFriendlyName": "Grid"},
        "2": {"typ": "Bus0", "name": "mxCell_a", "id": "a", "vn_kv": "110", "min_vm_pu": "0.9", "max_vm_pu": "1.1"},
        "3": {"typ": "Bus1", "name": "mxCell_b", "id": "b", "vn_kv": "110", "min_vm_pu": "0.9", "max_vm_pu": "1.1"},
        "4": {"typ": "Line0", "name": "mxCell_l", "id": "l", "busFrom": "mxCell_a", "busTo": "mxCell_b",
              "r_ohm_per_km": "0.06", "x_ohm_per_km": "0.4", "c_nf_per_km": "9", "g_us_per_km": "0",
              "length_km": "10", "max_i_ka": "0.6", "type": "ol", "parallel": "1", "df": "1",
              "max_loading_percent": "0", "userFriendlyName": "L"},
        "5": {"typ": "Load0", "name": "mxCell_ld", "id": "ld", "bus": "mxCell_b", "p_mw": "10", "q_mvar": "2",
              "const_z_percent": "0", "const_i_percent": "0", "sn_mva": "null", "scaling": "1", "type": "wye",
              "in_service": "true", "userFriendlyName": "Load"},
        "6": {"typ": "Static Generator0", "name": "mxCell_sg", "id": "sg", "bus": "mxCell_b", "p_mw": "30",
              "q_mvar": "0", "sn_mva": "35", "scaling": "1", "type": "wye", "k": "0", "rx": "0",
              "generator_type": "current_source", "lrc_pu": "0", "max_ik_ka": "0", "kappa": "0",
              "current_source": "true", "in_service": "true", "userFriendlyName": "Plant"},
    }


def post(payload):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=payload)
    return json.loads(response.data)


def main() -> None:
    data = post(network())
    assert not data.get("error"), data.get("exception") or data.get("message")
    p_grid = data["externalgrids"][0]["p_mw"]
    assert p_grid < -15, f"the grid must absorb the surplus, got {p_grid} MW"
    print(f"OPF with unset grid limits OK: grid takes {-p_grid:.1f} MW")

    # A limit the user sets (import only) is still respected: the surplus has nowhere to go.
    data = post(network(eg_min="0", eg_max="500"))
    assert data.get("error"), "an import-only grid cannot absorb the plant's surplus"
    print("user-set import-only limit kept")


if __name__ == "__main__":
    main()
