import py_dss_interface
from typing import List
import math
import json

# Output classes for OpenDSS results (similar to pandapower_electrisim.py structure)
class BusbarOut(object):
    def __init__(self, name: str, id: str, vm_pu: float, va_degree: float):          
        self.name = name
        self.id = id
        self.vm_pu = vm_pu
        self.va_degree = va_degree
                        
class BusbarsOut(object):
    def __init__(self, busbars: List[BusbarOut]):
        self.busbars = busbars             

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
            dss.text(command)
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


    
    for x in in_data:
        try:
            element_data = in_data[x]
            element_type = element_data.get('typ', '')
            element_name = element_data.get('name', '')
            element_id = element_data.get('id', '')  
            
            # Skip bus elements and parameters
            if "Bus" in element_type or element_type == "PowerFlowOpenDss Parameters":
                continue
            
            # Debug: Show what we're processing
      
            

            # Validate bus connections
            has_valid_bus_connection = False
            bus_connection_fields = []

            # Check all possible bus connection fields
            if 'bus' in element_data:
                bus_connection_fields.append(('bus', element_data['bus']))
            if 'busFrom' in element_data:
                bus_connection_fields.append(('busFrom', element_data['busFrom']))
            if 'busTo' in element_data:
                bus_connection_fields.append(('busTo', element_data['busTo']))

        

            # Validate each bus connection
            valid_connections = []
            for field_name, bus_ref in bus_connection_fields:
                # Frontend now sends bus names in the correct format (mxCell_126)
                bus_ref_backend = bus_ref               
                if bus_ref_backend in BusbarsDictConnectionToName:
                    # Valid bus connection
                    valid_connections.append(f"{field_name}={bus_ref}")
                    has_valid_bus_connection = True               
                else:
                    print(f"      ⚠️  Bus {bus_ref} (converted to {bus_ref_backend}) not found in BusbarsDictConnectionToName")
                    print(f"         Available buses: {list(BusbarsDictConnectionToName.keys())}")

   

            # Process different element types
            if "Line" in element_type:
                create_line_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LinesDict, LinesDictId, created_elements, execute_dss_command)
            elif element_type == "Load":
                create_load_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LoadsDict, LoadsDictId, created_elements, execute_dss_command)
            elif element_type == "Static Generator":
                create_static_generator_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, GeneratorsDict, GeneratorsDictId, created_elements, execute_dss_command)
            elif element_type == "Asymmetric Static Generator":
                # For OpenDSS, treat asymmetric static generator as a regular static generator
                # We'll use the phase A values as the main values
                create_static_generator_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, GeneratorsDict, GeneratorsDictId, created_elements, execute_dss_command)
            elif element_type == "Generator":
                create_generator_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, GeneratorsDict, GeneratorsDictId, created_elements, execute_dss_command)
            elif element_type == "Transformer":
                create_transformer_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, TransformersDict, TransformersDictId, created_elements, execute_dss_command)
            elif element_type == "Shunt Reactor":
                create_shunt_reactor_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, ShuntsDict, ShuntsDictId, created_elements, execute_dss_command)
            elif element_type == "Capacitor":
                create_capacitor_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, CapacitorsDict, CapacitorsDictId, created_elements, execute_dss_command)
            elif element_type == "Storage":
                create_storage_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, StoragesDict, StoragesDictId, created_elements, execute_dss_command)
            elif element_type == "PVSystem":
                create_pvsystem_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, PVSystemsDict, PVSystemsDictId, created_elements, execute_dss_command)
            elif element_type == "External Grid":
                create_external_grid_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, created_elements, execute_dss_command)
                # Store in dictionaries for later reference
                ExternalGridsDict[element_name] = element_name
                ExternalGridsDictId[element_name] = element_id
                
        except ValueError as ve:
            # Re-raise validation errors so they propagate to frontend
            print(f"Error processing element {x} ({element_type}): {ve}")
            raise
        except Exception as e:
            # For other errors, log and continue processing other elements
            print(f"Error processing element {x} ({element_type}): {e}")
            continue
    
   
    
    return (LinesDict, LinesDictId, LoadsDict, LoadsDictId, TransformersDict, TransformersDictId,
            ShuntsDict, ShuntsDictId, CapacitorsDict, CapacitorsDictId, GeneratorsDict, GeneratorsDictId,
            StoragesDict, StoragesDictId, PVSystemsDict, PVSystemsDictId, ExternalGridsDict, ExternalGridsDictId)

# Individual element creation functions
def create_line_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LinesDict, LinesDictId, created_elements, execute_dss_command=None):
    """Create a line element in OpenDSS"""
    
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
            
            print(f"Command: {line_cmd}")
            
            actual_name = dss.lines.name
            LinesDict[element_name] = actual_name
            LinesDictId[element_name] = element_id
            created_elements.add(element_name)
            
        except Exception as e:
            print(f"  ✗ Error creating line: {e}")
    else:
        print(f"  ✗ Line {element_name} missing bus connections")

def create_load_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LoadsDict, LoadsDictId, created_elements, execute_dss_command=None):
    """Create a load element in OpenDSS"""
    
    bus_connection = element_data.get('bus')
    if bus_connection:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_connection_backend = bus_connection
        if bus_connection_backend in BusbarsDictConnectionToName:
            bus_name = BusbarsDictConnectionToName[bus_connection_backend]
        # Get voltage from the bus data
        bus_voltage = BusbarsDictVoltage.get(bus_name)
        
        if bus_voltage is None:
            print(f"  ✗ Load {element_name} cannot be created - no voltage information for bus {bus_name}")
            return                 
        
        # Get load parameters with proper null handling
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
            
            # Create load using OpenDSS command
            execute_dss_command(load_cmd)
            print(f"Command: {load_cmd}")
            
            LoadsDict[element_name] = load_name
            LoadsDictId[element_name] = element_id
            created_elements.add(element_name)
            
        except Exception as e:
            print(f"  ✗ Error creating load: {e}")
    else:
        print(f"  ✗ Load {element_name} has no bus connection")
        print(f"    bus_connection: {bus_connection}")
        print(f"    in BusbarsDictConnectionToName: {bus_connection in BusbarsDictConnectionToName}")

def create_static_generator_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, GeneratorsDict, GeneratorsDictId, created_elements, execute_dss_command=None):
    """Create a static generator element in OpenDSS"""
   
    
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
                # Use simple Generator element with constant P and Q
                gen_cmd = f"New Generator.{gen_name} Bus1={bus_name} Phases=3 kV={bus_voltage} kW={p_kw:.3f} kvar={q_kvar:.3f}"

                # Create Generator element
                execute_dss_command(gen_cmd)
                print(f"✓ Command: {gen_cmd}")
                print(f"  Created: Generator P={p_mw:.3f} MW, Q={q_mvar:.3f} MVAr at {bus_voltage} kV bus")
                
                # Store in GeneratorsDict
                GeneratorsDict[element_name] = gen_name
                GeneratorsDictId[element_name] = element_id
                created_elements.add(element_name)
                
            except Exception as e:
                print(f"  ✗ Error creating static generator: {e}")
        else:
            print(f"  ✗ Could not find voltage information for bus {bus_name}")
    else:
        print(f"  ✗ Static Generator {element_name} has no bus connection")
        print(f"    bus_connection: {bus_connection}")
        print(f"    in BusbarsDictConnectionToName: {bus_connection in BusbarsDictConnectionToName}")

def create_generator_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, GeneratorsDict, GeneratorsDictId, created_elements, execute_dss_command=None):
    """Create a generator element in OpenDSS"""

    
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
        q_mvar_raw = element_data.get('q_mvar')
        vm_pu_raw = element_data.get('vm_pu')        

        # Convert to float
        p_mw = float(p_mw_raw)
        q_mvar = float(q_mvar_raw)
        vm_pu = float(vm_pu_raw)
        
                # Convert to kW and kVar
        p_kw = p_mw * 1000
        q_kvar = q_mvar * 1000

        try:
            # Create generator command string
            gen_cmd = f"New Generator.{element_name} Bus1={bus_name} kV={bus_voltage} kW={p_kw} kvar={q_kvar}"

            # Create generator using OpenDSS command
            execute_dss_command(gen_cmd)
            print(f"Command: {gen_cmd}")

            # Configure generator to NOT act as voltage source
            dss.generators.mode = 1  # Power Factor mode
            # Disable voltage control by setting control mode to 0 (no control)
            try:
                dss.generators.status = 'Variable'  # Set to variable (not fixed)
            except:
                pass  # Ignore if property doesn't exist

            GeneratorsDict[element_name] = element_name
            GeneratorsDictId[element_name] = element_id
            created_elements.add(element_name)
            
        except Exception as e:
            print(f"  ✗ Error creating generator: {e}")
    else:
        print(f"  ✗ Generator {element_name} has no bus connection")
        print(f"    bus_connection: {bus_connection}")
        print(f"    in BusbarsDictConnectionToName: {bus_connection in BusbarsDictConnectionToName}")

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
            
            # Create complete OpenDSS transformer command with calculated taps
            transformer_cmd = f"New Transformer.{element_name} Phases=3 Windings=2 Buses=({bus_from_name} {bus_to_name}) Conns=({conns}) kVs=({bus_from_voltage} {bus_to_voltage}) kVAs=({sn_kva} {sn_kva}) XHL={vk_percent} %Rs={vkr_percent} Taps=[{tap_hv} {tap_lv}]"
            
            execute_dss_command(transformer_cmd)
            print(f"Command: {transformer_cmd}")
            print(f"  Tap settings: Position={tap_pos}, Step={tap_step_percent}%, Side={tap_side}, Taps=[{tap_hv} {tap_lv}]")
            
            TransformersDict[element_name] = element_name
            TransformersDictId[element_name] = element_id
            created_elements.add(element_name)
            
        except Exception as e:
            print(f"  ✗ Error creating transformer: {e}")
            print(f"    Transformer properties after creation attempt:")
            try:
                print(f"      Name: {dss.transformers.name}")
                print(f"      Bus1: {dss.transformers.bus1}")
                print(f"      Bus2: {bus_to_name}")
            except Exception as debug_e:
                print(f"      Could not get transformer properties: {debug_e}")
    else:
        print(f"  ✗ Transformer {element_name} missing bus connections")

def create_shunt_reactor_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, ShuntsDict, ShuntsDictId, created_elements, execute_dss_command=None):
    """Create a shunt reactor element in OpenDSS"""

    
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
        print(f"  Shunt Reactor {element_name} parameters:")
        print(f"    q_mvar_raw: {q_mvar_raw}")
        print(f"    p_mw_raw: {p_mw_raw}")
        print(f"    bus_voltage: {bus_voltage}")
        
        # Convert to float
        q_mvar = float(q_mvar_raw)
        p_mw = float(p_mw_raw) if p_mw_raw is not None else 0.0
        
        # Convert to kVar and kW
        q_kvar = q_mvar * 1000
        p_kw = p_mw * 1000
        
        print(f"    p_mw: {p_mw}, q_mvar: {q_mvar}")
        print(f"    p_kw: {p_kw}, q_kvar: {q_kvar}")
        
        # Calculate parallel resistance Rp from active power
        # OpenDSS allows specifying Rp (parallel resistance) which consumes active power
        # For parallel resistance: P = V²/Rp (in per-phase values)
        # For 3-phase: P_total = 3 * V_LN² / Rp = V_LL² / Rp
        # Therefore: Rp = V_LL² / P_total (in ohms)
        rp_ohms = None
        if p_kw != 0 and bus_voltage is not None:
            voltage_kv = float(bus_voltage)
            # Convert kW to W and kV to V for calculation
            p_watts = p_kw * 1000
            v_volts = voltage_kv * 1000
            # Rp = V² / P (line-to-line voltage for 3-phase)
            rp_ohms = (v_volts ** 2) / p_watts
            print(f"    Calculated Rp: {rp_ohms} ohms")
        else:
            print(f"    Rp not calculated (p_kw={p_kw}, bus_voltage={bus_voltage})")

        try:
            # Create shunt reactor using bus name directly - OpenDSS will create bus automatically
            # Use Rp (parallel resistance) for active power consumption
            # R=0 means no series resistance (ideal inductor)
            simple_cmd = f"New Reactor.{element_name} Bus1={bus_name} R=0 kvar={abs(q_kvar)} kV={bus_voltage}"
            
            # Add parallel resistance if active power is specified
            if rp_ohms is not None:
                simple_cmd += f" Rp={rp_ohms}"
            execute_dss_command(simple_cmd)
            print(f"Command: {simple_cmd}")

            ShuntsDict[element_name] = element_name
            ShuntsDictId[element_name] = element_id
            created_elements.add(element_name)
            
        except Exception as e:
            print(f"  ✗ Error creating shunt reactor: {e}")
    else:
        print(f"  ✗ Shunt reactor {element_name} has no bus connection")
        print(f"    bus_connection: {bus_connection}")
        print(f"    in BusbarsDictConnectionToName: {bus_connection in BusbarsDictConnectionToName}")

def create_capacitor_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, CapacitorsDict, CapacitorsDictId, created_elements, execute_dss_command=None):
    """Create a capacitor element in OpenDSS"""
  
    
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
                print(f"Command: {simple_cmd}")

                CapacitorsDict[element_name] = element_name
                CapacitorsDictId[element_name] = element_id
                created_elements.add(element_name)
                
            except Exception as e:
                print(f"  ✗ Error creating capacitor: {e}")
        else:
            print(f"  ✗ Could not find voltage information for capacitor {element_name}")
    else:
        print(f"  ✗ Capacitor {element_name} has no bus connection")

def create_storage_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, StoragesDict, StoragesDictId, created_elements, execute_dss_command=None):
    """Create a storage element in OpenDSS"""

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
                execute_dss_command(simple_cmd)
                print(f"Command: {simple_cmd}")
       
                
                StoragesDict[element_name] = element_name
                StoragesDictId[element_name] = element_id
                created_elements.add(element_name)
                
            except Exception as e:
                print(f"  ✗ Error creating storage: {e}")
        else:
            print(f"  ✗ Could not find voltage information for storage {element_name}")
    else:
        print(f"  ✗ Storage {element_name} has no bus connection")
 
def create_pvsystem_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, PVSystemsDict, PVSystemsDictId, created_elements, execute_dss_command=None):
    """Create a PVSystem element in OpenDSS"""

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
            # Get PVSystem parameters with proper null handling
            irradiance_raw = element_data.get('irradiance')
            pmpp_raw = element_data.get('pmpp')
            temperature_raw = element_data.get('temperature')
            phases_raw = element_data.get('phases')
            kv_raw = element_data.get('kv')
            pf_raw = element_data.get('pf')
            kvar_raw = element_data.get('kvar')
            kva_raw = element_data.get('kva')
            cutin_raw = element_data.get('cutin')
            cutout_raw = element_data.get('cutout')
            effcurve_raw = element_data.get('effcurve')
            ptcurve_raw = element_data.get('ptcurve')
            r_raw = element_data.get('r')
            x_raw = element_data.get('x')

            # Convert to float with defaults based on OpenDSS documentation
            irradiance = float(irradiance_raw) if irradiance_raw is not None else 1.0
            pmpp = float(pmpp_raw) if pmpp_raw is not None else 100.0  # kW
            temperature = float(temperature_raw) if temperature_raw is not None else 25.0
            phases = int(phases_raw) if phases_raw is not None else 3
            kv = float(kv_raw) if kv_raw is not None else float(bus_voltage)
            pf = float(pf_raw) if pf_raw is not None else 1.0
            kvar = float(kvar_raw) if kvar_raw is not None else 0.0
            kva = float(kva_raw) if kva_raw is not None else pmpp * 1.2  # Default 20% above Pmpp
            cutin = float(cutin_raw) if cutin_raw is not None else 0.1
            cutout = float(cutout_raw) if cutout_raw is not None else 0.1

            try:
                # Create PVSystem command string with all basic parameters
                pv_cmd = f"New PVSystem.{element_name} phases={phases} Bus1={bus_name} kV={kv} irradiance={irradiance} Pmpp={pmpp} Temperature={temperature}"

                # Add optional parameters if they exist
                if pf is not None:
                    pv_cmd += f" pf={pf}"
                if kvar is not None:
                    pv_cmd += f" kvar={kvar}"
                if kva is not None:
                    pv_cmd += f" kVA={kva}"
                if cutin is not None:
                    pv_cmd += f" %Cutin={cutin * 100}"  # Convert to percentage
                if cutout is not None:
                    pv_cmd += f" %Cutout={cutout * 100}"  # Convert to percentage

                # Add resistance and reactance if provided
                if r_raw is not None:
                    pv_cmd += f" %R={float(r_raw)}"
                if x_raw is not None:
                    pv_cmd += f" %X={float(x_raw)}"

                # Add curve references if provided
                if effcurve_raw:
                    pv_cmd += f" EffCurve={effcurve_raw}"
                if ptcurve_raw:
                    pv_cmd += f" P-TCurve={ptcurve_raw}"

                execute_dss_command(pv_cmd)
                print(f"Command: {pv_cmd}")

                PVSystemsDict[element_name] = element_name
                PVSystemsDictId[element_name] = element_id
                created_elements.add(element_name)

            except Exception as e:
                print(f"  ✗ Error creating PVSystem: {e}")
        else:
            print(f"  ✗ Could not find voltage information for bus {bus_name}")
    else:
        print(f"  ✗ PVSystem {element_name} has no bus connection")
        print(f"    bus_connection: {bus_connection}")
        print(f"    in BusbarsDictConnectionToName: {bus_connection in BusbarsDictConnectionToName}")

def create_external_grid_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, created_elements, execute_dss_command=None):
    """Create an external grid element in OpenDSS"""

    
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
        
        # Ensure short circuit MVA is not zero (would cause singular matrix)
        # Use a reasonable default if zero or very small
        if s_sc_max_mva <= 0.1:
            s_sc_max_mva = 10000.0  # Default 10000 MVA short circuit capacity
            print(f"  ⚠️  External Grid {element_name}: s_sc_max_mva was {s_sc_max_mva_raw}, using default {s_sc_max_mva} MVA")
        
        try:
            # Create external grid using OpenDSS VSource command
            # Use bus name directly - OpenDSS will create bus automatically
            external_grid_cmd = f"New Vsource.{element_name} Bus1={bus_name} basekv={bus_voltage} pu={vm_pu} mvasc3={s_sc_max_mva}"
            execute_dss_command(external_grid_cmd)      
            print(f"Command: {external_grid_cmd}")
    
            
            # Note: We can't store in ExternalGridsDict here as it's not in scope
            # The calling function will handle this
            created_elements.add(element_name)
            
        except Exception as e:
            print(f"  ✗ Error creating external grid: {e}")
    else:
        print(f"  ✗ External Grid {element_name} has no bus connection")
        print(f"    bus_connection: {bus_connection}")
        print(f"    in BusbarsDictConnectionToName: {bus_connection in BusbarsDictConnectionToName}")
 
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
    
    dss = py_dss_interface.DSS()     

    # Initialize list to collect OpenDSS commands if export is requested
    opendss_commands = []
    
    def execute_dss_command(command):
        """Execute DSS command and optionally collect it for export"""
        dss.text(command)
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
         StoragesDict, StoragesDictId, PVSystemsDict, PVSystemsDictId, ExternalGridsDict, ExternalGridsDictId) = create_other_elements(in_data, dss, BusbarsDictVoltage, BusbarsDictConnectionToName, export_commands, opendss_commands, execute_dss_command)
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
    
    # Note: OpenDSS creates buses automatically when elements are connected
    # We don't need to explicitly create buses - they are created implicitly
    # when we set the bus1/bus2 properties of elements like lines, loads, etc.

    # Validate circuit before solve

    # Execute solve commands
    try:
        dss.text('calcv')
        dss.text('solve')
    except Exception as e:
        print(f"Error executing solve: {e}")
    
    # Check solve status
    try:
        converged = dss.solution.converged
        if converged:
            print(f"✓ Load flow converged ({dss.solution.iterations} iterations)")
        else:
            print(f"✗ Load flow did not converge")
    except Exception as e:
        print(f"Error checking solve status: {e}")
    
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
    
    # Process bus results using actual OpenDSS data with proper symmetrical component calculation
    
    # Build a mapping from OpenDSS bus numbers to our bus IDs
    # OpenDSS internally uses numeric bus IDs, we need to map them back
    BusbarsDict = {}
    nBusbar = 0
    for bus_id in BusbarsDictConnectionToName.keys():
        BusbarsDict[bus_id] = nBusbar
        nBusbar += 1
    
    print(f"  Expected user buses from input: {list(BusbarsDict.keys())}")
    
    # Track which buses have been processed to avoid duplicates
    processed_buses = set()
    
    try:
        all_bus_names = dss.circuit.buses_names
        print(f"  All buses in OpenDSS circuit: {all_bus_names}")
        
        # Process all buses from OpenDSS circuit
        for bus_name_from_list in all_bus_names:
            # Set active bus using the name from the list
            dss.circuit.set_active_bus(bus_name_from_list)
            
            # Get the actual bus name (might be different from list name)
            actual_bus_name = dss.bus.name
            
            # Debug: Print bus names to identify source buses
            print(f"  Processing bus from list: '{bus_name_from_list}', actual name: '{actual_bus_name}'")
            
            # Skip sourcebus and source - OpenDSS's internal voltage source buses created by "New Circuit"
            # These are NOT the user's buses where External Grid VSources connect
            if (actual_bus_name.lower() in ['sourcebus', 'source'] or 
                bus_name_from_list.lower() in ['sourcebus', 'source']):
                print(f"    ⚠️  Skipping OpenDSS system source bus: {actual_bus_name}")
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
                    print(f"    ✓ Matched to user bus: {matched_bus_name}")
                    break
            
            if not matched_bus_id:
                print(f"    ⚠️  No match found - this is not a user bus, skipping '{actual_bus_name}'")
                continue
            
            # Skip if we've already processed this bus number
            if bus_number in processed_buses:
                continue
            
            processed_buses.add(bus_number)
            
            try:
                # Calculate positive sequence voltage using symmetrical components
                # This matches the notebook approach exactly
                voltages = dss.bus.voltages  # in Volts: [Va_real, Va_imag, Vb_real, Vb_imag, Vc_real, Vc_imag]
                
                # Debug: Print raw voltages
                print(f"    Raw voltages from OpenDSS (Volts): {voltages[:6] if len(voltages) >= 6 else voltages}")
                
                # Convert to kV and create complex numbers
                Va = complex(voltages[0]/1000, voltages[1]/1000)
                Vb = complex(voltages[2]/1000, voltages[3]/1000)
                Vc = complex(voltages[4]/1000, voltages[5]/1000)
                
                print(f"    Phase voltages (kV L-N): Va={abs(Va):.3f}, Vb={abs(Vb):.3f}, Vc={abs(Vc):.3f}")
                
                # Symmetrical component operator: a = e^(j*2π/3)
                a = complex(-0.5, math.sqrt(3)/2)
                a2 = complex(-0.5, -math.sqrt(3)/2)  # a² = e^(j*4π/3)
                
                # Positive sequence voltage: V1 = (Va + a*Vb + a²*Vc) / 3
                V1 = (Va + a * Vb + a2 * Vc) / 3
                V1_mag_ln_kv = abs(V1)  # Magnitude in kV (line-to-neutral)
                
                # Convert to line-to-line voltage
                V1_mag_ll_kv = V1_mag_ln_kv * math.sqrt(3)
                
                print(f"    Positive sequence: V1_L-N={V1_mag_ln_kv:.3f} kV, V1_L-L={V1_mag_ll_kv:.3f} kV")
                
                # Use the user-specified base voltage from input data (not OpenDSS's internal base)
                # This is the vn_kv from the bus definition
                base_kv_user = BusbarsDictVoltage.get(matched_bus_id)
                
                if base_kv_user is not None:
                    # User specified voltage in L-L format
                    base_kv = float(base_kv_user)
                    print(f"    Base voltage (user-specified): {base_kv:.3f} kV L-L")
                else:
                    # Fallback to OpenDSS's base voltage
                    base_kv_ln = dss.bus.kv_base
                    base_kv = base_kv_ln * math.sqrt(3)  # Convert L-N to L-L
                    print(f"    Base voltage (OpenDSS default): {base_kv_ln:.3f} kV L-N, {base_kv:.3f} kV L-L")
                
                # Calculate per-unit based on user-specified base voltage
                vm_pu = V1_mag_ll_kv / base_kv if base_kv > 0 else 1.0
                
                print(f"    Calculated vm_pu = {V1_mag_ll_kv:.3f} / {base_kv:.3f} = {vm_pu:.6f}")
                
                # Get angle from vmag_angle_pu
                va_degree = dss.bus.vmag_angle_pu[1] if len(dss.bus.vmag_angle_pu) > 1 else 0.0
                
                print(f"    Final result: vm_pu={vm_pu:.6f}, va_degree={va_degree:.6f}")
                
                # Create busbar result - convert ID back to hash format for frontend
                frontend_bus_id = matched_bus_id.replace('_', '#')
                frontend_bus_name = matched_bus_name.replace('_', '#')
                busbar = BusbarOut(
                    name=frontend_bus_name,
                    id=frontend_bus_id,
                    vm_pu=vm_pu,
                    va_degree=va_degree
                )
                busbarList.append(busbar)
                print(f"    ✓ Added to results: {frontend_bus_name} (vm_pu={vm_pu:.6f}, va_degree={va_degree:.6f})")
                
            except Exception as e:
                print(f"Error calculating voltage for bus {matched_bus_name}: {e}")
                # Add with default values - convert ID back to hash format for frontend
                frontend_bus_id = matched_bus_id.replace('_', '#')
                frontend_bus_name = matched_bus_name.replace('_', '#')
                busbar = BusbarOut(
                    name=frontend_bus_name,
                    id=frontend_bus_id,
                    vm_pu=1.0,
                    va_degree=0.0
                )
                busbarList.append(busbar)
                
    except Exception as e:
        print(f"Error processing bus results: {e}")
        # Fallback to default processing if OpenDSS bus access fails
        for bus_name in BusbarsDictConnectionToName.keys():
            try:
                vm_pu = 1.0
                va_degree = 0.0
                
                # Convert to hash format for frontend
                frontend_bus_name = bus_name.replace('_', '#')
                frontend_bus_id = bus_name.replace('_', '#')
                busbar = BusbarOut(
                    name=frontend_bus_name,
                    id=frontend_bus_id,
                    vm_pu=vm_pu, 
                    va_degree=va_degree
                )
                busbarList.append(busbar)
                
            except Exception as e2:
                print(f"Error processing bus {bus_name}: {e2}")
                continue
    
    # Process line results (matching notebook approach)
    if dss.lines.count > 0:
        dss.lines.first()
        for _ in range(dss.lines.count):
            try:
                line_name = dss.lines.name
                
                # Find matching line in our dictionary (case-insensitive)
                for key, value in LinesDict.items():
                    if value.lower() == line_name.lower() or key.lower() == line_name.lower():
                        try:
                            # Get powers (in kW and kvar) - sum all three phases
                            powers = dss.cktelement.powers
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
                            currents = dss.cktelement.currents_mag_ang
                            if len(currents) >= 12:
                                # Current magnitude is at index 0, 6 for from and to sides
                                i_from_ka = currents[0] / 1000.0  # Convert A to kA
                                i_to_ka = currents[6] / 1000.0
                            else:
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
                            
                            if max_i_ka and max_i_ka > 0:
                                loading_percent = (i_from_ka / max_i_ka) * 100
                            else:
                                # Fallback if max_i_ka not available
                                loading_percent = 0.0

                            # Convert IDs back to hash format for frontend
                            frontend_name = key.replace('_', '#')
                            frontend_id = LinesDictId[key].replace('_', '#')
                            
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
                            break
                        except Exception as e:
                            print(f"    ✗ Error processing line {line_name}: {e}")
                            continue
            except Exception as e:
                print(f"  Error processing line: {e}")
            dss.lines.next()
    
    print(f"  Total lines processed: {len(linesList)}")
    
    # Process load and generator results (static generators are created as Load elements with negative power)
    if dss.loads.count > 0:
        dss.loads.first()
        for _ in range(dss.loads.count):
            try:
                load_name = dss.loads.name
                
                # Process as regular load (static generators are now PVSystem elements)
                if True:
                    for key, value in LoadsDict.items():
                        if value.lower() == load_name.lower() or key.lower() == load_name.lower():
                            try:
                                powers = dss.cktelement.powers
                                if len(powers) >= 6:
                                    p_raw = powers[0] + powers[2] + powers[4]
                                    q_raw = powers[1] + powers[3] + powers[5]
                                    p_mw = p_raw / 1000.0 if not math.isnan(p_raw) else 0.0
                                    q_mvar = q_raw / 1000.0 if not math.isnan(q_raw) else 0.0
                                else:
                                    p_mw = q_mvar = 0.0

                                # Convert IDs back to hash format
                                frontend_name = key.replace('_', '#')
                                frontend_id = LoadsDictId[key].replace('_', '#')
                                
                                load = LoadOut(name=frontend_name, id=frontend_id, p_mw=p_mw, q_mvar=q_mvar)
                                loadsList.append(load)
                                break
                            except Exception as e:
                                print(f"    Error processing load {load_name}: {e}")
                            break
                            
            except Exception as e:
                print(f"  Error processing load/generator: {e}")
            dss.loads.next()
    
    # Process static generators (created as PVSystem elements)
    if dss.pvsystems.count > 0:
        dss.pvsystems.first()
        for _ in range(dss.pvsystems.count):
            try:
                pv_name = dss.pvsystems.name
                
                # Check if this PVSystem is one of our static generators
                for key, value in GeneratorsDict.items():
                    if value.lower() == pv_name.lower() or key.lower() == pv_name.lower():
                        try:
                            # Set this PVSystem as the active circuit element
                            dss.circuit.set_active_element(f"PVSystem.{pv_name}")
                            
                            # Get PV powers
                            powers = dss.cktelement.powers
                            if len(powers) >= 6:
                                # Sum all three phases (powers come in pairs: P1,Q1,P2,Q2,P3,Q3)
                                p_raw = powers[0] + powers[2] + powers[4]
                                q_raw = powers[1] + powers[3] + powers[5]
                                # PVSystem reports power flowing OUT as NEGATIVE (like Generator)
                                # Negate to show positive generation in results
                                p_mw = -(p_raw / 1000.0) if not math.isnan(p_raw) else 0.0
                                q_mvar = -(q_raw / 1000.0) if not math.isnan(q_raw) else 0.0
                            else:
                                p_mw = q_mvar = 0.0

                            # Get voltage from bus
                            vm_pu = 1.0
                            va_degree = 0.0
                            try:
                                pv_bus_name = dss.pvsystems.bus1.split('.')[0]
                                bus_index = None
                                for i in range(dss.circuit.num_buses):
                                    dss.circuit.set_active_bus(i)
                                    if dss.bus.name.lower() == pv_bus_name.lower():
                                        bus_index = i
                                        break
                                if bus_index is not None:
                                    dss.circuit.set_active_bus(bus_index)
                                    bus_angles = dss.bus.vmag_angle_pu
                                    if len(bus_angles) >= 2:
                                        vm_pu = bus_angles[0] if not math.isnan(bus_angles[0]) else 1.0
                                        va_degree = bus_angles[1] if not math.isnan(bus_angles[1]) else 0.0
                            except Exception as e:
                                print(f"    Error getting voltage for PVSystem {pv_name}: {e}")

                            # Convert IDs back to hash format
                            frontend_name = key.replace('_', '#')
                            frontend_id = GeneratorsDictId[key].replace('_', '#')
                            
                            generator = GeneratorOut(
                                name=frontend_name, 
                                id=frontend_id, 
                                p_mw=p_mw, 
                                q_mvar=q_mvar, 
                                va_degree=va_degree, 
                                vm_pu=vm_pu
                            )
                            generatorsList.append(generator)
                            print(f"    ✓ Added PVSystem (static generator): {frontend_name}, P={p_mw:.3f} MW, Q={q_mvar:.3f} MVAr, V={vm_pu:.3f} pu")
                        except Exception as e:
                            print(f"    Error processing PVSystem {pv_name}: {e}")
                        break
            except Exception as e:
                print(f"  Error processing PVSystem: {e}")
            dss.pvsystems.next()
    
    # Process transformer results (matching notebook approach)
    if dss.transformers.count > 0:
        dss.transformers.first()
        for _ in range(dss.transformers.count):
            try:
                trafo_name = dss.transformers.name
                
                for key, value in TransformersDict.items():
                    # OpenDSS lowercases names, so compare case-insensitively
                    if value.lower() == trafo_name.lower() or key.lower() == trafo_name.lower():
                        try:
                            # Get powers (in kW and kvar) for transformer
                            powers = dss.cktelement.powers
                            
                            # Initialize power values
                            p_hv_mw = q_hv_mvar = p_lv_mw = q_lv_mvar = pl_mw = ql_mvar = 0.0
                            
                            if len(powers) >= 12:
                                # HV side (Terminal 1): phases 1, 2, 3
                                p_hv_kw = powers[0] + powers[2] + powers[4]
                                q_hv_kvar = powers[1] + powers[3] + powers[5]
                                # LV side (Terminal 2): phases 1, 2, 3
                                p_lv_kw = powers[6] + powers[8] + powers[10]
                                q_lv_kvar = powers[7] + powers[9] + powers[11]
                                
                                # Convert to MW/MVAr
                                p_hv_mw = p_hv_kw / 1000.0 if not math.isnan(p_hv_kw) else 0.0
                                q_hv_mvar = q_hv_kvar / 1000.0 if not math.isnan(q_hv_kvar) else 0.0
                                p_lv_mw = p_lv_kw / 1000.0 if not math.isnan(p_lv_kw) else 0.0
                                q_lv_mvar = q_lv_kvar / 1000.0 if not math.isnan(q_lv_kvar) else 0.0
                                
                                # Debug: Print raw power values for main transformer
                                if 'mxCell_160' in key or 'mxCell#160' in key:
                                    print(f"    DEBUG Transformer {key}: Raw powers array: {powers[:12]}")
                                    print(f"    P_HV={p_hv_mw:.3f} MW, Q_HV={q_hv_mvar:.3f} MVAr")
                                    print(f"    P_LV={p_lv_mw:.3f} MW, Q_LV={q_lv_mvar:.3f} MVAr")
                                
                                # Calculate losses
                                pl_mw = p_hv_mw + p_lv_mw
                                ql_mvar = q_hv_mvar + q_lv_mvar
                            
                            # Get complex currents [I1_real, I1_imag, I2_real, I2_imag, I3_real, I3_imag, ...] in Amperes
                            currents = dss.cktelement.currents
                            
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
                            # Get transformer rating from OpenDSS properties
                            try:
                                # dss.transformers.kva returns total kVA rating
                                sn_kva = dss.transformers.kva
                                sn_mva = sn_kva / 1000.0
                                # Get HV voltage from first winding
                                dss.transformers.wdg = 1
                                vn_hv_kv = dss.transformers.kv
                                # I_rated = S / (sqrt(3) * V)
                                i_rated_hv_ka = sn_mva / (math.sqrt(3) * vn_hv_kv)
                                loading_percent = (i_hv_ka / i_rated_hv_ka * 100.0) if i_rated_hv_ka > 0 else 0.0
                            except Exception as e:
                                print(f"    Could not calculate loading for {trafo_name}: {e}")
                                loading_percent = 0.0

                            # Convert IDs back to hash format for frontend
                            frontend_name = key.replace('_', '#')
                            frontend_id = TransformersDictId[key].replace('_', '#')
                            
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
                            break
                        except Exception as e:
                            print(f"    ✗ Error processing transformer {trafo_name}: {e}")
                            continue
            except Exception as e:
                print(f"  Error processing transformer: {e}")
            dss.transformers.next()
    
    print(f"  Total transformers processed: {len(transformersList)}")
    
    # Process capacitor results
    if dss.capacitors.count > 0:
        dss.capacitors.first()
        for _ in range(dss.capacitors.count):
            try:
                cap_name = dss.capacitors.name
                for key, value in CapacitorsDict.items():
                    # OpenDSS lowercases names, so compare case-insensitively
                    if value.lower() == cap_name.lower() or key.lower() == cap_name.lower():
                        try:
                            powers = dss.cktelement.powers
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
                                bus_angles = dss.bus.vmag_angle_pu
                                if len(bus_angles) >= 1:
                                    vm_pu = bus_angles[0] if not math.isnan(bus_angles[0]) else 1.0
                                    print(f"    Capacitor {cap_name} bus voltage: vm_pu={vm_pu}")
                            except Exception as e:
                                print(f"    Error getting voltage value for capacitor {cap_name}: {e}")

                            # Convert IDs back to hash format for frontend
                            frontend_name = key.replace('_', '#')
                            frontend_id = CapacitorsDictId[key].replace('_', '#')
                            
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
                            print(f"    Error processing capacitor {cap_name}: {e}")
                            continue
            except Exception as e:
                print(f"  Error processing capacitor: {e}")
            dss.capacitors.next()
    
    # Process shunt results (reactors in OpenDSS)
    # Use alternative method if dss.reactors is not available
    print(f"  Processing reactors: Expected shunts in dict: {list(ShuntsDict.keys())}")
    
    try:
        # Process each expected shunt directly by setting it as active element
        if ShuntsDict:
            for key, value in ShuntsDict.items():
                reactor_name = value  # e.g., 'mxCell_143'
                print(f"    Looking for reactor: {reactor_name}")
                
                try:
                    # Set this specific reactor as active circuit element
                    # Try with original case first, then lowercase if that fails
                    try:
                        dss.circuit.set_active_element(f"Reactor.{reactor_name}")
                    except:
                        # OpenDSS lowercases names, try lowercase
                        dss.circuit.set_active_element(f"Reactor.{reactor_name.lower()}")
                    
                    # Get element info
                    element_name = dss.cktelement.name
                    print(f"      Found reactor element: '{element_name}'")
                    
                    # Get powers
                    powers = dss.cktelement.powers
                    print(f"      Reactor powers array length: {len(powers)}, values: {powers[:6] if len(powers) >= 6 else powers}")
                    
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
                    
                    print(f"      Reactor P={p_mw:.6f} MW, Q={q_mvar:.6f} MVar")

                    # Get voltage value from the shunt's bus
                    vm_pu = 1.0
                    try:
                        # Get the bus that this reactor is connected to
                        bus_names = dss.cktelement.bus_names
                        if len(bus_names) > 0:
                            bus_name = bus_names[0].split('.')[0]  # Remove phase info
                            dss.circuit.set_active_bus(bus_name)
                            bus_angles = dss.bus.vmag_angle_pu
                            if len(bus_angles) >= 1:
                                vm_pu = bus_angles[0] if not math.isnan(bus_angles[0]) else 1.0
                    except Exception as e:
                        pass

                    # Convert IDs back to hash format for frontend
                    frontend_name = key.replace('_', '#')
                    frontend_id = ShuntsDictId[key].replace('_', '#')
                    
                    shunt = ShuntOut(
                        name=frontend_name, 
                        id=frontend_id, 
                        p_mw=p_mw, 
                        q_mvar=q_mvar, 
                        vm_pu=vm_pu
                    )
                    shuntsList.append(shunt)
                    print(f"      ✓ Added shunt: {frontend_name}")
                    
                except Exception as e:
                    print(f"      Reactor {reactor_name} not found or error: {e}")
                    continue
        else:
            print(f"  No reactors found in circuit")
        
    except Exception as e:
        print(f"  Error accessing reactors: {e}")
    
    # Process storage results
    if hasattr(dss, 'storage') and dss.storage.count > 0:
        dss.storage.first()
        for _ in range(dss.storage.count):
            try:
                storage_name = dss.storage.name
                for key, value in StoragesDict.items():
                    # OpenDSS lowercases names, so compare case-insensitively
                    if value.lower() == storage_name.lower() or key.lower() == storage_name.lower():
                        try:
                            powers = dss.cktelement.powers
                            if len(powers) >= 6:
                                p_raw = powers[0] + powers[2] + powers[4]
                                q_raw = powers[1] + powers[3] + powers[5]
                                p_mw = p_raw / 1000.0 if not math.isnan(p_raw) else 0.0
                                q_mvar = q_raw / 1000.0 if not math.isnan(q_raw) else 0.0
                            else:
                                p_mw = q_mvar = 0.0

                            # Convert IDs back to hash format for frontend
                            frontend_name = key.replace('_', '#')
                            frontend_id = StoragesDictId[key].replace('_', '#')
                            
                            storage = StorageOut(
                                name=frontend_name, 
                                id=frontend_id, 
                                p_mw=p_mw, 
                                q_mvar=q_mvar
                            )
                            storagesList.append(storage)
                            break
                        except Exception as e:
                            print(f"    Error processing storage {storage_name}: {e}")
                            continue
                    else:
                        print(f"    Storage {storage_name} not found in StoragesDict")
            except Exception as e:
                print(f"  Error processing storage: {e}")
            dss.storage.next()

    # Process PVSystem results (matching notebook approach)
    if hasattr(dss, 'pvsystems'):
        if dss.pvsystems.count > 0:
            dss.pvsystems.first()
            for _ in range(dss.pvsystems.count):
                try:
                    pvsystem_name = dss.pvsystems.name
                    
                    for key, value in PVSystemsDict.items():
                        # OpenDSS lowercases names, so compare case-insensitively
                        if value.lower() == pvsystem_name.lower() or key.lower() == pvsystem_name.lower():
                            try:
                                # Get powers (in kW and kvar) - sum all three phases
                                powers = dss.cktelement.powers
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
                                    if hasattr(dss.pvsystems, 'irradiance'):
                                        irradiance = dss.pvsystems.irradiance
                                    if hasattr(dss.pvsystems, 'temperature'):
                                        temperature = dss.pvsystems.temperature

                                    # Get voltage from current bus using bus voltage array
                                    bus_angles = dss.bus.vmag_angle_pu
                                    if len(bus_angles) >= 1:
                                        vm_pu = bus_angles[0] if not math.isnan(bus_angles[0]) else 1.0
                                        va_degree = bus_angles[1] if len(bus_angles) > 1 else 0.0
                                except Exception as e:
                                    pass

                                # Convert IDs back to hash format for frontend
                                frontend_name = key.replace('_', '#')
                                frontend_id = PVSystemsDictId[key].replace('_', '#')
                                
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
                                print(f"    ✗ Error processing PVSystem {pvsystem_name}: {e}")
                                continue
                except Exception as e:
                    print(f"  Error processing PVSystem: {e}")
                dss.pvsystems.next()
        
        print(f"  Total PVSystems processed: {len(pvsystemsList)}")
    else:
        print("  No PVSystems interface available in OpenDSS")

    # Process external grid results
    if hasattr(dss, 'vsources') and dss.vsources.count > 0:
        dss.vsources.first()
        for _ in range(dss.vsources.count):
            try:
                vsource_name = dss.vsources.name
                print(f"    Processing VSource: {vsource_name}")

                # Skip system VSources (OpenDSS auto-creates these)
                if vsource_name in ['source', 'sourcebus']:
                    print(f"      ⚠️  Skipping system VSource: {vsource_name}")
                    dss.vsources.next()
                    continue

                # Try to find matching external grid by checking various name formats (case-insensitive)
                matched_key = None
                for key, value in ExternalGridsDict.items():
                    # OpenDSS lowercases names, so compare case-insensitively
                    if (value.lower() == vsource_name.lower() or key.lower() == vsource_name.lower()):
                        matched_key = key
                        break

                if matched_key:
                    try:
                        powers = dss.cktelement.powers
                        if len(powers) >= 6:
                            p_raw = powers[0] + powers[2] + powers[4]
                            q_raw = powers[1] + powers[3] + powers[5]
                            p_mw = p_raw / 1000.0 if not math.isnan(p_raw) else 0.0
                            q_mvar = q_raw / 1000.0 if not math.isnan(q_raw) else 0.0
                        else:
                            p_mw = q_mvar = 0.0

                        # Calculate power factor
                        pf = 1.0
                        if p_mw != 0 or q_mvar != 0:
                            s_mva = math.sqrt(p_mw**2 + q_mvar**2)
                            if s_mva > 0:
                                pf = p_mw / s_mva

                        # Calculate Q/P ratio
                        q_p = 0.0
                        if p_mw != 0:
                            q_p = q_mvar / p_mw

                        # Convert IDs back to hash format for frontend
                        frontend_name = matched_key.replace('_', '#')
                        frontend_id = ExternalGridsDictId[matched_key].replace('_', '#')
                        
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
                        print(f"Error processing external grid {vsource_name}: {e}")
            except Exception as e:
                print(f"  Error processing external grid: {e}")
            dss.vsources.next()
    
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
    
    print(f"OpenDSS results: {len(busbarList)} buses, {len(linesList)} lines, {len(transformersList)} transformers, {len(shuntsList)} shunts, {len(pvsystemsList)} pvsystems, {len(externalGridsList)} external grids")

    # Add OpenDSS commands to result if export was requested
    if export_commands and opendss_commands:
        commands_text = '\n'.join(opendss_commands)
        result['opendss_commands'] = commands_text
        print(f"OpenDSS commands export enabled: {len(opendss_commands)} commands collected")

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
        response = json.dumps(result, default=safe_json_serializer, indent=4)
        print("=== FINAL RESULT ===")
        print(f"Result keys: {list(result.keys())}")
        print(f"Total elements processed: {len(busbarList) + len(linesList) + len(loadsList) + len(transformersList) + len(shuntsList) + len(capacitorsList) + len(generatorsList) + len(storagesList) + len(externalGridsList)}")
        
        return response
    except Exception as json_error:
        print(f"JSON serialization error: {json_error}")
        return json.dumps({"error": "JSON serialization failed", "message": str(json_error)})
        
        #U[pu],angle[degree]
        #print(dss.bus.vmag_angle_pu)    
        #dss.circuit.set_active_element(dss.bus.name)
        #print(dss.cktelement.powers)
        #print(dss.circuit.total_power)
    #P[MW]
    #Q[MVar]
    #PF
        
