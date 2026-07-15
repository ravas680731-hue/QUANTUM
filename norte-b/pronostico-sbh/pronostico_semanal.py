#!/usr/bin/env python3
"""pronostico_semanal.py — entrypoint de la corrida semanal (SBH · QUANTUM Norte B).

Corre los lunes 07:00 (vía launchd). Genera el pronóstico a 7 días por producto,
pedido sugerido, dashboard y bitácora; copia a Drive. Idempotente.

Uso manual:
    ./.venv/bin/python pronostico_semanal.py            # corrida normal + copia a Drive
    ./.venv/bin/python pronostico_semanal.py --no-drive # sin copiar a Drive
    ./.venv/bin/python pronostico_semanal.py --validar  # además corre las 5 validaciones
    ./.venv/bin/python pronostico_semanal.py --solo-validar
"""
from __future__ import annotations

import argparse
import logging
import sys
import traceback
from datetime import datetime

# OpenMP (libomp) debe resolverse ANTES de importar xgboost.
from src import config

config.ensure_omp()

# A partir de aquí ya es seguro importar lo que depende de xgboost.
from src import carga_datos, salidas, validaciones  # noqa: E402


def _configurar_log() -> logging.Logger:
    config.asegurar_directorios()
    log = logging.getLogger("pronostico")
    log.setLevel(logging.INFO)
    if log.handlers:
        return log
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(config.LOGS / "pronostico.log", encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    log.addHandler(fh)
    log.addHandler(sh)
    return log


def correr(no_drive: bool, validar: bool, solo_validar: bool) -> int:
    log = _configurar_log()
    inicio = datetime.now()
    log.info("===== Inicio corrida semanal SBH =====")
    try:
        params = config.cargar_parametros()
        hist = carga_datos.construir_historico(params["productos"])
        log.info("Histórico cargado: %d filas, productos %s", len(hist), params["productos"])

        if not solo_validar:
            datos = salidas.preparar_datos_dashboard(hist, params)
            res = salidas.generar_todo(datos, params, copiar_drive=not no_drive)
            log.info("Semana %s · veredicto: %s", datos["semana_id"], salidas._veredicto(datos))
            for prod in params["productos"]:
                d = datos["productos"][prod]
                log.info("  %s: cobertura %.1f d · pedido %d pipas · atinado %.0f%%",
                         prod, d["cobertura_dias"], d["pipas_total"], d["atinado_pct"])
            log.info("Salidas en %s", res["dir"])
            log.info("Drive: %s", res["drive_msg"])

        if validar or solo_validar:
            log.info("----- Validaciones -----")
            vals = validaciones.ejecutar_todas(hist, params)
            for v in vals:
                log.info("%s %s", "PASA" if v["pasa"] else "NO PASA", v["nombre"])
            if not all(v["pasa"] for v in vals):
                log.warning("Alguna validación NO PASA (ver detalle).")

        dur = (datetime.now() - inicio).total_seconds()
        log.info("===== Fin corrida OK (%.1fs) =====", dur)
        return 0
    except Exception as e:  # noqa: BLE001
        log.error("FALLO en la corrida: %s", e)
        log.error(traceback.format_exc())
        log.info("===== Fin corrida CON ERROR =====")
        return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Pronóstico semanal EESS SBH")
    ap.add_argument("--no-drive", action="store_true", help="No copiar salidas a Google Drive")
    ap.add_argument("--validar", action="store_true", help="Correr también las 5 validaciones")
    ap.add_argument("--solo-validar", action="store_true", help="Solo validaciones, sin generar salidas")
    args = ap.parse_args()
    return correr(args.no_drive, args.validar, args.solo_validar)


if __name__ == "__main__":
    raise SystemExit(main())
