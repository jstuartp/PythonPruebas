from pyzabbix import ZabbixAPI
import sys

# Configuración del servidor Zabbix
ZABBIX_URL = "http://10.208.36.97/zabbix"
ZABBIX_USER = "Admin"
ZABBIX_PASSWORD = "zabbix"

# Archivo de entrada con los hosts
HOSTS_FILE = "listado_host.txt"

# Conectar a Zabbix
try:
    zapi = ZabbixAPI(ZABBIX_URL)
    zapi.login(ZABBIX_USER, ZABBIX_PASSWORD)
    print("Conexión exitosa a Zabbix")
except Exception as e:
    print(f"Error al conectar con Zabbix: {e}")
    sys.exit(1)

# Función para obtener el ID del grupo de host
def get_hostgroup_id(group_name):
    result = zapi.hostgroup.get(filter={"name": group_name})
    if result:
        return result[0]["groupid"]
    else:
        print(f"El grupo '{group_name}' no existe. Creándolo...")
        new_group = zapi.hostgroup.create(name=group_name)
        return new_group["groupids"][0]

# Función para agregar un host
def add_host(hostname):
    #group_id = get_hostgroup_id(group_name)

    try:
        zapi.host.create(
            host=hostname,
            interfaces=[{
                "type": 1,  # 1 = Agent, 2 = SNMP, 3 = IPMI, 4 = JMX
                "main": 1,
                "useip": 1,
                "ip": "163.178.101.110",
                "dns": "",
                "port": "10051"
            }],
            groups=[{"groupid": "19"}],
            templates=[{
                "templateid": "10653"
            }]
        )
        print(f"Host '{hostname}' agregado correctamente.")
    except Exception as e:
        print(f"Error al agregar el host '{hostname}': {e}")

# Leer el archivo de hosts y agregar los hosts al servidor Zabbix
try:
    with open(HOSTS_FILE, "r") as file:
        for line in file:
            data = line.strip().split(",")
            if len(data) == 3:
                hostname, ip, group_name = data
                add_host(hostname)
            else:
                print(f"Línea con formato incorrecto: {line}")
except FileNotFoundError:
    print(f"Error: El archivo '{HOSTS_FILE}' no se encuentra.")
    sys.exit(1)

print("Proceso finalizado.")