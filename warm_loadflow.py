# -*- coding: utf-8 -*-
"""Keep a few large Newton models in this process and rerun them from the last voltages.

The cache is per process. A multi-worker server rebuilds when the next request
hits a worker that does not hold the model.
"""
import json
import sys
import threading
import time
from collections import OrderedDict

import pandapower_electrisim


_TTL_SECONDS = 300
_MAX_MODELS = 3
_SETPOINT_FIELDS = ('p_mw', 'q_mvar', 'vm_pu', 'va_degree', 'scaling')
_SETPOINT_TABLES = (
    'load', 'asymmetric_load', 'sgen', 'asymmetric_sgen', 'gen',
    'ext_grid', 'storage', 'shunt', 'ward', 'xward',
)

_lock = threading.RLock()
_models = OrderedDict()


def _cache_id(user_email, topology_key):
    return (str(user_email or ''), str(topology_key))


def _valid_key(topology_key):
    if not isinstance(topology_key, str):
        return False
    key = topology_key.strip().lower()
    if not key or len(key) > 128:
        return False
    return all(ch in '0123456789abcdef' for ch in key)


def _finite(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in ('', 'none', 'null', 'nan'):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number == float('inf') or number == float('-inf'):
        return None
    return number


def _flag(value):
    if value is True or value == 1:
        return True
    if isinstance(value, str) and value.strip().lower() in ('true', '1', 'yes', 'on'):
        return True
    return False


def _log(msg):
    text = str(msg)
    try:
        sys.stderr.write(text + '\n')
        sys.stderr.flush()
    except Exception:
        pass
    print(text, flush=True)


def _eligible(net, algorithm):
    """Large constant-power Newton network with one slack.

    lightsim2grid is used when that package is installed. The saved model is
    still worth keeping when it is not, because the next Newton step can start
    from the previous voltages.
    """
    if str(algorithm) != 'nr':
        return False
    try:
        if pandapower_electrisim._electrisim_bus_count(net) <= pandapower_electrisim._LIGHTSIM2GRID_MIN_BUSES:
            return False
        if pandapower_electrisim._electrisim_has_voltage_dependent_loads(net):
            return False
        if pandapower_electrisim._electrisim_has_controllable_shunt(net):
            return False
        if any(
            pandapower_electrisim._electrisim_table_len(net, name)
            for name in pandapower_electrisim._LIGHTSIM2GRID_BLOCKING_TABLES
        ):
            return False
        if pandapower_electrisim._electrisim_slack_count(net) != 1:
            return False
    except Exception:
        return False
    return True


def _id_index(net):
    index = {}
    for table in _SETPOINT_TABLES:
        frame = getattr(net, table, None)
        if frame is None or len(frame) == 0 or 'id' not in getattr(frame, 'columns', []):
            continue
        for idx, val in frame['id'].items():
            if val is None:
                continue
            try:
                if val != val:
                    continue
            except Exception:
                pass
            index.setdefault(str(val), (table, idx))
    return index


def _drop_expired_locked(now):
    stale = [key for key, entry in _models.items() if now - entry['stored'] > _TTL_SECONDS]
    for key in stale:
        _models.pop(key, None)


def _drop(user_email, topology_key):
    with _lock:
        _models.pop(_cache_id(user_email, topology_key), None)


def _store(user_email, topology_key, net, busbars):
    now = time.time()
    with _lock:
        _drop_expired_locked(now)
        cache_id = _cache_id(user_email, topology_key)
        _models[cache_id] = {
            'net': net,
            'busbars': busbars,
            'index': _id_index(net),
            'stored': now,
        }
        _models.move_to_end(cache_id)
        while len(_models) > _MAX_MODELS:
            _models.popitem(last=False)


def _get(user_email, topology_key):
    now = time.time()
    with _lock:
        _drop_expired_locked(now)
        cache_id = _cache_id(user_email, topology_key)
        entry = _models.get(cache_id)
        if entry is None:
            return None
        entry['stored'] = now
        _models.move_to_end(cache_id)
        return entry


def _results_ready(net):
    res = getattr(net, 'res_bus', None)
    if res is None or len(res) == 0:
        return False
    columns = getattr(res, 'columns', [])
    return 'vm_pu' in columns and 'va_degree' in columns


def _success(response_text, net):
    if not getattr(net, 'converged', False):
        return False
    if not isinstance(response_text, str):
        return False
    stripped = response_text.lstrip()
    return stripped.startswith('{') and not stripped.startswith('{"error"')


def _annotate(response_text, topology_key, warm_solved):
    if not isinstance(response_text, str) or not response_text.endswith('}'):
        return response_text
    extra = ',"topology_key":' + json.dumps(topology_key)
    if warm_solved:
        extra += ',"warm_solved":true'
    return response_text[:-1] + extra + '}'


def _warm_miss(reason):
    _log(f"WARM load flow miss: {reason}")
    return json.dumps({'warm_miss': True, 'error': reason})


def apply_setpoints(net, in_data, params_key, id_index):
    """Write changed P, Q, and voltage setpoints onto the cached model."""
    applied = 0
    if not isinstance(in_data, dict):
        return applied
    for key, element in in_data.items():
        if key == params_key or not isinstance(element, dict):
            continue
        typ = element.get('typ')
        if isinstance(typ, str) and 'PowerFlowPandaPower' in typ:
            continue
        element_id = element.get('id')
        if element_id is None:
            continue
        found = id_index.get(str(element_id))
        if not found:
            continue
        table, idx = found
        frame = getattr(net, table, None)
        if frame is None or idx not in frame.index:
            continue
        wrote = False
        for field in _SETPOINT_FIELDS:
            if field not in element or field not in frame.columns:
                continue
            number = _finite(element[field])
            if number is None:
                continue
            frame.at[idx, field] = number
            wrote = True
        if wrote:
            applied += 1
    return applied


def solve_if_cached(in_data, params_key):
    """Solve from the cached model, or None when this request is a full build.

    A warm request whose model is gone or no longer eligible returns a small
    JSON object with warm_miss so the browser can send the full network.
    """
    if not isinstance(in_data, dict):
        return None
    params = in_data.get(params_key)
    if not isinstance(params, dict) or not _flag(params.get('warm_solve')):
        return None

    user_email = params.get('user_email') or 'unknown@user.com'
    topology_key = params.get('topology_key')
    if not _valid_key(topology_key):
        return _warm_miss('The saved load-flow model is no longer available.')

    if str(params.get('algorithm')) != 'nr' or _flag(params.get('exportPython')) or _flag(params.get('exportPandapowerResults')):
        _drop(user_email, topology_key)
        return _warm_miss('This study needs a full network build.')

    with _lock:
        entry = _get(user_email, topology_key)
        if entry is None:
            return _warm_miss('The saved load-flow model is no longer available.')

        net = entry['net']
        if not _eligible(net, 'nr') or not _results_ready(net):
            _drop(user_email, topology_key)
            return _warm_miss('The saved load-flow model cannot be reused for this study.')

        applied = apply_setpoints(net, in_data, params_key, entry['index'])
        _log(f"WARM load flow: {applied} setpoint update(s), init=results")
        rc2, rc3, rcs = pandapower_electrisim._resolve_controller_family_flags(params)
        try:
            response = pandapower_electrisim.powerflow(
                net,
                'nr',
                params.get('calculate_voltage_angles'),
                'results',
                False,
                in_data,
                entry['busbars'],
                run_control_trafo2w=rc2,
                run_control_trafo3w=rc3,
                run_control_shunt=rcs,
                reuse_model=True,
            )
        except Exception:
            _drop(user_email, topology_key)
            raise

        if not _success(response, net):
            _drop(user_email, topology_key)
            return response
        _get(user_email, topology_key)
        return _annotate(response, topology_key.strip().lower(), warm_solved=True)


def remember_after_full(response_text, net, busbars, params, user_email):
    """Cache a successful large Newton solve. Anything else drops that key."""
    if not isinstance(params, dict):
        return response_text
    topology_key = params.get('topology_key')
    if not _valid_key(topology_key):
        _log('Load-flow model not cached: request has no topology key')
        return response_text
    topology_key = topology_key.strip().lower()
    buses = pandapower_electrisim._electrisim_bus_count(net)
    if str(params.get('algorithm')) != 'nr' or not _eligible(net, 'nr') or not _success(response_text, net) or not _results_ready(net):
        _log(
            f"Load-flow model not cached: buses={buses} algorithm={params.get('algorithm')} "
            f"eligible={_eligible(net, 'nr')} converged={bool(getattr(net, 'converged', False))}"
        )
        _drop(user_email, topology_key)
        return response_text
    _store(user_email, topology_key, net, busbars)
    _log(f"Cached load-flow model ({buses} buses) for warm solves")
    return _annotate(response_text, topology_key, warm_solved=False)
