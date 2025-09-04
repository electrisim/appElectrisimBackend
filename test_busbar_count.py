#!/usr/bin/env python3
"""
Test script to verify busbar count in OpenDSS simulation
"""

import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the OpenDSS module
import opendss_electrisim

def test_busbar_count():
    """Test the busbar count to ensure only 5 busbars are created"""
    
    # Your Pandapower input data with 5 busbars
    test_data = {
        "0": {"typ": "PowerFlowPandaPower Parameters", "frequency": "50", "algorithm": "nr", "calculate_voltage_angles": "auto", "initialization": "auto", "user_email": "maciej@gmail.com"},
        "1": {"name": "mxCell_122", "id": "ApmFBaVE9PY9BRSX476v-10", "bus": "mxCell_126", "typ": "External Grid0", "userFriendlyName": "External Grid", "vm_pu": "1.02", "va_degree": "50", "s_sc_max_mva": "1000000", "s_sc_min_mva": "0", "rx_max": "0", "rx_min": "0", "r0x0_max": "0", "x0x_max": "0"},
        "2": {"name": "mxCell_148", "id": "iL9u3X7EebuMCR8bb91E-4", "bus": "mxCell_144", "typ": "Generator", "userFriendlyName": "Generator", "p_mw": "6", "vm_pu": "1.03", "sn_mva": "6", "scaling": "1", "vn_kv": "20", "xdss_pu": "1", "rdss_ohm": "1", "cos_phi": "0", "pg_percent": "0", "power_station_trafo": "0"},
        "3": {"name": "mxCell_152", "id": "iL9u3X7EebuMCR8bb91E-10", "bus": "mxCell_140", "typ": "Static Generator", "userFriendlyName": "Static Generator", "p_mw": "2", "q_mvar": "-0.5", "sn_mva": "2.5", "scaling": "1", "type": "Wye", "k": "1", "rx": "1", "generator_type": "async", "lrc_pu": "1", "max_ik_ka": "2", "kappa": "1", "current_source": "true"},
        "4": {"typ": "Bus0", "name": "mxCell_126", "id": "ApmFBaVE9PY9BRSX476v-12", "vn_kv": "110", "userFriendlyName": "Bus"},
        "5": {"typ": "Bus1", "name": "mxCell_129", "id": "ApmFBaVE9PY9BRSX476v-14", "vn_kv": "110", "userFriendlyName": "Bus"},
        "6": {"typ": "Bus2", "name": "mxCell_133", "id": "ApmFBaVE9PY9BRSX476v-16", "vn_kv": "20", "userFriendlyName": "Bus"},
        "7": {"typ": "Bus3", "name": "mxCell_140", "id": "ApmFBaVE9PY9BRSX476v-28", "vn_kv": "20", "userFriendlyName": "Bus"},
        "8": {"typ": "Bus4", "name": "mxCell_144", "id": "iL9u3X7EebuMCR8bb91E-2", "vn_kv": "20", "userFriendlyName": "Bus"},
        "9": {"typ": "Transformer0", "name": "mxCell_138", "id": "ApmFBaVE9PY9BRSX476v-23", "userFriendlyName": "25 MVA 110/20 kV", "hv_bus": "mxCell_129", "lv_bus": "mxCell_133", "sn_mva": "25", "vn_hv_kv": "110", "vn_lv_kv": "20", "vkr_percent": "0.41", "vk_percent": "12", "pfe_kw": "14", "i0_percent": "0.07", "vector_group": "Dyn", "vk0_percent": "1", "vkr0_percent": "1", "mag0_percent": "1", "si0_hv_partial": "1", "parallel": "1", "shift_degree": "0", "tap_side": "hv", "tap_pos": "0", "tap_neutral": "0", "tap_max": "9", "tap_min": "-9", "tap_step_percent": "1.5", "tap_step_degree": "0", "tap_phase_shifter": "False"},
        "10": {"typ": "Shunt Reactor0", "name": "mxCell_159", "id": "iL9u3X7EebuMCR8bb91E-17", "userFriendlyName": "Generator", "bus": "mxCell_129", "p_mw": "0", "q_mvar": "-0.96", "vn_kv": "110", "step": "1", "max_step": "1"},
        "11": {"typ": "Load0", "name": "mxCell_156", "id": "iL9u3X7EebuMCR8bb91E-13", "userFriendlyName": "Load", "bus": "mxCell_140", "p_mw": "2", "q_mvar": "4", "const_z_percent": "1", "const_i_percent": "1", "sn_mva": "0", "scaling": "0.6", "type": "Wye"},
        "12": {"typ": "Line0", "name": "mxCell_125", "id": "ApmFBaVE9PY9BRSX476v-22", "userFriendlyName": "N2XS(FL)2Y 1x300 RM/35 64/110 kV", "busFrom": "mxCell_126", "busTo": "mxCell_129", "length_km": "10", "parallel": "1", "df": "1", "r_ohm_per_km": "0.06", "x_ohm_per_km": "0.144", "c_nf_per_km": "144", "g_us_per_km": "0", "max_i_ka": "0.588", "type": "cs", "r0_ohm_per_km": "0.1", "x0_ohm_per_km": "0", "c0_nf_per_km": "0", "endtemp_degree": "250"},
        "13": {"typ": "Line1", "name": "mxCell_132", "id": "ApmFBaVE9PY9BRSX476v-26", "userFriendlyName": "NA2XS2Y 1x240 RM/25 12/20 kV", "busFrom": "mxCell_133", "busTo": "mxCell_140", "length_km": "2.5", "parallel": "1", "df": "1", "r_ohm_per_km": "0.122", "x_ohm_per_km": "0.112", "c_nf_per_km": "304", "g_us_per_km": "0", "max_i_ka": "0.421", "type": "cs", "r0_ohm_per_km": "0", "x0_ohm_per_km": "0", "c0_nf_per_km": "0", "endtemp_degree": "250"},
        "14": {"typ": "Line2", "name": "mxCell_143", "id": "iL9u3X7EebuMCR8bb91E-1", "userFriendlyName": "NA2XS2Y 1x240 RM/25 12/20 kV", "busFrom": "mxCell_133", "busTo": "mxCell_144", "length_km": "2", "parallel": "1", "df": "1", "r_ohm_per_km": "0.122", "x_ohm_per_km": "0.112", "c_nf_per_km": "304", "g_us_per_km": "0", "max_i_ka": "0.421", "type": "cs", "r0_ohm_per_km": "0", "x0_ohm_per_km": "0", "c0_nf_per_km": "0", "endtemp_degree": "250"}
    }
    
    print("=== TESTING BUSBAR COUNT ===")
    print(f"Input data has {len(test_data)} elements")
    
    # Count busbars in input data
    busbar_count = 0
    for key, element in test_data.items():
        if "Bus" in element.get('typ', ''):
            busbar_count += 1
            print(f"  Found busbar: {element['name']} (Type: {element['typ']})")
    
    print(f"Total busbars in input data: {busbar_count}")
    print()
    
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
            print(f"❌ Error in powerflow: {result['error']}")
            return False
        
        # Parse the result to count busbars
        if isinstance(result, str):
            import json
            try:
                result_dict = json.loads(result)
            except json.JSONDecodeError:
                print(f"❌ Failed to parse JSON result: {result}")
                return False
        else:
            result_dict = result
        
        # Count busbars in the result
        if 'busbars' in result_dict:
            result_busbar_count = len(result_dict['busbars'])
            print(f"✅ Result has {result_busbar_count} busbars")
            
            if result_busbar_count == busbar_count:
                print(f"✅ SUCCESS: Busbar count matches! Input: {busbar_count}, Output: {result_busbar_count}")
                return True
            else:
                print(f"❌ FAILURE: Busbar count mismatch! Input: {busbar_count}, Output: {result_busbar_count}")
                
                # Show the busbars in the result
                print("\nBusbars in result:")
                for i, busbar in enumerate(result_dict['busbars']):
                    print(f"  {i+1}: {busbar}")
                
                return False
        else:
            print(f"❌ No 'busbars' key found in result")
            print(f"Result keys: {list(result_dict.keys())}")
            return False
            
    except Exception as e:
        print(f"❌ Exception during powerflow: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_busbar_count()
    if success:
        print("\n🎉 Test PASSED: Busbar count issue is fixed!")
    else:
        print("\n💥 Test FAILED: Busbar count issue still exists!")
    
    sys.exit(0 if success else 1)
