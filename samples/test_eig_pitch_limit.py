"""Eigenvalue analysis does not call a wind farm unstable because of clamped pitch control.

On the onshore wind farm template (10 turbines below rated wind) every turbine's pitch sits at its
minimum angle. The linearisation ignores the pitch limiter, giving one positive eigenvalue per
turbine, so the app reported "UNSTABLE" although a time simulation stays flat. Participation
factors were also always empty (EIG.x_name is a numpy array, and ``array or []`` raised).

Run with ``python samples/test_eig_pitch_limit.py``.
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


def main() -> None:
    import andes_electrisim as ae

    with open(os.path.join(HERE, "fixtures", "eig_onshore_wf33.json"), encoding="utf-8") as fh:
        payload = json.load(fh)
    params = next(v for v in payload.values()
                  if isinstance(v, dict) and str(v.get("typ", "")).endswith("Parameters"))
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        result = json.loads(ae.run_eig(payload, params))
    assert not result.get("error"), result.get("message")
    assert result["n_positive_at_limit"] == 10, result["n_positive_at_limit"]
    assert result["n_positive"] == 0 and result["verdict"] != "unstable", (result["n_positive"], result["verdict"])
    assert any("pitch" in n for n in result["notes"]), result["notes"]
    assert result["participation"], "participation factors must be reported"
    print(f"EIG pitch-limit OK: verdict {result['verdict']}, {result['n_positive_at_limit']} clamped pitch modes")


if __name__ == "__main__":
    main()
