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
        if myNumStations.networks[0].stations[i].code == "CPAR": #definir una sola estacion
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



        try:    # falla si no hay datos para la estacion en el tiempo dado
            inventory = client.get_stations(network="MF", station=lista[d], level="RESP")
            st = client.get_waveforms("MF", lista[d], "", "HN*", inicio, fin,
                                      attach_response=True)
            coord = inventory.get_coordinates("MF." + lista[d] + "..HNZ")

        except:
            print("No hay datos para la estación "+lista[d])
        else:    #de existir datos continua con el calculo
            st.merge()
            #copia para quitar respuesta
            strNew =st.copy()
            #copia cruda
            stRaw = st.copy()
            try:
                strNew.detrend("demean")
                strNew = strNew.remove_response(inventory,output="ACC")
                #stRaw.detrend("demean")
                #stRaw.detrend("linear")
            except:
                print("Error en lectura de datos para la estación "+lista[d])
            else:
                #string con la ruta del archivo para referenciar en base de datos
                rutaArchivo ="/home/stuart/waves/"+tiempo.strftime("%m-%d-%Y_%H:%M:%S")+"_"+lista[d]+".mseed"
                #rutaArchivoRaw = "/home/stuart/waves/" + tiempo.strftime("%m-%d-%Y_%H:%M:%S") + "_" + lista[d] + "RAW.mseed"
                # guardar el stream en archivo mseed
                strNew.write(rutaArchivo,format="MSEED")
                #stRaw.write(rutaArchivoRaw, format="MSEED")
                #datos["estaciones"] = lista[d]
                #datos["latitud"] = coord["latitude"]
                #datos["longitud"] = coord["longitude"]
                #tr1 = strNew[0]
                #tr1filter=tr1.copy()
                #tr1.plot()
                #tr1filter = tr1filter.filter("bandpass", freqmin=0.05, freqmax=25)
                #tr1filter.plot()
                #sta_id = tr1.get_id()

                #Iteracion para filtrar e imprimir el resultado del pga
                chan=[]
                for tRaw in stRaw:
                    #tRaw.detrend("demean")
                    #tRaw.detrend("linear")
                    print(tRaw.stats.station, tRaw.stats.channel,max(abs(tRaw.data)))
                    #tRaw.plot()
                stRaw.plot()
                for trx in strNew:
                  trx.filter("bandpass", freqmin=0.05, freqmax=25)
                  chan.append(max(abs(trx.data)))

                  #print(trx.stats.station, trx.stats.channel,abs(max(trx.data))*100)
                print("Datos procesados para la estación "+lista[d])
                datos.append(tiempo.strftime("%d/%m/%Y %H:%M:%S"))
                datos.append(lista[d])
                datos.append(coord["latitude"])
                datos.append(coord["longitude"])
                datos.append(chan[0])
                datos.append(chan[1])
                datos.append(chan[2])
                datos.append(rutaArchivo)
                matriz.append(datos)
                #print(matriz)
                #datos["hne"] = chan[0]
                #datos["hnn"] = chan[1]
                #datos["hnz"] = chan[2]
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
    datos=calculoPGA(listaEstaciones,UTCDateTime("2024-02-12T05:55:00")) #enviando una hora fija
    #conection(datos)

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
