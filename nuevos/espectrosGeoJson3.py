import os
import sys
import glob
import csv
import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed

# Fundamental para evitar saturación de memoria gráfica en servidores "headless"
import matplotlib
matplotlib.use('Agg')

import obspy
import numpy as np
import pyrotd
import pymysql
from datetime import datetime
import matplotlib.pyplot as plt
from obspy import read_inventory

# ================= CONFIGURACIÓN FIJA =================
CARPETA_CURVAS = "/home/lis/seiscomp/share/scripts/lis/curvas_diseno"
CARPETA_RAIZ = "/home/lis/waves/sds/"
CARPETA_IMAGENES = "/home/lis/waves/imagenes/"

AMORTIGUAMIENTO = 0.05
PERIODOS = np.logspace(np.log10(0.01), np.log10(10), 100)
FREQS_OSCILADOR = 1 / PERIODOS
FACTOR_ESCALA_DISENO = 980
INV_PATH = "/home/lis/seiscomp/share/scripts/inventory_full_fdns.xml"
# =================================================

def cargar_datos_auxiliares():
    """ Carga suelos.csv y las curvas de diseño Z?S? en memoria. """
    print("--- Cargando datos auxiliares (Suelos y Curvas) ---")
    mapa_info = {}
    ruta_suelo = os.path.join(CARPETA_CURVAS, "suelos.csv")

    if os.path.exists(ruta_suelo):
        try:
            with open(ruta_suelo, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if len(row) >= 3:
                        estacion = row[0].strip()
                        mapa_info[estacion] = {"suelo": row[1].strip(), "zona": row[2].strip()}
        except Exception as e:
            print(f"⚠️ Error leyendo suelos.csv: {e}")

    curvas_diseno = {}
    for z in ["Z2", "Z3", "Z4"]:
        for s in ["S1", "S2", "S3", "S4"]:
            nombre = f"{z}{s}"
            ruta = os.path.join(CARPETA_CURVAS, f"{nombre}.csv")
            if os.path.exists(ruta):
                try:
                    data = np.loadtxt(ruta, delimiter=',', skiprows=1)
                    curvas_diseno[nombre] = {"T": data[:, 0], "A": data[:, 1] * FACTOR_ESCALA_DISENO}
                except:
                    pass
    return mapa_info, curvas_diseno

def obtener_coordenadas(estacion):
    coordenadas_db = {
        "SJS": {"lat": 9.9333, "lon": -84.0833},
        "LIM": {"lat": 9.9907, "lon": -83.0359},
    }
    if estacion in coordenadas_db:
        return [coordenadas_db[estacion]["lon"], coordenadas_db[estacion]["lat"]]
    return [0.0, 0.0]

# ---> MODIFICADO: Ahora recibe el `inventory` pre-cargado para evitar I/O masivo <---
def procesar_un_sismo(archivo, mapa_info, curvas_diseno, carpeta_salida, inventory):
    nombre_archivo = os.path.basename(archivo)
    nombre_archivo_sin_extension, extension = os.path.splitext(nombre_archivo)
    mapa_zonas = {"Z1": "ZI", "Z2": "ZII", "Z3": "ZIII", "Z4": "ZIV"}

    try:
        st = obspy.read(archivo)
        st.detrend("demean")
        st.detrend("linear")
        st.taper(max_percentage=0.05, type="hann")

        tr_n_list = st.select(channel="HNN")
        tr_e_list = st.select(channel="HNE")

        if not tr_n_list or not tr_e_list:
            return False, f"⚠️ Saltado (Faltan canales): {nombre_archivo}", None

        tr_y = tr_n_list[0]
        tr_x = tr_e_list[0]

        estacion_nombre = tr_x.stats.station

        # Utilizamos el inventario pasado en memoria
        catalogo_net = inventory.select(network="MF", station=estacion_nombre)
        mysta = catalogo_net.networks[0].stations[0]
        coords = [mysta.longitude, mysta.latitude]

        dt = tr_x.stats.delta
        n_pts = min(tr_x.stats.npts, tr_y.stats.npts)
        accel_x = tr_x.data[:n_pts] * 100.0
        accel_y = tr_y.data[:n_pts] * 100.0

        info = mapa_info.get(estacion_nombre, None)
        datos_curva, etiqueta = None, "Zona/Suelo Desconocido"
        if info:
            clave = f"{info['zona']}{info['suelo']}"
            zona_romana = mapa_zonas.get(info['zona'], info['zona'])
            if clave in curvas_diseno:
                datos_curva = curvas_diseno[clave]
                etiqueta = f"Diseño CSCR {zona_romana}{info['suelo']}"

        # Cálculo Espectral (Intensivo de CPU)
        resp_x = pyrotd.calc_spec_accels(dt, accel_x, FREQS_OSCILADOR, AMORTIGUAMIENTO, osc_type="psa")
        resp_y = pyrotd.calc_spec_accels(dt, accel_y, FREQS_OSCILADOR, AMORTIGUAMIENTO, osc_type="psa")
        rot_resp = pyrotd.calc_rotated_spec_accels(dt, accel_x, accel_y, FREQS_OSCILADOR, AMORTIGUAMIENTO, percentiles=[100], osc_type="psa")

        # EXTRACCIÓN DE DATOS PARA EL GEOJSON
        freqs = rot_resp.osc_freq
        sa_values = rot_resp.spec_accel
        periodos_calc = 1.0 / freqs

        idx_max = np.argmax(sa_values)
        sa_max = float(sa_values[idx_max])
        t_max = float(periodos_calc[idx_max])

        idx_orden = np.argsort(periodos_calc)
        periodos_ord = periodos_calc[idx_orden]
        sa_ord = sa_values[idx_orden]

        sa_02 = float(np.interp(0.2, periodos_ord, sa_ord))
        sa_10 = float(np.interp(1.0, periodos_ord, sa_ord))

        feature_geojson = {
            "type": "Feature",
            "properties": {
                "estacion": estacion_nombre,
                "nombre_archivo": nombre_archivo_sin_extension,
                "sa_max_cm_s2": round(sa_max, 4),
                "periodo_max_s": round(t_max, 4),
                "sa_02_cm_s2": round(sa_02, 4),
                "sa_10_cm_s2": round(sa_10, 4)
            },
            "geometry": {
                "type": "Point",
                "coordinates": coords
            }
        }

        # Generación de Gráficas
        crear_grafica(PERIODOS, resp_x, resp_y, rot_resp, estacion_nombre, nombre_archivo, carpeta_salida, datos_curva, etiqueta, "_CSCR")
        crear_grafica(PERIODOS, resp_x, resp_y, rot_resp, estacion_nombre, nombre_archivo, carpeta_salida, None, None, "")

        detalle = f"[{info['zona']}-{info['suelo']}]" if info else "[N/A]"
        return True, f"✅ {nombre_archivo} -> {estacion_nombre} {detalle}", feature_geojson

    except Exception as e:
        return False, f"❌ Error en {nombre_archivo}: {str(e)}", None

def crear_grafica(periodos, resp_x, resp_y, rot_resp, station, filename_orig, carpeta_out, datos_extra=None, etiqueta_extra=None, sufijo_archivo=""):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(periodos, resp_x.spec_accel, label='HNE', color='blue', alpha=0.4)
    ax.plot(periodos, resp_y.spec_accel, label='HNN', color='green', alpha=0.4)
    ax.plot(periodos, rot_resp.spec_accel, label='RotD100', color='red', linewidth=2)
    if datos_extra is not None:
        ax.plot(datos_extra["T"], datos_extra["A"], label=etiqueta_extra, color='black', linestyle='--', linewidth=2.5, alpha=0.8)
    elif etiqueta_extra and datos_extra is None:
        ax.plot([], [], ' ', label=f"({etiqueta_extra})")

    ax.set_title(f"Espectro de Respuesta (amortiguamiento = 5 %) - Estación: {station}")
    ax.set_xlabel("Periodo (s)")
    ax.set_ylabel("Aceleración Espectral ($cm/s^2$)")
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlim(left=0.01)
    ax.grid(True, which="major", ls="-", alpha=0.5)
    ax.grid(True, which="minor", ls=":", alpha=0.2)
    ax.legend()
    ruta_guardado = os.path.join(carpeta_out, f"{os.path.splitext(filename_orig)[0]}_RotD100_loglog{sufijo_archivo}.png")
    fig.savefig(ruta_guardado, dpi=150)

    # Liberar memoria cerrando explicitamente ambas cosas
    plt.clf()
    plt.close(fig)

# =========================================================================
# ---> NUEVO: FUNCIÓN PARA GUARDAR EN BASE DE DATOS <---
# =========================================================================
def guardar_en_bd(nombre_evento, features):
    if not features:
        return

    print(f"\n--- Guardando {len(features)} registros en la base de datos (Tabla: espectros) ---")
    try:
        # Datos de conexión extraídos de sccortawaves_PRUEBAS
        conexion = pymysql.connect(
            host='163.178.170.245',
            user='informes',
            password='B8EYvZRTpTUDquc3',
            database='informes'
        )
        cursor = conexion.cursor()
        # Limpiar registros previos de este evento (si es la primera vez, borrará 0 filas sin dar error)
        cursor.execute("DELETE FROM espectros WHERE nombre_evento = %s", (nombre_evento,))

        # Query de inserción adaptada a la entidad Espectros
        sql = """
              INSERT INTO espectros
              (nombre_evento, estacion, sa_max, periodo_max, sa_02, sa_10, latitud, longitud, fecha_evento, nombre_archivo) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) \
              """
        momento_calculo = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        valores = []
        for feature in features:
            props = feature['properties']
            coords = feature['geometry']['coordinates']  # Extraer el arreglo de coordenadas

            # GeoJSON estándar: [longitud, latitud]
            longitud = coords[0]
            latitud = coords[1]

            valores.append((
                nombre_evento,
                props['estacion'],
                props['sa_max_cm_s2'],
                props['periodo_max_s'],
                props['sa_02_cm_s2'],
                props['sa_10_cm_s2'],
                latitud,  # Agregado a la tupla
                longitud,
                momento_calculo,
                props['nombre_archivo']
            ))

        cursor.executemany(sql, valores)
        conexion.commit()
        print("✅ Datos guardados correctamente en la base de datos.")

    except Exception as e:
        print(f"❌ Error al guardar en la base de datos: {e}")
    finally:
        if 'conexion' in locals() and conexion.open:
            cursor.close()
            conexion.close()

def main():
    if len(sys.argv) < 2:
        print("\n❌ Error: Debes especificar el nombre del evento (carpeta).")
        sys.exit(1)

    nombreEvento = sys.argv[1]
    carpeta_entrada = CARPETA_RAIZ + nombreEvento

    if not os.path.isdir(carpeta_entrada):
        print(f"\n❌ Error: La carpeta '{carpeta_entrada}' no existe.\n")
        sys.exit(1)

    carpeta_salida = os.path.join(CARPETA_IMAGENES + nombreEvento, "espectros_acc")
    os.makedirs(carpeta_salida, exist_ok=True)

    mapa_info, curvas_diseno = cargar_datos_auxiliares()
    archivos = glob.glob(os.path.join(carpeta_entrada, "*.mseed"))
    total = len(archivos)

    if total == 0:
        print(f"⚠️ No se encontraron archivos .mseed")
        sys.exit(0)

    # ---> OPTIMIZACIÓN: Cargar el XML del catalogo una sola vez en el hilo principal <---
    print("--- Cargando catálogo de estaciones STATIONXML (una sola vez) ---")
    inventory = read_inventory(INV_PATH, format="STATIONXML")

    # ---> CONFIGURACIÓN DE PARALELISMO <---
    # Dejamos la mitad de los procesadores libres para no saturar el servidor
    cores_totales = multiprocessing.cpu_count()
    max_workers = max(1, cores_totales // 2)
    print(f"⚡ Iniciando cálculo paralelo usando {max_workers} de {cores_totales} hilos disponibles...")

    features_geojson = []
    resultados = []

    # Ejecutor de procesos en piscina (Pool)
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Asignar todas las tareas al pool
        futuros = {
            executor.submit(procesar_un_sismo, archivo, mapa_info, curvas_diseno, carpeta_salida, inventory): archivo
            for archivo in archivos
        }

        # Procesar los resultados a medida que van terminando
        completados = 0
        for futuro in as_completed(futuros):
            completados += 1
            try:
                exito, mensaje, feature = futuro.result()
                resultados.append(mensaje)
                if exito and feature is not None:
                    features_geojson.append(feature)

                # Imprimir un log por pantalla que no rompa la consola
                if exito:
                    print(f"[{completados}/{total}] Completado: {mensaje.split('->')[0].replace('✅ ', '').strip()}")
                else:
                    print(f"[{completados}/{total}] {mensaje}")

            except Exception as e:
                print(f"[{completados}/{total}] ❌ Error catastrófico en un hilo: {e}")

    # Guardar el archivo GeoJSON consolidado
    if features_geojson:
        archivo_geojson = os.path.join(carpeta_salida, "datos_espectrales.geojson")
        coleccion_geojson = {
            "type": "FeatureCollection",
            "features": features_geojson
        }
        with open(archivo_geojson, "w", encoding="utf-8") as f:
            json.dump(coleccion_geojson, f, indent=4)
        print(f"\n🗺️ GeoJSON guardado con {len(features_geojson)} estaciones en:\n   {archivo_geojson}")

        # ---> NUEVO: LLAMADA A LA BASE DE DATOS <---
        guardar_en_bd(nombreEvento, features_geojson)

    print("\n--- Resumen de Advertencias/Errores ---")
    errores = [res for res in resultados if "✅" not in res]
    if errores:
        for res in errores:
            print(res)
    else:
        print("Todo procesado sin errores.")

if __name__ == "__main__":
    main()
