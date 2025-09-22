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
    def __init__(self, name: str, id: str, i_hv_ka: float, i_lv_ka: float, loading_percent: float):          
        self.name = name
        self.id = id           
        self.i_hv_ka = i_hv_ka 
        self.i_lv_ka = i_lv_ka
        self.loading_percent = loading_percent
                                                             
                       
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

# Helper functions for OpenDSS element creation
# Frontend sends simple mxCell_ names (mxCell_126, mxCell_129, etc.)
# Frontend now sends bus names in the correct format (mxCell_126)
# OpenDSS may convert bus names to 
def create_busbars(in_data, dss):
    """Create busbars in OpenDSS circuit - Let OpenDSS handle bus creation automatically  when elements are connected"""
    BusbarsDictVoltage = {}  
    BusbarsDictConnectionToName = {}  
   
    
        # Collect bus information from input data for reference
    bus_elements = {}
    for x in in_data:         
        if "Bus" in in_data[x]['typ']:
            # Frontend now sends bus names in the correct format (mxCell_126)
            bus_name = in_data[x]['name']  # This is already mxCell_126
            bus_voltage = in_data[x].get('vn_kv', None)
            bus_elements[bus_name] = bus_name  # mxCell_126 -> mxCell_126
            BusbarsDictVoltage[bus_name] = bus_voltage
    
    # Since we want to use simple names everywhere, just store the bus names directly
    for bus_name in bus_elements.keys():
        # Store the mapping: bus_name (mxCell_126) -> bus_name (mxCell_126)
        BusbarsDictConnectionToName[bus_name] = bus_name  
    
    return BusbarsDictVoltage, BusbarsDictConnectionToName

def create_other_elements(in_data, dss, BusbarsDictVoltage, BusbarsDictConnectionToName):
    """Create other elements in OpenDSS circuit"""
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
                create_line_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LinesDict, LinesDictId, created_elements)
            elif element_type == "Load":
                create_load_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LoadsDict, LoadsDictId, created_elements)
            elif element_type == "Static Generator":
                create_static_generator_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, GeneratorsDict, GeneratorsDictId, created_elements)
            elif element_type == "Asymmetric Static Generator":
                # For OpenDSS, treat asymmetric static generator as a regular static generator
                # We'll use the phase A values as the main values
                create_static_generator_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, GeneratorsDict, GeneratorsDictId, created_elements)
            elif element_type == "Generator":
                create_generator_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, GeneratorsDict, GeneratorsDictId, created_elements)
            elif element_type == "Transformer":
                create_transformer_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, TransformersDict, TransformersDictId, created_elements)
            elif element_type == "Shunt Reactor":
                create_shunt_reactor_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, ShuntsDict, ShuntsDictId, created_elements)
            elif element_type == "Capacitor":
                create_capacitor_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, CapacitorsDict, CapacitorsDictId, created_elements)
            elif element_type == "Storage":
                create_storage_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, StoragesDict, StoragesDictId, created_elements)
            elif element_type == "External Grid":
                create_external_grid_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, created_elements)
                # Store in dictionaries for later reference
                ExternalGridsDict[element_name] = element_name
                ExternalGridsDictId[element_name] = element_id
                
        except Exception as e:
            print(f"Error processing element {x} ({element_type}): {e}")
            continue
    
   
    
    return (LinesDict, LinesDictId, LoadsDict, LoadsDictId, TransformersDict, TransformersDictId, 
            ShuntsDict, ShuntsDictId, CapacitorsDict, CapacitorsDictId, GeneratorsDict, GeneratorsDictId, 
            StoragesDict, StoragesDictId, ExternalGridsDict, ExternalGridsDictId)

# Individual element creation functions
def create_line_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LinesDict, LinesDictId, created_elements):
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
                
            dss.text(line_cmd)
            
            print(f"Command: {line_cmd}")
            
            actual_name = dss.lines.name
            LinesDict[element_name] = actual_name
            LinesDictId[element_name] = element_id
            created_elements.add(element_name)
            
        except Exception as e:
            print(f"  ✗ Error creating line: {e}")
    else:
        print(f"  ✗ Line {element_name} missing bus connections")

def create_load_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, LoadsDict, LoadsDictId, created_elements):
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
            dss.text(load_cmd)
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

def create_static_generator_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, GeneratorsDict, GeneratorsDictId, created_elements):
    """Create a static generator element in OpenDSS"""
   
    
    bus_connection = element_data.get('bus')
    if bus_connection:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_connection_backend = bus_connection
        if bus_connection_backend in BusbarsDictConnectionToName:
            bus_name = BusbarsDictConnectionToName[bus_connection_backend]
        bus_voltage = BusbarsDictVoltage.get(bus_name)
        
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
                # Create static generator command string
                gen_cmd = f"New Generator.{gen_name} Bus1={bus_name} kV={bus_voltage} kW={p_kw} kvar={q_kvar}"

                # Create generator using OpenDSS command
                dss.text(gen_cmd)
                print(f"Command: {gen_cmd}")

                # Configure generator to NOT act as voltage source
                dss.generators.mode = 1  # Power Factor mode
                # Disable voltage control by setting control mode to 0 (no control)
                try:
                    dss.generators.status = 'Variable'  # Set to variable (not fixed)
                except:
                    pass  # Ignore if property doesn't exist
                
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

def create_generator_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, GeneratorsDict, GeneratorsDictId, created_elements):
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
            dss.text(gen_cmd)
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

def create_transformer_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, TransformersDict, TransformersDictId, created_elements):
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
           
            
            # Convert to float
            sn_mva = float(sn_mva_raw)
            vk_percent = float(vk_percent_raw)
            vkr_percent = float(vkr_percent_raw)
            
            # Convert MVA to kVA
            sn_kva = sn_mva * 1000
            
                        # Create complete OpenDSS transformer command with all parameters
            transformer_cmd = f"New Transformer.{element_name} Phases=3 Windings=2 Buses=({bus_from_name} {bus_to_name}) Conns=(wye wye) kVs=({bus_from_voltage} {bus_to_voltage}) kVAs=({sn_kva} {sn_kva}) XHL={vk_percent} %Rs={vkr_percent}"
            
            dss.text(transformer_cmd)
            print(f"Command: {transformer_cmd}")
            
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

def create_shunt_reactor_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, ShuntsDict, ShuntsDictId, created_elements):
    """Create a shunt reactor element in OpenDSS"""

    
    bus_connection = element_data.get('bus')
    if bus_connection:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_connection_backend = bus_connection
        if bus_connection_backend in BusbarsDictConnectionToName:
            bus_name = BusbarsDictConnectionToName[bus_connection_backend]
        # Get voltage from the bus data
        bus_voltage = BusbarsDictVoltage.get(bus_name)
        
    
        
        # Get shunt reactor parameters with proper null handling
        q_mvar_raw = element_data.get('q_mvar')
        
  
        
        # Convert to float
        q_mvar = float(q_mvar_raw)
        
        # Convert to kVar
        q_kvar = q_mvar * 1000
        

        try:
            # Create shunt reactor using bus name directly - OpenDSS will create bus automatically
            simple_cmd = f"New Reactor.{element_name} Bus1={bus_name} R=0 X={abs(q_kvar)} kV={bus_voltage}"
            dss.text(simple_cmd)
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

def create_capacitor_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, CapacitorsDict, CapacitorsDictId, created_elements):
    """Create a capacitor element in OpenDSS"""
  
    
    bus_connection = element_data.get('bus')
    if bus_connection:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_connection_backend = bus_connection
        if bus_connection_backend in BusbarsDictConnectionToName:
            bus_name = BusbarsDictConnectionToName[bus_connection_backend]
        bus_voltage = BusbarsDictVoltage.get(bus_name)
        
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
                dss.text(simple_cmd)
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

def create_storage_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, StoragesDict, StoragesDictId, created_elements):
    """Create a storage element in OpenDSS"""

    bus_connection = element_data.get('bus')
    if bus_connection:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_connection_backend = bus_connection
        if bus_connection_backend in BusbarsDictConnectionToName:
            bus_name = BusbarsDictConnectionToName[bus_connection_backend]
        bus_voltage = BusbarsDictVoltage.get(bus_name)
        
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
                dss.text(simple_cmd)
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
 
def create_external_grid_element(dss, element_data, element_name, element_id, BusbarsDictVoltage, BusbarsDictConnectionToName, created_elements):
    """Create an external grid element in OpenDSS"""

    
    bus_connection = element_data.get('bus')
    if bus_connection:
        # Frontend now sends bus names in the correct format (mxCell_126)
        bus_connection_backend = bus_connection
        if bus_connection_backend in BusbarsDictConnectionToName:
            bus_name = BusbarsDictConnectionToName[bus_connection_backend]
        bus_voltage = BusbarsDictVoltage.get(bus_name)        
     
        # Get external grid parameters
        vm_pu_raw = element_data.get('vm_pu')
        s_sc_max_mva_raw = element_data.get('s_sc_max_mva')
        
        # Convert to float
        vm_pu = float(vm_pu_raw)
        s_sc_max_mva = float(s_sc_max_mva_raw)
        
        try:
            # Create external grid using OpenDSS VSource command
            # Use bus name directly - OpenDSS will create bus automatically
            external_grid_cmd = f"New Vsource.{element_name} Bus1={bus_name} basekv={bus_voltage} pu={vm_pu} mvasc3={s_sc_max_mva} 1000000"
            dss.text(external_grid_cmd)      
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
 
def powerflow(in_data, frequency, algorithm, max_iterations, tolerance, convergence, voltage_control, tap_control):
    """Main powerflow function for OpenDSS - similar structure to pandapower_electrisim.py"""
    
 
    dss = py_dss_interface.DSS()     


    # Set OpenDSS circuit parameters
    f = frequency
    
    # Execute OpenDSS circuit creation and configuration commands
   
    
    # Create new circuit first - OpenDSS requires this before any other commands
    circuit_created = False     
  
    dss.text('clear')    
    dss.text('New Circuit.OpenDSS_Circuit')  
    dss.text(f'set DefaultBaseFrequency={f}')

    # Set additional OpenDSS parameters
    if algorithm == 'PowerFlow':
        dss.text('set Algorithm=PowerFlow')    
    else: 
        dss.text('set Algorithm=Admittance')   
     
    dss.text(f'set MaxIterations={max_iterations}')
    dss.text(f'set Tolerance={tolerance}')
  
    
    # Create busbars using the new helper function
    BusbarsDictVoltage, BusbarsDictConnectionToName = create_busbars(in_data, dss)


    # Create other elements using the new helper function

    (LinesDict, LinesDictId, LoadsDict, LoadsDictId, TransformersDict, TransformersDictId, 
     ShuntsDict, ShuntsDictId, CapacitorsDict, CapacitorsDictId, GeneratorsDict, GeneratorsDictId, 
     StoragesDict, StoragesDictId, ExternalGridsDict, ExternalGridsDictId) = create_other_elements(in_data, dss, BusbarsDictVoltage, BusbarsDictConnectionToName)
    
    
    # Debug: Check what buses OpenDSS has created so far
    print("=== DEBUG: CHECKING BUSES AFTER ELEMENT CREATION ===")
    try:
        print(f"  Expected buses from connection mapping: {list(BusbarsDictConnectionToName.keys())}")
        print(f"  Expected bus names from connection mapping: {list(BusbarsDictConnectionToName.values())}")


        # Show which elements were created and their bus connections
        print("  Created elements summary:")
        if LinesDict:
            print(f"    Lines: {list(LinesDict.keys())}")
        if LoadsDict:
            print(f"    Loads: {list(LoadsDict.keys())}")
        if TransformersDict:
            print(f"    Transformers: {list(TransformersDict.keys())}")
        if ShuntsDict:
            print(f"    Shunts: {list(ShuntsDict.keys())}")
        if CapacitorsDict:
            print(f"    Capacitors: {list(CapacitorsDict.keys())}")
        if GeneratorsDict:
            print(f"    Generators: {list(GeneratorsDict.keys())}")
        if ExternalGridsDict:
            print(f"    External Grids: {list(ExternalGridsDict.keys())}")
            
        # Check if any elements were actually created
        total_elements = (len(LinesDict) + len(LoadsDict) + len(TransformersDict) +
                         len(ShuntsDict) + len(CapacitorsDict) + len(GeneratorsDict) + len(ExternalGridsDict))
        print(f"  Total elements created: {total_elements}")



     

    except Exception as e:
        print(f"  Error checking buses after element creation: {e}")
    print("=== END DEBUG ===")

    

    # Note: OpenDSS creates buses automatically when elements are connected
    # We don't need to explicitly create buses - they are created implicitly
    # when we set the bus1/bus2 properties of elements like lines, loads, etc.

    # Validate circuit before solve

    # Execute solve commands
    print("=== EXECUTING OPENDSS SOLVE COMMANDS ===")
    
    # First, try to calculate voltages
    print("Executing: calcv")
    try:
        dss.text('calcv')
        print("  ✓ Command executed successfully")
    except Exception as e:
        print(f"  ✗ Command failed: {e}")
    
    # Then solve the power flow
    print("Executing: solve")
    try:
        dss.text('solve')
        print("  ✓ Command executed successfully")
    except Exception as e:
        print(f"  ✗ Command failed: {e}")
    
    print("=== END SOLVE COMMANDS ===")
    
    # Print OpenDSS solve function results
    print("=== OPENDSS SOLVE RESULTS ===")
    try:
        # Get solution information
        solution_mode = dss.solution.mode
        print(f"  Solution mode: {solution_mode}")
        
        # Get convergence information
        converged = dss.solution.converged
        print(f"  Solution converged: {converged}")
        
        # Get iteration count
        iterations = dss.solution.iterations
        print(f"  Iterations: {iterations}")
        
        # Get total power
        total_power = dss.circuit.total_power
        print(f"  Total power: {total_power}")
        
        # Get bus count after solve
        bus_count_after = dss.circuit.num_buses
        print(f"  Buses after solve: {bus_count_after}")
        
        # Get element counts after solve
        print(f"  Lines after solve: {dss.lines.count}")
        print(f"  Loads after solve: {dss.loads.count}")
        print(f"  Generators after solve: {dss.generators.count}")
        print(f"  Transformers after solve: {dss.transformers.count}")
        print(f"  Capacitors after solve: {dss.capacitors.count}")
        if hasattr(dss, 'reactors'):
            print(f"  Reactors after solve: {dss.reactors.count}")
        if hasattr(dss, 'storage'):
            print(f"  Storage after solve: {dss.storage.count}")
        if hasattr(dss, 'vsources'):
            print(f"  VSources after solve: {dss.vsources.count}")
        
        # Print bus voltage information after solve
        print("  Bus voltage information after solve:")
        print(f"  Expected buses from input: {list(BusbarsDictConnectionToName.keys())}")
        print(f"  Expected bus names from input: {list(BusbarsDictConnectionToName.values())}")
        
    
        
        # Print line results after solve
        print("  Line results after solve:")
        try:
            if dss.lines.count > 0:
                dss.lines.first()
                for i in range(dss.lines.count):
                    line_name = dss.lines.name
                    print(f"    Line {i}: {line_name}")
                    
                    # Get line power flows
                    try:
                        powers = dss.cktelement.powers
                        if len(powers) >= 12:
                            p_from_raw = powers[0] + powers[2] + powers[4]
                            p_to_raw = powers[6] + powers[8] + powers[10]
                            q_from_raw = powers[1] + powers[3] + powers[5]
                            q_to_raw = powers[7] + powers[9] + powers[11]
                            
                            p_from_mw = p_from_raw / 1000.0 if not math.isnan(p_from_raw) else 0.0
                            p_to_mw = p_to_raw / 1000.0 if not math.isnan(p_to_raw) else 0.0
                            q_from_mvar = q_from_raw / 1000.0 if not math.isnan(q_from_raw) else 0.0
                            q_to_mvar = q_to_raw / 1000.0 if not math.isnan(q_to_raw) else 0.0
                            
                            print(f"      P from: {p_from_mw:.4f} MW, P to: {p_to_mw:.4f} MW")
                            print(f"      Q from: {q_from_mvar:.4f} MVar, Q to: {q_to_mvar:.4f} MVar")
                        else:
                            print(f"      Power data incomplete (length: {len(powers)})")
                    except Exception as e:
                        print(f"      Error getting power data: {e}")
                    
                    # Get line currents
                    try:
                        currents = dss.cktelement.currents_mag_ang
                        if len(currents) >= 12:
                            i_from_raw = currents[0]
                            i_to_raw = currents[6]
                            i_from_ka = i_from_raw if not math.isnan(i_from_raw) else 0.0
                            i_to_ka = i_to_raw if not math.isnan(i_to_raw) else 0.0
                            
                            print(f"      I from: {i_from_ka:.4f} A, I to: {i_to_ka:.4f} A")
                        else:
                            print(f"      Current data incomplete (length: {len(currents)})")
                    except Exception as e:
                        print(f"      Error getting current data: {e}")
                    
                    # Get line losses
                    try:
                        losses = dss.cktelement.losses
                        if len(losses) >= 2:
                            p_loss = losses[0] / 1000.0 if not math.isnan(losses[0]) else 0.0
                            q_loss = losses[1] / 1000.0 if not math.isnan(losses[1]) else 0.0
                            print(f"      Losses: P={p_loss:.4f} MW, Q={q_loss:.4f} MVar")
                        else:
                            print(f"      Loss data incomplete (length: {len(losses)})")
                    except Exception as e:
                        print(f"      Error getting loss data: {e}")
                    
                    dss.lines.next()
            else:
                print("    No lines found in circuit")
        except Exception as e:
            print(f"    Error getting line results: {e}")
        
        # State solve success/failure
        print("  === SOLVE STATUS SUMMARY ===")
        if converged:
            print("  ✅ SOLVE SUCCESSFUL - Power flow converged")
            print(f"     Converged in {iterations} iterations")
            print(f"     Solution mode: {solution_mode}")
        else:
            print("  ❌ SOLVE FAILED - Power flow did not converge")
            print(f"     Stopped after {iterations} iterations")
            print(f"     Solution mode: {solution_mode}")
            print("  ⚠️  Results may be incomplete or incorrect due to solve failure")
            print("  =================================")
            
        # If solve failed, try to provide some diagnostic information
        if not converged:
            print("  === SOLVE FAILURE DIAGNOSTICS ===")
            try:
                # Check if we have any voltage sources
                if hasattr(dss, 'vsources'):
                    print(f"    Voltage sources count: {dss.vsources.count}")
                    if dss.vsources.count > 0:
                        dss.vsources.first()
                        print(f"    First voltage source: {dss.vsources.name}")
                        print(f"    Base kV: {dss.vsources.basekv}")
                        print(f"    PU: {dss.vsources.pu}")
                
                # Check bus voltages to see if they're all zero or NaN
                print(f"    Checking bus voltages for diagnostic purposes:")
                for i in range(min(dss.circuit.num_buses, 5)):  # Check first 5 buses
                    try:
                        dss.circuit.set_active_bus(i)
                        bus_name = dss.bus.name
                        if hasattr(dss.bus, 'vmag_angle_pu'):
                            vmag_angle = dss.bus.vmag_angle_pu
                            if len(vmag_angle) >= 2:
                                vm_pu = vmag_angle[0]
                                va_degree = vmag_angle[1]
                                print(f"      Bus {i} ({bus_name}): vm_pu={vm_pu}, va_degree={va_degree}")
                            else:
                                print(f"      Bus {i} ({bus_name}): voltage data incomplete")
                        else:
                            print(f"      Bus {i} ({bus_name}): no voltage data available")
                    except Exception as e:
                        print(f"      Bus {i}: error accessing voltage data: {e}")
                
                print("    === END SOLVE FAILURE DIAGNOSTICS ===")
            except Exception as e:
                print(f"    Error during diagnostics: {e}")
            
    except Exception as e:
        print(f"  Error getting solve results: {e}")
    
    print("=== END OPENDSS SOLVE RESULTS ===")
    
    # Process results using the new output classes
    print("=== PROCESSING RESULTS ===")
    
    # Debug OpenDSS circuit state
    try:
        print(f"OpenDSS circuit state:")
        print(f"  Lines count: {dss.lines.count}")
        print(f"  Loads count: {dss.loads.count}")
        print(f"  Generators count: {dss.generators.count}")
        print(f"  Transformers count: {dss.transformers.count}")
        print(f"  Capacitors count: {dss.capacitors.count}")
        if hasattr(dss, 'reactors'):
            print(f"  Reactors count: {dss.reactors.count}")
        if hasattr(dss, 'storage'):
            print(f"  Storage count: {dss.storage.count}")
    except Exception as e:
        print(f"Error checking OpenDSS circuit state: {e}")
    
    # Initialize result lists
    busbarList = []
    linesList = []
    loadsList = []
    transformersList = []
    shuntsList = []
    capacitorsList = []
    generatorsList = []
    storagesList = []
    externalGridsList = []
    
    # Process bus results using actual OpenDSS data
    print("=== PROCESSING BUS RESULTS ===")
    try:
        print(f"OpenDSS circuit buses: {dss.circuit.buses_names}")
        print(f"Expected buses from input: {list(BusbarsDictConnectionToName.values())}")
        print(f"OpenDSS bus names (lowercase): {[name.lower() for name in dss.circuit.buses_names]}")
        print(f"Expected bus names (lowercase): {[name.lower() for name in BusbarsDictConnectionToName.values()]}")
        
                # Process bus results by directly matching OpenDSS bus names to our expected names
        print(f"Matching OpenDSS buses to expected buses:")
        expected_buses_processed = 0

        # Get all OpenDSS bus names and try to match them to our expected buses
        for i in range(dss.circuit.num_buses):
            try:
                dss.circuit.set_active_bus(i)
                open_dss_bus_name = dss.bus.name
                # If bus name is empty, try to get it from the buses_names list
                if not open_dss_bus_name and i < len(dss.circuit.buses_names):
                    open_dss_bus_name = dss.circuit.buses_names[i]
                print(f"  OpenDSS Bus {i}: '{open_dss_bus_name}'")

                # Skip system buses (like 'sourcebus', '0', etc.)
                if open_dss_bus_name in ['sourcebus', '0', 'source']:
                    print(f"    ⚠️  Skipping system bus: {open_dss_bus_name}")
                    continue

                # Try to find which of our expected buses this matches
                matched_expected_bus = None
                for expected_bus_id, expected_bus_name in BusbarsDictConnectionToName.items():
                    # Try different matching strategies:
                    # 1. Exact match
                    if open_dss_bus_name == expected_bus_name:
                        matched_expected_bus = (expected_bus_id, expected_bus_name)
                        print(f"    ✓ Exact match: {open_dss_bus_name} == {expected_bus_name}")
                        break
                    # 2. Case-insensitive match (OpenDSS converts to lowercase)
                    elif open_dss_bus_name.lower() == expected_bus_name.lower():
                        matched_expected_bus = (expected_bus_id, expected_bus_name)
                        print(f"    ✓ Case-insensitive match: {open_dss_bus_name} ≈ {expected_bus_name}")
                        break
                    # 3. Match without underscores (OpenDSS might remove them)
                    elif open_dss_bus_name.replace('_', '') == expected_bus_name.replace('_', ''):
                        matched_expected_bus = (expected_bus_id, expected_bus_name)
                        print(f"    ✓ Name match (ignoring underscores): {open_dss_bus_name} ≈ {expected_bus_name}")
                        break

                if matched_expected_bus:
                    expected_bus_id, expected_bus_name = matched_expected_bus
                    try:
                        # Get actual voltage values from OpenDSS
                        vm_pu = dss.bus.vmag_angle_pu[0]
                        va_degree = dss.bus.vmag_angle_pu[1]
                        print(f"    Voltage: vm_pu={vm_pu}, va_degree={va_degree}")

                        # Frontend now expects bus names in underscore format (mxCell_126)
                        frontend_bus_name = expected_bus_name  # Already in correct format
                        busbar = BusbarOut(
                            name=frontend_bus_name,  # Use underscore format (mxCell_126)
                            id=frontend_bus_name,   # Use underscore format (mxCell_126) so frontend can find cells
                            vm_pu=vm_pu,
                            va_degree=va_degree
                        )
                        busbarList.append(busbar)
                        print(f"    ✓ Added bus result: {expected_bus_name} -> {frontend_bus_name}")
                        expected_buses_processed += 1

                    except Exception as e:
                        print(f"    Error getting voltage data for bus {open_dss_bus_name}: {e}")
                        # Add with default values
                        frontend_bus_name = expected_bus_name.replace('_', '#')
                        busbar = BusbarOut(
                            name=frontend_bus_name,
                            id=frontend_bus_name,
                            vm_pu=1.0,
                            va_degree=0.0
                        )
                        busbarList.append(busbar)
                        print(f"    ✓ Added bus result with defaults: {expected_bus_name} -> {frontend_bus_name}")
                        expected_buses_processed += 1
                else:
                    print(f"    ⚠️  No match found for OpenDSS bus '{open_dss_bus_name}'")

            except Exception as e:
                print(f"  Error accessing OpenDSS bus {i}: {e}")

        # Handle any expected buses that weren't found in OpenDSS
        processed_bus_names = [bus.name.replace('#', '_') for bus in busbarList]
        for expected_bus_id, expected_bus_name in BusbarsDictConnectionToName.items():
            if expected_bus_name not in processed_bus_names:
                print(f"  ⚠️  Expected bus {expected_bus_name} not found in OpenDSS - adding with defaults")
                frontend_bus_name = expected_bus_name.replace('_', '#')
                busbar = BusbarOut(
                    name=frontend_bus_name,
                    id=frontend_bus_name,
                    vm_pu=1.0,
                    va_degree=0.0
                )
                busbarList.append(busbar)
                print(f"    ✓ Added missing bus with defaults: {expected_bus_name} -> {frontend_bus_name}")
                expected_buses_processed += 1

        print(f"  Total expected buses processed: {expected_buses_processed}")
        print(f"  Total buses in results: {len(busbarList)}")
                
    except Exception as e:
        print(f"Error processing bus results: {e}")
        # Fallback to default processing if OpenDSS bus access fails
        print("Falling back to default bus processing...")
        for bus_name in BusbarsDictConnectionToName.keys():
            try:
                print(f"  Processing expected bus: {bus_name}")
                vm_pu = 1.0
                va_degree = 0.0
                
                # Frontend now expects bus names in underscore format (mxCell_126)
                frontend_bus_name = bus_name  # Already in correct format
                busbar = BusbarOut(
                    name=frontend_bus_name,  # Use underscore format (mxCell_126)
                    id=frontend_bus_name,   # Use underscore format (mxCell_126) so frontend can find cells
                    vm_pu=vm_pu, 
                    va_degree=va_degree
                )
                busbarList.append(busbar)
                
            except Exception as e2:
                print(f"  Error processing bus {bus_name}: {e2}")
                continue
    
    # Process line results
    if dss.lines.count > 0:
        dss.lines.first()
        for _ in range(dss.lines.count):
            try:
                line_name = dss.lines.name
                # Find matching line in our dictionary
                for key, value in LinesDict.items():
                    if value == line_name or key == line_name:
                        try:
                            powers = dss.cktelement.powers
                            if len(powers) >= 12:
                                p_from_raw = powers[0] + powers[2] + powers[4]
                                p_to_raw = powers[6] + powers[8] + powers[10]
                                q_from_raw = powers[1] + powers[3] + powers[5]
                                q_to_raw = powers[7] + powers[9] + powers[11]

                                p_from_mw = p_from_raw / 1000.0 if not math.isnan(p_from_raw) else 0.0
                                p_to_mw = p_to_raw / 1000.0 if not math.isnan(p_to_raw) else 0.0
                                q_from_mvar = q_from_raw / 1000.0 if not math.isnan(q_from_raw) else 0.0
                                q_to_mvar = q_to_raw / 1000.0 if not math.isnan(q_to_raw) else 0.0
                            else:
                                p_from_mw = p_to_mw = q_from_mvar = q_to_mvar = 0.0

                            currents = dss.cktelement.currents_mag_ang
                            if len(currents) >= 12:
                                i_from_raw = currents[0]
                                i_to_raw = currents[6]
                                i_from_ka = i_from_raw if not math.isnan(i_from_raw) else 0.0
                                i_to_ka = i_to_raw if not math.isnan(i_to_raw) else 0.0
                            else:
                                i_from_ka = i_to_ka = 0.0

                            # Calculate loading percentage (simplified)
                            loading_percent = 0.0
                            if i_from_ka > 0:
                                loading_percent = (i_from_ka / 1.0) * 100  # Assuming 1.0 kA is 100% loading

                            line = LineOut(
                                name=key, 
                                id=LinesDictId[key], 
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
                            print(f"    Error processing line {line_name}: {e}")
                            continue
            except Exception as e:
                print(f"  Error processing line: {e}")
            dss.lines.next()
    
    # Process load results
    if dss.loads.count > 0:
        dss.loads.first()
        for _ in range(dss.loads.count):
            try:
                load_name = dss.loads.name
                for key, value in LoadsDict.items():
                    if value == load_name or key == load_name:
                        try:
                            powers = dss.cktelement.powers
                            if len(powers) >= 6:
                                p_raw = powers[0] + powers[2] + powers[4]
                                q_raw = powers[1] + powers[3] + powers[5]
                                p_mw = p_raw / 1000.0 if not math.isnan(p_raw) else 0.0
                                q_mvar = q_raw / 1000.0 if not math.isnan(q_raw) else 0.0
                            else:
                                p_mw = q_mvar = 0.0

                            load = LoadOut(name=key, id=LoadsDictId[key], p_mw=p_mw, q_mvar=q_mvar)
                            loadsList.append(load)
                            break
                        except Exception as e:
                            print(f"    Error processing load {load_name}: {e}")
                            continue
            except Exception as e:
                print(f"  Error processing load: {e}")
            dss.loads.next()
    
    # Process generator results
    if dss.generators.count > 0:
        dss.generators.first()
        for _ in range(dss.generators.count):
            try:
                gen_name = dss.generators.name
                for key, value in GeneratorsDict.items():
                    if value == gen_name or key == gen_name:
                        try:
                            powers = dss.cktelement.powers
                            if len(powers) >= 6:
                                p_raw = powers[0] + powers[2] + powers[4]
                                q_raw = powers[1] + powers[3] + powers[5]
                                p_mw = p_raw / 1000.0 if not math.isnan(p_raw) else 0.0
                                q_mvar = q_raw / 1000.0 if not math.isnan(q_raw) else 0.0
                            else:
                                p_mw = q_mvar = 0.0

                            # Get voltage values from the generator's bus
                            vm_pu = 1.0
                            va_degree = 0.0
                            try:
                                # Get the generator's bus name and find the corresponding bus index
                                gen_bus_name = dss.generators.bus1
                                # Find the bus index by name
                                bus_index = None
                                for i in range(dss.circuit.num_buses):
                                    dss.circuit.set_active_bus(i)
                                    if dss.bus.name == gen_bus_name:
                                        bus_index = i
                                        break
                                
                                if bus_index is not None:
                                    dss.circuit.set_active_bus(bus_index)
                                    bus_angles = dss.bus.vmag_angle_pu
                                    if len(bus_angles) >= 2:
                                        vm_pu = bus_angles[0] if not math.isnan(bus_angles[0]) else 1.0
                                        va_degree = bus_angles[1] if not math.isnan(bus_angles[1]) else 0.0
                                        print(f"    Generator {gen_name} bus voltage: vm_pu={vm_pu}, va_degree={va_degree}")
                                else:
                                    print(f"    Could not find bus index for generator {gen_name} bus {gen_bus_name}")
                            except Exception as e:
                                print(f"    Error getting voltage values for generator {gen_name}: {e}")

                            generator = GeneratorOut(
                                name=key, 
                                id=GeneratorsDictId[key], 
                                p_mw=p_mw, 
                                q_mvar=q_mvar, 
                                va_degree=va_degree, 
                                vm_pu=vm_pu
                            )
                            generatorsList.append(generator)
                            break
                        except Exception as e:
                            print(f"    Error processing generator {gen_name}: {e}")
                            continue
            except Exception as e:
                print(f"  Error processing generator: {e}")
            dss.generators.next()
    
    # Process transformer results
    if dss.transformers.count > 0:
        dss.transformers.first()
        for _ in range(dss.transformers.count):
            try:
                trafo_name = dss.transformers.name
                for key, value in TransformersDict.items():
                    if value == trafo_name or key == trafo_name:
                        try:
                            currents = dss.cktelement.currents
                            if len(currents) >= 6:
                                i_hv_raw = currents[0] + currents[2] + currents[4]
                                i_lv_raw = currents[1] + currents[3] + currents[5]
                                i_hv_ka = i_hv_raw / 1000.0 if not math.isnan(i_hv_raw) else 0.0
                                i_lv_ka = i_lv_raw / 1000.0 if not math.isnan(i_lv_raw) else 0.0
                            else:
                                i_hv_ka = i_lv_ka = 0.0

                            # Calculate loading percentage (simplified)
                            loading_percent = 0.0
                            if i_hv_ka > 0:
                                loading_percent = (i_hv_ka / 1.0) * 100  # Assuming 1.0 kA is 100% loading

                            transformer = TransformerOut(
                                name=key, 
                                id=TransformersDictId[key], 
                                i_hv_ka=i_hv_ka, 
                                i_lv_ka=i_lv_ka, 
                                loading_percent=loading_percent
                            )
                            transformersList.append(transformer)
                            break
                        except Exception as e:
                            print(f"    Error processing transformer {trafo_name}: {e}")
                            continue
            except Exception as e:
                print(f"  Error processing transformer: {e}")
            dss.transformers.next()
    
    # Process capacitor results
    if dss.capacitors.count > 0:
        dss.capacitors.first()
        for _ in range(dss.capacitors.count):
            try:
                cap_name = dss.capacitors.name
                for key, value in CapacitorsDict.items():
                    if value == cap_name or key == cap_name:
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

                            capacitor = CapacitorOut(
                                name=key, 
                                id=CapacitorsDictId[key], 
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
    
    # Process shunt results
    if hasattr(dss, 'reactors') and dss.reactors.count > 0:
        dss.reactors.first()
        for _ in range(dss.reactors.count):
            try:
                shunt_name = dss.reactors.name
                for key, value in ShuntsDict.items():
                    if value == shunt_name or key == shunt_name:
                        try:
                            powers = dss.cktelement.powers
                            if len(powers) >= 6:
                                p_raw = powers[0] + powers[2] + powers[4]
                                q_raw = powers[1] + powers[3] + powers[5]
                                p_mw = p_raw / 1000.0 if not math.isnan(p_raw) else 0.0
                                q_mvar = q_raw / 1000.0 if not math.isnan(q_raw) else 0.0
                            else:
                                p_mw = q_mvar = 0.0

                            # Get voltage value from the shunt's bus
                            vm_pu = 1.0
                            try:
                                # Set the active bus to the shunt's bus to get voltage value
                                # Note: We need to find the bus index for this shunt
                                # For now, using default value until we can map shunt to bus
                                bus_angles = dss.bus.vmag_angle_pu
                                if len(bus_angles) >= 1:
                                    vm_pu = bus_angles[0] if not math.isnan(bus_angles[0]) else 1.0
                                    print(f"    Shunt {shunt_name} bus voltage: vm_pu={vm_pu}")
                            except Exception as e:
                                print(f"    Error getting voltage value for shunt {shunt_name}: {e}")

                            shunt = ShuntOut(
                                name=key, 
                                id=ShuntsDictId[key], 
                                p_mw=p_mw, 
                                q_mvar=q_mvar, 
                                vm_pu=vm_pu
                            )
                            shuntsList.append(shunt)
                            break
                        except Exception as e:
                            print(f"    Error processing shunt {shunt_name}: {e}")
                            continue
            except Exception as e:
                print(f"  Error processing shunt: {e}")
            dss.reactors.next()
    
    # Process storage results
    if hasattr(dss, 'storage') and dss.storage.count > 0:
        dss.storage.first()
        for _ in range(dss.storage.count):
            try:
                storage_name = dss.storage.name
                for key, value in StoragesDict.items():
                    if value == storage_name or key == storage_name:
                        try:
                            powers = dss.cktelement.powers
                            if len(powers) >= 6:
                                p_raw = powers[0] + powers[2] + powers[4]
                                q_raw = powers[1] + powers[3] + powers[5]
                                p_mw = p_raw / 1000.0 if not math.isnan(p_raw) else 0.0
                                q_mvar = q_raw / 1000.0 if not math.isnan(q_raw) else 0.0
                            else:
                                p_mw = q_mvar = 0.0

                            storage = StorageOut(
                                name=key, 
                                id=StoragesDictId[key], 
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

                # Try to find matching external grid by checking various name formats
                matched_key = None
                for key, value in ExternalGridsDict.items():
                    # Check different matching possibilities
                    if (value == vsource_name or
                        key == vsource_name or
                        key.lower() == vsource_name.lower() or
                        value.lower() == vsource_name.lower()):
                        matched_key = key
                        print(f"      ✓ Matched VSource {vsource_name} to External Grid {key}")
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

                        externalGrid = ExternalGridOut(
                            name=matched_key,
                            id=ExternalGridsDictId[matched_key],
                            p_mw=p_mw,
                            q_mvar=q_mvar,
                            pf=pf,
                            q_p=q_p
                        )
                        externalGridsList.append(externalGrid)
                        print(f"      ✓ Added external grid result: {matched_key}")
                    except Exception as e:
                        print(f"    Error processing external grid {vsource_name}: {e}")
                else:
                    print(f"    ⚠️  External Grid {vsource_name} not found in ExternalGridsDict")
                    print(f"      Available External Grids: {list(ExternalGridsDict.keys())}")
            except Exception as e:
                print(f"  Error processing external grid: {e}")
            dss.vsources.next()
    
    print("=== END PROCESSING RESULTS ===")

    # Build final result using simplified structure (no output classes)
    print("=== BUILDING FINAL RESULT ===")
    result = {}
    
    if busbarList:
        result['busbars'] = busbarList
        print(f"Added {len(busbarList)} bus results")
    
    if linesList:
        result['lines'] = linesList
        print(f"Added {len(linesList)} line results")
    
    if loadsList:
        result['loads'] = loadsList
        print(f"Added {len(loadsList)} load results")
    
    if transformersList:
        result['transformers'] = transformersList
        print(f"Added {len(transformersList)} transformer results")
    
    if shuntsList:
        result['shunts'] = shuntsList
        print(f"Added {len(shuntsList)} shunt results")
    
    if capacitorsList:
        result['capacitors'] = capacitorsList
        print(f"Added {len(capacitorsList)} capacitor results")
    
    if generatorsList:
        result['generators'] = generatorsList
        print(f"Added {len(generatorsList)} generator results")
    
    if storagesList:
        result['storages'] = storagesList
        print(f"Added {len(storagesList)} storage results")
    
    if externalGridsList:
        result['externalgrids'] = externalGridsList
        print(f"Added {len(externalGridsList)} external grid results")
    
    print("=== END BUILDING FINAL RESULT ===")

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
        
