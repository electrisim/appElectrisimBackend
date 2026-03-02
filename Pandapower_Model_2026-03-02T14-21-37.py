# Pandapower Network Model
# Auto-generated code to recreate the network

import pandapower as pp

# Create empty network with 50 Hz
net = pp.create_empty_network(f_hz=50)

# Create buses
bus_0 = pp.create_bus(net, vn_kv=0.0, name='mxCell_149')
bus_1 = pp.create_bus(net, vn_kv=0.0, name='mxCell_166')
bus_2 = pp.create_bus(net, vn_kv=0.0, name='mxCell_180')

# Create external grids
pp.create_ext_grid(net, bus=bus_0, vm_pu=1.0, va_degree=0.0, name='mxCell_144')

# Create transformers (2-winding)
# Transformer ID: zemTqC6MKZAaJMMi14w2-7
pp.create_transformer_from_parameters(net, hv_bus=bus_1, lv_bus=bus_0, sn_mva=23.0, vn_hv_kv=63.0, vn_lv_kv=20.0, vkr_percent=0.0, vk_percent=0.0, pfe_kw=0.0, i0_percent=0.0, parallel=1, shift_degree=300.0, tap_side='hv', tap_pos=0.0, tap_neutral=0.0, tap_max=0.0, tap_min=0.0, tap_step_percent=0.0, tap_step_degree=0.0, tap_changer_type='Ratio', vector_group='Dyn', vk0_percent=0.0, vkr0_percent=0.0, mag0_percent=0.0, mag0_rx=0.0, si0_hv_partial=0.0, name='mxCell_159')
# Transformer ID: zemTqC6MKZAaJMMi14w2-17
pp.create_transformer_from_parameters(net, hv_bus=bus_2, lv_bus=bus_1, sn_mva=10.28, vn_hv_kv=20.0, vn_lv_kv=0.69, vkr_percent=0.0, vk_percent=0.0, pfe_kw=0.0, i0_percent=0.0, parallel=1, shift_degree=300.0, tap_side='hv', tap_pos=0.0, tap_neutral=0.0, tap_max=0.0, tap_min=0.0, tap_step_percent=0.0, tap_step_degree=0.0, tap_changer_type='Ratio', vector_group='Dyn', vk0_percent=0.0, vkr0_percent=0.0, mag0_percent=0.0, mag0_rx=0.0, si0_hv_partial=0.0, name='mxCell_174')

# Create static generators
pp.create_sgen(net, bus=bus_2, p_mw=10.0, q_mvar=0.0, name='mxCell_187')

# Run power flow
pp.runpp(net, algorithm='nr', calculate_voltage_angles='auto', init='auto')

# Print results
print('\nBus Results:')
print(net.res_bus)
print('\nLine Results:')
print(net.res_line)