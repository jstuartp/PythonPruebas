# This is a sample Python script.
from time import strftime

from obspy.clients.fdsn import Client
from obspy import read, UTCDateTime
import sys
import traceback
import datetime
import os
import pymysql
from seiscomp import core, client, io, math, logging
from seiscomp import client, datamodel
from seiscomp.client import Protocol


#Se crea el objeto cliente FDSN para obtener datos y el inventario
host = ("http://163.178.171.47:8080")  # SEISCOMP servidor Virtual
#host = ("http://localhost:8080")  # SEISCOMP computadora local
myClient = Client(host)
total = myClient.get_stations()
networks = myClient.get_stations(level="network")
rutaLog ="/home/stuart/waves/corta/PGALog.log"     #archivo de log
rutaPGA ="/home/stuart/waves/corta/PGAData.log"     #archivo de log




def calculoPGA():    #calculoPGA(obj): nombre con parametro
    #event = datamodel.Event.Cast(obj)
    #fechaEvento = str(event.creationInfo().creationTime())
    #fechaEvento = fechaEvento.replace(" ", "")
    #fechaEvento = fechaEvento.replace(":", "_")
    #fechaEvento = fechaEvento.replace(".", "_")
    #rutaWaves = "/home/lis/waves/corta/" + event.publicID() + fechaEvento + "/"
    #tiempo = event.creationInfo().creationTime()
    rutaWaves = "/home/stuart/waves/corta/UCR_lis2024kthc2024-06-0120_33_39_584/" #para prueba local
    tiempo= "2024-06-01 20:33:39.584" #para prueba local
    utctiempo = UTCDateTime(tiempo)
    now = core.Time.GMT()

    matriz = []
    archivo = open(rutaLog, "a")
    archivo.write("\n\n\n--EXITO--CALCULANDO PGA PARA NUEVO EVENTO UCR_lis2024kthc") #local
    archivo.write("\n--EXITO--Fecha del evento 2024-06-0120_33_39_584" ) #local
    #archivo.write("\n\n\n--EXITO--CALCULANDO PGA PARA NUEVO EVENTO %s" % event.publicID())
    #archivo.write("\n--EXITO--Fecha del evento %s" % event.creationInfo().creationTime())
    archivo.write("\n--EXITO--Fecha de procesamiento %s" % str(now))
    archivo.close()
    print("PROCESANDO EVENTO")



    #recorriendo lista de networks para solicitar datos con el código de cada estación
    for n in range(len(networks)):
        # print(total[n].code)
        for s in range(len(total.networks[n].stations)):
            # print(total.networks[n].stations[s].code)
            datos = []
            nombreFile= rutaWaves + utctiempo.strftime("%m-%d-%Y_%H_%M_%S") + "_" + \
                                          total.networks[n].stations[s].code + ".mseed"
            print(".", end=" ")


            try:
                # falla si no hay datos para la estacion en el tiempo dado

                inventory = myClient.get_stations(network=total[n].code,
                                                  station=total.networks[n].stations[s].code, level="RESP")

                #st = client.get_waveforms(total[n].code, total.networks[n].stations[s].code, "**", "HN*", inicio, fin,
                                        #  attach_response=True)


                st = read(nombreFile, format="mseed")


                archivo = open(rutaLog, "a")
                archivo.write("\n--EXITO--Data read for station %s" % total.networks[n].stations[s].code)
                archivo.close()



            except Exception as err:
                archivo = open(rutaLog, "a")
                archivo.write("\n--FALLO EN LECTURA--No data or file for station  %s" % total.networks[n].stations[s].code)
                # archivo.write(f"\nDescripcion del error:  {err.encode('utf-8')}")
                archivo.close()
                #print(f"FALLO TRY 1 Descripcion del error: {err}")
            else:    #de existir datos continua con el calculo

                st.merge()
                #copia para quitar respuesta
                strNew =st.copy()
                #string con la ruta del archivo para referenciar en base de datos
                rutaArchivo =rutaWaves+utctiempo.strftime("%m-%d-%Y_%H:%M:%S")+"_"+total.networks[n].stations[s].code+".mseed"


                #Iteracion para filtrar e imprimir el resultado del pga
                chan=[]

                for trx in strNew:
                        try:
                            trx.detrend("demean")
                            trx.detrend("linear")
                            trx.taper(max_percentage=0.05, type="hann")
                            trx.filter("bandpass", freqmin=0.05, freqmax=25, corners=2) #Filtro estandar para el LIS
                            trx = trx.remove_response(inventory, output="ACC")
                            absoluto = abs(trx.data)
                            maximo = max(absoluto)
                            archivo = open(rutaLog, "a")
                            archivo.write(
                                "\n--EXITO---------Processing Channel %s" % trx.stats.channel)
                            archivo.close()
                            archivo = open(rutaPGA, "a")
                            archivo.write(
                                "\n--DATOS--Processing Station  %s" % trx.stats.station)
                            archivo.write(
                                "\n--DATOS----Processing Channel  %s" % trx.stats.channel)
                            archivo.write(
                                "\n--DATOS----PGA;  %s" % str(maximo))
                            archivo.close()

                        except:
                            st_umask = trx.split()
                            a = []
                            for tr1 in st_umask:
                                tr1.detrend("demean")
                                tr1.detrend("linear")
                                tr1.taper(max_percentage=0.05, type="hann")
                                tr1.filter("bandpass", freqmin=0.1, freqmax=10, corners=2)
                                tr1 = tr1.remove_response(inventory, output="ACC")
                                a.append(abs(max(tr1.data)))
                                maximo = max(a)
                                archivo = open(rutaLog, "a")
                                archivo.write(
                                    "\n--WARNING---------Processing Channel With GAPS %s" % trx.stats.channel)
                                archivo.close()
                                archivo = open(rutaPGA, "a")
                                archivo.write(
                                    "\n--DATOS--Processing Station  %s" % trx.stats.station)
                                archivo.write(
                                    "\n--DATOS----Processing Channel  %s" % trx.stats.channel)
                                archivo.write(
                                    "\n--DATOS----PGA;  %s" % str(maximo))
                                archivo.close()

                        chan.append(maximo)


                #print(trx.stats.station, trx.stats.location, trx.stats.channel)
                #print(str(maximo))

                try:
                    coord = inventory.get_coordinates(total[n].code+"." + total.networks[n].stations[s].code + ".00.HNZ")
                except:
                    try:
                        coord = inventory.get_coordinates(total[n].code+"." + total.networks[n].stations[s].code + ".11.HNZ")
                    except:
                        coord = inventory.get_coordinates(total[n].code+"." + total.networks[n].stations[s].code + "..HNZ")
                datos.append(utctiempo.strftime("%d/%m/%Y %H:%M:%S"))
                datos.append(str(now))
                datos.append("UCR_lis2024kthc")
                datos.append(total.networks[n].stations[s].code)
                datos.append(coord["latitude"])
                datos.append(coord["longitude"])
                try:
                    if chan[0]:
                        datos.append(chan[0])
                    else:
                        datos.append(0)
                    if chan[1]:
                        datos.append(chan[1])
                    else:
                        datos.append(0)
                    if chan[2]:
                        datos.append(chan[2])
                    else:
                        datos.append(0)
                    datos.append(max(chan))
                except Exception as err:
                    archivo = open(rutaLog, "a")
                    archivo.write(
                        "\n--WARNING---------Fail in channels for station %s" % total.networks[n].stations[s].code)
                    archivo.close()
                    print(f"Faltan canales para procesar la estación  {err}")
                else:
                     datos.append(rutaArchivo)
                     matriz.append(datos)
                     archivo = open(rutaLog, "a")
                     archivo.write(
                         "\n--EXITO---------Data processed for station %s" % total.networks[n].stations[s].code)
                     archivo.close()
                     #print("Datos procesados para la estación  %s" % total.networks[n].stations[s].code)
    print("\nEvento procesado")
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
            sql = ("INSERT INTO `pga` (`fecha_evento`,`fecha_calculo`,`nombre_evento`,`estacion`, `latitud`, `longitud`, `hne_pga`, `hnn_pga`, `hnz_pga`,`maximo` ,`rutaWaveform`)"
                   " VALUES (%s ,%s ,%s ,%s ,%s ,%s ,%s, %s ,%s ,%s ,%s)")
            #print(values)
            cursor.executemany(sql,datos)

        # Commit changes
        conn.commit()

        print("PGA guardado en la Base de Datos")
    finally:
        conn.close()




if __name__ == "__main__":
    datos=calculoPGA()
    conection(datos)