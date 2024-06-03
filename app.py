# -*- coding: utf-8 -*-
import pandapower_electrisim
import opendss_electrisim

from flask import Flask, request, jsonify, make_response
from flask_cors import CORS, cross_origin #żeby działało trzeba wywołać polecenie pip install -U flask-cors==3.0.10 
import pandapower as pp
import pandas as pd


import numpy as np


from typing import List

app = Flask(__name__)
#cors = CORS(app)# BYŁO, support_credentials=True
CORS(app) #, origins=['http://127.0.0.1:5500','https://app.electrisim.com/'] 
app.config['CORS_HEADERS'] = 'Content-Type' # było
#app.config['CORS_ORIGINS'] = 'http://128.0.0.1:5500' #nie było tego
 #nie było tego
 #@cross_origin()
#@cross_origin(origins=['http://127.0.0.1:5500'],allow_headers=['Content-Type, access-control-allow-origin'])#supports_credentials=True #nie było tego

#pobieranie danych z frontend
@app.route('/')
def index():
        return 'Please send data to backend'

@app.route('/', methods=['GET','POST'])
def simulation():
    #in_data = request.get_json()
    in_data = request.get_json(force=True) #force – if set to True the mimetype is ignored.
    print(in_data)    
    
   
    Busbars = {} 
          
    #utworzenie sieci - w pierwszej petli sczytujemy parametry symulacji i tworzymy szyny
    for x in in_data:    
        if "PowerFlowPandaPower" in in_data[x]['typ']:
            print('jestem w PowerFlowPandaPower')
            frequency=eval(in_data[x]['frequency'])
            algorithm=in_data[x]['algorithm']
            calculate_voltage_angles = in_data[x]['calculate_voltage_angles']
            init = in_data[x]['initialization']

            net = pp.create_empty_network(f_hz=frequency)
       
            Busbars = pandapower_electrisim.create_busbars(in_data, net, x)                 
            pandapower_electrisim.create_other_elements(in_data, net, x, Busbars)   

            response = pandapower_electrisim.powerflow(net, algorithm, calculate_voltage_angles, init)  

            return response
        
        if "ShortCircuitPandaPower" in in_data[x]['typ']:                     

            net = pp.create_empty_network()
            Busbars = pandapower_electrisim.create_busbars(in_data, net, x)                 
            pandapower_electrisim.create_other_elements(in_data, net, x, Busbars)
            response = pandapower_electrisim.shortcircuit(net, in_data[x])
            return response
           
        if "PowerFlowOpenDss" in in_data[x]['typ']:            
            frequency=eval(in_data[x]['frequency'])
            algorithm=in_data[x]['algorithm'] #'Admittance' (Iterative Load Flow), 'PowerFlow' (Direct solution)
            response = opendss_electrisim.powerflow(in_data, frequency)           
            return response



             
      
    #print(net.bus)
    #print(net.shunt)
    #print(net.ext_grid)
    
    #print(net.line))
    
        
    

#DLA PRODUKCJI USUWAJ PONIŻSZE WERSJE        
if __name__ == '__main__':
    #app.debug = False
    #app.run(host = '127.0.0.1', port=5005)
    #app.debug = True
    #app.run(host = '127.0.0.1', port=5000)
    app.run(host = '0.0.0.0', port=5000, debug=True)