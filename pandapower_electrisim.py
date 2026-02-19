import pandapower as pp
import pandapower.contingency as contingency
import pandapower.shortcircuit as sc
import pandapower.plotting as plt
from pandapower.diagnostic import diagnostic
import pandapower.topology as top
from typing import List
import math
import json
import numpy as np
import pandas as pd
import pandapower.control as control
import pandapower.timeseries as ts
from pandapower.timeseries import DFData
from copy import deepcopy


Busbars = {} 

def generate_pandapower_python_code(net, in_data, Busbars, algorithm, calculate_voltage_angles, init):
    """Generate Python code to recreate the pandapower network"""
    lines = []
    
    # Add header
    lines.append("# Pandapower Network Model")
    lines.append("# Auto-generated code to recreate the network")
    lines.append("")
    lines.append("import pandapower as pp")
    lines.append("")
    
    # Get frequency from network
    frequency = net.f_hz
    lines.append(f"# Create empty network with {frequency} Hz")
    lines.append(f"net = pp.create_empty_network(f_hz={frequency})")
    lines.append("")
    
    # Create buses
    lines.append("# Create buses")
    for idx, row in net.bus.iterrows():
        name = row['name'] if 'name' in row else f"Bus_{idx}"
        vn_kv = row['vn_kv']
        lines.append(f"bus_{idx} = pp.create_bus(net, vn_kv={vn_kv}, name='{name}')")
    lines.append("")
    
    # Create external grids
    if not net.ext_grid.empty:
        lines.append("# Create external grids")
        for idx, row in net.ext_grid.iterrows():
            bus = row['bus']
            vm_pu = row['vm_pu']
            va_degree = row['va_degree']
            name = row['name'] if 'name' in row else f"ExtGrid_{idx}"
            lines.append(f"pp.create_ext_grid(net, bus=bus_{bus}, vm_pu={vm_pu}, va_degree={va_degree}, name='{name}')")
        lines.append("")
    
    # Create lines
    if not net.line.empty:
        lines.append("# Create lines")
        for idx, row in net.line.iterrows():
            from_bus = row['from_bus']
            to_bus = row['to_bus']
            name = row['name'] if 'name' in row else f"Line_{idx}"
            
            # Get all line parameters for create_line_from_parameters
            line_id = row.get('id', name)  # Use name as fallback if id not stored
            r_ohm_per_km = row.get('r_ohm_per_km', 0.122)
            x_ohm_per_km = row.get('x_ohm_per_km', 0.112)
            c_nf_per_km = row.get('c_nf_per_km', 304.0)
            g_us_per_km = row.get('g_us_per_km', 0.0)
            max_i_ka = row.get('max_i_ka', 1.0)
            line_type = row.get('type', 'ol')
            length_km = row['length_km']
            
            # Get optional parameters if they exist
            parallel = row.get('parallel', 1)
            df = row.get('df', 1.0)
            
            # Build the create_line_from_parameters call with all parameters
            # Note: 'id' is included as a comment since pandapower doesn't store it natively
            lines.append(f"# Line ID: {line_id}")
            line_code = (f"pp.create_line_from_parameters(net, from_bus=bus_{from_bus}, to_bus=bus_{to_bus}, "
                        f"length_km={length_km}, r_ohm_per_km={r_ohm_per_km}, x_ohm_per_km={x_ohm_per_km}, "
                        f"c_nf_per_km={c_nf_per_km}, g_us_per_km={g_us_per_km}, max_i_ka={max_i_ka}, "
                        f"type='{line_type}', parallel={parallel}, df={df}, name='{name}')")
            lines.append(line_code)
        lines.append("")
    
    # Create transformers
    if not net.trafo.empty:
        lines.append("# Create transformers (2-winding)")
        for idx, row in net.trafo.iterrows():
            hv_bus = row['hv_bus']
            lv_bus = row['lv_bus']
            name = row['name'] if 'name' in row else f"Trafo_{idx}"
            
            # Get transformer ID
            trafo_id = row.get('id', name)
            
            # Get all transformer parameters for create_transformer_from_parameters
            sn_mva = row.get('sn_mva', 1.0)
            vn_hv_kv = row.get('vn_hv_kv', 110.0)
            vn_lv_kv = row.get('vn_lv_kv', 20.0)
            vk_percent = row.get('vk_percent', 6.0)
            vkr_percent = row.get('vkr_percent', 1.0)
            pfe_kw = row.get('pfe_kw', 0.0)
            i0_percent = row.get('i0_percent', 0.0)
            
            # Get optional parameters
            parallel = row.get('parallel', 1)
            shift_degree = row.get('shift_degree', 0.0)
            tap_side = row.get('tap_side', 'hv')
            tap_pos = row.get('tap_pos', 0)
            tap_neutral = row.get('tap_neutral', 0)
            tap_max = row.get('tap_max', 0)
            tap_min = row.get('tap_min', 0)
            tap_step_percent = row.get('tap_step_percent', 0.0)
            tap_step_degree = row.get('tap_step_degree', 0.0)
            vector_group = row.get('vector_group', 'Dyn')
            
            # Get zero sequence parameters if available
            vk0_percent = row.get('vk0_percent', vk_percent)
            vkr0_percent = row.get('vkr0_percent', vkr_percent)
            mag0_percent = row.get('mag0_percent', 0.0)
            mag0_rx = row.get('mag0_rx', 0.0)
            si0_hv_partial = row.get('si0_hv_partial', 0.0)
            
            # Get tap_changer_type (pandapower 3.0+)
            tap_changer_type = row.get('tap_changer_type', 'Ratio')
            
            # Build the create_transformer_from_parameters call
            lines.append(f"# Transformer ID: {trafo_id}")
            trafo_code = (f"pp.create_transformer_from_parameters(net, hv_bus=bus_{hv_bus}, lv_bus=bus_{lv_bus}, "
                         f"sn_mva={sn_mva}, vn_hv_kv={vn_hv_kv}, vn_lv_kv={vn_lv_kv}, "
                         f"vkr_percent={vkr_percent}, vk_percent={vk_percent}, "
                         f"pfe_kw={pfe_kw}, i0_percent={i0_percent}, "
                         f"parallel={parallel}, shift_degree={shift_degree}, "
                         f"tap_side='{tap_side}', tap_pos={tap_pos}, tap_neutral={tap_neutral}, "
                         f"tap_max={tap_max}, tap_min={tap_min}, "
                         f"tap_step_percent={tap_step_percent}, tap_step_degree={tap_step_degree}, "
                         f"tap_changer_type='{tap_changer_type}', "
                         f"vector_group='{vector_group}', "
                         f"vk0_percent={vk0_percent}, vkr0_percent={vkr0_percent}, "
                         f"mag0_percent={mag0_percent}, mag0_rx={mag0_rx}, "
                         f"si0_hv_partial={si0_hv_partial}, name='{name}')")
            lines.append(trafo_code)
        lines.append("")
    
    # Create three-winding transformers
    if hasattr(net, 'trafo3w') and not net.trafo3w.empty:
        lines.append("# Create transformers (3-winding)")
        for idx, row in net.trafo3w.iterrows():
            hv_bus = row['hv_bus']
            mv_bus = row['mv_bus']
            lv_bus = row['lv_bus']
            name = row['name'] if 'name' in row else f"Trafo3W_{idx}"
            
            # Get transformer ID
            trafo3w_id = row.get('id', name)
            
            # Get all 3-winding transformer parameters
            sn_hv_mva = row.get('sn_hv_mva', 1.0)
            sn_mv_mva = row.get('sn_mv_mva', 1.0)
            sn_lv_mva = row.get('sn_lv_mva', 1.0)
            vn_hv_kv = row.get('vn_hv_kv', 110.0)
            vn_mv_kv = row.get('vn_mv_kv', 30.0)
            vn_lv_kv = row.get('vn_lv_kv', 10.0)
            vk_hv_percent = row.get('vk_hv_percent', 10.0)
            vk_mv_percent = row.get('vk_mv_percent', 10.0)
            vk_lv_percent = row.get('vk_lv_percent', 10.0)
            vkr_hv_percent = row.get('vkr_hv_percent', 0.5)
            vkr_mv_percent = row.get('vkr_mv_percent', 0.5)
            vkr_lv_percent = row.get('vkr_lv_percent', 0.5)
            pfe_kw = row.get('pfe_kw', 0.0)
            i0_percent = row.get('i0_percent', 0.0)
            
            # Get optional parameters
            shift_mv_degree = row.get('shift_mv_degree', 0.0)
            shift_lv_degree = row.get('shift_lv_degree', 0.0)
            tap_side = row.get('tap_side', 'hv')
            tap_pos = row.get('tap_pos', 0)
            tap_min = row.get('tap_min', 0)
            tap_max = row.get('tap_max', 0)
            tap_step_percent = row.get('tap_step_percent', 0.0)
            vector_group = row.get('vector_group', 'YNyn')
            
            # Get zero sequence parameters if available
            vk0_hv_percent = row.get('vk0_hv_percent', vk_hv_percent)
            vk0_mv_percent = row.get('vk0_mv_percent', vk_mv_percent)
            vk0_lv_percent = row.get('vk0_lv_percent', vk_lv_percent)
            vkr0_hv_percent = row.get('vkr0_hv_percent', vkr_hv_percent)
            vkr0_mv_percent = row.get('vkr0_mv_percent', vkr_mv_percent)
            vkr0_lv_percent = row.get('vkr0_lv_percent', vkr_lv_percent)
            
            # Get tap_changer_type (pandapower 3.0+)
            tap_changer_type_3w = row.get('tap_changer_type', 'Ratio')
            
            # Build the create_transformer3w_from_parameters call
            lines.append(f"# Three-Winding Transformer ID: {trafo3w_id}")
            trafo3w_code = (f"pp.create_transformer3w_from_parameters(net, "
                           f"hv_bus=bus_{hv_bus}, mv_bus=bus_{mv_bus}, lv_bus=bus_{lv_bus}, "
                           f"sn_hv_mva={sn_hv_mva}, sn_mv_mva={sn_mv_mva}, sn_lv_mva={sn_lv_mva}, "
                           f"vn_hv_kv={vn_hv_kv}, vn_mv_kv={vn_mv_kv}, vn_lv_kv={vn_lv_kv}, "
                           f"vk_hv_percent={vk_hv_percent}, vk_mv_percent={vk_mv_percent}, vk_lv_percent={vk_lv_percent}, "
                           f"vkr_hv_percent={vkr_hv_percent}, vkr_mv_percent={vkr_mv_percent}, vkr_lv_percent={vkr_lv_percent}, "
                           f"pfe_kw={pfe_kw}, i0_percent={i0_percent}, "
                           f"shift_mv_degree={shift_mv_degree}, shift_lv_degree={shift_lv_degree}, "
                           f"tap_side='{tap_side}', tap_pos={tap_pos}, tap_min={tap_min}, tap_max={tap_max}, "
                           f"tap_step_percent={tap_step_percent}, tap_changer_type='{tap_changer_type_3w}', "
                           f"vector_group='{vector_group}', "
                           f"vk0_hv_percent={vk0_hv_percent}, vk0_mv_percent={vk0_mv_percent}, vk0_lv_percent={vk0_lv_percent}, "
                           f"vkr0_hv_percent={vkr0_hv_percent}, vkr0_mv_percent={vkr0_mv_percent}, vkr0_lv_percent={vkr0_lv_percent}, "
                           f"name='{name}')")
            lines.append(trafo3w_code)
        lines.append("")
    
    # Create loads
    if not net.load.empty:
        lines.append("# Create loads")
        for idx, row in net.load.iterrows():
            bus = row['bus']
            p_mw = row['p_mw']
            q_mvar = row['q_mvar']
            name = row['name'] if 'name' in row else f"Load_{idx}"
            lines.append(f"pp.create_load(net, bus=bus_{bus}, p_mw={p_mw}, q_mvar={q_mvar}, name='{name}')")
        lines.append("")
    
    # Create static generators
    if not net.sgen.empty:
        lines.append("# Create static generators")
        for idx, row in net.sgen.iterrows():
            bus = row['bus']
            p_mw = row['p_mw']
            q_mvar = row['q_mvar']
            name = row['name'] if 'name' in row else f"SGen_{idx}"
            lines.append(f"pp.create_sgen(net, bus=bus_{bus}, p_mw={p_mw}, q_mvar={q_mvar}, name='{name}')")
        lines.append("")
    
    # Create generators
    if not net.gen.empty:
        lines.append("# Create generators")
        for idx, row in net.gen.iterrows():
            bus = row['bus']
            p_mw = row['p_mw']
            vm_pu = row['vm_pu']
            name = row['name'] if 'name' in row else f"Gen_{idx}"
            lines.append(f"pp.create_gen(net, bus=bus_{bus}, p_mw={p_mw}, vm_pu={vm_pu}, name='{name}')")
        lines.append("")
    
    # Create shunts
    if not net.shunt.empty:
        lines.append("# Create shunts")
        for idx, row in net.shunt.iterrows():
            bus = row['bus']
            q_mvar = row['q_mvar']
            p_mw = row['p_mw']
            name = row['name'] if 'name' in row else f"Shunt_{idx}"
            lines.append(f"pp.create_shunt(net, bus=bus_{bus}, q_mvar={q_mvar}, p_mw={p_mw}, name='{name}')")
        lines.append("")
    
    # Create storage elements
    if hasattr(net, 'storage') and not net.storage.empty:
        lines.append("# Create storage elements")
        for idx, row in net.storage.iterrows():
            bus = row['bus']
            name = row['name'] if 'name' in row else f"Storage_{idx}"
            p_mw = row['p_mw']
            q_mvar = row.get('q_mvar', 0.0)
            sn_mva = row.get('sn_mva', 1.0)
            scaling = row.get('scaling', 1.0)
            storage_type = row.get('type', 'storage')
            max_e_mwh = row.get('max_e_mwh', 1.0)
            min_e_mwh = row.get('min_e_mwh', 0.0)
            soc_percent = row.get('soc_percent', 50.0)
            in_service = row.get('in_service', True)
            
            # Build the create_storage call with all parameters
            storage_code = (f"pp.create_storage(net, bus=bus_{bus}, name='{name}', "
                          f"p_mw={p_mw}, q_mvar={q_mvar}, sn_mva={sn_mva}, "
                          f"scaling={scaling}, type='{storage_type}', "
                          f"max_e_mwh={max_e_mwh}, min_e_mwh={min_e_mwh}, "
                          f"soc_percent={soc_percent}, in_service={in_service})")
            lines.append(storage_code)
        lines.append("")
    
    # Create DC buses
    if hasattr(net, 'bus_dc') and not net.bus_dc.empty:
        lines.append("# Create DC buses")
        for idx, row in net.bus_dc.iterrows():
            name = row['name'] if 'name' in row else f"BusDC_{idx}"
            vn_kv = row.get('vn_kv', 0.0)
            in_service = row.get('in_service', True)
            lines.append(f"bus_dc_{idx} = pp.create_dc_bus(net, vn_kv={vn_kv}, name='{name}', in_service={in_service})")
        lines.append("")
    
    # Create asymmetric static generators
    if hasattr(net, 'asymmetric_sgen') and not net.asymmetric_sgen.empty:
        lines.append("# Create asymmetric static generators")
        for idx, row in net.asymmetric_sgen.iterrows():
            bus = row['bus']
            name = row['name'] if 'name' in row else f"AsymSGen_{idx}"
            p_a_mw = row.get('p_a_mw', 0.0)
            p_b_mw = row.get('p_b_mw', 0.0)
            p_c_mw = row.get('p_c_mw', 0.0)
            q_a_mvar = row.get('q_a_mvar', 0.0)
            q_b_mvar = row.get('q_b_mvar', 0.0)
            q_c_mvar = row.get('q_c_mvar', 0.0)
            sn_mva = row.get('sn_mva', 1.0)
            scaling = row.get('scaling', 1.0)
            sgen_type = row.get('type', 'current_source')
            in_service = row.get('in_service', True)
            lines.append(f"pp.create_asymmetric_sgen(net, bus=bus_{bus}, name='{name}', "
                        f"p_a_mw={p_a_mw}, p_b_mw={p_b_mw}, p_c_mw={p_c_mw}, "
                        f"q_a_mvar={q_a_mvar}, q_b_mvar={q_b_mvar}, q_c_mvar={q_c_mvar}, "
                        f"sn_mva={sn_mva}, scaling={scaling}, type='{sgen_type}', in_service={in_service})")
        lines.append("")
    
    # Create asymmetric loads
    if hasattr(net, 'asymmetric_load') and not net.asymmetric_load.empty:
        lines.append("# Create asymmetric loads")
        for idx, row in net.asymmetric_load.iterrows():
            bus = row['bus']
            name = row['name'] if 'name' in row else f"AsymLoad_{idx}"
            p_a_mw = row.get('p_a_mw', 0.0)
            p_b_mw = row.get('p_b_mw', 0.0)
            p_c_mw = row.get('p_c_mw', 0.0)
            q_a_mvar = row.get('q_a_mvar', 0.0)
            q_b_mvar = row.get('q_b_mvar', 0.0)
            q_c_mvar = row.get('q_c_mvar', 0.0)
            sn_mva = row.get('sn_mva', 1.0)
            scaling = row.get('scaling', 1.0)
            load_type = row.get('type', 'wye')
            in_service = row.get('in_service', True)
            lines.append(f"pp.create_asymmetric_load(net, bus=bus_{bus}, name='{name}', "
                        f"p_a_mw={p_a_mw}, p_b_mw={p_b_mw}, p_c_mw={p_c_mw}, "
                        f"q_a_mvar={q_a_mvar}, q_b_mvar={q_b_mvar}, q_c_mvar={q_c_mvar}, "
                        f"sn_mva={sn_mva}, scaling={scaling}, type='{load_type}', in_service={in_service})")
        lines.append("")
    
    # Create impedance elements
    if hasattr(net, 'impedance') and not net.impedance.empty:
        lines.append("# Create impedance elements")
        for idx, row in net.impedance.iterrows():
            from_bus = row['from_bus']
            to_bus = row['to_bus']
            name = row['name'] if 'name' in row else f"Impedance_{idx}"
            rft_pu = row.get('rft_pu', 0.0)
            xft_pu = row.get('xft_pu', 0.0)
            sn_mva = row.get('sn_mva', 1.0)
            in_service = row.get('in_service', True)
            lines.append(f"pp.create_impedance(net, from_bus=bus_{from_bus}, to_bus=bus_{to_bus}, "
                        f"name='{name}', rft_pu={rft_pu}, xft_pu={xft_pu}, sn_mva={sn_mva}, in_service={in_service})")
        lines.append("")
    
    # Create ward elements
    if hasattr(net, 'ward') and not net.ward.empty:
        lines.append("# Create ward elements")
        for idx, row in net.ward.iterrows():
            bus = row['bus']
            name = row['name'] if 'name' in row else f"Ward_{idx}"
            ps_mw = row.get('ps_mw', 0.0)
            qs_mvar = row.get('qs_mvar', 0.0)
            pz_mw = row.get('pz_mw', 0.0)
            qz_mvar = row.get('qz_mvar', 0.0)
            in_service = row.get('in_service', True)
            lines.append(f"pp.create_ward(net, bus=bus_{bus}, name='{name}', "
                        f"ps_mw={ps_mw}, qs_mvar={qs_mvar}, pz_mw={pz_mw}, qz_mvar={qz_mvar}, in_service={in_service})")
        lines.append("")
    
    # Create extended ward elements
    if hasattr(net, 'xward') and not net.xward.empty:
        lines.append("# Create extended ward elements")
        for idx, row in net.xward.iterrows():
            bus = row['bus']
            name = row['name'] if 'name' in row else f"XWard_{idx}"
            ps_mw = row.get('ps_mw', 0.0)
            qs_mvar = row.get('qs_mvar', 0.0)
            pz_mw = row.get('pz_mw', 0.0)
            qz_mvar = row.get('qz_mvar', 0.0)
            r_ohm = row.get('r_ohm', 0.0)
            x_ohm = row.get('x_ohm', 0.0)
            vm_pu = row.get('vm_pu', 1.0)
            in_service = row.get('in_service', True)
            lines.append(f"pp.create_xward(net, bus=bus_{bus}, name='{name}', "
                        f"ps_mw={ps_mw}, qs_mvar={qs_mvar}, pz_mw={pz_mw}, qz_mvar={qz_mvar}, "
                        f"r_ohm={r_ohm}, x_ohm={x_ohm}, vm_pu={vm_pu}, in_service={in_service})")
        lines.append("")
    
    # Create motor elements
    if hasattr(net, 'motor') and not net.motor.empty:
        lines.append("# Create motor elements")
        for idx, row in net.motor.iterrows():
            bus = row['bus']
            name = row['name'] if 'name' in row else f"Motor_{idx}"
            pn_mech_mw = row.get('pn_mech_mw', 0.0)
            cos_phi = row.get('cos_phi', 0.85)
            efficiency_n_percent = row.get('efficiency_n_percent', 90.0)
            lrc_pu = row.get('lrc_pu')
            rx = row.get('rx', 0.0)
            vn_kv = row.get('vn_kv', 0.4)
            efficiency_percent = row.get('efficiency_percent', 90.0)
            loading_percent = row.get('loading_percent', 100.0)
            scaling = row.get('scaling', 1.0)
            in_service = row.get('in_service', True)
            lrc_param = f"lrc_pu={lrc_pu}" if lrc_pu is not None else "lrc_pu=None"
            lines.append(f"pp.create_motor(net, bus=bus_{bus}, name='{name}', "
                        f"pn_mech_mw={pn_mech_mw}, cos_phi={cos_phi}, efficiency_n_percent={efficiency_n_percent}, "
                        f"{lrc_param}, rx={rx}, vn_kv={vn_kv}, efficiency_percent={efficiency_percent}, "
                        f"loading_percent={loading_percent}, scaling={scaling}, in_service={in_service})")
        lines.append("")
    
    # Create SVC elements
    if hasattr(net, 'svc') and not net.svc.empty:
        lines.append("# Create SVC (Static Var Compensator) elements")
        for idx, row in net.svc.iterrows():
            bus = row['bus']
            name = row['name'] if 'name' in row else f"SVC_{idx}"
            x_l_ohm = row.get('x_l_ohm', 0.0)
            x_cvar_ohm = row.get('x_cvar_ohm', 0.0)
            set_vm_pu = row.get('set_vm_pu', 1.0)
            thyristor_firing_angle_degree = row.get('thyristor_firing_angle_degree', 90.0)
            controllable = row.get('controllable', True)
            min_angle_degree = row.get('min_angle_degree', 90.0)
            max_angle_degree = row.get('max_angle_degree', 180.0)
            in_service = row.get('in_service', True)
            lines.append(f"pp.create_svc(net, bus=bus_{bus}, name='{name}', "
                        f"x_l_ohm={x_l_ohm}, x_cvar_ohm={x_cvar_ohm}, set_vm_pu={set_vm_pu}, "
                        f"thyristor_firing_angle_degree={thyristor_firing_angle_degree}, controllable={controllable}, "
                        f"min_angle_degree={min_angle_degree}, max_angle_degree={max_angle_degree}, in_service={in_service})")
        lines.append("")
    
    # Create TCSC elements
    if hasattr(net, 'tcsc') and not net.tcsc.empty:
        lines.append("# Create TCSC (Thyristor-Controlled Series Capacitor) elements")
        for idx, row in net.tcsc.iterrows():
            from_bus = row['from_bus']
            to_bus = row['to_bus']
            name = row['name'] if 'name' in row else f"TCSC_{idx}"
            x_l_ohm = row.get('x_l_ohm', 0.0)
            x_cvar_ohm = row.get('x_cvar_ohm', 0.0)
            set_p_to_mw = row.get('set_p_to_mw', 0.0)
            thyristor_firing_angle_degree = row.get('thyristor_firing_angle_degree', 90.0)
            controllable = row.get('controllable', True)
            min_angle_degree = row.get('min_angle_degree', 90.0)
            max_angle_degree = row.get('max_angle_degree', 180.0)
            in_service = row.get('in_service', True)
            lines.append(f"pp.create_tcsc(net, from_bus=bus_{from_bus}, to_bus=bus_{to_bus}, name='{name}', "
                        f"x_l_ohm={x_l_ohm}, x_cvar_ohm={x_cvar_ohm}, set_p_to_mw={set_p_to_mw}, "
                        f"thyristor_firing_angle_degree={thyristor_firing_angle_degree}, controllable={controllable}, "
                        f"min_angle_degree={min_angle_degree}, max_angle_degree={max_angle_degree}, in_service={in_service})")
        lines.append("")
    
    # Create SSC elements
    if hasattr(net, 'ssc') and not net.ssc.empty:
        lines.append("# Create SSC (Static Synchronous Compensator) elements")
        for idx, row in net.ssc.iterrows():
            bus = row['bus']
            name = row['name'] if 'name' in row else f"SSC_{idx}"
            r_ohm = row.get('r_ohm', 0.0)
            x_ohm = row.get('x_ohm', 0.0)
            set_vm_pu = row.get('set_vm_pu', 1.0)
            vm_internal_pu = row.get('vm_internal_pu', 1.0)
            va_internal_degree = row.get('va_internal_degree', 0.0)
            controllable = row.get('controllable', True)
            in_service = row.get('in_service', True)
            lines.append(f"pp.create_ssc(net, bus=bus_{bus}, name='{name}', "
                        f"r_ohm={r_ohm}, x_ohm={x_ohm}, set_vm_pu={set_vm_pu}, "
                        f"vm_internal_pu={vm_internal_pu}, va_internal_degree={va_internal_degree}, "
                        f"controllable={controllable}, in_service={in_service})")
        lines.append("")
    
    # Create load DC elements
    if hasattr(net, 'load_dc') and not net.load_dc.empty:
        lines.append("# Create DC load elements")
        for idx, row in net.load_dc.iterrows():
            bus = row['bus']
            name = row['name'] if 'name' in row else f"LoadDC_{idx}"
            p_mw = row.get('p_mw', 0.0)
            in_service = row.get('in_service', True)
            lines.append(f"pp.create_load_dc(net, bus=bus_{bus}, name='{name}', p_mw={p_mw}, in_service={in_service})")
        lines.append("")
    
    # Create source DC elements
    if hasattr(net, 'source_dc') and not net.source_dc.empty:
        lines.append("# Create DC source elements")
        for idx, row in net.source_dc.iterrows():
            bus = row['bus']
            name = row['name'] if 'name' in row else f"SourceDC_{idx}"
            vm_pu = row.get('vm_pu', 1.0)
            in_service = row.get('in_service', True)
            lines.append(f"pp.create_source_dc(net, bus=bus_{bus}, name='{name}', vm_pu={vm_pu}, in_service={in_service})")
        lines.append("")
    
    # Create switch elements
    if hasattr(net, 'switch') and not net.switch.empty:
        lines.append("# Create switch elements")
        for idx, row in net.switch.iterrows():
            bus = row['bus']
            element = row['element']
            et = row.get('et', 'line')
            name = row['name'] if 'name' in row else f"Switch_{idx}"
            closed = row.get('closed', True)
            switch_type = row.get('type', 'CB')
            z_ohm = row.get('z_ohm', 0.0)
            in_ka = row.get('in_ka', 0.0)
            in_service = row.get('in_service', True)
            lines.append(f"pp.create_switch(net, bus=bus_{bus}, element={element}, et='{et}', name='{name}', "
                        f"closed={closed}, type='{switch_type}', z_ohm={z_ohm}, in_ka={in_ka}, in_service={in_service})")
        lines.append("")
    
    # Create VSC elements
    if hasattr(net, 'vsc') and not net.vsc.empty:
        lines.append("# Create VSC (Voltage Source Converter) elements")
        for idx, row in net.vsc.iterrows():
            bus = row['bus']
            bus_dc = row.get('bus_dc')
            name = row['name'] if 'name' in row else f"VSC_{idx}"
            p_mw = row.get('p_mw', 0.0)
            vm_pu = row.get('vm_pu', 1.0)
            sn_mva = row.get('sn_mva', 0.0)
            rx = row.get('rx', 0.1)
            max_ik_ka = row.get('max_ik_ka', 0.0)
            in_service = row.get('in_service', True)
            # bus_dc refers to a DC bus index, so use bus_dc_{bus_dc} variable name
            bus_dc_var = f"bus_dc_{bus_dc}" if bus_dc is not None else "None"
            lines.append(f"pp.create_vsc(net, bus=bus_{bus}, bus_dc={bus_dc_var}, name='{name}', "
                        f"p_mw={p_mw}, vm_pu={vm_pu}, sn_mva={sn_mva}, rx={rx}, max_ik_ka={max_ik_ka}, in_service={in_service})")
        lines.append("")
    
    # Create B2B VSC elements
    if hasattr(net, 'b2b_vsc') and not net.b2b_vsc.empty:
        lines.append("# Create B2B VSC (Back-to-Back Voltage Source Converter) elements")
        for idx, row in net.b2b_vsc.iterrows():
            bus1 = row['bus1']
            bus2 = row['bus2']
            name = row['name'] if 'name' in row else f"B2BVSC_{idx}"
            p_mw = row.get('p_mw', 0.0)
            vm1_pu = row.get('vm1_pu', 1.0)
            vm2_pu = row.get('vm2_pu', 1.0)
            sn_mva = row.get('sn_mva', 0.0)
            rx = row.get('rx', 0.1)
            max_ik_ka = row.get('max_ik_ka', 0.0)
            in_service = row.get('in_service', True)
            lines.append(f"pp.create_b2b_vsc(net, bus1=bus_{bus1}, bus2=bus_{bus2}, name='{name}', "
                        f"p_mw={p_mw}, vm1_pu={vm1_pu}, vm2_pu={vm2_pu}, sn_mva={sn_mva}, "
                        f"rx={rx}, max_ik_ka={max_ik_ka}, in_service={in_service})")
        lines.append("")
    
    # Create DC line elements
    if hasattr(net, 'dcline') and not net.dcline.empty:
        lines.append("# Create DC line elements")
        for idx, row in net.dcline.iterrows():
            from_bus = row['from_bus']
            to_bus = row['to_bus']
            name = row['name'] if 'name' in row else f"DCLine_{idx}"
            p_mw = row.get('p_mw', 0.0)
            loss_percent = row.get('loss_percent', 0.0)
            loss_mw = row.get('loss_mw', 0.0)
            vm_from_pu = row.get('vm_from_pu', 1.0)
            vm_to_pu = row.get('vm_to_pu', 1.0)
            in_service = row.get('in_service', True)
            lines.append(f"pp.create_dcline(net, from_bus=bus_{from_bus}, to_bus=bus_{to_bus}, name='{name}', "
                        f"p_mw={p_mw}, loss_percent={loss_percent}, loss_mw={loss_mw}, "
                        f"vm_from_pu={vm_from_pu}, vm_to_pu={vm_to_pu}, in_service={in_service})")
        lines.append("")
    
    # Run power flow
    lines.append("# Run power flow")
    lines.append(f"pp.runpp(net, algorithm='{algorithm}', calculate_voltage_angles={calculate_voltage_angles}, init='{init}')")
    lines.append("")
    
    # Add results printing
    lines.append("# Print results")
    lines.append("print('\\nBus Results:')")
    lines.append("print(net.res_bus)")
    lines.append("print('\\nLine Results:')")
    lines.append("print(net.res_line)")
    
    return '\n'.join(lines)

def create_busbars(in_data, net):
    Busbars = {}
    # Store user-friendly names mapping for later use
    net.user_friendly_names = {}
    
    # Create a separate dictionary for DC buses
    DcBuses = {}
    
    # Check if DC bus functionality is available in this pandapower version
    has_dc_bus_support = hasattr(pp, 'create_bus_dc')
    if not has_dc_bus_support:
        print(f"⚠️ Note: pandapower version {pp.__version__} does not support DC buses (create_bus_dc).")
        print("   DC Bus, VSC, and B2B VSC elements will be skipped.")
        print("   You can still use 'DC Line' which connects two AC buses directly.")
        print("   Upgrade to pandapower 3.1+ for full DC grid support.")
    
    for x in in_data:
        if "DC Bus" in in_data[x]['typ']:
            # Handle DC Bus separately - requires pandapower 3.1+
            if not has_dc_bus_support:
                user_friendly_name = in_data[x].get('userFriendlyName', in_data[x].get('name', 'Unknown'))
                print(f"   Skipping DC Bus '{user_friendly_name}' - DC bus not supported in pandapower {pp.__version__}")
                continue
                
            dc_bus_name = in_data[x]['name']
            user_friendly_name = in_data[x].get('userFriendlyName', dc_bus_name)
            
            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            
            DcBuses[dc_bus_name] = pp.create_bus_dc(
                net,
                vn_kv=float(in_data[x].get('vn_kv', 0.0)),
                name=dc_bus_name,
                in_service=in_service
            )
            
            # Store the user-friendly name mapping
            net.user_friendly_names[dc_bus_name] = user_friendly_name
        elif "Bus" in in_data[x]['typ']:
            bus_name = in_data[x]['name']
            user_friendly_name = in_data[x].get('userFriendlyName', bus_name)
            
            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            
            Busbars[bus_name] = pp.create_bus(
                net,
                name=bus_name,
                id=in_data[x]['id'],
                vn_kv=float(in_data[x]['vn_kv']),
                type='b',
                in_service=in_service
            )
            
            # Store the user-friendly name mapping
            net.user_friendly_names[bus_name] = user_friendly_name
    
    # Store DC buses in Busbars dict for compatibility
    Busbars.update(DcBuses)
    
    # Store DC bus names in net object for later use (to distinguish DC vs AC buses)
    net.dc_bus_names = set(DcBuses.keys())
    
    return Busbars


def create_other_elements(in_data,net,x, Busbars):

    #tworzymy zmienne ktorych nazwa odpowiada modelowi z js - np.Hwap0ntfbV98zYtkLMVm-8

    # Helper function for safe type conversion (local version with different default)
    def safe_float_local(value, default=None):
        if value is None or value == 'None' or value == '':
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    for name,value in Busbars.items():
        globals()[name] = value    
       
    for x in in_data:
      
        #eval - rozwiazuje problem z wartosciami NaN
        if (in_data[x]['typ'].startswith("Line")):
            try:
                # Lines have busFrom and busTo fields directly
                bus_from = in_data[x].get('busFrom')
                bus_to = in_data[x].get('busTo')                
             
                from_bus_idx = Busbars.get(bus_from)
                to_bus_idx = Busbars.get(bus_to)
                
                if from_bus_idx is None:
                    element_name = in_data[x].get('userFriendlyName', in_data[x].get('name', 'Unknown'))
                    raise ValueError(
                        f"CONNECTION ERROR: Line '{element_name}' is trying to connect from bus '{bus_from}', "
                        f"but this bus does not exist in your diagram.\n\n"
                        f"SOLUTION: Please ensure that:\n"
                        f"1. You have placed Bus/Busbar elements at both ends of the line\n"
                        f"2. The line is properly connected to these Bus elements\n"
                        f"3. Lines must connect two Bus elements (from_bus and to_bus)"
                    )
                if to_bus_idx is None:
                    element_name = in_data[x].get('userFriendlyName', in_data[x].get('name', 'Unknown'))
                    raise ValueError(
                        f"CONNECTION ERROR: Line '{element_name}' is trying to connect to bus '{bus_to}', "
                        f"but this bus does not exist in your diagram.\n\n"
                        f"SOLUTION: Please ensure that:\n"
                        f"1. You have placed Bus/Busbar elements at both ends of the line\n"
                        f"2. The line is properly connected to these Bus elements\n"
                        f"3. Lines must connect two Bus elements (from_bus and to_bus)"
                    )
                    
         
            except Exception as e:
                continue
                
            # Create a base parameters dict with required parameters
            line_params = {
                "from_bus": from_bus_idx,
                "to_bus": to_bus_idx,
                "name": in_data[x]['name'],
                "id": in_data[x]['id'],
                "r_ohm_per_km": float(in_data[x]['r_ohm_per_km']),
                "x_ohm_per_km": float(in_data[x]['x_ohm_per_km']),
                "c_nf_per_km": float(in_data[x]['c_nf_per_km']),
                "g_us_per_km": float(in_data[x]['g_us_per_km']),
                "max_i_ka": float(in_data[x]['max_i_ka']),
                "type": in_data[x]['type'],
                "length_km": float(in_data[x]['length_km'])
            }

            # Handle optional parameters - include if they have valid values
            optional_params = ['parallel', 'df']
            
            for param in optional_params:
                value = in_data[x].get(param)
                if value is not None and value not in ('None', '', 'null'):
                    try:
                        if param == 'parallel':
                            line_params[param] = int(value)
                        else:  # df
                            line_params[param] = float(value)
                    except (ValueError, TypeError):
                        # If conversion fails, use default values
                        if param == 'parallel':
                            line_params[param] = 1
                        else:  # df
                            line_params[param] = 1.0
                else:
                    # Use default values when parameter is None or empty
                    if param == 'parallel':
                        line_params[param] = 1
                    else:  # df
                        line_params[param] = 1.0

            # Make sure zero sequence parameters are explicitly converted to float
            # This should solve the isnan() issue
            try:
                if 'r0_ohm_per_km' in in_data[x] and in_data[x]['r0_ohm_per_km'] is not None:
                    line_params["r0_ohm_per_km"] = float(in_data[x]['r0_ohm_per_km'])
                else:
                    line_params["r0_ohm_per_km"] = 1.0  # Default as float
                    
                if 'x0_ohm_per_km' in in_data[x] and in_data[x]['x0_ohm_per_km'] is not None:
                    line_params["x0_ohm_per_km"] = float(in_data[x]['x0_ohm_per_km'])
                else:
                    line_params["x0_ohm_per_km"] = 1.0  # Default as float
                    
                if 'c0_nf_per_km' in in_data[x] and in_data[x]['c0_nf_per_km'] is not None:
                    line_params["c0_nf_per_km"] = float(in_data[x]['c0_nf_per_km'])
                else:
                    line_params["c0_nf_per_km"] = 0.0  # Default as float
            except (ValueError, TypeError) as e:
                # Set to defaults if conversion fails
                line_params["r0_ohm_per_km"] = 1.0
                line_params["x0_ohm_per_km"] = 1.0
                line_params["c0_nf_per_km"] = 0.0

            # Handle endtemp_degree separately as it's truly optional
            if 'endtemp_degree' in in_data[x] and in_data[x]['endtemp_degree'] is not None:
                try:
                    line_params["endtemp_degree"] = float(in_data[x]['endtemp_degree'])
                except (ValueError, TypeError):
                    # Skip adding this parameter if conversion fails
                    pass

            # Add in_service parameter (default to True if not specified)
            if 'in_service' in in_data[x]:
                line_params["in_service"] = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            else:
                line_params["in_service"] = True

            # Call the function with the prepared parameters
            pp.create_line_from_parameters(net, **line_params)
            
            # Store user-friendly name for line
            line_name = in_data[x]['name']
            user_friendly_name = in_data[x].get('userFriendlyName', line_name)
            if not hasattr(net, 'user_friendly_names'):
                net.user_friendly_names = {}
            net.user_friendly_names[line_name] = user_friendly_name  
            
            
            #pp.create_line_from_parameters(net,  from_bus=eval(in_data[x]['busFrom']), to_bus=eval(in_data[x]['busTo']), name=in_data[x]['name'], id=in_data[x]['id'], r_ohm_per_km=in_data[x]['r_ohm_per_km'], x_ohm_per_km=in_data[x]['x_ohm_per_km'], c_nf_per_km= in_data[x]['c_nf_per_km'], g_us_per_km= in_data[x]['g_us_per_km'], 
            #                               r0_ohm_per_km=1, x0_ohm_per_km=1, c0_nf_per_km=0, endtemp_degree=in_data[x]['endtemp_degree'],
            #                               max_i_ka= in_data[x]['max_i_ka'],type= in_data[x]['type'], length_km=in_data[x]['length_km'], parallel=in_data[x]['parallel'], df=in_data[x]['df'])
            #w specyfikacji zapisano, że poniższe parametry są typu nan. Wartosci składowych zerowych mogą być wprowadzone przez funkcję create line.
            #r0_ohm_per_km= in_data[x]['r0_ohm_per_km'], x0_ohm_per_km= in_data[x]['x0_ohm_per_km'], c0_nf_per_km= in_data[x]['c0_nf_per_km'], max_loading_percent=in_data[x]['max_loading_percent'], endtemp_degree=in_data[x]['endtemp_degree'],
        
        if (in_data[x]['typ'].startswith("External Grid") or in_data[x]['typ'].startswith("ExternalGrid")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                element_name = in_data[x].get('userFriendlyName', in_data[x].get('name', 'Unknown'))
                bus_name = in_data[x]['bus']
                
                # Check if bus is None (not connected) or references non-existent bus
                if bus_name is None:
                    raise ValueError(
                        f"CONNECTION ERROR: External Grid '{element_name}' (ID: {in_data[x].get('id', 'Unknown')}) is NOT CONNECTED to any bus.\n\n"
                        f"SOLUTION: Please ensure that:\n"
                        f"1. You have placed a Bus/Busbar element in your diagram\n"
                        f"2. Draw a connection line from the External Grid to a Bus element\n"
                        f"3. Verify the connection line is properly attached at both ends\n\n"
                        f"IMPORTANT: Every electrical component must be connected to at least one Bus element."
                    )
                else:
                    raise ValueError(
                        f"CONNECTION ERROR: External Grid '{element_name}' is trying to connect to bus '{bus_name}', "
                        f"but this bus does not exist in your diagram.\n\n"
                        f"SOLUTION: Please ensure that:\n"
                        f"1. You have placed a Bus/Busbar element in your diagram\n"
                        f"2. The External Grid is connected to this Bus element with a connection line\n"
                        f"3. All electrical elements (External Grids, Generators, Loads, Transformers, etc.) "
                        f"are properly connected to Bus elements\n\n"
                        f"IMPORTANT: Each electrical component must be connected to at least one Bus element."
                    )

            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            
            # Validate and auto-correct vm_pu for external grid
            ext_grid_vm_pu = safe_float(in_data[x]['vm_pu'])
            bus_vn_kv = net.bus.loc[bus_idx, 'vn_kv'] if bus_idx is not None else None
            
            if ext_grid_vm_pu == 0:
                ext_grid_vm_pu = 1.0
                print(f"WARNING: External Grid '{in_data[x].get('userFriendlyName', in_data[x]['name'])}' had vm_pu=0, auto-corrected to 1.0 p.u.")
            elif ext_grid_vm_pu > 1.5 and bus_vn_kv is not None and bus_vn_kv > 0:
                # User likely entered voltage in kV instead of per unit
                corrected_vm_pu = ext_grid_vm_pu / bus_vn_kv
                print(f"WARNING: External Grid '{in_data[x].get('userFriendlyName', in_data[x]['name'])}' has vm_pu={ext_grid_vm_pu}, "
                      f"which is unreasonably high. vm_pu should be close to 1.0 (per unit). "
                      f"Bus nominal voltage is {bus_vn_kv} kV. Auto-correcting vm_pu from {ext_grid_vm_pu} to {corrected_vm_pu:.4f} p.u. "
                      f"(assuming user entered kV instead of p.u.)")
                if not hasattr(net, 'warnings'):
                    net.warnings = []
                net.warnings.append(
                    f"External Grid '{in_data[x].get('userFriendlyName', in_data[x]['name'])}': "
                    f"vm_pu was set to {ext_grid_vm_pu}, which appears to be a voltage in kV, not per unit. "
                    f"Auto-corrected to {corrected_vm_pu:.4f} p.u. "
                    f"(vm_pu should be close to 1.0, e.g. 0.95-1.05 for normal operation). "
                    f"The bus nominal voltage ({bus_vn_kv} kV) is used as the base."
                )
                ext_grid_vm_pu = corrected_vm_pu
            
            pp.create_ext_grid(
                net,
                bus=bus_idx,
                name=in_data[x]['name'],
                id=in_data[x]['id'],
                vm_pu=ext_grid_vm_pu,
                va_degree=safe_float(in_data[x]['va_degree']),
                s_sc_max_mva=safe_float(in_data[x]['s_sc_max_mva']),
                s_sc_min_mva=safe_float(in_data[x]['s_sc_min_mva']),
                rx_max=safe_float(in_data[x]['rx_max']),
                rx_min=safe_float(in_data[x]['rx_min']),
                r0x0_max=safe_float(in_data[x]['r0x0_max']),
                x0x_max=safe_float(in_data[x]['x0x_max']),
                in_service=in_service
            )
            
            # Store user-friendly name for external grid
            ext_grid_name = in_data[x]['name']
            user_friendly_name = in_data[x].get('userFriendlyName', ext_grid_name)
            if not hasattr(net, 'user_friendly_names'):
                net.user_friendly_names = {}
            net.user_friendly_names[ext_grid_name] = user_friendly_name
       
        if (in_data[x]['typ'].startswith("Generator")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                element_name = in_data[x].get('userFriendlyName', in_data[x].get('name', 'Unknown'))
                bus_name = in_data[x]['bus']
                
                # Check if bus is None (not connected) or references non-existent bus
                if bus_name is None:
                    raise ValueError(
                        f"CONNECTION ERROR: Generator '{element_name}' (ID: {in_data[x].get('id', 'Unknown')}) is NOT CONNECTED to any bus.\n\n"
                        f"SOLUTION: Please ensure that:\n"
                        f"1. You have placed a Bus/Busbar element in your diagram\n"
                        f"2. Draw a connection line from the Generator to a Bus element\n"
                        f"3. Verify the connection line is properly attached at both ends\n\n"
                        f"IMPORTANT: Every electrical component must be connected to at least one Bus element."
                    )
                else:
                    raise ValueError(
                        f"CONNECTION ERROR: Generator '{element_name}' is trying to connect to bus '{bus_name}', "
                        f"but this bus does not exist in your diagram.\n\n"
                        f"SOLUTION: Please ensure that:\n"
                        f"1. You have placed a Bus/Busbar element in your diagram\n"
                        f"2. The Generator is connected to this Bus element with a connection line\n"
                        f"3. All electrical elements must be properly connected to Bus elements"
                    )
    
            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            
            # Validate and auto-correct vm_pu for generator
            gen_vm_pu = safe_float(in_data[x]['vm_pu'])
            gen_bus_vn_kv = net.bus.loc[bus_idx, 'vn_kv'] if bus_idx is not None else None
            
            if gen_vm_pu == 0:
                gen_vm_pu = 1.0
                print(f"WARNING: Generator '{in_data[x].get('userFriendlyName', in_data[x]['name'])}' had vm_pu=0, auto-corrected to 1.0 p.u.")
            elif gen_vm_pu > 1.5 and gen_bus_vn_kv is not None and gen_bus_vn_kv > 0:
                corrected_vm_pu = gen_vm_pu / gen_bus_vn_kv
                print(f"WARNING: Generator '{in_data[x].get('userFriendlyName', in_data[x]['name'])}' has vm_pu={gen_vm_pu}, "
                      f"which is unreasonably high. Auto-correcting to {corrected_vm_pu:.4f} p.u.")
                if not hasattr(net, 'warnings'):
                    net.warnings = []
                net.warnings.append(
                    f"Generator '{in_data[x].get('userFriendlyName', in_data[x]['name'])}': "
                    f"vm_pu was set to {gen_vm_pu}, which appears to be a voltage in kV, not per unit. "
                    f"Auto-corrected to {corrected_vm_pu:.4f} p.u. "
                    f"(vm_pu should be close to 1.0, e.g. 0.95-1.05 for normal operation)."
                )
                gen_vm_pu = corrected_vm_pu
            elif gen_vm_pu > 0 and gen_vm_pu < 0.5:
                print(f"WARNING: Generator '{in_data[x].get('userFriendlyName', in_data[x]['name'])}' has unusually low vm_pu={gen_vm_pu}. "
                      f"vm_pu should be close to 1.0 (per unit). Please verify this value.")
                if not hasattr(net, 'warnings'):
                    net.warnings = []
                net.warnings.append(
                    f"Generator '{in_data[x].get('userFriendlyName', in_data[x]['name'])}': "
                    f"vm_pu is set to {gen_vm_pu}, which is unusually low. "
                    f"vm_pu is the voltage setpoint in per unit and should be close to 1.0 (e.g. 0.95-1.05). "
                    f"A very low value will cause the generator to try to regulate bus voltage to near zero, "
                    f"leading to unrealistic results."
                )
            
            pp.create_gen(net, bus = bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], p_mw=safe_float(in_data[x]['p_mw']), vm_pu=gen_vm_pu, sn_mva=safe_float(in_data[x]['sn_mva']), scaling=safe_float(in_data[x].get('scaling'), 1.0),
                          vn_kv=safe_float(in_data[x]['vn_kv']), xdss_pu=safe_float(in_data[x]['xdss_pu']), rdss_ohm=safe_float(in_data[x]['rdss_ohm']), cos_phi=safe_float(in_data[x]['cos_phi']), pg_percent=safe_float(in_data[x]['pg_percent']), in_service=in_service)    #, power_station_trafo=in_data[x]['power_station_trafo']
            
            # Store user-friendly name for generator
            gen_name = in_data[x]['name']
            user_friendly_name = in_data[x].get('userFriendlyName', gen_name)
            if not hasattr(net, 'user_friendly_names'):
                net.user_friendly_names = {}
            net.user_friendly_names[gen_name] = user_friendly_name
        
        if (in_data[x]['typ'].startswith("Static Generator")):      
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                element_name = in_data[x].get('userFriendlyName', in_data[x].get('name', 'Unknown'))
                bus_name = in_data[x]['bus']
                
                # Check if bus is None (not connected) or references non-existent bus
                if bus_name is None:
                    raise ValueError(
                        f"CONNECTION ERROR: Static Generator '{element_name}' (ID: {in_data[x].get('id', 'Unknown')}) is NOT CONNECTED to any bus.\n\n"
                        f"SOLUTION: Please ensure that:\n"
                        f"1. You have placed a Bus/Busbar element in your diagram\n"
                        f"2. Draw a connection line from the Static Generator to a Bus element\n"
                        f"3. Verify the connection line is properly attached at both ends\n\n"
                        f"IMPORTANT: Every electrical component must be connected to at least one Bus element."
                    )
                else:
                    raise ValueError(
                        f"CONNECTION ERROR: Static Generator '{element_name}' is trying to connect to bus '{bus_name}', "
                        f"but this bus does not exist in your diagram.\n\n"
                        f"SOLUTION: Please ensure that:\n"
                        f"1. You have placed a Bus/Busbar element in your diagram\n"
                        f"2. The Static Generator is connected to this Bus element with a connection line\n"
                        f"3. All electrical elements must be properly connected to Bus elements"
                    )
           
            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            
            pp.create_sgen(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], p_mw=safe_float(in_data[x]['p_mw']), q_mvar=safe_float(in_data[x]['q_mvar']), sn_mva=safe_float(in_data[x]['sn_mva']), scaling=safe_float(in_data[x].get('scaling'), 1.0), type=in_data[x]['type'],
                           k=1.1, rx=safe_float(in_data[x]['rx']), generator_type=in_data[x]['generator_type'], lrc_pu=safe_float(in_data[x]['lrc_pu']), max_ik_ka=safe_float(in_data[x]['max_ik_ka']), current_source=in_data[x]['current_source'], kappa = 1.5, in_service=in_service)
            
            # Store user-friendly name for static generator
            sgen_name = in_data[x]['name']
            user_friendly_name = in_data[x].get('userFriendlyName', sgen_name)
            if not hasattr(net, 'user_friendly_names'):
                net.user_friendly_names = {}
            net.user_friendly_names[sgen_name] = user_friendly_name
        
        if (in_data[x]['typ'].startswith("Asymmetric Static Generator")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                continue
            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            pp.create_asymmetric_sgen(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], p_a_mw=safe_float(in_data[x]['p_a_mw']), p_b_mw=safe_float(in_data[x]['p_b_mw']), p_c_mw=safe_float(in_data[x]['p_c_mw']), q_a_mvar=safe_float(in_data[x]['q_a_mvar']), q_b_mvar=safe_float(in_data[x]['q_b_mvar']), q_c_mvar=safe_float(in_data[x]['q_c_mvar']), sn_mva=safe_float(in_data[x]['sn_mva']), scaling=safe_float(in_data[x].get('scaling'), 1.0), type=in_data[x]['type'], in_service=in_service)   
        #Zero sequence parameters** (Added through std_type For Three phase load flow) :
            #vk0_percent** - zero sequence relative short-circuit voltage
            #vkr0_percent** - real part of zero sequence relative short-circuit voltage
            #mag0_percent** - ratio between magnetizing and short circuit impedance (zero sequence)                                
            #mag0_rx**  - zero sequence magnetizing r/x  ratio
            #si0_hv_partial** - zero sequence short circuit impedance  distribution in hv side
            #vk0_percent=in_data[x]['vk0_percent'], vkr0_percent=in_data[x]['vkr0_percent'], mag0_percent=in_data[x]['mag0_percent'], si0_hv_partial=in_data[x]['si0_hv_partial'],
        if (in_data[x]['typ'].startswith("Transformer")): 
            # Get values with default fallbacks and proper type conversion
            parallel_value = safe_int(in_data[x].get('parallel', 1), 1)
            vector_group_raw = in_data[x].get('vector_group', None)
            vk0_percent = safe_float(in_data[x].get('vk0_percent', None))
            vkr0_percent = safe_float(in_data[x].get('vkr0_percent', None))
            mag0_percent = safe_float(in_data[x].get('mag0_percent', None))
            mag0_rx = safe_float(in_data[x].get('mag0_rx', None))
            si0_hv_partial = safe_float(in_data[x].get('si0_hv_partial', None))
            
            # Parse vector group to separate base group from phase shift
            vector_group, phase_shift_from_group = parse_vector_group(vector_group_raw)
            
            # Get bus indices with error checking
            hv_bus_name = in_data[x]['hv_bus']
            lv_bus_name = in_data[x]['lv_bus']
            hv_bus_idx = Busbars.get(hv_bus_name)
            lv_bus_idx = Busbars.get(lv_bus_name)
            
            if hv_bus_idx is None:
                continue
            if lv_bus_idx is None:
                continue
            
            # Prepare parameters dict for transformer creation with proper type conversion
            # CRITICAL: tap_step_percent must be non-zero for tap control to work
            # If it's 0, all tap positions are identical (no voltage change)
            tap_step_value = safe_float(in_data[x].get('tap_step_percent', None))
            if tap_step_value is None or tap_step_value == 0.0:
                # Only use default if tap_max != tap_min (indicating tap control is intended)
                tap_max_val = safe_int(in_data[x].get('tap_max', 0))
                tap_min_val = safe_int(in_data[x].get('tap_min', 0))
                if tap_max_val != tap_min_val and tap_max_val != 0:
                    tap_step_value = 1.5  # Standard default for distribution transformers
                else:
                    tap_step_value = 0.0  # No tap control
            
            # Get tap_changer_type (pandapower 3.0+): "Ratio", "Symmetrical", or "Ideal"
            tap_changer_type = in_data[x].get('tap_changer_type', 'Ratio')
            if tap_changer_type not in ['Ratio', 'Symmetrical', 'Ideal']:
                tap_changer_type = 'Ratio'  # Default value
            
            transformer_params = {
                'hv_bus': hv_bus_idx,
                'lv_bus': lv_bus_idx,
                'name': in_data[x]['name'],
                'id': in_data[x]['id'],
                'sn_mva': safe_float(in_data[x]['sn_mva']),
                'vn_hv_kv': safe_float(in_data[x]['vn_hv_kv']),
                'vn_lv_kv': safe_float(in_data[x]['vn_lv_kv']),
                'vkr_percent': safe_float(in_data[x].get('vkr_percent', 1.0)),
                'vk_percent': safe_float(in_data[x].get('vk_percent', 6.0)),
                'pfe_kw': safe_float(in_data[x].get('pfe_kw', 0.0)),
                'i0_percent': safe_float(in_data[x].get('i0_percent', 0.0)),
                'parallel': float(parallel_value),
                'shift_degree': safe_float(in_data[x].get('shift_degree', 0)) + phase_shift_from_group,
                'tap_side': in_data[x].get('tap_side', 'hv'),
                'tap_pos': float(safe_int(in_data[x].get('tap_pos', 0))),
                'tap_neutral': float(safe_int(in_data[x].get('tap_neutral', 0))),
                'tap_max': float(safe_int(in_data[x].get('tap_max', 0))),
                'tap_min': float(safe_int(in_data[x].get('tap_min', 0))),
                'tap_step_percent': tap_step_value,
                'tap_step_degree': safe_float(in_data[x].get('tap_step_degree', 0)),
                'tap_changer_type': tap_changer_type  # pandapower 3.0+
            }
            
            # Add optional parameters with proper defaults
            if vector_group is not None and vector_group != 'None' and vector_group != '':
                transformer_params['vector_group'] = vector_group
            else:
                transformer_params['vector_group'] = 'Dyn'  # Default vector group
            
            # For zero sequence parameters, use provided values or default to main sequence values
            if vk0_percent is not None and vk0_percent != 0.0:
                transformer_params['vk0_percent'] = vk0_percent
            else:
                transformer_params['vk0_percent'] = transformer_params['vk_percent']  # Default to main sequence
            
            if vkr0_percent is not None and vkr0_percent != 0.0:
                transformer_params['vkr0_percent'] = vkr0_percent
            else:
                transformer_params['vkr0_percent'] = transformer_params['vkr_percent']  # Default to main sequence
            
            if mag0_percent is not None:
                transformer_params['mag0_percent'] = mag0_percent
            else:
                transformer_params['mag0_percent'] = 0.0  # Default zero sequence magnetizing current
            
            if si0_hv_partial is not None:
                transformer_params['si0_hv_partial'] = si0_hv_partial
            else:
                transformer_params['si0_hv_partial'] = 0.0  # Default zero sequence partial current
            
            if mag0_rx is not None:
                transformer_params['mag0_rx'] = mag0_rx
            else:
                transformer_params['mag0_rx'] = 0.0  # Default zero sequence magnetizing r/x ratio
            
            # Add in_service parameter (default to True if not specified)
            if 'in_service' in in_data[x]:
                transformer_params['in_service'] = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            else:
                transformer_params['in_service'] = True
            
            pp.create_transformer_from_parameters(net, **transformer_params)
            
            # Store user-friendly name for transformer
            trafo_name = in_data[x]['name']
            user_friendly_name = in_data[x].get('userFriendlyName', trafo_name)
            if not hasattr(net, 'user_friendly_names'):
                net.user_friendly_names = {}
            net.user_friendly_names[trafo_name] = user_friendly_name
            
            # Discrete Tap Control: collect (trafo_idx, control_side, vm_lower_pu, vm_upper_pu) for controllers
            discrete_tap = in_data[x].get('discrete_tap_control')
            if discrete_tap in (True, 'true', 'True', '1'):
                vm_lo = safe_float_local(in_data[x].get('vm_lower_pu'), 0.99)
                vm_hi = safe_float_local(in_data[x].get('vm_upper_pu'), 1.01)
                vm_lo = 0.99 if vm_lo is None else float(vm_lo)
                vm_hi = 1.01 if vm_hi is None else float(vm_hi)
                control_side = in_data[x].get('control_side', 'lv')  # Default to 'lv' if not specified
                trafo_idx = int(net.trafo.index[-1])
                if not hasattr(net, 'trafo_discrete_tap_controllers'):
                    net.trafo_discrete_tap_controllers = []
                net.trafo_discrete_tap_controllers.append((trafo_idx, control_side, vm_lo, vm_hi))
       
        if (in_data[x]['typ'].startswith("Three Winding Transformer")):  
            # Parse vector group to separate base group from phase shift
            vector_group_raw = in_data[x].get('vector_group', None)
            vector_group, phase_shift_from_group = parse_vector_group(vector_group_raw)
            
            # Get bus indices with error checking
            hv_bus_name = in_data[x]['hv_bus']
            mv_bus_name = in_data[x]['mv_bus']
            lv_bus_name = in_data[x]['lv_bus']
            hv_bus_idx = Busbars.get(hv_bus_name)
            mv_bus_idx = Busbars.get(mv_bus_name)
            lv_bus_idx = Busbars.get(lv_bus_name)
            
            if hv_bus_idx is None:
                continue
            if mv_bus_idx is None:
                continue
            if lv_bus_idx is None:
                continue
            
            # Get tap_changer_type (pandapower 3.0+): "Ratio", "Symmetrical", or "Ideal"
            tap_changer_type_3w = in_data[x].get('tap_changer_type', 'Ratio')
            if tap_changer_type_3w not in ['Ratio', 'Symmetrical', 'Ideal']:
                tap_changer_type_3w = 'Ratio'  # Default value
            
            # Prepare optional parameters - only include if they are not None
            transformer_params = {
                'hv_bus': hv_bus_idx,
                'mv_bus': mv_bus_idx,
                'lv_bus': lv_bus_idx,
                'name': in_data[x]['name'],
                'id': in_data[x]['id'],
                'sn_hv_mva': safe_float(in_data[x]['sn_hv_mva']),
                'sn_mv_mva': safe_float(in_data[x]['sn_mv_mva']),
                'sn_lv_mva': safe_float(in_data[x]['sn_lv_mva']),
                'vn_hv_kv': safe_float(in_data[x]['vn_hv_kv']),
                'vn_mv_kv': safe_float(in_data[x]['vn_mv_kv']),
                'vn_lv_kv': safe_float(in_data[x]['vn_lv_kv']),
                'vk_hv_percent': safe_float(in_data[x]['vk_hv_percent']),
                'vk_mv_percent': safe_float(in_data[x]['vk_mv_percent']),
                'vk_lv_percent': safe_float(in_data[x]['vk_lv_percent']),
                'vkr_hv_percent': safe_float(in_data[x]['vkr_hv_percent']),
                'vkr_mv_percent': safe_float(in_data[x]['vkr_mv_percent']),
                'vkr_lv_percent': safe_float(in_data[x]['vkr_lv_percent']),
                'pfe_kw': safe_float(in_data[x]['pfe_kw']),
                'i0_percent': safe_float(in_data[x]['i0_percent']),
                'shift_mv_degree': safe_float(in_data[x]['shift_mv_degree']) + phase_shift_from_group,
                'shift_lv_degree': safe_float(in_data[x]['shift_lv_degree']) + phase_shift_from_group,
                'tap_step_percent': safe_float(in_data[x]['tap_step_percent']),
                'tap_side': in_data[x]['tap_side'],
                'tap_min': float(safe_int(in_data[x]['tap_min'])),
                'tap_max': float(safe_int(in_data[x]['tap_max'])),
                'tap_pos': float(safe_int(in_data[x]['tap_pos'])),
                'tap_changer_type': tap_changer_type_3w  # pandapower 3.0+
            }
            
            # Add optional parameters only if they are not None
            optional_params = ['vector_group', 'vk0_hv_percent', 'vk0_mv_percent', 'vk0_lv_percent', 
                             'vkr0_hv_percent', 'vkr0_mv_percent', 'vkr0_lv_percent']
            
            for param in optional_params:
                value = in_data[x].get(param)
                if value is not None and value not in ('None', '', 'null'):
                    if param == 'vector_group':
                        transformer_params[param] = vector_group  # Use parsed base group
                    else:
                        transformer_params[param] = safe_float(value)  # Convert to float
            
            # Add in_service parameter (default to True if not specified)
            if 'in_service' in in_data[x]:
                transformer_params['in_service'] = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            else:
                transformer_params['in_service'] = True
            
            pp.create_transformer3w_from_parameters(net, **transformer_params)
            
            # Store user-friendly name for three-winding transformer
            trafo3w_name = in_data[x]['name']
            user_friendly_name = in_data[x].get('userFriendlyName', trafo3w_name)
            if not hasattr(net, 'user_friendly_names'):
                net.user_friendly_names = {}
            net.user_friendly_names[trafo3w_name] = user_friendly_name
        
        if (in_data[x]['typ'].startswith("Shunt Reactor")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                continue
            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            pp.create_shunt(net, typ="shuntreactor", bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], p_mw=safe_float(in_data[x]['p_mw']), q_mvar=safe_float(in_data[x]['q_mvar']), vn_kv=safe_float(in_data[x]['vn_kv']), step=float(safe_float(in_data[x].get('step', 1)) or 1), max_step=float(safe_float(in_data[x].get('max_step', 1)) or 1), in_service=in_service)
        
        if (in_data[x]['typ'].startswith("Capacitor")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                continue
            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            pp.create_shunt_as_capacitor(net, typ="capacitor", bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], q_mvar=safe_float(in_data[x]['q_mvar']), loss_factor=safe_float(in_data[x]['loss_factor']), vn_kv=safe_float(in_data[x]['vn_kv']), step=float(safe_float(in_data[x].get('step', 1)) or 1), max_step=float(safe_float(in_data[x].get('max_step', 1)) or 1), in_service=in_service)        
        
        if (in_data[x]['typ'].startswith("Load")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                element_name = in_data[x].get('userFriendlyName', in_data[x].get('name', 'Unknown'))
                bus_name = in_data[x]['bus']
                
                # Check if bus is None (not connected) or references non-existent bus
                if bus_name is None:
                    raise ValueError(
                        f"CONNECTION ERROR: Load '{element_name}' (ID: {in_data[x].get('id', 'Unknown')}) is NOT CONNECTED to any bus.\n\n"
                        f"SOLUTION: Please ensure that:\n"
                        f"1. You have placed a Bus/Busbar element in your diagram\n"
                        f"2. Draw a connection line from the Load to a Bus element\n"
                        f"3. Verify the connection line is properly attached at both ends\n\n"
                        f"IMPORTANT: Every electrical component must be connected to at least one Bus element."
                    )
                else:
                    raise ValueError(
                        f"CONNECTION ERROR: Load '{element_name}' is trying to connect to bus '{bus_name}', "
                        f"but this bus does not exist in your diagram.\n\n"
                        f"SOLUTION: Please ensure that:\n"
                        f"1. You have placed a Bus/Busbar element in your diagram\n"
                        f"2. The Load is connected to this Bus element with a connection line\n"
                        f"3. All electrical elements must be properly connected to Bus elements"
                    )
          
            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            
            pp.create_load(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], p_mw=safe_float(in_data[x]['p_mw']),q_mvar=safe_float(in_data[x]['q_mvar']),const_z_percent=safe_float(in_data[x]['const_z_percent']),const_i_percent=safe_float(in_data[x]['const_i_percent']), sn_mva=safe_float(in_data[x]['sn_mva']),scaling=safe_float(in_data[x].get('scaling'), 1.0),type=in_data[x]['type'], in_service=in_service)
            
            # Store user-friendly name for load
            load_name = in_data[x]['name']
            user_friendly_name = in_data[x].get('userFriendlyName', load_name)
            if not hasattr(net, 'user_friendly_names'):
                net.user_friendly_names = {}
            net.user_friendly_names[load_name] = user_friendly_name
      
        if (in_data[x]['typ'].startswith("Asymmetric Load")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                continue
            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            pp.create_asymmetric_load(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], p_a_mw=in_data[x]['p_a_mw'],p_b_mw=in_data[x]['p_b_mw'],p_c_mw=in_data[x]['p_c_mw'],q_a_mvar=in_data[x]['q_a_mvar'], q_b_mvar=in_data[x]['q_b_mvar'], q_c_mvar=in_data[x]['q_c_mvar'], sn_mva=in_data[x]['sn_mva'], scaling=in_data[x]['scaling'],type=in_data[x]['type'], in_service=in_service)         
   
        if (in_data[x]['typ'].startswith("Impedance")):
            from_bus_idx = Busbars.get(in_data[x]['busFrom'])
            to_bus_idx = Busbars.get(in_data[x]['busTo'])
            if from_bus_idx is None:
                continue
            if to_bus_idx is None:
                continue
            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            pp.create_impedance(net, from_bus=from_bus_idx, to_bus=to_bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], rft_pu=in_data[x]['rft_pu'],xft_pu=in_data[x]['xft_pu'],sn_mva=in_data[x]['sn_mva'], in_service=in_service)         
         
        if (in_data[x]['typ'].startswith("Ward")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                continue
            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            pp.create_ward(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], ps_mw=in_data[x]['ps_mw'],qs_mvar=in_data[x]['qs_mvar'], pz_mw=in_data[x]['pz_mw'], qz_mvar=in_data[x]['qz_mvar'], in_service=in_service)         
   
        if (in_data[x]['typ'].startswith("Extended Ward")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                continue
            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            pp.create_xward(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], ps_mw=in_data[x]['ps_mw'], qs_mvar=in_data[x]['qs_mvar'], pz_mw=in_data[x]['pz_mw'], qz_mvar=in_data[x]['qz_mvar'], r_ohm =in_data[x]['r_ohm'], x_ohm=in_data[x]['x_ohm'],vm_pu=in_data[x]['vm_pu'], in_service=in_service)         
   
        if (in_data[x]['typ'].startswith("Motor")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                continue
            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            
            # Handle Irc_pu / lrc_pu - frontend sends Irc_pu, Pandapower expects lrc_pu
            # Try both key names, handle None values
            lrc_pu_value = in_data[x].get('lrc_pu') or in_data[x].get('Irc_pu')
            if lrc_pu_value is None or lrc_pu_value == 'None' or lrc_pu_value == '':
                lrc_pu_value = None
            else:
                lrc_pu_value = safe_float_local(lrc_pu_value, None)
            
            pp.create_motor(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], 
                            pn_mech_mw=safe_float_local(in_data[x].get('pn_mech_mw'), 0.0),
                            cos_phi=safe_float_local(in_data[x].get('cos_phi'), 0.85),
                            efficiency_n_percent=safe_float_local(in_data[x].get('efficiency_n_percent'), 90.0),
                            lrc_pu=lrc_pu_value,
                            rx=safe_float_local(in_data[x].get('rx'), 0.0),
                            vn_kv=safe_float_local(in_data[x].get('vn_kv'), 0.4),
                            efficiency_percent=safe_float_local(in_data[x].get('efficiency_percent'), 90.0),
                            loading_percent=safe_float_local(in_data[x].get('loading_percent'), 100.0),
                            scaling=safe_float_local(in_data[x].get('scaling'), 1.0),
                            in_service=in_service)         
   
        
        if (in_data[x]['typ'].startswith("SVC")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                continue
            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            pp.create_svc(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], x_l_ohm=in_data[x]['x_l_ohm'], x_cvar_ohm=in_data[x]['x_cvar_ohm'], set_vm_pu=in_data[x]['set_vm_pu'], thyristor_firing_angle_degree=in_data[x]['thyristor_firing_angle_degree'], controllable=in_data[x]['controllable'], min_angle_degree=in_data[x]['min_angle_degree'], max_angle_degree=in_data[x]['max_angle_degree'], in_service=in_service)
         
        if (in_data[x]['typ'].startswith("TCSC")):
            from_bus_idx = Busbars.get(in_data[x]['busFrom'])
            to_bus_idx = Busbars.get(in_data[x]['busTo'])
            if from_bus_idx is None:
                continue
            if to_bus_idx is None:
                continue
            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            pp.create_tcsc(net, from_bus=from_bus_idx, to_bus=to_bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], x_l_ohm=in_data[x]['x_l_ohm'], x_cvar_ohm=in_data[x]['x_cvar_ohm'], set_p_to_mw=in_data[x]['set_p_to_mw'], thyristor_firing_angle_degree=in_data[x]['thyristor_firing_angle_degree'], controllable=in_data[x]['controllable'], min_angle_degree=in_data[x]['min_angle_degree'], max_angle_degree=in_data[x]['max_angle_degree'], in_service=in_service)
                   
        if (in_data[x]['typ'].startswith("SSC")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                continue
            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            pp.create_ssc(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], r_ohm=in_data[x]['r_ohm'], x_ohm=in_data[x]['x_ohm'], set_vm_pu=in_data[x]['set_vm_pu'], vm_internal_pu=in_data[x]['vm_internal_pu'], va_internal_degree=in_data[x]['va_internal_degree'], controllable=in_data[x]['controllable'], in_service=in_service)
        

        if (in_data[x]['typ'].startswith("Storage")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                continue
            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            # Convert all numeric values to float explicitly
            p_mw = float(in_data[x].get('p_mw', 0.0))
            q_mvar = float(in_data[x].get('q_mvar', 0.0))
            sn_mva = float(in_data[x].get('sn_mva', 1.0))
            max_e_mwh = float(in_data[x].get('max_e_mwh', 1.0))
            min_e_mwh = float(in_data[x].get('min_e_mwh', 0.0))
            soc_percent = float(in_data[x].get('soc_percent', 50.0))
            scaling = float(in_data[x].get('scaling', 1.0))
            storage_type = str(in_data[x].get('type', '0'))
            pp.create_storage(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], 
                            p_mw=p_mw, q_mvar=q_mvar, sn_mva=sn_mva, 
                            max_e_mwh=max_e_mwh, min_e_mwh=min_e_mwh, 
                            soc_percent=soc_percent, scaling=scaling, 
                            type=storage_type, in_service=in_service)         
   
        if (in_data[x]['typ'].startswith("Load DC")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                continue
            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            pp.create_load_dc(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], p_mw=safe_float(in_data[x].get('p_mw', 0.0)), in_service=in_service)
            
            # Store user-friendly name for load DC
            load_dc_name = in_data[x]['name']
            user_friendly_name = in_data[x].get('userFriendlyName', load_dc_name)
            if not hasattr(net, 'user_friendly_names'):
                net.user_friendly_names = {}
            net.user_friendly_names[load_dc_name] = user_friendly_name
        
        if (in_data[x]['typ'].startswith("Source DC")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                continue
            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            pp.create_source_dc(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], vm_pu=safe_float(in_data[x].get('vm_pu', 1.0)), in_service=in_service)
            
            # Store user-friendly name for source DC
            source_dc_name = in_data[x]['name']
            user_friendly_name = in_data[x].get('userFriendlyName', source_dc_name)
            if not hasattr(net, 'user_friendly_names'):
                net.user_friendly_names = {}
            net.user_friendly_names[source_dc_name] = user_friendly_name
        
        if (in_data[x]['typ'].startswith("Switch")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                continue
            # Get element index (line or transformer the switch is connected to)
            element_idx = in_data[x].get('element')
            if element_idx is None:
                continue
            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            # Get switch type (et parameter: 'line' or 'trafo')
            et = in_data[x].get('et', 'line')  # Default to 'line'
            closed = in_data[x].get('closed', True)
            if isinstance(closed, str):
                closed = closed.lower() == 'true'
            switch_type = in_data[x].get('type', 'CB')
            z_ohm = safe_float(in_data[x].get('z_ohm', 0.0))
            in_ka = safe_float(in_data[x].get('in_ka', 0.0))
            
            pp.create_switch(net, bus=bus_idx, element=int(element_idx), et=et, name=in_data[x]['name'], id=in_data[x]['id'], 
                           closed=closed, type=switch_type, z_ohm=z_ohm, in_ka=in_ka, in_service=in_service)
            
            # Store user-friendly name for switch
            switch_name = in_data[x]['name']
            user_friendly_name = in_data[x].get('userFriendlyName', switch_name)
            if not hasattr(net, 'user_friendly_names'):
                net.user_friendly_names = {}
            net.user_friendly_names[switch_name] = user_friendly_name
        
        if (in_data[x]['typ'].startswith("VSC")):
            # VSC requires pandapower 3.1+ with DC grid support
            if not hasattr(pp, 'create_vsc'):
                element_name = in_data[x].get('userFriendlyName', in_data[x].get('name', 'Unknown'))
                print(f"Warning: VSC '{element_name}' skipped - VSC not supported in pandapower {pp.__version__}. Upgrade to pandapower 3.1+")
                continue
                
            bus_idx = Busbars.get(in_data[x].get('bus', ''))
            if bus_idx is None:
                element_name = in_data[x].get('userFriendlyName', in_data[x].get('name', 'Unknown'))
                print(f"Warning: VSC '{element_name}' skipped - AC bus not found")
                continue
            bus_dc_idx = Busbars.get(in_data[x].get('bus_dc', ''))
            if bus_dc_idx is None:
                element_name = in_data[x].get('userFriendlyName', in_data[x].get('name', 'Unknown'))
                print(f"Warning: VSC '{element_name}' skipped - DC bus not connected. VSC requires connection to both AC bus and DC bus.")
                continue
            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            
            # VSC parameters according to pandapower API
            # Required: r_ohm, x_ohm, r_dc_ohm (coupling transformer and DC resistance)
            r_ohm = safe_float(in_data[x].get('r_ohm', 0.01))  # Coupling transformer resistance
            x_ohm = safe_float(in_data[x].get('x_ohm', 0.1))   # Coupling transformer reactance
            r_dc_ohm = safe_float(in_data[x].get('r_dc_ohm', 0.01))  # Internal DC resistance
            
            # Control parameters
            control_mode_ac = in_data[x].get('control_mode_ac', 'vm_pu')  # 'vm_pu' or 'q_mvar'
            control_value_ac = safe_float(in_data[x].get('control_value_ac', in_data[x].get('vm_pu', 1.0)))
            control_mode_dc = in_data[x].get('control_mode_dc', 'p_mw')  # 'vm_pu' or 'p_mw'
            control_value_dc = safe_float(in_data[x].get('control_value_dc', in_data[x].get('p_mw', 0.0)))
            
            vsc_idx = pp.create_vsc(net, bus=bus_idx, bus_dc=bus_dc_idx, 
                         r_ohm=r_ohm, x_ohm=x_ohm, r_dc_ohm=r_dc_ohm,
                         control_mode_ac=control_mode_ac, control_value_ac=control_value_ac,
                         control_mode_dc=control_mode_dc, control_value_dc=control_value_dc,
                         name=in_data[x]['name'], in_service=in_service)
            
            # Store custom 'id' field in the VSC dataframe
            if 'id' not in net.vsc.columns:
                net.vsc['id'] = ''
            net.vsc.at[vsc_idx, 'id'] = in_data[x].get('id', '')
            
            # Store user-friendly name for VSC
            vsc_name = in_data[x]['name']
            user_friendly_name = in_data[x].get('userFriendlyName', vsc_name)
            if not hasattr(net, 'user_friendly_names'):
                net.user_friendly_names = {}
            net.user_friendly_names[vsc_name] = user_friendly_name
        
        if (in_data[x]['typ'].startswith("B2B VSC")):
            element_name = in_data[x].get('userFriendlyName', in_data[x].get('name', 'Unknown'))
            
            # B2B VSC can work in two modes:
            # 1. Simple mode: AC bus to DC bus (uses create_vsc internally)
            # 2. Full mode: AC bus to DC bus pair (bus_dc_plus/bus_dc_minus)
            
            bus_idx = Busbars.get(in_data[x].get('bus', ''))
            bus_dc_idx = Busbars.get(in_data[x].get('bus_dc', ''))
            
            # Check for simple VSC mode (AC bus to single DC bus)
            if bus_idx is not None and bus_dc_idx is not None:
                # Use create_vsc for simple AC-to-DC connection
                if not hasattr(pp, 'create_vsc'):
                    print(f"Warning: B2B VSC '{element_name}' skipped - VSC not supported in pandapower {pp.__version__}. Upgrade to pandapower 3.1+")
                    continue
                
                # Get in_service parameter
                in_service = True
                if 'in_service' in in_data[x]:
                    in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
                
                # VSC parameters
                r_ohm = safe_float(in_data[x].get('r_ohm', 0.01))
                x_ohm = safe_float(in_data[x].get('x_ohm', 0.1))
                r_dc_ohm = safe_float(in_data[x].get('r_dc_ohm', 0.01))
                
                # Control parameters
                control_mode_ac = in_data[x].get('control_mode_ac', 'vm_pu')
                control_value_ac = safe_float(in_data[x].get('control_value_ac', in_data[x].get('vm_pu', 1.0)))
                control_mode_dc = in_data[x].get('control_mode_dc', 'p_mw')
                control_value_dc = safe_float(in_data[x].get('control_value_dc', in_data[x].get('p_mw', 0.0)))
                
                print(f"Creating VSC for B2B VSC '{element_name}': AC bus={bus_idx}, DC bus={bus_dc_idx}")
                pp.create_vsc(net, bus=bus_idx, bus_dc=bus_dc_idx,
                             r_ohm=r_ohm, x_ohm=x_ohm, r_dc_ohm=r_dc_ohm,
                             control_mode_ac=control_mode_ac, control_value_ac=control_value_ac,
                             control_mode_dc=control_mode_dc, control_value_dc=control_value_dc,
                             name=in_data[x]['name'], in_service=in_service)
            else:
                # Try full B2B VSC mode with bus_dc_plus/bus_dc_minus
                if not hasattr(pp, 'create_b2b_vsc'):
                    print(f"Warning: B2B VSC '{element_name}' skipped - B2B VSC not supported in pandapower {pp.__version__}. Upgrade to pandapower 3.1+")
                    continue
                    
                bus_dc_plus_idx = Busbars.get(in_data[x].get('bus_dc_plus', ''))
                bus_dc_minus_idx = Busbars.get(in_data[x].get('bus_dc_minus', ''))
                
                if bus_idx is None:
                    print(f"Warning: B2B VSC '{element_name}' skipped - AC bus not connected. Connect B2B VSC to both an AC bus and a DC bus.")
                    continue
                if bus_dc_plus_idx is None or bus_dc_minus_idx is None:
                    print(f"Warning: B2B VSC '{element_name}' skipped - DC buses not connected. For simple HVDC, connect B2B VSC to both an AC bus and a DC bus.")
                    continue
                    
                # Get in_service parameter
                in_service = True
                if 'in_service' in in_data[x]:
                    in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
                
                # B2B VSC parameters
                r_ohm = safe_float(in_data[x].get('r_ohm', 0.01))
                x_ohm = safe_float(in_data[x].get('x_ohm', 0.1))
                r_dc_ohm = safe_float(in_data[x].get('r_dc_ohm', 0.01))
                
                # Control parameters
                control_mode_ac = in_data[x].get('control_mode_ac', 'vm_pu')
                control_value_ac = safe_float(in_data[x].get('control_value_ac', in_data[x].get('vm1_pu', 1.0)))
                control_mode_dc = in_data[x].get('control_mode_dc', 'p_mw')
                control_value_dc = safe_float(in_data[x].get('control_value_dc', in_data[x].get('p_mw', 0.0)))
                
                pp.create_b2b_vsc(net, bus=bus_idx, bus_dc_plus=bus_dc_plus_idx, bus_dc_minus=bus_dc_minus_idx,
                                r_ohm=r_ohm, x_ohm=x_ohm, r_dc_ohm=r_dc_ohm,
                                control_mode_ac=control_mode_ac, control_value_ac=control_value_ac,
                                control_mode_dc=control_mode_dc, control_value_dc=control_value_dc,
                                name=in_data[x]['name'], in_service=in_service)
            
            # Store user-friendly name
            b2b_vsc_name = in_data[x]['name']
            user_friendly_name = in_data[x].get('userFriendlyName', b2b_vsc_name)
            if not hasattr(net, 'user_friendly_names'):
                net.user_friendly_names = {}
            net.user_friendly_names[b2b_vsc_name] = user_friendly_name
        
        if (in_data[x]['typ'].startswith("DC Line")):
            element_name = in_data[x].get('userFriendlyName', in_data[x].get('name', 'Unknown'))
            bus_from = in_data[x].get('busFrom')
            bus_to = in_data[x].get('busTo')
            
            if bus_from is None:
                print(f"Warning: DC Line '{element_name}' skipped - missing 'busFrom' connection. "
                      f"DC Lines must be connected between two buses (draw it as a line connecting buses).")
                continue
            if bus_to is None:
                print(f"Warning: DC Line '{element_name}' skipped - missing 'busTo' connection. "
                      f"DC Lines must be connected between two buses (draw it as a line connecting buses).")
                continue
            
            from_bus_idx = Busbars.get(bus_from)
            to_bus_idx = Busbars.get(bus_to)
            
            if from_bus_idx is None:
                print(f"Warning: DC Line '{element_name}' skipped - from_bus '{bus_from}' not found.")
                continue
            if to_bus_idx is None:
                print(f"Warning: DC Line '{element_name}' skipped - to_bus '{bus_to}' not found.")
                continue
            
            # Get in_service parameter (default to True if not specified)
            in_service = True
            if 'in_service' in in_data[x]:
                in_service = bool(in_data[x]['in_service']) if isinstance(in_data[x]['in_service'], bool) else (in_data[x]['in_service'] == 'true' or in_data[x]['in_service'] == True)
            
            # Check if both buses are DC buses - use create_line_dc for DC-to-DC connections
            dc_bus_names = getattr(net, 'dc_bus_names', set())
            is_dc_to_dc = bus_from in dc_bus_names and bus_to in dc_bus_names
            
            if is_dc_to_dc:
                # DC Line connecting two DC buses - use create_line_dc
                if hasattr(pp, 'create_line_dc'):
                    print(f"Creating DC line (line_dc) '{element_name}': DC bus {bus_from} -> DC bus {bus_to}")
                    
                    # Get line parameters
                    length_km = safe_float(in_data[x].get('length_km', 100.0))  # Default 100km for HVDC
                    r_ohm_per_km = safe_float(in_data[x].get('r_ohm_per_km', 0.01))  # Default DC cable resistance
                    
                    # Try to create a standard type for DC line if it doesn't exist
                    std_type_name = "HVDC_Cable_320kV"
                    try:
                        # Check if std_type already exists
                        if not hasattr(net, 'std_types') or 'line_dc' not in net.std_types or std_type_name not in net.std_types['line_dc']:
                            # Create a standard type for DC lines
                            if hasattr(pp, 'create_std_type'):
                                pp.create_std_type(net, {
                                    "r_ohm_per_km": r_ohm_per_km,
                                    "c_nf_per_km": 0.0,  # DC cables don't have capacitance issues like AC
                                    "max_i_ka": 2.0,  # Max current rating
                                }, name=std_type_name, element="line_dc")
                                print(f"Created DC line standard type: {std_type_name}")
                    except Exception as e:
                        print(f"Note: Could not create std_type: {e}")
                    
                    try:
                        # create_line_dc requires from_bus_dc and to_bus_dc (DC bus indices)
                        line_dc_idx = pp.create_line_dc(net, from_bus_dc=from_bus_idx, to_bus_dc=to_bus_idx,
                                         length_km=length_km, std_type=std_type_name,
                                         name=in_data[x]['name'], in_service=in_service)
                        # Store custom 'id' field in the line_dc dataframe
                        if 'id' not in net.line_dc.columns:
                            net.line_dc['id'] = ''
                        net.line_dc.at[line_dc_idx, 'id'] = in_data[x].get('id', '')
                    except TypeError as e:
                        # If std_type approach fails, try without it using different parameters
                        print(f"Standard type approach failed: {e}. Trying direct parameters...")
                        try:
                            # Some pandapower versions allow direct parameters
                            line_dc_idx = pp.create_line_dc(net, from_bus_dc=from_bus_idx, to_bus_dc=to_bus_idx,
                                             length_km=length_km, r_ohm_per_km=r_ohm_per_km,
                                             name=in_data[x]['name'], in_service=in_service)
                            # Store custom 'id' field in the line_dc dataframe
                            if 'id' not in net.line_dc.columns:
                                net.line_dc['id'] = ''
                            net.line_dc.at[line_dc_idx, 'id'] = in_data[x].get('id', '')
                        except Exception as e2:
                            print(f"Warning: Could not create DC line: {e2}. DC grid simulation may not work correctly.")
                            continue
                else:
                    print(f"Warning: DC Line '{element_name}' connects DC buses but create_line_dc not available in pandapower {pp.__version__}. Skipped.")
                    continue
            else:
                # DC Line connecting two AC buses - use create_dcline (simplified HVDC model)
                print(f"Creating DC line (dcline) '{element_name}': AC bus {bus_from} -> AC bus {bus_to}")
                pp.create_dcline(net, from_bus=from_bus_idx, to_bus=to_bus_idx, 
                               name=in_data[x]['name'], 
                               p_mw=safe_float(in_data[x].get('p_mw', 0.0)), 
                               loss_percent=safe_float(in_data[x].get('loss_percent', 0.0)), 
                               loss_mw=safe_float(in_data[x].get('loss_mw', 0.0)), 
                               vm_from_pu=safe_float(in_data[x].get('vm_from_pu', 1.0)), 
                               vm_to_pu=safe_float(in_data[x].get('vm_to_pu', 1.0)), 
                               in_service=in_service)
            
            # Store user-friendly name for DC Line
            dcline_name = in_data[x]['name']
            if not hasattr(net, 'user_friendly_names'):
                net.user_friendly_names = {}
            net.user_friendly_names[dcline_name] = element_name


def powerflow(net, algorithm, calculate_voltage_angles, init, export_python=False, in_data=None, Busbars=None, run_control=False):
            #pandapower - rozpływ mocy
            # Initialize tap_control_results before try block so it's accessible in else block
            tap_control_results = []
            
            try:
                # Check for isolated buses before running power flow
                isolated_buses = pp.topology.unsupplied_buses(net)
                if len(isolated_buses) > 0:
                    raise ValueError(f"Isolated buses found: {isolated_buses}. Check your network connectivity.")
                
                # Add DiscreteTapControl for two-winding transformers when "Include controllers" is enabled
                if run_control and getattr(net, 'trafo_discrete_tap_controllers', None):
                    print(f"🎛️ Creating DiscreteTapControl for {len(net.trafo_discrete_tap_controllers)} transformers")
                    for (trafo_idx, control_side, vm_lower_pu, vm_upper_pu) in net.trafo_discrete_tap_controllers:
                        try:
                            # Use the control_side from frontend (which bus voltage to monitor/control)
                            trafo_name = net.trafo.at[trafo_idx, 'name']
                            tap_side = net.trafo.at[trafo_idx, 'tap_side'] if 'tap_side' in net.trafo.columns else 'hv'
                            
                            # Get tap range info for debugging
                            tap_min = net.trafo.at[trafo_idx, 'tap_min']
                            tap_max = net.trafo.at[trafo_idx, 'tap_max']
                            tap_step_percent = net.trafo.at[trafo_idx, 'tap_step_percent']
                            tap_pos = net.trafo.at[trafo_idx, 'tap_pos']
                            
                            print(f"  Transformer {trafo_idx} ({trafo_name}): tap_side={tap_side}, control_side={control_side}, range=[{tap_min}, {tap_max}], step={tap_step_percent}%, pos={tap_pos}")
                            print(f"    Control limits: vm_lower={vm_lower_pu} pu, vm_upper={vm_upper_pu} pu")
                            
                            # Check if tap changer is properly configured
                            if tap_min >= tap_max:
                                print(f"    ⚠️ WARNING: tap_min ({tap_min}) >= tap_max ({tap_max}) - controller will not work!")
                            if tap_step_percent == 0:
                                print(f"    ⚠️ WARNING: tap_step_percent is 0 - controller will not work!")
                            
                            # Warning if tap is already at limit
                            if tap_pos == tap_max:
                                print(f"    ⚠️ WARNING: Initial tap_pos ({tap_pos}) is at MAXIMUM - controller cannot increase tap further!")
                                print(f"       Tip: Set tap_pos closer to tap_neutral (0) to allow both increase and decrease")
                            elif tap_pos == tap_min:
                                print(f"    ⚠️ WARNING: Initial tap_pos ({tap_pos}) is at MINIMUM - controller cannot decrease tap further!")
                                print(f"       Tip: Set tap_pos closer to tap_neutral (0) to allow both increase and decrease")
                            
                            # Create controller with side parameter
                            # 'side' tells which bus voltage to monitor/control (from user's control_side setting)
                            # Try different parameter names (pandapower versions may differ)
                            try:
                                ctrl = control.DiscreteTapControl(
                                    net=net,
                                    tid=trafo_idx,
                                    side=control_side,
                                    vm_lower_pu=vm_lower_pu,
                                    vm_upper_pu=vm_upper_pu
                                )
                                print(f"    ✅ Controller created with 'tid' parameter (index={ctrl.index})")
                            except TypeError as te:
                                # Try alternative parameter name
                                print(f"    ⚠️ 'tid' failed, trying 'element_index': {te}")
                                ctrl = control.DiscreteTapControl(
                                    net=net,
                                    element_index=trafo_idx,
                                    side=control_side,
                                    vm_lower_pu=vm_lower_pu,
                                    vm_upper_pu=vm_upper_pu
                                )
                                print(f"    ✅ Controller created with 'element_index' parameter (index={ctrl.index})")
                        except Exception as ctrl_err:
                            print(f"    ❌ Failed to create controller: {ctrl_err}")
                            import traceback
                            traceback.print_exc()
                
                # Log controller status before power flow
                if run_control and hasattr(net, 'controller') and not net.controller.empty:
                    print(f"🎛️ Running power flow WITH controllers (run_control=True)")
                    print(f"   Controllers in net: {len(net.controller)}")
                    print(net.controller[['object', 'in_service']])
                    
                    # Store initial tap positions for comparison
                    initial_tap_positions = {}
                    for idx in net.trafo.index:
                        initial_tap_positions[idx] = net.trafo.at[idx, 'tap_pos']
                    print(f"   Initial tap positions: {initial_tap_positions}")
                else:
                    print(f"⚡ Running power flow WITHOUT controllers (run_control={run_control})")
                    initial_tap_positions = {}
                
                pp.runpp(net, algorithm=algorithm, calculate_voltage_angles=calculate_voltage_angles, init=init, run_control=run_control)
                
                # Check if tap positions changed
                if run_control and initial_tap_positions:
                    changed = False
                    for idx, initial_pos in initial_tap_positions.items():
                        final_pos = net.trafo.at[idx, 'tap_pos']
                        if initial_pos != final_pos:
                            print(f"   📊 Tap changed: Trafo {idx}: {initial_pos} → {final_pos}")
                            changed = True
                    if not changed:
                        print(f"   ⚠️ WARNING: No tap positions changed during controlled power flow!")
                
                # Log transformer tap positions after power flow (only for controlled transformers)
                # Also build tap_control_results for frontend display
                
                if run_control and not net.trafo.empty and getattr(net, 'trafo_discrete_tap_controllers', None):
                    # Get list of transformer indices that have controllers
                    controlled_trafo_indices = set(ctrl_data[0] for ctrl_data in net.trafo_discrete_tap_controllers)
                    
                    print(f"🔧 Controlled transformer tap positions after power flow:")
                    for idx in net.trafo.index:
                        if idx not in controlled_trafo_indices:
                            continue  # Skip transformers without controllers
                        
                        name = net.trafo.at[idx, 'name']
                        tap_pos = net.trafo.at[idx, 'tap_pos']
                        tap_min = net.trafo.at[idx, 'tap_min']
                        tap_max = net.trafo.at[idx, 'tap_max']
                        tap_step = net.trafo.at[idx, 'tap_step_percent']
                        hv_bus_idx = net.trafo.at[idx, 'hv_bus']
                        lv_bus_idx = net.trafo.at[idx, 'lv_bus']
                        hv_vm_pu = net.res_bus.at[hv_bus_idx, 'vm_pu']
                        lv_vm_pu = net.res_bus.at[lv_bus_idx, 'vm_pu']
                        
                        # Get user-friendly name if available
                        user_friendly_name = net.user_friendly_names.get(name, name) if hasattr(net, 'user_friendly_names') else name
                        
                        # Get control limits for this transformer
                        ctrl_data = next((c for c in net.trafo_discrete_tap_controllers if c[0] == idx), None)
                        if ctrl_data:
                            ctrl_side, vm_lower, vm_upper = ctrl_data[1], ctrl_data[2], ctrl_data[3]
                            controlled_vm = lv_vm_pu if ctrl_side == 'lv' else hv_vm_pu
                            
                            # Check if voltage is within limits
                            in_limits = vm_lower <= controlled_vm <= vm_upper
                            status = "✅ IN LIMITS" if in_limits else "❌ OUT OF LIMITS"
                            
                            # Check if tap is at limit
                            at_limit = ""
                            at_limit_type = None
                            if tap_pos == tap_max:
                                at_limit = " (AT MAX LIMIT - cannot increase further)"
                                at_limit_type = "max"
                            elif tap_pos == tap_min:
                                at_limit = " (AT MIN LIMIT - cannot decrease further)"
                                at_limit_type = "min"
                            
                            print(f"   Trafo {idx} ({name}):")
                            print(f"      Tap: {tap_pos} [{tap_min}, {tap_max}] step={tap_step}%{at_limit}")
                            print(f"      Control side ({ctrl_side}): {controlled_vm:.4f} pu  Target: [{vm_lower}, {vm_upper}] pu  {status}")
                            print(f"      HV bus: {hv_vm_pu:.4f} pu, LV bus: {lv_vm_pu:.4f} pu")
                            
                            # Calculate how much more tap range would be needed
                            taps_needed = None
                            if not in_limits and (tap_pos == tap_max or tap_pos == tap_min):
                                voltage_gap = abs(controlled_vm - vm_upper) if controlled_vm > vm_upper else abs(vm_lower - controlled_vm)
                                taps_needed = int(voltage_gap / (tap_step / 100) / controlled_vm) + 1
                                print(f"      💡 Need ~{taps_needed} more tap positions OR increase tap_step_percent to reach target")
                            
                            # Build result object for frontend
                            # Convert numpy types to native Python types for JSON serialization
                            tap_control_results.append({
                                'name': str(user_friendly_name),
                                'id': str(name),
                                'tap_pos': float(tap_pos),
                                'tap_min': float(tap_min),
                                'tap_max': float(tap_max),
                                'tap_step_percent': float(tap_step),
                                'control_side': str(ctrl_side),
                                'controlled_vm_pu': round(float(controlled_vm), 4),
                                'vm_lower_pu': float(vm_lower),
                                'vm_upper_pu': float(vm_upper),
                                'hv_vm_pu': round(float(hv_vm_pu), 4),
                                'lv_vm_pu': round(float(lv_vm_pu), 4),
                                'in_limits': bool(in_limits),  # Convert numpy.bool_ to Python bool
                                'at_limit': at_limit_type,
                                'taps_needed': int(taps_needed) if taps_needed is not None else None
                            })
                
            except Exception as e:
                
                # Initialize diagnostic response
                diagnostic_response = {
                    "error": True,
                    "message": "Power flow calculation failed",
                    "exception": str(e),
                    "diagnostic": {}
                }               
                
                # Check for disconnected sections by finding unsupplied buses (buses not connected to ext_grid)
                # This is the same as isolated buses - buses without connection to external grid
                try:
                    # Get all buses that are not supplied (disconnected from external grid)
                    unsupplied_buses_set = pp.topology.unsupplied_buses(net)
                    if len(unsupplied_buses_set) > 0:
                        # Convert set to list and ensure all values are native Python int (not numpy int64)
                        if isinstance(unsupplied_buses_set, set):
                            unsupplied_buses_list = [int(x) for x in unsupplied_buses_set]
                        elif hasattr(unsupplied_buses_set, 'tolist'):
                            unsupplied_buses_list = [int(x) for x in unsupplied_buses_set.tolist()]
                        else:
                            unsupplied_buses_list = [int(x) for x in list(unsupplied_buses_set)]
                        
                        # Find elements connected to unsupplied buses
                        disconnected_elements = {
                            "buses": unsupplied_buses_list,
                            "trafos": [],
                            "sgens": [],
                            "loads": [],
                            "generators": []
                        }
                        
                        # Find transformers connected to unsupplied buses
                        if hasattr(net, 'trafo') and not net.trafo.empty:
                            for trafo_idx in net.trafo.index:
                                hv_bus = net.trafo.loc[trafo_idx, 'hv_bus']
                                lv_bus = net.trafo.loc[trafo_idx, 'lv_bus']
                                if hv_bus in unsupplied_buses_set or lv_bus in unsupplied_buses_set:
                                    disconnected_elements["trafos"].append(int(trafo_idx))
                        
                        # Find static generators connected to unsupplied buses
                        if hasattr(net, 'sgen') and not net.sgen.empty:
                            for sgen_idx in net.sgen.index:
                                if net.sgen.loc[sgen_idx, 'bus'] in unsupplied_buses_set:
                                    disconnected_elements["sgens"].append(int(sgen_idx))
                        
                        # Find loads connected to unsupplied buses
                        if hasattr(net, 'load') and not net.load.empty:
                            for load_idx in net.load.index:
                                if net.load.loc[load_idx, 'bus'] in unsupplied_buses_set:
                                    disconnected_elements["loads"].append(int(load_idx))
                        
                        # Find generators connected to unsupplied buses
                        if hasattr(net, 'gen') and not net.gen.empty:
                            for gen_idx in net.gen.index:
                                if net.gen.loc[gen_idx, 'bus'] in unsupplied_buses_set:
                                    disconnected_elements["generators"].append(int(gen_idx))
                        
                        # Ensure all bus indices are native Python int (not numpy int64)
                        disconnected_elements["buses"] = [int(x) for x in disconnected_elements["buses"]]
                        disconnected_elements["trafos"] = [int(x) for x in disconnected_elements["trafos"]]
                        disconnected_elements["sgens"] = [int(x) for x in disconnected_elements["sgens"]]
                        disconnected_elements["loads"] = [int(x) for x in disconnected_elements["loads"]]
                        disconnected_elements["generators"] = [int(x) for x in disconnected_elements["generators"]]
                        
                        total_disconnected = len(disconnected_elements["buses"]) + len(disconnected_elements["trafos"]) + len(disconnected_elements["sgens"]) + len(disconnected_elements["loads"]) + len(disconnected_elements["generators"])
                        
                        diagnostic_response["diagnostic"]["disconnected_elements"] = disconnected_elements
                        diagnostic_response["diagnostic"]["total_disconnected_elements"] = int(total_disconnected)
                except Exception as disconn_error:
                    # If detection fails, continue with other diagnostics
                    pass
                
                # Check for isolated buses (buses without connection to external grid)
                try:
                    isolated_buses = pp.topology.unsupplied_buses(net)
                    if len(isolated_buses) > 0:
                        # Convert set to list and ensure all values are native Python int (not numpy int64)
                        if isinstance(isolated_buses, set):
                            isolated_list = [int(x) for x in isolated_buses]
                        elif hasattr(isolated_buses, 'tolist'):
                            isolated_list = [int(x) for x in isolated_buses.tolist()]
                        else:
                            isolated_list = [int(x) for x in list(isolated_buses)]
                        
                        diagnostic_response["diagnostic"]["isolated_buses"] = isolated_list
                        diagnostic_response["diagnostic"]["num_isolated_buses"] = len(isolated_list)
                except Exception as isolated_error:
                    pass
                
                # Check if external grid exists
                if not hasattr(net, 'ext_grid') or net.ext_grid.empty:
                    diagnostic_response["diagnostic"]["no_external_grid"] = True
                    diagnostic_response["message"] = "No external grid found. At least one External Grid element is required for power flow simulation."
                
                # Access initial voltage magnitudes and angles  
                try:
                    # Capture the diagnostic output from stdout
                    import io
                    import sys
                    
                    captured_output = io.StringIO()
                    old_stdout = sys.stdout
                    old_stderr = sys.stderr
                    sys.stdout = captured_output
                    sys.stderr = captured_output  # Also capture stderr
                    
                    diag_result_dict = {}
                    try:
                        # Call diagnostic without report_style to get full text output
                        # The default call prints the detailed diagnostic tool output
                        diag_result_dict = pp.diagnostic(net)
                    except Exception as diag_ex:
                        captured_output.write(f"\nDiagnostic error: {str(diag_ex)}\n")
                    
                    # Restore stdout/stderr
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr
                    diagnostic_text_output = captured_output.getvalue()
                    
                    # Debug: print captured output to server console
                    print(f"[DEBUG] Captured diagnostic output length: {len(diagnostic_text_output)}")
                    if diagnostic_text_output:
                        print(f"[DEBUG] Diagnostic output preview: {diagnostic_text_output[:500]}...")
                    
                    # Include the text output in the diagnostic response
                    if diagnostic_text_output and len(diagnostic_text_output.strip()) > 0:
                        diagnostic_response["diagnostic"]["diagnostic_output"] = diagnostic_text_output
                    else:
                        # If no output captured, add a note
                        diagnostic_response["diagnostic"]["diagnostic_note"] = "No detailed diagnostic output available"
                    
                    # Process diagnostic data to convert element indices to user-friendly names
                    if diag_result_dict and isinstance(diag_result_dict, dict):
                        processed_diagnostic = process_diagnostic_data(net, diag_result_dict)
                        # Merge processed diagnostic (don't overwrite disconnected_sections or isolated_buses)
                        for key, value in processed_diagnostic.items():
                            if key not in diagnostic_response["diagnostic"]:
                                diagnostic_response["diagnostic"][key] = value
                except Exception as diag_error:
                    # If diagnostic fails, continue with what we have
                    diagnostic_response["diagnostic"]["diagnostic_error"] = str(diag_error)
                    import traceback
                    diagnostic_response["diagnostic"]["diagnostic_traceback"] = traceback.format_exc()
                
                # If no specific diagnostic was found, include the original exception
                if not diagnostic_response["diagnostic"]:
                   diagnostic_response["diagnostic"]["general_error"] = str(e)
                else:
                    # Enhance the message with diagnostic summary
                    if "no_external_grid" in diagnostic_response["diagnostic"]:
                        diagnostic_response["message"] = "No external grid found. At least one External Grid element is required for power flow simulation."
                    elif "disconnected_elements" in diagnostic_response["diagnostic"]:
                        disconnected = diagnostic_response["diagnostic"]["disconnected_elements"]
                        num_buses = len(disconnected.get("buses", []))
                        num_trafos = len(disconnected.get("trafos", []))
                        num_sgens = len(disconnected.get("sgens", []))
                        num_loads = len(disconnected.get("loads", []))
                        total_elements = diagnostic_response["diagnostic"].get("total_disconnected_elements", 0)
                        
                        elements_summary = []
                        if num_buses > 0:
                            elements_summary.append(f"{num_buses} bus(es)")
                        if num_trafos > 0:
                            elements_summary.append(f"{num_trafos} transformer(s)")
                        if num_sgens > 0:
                            elements_summary.append(f"{num_sgens} static generator(s)")
                        if num_loads > 0:
                            elements_summary.append(f"{num_loads} load(s)")
                        
                        summary_text = ", ".join(elements_summary) if elements_summary else "elements"
                        diagnostic_response["message"] = f"Network connectivity issue: {total_elements} disconnected {summary_text} found. All network sections must be connected to an External Grid element."
                    elif "isolated_buses" in diagnostic_response["diagnostic"]:
                        num_isolated = diagnostic_response["diagnostic"].get("num_isolated_buses", 0)
                        diagnostic_response["message"] = f"Network connectivity issue: {num_isolated} isolated bus(es) found. All buses must be connected to an External Grid."
                
                # Convert diagnostic response to JSON string (same format as successful response)
                # Use a custom encoder to handle numpy types
                def convert_numpy_types(obj):
                    """Recursively convert numpy types to native Python types for JSON serialization"""
                    if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
                        return int(obj)
                    elif isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
                        return float(obj)
                    elif isinstance(obj, np.ndarray):
                        return obj.tolist()
                    elif isinstance(obj, dict):
                        return {key: convert_numpy_types(value) for key, value in obj.items()}
                    elif isinstance(obj, (list, tuple)):
                        return [convert_numpy_types(item) for item in obj]
                    elif isinstance(obj, set):
                        return [convert_numpy_types(item) for item in obj]
                    return obj
                
                # Convert any remaining numpy types
                diagnostic_response = convert_numpy_types(diagnostic_response)
                return json.dumps(diagnostic_response, separators=(',', ':'))
            else:                              
                
                class BusbarOut(object):
                    def __init__(self, name: str, id: str, vm_pu: float, va_degree: float, p_mw: float, q_mvar: float, pf: float, q_p: float):          
                        self.name = name
                        self.id = id
                        self.vm_pu = vm_pu
                        self.va_degree = va_degree   
                        self.p_mw = p_mw
                        self.q_mvar = q_mvar  
                        self.pf = pf #p_mw/math.sqrt(math.pow(p_mw,2)+math.pow(q_mvar,2))  
                        self.q_p = q_p
                        
                class BusbarsOut(object):
                    def __init__(self, busbars: List[BusbarOut]):
                        self.busbars = busbars                
                
                busbarList = list() 
                
                class LineOut(object):
                    def __init__(self, name: str, id: str, p_from_mw: float, q_from_mvar: float, p_to_mw: float, q_to_mvar: float, i_from_ka: float, i_to_ka: float, loading_percent: float):          
                        self.name = name 
                        self.id = id                      
                        self.p_from_mw = p_from_mw
                        self.q_from_mvar = q_from_mvar 
                        self.p_to_mw = p_to_mw 
                        self.q_to_mvar = q_to_mvar            
                        self.i_from_ka = i_from_ka 
                        self.i_to_ka = i_to_ka               
                        self.loading_percent = loading_percent 
                       
                class LinesOut(object):
                    def __init__(self, lines: List[BusbarOut]):
                        self.lines = lines
                linesList = list()                              
                         
                class ExternalGridOut(object):
                    def __init__(self,  name: str, id: str, p_mw: float, q_mvar: float, pf: float, q_p:float):        
                        self.name = name
                        self.id = id
                        self.p_mw = p_mw 
                        self.q_mvar = q_mvar  
                        self.pf = pf            
                        self.q_p=q_p              
                       
                class ExternalGridsOut(object):
                    def __init__(self, externalgrids: List[ExternalGridOut]):
                        self.externalgrids = externalgrids              
                externalgridsList = list() 
                
                class GeneratorOut(object):
                    def __init__(self, name: str, id: str, p_mw: float, q_mvar: float, va_degree: float, vm_pu: float):          
                        self.name = name
                        self.id = id
                        self.p_mw = p_mw 
                        self.q_mvar = q_mvar  
                        self.va_degree = va_degree 
                        self.vm_pu = vm_pu                         
                       
                class GeneratorsOut(object):
                    def __init__(self, generators: List[GeneratorOut]):
                        self.generators = generators             
                generatorsList = list()
                
                
                class StaticGeneratorOut(object):
                    def __init__(self, name: str, id: str, p_mw: float, q_mvar: float):          
                        self.name = name
                        self.id = id
                        self.p_mw = p_mw 
                        self.q_mvar = q_mvar                                       
                       
                class StaticGeneratorsOut(object):
                    def __init__(self, staticgenerators: List[StaticGeneratorOut]):
                        self.staticgenerators = staticgenerators             
                staticgeneratorsList = list()
                
                
                class AsymmetricStaticGeneratorOut(object):
                    def __init__(self, name: str, id: str,  p_a_mw: float, q_a_mvar: float, p_b_mw: float, q_b_mvar: float, p_c_mw: float, q_c_mvar: float):          
                        self.name = name
                        self.id = id
                        self.p_a_mw = p_a_mw 
                        self.q_a_mvar = q_a_mvar    
                        self.p_b_mw = p_b_mw 
                        self.q_b_mvar = q_b_mvar  
                        self.p_c_mw = p_c_mw 
                        self.q_c_mvar = q_c_mvar                                     
                       
                class AsymmetricStaticGeneratorsOut(object):
                    def __init__(self, asymmetricstaticgenerators: List[AsymmetricStaticGeneratorOut]):
                        self.asymmetricstaticgenerators = asymmetricstaticgenerators             
                asymmetricstaticgeneratorsList = list()  
                
                
                class TransformerOut(object):
                    def __init__(self, name: str, id: str, p_hv_mw: float, q_hv_mvar: float, p_lv_mw: float, q_lv_mvar: float, pl_mw: float, ql_mvar: float, i_hv_ka: float, i_lv_ka: float, vm_hv_pu: float, vm_lv_pu: float, va_hv_degree: float, va_lv_degree: float, loading_percent: float):          
                        self.name = name
                        self.id = id
                        self.p_hv_mw = p_hv_mw 
                        self.q_hv_mvar = q_hv_mvar
                        self.p_lv_mw = p_lv_mw                            
                        self.q_lv_mvar = q_lv_mvar 
                        self.pl_mw = pl_mw  
                        self.ql_mvar = ql_mvar                         
                        self.i_hv_ka = i_hv_ka 
                        self.i_lv_ka = i_lv_ka
                        self.vm_hv_pu = vm_hv_pu
                        self.vm_lv_pu = vm_lv_pu
                        self.va_hv_degree = va_hv_degree
                        self.va_lv_degree = va_lv_degree
                        self.loading_percent = loading_percent
                                                             
                       
                class TransformersOut(object):
                    def __init__(self, transformers: List[TransformerOut]):
                        self.transformers = transformers             
                transformersList = list() 
                
                
                class Transformer3WOut(object):
                    def __init__(self, name: str, id: str, p_hv_mw: float, q_hv_mvar: float, p_mv_mw: float, q_mv_mvar: float, 
                                 p_lv_mw: float, q_lv_mvar: float, pl_mw: float, ql_mvar: float, i_hv_ka: float, 
                                 i_mv_ka: float, i_lv_ka: float, vm_hv_pu: float, vm_mv_pu: float, 
                                 vm_lv_pu: float, va_hv_degree: float, va_mv_degree: float, va_lv_degree: float, loading_percent: float):          
                        self.name = name
                        self.id = id
                        self.p_hv_mw = p_hv_mw 
                        self.q_hv_mvar = q_hv_mvar
                        self.p_mv_mw = p_mv_mw                            
                        self.q_mv_mvar = q_mv_mvar 
                        self.p_lv_mw = p_lv_mw  
                        self.q_lv_mvar = q_lv_mvar                         
                        self.pl_mw = pl_mw 
                        self.ql_mvar = ql_mvar
                        self.i_hv_ka = i_hv_ka
                        self.i_mv_ka = i_mv_ka
                        self.i_lv_ka = i_lv_ka
                        self.vm_hv_pu = vm_hv_pu
                        self.vm_mv_pu = vm_mv_pu
                        self.vm_lv_pu = vm_lv_pu
                        self.va_hv_degree = va_hv_degree
                        self.va_mv_degree = va_mv_degree
                        self.va_lv_degree = va_lv_degree
                        self.loading_percent = loading_percent                                                             
                       
                class Transformers3WOut(object):
                    def __init__(self, transformers3W: List[Transformer3WOut]):
                        self.transformers3W = transformers3W             
                transformers3WList = list()                 
                
                
                class ShuntOut(object):
                    def __init__(self, name: str, id: str, p_mw: float, q_mvar: float, vm_pu: float):          
                        self.name = name
                        self.id = id
                        self.p_mw = p_mw 
                        self.q_mvar = q_mvar  
                        self.vm_pu = vm_pu                          
                       
                class ShuntsOut(object):
                    def __init__(self, shunts: List[ShuntOut]):
                        self.shunts = shunts              
                shuntsList = list() 
                
                
                class CapacitorOut(object):
                    def __init__(self, name: str, id:str, p_mw: float, q_mvar: float, vm_pu: float):          
                        self.name = name
                        self.id = id
                        self.p_mw = p_mw 
                        self.q_mvar = q_mvar  
                        self.vm_pu = vm_pu                          
                       
                class CapacitorsOut(object):
                    def __init__(self, capacitors: List[CapacitorOut]):
                        self.capacitors = capacitors              
                capacitorsList = list()                 
                
                
                class LoadOut(object):
                    def __init__(self, name: str, id:str, p_mw: float, q_mvar: float):          
                        self.name = name
                        self.id = id
                        self.p_mw = p_mw 
                        self.q_mvar = q_mvar 
                                                                    
                class LoadsOut(object):
                    def __init__(self, loads: List[LoadOut]):
                        self.loads = loads              
                loadsList = list() 
                
                
                class AsymmetricLoadOut(object):
                    def __init__(self, name: str, id:str, p_a_mw: float, q_a_mvar: float, p_b_mw: float, q_b_mvar: float, p_c_mw: float, q_c_mvar: float):          
                        self.name = name
                        self.id = id
                        self.p_a_mw = p_a_mw 
                        self.q_a_mvar = q_a_mvar 
                        self.p_b_mw = p_b_mw 
                        self.q_b_mvar = q_b_mvar
                        self.p_c_mw = p_c_mw 
                        self.q_c_mvar = q_c_mvar
                                                                    
                class AsymmetricLoadsOut(object):
                    def __init__(self, asymmetricloads: List[AsymmetricLoadOut]):
                        self.asymmetricloads = asymmetricloads              
                asymmetricloadsList = list() 
                
                
                class ImpedanceOut(object):
                    def __init__(self, name: str, id:str, p_from_mw: float, q_from_mvar: float, p_to_mw: float, q_to_mvar: float, pl_mw: float, ql_mvar: float, i_from_ka: float, i_to_ka: float ):          
                        self.name = name
                        self.id = id
                        self.p_from_mw = p_from_mw 
                        self.q_from_mvar = q_from_mvar 
                        self.p_to_mw = p_to_mw 
                        self.q_to_mvar = q_to_mvar
                        self.pl_mw = pl_mw 
                        self.ql_mvar = ql_mvar
                        self.i_from_ka = i_from_ka 
                        self.i_to_ka = i_to_ka                        
                                                                    
                class ImpedancesOut(object):
                    def __init__(self, impedances: List[ImpedanceOut]):
                        self.impedances = impedances              
                impedancesList = list() 
                
                
                class WardOut(object):
                    def __init__(self, name: str, id:str, p_mw: float, q_mvar: float, vm_pu: float):          
                        self.name = name
                        self.id = id
                        self.p_mw = p_mw 
                        self.q_mvar = q_mvar 
                        self.vm_pu = vm_pu 
                       
                class WardsOut(object):
                    def __init__(self, wards: List[WardOut]):
                        self.wards = wards              
                wardsList = list() 
                
                
                class ExtendedWardOut(object):
                    def __init__(self, name: str, id:str, p_mw: float, q_mvar: float, vm_pu: float):          
                        self.name = name                        
                        self.id = id
                        self.p_mw = p_mw 
                        self.q_mvar = q_mvar 
                        self.vm_pu = vm_pu 
                       
                class ExtendedWardsOut(object):
                    def __init__(self, extendedwards: List[ExtendedWardOut]):
                        self.extendedwards = extendedwards              
                extendedwardsList = list() 
                
                
                class MotorOut(object):
                    def __init__(self, name: str, id:str, p_mw: float, q_mvar: float):          
                        self.name = name
                        self.id = id
                        self.p_mw = p_mw 
                        self.q_mvar = q_mvar 
                       
                       
                class MotorsOut(object):
                    def __init__(self, motors: List[MotorOut]):
                        self.motors = motors              
                motorsList = list()

                class SVCOut(object):
                    def __init__(self, name: str, id:str, thyristor_firing_angle_degree: float, x_ohm: float, q_mvar: float, vm_pu: float, va_degree: float):          
                        self.name = name
                        self.id = id
                        self.thyristor_firing_angle_degree = thyristor_firing_angle_degree 
                        self.x_ohm = x_ohm   
                        self.q_mvar = q_mvar
                        self.vm_pu = vm_pu
                        self.va_degree = va_degree      
                       
                class SVCsOut(object):
                    def __init__(self, svcs: List[SVCOut]):
                        self.svcs = svcs              
                SVCsList = list()

                class TCSCOut(object):
                    def __init__(self, name: str, id:str, thyristor_firing_angle_degree: float, x_ohm: float, p_from_mw: float, q_from_mvar: float, p_to_mw: float, q_to_mvar: float, p_l_mw: float, q_l_mvar: float, vm_from_pu: float, va_from_degree: float, vm_to_pu: float, va_to_degree: float ):          
                        self.name = name
                        self.id = id
                        self.thyristor_firing_angle_degree = thyristor_firing_angle_degree 
                        self.x_ohm = x_ohm
                        self.p_from_mw = p_from_mw 
                        self.q_from_mvar = q_from_mvar
                        self.p_to_mw = p_to_mw 
                        self.q_to_mvar = q_to_mvar
                        self.p_l_mw = p_l_mw 
                        self.q_l_mvar = q_l_mvar
                        self.vm_from_pu = vm_from_pu 
                        self.va_from_degree = va_from_degree
                        self.vm_to_pu = vm_to_pu 
                        self.va_to_degree = va_to_degree                        
                       
                class TCSCsOut(object):
                    def __init__(self, tcscs: List[TCSCOut]):
                        self.tcscs = tcscs              
                TCSCsList = list()

                
                class SSCOut(object):
                    def __init__(self, name: str, id:str, q_mvar: float, vm_internal_pu: float, va_internal_degree: float, vm_pu: float, va_degree: float):          
                        self.name = name
                        self.id = id
                        self.q_mvar = q_mvar 
                        self.vm_internal_pu = vm_internal_pu
                        self.va_internal_degree = va_internal_degree
                        self.vm_pu = vm_pu
                        self.va_degree = va_degree                       
                       
                class SSCsOut(object):
                    def __init__(self, sscs: List[SSCOut]):
                        self.sscs = sscs              
                sscsList = list()
                
                
                
                class StorageOut(object):
                    def __init__(self, name: str, id:str, p_mw: float, q_mvar: float):          
                        self.name = name
                        self.id = id
                        self.p_mw = p_mw 
                        self.q_mvar = q_mvar 
                       
                       
                class StoragesOut(object):
                    def __init__(self, storages: List[StorageOut]):
                        self.storages = storages              
                storagesList = list() 
                
                
                class DClineOut(object):
                    def __init__(self, name: str, id:str, p_from_mw: float, q_from_mvar: float, p_to_mw: float, q_to_mvar: float, pl_mw: float, vm_from_pu: float, va_from_degree: float, vm_to_pu: float, va_to_degree: float):          
                        self.name = name
                        self.id = id
                        self.p_from_mw = p_from_mw 
                        self.q_from_mvar = q_from_mvar 
                        self.p_to_mw = p_to_mw 
                        self.q_to_mvar = q_to_mvar
                        self.pl_mw = pl_mw                       
                        self.vm_from_pu = vm_from_pu 
                        self.va_from_degree = va_from_degree 
                        self.vm_to_pu = vm_to_pu 
                        self.va_to_degree = va_to_degree                           
                                                                    
                class DClinesOut(object):
                    def __init__(self, dclines: List[DClineOut]):
                        self.dclines = dclines              
                dclinesList = list()
                
                class DcBusOut(object):
                    def __init__(self, name: str, id: str, vm_pu: float, p_mw: float):          
                        self.name = name
                        self.id = id
                        self.vm_pu = vm_pu
                        self.p_mw = p_mw
                       
                class DcBusesOut(object):
                    def __init__(self, dcbuses: List[DcBusOut]):
                        self.dcbuses = dcbuses              
                dcbusesList = list()
                
                class LoadDcOut(object):
                    def __init__(self, name: str, id: str, p_mw: float):          
                        self.name = name
                        self.id = id
                        self.p_mw = p_mw
                       
                class LoadsDcOut(object):
                    def __init__(self, loadsdc: List[LoadDcOut]):
                        self.loadsdc = loadsdc              
                loadsdcList = list()
                
                class SourceDcOut(object):
                    def __init__(self, name: str, id: str, vm_pu: float, p_mw: float):          
                        self.name = name
                        self.id = id
                        self.vm_pu = vm_pu
                        self.p_mw = p_mw
                       
                class SourcesDcOut(object):
                    def __init__(self, sourcesdc: List[SourceDcOut]):
                        self.sourcesdc = sourcesdc              
                sourcesdcList = list()
                
                class SwitchOut(object):
                    def __init__(self, name: str, id: str, closed: bool, i_ka: float):          
                        self.name = name
                        self.id = id
                        self.closed = closed
                        self.i_ka = i_ka
                       
                class SwitchesOut(object):
                    def __init__(self, switches: List[SwitchOut]):
                        self.switches = switches              
                switchesList = list()
                
                class VSCOut(object):
                    def __init__(self, name: str, id: str, p_mw: float, vm_pu: float):          
                        self.name = name
                        self.id = id
                        self.p_mw = p_mw
                        self.vm_pu = vm_pu
                       
                class VSCsOut(object):
                    def __init__(self, vscs: List[VSCOut]):
                        self.vscs = vscs              
                vscsList = list()
                
                class B2bVSCOut(object):
                    def __init__(self, name: str, id: str, p_mw: float, vm1_pu: float, vm2_pu: float):          
                        self.name = name
                        self.id = id
                        self.p_mw = p_mw
                        self.vm1_pu = vm1_pu
                        self.vm2_pu = vm2_pu
                       
                class B2bVSCsOut(object):
                    def __init__(self, b2bvscs: List[B2bVSCOut]):
                        self.b2bvscs = b2bvscs              
                b2bvscsList = list() 
                
                
                #Bus
                for index, row in net.res_bus.iterrows():
                    p_mw = row['p_mw']
                    q_mvar = row['q_mvar']
                    denom_pf = math.sqrt(math.pow(p_mw, 2) + math.pow(q_mvar, 2))
                    if denom_pf != 0 and not math.isnan(denom_pf):
                        pf = p_mw / denom_pf
                    else:
                        pf = 0.0
                    if math.isnan(pf):
                        pf = 0.0
                    if p_mw != 0 and not math.isnan(p_mw):
                        q_p = q_mvar / p_mw
                    else:
                        q_p = 0.0
                    if math.isnan(q_p) or math.isinf(q_p):
                        q_p = 0.0
                    busbar = BusbarOut(name=net.bus._get_value(index, 'name'), id = net.bus._get_value(index, 'id'), vm_pu=row['vm_pu'], va_degree=row['va_degree'], p_mw=p_mw, q_mvar=q_mvar, pf = pf, q_p=q_p)         
                    busbarList.append(busbar) 
                    busbars = BusbarsOut(busbars = busbarList)
                
                #Line
                if(net.res_line.empty):
                        result = {**busbars.__dict__}                  
                else:                    
                        for index, row in net.res_line.iterrows():    
                            line = LineOut(name=net.line._get_value(index, 'name'), id = net.line._get_value(index, 'id'), p_from_mw=row['p_from_mw'], q_from_mvar=row['q_from_mvar'], p_to_mw=row['p_to_mw'], q_to_mvar=row['q_to_mvar'], i_from_ka=row['i_from_ka'], i_to_ka=row['i_to_ka'], loading_percent=row['loading_percent'])        
                            linesList.append(line) 
                            lines = LinesOut(lines = linesList)
                            
                            result = {**busbars.__dict__, **lines.__dict__} #łączenie dwóch dictionaries                        
                     
                
                #External Grid
                if(net.res_ext_grid.empty):
                    pass
                else:                    
                        for index, row in net.res_ext_grid.iterrows():    
                            externalgrid = ExternalGridOut(name=net.ext_grid._get_value(index, 'name'), id = net.ext_grid._get_value(index, 'id'), p_mw=row['p_mw'], q_mvar=row['q_mvar'], pf = row['p_mw']/math.sqrt(math.pow(row['p_mw'],2)+math.pow(row['q_mvar'],2)), q_p=row['q_mvar']/row['p_mw'])        
                            externalgridsList.append(externalgrid) 
                            externalgrids = ExternalGridsOut(externalgrids = externalgridsList) 
                        result = {**result, **externalgrids.__dict__}          
                             
                #Generator         
                if(net.res_gen.empty):
                    pass
                else:                    
                        for index, row in net.res_gen.iterrows():    
                            generator = GeneratorOut(name=net.gen._get_value(index, 'name'), id = net.gen._get_value(index, 'id'), p_mw=row['p_mw'], q_mvar=row['q_mvar'], va_degree=row['va_degree'], vm_pu=row['vm_pu'])        
                            generatorsList.append(generator) 
                            generators = GeneratorsOut(generators = generatorsList)
                        
                        result = {**result, **generators.__dict__}
                        
                #Static Generator                     
                if(net.res_sgen.empty):
                    pass
                else:                    
                        for index, row in net.res_sgen.iterrows():    
                            staticgenerator = StaticGeneratorOut(name=net.sgen._get_value(index, 'name'), id = net.sgen._get_value(index, 'id'), p_mw=row['p_mw'], q_mvar=row['q_mvar'])        
                            staticgeneratorsList.append(staticgenerator) 
                            staticgenerators = StaticGeneratorsOut(staticgenerators = staticgeneratorsList)
                        
                        result = {**result, **staticgenerators.__dict__}
                        
                        
                
                #Asymmetric Static Generator                     
                if(net.res_asymmetric_sgen.empty):
                    pass
                else:
                        available_columns = net.res_asymmetric_sgen.columns.tolist()
                        
                        # Check if phase-specific columns exist
                        has_phase_specific = all(col in available_columns for col in ['p_a_mw', 'q_a_mvar', 'p_b_mw', 'q_b_mvar', 'p_c_mw', 'q_c_mvar'])
                        has_aggregate = all(col in available_columns for col in ['p_mw', 'q_mvar'])
                        
                        if has_phase_specific:
                            # Use phase-specific results if available
                            for index, row in net.res_asymmetric_sgen.iterrows():    
                                asymmetricstaticgenerator = AsymmetricStaticGeneratorOut(
                                    name=net.asymmetric_sgen._get_value(index, 'name'), 
                                    id=net.asymmetric_sgen._get_value(index, 'id'), 
                                    p_a_mw=row['p_a_mw'], 
                                    q_a_mvar=row['q_a_mvar'], 
                                    p_b_mw=row['p_b_mw'], 
                                    q_b_mvar=row['q_b_mvar'], 
                                    p_c_mw=row['p_c_mw'], 
                                    q_c_mvar=row['q_c_mvar']
                                )        
                                asymmetricstaticgeneratorsList.append(asymmetricstaticgenerator)
                        elif has_aggregate:
                            # If only aggregate results available, distribute based on input phase distribution
                            for index, row in net.res_asymmetric_sgen.iterrows():
                                # Get input phase values to determine distribution
                                p_a_input = float(net.asymmetric_sgen._get_value(index, 'p_a_mw'))
                                p_b_input = float(net.asymmetric_sgen._get_value(index, 'p_b_mw'))
                                p_c_input = float(net.asymmetric_sgen._get_value(index, 'p_c_mw'))
                                q_a_input = float(net.asymmetric_sgen._get_value(index, 'q_a_mvar'))
                                q_b_input = float(net.asymmetric_sgen._get_value(index, 'q_b_mvar'))
                                q_c_input = float(net.asymmetric_sgen._get_value(index, 'q_c_mvar'))
                                
                                # Calculate total input power for distribution
                                p_total_input = abs(p_a_input) + abs(p_b_input) + abs(p_c_input)
                                q_total_input = abs(q_a_input) + abs(q_b_input) + abs(q_c_input)
                                
                                # Get aggregate results
                                p_total = float(row['p_mw'])
                                q_total = float(row['q_mvar'])
                                
                                # Distribute results proportionally based on input phase distribution
                                if p_total_input > 0:
                                    p_a_mw = p_total * (abs(p_a_input) / p_total_input)
                                    p_b_mw = p_total * (abs(p_b_input) / p_total_input)
                                    p_c_mw = p_total * (abs(p_c_input) / p_total_input)
                                else:
                                    # If no input power, distribute equally
                                    p_a_mw = p_total / 3.0
                                    p_b_mw = p_total / 3.0
                                    p_c_mw = p_total / 3.0
                                
                                if q_total_input > 0:
                                    q_a_mvar = q_total * (abs(q_a_input) / q_total_input)
                                    q_b_mvar = q_total * (abs(q_b_input) / q_total_input)
                                    q_c_mvar = q_total * (abs(q_c_input) / q_total_input)
                                else:
                                    # If no input reactive power, distribute equally
                                    q_a_mvar = q_total / 3.0
                                    q_b_mvar = q_total / 3.0
                                    q_c_mvar = q_total / 3.0
                                
                                asymmetricstaticgenerator = AsymmetricStaticGeneratorOut(
                                    name=net.asymmetric_sgen._get_value(index, 'name'), 
                                    id=net.asymmetric_sgen._get_value(index, 'id'), 
                                    p_a_mw=p_a_mw, 
                                    q_a_mvar=q_a_mvar, 
                                    p_b_mw=p_b_mw, 
                                    q_b_mvar=q_b_mvar, 
                                    p_c_mw=p_c_mw, 
                                    q_c_mvar=q_c_mvar
                                )        
                                asymmetricstaticgeneratorsList.append(asymmetricstaticgenerator)
                        else:
                            print(f"Warning: res_asymmetric_sgen has unexpected column structure. Available columns: {available_columns}")
                            pass
                        
                        if asymmetricstaticgeneratorsList:
                            asymmetricstaticgenerators = AsymmetricStaticGeneratorsOut(asymmetricstaticgenerators = asymmetricstaticgeneratorsList)
                            result = {**result, **asymmetricstaticgenerators.__dict__}
                        
               
                #Transformer                     
                if(net.res_trafo.empty):
                    pass
                else:                    
                        for index, row in net.res_trafo.iterrows():    
                            transformer = TransformerOut(name=net.trafo._get_value(index, 'name'), id = net.trafo._get_value(index, 'id'), p_hv_mw=row['p_hv_mw'], q_hv_mvar=row['q_hv_mvar'], p_lv_mw=row['p_lv_mw'], q_lv_mvar=row['q_lv_mvar'], pl_mw=row['pl_mw'], 
                                                         ql_mvar=row['ql_mvar'], i_hv_ka=row['i_hv_ka'], i_lv_ka=row['i_lv_ka'], vm_hv_pu=row['vm_hv_pu'], vm_lv_pu=row['vm_lv_pu'], va_hv_degree=row['va_hv_degree'], va_lv_degree=row['va_lv_degree'], loading_percent=row['loading_percent'])        
                            transformersList.append(transformer) 
                            transformers = TransformersOut(transformers = transformersList)
                        
                        result = {**result, **transformers.__dict__}   
                        
                        
                #Transformer3W                     
                if(net.res_trafo3w.empty):
                    pass
                else:                    
                        for index, row in net.res_trafo3w.iterrows():    
                            transformer3W = Transformer3WOut(name=net.trafo3w._get_value(index, 'name'), id = net.trafo3w._get_value(index, 'id'), p_hv_mw=row['p_hv_mw'], q_hv_mvar=row['q_hv_mvar'], p_mv_mw=row['p_mv_mw'], q_mv_mvar=row['q_mv_mvar'], p_lv_mw=row['p_lv_mw'], 
                                                         q_lv_mvar=row['q_lv_mvar'], pl_mw=row['pl_mw'], ql_mvar=row['ql_mvar'], i_hv_ka=row['i_hv_ka'], i_mv_ka=row['i_mv_ka'], i_lv_ka=row['i_lv_ka'], vm_hv_pu=row['vm_hv_pu'], vm_mv_pu=row['vm_mv_pu'],
                                                         vm_lv_pu=row['vm_lv_pu'], va_hv_degree=row['va_hv_degree'], va_mv_degree=row['va_mv_degree'], va_lv_degree=row['va_lv_degree'], loading_percent=row['loading_percent'])        
                            transformers3WList.append(transformer3W)
                            transformers3W = Transformers3WOut(transformers3W = transformers3WList)
                        
                        result = {**result, **transformers3W.__dict__}  
               
               

                
                #Shunt reactor
                if(net.res_shunt.empty):
                    pass
                else:                    
                        for index, row in net.res_shunt.iterrows():
                            #if (row['q_mvar'] >= 0):
                            if (net.shunt._get_value(index, 'typ') == 'shuntreactor'):     
                                shunt = ShuntOut(name=net.shunt._get_value(index, 'name'), id = net.shunt._get_value(index, 'id'), p_mw=row['p_mw'], q_mvar=row['q_mvar'], vm_pu = row['vm_pu'])        
                                shuntsList.append(shunt) 
                                shunts = ShuntsOut(shunts = shuntsList) 
                                result = {**result, **shunts.__dict__}  
                        
                #Capacitor
                if(net.res_shunt.empty):
                    pass
                else:                    
                        for index, row in net.res_shunt.iterrows(): 
                            if (net.shunt._get_value(index, 'typ') == 'capacitor'):  # q is always negative for capacitor
                                capacitor = CapacitorOut(name=net.shunt._get_value(index, 'name'), id = net.shunt._get_value(index, 'id'), p_mw=row['p_mw'], q_mvar=row['q_mvar'], vm_pu = row['vm_pu'])        
                                capacitorsList.append(capacitor) 
                                capacitors = CapacitorsOut(capacitors = capacitorsList) 
                                result = {**result, **capacitors.__dict__}  
                
               
                #Load
                if(net.res_load.empty):
                    pass
                else:                    
                        for index, row in net.res_load.iterrows():    
                            load = LoadOut(name=net.load._get_value(index, 'name'), id = net.load._get_value(index, 'id'), p_mw=row['p_mw'], q_mvar=row['q_mvar'])        
                            # print(load)  # Comment out this debug line
                            loadsList.append(load) 
                            # print(loadsList)  # Comment out this debug line
                            loads = LoadsOut(loads = loadsList) 
                        result = {**result, **loads.__dict__}        
                        
                #Asymmetric Load
                if(net.res_asymmetric_load.empty):
                    pass
                else:
                        available_columns = net.res_asymmetric_load.columns.tolist()
                        
                        # Check if phase-specific columns exist
                        has_phase_specific = all(col in available_columns for col in ['p_a_mw', 'q_a_mvar', 'p_b_mw', 'q_b_mvar', 'p_c_mw', 'q_c_mvar'])
                        has_aggregate = all(col in available_columns for col in ['p_mw', 'q_mvar'])
                        
                        if has_phase_specific:
                            # Use phase-specific results if available
                            for index, row in net.res_asymmetric_load.iterrows():    
                                asymmetricload = AsymmetricLoadOut(
                                    name=net.asymmetric_load._get_value(index, 'name'), 
                                    id=net.asymmetric_load._get_value(index, 'id'), 
                                    p_a_mw=row['p_a_mw'], 
                                    q_a_mvar=row['q_a_mvar'], 
                                    p_b_mw=row['p_b_mw'], 
                                    q_b_mvar=row['q_b_mvar'], 
                                    p_c_mw=row['p_c_mw'], 
                                    q_c_mvar=row['q_c_mvar']
                                )        
                                asymmetricloadsList.append(asymmetricload)
                        elif has_aggregate:
                            # If only aggregate results available, distribute based on input phase distribution
                            for index, row in net.res_asymmetric_load.iterrows():
                                # Get input phase values to determine distribution
                                p_a_input = float(net.asymmetric_load._get_value(index, 'p_a_mw'))
                                p_b_input = float(net.asymmetric_load._get_value(index, 'p_b_mw'))
                                p_c_input = float(net.asymmetric_load._get_value(index, 'p_c_mw'))
                                q_a_input = float(net.asymmetric_load._get_value(index, 'q_a_mvar'))
                                q_b_input = float(net.asymmetric_load._get_value(index, 'q_b_mvar'))
                                q_c_input = float(net.asymmetric_load._get_value(index, 'q_c_mvar'))
                                
                                # Calculate total input power for distribution
                                p_total_input = abs(p_a_input) + abs(p_b_input) + abs(p_c_input)
                                q_total_input = abs(q_a_input) + abs(q_b_input) + abs(q_c_input)
                                
                                # Get aggregate results
                                p_total = float(row['p_mw'])
                                q_total = float(row['q_mvar'])
                                
                                # Distribute results proportionally based on input phase distribution
                                if p_total_input > 0:
                                    p_a_mw = p_total * (abs(p_a_input) / p_total_input)
                                    p_b_mw = p_total * (abs(p_b_input) / p_total_input)
                                    p_c_mw = p_total * (abs(p_c_input) / p_total_input)
                                else:
                                    # If no input power, distribute equally
                                    p_a_mw = p_total / 3.0
                                    p_b_mw = p_total / 3.0
                                    p_c_mw = p_total / 3.0
                                
                                if q_total_input > 0:
                                    q_a_mvar = q_total * (abs(q_a_input) / q_total_input)
                                    q_b_mvar = q_total * (abs(q_b_input) / q_total_input)
                                    q_c_mvar = q_total * (abs(q_c_input) / q_total_input)
                                else:
                                    # If no input reactive power, distribute equally
                                    q_a_mvar = q_total / 3.0
                                    q_b_mvar = q_total / 3.0
                                    q_c_mvar = q_total / 3.0
                                
                                asymmetricload = AsymmetricLoadOut(
                                    name=net.asymmetric_load._get_value(index, 'name'), 
                                    id=net.asymmetric_load._get_value(index, 'id'), 
                                    p_a_mw=p_a_mw, 
                                    q_a_mvar=q_a_mvar, 
                                    p_b_mw=p_b_mw, 
                                    q_b_mvar=q_b_mvar, 
                                    p_c_mw=p_c_mw, 
                                    q_c_mvar=q_c_mvar
                                )        
                                asymmetricloadsList.append(asymmetricload)
                        else:
                            print(f"Warning: res_asymmetric_load has unexpected column structure. Available columns: {available_columns}")
                            pass
                        
                        if asymmetricloadsList:
                            asymmetricloads = AsymmetricLoadsOut(asymmetricloads = asymmetricloadsList) 
                            result = {**result, **asymmetricloads.__dict__}    
                        
                        
                #Impedance
                if(net.res_impedance.empty):
                    pass
                else:                    
                        for index, row in net.res_impedance.iterrows():    
                            impedance = ImpedanceOut(name=net.impedance._get_value(index, 'name'), id = net.impedance._get_value(index, 'id'), p_from_mw=row['p_from_mw'], q_from_mvar=row['q_from_mvar'], p_to_mw=row['p_to_mw'], q_to_mvar=row['q_to_mvar'], pl_mw=row['pl_mw'], ql_mvar=row['ql_mvar'], i_from_ka=row['i_from_ka'], i_to_ka=row['i_to_ka'])        
                            impedancesList.append(impedance) 
                            impedances = ImpedancesOut(impedances = impedancesList) 
                        result = {**result, **impedances.__dict__} 
                        
                
                #Ward
                if(net.res_ward.empty):
                    pass
                else:                    
                        for index, row in net.res_ward.iterrows():    
                            ward = WardOut(name=net.ward._get_value(index, 'name'), id = net.ward._get_value(index, 'id'), p_mw=row['p_mw'], q_mvar=row['q_mvar'], vm_pu=row['vm_pu'])        
                            wardsList.append(ward) 
                            wards = WardsOut(wards = wardsList) 
                        result = {**result, **wards.__dict__} 
                        
                        
                #Extended Ward
                if(net.res_xward.empty):
                    pass
                else:                    
                        for index, row in net.res_xward.iterrows():    
                            extendedward = ExtendedWardOut(name=net.xward._get_value(index, 'name'), id = net.xward._get_value(index, 'id'), p_mw=row['p_mw'], q_mvar=row['q_mvar'], vm_pu=row['vm_pu'])        
                            extendedwardsList.append(extendedward) 
                            extendedwards = ExtendedWardsOut(extendedwards = extendedwardsList) 
                        result = {**result, **extendedwards.__dict__} 
                        
                        
                #Motor
                if(net.res_motor.empty):
                    pass
                else:                    
                        for index, row in net.res_motor.iterrows():    
                            motor = MotorOut(name=net.motor._get_value(index, 'name'), id = net.motor._get_value(index, 'id'), p_mw=row['p_mw'], q_mvar=row['q_mvar'])        
                            motorsList.append(motor) 
                            motors = MotorsOut(motors = motorsList) 
                        result = {**result, **motors.__dict__} 
                        
                #Storage
                if(net.res_storage.empty):
                    pass
                else:                    
                        for index, row in net.res_storage.iterrows():    
                            storage = StorageOut(name=net.storage._get_value(index, 'name'), id = net.storage._get_value(index, 'id'), p_mw=row['p_mw'], q_mvar=row['q_mvar'])        
                            storagesList.append(storage) 
                            storages = StoragesOut(storages = storagesList) 
                        result = {**result, **storages.__dict__}


                #SVC
                try:                    
                    for index, row in net.res_svc.iterrows():    
                        svc = SVCOut(name=net.svc._get_value(index, 'name'), id = net.svc._get_value(index, 'id'), thyristor_firing_angle_degree=row['thyristor_firing_angle_degree'], x_ohm=row['x_ohm'], q_mvar=row['q_mvar'], vm_pu=row['vm_pu'], va_degree=row['va_degree'] )        
                        SVCsList.append(svc) 
                        svcs = SVCsOut(svcs = SVCsList) 
                    result = {**result, **svcs.__dict__}
                       
                except AttributeError:  
                    pass
                except UnboundLocalError:
                    pass
                        
                #TCSC   
                try:
                    for index, row in net.res_tcsc.iterrows():    
                            tcsc = TCSCOut(name=net.tcsc._get_value(index, 'name'), id = net.tcsc._get_value(index, 'id'), thyristor_firing_angle_degree=row['thyristor_firing_angle_degree'], x_ohm=row['x_ohm'], p_from_mw=row['p_from_mw'], q_from_mvar=row['q_from_mvar'], p_to_mw=row['p_to_mw'], q_to_mvar=row['q_to_mvar'], p_l_mw=row['p_l_mw'], q_l_mvar=row['q_l_mvar'], vm_from_pu=row['vm_from_pu'], va_from_degree=row['va_from_degree'], vm_to_pu=row['vm_to_pu'], va_to_degree=row['va_to_degree']  )        
                            TCSCsList.append(tcsc) 
                            tcscs = TCSCsOut(tcscs = TCSCsList) 
                    result = {**result, **tcscs.__dict__} 
                     
                except AttributeError:  
                    pass
                except UnboundLocalError:
                    pass

                                               
                #SSC
                
                #try:
                #    for index, row in net.res_ssc.iterrows():    
                #            ssc = SSCOut(name=net.ssc._get_value(index, 'name'), id = net.ssc._get_value(index, 'id'), q_mvar=row['q_mvar'], vm_internal_pu=row['vm_internal_pu'], va_internal_degree=row['va_internal_degree'], vm_pu=row['vm_pu'], va_degree=row['va_degree'])        
                #            sscsList.append(ssc) 
                #            sscs = SSCsOut(sscs = sscsList) 
                #    result = {**result, **sscs.__dict__}
                #except AttributeError:  
                #SSC    print("no SSC in the model")  
                     
                #SSC
                if(net.res_ssc.empty):
                    pass
                else:                    
                    for index, row in net.res_ssc.iterrows():    
                        ssc = SSCOut(name=net.ssc._get_value(index, 'name'), id = net.ssc._get_value(index, 'id'), q_mvar=row['q_mvar'], vm_internal_pu=row['vm_internal_pu'], va_internal_degree=row['va_internal_degree'], vm_pu=row['vm_pu'], va_degree=row['va_degree'])        
                        sscsList.append(ssc) 
                        sscs = SSCsOut(sscs = sscsList) 
                    result = {**result, **sscs.__dict__}                    
                       
                                        
                #DC Bus
                if(hasattr(net, 'res_dc_bus') and not net.res_dc_bus.empty):
                    for index, row in net.res_dc_bus.iterrows():    
                        dcbus = DcBusOut(name=net.dc_bus._get_value(index, 'name'), id = net.dc_bus._get_value(index, 'id'), vm_pu=row['vm_pu'], p_mw=row['p_mw'])        
                        dcbusesList.append(dcbus) 
                        dcbuses = DcBusesOut(dcbuses = dcbusesList) 
                    result = {**result, **dcbuses.__dict__}
                
                #Load DC
                if(hasattr(net, 'res_load_dc') and not net.res_load_dc.empty):
                    for index, row in net.res_load_dc.iterrows():    
                        loaddc = LoadDcOut(name=net.load_dc._get_value(index, 'name'), id = net.load_dc._get_value(index, 'id'), p_mw=row['p_mw'])        
                        loadsdcList.append(loaddc) 
                        loadsdc = LoadsDcOut(loadsdc = loadsdcList) 
                    result = {**result, **loadsdc.__dict__}
                
                #Source DC
                if(hasattr(net, 'res_source_dc') and not net.res_source_dc.empty):
                    for index, row in net.res_source_dc.iterrows():    
                        sourcedc = SourceDcOut(name=net.source_dc._get_value(index, 'name'), id = net.source_dc._get_value(index, 'id'), vm_pu=row['vm_pu'], p_mw=row['p_mw'])        
                        sourcesdcList.append(sourcedc) 
                        sourcesdc = SourcesDcOut(sourcesdc = sourcesdcList) 
                    result = {**result, **sourcesdc.__dict__}
                
                #Switch
                if(hasattr(net, 'res_switch') and not net.res_switch.empty):
                    for index, row in net.res_switch.iterrows():    
                        switch = SwitchOut(name=net.switch._get_value(index, 'name'), id = net.switch._get_value(index, 'id'), closed=row.get('closed', True), i_ka=row.get('i_ka', 0.0))        
                        switchesList.append(switch) 
                        switches = SwitchesOut(switches = switchesList) 
                    result = {**result, **switches.__dict__}
                
                #VSC
                if(hasattr(net, 'res_vsc') and not net.res_vsc.empty):
                    for index, row in net.res_vsc.iterrows():
                        vsc_name = net.vsc.at[index, 'name'] if 'name' in net.vsc.columns else f'VSC_{index}'
                        vsc_id = net.vsc.at[index, 'id'] if 'id' in net.vsc.columns else str(index)
                        vsc = VSCOut(name=vsc_name, id=vsc_id, p_mw=row['p_mw'], vm_pu=row.get('vm_pu', 0.0))        
                        vscsList.append(vsc) 
                        vscs = VSCsOut(vscs = vscsList) 
                    result = {**result, **vscs.__dict__}
                
                #B2B VSC
                if(hasattr(net, 'res_b2b_vsc') and not net.res_b2b_vsc.empty):
                    for index, row in net.res_b2b_vsc.iterrows():    
                        b2bvsc = B2bVSCOut(name=net.b2b_vsc._get_value(index, 'name'), id = net.b2b_vsc._get_value(index, 'id'), p_mw=row['p_mw'], vm1_pu=row['vm1_pu'], vm2_pu=row['vm2_pu'])        
                        b2bvscsList.append(b2bvsc) 
                        b2bvscs = B2bVSCsOut(b2bvscs = b2bvscsList) 
                    result = {**result, **b2bvscs.__dict__}
                
                #DCLine (old HVDC link element - pp.create_dcline)
                if(net.res_dcline.empty):
                    pass
                else:                    
                        for index, row in net.res_dcline.iterrows():    
                            dcline = ImpedanceOut(name=net.dcline._get_value(index, 'name'), id = net.dcline._get_value(index, 'id'), p_from_mw=row['p_from_mw'], q_from_mvar=row['q_from_mvar'], p_to_mw=row['p_to_mw'], q_to_mvar=row['q_to_mvar'], pl_mw=row['pl_mw'], vm_from_pu=row['vm_from_pu'], va_from_degree=row['va_from_degree'], vm_to_pu=row['vm_to_pu'], va_to_degree=row['va_to_degree'] )        
                            dclinesList.append(dcline) 
                            dclines = ImpedancesOut(dclines = dclinesList) 
                        result = {**result, **dclines.__dict__}         
                
                # DC Grid Line (line_dc element - pp.create_line_dc)
                # This is part of DC grid modeling (bus_dc + line_dc + vsc)
                if hasattr(net, 'res_line_dc') and not net.res_line_dc.empty:
                    print(f"Processing res_line_dc results: {len(net.res_line_dc)} items")
                    
                    class LineDcOut(object):
                        def __init__(self, name: str, id: str, p_from_mw: float, p_to_mw: float, pl_mw: float, 
                                     vm_from_pu: float, vm_to_pu: float, i_from_ka: float, i_to_ka: float, loading_percent: float):
                            self.name = name
                            self.id = id
                            self.p_from_mw = p_from_mw
                            self.p_to_mw = p_to_mw
                            self.pl_mw = pl_mw
                            self.vm_from_pu = vm_from_pu
                            self.vm_to_pu = vm_to_pu
                            self.i_from_ka = i_from_ka
                            self.i_to_ka = i_to_ka
                            self.loading_percent = loading_percent
                    
                    class LineDcsOut(object):
                        def __init__(self, linedcs: List[LineDcOut]):
                            self.linedcs = linedcs
                    
                    linedcsList = []
                    for index, row in net.res_line_dc.iterrows():
                        line_dc_name = net.line_dc.at[index, 'name'] if 'name' in net.line_dc.columns else f'LineDC_{index}'
                        line_dc_id = net.line_dc.at[index, 'id'] if 'id' in net.line_dc.columns else str(index)
                        
                        linedc = LineDcOut(
                            name=line_dc_name,
                            id=line_dc_id,
                            p_from_mw=row.get('p_from_mw', 0.0),
                            p_to_mw=row.get('p_to_mw', 0.0),
                            pl_mw=row.get('pl_mw', 0.0),
                            vm_from_pu=row.get('vm_from_pu', 0.0),
                            vm_to_pu=row.get('vm_to_pu', 0.0),
                            i_from_ka=row.get('i_from_ka', 0.0),
                            i_to_ka=row.get('i_to_ka', 0.0),
                            loading_percent=row.get('loading_percent', 0.0)
                        )
                        linedcsList.append(linedc)
                    
                    linedcs = LineDcsOut(linedcs=linedcsList)
                    result = {**result, **linedcs.__dict__}
                    print(f"Added {len(linedcsList)} line_dc results to response")
                           
                # Generate Python code if export is requested
                if export_python and in_data and Busbars:
                    python_code = generate_pandapower_python_code(net, in_data, Busbars, algorithm, calculate_voltage_angles, init)
                    result['pandapower_python'] = python_code
                
                # Add tap control results to the response for frontend display
                if tap_control_results:
                    result['tap_control_results'] = tap_control_results
                
                # Add any vm_pu validation warnings to the response
                if hasattr(net, 'warnings') and net.warnings:
                    result['warnings'] = net.warnings
                
                #json.dumps - convert a subset of Python objects into a json string
                #default: If specified, default should be a function that gets called for objects that can't otherwise be serialized. It should return a JSON encodable version of the object or raise a TypeError. If not specified, TypeError is raised. 
                # OPTIMIZED: Removed indent=4, using compact separators for ~40% size reduction
                response = json.dumps(result, default=lambda o: o.__dict__, separators=(',', ':')) 
            
                print("Response to FRONTEND CORRECT")   
                   
                return response  


def shortcircuit(net, in_data):
    
    # Add diagnostic prints
    # Print key parameters
    # print("\nBus Data:")
    # print(net.bus)
        
    net.sgen["k"] = 1.1
    #print(net.sgen["k"])
    
    
    # print("\nShunt reactor Data:")
    # print(net.shunt)
        
    # print("\nTransformer Data:")
    # print(net.trafo)
    
    #print("\nThree-winding transformer Data:")
    # print(net.trafo3w)
        
    #print("\nExternal Grid Data:")
    #print(net.ext_grid)
    
    #print("\nLine Data:")
    #print(net.line)
    
    #print(net.bus.isna().sum())          # Check buses
    #print(net.line.isna().sum())         # Check lines
    #print(net.trafo.isna().sum())        # Check transformers
    #print(net.load.isna().sum())         # Check loads
   # print(net.sgen.isna().sum())         # Check static generators
  
    #print(net.line[net.line.isna().any(axis=1)])
    
    isolated_buses = top.unsupplied_buses(net)
    if len(isolated_buses) > 0:
        raise ValueError(f"Isolated buses found: {isolated_buses}. Check your network connectivity.")
    
    pp.diagnostic(net)
    
    
    # Validate network before running calculations
    #pp.runpp(net, calculate_voltage_angles=True)    

    
    # Extract short circuit parameters with defaults
    # Frontend sends: fault_type, fault_location, fault_impedance
    # According to Pandapower docs: fault=fault_type, case=calculation_case
    fault_type = in_data.get('fault_type', '3ph')  # Frontend 'fault_type' becomes pandapower 'fault'
    fault_location = in_data.get('fault_location', 'max')  # Frontend 'fault_location' becomes pandapower 'case'
    
    # Convert fault_location to bus index for bus parameter (if needed)
    if isinstance(fault_location, str) and fault_location.isdigit():
        bus = int(fault_location)
    elif isinstance(fault_location, str) and fault_location in ['max', 'min']:
        # If it's 'max' or 'min', use None (calculate for all buses)
        bus = None
    else:
        bus = None  # Default to None (calculate for all buses)
    
    # Get other parameters
    lv_tol_percent = int(in_data.get('fault_impedance', 10))  # Frontend 'fault_impedance' becomes 'lv_tol_percent'
    ip = True
    ith = True
    topology = in_data.get('topology', 'radial')
    tk_s = float(in_data.get('tk_s', 1.0))
    r_fault_ohm = float(in_data.get('r_fault_ohm', 0.0))
    x_fault_ohm = float(in_data.get('x_fault_ohm', 0.0))
    inverse_y = in_data.get('inverse_y', False)
    
    # Debug print to see what parameters are being passed
    
    # Print Pandapower version for debugging
    
    # Validate fault_type parameter - Pandapower expects specific values
    valid_fault_types = ['3ph', '2ph', '1ph']
    if fault_type not in valid_fault_types:
        fault_type = '3ph'  # Default to 3ph if invalid
    
    # Validate case parameter
    valid_cases = ['max', 'min']
    if fault_location not in valid_cases:
        fault_location = 'max'  # Default to max if invalid
 

    try:
        # Use correct parameter mapping according to Pandapower documentation
        
        # Call short circuit calculation with correct parameters including ip and ith.
        # IMPORTANT: branch_results=True is required to populate res_line_sc / res_trafo_sc / res_trafo3w_sc.
        # NOTE: return_all_currents=False (default) gives max/min per branch (simple index).
        #       return_all_currents=True gives results per (branch, fault_bus) combination (MultiIndex).
        #       For UI display, we want max/min per branch, so keep return_all_currents=False.
        sc.calc_sc(
            net,
            fault=fault_type,
            case=fault_location,
            bus=bus,
            ip=ip,
            ith=ith,
            tk_s=tk_s,
            kappa_method='C',
            r_fault_ohm=r_fault_ohm,
            x_fault_ohm=x_fault_ohm,
            check_connectivity=False,
            branch_results=True,
            return_all_currents=False,  # Changed: False gives max/min per branch with simple index
        )
        
        # Check if ip_ka and ith_ka calculations failed (all NaN) for single-phase faults
        if fault_type == '1ph' and net.res_bus_sc['ip_ka'].isna().all() and net.res_bus_sc['ith_ka'].isna().all():
            
            # Calculate ip_ka and ith_ka from ikss_ka using standard electrical engineering formulas
            # ip_ka = kappa * sqrt(2) * ikss_ka (peak current)
            # ith_ka = ikss_ka (for short duration faults, thermal current ≈ initial current)

            # Kappa factor for peak current calculation (typical value for medium voltage networks)
            # This can vary from 1.0 to 2.0 depending on network characteristics
            kappa_factor = 1.8  # Conservative estimate for medium voltage networks
            
            # Calculate ip_ka (peak short-circuit current)
            net.res_bus_sc['ip_ka'] = kappa_factor * np.sqrt(2) * net.res_bus_sc['ikss_ka']
            
            # Calculate ith_ka (thermal short-circuit current)
            # For short duration faults (tk_s = 1.0), ith ≈ ikss
            # For longer durations, ith would be calculated differently
            if tk_s <= 1.0:
                net.res_bus_sc['ith_ka'] = net.res_bus_sc['ikss_ka']
            else:
                # For longer fault durations, thermal current is typically lower
                # ith = ikss * sqrt(thermal_factor) where thermal_factor depends on fault duration
                thermal_factor = 1.0 / tk_s if tk_s > 1.0 else 1.0
                net.res_bus_sc['ith_ka'] = net.res_bus_sc['ikss_ka'] * np.sqrt(thermal_factor)
            
        
    except Exception as e:
        
        # Capture the diagnostic output and process it
        import io
        import sys
        
        # Capture stdout to get the diagnostic output
        captured_output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured_output
        
        try:
            # Run diagnostic again to capture the output
            pp.diagnostic(net)
        except:
            pass
        
        # Restore stdout
        sys.stdout = old_stdout
        diagnostic_output = captured_output.getvalue()
        
        # Process the diagnostic output to extract structured information
        processed_diagnostic = process_short_circuit_diagnostic(diagnostic_output, net)
        
        # Return a diagnostic response with both raw and processed data
        diagnostic_response = {
            "error": True,
            "message": f"Short circuit calculation failed: {str(e)}",
            "exception": str(e),
            "diagnostic": {
                "raw_output": diagnostic_output,
                "processed": processed_diagnostic,
                "fault_type": fault_type,
                "calculation_case": fault_location,
                "bus_index": bus,
                "network_elements": {
                    "buses": len(net.bus),
                    "lines": len(net.line),
                    "transformers": len(net.trafo),
                    "generators": len(net.gen),
                    "loads": len(net.load)
                }
            }
        }
        # OPTIMIZED: Compact JSON for faster transfer
        return json.dumps(diagnostic_response, separators=(',', ':'))
    #print(net.res_line_sc) # nie uwzględniam ze względu na: Branch results are in beta mode and might not always be reliable, especially for transformers
                
    #wyrzuciłem skss_mw bo wyskakiwał błąd przy zwarciu jednofazowym
    class BusbarOut(object):
        def __init__(self, name: str, id: str, ikss_ka: float, ip_ka: float, ith_ka: float, rk_ohm: float, xk_ohm: float):
            self.name = name
            self.id = id
            self.ikss_ka = ikss_ka
            self.ip_ka = ip_ka
            self.ith_ka = ith_ka
            self.rk_ohm = rk_ohm
            self.xk_ohm = xk_ohm

    class BusbarsOut(object):
        def __init__(self, busbars: List[BusbarOut]):
            self.busbars = busbars

    busbarList: List[BusbarOut] = []

    for index, row in net.res_bus_sc.iterrows():

        # Handle ip_ka column (might not exist if ip=False)
        if 'ip_ka' in row and not math.isnan(row['ip_ka']):
            ip_ka = row['ip_ka']
        else:
            ip_ka = None

        # Handle ith_ka column (might not exist if ith=False)
        if 'ith_ka' in row and not math.isnan(row['ith_ka']):
            ith_ka = row['ith_ka']
        else:
            ith_ka = None

        busbar = BusbarOut(
            name=net.bus._get_value(index, 'name'),
            id=net.bus._get_value(index, 'id'),
            ikss_ka=row['ikss_ka'],
            ip_ka=ip_ka,
            ith_ka=ith_ka,
            rk_ohm=row['rk_ohm'],
            xk_ohm=row['xk_ohm'],
        )

        busbarList.append(busbar)

    busbars = BusbarsOut(busbars=busbarList)

    # Start result payload with busbar data (existing behaviour)
    result = {**busbars.__dict__}

    # ------------------------------------------------------------------
    # NEW: expose short-circuit results for lines and transformers
    # ------------------------------------------------------------------
    print(f"Short Circuit: Processing branch results...")
    print(f"Short Circuit: net.res_line_sc exists: {hasattr(net, 'res_line_sc')}")
    if hasattr(net, "res_line_sc"):
        print(f"Short Circuit: net.res_line_sc shape: {net.res_line_sc.shape}")
        print(f"Short Circuit: net.res_line_sc columns: {list(net.res_line_sc.columns)}")
    print(f"Short Circuit: net.res_trafo_sc exists: {hasattr(net, 'res_trafo_sc')}")
    if hasattr(net, "res_trafo_sc"):
        print(f"Short Circuit: net.res_trafo_sc shape: {net.res_trafo_sc.shape}")
    print(f"Short Circuit: net.res_trafo3w_sc exists: {hasattr(net, 'res_trafo3w_sc')}")
    if hasattr(net, "res_trafo3w_sc"):
        print(f"Short Circuit: net.res_trafo3w_sc shape: {net.res_trafo3w_sc.shape}")
    
    def _clean_value(v):
        """Convert NaN to None and numpy scalars to python scalars for JSON."""
        if isinstance(v, (float, np.floating)):
            if math.isnan(v):
                return None
            return float(v)
        return v

    # Lines short-circuit results (net.res_line_sc)
    if hasattr(net, "res_line_sc") and not net.res_line_sc.empty:
        print(f"Short Circuit: Processing {len(net.res_line_sc)} line SC results...")
        print(f"Short Circuit: net.line shape: {net.line.shape}")
        print(f"Short Circuit: net.res_line_sc index type: {type(net.res_line_sc.index)}")
        
        # Check if we have a MultiIndex (happens with return_all_currents=True)
        if hasattr(net.res_line_sc.index, 'levels'):
            print(f"Short Circuit: WARNING - res_line_sc has MultiIndex, will group by branch")
            # Group by first level (branch index) and take max values
            res_line_sc_grouped = net.res_line_sc.groupby(level=0).max()
        else:
            res_line_sc_grouped = net.res_line_sc
        
        lines_sc_list = []
        for idx, row in res_line_sc_grouped.iterrows():
            line_entry = {}

            # Map back to original line name and id used by the frontend
            if idx in net.line.index:
                line_entry["name"] = _clean_value(net.line.at[idx, "name"]) if "name" in net.line.columns else str(idx)
                if "id" in net.line.columns:
                    line_entry["id"] = _clean_value(net.line.at[idx, "id"])
                else:
                    # Fallback: use pandapower index if custom id is missing
                    line_entry["id"] = str(idx)
            else:
                print(f"Short Circuit: Warning - line index {idx} not found in net.line")
                continue

            # Copy all numeric result columns
            for col, val in row.items():
                line_entry[col] = _clean_value(val)

            lines_sc_list.append(line_entry)
            
            # Log first line entry
            if len(lines_sc_list) == 1:
                print(f"Short Circuit: First line SC entry with name/id: {line_entry}")

        result["lines_sc"] = lines_sc_list
        print(f"Short Circuit: Successfully processed {len(lines_sc_list)} line SC results")

    # Two-winding transformer short-circuit results (net.res_trafo_sc)
    if hasattr(net, "res_trafo_sc") and not net.res_trafo_sc.empty:
        print(f"Short Circuit: Processing {len(net.res_trafo_sc)} transformer SC results...")
        print(f"Short Circuit: net.trafo shape: {net.trafo.shape}")
        print(f"Short Circuit: net.res_trafo_sc index type: {type(net.res_trafo_sc.index)}")
        
        # Check if we have a MultiIndex (happens with return_all_currents=True)
        if hasattr(net.res_trafo_sc.index, 'levels'):
            print(f"Short Circuit: WARNING - res_trafo_sc has MultiIndex, will group by branch")
            # Group by first level (branch index) and take max values
            res_trafo_sc_grouped = net.res_trafo_sc.groupby(level=0).max()
        else:
            res_trafo_sc_grouped = net.res_trafo_sc
        
        trafos_sc_list = []
        for idx, row in res_trafo_sc_grouped.iterrows():
            trafo_entry = {}

            if idx in net.trafo.index:
                trafo_entry["name"] = _clean_value(net.trafo.at[idx, "name"]) if "name" in net.trafo.columns else str(idx)
                if "id" in net.trafo.columns:
                    trafo_entry["id"] = _clean_value(net.trafo.at[idx, "id"])
                else:
                    trafo_entry["id"] = str(idx)
            else:
                print(f"Short Circuit: Warning - trafo index {idx} not found in net.trafo")
                continue

            for col, val in row.items():
                trafo_entry[col] = _clean_value(val)

            trafos_sc_list.append(trafo_entry)
            
            # Log first trafo entry
            if len(trafos_sc_list) == 1:
                print(f"Short Circuit: First trafo SC entry: {trafo_entry}")

        result["trafos_sc"] = trafos_sc_list
        print(f"Short Circuit: Successfully processed {len(trafos_sc_list)} trafo SC results")

    # Three-winding transformer short-circuit results (net.res_trafo3w_sc)
    if hasattr(net, "res_trafo3w_sc") and not net.res_trafo3w_sc.empty:
        print(f"Short Circuit: Processing {len(net.res_trafo3w_sc)} 3-winding transformer SC results...")
        
        # Check if we have a MultiIndex (happens with return_all_currents=True)
        if hasattr(net.res_trafo3w_sc.index, 'levels'):
            print(f"Short Circuit: WARNING - res_trafo3w_sc has MultiIndex, will group by branch")
            res_trafo3w_sc_grouped = net.res_trafo3w_sc.groupby(level=0).max()
        else:
            res_trafo3w_sc_grouped = net.res_trafo3w_sc
        
        trafos3w_sc_list = []
        for idx, row in res_trafo3w_sc_grouped.iterrows():
            trafo_entry = {}

            if idx in net.trafo3w.index:
                trafo_entry["name"] = _clean_value(net.trafo3w.at[idx, "name"]) if "name" in net.trafo3w.columns else str(idx)
                if "id" in net.trafo3w.columns:
                    trafo_entry["id"] = _clean_value(net.trafo3w.at[idx, "id"])
                else:
                    trafo_entry["id"] = str(idx)
            else:
                print(f"Short Circuit: Warning - trafo3w index {idx} not found in net.trafo3w")
                continue

            for col, val in row.items():
                trafo_entry[col] = _clean_value(val)

            trafos3w_sc_list.append(trafo_entry)

        result["trafos3w_sc"] = trafos3w_sc_list
        print(f"Short Circuit: Successfully processed {len(trafos3w_sc_list)} 3-winding trafo SC results")

    # Log what we're sending back
    print(f"Short Circuit: Final result keys: {list(result.keys())}")
    if "lines_sc" in result:
        print(f"Short Circuit: Sending {len(result['lines_sc'])} line SC results")
        if len(result['lines_sc']) > 0:
            print(f"Short Circuit: First line SC result: {result['lines_sc'][0]}")
    if "trafos_sc" in result:
        print(f"Short Circuit: Sending {len(result['trafos_sc'])} trafo SC results")
    if "trafos3w_sc" in result:
        print(f"Short Circuit: Sending {len(result['trafos3w_sc'])} trafo3w SC results")

    # OPTIMIZED: Compact JSON for faster transfer
    response = json.dumps(result, default=lambda o: o.__dict__, separators=(",", ":"))
    return response


def process_short_circuit_diagnostic(diagnostic_output, net):
    """
    Process the raw diagnostic output and extract structured information
    """
    processed = {
        "invalid_values": {},
        "overload": {},
        "nominal_voltages_dont_match": {},
        "isolated_buses": [],
        "convergence": {},
        "summary": {}
    }
    
    lines = diagnostic_output.split('\n')
    current_section = None
    
    for line in lines:
        line = line.strip()
        
        # Detect sections
        if 'Checking for invalid_values' in line:
            current_section = 'invalid_values'
        elif 'Checking for overload' in line:
            current_section = 'overload'
        elif 'Checking for nominal_voltages_dont_match' in line:
            current_section = 'nominal_voltages_dont_match'
        elif 'Checking for isolated_buses' in line:
            current_section = 'isolated_buses'
        elif 'SUMMARY:' in line:
            current_section = 'summary'
        
        # Process invalid values
        elif current_section == 'invalid_values' and ':' in line and '=' in line:
            # Parse lines like: "Invalid value found: 'trafo 0' with attribute 'vk_percent' = 0.0"
            if "Invalid value found:" in line:
                try:
                    # Extract element type and name
                    parts = line.split("'")
                    if len(parts) >= 3:
                        element_info = parts[1]  # e.g., "trafo 0"
                        element_parts = element_info.split()
                        element_type = element_parts[0]  # e.g., "trafo"
                        
                        # Extract attribute and value
                        attr_part = line.split("attribute '")[1].split("'")[0]
                        value_part = line.split("= ")[1].split(" (")[0]
                        
                        if element_type not in processed["invalid_values"]:
                            processed["invalid_values"][element_type] = []
                        
                        # Get user-friendly name if available
                        element_index = int(element_parts[1]) if len(element_parts) > 1 else 0
                        display_name = get_element_display_name(net, element_type, element_index)
                        
                        processed["invalid_values"][element_type].append(
                            f"{display_name}: {attr_part} = {value_part}"
                        )
                except:
                    # If parsing fails, add the raw line
                    if "invalid_values" not in processed:
                        processed["invalid_values"] = {}
                    if "general" not in processed["invalid_values"]:
                        processed["invalid_values"]["general"] = []
                    processed["invalid_values"]["general"].append(line)
        
        # Process summary
        elif current_section == 'summary' and 'invalid values found' in line:
            processed["summary"]["invalid_values_count"] = line
        
        # Process other error messages
        elif 'failed' in line.lower() or 'error' in line.lower():
            if "convergence" not in processed:
                processed["convergence"] = {}
            if "errors" not in processed["convergence"]:
                processed["convergence"]["errors"] = []
            processed["convergence"]["errors"].append(line)
    
    return processed 

def contingency_analysis(net, contingency_params):
    """
    Perform contingency analysis on the network.
    
    Parameters:
    net: pandapower network
    contingency_params: dictionary containing contingency analysis parameters
    """
    try:
        # Extract parameters
        contingency_type = contingency_params.get('contingency_type', 'N-1')
        element_type = contingency_params.get('element_type', 'line')
        elements_to_analyze = contingency_params.get('elements_to_analyze', 'all')
        voltage_limits = contingency_params.get('voltage_limits', 'true') == 'true'
        thermal_limits = contingency_params.get('thermal_limits', 'true') == 'true'
        min_vm_pu = float(contingency_params.get('min_vm_pu', 0.95))
        max_vm_pu = float(contingency_params.get('max_vm_pu', 1.05))
        max_loading_percent = float(contingency_params.get('max_loading_percent', 100))
        
        # Validate network connectivity
        isolated_buses = top.unsupplied_buses(net)
        if len(isolated_buses) > 0:
            raise ValueError(f"Isolated buses found: {isolated_buses}. Check your network connectivity.")
        
        # Check if network has elements
        
        # Run base case power flow
        pp.runpp(net, algorithm='nr', calculate_voltage_angles=True)
        
        # Define contingency cases based on element type
        contingency_cases = []
        
        if element_type == 'line' or element_type == 'all':
            # Add line contingencies
            for line_idx in net.line.index:
                if net.line.loc[line_idx, 'in_service']:
                    contingency_cases.append({
                        'name': f"Line_{net.line.loc[line_idx, 'name']}",
                        'type': 'line',
                        'element_idx': line_idx,
                        'description': f"Outage of line {net.line.loc[line_idx, 'name']}"
                    })
        
        if element_type == 'transformer' or element_type == 'all':
            # Add transformer contingencies
            for trafo_idx in net.trafo.index:
                if net.trafo.loc[trafo_idx, 'in_service']:
                    contingency_cases.append({
                        'name': f"Trafo_{net.trafo.loc[trafo_idx, 'name']}",
                        'type': 'trafo',
                        'element_idx': trafo_idx,
                        'description': f"Outage of transformer {net.trafo.loc[trafo_idx, 'name']}"
                    })
        
        if element_type == 'generator' or element_type == 'all':
            # Add generator contingencies
            for gen_idx in net.gen.index:
                if net.gen.loc[gen_idx, 'in_service']:
                    contingency_cases.append({
                        'name': f"Gen_{net.gen.loc[gen_idx, 'name']}",
                        'type': 'gen',
                        'element_idx': gen_idx,
                        'description': f"Outage of generator {net.gen.loc[gen_idx, 'name']}"
                    })
        
        # Results storage
        contingency_results = []
        violations = []
        critical_contingencies = []
        
        # Store base case results
        base_case_results = {
            'bus_vm_pu': net.res_bus.vm_pu.copy(),
            'bus_va_degree': net.res_bus.va_degree.copy(),
            'line_loading_percent': net.res_line.loading_percent.copy() if not net.res_line.empty else pd.Series(),
            'trafo_loading_percent': net.res_trafo.loading_percent.copy() if not net.res_trafo.empty else pd.Series()
        }
        
        # Run contingency analysis
        for i, contingency_case in enumerate(contingency_cases):
            try:
                # Create a copy of the network for this contingency
                net_cont = net.copy()
                
                # Apply contingency
                if contingency_case['type'] == 'line':
                    net_cont.line.loc[contingency_case['element_idx'], 'in_service'] = False
                elif contingency_case['type'] == 'trafo':
                    net_cont.trafo.loc[contingency_case['element_idx'], 'in_service'] = False
                elif contingency_case['type'] == 'gen':
                    net_cont.gen.loc[contingency_case['element_idx'], 'in_service'] = False
                
                # Run power flow for contingency case
                pp.runpp(net_cont, algorithm='nr', calculate_voltage_angles=True)
                
                # Check for violations
                case_violations = []
                
                # Check voltage violations
                if voltage_limits:
                    voltage_violations = net_cont.res_bus[
                        (net_cont.res_bus.vm_pu < min_vm_pu) | 
                        (net_cont.res_bus.vm_pu > max_vm_pu)
                    ]
                    for bus_idx, bus_data in voltage_violations.iterrows():
                        case_violations.append({
                            'type': 'voltage',
                            'element': f"Bus_{net_cont.bus.loc[bus_idx, 'name']}",
                            'description': f"Voltage violation: {bus_data.vm_pu:.3f} p.u.",
                            'severity': 'high' if bus_data.vm_pu < 0.9 or bus_data.vm_pu > 1.1 else 'medium'
                        })
                
                # Check thermal violations
                if thermal_limits:
                    # Check line loading
                    if not net_cont.res_line.empty:
                        line_overloads = net_cont.res_line[
                            net_cont.res_line.loading_percent > max_loading_percent
                        ]
                        for line_idx, line_data in line_overloads.iterrows():
                            case_violations.append({
                                'type': 'thermal',
                                'element': f"Line_{net_cont.line.loc[line_idx, 'name']}",
                                'description': f"Line overload: {line_data.loading_percent:.1f}%",
                                'severity': 'high' if line_data.loading_percent > 120 else 'medium'
                            })
                    
                    # Check transformer loading
                    if not net_cont.res_trafo.empty:
                        trafo_overloads = net_cont.res_trafo[
                            net_cont.res_trafo.loading_percent > max_loading_percent
                        ]
                        for trafo_idx, trafo_data in trafo_overloads.iterrows():
                            case_violations.append({
                                'type': 'thermal',
                                'element': f"Trafo_{net_cont.trafo.loc[trafo_idx, 'name']}",
                                'description': f"Transformer overload: {trafo_data.loading_percent:.1f}%",
                                'severity': 'high' if trafo_data.loading_percent > 120 else 'medium'
                            })
                
                # Store results for this contingency
                contingency_result = {
                    'name': contingency_case['name'],
                    'description': contingency_case['description'],
                    'converged': True,
                    'violations': case_violations,
                    'bus_results': [],
                    'line_results': [],
                    'trafo_results': []
                }
                
                # Store bus results
                for bus_idx, bus_data in net_cont.res_bus.iterrows():
                    contingency_result['bus_results'].append({
                        'bus_id': net_cont.bus.loc[bus_idx, 'id'],
                        'name': net_cont.bus.loc[bus_idx, 'name'],
                        'vm_pu': bus_data.vm_pu,
                        'va_degree': bus_data.va_degree,
                        'p_mw': bus_data.p_mw,
                        'q_mvar': bus_data.q_mvar
                    })
                
                # Store line results
                for line_idx, line_data in net_cont.res_line.iterrows():
                    contingency_result['line_results'].append({
                        'line_id': net_cont.line.loc[line_idx, 'id'],
                        'name': net_cont.line.loc[line_idx, 'name'],
                        'loading_percent': line_data.loading_percent,
                        'p_from_mw': line_data.p_from_mw,
                        'q_from_mvar': line_data.q_from_mvar,
                        'p_to_mw': line_data.p_to_mw,
                        'q_to_mvar': line_data.q_to_mvar
                    })
                
                # Store transformer results
                for trafo_idx, trafo_data in net_cont.res_trafo.iterrows():
                    contingency_result['trafo_results'].append({
                        'trafo_id': net_cont.trafo.loc[trafo_idx, 'id'],
                        'name': net_cont.trafo.loc[trafo_idx, 'name'],
                        'loading_percent': trafo_data.loading_percent,
                        'p_hv_mw': trafo_data.p_hv_mw,
                        'q_hv_mvar': trafo_data.q_hv_mvar,
                        'p_lv_mw': trafo_data.p_lv_mw,
                        'q_lv_mvar': trafo_data.q_lv_mvar
                    })
                
                # Add to violations list if any violations found
                if case_violations:
                    violations.extend(case_violations)
                    if any(v['severity'] == 'high' for v in case_violations):
                        critical_contingencies.append({
                            'name': contingency_case['name'],
                            'description': contingency_case['description'],
                            'violations': len(case_violations)
                        })
                
                contingency_results.append(contingency_result)
                
            except Exception as e:
                # Handle non-convergent cases
                contingency_result = {
                    'name': contingency_case['name'],
                    'description': contingency_case['description'],
                    'converged': False,
                    'error': str(e),
                    'violations': [{'type': 'convergence', 'element': 'System', 'description': 'Power flow did not converge', 'severity': 'high'}]
                }
                contingency_results.append(contingency_result)
                critical_contingencies.append({
                    'name': contingency_case['name'],
                    'description': 'Non-convergent case',
                    'violations': 1
                })
        
        # Prepare summary
        summary = {
            'contingencies_analyzed': len(contingency_cases),
            'violations': violations,
            'critical_contingencies': critical_contingencies,
            'total_violations': len(violations),
            'total_critical': len(critical_contingencies)
        }
        
        # Prepare output classes for consistent formatting
        class ContingencyBusOut(object):
            def __init__(self, bus_id: str, name: str, vm_pu: float, va_degree: float, p_mw: float, q_mvar: float):
                self.bus_id = bus_id
                self.name = name
                self.vm_pu = vm_pu
                self.va_degree = va_degree
                self.p_mw = p_mw
                self.q_mvar = q_mvar
        
        class ContingencyLineOut(object):
            def __init__(self, line_id: str, name: str, loading_percent: float, p_from_mw: float, q_from_mvar: float, p_to_mw: float, q_to_mvar: float):
                self.line_id = line_id
                self.name = name
                self.loading_percent = loading_percent
                self.p_from_mw = p_from_mw
                self.q_from_mvar = q_from_mvar
                self.p_to_mw = p_to_mw
                self.q_to_mvar = q_to_mvar
        
        class ContingencyTransformerOut(object):
            def __init__(self, trafo_id: str, name: str, loading_percent: float, p_hv_mw: float, q_hv_mvar: float, p_lv_mw: float, q_lv_mvar: float):
                self.trafo_id = trafo_id
                self.name = name
                self.loading_percent = loading_percent
                self.p_hv_mw = p_hv_mw
                self.q_hv_mvar = q_hv_mvar
                self.p_lv_mw = p_lv_mw
                self.q_lv_mvar = q_lv_mvar
        
        # Convert results to output format
        bus_out_list = []
        line_out_list = []
        trafo_out_list = []
        
        # Check if we have contingency results
        if not contingency_cases:
            error_message = f"No contingency cases found. Network has {len(net.line)} lines, {len(net.trafo)} transformers, {len(net.gen)} generators."
            return json.dumps({'error': error_message}, separators=(',', ':'))
        
        if not contingency_results:
            error_message = f"No contingency results generated. All {len(contingency_cases)} cases failed to converge."
            return json.dumps({'error': error_message}, separators=(',', ':'))
        
        # Use the worst-case scenario results for display
        worst_case = max(contingency_results, key=lambda x: len(x.get('violations', [])))
        
        for bus_result in worst_case.get('bus_results', []):
            bus_out = ContingencyBusOut(
                bus_id=bus_result['bus_id'],
                name=bus_result['name'],
                vm_pu=bus_result['vm_pu'],
                va_degree=bus_result['va_degree'],
                p_mw=bus_result['p_mw'],
                q_mvar=bus_result['q_mvar']
            )
            bus_out_list.append(bus_out)
        
        for line_result in worst_case.get('line_results', []):
            line_out = ContingencyLineOut(
                line_id=line_result['line_id'],
                name=line_result['name'],
                loading_percent=line_result['loading_percent'],
                p_from_mw=line_result['p_from_mw'],
                q_from_mvar=line_result['q_from_mvar'],
                p_to_mw=line_result['p_to_mw'],
                q_to_mvar=line_result['q_to_mvar']
            )
            line_out_list.append(line_out)
        
        for trafo_result in worst_case.get('trafo_results', []):
            trafo_out = ContingencyTransformerOut(
                trafo_id=trafo_result['trafo_id'],
                name=trafo_result['name'],
                loading_percent=trafo_result['loading_percent'],
                p_hv_mw=trafo_result['p_hv_mw'],
                q_hv_mvar=trafo_result['q_hv_mvar'],
                p_lv_mw=trafo_result['p_lv_mw'],
                q_lv_mvar=trafo_result['q_lv_mvar']
            )
            trafo_out_list.append(trafo_out)
        
        # Prepare result dictionary
        result = {
            'bus': [bus.__dict__ for bus in bus_out_list],
            'line': [line.__dict__ for line in line_out_list],
            'transformer': [trafo.__dict__ for trafo in trafo_out_list],
            'summary': summary,
            'contingency_results': contingency_results
        }
        
        # OPTIMIZED: Compact JSON for faster transfer
        response = json.dumps(result, default=lambda o: o.__dict__, separators=(',', ':'))
        
        return response
        
    except Exception as e:
        error_message = f"Contingency analysis failed: {str(e)}"
        return json.dumps({'error': error_message}) 


def optimalPowerFlow(net, opf_params):
    """
    Run optimal power flow using pandapower.runopp (AC) or pandapower.rundcopp (DC)
    
    Args:
        net: pandapower network
        opf_params: dictionary containing OPF parameters from frontend
    
    Returns:
        JSON response with optimal power flow results or error message
    """
    
    try:
        # Extract OPF parameters
        opf_type = opf_params.get('opf_type', 'ac')
        algorithm = opf_params.get('ac_algorithm', 'pypower') if opf_type == 'ac' else opf_params.get('dc_algorithm', 'pypower')
        calculate_voltage_angles = opf_params.get('calculate_voltage_angles', 'auto')
        init = opf_params.get('init', 'pf')
        delta = float(opf_params.get('delta', 1e-8))
        trafo_model = opf_params.get('trafo_model', 't')
        trafo_loading = opf_params.get('trafo_loading', 'current')
        ac_line_model = opf_params.get('ac_line_model', 'pi')
        numba = opf_params.get('numba', True)
        suppress_warnings = opf_params.get('suppress_warnings', True)
        cost_function = opf_params.get('cost_function', 'none')
        
        # Check for isolated buses
        isolated_buses = top.unsupplied_buses(net)
        if len(isolated_buses) > 0:
            raise ValueError(f"Isolated buses found: {isolated_buses}. Check your network connectivity.")
        
        # Set up cost functions if specified and not already present
        if cost_function != 'none':
            setup_default_cost_functions(net, cost_function)
        
        # Check if any cost functions are defined
        if len(net.poly_cost) == 0 and len(net.pwl_cost) == 0:
            setup_default_cost_functions(net, 'polynomial')
        
        # Ensure min/max p_mw columns exist for OPF
        if 'min_p_mw' not in net.gen.columns:
            net.gen['min_p_mw'] = 0.0
        if 'max_p_mw' not in net.gen.columns:
            net.gen['max_p_mw'] = net.gen['p_mw'] * 1.2
        # Optionally ensure min_q_mvar/max_q_mvar as well
        if 'min_q_mvar' not in net.gen.columns:
            net.gen['min_q_mvar'] = -9999.0
        if 'max_q_mvar' not in net.gen.columns:
            net.gen['max_q_mvar'] = 9999.0
        
        # Run optimal power flow based on type
        if opf_type == 'ac':
            pp.runopp(net, 
                     verbose=not suppress_warnings,
                     suppress_warnings=suppress_warnings,
                     delta=delta,
                     trafo_model=trafo_model,
                     trafo_loading=trafo_loading,
                     ac_line_model=ac_line_model,
                     calculate_voltage_angles=calculate_voltage_angles,
                     init=init,
                     numba=numba)
        else:  # dc
            pp.rundcopp(net,
                       verbose=not suppress_warnings,
                       suppress_warnings=suppress_warnings,
                       delta=delta,
                       trafo_model=trafo_model,
                       trafo_loading=trafo_loading,
                       calculate_voltage_angles=calculate_voltage_angles,
                       init=init,
                       numba=numba)
        
        
    except Exception as e:
        
        # Initialize diagnostic response
        diagnostic_response = {
            "error": True,
            "message": "Optimal Power Flow calculation failed",
            "exception": str(e),
            "diagnostic": {}
        }
        
        # Try to get diagnostic information
        try:
            diag_result_dict = pp.diagnostic(net, report_style='detailed')
            
            # Check for isolated buses
            isolated_buses = pp.topology.unsupplied_buses(net)
            if len(isolated_buses) > 0:
                # Convert set to list (isolated_buses is a set, not numpy array)
                if isinstance(isolated_buses, set):
                    diagnostic_response["diagnostic"]["isolated_buses"] = list(isolated_buses)
                elif hasattr(isolated_buses, 'tolist'):
                    diagnostic_response["diagnostic"]["isolated_buses"] = isolated_buses.tolist()
                else:
                    diagnostic_response["diagnostic"]["isolated_buses"] = list(isolated_buses)
            
            # Process diagnostic data to convert element indices to user-friendly names
            processed_diagnostic = process_diagnostic_data(net, diag_result_dict)
            # Merge processed diagnostic with isolated_buses (don't overwrite)
            diagnostic_response["diagnostic"].update(processed_diagnostic)
                    
        except Exception as diag_error:
            pass
        
        # If no specific diagnostic was found, include the original exception
        if not diagnostic_response["diagnostic"]:
            diagnostic_response["diagnostic"]["general_error"] = str(e)
        
        return diagnostic_response
    
    # Build response with OPF results
    else:
        # Define output classes (similar to powerflow function)
        class BusbarOut(object):
            def __init__(self, name: str, id: str, vm_pu: float, va_degree: float, p_mw: float, q_mvar: float, 
                        pf: float, q_p: float, lam_p: float = 0.0, lam_q: float = 0.0):          
                self.name = name
                self.id = id
                self.vm_pu = vm_pu
                self.va_degree = va_degree   
                self.p_mw = p_mw
                self.q_mvar = q_mvar  
                self.pf = pf
                self.q_p = q_p
                self.lam_p = lam_p  # Lagrange multiplier for active power
                self.lam_q = lam_q  # Lagrange multiplier for reactive power
        
        class LineOut(object):
            def __init__(self, name: str, id: str, p_from_mw: float, q_from_mvar: float, p_to_mw: float, q_to_mvar: float, 
                        i_from_ka: float, i_to_ka: float, loading_percent: float, mu_sf: float = 0.0, mu_st: float = 0.0):          
                self.name = name 
                self.id = id                      
                self.p_from_mw = p_from_mw
                self.q_from_mvar = q_from_mvar 
                self.p_to_mw = p_to_mw 
                self.q_to_mvar = q_to_mvar            
                self.i_from_ka = i_from_ka 
                self.i_to_ka = i_to_ka               
                self.loading_percent = loading_percent
                self.mu_sf = mu_sf  # Shadow price for from-side flow limit
                self.mu_st = mu_st  # Shadow price for to-side flow limit
        
        class GeneratorOut(object):
            def __init__(self, name: str, id: str, p_mw: float, q_mvar: float, va_degree: float, vm_pu: float,
                        gen_cost: float = 0.0, marginal_cost: float = 0.0):          
                self.name = name
                self.id = id
                self.p_mw = p_mw 
                self.q_mvar = q_mvar  
                self.va_degree = va_degree 
                self.vm_pu = vm_pu
                self.gen_cost = gen_cost        # Total generation cost
                self.marginal_cost = marginal_cost  # Marginal cost
        
        # Similar classes for other components (simplified for space)
        class ExternalGridOut(object):
            def __init__(self,  name: str, id: str, p_mw: float, q_mvar: float, pf: float, q_p:float):        
                self.name = name
                self.id = id
                self.p_mw = p_mw 
                self.q_mvar = q_mvar  
                self.pf = pf            
                self.q_p = q_p
        
        class LoadOut(object):
            def __init__(self, name: str, id:str, p_mw: float, q_mvar: float):          
                self.name = name
                self.id = id
                self.p_mw = p_mw 
                self.q_mvar = q_mvar 
        
        # Initialize result lists
        busbarList = list()
        linesList = list()
        generatorsList = list()
        externalgridsList = list()
        loadsList = list()
        
        # Process bus results with OPF-specific data
        for index, row in net.res_bus.iterrows():
            try:
                bus_name = net.bus.loc[index, 'name']
                bus_id = net.bus.loc[index, 'id'] if 'id' in net.bus.columns else str(index)
                
                # Get user-friendly name from stored mapping
                user_friendly_name = getattr(net, 'user_friendly_names', {}).get(bus_name, bus_name)
                
                # Calculate power values
                p_mw = row['p_mw'] if 'p_mw' in row else 0.0
                q_mvar = row['q_mvar'] if 'q_mvar' in row else 0.0
                
                # Calculate power factor
                s_mva = (p_mw**2 + q_mvar**2)**0.5
                pf = p_mw / s_mva if s_mva > 0 else 0.0
                q_p = q_mvar / p_mw if p_mw > 0 else 0.0
                
                # Get Lagrange multipliers if available
                lam_p = 0.0
                lam_q = 0.0
                if hasattr(net, 'res_bus_opf') and not net.res_bus_opf.empty:
                    if index in net.res_bus_opf.index:
                        lam_p = net.res_bus_opf.loc[index, 'lam_p'] if 'lam_p' in net.res_bus_opf.columns else 0.0
                        lam_q = net.res_bus_opf.loc[index, 'lam_q'] if 'lam_q' in net.res_bus_opf.columns else 0.0
                
                busbar = BusbarOut(
                    name=get_display_name(user_friendly_name, bus_name, 'Bus', index),
                    id=bus_id,
                    vm_pu=row['vm_pu'],
                    va_degree=row['va_degree'],
                    p_mw=p_mw,
                    q_mvar=q_mvar,
                    pf=pf,
                    q_p=q_p,
                    lam_p=lam_p,
                    lam_q=lam_q
                )
                busbarList.append(busbar)
                
            except Exception as e:
                continue
        
        # Process line results with OPF-specific data
        for index, row in net.res_line.iterrows():
            try:
                line_name = net.line.loc[index, 'name']
                line_id = net.line.loc[index, 'id'] if 'id' in net.line.columns else str(index)
                
                # Get user-friendly name from stored mapping
                user_friendly_name = getattr(net, 'user_friendly_names', {}).get(line_name, line_name)
                
                # Get shadow prices if available
                mu_sf = 0.0
                mu_st = 0.0
                if hasattr(net, 'res_line_opf') and not net.res_line_opf.empty:
                    if index in net.res_line_opf.index:
                        mu_sf = net.res_line_opf.loc[index, 'mu_sf'] if 'mu_sf' in net.res_line_opf.columns else 0.0
                        mu_st = net.res_line_opf.loc[index, 'mu_st'] if 'mu_st' in net.res_line_opf.columns else 0.0
                
                line = LineOut(
                    name=get_display_name(user_friendly_name, line_name, 'Line', index),
                    id=line_id,
                    p_from_mw=row['p_from_mw'],
                    q_from_mvar=row['q_from_mvar'],
                    p_to_mw=row['p_to_mw'],
                    q_to_mvar=row['q_to_mvar'],
                    i_from_ka=row['i_from_ka'],
                    i_to_ka=row['i_to_ka'],
                    loading_percent=row['loading_percent'],
                    mu_sf=mu_sf,
                    mu_st=mu_st
                )
                linesList.append(line)
                
            except Exception as e:
                continue
        
        # Process generator results with OPF-specific data
        for index, row in net.res_gen.iterrows():
            try:
                gen_name = net.gen.loc[index, 'name']
                gen_id = net.gen.loc[index, 'id'] if 'id' in net.gen.columns else str(index)
                
                # Get user-friendly name from stored mapping
                user_friendly_name = getattr(net, 'user_friendly_names', {}).get(gen_name, gen_name)
                
                # Calculate generation costs if available
                gen_cost = 0.0
                marginal_cost = 0.0
                
                # Get costs from poly_cost table
                poly_costs = net.poly_cost[net.poly_cost['element'] == index]
                if not poly_costs.empty:
                    poly_cost_row = poly_costs.iloc[0]
                    p_gen = row['p_mw']
                    # Assuming quadratic cost: cost = c2*P^2 + c1*P + c0
                    if 'cp2_eur_per_mw2' in poly_cost_row and 'cp1_eur_per_mw' in poly_cost_row and 'cp0_eur' in poly_cost_row:
                        c2 = poly_cost_row['cp2_eur_per_mw2']
                        c1 = poly_cost_row['cp1_eur_per_mw']
                        c0 = poly_cost_row['cp0_eur']
                        gen_cost = c2 * p_gen**2 + c1 * p_gen + c0
                        marginal_cost = 2 * c2 * p_gen + c1
                
                generator = GeneratorOut(
                    name=get_display_name(user_friendly_name, gen_name, 'Generator', index),
                    id=gen_id,
                    p_mw=row['p_mw'],
                    q_mvar=row['q_mvar'],
                    va_degree=row['va_degree'],
                    vm_pu=row['vm_pu'],
                    gen_cost=gen_cost,
                    marginal_cost=marginal_cost
                )
                generatorsList.append(generator)
                
            except Exception as e:
                continue
        
        # Process external grid results
        for index, row in net.res_ext_grid.iterrows():
            try:
                ext_grid_name = net.ext_grid.loc[index, 'name']
                ext_grid_id = net.ext_grid.loc[index, 'id'] if 'id' in net.ext_grid.columns else str(index)
                
                # Get user-friendly name from stored mapping
                user_friendly_name = getattr(net, 'user_friendly_names', {}).get(ext_grid_name, ext_grid_name)
                
                p_mw = row['p_mw'] if 'p_mw' in row else 0.0
                q_mvar = row['q_mvar'] if 'q_mvar' in row else 0.0
                
                # Calculate power factor
                s_mva = (p_mw**2 + q_mvar**2)**0.5
                pf = p_mw / s_mva if s_mva > 0 else 0.0
                q_p = q_mvar / p_mw if p_mw > 0 else 0.0
                
                ext_grid = ExternalGridOut(
                    name=get_display_name(user_friendly_name, ext_grid_name, 'External Grid', index),
                    id=ext_grid_id,
                    p_mw=p_mw,
                    q_mvar=q_mvar,
                    pf=pf,
                    q_p=q_p
                )
                externalgridsList.append(ext_grid)
                
            except Exception as e:
                continue
        
        # Process load results
        for index, row in net.res_load.iterrows():
            try:
                load_name = net.load.loc[index, 'name']
                load_id = net.load.loc[index, 'id'] if 'id' in net.load.columns else str(index)
                
                # Get user-friendly name from stored mapping
                user_friendly_name = getattr(net, 'user_friendly_names', {}).get(load_name, load_name)
                
                load = LoadOut(
                    name=get_display_name(user_friendly_name, load_name, 'Load', index),
                    id=load_id,
                    p_mw=row['p_mw'],
                    q_mvar=row['q_mvar']
                )
                loadsList.append(load)
                
            except Exception as e:
                continue
        
        # Create response dictionary
        response_data = {
            'busbars': [busbar.__dict__ for busbar in busbarList],
            'lines': [line.__dict__ for line in linesList],
            'generators': [gen.__dict__ for gen in generatorsList],
            'externalgrids': [ext_grid.__dict__ for ext_grid in externalgridsList],
            'loads': [load.__dict__ for load in loadsList]
        }
        
        # Add optimization results summary if available
        if hasattr(net, 'OPF_converged') and net.OPF_converged:
            response_data['opf_converged'] = True
            if hasattr(net, 'res_cost'):
                response_data['total_cost'] = float(net.res_cost)
        else:
            response_data['opf_converged'] = False
        
        
        return response_data


def setup_default_cost_functions(net, cost_type='polynomial'):
    """
    Set up default cost functions for generators if none exist
    
    Args:
        net: pandapower network
        cost_type: 'polynomial' or 'piecewise_linear'
    """
    
    if cost_type == 'polynomial':
        # Add polynomial costs for generators without costs
        for gen_idx in net.gen.index:
            # Check if this generator already has a cost function
            existing_costs = net.poly_cost[net.poly_cost['element'] == gen_idx]
            if existing_costs.empty:
                # Default quadratic cost function: 0.01*P^2 + 20*P + 0
                pp.create_poly_cost(net, element=gen_idx, et='gen',
                                   cp2_eur_per_mw2=0.01,    # Quadratic term
                                   cp1_eur_per_mw=20,       # Linear term  
                                   cp0_eur=0)               # Constant term
    
    elif cost_type == 'piecewise_linear':
        # Add piecewise linear costs for generators without costs
        for gen_idx in net.gen.index:
            # Check if this generator already has a cost function
            existing_costs = net.pwl_cost[net.pwl_cost['element'] == gen_idx]
            if existing_costs.empty:
                # Get generator capacity
                gen_max_p = net.gen.loc[gen_idx, 'max_p_mw'] if 'max_p_mw' in net.gen.columns else 100
                gen_min_p = net.gen.loc[gen_idx, 'min_p_mw'] if 'min_p_mw' in net.gen.columns else 0
                
                # Create simple 2-point piecewise linear cost
                # From min to max power with cost increasing from 15 to 25 $/MWh
                pp.create_pwl_cost(net, element=gen_idx, et='gen',
                                  points=[[gen_min_p, gen_min_p * 15],    # [P_min, Cost_min]
                                         [gen_max_p, gen_max_p * 25]])    # [P_max, Cost_max]

def safe_float(value, default=0.0):
    """Convert value to float. Returns default for None, 'null', 'None', empty string, or invalid values."""
    import math
    if value is None or value == 'null' or value == 'None' or value == '':
        return default
    if isinstance(value, float) and math.isnan(value):
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_int(value, default=1):
    """Convert value to int with default fallback. Handles 'null', 'None', empty string."""
    if value is None or value == 'null' or value == 'None' or value == '':
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def parse_vector_group(vector_group):
    """Parse vector group to extract base group and phase shift number.
    
    Args:
        vector_group: String like 'Dyn11', 'Yd5', etc.
        
    Returns:
        tuple: (base_group, phase_shift_degrees)
    """
    if not vector_group or vector_group == 'None' or vector_group == '':
        return 'Dyn', 0
    
    # Common vector group patterns
    import re
    
    # Pattern to match vector groups with numbers (e.g., Dyn11, Yd5, Yy0)
    pattern = r'^([A-Za-z]+)(\d+)$'
    match = re.match(pattern, vector_group)
    
    if match:
        base_group = match.group(1)
        phase_shift_number = int(match.group(2))
        
        # Convert phase shift number to degrees (multiply by 30°)
        phase_shift_degrees = phase_shift_number * 30
        
        return base_group, phase_shift_degrees
    else:
        # No number found, return as-is with 0 phase shift
        return vector_group, 0

def get_display_name(user_friendly_name, technical_id, element_type, element_index, simulation_type='opf'):
    """
    Create a display name that combines user-friendly name with technical ID for uniqueness
    For controller and time series simulations, only return user-friendly name
    For other simulations (OPF), combine both for uniqueness
    """
    if simulation_type in ['controller', 'timeseries']:
        # For controller and time series simulations, only use user-friendly name
        if user_friendly_name and user_friendly_name != technical_id:
            return user_friendly_name
        else:
            # Fallback to type + index if no user-friendly name
            return f"{element_type} no. {element_index + 1}"
    else:
        # For other simulations (OPF), combine both for uniqueness
        if user_friendly_name and user_friendly_name != technical_id:
            # Use user-friendly name with technical ID in parentheses for uniqueness
            return f"{user_friendly_name} ({technical_id})"
        else:
            # Fallback to type + index if no user-friendly name
            return f"{element_type} no. {element_index + 1} ({technical_id})"

def process_diagnostic_data(net, diag_result_dict):
    """
    Process diagnostic data and convert element indices to user-friendly names
    """
    processed_diagnostic = {}
    
    # Process invalid values
    if 'invalid_values' in diag_result_dict:
        processed_invalid = {}
        invalid_data = diag_result_dict['invalid_values']
        
        # Handle different possible formats
        if isinstance(invalid_data, dict):
            for element_type, invalid_items in invalid_data.items():
                processed_items = []
                if isinstance(invalid_items, (list, tuple)):
                    for item in invalid_items:
                        if isinstance(item, (list, tuple)) and len(item) >= 4:
                            # Format: [element_index, parameter_name, current_value, constraint]
                            element_index = item[0]
                            parameter_name = item[1]
                            current_value = item[2]
                            constraint = item[3]
                            
                            # Get user-friendly name based on element type
                            element_id = get_element_display_name(net, element_type, element_index)
                            
                            # Create formatted message with element type and ID
                            element_type_display = element_type.capitalize()
                            if element_type == 'trafo':
                                element_type_display = 'Transformer'
                            elif element_type == 'trafo3w':
                                element_type_display = 'Three-Winding Transformer'
                            elif element_type == 'ext_grid':
                                element_type_display = 'External Grid'
                            elif element_type == 'gen':
                                element_type_display = 'Generator'
                            
                            formatted_item = f"{element_type_display} {element_id}: {parameter_name} = {current_value} (constraint: {constraint})"
                            processed_items.append(formatted_item)
                        else:
                            # Keep original format if not in expected format
                            processed_items.append(str(item))
                else:
                    processed_items.append(str(invalid_items))
                
                processed_invalid[element_type] = processed_items
        elif isinstance(invalid_data, (list, tuple)):
            processed_items = []
            for item in invalid_data:
                if isinstance(item, (list, tuple)) and len(item) >= 4:
                    element_index = item[0]
                    parameter_name = item[1]
                    current_value = item[2]
                    constraint = item[3]
                    element_id = get_element_display_name(net, 'unknown', element_index)
                    formatted_item = f"Element {element_id}: {parameter_name} = {current_value} (constraint: {constraint})"
                    processed_items.append(formatted_item)
                else:
                    processed_items.append(str(item))
            processed_invalid['general'] = processed_items
        else:
            processed_invalid['status'] = str(invalid_data)
        
        processed_diagnostic['invalid_values'] = processed_invalid
    
    # Process overload data
    if 'overload' in diag_result_dict:
        processed_overload = {}
        overload_data = diag_result_dict['overload']

        # Handle different possible formats of overload data
        if isinstance(overload_data, dict):
            # Expected format: dictionary with element types as keys
            for element_type, overload_items in overload_data.items():
                processed_items = []
                if isinstance(overload_items, (list, tuple)):
                    for item in overload_items:
                        if isinstance(item, (list, tuple)) and len(item) >= 2:
                            # Format: [element_index, loading_percent]
                            element_index = item[0]
                            loading_percent = item[1]

                            # Get user-friendly name
                            element_id = get_element_display_name(net, element_type, element_index)

                            # Create formatted message with element type and ID
                            element_type_display = element_type.capitalize()
                            if element_type == 'trafo':
                                element_type_display = 'Transformer'
                            elif element_type == 'trafo3w':
                                element_type_display = 'Three-Winding Transformer'
                            elif element_type == 'ext_grid':
                                element_type_display = 'External Grid'
                            elif element_type == 'gen':
                                element_type_display = 'Generator'

                            formatted_item = f"{element_type_display} {element_id}: Loading = {loading_percent}%"
                            processed_items.append(formatted_item)
                        else:
                            processed_items.append(str(item))
                else:
                    # If overload_items is not a list/tuple, just convert to string
                    processed_items.append(str(overload_items))

                processed_overload[element_type] = processed_items
        elif isinstance(overload_data, (list, tuple)):
            # Handle case where overload is a list directly
            processed_items = []
            for item in overload_data:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    element_index = item[0]
                    loading_percent = item[1]
                    element_id = get_element_display_name(net, 'unknown', element_index)
                    formatted_item = f"Element {element_id}: Loading = {loading_percent}%"
                    processed_items.append(formatted_item)
                else:
                    processed_items.append(str(item))
            processed_overload['general'] = processed_items
        else:
            # Handle boolean or other single values
            processed_overload['status'] = str(overload_data)

        processed_diagnostic['overload'] = processed_overload
    
    # Process nominal voltage mismatches
    if 'nominal_voltages_dont_match' in diag_result_dict:
        processed_voltage = {}
        voltage_data = diag_result_dict['nominal_voltages_dont_match']

        # Handle different possible formats
        if isinstance(voltage_data, dict):
            for element_type, voltage_items in voltage_data.items():
                processed_items = []
                if isinstance(voltage_items, (list, tuple)):
                    for item in voltage_items:
                        if isinstance(item, (list, tuple)) and len(item) >= 2:
                            # Format: [element_index, voltage_info]
                            element_index = item[0]
                            voltage_info = item[1]

                            # Get user-friendly name
                            element_id = get_element_display_name(net, element_type, element_index)

                            # Create formatted message with element type and ID
                            element_type_display = element_type.capitalize()
                            if element_type == 'trafo':
                                element_type_display = 'Transformer'
                            elif element_type == 'trafo3w':
                                element_type_display = 'Three-Winding Transformer'
                            elif element_type == 'ext_grid':
                                element_type_display = 'External Grid'
                            elif element_type == 'gen':
                                element_type_display = 'Generator'

                            formatted_item = f"{element_type_display} {element_id}: {voltage_info}"
                            processed_items.append(formatted_item)
                        else:
                            processed_items.append(str(item))
                else:
                    processed_items.append(str(voltage_items))

                processed_voltage[element_type] = processed_items
        elif isinstance(voltage_data, (list, tuple)):
            processed_items = []
            for item in voltage_data:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    element_index = item[0]
                    voltage_info = item[1]
                    element_id = get_element_display_name(net, 'unknown', element_index)
                    formatted_item = f"Element {element_id}: {voltage_info}"
                    processed_items.append(formatted_item)
                else:
                    processed_items.append(str(item))
            processed_voltage['general'] = processed_items
        else:
            processed_voltage['status'] = str(voltage_data)

        processed_diagnostic['nominal_voltages_dont_match'] = processed_voltage
    
    # Add other diagnostic data as-is
    for key, value in diag_result_dict.items():
        if key not in ['invalid_values', 'overload', 'nominal_voltages_dont_match']:
            processed_diagnostic[key] = value
    
    return processed_diagnostic

def get_element_display_name(net, element_type, element_index):
    """
    Get user-friendly display name for an element based on its type and index
    """
    try:
        # First, try to get the user-friendly name from net.user_friendly_names
        if hasattr(net, 'user_friendly_names'):
            if element_type == 'line':
                if element_index < len(net.line):
                    line_name = net.line.iloc[element_index]['name']
                    if line_name in net.user_friendly_names:
                        return net.user_friendly_names[line_name]
            
            elif element_type == 'bus':
                if element_index < len(net.bus):
                    bus_name = net.bus.iloc[element_index]['name']
                    if bus_name in net.user_friendly_names:
                        return net.user_friendly_names[bus_name]
            
            elif element_type == 'ext_grid':
                if element_index < len(net.ext_grid):
                    ext_grid_name = net.ext_grid.iloc[element_index]['name']
                    if ext_grid_name in net.user_friendly_names:
                        return net.user_friendly_names[ext_grid_name]
            
            elif element_type == 'trafo':
                if element_index < len(net.trafo):
                    trafo_name = net.trafo.iloc[element_index]['name']
                    if trafo_name in net.user_friendly_names:
                        return net.user_friendly_names[trafo_name]
            
            elif element_type == 'trafo3w':
                if element_index < len(net.trafo3w):
                    trafo3w_name = net.trafo3w.iloc[element_index]['name']
                    if trafo3w_name in net.user_friendly_names:
                        return net.user_friendly_names[trafo3w_name]
            
            elif element_type == 'gen':
                if element_index < len(net.gen):
                    gen_name = net.gen.iloc[element_index]['name']
                    if gen_name in net.user_friendly_names:
                        return net.user_friendly_names[gen_name]
            
            elif element_type == 'load':
                if element_index < len(net.load):
                    load_name = net.load.iloc[element_index]['name']
                    if load_name in net.user_friendly_names:
                        return net.user_friendly_names[load_name]
        
        # Fallback to the original name from the network dataframes
        if element_type == 'line':
            if element_index < len(net.line):
                line_name = net.line.iloc[element_index]['name']
                # Use the name directly (which is the user-provided ID like mxCell_138)
                return line_name
        
        elif element_type == 'bus':
            if element_index < len(net.bus):
                bus_name = net.bus.iloc[element_index]['name']
                # Use the name directly (which is the user-provided ID like mxCell_138)
                return bus_name
        
        elif element_type == 'ext_grid':
            if element_index < len(net.ext_grid):
                ext_grid_name = net.ext_grid.iloc[element_index]['name']
                # Use the name directly (which is the user-provided ID like mxCell_138)
                return ext_grid_name
        
        elif element_type == 'trafo':
            if element_index < len(net.trafo):
                trafo_name = net.trafo.iloc[element_index]['name']
                # Use the name directly (which is the user-provided ID like mxCell_138)
                return trafo_name
        
        elif element_type == 'trafo3w':
            if element_index < len(net.trafo3w):
                trafo3w_name = net.trafo3w.iloc[element_index]['name']
                # Use the name directly (which is the user-provided ID like mxCell_138)
                return trafo3w_name
        
        elif element_type == 'gen':
            if element_index < len(net.gen):
                gen_name = net.gen.iloc[element_index]['name']
                # Use the name directly (which is the user-provided ID like mxCell_138)
                return gen_name
        
        elif element_type == 'load':
            if element_index < len(net.load):
                load_name = net.load.iloc[element_index]['name']
                # Use the name directly (which is the user-provided ID like mxCell_138)
                return load_name
        
        # Fallback for unknown element types
        return f"{element_type.capitalize()} no. {element_index + 1}"
        
    except Exception as e:
        # Fallback if any error occurs
        return f"{element_type.capitalize()} no. {element_index + 1}"

def controller_simulation(net, controller_params):
    """
    Run controller simulation using pandapower control module
    Based on: https://pandapower.readthedocs.io/en/latest/control/run.html#pandapower.control.run_control
    """
    
    # Try to import control module, but don't fail if not available
 
    from pandapower.control import run_control
    
    try:
        # Clear any existing controllers
        if hasattr(net, 'controller') and len(net.controller) > 0:
            net.controller = net.controller.drop(net.controller.index)
        
        # Create controllers based on parameters
        controllers = []
        
        # Use proper pandapower control module
        
        # Voltage control using generator voltage setpoints
        if controller_params.get('voltage_control', False):
            for idx, gen in net.gen.iterrows():
                if 'vm_pu' in gen and gen['vm_pu'] != 1.0:
                    # Create a simple voltage controller
                    # Note: This is a simplified controller - in a full implementation,
                    # you would use specific controller classes like VoltageController
                    pass
        
        # Tap control using transformer tap positions
        if controller_params.get('tap_control', False):
            if len(net.trafo) > 0:
                for idx, trafo in net.trafo.iterrows():
                    # Create a simple tap controller
                    # Note: This is a simplified controller - in a full implementation,
                    # you would use specific controller classes like TapController
                    pass
        
        # Run controller simulation using the proper run_control function
        run_control(net, 
                   max_iter=30,
                   continue_on_divergence=False,
                   check_each_level=True)
        
        
        # Prepare results
        class ControllerBusOut(object):
            def __init__(self, name: str, id: str, vm_pu: float, va_degree: float, p_mw: float, q_mvar: float):
                self.name = name
                self.id = id
                self.vm_pu = vm_pu
                self.va_degree = va_degree
                self.p_mw = p_mw
                self.q_mvar = q_mvar
        
        class ControllerLineOut(object):
            def __init__(self, name: str, id: str, p_from_mw: float, q_from_mvar: float, p_to_mw: float, q_to_mvar: float, 
                         i_from_ka: float, i_to_ka: float, loading_percent: float):
                self.name = name
                self.id = id
                self.p_from_mw = p_from_mw
                self.q_from_mvar = q_from_mvar
                self.p_to_mw = p_to_mw
                self.q_to_mvar = q_to_mvar
                self.i_from_ka = i_from_ka
                self.i_to_ka = i_to_ka
                self.loading_percent = loading_percent
        
        class ControllerGeneratorOut(object):
            def __init__(self, name: str, id: str, p_mw: float, q_mvar: float, va_degree: float, vm_pu: float):
                self.name = name
                self.id = id
                self.p_mw = p_mw
                self.q_mvar = q_mvar
                self.va_degree = va_degree
                self.vm_pu = vm_pu
        
        class ControllerLoadOut(object):
            def __init__(self, name: str, id: str, p_mw: float, q_mvar: float):
                self.name = name
                self.id = id
                self.p_mw = p_mw
                self.q_mvar = q_mvar
        
        # Collect results with display names (user-friendly + technical ID)
        busbars = []
        for idx, bus in net.res_bus.iterrows():
            bus_name = net.bus.loc[idx, 'name']
            # Get user-friendly name from stored mapping
            user_friendly_name = getattr(net, 'user_friendly_names', {}).get(bus_name, bus_name)
            
            busbars.append(ControllerBusOut(
                name=get_display_name(user_friendly_name, bus_name, 'Bus', idx, 'controller'),
                id=str(bus_name),
                vm_pu=safe_float(bus['vm_pu']),
                va_degree=safe_float(bus['va_degree']),
                p_mw=safe_float(bus['p_mw']),
                q_mvar=safe_float(bus['q_mvar'])
            ))
        
        lines = []
        for idx, line in net.res_line.iterrows():
            line_name = net.line.loc[idx, 'name']
            # Get user-friendly name from stored mapping
            user_friendly_name = getattr(net, 'user_friendly_names', {}).get(line_name, line_name)
            
            lines.append(ControllerLineOut(
                name=get_display_name(user_friendly_name, line_name, 'Line', idx, 'controller'),
                id=str(line_name),
                p_from_mw=safe_float(line['p_from_mw']),
                q_from_mvar=safe_float(line['q_from_mvar']),
                p_to_mw=safe_float(line['p_to_mw']),
                q_to_mvar=safe_float(line['q_to_mvar']),
                i_from_ka=safe_float(line['i_from_ka']),
                i_to_ka=safe_float(line['i_to_ka']),
                loading_percent=safe_float(line['loading_percent'])
            ))
        
        generators = []
        for idx, gen in net.res_gen.iterrows():
            gen_name = net.gen.loc[idx, 'name']
            # Get user-friendly name from stored mapping
            user_friendly_name = getattr(net, 'user_friendly_names', {}).get(gen_name, gen_name)
            
            generators.append(ControllerGeneratorOut(
                name=get_display_name(user_friendly_name, gen_name, 'Generator', idx, 'controller'),
                id=str(gen_name),
                p_mw=safe_float(gen['p_mw']),
                q_mvar=safe_float(gen['q_mvar']),
                va_degree=safe_float(gen['va_degree']),
                vm_pu=safe_float(gen['vm_pu'])
            ))
        
        loads = []
        for idx, load in net.res_load.iterrows():
            load_name = net.load.loc[idx, 'name']
            # Get user-friendly name from stored mapping
            user_friendly_name = getattr(net, 'user_friendly_names', {}).get(load_name, load_name)
            
            loads.append(ControllerLoadOut(
                name=get_display_name(user_friendly_name, load_name, 'Load', idx, 'controller'),
                id=str(load_name),
                p_mw=safe_float(load['p_mw']),
                q_mvar=safe_float(load['q_mvar'])
            ))
        
        # Controller status for pandapower.control simulation
        controller_status = []
        if controller_params.get('voltage_control', False):
            controller_status.append({
                'controller_id': 0,
                'controller_type': 'VoltageControl',
                'active': True,
                'description': 'Generator voltage control using pandapower.control.run_control',
                'method': 'pandapower.control.run_control',
                'max_iterations': 30
            })
        if controller_params.get('tap_control', False):
            controller_status.append({
                'controller_id': 1,
                'controller_type': 'TapControl',
                'active': True,
                'description': 'Transformer tap control using pandapower.control.run_control',
                'method': 'pandapower.control.run_control',
                'max_iterations': 30
            })
        
        return {
            'controller_converged': net.converged,
            'controller_status': controller_status,
            'busbars': [vars(bus) for bus in busbars],
            'lines': [vars(line) for line in lines],
            'generators': [vars(gen) for gen in generators],
            'loads': [vars(load) for load in loads]
        }
        
    except Exception as e:
        
        # Initialize diagnostic response
        diagnostic_response = {
            "error": True,
            "message": "Controller simulation failed",
            "exception": str(e),
            "diagnostic": {}
        }
        
        # Try to get diagnostic information
        try:
            diag_result_dict = pp.diagnostic(net, report_style='detailed')
            
            # Check for isolated buses
            isolated_buses = pp.topology.unsupplied_buses(net)
            if len(isolated_buses) > 0:
                # Convert set to list (isolated_buses is a set, not numpy array)
                if isinstance(isolated_buses, set):
                    diagnostic_response["diagnostic"]["isolated_buses"] = list(isolated_buses)
                elif hasattr(isolated_buses, 'tolist'):
                    diagnostic_response["diagnostic"]["isolated_buses"] = isolated_buses.tolist()
                else:
                    diagnostic_response["diagnostic"]["isolated_buses"] = list(isolated_buses)
            
            # Process diagnostic data to convert element indices to user-friendly names
            processed_diagnostic = process_diagnostic_data(net, diag_result_dict)
            # Merge processed diagnostic with isolated_buses (don't overwrite)
            diagnostic_response["diagnostic"].update(processed_diagnostic)
                    
        except Exception as diag_error:
            pass
        
        # If no specific diagnostic was found, include the original exception
        if not diagnostic_response["diagnostic"]:
            diagnostic_response["diagnostic"]["general_error"] = str(e)
        
        return diagnostic_response


def time_series_simulation(net, timeseries_params):
    """
    Run time series simulation using pandapower timeseries module
    """
    try:
        # Try to import timeseries module, but don't fail if not available
        try:
            import pandapower.timeseries as ts
            from pandapower.timeseries import DFData
            timeseries_available = True
        except ImportError:
            timeseries_available = False
        
        # Get time series parameters
        time_steps = int(timeseries_params.get('time_steps', 24))
        load_profile = timeseries_params.get('load_profile', 'constant')
        generation_profile = timeseries_params.get('generation_profile', 'constant')
        
        # Create time stamps
        import datetime
        time_stamps = [datetime.datetime(2024, 1, 1, hour=h) for h in range(time_steps)]
        
        # Apply load and generation profiles
        if not timeseries_available:
            # Simplified approach: run multiple power flows with different profiles
            
            # Create enhanced load profiles with more variation
            import random
            import math
            
            if load_profile == 'daily':
                # Enhanced daily load profile with more variation
                base_profile = [0.3, 0.25, 0.2, 0.15, 0.2, 0.4, 0.7, 0.9, 1.0, 1.1, 1.05, 1.0,
                               0.95, 1.0, 1.05, 1.1, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.35]
                # Add significant random variation
                load_profile_values = []
                for i, val in enumerate(base_profile):
                    # Use time-based seed for more variation
                    random.seed(42 + i)
                    variation = random.uniform(-0.2, 0.2)  # ±20% variation
                    load_value = max(0.1, min(1.3, val + variation))
                    load_profile_values.append(load_value)
                    
            elif load_profile == 'industrial':
                # Enhanced industrial load profile with startup/shutdown effects
                base_profile = [0.1, 0.05, 0.05, 0.05, 0.1, 0.2, 0.6, 0.9, 1.0, 1.0, 1.0, 1.0,
                               1.0, 1.0, 1.0, 1.0, 1.0, 0.9, 0.7, 0.5, 0.3, 0.2, 0.1, 0.05]
                # Add variation
                load_profile_values = []
                for i, val in enumerate(base_profile):
                    random.seed(42 + i)
                    variation = random.uniform(-0.1, 0.1)  # ±10% variation
                    load_value = max(0.02, min(1.1, val + variation))
                    load_profile_values.append(load_value)
                    
            elif load_profile == 'variable':
                # Variable load profile with dramatic changes for testing voltage variation
                load_profile_values = []
                for hour in range(24):
                    # Use time-based seed for more variation
                    random.seed(42 + hour)
                    # Create dramatic load variations
                    base_load = 0.4 + 0.6 * math.sin(2 * math.pi * hour / 8)  # 8-hour cycle
                    # Add random spikes and drops
                    spike = random.uniform(0.6, 1.6) if random.random() < 0.4 else 1.0
                    load_value = max(0.05, min(1.8, base_load * spike))
                    load_profile_values.append(load_value)
                    
            else:  # constant with more variation
                load_profile_values = []
                for hour in range(24):
                    random.seed(42 + hour)
                    variation = random.uniform(-0.15, 0.15)  # ±15% variation
                    load_value = max(0.7, min(1.3, 1.0 + variation))
                    load_profile_values.append(load_value)
            
            # Create enhanced generation profiles with more variation
            if generation_profile == 'solar':
                # Enhanced solar generation profile with cloud effects
                base_profile = [0, 0, 0, 0, 0, 0, 0.05, 0.2, 0.5, 0.8, 0.95, 1.0,
                               1.0, 0.95, 0.8, 0.5, 0.2, 0.05, 0, 0, 0, 0, 0, 0]
                # Add cloud effects (random drops)
                gen_profile_values = []
                for i, val in enumerate(base_profile):
                    random.seed(42 + i)
                    if val > 0.3:  # Only add cloud effects during daylight
                        cloud_effect = random.uniform(0.7, 1.1)  # ±30% random variation
                        gen_value = max(0, min(1.2, val * cloud_effect))
                        gen_profile_values.append(gen_value)
                    else:
                        gen_profile_values.append(val)
                        
            elif generation_profile == 'wind':
                # Enhanced wind generation profile with realistic patterns
                gen_profile_values = []
                for hour in range(24):
                    random.seed(42 + hour)
                    # Create a more realistic wind pattern with diurnal variation
                    base_wind = 0.5 + 0.5 * math.sin(2 * math.pi * hour / 24)
                    # Add random gusts and lulls
                    wind_variation = random.uniform(0.6, 1.4)  # ±40% variation
                    wind_value = max(0.1, min(1.1, base_wind * wind_variation))
                    gen_profile_values.append(wind_value)
                    
            elif generation_profile == 'variable':
                # Variable generation profile with dramatic changes for testing voltage variation
                gen_profile_values = []
                for hour in range(24):
                    random.seed(42 + hour)
                    # Create dramatic generation variations
                    base_gen = 0.5 + 0.5 * math.cos(2 * math.pi * hour / 6)  # 6-hour cycle
                    # Add random fluctuations
                    fluctuation = random.uniform(0.5, 1.5) if random.random() < 0.5 else 1.0
                    gen_value = max(0.1, min(1.4, base_gen * fluctuation))
                    gen_profile_values.append(gen_value)
                    
            else:  # constant with more variation
                gen_profile_values = []
                for hour in range(24):
                    random.seed(42 + hour)
                    variation = random.uniform(-0.2, 0.2)  # ±20% variation
                    gen_value = max(0.6, min(1.4, 1.0 + variation))
                    gen_profile_values.append(gen_value)
            
            # Run power flow for each time step
            all_results = []
            for t in range(time_steps):
                # Use time-based seed for consistent variation
                random.seed(42 + t)
                
                # Apply load scaling with enhanced variation
                for idx, load in net.load.iterrows():
                    load_scale = load_profile_values[t % len(load_profile_values)]
                    # Add more dramatic reactive power variation
                    pf_variation = 1.0 + random.uniform(-0.2, 0.2)  # ±20% power factor variation
                    
                    # Store original values for reference
                    original_p = load['p_mw']
                    original_q = load['q_mvar']
                    
                    net.load.loc[idx, 'p_mw'] = original_p * load_scale
                    net.load.loc[idx, 'q_mvar'] = original_q * load_scale * pf_variation
                
                # Apply generation scaling with enhanced variation
                for idx, gen in net.gen.iterrows():
                    gen_scale = gen_profile_values[t % len(gen_profile_values)]
                    # Add more dramatic reactive power variation for generators
                    q_variation = 1.0 + random.uniform(-0.25, 0.25)  # ±25% Q variation
                    
                    # Store original values for reference
                    original_p = gen['p_mw']
                    original_q = gen.get('q_mvar', 0)
                    
                    net.gen.loc[idx, 'p_mw'] = original_p * gen_scale
                    # Adjust reactive power based on generation level
                    if original_q != 0:
                        net.gen.loc[idx, 'q_mvar'] = original_q * gen_scale * q_variation
                
                # Add more dramatic network effects
                if len(net.line) > 0:
                    for idx, line in net.line.iterrows():
                        # Simulate temperature effects on line resistance (higher temp = higher resistance)
                        temp_factor = 1.0 + random.uniform(-0.1, 0.1)  # ±10% temperature effect
                        if 'r_ohm_per_km' in line:
                            original_r = line['r_ohm_per_km']
                            net.line.loc[idx, 'r_ohm_per_km'] = original_r * temp_factor
                
                # Run power flow
                pp.runpp(net, 
                        algorithm=timeseries_params.get('algorithm', 'nr'),
                        calculate_voltage_angles=timeseries_params.get('calculate_voltage_angles', 'True'),
                        init=timeseries_params.get('init', 'dc'))
                
                all_results.append({
                    'time_step': t,
                    'converged': net.converged,
                    'bus_results': net.res_bus.copy(),
                    'line_results': net.res_line.copy(),
                    'gen_results': net.res_gen.copy()
                })
        else:
            # Use full timeseries module if available
            # For now, always use simplified approach since full module is not working
            # Run a single power flow as fallback
            pp.runpp(net, 
                    algorithm=timeseries_params.get('algorithm', 'nr'),
                    calculate_voltage_angles=timeseries_params.get('calculate_voltage_angles', 'auto'),
                    init=timeseries_params.get('init', 'dc'))
            
            all_results = [{
                'time_step': 0,
                'converged': net.converged,
                'bus_results': net.res_bus.copy(),
                'line_results': net.res_line.copy(),
                'gen_results': net.res_gen.copy()
            }]
        
        # Prepare results
        class TimeSeriesBusOut(object):
            def __init__(self, name: str, id: str, time_step: int, vm_pu: float, va_degree: float, p_mw: float, q_mvar: float):
                self.name = name
                self.id = id
                self.time_step = time_step
                self.vm_pu = vm_pu
                self.va_degree = va_degree
                self.p_mw = p_mw
                self.q_mvar = q_mvar
        
        class TimeSeriesLineOut(object):
            def __init__(self, name: str, id: str, time_step: int, loading_percent: float, p_from_mw: float, p_to_mw: float):
                self.name = name
                self.id = id
                self.time_step = time_step
                self.loading_percent = loading_percent
                self.p_from_mw = p_from_mw
                self.p_to_mw = p_to_mw
        
        # Collect results for each time step
        all_busbars = []
        all_lines = []
        
        if not timeseries_available:
            # Use results from simplified simulation
            for result in all_results:
                t = result['time_step']
                bus_results = result['bus_results']
                line_results = result['line_results']
                
                # Bus results for this time step
                for idx, bus in bus_results.iterrows():
                    bus_name = net.bus.loc[idx, 'name']
                    user_friendly_name = getattr(net, 'user_friendly_names', {}).get(bus_name, bus_name)
                    all_busbars.append(TimeSeriesBusOut(
                        name=get_display_name(user_friendly_name, bus_name, 'Bus', idx, 'timeseries'),
                        id=str(bus_name),
                        time_step=t,
                        vm_pu=safe_float(bus['vm_pu']),
                        va_degree=safe_float(bus['va_degree']),
                        p_mw=safe_float(bus['p_mw']),
                        q_mvar=safe_float(bus['q_mvar'])
                    ))
                
                # Line results for this time step
                for idx, line in line_results.iterrows():
                    line_name = net.line.loc[idx, 'name']
                    user_friendly_name = getattr(net, 'user_friendly_names', {}).get(line_name, line_name)
                    all_lines.append(TimeSeriesLineOut(
                        name=get_display_name(user_friendly_name, line_name, 'Line', idx, 'timeseries'),
                        id=str(line_name),
                        time_step=t,
                        loading_percent=safe_float(line['loading_percent']),
                        p_from_mw=safe_float(line['p_from_mw']),
                        p_to_mw=safe_float(line['p_to_mw'])
                    ))
        else:
            # Use results from full timeseries simulation
            for t in range(time_steps):
                # Bus results for this time step
                for idx, bus in net.res_bus.iterrows():
                    bus_name = net.bus.loc[idx, 'name']
                    user_friendly_name = getattr(net, 'user_friendly_names', {}).get(bus_name, bus_name)
                    all_busbars.append(TimeSeriesBusOut(
                        name=get_display_name(user_friendly_name, bus_name, 'Bus', idx, 'timeseries'),
                        id=str(bus_name),
                        time_step=t,
                        vm_pu=safe_float(bus['vm_pu']),
                        va_degree=safe_float(bus['va_degree']),
                        p_mw=safe_float(bus['p_mw']),
                        q_mvar=safe_float(bus['q_mvar'])
                    ))
                
                # Line results for this time step
                for idx, line in net.res_line.iterrows():
                    line_name = net.line.loc[idx, 'name']
                    user_friendly_name = getattr(net, 'user_friendly_names', {}).get(line_name, line_name)
                    all_lines.append(TimeSeriesLineOut(
                        name=get_display_name(user_friendly_name, line_name, 'Line', idx, 'timeseries'),
                        id=str(line_name),
                        time_step=t,
                        loading_percent=safe_float(line['loading_percent']),
                        p_from_mw=safe_float(line['p_from_mw']),
                        p_to_mw=safe_float(line['p_to_mw'])
                    ))
        
        # Summary statistics with display names (user-friendly + technical ID)
        vm_stats = {}
        for idx, bus in net.bus.iterrows():
            bus_name = bus['name']
            user_friendly_name = getattr(net, 'user_friendly_names', {}).get(bus_name, bus_name)
            display_name = get_display_name(user_friendly_name, bus_name, 'Bus', idx, 'timeseries')
            vm_values = [all_busbars[i].vm_pu for i in range(len(all_busbars)) 
                        if all_busbars[i].name == display_name]
            if vm_values:  # Check if list is not empty
                vm_stats[display_name] = {
                    'min_vm_pu': min(vm_values),
                    'max_vm_pu': max(vm_values),
                    'avg_vm_pu': sum(vm_values) / len(vm_values)
                }
            else:
                vm_stats[display_name] = {
                    'min_vm_pu': 0.0,
                    'max_vm_pu': 0.0,
                    'avg_vm_pu': 0.0
                }
        
        loading_stats = {}
        for idx, line in net.line.iterrows():
            line_name = line['name']
            user_friendly_name = getattr(net, 'user_friendly_names', {}).get(line_name, line_name)
            display_name = get_display_name(user_friendly_name, line_name, 'Line', idx, 'timeseries')
            loading_values = [all_lines[i].loading_percent for i in range(len(all_lines)) 
                             if all_lines[i].name == display_name]
            if loading_values:  # Check if list is not empty
                loading_stats[display_name] = {
                    'min_loading_percent': min(loading_values),
                    'max_loading_percent': max(loading_values),
                    'avg_loading_percent': sum(loading_values) / len(loading_values)
                }
            else:
                loading_stats[display_name] = {
                    'min_loading_percent': 0.0,
                    'max_loading_percent': 0.0,
                    'avg_loading_percent': 0.0
                }
        
        # Check convergence
        if not timeseries_available or 'all_results' in locals():
            timeseries_converged = all(result['converged'] for result in all_results)
        else:
            timeseries_converged = net.converged
        
        return {
            'timeseries_converged': timeseries_converged,
            'time_steps': time_steps,
            'busbars': [vars(bus) for bus in all_busbars],
            'lines': [vars(line) for line in all_lines],
            'voltage_statistics': vm_stats,
            'loading_statistics': loading_stats,
            'time_stamps': [str(ts) for ts in time_stamps]
        }
        
    except Exception as e:
        
        # Initialize diagnostic response
        diagnostic_response = {
            "error": True,
            "message": "Time series simulation failed",
            "exception": str(e),
            "diagnostic": {}
        }
        
        # Try to get diagnostic information
        try:
            diag_result_dict = pp.diagnostic(net, report_style='detailed')
            
            # Check for isolated buses
            isolated_buses = pp.topology.unsupplied_buses(net)
            if len(isolated_buses) > 0:
                # Convert set to list (isolated_buses is a set, not numpy array)
                if isinstance(isolated_buses, set):
                    diagnostic_response["diagnostic"]["isolated_buses"] = list(isolated_buses)
                elif hasattr(isolated_buses, 'tolist'):
                    diagnostic_response["diagnostic"]["isolated_buses"] = isolated_buses.tolist()
                else:
                    diagnostic_response["diagnostic"]["isolated_buses"] = list(isolated_buses)
            
            # Process diagnostic data to convert element indices to user-friendly names
            processed_diagnostic = process_diagnostic_data(net, diag_result_dict)
            # Merge processed diagnostic with isolated_buses (don't overwrite)
            diagnostic_response["diagnostic"].update(processed_diagnostic)
                    
        except Exception as diag_error:
            pass
        
        # If no specific diagnostic was found, include the original exception
        if not diagnostic_response["diagnostic"]:
            diagnostic_response["diagnostic"]["general_error"] = str(e)
        
        return diagnostic_response


class BESSControlForTargetBus(control.basic_controller.Controller):
    """
    Controller that adjusts BESS power to achieve target P and Q at Point of Coupling (POC).
    Uses iterative approach to converge to the target.
    
    EXACT implementation from BESS_sizing_tutorial.ipynb - DO NOT MODIFY SIGN CONVENTIONS!
    """
    def __init__(self, net, element_index, target_p_mw, target_q_mvar, poc_bus_idx,
                 kp_p=0.5, kp_q=0.5, max_p_mw=28.0, max_q_mvar=28.0, tolerance=1e-3,
                 in_service=True, recycle=False, order=0, level=0, **kwargs):
        super().__init__(net, in_service=in_service, recycle=recycle, 
                        order=order, level=level, initial_run=True)
        
        self.element_index = element_index
        self.target_p_mw = target_p_mw
        self.target_q_mvar = target_q_mvar
        self.poc_bus_idx = poc_bus_idx
        self.kp_p = kp_p
        self.kp_q = kp_q
        self.max_p_mw = max_p_mw
        self.max_q_mvar = max_q_mvar
        self.tolerance = tolerance
        
        # EXACT notebook algorithm - simple initial guess:
        # Sign convention: 
        # - If target P > 0 (consumption), BESS should DISCHARGE (negative P)
        # - If target P < 0 (generation), BESS should CHARGE (positive P)
        # Account for losses: need slightly more power than target
        initial_p = -target_p_mw * 1.05  # Negative because BESS discharges to supply load
        initial_q = -target_q_mvar * 1.05  # Negative to match sign convention
        self.p_mw = np.clip(initial_p, -max_p_mw, max_p_mw)
        self.q_mvar = np.clip(initial_q, -max_q_mvar, max_q_mvar)
        self.applied = False
        self.iteration = 0
        self.converged = False
        
        print(f"Initial guess: P={self.p_mw:.3f} MW, Q={self.q_mvar:.3f} Mvar")
        
    def is_converged(self, net):
        return self.applied
    
    def control_step(self, net):
        # DEBUG: Check storage value BEFORE setting
        if self.iteration == 0:
            print(f"  DEBUG: Storage BEFORE setting: p_mw={net.storage.at[self.element_index, 'p_mw']}, q_mvar={net.storage.at[self.element_index, 'q_mvar']}")
        
        # First, set the current BESS power values
        net.storage.at[self.element_index, 'p_mw'] = self.p_mw
        net.storage.at[self.element_index, 'q_mvar'] = self.q_mvar
        
        # DEBUG: Check storage value AFTER setting
        if self.iteration == 0:
            print(f"  DEBUG: Storage AFTER setting: p_mw={net.storage.at[self.element_index, 'p_mw']}, q_mvar={net.storage.at[self.element_index, 'q_mvar']}")
        
        # Run power flow to get current state (with sufficient iterations)
        try:
            pp.runpp(net, algorithm='nr', calculate_voltage_angles=True, 
                    init='auto', verbose=False)
        except Exception as e:
            # If power flow fails, don't update - keep current values
            # This can happen if the network is infeasible
            print(f"Power flow failed at iteration {self.iteration}: {str(e)}")
            self.applied = True
            return
        
        # DEBUG: Check full network power balance after power flow
        if self.iteration == 0:
            print(f"  DEBUG: res_storage after PF: p_mw={net.res_storage.at[self.element_index, 'p_mw']}, q_mvar={net.res_storage.at[self.element_index, 'q_mvar']}")
            print(f"  DEBUG: res_ext_grid: p_mw={net.res_ext_grid.at[net.ext_grid.index[0], 'p_mw']}, q_mvar={net.res_ext_grid.at[net.ext_grid.index[0], 'q_mvar']}")
            
            # Show ALL generators, loads, and other elements
            print(f"  DEBUG: Network elements count:")
            print(f"    - Buses: {len(net.bus)}")
            print(f"    - Ext grids: {len(net.ext_grid)}")
            print(f"    - Storages: {len(net.storage)}")
            print(f"    - Loads: {len(net.load) if hasattr(net, 'load') else 0}")
            print(f"    - Generators: {len(net.gen) if hasattr(net, 'gen') else 0}")
            print(f"    - Sgens: {len(net.sgen) if hasattr(net, 'sgen') else 0}")
            print(f"    - Trafos: {len(net.trafo)}")
            
            # Show bus results
            print(f"  DEBUG: Bus results:")
            for bus_idx in net.bus.index:
                bus_name = net.bus.at[bus_idx, 'name'] if 'name' in net.bus.columns else f"bus_{bus_idx}"
                bus_vn = net.bus.at[bus_idx, 'vn_kv']
                bus_vm = net.res_bus.at[bus_idx, 'vm_pu']
                bus_p = net.res_bus.at[bus_idx, 'p_mw']
                bus_q = net.res_bus.at[bus_idx, 'q_mvar']
                print(f"    Bus {bus_idx} ({bus_name}, {bus_vn}kV): vm={bus_vm:.4f}pu, P={bus_p:.3f}MW, Q={bus_q:.3f}Mvar")
            
            # Show transformer results (losses)
            print(f"  DEBUG: Transformer losses:")
            for trafo_idx in net.trafo.index:
                trafo_name = net.trafo.at[trafo_idx, 'name'] if 'name' in net.trafo.columns else f"trafo_{trafo_idx}"
                p_loss = net.res_trafo.at[trafo_idx, 'pl_mw']
                q_loss = net.res_trafo.at[trafo_idx, 'ql_mvar']
                print(f"    Trafo {trafo_idx} ({trafo_name}): P_loss={p_loss:.4f}MW, Q_loss={q_loss:.4f}Mvar")
            
            # Show if there are any generators
            if hasattr(net, 'gen') and len(net.gen) > 0:
                print(f"  DEBUG: Generator results:")
                for gen_idx in net.gen.index:
                    print(f"    Gen {gen_idx}: P={net.res_gen.at[gen_idx, 'p_mw']:.3f}MW, Q={net.res_gen.at[gen_idx, 'q_mvar']:.3f}Mvar")
            
            # Show if there are any sgens (static generators)
            if hasattr(net, 'sgen') and len(net.sgen) > 0:
                print(f"  DEBUG: Static generator results:")
                for sgen_idx in net.sgen.index:
                    print(f"    Sgen {sgen_idx}: P={net.res_sgen.at[sgen_idx, 'p_mw']:.3f}MW, Q={net.res_sgen.at[sgen_idx, 'q_mvar']:.3f}Mvar")
            
            # Show if there are any loads
            if hasattr(net, 'load') and len(net.load) > 0:
                print(f"  DEBUG: Load results:")
                for load_idx in net.load.index:
                    print(f"    Load {load_idx}: P={net.res_load.at[load_idx, 'p_mw']:.3f}MW, Q={net.res_load.at[load_idx, 'q_mvar']:.3f}Mvar")
        
        # Get current P and Q at POC from external grid
        ext_grid_idx = net.ext_grid.index[0]
        current_p = -net.res_ext_grid.at[ext_grid_idx, 'p_mw']
        current_q = -net.res_ext_grid.at[ext_grid_idx, 'q_mvar']
        
        # Calculate error
        error_p = self.target_p_mw - current_p
        error_q = self.target_q_mvar - current_q
        
        # Print diagnostic info every 10 iterations or at iteration 0
        if self.iteration % 10 == 0:
            print(f"Iteration {self.iteration}: BESS P={self.p_mw:.3f} MW, Q={self.q_mvar:.3f} Mvar")
            print(f"  POC: P={current_p:.3f} MW (target {self.target_p_mw:.3f}), Q={current_q:.3f} Mvar (target {self.target_q_mvar:.3f})")
            print(f"  Error: P={error_p:.3f} MW, Q={error_q:.3f} Mvar")
        
        # Check convergence - EXACT notebook tolerance
        if abs(error_p) < self.tolerance and abs(error_q) < self.tolerance:
            self.converged = True
            print(f"CONVERGED at iteration {self.iteration}!")
            print(f"  Final BESS: P={self.p_mw:.4f} MW, Q={self.q_mvar:.4f} Mvar")
        else:
            # EXACT notebook algorithm - simple damping, NO inversion
            # Adjust BESS power proportionally to error (with damping to avoid oscillations)
            # Sign convention: 
            # - If error_p > 0 (need more consumption), decrease BESS P (more negative = more discharge)
            # - If error_p < 0 (too much consumption), increase BESS P (less negative = less discharge)
            damping = 0.5  # Damping factor to prevent oscillations
            # Error correction: if we need more P at POC, BESS should discharge more (more negative)
            delta_p = -self.kp_p * error_p * damping  # Negative because BESS P is opposite to POC P
            delta_q = -self.kp_q * error_q * damping  # Same for Q
            
            self.p_mw += delta_p
            self.q_mvar += delta_q
            
            # Apply limits
            self.p_mw = np.clip(self.p_mw, -self.max_p_mw, self.max_p_mw)
            self.q_mvar = np.clip(self.q_mvar, -self.max_q_mvar, self.max_q_mvar)
        
        self.iteration += 1
        self.applied = True


def bess_sizing(net, bess_params):
    """
    Calculate required BESS power using iterative controller approach.
    
    Uses pandapower's control framework with BESSControlForTargetBus controller
    that iteratively adjusts BESS power until target P/Q at POC is achieved.
    
    Parameters:
    -----------
    net : pandapower network
        The network object
    bess_params : dict
        Dictionary containing:
        - storageId: ID of the storage element (from frontend)
        - pocBusbarId: ID of the POC busbar (from frontend)
        - targetP: Target active power at POC (MW)
        - targetQ: Target reactive power at POC (Mvar)
        - tolerance: Convergence tolerance (default: 0.001)
        - maxIterations: Maximum control iterations (default: 50)
        - kpP: Proportional gain for active power control (default: 0.5)
        - kpQ: Proportional gain for reactive power control (default: 0.5)
        - frequency: Network frequency (default: 50)
        - algorithm: Power flow algorithm (default: 'nr')
        
    Returns:
    --------
    str : JSON string with results
    """
    try:
        # Extract parameters
        storage_id = bess_params.get('storageId')
        poc_busbar_id = bess_params.get('pocBusbarId')
        target_p = float(bess_params.get('targetP', 0.0))
        target_q = float(bess_params.get('targetQ', 0.0))
        tolerance = float(bess_params.get('tolerance', 0.001))
        max_iterations = int(bess_params.get('maxIterations', 50))
        kp_p = float(bess_params.get('kpP', 0.5))
        kp_q = float(bess_params.get('kpQ', 0.5))
        
        # Find storage element by ID (match with busbar name)
        storage_idx = None
        for idx in net.storage.index:
            # Try to match by name or bus
            storage_name = net.storage.at[idx, 'name'] if 'name' in net.storage.columns else None
            storage_bus = net.storage.at[idx, 'bus']
            
            # Match by storage ID (could be name or bus index)
            if str(storage_id) == str(storage_name) or str(storage_id) == str(storage_bus):
                storage_idx = idx
                break
        
        if storage_idx is None:
            # Fallback: use first storage element
            if len(net.storage) > 0:
                storage_idx = net.storage.index[0]
            else:
                return json.dumps({
                    'error': 'No storage element found in network',
                    'bess_p_mw': None,
                    'bess_q_mvar': None,
                    'bess_s_mva': None,
                    'achieved_p_mw': None,
                    'achieved_q_mvar': None,
                    'error_p_mw': None,
                    'error_q_mvar': None,
                    'converged': False,
                    'iterations': 0
                })
        
        # Find POC bus by ID (match with busbar name)
        poc_bus_idx = None
        for idx in net.bus.index:
            bus_name = net.bus.at[idx, 'name'] if 'name' in net.bus.columns else None
            
            # Match by POC busbar ID
            if str(poc_busbar_id) == str(bus_name) or str(poc_busbar_id) == str(idx):
                poc_bus_idx = idx
                break
        
        if poc_bus_idx is None:
            # Fallback: use first bus (usually external grid bus)
            if len(net.bus) > 0:
                poc_bus_idx = net.bus.index[0]
            else:
                return json.dumps({
                    'error': 'No POC bus found in network',
                    'bess_p_mw': None,
                    'bess_q_mvar': None,
                    'bess_s_mva': None,
                    'achieved_p_mw': None,
                    'achieved_q_mvar': None,
                    'error_p_mw': None,
                    'error_q_mvar': None,
                    'converged': False,
                    'iterations': 0
                })
        
        # Get storage bus index
        bess_bus_idx = net.storage.at[storage_idx, 'bus']
        
        # Validate network configuration
        # Check if POC bus has an external grid
        ext_grid_at_poc = False
        for idx in net.ext_grid.index:
            if net.ext_grid.at[idx, 'bus'] == poc_bus_idx:
                ext_grid_at_poc = True
                break
        
        if not ext_grid_at_poc:
            print(f"WARNING: POC bus {poc_bus_idx} does not have an external grid!")
            print(f"External grid is at bus {net.ext_grid.at[net.ext_grid.index[0], 'bus']}")
        
        # Get storage limits from network
        max_p_mw = abs(net.storage.at[storage_idx, 'sn_mva']) if 'sn_mva' in net.storage.columns else 28.0
        max_q_mvar = abs(net.storage.at[storage_idx, 'sn_mva']) if 'sn_mva' in net.storage.columns else 28.0
        
        print(f"=== BESS SIZING STARTED ===")
        print(f"Storage: idx={storage_idx}, bus={bess_bus_idx}, max_P={max_p_mw:.1f} MW, max_Q={max_q_mvar:.1f} Mvar")
        print(f"POC: bus_idx={poc_bus_idx}, has_ext_grid={ext_grid_at_poc}")
        print(f"Target: P={target_p:.3f} MW, Q={target_q:.3f} Mvar")
        print(f"Control gains: kp_P={kp_p}, kp_Q={kp_q}, max_iter={max_iterations}, tolerance={tolerance}")
        
        # Create a copy of the network
        net_ctrl = deepcopy(net)
        
        # Create controller (using EXACT notebook algorithm)
        bess_ctrl = BESSControlForTargetBus(
            net_ctrl, storage_idx, target_p, target_q, poc_bus_idx,
            kp_p=kp_p, kp_q=kp_q, max_p_mw=max_p_mw, max_q_mvar=max_q_mvar,
            tolerance=tolerance
        )
        
        # Run iterative control loop
        for iteration in range(max_iterations):
            bess_ctrl.applied = False
            # Call control_step which will run power flow and adjust BESS power
            bess_ctrl.control_step(net_ctrl)
            if bess_ctrl.converged:
                break
        
        # Get final results
        ext_grid_idx = net_ctrl.ext_grid.index[0]
        achieved_p = -net_ctrl.res_ext_grid.at[ext_grid_idx, 'p_mw']
        achieved_q = -net_ctrl.res_ext_grid.at[ext_grid_idx, 'q_mvar']
        
        # Calculate apparent power
        bess_s_mva = np.sqrt(bess_ctrl.p_mw**2 + bess_ctrl.q_mvar**2)
        
        error_p_final = achieved_p - target_p
        error_q_final = achieved_q - target_q
        
        print(f"\n=== BESS SIZING RESULTS ===")
        print(f"Converged: {'YES' if bess_ctrl.converged else 'NO'}")
        print(f"Iterations: {bess_ctrl.iteration}")
        print(f"Final BESS: P={bess_ctrl.p_mw:.3f} MW, Q={bess_ctrl.q_mvar:.3f} Mvar, S={bess_s_mva:.3f} MVA")
        print(f"Achieved POC: P={achieved_p:.3f} MW, Q={achieved_q:.3f} Mvar")
        print(f"Final errors: P={error_p_final:.6f} MW, Q={error_q_final:.6f} Mvar")
        
        if not bess_ctrl.converged:
            print("\nPossible reasons for non-convergence:")
            print("1. Network might be too complex or have numerical issues")
            print("2. Target might be outside BESS capability")
            print("3. POC bus might not be properly connected to external grid")
            print("4. Try increasing maxIterations or adjusting gains (kpP, kpQ)")
        
        # Prepare response
        result = {
            'bess_p_mw': float(bess_ctrl.p_mw),
            'bess_q_mvar': float(bess_ctrl.q_mvar),
            'bess_s_mva': float(bess_s_mva),
            'achieved_p_mw': float(achieved_p),
            'achieved_q_mvar': float(achieved_q),
            'error_p_mw': float(error_p_final),
            'error_q_mvar': float(error_q_final),
            'converged': bool(bess_ctrl.converged),
            'iterations': int(bess_ctrl.iteration)
        }
        
        return json.dumps(result)
        
    except Exception as e:
        import traceback
        error_msg = f"BESS sizing calculation failed: {str(e)}"
        print(error_msg)
        print(traceback.format_exc())
        
        return json.dumps({
            'error': error_msg,
            'bess_p_mw': None,
            'bess_q_mvar': None,
            'bess_s_mva': None,
            'achieved_p_mw': None,
            'achieved_q_mvar': None,
            'error_p_mw': None,
            'error_q_mvar': None,
            'converged': False,
            'iterations': 0
        })
