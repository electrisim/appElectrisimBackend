"""
ParkController reactive power control for Electrisim.

``ParkQControl`` is pandapower's ``BinarySearchControl`` with two changes:

1. Bounded steps. pandapower's secant step can move each machine by 2*|Q| + 50 Mvar
   per iteration, and divides by 1e-6 when the measurement barely moves. One such
   guess can push the load flow past the point where Newton-Raphson converges.
   Here each guess moves the park total by at most ``max_step_mvar`` (default: a
   quarter of the park's Q band) and keeps every machine inside min_q_mvar / max_q_mvar.
   When every machine already sits at the limit the error points to, the target is
   out of reach: the controller stops there (``at_q_limit``) instead of iterating on.

2. Optional measurement as a sum of branch-end flows (``q_terms``). A busbar picked
   for "Control Q at" means the Q the park feeds into that busbar, not ``res_bus.q_mvar``
   (which is only the Q of elements connected directly to the bus).

This file is also copied verbatim into exported pandapower scripts, so it must only
import numpy and pandapower.
"""
import numpy as np
from pandapower.auxiliary import write_to_net
from pandapower.control.controller.station_control import BinarySearchControl


def read_q_terms(net, terms):
    """Sum of sign * net[table].at[index, column] over (table, column, index, sign) terms."""
    total = 0.0
    for table, column, index, sign in terms:
        total += float(sign) * float(net[table].at[index, column])
    return total


class ParkQControl(BinarySearchControl):
    """BinarySearchControl with bounded, limit-respecting steps (see module docstring)."""

    def __init__(self, net, *args, q_terms=None, max_step_mvar=None, **kwargs):
        super().__init__(net, *args, **kwargs)
        self.q_terms = [tuple(t) for t in q_terms] if q_terms else None
        self.max_step_mvar = max_step_mvar
        self.at_q_limit = False
        self._slope_sign = None

    def initialize_control(self, net):
        super().initialize_control(net)
        self.output_values = np.asarray(self.output_values, dtype=float)
        self.output_values_old = None
        self.diff = None
        self.diff_old = None
        self.at_q_limit = False

    def is_converged(self, net):
        forced = self.overwrite_covergence
        converged = super().is_converged(net)
        if not self.in_service:
            return converged
        if self.q_terms is not None and not (self.voltage_ctrl and self.bus_idx is not None):
            self.diff = self.set_point - read_q_terms(net, self.q_terms)
            self.converged = bool(abs(self.diff) < self.tol)
            converged = False if forced else self.converged
        if not converged and self.at_q_limit:
            # Every machine is at the limit the error points to: the target cannot be met.
            self.converged = True
            return True
        return converged

    # --- step -------------------------------------------------------------------------

    def _q_limits(self, net):
        n = len(self.output_element_index)
        q_min = np.full(n, -np.inf)
        q_max = np.full(n, np.inf)
        tab = net[self.output_element]
        for k, idx in enumerate(self.output_element_index):
            for col, arr in (('min_q_mvar', q_min), ('max_q_mvar', q_max)):
                if col in tab.columns:
                    try:
                        v = float(tab.at[idx, col])
                    except (TypeError, ValueError):
                        continue
                    if v == v:
                        arr[k] = v
        # A swapped pair would make clamping impossible; keep the wider reading.
        swap = q_min > q_max
        q_min[swap], q_max[swap] = q_max[swap], q_min[swap]
        return q_min, q_max

    def _max_step(self, net, q_min, q_max):
        if self.max_step_mvar is not None and self.max_step_mvar > 0:
            return float(self.max_step_mvar)
        band = q_max - q_min
        finite = np.isfinite(band)
        total = float(np.sum(band[finite]))
        if not np.all(finite):
            tab = net[self.output_element]
            for k, idx in enumerate(self.output_element_index):
                if finite[k]:
                    continue
                sn = 0.0
                if 'sn_mva' in tab.columns:
                    try:
                        sn = float(tab.at[idx, 'sn_mva'])
                    except (TypeError, ValueError):
                        sn = 0.0
                total += 2.0 * sn if sn == sn and sn > 0 else 10.0
        return max(0.25 * total, 1.0)

    def _distribute(self, total, q_min, q_max):
        """Split ``total`` by the distribution weights; clamp to limits and re-share the rest."""
        w = np.asarray(self.output_values_distribution, dtype=float)
        n = len(w)
        out = np.zeros(n)
        free = np.ones(n, dtype=bool)
        remaining = float(total)
        for _ in range(n + 1):
            wf = w[free]
            if not np.any(free) or wf.sum() <= 0:
                break
            share = np.zeros(n)
            share[free] = remaining * w[free] / wf.sum()
            lo = free & (share < q_min)
            hi = free & (share > q_max)
            if not np.any(lo | hi):
                out[free] = share[free]
                return out
            out[lo] = q_min[lo]
            out[hi] = q_max[hi]
            remaining -= float(np.sum(out[lo | hi]))
            free &= ~(lo | hi)
        return np.clip(out, q_min, q_max)

    def _binarysearchcontrol_step(self, net):
        if not self.in_service:
            return
        q_min, q_max = self._q_limits(net)
        q_now = np.asarray(self.output_values, dtype=float)
        total = float(np.sum(q_now))
        max_step = self._max_step(net, q_min, q_max)
        # Direction that raises the measurement, before any slope is known.
        resp = 1.0 if (not self.gen_Q_response or self.gen_Q_response[0] >= 0) else -1.0
        guess_sign = self._slope_sign if self._slope_sign is not None else resp

        if self.output_values_old is None or self.diff_old is None:
            # Small first move to measure how the measurement responds.
            move = 1e-3 * max(len(q_now), 1) * (guess_sign * np.sign(self.diff) or 1.0)
        else:
            d_q = total - float(np.sum(self.output_values_old))
            d_diff = self.diff - self.diff_old
            if abs(d_q) > 1e-9 and abs(d_diff) > 1e-9:
                slope = -d_diff / d_q  # change of the measurement per Mvar of park Q
                self._slope_sign = 1.0 if slope > 0 else -1.0
                move = self.diff / slope
            else:
                # No usable slope: take a bounded step in the expected direction.
                move = guess_sign * np.sign(self.diff) * max_step
        move = float(np.clip(move, -max_step, max_step))

        new_values = self._distribute(total + move, q_min, q_max)
        moved = float(np.max(np.abs(new_values - q_now))) if len(q_now) else 0.0
        if moved < 1e-9 and self.output_values_old is None and move != 0.0:
            # The probe hit a limit: probe the other way instead.
            new_values = self._distribute(total - move, q_min, q_max)
            moved = float(np.max(np.abs(new_values - q_now))) if len(q_now) else 0.0
        self.at_q_limit = moved < 1e-9 and self.output_values_old is not None

        self.output_values_old, self.output_values = q_now, new_values
        write_to_net(net, self.output_element, self.output_element_index, self.output_variable,
                     self.output_values, self.write_flag)
