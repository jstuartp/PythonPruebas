import obspy
from obspy import read_inventory
import numpy as np
import json
import argparse
from pathlib import Path

# ==========================================
# Configuración Global
# ==========================================
# Ruta base donde se generará la estructura de carpetas.
BASE_DIR_SALIDA = "/home/lis/waves/jsons"
# Ruta al inventario StationXML
INVENTORY_PATH = "/home/lis/waves/inventory_Estructuras.xml"


def procesar_carpeta_mseed(ruta_carpeta):
    """
    Recorre una carpeta, calcula el espectro de Fourier de todas las componentes
    de los .mseed (removiendo la respuesta instrumental) y guarda un único JSON
    por sismo con estructura de diccionario.
    """
    carpeta_entrada = Path(ruta_carpeta)

    if not carpeta_entrada.is_dir():
        print(f"❌ Error: La ruta '{ruta_carpeta}' no es un directorio válido o no existe.")
        return

    archivos_mseed = list(carpeta_entrada.glob("*.mseed"))

    if not archivos_mseed:
        print(f"⚠️ No se encontraron archivos .mseed en '{ruta_carpeta}'.")
        return

    # Cargar el inventario una sola vez antes de procesar los archivos
    try:
        inv = read_inventory(INVENTORY_PATH)
        print(f"📄 Inventario cargado correctamente desde: {INVENTORY_PATH}")
    except Exception as e:
        print(f"❌ Error al cargar el inventario: {e}")
        return

    # 1. Extraer el nombre de la carpeta de origen y construir la ruta de salida
    nombre_carpeta_mseeds = carpeta_entrada.name
    ruta_salida = Path(BASE_DIR_SALIDA) / nombre_carpeta_mseeds / "edificio" / "fourier"

    # 2. Crear la estructura de directorios
    ruta_salida.mkdir(parents=True, exist_ok=True)

    print(f"📁 Directorio de salida listo: {ruta_salida}")
    print(f"🔍 Procesando {len(archivos_mseed)} archivos .mseed...\n")

    for archivo in archivos_mseed:
        try:
            # Leer el archivo MiniSEED completo (contiene múltiples trazas/componentes)
            stream = obspy.read(str(archivo))
            # recortando el archivo para ver solo el espacio del sismo
            tiempo_inicio = stream[0].stats.starttime
            # Calcular el centro temporal del archivo
            # minutos = 180 segundos. El centro está a los 90 segundos del inicio.
            tiempo_centro = tiempo_inicio + 90

            # Definir los nuevos límites de corte (t0 y t1)
            # 1 minuto (60 segundos) hacia atrás del centro, y 1 minuto hacia adelante
            t0 = tiempo_centro - 60
            t1 = tiempo_centro + 40

            # 5. Aplicar el recorte al stream
            stream.trim(starttime=t0, endtime=t1)
            stream.detrend("demean")
            stream.detrend("linear")
            stream.taper(max_percentage=0.05)

            # --- NUEVO: Remover respuesta instrumental ---
            # Se aplica antes del trim para evitar que el 'taper' afecte la porción del sismo
            stream.remove_response(inventory=inv, output="ACC")

            # Convertir de m/s^2 a cm/s^2 (común en ingeniería sísmica)
            for traza in stream:
                traza.data = traza.data * 100.0
            # ---------------------------------------------



            # Diccionario que almacenará todas las componentes de este archivo
            resultados_json = {}

            # 3. Iterar sobre cada componente dentro del archivo
            for traza in stream:
                # Extraer datos y metadatos básicos
                aceleracion = traza.data
                dt = traza.stats.delta
                n_puntos = len(aceleracion)
                canal = traza.stats.channel  # Ej: 'HNE', 'HNN', 'HNZ'
                estacion = traza.stats.station

                # Transformada de Fourier
                transformada = np.fft.rfft(aceleracion)
                frecuencias = np.fft.rfftfreq(n_puntos, d=dt)
                amplitudes = np.abs(transformada) * dt

                # Agregamos esta componente al diccionario principal
                resultados_json[canal] = {
                    "estacion": estacion,
                    "frecuencias_hz": frecuencias.tolist(),
                    "amplitudes": amplitudes.tolist()
                }

            # 4. Construir el nombre del archivo y la ruta absoluta final
            nombre_archivo_salida = f"{archivo.stem}_fourier.json"
            archivo_salida_final = ruta_salida / nombre_archivo_salida

            # 5. Escribir el JSON resultante unificado en la nueva ruta
            with open(archivo_salida_final, 'w') as f:
                json.dump(resultados_json, f, indent=4)

            # Informamos qué componentes se encontraron y guardaron
            canales_procesados = list(resultados_json.keys())
            print(f"✅ Guardado: {nombre_archivo_salida} | Componentes: {canales_procesados}")

        except Exception as e:
            print(f"❌ Error al procesar '{archivo.name}': {e}")


# ==========================================
# Configuración de parámetros por consola
# ==========================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calcula el espectro de Fourier (3 componentes) y lo guarda en directorios estructurados.")
    parser.add_argument("carpeta", type=str, help="Ruta a la carpeta original con los archivos .mseed")

    args = parser.parse_args()
    procesar_carpeta_mseed(args.carpeta)