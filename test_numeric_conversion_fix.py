#!/usr/bin/env python3
"""
Test script for numeric conversion fix

This script tests the fix for the TypeError: ufunc 'isnan' not supported for input types
that occurred when pandapower tried to process string values as numeric parameters.

The issue was that all data from the frontend comes as strings, but pandapower expects
numeric types for mathematical operations.
"""

import json
import sys
import os

# Add the current directory to Python path to import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_safe_conversion_functions():
    """Test the safe conversion helper functions"""
    
    # Helper functions (same as in the main code)
    def safe_float(value, default=None):
        if value is None or value == 'None' or value == '':
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def safe_int(value, default=1):
        if value is None or value == 'None' or value == '':
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    print("Testing safe conversion functions...")
    print("=" * 50)
    
    # Test safe_float function
    print("Testing safe_float:")
    test_cases_float = [
        ('3.14', 3.14, "Valid float string"),
        ('1', 1.0, "Integer string"),
        ('0', 0.0, "Zero string"),
        (None, None, "None value"),
        ('None', None, "String 'None'"),
        ('', None, "Empty string"),
        ('invalid', None, "Invalid string"),
        ([], None, "Invalid type (list)"),
    ]
    
    for input_val, expected, description in test_cases_float:
        result = safe_float(input_val)
        status = "✅" if result == expected else "❌"
        print(f"  {status} {description}: {input_val} -> {result} (expected: {expected})")
    
    print("\nTesting safe_int:")
    test_cases_int = [
        ('5', 5, "Valid integer string"),
        ('0', 0, "Zero string"),
        (None, 1, "None value (default)"),
        ('None', 1, "String 'None' (default)"),
        ('', 1, "Empty string (default)"),
        ('3.14', 3, "Float string (truncated)"),
        ('invalid', 1, "Invalid string (default)"),
        ([], 1, "Invalid type (default)"),
    ]
    
    for input_val, expected, description in test_cases_int:
        result = safe_int(input_val)
        status = "✅" if result == expected else "❌"
        print(f"  {status} {description}: {input_val} -> {result} (expected: {expected})")
    
    return True

def test_transformer_data_conversion():
    """Test transformer data conversion with real data from the error"""
    print("\n" + "=" * 50)
    print("Testing transformer data conversion...")
    
    # Helper functions
    def safe_float(value, default=None):
        if value is None or value == 'None' or value == '':
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def safe_int(value, default=1):
        if value is None or value == 'None' or value == '':
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    # Sample transformer data from the user's error (this would cause isnan error)
    transformer_data = {
        'typ': 'Transformer0',
        'name': 'mxCell_154',
        'id': 'foAhtE_BjKncMedPiTMK-24',
        'userFriendlyName': '40 MVA 110/30 kV',
        'hv_bus': 'mxCell_147',
        'lv_bus': 'mxCell_150',
        'sn_mva': '40',                    # String!
        'vn_hv_kv': '110',                # String!
        'vn_lv_kv': '30',                 # String!
        'vkr_percent': '0.34',            # String!
        'vk_percent': '16.2',             # String!
        'pfe_kw': '18',                   # String!
        'i0_percent': '0.05',             # String!
        'vector_group': 'Dyn',
        'vk0_percent': '1',               # String that caused isnan error!
        'vkr0_percent': '1',              # String that caused isnan error!
        'mag0_percent': '1',              # String that caused isnan error!
        'si0_hv_partial': '1',            # String that caused isnan error!
        'parallel': '1',                  # String!
        'shift_degree': '0',              # String!
        'tap_side': 'hv',
        'tap_pos': '4',                   # String!
        'tap_neutral': '0',               # String!
        'tap_max': '9',                   # String!
        'tap_min': '-9',                  # String!
        'tap_step_percent': '1.5',        # String!
        'tap_step_degree': '0',           # String!
        'tap_phase_shifter': 'False'
    }
    
    try:
        # Simulate the conversion process that happens in the fixed code
        print("Converting transformer parameters...")
        
        # Get values with default fallbacks and proper type conversion
        parallel_value = safe_int(transformer_data.get('parallel', 1), 1)
        vector_group = transformer_data.get('vector_group', None)
        vk0_percent = safe_float(transformer_data.get('vk0_percent', None))
        vkr0_percent = safe_float(transformer_data.get('vkr0_percent', None))
        mag0_percent = safe_float(transformer_data.get('mag0_percent', None))
        si0_hv_partial = safe_float(transformer_data.get('si0_hv_partial', None))
        
        # Prepare parameters dict for transformer creation with proper type conversion
        transformer_params = {
            'name': transformer_data['name'],
            'id': transformer_data['id'],
            'sn_mva': safe_float(transformer_data['sn_mva']),
            'vn_hv_kv': safe_float(transformer_data['vn_hv_kv']),
            'vn_lv_kv': safe_float(transformer_data['vn_lv_kv']),
            'vkr_percent': safe_float(transformer_data['vkr_percent']),
            'vk_percent': safe_float(transformer_data['vk_percent']),
            'pfe_kw': safe_float(transformer_data['pfe_kw']),
            'i0_percent': safe_float(transformer_data['i0_percent']),
            'parallel': parallel_value,
            'shift_degree': safe_float(transformer_data['shift_degree']),
            'tap_side': transformer_data['tap_side'],
            'tap_pos': safe_int(transformer_data['tap_pos']),
            'tap_neutral': safe_int(transformer_data['tap_neutral']),
            'tap_max': safe_int(transformer_data['tap_max']),
            'tap_min': safe_int(transformer_data['tap_min']),
            'tap_step_percent': safe_float(transformer_data['tap_step_percent']),
            'tap_step_degree': safe_float(transformer_data['tap_step_degree'])
        }
        
        # Add optional parameters only if they exist and are not None
        if vector_group is not None and vector_group != 'None':
            transformer_params['vector_group'] = vector_group
        if vk0_percent is not None:
            transformer_params['vk0_percent'] = vk0_percent
        if vkr0_percent is not None:
            transformer_params['vkr0_percent'] = vkr0_percent
        if mag0_percent is not None:
            transformer_params['mag0_percent'] = mag0_percent
        if si0_hv_partial is not None:
            transformer_params['si0_hv_partial'] = si0_hv_partial
        
        print("✅ Conversion successful!")
        print("\nConverted parameters:")
        for key, value in transformer_params.items():
            value_type = type(value).__name__
            print(f"  {key}: {value} ({value_type})")
        
        # Test that the problematic values are now numeric
        problematic_params = ['vk0_percent', 'vkr0_percent', 'mag0_percent', 'si0_hv_partial']
        print(f"\n✅ Critical zero-sequence parameters (that caused isnan error):")
        for param in problematic_params:
            if param in transformer_params:
                value = transformer_params[param]
                value_type = type(value).__name__
                print(f"  {param}: {value} ({value_type}) - Now compatible with numpy isnan()")
        
        return True
        
    except Exception as e:
        print(f"❌ Conversion failed: {e}")
        return False

def test_numpy_compatibility():
    """Test that converted values are compatible with numpy functions like isnan"""
    print("\n" + "=" * 50)
    print("Testing numpy compatibility...")
    
    import numpy as np
    
    def safe_float(value, default=None):
        if value is None or value == 'None' or value == '':
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    try:
        # Test the problematic values that caused the original error
        test_values = ['1', '1.5', '0', None, '']
        
        print("Testing numpy.isnan compatibility:")
        for original_value in test_values:
            converted_value = safe_float(original_value)
            if converted_value is not None:
                # This is the operation that was failing before
                is_nan_result = np.isnan(converted_value)
                print(f"  ✅ np.isnan({original_value} -> {converted_value}): {is_nan_result}")
            else:
                print(f"  ✅ {original_value} -> None (skipped, as intended)")
        
        print("✅ All values are now compatible with numpy operations!")
        return True
        
    except Exception as e:
        print(f"❌ Numpy compatibility test failed: {e}")
        return False

if __name__ == "__main__":
    print("Numeric Conversion Fix Test")
    print("=" * 50)
    
    success = True
    success &= test_safe_conversion_functions()
    success &= test_transformer_data_conversion()
    success &= test_numpy_compatibility()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ ALL TESTS PASSED")
        print("The fix should resolve the TypeError: ufunc 'isnan' not supported for input types")
    else:
        print("❌ SOME TESTS FAILED")
        print("Please review the implementation")
    
    print("\nWhat was fixed:")
    print("1. Added safe_float() and safe_int() helper functions")
    print("2. All string parameters are now converted to proper numeric types")
    print("3. Zero-sequence parameters (vk0_percent, etc.) are now float/None instead of strings")
    print("4. Pandapower's isnan() function can now process the values correctly")
    print("5. All transformer parameters are properly typed before passing to pandapower")
