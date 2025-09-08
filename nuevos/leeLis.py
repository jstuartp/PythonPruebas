#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lector y graficador de archivos .LIS con tres componentes (N00E, UPDO, N90E).

Uso:
    python lis_plot.py /ruta/al/archivo.LIS

Comportamiento:
- Extrae todos los encabezados antes de la línea "=================DATA IN GALS=================",
  guardando pares "Etiqueta:" -> "valor" en un dict.
- Detecta la fila de nombres de columnas (p.ej. "N00E   UPDO   N90E").
- Lee exactamente 'Number of points' filas numéricas.
- Construye el eje X con fs = 200 Hz (dt = 1/200 s) iniciando en t = 0.
- Grafica las tres series en una figura (subplots) y guarda un PNG junto al archivo .LIS.

Requisitos:
- Python 3.8+
- numpy, matplotlib
"""

import sys
import os
import io
import re
from typing import Dict, List, Tuple

import numpy as np
import matplotlib.pyplot as plt


FS_HZ = 200.0  # frecuencia de muestreo fija, 200 muestras/segundo


def parse_lis(path: str) -> Tuple[Dict[str, str], List[str], np.ndarray]:
    """
    Parsea un archivo .LIS con estructura:
    - Encabezados de tipo "Clave:   Valor"
    - Separador "=================DATA IN GALS================="
    - Línea de nombres de columnas (esperadas 3)
    - Filas de datos en notación científica, tamaño = Number of points

    Retorna:
        headers: dict con "Clave:" -> "valor" (la clave incluye el ':', tal como viene)
        colnames: lista con los nombres de columnas detectados (p.ej. ["N00E","UPDO","N90E"])
        data: arreglo numpy shape (N, 3) con los datos en el orden de colnames
    """
    # Lectura segura con fallback de codificación
    with open(path, "r", errors="ignore") as f:
        lines = f.readlines()

    headers: Dict[str, str] = {}
    data_section_idx = None
    number_of_points = None

    # 1) Recorrer encabezado hasta “DATA IN GALS”
    for i, raw in enumerate(lines):
        line = raw.rstrip("\n")
        if "=================DATA IN GALS" in line:
            data_section_idx = i
            break
        # Capturar pares "Clave: Valor" (permitiendo espacios variables)
        if ":" in line:
            # conservar la clave con ':' final (según el ejemplo del usuario)
            key_part, value_part = line.split(":", 1)
            key = key_part.strip() + ":"
            value = value_part.strip()
            if key and value:
                headers[key] = value

        # Intentar leer "Number of points"
        if line.strip().lower().startswith("number of points"):
            # admite "Number of points:   72001"
            m = re.search(r"number of points\s*:\s*([0-9]+)", line, flags=re.IGNORECASE)
            if m:
                number_of_points = int(m.group(1))

    if data_section_idx is None:
        raise ValueError("No se encontró la sección 'DATA IN GALS' en el archivo.")

    if number_of_points is None:
        raise ValueError("No se encontró el encabezado 'Number of points' en el archivo.")

    # 2) La línea siguiente no vacía debe contener los nombres de columnas
    col_header_idx = None
    for j in range(data_section_idx + 1, len(lines)):
        cand = lines[j].strip()
        if cand:
            col_header_idx = j
            break
    if col_header_idx is None:
        raise ValueError("No se encontró la línea de nombres de columnas después de 'DATA IN GALS'.")

    colnames = lines[col_header_idx].strip().split()
    if len(colnames) != 3:
        raise ValueError(f"Se esperaban 3 columnas, pero se detectaron {len(colnames)}: {colnames}")

    # 3) A partir de la línea siguiente se esperan 'number_of_points' filas con 3 valores cada una
    data_start = col_header_idx + 1
    data_vals: List[List[float]] = []
    # Expresión para detectar tres números (admite -.123E-10, 0.123E+05, etc.)
    num_re = re.compile(r"([+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+\-]?\d+)?)(?:\s+|$)")

    line_idx = data_start
    while len(data_vals) < number_of_points and line_idx < len(lines):
        row = lines[line_idx].strip()
        line_idx += 1
        if not row:
            continue
        # Extraer números por regex (más robusto que split ante espacios irregulares)
        nums = [float(m.group(1)) for m in num_re.finditer(row)]
        if len(nums) == 3:
            data_vals.append(nums)
        # Ignorar líneas que no tengan 3 números (p.ej., separadores accidentales)
    if len(data_vals) != number_of_points:
        # Tolerancia: si el archivo termina antes, se recorta; si sobran, se trunca.
        if len(data_vals) < number_of_points:
            # Puede tratarse de un archivo cortado; se continúa con lo leído.
            pass
        else:
            data_vals = data_vals[:number_of_points]

    data = np.asarray(data_vals, dtype=float)  # shape (N, 3)
    return headers, colnames, data


def build_time_axis(n_samples: int, fs_hz: float = FS_HZ) -> np.ndarray:
    """
    Construye el eje temporal desde 0 con paso 1/fs_hz, longitud n_samples.
    """
    return np.arange(n_samples, dtype=float) / fs_hz


def plot_components(time_s: np.ndarray, data: np.ndarray, colnames: List[str], headers: Dict[str, str], out_png: str) -> None:
    """
    Genera una figura con tres subgráficos (uno por componente) y la guarda en 'out_png'.
    """
    if data.shape[1] != 3:
        raise ValueError("Se esperaban exactamente 3 columnas de datos.")

    station = headers.get("Station Code:", "")
    record_name = headers.get("Record name:", "")
    magnitude = headers.get("Event Magnitude (Mw):", "")
    date = headers.get("Event Date:", "")

    fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True)
    fig.suptitle(f"Registro {record_name} | Estación {station} | {date} | Mw {magnitude}".strip(), fontsize=12)

    for i in range(3):
        ax = axes[i]
        ax.plot(time_s, data[:, i], linewidth=0.8)
        ax.set_ylabel(f"{colnames[i]} (gal)")
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.6)

    axes[-1].set_xlabel("Tiempo (s)")
    plt.tight_layout(rect=[0, 0.02, 1, 0.95])

    # Guardar figura
    plt.savefig(out_png, dpi=150)
    plt.close(fig)


def main():
    if len(sys.argv) != 2:
        print("Uso: python lis_plot.py /ruta/al/archivo.LIS")
        sys.exit(1)

    in_path = sys.argv[1]
    if not os.path.isfile(in_path):
        print(f"Error: no se encontró el archivo: {in_path}")
        sys.exit(1)

    headers, colnames, data = parse_lis(in_path)

    # Validaciones mínimas
    if data.size == 0:
        print("No se pudieron leer datos numéricos del archivo.")
        sys.exit(1)

    # Eje temporal a 200 Hz
    t = build_time_axis(data.shape[0], FS_HZ)

    # Ruta de salida para el PNG
    base, _ = os.path.splitext(in_path)
    out_png = base + "_plot.png"

    # Graficar
    plot_components(t, data, colnames, headers, out_png)

    # Salida informativa (encabezados y archivo generado)
    print("Encabezados leídos (clave: valor):")
    for k, v in headers.items():
        print(f"  {k} {v}")
    print(f"\nColumnas detectadas: {colnames}")
    print(f"Muestras por columna: {data.shape[0]}")
    print(f"Frecuencia de muestreo asumida: {FS_HZ} Hz")
    print(f"Gráfico guardado en: {out_png}")


if __name__ == "__main__":
    main()
