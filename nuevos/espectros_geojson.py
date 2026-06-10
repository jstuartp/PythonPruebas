import os
import sys
import glob
import csv
import json # <--- NUEVO: Para exportar el GeoJSON
import obspy
import numpy as np
import pyrotd
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

# ---> NUEVO: Función para simular/cargar coordenadas <---
def obtener_coordenadas(estacion):
    """
    Sustituye este diccionario por una lectura a tu base de datos
    o a un archivo CSV (ej. coordenadas.csv).
    """
    coordenadas_db = {
        "SJS": {"lat": 9.9333, "lon": -84.0833},
        "LIM": {"lat": 9.9907, "lon": -83.0359},
        # Agrega las demás...
    }
    #leo el archivo de catalogo



    # Retorna [longitud, latitud] como requiere el estándar GeoJSON
    if estacion in coordenadas_db:
        return [coordenadas_db[estacion]["lon"], coordenadas_db[estacion]["lat"]]
    return [0.0, 0.0] # Coordenada por defecto si no se encuentra


def procesar_un_sismo(archivo, mapa_info, curvas_diseno, carpeta_salida):
    nombre_archivo = os.path.basename(archivo)
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
        #leo el archivo del catalogo
        inventory = read_inventory(INV_PATH, format="STATIONXML")
        #leo el nombre de la estacion
        estacion_nombre = tr_x.stats.station
        #selecciono la estacion del catalogo
        catalogo_net = inventory.select(network="MF", station=estacion_nombre)
        #asigno los datos a la estacion
        mysta = catalogo_net.networks[0].stations[0]
        #extraigo las coordenadas
        coords= [mysta.longitude, mysta.latitude]
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

        # Cálculo Espectral
        resp_x = pyrotd.calc_spec_accels(dt, accel_x, FREQS_OSCILADOR, AMORTIGUAMIENTO, osc_type="psa")
        resp_y = pyrotd.calc_spec_accels(dt, accel_y, FREQS_OSCILADOR, AMORTIGUAMIENTO, osc_type="psa")
        rot_resp = pyrotd.calc_rotated_spec_accels(dt, accel_x, accel_y, FREQS_OSCILADOR, AMORTIGUAMIENTO, percentiles=[100], osc_type="psa")

        # =========================================================================
        # ---> NUEVO: EXTRACCIÓN DE DATOS PARA EL GEOJSON <---
        # =========================================================================
        # Convertimos frecuencias a periodos
        freqs = rot_resp.osc_freq
        sa_values = rot_resp.spec_accel
        periodos_calc = 1.0 / freqs

        # 1. Obtener SA Máxima y su Periodo correspondiente
        idx_max = np.argmax(sa_values)
        sa_max = float(sa_values[idx_max])
        t_max = float(periodos_calc[idx_max])

        # 2. Obtener SA para 0.2s y 1.0s mediante interpolación lineal
        # Para usar np.interp, el eje X (periodos) debe estar estrictamente ordenado de menor a mayor
        idx_orden = np.argsort(periodos_calc)
        periodos_ord = periodos_calc[idx_orden]
        sa_ord = sa_values[idx_orden]

        sa_02 = float(np.interp(0.2, periodos_ord, sa_ord))
        sa_10 = float(np.interp(1.0, periodos_ord, sa_ord))

        # 3. Construir la propiedad (feature) para esta estación
        #coords = obtener_coordenadas(estacion_nombre)
        feature_geojson = {
            "type": "Feature",
            "properties": {
                "estacion": estacion_nombre,
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

        # Generación de Gráficas...
        crear_grafica(PERIODOS, resp_x, resp_y, rot_resp, estacion_nombre, nombre_archivo, carpeta_salida, datos_curva, etiqueta, "_CSCR")
        crear_grafica(PERIODOS, resp_x, resp_y, rot_resp, estacion_nombre, nombre_archivo, carpeta_salida, None, None, "")

        detalle = f"[{info['zona']}-{info['suelo']}]" if info else "[N/A]"
        return True, f"✅ {nombre_archivo} -> {estacion_nombre} {detalle}", feature_geojson

    except Exception as e:
        return False, f"❌ Error en {nombre_archivo}: {str(e)}", None


def crear_grafica(periodos, resp_x, resp_y, rot_resp, station, filename_orig, carpeta_out, datos_extra=None, etiqueta_extra=None, sufijo_archivo=""):
    # (El código de la gráfica permanece exactamente igual)
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
    plt.close(fig)


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

    # ---> NUEVO: Lista para almacenar las "features" del GeoJSON <---
    features_geojson = []
    resultados = []

    for i, archivo in enumerate(archivos, 1):
        print(f"[{i}/{total}] Procesando: {os.path.basename(archivo)} ... ", end="", flush=True)

        exito, mensaje, feature = procesar_un_sismo(archivo, mapa_info, curvas_diseno, carpeta_salida)

        resultados.append(mensaje)
        if exito and feature is not None:
            features_geojson.append(feature)

        print("Hecho.")

    # ---> NUEVO: Guardar el archivo GeoJSON consolidado <---
    if features_geojson:
        archivo_geojson = os.path.join(carpeta_salida, "datos_espectrales.geojson")
        coleccion_geojson = {
            "type": "FeatureCollection",
            "features": features_geojson
        }
        with open(archivo_geojson, "w", encoding="utf-8") as f:
            json.dump(coleccion_geojson, f, indent=4)
        print(f"\n🗺️ GeoJSON guardado con {len(features_geojson)} estaciones en:\n   {archivo_geojson}")

    print("\n--- Resumen ---")
    for res in resultados:
        if "✅" not in res:
            print(res)

if __name__ == "__main__":
    main()
