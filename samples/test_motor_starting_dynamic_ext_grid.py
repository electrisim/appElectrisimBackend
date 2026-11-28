"""Dynamic (ANDES) motor starting on a network whose only source is an External Grid.

Dynamic mode used to stop with "Failed to build ANDES system with motors. Transient /
eigenvalue analysis requires at least one synchronous Generator, renewable dynamic plant or
STATCOM. External Grid alone is not sufficient." A network fed only by an External Grid, such
as the "Industrial plant 6 kV with motors" template, could only be studied in steady state.

Now each External Grid is a source behind its short-circuit impedance, as in Transient
Stability: |Z| = S_base / S"k, split by R/X (S"k min and R/X min by default, the study's
grid_sc_case). (Transient Stability used the reactance alone, capped at 1 pu: a grid weaker than
the 100 MVA system base came out as strong as 100 MVA, and R/X was ignored.) Steady-state mode
puts the grid behind the same impedance from the start on.

1. A 3000 MVA, 110 kV grid feeds a 2.5 MW motor through a 6.3 MVA transformer. The motor runs
   up and passes. Right after the start the dips at the 6 kV and the 110 kV bus are within a few
   percent of steady-state mode on the same diagram, and the 110 kV bus dips by the grid's share
   of the source impedance.
2. A weak 60 MVA, 20 kV grid at R/X 0 and 1: the grid source in ANDES is exactly that
   impedance, and the dips at the grid bus and at the motor bus match steady-state mode, which
   gives the same dips as the grid drawn as a line of that impedance from an ideal source.
3. The template itself, as the frontend sends it, with all in-service motors started DOL: all
   six motors run up.

Run with ``python samples/test_motor_starting_dynamic_ext_grid.py``.
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
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import app  # noqa: E402
import motor_starting_electrisim as ms  # noqa: E402

CLIENT = app.app.test_client()
T_START = 0.1
T_END = 5.0
S_BASE = 100.0

# The template's 2.5 MW compressor: a fan-type load (c3 = 1) at 85 % loading.
MOTOR = {"typ": "Motor0", "name": "mxCell_m1", "id": "m1", "userFriendlyName": "Compressor", "bus": "mxCell_mv",
         "pn_mech_mw": "2.5", "cos_phi": "0.89", "cos_phi_n": "0.89", "efficiency_percent": "96.5",
         "efficiency_n_percent": "96.5", "loading_percent": "85", "scaling": "1", "lrc_pu": "6", "rx": "0.1",
         "vn_kv": "6", "Hm": "0.5", "tm_c1": "0", "tm_c2": "0", "tm_c3": "1", "in_service": "true"}


def study(mode):
    return {"typ": "MotorStartingPandaPower Parameters", "mode": mode, "motor_ids": "all",
            "starting_method": "dol", "voltage_limit_percent": "15", "thermal_limit_percent": "100",
            "t_start": str(T_START), "t_end": str(T_END), "frequency": "50", "sn_mva": str(S_BASE),
            "user_email": "test@example.com"}


def bus(key, vn):
    return {"typ": "Bus0", "name": f"mxCell_{key}", "id": key, "vn_kv": str(vn), "userFriendlyName": key}


def grid(bus_key, s_sc, rx):
    return {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "userFriendlyName": "Utility",
            "bus": f"mxCell_{bus_key}", "vm_pu": "1", "va_degree": "0", "s_sc_max_mva": str(s_sc),
            "s_sc_min_mva": str(s_sc), "rx_max": str(rx), "rx_min": str(rx), "r0x0_max": "0.1", "x0x_max": "1",
            "in_service": "true"}


def transformer(hv_key, vn_hv):
    # Rated at its bus voltages and without a magnetising branch, so both modes model it alike.
    return {"typ": "Transformer0", "name": "mxCell_tr", "id": "tr", "userFriendlyName": "TR",
            "hv_bus": f"mxCell_{hv_key}", "lv_bus": "mxCell_mv", "sn_mva": "6.3", "vn_hv_kv": str(vn_hv),
            "vn_lv_kv": "6", "vkr_percent": "0.5", "vk_percent": "8", "pfe_kw": "0", "i0_percent": "0",
            "vector_group": "Dyn", "shift_degree": "150", "tap_side": "hv", "tap_pos": "0", "tap_neutral": "0",
            "tap_max": "2", "tap_min": "-2", "tap_step_percent": "2.5", "parallel": "1", "in_service": "true"}


Z_TRAFO = 0.08 * S_BASE / 6.3  # pu on the system base


def diagram(elements, mode):
    data = {"0": study(mode)}
    data.update({str(k): dict(v) for k, v in enumerate(elements, start=1)})
    return data


def solve(data):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = CLIENT.post("/", json=data)
    assert response.status_code == 200, response.data[:400]
    out = json.loads(response.data)
    assert not out.get("error"), (out.get("message"), out.get("exception"))
    return out


def steady_dips(out):
    return {b["id"]: b["dip_percent"] for b in out["buses"]}


def first_dips(out):
    """Dip at each bus in the first sample after the motor is switched on (rotor at standstill)."""
    t = out["timeseries"]["t"]
    k = next(i for i, tk in enumerate(t) if tk > T_START + 1e-9)
    return {key.replace("mxCell_", ""): (ser["v"][0] - ser["v"][k]) / ser["v"][0] * 100.0
            for key, ser in out["timeseries"]["buses"].items()}


def source_impedance(elements):
    """(r, x) of the External Grid's source in the ANDES system Motor Starting builds, system base."""
    data = diagram(elements, "dynamic")
    motors = ms._motor_el_from_in_data(data, None)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        ss, _, _ = ms._build_system_with_motors(data, dict(data["0"]), motors, "dol", T_START, [])
    assert ss.GENCLS.n == 1 and ss.Motor3.n == 1, (ss.GENCLS.n, ss.Motor3.n)
    return float(ss.GENCLS.ra.v[0]), float(ss.GENCLS.xd1.v[0])


def test_grid_only_network():
    elements = [grid("hv", 3000, 0.1), bus("hv", 110), bus("mv", 6), transformer("hv", 110), MOTOR]
    steady = steady_dips(solve(diagram(elements, "steady")))
    out = solve(diagram(elements, "dynamic"))
    m = out["motors"][0]
    dyn = first_dips(out)
    share = (S_BASE / 3000.0) / (S_BASE / 3000.0 + Z_TRAFO)
    print(f"3000 MVA grid: run-up {m['start_time_s']:.2f} s, I start {m['i_start_pu']:.2f} pu; dip at 6 kV "
          f"{dyn['mv']:.2f} % (steady state {steady['mv']:.2f} %), at 110 kV {dyn['hv']:.3f} % "
          f"(grid share {share * dyn['mv']:.3f} %, steady state {steady['hv']:.3f} %)")
    assert m["pass"] is True and m["stalled"] is False, m
    assert 0.0 < m["start_time_s"] < T_END - T_START, m
    # The same locked rotor on the same network and the same grid source as steady-state mode.
    for key in ("mv", "hv"):
        assert abs(dyn[key] / steady[key] - 1.0) < 0.03, (key, dyn[key], steady[key])
    # Not an ideal source: the grid bus drops with the current through the grid's own impedance.
    assert abs(dyn["hv"] / (share * dyn["mv"]) - 1.0) < 0.1, (dyn["hv"], share * dyn["mv"])


def test_weak_grid_source_impedance():
    s_sc = 60.0  # weaker than the 100 MVA system base
    for rx in (0.0, 1.0):
        elements = [grid("pcc", s_sc, rx), bus("pcc", 20), bus("mv", 6), transformer("pcc", 20), MOTOR]
        r, x = source_impedance(elements)
        z = S_BASE / s_sc
        assert abs(x - z / math.sqrt(1.0 + rx * rx)) < 1e-9 and abs(r - rx * x) < 1e-9, (rx, r, x)

        dyn = first_dips(solve(diagram(elements, "dynamic")))
        steady = steady_dips(solve(diagram(elements, "steady")))
        # The same grid drawn as an ideal source behind a line of that impedance.
        x_ohm = 20.0 ** 2 / s_sc / math.sqrt(1.0 + rx * rx)
        line = {"typ": "Line0", "name": "mxCell_zg", "id": "zg", "userFriendlyName": "Grid impedance",
                "busFrom": "mxCell_src", "busTo": "mxCell_pcc", "r_ohm_per_km": str(rx * x_ohm),
                "x_ohm_per_km": str(x_ohm), "c_nf_per_km": "0", "g_us_per_km": "0", "length_km": "1",
                "max_i_ka": "10", "type": "cs", "parallel": "1", "df": "1", "in_service": "true"}
        drawn = steady_dips(solve(diagram([grid("src", 1e6, 0.0), bus("src", 20)] + elements[1:] + [line],
                                          "steady")))
        print(f"60 MVA grid, R/X {rx:g}: source {r:.4f} + j{x:.4f} pu; dip at 20 kV {dyn['pcc']:.2f} % "
              f"(steady state {steady['pcc']:.2f} %, behind a line {drawn['pcc']:.2f} %), at 6 kV {dyn['mv']:.2f} % "
              f"({steady['mv']:.2f} %, {drawn['mv']:.2f} %)")
        for key in ("pcc", "mv"):
            # Steady state puts the grid behind exactly that impedance (to the 1e6 MVA source's 1e-4 pu).
            assert abs(steady[key] / drawn[key] - 1.0) < 2e-3, (rx, key, steady[key], drawn[key])
            assert abs(dyn[key] / steady[key] - 1.0) < 0.03, (rx, key, dyn[key], steady[key])


def test_template():
    with open(os.path.join(ROOT, "samples", "fixtures", "industrial_plant_6kV_motors.json"), encoding="utf-8") as fh:
        data = {"0": study("dynamic")}
        data.update(json.load(fh))
    out = solve(data)
    motors = out["motors"]
    hv = next(b for b in out["buses"] if b["name"] == "Utility_110kV")
    print(f"template, all six motors DOL: run-up {min(m['start_time_s'] for m in motors):.2f}-"
          f"{max(m['start_time_s'] for m in motors):.2f} s, I start {min(m['i_start_pu'] for m in motors):.2f}-"
          f"{max(m['i_start_pu'] for m in motors):.2f} pu, worst dip {out['summary']['worst_dip_percent']:.1f} %, "
          f"110 kV dip {hv['dip_percent']:.2f} %")
    assert len(motors) == 6, [m["name"] for m in motors]
    for m in motors:
        assert m["pass"] is True and m["stalled"] is False, m
    assert hv["dip_percent"] > 0.5, hv


def main() -> None:
    if not ms._HAS_ANDES:
        print("SKIP: ANDES is not installed.")
        return
    test_grid_only_network()
    test_weak_grid_source_impedance()
    test_template()
    print("dynamic motor starting with an External Grid only OK")


if __name__ == "__main__":
    main()
