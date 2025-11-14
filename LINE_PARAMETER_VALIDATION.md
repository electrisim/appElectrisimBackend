# Line Parameter Validation for OpenDSS Calculations

## Overview
This document describes the validation implemented for Line element parameters in OpenDSS calculations to ensure data quality and prevent calculation errors.

## Validation Rules

For OpenDSS calculations, the following Line element parameters must be **greater than 0**:
- `r0_ohm_per_km` (Zero-sequence resistance)
- `x0_ohm_per_km` (Zero-sequence reactance)

## Implementation Details

### Backend Validation (opendss_electrisim.py)

**Location:** `create_line_element()` function, lines 369-390

The validation checks are performed before creating the Line element in OpenDSS:

```python
# Validate r0_ohm_per_km and x0_ohm_per_km for OpenDSS calculations
# These parameters must be greater than 0
if r0_ohm_per_km is not None:
    try:
        r0_value = float(r0_ohm_per_km)
        if r0_value <= 0:
            raise ValueError(f"Line '{element_name}': Parameter r0_ohm_per_km must be greater than 0 (current value: {r0_value}). Please update the line parameters.")
    except (TypeError, ValueError) as e:
        if "must be greater than 0" in str(e):
            raise  # Re-raise validation error
        raise ValueError(f"Line '{element_name}': Invalid value for r0_ohm_per_km: {r0_ohm_per_km}")

if x0_ohm_per_km is not None:
    try:
        x0_value = float(x0_ohm_per_km)
        if x0_value <= 0:
            raise ValueError(f"Line '{element_name}': Parameter x0_ohm_per_km must be greater than 0 (current value: {x0_value}). Please update the line parameters.")
    except (TypeError, ValueError) as e:
        if "must be greater than 0" in str(e):
            raise  # Re-raise validation error
        raise ValueError(f"Line '{element_name}': Invalid value for x0_ohm_per_km: {x0_ohm_per_km}")
```

### Error Response Format

When validation fails, the backend returns a JSON error response:

```json
{
    "error": "Line '{line_name}': Parameter {parameter_name} must be greater than 0 (current value: {value}). Please update the line parameters."
}
```

### Frontend Error Handling (loadFlow.js)

**Location:** `handleNetworkErrors()` function, lines 961-966

The frontend now includes a handler for simple error responses:

```javascript
// Handle simple error response (validation errors, etc.)
if (dataJson.error && !dataJson.diagnostic) {
    console.error('Power flow calculation failed:', dataJson.error);
    alert(`Power flow calculation failed:\n\n${dataJson.error}`);
    return true;
}
```

## User Experience

When a user attempts to run an OpenDSS calculation with invalid Line parameters:

1. **Backend Validation:** The backend detects the invalid parameter value during element creation
2. **Error Response:** A clear error message is sent to the frontend identifying:
   - The specific Line element with the issue
   - Which parameter is invalid (r0_ohm_per_km or x0_ohm_per_km)
   - The current value of the parameter
   - What needs to be done (update the line parameters)
3. **User Notification:** An alert dialog is displayed with the error message
4. **No Calculation:** The power flow calculation does not proceed, preventing incorrect results

## Example Error Messages

- `Line 'Line_1': Parameter r0_ohm_per_km must be greater than 0 (current value: 0). Please update the line parameters.`
- `Line 'Cable_ABC': Parameter x0_ohm_per_km must be greater than 0 (current value: 0). Please update the line parameters.`

## Benefits

1. **Data Quality:** Ensures that Line elements have valid zero-sequence parameters
2. **Error Prevention:** Catches invalid data before it reaches the OpenDSS solver
3. **Clear Feedback:** Users receive specific information about which Line needs correction
4. **Better UX:** Users can quickly identify and fix the problem without trial and error

## Technical Notes

- Validation only applies when parameters are explicitly provided (not None)
- Both zero (0) and negative values are rejected (must be > 0)
- Type checking ensures values can be converted to float
- The ValueError exception is caught by the powerflow function's try-except block (lines 1170-1181)
- Error messages are logged to the backend console for debugging
- ValueError exceptions are re-raised in `create_other_elements()` (line 325-328) to ensure they propagate to the frontend

## Testing

To test the validation:

1. Create a Line element in the frontend
2. Set r0_ohm_per_km or x0_ohm_per_km to 0
3. Run an OpenDSS power flow calculation
4. Verify that an alert dialog appears with the validation error message
5. Update the parameter to a value > 0
6. Verify that the calculation proceeds successfully

## Related Files

- Backend: `c:/Users/DELL/.vscode/appElectrisimBackend/appElectrisimBackend/opendss_electrisim.py`
- Frontend: `c:/Users/DELL/.vscode/appElectrisim/appElectrisim/src/main/webapp/js/electrisim/loadFlow.js`
- API Router: `c:/Users/DELL/.vscode/appElectrisimBackend/appElectrisimBackend/app.py`

