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


def interp_storage_pq_limits(element_data, p_mw=None):
    """
    Interpolate (q_min_mvar, q_max_mvar) at |p_mw| from Storage Q capability curve.
    Returns None if curve disabled or invalid.
    """
    if not _truthy(element_data.get('reactive_capability_curve')):
        return None
    pts = parse_q_capability_points(element_data.get('q_capability_curve_json'))
    if not pts:
        return None
    if p_mw is None:
        try:
            p_mw = float(element_data.get('p_mw') or 0.0)
        except (TypeError, ValueError):
            p_mw = 0.0
    p_abs = abs(float(p_mw))
    style = str(element_data.get('curve_style') or 'straightLineYValues')
    p_vals = [pt['p_mw'] for pt in pts]
    qmin_vals = [pt['q_min_mvar'] for pt in pts]
    qmax_vals = [pt['q_max_mvar'] for pt in pts]
    q_mi = interp_q_capability_at_p(p_vals, qmin_vals, p_abs, style)
    q_ma = interp_q_capability_at_p(p_vals, qmax_vals, p_abs, style)
    if q_mi is None or q_ma is None:
        return None
    return (float(q_mi), float(q_ma))


def storage_q_setpoint_from_curve(element_data, p_mw=None, q_mvar=None):
    """Apply q_setpoint_mode (capacitive_max / inductive_max) when curve is enabled."""
    lim = interp_storage_pq_limits(element_data, p_mw)
    if lim is None:
        return q_mvar
    q_mi, q_ma = lim
    mode = str(element_data.get('q_setpoint_mode') or 'manual').strip().lower()
    if mode == 'capacitive_max':
        return q_ma
    if mode == 'inductive_max':
        return q_mi
    return q_mvar


def clip_q_to_storage_curve(element_data, p_mw, q_mvar):
    """Clip q_mvar into [q_min, q_max] from P–Q curve when enabled."""
    lim = interp_storage_pq_limits(element_data, p_mw)
    if lim is None:
        return float(q_mvar)
    q_mi, q_ma = lim
    if q_mi > q_ma:
        q_mi, q_ma = q_ma, q_mi
    return float(max(q_mi, min(q_ma, float(q_mvar))))


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
