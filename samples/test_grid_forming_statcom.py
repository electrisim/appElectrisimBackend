"""Grid-forming STATCOM sizing: the energy and the bank must match the closed-form results.

Synthetic inertia of H seconds on S MVA releases H*S*(1 - (f1/f0)^2) when the frequency falls
from f0 to f1 and needs 2*H*S*RoCoF/f0 at the start of the fall. An ideal bank (no resistance,
no ageing, no converter loss, no margin, no current limit) needs exactly
C = 2*(E_discharge + E_charge)/(Vmax^2 - Vmin^2).

The network part is checked on the offshore wind fixture (450 MW, 200 Mvar STATCOM).

Run with ``python samples/test_grid_forming_statcom.py``.
"""
from __future__ import annotations

import contextlib
import io
import json
import math
import os
import sys
import warnings

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FIXTURES = os.path.join(ROOT, "samples", "fixtures")

import app  # noqa: E402
import grid_forming_statcom_electrisim as gfm  # noqa: E402

CLIENT = app.app.test_client()
IDEAL = {"cell_esr_mohm": "0", "eol_esr_percent": "100", "eol_capacitance_percent": "100",
         "efficiency_percent": "100", "design_margin_percent": "0", "cell_max_current_a": "1000000"}


def test_inertia_energy_matches_closed_form():
    params = dict(IDEAL, duty_phase_jump="false", duty_damping="false", inertia_h_s="3",
                  rocof_hz_s="2", f_min_hz="47.5", f_max_hz="51.5")
    out = gfm.sizing_core(params, 450.0, 200.0, 0.0)
    e_dis = 3 * 450 * (1 - 0.95 ** 2)
    e_chg = 3 * 450 * (1.03 ** 2 - 1)
    assert abs(out["requirement"]["energy_discharge_mj"] - e_dis) < 0.01 * e_dis
    assert abs(out["requirement"]["energy_charge_mj"] - e_chg) < 0.01 * e_chg
    # peak: 2 H S RoCoF / f0, times f/f0 at the top of the over-frequency event
    assert abs(out["requirement"]["peak_mw"] - 108.0 * 1.03) < 1.0
    bank = out["bank"]
    c_needed = 2 * (e_dis + e_chg) * 1e6 / (1500.0 ** 2 - 750.0 ** 2)
    c_string = 3000.0 / bank["cells_series"]
    assert bank["cells_series"] == math.ceil(1500 / 2.7)
    assert math.ceil(c_needed / c_string) <= bank["strings"] <= math.ceil(c_needed / c_string * 1.03) + 1
    for ev in out["events"].values():
        assert ev["v_low"] >= 750.0 - 0.5 and ev["v_high"] <= 1500.0 + 0.5


def test_resistance_and_ageing_make_the_bank_larger():
    base = dict(duty_phase_jump="false", duty_damping="false")
    ideal = gfm.sizing_core(dict(base, **IDEAL), 450.0, 200.0, 0.0)["bank"]["strings"]
    real = gfm.sizing_core(base, 450.0, 200.0, 0.0)["bank"]
    assert real["strings"] > ideal
    assert real["peak_cell_current_a"] <= real["cell_max_current_a"] + 1e-6


def test_frequency_support_adds_energy():
    base = dict(IDEAL, duty_inertia="false", duty_phase_jump="false", duty_damping="false",
                duty_frequency_support="true", droop_percent="5", deadband_mhz="20",
                support_range_percent="5", support_time_s="10", activation_threshold_hz="0.5",
                activation_delay_s="1")
    out = gfm.sizing_core(base, 450.0, 200.0, 0.0)
    # 5 % of 450 MW for 10 s, plus the short ramps in and out
    assert 22.5 * 10 <= out["requirement"]["energy_discharge_mj"] <= 22.5 * 11.5
    assert abs(out["requirement"]["peak_mw"] - 22.5) < 0.1


def test_no_duty_means_no_bank():
    out = gfm.sizing_core({"duty_inertia": "false", "duty_phase_jump": "false", "duty_damping": "false"},
                          450.0, 200.0, 0.0)
    assert out["storage_needed"] is False and out["bank"] is None
    assert out["requirement"]["peak_mw"] == 0.0


def _post_fixture(**params):
    with open(os.path.join(FIXTURES, "study_offshore_wind_statcom.json"), encoding="utf-8") as fh:
        data = json.load(fh)
    key = next(k for k, v in data.items() if isinstance(v, dict) and "Parameters" in str(v.get("typ", "")))
    study = {"typ": "GridFormingStatcomSizing Parameters", "frequency": "50", "run_control": True,
             "run_control_trafo3w": True, "run_control_shunt": True, "user_email": "t@e.com"}
    study.update(params)
    data[key] = study
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = CLIENT.post("/", json=data)
    assert response.status_code == 200, response.get_data(as_text=True)[:300]
    return json.loads(response.get_data(as_text=True))


def test_offshore_wind_model():
    out = _post_fixture(requirement_set="pse_grid_forming")
    assert out.get("study") == "grid_forming_statcom_sizing", out
    assert out["statcom"]["rating_mva"] == 200.0
    assert abs(out["plant"]["p_mw"] - 450.0) < 1e-6 and out["plant"]["units"] == 30
    assert out["statcom"]["q_operating_mvar"] is not None
    assert out["grid"]["statcom_bus"]["sk_max_mva"] > 1000
    assert out["statcom"]["rating_ok"] is True
    assert [row["item"] for row in out["checklist"]][:5] == ["15.3 a)", "15.3 b)", "15.4 a)", "15.4 b)", "15.4 c)"]
    # the older conditions ask for no grid forming: with its duties off there is nothing to store
    island = _post_fixture(requirement_set="pse_island", duty_inertia="false", duty_phase_jump="false",
                           duty_damping="false", duty_frequency_support="false",
                           activation_threshold_hz="0.5", activation_delay_s="1")
    assert island["storage_needed"] is False and island["bank"] is None
    assert island["statcom"]["rating_ok"] is True
    assert any(row["item"] == "1.3.5" and row["status"] == "plant" for row in island["checklist"])
    assert any(row["item"] == "Energy storage" for row in island["checklist"])
    # keeping the full reactive rating free leaves no room for active power
    full = _post_fixture(requirement_set="pse_grid_forming", q_reserve_mode="full")
    assert full["statcom"]["rating_ok"] is False
    assert full["statcom"]["required_rating_mva"] > 200.0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("All grid-forming STATCOM sizing tests passed.")
