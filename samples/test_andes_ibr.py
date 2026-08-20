"""Smoke test for an ANDES renewable (REGCA1 / REECA1 / REPCA1) plant.

The test intentionally skips on development machines where ANDES is not installed.
Run with ``python samples/test_andes_ibr.py``.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import andes_electrisim as ae
except ImportError as exc:  # pragma: no cover - only protects direct execution
    print(f"SKIP: unable to import ANDES integration: {exc}")
    raise SystemExit(0)


def sample_ibr_network():
    return {
        "0": {"frequency": "60", "sn_mva": "100"},
        "1": {"typ": "Bus0", "name": "bus1", "vn_kv": "110", "userFriendlyName": "Grid bus"},
        "2": {
            "typ": "External Grid0", "name": "grid", "bus": "bus1",
            "vm_pu": "1.0", "va_degree": "0", "in_service": "true",
        },
        "3": {
            "typ": "Static Generator", "name": "ibr1", "userFriendlyName": "IBR 1",
            "bus": "bus1", "p_mw": "20", "q_mvar": "0", "sn_mva": "25",
            "scaling": "1", "in_service": "true", "dyn_plant_kind": "IBR",
        },
    }


def main():
    if not ae._HAS_ANDES:
        print("SKIP: ANDES is not installed.")
        return
    ss, meta = ae.build_system(sample_ibr_network(), {"frequency": "60", "sn_mva": "100"})
    assert meta["n_generators"] == 0
    assert meta["n_renewable_plants"] == 1, meta["defaults_applied"]
    assert getattr(ss, "REGCA1").n == 1
    assert getattr(ss, "REECA1").n == 1
    assert getattr(ss, "REPCA1").n == 1
    print("IBR build OK")


if __name__ == "__main__":
    main()
