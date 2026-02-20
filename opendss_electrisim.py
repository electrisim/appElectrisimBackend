import opendssdirect as dss
from typing import List
import math
import json

# Output classes for OpenDSS results (similar to pandapower_electrisim.py structure)
class BusbarOut(object):
    def __init__(self, name: str, id: str, vm_pu: float, va_degree: float,
                 p_mw: float = None, q_mvar: float = None, pf: float = None, q_p: float = None):
        self.name = name
        self.id = id
        self.vm_pu = vm_pu
        self.va_degree = va_degree
        self.p_mw = p_mw
        self.q_mvar = q_mvar
        self.pf = pf
        self.q_p = q_p
                        
class BusbarsOut(object):
    def __init__(self, busbars: List[BusbarOut]):
        self.busbars = busbars

class BusbarScOut(object):
    """Short circuit bus result - compatible with Pandapower res_bus_sc format for frontend."""
    def __init__(self, name: str, id: str, ikss_ka: float, ip_ka: float, ith_ka: float, rk_ohm: float, xk_ohm: float):
        self.name = name
        self.id = id
        self.ikss_ka = ikss_ka
        self.ip_ka = ip_ka
        self.ith_ka = ith_ka
        self.rk_ohm = rk_ohm
        self.xk_ohm = xk_ohm

class LineOut(object):
    def __init__(self, name: str, id: str, p_from_mw: float, q_from_mvar: float, p_to_mw: float, q_to_mvar: float, i_from_ka: float, i_to_ka: float, loading_percent: float):          
        self.name = name
        self.id = id
        self.p_from_mw = p_from_mw
        self.q_from_mvar = q_from_mvar 
        self.p_to_mw = p_to_mw 
        self.q_to_mvar = q_to_mvar            
        self.i_from_ka = i_from_ka 
        self.i_to_ka = i_to_ka               
        self.loading_percent = loading_percent 
                       
class LinesOut(object):
    def __init__(self, lines: List[LineOut]):
        self.lines = lines

class ExternalGridOut(object):
    def __init__(self, name: str, id: str, p_mw: float, q_mvar: float, pf: float, q_p: float):        
        self.name = name
        self.id = id
        self.p_mw = p_mw
        self.q_mvar = q_mvar
        self.pf = pf
        self.q_p = q_p
                       
class ExternalGridsOut(object):
    def __init__(self, externalgrids: List[ExternalGridOut]):
        self.externalgrids = externalgrids

class GeneratorOut(object):
    def __init__(self, name: str, id: str, p_mw: float, q_mvar: float, va_degree: float, vm_pu: float):          
        self.name = name
        self.id = id
        self.p_mw = p_mw 
        self.q_mvar = q_mvar
        self.va_degree = va_degree
        self.vm_pu = vm_pu
                       
class GeneratorsOut(object):
    def __init__(self, generators: List[GeneratorOut]):
        self.generators = generators             

class StaticGeneratorOut(object):
    def __init__(self, name: str, id: str, p_mw: float, q_mvar: float):          
        self.name = name
        self.id = id
        self.p_mw = p_mw 
        self.q_mvar = q_mvar
                       
class StaticGeneratorsOut(object):
    def __init__(self, staticgenerators: List[StaticGeneratorOut]):
        self.staticgenerators = staticgenerators

class LoadOut(object):
    def __init__(self, name: str, id: str, p_mw: float, q_mvar: float):          
        self.name = name
        self.id = id
        self.p_mw = p_mw 
        self.q_mvar = q_mvar                       
                       
class LoadsOut(object):
    def __init__(self, loads: List[LoadOut]):
        self.loads = loads             

class TransformerOut(object):
    def __init__(self, name: str, id: str, i_hv_ka: float, i_lv_ka: float, loading_percent: float, 
                 p_hv_mw: float = 0.0, q_hv_mvar: float = 0.0, p_lv_mw: float = 0.0, q_lv_mvar: float = 0.0, 
                 pl_mw: float = 0.0, ql_mvar: float = 0.0):          
        self.name = name
        self.id = id           
        self.i_hv_ka = i_hv_ka 
        self.i_lv_ka = i_lv_ka
        self.loading_percent = loading_percent
        self.p_hv_mw = p_hv_mw
        self.q_hv_mvar = q_hv_mvar
        self.p_lv_mw = p_lv_mw
        self.q_lv_mvar = q_lv_mvar
        self.pl_mw = pl_mw
        self.ql_mvar = ql_mvar
                                                             
                       
class TransformersOut(object):
    def __init__(self, transformers: List[TransformerOut]):
        self.transformers = transformers             

class ShuntOut(object):
    def __init__(self, name: str, id: str, p_mw: float, q_mvar: float, vm_pu: float):          
        self.name = name
        self.id = id
        self.p_mw = p_mw 
        self.q_mvar = q_mvar  
        self.vm_pu = vm_pu                          
                       
class ShuntsOut(object):
    def __init__(self, shunts: List[ShuntOut]):
        self.shunts = shunts              
                
class CapacitorOut(object):
    def __init__(self, name: str, id: str, p_mw: float, q_mvar: float, vm_pu: float):         
        self.name = name
        self.id = id
        self.p_mw = p_mw 
        self.q_mvar = q_mvar  
        self.vm_pu = vm_pu                          
                       
class CapacitorsOut(object):
    def __init__(self, capacitors: List[CapacitorOut]):
        self.capacitors = capacitors              

class StorageOut(object):
    def __init__(self, name: str, id: str, p_mw: float, q_mvar: float):          
        self.name = name
        self.id = id
        self.p_mw = p_mw 
        self.q_mvar = q_mvar                       
                       
class StoragesOut(object):
    def __init__(self, storages: List[StorageOut]):
        self.storages = storages

class PVSystemOut(object):
    def __init__(self, name: str, id: str, p_mw: float, q_mvar: float, vm_pu: float, va_degree: float, irradiance: float, temperature: float):
        self.name = name
        self.id = id
        self.p_mw = p_mw
        self.q_mvar = q_mvar
        self.vm_pu = vm_pu
        self.va_degree = va_degree
        self.irradiance = irradiance
        self.temperature = temperature

class PVSystemsOut(object):
    def __init__(self, pvsystems: List[PVSystemOut]):
        self.pvsystems = pvsystems              

# Helper functions for OpenDSS element creation
# Frontend sends simple mxCell_ names (mxCell_126, mxCell_129, etc.)
# Frontend now sends bus names in the correct format (mxCell_126)
# OpenDSS may convert bus names to 
def create_busbars(in_data, dss, export_commands=False, opendss_commands=None):
    """Create busbars in OpenDSS circuit - Let OpenDSS handle bus creation automatically  when elements are connected"""
    BusbarsDictVoltage = {}  
    BusbarsDictConnectionToName = {}
    if opendss_commands is None:
        opendss_commands = []  
   
    
        # Collect bus information from input data for reference
    bus_elements = {}
    for x in in_data:         
        if "Bus" in in_data[x]['typ']:
            # Frontend now sends bus names in the correct format (mxCell_126)
            bus_name = in_data[x]['name']  # This is already mxCell_126
            bus_id = in_data[x].get('id', bus_name)  # Get ID for error messages
            bus_voltage_raw = in_data[x].get('vn_kv', None)
            
            # Validate bus voltage
            if bus_voltage_raw is None:
                error_msg = (
                    f"Bus '{bus_name}' (ID: {bus_id}) is missing the 'vn_kv' (nominal voltage) attribute.\n\n"
                    f"Please set the nominal voltage in kV for this bus element.\n"
                    f"Common values: 110, 30, 20, 10, etc."
                )
                raise ValueError(error_msg)
            
            # Convert to float and validate it's a positive number
            try:
                bus_voltage = float(bus_voltage_raw)
            except (ValueError, TypeError):
                error_msg = (
                    f"Bus '{bus_name}' (ID: {bus_id}) has an invalid 'vn_kv' value: '{bus_voltage_raw}'.\n\n"
                    f"The voltage must be a positive number in kV.\n"
                    f"Common values: 110, 30, 20, 10, etc."
                )
                raise ValueError(error_msg)
            
            # Check if voltage is zero or negative
            if bus_voltage <= 0:
                error_msg = (
                    f"Bus '{bus_name}' (ID: {bus_id}) has an invalid voltage: {bus_voltage} kV.\n\n"
                    f"The nominal voltage must be a positive number greater than 0.\n"
                    f"Common values: 110, 30, 20, 10, etc.\n\n"
                    f"Please correct the 'vn_kv' attribute for this bus element."
                )
                raise ValueError(error_msg)
            
            bus_elements[bus_name] = bus_name  # mxCell_126 -> mxCell_126
            BusbarsDictVoltage[bus_name] = bus_voltage
    
    # Since we want to use simple names everywhere, just store the bus names directly
    for bus_name in bus_elements.keys():
        # Store the mapping: bus_name (mxCell_126) -> bus_name (mxCell_126)
        BusbarsDictConnectionToName[bus_name] = bus_name  
    
    return BusbarsDictVoltage, BusbarsDictConnectionToName

def create_other_elements(in_data, dss, BusbarsDictVoltage, BusbarsDictConnectionToName, export_commands=False, opendss_commands=None, execute_dss_command=None):
    """Create other elements in OpenDSS circuit"""
    if opendss_commands is None:
        opendss_commands = []
    
    # If execute_dss_command is not provided, create a default one
    if execute_dss_command is None:
        def execute_dss_command(command):
            """Execute DSS command and optionally collect it for export"""
            print(f"[OpenDSS] {command}")  # Log all commands
            dss.Text.Command(command)  # Use Text.Command (run_command is deprecated)
            if export_commands:
                opendss_commands.append(command)
    
    # Initialize tracking dictionaries
    LinesDict = {}
    LinesDictId = {}
    LoadsDict = {}
    LoadsDictId = {}
    TransformersDict = {}
    TransformersDictId = {}
    ShuntsDict = {}
    ShuntsDictId = {}
    CapacitorsDict = {}
    CapacitorsDictId = {}
    GeneratorsDict = {}
    GeneratorsDictId = {}
    StoragesDict = {}
    StoragesDictId = {}
    PVSystemsDict = {}
    PVSystemsDictId = {}
    ExternalGridsDict = {}
    ExternalGridsDictId = {}
    
    # Track which elements have already been created to prevent duplicates
    created_elements = set()


    
    # First pass: create External Grid (Vsource) so the slack bus and base voltage are defined before other elements
    for x in in_data:
        try:
            element_data = in_data[x]
            element_type = element_data.get('typ', '')
            element_name = element_data.get('name', '')
            element_id = element_data.get('id', '')
            if "Bus" in element_type or element_type == "PowerFlowOpenDss Parameters":
                continue
            if not element_type.startswith("External Grid"):
                continue
            if 'bus' not in element_data or element_data['bus'] not in BusbarsDictConnectionToName:
                continue
            create_external_grid_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, created_elements, execute_dss_command)
            ExternalGridsDict[element_name] = element_name
            ExternalGridsDictId[element_name] = element_id
        except ValueError as ve:
            raise
        except Exception as e:
            continue

    # Extract the circuit source element name (first ext grid mapped to Vsource.source)
    circuit_source_element_name = None
    for item in created_elements:
        if isinstance(item, str) and item.startswith('circuit_source_element:'):
            circuit_source_element_name = item.split(':', 1)[1]
            break

    # Second pass: create Lines (establish bus connectivity at same voltage level)
    for x in in_data:
        try:
            element_data = in_data[x]
            element_type = element_data.get('typ', '')
            element_name = element_data.get('name', '')
            element_id = element_data.get('id', '')
            if "Line" in element_type:
                create_line_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LinesDict, LinesDictId, created_elements, execute_dss_command)
        except ValueError as ve:
            raise
        except Exception as e:
            continue

    # Third pass: create Transformers (establish voltage level transitions between buses)
    for x in in_data:
        try:
            element_data = in_data[x]
            element_type = element_data.get('typ', '')
            element_name = element_data.get('name', '')
            element_id = element_data.get('id', '')
            if element_type.startswith("Transformer"):
                create_transformer_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, TransformersDict, TransformersDictId, created_elements, execute_dss_command)
        except ValueError as ve:
            raise
        except Exception as e:
            continue

    # After lines and transformers: set voltage bases and run calcv so OpenDSS assigns correct base kV to each bus
    try:
        if BusbarsDictVoltage:
            vb_list = sorted(set(float(v) for v in BusbarsDictVoltage.values()), reverse=True)
            if vb_list:
                execute_dss_command('set voltagebases=[' + ','.join(str(v) for v in vb_list) + ']')
        execute_dss_command('calcv')
    except Exception as e:
        pass

    # Fourth pass: create Shunt elements (Reactors, Capacitors) - constant impedance elements
    for x in in_data:
        try:
            element_data = in_data[x]
            element_type = element_data.get('typ', '')
            element_name = element_data.get('name', '')
            element_id = element_data.get('id', '')
            if element_type.startswith("Shunt Reactor"):
                create_shunt_reactor_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, ShuntsDict, ShuntsDictId, created_elements, execute_dss_command)
            elif element_type.startswith("Capacitor"):
                create_capacitor_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, CapacitorsDict, CapacitorsDictId, created_elements, execute_dss_command)
        except ValueError as ve:
            raise
        except Exception as e:
            continue

    # Fifth pass: create power injection elements (Generators, Loads, Storage, PVSystems)
    for x in in_data:
        try:
            element_data = in_data[x]
            element_type = element_data.get('typ', '')
            element_name = element_data.get('name', '')
            element_id = element_data.get('id', '')
            if "Bus" in element_type or element_type == "PowerFlowOpenDss Parameters":
                continue
            if element_type.startswith("External Grid") or "Line" in element_type or element_type.startswith("Transformer") or element_type.startswith("Shunt Reactor") or element_type.startswith("Capacitor"):
                continue
            if element_type.startswith("Load"):
                create_load_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LoadsDict, LoadsDictId, created_elements, execute_dss_command)
            elif element_type.startswith("Motor"):
                # Motors are modeled as Loads in OpenDSS
                create_load_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LoadsDict, LoadsDictId, created_elements, execute_dss_command)
            elif element_type.startswith("Static Generator"):
                create_static_generator_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, GeneratorsDict, GeneratorsDictId, created_elements, execute_dss_command)
            elif element_type.startswith("Asymmetric Static Generator"):
                create_static_generator_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, GeneratorsDict, GeneratorsDictId, created_elements, execute_dss_command)
            elif element_type.startswith("Generator"):
                create_generator_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, GeneratorsDict, GeneratorsDictId, created_elements, execute_dss_command)
            elif element_type.startswith("Storage"):
                create_storage_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, StoragesDict, StoragesDictId, created_elements, execute_dss_command)
            elif element_type.startswith("PVSystem"):
                create_pvsystem_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, PVSystemsDict, PVSystemsDictId, created_elements, execute_dss_command)
        except ValueError as ve:
            raise
        except Exception as e:
            continue
    
   
    
    return (LinesDict, LinesDictId, LoadsDict, LoadsDictId, TransformersDict, TransformersDictId,
            ShuntsDict, ShuntsDictId, CapacitorsDict, CapacitorsDictId, GeneratorsDict, GeneratorsDictId,
            StoragesDict, StoragesDictId, PVSystemsDict, PVSystemsDictId, ExternalGridsDict, ExternalGridsDictId,
            circuit_source_element_name)

# Individual element creation functions
def create_line_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LinesDict, LinesDictId, created_elements, execute_dss_command=None):
    """Create a line element in OpenDSS"""
    
    # Check for duplicates - skip if already created
    if element_name in created_elements:
        return
    
    # Get bus connections
    bus_from_ref = element_data.get('busFrom')
    bus_to_ref = element_data.get('busTo')
    
    if bus_from_ref and bus_to_ref:
        
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_from_ref_backend = bus_from_ref
        bus_to_ref_backend = bus_to_ref
        
        # Get bus names from connection mapping
        if bus_from_ref_backend in BusbarsDictConnectionToName:
            bus_from_name = BusbarsDictConnectionToName[bus_from_ref_backend]
        else:
            bus_from_name = bus_from_ref_backend
            
        if bus_to_ref_backend in BusbarsDictConnectionToName:
            bus_to_name = BusbarsDictConnectionToName[bus_to_ref_backend]
        else:
            bus_to_name = bus_to_ref_backend        
        
        # Extract line parameters from input data (like the previous version)
        r_ohm_per_km = element_data.get('r_ohm_per_km')
        x_ohm_per_km = element_data.get('x_ohm_per_km')
        c_nf_per_km = element_data.get('c_nf_per_km')
        length_km = element_data.get('length_km')
        r0_ohm_per_km = element_data.get('r0_ohm_per_km')
        x0_ohm_per_km = element_data.get('x0_ohm_per_km')
        c0_nf_per_km = element_data.get('c0_nf_per_km')
        
        # Validate r0_ohm_per_km, x0_ohm_per_km and c0_nf_per_km for OpenDSS - must be greater than 0
        if r0_ohm_per_km is not None:
            try:
                r0_value = float(r0_ohm_per_km)
                if r0_value <= 0:
                    raise ValueError(f"Line '{element_name}': Parameter r0_ohm_per_km must be greater than 0 (current value: {r0_value}). Please update the line parameters.")
            except (TypeError, ValueError) as e:
                if "must be greater than 0" in str(e):
                    raise
                raise ValueError(f"Line '{element_name}': Invalid value for r0_ohm_per_km: {r0_ohm_per_km}")
        
        if x0_ohm_per_km is not None:
            try:
                x0_value = float(x0_ohm_per_km)
                if x0_value <= 0:
                    raise ValueError(f"Line '{element_name}': Parameter x0_ohm_per_km must be greater than 0 (current value: {x0_value}). Please update the line parameters.")
            except (TypeError, ValueError) as e:
                if "must be greater than 0" in str(e):
                    raise
                raise ValueError(f"Line '{element_name}': Invalid value for x0_ohm_per_km: {x0_ohm_per_km}")
        
        if c0_nf_per_km is not None:
            try:
                c0_value = float(c0_nf_per_km)
                if c0_value <= 0:
                    raise ValueError(f"Line '{element_name}': Parameter c0_nf_per_km must be greater than 0 (current value: {c0_value}). Please update the line parameters.")
            except (TypeError, ValueError) as e:
                if "must be greater than 0" in str(e):
                    raise
                raise ValueError(f"Line '{element_name}': Invalid value for c0_nf_per_km: {c0_nf_per_km}")
        
        try:
            # Create line using OpenDSS command with parameters from frontend
            line_cmd = f'New Line.{element_name} phases=3 Bus1={bus_from_name} Bus2={bus_to_name} R1={r_ohm_per_km} X1={x_ohm_per_km} Length={length_km} units=km'
            
            # Add optional parameters only if they exist
            if r0_ohm_per_km is not None:
                line_cmd += f' R0={r0_ohm_per_km}'
            if x0_ohm_per_km is not None:
                line_cmd += f' X0={x0_ohm_per_km}'
            if c_nf_per_km is not None:
                line_cmd += f' C1={c_nf_per_km}'
            if c0_nf_per_km is not None:
                line_cmd += f' C0={c0_nf_per_km}'
                
            execute_dss_command(line_cmd)
            
            # Handle in_service status AFTER creating the element
            # This prevents topology issues during network creation
            in_service = element_data.get('in_service', True)
            
            # Convert to boolean for comparison
            is_in_service = True
            if isinstance(in_service, bool):
                is_in_service = in_service
            elif isinstance(in_service, str):
                is_in_service = in_service.lower() not in ['false', 'no', '0']
            elif in_service in [0, None]:
                is_in_service = False
            
            if not is_in_service:
                # Disable the line after it's been created
                cmd = f'Line.{element_name}.enabled=no'
                print(f"[OpenDSS] {cmd}")
                dss.Text.Command(cmd)
            
            # print(f"Command: {line_cmd}")  # Reduced logging
            
            actual_name = dss.Lines.Name()
            LinesDict[element_name] = actual_name
            LinesDictId[element_name] = element_id
            created_elements.add(element_name)
            
        except Exception as e:
            pass
    else:
        pass
def create_load_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LoadsDict, LoadsDictId, created_elements, execute_dss_command=None):
    """Create a load element in OpenDSS (handles both Load and Motor types)"""
    
    # Check for duplicates - skip if already created
    if element_name in created_elements:
        return
    
    bus_connection = element_data.get('bus')
    if bus_connection:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_connection_backend = bus_connection
        if bus_connection_backend in BusbarsDictConnectionToName:
            bus_name = BusbarsDictConnectionToName[bus_connection_backend]
        # Get voltage from the bus data
        bus_voltage = BusbarsDictVoltage.get(bus_name)
        
        if bus_voltage is None:
            return                 
        
        # Detect if this is a Motor or regular Load
        element_type = element_data.get('typ', '')
        is_motor = element_type.startswith('Motor')
        
        if is_motor:
            import math
            # Motor: calculate P and Q to match pandapower's motor model
            # P_electric = pn_mech_mw * loading_percent / efficiency_percent * scaling
            pn_mw = float(element_data.get('pn_mech_mw', 0) or element_data.get('pn_mw', 0))
            efficiency_raw = float(element_data.get('efficiency_percent', 0.9))
            loading_raw = float(element_data.get('loading_percent', efficiency_raw))
            scaling = float(element_data.get('scaling', 1.0))
            
            # Detect if values are fractions (<=1) or actual percentages (>1)
            efficiency = efficiency_raw if efficiency_raw > 1 else efficiency_raw * 100
            loading = loading_raw if loading_raw > 1 else loading_raw * 100
            
            # P_elec = P_mech * (loading% / 100) / (efficiency% / 100) * scaling
            if efficiency > 0:
                p_mw = pn_mw * (loading / 100.0) / (efficiency / 100.0) * scaling
            else:
                p_mw = pn_mw * scaling
            
            # Use cos_phi (same as pandapower), fall back to cos_phi_n
            cos_phi = float(element_data.get('cos_phi', 0) or element_data.get('cos_phi_n', 0.85))
            
            # Q = P * tan(acos(cos_phi))
            if cos_phi > 0 and cos_phi < 1.0:
                q_mvar = p_mw * math.tan(math.acos(cos_phi))
            else:
                q_mvar = 0
        else:
            # Regular Load: get P and Q directly
            p_mw_raw = element_data.get('p_mw')
            q_mvar_raw = element_data.get('q_mvar')
            
            # Convert to float
            p_mw = float(p_mw_raw)
            q_mvar = float(q_mvar_raw)
        
        # Convert to kW and kVar
        p_kw = p_mw * 1000
        q_kvar = q_mvar * 1000             
        
        load_name = element_name.replace(' ', '_')
        
        try:
            # Create load command string
            load_cmd = f"New Load.{load_name} Bus1={bus_name} kV={bus_voltage} kW={p_kw} kvar={abs(q_kvar)}"
            
            # For motors, add model parameter
            if is_motor:
                load_cmd += " model=1"  # Constant P+jQ model for motors
            
            # Append harmonic analysis properties if provided
            spectrum = element_data.get('spectrum', 'defaultload')
            if spectrum and spectrum.lower() != 'none':
                load_cmd += f" spectrum={spectrum}"
            pct_series_rl = element_data.get('pctSeriesRL', '')
            if pct_series_rl not in ('', None):
                try:
                    load_cmd += f" %SeriesRL={float(pct_series_rl)}"
                except (ValueError, TypeError):
                    pass
            # puXharm: Special reactance for harmonics (default 0.0 means use %SeriesRL calculation)
            pu_xharm = element_data.get('puXharm', '')
            if pu_xharm not in ('', None, '0', '0.0'):
                try:
                    load_cmd += f" puXharm={float(pu_xharm)}"
                except (ValueError, TypeError):
                    pass
            # XRharm: X/R ratio for harmonics (default 6.0, used when puXharm > 0)
            xr_harm = element_data.get('XRharm', '')
            if xr_harm not in ('', None):
                try:
                    load_cmd += f" XRharm={float(xr_harm)}"
                except (ValueError, TypeError):
                    pass
            
            # Create load using OpenDSS command
            execute_dss_command(load_cmd)
            
            # Handle in_service status AFTER creating the element
            in_service = element_data.get('in_service', True)
            
            # Convert to boolean for comparison
            is_in_service = True
            if isinstance(in_service, bool):
                is_in_service = in_service
            elif isinstance(in_service, str):
                is_in_service = in_service.lower() not in ['false', 'no', '0']
            elif in_service in [0, None]:
                is_in_service = False
            
            if not is_in_service:
                cmd = f'Load.{load_name}.enabled=no'
                print(f"[OpenDSS] {cmd}")
                dss.Text.Command(cmd)
            # print(f"Command: {load_cmd}")  # Reduced logging
            
            LoadsDict[element_name] = load_name
            LoadsDictId[element_name] = element_id
            created_elements.add(element_name)
            
        except Exception as e:
            pass
    else:
        pass
def create_static_generator_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, GeneratorsDict, GeneratorsDictId, created_elements, execute_dss_command=None):
    """Create a static generator element in OpenDSS"""
    
    # Check for duplicates - skip if already created
    if element_name in created_elements:
        return
    
    bus_connection = element_data.get('bus')
    if bus_connection:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_connection_backend = bus_connection
        if bus_connection_backend in BusbarsDictConnectionToName:
            bus_name = BusbarsDictConnectionToName[bus_connection_backend]
        bus_voltage = BusbarsDictVoltage.get(bus_name)
        
        # Validate voltage is available
        if bus_voltage is None:
            error_msg = (
                f"Missing voltage information for bus '{bus_name}' connected to static generator '{element_name}'.\n\n"
                f"Please set the 'vn_kv' (nominal voltage) attribute for the bus element.\n\n"
                f"Available buses with voltage: {list(BusbarsDictVoltage.keys())}"
            )
            raise ValueError(error_msg)
        
        if bus_voltage is not None:
            # Handle both regular and asymmetric static generators
            if 'p_a_mw' in element_data and 'p_b_mw' in element_data and 'p_c_mw' in element_data:
                # This is an asymmetric static generator - use phase A values as main values
                p_mw_raw = element_data.get('p_a_mw')
                q_mvar_raw = element_data.get('q_a_mvar')
            else:
                # Regular static generator
                p_mw_raw = element_data.get('p_mw')
                q_mvar_raw = element_data.get('q_mvar')

            # Convert to float
            p_mw = float(p_mw_raw)
            q_mvar = float(q_mvar_raw)
            
            # Convert to kW and kVar
            p_kw = p_mw * 1000
            q_kvar = q_mvar * 1000        
            
            gen_name = element_name.replace(' ', '_')
            
            try:
                # Use Generator element for static generator. Model=1 for constant P and Q
                # (exact match for pandapower sgen which is a constant P,Q source).
                gen_cmd = f"New Generator.{gen_name} Bus1={bus_name} Phases=3 kV={bus_voltage} kW={p_kw:.3f} kvar={q_kvar:.3f} Model=1"
                
                # Append harmonic analysis properties if provided
                spectrum = element_data.get('spectrum', 'defaultgen')
                if spectrum and spectrum.lower() != 'none':
                    gen_cmd += f" spectrum={spectrum}"
                xdpp = element_data.get('Xdpp', '')
                if xdpp not in ('', None):
                    try:
                        gen_cmd += f" Xdpp={float(xdpp)}"
                    except (ValueError, TypeError):
                        pass
                xrdp = element_data.get('XRdp', '')
                if xrdp not in ('', None):
                    try:
                        gen_cmd += f" XRdp={float(xrdp)}"
                    except (ValueError, TypeError):
                        pass
                
                execute_dss_command(gen_cmd)
                
                # Handle in_service status AFTER creating the element
                in_service = element_data.get('in_service', True)
                
                # Convert to boolean for comparison
                is_in_service = True
                if isinstance(in_service, bool):
                    is_in_service = in_service
                elif isinstance(in_service, str):
                    is_in_service = in_service.lower() not in ['false', 'no', '0']
                elif in_service in [0, None]:
                    is_in_service = False
                
                if not is_in_service:
                    cmd = f'Generator.{gen_name}.enabled=no'
                    print(f"[OpenDSS] {cmd}")
                    dss.Text.Command(cmd)
                # print(f"✓ Command: {gen_cmd}")  # Reduced logging
                
                # Store in GeneratorsDict
                GeneratorsDict[element_name] = gen_name
                GeneratorsDictId[element_name] = element_id
                created_elements.add(element_name)
                
            except Exception as e:
                pass
        else:
            pass
    else:
        pass
def create_generator_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, GeneratorsDict, GeneratorsDictId, created_elements, execute_dss_command=None):
    """Create a generator element in OpenDSS"""
    
    # Check for duplicates - skip if already created
    if element_name in created_elements:
        return
    
    bus_connection = element_data.get('bus')
    if bus_connection:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_connection_backend = bus_connection
        if bus_connection_backend in BusbarsDictConnectionToName:
            bus_name = BusbarsDictConnectionToName[bus_connection_backend]
        # Get voltage from the bus data
        bus_voltage = BusbarsDictVoltage.get(bus_name)
        
        if bus_voltage is None:
             #  ✗ Generator {element_name} cannot be created - no voltage information for bus {bus_name})
            return         
        # Get generator parameters with proper null handling
        p_mw_raw = element_data.get('p_mw')
        q_mvar_raw = element_data.get('q_mvar', 0)
        vm_pu_raw = element_data.get('vm_pu', 1.0)
        cos_phi_raw = element_data.get('cos_phi', 0.85)

        # Convert to float
        p_mw = float(p_mw_raw)
        q_mvar = float(q_mvar_raw)
        vm_pu = float(vm_pu_raw)
        cos_phi = float(cos_phi_raw)
        
        # Convert to kW and kVar
        p_kw = p_mw * 1000
        
        # If q_mvar is 0, calculate from cos_phi (matching pandapower generator behavior)
        if q_mvar == 0 and p_mw > 0 and cos_phi > 0 and cos_phi < 1.0:
            import math
            q_kvar = p_kw * math.tan(math.acos(cos_phi))
        else:
            q_kvar = q_mvar * 1000

        try:
            # Create generator command string with Model=3 for constant kW and kvar
            gen_cmd = f"New Generator.{element_name} Bus1={bus_name} kV={bus_voltage} kW={p_kw} kvar={q_kvar} Model=3 PF={cos_phi}"
            
            # Add fault study parameters if provided (sub-transient reactance/resistance)
            xdss_pu_raw = element_data.get('xdss_pu')
            rdss_ohm_raw = element_data.get('rdss_ohm')
            sn_mva_raw = element_data.get('sn_mva')
            
            # Convert to float safely
            xdss_pu = float(xdss_pu_raw) if xdss_pu_raw is not None else 0.0
            rdss_ohm = float(rdss_ohm_raw) if rdss_ohm_raw is not None else 0.0
            sn_mva = float(sn_mva_raw) if sn_mva_raw is not None else 0.0
            
            # kVA rating - only add if meaningful (non-zero)
            if sn_mva > 0:
                gen_cmd += f" kva={sn_mva * 1000}"
            
            # Xdp/Xdpp - only add if meaningful (non-zero)
            if xdss_pu > 0:
                gen_cmd += f" Xdp={xdss_pu}"
                gen_cmd += f" Xdpp={xdss_pu}"
            
            # XRdp: X/R ratio for fault studies
            if xdss_pu > 0 and rdss_ohm > 0 and sn_mva > 0:
                bus_kv = float(BusbarsDictVoltage.get(bus_name, 1.0))
                x_ohm = xdss_pu * (bus_kv ** 2) / sn_mva
                xr_ratio = x_ohm / rdss_ohm
                gen_cmd += f" XRdp={xr_ratio}"
            
            # Harmonic analysis properties
            spectrum = element_data.get('spectrum', 'defaultgen')
            if spectrum and spectrum.lower() != 'none':
                gen_cmd += f" spectrum={spectrum}"
            # Override Xdpp from harmonic tab if provided (may differ from short-circuit Xdpp)
            harm_xdpp = element_data.get('Xdpp')
            if harm_xdpp not in ('', None) and xdss_pu == 0:
                try:
                    xdpp_val = float(harm_xdpp)
                    if xdpp_val > 0:
                        gen_cmd += f" Xdpp={xdpp_val}"
                except (ValueError, TypeError):
                    pass
            harm_xrdp = element_data.get('XRdp')
            if harm_xrdp not in ('', None) and not (xdss_pu > 0 and rdss_ohm > 0 and sn_mva > 0):
                try:
                    gen_cmd += f" XRdp={float(harm_xrdp)}"
                except (ValueError, TypeError):
                    pass

            # Create generator using OpenDSS command
            execute_dss_command(gen_cmd)
            
            # Handle in_service status AFTER creating the element
            in_service = element_data.get('in_service', True)
            
            # Convert to boolean for comparison
            is_in_service = True
            if isinstance(in_service, bool):
                is_in_service = in_service
            elif isinstance(in_service, str):
                is_in_service = in_service.lower() not in ['false', 'no', '0']
            elif in_service in [0, None]:
                is_in_service = False
            
            if not is_in_service:
                cmd = f'Generator.{element_name}.enabled=no'
                print(f"[OpenDSS] {cmd}")
                dss.Text.Command(cmd)

            GeneratorsDict[element_name] = element_name
            GeneratorsDictId[element_name] = element_id
            created_elements.add(element_name)
            
        except Exception as e:
            pass
    else:
        pass
def vector_group_to_opendss_conns(vector_group):
    """Convert vector group notation to OpenDSS connection format
    
    Vector group examples:
    - Dyn: Delta (HV) - Wye with neutral (LV)
    - Yy: Wye (HV) - Wye (LV)
    - Yd: Wye (HV) - Delta (LV)
    - Dd: Delta (HV) - Delta (LV)
    - YNd: Wye with neutral (HV) - Delta (LV)
    
    OpenDSS format: (hv_conn lv_conn)
    Connections: wye, delta, zigzag
    """
    if not vector_group:
        return "wye wye"  # Default
    
    # Convert to uppercase for easier parsing
    vg = vector_group.upper()
    
    # Mapping for connection types
    conn_map = {
        'Y': 'wye',
        'D': 'delta',
        'Z': 'zigzag'
    }
    
    # Parse HV connection (first character)
    hv_conn = conn_map.get(vg[0], 'wye')
    
    # Parse LV connection (after 'N' if present, or second character)
    if len(vg) >= 2:
        # Skip 'N' if present (indicates neutral/grounded)
        lv_start = 2 if len(vg) > 2 and vg[1] == 'N' else 1
        if lv_start < len(vg):
            lv_conn = conn_map.get(vg[lv_start], 'wye')
        else:
            lv_conn = 'wye'
    else:
        lv_conn = 'wye'
    
    return f"{hv_conn} {lv_conn}"

def create_transformer_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, TransformersDict, TransformersDictId, created_elements, execute_dss_command=None):
    """Create a transformer element in OpenDSS"""
    
    # Check for duplicates - skip if already created
    if element_name in created_elements:
        return
    
    bus_from_ref = element_data.get('busFrom')
    bus_to_ref = element_data.get('busTo')    
 
    
    if bus_from_ref and bus_to_ref:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_from_ref_backend = bus_from_ref
        bus_to_ref_backend = bus_to_ref
        
        # Resolve bus names from references (could be IDs or names)
        if bus_from_ref_backend in BusbarsDictConnectionToName:
            bus_from_name = BusbarsDictConnectionToName[bus_from_ref_backend]
            if bus_from_name.startswith('mxCell'):
                bus_from_name = bus_from_name
            else:
                bus_from_name = bus_from_ref_backend
        else:
            bus_from_name = bus_from_ref_backend
            
        if bus_to_ref_backend in BusbarsDictConnectionToName:
            bus_to_name = BusbarsDictConnectionToName[bus_to_ref_backend]
            if bus_to_name.startswith('mxCell'):
                bus_to_name = bus_to_name
            else:
                bus_to_name = bus_to_ref_backend
        else:
            bus_to_name = bus_to_ref_backend
        
        
        try:
            # Get voltage ratings from the connected buses
            bus_from_voltage = BusbarsDictVoltage.get(bus_from_name)
            bus_to_voltage = BusbarsDictVoltage.get(bus_to_name)
            
            # Get transformer parameters from frontend data - no defaults
            sn_mva_raw = element_data.get('sn_mva')
            vk_percent_raw = element_data.get('vk_percent')
            vkr_percent_raw = element_data.get('vkr_percent')
            vn_hv_kv_raw = element_data.get('vn_hv_kv')
            vn_lv_kv_raw = element_data.get('vn_lv_kv')
            vector_group = element_data.get('vector_group', 'Dyn')  # Default to Dyn if not specified
            
            # Validate that both bus voltages are available
            # No defaults or fallbacks - user must provide proper voltage information
            if bus_from_voltage is None:
                error_msg = (
                    f"Missing voltage information for bus '{bus_from_name}' connected to transformer '{element_name}'.\n\n"
                    f"Please ensure:\n"
                    f"1. The bus element has a 'vn_kv' (nominal voltage) attribute set, OR\n"
                    f"2. The transformer has 'vn_hv_kv' parameter set\n\n"
                    f"Available buses with voltage: {list(BusbarsDictVoltage.keys())}"
                )
                raise ValueError(error_msg)
            
            if bus_to_voltage is None:
                error_msg = (
                    f"Missing voltage information for bus '{bus_to_name}' connected to transformer '{element_name}'.\n\n"
                    f"Please ensure:\n"
                    f"1. The bus element has a 'vn_kv' (nominal voltage) attribute set, OR\n"
                    f"2. The transformer has 'vn_lv_kv' parameter set\n\n"
                    f"Available buses with voltage: {list(BusbarsDictVoltage.keys())}"
                )
                raise ValueError(error_msg)
           
            
            # Convert to float
            sn_mva = float(sn_mva_raw)
            vk_percent = float(vk_percent_raw)
            vkr_percent = float(vkr_percent_raw)
            
            # Convert MVA to kVA
            sn_kva = sn_mva * 1000
            
            # Convert vector group to OpenDSS connection format
            conns = vector_group_to_opendss_conns(vector_group)
            
            # Get loss parameters from frontend
            pfe_kw_raw = element_data.get('pfe_kw', '0')
            i0_percent_raw = element_data.get('i0_percent', '0')
            
            # Convert loss parameters to float
            pfe_kw = float(pfe_kw_raw)
            i0_percent = float(i0_percent_raw)
            
            # Get tap parameters from frontend
            tap_pos_raw = element_data.get('tap_pos', '0')
            tap_step_percent_raw = element_data.get('tap_step_percent', '1.5')
            tap_side = element_data.get('tap_side', 'hv')
            
            # Convert to numbers
            tap_pos = float(tap_pos_raw)
            tap_step_percent = float(tap_step_percent_raw)
            
            # Calculate tap values for each winding
            # Tap is a multiplier: 1.0 = neutral position
            # tap_pos * tap_step_percent gives the percentage change
            tap_change = tap_pos * tap_step_percent / 100.0
            
            if tap_side.lower() == 'hv':
                # Tap on HV side (winding 1)
                tap_hv = 1.0 + tap_change
                tap_lv = 1.0
            else:
                # Tap on LV side (winding 2)
                tap_hv = 1.0
                tap_lv = 1.0 + tap_change
            
            # Calculate no-load loss percentage from iron losses
            # %noloadloss = (total_iron_losses_kw / rated_kVA) * 100
            # This is a scalar property in OpenDSS applied to the transformer core
            if pfe_kw > 0 and sn_kva > 0:
                noloadloss_percent = (pfe_kw / sn_kva) * 100
            else:
                noloadloss_percent = 0
            
            # Split the winding resistance between HV and LV sides
            # Total %Rs should be split approximately 50/50 between windings for typical transformers
            rs_hv = vkr_percent / 2.0
            rs_lv = vkr_percent / 2.0
            
            # CRITICAL: OpenDSS XHL is the REACTANCE component only (not total impedance)
            # pandapower vk_percent = |Z_sc| = sqrt(vkr_percent^2 + vkx_percent^2)
            # OpenDSS XHL = vkx_percent = sqrt(vk_percent^2 - vkr_percent^2)
            if vk_percent > vkr_percent:
                xhl_percent = math.sqrt(vk_percent**2 - vkr_percent**2)
            else:
                xhl_percent = vk_percent  # Fallback: if vkr >= vk (shouldn't happen)
            
            # Create complete OpenDSS transformer command with calculated taps and losses
            # XHL = reactive component, %Rs = resistive components per winding
            transformer_cmd = f"New Transformer.{element_name} Phases=3 Windings=2 Buses=({bus_from_name} {bus_to_name}) Conns=({conns}) kVs=({bus_from_voltage} {bus_to_voltage}) kVAs=({sn_kva} {sn_kva}) XHL={xhl_percent} %Rs=[{rs_hv} {rs_lv}] Taps=[{tap_hv} {tap_lv}]"
            
            # Add loss parameters if they are non-zero
            # %noloadloss and %imag are scalar properties in OpenDSS (not per-winding arrays)
            if noloadloss_percent > 0:
                transformer_cmd += f" %noloadloss={noloadloss_percent}"
            
            # %imag is the magnetizing current as % of rated current (scalar property)
            if i0_percent > 0:
                transformer_cmd += f" %imag={i0_percent}"
            
            # Harmonic analysis property: XRConst
            # When Yes, X/R ratio is constant for all frequencies (series RL model)
            xr_const = element_data.get('XRConst', 'No')
            if xr_const and str(xr_const).lower() in ('yes', 'true'):
                transformer_cmd += " XRConst=Yes"
            
            execute_dss_command(transformer_cmd)
            
            # Handle in_service status AFTER creating the element
            in_service = element_data.get('in_service', True)
            
            # Convert to boolean for comparison
            is_in_service = True
            if isinstance(in_service, bool):
                is_in_service = in_service
            elif isinstance(in_service, str):
                is_in_service = in_service.lower() not in ['false', 'no', '0']
            elif in_service in [0, None]:
                is_in_service = False
            
            if not is_in_service:
                cmd = f'Transformer.{element_name}.enabled=no'
                print(f"[OpenDSS] {cmd}")
                dss.Text.Command(cmd)
            # print(f"Command: {transformer_cmd}")  # Reduced logging
            
            # Log loss parameters if they are included
            if noloadloss_percent > 0 or i0_percent > 0:
                pass
            TransformersDict[element_name] = element_name
            TransformersDictId[element_name] = element_id
            created_elements.add(element_name)
            
        except Exception as e:
            try:
                pass
            except Exception as debug_e:
                pass
    else:
        pass
def create_shunt_reactor_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, ShuntsDict, ShuntsDictId, created_elements, execute_dss_command=None):
    """Create a shunt reactor element in OpenDSS"""
    
    # Check for duplicates - skip if already created
    if element_name in created_elements:
        return
    
    bus_connection = element_data.get('bus')
    if bus_connection:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_connection_backend = bus_connection
        if bus_connection_backend in BusbarsDictConnectionToName:
            bus_name = BusbarsDictConnectionToName[bus_connection_backend]
        # Get voltage from the bus data
        bus_voltage = BusbarsDictVoltage.get(bus_name)
        
        # Validate voltage is available
        if bus_voltage is None:
            error_msg = (
                f"Missing voltage information for bus '{bus_name}' connected to shunt reactor '{element_name}'.\n\n"
                f"Please set the 'vn_kv' (nominal voltage) attribute for the bus element.\n\n"
                f"Available buses with voltage: {list(BusbarsDictVoltage.keys())}"
            )
            raise ValueError(error_msg)
        
        # Get shunt reactor parameters with proper null handling
        q_mvar_raw = element_data.get('q_mvar')
        p_mw_raw = element_data.get('p_mw')  # Active power from frontend
        
        # Debug: Print what we received
    
        
        # Convert to float
        q_mvar = float(q_mvar_raw)
        p_mw = float(p_mw_raw) if p_mw_raw is not None else 0.0
        
        # Convert to kVar and kW
        q_kvar = q_mvar * 1000
        p_kw = p_mw * 1000
        
        
        # OpenDSS Reactor element: constant impedance (kV + kvar), matches pandapower shunt.
        # Optional Rp = V_LL² / P_total for no-load losses when p_mw > 0.
        try:
            reactor_name = f"ShuntReactor_{element_name}"
            # kvar positive = inductive (reactor absorbs Q at rated voltage)
            cmd_parts = [f"New Reactor.{reactor_name} Bus1={bus_name} Phases=3 kV={bus_voltage} kvar={abs(q_kvar):.0f}"]
            if p_kw > 0 and bus_voltage is not None:
                voltage_kv = float(bus_voltage)
                p_watts = p_kw * 1000
                v_volts = voltage_kv * 1000
                rp_ohms = (v_volts ** 2) / p_watts
                cmd_parts.append(f" Rp={rp_ohms:.2f}")
            reactor_cmd = "".join(cmd_parts)
            execute_dss_command(reactor_cmd)
            
            # Handle in_service status AFTER creating the element
            in_service = element_data.get('in_service', True)
            
            # Convert to boolean for comparison
            is_in_service = True
            if isinstance(in_service, bool):
                is_in_service = in_service
            elif isinstance(in_service, str):
                is_in_service = in_service.lower() not in ['false', 'no', '0']
            elif in_service in [0, None]:
                is_in_service = False
            
            if not is_in_service:
                cmd = f'Reactor.{reactor_name}.enabled=no'
                print(f"[OpenDSS] {cmd}")
                dss.Text.Command(cmd)

            ShuntsDict[element_name] = reactor_name
            ShuntsDictId[element_name] = element_id
            created_elements.add(element_name)
        except Exception as e:
            pass
    else:
        pass
def create_capacitor_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, CapacitorsDict, CapacitorsDictId, created_elements, execute_dss_command=None):
    """Create a capacitor element in OpenDSS"""
    
    # Check for duplicates - skip if already created
    if element_name in created_elements:
        return
    
    bus_connection = element_data.get('bus')
    if bus_connection:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_connection_backend = bus_connection
        if bus_connection_backend in BusbarsDictConnectionToName:
            bus_name = BusbarsDictConnectionToName[bus_connection_backend]
        bus_voltage = BusbarsDictVoltage.get(bus_name)
        
        # Validate voltage is available
        if bus_voltage is None:
            error_msg = (
                f"Missing voltage information for bus '{bus_name}' connected to capacitor '{element_name}'.\n\n"
                f"Please set the 'vn_kv' (nominal voltage) attribute for the bus element.\n\n"
                f"Available buses with voltage: {list(BusbarsDictVoltage.keys())}"
            )
            raise ValueError(error_msg)
        
        if bus_voltage is not None:
            # Get capacitor parameters with proper null handling
            q_mvar_raw = element_data.get('q_mvar')
            
            # Check if required parameter is present
            if q_mvar_raw is None:
               # ✗ Capacitor {element_name} cannot be created - missing q_mvar parameter")
                return
            
            # Convert to float
            q_mvar = float(q_mvar_raw)
            
            # Convert to kVar
            q_kvar = q_mvar * 1000           
            
            
            try:
                # Use bus name directly - OpenDSS will create bus automatically
                simple_cmd = f"New Capacitor.{element_name} Bus1={bus_name} kvar={abs(q_kvar)} kV={bus_voltage}"
                execute_dss_command(simple_cmd)
                # print(f"Command: {simple_cmd}")  # Reduced logging
                
                # Handle in_service status AFTER creating the element
                in_service = element_data.get('in_service', True)
                
                # Convert to boolean for comparison
                is_in_service = True
                if isinstance(in_service, bool):
                    is_in_service = in_service
                elif isinstance(in_service, str):
                    is_in_service = in_service.lower() not in ['false', 'no', '0']
                elif in_service in [0, None]:
                    is_in_service = False
                
                if not is_in_service:
                    cmd = f'Capacitor.{element_name}.enabled=no'
                    print(f"[OpenDSS] {cmd}")
                    dss.Text.Command(cmd)

                CapacitorsDict[element_name] = element_name
                CapacitorsDictId[element_name] = element_id
                created_elements.add(element_name)
                
            except Exception as e:
                pass
        else:
            pass
    else:
        pass
def create_storage_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, StoragesDict, StoragesDictId, created_elements, execute_dss_command=None):
    """Create a storage element in OpenDSS"""
    
    # Check for duplicates - skip if already created
    if element_name in created_elements:
        return
    
    bus_connection = element_data.get('bus')
    if bus_connection:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_connection_backend = bus_connection
        if bus_connection_backend in BusbarsDictConnectionToName:
            bus_name = BusbarsDictConnectionToName[bus_connection_backend]
        bus_voltage = BusbarsDictVoltage.get(bus_name)
        
        # Validate voltage is available
        if bus_voltage is None:
            error_msg = (
                f"Missing voltage information for bus '{bus_name}' connected to storage '{element_name}'.\n\n"
                f"Please set the 'vn_kv' (nominal voltage) attribute for the bus element.\n\n"
                f"Available buses with voltage: {list(BusbarsDictVoltage.keys())}"
            )
            raise ValueError(error_msg)
        
        if bus_voltage is not None:
            # Get storage parameters
            p_mw_raw = element_data.get('p_mw')
            q_mvar_raw = element_data.get('q_mvar')           
            # Convert to float
            p_mw = float(p_mw_raw)
            q_mvar = float(q_mvar_raw)
            
            # Convert to kW and kVar
            p_kw = p_mw * 1000
            q_kvar = q_mvar * 1000
                        
            try:
                # Use bus name directly - OpenDSS will create bus automatically
                simple_cmd = f"New Storage.{element_name} Bus1={bus_name} kV={bus_voltage} kW={p_kw} kvar={q_kvar}"
                
                # Append harmonic analysis spectrum if provided
                spectrum = element_data.get('spectrum', 'default')
                if spectrum and spectrum.lower() not in ('none', ''):
                    simple_cmd += f" spectrum={spectrum}"
                
                execute_dss_command(simple_cmd)
                # print(f"Command: {simple_cmd}")  # Reduced logging
                
                # Handle in_service status AFTER creating the element
                in_service = element_data.get('in_service', True)
                
                # Convert to boolean for comparison
                is_in_service = True
                if isinstance(in_service, bool):
                    is_in_service = in_service
                elif isinstance(in_service, str):
                    is_in_service = in_service.lower() not in ['false', 'no', '0']
                elif in_service in [0, None]:
                    is_in_service = False
                
                if not is_in_service:
                    cmd = f'Storage.{element_name}.enabled=no'
                    print(f"[OpenDSS] {cmd}")
                    dss.Text.Command(cmd)
       
                
                StoragesDict[element_name] = element_name
                StoragesDictId[element_name] = element_id
                created_elements.add(element_name)
                
            except Exception as e:
                pass
        else:
            pass
    else:
        pass
def create_pvsystem_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, PVSystemsDict, PVSystemsDictId, created_elements, execute_dss_command=None):
    """Create a PVSystem element in OpenDSS with comprehensive parameter support"""
    
    # Check for duplicates - skip if already created
    if element_name in created_elements:
        return
    
    bus_connection = element_data.get('bus')
    if bus_connection:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_connection_backend = bus_connection
        if bus_connection_backend in BusbarsDictConnectionToName:
            bus_name = BusbarsDictConnectionToName[bus_connection_backend]
        bus_voltage = BusbarsDictVoltage.get(bus_name)

        # Validate voltage is available
        if bus_voltage is None:
            error_msg = (
                f"Missing voltage information for bus '{bus_name}' connected to PV system '{element_name}'.\n\n"
                f"Please set the 'vn_kv' (nominal voltage) attribute for the bus element.\n\n"
                f"Available buses with voltage: {list(BusbarsDictVoltage.keys())}"
            )
            raise ValueError(error_msg)

        if bus_voltage is not None:
            # Extract ONLY VALIDATED PVSystem parameters from frontend data
            # These parameters are confirmed to work in OpenDSS
            
            # Basic required parameters
            irradiance_raw = element_data.get('irradiance')
            pmpp_raw = element_data.get('pmpp')
            temperature_raw = element_data.get('temperature')
            phases_raw = element_data.get('phases')
            kv_raw = element_data.get('kv')
            
            # Power parameters
            pf_raw = element_data.get('pf')
            kvar_raw = element_data.get('kvar')
            kva_raw = element_data.get('kva')
            
            # Cut-in/Cut-out parameters (frontend sends as per-unit 0.1, needs to be converted to percentage 10%)
            cutin_raw = element_data.get('cutin')
            cutout_raw = element_data.get('cutout')

            # Convert basic parameters with defaults
            irradiance = float(irradiance_raw) if irradiance_raw is not None else 1.0
            pmpp = float(pmpp_raw) if pmpp_raw is not None else 100.0  # kW
            temperature = float(temperature_raw) if temperature_raw is not None else 25.0
            phases = int(phases_raw) if phases_raw is not None else 3
            kv = float(kv_raw) if kv_raw is not None else float(bus_voltage)
            pf = float(pf_raw) if pf_raw is not None else 1.0
            kvar = float(kvar_raw) if kvar_raw is not None else 0.0
            kva = float(kva_raw) if kva_raw is not None else pmpp * 1.2  # Default 20% above Pmpp

            try:
                # Create PVSystem command string with ONLY VALIDATED OpenDSS parameters
                # Based on OpenDSS documentation and user validation
                pv_cmd = f"New PVSystem.{element_name} phases={phases} Bus1={bus_name} kV={kv} irradiance={irradiance} Pmpp={pmpp} Temperature={temperature}"
                
     
                
                # Add power parameters (VALIDATED - these work in OpenDSS)
                if pf_raw is not None:
                    pv_cmd += f" pf={pf}"
                if kvar_raw is not None:
                    pv_cmd += f" kvar={kvar}"
                if kva_raw is not None:
                    pv_cmd += f" kVA={kva}"
                
                # Add cut-in/cut-out (VALIDATED - frontend sends as per-unit, OpenDSS expects percentage)
                if cutin_raw is not None:
                    cutin_percent = float(cutin_raw) * 100  # Convert 0.1 to 10%
                    pv_cmd += f" %Cutin={cutin_percent}"
                if cutout_raw is not None:
                    cutout_percent = float(cutout_raw) * 100  # Convert 0.1 to 10%
                    pv_cmd += f" %Cutout={cutout_percent}"
                
                # ONLY ADD PARAMETERS THAT ARE CONFIRMED TO WORK IN OpenDSS
                # The following parameters caused "Unknown parameter" errors and are commented out:
                # - PminKvarMax (not supported)
                # - PminNoVars (not supported)
                # - %PmppGain (not supported)
                # - Many other advanced parameters are not in standard OpenDSS
                
                # Harmonic analysis property
                spectrum = element_data.get('spectrum', 'default')
                if spectrum and spectrum.lower() not in ('none', ''):
                    pv_cmd += f" spectrum={spectrum}"
                
                # If you need additional parameters, verify them in OpenDSS documentation first:
                # https://opendss.epri.com/PVSystem.html

                execute_dss_command(pv_cmd)
              

                # Handle in_service status AFTER creating the element
                in_service = element_data.get('in_service', True)
                
                # Convert to boolean for comparison
                is_in_service = True
                if isinstance(in_service, bool):
                    is_in_service = in_service
                elif isinstance(in_service, str):
                    is_in_service = in_service.lower() not in ['false', 'no', '0']
                elif in_service in [0, None]:
                    is_in_service = False
                
                if not is_in_service:
                    cmd = f'PVSystem.{element_name}.enabled=no'
                    print(f"[OpenDSS] {cmd}")
                    dss.Text.Command(cmd)

                PVSystemsDict[element_name] = element_name
                PVSystemsDictId[element_name] = element_id
                created_elements.add(element_name)

            except Exception as e:
                pass
        else:
            pass
    else:
        pass
def create_external_grid_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, created_elements, execute_dss_command=None):
    """Create an external grid element in OpenDSS"""
    
    # Check for duplicates - skip if already created
    if element_name in created_elements:
        return
    
    bus_connection = element_data.get('bus')
    if bus_connection:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_connection_backend = bus_connection
        if bus_connection_backend in BusbarsDictConnectionToName:
            bus_name = BusbarsDictConnectionToName[bus_connection_backend]
        bus_voltage = BusbarsDictVoltage.get(bus_name)        
     
        # Validate voltage is available
        if bus_voltage is None:
            error_msg = (
                f"Missing voltage information for bus '{bus_name}' connected to external grid '{element_name}'.\n\n"
                f"Please set the 'vn_kv' (nominal voltage) attribute for the bus element.\n\n"
                f"Available buses with voltage: {list(BusbarsDictVoltage.keys())}"
            )
            raise ValueError(error_msg)
     
        # Get external grid parameters
        vm_pu_raw = element_data.get('vm_pu')
        s_sc_max_mva_raw = element_data.get('s_sc_max_mva')
        
        # Convert to float
        vm_pu = float(vm_pu_raw)
        s_sc_max_mva = float(s_sc_max_mva_raw)
        
        # Validate and auto-correct vm_pu (OpenDSS Vsource 'pu' parameter)
        # vm_pu should be close to 1.0 (per unit). If user entered kV value instead of p.u., auto-correct.
        if vm_pu == 0:
            vm_pu = 1.0
            print(f"WARNING: External Grid '{element_name}' had vm_pu=0, auto-corrected to 1.0 p.u.")
        elif vm_pu > 1.5 and bus_voltage is not None and float(bus_voltage) > 0:
            corrected_vm_pu = vm_pu / float(bus_voltage)
            print(f"WARNING: External Grid '{element_name}' has vm_pu={vm_pu}, "
                  f"which is unreasonably high. vm_pu should be close to 1.0 (per unit). "
                  f"Bus voltage is {bus_voltage} kV. Auto-correcting to {corrected_vm_pu:.4f} p.u. "
                  f"(assuming user entered kV instead of p.u.)")
            vm_pu = corrected_vm_pu
        
        # Ensure short circuit MVA is not zero (would cause singular matrix)
        # Use a reasonable default if zero or very small
        if s_sc_max_mva <= 0.1:
            s_sc_max_mva = 10000.0  # Default 10000 MVA short circuit capacity
        
        try:
            # Build spectrum parameter if provided
            spectrum = element_data.get('spectrum', 'defaultvsource')
            spectrum_suffix = ''
            if spectrum and spectrum.lower() != 'none':
                spectrum_suffix = f" spectrum={spectrum}"
            
            if 'circuit_source_configured' not in created_elements:
                # First external grid: configure the default Circuit source directly.
                # When 'New Circuit' is called, OpenDSS creates a default Vsource named
                # "source" at bus "sourcebus". Instead of disabling it and creating a
                # separate Vsource, we edit it with the first external grid's parameters.
                # This is cleaner and follows the standard OpenDSS pattern where the
                # Circuit source IS the main grid connection.
                edit_cmd = (f"Edit Vsource.source Bus1={bus_name} basekv={bus_voltage} "
                            f"pu={vm_pu} Phases=3 angle=0 mvasc3={s_sc_max_mva}{spectrum_suffix}")
                execute_dss_command(edit_cmd)
                created_elements.add('circuit_source_configured')
                # Track which element name maps to the circuit source for result retrieval
                created_elements.add(f'circuit_source_element:{element_name}')
            else:
                # Additional external grids: create a new Vsource element
                external_grid_cmd = (f"New Vsource.{element_name} Bus1={bus_name} basekv={bus_voltage} "
                                     f"pu={vm_pu} Phases=3 angle=0 mvasc3={s_sc_max_mva}{spectrum_suffix}")
                execute_dss_command(external_grid_cmd)
            
            # Handle in_service status AFTER creating the element
            in_service = element_data.get('in_service', True)
            
            # Convert to boolean for comparison
            is_in_service = True
            if isinstance(in_service, bool):
                is_in_service = in_service
            elif isinstance(in_service, str):
                is_in_service = in_service.lower() not in ['false', 'no', '0']
            elif in_service in [0, None]:
                is_in_service = False
            
            if not is_in_service:
                # For the first external grid (mapped to source), we edit it
                if 'circuit_source_element:' + element_name in created_elements:
                    cmd = 'Vsource.source.enabled=no'
                    print(f"[OpenDSS] {cmd}")
                    dss.Text.Command(cmd)
                else:
                    # For additional external grids
                    cmd = f'Vsource.{element_name}.enabled=no'
                    print(f"[OpenDSS] {cmd}")
                    dss.Text.Command(cmd)
            
            created_elements.add(element_name)
            
        except Exception as e:
            pass
    else:
        pass


def shortcircuit(in_data, frequency=50, fault_type='3ph', export_open_dss_results=False):
    """OpenDSS fault study / short circuit analysis.

    Builds the circuit from in_data (same as powerflow), sets Solution.Mode to FaultStudy,
    solves, and returns bus short circuit results in the same format as Pandapower
    (busbars with ikss_ka, ip_ka, ith_ka, rk_ohm, xk_ohm) for frontend compatibility.

    Reference: https://opendss.epri.com/OpenDSSFaultStudyMode.html
    OpenDSSDirect.py: dss.Solution.Mode(4) for FaultStudy, dss.Bus.Isc(), dss.Bus.Zsc1()
    """
    opendss_commands = []

    def execute_dss_command(command):
        print(f"[OpenDSS] {command}")  # Log all commands
        dss.Text.Command(command)
        if export_open_dss_results:
            opendss_commands.append(command)

    f = int(frequency) if frequency else 50
    execute_dss_command('clear')
    execute_dss_command('New Circuit.OpenDSS_Circuit')
    execute_dss_command(f'set DefaultBaseFrequency={f}')

    try:
        BusbarsDictVoltage, BusbarsDictConnectionToName = create_busbars(in_data, dss, False, opendss_commands)
        (LinesDict, LinesDictId, LoadsDict, LoadsDictId, TransformersDict, TransformersDictId,
         ShuntsDict, ShuntsDictId, CapacitorsDict, CapacitorsDictId, GeneratorsDict, GeneratorsDictId,
         StoragesDict, StoragesDictId, PVSystemsDict, PVSystemsDictId, ExternalGridsDict, ExternalGridsDictId,
         _circuit_source) = create_other_elements(in_data, dss, BusbarsDictVoltage, BusbarsDictConnectionToName, False, opendss_commands, execute_dss_command)
    except ValueError as ve:
        return json.dumps({"error": str(ve)})
    except Exception as e:
        return json.dumps({"error": f"Error creating network elements: {str(e)}"})

    # Set voltage bases (required for fault study and per-unit results)
    try:
        # Explicit voltage base list helps FaultStudy; calcv refines from equipment
        if BusbarsDictVoltage:
            vb_list = sorted(set(float(v) for v in BusbarsDictVoltage.values()), reverse=True)
            if vb_list:
                execute_dss_command('set voltagebases=[' + ','.join(str(v) for v in vb_list) + ']')
        print("[OpenDSS] calcv")
        dss.Text.Command('calcv')
    except Exception:
        pass

    # Run Snapshot solve first so circuit has a solution and open-circuit voltages exist
    # Fault Study uses these for Isc = Ysc * Voc; some engines need this before FaultStudy
    try:
        dss.Solution.Mode(0)  # 0 = Snapshot
        dss.Solution.Solve()
        print(f"[DEBUG] Snapshot solve completed. Converged: {dss.Solution.Converged()}")
        # Check if buses have voltage after snapshot solve
        for bus_name in (dss.Circuit.AllBusNames() or [])[:3]:
            dss.Circuit.SetActiveBus(bus_name)
            vmag = dss.Bus.VMagAngle()
            print(f"[DEBUG] After Snapshot - Bus {bus_name}: VMagAngle={vmag[:4] if vmag and len(vmag) >= 4 else vmag}")
    except Exception as e:
        print(f"[DEBUG] Snapshot solve exception: {e}")
        try:
            execute_dss_command('set Mode=Snapshot')
            print("[OpenDSS] solve")
            dss.Text.Command('solve')
        except Exception:
            pass

    # Set solution mode to Fault Study (mode 4) and solve
    # https://opendss.epri.com/OpenDSSFaultStudyMode.html
    # Use run_command so the engine runs the full fault-study sequence (Solve populates Isc/Zsc per bus)
    try:
        execute_dss_command('set Mode=FaultStudy')
        print("[OpenDSS] solve")
        dss.Text.Command('solve')
        print(f"[DEBUG] FaultStudy solve completed. Solution.Mode: {dss.Solution.Mode()}")
        if hasattr(dss.Solution, 'Converged'):
            print(f"[DEBUG] Solution.Converged: {dss.Solution.Converged()}")
    except Exception as e1:
        try:
            dss.Solution.Mode(4)
            dss.Solution.Solve()
            print(f"[DEBUG] FaultStudy solve (API) completed. Solution.Mode: {dss.Solution.Mode()}")
        except Exception as e2:
            return json.dumps({"error": f"Fault study solve failed: {str(e1)}; {str(e2)}"})

    # Build bus index mapping (same as powerflow)
    BusbarsDict = {}
    nBusbar = 0
    for bus_id in BusbarsDictConnectionToName.keys():
        BusbarsDict[bus_id] = nBusbar
        nBusbar += 1

    # Map bus name (with _) to graph cell id from in_data for frontend getCell(cell.id)
    bus_name_to_graph_id = {}
    for key in in_data:
        try:
            elem = in_data[key]
            if elem and isinstance(elem, dict) and 'Bus' in str(elem.get('typ', '')) and elem.get('name') and elem.get('id') is not None:
                bus_name_to_graph_id[str(elem.get('name')).replace('#', '_')] = str(elem.get('id'))
        except (TypeError, AttributeError):
            continue

    busbarList = []
    processed_buses = set()
    kappa = 1.8  # Peak current factor for ip_ka = kappa * sqrt(2) * ikss_ka

    try:
        all_bus_names = dss.Circuit.AllBusNames()
        print(f"[DEBUG] Total buses in circuit: {len(all_bus_names) if all_bus_names else 0}")
        print(f"[DEBUG] All bus names: {all_bus_names}")
        for bus_name_from_list in all_bus_names:
            dss.Circuit.SetActiveBus(bus_name_from_list)
            actual_bus_name = dss.Bus.Name()
            if actual_bus_name.lower() in ['sourcebus', 'source'] or bus_name_from_list.lower() in ['sourcebus', 'source']:
                continue

            matched_bus_id = None
            bus_number = None
            for key, value in BusbarsDict.items():
                if key.lower() == actual_bus_name.lower():
                    matched_bus_id = key
                    bus_number = value
                    break
            if not matched_bus_id or bus_number in processed_buses:
                continue
            processed_buses.add(bus_number)

            try:
                # Ensure Zsc/Isc are populated for this bus (required in some OpenDSS versions)
                if hasattr(dss.Bus, 'ZscRefresh'):
                    try:
                        dss.Bus.ZscRefresh()
                    except Exception:
                        pass
                # Isc() returns complex array: [I1_re, I1_im, I2_re, I2_im, ...] in Amps (flat), or list of 3 complex when AdvancedTypes
                isc_arr = dss.Bus.Isc()
                print(f"[DEBUG] Bus {actual_bus_name}: Isc() = {isc_arr}, type: {type(isc_arr)}, len: {len(isc_arr) if isc_arr else 0}")
                ikss_ka = 0.0
                if isc_arr is not None:
                    if len(isc_arr) >= 6:
                        # Flat [re, im, re, im, re, im]
                        try:
                            I_a = complex(float(isc_arr[0]), float(isc_arr[1]))
                            I_b = complex(float(isc_arr[2]), float(isc_arr[3]))
                            I_c = complex(float(isc_arr[4]), float(isc_arr[5]))
                            ikss_mag = (abs(I_a) + abs(I_b) + abs(I_c)) / 3.0
                            ikss_ka = ikss_mag / 1000.0
                        except (TypeError, ValueError, IndexError):
                            pass
                    elif len(isc_arr) >= 3:
                        # List of 3 complex numbers (AdvancedTypes)
                        try:
                            mags = []
                            for x in isc_arr[:3]:
                                if hasattr(x, 'real') and hasattr(x, 'imag'):
                                    mags.append(abs(x))
                                elif hasattr(x, '__len__') and len(x) >= 2:
                                    mags.append(abs(complex(float(x[0]), float(x[1]))))
                                else:
                                    mags.append(0.0)
                            ikss_mag = sum(mags) / 3.0
                            ikss_ka = ikss_mag / 1000.0
                        except (TypeError, ValueError, IndexError):
                            pass

                # Peak short-circuit current: ip = kappa * sqrt(2) * ikss
                ip_ka = kappa * math.sqrt(2) * ikss_ka if ikss_ka else 0.0
                # Thermal short-circuit current (short duration): ith ≈ ikss
                ith_ka = ikss_ka

                # Zsc1() returns complex positive-sequence short-circuit impedance at bus (ohms)
                # May be [real, imag] list or a single complex number
                zsc1 = dss.Bus.Zsc1()
                print(f"[DEBUG] Bus {actual_bus_name}: Zsc1() = {zsc1}, type: {type(zsc1)}")
                rk_ohm = 0.0
                xk_ohm = 0.0
                if zsc1 is not None:
                    if hasattr(zsc1, '__len__') and len(zsc1) >= 2:
                        try:
                            rk_ohm = float(zsc1[0])
                            xk_ohm = float(zsc1[1])
                        except (TypeError, ValueError, IndexError):
                            pass
                    elif hasattr(zsc1, 'real') and hasattr(zsc1, 'imag'):
                        rk_ohm = float(zsc1.real)
                        xk_ohm = float(zsc1.imag)

                # When Isc() returns zeros but Zsc1 is valid, derive Isc from OpenDSS Voc and Zsc1 (Isc = Ysc*Voc = Voc/Zsc1)
                if ikss_ka <= 0.0 and (rk_ohm != 0.0 or xk_ohm != 0.0) and hasattr(dss.Bus, 'Voc'):
                    try:
                        voc_arr = dss.Bus.Voc()
                        print(f"[DEBUG] Bus {actual_bus_name}: Voc() = {voc_arr}, type: {type(voc_arr)}, len: {len(voc_arr) if voc_arr else 0}")
                        v_ln = 0.0
                        if voc_arr is not None and len(voc_arr) >= 2:
                            if len(voc_arr) >= 6:
                                # Flat [re, im, re, im, re, im] - use first phase magnitude (line-to-neutral)
                                v1 = complex(float(voc_arr[0]), float(voc_arr[1]))
                                v2 = complex(float(voc_arr[2]), float(voc_arr[3]))
                                v3 = complex(float(voc_arr[4]), float(voc_arr[5]))
                                v_ln = (abs(v1) + abs(v2) + abs(v3)) / 3.0
                            else:
                                v_ln = abs(complex(float(voc_arr[0]), float(voc_arr[1])))
                        if v_ln > 0:
                            z_mag = math.sqrt(rk_ohm * rk_ohm + xk_ohm * xk_ohm)
                            if z_mag > 0:
                                ikss_ka = (v_ln / z_mag) / 1000.0  # Amps -> kA
                                ip_ka = kappa * math.sqrt(2) * ikss_ka
                                ith_ka = ikss_ka
                    except (TypeError, ValueError, IndexError, ZeroDivisionError):
                        pass

                # Use graph cell id from in_data so frontend getCell(cell.id) finds the bus
                frontend_bus_id = bus_name_to_graph_id.get(matched_bus_id) or matched_bus_id.replace('_', '#')
                frontend_bus_name = BusbarsDictConnectionToName.get(matched_bus_id, matched_bus_id).replace('_', '#')
                print(f"[DEBUG] Bus {actual_bus_name}: Final ikss_ka={ikss_ka}, ip_ka={ip_ka}, ith_ka={ith_ka}, rk_ohm={rk_ohm}, xk_ohm={xk_ohm}")
                busbar = BusbarScOut(
                    name=frontend_bus_name,
                    id=frontend_bus_id,
                    ikss_ka=round(ikss_ka, 6),
                    ip_ka=round(ip_ka, 6),
                    ith_ka=round(ith_ka, 6),
                    rk_ohm=round(rk_ohm, 6),
                    xk_ohm=round(xk_ohm, 6)
                )
                busbarList.append(busbar)
            except Exception as e:
                frontend_bus_id = bus_name_to_graph_id.get(matched_bus_id) or matched_bus_id.replace('_', '#')
                frontend_bus_name = BusbarsDictConnectionToName.get(matched_bus_id, matched_bus_id).replace('_', '#')
                busbarList.append(BusbarScOut(
                    name=frontend_bus_name,
                    id=frontend_bus_id,
                    ikss_ka=0.0,
                    ip_ka=0.0,
                    ith_ka=0.0,
                    rk_ohm=0.0,
                    xk_ohm=0.0
                ))

    except Exception as e:
        for bus_name in BusbarsDictConnectionToName.keys():
            frontend_bus_name = bus_name.replace('_', '#')
            frontend_bus_id = bus_name_to_graph_id.get(bus_name) or bus_name.replace('_', '#')
            busbarList.append(BusbarScOut(
                name=frontend_bus_name,
                id=frontend_bus_id,
                ikss_ka=0.0,
                ip_ka=0.0,
                ith_ka=0.0,
                rk_ohm=0.0,
                xk_ohm=0.0
            ))

    result = {"busbars": [vars(b) for b in busbarList]}
    return json.dumps(result, separators=(',', ':'))


def powerflow(in_data, frequency, mode, algorithm, loadmodel, max_iterations, tolerance, controlmode, export_commands=False):
    """Main powerflow function for OpenDSS
    
    Parameters based on OpenDSS documentation: https://opendss.epri.com/PowerFlow.html
    
    Args:
        in_data: Network element data
        frequency: Base frequency (50 or 60 Hz)
        mode: Solution mode (Snapshot, Daily, Dutycycle, Yearly, etc.)
        algorithm: Solution algorithm (Normal, Newton, NCIM)
        loadmodel: Load model (Powerflow=iterative with power injections, Admittance=direct solution)
        export_commands: Boolean flag to export OpenDSS commands to file
        max_iterations: Maximum number of iterations
        tolerance: Convergence tolerance
        controlmode: Control mode (Static, Event, Time)
    """
    
    # OpenDSSDirect.py is already imported as dss at the module level

    # Initialize list to collect OpenDSS commands if export is requested
    opendss_commands = []
    
    def execute_dss_command(command):
        """Execute DSS command and optionally collect it for export"""
        print(f"[OpenDSS] {command}")  # Log all commands
        dss.Text.Command(command)
        if export_commands:
            opendss_commands.append(command)
    
    # Set OpenDSS circuit parameters
    f = frequency
    
    # Create new circuit first - OpenDSS requires this before any other commands
    execute_dss_command('clear')
    execute_dss_command('New Circuit.OpenDSS_Circuit')
    execute_dss_command(f'set DefaultBaseFrequency={f}')

    # Set solution mode (Snapshot, Daily, Dutycycle, Yearly, etc.)
    # Reference: https://opendss.epri.com/PowerFlow.html
    execute_dss_command(f'set Mode={mode}')
    
    # Set solution algorithm (Normal, Newton, or NCIM)
    # Normal = fast current injection (default)
    # Newton = more robust for difficult circuits
    # NCIM = N-Node Current Injection Method for difficult transmission systems
    execute_dss_command(f'set Algorithm={algorithm}')
    
    # Set load model
    # Powerflow = iterative solution with power injections (default)
    # Admittance = direct solution with admittances
    execute_dss_command(f'set LoadModel={loadmodel}')
    
    # Set control mode
    # Static = no control actions (default)
    # Event = time-based controls
    # Time = continuous controls
    execute_dss_command(f'set ControlMode={controlmode}')
     
    # Set convergence parameters
    execute_dss_command(f'set MaxIterations={max_iterations}')
    execute_dss_command(f'set Tolerance={tolerance}')
  
    
    # Create busbars and other elements using helper functions
    # Wrap in try-except to catch validation errors and return them to frontend
    try:
        # Create busbars - this validates voltage values
        BusbarsDictVoltage, BusbarsDictConnectionToName = create_busbars(in_data, dss, export_commands, opendss_commands)

        # Create other elements
        (LinesDict, LinesDictId, LoadsDict, LoadsDictId, TransformersDict, TransformersDictId,
         ShuntsDict, ShuntsDictId, CapacitorsDict, CapacitorsDictId, GeneratorsDict, GeneratorsDictId,
         StoragesDict, StoragesDictId, PVSystemsDict, PVSystemsDictId, ExternalGridsDict, ExternalGridsDictId,
         circuit_source_element_name) = create_other_elements(in_data, dss, BusbarsDictVoltage, BusbarsDictConnectionToName, export_commands, opendss_commands, execute_dss_command)
    except ValueError as ve:
        # Validation error - return error message to frontend
        error_response = {
            "error": str(ve)
        }
        return json.dumps(error_response)
    except Exception as e:
        # Other errors during element creation
        error_response = {
            "error": f"Error creating network elements: {str(e)}"
        }
        return json.dumps(error_response)
    
    # Execute solve commands (voltage bases and calcv already run during element creation)
    try:
        print("[OpenDSS] solve")
        dss.Text.Command('solve')
    except Exception as e:
        pass
    # Check solve status
    try:
        converged = dss.Solution.Converged()
        if converged:
            pass
        else:
            pass
    except Exception as e:
        pass
    # Process results using the new output classes
    
    # Initialize result lists
    busbarList = []
    linesList = []
    loadsList = []
    transformersList = []
    shuntsList = []
    capacitorsList = []
    generatorsList = []
    storagesList = []
    pvsystemsList = []
    externalGridsList = []
    
    # Aggregate P and Q per bus from CktElement powers (for bus result boxes: P[MW], Q[MVAr], PF, Q/P)
    bus_pq_kw = {}  # bus_name_lower -> (p_kw, q_kvar)
    try:
        for is_pc in [False, True]:  # PDElements then PCElements
            idx = dss.Circuit.FirstPCElement() if is_pc else dss.Circuit.FirstPDElement()
            while idx > 0:
                try:
                    bus_names = dss.CktElement.BusNames()
                    powers = dss.CktElement.Powers()
                    if not bus_names or not powers:
                        idx = dss.Circuit.NextPCElement() if is_pc else dss.Circuit.NextPDElement()
                        continue
                    n_phases = dss.CktElement.NumPhases()
                    n_conductors = dss.CktElement.NumConductors()
                    n_terminals = dss.CktElement.NumTerminals()
                    # Powers() is [P1, Q1, P2, Q2, ...] per conductor (kW, kvar)
                    n_per_terminal = (n_conductors * 2) if n_conductors else (n_phases * 2)
                    for t in range(min(n_terminals, len(bus_names))):
                        bus_ref = bus_names[t]
                        bus_name_lower = bus_ref.split('.')[0].lower() if bus_ref else ''
                        if not bus_name_lower:
                            continue
                        p_kw = 0.0
                        q_kvar = 0.0
                        start = t * n_per_terminal
                        for i in range(0, min(n_per_terminal, len(powers) - start), 2):
                            p_kw += float(powers[start + i]) if start + i < len(powers) else 0.0
                            q_kvar += float(powers[start + i + 1]) if start + i + 1 < len(powers) else 0.0
                        if bus_name_lower not in bus_pq_kw:
                            bus_pq_kw[bus_name_lower] = [0.0, 0.0]
                        bus_pq_kw[bus_name_lower][0] += p_kw
                        bus_pq_kw[bus_name_lower][1] += q_kvar
                except Exception:
                    pass
                idx = dss.Circuit.NextPCElement() if is_pc else dss.Circuit.NextPDElement()
    except Exception:
        pass

    # Process bus results using actual OpenDSS data with proper symmetrical component calculation
    
    # Build a mapping from OpenDSS bus numbers to our bus IDs
    # OpenDSS internally uses numeric bus IDs, we need to map them back
    BusbarsDict = {}
    nBusbar = 0
    for bus_id in BusbarsDictConnectionToName.keys():
        BusbarsDict[bus_id] = nBusbar
        nBusbar += 1
    
    
    
    # Track which buses have been processed to avoid duplicates
    processed_buses = set()
    
    try:
        all_bus_names = dss.Circuit.AllBusNames()

        
        # Process all buses from OpenDSS circuit
        for bus_name_from_list in all_bus_names:
            # Set active bus using the name from the list
            dss.Circuit.SetActiveBus(bus_name_from_list)
            
            # Get the actual bus name (might be different from list name)
            actual_bus_name = dss.Bus.Name()
            
            # Debug: Print bus names to identify source buses (commented out for less verbose logging)
            # print(f"  Processing bus from list: '{bus_name_from_list}', actual name: '{actual_bus_name}'")
            
            # Skip sourcebus and source - OpenDSS's internal voltage source buses created by "New Circuit"
            # These are NOT the user's buses where External Grid VSources connect
            if (actual_bus_name.lower() in ['sourcebus', 'source'] or 
                bus_name_from_list.lower() in ['sourcebus', 'source']):
                continue
            
            # OpenDSS converts names to lowercase, so try to match against our expected buses (case-insensitive)
            matched_bus_id = None
            matched_bus_name = None
            
            # Try case-insensitive matching against our bus IDs
            for key, value in BusbarsDict.items():
                # OpenDSS lowercases names, so compare lowercase versions
                if key.lower() == actual_bus_name.lower():
                    matched_bus_id = key
                    matched_bus_name = BusbarsDictConnectionToName[key]
                    bus_number = value
                    # print(f"    ✓ Matched to user bus: {matched_bus_name}")  # Reduced logging
                    break
            
            if not matched_bus_id:
                continue
            
            # Skip if we've already processed this bus number
            if bus_number in processed_buses:
                continue
            
            processed_buses.add(bus_number)
            
            try:
                # Calculate positive sequence voltage using symmetrical components
                # This matches the notebook approach exactly
                voltages = dss.Bus.Voltages()  # in Volts: [Va_real, Va_imag, Vb_real, Vb_imag, Vc_real, Vc_imag]
                
                # Convert to kV and create complex numbers
                Va = complex(voltages[0]/1000, voltages[1]/1000)
                Vb = complex(voltages[2]/1000, voltages[3]/1000)
                Vc = complex(voltages[4]/1000, voltages[5]/1000)
                
                # Symmetrical component operator: a = e^(j*2π/3)
                a = complex(-0.5, math.sqrt(3)/2)
                a2 = complex(-0.5, -math.sqrt(3)/2)  # a² = e^(j*4π/3)
                
                # Positive sequence voltage: V1 = (Va + a*Vb + a²*Vc) / 3
                V1 = (Va + a * Vb + a2 * Vc) / 3
                V1_mag_ln_kv = abs(V1)  # Magnitude in kV (line-to-neutral)
                
                # Convert to line-to-line voltage
                V1_mag_ll_kv = V1_mag_ln_kv * math.sqrt(3)
                
                # Use the user-specified base voltage from input data (not OpenDSS's internal base)
                # This is the vn_kv from the bus definition
                base_kv_user = BusbarsDictVoltage.get(matched_bus_id)
                
                if base_kv_user is not None:
                    # User specified voltage in L-L format
                    base_kv = float(base_kv_user)
                else:
                    # Fallback to OpenDSS's base voltage
                    base_kv_ln = dss.Bus.kVBase()
                    base_kv = base_kv_ln * math.sqrt(3)  # Convert L-N to L-L
                
                # Calculate per-unit based on user-specified base voltage
                vm_pu = V1_mag_ll_kv / base_kv if base_kv > 0 else 1.0
                
                # Get angle from vmag_angle_pu
                va_degree = dss.Bus.puVmagAngle()[1] if len(dss.Bus.puVmagAngle()) > 1 else 0.0
                
                # P, Q, PF, Q/P for bus result box (from aggregated bus power)
                p_mw = None
                q_mvar = None
                pf = None
                q_p = None
                pq = bus_pq_kw.get(matched_bus_id.lower())
                if pq is not None:
                    p_kw, q_kvar = pq[0], pq[1]
                    p_mw = p_kw / 1000.0
                    q_mvar = q_kvar / 1000.0
                    s = math.sqrt(p_kw * p_kw + q_kvar * q_kvar)
                    pf = (p_kw / s) if s > 0 else None
                    q_p = (q_kvar / p_kw) if p_kw != 0 else None
                
                # Use name/id as stored (underscore format to match pandapower/frontend)
                frontend_bus_id = matched_bus_id
                frontend_bus_name = matched_bus_name
                busbar = BusbarOut(
                    name=frontend_bus_name,
                    id=frontend_bus_id,
                    vm_pu=vm_pu,
                    va_degree=va_degree,
                    p_mw=p_mw,
                    q_mvar=q_mvar,
                    pf=pf,
                    q_p=q_p
                )
                busbarList.append(busbar)
                # print(f"    ✓ Added to results: {frontend_bus_name} (vm_pu={vm_pu:.6f}, va_degree={va_degree:.6f})")  # Reduced logging
                
            except Exception as e:
                # Add with default values - use name/id as stored
                frontend_bus_id = matched_bus_id
                frontend_bus_name = matched_bus_name
                busbar = BusbarOut(
                    name=frontend_bus_name,
                    id=frontend_bus_id,
                    vm_pu=1.0,
                    va_degree=0.0,
                    p_mw=None,
                    q_mvar=None,
                    pf=None,
                    q_p=None
                )
                busbarList.append(busbar)
                
    except Exception as e:
        # Fallback to default processing if OpenDSS bus access fails
        for bus_name in BusbarsDictConnectionToName.keys():
            try:
                vm_pu = 1.0
                va_degree = 0.0
                pq = bus_pq_kw.get(bus_name.lower()) if bus_pq_kw else None
                p_mw = (pq[0] / 1000.0) if pq else None
                q_mvar = (pq[1] / 1000.0) if pq else None
                pf = None
                q_p = None
                if pq and (pq[0] != 0 or pq[1] != 0):
                    s = math.sqrt(pq[0] * pq[0] + pq[1] * pq[1])
                    pf = (pq[0] / s) if s > 0 else None
                    q_p = (pq[1] / pq[0]) if pq[0] != 0 else None
                # Use name/id as stored (underscore format to match pandapower/frontend)
                frontend_bus_name = bus_name
                frontend_bus_id = bus_name
                busbar = BusbarOut(
                    name=frontend_bus_name,
                    id=frontend_bus_id,
                    vm_pu=vm_pu,
                    va_degree=va_degree,
                    p_mw=p_mw,
                    q_mvar=q_mvar,
                    pf=pf,
                    q_p=q_p
                )
                busbarList.append(busbar)
                
            except Exception as e2:
                continue
    
    # Process line results - iterate through ALL lines we created (not just OpenDSS's active ones)
    # This ensures we get results for disabled lines too (with zero values)
    
    for key, line_name in LinesDict.items():
        try:
            # Set the active element
            dss.Circuit.SetActiveElement(f"Line.{line_name}")
            
            # Check if the line is enabled
            is_enabled = dss.CktElement.Enabled()
            
            if is_enabled:
                # Get powers (in kW and kvar) - sum all three phases
                powers = dss.CktElement.Powers()
                if len(powers) >= 12:
                    # From side: phases 1, 2, 3
                    p_from_mw = (powers[0] + powers[2] + powers[4]) / 1000.0
                    q_from_mvar = (powers[1] + powers[3] + powers[5]) / 1000.0
                    # To side: phases 1, 2, 3
                    p_to_mw = (powers[6] + powers[8] + powers[10]) / 1000.0
                    q_to_mvar = (powers[7] + powers[9] + powers[11]) / 1000.0
                else:
                    p_from_mw = p_to_mw = q_from_mvar = q_to_mvar = 0.0

                # Get currents (in A) - use magnitude from currents_mag_ang
                currents = dss.CktElement.CurrentsMagAng()
                if len(currents) >= 12:
                    # Current magnitude is at index 0, 6 for from and to sides
                    i_from_ka = currents[0] / 1000.0  # Convert A to kA
                    i_to_ka = currents[6] / 1000.0
                else:
                    i_from_ka = i_to_ka = 0.0
            else:
                # Line is disabled - report zero values
                p_from_mw = p_to_mw = q_from_mvar = q_to_mvar = 0.0
                i_from_ka = i_to_ka = 0.0

            # Calculate loading percentage using max_i_ka from input data
            loading_percent = 0.0
            # Find the line in input data to get max_i_ka
            max_i_ka = None
            for data_key, data_value in in_data.items():
                if data_value.get('name') == key and 'Line' in data_value.get('typ', ''):
                    max_i_ka_raw = data_value.get('max_i_ka')
                    if max_i_ka_raw is not None:
                        max_i_ka = float(max_i_ka_raw)
                    break
            
            if max_i_ka and max_i_ka > 0 and is_enabled:
                loading_percent = (i_from_ka / max_i_ka) * 100
            else:
                # Fallback if max_i_ka not available or line is disabled
                loading_percent = 0.0

            # Convert IDs back to hash format for frontend
            frontend_name = key
            frontend_id = LinesDictId[key]
            
            line = LineOut(
                name=frontend_name, 
                id=frontend_id, 
                p_from_mw=p_from_mw, 
                q_from_mvar=q_from_mvar, 
                p_to_mw=p_to_mw, 
                q_to_mvar=q_to_mvar, 
                i_from_ka=i_from_ka, 
                i_to_ka=i_to_ka, 
                loading_percent=loading_percent
            )
            linesList.append(line)
            
        except Exception as e:
            # Still add the line to results with zero values
            try:
                frontend_name = key
                frontend_id = LinesDictId[key]
                line = LineOut(
                    name=frontend_name, 
                    id=frontend_id, 
                    p_from_mw=0.0, 
                    q_from_mvar=0.0, 
                    p_to_mw=0.0, 
                    q_to_mvar=0.0, 
                    i_from_ka=0.0, 
                    i_to_ka=0.0, 
                    loading_percent=0.0
                )
                linesList.append(line)
            except:
                pass
    
    
    # Process load results - iterate through ALL loads we created
    
    for key, load_name in LoadsDict.items():
        try:
            # Set the active element
            dss.Circuit.SetActiveElement(f"Load.{load_name}")
            
            # Check if the load is enabled
            is_enabled = dss.CktElement.Enabled()
            
            if is_enabled:
                powers = dss.CktElement.Powers()
                if len(powers) >= 6:
                    p_raw = powers[0] + powers[2] + powers[4]
                    q_raw = powers[1] + powers[3] + powers[5]
                    p_mw = p_raw / 1000.0 if not math.isnan(p_raw) else 0.0
                    q_mvar = q_raw / 1000.0 if not math.isnan(q_raw) else 0.0
                else:
                    p_mw = q_mvar = 0.0
            else:
                # Load is disabled - report zero values
                p_mw = q_mvar = 0.0

            # Convert IDs back to hash format
            frontend_name = key
            frontend_id = LoadsDictId[key]
            
            load = LoadOut(name=frontend_name, id=frontend_id, p_mw=p_mw, q_mvar=q_mvar)
            loadsList.append(load)
                            
        except Exception as e:
            # Still add the load to results with zero values
            try:
                frontend_name = key
                frontend_id = LoadsDictId[key]
                load = LoadOut(name=frontend_name, id=frontend_id, p_mw=0.0, q_mvar=0.0)
                loadsList.append(load)
            except:
                pass
    
    
    # Process static generators (created as Generator elements) - iterate through ALL generators we created
    
    for key, gen_name in GeneratorsDict.items():
        try:
            # Set this Generator as the active circuit element (static generators are created as Generator, not PVSystem)
            dss.Circuit.SetActiveElement(f"Generator.{gen_name}")
            
            # Check if the generator is enabled
            is_enabled = dss.CktElement.Enabled()
            
            if is_enabled:
                # Get generator powers (solution values; Model 1 = constant P,Q so these match setpoint)
                powers = dss.CktElement.Powers()
                if len(powers) >= 6:
                    # Sum all three phases (powers come in pairs: P1,Q1,P2,Q2,P3,Q3)
                    p_raw = powers[0] + powers[2] + powers[4]
                    q_raw = powers[1] + powers[3] + powers[5]
                    # Generator reports power flowing OUT as NEGATIVE (generation into grid)
                    # Negate to show positive generation in results
                    p_mw = -(p_raw / 1000.0) if not math.isnan(p_raw) else 0.0
                    q_mvar = -(q_raw / 1000.0) if not math.isnan(q_raw) else 0.0
                else:
                    p_mw = q_mvar = 0.0

                # Get voltage from bus (use CktElement so it works for Generator)
                vm_pu = 1.0
                va_degree = 0.0
                try:
                    bus_names = dss.CktElement.BusNames()
                    gen_bus_name = bus_names[0].split('.')[0] if bus_names else None
                    bus_index = None
                    if gen_bus_name:
                        for i in range(dss.Circuit.NumBuses()):
                            dss.Circuit.SetActiveBus(i)
                            if dss.Bus.Name().lower() == gen_bus_name.lower():
                                bus_index = i
                                break
                    if bus_index is not None:
                        dss.Circuit.SetActiveBus(bus_index)
                        bus_angles = dss.Bus.puVmagAngle()
                        if len(bus_angles) >= 2:
                            vm_pu = bus_angles[0] if not math.isnan(bus_angles[0]) else 1.0
                            va_degree = bus_angles[1] if not math.isnan(bus_angles[1]) else 0.0
                except Exception as e:
                    pass
            else:
                # Generator is disabled - report zero values
                p_mw = q_mvar = 0.0
                vm_pu = 1.0
                va_degree = 0.0

            # Convert IDs back to hash format
            frontend_name = key
            frontend_id = GeneratorsDictId[key]
            
            generator = GeneratorOut(
                name=frontend_name, 
                id=frontend_id, 
                p_mw=p_mw, 
                q_mvar=q_mvar, 
                va_degree=va_degree, 
                vm_pu=vm_pu
            )
            generatorsList.append(generator)
            # print(f"    ✓ Added Generator (static generator): {frontend_name}, P={p_mw:.3f} MW, Q={q_mvar:.3f} MVAr, V={vm_pu:.3f} pu")  # Reduced logging
                        
        except Exception as e:
            # Still add the generator to results with zero values
            try:
                frontend_name = key
                frontend_id = GeneratorsDictId[key]
                generator = GeneratorOut(
                    name=frontend_name, 
                    id=frontend_id, 
                    p_mw=0.0, 
                    q_mvar=0.0, 
                    va_degree=0.0, 
                    vm_pu=1.0
                )
                generatorsList.append(generator)
            except:
                pass
    
    
    # Process transformer results - iterate through ALL transformers we created
   
    
    for key, trafo_name in TransformersDict.items():
        try:
            # Set the active element
            dss.Circuit.SetActiveElement(f"Transformer.{trafo_name}")
            
            # Check if the transformer is enabled
            is_enabled = dss.CktElement.Enabled()
            
            if is_enabled:
                # Get powers (in kW and kvar) for transformer
                powers = dss.CktElement.Powers()
                # Initialize power values
                p_hv_mw = q_hv_mvar = p_lv_mw = q_lv_mvar = pl_mw = ql_mvar = 0.0
                
                if len(powers) >= 12:
                    # Debug: Print per-phase powers for detailed analysis

                    # HV side (Terminal 1): phases 1, 2, 3
                    p_hv_kw = powers[0] + powers[2] + powers[4]
                    q_hv_kvar = powers[1] + powers[3] + powers[5]
                    # LV side (Terminal 2): phases 1, 2, 3
                    p_lv_kw = powers[8] + powers[10] + powers[12]
                    q_lv_kvar = powers[9] + powers[11] + powers[13]
                    
                    # Convert to MW/MVAr
                    p_hv_mw = p_hv_kw / 1000.0 if not math.isnan(p_hv_kw) else 0.0
                    q_hv_mvar = q_hv_kvar / 1000.0 if not math.isnan(q_hv_kvar) else 0.0
                    p_lv_mw = p_lv_kw / 1000.0 if not math.isnan(p_lv_kw) else 0.0
                    q_lv_mvar = q_lv_kvar / 1000.0 if not math.isnan(q_lv_kvar) else 0.0
                    
                    # Try to get losses directly from OpenDSS
                    try:
                        losses_direct = dss.CktElement.Losses()
                        if len(losses_direct) >= 2:
                            # OpenDSS returns losses in Watts (W), not kW
                            pl_direct_w = losses_direct[0]
                            ql_direct_var = losses_direct[1]
                       
                            # Convert from Watts to MW (divide by 1,000,000)
                            pl_mw = pl_direct_w / 1e6
                            ql_mvar = ql_direct_var / 1e6
                         
                        else:
                            raise ValueError("Losses array too short")
                    except Exception as e:
                        # Fallback: Calculate losses using power balance
                        # With OpenDSS convention: positive = into terminal, negative = out of terminal
                        # Losses = P_terminal1 + P_terminal2 (algebraic sum)
                        pl_mw = p_hv_mw + p_lv_mw
                        ql_mvar = q_hv_mvar + q_lv_mvar
                    
                
                # Get complex currents [I1_real, I1_imag, I2_real, I2_imag, I3_real, I3_imag, ...] in Amperes
                currents = dss.CktElement.Currents()
                
                if len(currents) >= 12:
                    # Terminal 1 (HV): Calculate magnitude for each phase
                    i1_hv = math.sqrt(currents[0]**2 + currents[1]**2)  # Phase 1
                    i2_hv = math.sqrt(currents[2]**2 + currents[3]**2)  # Phase 2
                    i3_hv = math.sqrt(currents[4]**2 + currents[5]**2)  # Phase 3
                    i_hv_ka = (i1_hv + i2_hv + i3_hv) / 3 / 1000  # Average magnitude in kA
                    
                    # Terminal 2 (LV): Calculate magnitude for each phase
                    i1_lv = math.sqrt(currents[6]**2 + currents[7]**2)   # Phase 1
                    i2_lv = math.sqrt(currents[8]**2 + currents[9]**2)   # Phase 2
                    i3_lv = math.sqrt(currents[10]**2 + currents[11]**2) # Phase 3
                    i_lv_ka = (i1_lv + i2_lv + i3_lv) / 3 / 1000  # Average magnitude in kA
                else:
                    i_hv_ka = i_lv_ka = 0.0

                # Calculate loading percentage based on rated current
                # Get transformer rating - prefer original input data over OpenDSS reported value
                try:
                    # First, try to get the original rating from input data (most reliable)
                    sn_mva = None
                    if in_data:
                        element_data = None
                        # Search through all elements in in_data
                        # in_data structure: keys are arbitrary, elements have 'typ' and 'name' fields
                        for elem_key, elem_data in in_data.items():
                            if isinstance(elem_data, dict):
                                elem_type = elem_data.get('typ', '')  # Note: 'typ' not 'element_type'
                                elem_name = elem_data.get('name', '')
                                elem_id = elem_data.get('id', '')
                                
                                # Match transformer by type and name/id
                                if elem_type == 'Transformer':
                                    # Match by name (most reliable)
                                    if elem_name == trafo_name or elem_name == key:
                                        element_data = elem_data
                                        break
                                    # Also try matching by ID
                                    elif elem_id == TransformersDictId.get(key, ''):
                                        element_data = elem_data
                                        break
                        
                        if element_data:
                            sn_mva_raw = element_data.get('sn_mva')
                            if sn_mva_raw is not None:
                                sn_mva = float(sn_mva_raw)
                            else:
                                pass
                        else:
                            # Debug: show what transformers ARE in in_data
                            transformer_keys_found = []
                            for elem_key, elem_data in in_data.items():
                                if isinstance(elem_data, dict) and elem_data.get('typ', '') == 'Transformer':
                                    transformer_keys_found.append(f"{elem_key}: name={elem_data.get('name', 'N/A')}, id={elem_data.get('id', 'N/A')}")
                            if transformer_keys_found:
                                pass
                    # Fallback to OpenDSS reported value if original not available
                    if sn_mva is None:
                        sn_kva_reported = dss.Transformers.kVA()
                        sn_mva = sn_kva_reported / 1000.0
                    
                    # Get HV voltage from first winding
                    dss.Transformers.Wdg(1)
                    vn_hv_kv = dss.Transformers.kV()
                    
                    
                    # Get number of phases from transformer properties
                    try:
                        num_phases = dss.Transformers.Phases()
                    except:
                        # Fallback: assume 3-phase if not available
                        num_phases = 3
                    
                    
                    # Calculate loading using two methods and use the most reasonable one
                    
                    # METHOD 1: Current-based loading
                    # I_rated = S / (sqrt(3) * V_LL) for 3-phase
                    # For single-phase: I_rated = S / V
                    if num_phases == 3:
                        i_rated_hv_ka = sn_mva / (math.sqrt(3) * vn_hv_kv)
                    else:
                        i_rated_hv_ka = sn_mva / vn_hv_kv
                    
                    loading_by_current = (i_hv_ka / i_rated_hv_ka * 100.0) if i_rated_hv_ka > 0 else 0.0
                    
                    # METHOD 2: Power-based loading (MVA method)
                    # Calculate actual apparent power from HV side (use absolute values for magnitude)
                    # P and Q can be negative (power flow direction), but for loading we need magnitude
                    p_hv_abs = abs(p_hv_mw)
                    q_hv_abs = abs(q_hv_mvar)
                    s_actual_mva = math.sqrt(p_hv_abs**2 + q_hv_abs**2)
                    loading_by_power = (s_actual_mva / sn_mva * 100.0) if sn_mva > 0 else 0.0
                    
                    
                    # Use power-based loading (more reliable for transformers)
                    loading_percent = loading_by_power
                except Exception as e:
                    loading_percent = 0.0
            else:
                # Transformer is disabled - report zero values
                p_hv_mw = q_hv_mvar = p_lv_mw = q_lv_mvar = pl_mw = ql_mvar = 0.0
                i_hv_ka = i_lv_ka = 0.0
                loading_percent = 0.0

            # Convert IDs back to hash format for frontend
            frontend_name = key
            frontend_id = TransformersDictId[key]
            
            transformer = TransformerOut(
                name=frontend_name, 
                id=frontend_id, 
                i_hv_ka=i_hv_ka, 
                i_lv_ka=i_lv_ka, 
                loading_percent=loading_percent,
                p_hv_mw=p_hv_mw,
                q_hv_mvar=q_hv_mvar,
                p_lv_mw=p_lv_mw,
                q_lv_mvar=q_lv_mvar,
                pl_mw=pl_mw,
                ql_mvar=ql_mvar
            )
            transformersList.append(transformer)
                        
        except Exception as e:
            # Still add the transformer to results with zero values
            try:
                frontend_name = key
                frontend_id = TransformersDictId[key]
                transformer = TransformerOut(
                    name=frontend_name, 
                    id=frontend_id, 
                    i_hv_ka=0.0, 
                    i_lv_ka=0.0, 
                    loading_percent=0.0,
                    p_hv_mw=0.0,
                    q_hv_mvar=0.0,
                    p_lv_mw=0.0,
                    q_lv_mvar=0.0,
                    pl_mw=0.0,
                    ql_mvar=0.0
                )
                transformersList.append(transformer)
            except:
                pass
    
  
    
    # Process capacitor results
    if dss.Capacitors.Count() > 0:
        dss.Capacitors.First()
        for _ in range(dss.Capacitors.Count()):
            try:
                cap_name = dss.Capacitors.Name()
                for key, value in CapacitorsDict.items():
                    # OpenDSS lowercases names, so compare case-insensitively
                    if value.lower() == cap_name.lower() or key.lower() == cap_name.lower():
                        try:
                            powers = dss.CktElement.Powers()
                            if len(powers) >= 6:
                                p_raw = powers[0] + powers[2] + powers[4]
                                q_raw = powers[1] + powers[3] + powers[5]
                                p_mw = p_raw / 1000.0 if not math.isnan(p_raw) else 0.0
                                q_mvar = q_raw / 1000.0 if not math.isnan(q_raw) else 0.0
                            else:
                                p_mw = q_mvar = 0.0

                            # Get voltage value from the capacitor's bus
                            vm_pu = 1.0
                            try:
                                # Set the active bus to the capacitor's bus to get voltage value
                                # Note: We need to find the bus index for this capacitor
                                # For now, using default value until we can map capacitor to bus
                                bus_angles = dss.Bus.puVmagAngle()
                                if len(bus_angles) >= 1:
                                    vm_pu = bus_angles[0] if not math.isnan(bus_angles[0]) else 1.0
                            except Exception as e:
                                pass
                            # Convert IDs back to hash format for frontend
                            frontend_name = key
                            frontend_id = CapacitorsDictId[key]
                            
                            capacitor = CapacitorOut(
                                name=frontend_name, 
                                id=frontend_id, 
                                p_mw=p_mw, 
                                q_mvar=q_mvar, 
                                vm_pu=vm_pu
                            )
                            capacitorsList.append(capacitor)
                            break
                        except Exception as e:
                            continue
            except Exception as e:
                pass
            dss.Capacitors.Next()
    
    # Process shunt results (reactors in OpenDSS)
    # Use alternative method if dss.reactors is not available
    
    try:
        # Process each expected shunt directly by setting it as active element
        if ShuntsDict:
            for key, value in ShuntsDict.items():
                # value is OpenDSS element name (ShuntReactor_xxx for Reactor element)
                dss_elem_name = value
                try:
                    # Shunt reactors are modeled as Reactor element; try Reactor first, then legacy Generator
                    try:
                        dss.Circuit.SetActiveElement(f"Reactor.{dss_elem_name}")
                    except Exception:
                        try:
                            dss.Circuit.SetActiveElement(f"Reactor.{dss_elem_name.lower()}")
                        except Exception:
                            try:
                                dss.Circuit.SetActiveElement(f"Generator.{dss_elem_name}")
                            except Exception:
                                try:
                                    dss.Circuit.SetActiveElement(f"Generator.{dss_elem_name.lower()}")
                                except Exception:
                                    try:
                                        dss.Circuit.SetActiveElement(f"Load.{dss_elem_name}")
                                    except Exception:
                                        pass
                    
                    # Get element info
                    element_name = dss.CktElement.Name()
                    
                    # Get powers
                    powers = dss.CktElement.Powers()
                    
                    # Reactors can be single-phase or three-phase
                    if len(powers) >= 6:
                        # Three-phase reactor
                        p_raw = powers[0] + powers[2] + powers[4]
                        q_raw = powers[1] + powers[3] + powers[5]
                    elif len(powers) >= 2:
                        # Single-phase reactor
                        p_raw = powers[0]
                        q_raw = powers[1]
                    else:
                        p_raw = 0.0
                        q_raw = 0.0
                    
                    # Convert to MW/MVar and handle NaN
                    p_mw = (p_raw / 1000.0) if (not math.isnan(p_raw) and not math.isinf(p_raw)) else 0.0
                    q_mvar = (q_raw / 1000.0) if (not math.isnan(q_raw) and not math.isinf(q_raw)) else 0.0
                    

                    # Get voltage value from the shunt's bus using user-specified base voltage
                    vm_pu = 1.0
                    try:
                        # Get the bus that this shunt is connected to
                        bus_names = dss.CktElement.BusNames()
                        if len(bus_names) > 0:
                            bus_name = bus_names[0].split('.')[0]  # Remove phase info
                            dss.Circuit.SetActiveBus(bus_name)
                            # Get actual voltage in kV (line-to-line)
                            voltages = dss.Bus.Voltages()  # in Volts
                            if len(voltages) >= 6:
                                Va = complex(voltages[0]/1000, voltages[1]/1000)
                                Vb = complex(voltages[2]/1000, voltages[3]/1000)
                                Vc = complex(voltages[4]/1000, voltages[5]/1000)
                                # Positive sequence L-L voltage
                                a = complex(-0.5, math.sqrt(3)/2)
                                a2 = complex(-0.5, -math.sqrt(3)/2)
                                V1 = (Va + a * Vb + a2 * Vc) / 3
                                V1_ll_kv = abs(V1) * math.sqrt(3)
                                # Use user-specified base voltage
                                base_kv = BusbarsDictVoltage.get(bus_name.lower()) or BusbarsDictVoltage.get(bus_name)
                                if base_kv:
                                    vm_pu = V1_ll_kv / float(base_kv)
                    except Exception as e:
                        pass

                    # Convert IDs back to hash format for frontend
                    frontend_name = key
                    frontend_id = ShuntsDictId[key]
                    
                    shunt = ShuntOut(
                        name=frontend_name, 
                        id=frontend_id, 
                        p_mw=p_mw, 
                        q_mvar=q_mvar, 
                        vm_pu=vm_pu
                    )
                    shuntsList.append(shunt)
                    
                except Exception as e:
                    continue
        else:
            pass
    except Exception as e:
        pass
    # Process storage results
    if hasattr(dss, 'Storages') and dss.Storages.Count() > 0:
        dss.Storages.First()
        for _ in range(dss.Storages.Count()):
            try:
                storage_name = dss.Storages.Name()
                for key, value in StoragesDict.items():
                    # OpenDSS lowercases names, so compare case-insensitively
                    if value.lower() == storage_name.lower() or key.lower() == storage_name.lower():
                        try:
                            powers = dss.CktElement.Powers()
                            if len(powers) >= 6:
                                p_raw = powers[0] + powers[2] + powers[4]
                                q_raw = powers[1] + powers[3] + powers[5]
                                p_mw = p_raw / 1000.0 if not math.isnan(p_raw) else 0.0
                                q_mvar = q_raw / 1000.0 if not math.isnan(q_raw) else 0.0
                            else:
                                p_mw = q_mvar = 0.0

                            # Convert IDs back to hash format for frontend
                            frontend_name = key
                            frontend_id = StoragesDictId[key]
                            
                            storage = StorageOut(
                                name=frontend_name, 
                                id=frontend_id, 
                                p_mw=p_mw, 
                                q_mvar=q_mvar
                            )
                            storagesList.append(storage)
                            break
                        except Exception as e:
                            continue
                    else:
                        pass
            except Exception as e:
                pass
            dss.Storages.Next()

    # Process PVSystem results (matching notebook approach)
    if hasattr(dss, 'PVsystems'):
        if dss.PVsystems.Count() > 0:
            dss.PVsystems.First()
            for _ in range(dss.PVsystems.Count()):
                try:
                    pvsystem_name = dss.PVsystems.Name()
                    
                    for key, value in PVSystemsDict.items():
                        # OpenDSS lowercases names, so compare case-insensitively
                        if value.lower() == pvsystem_name.lower() or key.lower() == pvsystem_name.lower():
                            try:
                                # Get powers (in kW and kvar) - sum all three phases
                                powers = dss.CktElement.Powers()
                                if len(powers) >= 6:
                                    p_mw = (powers[0] + powers[2] + powers[4]) / 1000.0
                                    q_mvar = (powers[1] + powers[3] + powers[5]) / 1000.0
                                else:
                                    p_mw = q_mvar = 0.0

                                # Get voltage value from the PVSystem's bus
                                vm_pu = 1.0
                                va_degree = 0.0
                                irradiance = 1.0
                                temperature = 25.0
                                
                                try:
                                    # Get irradiance and temperature from PVSystem properties
                                    if hasattr(dss.PVsystems, 'Irradiance'):
                                        irradiance = dss.PVsystems.Irradiance()
                                    if hasattr(dss.PVsystems, 'Pmpp'):
                                        temperature = 25  # Default temperature if not available

                                    # Get voltage from current bus using bus voltage array
                                    bus_angles = dss.Bus.puVmagAngle()
                                    if len(bus_angles) >= 1:
                                        vm_pu = bus_angles[0] if not math.isnan(bus_angles[0]) else 1.0
                                        va_degree = bus_angles[1] if len(bus_angles) > 1 else 0.0
                                except Exception as e:
                                    pass

                                # Convert IDs back to hash format for frontend
                                frontend_name = key
                                frontend_id = PVSystemsDictId[key]
                                
                                pvsystem = PVSystemOut(
                                    name=frontend_name,
                                    id=frontend_id,
                                    p_mw=p_mw,
                                    q_mvar=q_mvar,
                                    vm_pu=vm_pu,
                                    va_degree=va_degree,
                                    irradiance=irradiance,
                                    temperature=temperature
                                )
                                pvsystemsList.append(pvsystem)
                                break
                            except Exception as e:
                                continue
                except Exception as e:
                    pass
                dss.PVsystems.Next()
        
    else:
        pass
    # Process external grid results (deduplicate by matched_key so each grid appears once)
    added_external_grid_keys = set()
    if hasattr(dss, 'Vsources') and dss.Vsources.Count() > 0:
        dss.Vsources.First()
        for _ in range(dss.Vsources.Count()):
            try:
                vsource_name = dss.Vsources.Name()

                matched_key = None
                if vsource_name.lower() in ['source', 'sourcebus']:
                    # The default circuit source was configured with the first external
                    # grid's parameters via "Edit Vsource.source". Map it back.
                    if circuit_source_element_name:
                        matched_key = circuit_source_element_name
                    else:
                        # No external grid mapped to circuit source; skip
                        dss.Vsources.Next()
                        continue
                else:
                    # Try to find matching external grid by checking various name formats (case-insensitive)
                    for key, value in ExternalGridsDict.items():
                        # OpenDSS lowercases names, so compare case-insensitively
                        if (value.lower() == vsource_name.lower() or key.lower() == vsource_name.lower()):
                            matched_key = key
                            break

                if matched_key and matched_key not in added_external_grid_keys:
                    added_external_grid_keys.add(matched_key)
                    try:
                        powers = dss.CktElement.Powers()
                        if len(powers) >= 6:
                            p_raw = powers[0] + powers[2] + powers[4]
                            q_raw = powers[1] + powers[3] + powers[5]
                            # OpenDSS uses Passive Sign Convention: positive = power INTO component (consumption)
                            # Frontend convention: positive = power FROM source (generation/supply)
                            # Therefore, we need to negate the values to match frontend convention
                            p_mw = -(p_raw / 1000.0) if not math.isnan(p_raw) else 0.0
                            q_mvar = -(q_raw / 1000.0) if not math.isnan(q_raw) else 0.0
                        else:
                            p_mw = q_mvar = 0.0

                        # Calculate power factor (use absolute values for magnitude)
                        pf = 1.0
                        if p_mw != 0 or q_mvar != 0:
                            s_mva = math.sqrt(p_mw**2 + q_mvar**2)
                            if s_mva > 0:
                                pf = abs(p_mw) / s_mva

                        # Calculate Q/P ratio
                        q_p = 0.0
                        if p_mw != 0:
                            q_p = q_mvar / p_mw

                        # Use name/id as stored (underscore format to match pandapower/frontend)
                        frontend_name = matched_key
                        frontend_id = ExternalGridsDictId[matched_key]
                        
                        externalGrid = ExternalGridOut(
                            name=frontend_name,
                            id=frontend_id,
                            p_mw=p_mw,
                            q_mvar=q_mvar,
                            pf=pf,
                            q_p=q_p
                        )
                        externalGridsList.append(externalGrid)
                    except Exception as e:
                        pass
            except Exception as e:
                pass
            dss.Vsources.Next()
    
    # Build final result using simplified structure (no output classes)
    result = {}
    
    if busbarList:
        result['busbars'] = busbarList
    if linesList:
        result['lines'] = linesList
    if loadsList:
        result['loads'] = loadsList
    if transformersList:
        result['transformers'] = transformersList
    if shuntsList:
        result['shunts'] = shuntsList
    if capacitorsList:
        result['capacitors'] = capacitorsList
    if generatorsList:
        result['generators'] = generatorsList
    if storagesList:
        result['storages'] = storagesList
    if pvsystemsList:
        result['pvsystems'] = pvsystemsList
    if externalGridsList:
        result['externalgrids'] = externalGridsList
    

    # Add OpenDSS commands to result if export was requested
    if export_commands and opendss_commands:
        commands_text = '\n'.join(opendss_commands)
        result['opendss_commands'] = commands_text

    # Custom JSON encoder to handle NaN values
    def safe_json_serializer(obj):
        if hasattr(obj, '__dict__'):
            result_dict = {}
            for key, value in obj.__dict__.items():
                if isinstance(value, float) and math.isnan(value):
                    result_dict[key] = 0.0
                elif isinstance(value, list):
                    result_dict[key] = [safe_json_serializer(item) for item in value]
                else:
                    result_dict[key] = safe_json_serializer(value) if hasattr(value, '__dict__') else value
            return result_dict
        elif isinstance(obj, float) and math.isnan(obj):
            return 0.0
        elif isinstance(obj, list):
            return [safe_json_serializer(item) for item in obj]
        else:
            return obj

    try:
        # Optimized: Remove indent=4 to reduce payload size by ~40%
        response = json.dumps(result, default=safe_json_serializer, separators=(',', ':'))
        
        return response
    except Exception as json_error:
        return json.dumps({"error": "JSON serialization failed", "message": str(json_error)}, separators=(',', ':'))
        
        #U[pu],angle[degree]
        #print(dss.Bus.puVmagAngle())    
        #dss.Circuit.SetActiveElement(dss.bus.name)
        #print(dss.CktElement.Powers())
        #print(dss.circuit.total_power)
    #P[MW]
    #Q[MVar]
    #PF
        
        
def harmonic_analysis(in_data, frequency, mode, algorithm, loadmodel, max_iterations,
                      tolerance, controlmode, harmonics, neglect_load_y=False,
                      export_commands=False):
    """
    Perform OpenDSS harmonic analysis with full per-bus / per-line results.

    Workflow (per OpenDSS docs):
    1. Build the circuit, run a snapshot power flow to initialise.
    2. Read fundamental (h=1) bus voltages as baseline for per-unit.
    3. For each requested harmonic order, set frequency, solve in Direct
       mode, and read bus voltages + line currents.
    4. Compute VTHD per bus and ITHD per line.
    5. Return everything in the same JSON envelope that the frontend
       already knows (busbars, lines, etc.) plus a new
       ``harmonic_analysis`` block with per-element detail.
    """    # ---- Parse harmonic orders ------------------------------------------------
    harmonic_orders = []
    if isinstance(harmonics, str):
        for token in harmonics.replace(';', ',').split(','):
            token = token.strip()
            if not token:
                continue
            try:
                h = int(token)
                if h > 0:
                    harmonic_orders.append(h)
            except ValueError:
                continue
    elif isinstance(harmonics, (list, tuple)):
        for h in harmonics:
            try:
                h_int = int(h)
                if h_int > 0:
                    harmonic_orders.append(h_int)
            except (TypeError, ValueError):
                continue
    if not harmonic_orders:
        harmonic_orders = [3, 5, 7, 11, 13]

    # ---- Step 1: run fundamental power flow (reuse existing function) ---------
    base_result_json = powerflow(
        in_data, frequency, mode, algorithm, loadmodel,
        max_iterations, tolerance, controlmode, export_commands
    )
    try:
        base_result = json.loads(base_result_json)
    except Exception:
        return base_result_json
    if "error" in base_result:
        return base_result_json

    # ---- Step 2: rebuild circuit for harmonic analysis -------------------------
    opendss_commands = []

    def execute_dss_command(command):
        print(f"[OpenDSS][HARMONICS] {command}")
        dss.Text.Command(command)
        if export_commands:
            opendss_commands.append(command)

    execute_dss_command('clear')
    execute_dss_command('New Circuit.OpenDSS_Circuit_Harmonics')
    execute_dss_command(f'set DefaultBaseFrequency={frequency}')
    execute_dss_command(f'set Mode={mode}')
    execute_dss_command(f'set Algorithm={algorithm}')
    execute_dss_command(f'set LoadModel={loadmodel}')
    execute_dss_command(f'set ControlMode={controlmode}')
    execute_dss_command(f'set MaxIterations={max_iterations}')
    execute_dss_command(f'set Tolerance={tolerance}')

    try:
        BusbarsDictVoltage, BusbarsDictConnectionToName = create_busbars(
            in_data, dss, export_commands, opendss_commands)
        (LinesDict, LinesDictId, LoadsDict, LoadsDictId,
         TransformersDict, TransformersDictId,
         ShuntsDict, ShuntsDictId, CapacitorsDict, CapacitorsDictId,
         GeneratorsDict, GeneratorsDictId,
         StoragesDict, StoragesDictId, PVSystemsDict, PVSystemsDictId,
         ExternalGridsDict, ExternalGridsDictId,
         _circuit_source) = create_other_elements(
            in_data, dss, BusbarsDictVoltage, BusbarsDictConnectionToName,
            export_commands, opendss_commands, execute_dss_command)
    except ValueError as ve:
        return json.dumps({"error": str(ve)}, separators=(',', ':'))
    except Exception as e:
        return json.dumps({"error": f"Error creating network elements for harmonics: {str(e)}"}, separators=(',', ':'))

    # ---- Step 3: Add monitors for per-harmonic data capture -------------------
    # Monitors on lines capture both voltages and currents at each harmonic step
    user_bus_names = list(BusbarsDictConnectionToName.keys())
    
    for line_key, dss_line_name in LinesDict.items():
        execute_dss_command(f'New Monitor.mon_{dss_line_name} element=Line.{dss_line_name} terminal=1 mode=0')

    # ---- Step 4: Solve fundamental power flow first ---------------------------
    # OpenDSS requires a converged fundamental power flow before switching to harmonics mode.
    # See: https://opendss.epri.com/HarmonicFlowAnalysis.html
    execute_dss_command('set Mode=Snapshot')
    execute_dss_command('solve')
    
    # Check convergence before proceeding to harmonics mode
    converged = dss.Solution.Converged()
    if not converged:
        # Try Direct solution mode as fallback (often more robust for initialization)
        execute_dss_command('set Mode=Direct')
        execute_dss_command('solve')
        converged = dss.Solution.Converged()
    
    if not converged:
        return json.dumps({
            "error": "Power flow did not converge. Cannot proceed with harmonic analysis. "
                     "Check the circuit topology and parameters (e.g., loads, generators, voltage setpoints)."
        }, separators=(',', ':'))

    # Read fundamental (h=1) bus voltages and line currents as baseline
    def _read_bus_voltages_ll_kv():
        """Return dict  bus_key(lower) -> V_ll_kV  for user buses."""
        result_map = {}
        for bus_key in user_bus_names:
            try:
                dss.Circuit.SetActiveBus(bus_key)
                voltages = dss.Bus.Voltages()
                if len(voltages) >= 6:
                    Va = complex(voltages[0], voltages[1]) / 1000.0
                    Vb = complex(voltages[2], voltages[3]) / 1000.0
                    Vc = complex(voltages[4], voltages[5]) / 1000.0
                    a_op = complex(-0.5, math.sqrt(3) / 2)
                    a2 = complex(-0.5, -math.sqrt(3) / 2)
                    V1 = (Va + a_op * Vb + a2 * Vc) / 3.0
                    result_map[bus_key.lower()] = abs(V1) * math.sqrt(3)
                else:
                    Va = complex(voltages[0], voltages[1]) / 1000.0
                    result_map[bus_key.lower()] = abs(Va) * math.sqrt(3)
            except Exception:
                result_map[bus_key.lower()] = 0.0
        return result_map

    def _read_line_currents_a():
        """Return dict  line_key -> I_from_A  for user lines."""
        result_map = {}
        for key in LinesDict:
            try:
                dss.Circuit.SetActiveElement(f"Line.{LinesDict[key]}")
                currents = dss.CktElement.CurrentsMagAng()
                if len(currents) >= 2:
                    result_map[key] = currents[0]
                else:
                    result_map[key] = 0.0
            except Exception:
                result_map[key] = 0.0
        return result_map

    fund_bus_v = _read_bus_voltages_ll_kv()
    fund_line_i = _read_line_currents_a()

    # ---- Step 5: Solve harmonics using OpenDSS built-in harmonic mode ---------
    # This is the correct way per OpenDSS documentation:
    # https://opendss.epri.com/HarmonicFlowAnalysis.html
    # OpenDSS will automatically:
    # - Convert loads to impedance models at each harmonic frequency
    # - Use element spectra to determine harmonic current/voltage injections
    # - Apply %SeriesRL for loads, Xdpp for generators
    
    if neglect_load_y:
        execute_dss_command('set NeglectLoadY=Yes')
    else:
        execute_dss_command('set NeglectLoadY=No')
    
    # Set the harmonics list (include fundamental h=1 for reference)
    all_harmonics = sorted(set([1] + harmonic_orders))
    h_str = '[' + ','.join(str(h) for h in all_harmonics) + ']'
    execute_dss_command(f'set harmonics={h_str}')
    execute_dss_command('set mode=harmonics')
    execute_dss_command('solve')

    # ---- Step 6: Read per-harmonic data from monitors -------------------------
    # After mode=harmonics solve, monitors have one record per harmonic step.
    # For mode=0 monitors on 3-phase lines:
    #   Channel 1 = V_a mag, Channel 3 = V_b mag, Channel 5 = V_c mag
    #   Channel 7 = I_a mag, Channel 9 = I_b mag, Channel 11 = I_c mag
    # (even channels are angles)
    
    bus_harmonic_v = {bk.lower(): {} for bk in user_bus_names}
    line_harmonic_i = {lk: {} for lk in LinesDict}
    
    # Build a mapping from line terminal buses to bus keys for voltage data
    line_bus_map = {}
    for line_key in LinesDict:
        for x_key in in_data:
            ed = in_data[x_key]
            if ed.get('name', '') == line_key:
                bf = ed.get('busFrom', '')
                if bf in BusbarsDictConnectionToName:
                    line_bus_map[line_key] = bf.lower()
                break
    
    for line_key, dss_line_name in LinesDict.items():
        try:
            # OpenDSSDirect uses function calls, not assignments
            mon_name = f'mon_{dss_line_name}'
            dss.Monitors.Name(mon_name)
            
            # Get number of channels and samples (function calls for OpenDSSDirect)
            num_channels = dss.Monitors.NumChannels()
            sample_count = dss.Monitors.SampleCount()
            
            if sample_count == 0 or num_channels == 0:
                print(f"[OpenDSS][HARMONICS] Monitor mon_{dss_line_name}: no data (channels={num_channels}, samples={sample_count})")
                continue
            
            print(f"[OpenDSS][HARMONICS] Monitor mon_{dss_line_name}: channels={num_channels}, samples={sample_count}, harmonics={all_harmonics}")
            
            # Read voltage magnitude channel 1 (V_a) and current magnitude channel 7 (I_a)
            # For mode=0 monitor: V1, V1ang, V2, V2ang, V3, V3ang, I1, I1ang, I2, I2ang, I3, I3ang
            try:
                v_data = list(dss.Monitors.Channel(1))  # V_a magnitude per harmonic step
            except Exception:
                v_data = []
            
            i_channel = min(7, num_channels)  # I_a is channel 7 for 3-phase
            try:
                i_data = list(dss.Monitors.Channel(i_channel))  # I_a magnitude per harmonic step
            except Exception:
                i_data = []
            
            # Map samples to harmonic orders
            for idx, h in enumerate(all_harmonics):
                if h == 1:
                    continue  # Skip fundamental (we have it from power flow)
                if h not in harmonic_orders:
                    continue
                
                # Get current for this harmonic
                if idx < len(i_data):
                    line_harmonic_i[line_key][h] = abs(i_data[idx])
                else:
                    line_harmonic_i[line_key][h] = 0.0
                
                # Get voltage and map to bus
                bus_key = line_bus_map.get(line_key, '')
                if bus_key and idx < len(v_data):
                    # Convert phase voltage (V) to LL (kV): V_a * sqrt(3) / 1000
                    v_ll_kv = abs(v_data[idx]) * math.sqrt(3) / 1000.0
                    # Only update if this is larger (multiple lines may connect to same bus)
                    existing = bus_harmonic_v.get(bus_key, {}).get(h, 0.0)
                    if v_ll_kv > existing:
                        if bus_key in bus_harmonic_v:
                            bus_harmonic_v[bus_key][h] = v_ll_kv
                        
        except Exception as e:
            print(f"[OpenDSS][HARMONICS] Error reading monitor for {dss_line_name}: {e}")
            continue
    
    # Fallback: also try reading bus voltages directly at each harmonic frequency
    # (some buses may not be connected to monitored lines)
    for h in harmonic_orders:
        f_h = frequency * h
        execute_dss_command(f'set frequency={f_h}')
        execute_dss_command('set mode=direct')
        execute_dss_command('solve')
        
        v_map = _read_bus_voltages_ll_kv()
        i_map = _read_line_currents_a()
        
        for bk in bus_harmonic_v:
            if h not in bus_harmonic_v[bk] or bus_harmonic_v[bk][h] == 0.0:
                bus_harmonic_v[bk][h] = v_map.get(bk, 0.0)
        
        for lk in line_harmonic_i:
            if h not in line_harmonic_i[lk] or line_harmonic_i[lk][h] == 0.0:
                line_harmonic_i[lk][h] = i_map.get(lk, 0.0)

    # ---- Step 7: compute THD --------------------------------------------------
    bus_thd = {}
    for bk in bus_harmonic_v:
        v1 = fund_bus_v.get(bk, 0.0)
        if v1 > 0:
            sum_sq = sum(bus_harmonic_v[bk].get(h, 0.0) ** 2 for h in harmonic_orders)
            bus_thd[bk] = (math.sqrt(sum_sq) / v1) * 100.0
        else:
            bus_thd[bk] = 0.0

    line_thd = {}
    for lk in line_harmonic_i:
        i1 = fund_line_i.get(lk, 0.0)
        if i1 > 0:
            sum_sq = sum(line_harmonic_i[lk].get(h, 0.0) ** 2 for h in harmonic_orders)
            line_thd[lk] = (math.sqrt(sum_sq) / i1) * 100.0
        else:
            line_thd[lk] = 0.0

    # ---- Step 8: enrich base_result with harmonic data -------------------------
    if "busbars" in base_result:
        for bus_entry in base_result["busbars"]:
            bus_key = (bus_entry.get("id") or bus_entry.get("name", "")).lower()
            bus_entry["vthd_percent"] = round(bus_thd.get(bus_key, 0.0), 3)
            per_h = {}
            for h in harmonic_orders:
                per_h[str(h)] = round(bus_harmonic_v.get(bus_key, {}).get(h, 0.0), 6)
            bus_entry["harmonic_voltages_kv"] = per_h

    if "lines" in base_result:
        for line_entry in base_result["lines"]:
            line_key = line_entry.get("name", "")
            line_entry["ithd_percent"] = round(line_thd.get(line_key, 0.0), 3)
            per_h = {}
            for h in harmonic_orders:
                per_h[str(h)] = round(line_harmonic_i.get(line_key, {}).get(h, 0.0), 6)
            line_entry["harmonic_currents_a"] = per_h

    # Overall metadata
    base_result["harmonic_analysis"] = {
        "executed": True,
        "frequency_hz": frequency,
        "harmonic_orders": harmonic_orders,
        "neglectLoadY": bool(neglect_load_y),
    }
    if export_commands:
        existing_text = base_result.get("opendss_commands", "")
        harmonic_text = "\n".join(["# --- HARMONIC ANALYSIS ---"] + opendss_commands) if opendss_commands else ""
        if existing_text and harmonic_text:
            base_result["opendss_commands"] = existing_text + "\n" + harmonic_text
        elif harmonic_text:
            base_result["opendss_commands"] = harmonic_text

    def _to_native_json(obj):
        """Convert numpy types to native Python for JSON serialization."""
        try:
            import numpy as np
            if isinstance(obj, (np.floating, np.float32, np.float64, np.float16)):
                return float(obj)
            if isinstance(obj, (np.integer, np.int32, np.int64)):
                return int(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            pass
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    def _sanitize_nan(obj):
        """Replace NaN/Inf with null so JSON is parseable by strict parsers (e.g. JSON.parse)."""
        if isinstance(obj, dict):
            return {k: _sanitize_nan(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize_nan(v) for v in obj]
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        try:
            import numpy as np
            if isinstance(obj, (np.floating, np.float32, np.float64, np.float16)):
                v = float(obj)
                return None if (math.isnan(v) or math.isinf(v)) else v
        except ImportError:
            pass
        return obj

    try:
        sanitized = _sanitize_nan(base_result)
        return json.dumps(sanitized, default=_to_native_json, allow_nan=False, separators=(',', ':'))
    except Exception as json_error:
        return json.dumps(
            {
                "error": "Harmonic JSON serialization failed",
                "message": str(json_error),
            },
            separators=(',', ':'),
        )
