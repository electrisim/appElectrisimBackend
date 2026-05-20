# -*- coding: utf-8 -*-
"""
Electrisim pandapower import — small MV/LV radial example with fuse-mode switches.

- 20 kV slack → 0.63 MVA 20/0.4 kV transformer → 400 V lines → load.
- ``net.switch`` rows use ``type="fuse"`` for trafo, line, and a bus-bus (load) path.

Import: POST this file’s contents to ``/import-pandapower`` (frontend already does this).
The script must define a variable named ``net`` in the global scope after execution.
"""

import pandapower as pp

# --- Network (variable ``net`` is required for Electrisim import) ---
net = pp.create_empty_network(name="fuse_network_demo", f_hz=50)

# Buses
pp.create_buses(
    net,
    nr_buses=5,
    vn_kv=[20, 0.4, 0.4, 0.4, 0.4],
    index=[0, 1, 2, 3, 4],
    name=None,
    type="n",
    geodata=[(0, 0), (0, -2), (0, -4), (0, -6), (0, -8)],
)

# External grid
pp.create_ext_grid(
    net,
    0,
    vm_pu=1.0,
    va_degree=0,
    s_sc_max_mva=100,
    s_sc_min_mva=50,
    rx_max=0.1,
    rx_min=0.1,
)

# Lines (LV segments)
pp.create_lines_from_parameters(
    net,
    from_buses=[1, 2],
    to_buses=[2, 3],
    length_km=[0.1, 0.1],
    r_ohm_per_km=0.2067,
    x_ohm_per_km=0.080424,
    c_nf_per_km=261,
    name=None,
    index=[0, 1],
    max_i_ka=0.27,
)

net.line["endtemp_degree"] = 250

# Transformer (standard type must exist in pandapower ``trafo`` library)
pp.create_transformer(net, hv_bus=0, lv_bus=1, std_type="0.63 MVA 20/0.4 kV")

# Trafo fuses
pp.create_switches(net, buses=[0, 1], elements=[0, 0], et="t", type="fuse")

# Line fuses
pp.create_switches(net, buses=[1, 2], elements=[0, 1], et="l", type="fuse")

# Load fuse (bus-bus switch)
pp.create_switch(net, bus=3, element=4, et="b", type="fuse", z_ohm=0.0001)

# Load
pp.create_load(
    net,
    bus=4,
    p_mw=0.1,
    q_mvar=0,
    const_z_percent=0,
    const_i_percent=0,
    sn_mva=0.1,
    name=None,
    scaling=1.0,
    index=0,
)

if __name__ == "__main__":
    print("Switches:", len(net.switch.index))
    print(net.switch[["bus", "element", "et", "type", "closed"]])
    try:
        pp.runpp(net, algorithm="nr", calculate_voltage_angles=True)
        print("runpp OK — max line loading %:", float(net.res_line.loading_percent.max()))
    except Exception as exc:
        print("runpp skipped/failed (topology still valid for import):", exc)
