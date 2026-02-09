import os
import glob
import pandas as pd

# ================= CONFIGURACIÓN =================
# Carpeta donde están tus CSV originales (./ significa la carpeta actual)
CARPETA_ENTRADA = "./"

# Carpeta donde se guardarán los modificados
CARPETA_SALIDA = "./modificados"

# Factor de multiplicación
FACTOR = 1.25


# =================================================

def procesar_csvs():
    # Crear carpeta de salida si no existe
    if not os.path.exists(CARPETA_SALIDA):
        os.makedirs(CARPETA_SALIDA)
        print(f"📂 Carpeta creada: {CARPETA_SALIDA}")

    # Buscar todos los archivos .csv
    archivos = glob.glob(os.path.join(CARPETA_ENTRADA, "*.csv"))

    print(f"--- Encontrados {len(archivos)} archivos CSV ---")

    for archivo in archivos:
        nombre_archivo = os.path.basename(archivo)

        # Evitar procesar archivos que ya estén en la carpeta de salida (si corres el script ahí mismo)
        if "modificados" in archivo:
            continue

        try:
            # Leer el CSV
            df = pd.read_csv(archivo)

            # Buscar la columna correcta (Mayúscula o minúscula)
            columna_objetivo = None
            if "Aceleracion" in df.columns:
                columna_objetivo = "Aceleracion"
            elif "aceleracion" in df.columns:
                columna_objetivo = "aceleracion"

            if columna_objetivo:
                # --- OPERACIÓN MATEMÁTICA ---
                df[columna_objetivo] = df[columna_objetivo] * FACTOR

                # Guardar el nuevo archivo
                ruta_guardado = os.path.join(CARPETA_SALIDA, nombre_archivo)
                df.to_csv(ruta_guardado, index=False)
                print(f"✅ Procesado: {nombre_archivo} -> Guardado en modificados/")
            else:
                print(f"⚠️ Saltado: {nombre_archivo} (No tiene columna 'Aceleracion')")

        except Exception as e:
            print(f"❌ Error en {nombre_archivo}: {e}")

    print("\n--- Proceso Finalizado ---")


if __name__ == "__main__":
    # Verificar si pandas está instalado
    try:
        import pandas

        procesar_csvs()
    except ImportError:
        print("❌ Error: Necesitas instalar pandas.")
        print("   Ejecuta: pip install pandas")