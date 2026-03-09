import obspy
import numpy as np
import json
import argparse
from pathlib import Path

# ==========================================
# Configuración Global
# ==========================================
# Ruta base donde se generará la estructura de carpetas.
BASE_DIR_SALIDA = "/home/lis/waves/jsons"


def procesar_carpeta_mseed(ruta_carpeta):
    """
    Recorre una carpeta, calcula el espectro de Fourier de todas las componentes
    de los .mseed y guarda un único JSON por sismo con estructura de diccionario.
    """
    carpeta_entrada = Path(ruta_carpeta)

    if not carpeta_entrada.is_dir():
        print(f"❌ Error: La ruta '{ruta_carpeta}' no es un directorio válido o no existe.")
        return

    archivos_mseed = list(carpeta_entrada.glob("*.mseed"))

    if not archivos_mseed:
        print(f"⚠️ No se encontraron archivos .mseed en '{ruta_carpeta}'.")
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