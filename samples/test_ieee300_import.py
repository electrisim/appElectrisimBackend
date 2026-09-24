#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Verify ieee300 tutorial: load flow + import JSON geo for all buses."""
from __future__ import annotations

import json
import os
import sys

import pandapower as pp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TUTORIAL = os.path.join(
    os.path.dirname(ROOT),
    "appElectrisim",
    "appElectrisim",
    "src",
    "main",
    "webapp",
    "templates",
    "tutorials",
    "ieee300.py",
)
if not os.path.isfile(TUTORIAL):
    TUTORIAL = os.path.join(os.path.dirname(__file__), "ieee300.py")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import pandapower_net_to_json


def main():
    ns = {}
    exec(open(TUTORIAL, encoding="utf-8").read(), ns)
    net = ns["net"]
    pp.runpp(net)
    assert net.converged, "case300 load flow did not converge"

    raw = pandapower_net_to_json(net)
    data = json.loads(raw)
    buses = json.loads(data["_object"]["bus"]["_object"])["data"]
    assert len(buses) == len(net.bus), "bus row count mismatch"
    for row in buses:
        assert len(row) >= 6, f"expected geo columns in bus row: {row[:4]}"
        gx, gy = row[4], row[5]
        assert gx is not None and gy is not None, f"missing geo: {row[0]}"
        assert float(gx) == float(gx) and float(gy) == float(gy), f"bad geo: {row[0]}"

    print(f"test_ieee300_import: OK ({len(buses)} buses, load flow converged)")


if __name__ == "__main__":
    main()
