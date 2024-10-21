import py_dss_interface
from typing import List
import math
import json


#you don't have to create busbars, they are already defined in other element
#def create_other_elements(in_data,x):




def powerflow(in_data, frequency):

    dss = py_dss_interface.DSS()

    f=frequency
    com_frequency = [
        'clear',
        f'set DefaultBaseFrequency={f}',
    ]
    #dss.text(com_frequency)

    BusbarsDict = {}
    BusbarsDictId = {}
    BusbarsDictVoltage = {}  
    nBusbar = int(0)

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

    command_line = [] 
    command_load = []
    command_transformer = []
    command_shunt = []
    command_capacitor = []
    command_generator = []
    command_storage = []

    #tworzę dictionary Busbar i przypisuję nazwom szyn cyfry int (ponieważ tylko one mogą być używane przez py_dss_interface)
    #przykład przypisania: {''mxCell_88'': 0, ''mxCell_99'': 1}
    for x in in_data:         
        if "Bus" in in_data[x]['typ']:
            BusbarsDict[in_data[x]['name']]=nBusbar
            BusbarsDictId[in_data[x]['name']] = in_data[x]['id']
            nBusbar=nBusbar+1
            BusbarsDictVoltage[in_data[x]['name']]= in_data[x]['vn_kv']            
    print(BusbarsDict)   

    #dla innych elementów muszę odpowiednio nazwać elementy 
    for x in in_data:         
        if "Line" in in_data[x]['typ']:
            LinesDict[in_data[x]['name']]=in_data[x]['name'].lower()
            LinesDictId[in_data[x]['name']] = in_data[x]['id']
        if "Load" in in_data[x]['typ']:
            LoadsDict[in_data[x]['name']]=in_data[x]['name'].lower()
            LoadsDictId[in_data[x]['name']] = in_data[x]['id']
        if "Transformer" in in_data[x]['typ']:
            TransformersDict[in_data[x]['name']]=in_data[x]['name'].lower()
            TransformersDictId[in_data[x]['name']] = in_data[x]['id']
        if "Shunt" in in_data[x]['typ']:
            ShuntsDict[in_data[x]['name']]=in_data[x]['name'].lower()
            ShuntsDictId[in_data[x]['name']] = in_data[x]['id']
        if "Capacitor" in in_data[x]['typ']:
            CapacitorsDict[in_data[x]['name']]=in_data[x]['name'].lower()
            CapacitorsDictId[in_data[x]['name']] = in_data[x]['id']
        if "Generator" in in_data[x]['typ']:
            GeneratorsDict[in_data[x]['name']]=in_data[x]['name'].lower()
            GeneratorsDictId[in_data[x]['name']] = in_data[x]['id']
        if "Storage" in in_data[x]['typ']:
            StoragesDict[in_data[x]['name']]=in_data[x]['name'].lower()
            StoragesDictId[in_data[x]['name']] = in_data[x]['id']



    for x in in_data:
        if (in_data[x]['typ'].startswith("External Grid")):
            name=in_data[x]['name']
            id=in_data[x]['id']
            #bus=in_data[x]['bus']

            for key, value in BusbarsDict.items():
                if key == in_data[x]['bus']:
                    bus=value
            for key, value in BusbarsDictVoltage.items():
                if key == in_data[x]['bus']:
                    basekv=value
       

            vm_pu=in_data[x]['vm_pu']
            s_sc_max_mva=eval(in_data[x]['s_sc_max_mva'])
            
            #BasekV musisz wziąć szyny do której jest przyłączana external grid - DO ZROBIENIA
            #Basekv=115 - na razie działa bez tego 
            com_externalgrid = [
                f'New Circuit.{name} bus1={bus} Basekv={basekv} pu={vm_pu}  mvasc3={s_sc_max_mva}  1000000', 
            ]
            #com_externalgrid.extend(com_externalgrid)
            #dss.text(com_externalgrid)
        
        if (in_data[x]['typ'].startswith("Line")):  

            name=in_data[x]['name']
            #print('Linia name')
            #print(name)

            for key, value in BusbarsDict.items():
                if key == in_data[x]['busFrom']:
                    from_bus=value
                if key == in_data[x]['busTo']:
                    to_bus=value

            r_ohm_per_km=in_data[x]['r_ohm_per_km']
            x_ohm_per_km=in_data[x]['x_ohm_per_km']
            c_nf_per_km= in_data[x]['c_nf_per_km']
            length_km=in_data[x]['length_km']
            #g_us_per_km= in_data[x]['g_us_per_km']
            r0_ohm_per_km=in_data[x]['r0_ohm_per_km'] 
            x0_ohm_per_km=in_data[x]['x0_ohm_per_km']
            c0_nf_per_km=0

            #Lines in ohms @ 115 kV
            com_line = [
                f'New Line.{name} phases=3 Bus1={from_bus}  Bus2={to_bus}  R1={r_ohm_per_km}   X1={x_ohm_per_km}    R0={r0_ohm_per_km}   X0={x0_ohm_per_km}   C1={c_nf_per_km}  C0={c0_nf_per_km} Length={length_km} units=km',
            ]
            command_line.extend(com_line)
            #dss.text(com_line)

        if (in_data[x]['typ'].startswith("Load")):

            name=in_data[x]['name']

            for key, value in BusbarsDict.items():
                if key == in_data[x]['bus']:
                    bus=value
            for key, value in BusbarsDictVoltage.items():
                if key == in_data[x]['bus']:
                    basekv=value            
                                   
            p_kw=float(in_data[x]['p_mw'])*1000
            q_kvar=float(in_data[x]['q_mvar'])*1000 #negative sign due to different interpretation of reactive power between openDSS and Pandapower
                    
            #napięcie weź z przyłączonej szyny 

            com_load = [
                f'New load.{name}  phases=3  bus1={bus}  kV={basekv}  kW={p_kw}  kvar={q_kvar} ',
            ]
            command_load.extend(com_load)
            #dss.text(com_load)
        
        
        if (in_data[x]['typ'].startswith("Transformer")):
            name=in_data[x]['name']
       
            vn_hv_kv = in_data[x]['vn_hv_kv']
            vn_lv_kv = in_data[x]['vn_lv_kv']
            sn_kva = float(in_data[x]['sn_mva'])*1000

            #BusbarsDict = {'mxCell_84': 0, 'mxCell_87': 1, 'mxCell_94': 2}
            for key, value in BusbarsDict.items():
                if key == in_data[x]['hv_bus']:
                    hv_bus=value
                if key == in_data[x]['lv_bus']:
                    lv_bus=value    
        

            #vector group do ogarniecia
            #do ogarniecia XHL i inne pozostałe parametry trafo
            com_transformer = [
                f'New transformer.{name}  phases=3 windings=2 buses=({hv_bus} {lv_bus}) conns="delta wye" kVs="{vn_hv_kv} {vn_lv_kv}" kvas="{sn_kva} {sn_kva}" XHL=7',
            ]

            #tu może lepsze rozwiązanie w definiowaniu transformatora
            #New Transformer.wind_up  phases=3 xhl=5.750000  
            #~ wdg=1 bus=trafo_wind kV=0.69 kVA=750.000000 conn=wye
            #~ wdg=2 bus=680 kV=4.16 kVA=750.000000 conn=wye
            command_transformer.extend(com_transformer)

        if (in_data[x]['typ'].startswith("Shunt")):
            name=in_data[x]['name']
            q_kvar=float(in_data[x]['q_mvar'])*1000
            vn_kv=in_data[x]['vn_kv']
            bus=in_data[x]['bus']

            #przelicz R z mocy p_mw
            #nie specyfikujemy  bus2 dla delta (LL) connection 
            com_shunt = [
                f'New Reactor.{name}  phases=3 bus1={bus}  kv={vn_kv} kvar={q_kvar} R=0.3',
            ]
            command_shunt.extend(com_shunt)

        if (in_data[x]['typ'].startswith("Capacitor")):
            name=in_data[x]['name']
            q_kvar=float(in_data[x]['q_mvar'])*1000

            for key, value in BusbarsDict.items():
                if key == in_data[x]['bus']:
                    bus=value
            for key, value in BusbarsDictVoltage.items():
                if key == in_data[x]['bus']:
                    vn_kv=value 

            #vn_kv=in_data[x]['vn_kv']
            #bus=in_data[x]['bus']

            com_capacitor = [
                f'New Capacitor.{name} Bus1={bus} phases=3 kvar={q_kvar} kV={vn_kv}',
            ]
            command_capacitor.extend(com_capacitor)

        if (in_data[x]['typ'].startswith("Generator")):
            name=in_data[x]['name'] 
            bus=in_data[x]['bus']
            vn_kv=in_data[x]['vn_kv']
            p_kw = float(in_data[x]['p_mw'])*1000
            vm_pu = in_data[x]['vm_pu']           
            
            #zaktualizuj parametr o nazwie model 
            com_generator = [
                f'New Generator.{name}  phases=3 bus1={bus}   kV={vn_kv} kW={p_kw}  model=3  Vpu={vm_pu}',
            ]
            command_generator.extend(com_generator)     

        if (in_data[x]['typ'].startswith("Storage")):
            name=in_data[x]['name']
            bus=in_data[x]['bus']
            p_kw = float(in_data[x]['p_mw'])*1000
            max_e_kwh = float(in_data[x]['max_e_mwh'])*1000

            com_storage = [
                f'New Storage.{name} phases=3 Bus1={bus} kV={vn_kv} kWrated={p_kw}  kWhrated={max_e_kwh}',
            ]
            command_storage.extend(com_storage)        
    
    com_solve = [        
        'calcv',
        'solve',                
    ]
    
    com_frequency.extend(com_externalgrid)
    com_frequency.extend(command_line)
    com_frequency.extend(command_load)
    com_frequency.extend(command_transformer)
    com_frequency.extend(command_shunt)
    com_frequency.extend(command_capacitor)
    com_frequency.extend(command_generator)
    com_frequency.extend(command_storage)


    com_frequency.extend(com_solve)

    for cmd in com_frequency:
     print(cmd)
     dss.text(cmd) 


    class BusbarOut(object):
        def __init__(self, name: str, id: str, vm_pu: float, va_degree: float):#, ,   , p_mw: float, q_mvar: float, pf: float, q_p: float):          
            self.name = name
            self.id = id
            self.vm_pu = vm_pu
            self.va_degree = va_degree   
            #self.p_mw = p_mw
            #self.q_mvar = q_mvar  
            #self.pf = pf #p_mw/math.sqrt(math.pow(p_mw,2)+math.pow(q_mvar,2))  
            #self.q_p = q_p
                        
    class BusbarsOut(object):
        def __init__(self, busbars: List[BusbarOut]):
            self.busbars = busbars             
    busbarList = list()

    class LineOut(object):
        def __init__(self, name: str, id: str, p_from_mw: float, q_from_mvar: float, p_to_mw: float, q_to_mvar: float, i_from_ka: float, i_to_ka: float): #loading_percent: float
            self.name = name
            self.id= id
            self.p_from_mw = p_from_mw
            self.q_from_mvar = q_from_mvar 
            self.p_to_mw = p_to_mw 
            self.q_to_mvar = q_to_mvar            
            self.i_from_ka = i_from_ka 
            self.i_to_ka = i_to_ka               
            #self.loading_percent = loading_percent 
                       
    class LinesOut(object):
        def __init__(self, lines: List[LineOut]):
                self.lines = lines
    linesList = list()

    class GeneratorOut(object):
        def __init__(self, name: str, id: str, p_mw: float, q_mvar: float, va_degree: float, vm_pu: float):          
            self.name = name
            self.id = id
            self.p_mw = p_mw 
            self.q_mvar = q_mvar                                  
                       
    class GeneratorsOut(object):
        def __init__(self, generators: List[GeneratorOut]):
            self.generators = generators             
    generatorsList = list()

    class TransformerOut(object):
        def __init__(self, name: str, id: str, i_hv_ka: float, i_lv_ka: float):          
            self.name = name
            self.id = id           
            self.i_hv_ka = i_hv_ka 
            self.i_lv_ka = i_lv_ka          
            
                                                             
                       
    class TransformersOut(object):
        def __init__(self, transformers: List[TransformerOut]):
            self.transformers = transformers             
    transformersList = list()

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
    shuntsList = list() 
                
                
    class CapacitorOut(object):
        def __init__(self, name: str, id:str, p_mw: float, q_mvar: float): #, vm_pu: float         
            self.name = name
            self.id = id
            self.p_mw = p_mw 
            self.q_mvar = q_mvar  
            #self.vm_pu = vm_pu                          
                       
    class CapacitorsOut(object):
        def __init__(self, capacitors: List[CapacitorOut]):
            self.capacitors = capacitors              
    capacitorsList = list()

    class StorageOut(object):
        def __init__(self, name: str, id:str, p_mw: float, q_mvar: float):          
            self.name = name
            self.id = id
            self.p_mw = p_mw 
            self.q_mvar = q_mvar                       
                       
    class StoragesOut(object):
        def __init__(self, storages: List[StorageOut]):
            self.storages = storages              
    storagesList = list()

    class LoadOut(object):
        def __init__(self, name: str, id:str, p_mw: float, q_mvar: float):          
            self.name = name
            self.id = id
            self.p_mw = p_mw 
            self.q_mvar = q_mvar                       
                       
    class LoadsOut(object):
        def __init__(self, loads: List[LoadOut]):
            self.loads = loads              
    loadsList = list() 
       
    print(dss.circuit.buses_names)
    for bus in dss.circuit.buses_names:      
        dss.circuit.set_active_bus(bus)
        print("tutaj wypisuje")
        print(dss.bus.name)
        print("tutaj koniec wypisywania")
        #print(dss.bus.vmag_angle_pu)
        
        #print(bus)
        
        # key = mx_cell; value = 0
        for key, value in BusbarsDict.items(): 
            if value == int(dss.bus.name):
                print("BusbarsDictId")  
                print(BusbarsDictId)              
                busName=key   
                busbar = BusbarOut(name=busName, id = BusbarsDictId[key], vm_pu = dss.bus.vmag_angle_pu[0], va_degree=dss.bus.vmag_angle_pu[1])#, firstnumberinid = net.bus._get_value(index, 'firstnumberinid'), vm_pu=row['vm_pu'], va_degree=row['va_degree'], p_mw=row['p_mw'], q_mvar=row['q_mvar'], pf = pf, q_p=q_p)      
                busbarList.append(busbar) 
                busbars = BusbarsOut(busbars = busbarList)
                result = {**busbars.__dict__} 
    
    #line_length_dict = dict()
    #line_powers_dict = dict()

    dss.lines.first()
    for _ in range(dss.lines.count):   
        # key = j5X72v2I2KgoAc5RDL2y___7; value = 0
        for key, value in LinesDict.items():           
            
            if value == dss.lines.name:
                lineName=key   

                p_from_mw = (dss.cktelement.powers[0]+dss.cktelement.powers[2]+dss.cktelement.powers[4])/1000
                p_to_mw = (dss.cktelement.powers[6]+dss.cktelement.powers[8]+dss.cktelement.powers[10])/1000
                q_from_mvar = (dss.cktelement.powers[1]+dss.cktelement.powers[3]+dss.cktelement.powers[5])/1000   
                q_to_mvar = (dss.cktelement.powers[7]+dss.cktelement.powers[9]+dss.cktelement.powers[11])/1000                
                i_from_ka = dss.cktelement.currents_mag_ang[0]
                i_to_ka =  dss.cktelement.currents_mag_ang[6]              
                #loading_percent = dss.cktelement.norm_amps - nie wiem jak to zrobić...może wziąć rated i podzielić przez wynikowy prąd
        
                #line_powers_dict[dss.lines.name] = dss.cktelement.powers

                line = LineOut(name=lineName, id = LinesDictId[key], p_from_mw=p_from_mw, q_from_mvar=q_from_mvar, p_to_mw=p_to_mw, q_to_mvar=q_to_mvar, i_from_ka=i_from_ka, i_to_ka=i_to_ka)#, loading_percent=row['loading_percent'])        
                linesList.append(line) 
                lines = LinesOut(lines = linesList)

                result = {**result, **lines.__dict__}      

    dss.lines.next()
    
    dss.loads.first()
    for _ in range(dss.loads.count):
        # key = j5X72v2I2KgoAc5RDL2y___7; value = 0
        for key, value in LoadsDict.items():         
            if value == dss.loads.name:
                loadName=key   

                p_mw = (dss.cktelement.powers[0]+dss.cktelement.powers[2]+dss.cktelement.powers[4])/1000
                q_mvar = (dss.cktelement.powers[1]+dss.cktelement.powers[3]+dss.cktelement.powers[5])/1000   
              
                load = LoadOut(name=loadName, id = LoadsDictId[key], p_mw=p_mw, q_mvar=q_mvar)        
                loadsList.append(load) 
                loads = LoadsOut(loads = loadsList)

                result = {**result, **loads.__dict__}
        dss.loads.next()

    dss.transformers.first()
    for _ in range(dss.transformers.count):
        # key = j5X72v2I2KgoAc5RDL2y___7; value = 0
        for key, value in TransformersDict.items():         
            if value == dss.transformers.name:
                transformerName=key   

                i_hv_ka = (dss.cktelement.currents[0]+dss.cktelement.currents[2]+dss.cktelement.currents[4])/1000
                i_lv_ka = (dss.cktelement.currents[1]+dss.cktelement.currents[3]+dss.cktelement.currents[5])/1000   
                
                #loading_percent = nie wiem jak zrobić loading percent
                transformer = TransformerOut(name=transformerName, id = TransformersDictId[key], i_hv_ka=i_hv_ka, i_lv_ka=i_lv_ka)        
                transformersList.append(transformer) 
                transformers = TransformersOut(transformers = transformersList)

                result = {**result, **transformers.__dict__}
        dss.transformers.next()

    #gdzie jest reactor ? reactor jest PDelementem 
    #You are trying to call objects in the COM interface that do not exist. For instance, the Reactor does not exist in the COM interface
    
    dss.capacitors.first()    
    for _ in range(dss.capacitors.count):
        # key = j5X72v2I2KgoAc5RDL2y___7; value = 0
        for key, value in CapacitorsDict.items():         
            if value == dss.capacitors.name:
                capacitorName=key   

                p_mw = (dss.cktelement.powers[0]+dss.cktelement.powers[2]+dss.cktelement.powers[4])/1000
                q_mvar = (dss.cktelement.powers[1]+dss.cktelement.powers[3]+dss.cktelement.powers[5])/1000   
                #vm_pu = dss.cktelement.voltages_mag_ang[0]
                #loading_percent = nie wiem jak zrobić loading percent
                capacitor = CapacitorOut(name=capacitorName, id = CapacitorsDictId[key], p_mw=p_mw, q_mvar=q_mvar) #vm_pu=vm_pu        
                capacitorsList.append(capacitor) 
                capacitors = CapacitorsOut(capacitors = capacitorsList)

                result = {**result, **capacitors.__dict__}
        dss.capacitors.next()


    dss.generators.first()
    for _ in range(dss.generators.count):
        # key = j5X72v2I2KgoAc5RDL2y___7; value = 0
        for key, value in GeneratorsDict.items():         
            if value == dss.generators.name:
                generatorName=key   

                p_mw = (dss.cktelement.powers[0]+dss.cktelement.powers[2]+dss.cktelement.powers[4])/1000
                q_mvar = (dss.cktelement.powers[1]+dss.cktelement.powers[3]+dss.cktelement.powers[5])/1000   
                
                #loading_percent = nie wiem jak zrobić loading percent
                generator = GeneratorOut(name=generatorName, id = GeneratorsDictId[key], p_mw=p_mw, q_mvar=q_mvar,vm_pu=vm_pu)        
                generatorsList.append(generator) 
                generators = GeneratorsOut(generators = generatorsList)

                result = {**result, **generators.__dict__}
        dss.generators.next()


    #gdzie jest storage ?

    #print(line_powers_dict)               
           
    response = json.dumps(result, default=lambda o: o.__dict__, indent=4)
    print(response)    
    return response    
        
        #U[pu],angle[degree]
        #print(dss.bus.vmag_angle_pu)    
        #dss.circuit.set_active_element(dss.bus.name)
        #print(dss.cktelement.powers)
        #print(dss.circuit.total_power)
    #P[MW]
    #Q[MVar]
    #PF
        