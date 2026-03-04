import os
import sys
import json
import logging
import argparse
from pathlib import Path
from obspy import read, read_inventory


def setup_logger(log_dir, dir_name):
    """
    Configura el sistema de logging para escribir en un archivo específico por evento,
    además de mostrar la salida en la consola.
    """
    # Crear el directorio de logs si no existe
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f"log_evento_{dir_name}.log")

    # Crear un logger personalizado
    logger = logging.getLogger(f"procesador_{dir_name}")
    logger.setLevel(logging.DEBUG)  # Nivel base del logger

    # Evitar duplicar logs si la función se llama varias veces
    if not logger.handlers:
        # Formato del log
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

        # Handler para el archivo
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)

        # Handler para la consola (opcional, pero útil al correr en terminal)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


def procesar_mseed(input_dir):
    """
    Lee archivos mseed de un directorio, remueve la respuesta instrumental para
    obtener ACC, VEL y DISP, y los guarda como JSON.
    """
    # 1. Definir rutas y variables principales
    input_path = Path(input_dir)
    dir_name = input_path.name  # Extrae el 'nombredirectorio' final de la ruta

    # Rutas estáticas definidas en tus requerimientos
    inventory_file = "/home/lis/waves/inventory_Estructuras.xml"
    base_json_dir = f"/home/lis/waves/jsons/{dir_name}/edificio"
    log_dir = "/home/lis/waves/logs/"

    # 2. Inicializar el logger
    logger = setup_logger(log_dir, dir_name)
    logger.info(f"Iniciando procesamiento del directorio: {input_path}")

    # 3. Validar entradas
    if not input_path.exists() or not input_path.is_dir():
        logger.error(f"El directorio de entrada no existe o no es un directorio: {input_path}")
        sys.exit(1)

    if not os.path.exists(inventory_file):
        logger.error(f"El archivo de inventario no existe: {inventory_file}")
        sys.exit(1)

    # 4. Crear directorio de salida JSON si no existe
    os.makedirs(base_json_dir, exist_ok=True)
    logger.info(f"Directorio de salida JSON preparado: {base_json_dir}")

    # 5. Cargar el inventario (Metadata de las estaciones)
    try:
        logger.info(f"Cargando inventario desde: {inventory_file}")
        inventory = read_inventory(inventory_file)
    except Exception as e:
        logger.error(f"Error al cargar el inventario XML: {e}")
        sys.exit(1)

    # Buscar archivos .mseed (puedes ajustar la extensión si tus archivos no la tienen)
    mseed_files = list(input_path.glob("*.mseed"))
    if not mseed_files:
        logger.warning(f"No se encontraron archivos .mseed en {input_dir}")
        return

    # 6. Procesar cada archivo MiniSEED
    for file_path in mseed_files:
        logger.info(f"Procesando archivo: {file_path.name}")

        try:
            # Leer el archivo MiniSEED (generalmente contendrá 3 traces)
            st = read(str(file_path))

            # Definir las unidades de salida requeridas
            output_types = ['ACC', 'VEL', 'DISP']

            for out_type in output_types:
                # Trabajar sobre una copia para no alterar el stream original en cada iteración
                st_copy = st.copy()

                try:
                    # Remover la respuesta instrumental.
                    # Nota de Sismología: Para VEL y DISP, suele ser muy recomendable aplicar
                    # un 'pre_filt' para evitar que el ruido de baja frecuencia se amplifique
                    # durante la integración. Lo dejo como lo pediste, pero tenlo en cuenta.
                    st_copy.remove_response(inventory=inventory, output=out_type)

                    # Asumimos que todos los traces en el stream comparten meta-información básica
                    # Tomamos el primero para armar el bloque "meta"
                    t0 = st_copy[0].stats.starttime

                    payload = {
                        "meta": {
                            "station": st_copy[0].stats.station,
                            "network": st_copy[0].stats.network,
                            "start_time": t0.strftime('%Y%m%dT%H%M%S'),
                            "sample_rate": 200,
                            "npts": st[0].stats.npts
                        },
                        "data": {}
                    }

                    # Llenar el bloque de datos con cada Trace (ej. HNE, HNN, HNZ)
                    for tr in st_copy:
                        channel_name = tr.stats.channel
                        # Convertimos el array de numpy a una lista normal de Python para JSON
                        payload["data"][channel_name] = tr.data.tolist()

                    # Construir el nombre del archivo JSON de salida
                    # Ejemplo: sismo_ACC.json
                    base_name = file_path.stem  # Nombre del archivo sin extensión
                    json_filename = f"{base_name}_{out_type}.json"
                    json_filepath = os.path.join(base_json_dir, json_filename)

                    # Guardar el JSON
                    with open(json_filepath, 'w') as f:
                        json.dump(payload, f)

                    logger.info(f"  -> Archivo JSON generado con éxito: {json_filename}")

                except Exception as e:
                    logger.error(
                        f"  -> Error al remover respuesta o generar JSON para {out_type} en {file_path.name}: {e}")

        except Exception as e:
            logger.error(f"Error al leer el archivo MiniSEED {file_path.name}: {e}")

    logger.info("Procesamiento finalizado.")


if __name__ == "__main__":
    # Configurar el parseo de argumentos por línea de comandos
    parser = argparse.ArgumentParser(description="Convierte archivos MiniSEED a JSON (ACC, VEL, DISP)")
    parser.add_argument("input_dir", help="Ruta al directorio que contiene los archivos mseed a procesar")

    args = parser.parse_args()

    # Limpiar la ruta para evitar problemas con barras diagonales al final (ej. /carpeta/ vs /carpeta)
    clean_input_dir = os.path.normpath(args.input_dir)

    procesar_mseed(clean_input_dir)