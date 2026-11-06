"""Load Flow "Enforce Q Limits" and Generator reactive limits.

The dialog's "Enforce Q Limits" tick and the Generator's Min/Max Reactive Power used to be
dropped: the tick was never sent and the limits were never read, so generators could
exceed their Q limits even with the box ticked. The dialog default 0/0 means "not set".

Run with ``python samples/test_loadflow_q_limits.py``.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import app  # noqa: E402
import pandapower_electrisim as pe  # noqa: E402
from test_andes_stability import _sample_network  # noqa: E402

GEN_FIELDS = {
    "xdss_pu": "0.2", "rdss_ohm": "0", "cos_phi": "0.9", "pg_percent": "0", "power_station_trafo": "",
    "in_service": "true", "max_p_mw": "200", "min_p_mw": "0", "controllable": "false",
}


def run(enforce, gen2_q=("-5", "5"), **extra):
    params = {
        "typ": "PowerFlowPandaPower Parameters", "frequency": "50", "algorithm": "nr",
        "calculate_voltage_angles": "auto", "initialization": "auto", "exportPython": False,
        "enforce_q_lims": enforce, "user_email": "test@example.com", **extra,
    }
    net = _sample_network(params)
    for key, q in (("5", ("0", "0")), ("6", gen2_q)):
        net[key].update(GEN_FIELDS)
        net[key]["min_q_mvar"], net[key]["max_q_mvar"] = q
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=net)
    assert response.status_code == 200, response.data[:300]
    data = json.loads(response.data)
    q = {g["name"]: float(g["q_mvar"]) for g in data["generators"]}
    vm = {b["name"]: float(b["vm_pu"]) for b in data["busbars"]}
    return q["mxCell_gen2"], vm["mxCell_bus2"]


def main() -> None:
    assert pe._gen_q_limits_from_dialog({"min_q_mvar": "0", "max_q_mvar": "0"}) is None
    assert pe._gen_q_limits_from_dialog({"min_q_mvar": "", "max_q_mvar": "5"}) is None
    assert pe._gen_q_limits_from_dialog({"min_q_mvar": "5", "max_q_mvar": "-5"}) is None
    assert pe._gen_q_limits_from_dialog({"min_q_mvar": "-5", "max_q_mvar": "5"}) == (-5.0, 5.0)

    q_free, v_free = run(False)
    assert q_free > 10, q_free  # unticked: the generator holds 1.0 pu with ~20 Mvar
    assert abs(v_free - 1.0) < 1e-4, v_free

    q_lim, v_lim = run(True)
    assert abs(q_lim - 5.0) < 1e-3, q_lim  # ticked: capped at its 5 Mvar limit
    assert v_lim < 0.995, v_lim  # and the bus voltage drops once it stops regulating

    q_default, _ = run(True, gen2_q=("0", "0"))
    assert abs(q_default - q_free) < 1e-3, (q_default, q_free)  # 0/0 = no limit, not Q = 0
    print(f"Q limits OK: free {q_free:.2f} Mvar, enforced {q_lim:.2f} Mvar at {v_lim:.4f} pu")

    # Max Iterations / Tolerance reach the solver; unset values leave pandapower's defaults.
    seen = []
    real_runpp = pe.electrisim_runpp

    def spy(net, *args, **kwargs):
        seen.append({k: kwargs.get(k) for k in ("max_iteration", "tolerance_mva")})
        return real_runpp(net, *args, **kwargs)

    pe.electrisim_runpp = spy
    try:
        run(False, max_iteration="40", tolerance_mva="1e-7")
        assert seen and seen[0] == {"max_iteration": 40, "tolerance_mva": 1e-7}, seen
        seen.clear()
        run(False)
        assert seen and seen[0] == {"max_iteration": None, "tolerance_mva": None}, seen
        seen.clear()
        run(False, max_iteration="3")  # never below pandapower's Newton default of 10
        assert seen[0]["max_iteration"] == 10, seen
    finally:
        pe.electrisim_runpp = real_runpp
    print("Max iterations / tolerance OK")

    # The exported script must keep the slack generator and the Q limits, or it cannot
    # reproduce the run (no reference bus, or unlimited Q).
    import pandapower as pp
    import script_guard
    net = pp.create_empty_network()
    b1, b2 = pp.create_bus(net, 230), pp.create_bus(net, 230)
    pp.create_line_from_parameters(net, b1, b2, 100, 0.05, 0.5, 8, 1)
    pp.create_load(net, b2, p_mw=100, q_mvar=20)
    pp.create_gen(net, b1, p_mw=100, vm_pu=1.0, slack=True, name="G1")
    pp.create_gen(net, b2, p_mw=50, vm_pu=1.0, min_q_mvar=-5, max_q_mvar=5, name="G2")
    pp.runpp(net, enforce_q_lims=True)
    code = pe.generate_pandapower_python_code(net, {}, {}, "nr", "auto", "auto")
    back = script_guard.run_script(code)["net"]
    assert bool(back.gen.slack.iloc[0]) and float(back.gen.max_q_mvar.iloc[1]) == 5.0
    pp.runpp(back, enforce_q_lims=True)
    assert abs(float(back.res_gen.q_mvar.iloc[1]) - float(net.res_gen.q_mvar.iloc[1])) < 1e-6
    print("Exported generator slack and Q limits OK")


if __name__ == "__main__":
    main()
