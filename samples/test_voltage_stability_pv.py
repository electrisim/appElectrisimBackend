"""Voltage Stability Margin (P-V curves): the collapse point must match the textbook two-bus result.

A load P + jQ fed through a lossless reactance X from a stiff source of voltage V has its
maximum power transfer at

    Pmax = V^2 * cos(phi) / (2 X (1 + sin(phi)))        and, at unity power factor,
    Pmax = V^2 / (2 X)   with the load bus at V / sqrt(2) = 0.707 p.u.

The study steps the load up until the load flow no longer solves, so its tip must sit just
below these values. Further checks: the order of the limits on the IEEE 39-bus template, the
all-loads mode, and the plain messages for the slack bus and for a diagram without loads.

Run with ``python samples/test_voltage_stability_pv.py``.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import math
import os
import sys
import warnings

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FIXTURES = os.path.join(ROOT, "samples", "fixtures")

import app  # noqa: E402

CLIENT = app.app.test_client()
V_KV = 110.0
X_OHM = 40.0


def post(payload):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = CLIENT.post("/", json=payload)
    assert response.status_code == 200, (response.status_code, response.get_data(as_text=True)[:300])
    return json.loads(response.get_data(as_text=True))


def two_bus(power_factor, **params):
    study = {"typ": "VoltageStabilityPandaPower Parameters", "mode": "bus", "bus_id": "b",
             "power_factor": str(power_factor), "frequency": "50", "tip_tolerance_percent": "0.05",
             "user_email": "t@e.com"}
    study.update(params)
    return {
        "0": study,
        "1": {"typ": "Bus0", "name": "mxCell_a", "id": "a", "vn_kv": str(V_KV), "userFriendlyName": "Grid bus"},
        "2": {"typ": "Bus1", "name": "mxCell_b", "id": "b", "vn_kv": str(V_KV), "userFriendlyName": "Site"},
        "3": {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_a", "vm_pu": "1.0",
              "va_degree": "0", "s_sc_max_mva": "100000", "s_sc_min_mva": "80000", "rx_max": "0.1",
              "rx_min": "0.1", "r0x0_max": "0.1", "x0x_max": "1.0", "in_service": "true"},
        "4": {"typ": "Line0", "name": "mxCell_l", "id": "l", "busFrom": "mxCell_a", "busTo": "mxCell_b",
              "r_ohm_per_km": "0.000001", "x_ohm_per_km": str(X_OHM / 100.0), "c_nf_per_km": "0",
              "g_us_per_km": "0", "length_km": "100", "max_i_ka": "1", "type": "ol", "parallel": "1",
              "df": "1", "in_service": "true", "userFriendlyName": "Feeder"},
    }


def test_two_bus_matches_theory():
    data = post(two_bus(1.0))
    assert not data.get("error"), data.get("error")
    p_max = V_KV ** 2 / (2 * X_OHM)                      # 151.25 MW
    assert p_max * 0.995 <= data["tip_mw"] <= p_max, (data["tip_mw"], p_max)
    # the last solved point is just before the tip, so the voltage is a little above 0.707
    assert 0.70 <= data["tip_min_vm_pu"] <= 0.74, data["tip_min_vm_pu"]
    print(f"two-bus, pf 1.00: tip {data['tip_mw']:.2f} MW, theory {p_max:.2f} MW")

    phi = math.acos(0.95)
    data = post(two_bus(0.95))
    p_max = V_KV ** 2 * math.cos(phi) / (2 * X_OHM * (1 + math.sin(phi)))   # 109.50 MW
    assert p_max * 0.995 <= data["tip_mw"] <= p_max * 1.0005, (data["tip_mw"], p_max)
    print(f"two-bus, pf 0.95: tip {data['tip_mw']:.2f} MW, theory {p_max:.2f} MW")

    # the voltage limit comes first: V = 0.95 p.u. is reached long before the tip
    kinds = [limit["kind"] for limit in data["limits"]]
    assert kinds[0] == "voltage" and kinds[-1] == "collapse", kinds
    voltage = data["limits"][0]
    assert voltage["element"] == "Site" and 0 < voltage["x_mw"] < data["tip_mw"]
    assert data["binding_limit"]["kind"] == "voltage"

    # curve data is consistent: load rises, the study bus voltage falls all the way
    xs = data["x_mw"]
    assert all(b > a for a, b in zip(xs, xs[1:])) and abs(xs[-1] - data["tip_mw"]) < 1e-9
    site = next(c for c in data["curves"] if c["is_study_bus"])
    assert len(site["vm_pu"]) == len(xs)
    assert all(b < a for a, b in zip(site["vm_pu"], site["vm_pu"][1:]))


def test_messages():
    data = post(two_bus(0.95, bus_id="a"))
    assert "slack bus" in (data.get("error") or ""), data
    data = post(two_bus(0.95, mode="all_loads"))
    assert "no in-service loads" in (data.get("error") or ""), data
    data = post(two_bus(0.95, bus_id="nope"))
    assert "Choose the bus" in (data.get("error") or ""), data
    print("messages OK: slack bus, no loads, unknown bus")


def test_case39_template():
    with open(os.path.join(FIXTURES, "opendss_lf_case39.json"), encoding="utf-8") as handle:
        raw = json.load(handle)
    net = {}
    for key, element in raw.items():
        if "Parameters" in str(element.get("typ", "")):
            continue
        element = copy.deepcopy(element)
        if str(element.get("typ", "")).startswith("Transformer"):      # OpenDSS payload field names
            element.setdefault("hv_bus", element.get("busFrom"))
            element.setdefault("lv_bus", element.get("busTo"))
        if str(element.get("typ", "")).startswith("Load"):
            element["const_z_percent"], element["const_i_percent"] = "0", "0"
        net[key] = element

    payload = {"0": {"typ": "VoltageStabilityPandaPower Parameters", "mode": "all_loads", "frequency": "60"}}
    payload.update(net)
    data = post(payload)
    assert not data.get("error"), data.get("error")
    assert data["tip_mw"] > data["base_mw"] > 0
    assert 5 < data["tip_margin_percent"] < 200, data["tip_margin_percent"]
    assert data["limits"][-1]["kind"] == "collapse"
    assert [l["x_mw"] for l in data["limits"]] == sorted(l["x_mw"] for l in data["limits"])
    assert len(data["curves"]) == 8 and len(data["weakest_buses"]) == 20
    assert data["load_flows_run"] < 200
    print(f"case39, all loads: {data['base_mw']:.0f} MW today, collapse at {data['tip_mw']:.0f} MW "
          f"(+{data['tip_margin_percent']:.0f} %), first limit: {data['binding_limit']['kind']}")


def main() -> None:
    test_two_bus_matches_theory()
    test_messages()
    test_case39_template()
    print("All voltage stability checks passed.")


if __name__ == "__main__":
    main()
