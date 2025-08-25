#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import sys
from getpass import getpass
import pymysql



def column_exists(cursor, schema, table, column):
    """
    Verifica si una columna existe en una tabla del esquema indicado.
    """
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME   = %s
          AND COLUMN_NAME  = %s
        """,
        (schema, table, column)
    )
    (count,) = cursor.fetchone()
    return count > 0


def normalize(value):
    """
    Convierte cadenas vacías en None; recorta espacios.
    """
    if value is None:
        return None
    v = str(value).strip()
    return v if v != "" else None


def read_csv(csv_path):
    """
    Lee el CSV y produce una lista de dicts con los campos requeridos.
    Exige encabezados: hostid, hostname, lat, lon, ip
    """
    rows = []
    with open(csv_path, "r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        required = {"hostid", "hostname", "lat", "lon", "ip"}
        missing = required - set(h.lower() for h in reader.fieldnames or [])
        # Intentamos ser tolerantes con mayúsculas; mapeamos headers a lower
        header_map = {h.lower(): h for h in (reader.fieldnames or [])}

        if missing:
            raise ValueError(
                f"El CSV no contiene las columnas requeridas: {', '.join(sorted(missing))}"
            )

        for raw in reader:
            row = {
                "hostid": normalize(raw[header_map["hostid"]]),
                "hostname": normalize(raw[header_map["hostname"]]),
                "lat": normalize(raw[header_map["lat"]]),
                "lon": normalize(raw[header_map["lon"]]),
                "ip": normalize(raw[header_map["ip"]]),
            }
            # Validación mínima de hostid e ip (opcional)
            if row["hostid"] is None:
                raise ValueError("Se encontró una fila con 'hostid' vacío.")
            rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Carga/actualiza inventario e interfaces en Zabbix a partir de un CSV "
            "(hostid, hostname, lat, lon, ip)."
        )
    )
    parser.add_argument("--csv", required=True, help="Ruta al archivo CSV de entrada.")
    parser.add_argument("--db-host", default="163.178.101.124", help="Host de MySQL.")
    parser.add_argument("--db-port", type=int, default=3306, help="Puerto de MySQL.")
    parser.add_argument("--db-user", default="root", help="Usuario de MySQL.")
    parser.add_argument("--db-pass", default="lisUcr01_124", help="Password de MySQL (si se omite, se solicitará).")
    parser.add_argument("--db-name", default="zabbix", help="Nombre de la base de datos (por defecto: zabbix).")

    args = parser.parse_args()

    if not args.db_pass:
        args.db_pass = getpass("Password de MySQL: ")

    # 1) Leer CSV
    try:
        rows = read_csv(args.csv)
        if not rows:
            print("El CSV no contiene filas para procesar.", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Error al leer el CSV: {e}", file=sys.stderr)
        sys.exit(1)

    # 2) Conexión a MySQL
    try:
        cnx = pymysql.connect(
            host=args.db_host,
            port=args.db_port,
            user=args.db_user,
            password=args.db_pass,
            database=args.db_name,
            autocommit=False,
        )
    except Exception as err:

        print(f"La base de datos '{args.db_name}' no existe.", file=sys.stderr)
        print(f"Error de conexión a MySQL: {err}", file=sys.stderr)
        sys.exit(1)

    try:
        cur = cnx.cursor()

        # 3) Descubrir si host_inventory tiene la columna inventory_mode
        inv_mode_in_host_inventory = column_exists(
            cur, args.db_name, "host_inventory", "inventory_mode"
        )

        # Preparar sentencias
        if inv_mode_in_host_inventory:
            insert_inv_sql = (
                "INSERT INTO host_inventory (hostid, location_lat, location_lon, inventory_mode) "
                "VALUES (%s, %s, %s, 0) "
                "ON DUPLICATE KEY UPDATE "
                "location_lat=VALUES(location_lat), "
                "location_lon=VALUES(location_lon), "
                "inventory_mode=VALUES(inventory_mode)"
            )
        else:
            insert_inv_sql = (
                "INSERT INTO host_inventory (hostid, location_lat, location_lon) "
                "VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE "
                "location_lat=VALUES(location_lat), "
                "location_lon=VALUES(location_lon)"
            )
            # Si no existe la columna en host_inventory, actualizaremos hosts.inventory_mode=0
            update_hosts_inv_mode_sql = (
                "UPDATE hosts SET inventory_mode=0 WHERE hostid=%s"
            )

        update_interface_sql = "UPDATE interface SET ip=%s WHERE hostid=%s"

        # 4) Ejecutar dentro de una transacción
        for i, r in enumerate(rows, start=1):
            hostid = r["hostid"]
            lat = r["lat"]
            lon = r["lon"]
            ip = r["ip"]

            # a) Insert/Update host_inventory
            cur.execute(insert_inv_sql, (hostid, lat, lon))

            # b) Si inventory_mode no está en host_inventory, setear en hosts
            if not inv_mode_in_host_inventory:
                cur.execute(update_hosts_inv_mode_sql, (hostid,))

            # c) Update interface.ip (para todas las interfaces de ese hostid)
            if ip is not None:
                cur.execute(update_interface_sql, (ip, hostid))

        # Confirmar cambios
        cnx.commit()
        print(
            f"Proceso finalizado correctamente. Filas procesadas: {len(rows)}. "
            f"{'Se estableció inventory_mode=0 en host_inventory.' if inv_mode_in_host_inventory else 'Se estableció inventory_mode=0 en hosts.'}"
        )


    except Exception as ex:
        cnx.rollback()
        print(f"Error inesperado: {ex}; transacción revertida.", file=sys.stderr)
        sys.exit(1)
    finally:
        try:
            cur.close()
        except Exception:
            pass
        cnx.close()


if __name__ == "__main__":
    main()
