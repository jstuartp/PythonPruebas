import os
import glob
import obspy
import numpy as np
import pyrotd
import matplotlib.pyplot as plt
from joblib import Parallel, delayed  # Importamos la herramienta de paralelización

# ================= CONFIGURACIÓN =================
CARPETA_MSEED = "./UCR_lis2026biqs"  # Carpeta con tus archivos .mseed (ya en aceleración)
CARPETA_SALIDA = "./espectros_out_1"  # Donde se guardarán los PNG

# Parámetros para Espectros
AMORTIGUAMIENTO = 0.05
PERIODOS = np.logspace(np.log10(0.01), np.log10(10), 100)  # De 0.01s a 10s
FREQS_OSCILADOR = 1 / PERIODOS


# =================================================

def procesar_un_sismo(archivo):
    """
    Función aislada que procesa un solo archivo.
    Al ser independiente, puede correr en un núcleo separado del procesador.
    """
    nombre_archivo = os.path.basename(archivo)

    try:
        # Leer traza (ObsPy lee rápido, el cuello de botella es el cálculo espectral)
        st = obspy.read(archivo)

        # --- PRE-PROCESAMIENTO BÁSICO ---
        # Aunque ya sea aceleración, quitamos tendencias lineales y medias
        # para evitar derivas en el cálculo numérico.
        st.detrend("demean")
        st.detrend("linear")
        st.taper(max_percentage=0.05, type="hann")

        # --- SELECCIÓN DE CANALES ---
        # Buscamos trazas HNN y HNE
        tr_n_list = st.select(channel="HNN")
        tr_e_list = st.select(channel="HNE")

        if not tr_n_list or not tr_e_list:
            return f"⚠️ Saltado (Faltan canales HNN/HNE): {nombre_archivo}"

        # Tomamos la primera traza encontrada de cada canal
        tr_y = tr_n_list[0]  # N (Y)
        tr_x = tr_e_list[0]  # E (X)

        estacion_nombre = tr_x.stats.station
        dt = tr_x.stats.delta

        # Asegurar que tengan el mismo número de puntos
        n_pts = min(tr_x.stats.npts, tr_y.stats.npts)
        accel_x = tr_x.data[:n_pts] * 100.0
        accel_y = tr_y.data[:n_pts] * 100.0

        # --- CÁLCULO DE ESPECTROS (Pyrotd) ---
        # Esto es lo que consume CPU, ideal para paralelo
        resp_x = pyrotd.calc_spec_accels(dt, accel_x, FREQS_OSCILADOR, AMORTIGUAMIENTO)
        resp_y = pyrotd.calc_spec_accels(dt, accel_y, FREQS_OSCILADOR, AMORTIGUAMIENTO)

        rot_resp = pyrotd.calc_rotated_spec_accels(
            dt, accel_x, accel_y, FREQS_OSCILADOR, AMORTIGUAMIENTO, percentiles=[100]
        )

        # --- GRAFICAR ---
        # Usamos el estilo Orientado a Objetos para evitar problemas de hilos con Pyplot
        crear_grafica_thread_safe(PERIODOS, resp_x, resp_y, rot_resp, estacion_nombre, nombre_archivo)

        return f"✅ Procesado con éxito: {nombre_archivo} ({estacion_nombre})"

    except Exception as e:
        return f"❌ Error en {nombre_archivo}: {str(e)}"


def crear_grafica_thread_safe(periodos, resp_x, resp_y, rot_resp, station, filename_orig):
    """
    Crea la gráfica y la guarda. Usa una figura nueva cada vez y la cierra explícitamente
    para evitar fugas de memoria en procesos largos.
    """
    # Crear figura y ejes explícitamente
    fig, ax = plt.subplots(figsize=(10, 6))

    # Graficar
    ax.plot(periodos, resp_x.spec_accel, label='HNE (Este)', linestyle='--', color='blue', alpha=0.5, linewidth=1)
    ax.plot(periodos, resp_y.spec_accel, label='HNN (Norte)', linestyle='--', color='green', alpha=0.5, linewidth=1)
    ax.plot(periodos, rot_resp.spec_accel, label='RotD100', color='red', linewidth=2)

    # Estética
    ax.set_title(f"Espectro de Respuesta - Estación: {station}")
    ax.set_xlabel("Periodo (s)")
    ax.set_ylabel("Aceleración Espectral ($cm/s^2$)")
    ax.set_xscale('log')
    ax.grid(True, which="both", ls="-", alpha=0.3)
    ax.legend()

    # Guardar archivo
    nombre_limpio = os.path.splitext(filename_orig)[0]
    ruta_guardado = os.path.join(CARPETA_SALIDA, f"{station}_{nombre_limpio}_RotD100.png")

    fig.savefig(ruta_guardado, dpi=150)
    plt.close(fig)  # CRÍTICO: Cerrar la figura para liberar memoria en el proceso


def main():
    # 1. Preparar entorno
    if not os.path.exists(CARPETA_SALIDA):
        os.makedirs(CARPETA_SALIDA)

    # 2. Buscar archivos
    archivos = glob.glob(os.path.join(CARPETA_MSEED, "*.mseed"))
    total = len(archivos)
    print(f"--- Iniciando procesamiento paralelo de {total} archivos ---")
    print(f"--- Usando todos los núcleos disponibles ---")

    # 3. EJECUCIÓN PARALELA
    # n_jobs=-1 usa todos los CPUs.
    # verbose=10 muestra una barra de progreso o logs en la consola.
    resultados = Parallel(n_jobs=-1, verbose=5)(
        delayed(procesar_un_sismo)(archivo) for archivo in archivos
    )

    # 4. Reporte final
    print("\n--- Resumen del Procesamiento ---")
    for res in resultados:
        # Imprimimos solo si hubo error o advertencia para no saturar,
        # o puedes imprimir todo si prefieres.
        if "✅" not in res:
            print(res)

    print("Proceso finalizado.")


if __name__ == "__main__":
    # Esta protección es obligatoria en Windows para multiprocessing
    main()