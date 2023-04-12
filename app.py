# -*- coding: utf-8 -*-
"""
Created on Thu Aug 27 16:25:53 2020

@author: dom
"""

from flask import Flask, request, jsonify, make_response
from flask_cors import CORS, cross_origin #żeby działało trzeba wywołać polecenie pip install -U flask-cors
import pandapower as pp
import pandapower.shortcircuit as sc
import pandas as pd
import math

import numpy as np
import re
import json

from typing import List

app = Flask(__name__)
cors = CORS(app)#, support_credentials=True
app.config['CORS_HEADERS'] = 'Content-Type'



@app.route('/')
def hello():  
    return "Hello Spyder!"

#pobieranie danych z frontend
@app.route('/json-example', methods=['GET','POST'])
#@cross_origin()#supports_credentials=True
def json_example():
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
            Busbars[in_data[x]['name']]=pp.create_bus(net,name=in_data[x]['name'], vn_kv=in_data[x]['vn_kv'], type=in_data[x]['type'])
          
                         
    #tworzymy zmienne ktorych nazwa odpowiada modelowi z js - np.Hwap0ntfbV98zYtkLMVm-8     
    for name,value in Busbars.items():
        globals()[name] = value    
    
    for x in in_data:
        #eval - rozwiazuje problem z wartosciami NaN
        if (in_data[x]['typ'].startswith("Line")):  
            pp.create_line_from_parameters(net, from_bus=eval(in_data[x]['busFrom']), to_bus=eval(in_data[x]['busTo']), name=in_data[x]['name'], r_ohm_per_km=in_data[x]['r_ohm_per_km'], x_ohm_per_km=in_data[x]['x_ohm_per_km'], c_nf_per_km= in_data[x]['c_nf_per_km'], g_us_per_km= in_data[x]['g_us_per_km'], 
                                           r0_ohm_per_km=1, x0_ohm_per_km=1, c0_nf_per_km=1, endtemp_degree= in_data[x]['endtemp_degree'],
                                           max_i_ka= in_data[x]['max_i_ka'],type= in_data[x]['type'], length_km=in_data[x]['length_km'], parallel=in_data[x]['parallel'], df=in_data[x]['df'])
            #w specyfikacji zapisano, że poniższe parametry są typu nan. Wartosci składowych zerowych mogą być wprowadzone przez funkcję create line.
            #r0_ohm_per_km= in_data[x]['r0_ohm_per_km'], x0_ohm_per_km= in_data[x]['x0_ohm_per_km'], c0_nf_per_km= in_data[x]['c0_nf_per_km'], max_loading_percent=in_data[x]['max_loading_percent'], endtemp_degree=in_data[x]['endtemp_degree'],
        
        if (in_data[x]['typ'].startswith("External Grid")):     
            pp.create_ext_grid(net, bus = eval(in_data[x]['bus']), name=in_data[x]['name'], vm_pu=in_data[x]['vm_pu'], va_degree=in_data[x]['va_degree'],
                               s_sc_max_mva=eval(in_data[x]['s_sc_max_mva']), s_sc_min_mva=eval(in_data[x]['s_sc_min_mva']), rx_max=eval(in_data[x]['rx_max']), rx_min=eval(in_data[x]['rx_min']), r0x0_max=eval(in_data[x]['r0x0_max']), x0x_max=eval(in_data[x]['x0x_max']))
       
        if (in_data[x]['typ'].startswith("Generator")):     
            pp.create_gen(net, bus = eval(in_data[x]['bus']), name=in_data[x]['name'], p_mw=in_data[x]['p_mw'], vm_pu=in_data[x]['vm_pu'], sn_mva=in_data[x]['sn_mva'], scaling=in_data[x]['scaling'],
                          vn_kv=in_data[x]['vn_kv'], xdss_pu=in_data[x]['xdss_pu'], rdss_ohm=in_data[x]['rdss_ohm'], cos_phi=in_data[x]['cos_phi'], pg_percent=in_data[x]['pg_percent'], power_station_trafo=in_data[x]['power_station_trafo'])    
        
        if (in_data[x]['typ'].startswith("Static Generator")):      
            pp.create_sgen(net, bus = eval(in_data[x]['bus']), name=in_data[x]['name'], p_mw=in_data[x]['p_mw'], q_mvar=in_data[x]['q_mvar'], sn_mva=in_data[x]['sn_mva'], scaling=in_data[x]['scaling'], type=in_data[x]['type'],
                           k=in_data[x]['k'], rx=in_data[x]['rx'], generator_type=in_data[x]['generator_type'], lrc_pu=in_data[x]['lrc_pu'], max_ik_ka=in_data[x]['max_ik_ka'], kappa=in_data[x]['kappa'], current_source=in_data[x]['current_source'])   
        
        if (in_data[x]['typ'].startswith("Asymmetric Static Generator")):      
            pp.create_asymmetric_sgen(net, bus = eval(in_data[x]['bus']), name=in_data[x]['name'], p_a_mw=in_data[x]['p_a_mw'], p_b_mw=in_data[x]['p_b_mw'], p_c_mw=in_data[x]['p_c_mw'], q_a_mvar=in_data[x]['q_a_mvar'], q_b_mvar=in_data[x]['q_b_mvar'], q_c_mvar=in_data[x]['q_c_mvar'], sn_mva=in_data[x]['sn_mva'], scaling=in_data[x]['scaling'], type=in_data[x]['type'])   
        #Zero sequence parameters** (Added through std_type For Three phase load flow) :
            #vk0_percent** - zero sequence relative short-circuit voltage
            #vkr0_percent** - real part of zero sequence relative short-circuit voltage
            #mag0_percent** - ratio between magnetizing and short circuit impedance (zero sequence)                                
            #mag0_rx**  - zero sequence magnetizing r/x  ratio
            #si0_hv_partial** - zero sequence short circuit impedance  distribution in hv side
            #vk0_percent=in_data[x]['vk0_percent'], vkr0_percent=in_data[x]['vkr0_percent'], mag0_percent=in_data[x]['mag0_percent'], si0_hv_partial=in_data[x]['si0_hv_partial'],
        if (in_data[x]['typ'].startswith("Transformer")): 
            pp.create_transformer_from_parameters(net, hv_bus = eval(in_data[x]['hv_bus']), lv_bus = eval(in_data[x]['lv_bus']), sn_mva=in_data[x]['sn_mva'], vn_hv_kv=in_data[x]['vn_hv_kv'], vn_lv_kv=in_data[x]['vn_lv_kv'],
                                                  vkr_percent=in_data[x]['vkr_percent'], vk_percent=in_data[x]['vk_percent'], pfe_kw=in_data[x]['pfe_kw'], i0_percent=in_data[x]['i0_percent'], vector_group=in_data[x]['vector_group'],
                                                  parallel=in_data[x]['parallel'], shift_degree=in_data[x]['shift_degree'], tap_side=in_data[x]['tap_side'], tap_pos=in_data[x]['tap_pos'], tap_neutral=in_data[x]['tap_neutral'], tap_max=in_data[x]['tap_max'], tap_min=in_data[x]['tap_min'], tap_step_percent=in_data[x]['tap_step_percent'], tap_step_degree=in_data[x]['tap_step_degree'],  tap_phase_shifter=eval(in_data[x]['tap_phase_shifter']),  
                                                )
       
        if (in_data[x]['typ'].startswith("Three Winding Transformer")):  
            pp.create_transformer3w_from_parameters(net, hv_bus = eval(in_data[x]['hv_bus']), mv_bus = eval(in_data[x]['mv_bus']), lv_bus = eval(in_data[x]['lv_bus']), name=in_data[x]['name'], 
                                                    sn_hv_mva=in_data[x]['sn_hv_mva'], sn_mv_mva=in_data[x]['sn_mv_mva'], sn_lv_mva=in_data[x]['sn_lv_mva'], 
                                                    vn_hv_kv=in_data[x]['vn_hv_kv'], vn_mv_kv=in_data[x]['vn_mv_kv'], vn_lv_kv=in_data[x]['vn_lv_kv'], 
                                                    vk_hv_percent=in_data[x]['vk_hv_percent'], vk_mv_percent=in_data[x]['vk_mv_percent'], vk_lv_percent=in_data[x]['vk_lv_percent'], 
                                                    vkr_hv_percent=in_data[x]['vkr_hv_percent'], vkr_mv_percent=in_data[x]['vkr_mv_percent'], vkr_lv_percent=in_data[x]['vkr_lv_percent'], 
                                                    pfe_kw=in_data[x]['pfe_kw'], i0_percent=in_data[x]['i0_percent'], 
                                                    vk0_hv_percent=in_data[x]['vk0_hv_percent'], vk0_mv_percent=in_data[x]['vk0_mv_percent'], vk0_lv_percent=in_data[x]['vk0_lv_percent'], vkr0_hv_percent=in_data[x]['vkr0_hv_percent'], vkr0_mv_percent=in_data[x]['vkr0_mv_percent'], vkr0_lv_percent=in_data[x]['vkr0_lv_percent'], vector_group=in_data[x]['vector_group'],                                                    
                                                    shift_mv_degree=in_data[x]['shift_mv_degree'], shift_lv_degree=in_data[x]['shift_lv_degree'], tap_step_percent=in_data[x]['tap_step_percent'], tap_side=in_data[x]['tap_side'], tap_neutral=in_data[x]['tap_neutral'], tap_min=in_data[x]['tap_min'], tap_max=in_data[x]['tap_max'], tap_pos=in_data[x]['tap_pos'], tap_at_star_point=in_data[x]['tap_at_star_point'])
        
        if (in_data[x]['typ'].startswith("Shunt Reactor")):  
            pp.create_shunt(net, bus = eval(in_data[x]['bus']), p_mw=in_data[x]['p_mw'], q_mvar=in_data[x]['q_mvar'], vn_kv=in_data[x]['vn_kv'], step=in_data[x]['step'], max_step=in_data[x]['max_step'])
        
        if (in_data[x]['typ'].startswith("Capacitor")):  
            pp.create_shunt_as_capacitor(net, bus = eval(in_data[x]['bus']), q_mvar=in_data[x]['q_mvar'], loss_factor=in_data[x]['loss_factor'], vn_kv=in_data[x]['vn_kv'], step=in_data[x]['step'], max_step=in_data[x]['max_step'])        
        
        if (in_data[x]['typ'].startswith("Load")):
            pp.create_load(net, bus=eval(in_data[x]['bus']), p_mw=in_data[x]['p_mw'],q_mvar=in_data[x]['q_mvar'],const_z_percent=in_data[x]['const_z_percent'],const_i_percent=in_data[x]['const_i_percent'], sn_mva=in_data[x]['sn_mva'],scaling=in_data[x]['scaling'],type=in_data[x]['type'])
      
        if (in_data[x]['typ'].startswith("Asymmetric Load")):
            pp.create_asymmetric_load(net, bus=eval(in_data[x]['bus']), p_a_mw=in_data[x]['p_a_mw'],p_b_mw=in_data[x]['p_b_mw'],p_c_mw=in_data[x]['p_c_mw'],q_a_mvar=in_data[x]['q_a_mvar'], q_b_mvar=in_data[x]['q_b_mvar'], q_c_mvar=in_data[x]['q_c_mvar'], sn_mva=in_data[x]['sn_mva'], scaling=in_data[x]['scaling'],type=in_data[x]['type'])         
   
        if (in_data[x]['typ'].startswith("Impedance")):
            pp.create_impedance(net, from_bus=eval(in_data[x]['busFrom']), to_bus=eval(in_data[x]['busTo']), rft_pu=in_data[x]['rft_pu'],xft_pu=in_data[x]['xft_pu'],sn_mva=in_data[x]['sn_mva'])         
         
        if (in_data[x]['typ'].startswith("Ward")):
            pp.create_ward(net, bus=eval(in_data[x]['bus']), ps_mw=in_data[x]['ps_mw'],qs_mvar=in_data[x]['qs_mvar'], pz_mw=in_data[x]['pz_mw'], qz_mvar=in_data[x]['qz_mvar'])         
   
        if (in_data[x]['typ'].startswith("Extended Ward")):
            pp.create_xward(net, bus=eval(in_data[x]['bus']), ps_mw=in_data[x]['ps_mw'], qs_mvar=in_data[x]['qs_mvar'], pz_mw=in_data[x]['pz_mw'], qz_mvar=in_data[x]['qz_mvar'], r_ohm =in_data[x]['r_ohm'], x_ohm=in_data[x]['x_ohm'],vm_pu=in_data[x]['vm_pu'])         
   
        if (in_data[x]['typ'].startswith("Motor")):
            pp.create_motor(net, bus=eval(in_data[x]['bus']), pn_mech_mw=in_data[x]['pn_mech_mw'],
                            cos_phi=in_data[x]['cos_phi'],efficiency_n_percent=in_data[x]['efficiency_n_percent'],
                            lrc_pu=in_data[x]['lrc_pu'], rx=in_data[x]['rx'], vn_kv=in_data[x]['vn_kv'],
                            efficiency_percent=in_data[x]['efficiency_percent'], loading_percent=in_data[x]['loading_percent'], scaling=in_data[x]['scaling'])         
   
        if (in_data[x]['typ'].startswith("Storage")):
            pp.create_storage(net, bus=eval(in_data[x]['bus']), p_mw=in_data[x]['p_mw'],max_e_mwh=in_data[x]['max_e_mwh'],q_mvar=in_data[x]['q_mvar'],sn_mva=in_data[x]['sn_mva'], soc_percent=in_data[x]['soc_percent'],min_e_mwh=in_data[x]['min_e_mwh'],scaling=in_data[x]['scaling'], type=in_data[x]['type'])         
   
        if (in_data[x]['typ'].startswith("DC Line")):
            pp.create_dcline(net, from_bus=eval(in_data[x]['busFrom']), to_bus=eval(in_data[x]['busTo']), p_mw=in_data[x]['p_mw'], loss_percent=in_data[x]['loss_percent'], loss_mw=in_data[x]['loss_mw'], vm_from_pu=in_data[x]['vm_from_pu'], vm_to_pu=in_data[x]['vm_to_pu'])         
      
    #print(net.bus)
    #print(net.line))
    
        
    for x in in_data:
        if "PowerFlow" in in_data[x]['typ']:   
            #pandapower - rozpływ mocy
            try:
                pp.runpp(net, algorithm=algorithm, calculate_voltage_angles=calculate_voltage_angles, init=init)    
                
                class BusbarOut(object):
                    def __init__(self, name: str, vm_pu: float, va_degree: float, p_mw: float, q_mvar: float, pf: float):          
                        self.name = name
                        self.vm_pu = vm_pu
                        self.va_degree = va_degree   
                        self.p_mw = p_mw
                        self.q_mvar = q_mvar  
                        self.pf = p_mw/math.sqrt(math.pow(p_mw,2)+math.pow(q_mvar,2))  
                        
                class BusbarsOut(object):
                    def __init__(self, busbars: List[BusbarOut]):
                        self.busbars = busbars                
                
                busbarList = list()      
                
                for index, row in net.res_bus.iterrows():    
                    busbar = BusbarOut(name=net.bus._get_value(index, 'name'), vm_pu=row['vm_pu'], va_degree=row['va_degree'], p_mw=row['p_mw'], q_mvar=row['q_mvar'], pf=pf)         
                    busbarList.append(busbar)
                    busbars = BusbarsOut(busbars = busbarList)
                
                
                class LineOut(object):
                    def __init__(self, name: str, p_from_mw: float, q_from_mvar: float, p_to_mw: float, q_to_mvar: float, i_from_ka: float, i_to_ka: float, loading_percent: float):          
                        self.name = name
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
                
                #jesli nie ma żadnej linii w modelu
                if(net.res_line.empty):
                        result = {**busbars.__dict__}                  
                else:                    
                        for index, row in net.res_line.iterrows():    
                            line = LineOut(name=net.line._get_value(index, 'name'), p_from_mw=row['p_from_mw'], q_from_mvar=row['q_from_mvar'], p_to_mw=row['p_to_mw'], q_to_mvar=row['q_to_mvar'], i_from_ka=row['i_from_ka'], i_to_ka=row['i_to_ka'], loading_percent=row['loading_percent'])        
                            linesList.append(line) 
                            lines = LinesOut(lines = linesList)
                            
                            result = {**busbars.__dict__, **lines.__dict__} #łączenie dwóch dictionaries
                    
                
                
                #print(bus_results)
                    
                #response = make_response(resultFrame.to_json())
                #response = make_response(bus_results.to_json())
                print(type(busbars.__dict__))
                result = {**busbars.__dict__, **lines.__dict__} #łączenie dwóch dictionaries
                
                #response1 = json.dumps(busbars.__dict__, default=lambda o: o.__dict__, indent=4) 
                #response2 = json.dumps(lines.__dict__, default=lambda o: o.__dict__, indent=4)
                
                response = json.dumps(result, default=lambda o: o.__dict__, indent=4) #json.dumps - convert a subset of Python objects into a json string
            
                
                print(type(response))
                print(response)         
             
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
                    def __init__(self, name: str, ikss_ka: float, ip_ka: float, ith_ka: float, rk_ohm: float, xk_ohm: float):          
                        self.name = name
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
                    
                    busbar = BusbarOut(name=net.bus._get_value(index, 'name'), ikss_ka=row['ikss_ka'], ip_ka=row['ip_ka'], ith_ka=row['ith_ka'], rk_ohm=row['rk_ohm'], xk_ohm=row['xk_ohm'])    
                 
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