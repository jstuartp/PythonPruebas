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



#Se crea el objeto cliente FDSN para obtener datos y el inventario
host = ("http://163.178.171.47:8080")  # SEISCOMP servidor Virtual
#host = ("http://localhost:8080")  # SEISCOMP computadora local
client = Client(host)
total = client.get_stations()
networks = client.get_stations(level="network")
#print(len(networks))

def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi, {name}')  # Press Ctrl+F8 to toggle the breakpoint.




#guarda los archivos mseed +- 5 minutos del evento dado
def Guarda_waves(tiempo):
    inicio = tiempo - datetime.timedelta(minutes=5)  # resta 5 minutos a la hora fija

    fin = tiempo + datetime.timedelta(minutes=5)  # suma 5 minutos a la hora fija
    lista = []

    for n in range(len(networks)):
        #print(total[n].code)
        for s in range(len(total.networks[n].stations)):
            #print(total.networks[n].stations[s].code)
            try:
                st = client.get_waveforms(total[n].code, total.networks[n].stations[s].code, "**", "HN*", inicio, fin, attach_response=True)
                #print(st)
            except:
                print("No hay datos para la estación " + total.networks[n].stations[s].code)

            else:  # de existir datos continua con el calculo
                st.merge()
                # copia para quitar respuesta
                strNew = st.copy()
                try:
                    rutaArchivo = "/home/stuart/waves/ver3/" + tiempo.strftime("%m-%d-%Y_%H:%M:%S") + "_" + total.networks[n].stations[s].code + ".mseed"
                    # guardar el stream en archivo mseed
                    strNew.write(rutaArchivo, format="MSEED")

                except:
                    print("Error en lectura de datos para la estación " + total.networks[n].stations[s].code)


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
   #cantidad_Estaciones()
    #listaEstaciones = lista_Estaciones(numStations,myNumStations)
    #print(listaEstaciones)
    #date = sys.argv[1]
    #print(date)
    Guarda_waves(UTCDateTime("2024-04-17T21:21:56"))
    #conection(datos)

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
