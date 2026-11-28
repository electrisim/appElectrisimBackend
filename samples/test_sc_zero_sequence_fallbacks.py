"""Single-phase faults run when zero-sequence data was never entered, and say what they used.

* Lines drawn without R0 / X0 carry 0, a zero-impedance branch in the zero sequence: every
  single-phase fault stopped with "divide by zero encountered in divide" (10-bus Italian grid
  template). The positive-sequence R and X are used instead, with a warning naming the lines.
* Three-winding transformers with vk0 = 0 (the dialog default) stopped every single-phase fault
  with "Equivalent transformer with zero impedance!". The positive-sequence vk / vkr are used.
* A three-winding transformer with a two-winding vector group (the multivoltage template has
  "Dyn") stopped with "Dyn not supported yet for trafo3w!" and no name; ANSI answered HTTP 500.
  Both studies now say which transformer and which groups work.
* ANSI line-to-ground uses pandapower's zero-sequence network, so it also had to cope with an
  Impedance without zero-sequence columns (KeyError 'rft0_pu') and an Extended Ward (divide by
  zero). The Impedance gets Z0 = Z1, the Extended Ward stays out of the zero sequence.

Run with ``python samples/test_sc_zero_sequence_fallbacks.py``.
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

import app  # noqa: E402,F401  (installs Electrisim's pandapower fixes)
import numpy as np  # noqa: E402
import pandapower as pp  # noqa: E402
import pandapower.shortcircuit as sc  # noqa: E402

import ansi_shortcircuit_electrisim as ansi_sc  # noqa: E402
from pandapower_electrisim import (  # noqa: E402
    ensure_line_zero_sequence_data,
    ensure_trafo3w_zero_sequence_data,
    trafo3w_vector_group_problem,
)

TOL = 1e-3


def close(a, b, rel=TOL):
    return abs(a - b) <= rel * max(abs(a), abs(b), 1e-9)


def calc_1ph(net):
    with contextlib.redirect_stdout(io.StringIO()), np.errstate(divide="raise", invalid="raise"):
        sc.calc_sc(net, fault="1ph", case="max", branch_results=False, tk_s=1, kappa_method="C")
    return net.res_bus_sc


def ansi(net, fault="1ph"):
    params = {"fault_type": fault, "frequency_hz": 50, "prefault_v_pu": 1.0, "contact_parting_cycles": 3}
    with np.errstate(divide="raise", invalid="raise"):
        return json.loads(ansi_sc.shortcircuit_ansi(net, params))


def radial_line_net(r0, x0):
    net = pp.create_empty_network()
    a, b, c = (pp.create_bus(net, 20.0, name=n) for n in ("A", "B", "C"))
    pp.create_ext_grid(net, a, s_sc_max_mva=500, s_sc_min_mva=400, rx_max=0.1, rx_min=0.1,
                       x0x_max=1.0, r0x0_max=0.1, x0x_min=1.0, r0x0_min=0.1)
    pp.create_line_from_parameters(net, a, b, 5, 0.12, 0.35, 0, 0.4, name="L-NO-Z0",
                                   r0_ohm_per_km=r0, x0_ohm_per_km=x0, c0_nf_per_km=0)
    pp.create_line_from_parameters(net, b, c, 3, 0.12, 0.35, 0, 0.4, name="L-WITH-X0",
                                   r0_ohm_per_km=0.0, x0_ohm_per_km=1.05, c0_nf_per_km=0)
    return net


def line_without_zero_sequence() -> None:
    net = radial_line_net(0.0, 0.0)
    notes = ensure_line_zero_sequence_data(net, "1ph")
    assert len(notes) == 1 and "'L-NO-Z0'" in notes[0] and "L-WITH-X0" not in notes[0], notes
    assert net.line.at[0, "r0_ohm_per_km"] == 0.12 and net.line.at[0, "x0_ohm_per_km"] == 0.35, net.line
    assert net.line.at[1, "r0_ohm_per_km"] == 0.0 and net.line.at[1, "x0_ohm_per_km"] == 1.05, net.line
    assert ensure_line_zero_sequence_data(radial_line_net(0.0, 0.0), "3ph") == []
    got = calc_1ph(net)
    ref = calc_1ph(radial_line_net(0.12, 0.35))
    for b in got.index:
        assert close(got.at[b, "ikss_ka"], ref.at[b, "ikss_ka"]), (got, ref)
    res = ansi(radial_line_net(0.0, 0.0))
    assert not res.get("error"), res
    assert any("'L-NO-Z0'" in w for w in res.get("warnings", [])), res.get("warnings")
    print(f"line without R0/X0: 1ph Ik1 at C {got.at[2, 'ikss_ka']:.4f} kA (R0 = R, X0 = X), "
          f"ANSI ran with the note")


def three_winding_net(vk0, vector_group="YNynd"):
    net = pp.create_empty_network()
    hv, mv, lv = (pp.create_bus(net, kv, name=n) for kv, n in ((110, "HV"), (20, "MV"), (10, "LV")))
    pp.create_ext_grid(net, hv, s_sc_max_mva=3000, s_sc_min_mva=2500, rx_max=0.1, rx_min=0.1,
                       x0x_max=1.0, r0x0_max=0.1, x0x_min=1.0, r0x0_min=0.1)
    pp.create_transformer3w_from_parameters(
        net, hv, mv, lv, 110, 20, 10, 40, 40, 40, vk_hv_percent=12, vk_mv_percent=8, vk_lv_percent=6,
        vkr_hv_percent=0.4, vkr_mv_percent=0.3, vkr_lv_percent=0.3, pfe_kw=0, i0_percent=0,
        shift_mv_degree=0, shift_lv_degree=150, name="T3W",
        vk0_hv_percent=vk0[0], vk0_mv_percent=vk0[1], vk0_lv_percent=vk0[2],
        vkr0_hv_percent=0.4 if vk0[0] else 0.0, vkr0_mv_percent=0.3 if vk0[1] else 0.0,
        vkr0_lv_percent=0.3 if vk0[2] else 0.0, vector_group=vector_group)
    return net


def three_winding_without_vk0() -> None:
    net = three_winding_net((0, 0, 0))
    notes = ensure_trafo3w_zero_sequence_data(net, "1ph")
    assert len(notes) == 1 and "'T3W'" in notes[0] and "HV/MV/LV" in notes[0], notes
    got = calc_1ph(net)
    ref = calc_1ph(three_winding_net((12, 8, 6)))
    for b in got.index:
        assert close(got.at[b, "ikss_ka"], ref.at[b, "ikss_ka"]), (got, ref)
    res = ansi(three_winding_net((0, 0, 0)))
    assert not res.get("error"), res
    assert any("'T3W'" in w for w in res.get("warnings", [])), res.get("warnings")
    print(f"three-winding without vk0: 1ph Ik1 at MV {got.at[1, 'ikss_ka']:.4f} kA (vk0 = vk), ANSI ran")


def three_winding_vector_group() -> None:
    assert trafo3w_vector_group_problem(three_winding_net((12, 8, 6)), "1ph") is None
    for group in ("YNyn0yn0", "Dyn"):
        net = three_winding_net((12, 8, 6), vector_group=group)
        assert trafo3w_vector_group_problem(net, "3ph") is None
        message = trafo3w_vector_group_problem(net, "1ph")
        assert message and "'T3W'" in message and f"({group})" in message, message
        res = ansi(net)
        assert res.get("error") and res.get("message") == message, res
    print("three-winding vector group: named in the message for IEC and ANSI")


def ansi_impedance_and_extended_ward() -> None:
    """With Z0 = Z1 everywhere a line-to-ground fault equals the three-phase fault."""
    net = pp.create_empty_network()
    a, b = pp.create_bus(net, 20.0, name="A"), pp.create_bus(net, 20.0, name="B")
    pp.create_ext_grid(net, a, s_sc_max_mva=500, rx_max=0.1, x0x_max=1.0, r0x0_max=0.1)
    pp.create_impedance(net, a, b, rft_pu=0.01, xft_pu=0.1, sn_mva=100, name="Z-SERIES")
    pp.create_xward(net, a, ps_mw=1.0, qs_mvar=0.2, pz_mw=0.5, qz_mvar=0.1, r_ohm=1.0, x_ohm=10.0,
                    vm_pu=1.0, name="XW")
    assert "rft0_pu" not in net.impedance.columns or net.impedance["rft0_pu"].isna().all()
    res1 = ansi(net, "1ph")
    res3 = ansi(net, "3ph")
    assert not res1.get("error") and not res3.get("error"), (res1, res3)
    i1 = {r["name"]: r["i_first_sym_ka"] for r in res1["busbars"]}
    i3 = {r["name"]: r["i_first_sym_ka"] for r in res3["busbars"]}
    for name in ("A", "B"):
        assert close(i1[name], i3[name]), (name, i1, i3)
    assert any("'Z-SERIES'" in w and "Z0 = Z1" in w for w in res1.get("warnings", [])), res1.get("warnings")
    print(f"ANSI with an Impedance and an Extended Ward: B I_SLG {i1['B']:.4f} kA = I_3ph {i3['B']:.4f} kA")


if __name__ == "__main__":
    line_without_zero_sequence()
    three_winding_without_vk0()
    three_winding_vector_group()
    ansi_impedance_and_extended_ward()
    print("zero-sequence fallbacks OK")
