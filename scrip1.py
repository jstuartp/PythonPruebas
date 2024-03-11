# This is a sample Python script.
from time import strftime

from matplotlib.pyplot import plot
# Press Mayús+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
from obspy.clients.fdsn import Client
from obspy import read, UTCDateTime
from obspy import read_inventory
import datetime
import numpy as np
import pymysql
import sys



def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi, {name}')  # Press Ctrl+F8 to toggle the breakpoint.


#Se crea el objeto cliente FDSN para obtener datos y el inventario
host = ("http://163.178.171.47:8080")  # Local FDSN client
client = Client(host)

#objeto con el el catalogo de las estaciones
myNumStations = client.get_stations(network="MF", station="*", level="station")



def cantidad_Estaciones(myNumStations):
    # iterando por el inventario para determinar la cantidad de estaciones
    numStations = 0
    for (k, v) in sorted(myNumStations.get_contents().items()):
        if k == "stations":
            numStations = len(v)  # v termina con el número de estaciones presentes en el inventory

    return numStations

def lista_Estaciones(numStations, myNumStations):
    #Lista para guardar los códigos de las estaciones del inventory
    lista = []
    #Iterando por el inventory para obtener la lista de estaciones
    for i in range(numStations):
        #print(i)
        if myNumStations.networks[0].stations[i].code == "CTEC": #definir una sola estacion
            lista.append(myNumStations.networks[0].stations[i].code) #lista termina con el listado de los códigos de las estaciones
    return lista




def calculoPGA(lista,tiempo):
    inicio= tiempo - datetime.timedelta(minutes=5)  #resta 5 minutos a la hora fija

    fin =tiempo + datetime.timedelta(minutes=5)     #suma 5 minutos a la hora fija
    #datos = [] #crear estructura para guardar los datos antes de enviarlos a la base
    matriz = []


    #recorriendo lista para solicitar datos con el código de cada estación
    for d in range(len(lista)):
    #for d in range(0,4):
        #inventory = client.get_stations(network="MF", station=lista[d], level="RESP")
        datos = []
        column1, column2, column3 = [], [], []
        g = 980.665



        try:    # falla si no hay datos para la estacion en el tiempo dado
            inventory = client.get_stations(network="MF", station=lista[d], level="RESP")
            st = client.get_waveforms("MF", lista[d], "", "HN*", inicio, fin,
                                      attach_response=True)
            #coord = inventory.get_coordinates("MF." + lista[d] + "..HNZ")
            st.merge()

        except:
            print("No hay datos para la estación "+lista[d])
        else:    #de existir datos continua con el calculo
            for tr in st:
                sta_id = tr.get_id()
                sensi = tr.stats.response.instrument_sensitivity.value
                in_unit = tr.stats.response.instrument_sensitivity.input_units
                if isinstance(tr.data, np.ma.core.MaskedArray):
                    st_umask = tr.split()
                    a = []
                    for tr1 in st_umask:
                        tr1.detrend("demean")
                        tr1.detrend("linear")
                        if in_unit == "m/s" or in_unit == "M/S":
                            tr1.data = np.gradient(tr1.data, tr1.stats.delta)
                            tr1.remove_sensitivity()
                            a.append(abs(max(tr1.data)))
                            amax = max(a)

                        elif in_unit == "m/s**2" or "M/S**2":
                            tr1.remove_sensitivity()
                            a.append(abs(max(tr1.data)))
                            amax = max(a)
                    column1.append(sta_id)
                    column2.append(amax*100)           ## cm/s**2
                    column3.append(amax*100/g)               ## g
                else:
                    if in_unit == "m/s" or in_unit == "M/S":
                        tr.detrend("demean")
                        tr.detrend("linear")
                        tr.data = np.gradient(tr.data, tr.stats.delta)
                        tr.remove_sensitivity()
                        amax = abs(max(tr.data))
                    elif in_unit == "m/s**2" or "M/S**2":
                        tr.detrend("demean")
                        tr.detrend("linear")
                        tr.remove_sensitivity()
                        amax = abs(max(tr.data))
                    column1.append(sta_id)
                    column2.append(amax*100 )
                    column3.append(amax*100/g)
            dict = {'STATION ID': column1, 'PGA [cm/s**2]': column2, 'PGA [g]': column3}
            print(dict)

    return matriz


def conection(datos):
    conn = pymysql.connect(
        host='localhost',
        user='stuart',
        password='jspz2383',
        db='tabla_pga',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

    try:
        with (conn.cursor() as cursor):
            # Create a new record
            sql = "INSERT INTO `pga` (`fecha`,`estacion`, `latitud`, `longitud`, `hne_pga`, `hnn_pga`, `hnz_pga`, `rutaWaveform`) VALUES (%s ,%s ,%s ,%s ,%s ,%s ,%s ,%s)"
            #print(values)
            cursor.executemany(sql,datos)

        # Commit changes
        conn.commit()

        print("PGA guardado en la Base de Datos")
    finally:
        conn.close()






    #response = tr1.stats.response
    #sensi = tr1.stats.response.instrument_sensitivity.value
    #in_unit = tr1.stats.response.instrument_sensitivity.input_units
    #print(in_unit)
    #response.plot(0.001,output="ACC")
    #st.plot()



# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    #print_hi('PyCharm')
    numStations = cantidad_Estaciones(myNumStations)
    listaEstaciones = lista_Estaciones(numStations,myNumStations)
    #date = sys.argv[1]
    #print(date)
    #datos = calculoPGA(listaEstaciones, UTCDateTime(sys.argv[1]))  # enviando una hora que ingresa por parámetro
    datos=calculoPGA(listaEstaciones,UTCDateTime("2024-02-27T20:11:00")) #enviando una hora fija
    #conection(datos)

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
