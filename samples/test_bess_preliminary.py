# -*- coding: utf-8 -*-
"""Smoke test for BESS preliminary design backend."""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandapower as pp
import pandapower_electrisim as pp_el
import bess_preliminary_electrisim as bess_prelim


def _minimal_bess_net():
    """Simple 2-bus + storage network for envelope dispatch checks."""
    net = pp.create_empty_network(f_hz=50)
    b_hv = pp.create_bus(net, vn_kv=132, name='POC_HV')
    b_mv = pp.create_bus(net, vn_kv=33, name='MV_Collection')
    pp.create_ext_grid(net, bus=b_hv, vm_pu=1.0, name='Grid')
    pp.create_transformer_from_parameters(
        net, hv_bus=b_hv, lv_bus=b_mv, sn_mva=60, vn_hv_kv=132, vn_lv_kv=33,
        vk_percent=12, vkr_percent=0.4, pfe_kw=0, i0_percent=0, name='POC_Transformer',
        tap_side='hv', tap_min=-5, tap_max=5, tap_neutral=0, tap_pos=0, tap_step_percent=1.25,
        tap_changer_type='Ratio')
    b_lv = pp.create_bus(net, vn_kv=0.69, name='LV_Bus_1')
    pp.create_transformer_from_parameters(
        net, hv_bus=b_mv, lv_bus=b_lv, sn_mva=15, vn_hv_kv=33, vn_lv_kv=0.69,
        vk_percent=8, vkr_percent=0.5, pfe_kw=0, i0_percent=0, name='MV_LV_Trafo_1')
    pp.create_storage(net, bus=b_lv, p_mw=0, q_mvar=0, sn_mva=15, max_e_mwh=30, name='BESS_1')
    pp.create_load(net, bus=b_mv, p_mw=0.5, q_mvar=0.1, name='Aux_Load')
    return net


def _two_unit_bess_net():
    """Same plant with two BESS strings, for per-unit rating checks."""
    net = _minimal_bess_net()
    b_mv = pp.get_element_index(net, 'bus', 'MV_Collection')
    b_lv2 = pp.create_bus(net, vn_kv=0.69, name='LV_Bus_2')
    pp.create_transformer_from_parameters(
        net, hv_bus=b_mv, lv_bus=b_lv2, sn_mva=15, vn_hv_kv=33, vn_lv_kv=0.69,
        vk_percent=8, vkr_percent=0.5, pfe_kw=0, i0_percent=0, name='MV_LV_Trafo_2')
    pp.create_storage(net, bus=b_lv2, p_mw=0, q_mvar=0, sn_mva=15, max_e_mwh=30, name='BESS_2')
    return net


def _base_params(**over):
    params = {
        'pocBusName': 'POC_HV',
        'extGridName': 'Grid',
        'storageNames': ['BESS_1'],
        'storageSnMva': 15,
        'pMaxDischarge_MW': 8,
        'pMaxCharge_MW': 8,
        'pocP_MW': 8,
        'pocQ_Mvar': 2,
        'unom_pu': 1.0,
        'umin_pu': 0.95,
        'umax_pu': 1.05,
        'vmin_pu': 0.95,
        'vmax_pu': 1.05,
        'max_loading_percent': 100,
        'algorithm': 'nr',
        'hvTrafoName': 'POC_Transformer',
        'tapSweep': False,
        'tapQCapability': False,
        'oltcEnabled': False,
    }
    params.update(over)
    return params


def test_resolves_user_friendly_element_names():
    """Diagram cells use display names; pandapower stores mxCell ids."""
    net = _minimal_bess_net()
    poc = pp.get_element_index(net, 'bus', 'POC_HV')
    eg = pp.get_element_index(net, 'ext_grid', 'Grid')
    st = pp.get_element_index(net, 'storage', 'BESS_1')
    net.bus.at[poc, 'name'] = 'mxCell_poc'
    net.ext_grid.at[eg, 'name'] = 'mxCell_grid'
    net.storage.at[st, 'name'] = 'mxCell_bess'
    net.user_friendly_names = {
        'mxCell_poc': 'POC_HV',
        'mxCell_grid': 'Grid',
        'mxCell_bess': 'BESS_1',
    }
    r = bess_prelim._run_named_case(
        net, _base_params(),
        {'name': 'Unom_POC_Target', 'vm_pu': 1.0, 'target_p_mw': 8.0, 'target_q_mvar': 2.0})
    assert r['converged'] and r.get('target_met'), r


def test_envelope_runs_with_user_friendly_names():
    """The envelope engine matches pandapower names, so display names coming
    from the diagram must be translated before it is called."""
    net = _minimal_bess_net()
    poc = pp.get_element_index(net, 'bus', 'POC_HV')
    eg = pp.get_element_index(net, 'ext_grid', 'Grid')
    st = pp.get_element_index(net, 'storage', 'BESS_1')
    net.bus.at[poc, 'name'] = 'mxCell_140'
    net.ext_grid.at[eg, 'name'] = 'mxCell_141'
    net.storage.at[st, 'name'] = 'mxCell_151'
    net.user_friendly_names = {
        'mxCell_140': 'POC_HV',
        'mxCell_141': 'Grid',
        'mxCell_151': 'BESS_1',
    }
    env = bess_prelim._run_pq_envelope(net, _base_params(), {})
    assert env and not env.get('error'), env
    assert env.get('curves'), env
    names = [lim.get('name') for curve in env['curves'].values()
             for key in ('limit_max', 'limit_min')
             for lim in (curve.get(key) or []) if isinstance(lim, dict)]
    assert names, env
    assert not any(str(n).startswith('mxCell_') for n in names), names


def test_poc_target_is_met_including_aux_and_losses():
    """The requested POC P/Q must actually be delivered, not just the PCS
    setpoint: auxiliaries and transformer losses are the plant's to cover."""
    net = _minimal_bess_net()
    params = _base_params()
    case = {'name': 'Unom_POC_Target', 'vm_pu': 1.0, 'target_p_mw': 8.0, 'target_q_mvar': 2.0}
    r = bess_prelim._run_named_case(net, params, case)
    assert r['converged'], r
    assert r['target_met'], r
    assert abs(r['p_poc_mw'] - 8.0) <= 0.05, r
    assert abs(r['q_poc_mvar'] - 2.0) <= 0.05, r
    # Discharging more than the POC target proves losses were absorbed.
    assert r['pcs_p_each_mw'] < -8.0, r


def test_poc_target_flags_infeasible_request():
    """A request beyond the PCS rating must fail rather than silently clamp."""
    net = _minimal_bess_net()
    params = _base_params(pocP_MW=40, storageSnMva=15)
    case = {'name': 'Unom_POC_Target', 'vm_pu': 1.0, 'target_p_mw': 40.0, 'target_q_mvar': 0.0}
    r = bess_prelim._run_named_case(net, params, case)
    assert not r.get('target_met'), r
    assert r.get('rating_clamped'), r


def test_qmax_uses_per_unit_rating_not_plant_share():
    """storageSnMva is the per-unit PCS rating, so each unit's Q command must
    not be divided by the number of units."""
    one = bess_prelim._build_named_cases(_base_params(storageNames=['BESS_1']))
    two = bess_prelim._build_named_cases(_base_params(storageNames=['BESS_1', 'BESS_2']))

    def qcap(cases):
        c = next(c for c in cases if c['name'] == 'Unom_Qmax_Capacitive')
        return abs(c['q_each'])

    assert qcap(one) == qcap(two) == 15.0, (qcap(one), qcap(two))


def test_pmax_uses_per_unit_rating_not_plant_share():
    """pMaxDischarge_MW is per PCS, so rated-discharge p_each must not be / N."""
    one = bess_prelim._build_named_cases(_base_params(storageNames=['BESS_1'], pMaxDischarge_MW=8))
    two = bess_prelim._build_named_cases(
        _base_params(storageNames=['BESS_1', 'BESS_2'], pMaxDischarge_MW=8))

    def pdis(cases):
        c = next(c for c in cases if c['name'] == 'Unom_Rated_Discharge')
        return c['p_each']

    assert pdis(one) == pdis(two) == -8.0, (pdis(one), pdis(two))


def test_two_unit_plant_doubles_active_export():
    net = _two_unit_bess_net()
    params = _base_params(storageNames=['BESS_1', 'BESS_2'], pMaxDischarge_MW=8)
    cases = bess_prelim._build_named_cases(params)
    case = next(c for c in cases if c['name'] == 'Unom_Rated_Discharge')
    r = bess_prelim._run_named_case(net, params, case)
    assert r['converged'], r
    # Two 8 MW units minus aux/losses should still exceed one unit's export.
    assert r['p_poc_mw'] > 12.0, r
    assert r.get('p_loss_mw') is not None and r['p_loss_mw'] > 0, r


def test_two_unit_plant_doubles_reactive_export():
    net = _two_unit_bess_net()
    params = _base_params(storageNames=['BESS_1', 'BESS_2'], storageSnMva=6)
    cases = bess_prelim._build_named_cases(params)
    case = next(c for c in cases if c['name'] == 'Unom_Qmax_Capacitive')
    r = bess_prelim._run_named_case(net, params, case)
    assert r['converged'], r
    # Two 6 Mvar units, minus transformer reactive losses.
    assert r['q_poc_mvar'] > 6.0, r


def test_out_of_service_transformer_does_not_break_loadings():
    net = _two_unit_bess_net()
    t2 = pp.get_element_index(net, 'trafo', 'MV_LV_Trafo_2')
    net.trafo.at[t2, 'in_service'] = False
    net.storage.at[pp.get_element_index(net, 'storage', 'BESS_2'), 'in_service'] = False
    assert bess_prelim._run_lf(net)
    loadings = bess_prelim._collect_element_loadings(net)
    names = [e['name'] for e in loadings]
    assert 'MV_LV_Trafo_1' in names
    assert 'MV_LV_Trafo_2' not in names


def test_p_sweep_covers_charge_and_discharge():
    """The envelope must span both export and import of active power."""
    pts = bess_prelim.gc_pq._pq_p_sweep(
        pn=10.0, p_start_pct=0, p_step_pct=20, p_end_pct=100, i_op_range=2)
    assert min(pts) < 0 < max(pts), pts
    assert abs(min(pts) + 10.0) < 1e-6 and abs(max(pts) - 10.0) < 1e-6, pts


def test_envelope_sign_and_voltage_dependence():
    """Qmax must be capacitive (positive) and Qmin inductive (negative) in the
    export-positive POC convention, and the curves must differ by voltage."""
    net = _minimal_bess_net()
    res = json.loads(bess_prelim.bess_preliminary_study(
        net, _base_params(tapSweep=False), {}))['bess_preliminary_results']
    env = res['pq_envelope']
    assert env and not env.get('error'), env
    curves = env['curves']
    assert len(curves) == 3, list(curves)
    for key, c in curves.items():
        assert max(c['q_max_mvar']) > 0, (key, c['q_max_mvar'])
        assert min(c['q_min_mvar']) < 0, (key, c['q_min_mvar'])
        for qmax, qmin in zip(c['q_max_mvar'], c['q_min_mvar']):
            assert qmax >= qmin, (key, qmax, qmin)
        assert min(c['p_mw']) < 0 < max(c['p_mw']), (key, c['p_mw'])
        assert c.get('limit_max') and len(c['limit_max']) == len(c['p_mw']), key
        assert any(lim and lim.get('type') for lim in c['limit_max']), (key, c['limit_max'])
    lo = curves['0.9500']['q_max_mvar']
    hi = curves['1.0500']['q_max_mvar']
    assert lo != hi, (lo, hi)


def test_named_case_voltage_profile_and_pcs_nameplate():
    net = _minimal_bess_net()
    r = bess_prelim._run_named_case(
        net, _base_params(),
        {'name': 'Unom_POC_Target', 'vm_pu': 1.0, 'target_p_mw': 8.0, 'target_q_mvar': 2.0})
    assert r['converged'], r
    names = {b['name'] for b in (r.get('voltage_profile') or [])}
    assert 'POC_HV' in names and 'MV_Collection' in names and 'LV_Bus_1' in names, names
    pcs = [e for e in r['elements'] if e.get('type') == 'storage']
    assert pcs and pcs[0].get('sn_mva') == 15, pcs
    assert r.get('p_loss_mw') is not None and r['p_loss_mw'] > 0, r
    trafos = [e for e in r['elements'] if e.get('type') == 'transformer']
    assert any(t.get('sn_mva') for t in trafos), trafos


def test_tap_sweep_available_q_at_poc():
    """Available Q at the POC must be reported per tap, capacitive positive."""
    net = _minimal_bess_net()
    ti = pp.get_element_index(net, 'trafo', 'POC_Transformer')
    net.trafo.at[ti, 'tap_min'] = -1
    net.trafo.at[ti, 'tap_max'] = 1
    rows = [r for r in bess_prelim._tap_sweep(
        net, _base_params(tapSweep=True, tapQCapability=True)) if r.get('converged')]
    assert len(rows) == 3, rows
    for r in rows:
        assert r.get('q_max_mvar') is not None and r['q_max_mvar'] > 0, r
        assert r.get('q_min_mvar') is not None and r['q_min_mvar'] < 0, r
        assert r['q_max_mvar'] >= r['q_min_mvar'], r
        assert r.get('q_max_limiter'), r
    volts = [r['mv_vm_pu'] for r in rows]
    assert max(volts) - min(volts) > 1e-3, volts


def test_preliminary_study_exposes_profile_and_ratings():
    net = _minimal_bess_net()
    case = bess_prelim._run_named_case(
        net, _base_params(),
        {'name': 'Unom_POC_Target', 'vm_pu': 1.0, 'target_p_mw': 8.0, 'target_q_mvar': 2.0})
    ratings = bess_prelim._rating_table(net, [case])
    types = {el.get('type') for el in ratings}
    assert 'storage' in types and 'transformer' in types, types
    assert any(el.get('sn_mva') for el in ratings if el.get('type') == 'storage'), ratings


def test_voltage_level_changes_poc_result():
    net = _minimal_bess_net()
    params = _base_params()
    base = {'p_each': -8.0, 'q_each': 0.0}
    lo = bess_prelim._run_named_case(net, params, dict(name='Umin', vm_pu=0.95, **base))
    hi = bess_prelim._run_named_case(net, params, dict(name='Umax', vm_pu=1.05, **base))
    assert lo['converged'] and hi['converged']
    assert abs(lo['q_poc_mvar'] - hi['q_poc_mvar']) > 1e-3, (lo, hi)


def test_tap_sweep_moves_internal_voltage():
    net = _minimal_bess_net()
    params = _base_params(tapSweep=True)
    rows = [r for r in bess_prelim._tap_sweep(net, params) if r.get('converged')]
    assert len(rows) >= 3, rows
    volts = [r['mv_vm_pu'] for r in rows if r.get('mv_vm_pu') is not None]
    assert max(volts) - min(volts) > 1e-3, volts


def test_tap_sweep_reports_inactive_tap_changer():
    """An unusable tap changer must be reported, not silently swept."""
    net = _minimal_bess_net()
    net.trafo.at[pp.get_element_index(net, 'trafo', 'POC_Transformer'), 'tap_side'] = None
    rows = bess_prelim._tap_sweep(net, _base_params(tapSweep=True))
    assert len(rows) == 1 and rows[0].get('error') == 'inactive_tap_changer', rows


def test_named_case_converges():
    net = _minimal_bess_net()
    params = {
        'pocBusName': 'POC_HV',
        'extGridName': 'Grid',
        'storageNames': ['BESS_1'],
        'pMaxDischarge_MW': 10,
        'pMaxCharge_MW': 10,
        'pocP_MW': 10,
        'pocQ_Mvar': 2,
        'unom_pu': 1.0,
        'umin_pu': 0.95,
        'umax_pu': 1.05,
        'vmin_pu': 0.95,
        'vmax_pu': 1.05,
        'max_loading_percent': 100,
        'algorithm': 'nr',
        'hvTrafoName': 'POC_Transformer',
        'tapSweep': False,
        'oltcEnabled': False,
    }
    case = {
        'name': 'Unom_Rated_Discharge',
        'vm_pu': 1.0,
        'p_each': -10.0,
        'q_each': -2.0,
    }
    r = bess_prelim._run_named_case(net, params, case)
    assert r['converged'], r
    assert r.get('p_poc_mw') is not None


def test_preliminary_study_json():
    net = _minimal_bess_net()
    params = {
        'pocBusName': 'POC_HV',
        'extGridName': 'Grid',
        'storageNames': ['BESS_1'],
        'storageSnMva': 15,
        'pMaxDischarge_MW': 8,
        'pMaxCharge_MW': 8,
        'pocP_MW': 8,
        'pocQ_Mvar': 0,
        'unom_pu': 1.0,
        'umin_pu': 0.95,
        'umax_pu': 1.05,
        'vmin_pu': 0.95,
        'vmax_pu': 1.05,
        'max_loading_percent': 100,
        'algorithm': 'nr',
        'hvTrafoName': 'POC_Transformer',
        'tapSweep': True,
        'tapQCapability': False,
        'oltcEnabled': False,
    }
    raw = bess_prelim.bess_preliminary_study(net, params, {})
    data = json.loads(raw)
    assert 'bess_preliminary_results' in data
    res = data['bess_preliminary_results']
    assert len(res['named_cases']) >= 1
    assert res['summary']['total_cases'] >= 1


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    failed = []
    for t in tests:
        try:
            t()
            print(f'PASS {t.__name__}')
        except Exception as ex:
            failed.append((t.__name__, ex))
            print(f'FAIL {t.__name__}: {ex}')
    if failed:
        sys.exit(f'{len(failed)} of {len(tests)} tests failed')
    print(f'OK ({len(tests)} tests)')
