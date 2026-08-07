import numpy as np
import sys
from joblib import Parallel, delayed
from pathlib import Path
from obspy import read, read_inventory
from scipy.fft import fft, ifft, fftfreq
import argparse
import pymysql
import matplotlib
matplotlib.use('Agg') # Para servidores sin interfaz gráfica
import matplotlib.pyplot as plt
from scipy.interpolate import griddata
from shapely.geometry import box
from matplotlib.colors import ListedColormap, BoundaryNorm
import geopandas as gpd
import matplotlib.colors as mcolors
from scipy.spatial.distance import cdist
import shapely


#CONSTANTES BASES DE DATOS LOCAL
local_host = '163.178.170.245'
local_user = 'informes'
local_password = 'B8EYvZRTpTUDquc3'
local_db = 'informes'
#local_host = 'localhost'
#local_user = 'root'
#local_password = 'jspz2383'
#local_db = 'sismos_lis'

inv_path = "/home/lis/seiscomp/share/scripts/inventory_full_fdns.xml"
inventory = read_inventory(inv_path, format="STATIONXML")
geojsonCr = "/home/lis/seiscomp/share/scripts/lis/CostaRicaS.json"
ruta_salida="/home/lis/waves/imagenes"


def generar_shakemap_estatico(datos, evento, ruta_salida):
    print(f"--- Generando ShakeMap estático para el evento: {evento} ---")

    # Extraer variables para interpolación fluida
    lons = np.array([d['lon'] for d in datos])
    lats = np.array([d['lat'] for d in datos])
    valores = np.array([d['I_truncated'] for d in datos])

    # Límites de Costa Rica (ajustados)
    min_lon, max_lon = -86.1, -82.5
    min_lat, max_lat = 8.0, 11.3

    # Malla de interpolación
    grid_lon, grid_lat = np.mgrid[min_lon:max_lon:200j, min_lat:max_lat:200j]

    # =====================================================================
    # IDW
    # =====================================================================
    flat_glon = grid_lon.flatten()
    flat_glat = grid_lat.flatten()

    puntos_malla = np.column_stack((flat_glon, flat_glat))
    puntos_estaciones = np.column_stack((lons, lats))

    # Calcular la matriz de distancias
    distancias = cdist(puntos_malla, puntos_estaciones)
    dist_cero = distancias < 0.001

    factor_suavizado = 0.7  # Ajusta este valor (en grados). Un valor mayor = manchas más amplias.
    with np.errstate(divide='ignore'):
        pesos = 1.0 / ((distancias + factor_suavizado) ** 15)

    #with np.errstate(divide='ignore'):
    #    pesos = 1.0 / (distancias ** 20)

    numerador = np.sum(pesos * valores, axis=1)
    denominador = np.sum(pesos, axis=1)
    grid_z_flat = numerador / denominador

    for i in range(len(flat_glon)):
        idx_coincidencia = np.where(dist_cero[i])[0]
        if len(idx_coincidencia) > 0:
            grid_z_flat[i] = valores[idx_coincidencia[0]]

    # NUEVO: Recortar los datos a la forma de Costa Rica para que el océano sea transparente
    try:
        mapa_cr = gpd.read_file(geojsonCr)
        geometria_cr = mapa_cr.geometry.unary_union

        # Convertimos la malla a puntos espaciales y verificamos si están dentro del país
        puntos_malla_geo = gpd.GeoSeries(gpd.points_from_xy(flat_glon, flat_glat))
        puntos_dentro = puntos_malla_geo.within(geometria_cr)

        # Asignamos NaN (Transparente) a todo lo que esté en el océano/afuera
        grid_z_flat[~puntos_dentro] = np.nan
    except Exception as e:
        print(f"⚠️ Error al enmascarar con GeoJSON: {e}")

    # Reconstruir la forma bidimensional
    grid_z = grid_z_flat.reshape(grid_lon.shape)
    grid_z = np.clip(grid_z, 0, 7)
    # =====================================================================

    # Configurar el lienzo
    fig, ax = plt.subplots(figsize=(8, 8))

    colores_ref = ['#ffffff', '#d2d2d2', '#0032ff', '#00faff', '#0bc200', '#ffff00', '#f77a00', '#f40001','#a90000','#640064']
    cmap_jma_smooth = mcolors.LinearSegmentedColormap.from_list('jma_smooth', colores_ref, N=256)
    norm_jma = mcolors.Normalize(vmin=0, vmax=10)

    # NUEVO: alpha=0.55 para mayor transparencia sobre el mapa Leaflet
   # contorno = ax.contourf(
   #     grid_lon, grid_lat, grid_z,
   #     levels=np.linspace(0, 7, 100),
    #    cmap=cmap_jma_smooth,
     #   norm=norm_jma,
      #  extend='both',
      #  alpha=0.55
    #)

    mapa_raster = ax.pcolormesh(
        grid_lon, grid_lat, grid_z,
        cmap=cmap_jma_smooth,
        norm=norm_jma,
        alpha=0.55,
        shading='gouraud'
    )

    # NUEVO: Solo dibujamos la frontera negra de Costa Rica, sin la máscara celeste exterior
    try:
        mapa_cr.plot(ax=ax, facecolor='none', edgecolor='black', linewidth=0, zorder=3)
    except Exception as e:
        pass

    # ESTILO DE LA CUADRÍCULA
    ax.set_xlim(min_lon, max_lon)
    ax.set_ylim(min_lat, max_lat)

    # NUEVO: Apagamos los ejes, números y bordes para que sea un overlay limpio
    ax.axis('off')

    # LEYENDA JMA INCRUSTADA
    #cax = ax.inset_axes([0.04, 0.04, 0.35, 0.025], zorder=6)
    #cbar = fig.colorbar(mapa_raster, cax=cax, orientation='horizontal', ticks=[0, 1, 2, 3, 4, 5, 6, 7])

    # Agregamos un fondo blanco semi-transparente a la leyenda para que sea legible sobre el mapa base
    #cax.set_facecolor((1.0, 1.0, 1.0, 0.7))

    #cbar.ax.set_title("INTENSIDAD SISMICA ESCALA JMA", fontsize=9, pad=6, loc='left', fontweight='bold')
    #cbar.ax.tick_params(labelsize=9, length=4, direction='out')

    #cax.text(1, -2.2, "Débil", ha='center', va='top', fontsize=9, transform=cax.transData)
    #cax.text(3.5, -2.2, "Moderado", ha='center', va='top', fontsize=9, transform=cax.transData)
    #cax.text(6, -2.2, "Fuerte", ha='center', va='top', fontsize=9, transform=cax.transData)

    # NUEVO: Guardar imagen con transparent=True y sin márgenes en blanco (pad_inches=0)
    archivo_png = Path(ruta_salida) / f"{evento}_interpolado.png"
    plt.savefig(archivo_png, dpi=200, bbox_inches='tight', pad_inches=0, transparent=True)
    plt.close()

    print(f"✅ Mapa estático guardado en: {archivo_png}")

def jma_filters(frequencies):
    f = frequencies
    x = f / 10.0
    with np.errstate(divide='ignore', invalid='ignore'):
        F1 = np.sqrt(1.0 / np.where(f > 0, f, np.inf))
    F2 = (1 + 0.694 * x**2 + 0.241 * x**4 + 0.0557 * x**6
          + 0.009664 * x**8 + 0.00134 * x**10 + 0.000155 * x**12) ** -0.5
    F3 = np.sqrt(1 - np.exp(-(f / 0.5)**3))
    return F1 * F2 * F3


def compute_jma_intensity(acc_ns, acc_ew, acc_up, fs=200.0):
    n = len(acc_ns)
    freqs = fftfreq(n, d=1/fs)

    def filter_component(acc):
        A_f = fft(acc)
        filt = jma_filters(np.abs(freqs))
        return np.real(ifft(A_f * filt))

    ns_filt = filter_component(acc_ns)
    ew_filt = filter_component(acc_ew)
    up_filt = filter_component(acc_up)

    a_comp = np.sqrt(ns_filt**2 + ew_filt**2 + up_filt**2)

    def find_a0():
        lo, hi = 0.0, np.max(a_comp)
        target_samples = int(0.3 * fs)
        for _ in range(50):
            mid = (lo + hi) / 2
            count = np.sum(a_comp >= mid)
            if count > target_samples:
                lo = mid
            else:
                hi = mid
        return lo

    a0 = find_a0()

    if a0 <= 0:
        return {
            "a0_gal": a0,
            "I_continuous": 0.0,
            "I_truncated": 0.0,
            "JMA_intensity": 0
        }

    I = 2 * np.log10(a0) + 0.94
    I_rounded = round(I, 3)
    I_truncated = np.floor(I_rounded * 100) / 100.0

    def classify_intensity(I_val):
        if I_val < 0.5:
            return 0
        elif I_val < 1.5:
            return 1
        elif I_val < 2.5:
            return 2
        elif I_val < 3.5:
            return 3
        elif I_val < 4.5:
            return 4
        elif I_val < 5.0:
            return "5−"
        elif I_val < 5.5:
            return "5+"
        elif I_val < 6.0:
            return "6−"
        elif I_val < 6.5:
            return "6+"
        else:
            return 7

    jma_level = classify_intensity(I_truncated)

    return {
        "a0_gal": round(a0, 3),
        "I_continuous": I_rounded,
        "I_truncated": I_truncated,
        "JMA_intensity": jma_level
    }


def load_components_from_miniseed(file_path,evento,tipo):
    st = read(file_path)
    station =""
    network = ""
    sta_lat =0
    sta_long = 0

    try:
        val = len(st) < 3
        # Try to match components by channel code endings
        components = {'N': None, 'E': None, 'Z': None}
        for tr in st:
            channel = tr.stats.channel.upper()
            station = tr.stats.station
            network = tr.stats.network
            if channel.endswith("N") or channel.endswith("1"):
                components['N'] = tr
            elif channel.endswith("E") or channel.endswith("2"):
                components['E'] = tr
            elif channel.endswith("Z"):
                components['Z'] = tr


        sta = inventory.select(network=network, station=station)[0]
        my_sta=sta[0]


        if not all(components.values()):
            raise ValueError("Could not find all 3 components (N, E, Z) in MiniSEED file.")

        # Extract data and ensure same length
        acc_ns = components['N'].data.astype(np.float64) * 100
        acc_ew = components['E'].data.astype(np.float64) * 100
        acc_up = components['Z'].data.astype(np.float64) * 100
        fs = components['N'].stats.sampling_rate

        min_len = min(len(acc_ns), len(acc_ew), len(acc_up))
        acc_ns = acc_ns[:min_len]
        acc_ew = acc_ew[:min_len]
        acc_up = acc_up[:min_len]

        data = compute_jma_intensity(acc_ns, acc_ew, acc_up, fs)
        mapData =data
        mapData['lon'] = my_sta.longitude
        mapData['lat'] = my_sta.latitude
        # guardar en base de datos "data" con el id de evento
        print(station)
        if(tipo == 1):
            insertaBd(data, evento, station,my_sta.latitude,my_sta.longitude)
            print(f"termine insertar {station}")
        if(tipo == 2):
            actualizaBd(data, evento, station,my_sta.latitude,my_sta.longitude)
            print(f"termine actualizar {station}")
        return mapData
    except Exception as e:
        print(f"No existen las 3 componentes en el archivo {station}")




def insertaBd(datos,evento,station,lat,lon):
        #print(datos)
        valores =[]
        try:
            valores = [evento,station,datos['a0_gal'], datos['I_continuous'], datos['I_truncated'], datos['JMA_intensity'],
                       lat,lon]
        except Exception as err:
            print(
                "--ERROR---------Fail in channels ")
            print(
                "--ERROR---------Error data %s " % station)
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
                        "INSERT INTO `jma` (`idEvento`,`estacion`,`threshold_a0`,`continuos`,`truncated`, "
                        "`jma`,`lat`,`lon`)"
                        " VALUES (%s ,%s ,%s ,%s ,%s ,%s,%s,%s )")
                    # print(values)
                    cursor.execute(sql, valores)
                # Commit changes
                conn.commit()
                print(
                    "--EXITO---------Data save to Database  \n" )
                #print("PGA guardado en la Base de Datos")
            finally:
                conn.close()


def actualizaBd(datos, evento, station,lat,lon):
    # print(datos)
    valores = []
    try:
        valores = [ datos['a0_gal'], datos['I_continuous'], datos['I_truncated'], datos['JMA_intensity'],
                   lat,lon,evento, station]
    except Exception as err:
        print(
            "--ERROR---------Fail in channels ")
        print(
            "--ERROR---------Error data %s " % station)
    else:
        # print(valores)
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
                    "Update `jma` SET `threshold_a0`=%s,`continuos`=%s,`truncated`=%s, "
                    "`jma`=%s, `lat`=%s, `lon`=%s"
                    " Where idEvento =%s and estacion = %s ")
                # print(values)
                cursor.execute(sql, valores)
            # Commit changes
            conn.commit()
            print(
                "--EXITO---------Data updated to Database  \n")
            # print("PGA guardado en la Base de Datos")
        finally:
            conn.close()





def calcula_jma(evento,ruta,tipo):
    directorio = Path(ruta)
    #activa el calculo del JMA
    archivos_mseed = list(directorio.glob("*.mseed"))
    #print(archivos_mseed)
    num_trabajos = -1
    calculaJma = Parallel(n_jobs=num_trabajos, prefer="threads")(  # prefer puede ser processes o threads
        delayed(load_components_from_miniseed)(archivo,evento,tipo) for archivo in archivos_mseed)
    #print(calculaJma)
    datos_validos = [res for res in calculaJma if res is not None]
    salida = ruta_salida+"/"+evento+"/"

    if len(datos_validos) > 3:  # Se necesitan al menos 4 puntos para interpolar bien
        generar_shakemap_estatico(datos_validos, evento, salida)
    else:
        print("⚠️ No hay suficientes estaciones válidas para generar el ShakeMap.")

def main():
    parser = argparse.ArgumentParser(
        description="Compute JMA Intensity from a MiniSEED file containing all 3 components.")
    #parser.add_argument("mseed_file", help="MiniSEED file with NS, EW, and UP acceleration (in gals)")
    parser.add_argument("--evento",type=str, required=True, help="Nombre del evento")
    parser.add_argument("--ruta", type=str, required=True, help="ruta de archivos")
    parser.add_argument("--tipo", type=int, required=True, help="1 inserta 2 actualiza")
    args = parser.parse_args()
    calcula_jma(args.evento,args.ruta,args.tipo)

    #acc_ns, acc_ew, acc_up, fs = load_components_from_miniseed(args.mseed_file)

    #result = compute_jma_intensity(acc_ns, acc_ew, acc_up, fs)
    #print("\n📊 JMA Instrumental Seismic Intensity Results")
    #print("============================================")
    #print(f"Threshold a₀ (gal):       {result['a0_gal']}")
    #print(f"Continuous intensity (I): {result['I_continuous']}")
    #print(f"Truncated intensity (I):  {result['I_truncated']}")
    #print(f"JMA Intensity Level:      {result['JMA_intensity']}")

if __name__ == "__main__":
    sys.exit(main())



