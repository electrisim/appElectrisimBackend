# -*- coding: utf-8 -*-
import pandapower_electrisim
import opendss_electrisim
import os

from flask import Flask, request, jsonify, make_response
from flask_cors import CORS, cross_origin #żeby działało trzeba wywołać polecenie pip install -U flask-cors==3.0.10 
import pandapower as pp
import pandas as pd
import gzip
import io

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
    #in_data = request.get_json()
    in_data = request.get_json(force=True) #force – if set to True the mimetype is ignored.
    print(in_data) 
   
    Busbars = {}
          
    #utworzenie sieci - w pierwszej petli sczytujemy parametry symulacji i tworzymy szyny
    for x in in_data:    
        #print(x)
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
                'cost_function': in_data[x]['cost_function']
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

            net = pp.create_empty_network(f_hz=frequency)
       
            Busbars = pandapower_electrisim.create_busbars(in_data, net)
            pandapower_electrisim.create_other_elements(in_data, net, x, Busbars)   

            response_data = pandapower_electrisim.powerflow(net, algorithm, calculate_voltage_angles, init, export_python, in_data, Busbars)  

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

        
        
        if "ShortCircuitPandaPower" in in_data[x]['typ']:
            # Extract user email for logging
            user_email = in_data[x].get('user_email', 'unknown@user.com')

            net = pp.create_empty_network()
            Busbars = pandapower_electrisim.create_busbars(in_data, net)
            pandapower_electrisim.create_other_elements(in_data, net, x, Busbars)
            response_data = pandapower_electrisim.shortcircuit(net, in_data[x])
            
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
           
        if "PowerFlowOpenDss" in in_data[x]['typ']:
            # Extract user email for logging
            user_email = in_data[x].get('user_email', 'unknown@user.com')
            
            # Extract OpenDSS parameters based on OpenDSS documentation
            # Reference: https://opendss.epri.com/PowerFlow.html
            frequency = eval(in_data[x]['frequency'])  # Base frequency (50 or 60 Hz)
            mode = in_data[x].get('mode', 'Snapshot')  # Solution mode (Snapshot, Daily, Dutycycle, Yearly)
            algorithm = in_data[x].get('algorithm', 'Normal')  # Solution algorithm (Normal, Newton)
            loadmodel = in_data[x].get('loadmodel', 'Powerflow')  # Load model (Powerflow, Admittance)
            max_iterations = int(in_data[x].get('maxIterations', 100))  # Maximum iterations
            tolerance = float(in_data[x].get('tolerance', 0.0001))  # Convergence tolerance
            controlmode = in_data[x].get('controlmode', 'Static')  # Control mode (Static, Event, Time)
            export_commands = in_data[x].get('exportCommands', False)  # Export OpenDSS commands flag
            
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
                'contingency_type': in_data[x]['contingency_type'],
                'element_type': in_data[x]['element_type'],
                'elements_to_analyze': in_data[x]['elements_to_analyze'],
                'voltage_limits': in_data[x]['voltage_limits'],
                'thermal_limits': in_data[x]['thermal_limits'],
                'min_vm_pu': in_data[x]['min_vm_pu'],
                'max_vm_pu': in_data[x]['max_vm_pu'],
                'max_loading_percent': in_data[x].get('max_loading_percent', '100'),
                'post_contingency_actions': in_data[x].get('post_contingency_actions', 'none'),
                'analysis_mode': in_data[x].get('analysis_mode', 'fast')
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
                'frequency': eval(in_data[x].get('frequency', '50')),
                'algorithm': in_data[x].get('algorithm', 'nr'),
                'calculate_voltage_angles': in_data[x].get('calculate_voltage_angles', 'auto'),
                'init': in_data[x].get('init', 'dc')
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