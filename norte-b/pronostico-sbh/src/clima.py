"""clima.py — carga de clima (02). Escala 0-3.

datos/entrada/clima.csv con columnas: fecha,norte,lluvia,puerto_cerrado.
SI NO EXISTE: crear plantilla vacía, asumir 0 y avisar. NUNCA abortar.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config

COLUMNAS = ["fecha", "norte", "lluvia", "puerto_cerrado"]


def _crear_plantilla(ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(columns=COLUMNAS).to_csv(ruta, index=False)


def cargar_clima(fechas: pd.DatetimeIndex, ruta: Path | None = None) -> tuple[pd.DataFrame, bool]:
    """Devuelve (df_clima alineado a `fechas`, faltante:bool).

    faltante=True si el archivo no existía o estaba vacío (se asume clima 0).
    """
    ruta = ruta or config.CLIMA_CSV
    faltante = False
    if not ruta.exists():
        _crear_plantilla(ruta)
        faltante = True
        clima = pd.DataFrame(columns=COLUMNAS)
    else:
        try:
            clima = pd.read_csv(ruta)
        except pd.errors.EmptyDataError:
            clima = pd.DataFrame(columns=COLUMNAS)
        if clima.empty or "fecha" not in clima.columns:
            faltante = True
            clima = pd.DataFrame(columns=COLUMNAS)

    base = pd.DataFrame(index=pd.DatetimeIndex(fechas, name="fecha"))
    for c in ["norte", "lluvia", "puerto_cerrado"]:
        base[c] = 0.0

    if not clima.empty:
        clima["fecha"] = pd.to_datetime(clima["fecha"], errors="coerce")
        clima = clima.dropna(subset=["fecha"]).set_index("fecha")
        for c in ["norte", "lluvia", "puerto_cerrado"]:
            if c in clima.columns:
                vals = pd.to_numeric(clima[c], errors="coerce")
                base[c] = vals.reindex(base.index).fillna(0.0).clip(0, 3)

    return base, faltante
