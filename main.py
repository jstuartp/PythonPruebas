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
        if myNumStations.networks[0].stations[i].code == "CCDN": #definir una sola estacion
            lista.append(myNumStations.networks[0].stations[i].code) #lista termina con el listado de los códigos de las estaciones

    return lista

#guarda los archivos mseed +- 5 minutos del evento dado
def Guarda_waves(lista,tiempo):
    inicio = tiempo - datetime.timedelta(minutes=5)  # resta 5 minutos a la hora fija

    fin = tiempo + datetime.timedelta(minutes=5)  # suma 5 minutos a la hora fija

    for d in range(len(lista)):
        # for d in range(0,4):


        try:  # falla si no hay datos para la estacion en el tiempo dado

            st = client.get_waveforms("MF", lista[d], "**", "HN*", inicio, fin,
                                      attach_response=True)
        except:
            print("No hay datos para la estación " + lista[d])
        else:  # de existir datos continua con el calculo
            #st.merge()
            # copia para quitar respuesta
            strNew = st.copy()
            try:
                rutaArchivo = "/home/stuart/waves/" + tiempo.strftime("%m-%d-%Y_%H:%M:%S") + "_" + lista[d] + ".mseed"
                # guardar el stream en archivo mseed
                strNew.write(rutaArchivo, format="MSEED")

            except:
                print("Error en lectura de datos para la estación " + lista[d])





def calculoPGA(lista,tiempo):
    #inicio= tiempo - datetime.timedelta(minutes=5)  #resta 5 minutos a la hora fija

    #fin =tiempo + datetime.timedelta(minutes=5)     #suma 5 minutos a la hora fija
    #datos = [] #crear estructura para guardar los datos antes de enviarlos a la base
    matriz = []



    #recorriendo lista para solicitar datos con el código de cada estación
    for d in range(len(lista)):
    #for d in range(0,15):
        #inventory = client.get_stations(network="MF", station=lista[d], level="RESP")
        datos = []


        try:    # falla si no hay datos para la estacion en el tiempo dado
            inventory = client.get_stations(network="MF", station=lista[d], level="RESP")
            st = read("/home/stuart/waves/" + tiempo.strftime("%m-%d-%Y_%H:%M:%S") + "_" + lista[d] + ".mseed", attach_response=True)




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
                stRaw.detrend("linear")

                strNew = strNew.remove_response(inventory)
                #stRaw.detrend("demean")
                #stRaw.detrend("linear")
            except:
                print("Error en lectura de datos para la estación "+lista[d])
            else:
                #string con la ruta del archivo para referenciar en base de datos
                rutaArchivo ="/home/stuart/waves/"+tiempo.strftime("%m-%d-%Y_%H:%M:%S")+"_"+lista[d]+".mseed"
                rutaArchivoProcesado = "/home/stuart/waves/" + tiempo.strftime("%m-%d-%Y_%H:%M:%S") + "_" + lista[d] + "_Procesado.mseed"
                # guardar el stream en archivo mseed
                #strNew.write(rutaArchivoProcesado,format="MSEED")


                #Iteracion para filtrar e imprimir el resultado del pga
                chan=[]

                for trx in strNew:
                  #print(trx.stats.station, trx.stats.channel,max(abs(trx.data))*100)
                  trx.filter("bandpass", freqmin=0.05, freqmax=25)
                  chan.append(max(abs(trx.data*980)))

                  print(trx.stats.station, trx.stats.location, trx.stats.channel, max(abs(trx.data*980)))

                try:
                    coord = inventory.get_coordinates("MF." + lista[d] + ".00.HNZ")
                except:
                    coord = inventory.get_coordinates("MF." + lista[d] + "..HNZ")
                datos.append(tiempo.strftime("%d/%m/%Y %H:%M:%S"))
                datos.append(lista[d])
                datos.append(coord["latitude"])
                datos.append(coord["longitude"])
                try:
                    datos.append(chan[0])
                    datos.append(chan[1])
                    datos.append(chan[2])
                except:
                    print("Faltan canales para procesar la estación "+ lista[d])
                else:
                    datos.append(rutaArchivo)
                    matriz.append(datos)
                    print("Datos procesados para la estación " + lista[d])
                #print(matriz)
                #datos["hne"] = chan[0]
                #datos["hnn"] = chan[1]
                #datos["hnz"] = chan[2]
    return matriz


def conection(datos):
    """"
    conn = pymysql.connect( #conexión casa Stuart
        host='localhost',
        user='root',
        password='root',
        db='tabla_pga',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    """
    conn = pymysql.connect(  #conexion compu lis
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
    #Guarda_waves(listaEstaciones,UTCDateTime("2024-02-28T22:56:00"))
    #datos = calculoPGA(listaEstaciones, UTCDateTime(sys.argv[1]))  # enviando una hora que ingresa por parámetro
    datos=calculoPGA(listaEstaciones,UTCDateTime("2024-02-24T10:10:00")) #enviando una hora fija
    conection(datos)

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
