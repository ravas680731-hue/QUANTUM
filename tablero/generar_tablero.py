#!/usr/bin/env python3
"""
Generador de Tableros EESS — CLI.

Dado el Excel mensual de una EESS y su config, produce un PDF de 5 páginas
(Carta horizontal) y lo deja en la carpeta de la EESS (y en /output).

Uso:
  python generar_tablero.py --config config/SBH.yaml [--periodo 2026-06]
  python generar_tablero.py --config config/GIN.yaml --excel /ruta/GIN_06_2026.xlsx
  python generar_tablero.py --all
"""
from __future__ import annotations
import argparse, base64, os, re, subprocess, sys, glob, datetime as dt
import yaml
import ingesta, kpis, charts as C

HERE = os.path.dirname(os.path.abspath(__file__))
MES_LARGO = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
             "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


# ----------------------------------------------------------------- resolución
def icloud_base(cfg):
    v = cfg.get("icloud_base", "auto")
    if v and v != "auto":
        return os.path.expanduser(v)
    home = os.path.expanduser("~")
    mac = os.path.join(home, "Library", "Mobile Documents", "com~apple~CloudDocs")
    if os.path.isdir(mac):
        return mac
    return os.path.join(home, "iCloudDrive")


def resolve_excel(cfg, periodo=None, override=None):
    if override:
        return override
    folder = os.path.join(icloud_base(cfg), cfg["carpeta_eess"])
    eess = cfg["eess_nombre_corto"]
    if periodo:
        y, m = periodo.split("-")
        name = cfg["patron_excel"].format(EESS=eess, MM=f"{int(m):02d}", YYYY=y)
        p = os.path.join(folder, name)
        if not os.path.isfile(p):
            raise SystemExit(f"No existe el Excel del periodo: {p}")
        return p
    # auto: último {EESS}_MM_YYYY.xlsx
    pat = re.compile(rf"^{re.escape(eess)}_(\d{{2}})_(\d{{4}})\.xlsx$", re.I)
    best = None
    for f in glob.glob(os.path.join(folder, "*.xlsx")):
        mm = pat.match(os.path.basename(f))
        if mm:
            key = (int(mm.group(2)), int(mm.group(1)))
            if best is None or key > best[0]:
                best = (key, f)
    if not best:
        raise SystemExit(f"No encontré ningún {eess}_MM_YYYY.xlsx en {folder}")
    return best[1]


def periodo_from_name(path):
    mm = re.search(r"_(\d{2})_(\d{4})\.xlsx$", os.path.basename(path))
    if mm:
        return int(mm.group(2)), int(mm.group(1))
    return 2026, 6


# ----------------------------------------------------------------- HTML
def _font_face():
    ttf = os.path.join(HERE, "assets", "fonts", "Inter.ttf")
    b64 = base64.b64encode(open(ttf, "rb").read()).decode()
    return (f"@font-face{{font-family:'Inter';font-weight:100 900;font-style:normal;"
            f"src:url(data:font/ttf;base64,{b64}) format('truetype');}}")


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
@page{size:Letter landscape;margin:8mm 9mm}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font-family:'Inter',sans-serif;color:#0F172A;font-variant-numeric:tabular-nums}
.page{width:261mm;height:192mm;page-break-after:always;display:flex;flex-direction:column;
      position:relative;overflow:hidden}
.page:last-child{page-break-after:auto}
.phead{display:flex;align-items:flex-end;justify-content:space-between;
       border-left:5px solid var(--ac);padding:0 0 6px 10px;margin-bottom:7px}
.eyebrow{font-size:9px;letter-spacing:.14em;text-transform:uppercase;color:#64748B;font-weight:700}
.phead h1{font-size:21px;font-weight:800;line-height:1.05;color:#0F172A}
.phead .sub{font-size:11px;font-style:italic;color:#64748B;margin-top:2px}
.brand{text-align:right}
.brand .nm{font-size:13px;font-weight:800;color:var(--ac)}
.brand .mo{font-size:10px;color:#64748B}
.grid{flex:1;display:grid;gap:7px}
.card{border:1px solid #E6E9EF;border-radius:8px;padding:7px 9px;background:#fff;
      box-shadow:0 1px 2px rgba(15,23,42,.04);display:flex;flex-direction:column;min-height:0}
.card h3{font-size:9.5px;text-transform:uppercase;letter-spacing:.06em;color:#334155;font-weight:700;margin-bottom:2px}
.card .cs{font-size:8.5px;color:#94A3B8;margin-bottom:3px}
.card .chart{flex:1;min-height:0;position:relative}
.kpirow{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-bottom:7px}
.kpi{border:1px solid #E6E9EF;border-radius:8px;padding:9px 11px;background:#fff}
.kpi .lb{font-size:9px;text-transform:uppercase;letter-spacing:.06em;color:#64748B;font-weight:700}
.kpi .hero{font-size:30px;font-weight:800;color:var(--ac);line-height:1.1;margin-top:3px}
.kpi .sl{font-size:9.5px;color:#64748B;margin-top:1px}
.chip{display:inline-block;font-size:9px;font-weight:700;padding:1px 7px;border-radius:10px;margin-top:4px}
.exec{border-top:2px solid var(--ac);margin-top:7px;padding-top:5px;
      display:grid;grid-template-columns:1fr 1fr;gap:2px 18px}
.exec .b{font-size:9.5px;color:#334155;line-height:1.32;display:flex;gap:5px}
.exec .b b{color:#0F172A}
.pfoot{display:flex;justify-content:space-between;font-size:8px;color:#94A3B8;margin-top:4px;padding-top:3px;border-top:1px solid #EEF1F6}
table.kpi-t{width:100%;border-collapse:collapse;font-size:9.5px}
table.kpi-t th{background:#F1F5F9;color:#475569;text-align:left;padding:3px 7px;font-size:8.5px;text-transform:uppercase;letter-spacing:.04em}
table.kpi-t th.num,table.kpi-t td.num{text-align:right}
table.kpi-t td{padding:3px 7px;border-bottom:1px solid #EEF1F6}
table.kpi-t tr:nth-child(even) td{background:#FAFBFD}
.secband td{background:var(--ac)!important;color:#fff;font-weight:700;font-size:8.5px;text-transform:uppercase;letter-spacing:.05em}
.cut{background:color-mix(in srgb,var(--ac) 12%,#fff)!important;font-weight:700}
.lread{font-weight:700}
"""


def esc(s): return C.html.escape(str(s))


def card(title, sub, svg):
    sub_h = f'<div class="cs">{esc(sub)}</div>' if sub else ""
    return f'<div class="card"><h3>{esc(title)}</h3>{sub_h}<div class="chart">{svg}</div></div>'


def exec_band(bullets):
    ic = {"up": ("▲", C.POS), "down": ("▼", C.NEG), "sq": ("■", "#64748B"), "ci": ("●", "#334155")}
    rows = []
    for kind, txt in bullets:
        sym, col = ic[kind]
        rows.append(f'<div class="b"><span style="color:{col};font-weight:800">{sym}</span><span>{txt}</span></div>')
    return '<div class="exec">' + "".join(rows) + "</div>"


def pfoot(fuente, pag, n=5):
    return (f'<div class="pfoot"><span>Fuente: {esc(fuente)}</span>'
            f'<span>CONFIDENCIAL · Solo uso interno · Junta de Accionistas</span>'
            f'<span>Pág. {pag} de {n}</span></div>')


def head(eyebrow, title, sub, nm, mo):
    return (f'<div class="phead"><div><div class="eyebrow">{esc(eyebrow)}</div>'
            f'<h1>{esc(title)}</h1><div class="sub">{esc(sub)}</div></div>'
            f'<div class="brand"><div class="nm">{esc(nm)}</div><div class="mo">{esc(mo)}</div></div></div>')


# ----------------------------------------------------------------- páginas
def build_html(model, k, cfg, anio, mes):
    ac = cfg["acento_primario"]
    nm = cfg["eess_nombre_legal"]; corto = cfg["eess_nombre_corto"]
    n = k["n"]; ML = charts_labels = ingesta.MESES[:n]
    periodo_txt = f"{MES_LARGO[0]}–{MES_LARGO[mes-1]} {anio}"
    corte_txt = f"{MES_LARGO[mes-1]} {anio}"
    fuente = f"Estados financieros {corto} · {corte_txt}"
    pages = []

    # ---- P1 Volumen y mix
    lit = model["litros"]
    tickets = {p: model["despachos"].get(p, {}).get("ticket", 0) for p in ["Magna", "Premium", "Diesel"]}
    p1 = head("01 · Operación", "Volumen, vehículos y mix de combustibles",
              f"Acumulado {periodo_txt} · litros y despachos", nm, corte_txt)
    g = '<div class="grid" style="grid-template-columns:1.3fr 1.3fr 1fr;grid-template-rows:1fr 1fr">'
    g += card("Volumen total de combustible", "Litros despachados por mes",
              C.bars(k["litros_tot_mes"][:n], ML, accent=ac, fmt="num", record=True))
    g += card("Litros por producto", "Apilado mensual (Magna·Premium·Diesel)",
              C.stacked({p: lit[p][:n] for p in lit}, ML))
    g += card("Mix de litros (acum.)", "Participación por producto",
              C.donut(k["mix"], colors=C.PROD, center=C.num_c(sum(k["mix"].values())), csub="litros"))
    g += card("Ticket promedio por producto", f"Importe/despacho · {corte_txt}",
              C.bars([tickets["Magna"], tickets["Premium"], tickets["Diesel"]],
                     ["Magna", "Premium", "Diesel"], accent=ac, fmt="money"))
    g += card("Utilidad Total (UT) por mes", "Serie mensual",
              C.bars(model["ut"][:n], ML, accent=ac, fmt="money", record=True))
    g += "</div>"
    litros_jun = k["litros_tot_mes"][n-1]; litros_prev = k["litros_tot_mes"][n-2] if n > 1 else litros_jun
    dvar = (litros_jun/litros_prev-1) if litros_prev else 0
    top_prod = max(k["mix"], key=k["mix"].get)
    p1 += g + exec_band([
        ("up" if dvar >= 0 else "down", f"Volumen de {esc(corte_txt)}: <b>{C.num_c(litros_jun)} L</b> ({C.pct(dvar)} vs mes previo)."),
        ("sq", f"<b>{esc(top_prod)}</b> concentra <b>{C.pct(k['mix'][top_prod]/sum(k['mix'].values()))}</b> del mix de litros acumulado."),
        ("ci", f"Ticket promedio Magna <b>${tickets['Magna']:,.0f}</b> · Premium <b>${tickets['Premium']:,.0f}</b> · Diesel <b>${tickets['Diesel']:,.0f}</b>."),
        ("up" if model['ut'][k['ut_record_i']] == max(model['ut'][:n]) else "sq",
         f"UT récord en <b>{MES_LARGO[k['ut_record_i']]}</b>: <b>${model['ut'][k['ut_record_i']]:,.0f}</b>."),
    ]) + pfoot(fuente, 1)
    pages.append(p1)

    # ---- P2 Resultados y gastos (6 paneles)
    p2 = head("02 · Resultados", "Resultados financieros y estructura de gastos",
              f"Acumulado {periodo_txt} · pesos y márgenes", nm, corte_txt)
    g = '<div class="grid" style="grid-template-columns:repeat(3,1fr);grid-template-rows:1fr 1fr">'
    g += card("Ventas por mes", "Ingresos mensuales",
              C.bars(model["ventas"][:n], ML, accent=ac, fmt="money", record=True))
    g += card("Utilidad bruta y margen", "Barras UB · línea margen %",
              C.bar_line(model["utilidad_bruta"][:n], k["margen_mes"][:n], ML, accent=ac))
    g += card("UB vs Gastos vs Resultado Op.", "Comparativo mensual",
              C.grouped({"UB": model["utilidad_bruta"][:n], "Gastos": model["gastos"][:n],
                         "Res. Op.": model["resultado_op"][:n]}, ML,
                        colors=["#1B7F5B", "#C0392B", ac]))
    g += card("EBITDA vs Resultado Operativo", "La diferencia ≈ Depreciación y amortización",
              C.grouped({"EBITDA": model["ebitda"][:n], "Res. Op.": model["resultado_op"][:n]}, ML,
                        colors=[ac, "#94A3B8"]))
    g += card("Gastos por mes", "Gasto operativo mensual",
              C.bars(model["gastos"][:n], ML, accent="#C0392B", fmt="money"))
    g += card("Composición de gastos", "Por categoría (acum.)",
              C.donut(model["gastos_categorias"], center=C.money_c(k["gastos_acum"]), csub="gasto acum."))
    g += "</div>"
    resop_ac = k["resultado_op_acum"]
    p2 += g + exec_band([
        ("up" if resop_ac >= 0 else "down", f"Resultado operativo acumulado: <b>{C.money_c(resop_ac)}</b> ({C.pct(resop_ac/k['ventas_acum'])} de ventas)."),
        ("sq", f"Margen bruto acumulado <b>{C.pct(k['margen_acum'])}</b> sobre ventas de <b>{C.money_c(k['ventas_acum'])}</b>."),
        ("ci", f"EBITDA acumulado <b>{C.money_c(k['ebitda_acum'])}</b>; brecha vs resultado op. = depreciación."),
        ("down" if resop_ac < 0 else "up",
         f"Mayor gasto: <b>{esc(max(model['gastos_categorias'], key=model['gastos_categorias'].get))}</b> "
         f"(<b>{C.pct(max(model['gastos_categorias'].values())/k['gastos_acum'])}</b>)."),
    ]) + pfoot(fuente, 2)
    pages.append(p2)

    # ---- P3 KPIs operativos (tabla)
    p3 = head("03 · KPIs operativos", "Capital de trabajo, eficiencia y estructura",
              f"Indicadores al corte de {corte_txt}", nm, corte_txt)
    p3 += kpi_table(k, ac) + exec_band([
        ("sq", f"Rotación de activo <b>{k['rot_activo']:.2f}×</b> (Ventas/Activo total)."),
        ("ci", f"Endeudamiento <b>{C.pct(k['endeudamiento'])}</b> · Apalancamiento <b>{k['apalancamiento']:.2f}×</b>."),
        ("up", f"Venta media diaria <b>{C.money_c(k['VMD'])}</b> · Costo medio diario <b>{C.money_c(k['CMD'])}</b>."),
        ("down" if k['ciclo'] > 0 else "up", f"Ciclo de conversión de efectivo <b>{k['ciclo']:.0f} días</b>."),
    ]) + pfoot(fuente, 3)
    pages.append(p3)

    # ---- P4 DuPont
    p4 = head("04 · Rentabilidad", "Análisis de rentabilidad — Modelo DuPont",
              f"ROE = Margen × Rotación × Apalancamiento · ROE acum. {C.pct(k['roe_acum'])}", nm, corte_txt)
    g = '<div class="grid" style="grid-template-columns:1.5fr 1fr;grid-template-rows:1fr 1fr">'
    g += (f'<div class="card" style="grid-row:span 2"><h3>ROE mensual</h3>'
          f'<div class="cs">Utilidad neta / Capital contable (verde+ / rojo−)</div>'
          f'<div class="chart">{C.bars(k["roe_mes"][:n], ML, semantic=True, fmt="pct", w=440, h=470)}</div></div>')
    g += card("Margen neto (UN/Ventas)", "Tendencia mensual",
              C.sparkline(k["margen_un_mes"][:n], ML, color=ac, fmt="pct"))
    g += card("Rotación (Ventas/Activo)", "Tendencia mensual",
              C.sparkline(k["rot_mes"][:n], ML, color="#1B7F5B", fmt="mult"))
    g += "</div>"
    p4 += g + exec_band([
        ("sq", f"ROE acumulado <b>{C.pct(k['roe_acum'])}</b> = margen {C.pct(k['dp_margen'])} × rot. {k['dp_rot']:.2f} × apal. {k['dp_apal']:.2f}."),
        ("up" if k['dp_margen'] >= 0 else "down", f"Margen neto acumulado <b>{C.pct(k['dp_margen'])}</b>."),
        ("ci", f"Apalancamiento financiero <b>{k['dp_apal']:.2f}×</b> (Activo/Capital)."),
        ("down" if k['roe_acum'] < 0 else "up", f"Palanca principal del ROE: {'rotación' if k['dp_rot']>k['dp_apal'] else 'apalancamiento'}."),
    ]) + pfoot(fuente, 4)
    pages.append(p4)

    # ---- P5 UT acumulada
    p5 = head("05 · Utilidad Total", "Dashboard de Utilidad Total (UT) acumulada",
              f"Acumulado {periodo_txt}", nm, corte_txt)
    reci = k["ut_record_i"]
    krow = ('<div class="kpirow">'
            f'<div class="kpi"><div class="lb">UT acumulada</div><div class="hero">{C.money_c(k["ut_acum"])}</div>'
            f'<div class="sl">{n} meses · {periodo_txt}</div></div>'
            f'<div class="kpi"><div class="lb">UT mes récord</div><div class="hero">{C.money_c(model["ut"][reci])}</div>'
            f'<div class="sl">{MES_LARGO[reci]} {anio}</div></div>'
            f'<div class="kpi"><div class="lb">UT promedio mensual</div><div class="hero">{C.money_c(k["ut_prom"])}</div>'
            f'<div class="sl">media {n} meses</div></div></div>')
    g = '<div class="grid" style="grid-template-columns:1.5fr 1fr;grid-template-rows:1fr">'
    g += card("UT por mes", "Serie mensual con récord",
              C.bars(model["ut"][:n], ML, accent=ac, fmt="money", record=True))
    g += card("Participación mensual de UT", "Peso de cada mes",
              C.donut({ML[i]: model["ut"][i] for i in range(n)}, center=C.money_c(k["ut_acum"]), csub="UT acum."))
    g += "</div>"
    p5 += krow + g + exec_band([
        ("up", f"UT acumulada <b>{C.money_c(k['ut_acum'])}</b> en {n} meses."),
        ("sq", f"Mejor mes: <b>{MES_LARGO[reci]}</b> con <b>{C.money_c(model['ut'][reci])}</b>."),
        ("ci", f"Promedio mensual <b>{C.money_c(k['ut_prom'])}</b>."),
        ("up" if model['ut'][n-1] >= k['ut_prom'] else "down",
         f"{esc(corte_txt)} {'por encima' if model['ut'][n-1]>=k['ut_prom'] else 'por debajo'} del promedio (<b>{C.money_c(model['ut'][n-1])}</b>)."),
    ]) + pfoot(fuente, 5)
    pages.append(p5)

    body = "".join(f'<section class="page" style="--ac:{ac}">{p}</section>' for p in pages)
    return (f"<!doctype html><html lang='es'><head><meta charset='utf-8'>"
            f"<style>{_font_face()}{CSS}</style></head><body>{body}</body></html>")


def _lectura(kind):
    # kind in {'mejora','estable','deterioro','neutral'}
    cmap = {"mejora": ("Mejora", "#1B7F5B", "#E7F3EE"),
            "estable": ("Estable", "#64748B", "#EEF1F6"),
            "deterioro": ("Deterioro", "#C0392B", "#F7E7E5"),
            "neutral": ("—", "#94A3B8", "#F1F5F9")}
    t, col, bg = cmap[kind]
    return f'<span class="chip" style="color:{col};background:{bg}">{t}</span>'


def kpi_table(k, ac):
    def money(v): return f"${v:,.0f}"
    def band(v, good, ok, invert=False):
        if invert:
            return "mejora" if v <= good else ("estable" if v <= ok else "deterioro")
        return "mejora" if v >= good else ("estable" if v >= ok else "deterioro")
    secs = [
        ("Ingresos y costos", [
            ("Venta media diaria (VMD)", money(k["VMD"]), "neutral"),
            ("Costo medio diario (CMD)", money(k["CMD"]), "neutral"),
            ("Ventas acumuladas", money(k["ventas_acum"]), "neutral"),
            ("Margen bruto acumulado", C.pct(k["margen_acum"]), band(k["margen_acum"], .06, .04)),
        ]),
        ("Ciclo de efectivo", [
            ("Días de cuentas por cobrar", f"{k['dias_cxc']:.0f} días", band(k["dias_cxc"], 15, 30, invert=True)),
            ("Días de inventario", f"{k['dias_inv']:.0f} días", "neutral" if not k["dias_inv"] else band(k["dias_inv"], 15, 30, invert=True)),
            ("Días de cuentas por pagar", f"{k['dias_cxp']:.0f} días", "neutral"),
            ("Ciclo de conversión de efectivo", f"{k['ciclo']:.0f} días", band(k["ciclo"], 0, 30, invert=True)),
        ]),
        ("Rotación y eficiencia", [
            ("Rotación de activo total", f"{k['rot_activo']:.2f}×", band(k["rot_activo"], 1.5, 1.0)),
            ("Rotación de inventario", (f"{k['rot_inv']:.1f}×" if k['rot_inv'] else "n/d"), "neutral"),
        ]),
        ("Estructura financiera", [
            ("Endeudamiento (Pasivo/Activo)", C.pct(k["endeudamiento"]), band(k["endeudamiento"], .40, .60, invert=True)),
            ("Apalancamiento (Activo/Capital)", f"{k['apalancamiento']:.2f}×", band(k["apalancamiento"], 1.5, 2.0, invert=True)),
            ("Capitalización (PLP/(PLP+Capital))", C.pct(k["capitalizacion"]), "neutral"),
        ]),
    ]
    rows = ['<table class="kpi-t"><tr><th>Indicador</th><th class="num">Valor al corte</th><th>Lectura</th></tr>']
    for sec, items in secs:
        rows.append(f'<tr class="secband"><td colspan="3">{esc(sec)}</td></tr>')
        for name, val, kind in items:
            rows.append(f'<tr><td>{esc(name)}</td><td class="num cut">{esc(val)}</td><td>{_lectura(kind)}</td></tr>')
    rows.append("</table>")
    return ('<div class="card" style="flex:1;padding:12px 14px"><h3>Indicadores operativos y financieros</h3>'
            + "".join(rows) + "</div>")


# ----------------------------------------------------------------- render
def render_pdf(html, out_pdf):
    tmp = out_pdf + ".html"
    open(tmp, "w", encoding="utf-8").write(html)
    exe = detect_chromium()
    env = dict(os.environ)
    if exe:
        env["TABLERO_CHROMIUM_PATH"] = exe
    r = subprocess.run(["node", os.path.join(HERE, "render_pdf.mjs"), tmp, out_pdf],
                       cwd=HERE, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"Fallo el render con Chromium:\n{r.stderr}")
    os.remove(tmp)


def detect_chromium():
    if os.environ.get("TABLERO_CHROMIUM_PATH"):
        return os.environ["TABLERO_CHROMIUM_PATH"]
    root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
    for d in sorted(glob.glob(os.path.join(root, "chromium-*")), reverse=True):
        for cand in ("chrome-linux/chrome", "chrome-mac/Chromium.app/Contents/MacOS/Chromium"):
            p = os.path.join(d, cand)
            if os.path.exists(p):
                return p
    return None


def verify_fonts(pdf):
    try:
        r = subprocess.run(["pdffonts", pdf], capture_output=True, text=True)
        if "Inter" in r.stdout:
            return "Inter (OK)"
        if "DejaVu" in r.stdout:
            return "DejaVu (¡falló el embebido de Inter!)"
        return r.stdout.splitlines()[2] if len(r.stdout.splitlines()) > 2 else "?"
    except FileNotFoundError:
        return "pdffonts no disponible"


# ----------------------------------------------------------------- CLI
def run_one(cfg_path, periodo=None, excel=None, outdir=None):
    cfg = yaml.safe_load(open(cfg_path, encoding="utf-8"))
    xls = resolve_excel(cfg, periodo, excel)
    anio, mes = periodo_from_name(xls) if not periodo else (int(periodo[:4]), int(periodo[5:7]))
    model = ingesta.ingest(xls)
    k = kpis.compute(model, anio=anio)
    html = build_html(model, k, cfg, anio, mes)

    corto = cfg["eess_nombre_corto"]
    fname = f"{corto}_Dashboard_{anio}{mes:02d}_v01.pdf"
    outdir = outdir or os.path.join(HERE, "output", corto)
    os.makedirs(outdir, exist_ok=True)
    out_pdf = os.path.join(outdir, fname)
    render_pdf(html, out_pdf)

    placed = [out_pdf]
    if cfg.get("salida_en_carpeta_eess"):
        folder = os.path.join(icloud_base(cfg), cfg["carpeta_eess"])
        if os.path.isdir(folder):
            import shutil
            dst = os.path.join(folder, fname)
            shutil.copy(out_pdf, dst); placed.append(dst)

    print(f"[{corto}] periodo={anio}-{mes:02d}  excel={os.path.basename(xls)}")
    print(f"         ventas_acum={model and sum(model['ventas']):,.0f}  n_meses={k['n']}  fuente_font={verify_fonts(out_pdf)}")
    for p in placed:
        print(f"         PDF -> {p}")
    return out_pdf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--periodo", help="YYYY-MM")
    ap.add_argument("--excel", help="ruta directa al Excel (override)")
    ap.add_argument("--outdir")
    ap.add_argument("--all", action="store_true", help="procesa todos los config/*.yaml")
    a = ap.parse_args()
    if a.all:
        for cfg in sorted(glob.glob(os.path.join(HERE, "config", "*.yaml"))):
            run_one(cfg, a.periodo, None, a.outdir)
    elif a.config:
        run_one(a.config, a.periodo, a.excel, a.outdir)
    else:
        ap.error("indica --config <archivo.yaml> o --all")


if __name__ == "__main__":
    main()
