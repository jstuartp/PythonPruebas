#!/usr/bin/env seiscomp-python
# -*- coding: utf-8 -*-
import glob

from obspy.clients.fdsn import Client
from obspy import read, UTCDateTime
import sys
import traceback
import datetime
import os
import pymysql
import csv
from time import strftime





def chequeaBd():

        conn = pymysql.connect(  # conexión casa Stuart
            host='localhost',
            user='stuart',
            password='jspz2383',
            db='base_varios',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        #estaciones
        dat=[]

        try:
            with (conn.cursor() as cursor):
                # Create a new record

                consulta_sql = "select  distinct estacion as estacion, canal From log"

                # Ejecutar la consulta pasando los parámetros
                cursor.execute(consulta_sql, ())

                # Obtener todos los resultados
                estaciones = cursor.fetchall()
                for myx in estaciones:
                    dat.append(myx["estacion"])
                    #print(dat)

                # Commit changes
            conn.commit()
        finally:
            conn.close()

        return estaciones

def promedio(estacion):

    aa=estacion["estacion"]
    bb = estacion["canal"]

    conn = pymysql.connect(  # conexión casa Stuart
            host='localhost',
            user='stuart',
            password='jspz2383',
            db='base_varios',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )

    try:

        with (conn.cursor() as cursor):
            # Create a new record


            consulta_sql = ("SELECT  log.estacion, log.canal, lista_principal.marca, AVG (CONVERT(log.datoslat , DECIMAL(5,2) )) as PromedioLat,"
                            "AVG (CONVERT(log.diff , DECIMAL(5,2) )) as PromedioDiff"
                            " FROM log,lista_principal WHERE log.estacion = %s and canal = %s and log.estacion = lista_principal.estacion")

            # Ejecutar la consulta pasando los parámetros
            cursor.execute(consulta_sql, (aa,bb))
            #print(consulta_sql)
            # Obtener todos los resultados
            resultados = cursor.fetchall()
            print(resultados)


        # Commit changes
        conn.commit()
    finally:
        conn.close()
    return resultados


def main():

    datos=[]
    estaciones = chequeaBd()
    #print(estaciones)
    for (estacion) in estaciones:
        datos.append( promedio(estacion))

    #archivo = open("archivo_diccionario.csv", "a")
    #archivo.write(str(datos))
    #archivo.write("\n")
    #archivo.close()
    #print(datos)
    with open('archivo_diccionario.csv', 'a', newline='', encoding='utf-8') as archivo_csv:
        escritor_csv = csv.writer(archivo_csv)
        escritor_csv.writerows(datos)

    print(" datos guardados ")

if __name__ == "__main__":
        sys.exit(main())
