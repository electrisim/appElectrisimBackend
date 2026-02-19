# -*- coding: utf-8 -*-
import pandapower_electrisim
import opendss_electrisim
import os
import json

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
                run_control = in_data[x].get('run_control', False)  # Include controllers (DiscreteTapControl, etc.)

                net = pp.create_empty_network(f_hz=frequency)
           
                Busbars = pandapower_electrisim.create_busbars(in_data, net)
                pandapower_electrisim.create_other_elements(in_data, net, x, Busbars)   

                response_data = pandapower_electrisim.powerflow(net, algorithm, calculate_voltage_angles, init, export_python, in_data, Busbars, run_control=run_control)  

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
    """
    import json
    import numpy as np
    
    def dataframe_to_list(df):
        """Convert a pandapower DataFrame to a list of lists for the frontend"""
        if df.empty:
            return []
        # Replace NaN, NA, and other non-serializable values with None
        return df.replace({np.nan: None, pd.NA: None}).values.tolist()
    
    # Build the structure matching example_simple.json format
    model = {
        "_object": {
            "bus": {
                "_object": json.dumps({
                    "data": dataframe_to_list(net.bus)
                })
            },
            "line": {
                "_object": json.dumps({
                    "data": dataframe_to_list(net.line) if hasattr(net, 'line') and not net.line.empty else []
                })
            },
            "ext_grid": {
                "_object": json.dumps({
                    "data": dataframe_to_list(net.ext_grid) if hasattr(net, 'ext_grid') and not net.ext_grid.empty else []
                })
            },
            "gen": {
                "_object": json.dumps({
                    "data": dataframe_to_list(net.gen) if hasattr(net, 'gen') and not net.gen.empty else []
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
                    "data": dataframe_to_list(net.trafo) if hasattr(net, 'trafo') and not net.trafo.empty else []
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
                    "data": dataframe_to_list(net.load) if hasattr(net, 'load') and not net.load.empty else []
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
        finally:
            # Restore stdout
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

        # Create temp file without auto-delete (Windows issue)
        fd, temp_path = tempfile.mkstemp(suffix='.dss', text=True)
        try:
            # Write the DSS content
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(dss_text)
            
            # Now load it in OpenDSS
            dss.Text.Command("Clear")
            dss.Text.Command(f"Redirect \"{temp_path}\"")

            # Solve once to ensure circuit is initialized
            dss.Solution.Solve()

            # Build a complete model JSON with all OpenDSS elements
            bus_names = dss.Circuit.AllBusNames()
            buses = []
            for idx, bname in enumerate(bus_names):
                dss.Circuit.SetActiveBus(bname)
                kv_base = dss.Bus.kVBase()
                # Name and vn_kv follow the pandapower schema used on frontend
                buses.append([bname, float(kv_base) if kv_base is not None else 0.0, "b", True])

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
                            hv_bus = bus_names_xfmr[0].split('.')[0]
                            lv_bus = bus_names_xfmr[1].split('.')[0]
                            
                            # Get transformer parameters
                            dss.Transformers.Wdg(1)
                            hv_kv = dss.Transformers.kV()
                            dss.Transformers.Wdg(2)
                            lv_kv = dss.Transformers.kV()
                            sn_mva = dss.Transformers.kVA() / 1000.0  # Convert to MVA
                            
                            try:
                                hv_idx = bus_names.index(hv_bus)
                                lv_idx = bus_names.index(lv_bus)
                            except ValueError:
                                continue
                            
                            # [name, std_type, hv_bus, lv_bus, sn_mva, vn_hv_kv, vn_lv_kv, vk_percent, vkr_percent, pfe_kw, i0_percent, shift_degree, ...]
                            trafo_row = [
                                tname, "", hv_idx, lv_idx, sn_mva, hv_kv, lv_kv,
                                6.0, 1.0, 0.0, 0.0, 0.0,  # Default impedance values
                                None, 0, 0, 0, 0.0, 0.0, 0, False, 1, 1.0, True
                            ]
                            trafos.append(trafo_row)

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
                        
                        # [name, bus, p_mw, q_mvar, const_z_percent, const_i_percent, sn_mva, scaling, type]
                        load_row = [lname, bus_idx, kw/1000.0, kvar/1000.0, 0.0, 0.0, None, 1.0, "wye"]
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
                        dss.Vsources.Name(vname)
                        basekv = dss.Vsources.BasekV()
                        pu = dss.Vsources.PU()
                        angle = dss.Vsources.AngleDeg()
                        
                        try:
                            bus_idx = bus_names.index(bus)
                        except ValueError:
                            continue
                        
                        # First Vsource is typically the external grid (slack bus)
                        if idx == 0:
                            # [name, bus, vm_pu, va_degree, slack_weight, in_service]
                            ext_grid_row = [vname, bus_idx, pu, angle, 1.0, True]
                            ext_grids.append(ext_grid_row)
                        else:
                            # Other Vsources as generators
                            # [name, bus, p_mw, vm_pu, sn_mva, min_q_mvar, max_q_mvar, scaling, slack, in_service, slack_weight, type]
                            gen_row = [vname, bus_idx, 0.0, pu, 100.0, -50.0, 50.0, 1.0, False, True, 0.0, ""]
                            generators.append(gen_row)

            # Reactors (inductors) - these connect buses and are used in filters
            reactor_names = dss.Reactors.AllNames()
            impedances = []
            if reactor_names:
                print(f"Found {len(reactor_names)} reactors in OpenDSS model")
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
                        
                        # Convert to impedance format for pandapower
                        # [name, from_bus, to_bus, rft_pu, xft_pu, rtf_pu, xtf_pu, sn_mva, in_service]
                        # For now use ohm values directly (frontend can handle it)
                        impedance_row = [rname, from_idx, to_idx, r_ohm, x_ohm, r_ohm, x_ohm, 100.0, True]
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