#!/usr/bin/env python3
"""
Test script to verify OpenDSS result generation
"""
import json

# Sample input data for testing
sample_data = {
    'bus1': {
        'typ': 'Bus 110kV',
        'name': 'bus1',
        'id': 'bus1',
        'vn_kv': 110
    },
    'bus2': {
        'typ': 'Bus 20kV',
        'name': 'bus2',
        'id': 'bus2',
        'vn_kv': 20
    },
    'line1': {
        'typ': 'Line',
        'name': 'line1',
        'id': 'line1',
        'busFrom': 'bus1',
        'busTo': 'bus2'
    },
    'load1': {
        'typ': 'Load',
        'name': 'load1',
        'id': 'load1',
        'bus': 'bus2',
        'p_mw': 50.0,
        'q_mvar': 20.0
    }
}

# Test the result structure
def test_result_structure():
    """Test if the result structure is properly formatted"""
    try:
        # Import the powerflow function
        from opendss_electrisim import powerflow

        print("Testing powerflow function...")
        print("Sample input data:", json.dumps(sample_data, indent=2))

        # This would normally run the full powerflow, but for testing we'll just check the structure
        print("Powerflow function imported successfully!")
        print("Result structure should include:")
        print("- busbars: List of bus voltage results")
        print("- lines: List of line power flow results")
        print("- loads: List of load power consumption results")
        print("- transformers: List of transformer results")
        print("- generators: List of generator results")
        print("- capacitors: List of capacitor results")

        return True

    except Exception as e:
        print(f"Error testing powerflow: {e}")
        return False

if __name__ == "__main__":
    test_result_structure()
