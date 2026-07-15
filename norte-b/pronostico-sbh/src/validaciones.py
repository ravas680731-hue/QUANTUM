"""validaciones.py — las 5 validaciones obligatorias (04).

1. Backtest walk-forward (MAPE por producto vs umbral).
2. calendario(2026) y calendario(2027) correctos; Pascua 2026=5-abr, 2027=28-mar.
3. Congelamiento: 6 días sin recepción -> deriva inmóvil (=1.0).
4. Idempotencia: doble ejecución = salidas idénticas.
5. Assert de régimen: fecha mínima de entrenamiento de PREMIUM y DIESEL >= 2026-01-01.
"""
from __future__ import annotations

import datetime as dt
import hashlib

import pandas as pd

from . import backtest as BT
from . import calendario as C
from . import carga_datos as CD
from . import clima as CL
from . import pipeline as P
from . import salidas as S


def val1_backtest(hist, params) -> dict:
    res = BT.backtest_todos(hist, params)
    filas = []
    todos_pasan = True
    for prod, r in res.items():
        todos_pasan &= r["pasa"]
        filas.append({"producto": prod, "mape": round(r["mape"], 2),
                      "umbral": r["umbral"], "pasa": r["pasa"], "n_obs": r["n_obs"]})
    return {"nombre": "1. Backtest walk-forward", "pasa": todos_pasan, "detalle": filas}


def val2_calendario(params) -> dict:
    chk = []
    p26 = C.domingo_pascua(2026)
    p27 = C.domingo_pascua(2027)
    chk.append(("Pascua 2026 = 2026-04-05", p26 == dt.date(2026, 4, 5), str(p26)))
    chk.append(("Pascua 2027 = 2027-03-28", p27 == dt.date(2027, 3, 28), str(p27)))
    lft26 = C.festivos_lft(2026)
    chk.append(("1er lunes feb 2026 = 2026-02-02", dt.date(2026, 2, 2) in lft26, "ok"))
    chk.append(("3er lunes mar 2026 = 2026-03-16", dt.date(2026, 3, 16) in lft26, "ok"))
    chk.append(("16-sep-2026 festivo", dt.date(2026, 9, 16) in lft26, "ok"))
    lft27 = C.festivos_lft(2027)
    chk.append(("1-ene-2027 festivo", dt.date(2027, 1, 1) in lft27, "ok"))
    # Jueves/Viernes santo 2026 dentro del calendario
    cal = C.calendario_rango("2026-03-30", "2026-04-05", params)
    chk.append(("Jueves Santo 2026 = 2026-04-02", int(cal.loc["2026-04-02", "jueves_santo"]) == 1, "ok"))
    chk.append(("Viernes Santo 2026 = 2026-04-03", int(cal.loc["2026-04-03", "viernes_santo"]) == 1, "ok"))
    pasa = all(ok for _, ok, _ in chk)
    return {"nombre": "2. Calendario 2026/2027", "pasa": pasa,
            "detalle": [{"check": c, "ok": ok, "valor": v} for c, ok, v in chk]}


def val3_congelamiento(hist, params) -> dict:
    """6 días sin recepción -> deriva congelada (=1.0)."""
    prod = "MAGNA"
    dfp = hist[hist["producto"] == prod].copy()
    origen = pd.Timestamp(dfp["fecha"].max())
    cl, _ = CL.cargar_clima(pd.date_range(dfp["fecha"].min(), origen + pd.Timedelta(days=7)))

    # control: datos normales
    r_ctrl = P.generar_pronostico(dfp, prod, params, cl, origen, con_banda=False)

    # escenario: últimos 6 días sin compras
    dfp_frio = dfp.copy()
    ult6 = dfp_frio["fecha"] > (origen - pd.Timedelta(days=6))
    dfp_frio.loc[ult6, "compras"] = 0.0
    r_frio = P.generar_pronostico(dfp_frio, prod, params, cl, origen, con_banda=False)

    dsr = float(r_frio["frame"].loc[origen, "dias_sin_recepcion"])
    congelada = abs(r_frio["deriva"] - 1.0) < 1e-9
    pasa = congelada and dsr > 4
    return {"nombre": "3. Congelamiento de deriva", "pasa": pasa, "detalle": [
        {"check": "deriva normal (control) se mueve", "ok": abs(r_ctrl["deriva"] - 1.0) > 1e-6,
         "valor": f"{r_ctrl['deriva']:.4f}"},
        {"check": "días sin recepción tras 6 días", "ok": dsr > 4, "valor": f"{dsr:.0f}"},
        {"check": "deriva congelada = 1.0", "ok": congelada, "valor": f"{r_frio['deriva']:.4f}"},
    ]}


def _hash_archivo(ruta) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()[:12]


def val4_idempotencia(hist, params) -> dict:
    """Doble ejecución el mismo lunes => salidas idénticas y bitácora sin duplicados."""
    datos1 = S.preparar_datos_dashboard(hist, params)
    r1 = S.generar_todo(datos1, params, copiar_drive=False)
    h1 = {k: _hash_archivo(r1[k]) for k in ("csv", "pedido", "dashboard")}
    n_bita1 = len(pd.read_csv(r1["bitacora"]))

    datos2 = S.preparar_datos_dashboard(hist, params)
    r2 = S.generar_todo(datos2, params, copiar_drive=False)
    h2 = {k: _hash_archivo(r2[k]) for k in ("csv", "pedido", "dashboard")}
    n_bita2 = len(pd.read_csv(r2["bitacora"]))

    iguales = h1 == h2
    bita_ok = n_bita1 == n_bita2
    return {"nombre": "4. Idempotencia", "pasa": iguales and bita_ok, "detalle": [
        {"check": "hash pronostico_semana.csv", "ok": h1["csv"] == h2["csv"], "valor": f"{h1['csv']}=={h2['csv']}"},
        {"check": "hash pedido_sugerido.md", "ok": h1["pedido"] == h2["pedido"], "valor": f"{h1['pedido']}=={h2['pedido']}"},
        {"check": "hash dashboard_semanal.html", "ok": h1["dashboard"] == h2["dashboard"], "valor": f"{h1['dashboard']}=={h2['dashboard']}"},
        {"check": "bitácora sin duplicados", "ok": bita_ok, "valor": f"{n_bita1} == {n_bita2} filas"},
    ]}


def val5_regimen(hist, params) -> dict:
    filas = []
    pasa = True
    for prod in ("PREMIUM", "DIESEL"):
        dfp = hist[hist["producto"] == prod]
        origen = pd.Timestamp(dfp["fecha"].max())
        cl, _ = CL.cargar_clima(pd.date_range(dfp["fecha"].min(), origen + pd.Timedelta(days=7)))
        r = P.generar_pronostico(dfp, prod, params, cl, origen, con_banda=False)
        mn = r["min_train_fecha"]
        ok = mn is not None and mn >= pd.Timestamp("2026-01-01")
        pasa &= ok
        filas.append({"check": f"min fecha entrenamiento {prod} >= 2026-01-01", "ok": ok,
                      "valor": str(mn.date()) if mn is not None else "—"})
    return {"nombre": "5. Assert de régimen", "pasa": pasa, "detalle": filas}


def ejecutar_todas(hist=None, params=None) -> list[dict]:
    from . import config
    params = params or config.cargar_parametros()
    hist = hist if hist is not None else CD.construir_historico(params["productos"])
    return [
        val2_calendario(params),
        val5_regimen(hist, params),
        val3_congelamiento(hist, params),
        val4_idempotencia(hist, params),
        val1_backtest(hist, params),
    ]
