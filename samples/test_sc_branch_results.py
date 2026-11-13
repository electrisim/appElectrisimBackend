"""Line and transformer short-circuit currents (IEC 60909) follow the physics of each fault.

A user saw two things in a 10 kV network with 0.4 / 0.69 kV transformers:

* Single-phase maximum: the 10 kV lines showed about 3 kA while every 10 kV bus showed about
  0.9 kA. pandapower spread the whole fault current over the positive-sequence network, so a
  0.69 kV earth fault behind a Dyn transformer appeared on the 10 kV side as Ik1 * ratio, sqrt(3)
  more than the real phase current Ik1 * ratio / sqrt(3).
* Three-phase minimum: the lines showed about 0.2 kA while the buses showed about 10 kA. The
  minimum was taken over every fault location in the network (a fault two transformers away), and
  ip / Ith came from a different fault than Ik".

Now a branch current of an unbalanced fault is its largest phase current (sequence currents and
transformer phase shift), the minimum case uses a fault at the branch's own end, and each value
names the bus whose fault gives it.

Run with ``python samples/test_sc_branch_results.py``.
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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app  # noqa: E402

RATIO = 0.4 / 10.0


def payload(fault, case, selected=None):
    settings = {"typ": "ShortCircuitPandaPower Parameters", "fault_type": fault, "fault_location": case,
                "fault_bus_mode": "selection" if selected else "all", "fault_bus_ids": [],
                "fault_bus_names": list(selected or []), "fault_impedance": "6", "topology": "auto",
                "tk_s": "1", "r_fault_ohm": "0", "x_fault_ohm": "0", "inverse_y": "True",
                "exportPython": False, "user_email": "t@e.com"}

    def bus(n, key, kv):
        return {"typ": f"Bus{n}", "name": f"mxCell_{key}", "id": key, "vn_kv": kv, "userFriendlyName": key.upper()}

    def line(key, a, b, km):
        # No capacitance, so a radial line carries exactly the current of a fault beyond it.
        return {"typ": "Line0", "name": f"mxCell_{key}", "id": key, "busFrom": a, "busTo": b,
                "r_ohm_per_km": "0.125", "x_ohm_per_km": "0.0911", "c_nf_per_km": "0", "g_us_per_km": "0",
                "length_km": km, "max_i_ka": "0.4", "type": "cs", "parallel": "1", "df": "1",
                "r0_ohm_per_km": "0.5", "x0_ohm_per_km": "0.3", "c0_nf_per_km": "0", "endtemp_degree": "160",
                "in_service": "true", "userFriendlyName": key.upper()}

    def trafo(key, hv, lv, group, shift, mag0="100"):
        return {"typ": "Transformer0", "name": f"mxCell_{key}", "id": key, "hv_bus": hv, "lv_bus": lv,
                "sn_mva": "1", "vn_hv_kv": "10", "vn_lv_kv": "0.4", "vkr_percent": "0.75", "vk_percent": "5.6",
                "pfe_kw": "0.63", "i0_percent": "0.079", "shift_degree": shift, "tap_pos": "0", "tap_neutral": "0",
                "tap_max": "0", "tap_min": "0", "tap_step_percent": "0", "tap_side": "hv", "parallel": "1",
                "vector_group": group, "vk0_percent": "5.6", "vkr0_percent": "0.75", "mag0_percent": mag0,
                "mag0_rx": "0", "si0_hv_partial": "0.9", "in_service": "true", "userFriendlyName": key.upper()}

    return {
        "0": settings,
        "1": bus(0, "a", "10"), "2": bus(1, "b", "10"), "3": bus(2, "c", "0.4"), "4": bus(3, "d", "0.4"),
        "5": {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_a", "vm_pu": "1",
              "va_degree": "0", "s_sc_max_mva": "205.77", "s_sc_min_mva": "160", "rx_max": "0.0543",
              "rx_min": "0.0543", "r0x0_max": "1.95", "x0x_max": "16.3", "r0x0_min": "1.95", "x0x_min": "16.3",
              "in_service": "true", "userFriendlyName": "Grid"},
        "6": line("l1", "mxCell_a", "mxCell_b", "0.47"),
        "7": trafo("td", "mxCell_b", "mxCell_c", "Dyn", "150"),
        # A large zero-sequence magnetising impedance: the YNyn is no earth path for a fault at B.
        "8": trafo("ty", "mxCell_b", "mxCell_d", "YNyn", "0", mag0="100000"),
    }


def solve(fault, case, selected=None):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=payload(fault, case, selected))
    assert response.status_code == 200, response.data[:400]
    data = json.loads(response.data)
    assert not data.get("error"), data.get("message") or data
    assert not data.get("warnings"), data["warnings"]
    buses = {b["id"]: b for b in data["busbars"]}
    lines = {ln["id"]: ln for ln in data["lines_sc"]}
    trafos = {t["id"]: t for t in data["trafos_sc"]}
    return buses, lines, trafos


def close(a, b, rel):
    return abs(a - b) <= rel * max(abs(a), abs(b), 1e-9)


def main() -> None:
    # Single-phase: behind the Dyn transformer the 10 kV phase current is Ik1(0.4 kV) * ratio / sqrt(3).
    buses, lines, trafos = solve("1ph", "max")
    dyn = trafos["td"]
    assert dyn["fault_bus"] == "mxCell_c", dyn
    assert close(dyn["ikss_lv_ka"], buses["c"]["ikss_ka"], 1e-6), (dyn, buses["c"])
    assert close(dyn["ikss_hv_ka"], dyn["ikss_lv_ka"] * RATIO / math.sqrt(3.0), 1e-3), dyn
    # YNyn passes the zero sequence too, so all three sequence currents reach the 10 kV side.
    yny = trafos["ty"]
    assert yny["fault_bus"] == "mxCell_d", yny
    assert close(yny["ikss_hv_ka"], yny["ikss_lv_ka"] * RATIO, 0.02), yny
    # The radial line carries the whole current of whichever fault beyond it is largest.
    expected = max(buses["b"]["ikss_ka"], dyn["ikss_hv_ka"], yny["ikss_hv_ka"])
    assert close(lines["l1"]["ikss_ka"], expected, 1e-4), (lines["l1"], buses["b"], dyn, yny)
    assert lines["l1"]["ith_ka"] >= lines["l1"]["ikss_ka"] and lines["l1"]["ip_ka"] > lines["l1"]["ikss_ka"]
    print(f"1ph max: Dyn HV {dyn['ikss_hv_ka']:.3f} kA = LV {dyn['ikss_lv_ka']:.3f} kA x ratio / sqrt(3); "
          f"line {lines['l1']['ikss_ka']:.3f} kA (fault at {lines['l1']['fault_bus']})")

    # Two-phase: I2 = -I1, so across 150 degrees one phase carries 2/sqrt(3) times the transferred current.
    buses, lines, trafos = solve("2ph", "max")
    dyn = trafos["td"]
    assert close(dyn["ikss_hv_ka"], dyn["ikss_lv_ka"] * RATIO * 2.0 / math.sqrt(3.0), 1e-3), dyn
    assert close(trafos["ty"]["ikss_hv_ka"], trafos["ty"]["ikss_lv_ka"] * RATIO, 1e-3), trafos["ty"]
    print(f"2ph max: Dyn HV {dyn['ikss_hv_ka']:.3f} kA = LV x ratio x 2/sqrt(3)")

    # Minimum case: the fault at the line's own far end, with ip and Ith of that same fault.
    for fault in ("3ph", "2ph", "1ph"):
        buses, lines, trafos = solve(fault, "min")
        l1, b = lines["l1"], buses["b"]
        assert l1["fault_bus"] == "mxCell_b", (fault, l1)
        assert close(l1["ikss_ka"], b["ikss_ka"], 1e-4), (fault, l1, b)
        assert close(l1["ip_ka"] / l1["ikss_ka"], b["ip_ka"] / b["ikss_ka"], 1e-6), (fault, l1, b)
        assert close(l1["ith_ka"] / l1["ikss_ka"], b["ith_ka"] / b["ikss_ka"], 1e-6), (fault, l1, b)
        for key, lv_bus in (("td", "c"), ("ty", "d")):
            assert trafos[key]["fault_bus"] == f"mxCell_{lv_bus}", (fault, trafos[key])
            assert close(trafos[key]["ikss_lv_ka"], buses[lv_bus]["ikss_ka"], 1e-4), (fault, trafos[key])
        print(f"{fault} min: line {l1['ikss_ka']:.3f} kA = bus B {b['ikss_ka']:.3f} kA (fault at its far end)")

    # User Selection without the line's terminals: the line shows the selected fault.
    buses, lines, trafos = solve("3ph", "min", selected=["mxCell_c"])
    assert lines["l1"]["fault_bus"] == "mxCell_c", lines["l1"]
    assert close(lines["l1"]["ikss_ka"], trafos["td"]["ikss_hv_ka"], 1e-4), (lines["l1"], trafos["td"])
    assert trafos["ty"]["fault_bus"] is None and trafos["ty"]["ikss_hv_ka"] == 0.0, trafos["ty"]
    print("3ph min, User Selection C: line shows the fault at C; the other transformer carries none")
    three_winding()
    print("short-circuit branch results OK")


def three_winding_net(c0_nf_per_km):
    """110/20/10 kV YNdyn transformer, a 20 kV cable on the delta winding and a 10 kV cable."""
    import pandapower as pp

    net = pp.create_empty_network()
    hv, mv, lv, mv2, lv2 = (pp.create_bus(net, kv) for kv in (110, 20, 10, 20, 10))
    pp.create_ext_grid(net, hv, s_sc_max_mva=3000, s_sc_min_mva=2500, rx_max=0.1, rx_min=0.1,
                       x0x_max=1.0, r0x0_max=0.1, x0x_min=1.0, r0x0_min=0.1)
    pp.create_transformer3w_from_parameters(
        net, hv, mv, lv, 110, 20, 10, 40, 40, 40, vk_hv_percent=12, vk_mv_percent=8, vk_lv_percent=6,
        vkr_hv_percent=0.4, vkr_mv_percent=0.3, vkr_lv_percent=0.3, pfe_kw=20, i0_percent=0.1,
        shift_mv_degree=150, shift_lv_degree=150, vk0_hv_percent=12, vk0_mv_percent=8, vk0_lv_percent=6,
        vkr0_hv_percent=0.4, vkr0_mv_percent=0.3, vkr0_lv_percent=0.3, vector_group="YNdyn")
    for a, b in ((mv, mv2), (lv, lv2)):
        pp.create_line_from_parameters(net, a, b, 2, 0.1, 0.1, 0, 0.4, r0_ohm_per_km=0.4, x0_ohm_per_km=0.3,
                                       c0_nf_per_km=c0_nf_per_km, endtemp_degree=80)
    return net


def three_winding_solve(fault, case, c0_nf_per_km=0.0):
    import pandapower.shortcircuit as sc

    with contextlib.redirect_stdout(io.StringIO()):
        from pandapower_electrisim import electrisim_1ph_ip_ith, electrisim_branch_sc_results
    net = three_winding_net(c0_nf_per_km)
    sc.calc_sc(net, fault=fault, case=case, ip=True, ith=True, branch_results=True, tk_s=1, kappa_method="C")
    if fault == "1ph":
        electrisim_1ph_ip_ith(net, case=case)
    assert electrisim_branch_sc_results(net, fault=fault, case=case)
    return net


def three_winding() -> None:
    # Minimum case: one fault cannot load all three windings, so each winding shows its own terminal
    # fault (pandapower's single snapshot left two windings at about 0).
    net = three_winding_solve("3ph", "min")
    t3, ik = net.res_trafo3w_sc.iloc[0], net.res_bus_sc["ikss_ka"]
    assert t3["fault_bus"] is None, t3
    assert close(t3["ikss_mv_ka"], ik.at[1], 1e-6) and close(t3["ikss_lv_ka"], ik.at[2], 1e-6), (t3, ik)
    assert t3["ikss_hv_ka"] > 0.5, t3
    print(f"3ph min three-winding: HV {t3['ikss_hv_ka']:.3f} / MV {t3['ikss_mv_ka']:.3f} / LV {t3['ikss_lv_ka']:.3f} kA")

    # The 20 kV cable behind the delta winding has no zero-sequence earth and no capacitance. That
    # part of the zero-sequence network is singular; it must neither spoil the 110 kV current of a
    # 10 kV earth fault nor show a current itself. With a little cable capacitance the network is
    # regular, and the result must be practically the same.
    floating = three_winding_solve("1ph", "max")
    regular = three_winding_solve("1ph", "max", c0_nf_per_km=10.0)
    t3, reference = floating.res_trafo3w_sc.iloc[0], regular.res_trafo3w_sc.iloc[0]
    assert floating.res_line_sc.at[0, "ikss_ka"] == 0.0 and t3["ikss_mv_ka"] == 0.0, (floating.res_line_sc, t3)
    # pandapower's own bus Ik1 differs between the two (its inversion of the singular network), so
    # compare the 110 kV current per kA of 10 kV fault current.
    ik_floating, ik_regular = floating.res_bus_sc["ikss_ka"].at[2], regular.res_bus_sc["ikss_ka"].at[2]
    assert close(t3["ikss_hv_ka"] / ik_floating, reference["ikss_hv_ka"] / ik_regular, 1e-3), (t3, reference)
    # Phase currents on the 110 kV side: 2 I1 cos 30 from the positive and negative sequence, plus
    # part of the zero sequence that the YN winding carries.
    transferred = ik_floating / 3.0 * 10.0 / 110.0
    assert 2.0 * transferred * math.cos(math.radians(30.0)) < t3["ikss_hv_ka"] < 3.0 * transferred, t3
    print(f"1ph max three-winding: HV {t3['ikss_hv_ka']:.3f} kA; the unearthed 20 kV cable carries none")


if __name__ == "__main__":
    main()
