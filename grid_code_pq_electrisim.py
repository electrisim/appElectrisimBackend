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

from copy import deepcopy
import json
import math
import sys
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

    return {
        'p_mw': _s(req.get('p_mw')),
        'q_req_max_mvar': _s(req.get('q_req_max_mvar')),
        'q_req_min_mvar': _s(req.get('q_req_min_mvar')),
    }


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
        is_park = name in ('BinarySearchControl', 'DroopControl')
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


def _pq_try_runpp(net_pf, init, max_iteration, run_control, q_kw):
    try:
        pp.runpp(
            net_pf, algorithm='nr', calculate_voltage_angles=True,
            init=init, max_iteration=max_iteration,
            run_control=run_control, **q_kw)
        return True
    except GridCodePqCancelled:
        raise
    except Exception:
        return False


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
    inits = ('auto', 'dc', 'flat')
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
        net_pf._pq_pf_stage = 'park+tap'
        return True

    if rc:
        ok = _pq_try_inits(net_pf, q_kw, inits, 100)
        net_pf._pq_pf_stage = 'ctrl' if ok else 'div:ctrl'
        return ok

    strategies = [
        {'algorithm': 'nr', 'init': 'auto', 'max_iteration': 50},
        {'algorithm': 'nr', 'init': 'dc', 'max_iteration': 80},
        {'algorithm': 'nr', 'init': 'flat', 'max_iteration': 80},
        {'algorithm': 'iwamoto_nr', 'init': 'dc', 'max_iteration': 80},
    ]
    for s in strategies:
        algo = s['algorithm']
        try:
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
    net_try = deepcopy(base_net)
    _pq_clear_controllers(net_try)
    _pq_apply_tap_family_filter(net_try, ctx)
    if tap_bound:
        _pq_pin_taps(net_try, tap_bound)
    net_try.ext_grid.at[ctx['ext_grid_idx'], 'vm_pu'] = float(ctx['v_applied'])
    _pq_dispatch_p(net_try, ctx['gen_info'], p_val, ctx['exclude_names'])

    force_ctrl = False
    if use_park:
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
    else:
        _pq_apply_local_q(
            net_try, ctx['gen_info'], p_val, ctx['q_mode'], direction, float(frac_or_q),
            ctx['exclude_names'], ctx.get('in_data'))

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

    overloaded = ctx['limit_overloads'] and _pq_overloaded(net_try, ctx['max_loading'])
    volt_viol = ctx['lim_q_uprot'] and _pq_voltage_violation(
        net_try, ctx['gen_info'], ctx['u_min_prot'], ctx['u_max_prot'])

    q_pcc = pp_el._rpc_pcc_q_for_chart(net_try, ctx['pcc_bus_idx'], ctx['ext_grid_idx'])
    reason = None
    unphysical = False
    if overloaded:
        reason = 'overload'
    elif volt_viol:
        reason = 'voltage'
    elif q_cap is not None and _pq_q_unphysical(q_pcc, q_cap, direction, ctx):
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
    return _pq_fill_diag(r, ctx)


def _pq_feasible(r):
    return (
        bool(r.get('converged'))
        and not r.get('overloaded')
        and not r.get('volt_viol')
        and not r.get('unphysical')
    )


def _pq_bisect_q(work, ctx, p_val, direction, use_park, tap_bound, x_fail, q_cap, reason):
    """Largest feasible |Q| between 0 and the failed capability trial, within q_step."""
    dq = max(abs(float(ctx['q_step_mw'])), 1e-6)
    tol = dq if use_park else dq / max(abs(float(q_cap)), 1e-9)
    x_lo = 0.0
    r_ok = _pq_eval_trial(
        work, ctx, p_val, direction, x_lo, tap_bound=tap_bound, use_park=use_park, q_cap=q_cap)
    if not _pq_feasible(r_ok):
        return r_ok, x_lo, r_ok.get('limit_reason') or reason
    x_hi = x_fail
    best_r, best_x = r_ok, x_lo
    guard = 0
    while abs(x_hi - x_lo) > tol + 1e-12 and guard < 40:
        guard += 1
        x_mid = 0.5 * (x_hi + x_lo)
        r = _pq_eval_trial(
            work, ctx, p_val, direction, x_mid, tap_bound=tap_bound, use_park=use_park, q_cap=q_cap)
        if _pq_feasible(r):
            x_lo = x_mid
            best_r, best_x = r, x_mid
        else:
            x_hi = x_mid
            reason = r.get('limit_reason') or reason
    return best_r, best_x, reason


def _pq_search_one_side(base_net, ctx, p_val, direction, use_park, tap_bound):
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
    work = deepcopy(base_net)
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

        r = _pq_eval_trial(
            work, ctx, p_val, direction, x, tap_bound=tap_bound, use_park=use_park, q_cap=q_cap)
        _pq_log_trial(ctx, p_val, tap_bound, direction, r, x, q_cap, 'cap')
        if _pq_feasible(r):
            return r, x, None, q_cap

        reason = r.get('limit_reason') or 'divergence'
        if ctx['shnt_ctrl'] and ctx['limit_overloads'] and r.get('overloaded'):
            ctx['rcs'] = False
            guard = 0
            while r.get('overloaded') and guard < 200:
                if not _pq_reduce_compensation_one_step(work, ctx['shunt_names'], direction):
                    break
                r = _pq_eval_trial(
                    work, ctx, p_val, direction, x, tap_bound=tap_bound, use_park=use_park,
                    q_cap=q_cap)
                guard += 1
                if _pq_feasible(r):
                    _pq_log_trial(ctx, p_val, tap_bound, direction, r, x, q_cap, 'after shunt')
                    return r, x, 'shunt', q_cap
                reason = r.get('limit_reason') or reason

        r, x, reason = _pq_bisect_q(
            work, ctx, p_val, direction, use_park, tap_bound, x, q_cap, reason)
        _pq_log_trial(ctx, p_val, tap_bound, direction, r, x, q_cap, 'bisect')
        if _pq_feasible(r):
            return r, x, reason, q_cap
    finally:
        ctx['rcs'] = rcs_saved
        ctx['rc2'], ctx['rc3'] = rc2_saved, rc3_saved

    if r and r.get('converged') and not r.get('unphysical'):
        return r, x, reason, q_cap
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


def grid_code_pq_capability(net, pq_params, in_data=None):
    """
    P-Q capability at the PoC. Returns JSON string:
      { "grid_code_pq_results": { ... same curve/compliance shape as RPC, plus summary } }
    """
    try:
        pcc_bus_name = pq_params.get('pcc_bus_name')
        ext_grid_name = pq_params.get('ext_grid_name')
        generator_names = pq_params.get('generator_names') or []
        exclude_names = pq_params.get('exclude_generator_names') or []
        shunt_names = pq_params.get('shunt_names') or []
        voltage_levels = list(pq_params.get('voltage_levels') or [1.0])
        q_mode = pq_params.get('q_capability_mode') or 'from_rating'
        i_park = _pq_bool(pq_params.get('i_park_ctrl'), False)
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
            try:
                p_mw = float(net.storage.at[idx, 'p_mw']) if not pd.isna(net.storage.at[idx, 'p_mw']) else 0.0
            except Exception:
                p_mw = 0.0
            sn_f = float(sn) if sn and sn > 0 else 0.0
            p_rated = abs(p_mw) if abs(p_mw) > 0 else sn_f
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
            f'  Q dispatch={"Park" if i_park else "Local"} {park_name or "—"}  '
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

        for v_pu in voltage_levels:
            v_key = f"{float(v_pu):.4f}"
            ctx['v_applied'] = float(v_pu) * u_scale
            _pq_emit(
                f'  Voltage {v_pu} pu (applied {ctx["v_applied"]:.4f} pu)',
                ctx, progress=True)

            p_result, p_max_result, p_min_result, p_disp_result = [], [], [], []
            q_max_result, q_min_result = [], []
            cos_over, cos_under = [], []
            limit_max_result, limit_min_result = [], []

            for p_val in p_points:
                _pq_check_cancel(ctx)
                qmax_cands = []
                qmin_cands = []
                max_pairs = []
                min_pairs = []
                max_rs = []
                min_rs = []
                reasons_max = []
                reasons_min = []
                for bound in tap_bounds:
                    rmax, xmax, rsn_max, _ = _pq_search_one_side(
                        net, ctx, p_val, 'max', i_park, bound)
                    rmin, xmin, rsn_min, _ = _pq_search_one_side(
                        net, ctx, p_val, 'min', i_park, bound)
                    qmax_cands.append(None if rmax is None else rmax.get('q_pcc'))
                    qmin_cands.append(None if rmin is None else rmin.get('q_pcc'))
                    max_pairs.append((
                        None if rmax is None else rmax.get('q_pcc'),
                        None if rmax is None else rmax.get('net'),
                    ))
                    min_pairs.append((
                        None if rmin is None else rmin.get('q_pcc'),
                        None if rmin is None else rmin.get('net'),
                    ))
                    max_rs.append(rmax)
                    min_rs.append(rmin)
                    if rsn_max:
                        reasons_max.append(rsn_max)
                    if rsn_min:
                        reasons_min.append(rsn_min)
                    if rmax and rmax.get('net') is not None and not rmax.get('unphysical'):
                        _pq_update_summary(summary, rmax['net'], gen_info)
                        _pq_update_tap_health(ctx, rmax.get('tap_recs'), p_val, bound, 'max')
                    if rmin and rmin.get('net') is not None and not rmin.get('unphysical'):
                        _pq_update_summary(summary, rmin['net'], gen_info)
                        _pq_update_tap_health(ctx, rmin.get('tap_recs'), p_val, bound, 'min')

                q_max_pcc = qmax_cands[0]
                q_min_pcc = qmin_cands[0]
                if (rc2 or rc3) and len(qmax_cands) > 1:
                    q_max_pcc = _pq_restrictive_qmax(qmax_cands[0], qmax_cands[1])
                    q_min_pcc = _pq_restrictive_qmin(qmin_cands[0], qmin_cands[1])
                    _pq_emit(
                        f'    P={p_val:.2f} MW tap bounds: '
                        f'Qmax [{_pq_fmt(qmax_cands[0])} | {_pq_fmt(qmax_cands[1])}] → {_pq_fmt(q_max_pcc)}  '
                        f'Qmin [{_pq_fmt(qmin_cands[0])} | {_pq_fmt(qmin_cands[1])}] → {_pq_fmt(q_min_pcc)}',
                        ctx, progress=True)
                snap_max = _pq_net_matching_q(max_pairs, q_max_pcc)
                snap_min = _pq_net_matching_q(min_pairs, q_min_pcc)

                if q_max_pcc is None:
                    why = ', '.join(sorted(set(x for x in reasons_max if x))) or 'no converged load flow'
                    _pq_emit(f'    Q_max failed at P={p_val:.2f} MW ({why})', ctx, progress=True)
                if q_min_pcc is None:
                    why = ', '.join(sorted(set(x for x in reasons_min if x))) or 'no converged load flow'
                    _pq_emit(f'    Q_min failed at P={p_val:.2f} MW ({why})', ctx, progress=True)
                if q_max_pcc is not None and q_max_pcc < -1e-3:
                    _pq_emit(
                        f'    WARNING: Q_max={q_max_pcc:.2f} Mvar is negative at P={p_val:.2f} MW '
                        f'(overexcited plant Q should be ≥ 0 in generator convention).',
                        ctx, progress=True)

                for rsn, side in ((reasons_max, 'max'), (reasons_min, 'min')):
                    uniq = [x for x in rsn if x]
                    if uniq:
                        warnings_list.append(
                            f"V={v_pu}pu, P={p_val:.1f}MW: Q_{side} limited "
                            f"({', '.join(sorted(set(uniq)))})"
                        )

                p_disp_plot = sign_out * float(p_val)
                p_plot_max = _pq_pcc_plot_from_net(snap_max, ctx, sign_out)
                p_plot_min = _pq_pcc_plot_from_net(snap_min, ctx, sign_out)
                if p_plot_max is None:
                    p_plot_max = p_disp_plot
                if p_plot_min is None:
                    p_plot_min = p_disp_plot

                qmax_plot = None if q_max_pcc is None else sign_out * float(q_max_pcc)
                qmin_plot = None if q_min_pcc is None else sign_out * float(q_min_pcc)

                p_max_r = round(float(p_plot_max), 4)
                p_min_r = round(float(p_plot_min), 4)

                if snap_max is not None:
                    pp_el._rpc_store_point_snapshot(point_loadflows, v_key, 'q_max', p_val, snap_max)
                    pp_el._rpc_store_point_snapshot(point_loadflows, v_key, 'q_max', p_max_r, snap_max)
                if snap_min is not None:
                    pp_el._rpc_store_point_snapshot(point_loadflows, v_key, 'q_min', p_val, snap_min)
                    pp_el._rpc_store_point_snapshot(point_loadflows, v_key, 'q_min', p_min_r, snap_min)

                p_pcc_log = p_plot_max / sign_out if sign_out else p_plot_max
                _pq_emit(
                    f'    → P_disp={p_val:.2f} MW  P_PCC={_pq_fmt(p_pcc_log)} MW '
                    f'envelope: Q_max={_pq_fmt(q_max_pcc)} Mvar, '
                    f'Q_min={_pq_fmt(q_min_pcc)} Mvar  (LF={ctx["iLDF"][0]})',
                    ctx, progress=True)
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

            curves[v_key] = {
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
            pmax_pcc = _pq_pmax_pcc_for_req(curves[v_key])
            v_req = requirements.get(v_key) if requirements else None
            if v_req and pn > 0 and pmax_pcc and pmax_pcc > 0:
                k = float(pmax_pcc) / float(pn)
                v_req = _pq_scale_requirement(v_req, k)
                requirements[v_key] = v_req
                _pq_emit(
                    f'  Grid-code envelope: Pmax at PCC={pmax_pcc:.3f} MW '
                    f'(Pn={pn:.3f} MW, scale={k:.4f})',
                    ctx, progress=True)
            if v_req:
                # Compare in generator-oriented MW/Mvar (requirements are always generator-oriented)
                pmax_cmp = [sign_out * p for p in p_max_result]
                pmin_cmp = [sign_out * p for p in p_min_result]
                qmax_cmp = [None if q is None else sign_out * q for q in q_max_result]
                qmin_cmp = [None if q is None else sign_out * q for q in q_min_result]
                compliance[v_key] = _pq_check_compliance(
                    pmax_cmp, qmax_cmp, pmin_cmp, qmin_cmp, v_req)
            else:
                compliance[v_key] = None

        pq0 = None
        if i_show_pq0:
            net0 = deepcopy(net)
            _pq_clear_controllers(net0)
            _pq_apply_tap_family_filter(net0, ctx)
            for g in gen_info:
                _pq_set_gen_pq(net0, g, 0.0, 0.0)
            net0.ext_grid.at[ext_grid_idx, 'vm_pu'] = float(voltage_levels[0]) * u_scale if voltage_levels else 1.0
            iLDF[0] += 1
            if _pq_run_pf(
                    net0, verbose, rc2, rc3, rcs, force_control=False,
                    cancel_event=ctx.get('cancel_event')):
                p0 = _pq_pcc_p(net0, pcc_bus_idx, ext_grid_idx)
                q0 = pp_el._rpc_pcc_q_for_chart(net0, pcc_bus_idx, ext_grid_idx)
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
                    'pcc_pmax' if (requirements and pmax_pcc_mw and pn > 0) else
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
                'q_dispatch_mode': 'park' if i_park else 'local',
                'park_controller_name': park_name,
                'i_curve_mw': i_curve_mw,
                'i_curve_mvar': i_curve_mvar,
                'generator_oriented': generator_oriented,
                'i_output': i_output,
                'output_table': output_table,
                'pq0': pq0,
                'summary': summary,
                'load_flow_count': iLDF[0],
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
