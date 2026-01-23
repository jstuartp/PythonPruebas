import os
import glob
import csv
import obspy
import numpy as np
import pyrotd
import matplotlib.pyplot as plt
from joblib import Parallel, delayed

# ================= CONFIGURACIÓN =================
CARPETA_MSEED = "./UCR_lis2026biqs"
CARPETA_SALIDA = "./espectros_out_1"
CARPETA_CURVAS = "./curvas_diseno"  # Carpeta donde están S1.csv, S2.csv... y suelo.csv

# Parámetros Cálculo
AMORTIGUAMIENTO = 0.05
PERIODOS = np.logspace(np.log10(0.01), np.log10(10), 100)
FREQS_OSCILADOR = 1 / PERIODOS


# =================================================

def cargar_datos_auxiliares():
    """
    Carga los CSV de curvas de diseño y el mapeo de suelos en memoria.
    Retorna dos diccionarios.
    """
    print("--- Cargando datos auxiliares ---")

    # 1. Cargar Mapeo de Suelos (Estación -> Tipo)
    mapa_suelos = {}
    ruta_suelo = os.path.join(CARPETA_CURVAS, "suelo.csv")
    try:
        with open(ruta_suelo, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # Saltar cabecera si existe
            for row in reader:
                if len(row) >= 2:
                    estacion = row[0].strip()
                    tipo = row[1].strip()
                    mapa_suelos[estacion] = tipo
        print(f"✅ Mapa de suelos cargado: {len(mapa_suelos)} estaciones registradas.")
    except Exception as e:
        print(f"⚠️ Error cargando suelo.csv: {e}")

    # 2. Cargar Curvas de Diseño (S1, S2, S3, S4)
    curvas_diseno = {}
    tipos = ["S1", "S2", "S3", "S4"]

    for t in tipos:
        ruta = os.path.join(CARPETA_CURVAS, f"{t}.csv")
        try:
            # Usamos numpy para leer rápido las columnas numéricas
            # Asumimos: Col 0 = Periodo, Col 1 = Aceleración
            data = np.loadtxt(ruta, delimiter=',', skiprows=1)
            curvas_diseno[t] = {
                "T": data[:, 0],  # Periodos
                "A": data[:, 1] * 100  # Aceleraciones
            }
            print(f"✅ Curva {t} cargada correctamente.")
        except Exception as e:
            print(f"⚠️ No se pudo cargar la curva {t} (o archivo no existe): {e}")

    return mapa_suelos, curvas_diseno


def procesar_un_sismo(archivo, mapa_suelos, curvas_diseno):
    """
    Procesa el sismo y recibe los diccionarios de suelos y curvas como argumentos.
    """
    nombre_archivo = os.path.basename(archivo)

    try:
        st = obspy.read(archivo)

        # Pre-procesamiento
        st.detrend("demean")
        st.detrend("linear")
        st.taper(max_percentage=0.05, type="hann")

        # Seleccionar canales
        tr_n_list = st.select(channel="HNN")
        tr_e_list = st.select(channel="HNE")

        if not tr_n_list or not tr_e_list:
            return f"⚠️ Saltado (Faltan canales): {nombre_archivo}"

        tr_y = tr_n_list[0]
        tr_x = tr_e_list[0]

        estacion_nombre = tr_x.stats.station
        dt = tr_x.stats.delta

        # Recorte y Conversión a cm/s²
        n_pts = min(tr_x.stats.npts, tr_y.stats.npts)
        accel_x = tr_x.data[:n_pts] * 100.0  # m/s² a cm/s²
        accel_y = tr_y.data[:n_pts] * 100.0  # m/s² a cm/s²

        # --- LÓGICA DE SUELOS ---
        # 1. Buscar qué suelo tiene esta estación
        tipo_suelo = mapa_suelos.get(estacion_nombre, None)

        datos_curva_usuario = None
        etiqueta_curva = None

        # 2. Si encontramos el suelo, buscamos su curva correspondiente
        if tipo_suelo and tipo_suelo in curvas_diseno:
            datos_curva_usuario = curvas_diseno[tipo_suelo]
            etiqueta_curva = f"Diseño {tipo_suelo}"
        elif tipo_suelo:
            etiqueta_curva = f"Suelo {tipo_suelo} (Sin curva cargada)"
        else:
            etiqueta_curva = "Suelo Desconocido"

        # --- CÁLCULO ---
        resp_x = pyrotd.calc_spec_accels(dt, accel_x, FREQS_OSCILADOR, AMORTIGUAMIENTO)
        resp_y = pyrotd.calc_spec_accels(dt, accel_y, FREQS_OSCILADOR, AMORTIGUAMIENTO)
        rot_resp = pyrotd.calc_rotated_spec_accels(
            dt, accel_x, accel_y, FREQS_OSCILADOR, AMORTIGUAMIENTO, percentiles=[100]
        )

        # --- GRAFICAR ---
        crear_grafica_thread_safe(
            PERIODOS, resp_x, resp_y, rot_resp,
            estacion_nombre, nombre_archivo,
            datos_extra=datos_curva_usuario,
            etiqueta_extra=etiqueta_curva
        )

        return f"✅ {nombre_archivo} -> Estación: {estacion_nombre} (Suelo: {tipo_suelo if tipo_suelo else 'N/A'})"

    except Exception as e:
        return f"❌ Error en {nombre_archivo}: {str(e)}"


def crear_grafica_thread_safe(periodos, resp_x, resp_y, rot_resp, station, filename_orig, datos_extra=None,
                              etiqueta_extra=None):
    fig, ax = plt.subplots(figsize=(10, 6))

    # Curvas calculadas
    ax.plot(periodos, resp_x.spec_accel, label='HNE', linestyle=':', color='blue', alpha=0.4)
    ax.plot(periodos, resp_y.spec_accel, label='HNN', linestyle=':', color='green', alpha=0.4)
    ax.plot(periodos, rot_resp.spec_accel, label='RotD100', color='red', linewidth=2)

    # Curva de diseño (Si existe)
    if datos_extra is not None:
        ax.plot(
            datos_extra["T"],
            datos_extra["A"],
            label=etiqueta_extra,
            color='black',
            linestyle='--',
            linewidth=2.5,
            alpha=0.8
        )
    elif etiqueta_extra:
        # Truco para que aparezca en la leyenda que no se encontró suelo
        ax.plot([], [], ' ', label=f"({etiqueta_extra})")

    ax.set_title(f"Espectro de Respuesta - Estación: {station}")
    ax.set_xlabel("Periodo (s)")
    ax.set_ylabel("Aceleración Espectral ($cm/s^2$)")
    ax.set_xscale('log')
    ax.set_xlim(left=0.01)
    ax.grid(True, which="both", ls="-", alpha=0.3)
    ax.legend()

    nombre_limpio = os.path.splitext(filename_orig)[0]
    ruta_guardado = os.path.join(CARPETA_SALIDA, f"{station}_{nombre_limpio}_RotD100.png")

    fig.savefig(ruta_guardado, dpi=150)
    plt.close(fig)


def main():
    if not os.path.exists(CARPETA_SALIDA):
        os.makedirs(CARPETA_SALIDA)

    # 1. CARGAR DATOS ANTES DEL PARALELISMO
    mapa_suelos, curvas_diseno = cargar_datos_auxiliares()

    archivos = glob.glob(os.path.join(CARPETA_MSEED, "*.mseed"))
    total = len(archivos)

    print(f"\n--- Iniciando procesamiento paralelo de {total} archivos ---")

    # 2. EJECUCIÓN PARALELA
    # Pasamos mapa_suelos y curvas_diseno a cada hilo
    resultados = Parallel(n_jobs=-1, verbose=5)(
        delayed(procesar_un_sismo)(archivo, mapa_suelos, curvas_diseno) for archivo in archivos
    )

    print("\n--- Resumen ---")
    for res in resultados:
        if "✅" not in res:  # Solo mostrar errores o advertencias para limpiar la salida
            print(res)

    print("Proceso finalizado.")


if __name__ == "__main__":
    main()
