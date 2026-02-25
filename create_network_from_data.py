"""
Create Pandapower Python model file from Electrisim diagram data.
Uses the same export logic as Load Flow dialog's "Export Pandapower Python Code" option.
Run: python create_network_from_data.py
Output: Pandapower_Model_<timestamp>.py (same format as Load Flow export)
"""
import pandapower as pp
import sys
import os
from datetime import datetime

# Add parent directory for pandapower_electrisim import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandapower_electrisim

# Input data from Electrisim diagram
in_data = {
    '0': {'typ': 'PowerFlowPandaPower Parameters', 'frequency': '50', 'algorithm': 'nr', 'calculate_voltage_angles': 'auto', 'initialization': 'auto', 'exportPython': False, 'exportPandapowerResults': False, 'run_control': False },
    '1': {'name': 'mxCell_319', 'id': 'EPPCK7KSd04BZHHZv-Wq-12', 'userFriendlyName': 'Generator', 'bus': 'mxCell_430', 'typ': 'Generator', 'p_mw': '50', 'vm_pu': '1', 'sn_mva': '0', 'scaling': '1', 'vn_kv': '0', 'xdss_pu': '0', 'rdss_ohm': '0', 'cos_phi': '0', 'pg_percent': '0', 'power_station_trafo': '0', 'in_service': 'true'},
    '2': {'name': 'mxCell_321', 'id': 'EPPCK7KSd04BZHHZv-Wq-14', 'userFriendlyName': 'Generator', 'bus': 'mxCell_287', 'typ': 'Generator', 'p_mw': '100', 'vm_pu': '1', 'sn_mva': '0', 'scaling': '1', 'vn_kv': '0', 'xdss_pu': '0', 'rdss_ohm': '0', 'cos_phi': '0', 'pg_percent': '0', 'power_station_trafo': '0', 'in_service': 'true'},
    '3': {'typ': 'Bus0', 'name': 'mxCell_287', 'id': 'EPPCK7KSd04BZHHZv-Wq-0', 'vn_kv': '220', 'userFriendlyName': 'Bus 2'},
    '4': {'typ': 'Bus1', 'name': 'mxCell_430', 'id': 'OgqhaA2ynyl4dVpjJIDU-3', 'vn_kv': '220', 'userFriendlyName': 'Bus'},
    '5': {'typ': 'Load0', 'name': 'mxCell_341', 'id': 'EPPCK7KSd04BZHHZv-Wq-16', 'userFriendlyName': 'Load', 'bus': 'mxCell_430', 'p_mw': '100', 'q_mvar': '0', 'const_z_percent': '0', 'const_i_percent': '0', 'sn_mva': '0', 'scaling': '1', 'type': 'wye', 'spectrum': 'defaultload', 'spectrum_csv': '', 'pctSeriesRL': '100', 'conn': 'wye', 'puXharm': '0', 'XRharm': '6', 'in_service': 'true'},
    '6': {'typ': 'Load1', 'name': 'mxCell_346', 'id': 'EPPCK7KSd04BZHHZv-Wq-18', 'userFriendlyName': 'Load', 'bus': 'mxCell_287', 'p_mw': '50', 'q_mvar': '0', 'const_z_percent': '0', 'const_i_percent': '0', 'sn_mva': '0', 'scaling': '1', 'type': 'wye', 'spectrum': 'defaultload', 'spectrum_csv': '', 'pctSeriesRL': '100', 'conn': 'wye', 'puXharm': '0', 'XRharm': '6', 'in_service': 'true'},
    '7': {'typ': 'Line0', 'name': 'mxCell_403', 'id': 'EPPCK7KSd04BZHHZv-Wq-37', 'userFriendlyName': 'Line', 'busFrom': 'mxCell_287', 'busTo': 'mxCell_430', 'length_km': '10', 'parallel': '1', 'df': '1', 'in_service': 'true', 'r_ohm_per_km': '0.002', 'x_ohm_per_km': '0.05', 'c_nf_per_km': '0', 'g_us_per_km': '0', 'max_i_ka': '0', 'type': 'cs', 'r0_ohm_per_km': '0', 'x0_ohm_per_km': '0', 'c0_nf_per_km': '0', 'endtemp_degree': '0'}
}


def main():
    # Get PowerFlow params from in_data if present, else defaults
    pf_params = next((in_data[k] for k in in_data if 'PowerFlowPandaPower' in in_data[k].get('typ', '')), {})
    frequency = int(pf_params.get('frequency', 50))
    algorithm = pf_params.get('algorithm', 'nr')
    calculate_voltage_angles = pf_params.get('calculate_voltage_angles', 'auto')
    init = pf_params.get('initialization', 'auto')

    # Create empty network
    net = pp.create_empty_network(f_hz=frequency)

    # Build network using existing Electrisim logic (same as Load Flow / Short Circuit)
    Busbars = pandapower_electrisim.create_busbars(in_data, net)
    pandapower_electrisim.create_other_elements(in_data, net, None, Busbars)

    # Generate Python code using same function as Load Flow "Export Pandapower Python Code"
    python_code = pandapower_electrisim.generate_pandapower_python_code(
        net, in_data, Busbars, algorithm, calculate_voltage_angles, init
    )

    # Save to .py file (same naming as Load Flow export: Pandapower_Model_<timestamp>.py)
    timestamp = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
    output_filename = f'Pandapower_Model_{timestamp}.py'
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), output_filename)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(python_code)

    print("Network created successfully!")
    print(f"  Buses: {len(net.bus)}")
    print(f"  Lines: {len(net.line)}")
    print(f"  Transformers: {len(net.trafo)}")
    print(f"  External grids: {len(net.ext_grid)}")
    print(f"  Loads: {len(net.load)}")
    print(f"  Static generators: {len(net.sgen)}")
    print(f"\nSaved to: {output_path}")


if __name__ == '__main__':
    main()
