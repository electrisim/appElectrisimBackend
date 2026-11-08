"""DG Interconnection finds the DER the user picked.

The app's DER picker sends the cell id ("mxCell#277") while network elements are named
"mxCell_277", so every screening failed with "DER element not found". Wind Turbines are
picked as generator-type DERs.

Run with ``python samples/test_dg_der_lookup.py``.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opendss_electrisim import _dg_find_der_element, _dg_label_metrics  # noqa: E402


def main() -> None:
    data = {
        "1": {"typ": "Bus0", "name": "mxCell_200", "id": "b"},
        "2": {"typ": "Wind Turbine0", "name": "mxCell_277", "id": "EA3TQ-2"},
        "3": {"typ": "PVSystem0", "name": "mxCell_300", "id": "pv-1"},
    }
    assert _dg_find_der_element(data, "mxCell#277", "Generator")["id"] == "EA3TQ-2"
    assert _dg_find_der_element(data, "mxCell_277", "Generator")["id"] == "EA3TQ-2"
    assert _dg_find_der_element(data, "pv-1", "PVSystem")["name"] == "mxCell_300"
    assert _dg_find_der_element(data, "mxCell#277", "PVSystem") is None
    assert _dg_find_der_element(data, "mxCell#999", "Generator") is None
    print("DG DER lookup OK")

    # Results name buses / lines as the user does; a shared name gets the element id.
    names = {
        "1": {"typ": "Bus0", "name": "mxCell_200", "userFriendlyName": "POC  110 kV"},
        "2": {"typ": "Bus1", "name": "mxCell_263", "userFriendlyName": "Bus"},
        "3": {"typ": "Bus2", "name": "mxCell_264", "userFriendlyName": "Bus"},
        "4": {"typ": "Line0", "name": "mxCell_210", "userFriendlyName": "Cable A"},
    }
    buses = [{"name": "mxcell_200", "vm_pu": 1.0}, {"name": "mxcell_263", "vm_pu": 1.1}, {"name": "other", "vm_pu": 1}]
    lines = [{"name": "mxCell_210", "loading_percent": 50.0}]
    _dg_label_metrics(names, buses, lines)
    assert [b["name"] for b in buses] == ["POC 110 kV", "Bus (mxCell_263)", "other"], buses
    assert lines[0]["name"] == "Cable A", lines
    print("DG result labels OK")


if __name__ == "__main__":
    main()
