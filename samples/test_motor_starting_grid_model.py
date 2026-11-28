"""Motor Starting models the sources alike in steady-state and dynamic mode.

Before the start every source holds the voltage of the load flow. From the start on:

- each External Grid is a fixed voltage behind its short-circuit impedance, from S"k min and
  R/X min (the default) or S"k max and R/X max (the study's ``grid_sc_case``), in both modes,
  with or without a generator in the network;
- a synchronous generator is its own dynamic model in dynamic mode (GENROU and exciter); in the
  steady-state locked-rotor snapshot it is a fixed voltage behind its transient reactance xd'
  (its voltage regulator has not acted yet), and it controls its voltage again after the start.

Steady-state mode used to keep the External Grid an ideal source and every generator on perfect
voltage control, so neither bus could dip: with a 10 MVA generator at the motor bus the motor bus
dipped 0 % in steady state and 11 % in dynamic mode. Dynamic mode kept the External Grid an
ideal source whenever the network had a generator.

1. External Grid only, at 1.02 pu with a load on the network before the start: right after the
   start the grid-bus and motor-bus dips of the two modes agree within 3 %, for S"k min and for
   S"k max, and the grid-bus dip grows with the grid impedance (S"k max / S"k min).
2. A generator at the grid bus, and one at the motor bus: the modes agree within 5 %. After the
   start the generator's bus is back at its set voltage.
3. A generator alone feeds the motor through a line: the steady-state motor-bus voltage is the
   exact divider Z_eq / (Z_eq + Z_line + j xd'), with xd' entered or the dynamic model's default
   0.3 pu, on the generator's rating and rated voltage.
4. An External Grid without S"k min: both modes use S"k max and say so.
5. The study leaves the network as it found it.

The loads here are constant impedance: ANDES turns PQ loads into constant impedance during the
simulation, so constant-power loads would make the modes differ for a reason of their own.

Run with ``python samples/test_motor_starting_grid_model.py``.
"""
from __future__ import annotations

import cmath
import contextlib
import io
import json
import math
import os
import sys
import warnings

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandapower as pp  # noqa: E402

import app  # noqa: E402
import motor_starting_electrisim as ms  # noqa: E402
import pandapower_electrisim  # noqa: E402

CLIENT = app.app.test_client()
T_START = 0.1
T_END = 5.0

# The "Industrial plant 6 kV" compressor: a fan-type load (c3 = 1) at 85 % loading.
MOTOR = {"typ": "Motor0", "name": "mxCell_m1", "id": "m1", "userFriendlyName": "Compressor", "bus": "mxCell_mv",
         "pn_mech_mw": "2.5", "cos_phi": "0.89", "cos_phi_n": "0.89", "efficiency_percent": "96.5",
         "efficiency_n_percent": "96.5", "loading_percent": "85", "scaling": "1", "lrc_pu": "6", "rx": "0.1",
         "vn_kv": "6", "Hm": "0.5", "tm_c1": "0", "tm_c2": "0", "tm_c3": "1", "in_service": "true"}
LOAD = {"typ": "Load0", "name": "mxCell_ld", "id": "ld", "userFriendlyName": "Process load", "bus": "mxCell_mv",
        "p_mw": "2", "q_mvar": "1", "const_z_percent": "100", "const_i_percent": "0", "sn_mva": "0",
        "scaling": "1", "type": "wye", "in_service": "true"}


def study(mode, **settings):
    params = {"typ": "MotorStartingPandaPower Parameters", "mode": mode, "motor_ids": "all",
              "starting_method": "dol", "voltage_limit_percent": "15", "thermal_limit_percent": "100",
              "t_start": str(T_START), "t_end": str(T_END), "frequency": "50", "sn_mva": "100",
              "user_email": "test@example.com"}
    params.update(settings)
    return params


def bus(key, vn):
    return {"typ": "Bus0", "name": f"mxCell_{key}", "id": key, "vn_kv": str(vn), "userFriendlyName": key}


def grid(bus_key, s_max, s_min, rx, vm="1"):
    return {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "userFriendlyName": "Utility",
            "bus": f"mxCell_{bus_key}", "vm_pu": vm, "va_degree": "0", "s_sc_max_mva": str(s_max),
            "s_sc_min_mva": str(s_min), "rx_max": str(rx), "rx_min": str(rx), "r0x0_max": "0.1",
            "x0x_max": "1", "in_service": "true"}


def transformer(hv_key, vn_hv, sn):
    # Rated at its bus voltages and without a magnetising branch, so both modes model it alike.
    return {"typ": "Transformer0", "name": "mxCell_tr", "id": "tr", "userFriendlyName": "TR",
            "hv_bus": f"mxCell_{hv_key}", "lv_bus": "mxCell_mv", "sn_mva": str(sn), "vn_hv_kv": str(vn_hv),
            "vn_lv_kv": "6", "vkr_percent": "0.5", "vk_percent": "8", "pfe_kw": "0", "i0_percent": "0",
            "vector_group": "Dyn", "shift_degree": "150", "tap_side": "hv", "tap_pos": "0", "tap_neutral": "0",
            "tap_max": "2", "tap_min": "-2", "tap_step_percent": "2.5", "parallel": "1", "in_service": "true"}


def generator(bus_key, sn, p, vn, slack=False, **dyn):
    el = {"typ": "Generator", "name": "mxCell_g", "id": "g", "bus": f"mxCell_{bus_key}", "userFriendlyName": "Gen",
          "p_mw": str(p), "vm_pu": "1", "sn_mva": str(sn), "scaling": "1", "slack": "true" if slack else "false",
          "vn_kv": str(vn), "xdss_pu": "0.25", "rdss_ohm": "0", "cos_phi": "0.85", "pg_percent": "0",
          "power_station_trafo": "0", "in_service": "true"}
    el.update({k: str(v) for k, v in dyn.items()})
    return el


def diagram(elements, mode, **settings):
    data = {"0": study(mode, **settings)}
    data.update({str(k): dict(v) for k, v in enumerate(elements, start=1)})
    return data


def solve(data):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = CLIENT.post("/", json=data)
    assert response.status_code == 200, response.data[:400]
    out = json.loads(response.data)
    assert not out.get("error"), (out.get("message"), out.get("exception"))
    return out


def steady(elements, **settings):
    out = solve(diagram(elements, "steady", **settings))
    assert {b["id"] for b in out["buses"]} == {el["id"] for el in elements if el["typ"].startswith("Bus")}, out["buses"]
    return out, {b["id"]: b for b in out["buses"]}


def dynamic(elements, **settings):
    """The result and each bus's dip in the first sample after the motor is switched on."""
    out = solve(diagram(elements, "dynamic", **settings))
    t = out["timeseries"]["t"]
    k = next(i for i, tk in enumerate(t) if tk > T_START + 1e-9)
    first = {key.replace("mxCell_", ""): (ser["v"][0] - ser["v"][k]) / ser["v"][0] * 100.0
             for key, ser in out["timeseries"]["buses"].items()}
    assert all(m["pass"] for m in out["motors"]), out["motors"]
    return out, first


def agree(label, s_buses, d_first, keys, tol):
    for key in keys:
        s, d = s_buses[key]["dip_percent"], d_first[key]
        print(f"  {label}: {key} dip steady {s:.3f} %, dynamic {d:.3f} %")
        assert s > 0.1 and abs(d / s - 1.0) < tol, (label, key, s, d)


# --- 1. External Grid only -----------------------------------------------------------------

def test_grid_only():
    elements = [grid("hv", 3000, 2000, 0.1, vm="1.02"), bus("hv", 110), bus("mv", 6), transformer("hv", 110, 6.3),
                MOTOR, LOAD]
    dips = {}
    for case in ("min", "max"):
        settings = {"grid_sc_case": case} if case == "max" else {}  # S"k min is the default
        s_out, s_buses = steady(elements, **settings)
        d_out, d_first = dynamic(elements, **settings)
        assert s_out["parameters"]["grid_sc_case"] == case and d_out["parameters"]["grid_sc_case"] == case
        # Before the start the grid holds its set voltage, as in the load flow.
        assert abs(s_buses["hv"]["vm_before"] - 1.02) < 1e-6, s_buses["hv"]
        assert any(f"{case} short-circuit power {3000 if case == 'max' else 2000} MVA" in n
                   for n in s_out["defaults_applied"]), s_out["defaults_applied"]
        agree(f'S"k {case}', s_buses, d_first, ("hv", "mv"), 0.03)
        dips[case] = s_buses["hv"]["dip_percent"]
    # The grid's share of the dip grows with its impedance.
    assert abs(dips["min"] / dips["max"] / 1.5 - 1.0) < 0.03, dips


# --- 2. with a generator ----------------------------------------------------------------------

def test_with_generator():
    networks = {
        "50 MVA at the 110 kV grid bus": [grid("hv", 3000, 2000, 0.1), bus("hv", 110), bus("mv", 6),
                                          transformer("hv", 110, 6.3), MOTOR, LOAD, generator("hv", 50, 20, 110)],
        "10 MVA at the 6 kV motor bus": [grid("hv", 300, 300, 0.1), bus("hv", 20), bus("mv", 6),
                                         transformer("hv", 20, 10), MOTOR, LOAD, generator("mv", 10, 5, 6)],
    }
    for label, elements in networks.items():
        s_out, s_buses = steady(elements)
        _, d_first = dynamic(elements)
        agree(label, s_buses, d_first, ("hv", "mv"), 0.05)
        gen_bus = elements[-1]["bus"].replace("mxCell_", "")
        # After the start the generator controls its voltage again.
        assert abs(s_buses[gen_bus]["vm_after"] - 1.0) < 1e-6, s_buses[gen_bus]
        assert any("transient reactance xd' = 0.3 pu" in n for n in s_out["defaults_applied"]), s_out["defaults_applied"]
    # The generator's own bus dips too (it used to hold 1.0 pu through the start).
    assert s_buses["mv"]["dip_percent"] > 10.0, s_buses["mv"]


# --- 3. the generator's transient reactance, exactly ---------------------------------------------

Z_LINE = complex(0.1, 0.4)  # ohm: 1 km of 0.1 + j0.4 ohm/km, no charging


def test_generator_divider():
    sn_m = 2.5 / 0.965 / 0.89
    z_lr = 6.0 ** 2 / (6.0 * sn_m) * cmath.exp(1j * math.atan2(1.0, 0.1))  # locked rotor at 6 kV, ohm
    line = {"typ": "Line0", "name": "mxCell_ln", "id": "ln", "userFriendlyName": "Feeder", "busFrom": "mxCell_g",
            "busTo": "mxCell_mv", "r_ohm_per_km": "0.1", "x_ohm_per_km": "0.4", "c_nf_per_km": "0",
            "g_us_per_km": "0", "length_km": "1", "max_i_ka": "2", "type": "cs", "parallel": "1", "df": "1",
            "in_service": "true"}
    cases = [
        ("xd' entered", generator("g", 10, 0, 6, slack=True, dyn_xd1=0.25), 0.25, 6.0),
        ("xd' default", generator("g", 10, 0, 6, slack=True), 0.3, 6.0),
        ("rated 6.3 kV", generator("g", 10, 0, 6.3, slack=True, dyn_xd1=0.25), 0.25, 6.3),
    ]
    for label, gen, xd1, vn_gen in cases:
        # No load before the start, so the voltage behind xd' is the set 1.0 pu.
        _, buses = steady([gen, bus("g", 6), bus("mv", 6), line, MOTOR])
        z_gen = 1j * xd1 * vn_gen ** 2 / 10.0  # ohm, on the generator's rating
        v_expected = abs(z_lr / (z_lr + Z_LINE + z_gen))
        print(f"  generator alone, {label}: motor bus {buses['mv']['vm_during']:.5f} pu (expected {v_expected:.5f})")
        assert abs(buses["mv"]["vm_during"] - v_expected) < 2e-4, (label, buses["mv"], v_expected)
        assert abs(buses["g"]["vm_after"] - 1.0) < 1e-6, buses["g"]


# --- 4. S"k min not set ----------------------------------------------------------------------------

def test_min_not_set():
    elements = [grid("hv", 3000, 0, 0.1), bus("hv", 110), bus("mv", 6), transformer("hv", 110, 6.3), MOTOR]
    s_out, s_buses = steady(elements)
    _, s_max = steady(elements, grid_sc_case="max")
    d_out, _ = dynamic(elements)
    for out in (s_out, d_out):
        assert any("Min Short Circuit Power is not set; its impedance uses the Max Short Circuit Power, 3000 MVA"
                   in w for w in out["warnings"]), out["warnings"]
    assert abs(s_buses["hv"]["dip_percent"] - s_max["hv"]["dip_percent"]) < 1e-9, (s_buses["hv"], s_max["hv"])


# --- 5. the network is left as it was --------------------------------------------------------------

def test_network_restored():
    data = diagram([grid("hv", 3000, 2000, 0.1), bus("hv", 110), bus("mv", 6), transformer("hv", 110, 6.3), MOTOR,
                    LOAD, generator("mv", 5, 2, 6)], "steady")
    with contextlib.redirect_stdout(io.StringIO()):
        net = pp.create_empty_network()
        buses = pandapower_electrisim.create_busbars(data, net)
        pandapower_electrisim.create_other_elements(data, net, "0", buses)
    tables = ("bus", "ext_grid", "gen", "impedance", "shunt")
    before = {name: net[name].copy() for name in tables}
    out = json.loads(ms.motor_starting(net, data["0"], data))
    assert not out.get("error"), out
    for name in tables:
        assert net[name].equals(before[name]), (name, net[name], before[name])


def main() -> None:
    if not ms._HAS_ANDES:
        print("SKIP: ANDES is not installed.")
        return
    test_grid_only()
    test_with_generator()
    test_generator_divider()
    test_min_not_set()
    test_network_restored()
    print("motor starting source model (External Grid and generators) OK")


if __name__ == "__main__":
    main()
