from pyzabbix import ZabbixAPI
import sys

# Configuración del servidor Zabbix
ZABBIX_URL = "http://10.208.36.97/zabbix"
ZABBIX_USER = "Admin"
ZABBIX_PASSWORD = "zabbix"

# Archivo de entrada con los hosts
HOSTS_FILE = "listado_host_borrar.txt"

# Conectar a Zabbix
try:
    zapi = ZabbixAPI(ZABBIX_URL)
    zapi.login(ZABBIX_USER, ZABBIX_PASSWORD)
    print("Conexión exitosa a Zabbix")
except Exception as e:
    print(f"Error al conectar con Zabbix: {e}")
    sys.exit(1)

# Función para obtener el ID de un host por nombre
def get_host_id(hostname):
    result = zapi.host.get(filter={"host": hostname})
    if result:
        return result[0]["hostid"]
    else:
        return None

# Leer el archivo de hosts y eliminar los hosts del servidor Zabbix
try:
    with open(HOSTS_FILE, "r") as file:
        for line in file:
            hostname = line.strip()
            if hostname:
                host_id = get_host_id(hostname)
                if host_id:
                    try:
                        zapi.host.delete(host_id)
                        print(f"Host '{hostname}' eliminado correctamente.")
                    except Exception as e:
                        print(f"Error al eliminar el host '{hostname}': {e}")
                else:
                    print(f"Host '{hostname}' no encontrado en Zabbix.")
except FileNotFoundError:
    print(f"Error: El archivo '{HOSTS_FILE}' no se encuentra.")
    sys.exit(1)

print("Proceso de eliminación finalizado.")