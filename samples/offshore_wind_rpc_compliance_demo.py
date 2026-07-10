"""
Offshore wind farm grid-code RPC demonstration (U-Q/Pmax + P-Q/Pmax).

Builds a simplified 450 MW plant + 400 kV PoC model and runs
reactive_power_capability() with Polish Type D requirements.

Run from appElectrisimBackend:
  python samples/offshore_wind_rpc_compliance_demo.py

Full Rev 4 1 GW model: open in Electrisim, use the same RPC dialog settings
documented in docs/offshore-wind-rpc-preflight.md and article Part 2.
"""
import json
import os
import sys

import pandapower as pp

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandapower_electrisim as pe  # noqa: E402

P_RATED_MW = 450.0


def build_simplified_offshore_net():
    """Simplified HVAC offshore wind farm: WTGs -> 275 kV cable -> 400 kV PoC."""
    net = pp.create_empty_network(f_hz=50, sn_mva=1000)
    b_poc = pp.create_bus(net, vn_kv=400, name='PoC_400kV')
    b_on = pp.create_bus(net, vn_kv=275, name='Onshore_275kV')
    b_off = pp.create_bus(net, vn_kv=66, name='Offshore_66kV')

    pp.create_ext_grid(net, bus=b_poc, vm_pu=1.0, name='External_Grid')
    pp.create_line_from_parameters(
        net, from_bus=b_on, to_bus=b_off, length_km=100,
        r_ohm_per_km=0.02, x_ohm_per_km=0.12, c_nf_per_km=250,
        max_i_ka=2.0, name='Export_275kV'
    )
    pp.create_transformer_from_parameters(
        net, hv_bus=b_poc, lv_bus=b_on, sn_mva=600,
        vn_hv_kv=400, vn_lv_kv=275, vkr_percent=0.5, vk_percent=14,
        pfe_kw=120, i0_percent=0.1, name='Onshore_400_275'
    )
    # VSR + fixed shunt at 275 kV (simplified fixed steps)
    pp.create_shunt(net, bus=b_on, q_mvar=-80, p_mw=0, name='VSR_275kV')
    pp.create_shunt(net, bus=b_poc, q_mvar=-25, p_mw=0, name='Shunt_400kV')

    # 30 x 15 MW turbines aggregated as one static generator with Type D Q envelope
    pp.create_sgen(
        net, bus=b_off, p_mw=P_RATED_MW, q_mvar=0, sn_mva=500,
        name='WTG_450MW', type='wye'
    )
    if 'max_q_mvar' in net.sgen.columns:
        net.sgen.at[0, 'max_q_mvar'] = P_RATED_MW * 0.4843
        net.sgen.at[0, 'min_q_mvar'] = -P_RATED_MW * 0.3287

    return net


def polish_ppm_fig2_pq_requirements():
    """NC RfG Fig. 2 — PPM P-Q/Pmax @ 400 kV (Type D connection)."""
    rows = [
        (0.0, 0.0, 0.0),
        (0.1, -0.35, 0.40),
        (0.5, -0.35, 0.40),
        (0.9, -0.35, 0.40),
        (1.0, -0.33, 0.33),
    ]
    return {
        'p_mw': [r[0] * P_RATED_MW for r in rows],
        'q_req_min_mvar': [r[1] * P_RATED_MW for r in rows],
        'q_req_max_mvar': [r[2] * P_RATED_MW for r in rows],
    }


def polish_ppm_uq_requirements():
    # NC RfG Fig. 1 @ 400 kV — polygon vertices projected to U slices
    rows = [
        (0.875, 0.165, 0.33),
        (0.900, 0.0, 0.33),
        (0.925, -0.165, 0.33),
        (0.950, -0.33, 0.33),
        (1.000, -0.33, 0.33),
        (1.050, -0.33, 0.33),
        (1.075, -0.33, -0.12),
        (1.100, -0.33, -0.24),
    ]
    return {
        'u_pu': [r[0] for r in rows],
        'q_req_min_mvar': [r[1] * P_RATED_MW for r in rows],
        'q_req_max_mvar': [r[2] * P_RATED_MW for r in rows],
    }


def polish_type_d_pq_requirements():
    return polish_ppm_fig2_pq_requirements()


def run_pq_study(net):
    pq_req = polish_type_d_pq_requirements()
    req_v1 = {'1.0000': pq_req}
    params = {
        'pcc_bus_name': 'PoC_400kV',
        'ext_grid_name': 'External_Grid',
        'generator_names': ['WTG_450MW'],
        'voltage_levels': [1.0],
        'p_min_mw': 0,
        'p_max_mw': P_RATED_MW,
        'p_steps': 5,
        'q_capability_mode': 'from_rating',
        'requirements': req_v1,
        'uq_requirements': polish_ppm_uq_requirements(),
        'grid_code_template_name': 'Polish PPM P-Q/Pmax Fig. 2 @ 400 kV',
        'uq_grid_code_template_name': 'Polish PPM U-Q/Pmax @ 400 kV',
    }
    return json.loads(pe.reactive_power_capability(net, params))


def run_uq_study(net):
    uq_req = polish_ppm_uq_requirements()
    params = {
        'pcc_bus_name': 'PoC_400kV',
        'ext_grid_name': 'External_Grid',
        'generator_names': ['WTG_450MW'],
        'voltage_levels': [0.875, 0.9, 0.925, 0.95, 1.0, 1.05, 1.075, 1.1],
        'p_min_mw': P_RATED_MW,
        'p_max_mw': P_RATED_MW,
        'p_steps': 0,
        'q_capability_mode': 'from_rating',
        'uq_requirements': uq_req,
        'uq_grid_code_template_name': 'Polish IRiESP Type D U-Q @ 400 kV',
    }
    return json.loads(pe.reactive_power_capability(net, params))


def print_uq_table(result):
    rpc = result.get('rpc_results', result)
    uq = rpc.get('uq_curve', {})
    req = rpc.get('uq_requirements', {})
    print('\n=== U-Q/Pmax @ P = 450 MW ===')
    print(f"U-Q compliance: {rpc.get('uq_compliance')}")
    print('U_pu\tQ_max\tQ_min\tReq_Q_max\tReq_Q_min')
    ru = req.get('u_pu', [])
    rmax = req.get('q_req_max_mvar', [])
    rmin = req.get('q_req_min_mvar', [])
    for i, u in enumerate(uq.get('u_pu', [])):
        qx = uq['q_max_mvar'][i]
        qn = uq['q_min_mvar'][i]
        # interpolate req at u
        import numpy as np
        req_max = float(np.interp(u, ru, rmax)) if ru else ''
        req_min = float(np.interp(u, ru, rmin)) if ru else ''
        print(f"{u:.3f}\t{qx}\t{qn}\t{req_max:.1f}\t{req_min:.1f}")


def print_pq_table(result):
    rpc = result.get('rpc_results', result)
    curve = rpc.get('curves', {}).get('1.0000', {})
    req = rpc.get('requirements', {}).get('1.0000', {})
    print('\n=== P-Q/Pmax @ U = 1.0 pu ===')
    print(f"P-Q compliance @ 1.0 pu: {rpc.get('compliance', {}).get('1.0000')}")
    print('P_MW\tQ_max\tQ_min')
    for i, p in enumerate(curve.get('p_mw', [])):
        print(f"{p}\t{curve['q_max_mvar'][i]}\t{curve['q_min_mvar'][i]}")


def main():
    net = build_simplified_offshore_net()
    print('Running P-Q/Pmax study (U=1.0 pu)...')
    pq_result = run_pq_study(net)
    print_pq_table(pq_result)

    net2 = build_simplified_offshore_net()
    print('\nRunning U-Q/Pmax study (P=450 MW)...')
    uq_result = run_uq_study(net2)
    print_uq_table(uq_result)

    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, 'offshore_wind_rpc_results_450mw.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({'pq_study': pq_result, 'uq_study': uq_result}, f, indent=2)
    print(f'\nSaved results to {out_path}')


if __name__ == '__main__':
    main()
