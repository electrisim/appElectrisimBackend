"""Grid-forming STATCOM sizing: converter rating and supercapacitor bank.

A STATCOM alone has no energy store, so it can only exchange reactive power. To behave as a
grid-forming unit (voltage source, synthetic inertia, damping of power oscillations, short
frequency support in an island) it has to deliver and absorb active power for seconds. That
energy comes from supercapacitors on its DC side. This study answers two questions:

1. How much active power and energy do the grid-forming duties need?
2. Which converter rating and which supercapacitor bank deliver it at end of life?

Duties (each can be switched off):

- synthetic inertia   P = -2 H S (f/f0) (df/dt) / f0, energy H S (1 - (f1/f0)^2)
- phase jump          P = V^2 sin(d_theta) / (X_coupling + X_grid), decaying with tau
- oscillation damping P = A sin(2 pi f_osc t)
- frequency support   droop with deadband, limited to a share of the plant power, for a
                      bridging time (FSM / LFSM while the turbines take over)

What comes from the diagram: the STATCOM rating and coupling reactance, the plant rated power,
the reactive power the STATCOM carries in the solved load flow (with the park controller, plant
supervisory controller, reactor steps and tap changers), and the short-circuit power of the
grid at the STATCOM bus and at the connection point (turbines excluded).

The bank is sized by simulating an under-frequency event (discharge) and an over-frequency
event (charge) with end-of-life capacitance and resistance, and taking the smallest number of
parallel strings that keeps the bank voltage and the cell current inside their limits.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import math

import numpy as np

DT = 0.005
PRE_S = 0.5
RECOVERY_S = 5.0
CHART_POINTS = 500
MAX_STRINGS = 2_000_000


class _StudyError(Exception):
    pass


def _num(value, default):
    try:
        out = float(str(value).replace(',', '.'))
        return out if math.isfinite(out) else default
    except (TypeError, ValueError):
        return default


def _flag(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None or value == '':
        return default
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def _r(value, digits=3):
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return round(value, digits) if math.isfinite(value) else None


# --------------------------------------------------------------------------- duties

def read_duties(params, plant_mw, statcom_mva, f0):
    """Duty settings as numbers. ``plant_mw`` and ``statcom_mva`` are the bases."""
    p = params or {}
    base_kind = str(p.get('inertia_base', 'plant')).strip().lower()
    inertia_base = statcom_mva if base_kind.startswith('statcom') else plant_mw
    f_min = min(_num(p.get('f_min_hz'), f0 * 0.95), f0 - 0.01)
    f_max = max(_num(p.get('f_max_hz'), f0 * 1.03), f0 + 0.01)
    return {
        'f0': f0,
        'rocof': max(_num(p.get('rocof_hz_s'), 2.0), 0.01),
        'f_min': f_min,
        'f_max': f_max,
        'inertia': _flag(p.get('duty_inertia'), True),
        'h_s': max(_num(p.get('inertia_h_s'), 3.0), 0.0),
        'inertia_base_kind': 'statcom' if base_kind.startswith('statcom') else 'plant',
        'inertia_base_mva': inertia_base,
        'phase_jump': _flag(p.get('duty_phase_jump'), True),
        'phase_deg': min(max(_num(p.get('phase_jump_deg'), 10.0), 0.0), 90.0),
        'phase_tau': max(_num(p.get('phase_jump_tau_s'), 0.2), 0.01),
        'damping': _flag(p.get('duty_damping'), True),
        'damping_mw': max(_num(p.get('damping_percent'), 5.0), 0.0) / 100.0 * statcom_mva,
        'damping_hz': max(_num(p.get('damping_freq_hz'), 0.5), 0.01),
        'support': _flag(p.get('duty_frequency_support'), False),
        'droop': max(_num(p.get('droop_percent'), 5.0), 0.1) / 100.0,
        'deadband_hz': max(_num(p.get('deadband_mhz'), 20.0), 0.0) / 1000.0,
        'support_cap_mw': max(_num(p.get('support_range_percent'), 5.0), 0.0) / 100.0 * plant_mw,
        'support_time': max(_num(p.get('support_time_s'), 15.0), 0.0),
        'activation_hz': max(_num(p.get('activation_threshold_hz'), 0.0), 0.0),
        'activation_delay': max(_num(p.get('activation_delay_s'), 0.0), 0.0),
        'plant_mw': plant_mw,
    }


def event_profile(d, direction, phase_jump_mw):
    """Active power the STATCOM must deliver (+) or absorb (-) through a frequency event.

    ``direction`` is +1 for the under-frequency event (frequency falls, the STATCOM injects) and
    -1 for the over-frequency event. Returns arrays ``t``, ``f`` and one array per duty.
    """
    f0 = d['f0']
    f_end = d['f_min'] if direction > 0 else d['f_max']
    span = abs(f_end - f0)
    fall = span / d['rocof']
    t_fall_end = PRE_S + fall

    # when the frequency support starts: deviation beyond the threshold (or the deadband), plus the delay
    trigger = max(d['activation_hz'], d['deadband_hz'])
    t_act = None
    if d['support'] and span > trigger:
        t_act = PRE_S + trigger / d['rocof'] + d['activation_delay']
    hold = 2.0
    if t_act is not None:
        hold = max(hold, t_act + d['support_time'] + 1.0 - t_fall_end)
    t_hold_end = t_fall_end + hold
    t_end = t_hold_end + RECOVERY_S + 1.0

    t = np.arange(0.0, t_end + DT / 2, DT)
    f = np.full_like(t, f0)
    falling = (t >= PRE_S) & (t < t_fall_end)
    f[falling] = f0 - direction * d['rocof'] * (t[falling] - PRE_S)
    f[(t >= t_fall_end) & (t < t_hold_end)] = f_end
    rec = (t >= t_hold_end) & (t < t_hold_end + RECOVERY_S)
    f[rec] = f_end + (f0 - f_end) * (t[rec] - t_hold_end) / RECOVERY_S
    dfdt = np.gradient(f, DT)

    zero = np.zeros_like(t)
    after = t >= PRE_S
    p_inertia = -2.0 * d['h_s'] * d['inertia_base_mva'] * (f / f0) * dfdt / f0 if d['inertia'] else zero
    p_phase = zero.copy()
    if d['phase_jump'] and phase_jump_mw > 0:
        p_phase[after] = direction * phase_jump_mw * np.exp(-(t[after] - PRE_S) / d['phase_tau'])
    p_damp = zero.copy()
    if d['damping'] and d['damping_mw'] > 0:
        active = after & (t < t_hold_end)
        p_damp[active] = direction * d['damping_mw'] * np.sin(2 * math.pi * d['damping_hz'] * (t[active] - PRE_S))
    p_support = zero.copy()
    if t_act is not None and d['support_time'] > 0:
        deviation = np.maximum(np.abs(f - f0) - d['deadband_hz'], 0.0)
        wanted = np.minimum(deviation / f0 / d['droop'] * d['plant_mw'], d['support_cap_mw'])
        window = np.clip((t - t_act) / 0.2, 0.0, 1.0) * np.clip((t_act + d['support_time'] + 1.0 - t), 0.0, 1.0)
        p_support = direction * wanted * window
    total = p_inertia + p_phase + p_damp + p_support
    return {'t': t, 'f': f, 'p_inertia': p_inertia, 'p_phase': p_phase, 'p_damping': p_damp,
            'p_support': p_support, 'p_total': total}


def duty_table(d, phase_jump_mw):
    """Peak power and energy of each duty on its own (closed-form, for the results table)."""
    f0 = d['f0']
    rows = []
    if d['inertia']:
        k = d['h_s'] * d['inertia_base_mva']
        rows.append({
            'key': 'inertia', 'label': 'Synthetic inertia',
            'peak_mw': 2.0 * k * d['rocof'] / f0 * d['f_max'] / f0,
            'energy_discharge_mj': k * (1.0 - (d['f_min'] / f0) ** 2),
            'energy_charge_mj': k * ((d['f_max'] / f0) ** 2 - 1.0),
            'basis': (f"H = {d['h_s']:g} s on {d['inertia_base_mva']:.0f} MVA "
                      f"({'plant rated power' if d['inertia_base_kind'] == 'plant' else 'STATCOM rating'}), "
                      f"RoCoF {d['rocof']:g} Hz/s, {d['f_min']:g} to {d['f_max']:g} Hz")})
    if d['phase_jump']:
        e = phase_jump_mw * d['phase_tau']
        rows.append({
            'key': 'phase_jump', 'label': 'Phase jump (voltage source behaviour)',
            'peak_mw': phase_jump_mw, 'energy_discharge_mj': e, 'energy_charge_mj': e,
            'basis': f"{d['phase_deg']:g}° step, decaying with {d['phase_tau']:g} s"})
    if d['damping']:
        e = d['damping_mw'] / (math.pi * d['damping_hz'])
        rows.append({
            'key': 'damping', 'label': 'Power oscillation damping',
            'peak_mw': d['damping_mw'], 'energy_discharge_mj': e, 'energy_charge_mj': e,
            'basis': f"±{d['damping_mw']:.1f} MW at {d['damping_hz']:g} Hz (energy of one half cycle)"})
    if d['support']:
        def _power(f_end):
            dev = max(abs(f_end - f0) - d['deadband_hz'], 0.0)
            if abs(f_end - f0) <= max(d['activation_hz'], d['deadband_hz']):
                return 0.0
            return min(dev / f0 / d['droop'] * d['plant_mw'], d['support_cap_mw'])
        p_dn, p_up = _power(d['f_min']), _power(d['f_max'])
        rows.append({
            'key': 'support', 'label': 'Frequency support (FSM / LFSM bridging)',
            'peak_mw': max(p_dn, p_up),
            'energy_discharge_mj': p_dn * d['support_time'], 'energy_charge_mj': p_up * d['support_time'],
            'basis': (f"droop {d['droop'] * 100:g} %, deadband {d['deadband_hz'] * 1000:g} mHz, limited to "
                      f"{d['support_cap_mw']:.1f} MW for {d['support_time']:g} s")})
    return rows


# --------------------------------------------------------------------------- supercapacitor bank

def read_bank(params):
    p = params or {}
    v_max = max(_num(p.get('bank_vmax_v'), 1500.0), 10.0)
    v_min_pct = min(max(_num(p.get('bank_vmin_percent'), 50.0), 5.0), 95.0)
    return {
        'cell_f': max(_num(p.get('cell_capacitance_f'), 3000.0), 1e-3),
        'cell_v': max(_num(p.get('cell_voltage_v'), 2.7), 0.1),
        'cell_esr_ohm': max(_num(p.get('cell_esr_mohm'), 0.29), 0.0) / 1000.0,
        'cell_imax_a': max(_num(p.get('cell_max_current_a'), 1900.0), 1.0),
        'v_max': v_max,
        'v_min': v_max * v_min_pct / 100.0,
        'eol_c': min(max(_num(p.get('eol_capacitance_percent'), 80.0), 10.0), 100.0) / 100.0,
        'eol_esr': max(_num(p.get('eol_esr_percent'), 200.0), 100.0) / 100.0,
        'eta': min(max(_num(p.get('efficiency_percent'), 97.0), 50.0), 100.0) / 100.0,
        'margin': max(_num(p.get('design_margin_percent'), 10.0), 0.0) / 100.0,
    }


def simulate_bank(p_ac_mw, c_f, r_ohm, v0, eta):
    """Bank voltage for an AC power profile (MW, + = discharge). Returns None when it cannot follow.

    ``c_f`` and ``r_ohm`` describe the whole bank (capacitance behind a series resistance).
    Returns ``(v_terminal, i_total, e_stored_mj)``.
    """
    n = len(p_ac_mw)
    v_t = np.empty(n)
    cur = np.empty(n)
    stored = np.empty(n)
    vc = v0
    for k in range(n):
        p = p_ac_mw[k] * 1e6
        p_dc = p / eta if p >= 0 else p * eta
        if r_ohm > 0:
            disc = vc * vc - 4.0 * r_ohm * p_dc
            if disc < 0 or vc <= 0:
                return None
            i = (vc - math.sqrt(disc)) / (2.0 * r_ohm)
        else:
            if vc <= 0:
                return None
            i = p_dc / vc
        v_t[k] = vc - i * r_ohm
        cur[k] = i
        stored[k] = 0.5 * c_f * vc * vc / 1e6
        vc -= i * DT / c_f
    return v_t, cur, stored


def size_bank(bank, profiles):
    """Smallest bank (parallel strings) that carries both events at end of life.

    ``profiles`` maps ``'under'`` / ``'over'`` to the AC power arrays.
    """
    n_series = int(math.ceil(bank['v_max'] / bank['cell_v'] - 1e-9))
    p_under, p_over = profiles['under'], profiles['over']
    # net AC energy drawn / returned, as a first guess of the split of the voltage window
    e_dis = max(float(np.max(np.cumsum(p_under) * DT)), 0.0) / bank['eta']
    e_chg = max(float(np.max(np.cumsum(-p_over) * DT)), 0.0) * bank['eta']
    e_total = e_dis + e_chg
    if e_total <= 0:
        raise _StudyError('No duty asks for active power, so there is nothing to size. Switch on at least '
                          'one duty with a value above zero.')
    win = bank['v_max'] ** 2 - bank['v_min'] ** 2
    c_string_eol = bank['cell_f'] / n_series * bank['eol_c']
    r_string_eol = bank['cell_esr_ohm'] * n_series * bank['eol_esr']
    n_par = max(1, int(math.floor(2.0 * e_total * 1e6 / win / c_string_eol)))
    peak_w = max(float(np.max(np.abs(p_under))), float(np.max(np.abs(p_over)))) * 1e6
    n_par = max(n_par, int(peak_w / bank['v_max'] / bank['cell_imax_a']))

    def attempt(n):
        c, r = c_string_eol * n, r_string_eol / n
        lo_ok = hi_ok = None
        # rest voltage: lowest that survives the discharge, highest that survives the charge
        a, b = bank['v_min'], bank['v_max']
        for _ in range(14):
            mid = 0.5 * (a + b)
            sim = simulate_bank(p_under, c, r, mid, bank['eta'])
            good = sim is not None and float(sim[0].min()) >= bank['v_min'] and \
                float(np.abs(sim[1]).max()) / n <= bank['cell_imax_a']
            if good:
                lo_ok, b = mid, mid
            else:
                a = mid
        if lo_ok is None:
            return None
        a, b = bank['v_min'], bank['v_max']
        for _ in range(14):
            mid = 0.5 * (a + b)
            sim = simulate_bank(p_over, c, r, mid, bank['eta'])
            good = sim is not None and float(sim[0].max()) <= bank['v_max'] and \
                float(np.abs(sim[1]).max()) / n <= bank['cell_imax_a']
            if good:
                hi_ok, a = mid, mid
            else:
                b = mid
        if hi_ok is None or hi_ok < lo_ok:
            return None
        return lo_ok, hi_ok

    found = None
    while n_par <= MAX_STRINGS:
        found = attempt(n_par)
        if found:
            break
        n_par = max(n_par + 1, int(math.ceil(n_par * 1.02)))
    if not found:
        raise _StudyError('No supercapacitor bank of a sensible size can carry these duties. Check the duty '
                          'values, the bank voltage window and the cell data.')
    n_min = n_par
    n_final = int(math.ceil(n_min * (1.0 + bank['margin'])))
    lo, hi = attempt(n_final) or found
    v_rest = 0.5 * (lo + hi)
    return {'n_series': n_series, 'n_parallel_min': n_min, 'n_parallel': n_final, 'v_rest': v_rest,
            'v_rest_low': lo, 'v_rest_high': hi,
            'c_eol_f': c_string_eol * n_final, 'r_eol_ohm': r_string_eol / n_final,
            'c_bol_f': bank['cell_f'] / n_series * n_final,
            'r_bol_ohm': bank['cell_esr_ohm'] * n_series / n_final}


def _downsample(arr, idx):
    return [round(float(v), 4) for v in np.asarray(arr)[idx]]


def sizing_core(params, plant_mw, statcom_mva, phase_jump_mw, f0=50.0):
    """Duties, event simulation and bank design. No network needed (used by the tests)."""
    d = read_duties(params, plant_mw, statcom_mva, f0)
    bank = read_bank(params)
    if not d['phase_jump']:
        phase_jump_mw = 0.0
    events = {'under': event_profile(d, +1, phase_jump_mw), 'over': event_profile(d, -1, phase_jump_mw)}
    if max(float(np.max(np.abs(ev['p_total']))) for ev in events.values()) < 1e-6:
        # no duty asks for active power: a plain STATCOM (reactive power only) is enough
        return {'duties_settings': d, 'storage_needed': False, 'duties': [],
                'requirement': {'peak_mw': 0.0, 'energy_discharge_mj': 0.0, 'energy_charge_mj': 0.0},
                'bank': None, 'events': {}}
    design = size_bank(bank, {k: v['p_total'] for k, v in events.items()})

    out_events = {}
    peak_mw = 0.0
    peak_cell_a = 0.0
    peak_loss_mw = 0.0
    energy = {}
    for key, ev in events.items():
        sim = simulate_bank(ev['p_total'], design['c_eol_f'], design['r_eol_ohm'], design['v_rest'], bank['eta'])
        v_t, cur, stored = sim
        n = len(ev['t'])
        idx = np.unique(np.linspace(0, n - 1, min(n, CHART_POINTS)).astype(int))
        # keep the sharp peaks visible after thinning
        idx = np.unique(np.concatenate([idx, [int(np.argmax(np.abs(ev['p_total']))), int(np.argmin(v_t)), int(np.argmax(v_t))]]))
        cum = np.cumsum(ev['p_total']) * DT
        energy[key] = float(np.max(cum if key == 'under' else -cum))
        peak_mw = max(peak_mw, float(np.max(np.abs(ev['p_total']))))
        peak_cell_a = max(peak_cell_a, float(np.max(np.abs(cur))) / design['n_parallel'])
        peak_loss_mw = max(peak_loss_mw, float(np.max(cur ** 2)) * design['r_eol_ohm'] / 1e6)
        out_events[key] = {
            't': _downsample(ev['t'], idx), 'f': _downsample(ev['f'], idx),
            'p_total': _downsample(ev['p_total'], idx), 'p_inertia': _downsample(ev['p_inertia'], idx),
            'p_phase': _downsample(ev['p_phase'], idx), 'p_damping': _downsample(ev['p_damping'], idx),
            'p_support': _downsample(ev['p_support'], idx),
            'v_bank': _downsample(v_t, idx), 'e_stored_mj': _downsample(stored, idx),
            'peak_mw': _r(float(np.max(np.abs(ev['p_total'])))),
            'v_low': _r(float(v_t.min()), 1), 'v_high': _r(float(v_t.max()), 1),
        }

    cells = design['n_series'] * design['n_parallel']
    win = bank['v_max'] ** 2 - bank['v_min'] ** 2
    return {
        'duties_settings': d,
        'storage_needed': True,
        'duties': [{**row, 'peak_mw': _r(row['peak_mw']), 'energy_discharge_mj': _r(row['energy_discharge_mj']),
                    'energy_charge_mj': _r(row['energy_charge_mj'])} for row in duty_table(d, phase_jump_mw)],
        'requirement': {'peak_mw': _r(peak_mw), 'energy_discharge_mj': _r(energy['under']),
                        'energy_charge_mj': _r(energy['over'])},
        'bank': {
            'cells_series': design['n_series'], 'strings': design['n_parallel'],
            'strings_without_margin': design['n_parallel_min'], 'cells_total': cells,
            'cell_capacitance_f': bank['cell_f'], 'cell_voltage_v': bank['cell_v'],
            'cell_esr_mohm': bank['cell_esr_ohm'] * 1000, 'cell_max_current_a': bank['cell_imax_a'],
            'v_max': _r(bank['v_max'], 1), 'v_min': _r(bank['v_min'], 1), 'v_rest': _r(design['v_rest'], 1),
            'v_rest_low': _r(design['v_rest_low'], 1), 'v_rest_high': _r(design['v_rest_high'], 1),
            'capacitance_new_f': _r(design['c_bol_f'], 2), 'capacitance_eol_f': _r(design['c_eol_f'], 2),
            'esr_new_mohm': _r(design['r_bol_ohm'] * 1000, 4), 'esr_eol_mohm': _r(design['r_eol_ohm'] * 1000, 4),
            'energy_rated_mj': _r(0.5 * design['c_bol_f'] * (design['n_series'] * bank['cell_v']) ** 2 / 1e6),
            'energy_usable_new_mj': _r(0.5 * design['c_bol_f'] * win / 1e6),
            'energy_usable_eol_mj': _r(0.5 * design['c_eol_f'] * win / 1e6),
            'peak_cell_current_a': _r(peak_cell_a, 1),
            'peak_bank_current_ka': _r(peak_cell_a * design['n_parallel'] / 1000, 3),
            'peak_loss_mw': _r(peak_loss_mw),
            'efficiency_percent': bank['eta'] * 100, 'eol_capacitance_percent': bank['eol_c'] * 100,
            'eol_esr_percent': bank['eol_esr'] * 100, 'design_margin_percent': bank['margin'] * 100,
        },
        'events': out_events,
    }


# --------------------------------------------------------------------------- network

def _friendly_map(in_data):
    return {str(e.get('name')): str(e.get('userFriendlyName') or e.get('name'))
            for e in in_data.values() if isinstance(e, dict) and e.get('name')}


def _build_net(in_data, x, f0):
    import pandapower as pp
    import pandapower_electrisim as pe
    with contextlib.redirect_stdout(io.StringIO()):
        net = pp.create_empty_network(f_hz=f0)
        busbars = pe.create_busbars(in_data, net)
        pe.create_other_elements(in_data, net, x, busbars)
    return net


def _find_statcom(net, ref):
    if not len(net.ssc):
        return None
    ref = str(ref or '').strip()
    if ref:
        for column in ('id', 'name'):
            if column in net.ssc.columns:
                hit = net.ssc.index[net.ssc[column].astype(str) == ref]
                if len(hit):
                    return int(hit[0])
    active = net.ssc.index[net.ssc.in_service.astype(bool)]
    return int(active[0] if len(active) else net.ssc.index[0])


def _grid_strength(net, buses):
    """Short-circuit power of the grid at ``buses`` (max and min case), converters excluded."""
    import pandapower.shortcircuit as sc
    import pandapower_electrisim as pe
    out = {int(b): {} for b in buses}
    warnings = []
    for case in ('max', 'min'):
        work = copy.deepcopy(net)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                pe._drop_dc_grid_for_sc(work)
                for table in ('sgen', 'storage'):
                    if table in work and len(work[table]):
                        work[table]['in_service'] = False
                if case == 'min':
                    if pe.sc_min_case_missing_grid_power(work):
                        warnings.append('The External Grid has no minimum short-circuit power, so the weakest-grid '
                                        'values are missing. Enter S"k min in the External Grid.')
                        continue
                    pe.ensure_line_endtemp_for_min_case(work)
                pe.ensure_gen_short_circuit_data(work, None)
                sc.calc_sc(work, fault='3ph', case=case, bus=[int(b) for b in buses], ip=False, ith=False,
                           check_connectivity=True, branch_results=False)
            for b in buses:
                row = work.res_bus_sc.loc[int(b)]
                vn = float(net.bus.at[int(b), 'vn_kv'])
                ikss = float(row['ikss_ka'])
                if not (ikss > 0):
                    continue
                skss = float(row['skss_mw']) if 'skss_mw' in row and math.isfinite(float(row['skss_mw'])) \
                    else math.sqrt(3) * vn * ikss
                rk = float(row['rk_ohm']) if 'rk_ohm' in row else float('nan')
                xk = float(row['xk_ohm']) if 'xk_ohm' in row else float('nan')
                if not (math.isfinite(xk) and xk > 0):
                    z = vn / (math.sqrt(3) * ikss)
                    rk, xk = 0.0, z
                out[int(b)][case] = {'sk_mva': skss, 'ik_ka': ikss, 'r_ohm': rk, 'x_ohm': xk}
        except Exception as exc:  # the sizing still runs without the grid strength
            warnings.append(f'The {"maximum" if case == "max" else "minimum"} short-circuit power of the grid '
                            f'could not be calculated ({exc}).')
    return out, warnings


def _operating_point(in_data, x, params, f0):
    import harmonic_operating_point as hop
    network = dict(in_data)
    lf = dict(params)
    lf['typ'] = 'PowerFlowPandaPower Parameters'
    lf.setdefault('algorithm', 'nr')
    lf.setdefault('calculate_voltage_angles', 'auto')
    lf.setdefault('initialization', 'auto')
    network[x] = lf
    return hop.controlled_operating_point(network, f0)


def _checklist(kind, ctx):
    """Requirement items of the chosen Grid Code set, each with what this design gives."""
    d = ctx['d']
    rows = []
    inertia_txt = (f"H = {d['h_s']:g} s on {d['inertia_base_mva']:.0f} MVA: up to {ctx['inertia_peak']:.1f} MW "
                   f"at {d['rocof']:g} Hz/s, {ctx['inertia_e']:.0f} MJ down to {d['f_min']:g} Hz") if d['inertia'] else None
    damping_txt = f"±{d['damping_mw']:.1f} MW at {d['damping_hz']:g} Hz" if d['damping'] else None
    conv = 'ok' if ctx['rating_ok'] else 'check'
    off = 'Duty switched off in this study'
    agreed = ('The connection conditions leave the values to be agreed with the Operator at the design stage; '
              'the numbers used here are your assumptions.')
    if kind == 'pse_grid_forming':
        rows.append({'item': '15.3 a)', 'requirement': 'Offshore wind farm: synthetic inertia',
                     'result': inertia_txt or off, 'status': conv if d['inertia'] else 'check'})
        rows.append({'item': '15.3 b)', 'requirement': 'Offshore wind farm: damping of oscillations',
                     'result': damping_txt or off, 'status': conv if d['damping'] else 'check'})
        vs = (f"Coupling reactance {ctx['x_pu']:.2f} p.u.; a {d['phase_deg']:g}° phase jump draws "
              f"{ctx['phase_mw']:.1f} MW at once") if d['phase_jump'] else off
        rows.append({'item': '15.4 a)', 'requirement': 'STATCOM in grid-forming mode: behaves as a voltage source',
                     'result': vs, 'status': conv if d['phase_jump'] else 'check'})
        rows.append({'item': '15.4 b)', 'requirement': 'STATCOM in grid-forming mode: synthetic inertia',
                     'result': inertia_txt or off, 'status': conv if d['inertia'] else 'check'})
        rows.append({'item': '15.4 c)', 'requirement': 'STATCOM in grid-forming mode: damping of oscillations',
                     'result': damping_txt or off, 'status': conv if d['damping'] else 'check'})
        rows.append({'item': '15.3 / 15.4', 'requirement': 'Detailed scope, control and activation of grid forming',
                     'result': agreed, 'status': 'info'})
    elif kind == 'pse_island':
        # These conditions put FSM / LFSM and island operation on the plant (turbines and park
        # controller). They ask for no grid forming, no synthetic inertia and no stored energy.
        extra = ''
        if d['support'] and ctx['storage']:
            extra = (f" Added by you: the STATCOM bridges up to {d['support_cap_mw']:.1f} MW "
                     f"for {d['support_time']:g} s.")
        rows.append({'item': '1.1', 'requirement': 'FSM capability as in NC RfG',
                     'result': 'Turbines and park controller.' + extra, 'status': 'plant'})
        rows.append({'item': '1.2', 'requirement': 'Island operation, NC RfG art. 15(5)(b)',
                     'result': ('Asked for in islands that keep inertia and short-circuit power from synchronous '
                                'machines; it may not be kept where the plant is the only source. No grid forming is asked for.'),
                     'status': 'plant'})
        rows.append({'item': '1.3.1', 'requirement': 'Voltage and reactive power control in island operation',
                     'result': (f"STATCOM and turbines, reactive power only: {ctx['q_reserved']:.0f} Mvar "
                                f"of the {ctx['rating']:.0f} MVA STATCOM in use"), 'status': conv})
        db_ok = d['deadband_hz'] <= 0.020 + 1e-9
        rows.append({'item': '1.3.2 to 1.3.4', 'requirement': 'FSM, LFSM-O and LFSM-U in island operation, deadband not above 20 mHz',
                     'result': ('Turbines and park controller, from synchronisation power to maximum power. '
                                f"Deadband entered here: {d['deadband_hz'] * 1000:g} mHz" +
                                ('' if db_ok else ' (above 20 mHz)') + '.' + extra),
                     'status': 'plant' if db_ok else 'check'})
        th_ok = 0.5 - 1e-9 <= d['activation_hz'] <= 1.0 + 1e-9 and abs(d['activation_delay'] - 1.0) < 1e-6
        rows.append({'item': '1.3.5', 'requirement': 'Automatic island mode at a frequency deviation of ±0.5 to ±1.0 Hz, 1 s delay',
                     'result': (f"Setting of the plant controller. Entered here: ±{d['activation_hz']:g} Hz, "
                                f"delay {d['activation_delay']:g} s."),
                     'status': 'plant' if th_ok else 'check'})
        rows.append({'item': '1.4', 'requirement': 'Black start (NC RfG art. 15(5)(a))',
                     'result': 'Not required', 'status': 'info'})
        sk = ctx.get('pcc_sk_min')
        rows.append({'item': '1.5', 'requirement': 'Minimum short-circuit power and inertia needed to start generation, to be given to the TSO',
                     'result': ((f"Model: S\"k min at the connection point {sk:,.0f} MVA. " if sk else '') +
                                'The turbine supplier states the minimum the turbines need.'),
                     'status': 'info'})
        rows.append({'item': 'Energy storage', 'requirement': 'Supercapacitors on the STATCOM',
                     'result': ('Not asked for by these conditions.' if not ctx['storage'] else
                                'Not asked for by these conditions; the bank below covers only the duties you switched on.'),
                     'status': 'info'})
    return rows


def _study(in_data, x):
    import pandapower_electrisim as pe
    import voltage_stability_electrisim as vs

    params = in_data[x]
    f0 = 60.0 if abs(_num(params.get('frequency'), 50.0) - 60.0) < 1 else 50.0
    net = _build_net(in_data, x, f0)
    not_ready = pe.network_not_ready_message(net, 'Grid-forming STATCOM sizing')
    if not_ready:
        raise _StudyError(not_ready)
    friendly = _friendly_map(in_data)
    warnings = []

    ssc_idx = _find_statcom(net, params.get('statcom_id'))
    if ssc_idx is None:
        raise _StudyError('Grid-forming STATCOM sizing needs a STATCOM on the diagram. Add a STATCOM (SSC), '
                          'connect it to a bus and try again.')
    ssc = net.ssc.loc[ssc_idx]
    ssc_bus = int(ssc['bus'])
    ssc_name = str(ssc['name'])
    vn = float(net.bus.at[ssc_bus, 'vn_kv'])
    rating_model = 0.0
    for col in ('q_max_mvar', 'q_min_mvar'):
        if col in net.ssc.columns:
            rating_model = max(rating_model, abs(_num(ssc[col], 0.0)))
    rating = _num(params.get('statcom_rating_mva'), 0.0)
    if rating <= 0:
        rating = rating_model
    if rating <= 0:
        raise _StudyError('The STATCOM has no reactive power rating. Enter Q max / Q min in the STATCOM, or type '
                          'the STATCOM rating in this dialog.')

    plant_mw = _num(params.get('plant_mw'), 0.0)
    plant_units = 0
    plant_mva = 0.0
    if len(net.sgen):
        active = net.sgen[net.sgen.in_service.astype(bool)]
        scaling = active['scaling'] if 'scaling' in active.columns else 1.0
        plant_units = int(len(active))
        model_mw = float((active['p_mw'] * scaling).sum())
        if 'sn_mva' in active.columns:
            plant_mva = float(active['sn_mva'].fillna(0).sum())
    else:
        model_mw = 0.0
    if plant_mw <= 0:
        plant_mw = model_mw
    if plant_mw <= 0:
        raise _StudyError('The diagram has no Static Generators in service, so the plant rated power is unknown. '
                          'Type the plant rated power in this dialog.')

    # reactive power the STATCOM carries in the solved model
    q_operating = None
    op_summary = {}
    try:
        op = _operating_point(in_data, x, params, f0)
        if op.get('ok'):
            q_operating = op['sscs'].get(ssc_name, {}).get('q_inject_mvar')
            op_summary = op.get('summary') or {}
            for w in op.get('warnings') or []:
                warnings.append(str(w))
        else:
            warnings.append(f"The load flow of the model did not solve ({op.get('error')}); the reactive power "
                            'of the STATCOM in normal operation is unknown.')
    except Exception as exc:
        warnings.append(f'The load flow of the model could not be run ({exc}).')

    q_mode = str(params.get('q_reserve_mode', 'load_flow')).strip().lower()
    if q_mode == 'full':
        q_reserved = rating
    elif q_mode == 'percent':
        q_reserved = min(max(_num(params.get('q_reserve_percent'), 50.0), 0.0), 100.0) / 100.0 * rating
    else:
        q_reserved = min(abs(q_operating), rating) if q_operating is not None else 0.0
        if q_operating is None:
            warnings.append('No reactive power is reserved in the converter check because the load flow gave none.')
    overload = max(_num(params.get('overload_pu'), 1.0), 0.1)

    # grid strength, turbines excluded
    pcc_bus = vs._resolve_bus(net, params.get('pcc_bus_id'))
    if pcc_bus is None and len(net.ext_grid):
        pcc_bus = int(net.ext_grid.bus.iloc[0])
    buses = [ssc_bus] + ([pcc_bus] if pcc_bus is not None and pcc_bus != ssc_bus else [])
    strength, sc_warnings = _grid_strength(net, buses)
    warnings.extend(sc_warnings)

    x_c = abs(_num(ssc.get('x_ohm'), 0.0))
    z_base = vn * vn / rating
    if x_c <= 0:
        x_c = 0.15 * z_base
        warnings.append('The STATCOM has no coupling reactance; 0.15 p.u. on its rating is used for the phase jump.')
    x_grid = strength.get(ssc_bus, {}).get('max', {}).get('x_ohm')
    if x_grid is None:
        x_grid = 0.0
        warnings.append('The grid reactance is unknown, so the phase-jump power counts the coupling reactance only.')
    phase_deg = min(max(_num(params.get('phase_jump_deg'), 10.0), 0.0), 90.0)
    phase_mw = vn * vn / (x_c + x_grid) * math.sin(math.radians(phase_deg))

    core = sizing_core(params, plant_mw, rating, phase_mw, f0)
    d = core.pop('duties_settings')
    peak = core['requirement']['peak_mw']
    required_rating = math.hypot(peak, q_reserved) / overload
    limit = rating * overload
    headroom = math.sqrt(max(limit * limit - q_reserved * q_reserved, 0.0))
    rating_ok = required_rating <= rating * 1.0005
    if core['storage_needed'] and q_mode not in ('full', 'percent') and q_operating is not None and abs(q_operating) >= 0.98 * rating:
        warnings.append(f'In the load flow of this model the STATCOM is at its reactive limit ({abs(q_operating):.0f} Mvar), '
                        'so nothing is left for active power. Check the voltage set point and the plant controller, '
                        'or choose a share of the rating to keep for reactive power.')

    def _bus_strength(bus):
        if bus is None:
            return None
        s = strength.get(int(bus), {})
        name = str(net.bus.at[int(bus), 'name'])
        out = {'bus': friendly.get(name, name), 'vn_kv': float(net.bus.at[int(bus), 'vn_kv'])}
        for case in ('max', 'min'):
            if case in s:
                out[f'sk_{case}_mva'] = _r(s[case]['sk_mva'], 1)
                out[f'x_{case}_ohm'] = _r(s[case]['x_ohm'], 3)
        return out

    grid_statcom = _bus_strength(ssc_bus)
    grid_pcc = _bus_strength(pcc_bus)
    for g, base in ((grid_statcom, rating), (grid_pcc, plant_mw)):
        if g:
            for case in ('max', 'min'):
                if g.get(f'sk_{case}_mva'):
                    g[f'scr_{case}'] = _r(g[f'sk_{case}_mva'] / base, 2)

    for g, what in ((grid_statcom, 'the STATCOM bus'), (grid_pcc, 'the connection point')):
        if g and g.get('scr_min') is not None and g['scr_min'] < 1.5:
            warnings.append(f"With the minimum short-circuit power of the External Grid the short-circuit ratio at {what} "
                            f"is only {g['scr_min']:g}. Check S\"k min in the External Grid; it may be a placeholder.")
            break
    kinetic = d['h_s'] * d['inertia_base_mva'] if d['inertia'] else 0.0
    inertia_row = next((r for r in core['duties'] if r['key'] == 'inertia'), None)
    kind = str(params.get('requirement_set', 'custom')).strip().lower()
    checklist = _checklist(kind, {
        'd': d, 'rating_ok': rating_ok, 'rating': rating, 'q_reserved': q_reserved, 'x_pu': x_c / z_base,
        'phase_mw': phase_mw, 'kinetic': kinetic,
        'inertia_peak': inertia_row['peak_mw'] if inertia_row else 0.0,
        'inertia_e': inertia_row['energy_discharge_mj'] if inertia_row else 0.0,
        'pcc_sk_min': (grid_pcc or {}).get('sk_min_mva'), 'storage': core['storage_needed'],
    })

    notes = [
        'The bank is sized at end of life (reduced capacitance, increased resistance) by simulating an '
        'under-frequency event (discharge) and an over-frequency event (charge) with all switched-on duties acting together.',
        'The grid short-circuit power is calculated with the turbines out of service: it is the strength the '
        'grid-forming STATCOM sees from the transmission system.',
        'The converter check adds the peak active power to the reserved reactive power as apparent power.',
        'This is a pre-design. The final rating follows from EMT studies with the manufacturer models and from '
        'the values agreed with the transmission system operator.',
    ]
    if not core['storage_needed']:
        notes = [
            'No duty that needs active power is switched on, so the STATCOM needs no energy store. '
            'The converter is checked for reactive power only.',
            'Switch on a duty in the dialog to see what a supercapacitor bank for it would look like.',
        ]
    return {
        'study': 'grid_forming_statcom_sizing',
        'requirement_set': kind,
        'frequency_hz': f0,
        'statcom': {
            'name': friendly.get(ssc_name, ssc_name),
            'bus': friendly.get(str(net.bus.at[ssc_bus, 'name']), str(net.bus.at[ssc_bus, 'name'])),
            'vn_kv': vn, 'rating_mva': _r(rating, 2), 'rating_from_model_mva': _r(rating_model, 2),
            'q_operating_mvar': _r(q_operating, 2), 'q_reserved_mvar': _r(q_reserved, 2),
            'overload_pu': overload, 'p_headroom_mw': _r(headroom, 2),
            'required_rating_mva': _r(required_rating, 1), 'rating_ok': rating_ok,
            'x_coupling_ohm': _r(x_c, 3), 'x_coupling_pu': _r(x_c / z_base, 3),
            'phase_jump_mw': _r(phase_mw, 2) if d['phase_jump'] else None,
        },
        'plant': {'p_mw': _r(plant_mw, 2), 'p_model_mw': _r(model_mw, 2), 's_mva': _r(plant_mva, 2), 'units': plant_units},
        'inertia': {
            'enabled': d['inertia'], 'h_s': d['h_s'], 'base_mva': _r(d['inertia_base_mva'], 2),
            'kinetic_energy_mws': _r(kinetic, 1),
            'h_on_plant_s': _r(kinetic / plant_mw, 3), 'h_on_statcom_s': _r(kinetic / rating, 3),
        },
        'grid': {'statcom_bus': grid_statcom, 'connection_point': grid_pcc},
        'operating_point': op_summary,
        'checklist': checklist,
        'warnings': warnings[:8],
        'notes': notes,
        **core,
    }


def grid_forming_statcom_study(in_data, x):
    """Run the sizing and return the result as a JSON string."""
    try:
        return json.dumps(_study(in_data, x), allow_nan=False, separators=(',', ':'))
    except _StudyError as exc:
        return json.dumps({'error': str(exc)})
    except Exception as exc:  # unexpected: still answer with a readable message
        return json.dumps({'error': f'Grid-forming STATCOM sizing failed: {exc}'})
