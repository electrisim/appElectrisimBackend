"""Load flow with VSC converters and a DC grid, in the payload format the app sends.

VSC, B2B VSC, DC Bus and Load DC elements used to be dropped by the load-flow payload
builder, and DC Lines were sent without their two bus connections, so a diagram with an
HVDC link ran as if the DC part did not exist. This builds the payload the fixed builder
sends (the same shape the app produced for a test diagram).

Network: AC bus A (grid) and AC bus B (load) joined by an AC line. VSC1 at A holds the DC
voltage, VSC2 at B sends a fixed power into the DC grid, and a DC cable joins the two DC
buses. A second case uses a B2B VSC at B instead of the VSC.

Run with ``python samples/test_loadflow_vsc_dc.py``.
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

GRID = {"s_sc_max_mva": "1000", "s_sc_min_mva": "800", "rx_max": "0.1", "rx_min": "0.1",
        "r0x0_max": "0.1", "x0x_max": "1.0"}


def converter(typ, name, ac_bus, dc_bus, mode_dc, value_dc):
    return {
        "typ": typ, "name": name, "id": name, "userFriendlyName": name.upper(),
        "bus": ac_bus, "bus_dc": dc_bus,
        "r_ohm": "0.5", "x_ohm": "5", "r_dc_ohm": "0.05",
        "control_mode_ac": "q_mvar", "control_value_ac": "0",
        "control_mode_dc": mode_dc, "control_value_dc": value_dc, "in_service": "true",
    }


def network(second_converter_typ="VSC1"):
    return {
        "0": {"typ": "PowerFlowPandaPower Parameters", "frequency": "50", "algorithm": "nr",
              "calculate_voltage_angles": "auto", "initialization": "auto", "exportPython": False,
              "user_email": "test@example.com"},
        "1": {"typ": "Bus0", "name": "mxCell_a", "id": "a", "vn_kv": "110", "userFriendlyName": "A"},
        "2": {"typ": "Bus1", "name": "mxCell_b", "id": "b", "vn_kv": "110", "userFriendlyName": "B"},
        "3": {"typ": "DC Bus0", "name": "mxCell_dc1", "id": "dc1", "vn_kv": "150", "in_service": "true",
              "userFriendlyName": "DC1"},
        "4": {"typ": "DC Bus1", "name": "mxCell_dc2", "id": "dc2", "vn_kv": "150", "in_service": "true",
              "userFriendlyName": "DC2"},
        "5": {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_a", "vm_pu": "1.0",
              "va_degree": "0", "in_service": "true", "userFriendlyName": "Grid", **GRID},
        "6": {"typ": "Line0", "name": "mxCell_l", "id": "l", "busFrom": "mxCell_a", "busTo": "mxCell_b",
              "r_ohm_per_km": "0.06", "x_ohm_per_km": "0.4", "c_nf_per_km": "9", "g_us_per_km": "0",
              "length_km": "50", "max_i_ka": "0.6", "type": "ol", "parallel": "1", "df": "1",
              "in_service": "true", "userFriendlyName": "AC line"},
        "7": {"typ": "Load0", "name": "mxCell_ld", "id": "ld", "bus": "mxCell_b", "p_mw": "40", "q_mvar": "10",
              "scaling": "1", "const_z_percent": "0", "const_i_percent": "0", "sn_mva": "0", "type": "wye",
              "in_service": "true", "userFriendlyName": "Load"},
        "8": converter("VSC0", "vsc1", "mxCell_a", "mxCell_dc1", "vm_pu", "1.0"),
        "9": converter(second_converter_typ, "vsc2", "mxCell_b", "mxCell_dc2", "p_mw", "10"),
        "10": {"typ": "DC Line0", "name": "mxCell_dcl", "id": "dcl", "busFrom": "mxCell_dc1", "busTo": "mxCell_dc2",
               "p_mw": "0", "loss_percent": "0", "loss_mw": "0", "vm_from_pu": "1", "vm_to_pu": "1",
               "in_service": "true", "userFriendlyName": "DC cable"},
        # "Load DC" also starts with "Load"; it must not be built as an AC load.
        "11": {"typ": "Load DC0", "name": "mxCell_ldc", "id": "ldc", "bus": "mxCell_dc1", "p_mw": "2",
               "in_service": "true", "userFriendlyName": "DC load"},
    }


def solve(payload):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=payload)
    assert response.status_code == 200, response.data[:400]
    data = json.loads(response.data)
    assert not data.get("error"), data.get("error")
    return data


def main() -> None:
    data = solve(network())
    vscs = {v["id"]: v for v in data.get("vscs", [])}
    assert set(vscs) == {"vsc1", "vsc2"}, data.keys()
    assert data.get("linedcs"), "the DC cable must be in the results"
    # VSC2 sends 10 MW into the DC grid; VSC1 takes it out (minus the losses).
    p1, p2 = float(vscs["vsc1"]["p_mw"]), float(vscs["vsc2"]["p_mw"])
    print(f"VSC P: vsc1={p1:.3f} MW, vsc2={p2:.3f} MW")
    assert abs(abs(p2) - 10.0) < 0.5, p2
    assert p1 * p2 < 0, "the two converters must carry power in opposite directions"
    # VSC1 also feeds the 2 MW DC load, so it carries about 12 MW.
    assert abs(abs(p1) - 12.0) < 0.5, p1
    assert [ld["id"] for ld in data.get("loads", [])] == ["ld"], "Load DC must not appear as an AC load"
    assert abs(float(data["loadsdc"][0]["p_mw"]) - 2.0) < 1e-6, data.get("loadsdc")
    dc_buses = {b["id"]: b for b in data.get("dcbuses", [])}
    assert set(dc_buses) == {"dc1", "dc2"}, data.get("dcbuses")
    assert abs(float(dc_buses["dc1"]["vm_pu"]) - 1.0) < 1e-6, "VSC1 holds the DC voltage"
    print("VSC + DC line load flow OK")

    # A battery drawn on its own DC bus (no VSC; the AC Storage element models the PCS) is a DC
    # island. pandapower cannot solve it ("matrix - rhs dimension mismatch"), so it is left out.
    island = network()
    island["12"] = {"typ": "DC Bus2", "name": "mxCell_bat", "id": "bat", "vn_kv": "1.5", "in_service": "true",
                    "userFriendlyName": "Battery DC"}
    island["13"] = {"typ": "Source DC0", "name": "mxCell_src", "id": "src", "bus": "mxCell_bat", "vm_pu": "1.0",
                    "in_service": "true", "userFriendlyName": "Battery"}
    data = solve(island)
    assert {v["id"] for v in data.get("vscs", [])} == {"vsc1", "vsc2"}, "the linked DC grid must stay"
    assert "bat" not in {b["id"] for b in data.get("dcbuses", [])}
    print("DC island without converter skipped OK")

    # BESS Sizing on a plant whose batteries are drawn on DC buses behind the AC Storage element.
    bess = {
        "1": {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_poc", "vm_pu": "1",
              "va_degree": "0", "in_service": "true", **GRID},
        "2": {"typ": "Bus0", "name": "mxCell_poc", "id": "poc", "vn_kv": "132", "userFriendlyName": "POC"},
        "3": {"typ": "Bus1", "name": "mxCell_lv", "id": "lv", "vn_kv": "0.69", "userFriendlyName": "LV"},
        "4": {"typ": "Transformer0", "name": "mxCell_tr", "id": "tr", "hv_bus": "mxCell_poc", "lv_bus": "mxCell_lv",
              "sn_mva": "21.3", "vn_hv_kv": "132", "vn_lv_kv": "0.69", "vkr_percent": "0.5", "vk_percent": "6",
              "pfe_kw": "0", "i0_percent": "0", "shift_degree": "0", "tap_pos": "0", "tap_neutral": "0",
              "tap_max": "0", "tap_min": "0", "tap_step_percent": "0", "tap_side": "hv", "parallel": "1",
              "in_service": "true", "userFriendlyName": "TR"},
        "5": {"typ": "Storage0", "name": "mxCell_st", "id": "storage_0", "bus": "mxCell_lv", "p_mw": "0",
              "q_mvar": "0", "max_e_mwh": "29.7", "min_e_mwh": "0", "soc_percent": "50", "sn_mva": "21.3",
              "scaling": "1", "in_service": "true", "userFriendlyName": "PCS"},
        "6": {"typ": "DC Bus0", "name": "mxCell_bat", "id": "bat", "vn_kv": "1.5", "in_service": "true",
              "userFriendlyName": "Battery DC"},
        "7": {"typ": "Source DC0", "name": "mxCell_src", "id": "src", "bus": "mxCell_bat", "vm_pu": "1.0",
              "in_service": "true", "userFriendlyName": "Battery"},
        "bess_sizing_params": {"typ": "BessSizingPandaPower", "storageId": "storage_0", "pocBusbarId": "poc",
                               "calculationMode": "single", "tolerance": 0.001, "maxIterations": 50, "kpP": 0.5,
                               "kpQ": 0.5, "frequency": 50, "algorithm": "nr", "targetP": 10, "targetQ": 2,
                               "user_email": "test@example.com"},
    }
    sized = solve(bess)
    assert sized.get("converged") is True, sized
    assert abs(float(sized["achieved_p_mw"]) - 10.0) < 0.05, sized
    print(f"BESS sizing with a battery DC island OK: {float(sized['bess_p_mw']):.2f} MW")

    # OpenDSS has no DC model: DC elements are dropped before it builds AC buses, lines and loads.
    import opendss_electrisim
    kept = opendss_electrisim._without_dc_elements(network())
    assert {v["typ"] for v in kept.values()} == {
        "PowerFlowPandaPower Parameters", "Bus0", "Bus1", "External Grid0", "Line0", "Load0"}, kept
    print("OpenDSS DC filter OK")

    # A B2B VSC drawn between an AC bus and a DC bus is solved as a VSC.
    b2b = solve(network(second_converter_typ="B2B VSC0"))
    ids = {v["id"] for v in b2b.get("vscs", [])}
    assert ids == {"vsc1", "vsc2"}, ids
    print("B2B VSC load flow OK")


if __name__ == "__main__":
    main()
