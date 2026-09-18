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
        'powerFactor': 0.95,
    }
    params.update(over)
    return params


def test_sld_identity_keys_use_cell_id_and_display_name():
    """SLD painter matches mxGraph cell.id plus diagram display names."""
    net = _minimal_bess_net()
    poc = pp.get_element_index(net, 'bus', 'POC_HV')
    st = pp.get_element_index(net, 'storage', 'BESS_1')
    net.bus['id'] = [None] * len(net.bus)
    net.storage['id'] = [None] * len(net.storage)
    net.bus.at[poc, 'id'] = 'cell-poc'
    net.storage.at[st, 'id'] = 'cell-bess'
    net.bus.at[poc, 'name'] = 'mxCell_poc'
    net.storage.at[st, 'name'] = 'mxCell_bess'
    net.user_friendly_names = {
        'mxCell_poc': 'POC_HV',
        'mxCell_bess': 'BESS_1',
        'MV_Collection': 'MV_Collection',
        'LV_Bus_1': 'LV_Bus_1',
        'Grid': 'Grid',
        'POC_Transformer': 'POC_Transformer',
        'MV_LV_Trafo_1': 'MV_LV_Trafo_1',
        'Aux_Load': 'Aux_Load',
    }
    r = bess_prelim._run_named_case(
        net, _base_params(),
        {'name': 'Unom_POC_Target', 'vm_pu': 1.0, 'target_p_mw': 8.0, 'target_q_mvar': 2.0})
    assert r['converged'], r
    poc_row = next(b for b in r['voltage_profile'] if b['name'] == 'POC_HV')
    assert poc_row['id'] == 'cell-poc', poc_row
    assert poc_row['technical_name'] == 'mxCell_poc', poc_row
    bess_row = next(e for e in r['elements'] if e.get('type') == 'storage')
    assert bess_row['id'] == 'cell-bess' and bess_row['name'] == 'BESS_1', bess_row


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


def test_qpf_corners_are_plant_level_targets():
    """Grid-code Q is a plant requirement at Pn, not a per-PCS split in the case list."""
    q_plant = bess_prelim._q_from_p_pf(8, 0.95)
    one = bess_prelim._build_named_cases(_base_params(storageNames=['BESS_1'], pocP_MW=8, powerFactor=0.95))
    two = bess_prelim._build_named_cases(
        _base_params(storageNames=['BESS_1', 'BESS_2'], pocP_MW=8, powerFactor=0.95))
    for cases in (one, two):
        cap = next(c for c in cases if c['name'] == 'Unom_Export_Capacitive')
        assert abs(cap['target_p_mw'] - 8) < 1e-9 and abs(cap['target_q_mvar'] - q_plant) < 1e-9, cap
        ind = next(c for c in cases if c['name'] == 'Unom_Export_Inductive')
        assert abs(ind['target_q_mvar'] + q_plant) < 1e-9, ind
        imp = next(c for c in cases if c['name'] == 'Unom_Import_Capacitive')
        assert abs(imp['target_p_mw'] + 8) < 1e-9, imp


def test_battery_pmax_caps_named_case_p():
    cases = bess_prelim._build_named_cases(_base_params(
        storageNames=['BESS_1'], pMaxDischarge_MW=12, batteryPmax_MW=5, pocP_MW=12))
    dis = next(c for c in cases if c['name'] == 'Unom_Rated_Discharge')
    assert dis['p_each'] == -5.0, dis


def test_poc_target_clamped_by_battery_pmax():
    """POC Pn above Battery DC Pmax must fail the target and name that limiter."""
    net = _minimal_bess_net()
    params = _base_params(
        pMaxDischarge_MW=12, pMaxCharge_MW=12, batteryPmax_MW=5,
        pocP_MW=12, storageSnMva=15)
    r = bess_prelim._run_named_case(
        net, params,
        {'name': 'Unom_POC_Target', 'vm_pu': 1.0, 'target_p_mw': 12.0, 'target_q_mvar': 0.0})
    assert r.get('rating_clamped'), r
    assert not r.get('target_met'), r
    assert r.get('clamp_reason') == 'Battery DC Pmax', r
    assert abs(r.get('pcs_p_each_mw', 0)) <= 5.0 + 1e-6, r
    lim = r.get('limiting_element') or {}
    assert lim.get('type') == 'battery_dc' or lim.get('name') in (
        'Battery DC Pmax', 'Battery_1'), lim


def test_poc_target_still_moves_q_when_p_is_at_battery_pmax():
    """Battery DC Pmax must not freeze Q at the 1.03 seed (wrong-sign POC Q)."""
    net = _minimal_bess_net()
    params = _base_params(
        pMaxDischarge_MW=8, pMaxCharge_MW=8, batteryPmax_MW=8,
        pocP_MW=8, storageSnMva=15)
    r = bess_prelim._run_named_case(
        net, params,
        {'name': 'Unom_POC_Target', 'vm_pu': 1.0, 'target_p_mw': 8.0, 'target_q_mvar': 2.0})
    assert r['converged'], r
    assert abs((r.get('q_poc_mvar') or 0) - 2.0) <= 0.08, r


def _three_winding_skid_net(sn_hv=60, sn_w=30):
    """One MV/LV 3W skid with two 690 V buses and four PCS (2 per winding)."""
    net = pp.create_empty_network(f_hz=50)
    b_hv = pp.create_bus(net, vn_kv=132, name='POC_HV')
    b_mv = pp.create_bus(net, vn_kv=33, name='MV_Collection')
    pp.create_ext_grid(net, bus=b_hv, vm_pu=1.0, name='Grid')
    pp.create_transformer_from_parameters(
        net, hv_bus=b_hv, lv_bus=b_mv, sn_mva=60, vn_hv_kv=132, vn_lv_kv=33,
        vk_percent=12, vkr_percent=0.4, pfe_kw=0, i0_percent=0, name='POC_Transformer',
        tap_side='hv', tap_min=-5, tap_max=5, tap_neutral=0, tap_pos=0, tap_step_percent=1.25,
        tap_changer_type='Ratio')
    b_str = pp.create_bus(net, vn_kv=33, name='String_HV_1')
    pp.create_line_from_parameters(
        net, from_bus=b_mv, to_bus=b_str, length_km=0.3,
        r_ohm_per_km=0.08, x_ohm_per_km=0.12, c_nf_per_km=0, max_i_ka=1.0,
        name='MV_Cable_1')
    b_a = pp.create_bus(net, vn_kv=0.69, name='LV_Bus_1A')
    b_b = pp.create_bus(net, vn_kv=0.69, name='LV_Bus_1B')
    pp.create_transformer3w_from_parameters(
        net, hv_bus=b_str, mv_bus=b_a, lv_bus=b_b,
        sn_hv_mva=sn_hv, sn_mv_mva=sn_w, sn_lv_mva=sn_w,
        vn_hv_kv=33, vn_mv_kv=0.69, vn_lv_kv=0.69,
        vk_hv_percent=8, vk_mv_percent=8, vk_lv_percent=8,
        vkr_hv_percent=0.5, vkr_mv_percent=0.5, vkr_lv_percent=0.5,
        pfe_kw=0, i0_percent=0, name='MV_LV_Trafo3w_1')
    for i, bus in enumerate([b_a, b_a, b_b, b_b]):
        pp.create_storage(net, bus=bus, p_mw=0, q_mvar=0, sn_mva=15,
                          max_e_mwh=30, name=f'PCS_{i + 1}')
    pp.create_load(net, bus=b_mv, p_mw=0.5, q_mvar=0.1, name='Aux_Load')
    return net


def test_sized_three_winding_skid_meets_poc_target():
    net = _three_winding_skid_net(60, 30)
    names = ['PCS_1', 'PCS_2', 'PCS_3', 'PCS_4']
    params = _base_params(
        storageNames=names, storageSnMva=15,
        pMaxDischarge_MW=13, pMaxCharge_MW=13, batteryPmax_MW=13,
        pocP_MW=50, pocQ_Mvar=16.434, specifyQDirectly=True)
    r = bess_prelim._run_named_case(
        net, params,
        {'name': 'Unom_POC_Target', 'vm_pu': 1.0, 'target_p_mw': 50.0, 'target_q_mvar': 16.434})
    assert r['converged'], r
    assert r.get('target_met'), r
    lim = r.get('limiting_element') or {}
    assert (lim.get('loading_percent') or 0) < 120, lim


def _four_string_two_winding_net():
    """Four 2W strings, matching the wizard default 50 MW / 4 PCS plant."""
    net = pp.create_empty_network(f_hz=50)
    b_hv = pp.create_bus(net, vn_kv=132, name='POC_HV')
    b_mv = pp.create_bus(net, vn_kv=33, name='MV_Collection')
    pp.create_ext_grid(net, bus=b_hv, vm_pu=1.0, name='Grid')
    pp.create_transformer_from_parameters(
        net, hv_bus=b_hv, lv_bus=b_mv, sn_mva=60, vn_hv_kv=132, vn_lv_kv=33,
        vk_percent=12, vkr_percent=0.4, pfe_kw=0, i0_percent=0, name='POC_Transformer',
        tap_side='hv', tap_min=-5, tap_max=5, tap_neutral=0, tap_pos=0, tap_step_percent=1.25,
        tap_changer_type='Ratio')
    for i in range(4):
        b_str = pp.create_bus(net, vn_kv=33, name=f'String_HV_{i + 1}')
        pp.create_line_from_parameters(
            net, from_bus=b_mv, to_bus=b_str, length_km=0.3,
            r_ohm_per_km=0.08, x_ohm_per_km=0.12, c_nf_per_km=0, max_i_ka=0.5,
            name=f'MV_Cable_{i + 1}')
        b_lv = pp.create_bus(net, vn_kv=0.69, name=f'LV_Bus_{i + 1}')
        pp.create_transformer_from_parameters(
            net, hv_bus=b_str, lv_bus=b_lv, sn_mva=15, vn_hv_kv=33, vn_lv_kv=0.69,
            vk_percent=8, vkr_percent=0.5, pfe_kw=0, i0_percent=0,
            name=f'MV_LV_Trafo_{i + 1}')
        pp.create_storage(net, bus=b_lv, p_mw=0, q_mvar=0, sn_mva=15,
                          max_e_mwh=30, name=f'PCS_{i + 1}')
    pp.create_load(net, bus=b_mv, p_mw=0.5, q_mvar=0.1, name='Aux_Load')
    return net


def test_four_string_12mw_battery_cannot_meet_50mw_poc():
    """4 × 12 MW DC Pmax cannot export 50 MW; Q must still leave the 1.03 seed."""
    net = _four_string_two_winding_net()
    names = ['PCS_1', 'PCS_2', 'PCS_3', 'PCS_4']
    params = _base_params(
        storageNames=names, storageSnMva=15,
        pMaxDischarge_MW=12, pMaxCharge_MW=12, batteryPmax_MW=12,
        pocP_MW=50, pocQ_Mvar=16.434, specifyQDirectly=True)
    r = bess_prelim._run_named_case(
        net, params,
        {'name': 'Unom_POC_Target', 'vm_pu': 1.0, 'target_p_mw': 50.0, 'target_q_mvar': 16.434})
    assert r['converged'], r
    assert not r.get('target_met'), r
    assert r.get('clamp_reason') == 'Battery DC Pmax', r
    assert abs(r.get('pcs_p_each_mw', 0)) <= 12.0 + 1e-6, r
    assert abs(abs(r.get('pcs_q_each_mvar') or 0) - 4.232) > 0.2, r
    assert (r.get('q_poc_mvar') or 0) > 12.0, r


def test_four_string_suggested_pmax_meets_50mw_poc():
    net = _four_string_two_winding_net()
    names = ['PCS_1', 'PCS_2', 'PCS_3', 'PCS_4']
    params = _base_params(
        storageNames=names, storageSnMva=15,
        pMaxDischarge_MW=13.13, pMaxCharge_MW=13.13, batteryPmax_MW=13.13,
        pocP_MW=50, pocQ_Mvar=16.434, specifyQDirectly=True)
    r = bess_prelim._run_named_case(
        net, params,
        {'name': 'Unom_POC_Target', 'vm_pu': 1.0, 'target_p_mw': 50.0, 'target_q_mvar': 16.434})
    assert r['converged'], r
    assert r.get('target_met'), r


def test_undersized_three_winding_skid_flags_transformer():
    net = _three_winding_skid_net(15, 7.5)
    names = ['PCS_1', 'PCS_2', 'PCS_3', 'PCS_4']
    params = _base_params(
        storageNames=names, storageSnMva=15,
        pMaxDischarge_MW=12, pMaxCharge_MW=12, batteryPmax_MW=12,
        pocP_MW=50)
    r = bess_prelim._run_named_case(
        net, params,
        {'name': 'Unom_Rated_Discharge', 'vm_pu': 1.0, 'p_each': -12.0, 'q_each': 0.0})
    if r.get('converged'):
        lim = r.get('limiting_element') or {}
        assert lim.get('type') == 'transformer', lim
        assert (lim.get('loading_percent') or 0) > 200, lim
    else:
        assert r.get('limit_reason') in ('divergence', 'no_result'), r


def test_battery_dc_in_rating_table():
    net = _minimal_bess_net()
    params = _base_params(batteryPmax_MW=5, pMaxDischarge_MW=8, pocP_MW=5)
    case = bess_prelim._run_named_case(
        net, params,
        {'name': 'Unom_Rated_Discharge', 'vm_pu': 1.0, 'p_each': -5.0, 'q_each': 0.0})
    assert case['converged'], case
    batt = [e for e in case['elements'] if e.get('type') == 'battery_dc']
    assert batt, case['elements']
    assert abs(batt[0]['pmax_mw'] - 5) < 1e-9, batt
    assert batt[0]['loading_percent'] > 90, batt
    ratings = bess_prelim._rating_table(net, [case])
    assert any(el.get('type') == 'battery_dc' for el in ratings), ratings


def test_dc_island_is_stripped_so_ac_lf_still_runs():
    """Isolated DC rack on the SLD must not break the AC plant load-flow."""
    net = _minimal_bess_net()
    dc = pp.create_bus_dc(net, vn_kv=1.5, name='DC_Bus_1')
    pp.create_source_dc(net, bus_dc=dc, vm_pu=1.0, name='Battery_1')
    net.user_friendly_names = getattr(net, 'user_friendly_names', {}) or {}
    net.user_friendly_names['Battery_1'] = 'Battery_1'
    raw = bess_prelim.bess_preliminary_study(
        net, _base_params(batteryPmax_MW=5, tapSweep=False), {})
    res = json.loads(raw)['bess_preliminary_results']
    cases = [c for c in res['named_cases'] if c.get('converged')]
    assert cases, res['named_cases']
    batt = [e for e in (cases[0].get('elements') or []) if e.get('type') == 'battery_dc']
    assert batt and batt[0].get('name') == 'Battery_1', batt


def test_pmax_uses_per_unit_rating_not_plant_share():
    """Per-PCS nameplate is used only up to the user's POC Pn share."""
    one = bess_prelim._build_named_cases(_base_params(storageNames=['BESS_1'], pMaxDischarge_MW=8, pocP_MW=8))
    two = bess_prelim._build_named_cases(
        _base_params(storageNames=['BESS_1', 'BESS_2'], pMaxDischarge_MW=8, pocP_MW=8))

    def pdis(cases):
        c = next(c for c in cases if c['name'] == 'Unom_Rated_Discharge')
        return c['p_each']

    assert pdis(one) == -8.0, pdis(one)
    assert pdis(two) == -4.0, pdis(two)


def test_named_cases_do_not_exceed_poc_p():
    cases = bess_prelim._build_named_cases(
        _base_params(storageNames=['BESS_1', 'BESS_2'], pMaxDischarge_MW=20, pocP_MW=23.5))
    n = 2
    for c in cases:
        if 'p_each' in c:
            assert abs(c['p_each']) * n <= 23.5 + 1e-9, c
        if 'target_p_mw' in c:
            assert abs(c['target_p_mw']) <= 23.5 + 1e-9, c


def test_q_follows_power_factor():
    q = bess_prelim._q_from_p_pf(23.5, 0.95)
    assert abs(q / 23.5 - 0.3287) < 1e-3, q
    cases = bess_prelim._build_named_cases(
        _base_params(storageNames=['BESS_1'], pocP_MW=23.5, powerFactor=0.95, pMaxDischarge_MW=23.5))
    tgt = next(c for c in cases if c['name'] == 'Unom_Export_Capacitive')
    assert abs(tgt['target_q_mvar'] - q) < 1e-6, tgt
    ind = next(c for c in cases if c['name'] == 'Unom_Export_Inductive')
    assert abs(ind['target_q_mvar'] + q) < 1e-6, ind
    imp = next(c for c in cases if c['name'] == 'Unom_Import_Capacitive')
    assert abs(imp['target_p_mw'] + 23.5) < 1e-6, imp


def test_two_unit_plant_doubles_active_export():
    net = _two_unit_bess_net()
    params = _base_params(storageNames=['BESS_1', 'BESS_2'], pMaxDischarge_MW=8, pocP_MW=16)
    cases = bess_prelim._build_named_cases(params)
    case = next(c for c in cases if c['name'] == 'Unom_Rated_Discharge')
    r = bess_prelim._run_named_case(net, params, case)
    assert r['converged'], r
    assert r['p_poc_mw'] > 12.0, r
    assert r.get('p_loss_mw') is not None and r['p_loss_mw'] > 0, r


def test_two_unit_plant_doubles_reactive_export():
    net = _two_unit_bess_net()
    params = _base_params(
        storageNames=['BESS_1', 'BESS_2'], storageSnMva=15,
        pocP_MW=20, powerFactor=0.95, pMaxDischarge_MW=10)
    cases = bess_prelim._build_named_cases(params)
    case = next(c for c in cases if c['name'] == 'Unom_Export_Capacitive')
    r = bess_prelim._run_named_case(net, params, case)
    assert r['converged'], r
    assert r['q_poc_mvar'] > 4.0, r


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
    req = env.get('requirements') or {}
    sample = next(iter(req.values()), None)
    assert sample and sample.get('p_mw') and sample.get('q_req_max_mvar'), req
    uq = env.get('uq_at_rated_p')
    assert uq and isinstance(uq.get('compliant'), bool), uq
    assert uq.get('points') and uq.get('q_over_pn'), uq


def test_uq_at_rated_p_pass_and_fail():
    """U–Q at rated P covers the required |Q|/Pn at every inner-band voltage."""
    env = {
        'pn_mw': 50.0,
        'requirements': {
            '1.0000': {
                'p_mw': [-50.0, 50.0],
                'q_req_max_mvar': [16.43, 16.43],
                'q_req_min_mvar': [-16.43, -16.43],
                'q_over_pn': 0.3286,
            }
        },
        'curves': {
            '0.9500': {'p_mw': [-50.0, 50.0], 'q_max_mvar': [20.0, 20.0], 'q_min_mvar': [-20.0, -20.0]},
            '1.0000': {'p_mw': [-50.0, 50.0], 'q_max_mvar': [20.0, 20.0], 'q_min_mvar': [-20.0, -20.0]},
            '1.0500': {'p_mw': [-50.0, 50.0], 'q_max_mvar': [20.0, 20.0], 'q_min_mvar': [-20.0, -20.0]},
        },
    }
    params = {'umin_pu': 0.95, 'umax_pu': 1.05}
    ok = bess_prelim._assess_uq_at_rated_p(env, params)
    assert ok and ok['compliant'] is True, ok
    # Weak import / charge Q must not fail U–Q/Pmax (export only).
    env['curves']['0.9500']['q_max_mvar'] = [5.0, 20.0]
    env['curves']['0.9500']['q_min_mvar'] = [-5.0, -20.0]
    still_ok = bess_prelim._assess_uq_at_rated_p(env, params)
    assert still_ok and still_ok['compliant'] is True, still_ok
    env['curves']['1.0000']['q_max_mvar'] = [5.0, 5.0]
    env['curves']['1.0000']['q_min_mvar'] = [-20.0, -20.0]
    bad = bess_prelim._assess_uq_at_rated_p(env, params)
    assert bad and bad['compliant'] is False, bad
    fail_u = [p['u_pu'] for p in bad['points'] if not p['covers']]
    assert 1.0 in fail_u, fail_u


def test_uq_requirement_uses_grid_code_pn_not_pcc_pmax():
    """|Q|/Pn is tan(acos(PF)) at wizard Pn, not Q divided by a lower PCC Pmax."""
    env = {
        'pn_mw': 48.9,
        'requirements': {
            '1.0000': {
                'p_mw': [-50.0, 50.0],
                'q_req_max_mvar': [16.43, 16.43],
                'q_over_pn': 0.3286,
            }
        },
        'curves': {
            '0.9500': {'p_mw': [50.0], 'q_max_mvar': [16.5], 'q_min_mvar': [-16.5]},
            '1.0000': {'p_mw': [50.0], 'q_max_mvar': [16.5], 'q_min_mvar': [-16.5]},
            '1.0500': {'p_mw': [50.0], 'q_max_mvar': [16.5], 'q_min_mvar': [-16.5]},
        },
    }
    uq = bess_prelim._assess_uq_at_rated_p(env, {'umin_pu': 0.95, 'umax_pu': 1.05})
    assert uq and abs(uq['q_over_pn'] - 0.3286) < 1e-4, uq
    assert abs(uq['pn_mw'] - 50.0) < 1e-6, uq
    assert uq['compliant'] is True


def test_named_case_voltage_profile_and_pcs_nameplate():
    net = _minimal_bess_net()
    r = bess_prelim._run_named_case(
        net, _base_params(),
        {'name': 'Unom_POC_Target', 'vm_pu': 1.0, 'target_p_mw': 8.0, 'target_q_mvar': 2.0})
    assert r['converged'], r
    names = {b['name'] for b in (r.get('voltage_profile') or [])}
    assert 'POC_HV' in names and 'MV_Collection' in names and 'LV_Bus_1' in names, names
    assert all(b.get('id') for b in r['voltage_profile']), r['voltage_profile']
    pcs = [e for e in r['elements'] if e.get('type') == 'storage']
    assert pcs and pcs[0].get('sn_mva') == 15, pcs
    assert r.get('p_loss_mw') is not None and r['p_loss_mw'] > 0, r
    trafos = [e for e in r['elements'] if e.get('type') == 'transformer']
    assert any(t.get('sn_mva') for t in trafos), trafos
    loads = [e for e in r['elements'] if e.get('type') == 'load']
    assert loads and loads[0].get('name') == 'Aux_Load', loads
    assert loads[0].get('p_mw') is not None, loads


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


def test_named_cases_cover_four_quadrants_at_each_voltage():
    cases = bess_prelim._build_named_cases(
        _base_params(pocP_MW=23.5, powerFactor=0.95, pMaxDischarge_MW=23.5))
    names = {c['name'] for c in cases}
    for u in ('Umin', 'Unom', 'Umax'):
        for p in ('Export', 'Import'):
            for q in ('Capacitive', 'Inductive'):
                assert f'{u}_{p}_{q}' in names, names
        assert f'{u}_Rated_Discharge' in names and f'{u}_Rated_Charge' in names, names
    targets = [c for c in cases if 'target_p_mw' in c]
    assert len(targets) == 12, len(targets)


def test_oltc_regulates_mv_at_umin():
    """At Umin the POC OLTC must lift MV / string HV toward 1.0 pu."""
    net = _minimal_bess_net()
    case = {'name': 'Umin_Rated_Discharge', 'vm_pu': 0.95, 'p_each': -8.0, 'q_each': 0.0}

    def mv_pu(result):
        return next(b['vm_pu'] for b in result['voltage_profile'] if b['name'] == 'MV_Collection')

    off = bess_prelim._run_named_case(net, _base_params(oltcEnabled=False), case)
    on = bess_prelim._run_named_case(net, _base_params(oltcEnabled=True), case)
    assert off['converged'] and on['converged'], (off, on)
    assert mv_pu(on) > mv_pu(off) + 0.02, (mv_pu(off), mv_pu(on), on.get('tap_pos'))
    assert abs(mv_pu(on) - 1.0) < abs(mv_pu(off) - 1.0), (mv_pu(off), mv_pu(on))
    assert abs(on.get('tap_pos') or 0) >= 1, on


def test_rated_charge_poc_does_not_exceed_pn():
    """Auxiliaries and losses must not push charge import above the entered Pn."""
    net = _minimal_bess_net()
    params = _base_params(pMaxDischarge_MW=8, pMaxCharge_MW=8, pocP_MW=8)
    case = next(c for c in bess_prelim._build_named_cases(params)
                if c['name'] == 'Unom_Rated_Charge')
    r = bess_prelim._run_named_case(net, params, case)
    assert r['converged'], r
    assert abs(r['p_poc_mw']) <= 8.0 + 0.05, r


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
    case = next((c for c in res['named_cases'] if c.get('converged') and c.get('voltage_profile')), None)
    assert case, res['named_cases']
    bus = next((b for b in case['voltage_profile'] if b.get('name') == 'POC_HV' or b.get('id')), None)
    assert bus and bus.get('vm_pu') is not None, bus
    assert 'id' in bus and 'name' in bus, bus
    els = case.get('elements') or []
    assert any(el.get('type') == 'storage' and el.get('p_mw') is not None for el in els), els
    assert any(el.get('type') == 'transformer' and el.get('loading_percent') is not None for el in els), els


def test_tap_sweep_off_by_default_and_voltage_params_echoed():
    net = _minimal_bess_net()
    params = _base_params()
    params.pop('vmin_pu', None)
    params.pop('vmax_pu', None)
    params.pop('tapSweep', None)
    raw = bess_prelim.bess_preliminary_study(net, params, {})
    res = json.loads(raw)['bess_preliminary_results']
    assert not res.get('tap_sweep'), res.get('tap_sweep')
    assert abs(float(res['params']['vmin_pu']) - 0.90) < 1e-9
    assert abs(float(res['params']['vmax_pu']) - 1.10) < 1e-9


def _interp_q_at_p(p_arr, q_arr, p_want):
    pts = [(float(p), float(q)) for p, q in zip(p_arr or [], q_arr or [])
           if p is not None and q is not None]
    if not pts:
        return None
    pts.sort()
    p = min(pts[-1][0], max(pts[0][0], float(p_want)))
    if len(pts) == 1:
        return pts[0][1]
    for i in range(len(pts) - 1):
        if pts[i][0] <= p <= pts[i + 1][0]:
            den = pts[i + 1][0] - pts[i][0]
            t = 0.0 if den == 0 else (p - pts[i][0]) / den
            return pts[i][1] + t * (pts[i + 1][1] - pts[i][1])
    return pts[-1][1]


def _wizard_default_50mw_net():
    """Ratings matching BESS Preliminary Design Generate defaults (50 MW / PF 0.95)."""
    net = pp.create_empty_network(f_hz=50)
    b_hv = pp.create_bus(net, vn_kv=132, name='POC_HV')
    b_mv = pp.create_bus(net, vn_kv=33, name='MV_Collection')
    pp.create_ext_grid(net, bus=b_hv, vm_pu=1.0, name='Grid')
    pp.create_transformer_from_parameters(
        net, hv_bus=b_hv, lv_bus=b_mv, sn_mva=75, vn_hv_kv=132, vn_lv_kv=33,
        vk_percent=8, vkr_percent=0.4, pfe_kw=0, i0_percent=0, name='POC_Transformer',
        tap_side='hv', tap_min=-5, tap_max=5, tap_neutral=0, tap_pos=0,
        tap_step_percent=1.25, tap_changer_type='Ratio')
    pp.create_load(net, bus=b_mv, p_mw=0.5, q_mvar=0.1, name='Aux_Load')
    names = []
    for i in range(4):
        b_str = pp.create_bus(net, vn_kv=33, name=f'String_HV_{i + 1}')
        b_lv = pp.create_bus(net, vn_kv=0.69, name=f'LV_Bus_{i + 1}')
        pp.create_line_from_parameters(
            net, from_bus=b_mv, to_bus=b_str, length_km=0.3,
            r_ohm_per_km=0.08, x_ohm_per_km=0.12, c_nf_per_km=0, max_i_ka=0.6,
            name=f'MV_Cable_{i + 1}')
        pp.create_transformer_from_parameters(
            net, hv_bus=b_str, lv_bus=b_lv, sn_mva=22, vn_hv_kv=33, vn_lv_kv=0.69,
            vk_percent=6, vkr_percent=0.5, pfe_kw=0, i0_percent=0,
            name=f'MV_LV_Trafo_{i + 1}')
        pp.create_storage(
            net, bus=b_lv, p_mw=0, q_mvar=0, sn_mva=22, max_e_mwh=44,
            max_p_mw=15, min_p_mw=-15, max_q_mvar=22, min_q_mvar=-22,
            name=f'PCS_{i + 1}')
        names.append(f'PCS_{i + 1}')
    return net, names


def test_default_50mw_plant_pq_envelope_covers_pf_rectangle_at_umin():
    """Catalog 15 MVA / vk 12 % failed |Q|/Pn at U=0.95; wizard defaults must pass."""
    net, names = _wizard_default_50mw_net()
    params = _base_params(
        storageNames=names, storageSnMva=22, pocP_MW=50, pocQ_Mvar=16.434,
        powerFactor=0.95, pMaxDischarge_MW=15, pMaxCharge_MW=15)
    env = bess_prelim._run_pq_envelope(net, params, {})
    assert env and not env.get('error'), env
    pn, q_req, tol = 50.0, 16.43, 0.2
    curve = env['curves']['0.9500']
    p_arr = curve['p_mw']
    for p_want in list(p_arr) + [0.0, pn, -pn]:
        if abs(float(p_want)) > pn + 1.0:
            continue
        qmax = _interp_q_at_p(p_arr, curve['q_max_mvar'], p_want)
        qmin = _interp_q_at_p(p_arr, curve['q_min_mvar'], p_want)
        assert qmax is not None and qmin is not None, (p_want, qmax, qmin)
        assert qmax >= q_req - tol, (p_want, qmax, q_req)
        assert qmin <= -q_req + tol, (p_want, qmin, q_req)


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
