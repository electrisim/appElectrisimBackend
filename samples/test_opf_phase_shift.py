"""OPF solves radial networks with Dyn transformers.

pandapower's AC OPF did not converge on the arc-flash tutorial, Kerber village network and BESS
templates: their Dyn5 / Dyn11 transformers (150 / 330 degree shifts) break it. No loop closes over
those shifts, so the backend retries without them and says so in a warning. A meshed network
whose loop closes over a shift must not be treated as loop-free.

Run with ``python samples/test_opf_phase_shift.py``.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import pandapower as pp  # noqa: E402

import app  # noqa: E402
from pandapower_electrisim import _opf_phase_shifts_loop_free  # noqa: E402


def main() -> None:
    with open(os.path.join(HERE, "fixtures", "opf_dyn5_radial.json"), encoding="utf-8") as fh:
        payload = json.load(fh)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=payload)
    data = json.loads(response.data)
    assert not data.get("error"), data.get("exception") or data.get("message")
    assert data.get("opf_converged") is True, data.get("opf_converged")
    assert any("phase shifts" in w for w in data.get("warnings") or []), data.get("warnings")
    print("OPF on radial Dyn5 network OK")

    # Two parallel paths between the same buses, one through a 150 degree transformer pair
    # and one direct: the loop closes over a shift, so it is not loop-free.
    net = pp.create_empty_network()
    hv, lv1, lv2 = (pp.create_bus(net, kv) for kv in (20.0, 0.4, 0.4))
    pp.create_transformer(net, hv, lv1, "0.63 MVA 20/0.4 kV")
    pp.create_transformer(net, hv, lv2, "0.63 MVA 20/0.4 kV")
    net.trafo.loc[1, "shift_degree"] = 0.0
    pp.create_line(net, lv1, lv2, 0.1, "NAYY 4x150 SE")
    assert net.trafo.shift_degree.iloc[0] != 0.0
    assert _opf_phase_shifts_loop_free(net) is False
    net.line.loc[0, "in_service"] = False
    assert _opf_phase_shifts_loop_free(net) is True
    print("phase-shift loop check OK")


if __name__ == "__main__":
    main()
