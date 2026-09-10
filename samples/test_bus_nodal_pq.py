"""Regression: busbar result P must not double-count local BESS/sgen injection.

Junction buses (transformer/impedance + another feeder) used to add
``res_bus`` injection to the same power already leaving on branches, so two
1.75 MW BESS units displayed as -7 MW. The solved load flow was already
correct (~3.5 MW at the slack).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandapower as pp
from pandapower_electrisim import (
    _electrisim_bus_nodal_p_q_sum,
    _electrisim_bus_branch_terminal_count,
)


def _lv_net(p_storage=-1.75, extra_feeder=False, aux_switches=False, two_upstreams=False):
    net = pp.create_empty_network()
    b_grid = pp.create_bus(net, vn_kv=20.0, name='grid', id='grid')
    b_lv = pp.create_bus(net, vn_kv=0.69, name='lv', id='lv')
    pp.create_ext_grid(net, bus=b_grid, vm_pu=1.0, name='EG')
    pp.create_impedance(
        net, from_bus=b_grid, to_bus=b_lv, rft_pu=0.0001, xft_pu=0.001,
        sn_mva=10.0, name='upstream',
    )
    if two_upstreams:
        pp.create_impedance(
            net, from_bus=b_grid, to_bus=b_lv, rft_pu=0.0001, xft_pu=0.001,
            sn_mva=10.0, name='upstream2',
        )
    if extra_feeder:
        b_load = pp.create_bus(net, vn_kv=0.69, name='loadbus', id='loadbus')
        pp.create_line_from_parameters(
            net, from_bus=b_lv, to_bus=b_load, length_km=0.05,
            r_ohm_per_km=0.1, x_ohm_per_km=0.1, c_nf_per_km=0,
            max_i_ka=1.0, name='feeder',
        )
        pp.create_load(net, bus=b_load, p_mw=0.1, q_mvar=0.0, name='tinyload')

    def add_storage(name, sid):
        bus = b_lv
        if aux_switches:
            aux = pp.create_bus(net, vn_kv=0.69, name=f'_electrisim_aux_{sid}', id=f'aux_{sid}')
            pp.create_switch(net, bus=b_lv, element=aux, et='b', closed=True, z_ohm=0, name=f'sw_{sid}')
            bus = aux
        pp.create_storage(net, bus=bus, p_mw=p_storage, max_e_mwh=10, name=name, id=sid, sn_mva=2.0)

    add_storage('BESS1', 'bess1')
    add_storage('BESS2', 'bess2')
    pp.runpp(net)
    return net, b_lv


def _assert_close(actual, expected, tol=1e-3, msg=''):
    if abs(actual - expected) > tol:
        raise AssertionError(f'{msg}: got {actual:.6f}, expected {expected:.6f}')


def test_junction_two_bess_discharging_not_doubled():
    """User report: two 1.75 MW BESS on 0.69 kV bus with a second branch → −7 MW."""
    net, b_lv = _lv_net(p_storage=-1.75, extra_feeder=True)
    assert _electrisim_bus_branch_terminal_count(net, b_lv) >= 2
    p_nodal, _ = _electrisim_bus_nodal_p_q_sum(net, b_lv)
    _assert_close(p_nodal, -3.5, msg='junction bus P (2 BESS discharging)')
    p_slack = float(net.res_ext_grid.p_mw.iloc[0])
    # Grid receives BESS minus feeder load (~3.4 MW), not 7 MW.
    if not (p_slack < -3.0 and p_slack > -3.6):
        raise AssertionError(f'slack P looks like duplicated injection: {p_slack}')


def test_junction_two_bess_behind_switches():
    net, b_lv = _lv_net(p_storage=-1.75, extra_feeder=True, aux_switches=True)
    p_nodal, _ = _electrisim_bus_nodal_p_q_sum(net, b_lv)
    _assert_close(p_nodal, -3.5, msg='junction + aux-switch BESS P')


def test_two_upstreams_two_bess():
    net, b_lv = _lv_net(p_storage=-1.75, two_upstreams=True)
    p_nodal, _ = _electrisim_bus_nodal_p_q_sum(net, b_lv)
    _assert_close(p_nodal, -3.5, msg='two upstream branches + 2 BESS')


def test_radial_two_bess_still_correct():
    net, b_lv = _lv_net(p_storage=-1.75)
    assert _electrisim_bus_branch_terminal_count(net, b_lv) == 1
    p_nodal, _ = _electrisim_bus_nodal_p_q_sum(net, b_lv)
    _assert_close(p_nodal, -3.5, msg='radial bus P (2 BESS discharging)')


def test_charging_sign():
    net, b_lv = _lv_net(p_storage=1.75, extra_feeder=True)
    p_nodal, _ = _electrisim_bus_nodal_p_q_sum(net, b_lv)
    _assert_close(p_nodal, 3.5, msg='junction bus P (2 BESS charging)')


def test_passthrough_shows_through_power():
    net = pp.create_empty_network()
    b1 = pp.create_bus(net, vn_kv=20.0, name='a', id='a')
    b2 = pp.create_bus(net, vn_kv=20.0, name='mid', id='mid')
    b3 = pp.create_bus(net, vn_kv=20.0, name='c', id='c')
    pp.create_ext_grid(net, bus=b1, vm_pu=1.0)
    pp.create_line_from_parameters(
        net, from_bus=b1, to_bus=b2, length_km=1.0,
        r_ohm_per_km=0.05, x_ohm_per_km=0.1, c_nf_per_km=0, max_i_ka=1.0,
    )
    pp.create_line_from_parameters(
        net, from_bus=b2, to_bus=b3, length_km=1.0,
        r_ohm_per_km=0.05, x_ohm_per_km=0.1, c_nf_per_km=0, max_i_ka=1.0,
    )
    pp.create_load(net, bus=b3, p_mw=5.0, q_mvar=0.0)
    pp.runpp(net)
    p_mid, _ = _electrisim_bus_nodal_p_q_sum(net, b2)
    if abs(p_mid) < 4.0:
        raise AssertionError(f'pass-through mid bus hid through-power: {p_mid}')


def test_transit_hub_with_small_shunt_not_doubled():
    """Through-power must stay visible; shunt P must not be added on top of it."""
    net = pp.create_empty_network()
    b1 = pp.create_bus(net, vn_kv=20.0, name='a', id='a')
    b2 = pp.create_bus(net, vn_kv=20.0, name='mid', id='mid')
    b3 = pp.create_bus(net, vn_kv=20.0, name='c', id='c')
    pp.create_ext_grid(net, bus=b1, vm_pu=1.0)
    pp.create_line_from_parameters(
        net, from_bus=b1, to_bus=b2, length_km=1.0,
        r_ohm_per_km=0.05, x_ohm_per_km=0.1, c_nf_per_km=0, max_i_ka=1.0,
    )
    pp.create_line_from_parameters(
        net, from_bus=b2, to_bus=b3, length_km=1.0,
        r_ohm_per_km=0.05, x_ohm_per_km=0.1, c_nf_per_km=0, max_i_ka=1.0,
    )
    pp.create_load(net, bus=b3, p_mw=10.0, q_mvar=0.0)
    pp.create_shunt(net, bus=b2, q_mvar=1.0, p_mw=0.05)
    pp.runpp(net)
    p_mid, _ = _electrisim_bus_nodal_p_q_sum(net, b2)
    if abs(p_mid) < 8.0:
        raise AssertionError(f'transit hub hid through-power behind shunt: {p_mid}')
    if abs(p_mid) > 15.0:
        raise AssertionError(f'transit hub double-counted shunt + through-power: {p_mid}')


if __name__ == '__main__':
    tests = [
        test_junction_two_bess_discharging_not_doubled,
        test_junction_two_bess_behind_switches,
        test_two_upstreams_two_bess,
        test_radial_two_bess_still_correct,
        test_charging_sign,
        test_passthrough_shows_through_power,
        test_transit_hub_with_small_shunt_not_doubled,
    ]
    for fn in tests:
        fn()
        print(f'OK {fn.__name__}')
    print('all passed')
