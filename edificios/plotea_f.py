import json
import argparse
import matplotlib.pyplot as plt
from pathlib import Path


def graficar_componentes_json(ruta_archivo):
    """
    Lee un único archivo JSON que contiene múltiples componentes sísmicas
    y grafica sus espectros de Fourier en una sola figura.
    """
    archivo = Path(ruta_archivo)

    # Validación de existencia y formato
    if not archivo.is_file() or archivo.suffix != '.json':
        print(f"❌ Error: El archivo '{ruta_archivo}' no existe o no es un archivo .json válido.")
        return

    print(f"📊 Leyendo componentes del archivo: {archivo.name}...\n")

    try:
        with open(archivo, 'r') as f:
            datos_sismo = json.load(f)

        # Configuramos el tamaño de la figura
        plt.figure(figsize=(10, 6))

        # Iteramos sobre cada componente dentro del JSON
        # Se asume la estructura: {"HNZ": {"frecuencias_hz": [...], "amplitudes": [...]}, "HNN": {...}}
        for componente, valores in datos_sismo.items():
            # Verificamos que las llaves necesarias existan para evitar errores
            if "frecuencias_hz" in valores and "amplitudes" in valores:
                frecuencias = valores["frecuencias_hz"]
                amplitudes = valores["amplitudes"]

                # Graficamos la línea de esta componente
                plt.plot(frecuencias, amplitudes, label=f"Componente {componente}", alpha=0.8, linewidth=1.5)
            else:
                print(f"⚠️ Advertencia: La componente '{componente}' no tiene el formato esperado. Omitiendo...")

        # ==========================================
        # Configuración visual del gráfico
        # ==========================================
        plt.title(f"Espectro de Fourier - {archivo.stem}", fontsize=14, fontweight='bold')
        plt.xlabel("Frecuencia (Hz)", fontsize=12)
        plt.ylabel("Amplitud de Fourier (m/s)", fontsize=12)

        # Escala logarítmica (estándar en sismología)
        plt.xscale('log')
        plt.yscale('log')

        # Límites del eje X (ajustable según tu necesidad)
        plt.xlim(0.1, 50)

        # Cuadrícula y leyenda
        plt.grid(True, which="both", ls="--", linewidth=0.5, alpha=0.7)
        plt.legend(loc='upper right')
        plt.tight_layout()

        # ==========================================
        # Salida
        # ==========================================
        # Guarda la imagen en la misma carpeta que el archivo JSON original
        ruta_imagen = archivo.parent / f"{archivo.stem}_grafico.png"
        plt.savefig(ruta_imagen, dpi=300)
        print(f"🖼️ Gráfico de componentes guardado en: {ruta_imagen}")

        # Mostrar la ventana interactiva
        plt.show()

    except Exception as e:
        print(f"❌ Error crítico al procesar el archivo: {e}")


# ==========================================
# Configuración de parámetros por consola
# ==========================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Grafica todas las componentes de un espectro de Fourier desde un único archivo JSON.")
    parser.add_argument("archivo", type=str, help="Ruta absoluta o relativa al archivo JSON a graficar")

    args = parser.parse_args()
    graficar_componentes_json(args.archivo)