"""OpenDSS load flow against pandapower on meshed transmission templates with PV generators.

The fixtures are the payloads the frontend sends for the case14, case39 and CIGRE HV templates.
Before the fixes the OpenDSS results were 0.04-0.08 pu off:

1. Generators ignored vm_pu and were limited to +/-10 Mvar, so they were PQ injections.
2. OpenDSS's own Model=3 does not hold the set point on meshed grids, and on case39 even fixed-Q
   generators diverge; the load flow now holds generator buses with temporary voltage sources and
   hands their kvar back to the units.
3. Per-unit results used OpenDSS's calcv base, which put case14's 12 kV bus 8 on 14 kV.
4. The imported default "Dyn" on 0 degree transformers broke case14's loops (4-9 versus 4-7-9);
   CIGRE HV, where the default vector groups are consistent, keeps them.

Run with ``python samples/test_opendss_pv_generators.py``.
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
import pandapower.networks as pn  # noqa: E402

import app  # noqa: E402

CASES = (
    ("opendss_lf_case14.json", pn.case14, 0.002),
    ("opendss_lf_case39.json", pn.case39, 0.002),
    ("opendss_lf_cigre_hv.json", pn.create_cigre_network_hv, 0.002),
)


def run(payload):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=payload)
    assert response.status_code == 200, response.data[:300]
    data = json.loads(response.data)
    assert not data.get("error"), data.get("message") or data.get("error")
    return data


def main() -> None:
    summary = []
    for fixture, factory, tol in CASES:
        with open(os.path.join(HERE, "fixtures", fixture), encoding="utf-8") as fh:
            payload = json.load(fh)
        net = factory()
        assert int(float(payload["0"]["frequency"])) == int(net.f_hz)
        pp.runpp(net)
        ref = {str(name): vm for name, vm in zip(net.bus.name, net.res_bus.vm_pu)}
        labels = {v["name"]: str(v.get("userFriendlyName")) for v in payload.values()
                  if isinstance(v, dict) and str(v.get("typ", "")).startswith("Bus")}
        data = run(payload)
        assert not any("set points could not be held" in w for w in data.get("warnings") or []), data["warnings"]
        worst = 0.0
        for bus in data["busbars"]:
            label = labels[bus["name"]]
            diff = float(bus["vm_pu"]) - float(ref[label])
            assert abs(diff) < tol, (fixture, label, bus["vm_pu"], ref[label])
            worst = max(worst, abs(diff))
        summary.append(f"{fixture.split('_', 2)[2][:-5]} {worst:.4f}")
    print("OpenDSS PV generators match pandapower (max |dV| pu): " + ", ".join(summary))


if __name__ == "__main__":
    main()
