import os
import warnings
from obspy.clients.fdsn import Client
from obspy import UTCDateTime
from datetime import datetime, timedelta, timezone
from obspy.io.mseed.headers import InternalMSEEDWarning
from concurrent.futures import ThreadPoolExecutor, as_completed

# ------------------------------------------------------------------------------
# Ignoramos advertencias que salen a veces al procesar archivos miniSEED
# ------------------------------------------------------------------------------
warnings.filterwarnings("ignore", category=InternalMSEEDWarning)

# ------------------------------------------------------------------------------
# Función auxiliar para formatear fecha-hora de log
# ------------------------------------------------------------------------------
def log_time():
    """
    Devuelve la fecha-hora actual en formato:
    YYYY-MM-DD HH:MM:SS (zona UTC)
    """
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

# ------------------------------------------------------------------------------
# Función para descargar y procesar una estación en particular
# ------------------------------------------------------------------------------
def descargar_estacion(estacion, client, t_inicio, ahora, directorio_storage):
    """
    Descarga y procesa los datos para la estación dada (formato NET.STA),
    eliminando respuesta instrumental y guardando el archivo miniSEED.
    Devuelve un string con el log del resultado.
    """
    try:
        # Separar la red (net) y la estación (sta)
        net, sta = estacion.split(".")
        
        # Definir comodines de localización y canal
        loc = "*"
        cha = "H*"
        
        # Obtener la traza (stream) desde el FDSN
        st = client.get_waveforms(
            network=net,
            station=sta,
            location=loc,
            channel=cha,
            starttime=t_inicio,
            endtime=ahora,
            attach_response=False
        )
        
        # Si la traza está vacía, no hay datos
        if len(st) == 0:
            return f"[{log_time()}] Estacion {sta} sin datos ..."
        
        # Obtener la respuesta del instrumento para poder removerla
        response = client.get_stations(
            network=net,
            station=sta,
            location=loc,
            channel=cha,
            starttime=t_inicio,
            endtime=ahora,
            level="response"
        )
        
        # Adjuntar la respuesta a la traza
        st.attach_response(response)
        
        # Remover la respuesta instrumental para obtener aceleración (ACC)
        st.remove_response(output="ACC", zero_mean=True, taper=True)
        
        # Crear un string con el tiempo de inicio en formato:
        # Año, día juliano, hora, minuto
        # (Por ejemplo: 2023054_1530 => 23 de febrero, 15:30 UTC)
        timestamp = t_inicio.strftime('%Y%j_%H%M')
        
        # Construir el nombre de archivo con la estación y el timestamp
        nombre_archivo = f"{sta}_{timestamp}.mseed"
        
        # Ruta final donde se va a guardar
        ruta_archivo = os.path.join(directorio_storage, nombre_archivo)
        
        # Guardar el stream en formato MSEED
        st.write(ruta_archivo, format="MSEED")
        
        # Devuelve log de que se descargó correctamente
        return f"[{log_time()}] Estacion {sta} descargada => {ruta_archivo}"
        
    except Exception as e:
        # Si ocurre un error (por ejemplo, no conecta, etc.)
        return f"[{log_time()}] Estacion {estacion} sin datos ... Error: {e}"


# ------------------------------------------------------------------------------
# Registramos la hora de inicio del script
# ------------------------------------------------------------------------------
script_start = datetime.now(timezone.utc)

# ------------------------------------------------------------------------------
# Configuración del servidor FDSN
# ------------------------------------------------------------------------------
fdsn_url = "http://163.178.101.110:8080"  # URL base del servidor FDSN
client = Client(base_url=fdsn_url)        # Creamos el cliente a partir de esa URL

# ------------------------------------------------------------------------------
# Directorio donde se guardarán los miniSEED
# ------------------------------------------------------------------------------
directorio_storage = "/home/lis/administrador-de-servidores/trazas-para-la-web/storage"
os.makedirs(directorio_storage, exist_ok=True)

# ------------------------------------------------------------------------------
# Leemos la lista de estaciones desde un archivo de texto
# (Se asume que cada línea del archivo estaciones.txt tiene el formato NET.STA)
# ------------------------------------------------------------------------------
ruta_estaciones = "/home/lis/administrador-de-servidores/trazas-para-la-web/estaciones.txt"
with open(ruta_estaciones, "r") as f:
    estaciones = [line.strip() for line in f if line.strip()]  # quitamos líneas vacías

# ------------------------------------------------------------------------------
# Definimos los tiempos de inicio y fin para la descarga (últimos 12 minutos)
# ------------------------------------------------------------------------------
ahora = UTCDateTime()  # Momento actual en UTCDateTime (Obspy)
t_inicio = ahora - 600  # 600 segundos = 12 minutos

# ------------------------------------------------------------------------------
# Descarga en paralelo usando un ThreadPoolExecutor
# ------------------------------------------------------------------------------
max_workers = min(10, len(estaciones))  # Número de hilos (ajústalo según tu caso)
futures = []

print(f"[{log_time()}] Iniciando descargas en paralelo...")

with ThreadPoolExecutor(max_workers=max_workers) as executor:
    for estacion in estaciones:
        # Lanzamos la tarea en un hilo
        futures.append(executor.submit(descargar_estacion, estacion, client, t_inicio, ahora, directorio_storage))
    
    # Vamos esperando que concluyan y recogiendo sus resultados (logs)
    for future in as_completed(futures):
        resultado_log = future.result()
        print(resultado_log)

# ------------------------------------------------------------------------------
# Eliminar archivos con más de 70 minutos de antigüedad
# ------------------------------------------------------------------------------
limite_tiempo = datetime.now(timezone.utc) - timedelta(minutes=70)

for archivo in os.listdir(directorio_storage):
    ruta_archivo = os.path.join(directorio_storage, archivo)
    if os.path.isfile(ruta_archivo):
        # Obtener la fecha de modificación del archivo en zona UTC
        tiempo_modificacion = datetime.fromtimestamp(os.path.getmtime(ruta_archivo), timezone.utc)
        
        # Si el archivo se modificó hace más de 70 minutos, lo borramos
        if tiempo_modificacion < limite_tiempo:
            os.remove(ruta_archivo)
            print(f"[{log_time()}] Archivo eliminado por antigüedad: {archivo}")

# ------------------------------------------------------------------------------
# Mensaje final con la duración total del script
# ------------------------------------------------------------------------------
script_end = datetime.now(timezone.utc)  # Hora final
duracion = (script_end - script_start).total_seconds()  # Duración en segundos

print(f"[{log_time()}] Script finalizado. Duración total: {duracion:.2f} segundos.")
