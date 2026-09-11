# -*- coding: utf-8 -*-
"""BESS charge/discharge reversal study: OpenDSS network + EPRI OpenDER IEEE 1547 inverter."""

import copy
import json
import math

import opendss_electrisim as ods
from storage_q_capability import interp_storage_pq_limits

try:
    import opendssdirect as dss
except ImportError:
    dss = None

_OPENDER_AVAILABLE = False
try:
    from opender import DER_BESS
    _OPENDER_AVAILABLE = True
except ImportError:
    DER_BESS = None


def _sf(val, default=0.0):
    try:
        if val is None or val == '':
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _downsample_series(time_s, series_dict, max_points=800):
    n = len(time_s)
    if n <= max_points:
        return time_s, series_dict
    step = max(1, int(math.ceil(n / max_points)))
    idx = list(range(0, n, step))
    if idx[-1] != n - 1:
        idx.append(n - 1)
    out_time = [time_s[i] for i in idx]
    out_series = {}
    for key, values in series_dict.items():
        out_series[key] = [values[i] for i in idx]
    return out_time, out_series


def _p_at_time(t, pre_hold_s, ramp_s, post_hold_s, p_start_mw, p_end_mw):
    """Electrisim sign: p_mw > 0 charge, p_mw < 0 discharge."""
    if t <= pre_hold_s:
        return p_start_mw
    t_ramp = t - pre_hold_s
    if t_ramp <= ramp_s:
        if ramp_s <= 0:
            return p_end_mw
        alpha = t_ramp / ramp_s
        return p_start_mw + alpha * (p_end_mw - p_start_mw)
    return p_end_mw


def _electrisim_p_to_opender_p_dem_pu(p_mw, p_max_mw):
    """OpenDER BESS: negative p_dem_pu = charge, positive = discharge."""
    if p_max_mw <= 0:
        return 0.0
    return -float(p_mw) / float(p_max_mw)


def _electrisim_q_from_opender_kvar(q_kvar):
    """Electrisim: +Q absorb, -Q inject."""
    return -float(q_kvar) / 1000.0


def _freq_scale_kwargs(frequency_hz):
    """Scale IEEE 1547 default 60 Hz trip/enter-service settings for 50 Hz plants."""
    f0 = float(frequency_hz or 50)
    if abs(f0 - 60.0) < 0.5:
        return {}
    scale = f0 / 60.0
    return {
        'ES_F_LOW': 59.5 * scale,
        'ES_F_HIGH': 60.1 * scale,
        'OF1_TRIP_F': 61.2 * scale,
        'UF1_TRIP_F': 58.5 * scale,
        'OF2_TRIP_F': 62.0 * scale,
        'UF2_TRIP_F': 57.0 * scale,
    }


def _pf_excitation(lagging):
    """OpenDER CONST_PF_EXCITATION: INJ = leading/capacitive, ABS = lagging/inductive."""
    return 'ABS' if lagging else 'INJ'


def _configure_opender_from_storage(storage_el, frequency_hz, olrt_s):
    """Build OpenDER DER_BESS kwargs from Electrisim Storage attributes."""
    sn_mva = _sf(storage_el.get('sn_mva'), 0.0)
    p_max_mw = abs(_sf(storage_el.get('p_mw'), sn_mva)) or sn_mva or 1.0
    if sn_mva <= 0:
        sn_mva = p_max_mw
    p_max_w = max(p_max_mw, sn_mva) * 1e6
    va_max_w = sn_mva * 1e6
    q_max_w = min(va_max_w * 0.5, p_max_w * 0.6)
    curve_lim = interp_storage_pq_limits(storage_el)
    if curve_lim is not None:
        q_mi, q_ma = curve_lim
        q_curve_mvar = max(abs(float(q_mi)), abs(float(q_ma)))
        if q_curve_mvar > 0:
            q_max_w = q_curve_mvar * 1e6

    bus_vn_kv = _sf(storage_el.get('vn_kv') or storage_el.get('kV'), 0.0)
    if bus_vn_kv <= 0:
        bus_vn_kv = 22.0
    ac_v_nom = bus_vn_kv * 1000.0

    soc_pct = _sf(storage_el.get('soc_percent'), 50.0)
    soc_init = max(0.0, min(1.0, soc_pct / 100.0))

    max_e_mwh = _sf(storage_el.get('max_e_mwh'), 0.0)
    bess_capacity_wh = max_e_mwh * 1e6 if max_e_mwh > 0 else p_max_mw * 1e6 * 2.0

    inv_mode = str(storage_el.get('inv_control_mode') or 'NONE').upper()
    olrt = max(0.1, _sf(olrt_s, 5.0))

    kwargs = {
        'NP_P_MAX': p_max_w,
        'NP_VA_MAX': va_max_w,
        'NP_P_MAX_CHARGE': p_max_w,
        'NP_APPARENT_POWER_CHARGE_MAX': va_max_w,
        'NP_Q_MAX_INJ': q_max_w,
        'NP_Q_MAX_ABS': q_max_w,
        'NP_AC_V_NOM': ac_v_nom,
        'SOC_INIT': soc_init,
        'NP_BESS_CAPACITY': bess_capacity_wh,
        'STATUS_INIT': True,
        'PF_MODE_ENABLE': False,
        'PV_MODE_ENABLE': False,
        'QV_MODE_ENABLE': False,
        'CONST_PF_MODE_ENABLE': False,
        'CONST_Q_MODE_ENABLE': False,
        **_freq_scale_kwargs(frequency_hz),
    }

    watt_priority = str(storage_el.get('watt_priority', '')).lower() in ('true', '1', 'yes')
    if watt_priority:
        kwargs['NP_PRIO_OUTSIDE_MIN_Q_REQ'] = 'ACTIVE'

    if inv_mode == 'FIXED_PF':
        kwargs['CONST_PF_MODE_ENABLE'] = True
        kwargs['CONST_PF_RT'] = olrt
        kwargs['PF_MODE_ENABLE'] = False
    elif inv_mode == 'VOLTVAR':
        kwargs['QV_MODE_ENABLE'] = True
        kwargs['QV_OLRT'] = olrt
        kwargs['PF_MODE_ENABLE'] = False
        x_raw = str(storage_el.get('vv_xarray') or '0.92 0.98 1.02 1.08').split()
        y_raw = str(storage_el.get('vv_yarray') or '0.44 0 -0.44 -0.44').split()
        try:
            xs = [float(x) for x in x_raw[:4]]
            ys = [float(y) for y in y_raw[:4]]
            if len(xs) >= 4 and len(ys) >= 4:
                kwargs.update({
                    'QV_CURVE_V1': xs[0], 'QV_CURVE_Q1': ys[0],
                    'QV_CURVE_V2': xs[1], 'QV_CURVE_Q2': ys[1],
                    'QV_CURVE_V3': xs[2], 'QV_CURVE_Q3': ys[2],
                    'QV_CURVE_V4': xs[3], 'QV_CURVE_Q4': ys[3],
                })
        except (TypeError, ValueError):
            pass
    elif inv_mode == 'FIXED_Q':
        kwargs['CONST_Q_MODE_ENABLE'] = True
        kwargs['CONST_Q'] = _sf(storage_el.get('q_mvar'), 0.0) * 1e6 / max(va_max_w, 1.0)
        kwargs['CONST_Q_RT'] = olrt

    return kwargs, p_max_mw


def _update_opender_pf_modes(der, storage_el, p_mw):
    """Apply charge vs discharge PF when inverter mode is FIXED_PF."""
    if str(storage_el.get('inv_control_mode') or 'NONE').upper() != 'FIXED_PF':
        return
    charging = float(p_mw) > 0
    mag_raw = storage_el.get('pf_charge') if charging else storage_el.get('pf')
    if mag_raw is None or str(mag_raw).strip() == '':
        mag_raw = storage_el.get('pf', 1.0)
    mode = storage_el.get('pf_charge_q_mode') if charging else storage_el.get('pf_q_mode')
    if not mode:
        mode = 'lagging'
    try:
        pf_mag = abs(float(mag_raw))
    except (TypeError, ValueError):
        pf_mag = 1.0
    pf_mag = max(0.5, min(1.0, pf_mag))
    lagging = str(mode).lower() != 'leading'
    der.der_file.CONST_PF = pf_mag
    der.der_file.CONST_PF_EXCITATION = _pf_excitation(lagging)


def _resolve_bus_name(poc_ref, bus_map):
    ref = str(poc_ref or '').strip()
    if not ref:
        return None
    for key in (ref, ref.replace('#', '_'), ref.replace('_', '#')):
        if key in bus_map:
            return bus_map[key]
    sanitized = ods._sanitize_opendss_name(ref)
    return bus_map.get(sanitized, sanitized)


def _read_bus_v_pu(bus_name):
    """Read bus voltage magnitude in per-unit (aligned with OpenDSS load-flow helpers)."""
    try:
        dss.Circuit.SetActiveBus(str(bus_name))
        pu_values = dss.Bus.puVmagAngle()
        if pu_values:
            mags = [
                float(pu_values[i])
                for i in range(0, len(pu_values), 2)
                if math.isfinite(float(pu_values[i]))
            ]
            if mags:
                return float(sum(mags) / len(mags))
        vmag = dss.Bus.VMagAngle()
        kv_base = dss.Bus.kVBase()
        if not vmag or not kv_base or kv_base <= 0:
            return None
        phases = max(1, int(len(vmag) / 2))
        mags_v = [vmag[i * 2] for i in range(phases) if i * 2 < len(vmag)]
        if not mags_v:
            return None
        return float(sum(mags_v) / len(mags_v) / (kv_base * 1000.0))
    except Exception:
        return None


def _ensure_snapshot_voltages(execute_dss_command):
    """Energize the snapshot circuit before the time loop.

    OpenDSS leaves all bus voltages at zero when Vsource uses ``defaultvsource`` spectrum
    together with Storage in CHARGING EXTERNAL dispatch if Snapshot mode is set first.
    Fix the spectrum, solve once, then apply Snapshot solver settings."""
    try:
        execute_dss_command('Edit Vsource.source spectrum=default')
    except Exception:
        pass
    execute_dss_command('solve')
    execute_dss_command('set Mode=Snapshot')
    execute_dss_command('set Algorithm=Normal')
    execute_dss_command('set ControlMode=Static')
    execute_dss_command('set MaxIterations=100')
    execute_dss_command('set tolerance=0.0001')
    execute_dss_command('solve')


def _read_storage_terminal_pq_kw(storage_name):
    try:
        dss.Circuit.SetActiveElement(f'Storage.{storage_name}')
        powers = dss.CktElement.Powers()
        if not powers:
            return 0.0, 0.0
        p_kw = sum(powers[i * 2] for i in range(min(3, int(len(powers) / 2))))
        q_kvar = sum(powers[i * 2 + 1] for i in range(min(3, int(len(powers) / 2))))
        return float(p_kw), float(q_kvar)
    except Exception:
        return 0.0, 0.0


def _set_storage_dispatch(storage_name, kw, kvar, execute_dss_command, pct_stored=None):
    """Apply P/Q to OpenDSS Storage for a snapshot P-step.

    OpenDSS treats kW as signed (negative = charging, positive = discharging).
    TimeChargeTrig must be -1 or DEFAULT/clock logic re-enters CHARGE after P=0.
    """
    kw = float(kw)
    kvar = float(kvar)
    if kw > 1e-6:
        state = 'DISCHARGING'
    elif kw < -1e-6:
        state = 'CHARGING'
    else:
        state = 'IDLING'
    stored = ''
    if pct_stored is not None:
        stored = f' %stored={float(pct_stored)}'
    execute_dss_command(
        f'Edit Storage.{storage_name} DispMode=EXTERNAL TimeChargeTrig=-1 '
        f'ChargeTrigger=0 DischargeTrigger=0 State={state} kW={kw} kvar={kvar}{stored}'
    )
    # Re-assert after DispMode (OpenDSS may rewrite State on energy/dispatch properties).
    execute_dss_command(f'Storage.{storage_name}.State={state}')
    execute_dss_command(f'Storage.{storage_name}.kW={kw}')
    return state


def _electrisim_p_to_opendss_kw(p_mw):
    """Electrisim p_mw > 0 charge; OpenDSS kW > 0 discharge."""
    return -float(p_mw) * 1000.0


def _opendss_q_for_storage(storage_el, p_mw):
    """Fixed-PF Q for OpenDSS-only fallback (kvar, generator convention)."""
    inv_mode = str(storage_el.get('inv_control_mode') or 'NONE').upper()
    if inv_mode == 'FIXED_PF':
        charging = float(p_mw) > 0
        state = 'CHARGING' if charging else 'DISCHARGING'
        pf_suffix = ods._opendss_storage_fixed_pf_suffix(storage_el, state)
        if 'pf=' in pf_suffix:
            try:
                pf_val = float(pf_suffix.split('pf=')[1].strip())
                kw = abs(_electrisim_p_to_opendss_kw(p_mw))
                if kw == 0:
                    return 0.0
                pf_mag = min(0.999999, abs(pf_val))
                if pf_mag >= 0.999:
                    return 0.0
                q_mag = kw * math.tan(math.acos(pf_mag))
                return q_mag if pf_val >= 0 else -q_mag
            except (TypeError, ValueError):
                pass
    q_mvar = _sf(storage_el.get('q_mvar'), 0.0)
    return -q_mvar * 1000.0


def _build_circuit(in_data, frequency_hz):
    ods._reset_opendss_warnings()
    work = copy.deepcopy(in_data)
    opendss_commands = []

    def execute_dss_command(command):
        print(f"[OpenDSS BESS P-step] {command}")
        dss.Text.Command(command)
        opendss_commands.append(command)

    try:
        dss.Basic.ClearAll()
    except Exception:
        pass

    ext_scan = ods._prescan_external_grid(work)

    circuit_cmd = (
        ods._new_circuit_command(ext_scan) if ext_scan else f'New Circuit.ElectrisimBESS'
    )
    if 'basefreq=' not in circuit_cmd.lower():
        circuit_cmd = f'{circuit_cmd} basefreq={frequency_hz}'
    execute_dss_command(circuit_cmd)
    BusbarsDictVoltage, BusbarsDictConnectionToName = ods.create_busbars(work, dss, False, opendss_commands)
    element_dicts = ods.create_other_elements(
        work, dss, BusbarsDictVoltage, BusbarsDictConnectionToName, False, opendss_commands, execute_dss_command)
    StoragesDictId = element_dicts[13] if element_dicts and len(element_dicts) > 13 else {}
    return execute_dss_command, BusbarsDictConnectionToName, StoragesDictId


def bess_dispatch_reversal(in_data, params):
    """Time-domain BESS P ramp with POC voltage tracking."""
    if dss is None:
        return json.dumps({'error': True, 'message': 'OpenDSS (opendssdirect) is not installed on the server.'})

    storage_id = params.get('storage_id') or params.get('storageId') or ''
    poc_bus_id = params.get('poc_bus_id') or params.get('pocBusId') or ''
    p_start_mw = _sf(params.get('p_start_mw') or params.get('pStartMw'), 45.0)
    p_end_mw = _sf(params.get('p_end_mw') or params.get('pEndMw'), -45.0)
    pre_hold_s = max(0.0, _sf(params.get('pre_hold_s') or params.get('preHoldS'), 2.0))
    ramp_s = max(0.01, _sf(params.get('ramp_s') or params.get('rampS'), 10.0))
    post_hold_s = max(0.0, _sf(params.get('post_hold_s') or params.get('postHoldS'), 60.0))
    dt = max(0.01, _sf(params.get('dt'), 0.1))
    vmin_pu = _sf(params.get('vmin_pu') or params.get('vminPu'), 0.98)
    vmax_pu = _sf(params.get('vmax_pu') or params.get('vmaxPu'), 1.02)
    frequency_hz = _sf(params.get('frequency'), 50.0)
    olrt_s = _sf(params.get('olrt_s') or params.get('olrtS'), 5.0)
    engine = str(params.get('engine') or 'opender').lower()

    if engine == 'opender' and not _OPENDER_AVAILABLE:
        return json.dumps({
            'error': True,
            'message': 'OpenDER (pip install opender>=2.2.0) is not installed. Choose "OpenDSS only" or install opender on the backend.',
        })

    clean = {}
    for k, v in in_data.items():
        if not isinstance(v, dict):
            continue
        typ = str(v.get('typ', ''))
        if 'BessDispatchReversal' in typ:
            continue
        clean[k] = copy.deepcopy(v)

    storage_el = ods._dg_find_der_element(clean, storage_id, 'Storage')
    if storage_el is None:
        return json.dumps({
            'error': True,
            'message': f'Storage element not found (id={storage_id}). Select a Storage element on the canvas.',
        })

    storage_name = ods._sanitize_opendss_name(storage_el.get('name') or storage_el.get('userFriendlyName') or 'storage')
    storage_label = str(storage_el.get('userFriendlyName') or storage_el.get('name') or storage_name)
    soc_hold = _sf(storage_el.get('soc_percent'), 50.0)
    if soc_hold <= 1.0 or soc_hold >= 99.0:
        soc_hold = 50.0

    study_storage = copy.deepcopy(storage_el)
    study_storage['disp_mode'] = 'EXTERNAL'
    # Snapshot P-step: clock-based charging would snap the unit back to CHARGE after P=0.
    study_storage['time_charge_trig'] = -1
    study_storage['charge_trigger'] = 0
    study_storage['discharge_trigger'] = 0
    opender_inv_settings = copy.deepcopy(storage_el)
    if engine == 'opender':
        # Disable native OpenDSS InvControl; OpenDER owns P/Q in co-simulation.
        study_storage['inv_control_mode'] = 'NONE'
    study_storage['p_mw'] = p_start_mw
    storage_key = None
    for k, v in clean.items():
        if not isinstance(v, dict):
            continue
        if v is storage_el or v.get('id') == storage_el.get('id') or v.get('name') == storage_el.get('name'):
            storage_key = k
            break
    if storage_key is not None:
        clean[storage_key] = study_storage

    try:
        execute_dss_command, bus_map, storages_id_map = _build_circuit(clean, frequency_hz)
    except Exception as exc:
        return json.dumps({'error': True, 'message': f'Failed to build OpenDSS circuit: {exc}'})

    poc_bus_name = _resolve_bus_name(poc_bus_id, bus_map)
    if not poc_bus_name:
        for _n, bid in (storages_id_map or {}).items():
            if str(bid) == str(storage_id):
                break
        poc_bus_name = _resolve_bus_name(storage_el.get('bus'), bus_map)
    if not poc_bus_name:
        return json.dumps({'error': True, 'message': 'POC bus could not be resolved. Select a POC bus in the study dialog.'})

    der = None
    p_max_mw = abs(_sf(study_storage.get('sn_mva'), 50.0))
    if engine == 'opender':
        der_kwargs, p_max_mw = _configure_opender_from_storage(
            opender_inv_settings, frequency_hz, olrt_s)
        DER_BESS.t_s = dt
        der = DER_BESS(**der_kwargs)
        der.reinitialize()

    _ensure_snapshot_voltages(execute_dss_command)
    v_init = _read_bus_v_pu(poc_bus_name)
    if v_init is None or v_init <= 0.05:
        execute_dss_command('calcvoltagebases')
        _ensure_snapshot_voltages(execute_dss_command)
        v_init = _read_bus_v_pu(poc_bus_name)
    if v_init is None or v_init <= 0.05:
        return json.dumps({
            'error': True,
            'message': f'POC bus "{poc_bus_name}" has no valid voltage after initial power flow. Check external grid and connections.',
        })

    if engine == 'opender' and der is not None:
        warmup_steps = max(5, int(math.ceil(max(olrt_s, 1.0) / dt)))
        _set_storage_dispatch(
            storage_name,
            _electrisim_p_to_opendss_kw(p_start_mw),
            0.0,
            execute_dss_command,
            pct_stored=soc_hold,
        )
        execute_dss_command('solve')
        v_warm = _read_bus_v_pu(poc_bus_name) or v_init
        for _ in range(warmup_steps):
            _update_opender_pf_modes(der, opender_inv_settings, p_start_mw)
            der.update_der_input(
                v_pu=v_warm,
                p_dem_pu=_electrisim_p_to_opender_p_dem_pu(p_start_mw, p_max_mw),
                f=frequency_hz,
            )
            der.run()

    total_duration = pre_hold_s + ramp_s + post_hold_s
    n_steps = int(math.ceil(total_duration / dt)) + 1

    time_s = []
    v_poc = []
    p_mw_series = []
    q_mvar_series = []
    p_cmd_series = []
    warnings = list(getattr(ods, '_opendss_warnings', []) or [])

    if engine == 'opender':
        warnings.append(
            'OpenDER IEEE 1547 generic inverter model (RMS screening).'
        )

    converged_all = True
    v_last = v_init
    trip_warned = False
    for step in range(n_steps):
        t = step * dt
        if t > total_duration:
            break
        p_cmd_mw = _p_at_time(t, pre_hold_s, ramp_s, post_hold_s, p_start_mw, p_end_mw)
        p_cmd_series.append(p_cmd_mw)

        v_before = v_last

        kw_cmd = _electrisim_p_to_opendss_kw(p_cmd_mw)
        kvar = _opendss_q_for_storage(opender_inv_settings, p_cmd_mw)

        if engine == 'opender' and der is not None:
            _update_opender_pf_modes(der, opender_inv_settings, p_cmd_mw)
            p_dem_pu = _electrisim_p_to_opender_p_dem_pu(p_cmd_mw, p_max_mw)
            der.update_der_input(v_pu=v_before, p_dem_pu=p_dem_pu, f=frequency_hz)
            der.run()
            kw_der = float(der.p_out_kw or 0.0)
            kvar_der = float(der.q_out_kvar or 0.0)
            if der.der_status == 'Trip' and not trip_warned:
                warnings.append(
                    'OpenDER DER reported Trip during the study (often frequency/enter-service at 50 Hz). '
                    'Active power follows the P command; Q uses the Storage inverter settings.'
                )
                trip_warned = True
            # P-step screening: OpenDSS must follow the commanded P. OpenDER Q is used when
            # it is producing vars (Volt-VAR / PF); otherwise fall back to Storage PF/Q.
            kw = kw_cmd
            # Prefer Storage PF/Q setpoint; OpenDER Q only when it is actually producing vars.
            if abs(kvar_der) > max(1.0, 0.02 * abs(kw_cmd)):
                kvar = kvar_der
        else:
            kw = kw_cmd

        _set_storage_dispatch(storage_name, kw, kvar, execute_dss_command, pct_stored=soc_hold)
        execute_dss_command('solve')
        if not dss.Solution.Converged():
            converged_all = False
            warnings.append(f'OpenDSS did not converge at t={t:.1f}s.')

        v_after = _read_bus_v_pu(poc_bus_name)
        if v_after is not None and v_after > 0.05:
            v_last = v_after
        kw_meas, kvar_meas = _read_storage_terminal_pq_kw(storage_name)

        time_s.append(round(t, 4))
        v_poc.append(round(v_last, 6))
        # OpenDSS generator convention (+ discharge / + inject) → Electrisim (+ charge / + absorb).
        p_mw_series.append(round(-kw_meas / 1000.0, 4))
        q_mvar_series.append(round(-kvar_meas / 1000.0, 4))

    if not time_s:
        return json.dumps({'error': True, 'message': 'Simulation produced no time steps.'})

    v_min = min(v_poc)
    v_max = max(v_poc)
    v_init = v_poc[0]
    within_limits = (v_min >= vmin_pu - 1e-9) and (v_max <= vmax_pu + 1e-9)
    dv_from_nominal = max(abs(v_max - 1.0), abs(1.0 - v_min))
    dv_event = [abs(v - v_init) for v in v_poc]
    imax = max(range(len(dv_event)), key=lambda i: dv_event[i])
    dv_overshoot = dv_event[imax]
    t_peak_s = time_s[imax]
    if dv_overshoot < 5e-4:
        warnings.append(
            'POC voltage barely changed during the P ramp. The selected POC is likely the slack/source bus. '
            'Choose the plant HV / POC bus (not the External Grid bus) and re-run.'
        )

    ds_time, ds = _downsample_series(time_s, {
        'v_poc': v_poc,
        'p_mw': p_mw_series,
        'q_mvar': q_mvar_series,
        'p_cmd_mw': p_cmd_series,
    })

    result = {
        'error': False,
        'engine': engine,
        'converged': converged_all,
        'storage_name': storage_label,
        'poc_bus': poc_bus_name,
        'p_start_mw': p_start_mw,
        'p_end_mw': p_end_mw,
        'pre_hold_s': pre_hold_s,
        'ramp_s': ramp_s,
        'post_hold_s': post_hold_s,
        'dt': dt,
        'vmin_pu': vmin_pu,
        'vmax_pu': vmax_pu,
        'v_min': round(v_min, 6),
        'v_max': round(v_max, 6),
        'v_init': round(v_init, 6),
        'dv_from_nominal_pu': round(dv_from_nominal, 6),
        'dv_overshoot_pu': round(dv_overshoot, 6),
        't_peak_s': round(t_peak_s, 3),
        'within_limits': within_limits,
        'time': ds_time,
        'bus_voltage': [{'name': poc_bus_name, 'values': ds['v_poc']}],
        'p_mw': [{'name': storage_label, 'values': ds['p_mw']}],
        'q_mvar': [{'name': storage_label, 'values': ds['q_mvar']}],
        'p_cmd_mw': [{'name': 'P command', 'values': ds['p_cmd_mw']}],
        'warnings': warnings,
    }
    return json.dumps(result)
