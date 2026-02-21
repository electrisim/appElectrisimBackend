# Pandapower Network Model
# Auto-generated code to recreate the network

import pandapower as pp

# Create empty network with 50 Hz
net = pp.create_empty_network(f_hz=50)

# Create buses
bus_0 = pp.create_bus(net, vn_kv=132.0, name='mxCell_144')
bus_1 = pp.create_bus(net, vn_kv=20.0, name='mxCell_148')
bus_2 = pp.create_bus(net, vn_kv=20.0, name='mxCell_157')
bus_3 = pp.create_bus(net, vn_kv=20.0, name='mxCell_169')
bus_4 = pp.create_bus(net, vn_kv=0.69, name='mxCell_176')

# Create external grids
pp.create_ext_grid(net, bus=bus_0, vm_pu=1.02, va_degree=50.0, name='mxCell_141')

# Create lines
# Line ID: ApmFBaVE9PY9BRSX476v-26
pp.create_line_from_parameters(net, from_bus=bus_1, to_bus=bus_2, length_km=1.0, r_ohm_per_km=0.047, x_ohm_per_km=0.163, c_nf_per_km=290.0, g_us_per_km=0.0, max_i_ka=0.7, type='cs', parallel=1, df=1.0, name='mxCell_147')
# Line ID: KGSm_k2Mq3GUWYyM00zU-15
pp.create_line_from_parameters(net, from_bus=bus_2, to_bus=bus_3, length_km=3.0, r_ohm_per_km=0.161, x_ohm_per_km=0.117, c_nf_per_km=273.0, g_us_per_km=0.0, max_i_ka=0.362, type='cs', parallel=1, df=1.0, name='mxCell_155')

# Create transformers (2-winding)
# Transformer ID: ApmFBaVE9PY9BRSX476v-23
pp.create_transformer_from_parameters(net, hv_bus=bus_0, lv_bus=bus_1, sn_mva=25.0, vn_hv_kv=132.0, vn_lv_kv=20.0, vkr_percent=0.41, vk_percent=12.0, pfe_kw=14.0, i0_percent=0.07, parallel=1, shift_degree=0.0, tap_side='hv', tap_pos=0.0, tap_neutral=0.0, tap_max=9.0, tap_min=-9.0, tap_step_percent=1.5, tap_step_degree=0.0, tap_changer_type='Ratio', vector_group='Dyn', vk0_percent=1.0, vkr0_percent=1.0, mag0_percent=1.0, mag0_rx=0.0, si0_hv_partial=1.0, name='mxCell_153')
# Transformer ID: KGSm_k2Mq3GUWYyM00zU-4
pp.create_transformer_from_parameters(net, hv_bus=bus_3, lv_bus=bus_4, sn_mva=2.5, vn_hv_kv=20.0, vn_lv_kv=0.69, vkr_percent=0.0, vk_percent=6.0, pfe_kw=0.0, i0_percent=0.0, parallel=1, shift_degree=0.0, tap_side='hv', tap_pos=0.0, tap_neutral=0.0, tap_max=0.0, tap_min=0.0, tap_step_percent=0.0, tap_step_degree=0.0, tap_changer_type='Ratio', vector_group='Dyn', vk0_percent=6.0, vkr0_percent=0.0, mag0_percent=0.0, mag0_rx=0.0, si0_hv_partial=0.0, name='mxCell_175')

# Create loads
pp.create_load(net, bus=bus_4, p_mw=2.0, q_mvar=1.0, name='mxCell_167')

# Create static generators
pp.create_sgen(net, bus=bus_4, p_mw=2.0, q_mvar=-0.5, name='mxCell_162')

# Run power flow
pp.runpp(net, algorithm='nr', calculate_voltage_angles=auto, init='auto')

# Print results
print('\nBus Results:')
print(net.res_bus)
print('\nLine Results:')
print(net.res_line)