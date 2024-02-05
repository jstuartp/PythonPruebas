# This is a sample Python script.
from matplotlib.pyplot import plot
# Press Mayús+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
from obspy.clients.fdsn import Client
from obspy import read, UTCDateTime
from obspy import read_inventory
import datetime
import numpy as np



def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi, {name}')  # Press Ctrl+F8 to toggle the breakpoint.


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print_hi('PyCharm')

    host = ("http://163.178.171.47:8080")  # Local FDSN client
    client = Client(host)

    # iterando por el inventario para determinar la cantidad de estaciones
    numStations =0
    myNumStations = client.get_stations(network="MF",station="*", level="station")
    for (k, v) in sorted(myNumStations.get_contents().items()):
        if k == "stations":
            numStations =len(v) #v termina con el número de estaciones presentes en el inventory

    #Lista para guardar los códigos de las estaciones del inventory
    lista = []
    #Iterando por el inventory para obtener la lista de estaciones
    for i in range(numStations):
        #print(i)
        lista.append(myNumStations.networks[0].stations[i].code) #lista termina con el listado de los códigos de las estaciones





    #recorriendo lista para solicitar datos con el código de cada estación
    for d in range(len(lista)):
        try:    # falla si no hay datos para la estacion en el tiempo dado
            inventory = client.get_stations(network="MF", station=lista[d], level="RESP")
            st = client.get_waveforms("MF", lista[d], "", "HN*", UTCDateTime("2024-01-31T06:44:00"), UTCDateTime("2024-01-31T06:48:00"),
                                      attach_response=True)
        except:
            print("No hay datos para la estación "+lista[d])
        else:    #de existir datos continua con el calculo
            st.merge()
            strNew =st.copy()
            try:
                strNew = strNew.remove_response(inventory,output="ACC")
            except:
                print("Error en lectura de datos para la estación "+lista[d])
            else:
                tr1 = strNew[0]
                tr1filter=tr1.copy()
                #tr1.plot()
                tr1filter = tr1filter.filter("bandpass", freqmin=0.05, freqmax=25)
                #tr1filter.plot()
                sta_id = tr1.get_id()

                #aceleracion para una componente
                #print(tr1filter.stats)
                pga1= abs(max(tr1filter.data))
                #print(pga1*100)

                #st.plot()
                #strNew.plot()
                #print(strNew)

                for trx in strNew:
                  trx.filter("bandpass", freqmin=0.05, freqmax=25)
                  print(trx.stats.station, trx.stats.channel,abs(max(trx.data))*100)

                #trx.plot()


    #response = tr1.stats.response
    #sensi = tr1.stats.response.instrument_sensitivity.value
    #in_unit = tr1.stats.response.instrument_sensitivity.input_units
    #print(in_unit)
    #response.plot(0.001,output="ACC")
    #st.plot()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
