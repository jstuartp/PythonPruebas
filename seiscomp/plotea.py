#!/usr/bin/env seiscomp-python
# -*- coding: utf-8 -*-
import glob

import matplotlib
from matplotlib import pyplot as plt
from obspy.clients.fdsn import Client
from obspy import read, UTCDateTime
import sys
import argparse
import traceback
import datetime
import os
import csv
from time import strftime





def Plotear(imgagenpng, ruta,taperMaxPercent,taperType,filterType,filterFreqMin,filterFreqMax,filterCorners):
    # Configurar la figura y subgráficos
    strNew = read(ruta, format="mseed")
    strNew.detrend("demean")
    strNew.taper(max_percentage=float(taperMaxPercent), type=taperType)
    strNew.filter(filterType, freqmin=float(filterFreqMin),
                                       freqmax=float(filterFreqMax),
                                       corners=float(filterCorners))
    matplotlib.use('agg')
    fig, axes = plt.subplots(len(strNew), 1, figsize=(12, 8), sharex=True)

    nombreEstacion = ""
    archivo = open("/home/lis/waves/Plotea.log", "a")
    archivo.write(str(UTCDateTime.now()))
    archivo.write("--Voy a procesar imagen de %s--\n" %imgagenpng)
    archivo.close()

    # Graficar cada traza en su respectivo subgráfico
    for i, trace in enumerate(strNew):
        nombreEstacion = trace.stats.station
        ax = axes[i]
        # Convertir los tiempos a segundos relativos desde el inicio de la traza
        times = trace.times()
        ax.plot(trace.data, label=f"Traza: {trace.id}", color='blue')
        ax.set_ylabel("Amplitud")
        ax.legend(loc="upper right")
        ax.grid(True)
        # Centrar el eje Y en 0 para cada traza

    # Etiquetas generales del gráfico
    fig.suptitle("Grafica PGA para %s" % nombreEstacion, fontsize=14)
    axes[-1].set_xlabel("Tiempo")

    # Formato automático de las fechas en el eje X
    plt.gcf().autofmt_xdate()

    # Guardar el gráfico en un archivo
    # output_file = "01-30-2025-14-50-37_MF_PLRL.png"
    plt.savefig(imgagenpng, dpi=300)
    plt.close()
    archivo = open("/home/lis/waves/Plotea.log", "a")
    archivo.write(str(UTCDateTime.now()))
    archivo.write("--Termine la imagen de %s--\n" % nombreEstacion)
    archivo.close()




def main():
    parser = argparse.ArgumentParser(description="Recibe parámetros string y float")
    parser.add_argument("--imagenpng", type=str, required=True, help="donde guardar imagenes")
    parser.add_argument("--ruta", type=str, required=True, help="ruta del mseed")
    parser.add_argument("--maxpercent", type=float, required=True, help="Taper max percent")
    parser.add_argument("--tapertype", type=str, required=True, help="Taper Type")
    parser.add_argument("--filtertype", type=str, required=True, help="Filter Type")
    parser.add_argument("--filterfreqmin", type=float, required=True, help="Filter freq min")
    parser.add_argument("--filterfreqmax", type=float, required=True, help="Filter freq max")
    parser.add_argument("--filtercorners", type=float, required=True, help="Filter corners")
    args = parser.parse_args()
    archivo = open("/home/lis/waves/Plotea.log", "a")
    archivo.write(str(UTCDateTime.now()))
    archivo.write("--Estos son los argumentos %s--\n" % args)
    archivo.close()

    Plotear(args.imagenpng,args.ruta,args.maxpercent,args.tapertype,args.filtertype,args.filterfreqmin,args.filterfreqmax,args.filtercorners)



if __name__ == "__main__":
        sys.exit(main())
