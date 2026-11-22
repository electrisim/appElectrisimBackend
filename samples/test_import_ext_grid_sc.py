"""Importing a pandapower .py keeps the short-circuit data of the External Grid.

Before the fix the import sent only name, bus, voltage, angle, slack weight and in service, so the
diagram fell back to a 1,000,000 MVA grid and every short-circuit study of an imported model was off.
Run with ``python samples/test_import_ext_grid_sc.py``.
"""
import contextlib
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app  # noqa: E402

CODE = """
import pandapower as pp
net = pp.create_empty_network()
b = pp.create_bus(net, vn_kv=138.0, name="Utility_138")
pp.create_ext_grid(net, bus=b, vm_pu=1.02, s_sc_max_mva=8000, s_sc_min_mva=4000, rx_max=0.1, rx_min=0.2,
                   r0x0_max=0.1, x0x_max=1.0, r0x0_min=0.15, x0x_min=1.1, name="Utility_Grid")
b2 = pp.create_bus(net, vn_kv=138.0, name="Other")
pp.create_ext_grid(net, bus=b2, name="Plain")
"""


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        r = app.app.test_client().post('/import-pandapower', json={'content': CODE})
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    rows = json.loads(json.loads(r.get_data())['_object']['ext_grid']['_object'])['data']
    # [name, bus, vm_pu, va_degree, slack_weight, in_service, s_sc_max, s_sc_min, rx_max, rx_min, r0x0_max, x0x_max, r0x0_min, x0x_min]
    assert rows[0][0] == 'Utility_Grid' and rows[0][6:] == [8000.0, 4000.0, 0.1, 0.2, 0.1, 1.0, 0.15, 1.1], rows[0]
    # a grid without short-circuit data sends nulls, so the diagram keeps its own defaults
    assert len(rows[1]) == 14 and all(v is None for v in rows[1][6:]), rows[1]
    print('ok External Grid short-circuit data survives the pandapower import')


if __name__ == '__main__':
    main()
