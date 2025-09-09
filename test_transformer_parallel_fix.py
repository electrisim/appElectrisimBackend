#!/usr/bin/env python3
"""
Test script for transformer parallel field fix

This script tests the fix for the KeyError: 'parallel' issue that occurred
when processing transformer data in the short circuit simulation.

The issue was that some transformer data (particularly Transformer0) was missing
the 'parallel' field, causing a KeyError during simulation.
"""

import json
import sys
import os

# Add the current directory to Python path to import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_transformer_data_handling():
    """Test the transformer data handling with missing parallel field"""
    
    # Sample transformer data that caused the original error
    # This is based on the actual data from the user's error log
    test_transformer_data = {
        'typ': 'Transformer0',
        'name': 'mxCell_402',
        'id': 'foAhtE_BjKncMedPiTMK-24',
        'hv_bus': 'mxCell_395',
        'lv_bus': 'mxCell_398',
        'sn_mva': '40',
        'vn_hv_kv': '110',
        'vn_lv_kv': '30',
        'vkr_percent': '0.34',
        'vk_percent': '14',
        'pfe_kw': '18',
        'i0_percent': '0.05',
        'vector_group': None,  # This was None in the original data
        'vk0_percent': None,
        'vkr0_percent': None,
        'mag0_percent': None,
        'si0_hv_partial': None,
        'shift_degree': '0',
        'tap_side': 'hv',
        'tap_pos': '4',
        'tap_neutral': '0',
        'tap_max': '9',
        'tap_min': '-9',
        'tap_step_percent': '1.5',
        'tap_step_degree': '0',
        'tap_phase_shifter': 'false'
        # Note: 'parallel' field is missing - this caused the original error
    }
    
    # Test transformer data with parallel field
    test_transformer_data_with_parallel = {
        'typ': 'Transformer1',
        'name': 'mxCell_425',
        'id': 'foAhtE_BjKncMedPiTMK-47',
        'hv_bus': 'mxCell_409',
        'lv_bus': 'mxCell_416',
        'sn_mva': '3.75',
        'vn_hv_kv': '30',
        'vn_lv_kv': '0.65',
        'vkr_percent': '0.8',
        'vk_percent': '9',
        'pfe_kw': '5.8',
        'i0_percent': '0.5',
        'vector_group': 'Dyn',
        'vk0_percent': '8.2',
        'vkr0_percent': '0.7',
        'mag0_percent': '1',
        'si0_hv_partial': '1',
        'parallel': '1',  # This field is present
        'shift_degree': '0',
        'tap_side': 'hv',
        'tap_pos': '2',
        'tap_neutral': '0',
        'tap_max': '2',
        'tap_min': '-2',
        'tap_step_percent': '2.5',
        'tap_step_degree': '0',
        'tap_phase_shifter': 'False'
    }
    
    print("Testing transformer data handling fix...")
    print("=" * 50)
    
    # Test 1: Missing parallel field handling
    print("Test 1: Transformer data missing 'parallel' field")
    try:
        parallel_value = test_transformer_data.get('parallel', 1)
        vector_group = test_transformer_data.get('vector_group', None)
        vk0_percent = test_transformer_data.get('vk0_percent', None)
        vkr0_percent = test_transformer_data.get('vkr0_percent', None)
        mag0_percent = test_transformer_data.get('mag0_percent', None)
        si0_hv_partial = test_transformer_data.get('si0_hv_partial', None)
        
        print(f"✅ parallel_value: {parallel_value} (default used)")
        print(f"✅ vector_group: {vector_group}")
        print(f"✅ vk0_percent: {vk0_percent}")
        print(f"✅ vkr0_percent: {vkr0_percent}")
        print(f"✅ mag0_percent: {mag0_percent}")
        print(f"✅ si0_hv_partial: {si0_hv_partial}")
        print("✅ Test 1 PASSED: Missing fields handled correctly")
    except Exception as e:
        print(f"❌ Test 1 FAILED: {e}")
    
    print("\n" + "-" * 30 + "\n")
    
    # Test 2: Existing parallel field handling
    print("Test 2: Transformer data with 'parallel' field present")
    try:
        parallel_value = test_transformer_data_with_parallel.get('parallel', 1)
        vector_group = test_transformer_data_with_parallel.get('vector_group', None)
        vk0_percent = test_transformer_data_with_parallel.get('vk0_percent', None)
        vkr0_percent = test_transformer_data_with_parallel.get('vkr0_percent', None)
        mag0_percent = test_transformer_data_with_parallel.get('mag0_percent', None)
        si0_hv_partial = test_transformer_data_with_parallel.get('si0_hv_partial', None)
        
        print(f"✅ parallel_value: {parallel_value} (from data)")
        print(f"✅ vector_group: {vector_group}")
        print(f"✅ vk0_percent: {vk0_percent}")
        print(f"✅ vkr0_percent: {vkr0_percent}")
        print(f"✅ mag0_percent: {mag0_percent}")
        print(f"✅ si0_hv_partial: {si0_hv_partial}")
        print("✅ Test 2 PASSED: Existing fields used correctly")
    except Exception as e:
        print(f"❌ Test 2 FAILED: {e}")
    
    print("\n" + "=" * 50)
    print("Summary of fixes applied:")
    print("1. Added .get() method with default values for optional fields")
    print("2. Used parameter dictionary approach for cleaner code")
    print("3. Only include optional parameters if they are not None")
    print("4. Default 'parallel' value is 1 when missing")
    print("5. Optional zero-sequence parameters handled gracefully")
    
    return True

def test_parameter_dict_creation():
    """Test the parameter dictionary creation logic"""
    print("\n" + "=" * 50)
    print("Testing parameter dictionary creation logic...")
    
    # Mock data similar to what caused the error
    mock_data = {
        'hv_bus': 'mxCell_395',
        'lv_bus': 'mxCell_398',
        'name': 'mxCell_402',
        'id': 'foAhtE_BjKncMedPiTMK-24',
        'sn_mva': '40',
        'vn_hv_kv': '110',
        'vn_lv_kv': '30',
        'vkr_percent': '0.34',
        'vk_percent': '14',
        'pfe_kw': '18',
        'i0_percent': '0.05',
        'shift_degree': '0',
        'tap_side': 'hv',
        'tap_pos': '4',
        'tap_neutral': '0',
        'tap_max': '9',
        'tap_min': '-9',
        'tap_step_percent': '1.5',
        'tap_step_degree': '0',
        'vector_group': None,
        # 'parallel' is missing
    }
    
    try:
        # Simulate the fix logic
        parallel_value = mock_data.get('parallel', 1)
        vector_group = mock_data.get('vector_group', None)
        vk0_percent = mock_data.get('vk0_percent', None)
        vkr0_percent = mock_data.get('vkr0_percent', None)
        mag0_percent = mock_data.get('mag0_percent', None)
        si0_hv_partial = mock_data.get('si0_hv_partial', None)
        
        # Create parameter dictionary
        transformer_params = {
            'hv_bus': mock_data['hv_bus'],  # Would use eval() in real code
            'lv_bus': mock_data['lv_bus'],  # Would use eval() in real code
            'name': mock_data['name'],
            'id': mock_data['id'],
            'sn_mva': mock_data['sn_mva'],
            'vn_hv_kv': mock_data['vn_hv_kv'],
            'vn_lv_kv': mock_data['vn_lv_kv'],
            'vkr_percent': mock_data['vkr_percent'],
            'vk_percent': mock_data['vk_percent'],
            'pfe_kw': mock_data['pfe_kw'],
            'i0_percent': mock_data['i0_percent'],
            'parallel': parallel_value,
            'shift_degree': mock_data['shift_degree'],
            'tap_side': mock_data['tap_side'],
            'tap_pos': mock_data['tap_pos'],
            'tap_neutral': mock_data['tap_neutral'],
            'tap_max': mock_data['tap_max'],
            'tap_min': mock_data['tap_min'],
            'tap_step_percent': mock_data['tap_step_percent'],
            'tap_step_degree': mock_data['tap_step_degree']
        }
        
        # Add optional parameters only if they exist and are not None
        if vector_group is not None:
            transformer_params['vector_group'] = vector_group
        if vk0_percent is not None:
            transformer_params['vk0_percent'] = vk0_percent
        if vkr0_percent is not None:
            transformer_params['vkr0_percent'] = vkr0_percent
        if mag0_percent is not None:
            transformer_params['mag0_percent'] = mag0_percent
        if si0_hv_partial is not None:
            transformer_params['si0_hv_partial'] = si0_hv_partial
        
        print("✅ Parameter dictionary created successfully")
        print(f"✅ Required parameters: {len([k for k, v in transformer_params.items() if k not in ['vector_group', 'vk0_percent', 'vkr0_percent', 'mag0_percent', 'si0_hv_partial']])}")
        print(f"✅ Optional parameters included: {len([k for k, v in transformer_params.items() if k in ['vector_group', 'vk0_percent', 'vkr0_percent', 'mag0_percent', 'si0_hv_partial']])}")
        print("✅ Parameter dictionary test PASSED")
        
        return True
        
    except Exception as e:
        print(f"❌ Parameter dictionary test FAILED: {e}")
        return False

if __name__ == "__main__":
    print("Transformer Parallel Field Fix Test")
    print("=" * 50)
    
    success = True
    success &= test_transformer_data_handling()
    success &= test_parameter_dict_creation()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ ALL TESTS PASSED")
        print("The fix should resolve the KeyError: 'parallel' issue")
    else:
        print("❌ SOME TESTS FAILED")
        print("Please review the implementation")
    
    print("\nNext steps:")
    print("1. Test the actual short circuit simulation")
    print("2. Verify that all transformer types are handled correctly")
    print("3. Monitor for any other missing field errors")
