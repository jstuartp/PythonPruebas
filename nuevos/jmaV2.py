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


def generar_shakemap_estatico(datos, evento, ruta_salida):
    print(f"--- Generando ShakeMap estático para el evento: {evento} ---")

    # Extraer I_continuous para una interpolación fluida
    lons = np.array([d['lon'] for d in datos])
    lats = np.array([d['lat'] for d in datos])
    valores = np.array([d['I_truncated'] for d in datos])

    # Límites de Costa Rica
    min_lon, max_lon = -86.5, -82.5
    min_lat, max_lat = 8.0, 11.5

    # Malla de interpolación
    grid_lon, grid_lat = np.mgrid[min_lon:max_lon:200j, min_lat:max_lat:200j]

    # 1. Usar 'linear' en lugar de 'cubic' para evitar el sobreimpulso
    grid_z = griddata((lons, lats), valores, (grid_lon, grid_lat), method='linear')

    # 2. Rellenar los bordes (fuera de la malla convexa de estaciones) con nearest
    grid_z_nearest = griddata((lons, lats), valores, (grid_lon, grid_lat), method='nearest')
    grid_z = np.where(np.isnan(grid_z), grid_z_nearest, grid_z)

    # 3. SEGURIDAD ADICIONAL: Limitar estrictamente los valores entre 0 y 7
    # Esto asegura que ningún cálculo matemático se salga de la escala JMA
    grid_z = np.clip(grid_z, 0, 7)

    # Configurar el lienzo (sin título ni etiquetas en los bordes)
    fig, ax = plt.subplots(figsize=(8, 8))

    # 1. NUEVO COLormap: Gradiente continuo basado en tu imagen de referencia
    colores_ref = ['#ffffff', '#a0c8ff', '#0000ff', '#00ff00', '#ffff00', '#ff8c00', '#ff0000', '#800000']
    cmap_jma_smooth = mcolors.LinearSegmentedColormap.from_list('jma_smooth', colores_ref, N=256)
    norm_jma = mcolors.Normalize(vmin=0, vmax=7)

    # contourf con 100 niveles para que el degradado se vea completamente suave
    contorno = ax.contourf(
        grid_lon, grid_lat, grid_z,
        levels=np.linspace(0, 7, 100),
        cmap=cmap_jma_smooth,
        norm=norm_jma,
        extend='both',
        alpha=0.95
    )
    mapa_raster = ax.pcolormesh(
        grid_lon, grid_lat, grid_z,
        cmap=cmap_jma_smooth,
        norm=norm_jma,
        alpha=0.95,
        shading='nearest'
    )

    # 2. MÁSCARA Y BORDES: Ocultar extrapolación simulando el océano
    try:
        mapa_cr = gpd.read_file(geojsonCr)  # RECUERDA PONER TU RUTA
        geometria_cr = mapa_cr.geometry.unary_union
        lienzo_bbox = box(min_lon - 1, min_lat - 1, max_lon + 1, max_lat + 1)
        mascara_exterior = lienzo_bbox.difference(geometria_cr)

        # Tapamos el exterior de Costa Rica con color celeste (simulando océano)
        gpd.GeoSeries([mascara_exterior]).plot(ax=ax, facecolor='#d4e6f1', edgecolor='none', zorder=2)

        # Dibujamos un contorno negro grueso
        mapa_cr.plot(ax=ax, facecolor='none', edgecolor='black', linewidth=1.8, zorder=3)
    except Exception as e:
        print(f"⚠️ No se pudo aplicar la máscara: {e}")

    # 3. ESTILO DE LA CUADRÍCULA: Marcas de lat/lon hacia adentro
    ax.set_xlim(min_lon, max_lon)
    ax.set_ylim(min_lat, max_lat)
    ax.set_xticks([-86, -85, -84, -83])
    ax.set_yticks([8, 9, 10, 11])

    # Formato con el símbolo de grados
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:g}°"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:g}°"))

    # Configuración del borde grueso y marcas internas (similar al estilo GIS)
    ax.tick_params(axis='both', which='major', direction='in', top=True, right=True,
                   length=7, width=1.5, labelsize=10, zorder=5)
    for spine in ax.spines.values():
        spine.set_linewidth(1.5)
        spine.set_zorder(5)

    # 4. NUEVA LEYENDA JMA INCRUSTADA: Posicionada abajo a la izquierda
    # [x_pos, y_pos, width, height]
    cax = ax.inset_axes([0.04, 0.04, 0.35, 0.025], zorder=6)

    cbar = fig.colorbar(mapa_raster, cax=cax, orientation='horizontal', ticks=[0, 1, 2, 3, 4, 5, 6, 7])
    cbar.ax.set_title("INTENSIDAD SISMICA ESCALA JMA", fontsize=9, pad=6, loc='left', fontweight='bold')
    cbar.ax.tick_params(labelsize=9, length=4, direction='out')

    # Agregar las etiquetas manuales debajo de la barra
    cax.text(1, -2.2, "Débil", ha='center', va='top', fontsize=9, transform=cax.transData)
    cax.text(3.5, -2.2, "Moderado", ha='center', va='top', fontsize=9, transform=cax.transData)
    cax.text(6, -2.2, "Fuerte", ha='center', va='top', fontsize=9, transform=cax.transData)

    # Guardar imagen (Se aumentó ligeramente el DPI para mayor nitidez)
    archivo_png = Path(ruta_salida) / f"{evento}_shakemap.png"
    plt.savefig(archivo_png, dpi=200, bbox_inches='tight', facecolor='white')
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

    if len(datos_validos) > 3:  # Se necesitan al menos 4 puntos para interpolar bien
        generar_shakemap_estatico(datos_validos, evento, ruta)
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



