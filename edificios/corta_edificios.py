#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extracción de tramos MiniSEED desde un archivo SDS local y conversión a aceleración,
parametrizado por fecha de inicio (UTC) y nombre de evento.

USO:
    python extract_acc_sds.py --start "2025-09-26T12:34:56" --event "UCR_lis2025xxxx" \
        [--sds ./SDS] [--inventory ./inventory_full_fdns.xml] [--out ./out_mseed]
"""

import argparse
import os
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Tuple

from obspy import UTCDateTime, read_inventory, Stream
from obspy.clients.filesystem.sds import Client as SDSClient
#ruta al directorio seiscomp
SDS_ROOT = "/home/lis/seiscomp/var/lib/archive/"  # Ruta al SDS de seiscomp
Inventory= "/home/lis/waves/inventory_Estructuras.xml" # Ruta al inventario

# --------------------------- Utilidades --------------------------------- #



def estaciones_con_HN(inventory) -> List[Tuple[str, str, str]]:
    """
    Devuelve tuplas (network, station, location) con los tres canales HNE/HNN/HNZ
    definidos en el inventario.
    """
    triples = set()
    for net in inventory.networks:
        for sta in net.stations:
            chans_por_loc: Dict[str, set] = {}
            for cha in sta.channels:
                code = cha.code or ""
                loc = cha.location_code or ""
                if code in {"HNE", "HNN", "HNZ"}:
                    chans_por_loc.setdefault(loc, set()).add(code)
            for loc, cods in chans_por_loc.items():
                if {"HNE", "HNN", "HNZ"}.issubset(cods):
                    triples.add((net.code, sta.code, loc))
    return sorted(triples)

def leer_y_convertir_a_acc_cmss(client: SDSClient, inv, net: str, sta: str, loc: str,
                                t0: UTCDateTime, t1: UTCDateTime) -> Stream:
    """
    Lee HNE/HNN/HNZ del SDS y remueve respuesta para obtener aceleración en cm/s^2.
    """
    loc_sel = loc if loc else "*"
    st = client.get_waveforms(net, sta, loc_sel, "HN?", t0, t1, merge=1)
    if len(st) == 0:
        return Stream()

    # Filtrar exactamente HNE/HNN/HNZ y ordenar
    st = st.select(channel="HNE") + st.select(channel="HNN") + st.select(channel="HNZ")
    if len(st) == 0:
        return Stream()

    out = Stream()
    for tr in st:
        inv_sel = inv.select(network=net, station=sta, location=tr.stats.location, channel=tr.stats.channel)
        tr_acc = tr.copy().remove_response(inventory=inv_sel, output="ACC", zero_mean=True, taper=True)
        tr_acc.data = tr_acc.data * 100.0  # m/s^2 -> cm/s^2
        if not hasattr(tr_acc.stats, "processing"):
            tr_acc.stats.processing = []
        tr_acc.stats.processing.append("Converted to acceleration in cm/s^2 (from ACC m/s^2 * 100).")
        tr_acc.stats.units = "cm/s^2"
        out += tr_acc
    return out

def escribir_mseed_por_estacion(st: Stream, out_dir: Path, event_name: str, net: str, sta: str, loc: str, date: str):
    """
    Escribe un archivo MiniSEED por estación con los 3 canales presentes.
    Nombre: {event}_{NET}.{STA}.{LOC or --}.mseed
    """
    if len(st) == 0:
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    loc_str = loc if loc else "--"
    fname = f"{net}_{sta}_{date}.mseed"
    path = out_dir / fname

    ordered = Stream()
    for ch in ("HNE", "HNN", "HNZ"):
        ordered += st.select(channel=ch)
    if len(ordered) == 0:
        ordered = st
    ordered.write(str(path), format="MSEED")

# --------------------------- Programa principal -------------------------- #

def main():
    parser = argparse.ArgumentParser(
        description="Extraer tramos HNE/HNN/HNZ de un SDS local y convertir a aceleración (cm/s^2)."
    )
    parser.add_argument("--start", required=True,
                        help="Fecha/hora de inicio en UTC (p. ej., 2025-09-26T12:34:56).")
    parser.add_argument("--event", required=True, help="Nombre/identificador del evento.")
    parser.add_argument("--sds", default=None,
                        help="Ruta al directorio SDS. Por defecto, '<dir_del_script>/SDS'.")
    parser.add_argument("--inventory", default=None,
                        help="Ruta al StationXML. Por defecto se autodetecta en el directorio del script.")
    parser.add_argument("--out", default=None,
                        help="Directorio de salida de los MiniSEED. Por defecto '<dir_del_script>/out_mseed'.")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent

    # Ventana solicitada: inicio ± 3 minutos
    start = UTCDateTime(args.start)
    t0 = start - 3 * 60
    t1 = start + 3 * 60

    sds_root = SDS_ROOT
    OUT_DIR = Path(f"/home/lis/waves/eventos/{args.event}/")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    logfile = OUT_DIR / f"{args.event}.log"
    logging.basicConfig(
        filename=logfile,
        level=logging.INFO,  # Nivel mínimo que se registrará
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    out_dir = OUT_DIR
    inv_path = Inventory
    inv = read_inventory(str(inv_path))

    client = SDSClient(str(sds_root))
    triples = estaciones_con_HN(inv)
    if not triples:
        logging.error("No estaciones con HN/HNZ")
        raise RuntimeError("El inventario no contiene estaciones con los canales HNE/HNN/HNZ.")

    for net, sta, loc in triples:
        st_acc = leer_y_convertir_a_acc_cmss(client, inv, net, sta, loc, t0, t1)
        if len(st_acc):
            escribir_mseed_por_estacion(st_acc, out_dir, args.event, net, sta, loc,start.strftime("%Y%m%dT%H%M%S"))

    logging.info(f"Finalizado. Salida en: {out_dir}")
    logging.info("Iniciando procesamiento...")
    result = subprocess.Popen(
        ["python3","/home/lis/waves/scripts/procesa_edificio.py", "--start", args.start, "--event",
         args.event])
    logging.info(f"Resultado de proceso... {result}")

if __name__ == "__main__":
    main()
