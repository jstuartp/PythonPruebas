import os
import sys
import json
import logging
import argparse
import subprocess
from pathlib import Path

# Nuevas importaciones para la integración matemática y filtros
import numpy as np
from scipy.integrate import cumulative_trapezoid
from scipy.signal import butter, filtfilt
from obspy import read, read_inventory


def setup_logger(log_dir, dir_name):
    """
    Configura el sistema de logging para escribir en un archivo específico por evento,
    además de mostrar la salida en la consola.
    """
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"log_evento_{dir_name}.log")

    logger = logging.getLogger(f"procesador_{dir_name}")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


def filtro_paso_alto(data, cutoff, fs, order=4):
    """
    Aplica un filtro paso alto para eliminar la desviación de la línea base (drift)
    que ocurre naturalmente al integrar señales sísmicas.
    """
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='high', analog=False)
    # filtfilt aplica el filtro hacia adelante y hacia atrás para no desfasar la onda
    y = filtfilt(b, a, data)
    return y


def procesar_mseed(input_dir):
    """
    Lee archivos mseed de un directorio, remueve la respuesta instrumental para
    obtener ACC usando ObsPy, y usa SciPy para integrar a VEL y DISP.
    Guarda los resultados como JSON.
    """
    input_path = Path(input_dir)
    dir_name = input_path.name

    inventory_file = "/home/lis/waves/inventory_Estructuras.xml"
    base_json_dir = f"/home/lis/waves/jsons/{dir_name}/edificio"
    log_dir = "/home/lis/waves/logs/"

    logger = setup_logger(log_dir, dir_name)
    logger.info(f"Iniciando procesamiento del directorio: {input_path}")

    if not input_path.exists() or not input_path.is_dir():
        logger.error(f"El directorio de entrada no existe o no es un directorio: {input_path}")
        sys.exit(1)

    if not os.path.exists(inventory_file):
        logger.error(f"El archivo de inventario no existe: {inventory_file}")
        sys.exit(1)

    os.makedirs(base_json_dir, exist_ok=True)
    logger.info(f"Directorio de salida JSON preparado: {base_json_dir}")

    try:
        logger.info(f"Cargando inventario desde: {inventory_file}")
        inventory = read_inventory(inventory_file)
    except Exception as e:
        logger.error(f"Error al cargar el inventario XML: {e}")
        sys.exit(1)

    mseed_files = list(input_path.glob("*.mseed"))
    if not mseed_files:
        logger.warning(f"No se encontraron archivos .mseed en {input_dir}")
        return

    for file_path in mseed_files:
        logger.info(f"Procesando archivo: {file_path.name}")

        try:
            st = read(str(file_path))

            # 1. Obtener la Aceleración usando ObsPy
            st_acc = st.copy()

            try:
                # Opcional pero recomendado: un pre_filt básico para la remoción de respuesta
                st_acc.remove_response(inventory=inventory, output='ACC', pre_filt=(0.05, 0.1, 30.0, 35.0))

                # Variables base asumiendo que todos los canales del archivo comparten meta
                t0 = st_acc[0].stats.starttime
                fs = st_acc[0].stats.sampling_rate
                npts = st_acc[0].stats.npts
                dt = 1.0 / fs  # Diferencial de tiempo en segundos

                # Preparar los diccionarios de datos para los JSON
                datos_acc = {}
                datos_vel = {}
                datos_disp = {}

                for tr in st_acc:
                    canal = tr.stats.channel
                    acc_raw = tr.data

                    # --- PROCESAMIENTO MATEMÁTICO ---

                    # A. Aceleración Limpia
                    # Quitamos la media (detrend) y filtramos
                    acc_clean = acc_raw - np.mean(acc_raw)
                    acc_clean = filtro_paso_alto(acc_clean, cutoff=0.05, fs=fs)

                    # ---> CONVERSIÓN DE UNIDADES <---
                    # Multiplicamos to_do el arreglo por 100 para pasar de m/s² a cm/s²
                    acc_clean = acc_clean * 100.0

                    # B. Integrar para obtener Velocidad
                    vel_raw = cumulative_trapezoid(acc_clean, dx=dt, initial=0.0)
                    vel_clean = vel_raw - np.mean(vel_raw)
                    vel_clean = filtro_paso_alto(vel_clean, cutoff=0.05, fs=fs)

                    # C. Integrar para obtener Desplazamiento
                    disp_raw = cumulative_trapezoid(vel_clean, dx=dt, initial=0.0)
                    disp_clean = disp_raw - np.mean(disp_raw)
                    disp_clean = filtro_paso_alto(disp_clean, cutoff=0.05, fs=fs)

                    # Guardar en diccionarios convirtiendo a listas de Python
                    datos_acc[canal] = acc_clean.tolist()
                    datos_vel[canal] = vel_clean.tolist()
                    datos_disp[canal] = disp_clean.tolist()

                # --- GENERACIÓN DE JSONs ---

                meta_base = {
                    "station": st_acc[0].stats.station,
                    "network": st_acc[0].stats.network,
                    "start_time": t0.strftime('%Y%m%dT%H%M%S'),
                    "sample_rate": fs,
                    "npts": npts
                }

                base_name = file_path.stem  # Nombre del archivo sin extensión

                # Función auxiliar para guardar cada tipo
                def guardar_json(out_type, datos):
                    json_filename = f"{base_name}_{out_type}.json"
                    json_filepath = os.path.join(base_json_dir, json_filename)
                    payload = {"meta": meta_base, "data": datos}
                    with open(json_filepath, 'w') as f:
                        json.dump(payload, f)
                    logger.info(f"  -> Archivo JSON generado con éxito: {json_filename}")

                guardar_json("ACC", datos_acc)
                guardar_json("VEL", datos_vel)
                guardar_json("DISP", datos_disp)

            except Exception as e:
                logger.error(f"  -> Error al procesar matemática o generar JSON para {file_path.name}: {e}")

        except Exception as e:
            logger.error(f"Error al leer el archivo MiniSEED {file_path.name}: {e}")

    logger.info("Procesamiento finalizado.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convierte archivos MiniSEED a JSON (ACC, VEL, DISP) mediante integración numérica")
    parser.add_argument("input_dir", help="Ruta al directorio que contiene los archivos mseed a procesar")

    args = parser.parse_args()

    clean_input_dir = os.path.normpath(args.input_dir)
    procesar_mseed(clean_input_dir)
    resultEspectroF = subprocess.Popen(
        ["python3", "/home/lis/waves/scripts/espectro_f.py", "/home/lis/waves/eventos/" + args.input_dir])
    logging.info(f"Resultado de proceso... {resultEspectroF}")