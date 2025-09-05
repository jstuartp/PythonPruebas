#!/usr/bin/env seiscomp-python
# -*- coding: utf-8 -*-
# Create a reusable Python script that writes a LIS-style file matching the provided template.

from __future__ import annotations
import argparse
import datetime as dt
import math
from typing import Dict, List

import numpy as np
from obspy import read, Stream, Trace


# ------------------------- Formateo numérico estilo Fortran ------------------
def fortran_like(value: float) -> str:
    """
    Devuelve una cadena con formato similar al observado en el archivo de ejemplo,
    por ejemplo:
      0.10106273E-02
     -.34001481E-04
    Es decir, mantisa en [0,1), 8 decimales, exponente con signo y dos dígitos,
    y omitiendo el '0' tras el signo en valores negativos ( -.xxx... ).
    Longitud final: 14 caracteres.
    """
    #if value == 0 or np.isclose(value, 0.0):
    if value == 0:
        return "0.00000000E+00"
    sign = "-" if value < 0 else ""
    v = abs(float(value))
    exp = int(math.floor(math.log10(v)))
    mant = v / (10 ** exp)
    mant /= 10.0
    exp += 1
    s = f"{sign}{mant:.8f}E{exp:+03d}"
    if sign and s.startswith("-0."):
        s = "-" + s[2:]
    return s  # 14 caracteres


# ------------------------- Escritura de archivo LIS -------------------------
HEADER_TOP = [
    "Agency Lab. de Ing. Sismica (LIS-UCR)         ",
    # La línea "Processed on ..." se genera dinámicamente con la fecha actual
    # Líneas libres definidas por el usuario: 'Epicenter', 'Station name'
    "==============================================",
]

HEADER_FIELDS = [
    ("Record name:", "record_name"),
    ("Event Date:", "event_date"),
    ("Event Latitude:", "event_lat"),
    ("Event Longitude:", "event_lon"),
    ("Event Depth (km):", "event_depth"),
    ("Event Magnitude (Mw):", "event_mw"),
    ("Source type:", "source_type"),
    ("Station Code:", "station_code"),
    ("Instrument type:", "instrument_type"),
    ("Serial number:", "serial_number"),
    ("Station Latitude:", "station_lat"),
    ("Station Longitude:", "station_lon"),
    ("Station Elevation (m):", "station_elev"),
    ("Soil type (ATC 1985):", "soil_type"),
    ("Site condition:", "site_condition"),
    ("Epicentral Dist. (km):", "epicentral_km"),
    ("Hypocentral Dist. (km):", "hypocentral_km"),
    ("Azimuth (Ep.to.St):", "azimuth"),
    ("Delta t:", "delta_t"),
    ("PGA-N00E:", "pga_n00e"),
    ("PGA-UPDO:", "pga_updo"),
    ("PGA-N90E:", "pga_n90e"),
    ("MIN. FILT. FREQ:", "min_filt_freq"),
    ("MAX. FILT. FREQ:", "max_filt_freq"),
    ("Number of points:", "n_points"),
]

def format_header_line(label: str, value: str) -> str:
    """
    Ajusta el espaciado para alinear visualmente valores a la derecha, de modo
    similar al archivo de ejemplo. Se usa una columna destino estándar.
    """
    # Columna donde inicia el valor (1-indexed aproximado al ejemplo)
    VALUE_COL = 40
    left = f"{label}"
    spaces = max(1, VALUE_COL - len(left))
    return f"{left}{' ' * spaces}{value:<40}"


def normalize_metadata(md: Dict) -> Dict:
    md = dict(md) if md else {}
    # Campos opcionales con valores por defecto
    md.setdefault("epicenter_text", "")
    md.setdefault("station_name", "")
    # Derivados o por defecto
    md.setdefault("min_filt_freq", "")
    md.setdefault("max_filt_freq", "")
    return md


def stream_to_ordered_arrays(st: Stream, order: List[str]) -> np.ndarray:
    """Devuelve arreglo (n, 3) con canales en el orden solicitado."""
    # Selección estricta por canal
    arrs = []
    nsamples = []
    t0s = []
    for ch in order:
        tr: Trace = st.select(channel=ch)[0]
        arrs.append(tr.data.astype(np.float64))
        nsamples.append(tr.stats.npts)
        t0s.append(tr.stats.starttime.timestamp)
    # Asegurar misma longitud: recortamos al mínimo común
    n = int(min(nsamples))
    arrs = [a[:n] for a in arrs]
    return np.column_stack(arrs)


def maybe_convert_units(data: np.ndarray, units: str) -> np.ndarray:
    """
    Convierte los datos a gals si 'units' es 'mps2' o 'm/s^2'.
    1 gal = 1 cm/s^2 = 0.01 m/s^2  =>  gal = m/s^2 * 100
    """
    u = (units or "").lower().replace(" ", "")
    if u in {"mps2", "m/s^2", "m/s2"}:
        return data * 100.0
    return data


def compute_delta_t_and_npts(st: Stream) -> (float, int):
    # Suponemos la misma Fs para las tres trazas, tomamos la primera
    tr = st[0]
    fs = float(tr.stats.sampling_rate)
    dt = 1.0 / fs if fs else 0.0
    npts = int(min(t.stats.npts for t in st))
    return dt, npts


def main():
    ap = argparse.ArgumentParser(description="Escribe archivo estilo LIS con HNE, HNZ, HNN en GALS.")
    ap.add_argument("--mseed", required=True, help="Ruta al archivo .mseed de entrada")
    ap.add_argument("--out", required=True, help="Ruta de salida .lis")
    # Encabezados libres
    ap.add_argument("--epicenter", default="", help="Texto libre para 'Epicenter ...'")
    ap.add_argument("--station-name", default="", help="Texto libre para 'Station name ...'")
    # Campos del encabezado (valores pueden ser calculados/omitidos)
    ap.add_argument("--record-name", default="", help="Record name")
    ap.add_argument("--event-date", default="", help="YYYY/MM/DD HH:MM")
    ap.add_argument("--event-lat", type=float, default=None)
    ap.add_argument("--event-lon", type=float, default=None)
    ap.add_argument("--event-depth", type=float, default=None)
    ap.add_argument("--event-mw", type=float, default=None)
    ap.add_argument("--source-type", default="INDEF")
    ap.add_argument("--station-code", default="")
    ap.add_argument("--instrument-type", default="")
    ap.add_argument("--serial", default="")
    ap.add_argument("--station-lat", type=float, default=None)
    ap.add_argument("--station-lon", type=float, default=None)
    ap.add_argument("--station-elev", type=float, default=None)
    ap.add_argument("--soil-type", default="")
    ap.add_argument("--site-condition", default="")
    ap.add_argument("--epicentral-km", type=float, default=None)
    ap.add_argument("--hypocentral-km", type=float, default=None)
    ap.add_argument("--azimuth", type=float, default=None)
    ap.add_argument("--min-freq", type=float, default="0.05")
    ap.add_argument("--max-freq", type=float, default="25")
    ap.add_argument("--pga-n00e", type=float, default=None)
    ap.add_argument("--pga-updo", type=float, default=None)
    ap.add_argument("--pga-n90e", type=float, default=None)
    ap.add_argument("--column-names", nargs=3, default=["N00E", "UPDO", "N90E"], metavar=("C1", "C2", "C3"))
    ap.add_argument("--units", default="mps2", help="Unidades de los datos del .mseed: mps2|m/s^2|gal")
    args = ap.parse_args()

    # Leer stream
    st: Stream = read(args.mseed)
    # Orden requerido y extracción
    order = ["HNE", "HNZ", "HNN"]
    data = stream_to_ordered_arrays(st, order=order)
    #data = maybe_convert_units(data, args.units)

    # Delta t y npts (pueden sobrescribirse por CLI si se desea)
    delta_t, npts = compute_delta_t_and_npts(st)

    # Construcción de metadatos
    md = normalize_metadata({
        "record_name": args.record_name or (args.out.split("/")[-1]),
        "event_date": args.event_date,
        "event_lat": f"{args.event_lat:.4f}" if args.event_lat is not None else "",
        "event_lon": f"{args.event_lon:.4f}" if args.event_lon is not None else "",
        "event_depth": f"{args.event_depth:.4f}" if args.event_depth is not None else "",
        "event_mw": f"{args.event_mw:.4f}" if args.event_mw is not None else "",
        "source_type": args.source_type,
        "station_code": args.station_code,
        "instrument_type": args.instrument_type,
        "serial_number": args.serial,
        "station_lat": f"{args.station_lat:.4f}" if args.station_lat is not None else "",
        "station_lon": f"{args.station_lon:.4f}" if args.station_lon is not None else "",
        "station_elev": f"{args.station_elev:.4f}" if args.station_elev is not None else "",
        "soil_type": args.soil_type,
        "site_condition": args.site_condition,
        "epicentral_km": f"{args.epicentral_km:.4f}" if args.epicentral_km is not None else "",
        "hypocentral_km": f"{args.hypocentral_km:.4f}" if args.hypocentral_km is not None else "",
        "azimuth": f"{args.azimuth:.4f}" if args.azimuth is not None else "",
        "delta_t": f"{delta_t:.4f}",
        "min_filt_freq": f"{args.min_freq:.4f}" if args.min_freq is not None else "",
        "max_filt_freq": f"{args.max_freq:.4f}" if args.max_freq is not None else "",
        "n_points": f"{npts:d}",
    })

    # PGAs (si fueron pasados)
    if args.pga_n00e is not None:
        md["pga_n00e"] = f"{args.pga_n00e:.4f}"
    if args.pga_updo is not None:
        md["pga_updo"] = f"{args.pga_updo:.4f}"
    if args.pga_n90e is not None:
        md["pga_n90e"] = f"{args.pga_n90e:.4f}"

    # Cabecera textual libre
    epicenter_text = args.epicenter or ""
    station_name_text = args.station_name or ""

    # Escritura
    with open(args.out, "w", encoding="utf-8") as f:
        # Encabezado superior
        f.write(HEADER_TOP[0] + "\n")
        f.write(f"Processed on {dt.datetime.now().strftime('%a %b %d %H:%M:%S %Y')}\n")
        if epicenter_text:
            f.write(f"Epicenter {epicenter_text}\n")
        else:
            f.write("Epicenter \n")
        if station_name_text:
            f.write(f"Station name {station_name_text:<30}\n")
        else:
            f.write("Station name \n")
        f.write(HEADER_TOP[1] + "\n")  # línea de ======

        # Campos con alineación
        for label, key in HEADER_FIELDS:
            val = md.get(key, "")
            f.write(format_header_line(label, val) + "\n")

        # Leyendas de suelo y condición, como en el ejemplo
        f.write("S1-Rock    S2-Hard    S3-Soft    S4-Very soft\n")
        f.write("FFD-Free_field BDU-Buildng_up BDG-Buildng_down\n")

        # Sección de datos
        f.write("=================DATA IN GALS=================\n")
        # Encabezados de columnas (alineados visualmente a los datos)
        # Mantener separación equivalente (2 espacios entre columnas)
        hdr = f"{args.column_names[0]:>5}             {args.column_names[1]:>4}            {args.column_names[2]:>4}\n"
        f.write(hdr)

        # Filas de datos
        for row in data:
            c1, c2, c3 = (fortran_like(float(row[0])),
                          fortran_like(float(row[1])),
                          fortran_like(float(row[2])))
            f.write(f"{c1}  {c2}  {c3}\n")  # 2 espacios entre columnas
            #f.write(f"{row[0]}  {row[1]}  {row[2]}\n")  # 2 espacios entre columnas

    print(f"Archivo escrito en: {args.out}")


if __name__ == "__main__":
    main()
