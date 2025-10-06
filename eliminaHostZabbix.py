#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elimina una lista de hosts en Zabbix usando API Token (Bearer).
Evita enviar la cabecera Authorization en métodos públicos como apiinfo.version.
"""

import requests
import json
import sys
from typing import List

# === CONFIGURACIÓN ===
ZABBIX_API_URL = "https://zabbix.lis.ucr.ac.cr/api_jsonrpc.php"
ZABBIX_API_TOKEN = "ed931eb1157f82fcdbc63f9f208794bbfbb5a92b308c1d2d7aa2616df9923faf"  # <- reemplazar por tu token
HOSTS_FILE = "listado_host_borrar.txt"

# Si el certificado es autofirmado y no quieres validación SSL (no recomendado):
VERIFY_SSL = True

BASE_HEADERS = {
    "Content-Type": "application/json-rpc",
    "User-Agent": "ZabbixHostDelete/2.1",
}

def zbx_call(method: str, params=None, with_auth=True) -> dict:
    """
    Llama a la API JSON-RPC de Zabbix.
    - Si with_auth=False, no incluye la cabecera Authorization.
    """
    headers = BASE_HEADERS.copy()
    if with_auth:
        headers["Authorization"] = f"Bearer {ZABBIX_API_TOKEN}"

    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params if params is not None else {},
        "id": 1,
    }

    response = requests.post(
        ZABBIX_API_URL,
        headers=headers,
        data=json.dumps(payload),
        verify=VERIFY_SSL,
    )

    try:
        result = response.json()
    except Exception:
        raise RuntimeError(f"Respuesta no válida del servidor: {response.text[:400]}")

    if "error" in result:
        err = result["error"]
        raise RuntimeError(f"Error {err['code']} - {err['message']}: {err['data']}")

    return result["result"]

def leer_hosts(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def main():
    try:
        # 1️⃣ Llamada pública sin autenticación
        version = zbx_call("apiinfo.version", {}, with_auth=False)
        print(f"[*] Conectado a Zabbix API (versión {version})")

        # 2️⃣ Cargar lista de hosts
        try:
            hostnames = leer_hosts(HOSTS_FILE)
        except FileNotFoundError:
            print(f"[x] No se encontró el archivo {HOSTS_FILE}")
            sys.exit(1)

        if not hostnames:
            print("[x] El archivo está vacío.")
            sys.exit(1)

        print(f"[*] {len(hostnames)} host(s) leídos desde {HOSTS_FILE}.")

        eliminados, no_encontrados = [], []

        # 3️⃣ Buscar y eliminar hosts
        for hn in hostnames:
            print(f"\n[*] Buscando host: {hn}")
            result = zbx_call(
                "host.get",
                {"output": ["hostid", "host"], "filter": {"host": [hn]}},
                with_auth=True,
            )

            if not result:
                print(f"[-] No se encontró el host '{hn}'.")
                no_encontrados.append(hn)
                continue

            host_ids = [h["hostid"] for h in result]
            print(f"[+] Encontrado: {host_ids}, eliminando...")

            zbx_call("host.delete", host_ids, with_auth=True)
            print(f"[✔] Host '{hn}' eliminado.")
            eliminados.append(hn)

        # 4️⃣ Resumen
        print("\n===== RESUMEN =====")
        print(f"Eliminados: {len(eliminados)}")
        if eliminados:
            print(" - " + "\n - ".join(eliminados))
        print(f"No encontrados: {len(no_encontrados)}")
        if no_encontrados:
            print(" - " + "\n - ".join(no_encontrados))

    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
