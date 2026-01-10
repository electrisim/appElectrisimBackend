# Instructions to Add BESS Sizing Function

## Problem
The backend is missing the `bess_sizing` function in `pandapower_electrisim.py`.

## Solution
Add the following code to the **END** of `pandapower_electrisim.py` (after line 4236).

## Steps

1. Open `appElectrisimBackend/pandapower_electrisim.py`
2. Scroll to the very end of the file (line 4236)
3. Add the code from `pandapower_electrisim_BESS_ADDITION.py` (or copy from below)

## Code to Add

Copy the entire contents of `pandapower_electrisim_BESS_ADDITION.py` and paste it at the end of `pandapower_electrisim.py`.

**OR** manually add these two items:

1. **BESSControlForTargetBus class** - A controller class that iteratively adjusts BESS power
2. **bess_sizing function** - The main function that performs the BESS sizing calculation

The code is already prepared in the file `pandapower_electrisim_BESS_ADDITION.py` in the same directory.

## Verification

After adding the code, the backend should be able to:
- Import `bess_sizing` from `pandapower_electrisim`
- Process BESS sizing requests from the frontend
- Return calculated BESS power requirements

## Testing

Once added, restart your Flask backend and try the BESS sizing calculation again from the frontend.
