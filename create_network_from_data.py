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
    '0': {'typ': 'ShortCircuitPandaPower Parameters', 'fault_type': '3ph', 'fault_location': 'max', 'fault_impedance': '6', 'topology': 'auto', 'tk_s': '1', 'r_fault_ohm': '0', 'x_fault_ohm': '0', 'inverse_y': 'True'}, '1': {'name': 'mxCell_144', 'id': 'zemTqC6MKZAaJMMi14w2-1', 'bus': 'mxCell_149', 'typ': 'External Grid0', 'vm_pu': '1', 'va_degree': '0', 's_sc_max_mva': '1000000.0', 's_sc_min_mva': '0', 'rx_max': '0', 'rx_min': '0', 'r0x0_max': '0', 'x0x_max': '0'}, '2': {'name': 'mxCell_187', 'id': 'zemTqC6MKZAaJMMi14w2-24', 'bus': 'mxCell_180', 'typ': 'Static Generator', 'p_mw': '10', 'q_mvar': '0', 'sn_mva': '10.08', 'scaling': '1', 'type': 'wye', 'k': '0', 'rx': '0.033', 'generator_type': 'async', 'lrc_pu': '0', 'max_ik_ka': '10.416', 'kappa': '0', 'current_source': 'true'}, '3': {'typ': 'Bus0', 'name': 'mxCell_149', 'id': 'zemTqC6MKZAaJMMi14w2-3', 'vn_kv': '0'}, '4': {'typ': 'Bus1', 'name': 'mxCell_166', 'id': 'zemTqC6MKZAaJMMi14w2-12', 'vn_kv': '0'}, '5': {'typ': 'Bus2', 'name': 'mxCell_180', 'id': 'zemTqC6MKZAaJMMi14w2-20', 'vn_kv': '0'}, '6': {'typ': 'Transformer0', 'name': 'mxCell_159', 'id': 'zemTqC6MKZAaJMMi14w2-7', 'hv_bus': 'mxCell_166', 'lv_bus': 'mxCell_149', 'sn_mva': '23', 'vn_hv_kv': '63', 'vn_lv_kv': '20', 'vkr_percent': '0', 'vk_percent': '0', 'pfe_kw': '0', 'i0_percent': '0', 'vector_group': 'Dyn11', 'vk0_percent': '0', 'vkr0_percent': '0', 'mag0_percent': '0', 'si0_hv_partial': '0', 'parallel': '1', 'shift_degree': '-30', 'tap_side': 'hv', 'tap_pos': '0', 'tap_neutral': '0', 'tap_max': '0', 'tap_min': '0', 'tap_step_percent': '0', 'tap_step_degree': '0', 'tap_phase_shifter': 'false', 'tap_changer_type': 'Ratio'}, '7': {'typ': 'Transformer1', 'name': 'mxCell_174', 'id': 'zemTqC6MKZAaJMMi14w2-17', 'hv_bus': 'mxCell_180', 'lv_bus': 'mxCell_166', 'sn_mva': '10.28', 'vn_hv_kv': '20', 'vn_lv_kv': '0.69', 'vkr_percent': '0', 'vk_percent': '0', 'pfe_kw': '0', 'i0_percent': '0', 'vector_group': 'Dyn11', 'vk0_percent': '0', 'vkr0_percent': '0', 'mag0_percent': '0', 'si0_hv_partial': '0', 'parallel': '1', 'shift_degree': '-30', 'tap_side': 'hv', 'tap_pos': '0', 'tap_neutral': '0', 'tap_max': '0', 'tap_min': '0', 'tap_step_percent': '0', 'tap_step_degree': '0', 'tap_phase_shifter': 'false', 'tap_changer_type': 'Ratio'}
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
