#!/usr/bin/env python3
"""
Test script to verify OpenDSS integration fixes
"""

import opendss_electrisim

# Test data similar to what was provided by the user
test_data = {
    '0': {'typ': 'PowerFlowOpenDss Parameters', 'frequency': '50', 'algorithm': 'Admittance', 'maxIterations': '100', 'tolerance': '1e-6', 'convergence': 'normal', 'voltageControl': 'off', 'tapControl': 'off', 'user_email': 'maciej@gmail.com'},
    '1': {'typ': 'Line', 'name': 'cell_eGnM8k9L8ruUL_v1ilzH-52', 'id': 'eGnM8k9L8ruUL_v1ilzH-52', 'busFrom': 'ApmFBaVE9PY9BRSX476v-16', 'busTo': 'iL9u3X7EebuMCR8bb91E-2'},
    '2': {'typ': 'Line', 'name': 'cell_eGnM8k9L8ruUL_v1ilzH-51', 'id': 'cell_eGnM8k9L8ruUL_v1ilzH-51', 'busFrom': 'ApmFBaVE9PY9BRSX476v-16', 'busTo': 'ApmFBaVE9PY9BRSX476v-28'},
    '3': {'typ': 'Line', 'name': 'cell_eGnM8k9L8ruUL_v1ilzH-50', 'id': 'cell_eGnM8k9L8ruUL_v1ilzH-50', 'busFrom': 'ApmFBaVE9PY9BRSX476v-12', 'busTo': 'ApmFBaVE9PY9BRSX476v-14'},
    '4': {'typ': 'External Grid', 'name': 'cell_ApmFBaVE9PY9BRSX476v-11', 'id': 'ApmFBaVE9PY9BRSX476v-11'},
    '5': {'typ': 'External Grid', 'name': 'cell_eGnM8k9L8ruUL_v1ilzH-53', 'id': 'cell_eGnM8k9L8ruUL_v1ilzH-53', 'p_mw': -6.742, 'q_mvar': -7.147},
    '6': {'typ': 'Bus-1 110kV', 'name': 'cell_ApmFBaVE9PY9BRSX476v-13', 'id': 'cell_ApmFBaVE9PY9BRSX476v-13', 'vn_kv': 110},
    '7': {'typ': 'Bus', 'name': 'cell_eGnM8k9L8ruUL_v1ilzH-45', 'id': 'cell_eGnM8k9L8ruUL_v1ilzH-45', 'vn_kv': 110, 'p_mw': 6.742, 'q_mvar': 7.147},
    '8': {'typ': 'Bus-2 110kV', 'name': 'cell_ApmFBaVE9PY9BRSX476v-15', 'id': 'cell_ApmFBaVE9PY9BRSX476v-15', 'vn_kv': 110},
    '9': {'typ': 'Bus', 'name': 'cell_eGnM8k9L8ruUL_v1ilzH-46', 'id': 'cell_eGnM8k9L8ruUL_v1ilzH-46', 'vn_kv': 110, 'p_mw': 0, 'q_mvar': -1},
    '10': {'typ': 'Bus-1 20kV', 'name': 'cell_eGnM8k9L8ruUL_v1ilzH-17', 'id': 'cell_eGnM8k9L8ruUL_v1ilzH-17', 'vn_kv': 20},
    '11': {'typ': 'Bus', 'name': 'cell_eGnM8k9L8ruUL_v1ilzH-47', 'id': 'cell_eGnM8k9L8ruUL_v1ilzH-47', 'vn_kv': 110, 'p_mw': 0, 'q_mvar': 0},
    '12': {'typ': 'Transformer', 'name': 'cell_eGnM8k9L8ruUL_v1ilzH-56', 'id': 'cell_eGnM8k9L8ruUL_v1ilzH-56'},
    '13': {'typ': 'Bus-2', 'name': 'cell_eGnM8k9L8ruUL_v1ilzH-29', 'id': 'cell_eGnM8k9L8ruUL_v1ilzH-29', 'vn_kv': 110},
    '14': {'typ': 'Bus', 'name': 'cell_eGnM8k9L8ruUL_v1ilzH-48', 'id': 'cell_eGnM8k9L8ruUL_v1ilzH-48', 'vn_kv': 110, 'p_mw': -0.799, 'q_mvar': 2.902},
    '15': {'typ': 'Bus-3', 'name': 'cell_iL9u3X7EebuMCR8bb91E-3', 'id': 'cell_iL9u3X7EebuMCR8bb91E-3', 'vn_kv': 110},
    '16': {'typ': 'Bus', 'name': 'cell_eGnM8k9L8ruUL_v1ilzH-49', 'id': 'cell_eGnM8k9L8ruUL_v1ilzH-49', 'vn_kv': 110, 'p_mw': -6, 'q_mvar': -3.428},
    '17': {'typ': 'Generator', 'name': 'cell_iL9u3X7EebuMCR8bb91E-5', 'id': 'cell_iL9u3X7EebuMCR8bb91E-5', 'bus': 'ApmFBaVE9PY9BRSX476v-28'},
    '18': {'typ': 'Generator', 'name': 'cell_eGnM8k9L8ruUL_v1ilzH-54', 'id': 'cell_eGnM8k9L8ruUL_v1ilzH-54', 'p_mw': 6, 'q_mvar': 3.428, 'vm_pu': 1.03, 'bus': 'ApmFBaVE9PY9BRSX476v-28'},
    '19': {'typ': 'Load', 'name': 'Static Generator', 'id': 'iL9u3X7EebuMCR8bb91E-10', 'p_mw': 2, 'q_mvar': -0.5, 'vn_kv': 110, 'type': 'Wye', 'bus': 'ApmFBaVE9PY9BRSX476v-28'},
    '20': {'typ': 'Static Generator', 'name': 'cell_iL9u3X7EebuMCR8bb91E-11', 'id': 'cell_iL9u3X7EebuMCR8bb91E-11', 'bus': 'ApmFBaVE9PY9BRSX476v-28'},
    '21': {'typ': 'Static Generator', 'name': 'cell_eGnM8k9L8ruUL_v1ilzH-55', 'id': 'cell_eGnM8k9L8ruUL_v1ilzH-55', 'bus': 'ApmFBaVE9PY9BRSX476v-28'},
    '22': {'typ': 'Load', 'name': 'Load', 'id': 'iL9u3X7EebuMCR8bb91E-13', 'p_mw': 0.5, 'q_mvar': 0.2, 'vn_kv': 110, 'type': 'Wye', 'bus': 'ApmFBaVE9PY9BRSX476v-28'},
    '23': {'typ': 'Shunt Reactor', 'name': 'cell_eGnM8k9L8ruUL_v1ilzH-57', 'id': 'cell_eGnM8k9L8ruUL_v1ilzH-57', 'bus': 'ApmFBaVE9PY9BRSX476v-28', 'vn_kv': 110, 'q_mvar': 1},
    '24': {'typ': 'Capacitor', 'name': 'cell_eGnM8k9L8ruUL_v1ilzH-58', 'id': 'cell_eGnM8k9L8ruUL_v1ilzH-58', 'bus': 'ApmFBaVE9PY9BRSX476v-28', 'vn_kv': 110, 'q_mvar': 0.5}
}

print("Testing OpenDSS integration with improved error handling...")
print("=" * 60)

try:
    # Call the powerflow function with required parameters
    result = opendss_electrisim.powerflow(
        test_data, 
        frequency=50,
        algorithm='Admittance',
        max_iterations=100,
        tolerance=1e-6,
        convergence='normal',
        voltage_control=True,
        tap_control=True
    )
    
    if isinstance(result, dict) and "error" in result:
        print(f"❌ Power flow failed: {result['error']}")
    else:
        print("✅ Power flow completed successfully!")
        print(f"Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
        
except Exception as e:
    print(f"❌ Exception occurred: {e}")
    print(f"Exception type: {type(e)}")
    import traceback
    traceback.print_exc()

print("=" * 60)
print("Test completed.")
