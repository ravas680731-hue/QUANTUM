"""modelo.py — XGBoost por producto (03.4).

objective='reg:quantileerror'. Se entrena un modelo por cuantil solicitado
(0.62 para el pronóstico central; 0.20 / 0.80 para la banda).
Reentrena cada corrida con todo el histórico permitido por el régimen (03.2).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from xgboost import XGBRegressor


def _crear_modelo(params: dict, alpha: float) -> XGBRegressor:
    xp = params["xgboost"]
    return XGBRegressor(
        objective=xp["objective"],
        quantile_alpha=alpha,
        n_estimators=xp["n_estimators"],
        max_depth=xp["max_depth"],
        learning_rate=xp["learning_rate"],
        subsample=xp["subsample"],
        colsample_bytree=xp["colsample_bytree"],
        reg_lambda=xp["reg_lambda"],
        min_child_weight=xp["min_child_weight"],
        random_state=xp["random_state"],
        n_jobs=0,
        tree_method="hist",
    )


def entrenar(X: pd.DataFrame, y: pd.Series, params: dict, alpha: float) -> XGBRegressor:
    m = _crear_modelo(params, alpha)
    m.fit(X.values, y.values)
    return m


def predecir(modelo: XGBRegressor, X: pd.DataFrame) -> np.ndarray:
    pred = modelo.predict(X.values)
    return np.clip(pred, 0, None)
