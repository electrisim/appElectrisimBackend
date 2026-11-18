"""Single-phase bus Ik" stays right when part of the network has no zero-sequence earth.

pandapower models an open zero-sequence path (a delta winding) as a 1e20 pu branch and inverts
the whole zero-sequence network. A delta-fed cable with c0 = 0 has no earth at all; that part is
singular, and the inverse spoiled Z0 at the earthed buses too. In a 110/20/10 kV YNdyn
transformer the 10 kV bus got Z0 = 0.00029 instead of 0.00111 pu and Ik1" about 20% too high,
and the unearthed buses showed Rk0 of about -1e45 ohm. A PV or BESS plant behind a YNd
transformer with c0 = 0 collector cables is the same case.

Electrisim now inverts each earthed part on its own and holds an unearthed part open. A little
cable capacitance (c0 = 10 nF/km) earths that part and makes the network regular, where
pandapower was right all along, so the results with c0 = 0 must match it.

Run with ``python samples/test_sc_unearthed_zero_sequence.py``.
"""
from __future__ import annotations

import contextlib
import io
import json
import math
import os
import subprocess
import sys
import tempfile
import warnings

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import app  # noqa: E402  (installs Electrisim's pandapower fixes)
import pandapower as pp  # noqa: E402
import pandapower.shortcircuit as sc  # noqa: E402

TOL = 1e-3  # 0.1 %


def close(a, b, rel=TOL):
    return abs(a - b) <= rel * max(abs(a), abs(b), 1e-9)


def three_winding_net(c0_nf_per_km):
    """110/20/10 kV YNdyn transformer, a 20 kV cable on the delta winding and a 10 kV cable."""
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


def three_winding() -> None:
    """The reproduction: pandapower calc_sc with Electrisim's Zbus, c0 = 0 against c0 = 10 nF/km."""
    earthed, unearthed = (0, 2, 4), (1, 3)  # the 20 kV buses hang on the delta winding
    for case in ("max", "min"):
        results = {}
        for c0 in (0.0, 10.0):
            net = three_winding_net(c0)
            with contextlib.redirect_stdout(io.StringIO()):
                sc.calc_sc(net, fault="1ph", case=case, ip=True, ith=True, branch_results=True, tk_s=1,
                           kappa_method="C")
            results[c0] = net.res_bus_sc
        floating, regular = results[0.0], results[10.0]
        for b in earthed:
            for column in ("ikss_ka", "rk0_ohm", "xk0_ohm"):
                assert close(floating.at[b, column], regular.at[b, column]), (case, b, column, floating, regular)
        for b in unearthed:  # no zero-sequence path: no earth-fault current, Z0 open
            assert floating.at[b, "ikss_ka"] < 1e-12, (case, floating)
            assert math.isinf(floating.at[b, "rk0_ohm"]) and math.isinf(floating.at[b, "xk0_ohm"]), floating
        if case == "max":  # X0 of the 10 kV bus in per unit (100 ohm base): 0.00111, not pandapower's 0.00029
            assert close(floating.at[2, "xk0_ohm"] / 100.0, 0.001112, 2e-3), floating
        print(f"three-winding 1ph {case}: 10 kV Ik1 {floating.at[2, 'ikss_ka']:.3f} kA "
              f"(c0 = 10 nF/km: {regular.at[2, 'ikss_ka']:.3f} kA), Xk0 {floating.at[2, 'xk0_ohm']:.4f} ohm")


SECTIONS = 3  # 20 kV collector cable sections of 0.5 km, each with a 20/0.69 kV unit transformer


def plant_payload(fault, case, c0_nf_per_km, export=False):
    """110 kV grid, YNd11 main transformer, 20 kV collector cable, Dyn11 unit transformers, BESS.

    With c0 = 0 pandapower 3.3.2 alone stops with "singular matrix" on this network (maximum
    case); similar plants gave Ik1" 10-40% wrong at the earthed buses instead.
    """
    settings = {"typ": "ShortCircuitPandaPower Parameters", "fault_type": fault, "fault_location": case,
                "fault_bus_mode": "all", "fault_bus_ids": [], "fault_bus_names": [], "fault_impedance": "6",
                "topology": "auto", "tk_s": "1", "r_fault_ohm": "0", "x_fault_ohm": "0", "inverse_y": "True",
                "exportPython": export, "user_email": "t@e.com"}

    def bus(n, key, kv):
        return {"typ": f"Bus{n}", "name": f"mxCell_{key}", "id": key, "vn_kv": kv, "userFriendlyName": key.upper()}

    def trafo(key, hv, lv, sn, vn_hv, vn_lv, vk, group, shift):
        return {"typ": "Transformer0", "name": f"mxCell_{key}", "id": key, "hv_bus": hv, "lv_bus": lv,
                "sn_mva": sn, "vn_hv_kv": vn_hv, "vn_lv_kv": vn_lv, "vkr_percent": "0.5", "vk_percent": vk,
                "pfe_kw": "10", "i0_percent": "0.1", "shift_degree": shift, "tap_pos": "0", "tap_neutral": "0",
                "tap_max": "0", "tap_min": "0", "tap_step_percent": "0", "tap_side": "hv", "parallel": "1",
                "vector_group": group, "vk0_percent": vk, "vkr0_percent": "0.5", "mag0_percent": "100",
                "mag0_rx": "0", "si0_hv_partial": "0.9", "in_service": "true", "userFriendlyName": key.upper()}

    def cable(key, a, b):
        return {"typ": "Line0", "name": f"mxCell_{key}", "id": key, "busFrom": a, "busTo": b,
                "r_ohm_per_km": "0.1", "x_ohm_per_km": "0.1", "c_nf_per_km": "250", "g_us_per_km": "0",
                "length_km": "0.5", "max_i_ka": "0.4", "type": "cs", "parallel": "1", "df": "1",
                "r0_ohm_per_km": "0.4", "x0_ohm_per_km": "0.3", "c0_nf_per_km": str(c0_nf_per_km),
                "endtemp_degree": "250", "in_service": "true", "userFriendlyName": key.upper()}

    cells = [
        settings,
        bus(0, "poi", "110"), bus(1, "mv", "20"),
        {"typ": "External Grid0", "name": "mxCell_eg", "id": "eg", "bus": "mxCell_poi", "vm_pu": "1",
         "va_degree": "0", "s_sc_max_mva": "3000", "s_sc_min_mva": "2500", "rx_max": "0.1",
         "rx_min": "0.1", "r0x0_max": "0.1", "x0x_max": "1", "r0x0_min": "0.1", "x0x_min": "1",
         "in_service": "true", "userFriendlyName": "Grid"},
        trafo("tm", "mxCell_poi", "mxCell_mv", "40", "110", "20", "12", "YNd", "330"),
    ]
    previous = "mxCell_mv"
    for k in range(1, SECTIONS + 1):
        cells += [bus(2 * k, f"k{k}", "20"), bus(2 * k + 1, f"lv{k}", "0.69"),
                  cable(f"cab{k}", previous, f"mxCell_k{k}"),
                  trafo(f"tu{k}", f"mxCell_k{k}", f"mxCell_lv{k}", "4", "20", "0.69", "7", "Dyn", "330")]
        previous = f"mxCell_k{k}"
    # Converter with Ik" per fault and a negative-sequence reactance (the r2/x2 correction, which
    # uses Z0 too) at the end of the feeder.
    cells.append({"typ": "Static Generator0", "name": "mxCell_bess", "id": "bess", "bus": f"mxCell_lv{SECTIONS}",
                  "p_mw": "3", "q_mvar": "0", "sn_mva": "4", "scaling": "1", "type": "wye", "k": "1.2", "rx": "0",
                  "generator_type": "current_source", "lrc_pu": "0", "max_ik_ka": "0", "kappa": "0",
                  "current_source": "true", "ikss_3ph_ka": "4.0", "ikss_2ph_ka": "3.5", "ikss_1ph_ka": "2.0",
                  "sc_ref_vn_kv": "0.69", "r2_pu": "0.02", "x2_pu": "0.2", "in_service": "true",
                  "userFriendlyName": "BESS"})
    return {str(i): cell for i, cell in enumerate(cells)}


def solve(fault, case, c0_nf_per_km, export=False):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=plant_payload(fault, case, c0_nf_per_km, export))
    assert response.status_code == 200, response.data[:400]
    data = json.loads(response.data)
    assert not data.get("error"), data.get("message") or data
    assert not data.get("warnings"), data["warnings"]
    if export:
        assert data.get("pandapower_python"), data.get("pandapower_python_error")
    return data


def by_id(rows):
    return {row["id"]: row for row in rows}


def run_exported(code):
    """Run the exported script in a fresh interpreter without Electrisim's modules; return its results."""
    dump = (
        "\nimport json as _json\n"
        "print('@@RESULT@@' + _json.dumps({\n"
        "    'bus': {str(net.bus.at[i, 'name']): {c: float(net.res_bus_sc.at[i, c]) for c in "
        "('ikss_ka', 'ip_ka', 'ith_ka', 'rk0_ohm', 'xk0_ohm')} for i in net.res_bus_sc.index},\n"
        "    'line': {str(net.line.at[i, 'name']): {c: float(net.res_line_sc.at[i, c]) for c in "
        "('ikss_ka', 'ip_ka', 'ith_ka')} for i in net.res_line_sc.index},\n"
        "    'trafo': {str(net.trafo.at[i, 'name']): {c: float(net.res_trafo_sc.at[i, c]) for c in "
        "('ikss_hv_ka', 'ikss_lv_ka')} for i in net.res_trafo_sc.index},\n"
        "}))\n"
    )
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "electrisim_export.py")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(code + dump)
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONWARNINGS="ignore")
        proc = subprocess.run([sys.executable, "-I", path], cwd=folder, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=600, env=env)
    assert proc.returncode == 0, proc.stderr[-2000:]
    marker = [ln for ln in proc.stdout.splitlines() if ln.startswith("@@RESULT@@")]
    assert marker, proc.stdout[-2000:]
    return json.loads(marker[-1][len("@@RESULT@@"):])


def plant() -> None:
    # The 20 kV collector system hangs on the delta winding; with c0 = 0 it has no earth at all.
    earthed = ["poi"] + [f"lv{k}" for k in range(1, SECTIONS + 1)]
    unearthed = ["mv"] + [f"k{k}" for k in range(1, SECTIONS + 1)]
    for case in ("max", "min"):
        floating = solve("1ph", case, 0.0, export=True)
        regular = solve("1ph", case, 10.0)
        f_bus, r_bus = by_id(floating["busbars"]), by_id(regular["busbars"])
        for key in earthed:
            for column in ("ikss_ka", "ip_ka", "ith_ka"):
                assert close(f_bus[key][column], r_bus[key][column]), (case, key, column, f_bus[key], r_bus[key])
        for key in unearthed:  # no zero-sequence path: at most the converter's own contribution
            assert f_bus[key]["ikss_ka"] < 0.1, (case, key, f_bus[key])
        # Transformer currents follow the same Z0 (each at the fault on its own terminals).
        f_tr, r_tr = by_id(floating["trafos_sc"]), by_id(regular["trafos_sc"])
        for key in f_tr:
            for column in ("ikss_hv_ka", "ikss_lv_ka"):
                assert close(f_tr[key][column], r_tr[key][column], 5e-3), (case, key, column, f_tr[key], r_tr[key])

        # The exported script, run on its own, gives the same numbers.
        script = run_exported(floating["pandapower_python"])
        for row in floating["busbars"]:
            got = script["bus"][row["name"]]
            for column in ("ikss_ka", "ip_ka", "ith_ka"):
                assert close(row[column], got[column], 1e-6), (case, row["name"], column, row[column], got[column])
        for key in unearthed:
            assert math.isinf(script["bus"][f"mxCell_{key}"]["rk0_ohm"]), script["bus"][f"mxCell_{key}"]
        for row in floating["lines_sc"]:
            got = script["line"][row["name"]]
            for column in ("ikss_ka", "ip_ka", "ith_ka"):
                assert close(row[column] or 0.0, got[column], 1e-6), (case, row["name"], column, row, got)
        for row in floating["trafos_sc"]:
            got = script["trafo"][row["name"]]
            for column in ("ikss_hv_ka", "ikss_lv_ka"):
                assert close(row[column] or 0.0, got[column], 1e-6), (case, row["name"], column, row, got)
        print(f"plant 1ph {case}: 110 kV Ik1 {f_bus['poi']['ikss_ka']:.3f} kA, 0.69 kV Ik1 "
              f"{f_bus['lv1']['ikss_ka']:.3f} kA (c0 = 10 nF/km: {r_bus['poi']['ikss_ka']:.3f} / "
              f"{r_bus['lv1']['ikss_ka']:.3f} kA); exported script matches")


def regular_unchanged() -> None:
    """A network where every part is earthed keeps pandapower's own inverse, bit for bit."""
    import importlib

    from pandapower.shortcircuit.impedance import _calc_zbus as pandapower_calc_zbus

    calc_sc_module = importlib.import_module("pandapower.shortcircuit.calc_sc")
    assert calc_sc_module._calc_zbus is not pandapower_calc_zbus, "Electrisim's Zbus is not installed"
    for fault in ("1ph", "3ph"):
        results = []
        for patched in (True, False):
            installed = calc_sc_module._calc_zbus
            if not patched:
                calc_sc_module._calc_zbus = pandapower_calc_zbus
            try:
                net = three_winding_net(10.0)
                with contextlib.redirect_stdout(io.StringIO()):
                    sc.calc_sc(net, fault=fault, case="max", ip=True, ith=True, branch_results=True, tk_s=1,
                               kappa_method="C")
            finally:
                calc_sc_module._calc_zbus = installed
            results.append((net.res_bus_sc.copy(), net.res_line_sc.copy()))
        (bus_a, line_a), (bus_b, line_b) = results
        assert bus_a.equals(bus_b) and line_a.equals(line_b), (fault, bus_a, bus_b)
    print("every part earthed (c0 = 10 nF/km): results identical to pandapower's")


def main() -> None:
    three_winding()
    regular_unchanged()
    plant()
    print("single-phase Ik\" with unearthed zero-sequence parts OK")


if __name__ == "__main__":
    main()
