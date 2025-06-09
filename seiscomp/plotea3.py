#!/usr/bin/env seiscomp-python
# -*- coding: utf-8 -*-
import glob

import matplotlib
import obspy
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
    max_amp_global = max(abs(tr.data).max() for tr in strNew)

    nombreEstacion = ""
    archivo = open("/home/lis/waves/Plotea.log", "a")
    archivo.write(str(UTCDateTime.now()))
    archivo.write("--Voy a procesar imagen de %s--\n" %imgagenpng)
    archivo.close()

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
        times = trace.times()  # Segundos relativos desde trace.stats.starttime :contentReference[oaicite:15]{index=15}
        ax.plot(
            times,
            trace.data,
            color=colores.get(chan, 'k'),
            linewidth=0.8,
            alpha=0.9,
            label=f"{trace.stats.network}.{trace.stats.station}.{trace.stats.location or '--'}.{chan}"
        )
        ax.set_ylabel("Amplitud (counts)")
        ax.set_ylim(-max_amp_global * 1.05, max_amp_global * 1.05)
        ax.grid(True, which='major', linestyle='--', linewidth=0.5, alpha=0.7)
        # Mostrar etiqueta en texto dentro del subplot
        ax.text(
            0.01, 0.9,
            f"{trace.id}   Fs={trace.stats.sampling_rate:.1f} Hz",
            transform=ax.transAxes,
            fontsize=9,
            verticalalignment='top',
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.6, edgecolor="none")
        )

    # 8) Etiqueta común del eje X
    axes[-1].set_xlabel("Tiempo (s) desde inicio")
    fig.suptitle(
        f"Estación {strNew[0].stats.station} — {inicio.isoformat()} a {fin.isoformat()} (UTC)",
        fontsize=14
    )

    # 9) Ajustar espacio y colocar leyenda compacta en cada subplot
    for ax in axes:
        ax.legend(loc="upper right", fontsize="x-small", frameon=False)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(imgagenpng, dpi=300)
    plt.close(fig)
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
