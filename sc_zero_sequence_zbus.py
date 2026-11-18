"""Short-circuit Zbus for networks with parts that have no zero-sequence earth (IEC 60909).

pandapower 3.3 models an open zero-sequence path (a delta winding, a Yd / Dy / Dd / Yy
transformer without an earthed neutral) as a branch of 1e20 pu and inverts the whole bus
admittance matrix. A part of the network behind such a path that has no earth of its own and
no cable capacitance (a delta winding feeding cables with c0 = 0) is then singular, and the
inverse of the nearly singular matrix spoils the zero-sequence impedance of the earthed buses
too. In a 110/20/10 kV YNdyn transformer test the 10 kV bus came out at Z0 = 0.00029 instead
of 0.00111 pu, so its single-phase Ik" was about 20% too high, and the unearthed buses showed
a negative Rk0 of about -1e45 ohm.

electrisim_calc_zbus takes the place of pandapower's _calc_zbus inside calc_sc. It cuts the
1e20 pu paths, inverts each remaining part on its own, and gives a part without an earth the
impedance of an open path (1e20 pu, pandapower's own value) for every entry: no zero-sequence
current flows into that part, an earth fault inside it has no zero-sequence current, and
pandapower reports its Rk0 / Xk0 as infinite. When every part is earthed (any cable capacitance
or earthed winding is enough) pandapower's own inverse is used, so those results do not change.

Electrisim installs this for the whole process; the exported Python script installs the same
functions, so both give the same numbers.
"""

from pandapower.shortcircuit.impedance import _calc_zbus as pandapower_calc_zbus


def electrisim_zbus(ybus):
    """Zbus with every part that has no earth held open, or None when pandapower's inverse is right.

    ybus is a sparse bus admittance matrix in per unit. Couplings below 1e-10 pu are pandapower's
    open paths (1e20 pu branches); without them the network falls apart into parts. A part whose
    admittance block is singular has no earth: all its entries become 1e20 (1 + 1j) pu, so a fault
    inside it sees an open zero-sequence circuit and its voltages move together (no current in
    its branches). The entries between different parts are 0.
    """
    import numpy as np
    from scipy.sparse import coo_matrix, csgraph
    from scipy.sparse.linalg import splu

    open_path = 1e20 * (1.0 + 1.0j)
    y = ybus.tocoo()
    keep = (y.row == y.col) | (np.abs(y.data) > 1e-10)
    rows, cols = y.row[keep], y.col[keep]
    pattern = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=ybus.shape)
    n_parts, part = csgraph.connected_components(pattern, directed=False)
    if n_parts == 1 and keep.all():
        return None
    cut = coo_matrix((y.data[keep], (rows, cols)), shape=ybus.shape).tocsr()
    parts = []
    for p in range(n_parts):
        members = np.flatnonzero(part == p)
        block = cut[members][:, members].tocsc()
        try:
            lu = splu(block)
            probe = lu.solve(np.ones(len(members), dtype=complex))
            # |Z| * |Y| far above any real network (1e10 for a very weak capacitive earth)
            # but below the 1e15 of a singular block in double precision.
            scale = max(float(np.abs(block.data).max()), 1.0)
            earthed = bool(np.all(np.isfinite(probe))) and float(np.abs(probe).max()) * scale < 1e12
        except RuntimeError:  # exactly singular
            lu, earthed = None, False
        parts.append((members, lu if earthed else None))
    if all(lu is not None for _members, lu in parts):
        return None
    zbus = np.zeros(ybus.shape, dtype=complex)
    for members, lu in parts:
        index = np.ix_(members, members)
        zbus[index] = open_path if lu is None else lu.solve(np.eye(len(members), dtype=complex))
    return zbus


def electrisim_calc_zbus(net, ppci):
    """pandapower's _calc_zbus, except for a network with parts that have no zero-sequence earth."""
    zbus = electrisim_zbus(ppci["internal"]["Ybus"])
    if zbus is None:
        return pandapower_calc_zbus(net, ppci)
    ppci["internal"]["Zbus"] = zbus


def install():
    """Use electrisim_calc_zbus in pandapower's calc_sc for this process."""
    import importlib

    calc_sc_module = importlib.import_module("pandapower.shortcircuit.calc_sc")
    calc_sc_module._calc_zbus = electrisim_calc_zbus


def export_lines():
    """Python statements that install the same Zbus in a standalone script."""
    import inspect

    lines = [
        "# --- Electrisim zero-sequence Zbus for parts without an earth ---",
        "# pandapower inverts the whole zero-sequence network. A part behind a delta winding with no",
        "# earth and no cable capacitance is singular there and spoils Z0 at the other buses, so",
        "# Electrisim inverts each earthed part on its own and holds the unearthed parts open.",
        "# Networks where every part is earthed keep pandapower's own inverse.",
        "import importlib",
        "from pandapower.shortcircuit.impedance import _calc_zbus as pandapower_calc_zbus",
        "",
    ]
    for func in (electrisim_zbus, electrisim_calc_zbus):
        lines.extend(inspect.getsource(func).rstrip("\n").split("\n"))
        lines.append("")
    lines.append("importlib.import_module('pandapower.shortcircuit.calc_sc')._calc_zbus = electrisim_calc_zbus")
    lines.append("")
    return lines
