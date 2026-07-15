"""reglas.py — reglas post-modelo (03.5). NADA hardcodeado: todo viene del yaml.

- resolver_regla: qué regla aplica en un día y su multiplicador (con prioridad).
- nivel_tipico_dow: nivel típico del día-de-semana (mediana reciente no-regla).
- calcular_deriva: media(real/pred) últimos 14 días no-festivos, amortiguada y acotada.
- politica_nortes: cobertura mínima y alertas en temporada de nortes.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

# Prioridad de reglas (de más específica a menos)
PRIORIDAD = [
    "jue_vie_santo",
    "festivo_lft_puente",
    "festivo_lft_fijo",
    "festivo_escolar",
    "vacacion_semana_santa",
    "partido_mx",
    "quincena_laboral",
]


def resolver_regla(fila, params: dict, producto: str) -> tuple[str | None, float]:
    """Devuelve (nombre_regla, multiplicador) para una fila de calendario.

    `fila` expone banderas: jue_vie_santo, festivo_lft, festivo_escolar,
    vac_semana_santa, partido_mx, quincena_laboral, dow.
    """
    mult = params["multiplicadores"]
    dow = int(fila["dow"])
    es_finde = dow in (5, 6)

    if fila.get("jue_vie_santo", 0):
        return "jueves_viernes_santo", mult["jueves_viernes_santo"][producto]
    if fila.get("festivo_lft_puente", 0):
        return "festivo_lft_puente", mult["festivo_lft_puente"][producto]
    if fila.get("festivo_lft_fijo", 0):
        return "festivo_lft_fijo", mult["festivo_lft_fijo"][producto]
    if fila.get("festivo_escolar", 0):
        return "festivo_escolar", mult["festivo_escolar"][producto]
    if fila.get("vac_semana_santa", 0):
        return "vacacion_semana_santa", mult["vacacion_semana_santa"][producto]
    if fila.get("partido_mx", 0):
        clave = "partido_mx_finde" if (es_finde and "partido_mx_finde" in mult) else "partido_mx"
        return "partido_mx", mult[clave][producto]
    if fila.get("quincena_laboral", 0):
        return "quincena_laboral", mult["quincena_laboral"][producto]
    return None, 1.0


def nivel_tipico_dow(frame: pd.DataFrame, fecha: pd.Timestamp, dow: int, params: dict) -> float:
    """Mediana de ventas (no censuradas, no-regla, con dato) del mismo dow en las
    últimas N semanas anteriores a `fecha`."""
    semanas = params["nivel_tipico_dow"]["semanas_lookback"]
    lo = fecha - pd.Timedelta(days=7 * semanas)
    hist = frame[(frame.index < fecha) & (frame.index >= lo)]
    mismo = hist[(hist["dow"] == dow) & (hist["censurado"] == 0) & (hist["sin_dato"] == 0)]
    # excluir días con regla activa para no contaminar el "nivel típico"
    regla_activa = (
        (mismo.get("jue_vie_santo", 0) == 1)
        | (mismo.get("festivo_lft", 0) == 1)
        | (mismo.get("festivo_escolar", 0) == 1)
    )
    mismo = mismo[~regla_activa]
    vals = mismo["ventas"].dropna()
    if len(vals):
        return float(vals.median())
    # respaldo: mediana global reciente
    glob = hist["ventas"].dropna()
    return float(glob.median()) if len(glob) else float(frame["ventas"].dropna().median())


def calcular_deriva(frame: pd.DataFrame, preds_hist: pd.Series, params: dict,
                    dias_sin_recepcion_origen: float) -> float:
    """media(real/pred) de últimos N días no-festivos, amortiguada y acotada.

    CONGELAR (=1.0) si dias_sin_recepcion_origen supera el umbral.
    `preds_hist`: predicciones del modelo (mismas fechas que `frame` observado).
    """
    dv = params["deriva"]
    if dias_sin_recepcion_origen > dv["congelar_si_dias_sin_recepcion_mayor_a"]:
        return 1.0

    obs = frame[(frame["sin_dato"] == 0) & (frame["censurado"] == 0)].copy()
    # excluir festivos (LFT / escolar / santo)
    festivo = (
        (obs.get("festivo_lft", 0) == 1)
        | (obs.get("festivo_escolar", 0) == 1)
        | (obs.get("jue_vie_santo", 0) == 1)
    )
    obs = obs[~festivo]
    obs = obs.join(preds_hist.rename("pred"), how="inner")
    obs = obs[obs["pred"] > 0].sort_index().tail(dv["ventana_dias"])
    if obs.empty:
        return 1.0
    ratio = (obs["ventas"] / obs["pred"]).replace([np.inf, -np.inf], np.nan).dropna()
    if ratio.empty:
        return 1.0
    ratio_medio = float(ratio.mean())
    deriva = 1.0 + dv["amortiguacion"] * (ratio_medio - 1.0)
    return float(np.clip(deriva, dv["cota_min"], dv["cota_max"]))


def en_temporada_nortes(fecha: pd.Timestamp, params: dict) -> bool:
    n = params["nortes"]
    mmdd = (fecha.month, fecha.day)
    ini = tuple(int(x) for x in n["temporada_inicio"].split("-"))
    fin = tuple(int(x) for x in n["temporada_fin"].split("-"))
    # temporada cruza el año (oct -> mar)
    return mmdd >= ini or mmdd <= fin


def cobertura_objetivo_dias(fecha: pd.Timestamp, params: dict, hay_norte_proximo: bool,
                            llega_festivo_lft: bool) -> tuple[int, list[str]]:
    """Días de cobertura objetivo según política de nortes y festivos LFT."""
    n = params["nortes"]
    alertas: list[str] = []
    objetivo = params["pedido"]["cobertura_objetivo_dias"]
    if en_temporada_nortes(fecha, params):
        objetivo = max(objetivo, n["cobertura_min_dias"])
        if int(n.get("norte_72h", 0)) == 1 or hay_norte_proximo:
            objetivo = max(objetivo, n["cobertura_norte72h_dias"])
    if llega_festivo_lft:
        objetivo = max(objetivo, n["minimo_ante_festivo_lft"])
    return objetivo, alertas
