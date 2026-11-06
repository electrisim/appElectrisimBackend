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

    # Physical checks: these fail if the series are read from the wrong state/algebraic column.
    t = tds["time"]
    bus2 = next(s for s in tds["bus_voltage"] if s["name"] == "Bus2")["values"]
    during_fault = [v for ti, v in zip(t, bus2) if 0.52 < ti < 0.58]
    assert 0.95 < bus2[0] < 1.05, bus2[0]
    assert during_fault and max(during_fault) < 0.1, during_fault  # bolted fault on Bus2
    assert bus2[-1] > 0.9, bus2[-1]  # recovers after clearing at 0.6 s
    for series in tds["omega"]:
        w = series["values"]
        assert abs(w[0] - 1.0) < 1e-3, w[0]  # rated speed before the fault
        assert max(w) > 1.0005, max(w)  # machines accelerate during the fault
    print("TDS physics OK: fault dip", round(max(during_fault), 3), "pu, recovery", round(bus2[-1], 3), "pu")

    # Line outage that keeps the network connected (second, parallel line).
    outage_params = dict(tds_params, fault_enabled="false", toggle_line="mxCell_line1", toggle_t="0.5")
    net = _sample_network(outage_params)
    net["99"] = dict(net["3"], name="mxCell_line2", id="l2", userFriendlyName="Line2")
    outage = json.loads(ae.run_tds(net, outage_params))
    assert not outage.get("error"), outage.get("message")
    assert outage.get("converged")
    print("Line outage OK")

    # An outage that islands Bus2 must be explained, not reported as "index out of range".
    island = json.loads(ae.run_tds(_sample_network(outage_params), outage_params))
    assert island.get("error") and "island" in island.get("message", ""), island.get("message")
    print("Islanding outage message OK")

    # IEEEST stabilizer: it attaches to the exciter and needs MODE; before the fix it was left
    # half-added and the run failed.
    pss_net = _sample_network(tds_params)
    next(v for v in pss_net.values() if isinstance(v, dict) and v.get("typ") == "Generator")["dyn_pss_model"] = "IEEEST"
    ss_pss, meta_pss = ae.build_system(pss_net, tds_params)
    assert ss_pss.IEEEST.n == 1, meta_pss["defaults_applied"]
    assert not any("could not add" in d for d in meta_pss["defaults_applied"]), meta_pss["defaults_applied"]
    pss_run = json.loads(ae.run_tds(pss_net, tds_params))
    assert not pss_run.get("error") and pss_run.get("converged"), pss_run.get("message")
    print("IEEEST stabilizer OK")

    # A model whose mandatory parameter is missing must be skipped whole, never half-added.
    ss_skip, _ = ae.build_system(_sample_network(tds_params), tds_params)
    notes = []
    assert ae._add_model_safe(ss_skip, "IEEEST", notes, "test", idx="IEEEST_x", name="x") is None
    assert ss_skip.IEEEST.n == 0 and notes and "missing" in notes[0], notes
    print("Mandatory-parameter pre-check OK")

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

    # The Generator dialog holds xdss_pu = 0 until it is filled in. xdss_pu doubles as GENROU xd2,
    # and a zero xd2 made initialisation fail with NaN (no TDS output, "Array must not contain
    # infs or NaNs" in EIG). A non-positive reactance is now read as "not set".
    def _zero_xdss(params):
        net = _sample_network(params)
        next(v for v in net.values() if isinstance(v, dict) and v.get("typ") == "Generator")["xdss_pu"] = "0"
        return net
    ss_zero, _ = ae.build_system(_zero_xdss(tds_params), tds_params)
    assert all(x > 0 for x in ss_zero.GENROU.xd2.v), ss_zero.GENROU.xd2.v
    zero_tds = json.loads(ae.run_tds(_zero_xdss(tds_params), tds_params))
    assert not zero_tds.get("error") and zero_tds.get("converged"), zero_tds.get("message")
    zero_eig = json.loads(ae.run_eig(_zero_xdss(eig_params), eig_params))
    assert not zero_eig.get("error"), zero_eig.get("message")
    print("Zero xdss_pu from the dialog OK")
    print("All smoke tests passed.")


if __name__ == "__main__":
    main()
