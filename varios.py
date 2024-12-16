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
import csv



def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi, {name}')  # Press Ctrl+F8 to toggle the breakpoint.




# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    #do something
    # Ruta al archivo CSV
    ruta_csv = "distritosLatLong.csv"
    archivoxml = open("cities.xml", "a")
    archivoxml.write(
        '<?xml version="1.0" encoding="utf-8"?>\n<seiscomp sourceCapitals="https://en.wikipedia.org/wiki/List_of_national_capitals">\n')
    archivoxml.close()

    # Leer el archivo CSV
    with open(ruta_csv, mode='r', newline='', encoding='utf-8') as archivo:
        lector = csv.DictReader(archivo)




        for fila in lector:
            print(fila)
            archivoxml = open("cities.xml", "a")
            archivoxml.write(
                '<City category="C" countryID="CRC">\n<name>'+fila["distrito"]+'</name>\n<latitude>'+fila["latitud"]+
                '</latitude>\n<longitude>'+fila["longitud"]+'</longitude>\n<population>'+fila["poblacion"]+'</population>\n</City>\n')
            archivoxml.close()
            #print(fila["Columna1"], fila["Columna2"])

    archivoxml = open("cities.xml", "a")
    archivoxml.write(
        '\n</seiscomp>')
    archivoxml.close()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
