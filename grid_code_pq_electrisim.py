# -*- coding: utf-8 -*-
"""
Grid Code Compliance (P-Q) at the point of connection.

Pandapower study that sweeps plant P and finds feasible Qmin/Qmax.
Q is reduced stepwise by a fraction of Pn until loading/voltage limits are met
or Q = 0. With park control on, plant Q is dispatched through ParkController
(BinarySearchControl, constant Q at the point of connection); otherwise each
sgen gets a local Q setpoint.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
import json
import math
import os
import sys
import threading
import time
import traceback

import numpy as np
import pandas as pd
import pandapower as pp

import pandapower_electrisim as pp_el
from storage_q_capability import interp_storage_pq_limits


class GridCodePqCancelled(Exception):
    """Raised when the user stops the P-Q study from the UI."""


def _pq_bool(v, default=False):
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    return str(v).strip().lower() in ('1', 'true', 'yes', 'on')


def _pq_float(v, default=0.0):
    try:
        if v is None or v == '':
            return float(default)
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _pq_cosphi(p_mw, q_mvar):
    denom = math.sqrt(float(p_mw) ** 2 + float(q_mvar) ** 2)
    if denom <= 1e-12:
        return 1.0
    return float(p_mw) / denom


def _pq_pcc_p(net_pf, pcc_bus_idx, ext_grid_idx):
    """
    Net active power (MW) at the PCC, same bus / sign convention as
    ``_rpc_pcc_q_for_chart``. Grid-code P-Q envelopes are defined at the
    connection point, so the red chart uses this value (not dispatched
    generator P). Losses in collector feeders and transformers make
    |P_PCC| smaller than plant P.
    """
    p_raw = float(net_pf.res_bus.at[pcc_bus_idx, 'p_mw'])
    try:
        if ext_grid_idx is not None and not net_pf.ext_grid.empty:
            eg_bus = int(net_pf.ext_grid.at[ext_grid_idx, 'bus'])
            if int(pcc_bus_idx) == eg_bus:
                return p_raw
    except Exception:
        pass
    return -p_raw


def _pq_pcc_plot_from_net(net, ctx, sign_out):
    """Chart-axis P at the PCC from a solved net, or None if unavailable."""
    if net is None:
        return None
    try:
        return float(sign_out) * float(_pq_pcc_p(net, ctx['pcc_bus_idx'], ctx['ext_grid_idx']))
    except Exception:
        return None


def _pq_interp_q_in_span(p_target, p_list, q_list, p_tol=1e-3):
    """
    Interpolate Q at p_target using finite (p, q) pairs.
    Returns None if p_target lies outside the measured P span (no
    extrapolation — a requirement at Pn is not met if the plant only
    delivers P_PCC < Pn).
    """
    pairs = []
    for p, q in zip(p_list or [], q_list or []):
        if q is None:
            continue
        try:
            pairs.append((float(p), float(q)))
        except (TypeError, ValueError):
            continue
    if not pairs:
        return None
    pairs.sort(key=lambda t: t[0])
    px = [t[0] for t in pairs]
    qy = [t[1] for t in pairs]
    pt = float(p_target)
    lo, hi = px[0], px[-1]
    if pt < lo - p_tol or pt > hi + p_tol:
        return None
    if len(px) == 1:
        return float(qy[0])
    pt_clip = min(max(pt, lo), hi)
    return float(np.interp(pt_clip, np.array(px, dtype=float), np.array(qy, dtype=float)))


def _pq_max_abs_p(arr):
    best = None
    for p in arr or []:
        try:
            a = abs(float(p))
        except (TypeError, ValueError):
            continue
        if best is None or a > best:
            best = a
    return best


def _pq_pmax_pcc_for_req(curve):
    """
    Grid-code Pmax at the PCC: the highest |P| that both Qmax and Qmin
    branches reach, so the required P = 1.0 p.u. point lies on the red
    envelope. Templates are Q/Pmax; this value replaces generator Pn.
    """
    a = _pq_max_abs_p(curve.get('p_max_mw') or curve.get('p_mw'))
    b = _pq_max_abs_p(curve.get('p_min_mw') or curve.get('p_mw'))
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)


def _pq_scale_requirement(req, k):
    """Scale a MW/Mvar requirement envelope by k (Pmax_PCC / Pn)."""
    if not req or not (k > 0):
        return req

    def _s(xs):
        out = []
        for x in xs or []:
            if x is None:
                out.append(None)
                continue
            try:
                out.append(round(float(x) * float(k), 4))
            except (TypeError, ValueError):
                out.append(x)
        return out

    out = {
        'p_mw': _s(req.get('p_mw')),
        'q_req_max_mvar': _s(req.get('q_req_max_mvar')),
        'q_req_min_mvar': _s(req.get('q_req_min_mvar')),
    }
    for key in ('pf', 'q_over_pn', 'label'):
        if key in req:
            out[key] = req[key]
    return out


def _pq_fmt(v, digits=2):
    if v is None:
        return 'n/a'
    try:
        return f'{float(v):.{digits}f}'
    except (TypeError, ValueError):
        return 'n/a'


def _pq_check_cancel(ctx):
    ev = (ctx or {}).get('cancel_event')
    if ev is not None and getattr(ev, 'is_set', lambda: False)():
        raise GridCodePqCancelled('Stopped by user')


def _pq_emit(msg, ctx=None, progress=False):
    """Always print to the backend console. Optionally also update the UI progress overlay."""
    _pq_check_cancel(ctx)
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        # Windows consoles default to a legacy code page, so drop characters
        # the console cannot represent rather than aborting the study.
        enc = getattr(sys.stdout, 'encoding', None) or 'ascii'
        print(str(msg).encode(enc, 'replace').decode(enc, 'replace'), flush=True)
    if not progress:
        return
    cb = None
    if ctx:
        cb = ctx.get('progress_cb')
    if cb:
        try:
            cb(str(msg).strip())
        except GridCodePqCancelled:
            raise
        except Exception:
            pass


def _pq_sgen_q_sum(net, gen_info):
    s = 0.0
    for g in gen_info:
        idx = g['idx']
        storage = g.get('type') == 'storage'
        res_tbl = getattr(net, 'res_storage' if storage else 'res_sgen', None)
        el_tbl = getattr(net, 'storage' if storage else 'sgen', None)
        try:
            if res_tbl is not None and not res_tbl.empty and idx in res_tbl.index:
                s += float(res_tbl.at[idx, 'q_mvar'])
            elif el_tbl is not None and idx in el_tbl.index:
                s += float(el_tbl.at[idx, 'q_mvar'] or 0.0)
        except Exception:
            continue
    return s


def _pq_ext_grid_pq(net, ext_grid_idx):
    try:
        if ext_grid_idx is None or not hasattr(net, 'res_ext_grid') or net.res_ext_grid is None:
            return None, None
        if ext_grid_idx not in net.res_ext_grid.index:
            return None, None
        return (
            float(net.res_ext_grid.at[ext_grid_idx, 'p_mw']),
            float(net.res_ext_grid.at[ext_grid_idx, 'q_mvar']),
        )
    except Exception:
        return None, None


def _pq_vm(net, bus_idx):
    try:
        return float(net.res_bus.at[bus_idx, 'vm_pu'])
    except Exception:
        return None


def _pq_tap_records(net):
    """Per-transformer tap state judged against the configured (not pinned) band."""
    recs = []
    ufn = getattr(net, 'user_friendly_names', None) or {}
    bands = getattr(net, '_pq_tap_bands_original', None) or {}

    def _one(element, table, spec):
        if spec is None or len(spec) < 4 or table is None or table.empty:
            return
        idx, side = spec[0], str(spec[1])
        try:
            name = str(table.at[idx, 'name'])
            pos = float(table.at[idx, 'tap_pos'])
            tmin = float(table.at[idx, 'tap_min'])
            tmax = float(table.at[idx, 'tap_max'])
            step_pct = abs(float(table.at[idx, 'tap_step_percent'] or 0.0))
            if element == 'trafo3w':
                bus_col = {'hv': 'hv_bus', 'mv': 'mv_bus', 'lv': 'lv_bus'}.get(side, 'lv_bus')
            else:
                bus_col = 'lv_bus' if side == 'lv' else 'hv_bus'
            vm = float(net.res_bus.at[int(table.at[idx, bus_col]), 'vm_pu'])
        except Exception:
            return
        lo, hi = bands.get(_pq_tap_band_key(element, idx), (float(spec[2]), float(spec[3])))
        if hi < lo:
            lo, hi = hi, lo
        if vm > hi + 1e-4:
            dev = vm - hi
        elif vm < lo - 1e-4:
            dev = vm - lo
        else:
            dev = 0.0
        at_limit = None
        if pos >= tmax - 1e-9:
            at_limit = 'max'
        elif pos <= tmin + 1e-9:
            at_limit = 'min'
        recs.append({
            'name': str(ufn.get(name, name)),
            'control_side': side,
            'tap_pos': pos,
            'tap_min': tmin,
            'tap_max': tmax,
            'tap_step_percent': step_pct,
            'vm_pu': vm,
            'vm_lower_pu': lo,
            'vm_upper_pu': hi,
            'deviation_pu': dev,
            'in_limits': dev == 0.0,
            'at_limit': at_limit,
            'band_narrower_than_step': (hi - lo) < (step_pct / 100.0) - 1e-9,
        })

    for spec in getattr(net, 'trafo_discrete_tap_controllers', None) or []:
        _one('trafo', getattr(net, 'trafo', None), spec)
    for spec in getattr(net, 'trafo3w_discrete_tap_controllers', None) or []:
        _one('trafo3w', getattr(net, 'trafo3w', None), spec)
    return recs


def _pq_tap_status(net, recs=None):
    bits = []
    for rec in (recs if recs is not None else _pq_tap_records(net)):
        note = 'OK'
        if not rec['in_limits']:
            note = 'OUT (tap at limit)' if rec['at_limit'] else 'OUT'
        bits.append(
            f'{rec["name"]} tap_pos={rec["tap_pos"]:.0f} '
            f'[{rec["tap_min"]:.0f}…{rec["tap_max"]:.0f}] '
            f'U_{rec["control_side"]}={rec["vm_pu"]:.4f} pu '
            f'band=[{rec["vm_lower_pu"]:.4f}…{rec["vm_upper_pu"]:.4f}] {note}'
        )
    return bits


def _pq_update_tap_health(ctx, recs, p_val, bound, direction):
    """Accumulate, per transformer, how often tap control failed to hold its band."""
    health = (ctx or {}).get('tap_health')
    if not health or not recs:
        return
    health['points'] += 1
    any_out = False
    for rec in recs:
        entry = health['by_trafo'].setdefault(rec['name'], {
            'name': rec['name'],
            'control_side': rec['control_side'],
            'vm_lower_pu': rec['vm_lower_pu'],
            'vm_upper_pu': rec['vm_upper_pu'],
            'tap_min': rec['tap_min'],
            'tap_max': rec['tap_max'],
            'tap_step_percent': rec['tap_step_percent'],
            'band_narrower_than_step': rec['band_narrower_than_step'],
            'points': 0,
            'out_points': 0,
            'at_limit_points': 0,
            'worst_vm_pu': None,
            'worst_deviation_pu': 0.0,
            'worst_p_mw': None,
            'worst_case': None,
        })
        entry['points'] += 1
        if rec['in_limits']:
            continue
        any_out = True
        entry['out_points'] += 1
        if rec['at_limit']:
            entry['at_limit_points'] += 1
        if abs(rec['deviation_pu']) > abs(entry['worst_deviation_pu']):
            entry['worst_deviation_pu'] = rec['deviation_pu']
            entry['worst_vm_pu'] = rec['vm_pu']
            entry['worst_p_mw'] = p_val
            entry['worst_case'] = f'Q_{direction} at tap={bound or "fixed"}'
    if any_out:
        health['out_points'] += 1


def _pq_tap_health_warnings(health):
    msgs = []
    for entry in (health or {}).get('by_trafo', {}).values():
        if not entry.get('out_points'):
            continue
        msg = (
            f'Transformer tap control: {entry["name"]} could not keep the '
            f'{entry["control_side"]} bus voltage inside its band '
            f'{entry["vm_lower_pu"]:.3f}-{entry["vm_upper_pu"]:.3f} pu at '
            f'{entry["out_points"]} of {entry["points"]} evaluated envelope points'
        )
        if entry.get('worst_vm_pu') is not None:
            msg += (
                f'; worst {entry["worst_vm_pu"]:.3f} pu '
                f'({entry["worst_deviation_pu"]:+.3f} pu outside the band) at '
                f'P = {entry["worst_p_mw"]:.2f} MW, {entry["worst_case"]}'
            )
        if entry.get('at_limit_points'):
            msg += (
                f'; the tap was already at an end position '
                f'[{entry["tap_min"]:.0f}...{entry["tap_max"]:.0f}] at '
                f'{entry["at_limit_points"]} of those points'
            )
        msgs.append(
            msg + '. Those envelope points are reachable in reactive power but not '
                  'voltage-regulated, so treat them as indicative only.'
        )
        step_pu = float(entry.get('tap_step_percent') or 0.0) / 100.0
        if entry.get('band_narrower_than_step') and step_pu > 0.0:
            width = entry['vm_upper_pu'] - entry['vm_lower_pu']
            msgs.append(
                f'Transformer tap control: {entry["name"]} band '
                f'{entry["vm_lower_pu"]:.3f}-{entry["vm_upper_pu"]:.3f} pu is {width:.3f} pu wide, '
                f'narrower than one tap step ({entry["tap_step_percent"]:.2f}% = {step_pu:.3f} pu). '
                f'A discrete tap changer overshoots such a band and can never settle inside it. '
                f'Widen vm_lower_pu/vm_upper_pu to at least {1.2 * step_pu:.3f} pu, or use a '
                f'transformer with a smaller tap_step_percent.'
            )
    return msgs


def _pq_q_unphysical(q_pcc, q_cap, direction, ctx):
    """True when measured PCC Q cannot be a plant Qmax/Qmin (slack/tap artefact)."""
    if q_pcc is None:
        return False
    try:
        q = float(q_pcc)
        cap = abs(float(q_cap or 0.0))
    except (TypeError, ValueError):
        return True
    pn = abs(float((ctx or {}).get('pn_mw') or 0.0))
    limit = max(8.0 * max(cap, 1.0), 5.0 * max(pn, 1.0), 30.0)
    if abs(q) > limit:
        return True
    if direction == 'max' and q < -max(8.0, 0.75 * max(cap, 1.0)):
        return True
    if direction == 'min' and q > max(8.0, 0.75 * max(cap, 1.0)):
        return True
    return False


def _pq_fill_diag(r, ctx):
    if not r or r.get('net') is None:
        return r
    net = r['net']
    r['q_sgen'] = _pq_sgen_q_sum(net, ctx['gen_info'])
    r['p_ext'], r['q_ext'] = _pq_ext_grid_pq(net, ctx['ext_grid_idx'])
    r['vm_pcc'] = _pq_vm(net, ctx['pcc_bus_idx'])
    r['tap_recs'] = _pq_tap_records(net)
    r['taps'] = _pq_tap_status(net, r['tap_recs'])
    try:
        r['q_bus_raw'] = float(net.res_bus.at[ctx['pcc_bus_idx'], 'q_mvar'])
    except Exception:
        r['q_bus_raw'] = None
    return r


def _pq_log_trial(ctx, p_val, bound, direction, r, x, q_cap, stage):
    bound_s = bound or 'fixed'
    if r is None:
        _pq_emit(
            f'    P={p_val:.2f} MW tap={bound_s} Q_{direction} {stage}: no result  '
            f'set={_pq_fmt(x)} cap={_pq_fmt(q_cap)} LF={ctx["iLDF"][0]}',
            ctx, progress=True)
        return
    flags = []
    if not r.get('converged'):
        flags.append(str(r.get('pf_stage') or 'div'))
    elif r.get('pf_stage'):
        flags.append(str(r['pf_stage']))
    if r.get('unphysical'):
        flags.append('UNPHYSICAL')
    if r.get('overloaded'):
        flags.append('overload')
    if r.get('volt_viol'):
        flags.append('volt')
    flag_s = f'  [{", ".join(flags)}]' if flags else ''
    _pq_emit(
        f'    P={p_val:.2f} MW tap={bound_s} Q_{direction} {stage}: '
        f'PCC Q={_pq_fmt(r.get("q_pcc"))} Mvar  set={_pq_fmt(x)}  cap={_pq_fmt(q_cap)}  '
        f'sgen Q={_pq_fmt(r.get("q_sgen"))}  ext Q={_pq_fmt(r.get("q_ext"))}  '
        f'bus Q_raw={_pq_fmt(r.get("q_bus_raw"))}  U_pcc={_pq_fmt(r.get("vm_pcc"), 4)} pu  '
        f'LF={ctx["iLDF"][0]}{flag_s}',
        ctx, progress=True)
    for t in (r.get('taps') or []):
        _pq_emit(f'      {t}', ctx, progress=False)


def _pq_match_park(park, name, id_):
    if not isinstance(park, dict):
        return False
    if name and str(park.get('name') or '') == str(name):
        return True
    if id_ is not None and str(park.get('id') or '') == str(id_):
        return True
    return False


def _pq_filter_in_data(in_data, selected_name, selected_id, q_set=None, force_const_q=False, pcc_bus_name=None):
    """Keep only the selected park (or none). Optionally force Const. Q setpoint."""
    out = {}
    if not isinstance(in_data, dict):
        return out
    for k, el in in_data.items():
        if not isinstance(el, dict):
            out[k] = el
            continue
        typ = str(el.get('typ') or '')
        if typ == 'ParkController' or typ.startswith('ParkController'):
            if not selected_name and selected_id is None:
                continue
            if not _pq_match_park(el, selected_name, selected_id):
                continue
            park = dict(el)
            park['enabled'] = True
            if force_const_q:
                park['control_mode'] = 'Reactive Power Control'
                park['q_control_type'] = 'Const. Q'
                if q_set is not None:
                    park['q_set_mvar'] = float(q_set)
                if not str(park.get('control_q_at') or '').strip() and pcc_bus_name:
                    park['control_q_at'] = pcc_bus_name
            out[k] = park
        else:
            out[k] = el
    return out


def _pq_tap_band_key(element, idx):
    return f'{element}:{idx}'


def _pq_tap_table(net, element):
    return getattr(net, 'trafo3w' if element == 'trafo3w' else 'trafo', None)


def _pq_tap_step_pu(net, element, idx):
    """One tap step expressed in p.u. voltage (tap_step_percent / 100)."""
    table = _pq_tap_table(net, element)
    try:
        return abs(float(table.at[idx, 'tap_step_percent'] or 0.0)) / 100.0
    except Exception:
        return 0.0


def _pq_capture_tap_bands(net):
    """Remember each transformer's configured band before worst-case pinning rewrites it."""
    bands = getattr(net, '_pq_tap_bands_original', None)
    if bands:
        return bands
    bands = {}
    for element, attr in (('trafo', 'trafo_discrete_tap_controllers'),
                          ('trafo3w', 'trafo3w_discrete_tap_controllers')):
        for row in getattr(net, attr, None) or []:
            if not row or len(row) < 4:
                continue
            lo, hi = float(row[2]), float(row[3])
            if hi < lo:
                lo, hi = hi, lo
            bands[_pq_tap_band_key(element, row[0])] = (lo, hi)
    net._pq_tap_bands_original = bands
    return bands


def _pq_apply_tap_family_filter(net, ctx):
    """Drop DiscreteTap specs for transformer families that are not enabled this run."""
    if not (ctx or {}).get('rc2'):
        net.trafo_discrete_tap_controllers = []
    if not (ctx or {}).get('rc3'):
        net.trafo3w_discrete_tap_controllers = []


def _pq_pin_taps(net, bound, band_pu=0.005):
    """Bias DiscreteTapControl toward the lower or upper voltage setpoint.

    DiscreteTapControl hunts if vm_lower == vm_upper (no deadband). That fails
    the controlled load flow and forces a long Q-step walk toward zero.
    Keep a band the tap can actually reach at the chosen extreme.
    """
    bands = _pq_capture_tap_bands(net)

    def _pin(element, lst):
        pinned = []
        for row in lst or []:
            if not row or len(row) < 4:
                continue
            idx, side = row[0], row[1]
            lo, hi = bands.get(_pq_tap_band_key(element, idx), (float(row[2]), float(row[3])))
            if hi < lo:
                lo, hi = hi, lo
            # A discrete tap cannot settle inside a deadband narrower than one tap step:
            # it overshoots, hunts, and the controlled load flow fails to converge.
            dead = max(float(band_pu), 1e-4, 1.3 * _pq_tap_step_pu(net, element, idx))
            if (hi - lo) >= dead:
                if bound == 'lower':
                    vm_lo, vm_hi = lo, lo + dead
                else:
                    vm_lo, vm_hi = hi - dead, hi
            else:
                # Configured band is itself narrower than one tap step, so neither
                # extreme is reachable. Aim at the band centre for both bounds.
                mid = 0.5 * (lo + hi)
                vm_lo, vm_hi = mid - 0.5 * dead, mid + 0.5 * dead
            pinned.append((idx, side, vm_lo, vm_hi))
        return pinned

    if bound not in ('lower', 'upper'):
        return
    net.trafo_discrete_tap_controllers = _pin(
        'trafo', getattr(net, 'trafo_discrete_tap_controllers', None))
    net.trafo3w_discrete_tap_controllers = _pin(
        'trafo3w', getattr(net, 'trafo3w_discrete_tap_controllers', None))


def _pq_shunt_is_selected(net, idx, selected):
    """True when this shunt was ticked under Additional shunts."""
    if not selected:
        return False
    name = str(net.shunt.at[idx, 'name']) if 'name' in net.shunt.columns else ''
    if name in selected or str(idx) in selected:
        return True
    if 'id' in net.shunt.columns and str(net.shunt.at[idx, 'id']) in selected:
        return True
    friendly = str((getattr(net, 'user_friendly_names', None) or {}).get(name, '') or '')
    return bool(friendly) and friendly in selected


def _pq_apply_ssc_selection(net, ssc_names, in_data=None):
    """STATCOMs (SSC) not ticked in the P-Q dialog are out of service for this study."""
    df = getattr(net, 'ssc', None)
    if df is None or getattr(df, 'empty', True) or ssc_names is None:
        return []
    selected = {str(n) for n in ssc_names if n not in (None, '')}
    ufn = getattr(net, 'user_friendly_names', None) or {}
    off = []
    for idx in list(df.index):
        name = str(df.at[idx, 'name'])
        sid = str(df.at[idx, 'id']) if 'id' in df.columns else ''
        if name in selected or sid in selected or str(ufn.get(name, '')) in selected:
            continue
        if 'in_service' in df.columns and bool(df.at[idx, 'in_service']):
            df.at[idx, 'in_service'] = False
            off.append(_pq_statcom_display_name(net, idx, in_data, ufn))
    return off


def _pq_apply_shunt_selection(net, shunt_names):
    """Unticked additional shunts do not operate in this P-Q study."""
    if not hasattr(net, 'shunt') or net.shunt is None or getattr(net.shunt, 'empty', True):
        return []
    selected = {str(n) for n in (shunt_names or []) if n not in (None, '')}
    switched_off = []
    off_idx = set()
    for idx in list(net.shunt.index):
        if _pq_shunt_is_selected(net, idx, selected):
            continue
        name = str(net.shunt.at[idx, 'name']) if 'name' in net.shunt.columns else str(idx)
        friendly = str((getattr(net, 'user_friendly_names', None) or {}).get(name, '') or '')
        if 'in_service' in net.shunt.columns:
            net.shunt.at[idx, 'in_service'] = False
        if 'q_mvar' in net.shunt.columns:
            net.shunt.at[idx, 'q_mvar'] = 0.0
        if 'p_mw' in net.shunt.columns:
            net.shunt.at[idx, 'p_mw'] = 0.0
        if 'step' in net.shunt.columns:
            net.shunt.at[idx, 'step'] = 0.0
        off_idx.add(idx)
        switched_off.append(friendly or name)
    if off_idx:
        specs = getattr(net, 'shunt_discrete_controllers', None) or []
        if isinstance(specs, list):
            net.shunt_discrete_controllers = [
                row for row in specs
                if not (isinstance(row, dict) and row.get('shunt_index') in off_idx)
            ]
        pending = getattr(net, '_electrisim_pending_line_flow_shunts', None) or []
        if isinstance(pending, list):
            net._electrisim_pending_line_flow_shunts = [
                row for row in pending
                if not (isinstance(row, dict) and row.get('shunt_index') in off_idx)
            ]
        attached = getattr(net, 'line_flow_shunt_controllers', None) or []
        if isinstance(attached, list):
            net.line_flow_shunt_controllers = [
                row for row in attached
                if not (isinstance(row, dict) and row.get('shunt_index') in off_idx)
            ]
    return switched_off


def _pq_shunt_in_selection(net, idx, shunt_names):
    if not shunt_names:
        return True
    name = str(net.shunt.at[idx, 'name']) if 'name' in net.shunt.columns else ''
    return name in shunt_names or str(idx) in shunt_names


def _pq_reduce_compensation_one_step(net, shunt_names=None, direction='max'):
    """
    Reduce one compensation step toward zero (cut shunt steps before plant Q).
    Prefers selected shunts whose Q has the same sign as the plant Q being tested.
    """
    if not hasattr(net, 'shunt') or net.shunt.empty:
        return False
    names = set(shunt_names or [])
    sign_plant = 1.0 if direction == 'max' else -1.0
    candidates = []
    for idx in net.shunt.index:
        q = 0.0
        if 'q_mvar' in net.shunt.columns:
            try:
                q = float(net.shunt.at[idx, 'q_mvar'] or 0.0)
            except (TypeError, ValueError):
                q = 0.0
        step = 1.0
        if 'step' in net.shunt.columns:
            try:
                step = float(net.shunt.at[idx, 'step'] or 0.0)
            except (TypeError, ValueError):
                step = 1.0
        q_eff = q * (step if abs(step) > 1e-12 else 1.0)
        if step <= 0 and abs(q_eff) < 1e-12:
            continue
        in_sel = _pq_shunt_in_selection(net, idx, names)
        same_sign = (q_eff * sign_plant) > 1e-12
        candidates.append((not in_sel, not same_sign, -abs(q_eff), idx, step, q))
    if not candidates:
        return False
    candidates.sort()
    _, _, _, idx, step, q = candidates[0]
    if 'step' in net.shunt.columns and step > 0:
        net.shunt.at[idx, 'step'] = 0.0 if step < 1.0 else step - 1.0
        return True
    if 'q_mvar' in net.shunt.columns and abs(q) > 1e-12:
        net.shunt.at[idx, 'q_mvar'] = 0.0
        if 'p_mw' in net.shunt.columns:
            net.shunt.at[idx, 'p_mw'] = 0.0
        return True
    return False


def _pq_overloaded(net, max_loading_percent):
    lim = float(max_loading_percent)
    if hasattr(net, 'res_trafo') and net.res_trafo is not None and not net.res_trafo.empty:
        if float(net.res_trafo.loading_percent.max()) > lim:
            return True
    if hasattr(net, 'res_line') and net.res_line is not None and not net.res_line.empty:
        if float(net.res_line.loading_percent.max()) > lim:
            return True
    if hasattr(net, 'res_trafo3w') and net.res_trafo3w is not None and not net.res_trafo3w.empty:
        if 'loading_percent' in net.res_trafo3w.columns:
            if float(net.res_trafo3w.loading_percent.max()) > lim:
                return True
    return False


def _pq_voltage_violation(net, gen_info, u_min, u_max):
    if not hasattr(net, 'res_bus') or net.res_bus.empty:
        return False
    for g in gen_info:
        try:
            bus = _pq_gen_bus(net, g)
            vm = float(net.res_bus.at[bus, 'vm_pu'])
        except Exception:
            continue
        if vm > float(u_max) + 1e-9 or vm < float(u_min) - 1e-9:
            return True
    return False


def _pq_storage_q_caps(net, storage_idx, p_gen, sn_mva, q_mode, element_data=None):
    """Q caps for Storage (Electrisim sign: p_gen is plant P at POC scale, map to storage p)."""
    if element_data and _pq_bool(element_data.get('reactive_capability_curve')):
        lim = interp_storage_pq_limits(element_data, p_gen)
        if lim is not None:
            q_mi, q_ma = lim
            return max(0.0, float(q_ma)), max(0.0, float(-q_mi))
    if q_mode == 'from_rating' and sn_mva > 0:
        fr = math.sqrt(max(sn_mva ** 2 - abs(p_gen) ** 2, 0))
        return fr, fr
    half = sn_mva * 0.5 if sn_mva > 0 else 0.0
    return half, half


def _pq_storage_element_data(in_data, storage_name):
    if not in_data:
        return {}
    for el in in_data.values():
        if isinstance(el, dict) and str(el.get('typ', '')).startswith('Storage') and str(el.get('name')) == str(storage_name):
            return el
    return {}


def _pq_gen_bus(net, g):
    """Bus index of a gen_info entry, which may be an sgen or a storage unit."""
    tbl = net.storage if g.get('type') == 'storage' else net.sgen
    return int(tbl.at[g['idx'], 'bus'])


def _pq_gen_p(net, g):
    """Current P of a gen_info entry in generator convention (positive = into
    the grid). Electrisim storage stores the opposite sign."""
    if g.get('type') == 'storage':
        val = net.storage.at[g['idx'], 'p_mw']
        return 0.0 if pd.isna(val) else -float(val)
    val = net.sgen.at[g['idx'], 'p_mw']
    return 0.0 if pd.isna(val) else float(val)


def _pq_set_gen_pq(net, g, p_gen, q_mvar):
    """p_gen and q_mvar are in generator convention (positive = injected into
    the grid). Electrisim storage uses p_mw > 0 for charging and q_mvar > 0 for
    absorbing, so both are inverted for storage units."""
    if g.get('type') == 'storage':
        net.storage.at[g['idx'], 'p_mw'] = -float(p_gen)
        net.storage.at[g['idx'], 'q_mvar'] = -float(q_mvar)
    else:
        net.sgen.at[g['idx'], 'p_mw'] = float(p_gen)
        net.sgen.at[g['idx'], 'q_mvar'] = float(q_mvar)


def _pq_dispatch_p(net, gen_info, p_val, exclude_names):
    """Scale P across selected sgens or storage; excluded units keep diagram P."""
    exclude = set(exclude_names or [])
    scale = [g for g in gen_info if g.get('name') not in exclude]
    total = sum(float(g['p_rated_mw']) for g in scale) or 0.0
    for g in gen_info:
        idx = g['idx']
        if g.get('name') in exclude:
            continue
        if total <= 0:
            p_set = 0.0
        else:
            share = float(g['p_rated_mw']) / total
            p_set = float(p_val) * share
        if g.get('type') == 'storage':
            # POC export (+) → storage discharge (p_mw < 0)
            net.storage.at[idx, 'p_mw'] = -p_set
        else:
            net.sgen.at[idx, 'p_mw'] = p_set


def _pq_plant_q_caps(net, gen_info, p_val, q_mode, exclude_names, in_data=None):
    """Plant Qmax / Qmin magnitudes at this P (positive numbers)."""
    exclude = set(exclude_names or [])
    scale = [g for g in gen_info if g.get('name') not in exclude]
    total = sum(float(g['p_rated_mw']) for g in scale) or 0.0
    q_pos = 0.0
    q_neg = 0.0
    for g in gen_info:
        if g.get('name') in exclude:
            p_gen = _pq_gen_p(net, g)
        elif total <= 0:
            p_gen = 0.0
        else:
            p_gen = float(p_val) * (float(g['p_rated_mw']) / total)
        if g.get('type') == 'storage':
            el = _pq_storage_element_data(in_data, g.get('name'))
            qp, qn = _pq_storage_q_caps(net, g['idx'], abs(p_gen), g['sn_mva'], q_mode, el)
        else:
            qp, qn = pp_el._rpc_sgen_q_caps(net, g['idx'], p_gen, g['sn_mva'], q_mode)
        q_pos += float(qp)
        q_neg += float(qn)
    return q_pos, q_neg


def _pq_clear_controllers(net):
    try:
        if hasattr(net, 'controller') and net.controller is not None and not net.controller.empty:
            net.controller.drop(list(net.controller.index), inplace=True)
    except Exception:
        pass


def _pq_set_controller_in_service(net, tap=None, park=None):
    if not hasattr(net, 'controller') or net.controller is None or net.controller.empty:
        return
    for ci in net.controller.index:
        obj = net.controller.at[ci, 'object']
        name = type(obj).__name__
        is_tap = name in ('DiscreteTapControl', 'ContinuousTapControl')
        is_park = name in ('BinarySearchControl', 'ParkQControl', 'DroopControl', 'PlantSupervisoryControl')
        try:
            if tap is not None and is_tap:
                net.controller.at[ci, 'in_service'] = bool(tap)
            if park is not None and is_park:
                net.controller.at[ci, 'in_service'] = bool(park)
        except Exception:
            continue


def _pq_snapshot_solved(net):
    """Shallow copies of setpoints and result tables so a failed tap pass can be undone."""
    snap = {}
    if hasattr(net, 'trafo') and net.trafo is not None and not net.trafo.empty and 'tap_pos' in net.trafo.columns:
        snap['tap_pos'] = net.trafo['tap_pos'].copy()
    if hasattr(net, 'trafo3w') and net.trafo3w is not None and not net.trafo3w.empty and 'tap_pos' in net.trafo3w.columns:
        snap['tap_pos_3w'] = net.trafo3w['tap_pos'].copy()
    for el in ('sgen', 'storage'):
        tbl = getattr(net, el, None)
        if tbl is None or tbl.empty:
            continue
        if 'p_mw' in tbl.columns:
            snap[f'{el}_p'] = tbl['p_mw'].copy()
        if 'q_mvar' in tbl.columns:
            snap[f'{el}_q'] = tbl['q_mvar'].copy()
    for name in ('res_bus', 'res_sgen', 'res_storage', 'res_gen', 'res_trafo', 'res_trafo3w',
                 'res_line', 'res_ext_grid', 'res_load', 'res_shunt'):
        tbl = getattr(net, name, None)
        if tbl is not None:
            try:
                snap[name] = tbl.copy()
            except Exception:
                pass
    return snap


def _pq_restore_solved(net, snap):
    if not snap:
        return
    if 'tap_pos' in snap and hasattr(net, 'trafo') and not net.trafo.empty:
        net.trafo['tap_pos'] = snap['tap_pos']
    if 'tap_pos_3w' in snap and hasattr(net, 'trafo3w') and not net.trafo3w.empty:
        net.trafo3w['tap_pos'] = snap['tap_pos_3w']
    for el in ('sgen', 'storage'):
        tbl = getattr(net, el, None)
        if tbl is None or tbl.empty:
            continue
        if f'{el}_p' in snap:
            tbl['p_mw'] = snap[f'{el}_p']
        if f'{el}_q' in snap:
            tbl['q_mvar'] = snap[f'{el}_q']
    for name, tbl in snap.items():
        if name.startswith('res_'):
            setattr(net, name, tbl)


def _pq_step_positions(net):
    """Transformer tap positions and shunt steps, to see whether a control pass moved them."""
    out = []
    for table, col in (('trafo', 'tap_pos'), ('trafo3w', 'tap_pos'), ('shunt', 'step')):
        df = getattr(net, table, None)
        if df is None or df.empty or col not in df.columns:
            continue
        out.extend((table, int(i), float(v)) for i, v in df[col].items() if v == v)
    return out


def _pq_tap_positions(net):
    """Transformer tap positions only (shunt steps follow P or voltage on their own)."""
    out = {}
    for table in ('trafo', 'trafo3w'):
        df = getattr(net, table, None)
        if df is None or df.empty or 'tap_pos' not in df.columns:
            continue
        out[table] = {int(i): float(v) for i, v in df['tap_pos'].items() if v == v}
    return out


def _pq_apply_tap_positions(net, positions):
    """Start a trial from tap positions solved at a nearby point (warm start for tap control)."""
    for table, taps in (positions or {}).items():
        df = getattr(net, table, None)
        if df is None or df.empty or 'tap_pos' not in df.columns:
            continue
        for idx, pos in taps.items():
            if idx in df.index:
                df.at[idx, 'tap_pos'] = pos


def _pq_has_psc(net):
    ctrl = getattr(net, 'controller', None)
    if ctrl is None or getattr(ctrl, 'empty', True):
        return False
    try:
        return any(type(o).__name__ == 'PlantSupervisoryControl' and bool(on)
                   for o, on in zip(ctrl['object'], ctrl['in_service']))
    except Exception:
        return False


def _pq_psc_reactors(net, in_data):
    """{shunt index: (steps, {step: Mvar absorbed at 1 p.u.})} of reactors led by a Plant Supervisory Controller."""
    out = {}
    ufn = getattr(net, 'user_friendly_names', {}) or {}
    for psc in pp_el._electrisim_collect_psc_payloads(in_data):
        for r_idx, _name in pp_el._psc_find_rows(getattr(net, 'shunt', None),
                                                 pp_el._park_parse_json_list(psc.get('reactors_json')), ufn):
            steps, qmap = pp_el._psc_reactor_steps(net, r_idx)
            if len(steps) >= 2:
                out[int(r_idx)] = (steps, qmap)
    return out


def _pq_detach_psc(net):
    """Remove the helper sources a Plant Supervisory Controller added for one trial."""
    sgen_of = getattr(net, '_electrisim_ssc_sgen', None) or {}
    drop = [g for g in sgen_of.values() if g in net.sgen.index]
    try:
        if drop:
            net.sgen.drop(index=drop, inplace=True)
            if hasattr(net, 'res_sgen') and net.res_sgen is not None:
                net.res_sgen.drop(index=[g for g in drop if g in net.res_sgen.index], inplace=True, errors='ignore')
    except Exception:
        pass
    for s_idx in sgen_of:
        try:
            net.ssc.at[s_idx, 'in_service'] = True
        except Exception:
            pass
    net._electrisim_ssc_sgen = {}
    net._electrisim_ssc_equiv = {}
    net._electrisim_ssc_info = {}
    net._electrisim_psc_reactors = set()


def _pq_try_runpp(net_pf, init, max_iteration, run_control, q_kw, algorithm='nr', recycle=False):
    runner = pp_el.electrisim_runpp if algorithm == 'nr' else pp.runpp
    extra = {}
    if run_control and _pq_has_psc(net_pf):
        extra['max_iter'] = 80
    if recycle and algorithm == 'nr' and not run_control and getattr(net_pf, '_ppc', None) is not None:
        # Topology is unchanged between P-Q trials. Reuse the admittance matrix
        # and only refresh injections (the time-series path in pandapower).
        extra['recycle'] = {'bus_pq': True, 'trafo': False, 'gen': True}
        extra['check_connectivity'] = False
    try:
        runner(
            net_pf, algorithm=algorithm, calculate_voltage_angles=True,
            init=init, max_iteration=max_iteration,
            run_control=run_control, **q_kw, **extra)
        return True
    except GridCodePqCancelled:
        raise
    except Exception:
        # Retry once without recycling. Only a recycled (cached-matrix) solve is retried:
        # retrying on any extra option (e.g. max_iter) would repeat a failed solve forever.
        if 'recycle' in extra:
            try:
                del net_pf._ppc
            except Exception:
                net_pf._ppc = None
            return _pq_try_runpp(
                net_pf, 'auto', max(int(max_iteration or 40), 40), run_control, q_kw,
                algorithm=algorithm, recycle=False)
        return False


def _pq_has_voltage_seed(net):
    res = getattr(net, 'res_bus', None)
    if res is None or getattr(res, 'empty', True):
        return False
    if 'vm_pu' not in res.columns or 'va_degree' not in res.columns:
        return False
    try:
        return bool(res['vm_pu'].notna().all()) and len(res) == len(net.bus)
    except Exception:
        return False


def _pq_apply_vm_seed(net, seed):
    """Copy a previous voltage solution so the next Newton start is warm."""
    if not seed or not hasattr(net, 'bus') or net.bus is None or net.bus.empty:
        return
    vm, va = seed
    try:
        if list(net.bus.index) != list(vm.index):
            return
        res = getattr(net, 'res_bus', None)
        if res is None or getattr(res, 'empty', True) or len(res) != len(vm):
            net.res_bus = pd.DataFrame(index=net.bus.index)
        net.res_bus['vm_pu'] = vm.to_numpy()
        net.res_bus['va_degree'] = va.to_numpy()
    except Exception:
        return


_PQ_BASELINE_COLUMNS = (
    ('ext_grid', ('vm_pu',)),
    ('sgen', ('p_mw', 'q_mvar')),
    ('storage', ('p_mw', 'q_mvar')),
    ('shunt', ('p_mw', 'q_mvar', 'step')),
    ('trafo', ('tap_pos',)),
    ('trafo3w', ('tap_pos',)),
    ('gen', ('p_mw', 'vm_pu', 'q_mvar')),
)
_PQ_BASELINE_ATTRS = (
    'trafo_discrete_tap_controllers',
    'trafo3w_discrete_tap_controllers',
    'shunt_discrete_controllers',
    'line_flow_shunt_controllers',
)


def _pq_input_baseline(net):
    """Setpoints a trial changes, so the same net can be reused instead of copied."""
    tables = {}
    for name, cols in _PQ_BASELINE_COLUMNS:
        df = getattr(net, name, None)
        if df is None or getattr(df, 'empty', True):
            continue
        saved = {}
        for col in cols:
            if col in df.columns:
                saved[col] = df[col].copy()
        if saved:
            tables[name] = saved
    attrs = {}
    for name in _PQ_BASELINE_ATTRS:
        val = getattr(net, name, None)
        if isinstance(val, list):
            attrs[name] = list(val)
    return {'tables': tables, 'attrs': attrs}


def _pq_restore_baseline(net, baseline):
    if not baseline:
        return
    for name, cols in (baseline.get('tables') or {}).items():
        df = getattr(net, name, None)
        if df is None:
            continue
        for col, series in cols.items():
            try:
                df[col] = series.copy()
            except Exception:
                pass
    for name, val in (baseline.get('attrs') or {}).items():
        setattr(net, name, list(val))


def _pq_acquire_work_net(ctx, base_net):
    """One copied network per voltage. Later trials restore setpoints onto it."""
    if ctx.get('_work_net') is None:
        ctx['_work_net'] = deepcopy(base_net)
        ctx['_work_baseline'] = _pq_input_baseline(ctx['_work_net'])
    else:
        _pq_restore_baseline(ctx['_work_net'], ctx.get('_work_baseline'))
    return ctx['_work_net']


def _pq_capture_vm_seed(net):
    try:
        res = net.res_bus
        if res is None or res.empty:
            return None
        return (res['vm_pu'].copy(), res['va_degree'].copy())
    except Exception:
        return None


def _pq_try_inits(net_pf, q_kw, inits, max_iteration):
    for init in inits:
        if _pq_try_runpp(net_pf, init, max_iteration, True, q_kw):
            return True
    return False


def _pq_run_pf(net_pf, verbose_iwamoto=False, rc2=False, rc3=False, rcs=False, force_control=False,
              cancel_event=None):
    """Power flow with optional tap/shunt controllers; force_control for Park BinarySearchControl.

    DiscreteTapControl and BinarySearchControl often fail if both are active in one runpp.
    Apply park Q first. Then try to retap. If the tap pass diverges it used to discard the
    whole trial (PCC Q = n/a) even though park Q had already solved — that collapsed the
    envelope (e.g. 7.33 Mvar → 0.92 Mvar). Keep the park solution when retap fails.
    """
    import io

    if cancel_event is not None and getattr(cancel_event, 'is_set', lambda: False)():
        raise GridCodePqCancelled('Stopped by user')

    q_kw = pp_el._electrisim_enforce_q_lims_kw(net_pf)
    tc2 = getattr(net_pf, 'trafo_discrete_tap_controllers', None) or []
    tc3 = getattr(net_pf, 'trafo3w_discrete_tap_controllers', None) or []
    shc = getattr(net_pf, 'shunt_discrete_controllers', None) or []
    lfc = getattr(net_pf, 'line_flow_shunt_controllers', None) or []
    attach_2w = bool(rc2) and bool(tc2)
    attach_3w = bool(rc3) and bool(tc3)
    attach_sh = bool(rcs) and bool(shc)
    attach_lf = bool(rcs) and bool(lfc)
    if attach_2w or attach_3w:
        pp_el._electrisim_attach_discrete_tap_controllers(net_pf, attach_trafo=attach_2w, attach_trafo3w=attach_3w)
    if attach_sh:
        pp_el._electrisim_attach_discrete_shunt_controllers(net_pf)
    if attach_lf:
        pp_el._electrisim_attach_line_flow_shunt_controllers(net_pf)
    has_tap = attach_2w or attach_3w
    has_park = bool(force_control)
    rc = has_park or has_tap or attach_sh or attach_lf
    inits = ('results', 'auto', 'flat') if _pq_has_voltage_seed(net_pf) else ('auto', 'flat')
    net_pf._pq_pf_stage = None

    if has_tap and has_park:
        _pq_set_controller_in_service(net_pf, tap=False, park=True)
        park_ok = _pq_try_inits(net_pf, q_kw, inits, 100)
        if not park_ok:
            _pq_set_controller_in_service(net_pf, tap=True, park=False)
            if not _pq_try_inits(net_pf, q_kw, inits, 80):
                net_pf._pq_pf_stage = 'div:tap_warmup'
                return False
            _pq_set_controller_in_service(net_pf, tap=False, park=True)
            park_ok = _pq_try_inits(net_pf, q_kw, inits, 100)
        if not park_ok:
            net_pf._pq_pf_stage = 'div:park'
            return False

        snap = _pq_snapshot_solved(net_pf)
        _pq_set_controller_in_service(net_pf, tap=True, park=False)
        tap_ok = _pq_try_runpp(net_pf, 'results', 80, True, q_kw)
        if not tap_ok:
            _pq_restore_solved(net_pf, snap)
            _pq_set_controller_in_service(net_pf, tap=False, park=False)
            net_pf._pq_pf_stage = 'park_only'
            return True
        # A tap move after the park pass shifts plant Q away from the park setpoint.
        # Alternate park and tap passes until the taps stop moving, so the kept
        # operating point meets the park setpoint with taps inside their band.
        stage = 'park+tap'
        for _round in range(4):
            taps_before = _pq_step_positions(net_pf)
            _pq_set_controller_in_service(net_pf, tap=False, park=True)
            snap = _pq_snapshot_solved(net_pf)
            if not _pq_try_runpp(net_pf, 'results', 100, True, q_kw):
                _pq_restore_solved(net_pf, snap)
                stage = 'park+tap (park re-run failed)'
                break
            _pq_set_controller_in_service(net_pf, tap=True, park=False)
            snap = _pq_snapshot_solved(net_pf)
            if not _pq_try_runpp(net_pf, 'results', 80, True, q_kw):
                _pq_restore_solved(net_pf, snap)
                stage = 'park+tap (retap failed, park setpoint kept)'
                break
            if _pq_step_positions(net_pf) == taps_before:
                break
        else:
            # Taps still moving: finish on the park setpoint.
            _pq_set_controller_in_service(net_pf, tap=False, park=True)
            snap = _pq_snapshot_solved(net_pf)
            if not _pq_try_runpp(net_pf, 'results', 100, True, q_kw):
                _pq_restore_solved(net_pf, snap)
            stage = 'park+tap (taps still moving)'
        _pq_set_controller_in_service(net_pf, tap=False, park=False)
        net_pf._pq_pf_stage = stage
        return True

    if rc:
        ok = _pq_try_inits(net_pf, q_kw, inits, 100)
        net_pf._pq_pf_stage = 'ctrl' if ok else 'div:ctrl'
        return ok

    strategies = []
    if _pq_has_voltage_seed(net_pf):
        strategies.append({'algorithm': 'nr', 'init': 'results', 'max_iteration': 20})
    strategies.extend([
        {'algorithm': 'nr', 'init': 'auto', 'max_iteration': 40},
        {'algorithm': 'nr', 'init': 'flat', 'max_iteration': 60},
        {'algorithm': 'iwamoto_nr', 'init': 'flat', 'max_iteration': 40},
    ])
    for s in strategies:
        algo = s['algorithm']
        try:
            if algo == 'nr':
                if _pq_try_runpp(
                        net_pf, s['init'], s['max_iteration'], False, q_kw, algorithm='nr',
                        recycle=(s['init'] == 'results')):
                    return True
                continue
            if algo == 'iwamoto_nr' and not verbose_iwamoto:
                buf = io.StringIO()
                old_out, old_err = sys.stdout, sys.stderr
                sys.stdout = sys.stderr = buf
                try:
                    pp.runpp(
                        net_pf, algorithm=algo, calculate_voltage_angles=True,
                        init=s['init'], max_iteration=s['max_iteration'],
                        run_control=False, **q_kw)
                finally:
                    sys.stdout = old_out
                    sys.stderr = old_err
            else:
                pp.runpp(
                    net_pf, algorithm=algo, calculate_voltage_angles=True,
                    init=s['init'], max_iteration=s['max_iteration'],
                    run_control=False, **q_kw)
            return True
        except GridCodePqCancelled:
            raise
        except Exception:
            continue
    net_pf._pq_pf_stage = 'div:nr'
    return False


def _pq_settle_and_freeze_taps(base_net, ctx, p_val, tap_bound):
    """Warm-start discrete tap_pos at Q = 0 for the lower/upper voltage target.

    Controllers are cleared on the returned net so the next trial can re-attach
    them. Callers must keep tap control enabled: plant Q after this settle would
    otherwise leave the controlled bus outside the DiscreteTapControl band.
    """
    net_try = deepcopy(base_net)
    _pq_clear_controllers(net_try)
    _pq_apply_tap_family_filter(net_try, ctx)
    if tap_bound:
        _pq_pin_taps(net_try, tap_bound)
    net_try.ext_grid.at[ctx['ext_grid_idx'], 'vm_pu'] = float(ctx['v_applied'])
    _pq_dispatch_p(net_try, ctx['gen_info'], p_val, ctx['exclude_names'])
    for g in ctx['gen_info']:
        try:
            if g.get('type') == 'storage':
                net_try.storage.at[g['idx'], 'q_mvar'] = 0.0
            else:
                net_try.sgen.at[g['idx'], 'q_mvar'] = 0.0
        except Exception:
            pass
    ctx['iLDF'][0] += 1
    _pq_check_cancel(ctx)
    if not _pq_run_pf(
            net_try, ctx['verbose'], ctx['rc2'], ctx['rc3'], False, force_control=False,
            cancel_event=ctx.get('cancel_event')):
        return None
    _pq_clear_controllers(net_try)
    return net_try


def _pq_apply_local_q(net, gen_info, p_val, q_mode, direction, frac, exclude_names, in_data=None):
    exclude = set(exclude_names or [])
    scale = [g for g in gen_info if g.get('name') not in exclude]
    total = sum(float(g['p_rated_mw']) for g in scale) or 0.0
    sign = 1.0 if direction == 'max' else -1.0
    for g in gen_info:
        if g.get('name') in exclude:
            p_gen = _pq_gen_p(net, g)
        elif total <= 0:
            p_gen = 0.0
        else:
            p_gen = float(p_val) * (float(g['p_rated_mw']) / total)
        if g.get('type') == 'storage':
            el = _pq_storage_element_data(in_data, g.get('name'))
            q_pos, q_neg = _pq_storage_q_caps(net, g['idx'], abs(p_gen), g['sn_mva'], q_mode, el)
        else:
            q_pos, q_neg = pp_el._rpc_sgen_q_caps(net, g['idx'], p_gen, g['sn_mva'], q_mode)
        q_full = q_pos if direction == 'max' else q_neg
        _pq_set_gen_pq(net, g, p_gen, sign * q_full * float(frac))


def _pq_eval_trial(base_net, ctx, p_val, direction, frac_or_q, tap_bound=None, use_park=False,
                  q_cap=None):
    """
    One load-flow trial. frac_or_q is capability fraction (local) or plant Q setpoint (park).
    Returns dict: converged, overloaded, volt_viol, q_pcc, p_pcc, net.
    """
    inplace = ctx.get('_inplace_net') is base_net
    if inplace:
        net_try = base_net
        _pq_restore_baseline(net_try, ctx.get('_trial_baseline'))
    else:
        net_try = deepcopy(base_net)
    _pq_clear_controllers(net_try)
    _pq_apply_tap_family_filter(net_try, ctx)
    # Park as configured: start the taps where the previous P point on the same edge settled.
    # From the diagram's tap positions a heavy point (e.g. full P with the STATCOM at its
    # inductive rating) can have no load-flow solution at all, so tap control never starts.
    tap_seed_key = None
    if use_park and ctx.get('park_configured') and not tap_bound:
        tap_seed_key = ctx.get('_statcom_force') or 'op'
        seeds = ctx.get('_pq_tap_seed') or {}
        _pq_apply_tap_positions(net_try, seeds.get(tap_seed_key) or seeds.get('op'))
    if tap_bound:
        _pq_pin_taps(net_try, tap_bound)
    net_try.ext_grid.at[ctx['ext_grid_idx'], 'vm_pu'] = float(ctx['v_applied'])
    _pq_apply_vm_seed(net_try, ctx.get('vm_seed'))
    _pq_dispatch_p(net_try, ctx['gen_info'], p_val, ctx['exclude_names'])

    force_ctrl = False
    if use_park:
        if ctx.get('park_configured'):
            # Run the Park Controller exactly as configured on the diagram.
            filtered = _pq_filter_in_data(
                ctx['in_data'], ctx['park_name'], ctx['park_id'],
                q_set=None, force_const_q=False, pcc_bus_name=ctx['pcc_bus_name'])
        else:
            q_set = float(frac_or_q)
            filtered = _pq_filter_in_data(
                ctx['in_data'], ctx['park_name'], ctx['park_id'],
                q_set=q_set, force_const_q=True, pcc_bus_name=ctx['pcc_bus_name'])
        attached = pp_el._electrisim_attach_park_controllers(net_try, filtered, quiet=True)
        force_ctrl = attached > 0
        if attached <= 0:
            return {
                'converged': False, 'overloaded': False, 'volt_viol': False,
                'q_pcc': None, 'p_pcc': None, 'net': None, 'limit_reason': 'park_attach',
            }
        side = ctx.get('_statcom_force')
        if ctx.get('park_configured') and ctx.get('psc_reactors') is not None:
            if side in ('max', 'min'):
                # Capability edge: the supervisory controller's reactors at their extreme step
                # (least absorption for the capacitive edge, most for the inductive edge).
                psc_reactors = ctx.get('psc_reactors') or {}
                pp_el._psc_release_reactors(net_try, list(psc_reactors))
                for r_idx, (steps, qmap) in psc_reactors.items():
                    pick = min if side == 'max' else max
                    net_try.shunt.at[r_idx, 'step'] = pick(steps, key=lambda st: qmap.get(st, 0.0))
            elif ctx.get('has_psc'):
                # Operating point: the Plant Supervisory Controller leads its STATCOMs and reactors.
                n_psc = pp_el._electrisim_attach_plant_supervisory_controllers(net_try, ctx['in_data'], quiet=True)
                force_ctrl = force_ctrl or n_psc > 0
    else:
        _pq_apply_local_q(
            net_try, ctx['gen_info'], p_val, ctx['q_mode'], direction, float(frac_or_q),
            ctx['exclude_names'], ctx.get('in_data'))

    local_statcom_q = None
    if ctx.get('local_statcoms') and not ctx.get('park_configured'):
        local_statcom_q = _pq_set_local_statcoms(
            net_try, ctx, direction, frac=None if use_park else frac_or_q)

    if ctx.get('_statcom_force') and ctx.get('statcoms'):
        led = getattr(net_try, '_electrisim_ssc_sgen', None) or {}
        to_force = [st for st in ctx['statcoms'] if st[0] not in led]
        if to_force:
            ctx['_statcom_undo'] = _pq_force_statcoms(
                net_try, ctx['_statcom_force'], to_force, frac=ctx.get('_statcom_frac'))

    ctx['iLDF'][0] += 1
    _pq_check_cancel(ctx)
    ok = _pq_run_pf(
        net_try, ctx['verbose'], ctx['rc2'], ctx['rc3'], ctx['rcs'], force_control=force_ctrl,
        cancel_event=ctx.get('cancel_event'))
    pf_stage = getattr(net_try, '_pq_pf_stage', None)
    if not ok:
        return {
            'converged': False, 'overloaded': False, 'volt_viol': False,
            'q_pcc': None, 'p_pcc': None, 'net': None, 'limit_reason': 'divergence',
            'pf_stage': pf_stage,
        }

    if tap_seed_key:
        ctx.setdefault('_pq_tap_seed', {})[tap_seed_key] = _pq_tap_positions(net_try)

    overloaded = ctx['limit_overloads'] and _pq_overloaded(net_try, ctx['max_loading'])
    volt_viol = ctx['lim_q_uprot'] and _pq_voltage_violation(
        net_try, ctx['gen_info'], ctx['u_min_prot'], ctx['u_max_prot'])

    seed = _pq_capture_vm_seed(net_try)
    if seed is not None:
        ctx['vm_seed'] = seed
    q_pcc = _pq_pcc_q(net_try, ctx)
    reason = None
    unphysical = False
    if overloaded:
        reason = 'overload'
    elif volt_viol:
        reason = 'voltage'
    elif q_cap is not None and not ctx.get('_pq_cross_walk') and _pq_q_unphysical(q_pcc, q_cap, direction, ctx):
        unphysical = True
        reason = 'unphysical_q'

    limiting_element = None
    if overloaded and hasattr(net_try, 'res_line') and not net_try.res_line.empty:
        try:
            idx = net_try.res_line['loading_percent'].idxmax()
            limiting_element = {
                'type': 'line',
                'name': str(net_try.line.at[idx, 'name']),
                'loading_percent': float(net_try.res_line.at[idx, 'loading_percent']),
            }
        except Exception:
            pass
    if overloaded and limiting_element is None and hasattr(net_try, 'res_trafo') and not net_try.res_trafo.empty:
        try:
            idx = net_try.res_trafo['loading_percent'].idxmax()
            limiting_element = {
                'type': 'transformer',
                'name': str(net_try.trafo.at[idx, 'name']),
                'loading_percent': float(net_try.res_trafo.at[idx, 'loading_percent']),
            }
        except Exception:
            pass
    if volt_viol and limiting_element is None:
        limiting_element = {'type': 'voltage', 'name': ctx.get('pcc_bus_name'), 'limit_reason': 'voltage'}

    r = {
        'converged': True,
        'overloaded': overloaded,
        'volt_viol': volt_viol,
        'unphysical': unphysical,
        'q_pcc': q_pcc,
        'p_pcc': _pq_pcc_p(net_try, ctx['pcc_bus_idx'], ctx['ext_grid_idx']),
        'net': net_try,
        'limit_reason': reason,
        'limiting_element': limiting_element,
        'pf_stage': pf_stage,
    }
    if local_statcom_q:
        r['_statcom_q'] = local_statcom_q
    return _pq_fill_diag(r, ctx)


_pq_serialize_lock = threading.Lock()


def _pq_serialize_point(net):
    """Snapshot for the diagram without the per-bus branch scan used by a full load flow."""
    def _fast_branch(_solved, _bus_idx):
        return 0.0, 0.0

    def _fast_nodal(solved, bus_idx):
        try:
            return (
                float(solved.res_bus.at[bus_idx, 'p_mw']),
                float(solved.res_bus.at[bus_idx, 'q_mvar']),
            )
        except Exception:
            return 0.0, 0.0

    with _pq_serialize_lock:
        orig_br = pp_el._electrisim_bus_branch_p_q_sum
        orig_nd = pp_el._electrisim_bus_nodal_p_q_sum
        pp_el._electrisim_bus_branch_p_q_sum = _fast_branch
        pp_el._electrisim_bus_nodal_p_q_sum = _fast_nodal
        try:
            snap = pp_el._rpc_serialize_solved_net(net)
        finally:
            pp_el._electrisim_bus_branch_p_q_sum = orig_br
            pp_el._electrisim_bus_nodal_p_q_sum = orig_nd
    return _pq_omit_out_of_service_shunts(snap, net)


def _pq_omit_out_of_service_shunts(snap, net):
    if not snap or not hasattr(net, 'shunt') or net.shunt is None or getattr(net.shunt, 'empty', True):
        return snap
    if 'in_service' not in net.shunt.columns:
        return snap
    off = set()
    for idx in net.shunt.index:
        try:
            if bool(net.shunt.at[idx, 'in_service']):
                continue
            off.add(str(net.shunt.at[idx, 'name']))
            if 'id' in net.shunt.columns:
                off.add(str(net.shunt.at[idx, 'id']))
        except Exception:
            continue
    if not off:
        return snap
    for key in ('shunts', 'capacitors'):
        rows = snap.get(key)
        if not isinstance(rows, list):
            continue
        kept = [
            row for row in rows
            if str(row.get('name')) not in off and str(row.get('id')) not in off
        ]
        if kept:
            snap[key] = kept
        else:
            snap.pop(key, None)
    return snap


def _pq_hold_solved(net):
    """Cheap copy of the solved state so a later trial can reuse the same network."""
    res = {}
    for name in (
        'res_bus', 'res_line', 'res_trafo', 'res_trafo3w', 'res_sgen', 'res_storage',
        'res_gen', 'res_ext_grid', 'res_load', 'res_shunt', 'res_switch', 'res_svc',
    ):
        tbl = getattr(net, name, None)
        if tbl is not None and not getattr(tbl, 'empty', True):
            try:
                res[name] = tbl.copy()
            except Exception:
                pass
    return {'res': res, 'setpoints': _pq_input_baseline(net)}


def _pq_apply_hold(net, hold):
    if not hold:
        return
    _pq_restore_baseline(net, hold.get('setpoints'))
    for name, tbl in (hold.get('res') or {}).items():
        setattr(net, name, tbl.copy())


def _pq_finalize_kept(r, work, ctx):
    """Build the diagram snapshot once, for the operating point that is kept."""
    if not r:
        return r
    if r.get('_hold'):
        _pq_apply_hold(work, r.pop('_hold'))
    if r.get('lf_snap') is None and work is not None:
        try:
            r['lf_snap'] = _pq_serialize_point(work)
        except Exception:
            r['lf_snap'] = None
        statcom_q = r.pop('_statcom_q', None)
        if statcom_q and r.get('lf_snap'):
            r['lf_snap'] = _pq_snap_with_statcoms(r['lf_snap'], work, forced=statcom_q)
        if not r.get('unphysical'):
            summary = ctx.get('summary')
            if summary is not None:
                _pq_update_summary(summary, work, ctx.get('gen_info') or [])
    try:
        ctx['_last_kept_state'] = (_pq_tap_positions(work), _pq_voltages_of_result(None, work))
    except Exception:
        ctx['_last_kept_state'] = None
    r['net'] = None
    return r


def _pq_feasible(r):
    return (
        bool(r.get('converged'))
        and not r.get('overloaded')
        and not r.get('volt_viol')
        and not r.get('unphysical')
    )


def _pq_q_hint(ctx, direction, tap_bound):
    return (ctx.get('q_frac_hint') or {}).get((direction, tap_bound))


def _pq_remember_q_hint(ctx, direction, tap_bound, x):
    try:
        ctx.setdefault('q_frac_hint', {})[(direction, tap_bound)] = float(x)
    except (TypeError, ValueError):
        pass


def _pq_bisect_q(work, ctx, p_val, direction, use_park, tap_bound, x_fail, q_cap, reason,
                 x_lo=0.0, r_lo=None):
    """Largest feasible |Q| between x_lo and the failed trial, within q_step."""
    dq = max(abs(float(ctx['q_step_mw'])), 1e-6)
    tol = dq if use_park else dq / max(abs(float(q_cap or 0.0)) or 1.0, 1e-9)
    x_lo = float(x_lo)
    x_hi = float(x_fail)
    if r_lo is not None and _pq_feasible(r_lo):
        best_r, best_x = r_lo, x_lo
        best_r['_hold'] = _pq_hold_solved(work)
    else:
        r_ok = _pq_eval_trial(
            work, ctx, p_val, direction, x_lo, tap_bound=tap_bound, use_park=use_park, q_cap=q_cap)
        if not _pq_feasible(r_ok):
            return r_ok, x_lo, r_ok.get('limit_reason') or reason
        best_r, best_x = r_ok, x_lo
        best_r['_hold'] = _pq_hold_solved(work)
    guard = 0
    while abs(x_hi - x_lo) > tol + 1e-12 and guard < 40:
        guard += 1
        x_mid = 0.5 * (x_hi + x_lo)
        r = _pq_eval_trial(
            work, ctx, p_val, direction, x_mid, tap_bound=tap_bound, use_park=use_park, q_cap=q_cap)
        if _pq_feasible(r):
            x_lo = x_mid
            best_r, best_x = r, x_mid
            best_r['_hold'] = _pq_hold_solved(work)
        else:
            x_hi = x_mid
            reason = r.get('limit_reason') or reason
    return best_r, best_x, reason


def _pq_taps_of_result(r, work):
    """Tap positions of a kept trial: from its held state, or from the net when it was the last trial."""
    hold = (r or {}).get('_hold')
    tables = ((hold or {}).get('setpoints') or {}).get('tables') or {}
    if hold:
        out = {}
        for table in ('trafo', 'trafo3w'):
            col = (tables.get(table) or {}).get('tap_pos')
            if col is not None:
                out[table] = {int(i): float(v) for i, v in col.items() if v == v}
        return out
    return _pq_tap_positions(work)


def _pq_voltages_of_result(r, work):
    """Bus voltages of a kept trial, as a Newton warm start (vm, va) or None."""
    hold = (r or {}).get('_hold')
    res_bus = ((hold or {}).get('res') or {}).get('res_bus') if hold else getattr(work, 'res_bus', None)
    try:
        if res_bus is None or res_bus.empty or res_bus['vm_pu'].isna().any():
            return None
        return res_bus['vm_pu'].copy(), res_bus['va_degree'].copy()
    except Exception:
        return None


def _pq_seed_baseline_taps(baseline, taps):
    """Make the next trials start from these tap positions."""
    tables = (baseline or {}).get('tables') or {}
    for table, pos in (taps or {}).items():
        col = (tables.get(table) or {}).get('tap_pos')
        if col is None:
            continue
        for idx, v in pos.items():
            if idx in col.index:
                col.at[idx] = v


def _pq_continue_after_divergence(work, ctx, p_val, direction, use_park, tap_bound,
                                  x_ok, r_ok, x_cap, q_cap):
    """
    The trial at full capability did not converge, which is not a network limit: tap changers
    started from their Q = 0 positions, too far from the solution. Walk from the last solved
    point toward the capability, each trial starting from the taps solved at the previous one,
    and halve the step when a trial diverges. A converged trial that breaks a loading or voltage
    limit is a real limit: refine between the two points with the usual bisection.
    Returns (r, x, reason).
    """
    best_x, best_r = float(x_ok), r_ok
    taps = _pq_taps_of_result(best_r, work)
    vm_seed_saved = ctx.get('vm_seed')
    seed = _pq_voltages_of_result(best_r, work)
    try:
        return _pq_continue_steps(work, ctx, p_val, direction, use_park, tap_bound,
                                  best_x, best_r, taps, seed, x_cap, q_cap, x_ok, r_ok)
    finally:
        ctx['vm_seed'] = vm_seed_saved


def _pq_continue_steps(work, ctx, p_val, direction, use_park, tap_bound,
                       best_x, best_r, taps, seed, x_cap, q_cap, x_ok, r_ok):
    dq = max(abs(float(ctx['q_step_mw'])), 1e-6)
    tol = dq if use_park else dq / max(abs(float(q_cap or 0.0)) or 1.0, 1e-9)
    gap = float(x_cap) - best_x
    # Start with a step about the size of the part that already solved, then grow it after
    # each solved trial and halve it after each diverged one.
    step = gap if abs(best_x) <= tol else math.copysign(min(abs(gap), max(abs(best_x), tol)), gap)
    reason = 'divergence'
    for _ in range(30):
        if abs(step) <= tol:
            break
        x_try = best_x + step
        if (x_try - float(x_cap)) * math.copysign(1.0, gap) > 0:
            x_try = float(x_cap)
        _pq_seed_baseline_taps(ctx.get('_trial_baseline'), taps)
        if seed is not None:
            ctx['vm_seed'] = seed
        r = _pq_eval_trial(
            work, ctx, p_val, direction, x_try, tap_bound=tap_bound, use_park=use_park, q_cap=q_cap)
        _pq_log_trial(ctx, p_val, tap_bound, direction, r, x_try, q_cap, 'continue')
        if _pq_feasible(r):
            r['_hold'] = _pq_hold_solved(work)
            best_x, best_r = x_try, r
            taps = _pq_tap_positions(work)
            seed = _pq_voltages_of_result(None, work) or seed
            reason = None
            if abs(float(x_cap) - best_x) <= tol:
                break
            step *= 1.5
            continue
        if r and r.get('converged') and not r.get('unphysical'):
            reason = r.get('limit_reason') or 'limit'
            _pq_seed_baseline_taps(ctx.get('_trial_baseline'), taps)
            rb, xb, rsn = _pq_bisect_q(
                work, ctx, p_val, direction, use_park, tap_bound, x_try, q_cap, reason,
                x_lo=best_x, r_lo=best_r)
            if _pq_feasible(rb):
                return rb, xb, rsn
            break
        step /= 2.0
    if best_r is r_ok:
        return r_ok, float(x_ok), 'divergence'
    # Stopped short of the capability on a divergence: report it as such.
    reached = abs(float(x_cap) - best_x) <= tol
    return best_r, best_x, (None if reached else (reason or 'divergence'))


def _pq_search_one_side(base_net, ctx, p_val, direction, use_park, tap_bound):
    """Search one edge; file its solved taps and voltages so the opposite edge can start there."""
    ctx['_last_kept_state'] = None
    out = _pq_search_one_side_inner(base_net, ctx, p_val, direction, use_park, tap_bound)
    if out and out[0] is not None and out[1] is not None and ctx.get('_last_kept_state'):
        taps, volts = ctx['_last_kept_state']
        ctx.setdefault('_edge_seed', {})[(round(float(p_val), 6), tap_bound, direction)] = (
            taps, volts, float(out[1]), abs(float(out[3] or 0.0)))
    return out


def _pq_retry_from_other_edge(work, ctx, p_val, direction, use_park, tap_bound, x_cap, q_cap):
    """
    Nothing solved on this edge, not even Q = 0. Start from the operating point solved on the
    opposite edge at the same P (same taps, voltages and plant Q) and walk toward this edge's
    capability. Example: at a low grid voltage and full P the plant may only solve while it
    supplies Q; the lowest Q it can then reach is still capacitive, and that is its Q_min.
    """
    other = 'max' if direction == 'min' else 'min'
    seed = (ctx.get('_edge_seed') or {}).get((round(float(p_val), 6), tap_bound, other))
    if not seed:
        return None, None, None
    taps, volts, x_other, cap_other = seed
    if use_park:
        x0 = x_other  # plant Q setpoint at the PCC, same value on both edges
    else:
        # Same unit Q expressed as a fraction of this edge's capability (negative = other side).
        cap_this = abs(float(q_cap or 0.0)) or 1.0
        x0 = -float(x_other) * (float(cap_other or cap_this) / cap_this)
        x0 = max(-1.0, min(1.0, x0))
    vm_seed_saved = ctx.get('vm_seed')
    # The walk starts on the other side of Q = 0, so the per-edge Q sanity check only applies
    # to the point it ends on.
    ctx['_pq_cross_walk'] = True
    try:
        _pq_seed_baseline_taps(ctx.get('_trial_baseline'), taps)
        if volts is not None:
            ctx['vm_seed'] = volts
        r0 = _pq_eval_trial(
            work, ctx, p_val, direction, x0, tap_bound=tap_bound, use_park=use_park, q_cap=q_cap)
        _pq_log_trial(ctx, p_val, tap_bound, direction, r0, x0, q_cap, f'from Q_{other}')
        if not _pq_feasible(r0):
            return None, None, None
        r, x, reason = _pq_continue_after_divergence(
            work, ctx, p_val, direction, use_park, tap_bound, x0, r0, x_cap, q_cap)
    finally:
        ctx['vm_seed'] = vm_seed_saved
        ctx['_pq_cross_walk'] = False
    if r is None or abs(float(x) - float(x0)) < 1e-9:
        return None, None, None  # never moved off the other edge's point
    if _pq_q_unphysical(r.get('q_pcc'), q_cap, direction, ctx):
        return None, None, None
    return r, x, reason or 'divergence'


def _pq_search_one_side_inner(base_net, ctx, p_val, direction, use_park, tap_bound):
    """
    Find feasible Q for one P and one Q extreme:

    1. Set Q to the unit/plant capability (Qmax or Qmin) and run a load flow.
    2. If loading limit and shunt control are on and the network is overloaded: reduce
       compensation steps one at a time (shunt controllers frozen) until OK or
       no steps remain.
    3. Then search toward Q = 0 until limits are OK (resolution = Q reduction step).
       Park control off: each unit's Q as a fraction of its capability at this P.
       Park control on: Park Controller constant-Q setpoint at the point of connection.
    """
    q_pos, q_neg = _pq_plant_q_caps(
        base_net, ctx['gen_info'], p_val, ctx['q_mode'], ctx['exclude_names'], ctx.get('in_data'))
    q_cap = q_pos if direction == 'max' else q_neg
    work = _pq_acquire_work_net(ctx, base_net)
    _pq_clear_controllers(work)
    if use_park:
        sign = 1.0 if direction == 'max' else -1.0
        x = sign * float(q_cap)
    else:
        x = 1.0

    r = None
    reason = 'divergence'
    rcs_saved = ctx['rcs']
    rc2_saved, rc3_saved = ctx['rc2'], ctx['rc3']
    try:
        if tap_bound and (ctx['rc2'] or ctx['rc3']):
            settled = _pq_settle_and_freeze_taps(base_net, ctx, p_val, tap_bound)
            if settled is not None:
                work = settled
                _pq_emit(
                    f'    P={p_val:.2f} MW tap={tap_bound}: tap warm-start at Q=0 OK',
                    ctx, progress=False)
            else:
                _pq_emit(
                    f'    P={p_val:.2f} MW tap={tap_bound}: tap warm-start failed; using diagram tap_pos',
                    ctx, progress=False)

        ctx['_inplace_net'] = work
        ctx['_trial_baseline'] = _pq_input_baseline(work)
        r = _pq_eval_trial(
            work, ctx, p_val, direction, x, tap_bound=tap_bound, use_park=use_park, q_cap=q_cap)
        _pq_log_trial(ctx, p_val, tap_bound, direction, r, x, q_cap, 'cap')
        x_cap = x
        cap_diverged = not (r and r.get('converged'))
        if _pq_feasible(r):
            _pq_remember_q_hint(ctx, direction, tap_bound, x)
            return _pq_finalize_kept(r, work, ctx), x, None, q_cap

        reason = r.get('limit_reason') or 'divergence'
        if ctx['shnt_ctrl'] and ctx['limit_overloads'] and r.get('overloaded'):
            ctx['rcs'] = False
            guard = 0
            while r.get('overloaded') and guard < 200:
                if not _pq_reduce_compensation_one_step(work, ctx['shunt_names'], direction):
                    break
                ctx['_trial_baseline'] = _pq_input_baseline(work)
                r = _pq_eval_trial(
                    work, ctx, p_val, direction, x, tap_bound=tap_bound, use_park=use_park,
                    q_cap=q_cap)
                guard += 1
                if _pq_feasible(r):
                    _pq_log_trial(ctx, p_val, tap_bound, direction, r, x, q_cap, 'after shunt')
                    _pq_remember_q_hint(ctx, direction, tap_bound, x)
                    return _pq_finalize_kept(r, work, ctx), x, 'shunt', q_cap
                reason = r.get('limit_reason') or reason

        hint = _pq_q_hint(ctx, direction, tap_bound)
        if hint is not None and abs(float(hint) - float(x)) > 1e-6:
            r_hint = _pq_eval_trial(
                work, ctx, p_val, direction, float(hint), tap_bound=tap_bound,
                use_park=use_park, q_cap=q_cap)
            if _pq_feasible(r_hint):
                r, x, reason = _pq_bisect_q(
                    work, ctx, p_val, direction, use_park, tap_bound, x, q_cap, reason,
                    x_lo=float(hint), r_lo=r_hint)
            else:
                r, x, reason = _pq_bisect_q(
                    work, ctx, p_val, direction, use_park, tap_bound, float(hint), q_cap, reason)
        else:
            r, x, reason = _pq_bisect_q(
                work, ctx, p_val, direction, use_park, tap_bound, x, q_cap, reason)
        _pq_log_trial(ctx, p_val, tap_bound, direction, r, x, q_cap, 'bisect')
        if (cap_diverged and _pq_feasible(r) and x is not None
                and abs(float(x)) < abs(float(x_cap)) * (1.0 - 1e-6)):
            r, x, reason = _pq_continue_after_divergence(
                work, ctx, p_val, direction, use_park, tap_bound, x, r, x_cap, q_cap)
        if cap_diverged and not _pq_feasible(r):
            r2, x2, reason2 = _pq_retry_from_other_edge(
                work, ctx, p_val, direction, use_park, tap_bound, x_cap, q_cap)
            if r2 is not None and _pq_feasible(r2):
                r, x, reason = r2, x2, reason2
        if _pq_feasible(r):
            _pq_remember_q_hint(ctx, direction, tap_bound, x)
            return _pq_finalize_kept(r, work, ctx), x, reason, q_cap
    finally:
        if ctx.get('_inplace_net') is work:
            ctx['_inplace_net'] = None
        ctx['rcs'] = rcs_saved
        ctx['rc2'], ctx['rc3'] = rc2_saved, rc3_saved

    if r and r.get('converged') and not r.get('unphysical'):
        return _pq_finalize_kept(r, work, ctx), x, reason, q_cap
    return None, None, reason, q_cap


def _pq_restrictive_qmax(a, b):
    """Worst-case Qmax: smaller overexcited value. Ignore large negative artefacts."""
    vals = [v for v in (a, b) if v is not None]
    if not vals:
        return None
    pos = [v for v in vals if v >= -1e-6]
    if pos:
        return min(pos)
    return max(vals)


def _pq_restrictive_qmin(a, b):
    """Worst-case Qmin: larger value (weaker underexcited)."""
    vals = [v for v in (a, b) if v is not None]
    if not vals:
        return None
    return max(vals)


def _pq_net_matching_q(pairs, q_sel):
    """Pick the solved net whose PCC Q matches the envelope value used on the chart."""
    if q_sel is not None:
        target = float(q_sel)
        for q, net in pairs:
            if q is None or net is None:
                continue
            if abs(float(q) - target) < 1e-9:
                return net
    for _, net in reversed(pairs):
        if net is not None:
            return net
    return None


def _pq_r_matching_q(rs, q_sel):
    """Pick the trial result whose PCC Q matches the envelope value."""
    if q_sel is not None:
        target = float(q_sel)
        for r in rs:
            if not r or r.get('q_pcc') is None:
                continue
            if abs(float(r['q_pcc']) - target) < 1e-9:
                return r
    for r in reversed(rs or []):
        if r is not None:
            return r
    return None


def _pq_limit_payload(r):
    """JSON-safe limiter for one envelope point. Full capability → PCS rating."""
    if not r:
        return None
    payload = {}
    el = r.get('limiting_element')
    if isinstance(el, dict):
        for k, v in el.items():
            try:
                fv = float(v)
                payload[k] = None if math.isnan(fv) else fv
            except (TypeError, ValueError):
                payload[k] = v
    reason = r.get('limit_reason')
    if reason:
        payload.setdefault('limit_reason', reason)
        payload.setdefault('type', reason)
        payload.setdefault('name', reason)
    if not payload:
        payload = {'type': 'pcs', 'name': 'unit rating', 'limit_reason': 'rating'}
    return payload


def _pq_trafo_display_name(net, table, idx):
    name = str(table.at[idx, 'name'])
    ufn = getattr(net, 'user_friendly_names', None) or {}
    return str(ufn.get(name, name))


def _pq_update_summary(summary, net, gen_info):
    if net is None or not hasattr(net, 'res_bus') or net.res_bus.empty:
        return
    vm = net.res_bus['vm_pu']
    summary['umax_tot'] = max(summary['umax_tot'], float(vm.max()))
    summary['umin_tot'] = min(summary['umin_tot'], float(vm.min()))
    for g in gen_info:
        try:
            bus = _pq_gen_bus(net, g)
            v = float(net.res_bus.at[bus, 'vm_pu'])
            summary['ugenmax_tot'] = max(summary['ugenmax_tot'], v)
            summary['ugenmin_tot'] = min(summary['ugenmin_tot'], v)
        except Exception:
            pass
    if hasattr(net, 'shunt') and not net.shunt.empty and hasattr(net, 'res_bus'):
        for idx in net.shunt.index:
            try:
                bus = int(net.shunt.at[idx, 'bus'])
                v = float(net.res_bus.at[bus, 'vm_pu'])
                summary['ushntmax_tot'] = max(summary['ushntmax_tot'], v)
                summary['ushntmin_tot'] = min(summary['ushntmin_tot'], v)
            except Exception:
                pass
    if hasattr(net, 'res_line') and net.res_line is not None and not net.res_line.empty:
        summary['maxloading_cbl'] = max(summary['maxloading_cbl'], float(net.res_line.loading_percent.max()))
    if hasattr(net, 'res_trafo') and net.res_trafo is not None and not net.res_trafo.empty:
        summary['maxloading_trf'] = max(summary['maxloading_trf'], float(net.res_trafo.loading_percent.max()))
        if 'tap_pos' in net.trafo.columns:
            summary['trf_tap_max'] = max(summary['trf_tap_max'], float(net.trafo['tap_pos'].max()))
            summary['trf_tap_min'] = min(summary['trf_tap_min'], float(net.trafo['tap_pos'].min()))
    if hasattr(net, 'res_trafo3w') and net.res_trafo3w is not None and not net.res_trafo3w.empty:
        if 'loading_percent' in net.res_trafo3w.columns:
            summary['maxloading_trf'] = max(summary['maxloading_trf'], float(net.res_trafo3w.loading_percent.max()))


def _pq_p_sweep(pn, p_start_pct, p_step_pct, p_end_pct, i_op_range):
    start = _pq_float(p_start_pct, 0.0)
    step = abs(_pq_float(p_step_pct, 10.0))
    end = _pq_float(p_end_pct, 100.0)
    if step <= 0:
        step = 10.0
    if end < start:
        start, end = end, start

    def _pct_points(s, e):
        pts = []
        x = s
        # include endpoint
        guard = 0
        while x <= e + 1e-9 and guard < 500:
            pts.append(x)
            x += step
            guard += 1
        if pts and abs(pts[-1] - e) > 1e-6:
            pts.append(e)
        return pts

    pcts_pos = _pct_points(start, end)
    points = []
    if i_op_range in (0, 2):
        points.extend([pn * p / 100.0 for p in pcts_pos])
    if i_op_range in (1, 2):
        points.extend([-pn * p / 100.0 for p in pcts_pos])
    # unique sorted
    seen = set()
    out = []
    for p in sorted(points):
        key = round(float(p), 6)
        if key in seen:
            continue
        seen.add(key)
        out.append(float(p))
    if not out:
        out = [0.0, pn] if i_op_range != 1 else [0.0, -pn]
    return out


def _pq_merge_extra_p(p_points, extra_p_mw):
    """Add caller-supplied P points (MW, signed) to the uniform sweep.

    Used to close the envelope between Pn and the plant P limit, where the
    uniform % step would stop short and leave the curve open at the ends.
    """
    merged = list(p_points or [])
    for val in extra_p_mw or []:
        try:
            merged.append(float(val))
        except (TypeError, ValueError):
            continue
    seen = set()
    out = []
    for p in sorted(merged):
        key = round(float(p), 6)
        if key in seen:
            continue
        seen.add(key)
        out.append(float(p))
    return out


def _pq_check_compliance(p_max_result, q_max_result, p_min_result, q_min_result, v_req):
    """
    True when plant Qmax/Qmin at the PCC cover the required envelope.
    P arrays are net P at the PCC (same axis as the red chart). A required
    P outside the delivered PCC P span is not compliant (no clip to Pn).
    """
    if not v_req:
        return None
    req_p = v_req.get('p_mw', [])
    req_q_max = v_req.get('q_req_max_mvar', [])
    req_q_min = v_req.get('q_req_min_mvar', [])
    n = min(len(req_p), len(req_q_max), len(req_q_min))
    if n < 1:
        return False
    try:
        order = np.argsort([float(req_p[i]) for i in range(n)])
        rp = np.array([float(req_p[i]) for i in order], dtype=float)
        rmax = np.array([float(req_q_max[i]) for i in order], dtype=float)
        rmin = np.array([float(req_q_min[i]) for i in order], dtype=float)
    except (TypeError, ValueError):
        return False
    tol_mvar = 1e-4
    p_lo = float(rp[0])
    p_hi = float(rp[-1])
    p_check = set(float(x) for x in rp.tolist())
    for p_arr in (p_max_result, p_min_result):
        for p_val in p_arr or []:
            try:
                pf = float(p_val)
            except (TypeError, ValueError):
                continue
            if p_lo <= pf <= p_hi:
                p_check.add(pf)
    for p_s in sorted(p_check):
        req_max_v = float(np.interp(p_s, rp, rmax, left=float(rmax[0]), right=float(rmax[-1])))
        req_min_v = float(np.interp(p_s, rp, rmin, left=float(rmin[0]), right=float(rmin[-1])))
        cap_max_v = _pq_interp_q_in_span(p_s, p_max_result, q_max_result)
        cap_min_v = _pq_interp_q_in_span(p_s, p_min_result, q_min_result)
        if cap_max_v is None or cap_min_v is None:
            return False
        if cap_max_v < req_max_v - tol_mvar or cap_min_v > req_min_v + tol_mvar:
            return False
    return True


def _pq_statcom_display_name(net, idx, in_data, ufn):
    """Dialog name of a STATCOM (userFriendlyName from the payload), else its network name."""
    tech = str(net.ssc.at[idx, 'name'])
    sid = str(net.ssc.at[idx, 'id']) if 'id' in net.ssc.columns else None
    for el in (in_data or {}).values():
        if not isinstance(el, dict) or not str(el.get('typ') or '').startswith('SSC'):
            continue
        if str(el.get('name')) == tech or (sid and str(el.get('id')) == sid):
            friendly = el.get('userFriendlyName')
            if friendly:
                return str(friendly)
    return str((ufn or {}).get(tech, tech))


def _pq_statcom_q_on_bus(net, bus_idx):
    """
    Q (Mvar, generator convention: + = supplied) that STATCOMs inject directly on ``bus_idx``:
    in-service SSC results plus the helper injections that stand in for them in a trial.
    """
    total = 0.0
    try:
        bus_idx = int(bus_idx)
    except (TypeError, ValueError):
        return 0.0
    df = getattr(net, 'ssc', None)
    res = getattr(net, 'res_ssc', None)
    if df is not None and not df.empty and res is not None and not res.empty:
        for idx in df.index:
            try:
                if int(df.at[idx, 'bus']) != bus_idx or not bool(df.at[idx, 'in_service']):
                    continue
                q = float(res.at[idx, 'q_mvar'])
                if q == q:
                    total -= q  # pandapower SSC results are load convention
            except Exception:
                continue
    for table, res_name in (('sgen', 'res_sgen'), ('gen', 'res_gen')):
        tab = getattr(net, table, None)
        rtab = getattr(net, res_name, None)
        if tab is None or tab.empty or rtab is None or rtab.empty or 'name' not in tab.columns:
            continue
        for idx in tab.index:
            try:
                if not str(tab.at[idx, 'name']).startswith((_PQ_STATCOM_SGEN_PREFIX, pp_el._SSC_EQUIV_PREFIX)):
                    continue
                if int(tab.at[idx, 'bus']) != bus_idx or idx not in rtab.index:
                    continue
                q = float(rtab.at[idx, 'q_mvar'])
                if q == q:
                    total += q
            except Exception:
                continue
    return total


def _pq_pcc_q(net, ctx_or_pcc, ext_grid_idx=None):
    """
    Plant Q at the PCC for the chart. When the PCC is the external grid's bus, the base
    measurement only sees branch flows from the plant, so STATCOMs sitting on that bus are
    added (they belong to the plant side of the connection point).
    """
    if isinstance(ctx_or_pcc, dict):
        pcc_bus_idx = ctx_or_pcc['pcc_bus_idx']
        ext_grid_idx = ctx_or_pcc['ext_grid_idx']
    else:
        pcc_bus_idx = ctx_or_pcc
    q = pp_el._rpc_pcc_q_for_chart(net, pcc_bus_idx, ext_grid_idx)
    try:
        eg_bus = int(net.ext_grid.at[ext_grid_idx, 'bus']) if ext_grid_idx is not None else None
    except Exception:
        eg_bus = None
    if eg_bus is not None and int(pcc_bus_idx) == eg_bus:
        q += _pq_statcom_q_on_bus(net, pcc_bus_idx)
    return q


def _pq_rated_statcoms(net):
    """In-service STATCOMs with a Q rating: [(ssc_idx, bus, q_max_mvar, q_min_mvar)]."""
    out = []
    df = getattr(net, 'ssc', None)
    if df is None or df.empty:
        return out
    for idx in df.index:
        try:
            if 'in_service' in df.columns and not bool(df.at[idx, 'in_service']):
                continue
            if not pp_el._electrisim_ssc_controllable(df.loc[idx]):
                continue  # Controllable unticked: the STATCOM does not regulate, so it is not swept
            q_max = float(df.at[idx, 'q_max_mvar']) if 'q_max_mvar' in df.columns else float('nan')
            q_min = float(df.at[idx, 'q_min_mvar']) if 'q_min_mvar' in df.columns else float('nan')
        except (TypeError, ValueError):
            continue
        q_max = q_max if q_max == q_max else 0.0
        q_min = q_min if q_min == q_min else 0.0
        q_max = abs(q_max)
        q_min = -abs(q_min)
        if q_max > 1e-9 or q_min < -1e-9:
            out.append((int(idx), int(df.at[idx, 'bus']), q_max, q_min))
    return out


_PQ_STATCOM_SGEN_PREFIX = '_pq_statcom_'


def _pq_idle_uncontrollable_statcoms(net):
    """STATCOMs with Controllable unticked do not regulate (Q = 0), as in load flow.

    Taking them out of service avoids pandapower's own SSC model, which often does not
    converge in plant models with phase-shifting (e.g. three-winding) transformers.
    """
    df = getattr(net, 'ssc', None)
    if df is None or df.empty:
        return []
    idled = []
    for idx in df.index:
        try:
            if 'in_service' in df.columns and not bool(df.at[idx, 'in_service']):
                continue
            if pp_el._electrisim_ssc_controllable(df.loc[idx]):
                continue
            df.at[idx, 'in_service'] = False
            idled.append(int(idx))
        except Exception:
            continue
    return idled


def _pq_prepare_local_statcoms(net):
    """
    Local Q (and park constant-Q) dispatch: each rated STATCOM becomes a fixed-Q injection
    that every trial sets on its own edge (capacitive rating on Q max, inductive rating on
    Q min), like the STATCOM envelope of the configured Park Controller. Without this the
    network keeps pandapower's SSC model, which does not converge in many plant models.
    Returns [(ssc_idx, sgen_idx, q_max_mvar, q_min_mvar)].
    """
    out = []
    for idx, bus, q_max, q_min in _pq_rated_statcoms(net):
        try:
            net.ssc.at[idx, 'in_service'] = False
            sg = pp.create_sgen(net, bus=bus, p_mw=0.0, q_mvar=0.0,
                                name=f'{_PQ_STATCOM_SGEN_PREFIX}{idx}', in_service=True)
            out.append((int(idx), int(sg), float(q_max), float(q_min)))
        except Exception:
            continue
    return out


def _pq_set_local_statcoms(net, ctx, direction, frac=None):
    """Put the local-mode STATCOM injections on this trial's edge. Returns {ssc_idx: q_mvar}."""
    q_of = {}
    for idx, sg, q_max, q_min in ctx.get('local_statcoms') or []:
        if sg not in net.sgen.index:
            continue
        q = q_max if direction == 'max' else q_min
        if frac is not None:
            # Local Q search: the STATCOM follows the same fraction as the units (a negative
            # fraction crosses Q = 0 toward the opposite side, as the units do).
            q *= max(-1.0, min(1.0, float(frac)))
        net.sgen.at[sg, 'q_mvar'] = float(q)
        q_of[idx] = float(q)
    return q_of


def _pq_force_statcoms(net, side, statcoms, frac=None):
    """
    Replace each rated STATCOM for one trial (pandapower's own SSC model often does not
    converge in plant models with three-winding transformers):

    - side 'max' / 'min': constant-Q injection at its capacitive / inductive rating.
    - side 'op': voltage control as configured, modelled as a P = 0 generator holding the
      STATCOM's voltage setpoint with Q limited to its rating (Q limits enforced).

    Returns undo info.
    """
    undo = {'sgens': [], 'gens': [], 'ssc_on': [], 'forced': {}, 'gen_of': {},
            'q_lims_flag': getattr(net, '_electrisim_enforce_q_lims', None)}
    slack_buses = set()
    try:
        for eg in net.ext_grid.index:
            if bool(net.ext_grid.at[eg, 'in_service']):
                slack_buses.add(int(net.ext_grid.at[eg, 'bus']))
    except Exception:
        pass
    for idx, bus, q_max, q_min in statcoms:
        undo['ssc_on'].append(idx)
        net.ssc.at[idx, 'in_service'] = False
        if side == 'op' and int(bus) in slack_buses:
            sg = pp.create_sgen(net, bus=bus, p_mw=0.0, q_mvar=0.0,
                                name=f'{_PQ_STATCOM_SGEN_PREFIX}{idx}', in_service=True)
            undo['sgens'].append(sg)
            undo['forced'][idx] = 0.0
            continue
        if side == 'op':
            try:
                vm = float(net.ssc.at[idx, 'set_vm_pu'])
            except (TypeError, ValueError, KeyError):
                vm = 1.0
            if not vm == vm or vm <= 0:
                vm = 1.0
            g = pp.create_gen(net, bus=bus, p_mw=0.0, vm_pu=vm, min_q_mvar=float(q_min),
                              max_q_mvar=float(q_max), name=f'{_PQ_STATCOM_SGEN_PREFIX}{idx}',
                              in_service=True)
            undo['gens'].append(g)
            undo['gen_of'][idx] = g
            net._electrisim_enforce_q_lims = True
            continue
        q = q_max if side == 'max' else q_min
        if frac is not None:
            q *= max(0.0, min(1.0, float(frac)))  # part of the rating while ramping toward an edge
        sg = pp.create_sgen(net, bus=bus, p_mw=0.0, q_mvar=float(q),
                            name=f'{_PQ_STATCOM_SGEN_PREFIX}{idx}', in_service=True)
        undo['sgens'].append(sg)
        undo['forced'][idx] = float(q)
    return undo


def _pq_unforce_statcoms(net, undo):
    if not undo:
        return
    try:
        if undo.get('sgens'):
            net.sgen.drop(index=[i for i in undo['sgens'] if i in net.sgen.index], inplace=True)
            if hasattr(net, 'res_sgen') and net.res_sgen is not None:
                net.res_sgen.drop(index=[i for i in undo['sgens'] if i in net.res_sgen.index],
                                  inplace=True, errors='ignore')
    except Exception:
        pass
    try:
        if undo.get('gens'):
            net.gen.drop(index=[i for i in undo['gens'] if i in net.gen.index], inplace=True)
            if hasattr(net, 'res_gen') and net.res_gen is not None:
                net.res_gen.drop(index=[i for i in undo['gens'] if i in net.res_gen.index],
                                 inplace=True, errors='ignore')
    except Exception:
        pass
    if 'q_lims_flag' in undo:
        if undo['q_lims_flag'] is None:
            try:
                del net._electrisim_enforce_q_lims
            except AttributeError:
                pass
        else:
            net._electrisim_enforce_q_lims = undo['q_lims_flag']
    for idx in undo.get('ssc_on') or []:
        try:
            net.ssc.at[idx, 'in_service'] = True
        except Exception:
            pass


def _pq_snap_with_statcoms(snap, net, forced=None, gen_of=None):
    """
    Add STATCOM rows to a point snapshot (q_mvar in pandapower load convention, as in a normal
    load flow: negative = supplying Q) and hide the helper injections used to force them.
    """
    if not snap:
        return snap
    df = getattr(net, 'ssc', None)
    if df is None or df.empty:
        return snap
    for key in ('staticgenerators', 'generators'):
        rows = snap.get(key)
        if isinstance(rows, list):
            kept = [r for r in rows if not str(r.get('name') or '').startswith(
                (_PQ_STATCOM_SGEN_PREFIX, pp_el._SSC_EQUIV_PREFIX))]
            if kept:
                snap[key] = kept
            else:
                snap.pop(key, None)
    forced = forced or {}
    gen_of = gen_of or {}
    psc_of = getattr(net, '_electrisim_ssc_sgen', None) or {}
    psc_info = getattr(net, '_electrisim_ssc_info', None) or {}
    res = getattr(net, 'res_ssc', None)
    out = []
    for idx in df.index:
        row = {
            'name': str(df.at[idx, 'name']),
            'id': str(df.at[idx, 'id']) if 'id' in df.columns else str(idx),
        }
        bus = int(df.at[idx, 'bus'])
        try:
            row['vm_pu'] = float(net.res_bus.at[bus, 'vm_pu'])
            row['va_degree'] = float(net.res_bus.at[bus, 'va_degree'])
        except Exception:
            pass
        if idx in psc_of:
            try:
                row['q_mvar'] = -float(net.res_sgen.at[psc_of[idx], 'q_mvar'])
            except Exception:
                continue
            row['controller'] = (psc_info.get(idx) or {}).get('controller')
        elif idx in forced:
            row['q_mvar'] = -float(forced[idx])
            row['forced_to_rating'] = True
        elif idx in gen_of:
            try:
                row['q_mvar'] = -float(net.res_gen.at[gen_of[idx], 'q_mvar'])
            except Exception:
                continue
        elif res is not None and idx in res.index and bool(df.at[idx, 'in_service']):
            try:
                row['q_mvar'] = float(res.at[idx, 'q_mvar'])
                row['vm_internal_pu'] = float(res.at[idx, 'vm_internal_pu'])
                row['va_internal_degree'] = float(res.at[idx, 'va_internal_degree'])
            except Exception:
                continue
        else:
            continue
        out.append({k: (None if isinstance(v, float) and v != v else v) for k, v in row.items()})
    if out:
        snap['sscs'] = out
    return snap


def _pq_operating_point(base_net, ctx, p_val, statcom_side=None):
    """
    Park Controller as configured: one load flow at this P with the controller's own mode,
    setpoint, Control Q at and characteristics. Tap / shunt controllers stay active as ticked.
    Returns (result, reason). The result is kept even when it breaks a loading or voltage
    limit, because it is the plant's actual operating point.
    """
    work = _pq_acquire_work_net(ctx, base_net)
    _pq_clear_controllers(work)
    ctx['_statcom_force'] = statcom_side
    ctx['_statcom_undo'] = None
    try:
        ctx['_inplace_net'] = work
        ctx['_trial_baseline'] = _pq_input_baseline(work)
        r = _pq_eval_trial(work, ctx, p_val, 'max', 0.0, tap_bound=None, use_park=True)
        if not r or not r.get('converged'):
            return None, (r or {}).get('limit_reason') or 'divergence'
        r = _pq_finalize_kept(r, work, ctx)
        undo = ctx.get('_statcom_undo') or {}
        r['lf_snap'] = _pq_snap_with_statcoms(r.get('lf_snap'), work, undo.get('forced'), undo.get('gen_of'))
        return r, r.get('limit_reason')
    finally:
        _pq_unforce_statcoms(work, ctx.get('_statcom_undo'))
        _pq_detach_psc(work)
        ctx['_statcom_undo'] = None
        ctx['_statcom_force'] = None
        if ctx.get('_inplace_net') is work:
            ctx['_inplace_net'] = None


def _pq_edge_operating_point(base_net, ctx, p_val, side):
    """
    Capability edge with the Park Controller as configured: STATCOMs at their capacitive ('max')
    or inductive ('min') rating. When that load flow has no solution from the taps of the
    operating point (e.g. a single-P U-Q study, where no neighbouring P point has solved this
    edge yet), ramp the STATCOMs from 0 toward the rating. Each solved step files its tap
    positions for this edge, so the next step starts there. Returns (result, reason); the reason
    is 'divergence' when the full rating was not reached.
    """
    r, rsn = _pq_operating_point(base_net, ctx, p_val, statcom_side=side)
    if r is not None or (rsn or 'divergence') != 'divergence':
        return r, rsn
    best, best_frac, step = None, 0.0, 0.5
    try:
        for _ in range(16):
            if step < 0.02:
                break
            frac = min(1.0, best_frac + step)
            ctx['_statcom_frac'] = frac
            r_try, rsn_try = _pq_operating_point(base_net, ctx, p_val, statcom_side=side)
            _pq_emit(
                f'    P={p_val:.2f} MW STATCOM {side} ramp {frac:.0%}: '
                + ('solved' if r_try is not None else 'no solution'),
                ctx, progress=False)
            if r_try is not None:
                best, best_frac, rsn = r_try, frac, rsn_try
                if frac >= 1.0:
                    break
                step *= 1.5
            else:
                step /= 2.0
    finally:
        ctx['_statcom_frac'] = None
    if best is None:
        return None, 'divergence'
    return best, (rsn if best_frac >= 1.0 else 'divergence')


def _pq_check_operating_compliance(p_result, q_result, v_req):
    """
    True when every operating point inside the required P span lies between the
    required Qmin and Qmax at that P. None when there is no requirement.
    """
    if not v_req:
        return None
    req_p = v_req.get('p_mw', [])
    req_q_max = v_req.get('q_req_max_mvar', [])
    req_q_min = v_req.get('q_req_min_mvar', [])
    n = min(len(req_p), len(req_q_max), len(req_q_min))
    if n < 1:
        return False
    try:
        order = np.argsort([float(req_p[i]) for i in range(n)])
        rp = np.array([float(req_p[i]) for i in order], dtype=float)
        rmax = np.array([float(req_q_max[i]) for i in order], dtype=float)
        rmin = np.array([float(req_q_min[i]) for i in order], dtype=float)
    except (TypeError, ValueError):
        return False
    tol_mvar = 1e-4
    checked = 0
    for p_val, q_val in zip(p_result or [], q_result or []):
        try:
            pf = float(p_val)
        except (TypeError, ValueError):
            continue
        if pf < rp[0] - tol_mvar or pf > rp[-1] + tol_mvar:
            continue
        if q_val is None:
            return False
        qf = float(q_val)
        req_max_v = float(np.interp(pf, rp, rmax))
        req_min_v = float(np.interp(pf, rp, rmin))
        if qf > req_max_v + tol_mvar or qf < req_min_v - tol_mvar:
            return False
        checked += 1
    return True if checked else False


def _pq_output_table(voltage_levels, curves, pn, generator_oriented):
    rows = []
    if pn <= 0:
        return rows
    targets = [i * 0.1 * pn for i in range(1, 11)]
    sign = 1.0 if generator_oriented else -1.0
    for v in voltage_levels:
        v_key = f"{float(v):.4f}"
        curve = curves.get(v_key) or {}
        p_max = curve.get('p_max_mw') or curve.get('p_mw') or []
        p_min = curve.get('p_min_mw') or curve.get('p_mw') or []
        qmax = curve.get('q_max_mvar') or []
        qmin = curve.get('q_min_mvar') or []
        for tgt in targets:
            # Table P is % of Pn at the PCC axis (same as the red chart).
            p_tgt = sign * tgt
            qm = _pq_interp_q_in_span(p_tgt, p_max, qmax)
            qn = _pq_interp_q_in_span(p_tgt, p_min, qmin)
            if qm is None and qn is None:
                continue
            rows.append({
                'u_pu': round(float(v), 4),
                'p_mw': round(p_tgt, 4),
                'p_pu': round(tgt / pn, 4),
                'q_max_mvar': None if qm is None else round(qm, 4),
                'q_min_mvar': None if qn is None else round(qn, 4),
                'cosphi_over': None if qm is None else round(_pq_cosphi(p_tgt, qm), 4),
                'cosphi_under': None if qn is None else round(_pq_cosphi(p_tgt, qn), 4),
            })
    return rows


def _pq_blank_summary():
    return {
        'maxloading_cbl': 0.0,
        'maxloading_trf': 0.0,
        'umax_tot': 0.0,
        'umin_tot': 99.0,
        'ugenmax_tot': 0.0,
        'ugenmin_tot': 99.0,
        'ushntmax_tot': 0.0,
        'ushntmin_tot': 99.0,
        'trf_tap_max': -1e9,
        'trf_tap_min': 1e9,
    }


def _pq_merge_summary(dst, src):
    if not src:
        return
    for key in ('maxloading_cbl', 'maxloading_trf', 'umax_tot', 'ugenmax_tot', 'ushntmax_tot', 'trf_tap_max'):
        val = src.get(key)
        if isinstance(val, (int, float)):
            dst[key] = max(dst.get(key, val), val)
    for key in ('umin_tot', 'ugenmin_tot', 'ushntmin_tot', 'trf_tap_min'):
        val = src.get(key)
        if isinstance(val, (int, float)):
            dst[key] = min(dst.get(key, val), val)


def _pq_merge_tap_health(dst, src):
    if not src:
        return
    dst['points'] = (dst.get('points') or 0) + (src.get('points') or 0)
    dst['out_points'] = (dst.get('out_points') or 0) + (src.get('out_points') or 0)
    by = dst.setdefault('by_trafo', {})
    for name, entry in (src.get('by_trafo') or {}).items():
        cur = by.get(name)
        if cur is None:
            by[name] = dict(entry)
            continue
        cur['points'] = (cur.get('points') or 0) + (entry.get('points') or 0)
        cur['out_points'] = (cur.get('out_points') or 0) + (entry.get('out_points') or 0)
        cur['at_limit_points'] = (cur.get('at_limit_points') or 0) + (entry.get('at_limit_points') or 0)
        if abs(entry.get('worst_deviation_pu') or 0) > abs(cur.get('worst_deviation_pu') or 0):
            for key in ('worst_vm_pu', 'worst_deviation_pu', 'worst_p_mw', 'worst_case'):
                cur[key] = entry.get(key)


def _pq_file_prepared_snap(point_loadflows, v_key, side, snap, *p_vals):
    if not snap:
        return
    if v_key not in point_loadflows:
        point_loadflows[v_key] = {'q_max': {}, 'q_min': {}}
    side_map = point_loadflows[v_key].setdefault(side, {})
    for p_val in p_vals:
        if p_val is None:
            continue
        side_map[f"{float(p_val):.4f}"] = snap


def _pq_store_point_keys(point_loadflows, v_key, side, net_pf, *p_vals):
    """Serialize a solved net once and file it under every P key for that side."""
    snap = pp_el._rpc_serialize_solved_net(net_pf)
    if not snap:
        return
    if v_key not in point_loadflows:
        point_loadflows[v_key] = {'q_max': {}, 'q_min': {}}
    side_map = point_loadflows[v_key].setdefault(side, {})
    for p_val in p_vals:
        if p_val is None:
            continue
        side_map[f"{float(p_val):.4f}"] = snap


def _pq_sweep_voltage(net, ctx, v_pu, u_scale, p_points, i_park, tap_bounds, sign_out,
                      requirements, scale_requirement_to_pcc, pn, rc2, rc3, gen_info):
    """One PCC voltage: every P step, Q max and Q min. Safe to run beside other voltages."""
    local = dict(ctx)
    local['iLDF'] = [0]
    local['q_frac_hint'] = {}
    local['vm_seed'] = None
    local['tap_health'] = {'points': 0, 'out_points': 0, 'by_trafo': {}}
    local['v_applied'] = float(v_pu) * float(u_scale)
    summary = _pq_blank_summary()
    local['summary'] = summary
    warnings = []
    point_loadflows = {}
    v_key = f"{float(v_pu):.4f}"
    _pq_emit(
        f'  Voltage {v_pu} pu (applied {local["v_applied"]:.4f} pu)',
        local, progress=True)

    p_result, p_max_result, p_min_result, p_disp_result = [], [], [], []
    q_max_result, q_min_result = [], []
    op_p_result, op_q_result = [], []
    cos_over, cos_under = [], []
    limit_max_result, limit_min_result = [], []

    for p_val in p_points:
        _pq_check_cancel(local)
        qmax_cands = []
        qmin_cands = []
        max_rs = []
        min_rs = []
        reasons_max = []
        reasons_min = []
        configured = bool(local.get('park_configured'))
        statcom_env = configured and bool(local.get('statcoms'))
        r_op = None
        for bound in ((None,) if configured else tap_bounds):
            if configured:
                r_op, rsn_op = _pq_operating_point(
                    net, local, p_val, statcom_side='op' if statcom_env else None)
                if rsn_op:
                    reasons_max.append(rsn_op)
                if r_op and r_op.get('lf_snap') is not None:
                    _pq_update_tap_health(local, r_op.get('tap_recs'), p_val, bound, 'max')
                if statcom_env:
                    # Edges: STATCOMs at their capacitive / inductive rating, park as configured.
                    r_hi, rsn_hi = _pq_edge_operating_point(net, local, p_val, 'max')
                    r_lo, rsn_lo = _pq_edge_operating_point(net, local, p_val, 'min')
                    if rsn_hi:
                        reasons_max.append(rsn_hi)
                    if rsn_lo:
                        reasons_min.append(rsn_lo)
                else:
                    r_hi, r_lo = r_op, r_op
                qmax_cands.append(None if r_hi is None else r_hi.get('q_pcc'))
                qmin_cands.append(None if r_lo is None else r_lo.get('q_pcc'))
                max_rs.append(r_hi)
                min_rs.append(r_lo)
                continue
            rmax, _xmax, rsn_max, _ = _pq_search_one_side(
                net, local, p_val, 'max', i_park, bound)
            rmin, _xmin, rsn_min, _ = _pq_search_one_side(
                net, local, p_val, 'min', i_park, bound)
            qmax_cands.append(None if rmax is None else rmax.get('q_pcc'))
            qmin_cands.append(None if rmin is None else rmin.get('q_pcc'))
            max_rs.append(rmax)
            min_rs.append(rmin)
            if rsn_max:
                reasons_max.append(rsn_max)
            if rsn_min:
                reasons_min.append(rsn_min)
            if rmax and not rmax.get('unphysical') and (rmax.get('lf_snap') or rmax.get('net') is not None):
                if rmax.get('net') is not None:
                    _pq_update_summary(summary, rmax['net'], gen_info)
                _pq_update_tap_health(local, rmax.get('tap_recs'), p_val, bound, 'max')
            if rmin and not rmin.get('unphysical') and (rmin.get('lf_snap') or rmin.get('net') is not None):
                if rmin.get('net') is not None:
                    _pq_update_summary(summary, rmin['net'], gen_info)
                _pq_update_tap_health(local, rmin.get('tap_recs'), p_val, bound, 'min')

        q_max_pcc = qmax_cands[0]
        q_min_pcc = qmin_cands[0]
        if (rc2 or rc3) and len(qmax_cands) > 1:
            q_max_pcc = _pq_restrictive_qmax(qmax_cands[0], qmax_cands[1])
            q_min_pcc = _pq_restrictive_qmin(qmin_cands[0], qmin_cands[1])
            _pq_emit(
                f'    P={p_val:.2f} MW tap bounds: '
                f'Qmax [{_pq_fmt(qmax_cands[0])} | {_pq_fmt(qmax_cands[1])}] → {_pq_fmt(q_max_pcc)}  '
                f'Qmin [{_pq_fmt(qmin_cands[0])} | {_pq_fmt(qmin_cands[1])}] → {_pq_fmt(q_min_pcc)}',
                local, progress=True)
        r_max_used = _pq_r_matching_q(max_rs, q_max_pcc)
        r_min_used = _pq_r_matching_q(min_rs, q_min_pcc)

        if configured and not statcom_env and q_max_pcc is None:
            why = ', '.join(sorted(set(x for x in reasons_max if x))) or 'no converged load flow'
            _pq_emit(f'    Operating point failed at P={p_val:.2f} MW ({why})', local, progress=True)
        elif q_max_pcc is None:
            why = ', '.join(sorted(set(x for x in reasons_max if x))) or 'no converged load flow'
            _pq_emit(f'    Q_max failed at P={p_val:.2f} MW ({why})', local, progress=True)
        if q_min_pcc is None and (statcom_env or not configured):
            why = ', '.join(sorted(set(x for x in reasons_min if x))) or 'no converged load flow'
            _pq_emit(f'    Q_min failed at P={p_val:.2f} MW ({why})', local, progress=True)
        if q_max_pcc is not None and q_max_pcc < -1e-3 and not configured:
            _pq_emit(
                f'    WARNING: Q_max={q_max_pcc:.2f} Mvar is negative at P={p_val:.2f} MW '
                f'(overexcited plant Q should be ≥ 0 in generator convention).',
                local, progress=True)

        for rsn, side in ((reasons_max, 'max'), (reasons_min, 'min')):
            uniq = [x for x in rsn if x]
            if uniq and configured and not statcom_env:
                warnings.append(
                    f"V={v_pu}pu, P={p_val:.1f}MW: operating point breaks a limit "
                    f"({', '.join(sorted(set(uniq)))})"
                )
            elif uniq:
                words = {
                    'divergence': 'no load-flow solution beyond this Q: plant voltages collapse '
                                  '(full unit and STATCOM Q is not reachable at this grid voltage)',
                }
                warnings.append(
                    f"V={v_pu}pu, P={p_val:.1f}MW: Q_{side} limited "
                    f"({', '.join(words.get(x, x) for x in sorted(set(uniq)))})"
                )

        p_disp_plot = sign_out * float(p_val)
        p_plot_max = None
        p_plot_min = None
        if r_max_used and r_max_used.get('p_pcc') is not None:
            p_plot_max = float(sign_out) * float(r_max_used['p_pcc'])
        elif r_max_used and r_max_used.get('net') is not None:
            p_plot_max = _pq_pcc_plot_from_net(r_max_used['net'], local, sign_out)
        if r_min_used and r_min_used.get('p_pcc') is not None:
            p_plot_min = float(sign_out) * float(r_min_used['p_pcc'])
        elif r_min_used and r_min_used.get('net') is not None:
            p_plot_min = _pq_pcc_plot_from_net(r_min_used['net'], local, sign_out)
        if p_plot_max is None:
            p_plot_max = p_disp_plot
        if p_plot_min is None:
            p_plot_min = p_disp_plot

        qmax_plot = None if q_max_pcc is None else sign_out * float(q_max_pcc)
        qmin_plot = None if q_min_pcc is None else sign_out * float(q_min_pcc)

        p_max_r = round(float(p_plot_max), 4)
        p_min_r = round(float(p_plot_min), 4)

        snap_max = None if not r_max_used else r_max_used.get('lf_snap')
        snap_min = None if not r_min_used else r_min_used.get('lf_snap')
        if snap_max is not None:
            _pq_file_prepared_snap(point_loadflows, v_key, 'q_max', snap_max, p_val, p_max_r)
        elif r_max_used and r_max_used.get('net') is not None:
            _pq_store_point_keys(point_loadflows, v_key, 'q_max', r_max_used['net'], p_val, p_max_r)
        if snap_min is not None:
            _pq_file_prepared_snap(point_loadflows, v_key, 'q_min', snap_min, p_val, p_min_r)
        elif r_min_used and r_min_used.get('net') is not None:
            _pq_store_point_keys(point_loadflows, v_key, 'q_min', r_min_used['net'], p_val, p_min_r)

        if statcom_env:
            q_op = None if (r_op is None or r_op.get('q_pcc') is None) else sign_out * float(r_op['q_pcc'])
            p_op = p_disp_plot
            if r_op and r_op.get('p_pcc') is not None:
                p_op = float(sign_out) * float(r_op['p_pcc'])
            op_p_result.append(round(float(p_op), 4))
            op_q_result.append(None if q_op is None else round(q_op, 4))
            if r_op and r_op.get('lf_snap') is not None:
                _pq_file_prepared_snap(point_loadflows, v_key, 'q_op', r_op['lf_snap'], p_val, round(float(p_op), 4))
            _pq_emit(
                f'    → P_disp={p_val:.2f} MW  operating point: Q={_pq_fmt(None if q_op is None else q_op / sign_out)} Mvar; '
                f'STATCOM range at PCC: {_pq_fmt(q_min_pcc)} … {_pq_fmt(q_max_pcc)} Mvar  (LF={local["iLDF"][0]})',
                local, progress=True)
        p_pcc_log = p_plot_max / sign_out if sign_out else p_plot_max
        if configured and statcom_env:
            pass
        elif configured:
            _pq_emit(
                f'    → P_disp={p_val:.2f} MW  P_PCC={_pq_fmt(p_pcc_log)} MW '
                f'operating point: Q={_pq_fmt(q_max_pcc)} Mvar  (LF={local["iLDF"][0]})',
                local, progress=True)
        else:
            _pq_emit(
                f'    → P_disp={p_val:.2f} MW  P_PCC={_pq_fmt(p_pcc_log)} MW '
                f'envelope: Q_max={_pq_fmt(q_max_pcc)} Mvar, '
                f'Q_min={_pq_fmt(q_min_pcc)} Mvar  (LF={local["iLDF"][0]})',
                local, progress=True)
        p_max_result.append(p_max_r)
        p_min_result.append(p_min_r)
        p_result.append(p_max_r)
        p_disp_result.append(round(p_disp_plot, 4))
        q_max_result.append(None if qmax_plot is None else round(qmax_plot, 4))
        q_min_result.append(None if qmin_plot is None else round(qmin_plot, 4))
        cos_over.append(None if qmax_plot is None else round(_pq_cosphi(p_max_r, qmax_plot), 4))
        cos_under.append(None if qmin_plot is None else round(_pq_cosphi(p_min_r, qmin_plot), 4))
        limit_max_result.append(_pq_limit_payload(_pq_r_matching_q(max_rs, q_max_pcc)))
        limit_min_result.append(_pq_limit_payload(_pq_r_matching_q(min_rs, q_min_pcc)))

    curve = {
        'p_mw': p_result,
        'p_max_mw': p_max_result,
        'p_min_mw': p_min_result,
        'p_dispatch_mw': p_disp_result,
        'q_max_mvar': q_max_result,
        'q_min_mvar': q_min_result,
        'cosphi_over': cos_over,
        'cosphi_under': cos_under,
        'limit_max': limit_max_result,
        'limit_min': limit_min_result,
    }
    if local.get('park_configured') and local.get('statcoms'):
        # Envelope: STATCOMs at their ratings. The configured operating point is drawn on top.
        curve['statcom_envelope'] = True
        curve['operating_line'] = {'p_mw': op_p_result, 'q_mvar': op_q_result}
    elif local.get('park_configured'):
        # Q_max and Q_min hold the same operating point in this mode.
        curve['operating'] = True
    pmax_pcc = _pq_pmax_pcc_for_req(curve)
    v_req = requirements.get(v_key) if requirements else None
    if (
        scale_requirement_to_pcc
        and v_req and pn > 0 and pmax_pcc and pmax_pcc > 0
    ):
        k = float(pmax_pcc) / float(pn)
        v_req = _pq_scale_requirement(v_req, k)
        requirements[v_key] = v_req
        _pq_emit(
            f'  Grid-code envelope: Pmax at PCC={pmax_pcc:.3f} MW '
            f'(Pn={pn:.3f} MW, scale={k:.4f})',
            local, progress=True)
    elif v_req and pn > 0:
        _pq_emit(
            f'  Grid-code envelope: requirement held at Pn={pn:.3f} MW '
            f'(Pmax at PCC={_pq_fmt(pmax_pcc)} MW, not used as Pn)',
            local, progress=True)
    if v_req:
        pmax_cmp = [sign_out * p for p in p_max_result]
        pmin_cmp = [sign_out * p for p in p_min_result]
        qmax_cmp = [None if q is None else sign_out * q for q in q_max_result]
        qmin_cmp = [None if q is None else sign_out * q for q in q_min_result]
        if local.get('park_configured') and not local.get('statcoms'):
            compliance_val = _pq_check_operating_compliance(pmax_cmp, qmax_cmp, v_req)
        else:
            compliance_val = _pq_check_compliance(
                pmax_cmp, qmax_cmp, pmin_cmp, qmin_cmp, v_req)
    else:
        compliance_val = None

    return {
        'v_key': v_key,
        'curve': curve,
        'compliance': compliance_val,
        'point_loadflows': point_loadflows.get(v_key) or {'q_max': {}, 'q_min': {}},
        'warnings': warnings,
        'summary': summary,
        'tap_health': local['tap_health'],
        'lf_count': local['iLDF'][0],
    }


def grid_code_pq_capability(net, pq_params, in_data=None):
    """
    P-Q capability at the PoC. Returns JSON string:
      { "grid_code_pq_results": { ... same curve/compliance shape as RPC, plus summary } }
    """
    # Plant Supervisory Controller picked in the dialog: keep only that one ('' = none).
    if isinstance(in_data, dict) and 'psc_cell_id' in (pq_params or {}):
        _sel = str(pq_params.get('psc_cell_id') or '')
        in_data = {
            k: v for k, v in in_data.items()
            if not (isinstance(v, dict) and str(v.get('typ') or '').startswith('PlantSupervisoryController')
                    and str(v.get('cell_id') or v.get('id') or '') != _sel)
        }
    try:
        pcc_bus_name = pq_params.get('pcc_bus_name')
        ext_grid_name = pq_params.get('ext_grid_name')
        generator_names = pq_params.get('generator_names') or []
        exclude_names = pq_params.get('exclude_generator_names') or []
        shunt_names = pq_params.get('shunt_names') or []
        shunts_off = _pq_apply_shunt_selection(net, shunt_names)
        # Older dialogs send no ssc_names: keep every STATCOM as on the diagram.
        sscs_off = _pq_apply_ssc_selection(net, pq_params.get('ssc_names'), in_data)
        voltage_levels = list(pq_params.get('voltage_levels') or [1.0])
        q_mode = pq_params.get('q_capability_mode') or 'from_rating'
        i_park = _pq_bool(pq_params.get('i_park_ctrl'), False)
        park_configured = str(pq_params.get('q_dispatch_mode') or '') == 'park_configured'
        if park_configured:
            i_park = True
        park_name = pq_params.get('park_controller_name')
        park_id = pq_params.get('park_controller_id')
        i_trf = _pq_bool(pq_params.get('i_trf_ctrl'), False)
        i_trf3 = _pq_bool(pq_params.get('i_trf3w_ctrl'), False)
        if not i_trf3:
            i_trf3 = _pq_bool(pq_params.get('run_control_trafo3w'), False)
        shnt_ctrl = _pq_bool(pq_params.get('shnt_ctrl'), False)
        rcs = _pq_bool(pq_params.get('run_control_shunt'), False)
        limit_overloads = _pq_bool(pq_params.get('limit_overloads'), False)
        max_loading = _pq_float(pq_params.get('max_loading_percent'), 100.0)
        lim_q_uprot = _pq_bool(pq_params.get('lim_q_uprot'), False)
        u_max_prot = _pq_float(pq_params.get('u_max_prot'), 1.15)
        u_min_prot = _pq_float(pq_params.get('u_min_prot'), 0.85)
        i_show_pq0 = _pq_bool(pq_params.get('i_show_pq0'), True)
        i_output = _pq_bool(pq_params.get('i_output'), False)
        generator_oriented = _pq_bool(pq_params.get('generator_oriented'), True)
        i_curve_mw = _pq_bool(pq_params.get('i_curve_mw'), True)
        i_curve_mvar = _pq_bool(pq_params.get('i_curve_mvar'), True)
        requirements = pq_params.get('requirements') or None
        scale_requirement_to_pcc = _pq_bool(pq_params.get('scale_requirement_to_pcc'), True)
        verbose = _pq_bool(pq_params.get('verbose_iwamoto'), False)
        progress_cb = pq_params.get('_progress_callback')
        rc2 = bool(i_trf)
        rc3 = bool(i_trf3)

        print('=== Grid Code Compliance (P-Q) starting ===', flush=True)

        pcc_bus_idx = None
        for idx in net.bus.index:
            if net.bus.at[idx, 'name'] == pcc_bus_name:
                pcc_bus_idx = idx
                break
        if pcc_bus_idx is None:
            return json.dumps({'error': f'PCC bus "{pcc_bus_name}" not found in network'}, separators=(',', ':'))

        ext_grid_idx = None
        for idx in net.ext_grid.index:
            if net.ext_grid.at[idx, 'name'] == ext_grid_name:
                ext_grid_idx = idx
                break
        if ext_grid_idx is None:
            return json.dumps({'error': f'External grid "{ext_grid_name}" not found in network'}, separators=(',', ':'))

        storage_names = list(pq_params.get('storage_names') or [])
        sgen_indices = [idx for idx in net.sgen.index if net.sgen.at[idx, 'name'] in generator_names]
        storage_indices = []
        if hasattr(net, 'storage') and net.storage is not None and not net.storage.empty:
            storage_indices = [idx for idx in net.storage.index if str(net.storage.at[idx, 'name']) in storage_names]

        if not sgen_indices and not storage_indices:
            return json.dumps({'error': 'No matching generators or storage units found in the network'}, separators=(',', ':'))

        gen_info = []
        for idx in sgen_indices:
            sn = net.sgen.at[idx, 'sn_mva'] if 'sn_mva' in net.sgen.columns and not pd.isna(net.sgen.at[idx, 'sn_mva']) else 0
            p_mw = float(net.sgen.at[idx, 'p_mw']) if not pd.isna(net.sgen.at[idx, 'p_mw']) else 0.0
            sn_f = float(sn) if sn and sn > 0 else 0.0
            p_rated = p_mw if p_mw > 0 else sn_f
            gen_info.append({
                'type': 'sgen',
                'idx': idx,
                'name': net.sgen.at[idx, 'name'],
                'p_rated_mw': p_rated,
                'sn_mva': sn_f if sn_f > 0 else p_rated,
            })
        for idx in storage_indices:
            sn = net.storage.at[idx, 'sn_mva'] if 'sn_mva' in net.storage.columns and not pd.isna(net.storage.at[idx, 'sn_mva']) else 0
            sn_f = float(sn) if sn and sn > 0 else 0.0
            caps = [sn_f] if sn_f > 0 else []
            try:
                mx = float(net.storage.at[idx, 'max_p_mw'])
                if mx > 0:
                    caps.append(mx)
            except Exception:
                pass
            try:
                mn = float(net.storage.at[idx, 'min_p_mw'])
                if abs(mn) > 0:
                    caps.append(abs(mn))
            except Exception:
                pass
            # Operating p_mw is often 0 on the diagram; the nameplate that
            # actually limits the sweep is min(Sn, charge Pmax, discharge Pmax),
            # which includes Battery DC Pmax when the wizard wrote it onto
            # max_p_mw / min_p_mw.
            p_rated = min(caps) if caps else 0.0
            gen_info.append({
                'type': 'storage',
                'idx': idx,
                'name': net.storage.at[idx, 'name'],
                'p_rated_mw': p_rated,
                'sn_mva': sn_f if sn_f > 0 else p_rated,
            })
        total_installed_mw = sum(g['p_rated_mw'] for g in gen_info)
        if total_installed_mw <= 0:
            return json.dumps(
                {'error': 'Total installed capacity is zero. Set ratings on storage or generators.'},
                separators=(',', ':'))

        pn = _pq_float(pq_params.get('pn_mw'), 0.0)
        if pn <= 0:
            pn = total_installed_mw
        un = _pq_float(pq_params.get('un_kv'), 0.0)
        uc = _pq_float(pq_params.get('uc_kv'), 0.0)
        if un <= 0:
            try:
                un = float(net.bus.at[pcc_bus_idx, 'vn_kv'])
            except Exception:
                un = 1.0
        if uc <= 0:
            uc = un
        u_scale = (uc / un) if un > 0 else 1.0

        p_points = _pq_p_sweep(
            pn,
            pq_params.get('p_start_pct', 0),
            pq_params.get('p_step_pct', 10),
            pq_params.get('p_end_pct', 100),
            int(pq_params.get('i_op_range') or 0),
        )
        p_points = _pq_merge_extra_p(p_points, pq_params.get('extra_p_mw'))
        q_step_pct = abs(_pq_float(pq_params.get('q_step_pct'), 0.5))
        q_step_mw = (q_step_pct / 100.0) * pn

        pcc_bus_friendly = pcc_bus_name
        if hasattr(net, 'user_friendly_names') and pcc_bus_name in net.user_friendly_names:
            pcc_bus_friendly = net.user_friendly_names[pcc_bus_name]

        warnings_list = []
        extra_parks = []
        for park in pp_el._electrisim_collect_park_payloads(in_data or {}):
            if i_park and _pq_match_park(park, park_name, park_id):
                continue
            extra_parks.append(str(park.get('name') or 'ParkController'))
        if extra_parks:
            warnings_list.append(
                'Park controllers on the diagram were taken out of service for this study so they '
                'cannot overwrite Q setpoints: ' + ', '.join(extra_parks)
            )
        if i_park:
            parks = []
            for _k, el in (in_data or {}).items():
                if isinstance(el, dict) and str(el.get('typ') or '').startswith('ParkController'):
                    parks.append(el)
            chosen = [p for p in parks if _pq_match_park(p, park_name, park_id)]
            if not chosen:
                return json.dumps(
                    {'error': 'Park controller is active but the selected Park Controller was not found in the network payload.'},
                    separators=(',', ':'))
            park0 = chosen[0]
            if not pp_el._park_truthy(park0.get('enabled', True), True):
                warnings_list.append(
                    f"Park Controller '{park0.get('name')}' is disabled on the diagram; the study still uses it because Park controller active is on."
                )
            machines = pp_el._park_parse_json_list(park0.get('machines_json'))
            connected = [m for m in machines if m and pp_el._park_truthy(m.get('connected', True), True)]
            connected_names = {str(m.get('name') or '') for m in connected}
            sgen_names = {str(net.sgen.at[i, 'name']) for i in sgen_indices}
            ufn = getattr(net, 'user_friendly_names', {}) or {}
            friendly_to_tech = {str(v): str(k) for k, v in ufn.items()}
            unresolved = []
            for n in connected_names:
                if n in sgen_names or n in generator_names:
                    continue
                tech = friendly_to_tech.get(n)
                if tech and (tech in sgen_names or tech in generator_names):
                    continue
                unresolved.append(n)
            if unresolved:
                warnings_list.append(
                    'Park machines not resolved as static generators / wind turbines: ' + ', '.join(unresolved)
                )

        if q_mode == 'from_sgen_curve':
            if not any(pp_el._rpc_sgen_has_q_curve(net, g['idx']) for g in gen_info):
                warnings_list.append(
                    'Q mode "from_sgen_curve": no selected unit has an active P–Q curve. '
                    'Using circular √(S_n²−P²) fallback.'
                )

        tc2_list = getattr(net, 'trafo_discrete_tap_controllers', None) or []
        tc3_list = getattr(net, 'trafo3w_discrete_tap_controllers', None) or []
        shc_list = getattr(net, 'shunt_discrete_controllers', None) or []
        lfc_list = getattr(net, 'line_flow_shunt_controllers', None) or []
        tc2_names = []
        tc3_names = []
        for row in tc2_list:
            try:
                tc2_names.append(_pq_trafo_display_name(net, net.trafo, row[0]))
            except Exception:
                pass
        for row in tc3_list:
            try:
                tc3_names.append(_pq_trafo_display_name(net, net.trafo3w, row[0]))
            except Exception:
                pass
        applied_2w = tc2_list if rc2 else []
        applied_3w = tc3_list if rc3 else []
        applied_shc = shc_list if rcs else []
        applied_lfc = lfc_list if rcs else []
        tc_names = []
        if rc2:
            tc_names.extend(tc2_names)
        if rc3:
            tc_names.extend(tc3_names)
        has_applicable = bool(applied_2w or applied_3w or applied_shc or applied_lfc)
        if i_trf and not tc2_list:
            warnings_list.append(
                'Two-winding transformer tap control is on, but no two-winding transformer '
                'has Discrete tap control enabled on the diagram.'
            )
        if i_trf3 and not tc3_list:
            warnings_list.append(
                'Three-winding transformer tap control is on, but no three-winding transformer '
                'has Discrete tap control enabled on the diagram.'
            )
        if rcs and not shc_list and not lfc_list:
            warnings_list.append(
                'Shunt reactor control is on, but no DiscreteShuntController or Line P→shunt '
                'step is configured on the diagram.'
            )

        iLDF = [0]
        _pq_idle_uncontrollable_statcoms(net)
        ctx = {
            'ext_grid_idx': ext_grid_idx,
            'pcc_bus_idx': pcc_bus_idx,
            'pcc_bus_name': pcc_bus_name,
            'gen_info': gen_info,
            'exclude_names': exclude_names,
            'shunt_names': set(shunt_names or []),
            'q_mode': q_mode,
            'in_data': in_data or {},
            'park_name': park_name,
            'park_id': park_id,
            'park_configured': park_configured,
            'statcoms': _pq_rated_statcoms(net) if park_configured else [],
            'local_statcoms': [] if park_configured else _pq_prepare_local_statcoms(net),
            'has_psc': bool(park_configured and pp_el._electrisim_collect_psc_payloads(in_data)),
            'psc_reactors': _pq_psc_reactors(net, in_data) if park_configured else None,
            'verbose': verbose,
            'rc2': rc2,
            'rc3': rc3,
            'rcs': rcs,
            'limit_overloads': limit_overloads,
            'max_loading': max_loading,
            'lim_q_uprot': lim_q_uprot,
            'u_max_prot': u_max_prot,
            'u_min_prot': u_min_prot,
            'shnt_ctrl': shnt_ctrl,
            'q_step_mw': q_step_mw,
            'pn_mw': pn,
            'iLDF': iLDF,
            'v_applied': 1.0,
            'progress_cb': progress_cb,
            'cancel_event': pq_params.get('_cancel_event'),
            'tap_health': {'points': 0, 'out_points': 0, 'by_trafo': {}},
        }
        _pq_capture_tap_bands(net)

        ufn_all = getattr(net, 'user_friendly_names', None) or {}
        _pq_emit('=== Grid Code Compliance (P-Q) ===', ctx, progress=True)
        if shunts_off:
            _pq_emit(
                '  Additional shunts out of service (not ticked): ' + ', '.join(shunts_off),
                ctx, progress=True)
        else:
            _pq_emit('  Additional shunts: all ticked shunts stay in service', ctx, progress=True)
        if sscs_off:
            _pq_emit('  STATCOMs out of service (not ticked): ' + ', '.join(sscs_off), ctx, progress=True)
        if ctx.get('statcoms'):
            try:
                slack_buses = {int(net.ext_grid.at[eg, 'bus']) for eg in net.ext_grid.index}
            except Exception:
                slack_buses = set()
            on_slack = [
                _pq_statcom_display_name(net, i, in_data, ufn_all)
                for i, b, _qx, _qn in ctx['statcoms'] if int(b) in slack_buses
            ]
            if on_slack:
                warnings_list.append(
                    'STATCOM on the external grid bus (' + ', '.join(on_slack) + '): the external grid fixes '
                    'that bus voltage, so the STATCOM cannot regulate it. Its Q at the PCC is counted, the '
                    'red edges use its Q rating, and the operating point holds it at 0 Mvar. Connect it to a '
                    'plant-side bus for voltage control.'
                )
            _pq_emit(
                '  STATCOMs swept to their Q rating: ' + ', '.join(
                    f'{_pq_statcom_display_name(net, i, in_data, ufn_all)} [{qn:g} … +{qx:g} Mvar]'
                    for i, _b, qx, qn in ctx['statcoms']),
                ctx, progress=True)
        _pq_emit(
            f'  PCC={pcc_bus_friendly}  ExtGrid={ext_grid_name}  Pn={pn:.3f} MW  '
            f'Qstep={q_step_mw:.4f} Mvar ({q_step_pct:g}% Pn)  units={len(gen_info)}',
            ctx, progress=True)
        tap_bits = []
        if rc2:
            tap_bits.append(f'2w={len(applied_2w)} DiscreteTap: {", ".join(tc2_names) or "none"}')
        else:
            tap_bits.append('2w=OFF')
        if rc3:
            tap_bits.append(f'3w={len(applied_3w)} DiscreteTap: {", ".join(tc3_names) or "none"}')
        else:
            tap_bits.append('3w=OFF')
        shunt_bits = []
        if rcs:
            shunt_bits.append(
                f'DiscreteShunt={len(applied_shc)} LineP={len(applied_lfc)}'
            )
        else:
            shunt_bits.append('controllers=OFF')
        shunt_bits.append('on/off=' + ('ON' if shnt_ctrl else 'OFF'))
        _pq_emit(
            f'  Q dispatch={"Park as configured" if park_configured else ("Park" if i_park else "Local")} '
            f'{park_name or "—"}  '
            f'tap {" ".join(tap_bits)}  shunt {" ".join(shunt_bits)}',
            ctx, progress=True)
        q0p, q0n = _pq_plant_q_caps(net, gen_info, 0.0, q_mode, exclude_names, in_data)
        qnp, qnn = _pq_plant_q_caps(net, gen_info, pn, q_mode, exclude_names, in_data)
        _pq_emit(
            f'  Plant Q capability: at P=0  Qmax={q0p:.2f} / Qmin=-{q0n:.2f} Mvar; '
            f'at P=Pn  Qmax={qnp:.2f} / Qmin=-{qnn:.2f} Mvar',
            ctx, progress=True)
        for g in gen_info:
            qp, qn = pp_el._rpc_sgen_q_caps(net, g['idx'], 0.0, g['sn_mva'], q_mode)
            disp = str(ufn_all.get(g['name'], g['name']))
            _pq_emit(
                f'    {disp}  sn={g["sn_mva"]:.3f} MVA  P_rated={g["p_rated_mw"]:.3f} MW  '
                f'Q(P=0)=+{qp:.2f}/-{qn:.2f} Mvar',
                ctx, progress=False)
        _pq_emit(
            '  P sweep (' + str(len(p_points)) + ' pts): '
            + ', '.join(f'{p:.2f}' for p in p_points) + ' MW',
            ctx, progress=True)
        _pq_emit(
            '  Voltage levels: '
            + ', '.join(f'{v:g}' for v in voltage_levels)
            + f' pu  Uc/Un={u_scale:.4f}',
            ctx, progress=True)

        tap_bounds = ('lower', 'upper') if (rc2 or rc3) else (None,)
        sign_out = 1.0 if generator_oriented else -1.0

        curves = {}
        point_loadflows = {}
        compliance = {}
        summary = {
            'maxloading_cbl': 0.0,
            'maxloading_trf': 0.0,
            'umax_tot': 0.0,
            'umin_tot': 99.0,
            'ugenmax_tot': 0.0,
            'ugenmin_tot': 99.0,
            'ushntmax_tot': 0.0,
            'ushntmin_tot': 99.0,
            'trf_tap_max': -1e9,
            'trf_tap_min': 1e9,
        }

        t_sweep = time.perf_counter()

        def _run_voltage(v_pu, net_v):
            return _pq_sweep_voltage(
                net_v, ctx, v_pu, u_scale, p_points, i_park, tap_bounds, sign_out,
                requirements, scale_requirement_to_pcc, pn, rc2, rc3, gen_info)

        n_v = len(voltage_levels)
        workers = 1 if n_v < 2 else min(n_v, os.cpu_count() or 2, 4)
        if workers == 1:
            swept = [_run_voltage(v, net) for v in voltage_levels]
        else:
            _pq_emit(
                f'  Running {n_v} voltage levels in parallel ({workers} workers)',
                ctx, progress=True)
            nets = [deepcopy(net) for _v in voltage_levels]
            swept_by_i = {}
            with ThreadPoolExecutor(max_workers=workers) as pool:
                fut_map = {
                    pool.submit(_run_voltage, voltage_levels[i], nets[i]): i
                    for i in range(n_v)
                }
                try:
                    for fut in as_completed(fut_map):
                        swept_by_i[fut_map[fut]] = fut.result()
                except GridCodePqCancelled:
                    ev = ctx.get('cancel_event')
                    if ev is not None and hasattr(ev, 'set'):
                        ev.set()
                    raise
            swept = [swept_by_i[i] for i in range(n_v)]

        for item in swept:
            v_key = item['v_key']
            curves[v_key] = item['curve']
            compliance[v_key] = item['compliance']
            point_loadflows[v_key] = item['point_loadflows']
            warnings_list.extend(item['warnings'])
            _pq_merge_summary(summary, item['summary'])
            _pq_merge_tap_health(ctx['tap_health'], item['tap_health'])
            iLDF[0] += item['lf_count']
        elapsed_s = round(time.perf_counter() - t_sweep, 1)
        _pq_emit(
            f'  P-Q sweep finished in {elapsed_s:.1f} s ({iLDF[0]} load flows)',
            ctx, progress=True)

        pq0 = None
        if i_show_pq0:
            net0 = deepcopy(net)
            _pq_clear_controllers(net0)
            _pq_apply_tap_family_filter(net0, ctx)
            for g in gen_info:
                _pq_set_gen_pq(net0, g, 0.0, 0.0)
            net0.ext_grid.at[ext_grid_idx, 'vm_pu'] = float(voltage_levels[0]) * u_scale if voltage_levels else 1.0
            if ctx.get('statcoms'):
                # Same STATCOM model as the operating points (pandapower's SSC often diverges here).
                _pq_force_statcoms(net0, 'op', ctx['statcoms'])
            for _i, sg, _qx, _qn in ctx.get('local_statcoms') or []:
                if sg in net0.sgen.index:
                    net0.sgen.at[sg, 'q_mvar'] = 0.0
            iLDF[0] += 1
            if _pq_run_pf(
                    net0, verbose, rc2, rc3, rcs, force_control=False,
                    cancel_event=ctx.get('cancel_event')):
                p0 = _pq_pcc_p(net0, pcc_bus_idx, ext_grid_idx)
                q0 = _pq_pcc_q(net0, pcc_bus_idx, ext_grid_idx)
                # Residual exchange at the PCC with plant units off. This is not the
                # P=0 capability on the red envelope (units still supplying Q there).
                pq0 = {
                    'p_mw': round(float(p0), 4),
                    'q_mvar': round(float(q0), 4),
                }
                _pq_emit(
                    f'  Units off (not the P=0 envelope): P={p0:.3f} MW  Q={q0:.3f} Mvar',
                    ctx, progress=True)
            else:
                _pq_emit('  Units off (PQ0): load flow failed', ctx, progress=True)

        tap_health = ctx['tap_health']
        tap_warnings = _pq_tap_health_warnings(tap_health)
        if tap_warnings:
            _pq_emit('  Tap control could not hold the configured voltage band:', ctx,
                     progress=True)
            for msg in tap_warnings:
                _pq_emit(f'    {msg}', ctx, progress=True)
            warnings_list.extend(tap_warnings)
        elif tap_health['points']:
            _pq_emit(
                f'  Tap control held the configured voltage band at all '
                f'{tap_health["points"]} evaluated envelope points',
                ctx, progress=True)

        if summary['umin_tot'] > 90:
            summary['umin_tot'] = None
        if summary['ugenmin_tot'] > 90:
            summary['ugenmin_tot'] = None
        if summary['ushntmin_tot'] > 90:
            summary['ushntmin_tot'] = None
        if summary['trf_tap_min'] > 1e8:
            summary['trf_tap_min'] = None
        if summary['trf_tap_max'] < -1e8:
            summary['trf_tap_max'] = None
        for k in list(summary.keys()):
            if isinstance(summary[k], float):
                summary[k] = round(summary[k], 4)

        output_table = _pq_output_table(voltage_levels, curves, pn, generator_oriented) if i_output else []

        pmax_pcc_by_voltage = {}
        pmax_pcc_vals = []
        for vk, curve in (curves or {}).items():
            pm = _pq_pmax_pcc_for_req(curve)
            pmax_pcc_by_voltage[vk] = None if pm is None else round(float(pm), 4)
            if pm:
                pmax_pcc_vals.append(float(pm))
        pmax_pcc_mw = round(max(pmax_pcc_vals), 4) if pmax_pcc_vals else None

        result = {
            'grid_code_pq_results': {
                'voltage_levels': [round(float(v), 4) for v in voltage_levels],
                'curves': curves,
                'point_loadflows': point_loadflows,
                'requirements': requirements if requirements else {},
                'requirements_base': (
                    'pcc_pmax' if (scale_requirement_to_pcc and requirements and pmax_pcc_mw and pn > 0) else
                    ('pn' if requirements else None)
                ),
                'compliance': compliance,
                'warnings': warnings_list,
                'total_installed_mw': round(total_installed_mw, 4),
                'pn_mw': round(pn, 4),
                'pmax_pcc_mw': pmax_pcc_mw,
                'pmax_pcc_by_voltage': pmax_pcc_by_voltage,
                'un_kv': round(un, 4),
                'uc_kv': round(uc, 4),
                'pcc_bus_name': pcc_bus_friendly,
                'generator_count': len(gen_info),
                'grid_code_template_name': pq_params.get('grid_code_template_name'),
                'grid_code_template_key': pq_params.get('grid_code_template_key'),
                'q_capability_mode': q_mode,
                'i_park_ctrl': i_park,
                'q_dispatch_mode': 'park_configured' if park_configured else ('park' if i_park else 'local'),
                'statcom_envelope': bool(ctx.get('statcoms')),
                'statcom_names': [
                    _pq_statcom_display_name(net, i, in_data, ufn_all)
                    for i, _b, _qx, _qn in (ctx.get('statcoms') or [])
                ],
                'park_controller_name': park_name,
                'i_curve_mw': i_curve_mw,
                'i_curve_mvar': i_curve_mvar,
                'generator_oriented': generator_oriented,
                'i_output': i_output,
                'output_table': output_table,
                'pq0': pq0,
                'summary': summary,
                'load_flow_count': iLDF[0],
                'elapsed_s': elapsed_s,
                'tap_changer_control': {
                    'run_control_requested': bool(rc2 or rc3 or rcs or shnt_ctrl),
                    'controllers_applied': bool(has_applicable),
                    'transformer_count': len(applied_2w) + len(applied_3w),
                    'transformer_2w_count': len(applied_2w),
                    'transformer_3w_count': len(applied_3w),
                    'shunt_controller_count': len(applied_shc),
                    'shunt_line_flow_count': len(applied_lfc),
                    'transformer_names': tc_names,
                    'transformer_2w_names': tc2_names if rc2 else [],
                    'transformer_3w_names': tc3_names if rc3 else [],
                    'i_trf_ctrl': rc2,
                    'i_trf3w_ctrl': rc3,
                    'run_control_shunt': rcs,
                    'shnt_ctrl': shnt_ctrl,
                    'only_discrete_tap_enabled': True,
                    'points_checked': tap_health['points'],
                    'points_out_of_band': tap_health['out_points'],
                    'per_transformer': list(tap_health['by_trafo'].values()),
                },
                'pcc_q_convention': (
                    'Red: net P and Q at the PCC after power flow. '
                    'Blue: grid-code envelope in p.u. of Pmax at the PCC '
                    '(measured net P, not generator Pn). '
                    + (
                        'Plant Q follows the Park Controller exactly as configured on the diagram; '
                        'each point is the operating point at that P, not a capability limit.'
                        if park_configured else
                        'Plant Q is dispatched as constant Q at the point of connection '
                        'via the Park Controller (BinarySearchControl).'
                        if i_park else
                        'Plant Q is set locally on each static generator / wind turbine '
                        'from its P–Q capability (or circular S_n–P fallback).'
                    )
                ),
            }
        }
        _pq_emit(
            f'=== Grid Code Compliance (P-Q) finished: {iLDF[0]} load flows ===',
            ctx, progress=True)
        return json.dumps(result, default=pp_el._json_serialize_default, separators=(',', ':'))

    except GridCodePqCancelled:
        print('=== Grid Code Compliance (P-Q) stopped by user ===', flush=True)
        raise
    except Exception as e:
        traceback.print_exc()
        return json.dumps({'error': f'Grid Code Compliance (P-Q) failed: {str(e)}'}, separators=(',', ':'))
