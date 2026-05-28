# -*- coding: utf-8 -*-
"""
Simple time-series tutorial network from pandapower ``time_series.ipynb`` (``simple_test_net``).

Upstream reference:
https://github.com/e2nIEE/pandapower/blob/develop/tutorials/time_series.ipynb

Topology::

    ext_grid b0 --- b1  trafo (110/20 kV)  b2 ---- b3  load (load1)
                                              |
                                              b4  sgen (sgen1)

Electrisim runs this file on import with ``pandapower`` available as ``pp``.
You MUST leave a variable named ``net`` in scope.

Topology and power-flow options only; no time-series controllers or ``run_timeseries``.
Run load flow in the app: Simulate → Load Flow → Calculate.
"""

net = pp.create_empty_network()
pp.set_user_pf_options(
    net,
    init_vm_pu="flat",
    init_va_degree="dc",
    calculate_voltage_angles=True,
)

b0 = pp.create_bus(net, 110)
b1 = pp.create_bus(net, 110)
b2 = pp.create_bus(net, 20)
b3 = pp.create_bus(net, 20)
b4 = pp.create_bus(net, 20)

pp.create_ext_grid(net, b0)
pp.create_line(net, b0, b1, 10, "149-AL1/24-ST1A 110.0")
pp.create_transformer(net, b1, b2, "25 MVA 110/20 kV", name="tr1")
pp.create_line(net, b2, b3, 10, "184-AL1/30-ST1A 20.0")
pp.create_line(net, b2, b4, 10, "184-AL1/30-ST1A 20.0")

pp.create_load(net, b3, p_mw=15.0, q_mvar=10.0, name="load1")
pp.create_sgen(net, b4, p_mw=20.0, q_mvar=0.15, name="sgen1")

# Single-line diagram layout (bus index → x, y)
_layout = {
    b0: (0, 0),   # 110 kV — external grid
    b1: (0, 1),   # 110 kV
    b2: (0, 2),   # 20 kV — after transformer
    b3: (-1, 3),  # 20 kV — load1
    b4: (1, 3),   # 20 kV — sgen1
}
for idx, (x, y) in _layout.items():
    net.bus.at[idx, "geo"] = {"type": "Point", "coordinates": [float(x), float(y)]}
