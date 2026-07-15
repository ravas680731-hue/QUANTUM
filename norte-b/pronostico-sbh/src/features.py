"""features.py — construcción de features sin fuga a 7 días (03.1 / 03.3).

Todas las features autoregresivas usan shift >= 7, de modo que el bloque de 7
días futuros es predecible con datos observados hasta el origen (pronóstico
directo, sin recursión).

Salida principal: `construir_frame(...)` devuelve un DataFrame diario continuo
desde el inicio del histórico hasta `origen + horizonte`, con:
 - columnas de features (FEATURE_COLS / feature_cols_producto)
 - target `ventas` (real; NaN en días futuros o sin dato)
 - meta: `censurado`, `sin_dato`, `sdo_final`, `compras`, `ventas_imp`,
   `dias_sin_recepcion`, `cobertura_dias`, `en_horizonte`
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import calendario as C

BANDERAS_CAL = [
    "festivo_lft", "festivo_escolar", "jueves_santo", "viernes_santo",
    "vac_semana_santa", "partido_mx", "evento_tv",
    "vac_invierno", "fin_ciclo", "regreso_clases", "gr",
]
CLIMA_COLS = ["norte", "lluvia", "puerto_cerrado", "norte_lag3", "post_norte", "norte_x_lunes"]
INVENTARIO_COLS = ["dias_sin_recepcion", "cobertura_dias"]
DOW_COLS = [f"dow_{i}" for i in range(7)]
AR_COLS = ["lag7", "lag14", "ma7", "ma14", "ma28", "tendencia"]
CAL_NUM = ["dia", "mes", "quincena"]
PRIOR_COLS = ["prior_estacional"]


def feature_cols_producto(usa_lag364: bool) -> list[str]:
    cols = (AR_COLS + (["lag364"] if usa_lag364 else [])
            + DOW_COLS + CAL_NUM + BANDERAS_CAL + CLIMA_COLS + INVENTARIO_COLS + PRIOR_COLS)
    return cols


def _imputar_dow(ventas: pd.Series, invalida: pd.Series, ventana: int) -> pd.Series:
    """Imputa valores inválidos con la mediana del mismo día-de-semana en ±`ventana` días.

    `ventas`: serie indexada por fecha diaria continua.
    `invalida`: máscara booleana de días a imputar (censurados o sin dato).
    """
    out = ventas.copy()
    validos = ventas.where(~invalida)
    idx = ventas.index
    dow = idx.weekday
    for pos in np.where(invalida.values)[0]:
        f = idx[pos]
        wd = dow[pos]
        lo = f - pd.Timedelta(days=ventana)
        hi = f + pd.Timedelta(days=ventana)
        ventana_mask = (idx >= lo) & (idx <= hi) & (dow == wd)
        vals = validos[ventana_mask].dropna()
        if len(vals):
            out.iloc[pos] = float(vals.median())
        else:
            glob = validos.dropna()
            out.iloc[pos] = float(glob.median()) if len(glob) else 0.0
    return out


def construir_frame(
    df_producto: pd.DataFrame,
    producto: str,
    params: dict,
    clima_df: pd.DataFrame,
    fecha_origen: pd.Timestamp,
    horizonte: int = 7,
) -> pd.DataFrame:
    """Construye el frame diario de features + target hasta origen+horizonte.

    `df_producto` debe estar filtrado a fechas <= fecha_origen (no futuras).
    `clima_df` debe cubrir todo el rango (usar clima.cargar_clima).
    """
    cfgp = params["config_producto"][producto]
    fondo_muerto = cfgp["fondo_muerto"]
    usa_lag364 = bool(cfgp["usa_lag364"])
    pct = params["censura"]["percentil_ventas"]
    ventana_imp = params["censura"]["ventana_imputacion_dias"]

    d = df_producto[df_producto["fecha"] <= fecha_origen].copy().set_index("fecha").sort_index()

    inicio = d.index.min()
    fin = fecha_origen + pd.Timedelta(days=horizonte)
    idx = pd.date_range(inicio, fin, freq="D")

    f = pd.DataFrame(index=idx)
    f.index.name = "fecha"
    f["ventas"] = d["ventas"].reindex(idx)
    f["sdo_final"] = d["sdo_final"].reindex(idx)
    f["compras"] = d["compras"].reindex(idx)

    f["en_horizonte"] = (idx > fecha_origen).astype(int)
    f["sin_dato"] = (f["ventas"].isna() & (f["en_horizonte"] == 0)).astype(int)

    # --- Censura de desabasto (03.1) ---
    obs = f["ventas"].dropna()
    p5 = np.percentile(obs, pct) if len(obs) else 0.0
    censurado = (f["ventas"] < p5) & (f["sdo_final"] < fondo_muerto) & f["ventas"].notna()
    f["censurado"] = censurado.astype(int)

    # --- Serie imputada para construir lags ---
    invalida = (censurado | f["ventas"].isna()) & (f["en_horizonte"] == 0)
    f["ventas_imp"] = _imputar_dow(f["ventas"].fillna(np.nan), invalida, ventana_imp)
    # días futuros: sin valor imputado (NaN) — no se usan como fuente de lag
    f.loc[f["en_horizonte"] == 1, "ventas_imp"] = np.nan

    vi = f["ventas_imp"]
    # --- Autoregresivas (shift >= 7, sin fuga) ---
    f["lag7"] = vi.shift(7)
    f["lag14"] = vi.shift(14)
    f["ma7"] = vi.rolling(7).mean().shift(7)
    f["ma14"] = vi.rolling(14).mean().shift(7)
    f["ma28"] = vi.rolling(28).mean().shift(7)
    f["tendencia"] = f["ma7"] - f["ma28"]
    if usa_lag364:
        f["lag364"] = vi.shift(364)

    # --- Calendario ---
    cal = C.calendario_rango(idx.min(), idx.max(), params)
    cal = cal.reindex(idx)
    for c in DOW_COLS:
        pass
    for i in range(7):
        f[f"dow_{i}"] = (cal["dow"] == i).astype(int)
    f["dia"] = cal["dia"]
    f["mes"] = cal["mes"]
    f["quincena"] = cal["quincena"]
    for c in BANDERAS_CAL:
        f[c] = cal[c]
    # guardamos banderas auxiliares para reglas
    f["jue_vie_santo"] = cal["jue_vie_santo"]
    f["festivo_lft_puente"] = cal["festivo_lft_puente"]
    f["festivo_lft_fijo"] = cal["festivo_lft_fijo"]
    f["quincena_laboral"] = cal["quincena_laboral"]
    f["dow"] = cal["dow"]

    # --- Clima ---
    cl = clima_df.reindex(idx).fillna(0.0)
    f["norte"] = cl["norte"]
    f["lluvia"] = cl["lluvia"]
    f["puerto_cerrado"] = cl["puerto_cerrado"]
    f["norte_lag3"] = cl["norte"].shift(3).fillna(0.0)
    f["post_norte"] = (((cl["norte"].shift(1) >= 2) | (cl["norte"].shift(2) >= 2)).astype(int)).fillna(0)
    f["norte_x_lunes"] = cl["norte"] * (cal["dow"] == 0).astype(int)

    # --- Inventario ---
    # días sin recepción: días consecutivos con compras == 0 (a inicio de día)
    compras = f["compras"].fillna(0.0)
    recepcion = (compras > 0).astype(int)
    # contador reiniciado en cada recepción
    grupos = recepcion.cumsum()
    dias_sin = recepcion.groupby(grupos).cumcount()
    f["dias_sin_recepcion"] = dias_sin
    # cobertura al inicio del día: saldo útil de ayer / ma7 ventas de ayer
    sdo_util = (f["sdo_final"].shift(1) - fondo_muerto).clip(lower=0)
    ma7v = vi.rolling(7).mean().shift(1)
    f["cobertura_dias"] = (sdo_util / ma7v.replace(0, np.nan)).clip(0, 60)

    # Para el horizonte: congelar estado de inventario en el valor del origen
    if (f["en_horizonte"] == 1).any():
        cob_origen = f.loc[fecha_origen, "cobertura_dias"] if fecha_origen in f.index else np.nan
        dsr_origen = f.loc[fecha_origen, "dias_sin_recepcion"] if fecha_origen in f.index else 0
        hz = f["en_horizonte"] == 1
        f.loc[hz, "cobertura_dias"] = f.loc[hz, "cobertura_dias"].fillna(cob_origen)
        # incrementa días sin recepción asumiendo que aún no llega pipa
        offsets = np.arange(1, hz.sum() + 1)
        f.loc[hz, "dias_sin_recepcion"] = (dsr_origen + offsets)

    f["cobertura_dias"] = f["cobertura_dias"].fillna(0.0)

    # --- Prior estacional (03.3) ---
    priors = params.get("priors_estacionales", {}).get(producto, {})
    f["prior_estacional"] = f["mes"].map(lambda m: priors.get(int(m), 100) / 100.0 if int(m) in priors else 1.0)

    return f
