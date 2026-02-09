import os
import glob
import json
import obspy

# ================= CONFIGURACIÓN =================
# Lista de carpetas que contienen los archivos .mseed
# Puedes agregar tantas rutas como necesites.
LISTA_DE_CARPETAS = [
    "./UCR_lis2025uumn","./UCR_lis2025wjyk","./UCR_lis2025wobp","./UCR_lis2025wvmd","./UCR_lis2025yrfu",
    "./UCR_lis2026akht","./UCR_lis2026bhem","./UCR_lis2026bxgo",
    "./UCR_lis2025uyll","./UCR_lis2025wlsz","./UCR_lis2025wqfg",
    "./UCR_lis2025wxfm","./UCR_lis2025yrfw","./UCR_lis2026autp",
    "./UCR_lis2026biqs","./UCR_lis2026cczr","./UCR_lis2025vbwz",
    "./UCR_lis2025wnzi","./UCR_lis2025wslb","./UCR_lis2025xyhk",
    "./UCR_lis2026agiv","./UCR_lis2026bern","./UCR_lis2026birv",
    "./UCR_lis2026cqti"
    # Agrega aquí más rutas...
]


# =================================================

def procesar_listado_carpetas():
    print(f"--- Iniciando procesamiento de {len(LISTA_DE_CARPETAS)} carpetas ---\n")

    for carpeta in LISTA_DE_CARPETAS:
        # Verificación de seguridad: ¿Existe la carpeta?
        if not os.path.isdir(carpeta):
            print(f"⚠️ Advertencia: La carpeta '{carpeta}' no existe o no es un directorio. Saltando...")
            continue

        print(f"📂 Explorando carpeta: {carpeta}")

        # Buscar todos los archivos .mseed en la carpeta actual
        patron = os.path.join(carpeta, "*.mseed")
        archivos = glob.glob(patron)

        if len(archivos) == 0:
            print(f"   └── No se encontraron archivos .mseed aquí.")
            continue

        # Procesar cada archivo encontrado en esta carpeta
        for archivo in archivos:
            try:
                # 1. Leer el archivo mseed
                st = obspy.read(archivo)

                # Unir trazas fragmentadas si es necesario
                st.merge(fill_value='interpolate')

                if len(st) == 0:
                    print(f"   ⚠️ Archivo vacío: {os.path.basename(archivo)}")
                    continue

                # 2. Obtener metadatos generales (usando la primera traza como referencia)
                tr_referencia = st[0]
                start_time_iso = str(tr_referencia.stats.starttime)

                # Construcción de la parte "meta"
                meta = {
                    "station": tr_referencia.stats.station,
                    "network": tr_referencia.stats.network,
                    "start_time": start_time_iso,
                    "sample_rate": 200,  # Valor fijo solicitado
                    "npts": 7001  # Valor fijo solicitado
                }

                # 3. Construcción de la parte "data"
                data_dict = {}

                for traza in st:
                    canal = traza.stats.channel
                    # Conversión a lista estándar de Python para JSON
                    data_dict[canal] = traza.data.tolist()

                # 4. Armar el payload final
                payload = {
                    "meta": meta,
                    "data": data_dict
                }

                # 5. Generar nombre de archivo de salida (.json)
                # Se guardará en la misma carpeta que el archivo original
                base_name = os.path.splitext(archivo)[0]
                nombre_json = f"{base_name}.json"

                # 6. Escribir el archivo JSON
                with open(nombre_json, 'w') as f:
                    json.dump(payload, f)

                print(f"   ✅ JSON Generado: {os.path.basename(nombre_json)}")

            except Exception as e:
                print(f"   ❌ Error procesando {os.path.basename(archivo)}: {e}")

        print("   └── Carpeta finalizada.\n")


if __name__ == "__main__":
    procesar_listado_carpetas()