"""Checks for ``script_guard``, which screens scripts sent to ``/import-pandapower``.

Normal network scripts (like the exported ones and the app templates) must still load;
scripts that try to reach the operating system or the file system must be rejected.

Run with ``python samples/test_script_guard.py``.
"""
from __future__ import annotations

import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import script_guard as g  # noqa: E402

GOOD = '''
import math
import json
from collections import deque
import pandapower as pp
import pandapower.shortcircuit as sc

net = pp.create_empty_network(f_hz=50)
b1 = pp.create_bus(net, vn_kv=20, name="B1")
b2 = pp.create_bus(net, vn_kv=20, name="B2")
pp.create_ext_grid(net, b1)
pp.create_line_from_parameters(net, b1, b2, 1.0, 0.1, 0.3, 10, 0.4)
pp.create_load(net, b2, p_mw=1.0 * math.sqrt(1))
for row in net.bus.itertuples():
    if not getattr(row, "in_service", True):
        pass
print("built", json.dumps({"n": len(net.bus)}))
pp.runpp(net)

if __name__ == "__main__":
    import os
    os.system("echo this never runs on import")
'''

# A script whose own power flow fails after it built the net still imports.
FAILS_AFTER_NET = '''
import pandapower as pp
net = pp.create_empty_network()
pp.create_bus(net, vn_kv=20)
raise RuntimeError("study failed")
'''

ATTACKS = {
    "import os": "import os\nos.system('whoami')",
    "from subprocess": "from subprocess import run\nrun(['whoami'])",
    "dunder import": "__import__('os').system('whoami')",
    "open file": "open('/etc/passwd').read()",
    "eval": "eval('1+1')",
    "subclass walk": "().__class__.__bases__[0].__subclasses__()",
    "getattr dunder": "getattr((), '__class__')",
    "dynamic getattr": "n = '__cl' + 'ass__'\ngetattr((), n)",
    "module via attr": "import pandapower as pp\npp.os.system('whoami')",
    "pickle loader": "import pandapower as pp\npp.from_pickle('x.p')",
    "pandas reader": "import pandas as pd\npd.read_csv('/etc/passwd')",
    "file writer kw": "import pandapower as pp\nnet = pp.create_empty_network()\npp.to_json(net, filename='x.json')",
    "to_string to file": "import pandas as pd\npd.DataFrame().to_string('app.py')",
    "format leak": "'{0.__class__}'.format(1)",
    "relative import": "from . import app",
    "globals": "globals()['__builtins__']",
}


def expect_rejected(name: str, code: str) -> None:
    try:
        g.run_script(code)
    except (g.ScriptRejected, ImportError, NameError) as exc:
        return exc
    raise AssertionError(f"attack '{name}' was not rejected")


def main() -> None:
    ns = g.run_script(GOOD)
    net = ns["net"]
    assert len(net.bus) == 2, len(net.bus)
    assert net.converged, "power flow in the script should have run"

    ns = g.run_script(FAILS_AFTER_NET)
    assert len(ns["net"].bus) == 1

    try:
        g.run_script("x = 1\nraise RuntimeError('boom')")
    except RuntimeError:
        pass
    else:
        raise AssertionError("an error without a net must propagate")

    for name, code in ATTACKS.items():
        exc = expect_rejected(name, code)
        assert exc is not None

    # The guard's own runtime wall: even code that slips past the check cannot import os.
    try:
        g._guarded_import("os")
    except ImportError:
        pass
    else:
        raise AssertionError("_guarded_import allowed os")

    # An exported network whose names contain quotes must import back unchanged.
    import pandapower as pp
    import pandapower_electrisim as pe
    exported = pp.create_empty_network()
    tricky = "St John's \\ \"North\""
    b1 = pp.create_bus(exported, 20, name=tricky)
    b2 = pp.create_bus(exported, 20, name="B2")
    pp.create_ext_grid(exported, b1, name=tricky)
    pp.create_line(exported, b1, b2, 1, "NA2XS2Y 1x95 RM/25 12/20 kV", name=tricky)
    pp.create_load(exported, b2, p_mw=1, name=tricky)
    code = pe.generate_pandapower_python_code(exported, {}, {}, "nr", "auto", "auto")
    back = g.run_script(code)["net"]
    assert list(back.bus.name) == [tricky, "B2"], list(back.bus.name)
    assert back.line.name.iloc[0] == tricky and back.load.name.iloc[0] == tricky

    # Running must not leave the throwaway module behind.
    assert not any(k.startswith("electrisim_import_") for k in sys.modules)
    print(f"script guard OK: good scripts load, {len(ATTACKS)} attack scripts rejected")


if __name__ == "__main__":
    main()
