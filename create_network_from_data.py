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
    '0': {'typ': 'ShortCircuitPandaPower Parameters', 'fault_type': '3ph', 'fault_location': 'max', 'fault_impedance': '6', 'topology': 'auto', 'tk_s': '1', 'r_fault_ohm': '0', 'x_fault_ohm': '0', 'inverse_y': 'True', 'user_email': 'xxxx'},
    '1': {'name': 'mxCell_141', 'id': 'ApmFBaVE9PY9BRSX476v-10', 'bus': 'mxCell_144', 'typ': 'External Grid0', 'vm_pu': '1.02', 'va_degree': '50', 's_sc_max_mva': '5000', 's_sc_min_mva': '5000', 'rx_max': '0.3', 'rx_min': '0.1', 'r0x0_max': '0.5', 'x0x_max': '1'},
    '2': {'name': 'mxCell_162', 'id': 'iL9u3X7EebuMCR8bb91E-10', 'bus': 'mxCell_176', 'typ': 'Static Generator', 'p_mw': '2', 'q_mvar': '-0.5', 'sn_mva': '2.5', 'scaling': '1', 'type': 'wye', 'k': '1', 'rx': '1', 'generator_type': 'async', 'lrc_pu': '1', 'max_ik_ka': '2', 'kappa': '1', 'current_source': 'true'},
    '3': {'typ': 'Bus0', 'name': 'mxCell_144', 'id': 'ApmFBaVE9PY9BRSX476v-12', 'vn_kv': '132'},
    '4': {'typ': 'Bus1', 'name': 'mxCell_148', 'id': 'ApmFBaVE9PY9BRSX476v-16', 'vn_kv': '20'},
    '5': {'typ': 'Bus2', 'name': 'mxCell_157', 'id': 'ApmFBaVE9PY9BRSX476v-28', 'vn_kv': '20'},
    '6': {'typ': 'Bus3', 'name': 'mxCell_169', 'id': 'KGSm_k2Mq3GUWYyM00zU-1', 'vn_kv': '20'},
    '7': {'typ': 'Bus4', 'name': 'mxCell_176', 'id': 'KGSm_k2Mq3GUWYyM00zU-5', 'vn_kv': '0.69'},
    '8': {'typ': 'Transformer0', 'name': 'mxCell_153', 'id': 'ApmFBaVE9PY9BRSX476v-23', 'hv_bus': 'mxCell_144', 'lv_bus': 'mxCell_148', 'sn_mva': '25', 'vn_hv_kv': '132', 'vn_lv_kv': '20', 'vkr_percent': '0.41', 'vk_percent': '12', 'pfe_kw': '14', 'i0_percent': '0.07', 'vector_group': 'Dyn', 'vk0_percent': '1', 'vkr0_percent': '1', 'mag0_percent': '1', 'si0_hv_partial': '1', 'parallel': '1', 'shift_degree': '0', 'tap_side': 'hv', 'tap_pos': '0', 'tap_neutral': '0', 'tap_max': '9', 'tap_min': '-9', 'tap_step_percent': '1.5', 'tap_step_degree': '0', 'tap_phase_shifter': 'false', 'tap_changer_type': 'Ratio'},
    '9': {'typ': 'Transformer1', 'name': 'mxCell_175', 'id': 'KGSm_k2Mq3GUWYyM00zU-4', 'hv_bus': 'mxCell_169', 'lv_bus': 'mxCell_176', 'sn_mva': '2.5', 'vn_hv_kv': '20', 'vn_lv_kv': '0.69', 'vkr_percent': '0', 'vk_percent': '6', 'pfe_kw': '0', 'i0_percent': '0', 'vector_group': 'Dyn', 'vk0_percent': '0', 'vkr0_percent': '0', 'mag0_percent': '0', 'si0_hv_partial': '0', 'parallel': '1', 'shift_degree': '0', 'tap_side': 'hv', 'tap_pos': '0', 'tap_neutral': '0', 'tap_max': '0', 'tap_min': '0', 'tap_step_percent': '0', 'tap_step_degree': '0', 'tap_phase_shifter': 'false', 'tap_changer_type': 'Ratio'},
    '10': {'typ': 'Load0', 'name': 'mxCell_167', 'id': 'iL9u3X7EebuMCR8bb91E-13', 'bus': 'mxCell_176', 'p_mw': '2', 'q_mvar': '1', 'const_z_percent': '1', 'const_i_percent': '1', 'sn_mva': '0', 'scaling': '0.6', 'type': 'wye'},
    '11': {'typ': 'Line0', 'name': 'mxCell_147', 'id': 'ApmFBaVE9PY9BRSX476v-26', 'busFrom': 'mxCell_148', 'busTo': 'mxCell_157', 'length_km': '1', 'parallel': '1', 'df': '1', 'r_ohm_per_km': '0.047', 'x_ohm_per_km': '0.163', 'c_nf_per_km': '290', 'g_us_per_km': '0', 'max_i_ka': '0.7', 'type': 'cs', 'r0_ohm_per_km': '0', 'x0_ohm_per_km': '0', 'c0_nf_per_km': '0', 'endtemp_degree': '250'},
    '12': {'typ': 'Line1', 'name': 'mxCell_155', 'id': 'KGSm_k2Mq3GUWYyM00zU-15', 'busFrom': 'mxCell_157', 'busTo': 'mxCell_169', 'length_km': '3', 'parallel': '1', 'df': '1', 'r_ohm_per_km': '0.161', 'x_ohm_per_km': '0.117', 'c_nf_per_km': '273', 'g_us_per_km': '0', 'max_i_ka': '0.362', 'type': 'cs', 'r0_ohm_per_km': '0', 'x0_ohm_per_km': '0', 'c0_nf_per_km': '0', 'endtemp_degree': '250'}
}


def main():
    # Create empty network (50 Hz - standard for European grids)
    net = pp.create_empty_network(f_hz=50)

    # Build network using existing Electrisim logic (same as Load Flow / Short Circuit)
    Busbars = pandapower_electrisim.create_busbars(in_data, net)
    pandapower_electrisim.create_other_elements(in_data, net, None, Busbars)

    # Generate Python code using same function as Load Flow "Export Pandapower Python Code"
    algorithm = 'nr'
    calculate_voltage_angles = 'auto'
    init = 'auto'
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
