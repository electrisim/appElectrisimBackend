#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Ride-through envelope check (same logic as ANDES TDS post-processing)."""
from __future__ import annotations


def _vmin_curve(t_val: float, ride_pts):
    if not ride_pts:
        return 0.0
    if t_val <= ride_pts[0][0]:
        return ride_pts[0][1]
    for i in range(len(ride_pts) - 1):
        t0, v0 = ride_pts[i]
        t1, v1 = ride_pts[i + 1]
        if t0 <= t_val <= t1:
            if t1 <= t0:
                return v0
            return v0 + (v1 - v0) * (t_val - t0) / (t1 - t0)
    return ride_pts[-1][1]


def _check_ride_through(time_s, voltage_pu, ride_pts):
    for ti, vi in zip(time_s, voltage_pu):
        if float(vi) < _vmin_curve(float(ti), ride_pts) - 1e-5:
            return False
    return True


def test_ride_through_pass():
    pts = [(0.0, 0.9), (10.0, 0.9)]
    t = [0.0, 0.5, 1.0]
    v = [0.95, 0.92, 0.91]
    assert _check_ride_through(t, v, pts) is True


def test_ride_through_fail():
    pts = [(0.0, 0.9), (10.0, 0.9)]
    t = [0.0, 0.5, 1.0]
    v = [0.95, 0.82, 0.91]
    assert _check_ride_through(t, v, pts) is False


if __name__ == "__main__":
    test_ride_through_pass()
    test_ride_through_fail()
    print("test_data_center_ride_through: OK")
