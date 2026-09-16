"""Grid Code Compliance (V-Q): U-Q/Pmax reshaping and compliance."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandapower as pp
import grid_code_vq_electrisim as gc_vq
import pandapower_electrisim as pp_el


def _minimal_export_net(p_mw=5.0, sn_mva=6.0):
    net = pp.create_empty_network(f_hz=50.0)
    b_pcc = pp.create_bus(net, vn_kv=110.0, name='pcc')
    b_gen = pp.create_bus(net, vn_kv=30.0, name='gen')
    pp.create_ext_grid(net, bus=b_pcc, vm_pu=1.0, name='ext_grid')
    pp.create_line_from_parameters(
        net, from_bus=b_gen, to_bus=b_pcc, length_km=1.0,
        r_ohm_per_km=0.1, x_ohm_per_km=0.2, c_nf_per_km=0, max_i_ka=1.0, name='export',
    )
    pp.create_sgen(net, bus=b_gen, p_mw=p_mw, q_mvar=0.0, sn_mva=sn_mva, name='wtg1')
    return net


def _base_params():
    return {
        'pcc_bus_name': 'pcc',
        'ext_grid_name': 'ext_grid',
        'generator_names': ['wtg1'],
        'voltage_levels': [0.95, 1.0, 1.05],
        'pn_mw': 0,
        'p_max_pct': 100,
        'q_step_pct': 1.0,
        'q_capability_mode': 'from_rating',
        'i_park_ctrl': False,
        'limit_overloads': False,
    }


def test_vq_returns_uq_curve_and_compliance():
    net = _minimal_export_net()
    pn = 5.0
    uq_req = {
        'u_pu': [0.9, 1.0, 1.1],
        'q_req_max_mvar': [0.33 * pn] * 3,
        'q_req_min_mvar': [-0.33 * pn] * 3,
    }
    params = {**_base_params(), 'uq_requirements': uq_req}
    raw = gc_vq.grid_code_vq_capability(net, params, {})
    outer = json.loads(raw)
    assert 'error' not in outer, outer
    res = outer['grid_code_vq_results']
    uq = res['uq_curve']
    assert len(uq['u_pu']) >= 3, uq
    assert len(uq['q_max_mvar']) == len(uq['u_pu'])
    assert res['uq_compliance'] in (True, False, None)


def test_vq_compliance_false_when_capability_too_small():
    net = _minimal_export_net(p_mw=5.0, sn_mva=5.5)
    pn = 5.0
    uq_req = {
        'u_pu': [1.0],
        'q_req_max_mvar': [10.0 * pn],
        'q_req_min_mvar': [-10.0 * pn],
    }
    params = {**_base_params(), 'voltage_levels': [1.0], 'uq_requirements': uq_req}
    raw = gc_vq.grid_code_vq_capability(net, params, {})
    res = json.loads(raw)['grid_code_vq_results']
    assert res['uq_compliance'] is False, res


def test_vq_build_curve_uses_pq_engine():
    """Capability Q values come from the P-Q search at fixed P, not an empty stub."""
    net = _minimal_export_net()
    params = _base_params()
    raw = gc_vq.grid_code_vq_capability(net, params, {})
    res = json.loads(raw)['grid_code_vq_results']
    qmax = res['uq_curve']['q_max_mvar']
    assert any(q is not None and abs(q) > 0.01 for q in qmax), qmax


if __name__ == '__main__':
    test_vq_returns_uq_curve_and_compliance()
    test_vq_compliance_false_when_capability_too_small()
    test_vq_build_curve_uses_pq_engine()
    print('test_grid_code_vq: OK')
