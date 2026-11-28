"""Steady-state motor starting: the locked rotor is a constant impedance.

A starting motor used to be replaced by a constant-power load sized at rated voltage. A locked
rotor is an impedance, so whenever the voltage sagged the current (and the dip) came out too
high, and simultaneous starts that pull the voltage down far enough had no load-flow solution:
the "Industrial plant 6 kV with motors" template stopped with "Load flow failed for
locked-rotor (during) snapshot" for "All in-service motors" (6 motors, about 45 MVA
locked-rotor, on a 16 MVA, 10 % transformer).

1. One motor at the end of a line from a 1.0 pu source. The motor-bus voltage is the exact
   impedance divider Z_eq / (Z_eq + Z_line), and I start is the current at that voltage.
   The starter factor k keeps its meaning (current at rated voltage relative to DOL):
   DOL 1, star-delta 1/3, autotransformer tap^2 and reactor 1/(1 + x) scale the
   locked-rotor admittance; a soft starter holds its current limit whatever the voltage.
2. The template's six motors started together on its 16 MVA, 10 % transformer solve, and each
   motor's current follows the voltage it sees. The dip fails the 15 % limit, as it should.

Run with ``python samples/test_motor_starting_locked_rotor.py``.
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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app  # noqa: E402

CLIENT = app.app.test_client()


def study(**settings):
    params = {"typ": "MotorStartingPandaPower Parameters", "mode": "steady", "motor_ids": "all",
              "starting_method": "dol", "i_limit_pu": "3", "at_tap_pu": "0.8", "reactor_x_pu": "0.25",
              "voltage_limit_percent": "15", "thermal_limit_percent": "100", "frequency": "50",
              "sn_mva": "100", "user_email": "test@example.com"}
    params.update(settings)
    return params


def motor(key, bus, pn, cos_n, eff, lrc, rx, vn, loading="85"):
    return {"typ": "Motor0", "name": f"mxCell_{key}", "id": key, "userFriendlyName": key, "bus": bus,
            "pn_mech_mw": pn, "cos_phi": cos_n, "cos_phi_n": cos_n, "efficiency_percent": eff,
            "efficiency_n_percent": eff, "loading_percent": loading, "scaling": "1", "lrc_pu": lrc,
            "rx": rx, "vn_kv": vn, "in_service": "true"}


def solve(data):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = CLIENT.post("/", json=data)
    assert response.status_code == 200, response.data[:400]
    result = json.loads(response.data)
    assert not result.get("error"), result
    return result


# --- 1. one motor behind a line: the exact impedance divider ------------------------------

PN, COS_N, EFF, LRC, RX, VN = 2.5, 0.89, 96.5, 6.0, 0.1, 6.0
Z_LINE = complex(0.1, 0.4)  # ohm: 1 km of 0.1 + j0.4 ohm/km, no charging


def divider_network(method, **settings):
    data = {
        "0": study(starting_method=method, **settings),
        "1": {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_src", "vm_pu": "1",
              "va_degree": "0", "s_sc_max_mva": "500", "s_sc_min_mva": "400", "rx_max": "0.1", "rx_min": "0.1",
              "r0x0_max": "0.1", "x0x_max": "1", "in_service": "true"},
        "2": {"typ": "Bus0", "name": "mxCell_src", "id": "src", "vn_kv": "6", "userFriendlyName": "Source"},
        "3": {"typ": "Bus1", "name": "mxCell_m", "id": "m", "vn_kv": "6", "userFriendlyName": "Motor bus"},
        "4": {"typ": "Line0", "name": "mxCell_ln", "id": "ln", "userFriendlyName": "Feeder",
              "busFrom": "mxCell_src", "busTo": "mxCell_m", "r_ohm_per_km": "0.1", "x_ohm_per_km": "0.4",
              "c_nf_per_km": "0", "g_us_per_km": "0", "length_km": "1", "max_i_ka": "2", "type": "cs",
              "parallel": "1", "df": "1", "in_service": "true"},
        "5": motor("M1", "mxCell_m", str(PN), str(COS_N), str(EFF), str(LRC), str(RX), str(VN)),
    }
    return solve(data)


def expected(method):
    """(k, V at the motor bus in pu, I start in kA) from the motor's equivalent locked-rotor impedance."""
    sn = PN / (EFF / 100.0) / COS_N
    i_lr = LRC * sn / (math.sqrt(3.0) * VN)
    angle = math.atan2(1.0, RX)  # locked-rotor impedance angle from R/X
    z_lr = VN / (math.sqrt(3.0) * i_lr) * cmath.exp(1j * angle)
    v_src = VN / math.sqrt(3.0)  # kV per phase at 1.0 pu
    if method == "soft_start":
        k = 3.0 / LRC  # current limit 3 x In, held at any voltage
        i = k * i_lr
        drop = i * cmath.exp(-1j * angle) * Z_LINE  # I lags the motor-bus voltage by the locked-rotor angle
        v = math.sqrt(v_src ** 2 - drop.imag ** 2) - drop.real
        return k, v / v_src, i
    k = {"dol": 1.0, "star_delta": 1.0 / 3.0, "autotransformer": 0.8 ** 2, "reactor": 1.0 / 1.25}[method]
    z_eq = z_lr / k
    v = abs(z_eq / (z_eq + Z_LINE))
    return k, v, k * i_lr * v


def test_divider():
    for method in ("dol", "star_delta", "autotransformer", "reactor", "soft_start"):
        result = divider_network(method)
        k, v_expected, i_expected = expected(method)
        m = result["motors"][0]
        bus = {b["id"]: b for b in result["buses"]}["m"]
        print(f"{method:16s} k={m['k_method']:.4f}  V={bus['vm_during']:.5f} pu (expected {v_expected:.5f})  "
              f"I start={m['i_start_ka']:.4f} kA (expected {i_expected:.4f})")
        assert abs(m["k_method"] - k) < 1e-9, (method, m["k_method"], k)
        assert abs(bus["vm_before"] - 1.0) < 1e-6, bus
        assert abs(bus["vm_during"] - v_expected) < 2e-4, (method, bus["vm_during"], v_expected)
        assert abs(m["i_start_ka"] / i_expected - 1.0) < 1e-3, (method, m["i_start_ka"], i_expected)
        assert abs(m["v_start_pu"] - bus["vm_during"]) < 1e-9, m  # motor rated 6 kV on a 6 kV bus


# --- 2. the template's six motors started together ----------------------------------------

def template_network():
    trafo = {"parameters": "true", "vkr_percent": "0.875", "vk_percent": "6", "pfe_kw": "1.45",
             "i0_percent": "0.3", "vector_group": "Dyn", "shift_degree": "150", "tap_side": "hv", "tap_pos": "0",
             "tap_neutral": "0", "tap_max": "2", "tap_min": "-2", "tap_step_percent": "2.5", "parallel": "1",
             "sn_mva": "1.6", "vn_hv_kv": "6", "vn_lv_kv": "0.4", "in_service": "true"}
    return {
        "0": study(),
        "1": {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_hv", "vm_pu": "1",
              "va_degree": "0", "s_sc_max_mva": "3000", "s_sc_min_mva": "2000", "rx_max": "0.1", "rx_min": "0.1",
              "r0x0_max": "0.1", "x0x_max": "1", "in_service": "true"},
        "2": {"typ": "Bus0", "name": "mxCell_hv", "id": "hv", "vn_kv": "110", "userFriendlyName": "Utility_110kV"},
        "3": {"typ": "Bus1", "name": "mxCell_mv", "id": "mv", "vn_kv": "6", "userFriendlyName": "MV_SWGR_6kV"},
        "4": {"typ": "Bus2", "name": "mxCell_lva", "id": "lva", "vn_kv": "0.4", "userFriendlyName": "LV_MCC_A"},
        "5": {"typ": "Bus3", "name": "mxCell_lvb", "id": "lvb", "vn_kv": "0.4", "userFriendlyName": "LV_MCC_B"},
        "6": {"typ": "Transformer0", "name": "mxCell_tr1", "id": "tr1", "userFriendlyName": "TR-1",
              "hv_bus": "mxCell_hv", "lv_bus": "mxCell_mv", "sn_mva": "16", "vn_hv_kv": "110", "vn_lv_kv": "6.3",
              "vkr_percent": "0.5", "vk_percent": "10", "pfe_kw": "12", "i0_percent": "0.08", "vector_group": "YNd",
              "shift_degree": "150", "tap_side": "hv", "tap_pos": "0", "tap_neutral": "0", "tap_max": "9",
              "tap_min": "-9", "tap_step_percent": "1.5", "parallel": "1", "in_service": "true"},
        "7": dict(trafo, typ="Transformer1", name="mxCell_tra", id="tra", userFriendlyName="TR-LV1",
                  hv_bus="mxCell_mv", lv_bus="mxCell_lva"),
        "8": dict(trafo, typ="Transformer2", name="mxCell_trb", id="trb", userFriendlyName="TR-LV2",
                  hv_bus="mxCell_mv", lv_bus="mxCell_lvb"),
        "9": motor("Compressor M1", "mxCell_mv", "2.5", "0.89", "96.5", "6", "0.1", "6"),
        "10": motor("Pump M2", "mxCell_mv", "1.2", "0.87", "96", "5.8", "0.1", "6", loading="90"),
        "11": motor("Pump M3", "mxCell_mv", "1.2", "0.87", "96", "5.8", "0.1", "6", loading="90"),
        "12": motor("Fan M4", "mxCell_mv", "0.8", "0.86", "95.5", "5.5", "0.15", "6", loading="80"),
        "13": motor("LV group A", "mxCell_lva", "0.35", "0.85", "93", "6.5", "0.42", "0.4", loading="80"),
        "14": motor("LV group B", "mxCell_lvb", "0.25", "0.85", "93", "6.5", "0.42", "0.4", loading="80"),
        "15": {"typ": "Load0", "name": "mxCell_lda", "id": "lda", "bus": "mxCell_lva", "p_mw": "0.6",
               "q_mvar": "0.2906", "const_z_percent": "0", "const_i_percent": "0", "sn_mva": "0", "scaling": "1",
               "type": "wye", "in_service": "true"},
        "16": {"typ": "Load1", "name": "mxCell_ldb", "id": "ldb", "bus": "mxCell_lvb", "p_mw": "0.45",
               "q_mvar": "0.1917", "const_z_percent": "0", "const_i_percent": "0", "sn_mva": "0", "scaling": "1",
               "type": "wye", "in_service": "true"},
        "17": {"typ": "Capacitor0", "name": "mxCell_pfc", "id": "pfc", "bus": "mxCell_mv", "q_mvar": "1.5",
               "loss_factor": "0.0002", "vn_kv": "6", "step": "1", "max_step": "1", "in_service": "true"},
    }


def test_simultaneous_start():
    result = solve(template_network())
    motors = result["motors"]
    assert len(motors) == 6, [m["name"] for m in motors]
    s_lr = sum(m["lrc_pu"] * m["sn_mva"] for m in motors)
    assert 40.0 < s_lr < 50.0, s_lr  # about 45 MVA locked-rotor at rated voltage
    buses = {b["id"]: b for b in result["buses"]}
    dip = buses["mv"]["dip_percent"]
    print(f"six motors at once: {s_lr:.1f} MVA locked-rotor, 6 kV dip {dip:.1f} %, "
          f"{result['summary']['n_fail_voltage']} buses over the limit")
    assert 15.0 < dip < 35.0, buses["mv"]
    assert result["summary"]["n_fail_voltage"] >= 1, result["summary"]
    for m in motors:
        # Constant impedance: the current is the locked-rotor current scaled by the voltage the motor sees.
        i_lr = m["lrc_pu"] * m["i_rated_ka"]
        assert m["v_start_pu"] < 0.9, m
        assert abs(m["i_start_ka"] / (i_lr * m["v_start_pu"]) - 1.0) < 1e-3, m


def main() -> None:
    test_divider()
    test_simultaneous_start()
    print("motor starting locked-rotor impedance OK")


if __name__ == "__main__":
    main()
