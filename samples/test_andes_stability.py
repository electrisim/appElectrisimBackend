# -*- coding: utf-8 -*-
"""
Smoke test for ANDES TDS / EIG Electrisim integration.

Run:
  .venv\\Scripts\\python.exe samples\\test_andes_stability.py

Limitations (MVP):
  - Requires at least one Generator (SynGen); External Grid alone is insufficient
  - Static generators have no SynGen dynamics
  - Three-winding transformers and DC lines are skipped
  - Missing dynamics → GENROU + EXDC2 + TGOV1 defaults
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import andes_electrisim as ae


def _sample_network(params):
    return {
        "0": params,
        "1": {"typ": "Bus0", "name": "mxCell_bus1", "id": "b1", "vn_kv": "230", "userFriendlyName": "Bus1"},
        "2": {"typ": "Bus1", "name": "mxCell_bus2", "id": "b2", "vn_kv": "230", "userFriendlyName": "Bus2"},
        "3": {
            "typ": "Line0",
            "name": "mxCell_line1",
            "id": "l1",
            "busFrom": "mxCell_bus1",
            "busTo": "mxCell_bus2",
            "r_ohm_per_km": "0.05",
            "x_ohm_per_km": "0.5",
            "c_nf_per_km": "8",
            "g_us_per_km": "0",
            "length_km": "100",
            "max_i_ka": "1",
            "type": "ol",
            "userFriendlyName": "Line1",
        },
        "4": {
            "typ": "Load0",
            "name": "mxCell_load1",
            "id": "ld1",
            "bus": "mxCell_bus2",
            "p_mw": "100",
            "q_mvar": "20",
            "scaling": "1",
            "const_z_percent": "0",
            "const_i_percent": "0",
            "sn_mva": "0",
            "type": "wye",
            "userFriendlyName": "Load1",
        },
        "5": {
            "typ": "Generator",
            "name": "mxCell_gen1",
            "id": "g1",
            "bus": "mxCell_bus1",
            "p_mw": "100",
            "vm_pu": "1.0",
            "sn_mva": "200",
            "scaling": "1",
            "vn_kv": "230",
            "slack": "true",
            "userFriendlyName": "Gen1",
        },
        "6": {
            "typ": "Generator",
            "name": "mxCell_gen2",
            "id": "g2",
            "bus": "mxCell_bus2",
            "p_mw": "50",
            "vm_pu": "1.0",
            "sn_mva": "200",
            "scaling": "1",
            "vn_kv": "230",
            "slack": "false",
            "userFriendlyName": "Gen2",
        },
    }


def main():
    assert ae._HAS_ANDES, "ANDES not installed"

    tds_params = {
        "typ": "TransientStabilityAndes Parameters",
        "frequency": "60",
        "sn_mva": "100",
        "tf": "2",
        "fault_bus": "mxCell_bus2",
        "fault_enabled": "true",
        "fault_tf": "0.5",
        "fault_tc": "0.6",
    }
    tds = json.loads(ae.run_tds(_sample_network(tds_params), tds_params))
    assert not tds.get("error"), tds.get("message")
    assert tds.get("converged")
    assert tds.get("n_points", 0) > 10
    assert len(tds.get("omega") or []) >= 1
    print("TDS OK:", tds["n_points"], "points,", len(tds["omega"]), "machines")

    eig_params = {
        "typ": "EigenvalueAndes Parameters",
        "frequency": "60",
        "sn_mva": "100",
        "n_modes": "5",
    }
    eig = json.loads(ae.run_eig(_sample_network(eig_params), eig_params))
    assert not eig.get("error"), eig.get("message")
    assert eig.get("verdict") in ("stable", "marginally_stable", "unstable")
    assert len(eig.get("eigenvalues") or []) > 0
    print("EIG OK:", eig["verdict"], "modes=", len(eig["eigenvalues"]))
    print("All smoke tests passed.")


if __name__ == "__main__":
    main()
