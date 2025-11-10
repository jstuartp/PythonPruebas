#!/usr/bin/env seiscomp-python
# -*- coding: utf-8 -*-
import glob
import argparse

import matplotlib
from future.backports.datetime import timedelta
from obspy.clients.fdsn import Client
from obspy import read, UTCDateTime
from threading import Timer
import time
from concurrent.futures import ProcessPoolExecutor
import sys
import traceback
import logging
import datetime
from datetime import datetime, timedelta
import os
import math
import pymysql
import subprocess
import pandas as pd
import matplotlib.pyplot as plt
from soupsieve.css_types import pickle_register


from time import strftime
from joblib import Parallel, delayed
import os

from obspy import UTCDateTime, read, Stream
from obspy.core.inventory import Inventory
from obspy import read_inventory
from obspy.geodetics.base import gps2dist_azimuth
from geopy.distance import geodesic
from obspy import io
#from obspy.signal.peak import pk_tr
from obspy.signal.filter import envelope
from obspy.clients.filesystem.sds import Client as SDSClient
from obspy.signal.invsim import simulate_seismometer
from datetime import timedelta
import numpy as np
from dotenv import load_dotenv
from pathlib import Path

#CONSTANTES BASES DE DATOS SEISCOMP
my_host = '163.178.101.110'
my_user = 'lis'
my_password = 'Ucr_lis_seiscomp_110'
my_db = 'seiscomp'

#CONSTANTES BASES DE DATOS LOCAL
local_host = '163.178.170.245'
local_user = 'informes'
local_password = 'B8EYvZRTpTUDquc3'
local_db = 'informes'
#local_host = 'localhost'
#local_user = 'root'
#local_password = 'jspz2383'
#local_db = 'sismos_lis'


# Parámetros configurables
#SDS_ROOT = "/home/lis/seiscomp/var/lib/archive/"                # Ruta al SDS de seiscomp
OUTPUT_DIR = "/home/lis/waves/eventos/"         # Carpeta de salida para los MiniSEED
TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"  # Formato ISO para tiempo inicial
# Dirección del servicio FDSN de su SeisComP (ajuste el host y puerto según su instalación)
FDSN_URL = "http://localhost:8080"  # Cambie localhost:8080 si corresponde
ESTRUCTURAS_SCRIPT ="/home/lis/waves/corta_edificios.py" #ubicacion del script para activar procesos en el servidor edificios


# Parámetros de PGA
MIN_PGA_CM_S2 = 2.0                    # Mínimo PGA en cm/s^2
TOP_N = 30                             # Cantidad de registros a guardar

#seccion para manejar info de configuracion y loggin
taperMaxPercent=0.05
taperType= "hann"
filterType="bandpass"
filterFreqMin=0.05
filterFreqMax=25
filterCorners=2

rutaScrips="/home/lis/waves/scripts/"
rutaRaiz ="/home/lis/waves/eventos/"
rutaImagenes ="/home/lis/waves/imagenes/"
direccionWebServer = "lis@163.178.101.121:/var/www/informes.lis.ucr.ac.cr/seiscomp/public/assets/waves"






def doSomethingWithEvent(inicio,evento):

    logging.basicConfig(
        filename=rutaRaiz+evento+'/log_evento.log',
        level=logging.INFO,  # Nivel mínimo que se registrará
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    #tiempo = inicio
    inv_path = "/home/lis/waves/inventory_Estructuras.xml"
    base = "/home/lis/waves/eventos/"
    agrupados = get_streams_for_event_from_directory(base,evento)
    proceso(agrupados,inv_path,evento,inicio)
    parametroa = rutaImagenes + evento + "/"
    logging.info("Proceso terminado")

    #proceso para copiar imagenes de ondas
    #result = subprocess.run(['scp', '-r', parametroa, direccionWebServer], capture_output=True, text=True)
    #Logging.info("IMAGENES COPIADAS")


def load_inventory_sc3(inv_path):
    # Ejemplo: usar StationXML o SC3ML convertido a Inventory de ObsPy
    #inventory = clientfdsn.get_stations(
    #    network="*",  # todas las redes
    #    station="*",  # todas las estaciones
    #    location="*",  # todos los códigos de localización
    #    channel="*",  # todos los canales
    #    level="response"  # nivel de detalle: incluye respuesta instrumental
    #)
    #return inventory
    return read_inventory(inv_path, format="STATIONXML")

def calculate_pga(tr, inventory, network, station, location, channel):
    # Se asume que 'tr' es ya un Trace de aceleración en m/s^2
    # Aplicar la respuesta instrumental (de ser necesario)
    # Si la respuesta ya está aplicada, omitir el siguiente bloque
    #net = inventory.select(network=network, station=station)
    #print(inventory)
    #if inventory is None:
        #tr.remove_response(inventory=catalogo_net, output="ACC")
        #print("PUDE REMOVER PARA %s" % tr.stats.station)


    # Calcular PGA (valor máximo absoluto)
    logging.info("Calculando PGA")
    try:
        tr.detrend("demean")
        tr.detrend("linear")
        tr.taper(max_percentage=float(taperMaxPercent), type=taperType)
        tr.filter(filterType, freqmin=float(filterFreqMin),
                   freqmax=float(filterFreqMax),
                   corners=float(filterCorners))
        pga = np.max(np.abs(tr.data))
        #print("PGA NORMAL PARA %s" % tr.stats.station)
        #print("Canal %s" % tr.stats.channel)
        #print("VALOR %s" % pga)
    except  Exception as e:
        st_umask = tr.split()
        a = []
        for tr1 in st_umask:
            print("UMASK %s" % station)
            #tr1 = tr1.remove_response(inventory, output="ACC")
            tr1.detrend("demean")
            tr1.detrend("linear")
            tr1.taper(max_percentage=float(taperMaxPercent), type=taperType)
            tr1.filter(filterType, freqmin=float(filterFreqMin),
                       freqmax=float(filterFreqMax),
                       corners=float(filterCorners))
            a.append(np.max(np.abs(tr1.data)))
            pga = max(a)
            #print("PGA SPLIT PARA %s" % tr.stats.station)
            #print("Canal %s" % tr.stats.channel)
            #print("VALOR %s" % pga)
        logging.error(f"Error en cacululoPGA {network}.{station}.{tr.stats.channel}: {e}")
    return pga #* 100.0  # Convertir a cm/s^2

def get_streams_for_event_from_directory(base_dir: str, event: str) -> dict[tuple[str, str], Stream]:
    """Lee todos los .mseed en base_dir/event, agrupa por (network, station) y fusiona trazas.
    Devuelve un diccionario {(net, sta): Stream}.
    """

    ruta_evento = os.path.join(base_dir, event)
    if not os.path.isdir(ruta_evento):
        raise FileNotFoundError(f"No existe el directorio del evento: {ruta_evento}")

    paths = sorted(glob.glob(os.path.join(ruta_evento, "*.mseed")))
    if not paths:
        logging.error("No se encontraron archivos .mseed en %s", ruta_evento)

    agrupados: dict[tuple[str, str], Stream] = {}
    for p in paths:
        try:
            st = read(p)
        except Exception as e:
            logging.error("No se pudo leer %s: %s", p, e)
        #continue
        for tr in st:
            key = (tr.stats.network, tr.stats.station)
            if key not in agrupados:
                agrupados[key] = Stream()
            agrupados[key] += tr
            # Merge por estación
            for key, st in list(agrupados.items()):
                try:
                    st.merge(method=1, fill_value="interpolate")
                    agrupados[key] = st
                except Exception as e:
                    logging.error("No se pudo fusionar stream %s: %s", key, e)

    return agrupados

def proceso(agrupados, inv_path,evento,inicio):
    #os.makedirs(OUTPUT_DIR, exist_ok=True)
    # 1. Tiempo inicial y ventanas de búsqueda

    # 2. Cargar inventario completo (ObsPy Inventory)
    inventory = load_inventory_sc3(inv_path)
    #print(inventory)

    resultados = []
    streams = []
    pgas = []
    maximos = []
    informe = 0
    #agrupados = self.get_streams_for_event_from_directory(base_dir, event)

    # 4. Recorre todos los canales de aceleración del inventario
    logging.info("Voy a recorrer streams")

    for (net, sta), st in agrupados.items():

        catalogo_net =  inventory.select(network=net, station=sta)
        #print(f"{net} -> {sta}")
        #print(f"Network? {catalogo_net.networks[0].code}")
        network = catalogo_net.networks[0].code
        mysta = catalogo_net.networks[0].stations[0]
        #print(f"Estacion? {mysta.code}")
        station = mysta.code
        site_name = mysta.site.name
        #print(f"Nombre? {site_name}")
        channel = mysta[0]
        soil = ""  # obtener tipo de suelo
        try:
            manufacturer = channel.sensor.manufacturer
            serial = channel.sensor.serial_number
        except Exception as e:
            manufacturer = "unknown"
            serial = "unknown"
            logging.error(f"error {e}")
        elevation = channel.elevation
        logging.info(f"Procesando estacion...{sta}")
        location = "**"
        channel = "HN*"
        pgasChannel = []

        # 5. Leer la traza
        try:
            #print(st)
            #st.merge(method=1, fill_value='interpolate')
            stRaw = st
            if not st or len(st) == 0:
                continue
            # tr = st[0]
            # 6. Aplicar respuesta y calcular PGA
            m = 0.0
            for tr in st:
                logging.info(f"Voy a calcular pga para {tr.stats.channel}")
                pga = calculate_pga(tr, catalogo_net, network, station, location, channel)
                if pga > m:
                    m = pga
                #  pgas.append({
                #      "pga": pga
                # })
                pgasChannel.append({str(tr.stats.channel).lower(): pga})
            maximos.append({
                "station": station,
                "maximos": m
            })
            # print(pgasChannel)
            resultados.append({
                "fecha_evento": inicio,
                "fecha_calculo": datetime.now(),
                "evento": evento,
                "tipo": 2,
                "network": network,
                "estacion": station,
                "latitud": mysta.latitude,
                "longitud": mysta.longitude,
                "site_name": site_name,
                "altitud": elevation,
                "site_manufacturer": manufacturer,
                "site_serial": serial
            })
            ultimo = resultados[-1]
            for i in pgasChannel:
                ultimo.update(i)
            streams.append({
                "evento": evento,
                "network": network,
                "station": station,
                "st": stRaw.copy(),
            })

        except Exception as e:
            logging.error(f"Error en {net}.{sta}: {e}")
            continue

        # 7. Ordenar y seleccionar los 20 registros con mayor PGA
    #maximos = sorted(maximos, key=lambda x: -x["maximos"])

    #se hacen las imagenes de todos los archivos mseed escritos
    result = subprocess.Popen(
        ["python3", rutaScrips+"plotea.py", "--imagenpng", rutaImagenes,"--ruta", OUTPUT_DIR+evento])
    logging.info("Resultado del ploteo %s" % result)

    # se escriben los archivos .LIS
    num_trabajos = -1  # Utiliza todos los núcleos disponibles
    crealis = Parallel(n_jobs=num_trabajos, prefer="threads")(  # prefer puede ser processes o threads
        delayed(archivoLis)(resultados[s], evento,inicio) for s in range(len(resultados)))
    logging.info("Resultado del archivoLIS %s" % crealis)
    #envia archivos lis a servidor central
    res1 = subprocess.Popen(['rsync', '-avz', f"/home/lis/waves/archivosLis/{evento}/",
                           "lis@163.178.101.86:/home/lis/formato_lis/registros_edificios/"])
    res2 = subprocess.Popen(['rsync', '-avz', f"/home/lis/waves/archivosLis/{evento}/",
                           "lis@163.178.109.104:/home/lis/formato_lis/registros_edificios/"])
    res3 = subprocess.Popen(['rsync', '-avz', f"/home/lis/waves/archivosLis/{evento}/",
                           "lis@163.178.174.210:/home/lis/formato_lis/registros_edificios/"])
    #envia archivos lis a repositorio stuart
    res4 = subprocess.run(['rsync', '-avz', f"/home/lis/waves/archivosLis/{evento}",
                             "lis@163.178.109.101:/home/lis/repositorio_archivo_lis/por_eventos/"])



    # mandar a guardar los pga, iterando el arreglo y preguntando por cada estacion
    #print(resultados)
    for  res in resultados:
        # chequeo si el evento ya tiene pgas guardados para cada estacion
        #print(res)
        idPga = chequeaBdPga(res["estacion"],res["evento"])
        if not idPga:
            # si la estacion no esta en la tabla pga -- hacer insert
            insertaBd(res)
        else:
            # si la estación ya esta en la tabla pga -- hacer update
            updateBd(res,idPga)


    # consultar el evento.id, traer los datos
    #datosEvento = obtener_datos_por_id(evento)
    # chequear si el evento no existe en la tabla nueva
    #fechaEvento = chequeaEvento(evento)
    # si no existe mandar a guardar en tabla de eventos nueva
    jmaEvento = chequeaJMA(evento)
    logging.info(f"Evento JMA existe: {jmaEvento['existe']}")
    if jmaEvento['existe']==0:
        logging.info("sacando JMA nuevo")
        resultJMA = subprocess.run(
            ["python3", rutaScrips+"jma_estructuras.py", "--evento",
            evento, "--ruta", OUTPUT_DIR + evento, "--tipo", "1"])
        logging.info("Resultado del JMA insertar %s" % resultJMA)
    else:
        # si llega un evento mas nuevo, lo actualiza
        #print(fechaEvento['fecha'])
        #t0 = inicio
        #print(t0)
        logging.info("Actualizando JMA")
        # se llama el jma para actualizar valores del evento
        resultJMA = subprocess.run(
            ["python3", rutaScrips+"/jma_estructuras.py", "--evento",
             evento, "--ruta", OUTPUT_DIR + evento, "--tipo", "2"])
        logging.info("Resultado del JMA actualizar %s" % resultJMA)



#funcion para calcular la distancia de epicentro e hipocentro
def epicentral_and_hypocentral_obspy(lat_epi, lon_epi, lat_sta, lon_sta, depth_km):
    # Distancia sobre el elipsoide WGS84 (metros) y azimuts (grados)
    dist_m, az, baz = gps2dist_azimuth(lat_epi, lon_epi, lat_sta, lon_sta)
    delta_km = dist_m / 1000.0
    Rh = math.sqrt(delta_km ** 2 + depth_km ** 2)
    return {
        "dist_epicentral_km": delta_km,
        "dist_hipocentral_km": Rh,
        "azimuth_deg": az,  # desde el epicentro hacia la estación
        "back_azimuth_deg": baz  # desde la estación hacia el epicentro
    }



#funcion para hacer archivos LIS
def archivoLis(resultados,evento,fecha):

    #el try elimina las estaciones que no tienen las 3 componentes
    try:

        carpeta = os.path.join(OUTPUT_DIR, evento)
        # Buscar archivos que contengan la estación en el nombre
        patron = os.path.join(carpeta, f"*_{resultados['estacion']}_*.mseed")
        archivos = glob.glob(patron)
        try:
            os.stat("/home/lis/waves/archivosLis/" + evento)
        except:
            os.mkdir("/home/lis/waves/archivosLis/" + evento)

        datos = obtener_datos_por_id(evento)

        #manda a llamar al escribe_lis
        punto_epi=(datos['latitud'],datos["longitud"])
        punto_sta =(resultados['latitud'],resultados["longitud"])
        distancias = epicentral_and_hypocentral_obspy(datos['latitud'],datos["longitud"],resultados['latitud'],resultados["longitud"],datos["profundidad"])
        epicentral_dist = geodesic(punto_epi,punto_sta).kilometers
        soil=obtener_suelo(resultados['estacion'])
        epicenter_str = ciudad_mas_cercana_descripcion(datos['latitud'],datos['longitud'])

        # se llama al escribe lis que es un proceso externo, se envian todos los parametros necesarios
        result = subprocess.run(
            ["python3", rutaScrips+"escribe_lis.py", "--mseed", archivos[0], "--out",
             f"/home/lis/waves/archivosLis/{evento}/{fecha.replace('-', '').replace(':', '').replace('T', '')[:-2]}{resultados['estacion']}.lis",
             "--station-name", resultados['site_name'],"--event-date",fecha.replace("-", "/").replace("T", " ")[:-3],
             "--event-lat",str(datos['latitud']),"--event-lon", str(datos["longitud"]),"--event-depth",str(datos["profundidad"]),"--event-mw",str(datos["magnitud"]),
             "--station-code",resultados['estacion'],"--station-lat",str(resultados['latitud']),"--station-lon",str(resultados['longitud']),
             "--pga-n00e",str(resultados['hnn']),"--pga-updo",str(resultados['hnz']),"--pga-n90e",str(resultados['hne']),"--station-elev", str(resultados['altitud']),
             "--instrument-type", str(resultados['site_manufacturer']), "--serial", str(resultados['site_serial']),"--epicentral-km",str(epicentral_dist),
             "--hypocentral-km", str(distancias['dist_hipocentral_km']),"--azimuth",str(distancias['azimuth_deg']),"--site-condition","BDG","--soil-type",str(soil),
             "--epicenter", epicenter_str, "--units","gal"
             ])
        #Logging.info("Resultado de los archivos LIS %s" % result)
    except Exception as e:
        print(
            "--Fallo creando el archivo lis para: %s---------\n" % resultados['estacion'])
        logging.error(f"Fallo creando el archivo lis para: {resultados['estacion']}, error = {e}")


#funcion para calcular la cuidad mas cercana al epicentro
#necesita un archivo de cuidades
def ciudad_mas_cercana_descripcion(
                                   lat_punto: float,
                                   lon_punto: float,
                                   lat_col: str = "latitud",
                                   lon_col: str = "longitud",
                                   name_col: str = "distrito") -> str:
    """
    Lee el CSV fijo en self.seiscomp_path + "/share/scripts/lis/ciudades.csv",
    identifica la ciudad más cercana al punto (lat_punto, lon_punto), calcula la
    distancia geodésica (Haversine) y el rumbo desde la ciudad hacia el punto,
    lo clasifica en octantes cardinales en español y retorna una descripción con
    el formato:
        "<dist> kilómetros al "<OCTANTE>" de "<NombreCiudad>"".

    Parámetros:
        lat_punto (float): Latitud del punto objetivo en grados.
        lon_punto (float): Longitud del punto objetivo en grados.
        lat_col (str): Nombre de la columna de latitud en el CSV (default: "latitud").
        lon_col (str): Nombre de la columna de longitud en el CSV (default: "longitud").
        name_col (str): Nombre de la columna con el nombre de ciudad (default: "ciudad").

    Retorna:
        str: Descripción como '<dist> kilómetros al "<OCTANTE>" de "<NombreCiudad>"'.

    Excepciones:
        FileNotFoundError: Si el CSV no existe.
        ValueError: Si faltan columnas requeridas o no hay registros válidos.
    """

    # --- Ruta fija del CSV ---
    csv_path = os.path.join(rutaScrips,"ciudades.csv")

    # --- Carga y validaciones ---
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"No se encontró el archivo CSV: {csv_path!r}")

    for col in (lat_col, lon_col, name_col):
        if col not in df.columns:
            raise ValueError(f"El CSV debe contener la columna {col!r}. Columnas encontradas: {list(df.columns)}")

    df = df.dropna(subset=[lat_col, lon_col, name_col])
    if df.empty:
        raise ValueError("El CSV no contiene filas válidas (está vacío o con valores nulos).")

    # --- Constantes y conversiones del punto ---
    R = 6371.0088  # Radio medio terrestre (km)
    phi_p = math.radians(lat_punto)
    lam_p = math.radians(lon_punto)

    # --- Búsqueda de la ciudad más cercana (Haversine) ---
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

    if ciudad_min is None:
        raise ValueError("No fue posible determinar la ciudad más cercana.")

    # --- Rumbo (bearing) desde la ciudad más cercana hacia el punto ---
    dlam_min = lam_p - lam_c_min
    y = math.sin(dlam_min) * math.cos(phi_p)
    x = (math.cos(phi_c_min) * math.sin(phi_p) -
         math.sin(phi_c_min) * math.cos(phi_p) * math.cos(dlam_min))
    theta = math.atan2(y, x)  # radianes
    brng_deg = (math.degrees(theta) + 360.0) % 360.0  # [0, 360)

    # --- Mapeo a octantes cardinales (N, N.E., E, S.E., S, S.O., O, N.O.) ---
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

    # --- Redondeo y salida ---
    dist_str = f"{min_dist:.1f}"
    return f'{dist_str} kilómetros al {dir_cardinal} de {ciudad_min}'


#funcion que devuelve el tipo de suelo de una estacion particular
#necesita un archivo con los tipos de suelo
def obtener_suelo(estacion_buscar):
    # Leer el CSV en un DataFrame
    #path = os.environ.get("SEISCOMP_ROOT")
    dir = rutaScrips+"suelo.csv"
    df = pd.read_csv(dir)

    # Convertir a diccionario: clave=estacion, valor=suelo
    dicc = dict(zip(df['estacion'], df['suelo']))

    # Retornar el valor de suelo si existe la estación
    return dicc.get(estacion_buscar, None)

#actualiza en caso de que llegue un evento igual, pero con fecha actualizada
def actualizaEvento(datos,idEvento,maxAcelera,lugarAcelera,informe):

    print(
        "Actualizando evento %s " % idEvento)
    conn = pymysql.connect(  # conexión usa parametros puestos arriba
        host=local_host,
        user= local_user,
        password= local_password,
        db= local_db,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    #arreglo para insertar valores junto con los datos por parametro
    valores = [datos["hora"],datos["latitud"],datos["longitud"],datos["magnitud"],maxAcelera,lugarAcelera,datos["profundidad"],informe,idEvento]
    try:
        with (conn.cursor() as cursor):
            # Create a new record
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
            print(valores)
            cursor.execute(sql, valores)
        # Commit changes
        conn.commit()
        logging.info(
            "--EXITO---------Evento actualizado  \n" )
        #print("Nuevos sismo registrado")
    except  Exception as e:
        logging.error(
            "--ERROR---------Se registro el siguiente error actualizando datos %s  \n" %e)
    finally:
        conn.close()


def insertaBd(datos):

    #print(datos)
    valores =[]
    try:
        valores = [datos['fecha_evento'], datos['fecha_calculo'], datos['evento'], datos['tipo'], datos['estacion'],
                   datos['latitud'],
                   datos['longitud'], datos['hne'], datos['hnn'], datos['hnz'],
                   max(datos['hne'], datos['hnn'], datos['hnz']),
                   datos['evento'] + "/" + datos['network'] + "_" + datos['estacion'] + "_" + datos[
                       'fecha_evento'].strftime('%Y%m%dT%H%M%S'), filterFreqMin, filterFreqMax]
    except Exception as err:
        logging.error(
            "--ERROR---------Fail in channels for station %s " % datos['estacion'])
        logging.error(
            "--ERROR---------Error data %s " % err)
    else:
        #print(valores)
        conn = pymysql.connect(  # conexión usa parametros puestos arriba
            host=local_host,
            user= local_user,
            password= local_password,
            db= local_db,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        try:
            with (conn.cursor() as cursor):
                # Create a new record
                sql = (
                    "INSERT INTO `Pga_estructuras` (`fecha_evento`,`fecha_calculo`,`nombre_evento`,`tipo_estacion`,`estacion`, "
                    "`latitud`, `longitud`, `hne_pga`, `hnn_pga`, `hnz_pga`,`maximo` ,`rutaWaveform`,`min_filter`,`max_filter`)"
                    " VALUES (%s ,%s ,%s ,%s ,%s ,%s ,%s, %s ,%s ,%s ,%s ,%s,%s,%s)")
                # print(values)
                cursor.execute(sql, valores)
            # Commit changes
            conn.commit()
            logging.info(
                "--EXITO---------Data save to Database  \n" )
            #print("PGA guardado en la Base de Datos")
        finally:
            conn.close()

def updateBd(datos,idPga):

    #print(datos)
    valores = []
    data_id = idPga[0]['id']
    try:
        valores = [datos['fecha_evento'], datos['fecha_calculo'],datos['evento'],datos['tipo'],datos['estacion'],datos['latitud'],
                   datos['longitud'],datos['hne'],datos['hnn'],datos['hnz'],max(datos['hne'],datos['hnn'],datos['hnz']),
                   datos['evento']+"/"+datos['network']+"_"+datos['estacion']+"_"+datos['fecha_evento'],filterFreqMin,filterFreqMax,data_id]
    except Exception as err:
        logging.error(
            "--ERROR---------Fail in channels for station %s " % datos['estacion'])
        logging.error(
            "--ERROR---------Error data %s " % err)
        #print(datos)
    else:
        #print(valores)
        conn = pymysql.connect(  # conexión usa parametros puestos arriba
            host=local_host,
            user=local_user,
            password=local_password,
            db=local_db,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        try:
            with (conn.cursor() as cursor):
                # Create a new record
                sql = (
                    "UPDATE informes.Pga_estructuras SET `fecha_evento`=%s,`fecha_calculo`=%s,`nombre_evento`=%s,`tipo_estacion`=%s,`estacion`=%s, `latitud`=%s,"
                    " `longitud`=%s, `hne_pga`=%s, `hnn_pga`=%s, `hnz_pga`=%s,`maximo`=%s ,`rutaWaveform`=%s,`min_filter`=%s,`max_filter`=%s"
                    " WHERE idpga = %s")
                #print(cursor.mogrify(sql, valores))
                cursor.execute(sql, valores)
            # Commit changes
            conn.commit()
            logging.info(
                "--EXITO---------Data updated to Database  \n" )
            #print("PGA actualizado en la Base de Datos")
        finally:
            conn.close()


#Consulta a la base para extraer los datos del evento
def obtener_datos_por_id(eventoId):
    conn = pymysql.connect(  # conexión usa parametros puestos arriba
        host=my_host,
        user=my_user,
        password=my_password,
        db=my_db,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with (conn.cursor() as cursor):
            consulta = (
                "select distinct PEvent.publicID, Origin.time_value as hora,  Origin.latitude_value as latitud,"
                "Origin.longitude_value as longitud,"
                "M.magnitude_value as magnitud, "
                "Origin.depth_value as profundidad "
                "from Origin,PublicObject as POrigin,Event,PublicObject as PEvent, Magnitude as M "
                "where POrigin.publicID=Event.preferredOriginID and  M._parent_oid = Origin._oid "
                "and Origin._oid=POrigin._oid and Event._oid=PEvent._oid "
                "and PEvent.publicID = %s Order by Origin.time_value DESC;")
            #print(consulta)
            cursor.execute(consulta, eventoId)
            resultado = cursor.fetchone()
    finally:
            conn.close()
    return resultado



def chequeaBdPga(estacion,evento):
    print(f"estacion {estacion}, evento {evento}")

    conn = pymysql.connect(  # conexión usa parametros puestos arriba
        host=local_host,
        user=local_user,
        password=local_password,
        db=local_db,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    #print(estacion)
    #print(evento)
    try:
        with (conn.cursor() as cursor):
            # Create a new record

            consulta_sql = "select  idpga as id From Pga_estructuras WHERE nombre_evento = %s AND estacion = %s"

            # Ejecutar la consulta pasando los parámetros
            cursor.execute(consulta_sql, (evento, estacion))
            #print(consulta_sql)

            # Obtener todos los resultados
            resultados = cursor.fetchall()

        # Commit changes
        conn.commit()
    finally:
        conn.close()

    return resultados

#chequea la fecha del evento a insertar, si ya existe
def chequeaEvento(evento):

    print(
        "Chequeando evento %s " %evento)
    conn = pymysql.connect(  # conexión usa parametros puestos arriba
        host=local_host,
        user=local_user,
        password=local_password,
        db=local_db,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with (conn.cursor() as cursor):
            # Create a new record
            consulta_sql = "select  fechaEvento as fecha From historico_sismos WHERE idEvento = %s "
            # Ejecutar la consulta pasando los parámetros
            cursor.execute(consulta_sql,evento)
            # Obtener todos los resultados
            resultados = cursor.fetchone()
            #print(resultados['fecha'])
        # Commit changes
        conn.commit()
    except  Exception as e:
        logging.error(
            "--ERROR---------Se registro el siguiente error %s  \n" %e)
    finally:
        conn.close()
    return resultados

#chequea la existencia de registros JMA para un evento
def chequeaJMA(evento):

    logging.info(
        "Chequeando JMA para evento %s " %evento)
    conn = pymysql.connect(  # conexión usa parametros puestos arriba
        host=local_host,
        user=local_user,
        password=local_password,
        db=local_db,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with (conn.cursor() as cursor):
            # Create a new record
            consulta_sql = "SELECT EXISTS ( SELECT 1 FROM informes.jma_estructuras WHERE idEvento = %s ) AS existe;"
            # Ejecutar la consulta pasando los parámetros
            cursor.execute(consulta_sql,evento)
            # Obtener todos los resultados
            resultados = cursor.fetchone()
            #print(resultados['fecha'])
        # Commit changes
        conn.commit()
    except  Exception as e:
        logging.error(
            "--ERROR---------Se registro el siguiente error %s  \n" %e)
    finally:
        conn.close()
    return resultados




def main():
    parser = argparse.ArgumentParser(
        description="Calcula PGA y demas datos para las estructuras"
    )
    parser.add_argument("--start", required=True,
                        help="Fecha/hora de inicio en UTC (p. ej., 2025-09-26T12:34:56).")
    parser.add_argument("--event", required=True, help="Nombre/identificador del evento.")
    args = parser.parse_args()
    doSomethingWithEvent(args.start,args.event)


if __name__ == "__main__":
    sys.exit(main())
