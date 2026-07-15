#!/usr/bin/env python3
"""pronostico_semanal.py — entrypoint multi-estación (QUANTUM Norte B).

Cada estación corre AISLADA (su histórico, su bitácora, su yaml, sus modelos),
identificada por su permiso CNE. Nunca se mezcla data de dos estaciones.

Uso manual:
    ./.venv/bin/python pronostico_semanal.py --estacion PL/6812/EXP/ES/2015
    ./.venv/bin/python pronostico_semanal.py --todas
    ./.venv/bin/python pronostico_semanal.py --todas --no-drive --validar
    ./.venv/bin/python pronostico_semanal.py --alta PL/9999/EXP/ES/2020
    ./.venv/bin/python pronostico_semanal.py --estacion PL/6812/EXP/ES/2015 --solo-validar
"""
from __future__ import annotations

import argparse
import logging
import sys
import traceback
from datetime import datetime

from src import config

config.ensure_omp()  # libomp antes de xgboost

from src import alta as ALTA  # noqa: E402
from src import carga_datos, salidas, validaciones  # noqa: E402


def _log() -> logging.Logger:
    config.LOGS.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("pronostico")
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(config.LOGS / "orquestador.log", encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    log.addHandler(fh); log.addHandler(sh)
    return log


def _resolver_norm(valor: str) -> str:
    """Acepta permiso (PL/…) o ya-normalizado (PL-…)."""
    return config.normalizar_permiso(valor)


def correr_estacion(norm: str, no_drive: bool, validar: bool, solo_validar: bool, log) -> dict:
    config.usar_estacion(norm)
    if not config.PARAMETROS_YAML.exists():
        log.error("Estación %s sin parametros.yaml (%s). Se omite.", norm, config.PARAMETROS_YAML)
        return {"norm": norm, "ok": False, "datos": None, "params": None}

    reg = config.cargar_registro().get("estaciones", {}).get(norm, {})
    estatus = reg.get("estatus", "desconocido")
    params = config.cargar_parametros()
    hist = carga_datos.construir_historico(params["productos"], estacion=norm)
    carga_datos.assert_una_estacion(hist, contexto=f"corrida {norm}")
    log.info("[%s] %s · estatus=%s · %d filas", norm, reg.get("clave_corta", ""), estatus, len(hist))

    datos = None
    if not solo_validar:
        datos = salidas.preparar_datos_dashboard(hist, params)
        # En calibración NO se emite pedido sugerido (solo aprende).
        if estatus == "calibración":
            for p in datos["productos"].values():
                p["pipas_total"] = 0
                for d in p["plan"]:
                    d["pipas"] = 0
            log.info("[%s] en CALIBRACIÓN: se genera pronóstico pero NO pedido sugerido.", norm)
        res = salidas.generar_todo(datos, params, copiar_drive=not no_drive)
        log.info("[%s] semana %s · %s", norm, datos["semana_id"], salidas._veredicto(datos))
        log.info("[%s] Drive: %s", norm, res["drive_msg"])

    if validar or solo_validar:
        vals = validaciones.ejecutar_todas(hist, params)
        for v in vals:
            log.info("[%s] %s %s", norm, "PASA" if v["pasa"] else "NO PASA", v["nombre"])
        if estatus == "calibración" and all(v["pasa"] for v in vals):
            log.info("[%s] pasó sus 5 validaciones: candidata a pasar de 'calibración' a 'activa'.", norm)

    return {"norm": norm, "ok": True, "datos": datos, "params": params, "reg": reg}


def generar_dashboard_multi(resultados: list[dict], log) -> None:
    """Dashboard combinado con selector en salidas/ (vista local)."""
    items = []
    registro = config.cargar_registro()
    for r in resultados:
        if r["datos"] is None:
            continue
        config.usar_estacion(r["norm"])
        html = salidas.render_dashboard(r["datos"], r["params"])
        items.append((r["norm"], html))
    if not items:
        return
    combo = salidas.render_dashboard_multi(items, registro)
    ruta = config.SALIDAS_ROOT / "dashboard_semanal.html"
    ruta.write_text(combo, encoding="utf-8")
    log.info("Dashboard multi-estación (selector) en %s", ruta)


def main() -> int:
    ap = argparse.ArgumentParser(description="Pronóstico semanal EESS (multi-estación)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--estacion", help="Permiso CNE de la estación (o su forma normalizada)")
    g.add_argument("--todas", action="store_true", help="Corre todas las estaciones del registro")
    g.add_argument("--alta", help="Da de alta una estación nueva por permiso (scaffold en calibración)")
    ap.add_argument("--no-drive", action="store_true")
    ap.add_argument("--validar", action="store_true")
    ap.add_argument("--solo-validar", action="store_true")
    args = ap.parse_args()
    log = _log()

    if args.alta:
        info = ALTA.alta_estacion(args.alta)
        if info.get("ya_existe"):
            log.info(info["mensaje"]); return 0
        log.info("ALTA %s", info["norm"])
        for linea in info["checklist"]:
            log.info("  %s", linea)
        return 0

    if args.todas:
        norms = config.estaciones_registradas()
        if not norms:
            log.error("El registro no tiene estaciones."); return 1
    else:
        norms = [_resolver_norm(args.estacion)]

    log.info("===== Corrida (%d estación/es) =====", len(norms))
    inicio = datetime.now()
    resultados = []
    hubo_error = False
    for norm in norms:
        try:
            resultados.append(correr_estacion(norm, args.no_drive, args.validar, args.solo_validar, log))
        except Exception as e:  # noqa: BLE001
            hubo_error = True
            log.error("[%s] FALLO: %s", norm, e)
            log.error(traceback.format_exc())

    if not args.solo_validar and len([r for r in resultados if r.get("datos")]) >= 1:
        generar_dashboard_multi(resultados, log)

    dur = (datetime.now() - inicio).total_seconds()
    log.info("===== Fin (%.1fs) %s =====", dur, "CON ERROR" if hubo_error else "OK")
    return 1 if hubo_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
