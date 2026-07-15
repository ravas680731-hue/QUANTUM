"""calendario.py — calendario de 4 capas autogenerable por año (03.3).

Capas:
 (1) LFT Art.74: 1-ene, 1er lun feb, 3er lun mar, 1-may, 16-sep, 3er lun nov, 25-dic
 (2) escolar: 5-may, 10-may, 15-may
 (3) Semana Santa (computus de Gauss): Jue/Vie Santo + vacación SEP [Pascua-6, Pascua+7]
 (4) partido_mx / evento_tv desde yaml

Extras: vac_invierno (<=6-ene), fin_ciclo (10-15 jul),
regreso_clases (1-15 sep, prior 0.0), gr (12-dic -> 31-dic), quincena (14-16 y 29-01).
"""
from __future__ import annotations

import datetime as dt

import pandas as pd


# --- Semana Santa: algoritmo de Gauss / anónimo gregoriano ------------------
def domingo_pascua(anio: int) -> dt.date:
    """Domingo de Pascua (Gregoriano). Verificado: 2026=5-abr, 2027=28-mar."""
    a = anio % 19
    b = anio // 100
    c = anio % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    ll = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ll) // 451
    mes = (h + ll - 7 * m + 114) // 31
    dia = ((h + ll - 7 * m + 114) % 31) + 1
    return dt.date(anio, mes, dia)


def _nth_weekday(anio: int, mes: int, weekday: int, n: int) -> dt.date:
    """n-ésimo `weekday` (lunes=0) del mes."""
    d = dt.date(anio, mes, 1)
    delta = (weekday - d.weekday()) % 7
    return d + dt.timedelta(days=delta + 7 * (n - 1))


def festivos_lft_puente(anio: int) -> set[dt.date]:
    """Festivos LFT movibles a lunes (generan fin de semana largo / 'puente')."""
    return {
        _nth_weekday(anio, 2, 0, 1),            # 1er lunes de febrero (Constitución)
        _nth_weekday(anio, 3, 0, 3),            # 3er lunes de marzo (Benito Juárez)
        _nth_weekday(anio, 11, 0, 3),           # 3er lunes de noviembre (Revolución)
    }


def festivos_lft_fijo(anio: int) -> set[dt.date]:
    """Festivos LFT de fecha fija (efecto de demanda distinto al puente)."""
    return {
        dt.date(anio, 1, 1),                    # Año Nuevo
        dt.date(anio, 5, 1),                    # Día del Trabajo
        dt.date(anio, 9, 16),                   # Independencia
        dt.date(anio, 12, 25),                  # Navidad
    }


def festivos_lft(anio: int) -> set[dt.date]:
    """LFT Art.74 completo (puente + fijo)."""
    return festivos_lft_puente(anio) | festivos_lft_fijo(anio)


def festivos_escolar(anio: int) -> set[dt.date]:
    return {dt.date(anio, 5, 5), dt.date(anio, 5, 10), dt.date(anio, 5, 15)}


def _rango_fechas(a: dt.date, b: dt.date) -> list[dt.date]:
    n = (b - a).days
    return [a + dt.timedelta(days=i) for i in range(n + 1)]


def construir_calendario(anio: int, params: dict | None = None) -> pd.DataFrame:
    """DataFrame indexado por fecha (todos los días del año) con banderas de calendario."""
    params = params or {}
    extras = params.get("extras_calendario", {})
    partidos = set(pd.to_datetime(params.get("partido_mx", []) or []).date) if params.get("partido_mx") else set()
    eventos_tv = set(pd.to_datetime(params.get("evento_tv", []) or []).date) if params.get("evento_tv") else set()

    dias = _rango_fechas(dt.date(anio, 1, 1), dt.date(anio, 12, 31))
    df = pd.DataFrame(index=pd.to_datetime(dias))
    df.index.name = "fecha"

    f_puente = festivos_lft_puente(anio)
    f_fijo = festivos_lft_fijo(anio)
    f_lft = f_puente | f_fijo
    f_esc = festivos_escolar(anio)

    pascua = domingo_pascua(anio)
    jue_santo = pascua - dt.timedelta(days=3)
    vie_santo = pascua - dt.timedelta(days=2)
    # Vacación SEP alrededor de Semana Santa
    ss_ini = pascua - dt.timedelta(days=6)
    ss_fin = pascua + dt.timedelta(days=7)
    set_ss = set(_rango_fechas(ss_ini, ss_fin))

    d = df.index.date

    df["dow"] = df.index.weekday                     # lunes=0
    df["dia"] = df.index.day
    df["mes"] = df.index.month

    df["festivo_lft"] = [1 if x in f_lft else 0 for x in d]
    df["festivo_lft_puente"] = [1 if x in f_puente else 0 for x in d]
    df["festivo_lft_fijo"] = [1 if x in f_fijo else 0 for x in d]
    df["festivo_escolar"] = [1 if x in f_esc else 0 for x in d]
    df["jueves_santo"] = [1 if x == jue_santo else 0 for x in d]
    df["viernes_santo"] = [1 if x == vie_santo else 0 for x in d]
    df["jue_vie_santo"] = ((df["jueves_santo"] == 1) | (df["viernes_santo"] == 1)).astype(int)
    df["vac_semana_santa"] = [1 if x in set_ss else 0 for x in d]
    df["partido_mx"] = [1 if x in partidos else 0 for x in d]
    df["evento_tv"] = [1 if x in eventos_tv else 0 for x in d]

    # --- Extras ---
    vac_inv_hasta = _mmdd(extras.get("vac_invierno_hasta", "01-06"))
    df["vac_invierno"] = [1 if (x.month, x.day) <= vac_inv_hasta and x.month == 1 else 0 for x in d]

    fc = extras.get("fin_ciclo", {"inicio": "07-10", "fin": "07-15"})
    df["fin_ciclo"] = _flag_mmdd_rango(d, fc["inicio"], fc["fin"])

    rc = extras.get("regreso_clases", {"inicio": "09-01", "fin": "09-15"})
    df["regreso_clases"] = _flag_mmdd_rango(d, rc["inicio"], rc["fin"])

    gr = extras.get("gr", {"inicio": "12-12", "fin": "12-31"})
    df["gr"] = _flag_mmdd_rango(d, gr["inicio"], gr["fin"])

    # Quincena: días 14-16 y 29-01
    df["quincena"] = df["dia"].isin([14, 15, 16, 29, 30, 31, 1]).astype(int)
    # Quincena laboral: quincena en día hábil (lun-vie)
    df["quincena_laboral"] = ((df["quincena"] == 1) & (df["dow"] < 5)).astype(int)

    return df


def _mmdd(s: str) -> tuple[int, int]:
    mm, dd = s.split("-")
    return (int(mm), int(dd))


def _flag_mmdd_rango(fechas, ini: str, fin: str) -> list[int]:
    a = _mmdd(ini)
    b = _mmdd(fin)
    return [1 if a <= (x.month, x.day) <= b else 0 for x in fechas]


def calendario_rango(fecha_ini, fecha_fin, params: dict | None = None) -> pd.DataFrame:
    """Calendario continuo cubriendo [fecha_ini, fecha_fin], concatenando años."""
    fi = pd.Timestamp(fecha_ini)
    ff = pd.Timestamp(fecha_fin)
    partes = [construir_calendario(a, params) for a in range(fi.year, ff.year + 1)]
    cal = pd.concat(partes)
    return cal.loc[(cal.index >= fi) & (cal.index <= ff)]
