"""The short-circuit model must not be changed by the checks that run before it.

- ``pp.diagnostic`` ran on the study network. On some diagrams (the case145 template) it left
  bus-bus switches behind, merging buses into the grid: every bus showed the grid's 18,542 kA,
  or the study failed with KeyError 'ikss_ka'. It now runs on a copy.
- Those diagnostic load flows were also what let ``calc_sc(check_connectivity=False)`` work with
  a Generator ('_is_elements_final'); the study now sets that up itself.
- Diagrams whose only switches are closed bus-bus switches (bus couplers) failed with
  KeyError 'ikss_ka' inside pandapower.

Run with ``python samples/test_sc_network_isolation.py``.
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

import pandapower as pp  # noqa: E402
import pandapower.shortcircuit as sc  # noqa: E402

import app  # noqa: E402
from samples.test_sc_dialog_defaults import ikss, payload  # noqa: E402


def solve(data):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=data)
    assert response.status_code == 200, response.data[:400]
    return json.loads(response.data)


def main() -> None:
    reference = solve(payload("3ph", "max"))
    assert not reference.get("error"), reference.get("message")

    # A diagnostic that changes the network it is given (merges bus B into the grid bus) and runs
    # no load flow. The study must not see either effect.
    real_diagnostic = pp.diagnostic

    def mutating_diagnostic(net, *args, **kwargs):
        pp.create_switch(net, bus=0, element=1, et="b", closed=True)
        return {}

    pp.diagnostic = mutating_diagnostic
    try:
        isolated = solve(payload("3ph", "max"))
    finally:
        pp.diagnostic = real_diagnostic
    assert not isolated.get("error"), isolated.get("message")
    for bus in ("a", "b"):
        assert abs(ikss(isolated, bus) - ikss(reference, bus)) < 1e-9, (bus, ikss(isolated, bus), ikss(reference, bus))
    print(f"diagnostic isolated: Ik'' at B = {ikss(isolated, 'b'):.3f} kA (unchanged)")

    # Bus coupler only: pandapower 3.2 never writes res_switch_sc.ikss_ka for it.
    net = pp.create_empty_network()
    a = pp.create_bus(net, 20)
    b = pp.create_bus(net, 20)
    c = pp.create_bus(net, 20)
    pp.create_ext_grid(net, a, s_sc_max_mva=500, rx_max=0.1)
    pp.create_switch(net, a, b, et="b", closed=True)
    pp.create_line_from_parameters(net, b, c, 2, 0.1, 0.3, 10, 0.4)
    sc.calc_sc(net, case="max", branch_results=True)
    assert net.res_bus_sc.ikss_ka.notna().all(), net.res_bus_sc
    print(f"bus coupler only: Ik'' at line end = {net.res_bus_sc.ikss_ka.at[c]:.3f} kA")


if __name__ == "__main__":
    main()
