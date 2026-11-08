"""OpenDSS studies run when a line's zero-sequence data is left at 0.

The BESS utility-scale HV template has lines with r0/x0/c0 = 0, so Harmonic Analysis stopped with
"Parameter r0_ohm_per_km must be greater than 0". Unknown zero-sequence data now falls back to the
positive-sequence values, with a warning.

Run with ``python samples/test_opendss_zero_sequence_defaults.py``.
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

import app  # noqa: E402


def main() -> None:
    with open(os.path.join(HERE, "fixtures", "harmonic_bess_zero_seq.json"), encoding="utf-8") as fh:
        payload = json.load(fh)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = app.app.test_client().post("/", json=payload)
    data = json.loads(response.data)
    assert not data.get("error"), data.get("message") or data.get("exception")
    assert data.get("harmonic_analysis"), list(data)
    assert any("zero-sequence" in w for w in data.get("warnings") or []), data.get("warnings")
    print("OpenDSS zero-sequence defaults OK")


if __name__ == "__main__":
    main()
