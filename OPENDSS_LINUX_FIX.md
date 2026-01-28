# OpenDSS Linux Compatibility Fix

## Problem
The backend was failing in production (Railway/Linux) with the error:
```
RuntimeError: No active exception to reraise
py-dss-interface uses only the official version of OpenDSS.
EPRI provides OpenDSS only for Windows machines.
```

This occurred because:
- **Development**: Windows environment (OpenDSS works natively)
- **Production**: Linux environment (Railway) - OpenDSS official version is Windows-only
- The `py-dss-interface` library requires the Windows-specific OpenDSS DLL

## Solution
Replaced `py-dss-interface` with `OpenDSSDirect.py`, a cross-platform alternative that works on both Windows and Linux.

## Changes Made

### 1. Updated `requirements.txt`
- **Removed**: `py-dss-interface==2.0.4`
- **Added**: `OpenDSSDirect.py==0.9.4`

### 2. Updated `opendss_electrisim.py`

#### Import Statement
```python
# Before:
import py_dss_interface

# After:
import opendssdirect as dss
```

#### DSS Initialization
```python
# Before:
dss = py_dss_interface.DSS()

# After:
# OpenDSSDirect.py is already imported as dss at the module level
# No initialization needed - use the module directly
```

#### API Method Updates
OpenDSSDirect.py uses a similar but slightly different API:

| py-dss-interface | OpenDSSDirect.py |
|-----------------|------------------|
| `dss.text(cmd)` | `dss.run_command(cmd)` |
| `dss.solution.converged` | `dss.Solution.Converged()` |
| `dss.circuit.buses_names` | `dss.Circuit.AllBusNames()` |
| `dss.circuit.set_active_bus()` | `dss.Circuit.SetActiveBus()` |
| `dss.circuit.set_active_element()` | `dss.Circuit.SetActiveElement()` |
| `dss.circuit.num_buses` | `dss.Circuit.NumBuses()` |
| `dss.bus.name` | `dss.Bus.Name()` |
| `dss.bus.voltages` | `dss.Bus.Voltages()` |
| `dss.bus.kv_base` | `dss.Bus.kVBase()` |
| `dss.bus.vmag_angle_pu` | `dss.Bus.puVmagAngle()` |
| `dss.cktelement.enabled` | `dss.CktElement.Enabled()` |
| `dss.cktelement.powers` | `dss.CktElement.Powers()` |
| `dss.cktelement.currents_mag_ang` | `dss.CktElement.CurrentsMagAng()` |
| `dss.cktelement.losses` | `dss.CktElement.Losses()` |
| `dss.cktelement.currents` | `dss.CktElement.Currents()` |
| `dss.cktelement.name` | `dss.CktElement.Name()` |
| `dss.cktelement.bus_names` | `dss.CktElement.BusNames()` |
| `dss.lines.name` | `dss.Lines.Name()` |
| `dss.generators.mode` | `dss.Generators.Model()` |
| `dss.generators.status` | `dss.Generators.Status()` |
| `dss.pvsystems.bus1` | `dss.PVsystems.Bus1()` |
| `dss.pvsystems.count` | `dss.PVsystems.Count()` |
| `dss.pvsystems.first()` | `dss.PVsystems.First()` |
| `dss.pvsystems.next()` | `dss.PVsystems.Next()` |
| `dss.pvsystems.name` | `dss.PVsystems.Name()` |
| `dss.transformers.kva` | `dss.Transformers.kVA()` |
| `dss.transformers.wdg` | `dss.Transformers.Wdg()` |
| `dss.transformers.kv` | `dss.Transformers.kV()` |
| `dss.transformers.phases` | `dss.Transformers.Phases()` |
| `dss.capacitors.count` | `dss.Capacitors.Count()` |
| `dss.capacitors.first()` | `dss.Capacitors.First()` |
| `dss.capacitors.next()` | `dss.Capacitors.Next()` |
| `dss.capacitors.name` | `dss.Capacitors.Name()` |
| `dss.storage.count` | `dss.Storages.Count()` |
| `dss.storage.first()` | `dss.Storages.First()` |
| `dss.storage.next()` | `dss.Storages.Next()` |
| `dss.storage.name` | `dss.Storages.Name()` |
| `dss.vsources.count` | `dss.Vsources.Count()` |
| `dss.vsources.first()` | `dss.Vsources.First()` |
| `dss.vsources.next()` | `dss.Vsources.Next()` |
| `dss.vsources.name` | `dss.Vsources.Name()` |

## Deployment Steps

1. **Commit the changes**:
   ```bash
   git add requirements.txt opendss_electrisim.py
   git commit -m "Fix: Replace py-dss-interface with OpenDSSDirect.py for Linux compatibility"
   ```

2. **Push to production branch**:
   ```bash
   git push origin main
   ```

3. **Railway will automatically**:
   - Detect the changes
   - Rebuild the application with the new requirements
   - Deploy the updated version

## Testing

### In Development (Windows)
The application should continue to work exactly as before since OpenDSSDirect.py is cross-platform.

### In Production (Linux/Railway)
The OpenDSS initialization error should be resolved, and power flow simulations should work correctly.

## Additional Notes

- OpenDSSDirect.py is the official Python interface for OpenDSS and is maintained by NREL
- It provides binaries for Windows, Linux, and macOS
- The API is very similar to py-dss-interface, with the main difference being capitalized method names
- All functionality remains the same - only the underlying library changed

## Rollback Plan
If issues occur, you can revert by:
1. Changing `requirements.txt` back to `py-dss-interface==2.0.4`
2. Reverting the `opendss_electrisim.py` changes
3. Note: This will only work in Windows environments

## References
- OpenDSSDirect.py: https://github.com/dss-extensions/OpenDSSDirect.py
- py-dss-interface: https://github.com/PauloRadatz/py_dss_interface
