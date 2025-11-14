# Voltage Validation Fix - No More Default Values

## Problem Statement

Previously, the system would use default voltage values when voltage information was missing from bus elements. This masked configuration errors and could lead to incorrect simulation results.

**User Request**: "Don't use default voltage - if there is no voltage send than notify user by dialog at frontend"

**Specific Issue Reported**: User had a bus with `vn_kv: '0'` but received no error feedback at frontend. A voltage of 0 kV is invalid in electrical networks and would cause calculation errors.

## Solution Implemented

### Changes Made

#### 1. Backend Changes (`opendss_electrisim.py`)

**Error Handling Strategy**:
- ✅ All element creation functions now validate that voltage information exists
- ✅ **Bus creation validates voltage is positive and non-zero** (lines 175-202)
- ✅ Raise `ValueError` with clear, actionable error messages when voltage is missing, zero, or invalid
- ✅ Error messages include:
  - Which bus is missing voltage
  - Which element requires the voltage
  - List of available buses with voltage
  - Instructions on how to fix the issue
  - Common voltage values (110, 30, 20, 10 kV)

**Functions Updated**:
1. **`create_busbars()`** - Lines 175-202
   - **NEW: Validates bus voltage is not None, zero, or negative**
   - Checks if `vn_kv` attribute exists
   - Validates it can be converted to float
   - Validates it's greater than 0
2. `create_transformer_element()` - Lines 615-635
3. `create_static_generator_element()` - Lines 426-433
4. `create_shunt_reactor_element()` - Lines 717-724
5. `create_capacitor_element()` - Lines 799-806
6. `create_storage_element()` - Lines 852-859
7. `create_pvsystem_element()` - Lines 902-909
8. `create_external_grid_element()` - Lines 996-1003

**Error Propagation**:
- Added try-except block in `powerflow()` function (lines 1054-1069)
- Catches `ValueError` exceptions from element creation
- Returns JSON error response: `{"error": "error message"}`
- Frontend receives error and displays it to user

**Example Error Messages**:

**Case 1: Missing voltage (None)**
```
Missing voltage information for bus 'mxCell_147' connected to transformer 'mxCell_147'.

Please ensure:
1. The bus element has a 'vn_kv' (nominal voltage) attribute set, OR
2. The transformer has 'vn_hv_kv' parameter set

Available buses with voltage: ['mxCell_150', 'mxCell_126']
```

**Case 2: Zero or negative voltage**
```
Bus 'mxCell_160' (ID: mxCell#160) has an invalid voltage: 0.0 kV.

The nominal voltage must be a positive number greater than 0.
Common values: 110, 30, 20, 10, etc.

Please correct the 'vn_kv' attribute for this bus element.
```

**Case 3: Invalid voltage format**
```
Bus 'mxCell_160' (ID: mxCell#160) has an invalid 'vn_kv' value: 'abc'.

The voltage must be a positive number in kV.
Common values: 110, 30, 20, 10, etc.
```

#### 2. Frontend Changes (`loadflowOpenDss.js`)

**`getBusVoltage()` Function Updated** (lines 2495-2526):
- ✅ Removed default voltage return value of `'110'`
- ✅ Now returns `null` when voltage is not found
- ✅ Still tries to parse voltage from cell text (e.g., "110kV", "30kV")
- ✅ Backend validation will catch the `null` value

**Before**:
```javascript
// Default voltage
return '110';  // ❌ Hides missing voltage
```

**After**:
```javascript
// No default voltage - return null to indicate missing voltage
// This will cause backend validation to catch the error
return null;  // ✅ Forces proper validation
```

#### 3. Error Display in Frontend

**Existing Error Handling** (lines 1098-1099, 1230, 1250-1252):
- Frontend already has error handling via `handleNetworkErrors()`
- Checks for `error` property in JSON response
- Displays error using `alert()` dialog
- Error message from backend is shown directly to user

```javascript
function handleNetworkErrors(dataJson) {
    if (dataJson.error) {
        alert('OpenDSS calculation error: ' + dataJson.error);
        return true;
    }
    return false;
}
```

## Testing Instructions

### Test Case 1: Zero Voltage Value (Your Issue!)

1. **Setup**: Create a bus with `vn_kv: '0'` or `vn_kv: 0`
2. **Action**: Run OpenDSS load flow
3. **Expected Result**: 
   - Alert dialog appears with message:
     ```
     OpenDSS calculation error: Bus 'mxCell_160' (ID: mxCell#160) has an invalid voltage: 0.0 kV.
     
     The nominal voltage must be a positive number greater than 0.
     Common values: 110, 30, 20, 10, etc.
     
     Please correct the 'vn_kv' attribute for this bus element.
     ```
4. **Resolution**: 
   - Set `vn_kv` to a valid positive voltage value (e.g., 110, 30, 20, 10)

### Test Case 2: Missing Bus Voltage Attribute

1. **Setup**: Create a transformer connected to a bus without `vn_kv` attribute
2. **Action**: Run OpenDSS load flow
3. **Expected Result**: 
   - Alert dialog appears with message:
     ```
     Missing voltage information for bus 'mxCell_XXX' connected to transformer 'mxCell_YYY'.
     
     Please ensure:
     1. The bus element has a 'vn_kv' (nominal voltage) attribute set, OR
     2. The transformer has 'vn_hv_kv' parameter set
     
     Available buses with voltage: [...]
     ```
4. **Resolution**: 
   - Add `vn_kv` attribute to the bus element, OR
   - Add `vn_hv_kv` and `vn_lv_kv` parameters to the transformer

### Test Case 3: Invalid Voltage Format

1. **Setup**: Create a bus with `vn_kv: 'abc'` or other non-numeric value
2. **Action**: Run OpenDSS load flow
3. **Expected Result**: Alert shows invalid format error
4. **Resolution**: Set `vn_kv` to a valid numeric value

### Test Case 4: All Buses Have Proper Voltage

1. **Setup**: Ensure all buses have `vn_kv` attribute set to positive values
2. **Action**: Run OpenDSS load flow
3. **Expected Result**: Simulation runs successfully without errors

### Test Case 5: Other Elements Missing Voltage

Test with:
- Static Generator without bus voltage
- Load without bus voltage  
- Capacitor without bus voltage
- Shunt Reactor without bus voltage
- PV System without bus voltage
- Storage without bus voltage
- External Grid without bus voltage

All should display appropriate error messages.

## Benefits

### ✅ **Data Integrity**
- No silent failures
- No incorrect default values masking configuration errors
- Users are forced to provide proper voltage information

### ✅ **Better User Experience**
- Clear error messages
- Actionable instructions
- Shows which buses have voltage information
- Helps users quickly identify and fix issues

### ✅ **Debugging Support**
- Lists available buses with voltage
- Shows exactly which element and bus are problematic
- Provides multiple solutions (set bus voltage OR element voltage parameters)

## Migration Notes

### For Existing Models

If you have existing models that relied on default voltages:

1. **Review all bus elements** - Ensure each has `vn_kv` attribute set
2. **Check transformers** - Verify `vn_hv_kv` and `vn_lv_kv` are set
3. **Test simulation** - Run load flow to identify any missing voltages
4. **Fix errors** - Add voltage attributes as indicated by error messages

### Best Practices

1. **Always set bus voltage**: Add `vn_kv` attribute to every bus element
2. **Use proper voltage levels**: Match system voltage (e.g., 110, 30, 20, 10 kV)
3. **Check connections**: Ensure elements are connected to proper voltage buses
4. **Validate before simulation**: Review model completeness before running

## Files Modified

### Backend
- `opendss_electrisim.py`
  - **Lines 175-202: Bus voltage validation (NEW!)**
    - Validates voltage is not None
    - Validates voltage can be converted to float
    - Validates voltage is greater than 0
  - Lines 615-635: Transformer validation
  - Lines 426-433: Static generator validation
  - Lines 717-724: Shunt reactor validation
  - Lines 799-806: Capacitor validation
  - Lines 852-859: Storage validation
  - Lines 902-909: PV system validation
  - Lines 996-1003: External grid validation
  - Lines 1132-1153: Error propagation in powerflow() - now includes bus creation

### Frontend
- `loadflowOpenDss.js`
  - Lines 2495-2526: getBusVoltage() updated to return null instead of default

## Summary

This update enforces proper voltage specification throughout the electrical network model. The validation now catches:

1. **Missing voltages** (`None` or not set)
2. **Zero voltages** (`0` or `'0'`) - **This fixes your reported issue!**
3. **Negative voltages** (< 0)
4. **Invalid formats** (non-numeric strings)

Users will now receive immediate, actionable feedback when voltage information is missing or invalid, rather than having the system silently use incorrect default values or allow invalid values like zero. This improves simulation accuracy and helps users maintain properly configured models.

**No more silent failures. No more hidden defaults. No more zero voltages. Clear errors with clear solutions.**

