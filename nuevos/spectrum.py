import os
import glob
import obspy
import numpy as np
import pyrotd
import matplotlib.pyplot as plt

# ================= CONFIGURACIÓN =================
CARPETA_MSEED = "./UCR_lis2026biqs/raw"  # Carpeta con tus archivos .mseed
ARCHIVO_INVENTORY = "inventory_full_fdns.xml"  # Ruta a tu archivo StationXML
CARPETA_SALIDA = "./espectros_out"  # Donde se guardarán los PNG

# Parámetros para Espectros
AMORTIGUAMIENTO = 0.05
PERIODOS = np.logspace(np.log10(0.01), np.log10(10), 100)  # De 0.01s a 10s
FREQS_OSCILADOR = 1 / PERIODOS

# Filtro para remove_response (Evita explosión de ruido en bajas frecuencias)
# (f1, f2, f3, f4) -> Pasa banda plana entre f2 y f3
PRE_FILT = (0.005, 0.01, 45.0, 50.0)


# =================================================

def procesar_archivos():
    # 1. Crear carpeta de salida si no existe
    if not os.path.exists(CARPETA_SALIDA):
        os.makedirs(CARPETA_SALIDA)

    # 2. Cargar Inventario
    print(f"Cargando inventario desde {ARCHIVO_INVENTORY}...")
    try:
        inv = obspy.read_inventory(ARCHIVO_INVENTORY)
    except Exception as e:
        print(f"❌ Error fatal cargando inventario: {e}")
        return

    # 3. Buscar archivos .mseed
    archivos = glob.glob(os.path.join(CARPETA_MSEED, "*.mseed"))
    print(f"Se encontraron {len(archivos)} archivos para procesar.\n")

    for i, archivo in enumerate(archivos, 1):
        try:
            print(f"[{i}/{len(archivos)}] Procesando: {os.path.basename(archivo)}")

            # Leer traza
            st = obspy.read(archivo)

            # --- PRE-PROCESAMIENTO BÁSICO ---
            # Necesario antes de quitar respuesta para estabilidad
            st.detrend("demean")
            st.detrend("linear")
            st.taper(max_percentage=0.05, type="hann")

            # --- REMOVE RESPONSE (Aceleración) ---
            # output="ACC" nos da unidades físicas (m/s² usualmente, depende del inventario)
            try:
                st.remove_response(inventory=inv, output="ACC", pre_filt=PRE_FILT, water_level=60)
            except Exception as e:
                print(f"   ⚠️ No se pudo remover respuesta (¿falta metadata para esta estación?): {e}")
                continue

            # --- SELECCIÓN DE CANALES ---
            # Buscamos trazas HNN y HNE
            tr_n = st.select(channel="HNN")
            tr_e = st.select(channel="HNE")

            if not tr_n or not tr_e:
                print(f"   ⚠️ Saltando: No se encontraron canales HNN y HNE en {os.path.basename(archivo)}")
                continue

            # Tomamos la primera traza encontrada de cada canal
            tr_y = tr_n[0]  # N (Y)
            tr_x = tr_e[0]  # E (X)

            estacion_nombre = tr_x.stats.station
            dt = tr_x.stats.delta

            # Asegurar que tengan el mismo número de puntos (recortar al menor)
            n_pts = min(tr_x.stats.npts, tr_y.stats.npts)
            accel_x = tr_x.data[:n_pts]
            accel_y = tr_y.data[:n_pts]

            # --- CÁLCULO DE ESPECTROS (Pyrotd) ---
            # 1. Componente X (HNE)
            resp_x = pyrotd.calc_spec_accels(dt, accel_x, FREQS_OSCILADOR, AMORTIGUAMIENTO)
            # 2. Componente Y (HNN)
            resp_y = pyrotd.calc_spec_accels(dt, accel_y, FREQS_OSCILADOR, AMORTIGUAMIENTO)
            # 3. RotD100
            rot_resp = pyrotd.calc_rotated_spec_accels(
                dt, accel_x, accel_y, FREQS_OSCILADOR, AMORTIGUAMIENTO, percentiles=[100]
            )

            # --- GRAFICAR Y GUARDAR ---
            crear_grafica(PERIODOS, resp_x, resp_y, rot_resp, estacion_nombre, archivo)

        except Exception as e:
            print(f"   ❌ Error inesperado en archivo {archivo}: {e}")


def crear_grafica(periodos, resp_x, resp_y, rot_resp, station, filename_orig):
    plt.figure(figsize=(10, 6))

    # Graficar
    plt.plot(periodos, resp_x.spec_accel, label='HNE (Este)', linestyle='--', color='blue', alpha=0.5, linewidth=1)
    plt.plot(periodos, resp_y.spec_accel, label='HNN (Norte)', linestyle='--', color='green', alpha=0.5, linewidth=1)
    plt.plot(periodos, rot_resp.spec_accel, label='RotD100', color='red', linewidth=2)

    # Estética
    plt.title(f"Espectro de Respuesta - Estación: {station}")
    plt.xlabel("Periodo (s)")
    plt.ylabel("Aceleración Espectral (m/s²)")  # Asumiendo que el StationXML devuelve m/s²
    plt.xscale('log')
    plt.grid(True, which="both", ls="-", alpha=0.3)
    plt.legend()

    # Guardar archivo
    nombre_limpio = os.path.splitext(os.path.basename(filename_orig))[0]
    ruta_guardado = os.path.join(CARPETA_SALIDA, f"{station}_{nombre_limpio}_RotD100.png")

    plt.savefig(ruta_guardado, dpi=150)
    plt.close()  # Importante cerrar para liberar memoria RAM
    print(f"   ✅ Gráfica guardada: {ruta_guardado}")


if __name__ == "__main__":
    procesar_archivos()