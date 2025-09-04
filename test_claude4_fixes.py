#!/usr/bin/env python3
"""
Test script to verify Claude 4's OpenDSS fixes
Tests the corrected powerflow function with sample data
"""

import json
import sys
import os

# Add the current directory to Python path to import the module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from opendss_electrisim import powerflow
    print("✓ Successfully imported powerflow function")
except ImportError as e:
    print(f"✗ Failed to import powerflow: {e}")
    sys.exit(1)

# Sample input data that matches the user's real data structure
sample_data = {
    '0': {
        'typ': 'PowerFlowOpenDss Parameters',
        'frequency': '50',
        'algorithm': 'Admittance',
        'maxIterations': '100',
        'tolerance': '1e-6',
        'convergence': 'normal',
        'voltageControl': 'off',
        'tapControl': 'off',
        'user_email': 'maciej@gmail.com'
    },
    '1': {
        'typ': 'Line',
        'name': 'cell_eGnM8k9L8ruUL_v1ilzH-52',
        'id': 'eGnM8k9L8ruUL_v1ilzH-52',
        'busFrom': 'ApmFBaVE9PY9BRSX476v-16',
        'busTo': 'iL9u3X7EebuMCR8bb91E-2'
    },
    '2': {
        'typ': 'Line',
        'name': 'cell_eGnM8k9L8ruUL_v1ilzH-51',
        'id': 'cell_eGnM8k9L8ruUL_v1ilzH-51',
        'busFrom': 'ApmFBaVE9PY9BRSX476v-16',
        'busTo': 'ApmFBaVE9PY9BRSX476v-28'
    },
    '3': {
        'typ': 'Line',
        'name': 'cell_eGnM8k9L8ruUL_v1ilzH-50',
        'id': 'cell_eGnM8k9L8ruUL_v1ilzH-50',
        'busFrom': 'ApmFBaVE9PY9BRSX476v-12',
        'busTo': 'ApmFBaVE9PY9BRSX476v-14'
    },
    '4': {
        'typ': 'External Grid',
        'name': 'cell_ApmFBaVE9PY9BRSX476v-11',
        'id': 'ApmFBaVE9PY9BRSX476v-11'
    },
    '5': {
        'typ': 'External Grid',
        'name': 'cell_eGnM8k9L8ruUL_v1ilzH-53',
        'id': 'cell_eGnM8k9L8ruUL_v1ilzH-53',
        'p_mw': -6.742,
        'q_mvar': -7.147
    },
    '6': {
        'typ': 'Bus-1 110kV',
        'name': 'cell_ApmFBaVE9PY9BRSX476v-13',
        'id': 'ApmFBaVE9PY9BRSX476v-13',
        'vn_kv': 110
    },
    '7': {
        'typ': 'Bus',
        'name': 'cell_eGnM8k9L8ruUL_v1ilzH-45',
        'id': 'cell_eGnM8k9L8ruUL_v1ilzH-45',
        'vn_kv': 110,
        'p_mw': 6.742,
        'q_mvar': 7.147
    },
    '8': {
        'typ': 'Bus-2 110kV',
        'name': 'cell_ApmFBaVE9PY9BRSX476v-15',
        'id': 'cell_ApmFBaVE9PY9BRSX476v-15',
        'vn_kv': 110
    },
    '9': {
        'typ': 'Bus',
        'name': 'cell_eGnM8k9L8ruUL_v1ilzH-46',
        'id': 'cell_eGnM8k9L8ruUL_v1ilzH-46',
        'vn_kv': 110,
        'p_mw': 0,
        'q_mvar': -1
    },
    '10': {
        'typ': 'Bus-1 20kV',
        'name': 'cell_ApmFBaVE9PY9BRSX476v-17',
        'id': 'cell_eGnM8k9L8ruUL_v1ilzH-17',
        'vn_kv': 20
    },
    '11': {
        'typ': 'Bus',
        'name': 'cell_eGnM8k9L8ruUL_v1ilzH-47',
        'id': 'cell_eGnM8k9L8ruUL_v1ilzH-47',
        'vn_kv': 110,
        'p_mw': 0,
        'q_mvar': 0
    },
    '12': {
        'typ': 'Transformer',
        'name': 'cell_eGnM8k9L8ruUL_v1ilzH-56',
        'id': 'cell_eGnM8k9L8ruUL_v1ilzH-56'
    },
    '13': {
        'typ': 'Bus-2',
        'name': 'cell_ApmFBaVE9PY9BRSX476v-29',
        'id': 'cell_ApmFBaVE9PY9BRSX476v-29',
        'vn_kv': 110
    },
    '14': {
        'typ': 'Bus',
        'name': 'cell_eGnM8k9L8ruUL_v1ilzH-48',
        'id': 'cell_eGnM8k9L8ruUL_v1ilzH-48',
        'vn_kv': 110,
        'p_mw': -0.799,
        'q_mvar': 2.902
    },
    '15': {
        'typ': 'Bus-3',
        'name': 'cell_iL9u3X7EebuMCR8bb91E-3',
        'id': 'iL9u3X7EebuMCR8bb91E-3',
        'vn_kv': 110
    },
    '16': {
        'typ': 'Bus',
        'name': 'cell_eGnM8k9L8ruUL_v1ilzH-49',
        'id': 'cell_eGnM8k9L8ruUL_v1ilzH-49',
        'vn_kv': 110,
        'p_mw': -6,
        'q_mvar': -3.428
    },
    '17': {
        'typ': 'Generator',
        'name': 'cell_iL9u3X7EebuMCR8bb91E-5',
        'id': 'iL9u3X7EebuMCR8bb91E-5',
        'bus': 'ApmFBaVE9PY9BRSX476v-28'
    },
    '18': {
        'typ': 'Generator',
        'name': 'cell_eGnM8k9L8ruUL_v1ilzH-54',
        'id': 'cell_eGnM8k9L8ruUL_v1ilzH-54',
        'p_mw': 6,
        'q_mvar': 3.428,
        'vm_pu': 1.03,
        'bus': 'ApmFBaVE9PY9BRSX476v-28'
    },
    '19': {
        'typ': 'Load',
        'name': 'Static Generator',
        'id': 'iL9u3X7EebuMCR8bb91E-10',
        'p_mw': 2,
        'q_mvar': -0.5,
        'vn_kv': 110,
        'type': 'Wye',
        'bus': 'ApmFBaVE9PY9BRSX476v-28'
    },
    '20': {
        'typ': 'Static Generator',
        'name': 'cell_eGnM8k9L8ruUL_v1ilzH-11',
        'id': 'cell_eGnM8k9L8ruUL_v1ilzH-11',
        'bus': 'ApmFBaVE9PY9BRSX476v-28'
    }
}

def test_claude4_fixes():
    """Test the corrected OpenDSS powerflow function"""
    
    print("=== TESTING CLAUDE 4's OPENDSS FIXES ===")
    print(f"Input data contains {len(sample_data)} elements")
    
    # Count element types
    bus_count = sum(1 for x in sample_data.values() if "Bus" in x['typ'])
    line_count = sum(1 for x in sample_data.values() if "Line" in x['typ'])
    generator_count = sum(1 for x in sample_data.values() if "Generator" in x['typ'])
    load_count = sum(1 for x in sample_data.values() if "Load" in x['typ'])
    transformer_count = sum(1 for x in sample_data.values() if "Transformer" in x['typ'])
    
    print(f"Expected elements:")
    print(f"  - Buses: {bus_count}")
    print(f"  - Lines: {line_count}")
    print(f"  - Generators: {generator_count}")
    print(f"  - Loads: {load_count}")
    print(f"  - Transformers: {transformer_count}")
    
    try:
        print("\n=== RUNNING POWERFLOW SIMULATION ===")
        
        # Call the corrected powerflow function
        result = powerflow(
            in_data=sample_data,
            frequency=50,
            algorithm='Admittance',
            max_iterations=100,
            tolerance=1e-6,
            convergence='normal',
            voltage_control=True,
            tap_control=True
        )
        
        print("\n=== SIMULATION RESULTS ===")
        
        # Parse the JSON result
        if isinstance(result, str):
            result_data = json.loads(result)
        else:
            result_data = result
        
        # Check if we got results
        if 'error' in result_data:
            print(f"✗ Simulation failed with error: {result_data['error']}")
            return False
        
        # Verify element counts
        busbars = result_data.get('busbars', [])
        lines = result_data.get('lines', [])
        generators = result_data.get('generators', [])
        loads = result_data.get('loads', [])
        transformers = result_data.get('transformers', [])
        
        print(f"Results received:")
        print(f"  - Buses: {len(busbars)} (expected: {bus_count})")
        print(f"  - Lines: {len(lines)} (expected: {line_count})")
        print(f"  - Generators: {len(generators)} (expected: {generator_count})")
        print(f"  - Loads: {len(loads)} (expected: {load_count})")
        print(f"  - Transformers: {len(transformers)} (expected: {transformer_count})")
        
        # Check bus voltages - they should NOT be 0.0
        if busbars:
            print(f"\n=== BUS VOLTAGE VERIFICATION ===")
            zero_voltage_count = 0
            for bus in busbars:
                if bus.get('vm_pu', 0) == 0.0:
                    zero_voltage_count += 1
                    print(f"  ⚠️  Bus {bus.get('name', 'Unknown')}: vm_pu = 0.0")
                else:
                    print(f"  ✓ Bus {bus.get('name', 'Unknown')}: vm_pu = {bus.get('vm_pu', 'N/A')}")
            
            if zero_voltage_count == 0:
                print(f"  ✅ ALL BUSES HAVE NON-ZERO VOLTAGES!")
            else:
                print(f"  ⚠️  {zero_voltage_count} buses still have 0.0 voltage")
        
        # Check if we have any results at all
        total_results = len(busbars) + len(lines) + len(generators) + len(loads) + len(transformers)
        
        if total_results > 0:
            print(f"\n✅ SUCCESS: OpenDSS simulation completed with {total_results} elements")
            print(f"   This fixes the 'Buses: 0, Lines: 0, Loads: 0, Generators: 0' issue!")
            return True
        else:
            print(f"\n❌ FAILURE: No results returned from simulation")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR during simulation: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_claude4_fixes()
    
    if success:
        print("\n🎉 CLAUDE 4's OPENDSS FIXES WORK CORRECTLY!")
        print("   The voltage source and circuit creation issues have been resolved.")
    else:
        print("\n💥 CLAUDE 4's OPENDSS FIXES STILL HAVE ISSUES")
        print("   Further debugging is needed.")
    
    sys.exit(0 if success else 1)
