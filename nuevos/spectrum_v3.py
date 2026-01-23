import os
import sys
import glob
import csv
import obspy
import numpy as np
import pyrotd
import matplotlib.pyplot as plt
from joblib import Parallel, delayed

# ================= CONFIGURACIÓN FIJA =================
# Estas variables siguen siendo relativas a donde corre el script,
# o puedes poner rutas absolutas si prefieres.
CARPETA_CURVAS = "./curvas_diseno"

# Parámetros Cálculo
AMORTIGUAMIENTO = 0.05
PERIODOS = np.logspace(np.log10(0.01), np.log10(10), 100)
FREQS_OSCILADOR = 1 / PERIODOS

# Factor de escala (ej. 1.0 si ya está en cm/s2)
FACTOR_ESCALA_DISENO = 1.0


# =================================================

def cargar_datos_auxiliares():
    """
    Carga suelos.csv y las curvas de diseño Z?S? en memoria.
    """
    print("--- Cargando datos auxiliares (Suelos y Curvas) ---")

    # 1. Cargar Mapeo (Estacion -> Zona, Suelo)
    mapa_info = {}
    ruta_suelo = os.path.join(CARPETA_CURVAS, "suelos.csv")

    if not os.path.exists(ruta_suelo):
        print(f"⚠️ ADVERTENCIA: No se encontró el archivo de suelos en: {ruta_suelo}")
        print("   Las gráficas se generarán sin la curva de diseño.")
    else:
        try:
            with open(ruta_suelo, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)  # Saltar cabecera
                for row in reader:
                    if len(row) >= 3:
                        estacion = row[0].strip()
                        suelo = row[1].strip()
                        zona = row[2].strip()
                        mapa_info[estacion] = {"suelo": suelo, "zona": zona}
            print(f"✅ Mapa de estaciones cargado: {len(mapa_info)} registros.")
        except Exception as e:
            print(f"⚠️ Error leyendo suelos.csv: {e}")

    # 2. Cargar Curvas de Diseño
    curvas_diseno = {}
    zonas = ["Z2", "Z3", "Z4"]
    suelos = ["S1", "S2", "S3", "S4"]

    for z in zonas:
        for s in suelos:
            nombre = f"{z}{s}"
            ruta = os.path.join(CARPETA_CURVAS, f"{nombre}.csv")
            if os.path.exists(ruta):
                try:
                    data = np.loadtxt(ruta, delimiter=',', skiprows=1)
                    # Aplicar factor de escala
                    curvas_diseno[nombre] = {
                        "T": data[:, 0],
                        "A": data[:, 1] * 100.0 * FACTOR_ESCALA_DISENO
                    }
                except Exception as e:
                    print(f"⚠️ Error en {nombre}.csv: {e}")
            # Si no existe, simplemente no se carga (silencioso)

    print(f"✅ Total curvas de diseño cargadas: {len(curvas_diseno)}")
    return mapa_info, curvas_diseno


def procesar_un_sismo(archivo, mapa_info, curvas_diseno, carpeta_salida):
    """
    Procesa un archivo mseed. Recibe carpeta_salida como argumento.
    """
    nombre_archivo = os.path.basename(archivo)

    try:
        st = obspy.read(archivo)

        # Pre-procesamiento
        st.detrend("demean")
        st.detrend("linear")
        st.taper(max_percentage=0.05, type="hann")

        # Canales
        tr_n_list = st.select(channel="HNN")
        tr_e_list = st.select(channel="HNE")

        if not tr_n_list or not tr_e_list:
            return f"⚠️ Saltado (Faltan canales): {nombre_archivo}"

        tr_y = tr_n_list[0]
        tr_x = tr_e_list[0]

        estacion_nombre = tr_x.stats.station
        dt = tr_x.stats.delta

        # Recorte y Conversión
        n_pts = min(tr_x.stats.npts, tr_y.stats.npts)
        accel_x = tr_x.data[:n_pts] * 100.0
        accel_y = tr_y.data[:n_pts] * 100.0

        # Selección de Curva de Diseño
        datos_curva = None
        etiqueta = None
        info = mapa_info.get(estacion_nombre, None)

        if info:
            clave = f"{info['zona']}{info['suelo']}"  # Ej: Z2S2
            if clave in curvas_diseno:
                datos_curva = curvas_diseno[clave]
                etiqueta = f"Diseño {clave}"
            else:
                etiqueta = f"Falta {clave}"
        else:
            etiqueta = "Zona/Suelo Desconocido"

        # Cálculo Espectral
        resp_x = pyrotd.calc_spec_accels(dt, accel_x, FREQS_OSCILADOR, AMORTIGUAMIENTO)
        resp_y = pyrotd.calc_spec_accels(dt, accel_y, FREQS_OSCILADOR, AMORTIGUAMIENTO)
        rot_resp = pyrotd.calc_rotated_spec_accels(
            dt, accel_x, accel_y, FREQS_OSCILADOR, AMORTIGUAMIENTO, percentiles=[100]
        )

        # Graficar (Pasando la ruta de salida)
        crear_grafica(
            PERIODOS, resp_x, resp_y, rot_resp,
            estacion_nombre, nombre_archivo,
            carpeta_salida,
            datos_extra=datos_curva, etiqueta_extra=etiqueta
        )

        detalle = f"[{info['zona']}-{info['suelo']}]" if info else "[N/A]"
        return f"✅ {nombre_archivo} -> {estacion_nombre} {detalle}"

    except Exception as e:
        return f"❌ Error en {nombre_archivo}: {str(e)}"


def crear_grafica(periodos, resp_x, resp_y, rot_resp, station, filename_orig, carpeta_out, datos_extra=None,
                  etiqueta_extra=None):
    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(periodos, resp_x.spec_accel, label='HNE', linestyle=':', color='blue', alpha=0.4)
    ax.plot(periodos, resp_y.spec_accel, label='HNN', linestyle=':', color='green', alpha=0.4)
    ax.plot(periodos, rot_resp.spec_accel, label='RotD100', color='red', linewidth=2)

    if datos_extra is not None:
        ax.plot(datos_extra["T"], datos_extra["A"], label=etiqueta_extra, color='black', linestyle='--', linewidth=2.5,
                alpha=0.8)
    elif etiqueta_extra:
        ax.plot([], [], ' ', label=f"({etiqueta_extra})")

    ax.set_title(f"Espectro de Respuesta - Estación: {station}")
    ax.set_xlabel("Periodo (s)")
    ax.set_ylabel("Aceleración Espectral ($cm/s^2$)")
    ax.set_xscale('log')
    ax.set_xlim(left=0.01)
    ax.grid(True, which="both", ls="-", alpha=0.3)
    ax.legend()

    # Guardar en la carpeta dinámica
    nombre_limpio = os.path.splitext(filename_orig)[0]
    ruta_guardado = os.path.join(carpeta_out, f"{station}_{nombre_limpio}_RotD100.png")

    fig.savefig(ruta_guardado, dpi=150)
    plt.close(fig)


def main():
    # 1. Validación de Argumentos
    if len(sys.argv) < 2:
        print("\n❌ Error: Debes especificar la carpeta de los archivos mseed.")
        print("   Uso: python script.py <ruta_de_la_carpeta>")
        print("   Ejemplo: python script.py ./sismos_2024\n")
        sys.exit(1)

    carpeta_entrada = sys.argv[1]

    if not os.path.isdir(carpeta_entrada):
        print(f"\n❌ Error: La carpeta '{carpeta_entrada}' no existe.\n")
        sys.exit(1)

    # 2. Configurar Carpeta de Salida (Dentro de la de entrada)
    carpeta_salida = os.path.join(carpeta_entrada, "espectros_calculados")
    if not os.path.exists(carpeta_salida):
        os.makedirs(carpeta_salida)
        print(f"📂 Carpeta creada: {carpeta_salida}")
    else:
        print(f"📂 Usando carpeta existente: {carpeta_salida}")

    # 3. Cargar Datos y Archivos
    mapa_info, curvas_diseno = cargar_datos_auxiliares()

    archivos = glob.glob(os.path.join(carpeta_entrada, "*.mseed"))
    total = len(archivos)

    if total == 0:
        print(f"⚠️ No se encontraron archivos .mseed en {carpeta_entrada}")
        sys.exit(0)

    print(f"\n--- Iniciando procesamiento de {total} archivos en paralelo ---")

    # 4. Ejecución Paralela
    # Pasamos 'carpeta_salida' a cada hilo
    resultados = Parallel(n_jobs=-1, verbose=5)(
        delayed(procesar_un_sismo)(archivo, mapa_info, curvas_diseno, carpeta_salida)
        for archivo in archivos
    )

    print("\n--- Resumen ---")
    for res in resultados:
        if "✅" not in res:
            print(res)

    print(f"\n✅ Proceso finalizado. Gráficas guardadas en:\n   {carpeta_salida}")


if __name__ == "__main__":
    main()