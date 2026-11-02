"""
Plant Supervisory Controller for Electrisim.

Leads the plant's STATCOMs (continuous reactive power) and variable shunt reactors (reactive
power in steps) to meet one target at a chosen busbar, normally the point of connection (POC).

Control modes (generator convention at the busbar: + = the plant supplies Q, capacitive):

* ``Q``       - reactive power fed into the busbar = ``q_set_mvar``
* ``V``       - busbar voltage = ``vm_set_pu``
* ``V_droop`` - Q = Q_droop * (vm_set_pu - V), with Q_droop = q_ref_mvar * 100 / droop_percent
                (Mvar per p.u.), as grid codes specify at the POC
* ``cosphi``  - Q = |P| * tan(acos(cos phi)); overexcited = +Q, underexcited = -Q
* ``QP``      - Q from a Q(P) characteristic, linear between points

The reactor steps take the bulk of the reactive power and the STATCOMs supply the exact
remainder, so the result at the busbar is continuous although the reactors switch in steps.
A reactor switches only when the STATCOMs leave their reserve band (``statcom_band`` x half
of their range, around the middle of the range), and then to the steps that bring the
STATCOMs back closest to the middle. Total reactor switching is capped (``max_switching``) so
the control loop always settles.

Each iteration moves the total device Q by a secant step on the target error, bounded to a
quarter of the total range. When every device is at the limit the error points to, the target
is out of reach: the controller stops there (``at_limit``). It also stops pushing once one of
its device buses reaches ``vm_min_pu`` / ``vm_max_pu`` (``at_limit`` = 'v_low' / 'v_high'), and
backs off if a bus is already outside that band, as a STATCOM's own voltage limits would.

This file is copied verbatim into exported pandapower scripts: numpy and pandapower only.
"""
import itertools
import math

import numpy as np
from pandapower.control.basic_controller import Controller

PSC_MODES = ('Q', 'V', 'V_droop', 'cosphi', 'QP')


def _terms_sum(net, terms):
    """Sum of sign * net[table].at[index, column] over (table, column, index, sign) terms."""
    total = 0.0
    for table, column, index, sign in terms or ():
        total += float(sign) * float(net[table].at[index, column])
    return total


def _interp(points, x):
    pts = sorted((float(a), float(b)) for a, b in points)
    if not pts:
        return 0.0
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1]


class PlantSupervisoryControl(Controller):
    """Plant Supervisory Controller (see module docstring).

    statcom_sgens   sgen indices that stand in for the STATCOMs (PQ sources set here)
    statcom_q_min / statcom_q_max   their Q ratings (generator convention)
    reactors        [{'shunt': index, 'steps': [pandapower steps], 'q_mvar': {step: Mvar absorbed at 1 p.u.}}]
    q_terms / p_terms   (table, column, index, sign): their sum is the Q / P the plant feeds into the busbar
    """

    def __init__(self, net, bus, mode='Q', statcom_sgens=(), statcom_q_min=(), statcom_q_max=(),
                 reactors=(), q_terms=(), p_terms=(), q_set_mvar=0.0, vm_set_pu=1.0,
                 droop_percent=4.0, q_ref_mvar=0.0, cos_phi=1.0, overexcited=True, qp_points=(),
                 statcom_band=0.5, tol_mvar=0.01, tol_vm_pu=1e-4, max_switching=20,
                 vm_min_pu=0.9, vm_max_pu=1.1,
                 name='Plant Supervisory Controller', in_service=True, order=1, level=0, **kwargs):
        super().__init__(net, in_service=in_service, order=order, level=level, **kwargs)
        if mode not in PSC_MODES:
            raise ValueError(f'unknown mode {mode!r}; use one of {PSC_MODES}')
        self.name = name
        self.bus = int(bus)
        self.mode = mode
        self.statcom_sgens = [int(i) for i in statcom_sgens]
        self.statcom_q_min = np.asarray(statcom_q_min, dtype=float).reshape(-1)
        self.statcom_q_max = np.asarray(statcom_q_max, dtype=float).reshape(-1)
        self.reactors = [
            {
                'shunt': int(r['shunt']),
                'steps': sorted(int(s) for s in r['steps']),
                'q_mvar': {int(k): float(v) for k, v in dict(r['q_mvar']).items()},
            }
            for r in reactors
        ]
        self.q_terms = [tuple(t) for t in q_terms]
        self.p_terms = [tuple(t) for t in p_terms]
        self.q_set = float(q_set_mvar)
        self.vm_set = float(vm_set_pu)
        self.q_droop = (float(q_ref_mvar) * 100.0 / float(droop_percent)
                        if droop_percent and q_ref_mvar else 0.0)
        self.cos_phi = float(cos_phi)
        self.overexcited = bool(overexcited)
        self.qp_points = [(float(a), float(b)) for a, b in qp_points]
        self.statcom_band = min(max(float(statcom_band), 0.0), 1.0)
        self.tol_mvar = float(tol_mvar)
        self.tol_vm = float(tol_vm_pu)
        self.max_switching = int(max_switching)
        self.vm_min = float(vm_min_pu)
        self.vm_max = float(vm_max_pu)
        self._reset()

    # --- state ----------------------------------------------------------------------------

    def _reset(self):
        self._x_old = None
        self._e_old = None
        self._slope = None if self.mode == 'V' else -1.0
        self._slope0 = self._slope
        self.switching = 0
        self.at_limit = None
        self.target = None
        self.p_meas = self.q_meas = self.vm_meas = None

    def initialize_control(self, net):
        self._reset()

    # --- measurement and target -----------------------------------------------------------

    def _measure(self, net):
        q = _terms_sum(net, self.q_terms)
        p = _terms_sum(net, self.p_terms)
        vm = float(net.res_bus.at[self.bus, 'vm_pu'])
        self.p_meas, self.q_meas, self.vm_meas = p, q, vm
        return p, q, vm

    def q_target(self, p, vm):
        if self.mode == 'Q':
            return self.q_set
        if self.mode == 'V_droop':
            return self.q_droop * (self.vm_set - vm)
        if self.mode == 'cosphi':
            c = min(max(abs(self.cos_phi), 1e-6), 1.0)
            q = abs(p) * math.tan(math.acos(c))
            return q if self.overexcited else -q
        if self.mode == 'QP':
            return _interp(self.qp_points, p)
        return None

    def _error(self, net):
        """(target - measured, tolerance): p.u. in V mode, Mvar otherwise."""
        p, q, vm = self._measure(net)
        if self.mode == 'V':
            self.target = self.vm_set
            return self.vm_set - vm, self.tol_vm
        self.target = self.q_target(p, vm)
        return self.target - q, self.tol_mvar

    # --- devices --------------------------------------------------------------------------

    def _vm_at(self, net, bus):
        try:
            v = float(net.res_bus.at[int(bus), 'vm_pu'])
            return v if v == v else 1.0
        except Exception:
            return 1.0

    def _reactor_q(self, net, r, step):
        """Reactor Q at ``step`` in generator convention (absorbing = negative), at present voltage."""
        vm = self._vm_at(net, net.shunt.at[r['shunt'], 'bus'])
        return -r['q_mvar'].get(int(step), 0.0) * vm * vm

    def _steps_now(self, net):
        return [int(round(float(net.shunt.at[r['shunt'], 'step']))) for r in self.reactors]

    def _statcom_range(self):
        return float(np.sum(self.statcom_q_min)), float(np.sum(self.statcom_q_max))

    def _device_q(self, net):
        stat = sum(float(net.sgen.at[i, 'q_mvar']) for i in self.statcom_sgens)
        reac = sum(self._reactor_q(net, r, s) for r, s in zip(self.reactors, self._steps_now(net)))
        return stat + reac

    def _range(self, net):
        s_min, s_max = self._statcom_range()
        r_min = sum(min(self._reactor_q(net, r, s) for s in r['steps']) for r in self.reactors if r['steps'])
        r_max = sum(max(self._reactor_q(net, r, s) for s in r['steps']) for r in self.reactors if r['steps'])
        return s_min + r_min, s_max + r_max

    def _combos(self, steps_now):
        lists = [r['steps'] or [s] for r, s in zip(self.reactors, steps_now)]
        size = 1
        for lst in lists:
            size *= max(len(lst), 1)
        if size <= 4096:
            return itertools.product(*lists)
        # Too many combinations: move one reactor at a time from the present steps.
        out = [tuple(steps_now)]
        for k, lst in enumerate(lists):
            for s in lst:
                c = list(steps_now)
                c[k] = s
                out.append(tuple(c))
        return out

    def _best_steps(self, net, x):
        """Reactor steps for a total device Q ``x``: keep the STATCOMs inside their band."""
        steps_now = self._steps_now(net)
        if not self.reactors or self.switching >= self.max_switching:
            return steps_now
        s_min, s_max = self._statcom_range()
        mid = 0.5 * (s_min + s_max)
        reserve = self.statcom_band * 0.5 * (s_max - s_min)
        r_now = sum(self._reactor_q(net, r, s) for r, s in zip(self.reactors, steps_now))
        res_now = x - r_now
        if abs(res_now - mid) <= reserve + 1e-6 and s_min - 1e-6 <= res_now <= s_max + 1e-6:
            return steps_now
        best_key, best = None, steps_now
        for combo in self._combos(steps_now):
            res = x - sum(self._reactor_q(net, r, s) for r, s in zip(self.reactors, combo))
            outside = max(s_min - res, 0.0, res - s_max)
            changes = sum(1 for a, b in zip(combo, steps_now) if a != b)
            key = (round(outside, 6), round(abs(res - mid), 6), changes)
            if best_key is None or key < best_key:
                best_key, best = key, list(combo)
        return best

    def _share(self, total):
        """Split the STATCOM total by rating in the direction of ``total``."""
        n = len(self.statcom_sgens)
        if n == 0:
            return np.zeros(0)
        w = self.statcom_q_max if total >= 0 else -self.statcom_q_min
        w = np.clip(np.asarray(w, dtype=float), 0.0, None)
        if w.sum() <= 0:
            w = np.ones(n)
        return np.clip(total * w / w.sum(), self.statcom_q_min, self.statcom_q_max)

    def _apply(self, net, x):
        steps = self._best_steps(net, x)
        if steps != self._steps_now(net):
            self.switching += 1
        s_min, s_max = self._statcom_range()
        r_q = sum(self._reactor_q(net, r, s) for r, s in zip(self.reactors, steps))
        stat = self._share(min(max(x - r_q, s_min), s_max))
        for i, q in zip(self.statcom_sgens, stat):
            net.sgen.at[i, 'q_mvar'] = float(q)
        for r, s in zip(self.reactors, steps):
            net.shunt.at[r['shunt'], 'step'] = int(s)

    # --- control loop ---------------------------------------------------------------------

    def is_converged(self, net):
        e, tol = self._error(net)
        x = self._device_q(net)
        x_min, x_max = self._range(net)
        if abs(e) < tol:
            self.at_limit = None
            # Settled on the target: also settle the reactors so the STATCOMs keep their reserve.
            return self._best_steps(net, x) == self._steps_now(net)
        if (e > 0 and x >= x_max - 1e-3) or (e < 0 and x <= x_min + 1e-3):
            self.at_limit = 'max' if e > 0 else 'min'
            return True
        v_lo, v_hi = self._device_vm_range(net)
        if v_lo is not None and e < 0 and self.vm_min - 0.01 <= v_lo <= self.vm_min + 0.005:
            self.at_limit = 'v_low'  # more absorption would pull the device buses below vm_min
            return True
        if v_hi is not None and e > 0 and self.vm_max - 0.005 <= v_hi <= self.vm_max + 0.01:
            self.at_limit = 'v_high'
            return True
        return False

    def control_step(self, net):
        e, tol = self._error(net)
        x = self._device_q(net)
        x_min, x_max = self._range(net)
        if abs(e) < tol:
            move = 0.0
        else:
            if self._x_old is not None and abs(x - self._x_old) > 1e-6:
                # Other controllers (Park Controller, tap changers) move in the same iterations,
                # so one secant sample can be far off: smooth it and keep it in a sane band.
                sample = (e - self._e_old) / (x - self._x_old)
                if sample < 0:
                    if self._slope is None:
                        self._slope0 = sample
                        self._slope = sample
                    else:
                        self._slope = 0.5 * self._slope + 0.5 * sample
                    if self.mode == 'V':
                        lo, hi = 5.0 * self._slope0, 0.2 * self._slope0
                    else:
                        lo, hi = -3.0, -0.3
                    self._slope = min(max(self._slope, lo), hi)
            if self._slope is None:
                # Voltage mode before any response is known: probe in the expected direction.
                move = math.copysign(max(1.0, 0.02 * (x_max - x_min)), e)
            else:
                move = -e / self._slope
            if self._e_old is not None and e * self._e_old < 0:
                move *= 0.5  # the last step overshot: halve this one
        max_step = max(1.0, 0.25 * (x_max - x_min))
        # Voltage guard: do not pull the device buses outside vm_min..vm_max (a STATCOM
        # controller has the same limits); back off when they are already outside.
        v_lo, v_hi = self._device_vm_range(net)
        if v_lo is not None and v_lo < self.vm_min:
            move = max(move, 0.0) + max_step * min(1.0, (self.vm_min - v_lo) / 0.05)
        elif v_hi is not None and v_hi > self.vm_max:
            move = min(move, 0.0) - max_step * min(1.0, (v_hi - self.vm_max) / 0.05)
        elif v_lo is not None and move < 0 and v_lo <= self.vm_min + 0.005:
            move = 0.0
        elif v_hi is not None and move > 0 and v_hi >= self.vm_max - 0.005:
            move = 0.0
        move = max(-max_step, min(max_step, move))
        x_new = min(max(x + move, x_min), x_max)
        self._x_old, self._e_old = x, e
        self._apply(net, x_new)

    def _device_vm_range(self, net):
        buses = [net.sgen.at[i, 'bus'] for i in self.statcom_sgens] + \
                [net.shunt.at[r['shunt'], 'bus'] for r in self.reactors]
        vms = [self._vm_at(net, b) for b in buses]
        return (min(vms), max(vms)) if vms else (None, None)

    def __str__(self):
        return f'PlantSupervisoryControl [{self.name}] mode={self.mode} bus={self.bus}'
