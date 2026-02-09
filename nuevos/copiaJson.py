import os
import glob
import shutil

# ================= CONFIGURACIÓN =================
RUTA_BASE_DESTINO = "/home/lis/waves/imagenes/"

LISTA_DE_CARPETAS = [
    "./UCR_lis2025uumn", "./UCR_lis2025wjyk", "./UCR_lis2025wobp", "./UCR_lis2025wvmd", "./UCR_lis2025yrfu",
    "./UCR_lis2026akht", "./UCR_lis2026bhem", "./UCR_lis2026bxgo",
    "./UCR_lis2025uyll", "./UCR_lis2025wlsz", "./UCR_lis2025wqfg",
    "./UCR_lis2025wxfm", "./UCR_lis2025yrfw", "./UCR_lis2026autp",
    "./UCR_lis2026biqs", "./UCR_lis2026cczr", "./UCR_lis2025vbwz",
    "./UCR_lis2025wnzi", "./UCR_lis2025wslb", "./UCR_lis2025xyhk",
    "./UCR_lis2026agiv", "./UCR_lis2026bern", "./UCR_lis2026birv",
    "./UCR_lis2026cqti"
]


# =================================================

def organizar_jsons():
    print(f"--- Iniciando organización de {len(LISTA_DE_CARPETAS)} carpetas ---\n")

    for carpeta_origen in LISTA_DE_CARPETAS:
        # 1. Validar que la carpeta origen existe
        if not os.path.isdir(carpeta_origen):
            print(f"⚠️ La carpeta origen no existe: {carpeta_origen}")
            continue

        # 2. Obtener el nombre limpio de la carpeta (xx)
        # normpath quita el "./" inicial y posibles barras al final
        nombre_carpeta = os.path.basename(os.path.normpath(carpeta_origen))

        # 3. Construir la ruta de destino: /home/lis/waves/imagenes/xx
        ruta_destino = os.path.join(RUTA_BASE_DESTINO, nombre_carpeta)

        # 4. Crear la carpeta destino si no existe
        if not os.path.exists(ruta_destino):
            try:
                os.makedirs(ruta_destino)
                print(f"📂 Carpeta creada: {ruta_destino}")
            except OSError as e:
                print(f"❌ Error creando carpeta {ruta_destino}: {e}")
                continue

        # 5. Buscar archivos .json en la carpeta origen
        archivos_json = glob.glob(os.path.join(carpeta_origen, "*.json"))

        if not archivos_json:
            print(f"   └── {nombre_carpeta}: Sin archivos .json")
            continue

        print(f"   └── Procesando {nombre_carpeta} ({len(archivos_json)} archivos)...")

        # 6. Copiar/Mover los archivos
        contador = 0
        for archivo in archivos_json:
            try:
                # Opción A: COPIAR (Más seguro, conserva metadatos)
                shutil.copy2(archivo, ruta_destino)

                # Opción B: MOVER (Borra del origen). Descomenta la siguiente línea si prefieres mover:
                # shutil.move(archivo, ruta_destino)

                contador += 1
            except Exception as e:
                print(f"      ❌ Error con {os.path.basename(archivo)}: {e}")

        print(f"      ✅ {contador} archivos copiados exitosamente.")

    print("\n--- Proceso Finalizado ---")


if __name__ == "__main__":
    # Verificar permisos de escritura en el destino base antes de empezar
    if os.path.exists(os.path.dirname(RUTA_BASE_DESTINO)):
        organizar_jsons()
    else:
        print(f"❌ Error crítico: La ruta base {RUTA_BASE_DESTINO} (o su padre) no existe.")