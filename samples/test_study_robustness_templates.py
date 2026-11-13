"""Studies on shipped templates that used to fail or mislead (found by running every study on every template).

1. Contingency analysis
   - violations the intact network already has are flagged ``pre_existing`` and listed once in
     ``summary.base_case_violations`` (they used to be repeated in every case with no mark);
   - three-winding transformers are switched out and checked for overload;
   - the response carries result rows for the worst case only (it grew with cases x elements);
   - the network is left as it was (every element back in service).
2. Offshore wind farm with a STATCOM: contingency, time series and economic analysis solve it
   the way Load Flow does (they stopped with "did not converge").
3. Time series: an hour that cannot be solved is listed in ``failed_time_steps`` and the run
   continues (one such hour used to abort the whole study).
4. A Line drawn between two DC buses is calculated as a DC line, or rejected by name when it
   has no length / resistance (it was wired to unrelated AC buses: "divide by zero").
5. A zero-impedance AC line is rejected by name.
6. Minimum short circuit: a missing External Grid S"k min is named up front, and unset line end
   temperatures get a stated default instead of a pandapower error.

Run with ``python samples/test_study_robustness_templates.py``.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FIXTURES = os.path.join(ROOT, "samples", "fixtures")

import app  # noqa: E402
import pandapower as pp  # noqa: E402
import pandapower_electrisim as pe  # noqa: E402

CLIENT = app.app.test_client()

CONTINGENCY = {"typ": "ContingencyAnalysisPandaPower Parameters", "element_type": "all",
               "voltage_limits": "true", "thermal_limits": "true", "min_vm_pu": "0.95",
               "max_vm_pu": "1.05", "max_loading_percent": "100", "frequency": "50"}
TIME_SERIES = {"typ": "TimeSeriesSimulationPandaPower Parameters", "time_steps": 24,
               "load_profile": "daily", "generation_profile": "solar", "frequency": "50"}
ECONOMIC = {"typ": "EconomicAnalysisPandaPower Parameters", "frequency": "50", "currency": "EUR",
            "time_steps": 24, "lifetime_years": 30, "calculation_mode": "lookup_table",
            "load_profile": "daily", "generation_profile": "constant", "use_generation_profile": True}
LOAD_FLOW = {"typ": "PowerFlowPandaPower Parameters", "frequency": "50", "algorithm": "nr",
             "calculate_voltage_angles": "auto", "initialization": "auto"}
SC_MIN = {"typ": "ShortCircuitPandaPower Parameters", "fault_type": "3ph", "fault_location": "min",
          "fault_bus_mode": "all", "fault_impedance": "6", "topology": "auto", "tk_s": "1",
          "r_fault_ohm": "0", "x_fault_ohm": "0", "inverse_y": "True"}


def network(fixture):
    with open(os.path.join(FIXTURES, fixture), encoding="utf-8") as handle:
        data = json.load(handle)
    return {k: v for k, v in data.items() if "Parameters" not in str(v.get("typ", ""))}


def run(net_elements, params):
    payload = {"0": dict(params, user_email="t@e.com")}
    payload.update(copy.deepcopy(net_elements))
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = CLIENT.post("/", json=payload)
    return response.status_code, json.loads(response.get_data(as_text=True))


def test_contingency_base_case_and_trafo3w():
    net = network("study_multivoltage.json")
    status, data = run(net, CONTINGENCY)
    assert status == 200 and not data.get("error"), data.get("error")
    summary = data["summary"]

    base = summary["base_case_violations"]
    assert base, "the multivoltage example violates 0.95-1.05 p.u. with nothing switched out"
    base_keys = {(v["type"], v["element"]) for v in base}
    flagged = 0
    for case in data["contingency_results"]:
        assert "bus_results" not in case and "line_results" not in case, "per-case rows are not sent any more"
        if not case["converged"]:
            continue
        for v in case["violations"]:
            if (v["type"], v["element"]) in base_keys:
                assert v.get("pre_existing") is True and "base case" in v["description"], v
                flagged += 1
            else:
                assert not v.get("pre_existing"), v
        assert case["new_violations"] == sum(1 for v in case["violations"] if not v.get("pre_existing"))
    assert flagged > 0
    assert summary["cases_with_new_violations"] == sum(1 for c in data["contingency_results"] if c["new_violations"])

    three_winding = [c for c in data["contingency_results"] if "three-winding" in c["description"]]
    assert len(three_winding) == 1, "the three-winding transformer must be an outage case"
    assert any(v["type"] == "islanding" for v in three_winding[0]["violations"])

    assert data["worst_case"] in {c["name"] for c in data["contingency_results"]}
    assert len(data["bus"]) > 0 and len(data["line"]) > 0
    # two 2-winding transformers plus the three-winding one in the worst-case table
    assert len(data["transformer"]) == 3, len(data["transformer"])
    print(f"contingency OK: {len(data['contingency_results'])} cases, {len(base)} base-case violations, "
          f"{summary['cases_with_new_violations']} cases with new ones")


def test_contingency_leaves_network_unchanged():
    data = network("study_multivoltage.json")
    net = pp.create_empty_network()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        busbars = pe.create_busbars(data, net)
        pe.create_other_elements(data, net, None, busbars)
        before = {t: net[t].in_service.copy() for t in ("line", "trafo", "trafo3w", "gen")}
        result = json.loads(pe.contingency_analysis(net, {"element_type": "all"}))
    assert not result.get("error"), result.get("error")
    for table, state in before.items():
        assert net[table].in_service.equals(state), f"{table} in_service changed"
    print("contingency OK: network left as it was")


def test_statcom_network_in_repeated_studies():
    net = network("study_offshore_wind_statcom.json")
    status, lf = run(net, LOAD_FLOW)
    assert status == 200 and not lf.get("error"), "the fixture must solve in Load Flow"

    status, cont = run(net, dict(CONTINGENCY, element_type="transformer"))
    assert status == 200 and not cont.get("error"), cont.get("error")
    assert any(c["converged"] for c in cont["contingency_results"])

    status, ts = run(net, TIME_SERIES)
    assert status == 200 and not ts.get("error"), ts.get("message") or ts.get("error")
    assert len(ts["time_step_converged"]) == 24 and any(ts["time_step_converged"])

    status, econ = run(net, ECONOMIC)
    assert status == 200 and not econ.get("error"), econ.get("error")
    print("STATCOM network OK: contingency, time series and economic analysis solve")


def test_time_series_reports_failed_steps():
    net = network("study_time_series_basic.json")
    # Heavier load so that the evening peak collapses while the night hours still solve.
    status, data = None, None
    for factor in (1.0, 1.3, 1.6, 2.0, 2.5):
        scaled = copy.deepcopy(net)
        for element in scaled.values():
            if str(element.get("typ", "")).startswith("Load"):
                element["p_mw"] = str(float(element["p_mw"]) * factor)
                element["q_mvar"] = str(float(element["q_mvar"]) * factor)
        status, data = run(scaled, TIME_SERIES)
        if data.get("error") or data.get("failed_time_steps"):
            break
    assert status == 200 and not data.get("error"), data.get("message")
    failed = data["failed_time_steps"]
    assert failed, "expected at least one unsolved hour"
    assert 0 < len(failed) < 24
    assert data["timeseries_converged"] is False
    assert [i for i, ok in enumerate(data["time_step_converged"]) if not ok] == failed
    steps_with_rows = {row["time_step"] for row in data["busbars"]}
    assert steps_with_rows.isdisjoint(failed), "failed hours must not carry result rows"
    assert len(steps_with_rows) == 24 - len(failed)
    print(f"time series OK: {len(failed)} unsolved hour(s) reported, {len(steps_with_rows)} solved")


def test_line_between_dc_buses():
    net = network("study_italian_grid_hvdc.json")
    status, data = run(net, LOAD_FLOW)
    assert status == 400, status
    assert "DC-LN-01" in data["error"] and "DC line" in data["error"], data["error"]

    for element in net.values():
        if str(element.get("userFriendlyName", "")).startswith("DC-LN"):
            element["length_km"], element["r_ohm_per_km"] = "100", "0.01"
    status, data = run(net, LOAD_FLOW)
    assert status == 200 and not data.get("error"), data.get("message") or data.get("error")
    assert len(data.get("linedcs") or []) == 3, "the three lines are calculated as DC lines"
    assert sum("calculated as a DC line" in w for w in data.get("warnings", [])) == 3
    print("DC line OK: rejected by name without data, solved as a DC line with data")


def test_zero_impedance_line_is_named():
    net = network("study_time_series_basic.json")
    line = next(v for v in net.values() if str(v.get("typ", "")).startswith("Line"))
    label = line.get("userFriendlyName") or line["name"]
    line["length_km"] = "0"
    status, data = run(net, LOAD_FLOW)
    assert status == 400, status
    assert label in data["error"] and "no impedance" in data["error"], data["error"]
    print("zero-impedance line OK: rejected by name")


def test_minimum_short_circuit_inputs():
    net = network("study_time_series_basic.json")
    grid = next(v for v in net.values() if str(v.get("typ", "")).startswith("External Grid"))
    grid_label = grid.get("userFriendlyName") or grid["name"]

    grid["s_sc_min_mva"] = "0"
    status, data = run(net, SC_MIN)
    assert status == 200 and data.get("error"), "S\"k min = 0 must stop the minimum case"
    assert grid_label in data["message"] and "minimum short-circuit power" in data["message"], data["message"]
    assert "Ybus" not in data["message"]

    grid["s_sc_min_mva"] = str(float(grid.get("s_sc_max_mva") or 1000) * 0.8)
    grid["rx_min"] = grid.get("rx_min") if float(grid.get("rx_min") or 0) > 0 else "0.1"
    for element in net.values():
        if str(element.get("typ", "")).startswith("Line"):
            element["endtemp_degree"] = "0"
    status, data = run(net, SC_MIN)
    assert status == 200 and not data.get("error"), data.get("message")
    assert any("end temperature" in w for w in data.get("warnings", [])), data.get("warnings")
    assert all(b["ikss_ka"] is not None and b["ikss_ka"] > 0 for b in data["busbars"])

    # With the end temperature entered there is nothing to warn about.
    for element in net.values():
        if str(element.get("typ", "")).startswith("Line"):
            element["endtemp_degree"] = "80"
    status, data = run(net, SC_MIN)
    assert status == 200 and not data.get("error"), data.get("message")
    assert not any("end temperature" in w for w in data.get("warnings", []) or [])
    print("minimum short circuit OK: missing S\"k min named, end temperature defaulted with a warning")


def test_empty_and_unsupplied_diagrams():
    """Every study answers in plain words when there is nothing to calculate.

    A diagram without buses, or without any source, used to end in "division by zero" (ANSI),
    "max() arg is an empty sequence" (economic analysis, time series) or pandapower's
    "No reference bus is available".
    """
    studies = {
        "contingency": CONTINGENCY, "time series": TIME_SERIES, "economic": ECONOMIC,
        "ANSI": {"typ": "ShortCircuitAnsi Parameters", "fault_type": "3ph"},
        "arc flash": {"typ": "ArcFlashPandaPower Parameters", "electrode_config": "VCB",
                      "working_distance_mm": "455", "conductor_gap_mm": "25", "clearing_time_s": "0.2"},
        "OPF": {"typ": "OptimalPowerFlowPandaPower Parameters", "opf_type": "ac", "frequency": "50",
                "ac_algorithm": "pypower", "dc_algorithm": "pypower", "calculate_voltage_angles": "auto",
                "init": "pf", "delta": "1e-10", "trafo_model": "t", "trafo_loading": "current",
                "ac_line_model": "pi", "numba": True, "suppress_warnings": True, "cost_function": "none"},
        "voltage stability": {"typ": "VoltageStabilityPandaPower Parameters", "mode": "all_loads"},
    }
    no_source = {k: v for k, v in network("study_time_series_basic.json").items()
                 if not str(v.get("typ", "")).startswith("External Grid")}
    # Short-circuit studies accept any source, so for them the PV unit has to go as well.
    no_sc_source = {k: v for k, v in no_source.items() if not str(v.get("typ", "")).startswith("Static Generator")}
    raw_texts = ("division by zero", "empty sequence", "No reference bus", "Server error")
    for label, params in studies.items():
        unsupplied = no_sc_source if label in ("ANSI", "arc flash") else no_source
        for case, net, expect in (("no buses", {}, "no buses"), ("no source", unsupplied, "no in-service")):
            status, data = run(net, params)
            text = str(data.get("message") or data.get("error") or "")
            assert status == 200, (label, case, status, text)
            assert data.get("error"), (label, case)
            assert expect in text, (label, case, text)
            assert not any(raw in text for raw in raw_texts), (label, case, text)
    print("empty / unsupplied diagrams OK: plain message from", ", ".join(studies))


def main() -> None:
    test_contingency_base_case_and_trafo3w()
    test_contingency_leaves_network_unchanged()
    test_statcom_network_in_repeated_studies()
    test_time_series_reports_failed_steps()
    test_line_between_dc_buses()
    test_zero_impedance_line_is_named()
    test_minimum_short_circuit_inputs()
    test_empty_and_unsupplied_diagrams()
    print("All template robustness checks passed.")


if __name__ == "__main__":
    main()
