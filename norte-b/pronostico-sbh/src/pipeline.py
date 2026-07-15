"""pipeline.py — orquestación del pronóstico por producto (reutilizado por la
corrida real y por el backtest, garantizando el MISMO tratamiento y sin fuga).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import carga_datos as CD
from . import features as F
from . import modelo as M
from . import reglas as R


def _fecha_origen(df_producto: pd.DataFrame) -> pd.Timestamp:
    return pd.Timestamp(df_producto["fecha"].max())


def generar_pronostico(
    df_producto: pd.DataFrame,
    producto: str,
    params: dict,
    clima_df: pd.DataFrame,
    fecha_origen: pd.Timestamp,
    horizonte: int = 7,
    con_banda: bool = True,
    fecha_inicio: pd.Timestamp | None = None,
) -> dict:
    """Genera el pronóstico de `horizonte` días para un producto.

    `fecha_inicio`: primer día de la ventana (por defecto origen+1). La corrida en
    vivo pasa la fecha operativa (p.ej. el próximo martes); el backtest usa el
    default para no alterar la validación.

    Devuelve dict con:
      - 'forecast': DataFrame [fecha, pronostico, p20, p80, base_modelo, regla, mult, deriva]
      - 'frame': frame completo de features (para diagnóstico)
      - 'deriva': factor de deriva aplicado
      - 'origen': fecha_origen
    """
    # AISLAMIENTO (03.2 multi): el DataFrame no puede mezclar estaciones.
    CD.assert_una_estacion(df_producto, contexto=f"generar_pronostico({producto})")

    cfgp = params["config_producto"][producto]
    usa_lag364 = bool(cfgp["usa_lag364"])
    feat_cols = F.feature_cols_producto(usa_lag364)

    frame = F.construir_frame(df_producto, producto, params, clima_df, fecha_origen,
                              horizonte, fecha_inicio=fecha_inicio)

    # --- Conjunto de entrenamiento (respeta régimen 03.2) ---
    # lag364 puede ser NaN en 2025 (solo existe desde el 2º año): NO lo exigimos,
    # XGBoost maneja el faltante de forma nativa. Así MAGNA entrena 2025+2026.
    cols_requeridas = [c for c in feat_cols if c != "lag364"]
    entrena_desde = cfgp.get("entrena_desde")
    entrenable = (
        (frame["en_horizonte"] == 0)
        & (frame["sin_dato"] == 0)
        & (frame["censurado"] == 0)
        & frame["ventas"].notna()
        & frame[cols_requeridas].notna().all(axis=1)
    )
    if entrena_desde:
        entrenable &= frame.index >= pd.Timestamp(entrena_desde)

    train = frame[entrenable]
    X_train = train[feat_cols]
    y_train = train["ventas"]

    # --- Configuración de target-ratio (destrendizado) ---
    mcfg = params.get("modelo", {}) or {}
    target_ratio = bool(mcfg.get("target_ratio", False))
    base_col = mcfg.get("baseline_feature", "ma28")
    baseline = frame[base_col].clip(lower=1.0) if target_ratio else None
    if target_ratio:
        # exigir baseline válido en filas entrenables (ma28 ya está en cols_requeridas)
        entrenable &= frame[base_col].notna() & (frame[base_col] > 0)
        train = frame[entrenable]
        X_train = train[feat_cols]
        y_train = train["ventas"]

    def fit_predict_level(Xtr, ytr_level, idx_tr, Xpred, idx_pred, alpha):
        """Entrena y predice en nivel. Si target_ratio, trabaja en ventas/baseline."""
        if target_ratio:
            b_tr = baseline.loc[idx_tr]
            m = M.entrenar(Xtr, ytr_level / b_tr, params, alpha)
            ratio = M.predecir(m, Xpred)
            return pd.Series(ratio, index=idx_pred) * baseline.loc[idx_pred], m
        m = M.entrenar(Xtr, ytr_level, params, alpha)
        return pd.Series(M.predecir(m, Xpred), index=idx_pred), m

    # --- Predicción central (alpha del yaml) ---
    alpha = params["xgboost"]["quantile_alpha"]
    hz = frame[frame["en_horizonte"] == 1]
    X_hz = hz[feat_cols]
    base_pred, modelo = fit_predict_level(X_train, y_train, X_train.index, X_hz, hz.index, alpha)

    # --- Deriva ---
    # La deriva corrige el SESGO reciente real/pred. Debe medirse fuera de muestra:
    # un modelo entrenado con datos in-sample sobreajusta (real/pred≈1) y la deriva
    # quedaría ciega al sesgo. Entrenamos un modelo auxiliar excluyendo la ventana
    # reciente y predecimos esos días como verdadero holdout.
    dv = params["deriva"]
    dsr_origen = float(frame.loc[fecha_origen, "dias_sin_recepcion"]) if fecha_origen in frame.index else 0.0
    corte = fecha_origen - pd.Timedelta(days=dv["ventana_dias"] + 7)
    mask_dtrain = entrenable & (frame.index <= corte)
    mask_hold = entrenable & (frame.index > corte)
    if int(mask_dtrain.sum()) >= 30 and int(mask_hold.sum()) >= 1:
        dtr = frame[mask_dtrain]
        hold = frame[mask_hold]
        preds_hold, _ = fit_predict_level(dtr[feat_cols], dtr["ventas"], dtr.index,
                                          hold[feat_cols], hold.index, alpha)
    else:
        # histórico corto: respaldo in-sample (deriva será ~neutra)
        preds_hold, _ = fit_predict_level(X_train, y_train, X_train.index, X_train, X_train.index, alpha)
    deriva = R.calcular_deriva(frame, preds_hold, params, dsr_origen)

    # --- Aplicar reglas por día de horizonte ---
    filas = []
    for f, xrow in hz.iterrows():
        dow = int(xrow["dow"])
        regla, mult = R.resolver_regla(xrow, params, producto)
        if regla is not None:
            nivel = R.nivel_tipico_dow(frame, f, dow, params)
            pronostico = nivel * mult
            deriva_aplicada = 1.0
        else:
            pronostico = float(base_pred[f]) * deriva
            deriva_aplicada = deriva
        filas.append({
            "fecha": f,
            "producto": producto,
            "pronostico": round(float(pronostico), 2),
            "base_modelo": round(float(base_pred[f]), 2),
            "regla": regla or "modelo",
            "mult": round(float(mult), 3),
            "deriva": round(float(deriva_aplicada), 3),
        })

    forecast = pd.DataFrame(filas)

    # --- Banda p20 / p80 ---
    if con_banda:
        cb = params["cuantiles_banda"]
        p20, _ = fit_predict_level(X_train, y_train, X_train.index, X_hz, hz.index, cb["p20"])
        p80, _ = fit_predict_level(X_train, y_train, X_train.index, X_hz, hz.index, cb["p80"])
        # la banda escala con el mismo ajuste (regla/deriva) que el central
        escala = forecast.set_index("fecha")["pronostico"] / base_pred.replace(0, np.nan)
        escala = escala.fillna(1.0)
        forecast["p20"] = [round(float(p20[f] * escala.get(f, 1.0)), 2) for f in forecast["fecha"]]
        forecast["p80"] = [round(float(p80[f] * escala.get(f, 1.0)), 2) for f in forecast["fecha"]]
        # garantizar p20 <= pronostico <= p80
        forecast["p20"] = forecast[["p20", "pronostico"]].min(axis=1)
        forecast["p80"] = forecast[["p80", "pronostico"]].max(axis=1)
    else:
        forecast["p20"] = np.nan
        forecast["p80"] = np.nan

    return {
        "forecast": forecast,
        "frame": frame,
        "deriva": deriva,
        "origen": fecha_origen,
        "n_train": len(train),
        "min_train_fecha": X_train.index.min() if len(train) else None,
    }
