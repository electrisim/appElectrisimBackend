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


def _has_controllers(net):
    try:
        ctrl = getattr(net, 'controller', None)
        return ctrl is not None and not getattr(ctrl, 'empty', True)
    except Exception:
        return False


def _oltc_wanted(params):
    v = (params or {}).get('oltcEnabled', True)
    return v not in (False, 'false', 'False', '0', 0)


def _ensure_oltc(net, params):
    """Attach DiscreteTapControl on the POC transformer for named-case LF.

    The tap sweep and the envelope engine keep their own tap handling, so
    controllers are attached only on the deepcopy used by a named case.
    """
    if not _oltc_wanted(params):
        return False
    if _has_controllers(net):
        return True
    specs = list(getattr(net, 'trafo_discrete_tap_controllers', None) or [])
    if not specs:
        tidx = _find_trafo_by_name(net, params.get('hvTrafoName', 'POC_Transformer'))
        if tidx is None:
            return False
        vm_lo = _f(params.get('oltcVmLower'), 0.99)
        vm_hi = _f(params.get('oltcVmUpper'), 1.01)
        if vm_hi < vm_lo:
            vm_lo, vm_hi = vm_hi, vm_lo
        side = str(params.get('oltcControlSide') or 'lv')
        specs = [(int(tidx), side, vm_lo, vm_hi)]
        net.trafo_discrete_tap_controllers = specs
    try:
        pp_el._electrisim_attach_discrete_tap_controllers(
            net, attach_trafo=True, attach_trafo3w=True)
    except Exception:
        traceback.print_exc()
    if _has_controllers(net):
        return True
    try:
        from pandapower.control import DiscreteTapControl
        for row in specs:
            tid, side, vm_lo, vm_hi = int(row[0]), str(row[1]), float(row[2]), float(row[3])
            try:
                DiscreteTapControl(net, tid=tid, side=side,
                                   vm_lower_pu=vm_lo, vm_upper_pu=vm_hi)
            except TypeError:
                DiscreteTapControl(net, element_index=tid, side=side,
                                   vm_lower_pu=vm_lo, vm_upper_pu=vm_hi)
    except Exception:
        traceback.print_exc()
        return False
    return _has_controllers(net)


def _hv_trafo_tap_pos(net, params):
    tidx = _find_trafo_by_name(net, params.get('hvTrafoName', 'POC_Transformer'))
    if tidx is None:
        return None
    try:
        return float(net.trafo.at[tidx, 'tap_pos'])
    except Exception:
        return None


def _run_lf(net, algorithm='nr', run_control=None):
    """Newton-Raphson load-flow. run_control follows attached controllers
    unless the caller forces it (tap sweep keeps OLTC off)."""
    if run_control is None:
        run_control = _has_controllers(net)
    kwargs = dict(
        algorithm=algorithm,
        calculate_voltage_angles=True,
        verbose=False,
        run_control=bool(run_control),
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


def _trim_poc_p_to_pn(net, params, p_each, q_each, pn, algorithm='nr'):
    """Scale fixed-dispatch P so |P_POC| does not exceed the entered Pn.

    Charge plus auxiliaries and losses would otherwise import more than Pn.
    """
    if pn <= 0:
        return p_each
    poc_idx = _find_bus_idx(net, params['pocBusName'])
    ext_idx = _find_ext_grid_idx(net, params['extGridName'])
    names = params.get('storageNames') or []
    for _ in range(8):
        p_poc, _q = _poc_exchange(net, poc_idx, ext_idx)
        if p_poc is None or abs(p_poc) < 1e-9:
            return p_each
        if abs(p_poc) <= pn + 1e-3:
            return p_each
        p_each = p_each * (pn / abs(p_poc))
        _set_storage_dispatch(net, names, p_each, q_each)
        if not _run_lf(net, algorithm):
            break
    return p_each


def _is_default_poc_case(name):
    n = str(name or '')
    return n in ('Unom_Export_Capacitive', 'Unom_POC_Target')


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


def _clamp_unit_pq(p_each, q_each, params):
    """Clamp per-PCS P/Q for the POC-target solver.

    Battery DC Pmax, when set, is a physical P cap. Wizard PCS Pmax is not
    applied here so the plant can still cover auxiliaries and losses up to
    Sn (named cases already use _capped_unit_p).
    """
    sn_unit = _f(params.get('storageSnMva'), 0.0)
    batt = abs(_f(params.get('batteryPmax_MW'), 0.0))
    reason = None
    if batt > 0:
        p_lim = max(-batt, min(batt, p_each))
        if abs(p_lim - p_each) > 1e-9:
            reason = 'Battery DC Pmax'
            p_each = p_lim
    p_each, q_each, sn_hit = _clamp_to_rating(p_each, q_each, sn_unit)
    if sn_hit and reason is None:
        reason = 'PCS apparent power'
    return p_each, q_each, reason is not None, reason


def _solve_poc_target(net, params, target_p_mw, target_q_mvar, max_iter=25, tol=1e-3):
    """Adjust storage dispatch until the POC exchange matches the requested
    P/Q, so auxiliary consumption and internal losses are absorbed by the
    plant rather than the grid.

    Conventions: POC is export-positive; Electrisim storage p_mw > 0 charges
    and q_mvar > 0 absorbs, so exporting requires negative storage values.
    """
    names = params.get('storageNames') or []
    n = max(1, len(names))
    ext_idx = _find_ext_grid_idx(net, params['extGridName'])
    poc_idx = _find_bus_idx(net, params['pocBusName'])
    if ext_idx is None:
        return {'converged': False, 'error': 'ext_grid not found'}

    # Seed with a small allowance for losses and auxiliaries.
    p_each = -(target_p_mw / n) * 1.03
    q_each = -(target_q_mvar / n) * 1.03
    clamped = False
    p_poc = q_poc = None

    clamp_reason = None
    for i in range(max_iter):
        p_each, q_each, hit, reason = _clamp_unit_pq(p_each, q_each, params)
        clamped = clamped or hit
        if hit and reason:
            clamp_reason = reason
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
        p_try = p_each - dp / n
        q_try = q_each - dq / n
        p_new, q_new, hit2, reason2 = _clamp_unit_pq(p_try, q_try, params)
        if hit2:
            clamped = True
            if reason2:
                clamp_reason = reason2
        # P may already sit on Battery DC Pmax / Sn; still walk Q until the
        # circle or Pmax also blocks that step.
        if abs(p_new - p_each) < 1e-9 and abs(q_new - q_each) < 1e-9:
            break
        p_each, q_each = p_new, q_new

    return {
        'converged': True,
        'p_each': p_each,
        'q_each': q_each,
        'p_poc_mw': p_poc,
        'q_poc_mvar': q_poc,
        'rating_clamped': clamped,
        'clamp_reason': clamp_reason,
        'iterations': i + 1,
    }


def _json_num(val):
    try:
        if val is None or (isinstance(val, float) and (math.isnan(val) or pd.isna(val))):
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


def _table_cell_id(table, idx):
    """mxGraph cell.id stored on the pandapower element, if present."""
    if table is None or 'id' not in getattr(table, 'columns', []):
        return None
    try:
        raw = table.at[idx, 'id']
        if raw is None or pd.isna(raw):
            return None
        s = str(raw).strip()
        if not s or s.lower() in ('none', 'nan'):
            return None
        return s
    except Exception:
        return None


def _result_keys(net, table, idx):
    """Identity keys the SLD painter uses: cell.id, display name, mxObjectId name."""
    tech = str(table.at[idx, 'name'])
    return {
        'id': _table_cell_id(table, idx) or tech,
        'name': _display_name(net, tech),
        'technical_name': tech,
    }


def _unit_p_limits(params):
    """Wizard Pmax charge/discharge are per PCS, not plant totals.

    Battery DC Pmax, when set, is the tighter limit on the AC storage
    dispatch. Isolated DC islands are stripped before AC load-flow
    (pandapower 3.2 Jacobian mismatch on transformer nets).
    """
    p_dis = abs(_f(params.get('pMaxDischarge_MW'), 10))
    p_chg = abs(_f(params.get('pMaxCharge_MW'), 10))
    batt = abs(_f(params.get('batteryPmax_MW'), 0.0))
    if batt > 0:
        p_dis = min(p_dis, batt)
        p_chg = min(p_chg, batt)
    return p_dis, p_chg


def _dc_rack_snapshot(net):
    """Identity of DC bus / Source DC cells before they are stripped for AC LF."""
    out = {'bus_dc': [], 'source_dc': []}
    bus_dc = getattr(net, 'bus_dc', None)
    if bus_dc is not None and not getattr(bus_dc, 'empty', True):
        for idx in bus_dc.index:
            out['bus_dc'].append(_result_keys(net, bus_dc, idx))
    src = getattr(net, 'source_dc', None)
    if src is not None and not getattr(src, 'empty', True):
        for idx in src.index:
            out['source_dc'].append(_result_keys(net, src, idx))
    return out


def _strip_dc_for_ac_lf(net):
    """Drop isolated DC rows. pandapower 3.2 mismatches the AC Jacobian when a
    transformer net also has an uncoupled DC island, even if those rows are
    out of service."""
    for tbl in ('vsc', 'line_dc', 'load_dc', 'source_dc', 'bus_dc'):
        df = getattr(net, tbl, None)
        if df is None or getattr(df, 'empty', True):
            continue
        try:
            df.drop(df.index, inplace=True)
        except Exception:
            pass


def _apply_storage_p_limits(net, params):
    """Write wizard Pmax (including Battery DC Pmax) onto storage min/max P."""
    p_dis, p_chg = _unit_p_limits(params)
    idxs = _storage_indices(net, params.get('storageNames') or [])
    if not idxs and hasattr(net, 'storage') and net.storage is not None:
        idxs = list(net.storage.index)
    for idx in idxs:
        try:
            net.storage.at[idx, 'max_p_mw'] = p_chg
            net.storage.at[idx, 'min_p_mw'] = -p_dis
        except Exception:
            pass


def _battery_dc_rows(net, params):
    """Rating rows: |AC Storage P| / Battery DC Pmax, keyed to SLD Source DC."""
    batt = abs(_f((params or {}).get('batteryPmax_MW'), 0.0))
    if batt <= 0:
        return []
    snap = ((params or {}).get('_dc_snapshot') or {}).get('source_dc') or []
    names = (params or {}).get('storageNames') or []
    idxs = _storage_indices(net, names)
    if not idxs and hasattr(net, 'storage') and net.storage is not None \
            and not net.storage.empty:
        idxs = list(net.storage.index)
    rows = []
    for i, idx in enumerate(idxs):
        p, _q, _lp, _sn = _storage_loading(net, idx)
        p_abs = abs(p)
        ident = snap[i] if i < len(snap) else {}
        stor_disp = _display_name(net, net.storage.at[idx, 'name'])
        name = ident.get('name') or f'Battery_{i + 1}'
        row = {
            'id': ident.get('id') or ident.get('technical_name') or name,
            'name': name,
            'technical_name': ident.get('technical_name') or name,
            'type': 'battery_dc',
            'p_mw': _json_num(p),
            'p_dc_mw': _json_num(p_abs),
            'pmax_mw': batt,
            'loading_percent': (p_abs / batt * 100.0) if batt else 0.0,
            'paired_storage': stor_disp,
        }
        rows.append(row)
    return rows


def _n_units(params):
    return max(1, len(params.get('storageNames') or []))


def _q_from_p_pf(p_mw, pf):
    """|Q| implied by |P| and a lagging/leading power factor (Q/P = tan acos PF)."""
    pf = min(0.999999, max(0.1, abs(_f(pf, 0.95))))
    return abs(_f(p_mw, 0.0)) * math.tan(math.acos(pf))


def _poc_pn(params):
    """Grid-code Pn is the requested POC active power, not the sum of PCS nameplates."""
    n = _n_units(params)
    p_dis, _ = _unit_p_limits(params)
    return abs(_f(params.get('pocP_MW'), p_dis * n))


def _capped_unit_p(params):
    """Per-PCS P for named cases / tap sweep: never above the user's POC Pn share."""
    n = _n_units(params)
    p_dis, p_chg = _unit_p_limits(params)
    pn = _poc_pn(params)
    share = pn / n
    return min(p_dis, share), min(p_chg, share)


def _storage_pq_requirement(pn, pf):
    """Four-quadrant P/Q rectangle at cosφ: |Q|/Pn = tan(acos(PF)) from -Pn to +Pn (export-positive P)."""
    pn = abs(_f(pn, 0.0))
    q = _q_from_p_pf(pn, pf)
    # Closed rectangle so the chart can stroke a polygon.
    return {
        'p_mw': [-pn, -pn, pn, pn, -pn],
        'q_req_max_mvar': [q, q, q, q, q],
        'q_req_min_mvar': [-q, -q, -q, -q, -q],
        'pf': abs(_f(pf, 0.95)),
        'q_over_pn': (q / pn) if pn else 0.0,
        'label': 'Grid-code Q at PF={:.3g} (|Q|/Pn={:.3f})'.format(abs(_f(pf, 0.95)), (q / pn) if pn else 0.0),
    }


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


def _max_loading_element(net, params=None):
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
    if hasattr(net, 'res_trafo3w') and net.res_trafo3w is not None and not net.res_trafo3w.empty:
        for idx in net.res_trafo3w.index:
            try:
                if idx in net.trafo3w.index and 'in_service' in net.trafo3w.columns \
                        and not bool(net.trafo3w.at[idx, 'in_service']):
                    continue
                lp = float(net.res_trafo3w.at[idx, 'loading_percent'])
                if lp > best_load:
                    best_load = lp
                    best = {
                        'type': 'transformer',
                        'name': _display_name(net, net.trafo3w.at[idx, 'name']),
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
    for row in _battery_dc_rows(net, params):
        try:
            lp = float(row.get('loading_percent') or 0.0)
        except (TypeError, ValueError):
            continue
        if lp > best_load:
            best_load = lp
            best = {
                'type': 'battery_dc',
                'name': row.get('name') or 'Battery DC Pmax',
                'loading_percent': lp,
                'pmax_mw': row.get('pmax_mw'),
            }
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


def _copy_res_fields(row, res, idx, cols):
    if res is None or getattr(res, 'empty', True):
        return
    try:
        if idx not in res.index:
            return
    except Exception:
        return
    for col in cols:
        if col not in res.columns:
            continue
        try:
            row[col] = _json_num(res.at[idx, col])
        except Exception:
            pass


def _voltage_profile(net):
    """Per-bus voltage throughout the plant (not only violations)."""
    out = []
    res = getattr(net, 'res_bus', None)
    if res is None or res.empty:
        return out
    for idx in net.bus.index:
        row = _result_keys(net, net.bus, idx)
        row['vn_kv'] = _json_num(net.bus.at[idx, 'vn_kv'])
        _copy_res_fields(row, res, idx, ('vm_pu', 'va_degree', 'p_mw', 'q_mvar'))
        out.append(row)
    return out


def _limiting_element(net, vmax_loading, vmin_pu, vmax_pu, params=None):
    loader = _max_loading_element(net, params)
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


def _collect_element_loadings(net, params=None):
    """Loadings for in-service branches, PCS/storage, and Battery DC Pmax."""
    out = []
    for res_attr, el_attr, el_type, rating_col, rating_key in (
            ('res_line', 'line', 'line', 'max_i_ka', 'max_i_ka'),
            ('res_trafo', 'trafo', 'transformer', 'sn_mva', 'sn_mva'),
            ('res_trafo3w', 'trafo3w', 'transformer', 'sn_hv_mva', 'sn_mva')):
        res = getattr(net, res_attr, None)
        els = getattr(net, el_attr, None)
        if res is None or els is None or res.empty:
            continue
        for idx in res.index:
            if idx not in els.index:
                continue
            try:
                if 'in_service' in els.columns and not bool(els.at[idx, 'in_service']):
                    continue
            except Exception:
                pass
            try:
                lp = float(res.at[idx, 'loading_percent'])
            except (TypeError, ValueError, KeyError):
                continue
            if math.isnan(lp):
                continue
            row = _result_keys(net, els, idx)
            row['type'] = el_type
            row['loading_percent'] = lp
            try:
                row[rating_key] = _json_num(els.at[idx, rating_col])
            except Exception:
                pass
            if el_type == 'line':
                _copy_res_fields(row, res, idx, (
                    'p_from_mw', 'q_from_mvar', 'p_to_mw', 'q_to_mvar',
                    'i_from_ka', 'i_to_ka',
                ))
            elif el_attr == 'trafo':
                _copy_res_fields(row, res, idx, (
                    'p_hv_mw', 'q_hv_mvar', 'p_lv_mw', 'q_lv_mvar',
                    'i_hv_ka', 'i_lv_ka',
                ))
                try:
                    row['tap_pos'] = _json_num(els.at[idx, 'tap_pos'])
                    row['tap_min'] = _json_num(els.at[idx, 'tap_min'])
                    row['tap_max'] = _json_num(els.at[idx, 'tap_max'])
                    if row.get('tap_pos') is not None:
                        row['tap_control_result'] = {
                            'tap_pos': row['tap_pos'],
                            'tap_min': row.get('tap_min'),
                            'tap_max': row.get('tap_max'),
                        }
                except Exception:
                    pass
            elif el_attr == 'trafo3w':
                _copy_res_fields(row, res, idx, (
                    'p_hv_mw', 'q_hv_mvar', 'p_mv_mw', 'q_mv_mvar',
                    'p_lv_mw', 'q_lv_mvar',
                    'i_hv_ka', 'i_mv_ka', 'i_lv_ka',
                ))
            out.append(row)
    if hasattr(net, 'storage') and net.storage is not None and not net.storage.empty:
        for idx in net.storage.index:
            try:
                if 'in_service' in net.storage.columns and not bool(net.storage.at[idx, 'in_service']):
                    continue
            except Exception:
                pass
            p, q, lp, sn = _storage_loading(net, idx)
            row = _result_keys(net, net.storage, idx)
            row.update({
                'type': 'storage',
                'sn_mva': sn,
                'p_mw': p,
                'q_mvar': q,
                'loading_percent': lp,
            })
            for col in ('max_p_mw', 'min_p_mw', 'max_q_mvar', 'min_q_mvar'):
                if col in net.storage.columns:
                    row[col] = _json_num(net.storage.at[idx, col])
            out.append(row)
    if hasattr(net, 'load') and net.load is not None and not net.load.empty:
        resl = getattr(net, 'res_load', None)
        for idx in net.load.index:
            try:
                if 'in_service' in net.load.columns and not bool(net.load.at[idx, 'in_service']):
                    continue
            except Exception:
                pass
            row = _result_keys(net, net.load, idx)
            row['type'] = 'load'
            if resl is not None and not resl.empty and idx in resl.index:
                try:
                    row['p_mw'] = _json_num(resl.at[idx, 'p_mw'])
                    row['q_mvar'] = _json_num(resl.at[idx, 'q_mvar'])
                except Exception:
                    pass
            out.append(row)
    if hasattr(net, 'ext_grid') and net.ext_grid is not None and not net.ext_grid.empty:
        rese = getattr(net, 'res_ext_grid', None)
        for idx in net.ext_grid.index:
            try:
                if 'in_service' in net.ext_grid.columns and not bool(net.ext_grid.at[idx, 'in_service']):
                    continue
            except Exception:
                pass
            row = _result_keys(net, net.ext_grid, idx)
            row['type'] = 'ext_grid'
            _copy_res_fields(row, rese, idx, ('p_mw', 'q_mvar'))
            out.append(row)
    out.extend(_battery_dc_rows(net, params))
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
    _ensure_oltc(net, params)
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
        algorithm = params.get('algorithm', 'nr')
        converged = _run_lf(net, algorithm)
        if converged:
            case_def = dict(case_def)
            case_def['p_each'] = _trim_poc_p_to_pn(
                net, params, case_def['p_each'], case_def['q_each'],
                _poc_pn(params), algorithm)

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
    vmin_pu = _f(case_def.get('vmin_pu', params.get('vmin_pu')), 0.90)
    vmax_pu = _f(case_def.get('vmax_pu', params.get('vmax_pu')), 1.10)
    limiter = _limiting_element(net, vmax, vmin_pu, vmax_pu, params)
    vviol = _voltage_violations(net, vmin_pu, vmax_pu)
    overloaded = (
        limiter
        and limiter.get('type') in ('line', 'transformer', 'storage', 'battery_dc')
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
        'elements': _collect_element_loadings(net, params),
        'voltage_profile': _voltage_profile(net),
        'limiting_element': limiter,
        'pass': not overloaded and not vviol,
        'voltage_violations': vviol,
        'tap_pos': _hv_trafo_tap_pos(net, params),
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
            'clamp_reason': solve.get('clamp_reason'),
            'pcs_p_each_mw': solve.get('p_each'),
            'pcs_q_each_mvar': solve.get('q_each'),
        })
        result['pass'] = result['pass'] and target_met
        if not target_met and solve.get('rating_clamped'):
            lim = result.get('limiting_element') or {}
            over = lim.get('loading_percent', 0) > vmax
            if not over and lim.get('type') != 'battery_dc':
                reason = solve.get('clamp_reason') or (
                    'PCS apparent power' if solve.get('rating_clamped') else 'POC target')
                result['limiting_element'] = {
                    'type': 'battery_dc' if reason == 'Battery DC Pmax' else 'rating',
                    'name': reason,
                    'limit_reason': 'rating',
                }
        elif not target_met and result['limiting_element'] is None:
            result['limiting_element'] = {
                'type': 'rating' if solve.get('rating_clamped') else 'unreachable',
                'name': 'PCS apparent power' if solve.get('rating_clamped') else 'POC target',
            }

    return result


def _build_named_cases(params):
    p_dis, p_chg = _capped_unit_p(params)
    poc_p = _poc_pn(params)
    pf = _f(params.get('powerFactor'), 0.95)
    specify_q = params.get('specifyQDirectly') is True or params.get('specifyQDirectly') == 'true'
    poc_q = _f(params.get('pocQ_Mvar'), 0) if specify_q else _q_from_p_pf(poc_p, pf)
    u_levels = [
        ('Umin', _f(params.get('umin_pu'), 0.95)),
        ('Unom', _f(params.get('unom_pu'), 1.0)),
        ('Umax', _f(params.get('umax_pu'), 1.05)),
    ]
    cases = []
    for label, vm in u_levels:
        for p_name, p_sign in (('Export', 1.0), ('Import', -1.0)):
            for q_name, q_sign in (('Capacitive', 1.0), ('Inductive', -1.0)):
                cases.append({
                    'name': f'{label}_{p_name}_{q_name}',
                    'vm_pu': vm,
                    'target_p_mw': p_sign * poc_p,
                    'target_q_mvar': q_sign * poc_q,
                })
        cases.append({
            'name': f'{label}_Rated_Discharge',
            'vm_pu': vm,
            'p_each': -p_dis,
            'q_each': 0.0,
        })
        cases.append({
            'name': f'{label}_Rated_Charge',
            'vm_pu': vm,
            'p_each': p_chg,
            'q_each': 0.0,
        })
    return cases


def _dispatch_trial(net, params, p_each, q_each):
    """One load-flow at a fixed storage dispatch. Returns None if the LF diverges."""
    _set_storage_dispatch(net, params.get('storageNames') or [], p_each, q_each)
    if not _run_lf(net, params.get('algorithm', 'nr'), run_control=False):
        return None
    poc_idx = _find_bus_idx(net, params['pocBusName'])
    ext_idx = _find_ext_grid_idx(net, params['extGridName'])
    p_poc, q_poc = _poc_exchange(net, poc_idx, ext_idx)
    vmax = _f(params.get('max_loading_percent'), 100)
    vmin_pu = _f(params.get('vmin_pu'), 0.90)
    vmax_pu = _f(params.get('vmax_pu'), 1.10)
    limiter = _limiting_element(net, vmax, vmin_pu, vmax_pu, params)
    overloaded = (
        limiter
        and limiter.get('type') in ('line', 'transformer', 'storage', 'battery_dc')
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
    p_dis, _p_chg = _capped_unit_p(params)
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
        if not _run_lf(net, run_control=False):
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
                _f(params.get('vmin_pu'), 0.90), _f(params.get('vmax_pu'), 1.10),
                params),
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


def _requirement_pn_q(envelope, params=None):
    """Grid-code Pn and |Q| from the requirement rectangle (PF × Pn), not PCC Pmax."""
    params = params or {}
    req_map = envelope.get('requirements') or {}
    req = next((r for r in req_map.values() if isinstance(r, dict)), None) or {}
    pn = 0.0
    if isinstance(req.get('p_mw'), (list, tuple)) and req.get('p_mw'):
        try:
            pn = max(abs(float(p)) for p in req['p_mw'])
        except (TypeError, ValueError):
            pn = 0.0
    if pn <= 0:
        pn = abs(_f(envelope.get('pn_mw'), 0.0))
    if pn <= 0 and params:
        pn = abs(_poc_pn(params))
    q_over = abs(_f(req.get('q_over_pn'), 0.0))
    if q_over <= 0 and pn > 0 and req.get('q_req_max_mvar'):
        try:
            q_over = max(abs(float(q)) for q in req['q_req_max_mvar'] if q is not None) / pn
        except (TypeError, ValueError, ZeroDivisionError):
            q_over = 0.0
    return pn, q_over * pn, q_over


def _q_at_rated_p(curve):
    """Qmax / Qmin at rated export (max P > 0) — U–Q / Pmax, not charge."""
    pts = curve.get('p_mw') or []
    if not pts:
        return None
    try:
        pvals = [float(p) for p in pts]
    except (TypeError, ValueError):
        return None
    qmax_arr = curve.get('q_max_mvar') or []
    qmin_arr = curve.get('q_min_mvar') or []
    i_exp = max(range(len(pvals)), key=lambda i: pvals[i])
    if pvals[i_exp] <= 1e-6:
        return None

    def _at(idx):
        qx = qn = None
        try:
            qx = float(qmax_arr[idx]) if idx < len(qmax_arr) and qmax_arr[idx] is not None else None
        except (TypeError, ValueError, IndexError):
            qx = None
        try:
            qn = float(qmin_arr[idx]) if idx < len(qmin_arr) and qmin_arr[idx] is not None else None
        except (TypeError, ValueError, IndexError):
            qn = None
        return qx, qn

    qx, qn = _at(i_exp)
    return {
        'p_rated_mw': pvals[i_exp],
        'q_max_mvar': qx,
        'q_min_mvar': qn,
    }


def _assess_uq_at_rated_p(envelope, params=None):
    """Whether plant Q at rated export covers required |Q|/Pn over Umin–Umax."""
    if not isinstance(envelope, dict) or envelope.get('error'):
        return None
    params = params or {}
    umin = _f(params.get('umin_pu'), 0.95)
    umax = _f(params.get('umax_pu'), 1.05)
    pn, q_req, q_over = _requirement_pn_q(envelope, params)
    if pn <= 0 or q_over <= 0:
        return None
    # 0.5 % of Pn on the Q/Pn axis (~0.25 Mvar at 50 MW); also 2 % of required Q.
    tol_pu = 0.005
    points = []
    overall = True
    any_in_band = False
    for vk, curve in (envelope.get('curves') or {}).items():
        if not isinstance(curve, dict):
            continue
        try:
            u = float(vk)
        except (TypeError, ValueError):
            continue
        in_band = (umin - 1e-4) <= u <= (umax + 1e-4)
        rated = _q_at_rated_p(curve) or {}
        qmax = rated.get('q_max_mvar')
        qmin = rated.get('q_min_mvar')
        qmax_pu = (qmax / pn) if qmax is not None else None
        qmin_pu = (qmin / pn) if qmin is not None else None
        covers = (
            qmax_pu is not None and qmin_pu is not None
            and qmax_pu + tol_pu >= q_over
            and qmin_pu - tol_pu <= -q_over
        )
        if in_band:
            any_in_band = True
            if not covers:
                overall = False
        points.append({
            'u_pu': round(u, 4),
            'in_inner_band': in_band,
            'p_rated_mw': rated.get('p_rated_mw'),
            'q_max_mvar': qmax,
            'q_min_mvar': qmin,
            'q_max_over_pn': qmax_pu,
            'q_min_over_pn': qmin_pu,
            'covers': covers,
        })
    if not points or not any_in_band:
        return None
    return {
        'compliant': bool(overall),
        'q_req_mvar': q_req,
        'q_over_pn': q_over,
        'pn_mw': pn,
        'u_inner_min': umin,
        'u_inner_max': umax,
        'u_outer_min': 0.90,
        'u_outer_max': 1.10,
        'points': sorted(points, key=lambda p: p['u_pu']),
    }


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
    pn = _poc_pn({**params, 'storageNames': requested or storage_names})
    req = _storage_pq_requirement(pn, _f(params.get('powerFactor'), 0.95))
    v_keys = [
        f"{_f(params.get('umin_pu'), 0.95):.4f}",
        f"{_f(params.get('unom_pu'), 1.0):.4f}",
        f"{_f(params.get('umax_pu'), 1.05):.4f}",
    ]
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
        'pn_mw': pn,
        'p_start_pct': 0,
        'p_end_pct': 100,
        'p_step_pct': 25,
        'q_step_pct': 5,
        'i_op_range': 2,
        'q_capability_mode': 'from_curve' if params.get('useQCurve') else 'from_rating',
        'limit_overloads': True,
        'max_loading_percent': _f(params.get('max_loading_percent'), 100),
        'i_trf_ctrl': False,
        'run_control_trafo2w': False,
        'generator_oriented': True,
        'frequency': _f(params.get('frequency'), 50),
        'requirements': {k: req for k in v_keys},
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
        uq = _assess_uq_at_rated_p(results, params)
        if uq:
            results['uq_at_rated_p'] = uq
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

        params = dict(params or {})
        params['_dc_snapshot'] = _dc_rack_snapshot(net)
        _strip_dc_for_ac_lf(net)
        _apply_storage_p_limits(net, params)

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
        if params.get('tapSweep', False):
            if progress_cb:
                progress_cb('Tap position sweep…')
            tap_results = _tap_sweep(net, params)

        voltage_profile = []
        for c in named_cases:
            if c.get('converged') and c.get('voltage_profile'):
                if _is_default_poc_case(c.get('name')) or (
                        not voltage_profile and 'Unom' in str(c.get('name'))):
                    voltage_profile = c['voltage_profile']
                    if _is_default_poc_case(c.get('name')):
                        break

        uq = (pq_envelope or {}).get('uq_at_rated_p') if isinstance(pq_envelope, dict) else None
        summary = {
            'total_cases': len(named_cases),
            'passed_cases': sum(1 for c in named_cases if c.get('pass')),
            'failed_cases': sum(1 for c in named_cases if c.get('converged') and not c.get('pass')),
            'diverged_cases': sum(1 for c in named_cases if not c.get('converged')),
            'target_cases': sum(1 for c in named_cases if 'target_met' in c),
            'target_met_cases': sum(1 for c in named_cases if c.get('target_met')),
            'uq_at_rated_p_compliant': None if not uq else bool(uq.get('compliant')),
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
                    'vmin_pu': _f(params.get('vmin_pu'), 0.90),
                    'vmax_pu': _f(params.get('vmax_pu'), 1.10),
                    'umin_pu': _f(params.get('umin_pu'), 0.95),
                    'umax_pu': _f(params.get('umax_pu'), 1.05),
                },
            }
        }
        return json.dumps(result, separators=(',', ':'))
    except Exception as ex:
        traceback.print_exc()
        return json.dumps({'error': str(ex)}, separators=(',', ':'))
