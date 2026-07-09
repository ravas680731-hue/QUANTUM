"""
Ingesta del Excel mensual de una EESS -> modelo canónico (dict).

Diseñado para el modo "cualquier EESS": localiza hojas por sinónimos y filas
por etiqueta (no por número fijo), porque las EESS difieren entre sí
(p. ej. la Utilidad Neta cae en la fila 71 en SBH y en la 70 en GIN).
Si falta una hoja o fila crítica, aborta con un mensaje claro — no inventa.
"""
from __future__ import annotations
import re
import unicodedata
import datetime as dt
import openpyxl

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
         "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _norm(s) -> str:
    if s is None:
        return ""
    s = str(s)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


class IngestaError(Exception):
    pass


class Workbook:
    def __init__(self, path):
        self.wb = openpyxl.load_workbook(path, data_only=True)
        self._sheets = {_norm(ws.title): ws for ws in self.wb.worksheets}

    def sheet(self, *nombres):
        """Primera hoja cuyo título contenga alguno de los sinónimos dados."""
        want = [_norm(n) for n in nombres]
        for key, ws in self._sheets.items():
            if any(w in key for w in want):
                return ws
        raise IngestaError(
            f"No encontré una hoja que coincida con {nombres}. "
            f"Hojas disponibles: {[ws.title for ws in self.wb.worksheets]}")


def _find_row(ws, *labels, col=1, upto=90):
    """Fila cuyo texto en `col` contenga alguna etiqueta (normalizada)."""
    want = [_norm(l) for l in labels]
    for r in range(1, min(upto, ws.max_row) + 1):
        v = _norm(ws.cell(r, col).value)
        if v and any(w in v for w in want):
            return r
    return None


def _month_cols_edo(ws, header_row):
    """Columnas de Ene..Dic en EDO RESULT (por el encabezado de meses)."""
    cols = {}
    for c in range(1, ws.max_column + 1):
        v = _norm(ws.cell(header_row, c).value)
        for i, m in enumerate(MESES):
            if v.startswith(_norm(["enero","febrero","marzo","abril","mayo","junio",
                                   "julio","agosto","septiembre","octubre","noviembre",
                                   "diciembre"][i])):
                cols[i] = c
    return cols


def _series(ws, row, month_cols):
    out = [0.0] * 12
    if row is None:
        return out
    for i, c in month_cols.items():
        v = ws.cell(row, c).value
        out[i] = float(v) if isinstance(v, (int, float)) else 0.0
    return out


def ingest(path: str) -> dict:
    wb = Workbook(path)
    model = {"meses_nombres": MESES}

    # ---------------- EDO RESULT (estado de resultados mensual) ----------------
    edo = wb.sheet("edo result", "estado de result")
    hdr = _find_row(edo, "enero") or 10
    mc = _month_cols_edo(edo, hdr)
    if len(mc) < 12:
        # fallback: asume B..M
        mc = {i: i + 2 for i in range(12)}

    r_ventas = _find_row(edo, "4000000000", "ingresos")
    r_ub = _find_row(edo, "utilidad o perdida bruta", "utilidad bruta")
    r_gastos = _find_row(edo, "6000000000 - gastos", "6000000000")
    r_resop = _find_row(edo, "ganancias comerciales")
    r_ebitda = _find_row(edo, "ebitda")
    r_otros = _find_row(edo, "8000000000", "otros ingresos y egresos")
    r_neta = _find_row(edo, "periodo ganancias", "utilidad neta")
    for name, r in [("Ventas", r_ventas), ("Utilidad Bruta", r_ub), ("Gastos", r_gastos),
                    ("Resultado Operativo", r_resop), ("EBITDA", r_ebitda),
                    ("Utilidad Neta", r_neta)]:
        if r is None:
            raise IngestaError(f"No encontré la fila de '{name}' en EDO RESULT.")

    model["ventas"] = _series(edo, r_ventas, mc)
    model["costo"] = _series(edo, _find_row(edo, "5000000000", "costo de ventas"), mc)
    model["utilidad_bruta"] = _series(edo, r_ub, mc)
    model["gastos"] = _series(edo, r_gastos, mc)
    model["resultado_op"] = _series(edo, r_resop, mc)
    model["ebitda"] = _series(edo, r_ebitda, mc)
    model["otros_ingresos"] = _series(edo, r_otros, mc)
    model["utilidad_neta"] = _series(edo, r_neta, mc)

    # Composición de gastos por categoría (sublíneas 61.. y 62.. del EDO)
    cat_map = [
        ("Sueldos y salarios", ["sueldos y salarios"]),
        ("Honorarios", ["honorarios"]),
        ("Mantenimiento", ["mantenimiento"]),
        ("Depreciación", ["depreciacion"]),
        ("Estudios y proyectos", ["estudios analisis y proyectos", "estudios y proyectos"]),
        ("No deducibles", ["6200000000", "no deducibles"]),
    ]
    gastos_cat = {}
    for label, keys in cat_map:
        r = _find_row(edo, *keys, upto=edo.max_row)
        gastos_cat[label] = sum(_series(edo, r, mc)) if r else 0.0
    total_gastos = sum(model["gastos"])
    gastos_cat["Otros gastos admin."] = max(0.0, total_gastos - sum(gastos_cat.values()))
    model["gastos_categorias"] = gastos_cat

    # Detalle de gastos por concepto (subcuentas hoja 61.. y 62.. del EDO).
    detalle = []
    for r in range(1, edo.max_row + 1):
        code = edo.cell(r, 1).value
        if not isinstance(code, str):
            continue
        mm = re.match(r"\s*(6[12]\d{8})\s*-\s*(.+)", code)
        if not mm:
            continue
        codigo = mm.group(1)
        if codigo in ("6100000000", "6200000000"):   # padres, no hoja
            continue
        serie = _series(edo, r, mc)
        detalle.append({"codigo": codigo, "nombre": mm.group(2).strip(),
                        "serie": serie, "total": sum(serie)})
    model["gastos_detalle"] = detalle

    # meses poblados = aquellos con ventas != 0
    model["n_meses"] = sum(1 for v in model["ventas"] if abs(v) > 1e-6)

    # ---------------- VENTAS LITROS (litros por producto, año en curso) --------
    model["litros"] = _ingest_litros(wb)

    # ---------------- UT (utilidad total mensual) ------------------------------
    model["ut"] = _ingest_ut(wb)

    # ---------------- DESPACHOS (mes de corte) ---------------------------------
    model["despachos"] = _ingest_despachos(wb)

    # ---------------- BALANZA (AT, PT, CC, CxC, inv, CxP) ----------------------
    model["balanza"] = _ingest_balanza(wb)

    # Inventario: cuenta "Almacén" del Balance General en ANALISIS FINANCIERO
    # (más fiable que la balanza de comprobación, donde no viene desglosado).
    inv = _ingest_inventario(wb)
    if inv:
        model["balanza"]["inventario"] = inv

    # Vehículos del mes de corte: fila TOTALES de DESPACHOS (col despachos).
    model["vehiculos_mes"] = _ingest_vehiculos(wb)

    # Libro mayor de gastos: por concepto y por cuenta de contrapartida.
    model["gastos_libro"] = _ingest_gastos_libro(wb)

    # razón social (de EDO RESULT, fila de título)
    tit = None
    for r in range(1, 8):
        for c in range(1, min(6, edo.max_column) + 1):
            v = edo.cell(r, c).value
            if isinstance(v, str) and len(v.strip()) > 6 and "estado de result" not in _norm(v):
                if _norm(v) not in ("", ) and not v.strip().startswith(("Del", "del")):
                    tit = tit or v.strip()
    model["razon_social_excel"] = tit
    return model


def _ingest_litros(wb):
    ws = wb.sheet("ventas litros", "ventas de litros")
    year = 2026
    # localiza la columna del año en curso: fila con "Mes" y años 2021..2026
    year_col = None
    for r in range(1, min(70, ws.max_row) + 1):
        for c in range(1, ws.max_column + 1):
            v = ws.cell(r, c).value
            if isinstance(v, (int, float)) and int(v) == year:
                year_col = c
                break
        if year_col:
            break
    if not year_col:
        raise IngestaError("No localicé la columna del año en curso en VENTAS LITROS.")

    def block(prod_keys):
        # encuentra el título del bloque (magna/premium/diesel) y lee los 12 meses
        vals = [0.0] * 12
        start = None
        for r in range(1, ws.max_row + 1):
            joined = " ".join(_norm(ws.cell(r, c).value).replace(" ", "")
                              for c in range(1, min(6, ws.max_column) + 1))
            if any(k in joined for k in prod_keys):
                start = r
                break
        if start is None:
            return vals
        # a partir de start, busca filas cuyo col B sea ENE..DIC
        found = 0
        for r in range(start, min(start + 25, ws.max_row) + 1):
            mlabel = _norm(ws.cell(r, 2).value)
            for i, m in enumerate(["ene","feb","mar","abr","may","jun",
                                   "jul","ago","sep","oct","nov","dic"]):
                if mlabel == m:
                    v = ws.cell(r, year_col).value
                    vals[i] = float(v) if isinstance(v, (int, float)) else 0.0
                    found += 1
            if found >= 12:
                break
        return vals

    return {
        "Magna": block(["magna"]),
        "Premium": block(["premium"]),
        "Diesel": block(["diesel", "diésel"]),
    }


def _ingest_ut(wb):
    ws = wb.sheet("ut")
    vals = [0.0] * 12
    for r in range(1, ws.max_row + 1):
        for c in range(1, ws.max_column + 1):
            v = ws.cell(r, c).value
            mi = None
            if isinstance(v, dt.datetime):
                mi = v.month - 1
            elif isinstance(v, str) and re.match(r"20\d\d-\d\d-\d\d", v):
                mi = int(v[5:7]) - 1
            if mi is not None:
                # valor numérico en la siguiente columna no vacía
                for cc in range(c + 1, ws.max_column + 1):
                    nv = ws.cell(r, cc).value
                    if isinstance(nv, (int, float)):
                        vals[mi] = float(nv)
                        break
    return vals


def _ingest_despachos(wb):
    ws = wb.sheet("despachos")
    prods = {}
    for r in range(1, ws.max_row + 1):
        prod = _norm(ws.cell(r, 1).value)
        horario = ws.cell(r, 2).value
        if prod in ("magna", "premium", "diesel", "diésel") and (horario is None or str(horario).strip() == ""):
            desp = ws.cell(r, 3).value
            vol = ws.cell(r, 4).value
            imp = ws.cell(r, 5).value
            if isinstance(desp, (int, float)) and isinstance(imp, (int, float)):
                key = prod.capitalize().replace("Diésel", "Diesel")
                prods[key] = {
                    "despachos": float(desp),
                    "litros": float(vol) if isinstance(vol, (int, float)) else 0.0,
                    "importe": float(imp),
                    "ticket": float(imp) / float(desp) if desp else 0.0,
                }
    return prods


def _ingest_balanza(wb):
    ws = wb.sheet("balanza")
    saldo_col, hdr = None, 3
    for r in range(1, 8):
        for c in range(1, ws.max_column + 1):
            if _norm(ws.cell(r, c).value) == "saldo":
                saldo_col, hdr = c, r
    if saldo_col is None:
        saldo_col, hdr = ws.max_column, 3

    groups = {str(i): 0.0 for i in range(1, 9)}
    cxc = inv = cxp = plp = 0.0
    for r in range(hdr + 1, ws.max_row + 1):
        code = ws.cell(r, 1).value
        if not isinstance(code, str):
            continue
        m = re.match(r"\s*(\d)", code)
        if not m:
            continue
        val = ws.cell(r, saldo_col).value
        if not isinstance(val, (int, float)):
            continue
        val = float(val)
        g = m.group(1)
        groups[g] += val
        name = _norm(code)
        codenum = re.match(r"\s*(\d+)", code).group(1)
        if g == "1" and ("cliente" in name or "tarjeta" in name or codenum.startswith("11000400")):
            cxc += val
        if g == "1" and ("inventario" in name or "almacen" in name or "mercancia" in name):
            inv += val
        if g == "2" and ("proveedor" in name or codenum.startswith("21")):
            cxp += abs(val)
        if g == "2" and ("largo plazo" in name or "hipotec" in name or "prestamo" in name):
            plp += abs(val)

    return {
        "AT": groups["1"],
        "PT": abs(groups["2"]),
        "CC": abs(groups["3"]),
        "ingresos": abs(groups["4"]),
        "costos": abs(groups["5"]),
        "gastos": abs(groups["6"]),
        "CxC": cxc, "inventario": inv, "CxP": cxp, "PLP": plp,
    }


def _ingest_inventario(wb):
    """Cuenta 'Almacén' del Balance General en ANALISIS FINANCIERO, año en curso.

    El bloque (Q..W) trae columnas 2024 | % | 2025 | % | 2026 | %; tomamos el
    valor del año más reciente (la última columna de año del encabezado).
    """
    try:
        ws = wb.sheet("analisis financiero", "análisis financiero")
    except IngestaError:
        return 0.0
    # 1) localiza la celda etiqueta 'Almacén'
    row_a = col_a = None
    for r in range(1, ws.max_row + 1):
        for c in range(1, ws.max_column + 1):
            if _norm(ws.cell(r, c).value) in ("almacen", "almacenes", "inventario", "inventarios"):
                row_a, col_a = r, c
                break
        if row_a:
            break
    if not row_a:
        return 0.0
    # 2) columna del año más reciente en el encabezado A LA DERECHA de la etiqueta
    year_col = None
    for r in range(1, row_a):
        years = [(c, int(ws.cell(r, c).value)) for c in range(col_a + 1, min(col_a + 12, ws.max_column) + 1)
                 if isinstance(ws.cell(r, c).value, (int, float))
                 and 2015 <= int(ws.cell(r, c).value) <= 2100]
        if years:
            year_col = max(years, key=lambda t: t[1])[0]
            break
    if not year_col:
        return 0.0
    v = ws.cell(row_a, year_col).value
    return float(v) if isinstance(v, (int, float)) else 0.0


def _ingest_gastos_libro(wb):
    """Recorre la hoja de gastos (libro mayor) agrupando por concepto (bloque)
    y por cuenta de contrapartida. Devuelve una lista de conceptos:
    {concepto, total, n_movs, contrapartidas: [(nombre, monto, n), ...]}.
    """
    import datetime as _dt
    try:
        ws = wb.sheet("gastos ene", "gastos ")
    except IngestaError:
        return []
    # encabezado: localizar columnas de comentario / contrapartida / monto
    col_com, col_contra, col_monto = 2, 3, 4
    conceptos = []
    actual = None
    for r in range(1, ws.max_row + 1):
        a = ws.cell(r, 1).value
        b = ws.cell(r, col_com).value
        monto = ws.cell(r, col_monto).value
        es_fecha = isinstance(a, _dt.datetime) or (isinstance(a, str) and re.match(r"20\d\d-\d\d-\d\d", a))
        # cabecera de bloque: A no es fecha, B trae el nombre del concepto, sin monto
        if not es_fecha and isinstance(b, str) and b.strip() and not isinstance(monto, (int, float)):
            if _norm(b) in ("comentarios",):
                continue
            actual = {"concepto": b.strip(), "total": 0.0, "n_movs": 0, "_cp": {}}
            conceptos.append(actual)
            continue
        if actual is not None and isinstance(monto, (int, float)):
            actual["total"] += float(monto)
            actual["n_movs"] += 1
            cp = ws.cell(r, col_contra).value
            cp = cp.strip() if isinstance(cp, str) and cp.strip() else "(sin contrapartida)"
            e = actual["_cp"].get(cp, [0.0, 0])
            e[0] += float(monto); e[1] += 1
            actual["_cp"][cp] = e
    # ordena contrapartidas por monto desc y limpia
    out = []
    for c in conceptos:
        if c["n_movs"] == 0:
            continue
        cps = sorted(([k, v[0], v[1]] for k, v in c["_cp"].items()), key=lambda x: -x[1])
        out.append({"concepto": c["concepto"], "total": c["total"],
                    "n_movs": c["n_movs"], "contrapartidas": cps})
    return out


def _ingest_vehiculos(wb):
    """Vehículos del mes de corte: fila TOTALES de DESPACHOS, columna despachos."""
    try:
        ws = wb.sheet("despachos")
    except IngestaError:
        return 0
    for r in range(1, ws.max_row + 1):
        if _norm(ws.cell(r, 1).value) in ("totales", "total"):
            v = ws.cell(r, 3).value
            if isinstance(v, (int, float)):
                return int(v)
    return 0
