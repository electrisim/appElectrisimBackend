"""Harmonic study: order ranges, frequency scan, STATCOM and the controlled operating point.

- "5,7,11-13" style order lists are expanded;
- the frequency scan finds the parallel resonance of a capacitor bank against the grid
  (h = sqrt(S_sc / Q_c) = 10 for 1000 MVA and 10 Mvar) and returns one point per scanned order;
- harmonic voltages are reported for every bus and harmonic currents for lines and transformers;
- a STATCOM (SSC) is left out of a plain OpenDSS load flow with a warning, and is part of the
  circuit (0 kW generator with the given Mvar) once the operating point carries its output;
- apply_operating_point writes turbine Q, reactor steps, tap positions and STATCOM output into
  the OpenDSS request without touching the original.

Run with ``python samples/test_opendss_harmonic_scan.py``.
"""
from __future__ import annotations

import contextlib
import io
import json
import math
import os
import sys
import warnings

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import app  # noqa: E402
import harmonic_operating_point as hop  # noqa: E402

CLIENT = app.app.test_client()


def network(**params):
    """20 kV grid bus with a 10 Mvar capacitor bank, a 20/0.4 kV transformer and a load."""
    settings = {
        'typ': 'PowerFlowOpenDss Parameters', 'frequency': '50', 'mode': 'Snapshot',
        'algorithm': 'Normal', 'loadmodel': 'Powerflow', 'maxIterations': '100',
        'tolerance': '0.0001', 'controlmode': 'Static', 'exportCommands': False,
        'analysisType': 'harmonic', 'harmonics': '5,7,11-13', 'user_email': 'test@example.com',
    }
    settings.update(params)
    return {
        '0': settings,
        '1': {'typ': 'External Grid', 'name': 'grid', 'id': 'grid', 'bus': 'b_mv', 'vm_pu': 1, 'va_degree': 0,
              's_sc_max_mva': 1000, 's_sc_min_mva': 1000, 'rx_max': 0.1, 'rx_min': 0.1,
              'r0x0_max': 0.1, 'x0x_max': 1, 'r0x0_min': 0.1, 'x0x_min': 1, 'in_service': True},
        '2': {'typ': 'Bus0', 'name': 'b_mv', 'id': 'bus-mv', 'vn_kv': '20', 'userFriendlyName': 'MV bus'},
        '3': {'typ': 'Bus1', 'name': 'b_lv', 'id': 'bus-lv', 'vn_kv': '0.4', 'userFriendlyName': 'LV bus'},
        '4': {'typ': 'Bus2', 'name': 'b_end', 'id': 'bus-end', 'vn_kv': '20', 'userFriendlyName': 'Feeder end'},
        '5': {'typ': 'Shunt Reactor', 'name': 'cap', 'id': 'cap', 'bus': 'b_mv', 'p_mw': '0', 'q_mvar': '-10',
              'vn_kv': '20', 'step': '1', 'max_step': '1', 'in_service': True},
        '6': {'typ': 'Transformer', 'name': 'tr', 'id': 'tr', 'busFrom': 'b_mv', 'busTo': 'b_lv', 'sn_mva': '2',
              'vk_percent': '6', 'vkr_percent': '1', 'vn_hv_kv': '20', 'vn_lv_kv': '0.4', 'pfe_kw': '2',
              'i0_percent': '0.2', 'shift_degree': '0', 'tap_side': 'hv', 'tap_neutral': '0', 'tap_min': '-2',
              'tap_max': '2', 'tap_step_percent': '2.5', 'tap_pos': '0', 'in_service': True, 'vector_group': 'Dyn'},
        '7': {'typ': 'Load', 'name': 'ld', 'id': 'ld', 'bus': 'b_lv', 'p_mw': '1', 'q_mvar': '0.2', 'sn_mva': '1',
              'scaling': '1', 'type': 'wye', 'in_service': True, 'spectrum': 'defaultload', 'spectrum_csv': '',
              'pctSeriesRL': '50', 'conn': 'wye', 'puXharm': '0.0', 'XRharm': '6.0'},
        '8': {'typ': 'Line', 'name': 'ln', 'id': 'ln', 'busFrom': 'b_mv', 'busTo': 'b_end', 'r_ohm_per_km': '0.1',
              'x_ohm_per_km': '0.1', 'length_km': '1', 'c_nf_per_km': '200', 'parallel': '1', 'df': '1',
              'g_us_per_km': '0', 'max_i_ka': '1', 'in_service': True},
    }


def run(payload):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        response = CLIENT.post("/", json=payload)
    assert response.status_code == 200, response.get_data(as_text=True)[:300]
    return json.loads(response.get_data(as_text=True))


def test_order_ranges():
    assert hop.parse_harmonic_orders('3,5,7') == [3, 5, 7]
    assert hop.parse_harmonic_orders('2-6') == [2, 3, 4, 5, 6]
    assert hop.parse_harmonic_orders('5; 7, 11 - 13') == [5, 7, 11, 12, 13]
    assert hop.parse_harmonic_orders('1, 0, abc') == [3, 5, 7, 11, 13]      # nothing usable: the default
    assert hop.parse_harmonic_orders('') == [3, 5, 7, 11, 13]
    assert hop.parse_harmonic_orders([5, '7']) == [5, 7]
    print("harmonic order lists and ranges are parsed")


def test_scan_finds_capacitor_resonance():
    data = run(network(scanBusIds=['bus-mv'], scanMaxOrder=20, scanStep=0.1))
    assert not data.get('error'), data.get('error')
    meta = data['harmonic_analysis']
    assert meta['harmonic_orders'] == [5, 7, 11, 12, 13], meta['harmonic_orders']
    scan = meta['frequency_scan']
    assert len(scan['orders']) == 190 and abs(scan['orders'][0] - 1.1) < 1e-9 and abs(scan['orders'][-1] - 20.0) < 1e-9
    bus = scan['buses'][0]
    assert bus['id'] == 'bus-mv' and len(bus['z_ohm']) == 190
    assert all(z is not None and math.isfinite(z) and z > 0 for z in bus['z_ohm'])
    peaks = bus['parallel_resonances']
    assert peaks, 'no parallel resonance found'
    main = max(peaks, key=lambda r: r['z_ohm'])
    assert 9.3 <= main['order'] <= 10.4, main          # sqrt(1000 MVA / 10 Mvar) = 10, pulled down a little by the feeder
    # Well below resonance the grid dominates: |Z| ~ h * X_grid, X_grid = 20^2 / 1000 = 0.4 ohm, inductive
    i2 = scan['orders'].index(2.0)
    assert 0.6 < bus['z_ohm'][i2] < 1.1, bus['z_ohm'][i2]
    assert 60 < bus['angle_deg'][i2] < 90, bus['angle_deg'][i2]
    print(f"frequency scan: parallel resonance at h = {main['order']} ({main['z_ohm']:.1f} ohm)")


def test_every_bus_and_branch_has_harmonics():
    data = run(network())
    assert not data.get('error'), data.get('error')
    assert 'frequency_scan' not in data['harmonic_analysis']
    for bus in data['busbars']:
        assert set(bus['harmonic_voltages_kv']) == {'5', '7', '11', '12', '13'}, bus
        assert bus['fundamental_voltage_kv'] > 0 and bus['vn_kv'] > 0
        assert bus['harmonic_voltages_kv']['5'] > 0, bus   # the load injects a 5th harmonic
    for key in ('lines', 'transformers'):
        rows = data[key]
        assert rows and all('harmonic_currents_a' in r and 'ithd_percent' in r for r in rows), key
    trafo = data['transformers'][0]
    assert trafo['harmonic_currents_a']['5'] > 0 and trafo['ithd_percent'] > 0
    print("harmonic voltages for every bus, harmonic currents for lines and transformers")


def test_statcom_needs_operating_point():
    payload = network()
    payload['9'] = {'typ': 'SSC', 'name': 'ssc', 'id': 'ssc', 'bus': 'b_mv', 'p_mw': 0, 'q_mvar': 0,
                    'in_service': True, 'userFriendlyName': 'STATCOM 1'}
    data = run(payload)
    assert not data.get('error'), data.get('error')
    assert any('STATCOM' in w for w in data['harmonic_analysis']['warnings']), data['harmonic_analysis']['warnings']

    # With its output known (written by the controlled operating point) it is part of the circuit.
    payload = network(exportCommands=True)
    payload['9'] = {'typ': 'SSC', 'name': 'ssc', 'id': 'ssc', 'bus': 'b_mv', 'in_service': True,
                    'q_inject_mvar': 3.0, 'q_max_mvar': 5.0, 'r_ohm': 1.0, 'x_ohm': 20.0}
    data = run(payload)
    assert not data.get('error'), data.get('error')
    assert not any('STATCOM' in w for w in data['harmonic_analysis']['warnings'])
    commands = data.get('opendss_commands', '')
    assert 'New Generator.ssc_ssc' in commands and 'kvar=3000.000' in commands, 'STATCOM generator missing'
    assert 'Xdpp=0.250000' in commands, 'coupling reactance: 20 ohm on 20 kV / 5 MVA = 0.25 pu'
    print("STATCOM: warning without an operating point, 0 kW generator behind its coupling reactance with one")


def test_apply_operating_point():
    request = {
        'a': {'typ': 'Static Generator', 'name': 'wt1', 'q_mvar': '-3.26', 'q_setpoint_mode': 'capacitive_max'},
        'b': {'typ': 'Shunt Reactor', 'name': 'r1', 'q_mvar': '10', 'step': '1', 'max_step': '3',
              'step_dependency_table': 'true', 'line_flow_step_control': 'true'},
        'c': {'typ': 'Three Winding Transformer', 'name': 't3', 'tap_pos': '-4'},
        'd': {'typ': 'SSC', 'name': 's1', 'bus': 'b'},
        'e': {'typ': 'Static Generator', 'name': 'other', 'q_mvar': '1'},
    }
    op = {'ok': True,
          'sgen_q': {'wt1': {'p_mw': 15.0, 'q_mvar': -0.73}},
          'shunts': {'r1': {'p_mw': 0.1, 'q_mvar': 140.0, 'step': 3}},
          'taps': {'t3': -3.0},
          'sscs': {'s1': {'q_inject_mvar': 200.0, 'r_ohm': 15.0, 'x_ohm': 227.0, 'q_max_mvar': 200.0}}}
    out = hop.apply_operating_point(request, op)
    assert out['a']['q_mvar'] == -0.73 and 'q_setpoint_mode' not in out['a']
    assert out['b']['q_mvar'] == 140.0 and out['b']['step'] == 1 and out['b']['line_flow_step_control'] == 'false'
    assert out['c']['tap_pos'] == -3.0
    assert out['d']['q_inject_mvar'] == 200.0 and out['d']['x_ohm'] == 227.0
    assert out['e']['q_mvar'] == '1'
    assert request['a']['q_mvar'] == '-3.26' and 'q_inject_mvar' not in request['d'], 'the request itself must not change'
    assert hop.apply_operating_point(request, {'ok': False})['a']['q_mvar'] == '-3.26'
    print("the controlled operating point is written into a copy of the OpenDSS request")


def test_resonance_finder():
    orders = [round(1 + 0.1 * i, 1) for i in range(100)]
    z = [1.0 / abs(h - 5.0 + 0.03) + 0.2 * h for h in orders]      # one sharp peak near 5
    parallel, _series = hop.find_resonances(orders, z)
    assert len(parallel) == 1 and abs(parallel[0]['order'] - 5.0) < 0.11, parallel
    flat = [0.4 * h for h in orders]
    assert hop.find_resonances(orders, flat) == ([], [])
    print("resonances: one peak found, none on a plain inductive curve")


def main() -> None:
    test_order_ranges()
    test_resonance_finder()
    test_apply_operating_point()
    test_every_bus_and_branch_has_harmonics()
    test_scan_finds_capacitor_resonance()
    test_statcom_needs_operating_point()
    print("All harmonic scan checks passed.")


if __name__ == "__main__":
    main()
