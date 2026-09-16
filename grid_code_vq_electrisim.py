# -*- coding: utf-8 -*-
"""
Grid Code Compliance (V-Q) — U-Q/Pmax at the point of connection.

Runs the P-Q capability engine at a single active-power setpoint (Pmax) and
sweeps PCC voltage. Plant Q via local units or Park Controller constant Q at PoC.
"""
from __future__ import annotations

import json
import traceback

import grid_code_pq_electrisim as gc_pq
import pandapower_electrisim as pp_el

GridCodeVqCancelled = gc_pq.GridCodePqCancelled


def _vq_float(v, default=0.0):
    return gc_pq._pq_float(v, default)


def _vq_build_uq_curve_from_pq(pq_results, p_target_mw):
    """Extract U-Q/Pmax capability from per-voltage P-Q curves at one P."""
    levels = pq_results.get('voltage_levels') or []
    curves = pq_results.get('curves') or {}
    return pp_el._rpc_build_uq_curve(levels, curves, float(p_target_mw))


def _vq_p_at_pmax_from_curves(pq_results):
    """Representative net P at PCC at the Pmax operating point (MW, abs)."""
    curves = pq_results.get('curves') or {}
    vals = []
    for curve in curves.values():
        if not isinstance(curve, dict):
            continue
        for key in ('p_max_mw', 'p_mw'):
            arr = curve.get(key) or []
            for p in arr:
                if p is None:
                    continue
                try:
                    vals.append(abs(float(p)))
                except (TypeError, ValueError):
                    pass
    if vals:
        return max(vals)
    pm = pq_results.get('pmax_pcc_mw')
    if pm is not None:
        try:
            return abs(float(pm))
        except (TypeError, ValueError):
            pass
    pn = pq_results.get('pn_mw')
    return float(pn) if pn else 0.0


def grid_code_vq_capability(net, vq_params, in_data=None):
    """
    V-Q (U-Q/Pmax) study. Returns JSON:
      { "grid_code_vq_results": { uq_curve, uq_requirements, uq_compliance, ... } }
    """
    try:
        voltage_levels = list(vq_params.get('voltage_levels') or [1.0])
        uq_requirements = vq_params.get('uq_requirements') or None
        if isinstance(uq_requirements, dict) and not uq_requirements.get('u_pu'):
            uq_requirements = None

        voltage_levels = pp_el._rpc_merge_uq_voltages(
            voltage_levels, uq_requirements, None)

        p_pct = _vq_float(vq_params.get('p_max_pct'), 100.0)
        if p_pct <= 0:
            p_pct = 100.0

        pq_params = dict(vq_params)
        pq_params['voltage_levels'] = voltage_levels
        pq_params['p_start_pct'] = p_pct
        pq_params['p_end_pct'] = p_pct
        pq_params['p_step_pct'] = max(p_pct, 1.0)
        pq_params['i_op_range'] = 0
        pq_params['requirements'] = None
        pq_params['grid_code_template_key'] = None
        pq_params['grid_code_template_name'] = None
        pq_params['i_output'] = False
        if 'i_show_pq0' not in vq_params:
            pq_params['i_show_pq0'] = False

        print('=== Grid Code Compliance (V-Q) starting ===', flush=True)
        raw = gc_pq.grid_code_pq_capability(net, pq_params, in_data)
        outer = json.loads(raw)
        if outer.get('error'):
            return raw

        pq_results = outer.get('grid_code_pq_results') or outer
        if pq_results.get('error'):
            return json.dumps({'error': pq_results['error']}, separators=(',', ':'))

        pn = float(pq_results.get('pn_mw') or pq_results.get('total_installed_mw') or 0)
        p_target = pn * (p_pct / 100.0) if pn > 0 else 0.0
        uq_curve = _vq_build_uq_curve_from_pq(pq_results, p_target)
        p_pcc_mw = _vq_p_at_pmax_from_curves(pq_results)

        uq_compliance = pp_el._rpc_check_uq_compliance(uq_curve, uq_requirements)

        i_park = bool(pq_results.get('i_park_ctrl'))
        result = {
            'grid_code_vq_results': {
                'voltage_levels': [round(float(v), 4) for v in voltage_levels],
                'uq_curve': uq_curve,
                'uq_requirements': uq_requirements if uq_requirements else {},
                'uq_compliance': uq_compliance,
                'curves': pq_results.get('curves') or {},
                'point_loadflows': pq_results.get('point_loadflows') or {},
                'warnings': pq_results.get('warnings') or [],
                'total_installed_mw': pq_results.get('total_installed_mw'),
                'pn_mw': pq_results.get('pn_mw'),
                'p_max_pct': round(p_pct, 4),
                'p_dispatch_mw': round(p_target, 4),
                'p_pcc_mw': round(p_pcc_mw, 4) if p_pcc_mw else None,
                'pmax_pcc_mw': pq_results.get('pmax_pcc_mw'),
                'un_kv': pq_results.get('un_kv'),
                'uc_kv': pq_results.get('uc_kv'),
                'pcc_bus_name': pq_results.get('pcc_bus_name'),
                'generator_count': pq_results.get('generator_count'),
                'uq_grid_code_template_name': vq_params.get('uq_grid_code_template_name'),
                'uq_grid_code_template_key': vq_params.get('uq_grid_code_template_key'),
                'q_capability_mode': pq_results.get('q_capability_mode'),
                'i_park_ctrl': i_park,
                'q_dispatch_mode': pq_results.get('q_dispatch_mode'),
                'park_controller_name': pq_results.get('park_controller_name'),
                'generator_oriented': pq_results.get('generator_oriented', True),
                'summary': pq_results.get('summary') or {},
                'load_flow_count': pq_results.get('load_flow_count'),
                'tap_changer_control': pq_results.get('tap_changer_control'),
                'requirements_base': 'pn',
                'pcc_q_convention': (
                    'Red: Qmax/Qmin at the PCC at P = Pmax while voltage is swept. '
                    'Blue: U-Q/Pmax grid-code envelope in Q/Pmax × Pn (registered Pmax), '
                    'not scaled by collector losses. '
                    + (
                        'Plant Q is constant Q at the point of connection via the Park Controller.'
                        if i_park else
                        'Plant Q is set locally on each unit from its P–Q capability.'
                    )
                ),
            }
        }
        print('=== Grid Code Compliance (V-Q) finished ===', flush=True)
        return json.dumps(result, default=pp_el._json_serialize_default, separators=(',', ':'))

    except GridCodeVqCancelled:
        print('=== Grid Code Compliance (V-Q) stopped by user ===', flush=True)
        raise
    except Exception as e:
        traceback.print_exc()
        return json.dumps(
            {'error': f'Grid Code Compliance (V-Q) failed: {str(e)}'},
            separators=(',', ':'))
