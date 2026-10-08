#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Converter short-circuit k from PowerFactory Ik\" currents.

Run from appElectrisimBackend:
  python samples/test_converter_sc.py
"""
from __future__ import annotations

import math
import os
import sys

import pandapower as pp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from converter_sc_electrisim import (
    apply_converter_short_circuit_k,
    apply_negative_sequence_ikss,
    k_from_ik,
    sgen_k_export_lines,
)


def _expect(name, got, want, tol=1e-3):
    if abs(got - want) > tol:
        raise SystemExit(f"{name}: got {got}, want {want}")
    print(f"ok  {name} = {got}")


def test_k_formula():
    # 4.5 MVA at 30 kV has rated current 0.0866 kA.
    _expect("k 3ph", k_from_ik(0.0866, 4.5, 30.0), 1.0, tol=1e-3)
    _expect("k 2ph", k_from_ik(0.0433, 4.5, 30.0), 0.5, tol=1e-3)
    _expect("k 1ph", k_from_ik(0.0433, 4.5, 30.0), 0.5, tol=1e-3)
    # 5 MVA at 33 kV is the same current within about one percent.
    k5 = k_from_ik(0.0866, 5.0, 33.0)
    if not (0.98 < k5 < 1.0):
        raise SystemExit(f"k at 5 MVA / 33 kV: got {k5}")
    print(f"ok  k 5 MVA / 33 kV = {k5}")
    if k_from_ik(0, 4.5, 30) is not None:
        raise SystemExit("zero Ik must not define k")
    print("ok  zero Ik")


def _wind_net(x2=1.0, ik3=0.0866, ik2=0.0433, k_dialog=0.0, ref_kv=30.0):
    net = pp.create_empty_network(sn_mva=1.0)
    bus = pp.create_bus(net, vn_kv=30.0, name="collector")
    pp.create_ext_grid(
        net, bus, vm_pu=1.0, s_sc_max_mva=5.0, rx_max=0.1,
        s_sc_min_mva=5.0, rx_min=0.1, name="grid",
    )
    pp.create_sgen(
        net, bus, p_mw=4.0, q_mvar=0.0, sn_mva=4.5, name="wt",
        k=float("nan"), generator_type="current_source", current_source=True,
    )
    net.sgen["k_dialog"] = k_dialog
    net.sgen["ikss_3ph_ka"] = ik3
    net.sgen["ikss_2ph_ka"] = ik2
    net.sgen["ikss_1ph_ka"] = ik2
    net.sgen["sc_ref_vn_kv"] = ref_kv
    net.sgen["r2_pu"] = 0.0
    net.sgen["x2_pu"] = x2
    return net


def test_apply_k():
    net = _wind_net()
    apply_converter_short_circuit_k(net, "3ph")
    _expect("applied 3ph", float(net.sgen.at[0, "k"]), 1.0)
    apply_converter_short_circuit_k(net, "2ph")
    _expect("applied 2ph", float(net.sgen.at[0, "k"]), 0.5)
    apply_converter_short_circuit_k(net, "1ph")
    _expect("applied 1ph", float(net.sgen.at[0, "k"]), 0.5)

    # Empty reference voltage uses the connected bus (also 30 kV).
    net.sgen.at[0, "sc_ref_vn_kv"] = 0.0
    apply_converter_short_circuit_k(net, "3ph")
    _expect("bus voltage reference", float(net.sgen.at[0, "k"]), 1.0)

    # No Ik": dialog k, then 1.1.
    plain = _wind_net(ik3=0.0, ik2=0.0, k_dialog=1.25)
    apply_converter_short_circuit_k(plain, "3ph")
    _expect("dialog k", float(plain.sgen.at[0, "k"]), 1.25)
    plain.sgen.at[0, "k_dialog"] = 0.0
    apply_converter_short_circuit_k(plain, "3ph")
    _expect("fallback 1.1", float(plain.sgen.at[0, "k"]), 1.1)

    # Asynchronous machines keep their own k.
    async_net = _wind_net(ik3=0.0866, k_dialog=0.0)
    async_net.sgen.at[0, "generator_type"] = "async"
    async_net.sgen.at[0, "k"] = 2.0
    apply_converter_short_circuit_k(async_net, "3ph")
    _expect("async unchanged", float(async_net.sgen.at[0, "k"]), 2.0)


def test_negative_sequence_changes_2ph():
    without = _wind_net(x2=0.0)
    apply_converter_short_circuit_k(without, "2ph")
    pp.shortcircuit.calc_sc(without, fault="2ph", case="max", bus=0, ip=True, ith=True)
    ik_without = float(without.res_bus_sc.at[0, "ikss_ka"])

    with_x2 = _wind_net(x2=1.0)
    apply_converter_short_circuit_k(with_x2, "2ph")
    pp.shortcircuit.calc_sc(with_x2, fault="2ph", case="max", bus=0, ip=True, ith=True)
    before = float(with_x2.res_bus_sc.at[0, "ikss_ka"])
    ip_before = float(with_x2.res_bus_sc.at[0, "ip_ka"])
    apply_negative_sequence_ikss(with_x2, fault="2ph", case="max", bus=0)
    after = float(with_x2.res_bus_sc.at[0, "ikss_ka"])
    ip_after = float(with_x2.res_bus_sc.at[0, "ip_ka"])

    if not math.isfinite(after) or after <= 0:
        raise SystemExit(f"2ph ikss after r2/x2 is not a positive current: {after}")
    # x2 = 0 must not be corrected; x2 = 1 pu on this weak grid must move ikss.
    if abs(before - ik_without) > 1e-6:
        raise SystemExit(f"x2 must not change the pandapower run itself: {before} vs {ik_without}")
    if abs(after - before) < 1e-4:
        raise SystemExit(f"x2 = 1 pu did not change 2ph ikss ({before} -> {after})")
    if ip_before > 0 and abs(ip_after / ip_before - after / before) > 1e-6:
        raise SystemExit("ip was not scaled with ikss")
    print(f"ok  2ph ikss {before:.6f} -> {after:.6f} kA with x2 = 1 pu")

    # Three-phase results are left alone.
    three = _wind_net(x2=1.0)
    apply_converter_short_circuit_k(three, "3ph")
    pp.shortcircuit.calc_sc(three, fault="3ph", case="max", bus=0, ip=True, ith=True)
    ik3 = float(three.res_bus_sc.at[0, "ikss_ka"])
    apply_negative_sequence_ikss(three, fault="3ph", case="max", bus=0)
    if float(three.res_bus_sc.at[0, "ikss_ka"]) != ik3:
        raise SystemExit("3ph ikss must not be rewritten")
    print(f"ok  3ph ikss unchanged at {ik3:.6f} kA")


def test_export_lines():
    net = _wind_net()
    lines = sgen_k_export_lines(net, "3ph")
    text = "\n".join(lines)
    if 'net.sgen["k"] = 1.1' in text:
        raise SystemExit("export still forces every sgen to k = 1.1")
    published = None
    for line in lines:
        if line.startswith("net.sgen.at[0, 'k']"):
            published = float(line.split("=", 1)[1].strip())
    if published is None or abs(published - 1.0) > 1e-3:
        raise SystemExit(f"export did not publish k = 1:\n{text}")
    print("ok  export lines")
    print(text)


def main():
    test_k_formula()
    test_apply_k()
    test_negative_sequence_changes_2ph()
    test_export_lines()
    print("all converter short-circuit checks passed")


if __name__ == "__main__":
    main()
