# -*- coding: utf-8 -*-
"""BESS preliminary design study: named load-flow cases, rating checks, P/Q envelope, tap sweep."""

import json
import math
import traceback

import pandas as pd
import pandapower as pp

import pandapower_electrisim as pp_el
import grid_code_pq_electrisim as gc_pq


def _f(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _friendly_map(net):
    return getattr(net, 'user_friendly_names', None) or {}


def _display_name(net, technical):
    tech = str(technical)
    return str(_friendly_map(net).get(tech, tech))


def _expand_names(net, names):
    """Accept diagram display names or pandapower technical (mxCell) names."""
    ufn = _friendly_map(net)
    friendly_to_tech = {str(v): str(k) for k, v in ufn.items()}
    out = []
    seen = set()
    for n in names or []:
        n = str(n)
        for cand in (n, friendly_to_tech.get(n), ufn.get(n)):
            if cand and cand not in seen:
                seen.add(cand)
                out.append(cand)
    return out


def _technical_name(net, table, want):
    """Grid Code P-Q matches pandapower names only, so display names from the
    diagram have to be translated back to the technical (mxCell) name."""
    idx = _find_row(net, table, want)
    if idx is None:
        return want
    return str(table.at[idx, 'name'])


def _technical_names(net, table, names):
    if table is None or getattr(table, 'empty', True):
        return [str(n) for n in names or []]
    want = set(_expand_names(net, names))
    return [str(table.at[idx, 'name']) for idx in table.index
            if str(table.at[idx, 'name']) in want]


def _row_matches(net, technical, want):
    if want is None:
        return False
    want = str(want)
    tech = str(technical)
    if tech == want:
        return True
    return str(_friendly_map(net).get(tech, '')) == want


def _find_row(net, table, want):
    if table is None or getattr(table, 'empty', True) or want is None:
        return None
    want = str(want)
    for idx in table.index:
        if _row_matches(net, table.at[idx, 'name'], want):
            return idx
    return None


def _find_bus_idx(net, name):
    return _find_row(net, getattr(net, 'bus', None), name)


def _find_ext_grid_idx(net, name):
    return _find_row(net, getattr(net, 'ext_grid', None), name)


def _find_trafo_by_name(net, name):
    return _find_row(net, getattr(net, 'trafo', None), name)


def _storage_indices(net, storage_names):
    if not hasattr(net, 'storage') or net.storage.empty:
        return []
    want = set(_expand_names(net, storage_names))
    return [idx for idx in net.storage.index if str(net.storage.at[idx, 'name']) in want]


def _set_storage_dispatch(net, storage_names, p_each, q_each):
    """Electrisim storage sign: p_mw > 0 charge, p_mw < 0 discharge."""
    for idx in _storage_indices(net, storage_names):
        net.storage.at[idx, 'p_mw'] = float(p_each)
        net.storage.at[idx, 'q_mvar'] = float(q_each)


def _run_lf(net, algorithm='nr'):
    """Single Newton-Raphson load-flow. Controllers stay off so named cases
    and the tap sweep do not iterate an OLTC at every trial (the envelope
    engine has its own controller path)."""
    kwargs = dict(
        algorithm=algorithm,
        calculate_voltage_angles=True,
        verbose=False,
        run_control=False,
    )
    try:
        has_res = (
            hasattr(net, 'res_bus') and net.res_bus is not None
            and not getattr(net.res_bus, 'empty', True)
        )
        pp.runpp(net, init='results' if has_res else 'auto', **kwargs)
        return True
    except Exception:
        try:
            pp.runpp(net, init='flat', **kwargs)
            return True
        except Exception:
            return False


def _poc_exchange(net, poc_idx, ext_idx):
    """POC exchange in export-positive convention: P > 0 means the plant
    delivers into the grid, Q > 0 means capacitive (Q exported)."""
    try:
        p = -float(net.res_ext_grid.at[ext_idx, 'p_mw'])
        q = -float(net.res_ext_grid.at[ext_idx, 'q_mvar'])
        return p, q
    except Exception:
        return None, None


def _clamp_to_rating(p_each, q_each, sn_unit):
    """Keep the per-unit operating point inside the PCS apparent-power circle,
    holding P and trimming Q (watt priority). Returns (p, q, clamped)."""
    if sn_unit <= 0:
        return p_each, q_each, False
    if math.hypot(p_each, q_each) <= sn_unit + 1e-9:
        return p_each, q_each, False
    p_lim = max(-sn_unit, min(sn_unit, p_each))
    q_room = math.sqrt(max(0.0, sn_unit ** 2 - p_lim ** 2))
    q_lim = max(-q_room, min(q_room, q_each))
    return p_lim, q_lim, True


def _solve_poc_target(net, params, target_p_mw, target_q_mvar, max_iter=25, tol=1e-3):
    """Adjust storage dispatch until the POC exchange matches the requested
    P/Q, so auxiliary consumption and internal losses are absorbed by the
    plant rather than the grid.

    Conventions: POC is export-positive; Electrisim storage p_mw > 0 charges
    and q_mvar > 0 absorbs, so exporting requires negative storage values.
    """
    names = params.get('storageNames') or []
    n = max(1, len(names))
    sn_unit = _f(params.get('storageSnMva'), 0.0)
    ext_idx = _find_ext_grid_idx(net, params['extGridName'])
    poc_idx = _find_bus_idx(net, params['pocBusName'])
    if ext_idx is None:
        return {'converged': False, 'error': 'ext_grid not found'}

    # Seed with a small allowance for losses and auxiliaries.
    p_each = -(target_p_mw / n) * 1.03
    q_each = -(target_q_mvar / n) * 1.03
    clamped = False
    p_poc = q_poc = None

    for i in range(max_iter):
        p_each, q_each, hit = _clamp_to_rating(p_each, q_each, sn_unit)
        clamped = clamped or hit
        _set_storage_dispatch(net, names, p_each, q_each)
        if not _run_lf(net, params.get('algorithm', 'nr')):
            return {'converged': False, 'limit_reason': 'divergence',
                    'p_each': p_each, 'q_each': q_each}
        p_poc, q_poc = _poc_exchange(net, poc_idx, ext_idx)
        if p_poc is None:
            return {'converged': False, 'limit_reason': 'no_result'}
        dp = target_p_mw - p_poc
        dq = target_q_mvar - q_poc
        if abs(dp) <= tol and abs(dq) <= tol:
            break
        if hit:
            # Rating is the binding constraint; the target is unreachable.
            break
        p_each -= dp / n
        q_each -= dq / n

    return {
        'converged': True,
        'p_each': p_each,
        'q_each': q_each,
        'p_poc_mw': p_poc,
        'q_poc_mvar': q_poc,
        'rating_clamped': clamped,
        'iterations': i + 1,
    }


def _json_num(val):
    try:
        if val is None or (isinstance(val, float) and (math.isnan(val) or pd.isna(val))):
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


def _unit_p_limits(params):
    """Wizard Pmax charge/discharge are per PCS, not plant totals."""
    p_dis = abs(_f(params.get('pMaxDischarge_MW'), 10))
    p_chg = abs(_f(params.get('pMaxCharge_MW'), 10))
    return p_dis, p_chg


def _network_losses(net):
    """Sum branch active/reactive losses from the last load-flow."""
    pl = ql = 0.0
    for attr in ('res_line', 'res_trafo', 'res_trafo3w', 'res_impedance'):
        res = getattr(net, attr, None)
        if res is None or getattr(res, 'empty', True):
            continue
        if 'pl_mw' in res.columns:
            try:
                pl += float(res['pl_mw'].fillna(0).sum())
            except Exception:
                pass
        if 'ql_mvar' in res.columns:
            try:
                ql += float(res['ql_mvar'].fillna(0).sum())
            except Exception:
                pass
    return _json_num(pl), _json_num(ql)


def _storage_loading(net, idx):
    sn = _f(net.storage.at[idx, 'sn_mva'], 0.0)
    p = q = 0.0
    res = getattr(net, 'res_storage', None)
    try:
        if res is not None and not res.empty and idx in res.index:
            p = float(res.at[idx, 'p_mw'])
            q = float(res.at[idx, 'q_mvar'])
        else:
            p = float(net.storage.at[idx, 'p_mw'] or 0.0)
            q = float(net.storage.at[idx, 'q_mvar'] or 0.0)
    except (TypeError, ValueError, KeyError):
        return 0.0, 0.0, 0.0, sn
    loading = (math.hypot(p, q) / sn * 100.0) if sn > 0 else 0.0
    return p, q, loading, sn


def _max_loading_element(net):
    best = None
    best_load = -1.0
    if hasattr(net, 'res_line') and net.res_line is not None and not net.res_line.empty:
        for idx in net.res_line.index:
            try:
                lp = float(net.res_line.at[idx, 'loading_percent'])
                if lp > best_load:
                    best_load = lp
                    best = {
                        'type': 'line',
                        'name': _display_name(net, net.line.at[idx, 'name']),
                        'loading_percent': lp,
                    }
            except Exception:
                pass
    if hasattr(net, 'res_trafo') and net.res_trafo is not None and not net.res_trafo.empty:
        for idx in net.res_trafo.index:
            try:
                lp = float(net.res_trafo.at[idx, 'loading_percent'])
                if lp > best_load:
                    best_load = lp
                    best = {
                        'type': 'transformer',
                        'name': _display_name(net, net.trafo.at[idx, 'name']),
                        'loading_percent': lp,
                    }
            except Exception:
                pass
    if hasattr(net, 'storage') and net.storage is not None and not net.storage.empty:
        for idx in net.storage.index:
            try:
                _p, _q, lp, sn = _storage_loading(net, idx)
                if lp > best_load:
                    best_load = lp
                    best = {
                        'type': 'storage',
                        'name': _display_name(net, net.storage.at[idx, 'name']),
                        'loading_percent': lp,
                        'sn_mva': sn,
                    }
            except Exception:
                pass
    return best


def _voltage_violations(net, vmin, vmax):
    issues = []
    if not hasattr(net, 'res_bus') or net.res_bus.empty:
        return issues
    for idx in net.bus.index:
        try:
            vm = float(net.res_bus.at[idx, 'vm_pu'])
            if vm < vmin - 1e-6 or vm > vmax + 1e-6:
                issues.append({
                    'type': 'voltage',
                    'name': _display_name(net, net.bus.at[idx, 'name']),
                    'vm_pu': vm,
                })
        except Exception:
            pass
    return issues


def _voltage_profile(net):
    """Per-bus voltage throughout the plant (not only violations)."""
    out = []
    res = getattr(net, 'res_bus', None)
    if res is None or res.empty:
        return out
    for idx in net.bus.index:
        vm = None
        try:
            if idx in res.index:
                vm = _json_num(res.at[idx, 'vm_pu'])
        except (TypeError, ValueError, KeyError):
            vm = None
        out.append({
            'name': _display_name(net, net.bus.at[idx, 'name']),
            'vn_kv': _json_num(net.bus.at[idx, 'vn_kv']),
            'vm_pu': vm,
        })
    return out


def _limiting_element(net, vmax_loading, vmin_pu, vmax_pu):
    loader = _max_loading_element(net)
    if loader and loader['loading_percent'] > vmax_loading:
        return loader
    vissues = _voltage_violations(net, vmin_pu, vmax_pu)
    if vissues:
        w = max(vissues, key=lambda x: abs(x['vm_pu'] - 1.0))
        return {
            'type': 'voltage',
            'name': w['name'],
            'vm_pu': w['vm_pu'],
        }
    return loader


def _rating_table(net, cases):
    """Worst-case loading per element across all cases, with nameplate fields."""
    ratings = {}
    for case in cases:
        if not case.get('converged'):
            continue
        for el in case.get('elements') or []:
            key = el.get('name')
            if not key:
                continue
            prev = ratings.get(key)
            if prev is None or el.get('loading_percent', 0) > prev.get('loading_percent', 0):
                ratings[key] = dict(el)
    return list(ratings.values())


def _collect_element_loadings(net):
    """Loadings for in-service branches and PCS/storage, including nameplate."""
    out = []
    for res_attr, el_attr, el_type, rating_col, rating_key in (
            ('res_line', 'line', 'line', 'max_i_ka', 'max_i_ka'),
            ('res_trafo', 'trafo', 'transformer', 'sn_mva', 'sn_mva')):
        res = getattr(net, res_attr, None)
        els = getattr(net, el_attr, None)
        if res is None or els is None or res.empty:
            continue
        for idx in res.index:
            if idx not in els.index:
                continue
            try:
                lp = float(res.at[idx, 'loading_percent'])
            except (TypeError, ValueError, KeyError):
                continue
            if math.isnan(lp):
                continue
            row = {
                'type': el_type,
                'name': _display_name(net, els.at[idx, 'name']),
                'loading_percent': lp,
            }
            try:
                row[rating_key] = _json_num(els.at[idx, rating_col])
            except Exception:
                pass
            out.append(row)
    if hasattr(net, 'storage') and net.storage is not None and not net.storage.empty:
        for idx in net.storage.index:
            try:
                if 'in_service' in net.storage.columns and not bool(net.storage.at[idx, 'in_service']):
                    continue
            except Exception:
                pass
            p, q, lp, sn = _storage_loading(net, idx)
            row = {
                'type': 'storage',
                'name': _display_name(net, net.storage.at[idx, 'name']),
                'sn_mva': sn,
                'p_mw': p,
                'q_mvar': q,
                'loading_percent': lp,
            }
            for col in ('max_p_mw', 'min_p_mw', 'max_q_mvar', 'min_q_mvar'):
                if col in net.storage.columns:
                    row[col] = _json_num(net.storage.at[idx, col])
            out.append(row)
    return out


def _run_named_case(base_net, params, case_def):
    from copy import deepcopy
    net = deepcopy(base_net)
    poc_idx = _find_bus_idx(net, params['pocBusName'])
    ext_idx = _find_ext_grid_idx(net, params['extGridName'])
    if poc_idx is None or ext_idx is None:
        return {
            'name': case_def['name'],
            'converged': False,
            'error': 'POC or ext_grid not found',
            'limiting_element': {'type': 'missing', 'name': 'POC or ext_grid'},
        }

    net.ext_grid.at[ext_idx, 'vm_pu'] = float(case_def['vm_pu'])
    is_target = 'target_p_mw' in case_def
    solve = None

    if is_target:
        solve = _solve_poc_target(
            net, params,
            _f(case_def.get('target_p_mw')),
            _f(case_def.get('target_q_mvar')),
        )
        converged = bool(solve.get('converged'))
    else:
        _set_storage_dispatch(
            net,
            params.get('storageNames') or [],
            case_def['p_each'],
            case_def['q_each'],
        )
        converged = _run_lf(net, params.get('algorithm', 'nr'))

    if not converged:
        return {
            'name': case_def['name'],
            'converged': False,
            'limit_reason': (solve or {}).get('limit_reason', 'divergence'),
            'limiting_element': {'type': 'divergence', 'name': 'load_flow'},
        }

    p_poc, q_poc = _poc_exchange(net, poc_idx, ext_idx)
    p_loss_mw, q_loss_mvar = _network_losses(net)
    vmax = _f(params.get('max_loading_percent'), 100)
    vmin_pu = _f(case_def.get('vmin_pu', params.get('vmin_pu')), 0.95)
    vmax_pu = _f(case_def.get('vmax_pu', params.get('vmax_pu')), 1.05)
    limiter = _limiting_element(net, vmax, vmin_pu, vmax_pu)
    vviol = _voltage_violations(net, vmin_pu, vmax_pu)
    overloaded = (
        limiter
        and limiter.get('type') in ('line', 'transformer', 'storage')
        and limiter.get('loading_percent', 0) > vmax
    )

    result = {
        'name': case_def['name'],
        'converged': True,
        'vm_pu': case_def['vm_pu'],
        'p_poc_mw': p_poc,
        'q_poc_mvar': q_poc,
        'p_loss_mw': p_loss_mw,
        'q_loss_mvar': q_loss_mvar,
        'elements': _collect_element_loadings(net),
        'voltage_profile': _voltage_profile(net),
        'limiting_element': limiter,
        'pass': not overloaded and not vviol,
        'voltage_violations': vviol,
    }

    if is_target:
        tol = _f(params.get('poc_target_tol_mw'), 0.05)
        target_p = _f(case_def.get('target_p_mw'))
        target_q = _f(case_def.get('target_q_mvar'))
        p_err = (p_poc or 0.0) - target_p
        q_err = (q_poc or 0.0) - target_q
        target_met = abs(p_err) <= tol and abs(q_err) <= tol
        result.update({
            'target_p_mw': target_p,
            'target_q_mvar': target_q,
            'p_error_mw': p_err,
            'q_error_mvar': q_err,
            'target_met': target_met,
            'rating_clamped': bool(solve.get('rating_clamped')),
            'pcs_p_each_mw': solve.get('p_each'),
            'pcs_q_each_mvar': solve.get('q_each'),
        })
        result['pass'] = result['pass'] and target_met
        if not target_met and result['limiting_element'] is None:
            result['limiting_element'] = {
                'type': 'rating' if solve.get('rating_clamped') else 'unreachable',
                'name': 'PCS apparent power' if solve.get('rating_clamped') else 'POC target',
            }

    return result


def _build_named_cases(params):
    p_dis, p_chg = _unit_p_limits(params)
    poc_p = _f(params.get('pocP_MW'), p_dis)
    poc_q = _f(params.get('pocQ_Mvar'), 0)
    # storageSnMva / pMax* are per-unit PCS ratings. Do not divide by N.
    q_cap_unit = _f(params.get('storageSnMva'), p_dis * 1.1)
    u_levels = [
        ('Umin', _f(params.get('umin_pu'), 0.95)),
        ('Unom', _f(params.get('unom_pu'), 1.0)),
        ('Umax', _f(params.get('umax_pu'), 1.05)),
    ]
    cases = []
    for label, vm in u_levels:
        # Headline check: can the plant actually deliver the requested POC P/Q
        # once auxiliaries and internal losses are covered?
        cases.append({
            'name': f'{label}_POC_Target',
            'vm_pu': vm,
            'target_p_mw': poc_p,
            'target_q_mvar': poc_q,
        })
        # Discharge: storage p < 0
        cases.append({
            'name': f'{label}_Rated_Discharge',
            'vm_pu': vm,
            'p_each': -p_dis,
            'q_each': 0.0,
        })
        # Charge: storage p > 0
        cases.append({
            'name': f'{label}_Rated_Charge',
            'vm_pu': vm,
            'p_each': p_chg,
            'q_each': 0.0,
        })
        # Q support at P ~ 0; export-positive Q means negative storage q_mvar.
        cases.append({
            'name': f'{label}_Qmax_Capacitive',
            'vm_pu': vm,
            'p_each': 0.0,
            'q_each': -q_cap_unit,
        })
        cases.append({
            'name': f'{label}_Qmax_Inductive',
            'vm_pu': vm,
            'p_each': 0.0,
            'q_each': q_cap_unit,
        })
    return cases


def _dispatch_trial(net, params, p_each, q_each):
    """One load-flow at a fixed storage dispatch. Returns None if the LF diverges."""
    _set_storage_dispatch(net, params.get('storageNames') or [], p_each, q_each)
    if not _run_lf(net, params.get('algorithm', 'nr')):
        return None
    poc_idx = _find_bus_idx(net, params['pocBusName'])
    ext_idx = _find_ext_grid_idx(net, params['extGridName'])
    p_poc, q_poc = _poc_exchange(net, poc_idx, ext_idx)
    vmax = _f(params.get('max_loading_percent'), 100)
    vmin_pu = _f(params.get('vmin_pu'), 0.95)
    vmax_pu = _f(params.get('vmax_pu'), 1.05)
    limiter = _limiting_element(net, vmax, vmin_pu, vmax_pu)
    overloaded = (
        limiter
        and limiter.get('type') in ('line', 'transformer', 'storage')
        and limiter.get('loading_percent', 0) > vmax
    )
    vviol = _voltage_violations(net, vmin_pu, vmax_pu)
    return {
        'feasible': not overloaded and not vviol,
        'p_poc_mw': p_poc,
        'q_poc_mvar': q_poc,
        'limiting_element': limiter,
    }


def _snapshot_storage(net, storage_names):
    return [(idx, float(net.storage.at[idx, 'p_mw']), float(net.storage.at[idx, 'q_mvar']))
            for idx in _storage_indices(net, storage_names)]


def _restore_storage(net, snap):
    for idx, p_mw, q_mvar in snap:
        net.storage.at[idx, 'p_mw'] = p_mw
        net.storage.at[idx, 'q_mvar'] = q_mvar


def _bisect_available_q(net, params, p_each, q_sign):
    """Largest feasible |Q| at a fixed P and tap. Mutates then restores storage
    dispatch (no deepcopy). q_sign -1 = capacitive, +1 = inductive."""
    sn = _f(params.get('storageSnMva'), abs(p_each) * 1.1)
    q_hi = math.sqrt(max(0.0, sn ** 2 - p_each ** 2))
    names = params.get('storageNames') or []
    snap = _snapshot_storage(net, names)
    try:
        r_hi = _dispatch_trial(net, params, p_each, q_sign * q_hi)
        if r_hi is None:
            return {'converged': False, 'q_poc_mvar': None}
        if r_hi['feasible']:
            return {
                'converged': True,
                'q_poc_mvar': r_hi['q_poc_mvar'],
                'limiting_element': {'type': 'pcs', 'name': 'PCS rating', 'limit_reason': 'rating'},
            }
        r0 = _dispatch_trial(net, params, p_each, 0.0)
        if r0 is None or not r0['feasible']:
            return {
                'converged': r0 is not None,
                'q_poc_mvar': None,
                'limiting_element': (r0 or r_hi).get('limiting_element'),
            }
        lo, hi = 0.0, q_hi
        best_q = r0['q_poc_mvar']
        limiter = r_hi.get('limiting_element')
        for _ in range(6):
            mid = 0.5 * (lo + hi)
            rt = _dispatch_trial(net, params, p_each, q_sign * mid)
            if rt is None:
                hi = mid
                continue
            if rt['feasible']:
                lo = mid
                best_q = rt['q_poc_mvar']
            else:
                hi = mid
                limiter = rt.get('limiting_element') or limiter
        return {
            'converged': True,
            'q_poc_mvar': best_q,
            'limiting_element': limiter,
        }
    finally:
        _restore_storage(net, snap)


def _tap_sweep(base_net, params):
    trafo_idx = _find_trafo_by_name(base_net, params.get('hvTrafoName', 'POC_Transformer'))
    if trafo_idx is None:
        return []
    def _tap_int(val, default):
        try:
            if val is None or (isinstance(val, float) and (math.isnan(val) or pd.isna(val))):
                return default
            return int(float(val))
        except (TypeError, ValueError):
            return default

    # pandapower 3.x ignores tap_pos unless tap_side, tap_step_percent and
    # tap_changer_type are all set, which would otherwise produce a sweep of
    # identical-looking rows that reads as a valid result.
    def _blank(val):
        try:
            return val is None or pd.isna(val) or str(val).strip() == ''
        except (TypeError, ValueError):
            return val is None

    missing = []
    if _blank(base_net.trafo.at[trafo_idx, 'tap_side']):
        missing.append('tap_side')
    if _f(base_net.trafo.at[trafo_idx, 'tap_step_percent'], 0.0) == 0:
        missing.append('tap_step_percent')
    if 'tap_changer_type' in base_net.trafo.columns and _blank(
            base_net.trafo.at[trafo_idx, 'tap_changer_type']):
        missing.append('tap_changer_type')
    if missing:
        return [{
            'error': 'inactive_tap_changer',
            'message': (
                f'Transformer "{params.get("hvTrafoName", "POC_Transformer")}" has no usable '
                f'tap changer (missing: {", ".join(missing)}), so tap position has no effect '
                'on the network.'
            ),
        }]

    tap_min = _tap_int(base_net.trafo.at[trafo_idx, 'tap_min'], -5)
    tap_max = _tap_int(base_net.trafo.at[trafo_idx, 'tap_max'], 5)
    if tap_min > tap_max:
        tap_min, tap_max = -5, 5
    results = []
    from copy import deepcopy
    p_dis, _p_chg = _unit_p_limits(params)
    ext_idx = _find_ext_grid_idx(base_net, params['extGridName'])
    poc_idx = _find_bus_idx(base_net, params['pocBusName'])

    for tap in range(tap_min, tap_max + 1):
        net = deepcopy(base_net)
        tidx = _find_trafo_by_name(net, params.get('hvTrafoName', 'POC_Transformer'))
        if tidx is None:
            continue
        net.trafo.at[tidx, 'tap_pos'] = tap
        progress_cb = params.get('_progress_callback')
        if progress_cb:
            progress_cb(f'Tap position sweep ({tap} of {tap_min}…{tap_max})…')
        if ext_idx is not None:
            net.ext_grid.at[ext_idx, 'vm_pu'] = _f(params.get('unom_pu'), 1.0)
        _set_storage_dispatch(net, params.get('storageNames') or [], -p_dis, 0.0)
        if not _run_lf(net):
            results.append({'tap_pos': tap, 'converged': False})
            continue
        hv_v = mv_v = None
        try:
            hv_bus = int(net.trafo.at[tidx, 'hv_bus'])
            lv_bus = int(net.trafo.at[tidx, 'lv_bus'])
            hv_v = float(net.res_bus.at[hv_bus, 'vm_pu'])
            mv_v = float(net.res_bus.at[lv_bus, 'vm_pu'])
        except Exception:
            pass
        p_poc, q_poc = _poc_exchange(net, poc_idx, ext_idx)
        row = {
            'tap_pos': tap,
            'converged': True,
            'hv_vm_pu': hv_v,
            'mv_vm_pu': mv_v,
            'p_poc_mw': p_poc,
            'q_poc_mvar': q_poc,
            'voltage_profile': _voltage_profile(net),
            'limiting_element': _limiting_element(
                net, _f(params.get('max_loading_percent'), 100),
                _f(params.get('vmin_pu'), 0.95), _f(params.get('vmax_pu'), 1.05)),
        }
        if params.get('tapQCapability', True):
            qmax = _bisect_available_q(net, params, -p_dis, -1.0)
            qmin = _bisect_available_q(net, params, -p_dis, 1.0)
            row['q_max_mvar'] = qmax.get('q_poc_mvar')
            row['q_min_mvar'] = qmin.get('q_poc_mvar')
            row['q_max_limiter'] = qmax.get('limiting_element')
            row['q_min_limiter'] = qmin.get('limiting_element')
        results.append(row)
    return results


def _relabel_envelope_limiters(net, results):
    """The envelope engine reports pandapower names; show diagram names instead."""
    curves = (results or {}).get('curves')
    if not isinstance(curves, dict):
        return
    for curve in curves.values():
        if not isinstance(curve, dict):
            continue
        for key in ('limit_max', 'limit_min'):
            for lim in curve.get(key) or []:
                if isinstance(lim, dict) and lim.get('name'):
                    lim['name'] = _display_name(net, lim['name'])


def _run_pq_envelope(net, params, in_data, progress_cb=None):
    requested = list(params.get('storageNames') or [])
    if not requested:
        return None
    storage_names = _technical_names(net, getattr(net, 'storage', None), requested)
    if not storage_names:
        return {'error': 'No Storage/PCS units from the wizard were found in the network.'}
    n_units = len(storage_names)

    total_p = _f(params.get('pMaxDischarge_MW'), 10) * n_units
    pq_params = {
        'pcc_bus_name': _technical_name(net, getattr(net, 'bus', None), params['pocBusName']),
        'ext_grid_name': _technical_name(net, getattr(net, 'ext_grid', None), params['extGridName']),
        'storage_names': storage_names,
        'generator_names': [],
        'voltage_levels': [
            _f(params.get('umin_pu'), 0.95),
            _f(params.get('unom_pu'), 1.0),
            _f(params.get('umax_pu'), 1.05),
        ],
        'pn_mw': total_p,
        # Coarser than the dedicated Grid Code P-Q study: 25 % Pn in both
        # directions, 5 % Pn Q resolution. Fine enough for a preliminary
        # envelope, far fewer load-flows than a 0.5 % Q / 20 % P sweep.
        'p_start_pct': 0,
        'p_end_pct': 100,
        'p_step_pct': 25,
        'q_step_pct': 5,
        'i_op_range': 2,
        'q_capability_mode': 'from_curve' if params.get('useQCurve') else 'from_rating',
        'limit_overloads': True,
        'max_loading_percent': _f(params.get('max_loading_percent'), 100),
        # Envelope at the diagram tap. Searching both OLTC extremes at every
        # P point (i_trf_ctrl) roughly doubled-to-quadrupled the load-flow
        # count; the tap sweep already reports Q vs tap separately.
        'i_trf_ctrl': False,
        'run_control_trafo2w': False,
        'generator_oriented': True,
        'frequency': _f(params.get('frequency'), 50),
        '_progress_callback': progress_cb,
        '_cancel_event': params.get('_cancel_event'),
    }
    try:
        raw = gc_pq.grid_code_pq_capability(net, pq_params, in_data)
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(parsed, dict) and parsed.get('error'):
            return {'error': parsed.get('error')}
        results = parsed.get('grid_code_pq_results') or parsed
        _relabel_envelope_limiters(net, results)
        return results
    except Exception as ex:
        traceback.print_exc()
        return {'error': str(ex)}


def bess_preliminary_study(net, params, in_data=None):
    """
    Main entry: named cases + ratings + P/Q envelope + tap sweep.
    Returns JSON string with bess_preliminary_results.
    """
    try:
        progress_cb = params.get('_progress_callback')
        if progress_cb:
            progress_cb('Building named load-flow cases…')

        case_defs = _build_named_cases(params)
        named_cases = []
        for i, cd in enumerate(case_defs):
            if progress_cb:
                progress_cb(f'Case {i + 1}/{len(case_defs)}: {cd["name"]}…')
            named_cases.append(_run_named_case(net, params, cd))

        if progress_cb:
            progress_cb('Computing rating verification table…')
        ratings = _rating_table(net, named_cases)

        if progress_cb:
            progress_cb('Running P/Q capability envelope at POC (diagram tap)…')
        from copy import deepcopy
        pq_envelope = _run_pq_envelope(deepcopy(net), params, in_data, progress_cb)

        tap_results = []
        if params.get('tapSweep', True):
            if progress_cb:
                progress_cb('Tap position sweep…')
            tap_results = _tap_sweep(net, params)

        voltage_profile = []
        for c in named_cases:
            if c.get('converged') and c.get('voltage_profile'):
                if 'Unom_POC_Target' in str(c.get('name')) or (
                        not voltage_profile and 'Unom' in str(c.get('name'))):
                    voltage_profile = c['voltage_profile']
                    if 'POC_Target' in str(c.get('name')):
                        break

        summary = {
            'total_cases': len(named_cases),
            'passed_cases': sum(1 for c in named_cases if c.get('pass')),
            'failed_cases': sum(1 for c in named_cases if c.get('converged') and not c.get('pass')),
            'diverged_cases': sum(1 for c in named_cases if not c.get('converged')),
            'target_cases': sum(1 for c in named_cases if 'target_met' in c),
            'target_met_cases': sum(1 for c in named_cases if c.get('target_met')),
        }

        result = {
            'bess_preliminary_results': {
                'named_cases': named_cases,
                'rating_table': ratings,
                'voltage_profile': voltage_profile,
                'pq_envelope': pq_envelope,
                'tap_sweep': tap_results,
                'summary': summary,
                'params': {
                    'pocBusName': params.get('pocBusName'),
                    'storageNames': params.get('storageNames'),
                    'poc_convention': 'export_positive',
                },
            }
        }
        return json.dumps(result, separators=(',', ':'))
    except Exception as ex:
        traceback.print_exc()
        return json.dumps({'error': str(ex)}, separators=(',', ':'))
