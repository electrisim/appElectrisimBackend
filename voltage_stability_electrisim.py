"""Voltage stability margin (P-V curves) with pandapower.

Load is increased step by step until the load flow no longer solves. The last solvable
point is the tip ("nose") of the P-V curve: the most the network can deliver.

Two ways to grow the load:

- ``all_loads``: every in-service load is scaled up together (P and Q, constant power factor);
- ``bus``: a new load with a chosen power factor is added at one bus (a data center, a factory)
  and grown from 0 MW.

The extra power comes from the slack (External Grid or slack generator); other generators keep
their set points. Generator reactive limits are enforced when they are entered.

Method: the tip is bracketed by doubling the step and then narrowed by bisection, each solve
starting from the previous solution so it stays on the upper (stable) branch. A stepped search
finds the last point that solves, so the reported tip is slightly below the true one (by less
than ``tip_tolerance``). The curve is then sampled with more points close to the tip.

Besides the collapse point the study reports where the first bus leaves the voltage limit and
where the first line or transformer exceeds its loading limit, because one of those usually
comes first and is the real limit of the connection.
"""
from __future__ import annotations

import json
import math

import pandapower as pp

import pandapower_electrisim as pe

MAX_SOLVES = 400
CURVE_POINTS = 45
SHOWN_CURVES = 8


class _Grower:
    """Applies a growth value ``x`` (MW) to the network and solves it."""

    def __init__(self, net, mode, bus_idx, power_factor):
        self.net = net
        self.mode = mode
        self.solves = 0
        self.kwargs = dict(calculate_voltage_angles=True, **pe._electrisim_enforce_q_lims_kw(net))
        self.has_solution = False
        if mode == 'bus':
            pf = min(max(float(power_factor), 0.05), 1.0)
            self.tan_phi = math.tan(math.acos(pf))
            self.load_idx = pp.create_load(net, bus=bus_idx, p_mw=0.0, q_mvar=0.0,
                                           name='__electrisim_pv_study_load__')
            self.base_mw = 0.0
        else:
            active = net.load.in_service.astype(bool)
            scaling = net.load.scaling if 'scaling' in net.load.columns else 1.0
            self.base_p = net.load.p_mw.copy()
            self.base_q = net.load.q_mvar.copy()
            self.active = active
            self.base_mw = float((net.load.p_mw * scaling)[active].sum())

    def apply(self, x):
        """``x`` is the added load in MW (bus mode) or the total load in MW (all loads)."""
        net = self.net
        if self.mode == 'bus':
            net.load.at[self.load_idx, 'p_mw'] = float(x)
            net.load.at[self.load_idx, 'q_mvar'] = float(x) * self.tan_phi
        else:
            factor = float(x) / self.base_mw
            net.load.loc[self.active, 'p_mw'] = self.base_p[self.active] * factor
            net.load.loc[self.active, 'q_mvar'] = self.base_q[self.active] * factor

    def solve(self, x):
        """True when the load flow solves at ``x``. Warm-started from the last solution."""
        self.apply(x)
        self.solves += 1
        attempts = []
        if self.has_solution:
            attempts.append({'init': 'results', 'max_iteration': 30})
        attempts.append({'init': 'auto', 'max_iteration': 30})
        for extra in attempts:
            try:
                pe.electrisim_runpp(self.net, algorithm='nr', **self.kwargs, **extra)
            except Exception:
                continue
            vm = self.net.res_bus.vm_pu
            # A "solution" with collapsed voltages is the lower branch or a numerical artefact.
            if bool(self.net.converged) and float(vm.min(skipna=True)) > 0.3:
                self.has_solution = True
                return True
        self.has_solution = False
        return False


def _num(value, default):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _friendly(net, table, idx):
    raw = str(net[table].at[idx, 'name'])
    names = getattr(net, 'user_friendly_names', None) or {}
    label = names.get(raw)
    return str(label).strip() if label not in (None, '') and str(label).strip() else raw


def _element_id(net, table, idx):
    if 'id' in net[table].columns:
        value = net[table].at[idx, 'id']
        if value is not None and str(value) not in ('', 'nan', 'None'):
            return str(value)
    return str(net[table].at[idx, 'name'])


def _snapshot(net, x):
    """Everything kept from one solved point."""
    point = {'x_mw': float(x), 'vm': net.res_bus.vm_pu.copy()}
    worst = None
    for table, res in (('line', 'res_line'), ('trafo', 'res_trafo'), ('trafo3w', 'res_trafo3w')):
        df = getattr(net, res, None)
        if df is None or df.empty or 'loading_percent' not in df:
            continue
        loading = df.loading_percent.dropna()
        if loading.empty:
            continue
        idx = loading.idxmax()
        if worst is None or float(loading.at[idx]) > worst[0]:
            worst = (float(loading.at[idx]), table, idx)
        point[table] = df.loading_percent.copy()
    point['worst_branch'] = worst
    try:
        point['slack_p_mw'] = float(net.res_ext_grid.p_mw.sum()) if len(net.ext_grid) else None
        point['slack_q_mvar'] = float(net.res_ext_grid.q_mvar.sum()) if len(net.ext_grid) else None
    except Exception:
        point['slack_p_mw'] = point['slack_q_mvar'] = None
    return point


def _first_crossing(xs, ys, limit, below):
    """x where the series first goes below (or above) ``limit``, by linear interpolation."""
    for i, y in enumerate(ys):
        if y is None or (isinstance(y, float) and math.isnan(y)):
            continue
        crossed = y < limit if below else y > limit
        if not crossed:
            continue
        if i == 0:
            return xs[0]
        y0 = ys[i - 1]
        if y0 is None or y0 == y:
            return xs[i]
        return xs[i - 1] + (limit - y0) * (xs[i] - xs[i - 1]) / (y - y0)
    return None


def _resolve_bus(net, bus_ref):
    ref = str(bus_ref or '').strip()
    if not ref:
        return None
    names = getattr(net, 'user_friendly_names', None) or {}
    for column in ('id', 'name'):
        if column in net.bus.columns:
            hit = net.bus.index[net.bus[column].astype(str) == ref]
            if len(hit):
                return int(hit[0])
    alt = ref.replace('#', '_')
    hit = net.bus.index[net.bus['name'].astype(str) == alt]
    if len(hit):
        return int(hit[0])
    for idx in net.bus.index:
        if str(names.get(str(net.bus.at[idx, 'name']), '')).strip() == ref:
            return int(idx)
    return None


def _is_slack_bus(net, bus_idx):
    if len(net.ext_grid) and bool((net.ext_grid.bus[net.ext_grid.in_service.astype(bool)] == bus_idx).any()):
        return True
    if len(net.gen) and 'slack' in net.gen.columns:
        slack = net.gen[net.gen.slack.astype(bool) & net.gen.in_service.astype(bool)]
        return bool((slack.bus == bus_idx).any())
    return False


def voltage_stability_study(net, params):
    """Run the P-V study and return the result as a JSON string."""
    try:
        return json.dumps(_study(net, params or {}), allow_nan=False, separators=(',', ':'))
    except _StudyError as exc:
        return json.dumps({'error': str(exc)})
    except Exception as exc:  # unexpected: still answer with a readable message
        return json.dumps({'error': f"Voltage stability study failed: {exc}"})


class _StudyError(Exception):
    pass


def _study(net, params):
    mode = 'bus' if str(params.get('mode', 'all_loads')).strip().lower() in ('bus', 'new_load', 'site') else 'all_loads'
    min_vm = _num(params.get('min_vm_pu'), 0.95)
    max_loading = _num(params.get('max_loading_percent'), 100.0)
    power_factor = _num(params.get('power_factor'), 0.95)
    if not 0 < power_factor <= 1:
        raise _StudyError("Power factor must be above 0 and at most 1.")

    if net.bus.empty:
        raise _StudyError("The diagram has no buses.")
    try:
        pe.electrisim_runpp_robust(net, algorithm='nr', calculate_voltage_angles=True,
                                   **pe._electrisim_enforce_q_lims_kw(net))
    except Exception as exc:
        raise _StudyError(
            "The load flow of the network as drawn did not converge, so there is no starting point "
            f"for the study. Run Load Flow first and resolve what it reports. ({exc})")

    bus_idx = None
    if mode == 'bus':
        bus_idx = _resolve_bus(net, params.get('bus_id') or params.get('bus_name'))
        if bus_idx is None:
            raise _StudyError("Choose the bus where the new load connects.")
        if not bool(net.bus.at[bus_idx, 'in_service']) or math.isnan(float(net.res_bus.vm_pu.at[bus_idx])):
            raise _StudyError(f"Bus '{_friendly(net, 'bus', bus_idx)}' is not supplied, so no load can be added there.")
    else:
        if net.load.empty or not bool(net.load.in_service.astype(bool).any()):
            raise _StudyError("There are no in-service loads to grow. Add a Load, or use \"Add a new load at one bus\".")

    grower = _Grower(net, mode, bus_idx, power_factor)
    base_x = grower.base_mw
    if mode == 'all_loads' and base_x <= 0:
        raise _StudyError("The loads add up to 0 MW or less, so they cannot be scaled up. Use \"Add a new load at one bus\".")

    system_load = float(net.res_load.p_mw.sum()) if len(net.load) else 0.0
    if mode == 'bus':
        first_step = max(0.02 * abs(system_load), 0.001 * float(net.bus.at[bus_idx, 'vn_kv']) ** 2 / 10.0, 0.01)
    else:
        first_step = 0.05 * base_x

    if not grower.solve(base_x):
        raise _StudyError("The starting point could not be solved again; the network is at its limit as drawn.")

    # --- bracket the tip: double the step while it solves
    good = base_x
    step = first_step
    bad = None
    doublings = 0
    while grower.solves < MAX_SOLVES and doublings < 40:
        doublings += 1
        trial = good + step
        if grower.solve(trial):
            good = trial
            step *= 2.0
        else:
            bad = trial
            break
    if bad is None:
        if bus_idx is not None and _is_slack_bus(net, bus_idx):
            raise _StudyError(
                f"Bus '{_friendly(net, 'bus', bus_idx)}' is the slack bus (External Grid or slack generator). It holds "
                "its voltage and supplies whatever is asked, so it has no collapse point. Choose another bus.")
        raise _StudyError("No voltage limit was found within the search range; check the External Grid and generator data.")

    # --- bisection between the last solved and the first failed value
    tolerance = max(_num(params.get('tip_tolerance_percent'), 0.2), 0.01) / 100.0
    grower.solve(good)
    while (bad - good) > tolerance * max(good, first_step) and grower.solves < MAX_SOLVES:
        middle = 0.5 * (good + bad)
        if grower.solve(middle):
            good = middle
        else:
            bad = middle
            grower.solve(good)   # back onto the upper branch before the next trial
    tip_x = good

    # --- sample the curve, denser towards the tip
    span = tip_x - base_x
    xs = [base_x + span * (1.0 - (1.0 - i / (CURVE_POINTS - 1)) ** 2) for i in range(CURVE_POINTS)]
    xs[-1] = tip_x
    points = []
    grower.has_solution = False
    for x in xs:
        if grower.solve(x):
            points.append(_snapshot(net, x))
    if len(points) < 3:
        raise _StudyError("Too few points of the curve could be solved to draw it.")
    tip = points[-1]
    xs = [p['x_mw'] for p in points]

    # --- limits met on the way
    buses = [b for b in net.bus.index if not math.isnan(float(points[0]['vm'].at[b]))]
    min_vm_series = [float(min(p['vm'].at[b] for b in buses)) for p in points]
    x_voltage = _first_crossing(xs, min_vm_series, min_vm, below=True)
    voltage_bus = None
    if x_voltage is not None:
        best = None
        for b in buses:
            xb = _first_crossing(xs, [float(p['vm'].at[b]) for p in points], min_vm, below=True)
            if xb is not None and (best is None or xb < best[0]):
                best = (xb, b)
        if best:
            x_voltage, voltage_bus = best[0], best[1]

    x_thermal, thermal_element = None, None
    for table in ('line', 'trafo', 'trafo3w'):
        if table not in points[0]:
            continue
        for idx in points[0][table].index:
            series = [float(p[table].at[idx]) if table in p else float('nan') for p in points]
            xe = _first_crossing(xs, series, max_loading, below=False)
            if xe is not None and (x_thermal is None or xe < x_thermal):
                x_thermal, thermal_element = xe, (table, idx)

    limits = [{'kind': 'collapse', 'x_mw': tip_x,
               'label': 'Voltage collapse (tip of the curve)'}]
    if x_voltage is not None:
        limits.append({'kind': 'voltage', 'x_mw': x_voltage,
                       'label': f"Voltage below {min_vm:g} p.u.",
                       'element': _friendly(net, 'bus', voltage_bus),
                       'element_id': _element_id(net, 'bus', voltage_bus)})
    if x_thermal is not None:
        table, idx = thermal_element
        kind_label = 'Line' if table == 'line' else 'Transformer'
        limits.append({'kind': 'thermal', 'x_mw': x_thermal,
                       'label': f"{kind_label} above {max_loading:g} %",
                       'element': _friendly(net, table, idx),
                       'element_id': _element_id(net, table, idx),
                       'element_type': table})
    limits.sort(key=lambda item: item['x_mw'])
    for item in limits:
        item['margin_mw'] = item['x_mw'] - base_x
        item['margin_percent'] = (100.0 * (item['x_mw'] - base_x) / base_x) if base_x > 0 else None
        item['already_violated'] = item['x_mw'] <= base_x + 1e-9
    binding = limits[0]

    # --- buses ranked by how far the voltage falls
    ranked = sorted(buses, key=lambda b: float(tip['vm'].at[b]))
    shown = ranked[:SHOWN_CURVES]
    if bus_idx is not None and bus_idx not in shown:
        shown = [bus_idx] + shown[:SHOWN_CURVES - 1]
    curves = [{
        'bus': _friendly(net, 'bus', b),
        'bus_id': _element_id(net, 'bus', b),
        'vn_kv': float(net.bus.at[b, 'vn_kv']),
        'is_study_bus': bool(bus_idx is not None and b == bus_idx),
        'vm_pu': [float(p['vm'].at[b]) for p in points],
    } for b in shown]
    weakest = [{
        'bus': _friendly(net, 'bus', b),
        'bus_id': _element_id(net, 'bus', b),
        'vn_kv': float(net.bus.at[b, 'vn_kv']),
        'vm_start_pu': float(points[0]['vm'].at[b]),
        'vm_tip_pu': float(tip['vm'].at[b]),
        'drop_pu': float(points[0]['vm'].at[b]) - float(tip['vm'].at[b]),
    } for b in ranked[:20]]

    def _worst(point):
        worst = point.get('worst_branch')
        if not worst:
            return None
        return {'loading_percent': worst[0], 'element': _friendly(net, worst[1], worst[2]),
                'element_type': worst[1]}

    result = {
        'study': 'voltage_stability',
        'mode': mode,
        'x_label': 'Added load at the bus [MW]' if mode == 'bus' else 'Total load [MW]',
        'base_mw': base_x,
        'system_load_mw': system_load,
        'tip_mw': tip_x,
        'tip_margin_mw': tip_x - base_x,
        'tip_margin_percent': (100.0 * (tip_x - base_x) / base_x) if base_x > 0 else None,
        'tip_min_vm_pu': float(min_vm_series[-1]),
        'tip_tolerance_percent': tolerance * 100.0,
        'min_vm_pu': min_vm,
        'max_loading_percent': max_loading,
        'power_factor': power_factor if mode == 'bus' else None,
        'study_bus': _friendly(net, 'bus', bus_idx) if bus_idx is not None else None,
        'limits': limits,
        'binding_limit': binding,
        'x_mw': xs,
        'min_vm_pu_series': min_vm_series,
        'max_loading_series': [(p['worst_branch'][0] if p.get('worst_branch') else None) for p in points],
        'slack_p_mw_series': [p.get('slack_p_mw') for p in points],
        'slack_q_mvar_series': [p.get('slack_q_mvar') for p in points],
        'curves': curves,
        'weakest_buses': weakest,
        'worst_branch_start': _worst(points[0]),
        'worst_branch_tip': _worst(tip),
        'load_flows_run': grower.solves,
        'notes': [
            "The extra power comes from the slack (External Grid or slack generator); other generators keep their set points.",
            f"The tip is the last point that solved, within {tolerance * 100.0:g} % of the true tip and slightly below it.",
        ],
    }
    warnings_out = [str(w) for w in (getattr(net, 'warnings', None) or [])]
    if warnings_out:
        result['warnings'] = warnings_out
    return pe._sanitize_for_strict_json(result)
