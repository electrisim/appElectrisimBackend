"""OpenDSS load flow: transformers with "null" tap data and line/transformer switches.

1. create_transformer_element read pfe/tap fields with float(); CIGRE and imported transformers send
   "null", the ValueError was swallowed and the transformer was left out, so every bus behind it had 0 V.
2. create_switch_element called dss.ActiveElement (not in opendssdirect); the AttributeError was
   swallowed, so an open line switch never opened anything (CIGRE MV tie lines stayed closed).
3. A closed switch at the other end of the line re-closed it, and a closed transformer switch
   re-enabled a transformer that was out of service.

Run with ``python samples/test_opendss_switch_trafo.py``.
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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app  # noqa: E402

NULL_TAPS = {"tap_side": "null", "tap_neutral": "null", "tap_min": "null", "tap_max": "null",
             "tap_step_percent": "null", "tap_step_degree": "null", "tap_pos": "null"}


def line(name, label):
    return {"typ": "Line", "name": name, "id": name.replace("_", "#"), "busFrom": "mxCell_b", "busTo": "mxCell_c",
            "r_ohm_per_km": "0.3", "x_ohm_per_km": "0.4", "length_km": "4", "c_nf_per_km": "0", "parallel": "1",
            "df": "1", "g_us_per_km": "0", "max_i_ka": "0.4", "type": "cs", "in_service": True,
            "r0_ohm_per_km": "0.9", "x0_ohm_per_km": "1.2", "c0_nf_per_km": "0", "endtemp_degree": "20",
            "userFriendlyName": label}


def base():
    return {
        "0": {"typ": "PowerFlowOpenDss Parameters", "frequency": "50", "mode": "Snapshot", "algorithm": "Normal",
              "loadmodel": "Powerflow", "maxIterations": "100", "tolerance": "0.0001", "controlmode": "Static",
              "exportCommands": False, "monteCarloNumber": "100", "monteCarloRandom": "Uniform",
              "monteCarloHour": "0", "exportOpenDSSResults": False, "exportPdfReport": False,
              "user_email": "test@example.com"},
        "1": {"typ": "Bus0", "name": "mxCell_a", "id": "a", "vn_kv": "110", "userFriendlyName": "HV"},
        "2": {"typ": "Bus1", "name": "mxCell_b", "id": "b", "vn_kv": "20", "userFriendlyName": "MV"},
        "3": {"typ": "Bus2", "name": "mxCell_c", "id": "c", "vn_kv": "20", "userFriendlyName": "Feeder end"},
        "4": {"typ": "External Grid", "name": "mxCell_eg", "id": "mxCell#eg", "bus": "mxCell_a", "vm_pu": 1.0,
              "va_degree": 0, "s_sc_max_mva": 5000, "s_sc_min_mva": 5000, "rx_max": 0.1, "rx_min": 0.1,
              "r0x0_max": 0.1, "x0x_max": 1, "in_service": True, "userFriendlyName": "Grid"},
        "5": {"typ": "Transformer", "name": "mxCell_t", "id": "mxCell#t", "busFrom": "mxCell_a", "busTo": "mxCell_b",
              "sn_mva": "25", "vk_percent": "12", "vkr_percent": "0.2", "vn_hv_kv": "110", "vn_lv_kv": "20",
              "pfe_kw": "null", "i0_percent": "null", "shift_degree": "30", "tap_phase_shifter": "false",
              "in_service": True, "userFriendlyName": "T1", **NULL_TAPS},
        "6": line("mxCell_l1", "L1"),
        "7": line("mxCell_l2", "L2"),
        "8": {"typ": "Load", "name": "mxCell_ld", "id": "mxCell#ld", "bus": "mxCell_c", "p_mw": "6", "q_mvar": "1.5",
              "sn_mva": "0", "scaling": "1", "type": "wye", "const_i_percent": "0", "const_z_percent": "0",
              "in_service": True, "pctSeriesRL": "100", "conn": "wye", "userFriendlyName": "Load"},
    }


def switch(key, label, bus, element, et, closed):
    return {"typ": "Switch", "name": key, "id": key.replace("_", "#"), "userFriendlyName": label,
            "bus": bus, "element": element, "et": et, "closed": closed}


def run(net):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=net)
    assert response.status_code == 200, response.data[:300]
    data = json.loads(response.data)
    assert not data.get("error"), data.get("message") or data.get("error")
    vm = {b["name"]: float(b["vm_pu"]) for b in data["busbars"]}
    amps = {ln["name"]: abs(float(ln["i_from_ka"])) for ln in data["lines"]}
    return vm, amps, data.get("warnings") or []


def main() -> None:
    # 1. Transformer with "null" taps / losses is built (feeder end was 0 V before).
    vm, amps, _ = run(base())
    assert vm["mxCell_b"] > 0.9 and vm["mxCell_c"] > 0.9, vm
    assert abs(amps["mxCell_l1"] - amps["mxCell_l2"]) < 1e-4, amps

    # Taps: null position == neutral; tap_pos == tap_neutral (non-zero) is still the neutral ratio.
    tapped = base()
    tapped["5"].update({"tap_side": "hv", "tap_neutral": "2", "tap_pos": "2", "tap_step_percent": "2.5",
                        "tap_min": "-9", "tap_max": "9"})
    vm_t, _, _ = run(tapped)
    assert abs(vm_t["mxCell_b"] - vm["mxCell_b"]) < 1e-6, (vm_t, vm)

    # 2/3. L2 opened at the feeder end; the closed switch at its other end comes later and must not re-close it.
    opened = base()
    opened["9"] = switch("mxCell_s_open", "S open", "mxCell_c", "mxCell_l2", "l", False)
    opened["10"] = switch("mxCell_s_closed", "S closed", "mxCell_b", "mxCell_l2", "l", True)
    vm_o, amps_o, _ = run(opened)
    assert amps_o["mxCell_l2"] < 1e-3, amps_o
    assert amps_o["mxCell_l1"] > 1.8 * amps["mxCell_l1"], (amps_o, amps)
    assert vm_o["mxCell_c"] < vm["mxCell_c"], (vm_o, vm)

    # A closed switch must not bring an out-of-service transformer back.
    off = base()
    off["5"]["in_service"] = False
    off["9"] = switch("mxCell_s_t", "S trafo", "mxCell_a", "mxCell_t", "t", True)
    vm_off, _, _ = run(off)
    assert vm_off["mxCell_c"] < 0.05, vm_off

    # An open transformer switch disconnects the MV side.
    open_t = base()
    open_t["9"] = switch("mxCell_s_t", "S trafo", "mxCell_a", "mxCell_t", "t", False)
    vm_ot, _, _ = run(open_t)
    assert vm_ot["mxCell_c"] < 0.05, vm_ot

    print(f"OpenDSS switches/trafo OK: feeder end {vm['mxCell_c']:.4f} pu (2 lines), "
          f"{vm_o['mxCell_c']:.4f} pu (L2 open); L1 {amps['mxCell_l1'] * 1000:.1f} A -> {amps_o['mxCell_l1'] * 1000:.1f} A")


if __name__ == "__main__":
    main()
