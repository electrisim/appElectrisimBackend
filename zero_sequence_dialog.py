"""Use the transformer zero-sequence voltages stored on the network.

pandapower treats vk0_percent / vkr0_percent as missing when every transformer
in a vector group is 0, and then calculates with vk_percent / vkr_percent.
Electrisim stores the dialog value, including an explicit 0, so the
zero-sequence build has to keep that value.

A stored 0 is a zero-sequence short. The admittance 1/Z is kept finite with a
local impedance floor. That floor is not written back to net.trafo.
"""

import inspect

import numpy as np

_INSTALLED = False

_VK0_BLOCK = """        vk0_percent = (
            trafos["vk0_percent"].values.astype(float)
            if np.abs(trafos["vk0_percent"].values.astype(float)).max() > 1e-8
            else trafos["vk_percent"].values.astype(float)
        )"""

_VKR0_BLOCK = """        vkr0_percent = (
            trafos["vkr0_percent"].values.astype(float)
            if np.abs(trafos["vkr0_percent"].values.astype(float)).max() > 1e-8
            else trafos["vkr_percent"].values.astype(float)
        )"""

_Y0_LINE = "        y0_k = 1 / z0_k  # adding admittance for \"pi\" model"

_Y0_FLOOR = """        # Dialog vk0/vkr0 of 0 is a short. Floor only this local impedance.
        _z_abs = np.abs(z0_k)
        _short = _z_abs <= 1e-8
        if np.any(_short):
            z0_k = np.array(z0_k, dtype=complex, copy=True)
            z0_k[_short] = 1e-6
        y0_k = 1 / z0_k  # adding admittance for "pi" model"""


def install():
    """Replace pandapower's zero-sequence voltage fallback for this process."""
    global _INSTALLED
    if _INSTALLED:
        return

    import pandapower.pd2ppc_zero as zmod

    src = inspect.getsource(zmod._add_trafo_sc_impedance_zero)
    if _VK0_BLOCK not in src or _VKR0_BLOCK not in src or _Y0_LINE not in src:
        raise RuntimeError(
            "pandapower zero-sequence transformer code changed; "
            "dialog vk0_percent cannot be applied"
        )
    src = src.replace(
        _VK0_BLOCK,
        '        vk0_percent = trafos["vk0_percent"].values.astype(float)',
        1,
    )
    src = src.replace(
        _VKR0_BLOCK,
        '        vkr0_percent = trafos["vkr0_percent"].values.astype(float)',
        1,
    )
    src = src.replace(_Y0_LINE, _Y0_FLOOR, 1)
    exec(src, zmod.__dict__)
    raw = zmod._add_trafo_sc_impedance_zero

    def _add_trafo_sc_impedance_zero(net, ppc, trafo_df=None, k_st=None):
        # The T-equivalent is unused for the pi model. A dialog vk0 of 0
        # makes those unused divisions 0/0; they must not change the result.
        with np.errstate(divide="ignore", invalid="ignore"):
            return raw(net, ppc, trafo_df=trafo_df, k_st=k_st)

    _add_trafo_sc_impedance_zero._electrisim_dialog_vk0 = True
    zmod._add_trafo_sc_impedance_zero = _add_trafo_sc_impedance_zero
    _INSTALLED = True
