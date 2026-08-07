import os
import glob
import json
import sys
import argparse
import numpy as np
from obspy import read
from pathlib import Path

def procesar_duracion_y_exportar(directorio, resultado,umbral):
    """
    Calcula la duración 3D, filtra por umbral, ordena por duración máxima
    y exporta los resultados a un archivo JSON.
    """
    resultados = []

    ruta_busqueda = os.path.join(directorio, "*.mseed")
    archivos = glob.glob(ruta_busqueda)

    if not archivos:
        print(f"No se encontraron archivos .mseed en: {directorio}")
        return None

    print(f"{'ESTACIoN':<12} | {'DURACIoN (s)':<15} | {'PGA 3D (cm/s²)':<15}")
    print("-" * 50)

    for archivo in archivos:
        try:
            st = read(archivo)

            tr_z = st.select(component="Z")[0]
            tr_n = st.select(component="N")[0]
            tr_e = st.select(component="E")[0]

            tr_z.filter("bandpass", freqmin=0.1, freqmax=10, corners=2)
            tr_n.filter("bandpass", freqmin=0.1, freqmax=10, corners=2)
            tr_e.filter("bandpass", freqmin=0.1, freqmax=10, corners=2)

            dt = tr_z.stats.delta
            estacion = tr_z.stats.station

            min_len = min(len(tr_z.data), len(tr_n.data), len(tr_e.data))

            data_z = tr_z.data[:min_len]
            data_n = tr_n.data[:min_len]
            data_e = tr_e.data[:min_len]

            a_3d = np.sqrt(data_z**2 + data_n**2 + data_e**2)
            pga_3d = np.max(a_3d)

            indices_superan = np.where(a_3d > umbral)[0]

            # Filtro: Solo procesar si el umbral es superado
            #solo se guardan los puntos que superan el umbral
            if len(indices_superan) > 0:
                i_inicial = indices_superan[0]
                i_final = indices_superan[-1]
                # se calcula restando el primer punto que supero el umbral - el ultimo punto x el delta
                duracion = (i_final - i_inicial) * dt

                # Guardar en diccionario, casteando a float nativo para el JSON
                resultados.append({
                    "estacion": estacion,
                    "duracion_s": float(duracion),
                    "pga_3d_cm_s2": float(pga_3d)
                })
                print(f"{estacion:<12} | {duracion:<15.2f} | {pga_3d:<15.4f}")
            else:
                # Opcional: Imprimir en consola que fue omitida
                print(f"{estacion:<12} | {'0.00 (Omitida)':<15} | {pga_3d:<15.4f}")

        except IndexError:
            print(f"[{os.path.basename(archivo)}] Error: Faltan componentes (Z, N o E).")
        except Exception as e:
            print(f"[{os.path.basename(archivo)}] Error inesperado: {e}")

    # Si ninguna estación superó el umbral, terminamos la ejecución
    if not resultados:
        print("\nNinguna estacion supero el umbral establecido. No se genero JSON.")
        return None

    # Ordenar la lista de diccionarios por 'duracion_s' de forma descendente
    resultados_ordenados = sorted(resultados, key=lambda x: x['duracion_s'], reverse=True)

    if len(resultados_ordenados) > 20:
        resultados_ordenados = resultados_ordenados[:20]

    # 3. Si cumple con tener al menos 5 registros, se ejecuta tu fragmento de código
    if len(resultados_ordenados) >= 5:
        umbral_str = str(umbral).replace(".", "_")
        nombre_archivo_json = f"{resultado}_{umbral_str}_grafico_mov.json"
        # Exportar el archivo JSON
        with open(nombre_archivo_json, 'w', encoding='utf-8') as f:
            json.dump(resultados_ordenados, f, indent=4)

        print(f"\nProceso finalizado. Archivo creado: {nombre_archivo_json}")

    return resultados_ordenados

# Ejecución
# Asegúrate de que el umbral coincida con la unidad (0.05 cm/s²)
#directorio_mseed = "./UCR_lis2026jikv"
#datos_json = procesar_duracion_y_exportar(directorio_mseed, umbral=0.05)

def main():
    parser = argparse.ArgumentParser(description="Recibe parametros string y float")
    parser.add_argument("--directorio", type=str, required=True, help="directorio mseed a procesar")
    parser.add_argument("--resultado", type=str, required=True, help="donde se guarda el json")



    args = parser.parse_args()

    # Pasamos datos a la funcion
    datos1_json = procesar_duracion_y_exportar(args.directorio, args.resultado, 0.05)
    datos2_json = procesar_duracion_y_exportar(args.directorio, args.resultado, 10)


if __name__ == "__main__":
    sys.exit(main())






