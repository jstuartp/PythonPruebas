#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import glob
import logging
import re
import shutil
import matplotlib
from future.backports.datetime import timedelta
from obspy.clients.fdsn import Client
from obspy import read, UTCDateTime
from threading import Timer
import time
from concurrent.futures import ProcessPoolExecutor
import sys
import traceback
import datetime
from datetime import datetime as dt_python, timedelta
import os
import math
import logging as mylog
import pymysql
import subprocess
import pandas as pd
import matplotlib.pyplot as plt
from scipy.integrate import cumulative_trapezoid
from scipy.signal import butter, filtfilt

# Se mantienen las importaciones de seiscomp necesarias para otros scripts
from seiscomp import datamodel, client
from obspy import Stream
from obspy.core.inventory import Inventory
from obspy import read_inventory
from obspy.geodetics.base import gps2dist_azimuth
from geopy.distance import geodesic
from obspy import io
from obspy.signal.filter import envelope
import numpy as np
from dotenv import load_dotenv
from pathlib import Path
import json
from joblib import Parallel, delayed

# CONSTANTES BASES DE DATOS SEISCOMP
my_host = 'localhost'
my_user = 'sysop'
my_password = 'sysop'
my_db = 'seiscomp'

# CONSTANTES BASES DE DATOS LOCAL
local_host = '163.178.170.245'
local_user = 'informes'
local_password = 'B8EYvZRTpTUDquc3'
local_db = 'informes'

# Parámetros configurables
OUTPUT_DIR = "/home/lis/waves/sds/"  # Carpeta de entrada/salida para los MiniSEED
OUTPUT_JSON = "/home/lis/waves/imagenes/"  # Carpeta de salida para los JSON
TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"  # Formato ISO para tiempo inicial
ESTRUCTURAS_SCRIPT = "/home/lis/waves/scripts/corta_edificios.py"

# Ruta absoluta o relativa al archivo .env
ruta_env = Path("/home/lis/.env")
load_dotenv(dotenv_path=ruta_env)

# Esto se ejecuta una sola vez al arrancar el script.
waveslogger = logging.getLogger("Sccortawaveslogger.")
waveslogger.setLevel(logging.INFO)
# Handler de Consola
c_handler = logging.StreamHandler(sys.stdout)
c_format = logging.Formatter('%(asctime)s - GLOBAL - %(message)s')
c_handler.setFormatter(c_format)
waveslogger.addHandler(c_handler)


class EventProcessor:

    def __init__(self, event_id):
        self.event_id = event_id

        # Configuracion por defecto (anteriormente cargada por initConfiguration)
        self.taperMaxPercent = 0.05
        self.taperType = "hann"
        self.filterType = "bandpass"
        self.filterFreqMin = 0.05
        self.filterFreqMax = 25
        self.filterCorners = 2

        self.rutaRaiz = "/home/lis/waves/corta/"
        self.rutaImagenes = "/home/lis/waves/imagenes/"
        self.direccionWebServer = "lis@163.178.170.245:/var/cache/graficas_seiscomp/waves"
        self.seiscomp_path = os.environ.get("SEISCOMP_ROOT", "/home/lis/seiscomp")
        self.SDS_ROOT = os.path.join(self.seiscomp_path, "var/lib/archive/")
        self.procesos_pendientes = []

    def configurar_log_evento(self, event_id, myhora):
        horalog = myhora.replace(" ", "")
        horalog = horalog.replace(":", "")
        nombre_archivo = f"/home/lis/waves/logs/log_evento_{horalog}_{event_id}.log"

        f_handler = logging.FileHandler(nombre_archivo)
        f_handler.setLevel(logging.INFO)
        f_format = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        f_handler.setFormatter(f_format)
        waveslogger.addHandler(f_handler)
        return f_handler

    def limpiar_log_evento(self, handler):
        handler.close()
        waveslogger.removeHandler(handler)

    def doSomethingWithEvent(self):
        # Extraer informacion de la BD usando el ID
        datosEvento = self.obtener_datos_por_id(self.event_id)
        if not datosEvento:
            waveslogger.error(f"No se encontro informacion para el evento {self.event_id} en la BD.")
            return

        myhora = datosEvento["hora"]
        dt = dt_python.strptime(str(myhora), "%Y-%m-%d %H:%M:%S")

        file_handler = self.configurar_log_evento(self.event_id, str(myhora))
        waveslogger.info(f"LOG del calculo de sccortawaves para el evento {self.event_id}")
        waveslogger.info(f"LOG Iniciado en: {str(myhora)}")

        tiempo = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        inv_path = self.seiscomp_path + "/share/scripts/inventory_full_fdns.xml"

        # Procesar los datos
        inf = self.proceso(tiempo, inv_path, self.event_id, dt)
        parametroa = self.rutaImagenes + self.event_id + "/"

        if inf == 1:
            for p in self.procesos_pendientes:
                p.wait()

            subprocess.run(["python3", self.seiscomp_path + "/share/scripts/lis/espectrosGeoJson4.py", self.event_id])
            subprocess.run(['scp', '-r', parametroa, self.direccionWebServer], capture_output=True, text=True)
            waveslogger.info(f"IMAGENES COPIADAS para evento {self.event_id}")

        waveslogger.info(f"Cerrando el log de {self.event_id}")
        self.limpiar_log_evento(file_handler)

    def load_inventory_sc3(self, inv_path):
        return read_inventory(inv_path, format="STATIONXML")

    def filtro_paso_alto(self, data, cutoff, fs, order=4):
        nyq = 0.5 * fs
        normal_cutoff = cutoff / nyq
        b, a = butter(order, normal_cutoff, btype='high', analog=False)
        y = filtfilt(b, a, data)
        return y

    def filtro_pasa_banda(self, data, fs, freq_min=0.05, freq_max=25.0, corners=2, taper_percent=0.05):
        npts = len(data)
        taper_length = int(npts * taper_percent)

        if taper_length > 0:
            window = np.hanning(2 * taper_length)
            taper_array = np.ones(npts)
            taper_array[:taper_length] = window[:taper_length]
            taper_array[-taper_length:] = window[-taper_length:]
            data = data * taper_array

        nyq = 0.5 * fs
        low = freq_min / nyq
        high = freq_max / nyq
        b, a = butter(corners, [low, high], btype='bandpass', analog=False)
        y = filtfilt(b, a, data)
        return y

    def calculate_pgv(self, tr):
        dt = 1.0 / 200
        vel_raw = cumulative_trapezoid(tr, dx=dt, initial=0.0)
        vel_clean = vel_raw - np.mean(vel_raw)
        vel_clean = self.filtro_pasa_banda(vel_clean, fs=200)
        pgv = np.max(np.abs(vel_clean))
        return pgv * 100

    def calculate_pgd(self, tr):
        dt = 1.0 / 200
        vel_raw = cumulative_trapezoid(tr, dx=dt, initial=0.0)
        vel_clean = vel_raw - np.mean(vel_raw)
        vel_clean = self.filtro_pasa_banda(vel_clean, fs=200)
        disp_raw = cumulative_trapezoid(vel_clean, dx=dt, initial=0.0)
        disp_clean = disp_raw - np.mean(disp_raw)
        disp_clean = self.filtro_pasa_banda(disp_clean, fs=200)
        pgd = np.max(np.abs(disp_clean))
        return pgd * 100

    def calculate_pga(self, tr, inventory, network, station, location, channel):
        # YA NO SE ELIMINA LA RESPUESTA INSTRUMENTAL PORQUE ESTAN EN m/s2
        try:
            tr.detrend("demean")
            tr.detrend("linear")
            tr.taper(max_percentage=float(self.taperMaxPercent), type=self.taperType)
            tr.filter(self.filterType, freqmin=float(self.filterFreqMin),
                      freqmax=float(self.filterFreqMax),
                      corners=float(self.filterCorners))
            pga = np.max(np.abs(tr.data))

            waveslogger.info("PGA NORMAL PARA %s" % tr.stats.station)
            waveslogger.info("Canal %s" % tr.stats.channel)
            waveslogger.info("VALOR %s" % pga)
        except Exception as e:
            st_umask = tr.split()
            a = []
            for tr1 in st_umask:
                print("UMASK %s" % station)
                tr1.detrend("demean")
                tr1.detrend("linear")
                tr1.taper(max_percentage=float(self.taperMaxPercent), type=self.taperType)
                tr1.filter(self.filterType, freqmin=float(self.filterFreqMin),
                           freqmax=float(self.filterFreqMax),
                           corners=float(self.filterCorners))
                a.append(np.max(np.abs(tr1.data)))
                pga = max(a)
            waveslogger.warning(f"Error CALCULANDO PGA {network}.{station}.{tr.stats.channel}: {e}")
        return pga * 100.0  # Convertir a cm/s^2

    def proceso(self, time_inicial_str, inv_path, event_id, dt_obj):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        t0 = UTCDateTime(time_inicial_str)
        t1 = t0 - 180
        t2 = t0 + 180
        waveslogger.info(f"El evento procesa archivos locales para tiempo {t0}")

        inventory = self.load_inventory_sc3(inv_path)

        resultados = []
        streams = []
        maximos = []
        informe = 0

        # Directorio de los MSEED ya cortados
        mseed_folder = os.path.join(OUTPUT_DIR, event_id)

        for net in inventory:
            for sta in net:
                if sta.end_date is None:
                    waveslogger.info(f"Inicio proceso estacion {sta.code}")
                    try:
                        network = net.code
                        station = sta.code
                        site_name = sta.site.name
                        channel = sta[0]
                        soil = ""
                        try:
                            manufacturer = channel.sensor.manufacturer
                            serial = channel.sensor.serial_number
                        except Exception as e:
                            manufacturer = "unknown"
                            serial = "unknown"
                        elevation = channel.elevation
                        location = "**"
                        channel = "HN*"
                        pgasChannel = []
                        pgvsChannel = []
                        pgdsChannel = []
                    except Exception as e:
                        waveslogger.error(f"Error importante con la estacion {sta.code} {e}")

                    try:
                        if station == "BID0":
                            targets = [
                                {"loc": "00", "sta_name": "BID0"},
                                {"loc": "01", "sta_name": "BID1"}
                            ]
                        else:
                            targets = [
                                {"loc": location, "sta_name": station}
                            ]

                        for target in targets:
                            current_loc = target["loc"]
                            current_sta_name = target["sta_name"]

                            pgasChannel = []
                            pgvsChannel = []
                            pgdsChannel = []

                            # LEER ARCHIVOS MSEED DESDE CARPETA LOCAL (Ya cortados y procesados)
                            patron = os.path.join(mseed_folder, f"{network}_{current_sta_name}_*.mseed")
                            archivos_mseed = glob.glob(patron)

                            st = Stream()
                            for arch in archivos_mseed:
                                if "RAW" not in arch:  # Evitar procesar archivos RAW si existen
                                    st += read(arch)

                            if not st or len(st) == 0:
                                waveslogger.warning(
                                    f"Error en {network}.{current_sta_name} (loc {current_loc}): no hay trazas locales en {mseed_folder}")
                                continue

                            st.merge(method=1, fill_value='interpolate')
                            stRaw = st.copy()

                            net_inv = inventory.select(network=network, station=station)[0]
                            mysta = net_inv.stations[0]

                            m = v = d = 0.0

                            for tr in st:
                                try:
                                    pga = self.calculate_pga(tr, inventory, network, station, current_loc, channel)
                                    waveslogger.info(
                                        f"Estacion: {current_sta_name} canal: {tr.stats.channel} PGA {pga}")

                                    pgv = self.calculate_pgv(tr.copy())
                                    waveslogger.info(
                                        f"Estacion: {current_sta_name} canal: {tr.stats.channel} PGV {pgv}")

                                    pgd = self.calculate_pgd(tr.copy())
                                    waveslogger.info(
                                        f"Estacion: {current_sta_name} canal: {tr.stats.channel} PGD {pgd}")

                                    if pga > m: m = pga
                                    if pgv > v: v = pgv
                                    if pgd > d: d = pgd

                                    try:
                                        chan_lower = str(tr.stats.channel).lower()
                                        pgasChannel.append({chan_lower: pga})
                                        pgvsChannel.append({f"{chan_lower}_vel": pgv})
                                        pgdsChannel.append({f"{chan_lower}_des": pgd})
                                    except Exception as e:
                                        waveslogger.error(f"Error construyendo diccionarios de canales: {e}")

                                except Exception as e:
                                    waveslogger.error(f"Canales no validos: {e}")
                                    continue

                            maximos.append({
                                "station": current_sta_name,
                                "maximos": m
                            })

                            resultados.append({
                                "fecha_evento": t0,
                                "fecha_calculo": dt_python.now(),
                                "evento": event_id,
                                "tipo": 1,
                                "network": network,
                                "estacion": current_sta_name,
                                "latitud": mysta.latitude,
                                "longitud": mysta.longitude,
                                "site_name": site_name,
                                "altitud": elevation,
                                "site_manufacturer": manufacturer,
                                "site_serial": serial
                            })

                            ultimo = resultados[-1]
                            for i in pgasChannel: ultimo.update(i)
                            for x in pgvsChannel: ultimo.update(x)
                            for y in pgdsChannel: ultimo.update(y)

                            streams.append({
                                "evento": event_id,
                                "network": network,
                                "station": current_sta_name,
                                "st": st,
                                "stRaw": stRaw,
                                "t1": t1,
                                "t2": t2,
                            })
                    except Exception as e:
                        sta_info = mysta if 'mysta' in locals() else "N/A"
                        waveslogger.error(f"Error en {network}.{station}: leyendo traza y arreglos {e}__ {sta_info}")

        if not maximos:
            waveslogger.warning(f"No se encontraron maximos para el evento {event_id}. Terminando procesamiento.")
            return informe

        maximos = sorted(maximos, key=lambda x: -x["maximos"])
        waveslogger.info(f"6 aceleraciones maximas del evento: {maximos[:6]}")

        # YA NO SE CORTAN NI GUARDAN MSEEDS PORQUE YA EXISTEN

        if maximos[4]["maximos"] >= 2 if len(maximos) > 4 else (maximos[0]["maximos"] >= 2):
            informe = 1

            guarda_jsons = subprocess.Popen(
                ["python3", "/home/lis/seiscomp/share/scripts/lis/mseed_to_json_124.py",
                 "/home/lis/waves/sds/" + event_id]
                , stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.procesos_pendientes.append(guarda_jsons)

            jsons_mov_sismico = subprocess.run(
                ["python3", "/home/lis/seiscomp/share/scripts/lis/mov_sismico.py", "--directorio",
                 "/home/lis/waves/sds/" + event_id, "--resultado", "/home/lis/waves/imagenes/" + event_id + "/"]
                , stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="ignore")

            num_trabajos = 70
            crealis = Parallel(n_jobs=num_trabajos, prefer="threads")(
                delayed(self.archivoLis)(resultados[s], event_id, dt_obj) for s in range(len(resultados)))

            res1 = subprocess.Popen(['rsync', '-avz', f"/home/lis/waves/LIS/{event_id}/",
                                     "lis@163.178.101.86:/home/lis/formato_lis/registros_revisados"])
            res2 = subprocess.Popen(['rsync', '-avz', f"/home/lis/waves/LIS/{event_id}/",
                                     "lis@163.178.109.104:/home/lis/formato_lis/registros_revisados"])
            res3 = subprocess.Popen(['rsync', '-avz', f"/home/lis/waves/LIS/{event_id}/",
                                     "lis@163.178.174.210:/home/lis/formato_lis/registros_revisados"])
            res4 = subprocess.run(['rsync', '-avz', f"/home/lis/waves/LIS/{event_id}",
                                   "lis@163.178.109.101:/home/lis/repositorio_archivo_lis/por_eventos/"])

            self.procesos_pendientes.extend([res1, res2, res3])

            print("Voy a llamar a estructuras")
            estructuras = subprocess.Popen(
                ["ssh", "lis@163.178.171.47",
                 f" nohup python3 {ESTRUCTURAS_SCRIPT} --start {dt_obj.strftime('%Y-%m-%dT%H:%M:%S')}"
                 f" --event {event_id}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )

            for res in resultados:
                idPga = self.chequeaBdPga(res["estacion"], res["evento"])
                if not idPga:
                    self.insertaBd(res)
                else:
                    self.updateBd(res, idPga)
        else:
            waveslogger.info(f"El evento {event_id} No cumple con el umbral de aceleracion ")

        datosEvento = self.obtener_datos_por_id(event_id)
        fechaEvento = self.chequeaEvento(event_id)

        if not fechaEvento:
            waveslogger.info(f"Guardando nuevo evento {event_id} en base de datos")
            self.insertarEvento(datosEvento, maximos[0]["maximos"], maximos[0]["station"], informe)
            resultJMA = subprocess.run(
                ["python3", self.seiscomp_path + "/share/scripts/lis/jma.py", "--evento",
                 event_id, "--ruta", OUTPUT_DIR + event_id, "--tipo", "1"])
            if resultJMA: waveslogger.info("Exito guardando JMA")
        else:
            t0 = UTCDateTime(dt_obj.strftime("%Y-%m-%dT%H:%M:%S"))
            if fechaEvento['fecha'] < t0:
                waveslogger.info(f"Actualizando evento {event_id} existente en la DB")
                self.actualizaEvento(datosEvento, event_id, maximos[0]["maximos"], maximos[0]["station"], informe)
                resultJMA = subprocess.run(
                    ["python3", self.seiscomp_path + "/share/scripts/lis/jma.py", "--evento",
                     event_id, "--ruta", OUTPUT_DIR + event_id, "--tipo", "2"])
            elif fechaEvento['fecha'] >= t0:
                waveslogger.info(f"Insertando evento {event_id} existente en la DB")
                self.actualizaEvento(datosEvento, event_id, maximos[0]["maximos"], maximos[0]["station"], informe)
                resultJMA = subprocess.run(
                    ["python3", self.seiscomp_path + "/share/scripts/lis/jma.py", "--evento",
                     event_id, "--ruta", OUTPUT_DIR + event_id, "--tipo", "1"])

        return informe

    def epicentral_and_hypocentral_obspy(self, lat_epi, lon_epi, lat_sta, lon_sta, depth_km):
        dist_m, az, baz = gps2dist_azimuth(lat_epi, lon_epi, lat_sta, lon_sta)
        delta_km = dist_m / 1000.0
        Rh = math.sqrt(delta_km ** 2 + depth_km ** 2)
        return {
            "dist_epicentral_km": delta_km,
            "dist_hipocentral_km": Rh,
            "azimuth_deg": az,
            "back_azimuth_deg": baz
        }

    def archivoLis(self, resultados, event_id, dt_obj):
        try:
            if max(resultados['hnn'], resultados['hne'], resultados['hnz']) >= 2:
                carpeta = os.path.join(OUTPUT_DIR, event_id)
                patron = os.path.join(carpeta, f"*_{resultados['estacion']}_*.mseed")
                archivos = glob.glob(patron)

                if not archivos: return

                os.makedirs("/home/lis/waves/LIS/" + event_id, exist_ok=True)
                datos = self.obtener_datos_por_id(event_id)

                punto_epi = (datos['latitud'], datos["longitud"])
                punto_sta = (resultados['latitud'], resultados["longitud"])
                distancias = self.epicentral_and_hypocentral_obspy(datos['latitud'], datos["longitud"],
                                                                   resultados['latitud'], resultados["longitud"],
                                                                   datos["profundidad"])
                epicentral_dist = geodesic(punto_epi, punto_sta).kilometers
                soil = self.obtener_suelo(resultados['estacion'])
                epicenter_str = self.ciudad_mas_cercana_descripcion(datos['latitud'], datos['longitud'])

                result = subprocess.run(
                    ["python3", self.seiscomp_path + "/share/scripts/lis/escribe_lis.py", "--mseed", archivos[0],
                     "--out",
                     f"/home/lis/waves/LIS/{event_id}/{dt_obj.strftime('%Y%m%d%H%M')}{resultados['estacion']}.lis",
                     "--station-name", resultados['site_name'], "--event-date", dt_obj.strftime('%Y/%m/%d %H:%M'),
                     "--event-lat", str(datos['latitud']), "--event-lon", str(datos["longitud"]), "--event-depth",
                     str(round(datos["profundidad"], 1)),
                     "--event-mw", str(round(datos["magnitud"], 1)),
                     "--station-code", resultados['estacion'], "--station-lat", str(resultados['latitud']),
                     "--station-lon", str(resultados['longitud']),
                     "--pga-n00e", str(resultados['hnn']), "--pga-updo", str(resultados['hnz']), "--pga-n90e",
                     str(resultados['hne']), "--station-elev", str(resultados['altitud']),
                     "--instrument-type", str(resultados['site_manufacturer']), "--serial",
                     str(resultados['site_serial']), "--epicentral-km", str(epicentral_dist),
                     "--hypocentral-km", str(distancias['dist_hipocentral_km']), "--azimuth",
                     str(distancias['azimuth_deg']), "--site-condition", "FFD", "--soil-type", str(soil),
                     "--epicenter", epicenter_str
                     ])
        except Exception as e:
            waveslogger.error(f"El archivo no tiene las tres componentes {resultados['estacion']}")
            waveslogger.error(f"---Error se registra como: {e}")

    def ciudad_mas_cercana_descripcion(self, lat_punto: float, lon_punto: float, lat_col: str = "latitud",
                                       lon_col: str = "longitud", name_col: str = "distrito") -> str:
        csv_path = os.path.join(self.seiscomp_path, "share", "scripts", "lis", "ciudades.csv")
        try:
            df = pd.read_csv(csv_path)
        except FileNotFoundError:
            raise FileNotFoundError(f"No se encontró el archivo CSV: {csv_path!r}")

        df = df.dropna(subset=[lat_col, lon_col, name_col])
        R = 6371.0088
        phi_p = math.radians(lat_punto)
        lam_p = math.radians(lon_punto)
        min_dist = float("inf")
        ciudad_min = None
        phi_c_min = None
        lam_c_min = None

        for row in df.itertuples(index=False):
            lat_c = float(getattr(row, lat_col))
            lon_c = float(getattr(row, lon_col))
            nombre_c = str(getattr(row, name_col))

            phi_c = math.radians(lat_c)
            lam_c = math.radians(lon_c)
            dphi = phi_p - phi_c
            dlam = lam_p - lam_c
            a = math.sin(dphi / 2) ** 2 + math.cos(phi_c) * math.cos(phi_p) * math.sin(dlam / 2) ** 2
            c = 2 * math.asin(min(1.0, math.sqrt(a)))
            dist_km = R * c

            if dist_km < min_dist:
                min_dist = dist_km
                ciudad_min = nombre_c
                phi_c_min = phi_c
                lam_c_min = lam_c

        dlam_min = lam_p - lam_c_min
        y = math.sin(dlam_min) * math.cos(phi_p)
        x = (math.cos(phi_c_min) * math.sin(phi_p) - math.sin(phi_c_min) * math.cos(phi_p) * math.cos(dlam_min))
        theta = math.atan2(y, x)
        brng_deg = (math.degrees(theta) + 360.0) % 360.0

        def octante(ang: float) -> str:
            if ang >= 337.5 or ang < 22.5:
                return "N."
            elif ang < 67.5:
                return "N.E."
            elif ang < 112.5:
                return "E."
            elif ang < 157.5:
                return "S.E."
            elif ang < 202.5:
                return "S."
            elif ang < 247.5:
                return "S.O."
            elif ang < 292.5:
                return "O."
            else:
                return "N.O."

        dir_cardinal = octante(brng_deg)
        return f'{min_dist:.1f} kilómetros al {dir_cardinal} de {ciudad_min}'

    def obtener_suelo(self, estacion_buscar):
        dir = self.seiscomp_path + "/share/scripts/lis/curvas_diseno/suelos.csv"
        df = pd.read_csv(dir)
        dicc = dict(zip(df['estacion'], df['suelo']))
        return dicc.get(estacion_buscar, None)

    def actualizaEvento(self, datos, idEvento, maxAcelera, lugarAcelera, informe):
        conn = pymysql.connect(
            host=local_host, user=local_user, password=local_password, db=local_db, charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        valores = [datos["hora"], datos["latitud"], datos["longitud"], datos["magnitud"], maxAcelera, lugarAcelera,
                   datos["profundidad"], informe, idEvento]
        try:
            with (conn.cursor() as cursor):
                sql = (
                    "UPDATE historico_sismos SET "
                    "`fechaEvento` = %s,"
                    "`latitudEvento`= %s,"
                    "`longitudEvento`= %s,"
                    "`magnitudEvento`= %s,"
                    "`aceleracionEvento`= %s,"
                    "`lugarAceleracion`= %s,"
                    "`profundidadEvento`= %s,"
                    "`informe`= %s "
                    "WHERE idEvento = %s")
                cursor.execute(sql, valores)
            conn.commit()
            waveslogger.info("--EXITO---------Evento actualizado  \n")
        except Exception as e:
            waveslogger.error("--ERROR---------Se registro el siguiente error actualizando datos %s  \n" % e)
        finally:
            conn.close()

    def insertarEvento(self, datos, maxpga, stationpga, informe):
        conn = pymysql.connect(
            host=local_host, user=local_user, password=local_password, db=local_db, charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        valores = [datos["publicID"], datos["hora"], datos["latitud"], datos["longitud"], datos["magnitud"], maxpga,
                   stationpga, datos["profundidad"], informe]
        try:
            with (conn.cursor() as cursor):
                sql = (
                    "INSERT INTO historico_sismos ("
                    "idEvento, fechaEvento, latitudEvento, longitudEvento, magnitudEvento, aceleracionEvento, lugarAceleracion, profundidadEvento, informe"
                    ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);")
                cursor.execute(sql, valores)
            conn.commit()
            waveslogger.info("--EXITO---------New event saved  \n")
        finally:
            conn.close()

    def insertaBd(self, datos):
        try:
            valores = [datos['fecha_evento'], datos['fecha_calculo'], datos['evento'], datos['tipo'], datos['estacion'],
                       datos['latitud'], datos['longitud'], datos['hne'], datos['hnn'], datos['hnz'],
                       max(datos['hne'], datos['hnn'], datos['hnz']),
                       datos['evento'] + "/" + datos['network'] + "_" + datos['estacion'] + "_" + datos[
                           'fecha_evento'].strftime('%Y%m%dT%H%M%S'),
                       self.filterFreqMin, self.filterFreqMax,
                       datos['hne_vel'], datos['hnn_vel'], datos['hnz_vel'],
                       datos['hne_des'], datos['hnn_des'], datos['hnz_des']]
        except Exception as err:
            waveslogger.error("--ERROR---------Fail in channels for station %s " % datos['estacion'])
            return

        conn = pymysql.connect(
            host=local_host, user=local_user, password=local_password, db=local_db, charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        try:
            with (conn.cursor() as cursor):
                sql = (
                    "INSERT INTO `Pga` (`fecha_evento`,`fecha_calculo`,`nombre_evento`,`tipo_estacion`,`estacion`, "
                    "`latitud`, `longitud`, `hne_pga`, `hnn_pga`, `hnz_pga`,`maximo` ,`rutaWaveform`,`min_filter`,`max_filter`,"
                    "`hne_pgv`, `hnn_pgv`, `hnz_pgv`,`hne_pgd`, `hnn_pgd`, `hnz_pgd`)"
                    " VALUES (%s ,%s ,%s ,%s ,%s ,%s ,%s, %s ,%s ,%s ,%s ,%s,%s,%s,%s,%s,%s,%s,%s,%s)")
                cursor.execute(sql, valores)
            conn.commit()
            waveslogger.info("--EXITO---------Data save to Database  \n")
        finally:
            conn.close()

    def updateBd(self, datos, idPga):
        data_id = idPga[0]['id']
        try:
            valores = [datos['fecha_evento'], datos['fecha_calculo'], datos['evento'], datos['tipo'], datos['estacion'],
                       datos['latitud'],
                       datos['longitud'], datos['hne'], datos['hnn'], datos['hnz'], datos['hne_vel'], datos['hnn_vel'],
                       datos['hnz_vel'],
                       datos['hne_des'], datos['hnn_des'], datos['hnz_des'],
                       max(datos['hne'], datos['hnn'], datos['hnz']),
                       datos['evento'] + "/" + datos['network'] + "_" + datos['estacion'] + "_" + datos[
                           'fecha_evento'].strftime('%Y%m%dT%H%M%S'), self.filterFreqMin, self.filterFreqMax, data_id]
        except Exception as err:
            waveslogger.error("--ERROR---------Fail in channels for station %s " % datos['estacion'])
            return

        conn = pymysql.connect(
            host=local_host, user=local_user, password=local_password, db=local_db, charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        try:
            with (conn.cursor() as cursor):
                sql = (
                    "UPDATE Pga SET `fecha_evento`=%s,`fecha_calculo`=%s,`nombre_evento`=%s,`tipo_estacion`=%s,`estacion`=%s, `latitud`=%s,"
                    " `longitud`=%s, `hne_pga`=%s, `hnn_pga`=%s, `hnz_pga`=%s,"
                    " `hne_pgv`=%s, `hnn_pgv`=%s, `hnz_pgv`=%s,"
                    " `hne_pgd`=%s, `hnn_pgd`=%s, `hnz_pgd`=%s,"
                    "`maximo`=%s ,`rutaWaveform`=%s,`min_filter`=%s,`max_filter`=%s"
                    " WHERE idpga = %s")
                cursor.execute(sql, valores)
            conn.commit()
            waveslogger.info("--EXITO---------Data updated to Database  \n")
        finally:
            conn.close()

    def obtener_datos_por_id(self, eventoId):
        conn = pymysql.connect(
            host=my_host, user=my_user, password=my_password, db=my_db, charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        try:
            with (conn.cursor() as cursor):
                consulta = (
                    "select distinct PEvent.publicID, Origin.time_value as hora,  Origin.latitude_value as latitud,"
                    "Origin.longitude_value as longitud, M.magnitude_value as magnitud, Origin.depth_value as profundidad "
                    "from Origin,PublicObject as POrigin,Event,PublicObject as PEvent, Magnitude as M "
                    "where POrigin.publicID=Event.preferredOriginID and  M._parent_oid = Origin._oid "
                    "and Origin._oid=POrigin._oid and Event._oid=PEvent._oid "
                    "and PEvent.publicID = %s Order by Origin.time_value DESC;")
                cursor.execute(consulta, eventoId)
                resultado = cursor.fetchone()
        finally:
            conn.close()
        return resultado

    def chequeaBdPga(self, estacion, evento):
        conn = pymysql.connect(
            host=local_host, user=local_user, password=local_password, db=local_db, charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        try:
            with (conn.cursor() as cursor):
                consulta_sql = "select Pga.idpga as id From Pga WHERE nombre_evento = %s AND estacion = %s"
                cursor.execute(consulta_sql, (evento, estacion))
                resultados = cursor.fetchall()
            conn.commit()
        finally:
            conn.close()
        return resultados

    def chequeaEvento(self, evento):
        conn = pymysql.connect(
            host=local_host, user=local_user, password=local_password, db=local_db, charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        try:
            with (conn.cursor() as cursor):
                consulta_sql = "select fechaEvento as fecha From historico_sismos WHERE idEvento = %s "
                cursor.execute(consulta_sql, evento)
                resultados = cursor.fetchone()
            conn.commit()
        except Exception as e:
            waveslogger.error("--ERROR---------Se registro el siguiente error %s  \n" % e)
        finally:
            conn.close()
        return resultados


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 script.py <EVENT_ID>")
        sys.exit(1)

    event_id = sys.argv[1]
    app = EventProcessor(event_id)
    app.doSomethingWithEvent()


if __name__ == "__main__":
    main()