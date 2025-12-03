#!/usr/bin/env seiscomp-python
# -*- coding: utf-8 -*-
import glob
from urllib.parse import splitquery

import matplotlib
import logging
import obspy
from pathlib import Path
from matplotlib import pyplot as plt
from obspy.clients.fdsn import Client
from obspy import read, UTCDateTime
from obspy import read_inventory
import sys
import argparse
import traceback
import datetime
import os
import csv
from time import strftime

# FDSN server used to obtain station metadata

# CONSTANTES FIJAS PARA PLOTEAR
taperMaxPercent = 0.05
taperType = "hann"
filterType = "bandpass"
filterFreqMin = 0.1
filterFreqMax = 10
filterCorners = 2
inventory = read_inventory("/home/lis/waves/inventory_Estructuras.xml", format="STATIONXML")




def Plotear(imagenpng,ruta):
    """Plot seismic traces applying instrument response."""

    # Read the mseed file
    directorio = Path(ruta)
    archivos_mseed = list(directorio.glob("*.mseed"))
    order = {"HNN": 0, "HNE": 1, "HNZ": 2}


    for archivo in archivos_mseed:
        nuevo_directorio =str(archivo).split("/")[-2]
        nombre_imagen =archivo.name.split(".")[0]
        nombrearchivo =imagenpng+nuevo_directorio+"/"+nombre_imagen+"_vel.png"
        print(nombrearchivo)

        try:
            os.stat(imagenpng+nuevo_directorio)
        except:
            os.mkdir(imagenpng+nuevo_directorio)

        logging.basicConfig(
            filename="/home/lis/waves/imagenes/" + nuevo_directorio + "/plotlog_vel.log",
            level=logging.INFO,  # Nivel mínimo que se registrará
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        logging.info(f"Nombre del directorio: {ruta}")
        logging.info(f"Nombre del archivo: {nombre_imagen}")
        strNew = read(archivo, format="mseed")
        #print("padre %s" %archivo.parent)

        logging.info("--Voy a procesar imagen de %s--\n" % nombre_imagen)
        # Preprocess each trace independently and remove instrument response
        strNew.merge(method=1, fill_value='interpolate')
        # Ordenar in-place la lista interna de trazas
        strNew.traces.sort(
            key=lambda tr: (
                tr.stats.station,  # agrupar por estación
                order.get(tr.stats.channel, 99),  # HNN < HNE < HNZ; otros al final
                tr.stats.starttime  # desempate temporal (opcional)
            )
        )
        for tr in strNew:
            try:
                tr.remove_response(inventory.select(network=tr.stats.network, station=tr.stats.station), output="VEL")
                tr.detrend("demean")
                tr.detrend("linear")
                tr.taper(max_percentage=float(taperMaxPercent), type=taperType)
                tr.filter(
                    filterType,
                    freqmin=filterFreqMin,
                    freqmax=filterFreqMax,
                    corners=float(filterCorners),
                )
                # Convert from m/s^2 to cm/s^2
                tr.data *= 100.0
                logging.info(f"--valor max de la traza {tr.stats.channel} en cm/s**2 {max(tr.data)}--\n")
            except Exception as e:
                #print(f"Error processing {tr.id}: {e}")
                logging.error("--ERROR Fallo el try de lectura para %s--\n" % e)
                logging.error(f"Error processing {tr.id}: {e}")


        matplotlib.use("agg")
        fig, axes = plt.subplots(len(strNew), 1, figsize=(12, 8), sharex=True)
        max_amp_global = max(abs(tr.data).max() for tr in strNew)
        logging.info(f"------Amplitud global para grafico {strNew[0].stats.station} es {max_amp_global}--\n")

        nombreEstacion = strNew[0].stats.station


        n_trazas = len(strNew)
        fig, axes = plt.subplots(
            n_trazas,
            1,
            figsize=(10, 7),
            sharex=True,
            gridspec_kw={'height_ratios': [1] * n_trazas}
        )
        if n_trazas == 1:
            axes = [axes]  # Asegurar que axes sea lista si hay una sola traza

        # 5) Colores asignados por canal
        colores = {'HNZ': 'tab:red', 'HNN': 'tab:green', 'HNE': 'tab:blue'}

        # 6) Registrar el instante inicial y final (UTC)
        inicio = strNew[0].stats.starttime
        fin = strNew[0].stats.endtime

        # 7) Graficar cada traza con tiempos reales en segundos
        for idx, trace in enumerate(strNew):
            ax = axes[idx]
            chan = trace.stats.channel
            # Segundos relativos desde el inicio de la traza
            times = trace.times()
            ax.plot(
                times,
                trace.data,
                color=colores.get(chan, 'k'),
                linewidth=0.8,
                alpha=0.9,
                label=f"{trace.stats.network}.{trace.stats.station}.{trace.stats.location or '--'}.{chan}"
            )
            ax.set_ylabel("Amplitud (cm/s\xb2)")
            ax.set_ylim(-max_amp_global * 1.05, max_amp_global * 1.05)
            ax.grid(True, which='major', linestyle='--', linewidth=0.5, alpha=0.7)
            # Mostrar etiqueta en texto dentro del subplot
            ax.text(
                0.01, 0.9,
                f" ",
                transform=ax.transAxes,
                fontsize=9,
                verticalalignment='top',
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.6, edgecolor="none")
            )

        # 8) Etiqueta común del eje X
        axes[-1].set_xlabel("Tiempo (s)")
        fig.suptitle(
            f"Estación {strNew[0].stats.station} — {inicio.isoformat()} a {fin.isoformat()} (UTC)",
            fontsize=14
        )

        # 9) Ajustar espacio y colocar leyenda compacta en cada subplot
        for ax in axes:
            ax.legend(loc="upper right", fontsize="x-small", frameon=False)

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.savefig(nombrearchivo, dpi=300)
        plt.close(fig)
        logging.info("--Termine la imagen de %s--\n" % nombreEstacion)





def main():
    parser = argparse.ArgumentParser(description="Recibe parámetros string y float")
    parser.add_argument("--imagenpng", type=str, required=True, help="donde guardar imagenes")
    parser.add_argument("--ruta", type=str, required=True, help="ruta del mseed")
    args = parser.parse_args()
    Plotear(args.imagenpng,args.ruta)



if __name__ == "__main__":
        sys.exit(main())
