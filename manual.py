import os
from obspy import read, read_inventory
from obspy.signal.filter import bandpass
from obspy.signal.invsim import simulate_seismometer
import numpy as np

# Ruta del directorio con archivos .mseed
DATA_DIR = "/home/lis/waves/manual/"
# Ruta del archivo StationXML
INVENTORY_FILE = "/home/lis/Pruebas_fdns.xml"

# Cargar inventario
inventory = read_inventory(INVENTORY_FILE)

# Función para calcular PGA (en cm/s²)
def calcular_pga(tr):
    # Convertir de m/s² a cm/s²
    data_cm = tr.data * 100.0
    pga = np.max(np.abs(data_cm))
    return pga

# Procesar cada archivo .mseed en el directorio
for filename in os.listdir(DATA_DIR):
    if filename.endswith(".mseed"):
        filepath = os.path.join(DATA_DIR, filename)
        try:
            # Leer waveform
            st = read(filepath)

            # Para cada traza, quitar la respuesta y calcular PGA
            for tr in st:
                # Quitar la respuesta instrumental
                tr.remove_response(inventory=inventory)
                tr.detrend("demean")
                tr.detrend("linear")
                tr.taper(max_percentage=0.05, type="hann")
                tr.filter("bandpass", freqmin=0.05,
                          freqmax=25,
                          corners=2)

                # Calcular el PGA
                pga_cm_s2 = calcular_pga(tr)

                # Imprimir resultado
                print(f"Archivo: {filename} | Estación: {tr.stats.station} | PGA: {pga_cm_s2:.2f} cm/s²")

        except Exception as e:
            print(f"Error procesando {filename}: {e}")