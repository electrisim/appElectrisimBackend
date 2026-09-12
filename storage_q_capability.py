# -*- coding: utf-8 -*-
"""P–Q capability curve helpers for Storage (Qmin/Qmax vs |P|)."""

import json
import math

import numpy as np


def _truthy(val):
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ('true', '1', 'yes', 'on')


def parse_q_capability_points(raw):
    """Parse q_capability_curve_json into sorted list of dicts."""
    if raw is None or raw == '':
        return None
    try:
        pts = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(pts, list) or len(pts) < 2:
        return None
    out = []
    for pt in pts:
        if not isinstance(pt, dict):
            continue
        try:
            p = float(pt.get('p_mw'))
            qmin = float(pt.get('q_min_mvar'))
            qmax = float(pt.get('q_max_mvar'))
        except (TypeError, ValueError):
            continue
        out.append({'p_mw': p, 'q_min_mvar': qmin, 'q_max_mvar': qmax})
    if len(out) < 2:
        return None
    out.sort(key=lambda x: x['p_mw'])
    return out


def interp_q_capability_at_p(p_vals, q_vals, p_target, curve_style='straightLineYValues'):
    """Interpolate Q at p_target (mirrors pandapower_electrisim._interp_q_capability_at_p)."""
    if p_vals is None or q_vals is None or len(p_vals) < 2 or len(q_vals) < 2:
        return None
    p = np.asarray(p_vals, dtype=float)
    q = np.asarray(q_vals, dtype=float)
    p_m = float(p_target)
    if p_m <= p[0]:
        return float(q[0])
    if p_m >= p[-1]:
        return float(q[-1])
    style = curve_style if curve_style in ('straightLineYValues', 'constantYValue') else 'straightLineYValues'
    if style == 'constantYValue':
        for i in range(len(p) - 1):
            if p[i] <= p_m < p[i + 1]:
                return float(q[i])
        return float(q[-1])
    return float(np.interp(p_m, p, q))


# PCS capability vs voltage (not Volt-VAR droop). Peaks at 1.00 pu so a
# ±2 % dispatch-reversal band already scales Q (flat 0.95–1.05 hid the effect).
_DEFAULT_U_DERATE = (
    (0.88, 0.44),
    (0.92, 0.70),
    (0.96, 0.88),
    (1.00, 1.00),
    (1.04, 0.88),
    (1.08, 0.70),
    (1.10, 0.44),
)

BESS_PCS_PRESETS = frozenset(('pcs_circle', 'pcs_d_shape'))
BESS_D_SHAPE_Q_FLAT_PU = 0.90


def _sf(val, default=0.0):
    try:
        if val is None or val == '':
            return float(default)
        return float(val)
    except (TypeError, ValueError):
        return float(default)


def resolve_bess_pcs_ratings(element_data):
    """Inverter Sn and |P|max from Storage ratings (OPF limits, then momentary P)."""
    sn = abs(_sf((element_data or {}).get('sn_mva'), 0.0))
    p_ch = abs(_sf((element_data or {}).get('max_p_mw'), 0.0))
    p_dis = abs(_sf((element_data or {}).get('min_p_mw'), 0.0))
    p_mom = abs(_sf((element_data or {}).get('p_mw'), 0.0))
    p_max = max(p_ch, p_dis)
    if p_max <= 0:
        p_max = p_mom
    if sn <= 0 and p_max > 0:
        sn = p_max
    if p_max <= 0 and sn > 0:
        p_max = sn
    if sn <= 0:
        sn, p_max = 50.0, 50.0
    if p_max > sn:
        p_max = sn
    return sn, p_max


def bess_pcs_q_abs(p_mw, sn, preset='pcs_circle'):
    """|Q| on the four-quadrant PCS envelope at operating P."""
    s = abs(float(sn or 0.0))
    if s <= 0:
        return 0.0
    p = float(p_mw or 0.0)
    if abs(p) > s:
        p = math.copysign(s, p) if p != 0 else 0.0
    q_circ = math.sqrt(max(0.0, s * s - p * p))
    if str(preset or '').strip().lower() == 'pcs_d_shape':
        return min(BESS_D_SHAPE_Q_FLAT_PU * s, q_circ)
    return q_circ


def _looks_like_wtg_pf_triangle(pts):
    """Legacy Storage default: Q≈0 at P=0 and |Q| grows with P (±0.95 PF wind model)."""
    if not pts or len(pts) < 2:
        return False
    first, last = pts[0], pts[-1]
    if float(first.get('p_mw') or 0.0) > 1e-6:
        return False
    q0 = max(abs(float(first.get('q_min_mvar') or 0.0)), abs(float(first.get('q_max_mvar') or 0.0)))
    q1 = max(abs(float(last.get('q_min_mvar') or 0.0)), abs(float(last.get('q_max_mvar') or 0.0)))
    return q0 < 0.05 * max(q1, 1.0) and q1 > q0 + 0.1


def storage_q_voltage_derate(v_pu):
    """Scale factor in [0, 1] for Qmin/Qmax at terminal voltage v_pu."""
    try:
        v = float(v_pu)
    except (TypeError, ValueError):
        return 1.0
    if not math.isfinite(v) or v <= 0.05:
        return 1.0
    us = [row[0] for row in _DEFAULT_U_DERATE]
    fs = [row[1] for row in _DEFAULT_U_DERATE]
    if v <= us[0]:
        return float(fs[0])
    if v >= us[-1]:
        return float(fs[-1])
    return float(np.interp(v, us, fs))


def interp_storage_pq_limits(element_data, p_mw=None, v_pu=None):
    """
    Interpolate (q_min_mvar, q_max_mvar) at operating P from the Storage Q envelope.
    PCS presets (and the legacy wind ±0.95 PF triangle) use the analytical kVA circle.
    Signed P is used when the JSON table includes negative P (discharge).
    When q_cap_voltage_dependent is set, scale the band by voltage (capability vs U).
    Returns None if curve disabled or invalid.
    """
    if not _truthy((element_data or {}).get('reactive_capability_curve')):
        return None
    if p_mw is None:
        p_mw = _sf((element_data or {}).get('p_mw'), 0.0)
    p_op = float(p_mw)
    preset = str((element_data or {}).get('q_capability_preset') or '').strip().lower()
    pts = parse_q_capability_points((element_data or {}).get('q_capability_curve_json'))
    use_pcs = preset in BESS_PCS_PRESETS or not pts or (
        preset in ('', 'pcs_circle') and _looks_like_wtg_pf_triangle(pts)
    )
    if use_pcs:
        sn, _p_max = resolve_bess_pcs_ratings(element_data)
        if preset not in BESS_PCS_PRESETS:
            preset = 'pcs_circle'
        q_abs = bess_pcs_q_abs(p_op, sn, preset)
        q_mi, q_ma = -q_abs, q_abs
    else:
        if not pts:
            return None
        style = str((element_data or {}).get('curve_style') or 'straightLineYValues')
        p_vals = [pt['p_mw'] for pt in pts]
        qmin_vals = [pt['q_min_mvar'] for pt in pts]
        qmax_vals = [pt['q_max_mvar'] for pt in pts]
        p_query = p_op if p_vals[0] < -1e-9 else abs(p_op)
        q_mi = interp_q_capability_at_p(p_vals, qmin_vals, p_query, style)
        q_ma = interp_q_capability_at_p(p_vals, qmax_vals, p_query, style)
        if q_mi is None or q_ma is None:
            return None
    if _truthy((element_data or {}).get('q_cap_voltage_dependent')) and v_pu is not None:
        fac = storage_q_voltage_derate(v_pu)
        q_mi = float(q_mi) * fac
        q_ma = float(q_ma) * fac
    return (float(q_mi), float(q_ma))


def storage_q_setpoint_from_curve(element_data, p_mw=None, q_mvar=None, v_pu=None):
    """Apply q_setpoint_mode (capacitive_max / inductive_max) when curve is enabled."""
    lim = interp_storage_pq_limits(element_data, p_mw, v_pu=v_pu)
    if lim is None:
        return q_mvar
    q_mi, q_ma = lim
    mode = str(element_data.get('q_setpoint_mode') or 'manual').strip().lower()
    if mode == 'capacitive_max':
        return q_ma
    if mode == 'inductive_max':
        return q_mi
    return q_mvar


def clip_q_to_storage_curve(element_data, p_mw, q_mvar, v_pu=None):
    """Clip q_mvar into [q_min, q_max] from P–Q curve when enabled."""
    lim = interp_storage_pq_limits(element_data, p_mw, v_pu=v_pu)
    if lim is None:
        return float(q_mvar)
    q_mi, q_ma = lim
    if q_mi > q_ma:
        q_mi, q_ma = q_ma, q_mi
    return float(max(q_mi, min(q_ma, float(q_mvar))))


def resolve_storage_operating_pq(element_data, p_mw, q_mvar, v_pu=None):
    """Clip requested P/Q to the P–Q envelope (optional U-derate) and kVA priority."""
    try:
        sn_mva = float(element_data.get('sn_mva') or 0.0)
    except (TypeError, ValueError):
        sn_mva = 0.0
    q_mvar = clip_q_to_storage_curve(element_data, p_mw, q_mvar, v_pu=v_pu)
    return apply_storage_kva_priority(
        p_mw, q_mvar, sn_mva, element_data.get('watt_priority'))


def apply_storage_kva_priority(p_mw, q_mvar, sn_mva, watt_priority):
    """
    Enforce kVA circle with P vs Q priority (Electrisim sign: p_mw + charge, q_mvar + absorb).
    watt_priority True: keep |P|, reduce |Q|.
    watt_priority False: keep |Q|, reduce |P|.
    """
    try:
        p = float(p_mw)
        q = float(q_mvar)
        s = float(sn_mva)
    except (TypeError, ValueError):
        return p_mw, q_mvar
    if s <= 0:
        return p, q
    s_app = math.hypot(p, q)
    if s_app <= s + 1e-9:
        return p, q
    if _truthy(watt_priority):
        q_allow = math.sqrt(max(0.0, s * s - p * p))
        if q >= 0:
            q = min(q, q_allow)
        else:
            q = max(q, -q_allow)
        return p, q
    p_allow = math.sqrt(max(0.0, s * s - q * q))
    if p >= 0:
        p = min(p, p_allow)
    else:
        p = max(p, -p_allow)
    return p, q


def resolve_storage_pq(element_data):
    """
    Full Storage P/Q resolution: setpoint mode → curve clip → kVA priority.
    Returns (p_mw, q_mvar, q_min, q_max) where q_min/q_max may be None.
    """
    try:
        p_mw = float(element_data.get('p_mw') or 0.0)
    except (TypeError, ValueError):
        p_mw = 0.0
    try:
        q_mvar = float(element_data.get('q_mvar') or 0.0)
    except (TypeError, ValueError):
        q_mvar = 0.0
    try:
        sn_mva = float(element_data.get('sn_mva') or 0.0)
    except (TypeError, ValueError):
        sn_mva = 0.0

    lim = interp_storage_pq_limits(element_data, p_mw)
    inv_mode = str(element_data.get('inv_control_mode') or 'NONE').strip().upper()
    if inv_mode != 'FIXED_PF':
        q_mvar = storage_q_setpoint_from_curve(element_data, p_mw, q_mvar)
    q_mvar = clip_q_to_storage_curve(element_data, p_mw, q_mvar)
    p_mw, q_mvar = apply_storage_kva_priority(
        p_mw, q_mvar, sn_mva, element_data.get('watt_priority'))

    return p_mw, q_mvar, (lim[0] if lim else None), (lim[1] if lim else None)
