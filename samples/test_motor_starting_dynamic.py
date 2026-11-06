"""Smoke test for the dynamic (ANDES) motor-starting study.

The time series are read from ``ss.dae.ts`` (states from ``x``, algebraic variables from
``y``). This checks the backend returns real bus-voltage and motor series instead of
empty ones with a "Could not extract" warning, and that they make physical sense.

Run with ``python samples/test_motor_starting_dynamic.py``.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import motor_starting_electrisim as ms  # noqa: E402


def sample_network():
    return {
        "0": {"frequency": "50", "sn_mva": "100"},
        "1": {"typ": "Bus0", "name": "mxCell_bus1", "id": "b1", "vn_kv": "20", "userFriendlyName": "Grid bus"},
        "2": {"typ": "Bus1", "name": "mxCell_bus2", "id": "b2", "vn_kv": "20", "userFriendlyName": "Motor bus"},
        # ANDES needs a synchronous machine; the generator is the slack of the dynamic model.
        "3": {
            "typ": "Generator", "name": "mxCell_gen1", "id": "g1", "bus": "mxCell_bus1",
            "p_mw": "2", "vm_pu": "1.0", "sn_mva": "200", "scaling": "1", "vn_kv": "20",
            "slack": "true", "userFriendlyName": "Gen1",
        },
        "4": {
            "typ": "Line0", "name": "mxCell_line1", "id": "l1", "userFriendlyName": "Feeder",
            "busFrom": "mxCell_bus1", "busTo": "mxCell_bus2",
            "r_ohm_per_km": "0.1", "x_ohm_per_km": "0.35", "c_nf_per_km": "10",
            "g_us_per_km": "0", "length_km": "2", "max_i_ka": "0.5", "in_service": "true",
        },
        "5": {
            "typ": "Motor0", "name": "mxCell_motor1", "id": "m1", "userFriendlyName": "Pump motor",
            "bus": "mxCell_bus2", "pn_mech_mw": "1.0", "cos_phi": "0.88", "cos_phi_n": "0.88",
            "efficiency_n_percent": "95", "efficiency_percent": "95", "loading_percent": "100",
            "lrc_pu": "6", "rx": "0.3", "vn_kv": "20", "in_service": "true",
        },
    }


def main():
    if not ms._HAS_ANDES:
        print("SKIP: ANDES is not installed.")
        return
    params = {"mode": "dynamic", "starting_method": "dol", "t_start": "0.1", "t_end": "2"}
    out = json.loads(ms.motor_starting(None, params, sample_network()))
    assert not out.get("error"), out.get("message") or out.get("exception")
    warnings = out.get("warnings") or []
    assert not any("Could not extract" in w for w in warnings), warnings
    ts = out["timeseries"]
    assert len(ts["t"]) > 10, len(ts["t"])
    v_motor_bus = ts["buses"]["mxCell_bus2"]["v"]
    slip = ts["motors"]["m1"]["slip"]
    assert len(v_motor_bus) == len(ts["t"]) and len(slip) == len(ts["t"])
    # Physical sanity: before the start the motor bus sits near 1 pu and the motor is idle;
    # a 1 MW start on a 200 MVA source dips the bus by a few percent, never to zero.
    assert 0.95 < v_motor_bus[0] < 1.05, v_motor_bus[0]
    assert min(v_motor_bus) > 0.8, min(v_motor_bus)
    assert 0.0 < out["summary"]["worst_dip_percent"] < 20.0, out["summary"]
    # The series must not be the time vector read from the wrong column.
    assert slip != ts["t"], "slip series equals the time vector"
    print(f"dynamic motor starting OK: {len(ts['t'])} points, worst dip "
          f"{out['summary']['worst_dip_percent']:.1f}%")


if __name__ == "__main__":
    main()
