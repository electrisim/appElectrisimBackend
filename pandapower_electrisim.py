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




Busbars = {} 
def create_busbars(in_data, net):
    Busbars = {}
    for x in in_data:
        if "Bus" in in_data[x]['typ']:
            Busbars[in_data[x]['name']] = pp.create_bus(
                net,
                name=in_data[x]['name'],
                id=in_data[x]['id'],
                vn_kv=float(in_data[x]['vn_kv']),
                type='b'
            )
    return Busbars


def create_other_elements(in_data,net,x, Busbars):

    #tworzymy zmienne ktorych nazwa odpowiada modelowi z js - np.Hwap0ntfbV98zYtkLMVm-8
    print(f"Setting up bus variables from Busbars: {Busbars}")
    for name,value in Busbars.items():
        globals()[name] = value    
        print(f"Set global variable: {name} = {value}")

    for x in in_data:
        print(f"Processing element: {in_data[x]['typ']} - {in_data[x].get('name', 'no_name')}")
        #eval - rozwiazuje problem z wartosciami NaN
        if (in_data[x]['typ'].startswith("Line")):
            try:
                print(f"Processing Line: busFrom='{in_data[x]['busFrom']}', busTo='{in_data[x]['busTo']}'")
                from_bus_idx = Busbars.get(in_data[x]['busFrom'])
                to_bus_idx = Busbars.get(in_data[x]['busTo'])
                
                if from_bus_idx is None:
                    raise ValueError(f"Bus {in_data[x]['busFrom']} not found for Line from_bus")
                if to_bus_idx is None:
                    raise ValueError(f"Bus {in_data[x]['busTo']} not found for Line to_bus")
                    
                print(f"Found bus indices: from_bus={from_bus_idx}, to_bus={to_bus_idx}")
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
                "length_km": float(in_data[x]['length_km']), 
                "parallel": int(in_data[x]['parallel']), 
                "df": float(in_data[x]['df'])
            }

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
            
            
            #pp.create_line_from_parameters(net,  from_bus=eval(in_data[x]['busFrom']), to_bus=eval(in_data[x]['busTo']), name=in_data[x]['name'], id=in_data[x]['id'], r_ohm_per_km=in_data[x]['r_ohm_per_km'], x_ohm_per_km=in_data[x]['x_ohm_per_km'], c_nf_per_km= in_data[x]['c_nf_per_km'], g_us_per_km= in_data[x]['g_us_per_km'], 
            #                               r0_ohm_per_km=1, x0_ohm_per_km=1, c0_nf_per_km=0, endtemp_degree=in_data[x]['endtemp_degree'],
            #                               max_i_ka= in_data[x]['max_i_ka'],type= in_data[x]['type'], length_km=in_data[x]['length_km'], parallel=in_data[x]['parallel'], df=in_data[x]['df'])
            #w specyfikacji zapisano, że poniższe parametry są typu nan. Wartosci składowych zerowych mogą być wprowadzone przez funkcję create line.
            #r0_ohm_per_km= in_data[x]['r0_ohm_per_km'], x0_ohm_per_km= in_data[x]['x0_ohm_per_km'], c0_nf_per_km= in_data[x]['c0_nf_per_km'], max_loading_percent=in_data[x]['max_loading_percent'], endtemp_degree=in_data[x]['endtemp_degree'],
        
        if (in_data[x]['typ'].startswith("External Grid") or in_data[x]['typ'].startswith("ExternalGrid")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                raise ValueError(f"Bus {in_data[x]['bus']} not found for External Grid")
            print(f"Creating External Grid on bus {bus_idx} (name: {in_data[x]['bus']})")
            pp.create_ext_grid(
                net,
                bus=bus_idx,
                name=in_data[x]['name'],
                id=in_data[x]['id'],
                vm_pu=float(in_data[x]['vm_pu']),
                va_degree=float(in_data[x]['va_degree']),
                s_sc_max_mva=float(in_data[x]['s_sc_max_mva']),
                s_sc_min_mva=float(in_data[x]['s_sc_min_mva']),
                rx_max=float(in_data[x]['rx_max']),
                rx_min=float(in_data[x]['rx_min']),
                r0x0_max=float(in_data[x]['r0x0_max']),
                x0x_max=float(in_data[x]['x0x_max'])
            )
       
        if (in_data[x]['typ'].startswith("Generator")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                raise ValueError(f"Bus {in_data[x]['bus']} not found for Generator")
            print(f"Creating Generator on bus {bus_idx} (name: {in_data[x]['bus']})")
            pp.create_gen(net, bus = bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], p_mw=float(in_data[x]['p_mw']), vm_pu=float(in_data[x]['vm_pu']), sn_mva=float(in_data[x]['sn_mva']), scaling=in_data[x]['scaling'],
                          vn_kv=float(in_data[x]['vn_kv']), xdss_pu=float(in_data[x]['xdss_pu']), rdss_ohm=float(in_data[x]['rdss_ohm']), cos_phi=float(in_data[x]['cos_phi']), pg_percent=float(in_data[x]['pg_percent']))    #, power_station_trafo=in_data[x]['power_station_trafo']
        
        if (in_data[x]['typ'].startswith("Static Generator")):      
            pp.create_sgen(net, bus = eval(in_data[x]['bus']), name=in_data[x]['name'], id=in_data[x]['id'], p_mw=float(in_data[x]['p_mw']), q_mvar=float(in_data[x]['q_mvar']), sn_mva=float(in_data[x]['sn_mva']), scaling=in_data[x]['scaling'], type=in_data[x]['type'],
                           k=1.1, rx=float(in_data[x]['rx']), generator_type=in_data[x]['generator_type'], lrc_pu=float(in_data[x]['lrc_pu']), max_ik_ka=float(in_data[x]['max_ik_ka']), current_source=in_data[x]['current_source'], kappa = 1.5)
        
        if (in_data[x]['typ'].startswith("Asymmetric Static Generator")):      
            pp.create_asymmetric_sgen(net, bus = eval(in_data[x]['bus']), name=in_data[x]['name'], id=in_data[x]['id'], p_a_mw=in_data[x]['p_a_mw'], p_b_mw=in_data[x]['p_b_mw'], p_c_mw=in_data[x]['p_c_mw'], q_a_mvar=in_data[x]['q_a_mvar'], q_b_mvar=in_data[x]['q_b_mvar'], q_c_mvar=in_data[x]['q_c_mvar'], sn_mva=in_data[x]['sn_mva'], scaling=in_data[x]['scaling'], type=in_data[x]['type'])   
        #Zero sequence parameters** (Added through std_type For Three phase load flow) :
            #vk0_percent** - zero sequence relative short-circuit voltage
            #vkr0_percent** - real part of zero sequence relative short-circuit voltage
            #mag0_percent** - ratio between magnetizing and short circuit impedance (zero sequence)                                
            #mag0_rx**  - zero sequence magnetizing r/x  ratio
            #si0_hv_partial** - zero sequence short circuit impedance  distribution in hv side
            #vk0_percent=in_data[x]['vk0_percent'], vkr0_percent=in_data[x]['vkr0_percent'], mag0_percent=in_data[x]['mag0_percent'], si0_hv_partial=in_data[x]['si0_hv_partial'],
        if (in_data[x]['typ'].startswith("Transformer")): 
            pp.create_transformer_from_parameters(net, hv_bus = eval(in_data[x]['hv_bus']), lv_bus = eval(in_data[x]['lv_bus']), name=in_data[x]['name'], id=in_data[x]['id'], sn_mva=in_data[x]['sn_mva'], vn_hv_kv=in_data[x]['vn_hv_kv'], vn_lv_kv=in_data[x]['vn_lv_kv'],
                                                  vkr_percent=in_data[x]['vkr_percent'], vk_percent=in_data[x]['vk_percent'], pfe_kw=in_data[x]['pfe_kw'], i0_percent=in_data[x]['i0_percent'], vector_group=in_data[x]['vector_group'],
                                                  parallel=in_data[x]['parallel'], shift_degree=in_data[x]['shift_degree'], tap_side=in_data[x]['tap_side'], tap_pos=in_data[x]['tap_pos'], tap_neutral=in_data[x]['tap_neutral'], tap_max=in_data[x]['tap_max'], tap_min=in_data[x]['tap_min'], tap_step_percent=in_data[x]['tap_step_percent'], tap_step_degree=in_data[x]['tap_step_degree'],  
                                                )#tap_phase_shifter=eval(in_data[x]['tap_phase_shifter'])
       
        if (in_data[x]['typ'].startswith("Three Winding Transformer")):  
            pp.create_transformer3w_from_parameters(net, hv_bus = eval(in_data[x]['hv_bus']), mv_bus = eval(in_data[x]['mv_bus']), lv_bus = eval(in_data[x]['lv_bus']), name=in_data[x]['name'], id=in_data[x]['id'],
                                                    sn_hv_mva=in_data[x]['sn_hv_mva'], sn_mv_mva=in_data[x]['sn_mv_mva'], sn_lv_mva=in_data[x]['sn_lv_mva'], 
                                                    vn_hv_kv=in_data[x]['vn_hv_kv'], vn_mv_kv=in_data[x]['vn_mv_kv'], vn_lv_kv=in_data[x]['vn_lv_kv'], 
                                                    vk_hv_percent=in_data[x]['vk_hv_percent'], vk_mv_percent=in_data[x]['vk_mv_percent'], vk_lv_percent=in_data[x]['vk_lv_percent'], 
                                                    vkr_hv_percent=in_data[x]['vkr_hv_percent'], vkr_mv_percent=in_data[x]['vkr_mv_percent'], vkr_lv_percent=in_data[x]['vkr_lv_percent'], 
                                                    pfe_kw=in_data[x]['pfe_kw'], i0_percent=in_data[x]['i0_percent'], 
                                                     vector_group=in_data[x]['vector_group'],                                                    
                                                    shift_mv_degree=in_data[x]['shift_mv_degree'], shift_lv_degree=in_data[x]['shift_lv_degree'], tap_step_percent=in_data[x]['tap_step_percent'], tap_side=in_data[x]['tap_side'],  tap_min=in_data[x]['tap_min'], tap_max=in_data[x]['tap_max'], tap_pos=in_data[x]['tap_pos']) #tap_neutral=in_data[x]['tap_neutral'],, tap_at_star_point=in_data[x]['tap_at_star_point'], vk0_hv_percent=in_data[x]['vk0_hv_percent'], vk0_mv_percent=in_data[x]['vk0_mv_percent'], vk0_lv_percent=in_data[x]['vk0_lv_percent'], vkr0_hv_percent=in_data[x]['vkr0_hv_percent'], vkr0_mv_percent=in_data[x]['vkr0_mv_percent'], vkr0_lv_percent=in_data[x]['vkr0_lv_percent'],
        
        if (in_data[x]['typ'].startswith("Shunt Reactor")):  
            pp.create_shunt(net, typ = "shuntreactor", bus = eval(in_data[x]['bus']), name=in_data[x]['name'], id=in_data[x]['id'], p_mw=in_data[x]['p_mw'], q_mvar=in_data[x]['q_mvar'], vn_kv=in_data[x]['vn_kv'], step=in_data[x]['step'], max_step=in_data[x]['max_step'], in_service = True)
        
        if (in_data[x]['typ'].startswith("Capacitor")):  
            pp.create_shunt_as_capacitor(net, typ = "capacitor", bus = eval(in_data[x]['bus']), name=in_data[x]['name'], id=in_data[x]['id'], q_mvar=float(in_data[x]['q_mvar']), loss_factor=float(in_data[x]['loss_factor']), vn_kv=in_data[x]['vn_kv'], step=in_data[x]['step'], max_step=in_data[x]['max_step'])        
        
        if (in_data[x]['typ'].startswith("Load")):
            bus_idx = Busbars.get(in_data[x]['bus'])
            if bus_idx is None:
                raise ValueError(f"Bus {in_data[x]['bus']} not found for Load")
            print(f"Creating Load on bus {bus_idx} (name: {in_data[x]['bus']})")
            pp.create_load(net, bus=bus_idx, name=in_data[x]['name'], id=in_data[x]['id'], p_mw=in_data[x]['p_mw'],q_mvar=in_data[x]['q_mvar'],const_z_percent=in_data[x]['const_z_percent'],const_i_percent=in_data[x]['const_i_percent'], sn_mva=in_data[x]['sn_mva'],scaling=in_data[x]['scaling'],type=in_data[x]['type'])
      
        if (in_data[x]['typ'].startswith("Asymmetric Load")):
            pp.create_asymmetric_load(net, bus=eval(in_data[x]['bus']), name=in_data[x]['name'], id=in_data[x]['id'], p_a_mw=in_data[x]['p_a_mw'],p_b_mw=in_data[x]['p_b_mw'],p_c_mw=in_data[x]['p_c_mw'],q_a_mvar=in_data[x]['q_a_mvar'], q_b_mvar=in_data[x]['q_b_mvar'], q_c_mvar=in_data[x]['q_c_mvar'], sn_mva=in_data[x]['sn_mva'], scaling=in_data[x]['scaling'],type=in_data[x]['type'])         
   
        if (in_data[x]['typ'].startswith("Impedance")):
            pp.create_impedance(net, from_bus=eval(in_data[x]['busFrom']), to_bus=eval(in_data[x]['busTo']),  name=in_data[x]['name'], id=in_data[x]['id'], rft_pu=in_data[x]['rft_pu'],xft_pu=in_data[x]['xft_pu'],sn_mva=in_data[x]['sn_mva'])         
         
        if (in_data[x]['typ'].startswith("Ward")):
            pp.create_ward(net, bus=eval(in_data[x]['bus']), name=in_data[x]['name'], id=in_data[x]['id'], ps_mw=in_data[x]['ps_mw'],qs_mvar=in_data[x]['qs_mvar'], pz_mw=in_data[x]['pz_mw'], qz_mvar=in_data[x]['qz_mvar'])         
   
        if (in_data[x]['typ'].startswith("Extended Ward")):
            pp.create_xward(net, bus=eval(in_data[x]['bus']), name=in_data[x]['name'], id=in_data[x]['id'], ps_mw=in_data[x]['ps_mw'], qs_mvar=in_data[x]['qs_mvar'], pz_mw=in_data[x]['pz_mw'], qz_mvar=in_data[x]['qz_mvar'], r_ohm =in_data[x]['r_ohm'], x_ohm=in_data[x]['x_ohm'],vm_pu=in_data[x]['vm_pu'])         
   
        if (in_data[x]['typ'].startswith("Motor")):
            pp.create_motor(net, bus=eval(in_data[x]['bus']), name=in_data[x]['name'], id=in_data[x]['id'], pn_mech_mw=in_data[x]['pn_mech_mw'],
                            cos_phi=in_data[x]['cos_phi'],efficiency_n_percent=in_data[x]['efficiency_n_percent'],
                            lrc_pu=in_data[x]['lrc_pu'], rx=in_data[x]['rx'], vn_kv=in_data[x]['vn_kv'],
                            efficiency_percent=in_data[x]['efficiency_percent'], loading_percent=in_data[x]['loading_percent'], scaling=in_data[x]['scaling'])         
   
        
        if (in_data[x]['typ'].startswith("SVC")):            
            pp.create_svc(net, bus=eval(in_data[x]['bus']), name=in_data[x]['name'], id=in_data[x]['id'], x_l_ohm=in_data[x]['x_l_ohm'], x_cvar_ohm=in_data[x]['x_cvar_ohm'], set_vm_pu=in_data[x]['set_vm_pu'], thyristor_firing_angle_degree=in_data[x]['thyristor_firing_angle_degree'], controllable=in_data[x]['controllable'], min_angle_degree=in_data[x]['min_angle_degree'], max_angle_degree=in_data[x]['max_angle_degree'])
         
        if (in_data[x]['typ'].startswith("TCSC")):
            pp.create_tcsc(net, from_bus=eval(in_data[x]['busFrom']), to_bus=eval(in_data[x]['busTo']), name=in_data[x]['name'], id=in_data[x]['id'], x_l_ohm=in_data[x]['x_l_ohm'], x_cvar_ohm=in_data[x]['x_cvar_ohm'], set_p_to_mw=in_data[x]['set_p_to_mw'], thyristor_firing_angle_degree=in_data[x]['thyristor_firing_angle_degree'], controllable=in_data[x]['controllable'], min_angle_degree=in_data[x]['min_angle_degree'], max_angle_degree=in_data[x]['max_angle_degree'])
                   
        if (in_data[x]['typ'].startswith("SSC")):
            pp.create_ssc(net, bus=eval(in_data[x]['bus']), name=in_data[x]['name'], id=in_data[x]['id'], r_ohm=in_data[x]['r_ohm'], x_ohm=in_data[x]['x_ohm'], set_vm_pu=in_data[x]['set_vm_pu'], vm_internal_pu=in_data[x]['vm_internal_pu'], va_internal_degree=in_data[x]['va_internal_degree'], controllable=in_data[x]['controllable'])
        

        if (in_data[x]['typ'].startswith("Storage")):
            pp.create_storage(net, bus=eval(in_data[x]['bus']), name=in_data[x]['name'], id=in_data[x]['id'], p_mw=in_data[x]['p_mw'],max_e_mwh=in_data[x]['max_e_mwh'],q_mvar=in_data[x]['q_mvar'],sn_mva=in_data[x]['sn_mva'], soc_percent=in_data[x]['soc_percent'],min_e_mwh=in_data[x]['min_e_mwh'],scaling=in_data[x]['scaling'], type=in_data[x]['type'])         
   
        if (in_data[x]['typ'].startswith("DC Line")):
            pp.create_dcline(net, from_bus=eval(in_data[x]['busFrom']), to_bus=eval(in_data[x]['busTo']), name=in_data[x]['name'], id=in_data[x]['id'], p_mw=in_data[x]['p_mw'], loss_percent=in_data[x]['loss_percent'], loss_mw=in_data[x]['loss_mw'], vm_from_pu=in_data[x]['vm_from_pu'], vm_to_pu=in_data[x]['vm_to_pu'])



def powerflow(net, algorithm, calculate_voltage_angles, init):
               
         
            #pandapower - rozpływ mocy
            try:
                isolated_buses = top.unsupplied_buses(net)
                if len(isolated_buses) > 0:
                    raise ValueError(f"Isolated buses found: {isolated_buses}. Check your network connectivity.")
                pp.runpp(net, algorithm=algorithm, calculate_voltage_angles=calculate_voltage_angles, init=init) 
            except:
                print("An exception occurred")
                
                # Access initial voltage magnitudes and angles  
                
                diag_result_dict = pp.diagnostic(net, report_style='detailed')             
                
                print(diag_result_dict)
                #plt.simple_plot(net, plot_line_switches=True)
                
                if 'overload' in diag_result_dict: 
                    print('błąd overload')  
                    error_message = []
                    error_message.insert(0, "overload")   
                
                if 'invalid_values' in diag_result_dict: 
                    
                    if 'line' in diag_result_dict['invalid_values']:
                        error_message = diag_result_dict['invalid_values']['line']  
                        error_message.insert(0, "line")      
                        print(error_message)
                    if 'bus' in diag_result_dict['invalid_values']:
                        error_message = diag_result_dict['invalid_values']['bus']
                        error_message.insert(0, "bus")
                    if 'ext_grid' in diag_result_dict['invalid_values']:
                        error_message = diag_result_dict['invalid_values']['ext_grid']
                        error_message.insert(0, "ext_grid")
                if 'nominal_voltages_dont_match'in diag_result_dict:        
                    if 'trafo3w' in diag_result_dict['nominal_voltages_dont_match']:
                        error_message = [('trafo3w', 'trafo3w'),diag_result_dict['nominal_voltages_dont_match']['trafo3w']]
                        
                        #error_message["trafo3w"] = "trafo3w"            
                        print(error_message)
                return error_message      
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

                #response = make_response()
                #response.headers.add("Access-Control-Allow-Origin", "*")
                #response.headers.add("Access-Control-Allow-Headers", "*")
                #response.headers.add("Access-Control-Allow-Methods", "*")
                
                           
                #json.dumps - convert a subset of Python objects into a json string
                #default: If specified, default should be a function that gets called for objects that can't otherwise be serialized. It should return a JSON encodable version of the object or raise a TypeError. If not specified, TypeError is raised. 
                #indent - wcięcia
                response = json.dumps(result, default=lambda o: o.__dict__, indent=4) 
            
                print(response)   
                   
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

    
    fault=in_data['fault']  # Using first bus as fault location    #
    case=in_data['case']
    lv_tol_percent=int(in_data['lv_tol_percent'])
    ip=True
    ith=True
    topology=in_data['topology']
    tk_s=float(in_data['tk_s'])
    r_fault_ohm=float(in_data['r_fault_ohm'])
    x_fault_ohm=float(in_data['x_fault_ohm'])
    inverse_y=in_data['inverse_y']
 

    sc.calc_sc(net, fault=fault, case=case,  ip=ip, ith=ith, tk_s=tk_s, r_fault_ohm=r_fault_ohm, x_fault_ohm=x_fault_ohm, branch_results=True, check_connectivity=True, return_all_currents=True)  #kappa_method='C', , inverse_y=inverse_y,  topology=topology, lv_tol_percent=lv_tol_percent,
    print(net.res_bus_sc)
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
        print('jestem w for') 
        if math.isnan(row['ip_ka']):
            row['ip_ka'] = 'NaN'
        if math.isnan(row['ith_ka']):
            row['ith_ka'] = 'NaN'
                    
        busbar = BusbarOut(name=net.bus._get_value(index, 'name'), id = net.bus._get_value(index, 'id'), ikss_ka=row['ikss_ka'], ip_ka=row['ip_ka'], ith_ka=row['ith_ka'], rk_ohm=row['rk_ohm'], xk_ohm=row['xk_ohm'])    
                 
        busbarList.append(busbar)
        busbars = BusbarsOut(busbars = busbarList)  
            
               
        print(busbars.__dict__)
        print(type(busbars.__dict__))
            #result = {**busbars.__dict__, **lines.__dict__} #łączenie dwóch dictionaries
        result = {**busbars.__dict__}
            #response1 = json.dumps(busbars.__dict__, default=lambda o: o.__dict__, indent=4) 
            #response2 = json.dumps(lines.__dict__, default=lambda o: o.__dict__, indent=4)
            
    response = json.dumps(result, default=lambda o: o.__dict__, indent=4) #json.dumps - convert a subset of Python objects into a json string
        
              
    print(type(response))
    print(response)                                   
    return response 

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
        
        # Try to get diagnostic information
        try:
            diag_result_dict = pp.diagnostic(net, report_style='detailed')
            print(diag_result_dict)
            
            if 'overload' in diag_result_dict: 
                print('Error: overload')  
                error_message = []
                error_message.insert(0, "overload")   
                return error_message
            
            if 'invalid_values' in diag_result_dict: 
                if 'line' in diag_result_dict['invalid_values']:
                    error_message = diag_result_dict['invalid_values']['line']  
                    error_message.insert(0, "line")      
                    return error_message
                if 'bus' in diag_result_dict['invalid_values']:
                    error_message = diag_result_dict['invalid_values']['bus']
                    error_message.insert(0, "bus")
                    return error_message
                if 'ext_grid' in diag_result_dict['invalid_values']:
                    error_message = diag_result_dict['invalid_values']['ext_grid']
                    error_message.insert(0, "ext_grid")
                    return error_message
                    
            if 'nominal_voltages_dont_match' in diag_result_dict:        
                if 'trafo3w' in diag_result_dict['nominal_voltages_dont_match']:
                    error_message = [('trafo3w', 'trafo3w'), diag_result_dict['nominal_voltages_dont_match']['trafo3w']]
                    return error_message
                    
        except Exception as diag_error:
            print(f"Diagnostic failed: {diag_error}")
        
        # Return generic OPF failure message
        error_message = [['opf_failed']]
        return error_message
    
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
                
                # Calculate power factor and Q/P ratio
                p_mw = row['p_mw'] if not pd.isna(row['p_mw']) else 0.0
                q_mvar = row['q_mvar'] if not pd.isna(row['q_mvar']) else 0.0
                
                if p_mw != 0 or q_mvar != 0:
                    pf = p_mw / math.sqrt(p_mw**2 + q_mvar**2) if (p_mw**2 + q_mvar**2) > 0 else 0
                    q_p = q_mvar / p_mw if p_mw != 0 else float('inf')
                else:
                    pf = 0
                    q_p = 0
                
                # Get Lagrange multipliers if available
                lam_p = 0.0
                lam_q = 0.0
                if hasattr(net, 'res_bus_opf') and not net.res_bus_opf.empty:
                    if index in net.res_bus_opf.index:
                        lam_p = net.res_bus_opf.loc[index, 'lam_p'] if 'lam_p' in net.res_bus_opf.columns else 0.0
                        lam_q = net.res_bus_opf.loc[index, 'lam_q'] if 'lam_q' in net.res_bus_opf.columns else 0.0
                
                busbar = BusbarOut(
                    name=bus_name,
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
                
                # Get shadow prices if available
                mu_sf = 0.0
                mu_st = 0.0
                if hasattr(net, 'res_line_opf') and not net.res_line_opf.empty:
                    if index in net.res_line_opf.index:
                        mu_sf = net.res_line_opf.loc[index, 'mu_sf'] if 'mu_sf' in net.res_line_opf.columns else 0.0
                        mu_st = net.res_line_opf.loc[index, 'mu_st'] if 'mu_st' in net.res_line_opf.columns else 0.0
                
                line = LineOut(
                    name=line_name,
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
                    name=gen_name,
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
                
                p_mw = row['p_mw'] if not pd.isna(row['p_mw']) else 0.0
                q_mvar = row['q_mvar'] if not pd.isna(row['q_mvar']) else 0.0
                
                if p_mw != 0 or q_mvar != 0:
                    pf = p_mw / math.sqrt(p_mw**2 + q_mvar**2) if (p_mw**2 + q_mvar**2) > 0 else 0
                    q_p = q_mvar / p_mw if p_mw != 0 else float('inf')
                else:
                    pf = 0
                    q_p = 0
                
                ext_grid = ExternalGridOut(
                    name=ext_grid_name,
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
                
                load = LoadOut(
                    name=load_name,
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