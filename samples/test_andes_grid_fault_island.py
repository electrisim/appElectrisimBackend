"""Transient stability with a fault on the External Grid bus, and island-mode networks.

Built from a user's diagram: 400 kV External Grid, 200 MVA step-up transformer, 300 MVA
GENROU generator at 18 kV, 18/14 kV auxiliary transformer and load.

- The External Grid was an ideal ANDES Slack, which holds its bus voltage, so a three-phase
  fault on the 400 kV bus did nothing (V stayed 1.0 pu, no rotor swing). It is now a source
  behind its short-circuit impedance in time-domain runs.
- A run that stops early (generator out of step) now says why in "warnings".
- GENROU took xq'' = 0.25 by default while the dialog only sets xd'', so a machine with
  xd'' = 0.2 started off steady state; xq'' now follows xd'' unless given.
- With no External Grid and no generator marked slack, transient stability and load flow
  failed ("No slack bus found" / "At least one External Grid element is required"). The
  largest generator is now the island's reference, and a warning says so.

Run with ``python samples/test_andes_grid_fault_island.py``.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import warnings

import numpy as np

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app  # noqa: E402

GEN = {"typ": "Generator", "name": "mxCell_g", "id": "g", "bus": "mxCell_b18", "userFriendlyName": "Generator",
       "p_mw": "200", "vm_pu": "1", "sn_mva": "300", "scaling": "1", "slack": "false", "vn_kv": "18",
       "xdss_pu": "0.2", "rdss_ohm": "0.001", "cos_phi": "0.85", "pg_percent": "0", "power_station_trafo": "0",
       "dyn_machine_model": "GENROU", "dyn_M": "9", "dyn_xd": "2", "dyn_xq": "2", "dyn_xd1": "0.4",
       "dyn_xq1": "0.4", "dyn_xd2": "0.2", "dyn_Td10": "0.2", "dyn_Tq10": "1.5", "dyn_exciter_model": "EXDC2",
       "dyn_governor_model": "TGOV1", "dyn_gov_R": "0.04", "dyn_pss_model": "NONE", "in_service": "true"}


def _trafo(i, hv, lv, sn, vh, vl, vk, vkr):
    return {"typ": f"Transformer{i}", "name": f"mxCell_t{i}", "id": f"t{i}", "hv_bus": hv, "lv_bus": lv,
            "sn_mva": sn, "vn_hv_kv": vh, "vn_lv_kv": vl, "vk_percent": vk, "vkr_percent": vkr, "pfe_kw": "0",
            "i0_percent": "0", "shift_degree": "0", "tap_pos": "0", "tap_neutral": "0", "tap_max": "0",
            "tap_min": "0", "tap_step_percent": "0", "tap_side": "hv", "parallel": "1", "in_service": "true",
            "userFriendlyName": "-"}


def network(settings, external_grid=True):
    d = {
        "0": settings,
        "1": {"typ": "Bus0", "name": "mxCell_b400", "id": "b400", "vn_kv": "400", "userFriendlyName": "Bus 400 kV"},
        "2": {"typ": "Bus1", "name": "mxCell_b18", "id": "b18", "vn_kv": "18", "userFriendlyName": "Bus 18 kV"},
        "3": {"typ": "Bus2", "name": "mxCell_b14", "id": "b14", "vn_kv": "14", "userFriendlyName": "Bus 14 kV"},
        "4": _trafo(0, "mxCell_b400", "mxCell_b18", "200", "400", "17.8", "10", "1"),
        "5": _trafo(1, "mxCell_b18", "mxCell_b14", "10", "18", "14", "8", "0"),
        "6": dict(GEN),
        "7": {"typ": "Load0", "name": "mxCell_ld", "id": "ld", "bus": "mxCell_b14", "p_mw": "8", "q_mvar": "2.5",
              "const_z_percent": "50", "const_i_percent": "50", "sn_mva": "0", "scaling": "1", "type": "wye",
              "in_service": "true", "userFriendlyName": "Load"},
    }
    if external_grid:
        d["8"] = {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_b400", "vm_pu": "1",
                  "va_degree": "0", "s_sc_max_mva": "15000", "s_sc_min_mva": "12000", "rx_max": "0.1",
                  "rx_min": "0.1", "in_service": "true", "userFriendlyName": "External Grid"}
    return d


def tds(fault_bus="mxCell_b400", tc="1.1", external_grid=True):
    settings = {"typ": "TransientStabilityAndes Parameters", "frequency": "60", "sn_mva": "100", "tf": "5",
                "tstep": "0", "fault_bus": fault_bus, "fault_enabled": "true" if fault_bus else "false",
                "fault_tf": "1.0", "fault_tc": tc, "toggle_line": "", "toggle_t": "2.0", "toggle_gen": "",
                "toggle_gen_t": "2.0", "poi_bus": "", "user_email": "t@e.com"}
    return post(network(settings, external_grid))


def load_flow(external_grid=True):
    settings = {"typ": "PowerFlowPandaPower Parameters", "frequency": "60", "algorithm": "nr",
                "calculate_voltage_angles": "auto", "initialization": "auto", "exportPython": False,
                "enforce_q_lims": "False", "user_email": "t@e.com"}
    return post(network(settings, external_grid))


def post(data):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=data)
    assert response.status_code == 200, response.data[:400]
    return json.loads(response.data)


def vmin(result, bus_name):
    return min(next(v for v in result["bus_voltage"] if v["name"] == bus_name)["values"])


def main() -> None:
    # The dialog only offers xd''. With xq'' left at its 0.25 default (user xd'' = 0.2) the
    # machine did not start in steady state and drifted before any event.
    r = tds(fault_bus="")
    assert not r.get("error"), r.get("message")
    w = np.asarray(next(s for s in r["omega"] if s["name"] == "Generator")["values"])
    assert w.max() - w.min() < 1e-6, (w.min(), w.max())

    # 0.1 s fault on the External Grid bus: voltage collapses, generator swings and recovers.
    r = tds()
    assert not r.get("error"), r.get("message")
    assert r["frequency_base_hz"] == 60.0
    assert r["converged"], r.get("warnings")
    assert vmin(r, "Bus 400 kV") < 0.1, vmin(r, "Bus 400 kV")
    assert vmin(r, "Bus 18 kV") < 0.5, vmin(r, "Bus 18 kV")
    w = np.asarray(next(s for s in r["omega"] if s["name"] == "Generator")["values"])
    assert w.max() - w.min() > 0.005, (w.min(), w.max())
    print(f"400 kV fault 0.1 s: V400 min {vmin(r, 'Bus 400 kV'):.3f}, V18 min {vmin(r, 'Bus 18 kV'):.3f}, "
          f"speed {w.min():.4f}..{w.max():.4f} pu")

    # 0.3 s is past this machine's critical clearing time: the run stops and says why.
    r = tds(tc="1.3")
    assert not r.get("error"), r.get("message")
    assert not r["converged"]
    assert any("lost synchronism" in x for x in r.get("warnings") or []), r.get("warnings")

    # Island: no External Grid, generator not marked slack.
    r = tds(fault_bus="mxCell_b14", external_grid=False)
    assert not r.get("error"), r.get("message")
    assert r["converged"], r.get("warnings")
    assert any("reference machine" in x for x in r["defaults_applied"]), r["defaults_applied"]
    lf = load_flow(external_grid=False)
    assert not lf.get("error"), lf.get("message")
    assert any("Generator 'Generator'" in x for x in lf.get("warnings") or []), lf.get("warnings")
    assert not load_flow().get("warnings"), "a grid-connected load flow must not get the island note"
    print("island: transient and load flow run with the generator as reference")
    print("ok")


if __name__ == "__main__":
    main()
