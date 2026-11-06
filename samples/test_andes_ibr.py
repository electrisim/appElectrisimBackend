"""Smoke test for an ANDES renewable (REGCA1 / REECA1 / REPCA1) plant.

The test intentionally skips on development machines where ANDES is not installed.
Run with ``python samples/test_andes_ibr.py``.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import andes_electrisim as ae
except ImportError as exc:  # pragma: no cover - only protects direct execution
    print(f"SKIP: unable to import ANDES integration: {exc}")
    raise SystemExit(0)


def sample_ibr_network(measured_line=True):
    """Grid bus1 with an IBR plant. bus2 hangs off bus1 through line1, which REPCA1 can measure."""
    net = {
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
        "4": {"typ": "Bus1", "name": "bus2", "vn_kv": "110", "userFriendlyName": "Bus 2"},
        "5": {
            "typ": "Line0", "name": "line1", "userFriendlyName": "Line 1",
            "busFrom": "bus1", "busTo": "bus2", "r_ohm_per_km": "0.05", "x_ohm_per_km": "0.4",
            "c_nf_per_km": "8", "g_us_per_km": "0", "length_km": "10", "in_service": "true",
        },
    }
    if measured_line:
        net["3"]["dyn_repca_line"] = "line1"
    return net


def main():
    if not ae._HAS_ANDES:
        print("SKIP: ANDES is not installed.")
        return
    ss, meta = ae.build_system(sample_ibr_network(), {"frequency": "60", "sn_mva": "100"})
    assert meta["n_generators"] == 0
    assert meta["n_renewable_plants"] == 1, meta["defaults_applied"]
    assert not any("could not add" in w for w in meta["defaults_applied"]), meta["defaults_applied"]
    assert getattr(ss, "REGCA1").n == 1
    assert getattr(ss, "REECA1").n == 1
    assert getattr(ss, "REPCA1").n == 1
    print("IBR build OK")

    # Without a measured line REPCA1 cannot be built: it must be skipped with a note,
    # not left half-added in the system.
    ss2, meta2 = ae.build_system(sample_ibr_network(measured_line=False), {"frequency": "60", "sn_mva": "100"})
    assert getattr(ss2, "REPCA1").n == 0, "REPCA1 added without a measured line"
    assert any("REPCA1 not modelled" in w for w in meta2["defaults_applied"]), meta2["defaults_applied"]
    print("IBR without measured line OK")

    # A fault in a network with only an IBR plant and the grid: ANDES needs a synchronous
    # source for its switching bookkeeping, so the External Grid gets a stiff classical source.
    fault = {"frequency": "60", "sn_mva": "100", "tf": "2", "fault_bus": "bus2",
             "fault_enabled": "true", "fault_tf": "0.5", "fault_tc": "0.6"}
    out = json.loads(ae.run_tds(sample_ibr_network(), fault))
    assert not out.get("error"), out.get("message")
    assert out.get("converged")
    t = out["time"]
    bus2 = next(s for s in out["bus_voltage"] if s["name"] == "Bus 2")["values"]
    during = [v for ti, v in zip(t, bus2) if 0.52 < ti < 0.58]
    assert during and max(during) < 0.1, during
    assert bus2[-1] > 0.9, bus2[-1]
    assert any("stiff source" in d for d in out["defaults_applied"]), out["defaults_applied"]
    print("IBR fault ride-through run OK")

    # PVD1 distributed PV on a 50 Hz network: ANDES defaults PVD1 to 60 Hz, so the network
    # frequency must be passed; the dialog's "DG Tg" sets the current-lag time constants.
    pvd = sample_ibr_network(measured_line=False)
    pvd["0"]["frequency"] = "50"
    pvd["3"]["dyn_plant_kind"] = "PVD1"
    pvd["3"]["dyn_dg_Tg"] = "0.05"
    p50 = {"frequency": "50", "sn_mva": "100"}
    ss3, meta3 = ae.build_system(pvd, p50)
    assert ss3.PVD1.n == 1, meta3["defaults_applied"]
    assert float(ss3.PVD1.fn.v[0]) == 50.0, ss3.PVD1.fn.v
    assert abs(float(ss3.PVD1.tip.v[0]) - 0.05) < 1e-12 and abs(float(ss3.PVD1.tiq.v[0]) - 0.05) < 1e-12
    out3 = json.loads(ae.run_tds(pvd, {**p50, "tf": "2", "fault_bus": "bus2", "fault_enabled": "true",
                                       "fault_tf": "0.5", "fault_tc": "0.6"}))
    assert not out3.get("error"), out3.get("message")
    bus2 = next(s for s in out3["bus_voltage"] if s["name"] == "Bus 2")["values"]
    assert bus2[-1] > 0.9, bus2[-1]
    print("PVD1 at 50 Hz OK")

    esd = sample_ibr_network(measured_line=False)
    esd["3"]["dyn_plant_kind"] = "ESD1"
    ss4, meta4 = ae.build_system(esd, p50)
    assert ss4.ESD1.n == 1, meta4["defaults_applied"]
    assert float(ss4.ESD1.fn.v[0]) == 50.0
    print("ESD1 build OK")

    # Wind (type 3/4 chain): WTTQA1 needs Tflag. Before the fix it was half-added and every
    # transient run with a wind plant crashed in ANDES setup.
    wind = sample_ibr_network(measured_line=True)
    wind["3"]["dyn_plant_kind"] = "WIND"
    ss5, meta5 = ae.build_system(wind, p50)
    chain = ("REGCA1", "REECA1", "REPCA1", "WTDTA1", "WTARA1", "WTPTA1", "WTTQA1")
    assert all(getattr(ss5, m).n == 1 for m in chain), {m: getattr(ss5, m).n for m in chain}
    out5 = json.loads(ae.run_tds(wind, {**p50, "tf": "2", "fault_bus": "bus2", "fault_enabled": "true",
                                        "fault_tf": "0.5", "fault_tc": "0.6"}))
    assert not out5.get("error") and out5.get("converged"), out5.get("message")
    bus2 = next(s for s in out5["bus_voltage"] if s["name"] == "Bus 2")["values"]
    assert bus2[-1] > 0.9, bus2[-1]
    print("Wind plant fault run OK")


if __name__ == "__main__":
    main()
