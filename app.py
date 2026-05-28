# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import pandapower_electrisim
import opendss_electrisim
import os
import json

from flask import Flask, request, jsonify, make_response, Response, stream_with_context
from flask_cors import CORS, cross_origin #żeby działało trzeba wywołać polecenie pip install -U flask-cors==3.0.10 
import pandapower as pp
import pandas as pd
import gzip
import io
import queue
import threading

import numpy as np

from typing import List

import warnings
warnings.filterwarnings("ignore")

app = Flask(__name__)

# Get CORS origins from environment variable or use defaults
cors_origins = os.getenv('CORS_ORIGINS', '').split(',') if os.getenv('CORS_ORIGINS') else [
    # Development origins
    'http://127.0.0.1:5500',
    'http://127.0.0.1:5501',
    'http://localhost:5500',
    'http://localhost:5501',
    'http://localhost:5502',
    'https://03dht3kc-5000.euw.devtunnels.ms',
    # Production origins
    'https://app.electrisim.com',
    'https://www.electrisim.com',
    'https://electrisim.com'
]

# CORS configuration for both development and production
CORS(app, 
     origins=cors_origins, 
     methods=['GET', 'POST', 'OPTIONS'],
     allow_headers=['Content-Type', 'Authorization', 'Access-Control-Allow-Credentials'],
     supports_credentials=True)

app.config['CORS_HEADERS'] = 'Content-Type'
#app.config['CORS_ORIGINS'] = 'http://128.0.0.1:5500' #nie było tego
 #nie było tego
 #@cross_origin()
#@cross_origin(origins=['http://127.0.0.1:5500'],allow_headers=['Content-Type, access-control-allow-origin'])#supports_credentials=True #nie było tego

#pobieranie danych z frontend
@app.route('/')
def index():
        return 'Please send data to backend'

@app.route('/', methods=['GET','POST'])
def simulation():
    try:
        #in_data = request.get_json()
        in_data = request.get_json(force=True) #force – if set to True the mimetype is ignored.
        print(in_data) 
       
        Busbars = {}
        
        # Check for BESS sizing request first (it's in a nested structure)
        if 'bess_sizing_params' in in_data and in_data.get('bess_sizing_params', {}).get('typ') == 'BessSizingPandaPower':
            # Extract user email for logging
            user_email = in_data.get('bess_sizing_params', {}).get('user_email', 'unknown@user.com')
            print(f"=== BESS SIZING REQUESTED BY USER: {user_email} ===")
            
            # Extract BESS sizing parameters
            bess_params = in_data.get('bess_sizing_params', {})
            frequency = float(bess_params.get('frequency', 50))
            algorithm = bess_params.get('algorithm', 'nr')
            calculation_mode = bess_params.get('calculationMode', 'single')
            
            # Check if multiple scenarios mode
            if calculation_mode == 'multiple' and 'scenarios' in bess_params:
                scenarios = bess_params.get('scenarios', [])
                print(f"=== MULTIPLE SCENARIOS MODE: {len(scenarios)} scenarios ===")
                
                scenario_results = []
                for scenario in scenarios:
                    scenario_name = scenario.get('name', 'Unknown')
                    scenario_p = float(scenario.get('p', 0.0))
                    scenario_q = float(scenario.get('q', 0.0))
                    
                    print(f"=== Processing scenario: {scenario_name} (P={scenario_p} MW, Q={scenario_q} Mvar) ===")
                    
                    # Create fresh network for each scenario (as in notebook)
                    net = pp.create_empty_network(f_hz=frequency)
                    Busbars = pandapower_electrisim.create_busbars(in_data, net)
                    pandapower_electrisim.create_other_elements(in_data, net, None, Busbars)
                    
                    # Create scenario-specific params
                    scenario_params = bess_params.copy()
                    scenario_params['targetP'] = scenario_p
                    scenario_params['targetQ'] = scenario_q
                    
                    # Run BESS sizing calculation for this scenario
                    scenario_result_json = pandapower_electrisim.bess_sizing(net, scenario_params)
                    scenario_result = json.loads(scenario_result_json)
                    
                    # Add scenario name to result
                    scenario_result['scenario_name'] = scenario_name
                    scenario_result['scenario_p'] = scenario_p
                    scenario_result['scenario_q'] = scenario_q
                    scenario_results.append(scenario_result)
                
                # Aggregate results
                response_data = json.dumps({
                    'calculationMode': 'multiple',
                    'scenarios': scenario_results,
                    'total_scenarios': len(scenarios)
                })
            else:
                # Single target mode (existing logic)
                print(f"=== SINGLE TARGET MODE ===")
                
                # Create network
                net = pp.create_empty_network(f_hz=frequency)
                Busbars = pandapower_electrisim.create_busbars(in_data, net)
                # Process all elements (create_other_elements loops internally, so call once)
                pandapower_electrisim.create_other_elements(in_data, net, None, Busbars)
                
                # Run BESS sizing calculation
                response_data = pandapower_electrisim.bess_sizing(net, bess_params)
            
            # Check if client accepts gzip compression
            accept_encoding = request.headers.get('Accept-Encoding', '')
            if 'gzip' in accept_encoding and len(response_data) > 1024:
                compressed = gzip.compress(response_data.encode('utf-8'))
                response = make_response(compressed)
                response.headers['Content-Encoding'] = 'gzip'
                response.headers['Content-Type'] = 'application/json'
                response.headers['Content-Length'] = len(compressed)
                return response
            else:
                return response_data
              
        #utworzenie sieci - w pierwszej petli sczytujemy parametry symulacji i tworzymy szyny
        for x in in_data:    
            #print(x)
            if "FuseCharacteristicPreviewPandaPower" in in_data[x].get('typ', ''):
                user_email = in_data[x].get('user_email', 'unknown@user.com')
                print(f"=== FUSE CHARACTERISTIC PREVIEW: {user_email} ===")
                body = pandapower_electrisim.fuse_characteristic_preview(in_data[x])
                return Response(body, mimetype='application/json')

            if "OptimalPowerFlowPandaPower" in in_data[x]['typ']:
                # Extract user email for logging
                user_email = in_data[x].get('user_email', 'unknown@user.com')
                
                # Extract OPF parameters
                opf_params = {
                    'opf_type': in_data[x]['opf_type'],
                    'frequency': eval(in_data[x]['frequency']),
                    'ac_algorithm': in_data[x]['ac_algorithm'],
                    'dc_algorithm': in_data[x]['dc_algorithm'],
                    'calculate_voltage_angles': in_data[x]['calculate_voltage_angles'],
                    'init': in_data[x]['init'],
                    'delta': in_data[x]['delta'],
                    'trafo_model': in_data[x]['trafo_model'],
                    'trafo_loading': in_data[x]['trafo_loading'],
                    'ac_line_model': in_data[x]['ac_line_model'],
                    'numba': in_data[x]['numba'],
                    'suppress_warnings': in_data[x]['suppress_warnings'],
                    'cost_function': in_data[x]['cost_function'],
                    'cost_currency': in_data[x].get('cost_currency') or 'EUR',
                    'generator_cost_cp1': in_data[x].get('generator_cost_cp1') or {},
                    'generator_cost_cp2': in_data[x].get('generator_cost_cp2') or {},
                    'ext_grid_cost_cp1': in_data[x].get('ext_grid_cost_cp1') or {},
                    'ext_grid_cost_cp2': in_data[x].get('ext_grid_cost_cp2') or {},
                    'storage_cost_cp1': in_data[x].get('storage_cost_cp1') or {},
                    'storage_cost_cp2': in_data[x].get('storage_cost_cp2') or {},
                    'sgen_cost_cp1': in_data[x].get('sgen_cost_cp1') or {},
                    'sgen_cost_cp2': in_data[x].get('sgen_cost_cp2') or {},
                    'load_cost_cp1': in_data[x].get('load_cost_cp1') or {},
                    'load_cost_cp2': in_data[x].get('load_cost_cp2') or {},
                    'dcline_cost_cp1': in_data[x].get('dcline_cost_cp1') or {},
                    'dcline_cost_cp2': in_data[x].get('dcline_cost_cp2') or {},
                }
                
                # Create network
                net = pp.create_empty_network(f_hz=opf_params['frequency'])
                Busbars = pandapower_electrisim.create_busbars(in_data, net)
                pandapower_electrisim.create_other_elements(in_data, net, x, Busbars)
                
                # Run optimal power flow
                response = pandapower_electrisim.optimalPowerFlow(net, opf_params)
                return jsonify(response) # Changed to jsonify for direct dict return
            
            if "PowerFlowPandaPower" in in_data[x]['typ']:
                # Extract user email for logging
                user_email = in_data[x].get('user_email', 'unknown@user.com')
                print(f"=== LOAD FLOW SIMULATION REQUESTED BY USER: {user_email} ===")
                
                frequency=eval(in_data[x]['frequency'])
                algorithm=in_data[x]['algorithm']
                calculate_voltage_angles = in_data[x]['calculate_voltage_angles']
                init = in_data[x]['initialization']
                export_python = in_data[x].get('exportPython', False)  # Export Python code flag
                rc2, rc3, rcs = pandapower_electrisim._resolve_controller_family_flags(in_data[x])

                net = pp.create_empty_network(f_hz=frequency)
           
                Busbars = pandapower_electrisim.create_busbars(in_data, net)
                pandapower_electrisim.create_other_elements(in_data, net, x, Busbars)   

                response_data = pandapower_electrisim.powerflow(
                    net, algorithm, calculate_voltage_angles, init, export_python, in_data, Busbars,
                    run_control_trafo2w=rc2, run_control_trafo3w=rc3, run_control_shunt=rcs,
                )  

                # Check if client accepts gzip compression
                accept_encoding = request.headers.get('Accept-Encoding', '')
                if 'gzip' in accept_encoding and len(response_data) > 1024:  # Only compress if > 1KB
                    # Compress response
                    compressed = gzip.compress(response_data.encode('utf-8'))
                    response = make_response(compressed)
                    response.headers['Content-Encoding'] = 'gzip'
                    response.headers['Content-Type'] = 'application/json'
                    response.headers['Content-Length'] = len(compressed)
                    return response
                else:
                    return response_data
            
            
            if "RPCAnalysisPandaPower" in in_data[x]['typ']:
                user_email = in_data[x].get('user_email', 'unknown@user.com')
                print(f"=== RPC ANALYSIS REQUESTED BY USER: {user_email} ===")

                frequency = float(in_data[x].get('frequency', 50))
                net = pp.create_empty_network(f_hz=frequency)
                Busbars = pandapower_electrisim.create_busbars(in_data, net)
                pandapower_electrisim.create_other_elements(in_data, net, x, Busbars)

                q_mode = in_data[x].get('q_capability_mode', 'from_rating')
                if q_mode == 'from_sgen_curve':
                    pandapower_electrisim.apply_sgen_q_capability_curves(
                        net, in_data, rpc_use_diagram_curves=True)

                rpc_params = {
                    'pcc_bus_name': in_data[x].get('pcc_bus_name'),
                    'ext_grid_name': in_data[x].get('ext_grid_name'),
                    'generator_names': in_data[x].get('generator_names', []),
                    'voltage_levels': [float(v) for v in in_data[x].get('voltage_levels', [1.0])],
                    'p_min_mw': in_data[x].get('p_min_mw', 0),
                    'p_max_mw': in_data[x].get('p_max_mw', 0),
                    'p_steps': in_data[x].get('p_steps', 10),
                    'q_capability_mode': q_mode,
                    'limit_overloads': in_data[x].get('limit_overloads', False),
                    'max_loading_percent': in_data[x].get('max_loading_percent', 100),
                    'requirements': in_data[x].get('requirements', None),
                    'verbose_iwamoto': in_data[x].get('verbose_iwamoto', False),
                    'run_control': in_data[x].get('run_control', False),
                    'grid_code_template_key': in_data[x].get('grid_code_template_key'),
                    'grid_code_template_name': in_data[x].get('grid_code_template_name'),
                }

                use_rpc_stream = bool(in_data[x].get('rpc_stream', False))

                if use_rpc_stream:

                    def _rpc_ndjson_stream():
                        q = queue.Queue()

                        def _progress_cb(msg):
                            q.put(('p', msg))

                        def _worker():
                            try:
                                rp = {**rpc_params, '_progress_callback': _progress_cb}
                                out = pandapower_electrisim.reactive_power_capability(net, rp)
                                q.put(('d', out))
                            except Exception as ex:
                                q.put(('e', str(ex)))

                        threading.Thread(target=_worker, daemon=True).start()

                        while True:
                            kind, payload = q.get()
                            if kind == 'p':
                                yield json.dumps({'type': 'progress', 'message': payload}, ensure_ascii=False) + '\n'
                            elif kind == 'e':
                                yield json.dumps({'type': 'error', 'message': payload}, ensure_ascii=False) + '\n'
                                return
                            elif kind == 'd':
                                raw = payload
                                break

                        if raw is None:
                            yield json.dumps({'type': 'error', 'message': 'No RPC result'}, ensure_ascii=False) + '\n'
                            return
                        try:
                            obj = json.loads(raw)
                        except Exception:
                            yield json.dumps({'type': 'error', 'message': 'Invalid RPC JSON'}, ensure_ascii=False) + '\n'
                            return
                        if isinstance(obj, dict) and obj.get('error'):
                            yield json.dumps({'type': 'error', 'message': obj['error']}, ensure_ascii=False) + '\n'
                            return
                        yield json.dumps({'type': 'result', 'data': obj}, ensure_ascii=False, separators=(',', ':')) + '\n'

                    resp = Response(
                        stream_with_context(_rpc_ndjson_stream()),
                        mimetype='application/x-ndjson'
                    )
                    resp.headers['Cache-Control'] = 'no-cache'
                    resp.headers['X-Accel-Buffering'] = 'no'
                    return resp

                response_data = pandapower_electrisim.reactive_power_capability(net, rpc_params)

                accept_encoding = request.headers.get('Accept-Encoding', '')
                if 'gzip' in accept_encoding and len(response_data) > 1024:
                    compressed = gzip.compress(response_data.encode('utf-8'))
                    response = make_response(compressed)
                    response.headers['Content-Encoding'] = 'gzip'
                    response.headers['Content-Type'] = 'application/json'
                    response.headers['Content-Length'] = len(compressed)
                    return response
                else:
                    return response_data

            if "ShortCircuitPandaPower" in in_data[x]['typ']:
                # Extract user email for logging
                user_email = in_data[x].get('user_email', 'unknown@user.com')

                net = pp.create_empty_network()
                Busbars = pandapower_electrisim.create_busbars(in_data, net)
                pandapower_electrisim.create_other_elements(in_data, net, x, Busbars)
                response_data = pandapower_electrisim.shortcircuit(net, in_data[x], in_data)
                
                # Check if client accepts gzip compression
                accept_encoding = request.headers.get('Accept-Encoding', '')
                if 'gzip' in accept_encoding and len(response_data) > 1024:  # Only compress if > 1KB
                    # Compress response
                    compressed = gzip.compress(response_data.encode('utf-8'))
                    response = make_response(compressed)
                    response.headers['Content-Encoding'] = 'gzip'
                    response.headers['Content-Type'] = 'application/json'
                    response.headers['Content-Length'] = len(compressed)
                    return response
                else:
                    return response_data

            if "ShortCircuitOpenDss" in in_data[x]['typ']:
                # Extract user email for logging
                user_email = in_data[x].get('user_email', 'unknown@user.com')
                frequency = int(in_data[x].get('frequency', 50))
                fault_type = in_data[x].get('fault', '3ph')
                export_open_dss_results = in_data[x].get('exportOpenDSSResults', False)

                response_data = opendss_electrisim.shortcircuit(
                    in_data,
                    frequency=frequency,
                    fault_type=fault_type,
                    export_open_dss_results=export_open_dss_results
                )

                accept_encoding = request.headers.get('Accept-Encoding', '')
                if 'gzip' in accept_encoding and len(response_data) > 1024:
                    compressed = gzip.compress(response_data.encode('utf-8'))
                    response = make_response(compressed)
                    response.headers['Content-Encoding'] = 'gzip'
                    response.headers['Content-Type'] = 'application/json'
                    response.headers['Content-Length'] = len(compressed)
                    return response
                else:
                    return response_data
           
            if "PowerFlowOpenDss" in in_data[x]['typ']:
                # Extract user email for logging
                user_email = in_data[x].get('user_email', 'unknown@user.com')
                
                # Extract OpenDSS parameters based on OpenDSS documentation
                # Reference: https://opendss.epri.com/PowerFlow.html
                frequency = eval(in_data[x]['frequency'])  # Base frequency (50 or 60 Hz)
                analysis_type = in_data[x].get('analysisType', 'loadflow')
                mode = in_data[x].get('mode', 'Snapshot')  # Solution mode (Snapshot, Daily, Dutycycle, Yearly)
                algorithm = in_data[x].get('algorithm', 'Normal')  # Solution algorithm (Normal, Newton)
                loadmodel = in_data[x].get('loadmodel', 'Powerflow')  # Load model (Powerflow, Admittance)
                harmonics = in_data[x].get('harmonics', '3,5,7,11,13')
                neglect_load_y = bool(in_data[x].get('neglectLoadY', False))
                max_iterations = int(in_data[x].get('maxIterations', 100))  # Maximum iterations
                tolerance = float(in_data[x].get('tolerance', 0.0001))  # Convergence tolerance
                controlmode = in_data[x].get('controlmode', 'Static')  # Control mode (Static, Event, Time)
                export_commands = in_data[x].get('exportCommands', False)  # Export OpenDSS commands flag
                
                # For backwards compatibility, default to standard power flow when analysisType is missing
                if str(analysis_type).lower() == 'harmonic':
                    response_data = opendss_electrisim.harmonic_analysis(
                        in_data,
                        frequency,
                        mode,
                        algorithm,
                        loadmodel,
                        max_iterations,
                        tolerance,
                        controlmode,
                        harmonics,
                        neglect_load_y,
                        export_commands
                    )
                else:
                    response_data = opendss_electrisim.powerflow(
                        in_data, 
                        frequency, 
                        mode,
                        algorithm, 
                        loadmodel,
                        max_iterations, 
                        tolerance, 
                        controlmode,
                        export_commands
                    )
                
                # Check if client accepts gzip compression
                accept_encoding = request.headers.get('Accept-Encoding', '')
                if 'gzip' in accept_encoding and len(response_data) > 1024:  # Only compress if > 1KB
                    # Compress response
                    compressed = gzip.compress(response_data.encode('utf-8'))
                    response = make_response(compressed)
                    response.headers['Content-Encoding'] = 'gzip'
                    response.headers['Content-Type'] = 'application/json'
                    response.headers['Content-Length'] = len(compressed)
                    return response
                else:
                    return response_data
            
            if "ContingencyAnalysisPandaPower" in in_data[x]['typ']:
                # Extract user email for logging
                user_email = in_data[x].get('user_email', 'unknown@user.com')
                
                # Extract contingency analysis parameters
                contingency_params = {
                    'element_type': in_data[x].get('element_type', 'line'),
                    'voltage_limits': in_data[x].get('voltage_limits', 'true'),
                    'thermal_limits': in_data[x].get('thermal_limits', 'true'),
                    'min_vm_pu': in_data[x].get('min_vm_pu', '0.95'),
                    'max_vm_pu': in_data[x].get('max_vm_pu', '1.05'),
                    'max_loading_percent': in_data[x].get('max_loading_percent', '100'),
                }
                
                # Create network
                net = pp.create_empty_network()
                Busbars = pandapower_electrisim.create_busbars(in_data, net)
                pandapower_electrisim.create_other_elements(in_data, net, x, Busbars)
                
                # Run contingency analysis
                response_data = pandapower_electrisim.contingency_analysis(net, contingency_params)
                
                # Check if client accepts gzip compression
                accept_encoding = request.headers.get('Accept-Encoding', '')
                if 'gzip' in accept_encoding and len(response_data) > 1024:  # Only compress if > 1KB
                    # Compress response
                    compressed = gzip.compress(response_data.encode('utf-8'))
                    response = make_response(compressed)
                    response.headers['Content-Encoding'] = 'gzip'
                    response.headers['Content-Type'] = 'application/json'
                    response.headers['Content-Length'] = len(compressed)
                    return response
                else:
                    return response_data

            if "ProtectionCoordinationPandaPower" in in_data[x]['typ']:
                user_email = in_data[x].get('user_email', 'unknown@user.com')
                print(f"=== PROTECTION COORDINATION REQUESTED BY USER: {user_email} ===")

                prot_params = {
                    'fault_type': in_data[x].get('fault_type', '3ph'),
                    'case': in_data[x].get('case', 'max'),
                    'fault_location_mode': in_data[x].get('fault_location_mode', 'line'),
                    'fault_bus_id': in_data[x].get('fault_bus_id', ''),
                    'sc_line_id': in_data[x].get('sc_line_id'),
                    'sc_fraction': in_data[x].get('sc_fraction', 0.5),
                    'grading_mode': in_data[x].get('grading_mode', 'auto'),
                    'curve_type': in_data[x].get('curve_type', 'standard_inverse'),
                    'overload_factor': in_data[x].get('overload_factor', 1.25),
                    'ct_current_factor': in_data[x].get('ct_current_factor', 1.2),
                    'safety_factor': in_data[x].get('safety_factor', 1.0),
                    't_diff': in_data[x].get('t_diff', 0.3),
                    't_g': in_data[x].get('t_g', 0.5),
                    't_gg': in_data[x].get('t_gg', 0.07),
                    'tms': in_data[x].get('tms', 1.0),
                    't_grade': in_data[x].get('t_grade', 0.5),
                    'export_results': in_data[x].get('export_results', False),
                }

                net = pp.create_empty_network()
                Busbars = pandapower_electrisim.create_busbars(in_data, net)
                pandapower_electrisim.create_other_elements(in_data, net, x, Busbars)

                response_data = pandapower_electrisim.protection_coordination(net, prot_params, in_data)

                accept_encoding = request.headers.get('Accept-Encoding', '')
                if 'gzip' in accept_encoding and len(response_data) > 1024:
                    compressed = gzip.compress(response_data.encode('utf-8'))
                    response = make_response(compressed)
                    response.headers['Content-Encoding'] = 'gzip'
                    response.headers['Content-Type'] = 'application/json'
                    response.headers['Content-Length'] = len(compressed)
                    return response
                else:
                    return response_data

            if "EconomicAnalysisPandaPower" in in_data[x]['typ']:
                # Extract user email for logging
                user_email = in_data[x].get('user_email', 'unknown@user.com')
                print(f"=== ECONOMIC ANALYSIS REQUESTED BY USER: {user_email} ===")
                
                # Extract economic analysis parameters
                economic_params = {
                    'frequency': eval(in_data[x].get('frequency', '50')),
                    'currency': in_data[x].get('currency', 'EUR'),
                    'algorithm': in_data[x].get('algorithm', 'nr'),
                    'calculate_voltage_angles': in_data[x].get('calculate_voltage_angles', 'auto'),
                    'init': in_data[x].get('init', 'dc'),
                    'use_generation_profile': in_data[x].get('use_generation_profile', False),
                    'time_steps': int(in_data[x].get('time_steps', 24)),
                    'lifetime_years': int(in_data[x].get('lifetime_years', 30)),
                    'calculation_mode': in_data[x].get('calculation_mode', 'full'),
                    'load_profile': in_data[x].get('load_profile', 'constant'),
                    'generation_profile': in_data[x].get('generation_profile', 'constant'),
                    'energy_price_per_mwh': in_data[x].get('energy_price_per_mwh'),
                    'energy_price_currency': in_data[x].get('energy_price_currency', 'EUR')
                }
                
                # Create network
                net = pp.create_empty_network(f_hz=economic_params['frequency'])
                Busbars = pandapower_electrisim.create_busbars(in_data, net)
                pandapower_electrisim.create_other_elements(in_data, net, x, Busbars)
                
                # Run economic analysis
                response = pandapower_electrisim.economic_analysis(net, in_data, economic_params)
                print(f"=== ECONOMIC ANALYSIS RESPONSE: total_capex={response.get('total_capex')}, total_power_losses_mw={response.get('total_power_losses_mw')}, error={response.get('error')} ===")
                return jsonify(response)
                
            if "ControllerSimulationPandaPower Parameters" in in_data[x]['typ']:
                # Extract user email for logging
                user_email = in_data[x].get('user_email', 'unknown@user.com')
                
                # Extract controller simulation parameters
                controller_params = {
                    'voltage_control': in_data[x].get('voltage_control', False),
                    'tap_control': in_data[x].get('tap_control', False),
                    'discrete_tap_control': in_data[x].get('discrete_tap_control', False),
                    'continuous_tap_control': in_data[x].get('continuous_tap_control', False),
                    'frequency': eval(in_data[x].get('frequency', '50')),
                    'algorithm': in_data[x].get('algorithm', 'nr'),
                    'calculate_voltage_angles': in_data[x].get('calculate_voltage_angles', 'auto'),
                    'init': in_data[x].get('init', 'dc')
                }
                
                # Create network
                net = pp.create_empty_network(f_hz=controller_params['frequency'])
                Busbars = pandapower_electrisim.create_busbars(in_data, net)
                pandapower_electrisim.create_other_elements(in_data, net, x, Busbars)
                
                # Run controller simulation
                response = pandapower_electrisim.controller_simulation(net, controller_params)
                return jsonify(response)
                
            if "TimeSeriesSimulationPandaPower Parameters" in in_data[x]['typ']:
                # Extract user email for logging
                user_email = in_data[x].get('user_email', 'unknown@user.com')
                
                # Extract time series simulation parameters
                timeseries_params = {
                    'time_steps': int(in_data[x].get('time_steps', 24)),
                    'load_profile': in_data[x].get('load_profile', 'constant'),
                    'generation_profile': in_data[x].get('generation_profile', 'constant'),
                    'profile_mode': in_data[x].get('profile_mode', 'preset'),
                    'element_profiles': in_data[x].get('element_profiles') or {},
                    'frequency': eval(in_data[x].get('frequency', '50')),
                    'algorithm': in_data[x].get('algorithm', 'nr'),
                    'calculate_voltage_angles': in_data[x].get('calculate_voltage_angles', 'auto'),
                    'init': in_data[x].get('init') or in_data[x].get('initialization') or 'auto',
                }
                
                # Create network
                net = pp.create_empty_network(f_hz=timeseries_params['frequency'])
                Busbars = pandapower_electrisim.create_busbars(in_data, net)
                pandapower_electrisim.create_other_elements(in_data, net, x, Busbars)
                
                # Run time series simulation
                response = pandapower_electrisim.time_series_simulation(net, timeseries_params)
                return jsonify(response)
                 
        #print(net.bus)
        #print(net.shunt)
#print(net.ext_grid)    
#print(net.line))

# If no simulation type matches, return error
        return jsonify({'error': 'No valid simulation type found in request data'})
    
    except ValueError as ve:
        # Handle validation errors (like missing bus connections)
        error_message = str(ve)
        print(f"Validation Error: {error_message}")
        return jsonify({'error': error_message}), 400
    
    except Exception as e:
        # Handle other unexpected errors
        error_message = (
            f"Server error: {str(e)} "
            f"- if this problem persists, please contact electrisim@electrisim.com for support."
        )
        print(f"Unexpected Error: {error_message}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': error_message}), 500   


def pandapower_net_to_json(net):
    """
    Convert a pandapower network to the JSON structure expected by the frontend.
    This matches the format used by insertComponentsForData in supportingFunctions.js

    pandapower 3.x DataFrames include extra columns (e.g. zone, controllable) vs the
    fixed tuple positions assumed by the frontend. Missing bus names become None and
    render as "null", so findVertexByBusId matches the same bus for every element.
    We normalize rows/columns here so import layouts resolve correctly.
    """
    import json
    import numpy as np

    def dataframe_to_list(df):
        """Convert a pandapower DataFrame to a list of lists for the frontend"""
        if df.empty:
            return []
        return df.replace({np.nan: None, pd.NA: None}).values.tolist()

    def _is_blank_name(val):
        if val is None:
            return True
        try:
            if pd.isna(val):
                return True
        except Exception:
            pass
        s = str(val).strip()
        return s == '' or s.lower() == 'none'

    def _scalar(val):
        if val is None:
            return None
        try:
            if pd.isna(val):
                return None
        except Exception:
            pass
        if hasattr(val, 'item'):
            try:
                return val.item()
            except Exception:
                pass
        return val

    def _bus_geo_xy_from_cell(val):
        """Return (x, y) from pandapower bus ``geo`` cell (GeoJSON Point) or (None, None)."""
        if val is None:
            return None, None
        try:
            if pd.isna(val):
                return None, None
        except Exception:
            pass
        try:
            if isinstance(val, dict):
                coord = val.get('coordinates')
                if isinstance(coord, (list, tuple)) and len(coord) >= 2:
                    return float(coord[0]), float(coord[1])
        except (TypeError, ValueError):
            return None, None
        return None, None

    def normalize_bus_rows():
        df = net.bus
        if df.empty:
            return []
        used = set()
        names_out = []
        geo_x_out = []
        geo_y_out = []
        for idx in df.index:
            raw = df.at[idx, 'name'] if 'name' in df.columns else None
            if _is_blank_name(raw):
                base = f'Bus_{idx}'
            else:
                base = str(raw).strip()
            uniq = base
            dup = 0
            while uniq in used:
                dup += 1
                uniq = f'{base}_{dup}'
            used.add(uniq)
            names_out.append(uniq)
            gx, gy = None, None
            if 'geo' in df.columns:
                gx, gy = _bus_geo_xy_from_cell(df.at[idx, 'geo'])
            geo_x_out.append(gx)
            geo_y_out.append(gy)
        slim = pd.DataFrame({
            'name': names_out,
            'vn_kv': df['vn_kv'].values if 'vn_kv' in df.columns else 0.0,
            'type': df['type'].values if 'type' in df.columns else 'b',
            'in_service': df['in_service'].values if 'in_service' in df.columns else True,
            'geo_x': geo_x_out,
            'geo_y': geo_y_out,
        }, index=df.index)
        return dataframe_to_list(slim)

    def normalize_ext_grid_rows():
        df = net.ext_grid
        if df.empty:
            return []
        rows = []
        for idx in df.index:
            r = df.loc[idx]
            nm = r['name'] if 'name' in df.columns else None
            if _is_blank_name(nm):
                nm = f'ExtGrid_{idx}'
            rows.append([
                nm,
                int(_scalar(r['bus'])),
                _scalar(r['vm_pu']),
                _scalar(r['va_degree']),
                _scalar(r['slack_weight']),
                bool(_scalar(r['in_service'])) if r.get('in_service') is not None else True,
            ])
        return rows

    def normalize_gen_rows():
        df = net.gen
        if df.empty:
            return []
        rows = []
        for idx in df.index:
            r = df.loc[idx]
            nm = r['name'] if 'name' in df.columns else None
            if _is_blank_name(nm):
                nm = f'Gen_{idx}'
            rows.append([
                nm,
                int(_scalar(r['bus'])),
                _scalar(r['p_mw']),
                _scalar(r['vm_pu']),
                _scalar(r['sn_mva']),
                _scalar(r['min_q_mvar']),
                _scalar(r['max_q_mvar']),
                _scalar(r['scaling']),
                bool(_scalar(r['slack'])) if 'slack' in df.columns and r.get('slack') is not None else False,
                bool(_scalar(r['in_service'])) if r.get('in_service') is not None else True,
                float(_scalar(r['slack_weight'])) if 'slack_weight' in df.columns and r.get('slack_weight') is not None else 0.0,
                _scalar(r['type']) if r.get('type') is not None else 'async',
            ])
        return rows

    def normalize_load_rows():
        df = net.load
        if df.empty:
            return []
        rows = []
        for idx in df.index:
            r = df.loc[idx]
            nm = r['name'] if 'name' in df.columns else None
            if _is_blank_name(nm):
                nm = f'Load_{idx}'
            cz = None
            if 'const_z_percent' in df.columns:
                cz = _scalar(r['const_z_percent'])
            elif 'const_z_p_percent' in df.columns:
                cz = _scalar(r['const_z_p_percent'])
            ci = None
            if 'const_i_percent' in df.columns:
                ci = _scalar(r['const_i_percent'])
            elif 'const_i_p_percent' in df.columns:
                ci = _scalar(r['const_i_p_percent'])
            rows.append([
                nm,
                int(_scalar(r['bus'])),
                _scalar(r['p_mw']),
                _scalar(r['q_mvar']),
                cz,
                ci,
                _scalar(r['sn_mva']),
                _scalar(r['scaling']),
                _scalar(r['type']) if r.get('type') is not None else 'wye',
            ])
        return rows

    def normalize_trafo_rows():
        df = net.trafo
        if df.empty:
            return []
        rows = []
        for idx in df.index:
            r = df.loc[idx]
            nm = r['name'] if 'name' in df.columns else None
            if _is_blank_name(nm):
                nm = f'Trafo_{idx}'
            tap_phase = False
            if 'tap_phase_shifter' in df.columns and r.get('tap_phase_shifter') is not None:
                tap_phase = bool(_scalar(r['tap_phase_shifter']))
            rows.append([
                nm,
                _scalar(r['std_type']),
                int(_scalar(r['hv_bus'])),
                int(_scalar(r['lv_bus'])),
                _scalar(r['sn_mva']),
                _scalar(r['vn_hv_kv']),
                _scalar(r['vn_lv_kv']),
                _scalar(r['vk_percent']),
                _scalar(r['vkr_percent']),
                _scalar(r['pfe_kw']),
                _scalar(r['i0_percent']),
                _scalar(r['shift_degree']),
                _scalar(r['tap_side']),
                _scalar(r['tap_neutral']),
                _scalar(r['tap_min']),
                _scalar(r['tap_max']),
                _scalar(r['tap_step_percent']),
                _scalar(r['tap_step_degree']),
                _scalar(r['tap_pos']),
                tap_phase,
                _scalar(r['parallel']),
                _scalar(r['df']),
                bool(_scalar(r['in_service'])) if r.get('in_service') is not None else True,
            ])
        return rows

    line_cols = [
        'name', 'std_type', 'from_bus', 'to_bus', 'length_km', 'r_ohm_per_km',
        'x_ohm_per_km', 'c_nf_per_km', 'g_us_per_km', 'max_i_ka', 'df',
        'parallel', 'type', 'in_service',
    ]

    def normalize_line_rows():
        df = net.line
        if df.empty:
            return []
        slim = df[[c for c in line_cols if c in df.columns]].copy()
        for idx in slim.index:
            if _is_blank_name(slim.at[idx, 'name']):
                slim.at[idx, 'name'] = f'Line_{idx}'
        return dataframe_to_list(slim)

    def normalize_switch_rows():
        """Export pandapower switches for Electrisim import (protection coordination).

        Each row: [name, bus_name, element_name, et, closed, type, z_ohm, in_ka]
        bus_name / element_name match XML ``name`` on imported buses / lines / trafos.
        """
        if not hasattr(net, 'switch') or net.switch is None or getattr(net.switch, 'empty', True):
            return []
        rows = []
        for idx in net.switch.index:
            r = net.switch.loc[idx]
            nm = r['name'] if 'name' in net.switch.columns else None
            if _is_blank_name(nm):
                nm = f'Switch_{idx}'
            bus_i = int(_scalar(r['bus']))
            try:
                bus_nm = net.bus.at[bus_i, 'name'] if bus_i in net.bus.index else None
            except Exception:
                bus_nm = None
            if _is_blank_name(bus_nm):
                bus_nm = f'Bus_{bus_i}'
            et = _scalar(r['et']) if 'et' in net.switch.columns else 'l'
            if et is None or str(et).strip() == '':
                et = 'l'
            et = str(et)
            el_i = int(_scalar(r['element']))
            elem_nm = None
            try:
                if et == 'l' and not net.line.empty and el_i in net.line.index:
                    elem_nm = net.line.at[el_i, 'name']
                elif et == 't' and not net.trafo.empty and el_i in net.trafo.index:
                    elem_nm = net.trafo.at[el_i, 'name']
                elif et == 't3' and hasattr(net, 'trafo3w') and not net.trafo3w.empty and el_i in net.trafo3w.index:
                    elem_nm = net.trafo3w.at[el_i, 'name']
                elif et == 'b' and el_i in net.bus.index:
                    elem_nm = net.bus.at[el_i, 'name']
            except Exception:
                elem_nm = None
            if _is_blank_name(elem_nm):
                elem_nm = str(el_i)
            closed = True
            if 'closed' in net.switch.columns and r.get('closed') is not None:
                closed = bool(_scalar(r['closed']))
            sw_type = _scalar(r['type']) if 'type' in net.switch.columns and r.get('type') is not None else 'CB'
            zohm = _scalar(r['z_ohm']) if 'z_ohm' in net.switch.columns else 0.0
            inka = _scalar(r['in_ka']) if 'in_ka' in net.switch.columns else float('nan')
            rows.append([nm, bus_nm, elem_nm, et, closed, sw_type, zohm, inka])
        return rows

    model = {
        "_object": {
            "bus": {
                "_object": json.dumps({
                    "data": normalize_bus_rows()
                })
            },
            "line": {
                "_object": json.dumps({
                    "data": normalize_line_rows()
                })
            },
            "switch": {
                "_object": json.dumps({
                    "data": normalize_switch_rows()
                })
            },
            "ext_grid": {
                "_object": json.dumps({
                    "data": normalize_ext_grid_rows()
                })
            },
            "gen": {
                "_object": json.dumps({
                    "data": normalize_gen_rows()
                })
            },
            "sgen": {
                "_object": json.dumps({
                    "data": dataframe_to_list(net.sgen) if hasattr(net, 'sgen') and not net.sgen.empty else []
                })
            },
            "asymmetric_sgen": {
                "_object": json.dumps({
                    "data": dataframe_to_list(net.asymmetric_sgen) if hasattr(net, 'asymmetric_sgen') and not net.asymmetric_sgen.empty else []
                })
            },
            "trafo": {
                "_object": json.dumps({
                    "data": normalize_trafo_rows()
                })
            },
            "trafo3w": {
                "_object": json.dumps({
                    "data": dataframe_to_list(net.trafo3w) if hasattr(net, 'trafo3w') and not net.trafo3w.empty else []
                })
            },
            "shunt": {
                "_object": json.dumps({
                    "data": dataframe_to_list(net.shunt) if hasattr(net, 'shunt') and not net.shunt.empty else []
                })
            },
            "load": {
                "_object": json.dumps({
                    "data": normalize_load_rows()
                })
            },
            "asymmetric_load": {
                "_object": json.dumps({
                    "data": dataframe_to_list(net.asymmetric_load) if hasattr(net, 'asymmetric_load') and not net.asymmetric_load.empty else []
                })
            },
            "impedance": {
                "_object": json.dumps({
                    "data": dataframe_to_list(net.impedance) if hasattr(net, 'impedance') and not net.impedance.empty else []
                })
            },
            "ward": {
                "_object": json.dumps({
                    "data": dataframe_to_list(net.ward) if hasattr(net, 'ward') and not net.ward.empty else []
                })
            },
            "xward": {
                "_object": json.dumps({
                    "data": dataframe_to_list(net.xward) if hasattr(net, 'xward') and not net.xward.empty else []
                })
            },
            "motor": {
                "_object": json.dumps({
                    "data": dataframe_to_list(net.motor) if hasattr(net, 'motor') and not net.motor.empty else []
                })
            },
            "storage": {
                "_object": json.dumps({
                    "data": dataframe_to_list(net.storage) if hasattr(net, 'storage') and not net.storage.empty else []
                })
            },
            "svc": {
                "_object": json.dumps({
                    "data": dataframe_to_list(net.svc) if hasattr(net, 'svc') and not net.svc.empty else []
                })
            },
            "tcsc": {
                "_object": json.dumps({
                    "data": dataframe_to_list(net.tcsc) if hasattr(net, 'tcsc') and not net.tcsc.empty else []
                })
            },
            "dcline": {
                "_object": json.dumps({
                    "data": dataframe_to_list(net.dcline) if hasattr(net, 'dcline') and not net.dcline.empty else []
                })
            }
        }
    }

    return json.dumps(model)


@app.route('/import-pandapower', methods=['POST'])
def import_pandapower():
    """
    Accepts a Pandapower .py script, executes it to build `net`,
    and returns the network as JSON (the structure expected by insertComponentsForData).
    """
    payload = request.get_json(force=True)
    code = payload.get('content', '')

    if not code:
        return jsonify({'error': 'Empty file content'}), 400

    import pandapower as pp
    import sys
    import io

    # Simple execution environment – assumes the script defines a variable `net`
    global_env = {'pp': pp}
    local_env = {}

    try:
        # Capture stdout to suppress print statements from the uploaded script
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        
        try:
            exec(code, global_env, local_env)
        except (UserWarning, Exception) as run_err:
            # Power flow may fail (no reference bus, zero impedance, etc.) - for import we only need the net structure
            net = local_env.get('net') or global_env.get('net')
            if net is not None:
                # Import does not require power flow results; use net topology anyway
                pass
            else:
                raise run_err
        finally:
            sys.stdout = old_stdout
        
        net = local_env.get('net') or global_env.get('net')
        if net is None:
            return jsonify({'error': 'No variable named `net` found in Python file'}), 400

        # Convert pandapower net to the JSON structure the frontend expects
        model_json = pandapower_net_to_json(net)
        # Return as plain JSON string (frontend will JSON.parse it)
        return model_json, 200, {'Content-Type': 'application/json'}
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in import_pandapower: {error_details}")
        return jsonify({'error': str(e), 'details': error_details}), 400


def _infer_opendss_voltage_bases(dss, dss_text=''):
    """Collect line-to-line voltage levels (kV) for OpenDSS calcv from equipment."""
    import re
    import math

    levels = set()
    for vname in dss.Vsources.AllNames() or []:
        try:
            dss.Vsources.Name(vname)
            levels.add(float(dss.Vsources.BasekV()))
        except (TypeError, ValueError):
            pass
    for tname in dss.Transformers.AllNames() or []:
        try:
            dss.Transformers.Name(tname)
            for wdg in (1, 2, 3):
                try:
                    dss.Transformers.Wdg(wdg)
                    kv = float(dss.Transformers.kV())
                    if kv > 0:
                        levels.add(kv)
                except Exception:
                    break
        except (TypeError, ValueError):
            pass
    for pname in dss.PVsystems.AllNames() or []:
        try:
            dss.Circuit.SetActiveClass('PVSystem')
            dss.ActiveClass.Name(pname)
            kv = float(dss.Properties.Value('kV'))
            if kv > 0:
                levels.add(kv)
        except (TypeError, ValueError):
            pass
    m = re.search(r'voltagebases\s*=\s*\[([^\]]+)\]', dss_text, re.IGNORECASE)
    if m:
        for part in m.group(1).split(','):
            try:
                levels.add(float(part.strip()))
            except ValueError:
                pass
    positive = sorted((v for v in levels if v > 0), reverse=True)
    return positive


def _bus_voltages_from_equipment(dss, bus_names):
    """Map each bus to line-to-line kV from Vsource, transformer windings, and PV kV."""
    canon = {b.lower(): b for b in bus_names}
    vn = {}

    def set_vn(bus_raw, kv_ll):
        key = bus_raw.split('.')[0]
        c = canon.get(key.lower())
        if c is None:
            return
        prev = vn.get(c)
        if prev is None or kv_ll > prev:
            vn[c] = kv_ll

    for vname in dss.Vsources.AllNames() or []:
        try:
            dss.Circuit.SetActiveElement(f'Vsource.{vname}')
            bus_raw = dss.CktElement.BusNames()[0]
            dss.Vsources.Name(vname)
            set_vn(bus_raw, float(dss.Vsources.BasekV()))
        except (TypeError, ValueError, IndexError):
            pass

    for tname in dss.Transformers.AllNames() or []:
        try:
            dss.Circuit.SetActiveElement(f'Transformer.{tname}')
            buses = [b.split('.')[0] for b in dss.CktElement.BusNames()]
            dss.Transformers.Name(tname)
            kvs = []
            for wdg in (1, 2, 3):
                try:
                    dss.Transformers.Wdg(wdg)
                    kvs.append(float(dss.Transformers.kV()))
                except Exception:
                    break
            for bus, kv in zip(buses, kvs):
                set_vn(bus, kv)
        except (TypeError, ValueError, IndexError):
            pass

    for pname in dss.PVsystems.AllNames() or []:
        try:
            dss.Circuit.SetActiveClass('PVSystem')
            dss.ActiveClass.Name(pname)
            kv = float(dss.Properties.Value('kV'))
            dss.Circuit.SetActiveElement(f'PVSystem.{pname}')
            set_vn(dss.CktElement.BusNames()[0], kv)
        except (TypeError, ValueError, IndexError):
            pass

    return vn


@app.route('/import-opendss', methods=['POST'])
def import_opendss():
    """
    Accepts an OpenDSS .dss text, builds a model, and returns
    a JSON structure compatible with insertComponentsForData.
    NOTE: this is a minimal implementation focused on buses and lines;
    you can extend it to cover more element types as needed. 
    """
    payload = request.get_json(force=True)
    dss_text = payload.get('content', '')

    if not dss_text:
        return jsonify({'error': 'Empty file content'}), 400

    try:
        import tempfile
        import opendssdirect as dss
        import json as _json
        import os
        import re

        # Inject TCR_PU and HVDC_PU spectrum definitions if referenced but not defined
        dss_text_to_use = dss_text
        needs_tcr = bool(re.search(r'spectrum\s*=\s*TCR_PU', dss_text, re.IGNORECASE))
        needs_hvdc = bool(re.search(r'spectrum\s*=\s*HVDC_PU', dss_text, re.IGNORECASE))
        has_tcr = bool(re.search(r'New\s+Spectrum\.TCR_PU\b', dss_text, re.IGNORECASE))
        has_hvdc = bool(re.search(r'New\s+Spectrum\.HVDC_PU\b', dss_text, re.IGNORECASE))
        if (needs_tcr and not has_tcr) or (needs_hvdc and not has_hvdc):
            inj = []
            if needs_tcr and not has_tcr:
                cmd = opendss_electrisim._spectrum_dss_from_csv('TCR_PU', opendss_electrisim.SPECTRUM_TCR_PU_CSV)
                if cmd:
                    inj.append('! Injected TCR_PU spectrum (IEEE benchmark)')
                    inj.append(cmd)
            if needs_hvdc and not has_hvdc:
                cmd = opendss_electrisim._spectrum_dss_from_csv('HVDC_PU', opendss_electrisim.SPECTRUM_HVDC_PU_CSV)
                if cmd:
                    inj.append('! Injected HVDC_PU spectrum (IEEE benchmark)')
                    inj.append(cmd)
            if inj:
                # Insert after first "Clear" so spectra exist before Loads
                inj_block = '\n'.join(inj) + '\n\n'
                if re.match(r'^\s*Clear\s*$', dss_text, re.MULTILINE | re.IGNORECASE):
                    dss_text_to_use = re.sub(r'^(\s*Clear\s*)$', r'\1\n\n' + inj_block, dss_text, count=1, flags=re.MULTILINE | re.IGNORECASE)
                else:
                    dss_text_to_use = inj_block + dss_text

        # Create temp file without auto-delete (Windows issue)
        fd, temp_path = tempfile.mkstemp(suffix='.dss', text=True)
        try:
            # Write the DSS content
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(dss_text_to_use)
            
            # Now load it in OpenDSS
            dss.Text.Command("Clear")
            dss.Text.Command(f"Redirect \"{temp_path}\"")

            # Assign per-bus kV bases (HV + LV) before reading bus nominal voltages
            vb_list = _infer_opendss_voltage_bases(dss, dss_text_to_use)
            if vb_list:
                dss.Text.Command('set voltagebases=[' + ','.join(str(v) for v in vb_list) + ']')
            dss.Text.Command('calcv')
            dss.Solution.Solve()

            # Build a complete model JSON with all OpenDSS elements
            import math
            bus_names = dss.Circuit.AllBusNames()
            equip_vn = _bus_voltages_from_equipment(dss, bus_names)
            buses = []
            for idx, bname in enumerate(bus_names):
                dss.Circuit.SetActiveBus(bname)
                kv_base = dss.Bus.kVBase()
                # OpenDSS kVBase is line-to-neutral; Electrisim vn_kv expects line-to-line (pandapower convention)
                vn_kv_ll = float(kv_base) * math.sqrt(3) if kv_base is not None else 0.0
                if bname in equip_vn:
                    vn_kv_ll = equip_vn[bname]
                buses.append([bname, vn_kv_ll, "b", True])

            # Lines
            line_names = dss.Lines.AllNames()
            lines = []
            if line_names:
                for lname in line_names:
                    dss.Lines.Name(lname)
                    bus1 = dss.Lines.Bus1()
                    bus2 = dss.Lines.Bus2()
                    length = dss.Lines.Length()
                    r1 = dss.Lines.R1()
                    x1 = dss.Lines.X1()
                    c1 = dss.Lines.C1()
                    # Map OpenDSS fields into something close to the pandapower "line" table layout
                    # [name, std_type, from_bus, to_bus, length_km, r_ohm_per_km, x_ohm_per_km, c_nf_per_km, g_us_per_km, max_i_ka, df, parallel, type, in_service]
                    try:
                        from_idx = bus_names.index(bus1.split('.')[0])
                        to_idx = bus_names.index(bus2.split('.')[0])
                    except ValueError:
                        # Skip lines whose buses are not found
                        continue
                    length_km = float(length)
                    r_ohm_per_km = float(r1)
                    x_ohm_per_km = float(x1)
                    c_nf_per_km = float(c1)
                    line_row = [
                        lname,           # name
                        "",              # std_type
                        from_idx,        # from_bus index
                        to_idx,          # to_bus index
                        length_km,
                        r_ohm_per_km,
                        x_ohm_per_km,
                        c_nf_per_km,
                        0.0,             # g_us_per_km
                        1.0,             # max_i_ka (placeholder)
                        1.0,             # df
                        1,               # parallel
                        "ol",            # type
                        True             # in_service
                    ]
                    lines.append(line_row)

            # Parse transformer connection/vector group from DSS text
            import re
            _trafo_vecgrp_cache = {}
            trafo_blocks = re.split(r'(?=New\s+Transformer\.)', dss_text, flags=re.IGNORECASE)
            for blk in trafo_blocks:
                m = re.match(r'New\s+Transformer\.(\w+)', blk, re.IGNORECASE)
                if not m:
                    continue
                tname = m.group(1)
                info = {}
                conns_m = re.search(r'conns\s*=\s*\[([^\]]+)\]', blk, re.IGNORECASE)
                if conns_m:
                    info['conns'] = [c.strip().lower() for c in conns_m.group(1).split(',')]
                ang1_m = re.search(r'ANG1[^\d]*(-?\d+(?:\.\d+)?)', blk, re.IGNORECASE)
                if ang1_m:
                    info['ang1'] = float(ang1_m.group(1))
                vecgrp_m = re.search(r'\(record\s+in\s+table\s+is\s+"([^"]+)"\)', blk, re.IGNORECASE)
                if vecgrp_m:
                    info['vecgrp'] = vecgrp_m.group(1).strip()
                leadlag_m = re.search(r'leadlag\s*=\s*(\w+)', blk, re.IGNORECASE)
                if leadlag_m:
                    info['leadlag'] = leadlag_m.group(1).strip().lower()
                if info:
                    _trafo_vecgrp_cache[tname] = info

            def _opendss_vecgrp_to_iec(tname):
                """Map OpenDSS conns/leadlag/ANG1 to IEC vector group."""
                info = _trafo_vecgrp_cache.get(tname, {})
                if info.get('vecgrp'):
                    return info['vecgrp']
                conns = info.get('conns', ['wye', 'wye'])
                ang1 = info.get('ang1', 0.0)
                leadlag = info.get('leadlag', 'lead')
                hv_conn = conns[0] if len(conns) > 0 else 'wye'
                lv_conn = conns[1] if len(conns) > 1 else 'wye'
                # Map to IEC vector groups
                if hv_conn == 'wye' and lv_conn == 'wye':
                    return 'YNyn0' if abs(ang1) < 1 else ('YNyn6' if ang1 > 0 else 'YNyn0')
                if hv_conn == 'wye' and lv_conn == 'delta':
                    if abs(ang1 + 30) < 1 or leadlag == 'lead':
                        return 'YNd1'
                    if abs(ang1 - 30) < 1 or leadlag == 'lag':
                        return 'YNd11'
                    return 'YNd1'
                if hv_conn == 'delta' and lv_conn == 'wye':
                    if abs(ang1 + 30) < 1 or leadlag == 'lead':
                        return 'Dyn11'
                    if abs(ang1 - 30) < 1 or leadlag == 'lag':
                        return 'Dyn1'
                    return 'Dyn11'
                if hv_conn == 'delta' and lv_conn == 'delta':
                    return 'Dd0' if abs(ang1) < 1 else 'Dd6'
                return 'Dyn11'

            # Transformers
            trafo_names = dss.Transformers.AllNames()
            trafos = []
            if trafo_names:
                for tname in trafo_names:
                    dss.Circuit.SetActiveElement(f"Transformer.{tname}")
                    num_windings = dss.Transformers.NumWindings()
                    if num_windings == 2:
                        # Get bus names using CktElement interface
                        bus_names_xfmr = dss.CktElement.BusNames()
                        if len(bus_names_xfmr) >= 2:
                            # Get transformer parameters
                            dss.Transformers.Wdg(1)
                            wdg1_kv = float(dss.Transformers.kV())
                            wdg1_bus = bus_names_xfmr[0].split('.')[0]
                            dss.Transformers.Wdg(2)
                            wdg2_kv = float(dss.Transformers.kV())
                            wdg2_bus = bus_names_xfmr[1].split('.')[0]
                            sn_mva = dss.Transformers.kVA() / 1000.0  # Convert to MVA

                            if wdg1_kv >= wdg2_kv:
                                hv_kv, lv_kv = wdg1_kv, wdg2_kv
                                hv_bus, lv_bus = wdg1_bus, wdg2_bus
                            else:
                                hv_kv, lv_kv = wdg2_kv, wdg1_kv
                                hv_bus, lv_bus = wdg2_bus, wdg1_bus

                            xhl = 6.0
                            vkr = 1.0
                            pfe_kw = 0.0
                            i0_pct = 0.0
                            try:
                                dss.Circuit.SetActiveClass('Transformer')
                                dss.ActiveClass.Name(tname)
                                xhl = float(dss.Properties.Value('XHL'))
                                rs_raw = dss.Properties.Value('%Rs')
                                if isinstance(rs_raw, (list, tuple)):
                                    vkr = sum(float(x) for x in rs_raw if x not in (None, ''))
                                else:
                                    import ast
                                    parsed = ast.literal_eval(str(rs_raw).strip())
                                    if isinstance(parsed, (list, tuple)):
                                        vkr = sum(float(x) for x in parsed)
                                    else:
                                        vkr = float(parsed)
                                nll = dss.Properties.Value('%noloadloss')
                                imag = dss.Properties.Value('%imag')
                                if nll not in (None, ''):
                                    pfe_kw = float(nll) * sn_mva * 10.0  # % of kVA -> kW
                                if imag not in (None, ''):
                                    i0_pct = float(imag)
                            except (TypeError, ValueError, SyntaxError):
                                pass
                            vk_percent = math.sqrt(xhl ** 2 + vkr ** 2)
                            
                            try:
                                hv_idx = bus_names.index(hv_bus)
                                lv_idx = bus_names.index(lv_bus)
                            except ValueError:
                                continue
                            
                            vector_group = _opendss_vecgrp_to_iec(tname)
                            
                            # [name, std_type, hv_bus, lv_bus, sn_mva, vn_hv_kv, vn_lv_kv, vk_percent, vkr_percent, pfe_kw, i0_percent, shift_degree, ..., vector_group]
                            trafo_row = [
                                tname, "", hv_idx, lv_idx, sn_mva, hv_kv, lv_kv,
                                vk_percent, vkr, pfe_kw, i0_pct, 0.0,
                                None, 0, 0, 0, 0.0, 0.0, 0, False, 1, 1.0, True,
                                vector_group
                            ]
                            trafos.append(trafo_row)

            # Parse spectrum definitions from DSS text for custom spectra
            import re
            _SPECTRUM_TEMPLATES = {'defaultload', 'defaultgen', 'defaultvsource', 'linear', 'none'}
            _spectrum_cache = {}
            for spec_match in re.finditer(
                r'New\s+Spectrum\.(\w+).*?harmonic=\s*\(([^)]+)\).*?%mag=\s*\(([^)]+)\).*?angle=\s*\(([^)]+)\)',
                dss_text, re.IGNORECASE | re.DOTALL
            ):
                spec_name, harm_s, mag_s, ang_s = spec_match.groups()
                try:
                    harms = [int(x.strip()) for x in harm_s.split()]
                    mags = [float(x.strip()) for x in mag_s.split()]
                    angs = [float(x.strip()) for x in ang_s.split()]
                    csv_lines = [f'{h},{m},{a}' for h, m, a in zip(harms, mags, angs)]
                    _spectrum_cache[spec_name.lower()] = '\n'.join(csv_lines)
                except (ValueError, TypeError):
                    pass

            # Loads
            load_names = dss.Loads.AllNames()
            loads = []
            if load_names:
                for lname in load_names:
                    dss.Circuit.SetActiveElement(f"Load.{lname}")
                    bus_names_load = dss.CktElement.BusNames()
                    if bus_names_load:
                        bus = bus_names_load[0].split('.')[0]
                        dss.Loads.Name(lname)
                        kw = dss.Loads.kW()
                        kvar = dss.Loads.kvar()
                        
                        try:
                            bus_idx = bus_names.index(bus)
                        except ValueError:
                            continue
                        
                        # Harmonic parameters
                        try:
                            spec_name = (dss.Loads.Spectrum() or 'defaultload').strip() or 'defaultload'
                        except (TypeError, AttributeError):
                            spec_name = 'defaultload'
                        spec_lower = spec_name.lower()
                        pct_series_rl = 100.0
                        try:
                            pct_series_rl = float(dss.Loads.puSeriesRL())
                        except (TypeError, AttributeError):
                            pass
                        pu_xharm = 0.0
                        xr_harm = 6.0
                        try:
                            dss.Circuit.SetActiveClass('Load')
                            dss.ActiveClass.Name(lname)
                            pv = dss.Properties.Value('puXharm')
                            if pv:
                                pu_xharm = float(pv)
                            xv = dss.Properties.Value('XRharm')
                            if xv:
                                xr_harm = float(xv)
                        except (TypeError, AttributeError, ValueError):
                            pass
                        conn_load = 'wye'
                        try:
                            dss.Circuit.SetActiveClass('Load')
                            dss.ActiveClass.Name(lname)
                            cv = dss.Properties.Value('conn')
                            if cv:
                                conn_load = str(cv).strip().lower()
                        except (TypeError, AttributeError):
                            pass
                        
                        if spec_lower in _SPECTRUM_TEMPLATES:
                            spectrum = 'Linear' if spec_lower == 'linear' else spec_lower
                            spectrum_csv = ''
                        elif spec_lower in ('tcr_pu', 'hvdc_pu'):
                            spectrum = spec_name  # preserve TCR_PU or HVDC_PU
                            spectrum_csv = ''
                        else:
                            spectrum = 'custom'
                            spectrum_csv = _spectrum_cache.get(spec_lower, '')
                        
                        # [name, bus, p_mw, q_mvar, const_z, const_i, sn_mva, scaling, type, spectrum, spectrum_csv, pctSeriesRL, puXharm, XRharm, conn]
                        load_row = [
                            lname, bus_idx, kw/1000.0, kvar/1000.0, 0.0, 0.0, None, 1.0, "wye",
                            spectrum, spectrum_csv, pct_series_rl, pu_xharm, xr_harm, conn_load
                        ]
                        loads.append(load_row)

            # Generators (Vsources in OpenDSS)
            vsource_names = dss.Vsources.AllNames()
            generators = []
            ext_grids = []
            if vsource_names:
                for idx, vname in enumerate(vsource_names):
                    dss.Circuit.SetActiveElement(f"Vsource.{vname}")
                    bus_names_vsrc = dss.CktElement.BusNames()
                    if bus_names_vsrc:
                        bus = bus_names_vsrc[0].split('.')[0]
                        try:
                            bus_idx = bus_names.index(bus)
                        except ValueError:
                            continue
                        dss.Vsources.Name(vname)
                        basekv = dss.Vsources.BasekV()
                        pu = dss.Vsources.PU()
                        angle = dss.Vsources.AngleDeg()
                        bus_vn_ll = float(buses[bus_idx][1]) if bus_idx < len(buses) else float(basekv) * math.sqrt(3)
                        s_sc_max = 1000000.0
                        s_sc_min = 0.0
                        rx_max = 0.0
                        rx_min = 0.0
                        r0x0_max = 0.0
                        x0x_max = 0.0
                        try:
                            dss.Circuit.SetActiveClass('Vsource')
                            dss.ActiveClass.Name(vname)
                            r1 = float(dss.Properties.Value('R1') or 0)
                            x1 = float(dss.Properties.Value('X1') or 0)
                            r0 = float(dss.Properties.Value('R0') or 0)
                            x0 = float(dss.Properties.Value('X0') or 0)
                            if abs(r1) > 1e-9 or abs(x1) > 1e-9:
                                z1 = math.hypot(r1, x1)
                                if z1 > 0 and bus_vn_ll > 0:
                                    s_sc_max = (bus_vn_ll ** 2) / z1
                                    rx_max = r1 / x1 if abs(x1) > 1e-9 else 0.0
                                if abs(r0) > 1e-9 or abs(x0) > 1e-9:
                                    z0 = math.hypot(r0, x0)
                                    if z0 > 0 and bus_vn_ll > 0:
                                        s_sc_min = (bus_vn_ll ** 2) / z0
                                        r0x0_max = r0 / x0 if abs(x0) > 1e-9 else 0.0
                            else:
                                try:
                                    mvasc3 = float(dss.Vsources.MVAsc3())
                                    if mvasc3 > 0.1:
                                        s_sc_max = mvasc3
                                except (TypeError, ValueError, AttributeError):
                                    pass
                        except (TypeError, ValueError, AttributeError):
                            pass
                        
                        # First Vsource is typically the external grid (slack bus)
                        if idx == 0:
                            ext_grid_row = [
                                vname, bus_idx, pu, angle, 1.0, True,
                                s_sc_max, s_sc_min, rx_max, rx_min, r0x0_max, x0x_max,
                            ]
                            ext_grids.append(ext_grid_row)
                        else:
                            # Other Vsources as generators
                            # [name, bus, p_mw, vm_pu, sn_mva, min_q_mvar, max_q_mvar, scaling, slack, in_service, slack_weight, type]
                            gen_row = [vname, bus_idx, 0.0, pu, 100.0, -50.0, 50.0, 1.0, False, True, 0.0, ""]
                            generators.append(gen_row)

            # Reactors (inductors) - these connect buses and are used in filters
            reactor_names = dss.Reactors.AllNames()
            impedances = []
            # Read base MVA from OpenDSS circuit for per-unit conversion
            base_mva = 100.0
            try:
                if hasattr(dss.Circuit, 'BaseMVA'):
                    base_mva = float(dss.Circuit.BaseMVA())
                else:
                    # Fallback: parse from DSS text (e.g. baseMVA=100.0 in Circuit or Vsource)
                    m = re.search(r'baseMVA\s*=\s*([\d.]+)', dss_text, re.IGNORECASE)
                    if m:
                        base_mva = float(m.group(1))
            except (TypeError, ValueError, AttributeError):
                pass
            if base_mva <= 0:
                base_mva = 100.0
            if reactor_names:
                print(f"Found {len(reactor_names)} reactors in OpenDSS model (baseMVA={base_mva})")
                for rname in reactor_names:
                    dss.Circuit.SetActiveElement(f"Reactor.{rname}")
                    bus_names_reactor = dss.CktElement.BusNames()
                    print(f"Reactor {rname}: buses = {bus_names_reactor}")
                    if len(bus_names_reactor) >= 2:
                        from_bus = bus_names_reactor[0].split('.')[0]
                        to_bus = bus_names_reactor[1].split('.')[0]
                        
                        dss.Reactors.Name(rname)
                        r_ohm = dss.Reactors.R()
                        x_ohm = dss.Reactors.X()
                        
                        try:
                            from_idx = bus_names.index(from_bus)
                            to_idx = bus_names.index(to_bus)
                            print(f"  Reactor {rname}: {from_bus}({from_idx}) -> {to_bus}({to_idx}), R={r_ohm}, X={x_ohm}")
                        except ValueError as ve:
                            print(f"  WARNING: Skipping reactor {rname}, bus not found: {ve}")
                            continue
                        
                        # Convert R and X from Ohms to per-unit
                        # Z_base = V_base^2 / S_base (V_base in kV, S_base in MVA)
                        vn_kv = float(buses[from_idx][1]) if buses[from_idx][1] else 1.0
                        z_base = (vn_kv ** 2) / base_mva if vn_kv > 0 else 1.0
                        r_pu = float(r_ohm) / z_base
                        x_pu = float(x_ohm) / z_base
                        
                        # [name, from_bus, to_bus, rft_pu, xft_pu, rtf_pu, xtf_pu, sn_mva, in_service]
                        impedance_row = [rname, from_idx, to_idx, r_pu, x_pu, r_pu, x_pu, base_mva, True]
                        impedances.append(impedance_row)
                
                print(f"Total impedances extracted: {len(impedances)}")

            # Capacitors
            cap_names = dss.Capacitors.AllNames()
            shunts = []
            if cap_names:
                for cname in cap_names:
                    dss.Circuit.SetActiveElement(f"Capacitor.{cname}")
                    bus_names_cap = dss.CktElement.BusNames()
                    if bus_names_cap:
                        bus = bus_names_cap[0].split('.')[0]
                        dss.Capacitors.Name(cname)
                        kvar_val = dss.Capacitors.kvar()
                        
                        try:
                            bus_idx = bus_names.index(bus)
                        except ValueError:
                            continue
                        
                        # [bus, name, q_mvar, p_mw, vn_kv, step, max_step, in_service]
                        shunt_row = [bus_idx, cname, kvar_val/1000.0, 0.0, 1.0, 1, 1, True]
                        shunts.append(shunt_row)

            # PVSystems (OpenDSS-only; mapped to Electrisim PVSystem cells on import)
            pvsystems = []
            pv_names = dss.PVsystems.AllNames()
            if pv_names:
                def _pv_float(pvname, prop, default=0.0):
                    try:
                        dss.Circuit.SetActiveClass('PVSystem')
                        dss.ActiveClass.Name(pvname)
                        raw = dss.Properties.Value(prop)
                        if raw in (None, ''):
                            return default
                        return float(raw)
                    except (TypeError, ValueError, AttributeError):
                        return default

                for pvname in pv_names:
                    dss.Circuit.SetActiveElement(f"PVSystem.{pvname}")
                    bus_names_pv = dss.CktElement.BusNames()
                    if not bus_names_pv:
                        continue
                    bus = bus_names_pv[0].split('.')[0]
                    try:
                        bus_idx = bus_names.index(bus)
                    except ValueError:
                        continue
                    pmpp = _pv_float(pvname, 'pmpp', 0.0)
                    kva = _pv_float(pvname, 'kVA', pmpp if pmpp else 0.0)
                    cutin_pct = _pv_float(pvname, '%Cutin', 10.0)
                    cutout_pct = _pv_float(pvname, '%Cutout', 10.0)
                    # Electrisim stores cut-in/out as per-unit (0.1); OpenDSS uses percent (10)
                    pvsystems.append([
                        pvname,
                        bus_idx,
                        _pv_float(pvname, 'irradiance', 1.0),
                        pmpp,
                        _pv_float(pvname, 'temperature', 25.0),
                        int(_pv_float(pvname, 'phases', 3)),
                        _pv_float(pvname, 'kV', 0.4),
                        _pv_float(pvname, 'pf', 1.0),
                        _pv_float(pvname, 'kvar', 0.0),
                        kva,
                        cutin_pct / 100.0,
                        cutout_pct / 100.0,
                        True,
                    ])

            # Compose structure similar to example_simple.json
            model = {
                "_object": {
                    "bus": {
                        "_object": _json.dumps({
                            "data": buses
                        })
                    },
                    "line": {
                        "_object": _json.dumps({
                            "data": lines
                        })
                    },
                    "ext_grid": {
                        "_object": _json.dumps({
                            "data": ext_grids
                        })
                    },
                    "gen": {
                        "_object": _json.dumps({
                            "data": generators
                        })
                    },
                    "trafo": {
                        "_object": _json.dumps({
                            "data": trafos
                        })
                    },
                    "load": {
                        "_object": _json.dumps({
                            "data": loads
                        })
                    },
                    "shunt": {
                        "_object": _json.dumps({
                            "data": shunts
                        })
                    },
                    "impedance": {
                        "_object": _json.dumps({
                            "data": impedances
                        })
                    },
                    "pvsystems": {
                        "_object": _json.dumps({
                            "data": pvsystems
                        })
                    },
                    # Empty tables for elements not yet extracted
                    "sgen": {"_object": _json.dumps({"data": []})},
                    "asymmetric_sgen": {"_object": _json.dumps({"data": []})},
                    "trafo3w": {"_object": _json.dumps({"data": []})},
                    "asymmetric_load": {"_object": _json.dumps({"data": []})},
                    "ward": {"_object": _json.dumps({"data": []})},
                    "xward": {"_object": _json.dumps({"data": []})},
                    "motor": {"_object": _json.dumps({"data": []})},
                    "storage": {"_object": _json.dumps({"data": []})},
                    "svc": {"_object": _json.dumps({"data": []})},
                    "tcsc": {"_object": _json.dumps({"data": []})},
                    "dcline": {"_object": _json.dumps({"data": []})}
                }
            }

            return _json.dumps(model)
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except:
                pass
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in import_opendss: {error_details}")
        return jsonify({'error': str(e), 'details': error_details}), 400

#DLA PRODUKCJI USUWAJ PONIŻSZE WERSJE        
if __name__ == '__main__':
    # Get port from environment variable (Railway sets this automatically)
    port = int(os.getenv('PORT', 5000))
    
    # Check if running in production
    is_production = os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('FLASK_ENV') == 'production'
    
    if is_production:
        # Production mode
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        # Development mode - disable reloader to prevent MemoryError with numba/pandapower
        app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)