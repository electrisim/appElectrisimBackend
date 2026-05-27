# -*- coding: utf-8 -*-
"""
IEEE 9-bus test case from pandapower (``pandapower.networks.case9``).

Upstream reference:
https://github.com/e2nIEE/pandapower/blob/develop/pandapower/networks/power_system_test_cases.py

Electrisim runs this file on import with ``pandapower`` available as ``pp``.
You MUST leave a variable named ``net`` in scope.

This script loads the standard case9 network and assigns bus ``geo`` coordinates
for a readable single-line diagram on the canvas. It does **not** call ``runpp``
so import stays robust. Run power flow in the app: Simulate → Load Flow → Calculate.
"""

from pandapower.networks import case9

net = case9()

# Single-line diagram layout (pandapower bus index → x, y).
# Topology: slack/gen at buses 1 & 2, loads at buses 5, 7 & 9.
_layout = {
    0: (0, 0),    # Bus 1 — external grid + generator
    1: (6, 0),    # Bus 2 — generator
    2: (3, 6),    # Bus 3
    3: (3, 0),    # Bus 4
    4: (3, 2),    # Bus 5 — load
    5: (3, 4),    # Bus 6 — load
    6: (6, 2),    # Bus 7
    7: (6, 4),    # Bus 8 — load
    8: (0, 2),    # Bus 9
}

for idx, (x, y) in _layout.items():
    net.bus.at[idx, "geo"] = {"type": "Point", "coordinates": [float(x), float(y)]}
