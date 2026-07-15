"""backtest.py — validación walk-forward (04.1).

train >= 100d, h=7, folds semanales desde 2026-04-11.
MAPE objetivo: <= 9.0% Magna, <= 15% Premium, <= 19% Diesel.
Evalúa el sistema COMPLETO (modelo + reglas + deriva) sin fuga: cada fold
reconstruye features usando solo datos <= origen.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import clima as CL
from . import pipeline as P


def _origenes(desde: pd.Timestamp, ultimo: pd.Timestamp, horizonte: int) -> list[pd.Timestamp]:
    """Orígenes semanales O tal que O+horizonte <= ultimo."""
    ori = []
    o = pd.Timestamp(desde)
    while o + pd.Timedelta(days=horizonte) <= ultimo:
        ori.append(o)
        o = o + pd.Timedelta(days=7)
    return ori


def backtest_producto(df_producto: pd.DataFrame, producto: str, params: dict) -> dict:
    bt = params["backtest"]
    horizonte = bt["horizonte"]
    train_min = bt["train_min_dias"]
    desde = pd.Timestamp(bt["desde"])
    ultimo = pd.Timestamp(df_producto["fecha"].max())

    serie = df_producto.set_index("fecha").sort_index()
    origenes = _origenes(desde, ultimo, horizonte)

    registros = []
    for o in origenes:
        hist_o = df_producto[df_producto["fecha"] <= o]
        if len(hist_o) < train_min:
            continue
        cl, _ = CL.cargar_clima(pd.date_range(hist_o["fecha"].min(), o + pd.Timedelta(days=horizonte)))
        try:
            res = P.generar_pronostico(hist_o, producto, params, cl, o, horizonte=horizonte, con_banda=False)
        except Exception as e:  # noqa: BLE001
            registros.append({"origen": o, "error": str(e)})
            continue
        # respeta el mínimo de entrenamiento efectivo
        if res["n_train"] < train_min:
            continue
        fc = res["forecast"].set_index("fecha")
        for f, row in fc.iterrows():
            if f not in serie.index:
                continue
            real = serie.loc[f, "ventas"]
            sdo = serie.loc[f, "sdo_final"]
            fondo = params["config_producto"][producto]["fondo_muerto"]
            # excluir días censurados (desabasto) del cómputo de error
            censurado = (real is not None) and (not pd.isna(real)) and (real < np.percentile(serie["ventas"].dropna(), params["censura"]["percentil_ventas"])) and (sdo < fondo)
            if pd.isna(real) or censurado or real <= 0:
                continue
            pred = row["pronostico"]
            ape = abs(pred - real) / real * 100.0
            registros.append({
                "origen": o, "fecha": f, "producto": producto,
                "real": float(real), "pred": float(pred), "ape": float(ape),
                "regla": row["regla"],
            })

    det = pd.DataFrame([r for r in registros if "ape" in r])
    mape = float(det["ape"].mean()) if not det.empty else float("nan")
    return {
        "producto": producto,
        "mape": mape,
        "n_obs": len(det),
        "n_folds": len(origenes),
        "detalle": det,
        "umbral": params["backtest"]["mape_max"][producto],
        "pasa": (not np.isnan(mape)) and mape <= params["backtest"]["mape_max"][producto],
    }


def backtest_todos(hist: pd.DataFrame, params: dict) -> dict[str, dict]:
    out = {}
    for prod in params["productos"]:
        dfp = hist[hist["producto"] == prod]
        out[prod] = backtest_producto(dfp, prod, params)
    return out
