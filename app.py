# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify, make_response
from flask_cors import CORS, cross_origin #żeby działało trzeba wywołać polecenie pip install -U flask-cors==3.0.10 
import pandapower as pp
import pandapower.shortcircuit as sc
import pandas as pd
import math

import numpy as np
import re
import json

from typing import List

app = Flask(__name__)
cors = CORS(app)# BYŁO, support_credentials=True
app.config['CORS_HEADERS'] = 'Content-Type' # było
#app.config['CORS_ORIGINS'] = 'http://128.0.0.1:5500' #nie było tego
 #nie było tego

#pobieranie danych z frontend
@app.route('/', methods=['GET','POST'])
#@cross_origin()
#@cross_origin(origins=['http://127.0.0.1:5500'],allow_headers=['Content-Type, access-control-allow-origin'])#supports_credentials=True #nie było tego
def simulation():
    #in_data = request.get_json()
    in_data = request.get_json(force=True) #force – if set to True the mimetype is ignored.
    print(in_data)   
    
    net = pp.create_empty_network()
    
   
    Busbars = {} 
          
    #utworzenie sieci - w pierwszej petli sczytujemy parametry symulacji i tworzymy szyny
    for x in in_data:    
        if "PowerFlow" in in_data[x]['typ']:
            algorithm=in_data[x]['algorithm']
            calculate_voltage_angles = in_data[x]['calculate_voltage_angles']
            init = in_data[x]['initialization']
        if "ShortCircuit" in in_data[x]['typ']:
            fault=in_data[x]['fault']
            case=in_data[x]['case']
            lv_tol_percent=eval(in_data[x]['lv_tol_percent'])
            ip=True
            ith=True
            topology=in_data[x]['topology']
            tk_s=float(in_data[x]['tk_s'])
            r_fault_ohm=float(in_data[x]['r_fault_ohm'])
            x_fault_ohm=float(in_data[x]['x_fault_ohm'])
            inverse_y=in_data[x]['inverse_y']
        if "Bus" in in_data[x]['typ']:
            Busbars[in_data[x]['name']]=pp.create_bus(net,name=in_data[x]['name'], firstnumberinid=in_data[x]['firstnumberinid'], vn_kv=in_data[x]['vn_kv'], type='b')
          
                         
    #tworzymy zmienne ktorych nazwa odpowiada modelowi z js - np.Hwap0ntfbV98zYtkLMVm-8     
    for name,value in Busbars.items():
        globals()[name] = value    
    
    for x in in_data:
        #eval - rozwiazuje problem z wartosciami NaN
        if (in_data[x]['typ'].startswith("Line")):  
            pp.create_line_from_parameters(net, from_bus=eval(in_data[x]['busFrom']), to_bus=eval(in_data[x]['busTo']), name=in_data[x]['name'], firstnumberinid=in_data[x]['firstnumberinid'], r_ohm_per_km=in_data[x]['r_ohm_per_km'], x_ohm_per_km=in_data[x]['x_ohm_per_km'], c_nf_per_km= in_data[x]['c_nf_per_km'], g_us_per_km= in_data[x]['g_us_per_km'], 
                                           r0_ohm_per_km=1, x0_ohm_per_km=1, c0_nf_per_km=1, endtemp_degree= in_data[x]['endtemp_degree'],
                                           max_i_ka= in_data[x]['max_i_ka'],type= in_data[x]['type'], length_km=in_data[x]['length_km'], parallel=in_data[x]['parallel'], df=in_data[x]['df'])
            #w specyfikacji zapisano, że poniższe parametry są typu nan. Wartosci składowych zerowych mogą być wprowadzone przez funkcję create line.
            #r0_ohm_per_km= in_data[x]['r0_ohm_per_km'], x0_ohm_per_km= in_data[x]['x0_ohm_per_km'], c0_nf_per_km= in_data[x]['c0_nf_per_km'], max_loading_percent=in_data[x]['max_loading_percent'], endtemp_degree=in_data[x]['endtemp_degree'],
        
        if (in_data[x]['typ'].startswith("External Grid")):     
            pp.create_ext_grid(net, bus = eval(in_data[x]['bus']), name=in_data[x]['name'], firstnumberinid=in_data[x]['firstnumberinid'], vm_pu=in_data[x]['vm_pu'], va_degree=in_data[x]['va_degree'],
                               s_sc_max_mva=eval(in_data[x]['s_sc_max_mva']), s_sc_min_mva=eval(in_data[x]['s_sc_min_mva']), rx_max=eval(in_data[x]['rx_max']), rx_min=eval(in_data[x]['rx_min']), r0x0_max=eval(in_data[x]['r0x0_max']), x0x_max=eval(in_data[x]['x0x_max']))
       
        if (in_data[x]['typ'].startswith("Generator")):     
            pp.create_gen(net, bus = eval(in_data[x]['bus']), name=in_data[x]['name'], firstnumberinid=in_data[x]['firstnumberinid'], p_mw=in_data[x]['p_mw'], vm_pu=in_data[x]['vm_pu'], sn_mva=in_data[x]['sn_mva'], scaling=in_data[x]['scaling'],
                          vn_kv=in_data[x]['vn_kv'], xdss_pu=in_data[x]['xdss_pu'], rdss_ohm=in_data[x]['rdss_ohm'], cos_phi=in_data[x]['cos_phi'], pg_percent=in_data[x]['pg_percent'], power_station_trafo=in_data[x]['power_station_trafo'])    
        
        if (in_data[x]['typ'].startswith("Static Generator")):      
            pp.create_sgen(net, bus = eval(in_data[x]['bus']), name=in_data[x]['name'], firstnumberinid=in_data[x]['firstnumberinid'], p_mw=in_data[x]['p_mw'], q_mvar=in_data[x]['q_mvar'], sn_mva=in_data[x]['sn_mva'], scaling=in_data[x]['scaling'], type=in_data[x]['type'],
                           k=in_data[x]['k'], rx=in_data[x]['rx'], generator_type=in_data[x]['generator_type'], lrc_pu=in_data[x]['lrc_pu'], max_ik_ka=in_data[x]['max_ik_ka'], kappa=in_data[x]['kappa'], current_source=in_data[x]['current_source'])   
        
        if (in_data[x]['typ'].startswith("Asymmetric Static Generator")):      
            pp.create_asymmetric_sgen(net, bus = eval(in_data[x]['bus']), name=in_data[x]['name'], firstnumberinid=in_data[x]['firstnumberinid'], p_a_mw=in_data[x]['p_a_mw'], p_b_mw=in_data[x]['p_b_mw'], p_c_mw=in_data[x]['p_c_mw'], q_a_mvar=in_data[x]['q_a_mvar'], q_b_mvar=in_data[x]['q_b_mvar'], q_c_mvar=in_data[x]['q_c_mvar'], sn_mva=in_data[x]['sn_mva'], scaling=in_data[x]['scaling'], type=in_data[x]['type'])   
        #Zero sequence parameters** (Added through std_type For Three phase load flow) :
            #vk0_percent** - zero sequence relative short-circuit voltage
            #vkr0_percent** - real part of zero sequence relative short-circuit voltage
            #mag0_percent** - ratio between magnetizing and short circuit impedance (zero sequence)                                
            #mag0_rx**  - zero sequence magnetizing r/x  ratio
            #si0_hv_partial** - zero sequence short circuit impedance  distribution in hv side
            #vk0_percent=in_data[x]['vk0_percent'], vkr0_percent=in_data[x]['vkr0_percent'], mag0_percent=in_data[x]['mag0_percent'], si0_hv_partial=in_data[x]['si0_hv_partial'],
        if (in_data[x]['typ'].startswith("Transformer")): 
            pp.create_transformer_from_parameters(net, hv_bus = eval(in_data[x]['hv_bus']), lv_bus = eval(in_data[x]['lv_bus']), name=in_data[x]['name'], firstnumberinid=in_data[x]['firstnumberinid'], sn_mva=in_data[x]['sn_mva'], vn_hv_kv=in_data[x]['vn_hv_kv'], vn_lv_kv=in_data[x]['vn_lv_kv'],
                                                  vkr_percent=in_data[x]['vkr_percent'], vk_percent=in_data[x]['vk_percent'], pfe_kw=in_data[x]['pfe_kw'], i0_percent=in_data[x]['i0_percent'], vector_group=in_data[x]['vector_group'],
                                                  parallel=in_data[x]['parallel'], shift_degree=in_data[x]['shift_degree'], tap_side=in_data[x]['tap_side'], tap_pos=in_data[x]['tap_pos'], tap_neutral=in_data[x]['tap_neutral'], tap_max=in_data[x]['tap_max'], tap_min=in_data[x]['tap_min'], tap_step_percent=in_data[x]['tap_step_percent'], tap_step_degree=in_data[x]['tap_step_degree'],  tap_phase_shifter=eval(in_data[x]['tap_phase_shifter']),  
                                                )
       
        if (in_data[x]['typ'].startswith("Three Winding Transformer")):  
            pp.create_transformer3w_from_parameters(net, hv_bus = eval(in_data[x]['hv_bus']), mv_bus = eval(in_data[x]['mv_bus']), lv_bus = eval(in_data[x]['lv_bus']), name=in_data[x]['name'], firstnumberinid=in_data[x]['firstnumberinid'],
                                                    sn_hv_mva=in_data[x]['sn_hv_mva'], sn_mv_mva=in_data[x]['sn_mv_mva'], sn_lv_mva=in_data[x]['sn_lv_mva'], 
                                                    vn_hv_kv=in_data[x]['vn_hv_kv'], vn_mv_kv=in_data[x]['vn_mv_kv'], vn_lv_kv=in_data[x]['vn_lv_kv'], 
                                                    vk_hv_percent=in_data[x]['vk_hv_percent'], vk_mv_percent=in_data[x]['vk_mv_percent'], vk_lv_percent=in_data[x]['vk_lv_percent'], 
                                                    vkr_hv_percent=in_data[x]['vkr_hv_percent'], vkr_mv_percent=in_data[x]['vkr_mv_percent'], vkr_lv_percent=in_data[x]['vkr_lv_percent'], 
                                                    pfe_kw=in_data[x]['pfe_kw'], i0_percent=in_data[x]['i0_percent'], 
                                                    vk0_hv_percent=in_data[x]['vk0_hv_percent'], vk0_mv_percent=in_data[x]['vk0_mv_percent'], vk0_lv_percent=in_data[x]['vk0_lv_percent'], vkr0_hv_percent=in_data[x]['vkr0_hv_percent'], vkr0_mv_percent=in_data[x]['vkr0_mv_percent'], vkr0_lv_percent=in_data[x]['vkr0_lv_percent'], vector_group=in_data[x]['vector_group'],                                                    
                                                    shift_mv_degree=in_data[x]['shift_mv_degree'], shift_lv_degree=in_data[x]['shift_lv_degree'], tap_step_percent=in_data[x]['tap_step_percent'], tap_side=in_data[x]['tap_side'], tap_neutral=in_data[x]['tap_neutral'], tap_min=in_data[x]['tap_min'], tap_max=in_data[x]['tap_max'], tap_pos=in_data[x]['tap_pos'], tap_at_star_point=in_data[x]['tap_at_star_point'])
        
        if (in_data[x]['typ'].startswith("Shunt Reactor")):  
            pp.create_shunt(net, typ = "shuntreactor", bus = eval(in_data[x]['bus']), name=in_data[x]['name'], firstnumberinid=in_data[x]['firstnumberinid'], p_mw=in_data[x]['p_mw'], q_mvar=in_data[x]['q_mvar'], vn_kv=in_data[x]['vn_kv'], step=in_data[x]['step'], max_step=in_data[x]['max_step'], in_service = True)
        
        if (in_data[x]['typ'].startswith("Capacitor")):  
            pp.create_shunt_as_capacitor(net, typ = "capacitor", bus = eval(in_data[x]['bus']), name=in_data[x]['name'], firstnumberinid=in_data[x]['firstnumberinid'], q_mvar=float(in_data[x]['q_mvar']), loss_factor=float(in_data[x]['loss_factor']), vn_kv=in_data[x]['vn_kv'], step=in_data[x]['step'], max_step=in_data[x]['max_step'])        
        
        if (in_data[x]['typ'].startswith("Load")):
            pp.create_load(net, bus=eval(in_data[x]['bus']), name=in_data[x]['name'], firstnumberinid=in_data[x]['firstnumberinid'], p_mw=in_data[x]['p_mw'],q_mvar=in_data[x]['q_mvar'],const_z_percent=in_data[x]['const_z_percent'],const_i_percent=in_data[x]['const_i_percent'], sn_mva=in_data[x]['sn_mva'],scaling=in_data[x]['scaling'],type=in_data[x]['type'])
      
        if (in_data[x]['typ'].startswith("Asymmetric Load")):
            pp.create_asymmetric_load(net, bus=eval(in_data[x]['bus']), name=in_data[x]['name'], firstnumberinid=in_data[x]['firstnumberinid'], p_a_mw=in_data[x]['p_a_mw'],p_b_mw=in_data[x]['p_b_mw'],p_c_mw=in_data[x]['p_c_mw'],q_a_mvar=in_data[x]['q_a_mvar'], q_b_mvar=in_data[x]['q_b_mvar'], q_c_mvar=in_data[x]['q_c_mvar'], sn_mva=in_data[x]['sn_mva'], scaling=in_data[x]['scaling'],type=in_data[x]['type'])         
   
        if (in_data[x]['typ'].startswith("Impedance")):
            pp.create_impedance(net, from_bus=eval(in_data[x]['busFrom']), to_bus=eval(in_data[x]['busTo']),  name=in_data[x]['name'], firstnumberinid=in_data[x]['firstnumberinid'], rft_pu=in_data[x]['rft_pu'],xft_pu=in_data[x]['xft_pu'],sn_mva=in_data[x]['sn_mva'])         
         
        if (in_data[x]['typ'].startswith("Ward")):
            pp.create_ward(net, bus=eval(in_data[x]['bus']), name=in_data[x]['name'], firstnumberinid=in_data[x]['firstnumberinid'], ps_mw=in_data[x]['ps_mw'],qs_mvar=in_data[x]['qs_mvar'], pz_mw=in_data[x]['pz_mw'], qz_mvar=in_data[x]['qz_mvar'])         
   
        if (in_data[x]['typ'].startswith("Extended Ward")):
            pp.create_xward(net, bus=eval(in_data[x]['bus']), name=in_data[x]['name'], firstnumberinid=in_data[x]['firstnumberinid'], ps_mw=in_data[x]['ps_mw'], qs_mvar=in_data[x]['qs_mvar'], pz_mw=in_data[x]['pz_mw'], qz_mvar=in_data[x]['qz_mvar'], r_ohm =in_data[x]['r_ohm'], x_ohm=in_data[x]['x_ohm'],vm_pu=in_data[x]['vm_pu'])         
   
        if (in_data[x]['typ'].startswith("Motor")):
            pp.create_motor(net, bus=eval(in_data[x]['bus']), name=in_data[x]['name'], firstnumberinid=in_data[x]['firstnumberinid'], pn_mech_mw=in_data[x]['pn_mech_mw'],
                            cos_phi=in_data[x]['cos_phi'],efficiency_n_percent=in_data[x]['efficiency_n_percent'],
                            lrc_pu=in_data[x]['lrc_pu'], rx=in_data[x]['rx'], vn_kv=in_data[x]['vn_kv'],
                            efficiency_percent=in_data[x]['efficiency_percent'], loading_percent=in_data[x]['loading_percent'], scaling=in_data[x]['scaling'])         
   
        if (in_data[x]['typ'].startswith("Storage")):
            pp.create_storage(net, bus=eval(in_data[x]['bus']), name=in_data[x]['name'], firstnumberinid=in_data[x]['firstnumberinid'], p_mw=in_data[x]['p_mw'],max_e_mwh=in_data[x]['max_e_mwh'],q_mvar=in_data[x]['q_mvar'],sn_mva=in_data[x]['sn_mva'], soc_percent=in_data[x]['soc_percent'],min_e_mwh=in_data[x]['min_e_mwh'],scaling=in_data[x]['scaling'], type=in_data[x]['type'])         
   
        if (in_data[x]['typ'].startswith("DC Line")):
            pp.create_dcline(net, from_bus=eval(in_data[x]['busFrom']), to_bus=eval(in_data[x]['busTo']), name=in_data[x]['name'], firstnumberinid=in_data[x]['firstnumberinid'], p_mw=in_data[x]['p_mw'], loss_percent=in_data[x]['loss_percent'], loss_mw=in_data[x]['loss_mw'], vm_from_pu=in_data[x]['vm_from_pu'], vm_to_pu=in_data[x]['vm_to_pu'])         
      
    print(net.bus)
    #print(net.shunt)
    print(net.ext_grid)
    
    #print(net.line))
    
        
    for x in in_data:
        if "PowerFlow" in in_data[x]['typ']:   
            #pandapower - rozpływ mocy
            try:
                pp.runpp(net, algorithm=algorithm, calculate_voltage_angles=calculate_voltage_angles, init=init) 
            except:
                print("An exception occurred")
                diag_result_dict = pp.diagnostic(net, report_style='compact') 
                
                #diag_result_json = json.dumps(diag_result_dict,indent = 3)
                print(diag_result_dict)
                
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
                    def __init__(self, name: str, firstnumberinid: str, vm_pu: float, va_degree: float, p_mw: float, q_mvar: float, pf: float, q_p: float):          
                        self.name = name
                        self.firstnumberinid = firstnumberinid
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
                    def __init__(self, name: str, firstnumberinid: str, p_from_mw: float, q_from_mvar: float, p_to_mw: float, q_to_mvar: float, i_from_ka: float, i_to_ka: float, loading_percent: float):          
                        self.name = name
                        self.firstnumberinid= firstnumberinid
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
                    def __init__(self, name: str, firstnumberinid: str, p_mw: float, q_mvar: float, pf: float, q_p:float):          
                        self.name = name
                        self.firstnumberinid = firstnumberinid
                        self.p_mw = p_mw 
                        self.q_mvar = q_mvar  
                        self.pf = pf            
                        self.q_p=q_p              
                       
                class ExternalGridsOut(object):
                    def __init__(self, externalgrids: List[ExternalGridOut]):
                        self.externalgrids = externalgrids              
                externalgridsList = list() 
                
                class GeneratorOut(object):
                    def __init__(self, name: str, firstnumberinid: str, p_mw: float, q_mvar: float, va_degree: float, vm_pu: float):          
                        self.name = name
                        self.firstnumberinid = firstnumberinid
                        self.p_mw = p_mw 
                        self.q_mvar = q_mvar  
                        self.va_degree = va_degree 
                        self.vm_pu = vm_pu                         
                       
                class GeneratorsOut(object):
                    def __init__(self, generators: List[GeneratorOut]):
                        self.generators = generators             
                generatorsList = list()
                
                
                class StaticGeneratorOut(object):
                    def __init__(self, name: str, firstnumberinid: str, p_mw: float, q_mvar: float):          
                        self.name = name
                        self.firstnumberinid = firstnumberinid
                        self.p_mw = p_mw 
                        self.q_mvar = q_mvar                                       
                       
                class StaticGeneratorsOut(object):
                    def __init__(self, staticgenerators: List[StaticGeneratorOut]):
                        self.staticgenerators = staticgenerators             
                staticgeneratorsList = list()
                
                
                class AsymmetricStaticGeneratorOut(object):
                    def __init__(self, name: str, firstnumberinid: str,  p_a_mw: float, q_a_mvar: float, p_b_mw: float, q_b_mvar: float, p_c_mw: float, q_c_mvar: float):          
                        self.name = name
                        self.firstnumberinid = firstnumberinid
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
                    def __init__(self, name: str, firstnumberinid: str, p_hv_mw: float, q_hv_mvar: float, p_lv_mw: float, q_lv_mvar: float, pl_mw: float, ql_mvar: float, i_hv_ka: float, i_lv_ka: float, vm_hv_pu: float, vm_lv_pu: float, va_hv_degree: float, va_lv_degree: float, loading_percent: float):          
                        self.name = name
                        self.firstnumberinid = firstnumberinid
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
                    def __init__(self, name: str, firstnumberinid: str, p_hv_mw: float, q_hv_mvar: float, p_mv_mw: float, q_mv_mvar: float, 
                                 p_lv_mw: float, q_lv_mvar: float, pl_mw: float, ql_mvar: float, i_hv_ka: float, 
                                 i_mv_ka: float, i_lv_ka: float, vm_hv_pu: float, vm_mv_pu: float, 
                                 vm_lv_pu: float, va_hv_degree: float, va_mv_degree: float, va_lv_degree: float, loading_percent: float):          
                        self.name = name
                        self.firstnumberinid = firstnumberinid
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
                    def __init__(self, name: str, firstnumberinid: str, p_mw: float, q_mvar: float, vm_pu: float):          
                        self.name = name
                        self.firstnumberinid = firstnumberinid
                        self.p_mw = p_mw 
                        self.q_mvar = q_mvar  
                        self.vm_pu = vm_pu                          
                       
                class ShuntsOut(object):
                    def __init__(self, shunts: List[ShuntOut]):
                        self.shunts = shunts              
                shuntsList = list() 
                
                
                class CapacitorOut(object):
                    def __init__(self, name: str, firstnumberinid:str, p_mw: float, q_mvar: float, vm_pu: float):          
                        self.name = name
                        self.firstnumberinid = firstnumberinid
                        self.p_mw = p_mw 
                        self.q_mvar = q_mvar  
                        self.vm_pu = vm_pu                          
                       
                class CapacitorsOut(object):
                    def __init__(self, capacitors: List[CapacitorOut]):
                        self.capacitors = capacitors              
                capacitorsList = list()                 
                
                
                class LoadOut(object):
                    def __init__(self, name: str, firstnumberinid:str, p_mw: float, q_mvar: float):          
                        self.name = name
                        self.firstnumberinid = firstnumberinid
                        self.p_mw = p_mw 
                        self.q_mvar = q_mvar 
                                                                    
                class LoadsOut(object):
                    def __init__(self, loads: List[LoadOut]):
                        self.loads = loads              
                loadsList = list() 
                
                
                class AsymmetricLoadOut(object):
                    def __init__(self, name: str, firstnumberinid:str, p_a_mw: float, q_a_mvar: float, p_b_mw: float, q_b_mvar: float, p_c_mw: float, q_c_mvar: float):          
                        self.name = name
                        self.firstnumberinid = firstnumberinid
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
                    def __init__(self, name: str, firstnumberinid:str, p_from_mw: float, q_from_mvar: float, p_to_mw: float, q_to_mvar: float, pl_mw: float, ql_mvar: float, i_from_ka: float, i_to_ka: float ):          
                        self.name = name
                        self.firstnumberinid = firstnumberinid
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
                    def __init__(self, name: str, firstnumberinid:str, p_mw: float, q_mvar: float, vm_pu: float):          
                        self.name = name
                        self.firstnumberinid = firstnumberinid
                        self.p_mw = p_mw 
                        self.q_mvar = q_mvar 
                        self.vm_pu = vm_pu 
                       
                class WardsOut(object):
                    def __init__(self, wards: List[WardOut]):
                        self.wards = wards              
                wardsList = list() 
                
                
                class ExtendedWardOut(object):
                    def __init__(self, name: str, firstnumberinid:str, p_mw: float, q_mvar: float, vm_pu: float):          
                        self.name = name                        
                        self.firstnumberinid = firstnumberinid
                        self.p_mw = p_mw 
                        self.q_mvar = q_mvar 
                        self.vm_pu = vm_pu 
                       
                class ExtendedWardsOut(object):
                    def __init__(self, extendedwards: List[ExtendedWardOut]):
                        self.extendedwards = extendedwards              
                extendedwardsList = list() 
                
                
                class MotorOut(object):
                    def __init__(self, name: str, firstnumberinid:str, p_mw: float, q_mvar: float):          
                        self.name = name
                        self.firstnumberinid = firstnumberinid
                        self.p_mw = p_mw 
                        self.q_mvar = q_mvar 
                       
                       
                class MotorsOut(object):
                    def __init__(self, motors: List[MotorOut]):
                        self.motors = motors              
                motorsList = list() 
                
                
                class StorageOut(object):
                    def __init__(self, name: str, firstnumberinid:str, p_mw: float, q_mvar: float):          
                        self.name = name
                        self.firstnumberinid = firstnumberinid
                        self.p_mw = p_mw 
                        self.q_mvar = q_mvar 
                       
                       
                class StoragesOut(object):
                    def __init__(self, storages: List[StorageOut]):
                        self.storages = storages              
                storagesList = list() 
                
                
                class DClineOut(object):
                    def __init__(self, name: str, firstnumberinid:str, p_from_mw: float, q_from_mvar: float, p_to_mw: float, q_to_mvar: float, pl_mw: float, vm_from_pu: float, va_from_degree: float, vm_to_pu: float, va_to_degree: float):          
                        self.name = name
                        self.firstnumberinid = firstnumberinid
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
                    
                                                                       
                    busbar = BusbarOut(name=net.bus._get_value(index, 'name'), firstnumberinid = net.bus._get_value(index, 'firstnumberinid'), vm_pu=row['vm_pu'], va_degree=row['va_degree'], p_mw=row['p_mw'], q_mvar=row['q_mvar'], pf = pf, q_p=q_p)         
                    busbarList.append(busbar) 
                    busbars = BusbarsOut(busbars = busbarList)
                
                #Line
                if(net.res_line.empty):
                        result = {**busbars.__dict__}                  
                else:                    
                        for index, row in net.res_line.iterrows():    
                            line = LineOut(name=net.line._get_value(index, 'name'), firstnumberinid = net.line._get_value(index, 'firstnumberinid'), p_from_mw=row['p_from_mw'], q_from_mvar=row['q_from_mvar'], p_to_mw=row['p_to_mw'], q_to_mvar=row['q_to_mvar'], i_from_ka=row['i_from_ka'], i_to_ka=row['i_to_ka'], loading_percent=row['loading_percent'])        
                            linesList.append(line) 
                            lines = LinesOut(lines = linesList)
                            
                            result = {**busbars.__dict__, **lines.__dict__} #łączenie dwóch dictionaries                        
                     
                
                #External Grid
                if(net.res_ext_grid.empty):
                        print("no external grid in the model")                
                else:                    
                        for index, row in net.res_ext_grid.iterrows():    
                            externalgrid = ExternalGridOut(name=net.ext_grid._get_value(index, 'name'), firstnumberinid = net.ext_grid._get_value(index, 'firstnumberinid'), p_mw=row['p_mw'], q_mvar=row['q_mvar'], pf = row['p_mw']/math.sqrt(math.pow(row['p_mw'],2)+math.pow(row['q_mvar'],2)), q_p=row['q_mvar']/row['p_mw'])        
                            externalgridsList.append(externalgrid) 
                            externalgrids = ExternalGridsOut(externalgrids = externalgridsList) 
                        result = {**result, **externalgrids.__dict__}          
                             
                #Generator         
                if(net.res_gen.empty):
                        print("no generators in the model")                         
                                    
                else:                    
                        for index, row in net.res_gen.iterrows():    
                            generator = GeneratorOut(name=net.gen._get_value(index, 'name'), firstnumberinid = net.gen._get_value(index, 'firstnumberinid'), p_mw=row['p_mw'], q_mvar=row['q_mvar'], va_degree=row['va_degree'], vm_pu=row['vm_pu'])        
                            generatorsList.append(generator) 
                            generators = GeneratorsOut(generators = generatorsList)
                        
                        result = {**result, **generators.__dict__}
                        
                #Static Generator                     
                if(net.res_sgen.empty):
                        print("no static generators in the model")                         
                                    
                else:                    
                        for index, row in net.res_sgen.iterrows():    
                            staticgenerator = StaticGeneratorOut(name=net.sgen._get_value(index, 'name'), firstnumberinid = net.sgen._get_value(index, 'firstnumberinid'), p_mw=row['p_mw'], q_mvar=row['q_mvar'])        
                            staticgeneratorsList.append(staticgenerator) 
                            staticgenerators = StaticGeneratorsOut(staticgenerators = staticgeneratorsList)
                        
                        result = {**result, **staticgenerators.__dict__}
                        
                        
                
                #Asymmetric Static Generator                     
                if(net.res_asymmetric_sgen.empty):
                        print("no asymmetric static generators in the model")                         
                                    
                else:                    
                        for index, row in net.res_asymmetric_sgen.iterrows():    
                            asymmetricstaticgenerator = AsymmetricStaticGeneratorOut(name=net.asymmetric_sgen._get_value(index, 'name'), firstnumberinid = net.asymmetric_sgen._get_value(index, 'firstnumberinid'), p_a_mw=row['p_a_mw'], q_a_mvar=row['q_a_mvar'], p_b_mw=row['p_b_mw'], q_b_mvar=row['q_b_mvar'], p_c_mw=row['p_c_mw'], q_c_mvar=row['q_c_mvar'])        
                            asymmetricstaticgeneratorsList.append(asymmetricstaticgenerator) 
                            asymmetricstaticgenerators = AsymmetricStaticGeneratorsOut(asymmetricstaticgenerators = asymmetricstaticgeneratorsList)
                        
                        result = {**result, **asymmetricstaticgenerators.__dict__}
                        
                print(net.trafo)
                #Transformer                     
                if(net.res_trafo.empty):
                        print("no transformer in the model")                         
                                    
                else:                    
                        for index, row in net.res_trafo.iterrows():    
                            transformer = TransformerOut(name=net.trafo._get_value(index, 'name'), firstnumberinid = net.trafo._get_value(index, 'firstnumberinid'), p_hv_mw=row['p_hv_mw'], q_hv_mvar=row['q_hv_mvar'], p_lv_mw=row['p_lv_mw'], q_lv_mvar=row['q_lv_mvar'], pl_mw=row['pl_mw'], 
                                                         ql_mvar=row['ql_mvar'], i_hv_ka=row['i_hv_ka'], i_lv_ka=row['i_lv_ka'], vm_hv_pu=row['vm_hv_pu'], vm_lv_pu=row['vm_lv_pu'], va_hv_degree=row['va_hv_degree'], va_lv_degree=row['va_lv_degree'], loading_percent=row['loading_percent'])        
                            transformersList.append(transformer) 
                            transformers = TransformersOut(transformers = transformersList)
                        
                        result = {**result, **transformers.__dict__}   
                        
                        
                #Transformer3W                     
                if(net.res_trafo3w.empty):
                        print("no three winding transformer in the model")                         
                                    
                else:                    
                        for index, row in net.res_trafo3w.iterrows():    
                            transformer3W = Transformer3WOut(name=net.trafo3W._get_value(index, 'name'), firstnumberinid = net.trafo3W._get_value(index, 'firstnumberinid'), p_hv_mw=row['p_hv_mw'], q_hv_mvar=row['q_hv_mvar'], p_mv_mw=row['p_mv_mw'], q_mv_mvar=row['q_mv_mvar'], p_lv_mw=row['p_lv_mw'], 
                                                         q_lv_mvar=row['q_lv_mvar'], pl_mw=row['pl_mw'], ql_mvar=row['ql_mvar'], i_hv_ka=row['i_hv_ka'], i_mv_ka=row['i_mv_ka'], i_lv_ka=row['i_lv_ka'], vm_hv_pu=row['vm_hv_pu'], vm_mv_pu=row['vm_mv_pu'],
                                                         vm_lv_pu=row['vm_lv_pu'], va_hv_degree=row['va_hv_degree'], va_mv_degree=row['va_mv_degree'], va_lv_degree=row['va_lv_degree'], loading_percent=row['loading_percent'])        
                            transformers3WList.append(transformer3W)
                            transformers3W = Transformers3WOut(transformers3W = transformers3WList)
                        
                        result = {**result, **transformers3W.__dict__}  
               
               
                print('net.shunt')         
                print(net.shunt)
                print('net.res_shunt')         
                print(net.res_shunt)
                
                #Shunt reactor
                if(net.res_shunt.empty):
                        print("no shunt reactor in the model")                
                else:                    
                        for index, row in net.res_shunt.iterrows():
                            #if (row['q_mvar'] >= 0):
                            if (net.shunt._get_value(index, 'typ') == 'shuntreactor'):     
                                shunt = ShuntOut(name=net.shunt._get_value(index, 'name'), firstnumberinid = net.shunt._get_value(index, 'firstnumberinid'), p_mw=row['p_mw'], q_mvar=row['q_mvar'], vm_pu = row['vm_pu'])        
                                shuntsList.append(shunt) 
                                shunts = ShuntsOut(shunts = shuntsList) 
                                result = {**result, **shunts.__dict__}  
                        
                #Capacitor
                if(net.res_shunt.empty):
                        print("no capacitor in the model")                
                else:                    
                        for index, row in net.res_shunt.iterrows(): 
                            if (net.shunt._get_value(index, 'typ') == 'capacitor'):  # q is always negative for capacitor
                                capacitor = CapacitorOut(name=net.shunt._get_value(index, 'name'), firstnumberinid = net.shunt._get_value(index, 'firstnumberinid'), p_mw=row['p_mw'], q_mvar=row['q_mvar'], vm_pu = row['vm_pu'])        
                                capacitorsList.append(capacitor) 
                                capacitors = CapacitorsOut(capacitors = capacitorsList) 
                                result = {**result, **capacitors.__dict__}  
                
                print(net.load)  
                print(net.res_load)   
                #Load
                if(net.res_load.empty):
                        print("no load in the model")                
                else:                    
                        for index, row in net.res_load.iterrows():    
                            load = LoadOut(name=net.load._get_value(index, 'name'), firstnumberinid = net.load._get_value(index, 'firstnumberinid'), p_mw=row['p_mw'], q_mvar=row['q_mvar'])        
                            print(load) 
                            loadsList.append(load) 
                            print(loadsList) 
                            loads = LoadsOut(loads = loadsList) 
                        result = {**result, **loads.__dict__}        
                        
                #Asymmetric Load
                if(net.res_asymmetric_load.empty):
                        print("no asymmetric load in the model")                
                else:                    
                        for index, row in net.res_asymmetric_load.iterrows():    
                            asymmetricload = AsymmetricLoadOut(name=net.asymmetric_load._get_value(index, 'name'), firstnumberinid = net.asymmetric_load._get_value(index, 'firstnumberinid'), p_a_mw=row['p_a_mw'], q_a_mvar=row['q_a_mvar'], p_b_mw=row['p_b_mw'], q_b_mvar=row['q_b_mvar'], p_c_mw=row['p_c_mw'], q_c_mvar=row['q_c_mvar'])        
                            asymmetricloadsList.append(asymmetricload) 
                            asymmetricloads = AsymmetricLoadsOut(asymmetricloads = asymmetricloadsList) 
                        result = {**result, **asymmetricloads.__dict__}    
                        
                        
                #Impedance
                if(net.res_impedance.empty):
                        print("no impedance in the model")                
                else:                    
                        for index, row in net.res_impedance.iterrows():    
                            impedance = ImpedanceOut(name=net.impedance._get_value(index, 'name'), firstnumberinid = net.impedance._get_value(index, 'firstnumberinid'), p_from_mw=row['p_from_mw'], q_from_mvar=row['q_from_mvar'], p_to_mw=row['p_to_mw'], q_to_mvar=row['q_to_mvar'], pl_mw=row['pl_mw'], ql_mvar=row['ql_mvar'], i_from_ka=row['i_from_ka'], i_to_ka=row['i_to_ka'])        
                            impedancesList.append(impedance) 
                            impedances = ImpedancesOut(impedances = impedancesList) 
                        result = {**result, **impedances.__dict__} 
                        
                
                #Ward
                if(net.res_ward.empty):
                        print("no ward in the model")                
                else:                    
                        for index, row in net.res_ward.iterrows():    
                            ward = WardOut(name=net.ward._get_value(index, 'name'), firstnumberinid = net.ward._get_value(index, 'firstnumberinid'), p_mw=row['p_mw'], q_mvar=row['q_mvar'], vm_pu=row['vm_pu'])        
                            wardsList.append(ward) 
                            wards = WardsOut(wards = wardsList) 
                        result = {**result, **wards.__dict__} 
                        
                        
                #Extended Ward
                if(net.res_xward.empty):
                        print("no extended ward in the model")                
                else:                    
                        for index, row in net.res_xward.iterrows():    
                            extendedward = ExtendedWardOut(name=net.xward._get_value(index, 'name'), firstnumberinid = net.xward._get_value(index, 'firstnumberinid'), p_mw=row['p_mw'], q_mvar=row['q_mvar'], vm_pu=row['vm_pu'])        
                            extendedwardsList.append(extendedward) 
                            extendedwards = ExtendedWardsOut(extendedwards = extendedwardsList) 
                        result = {**result, **extendedwards.__dict__} 
                        
                        
                #Motor
                if(net.res_motor.empty):
                        print("no motor in the model")                
                else:                    
                        for index, row in net.res_motor.iterrows():    
                            motor = MotorOut(name=net.motor._get_value(index, 'name'), firstnumberinid = net.motor._get_value(index, 'firstnumberinid'), p_mw=row['p_mw'], q_mvar=row['q_mvar'])        
                            motorsList.append(motor) 
                            motors = MotorsOut(motors = motorsList) 
                        result = {**result, **motors.__dict__} 
                        
                #Storage
                if(net.res_storage.empty):
                        print("no storage in the model")                
                else:                    
                        for index, row in net.res_storage.iterrows():    
                            storage = StorageOut(name=net.storage._get_value(index, 'name'), firstnumberinid = net.storage._get_value(index, 'firstnumberinid'), p_mw=row['p_mw'], q_mvar=row['q_mvar'])        
                            storagesList.append(storage) 
                            storages = StoragesOut(storages = storagesList) 
                        result = {**result, **storages.__dict__} 
                
                #DCLine
                if(net.res_dcline.empty):
                        print("no impedance in the model")                
                else:                    
                        for index, row in net.res_dcline.iterrows():    
                            dcline = ImpedanceOut(name=net.dcline._get_value(index, 'name'), firstnumberinid = net.dcline._get_value(index, 'firstnumberinid'), p_from_mw=row['p_from_mw'], q_from_mvar=row['q_from_mvar'], p_to_mw=row['p_to_mw'], q_to_mvar=row['q_to_mvar'], pl_mw=row['pl_mw'], vm_from_pu=row['vm_from_pu'], va_from_degree=row['va_from_degree'], vm_to_pu=row['vm_to_pu'], va_to_degree=row['va_to_degree'] )        
                            dclinesList.append(dcline) 
                            dclines = ImpedancesOut(dclines = dclinesList) 
                        result = {**result, **dclines.__dict__} 
                        
                    
                        
                print(result)
               
                
                           
                #json.dumps - convert a subset of Python objects into a json string
                #default: If specified, default should be a function that gets called for objects that can’t otherwise be serialized. It should return a JSON encodable version of the object or raise a TypeError. If not specified, TypeError is raised. 
                #indent - wcięcia
                response = json.dumps(result, default=lambda o: o.__dict__, indent=4) 
            
                print(response)   
                   
                return response 
           
            
        if "ShortCircuit" in in_data[x]['typ']:   
            #pandapower - rozpływ mocy      
            
                diag_result_dict = pp.diagnostic(net, report_style='compact') 
 
                print(diag_result_dict)      
              
                sc.calc_sc(net, fault=fault, case=case, lv_tol_percent=lv_tol_percent, ip=ip, ith=ith, topology=topology, tk_s=tk_s, kappa_method='C', r_fault_ohm=r_fault_ohm, x_fault_ohm=x_fault_ohm, branch_results=True, check_connectivity=True, return_all_currents=True, inverse_y=inverse_y)  
                print(net.res_bus_sc)
                #print(net.res_line_sc) # nie uwzględniam ze względu na: Branch results are in beta mode and might not always be reliable, especially for transformers
                
                #wyrzuciłem skss_mw bo wyskakiwał błąd przy zwarciu jednofazowym
                class BusbarOut(object):
                    def __init__(self, name: str, firstnumberinid: str, ikss_ka: float, ip_ka: float, ith_ka: float, rk_ohm: float, xk_ohm: float):          
                        self.name = name
                        self.firstnumberinid = firstnumberinid
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
                    if math.isnan(row['ip_ka']):
                        row['ip_ka'] = 'NaN'
                    if math.isnan(row['ith_ka']):
                        row['ith_ka'] = 'NaN'
                    
                    busbar = BusbarOut(name=net.bus._get_value(index, 'name'), firstnumberinid = net.bus._get_value(index, 'firstnumberinid'), ikss_ka=row['ikss_ka'], ip_ka=row['ip_ka'], ith_ka=row['ith_ka'], rk_ohm=row['rk_ohm'], xk_ohm=row['xk_ohm'])    
                 
                    busbarList.append(busbar)
                    busbars = BusbarsOut(busbars = busbarList)
                
                """ 
                class LineOut(object):
                    def __init__(self, name: str, ikss_ka: float, ip_ka: float, ith_ka: float):          
                        self.name = name
                        self.ikss_ka = ikss_ka
                        self.ip_ka = ip_ka 
                        self.ith_ka = ith_ka
                        
                class LinesOut(object):
                    def __init__(self, lines: List[BusbarOut]):
                        self.lines = lines                
                
                linesList = list()      
                
                for index, row in net.res_line_sc.iterrows():    
                    line = LineOut(name=net.line._get_value(index, 'name'), ikss_ka=row['ikss_ka'], ip_ka=row['ip_ka'], ith_ka=row['ith_ka'])        
                    linesList.append(line)       
                    lines = LinesOut(lines = linesList)
                    
                """
                
                #print(bus_results)
                    
                #response = make_response(resultFrame.to_json())
                #response = make_response(bus_results.to_json())
                print(type(busbars.__dict__))
                #result = {**busbars.__dict__, **lines.__dict__} #łączenie dwóch dictionaries
                result = {**busbars.__dict__}
                #response1 = json.dumps(busbars.__dict__, default=lambda o: o.__dict__, indent=4) 
                #response2 = json.dumps(lines.__dict__, default=lambda o: o.__dict__, indent=4)
                
                response = json.dumps(result, default=lambda o: o.__dict__, indent=4) #json.dumps - convert a subset of Python objects into a json string
               
                print(type(response))
                print(response)           
      
                  
                return response 
        
          
if __name__ == '__main__':
    app.debug = False
    app.run(host = '127.0.0.1', port=5005)
   # app.debug = True
   # app.run(host = '0.0.0.0', port=5005)