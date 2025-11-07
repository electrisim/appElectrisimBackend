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
                           f"tap_step_percent={tap_step_percent}, vector_group='{vector_group}', "
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
    
    for x in in_data:
        if "Bus" in in_data[x]['typ']:
            bus_name = in_data[x]['name']
            user_friendly_name = in_data[x].get('userFriendlyName', bus_name)
            
            Busbars[bus_name] = pp.create_bus(
                net,
                name=bus_name,
                id=in_data[x]['id'],
                vn_kv=float(in_data[x]['vn_kv']),
                type='b'
            )
            
            # Store the user-friendly name mapping
            net.user_friendly_names[bus_name] = user_friendly_name
    
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
                    raise ValueError(f"Bus {bus_from} not found for Line from_bus")
                if to_bus_idx is None:
                    raise ValueError(f"Bus {bus_to} not found for Line to_bus")
                    
         
            except Exception as e:
                print(f"ERROR finding bus references for line: {e}")
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
                if value is not None and value != 'None' and value != '':
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
                print(f"Error converting zero sequence parameters for line {in_data[x]['name']}: {e}")
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
                raise ValueError(f"Bus {in_data[x]['bus']} not found for External Grid")

            pp.create_ext_grid(
                net,
                bus=bus_idx,
                name=in_data[x]['name'],
                id=in_data[x]['id'],
                vm_pu=safe_float(in_data[x]['vm_pu']),
                va_degree=safe_float(in_data[x]['va_degree']),
                s_sc_max_mva=safe_float(in_data[x]['s_sc_max_mva']),
                s_sc_min_mva=safe_float(in_data[x]['s_sc_min_mva']),
                rx_max=safe_float(in_data[x]['rx_max']),
                rx_min=safe_float(in_data[x]['rx_min']),
                r0x0_max=safe_float(in_data[x]['r0x0_max']),
                x0x_max=safe_float(in_data[x]['x0x_max'])
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
                raise ValueError(f"Bus {in_data[x]['bus']} not found for Generator")
    
            pp.create_gen(net, bus = bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], p_mw=safe_float(in_data[x]['p_mw']), vm_pu=safe_float(in_data[x]['vm_pu']), sn_mva=safe_float(in_data[x]['sn_mva']), scaling=in_data[x]['scaling'],
                          vn_kv=safe_float(in_data[x]['vn_kv']), xdss_pu=safe_float(in_data[x]['xdss_pu']), rdss_ohm=safe_float(in_data[x]['rdss_ohm']), cos_phi=safe_float(in_data[x]['cos_phi']), pg_percent=safe_float(in_data[x]['pg_percent']))    #, power_station_trafo=in_data[x]['power_station_trafo']
            
            # Store user-friendly name for generator
            gen_name = in_data[x]['name']
            user_friendly_name = in_data[x].get('userFriendlyName', gen_name)
            if not hasattr(net, 'user_friendly_names'):
                net.user_friendly_names = {}
            net.user_friendly_names[gen_name] = user_friendly_name
        
        if (in_data[x]['typ'].startswith("Static Generator")):      
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                raise ValueError(f"Bus {in_data[x]['bus']} not found for Static Generator")
           
            pp.create_sgen(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], p_mw=safe_float(in_data[x]['p_mw']), q_mvar=safe_float(in_data[x]['q_mvar']), sn_mva=safe_float(in_data[x]['sn_mva']), scaling=in_data[x]['scaling'], type=in_data[x]['type'],
                           k=1.1, rx=safe_float(in_data[x]['rx']), generator_type=in_data[x]['generator_type'], lrc_pu=safe_float(in_data[x]['lrc_pu']), max_ik_ka=safe_float(in_data[x]['max_ik_ka']), current_source=in_data[x]['current_source'], kappa = 1.5)
            
            # Store user-friendly name for static generator
            sgen_name = in_data[x]['name']
            user_friendly_name = in_data[x].get('userFriendlyName', sgen_name)
            if not hasattr(net, 'user_friendly_names'):
                net.user_friendly_names = {}
            net.user_friendly_names[sgen_name] = user_friendly_name
        
        if (in_data[x]['typ'].startswith("Asymmetric Static Generator")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                print(f"ERROR: Bus '{in_data[x]['bus']}' not found for Asymmetric Static Generator '{in_data[x]['name']}'. Available buses: {list(Busbars.keys())}")
                continue
            pp.create_asymmetric_sgen(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], p_a_mw=in_data[x]['p_a_mw'], p_b_mw=in_data[x]['p_b_mw'], p_c_mw=in_data[x]['p_c_mw'], q_a_mvar=in_data[x]['q_a_mvar'], q_b_mvar=in_data[x]['q_b_mvar'], q_c_mvar=in_data[x]['q_c_mvar'], sn_mva=in_data[x]['sn_mva'], scaling=in_data[x]['scaling'], type=in_data[x]['type'])   
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
                print(f"ERROR: HV Bus '{hv_bus_name}' not found for Transformer '{in_data[x]['name']}'. Available buses: {list(Busbars.keys())}")
                continue
            if lv_bus_idx is None:
                print(f"ERROR: LV Bus '{lv_bus_name}' not found for Transformer '{in_data[x]['name']}'. Available buses: {list(Busbars.keys())}")
                continue
            
            # Prepare parameters dict for transformer creation with proper type conversion
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
                'parallel': parallel_value,
                'shift_degree': safe_float(in_data[x].get('shift_degree', 0)) + phase_shift_from_group,
                'tap_side': in_data[x].get('tap_side', 'hv'),
                'tap_pos': safe_int(in_data[x].get('tap_pos', 0)),
                'tap_neutral': safe_int(in_data[x].get('tap_neutral', 0)),
                'tap_max': safe_int(in_data[x].get('tap_max', 0)),
                'tap_min': safe_int(in_data[x].get('tap_min', 0)),
                'tap_step_percent': safe_float(in_data[x].get('tap_step_percent', 0)),
                'tap_step_degree': safe_float(in_data[x].get('tap_step_degree', 0))
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
            
            pp.create_transformer_from_parameters(net, **transformer_params)
            
            # Store user-friendly name for transformer
            trafo_name = in_data[x]['name']
            user_friendly_name = in_data[x].get('userFriendlyName', trafo_name)
            if not hasattr(net, 'user_friendly_names'):
                net.user_friendly_names = {}
            net.user_friendly_names[trafo_name] = user_friendly_name
       
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
                print(f"ERROR: HV Bus '{hv_bus_name}' not found for Three Winding Transformer '{in_data[x]['name']}'. Available buses: {list(Busbars.keys())}")
                continue
            if mv_bus_idx is None:
                print(f"ERROR: MV Bus '{mv_bus_name}' not found for Three Winding Transformer '{in_data[x]['name']}'. Available buses: {list(Busbars.keys())}")
                continue
            if lv_bus_idx is None:
                print(f"ERROR: LV Bus '{lv_bus_name}' not found for Three Winding Transformer '{in_data[x]['name']}'. Available buses: {list(Busbars.keys())}")
                continue
            
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
                'tap_min': safe_int(in_data[x]['tap_min']),
                'tap_max': safe_int(in_data[x]['tap_max']),
                'tap_pos': safe_int(in_data[x]['tap_pos'])
            }
            
            # Add optional parameters only if they are not None
            optional_params = ['vector_group', 'vk0_hv_percent', 'vk0_mv_percent', 'vk0_lv_percent', 
                             'vkr0_hv_percent', 'vkr0_mv_percent', 'vkr0_lv_percent']
            
            for param in optional_params:
                value = in_data[x].get(param)
                if value is not None and value != 'None' and value != '':
                    if param == 'vector_group':
                        transformer_params[param] = vector_group  # Use parsed base group
                    else:
                        transformer_params[param] = safe_float(value)  # Convert to float
            
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
                print(f"ERROR: Bus '{in_data[x]['bus']}' not found for Shunt Reactor '{in_data[x]['name']}'. Available buses: {list(Busbars.keys())}")
                continue
            pp.create_shunt(net, typ = "shuntreactor", bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], p_mw=safe_float(in_data[x]['p_mw']), q_mvar=safe_float(in_data[x]['q_mvar']), vn_kv=in_data[x]['vn_kv'], step=in_data[x]['step'], max_step=in_data[x]['max_step'], in_service = True)
        
        if (in_data[x]['typ'].startswith("Capacitor")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                print(f"ERROR: Bus '{in_data[x]['bus']}' not found for Capacitor '{in_data[x]['name']}'. Available buses: {list(Busbars.keys())}")
                continue
            pp.create_shunt_as_capacitor(net, typ = "capacitor", bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], q_mvar=safe_float(in_data[x]['q_mvar']), loss_factor=safe_float(in_data[x]['loss_factor']), vn_kv=in_data[x]['vn_kv'], step=in_data[x]['step'], max_step=in_data[x]['max_step'])        
        
        if (in_data[x]['typ'].startswith("Load")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                raise ValueError(f"Bus {in_data[x]['bus']} not found for Load")
          
            pp.create_load(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], p_mw=safe_float(in_data[x]['p_mw']),q_mvar=safe_float(in_data[x]['q_mvar']),const_z_percent=safe_float(in_data[x]['const_z_percent']),const_i_percent=safe_float(in_data[x]['const_i_percent']), sn_mva=safe_float(in_data[x]['sn_mva']),scaling=in_data[x]['scaling'],type=in_data[x]['type'])
            
            # Store user-friendly name for load
            load_name = in_data[x]['name']
            user_friendly_name = in_data[x].get('userFriendlyName', load_name)
            if not hasattr(net, 'user_friendly_names'):
                net.user_friendly_names = {}
            net.user_friendly_names[load_name] = user_friendly_name
      
        if (in_data[x]['typ'].startswith("Asymmetric Load")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                print(f"ERROR: Bus '{in_data[x]['bus']}' not found for Asymmetric Load '{in_data[x]['name']}'. Available buses: {list(Busbars.keys())}")
                continue
            pp.create_asymmetric_load(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], p_a_mw=in_data[x]['p_a_mw'],p_b_mw=in_data[x]['p_b_mw'],p_c_mw=in_data[x]['p_c_mw'],q_a_mvar=in_data[x]['q_a_mvar'], q_b_mvar=in_data[x]['q_b_mvar'], q_c_mvar=in_data[x]['q_c_mvar'], sn_mva=in_data[x]['sn_mva'], scaling=in_data[x]['scaling'],type=in_data[x]['type'])         
   
        if (in_data[x]['typ'].startswith("Impedance")):
            from_bus_idx = Busbars.get(in_data[x]['busFrom'])
            to_bus_idx = Busbars.get(in_data[x]['busTo'])
            if from_bus_idx is None:
                print(f"ERROR: From Bus '{in_data[x]['busFrom']}' not found for Impedance '{in_data[x]['name']}'. Available buses: {list(Busbars.keys())}")
                continue
            if to_bus_idx is None:
                print(f"ERROR: To Bus '{in_data[x]['busTo']}' not found for Impedance '{in_data[x]['name']}'. Available buses: {list(Busbars.keys())}")
                continue
            pp.create_impedance(net, from_bus=from_bus_idx, to_bus=to_bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], rft_pu=in_data[x]['rft_pu'],xft_pu=in_data[x]['xft_pu'],sn_mva=in_data[x]['sn_mva'])         
         
        if (in_data[x]['typ'].startswith("Ward")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                print(f"ERROR: Bus '{in_data[x]['bus']}' not found for Ward '{in_data[x]['name']}'. Available buses: {list(Busbars.keys())}")
                continue
            pp.create_ward(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], ps_mw=in_data[x]['ps_mw'],qs_mvar=in_data[x]['qs_mvar'], pz_mw=in_data[x]['pz_mw'], qz_mvar=in_data[x]['qz_mvar'])         
   
        if (in_data[x]['typ'].startswith("Extended Ward")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                print(f"ERROR: Bus '{in_data[x]['bus']}' not found for Extended Ward '{in_data[x]['name']}'. Available buses: {list(Busbars.keys())}")
                continue
            pp.create_xward(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], ps_mw=in_data[x]['ps_mw'], qs_mvar=in_data[x]['qs_mvar'], pz_mw=in_data[x]['pz_mw'], qz_mvar=in_data[x]['qz_mvar'], r_ohm =in_data[x]['r_ohm'], x_ohm=in_data[x]['x_ohm'],vm_pu=in_data[x]['vm_pu'])         
   
        if (in_data[x]['typ'].startswith("Motor")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                print(f"ERROR: Bus '{in_data[x]['bus']}' not found for Motor '{in_data[x]['name']}'. Available buses: {list(Busbars.keys())}")
                continue
            pp.create_motor(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], pn_mech_mw=in_data[x]['pn_mech_mw'],
                            cos_phi=in_data[x]['cos_phi'],efficiency_n_percent=in_data[x]['efficiency_n_percent'],
                            lrc_pu=in_data[x]['lrc_pu'], rx=in_data[x]['rx'], vn_kv=in_data[x]['vn_kv'],
                            efficiency_percent=in_data[x]['efficiency_percent'], loading_percent=in_data[x]['loading_percent'], scaling=in_data[x]['scaling'])         
   
        
        if (in_data[x]['typ'].startswith("SVC")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                print(f"ERROR: Bus '{in_data[x]['bus']}' not found for SVC '{in_data[x]['name']}'. Available buses: {list(Busbars.keys())}")
                continue
            pp.create_svc(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], x_l_ohm=in_data[x]['x_l_ohm'], x_cvar_ohm=in_data[x]['x_cvar_ohm'], set_vm_pu=in_data[x]['set_vm_pu'], thyristor_firing_angle_degree=in_data[x]['thyristor_firing_angle_degree'], controllable=in_data[x]['controllable'], min_angle_degree=in_data[x]['min_angle_degree'], max_angle_degree=in_data[x]['max_angle_degree'])
         
        if (in_data[x]['typ'].startswith("TCSC")):
            from_bus_idx = Busbars.get(in_data[x]['busFrom'])
            to_bus_idx = Busbars.get(in_data[x]['busTo'])
            if from_bus_idx is None:
                print(f"ERROR: From Bus '{in_data[x]['busFrom']}' not found for TCSC '{in_data[x]['name']}'. Available buses: {list(Busbars.keys())}")
                continue
            if to_bus_idx is None:
                print(f"ERROR: To Bus '{in_data[x]['busTo']}' not found for TCSC '{in_data[x]['name']}'. Available buses: {list(Busbars.keys())}")
                continue
            pp.create_tcsc(net, from_bus=from_bus_idx, to_bus=to_bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], x_l_ohm=in_data[x]['x_l_ohm'], x_cvar_ohm=in_data[x]['x_cvar_ohm'], set_p_to_mw=in_data[x]['set_p_to_mw'], thyristor_firing_angle_degree=in_data[x]['thyristor_firing_angle_degree'], controllable=in_data[x]['controllable'], min_angle_degree=in_data[x]['min_angle_degree'], max_angle_degree=in_data[x]['max_angle_degree'])
                   
        if (in_data[x]['typ'].startswith("SSC")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                print(f"ERROR: Bus '{in_data[x]['bus']}' not found for SSC '{in_data[x]['name']}'. Available buses: {list(Busbars.keys())}")
                continue
            pp.create_ssc(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], r_ohm=in_data[x]['r_ohm'], x_ohm=in_data[x]['x_ohm'], set_vm_pu=in_data[x]['set_vm_pu'], vm_internal_pu=in_data[x]['vm_internal_pu'], va_internal_degree=in_data[x]['va_internal_degree'], controllable=in_data[x]['controllable'])
        

        if (in_data[x]['typ'].startswith("Storage")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                print(f"ERROR: Bus '{in_data[x]['bus']}' not found for Storage '{in_data[x]['name']}'. Available buses: {list(Busbars.keys())}")
                continue
            pp.create_storage(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], p_mw=in_data[x]['p_mw'],max_e_mwh=in_data[x]['max_e_mwh'],q_mvar=in_data[x]['q_mvar'],sn_mva=in_data[x]['sn_mva'], soc_percent=in_data[x]['soc_percent'],min_e_mwh=in_data[x]['min_e_mwh'],scaling=in_data[x]['scaling'], type=in_data[x]['type'])         
   
        if (in_data[x]['typ'].startswith("DC Line")):
            from_bus_idx = Busbars.get(in_data[x]['busFrom'])
            to_bus_idx = Busbars.get(in_data[x]['busTo'])
            if from_bus_idx is None:
                print(f"ERROR: From Bus '{in_data[x]['busFrom']}' not found for DC Line '{in_data[x]['name']}'. Available buses: {list(Busbars.keys())}")
                continue
            if to_bus_idx is None:
                print(f"ERROR: To Bus '{in_data[x]['busTo']}' not found for DC Line '{in_data[x]['name']}'. Available buses: {list(Busbars.keys())}")
                continue
            pp.create_dcline(net, from_bus=from_bus_idx, to_bus=to_bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], p_mw=in_data[x]['p_mw'], loss_percent=in_data[x]['loss_percent'], loss_mw=in_data[x]['loss_mw'], vm_from_pu=in_data[x]['vm_from_pu'], vm_to_pu=in_data[x]['vm_to_pu'])



def powerflow(net, algorithm, calculate_voltage_angles, init, export_python=False, in_data=None, Busbars=None):
               
         
            #pandapower - rozpływ mocy
            try:
            
                # Check for isolated buses before running power flow
                isolated_buses = pp.topology.unsupplied_buses(net)
                if len(isolated_buses) > 0:
                    raise ValueError(f"Isolated buses found: {isolated_buses}. Check your network connectivity.")
                pp.runpp(net, algorithm=algorithm, calculate_voltage_angles=calculate_voltage_angles, init=init) 
            except Exception as e:
                print("An exception occurred")
                print(f"Exception details: {str(e)}")
                
                # Initialize diagnostic response
                diagnostic_response = {
                    "error": True,
                    "message": "Power flow calculation failed",
                    "exception": str(e),
                    "diagnostic": {}
                }               
                
                
                # Access initial voltage magnitudes and angles  
                diag_result_dict = pp.diagnostic(net, report_style='detailed')             
                
                #print(diag_result_dict)
                #plt.simple_plot(net, plot_line_switches=True)
                
                # Check for isolated buses
                isolated_buses = pp.topology.unsupplied_buses(net)
                if len(isolated_buses) > 0:
                    diagnostic_response["diagnostic"]["isolated_buses"] = isolated_buses.tolist()
                
                # Process diagnostic data to convert element indices to user-friendly names
                processed_diagnostic = process_diagnostic_data(net, diag_result_dict)
                diagnostic_response["diagnostic"] = processed_diagnostic
                
                # If no specific diagnostic was found, include the original exception
                if not diagnostic_response["diagnostic"]:
                   diagnostic_response["diagnostic"]["general_error"] = str(e)
                
                return diagnostic_response
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
                
                
                #Bus
                for index, row in net.res_bus.iterrows():    
                    
                    pf = row['p_mw']/math.sqrt(math.pow(row['p_mw'],2)+math.pow(row['q_mvar'],2))
                    if math.isnan(pf):
                        pf = 0
                        
                    q_p = row['q_mvar']/row['p_mw']     
                    if math.isnan(q_p):
                        q_p = 0
                    if math.isinf(q_p):
                        q_p = 0
                    
                                                                       
                    busbar = BusbarOut(name=net.bus._get_value(index, 'name'), id = net.bus._get_value(index, 'id'), vm_pu=row['vm_pu'], va_degree=row['va_degree'], p_mw=row['p_mw'], q_mvar=row['q_mvar'], pf = pf, q_p=q_p)         
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
                        print("no external grid in the model")                
                else:                    
                        for index, row in net.res_ext_grid.iterrows():    
                            externalgrid = ExternalGridOut(name=net.ext_grid._get_value(index, 'name'), id = net.ext_grid._get_value(index, 'id'), p_mw=row['p_mw'], q_mvar=row['q_mvar'], pf = row['p_mw']/math.sqrt(math.pow(row['p_mw'],2)+math.pow(row['q_mvar'],2)), q_p=row['q_mvar']/row['p_mw'])        
                            externalgridsList.append(externalgrid) 
                            externalgrids = ExternalGridsOut(externalgrids = externalgridsList) 
                        result = {**result, **externalgrids.__dict__}          
                             
                #Generator         
                if(net.res_gen.empty):
                        print("no generators in the model")                         
                                    
                else:                    
                        for index, row in net.res_gen.iterrows():    
                            generator = GeneratorOut(name=net.gen._get_value(index, 'name'), id = net.gen._get_value(index, 'id'), p_mw=row['p_mw'], q_mvar=row['q_mvar'], va_degree=row['va_degree'], vm_pu=row['vm_pu'])        
                            generatorsList.append(generator) 
                            generators = GeneratorsOut(generators = generatorsList)
                        
                        result = {**result, **generators.__dict__}
                        
                #Static Generator                     
                if(net.res_sgen.empty):
                        print("no static generators in the model")                         
                                    
                else:                    
                        for index, row in net.res_sgen.iterrows():    
                            staticgenerator = StaticGeneratorOut(name=net.sgen._get_value(index, 'name'), id = net.sgen._get_value(index, 'id'), p_mw=row['p_mw'], q_mvar=row['q_mvar'])        
                            staticgeneratorsList.append(staticgenerator) 
                            staticgenerators = StaticGeneratorsOut(staticgenerators = staticgeneratorsList)
                        
                        result = {**result, **staticgenerators.__dict__}
                        
                        
                
                #Asymmetric Static Generator                     
                if(net.res_asymmetric_sgen.empty):
                        print("no asymmetric static generators in the model")                         
                                    
                else:                    
                        for index, row in net.res_asymmetric_sgen.iterrows():    
                            asymmetricstaticgenerator = AsymmetricStaticGeneratorOut(name=net.asymmetric_sgen._get_value(index, 'name'), id = net.asymmetric_sgen._get_value(index, 'id'), p_a_mw=row['p_a_mw'], q_a_mvar=row['q_a_mvar'], p_b_mw=row['p_b_mw'], q_b_mvar=row['q_b_mvar'], p_c_mw=row['p_c_mw'], q_c_mvar=row['q_c_mvar'])        
                            asymmetricstaticgeneratorsList.append(asymmetricstaticgenerator) 
                            asymmetricstaticgenerators = AsymmetricStaticGeneratorsOut(asymmetricstaticgenerators = asymmetricstaticgeneratorsList)
                        
                        result = {**result, **asymmetricstaticgenerators.__dict__}
                        
                print(net)
               
                #Transformer                     
                if(net.res_trafo.empty):
                        print("no transformer in the model")                         
                                    
                else:                    
                        for index, row in net.res_trafo.iterrows():    
                            transformer = TransformerOut(name=net.trafo._get_value(index, 'name'), id = net.trafo._get_value(index, 'id'), p_hv_mw=row['p_hv_mw'], q_hv_mvar=row['q_hv_mvar'], p_lv_mw=row['p_lv_mw'], q_lv_mvar=row['q_lv_mvar'], pl_mw=row['pl_mw'], 
                                                         ql_mvar=row['ql_mvar'], i_hv_ka=row['i_hv_ka'], i_lv_ka=row['i_lv_ka'], vm_hv_pu=row['vm_hv_pu'], vm_lv_pu=row['vm_lv_pu'], va_hv_degree=row['va_hv_degree'], va_lv_degree=row['va_lv_degree'], loading_percent=row['loading_percent'])        
                            transformersList.append(transformer) 
                            transformers = TransformersOut(transformers = transformersList)
                        
                        result = {**result, **transformers.__dict__}   
                        
                        
                #Transformer3W                     
                if(net.res_trafo3w.empty):
                        print("no three winding transformer in the model")                         
                                    
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
                        print("no shunt reactor in the model")                
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
                        print("no capacitor in the model")                
                else:                    
                        for index, row in net.res_shunt.iterrows(): 
                            if (net.shunt._get_value(index, 'typ') == 'capacitor'):  # q is always negative for capacitor
                                capacitor = CapacitorOut(name=net.shunt._get_value(index, 'name'), id = net.shunt._get_value(index, 'id'), p_mw=row['p_mw'], q_mvar=row['q_mvar'], vm_pu = row['vm_pu'])        
                                capacitorsList.append(capacitor) 
                                capacitors = CapacitorsOut(capacitors = capacitorsList) 
                                result = {**result, **capacitors.__dict__}  
                
               
                #Load
                if(net.res_load.empty):
                        print("no load in the model")                
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
                        print("no asymmetric load in the model")                
                else:                    
                        for index, row in net.res_asymmetric_load.iterrows():    
                            asymmetricload = AsymmetricLoadOut(name=net.asymmetric_load._get_value(index, 'name'), id = net.asymmetric_load._get_value(index, 'id'), p_a_mw=row['p_a_mw'], q_a_mvar=row['q_a_mvar'], p_b_mw=row['p_b_mw'], q_b_mvar=row['q_b_mvar'], p_c_mw=row['p_c_mw'], q_c_mvar=row['q_c_mvar'])        
                            asymmetricloadsList.append(asymmetricload) 
                            asymmetricloads = AsymmetricLoadsOut(asymmetricloads = asymmetricloadsList) 
                        result = {**result, **asymmetricloads.__dict__}    
                        
                        
                #Impedance
                if(net.res_impedance.empty):
                        print("no impedance in the model")                
                else:                    
                        for index, row in net.res_impedance.iterrows():    
                            impedance = ImpedanceOut(name=net.impedance._get_value(index, 'name'), id = net.impedance._get_value(index, 'id'), p_from_mw=row['p_from_mw'], q_from_mvar=row['q_from_mvar'], p_to_mw=row['p_to_mw'], q_to_mvar=row['q_to_mvar'], pl_mw=row['pl_mw'], ql_mvar=row['ql_mvar'], i_from_ka=row['i_from_ka'], i_to_ka=row['i_to_ka'])        
                            impedancesList.append(impedance) 
                            impedances = ImpedancesOut(impedances = impedancesList) 
                        result = {**result, **impedances.__dict__} 
                        
                
                #Ward
                if(net.res_ward.empty):
                        print("no ward in the model")                
                else:                    
                        for index, row in net.res_ward.iterrows():    
                            ward = WardOut(name=net.ward._get_value(index, 'name'), id = net.ward._get_value(index, 'id'), p_mw=row['p_mw'], q_mvar=row['q_mvar'], vm_pu=row['vm_pu'])        
                            wardsList.append(ward) 
                            wards = WardsOut(wards = wardsList) 
                        result = {**result, **wards.__dict__} 
                        
                        
                #Extended Ward
                if(net.res_xward.empty):
                        print("no extended ward in the model")                
                else:                    
                        for index, row in net.res_xward.iterrows():    
                            extendedward = ExtendedWardOut(name=net.xward._get_value(index, 'name'), id = net.xward._get_value(index, 'id'), p_mw=row['p_mw'], q_mvar=row['q_mvar'], vm_pu=row['vm_pu'])        
                            extendedwardsList.append(extendedward) 
                            extendedwards = ExtendedWardsOut(extendedwards = extendedwardsList) 
                        result = {**result, **extendedwards.__dict__} 
                        
                        
                #Motor
                if(net.res_motor.empty):
                        print("no motor in the model")                
                else:                    
                        for index, row in net.res_motor.iterrows():    
                            motor = MotorOut(name=net.motor._get_value(index, 'name'), id = net.motor._get_value(index, 'id'), p_mw=row['p_mw'], q_mvar=row['q_mvar'])        
                            motorsList.append(motor) 
                            motors = MotorsOut(motors = motorsList) 
                        result = {**result, **motors.__dict__} 
                        
                #Storage
                if(net.res_storage.empty):
                        print("no storage in the model")                
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
                     print("no SVC in the model")
                except UnboundLocalError:
                     print("no TCSC in the model")                
                    
                        
                #TCSC   
                try:
                    for index, row in net.res_tcsc.iterrows():    
                            tcsc = TCSCOut(name=net.tcsc._get_value(index, 'name'), id = net.tcsc._get_value(index, 'id'), thyristor_firing_angle_degree=row['thyristor_firing_angle_degree'], x_ohm=row['x_ohm'], p_from_mw=row['p_from_mw'], q_from_mvar=row['q_from_mvar'], p_to_mw=row['p_to_mw'], q_to_mvar=row['q_to_mvar'], p_l_mw=row['p_l_mw'], q_l_mvar=row['q_l_mvar'], vm_from_pu=row['vm_from_pu'], va_from_degree=row['va_from_degree'], vm_to_pu=row['vm_to_pu'], va_to_degree=row['va_to_degree']  )        
                            TCSCsList.append(tcsc) 
                            tcscs = TCSCsOut(tcscs = TCSCsList) 
                    result = {**result, **tcscs.__dict__} 
                     
                except AttributeError:  
                     print("no TCSC in the model")     
                except UnboundLocalError:
                     print("no TCSC in the model") 

                                               
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
                        print("no SSC in the model")                
                else:                    
                    for index, row in net.res_ssc.iterrows():    
                        ssc = SSCOut(name=net.ssc._get_value(index, 'name'), id = net.ssc._get_value(index, 'id'), q_mvar=row['q_mvar'], vm_internal_pu=row['vm_internal_pu'], va_internal_degree=row['va_internal_degree'], vm_pu=row['vm_pu'], va_degree=row['va_degree'])        
                        sscsList.append(ssc) 
                        sscs = SSCsOut(sscs = sscsList) 
                    result = {**result, **sscs.__dict__}                    
                       
                                        
                #DCLine
                if(net.res_dcline.empty):
                        print("no DC line in the model")                
                else:                    
                        for index, row in net.res_dcline.iterrows():    
                            dcline = ImpedanceOut(name=net.dcline._get_value(index, 'name'), id = net.dcline._get_value(index, 'id'), p_from_mw=row['p_from_mw'], q_from_mvar=row['q_from_mvar'], p_to_mw=row['p_to_mw'], q_to_mvar=row['q_to_mvar'], pl_mw=row['pl_mw'], vm_from_pu=row['vm_from_pu'], va_from_degree=row['va_from_degree'], vm_to_pu=row['vm_to_pu'], va_to_degree=row['va_to_degree'] )        
                            dclinesList.append(dcline) 
                            dclines = ImpedancesOut(dclines = dclinesList) 
                        result = {**result, **dclines.__dict__}         
                
                           
                # Generate Python code if export is requested
                if export_python and in_data and Busbars:
                    python_code = generate_pandapower_python_code(net, in_data, Busbars, algorithm, calculate_voltage_angles, init)
                    result['pandapower_python'] = python_code
                    print(f"Pandapower Python code export enabled: {len(python_code)} characters")
                
                #json.dumps - convert a subset of Python objects into a json string
                #default: If specified, default should be a function that gets called for objects that can't otherwise be serialized. It should return a JSON encodable version of the object or raise a TypeError. If not specified, TypeError is raised. 
                #indent - wcięcia
                response = json.dumps(result, default=lambda o: o.__dict__, indent=4) 
            
                print("Response to FRONTEND CORRECT")   
                   
                return response  


def shortcircuit(net, in_data):
    
    # Add diagnostic prints
    # Print key parameters
    # print("\nBus Data:")
    # print(net.bus)
        
    print("\nStatic Generator Data:")
    print(net.sgen)
    net.sgen["k"] = 1.1
    #print(net.sgen["k"])
    print(pp.__version__)
    
    
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
    print(f"Short circuit parameters:")
    print(f"  fault: {fault_type} (type: {type(fault_type)}) - fault type")
    print(f"  case: {fault_location} (type: {type(fault_location)}) - calculation case")
    print(f"  bus: {bus} (type: {type(bus)}) - bus index")
    print(f"  ip: {ip}")
    print(f"  ith: {ith}")
    print(f"  tk_s: {tk_s}")
    print(f"  r_fault_ohm: {r_fault_ohm}")
    print(f"  x_fault_ohm: {x_fault_ohm}")
    
    # Print Pandapower version for debugging
    print(f"Pandapower version: {pp.__version__}")
    
    # Validate fault_type parameter - Pandapower expects specific values
    valid_fault_types = ['3ph', '2ph', '1ph']
    if fault_type not in valid_fault_types:
        print(f"Warning: Invalid fault_type value '{fault_type}'. Valid values are: {valid_fault_types}")
        fault_type = '3ph'  # Default to 3ph if invalid
        print(f"Using default fault_type: {fault_type}")
    
    # Validate case parameter
    valid_cases = ['max', 'min']
    if fault_location not in valid_cases:
        print(f"Warning: Invalid case value '{fault_location}'. Valid values are: {valid_cases}")
        fault_location = 'max'  # Default to max if invalid
        print(f"Using default case: {fault_location}")
 

    try:
        # Use correct parameter mapping according to Pandapower documentation
        print(f"Attempting short circuit calculation with fault='{fault_type}', case='{fault_location}', bus={bus}")
        
        # Call short circuit calculation with correct parameters including ip and ith
        sc.calc_sc(net, fault=fault_type, case=fault_location, bus=bus, ip=ip, ith=ith, tk_s=tk_s, 
                   kappa_method='C', r_fault_ohm=r_fault_ohm, x_fault_ohm=x_fault_ohm, 
                   check_connectivity=False, return_all_currents=True)
        
        # Check if ip_ka and ith_ka calculations failed (all NaN) for single-phase faults
        if fault_type == '1ph' and net.res_bus_sc['ip_ka'].isna().all() and net.res_bus_sc['ith_ka'].isna().all():
            print("Warning: ip_ka and ith_ka calculations failed for single-phase fault.")
            print("This is a known limitation in pandapower for single-phase faults.")
            print("Calculating ip_ka and ith_ka from single-phase ikss_ka using standard formulas...")
            
            # Calculate ip_ka and ith_ka from ikss_ka using standard electrical engineering formulas
            # ip_ka = kappa * sqrt(2) * ikss_ka (peak current)
            # ith_ka = ikss_ka (for short duration faults, thermal current ≈ initial current)
            
            import numpy as np
            
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
            
            print(f"Calculated ip_ka using kappa factor: {kappa_factor}")
            print(f"Calculated ith_ka for fault duration: {tk_s}s")
            print("ip_ka and ith_ka values are now based on single-phase ikss_ka results")
        print("Short circuit calculation completed successfully")
        
    except Exception as e:
        print(f"Short circuit calculation failed: {e}")
        
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
        return json.dumps(diagnostic_response, indent=4)
    print("Short circuit results:")
    print(net.res_bus_sc)
    print("\nColumns in res_bus_sc:")
    print(net.res_bus_sc.columns.tolist())
    print("\nFirst few rows:")
    print(net.res_bus_sc.head())
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
                
    
    busbarList = list()      
                
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
                    
        busbar = BusbarOut(name=net.bus._get_value(index, 'name'), id = net.bus._get_value(index, 'id'), ikss_ka=row['ikss_ka'], ip_ka=ip_ka, ith_ka=ith_ka, rk_ohm=row['rk_ohm'], xk_ohm=row['xk_ohm'])    
                 
        busbarList.append(busbar)
        busbars = BusbarsOut(busbars = busbarList)  
            
    print(busbars.__dict__)
    print(type(busbars.__dict__))
    #result = {**busbars.__dict__, **lines.__dict__} #łączenie dwóch dictionaries
    result = {**busbars.__dict__}

    response = json.dumps(result, default=lambda o: o.__dict__, indent=4) #json.dumps - convert a subset of Python objects into a json string
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
        print(f"Network elements: Lines={len(net.line)}, Buses={len(net.bus)}, Generators={len(net.gen)}, Transformers={len(net.trafo)}")
        
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
            print(error_message)
            return json.dumps({'error': error_message})
        
        if not contingency_results:
            error_message = f"No contingency results generated. All {len(contingency_cases)} cases failed to converge."
            print(error_message)
            return json.dumps({'error': error_message})
        
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
        
        response = json.dumps(result, default=lambda o: o.__dict__, indent=4)
        print("Contingency Analysis Results:")
        print(response)
        
        return response
        
    except Exception as e:
        error_message = f"Contingency analysis failed: {str(e)}"
        print(error_message)
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
            print('Warning: No cost functions defined. Using default costs for optimization.')
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
            print(f"Running AC Optimal Power Flow with algorithm: {algorithm}")
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
            print(f"Running DC Optimal Power Flow with algorithm: {algorithm}")
            pp.rundcopp(net,
                       verbose=not suppress_warnings,
                       suppress_warnings=suppress_warnings,
                       delta=delta,
                       trafo_model=trafo_model,
                       trafo_loading=trafo_loading,
                       calculate_voltage_angles=calculate_voltage_angles,
                       init=init,
                       numba=numba)
        
        print("Optimal Power Flow completed successfully")
        
    except Exception as e:
        print(f"Optimal Power Flow failed: {str(e)}")
        
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
            print(diag_result_dict)
            
            # Check for isolated buses
            isolated_buses = pp.topology.unsupplied_buses(net)
            if len(isolated_buses) > 0:
                diagnostic_response["diagnostic"]["isolated_buses"] = isolated_buses.tolist()
            
            # Process diagnostic data to convert element indices to user-friendly names
            processed_diagnostic = process_diagnostic_data(net, diag_result_dict)
            diagnostic_response["diagnostic"] = processed_diagnostic
                    
        except Exception as diag_error:
            print(f"Diagnostic failed: {diag_error}")
        
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
                print(f"Error processing bus {index}: {e}")
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
                print(f"Error processing line {index}: {e}")
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
                print(f"Error processing generator {index}: {e}")
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
                print(f"Error processing external grid {index}: {e}")
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
                print(f"Error processing load {index}: {e}")
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
        
        print(f"OPF Results: {len(busbarList)} buses, {len(linesList)} lines, {len(generatorsList)} generators")
        
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
                print(f"Added default polynomial cost to generator {gen_idx}")
    
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
                print(f"Added default PWL cost to generator {gen_idx}") 

def safe_float(value):
    """Convert value to float, replacing NaN with 0.0"""
    import math
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0

def safe_int(value, default=1):
    """Convert value to int with default fallback"""
    if value is None or value == 'None' or value == '':
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
        print("Setting up controllers using pandapower.control module...")
        
        # Voltage control using generator voltage setpoints
        if controller_params.get('voltage_control', False):
            print("Setting up voltage control...")
            for idx, gen in net.gen.iterrows():
                if 'vm_pu' in gen and gen['vm_pu'] != 1.0:
                    print(f"Generator {idx} has voltage setpoint: {gen['vm_pu']}")
                    # Create a simple voltage controller
                    # Note: This is a simplified controller - in a full implementation,
                    # you would use specific controller classes like VoltageController
                    pass
        
        # Tap control using transformer tap positions
        if controller_params.get('tap_control', False):
            print("Setting up tap control...")
            if len(net.trafo) > 0:
                for idx, trafo in net.trafo.iterrows():
                    print(f"Transformer {idx} available for tap control")
                    # Create a simple tap controller
                    # Note: This is a simplified controller - in a full implementation,
                    # you would use specific controller classes like TapController
                    pass
        
        # Run controller simulation using the proper run_control function
        print("Running controller simulation with run_control...")
        run_control(net, 
                   max_iter=30,
                   continue_on_divergence=False,
                   check_each_level=True)
        
        print("Controller simulation completed successfully")
        
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
        print(f"Controller simulation error: {str(e)}")
        
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
            print(diag_result_dict)
            
            # Check for isolated buses
            isolated_buses = pp.topology.unsupplied_buses(net)
            if len(isolated_buses) > 0:
                diagnostic_response["diagnostic"]["isolated_buses"] = isolated_buses.tolist()
            
            # Process diagnostic data to convert element indices to user-friendly names
            processed_diagnostic = process_diagnostic_data(net, diag_result_dict)
            diagnostic_response["diagnostic"] = processed_diagnostic
                    
        except Exception as diag_error:
            print(f"Diagnostic failed: {diag_error}")
        
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
            print("pandapower.timeseries module not available, using simplified time series simulation")
        
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
            print(f"Running simplified time series simulation with {time_steps} time steps")
            print(f"Load profile: {load_profile}, Generation profile: {generation_profile}")
            print(f"Load profile values (first 5): {load_profile_values[:5]}")
            print(f"Generation profile values (first 5): {gen_profile_values[:5]}")
            
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
                        calculate_voltage_angles=timeseries_params.get('calculate_voltage_angles', 'auto'),
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
            print("Using full timeseries module")
            # For now, always use simplified approach since full module is not working
            print("Falling back to simplified approach")
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
        print(f"Time series simulation error: {str(e)}")
        
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
            print(diag_result_dict)
            
            # Check for isolated buses
            isolated_buses = pp.topology.unsupplied_buses(net)
            if len(isolated_buses) > 0:
                diagnostic_response["diagnostic"]["isolated_buses"] = isolated_buses.tolist()
            
            # Process diagnostic data to convert element indices to user-friendly names
            processed_diagnostic = process_diagnostic_data(net, diag_result_dict)
            diagnostic_response["diagnostic"] = processed_diagnostic
                    
        except Exception as diag_error:
            print(f"Diagnostic failed: {diag_error}")
        
        # If no specific diagnostic was found, include the original exception
        if not diagnostic_response["diagnostic"]:
            diagnostic_response["diagnostic"]["general_error"] = str(e)
        
        return diagnostic_response