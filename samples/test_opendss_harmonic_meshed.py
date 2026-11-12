"""Harmonic analysis must start from the same fundamental solution as the OpenDSS load flow.

The harmonic study rebuilt the circuit differently from the load flow (no External Grid data
on the source, no generator voltage control, no fallback solves) and ran a plain "solve":

- on case39 that solve diverged and the study ended in HTTP 500 with OpenDSS error #487;
- on case14 it "converged" to another operating point, so the fundamental line currents in
  the harmonic results did not match the load-flow currents shown next to them.

Run with ``python samples/test_opendss_harmonic_meshed.py``.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FIXTURES = os.path.join(ROOT, "samples", "fixtures")

import app  # noqa: E402

CLIENT = app.app.test_client()


def harmonic(fixture):
    with open(os.path.join(FIXTURES, fixture), encoding="utf-8") as handle:
        payload = json.load(handle)
    for element in payload.values():
        if "Parameters" in str(element.get("typ", "")):
            element["analysisType"] = "harmonic"
            element["harmonics"] = "3,5,7,11,13"
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = CLIENT.post("/", json=payload)
    assert response.status_code == 200, (fixture, response.status_code, response.get_data(as_text=True)[:300])
    data = json.loads(response.get_data(as_text=True))
    assert not data.get("error"), (fixture, data.get("error"))
    assert data.get("harmonic_analysis", {}).get("executed"), fixture
    return data


def main() -> None:
    for fixture in ("opendss_lf_case14.json", "opendss_lf_case39.json", "opendss_lf_cigre_hv.json"):
        data = harmonic(fixture)
        checked = 0
        for line in data["lines"]:
            load_flow_a = float(line["i_from_ka"]) * 1000.0
            fundamental_a = float(line["fundamental_current_a"])
            if load_flow_a < 1.0:
                continue
            assert abs(fundamental_a - load_flow_a) <= 0.01 * load_flow_a, (
                fixture, line.get("name"), load_flow_a, fundamental_a)
            checked += 1
        assert checked > 0, fixture
        print(f"{fixture}: harmonic analysis ran; fundamental current matches the load flow on {checked} lines")
    print("All harmonic checks passed.")


if __name__ == "__main__":
    main()
