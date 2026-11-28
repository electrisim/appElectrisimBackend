"""Dynamic (ANDES Motor3) motor starting: the motor runs up from standstill, and a stall fails.

Every motor used to report start time 0.0 s, I start 1.0 pu and "pass": the results were read
from the sample at the connect time, recorded before the Toggle switches the motor on. Behind
that the motor never really started:

- the load torque c1..c3 went to ANDES as given, on the 100 MVA system base, so c3 = 1 asked a
  1.2 MVA motor for 100 MVA of torque;
- ANDES 1.10 builds Tm(slip) with c2 where c3 belongs, so a fan load turned into 1 - 2 slip;
- the slip state starts at 0 when the motor is off, so the "start" began at synchronous speed;
- the currents were on the system base, not on the motor rating.

The motor fell from synchronous speed to slip 0.49 within milliseconds and stayed there.

Now: the motor is connected at standstill (slip 1), the load torque is (loading) x rated torque
x (c1 + c2 w + c3 w^2), I start is on the motor rating, and the start is complete when the motor
is within the slip threshold of its running speed. The run-up time agrees with the torque-speed
integral 2 H * integral ds / (Te - Tm) of the motor's own equivalent circuit, the motor ends at
its running slip, a motor whose load torque it cannot overcome is reported as stalled, and one
still accelerating at the end time is reported as not started.

Run with ``python samples/test_motor_starting_dynamic_run_up.py``.
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
import motor_starting_electrisim as ms  # noqa: E402

CLIENT = app.app.test_client()

MOTOR = {"typ": "Motor0", "name": "mxCell_motor1", "id": "m1", "userFriendlyName": "Pump motor",
         "bus": "mxCell_bus2", "pn_mech_mw": "1.0", "cos_phi": "0.88", "cos_phi_n": "0.88",
         "efficiency_n_percent": "95", "efficiency_percent": "95", "loading_percent": "100",
         "lrc_pu": "6", "rx": "0.3", "vn_kv": "20", "Hm": "0.5", "tm_c1": "0", "tm_c2": "0", "tm_c3": "1",
         "in_service": "true"}


def run(t_end="3", **motor):
    data = {
        "0": {"typ": "MotorStartingPandaPower Parameters", "mode": "dynamic", "motor_ids": "all",
              "starting_method": "dol", "voltage_limit_percent": "15", "thermal_limit_percent": "100",
              "t_start": "0.1", "t_end": t_end, "frequency": "50", "sn_mva": "100",
              "user_email": "test@example.com"},
        "1": {"typ": "Bus0", "name": "mxCell_bus1", "id": "b1", "vn_kv": "20", "userFriendlyName": "Grid bus"},
        "2": {"typ": "Bus1", "name": "mxCell_bus2", "id": "b2", "vn_kv": "20", "userFriendlyName": "Motor bus"},
        "3": {"typ": "Generator", "name": "mxCell_gen1", "id": "g1", "bus": "mxCell_bus1", "p_mw": "2",
              "vm_pu": "1.0", "sn_mva": "200", "scaling": "1", "vn_kv": "20", "slack": "true",
              "userFriendlyName": "Gen1"},
        "4": {"typ": "Line0", "name": "mxCell_line1", "id": "l1", "userFriendlyName": "Feeder",
              "busFrom": "mxCell_bus1", "busTo": "mxCell_bus2", "r_ohm_per_km": "0.1", "x_ohm_per_km": "0.35",
              "c_nf_per_km": "10", "g_us_per_km": "0", "length_km": "2", "max_i_ka": "0.5", "in_service": "true"},
        "5": dict(MOTOR, **motor),
    }
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = CLIENT.post("/", json=data)
    assert response.status_code == 200, response.data[:400]
    out = json.loads(response.data)
    assert not out.get("error"), out
    # The study's own settings entry is typed "MotorStarting..."; it is not a motor.
    assert not any("not found" in w for w in out["warnings"]), out["warnings"]
    return out, data["5"]


def torque_curve(el, v):
    """Steady-state electrical and load torque (motor base) of the Motor3 the study builds."""
    p = ms._derive_motor3_params(el, [])
    rs, xs, rr, xr, xm = p["rs"], p["xs"], p["rr1"], p["xr1"], p["xm"]
    sn = float(el["pn_mech_mw"]) / (float(el["efficiency_n_percent"]) / 100.0) / float(el["cos_phi_n"])
    t_load = float(el["loading_percent"]) / 100.0 * float(el["pn_mech_mw"]) / sn
    c1, c2, c3 = (float(el[k]) for k in ("tm_c1", "tm_c2", "tm_c3"))

    def te(s):
        z_rotor = complex(rr / s, xr)
        z_branch = complex(0.0, xm) * z_rotor / (complex(0.0, xm) + z_rotor)
        i_s = v / (complex(rs, xs) + z_branch)
        i_r = i_s * complex(0.0, xm) / (complex(0.0, xm) + z_rotor)
        return abs(i_r) ** 2 * rr / s

    def tm(s):
        w = 1.0 - s
        return t_load * (c1 + c2 * w + c3 * w * w)

    return te, tm, float(el["Hm"])


def running_slip(te, tm):
    lo, hi = 1e-6, 0.2
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if te(mid) > tm(mid):
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def run_up_time(te, tm, hm, s_done, n=4000):
    """t = 2 H * integral from s_done to 1 of ds / (Te - Tm)."""
    total, ds = 0.0, (1.0 - s_done) / n
    for k in range(n):
        s = s_done + (k + 0.5) * ds
        total += ds / (te(s) - tm(s))
    return 2.0 * hm * total


def test_run_up():
    out, el = run()
    ts = out["timeseries"]
    t = ts["t"]
    m = out["motors"][0]
    series = ts["motors"]["m1"]
    v_bus = ts["buses"]["mxCell_bus2"]["v"]
    after = [k for k, tk in enumerate(t) if tk > 0.1 + 1e-9]
    first = after[0]

    # Off until the connect time, then switched on at standstill.
    assert all(abs(i) < 1e-9 for i, tk in zip(series["i_pu"], t) if tk < 0.1), "current before the start"
    assert abs(series["slip"][first] - 1.0) < 0.02, series["slip"][first]

    # Starting current on the motor rating: the locked-rotor current at the voltage the motor sees.
    assert 0.85 * 6.0 * v_bus[first] < m["i_start_pu"] < 1.15 * 6.0 * v_bus[first], (m, v_bus[first])
    assert abs(m["i_start_ka"] - m["i_start_pu"] * m["i_rated_ka"]) < 1e-9, m

    # Run-up time: the torque-speed integral at the mean voltage of the run-up.
    v_run = sum(v_bus[k] for k in after if t[k] <= 0.1 + m["start_time_s"]) / max(
        1, sum(1 for k in after if t[k] <= 0.1 + m["start_time_s"]))
    te, tm, hm = torque_curve(el, v_run)
    s_run = running_slip(te, tm)
    s_done = s_run + 0.02 * (1.0 - s_run)
    t_expected = run_up_time(te, tm, hm, s_done)

    # After the start the motor carries its load at its running slip (the network frequency
    # settles about 0.01 Hz low, which the slip against 50 Hz includes: 0.5 %).
    te_end, tm_end, _ = torque_curve(el, v_bus[-1])
    s_end = running_slip(te_end, tm_end)
    print(f"run-up: {m['start_time_s']:.3f} s (torque-speed integral {t_expected:.3f} s), "
          f"I start {m['i_start_pu']:.2f} pu, final slip {series['slip'][-1]:.4f} (running slip {s_end:.4f})")
    assert m["pass"] is True and m.get("stalled") is False, m
    assert 0.85 * t_expected < m["start_time_s"] < 1.15 * t_expected, (m["start_time_s"], t_expected)
    assert abs(series["slip"][-1] / s_end - 1.0) < 0.02, (series["slip"][-1], s_end)
    assert abs(m["running_slip"] / s_end - 1.0) < 1e-6, (m["running_slip"], s_end)


def test_stall():
    # A fan load ten times the motor's rating: it crawls at high slip and never runs up.
    out, _ = run(tm_c3="10")
    m = out["motors"][0]
    slip = out["timeseries"]["motors"]["m1"]["slip"]
    print(f"stall: pass={m['pass']} stalled={m['stalled']} final slip {slip[-1]:.3f} - {m['note']}")
    assert m["pass"] is False and m["stalled"] is True, m
    assert m["start_time_s"] is None, m
    assert slip[-1] > 0.3, slip[-1]


def test_not_finished():
    # Ten times the inertia: still accelerating when the simulation ends. Not started, not stalled.
    out, _ = run(t_end="1", Hm="5")
    m = out["motors"][0]
    print(f"slow start: pass={m['pass']} stalled={m['stalled']} - {m['note']}")
    assert m["pass"] is False and m["stalled"] is False, m
    assert m["start_time_s"] is None, m


def main() -> None:
    if not ms._HAS_ANDES:
        print("SKIP: ANDES is not installed.")
        return
    test_run_up()
    test_stall()
    test_not_finished()
    print("dynamic motor run-up OK")


if __name__ == "__main__":
    main()
