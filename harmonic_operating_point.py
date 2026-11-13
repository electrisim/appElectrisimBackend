"""Helpers of the OpenDSS harmonic study that do not need the OpenDSS engine.

- ``parse_harmonic_orders``: "3,5,7", "2-50" or "5,7,11-25" -> sorted list of orders.
- ``controlled_operating_point`` / ``apply_operating_point``: the fundamental-frequency
  operating point of the harmonic study, taken from the pandapower load flow.

  OpenDSS has no Park Controller, no Plant Supervisory Controller, no STATCOM (SSC) and no
  transformer tap control. On a network that only solves with them (a long-cable offshore wind
  farm: turbines dispatched by the park controller, a STATCOM at its limit, reactor steps
  following the export power) the OpenDSS load flow collapses and the harmonic solution cannot
  start. The pandapower load flow applies all of them, so its result (turbine Q, STATCOM Q,
  reactor steps, tap positions) is written into the OpenDSS data as fixed values.
- ``find_resonances``: parallel / series resonances of an impedance scan.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import math

MAX_HARMONIC_ORDER = 100
MAX_HARMONIC_COUNT = 200


def parse_harmonic_orders(harmonics, default=(3, 5, 7, 11, 13)):
    """Integer harmonic orders (> 1) from text such as "3,5,7", "2-50", "5;7;11-25" or a list."""
    tokens = []
    if isinstance(harmonics, str):
        text = harmonics.replace(';', ',')
        for sep in (' - ', ' -', '- '):
            text = text.replace(sep, '-')
        tokens = [t.strip() for t in text.replace(' ', ',').split(',')]
    elif isinstance(harmonics, (list, tuple)):
        tokens = [str(t).strip() for t in harmonics]
    orders = set()
    for token in tokens:
        if not token:
            continue
        parts = [p.strip() for p in token.replace('..', '-').replace('–', '-').split('-')]
        try:
            if len(parts) == 2 and parts[0] and parts[1]:
                lo, hi = int(float(parts[0])), int(float(parts[1]))
                if lo > hi:
                    lo, hi = hi, lo
                for h in range(max(lo, 2), min(hi, MAX_HARMONIC_ORDER) + 1):
                    orders.add(h)
            else:
                h = int(float(parts[0]))
                if 1 < h <= MAX_HARMONIC_ORDER:
                    orders.add(h)
        except (TypeError, ValueError):
            continue
    out = sorted(orders)[:MAX_HARMONIC_COUNT]
    return out or list(default)


def _f(value, default=0.0):
    try:
        out = float(value)
        return out if math.isfinite(out) else default
    except (TypeError, ValueError):
        return default


def _params_key(network):
    for key, element in network.items():
        if isinstance(element, dict) and 'PowerFlowPandaPower' in str(element.get('typ', '')):
            return key
    return None


def controlled_operating_point(network, frequency=50.0):
    """Run the pandapower load flow (with its controllers) on ``network``.

    ``network`` is the pandapower request the frontend builds for the Load Flow study. Returns a
    dict: ``ok``, ``error``, ``warnings``, and per element name the values to fix in OpenDSS
    (``sgen_q``, ``shunts``, ``taps``, ``sscs``, ``bus_vm_pu``).
    """
    op = {'ok': False, 'error': None, 'warnings': [], 'sgen_q': {}, 'shunts': {}, 'taps': {},
          'sscs': {}, 'bus_vm_pu': {}, 'summary': {}}
    if not isinstance(network, dict) or not network:
        op['error'] = 'no network data for the pandapower load flow'
        return op
    x = _params_key(network)
    if x is None:
        op['error'] = 'the pandapower load flow settings are missing'
        return op
    try:
        import pandapower as pp
        import pandapower_electrisim as ppe

        params = network[x]
        with contextlib.redirect_stdout(io.StringIO()):
            net = pp.create_empty_network(f_hz=float(frequency))
            busbars = ppe.create_busbars(network, net)
            ppe.create_other_elements(network, net, x, busbars)
            ppe.apply_load_flow_dialog_settings(net, params)
            rc2, rc3, rcs = ppe._resolve_controller_family_flags(params)
            raw = ppe.powerflow(
                net, params.get('algorithm', 'nr'), params.get('calculate_voltage_angles', 'auto'),
                params.get('initialization', 'auto'), False, network, busbars,
                run_control_trafo2w=rc2, run_control_trafo3w=rc3, run_control_shunt=rcs)
        result = json.loads(raw) if isinstance(raw, str) else raw
    except Exception as exc:  # pragma: no cover - reported to the user
        op['error'] = f'the pandapower load flow failed: {exc}'
        return op
    if not isinstance(result, dict) or result.get('error'):
        message = result.get('error') if isinstance(result, dict) else 'no result'
        if isinstance(message, (dict, list)):
            message = json.dumps(message)[:300]
        op['error'] = f'the pandapower load flow did not solve: {message}'
        return op

    op['warnings'] = [str(w) for w in (result.get('warnings') or [])]
    for row in result.get('busbars') or []:
        if row.get('name') and row.get('vm_pu') is not None:
            op['bus_vm_pu'][str(row['name'])] = _f(row.get('vm_pu'))
    for row in result.get('staticgenerators') or []:
        if row.get('name'):
            op['sgen_q'][str(row['name'])] = {'p_mw': _f(row.get('p_mw')), 'q_mvar': _f(row.get('q_mvar'))}
    for row in result.get('shunts') or []:
        vm = _f(row.get('vm_pu'), 1.0)
        if not row.get('name') or vm < 0.1:
            continue
        op['shunts'][str(row['name'])] = {
            'p_mw': _f(row.get('p_mw')) / vm ** 2, 'q_mvar': _f(row.get('q_mvar')) / vm ** 2,
            'step': row.get('step')}
    ssc_inputs = {str(e.get('name')): e for e in network.values()
                  if isinstance(e, dict) and str(e.get('typ', '')) == 'SSC'}
    for row in result.get('sscs') or []:
        name = str(row.get('name') or '')
        if not name:
            continue
        src = ssc_inputs.get(name, {})
        q_max = max(abs(_f(row.get('q_max_mvar'))), abs(_f(row.get('q_min_mvar'))), abs(_f(row.get('q_mvar'))))
        op['sscs'][name] = {
            # pandapower reports an SSC in load convention: negative = injecting (capacitive)
            'q_inject_mvar': -_f(row.get('q_mvar')),
            'r_ohm': _f(src.get('r_ohm')), 'x_ohm': _f(src.get('x_ohm')),
            'q_max_mvar': q_max, 'at_q_limit': row.get('at_q_limit'),
            'vm_pu': _f(row.get('vm_pu'), 1.0)}
    for table in ('trafo', 'trafo3w'):
        try:
            frame = getattr(net, table)
            for _, tr in frame.iterrows():
                name = tr.get('name')
                tap = tr.get('tap_pos')
                if name is not None and tap is not None and math.isfinite(float(tap)):
                    op['taps'][str(name)] = float(tap)
        except Exception:
            continue
    friendly = {str(e.get('name')): str(e.get('userFriendlyName') or e.get('name'))
                for e in network.values() if isinstance(e, dict) and e.get('name')}
    op['summary'] = {
        'tap_changes': [
            {'name': str(r.get('name')), 'from': r.get('tap_pos_initial'), 'to': r.get('tap_pos')}
            for r in (result.get('tap_control_results') or [])
            if r.get('tap_pos_initial') != r.get('tap_pos')],
        'shunt_steps': [
            {'name': str(r.get('name')), 'label': friendly.get(str(r.get('name')), str(r.get('name'))),
             'from': r.get('step_initial'), 'to': r.get('step')}
            for r in (result.get('shunt_control_results') or [])],
        'park_controllers': [str(r.get('name')) for r in (result.get('park_controller_results') or [])],
        'statcoms': [
            {'name': n, 'label': friendly.get(n, n), 'q_inject_mvar': round(s['q_inject_mvar'], 3),
             'at_q_limit': s['at_q_limit']}
            for n, s in op['sscs'].items()],
    }
    op['ok'] = True
    return op


def apply_operating_point(in_data, op):
    """Copy of the OpenDSS request with the pandapower operating point written in as fixed values."""
    out = copy.deepcopy(in_data)
    if not op or not op.get('ok'):
        return out
    for element in out.values():
        if not isinstance(element, dict):
            continue
        typ = str(element.get('typ', ''))
        name = str(element.get('name', ''))
        if typ.startswith('Static Generator') or typ.startswith('Wind Turbine'):
            row = op['sgen_q'].get(name)
            if row is not None:
                element['q_mvar'] = row['q_mvar']
                # the controller's Q replaces the unit's own Q rule
                element.pop('q_setpoint_mode', None)
        elif typ.startswith('Shunt Reactor'):
            row = op['shunts'].get(name)
            if row is not None:
                element.update({
                    'p_mw': row['p_mw'], 'q_mvar': row['q_mvar'], 'step': 1, 'max_step': 1,
                    'step_dependency_table': 'false', 'discrete_shunt_control': 'false',
                    'line_flow_step_control': 'false'})
        elif typ == 'SSC':
            row = op['sscs'].get(name)
            if row is not None:
                element.update(row)
        elif typ.startswith('Transformer') or typ.startswith('Two Winding') or typ.startswith('Three Winding'):
            tap = op['taps'].get(name)
            if tap is not None:
                element['tap_pos'] = tap
    return out


def find_resonances(orders, magnitudes, max_count=8):
    """Local maxima (parallel resonance) and minima (series resonance) of |Z| over the scan."""
    parallel, series = [], []
    n = min(len(orders), len(magnitudes))
    for i in range(1, n - 1):
        prev_z, z, next_z = magnitudes[i - 1], magnitudes[i], magnitudes[i + 1]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (prev_z, z, next_z)):
            continue
        if z > prev_z and z >= next_z:
            lo = min(magnitudes[max(0, i - 15):i + 16])
            if z > 1.3 * lo:                      # ignore ripples
                parallel.append({'order': round(float(orders[i]), 3), 'z_ohm': round(float(z), 4)})
        elif z < prev_z and z <= next_z:
            hi = max(magnitudes[max(0, i - 15):i + 16])
            if hi > 1.3 * z:
                series.append({'order': round(float(orders[i]), 3), 'z_ohm': round(float(z), 4)})
    parallel.sort(key=lambda r: -r['z_ohm'])
    series.sort(key=lambda r: r['z_ohm'])
    return (sorted(parallel[:max_count], key=lambda r: r['order']),
            sorted(series[:max_count], key=lambda r: r['order']))
