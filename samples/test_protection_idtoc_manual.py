"""Protection Coordination with IDTOC relays and Manual time grading.

pandapower's OCRelay always runs its automatic, topology-based time grading for
IDTOC, even when the times were entered by hand. That grading finds no paths on
a network with a transformer and failed with
"UnboundLocalError: ... 'sorted_line_path'", so every IDTOC relay fell back to
the ElectriSim evaluator. Manual IDTOC relays are now built with pandapower from
the manual time tables, and the automatic-grading failure says why it happened.

Run with ``python samples/test_protection_idtoc_manual.py``.
"""
from __future__ import annotations

import contextlib
import gzip
import io
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app  # noqa: E402
import pandapower_electrisim as pe  # noqa: E402

# Settings from the user's report (F12 upstream, F133 downstream).
UPSTREAM = {"tms": "0.4", "t_grade": "0.5", "t_gg": "0.4", "t_g": "0.9", "t_diff": "0.3",
            "I_s_a": "250", "I_g_a": "300", "I_gg_a": "2500"}
DOWNSTREAM = {"tms": "0.2", "t_grade": "0.5", "t_gg": "0.07", "t_g": "0.5", "t_diff": "0.3",
              "I_s_a": "250", "I_g_a": "300", "I_gg_a": "2500"}


def switch(cell, name, bus, line, relay, settings, pickup_mode="manual"):
    s = {"typ": f"Switch{cell}", "id": f"sw{cell}", "name": name, "userFriendlyName": name,
         "et": "l", "type": "CB", "closed": "true", "z_ohm": "0", "in_ka": "0.63",
         "bus": bus, "element": line, "protection_type": "ocr", "oc_relay_type": relay,
         "curve_type": "standard_inverse", "pickup_mode": pickup_mode,
         "overload_factor": "1.25", "ct_current_factor": "1.2", "safety_factor": "1"}
    s.update(settings)
    return s


def line(cell, name, bus_from, bus_to, length_km):
    return {"typ": f"Line{cell}", "name": name, "id": name, "userFriendlyName": name,
            "busFrom": bus_from, "busTo": bus_to, "length_km": length_km, "parallel": "1", "df": "1",
            "in_service": "true", "r_ohm_per_km": "0.125", "x_ohm_per_km": "0.0911",
            "c_nf_per_km": "290", "g_us_per_km": "0", "max_i_ka": "0.4", "type": "cs",
            "r0_ohm_per_km": "0.88", "x0_ohm_per_km": "0.3", "c0_nf_per_km": "0.01",
            "endtemp_degree": "250"}


def payload(grading_mode="manual", relays=("IDTOC", "IDTOC"), pickup_mode="manual", transformer=True):
    p = {
        "0": {"typ": "ProtectionCoordinationPandaPower", "user_email": "t@e.com", "fault_type": "3ph",
              "case": "max", "fault_location_mode": "line", "fault_bus_id": "", "sc_line_id": "all",
              "sc_fraction": 0.5, "grading_mode": grading_mode, "curve_type": "standard_inverse",
              "t_diff": 0.3, "t_g": 0.5, "t_gg": 0.07, "tms": 1.0, "t_grade": 0.5,
              "overload_factor": 1.25, "ct_current_factor": 1.2, "safety_factor": 1.0},
        "1": {"typ": "Bus0", "name": "mxCell_src", "id": "src", "vn_kv": "10", "userFriendlyName": "Source"},
        "2": {"typ": "Bus1", "name": "mxCell_b1", "id": "b1", "vn_kv": "10", "userFriendlyName": "B1"},
        "3": {"typ": "Bus2", "name": "mxCell_b2", "id": "b2", "vn_kv": "10", "userFriendlyName": "B2"},
        "4": {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_src", "vm_pu": "1",
              "va_degree": "0", "s_sc_max_mva": "205.77", "s_sc_min_mva": "205.77", "rx_max": "0.0543",
              "rx_min": "0.0543", "r0x0_max": "1.95", "x0x_max": "16.3", "r0x0_min": "1.95",
              "x0x_min": "16.3", "in_service": "true", "userFriendlyName": "Grid"},
        "5": line(0, "mxCell_l1", "mxCell_src", "mxCell_b1", "0.47"),
        "6": line(1, "mxCell_l2", "mxCell_b1", "mxCell_b2", "0.236"),
        "7": switch(0, "F12", "mxCell_src", "mxCell_l1", relays[0], UPSTREAM, pickup_mode),
        "8": switch(1, "F133", "mxCell_b1", "mxCell_l2", relays[1], DOWNSTREAM, pickup_mode),
        "9": {"typ": "Load0", "name": "mxCell_ld", "id": "ld", "userFriendlyName": "Load",
              "bus": "mxCell_lv" if transformer else "mxCell_b2", "p_mw": "0.4", "q_mvar": "0.174",
              "const_z_percent": "0", "const_i_percent": "0", "sn_mva": "0", "scaling": "1",
              "type": "wye", "in_service": "true"},
    }
    if transformer:
        p["10"] = {"typ": "Bus3", "name": "mxCell_lv", "id": "lv", "vn_kv": "0.42", "userFriendlyName": "LV"}
        p["11"] = {"typ": "Transformer0", "name": "mxCell_tr", "id": "tr", "userFriendlyName": "TR",
                   "hv_bus": "mxCell_b2", "lv_bus": "mxCell_lv", "sn_mva": "1", "vn_hv_kv": "10",
                   "vn_lv_kv": "0.42", "vkr_percent": "0.75", "vk_percent": "5.6", "pfe_kw": "0.63",
                   "i0_percent": "0.079", "vector_group": "Dyn", "vk0_percent": "5.69",
                   "vkr0_percent": "0.752", "mag0_percent": "0", "si0_hv_partial": "0", "parallel": "1",
                   "shift_degree": "330", "tap_side": "hv", "tap_pos": "0", "tap_neutral": "0",
                   "tap_max": "0", "tap_min": "0", "tap_step_percent": "0", "in_service": "true"}
    return p


def solve(**kw):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=payload(**kw))
    assert response.status_code == 200, response.data[:400]
    body = response.data
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    data = json.loads(body)
    assert not data.get("error"), data
    return data


def summaries(data):
    return {s["switch_name"]: s for s in data["attach_summaries"]}


def devices(data):
    return {d["switch_name"]: d for d in data["devices"]}


def check_trip_times(data, settings_by_name):
    """Every pandapower trip time must match the IDTOC formula for its current."""
    n = 0
    for sc in data["scenarios"]:
        for trip in sc["trip"]:
            spec = {k: float(v) for k, v in settings_by_name[trip["switch_name"]].items()}
            spec["curve_type"] = "standard_inverse"
            _, expected, _ = pe._prot_eval_oc_trip(spec, "IDTOC", 1000.0 * float(trip["ikss_ka"] or 0.0))
            got = trip["t_trip_s"]
            if expected is None:
                assert got is None, (trip, expected)
            else:
                assert got is not None and abs(got - expected) < 1e-6, (trip, expected)
                n += 1
    return n


def main() -> None:
    settings = {"F12": UPSTREAM, "F133": DOWNSTREAM}

    # 1. The user's case: IDTOC + Manual grading + manual pickups, on a network with a transformer.
    data = solve()
    for name, s in summaries(data).items():
        assert s["engine"] == "pandapower" and not s.get("custom_evaluator"), (name, s.get("reason"))
    for name, d in devices(data).items():
        want = settings[name]
        for key in ("tms", "t_grade", "t_gg", "t_g", "I_s_a", "I_g_a", "I_gg_a"):
            assert abs(float(d["settings"][key]) - float(want[key])) < 1e-9, (name, key, d["settings"])
    n_trips = check_trip_times(data, settings)
    assert n_trips > 0
    print(f"manual IDTOC: both relays built by pandapower, {n_trips} trip times match the IDTOC curve")

    # 2. Calculated pickups with Manual grading also stay in pandapower.
    data = solve(pickup_mode="auto")
    for name, s in summaries(data).items():
        assert s["engine"] == "pandapower", (name, s.get("reason"))
    for name, d in devices(data).items():
        st = d["settings"]
        assert 0 < st["I_s_a"] < st["I_g_a"], (name, st)
        assert abs(st["t_g"] - float(settings[name]["t_g"])) < 1e-9, (name, st)
    print("manual IDTOC with calculated pickups: pandapower")

    # 3. DTOC and IDMT next to each other with Manual grading are unchanged.
    data = solve(relays=("DTOC", "IDMT"))
    s = summaries(data)
    assert s["F12"]["engine"] == "pandapower" and s["F133"]["engine"] == "pandapower", s
    d = devices(data)
    assert abs(d["F12"]["settings"]["t_g"] - 0.9) < 1e-9 and abs(d["F133"]["settings"]["tms"] - 0.2) < 1e-9, d
    print("manual DTOC + IDMT: pandapower")

    # 4. Automatic grading cannot handle the transformer: ElectriSim evaluates, and the reason says why.
    data = solve(grading_mode="auto")
    for name, s in summaries(data).items():
        assert s["engine"] == "electrisim", (name, s)
        assert "transformers" in s["reason"] and "Manual time grading" in s["reason"], s["reason"]
    print("auto grading with a transformer: clear reason ->", summaries(data)["F12"]["reason"][-160:])

    # 5. Automatic grading without a transformer still runs in pandapower.
    data = solve(grading_mode="auto", transformer=False)
    for name, s in summaries(data).items():
        assert s["engine"] == "pandapower", (name, s.get("reason"))
    print("auto grading without a transformer: pandapower")
    print("ok")


if __name__ == "__main__":
    main()
