"""salidas.py — genera las salidas de la corrida (03.6).

- pronostico_semana.csv
- pedido_sugerido.md
- dashboard_semanal.html  (modo humano)
- append a bitacora.csv (idempotente)
- copia a Google Drive (detecta ruta; avisa si no existe)

El dashboard está escrito para que un despachador de 18 años lo entienda a la
primera: veredicto en una frase, semáforo de tanques, plan de la semana en
lenguaje de pipas, gráfica de aciertos y avisos en lenguaje natural. Los números
técnicos van al final, colapsados.
"""
from __future__ import annotations

import html
import math
import shutil
from pathlib import Path

import pandas as pd

from . import clima as CL
from . import config
from . import pipeline as P

# --- Paleta QUANTUM ---------------------------------------------------------
NAVY = "#1F3A5F"
ORO = "#C9A227"
CREMA = "#F7F3EB"
VERDE = "#2E7D4F"
AMBAR = "#D89A00"
ROJO = "#B23A2E"

DIAS_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
DIAS_LARGO = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_ES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
            "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
NOMBRE = {"MAGNA": "Magna", "PREMIUM": "Premium", "DIESEL": "Diésel"}


# ============================================================================
#  LENGUAJE HUMANO
# ============================================================================
def describe_pipa(litros: float, cap: float) -> str:
    """Traduce litros a fracciones de pipa que cualquiera entiende."""
    p = litros / cap
    escala = [
        (0.20, "menos de un cuarto de pipa"),
        (0.30, "un cuarto de pipa"),
        (0.42, "un tercio de pipa"),
        (0.58, "media pipa"),
        (0.71, "dos tercios de pipa"),
        (0.85, "tres cuartos de pipa"),
        (1.15, "una pipa"),
        (1.6, "pipa y media"),
    ]
    for lim, txt in escala:
        if p < lim:
            return txt
    return f"{p:.1f} pipas"


def color_semaforo(cobertura: float) -> tuple[str, str, str]:
    """(color_hex, etiqueta, css_class) según cobertura en días. verde>5, ámbar 3-5, rojo<3."""
    if cobertura < 3:
        return ROJO, "SE VA A ACABAR", "rojo"
    if cobertura <= 5:
        return AMBAR, "VA JUSTO", "ambar"
    return VERDE, "ALCANZA BIEN", "verde"


def _veredicto(datos: dict) -> str:
    compras = []
    alcanza = []
    for prod in ("MAGNA", "PREMIUM", "DIESEL"):
        d = datos["productos"][prod]
        n = d["pipas_total"]
        if n > 0:
            plural = "pipas" if n != 1 else "pipa"
            compras.append(f"{n} {plural} de {NOMBRE[prod]}")
        elif d["cobertura_dias"] >= 7:
            alcanza.append(NOMBRE[prod])
    frase = ""
    if compras:
        frase += "Esta semana pide " + _y(compras) + "."
    else:
        frase += "Esta semana no necesitas comprar nada."
    if alcanza:
        if len(alcanza) == 1:
            frase += f" El {alcanza[0]} te alcanza de sobra — no compres."
        else:
            frase += f" El {_y(alcanza)} te alcanzan de sobra — no compres."
    return frase


def _y(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " y " + items[-1]


def _avisos(datos: dict, params: dict) -> list[dict]:
    """Alertas en lenguaje natural. Cada una: {icono, texto, tono}."""
    avisos = []
    # Cobertura crítica / justa
    for prod in ("MAGNA", "PREMIUM", "DIESEL"):
        d = datos["productos"][prod]
        if d["cobertura_dias"] < 3:
            avisos.append({"icono": "🔴", "tono": "rojo",
                           "texto": f"El tanque de {NOMBRE[prod]} está por acabarse "
                                    f"(alcanza ~{d['cobertura_dias']:.0f} días). El pedido de la semana ya lo cubre, "
                                    f"pero avisa a la pipa hoy mismo."})
        elif d["cobertura_dias"] <= 5:
            avisos.append({"icono": "🟡", "tono": "ambar",
                           "texto": f"El {NOMBRE[prod]} va justo (~{d['cobertura_dias']:.0f} días). "
                                    f"Con las {d['pipas_total']} pipas sugeridas se mantiene arriba."})
        elif d["cobertura_dias"] > 5 and d["pipas_total"] > 0:
            dia = next((p["fecha"] for p in d["plan"] if p["pipas"] > 0), None)
            cuando = f"para el {DIAS_LARGO[dia.weekday()]} {dia.day}" if dia is not None else "durante la semana"
            n = d["pipas_total"]
            avisos.append({"icono": "🟢", "tono": "info",
                           "texto": f"El {NOMBRE[prod]} hoy está bien (~{d['cobertura_dias']:.0f} días), pero baja durante "
                                    f"la semana: pídele {n} pipa {cuando} o termina el domingo muy abajo."})
    # Calendario de la semana
    cal = datos["calendario_semana"]
    if cal["hay_festivo_lft"]:
        for f in cal["festivos_lft"]:
            avisos.append({"icono": "📅", "tono": "info",
                           "texto": f"El {f} es día festivo: espera menos venta de Diésel "
                                    f"y algo más de Premium por salidas de fin de semana largo."})
    if cal["hay_quincena"]:
        avisos.append({"icono": "💵", "tono": "info",
                       "texto": "Cae quincena entre semana: la gente carga más, sobre todo Magna. "
                                "El pronóstico ya lo tomó en cuenta."})
    if cal["hay_fin_ciclo"]:
        avisos.append({"icono": "🎒", "tono": "info",
                       "texto": "Es fin de ciclo escolar: puede haber un poco más de movimiento de salida."})
    # Nortes
    if datos["temporada_nortes"]:
        avisos.append({"icono": "🌬️", "tono": "info",
                       "texto": "Estamos en temporada de nortes: el pedido trae colchón extra por si "
                                "cierran el puerto o baja el abasto."})
    # Clima faltante
    if datos["clima_faltante"]:
        avisos.append({"icono": "⛅", "tono": "info",
                       "texto": "No hay datos de clima cargados esta semana: el pronóstico asume clima normal. "
                                "Si esperas un norte fuerte, pide una pipa extra por tu cuenta."})
    # Precisión baja de algún producto (honestidad)
    for prod in ("MAGNA", "PREMIUM", "DIESEL"):
        d = datos["productos"][prod]
        if d["atinado_pct"] < 90:
            avisos.append({"icono": "🎯", "tono": "info",
                           "texto": f"El pronóstico de {NOMBRE[prod]} viene menos fino "
                                    f"(le atina al {d['atinado_pct']:.0f}% del volumen semanal): "
                                    f"trae un poco más de colchón en el pedido."})
    return avisos


# ============================================================================
#  GRÁFICA SVG (real vs pronóstico)  — inline, sin dependencias externas
# ============================================================================
def _svg_precision(fechas, real, pred, ancho=760, alto=150) -> str:
    """Mini-gráfica de líneas: real (navy sólida) vs pronóstico (oro punteada).

    Doble codificación (color + patrón) para que sea legible en b/n y con
    daltonismo. Sin ejes técnicos: solo la forma y el mensaje.
    """
    ml, mr, mt, mb = 8, 8, 12, 14
    W, H = ancho - ml - mr, alto - mt - mb
    vals = [v for v in list(real) + list(pred) if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if not vals:
        return ""
    vmin, vmax = min(vals) * 0.9, max(vals) * 1.05
    rng = max(vmax - vmin, 1)
    n = len(fechas)

    def x(i):
        return ml + (W * i / max(n - 1, 1))

    def y(v):
        return mt + H * (1 - (v - vmin) / rng)

    def path(serie):
        pts = []
        for i, v in enumerate(serie):
            if v is None or (isinstance(v, float) and math.isnan(v)):
                continue
            pts.append(f"{x(i):.1f},{y(v):.1f}")
        return " ".join(pts)

    real_pts = path(real)
    pred_pts = path(pred)
    # marcadores de semanas (cada 7)
    guias = "".join(
        f'<line x1="{x(i):.1f}" y1="{mt}" x2="{x(i):.1f}" y2="{mt+H}" stroke="#00000010" stroke-width="1"/>'
        for i in range(0, n, 7)
    )
    return f'''<svg viewBox="0 0 {ancho} {alto}" width="100%" preserveAspectRatio="xMidYMid meet" role="img"
      aria-label="Comparación de venta real contra el pronóstico de las últimas 4 semanas">
      {guias}
      <polyline fill="none" stroke="{ORO}" stroke-width="2.5" stroke-dasharray="5 4"
        stroke-linecap="round" stroke-linejoin="round" points="{pred_pts}"/>
      <polyline fill="none" stroke="{NAVY}" stroke-width="2.5"
        stroke-linecap="round" stroke-linejoin="round" points="{real_pts}"/>
    </svg>'''


# ============================================================================
#  PREPARACIÓN DE DATOS DEL DASHBOARD
# ============================================================================
def preparar_datos_dashboard(hist: pd.DataFrame, params: dict) -> dict:
    from . import calendario as C

    cap = params["pedido"]["capacidad_pipa_litros"]
    dias_seg = params["nortes"]["alerta_roja_dias"]

    # Auto-relleno de `real` en la bitácora con los datos ya llegados, y MAPE
    # acumulado modelo vs humano para la sección técnica del dashboard (03.6.3).
    actualizar_reales_bitacora(hist)
    mape_hist = mape_bitacora()

    origen_global = pd.Timestamp(hist["fecha"].max())
    fechas_forecast = pd.date_range(origen_global + pd.Timedelta(days=1), periods=7)
    iso = fechas_forecast[0].isocalendar()
    semana_id = f"{iso.year}-{int(iso.week):02d}"

    prod_out = {}
    for prod in params["productos"]:
        dfp = hist[hist["producto"] == prod]
        origen = pd.Timestamp(dfp["fecha"].max())
        fm = params["config_producto"][prod]["fondo_muerto"]
        s = dfp.set_index("fecha")["sdo_final"]
        sdo = float(s.loc[origen])
        util = sdo - fm
        cap_tanque = float(s.max()) * 1.05

        clima_df, clima_faltante = CL.cargar_clima(pd.date_range(dfp["fecha"].min(), origen + pd.Timedelta(days=7)))
        res = P.generar_pronostico(dfp, prod, params, clima_df, origen, con_banda=True)
        fc = res["forecast"]
        md = float(fc["pronostico"].mean())
        cobertura = util / md if md else 0.0

        # plan de pedido día a día (mantiene piso de seguridad, respeta tanque)
        floor_util = dias_seg * md
        saldo = sdo
        plan = []
        for _, row in fc.iterrows():
            v = row["pronostico"]
            pipas = 0
            while (saldo - v - fm) < floor_util and (saldo + cap) <= cap_tanque + 1:
                saldo += cap
                pipas += 1
            saldo -= v
            plan.append({"fecha": row["fecha"], "pipas": pipas, "venta": v,
                         "p20": row["p20"], "p80": row["p80"], "regla": row["regla"]})

        # walk-forward 4 semanas para la gráfica y el "atinado %"
        dias, real_arr, pred_arr, apes, semanas = [], [], [], [], []
        for k in (4, 3, 2, 1):
            o = origen - pd.Timedelta(days=7 * k)
            h = dfp[dfp["fecha"] <= o]
            if len(h) < params["backtest"]["train_min_dias"]:
                continue
            clk, _ = CL.cargar_clima(pd.date_range(h["fecha"].min(), o + pd.Timedelta(days=7)))
            f2 = P.generar_pronostico(h, prod, params, clk, o, con_banda=False)["forecast"].set_index("fecha")
            real = dfp.set_index("fecha")["ventas"]
            for f, r2 in f2.iterrows():
                rv = real.get(f, float("nan"))
                dias.append(f)
                pred_arr.append(float(r2["pronostico"]))
                real_arr.append(float(rv) if pd.notna(rv) else float("nan"))
                if pd.notna(rv) and rv > 0:
                    apes.append(abs(r2["pronostico"] - rv) / rv * 100)
            m = real.reindex(f2.index).notna()
            if m.sum():
                semanas.append((float(f2["pronostico"][m.values].sum()),
                                float(real.reindex(f2.index)[m.values].sum())))
        vol_err = (sum(abs(a - b) / b for a, b in semanas) / len(semanas) * 100) if semanas else float("nan")
        mape = (sum(apes) / len(apes)) if apes else float("nan")

        color, etiqueta, css = color_semaforo(cobertura)
        prod_out[prod] = {
            "nombre": NOMBRE[prod], "sdo": sdo, "util": util, "fondo": fm,
            "venta_media": md, "cobertura_dias": round(cobertura, 1),
            "color": color, "etiqueta": etiqueta, "css": css,
            "nivel_pct": max(6, min(100, cobertura / 10 * 100)),
            "pipas_total": sum(x["pipas"] for x in plan), "plan": plan,
            "forecast": fc, "deriva": res["deriva"], "n_train": res["n_train"],
            "min_train": res["min_train_fecha"], "clima_faltante": clima_faltante,
            "atinado_pct": round(100 - vol_err, 1) if not math.isnan(vol_err) else float("nan"),
            "mape": mape, "cap_tanque": cap_tanque,
            "graf": {"dias": dias, "real": real_arr, "pred": pred_arr},
        }

    # calendario de la semana
    cal = C.calendario_rango(fechas_forecast[0], fechas_forecast[-1], params)
    festivos_lft = [f"{f.day} de {MESES_ES[f.month]}" for f in cal.index[cal["festivo_lft"] == 1]]
    calendario_semana = {
        "hay_festivo_lft": bool((cal["festivo_lft"] == 1).any()),
        "festivos_lft": festivos_lft,
        "hay_quincena": bool((cal["quincena_laboral"] == 1).any()),
        "hay_fin_ciclo": bool((cal["fin_ciclo"] == 1).any()),
    }
    from . import reglas as R
    temporada_nortes = R.en_temporada_nortes(fechas_forecast[0], params)

    return {
        "semana_id": semana_id,
        "origen": origen_global,
        "fechas": list(fechas_forecast),
        "productos": prod_out,
        "calendario_semana": calendario_semana,
        "temporada_nortes": temporada_nortes,
        "clima_faltante": any(prod_out[p]["clima_faltante"] for p in prod_out),
        "mape_bitacora": mape_hist,
    }


# ============================================================================
#  RENDER HTML — DASHBOARD MODO HUMANO
# ============================================================================
def _icono_pipa(color=ORO) -> str:
    return (f'<svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">'
            f'<ellipse cx="12" cy="7" rx="8" ry="3.2" fill="{color}"/>'
            f'<path d="M4 7 v10 a8 3.2 0 0 0 16 0 V7" fill="{color}" opacity="0.85"/>'
            f'<ellipse cx="12" cy="7" rx="8" ry="3.2" fill="#ffffff" opacity="0.25"/>'
            f'<rect x="11" y="17" width="2" height="4" fill="{NAVY}"/></svg>')


def render_dashboard(datos: dict, params: dict) -> str:
    cap = params["pedido"]["capacidad_pipa_litros"]
    origen = datos["origen"]
    f0, f1 = datos["fechas"][0], datos["fechas"][-1]
    rango = (f"{f0.day} de {MESES_ES[f0.month]} al {f1.day} de {MESES_ES[f1.month]} de {f1.year}")
    veredicto = _veredicto(datos)
    avisos = _avisos(datos, params)

    # ---- Sección 2: semáforo ----
    tarjetas = []
    for prod in ("MAGNA", "PREMIUM", "DIESEL"):
        d = datos["productos"][prod]
        cob = d["cobertura_dias"]
        cob_txt = "menos de 1 día" if cob < 1 else f"~{cob:.0f} día{'s' if cob >= 2 else ''}"
        tarjetas.append(f'''
      <div class="tanque {d['css']}">
        <div class="circulo" style="background:{d['color']}">{cob_txt.split('~')[-1].split(' ')[0] if cob>=1 else '0'}</div>
        <h3>{d['nombre']}</h3>
        <p class="estado" style="color:{d['color']}">{d['etiqueta']}</p>
        <p class="dias">El tanque alcanza para <b>{cob_txt}</b></p>
        <div class="barra"><span style="width:{d['nivel_pct']:.0f}%;background:{d['color']}"></span></div>
        <p class="mini">Hoy tienes {d['util']:,.0f} L útiles · se vende ~{d['venta_media']:,.0f} L/día</p>
      </div>''')

    # ---- Sección 3: plan de la semana ----
    dias_html = []
    for i, f in enumerate(datos["fechas"]):
        dow = f.weekday()
        pipas_dia = {p: 0 for p in datos["productos"]}
        ventas_txt = []
        for prod in ("MAGNA", "PREMIUM", "DIESEL"):
            plan_i = datos["productos"][prod]["plan"][i]
            pipas_dia[prod] = plan_i["pipas"]
            ventas_txt.append((NOMBRE[prod], describe_pipa(plan_i["venta"], cap), plan_i["venta"]))
        pipas_html = ""
        for prod in ("MAGNA", "PREMIUM", "DIESEL"):
            n = pipas_dia[prod]
            if n:
                col = {"MAGNA": ORO, "PREMIUM": "#8B6F1E", "DIESEL": NAVY}[prod]
                pipas_html += f'<div class="pedido">{_icono_pipa(col)}<span>{n}× {NOMBRE[prod]}</span></div>'
        if not pipas_html:
            pipas_html = '<div class="sinpedido">— sin pedido —</div>'
        ventas_html = "".join(
            f'<li><b>{nom}:</b> {txt} <span class="lit">({lit:,.0f} L)</span></li>'
            for nom, txt, lit in ventas_txt)
        dias_html.append(f'''
      <div class="dia{' compra' if any(pipas_dia.values()) else ''}">
        <div class="fecha"><span class="dow">{DIAS_ES[dow]}</span><span class="num">{f.day}</span></div>
        {pipas_html}
        <ul class="ventas">{ventas_html}</ul>
      </div>''')

    # ---- Sección 4: gráficas ----
    graf_html = []
    for prod in ("MAGNA", "PREMIUM", "DIESEL"):
        d = datos["productos"][prod]
        g = d["graf"]
        svg = _svg_precision(g["dias"], g["real"], g["pred"])
        at = d["atinado_pct"]
        at_txt = f"le ha atinado al <b>{at:.0f}%</b> del volumen de la semana" if not math.isnan(at) else "aún sin historial suficiente"
        graf_html.append(f'''
      <div class="graf">
        <h4>{d['nombre']}</h4>
        {svg}
        <p class="graf-msg">En las últimas 4 semanas, el pronóstico {at_txt}.</p>
      </div>''')

    # ---- Sección 5: avisos ----
    if avisos:
        avisos_html = "".join(
            f'<li class="aviso {a["tono"]}"><span class="ic">{a["icono"]}</span><span>{html.escape(a["texto"])}</span></li>'
            for a in avisos)
    else:
        avisos_html = '<li class="aviso info"><span class="ic">✅</span><span>Semana tranquila: sin alertas.</span></li>'

    # ---- Sección 6: letras chiquitas (técnico) ----
    filas_tec = []
    for prod in ("MAGNA", "PREMIUM", "DIESEL"):
        d = datos["productos"][prod]
        fc = d["forecast"]
        band = " · ".join(f"{r['fecha'].strftime('%d/%m')}: {r['pronostico']:.0f} [{r['p20']:.0f}–{r['p80']:.0f}]"
                          for _, r in fc.iterrows())
        mape = d["mape"]
        filas_tec.append(f'''
        <tr><td><b>{d['nombre']}</b></td>
          <td>{d['mape']:.1f}%</td>
          <td>{d['deriva']:.3f}</td>
          <td>{d['n_train']}</td>
          <td>{d['min_train'].strftime('%Y-%m-%d') if d['min_train'] is not None else '—'}</td>
          <td>{d['fondo']:,} L</td></tr>''')
    band_rows = "".join(
        f'<tr><td><b>{datos["productos"][p]["nombre"]}</b></td><td class="mono">' +
        " · ".join(f"{r['fecha'].strftime('%d/%m')}: <b>{r['pronostico']:.0f}</b> ({r['p20']:.0f}–{r['p80']:.0f})"
                   for _, r in datos["productos"][p]["forecast"].iterrows()) + '</td></tr>'
        for p in ("MAGNA", "PREMIUM", "DIESEL"))
    xp = params["xgboost"]

    # --- MAPE acumulado modelo vs humano (de bitacora.csv) ---
    mb = datos.get("mape_bitacora", {})
    if mb:
        filas_mb = ""
        for p in ("MAGNA", "PREMIUM", "DIESEL"):
            if p in mb:
                m = mb[p]
                mh = f"{m['mape_humano']:.1f}% ({m['n_humano']})" if not math.isnan(m["mape_humano"]) else "— (sin decisión humana registrada)"
                filas_mb += (f'<tr><td><b>{NOMBRE[p]}</b></td><td>{m["mape_modelo"]:.1f}% ({m["n"]} días)</td>'
                             f'<td>{mh}</td></tr>')
        bloque_mb = (f'<p class="nota">Margen de error acumulado con datos ya realizados (de la bitácora), '
                     f'modelo vs decisión humana:</p>'
                     f'<table><tr><th>Producto</th><th>Modelo</th><th>Humano (n)</th></tr>{filas_mb}</table>')
    else:
        bloque_mb = ('<p class="nota">Margen de error acumulado modelo vs humano (bitácora): '
                     'aún sin días realizados esta semana; se irá llenando solo conforme lleguen los datos.</p>')

    return f'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pronóstico semanal SBH · {datos['semana_id']}</title>
<style>
  :root {{ --navy:{NAVY}; --oro:{ORO}; --crema:{CREMA}; --verde:{VERDE}; --ambar:{AMBAR}; --rojo:{ROJO}; }}
  * {{ box-sizing:border-box; }}
  html,body {{ margin:0; padding:0; max-width:100%; overflow-x:hidden; }}
  .qb {{ max-width:900px; margin:0 auto; padding:16px; background:var(--crema);
        font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; color:#2a2a2a;
        overflow-wrap:anywhere; word-break:normal; }}
  .qb svg {{ max-width:100%; height:auto; }}
  .qb h1,.qb h2,.qb h3,.qb h4 {{ font-family:Georgia,'Times New Roman',serif; color:var(--navy); margin:0; }}
  .qb .head {{ display:flex; justify-content:space-between; align-items:baseline; flex-wrap:wrap; gap:4px; margin-bottom:10px; }}
  .qb .head .est {{ font-weight:700; letter-spacing:1px; color:var(--oro); }}
  .qb .head .rango {{ color:#5a5a5a; font-size:.9rem; }}

  /* 1. Veredicto */
  .veredicto {{ background:var(--navy); color:var(--crema); border-radius:18px; padding:26px 24px;
    box-shadow:0 6px 22px #1f3a5f33; border-left:8px solid var(--oro); }}
  .veredicto .tag {{ color:var(--oro); font-weight:700; letter-spacing:2px; font-size:.8rem; }}
  .veredicto p {{ font-family:Georgia,serif; font-size:1.7rem; line-height:1.3; margin:8px 0 0; }}

  .sec-tit {{ font-size:1.15rem; margin:26px 0 12px; display:flex; align-items:center; gap:8px; }}
  .sec-tit::before {{ content:""; width:6px; height:22px; background:var(--oro); border-radius:3px; }}

  /* 2. Semáforo */
  .tanques {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }}
  .tanque {{ background:#fff; border-radius:16px; padding:18px 14px; text-align:center; box-shadow:0 2px 10px #0000000f; min-width:0; }}
  .tanque .circulo {{ width:64px; height:64px; border-radius:50%; margin:0 auto 8px; color:#fff;
    display:flex; align-items:center; justify-content:center; font-size:1.7rem; font-weight:800;
    font-family:Georgia,serif; box-shadow:inset 0 -4px 0 #00000022; }}
  .tanque h3 {{ font-size:1.15rem; }}
  .tanque .estado {{ font-weight:800; font-size:.8rem; letter-spacing:1px; margin:2px 0 6px; }}
  .tanque .dias {{ font-size:.95rem; margin:0 0 8px; }}
  .tanque .barra {{ height:12px; background:#eee; border-radius:8px; overflow:hidden; }}
  .tanque .barra span {{ display:block; height:100%; border-radius:8px; }}
  .tanque .mini {{ font-size:.72rem; color:#777; margin:8px 0 0; }}

  /* 3. Plan */
  .semana {{ display:grid; grid-template-columns:repeat(7,1fr); gap:8px; }}
  .dia {{ background:#fff; border-radius:12px; padding:8px 6px; text-align:center; box-shadow:0 2px 8px #0000000d;
    border-top:4px solid #e6e0d3; min-height:120px; min-width:0; }}
  .dia.compra {{ border-top-color:var(--oro); }}
  .dia .fecha {{ display:flex; flex-direction:column; line-height:1; margin-bottom:6px; }}
  .dia .dow {{ font-size:.72rem; color:#888; font-weight:700; text-transform:uppercase; }}
  .dia .num {{ font-family:Georgia,serif; font-size:1.3rem; color:var(--navy); font-weight:700; }}
  .dia .pedido {{ display:flex; align-items:center; justify-content:center; gap:3px; font-size:.72rem; font-weight:700; color:var(--navy); }}
  .dia .sinpedido {{ font-size:.68rem; color:#bbb; padding:6px 0; }}
  .dia .ventas {{ list-style:none; padding:0; margin:6px 0 0; text-align:left; font-size:.66rem; color:#555; }}
  .dia .ventas li {{ margin:2px 0; }}
  .dia .ventas .lit {{ color:#aaa; }}

  /* 4. Gráficas */
  .grafs {{ display:grid; grid-template-columns:1fr; gap:10px; }}
  .graf {{ background:#fff; border-radius:14px; padding:12px 14px; box-shadow:0 2px 8px #0000000d; }}
  .graf h4 {{ font-size:1rem; margin-bottom:2px; }}
  .graf-msg {{ font-size:.85rem; color:#444; margin:2px 0 0; }}
  .leyenda {{ display:flex; flex-wrap:wrap; gap:8px 18px; font-size:.78rem; color:#555; margin:2px 0 8px; }}
  .graf {{ min-width:0; }}
  .leyenda span {{ display:inline-flex; align-items:center; gap:6px; }}
  .sw {{ width:22px; height:0; border-top:3px solid; display:inline-block; }}

  /* 5. Avisos */
  .avisos {{ list-style:none; padding:0; margin:0; display:grid; gap:8px; }}
  .aviso {{ display:flex; gap:10px; background:#fff; border-radius:12px; padding:12px 14px;
    box-shadow:0 2px 8px #0000000d; border-left:5px solid var(--navy); font-size:.92rem; align-items:flex-start; }}
  .aviso.rojo {{ border-left-color:var(--rojo); }}
  .aviso.ambar {{ border-left-color:var(--ambar); }}
  .aviso.info {{ border-left-color:var(--oro); }}
  .aviso .ic {{ font-size:1.2rem; line-height:1.2; }}

  /* 6. Letras chiquitas */
  details.tec {{ margin-top:26px; background:#fff; border-radius:12px; padding:4px 14px; box-shadow:0 2px 8px #0000000d; }}
  details.tec summary {{ cursor:pointer; font-family:Georgia,serif; color:var(--navy); font-weight:700; padding:12px 0; font-size:1rem; }}
  details.tec table {{ width:100%; border-collapse:collapse; font-size:.8rem; margin:8px 0 14px; }}
  details.tec th,details.tec td {{ text-align:left; padding:6px 8px; border-bottom:1px solid #eee; }}
  details.tec th {{ color:#777; font-weight:600; }}
  details.tec .mono {{ font-family:ui-monospace,Menlo,monospace; font-size:.72rem; }}
  details.tec .nota {{ font-size:.78rem; color:#777; }}
  .pie {{ text-align:center; color:#999; font-size:.72rem; margin:18px 0 4px; }}

  @media (max-width:640px) {{
    .tanques {{ grid-template-columns:1fr; }}
    .semana {{ grid-template-columns:repeat(2,1fr); }}
    .veredicto p {{ font-size:1.35rem; }}
  }}
  @media (prefers-color-scheme:dark) {{
    .qb {{ background:#14202f; color:#e8e4da; }}
    .qb h1,.qb h2,.qb h3,.qb h4 {{ color:#dfe7f2; }}
    .tanque,.dia,.graf,.aviso,details.tec {{ background:#1e2d40; box-shadow:none; }}
    .dia .num {{ color:#dfe7f2; }}
    .tanque .mini {{ color:#9fb0c4; }}
  }}
</style>
</head>
<body>
<div class="qb">
  <div class="head">
    <span class="est">ESTACIÓN SBH · QUANTUM NORTE B</span>
    <span class="rango">Semana {rango}</span>
  </div>

  <!-- 1. VEREDICTO -->
  <div class="veredicto">
    <div class="tag">LO QUE TIENES QUE HACER ESTA SEMANA</div>
    <p>{html.escape(veredicto)}</p>
  </div>

  <!-- 2. SEMÁFORO -->
  <h2 class="sec-tit">¿Cómo están los tanques?</h2>
  <div class="tanques">{''.join(tarjetas)}</div>
  <p class="nota" style="font-size:.75rem;color:#888;margin:8px 2px 0;">
    🟢 verde = alcanza bien (más de 5 días) · 🟡 amarillo = va justo (3 a 5 días) · 🔴 rojo = se va a acabar (menos de 3 días)</p>

  <!-- 3. PLAN -->
  <h2 class="sec-tit">Plan de la semana</h2>
  <div class="semana">{''.join(dias_html)}</div>
  <p class="nota" style="font-size:.75rem;color:#888;margin:8px 2px 0;">
    Una pipa 🛢️ = {cap:,.0f} litros. Los días con borde dorado son los de pedido sugerido.</p>

  <!-- 4. GRÁFICA -->
  <h2 class="sec-tit">¿Qué tan atinados venimos?</h2>
  <div class="leyenda">
    <span><i class="sw" style="border-color:{NAVY}"></i> Lo que se vendió de verdad</span>
    <span><i class="sw" style="border-color:{ORO};border-top-style:dashed"></i> Lo que dijo el pronóstico</span>
  </div>
  <div class="grafs">{''.join(graf_html)}</div>

  <!-- 5. AVISOS -->
  <h2 class="sec-tit">Avisos de la semana</h2>
  <ul class="avisos">{avisos_html}</ul>

  <!-- 6. LETRAS CHIQUITAS -->
  <details class="tec">
    <summary>🔧 Números finos (para el CEO) — clic para ver</summary>
    <p class="nota">Margen de error = qué tanto se equivoca el pronóstico en promedio (más chico es mejor).
      Colchón de seguridad = cuánto se sube el pronóstico a propósito para no quedarnos cortos.
      Deriva = ajuste automático según cómo venía atinando.</p>
    <table>
      <tr><th>Producto</th><th>Margen de error<br><span style="font-weight:400;color:#aaa">(diario, últimas 4 sem)</span></th><th>Deriva</th><th>Días que aprendió</th><th>Aprende desde</th><th>Reserva mínima</th></tr>
      {''.join(filas_tec)}
    </table>
    <p class="nota">Pronóstico por día con su rango probable (piso–techo):</p>
    <table>{band_rows}</table>
    {bloque_mb}
    <p class="nota">Modelo: XGBoost cuantil α={xp['quantile_alpha']} (colchón de seguridad),
      {xp['n_estimators']} árboles, profundidad {xp['max_depth']}, lr {xp['learning_rate']}.
      Corrida basada en datos al {origen.strftime('%d/%m/%Y')}. Semana {datos['semana_id']}.</p>
  </details>

  <p class="pie">Generado automáticamente · Datos de SBH — uso interno · QUANTUM Insight</p>
</div>
</body>
</html>'''


# ============================================================================
#  ESCRITURA DE ARCHIVOS
# ============================================================================
def _dir_semana(semana_id: str) -> Path:
    d = config.SALIDAS / semana_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def escribir_pronostico_csv(datos: dict, destino: Path) -> Path:
    filas = []
    for prod in datos["productos"]:
        for _, r in datos["productos"][prod]["forecast"].iterrows():
            filas.append({"fecha": r["fecha"].strftime("%Y-%m-%d"), "producto": prod,
                          "pronostico": r["pronostico"], "p20": r["p20"], "p80": r["p80"]})
    df = pd.DataFrame(filas).sort_values(["fecha", "producto"])
    ruta = destino / "pronostico_semana.csv"
    df.to_csv(ruta, index=False)
    return ruta


def escribir_pedido_md(datos: dict, params: dict, destino: Path) -> Path:
    cap = params["pedido"]["capacidad_pipa_litros"]
    lineas = [f"# Pedido sugerido — Semana {datos['semana_id']}",
              f"_Estación SBH · datos al {datos['origen'].strftime('%d/%m/%Y')}_", ""]
    lineas.append(f"> {_veredicto(datos)}")
    lineas.append("")
    for prod in ("MAGNA", "PREMIUM", "DIESEL"):
        d = datos["productos"][prod]
        lineas.append(f"## {NOMBRE[prod]} — {d['pipas_total']} pipa(s) esta semana")
        dias_pedido = [f"{p['fecha'].strftime('%a %d/%m')}: {p['pipas']}×"
                       for p in d["plan"] if p["pipas"] > 0]
        if dias_pedido:
            lineas.append("- Días de recepción: " + ", ".join(dias_pedido))
        else:
            lineas.append("- Sin pedido: el tanque alcanza toda la semana.")
        # lógica en 3 líneas
        lineas.append(f"- Hoy hay {d['util']:,.0f} L útiles; se vende ~{d['venta_media']:,.0f} L/día "
                      f"(cobertura {d['cobertura_dias']:.1f} días).")
        lineas.append(f"- Regla: mantener siempre ≥{params['nortes']['alerta_roja_dias']} días de reserva "
                      f"sin pasar la capacidad del tanque; 1 pipa = {cap:,.0f} L.")
        lineas.append("")
    ruta = destino / "pedido_sugerido.md"
    ruta.write_text("\n".join(lineas), encoding="utf-8")
    return ruta


def escribir_dashboard(datos: dict, params: dict, destino: Path) -> Path:
    ruta = destino / "dashboard_semanal.html"
    ruta.write_text(render_dashboard(datos, params), encoding="utf-8")
    return ruta


def render_dashboard_multi(items: list[tuple[str, str]], registro: dict) -> str:
    """Dashboard combinado con SELECTOR de estación (un HTML).

    `items`: lista de (permiso_norm, html_completo_de_la_estacion). Cada estación
    va embebida en un <iframe srcdoc> autocontenido; el selector alterna cuál se
    ve y ajusta su altura. Es una vista local de conveniencia; el Drive sigue
    recibiendo el dashboard por estación en salidas/<PERMISO_NORM>/.
    """
    reg = registro.get("estaciones", {})
    def etiqueta(n):
        m = reg.get(n, {})
        return f'{m.get("clave_corta", n)} — {m.get("razon_social", "")}'.strip(" —")
    opciones = "".join(f'<option value="{n}">{html.escape(etiqueta(n))}</option>' for n, _ in items)
    frames = "".join(
        f'<iframe class="estframe" data-est="{n}" srcdoc="{html.escape(h, quote=True)}" '
        f'style="display:{"block" if i == 0 else "none"}"></iframe>'
        for i, (n, h) in enumerate(items))
    return f'''<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pronóstico semanal EESS — multi-estación</title>
<style>
  body {{ margin:0; font-family:-apple-system,'Segoe UI',Roboto,Arial,sans-serif; background:{CREMA}; }}
  .barra {{ position:sticky; top:0; z-index:5; background:{NAVY}; color:{CREMA};
    padding:10px 16px; display:flex; align-items:center; gap:12px; flex-wrap:wrap; }}
  .barra b {{ font-family:Georgia,serif; color:{ORO}; }}
  .barra select {{ font-size:1rem; padding:6px 10px; border-radius:8px; border:2px solid {ORO};
    background:#fff; color:{NAVY}; font-weight:700; max-width:100%; }}
  .estframe {{ width:100%; border:0; }}
  @media (prefers-color-scheme:dark) {{ body {{ background:#14202f; }} }}
</style></head><body>
  <div class="barra"><b>QUANTUM · EESS</b>
    <label>Estación:
      <select id="sel" onchange="cambiar(this.value)">{opciones}</select>
    </label>
  </div>
  {frames}
  <script>
    function ajustar(f){{ try{{ f.style.height = (f.contentWindow.document.documentElement.scrollHeight+20)+'px'; }}catch(e){{ f.style.height='1600px'; }} }}
    function cambiar(n){{
      document.querySelectorAll('.estframe').forEach(function(f){{
        var on = f.getAttribute('data-est')===n; f.style.display = on?'block':'none';
        if(on) ajustar(f);
      }});
    }}
    document.querySelectorAll('.estframe').forEach(function(f){{ f.addEventListener('load',function(){{ ajustar(f); }}); }});
    window.addEventListener('load',function(){{ var v=document.getElementById('sel').value; cambiar(v); }});
  </script>
</body></html>'''


def actualizar_bitacora(datos: dict, params: dict) -> Path:
    """Append idempotente a bitacora.csv. Clave: (fecha_corrida, producto, fecha_pronosticada).

    fecha_corrida = fecha de origen (dato más reciente) -> re-correr el mismo lunes
    no duplica filas. `decision_humana` es columna editable (se preserva si ya existe).
    """
    ruta = config.BITACORA_CSV
    corrida = datos["origen"].strftime("%Y-%m-%d")
    nuevas = []
    for prod in datos["productos"]:
        for _, r in datos["productos"][prod]["forecast"].iterrows():
            nuevas.append({
                "fecha_corrida": corrida, "producto": prod,
                "fecha_pronosticada": r["fecha"].strftime("%Y-%m-%d"),
                "pronostico": r["pronostico"], "real": "", "decision_humana": "",
            })
    df_new = pd.DataFrame(nuevas)
    cols = ["fecha_corrida", "producto", "fecha_pronosticada", "pronostico", "real", "decision_humana"]
    if ruta.exists():
        df_old = pd.read_csv(ruta, dtype=str)
        for c in cols:
            if c not in df_old.columns:
                df_old[c] = ""
        clave = ["fecha_corrida", "producto", "fecha_pronosticada"]
        existentes = set(map(tuple, df_old[clave].astype(str).values.tolist()))
        df_new = df_new[~df_new[clave].astype(str).apply(tuple, axis=1).isin(existentes)]
        df = pd.concat([df_old[cols], df_new[cols]], ignore_index=True)
    else:
        df = df_new[cols]
    df.to_csv(ruta, index=False)
    return ruta


def actualizar_reales_bitacora(hist: pd.DataFrame) -> tuple[Path, int]:
    """Rellena la columna `real` de la bitácora cuando ya llegó el dato de ese día.

    Idempotente: solo toca filas con `real` vacío y cuya fecha ya está en el
    histórico. Preserva `pronostico` y `decision_humana` (columna editable).
    """
    ruta = config.BITACORA_CSV
    if not ruta.exists():
        return ruta, 0
    b = pd.read_csv(ruta, dtype=str)
    if b.empty:
        return ruta, 0

    ventas = {(r.producto, r.fecha.strftime("%Y-%m-%d")): r.ventas
              for r in hist.itertuples() if pd.notna(r.ventas)}

    llenados = 0
    nuevos = []
    for _, row in b.iterrows():
        cur = row.get("real", "")
        vacio = pd.isna(cur) or str(cur).strip().lower() in ("", "nan")
        if vacio:
            v = ventas.get((row["producto"], row["fecha_pronosticada"]))
            if v is not None:
                nuevos.append(f"{float(v):.2f}")
                llenados += 1
            else:
                nuevos.append("")
        else:
            nuevos.append(cur)
    b["real"] = nuevos
    b.to_csv(ruta, index=False)
    return ruta, llenados


def mape_bitacora() -> dict:
    """MAPE acumulado modelo vs humano desde bitacora.csv (03.6.3).

    Devuelve {producto: {mape_modelo, mape_humano, n}} usando solo filas con
    `real` disponible. `mape_humano` requiere `decision_humana` numérica.
    """
    ruta = config.BITACORA_CSV
    out = {}
    if not ruta.exists():
        return out
    b = pd.read_csv(ruta)
    if b.empty or "real" not in b.columns:
        return out
    b = b[pd.to_numeric(b["real"], errors="coerce").notna()].copy()
    if b.empty:
        return out
    b["real"] = pd.to_numeric(b["real"], errors="coerce")
    b["pronostico"] = pd.to_numeric(b["pronostico"], errors="coerce")
    b["decision_humana"] = pd.to_numeric(b.get("decision_humana"), errors="coerce")
    b = b[b["real"] > 0]
    for prod, g in b.groupby("producto"):
        mm = (abs(g["pronostico"] - g["real"]) / g["real"] * 100).mean()
        gh = g[g["decision_humana"].notna()]
        mh = (abs(gh["decision_humana"] - gh["real"]) / gh["real"] * 100).mean() if len(gh) else float("nan")
        out[prod] = {"mape_modelo": float(mm), "mape_humano": float(mh),
                     "n": int(len(g)), "n_humano": int(len(gh))}
    return out


def detectar_drive(params: dict) -> Path | None:
    """Autodetecta el Google Drive montado en macOS según el patrón del yaml."""
    import glob as _glob
    patron = str(Path(params["drive"]["glob_base"]).expanduser())
    bases = sorted(_glob.glob(patron))
    if not bases:
        return None
    return Path(bases[0]) / params["drive"]["subruta_destino"]


def copiar_a_drive(semana_dir: Path, params: dict) -> tuple[bool, str]:
    destino_base = detectar_drive(params)
    if destino_base is None:
        return False, "No se detectó Google Drive montado (se omite la copia)."
    try:
        # Replica la estructura salidas/<PERMISO_NORM>/<AAAA-SS>/  (solo salidas)
        norm = config.estacion_actual or ""
        destino = destino_base / norm / semana_dir.name if norm else destino_base / semana_dir.name
        destino.mkdir(parents=True, exist_ok=True)
        for f in semana_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, destino / f.name)
        return True, f"Copiado a {destino}"
    except Exception as e:  # noqa: BLE001
        return False, f"Error copiando a Drive: {e}"


def generar_todo(datos: dict, params: dict, copiar_drive: bool = True) -> dict:
    destino = _dir_semana(datos["semana_id"])
    res = {
        "csv": escribir_pronostico_csv(datos, destino),
        "pedido": escribir_pedido_md(datos, params, destino),
        "dashboard": escribir_dashboard(datos, params, destino),
        "bitacora": actualizar_bitacora(datos, params),
        "dir": destino,
    }
    if copiar_drive:
        ok, msg = copiar_a_drive(destino, params)
        res["drive_ok"], res["drive_msg"] = ok, msg
    else:
        res["drive_ok"], res["drive_msg"] = False, "Copia a Drive desactivada (--no-drive)."
    return res
