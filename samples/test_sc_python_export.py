"""The Python export of an IEC short circuit reproduces the Electrisim result.

A user ran the six exported scripts (3ph / 2ph / 1ph, max / min) on their own: only the two
maximum 3ph / 2ph scripts ran. The others stopped with KeyError 'r0_ohm_per_km' or "Specify
end temperature for lines in net.line.endtemp_degree", because the export left out each line's
zero-sequence data and end temperature, which Electrisim itself uses. The export also dropped
out-of-service flags, the generator short-circuit data and induction-machine static generators,
and did not repeat the steps Electrisim runs after calc_sc (the converter r2/x2 correction and
the single-phase ip / Ith).

Single-phase ip and Ith used a fixed kappa of 1.8 with Ith = Ik1" (line Ith showed 0). They now
use each bus's own IEC 60909 kappa and m, the same values as the three-phase fault.

For every fault type and case this runs the study with exportPython, executes the script in a
fresh namespace and compares every bus and line current with the study's answer.

Run with ``python samples/test_sc_python_export.py``.
"""
from __future__ import annotations

import contextlib
import io
import json
import math
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app  # noqa: E402


def payload(fault, case):
    settings = {"typ": "ShortCircuitPandaPower Parameters", "fault_type": fault, "fault_location": case,
                "fault_bus_mode": "all", "fault_bus_ids": [], "fault_bus_names": [], "fault_impedance": "6",
                "topology": "auto", "tk_s": "1", "r_fault_ohm": "0", "x_fault_ohm": "0", "inverse_y": "True",
                "exportPython": True, "user_email": "t@e.com"}

    def line(key, a, b, km, in_service="true"):
        return {"typ": "Line0", "name": f"mxCell_{key}", "id": key, "busFrom": a, "busTo": b,
                "r_ohm_per_km": "0.125", "x_ohm_per_km": "0.0911", "c_nf_per_km": "290", "g_us_per_km": "0",
                "length_km": km, "max_i_ka": "0.4", "type": "cs", "parallel": "1", "df": "1",
                "r0_ohm_per_km": "0.88", "x0_ohm_per_km": "0.3", "c0_nf_per_km": "100", "endtemp_degree": "250",
                "in_service": in_service, "userFriendlyName": key.upper()}

    return {
        "0": settings,
        "1": {"typ": "Bus0", "name": "mxCell_a", "id": "a", "vn_kv": "10", "userFriendlyName": "A"},
        "2": {"typ": "Bus1", "name": "mxCell_b", "id": "b", "vn_kv": "10", "userFriendlyName": "B"},
        "3": {"typ": "Bus2", "name": "mxCell_c", "id": "c", "vn_kv": "10", "userFriendlyName": "C"},
        "4": {"typ": "Bus3", "name": "mxCell_d", "id": "d", "vn_kv": "0.4", "userFriendlyName": "D"},
        "5": {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_a", "vm_pu": "1",
              "va_degree": "0", "s_sc_max_mva": "205.77", "s_sc_min_mva": "160", "rx_max": "0.0543",
              "rx_min": "0.0543", "r0x0_max": "1.95", "x0x_max": "16.3", "r0x0_min": "1.95", "x0x_min": "16.3",
              "in_service": "true", "userFriendlyName": "Grid"},
        "6": line("l1", "mxCell_a", "mxCell_b", "0.47"),
        "7": line("l2", "mxCell_b", "mxCell_c", "0.5"),
        # A parallel path that is switched off: the script must keep it off.
        "8": line("l3", "mxCell_a", "mxCell_c", "0.2", in_service="false"),
        "9": {"typ": "Transformer0", "name": "mxCell_tr", "id": "tr", "hv_bus": "mxCell_c", "lv_bus": "mxCell_d",
              "sn_mva": "1", "vn_hv_kv": "10", "vn_lv_kv": "0.4", "vkr_percent": "0.75", "vk_percent": "5.6",
              "pfe_kw": "0.63", "i0_percent": "0.079", "shift_degree": "150", "tap_pos": "0", "tap_neutral": "0",
              "tap_max": "0", "tap_min": "0", "tap_step_percent": "0", "tap_side": "hv", "parallel": "1",
              "vector_group": "Dyn", "vk0_percent": "5.6", "vkr0_percent": "0.75", "mag0_percent": "100",
              "mag0_rx": "0", "si0_hv_partial": "0.5", "in_service": "true", "userFriendlyName": "TR"},
        # Synchronous generator whose short-circuit data Electrisim fills with typical values.
        "10": {"typ": "Generator", "name": "mxCell_g", "id": "g", "bus": "mxCell_b", "p_mw": "1", "vm_pu": "1",
               "sn_mva": "null", "scaling": "1", "vn_kv": "0", "xdss_pu": "0", "rdss_ohm": "0", "cos_phi": "0",
               "pg_percent": "0", "power_station_trafo": "0", "in_service": "true", "slack": "false",
               "userFriendlyName": "G1"},
        # Converter with Ik" per fault and a negative-sequence reactance (the r2/x2 correction).
        "11": {"typ": "Static Generator0", "name": "mxCell_pv", "id": "pv", "bus": "mxCell_d", "p_mw": "0.24",
               "q_mvar": "0", "sn_mva": "0.3", "scaling": "1", "type": "wye", "k": "1.2", "rx": "0",
               "generator_type": "current_source", "lrc_pu": "0", "max_ik_ka": "0", "kappa": "0",
               "current_source": "true", "ikss_3ph_ka": "0.52", "ikss_2ph_ka": "0.45", "ikss_1ph_ka": "0.3",
               "sc_ref_vn_kv": "0.4", "r2_pu": "0.02", "x2_pu": "0.2", "in_service": "true",
               "userFriendlyName": "PV"},
        # Induction-machine generator: an impedance in the short circuit, not a current source.
        "12": {"typ": "Static Generator1", "name": "mxCell_wt", "id": "wt", "bus": "mxCell_c", "p_mw": "1.5",
               "q_mvar": "0", "sn_mva": "2", "scaling": "1", "type": "wye", "k": "0", "rx": "0.1",
               "generator_type": "async", "lrc_pu": "5", "max_ik_ka": "0", "kappa": "0",
               "current_source": "false", "in_service": "true", "userFriendlyName": "WT"},
        "13": {"typ": "Load0", "name": "mxCell_ld", "id": "ld", "bus": "mxCell_d", "p_mw": "0.4", "q_mvar": "0.1",
               "const_z_percent": "0", "const_i_percent": "0", "sn_mva": "0", "scaling": "1", "type": "wye",
               "in_service": "false", "userFriendlyName": "Load"},
    }


def solve(fault, case):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=payload(fault, case))
    assert response.status_code == 200, response.data[:400]
    data = json.loads(response.data)
    assert not data.get("error"), data.get("message") or data
    assert data.get("pandapower_python"), data.get("pandapower_python_error")
    return data


def run_script(code):
    scope = {"__name__": "__electrisim_export__"}
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(code, "<export>", "exec"), scope)
    return scope["net"]


def close(a, b, tol=1e-6):
    if a is None or (isinstance(a, float) and math.isnan(a)):
        return b is None or (isinstance(b, float) and math.isnan(b))
    return b is not None and not (isinstance(b, float) and math.isnan(b)) and abs(a - b) <= tol * max(1.0, abs(a))


def main() -> None:
    for fault in ("3ph", "2ph", "1ph"):
        for case in ("max", "min"):
            data = solve(fault, case)
            code = data["pandapower_python"]
            assert "endtemp_degree=250.0" in code and "r0_ohm_per_km=0.88" in code, "line sequence data missing"
            assert code.count("in_service=False") >= 2, "the switched-off line and load must stay off"
            assert "xdss_pu=" in code and "generator_type='async'" in code
            assert ("apply_negative_sequence_ikss(net" in code) == (fault != "3ph")
            assert ("electrisim_1ph_ip_ith(net" in code) == (fault == "1ph")
            net = run_script(code)

            checked = 0
            for b in data["busbars"]:
                idx = net.bus.index[net.bus.name == b["name"]][0]
                row = net.res_bus_sc.loc[idx]
                for col in ("ikss_ka", "ip_ka", "ith_ka"):
                    got = None if math.isnan(row[col]) else float(row[col])
                    assert close(b[col], got), f"{fault} {case} bus {b['name']} {col}: study {b[col]} script {got}"
                    checked += 1
            for ln in data["lines_sc"]:
                idx = net.line.index[net.line.name == ln["name"]][0]
                row = net.res_line_sc.loc[idx]
                for col in ("ikss_ka", "ip_ka", "ith_ka"):
                    got = None if math.isnan(row[col]) else float(row[col])
                    assert close(ln[col], got), f"{fault} {case} line {ln['name']} {col}: study {ln[col]} script {got}"
                    checked += 1
            print(f"{fault} {case}: exported script matches the study ({checked} values)")

            if fault == "1ph":
                ratios = {b["id"]: b["ip_ka"] / (math.sqrt(2) * b["ikss_ka"]) for b in data["busbars"]}
                assert all(1.0 < k < 2.0 for k in ratios.values()), ratios
                assert abs(ratios["a"] - ratios["d"]) > 0.05, f"kappa must be the bus's own, not one constant: {ratios}"
                assert all(b["ith_ka"] > b["ikss_ka"] for b in data["busbars"]), "Ith includes the DC component"
                live = [ln for ln in data["lines_sc"] if (ln["ikss_ka"] or 0) > 0]
                assert live and all(ln["ith_ka"] >= ln["ikss_ka"] for ln in live), data["lines_sc"]
    print("short-circuit Python export OK")


if __name__ == "__main__":
    main()
