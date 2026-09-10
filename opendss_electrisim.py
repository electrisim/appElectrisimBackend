import opendssdirect as dss
from typing import List, Optional
import math
import json
import re

from storage_q_capability import (
    resolve_storage_pq,
    interp_storage_pq_limits,
    _truthy as _storage_qcap_truthy,
)

# Output classes for OpenDSS results (similar to pandapower_electrisim.py structure)
class BusbarOut(object):
    def __init__(self, name: str, id: str, vm_pu: float, va_degree: float,
                 p_mw: float = None, q_mvar: float = None, pf: float = None, q_p: float = None,
                 vm_kv: float = None):
        self.name = name
        self.id = id
        self.vm_pu = vm_pu
        self.va_degree = va_degree
        self.p_mw = p_mw
        self.q_mvar = q_mvar
        self.pf = pf
        self.q_p = q_p
        self.vm_kv = vm_kv
                        
class BusbarsOut(object):
    def __init__(self, busbars: List[BusbarOut]):
        self.busbars = busbars

class BusbarScOut(object):
    """Short circuit bus result - compatible with Pandapower res_bus_sc format for frontend."""
    def __init__(self, name: str, id: str, ikss_ka: float, ip_ka: float, ith_ka: float, rk_ohm: float, xk_ohm: float):
        self.name = name
        self.id = id
        self.ikss_ka = ikss_ka
        self.ip_ka = ip_ka
        self.ith_ka = ith_ka
        self.rk_ohm = rk_ohm
        self.xk_ohm = xk_ohm

class LineOut(object):
    def __init__(self, name: str, id: str, p_from_mw: float, q_from_mvar: float, p_to_mw: float, q_to_mvar: float, i_from_ka: float, i_to_ka: float, loading_percent: float):          
        self.name = name
        self.id = id
        self.p_from_mw = p_from_mw
        self.q_from_mvar = q_from_mvar 
        self.p_to_mw = p_to_mw 
        self.q_to_mvar = q_to_mvar            
        self.i_from_ka = i_from_ka 
        self.i_to_ka = i_to_ka               
        self.loading_percent = loading_percent 
                       
class LinesOut(object):
    def __init__(self, lines: List[LineOut]):
        self.lines = lines

class ExternalGridOut(object):
    def __init__(self, name: str, id: str, p_mw: float, q_mvar: float, pf: float, q_p: float):        
        self.name = name
        self.id = id
        self.p_mw = p_mw
        self.q_mvar = q_mvar
        self.pf = pf
        self.q_p = q_p
                       
class ExternalGridsOut(object):
    def __init__(self, externalgrids: List[ExternalGridOut]):
        self.externalgrids = externalgrids

class GeneratorOut(object):
    def __init__(self, name: str, id: str, p_mw: float, q_mvar: float, va_degree: float, vm_pu: float):          
        self.name = name
        self.id = id
        self.p_mw = p_mw 
        self.q_mvar = q_mvar
        self.va_degree = va_degree
        self.vm_pu = vm_pu
                       
class GeneratorsOut(object):
    def __init__(self, generators: List[GeneratorOut]):
        self.generators = generators             

class StaticGeneratorOut(object):
    def __init__(self, name: str, id: str, p_mw: float, q_mvar: float):          
        self.name = name
        self.id = id
        self.p_mw = p_mw 
        self.q_mvar = q_mvar
                       
class StaticGeneratorsOut(object):
    def __init__(self, staticgenerators: List[StaticGeneratorOut]):
        self.staticgenerators = staticgenerators

class LoadOut(object):
    def __init__(self, name: str, id: str, p_mw: float, q_mvar: float,
                 p_set_mw: float = None, vm_pu: float = None):
        self.name = name
        self.id = id
        self.p_mw = p_mw
        self.q_mvar = q_mvar
        self.p_set_mw = p_set_mw
        self.vm_pu = vm_pu                       
                       
class LoadsOut(object):
    def __init__(self, loads: List[LoadOut]):
        self.loads = loads             

class TransformerOut(object):
    def __init__(self, name: str, id: str, i_hv_ka: float, i_lv_ka: float, loading_percent: float, 
                 p_hv_mw: float = 0.0, q_hv_mvar: float = 0.0, p_lv_mw: float = 0.0, q_lv_mvar: float = 0.0, 
                 pl_mw: float = 0.0, ql_mvar: float = 0.0):          
        self.name = name
        self.id = id           
        self.i_hv_ka = i_hv_ka 
        self.i_lv_ka = i_lv_ka
        self.loading_percent = loading_percent
        self.p_hv_mw = p_hv_mw
        self.q_hv_mvar = q_hv_mvar
        self.p_lv_mw = p_lv_mw
        self.q_lv_mvar = q_lv_mvar
        self.pl_mw = pl_mw
        self.ql_mvar = ql_mvar
                                                             
                       
class TransformersOut(object):
    def __init__(self, transformers: List[TransformerOut]):
        self.transformers = transformers

class Transformer3WOut(object):
    def __init__(self, name: str, id: str, i_hv_ka: float, i_mv_ka: float, i_lv_ka: float,
                 loading_percent: float, p_hv_mw: float = 0.0, q_hv_mvar: float = 0.0,
                 p_mv_mw: float = 0.0, q_mv_mvar: float = 0.0, p_lv_mw: float = 0.0, q_lv_mvar: float = 0.0):
        self.name = name
        self.id = id
        self.i_hv_ka = i_hv_ka
        self.i_mv_ka = i_mv_ka
        self.i_lv_ka = i_lv_ka
        self.loading_percent = loading_percent
        self.p_hv_mw = p_hv_mw
        self.q_hv_mvar = q_hv_mvar
        self.p_mv_mw = p_mv_mw
        self.q_mv_mvar = q_mv_mvar
        self.p_lv_mw = p_lv_mw
        self.q_lv_mvar = q_lv_mvar

class Transformers3WOut(object):
    def __init__(self, transformers3w: List[Transformer3WOut]):
        self.transformers3w = transformers3w

class ShuntOut(object):
    def __init__(self, name: str, id: str, p_mw: float, q_mvar: float, vm_pu: float):          
        self.name = name
        self.id = id
        self.p_mw = p_mw 
        self.q_mvar = q_mvar  
        self.vm_pu = vm_pu                          
                       
class ShuntsOut(object):
    def __init__(self, shunts: List[ShuntOut]):
        self.shunts = shunts              
                
class CapacitorOut(object):
    def __init__(self, name: str, id: str, p_mw: float, q_mvar: float, vm_pu: float):         
        self.name = name
        self.id = id
        self.p_mw = p_mw 
        self.q_mvar = q_mvar  
        self.vm_pu = vm_pu                          
                       
class CapacitorsOut(object):
    def __init__(self, capacitors: List[CapacitorOut]):
        self.capacitors = capacitors              

class StorageOut(object):
    def __init__(self, name: str, id: str, p_mw: float, q_mvar: float,
                 inv_control_mode: str = '', vm_pu: float = None, note: str = ''):
        self.name = name
        self.id = id
        self.p_mw = p_mw
        self.q_mvar = q_mvar
        self.inv_control_mode = inv_control_mode
        self.vm_pu = vm_pu
        self.note = note or ''                       
                       
class StoragesOut(object):
    def __init__(self, storages: List[StorageOut]):
        self.storages = storages

class PVSystemOut(object):
    def __init__(self, name: str, id: str, p_mw: float, q_mvar: float, vm_pu: float, va_degree: float, irradiance: float, temperature: float, inv_control_mode: str = ''):
        self.name = name
        self.id = id
        self.p_mw = p_mw
        self.q_mvar = q_mvar
        self.vm_pu = vm_pu
        self.va_degree = va_degree
        self.irradiance = irradiance
        self.temperature = temperature
        self.inv_control_mode = inv_control_mode

class PVSystemsOut(object):
    def __init__(self, pvsystems: List[PVSystemOut]):
        self.pvsystems = pvsystems              

# Helper functions for OpenDSS element creation
# Frontend sends simple mxCell_ names (mxCell_126, mxCell_129, etc.)
# Frontend now sends bus names in the correct format (mxCell_126)
# OpenDSS may convert bus names to 
def _sanitize_opendss_name(name):
    """Replace spaces with underscores so the name is safe in OpenDSS commands.
    OpenDSS uses spaces as parameter delimiters, so any space inside a bus or
    element name breaks the command string."""
    if name is None:
        return name
    return name.replace(' ', '_')


_opendss_warnings = []
# Requested storage dispatch (Electrisim / pandapower sign) for post-solve checks.
_opendss_storage_dispatch = {}


def _reset_opendss_warnings():
    global _opendss_warnings, _opendss_storage_dispatch
    _opendss_warnings = []
    _opendss_storage_dispatch = {}


def _opendss_warn(message):
    """Log a warning and collect it for the frontend response."""
    print(f"[OpenDSS] WARNING: {message}")
    _opendss_warnings.append(message)


# Per-shunt metadata (step table, discrete voltage control) filled while creating reactors.
_opendss_shunt_meta = {}


def _opendss_is_true(val):
    return val in (True, 'true', 'True', '1', 1)


def _opendss_float(val, default=0.0):
    try:
        if val is None or val == '':
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _opendss_storage_fixed_pf_suffix(element_data, storage_state):
    """Map Electrisim lagging/leading PF to OpenDSS Storage pf=.

    Electrisim: lagging = absorb Q, leading = inject Q.
    OpenDSS (generator convention): +pf produces vars, -pf absorbs vars while discharging.
    While charging, kW is negative so the sign is reversed to keep the same Q direction.
    """
    charging = storage_state == 'CHARGING'
    mag_raw = element_data.get('pf_charge') if charging else element_data.get('pf')
    if mag_raw is None or str(mag_raw).strip() == '':
        mag_raw = element_data.get('pf', 1.0)
    mode = element_data.get('pf_charge_q_mode') if charging else element_data.get('pf_q_mode')
    if not mode:
        mode = element_data.get('pf_q_mode') or 'lagging'
    try:
        pf_val = float(mag_raw)
    except (TypeError, ValueError):
        return ''
    if pf_val < 0:
        mode = 'leading'
        pf_mag = abs(pf_val)
    else:
        pf_mag = abs(pf_val)
    if not (0.5 <= pf_mag <= 1.0):
        return ''
    leading = str(mode).lower() == 'leading'
    if storage_state == 'DISCHARGING':
        pf_opendss = pf_mag if leading else -pf_mag
    elif storage_state == 'CHARGING':
        pf_opendss = -pf_mag if leading else pf_mag
    else:
        pf_opendss = pf_val
    return f' pf={pf_opendss}'


def _opendss_parse_shunt_characteristic_rows(raw_json):
    """Parse Electrisim [{'step','p_mw','q_mvar'}, ...] JSON the same way as pandapower."""
    if raw_json is None:
        return []
    try:
        if isinstance(raw_json, list):
            data = raw_json
        elif isinstance(raw_json, str):
            data = json.loads(raw_json.strip() or '[]')
        else:
            return []
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    by_step = {}
    for row in data:
        if not isinstance(row, dict):
            continue
        try:
            st = int(round(float(row.get('step', 0))))
            pm = float(row.get('p_mw', 0.0))
            qv = float(row.get('q_mvar', 0.0))
        except (TypeError, ValueError):
            continue
        by_step[st] = {'step': st, 'p_mw': pm, 'q_mvar': qv}
    return sorted(by_step.values(), key=lambda r: r['step'])


def _opendss_shunt_uses_zero_based(electrisim_step, characteristic_rows, line_flow_bands=None):
    """Mirrors pandapower's _electrisim_shunt_uses_zero_based so both solvers pick the same step."""
    try:
        if int(round(float(electrisim_step))) == 0:
            return True
    except (TypeError, ValueError):
        pass
    for r in characteristic_rows or []:
        try:
            if int(r.get('step', -1)) == 0:
                return True
        except (TypeError, ValueError):
            continue
    for b in line_flow_bands or []:
        try:
            if int(b.get('step', -1)) == 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _opendss_shunt_step_to_pp(step_val, zero_based):
    try:
        s = int(round(float(step_val)))
    except (TypeError, ValueError):
        s = 1
    if zero_based:
        return max(1, s + 1)
    return max(1, s)


def _opendss_shunt_max_step_to_pp(max_step, zero_based):
    try:
        m = int(round(float(max_step)))
    except (TypeError, ValueError):
        m = 1
    return max(1, m + 1) if zero_based else max(1, m)


def _opendss_shunt_nominals_for_step(rows, step_val, p_fallback, q_fallback):
    try:
        si = int(round(float(step_val)))
    except (TypeError, ValueError):
        si = 1
    for r in rows or []:
        if int(r['step']) == si:
            return float(r['p_mw']), float(r['q_mvar'])
    return p_fallback, q_fallback


def _opendss_shunt_pq_at_pp_step(spec, step_pp):
    """Nominal P [MW], Q [MVAr] at 1.0 pu for a pandapower-style step index."""
    p_fb = spec.get('p_fallback', 0.0)
    q_fb = spec.get('q_fallback', 0.0)
    rows = spec.get('characteristic_rows') or []
    if spec.get('use_characteristic') and rows:
        el_step = (step_pp - 1) if spec.get('zero_based') else step_pp
        return _opendss_shunt_nominals_for_step(rows, el_step, p_fb, q_fb)
    return p_fb * float(step_pp), q_fb * float(step_pp)


def _opendss_busbar_vn_kv(BusbarsDictVoltage, bus_name):
    if not bus_name or not BusbarsDictVoltage:
        return None
    if bus_name in BusbarsDictVoltage:
        return BusbarsDictVoltage[bus_name]
    lower = str(bus_name).lower()
    for key, val in BusbarsDictVoltage.items():
        if str(key).lower() == lower:
            return val
    return None


def _opendss_read_bus_vm_pu(dss_mod, bus_name, BusbarsDictVoltage):
    """Positive-sequence L-L voltage in pu after a solve."""
    if not bus_name:
        return None
    try:
        dss_mod.Circuit.SetActiveBus(str(bus_name))
        voltages = dss_mod.Bus.Voltages()
        if voltages is None or len(voltages) < 6:
            return None
        va = complex(voltages[0] / 1000.0, voltages[1] / 1000.0)
        vb = complex(voltages[2] / 1000.0, voltages[3] / 1000.0)
        vc = complex(voltages[4] / 1000.0, voltages[5] / 1000.0)
        a = complex(-0.5, math.sqrt(3) / 2.0)
        a2 = complex(-0.5, -math.sqrt(3) / 2.0)
        v1 = (va + a * vb + a2 * vc) / 3.0
        v1_ll_kv = abs(v1) * math.sqrt(3)
        try:
            base_ln = float(dss_mod.Bus.kVBase())
            if base_ln > 0:
                return v1_ll_kv / (base_ln * math.sqrt(3))
        except (TypeError, ValueError):
            pass
        base_kv = _opendss_busbar_vn_kv(BusbarsDictVoltage, bus_name)
        if base_kv and float(base_kv) > 0:
            return v1_ll_kv / float(base_kv)
    except Exception:
        return None
    return None


def _opendss_shunt_rp_ohms(bus_voltage_kv, p_mw):
    if bus_voltage_kv is None or p_mw is None or p_mw <= 0:
        return None
    v_volts = float(bus_voltage_kv) * 1000.0
    p_watts = float(p_mw) * 1e6
    if p_watts <= 0:
        return None
    return (v_volts ** 2) / p_watts


def _opendss_apply_shunt_rating(execute_dss_command, spec, p_mw, q_mvar):
    """Update an existing Reactor/Capacitor to the nominal P/Q at 1.0 pu."""
    reactor_name = spec.get('reactor_name')
    bus_voltage = spec.get('bus_voltage')
    if not reactor_name:
        return
    q_kvar = float(q_mvar) * 1000.0
    prefix = spec.get('dss_class', 'Reactor')
    if abs(q_kvar) < 1.0:
        execute_dss_command(f'{prefix}.{reactor_name}.enabled=no')
        return
    execute_dss_command(f'{prefix}.{reactor_name}.enabled=yes')
    rp = _opendss_shunt_rp_ohms(bus_voltage, p_mw)
    if q_kvar >= 0:
        cmd = f'Edit Reactor.{reactor_name} kvar={q_kvar:.0f}'
        if rp is not None:
            cmd += f' Rp={rp:.2f}'
        execute_dss_command(cmd)
    else:
        execute_dss_command(f'Edit Capacitor.{reactor_name} kvar={abs(q_kvar):.0f}')


def _opendss_apply_discrete_shunt_control(dss_mod, execute_dss_command, BusbarsDictVoltage, max_iters=20):
    """
    Approximate pandapower DiscreteShuntController: step shunt Q to drive bus voltage
    toward vm_set_pu. Positive q_mvar is inductive (higher step lowers voltage).
    """
    specs = [m for m in _opendss_shunt_meta.values() if m.get('discrete_shunt_control')]
    if not specs:
        return
    for _ in range(max_iters):
        changed = False
        for spec in specs:
            vm = _opendss_read_bus_vm_pu(dss_mod, spec.get('bus_name'), BusbarsDictVoltage)
            if vm is None:
                continue
            vm_set = float(spec.get('vm_set_pu', 1.0))
            tol = float(spec.get('tol', 1e-3))
            increment = int(spec.get('increment', 1) or 1)
            if increment < 1:
                increment = 1
            step = int(spec.get('step', 1))
            max_step = int(spec.get('max_step', 1) or 1)
            min_step = 1
            p_now, q_now = _opendss_shunt_pq_at_pp_step(spec, step)
            q_sign = 1.0 if q_now >= 0 else -1.0
            if vm > vm_set + tol:
                new_step = step + increment if q_sign >= 0 else step - increment
            elif vm < vm_set - tol:
                new_step = step - increment if q_sign >= 0 else step + increment
            else:
                continue
            new_step = max(min_step, min(max_step, new_step))
            if new_step == step:
                continue
            spec['step'] = new_step
            p_mw, q_mvar = _opendss_shunt_pq_at_pp_step(spec, new_step)
            _opendss_apply_shunt_rating(execute_dss_command, spec, p_mw, q_mvar)
            changed = True
        if not changed:
            break
        execute_dss_command('solve')


def _opendss_circuit_has_usable_solution(dss_mod):
    """Finite slack power and finite voltages (Newton can miss Converged() at MaxIterations)."""
    try:
        total = dss_mod.Circuit.TotalPower()
        if not total or not math.isfinite(float(total[0])):
            return False
        buses = dss_mod.Circuit.AllBusNames() or []
        for bname in buses[:3]:
            dss_mod.Circuit.SetActiveBus(bname)
            v = dss_mod.Bus.Voltages()
            if not v:
                return False
            if not math.isfinite(float(v[0])):
                return False
        return True
    except Exception:
        return False


def _opendss_circuit_converged(dss_mod):
    """
    Whether the snapshot result can be reported. OpenDSS can stop at MaxIterations with
    Converged()=False on an operating point that is already valid, so finite voltages and
    slack power decide here; a diverged solve leaves NaN behind and is rejected.
    """
    return _opendss_circuit_has_usable_solution(dss_mod)


def _opendss_set_all_generator_vminpu(execute_dss_command, generators_dict, vminpu):
    for gen_name in (generators_dict or {}):
        if not gen_name:
            continue
        execute_dss_command(f'Edit Generator.{gen_name} Vminpu={float(vminpu):.3f}')


def _opendss_snapshot_solve_plans(algorithm, max_iterations):
    """
    Ordered snapshot attempts. A diverged solve leaves NaN in the node voltages and
    OpenDSS has no executive command to clear them, so every fallback here is applied
    to a freshly rebuilt circuit rather than to the failed one.
    """
    try:
        requested_iters = int(float(max_iterations))
    except (TypeError, ValueError):
        requested_iters = 100
    retry_iters = max(200, requested_iters)
    requested = str(algorithm or 'Normal')
    candidates = [
        (requested, requested_iters, None),
        # Newton at the requested iteration count first: a longer run can walk a
        # marginal case away from the finite iterate this one stops at.
        ('Newton', requested_iters, None),
        ('Newton', retry_iters, None),
        ('Newton', retry_iters, 0.90),
    ]
    plans = []
    seen = set()
    for algo, iters, vminpu in candidates:
        key = (algo.lower(), iters, vminpu)
        if key in seen:
            continue
        seen.add(key)
        label = f'{algo}, MaxIterations={iters}'
        if vminpu is not None:
            label += f', generator Vminpu={vminpu:.2f}'
        plans.append({'label': label, 'algorithm': algo,
                      'max_iterations': iters, 'gen_vminpu': vminpu})
    return plans


def _opendss_solve_snapshot_plan(dss_mod, execute_dss_command, plan, generators_dict=None):
    """Solve a freshly built circuit for one plan; Vminpu plans relax then restore PQ behaviour."""
    vminpu = plan.get('gen_vminpu')
    if vminpu is not None and generators_dict:
        _opendss_set_all_generator_vminpu(execute_dss_command, generators_dict, vminpu)
    execute_dss_command('solve')
    if vminpu is not None and generators_dict and _opendss_circuit_has_usable_solution(dss_mod):
        _opendss_set_all_generator_vminpu(execute_dss_command, generators_dict, 0.50)
        execute_dss_command('solve')
    return _opendss_circuit_converged(dss_mod)


def _opendss_parse_line_flow_step_table(raw_json):
    """[{p_mw_min, p_mw_max, step}, ...] — same rules as pandapower line-flow bands."""
    if raw_json is None:
        return []
    try:
        if isinstance(raw_json, list):
            data = raw_json
        elif isinstance(raw_json, str):
            data = json.loads(raw_json.strip() or '[]')
        else:
            return []
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    out = []
    for row in data:
        if not isinstance(row, dict):
            continue
        try:
            out.append({
                'p_mw_min': float(row.get('p_mw_min', 0)),
                'p_mw_max': float(row.get('p_mw_max', 0)),
                'step': int(row.get('step', 0)),
            })
        except (TypeError, ValueError):
            continue
    out.sort(key=lambda r: (r['p_mw_min'], r['p_mw_max']))
    return out


def _opendss_line_flow_pick_step(bands, p_mw):
    if not bands:
        return 0
    try:
        pv = float(p_mw)
    except (TypeError, ValueError):
        pv = 0.0
    if pv < float(bands[0]['p_mw_min']):
        return int(bands[0]['step'])
    if pv > float(bands[-1]['p_mw_max']):
        return int(bands[-1]['step'])
    n = len(bands)
    for i, b in enumerate(bands):
        lo = float(b['p_mw_min'])
        hi = float(b['p_mw_max'])
        st = int(b['step'])
        if i == n - 1:
            if lo <= pv <= hi:
                return st
        elif lo <= pv < hi:
            return st
    return int(bands[-1]['step'])


def _opendss_find_line_name(ref, LinesDict, LinesDictId):
    if not ref:
        return None
    ref_s = str(ref).strip()
    if not ref_s:
        return None
    if LinesDict and ref_s in LinesDict:
        return LinesDict[ref_s]
    san = _sanitize_opendss_name(ref_s)
    if LinesDict and san in LinesDict:
        return LinesDict[san]
    for name, lid in (LinesDictId or {}).items():
        if str(lid) == ref_s or _sanitize_opendss_name(str(lid)) == san:
            return (LinesDict or {}).get(name, name)
    return None


def _opendss_line_p_mw(dss_mod, line_name, p_reference='p_from_mw', use_abs=True):
    dss_mod.Circuit.SetActiveElement(f'Line.{line_name}')
    powers = dss_mod.CktElement.Powers() or []
    n_cond = dss_mod.CktElement.NumConductors()
    n_ph = dss_mod.CktElement.NumPhases()
    term = 1 if str(p_reference or '').lower() == 'p_to_mw' else 0
    p_kw, _q = _opendss_terminal_pq_kw(powers, term, n_cond, n_ph)
    p_mw = p_kw / 1000.0
    if use_abs:
        p_mw = abs(p_mw)
    return p_mw


def _opendss_apply_line_flow_shunt_control(dss_mod, execute_dss_command, LinesDict, LinesDictId, max_iters=3):
    """
    Match pandapower line_flow_step_control: map monitored line P to shunt step.
    Pandapower attaches this even when DiscreteShuntController is off.
    """
    specs = [m for m in _opendss_shunt_meta.values() if m.get('line_flow_step_control')]
    if not specs:
        return
    for _ in range(max_iters):
        changed = False
        for spec in specs:
            line_name = _opendss_find_line_name(
                spec.get('line_flow_reference_line_id'), LinesDict, LinesDictId)
            bands = spec.get('line_flow_bands') or []
            if not line_name or not bands:
                continue
            try:
                p_mw = _opendss_line_p_mw(
                    dss_mod, line_name,
                    spec.get('line_flow_p_reference') or 'p_from_mw',
                    spec.get('line_flow_p_use_abs', True),
                )
            except Exception as ex:
                print(f"[OpenDSS] Line-flow shunt: could not read line '{line_name}': {ex}")
                continue
            el_step = _opendss_line_flow_pick_step(bands, p_mw)
            step_pp = _opendss_shunt_step_to_pp(el_step, spec.get('zero_based'))
            if int(step_pp) == int(spec.get('step') or 0):
                continue
            spec['step'] = int(step_pp)
            p_now, q_now = _opendss_shunt_pq_at_pp_step(spec, step_pp)
            print(
                f"[OpenDSS] Line-flow shunt {spec.get('reactor_name')}: "
                f"|P|={p_mw:.2f} MW -> step {el_step} (Q={q_now} MVAr)"
            )
            _opendss_apply_shunt_rating(execute_dss_command, spec, p_now, q_now)
            changed = True
        if not changed:
            break
        execute_dss_command('solve')


def _format_opendss_bus_terminal(bus_name, phase=1, conn='wye'):
    """Return OpenDSS bus string with node notation, e.g. 'Bus5.1' or 'Bus5.1.2'."""
    try:
        p = int(phase)
    except (TypeError, ValueError):
        p = 1
    if p < 1 or p > 3:
        p = 1
    c = (conn or 'wye').strip().lower()
    if c == 'delta':
        p2 = 1 if p >= 3 else p + 1
        return f"{bus_name}.{p}.{p2}"
    return f"{bus_name}.{p}"


def _resolve_1ph_kv(bus_voltage_ll, conn='wye', explicit_kv=None):
    """Rated kV for single-phase OpenDSS elements."""
    if explicit_kv not in (None, '', '0'):
        try:
            return float(explicit_kv)
        except (TypeError, ValueError):
            pass
    try:
        v = float(bus_voltage_ll)
    except (TypeError, ValueError):
        return 0.0
    if v <= 0:
        return v
    if (conn or 'wye').strip().lower() == 'delta':
        return v
    return v / math.sqrt(3)


def _element_phase_conn(element_data):
    try:
        phase = int(element_data.get('phase', 1) or 1)
    except (TypeError, ValueError):
        phase = 1
    if phase < 1 or phase > 3:
        phase = 1
    conn = (element_data.get('conn') or 'wye').strip().lower()
    if conn not in ('wye', 'delta'):
        conn = 'wye'
    return phase, conn

def _resolve_load_1ph_kv(bus_voltage_ll, conn, explicit_kv=None):
    """Rated kV for OpenDSS Load (phases=1). Explicit kV from UI is often L-L bus vn_kv."""
    if explicit_kv not in (None, '', '0'):
        kv = float(explicit_kv)
    else:
        return _resolve_1ph_kv(bus_voltage_ll, conn, None)
    conn_l = (conn or 'wye').strip().lower()
    try:
        v_ll = float(bus_voltage_ll)
    except (TypeError, ValueError):
        return kv
    if conn_l == 'wye' and v_ll > 0 and abs(kv - v_ll) / v_ll < 0.25:
        return v_ll / math.sqrt(3)
    return kv


def _opendss_ckt_pq_mw(powers, terminal_index=0):
    """Extract P/Q in MW/MVAr for any element terminal (1ph or 3ph)."""
    if not powers or len(powers) < 2:
        return 0.0, 0.0
    try:
        n_conductors = dss.CktElement.NumConductors()
        n_phases = dss.CktElement.NumPhases()
    except Exception:
        n_conductors = 0
        n_phases = 3
    p_kw, q_kvar = _opendss_terminal_pq_kw(powers, terminal_index, n_conductors, n_phases)
    p_mw = p_kw / 1000.0 if not math.isnan(p_kw) else 0.0
    q_mvar = q_kvar / 1000.0 if not math.isnan(q_kvar) else 0.0
    return p_mw, q_mvar


def _collect_voltage_bases_from_in_data(in_data, BusbarsDictVoltage):
    """Build OpenDSS voltagebases list from buses and equipment rated voltages."""
    levels = set()
    for v in (BusbarsDictVoltage or {}).values():
        try:
            fv = float(v)
            if fv > 0:
                levels.add(fv)
        except (TypeError, ValueError):
            pass
    for elem in in_data.values():
        typ = elem.get('typ', '')
        for key in ('vn_kv', 'vn_hv_kv', 'vn_lv_kv', 'vn_mv_kv', 'kV', 'kv'):
            raw = elem.get(key)
            if raw in (None, '', '0'):
                continue
            try:
                fv = float(raw)
                if fv > 0:
                    levels.add(fv)
            except (TypeError, ValueError):
                pass
    return sorted(levels, reverse=True)

def _resolve_external_grid_basekv(in_data, bus_basekv):
    """Use transformer HV rating when slack bus vn_kv was imported at LV level."""
    try:
        bus_kv = float(bus_basekv)
    except (TypeError, ValueError):
        bus_kv = 110.0
    hv_levels = []
    for elem in in_data.values():
        typ = elem.get('typ', '')
        if not (typ.startswith('Transformer') or typ.startswith('Two Winding')):
            continue
        try:
            hv = float(elem.get('vn_hv_kv') or 0)
            if hv > 0:
                hv_levels.append(hv)
        except (TypeError, ValueError):
            pass
    if hv_levels and bus_kv < max(hv_levels):
        return max(hv_levels)
    return bus_kv


def _thevenin_impedance_ohm(vn_kv_ll, s_sc_mva, rx, r0x0=None, s_sc_min_mva=None):
    """Pandapower-compatible Thevenin R/X in Ohm (|Z| = vn_kv^2 / s_sc_mva, rx = R/X)."""
    import math
    vn = float(vn_kv_ll)
    s_sc = float(s_sc_mva)
    rx = float(rx)
    if vn <= 0 or s_sc <= 0.1 or rx <= 0:
        return None
    z = (vn ** 2) / s_sc
    x = z / math.sqrt(1.0 + rx * rx)
    r = rx * x
    if r0x0 and float(r0x0) > 0 and s_sc_min_mva and float(s_sc_min_mva) > 0.1:
        z0 = (vn ** 2) / float(s_sc_min_mva)
        r0x0f = float(r0x0)
        x0 = z0 / math.sqrt(1.0 + r0x0f * r0x0f)
        r0 = r0x0f * x0
    else:
        r0, x0 = r, x
    return r, x, r0, x0


def _ext_grid_vsource_impedance(element_data, bus_voltage_ll):
    """Build OpenDSS Vsource impedance clause from external grid SC parameters."""
    try:
        s_sc_max = float(element_data.get('s_sc_max_mva') or 10000.0)
    except (TypeError, ValueError):
        s_sc_max = 10000.0
    try:
        rx_max = float(element_data.get('rx_max') or 0)
    except (TypeError, ValueError):
        rx_max = 0.0
    try:
        s_sc_min = float(element_data.get('s_sc_min_mva') or 0)
    except (TypeError, ValueError):
        s_sc_min = 0.0
    try:
        r0x0_max = float(element_data.get('r0x0_max') or 0)
    except (TypeError, ValueError):
        r0x0_max = 0.0

    thev = _thevenin_impedance_ohm(
        bus_voltage_ll, s_sc_max, rx_max, r0x0_max,
        s_sc_min if s_sc_min > 0.1 else None,
    )
    if thev is not None:
        r, x, r0, x0 = thev
        return (
            'thevenin',
            f" R1={r:.6f} X1={x:.6f} R0={r0:.6f} X0={x0:.6f}",
            None,
        )
    if s_sc_max <= 0.1:
        s_sc_max = 10000.0
    return 'mvasc3', '', s_sc_max


def _prescan_external_grid(in_data):
    """Read first External Grid or Source 1ph element for New Circuit / Vsource.source setup."""
    for _elem in in_data.values():
        typ = _elem.get('typ', '')
        if not (typ.startswith('External Grid') or typ.startswith('Source 1ph')):
            continue
        bus_ref = _elem.get('bus', '')
        ext_bus = _sanitize_opendss_name(bus_ref)
        try:
            ext_pu = float(_elem.get('vm_pu', 1.0) or 1.0)
        except (TypeError, ValueError):
            ext_pu = 1.0
        try:
            ext_angle = float(_elem.get('va_degree', 0) or 0)
        except (TypeError, ValueError):
            ext_angle = 0.0
        if ext_pu == 0:
            ext_pu = 1.0
        ext_basekv = None
        for _belem in in_data.values():
            if 'Bus' in _belem.get('typ', '') and _sanitize_opendss_name(_belem.get('name', '')) == ext_bus:
                ext_basekv = _resolve_external_grid_basekv(in_data, _belem.get('vn_kv', 110))
                break
        if ext_basekv is None:
            ext_basekv = 110.0
        mode, imp_suffix, mvasc3 = _ext_grid_vsource_impedance(_elem, ext_basekv)
        phases = 1 if typ.startswith('Source 1ph') else 3
        phase, conn = _element_phase_conn(_elem)
        bus_terminal = _format_opendss_bus_terminal(ext_bus, phase, conn)
        if phases == 1:
            ext_basekv = _resolve_1ph_kv(ext_basekv, conn, _elem.get('kv'))
        return {
            'bus': ext_bus,
            'bus_terminal': bus_terminal,
            'basekv': ext_basekv,
            'pu': ext_pu,
            'angle': ext_angle,
            'mode': mode,
            'impedance_suffix': imp_suffix,
            'mvasc3': mvasc3,
            'phases': phases,
            'element': _elem,
            'typ': typ,
        }
    return None


def _new_circuit_command(ext_scan):
    """OpenDSS New Circuit line; Thevenin grid omits Mvasc3 (set on Edit Vsource.source)."""
    if not ext_scan:
        return 'New Circuit.OpenDSS_Circuit'
    parts = [
        f"New Circuit.OpenDSS_Circuit bus1={ext_scan.get('bus_terminal', ext_scan['bus'])}",
        f"basekv={ext_scan['basekv']}",
        f"pu={ext_scan['pu']}",
        f"phases={ext_scan.get('phases', 3)}",
        f"angle={ext_scan['angle']}",
    ]
    if ext_scan['mode'] == 'mvasc3' and ext_scan['mvasc3']:
        parts.append(f"Mvasc3={ext_scan['mvasc3']}")
    return ' '.join(parts)

def _bus_vm_pu_from_opendss(V1_mag_ll_kv, BusbarsDictVoltage, matched_bus_id):
    """Per-unit L-L voltage: prefer OpenDSS calcv base over diagram vn_kv."""
    try:
        base_kv_ln = float(dss.Bus.kVBase())
        base_kv_dss = base_kv_ln * math.sqrt(3)
        if base_kv_dss > 0 and V1_mag_ll_kv == V1_mag_ll_kv:
            return V1_mag_ll_kv / base_kv_dss
    except (TypeError, ValueError):
        pass
    base_kv_user = BusbarsDictVoltage.get(matched_bus_id)
    if base_kv_user is not None and float(base_kv_user) > 0:
        return V1_mag_ll_kv / float(base_kv_user)
    return 1.0


def _apply_equipment_bus_voltages(in_data, BusbarsDictVoltage, BusbarsDictConnectionToName):
    """Override bus vn_kv using transformer LV rating, PV kV, and external grid context."""
    def bus_key(ref):
        if not ref:
            return None
        name = _sanitize_opendss_name(ref)
        return BusbarsDictConnectionToName.get(name, name)

    for elem in in_data.values():
        typ = elem.get('typ', '')
        if typ.startswith('Transformer') or typ.startswith('Two Winding'):
            bt = bus_key(elem.get('busTo') or elem.get('lv_bus'))
            try:
                vn_lv = float(elem.get('vn_lv_kv') or 0)
            except (TypeError, ValueError):
                continue
            # HV bus keeps network vn_kv (e.g. 10.6 kV); vn_hv_kv is transformer nameplate only
            if vn_lv > 0 and bt in BusbarsDictVoltage:
                BusbarsDictVoltage[bt] = vn_lv
        elif typ.startswith('PVSystem'):
            b = bus_key(elem.get('bus'))
            try:
                kv = float(elem.get('kv') or elem.get('kV') or 0)
            except (TypeError, ValueError):
                kv = 0
            if kv > 0 and b in BusbarsDictVoltage:
                BusbarsDictVoltage[b] = kv
        elif typ.startswith('External Grid'):
            b = bus_key(elem.get('bus'))
            if b in BusbarsDictVoltage:
                BusbarsDictVoltage[b] = _resolve_external_grid_basekv(
                    in_data, BusbarsDictVoltage[b])

def create_busbars(in_data, dss, export_commands=False, opendss_commands=None):
    """Create busbars in OpenDSS circuit - Let OpenDSS handle bus creation automatically  when elements are connected"""
    BusbarsDictVoltage = {}  
    BusbarsDictConnectionToName = {}
    if opendss_commands is None:
        opendss_commands = []  
   
    
        # Collect bus information from input data for reference
    bus_elements = {}
    for x in in_data:         
        if "Bus" in in_data[x]['typ']:
            bus_name_raw = in_data[x]['name']
            bus_name = _sanitize_opendss_name(bus_name_raw)
            bus_id = in_data[x].get('id', bus_name_raw)  # Get ID for error messages
            bus_voltage_raw = in_data[x].get('vn_kv', None)
            
            # Validate bus voltage
            if bus_voltage_raw is None:
                error_msg = (
                    f"Bus '{bus_name_raw}' (ID: {bus_id}) is missing the 'vn_kv' (nominal voltage) attribute.\n\n"
                    f"Please set the nominal voltage in kV for this bus element.\n"
                    f"Common values: 110, 30, 20, 10, etc."
                )
                raise ValueError(error_msg)
            
            # Convert to float and validate it's a positive number
            try:
                bus_voltage = float(bus_voltage_raw)
            except (ValueError, TypeError):
                error_msg = (
                    f"Bus '{bus_name_raw}' (ID: {bus_id}) has an invalid 'vn_kv' value: '{bus_voltage_raw}'.\n\n"
                    f"The voltage must be a positive number in kV.\n"
                    f"Common values: 110, 30, 20, 10, etc."
                )
                raise ValueError(error_msg)
            
            # Check if voltage is zero or negative
            if bus_voltage <= 0:
                error_msg = (
                    f"Bus '{bus_name_raw}' (ID: {bus_id}) has an invalid voltage: {bus_voltage} kV.\n\n"
                    f"The nominal voltage must be a positive number greater than 0.\n"
                    f"Common values: 110, 30, 20, 10, etc.\n\n"
                    f"Please correct the 'vn_kv' attribute for this bus element."
                )
                raise ValueError(error_msg)
            
            bus_elements[bus_name] = bus_name
            BusbarsDictVoltage[bus_name] = bus_voltage
    
    # Map both bus name and bus id (cell id) to the sanitized bus name for OpenDSS.
    # This ensures that any reference (original name with spaces, sanitized name,
    # cell id with # or _) resolves to the same space-free OpenDSS bus name.
    for bus_name in bus_elements.keys():
        BusbarsDictConnectionToName[bus_name] = bus_name
    for x in in_data:
        if "Bus" in in_data[x].get('typ', ''):
            bus_name_raw = in_data[x].get('name', '')
            bus_name = _sanitize_opendss_name(bus_name_raw)
            bus_id = in_data[x].get('id', '')
            # Map original name (with spaces) to sanitized name
            if bus_name_raw and bus_name_raw != bus_name:
                BusbarsDictConnectionToName[bus_name_raw] = bus_name
            if bus_name and bus_id and bus_id != bus_name:
                BusbarsDictConnectionToName[bus_id] = bus_name
                BusbarsDictConnectionToName[bus_id.replace('#', '_')] = bus_name
                BusbarsDictConnectionToName[bus_id.replace('_', '#')] = bus_name  

    _apply_equipment_bus_voltages(in_data, BusbarsDictVoltage, BusbarsDictConnectionToName)
    
    return BusbarsDictVoltage, BusbarsDictConnectionToName

def create_other_elements(in_data, dss, BusbarsDictVoltage, BusbarsDictConnectionToName, export_commands=False, opendss_commands=None, execute_dss_command=None):
    """Create other elements in OpenDSS circuit"""
    global _opendss_shunt_meta
    _opendss_shunt_meta = {}
    if opendss_commands is None:
        opendss_commands = []
    
    # If execute_dss_command is not provided, create a default one
    if execute_dss_command is None:
        def execute_dss_command(command):
            """Execute DSS command and optionally collect it for export"""
            print(f"[OpenDSS] {command}")  # Log all commands
            dss.Text.Command(command)  # Use Text.Command (run_command is deprecated)
            if export_commands:
                opendss_commands.append(command)
    
    # Initialize tracking dictionaries
    LinesDict = {}
    LinesDictId = {}
    LoadsDict = {}
    LoadsDictId = {}
    TransformersDict = {}
    TransformersDictId = {}
    Transformers3WDict = {}
    Transformers3WDictId = {}
    ShuntsDict = {}
    ShuntsDictId = {}
    CapacitorsDict = {}
    CapacitorsDictId = {}
    GeneratorsDict = {}
    GeneratorsDictId = {}
    StoragesDict = {}
    StoragesDictId = {}
    PVSystemsDict = {}
    PVSystemsDictId = {}
    ExternalGridsDict = {}
    ExternalGridsDictId = {}
    
    # Track which elements have already been created to prevent duplicates
    created_elements = set()


    
    # First pass: create External Grid / Source 1ph (Vsource) so the slack bus is defined before other elements
    for x in in_data:
        try:
            element_data = in_data[x]
            element_type = element_data.get('typ', '')
            element_name = _sanitize_opendss_name(element_data.get('name', ''))
            element_id = element_data.get('id', '')
            if "Bus" in element_type or element_type == "PowerFlowOpenDss Parameters":
                continue
            if element_type.startswith("Source 1ph"):
                if 'bus' not in element_data or element_data['bus'] not in BusbarsDictConnectionToName:
                    continue
                create_source_1ph_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, created_elements, execute_dss_command)
                ExternalGridsDict[element_name] = element_name
                ExternalGridsDictId[element_name] = element_id
                continue
            if not element_type.startswith("External Grid"):
                continue
            if 'bus' not in element_data or element_data['bus'] not in BusbarsDictConnectionToName:
                continue
            create_external_grid_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, created_elements, execute_dss_command)
            ExternalGridsDict[element_name] = element_name
            ExternalGridsDictId[element_name] = element_id
        except ValueError as ve:
            raise
        except Exception as e:
            continue

    # Extract the circuit source element name (first ext grid mapped to Vsource.source)
    circuit_source_element_name = None
    for item in created_elements:
        if isinstance(item, str) and item.startswith('circuit_source_element:'):
            circuit_source_element_name = item.split(':', 1)[1]
            break

    # Second pass: create Lines and Impedances (establish bus connectivity at same voltage level)
    for x in in_data:
        try:
            element_data = in_data[x]
            element_type = element_data.get('typ', '')
            element_name = _sanitize_opendss_name(element_data.get('name', ''))
            element_id = element_data.get('id', '')
            if element_type.startswith("Line 1ph"):
                create_line_1ph_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LinesDict, LinesDictId, created_elements, execute_dss_command)
            elif "Line" in element_type:
                create_line_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LinesDict, LinesDictId, created_elements, execute_dss_command)
            elif element_type.startswith("Impedance"):
                create_impedance_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LinesDict, LinesDictId, created_elements, execute_dss_command)
        except ValueError as ve:
            raise
        except Exception as e:
            continue

    # Third pass: create 2-winding Transformers (exclude Three Winding Transformer)
    for x in in_data:
        try:
            element_data = in_data[x]
            element_type = element_data.get('typ', '')
            element_name = _sanitize_opendss_name(element_data.get('name', ''))
            element_id = element_data.get('id', '')
            if element_type.startswith("Transformer 1ph"):
                create_transformer_1ph_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, TransformersDict, TransformersDictId, created_elements, execute_dss_command)
            elif (element_type.startswith("Transformer") or element_type.startswith("Two Winding Transformer")) and not element_type.startswith("Three Winding Transformer"):
                create_transformer_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, TransformersDict, TransformersDictId, created_elements, execute_dss_command)
        except ValueError as ve:
            raise
        except Exception as e:
            continue

    # Third-b pass: create 3-winding Transformers
    for x in in_data:
        try:
            element_data = in_data[x]
            element_type = element_data.get('typ', '')
            element_name = _sanitize_opendss_name(element_data.get('name', ''))
            element_id = element_data.get('id', '')
            if element_type.startswith("Three Winding Transformer"):
                create_transformer3w_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, Transformers3WDict, Transformers3WDictId, created_elements, execute_dss_command)
        except ValueError as ve:
            raise
        except Exception as e:
            continue

    # Fourth pass: create Shunt elements (Reactors, Capacitors) - constant impedance elements
    for x in in_data:
        try:
            element_data = in_data[x]
            element_type = element_data.get('typ', '')
            element_name = _sanitize_opendss_name(element_data.get('name', ''))
            element_id = element_data.get('id', '')
            if element_type.startswith("Shunt Reactor"):
                create_shunt_reactor_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, ShuntsDict, ShuntsDictId, created_elements, execute_dss_command)
            elif element_type.startswith("Capacitor"):
                create_capacitor_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, CapacitorsDict, CapacitorsDictId, created_elements, execute_dss_command)
        except ValueError as ve:
            raise
        except Exception as e:
            continue

    # Fifth pass: create power injection elements (Generators, Loads, Storage, PVSystems)
    for x in in_data:
        try:
            element_data = in_data[x]
            element_type = element_data.get('typ', '')
            element_name = _sanitize_opendss_name(element_data.get('name', ''))
            element_id = element_data.get('id', '')
            if "Bus" in element_type or element_type == "PowerFlowOpenDss Parameters":
                continue
            if element_type.startswith("External Grid") or element_type.startswith("Source 1ph") or "Line" in element_type or element_type.startswith("Transformer") or element_type.startswith("Two Winding Transformer") or element_type.startswith("Three Winding") or element_type.startswith("Shunt Reactor") or element_type.startswith("Capacitor"):
                continue
            if element_type.startswith("Load 1ph"):
                create_load_1ph_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LoadsDict, LoadsDictId, created_elements, execute_dss_command)
            elif element_type.startswith("Load"):
                create_load_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LoadsDict, LoadsDictId, created_elements, execute_dss_command)
            elif element_type.startswith("Motor"):
                # Motors are modeled as Loads in OpenDSS
                create_load_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LoadsDict, LoadsDictId, created_elements, execute_dss_command)
            elif element_type.startswith("Static Generator") or element_type.startswith("Wind Turbine"):
                create_static_generator_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, GeneratorsDict, GeneratorsDictId, created_elements, execute_dss_command)
            elif element_type.startswith("Asymmetric Static Generator"):
                create_static_generator_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, GeneratorsDict, GeneratorsDictId, created_elements, execute_dss_command)
            elif element_type.startswith("Generator 1ph"):
                create_generator_1ph_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, GeneratorsDict, GeneratorsDictId, created_elements, execute_dss_command)
            elif element_type.startswith("Generator"):
                create_generator_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, GeneratorsDict, GeneratorsDictId, created_elements, execute_dss_command)
            elif element_type.startswith("Storage"):
                create_storage_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, StoragesDict, StoragesDictId, created_elements, execute_dss_command)
            elif element_type.startswith("PVSystem"):
                create_pvsystem_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, PVSystemsDict, PVSystemsDictId, created_elements, execute_dss_command)
        except ValueError as ve:
            raise
        except Exception as e:
            continue

    # Sixth pass: create Switch elements (OpenDSS: open/close Lines, disable Transformers, or Reactor for bus-bus)
    for x in in_data:
        try:
            element_data = in_data[x]
            element_type = element_data.get('typ', '')
            if not element_type.startswith("Switch"):
                continue
            create_switch_element(dss, element_data, LinesDict, TransformersDict, BusbarsDictConnectionToName, execute_dss_command)
        except ValueError as ve:
            raise
        except Exception as e:
            continue

    # Seventh pass: create OpenDSS control elements after their controlled equipment exists.
    # These are not electrical terminals, so their canvas attachment is a reference rather
    # than a bus connection.
    for x in in_data:
        try:
            element_data = in_data[x]
            element_type = element_data.get('typ', '')
            element_name = _sanitize_opendss_name(element_data.get('name', ''))
            element_id = element_data.get('id', '')
            if element_type.startswith('RegControl'):
                create_regcontrol_element(
                    dss, element_data, element_name, element_id, TransformersDict,
                    TransformersDictId, BusbarsDictConnectionToName, execute_dss_command, in_data)
            elif element_type.startswith('CapControl'):
                create_capcontrol_element(
                    dss, element_data, element_name, element_id, CapacitorsDict,
                    CapacitorsDictId, BusbarsDictConnectionToName, execute_dss_command, in_data)
            elif element_type.startswith('StorageController'):
                create_storagecontroller_element(
                    dss, element_data, element_name, element_id, StoragesDict,
                    StoragesDictId, execute_dss_command)
            elif element_type.startswith('WindTurbineController'):
                # Pref applied to linked Wind Turbine on the frontend for snapshot studies.
                pass
        except ValueError:
            raise
        except Exception as e:
            print(f'[OpenDSS] Control element creation failed: {e}')
            continue

    # After all elements: set voltage bases and run calcv so OpenDSS assigns correct base kV
    # to every bus (including those with PVSystems/Loads). Running calcv before power
    # injection elements can leave the first solve at zero power until the circuit is rebuilt.
    try:
        vb_list = _collect_voltage_bases_from_in_data(in_data, BusbarsDictVoltage)
        if vb_list:
            execute_dss_command('set voltagebases=[' + ','.join(str(v) for v in vb_list) + ']')
        execute_dss_command('calcv')
    except Exception:
        pass

    return (LinesDict, LinesDictId, LoadsDict, LoadsDictId, TransformersDict, TransformersDictId,
            Transformers3WDict, Transformers3WDictId,
            ShuntsDict, ShuntsDictId, CapacitorsDict, CapacitorsDictId, GeneratorsDict, GeneratorsDictId,
            StoragesDict, StoragesDictId, PVSystemsDict, PVSystemsDictId, ExternalGridsDict, ExternalGridsDictId,
            circuit_source_element_name)

# Individual element creation functions - OpenDSS single-phase elements
def create_load_1ph_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LoadsDict, LoadsDictId, created_elements, execute_dss_command=None):
    if element_name in created_elements:
        return
    bus_connection = element_data.get('bus')
    if not bus_connection:
        return
    bus_name = BusbarsDictConnectionToName.get(bus_connection) or _sanitize_opendss_name(bus_connection)
    bus_voltage = BusbarsDictVoltage.get(bus_name)
    if bus_voltage is None:
        return
    phase, conn = _element_phase_conn(element_data)
    # Delta 1ph loads need two energized nodes; radial Line 1ph (wye) only energizes one.
    if conn == 'delta':
        _opendss_warn(
            f"Load '{element_name}' conn=delta on single-phase radial feeder; using wye (L-N) on phase {phase}"
        )
        conn = 'wye'
    bus_terminal = _format_opendss_bus_terminal(bus_name, phase, conn)
    kv = _resolve_load_1ph_kv(bus_voltage, conn, element_data.get('kv'))
    if element_data.get('p_kw') not in (None, ''):
        p_kw = float(element_data.get('p_kw') or 0)
    else:
        p_kw = float(element_data.get('p_mw', 0) or 0) * 1000
    if element_data.get('q_kvar') not in (None, ''):
        q_kvar = float(element_data.get('q_kvar') or 0)
    else:
        q_kvar = float(element_data.get('q_mvar', 0) or 0) * 1000
    load_name = element_name.replace(' ', '_')
    try:
        load_cmd = f"New Load.{load_name} phases=1 Bus1={bus_terminal} kV={kv} kW={p_kw} kvar={abs(q_kvar)} conn={conn}"
        spectrum = element_data.get('spectrum', 'defaultload')
        if spectrum and str(spectrum).lower() != 'none':
            load_cmd += f" spectrum={spectrum}"
        pct_series_rl = element_data.get('pctSeriesRL', '')
        if pct_series_rl not in ('', None):
            load_cmd += f" %SeriesRL={float(pct_series_rl)}"
        execute_dss_command(load_cmd)
        in_service = element_data.get('in_service', True)
        is_in_service = in_service if isinstance(in_service, bool) else str(in_service).lower() not in ['false', 'no', '0']
        if not is_in_service:
            execute_dss_command(f'Load.{load_name}.enabled=no')
        LoadsDict[element_name] = load_name
        LoadsDictId[element_name] = element_id
        created_elements.add(element_name)
    except Exception:
        pass


def create_generator_1ph_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, GeneratorsDict, GeneratorsDictId, created_elements, execute_dss_command=None):
    if element_name in created_elements:
        return
    bus_connection = element_data.get('bus')
    if not bus_connection:
        return
    bus_name = BusbarsDictConnectionToName.get(bus_connection) or _sanitize_opendss_name(bus_connection)
    bus_voltage = BusbarsDictVoltage.get(bus_name)
    if bus_voltage is None:
        return
    phase, conn = _element_phase_conn(element_data)
    if conn == 'delta':
        _opendss_warn(
            f"Generator '{element_name}' conn=delta on single-phase radial feeder; using wye (L-N) on phase {phase}"
        )
        conn = 'wye'
    bus_terminal = _format_opendss_bus_terminal(bus_name, phase, conn)
    kv = _resolve_load_1ph_kv(bus_voltage, conn, element_data.get('kv'))
    if element_data.get('p_kw') not in (None, ''):
        p_kw = float(element_data.get('p_kw') or 0)
    else:
        p_kw = float(element_data.get('p_mw', 0) or 0) * 1000
    if element_data.get('q_kvar') not in (None, ''):
        q_kvar = float(element_data.get('q_kvar') or 0)
    else:
        q_kvar = float(element_data.get('q_mvar', 0) or 0) * 1000
    try:
        model = int(element_data.get('model', 1) or 1)
    except (TypeError, ValueError):
        model = 1
    gen_name = element_name.replace(' ', '_')
    try:
        gen_cmd = (
            f"New Generator.{gen_name} phases=1 Bus1={bus_terminal} kV={kv} "
            f"kW={p_kw} kvar={q_kvar} Model={model} conn={conn}"
        )
        sn_kva = element_data.get('sn_kva')
        if sn_kva not in (None, '', '0', 0):
            gen_cmd += f" kVA={float(sn_kva)}"
        spectrum = element_data.get('spectrum', 'defaultgen')
        if spectrum and str(spectrum).lower() != 'none':
            gen_cmd += f" spectrum={spectrum}"
        execute_dss_command(gen_cmd)
        in_service = element_data.get('in_service', True)
        is_in_service = in_service if isinstance(in_service, bool) else str(in_service).lower() not in ['false', 'no', '0']
        if not is_in_service:
            execute_dss_command(f'Generator.{gen_name}.enabled=no')
        GeneratorsDict[element_name] = gen_name
        GeneratorsDictId[element_name] = element_id
        created_elements.add(element_name)
    except Exception:
        pass


def create_line_1ph_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LinesDict, LinesDictId, created_elements, execute_dss_command=None):
    if element_name in created_elements:
        return
    bus_from_ref = element_data.get('busFrom')
    bus_to_ref = element_data.get('busTo')
    if not bus_from_ref or not bus_to_ref:
        return
    bus_from_name = BusbarsDictConnectionToName.get(bus_from_ref) or _sanitize_opendss_name(bus_from_ref)
    bus_to_name = BusbarsDictConnectionToName.get(bus_to_ref) or _sanitize_opendss_name(bus_to_ref)
    phase, conn = _element_phase_conn(element_data)
    t1 = _format_opendss_bus_terminal(bus_from_name, phase, conn)
    t2 = _format_opendss_bus_terminal(bus_to_name, phase, conn)
    r_ohm_per_km = float(element_data.get('r_ohm_per_km', 0.122) or 0.122)
    x_ohm_per_km = float(element_data.get('x_ohm_per_km', 0.112) or 0.112)
    length_km = float(element_data.get('length_km', 1) or 1)
    c_nf_per_km = element_data.get('c_nf_per_km')
    try:
        line_cmd = f'New Line.{element_name} phases=1 Bus1={t1} Bus2={t2} R1={r_ohm_per_km} X1={x_ohm_per_km} Length={length_km} units=km'
        if c_nf_per_km not in (None, '', '0', 0):
            line_cmd += f' C1={float(c_nf_per_km)}'
        execute_dss_command(line_cmd)
        in_service = element_data.get('in_service', True)
        is_in_service = in_service if isinstance(in_service, bool) else str(in_service).lower() not in ['false', 'no', '0']
        if not is_in_service:
            execute_dss_command(f'Line.{element_name}.enabled=no')
        LinesDict[element_name] = element_name
        LinesDictId[element_name] = element_id
        created_elements.add(element_name)
    except Exception:
        pass


def create_source_1ph_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, created_elements, execute_dss_command=None):
    if element_name in created_elements:
        return
    bus_connection = element_data.get('bus')
    if not bus_connection:
        return
    bus_name = BusbarsDictConnectionToName.get(bus_connection) or _sanitize_opendss_name(bus_connection)
    bus_voltage = BusbarsDictVoltage.get(bus_name)
    if bus_voltage is None:
        raise ValueError(f"Missing voltage for bus '{bus_name}' connected to Source 1ph '{element_name}'.")
    phase, conn = _element_phase_conn(element_data)
    bus_terminal = _format_opendss_bus_terminal(bus_name, phase, conn)
    basekv = _resolve_1ph_kv(bus_voltage, conn, element_data.get('kv'))
    vm_pu = float(element_data.get('vm_pu', 1.0) or 1.0)
    if vm_pu == 0:
        vm_pu = 1.0
    try:
        angle = float(element_data.get('va_degree', 0) or 0)
    except (TypeError, ValueError):
        angle = 0.0
    mode, imp_suffix, mvasc3 = _ext_grid_vsource_impedance(element_data, bus_voltage)
    imp_part = imp_suffix if mode == 'thevenin' else f" mvasc3={mvasc3}"
    if 'circuit_source_configured' not in created_elements:
        edit_cmd = (f"Edit Vsource.source Bus1={bus_terminal} basekv={basekv} "
                    f"pu={vm_pu} Phases=1 angle={angle}{imp_part}")
        execute_dss_command(edit_cmd)
        created_elements.add('circuit_source_configured')
        created_elements.add(f'circuit_source_element:{element_name}')
    else:
        execute_dss_command(
            f"New Vsource.{element_name} Bus1={bus_terminal} basekv={basekv} "
            f"pu={vm_pu} Phases=1 angle={angle}{imp_part}"
        )
    in_service = element_data.get('in_service', True)
    is_in_service = in_service if isinstance(in_service, bool) else str(in_service).lower() not in ['false', 'no', '0']
    if not is_in_service:
        target = 'Vsource.source' if f'circuit_source_element:{element_name}' in created_elements else f'Vsource.{element_name}'
        execute_dss_command(f'{target}.enabled=no')
    created_elements.add(element_name)


def create_transformer_1ph_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, TransformersDict, TransformersDictId, created_elements, execute_dss_command=None):
    if element_name in created_elements:
        return
    bus_from_ref = element_data.get('busFrom') or element_data.get('hv_bus')
    bus_to_ref = element_data.get('busTo') or element_data.get('lv_bus')
    if not bus_from_ref or not bus_to_ref:
        return
    bus_from_name = BusbarsDictConnectionToName.get(bus_from_ref) or _sanitize_opendss_name(bus_from_ref)
    bus_to_name = BusbarsDictConnectionToName.get(bus_to_ref) or _sanitize_opendss_name(bus_to_ref)
    phase, conn = _element_phase_conn(element_data)
    try:
        sn_kva = float(element_data.get('sn_kva', 25) or 25)
        vk_percent = float(element_data.get('vk_percent', 2.0) or 2.0)
        vkr_percent = float(element_data.get('vkr_percent', 0.6) or 0.6)
        kv_hv = float(element_data.get('vn_hv_kv', BusbarsDictVoltage.get(bus_from_name) or 7.2) or 7.2)
        kv_lv = float(element_data.get('vn_lv_kv', BusbarsDictVoltage.get(bus_to_name) or 0.12) or 0.12)
        tap_pos = float(element_data.get('tap_pos', 0) or 0)
    except (TypeError, ValueError):
        return
    if float(BusbarsDictVoltage.get(bus_from_name) or 0) >= float(BusbarsDictVoltage.get(bus_to_name) or 0):
        hv_name, lv_name = bus_from_name, bus_to_name
    else:
        hv_name, lv_name = bus_to_name, bus_from_name
        kv_hv, kv_lv = kv_lv, kv_hv
    hv_term = _format_opendss_bus_terminal(hv_name, phase, conn)
    lv_term = _format_opendss_bus_terminal(lv_name, phase, 'wye')
    pri_conn = 'delta' if conn == 'delta' else 'wye'
    xhl = vk_percent
    rs_hv = vkr_percent / 2.0
    rs_lv = vkr_percent / 2.0
    try:
        cmd = (
            f"New Transformer.{element_name} phases=1 Windings=2 "
            f"Buses=[{hv_term} {lv_term}] Conns=[{pri_conn} wye] "
            f"kVs=[{kv_hv} {kv_lv}] kVAs=[{sn_kva} {sn_kva}] "
            f"XHL={xhl} %Rs=[{rs_hv} {rs_lv}] Taps=[{1 + tap_pos * 0.00625} 1]"
        )
        execute_dss_command(cmd)
        in_service = element_data.get('in_service', True)
        is_in_service = in_service if isinstance(in_service, bool) else str(in_service).lower() not in ['false', 'no', '0']
        if not is_in_service:
            execute_dss_command(f'Transformer.{element_name}.enabled=no')
        TransformersDict[element_name] = element_name
        TransformersDictId[element_name] = element_id
        created_elements.add(element_name)
    except Exception:
        pass


# Individual element creation functions
def create_line_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LinesDict, LinesDictId, created_elements, execute_dss_command=None):
    """Create a line element in OpenDSS"""
    
    # Check for duplicates - skip if already created
    if element_name in created_elements:
        return
    
    # Get bus connections
    bus_from_ref = element_data.get('busFrom')
    bus_to_ref = element_data.get('busTo')
    
    if bus_from_ref and bus_to_ref:
        
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_from_ref_backend = bus_from_ref
        bus_to_ref_backend = bus_to_ref
        
        # Get bus names from connection mapping
        if bus_from_ref_backend in BusbarsDictConnectionToName:
            bus_from_name = BusbarsDictConnectionToName[bus_from_ref_backend]
        else:
            bus_from_name = _sanitize_opendss_name(bus_from_ref_backend)
            
        if bus_to_ref_backend in BusbarsDictConnectionToName:
            bus_to_name = BusbarsDictConnectionToName[bus_to_ref_backend]
        else:
            bus_to_name = _sanitize_opendss_name(bus_to_ref_backend)        
        
        # Extract line parameters from input data (like the previous version)
        r_ohm_per_km = element_data.get('r_ohm_per_km')
        x_ohm_per_km = element_data.get('x_ohm_per_km')
        c_nf_per_km = element_data.get('c_nf_per_km')
        length_km = element_data.get('length_km')
        r0_ohm_per_km = element_data.get('r0_ohm_per_km')
        x0_ohm_per_km = element_data.get('x0_ohm_per_km')
        c0_nf_per_km = element_data.get('c0_nf_per_km')
        
        # Validate r0_ohm_per_km, x0_ohm_per_km and c0_nf_per_km for OpenDSS - must be greater than 0
        if r0_ohm_per_km is not None:
            try:
                r0_value = float(r0_ohm_per_km)
                if r0_value <= 0:
                    raise ValueError(f"Line '{element_name}': Parameter r0_ohm_per_km must be greater than 0 (current value: {r0_value}). Please update the line parameters.")
            except (TypeError, ValueError) as e:
                if "must be greater than 0" in str(e):
                    raise
                raise ValueError(f"Line '{element_name}': Invalid value for r0_ohm_per_km: {r0_ohm_per_km}")
        
        if x0_ohm_per_km is not None:
            try:
                x0_value = float(x0_ohm_per_km)
                if x0_value <= 0:
                    raise ValueError(f"Line '{element_name}': Parameter x0_ohm_per_km must be greater than 0 (current value: {x0_value}). Please update the line parameters.")
            except (TypeError, ValueError) as e:
                if "must be greater than 0" in str(e):
                    raise
                raise ValueError(f"Line '{element_name}': Invalid value for x0_ohm_per_km: {x0_ohm_per_km}")
        
        if c0_nf_per_km is not None:
            try:
                c0_value = float(c0_nf_per_km)
                if c0_value <= 0:
                    raise ValueError(f"Line '{element_name}': Parameter c0_nf_per_km must be greater than 0 (current value: {c0_value}). Please update the line parameters.")
            except (TypeError, ValueError) as e:
                if "must be greater than 0" in str(e):
                    raise
                raise ValueError(f"Line '{element_name}': Invalid value for c0_nf_per_km: {c0_nf_per_km}")
        
        try:
            # Create line using OpenDSS command with parameters from frontend
            line_cmd = f'New Line.{element_name} phases=3 Bus1={bus_from_name} Bus2={bus_to_name} R1={r_ohm_per_km} X1={x_ohm_per_km} Length={length_km} units=km'
            
            # Add optional parameters only if they exist
            if r0_ohm_per_km is not None:
                line_cmd += f' R0={r0_ohm_per_km}'
            if x0_ohm_per_km is not None:
                line_cmd += f' X0={x0_ohm_per_km}'
            if c_nf_per_km is not None:
                line_cmd += f' C1={c_nf_per_km}'
            if c0_nf_per_km is not None:
                line_cmd += f' C0={c0_nf_per_km}'
                
            execute_dss_command(line_cmd)
            
            # Handle in_service status AFTER creating the element
            # This prevents topology issues during network creation
            in_service = element_data.get('in_service', True)
            
            # Convert to boolean for comparison
            is_in_service = True
            if isinstance(in_service, bool):
                is_in_service = in_service
            elif isinstance(in_service, str):
                is_in_service = in_service.lower() not in ['false', 'no', '0']
            elif in_service in [0, None]:
                is_in_service = False
            
            if not is_in_service:
                # Disable the line after it's been created
                cmd = f'Line.{element_name}.enabled=no'
                print(f"[OpenDSS] {cmd}")
                dss.Text.Command(cmd)
            
            # print(f"Command: {line_cmd}")  # Reduced logging
            
            actual_name = dss.Lines.Name()
            LinesDict[element_name] = actual_name
            LinesDictId[element_name] = element_id
            created_elements.add(element_name)
            
        except Exception as e:
            pass
    else:
        pass


def create_impedance_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LinesDict, LinesDictId, created_elements, execute_dss_command=None):
    """Create an impedance element in OpenDSS (modeled as Line with R1, X1, Length=1)"""
    if element_name in created_elements:
        return
    bus_from_ref = element_data.get('busFrom')
    bus_to_ref = element_data.get('busTo')
    if not bus_from_ref or not bus_to_ref:
        return
    bus_from_name = BusbarsDictConnectionToName.get(bus_from_ref) or _sanitize_opendss_name(bus_from_ref)
    bus_to_name = BusbarsDictConnectionToName.get(bus_to_ref) or _sanitize_opendss_name(bus_to_ref)
    r_ohm = float(element_data.get('r_ohm', 0) or 0)
    x_ohm = float(element_data.get('x_ohm', 0) or 0)
    # Avoid R1=0 X1=0 (short circuit) - OpenDSS can hang or fail to converge
    MIN_IMPEDANCE_OHM = 0.001
    if r_ohm <= 0 and x_ohm <= 0:
        r_ohm = MIN_IMPEDANCE_OHM
        x_ohm = MIN_IMPEDANCE_OHM
    elif r_ohm <= 0:
        r_ohm = MIN_IMPEDANCE_OHM
    elif x_ohm <= 0:
        x_ohm = MIN_IMPEDANCE_OHM
    try:
        line_cmd = f'New Line.{element_name} phases=3 Bus1={bus_from_name} Bus2={bus_to_name} R1={r_ohm} X1={x_ohm} Length=1 units=km'
        if execute_dss_command:
            execute_dss_command(line_cmd)
        else:
            dss.Text.Command(line_cmd)
        in_service = element_data.get('in_service', True)
        is_in_service = True
        if isinstance(in_service, bool):
            is_in_service = in_service
        elif isinstance(in_service, str):
            is_in_service = in_service.lower() not in ['false', 'no', '0']
        elif in_service in [0, None]:
            is_in_service = False
        if not is_in_service:
            cmd = f'Line.{element_name}.enabled=no'
            if execute_dss_command:
                execute_dss_command(cmd)
            else:
                dss.Text.Command(cmd)
        LinesDict[element_name] = element_name
        LinesDictId[element_name] = element_id
        created_elements.add(element_name)
    except Exception as e:
        pass


def _resolve_in_dict(key, d):
    """Resolve element key in dict, trying key and #/_ variants."""
    if not key:
        return None
    k = _sanitize_opendss_name(key)
    if k in d:
        return d[k]
    k_alt = k.replace('_', '#') if '_' in k else k.replace('#', '_')
    if k_alt in d:
        return d[k_alt]
    for dict_key in d:
        if (dict_key or '').replace('#', '_') == (k or '').replace('#', '_'):
            return d[dict_key]
    return None


def create_switch_element(dss, element_data, LinesDict, TransformersDict, BusbarsDictConnectionToName, execute_dss_command=None):
    """Create/open switch in OpenDSS.
    et='l': open/close Line via Bus2=__opened__...; et='t': Transformer.Enabled=no/yes;
    et='b': bus-bus switch as Reactor (R=0.001 closed, R=1e8 open); et='t3' not supported (no 3w in OpenDSS)."""
    def run(cmd):
        if execute_dss_command:
            execute_dss_command(cmd)
        else:
            dss.Text.Command(cmd)
    
    element_name = _sanitize_opendss_name(element_data.get('element', ''))
    switch_name = _sanitize_opendss_name(element_data.get('name', 'Switch'))
    closed = element_data.get('closed', True)
    if isinstance(closed, str):
        closed = closed.lower() not in ('false', 'no', '0', 'open')
    et = str(element_data.get('et', 'l')).lower()
    
    if et in ('l', 'line'):
        line_name = _resolve_in_dict(element_data.get('element', ''), LinesDict)
        if line_name is not None:
            try:
                dss.Circuit.SetActiveElement(f'Line.{line_name}')
                if dss.ActiveElement.Name() == line_name:
                    bus2 = dss.CktElement.BusNames()[1] if len(dss.CktElement.BusNames()) > 1 else ''
                    if closed:
                        if bus2.startswith('__opened__'):
                            run(f'Line.{line_name}.Bus2={bus2.replace("__opened__", "")}')
                    else:
                        if not bus2.startswith('__opened__'):
                            run(f'Line.{line_name}.Bus2=__opened__{bus2}')
            except Exception:
                pass
    elif et in ('t', 'trafo', 'transformer'):
        trafo_name = _resolve_in_dict(element_data.get('element', ''), TransformersDict)
        if trafo_name is not None:
            try:
                run(f'Transformer.{trafo_name}.enabled={"yes" if closed else "no"}')
            except Exception:
                pass
    elif et == 'b':
        bus1_ref = element_data.get('bus')
        bus2_ref = element_data.get('element')
        if bus1_ref and bus2_ref:
            bus1 = (BusbarsDictConnectionToName.get(bus1_ref) or BusbarsDictConnectionToName.get((bus1_ref or '').replace('#', '_')) or
                    BusbarsDictConnectionToName.get((bus1_ref or '').replace('_', '#')) or _sanitize_opendss_name(bus1_ref))
            bus2 = (BusbarsDictConnectionToName.get(bus2_ref) or BusbarsDictConnectionToName.get((bus2_ref or '').replace('#', '_')) or
                    BusbarsDictConnectionToName.get((bus2_ref or '').replace('_', '#')) or _sanitize_opendss_name(bus2_ref))
            r_ohm = 0.001 if closed else 1e8
            try:
                run(f'New Reactor.{switch_name} phases=3 Bus1={bus1} Bus2={bus2} R={r_ohm} X=0')
            except Exception:
                pass


# Built-in harmonic spectra (IEEE benchmark, harmonicscelsorocha)
SPECTRUM_TCR_PU_CSV = """1,100.000000000000000,46.916,
5,7.015117401093600,-124.4,
7,2.504872003481350,-29.867,
11,1.358541615423910,-23.745,
13,0.750004730100467,71.502,
17,0.615726638033792,77.119,
19,0.317862751404840,173.43,
23,0.431460844228331,178.02,
25,0.128550886420828,-83.446,
29,0.399901613910279,-80.445,
"""
SPECTRUM_HVDC_PU_CSV = """1,100.00000000000000,-49.555
5,19.40778541333880,-67.771
7,13.08897155783310,11.903
11,7.57732345594305,-7.1346
13,5.85910781864768,68.571
17,3.79203876625535,46.526
19,3.29191547755610,116.46
23,2.26336610311224,87.465
25,2.41141974977754,159.32
29,1.92737759576316,126.79
"""

# Electrisim UI "Linear" harmonic mode: magnitude ~ 100/h (% of fundamental), angle 0.
# OpenDSS does not provide a built-in Spectrum named "Linear"; passing spectrum=Linear yields
# no harmonic injection and zero harmonic voltages/currents after mode=harmonics.
SPECTRUM_LINEAR_UI_CSV = """3,33.333333,0
5,20.0,0
7,14.285714,0
11,9.090909,0
13,7.692308,0
"""


def _spectrum_dss_from_csv(spectrum_name, csv_text):
    """Parse CSV (harmonic,magnitude,angle per line) and return OpenDSS New Spectrum command string.
    Used for injecting TCR_PU/HVDC_PU into imported DSS files."""
    harmonics, mags, angles = [], [], []
    for line in csv_text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = [p.strip() for p in line.split(',') if p.strip()]
        if len(parts) >= 3:
            try:
                h = int(float(parts[0]))
                m = float(parts[1])
                a = float(parts[2])
                harmonics.append(h)
                mags.append(m)
                angles.append(a)
            except (ValueError, IndexError):
                continue
    if not harmonics:
        return None
    harm_str = ' '.join(str(h) for h in harmonics)
    mag_str = ' '.join(f'{m:.6g}' for m in mags)
    ang_str = ' '.join(f'{a:.6g}' for a in angles)
    return f'New Spectrum.{spectrum_name} NumHarm={len(harmonics)} harmonic=({harm_str}) %mag=({mag_str}) angle=({ang_str})'


def _create_spectrum_from_csv(dss, spectrum_name, csv_text, execute_dss_command):
    """Parse CSV (harmonic,magnitude,angle per line) and create OpenDSS Spectrum object."""
    harmonics, mags, angles = [], [], []
    for line in csv_text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = [p.strip() for p in line.split(',') if p.strip()]
        if len(parts) >= 3:
            try:
                h = int(float(parts[0]))
                m = float(parts[1])
                a = float(parts[2])
                harmonics.append(h)
                mags.append(m)
                angles.append(a)
            except (ValueError, IndexError):
                continue
    if not harmonics:
        return False
    harm_str = ' '.join(str(h) for h in harmonics)
    mag_str = ' '.join(f'{m:.6g}' for m in mags)
    ang_str = ' '.join(f'{a:.6g}' for a in angles)
    cmd = f'New Spectrum.{spectrum_name} NumHarm={len(harmonics)} harmonic=({harm_str}) %mag=({mag_str}) angle=({ang_str})'
    execute_dss_command(cmd)
    return True


def _resolve_named_spectrum_for_element(dss, element_data, default_spectrum, spectrum_object_name, execute_dss_command):
    """
    Resolve spectrum= for Generator, static Generator, PVSystem, Vsource: named spectrum or
    custom CSV (creates New Spectrum.<spectrum_object_name> and references it).
    """
    spectrum = element_data.get('spectrum', default_spectrum)
    if spectrum is None or str(spectrum).strip().lower() == 'none':
        return None
    spectrum = str(spectrum).strip()
    sl = spectrum.lower()
    if sl == 'custom':
        csv_text = element_data.get('spectrum_csv', '') or ''
        if csv_text.strip():
            safe_name = _sanitize_opendss_name(spectrum_object_name)
            if _create_spectrum_from_csv(dss, safe_name, csv_text, execute_dss_command):
                return safe_name
        return default_spectrum
    if sl == 'linear':
        lin_name = _sanitize_opendss_name(f"{spectrum_object_name}_linear")
        if _create_spectrum_from_csv(dss, lin_name, SPECTRUM_LINEAR_UI_CSV, execute_dss_command):
            return lin_name
        return default_spectrum
    return spectrum


def create_load_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LoadsDict, LoadsDictId, created_elements, execute_dss_command=None):
    """Create a load element in OpenDSS (handles both Load and Motor types)"""
    
    # Check for duplicates - skip if already created
    if element_name in created_elements:
        return
    
    bus_connection = element_data.get('bus')
    if bus_connection:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_connection_backend = bus_connection
        if bus_connection_backend in BusbarsDictConnectionToName:
            bus_name = BusbarsDictConnectionToName[bus_connection_backend]
        else:
            bus_name = _sanitize_opendss_name(bus_connection_backend)
        # Get voltage from the bus data
        bus_voltage = BusbarsDictVoltage.get(bus_name)
        
        if bus_voltage is None:
            return                 
        
        # Detect if this is a Motor or regular Load
        element_type = element_data.get('typ', '')
        is_motor = element_type.startswith('Motor')
        
        if is_motor:
            import math
            # Motor: calculate P and Q to match pandapower's motor model
            # P_electric = pn_mech_mw * loading_percent / efficiency_percent * scaling
            pn_mw = float(element_data.get('pn_mech_mw', 0) or element_data.get('pn_mw', 0))
            efficiency_raw = float(element_data.get('efficiency_percent', 0.9))
            loading_raw = float(element_data.get('loading_percent', efficiency_raw))
            scaling = float(element_data.get('scaling', 1.0))
            
            # Detect if values are fractions (<=1) or actual percentages (>1)
            efficiency = efficiency_raw if efficiency_raw > 1 else efficiency_raw * 100
            loading = loading_raw if loading_raw > 1 else loading_raw * 100
            
            # P_elec = P_mech * (loading% / 100) / (efficiency% / 100) * scaling
            if efficiency > 0:
                p_mw = pn_mw * (loading / 100.0) / (efficiency / 100.0) * scaling
            else:
                p_mw = pn_mw * scaling
            
            # Use cos_phi (same as pandapower), fall back to cos_phi_n
            cos_phi = float(element_data.get('cos_phi', 0) or element_data.get('cos_phi_n', 0.85))
            
            # Q = P * tan(acos(cos_phi))
            if cos_phi > 0 and cos_phi < 1.0:
                q_mvar = p_mw * math.tan(math.acos(cos_phi))
            else:
                q_mvar = 0
        else:
            # Regular Load: get P and Q directly
            p_mw_raw = element_data.get('p_mw')
            q_mvar_raw = element_data.get('q_mvar')
            
            # Convert to float
            p_mw = float(p_mw_raw)
            q_mvar = float(q_mvar_raw)
        
        # Convert to kW and kVar
        p_kw = p_mw * 1000
        q_kvar = q_mvar * 1000             
        
        load_name = element_name.replace(' ', '_')
        
        try:
            # Create load command string
            load_cmd = f"New Load.{load_name} Bus1={bus_name} kV={bus_voltage} kW={p_kw} kvar={abs(q_kvar)}"
            
            # For motors, add model parameter
            if is_motor:
                load_cmd += " model=1"  # Constant P+jQ model for motors
            
            # Append harmonic analysis properties if provided
            spectrum = element_data.get('spectrum', 'defaultload')
            if spectrum and spectrum.lower() != 'none':
                spectrum_to_use = spectrum
                # For TCR_PU / HVDC_PU: use built-in IEEE benchmark spectra
                if spectrum.upper() == 'TCR_PU':
                    if _create_spectrum_from_csv(dss, 'TCR_PU', SPECTRUM_TCR_PU_CSV, execute_dss_command):
                        spectrum_to_use = 'TCR_PU'
                    else:
                        spectrum_to_use = 'defaultload'
                elif spectrum.upper() == 'HVDC_PU':
                    if _create_spectrum_from_csv(dss, 'HVDC_PU', SPECTRUM_HVDC_PU_CSV, execute_dss_command):
                        spectrum_to_use = 'HVDC_PU'
                    else:
                        spectrum_to_use = 'defaultload'
                # For custom: create Spectrum object before Load
                elif spectrum.lower() == 'custom':
                    csv_text = element_data.get('spectrum_csv', '') or ''
                    if csv_text.strip():
                        spec_name = f"load_{load_name}"
                        if _create_spectrum_from_csv(dss, spec_name, csv_text, execute_dss_command):
                            spectrum_to_use = spec_name
                        # else: keep spectrum_to_use='custom' which may fail; fallback to defaultload
                    else:
                        spectrum_to_use = 'defaultload'  # no CSV provided
                elif spectrum.lower() == 'linear':
                    spec_name = _sanitize_opendss_name(f"load_linear_{load_name}")
                    if _create_spectrum_from_csv(dss, spec_name, SPECTRUM_LINEAR_UI_CSV, execute_dss_command):
                        spectrum_to_use = spec_name
                    else:
                        spectrum_to_use = 'defaultload'
                load_cmd += f" spectrum={spectrum_to_use}"
            # %SeriesRL: IEEE benchmark uses 100% for harmonic loads (TCR_PU, HVDC_PU)
            spectrum_upper = (spectrum or '').upper()
            if spectrum_upper in ('TCR_PU', 'HVDC_PU'):
                load_cmd += " %SeriesRL=100"  # Force 100% for benchmark alignment
            else:
                pct_series_rl = element_data.get('pctSeriesRL', '')
                if pct_series_rl not in ('', None):
                    try:
                        load_cmd += f" %SeriesRL={float(pct_series_rl)}"
                    except (ValueError, TypeError):
                        load_cmd += " %SeriesRL=100"
                else:
                    load_cmd += " %SeriesRL=100"
            # conn: TCR_PU -> delta, HVDC_PU -> wye (IEEE benchmark harmonics cancelling)
            if spectrum_upper == 'TCR_PU':
                conn_val = 'delta'
            elif spectrum_upper == 'HVDC_PU':
                conn_val = 'wye'
            else:
                conn_val = (element_data.get('conn') or element_data.get('type') or 'wye').strip().lower()
                conn_val = conn_val if conn_val in ('wye', 'delta') else 'wye'
            load_cmd += f" conn={conn_val}"
            # puXharm: Special reactance for harmonics (default 0.0 means use %SeriesRL calculation)
            pu_xharm = element_data.get('puXharm', '')
            if pu_xharm not in ('', None, '0', '0.0'):
                try:
                    load_cmd += f" puXharm={float(pu_xharm)}"
                except (ValueError, TypeError):
                    pass
            # XRharm: X/R ratio for harmonics (default 6.0, used when puXharm > 0)
            xr_harm = element_data.get('XRharm', '')
            if xr_harm not in ('', None):
                try:
                    load_cmd += f" XRharm={float(xr_harm)}"
                except (ValueError, TypeError):
                    pass
            
            # Create load using OpenDSS command
            execute_dss_command(load_cmd)
            
            # Handle in_service status AFTER creating the element
            in_service = element_data.get('in_service', True)
            
            # Convert to boolean for comparison
            is_in_service = True
            if isinstance(in_service, bool):
                is_in_service = in_service
            elif isinstance(in_service, str):
                is_in_service = in_service.lower() not in ['false', 'no', '0']
            elif in_service in [0, None]:
                is_in_service = False
            
            if not is_in_service:
                cmd = f'Load.{load_name}.enabled=no'
                print(f"[OpenDSS] {cmd}")
                dss.Text.Command(cmd)
            # print(f"Command: {load_cmd}")  # Reduced logging
            
            LoadsDict[element_name] = load_name
            LoadsDictId[element_name] = element_id
            created_elements.add(element_name)
            
        except Exception as e:
            pass
    else:
        pass
def create_static_generator_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, GeneratorsDict, GeneratorsDictId, created_elements, execute_dss_command=None):
    """Create a static generator element in OpenDSS"""

    # Wind Turbine: derive p_mw from wind speed + power curve when present
    typ = str(element_data.get('typ') or '')
    if typ.startswith('Wind Turbine'):
        raw = element_data.get('wind_power_curve_json')
        if raw is not None and (not isinstance(raw, str) or str(raw).strip()):
            try:
                points = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(points, list) and len(points) >= 2:
                    v = float(element_data.get('wind_speed_ms'))
                    approx = str(element_data.get('wind_curve_approx') or 'linear').strip().lower()
                    knots = sorted(
                        ((float(pt['v_ms']), float(pt['p_mw'])) for pt in points if isinstance(pt, dict)),
                        key=lambda x: x[0]
                    )
                    if len(knots) >= 2:
                        if v <= knots[0][0]:
                            element_data['p_mw'] = knots[0][1]
                        elif v >= knots[-1][0]:
                            element_data['p_mw'] = knots[-1][1]
                        elif approx == 'constant':
                            for i in range(len(knots) - 1):
                                v0, p0 = knots[i]
                                v1, _p1 = knots[i + 1]
                                if v0 <= v < v1:
                                    element_data['p_mw'] = p0
                                    break
                        else:
                            for i in range(len(knots) - 1):
                                v0, p0 = knots[i]
                                v1, p1 = knots[i + 1]
                                if v0 <= v <= v1:
                                    span = v1 - v0
                                    element_data['p_mw'] = p0 if abs(span) < 1e-12 else p0 + (v - v0) / span * (p1 - p0)
                                    break
            except (json.JSONDecodeError, TypeError, ValueError, KeyError):
                pass
    
    # Check for duplicates - skip if already created
    if element_name in created_elements:
        return
    
    bus_connection = element_data.get('bus')
    if bus_connection:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_connection_backend = bus_connection
        if bus_connection_backend in BusbarsDictConnectionToName:
            bus_name = BusbarsDictConnectionToName[bus_connection_backend]
        else:
            bus_name = _sanitize_opendss_name(bus_connection_backend)
        bus_voltage = BusbarsDictVoltage.get(bus_name)
        
        # Validate voltage is available
        if bus_voltage is None:
            error_msg = (
                f"Missing voltage information for bus '{bus_name}' connected to static generator '{element_name}'.\n\n"
                f"Please set the 'vn_kv' (nominal voltage) attribute for the bus element.\n\n"
                f"Available buses with voltage: {list(BusbarsDictVoltage.keys())}"
            )
            raise ValueError(error_msg)
        
        if bus_voltage is not None:
            # Handle both regular and asymmetric static generators
            if 'p_a_mw' in element_data and 'p_b_mw' in element_data and 'p_c_mw' in element_data:
                # This is an asymmetric static generator - use phase A values as main values
                p_mw_raw = element_data.get('p_a_mw')
                q_mvar_raw = element_data.get('q_a_mvar')
            else:
                # Regular static generator
                p_mw_raw = element_data.get('p_mw')
                q_mvar_raw = element_data.get('q_mvar')

            # Convert to float
            p_mw = float(p_mw_raw)
            q_mvar = float(q_mvar_raw)
            
            # Convert to kW and kVar
            p_kw = p_mw * 1000
            q_kvar = q_mvar * 1000        
            
            gen_name = element_name.replace(' ', '_')
            
            try:
                # Model=1 = constant kW and kvar, the PQ injection a pandapower sgen represents.
                # Model=3 is constant kW / constant kV, which pins the terminal at 1.0 pu and lets
                # Q float, so it must not be used here. Maxkvar/Minkvar only apply to Model=3.
                # Vminpu default 0.90 converts the generator to constant-Z when collector
                # voltage is low, so P collapses (e.g. 15 MW → ~8 MW). Keep PQ over a wide band.
                gen_cmd = (
                    f"New Generator.{gen_name} Bus1={bus_name} Phases=3 kV={bus_voltage} "
                    f"kW={p_kw:.3f} kvar={q_kvar:.3f} Model=1 "
                    f"Vminpu=0.5 Vmaxpu=2.0"
                )
                
                # Append harmonic analysis properties if provided
                spec_name = _sanitize_opendss_name(f"harm_sgen_{gen_name}")
                spectrum_resolved = _resolve_named_spectrum_for_element(
                    dss, element_data, 'defaultgen', spec_name, execute_dss_command)
                if spectrum_resolved:
                    gen_cmd += f" spectrum={spectrum_resolved}"
                xdpp = element_data.get('Xdpp', '')
                if xdpp not in ('', None):
                    try:
                        gen_cmd += f" Xdpp={float(xdpp)}"
                    except (ValueError, TypeError):
                        pass
                xrdp = element_data.get('XRdp', '')
                if xrdp not in ('', None):
                    try:
                        gen_cmd += f" XRdp={float(xrdp)}"
                    except (ValueError, TypeError):
                        pass
                
                execute_dss_command(gen_cmd)
                
                # Handle in_service status AFTER creating the element
                in_service = element_data.get('in_service', True)
                
                # Convert to boolean for comparison
                is_in_service = True
                if isinstance(in_service, bool):
                    is_in_service = in_service
                elif isinstance(in_service, str):
                    is_in_service = in_service.lower() not in ['false', 'no', '0']
                elif in_service in [0, None]:
                    is_in_service = False
                
                if not is_in_service:
                    cmd = f'Generator.{gen_name}.enabled=no'
                    print(f"[OpenDSS] {cmd}")
                    dss.Text.Command(cmd)
                # print(f"? Command: {gen_cmd}")  # Reduced logging
                
                # Store in GeneratorsDict
                GeneratorsDict[element_name] = gen_name
                GeneratorsDictId[element_name] = element_id
                created_elements.add(element_name)
                
            except Exception as e:
                pass
        else:
            pass
    else:
        pass
def create_generator_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, GeneratorsDict, GeneratorsDictId, created_elements, execute_dss_command=None):
    """Create a generator element in OpenDSS"""
    
    # Check for duplicates - skip if already created
    if element_name in created_elements:
        return
    
    bus_connection = element_data.get('bus')
    if bus_connection:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_connection_backend = bus_connection
        if bus_connection_backend in BusbarsDictConnectionToName:
            bus_name = BusbarsDictConnectionToName[bus_connection_backend]
        else:
            bus_name = _sanitize_opendss_name(bus_connection_backend)
        # Get voltage from the bus data
        bus_voltage = BusbarsDictVoltage.get(bus_name)
        
        if bus_voltage is None:
             #  ? Generator {element_name} cannot be created - no voltage information for bus {bus_name})
            return         
        # Get generator parameters with proper null handling
        p_mw_raw = element_data.get('p_mw')
        q_mvar_raw = element_data.get('q_mvar', 0)
        vm_pu_raw = element_data.get('vm_pu', 1.0)
        cos_phi_raw = element_data.get('cos_phi', 0.85)

        # Convert to float
        p_mw = float(p_mw_raw)
        q_mvar = float(q_mvar_raw)
        vm_pu = float(vm_pu_raw)
        cos_phi = float(cos_phi_raw)
        
        # Convert to kW and kVar
        p_kw = p_mw * 1000
        
        # If q_mvar is 0, calculate from cos_phi (matching pandapower generator behavior)
        if q_mvar == 0 and p_mw > 0 and cos_phi > 0 and cos_phi < 1.0:
            import math
            q_kvar = p_kw * math.tan(math.acos(cos_phi))
        else:
            q_kvar = q_mvar * 1000

        try:
            # Model=3 = constant kW / constant kV, matching pandapower gen (a PV bus).
            q_abs_sync = abs(float(q_kvar))
            maxkvar_sync = max(q_abs_sync * 2.0, 10000.0)
            gen_cmd = (
                f"New Generator.{element_name} Bus1={bus_name} kV={bus_voltage} "
                f"kW={p_kw} kvar={q_kvar} Model=3 PF={cos_phi} "
                f"Vminpu=0.5 Vmaxpu=2.0 Maxkvar={maxkvar_sync:.3f} Minkvar={-maxkvar_sync:.3f}"
            )
            
            # Add fault study parameters if provided (sub-transient reactance/resistance)
            xdss_pu_raw = element_data.get('xdss_pu')
            rdss_ohm_raw = element_data.get('rdss_ohm')
            sn_mva_raw = element_data.get('sn_mva')
            
            # Convert to float safely
            xdss_pu = float(xdss_pu_raw) if xdss_pu_raw is not None else 0.0
            rdss_ohm = float(rdss_ohm_raw) if rdss_ohm_raw is not None else 0.0
            sn_mva = float(sn_mva_raw) if sn_mva_raw is not None else 0.0
            
            # kVA rating - only add if meaningful (non-zero)
            if sn_mva > 0:
                gen_cmd += f" kva={sn_mva * 1000}"
            
            # Xdp/Xdpp - only add if meaningful (non-zero)
            if xdss_pu > 0:
                gen_cmd += f" Xdp={xdss_pu}"
                gen_cmd += f" Xdpp={xdss_pu}"
            
            # XRdp: X/R ratio for fault studies
            if xdss_pu > 0 and rdss_ohm > 0 and sn_mva > 0:
                bus_kv = float(BusbarsDictVoltage.get(bus_name, 1.0))
                x_ohm = xdss_pu * (bus_kv ** 2) / sn_mva
                xr_ratio = x_ohm / rdss_ohm
                gen_cmd += f" XRdp={xr_ratio}"
            
            # Harmonic analysis properties
            spec_name = _sanitize_opendss_name(f"harm_gen_{element_name}")
            spectrum_resolved = _resolve_named_spectrum_for_element(
                dss, element_data, 'defaultgen', spec_name, execute_dss_command)
            if spectrum_resolved:
                gen_cmd += f" spectrum={spectrum_resolved}"
            # Override Xdpp from harmonic tab if provided (may differ from short-circuit Xdpp)
            harm_xdpp = element_data.get('Xdpp')
            if harm_xdpp not in ('', None) and xdss_pu == 0:
                try:
                    xdpp_val = float(harm_xdpp)
                    if xdpp_val > 0:
                        gen_cmd += f" Xdpp={xdpp_val}"
                except (ValueError, TypeError):
                    pass
            harm_xrdp = element_data.get('XRdp')
            if harm_xrdp not in ('', None) and not (xdss_pu > 0 and rdss_ohm > 0 and sn_mva > 0):
                try:
                    gen_cmd += f" XRdp={float(harm_xrdp)}"
                except (ValueError, TypeError):
                    pass

            # Create generator using OpenDSS command
            execute_dss_command(gen_cmd)
            
            # Handle in_service status AFTER creating the element
            in_service = element_data.get('in_service', True)
            
            # Convert to boolean for comparison
            is_in_service = True
            if isinstance(in_service, bool):
                is_in_service = in_service
            elif isinstance(in_service, str):
                is_in_service = in_service.lower() not in ['false', 'no', '0']
            elif in_service in [0, None]:
                is_in_service = False
            
            if not is_in_service:
                cmd = f'Generator.{element_name}.enabled=no'
                print(f"[OpenDSS] {cmd}")
                dss.Text.Command(cmd)

            GeneratorsDict[element_name] = element_name
            GeneratorsDictId[element_name] = element_id
            created_elements.add(element_name)
            
        except Exception as e:
            pass
    else:
        pass


def _opendss_n_per_terminal(n_conductors, n_phases):
    """P/Q pairs per terminal in CktElement.Powers() / Currents()."""
    if n_conductors:
        return int(n_conductors) * 2
    return int(n_phases or 3) * 2


def _opendss_terminal_pq_kw(powers, terminal_index, n_conductors=0, n_phases=3):
    """Sum active (kW) and reactive (kvar) power for one OpenDSS terminal."""
    n_per_terminal = _opendss_n_per_terminal(n_conductors, n_phases)
    start = terminal_index * n_per_terminal
    p_kw = 0.0
    q_kvar = 0.0
    for i in range(0, min(n_per_terminal, max(0, len(powers) - start)), 2):
        p_kw += float(powers[start + i])
        if start + i + 1 < len(powers):
            q_kvar += float(powers[start + i + 1])
    return p_kw, q_kvar


def _opendss_terminal_i_ka(currents, terminal_index, n_conductors=0, n_phases=3):
    """Average phase/conductor current magnitude (kA) for one OpenDSS terminal."""
    n_per_terminal = _opendss_n_per_terminal(n_conductors, n_phases)
    start = terminal_index * n_per_terminal
    n_cond = int(n_conductors) if n_conductors else int(n_phases or 3)
    i_sum = 0.0
    count = 0
    for c in range(n_cond):
        idx = start + c * 2
        if idx + 1 < len(currents):
            i_sum += math.sqrt(float(currents[idx]) ** 2 + float(currents[idx + 1]) ** 2)
            count += 1
    return (i_sum / count / 1000.0) if count else 0.0


def vector_group_to_opendss_conns(vector_group):
    """Convert vector group notation to OpenDSS connection format
    
    Vector group examples:
    - Dyn: Delta (HV) - Wye with neutral (LV)
    - Yy: Wye (HV) - Wye (LV)
    - Yd: Wye (HV) - Delta (LV)
    - Dd: Delta (HV) - Delta (LV)
    - YNd: Wye with neutral (HV) - Delta (LV)
    
    OpenDSS format: (hv_conn lv_conn)
    Connections: wye, delta, zigzag
    """
    if not vector_group:
        return "wye wye"  # Default
    
    # Convert to uppercase for easier parsing
    vg = vector_group.upper()
    
    # Mapping for connection types
    conn_map = {
        'Y': 'wye',
        'D': 'delta',
        'Z': 'zigzag'
    }
    
    # Parse HV connection (first character)
    hv_conn = conn_map.get(vg[0], 'wye')
    
    # Parse LV connection (after 'N' if present, or second character)
    if len(vg) >= 2:
        # Skip 'N' if present (indicates neutral/grounded)
        lv_start = 2 if len(vg) > 2 and vg[1] == 'N' else 1
        if lv_start < len(vg):
            lv_conn = conn_map.get(vg[lv_start], 'wye')
        else:
            lv_conn = 'wye'
    else:
        lv_conn = 'wye'
    
    return f"{hv_conn} {lv_conn}"


def vector_group_to_opendss_conns_3w(vector_group):
    """Convert 3-winding vector group (e.g. YNdd) to OpenDSS conns format: 'wye delta delta'
    Vector group: first char=HV, then MV, then LV. N indicates neutral/grounded (ignored for conn type).
    """
    if not vector_group or not isinstance(vector_group, str):
        return "wye wye wye"
    vg = vector_group.upper().replace(' ', '')
    conn_map = {'Y': 'wye', 'D': 'delta', 'Z': 'zigzag'}
    result = []
    i = 0
    for _ in range(3):
        while i < len(vg) and vg[i] == 'N':
            i += 1
        if i < len(vg):
            result.append(conn_map.get(vg[i], 'wye'))
            i += 1
        else:
            result.append('wye')
    return ' '.join(result[:3])


def create_transformer3w_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, Transformers3WDict, Transformers3WDictId, created_elements, execute_dss_command=None):
    """Create a 3-winding transformer element in OpenDSS.
    OpenDSS syntax: New Transformer.Name Phases=3 Windings=3 XHL=... XHT=... XLT=...
    Buses=(bus1 bus2 bus3) kVs=(kv1 kv2 kv3) kVAs=(kva1 kva2 kva3) conns=(wye delta delta) %Rs=[r1 r2 r3]
    Pandapower mapping: vk_hv_percent (HV-MV) -> XHL; vk_lv_percent (HV-LV) -> XHT; vk_mv_percent (MV-LV) -> XLT
    """
    if element_name in created_elements:
        return

    hv_bus_ref = element_data.get('hv_bus')
    mv_bus_ref = element_data.get('mv_bus')
    lv_bus_ref = element_data.get('lv_bus')

    if not (hv_bus_ref and mv_bus_ref and lv_bus_ref):
        return

    hv_bus_name = BusbarsDictConnectionToName.get(hv_bus_ref) or _sanitize_opendss_name(hv_bus_ref)
    mv_bus_name = BusbarsDictConnectionToName.get(mv_bus_ref) or _sanitize_opendss_name(mv_bus_ref)
    lv_bus_name = BusbarsDictConnectionToName.get(lv_bus_ref) or _sanitize_opendss_name(lv_bus_ref)

    try:
        vn_hv = float(element_data.get('vn_hv_kv', 400))
        vn_mv = float(element_data.get('vn_mv_kv', 33))
        vn_lv = float(element_data.get('vn_lv_kv', 33))
        sn_hv = float(element_data.get('sn_hv_mva', 100)) * 1000  # kVA
        sn_mv = float(element_data.get('sn_mv_mva', 50)) * 1000
        sn_lv = float(element_data.get('sn_lv_mva', 50)) * 1000
        vk_hv = float(element_data.get('vk_hv_percent', 15))
        vk_mv = float(element_data.get('vk_mv_percent', 15))
        vk_lv = float(element_data.get('vk_lv_percent', 15))
        vkr_hv = float(element_data.get('vkr_hv_percent', 1))
        vkr_mv = float(element_data.get('vkr_mv_percent', 1))
        vkr_lv = float(element_data.get('vkr_lv_percent', 1))
        pfe_kw = float(element_data.get('pfe_kw', 0))
        i0_percent = float(element_data.get('i0_percent', 0))
        vector_group = element_data.get('vector_group', 'YNdd')

        # Base conversion - this is the subtle one.
        #
        # Pandapower trafo3w (https://pandapower.readthedocs.io/en/latest/elements/trafo3w.html)
        # defines each per-pair short-circuit voltage on the MIN apparent power of the pair:
        #   vk_hv_percent on min(sn_hv, sn_mv)   (HV-MV pair)
        #   vk_mv_percent on min(sn_mv, sn_lv)   (MV-LV pair)
        #   vk_lv_percent on min(sn_hv, sn_lv)   (HV-LV pair)
        #
        # OpenDSS Transformer with Windings=3 expects XHL/XHT/XLT on the WINDING-1 kVA base
        # (https://opendss.epri.com/Three-WindingTransformers.html and OpenDSS primer). With
        # winding 1 = HV, winding 2 = MV, winding 3 = LV we have XHL = 1-2 (HV-MV),
        # XHT = 1-3 (HV-LV), XLT = 2-3 (MV-LV), all referenced to sn_hv.
        #
        # The conversion factor for each pair is sn_hv / min(sn_x, sn_y). Without it the
        # 500/250/250 and 500/500/15 style transformers get impedances that are off by a
        # factor of 2 to ~33, which drives large voltage and reactive-power differences
        # versus pandapower.
        sn_hv_mva_val = sn_hv / 1000.0  # sn_hv above is already converted to kVA
        sn_mv_mva_val = sn_mv / 1000.0
        sn_lv_mva_val = sn_lv / 1000.0
        base_hm = min(sn_hv_mva_val, sn_mv_mva_val) if min(sn_hv_mva_val, sn_mv_mva_val) > 0 else sn_hv_mva_val
        base_ml = min(sn_mv_mva_val, sn_lv_mva_val) if min(sn_mv_mva_val, sn_lv_mva_val) > 0 else sn_hv_mva_val
        base_lh = min(sn_hv_mva_val, sn_lv_mva_val) if min(sn_hv_mva_val, sn_lv_mva_val) > 0 else sn_hv_mva_val

        vk_hm_snhv = vk_hv * sn_hv_mva_val / base_hm
        vk_ml_snhv = vk_mv * sn_hv_mva_val / base_ml
        vk_lh_snhv = vk_lv * sn_hv_mva_val / base_lh
        vkr_hm_snhv = vkr_hv * sn_hv_mva_val / base_hm
        vkr_ml_snhv = vkr_mv * sn_hv_mva_val / base_ml
        vkr_lh_snhv = vkr_lv * sn_hv_mva_val / base_lh

        xhl = math.sqrt(max(0.0, vk_hm_snhv ** 2 - vkr_hm_snhv ** 2))
        xht = math.sqrt(max(0.0, vk_lh_snhv ** 2 - vkr_lh_snhv ** 2))
        xlt = math.sqrt(max(0.0, vk_ml_snhv ** 2 - vkr_ml_snhv ** 2))

        # Per-winding resistances for OpenDSS %Rs=[r1 r2 r3].
        # OpenDSS treats each %R_i as the resistance of winding i on winding i's own kVA base.
        # Starting from the three per-pair vkr values on sn_hv base, apply the delta-to-star
        # conversion pandapower itself uses (see trafo3w docs "Electric Model"):
        #   R_H = 1/2 (vkr_hm + vkr_lh - vkr_ml)
        #   R_M = 1/2 (vkr_ml + vkr_hm - vkr_lh)
        #   R_L = 1/2 (vkr_ml + vkr_lh - vkr_hm)
        # then rescale R_M and R_L to their own winding bases.
        rH_snhv = 0.5 * (vkr_hm_snhv + vkr_lh_snhv - vkr_ml_snhv)
        rM_snhv = 0.5 * (vkr_ml_snhv + vkr_hm_snhv - vkr_lh_snhv)
        rL_snhv = 0.5 * (vkr_ml_snhv + vkr_lh_snhv - vkr_hm_snhv)
        r1_pct = max(0.0, rH_snhv)
        r2_pct = max(0.0, rM_snhv * (sn_mv_mva_val / sn_hv_mva_val)) if sn_hv_mva_val > 0 else 0.0
        r3_pct = max(0.0, rL_snhv * (sn_lv_mva_val / sn_hv_mva_val)) if sn_hv_mva_val > 0 else 0.0

        conns = vector_group_to_opendss_conns_3w(vector_group)

        # OLTC taps - must match create_transformer_element (2w) and pandapower_electrisim 3w branch.
        # Previously 3w transformers were always exported at Taps=1, which skewed voltages and slack Q.
        tap_pos_raw = element_data.get('tap_pos', '0')
        tap_step_percent_raw = element_data.get('tap_step_percent', '1.5')
        tap_side = str(element_data.get('tap_side', 'hv')).lower()
        try:
            tap_pos = float(tap_pos_raw)
        except (TypeError, ValueError):
            tap_pos = 0.0
        try:
            tap_step_percent = float(tap_step_percent_raw)
        except (TypeError, ValueError):
            tap_step_percent = 1.5
        tap_change = tap_pos * tap_step_percent / 100.0
        tap_hv, tap_mv, tap_lv = 1.0, 1.0, 1.0
        if tap_side == 'hv':
            tap_hv = 1.0 + tap_change
        elif tap_side == 'mv':
            tap_mv = 1.0 + tap_change
        elif tap_side == 'lv':
            tap_lv = 1.0 + tap_change

        # No-load loss and magnetizing
        noloadloss = (pfe_kw / sn_hv * 100) if sn_hv > 0 else 0

        cmd_parts = [
            f"New Transformer.{element_name} Phases=3 Windings=3",
            f"XHL={xhl} XHT={xht} XLT={xlt}",
            f"Buses=({hv_bus_name} {mv_bus_name} {lv_bus_name})",
            f"kVs=({vn_hv} {vn_mv} {vn_lv})",
            f"kVAs=({sn_hv} {sn_mv} {sn_lv})",
            f"conns=({conns})",
            f"%Rs=[{r1_pct} {r2_pct} {r3_pct}]",
        ]
        # Only pass Taps when off-nominal. Explicit Taps=[1 1 1] on Windings=3 has been observed to
        # yield Converged=True with all bus Voltages() = 0; omit property = default 1.0 per winding.
        # Use Taps=(...) array form (matches conns=(...) in DSS) when taps are non-neutral.
        if max(abs(tap_hv - 1.0), abs(tap_mv - 1.0), abs(tap_lv - 1.0)) > 1e-9:
            cmd_parts.append(f"Taps=({tap_hv} {tap_mv} {tap_lv})")
        if noloadloss > 0:
            cmd_parts.append(f"%noloadloss={noloadloss}")
        if i0_percent > 0:
            cmd_parts.append(f"%imag={i0_percent}")

        transformer_cmd = " ".join(cmd_parts)
        execute_dss_command(transformer_cmd)

        in_service = element_data.get('in_service', True)
        is_in_service = in_service if isinstance(in_service, bool) else str(in_service).lower() not in ('false', 'no', '0')
        if not is_in_service:
            execute_dss_command(f'Transformer.{element_name}.enabled=no')

        Transformers3WDict[element_name] = element_name
        Transformers3WDictId[element_name] = element_id
        created_elements.add(element_name)
    except Exception as e:
        pass


def create_transformer_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, TransformersDict, TransformersDictId, created_elements, execute_dss_command=None):
    """Create a transformer element in OpenDSS"""
    
    # Check for duplicates - skip if already created
    if element_name in created_elements:
        return
    
    bus_from_ref = element_data.get('busFrom') or element_data.get('hv_bus')
    bus_to_ref = element_data.get('busTo') or element_data.get('lv_bus')

    if bus_from_ref and bus_to_ref:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_from_ref_backend = bus_from_ref
        bus_to_ref_backend = bus_to_ref
        
        # Resolve bus names from references (could be IDs or names)
        if bus_from_ref_backend in BusbarsDictConnectionToName:
            bus_from_name = BusbarsDictConnectionToName[bus_from_ref_backend]
        else:
            bus_from_name = _sanitize_opendss_name(bus_from_ref_backend)
            
        if bus_to_ref_backend in BusbarsDictConnectionToName:
            bus_to_name = BusbarsDictConnectionToName[bus_to_ref_backend]
        else:
            bus_to_name = _sanitize_opendss_name(bus_to_ref_backend)
        
        
        try:
            # Get voltage ratings from the connected buses
            bus_from_voltage = BusbarsDictVoltage.get(bus_from_name)
            bus_to_voltage = BusbarsDictVoltage.get(bus_to_name)
            
            # Get transformer parameters from frontend data - no defaults
            sn_mva_raw = element_data.get('sn_mva')
            vk_percent_raw = element_data.get('vk_percent')
            vkr_percent_raw = element_data.get('vkr_percent')
            vn_hv_kv_raw = element_data.get('vn_hv_kv')
            vn_lv_kv_raw = element_data.get('vn_lv_kv')
            vector_group = element_data.get('vector_group', 'Dyn')  # Default to Dyn if not specified
            
            # Validate that both bus voltages are available
            # No defaults or fallbacks - user must provide proper voltage information
            if bus_from_voltage is None:
                error_msg = (
                    f"Missing voltage information for bus '{bus_from_name}' connected to transformer '{element_name}'.\n\n"
                    f"Please ensure:\n"
                    f"1. The bus element has a 'vn_kv' (nominal voltage) attribute set, OR\n"
                    f"2. The transformer has 'vn_hv_kv' parameter set\n\n"
                    f"Available buses with voltage: {list(BusbarsDictVoltage.keys())}"
                )
                raise ValueError(error_msg)
            
            if bus_to_voltage is None:
                error_msg = (
                    f"Missing voltage information for bus '{bus_to_name}' connected to transformer '{element_name}'.\n\n"
                    f"Please ensure:\n"
                    f"1. The bus element has a 'vn_kv' (nominal voltage) attribute set, OR\n"
                    f"2. The transformer has 'vn_lv_kv' parameter set\n\n"
                    f"Available buses with voltage: {list(BusbarsDictVoltage.keys())}"
                )
                raise ValueError(error_msg)
           
            
            # Convert to float
            sn_mva = float(sn_mva_raw)
            vk_percent = float(vk_percent_raw)
            vkr_percent = float(vkr_percent_raw)

            # Prefer explicit transformer rated voltages over bus vn_kv (import may tag all buses as HV)
            if vn_hv_kv_raw not in (None, '', '0') and vn_lv_kv_raw not in (None, '', '0'):
                kv_hv = float(vn_hv_kv_raw)
                kv_lv = float(vn_lv_kv_raw)
            else:
                v_from = float(bus_from_voltage)
                v_to = float(bus_to_voltage)
                if v_from >= v_to:
                    kv_hv, kv_lv = v_from, v_to
                else:
                    kv_hv, kv_lv = v_to, v_from

            if float(bus_from_voltage) >= float(bus_to_voltage):
                bus_hv_name, bus_lv_name = bus_from_name, bus_to_name
            else:
                bus_hv_name, bus_lv_name = bus_to_name, bus_from_name
            
            # Convert MVA to kVA
            sn_kva = sn_mva * 1000
            
            # Convert vector group to OpenDSS connection format
            conns = vector_group_to_opendss_conns(vector_group)
            
            # Get loss parameters from frontend
            pfe_kw_raw = element_data.get('pfe_kw', '0')
            i0_percent_raw = element_data.get('i0_percent', '0')
            
            # Convert loss parameters to float
            pfe_kw = float(pfe_kw_raw)
            i0_percent = float(i0_percent_raw)
            
            # Get tap parameters from frontend
            tap_pos_raw = element_data.get('tap_pos', '0')
            tap_step_percent_raw = element_data.get('tap_step_percent', '1.5')
            tap_side = element_data.get('tap_side', 'hv')
            
            # Convert to numbers
            tap_pos = float(tap_pos_raw)
            tap_step_percent = float(tap_step_percent_raw)
            
            # Calculate tap values for each winding
            # Tap is a multiplier: 1.0 = neutral position
            # tap_pos * tap_step_percent gives the percentage change
            tap_change = tap_pos * tap_step_percent / 100.0
            
            if tap_side.lower() == 'hv':
                # Tap on HV side (winding 1)
                tap_hv = 1.0 + tap_change
                tap_lv = 1.0
            else:
                # Tap on LV side (winding 2)
                tap_hv = 1.0
                tap_lv = 1.0 + tap_change
            
            # Calculate no-load loss percentage from iron losses
            # %noloadloss = (total_iron_losses_kw / rated_kVA) * 100
            # This is a scalar property in OpenDSS applied to the transformer core
            if pfe_kw > 0 and sn_kva > 0:
                noloadloss_percent = (pfe_kw / sn_kva) * 100
            else:
                noloadloss_percent = 0
            
            # Split the winding resistance between HV and LV sides
            # Total %Rs should be split approximately 50/50 between windings for typical transformers
            rs_hv = vkr_percent / 2.0
            rs_lv = vkr_percent / 2.0
            
            # CRITICAL: OpenDSS XHL is the REACTANCE component only (not total impedance)
            # pandapower vk_percent = |Z_sc| = sqrt(vkr_percent^2 + vkx_percent^2)
            # OpenDSS XHL = vkx_percent = sqrt(vk_percent^2 - vkr_percent^2)
            if vk_percent > vkr_percent:
                xhl_percent = math.sqrt(vk_percent**2 - vkr_percent**2)
            else:
                xhl_percent = vk_percent  # Fallback: if vkr >= vk (shouldn't happen)
            
            # Create complete OpenDSS transformer command with calculated taps and losses
            # XHL = reactive component, %Rs = resistive components per winding
            transformer_cmd = f"New Transformer.{element_name} Phases=3 Windings=2 Buses=({bus_hv_name} {bus_lv_name}) Conns=({conns}) kVs=({kv_hv} {kv_lv}) kVAs=({sn_kva} {sn_kva}) XHL={xhl_percent} %Rs=[{rs_hv} {rs_lv}] Taps=[{tap_hv} {tap_lv}]"
            
            # Add loss parameters if they are non-zero
            # %noloadloss and %imag are scalar properties in OpenDSS (not per-winding arrays)
            if noloadloss_percent > 0:
                transformer_cmd += f" %noloadloss={noloadloss_percent}"
            
            # %imag is the magnetizing current as % of rated current (scalar property)
            if i0_percent > 0:
                transformer_cmd += f" %imag={i0_percent}"
            
            # Harmonic analysis property: XRConst
            # When Yes, X/R ratio is constant for all frequencies (series RL model)
            xr_const = element_data.get('XRConst', 'No')
            if xr_const and str(xr_const).lower() in ('yes', 'true'):
                transformer_cmd += " XRConst=Yes"
            
            execute_dss_command(transformer_cmd)
            
            # Handle in_service status AFTER creating the element
            in_service = element_data.get('in_service', True)
            
            # Convert to boolean for comparison
            is_in_service = True
            if isinstance(in_service, bool):
                is_in_service = in_service
            elif isinstance(in_service, str):
                is_in_service = in_service.lower() not in ['false', 'no', '0']
            elif in_service in [0, None]:
                is_in_service = False
            
            if not is_in_service:
                cmd = f'Transformer.{element_name}.enabled=no'
                print(f"[OpenDSS] {cmd}")
                dss.Text.Command(cmd)
            # print(f"Command: {transformer_cmd}")  # Reduced logging
            
            # Log loss parameters if they are included
            if noloadloss_percent > 0 or i0_percent > 0:
                pass
            TransformersDict[element_name] = element_name
            TransformersDictId[element_name] = element_id
            created_elements.add(element_name)
            
        except Exception as e:
            try:
                pass
            except Exception as debug_e:
                pass
    else:
        pass
def create_shunt_reactor_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, ShuntsDict, ShuntsDictId, created_elements, execute_dss_command=None):
    """Create a shunt reactor element in OpenDSS"""
    
    # Check for duplicates - skip if already created
    if element_name in created_elements:
        return
    
    bus_connection = element_data.get('bus')
    if bus_connection:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_connection_backend = bus_connection
        if bus_connection_backend in BusbarsDictConnectionToName:
            bus_name = BusbarsDictConnectionToName[bus_connection_backend]
        else:
            bus_name = _sanitize_opendss_name(bus_connection_backend)
        # Get voltage from the bus data
        bus_voltage = BusbarsDictVoltage.get(bus_name)
        
        # Validate voltage is available
        if bus_voltage is None:
            error_msg = (
                f"Missing voltage information for bus '{bus_name}' connected to shunt reactor '{element_name}'.\n\n"
                f"Please set the 'vn_kv' (nominal voltage) attribute for the bus element.\n\n"
                f"Available buses with voltage: {list(BusbarsDictVoltage.keys())}"
            )
            raise ValueError(error_msg)
        
        # Nominal P/Q at 1.0 pu — same step / characteristic-table rules as pandapower.
        q_fallback = _opendss_float(element_data.get('q_mvar'), 0.0)
        p_fallback = _opendss_float(element_data.get('p_mw'), 0.0)
        characteristic_rows = _opendss_parse_shunt_characteristic_rows(
            element_data.get('shunt_characteristic_table_json'))
        line_flow_bands = _opendss_parse_line_flow_step_table(
            element_data.get('line_flow_step_table_json'))
        use_characteristic = _opendss_is_true(element_data.get('step_dependency_table')) and bool(characteristic_rows)
        step_electrisim = _opendss_float(element_data.get('step', 1), 1.0)
        max_step_electrisim = _opendss_float(element_data.get('max_step', 1), 1.0)
        zero_based = _opendss_shunt_uses_zero_based(
            step_electrisim, characteristic_rows, line_flow_bands)
        step_pp = _opendss_shunt_step_to_pp(step_electrisim, zero_based)
        max_step_pp = _opendss_shunt_max_step_to_pp(max_step_electrisim, zero_based)
        if use_characteristic:
            p_mw, q_mvar = _opendss_shunt_nominals_for_step(
                characteristic_rows, step_electrisim, p_fallback, q_fallback)
        else:
            p_mw = p_fallback * float(step_pp)
            q_mvar = q_fallback * float(step_pp)

        q_kvar = q_mvar * 1000.0

        # OpenDSS Reactor element: constant impedance (kV + kvar), matches pandapower shunt.
        # Optional Rp = V_LL^2 / P_total for no-load losses when p_mw > 0.
        # Sign convention (aligned with pandapower create_shunt):
        #   q_mvar > 0  -> inductive (absorbs Q)  -> OpenDSS Reactor with kvar > 0
        #   q_mvar < 0  -> capacitive (delivers Q) -> model as OpenDSS Capacitor
        try:
            reactor_name = f"ShuntReactor_{element_name}"
            dss_class = 'Reactor' if q_kvar >= 0 else 'Capacitor'

            if abs(q_kvar) < 1.0:
                print(f"[OpenDSS] Skipping Reactor {reactor_name}: kvar={q_kvar:.6f} is too small (would produce NaN impedance)")
                ShuntsDict[element_name] = reactor_name
                ShuntsDictId[element_name] = element_id
                created_elements.add(element_name)
                return

            if q_kvar >= 0:
                cmd_parts = [f"New Reactor.{reactor_name} Bus1={bus_name} Phases=3 kV={bus_voltage} kvar={q_kvar:.0f}"]
                rp_ohms = _opendss_shunt_rp_ohms(bus_voltage, p_mw)
                if rp_ohms is not None:
                    cmd_parts.append(f" Rp={rp_ohms:.2f}")
                execute_dss_command("".join(cmd_parts))
            else:
                cap_cmd = (f"New Capacitor.{reactor_name} Bus1={bus_name} Phases=3 "
                           f"kV={bus_voltage} kvar={abs(q_kvar):.0f}")
                execute_dss_command(cap_cmd)
            
            in_service = element_data.get('in_service', True)
            is_in_service = True
            if isinstance(in_service, bool):
                is_in_service = in_service
            elif isinstance(in_service, str):
                is_in_service = in_service.lower() not in ['false', 'no', '0']
            elif in_service in [0, None]:
                is_in_service = False
            
            if not is_in_service:
                cmd = f'{dss_class}.{reactor_name}.enabled=no'
                print(f"[OpenDSS] {cmd}")
                dss.Text.Command(cmd)

            ShuntsDict[element_name] = reactor_name
            ShuntsDictId[element_name] = element_id
            created_elements.add(element_name)

            vm_set = _opendss_float(element_data.get('vm_set_pu'), 1.0)
            if vm_set is None:
                vm_set = 1.0
            try:
                increment = int(_opendss_float(element_data.get('shunt_control_increment', 1), 1))
            except (TypeError, ValueError):
                increment = 1
            if increment < 1:
                increment = 1
            tol = _opendss_float(element_data.get('shunt_control_tol'), 1e-3)
            _opendss_shunt_meta[element_name] = {
                'reactor_name': reactor_name,
                'dss_class': dss_class,
                'bus_name': bus_name,
                'bus_voltage': float(bus_voltage) if bus_voltage is not None else None,
                'p_fallback': p_fallback,
                'q_fallback': q_fallback,
                'step': int(step_pp),
                'max_step': int(max_step_pp),
                'zero_based': bool(zero_based),
                'use_characteristic': bool(use_characteristic),
                'characteristic_rows': characteristic_rows,
                'discrete_shunt_control': _opendss_is_true(element_data.get('discrete_shunt_control')) and is_in_service,
                'vm_set_pu': float(vm_set),
                'increment': increment,
                'tol': float(tol) if tol is not None else 1e-3,
                'line_flow_step_control': (
                    _opendss_is_true(element_data.get('line_flow_step_control')) and is_in_service
                ),
                'line_flow_reference_line_id': element_data.get('line_flow_reference_line_id') or '',
                'line_flow_bands': line_flow_bands,
                'line_flow_p_use_abs': _opendss_is_true(
                    element_data.get('line_flow_p_use_abs', True)),
                'line_flow_p_reference': element_data.get('line_flow_p_reference') or 'p_from_mw',
            }
        except Exception as e:
            pass
    else:
        pass
def create_capacitor_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, CapacitorsDict, CapacitorsDictId, created_elements, execute_dss_command=None):
    """Create a capacitor element in OpenDSS"""
    
    # Check for duplicates - skip if already created
    if element_name in created_elements:
        return
    
    bus_connection = element_data.get('bus')
    if bus_connection:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_connection_backend = bus_connection
        if bus_connection_backend in BusbarsDictConnectionToName:
            bus_name = BusbarsDictConnectionToName[bus_connection_backend]
        else:
            bus_name = _sanitize_opendss_name(bus_connection_backend)
        bus_voltage = BusbarsDictVoltage.get(bus_name)
        
        # Validate voltage is available
        if bus_voltage is None:
            error_msg = (
                f"Missing voltage information for bus '{bus_name}' connected to capacitor '{element_name}'.\n\n"
                f"Please set the 'vn_kv' (nominal voltage) attribute for the bus element.\n\n"
                f"Available buses with voltage: {list(BusbarsDictVoltage.keys())}"
            )
            raise ValueError(error_msg)
        
        if bus_voltage is not None:
            # Get capacitor parameters with proper null handling
            q_mvar_raw = element_data.get('q_mvar')
            
            # Check if required parameter is present
            if q_mvar_raw is None:
               # ? Capacitor {element_name} cannot be created - missing q_mvar parameter")
                return
            
            # Convert to float
            q_mvar = float(q_mvar_raw)
            
            # Convert to kVar
            q_kvar = q_mvar * 1000           
            
            
            try:
                # Use bus name directly - OpenDSS will create bus automatically
                simple_cmd = f"New Capacitor.{element_name} Bus1={bus_name} kvar={abs(q_kvar)} kV={bus_voltage}"
                execute_dss_command(simple_cmd)
                # print(f"Command: {simple_cmd}")  # Reduced logging
                
                # Handle in_service status AFTER creating the element
                in_service = element_data.get('in_service', True)
                
                # Convert to boolean for comparison
                is_in_service = True
                if isinstance(in_service, bool):
                    is_in_service = in_service
                elif isinstance(in_service, str):
                    is_in_service = in_service.lower() not in ['false', 'no', '0']
                elif in_service in [0, None]:
                    is_in_service = False
                
                if not is_in_service:
                    cmd = f'Capacitor.{element_name}.enabled=no'
                    print(f"[OpenDSS] {cmd}")
                    dss.Text.Command(cmd)

                CapacitorsDict[element_name] = element_name
                CapacitorsDictId[element_name] = element_id
                created_elements.add(element_name)
                
            except Exception as e:
                pass
        else:
            pass
    else:
        pass


# --- Inverter control helpers (OpenDSS InvControl + XYCurve) ---
# Reference: https://opendss.epri.com/InvControl.html

_IEEE_1547_VV_X = [0.92, 0.98, 1.02, 1.08]
_IEEE_1547_VV_Y = [0.44, 0.0, -0.44, -0.44]
_IEEE_1547_VW_X = [1.06, 1.1]
_IEEE_1547_VW_Y = [1.0, 0.0]
_DEFAULT_WATTVAR_X = [0.2, 0.5, 1.0]
_DEFAULT_WATTVAR_Y = [0.44, 0.22, 0.0]
_INVCONTROL_TIME_MODES = ('VOLTVAR', 'VOLTWATT', 'WATTPF', 'WATTVAR', 'DYNAMICREACCURR')
_DER_TYP_PREFIXES = ('Storage', 'PVSystem')


def _parse_float_array(value, default=None):
    """Parse space- or comma-separated floats from frontend string."""
    if default is None:
        default = []
    if value is None or value == '':
        return list(default)
    if isinstance(value, (list, tuple)):
        try:
            return [float(v) for v in value]
        except (TypeError, ValueError):
            return list(default)
    try:
        parts = str(value).replace(',', ' ').split()
        return [float(p) for p in parts if p.strip()]
    except (TypeError, ValueError):
        return list(default)


def _element_typ_is_der(typ):
    t = str(typ or '')
    return any(t.startswith(p) for p in _DER_TYP_PREFIXES)


def _in_data_needs_time_control(in_data):
    """Return True if the model contains controls that need queued control actions."""
    for x in in_data:
        try:
            element_data = in_data[x]
            typ = str(element_data.get('typ', ''))
            if typ.startswith(('RegControl', 'CapControl', 'StorageController')):
                return True
            if not _element_typ_is_der(element_data.get('typ', '')):
                continue
            mode = str(element_data.get('inv_control_mode', 'NONE')).upper()
            if mode in _INVCONTROL_TIME_MODES:
                return True
        except Exception:
            continue
    return False


def _resolve_controlled_element(reference, elements, buses=None):
    """Resolve a canvas name/id (or a bus reference) to an OpenDSS element name."""
    reference = str(reference or '').strip()
    if not reference:
        return None
    resolved = _resolve_in_dict(reference, elements)
    if resolved:
        return resolved
    safe_reference = _sanitize_opendss_name(reference)
    if safe_reference in elements:
        return elements[safe_reference]
    if buses:
        for element_name in elements:
            if str(element_name).lower() == reference.lower():
                return element_name
    return None


def _dss_bool(value, default=True):
    if value is None or value == '':
        return default
    return str(value).strip().lower() not in ('false', 'no', '0', 'off')


def create_regcontrol_element(dss, element_data, element_name, element_id, TransformersDict,
                              TransformersDictId, BusbarsDictConnectionToName,
                              execute_dss_command=None, all_elements=None):
    """Create an OpenDSS RegControl attached to an existing Transformer."""
    if execute_dss_command is None:
        execute_dss_command = dss.Text.Command
    transformer_ref = element_data.get('transformer') or element_data.get('element') or element_data.get('bus')
    transformer = _resolve_controlled_element(
        transformer_ref, TransformersDict, BusbarsDictConnectionToName)
    if not transformer and all_elements:
        for candidate in (all_elements.values() if hasattr(all_elements, 'values') else all_elements):
            if str(candidate.get('typ', '')).startswith(('Transformer', 'Two Winding')) and str(transformer_ref) in (
                str(candidate.get('busFrom', '')), str(candidate.get('busTo', '')), str(candidate.get('bus', ''))
            ):
                transformer = _resolve_controlled_element(candidate.get('name'), TransformersDict)
                break
    if not transformer:
        print(f'[OpenDSS] RegControl {element_name} skipped: transformer not found ({transformer_ref})')
        return
    winding = int(float(element_data.get('winding', 2) or 2))
    vreg = float(element_data.get('vreg', 120) or 120)
    band = float(element_data.get('band', 3) or 3)
    ptratio = float(element_data.get('ptratio', 60) or 60)
    ctprim = float(element_data.get('ctprim', 300) or 300)
    delay = float(element_data.get('delaying', element_data.get('delay', 15)) or 0)
    enabled = 'yes' if _dss_bool(element_data.get('enabled'), True) else 'no'
    execute_dss_command(
        f'New RegControl.{element_name} Transformer={transformer} Winding={winding} '
        f'VReg={vreg} Band={band} PTRatio={ptratio} CTPrim={ctprim} Delay={delay} Enabled={enabled}')


def create_capcontrol_element(dss, element_data, element_name, element_id, CapacitorsDict,
                              CapacitorsDictId, BusbarsDictConnectionToName,
                              execute_dss_command=None, all_elements=None):
    """Create an OpenDSS CapControl attached to an existing Capacitor."""
    if execute_dss_command is None:
        execute_dss_command = dss.Text.Command
    capacitor_ref = element_data.get('capacitor') or element_data.get('element') or element_data.get('bus')
    capacitor = _resolve_controlled_element(
        capacitor_ref, CapacitorsDict, BusbarsDictConnectionToName)
    if not capacitor and all_elements:
        for candidate in (all_elements.values() if hasattr(all_elements, 'values') else all_elements):
            if str(candidate.get('typ', '')).startswith('Capacitor') and str(capacitor_ref) == str(candidate.get('bus', '')):
                capacitor = _resolve_controlled_element(candidate.get('name'), CapacitorsDict)
                break
    if not capacitor:
        print(f'[OpenDSS] CapControl {element_name} skipped: capacitor not found ({capacitor_ref})')
        return
    control_type = str(element_data.get('control_type', element_data.get('type', 'Voltage')) or 'Voltage').capitalize()
    if control_type.lower() == 'kvar':
        control_type = 'kvar'
    on_setting = float(element_data.get('on_setting', element_data.get('onsetting', 115)) or 0)
    off_setting = float(element_data.get('off_setting', element_data.get('offsetting', 125)) or 0)
    ct_ratio = float(element_data.get('ctratio', 1) or 1)
    pt_ratio = float(element_data.get('ptratio', 1) or 1)
    delay = float(element_data.get('delay', 15) or 0)
    enabled = 'yes' if _dss_bool(element_data.get('enabled'), True) else 'no'
    execute_dss_command(
        f'New CapControl.{element_name} Capacitor={capacitor} Type={control_type} '
        f'ONSetting={on_setting} OFFSetting={off_setting} CTRatio={ct_ratio} '
        f'PTRatio={pt_ratio} Delay={delay} Enabled={enabled}')


def create_storagecontroller_element(dss, element_data, element_name, element_id, StoragesDict,
                                     StoragesDictId, execute_dss_command=None):
    """Create an OpenDSS StorageController and put controlled storage in EXTERNAL mode."""
    if execute_dss_command is None:
        execute_dss_command = dss.Text.Command
    storage_ref = element_data.get('element') or element_data.get('storage') or ''
    references = storage_ref if isinstance(storage_ref, (list, tuple)) else str(storage_ref).replace(';', ',').split(',')
    storage_names = [
        _resolve_controlled_element(reference, StoragesDict)
        for reference in references
        if str(reference).strip()
    ]
    storage_names = [name for name in storage_names if name]
    if not storage_names:
        print(f'[OpenDSS] StorageController {element_name} skipped: storage not found ({storage_ref})')
        return
    mode = str(element_data.get('mode', 'PeakShave') or 'PeakShave')
    kw_target = float(element_data.get('kwtarget', element_data.get('kWTarget', 0)) or 0)
    reserve = float(element_data.get('pct_reserve', element_data.get('reserve', 20)) or 0)
    enabled = 'yes' if _dss_bool(element_data.get('enabled'), True) else 'no'
    storage_target = (
        f'Element=Storage.{storage_names[0]}'
        if len(storage_names) == 1
        else f'ElementList=[{" ".join("Storage." + name for name in storage_names)}]'
    )
    execute_dss_command(
        f'New StorageController.{element_name} {storage_target} Mode={mode} '
        f'kWTarget={kw_target} %Reserve={reserve} Enabled={enabled}')
    for storage_name in storage_names:
        execute_dss_command(f'Storage.{storage_name}.DispMode=EXTERNAL')


def _resolve_voltvar_curve(element_data):
    """Return (xarray, yarray) for Volt-VAR curve from DER parameters."""
    preset = str(element_data.get('vv_curve_preset', 'IEEE_1547')).upper()
    if preset == 'IEEE_1547':
        return list(_IEEE_1547_VV_X), list(_IEEE_1547_VV_Y)
    x_vals = _parse_float_array(element_data.get('vv_xarray'), _IEEE_1547_VV_X)
    y_vals = _parse_float_array(element_data.get('vv_yarray'), _IEEE_1547_VV_Y)
    if len(x_vals) < 2 or len(y_vals) < 2 or len(x_vals) != len(y_vals):
        return list(_IEEE_1547_VV_X), list(_IEEE_1547_VV_Y)
    return x_vals, y_vals


def _resolve_voltwatt_curve(element_data):
    """Return (xarray, yarray) for Volt-Watt curve from DER parameters."""
    preset = str(element_data.get('vw_curve_preset', 'IEEE_1547')).upper()
    if preset == 'IEEE_1547':
        return list(_IEEE_1547_VW_X), list(_IEEE_1547_VW_Y)
    x_vals = _parse_float_array(element_data.get('vw_xarray'), _IEEE_1547_VW_X)
    y_vals = _parse_float_array(element_data.get('vw_yarray'), _IEEE_1547_VW_Y)
    if len(x_vals) < 2 or len(y_vals) < 2 or len(x_vals) != len(y_vals):
        return list(_IEEE_1547_VW_X), list(_IEEE_1547_VW_Y)
    return x_vals, y_vals


def _resolve_wattpf_curve(element_data):
    """Return (xarray, yarray) for Watt-PF curve from DER parameters."""
    x_vals = _parse_float_array(element_data.get('wattpf_xarray'), [0.0, 0.5, 1.0])
    y_vals = _parse_float_array(element_data.get('wattpf_yarray'), [1.0, 0.98, 0.95])
    if len(x_vals) < 2 or len(y_vals) < 2 or len(x_vals) != len(y_vals):
        return [0.0, 0.5, 1.0], [1.0, 0.98, 0.95]
    return x_vals, y_vals


def _resolve_wattvar_curve(element_data):
    """Return (xarray, yarray) for Watt-VAR curve from DER parameters."""
    x_vals = _parse_float_array(element_data.get('wattvar_xarray'), _DEFAULT_WATTVAR_X)
    y_vals = _parse_float_array(element_data.get('wattvar_yarray'), _DEFAULT_WATTVAR_Y)
    if len(x_vals) < 2 or len(y_vals) < 2 or len(x_vals) != len(y_vals):
        return list(_DEFAULT_WATTVAR_X), list(_DEFAULT_WATTVAR_Y)
    return x_vals, y_vals


def create_xycurve_element(dss, curve_name, xarray, yarray, execute_dss_command=None):
    """Create an OpenDSS XYCurve for InvControl volt-var or watt-pf functions."""
    if execute_dss_command is None:
        execute_dss_command = dss.Text.Command
    safe_name = _sanitize_opendss_name(curve_name)
    npts = len(xarray)
    if npts < 2 or npts != len(yarray):
        return None
    x_str = ' '.join(str(v) for v in xarray)
    y_str = ' '.join(str(v) for v in yarray)
    cmd = f"New XYCurve.{safe_name} npts={npts} xarray=[{x_str}] yarray=[{y_str}]"
    execute_dss_command(cmd)
    return safe_name


def create_invcontrol_for_der(dss, der_class, element_name, element_data, execute_dss_command=None):
    """Create InvControl linked to a Storage or PVSystem. Returns True if created."""
    if execute_dss_command is None:
        execute_dss_command = dss.Text.Command
    mode = str(element_data.get('inv_control_mode', 'NONE')).upper()
    if mode in ('NONE', '', 'OFF', 'FIXED_Q', 'FIXED_PF'):
        return False

    der_class = str(der_class or 'Storage').strip()
    if der_class not in ('Storage', 'PVSystem'):
        der_class = 'Storage'

    der_name = _sanitize_opendss_name(element_name)
    ctrl_name = _sanitize_opendss_name(f"{element_name}_InvCtrl")
    der_list = f"{der_class}.{der_name}"

    if mode == 'VOLTVAR':
        x_vals, y_vals = _resolve_voltvar_curve(element_data)
        curve_name = create_xycurve_element(
            dss, f"{element_name}_VV", x_vals, y_vals, execute_dss_command)
        if not curve_name:
            return False
        cmd = (
            f"New InvControl.{ctrl_name} Mode=VOLTVAR DERList=[{der_list}] "
            f"VVC_Curve1={curve_name} RefReactivePower=VARMAX"
        )
        execute_dss_command(cmd)
        return True

    if mode == 'VOLTWATT':
        x_vals, y_vals = _resolve_voltwatt_curve(element_data)
        curve_name = create_xycurve_element(
            dss, f"{element_name}_VW", x_vals, y_vals, execute_dss_command)
        if not curve_name:
            return False
        cmd = (
            f"New InvControl.{ctrl_name} Mode=VOLTWATT DERList=[{der_list}] "
            f"voltwatt_curve={curve_name}"
        )
        execute_dss_command(cmd)
        return True

    if mode == 'WATTPF':
        x_vals, y_vals = _resolve_wattpf_curve(element_data)
        curve_name = create_xycurve_element(
            dss, f"{element_name}_WattPF", x_vals, y_vals, execute_dss_command)
        if not curve_name:
            return False
        cmd = (
            f"New InvControl.{ctrl_name} Mode=WATTPF DERList=[{der_list}] "
            f"WattPF_Curve={curve_name}"
        )
        execute_dss_command(cmd)
        return True

    if mode == 'WATTVAR':
        x_vals, y_vals = _resolve_wattvar_curve(element_data)
        curve_name = create_xycurve_element(
            dss, f"{element_name}_WattVar", x_vals, y_vals, execute_dss_command)
        if not curve_name:
            return False
        cmd = (
            f"New InvControl.{ctrl_name} Mode=WATTVAR DERList=[{der_list}] "
            f"WattVar_Curve={curve_name}"
        )
        execute_dss_command(cmd)
        return True

    if mode == 'DYNAMICREACCURR':
        cmd = (
            f"New InvControl.{ctrl_name} Mode=DYNAMICREACCURR DERList=[{der_list}]"
        )
        execute_dss_command(cmd)
        return True

    return False


def create_invcontrol_for_storage(dss, element_name, element_data, execute_dss_command=None):
    """Backward-compatible wrapper: InvControl for Storage."""
    return create_invcontrol_for_der(
        dss, 'Storage', element_name, element_data, execute_dss_command)


def create_storage_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, StoragesDict, StoragesDictId, created_elements, execute_dss_command=None):
    """Create a storage element in OpenDSS with full BESS/Battery storage support.
    Maps pandapower parameters to OpenDSS and supports OpenDSS-specific properties.
    Reference: https://opendss.epri.com/Properties5.html
    """
    
    # Check for duplicates - skip if already created
    if element_name in created_elements:
        return
    
    bus_connection = element_data.get('bus')
    if bus_connection:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_connection_backend = bus_connection
        if bus_connection_backend in BusbarsDictConnectionToName:
            bus_name = BusbarsDictConnectionToName[bus_connection_backend]
        else:
            bus_name = _sanitize_opendss_name(bus_connection_backend)
        bus_voltage = BusbarsDictVoltage.get(bus_name)
        
        # Validate voltage is available
        if bus_voltage is None:
            error_msg = (
                f"Missing voltage information for bus '{bus_name}' connected to storage '{element_name}'.\n\n"
                f"Please set the 'vn_kv' (nominal voltage) attribute for the bus element.\n\n"
                f"Available buses with voltage: {list(BusbarsDictVoltage.keys())}"
            )
            raise ValueError(error_msg)
        
        if bus_voltage is not None:
            # Get storage parameters
            p_mw_raw = element_data.get('p_mw')
            q_mvar_raw = element_data.get('q_mvar')           
            # Convert to float
            p_mw = float(p_mw_raw) if p_mw_raw is not None else 0.0
            q_mvar = float(q_mvar_raw) if q_mvar_raw is not None else 0.0

            # P–Q capability curve, setpoint mode, and kVA priority (Electrisim convention)
            try:
                p_mw, q_mvar, _, _ = resolve_storage_pq(element_data)
            except Exception:
                pass
            
            # Convert to kW and kVar (OpenDSS uses kW/kvar)
            p_kw = p_mw * 1000
            q_kvar = q_mvar * 1000

            # Determine OpenDSS State from dispatch power:
            #   pandapower p_mw < 0 → discharging/generating → State=DISCHARGING
            #   pandapower p_mw > 0 → charging/consuming    → State=CHARGING
            #   pandapower p_mw == 0 → idling               → State=IDLING
            # OpenDSS kW is generator convention: positive = discharging, negative = charging.
            if p_kw < 0:
                storage_state = 'DISCHARGING'
                kw_rated = abs(p_kw)
                kw_dispatch = abs(p_kw)
            elif p_kw > 0:
                storage_state = 'CHARGING'
                kw_rated = abs(p_kw)
                kw_dispatch = -abs(p_kw)
            else:
                storage_state = 'IDLING'
                kw_rated = float(element_data.get('sn_mva', 1) or 1) * 1000
                kw_dispatch = 0.0

            # Rated apparent power (kVA) from sn_mva
            sn_mva = float(element_data.get('sn_mva', 0) or 0)
            kva_rated = sn_mva * 1000 if sn_mva > 0 else kw_rated
                        
            try:
                # Negate q_kvar: Pandapower uses load convention (positive=absorbing),
                # OpenDSS Storage uses generator convention (positive=supplying)
                kvar_opendss = -q_kvar
                # Number of phases and connection type
                phases_raw = element_data.get('phases', 3)
                try:
                    phases = int(float(phases_raw)) if phases_raw is not None else 3
                    phases = max(1, min(3, phases))
                except (TypeError, ValueError):
                    phases = 3
                conn_raw = str(element_data.get('conn', 'wye')).lower()
                conn = 'delta' if conn_raw == 'delta' else 'wye'

                inv_mode = str(element_data.get('inv_control_mode', 'NONE')).upper()
                pf_suffix = ''
                if inv_mode == 'FIXED_PF':
                    pf_suffix = _opendss_storage_fixed_pf_suffix(element_data, storage_state)

                # Energy must be on the New command *before* State. OpenDSS default %stored=100;
                # applying kWhrated while full immediately forces CHARGING → IDLING
                # (terminal P = %IdlingkW of kWRated). A later %stored write does not restore charging.
                energy_suffix = ''
                max_e_mwh = element_data.get('max_e_mwh')
                kWhrated = 0.0
                if max_e_mwh is not None:
                    try:
                        kWhrated = float(max_e_mwh) * 1000  # MWh to kWh
                        if kWhrated > 0:
                            energy_suffix += f" kWhrated={kWhrated}"
                    except (TypeError, ValueError):
                        kWhrated = 0.0
                soc_percent = element_data.get('soc_percent')
                soc_for_new = None
                if soc_percent is not None:
                    try:
                        soc_for_new = float(soc_percent)
                        if 0 <= soc_for_new <= 100:
                            energy_suffix += f" %stored={soc_for_new}"
                        else:
                            soc_for_new = None
                    except (TypeError, ValueError):
                        soc_for_new = None

                qcap_suffix = ''
                if _storage_qcap_truthy(element_data.get('reactive_capability_curve')):
                    lim = interp_storage_pq_limits(element_data, p_mw)
                    if lim is not None:
                        q_mi, q_ma = lim
                        # OpenDSS generator convention: kvarMax = max supplying, kvarMaxAbs = max absorbing
                        kvar_max_gen = max(0.0, -float(q_mi)) * 1000.0
                        kvar_max_abs = max(0.0, float(q_ma)) * 1000.0
                        if kvar_max_gen > 0:
                            qcap_suffix += f" kvarMax={kvar_max_gen}"
                        if kvar_max_abs > 0:
                            qcap_suffix += f" kvarMaxAbs={kvar_max_abs}"

                simple_cmd = (
                    f"New Storage.{element_name} phases={phases} Bus1={bus_name} kV={bus_voltage} "
                    f"conn={conn} "
                    f"kWRated={kw_rated} kVA={kva_rated}{energy_suffix} "
                    f"kW={kw_dispatch} kvar={kvar_opendss}{qcap_suffix} "
                    f"State={storage_state}{pf_suffix}"
                )
                
                # Append harmonic analysis spectrum if provided
                spectrum = element_data.get('spectrum', 'default')
                if spectrum and spectrum.lower() not in ('none', ''):
                    sl_sp = str(spectrum).strip().lower()
                    if sl_sp == 'linear':
                        lin_name = _sanitize_opendss_name(f"{element_name}_stor_linear")
                        if _create_spectrum_from_csv(dss, lin_name, SPECTRUM_LINEAR_UI_CSV, execute_dss_command):
                            simple_cmd += f" spectrum={lin_name}"
                        else:
                            simple_cmd += " spectrum=default"
                    else:
                        simple_cmd += f" spectrum={spectrum}"
                
                execute_dss_command(simple_cmd)
                
                # Apply follow-up OpenDSS properties via Text.Command
                follow_up_cmds = []
                
                # soc_percent -> %stored (state of charge)
                soc_percent = element_data.get('soc_percent')
                if soc_percent is not None:
                    try:
                        pct_stored = float(soc_percent)
                        if 0 <= pct_stored <= 100:
                            follow_up_cmds.append(f'Storage.{element_name}.%stored={pct_stored}')
                    except (TypeError, ValueError):
                        pass
                
                # min_e_mwh / max_e_mwh -> %reserve (percent of rated kWh held in reserve)
                # Skip when pct_reserve >= 100% as that would block all discharge
                min_e_mwh = element_data.get('min_e_mwh')
                if min_e_mwh is not None and max_e_mwh is not None:
                    try:
                        min_e = float(min_e_mwh)
                        max_e = float(max_e_mwh)
                        if max_e > 0 and min_e >= 0 and min_e < max_e:
                            pct_reserve = (min_e / max_e) * 100
                            follow_up_cmds.append(f'Storage.{element_name}.%reserve={pct_reserve}')
                    except (TypeError, ValueError):
                        pass
                
                # OpenDSS-specific: %Charge, %Discharge (percent of rated kW)
                pct_charge = element_data.get('pct_charge')
                if pct_charge is not None:
                    try:
                        follow_up_cmds.append(f'Storage.{element_name}.%Charge={float(pct_charge)}')
                    except (TypeError, ValueError):
                        pass
                
                pct_discharge = element_data.get('pct_discharge')
                if pct_discharge is not None:
                    try:
                        follow_up_cmds.append(f'Storage.{element_name}.%Discharge={float(pct_discharge)}')
                    except (TypeError, ValueError):
                        pass
                
                # OpenDSS-specific: %EffCharge, %EffDischarge
                pct_eff_charge = element_data.get('pct_eff_charge')
                if pct_eff_charge is not None:
                    try:
                        follow_up_cmds.append(f'Storage.{element_name}.%EffCharge={float(pct_eff_charge)}')
                    except (TypeError, ValueError):
                        pass
                
                pct_eff_discharge = element_data.get('pct_eff_discharge')
                if pct_eff_discharge is not None:
                    try:
                        follow_up_cmds.append(f'Storage.{element_name}.%EffDischarge={float(pct_eff_discharge)}')
                    except (TypeError, ValueError):
                        pass

                # OpenDSS-specific: %IdlingkW, %IdlingkVar (self-depletion + auxiliary loads)
                pct_idling_kw = element_data.get('pct_idling_kw')
                if pct_idling_kw is not None:
                    try:
                        follow_up_cmds.append(f'Storage.{element_name}.%IdlingkW={float(pct_idling_kw)}')
                    except (TypeError, ValueError):
                        pass

                pct_idling_kvar = element_data.get('pct_idling_kvar')
                if pct_idling_kvar is not None:
                    try:
                        follow_up_cmds.append(f'Storage.{element_name}.%Idlingkvar={float(pct_idling_kvar)}')
                    except (TypeError, ValueError):
                        pass

                # OpenDSS-specific: DischargeTrigger, ChargeTrigger
                discharge_trigger = element_data.get('discharge_trigger')
                if discharge_trigger is not None:
                    try:
                        val = float(discharge_trigger)
                        if val != 0.0:
                            follow_up_cmds.append(f'Storage.{element_name}.DischargeTrigger={val}')
                    except (TypeError, ValueError):
                        pass

                charge_trigger = element_data.get('charge_trigger')
                if charge_trigger is not None:
                    try:
                        val = float(charge_trigger)
                        if val != 0.0:
                            follow_up_cmds.append(f'Storage.{element_name}.ChargeTrigger={val}')
                    except (TypeError, ValueError):
                        pass

                # OpenDSS-specific: TimeChargeTrig (fractional hours; -1 disables)
                time_charge_trig = element_data.get('time_charge_trig')
                if time_charge_trig is not None:
                    try:
                        follow_up_cmds.append(f'Storage.{element_name}.TimeChargeTrig={float(time_charge_trig)}')
                    except (TypeError, ValueError):
                        pass

                # Snapshot dispatch: re-assert State/kW after energy and DispMode writes.
                # OpenDSS default %stored=100; CHARGING a full battery becomes IDLING at
                # %IdlingkW (typically 1% of kWRated). A later %stored write does not restore charging.
                if p_kw == 0:
                    state = element_data.get('state')
                    if state and str(state).upper() in ('IDLING', 'CHARGING', 'DISCHARGING'):
                        follow_up_cmds.append(f'Storage.{element_name}.State={str(state).upper()}')
                
                # OpenDSS-specific: DispMode (DEFAULT, FOLLOW, EXTERNAL, LOADLEVEL, PRICE)
                disp_mode = element_data.get('disp_mode')
                if disp_mode and str(disp_mode).upper() in ('DEFAULT', 'FOLLOW', 'EXTERNAL', 'LOADLEVEL', 'PRICE'):
                    follow_up_cmds.append(f'Storage.{element_name}.DispMode={str(disp_mode).upper()}')
                watt_priority_raw = element_data.get('watt_priority')
                if watt_priority_raw is not None and str(watt_priority_raw).lower() in ('true', '1', 'yes'):
                    follow_up_cmds.append(f'Storage.{element_name}.WattPriority=yes')
                if p_kw != 0:
                    follow_up_cmds.append(f'Storage.{element_name}.State={storage_state}')
                    follow_up_cmds.append(f'Storage.{element_name}.kW={kw_dispatch}')
                
                for cmd in follow_up_cmds:
                    if execute_dss_command:
                        execute_dss_command(cmd)
                    else:
                        dss.Text.Command(cmd)

                _opendss_storage_dispatch[element_name] = {
                    'p_mw': p_mw,
                    'state': storage_state,
                    'kw_rated': kw_rated,
                    'pct_idling_kw': float(element_data.get('pct_idling_kw') or 1),
                    'user_name': str(element_data.get('userFriendlyName') or element_data.get('name') or element_name),
                }
                
                # InvControl for voltage-dependent inverter modes (Q-V droop, Watt-PF, ...)
                try:
                    create_invcontrol_for_der(
                        dss, 'Storage', element_name, element_data, execute_dss_command)
                except Exception as inv_err:
                    print(f"[OpenDSS] InvControl for {element_name} failed: {inv_err}")

                if p_kw != 0:
                    _st_cmd = f'Storage.{element_name}.State={storage_state}'
                    _kw_cmd = f'Storage.{element_name}.kW={kw_dispatch}'
                    if execute_dss_command:
                        execute_dss_command(_st_cmd)
                        execute_dss_command(_kw_cmd)
                    else:
                        dss.Text.Command(_st_cmd)
                        dss.Text.Command(_kw_cmd)
                
                # Handle in_service status AFTER creating the element
                in_service = element_data.get('in_service', True)
                
                # Convert to boolean for comparison
                is_in_service = True
                if isinstance(in_service, bool):
                    is_in_service = in_service
                elif isinstance(in_service, str):
                    is_in_service = in_service.lower() not in ['false', 'no', '0']
                elif in_service in [0, None]:
                    is_in_service = False
                
                if not is_in_service:
                    cmd = f'Storage.{element_name}.enabled=no'
                    print(f"[OpenDSS] {cmd}")
                    dss.Text.Command(cmd)
       
                
                StoragesDict[element_name] = element_name
                StoragesDictId[element_name] = element_id
                created_elements.add(element_name)
                
            except Exception as e:
                pass
        else:
            pass
    else:
        pass
def create_pvsystem_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, PVSystemsDict, PVSystemsDictId, created_elements, execute_dss_command=None):
    """Create a PVSystem element in OpenDSS with comprehensive parameter support"""
    
    # Check for duplicates - skip if already created
    if element_name in created_elements:
        return
    
    bus_connection = element_data.get('bus')
    if bus_connection:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_connection_backend = bus_connection
        if bus_connection_backend in BusbarsDictConnectionToName:
            bus_name = BusbarsDictConnectionToName[bus_connection_backend]
        else:
            bus_name = _sanitize_opendss_name(bus_connection_backend)
        bus_voltage = BusbarsDictVoltage.get(bus_name)

        # Validate voltage is available
        if bus_voltage is None:
            error_msg = (
                f"Missing voltage information for bus '{bus_name}' connected to PV system '{element_name}'.\n\n"
                f"Please set the 'vn_kv' (nominal voltage) attribute for the bus element.\n\n"
                f"Available buses with voltage: {list(BusbarsDictVoltage.keys())}"
            )
            raise ValueError(error_msg)

        if bus_voltage is not None:
            # Extract ONLY VALIDATED PVSystem parameters from frontend data
            # These parameters are confirmed to work in OpenDSS
            
            # Basic required parameters
            irradiance_raw = element_data.get('irradiance')
            pmpp_raw = element_data.get('pmpp')
            temperature_raw = element_data.get('temperature')
            phases_raw = element_data.get('phases')
            kv_raw = element_data.get('kv')
            
            # Power parameters
            pf_raw = element_data.get('pf')
            kvar_raw = element_data.get('kvar')
            kva_raw = element_data.get('kva')
            
            # Cut-in/Cut-out parameters (frontend sends as per-unit 0.1, needs to be converted to percentage 10%)
            cutin_raw = element_data.get('cutin')
            cutout_raw = element_data.get('cutout')

            # Convert basic parameters with defaults
            irradiance = float(irradiance_raw) if irradiance_raw is not None else 1.0
            pmpp = float(pmpp_raw) if pmpp_raw is not None else 100.0  # kW
            temperature = float(temperature_raw) if temperature_raw is not None else 25.0
            phases = int(phases_raw) if phases_raw is not None else 3
            kv = float(kv_raw) if kv_raw is not None else float(bus_voltage)
            pf = float(pf_raw) if pf_raw is not None else 1.0
            kvar = float(kvar_raw) if kvar_raw is not None else 0.0
            kva = float(kva_raw) if kva_raw is not None else pmpp * 1.2  # Default 20% above Pmpp

            try:
                # Create PVSystem command string with ONLY VALIDATED OpenDSS parameters
                # Based on OpenDSS documentation and user validation
                pv_cmd = f"New PVSystem.{element_name} phases={phases} Bus1={bus_name} kV={kv} irradiance={irradiance} Pmpp={pmpp} Temperature={temperature}"
                
     
                
                # Add power parameters (VALIDATED - these work in OpenDSS)
                if pf_raw is not None:
                    pv_cmd += f" pf={pf}"
                if kvar_raw is not None:
                    pv_cmd += f" kvar={kvar}"
                if kva_raw is not None:
                    pv_cmd += f" kVA={kva}"
                
                # Add cut-in/cut-out (VALIDATED - frontend sends as per-unit, OpenDSS expects percentage)
                if cutin_raw is not None:
                    cutin_percent = float(cutin_raw) * 100  # Convert 0.1 to 10%
                    pv_cmd += f" %Cutin={cutin_percent}"
                if cutout_raw is not None:
                    cutout_percent = float(cutout_raw) * 100  # Convert 0.1 to 10%
                    pv_cmd += f" %Cutout={cutout_percent}"

                # Safe advanced OpenDSS PVSystem parameters
                kvarmax_raw = element_data.get('kvarmax')
                kvarmaxabs_raw = element_data.get('kvarmaxabs')
                pct_pmpp_raw = element_data.get('pmpp_percent')
                if kvarmax_raw is not None:
                    try:
                        pv_cmd += f" kvarMax={float(kvarmax_raw)}"
                    except (TypeError, ValueError):
                        pass
                if kvarmaxabs_raw is not None:
                    try:
                        pv_cmd += f" kvarMaxAbs={float(kvarmaxabs_raw)}"
                    except (TypeError, ValueError):
                        pass
                if pct_pmpp_raw is not None:
                    try:
                        pct_pmpp = float(pct_pmpp_raw)
                        # Frontend may send 0-1 or 0-100
                        if pct_pmpp <= 1.0:
                            pct_pmpp *= 100.0
                        pv_cmd += f" %Pmpp={pct_pmpp}"
                    except (TypeError, ValueError):
                        pass

                # Harmonic analysis property
                spec_name = _sanitize_opendss_name(f"harm_pv_{element_name}")
                spectrum_resolved = _resolve_named_spectrum_for_element(
                    dss, element_data, 'default', spec_name, execute_dss_command)
                if spectrum_resolved:
                    pv_cmd += f" spectrum={spectrum_resolved}"

                execute_dss_command(pv_cmd)

                # InvControl for PVSystem (Volt-VAR / Volt-Watt / Watt-PF / ...)
                try:
                    create_invcontrol_for_der(
                        dss, 'PVSystem', element_name, element_data, execute_dss_command)
                except Exception as inv_err:
                    print(f"[OpenDSS] InvControl for PVSystem {element_name} failed: {inv_err}")

                # Handle in_service status AFTER creating the element
                in_service = element_data.get('in_service', True)
                
                # Convert to boolean for comparison
                is_in_service = True
                if isinstance(in_service, bool):
                    is_in_service = in_service
                elif isinstance(in_service, str):
                    is_in_service = in_service.lower() not in ['false', 'no', '0']
                elif in_service in [0, None]:
                    is_in_service = False
                
                if not is_in_service:
                    cmd = f'PVSystem.{element_name}.enabled=no'
                    print(f"[OpenDSS] {cmd}")
                    dss.Text.Command(cmd)

                PVSystemsDict[element_name] = element_name
                PVSystemsDictId[element_name] = element_id
                created_elements.add(element_name)

            except Exception as e:
                pass
        else:
            pass
    else:
        pass
def create_external_grid_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, created_elements, execute_dss_command=None):
    """Create an external grid element in OpenDSS"""
    
    # Check for duplicates - skip if already created
    if element_name in created_elements:
        return
    
    bus_connection = element_data.get('bus')
    if bus_connection:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_connection_backend = bus_connection
        if bus_connection_backend in BusbarsDictConnectionToName:
            bus_name = BusbarsDictConnectionToName[bus_connection_backend]
        else:
            bus_name = _sanitize_opendss_name(bus_connection_backend)
        bus_voltage = BusbarsDictVoltage.get(bus_name)        
     
        # Validate voltage is available
        if bus_voltage is None:
            error_msg = (
                f"Missing voltage information for bus '{bus_name}' connected to external grid '{element_name}'.\n\n"
                f"Please set the 'vn_kv' (nominal voltage) attribute for the bus element.\n\n"
                f"Available buses with voltage: {list(BusbarsDictVoltage.keys())}"
            )
            raise ValueError(error_msg)
     
        # Get external grid parameters
        vm_pu_raw = element_data.get('vm_pu')
        
        # Convert to float
        vm_pu = float(vm_pu_raw)
        
        # Validate and auto-correct vm_pu (OpenDSS Vsource 'pu' parameter)
        if vm_pu == 0:
            vm_pu = 1.0
            print(f"WARNING: External Grid '{element_name}' had vm_pu=0, auto-corrected to 1.0 p.u.")
        elif vm_pu > 1.5 and bus_voltage is not None and float(bus_voltage) > 0:
            corrected_vm_pu = vm_pu / float(bus_voltage)
            print(f"WARNING: External Grid '{element_name}' has vm_pu={vm_pu}, "
                  f"which is unreasonably high. Auto-correcting to {corrected_vm_pu:.4f} p.u.")
            vm_pu = corrected_vm_pu
        
        mode, imp_suffix, mvasc3 = _ext_grid_vsource_impedance(element_data, bus_voltage)
        
        try:
            # Build spectrum parameter if provided (named spectrum or custom CSV -> New Spectrum.*)
            spec_name = _sanitize_opendss_name(f"harm_vsrc_{element_name}")
            spectrum_resolved = _resolve_named_spectrum_for_element(
                dss, element_data, 'defaultvsource', spec_name, execute_dss_command)
            spectrum_suffix = ''
            if spectrum_resolved:
                spectrum_suffix = f" spectrum={spectrum_resolved}"

            imp_part = imp_suffix if mode == 'thevenin' else f" mvasc3={mvasc3}"
            
            if 'circuit_source_configured' not in created_elements:
                # First external grid: configure the default Circuit source directly.
                # When 'New Circuit' is called, OpenDSS creates a default Vsource named
                # "source" at bus "sourcebus". Instead of disabling it and creating a
                # separate Vsource, we edit it with the first external grid's parameters.
                # This is cleaner and follows the standard OpenDSS pattern where the
                # Circuit source IS the main grid connection.
                edit_cmd = (f"Edit Vsource.source Bus1={bus_name} basekv={bus_voltage} "
                            f"pu={vm_pu} Phases=3 angle=0{imp_part}{spectrum_suffix}")
                execute_dss_command(edit_cmd)
                created_elements.add('circuit_source_configured')
                # Track which element name maps to the circuit source for result retrieval
                created_elements.add(f'circuit_source_element:{element_name}')
            else:
                # Additional external grids: create a new Vsource element
                external_grid_cmd = (f"New Vsource.{element_name} Bus1={bus_name} basekv={bus_voltage} "
                                     f"pu={vm_pu} Phases=3 angle=0{imp_part}{spectrum_suffix}")
                execute_dss_command(external_grid_cmd)
            
            # Handle in_service status AFTER creating the element
            in_service = element_data.get('in_service', True)
            
            # Convert to boolean for comparison
            is_in_service = True
            if isinstance(in_service, bool):
                is_in_service = in_service
            elif isinstance(in_service, str):
                is_in_service = in_service.lower() not in ['false', 'no', '0']
            elif in_service in [0, None]:
                is_in_service = False
            
            if not is_in_service:
                # For the first external grid (mapped to source), we edit it
                if 'circuit_source_element:' + element_name in created_elements:
                    cmd = 'Vsource.source.enabled=no'
                    print(f"[OpenDSS] {cmd}")
                    dss.Text.Command(cmd)
                else:
                    # For additional external grids
                    cmd = f'Vsource.{element_name}.enabled=no'
                    print(f"[OpenDSS] {cmd}")
                    dss.Text.Command(cmd)
            
            created_elements.add(element_name)
            
        except Exception as e:
            pass
    else:
        pass


def shortcircuit(in_data, frequency=50, fault_type='3ph', export_open_dss_results=False):
    """OpenDSS fault study / short circuit analysis.

    Builds the circuit from in_data (same as powerflow), sets Solution.Mode to FaultStudy,
    solves, and returns bus short circuit results in the same format as Pandapower
    (busbars with ikss_ka, ip_ka, ith_ka, rk_ohm, xk_ohm) for frontend compatibility.

    Reference: https://opendss.epri.com/OpenDSSFaultStudyMode.html
    OpenDSSDirect.py: dss.Solution.Mode(4) for FaultStudy, dss.Bus.Isc(), dss.Bus.Zsc1()
    """
    opendss_commands = []

    def execute_dss_command(command):
        print(f"[OpenDSS] {command}")  # Log all commands
        dss.Text.Command(command)
        if export_open_dss_results:
            opendss_commands.append(command)

    f = int(frequency) if frequency else 50
    ext_scan = _prescan_external_grid(in_data)

    execute_dss_command('clear')
    execute_dss_command(_new_circuit_command(ext_scan))
    execute_dss_command(f'set DefaultBaseFrequency={f}')

    try:
        BusbarsDictVoltage, BusbarsDictConnectionToName = create_busbars(in_data, dss, False, opendss_commands)
        (LinesDict, LinesDictId, LoadsDict, LoadsDictId, TransformersDict, TransformersDictId,
         Transformers3WDict, Transformers3WDictId,
         ShuntsDict, ShuntsDictId, CapacitorsDict, CapacitorsDictId, GeneratorsDict, GeneratorsDictId,
         StoragesDict, StoragesDictId, PVSystemsDict, PVSystemsDictId, ExternalGridsDict, ExternalGridsDictId,
         _circuit_source) = create_other_elements(in_data, dss, BusbarsDictVoltage, BusbarsDictConnectionToName, False, opendss_commands, execute_dss_command)
    except ValueError as ve:
        return json.dumps({"error": str(ve)})
    except Exception as e:
        return json.dumps({"error": f"Error creating network elements: {str(e)}"})

    # Set voltage bases (required for fault study and per-unit results)
    try:
        vb_list = _collect_voltage_bases_from_in_data(in_data, BusbarsDictVoltage)
        if vb_list:
            execute_dss_command('set voltagebases=[' + ','.join(str(v) for v in vb_list) + ']')
        print("[OpenDSS] calcv")
        dss.Text.Command('calcv')
    except Exception:
        pass

    # Run Snapshot solve first so circuit has a solution and open-circuit voltages exist
    # Fault Study uses these for Isc = Ysc * Voc; some engines need this before FaultStudy
    try:
        dss.Solution.Mode(0)  # 0 = Snapshot
        dss.Solution.Solve()
        print(f"[DEBUG] Snapshot solve completed. Converged: {dss.Solution.Converged()}")
        # Check if buses have voltage after snapshot solve
        for bus_name in (dss.Circuit.AllBusNames() or [])[:3]:
            dss.Circuit.SetActiveBus(bus_name)
            vmag = dss.Bus.VMagAngle()
            print(f"[DEBUG] After Snapshot - Bus {bus_name}: VMagAngle={vmag[:4] if vmag and len(vmag) >= 4 else vmag}")
    except Exception as e:
        print(f"[DEBUG] Snapshot solve exception: {e}")
        try:
            execute_dss_command('set Mode=Snapshot')
            print("[OpenDSS] solve")
            dss.Text.Command('solve')
        except Exception:
            pass

    # Set solution mode to Fault Study (mode 4) and solve
    # https://opendss.epri.com/OpenDSSFaultStudyMode.html
    # Use run_command so the engine runs the full fault-study sequence (Solve populates Isc/Zsc per bus)
    try:
        execute_dss_command('set Mode=FaultStudy')
        print("[OpenDSS] solve")
        dss.Text.Command('solve')
        print(f"[DEBUG] FaultStudy solve completed. Solution.Mode: {dss.Solution.Mode()}")
        if hasattr(dss.Solution, 'Converged'):
            print(f"[DEBUG] Solution.Converged: {dss.Solution.Converged()}")
    except Exception as e1:
        try:
            dss.Solution.Mode(4)
            dss.Solution.Solve()
            print(f"[DEBUG] FaultStudy solve (API) completed. Solution.Mode: {dss.Solution.Mode()}")
        except Exception as e2:
            return json.dumps({"error": f"Fault study solve failed: {str(e1)}; {str(e2)}"})

    # Build bus index mapping (same as powerflow)
    BusbarsDict = {}
    nBusbar = 0
    for bus_id in BusbarsDictConnectionToName.keys():
        BusbarsDict[bus_id] = nBusbar
        nBusbar += 1

    # Map bus name (with _) to graph cell id from in_data for frontend getCell(cell.id)
    bus_name_to_graph_id = {}
    for key in in_data:
        try:
            elem = in_data[key]
            if elem and isinstance(elem, dict) and 'Bus' in str(elem.get('typ', '')) and elem.get('name') and elem.get('id') is not None:
                bus_name_to_graph_id[str(elem.get('name')).replace('#', '_')] = str(elem.get('id'))
        except (TypeError, AttributeError):
            continue

    busbarList = []
    processed_buses = set()
    kappa = 1.8  # Peak current factor for ip_ka = kappa * sqrt(2) * ikss_ka

    try:
        all_bus_names = dss.Circuit.AllBusNames()
        print(f"[DEBUG] Total buses in circuit: {len(all_bus_names) if all_bus_names else 0}")
        print(f"[DEBUG] All bus names: {all_bus_names}")
        for bus_name_from_list in all_bus_names:
            dss.Circuit.SetActiveBus(bus_name_from_list)
            actual_bus_name = dss.Bus.Name()
            if actual_bus_name.lower() in ['sourcebus', 'source'] or bus_name_from_list.lower() in ['sourcebus', 'source']:
                continue

            matched_bus_id = None
            bus_number = None
            for key, value in BusbarsDict.items():
                if key.lower() == actual_bus_name.lower():
                    matched_bus_id = key
                    bus_number = value
                    break
            if not matched_bus_id or bus_number in processed_buses:
                continue
            processed_buses.add(bus_number)

            try:
                # Ensure Zsc/Isc are populated for this bus (required in some OpenDSS versions)
                if hasattr(dss.Bus, 'ZscRefresh'):
                    try:
                        dss.Bus.ZscRefresh()
                    except Exception:
                        pass
                # Isc() returns complex array: [I1_re, I1_im, I2_re, I2_im, ...] in Amps (flat), or list of 3 complex when AdvancedTypes
                isc_arr = dss.Bus.Isc()
                print(f"[DEBUG] Bus {actual_bus_name}: Isc() = {isc_arr}, type: {type(isc_arr)}, len: {len(isc_arr) if isc_arr else 0}")
                ikss_ka = 0.0
                if isc_arr is not None:
                    if len(isc_arr) >= 6:
                        # Flat [re, im, re, im, re, im]
                        try:
                            I_a = complex(float(isc_arr[0]), float(isc_arr[1]))
                            I_b = complex(float(isc_arr[2]), float(isc_arr[3]))
                            I_c = complex(float(isc_arr[4]), float(isc_arr[5]))
                            ikss_mag = (abs(I_a) + abs(I_b) + abs(I_c)) / 3.0
                            ikss_ka = ikss_mag / 1000.0
                        except (TypeError, ValueError, IndexError):
                            pass
                    elif len(isc_arr) >= 3:
                        # List of 3 complex numbers (AdvancedTypes)
                        try:
                            mags = []
                            for x in isc_arr[:3]:
                                if hasattr(x, 'real') and hasattr(x, 'imag'):
                                    mags.append(abs(x))
                                elif hasattr(x, '__len__') and len(x) >= 2:
                                    mags.append(abs(complex(float(x[0]), float(x[1]))))
                                else:
                                    mags.append(0.0)
                            ikss_mag = sum(mags) / 3.0
                            ikss_ka = ikss_mag / 1000.0
                        except (TypeError, ValueError, IndexError):
                            pass

                # Peak short-circuit current: ip = kappa * sqrt(2) * ikss
                ip_ka = kappa * math.sqrt(2) * ikss_ka if ikss_ka else 0.0
                # Thermal short-circuit current (short duration): ith ? ikss
                ith_ka = ikss_ka

                # Zsc1() returns complex positive-sequence short-circuit impedance at bus (ohms)
                # May be [real, imag] list or a single complex number
                zsc1 = dss.Bus.Zsc1()
                print(f"[DEBUG] Bus {actual_bus_name}: Zsc1() = {zsc1}, type: {type(zsc1)}")
                rk_ohm = 0.0
                xk_ohm = 0.0
                if zsc1 is not None:
                    if hasattr(zsc1, '__len__') and len(zsc1) >= 2:
                        try:
                            rk_ohm = float(zsc1[0])
                            xk_ohm = float(zsc1[1])
                        except (TypeError, ValueError, IndexError):
                            pass
                    elif hasattr(zsc1, 'real') and hasattr(zsc1, 'imag'):
                        rk_ohm = float(zsc1.real)
                        xk_ohm = float(zsc1.imag)

                # When Isc() returns zeros but Zsc1 is valid, derive Isc from OpenDSS Voc and Zsc1 (Isc = Ysc*Voc = Voc/Zsc1)
                if ikss_ka <= 0.0 and (rk_ohm != 0.0 or xk_ohm != 0.0) and hasattr(dss.Bus, 'Voc'):
                    try:
                        voc_arr = dss.Bus.Voc()
                        print(f"[DEBUG] Bus {actual_bus_name}: Voc() = {voc_arr}, type: {type(voc_arr)}, len: {len(voc_arr) if voc_arr else 0}")
                        v_ln = 0.0
                        if voc_arr is not None and len(voc_arr) >= 2:
                            if len(voc_arr) >= 6:
                                # Flat [re, im, re, im, re, im] - use first phase magnitude (line-to-neutral)
                                v1 = complex(float(voc_arr[0]), float(voc_arr[1]))
                                v2 = complex(float(voc_arr[2]), float(voc_arr[3]))
                                v3 = complex(float(voc_arr[4]), float(voc_arr[5]))
                                v_ln = (abs(v1) + abs(v2) + abs(v3)) / 3.0
                            else:
                                v_ln = abs(complex(float(voc_arr[0]), float(voc_arr[1])))
                        if v_ln > 0:
                            z_mag = math.sqrt(rk_ohm * rk_ohm + xk_ohm * xk_ohm)
                            if z_mag > 0:
                                ikss_ka = (v_ln / z_mag) / 1000.0  # Amps -> kA
                                ip_ka = kappa * math.sqrt(2) * ikss_ka
                                ith_ka = ikss_ka
                    except (TypeError, ValueError, IndexError, ZeroDivisionError):
                        pass

                # Use graph cell id from in_data so frontend getCell(cell.id) finds the bus
                frontend_bus_id = bus_name_to_graph_id.get(matched_bus_id) or matched_bus_id.replace('_', '#')
                frontend_bus_name = BusbarsDictConnectionToName.get(matched_bus_id, matched_bus_id).replace('_', '#')
                print(f"[DEBUG] Bus {actual_bus_name}: Final ikss_ka={ikss_ka}, ip_ka={ip_ka}, ith_ka={ith_ka}, rk_ohm={rk_ohm}, xk_ohm={xk_ohm}")
                busbar = BusbarScOut(
                    name=frontend_bus_name,
                    id=frontend_bus_id,
                    ikss_ka=round(ikss_ka, 6),
                    ip_ka=round(ip_ka, 6),
                    ith_ka=round(ith_ka, 6),
                    rk_ohm=round(rk_ohm, 6),
                    xk_ohm=round(xk_ohm, 6)
                )
                busbarList.append(busbar)
            except Exception as e:
                frontend_bus_id = bus_name_to_graph_id.get(matched_bus_id) or matched_bus_id.replace('_', '#')
                frontend_bus_name = BusbarsDictConnectionToName.get(matched_bus_id, matched_bus_id).replace('_', '#')
                busbarList.append(BusbarScOut(
                    name=frontend_bus_name,
                    id=frontend_bus_id,
                    ikss_ka=0.0,
                    ip_ka=0.0,
                    ith_ka=0.0,
                    rk_ohm=0.0,
                    xk_ohm=0.0
                ))

    except Exception as e:
        for bus_name in BusbarsDictConnectionToName.keys():
            frontend_bus_name = bus_name.replace('_', '#')
            frontend_bus_id = bus_name_to_graph_id.get(bus_name) or bus_name.replace('_', '#')
            busbarList.append(BusbarScOut(
                name=frontend_bus_name,
                id=frontend_bus_id,
                ikss_ka=0.0,
                ip_ka=0.0,
                ith_ka=0.0,
                rk_ohm=0.0,
                xk_ohm=0.0
            ))

    result = {"busbars": [vars(b) for b in busbarList]}
    return json.dumps(result, separators=(',', ':'))


def _opendss_has_power_injections(LoadsDict, GeneratorsDict, StoragesDict, PVSystemsDict):
    """Return True when the model has loads, generators, storage, or PV that should draw/inject power."""
    return bool(LoadsDict or GeneratorsDict or StoragesDict or PVSystemsDict)


def _opendss_total_power_is_zero(total_power, threshold_kw=0.01):
    """Return True when circuit total power is effectively zero (OpenDSS first-solve quirk)."""
    try:
        p_kw = float(total_power[0])
        q_kvar = float(total_power[1])
    except (TypeError, IndexError, ValueError):
        return True
    return abs(p_kw) < threshold_kw and abs(q_kvar) < threshold_kw


def _monte_carlo_percentile(values, percentile):
    """Return a linear-interpolated percentile without adding a NumPy dependency."""
    values = sorted(float(value) for value in values if value is not None and math.isfinite(float(value)))
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * percentile / 100.0
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return values[lower]
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def _capture_monte_carlo_sample(BusbarsDictConnectionToName, LinesDict, LinesDictId, in_data):
    """Capture one native OpenDSS Monte Carlo solve result."""
    buses = {}
    lines = {}
    try:
        for bus_name in dss.Circuit.AllBusNames():
            dss.Circuit.SetActiveBus(bus_name)
            actual_name = dss.Bus.Name()
            bus_id = next((key for key in BusbarsDictConnectionToName
                           if key.lower() == actual_name.lower()), None)
            if not bus_id:
                continue
            pu_values = dss.Bus.puVmagAngle()
            magnitudes = [float(pu_values[index]) for index in range(0, len(pu_values), 2)
                          if math.isfinite(float(pu_values[index]))]
            if magnitudes:
                buses[bus_id] = {
                    'id': bus_id,
                    'name': BusbarsDictConnectionToName[bus_id],
                    'vm_pu': sum(magnitudes) / len(magnitudes),
                }
    except Exception as error:
        print(f"[OpenDSS] Monte Carlo bus capture failed: {error}")

    line_ratings = {}
    for element in in_data.values():
        if isinstance(element, dict) and 'Line' in str(element.get('typ', '')):
            line_ratings[_sanitize_opendss_name(element.get('name', ''))] = element.get('max_i_ka')
    for key, line_name in LinesDict.items():
        try:
            dss.Circuit.SetActiveElement(f"Line.{line_name}")
            currents = dss.CktElement.CurrentsMagAng()
            n_conductors = dss.CktElement.NumConductors()
            n_phases = dss.CktElement.NumPhases()
            current_ka = _opendss_terminal_i_ka(currents, 0, n_conductors, n_phases) if currents else 0.0
            rating_ka = float(line_ratings.get(key) or 0)
            lines[key] = {
                'id': LinesDictId.get(key, key),
                'name': key,
                'loading_percent': (current_ka / rating_ka * 100.0) if rating_ka > 0 else 0.0,
                'current_ka': current_ka,
            }
        except Exception:
            continue
    return buses, lines


def _build_monte_carlo_result(mode, number, random_distribution, bus_samples, line_samples, converged_count):
    """Aggregate captured Monte Carlo samples into the frontend response schema."""
    bus_stats = []
    for bus_id, entry in bus_samples.items():
        values = entry['values']
        bus_stats.append({
            'id': bus_id, 'name': entry['name'], 'vmin': min(values), 'vmean': sum(values) / len(values),
            'vmax': max(values), 'p5': _monte_carlo_percentile(values, 5),
            'p50': _monte_carlo_percentile(values, 50), 'p95': _monte_carlo_percentile(values, 95),
        })
    line_stats = []
    for line_id, entry in line_samples.items():
        values = entry['values']
        line_stats.append({
            'id': entry['id'], 'name': entry['name'], 'loading_mean': sum(values) / len(values),
            'loading_max': max(values), 'p95': _monte_carlo_percentile(values, 95),
        })
    histogram_buses = [
        {'id': bus_id, 'name': entry['name'], 'values': entry['values']}
        for bus_id, entry in list(bus_samples.items())[:20]
    ]
    return {
        'mode': mode, 'number': number, 'random': random_distribution,
        'bus_stats': bus_stats, 'line_stats': line_stats,
        'samples': {'bus_voltage_pu': histogram_buses},
        'summary': {'n_samples': number, 'converged_count': converged_count,
                    'failed_count': number - converged_count},
    }


def powerflow(in_data, frequency, mode, algorithm, loadmodel, max_iterations, tolerance, controlmode,
              export_commands=False, monte_carlo_number=100, monte_carlo_random='Uniform',
              monte_carlo_hour=None):
    """Main powerflow function for OpenDSS
    
    Parameters based on OpenDSS documentation: https://opendss.epri.com/PowerFlow.html
    
    Args:
        in_data: Network element data
        frequency: Base frequency in Hz (e.g. 50, 60, 75)
        mode: Solution mode (Snapshot, Daily, Dutycycle, Yearly, etc.)
        algorithm: Solution algorithm (Normal, Newton, NCIM)
        loadmodel: Load model (Powerflow=iterative with power injections, Admittance=direct solution)
        export_commands: Boolean flag to export OpenDSS commands to file
        max_iterations: Maximum number of iterations
        tolerance: Convergence tolerance
        controlmode: Control mode (Static, Event, Time)
    """
    
    # OpenDSSDirect.py is already imported as dss at the module level

    # Initialize list to collect OpenDSS commands if export is requested
    opendss_commands = []
    _reset_opendss_warnings()
    
    def execute_dss_command(command):
        """Execute DSS command and optionally collect it for export"""
        print(f"[OpenDSS] {command}")  # Log all commands
        dss.Text.Command(command)
        try:
            err = dss.Error.Description()
            if err:
                print(f"[OpenDSS ERROR] after '{command}': {err}")
        except Exception:
            pass
        if export_commands:
            opendss_commands.append(command)
    
    # Native OpenDSS Monte Carlo modes.  The individual Solve calls below are
    # intentional: OpenDSS exposes only the last solution after `Solve Number=N`,
    # so collecting sample-level statistics requires one native M1/M2/M3 solve per sample.
    mode = str(mode or 'Snapshot')
    monte_carlo_mode = mode.upper() in ('M1', 'M2', 'M3')
    try:
        monte_carlo_number = max(1, int(monte_carlo_number or 100))
    except (TypeError, ValueError):
        monte_carlo_number = 100
    monte_carlo_random = str(monte_carlo_random or 'Uniform').capitalize()
    if monte_carlo_random not in ('Uniform', 'Gaussian'):
        monte_carlo_random = 'Uniform'
    monte_carlo_bus_samples = {}
    monte_carlo_line_samples = {}
    monte_carlo_converged_count = 0

    # Set OpenDSS circuit parameters
    f = frequency
    
    # Auto-enable Time control when Storage uses InvControl (Volt-VAR, Watt-PF, etc.)
    effective_controlmode = controlmode
    if _in_data_needs_time_control(in_data):
        if str(controlmode).lower() == 'static':
            effective_controlmode = 'Time'
            print("[OpenDSS] InvControl detected - upgrading ControlMode Static -> Time")
    
    # Pre-scan in_data for the first External Grid to embed its Vsource parameters
    # directly into "New Circuit". This avoids relying on "Edit Vsource.source" which
    # can silently fail in some opendssdirect versions, leaving zero voltage everywhere.
    ext_scan = _prescan_external_grid(in_data)
    
    element_dicts = None
    if monte_carlo_mode:
        plan_queue = [{'label': str(mode), 'algorithm': algorithm,
                       'max_iterations': max_iterations, 'gen_vminpu': None}]
    else:
        plan_queue = _opendss_snapshot_solve_plans(algorithm, max_iterations)
    build_attempt = 0
    zero_power_rebuild_done = False
    usable_plan = None
    usable_plan_replayed = False

    while build_attempt < len(plan_queue):
        plan = plan_queue[build_attempt]
        if build_attempt > 0:
            print(f"[OpenDSS] Rebuilding circuit and solving again: {plan['label']}")
            if monte_carlo_mode:
                monte_carlo_bus_samples.clear()
                monte_carlo_line_samples.clear()
                monte_carlo_converged_count = 0

        execute_dss_command('clear')
        execute_dss_command(_new_circuit_command(ext_scan))
        execute_dss_command(f'set DefaultBaseFrequency={f}')
        execute_dss_command(f'set Mode={mode}')
        execute_dss_command(f"set Algorithm={plan['algorithm']}")
        execute_dss_command(f'set LoadModel={loadmodel}')
        execute_dss_command(f'set ControlMode={effective_controlmode}')
        execute_dss_command(f"set MaxIterations={plan['max_iterations']}")
        execute_dss_command(f'set Tolerance={tolerance}')
        if monte_carlo_mode:
            execute_dss_command(f'set Number={monte_carlo_number}')
            execute_dss_command(f'set Random={monte_carlo_random}')
            if mode.upper() == 'M3' and monte_carlo_hour not in (None, ''):
                execute_dss_command(f'set Hour={monte_carlo_hour}')

        # Create busbars and other elements using helper functions
        # Wrap in try-except to catch validation errors and return them to frontend
        try:
            BusbarsDictVoltage, BusbarsDictConnectionToName = create_busbars(
                in_data, dss, export_commands, opendss_commands)

            element_dicts = create_other_elements(
                in_data, dss, BusbarsDictVoltage, BusbarsDictConnectionToName,
                export_commands, opendss_commands, execute_dss_command)
        except ValueError as ve:
            error_response = {"error": str(ve)}
            return json.dumps(error_response)
        except Exception as e:
            error_response = {"error": f"Error creating network elements: {str(e)}"}
            return json.dumps(error_response)

        try:
            print("[OpenDSS] solve")
            gens_for_solve = element_dicts[12] if element_dicts and len(element_dicts) > 12 else {}
            if monte_carlo_mode:
                # Retain the requested Number setting in the exported model, then
                # use one solve at a time to preserve each random realization.
                execute_dss_command('set Number=1')
                for sample_index in range(monte_carlo_number):
                    dss.Text.Command('solve')
                    if not dss.Solution.Converged():
                        print(f"[OpenDSS] Monte Carlo sample {sample_index + 1} did not converge")
                        continue
                    monte_carlo_converged_count += 1
                    sample_buses, sample_lines = _capture_monte_carlo_sample(
                        BusbarsDictConnectionToName, element_dicts[0], element_dicts[1], in_data)
                    for bus_id, sample in sample_buses.items():
                        entry = monte_carlo_bus_samples.setdefault(
                            bus_id, {'name': sample['name'], 'values': []})
                        entry['values'].append(sample['vm_pu'])
                    for line_key, sample in sample_lines.items():
                        entry = monte_carlo_line_samples.setdefault(
                            line_key, {'id': sample['id'], 'name': sample['name'], 'values': []})
                        entry['values'].append(sample['loading_percent'])
            else:
                _opendss_solve_snapshot_plan(dss, execute_dss_command, plan, gens_for_solve)
        except Exception as e:
            print(f"[OpenDSS] Solve EXCEPTION: {e}")

        try:
            converged = dss.Solution.Converged()
            iterations = dss.Solution.Iterations()
            print(f"[OpenDSS] Converged: {converged}, Iterations: {iterations}")
            all_buses = dss.Circuit.AllBusNames()
            print(f"[OpenDSS] AllBusNames: {all_buses}")
            total_power = dss.Circuit.TotalPower()
            print(f"[OpenDSS] TotalPower (kW, kvar): {total_power}")
            for bname in all_buses[:6]:
                dss.Circuit.SetActiveBus(bname)
                v = dss.Bus.Voltages()
                print(f"[OpenDSS] Bus '{bname}' voltages (V): {v[:6] if len(v) >= 6 else v}")

            (LinesDict, LinesDictId, LoadsDict, LoadsDictId, TransformersDict, TransformersDictId,
             Transformers3WDict, Transformers3WDictId,
             ShuntsDict, ShuntsDictId, CapacitorsDict, CapacitorsDictId, GeneratorsDict, GeneratorsDictId,
             StoragesDict, StoragesDictId, PVSystemsDict, PVSystemsDictId, ExternalGridsDict, ExternalGridsDictId,
             circuit_source_element_name) = element_dicts

            if (not zero_power_rebuild_done
                    and _opendss_has_power_injections(LoadsDict, GeneratorsDict, StoragesDict, PVSystemsDict)
                    and _opendss_total_power_is_zero(total_power)):
                print("[OpenDSS] Zero-power solve with active injections; rebuilding circuit")
                zero_power_rebuild_done = True
                plan_queue.insert(build_attempt + 1, dict(plan))
                build_attempt += 1
                continue

            if monte_carlo_mode:
                break

            solution_usable = _opendss_circuit_has_usable_solution(dss)
            if converged and solution_usable:
                break
            if solution_usable and usable_plan is None:
                usable_plan = dict(plan)

            build_attempt += 1
            if (build_attempt >= len(plan_queue) and usable_plan is not None
                    and not solution_usable and not usable_plan_replayed):
                # Every later plan diverged; go back to the one that produced real voltages.
                usable_plan_replayed = True
                plan_queue.append(usable_plan)
        except Exception as e:
            print(f"[OpenDSS] Post-solve diagnostics EXCEPTION: {e}")
            if element_dicts is not None:
                (LinesDict, LinesDictId, LoadsDict, LoadsDictId, TransformersDict, TransformersDictId,
                 Transformers3WDict, Transformers3WDictId,
                 ShuntsDict, ShuntsDictId, CapacitorsDict, CapacitorsDictId, GeneratorsDict, GeneratorsDictId,
                 StoragesDict, StoragesDictId, PVSystemsDict, PVSystemsDictId, ExternalGridsDict, ExternalGridsDictId,
                 circuit_source_element_name) = element_dicts
            break

    if element_dicts is None:
        return json.dumps({"error": "Error creating network elements: circuit build failed"})
    (LinesDict, LinesDictId, LoadsDict, LoadsDictId, TransformersDict, TransformersDictId,
     Transformers3WDict, Transformers3WDictId,
     ShuntsDict, ShuntsDictId, CapacitorsDict, CapacitorsDictId, GeneratorsDict, GeneratorsDictId,
     StoragesDict, StoragesDictId, PVSystemsDict, PVSystemsDictId, ExternalGridsDict, ExternalGridsDictId,
     circuit_source_element_name) = element_dicts

    if not monte_carlo_mode:
        if not _opendss_circuit_converged(dss):
            iters = 0
            try:
                iters = dss.Solution.Iterations()
            except Exception:
                pass
            return json.dumps({
                "error": (
                    "OpenDSS load flow did not converge "
                    f"(iterations={iters}). Check generator P/Q, transformer ratings, "
                    "and slack short-circuit power. Try Algorithm=Newton in the OpenDSS "
                    "load-flow dialog, or compare with pandapower on the same case."
                )
            })
        try:
            if not dss.Solution.Converged():
                print(
                    f"[OpenDSS] Solution.Converged()=False after {dss.Solution.Iterations()} "
                    "iteration(s), but voltages and total power are finite; reporting result"
                )
        except Exception:
            pass
        try:
            _opendss_apply_discrete_shunt_control(dss, execute_dss_command, BusbarsDictVoltage)
        except Exception as e:
            print(f"[OpenDSS] Discrete shunt control failed: {e}")
        try:
            _opendss_apply_line_flow_shunt_control(dss, execute_dss_command, LinesDict, LinesDictId)
        except Exception as e:
            print(f"[OpenDSS] Line-flow shunt control failed: {e}")
        if not _opendss_circuit_converged(dss):
            iters = 0
            try:
                iters = dss.Solution.Iterations()
            except Exception:
                pass
            return json.dumps({
                "error": (
                    "OpenDSS load flow lost convergence after shunt control "
                    f"(iterations={iters})."
                )
            })

    # Process results using the new output classes
    
    # Initialize result lists
    busbarList = []
    linesList = []
    loadsList = []
    transformersList = []
    transformers3wList = []
    shuntsList = []
    capacitorsList = []
    generatorsList = []
    storagesList = []
    pvsystemsList = []
    externalGridsList = []

    # Lookup inv_control_mode per Storage / PVSystem id from input data
    storage_inv_mode_by_id = {}
    pv_inv_mode_by_id = {}
    for _k, _elem in in_data.items():
        try:
            typ = str(_elem.get('typ', ''))
            eid = _elem.get('id')
            if not eid:
                continue
            mode = str(_elem.get('inv_control_mode', 'NONE')).upper()
            if typ.startswith('Storage'):
                storage_inv_mode_by_id[str(eid)] = mode
            elif typ.startswith('PVSystem'):
                pv_inv_mode_by_id[str(eid)] = mode
        except Exception:
            pass
    
    # Aggregate P and Q per bus from CktElement powers
    bus_pq_kw = {}  # bus_name_lower -> (p_kw, q_kvar)
    try:
        for is_pc in [False, True]:  # PDElements then PCElements
            idx = dss.Circuit.FirstPCElement() if is_pc else dss.Circuit.FirstPDElement()
            while idx > 0:
                try:
                    bus_names = dss.CktElement.BusNames()
                    powers = dss.CktElement.Powers()
                    if not bus_names or not powers:
                        idx = dss.Circuit.NextPCElement() if is_pc else dss.Circuit.NextPDElement()
                        continue
                    n_phases = dss.CktElement.NumPhases()
                    n_conductors = dss.CktElement.NumConductors()
                    n_terminals = dss.CktElement.NumTerminals()
                    # Powers() is [P1, Q1, P2, Q2, ...] per conductor (kW, kvar)
                    n_per_terminal = (n_conductors * 2) if n_conductors else (n_phases * 2)
                    for t in range(min(n_terminals, len(bus_names))):
                        bus_ref = bus_names[t]
                        bus_name_lower = bus_ref.split('.')[0].lower() if bus_ref else ''
                        if not bus_name_lower:
                            continue
                        p_kw = 0.0
                        q_kvar = 0.0
                        start = t * n_per_terminal
                        for i in range(0, min(n_per_terminal, len(powers) - start), 2):
                            p_kw += float(powers[start + i]) if start + i < len(powers) else 0.0
                            q_kvar += float(powers[start + i + 1]) if start + i + 1 < len(powers) else 0.0
                        if bus_name_lower not in bus_pq_kw:
                            bus_pq_kw[bus_name_lower] = [0.0, 0.0]
                        bus_pq_kw[bus_name_lower][0] += p_kw
                        bus_pq_kw[bus_name_lower][1] += q_kvar
                except Exception:
                    pass
                idx = dss.Circuit.NextPCElement() if is_pc else dss.Circuit.NextPDElement()
    except Exception:
        pass

    # Process bus results using actual OpenDSS data with proper symmetrical component calculation
    
    # Build a mapping from OpenDSS bus numbers to our bus IDs
    # OpenDSS internally uses numeric bus IDs, we need to map them back
    BusbarsDict = {}
    nBusbar = 0
    for bus_id in BusbarsDictConnectionToName.keys():
        BusbarsDict[bus_id] = nBusbar
        nBusbar += 1
    
    
    
    # Track which buses have been processed to avoid duplicates
    processed_buses = set()
    
    try:
        all_bus_names = dss.Circuit.AllBusNames()

        
        # Process all buses from OpenDSS circuit
        for bus_name_from_list in all_bus_names:
            # Set active bus using the name from the list
            dss.Circuit.SetActiveBus(bus_name_from_list)
            
            # Get the actual bus name (might be different from list name)
            actual_bus_name = dss.Bus.Name()
            
            # Debug: Print bus names to identify source buses (commented out for less verbose logging)
            # print(f"  Processing bus from list: '{bus_name_from_list}', actual name: '{actual_bus_name}'")
            
            # Skip sourcebus and source - OpenDSS's internal voltage source buses created by "New Circuit"
            # These are NOT the user's buses where External Grid VSources connect
            if (actual_bus_name.lower() in ['sourcebus', 'source'] or 
                bus_name_from_list.lower() in ['sourcebus', 'source']):
                continue
            
            # OpenDSS converts names to lowercase, so try to match against our expected buses (case-insensitive)
            matched_bus_id = None
            matched_bus_name = None
            
            # Try case-insensitive matching against our bus IDs
            for key, value in BusbarsDict.items():
                # OpenDSS lowercases names, so compare lowercase versions
                if key.lower() == actual_bus_name.lower():
                    matched_bus_id = key
                    matched_bus_name = BusbarsDictConnectionToName[key]
                    bus_number = value
                    # print(f"    ? Matched to user bus: {matched_bus_name}")  # Reduced logging
                    break
            
            if not matched_bus_id:
                continue
            
            # Skip if we've already processed this bus number
            if bus_number in processed_buses:
                continue
            
            processed_buses.add(bus_number)
            
            try:
                # Calculate positive sequence voltage using symmetrical components
                # This matches the notebook approach exactly
                voltages = dss.Bus.Voltages()  # in Volts: [Va_real, Va_imag, Vb_real, Vb_imag, Vc_real, Vc_imag]
                
                # Convert to kV and create complex numbers
                Va = complex(voltages[0]/1000, voltages[1]/1000)
                Vb = complex(voltages[2]/1000, voltages[3]/1000)
                Vc = complex(voltages[4]/1000, voltages[5]/1000)
                
                # Symmetrical component operator: a = e^(j*2?/3)
                a = complex(-0.5, math.sqrt(3)/2)
                a2 = complex(-0.5, -math.sqrt(3)/2)  # a^2 = e^(j*4*pi/3)
                
                # Positive sequence voltage: V1 = (Va + a*Vb + a^2*Vc) / 3
                V1 = (Va + a * Vb + a2 * Vc) / 3
                V1_mag_ln_kv = abs(V1)  # Magnitude in kV (line-to-neutral)
                
                # Convert to line-to-line voltage
                V1_mag_ll_kv = V1_mag_ln_kv * math.sqrt(3)
                
                # Per-unit on OpenDSS calcv base (avoids e.g. bus4 at 10.6 kV with 10.0 kV trafo nameplate)
                vm_pu = _bus_vm_pu_from_opendss(V1_mag_ll_kv, BusbarsDictVoltage, matched_bus_id)
                
                # Get angle from vmag_angle_pu
                va_degree = dss.Bus.puVmagAngle()[1] if len(dss.Bus.puVmagAngle()) > 1 else 0.0
                
                # P, Q, PF, Q/P for bus result box (from aggregated bus power)
                p_mw = None
                q_mvar = None
                pf = None
                q_p = None
                pq = bus_pq_kw.get(matched_bus_id.lower())
                if pq is not None:
                    p_kw, q_kvar = pq[0], pq[1]
                    p_mw = p_kw / 1000.0
                    q_mvar = q_kvar / 1000.0
                    s = math.sqrt(p_kw * p_kw + q_kvar * q_kvar)
                    pf = (p_kw / s) if s > 0 else None
                    q_p = (q_kvar / p_kw) if p_kw != 0 else None
                
                # Use name/id as stored (underscore format to match pandapower/frontend)
                frontend_bus_id = matched_bus_id
                frontend_bus_name = matched_bus_name
                busbar = BusbarOut(
                    name=frontend_bus_name,
                    id=frontend_bus_id,
                    vm_pu=vm_pu,
                    va_degree=va_degree,
                    p_mw=p_mw,
                    q_mvar=q_mvar,
                    pf=pf,
                    q_p=q_p,
                    vm_kv=V1_mag_ll_kv if V1_mag_ll_kv == V1_mag_ll_kv else None,
                )
                busbarList.append(busbar)
                # print(f"    ? Added to results: {frontend_bus_name} (vm_pu={vm_pu:.6f}, va_degree={va_degree:.6f})")  # Reduced logging
                
            except Exception as e:
                # Add with default values - use name/id as stored
                frontend_bus_id = matched_bus_id
                frontend_bus_name = matched_bus_name
                _fb_kv = float(BusbarsDictVoltage.get(matched_bus_id, 0) or 0)
                busbar = BusbarOut(
                    name=frontend_bus_name,
                    id=frontend_bus_id,
                    vm_pu=1.0,
                    va_degree=0.0,
                    p_mw=None,
                    q_mvar=None,
                    pf=None,
                    q_p=None,
                    vm_kv=_fb_kv if _fb_kv > 0 else None,
                )
                busbarList.append(busbar)
                
    except Exception as e:
        # Fallback to default processing if OpenDSS bus access fails
        for bus_name in BusbarsDictConnectionToName.keys():
            try:
                vm_pu = 1.0
                va_degree = 0.0
                pq = bus_pq_kw.get(bus_name.lower()) if bus_pq_kw else None
                p_mw = (pq[0] / 1000.0) if pq else None
                q_mvar = (pq[1] / 1000.0) if pq else None
                pf = None
                q_p = None
                if pq and (pq[0] != 0 or pq[1] != 0):
                    s = math.sqrt(pq[0] * pq[0] + pq[1] * pq[1])
                    pf = (pq[0] / s) if s > 0 else None
                    q_p = (pq[1] / pq[0]) if pq[0] != 0 else None
                # Use name/id as stored (underscore format to match pandapower/frontend)
                frontend_bus_name = bus_name
                frontend_bus_id = bus_name
                _fb_vn = float(BusbarsDictVoltage.get(bus_name, 0) or 0)
                busbar = BusbarOut(
                    name=frontend_bus_name,
                    id=frontend_bus_id,
                    vm_pu=vm_pu,
                    va_degree=va_degree,
                    p_mw=p_mw,
                    q_mvar=q_mvar,
                    pf=pf,
                    q_p=q_p,
                    vm_kv=_fb_vn if _fb_vn > 0 else None,
                )
                busbarList.append(busbar)
                
            except Exception as e2:
                continue
    
    # Process line results - iterate through ALL lines we created (not just OpenDSS's active ones)
    # This ensures we get results for disabled lines too (with zero values)
    
    for key, line_name in LinesDict.items():
        try:
            # Set the active element
            dss.Circuit.SetActiveElement(f"Line.{line_name}")
            
            # Check if the line is enabled
            is_enabled = dss.CktElement.Enabled()
            
            if is_enabled:
                powers = dss.CktElement.Powers()
                if len(powers) >= 2:
                    n_conductors = dss.CktElement.NumConductors()
                    n_phases = dss.CktElement.NumPhases()
                    p_from_kw, q_from_kvar = _opendss_terminal_pq_kw(powers, 0, n_conductors, n_phases)
                    p_to_kw, q_to_kvar = _opendss_terminal_pq_kw(powers, 1, n_conductors, n_phases)
                    p_from_mw = p_from_kw / 1000.0
                    q_from_mvar = q_from_kvar / 1000.0
                    p_to_mw = p_to_kw / 1000.0
                    q_to_mvar = q_to_kvar / 1000.0
                else:
                    p_from_mw = p_to_mw = q_from_mvar = q_to_mvar = 0.0

                # Get currents (in A) - use magnitude from currents_mag_ang
                currents = dss.CktElement.CurrentsMagAng()
                if len(currents) >= 2:
                    n_conductors = dss.CktElement.NumConductors()
                    n_phases = dss.CktElement.NumPhases()
                    i_from_ka = _opendss_terminal_i_ka(currents, 0, n_conductors, n_phases)
                    i_to_ka = _opendss_terminal_i_ka(currents, 1, n_conductors, n_phases)
                else:
                    i_from_ka = i_to_ka = 0.0
            else:
                # Line is disabled - report zero values
                p_from_mw = p_to_mw = q_from_mvar = q_to_mvar = 0.0
                i_from_ka = i_to_ka = 0.0

            # Calculate loading percentage using max_i_ka from input data
            loading_percent = 0.0
            # Find the line in input data to get max_i_ka
            max_i_ka = None
            for data_key, data_value in in_data.items():
                if _sanitize_opendss_name(data_value.get('name', '')) == key and 'Line' in data_value.get('typ', ''):
                    max_i_ka_raw = data_value.get('max_i_ka')
                    if max_i_ka_raw is not None:
                        max_i_ka = float(max_i_ka_raw)
                    break
            
            if max_i_ka and max_i_ka > 0 and is_enabled:
                loading_percent = (i_from_ka / max_i_ka) * 100
            else:
                # Fallback if max_i_ka not available or line is disabled
                loading_percent = 0.0

            # Convert IDs back to hash format for frontend
            frontend_name = key
            frontend_id = LinesDictId[key]
            
            line = LineOut(
                name=frontend_name, 
                id=frontend_id, 
                p_from_mw=p_from_mw, 
                q_from_mvar=q_from_mvar, 
                p_to_mw=p_to_mw, 
                q_to_mvar=q_to_mvar, 
                i_from_ka=i_from_ka, 
                i_to_ka=i_to_ka, 
                loading_percent=loading_percent
            )
            linesList.append(line)
            
        except Exception as e:
            # Still add the line to results with zero values
            try:
                frontend_name = key
                frontend_id = LinesDictId[key]
                line = LineOut(
                    name=frontend_name, 
                    id=frontend_id, 
                    p_from_mw=0.0, 
                    q_from_mvar=0.0, 
                    p_to_mw=0.0, 
                    q_to_mvar=0.0, 
                    i_from_ka=0.0, 
                    i_to_ka=0.0, 
                    loading_percent=0.0
                )
                linesList.append(line)
            except:
                pass
    
    
    # Process load results - iterate through ALL loads we created
    
    for key, load_name in LoadsDict.items():
        try:
            # Set the active element
            dss.Circuit.SetActiveElement(f"Load.{load_name}")
            
            # Check if the load is enabled
            is_enabled = dss.CktElement.Enabled()
            
            if is_enabled:
                powers = dss.CktElement.Powers()
                p_mw, q_mvar = _opendss_ckt_pq_mw(powers, 0)
            else:
                # Load is disabled - report zero values
                p_mw = q_mvar = 0.0

            p_set_mw = None
            vm_pu = None
            if in_data:
                for elem in in_data.values():
                    if not isinstance(elem, dict):
                        continue
                    if not elem.get('typ', '').startswith('Load'):
                        continue
                    if _sanitize_opendss_name(elem.get('name', '')) != key:
                        continue
                    if elem.get('p_kw') not in (None, ''):
                        p_set_mw = float(elem.get('p_kw') or 0) / 1000.0
                    else:
                        p_set_mw = float(elem.get('p_mw', 0) or 0)
                    break
            try:
                bus_names = dss.CktElement.BusNames()
                load_bus = bus_names[0].split('.')[0] if bus_names else None
                if load_bus:
                    for bname in dss.Circuit.AllBusNames():
                        if bname.lower() == load_bus.lower():
                            dss.Circuit.SetActiveBus(bname)
                            bus_pu = dss.Bus.puVmagAngle()
                            if bus_pu and len(bus_pu) >= 1 and not math.isnan(bus_pu[0]):
                                vm_pu = float(bus_pu[0])
                            break
            except Exception:
                pass
            if (
                p_set_mw is not None and p_set_mw > 0.001
                and is_enabled and abs(p_mw) < 0.9 * abs(p_set_mw)
            ):
                vm_txt = f'{vm_pu:.3f} pu' if vm_pu is not None else 'low'
                _opendss_warn(
                    f"Load '{key}' draws {abs(p_mw) * 1000:.1f} kW vs {abs(p_set_mw) * 1000:.1f} kW set - "
                    f"bus voltage {vm_txt}. Check line length, transformer kVA, or use constant-P load (%SeriesRL=0)."
                )

            # Convert IDs back to hash format
            frontend_name = key
            frontend_id = LoadsDictId[key]

            load = LoadOut(
                name=frontend_name, id=frontend_id, p_mw=p_mw, q_mvar=q_mvar,
                p_set_mw=p_set_mw, vm_pu=vm_pu,
            )
            loadsList.append(load)
                            
        except Exception as e:
            # Still add the load to results with zero values
            try:
                frontend_name = key
                frontend_id = LoadsDictId[key]
                load = LoadOut(name=frontend_name, id=frontend_id, p_mw=0.0, q_mvar=0.0)
                loadsList.append(load)
            except:
                pass
    
    
    # Process static generators (created as Generator elements) - iterate through ALL generators we created
    
    for key, gen_name in GeneratorsDict.items():
        try:
            # Set this Generator as the active circuit element (static generators are created as Generator, not PVSystem)
            dss.Circuit.SetActiveElement(f"Generator.{gen_name}")
            
            # Check if the generator is enabled
            is_enabled = dss.CktElement.Enabled()
            
            if is_enabled:
                # Get generator powers (solution values; Model 1 = constant P,Q so these match setpoint)
                powers = dss.CktElement.Powers()
                if len(powers) >= 6:
                    # Sum all three phases (powers come in pairs: P1,Q1,P2,Q2,P3,Q3)
                    p_raw = powers[0] + powers[2] + powers[4]
                    q_raw = powers[1] + powers[3] + powers[5]
                else:
                    p_mw_raw, q_mvar_raw = _opendss_ckt_pq_mw(powers, 0)
                    p_raw = p_mw_raw * 1000.0
                    q_raw = q_mvar_raw * 1000.0
                # Generator reports power flowing OUT as NEGATIVE (generation into grid)
                # Negate to show positive generation in results
                p_mw = -(p_raw / 1000.0) if not math.isnan(p_raw) else 0.0
                q_mvar = -(q_raw / 1000.0) if not math.isnan(q_raw) else 0.0

                # Get voltage from bus (use CktElement so it works for Generator)
                vm_pu = 1.0
                va_degree = 0.0
                try:
                    bus_names = dss.CktElement.BusNames()
                    gen_bus_name = bus_names[0].split('.')[0] if bus_names else None
                    bus_index = None
                    if gen_bus_name:
                        for i in range(dss.Circuit.NumBuses()):
                            dss.Circuit.SetActiveBus(i)
                            if dss.Bus.Name().lower() == gen_bus_name.lower():
                                bus_index = i
                                break
                    if bus_index is not None:
                        dss.Circuit.SetActiveBus(bus_index)
                        bus_angles = dss.Bus.puVmagAngle()
                        if len(bus_angles) >= 2:
                            vm_pu = bus_angles[0] if not math.isnan(bus_angles[0]) else 1.0
                            va_degree = bus_angles[1] if not math.isnan(bus_angles[1]) else 0.0
                except Exception as e:
                    pass
            else:
                # Generator is disabled - report zero values
                p_mw = q_mvar = 0.0
                vm_pu = 1.0
                va_degree = 0.0

            # Convert IDs back to hash format
            frontend_name = key
            frontend_id = GeneratorsDictId[key]
            
            generator = GeneratorOut(
                name=frontend_name, 
                id=frontend_id, 
                p_mw=p_mw, 
                q_mvar=q_mvar, 
                va_degree=va_degree, 
                vm_pu=vm_pu
            )
            generatorsList.append(generator)
            # print(f"    ? Added Generator (static generator): {frontend_name}, P={p_mw:.3f} MW, Q={q_mvar:.3f} MVAr, V={vm_pu:.3f} pu")  # Reduced logging
                        
        except Exception as e:
            # Still add the generator to results with zero values
            try:
                frontend_name = key
                frontend_id = GeneratorsDictId[key]
                generator = GeneratorOut(
                    name=frontend_name, 
                    id=frontend_id, 
                    p_mw=0.0, 
                    q_mvar=0.0, 
                    va_degree=0.0, 
                    vm_pu=1.0
                )
                generatorsList.append(generator)
            except:
                pass
    
    
    # Process transformer results - iterate through ALL transformers we created
   
    
    for key, trafo_name in TransformersDict.items():
        try:
            # Set the active element
            dss.Circuit.SetActiveElement(f"Transformer.{trafo_name}")
            
            # Check if the transformer is enabled
            is_enabled = dss.CktElement.Enabled()
            
            if is_enabled:
                # Get powers (in kW and kvar) for transformer
                powers = dss.CktElement.Powers()
                # Initialize power values
                p_hv_mw = q_hv_mvar = p_lv_mw = q_lv_mvar = pl_mw = ql_mvar = 0.0
                
                if len(powers) >= 2:
                    n_conductors = dss.CktElement.NumConductors()
                    n_phases = dss.CktElement.NumPhases()
                    p_hv_kw, q_hv_kvar = _opendss_terminal_pq_kw(powers, 0, n_conductors, n_phases)
                    p_lv_kw, q_lv_kvar = _opendss_terminal_pq_kw(powers, 1, n_conductors, n_phases)
                    
                    # Convert to MW/MVAr
                    p_hv_mw = p_hv_kw / 1000.0 if not math.isnan(p_hv_kw) else 0.0
                    q_hv_mvar = q_hv_kvar / 1000.0 if not math.isnan(q_hv_kvar) else 0.0
                    p_lv_mw = p_lv_kw / 1000.0 if not math.isnan(p_lv_kw) else 0.0
                    q_lv_mvar = q_lv_kvar / 1000.0 if not math.isnan(q_lv_kvar) else 0.0
                    
                    # Try to get losses directly from OpenDSS
                    try:
                        losses_direct = dss.CktElement.Losses()
                        if len(losses_direct) >= 2:
                            # OpenDSS returns losses in Watts (W), not kW
                            pl_direct_w = losses_direct[0]
                            ql_direct_var = losses_direct[1]
                       
                            # Convert from Watts to MW (divide by 1,000,000)
                            pl_mw = pl_direct_w / 1e6
                            ql_mvar = ql_direct_var / 1e6
                         
                        else:
                            raise ValueError("Losses array too short")
                    except Exception as e:
                        # Fallback: Calculate losses using power balance
                        # With OpenDSS convention: positive = into terminal, negative = out of terminal
                        # Losses = P_terminal1 + P_terminal2 (algebraic sum)
                        pl_mw = p_hv_mw + p_lv_mw
                        ql_mvar = q_hv_mvar + q_lv_mvar
                    
                
                # Get complex currents [I1_real, I1_imag, I2_real, I2_imag, I3_real, I3_imag, ...] in Amperes
                currents = dss.CktElement.Currents()
                
                if len(currents) >= 2:
                    n_conductors = dss.CktElement.NumConductors()
                    n_phases = dss.CktElement.NumPhases()
                    i_hv_ka = _opendss_terminal_i_ka(currents, 0, n_conductors, n_phases)
                    i_lv_ka = _opendss_terminal_i_ka(currents, 1, n_conductors, n_phases)
                else:
                    i_hv_ka = i_lv_ka = 0.0

                # Calculate loading percentage based on rated current
                # Get transformer rating - prefer original input data over OpenDSS reported value
                try:
                    # First, try to get the original rating from input data (most reliable)
                    sn_mva = None
                    if in_data:
                        element_data = None
                        # Search through all elements in in_data
                        # in_data structure: keys are arbitrary, elements have 'typ' and 'name' fields
                        for elem_key, elem_data in in_data.items():
                            if isinstance(elem_data, dict):
                                elem_type = elem_data.get('typ', '')  # Note: 'typ' not 'element_type'
                                elem_name = elem_data.get('name', '')
                                elem_id = elem_data.get('id', '')
                                
                                # Match transformer by type and name/id (typ is usually "Transformer0", etc.)
                                if (elem_type.startswith("Transformer") or elem_type.startswith("Two Winding Transformer")) and not elem_type.startswith("Three Winding Transformer"):
                                    # Match by name (most reliable) - sanitize for comparison
                                    if _sanitize_opendss_name(elem_name) == trafo_name or _sanitize_opendss_name(elem_name) == key:
                                        element_data = elem_data
                                        break
                                    # Also try matching by ID
                                    elif elem_id == TransformersDictId.get(key, ''):
                                        element_data = elem_data
                                        break
                        
                        if element_data:
                            sn_mva_raw = element_data.get('sn_mva')
                            if sn_mva_raw is not None:
                                sn_mva = float(sn_mva_raw)
                            else:
                                sn_kva_raw = element_data.get('sn_kva')
                                if sn_kva_raw is not None:
                                    sn_mva = float(sn_kva_raw) / 1000.0
                        else:
                            # Debug: show what transformers ARE in in_data
                            transformer_keys_found = []
                            for elem_key, elem_data in in_data.items():
                                if isinstance(elem_data, dict) and (elem_data.get('typ', '').startswith("Transformer") or elem_data.get('typ', '').startswith("Two Winding Transformer")) and not elem_data.get('typ', '').startswith("Three Winding Transformer"):
                                    transformer_keys_found.append(f"{elem_key}: name={elem_data.get('name', 'N/A')}, id={elem_data.get('id', 'N/A')}")
                            if transformer_keys_found:
                                pass
                    # Fallback to OpenDSS reported value if original not available
                    if sn_mva is None:
                        sn_kva_reported = dss.Transformers.kVA()
                        sn_mva = sn_kva_reported / 1000.0
                    
                    # Get HV voltage from first winding
                    dss.Transformers.Wdg(1)
                    vn_hv_kv = dss.Transformers.kV()
                    
                    
                    # Get number of phases from transformer properties
                    try:
                        num_phases = dss.Transformers.Phases()
                    except:
                        # Fallback: assume 3-phase if not available
                        num_phases = 3
                    
                    
                    # Calculate loading using two methods and use the most reasonable one
                    
                    # METHOD 1: Current-based loading
                    # I_rated = S / (sqrt(3) * V_LL) for 3-phase
                    # For single-phase: I_rated = S / V
                    if num_phases == 3:
                        i_rated_hv_ka = sn_mva / (math.sqrt(3) * vn_hv_kv)
                    else:
                        i_rated_hv_ka = sn_mva / vn_hv_kv
                    
                    loading_by_current = (i_hv_ka / i_rated_hv_ka * 100.0) if i_rated_hv_ka > 0 else 0.0
                    
                    # METHOD 2: Power-based loading (MVA method)
                    # Calculate actual apparent power from HV side (use absolute values for magnitude)
                    # P and Q can be negative (power flow direction), but for loading we need magnitude
                    p_hv_abs = abs(p_hv_mw)
                    q_hv_abs = abs(q_hv_mvar)
                    s_actual_mva = math.sqrt(p_hv_abs**2 + q_hv_abs**2)
                    loading_by_power = (s_actual_mva / sn_mva * 100.0) if sn_mva > 0 else 0.0
                    
                    
                    # Use power-based loading (more reliable for transformers)
                    loading_percent = loading_by_power
                except Exception as e:
                    loading_percent = 0.0
            else:
                # Transformer is disabled - report zero values
                p_hv_mw = q_hv_mvar = p_lv_mw = q_lv_mvar = pl_mw = ql_mvar = 0.0
                i_hv_ka = i_lv_ka = 0.0
                loading_percent = 0.0

            # Convert IDs back to hash format for frontend
            frontend_name = key
            frontend_id = TransformersDictId[key]
            
            transformer = TransformerOut(
                name=frontend_name, 
                id=frontend_id, 
                i_hv_ka=i_hv_ka, 
                i_lv_ka=i_lv_ka, 
                loading_percent=loading_percent,
                p_hv_mw=p_hv_mw,
                q_hv_mvar=q_hv_mvar,
                p_lv_mw=p_lv_mw,
                q_lv_mvar=q_lv_mvar,
                pl_mw=pl_mw,
                ql_mvar=ql_mvar
            )
            transformersList.append(transformer)
                        
        except Exception as e:
            # Still add the transformer to results with zero values
            try:
                frontend_name = key
                frontend_id = TransformersDictId[key]
                transformer = TransformerOut(
                    name=frontend_name, 
                    id=frontend_id, 
                    i_hv_ka=0.0, 
                    i_lv_ka=0.0, 
                    loading_percent=0.0,
                    p_hv_mw=0.0,
                    q_hv_mvar=0.0,
                    p_lv_mw=0.0,
                    q_lv_mvar=0.0,
                    pl_mw=0.0,
                    ql_mvar=0.0
                )
                transformersList.append(transformer)
            except:
                pass

    # Process 3-winding transformer results
    for key, trafo_name in Transformers3WDict.items():
        try:
            dss.Circuit.SetActiveElement(f"Transformer.{trafo_name}")
            is_enabled = dss.CktElement.Enabled()
            p_hv_mw = q_hv_mvar = p_mv_mw = q_mv_mvar = p_lv_mw = q_lv_mvar = 0.0
            i_hv_ka = i_mv_ka = i_lv_ka = 0.0
            loading_percent = 0.0
            if is_enabled:
                powers = dss.CktElement.Powers()
                currents = dss.CktElement.Currents()
                n_conductors = dss.CktElement.NumConductors()
                n_phases = dss.CktElement.NumPhases()
                n_terminals = dss.CktElement.NumTerminals()
                if len(powers) >= 6 and n_terminals >= 3:
                    p_hv_kw, q_hv_kvar = _opendss_terminal_pq_kw(powers, 0, n_conductors, n_phases)
                    p_mv_kw, q_mv_kvar = _opendss_terminal_pq_kw(powers, 1, n_conductors, n_phases)
                    p_lv_kw, q_lv_kvar = _opendss_terminal_pq_kw(powers, 2, n_conductors, n_phases)
                    p_hv_mw = p_hv_kw / 1000.0
                    q_hv_mvar = q_hv_kvar / 1000.0
                    p_mv_mw = p_mv_kw / 1000.0
                    q_mv_mvar = q_mv_kvar / 1000.0
                    p_lv_mw = p_lv_kw / 1000.0
                    q_lv_mvar = q_lv_kvar / 1000.0
                if len(currents) >= 6 and n_terminals >= 3:
                    i_hv_ka = _opendss_terminal_i_ka(currents, 0, n_conductors, n_phases)
                    i_mv_ka = _opendss_terminal_i_ka(currents, 1, n_conductors, n_phases)
                    i_lv_ka = _opendss_terminal_i_ka(currents, 2, n_conductors, n_phases)
                sn_hv = 100.0  # default
                for elem_key, elem_data in in_data.items():
                    if isinstance(elem_data, dict) and elem_data.get('typ', '').startswith('Three Winding'):
                        if _sanitize_opendss_name(elem_data.get('name', '')) == trafo_name:
                            sn_hv = float(elem_data.get('sn_hv_mva', 100))
                            break
                s_actual = math.sqrt(abs(p_hv_mw)**2 + abs(q_hv_mvar)**2)
                loading_percent = (s_actual / sn_hv * 100.0) if sn_hv > 0 else 0.0
            frontend_id = Transformers3WDictId.get(key, key)
            t3w = Transformer3WOut(name=key, id=frontend_id, i_hv_ka=i_hv_ka, i_mv_ka=i_mv_ka, i_lv_ka=i_lv_ka,
                                   loading_percent=loading_percent, p_hv_mw=p_hv_mw, q_hv_mvar=q_hv_mvar,
                                   p_mv_mw=p_mv_mw, q_mv_mvar=q_mv_mvar, p_lv_mw=p_lv_mw, q_lv_mvar=q_lv_mvar)
            transformers3wList.append(t3w)
        except Exception:
            try:
                transformers3wList.append(Transformer3WOut(name=key, id=Transformers3WDictId.get(key, key),
                                                         i_hv_ka=0.0, i_mv_ka=0.0, i_lv_ka=0.0, loading_percent=0.0))
            except:
                pass

    # Process capacitor results
    if dss.Capacitors.Count() > 0:
        dss.Capacitors.First()
        for _ in range(dss.Capacitors.Count()):
            try:
                cap_name = dss.Capacitors.Name()
                for key, value in CapacitorsDict.items():
                    # OpenDSS lowercases names, so compare case-insensitively
                    if value.lower() == cap_name.lower() or key.lower() == cap_name.lower():
                        try:
                            powers = dss.CktElement.Powers()
                            if len(powers) >= 6:
                                p_raw = powers[0] + powers[2] + powers[4]
                                q_raw = powers[1] + powers[3] + powers[5]
                                p_mw = p_raw / 1000.0 if not math.isnan(p_raw) else 0.0
                                q_mvar = q_raw / 1000.0 if not math.isnan(q_raw) else 0.0
                            else:
                                p_mw = q_mvar = 0.0

                            # Get voltage value from the capacitor's bus
                            vm_pu = 1.0
                            try:
                                # Set the active bus to the capacitor's bus to get voltage value
                                # Note: We need to find the bus index for this capacitor
                                # For now, using default value until we can map capacitor to bus
                                bus_angles = dss.Bus.puVmagAngle()
                                if len(bus_angles) >= 1:
                                    vm_pu = bus_angles[0] if not math.isnan(bus_angles[0]) else 1.0
                            except Exception as e:
                                pass
                            # Convert IDs back to hash format for frontend
                            frontend_name = key
                            frontend_id = CapacitorsDictId[key]
                            
                            capacitor = CapacitorOut(
                                name=frontend_name, 
                                id=frontend_id, 
                                p_mw=p_mw, 
                                q_mvar=q_mvar, 
                                vm_pu=vm_pu
                            )
                            capacitorsList.append(capacitor)
                            break
                        except Exception as e:
                            continue
            except Exception as e:
                pass
            dss.Capacitors.Next()
    
    # Process shunt results (reactors in OpenDSS)
    # Use alternative method if dss.reactors is not available
    
    try:
        # Process each expected shunt directly by setting it as active element
        if ShuntsDict:
            for key, value in ShuntsDict.items():
                # value is OpenDSS element name (ShuntReactor_xxx for Reactor element)
                dss_elem_name = value
                try:
                    # Shunt reactors are modeled as Reactor element; try Reactor first, then legacy Generator
                    try:
                        dss.Circuit.SetActiveElement(f"Reactor.{dss_elem_name}")
                    except Exception:
                        try:
                            dss.Circuit.SetActiveElement(f"Reactor.{dss_elem_name.lower()}")
                        except Exception:
                            try:
                                dss.Circuit.SetActiveElement(f"Generator.{dss_elem_name}")
                            except Exception:
                                try:
                                    dss.Circuit.SetActiveElement(f"Generator.{dss_elem_name.lower()}")
                                except Exception:
                                    try:
                                        dss.Circuit.SetActiveElement(f"Load.{dss_elem_name}")
                                    except Exception:
                                        pass
                    
                    # Get element info
                    element_name = dss.CktElement.Name()
                    
                    # Get powers
                    powers = dss.CktElement.Powers()
                    
                    # Reactors can be single-phase or three-phase
                    if len(powers) >= 6:
                        # Three-phase reactor
                        p_raw = powers[0] + powers[2] + powers[4]
                        q_raw = powers[1] + powers[3] + powers[5]
                    elif len(powers) >= 2:
                        # Single-phase reactor
                        p_raw = powers[0]
                        q_raw = powers[1]
                    else:
                        p_raw = 0.0
                        q_raw = 0.0
                    
                    # Convert to MW/MVar and handle NaN
                    p_mw = (p_raw / 1000.0) if (not math.isnan(p_raw) and not math.isinf(p_raw)) else 0.0
                    q_mvar = (q_raw / 1000.0) if (not math.isnan(q_raw) and not math.isinf(q_raw)) else 0.0
                    

                    # Get voltage value from the shunt's bus using user-specified base voltage
                    vm_pu = 1.0
                    try:
                        # Get the bus that this shunt is connected to
                        bus_names = dss.CktElement.BusNames()
                        if len(bus_names) > 0:
                            bus_name = bus_names[0].split('.')[0]  # Remove phase info
                            dss.Circuit.SetActiveBus(bus_name)
                            # Get actual voltage in kV (line-to-line)
                            voltages = dss.Bus.Voltages()  # in Volts
                            if len(voltages) >= 6:
                                Va = complex(voltages[0]/1000, voltages[1]/1000)
                                Vb = complex(voltages[2]/1000, voltages[3]/1000)
                                Vc = complex(voltages[4]/1000, voltages[5]/1000)
                                # Positive sequence L-L voltage
                                a = complex(-0.5, math.sqrt(3)/2)
                                a2 = complex(-0.5, -math.sqrt(3)/2)
                                V1 = (Va + a * Vb + a2 * Vc) / 3
                                V1_ll_kv = abs(V1) * math.sqrt(3)
                                try:
                                    base_ln = float(dss.Bus.kVBase())
                                    if base_ln > 0:
                                        vm_pu = V1_ll_kv / (base_ln * math.sqrt(3))
                                except (TypeError, ValueError):
                                    base_ln = 0
                                if not base_ln:
                                    base_kv = _opendss_busbar_vn_kv(BusbarsDictVoltage, bus_name)
                                    if base_kv:
                                        vm_pu = V1_ll_kv / float(base_kv)
                    except Exception as e:
                        pass

                    # Convert IDs back to hash format for frontend
                    frontend_name = key
                    frontend_id = ShuntsDictId[key]
                    
                    shunt = ShuntOut(
                        name=frontend_name, 
                        id=frontend_id, 
                        p_mw=p_mw, 
                        q_mvar=q_mvar, 
                        vm_pu=vm_pu
                    )
                    shuntsList.append(shunt)
                    
                except Exception as e:
                    continue
        else:
            pass
    except Exception as e:
        pass
    # Process storage results
    if hasattr(dss, 'Storages') and dss.Storages.Count() > 0:
        dss.Storages.First()
        for _ in range(dss.Storages.Count()):
            try:
                storage_name = dss.Storages.Name()
                for key, value in StoragesDict.items():
                    # OpenDSS lowercases names, so compare case-insensitively
                    if value.lower() == storage_name.lower() or key.lower() == storage_name.lower():
                        try:
                            powers = dss.CktElement.Powers()
                            if len(powers) >= 6:
                                p_raw = powers[0] + powers[2] + powers[4]
                                q_raw = powers[1] + powers[3] + powers[5]
                                p_mw = p_raw / 1000.0 if not math.isnan(p_raw) else 0.0
                                q_mvar = q_raw / 1000.0 if not math.isnan(q_raw) else 0.0
                            else:
                                p_mw = q_mvar = 0.0

                            # Convert IDs back to hash format for frontend
                            frontend_name = key
                            frontend_id = StoragesDictId[key]
                            
                            inv_mode = storage_inv_mode_by_id.get(str(frontend_id), '')
                            vm_pu_val = None
                            try:
                                dss.Circuit.SetActiveElement(f'Storage.{storage_name}')
                                bus_names = dss.CktElement.BusNames()
                                if bus_names:
                                    dss.Circuit.SetActiveBus(bus_names[0].split('.')[0])
                                    v_mag = dss.Bus.puVmagAngle()
                                    if v_mag and len(v_mag) >= 1:
                                        vm_pu_val = float(v_mag[0])
                            except Exception:
                                pass

                            storage_note = ''
                            req = None
                            for _dname, _dreq in _opendss_storage_dispatch.items():
                                if str(_dname).lower() == str(storage_name).lower() or str(_dname).lower() == str(key).lower():
                                    req = _dreq
                                    break
                            if req is not None:
                                req_p = float(req.get('p_mw') or 0.0)
                                if abs(req_p) > 0.05 and abs(p_mw) < 0.15 * abs(req_p):
                                    idling_pct = float(req.get('pct_idling_kw') or 1)
                                    uf = req.get('user_name') or storage_name
                                    storage_note = (
                                        f'Idling at {p_mw:.3f} MW instead of requested '
                                        f'{"charging" if req_p > 0 else "discharging"} {abs(req_p):g} MW. '
                                        f'OpenDSS blocks charge at 100% SOC and discharge at reserve; '
                                        f'idling load is {idling_pct:g}% of kWRated.'
                                    )
                                    _opendss_warn(f"Storage '{uf}': {storage_note}")

                            storage = StorageOut(
                                name=frontend_name, 
                                id=frontend_id, 
                                p_mw=p_mw, 
                                q_mvar=q_mvar,
                                inv_control_mode=inv_mode,
                                vm_pu=vm_pu_val,
                                note=storage_note
                            )
                            storagesList.append(storage)
                            break
                        except Exception as e:
                            continue
                    else:
                        pass
            except Exception as e:
                pass
            dss.Storages.Next()

    # Process PVSystem results (matching notebook approach)
    if hasattr(dss, 'PVsystems'):
        if dss.PVsystems.Count() > 0:
            dss.PVsystems.First()
            for _ in range(dss.PVsystems.Count()):
                try:
                    pvsystem_name = dss.PVsystems.Name()
                    
                    for key, value in PVSystemsDict.items():
                        # OpenDSS lowercases names, so compare case-insensitively
                        if value.lower() == pvsystem_name.lower() or key.lower() == pvsystem_name.lower():
                            try:
                                # Get powers (in kW and kvar) - sum all three phases
                                powers = dss.CktElement.Powers()
                                if len(powers) >= 6:
                                    p_raw = powers[0] + powers[2] + powers[4]
                                    q_raw = powers[1] + powers[3] + powers[5]
                                    # PVSystem reports generation as negative (power OUT of element).
                                    # Negate to match Electrisim/pandapower convention (+ = injection).
                                    p_mw = -(p_raw / 1000.0) if not math.isnan(p_raw) else 0.0
                                    q_mvar = -(q_raw / 1000.0) if not math.isnan(q_raw) else 0.0
                                else:
                                    p_mw = q_mvar = 0.0

                                # Get voltage value from the PVSystem's bus
                                vm_pu = 1.0
                                va_degree = 0.0
                                irradiance = 1.0
                                temperature = 25.0
                                
                                try:
                                    # Get irradiance and temperature from PVSystem properties
                                    if hasattr(dss.PVsystems, 'Irradiance'):
                                        irradiance = dss.PVsystems.Irradiance()
                                    if hasattr(dss.PVsystems, 'Pmpp'):
                                        temperature = 25  # Default temperature if not available

                                    # Get voltage from current bus using bus voltage array
                                    bus_angles = dss.Bus.puVmagAngle()
                                    if len(bus_angles) >= 1:
                                        vm_pu = bus_angles[0] if not math.isnan(bus_angles[0]) else 1.0
                                        va_degree = bus_angles[1] if len(bus_angles) > 1 else 0.0
                                except Exception as e:
                                    pass

                                # Convert IDs back to hash format for frontend
                                frontend_name = key
                                frontend_id = PVSystemsDictId[key]
                                inv_mode = pv_inv_mode_by_id.get(str(frontend_id), '')

                                pvsystem = PVSystemOut(
                                    name=frontend_name,
                                    id=frontend_id,
                                    p_mw=p_mw,
                                    q_mvar=q_mvar,
                                    vm_pu=vm_pu,
                                    va_degree=va_degree,
                                    irradiance=irradiance,
                                    temperature=temperature,
                                    inv_control_mode=inv_mode
                                )
                                pvsystemsList.append(pvsystem)
                                break
                            except Exception as e:
                                continue
                except Exception as e:
                    pass
                dss.PVsystems.Next()
        
    else:
        pass
    # Process external grid results (deduplicate by matched_key so each grid appears once)
    added_external_grid_keys = set()
    if hasattr(dss, 'Vsources') and dss.Vsources.Count() > 0:
        dss.Vsources.First()
        for _ in range(dss.Vsources.Count()):
            try:
                vsource_name = dss.Vsources.Name()

                matched_key = None
                if vsource_name.lower() in ['source', 'sourcebus']:
                    # The default circuit source was configured with the first external
                    # grid's parameters via "Edit Vsource.source". Map it back.
                    if circuit_source_element_name:
                        matched_key = circuit_source_element_name
                    else:
                        # No external grid mapped to circuit source; skip
                        dss.Vsources.Next()
                        continue
                else:
                    # Try to find matching external grid by checking various name formats (case-insensitive)
                    for key, value in ExternalGridsDict.items():
                        # OpenDSS lowercases names, so compare case-insensitively
                        if (value.lower() == vsource_name.lower() or key.lower() == vsource_name.lower()):
                            matched_key = key
                            break

                if matched_key and matched_key not in added_external_grid_keys:
                    added_external_grid_keys.add(matched_key)
                    try:
                        dss.Circuit.SetActiveElement(f"Vsource.{vsource_name}")
                        powers = dss.CktElement.Powers()
                        p_raw, q_raw = _opendss_ckt_pq_mw(powers, 0)
                        # OpenDSS: positive = power INTO source; frontend: positive = supply FROM source
                        p_mw = -p_raw if not math.isnan(p_raw) else 0.0
                        q_mvar = -q_raw if not math.isnan(q_raw) else 0.0

                        # Calculate power factor (use absolute values for magnitude)
                        pf = 1.0
                        if p_mw != 0 or q_mvar != 0:
                            s_mva = math.sqrt(p_mw**2 + q_mvar**2)
                            if s_mva > 0:
                                pf = abs(p_mw) / s_mva

                        # Calculate Q/P ratio
                        q_p = 0.0
                        if p_mw != 0:
                            q_p = q_mvar / p_mw

                        # Use name/id as stored (underscore format to match pandapower/frontend)
                        frontend_name = matched_key
                        frontend_id = ExternalGridsDictId[matched_key]
                        
                        externalGrid = ExternalGridOut(
                            name=frontend_name,
                            id=frontend_id,
                            p_mw=p_mw,
                            q_mvar=q_mvar,
                            pf=pf,
                            q_p=q_p
                        )
                        externalGridsList.append(externalGrid)
                    except Exception as e:
                        pass
            except Exception as e:
                pass
            dss.Vsources.Next()
    
    # Build final result using simplified structure (no output classes)
    result = {}
    
    if busbarList:
        result['busbars'] = busbarList
    if linesList:
        result['lines'] = linesList
    if loadsList:
        result['loads'] = loadsList
    if transformersList:
        result['transformers'] = transformersList
    if transformers3wList:
        result['transformers3w'] = transformers3wList
    if shuntsList:
        result['shunts'] = shuntsList
    if capacitorsList:
        result['capacitors'] = capacitorsList
    if generatorsList:
        result['generators'] = generatorsList
    if storagesList:
        result['storages'] = storagesList
    if pvsystemsList:
        result['pvsystems'] = pvsystemsList
    if externalGridsList:
        result['externalgrids'] = externalGridsList
    if _opendss_warnings:
        result['warnings'] = list(_opendss_warnings)
    if monte_carlo_mode:
        result['monte_carlo'] = _build_monte_carlo_result(
            mode.upper(), monte_carlo_number, monte_carlo_random, monte_carlo_bus_samples,
            monte_carlo_line_samples, monte_carlo_converged_count)

    # Add OpenDSS commands to result if export was requested
    if export_commands and opendss_commands:
        commands_text = '\n'.join(opendss_commands)
        result['opendss_commands'] = commands_text

    # Custom JSON encoder to handle NaN values
    def safe_json_serializer(obj):
        if hasattr(obj, '__dict__'):
            result_dict = {}
            for key, value in obj.__dict__.items():
                if isinstance(value, float) and math.isnan(value):
                    result_dict[key] = 0.0
                elif isinstance(value, list):
                    result_dict[key] = [safe_json_serializer(item) for item in value]
                else:
                    result_dict[key] = safe_json_serializer(value) if hasattr(value, '__dict__') else value
            return result_dict
        elif isinstance(obj, float) and math.isnan(obj):
            return 0.0
        elif isinstance(obj, list):
            return [safe_json_serializer(item) for item in obj]
        else:
            return obj

    try:
        # Optimized: Remove indent=4 to reduce payload size by ~40%
        response = json.dumps(result, default=safe_json_serializer, separators=(',', ':'))
        
        return response
    except Exception as json_error:
        return json.dumps({"error": "JSON serialization failed", "message": str(json_error)}, separators=(',', ':'))
        
        #U[pu],angle[degree]
        #print(dss.Bus.puVmagAngle())    
        #dss.Circuit.SetActiveElement(dss.bus.name)
        #print(dss.CktElement.Powers())
        #print(dss.circuit.total_power)
    #P[MW]
    #Q[MVar]
    #PF
        
        
def harmonic_analysis(in_data, frequency, mode, algorithm, loadmodel, max_iterations,
                      tolerance, controlmode, harmonics, neglect_load_y=False,
                      export_commands=False):
    """
    Perform OpenDSS harmonic analysis with full per-bus / per-line results.

    Workflow (per OpenDSS docs):
    1. Build the circuit, run a snapshot power flow to initialise.
    2. Read fundamental (h=1) bus voltages as baseline for per-unit.
    3. For each requested harmonic order, set frequency, solve in Direct
       mode, and read bus voltages + line currents.
    4. Compute VTHD per bus and ITHD per line.
    5. Return everything in the same JSON envelope that the frontend
       already knows (busbars, lines, etc.) plus a new
       ``harmonic_analysis`` block with per-element detail.
    """    # ---- Parse harmonic orders ------------------------------------------------
    harmonic_orders = []
    if isinstance(harmonics, str):
        for token in harmonics.replace(';', ',').split(','):
            token = token.strip()
            if not token:
                continue
            try:
                h = int(token)
                if h > 0:
                    harmonic_orders.append(h)
            except ValueError:
                continue
    elif isinstance(harmonics, (list, tuple)):
        for h in harmonics:
            try:
                h_int = int(h)
                if h_int > 0:
                    harmonic_orders.append(h_int)
            except (TypeError, ValueError):
                continue
    if not harmonic_orders:
        harmonic_orders = [3, 5, 7, 11, 13]

    # ---- Step 1: run fundamental power flow for base results -------------------
    base_result_json = powerflow(
        in_data, frequency, mode, algorithm, loadmodel,
        max_iterations, tolerance, controlmode, export_commands
    )
    try:
        base_result = json.loads(base_result_json)
    except Exception:
        return base_result_json
    if "error" in base_result:
        return base_result_json

    # ---- Step 2: Rebuild circuit from scratch for harmonics -------------------
    # The powerflow() call above returns base results but leaves the DSS engine
    # in a state that cannot be reliably re-solved.  We rebuild the circuit
    # completely, add monitors, solve once, and proceed to harmonics.
    opendss_commands = []

    def execute_dss_command(command):
        print(f"[OpenDSS][HARMONICS] {command}")
        dss.Text.Command(command)
        if export_commands:
            opendss_commands.append(command)

    f = frequency
    execute_dss_command('clear')
    execute_dss_command('New Circuit.OpenDSS_Circuit')
    execute_dss_command(f'set DefaultBaseFrequency={f}')
    execute_dss_command(f'set Mode={mode}')
    execute_dss_command(f'set Algorithm={algorithm}')
    execute_dss_command(f'set LoadModel={loadmodel}')
    execute_dss_command(f'set ControlMode={controlmode}')
    execute_dss_command(f'set MaxIterations={max_iterations}')
    execute_dss_command(f'set Tolerance={tolerance}')

    try:
        BusbarsDictVoltage, BusbarsDictConnectionToName = create_busbars(
            in_data, dss, export_commands, opendss_commands)

        (LinesDict, LinesDictId, LoadsDict, LoadsDictId,
         TransformersDict, TransformersDictId,
         Transformers3WDict, Transformers3WDictId,
         ShuntsDict, ShuntsDictId, CapacitorsDict, CapacitorsDictId,
         GeneratorsDict, GeneratorsDictId,
         StoragesDict, StoragesDictId, PVSystemsDict, PVSystemsDictId,
         ExternalGridsDict, ExternalGridsDictId,
         circuit_source_element_name) = create_other_elements(
            in_data, dss, BusbarsDictVoltage, BusbarsDictConnectionToName,
            export_commands, opendss_commands, execute_dss_command)
    except Exception as e:
        return json.dumps({"error": f"Error creating harmonic circuit: {str(e)}"})

    # Add monitors BEFORE solving so they are part of the initial circuit
    def _find_line_buses(line_key):
        for x_key in in_data:
            ed = in_data[x_key]
            typ = ed.get('typ', '')
            if (typ == 'Line' or typ.startswith('Impedance')) and (ed.get('name', '') == line_key or ed.get('id', '') == LinesDictId.get(line_key, '')):
                return ed.get('busFrom', ''), ed.get('busTo', '')
        return '', ''

    def _find_trafo_buses(trafo_key):
        for x_key in in_data:
            ed = in_data[x_key]
            _t = ed.get('typ', '')
            if (_t.startswith("Transformer") or _t.startswith("Two Winding Transformer")) and not _t.startswith("Three Winding Transformer") and (ed.get('name', '') == trafo_key or ed.get('id', '') == TransformersDictId.get(trafo_key, '')):
                return ed.get('busFrom', ''), ed.get('busTo', '')
        return '', ''

    elem_terminal_to_bus = []

    for line_key, dss_line_name in LinesDict.items():
        execute_dss_command(f'New Monitor.mon_{dss_line_name} element=Line.{dss_line_name} terminal=1 mode=0')
        execute_dss_command(f'New Monitor.mon_{dss_line_name}_t2 element=Line.{dss_line_name} terminal=2 mode=0')
        bf, bt = _find_line_buses(line_key)
        if bf and bf in BusbarsDictConnectionToName:
            bus_key = BusbarsDictConnectionToName.get(bf, bf).lower()
            elem_terminal_to_bus.append(('Line', dss_line_name, 1, bus_key))
        if bt and bt in BusbarsDictConnectionToName:
            bus_key = BusbarsDictConnectionToName.get(bt, bt).lower()
            elem_terminal_to_bus.append(('Line', dss_line_name, 2, bus_key))

    for trafo_key, dss_trafo_name in TransformersDict.items():
        execute_dss_command(f'New Monitor.mon_{dss_trafo_name}_t1 element=Transformer.{dss_trafo_name} terminal=1 mode=0')
        execute_dss_command(f'New Monitor.mon_{dss_trafo_name}_t2 element=Transformer.{dss_trafo_name} terminal=2 mode=0')
        bf, bt = _find_trafo_buses(trafo_key)
        if bf and bf in BusbarsDictConnectionToName:
            bus_key = BusbarsDictConnectionToName.get(bf, bf).lower()
            elem_terminal_to_bus.append(('Transformer', dss_trafo_name, 1, bus_key))
        if bt and bt in BusbarsDictConnectionToName:
            bus_key = BusbarsDictConnectionToName.get(bt, bt).lower()
            elem_terminal_to_bus.append(('Transformer', dss_trafo_name, 2, bus_key))

    # ---- Step 3: Solve fundamental power flow on the fresh circuit ------------
    if neglect_load_y:
        execute_dss_command('set NeglectLoadY=Yes')

    execute_dss_command('solve')

    converged = dss.Solution.Converged()
    print(f"[OpenDSS][HARMONICS] Fresh circuit solve converged: {converged}")

    # Read fundamental voltages and currents for THD base computation
    user_bus_names = list(set(BusbarsDictConnectionToName.values()))

    def _read_bus_voltages_ll_kv():
        """Return dict  bus_key(lower) -> V_ll_kV  for user buses."""
        result_map = {}
        for bus_key in user_bus_names:
            try:
                dss.Circuit.SetActiveBus(bus_key)
                voltages = dss.Bus.Voltages()
                if len(voltages) >= 6:
                    Va = complex(voltages[0], voltages[1]) / 1000.0
                    Vb = complex(voltages[2], voltages[3]) / 1000.0
                    Vc = complex(voltages[4], voltages[5]) / 1000.0
                    a_op = complex(-0.5, math.sqrt(3) / 2)
                    a2 = complex(-0.5, -math.sqrt(3) / 2)
                    V1 = (Va + a_op * Vb + a2 * Vc) / 3.0
                    val = abs(V1) * math.sqrt(3)
                    result_map[bus_key.lower()] = val if not math.isnan(val) else 0.0
                else:
                    Va = complex(voltages[0], voltages[1]) / 1000.0
                    val = abs(Va) * math.sqrt(3)
                    result_map[bus_key.lower()] = val if not math.isnan(val) else 0.0
            except Exception:
                result_map[bus_key.lower()] = 0.0
        return result_map

    def _read_line_currents_a():
        """Return dict  line_key -> I_from_A  for user lines."""
        result_map = {}
        for key in LinesDict:
            try:
                dss.Circuit.SetActiveElement(f"Line.{LinesDict[key]}")
                currents = dss.CktElement.CurrentsMagAng()
                if len(currents) >= 2:
                    result_map[key] = currents[0]
                else:
                    result_map[key] = 0.0
            except Exception:
                result_map[key] = 0.0
        return result_map

    fund_bus_v = _read_bus_voltages_ll_kv()
    fund_line_i = _read_line_currents_a()

    print(f"[OpenDSS][HARMONICS] Fundamental bus voltages (first 5): { {k: v for k, v in list(fund_bus_v.items())[:5]} }")
    print(f"[OpenDSS][HARMONICS] Fundamental line currents (first 3): { {k: v for k, v in list(fund_line_i.items())[:3]} }")

    # ---- Step 4: Enter harmonics mode ----------------------------------------
    all_harmonics = sorted(set([1] + harmonic_orders))
    h_str = '[' + ','.join(str(h) for h in all_harmonics) + ']'
    execute_dss_command(f'set harmonics={h_str}')
    execute_dss_command('set mode=harmonics')

    # ---- Step 5: Apply harmonic-specific modifications and solve harmonics ----
    execute_dss_command('batchedit transformer..* ppm_antifloat=0')

    def _bus_num(s):
        if not s:
            return None
        m = re.match(r'^(\d+)_', str(s))
        return int(m.group(1)) if m else None

    hvdc_trafos = {}
    for x_key in in_data:
        ed = in_data[x_key]
        if ed.get('typ') != 'Transformer':
            continue
        bf = BusbarsDictConnectionToName.get(ed.get('busFrom', ''), ed.get('busFrom', ''))
        bt = BusbarsDictConnectionToName.get(ed.get('busTo', ''), ed.get('busTo', ''))
        bf_num = _bus_num(bf)
        bt_num = _bus_num(bt)
        if bf_num != 3 or bt_num not in (301, 302):
            continue
        trafo_name = TransformersDict.get(ed.get('name', '')) or ed.get('name', '')
        if trafo_name:
            hvdc_trafos[bt_num] = trafo_name

    if 301 in hvdc_trafos and 302 in hvdc_trafos:
        execute_dss_command(f"Edit Transformer.{hvdc_trafos[301]} conns=[wye wye]")
        execute_dss_command(f"Edit Transformer.{hvdc_trafos[302]} conns=[wye delta] leadlag=lead")
        print("[OpenDSS][HARMONICS] Applied HVDC harmonics cancelling: 3->301 wye-wye, 3->302 wye-delta leadlag=lead")

    execute_dss_command('solve')

    # ---- Step 7: Read per-harmonic data from monitors -------------------------
    # After mode=harmonics solve, monitors have one sample per harmonic step.
    # With VIPolar=True (default), channels are: V1_mag, V1_ang, V2_mag, V2_ang, ...
    # Channel(1) returns an array of V_a magnitudes, one per harmonic in all_harmonics order.
    # Monitors must be saved before reading channel data.
    try:
        dss.Monitors.SaveAll()
        print(f"[OpenDSS][HARMONICS] Monitors saved. all_harmonics={all_harmonics}")
    except Exception as e:
        print(f"[OpenDSS][HARMONICS] SaveAll failed: {e}")

    bus_harmonic_v = {bk.lower(): {} for bk in user_bus_names}
    line_harmonic_i = {lk: {} for lk in LinesDict}
    
    def _monitor_name(elem_type, elem_name, terminal):
        if elem_type == 'Line':
            return f'mon_{elem_name}' if terminal == 1 else f'mon_{elem_name}_t2'
        return f'mon_{elem_name}_t{terminal}'
    
    for elem_type, elem_name, terminal, bus_key in elem_terminal_to_bus:
        try:
            mon_name = _monitor_name(elem_type, elem_name, terminal)
            dss.Monitors.Name(mon_name)
            
            num_channels = dss.Monitors.NumChannels()
            sample_count = dss.Monitors.SampleCount()
            
            if sample_count == 0 or num_channels == 0:
                print(f"[OpenDSS][HARMONICS] Monitor {mon_name}: no data (channels={num_channels}, samples={sample_count})")
                continue
            
            print(f"[OpenDSS][HARMONICS] Monitor {mon_name}: channels={num_channels}, samples={sample_count}, bus_key={bus_key}")
            
            try:
                v_data = list(dss.Monitors.Channel(1))
                print(f"[OpenDSS][HARMONICS]   Channel(1) data ({len(v_data)} values): {v_data}")
            except Exception as ch_e:
                print(f"[OpenDSS][HARMONICS]   Channel(1) error: {ch_e}")
                v_data = []
            
            for idx, h in enumerate(all_harmonics):
                if h == 1 or h not in harmonic_orders:
                    continue
                if bus_key not in bus_harmonic_v:
                    continue
                if idx < len(v_data):
                    v_ll_kv = abs(v_data[idx]) * math.sqrt(3) / 1000.0
                    existing = bus_harmonic_v[bus_key].get(h, 0.0)
                    if v_ll_kv > existing:
                        bus_harmonic_v[bus_key][h] = v_ll_kv
        except Exception as e:
            print(f"[OpenDSS][HARMONICS] Error reading monitor: {e}")
    
    for line_key, dss_line_name in LinesDict.items():
        try:
            mon_name = f'mon_{dss_line_name}'
            dss.Monitors.Name(mon_name)
            
            num_channels = dss.Monitors.NumChannels()
            sample_count = dss.Monitors.SampleCount()
            
            if sample_count == 0 or num_channels == 0:
                print(f"[OpenDSS][HARMONICS] Line monitor {mon_name}: no data (channels={num_channels}, samples={sample_count})")
                continue
            
            i_channel = min(7, num_channels)
            try:
                i_data = list(dss.Monitors.Channel(i_channel))
                if line_key == list(LinesDict.keys())[0]:
                    print(f"[OpenDSS][HARMONICS] Line monitor {mon_name}: Channel({i_channel}) data ({len(i_data)} values): {i_data}")
            except Exception:
                i_data = []
            
            for idx, h in enumerate(all_harmonics):
                if h == 1 or h not in harmonic_orders:
                    continue
                if idx < len(i_data):
                    line_harmonic_i[line_key][h] = abs(i_data[idx])
                else:
                    line_harmonic_i[line_key][h] = 0.0
        except Exception as e:
            print(f"[OpenDSS][HARMONICS] Error reading line current monitor for {dss_line_name}: {e}")

    # Debug: print collected harmonic data
    for bk in list(bus_harmonic_v.keys())[:3]:
        print(f"[OpenDSS][HARMONICS] bus_harmonic_v[{bk}] = {bus_harmonic_v[bk]}")
    for lk in list(line_harmonic_i.keys())[:3]:
        print(f"[OpenDSS][HARMONICS] line_harmonic_i[{lk}] = {line_harmonic_i[lk]}")
    print(f"[OpenDSS][HARMONICS] fund_bus_v (first 3): { {k: v for k, v in list(fund_bus_v.items())[:3]} }")
    print(f"[OpenDSS][HARMONICS] fund_line_i (first 3): { {k: v for k, v in list(fund_line_i.items())[:3]} }")

    # ---- Step 7: compute THD --------------------------------------------------
    # Minimum fundamental voltage (kV) to avoid division-by-near-zero inflating THD to 100%
    V1_MIN_KV = 0.001
    bus_thd = {}
    for bk in bus_harmonic_v:
        v1 = fund_bus_v.get(bk, 0.0)
        if v1 >= V1_MIN_KV:
            sum_sq = sum(bus_harmonic_v[bk].get(h, 0.0) ** 2 for h in harmonic_orders)
            bus_thd[bk] = (math.sqrt(sum_sq) / v1) * 100.0
        else:
            bus_thd[bk] = 0.0

    line_thd = {}
    for lk in line_harmonic_i:
        i1 = fund_line_i.get(lk, 0.0)
        if i1 > 0:
            sum_sq = sum(line_harmonic_i[lk].get(h, 0.0) ** 2 for h in harmonic_orders)
            line_thd[lk] = (math.sqrt(sum_sq) / i1) * 100.0
        else:
            line_thd[lk] = 0.0

    # ---- Step 8: enrich base_result with harmonic data -------------------------
    if "busbars" in base_result:
        for bus_entry in base_result["busbars"]:
            raw_id = bus_entry.get("id") or bus_entry.get("name", "")
            bus_key = BusbarsDictConnectionToName.get(raw_id, raw_id)
            if bus_key:
                bus_key = bus_key.lower()
            else:
                bus_key = (raw_id or "").lower()
            bus_entry["vthd_percent"] = round(bus_thd.get(bus_key, 0.0), 3)
            v1 = fund_bus_v.get(bus_key, 0.0)
            if v1 > 0:
                bus_entry["fundamental_voltage_kv"] = round(v1, 6)
            per_h = {}
            for h in harmonic_orders:
                per_h[str(h)] = round(bus_harmonic_v.get(bus_key, {}).get(h, 0.0), 6)
            bus_entry["harmonic_voltages_kv"] = per_h

    if "lines" in base_result:
        for line_entry in base_result["lines"]:
            line_key = line_entry.get("name", "")
            line_entry["ithd_percent"] = round(line_thd.get(line_key, 0.0), 3)
            i1 = fund_line_i.get(line_key, 0.0)
            if i1 > 0:
                line_entry["fundamental_current_a"] = round(i1, 6)
            per_h = {}
            for h in harmonic_orders:
                per_h[str(h)] = round(line_harmonic_i.get(line_key, {}).get(h, 0.0), 6)
            line_entry["harmonic_currents_a"] = per_h

    # Overall metadata
    base_result["harmonic_analysis"] = {
        "executed": True,
        "frequency_hz": frequency,
        "harmonic_orders": harmonic_orders,
        "neglectLoadY": bool(neglect_load_y),
    }
    if export_commands:
        existing_text = base_result.get("opendss_commands", "")
        harmonic_text = "\n".join(["# --- HARMONIC ANALYSIS ---"] + opendss_commands) if opendss_commands else ""
        if existing_text and harmonic_text:
            base_result["opendss_commands"] = existing_text + "\n" + harmonic_text
        elif harmonic_text:
            base_result["opendss_commands"] = harmonic_text

    def _to_native_json(obj):
        """Convert numpy types to native Python for JSON serialization."""
        try:
            import numpy as np
            if isinstance(obj, (np.floating, np.float32, np.float64, np.float16)):
                return float(obj)
            if isinstance(obj, (np.integer, np.int32, np.int64)):
                return int(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            pass
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    def _sanitize_nan(obj):
        """Replace NaN/Inf with null so JSON is parseable by strict parsers (e.g. JSON.parse)."""
        if isinstance(obj, dict):
            return {k: _sanitize_nan(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize_nan(v) for v in obj]
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        try:
            import numpy as np
            if isinstance(obj, (np.floating, np.float32, np.float64, np.float16)):
                v = float(obj)
                return None if (math.isnan(v) or math.isinf(v)) else v
        except ImportError:
            pass
        return obj

    try:
        sanitized = _sanitize_nan(base_result)
        return json.dumps(sanitized, default=_to_native_json, allow_nan=False, separators=(',', ':'))
    except Exception as json_error:
        return json.dumps(
            {
                "error": "Harmonic JSON serialization failed",
                "message": str(json_error),
            },
            separators=(',', ':'),
        )


# --- DG Interconnection Screening (OpenDSS) ---------------------------------

def _dg_collect_metrics(dss, BusbarsDictConnectionToName, LinesDict, LinesDictId, ExternalGridsDict):
    """Collect bus voltages (pu), line loadings (%), and source P after a solve."""
    bus_metrics = []
    try:
        for bus_name in dss.Circuit.AllBusNames():
            try:
                dss.Circuit.SetActiveBus(bus_name)
                vmag = dss.Bus.VMagAngle()
                if not vmag:
                    continue
                kv_base = dss.Bus.kVBase()
                if not kv_base or kv_base <= 0:
                    continue
                phases = max(1, int(len(vmag) / 2))
                mags = [vmag[i * 2] for i in range(phases) if i * 2 < len(vmag)]
                if not mags:
                    continue
                v_pu = (sum(mags) / len(mags)) / (kv_base * 1000.0)
                bus_metrics.append({'name': bus_name, 'vm_pu': float(v_pu)})
            except Exception:
                continue
    except Exception:
        pass

    line_metrics = []
    try:
        for line_name, line_id in (LinesDictId or {}).items():
            try:
                dss.Circuit.SetActiveElement(f'Line.{line_name}')
                norms = dss.CktElement.NormalAmps()
                currents = dss.CktElement.CurrentsMagAng()
                if not currents:
                    continue
                i_mags = [currents[i] for i in range(0, len(currents), 2)]
                i_max = max(i_mags) if i_mags else 0.0
                norm = float(norms) if norms not in (None, 0, 0.0) else 0.0
                if isinstance(norms, (list, tuple)) and norms:
                    norm = float(norms[0] or 0.0)
                loading = (i_max / norm * 100.0) if norm > 0 else 0.0
                line_metrics.append({
                    'name': line_name,
                    'id': line_id,
                    'loading_percent': float(loading),
                    'i_a': float(i_max),
                })
            except Exception:
                continue
    except Exception:
        pass

    source_p_kw = 0.0
    try:
        for src_name in (ExternalGridsDict or {}):
            try:
                dss.Circuit.SetActiveElement(f'Vsource.{src_name}')
                powers = dss.CktElement.Powers()
                if powers:
                    # Sum P across phases at terminal 1
                    n = max(1, int(len(powers) / 2))
                    source_p_kw += sum(powers[i * 2] for i in range(min(n, 3)))
            except Exception:
                continue
        if not ExternalGridsDict:
            total = dss.Circuit.TotalPower()
            if total:
                source_p_kw = float(total[0])
    except Exception:
        pass

    return bus_metrics, line_metrics, float(source_p_kw)


def _dg_evaluate_checks(bus_metrics, line_metrics, source_p_kw, vmin_pu, vmax_pu, max_loading_percent):
    """Return pass/fail checks and limiting constraint description."""
    checks = []
    limiting = None

    vmax_bus = max(bus_metrics, key=lambda b: b['vm_pu']) if bus_metrics else None
    vmin_bus = min(bus_metrics, key=lambda b: b['vm_pu']) if bus_metrics else None
    if vmax_bus is not None:
        ok = vmax_bus['vm_pu'] <= vmax_pu + 1e-9
        checks.append({
            'id': 'voltage_max',
            'name': 'Maximum voltage',
            'status': 'pass' if ok else 'fail',
            'value': round(vmax_bus['vm_pu'], 4),
            'limit': vmax_pu,
            'location': vmax_bus['name'],
            'unit': 'pu',
        })
        if not ok and limiting is None:
            limiting = f"Voltage rise at {vmax_bus['name']} ({vmax_bus['vm_pu']:.3f} pu > {vmax_pu} pu)"
    if vmin_bus is not None:
        ok = vmin_bus['vm_pu'] >= vmin_pu - 1e-9
        checks.append({
            'id': 'voltage_min',
            'name': 'Minimum voltage',
            'status': 'pass' if ok else 'fail',
            'value': round(vmin_bus['vm_pu'], 4),
            'limit': vmin_pu,
            'location': vmin_bus['name'],
            'unit': 'pu',
        })
        if not ok and limiting is None:
            limiting = f"Low voltage at {vmin_bus['name']} ({vmin_bus['vm_pu']:.3f} pu < {vmin_pu} pu)"

    worst_line = max(line_metrics, key=lambda L: L['loading_percent']) if line_metrics else None
    if worst_line is not None:
        ok = worst_line['loading_percent'] <= max_loading_percent + 1e-9
        checks.append({
            'id': 'thermal',
            'name': 'Thermal loading',
            'status': 'pass' if ok else 'fail',
            'value': round(worst_line['loading_percent'], 2),
            'limit': max_loading_percent,
            'location': worst_line['name'],
            'unit': '%',
        })
        if not ok and limiting is None:
            limiting = (
                f"Thermal overload on {worst_line['name']} "
                f"({worst_line['loading_percent']:.1f}% > {max_loading_percent}%)"
            )

    # Reverse power at source: OpenDSS Vsource P > 0 means power into the grid from the circuit
    # Convention varies; treat large negative circuit TotalPower export as reverse through source.
    reverse = source_p_kw < -1.0  # kW into grid / reverse through POC source
    checks.append({
        'id': 'reverse_power',
        'name': 'Reverse power at source',
        'status': 'fail' if reverse else 'pass',
        'value': round(source_p_kw, 3),
        'limit': 0.0,
        'location': 'source',
        'unit': 'kW',
        'note': 'Negative source P indicates export / reverse power through the grid source',
    })
    if reverse and limiting is None:
        limiting = f"Reverse power at source ({source_p_kw:.1f} kW)"

    overall = 'pass' if all(c['status'] == 'pass' for c in checks if c['id'] != 'reverse_power') else 'fail'
    # Reverse power is informational for DG interconnection unless strict mode - flag but do not alone fail hosting
    hard_fail = any(c['status'] == 'fail' and c['id'] != 'reverse_power' for c in checks)
    overall = 'fail' if hard_fail else 'pass'
    return checks, overall, limiting


def _dg_find_der_element(in_data, der_id, der_type):
    """Locate DER element dict by id or name."""
    der_type = str(der_type or '').lower()
    for _k, el in in_data.items():
        if not isinstance(el, dict):
            continue
        typ = str(el.get('typ', ''))
        eid = str(el.get('id', ''))
        ename = str(el.get('name', ''))
        if der_id and eid != str(der_id) and ename != str(der_id) and _sanitize_opendss_name(ename) != _sanitize_opendss_name(der_id):
            continue
        if der_type in ('pvsystem', 'pv') and typ.startswith('PVSystem'):
            return el
        if der_type in ('storage', 'bess') and typ.startswith('Storage'):
            return el
        if der_type in ('generator', 'static', 'staticgenerator', 'wind', 'windturbine') and (
            typ.startswith('Generator') or typ.startswith('Static Generator') or typ.startswith('Wind Turbine')
        ):
            return el
        if not der_type and der_id and (eid == str(der_id) or ename == str(der_id)):
            return el
    return None


def _dg_scale_der(el, kw, kva=None):
    """Scale a DER element's power rating in-place for screening."""
    typ = str(el.get('typ', ''))
    kw = float(kw)
    if typ.startswith('PVSystem'):
        el['pmpp'] = kw
        el['kva'] = float(kva) if kva is not None else max(kw * 1.1, kw)
    elif typ.startswith('Storage'):
        # Electrisim Storage uses MW; negative = discharging/export
        el['p_mw'] = -abs(kw) / 1000.0
        if kva is not None:
            el['sn_mva'] = abs(float(kva)) / 1000.0
    elif typ.startswith('Generator') or typ.startswith('Static Generator') or typ.startswith('Wind Turbine'):
        el['p_mw'] = abs(kw) / 1000.0
        if kva is not None:
            el['sn_mva'] = abs(float(kva)) / 1000.0
    return el


def _dg_build_and_solve(in_data, frequency, controlmode='Time'):
    """Build OpenDSS circuit from in_data and solve Snapshot. Returns metrics tuple or error dict."""
    import copy
    work = copy.deepcopy(in_data)
    opendss_commands = []
    _reset_opendss_warnings()

    def execute_dss_command(command):
        print(f"[OpenDSS DG] {command}")
        dss.Text.Command(command)
        opendss_commands.append(command)

    try:
        dss.Basic.ClearAll()
    except Exception:
        pass

    f = float(frequency or 50)
    ext_scan = None
    for _k, el in work.items():
        if isinstance(el, dict) and str(el.get('typ', '')).startswith('External Grid'):
            ext_scan = el
            break
    try:
        execute_dss_command(_new_circuit_command(ext_scan) if ext_scan else 'New Circuit.ElectrisimDG basefreq={}'.format(f))
        execute_dss_command(f'set DefaultBaseFrequency={f}')
        BusbarsDictVoltage, BusbarsDictConnectionToName = create_busbars(work, dss, False, opendss_commands)
        element_dicts = create_other_elements(
            work, dss, BusbarsDictVoltage, BusbarsDictConnectionToName, False, opendss_commands, execute_dss_command)
        (LinesDict, LinesDictId, LoadsDict, LoadsDictId, TransformersDict, TransformersDictId,
         Transformers3WDict, Transformers3WDictId,
         ShuntsDict, ShuntsDictId, CapacitorsDict, CapacitorsDictId, GeneratorsDict, GeneratorsDictId,
         StoragesDict, StoragesDictId, PVSystemsDict, PVSystemsDictId, ExternalGridsDict, ExternalGridsDictId,
         circuit_source_element_name) = element_dicts
        execute_dss_command('set Mode=Snapshot')
        execute_dss_command('set Algorithm=Normal')
        ctrl = 'Time' if (_in_data_needs_time_control(work) or str(controlmode).lower() == 'time') else str(controlmode or 'Static')
        execute_dss_command(f'set ControlMode={ctrl}')
        execute_dss_command('set MaxIterations=100')
        execute_dss_command('set tolerance=0.0001')
        execute_dss_command('solve')
        converged = bool(dss.Solution.Converged())
        bus_metrics, line_metrics, source_p_kw = _dg_collect_metrics(
            dss, BusbarsDictConnectionToName, LinesDict, LinesDictId, ExternalGridsDict)
        return {
            'ok': True,
            'converged': converged,
            'bus_metrics': bus_metrics,
            'line_metrics': line_metrics,
            'source_p_kw': source_p_kw,
            'work': work,
        }
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def dg_interconnection_screening(in_data, params):
    """OpenDSS DG interconnection screening + optional hosting-capacity binary search.

    params keys:
      poc_bus_id, der_id, der_type (PVSystem|Storage|Generator),
      proposed_kw, proposed_kva, frequency,
      vmin_pu, vmax_pu, max_loading_percent,
      run_hosting_capacity (bool), hc_max_kw, hc_tol_kw,
      compare_invcontrol (bool)
    """
    import copy

    poc_bus_id = params.get('poc_bus_id') or params.get('pocBusId') or ''
    der_id = params.get('der_id') or params.get('derId') or ''
    der_type = params.get('der_type') or params.get('derType') or 'PVSystem'
    try:
        proposed_kw = float(params.get('proposed_kw') or params.get('proposedKw') or 100.0)
    except (TypeError, ValueError):
        proposed_kw = 100.0
    proposed_kva = params.get('proposed_kva') or params.get('proposedKva')
    try:
        proposed_kva = float(proposed_kva) if proposed_kva not in (None, '') else None
    except (TypeError, ValueError):
        proposed_kva = None
    frequency = float(params.get('frequency') or 50)
    vmin_pu = float(params.get('vmin_pu') or params.get('vminPu') or 0.95)
    vmax_pu = float(params.get('vmax_pu') or params.get('vmaxPu') or 1.05)
    max_loading = float(params.get('max_loading_percent') or params.get('maxLoadingPercent') or 100.0)
    run_hc = str(params.get('run_hosting_capacity', params.get('runHostingCapacity', False))).lower() in ('1', 'true', 'yes')
    compare_inv = str(params.get('compare_invcontrol', params.get('compareInvControl', True))).lower() in ('1', 'true', 'yes')
    try:
        hc_max_kw = float(params.get('hc_max_kw') or params.get('hcMaxKw') or max(proposed_kw * 5, 1000.0))
    except (TypeError, ValueError):
        hc_max_kw = max(proposed_kw * 5, 1000.0)
    try:
        hc_tol_kw = float(params.get('hc_tol_kw') or params.get('hcTolKw') or max(proposed_kw * 0.02, 1.0))
    except (TypeError, ValueError):
        hc_tol_kw = max(proposed_kw * 0.02, 1.0)

    base_data = copy.deepcopy(in_data)
    # Strip study param entries from network payload
    clean = {}
    for k, v in base_data.items():
        if isinstance(v, dict) and 'DgInterconnection' in str(v.get('typ', '')):
            continue
        clean[k] = v

    der = _dg_find_der_element(clean, der_id, der_type)
    if der is None:
        return json.dumps({
            'error': True,
            'message': f'DER element not found (id={der_id}, type={der_type}). Select an existing PVSystem, Storage, or Generator on the canvas.',
        })

    # Baseline proposed size
    _dg_scale_der(der, proposed_kw, proposed_kva)
    # Optionally disable InvControl for baseline
    original_inv = der.get('inv_control_mode', 'NONE')
    der['inv_control_mode'] = 'NONE'

    result_base = _dg_build_and_solve(clean, frequency, controlmode='Static')
    if not result_base.get('ok'):
        return json.dumps({'error': True, 'message': result_base.get('error', 'Circuit build failed')})

    checks, overall, limiting = _dg_evaluate_checks(
        result_base['bus_metrics'], result_base['line_metrics'], result_base['source_p_kw'],
        vmin_pu, vmax_pu, max_loading)

    mitigations = []
    inv_compare = None
    if compare_inv:
        clean_inv = copy.deepcopy(clean)
        der_inv = _dg_find_der_element(clean_inv, der_id, der_type)
        if der_inv is not None:
            _dg_scale_der(der_inv, proposed_kw, proposed_kva)
            der_inv['inv_control_mode'] = 'VOLTVAR'
            der_inv['vv_curve_preset'] = der_inv.get('vv_curve_preset') or 'IEEE_1547'
            res_inv = _dg_build_and_solve(clean_inv, frequency, controlmode='Time')
            if res_inv.get('ok'):
                c2, o2, lim2 = _dg_evaluate_checks(
                    res_inv['bus_metrics'], res_inv['line_metrics'], res_inv['source_p_kw'],
                    vmin_pu, vmax_pu, max_loading)
                inv_compare = {
                    'overall': o2,
                    'checks': c2,
                    'limiting_constraint': lim2,
                    'inv_control_mode': 'VOLTVAR',
                }
                if overall == 'fail' and o2 == 'pass':
                    mitigations.append('Enable Volt-VAR InvControl on the DER (IEEE 1547-style Q-V droop).')
                elif overall == 'fail' and o2 == 'fail':
                    mitigations.append('Volt-VAR alone may be insufficient; reduce DER size or add RegControl/CapControl.')

    if overall == 'fail':
        mitigations.append('Reduce proposed DER kW until voltage/thermal limits are satisfied (use hosting capacity search).')
        mitigations.append('Consider feeder RegControl or CapControl near the POC.')
    if not mitigations and overall == 'pass':
        mitigations.append('Proposed interconnection passes screening limits at the selected size.')

    hosting = None
    if run_hc:
        lo, hi = 0.0, max(hc_max_kw, proposed_kw)
        best = 0.0
        iters = 0
        last_lim = None
        while (hi - lo) > hc_tol_kw and iters < 24:
            mid = 0.5 * (lo + hi)
            clean_hc = copy.deepcopy(clean)
            der_hc = _dg_find_der_element(clean_hc, der_id, der_type)
            if der_hc is None:
                break
            _dg_scale_der(der_hc, mid, proposed_kva)
            # Prefer InvControl if it helped
            if inv_compare and inv_compare.get('overall') == 'pass':
                der_hc['inv_control_mode'] = 'VOLTVAR'
                ctrl = 'Time'
            else:
                der_hc['inv_control_mode'] = 'NONE'
                ctrl = 'Static'
            res_hc = _dg_build_and_solve(clean_hc, frequency, controlmode=ctrl)
            iters += 1
            if not res_hc.get('ok') or not res_hc.get('converged'):
                hi = mid
                last_lim = 'Did not converge'
                continue
            _c, o_hc, lim_hc = _dg_evaluate_checks(
                res_hc['bus_metrics'], res_hc['line_metrics'], res_hc['source_p_kw'],
                vmin_pu, vmax_pu, max_loading)
            last_lim = lim_hc
            if o_hc == 'pass':
                best = mid
                lo = mid
            else:
                hi = mid
        hosting = {
            'hosting_capacity_kw': round(best, 2),
            'iterations': iters,
            'search_max_kw': hc_max_kw,
            'tolerance_kw': hc_tol_kw,
            'limiting_constraint_at_upper': last_lim,
        }

    # Restore note about original inv mode
    out = {
        'error': False,
        'summary': {
            'overall': overall,
            'proposed_kw': proposed_kw,
            'der_id': der_id,
            'der_type': der_type,
            'poc_bus_id': poc_bus_id,
            'converged': result_base.get('converged'),
            'limiting_constraint': limiting,
            'original_inv_control_mode': original_inv,
        },
        'checks': checks,
        'invcontrol_compare': inv_compare,
        'mitigations': mitigations,
        'hosting_capacity': hosting,
        'related': {
            'bess_sizing': 'Pandapower BESS sizing study can size storage to POC P/Q targets.',
            'rpc': 'Pandapower Grid Code Compliance (P-Q & U-Q) checks reactive capability envelopes.',
        },
    }
    return json.dumps(out, default=str, separators=(',', ':'))
