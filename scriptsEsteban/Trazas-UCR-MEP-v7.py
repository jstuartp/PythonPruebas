#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import warnings
import pytz
import numpy as np
import matplotlib.pyplot as plt
import time
import concurrent.futures

from obspy import UTCDateTime, read, Stream
from obspy.io.mseed.headers import InternalMSEEDWarning
from matplotlib.dates import MinuteLocator, DateFormatter
from datetime import timedelta

warnings.filterwarnings("ignore", category=InternalMSEEDWarning)

# -------------------------------------------------------------------------
# 1. Definición de función para procesar cada estación
# -------------------------------------------------------------------------

def procesar_estacion(i, net, full_sta, loc, cha, estacion_nombres, data_directory, t_inicio, t_fin, ax):
    print(f"Procesando estación: {full_sta} ({i+1})")
    try:
        splitted = full_sta.split('.')
        if len(splitted) == 2:
            sta = splitted[1]
        else:
            sta = full_sta

        nombre_estacion = estacion_nombres.get(sta, sta)
        mseed_files = [
            os.path.join(data_directory, f)
            for f in os.listdir(data_directory)
            if f.startswith(sta) and f.endswith('.mseed')
        ]
        
        if not mseed_files:
            raise FileNotFoundError(f"Archivos MSEED no encontrados para {sta}")

        st = Stream()
        for file in mseed_files:
            st += read(file)
        
        if len(st) == 0:
            ax[i].plot([t_inicio.matplotlib_date, t_fin.matplotlib_date], [0, 0], 'r-', linewidth=1.5)
            left_label = f"[0.00 cm/s²] {sta}"
            ax[i].text(-0.02, 1.0, left_label, transform=ax[i].transAxes,
                       ha='right', va='top', color='black', fontsize=8,
                       fontproperties={'weight': 'normal'})
            ax[i].text(1.02, 1.0, nombre_estacion, transform=ax[i].transAxes,
                       ha='left', va='top', color='black', fontsize=8,
                       fontproperties={'weight': 'normal'})
            ax[i].yaxis.set_visible(False)
            for spine in ax[i].spines.values():
                spine.set_visible(False)
            return

        # [Explicación:] Dividimos en trazas separadas si hay huecos.
        st = st.split()

        # [Explicación:] Lista para guardar amplitudes de cada traza y ajustar ejes/etiquetas al final.
        amplitudes = []

        # [Explicación:] Graficar cada traza, pero SIN imprimir etiquetas repetidas en cada iteración.
        for tr in st:
            tr.detrend("linear")
            tr.filter("highpass", freq=0.1, corners=4, zerophase=True)
            tr.filter("lowpass", freq=10.0, corners=4, zerophase=True)
            tr.filter("bandstop", freqmin=49, freqmax=51, corners=2, zerophase=True)

            data_cm_s2 = tr.data * 100.0
            # [Explicación:] Se guarda la amplitud máxima de esta traza.
            amplitudes.append(abs(data_cm_s2).max())

            tiempos = tr.times("matplotlib")
            ax[i].plot(tiempos, data_cm_s2, 'b-', linewidth=1.5)

        # [Explicación:] Calcular la amplitud global de la estación (todas las trazas).
        max_amplitud_global = max(amplitudes) if amplitudes else 0.0
        # [Explicación:] Ajuste vertical (antes se calculaba por traza). Lo hacemos global.
        y_lim = round(max_amplitud_global * 1.2, 2)
        ax[i].set_ylim(-y_lim * 1.5, y_lim * 1.5)

        # [Explicación:] Etiqueta izquierda con la amplitud máxima global.
        left_label = f"[{max_amplitud_global:.2f} cm/s²] {sta}"
        ax[i].text(-0.02, 1.0, left_label, transform=ax[i].transAxes,
                   ha='right', va='top', color='black', fontsize=8,
                   fontproperties={'weight': 'normal'})

        # [Explicación:] Etiqueta derecha con el nombre amigable.
        ax[i].text(1.02, 1.0, nombre_estacion, transform=ax[i].transAxes,
                   ha='left', va='top', color='black', fontsize=8,
                   fontproperties={'weight': 'normal'})

        for spine in ax[i].spines.values():
            spine.set_visible(False)
        ax[i].yaxis.set_visible(False)
        ax[i].set_xlim(t_inicio.matplotlib_date, t_fin.matplotlib_date)

    except Exception as e:
        print(f"Error al procesar datos de {net}.{full_sta}: {e}")
        ax[i].plot([t_inicio.matplotlib_date, t_fin.matplotlib_date], [0, 0], 'r-', linewidth=1.5)
        left_label = f"[0.00 cm/s²] {sta}"
        nombre_estacion = estacion_nombres.get(sta, sta)
        ax[i].text(-0.02, 1.0, left_label, transform=ax[i].transAxes,
                   ha='right', va='top', color='black', fontsize=8,
                   fontproperties={'weight': 'normal'})
        ax[i].text(1.02, 1.0, nombre_estacion, transform=ax[i].transAxes,
                   ha='left', va='top', color='black', fontsize=8,
                   fontproperties={'weight': 'normal'})
        ax[i].yaxis.set_visible(False)
        for spine in ax[i].spines.values():
            spine.set_visible(False)

# -------------------------------------------------------------------------
# 2. Función principal
# -------------------------------------------------------------------------

def main():
    start_time = time.time()
    print("Iniciando el proceso...")
    data_directory = "storage"
    ahora = UTCDateTime()
    t_inicio = ahora - 3600
    t_fin = ahora

    # -------------------------------------------------------------------------
    # 3. Cargar nombres de estaciones
    # -------------------------------------------------------------------------
    print("Cargando nombres de estaciones...")
    estacion_nombres = {}
    with open("lista_de_estaciones_mep_por_nombre.txt", "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                code = parts[0]
                nombre = parts[1]
                estacion_nombres[code] = nombre

    # -------------------------------------------------------------------------
    # 4. Leer archivo de estaciones
    # -------------------------------------------------------------------------
    print("Leyendo lista de estaciones...")
    estaciones = []
    with open("lista_de_estaciones_mep_por_codigo.txt", "r") as f:
        for line in f:
            partes = line.strip().split()
            if len(partes) >= 2:
                net = partes[0]
                full_sta = partes[1]
                loc = "*"
                cha = "H*"
                estaciones.append((net, full_sta, loc, cha))

    if not estaciones:
        print("No hay estaciones definidas.")
        return

    # -------------------------------------------------------------------------
    # 5. Crear figura para graficar
    # -------------------------------------------------------------------------
    print("Creando figura para graficar...")
    fig, ax = plt.subplots(
        nrows=len(estaciones),
        ncols=1,
        figsize=(9, 12),
        dpi=150,
        sharex=True
    )
    if len(estaciones) == 1:
        ax = [ax]

    plt.subplots_adjust(left=0.15, right=0.75, hspace=0.4, top=0.95, bottom=0.05)

    # -------------------------------------------------------------------------
    # 6. Procesar estaciones en paralelo
    # -------------------------------------------------------------------------
    print("Procesando estaciones en paralelo...")
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(
                procesar_estacion, i, net, full_sta, loc, cha,
                estacion_nombres, data_directory, t_inicio, t_fin, ax
            )
            for i, (net, full_sta, loc, cha) in enumerate(estaciones)
        ]
        concurrent.futures.wait(futures)

    # -------------------------------------------------------------------------
    # 7. Ajustar eje X
    # -------------------------------------------------------------------------
    ax[-1].xaxis.set_major_locator(MinuteLocator(interval=10))
    ax[-1].xaxis.set_minor_locator(MinuteLocator(interval=5))
    ax[-1].xaxis.set_major_formatter(DateFormatter('%H:%M', tz=pytz.FixedOffset(-6*60)))
    ax[-1].set_xlabel("Tiempo (Hora local)", fontsize=8, color='black')

    fig.autofmt_xdate()

    # -------------------------------------------------------------------------
    # 8. Título y texto inferior
    # -------------------------------------------------------------------------
    fig.text(0.01, -0.02, (t_inicio.datetime - timedelta(hours=6)).strftime('%H:%M'),
             fontsize=7, va='bottom', ha='left', color='black')
    fig.text(0.99, -0.02, (t_fin.datetime - timedelta(hours=6)).strftime('%H:%M'),
             fontsize=7, va='bottom', ha='right', color='black')

    # -------------------------------------------------------------------------
    # 9. Guardar y mostrar
    # -------------------------------------------------------------------------
    print("Guardando imagen generada...")
    plt.savefig("MEP-UCR-v7.png", dpi=150, facecolor='white')
    plt.show()

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"\nTiempo total de ejecución: {elapsed_time:.2f} segundos ({elapsed_time/60:.2f} minutos)")

if __name__ == "__main__":
    main()
