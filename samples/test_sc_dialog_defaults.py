"""IEC short circuit on a diagram whose dialogs were left at their defaults.

- A Generator with no short-circuit data (sn_mva / vn_kv / xdss_pu / cos_phi = 0) failed every
  study with "'DataFrame' object has no attribute 'vn_kv'". Typical values are now filled in
  and reported in "warnings".
- A single-phase fault on an External Grid with X0/X = 0 failed with "nan value detected in
  Ybus"; the typical X0/X = 1 is used and reported.
- The minimum calculation with a zero minimum grid power still fails, and the diagnosis names
  only that field (it used to blame s_sc_min_mva for max calculations too).

Run with ``python samples/test_sc_dialog_defaults.py``.
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


def payload(fault, case, gen_in_service="true"):
    return {
        "0": {"typ": "ShortCircuitPandaPower Parameters", "fault_type": fault, "fault_location": case,
              "fault_bus_mode": "all", "fault_bus_ids": [], "fault_bus_names": [], "fault_impedance": "6",
              "topology": "auto", "tk_s": "1", "r_fault_ohm": "0", "x_fault_ohm": "0", "inverse_y": "True",
              "exportPython": False, "user_email": "t@e.com"},
        "1": {"typ": "Bus0", "name": "mxCell_a", "id": "a", "vn_kv": "110", "userFriendlyName": "A"},
        "2": {"typ": "Bus1", "name": "mxCell_b", "id": "b", "vn_kv": "110", "userFriendlyName": "B"},
        # External Grid as the dialog creates it before 1.23.0.
        "3": {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_a", "vm_pu": "1",
              "va_degree": "0", "s_sc_max_mva": "1000", "s_sc_min_mva": "0", "rx_max": "0", "rx_min": "0",
              "r0x0_max": "0", "x0x_max": "0", "r0x0_min": "0", "x0x_min": "0", "in_service": "true",
              "userFriendlyName": "Grid"},
        "4": {"typ": "Line0", "name": "mxCell_l", "id": "l", "busFrom": "mxCell_a", "busTo": "mxCell_b",
              "r_ohm_per_km": "0.06", "x_ohm_per_km": "0.4", "c_nf_per_km": "9", "g_us_per_km": "0",
              "length_km": "20", "max_i_ka": "0.6", "type": "ol", "parallel": "1", "df": "1",
              "r0_ohm_per_km": "0.18", "x0_ohm_per_km": "1.2", "c0_nf_per_km": "5", "endtemp_degree": "80",
              "in_service": "true", "userFriendlyName": "L"},
        # Generator with its short-circuit fields left at 0 / "null".
        "5": {"typ": "Generator", "name": "mxCell_g", "id": "g", "bus": "mxCell_b", "p_mw": "40", "vm_pu": "1",
              "sn_mva": "null", "scaling": "1", "vn_kv": "0", "xdss_pu": "0", "rdss_ohm": "0", "cos_phi": "0",
              "pg_percent": "0", "power_station_trafo": "0", "in_service": gen_in_service, "slack": "false",
              "userFriendlyName": "G1"},
    }


def solve(fault, case, **kw):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=payload(fault, case, **kw))
    assert response.status_code == 200, response.data[:400]
    return json.loads(response.data)


def ikss(data, bus_id):
    return next(b["ikss_ka"] for b in data["busbars"] if b["id"] == bus_id)


def main() -> None:
    data = solve("3ph", "max")
    assert not data.get("error"), data.get("message")
    warns = data.get("warnings") or []
    assert any("Generator 'G1'" in w and "Sn=47.059 MVA" in w for w in warns), warns
    grid_only = solve("3ph", "max", gen_in_service="false")
    print(f"3ph max: Ik'' at B = {ikss(data, 'b'):.2f} kA (grid only {ikss(grid_only, 'b'):.2f} kA)")
    assert ikss(data, "b") > ikss(grid_only, "b") + 0.5, "the generator must contribute to the fault"

    # Static Generator as the palette created it: "async" with no rating and lrc_pu = 0
    # ("nan value detected in Ybus"). It is treated as a converter rated at |P|.
    sg = payload("3ph", "max")
    sg["6"] = {"typ": "Static Generator", "name": "mxCell_sg", "id": "sg", "bus": "mxCell_b", "p_mw": "20",
               "q_mvar": "0", "sn_mva": "null", "scaling": "1", "type": "Wye", "k": "0", "rx": "0",
               "generator_type": "async", "lrc_pu": "0.0", "max_ik_ka": "0.0", "kappa": "0.0",
               "current_source": "true", "in_service": "true", "userFriendlyName": "PV1"}
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        sg_data = json.loads(app.app.test_client().post("/", json=sg).data)
    assert not sg_data.get("error"), sg_data.get("message")
    sg_warns = [w for w in sg_data.get("warnings") or [] if "PV1" in w]
    assert any("current source" in w for w in sg_warns) and any("Sn = |P| = 20" in w for w in sg_warns), sg_warns
    assert ikss(sg_data, "b") > ikss(data, "b"), "the converter must add to the fault current"
    print(f"static generator defaults OK: Ik'' at B = {ikss(sg_data, 'b'):.2f} kA")

    # A realistic grid (1000 MVA at 110 kV) is not flagged; an "infinite" 1,000,000 MVA grid is.
    assert not any("short-circuit power" in w for w in warns), warns
    infinite = payload("3ph", "max")
    infinite["3"]["s_sc_max_mva"] = "1000000"
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        inf_data = json.loads(app.app.test_client().post("/", json=infinite).data)
    assert not inf_data.get("error"), inf_data.get("message")
    assert any("External Grid 'Grid'" in w and "5,249 kA" in w for w in inf_data.get("warnings") or []), \
        inf_data.get("warnings")
    print("unrealistic grid short-circuit power flagged OK")

    data = solve("1ph", "max")
    assert not data.get("error"), data.get("message")
    assert any("External Grid 'Grid'" in w and "X0/X max=1" in w for w in data.get("warnings") or []), data.get("warnings")
    print(f"1ph max: Ik'' at A = {ikss(data, 'a'):.2f} kA")
    assert ikss(data, "a") > 0

    data = solve("3ph", "min")
    assert data.get("error"), "a zero minimum grid power must not be guessed"
    params = [p["param"] for p in data["diagnostic"]["invalid_parameters"]]
    assert params == ["s_sc_min_mva"], params
    print("3ph min: asks for s_sc_min_mva OK")
    # Studies that run IEC short circuit themselves hit the same generator gap.
    base = payload("3ph", "max")
    base["0"] = {"typ": "ArcFlashPandaPower Parameters", "electrode_config": "VCB", "working_distance_mm": "455",
                 "conductor_gap_mm": "25", "clearing_time_s": "0.2", "clearing_time_min_s": "0.2",
                 "user_email": "t@e.com"}
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        af = json.loads(app.app.test_client().post("/", json=base).data)
    assert not af.get("error") and af.get("arc_flash"), af.get("message")
    assert any("Generator 'G1'" in w for w in af.get("warnings") or []), af.get("warnings")
    print("arc flash with generator defaults OK")

    base["0"] = {"typ": "PoiFaultStudy Parameters", "frequency_hz": "50", "contact_parting_cycles": "3",
                 "prefault_v_pu": "1", "user_email": "t@e.com"}
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        poi = json.loads(app.app.test_client().post("/", json=base).data)
    assert not poi.get("error"), poi.get("message")
    max_rows = [c for c in poi["coordination"] if c["case"] == "max"]
    assert max_rows and all(not c.get("error") and c["ikss_ka"] > 0 for c in max_rows), max_rows
    min_rows = [c for c in poi["coordination"] if c["case"] == "min"]
    assert all("s_sc_min_mva" in (c.get("error") or "") for c in min_rows), min_rows
    print("POI coordination with generator defaults OK")
    print("short circuit with dialog defaults OK")


if __name__ == "__main__":
    main()
