"""The IEC 60909 short circuit must use the dialog's LV voltage tolerance (6 % or 10 %).

The Short Circuit dialog sends "Voltage tolerance in low voltage grids" as
``fault_impedance``. It used to be read and then ignored, so every run used 10 %.
The tolerance sets the voltage factor c below 1 kV, which mostly moves the minimum
currents (cmin 0.95 at 6 %, 0.90 at 10 %).

Run with ``python samples/test_iec_sc_lv_tolerance.py``.
"""
from __future__ import annotations

import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandapower as pp  # noqa: E402
import pandapower.shortcircuit as sc  # noqa: E402

import pandapower_electrisim as pe  # noqa: E402


def lv_network():
    net = pp.create_empty_network()
    mv = pp.create_bus(net, 20, name="MV")
    lv = pp.create_bus(net, 0.4, name="LV")
    pp.create_ext_grid(net, mv, s_sc_max_mva=500, rx_max=0.1, s_sc_min_mva=400, rx_min=0.1, name="EG")
    pp.create_transformer(net, mv, lv, "0.63 MVA 20/0.4 kV", name="T1")
    for table in ("bus", "ext_grid", "trafo"):
        net[table]["id"] = [f"{table}{i}" for i in range(len(net[table]))]
    return net


def lv_ikss(tol: str, case: str) -> float:
    net = lv_network()
    pe.shortcircuit(net, {"fault_type": "3ph", "fault_location": case, "fault_impedance": tol}, Busbars={})
    return float(net.res_bus_sc.ikss_ka.iloc[1])


def reference_ikss(tol: int, case: str) -> float:
    net = lv_network()
    sc.calc_sc(net, case=case, lv_tol_percent=tol)
    return float(net.res_bus_sc.ikss_ka.iloc[1])


def main() -> None:
    assert [pe.sc_lv_tol_percent(d) for d in (
        {}, {"fault_impedance": "6"}, {"fault_impedance": "6%"}, {"lv_tol_percent": 10},
        {"fault_impedance": "7"}, {"fault_impedance": None},
    )] == [10, 6, 6, 10, 10, 10]

    for case in ("min", "max"):
        for tol in (6, 10):
            got, want = lv_ikss(str(tol), case), reference_ikss(tol, case)
            assert abs(got - want) < 1e-6, (case, tol, got, want)
    # The minimum current at 6 % must be clearly higher than at 10 % (cmin 0.95 vs 0.90).
    assert lv_ikss("6", "min") > lv_ikss("10", "min") * 1.03

    code = pe.generate_pandapower_python_code(
        lv_network(), {}, {}, "nr", "auto", "auto", study="shortcircuit",
        sc_in_data={"fault_impedance": "6", "fault_location": "min"},
    )
    assert "lv_tol_percent=6," in code, "exported script must use the same tolerance"
    print("IEC SC LV tolerance OK")


if __name__ == "__main__":
    main()
