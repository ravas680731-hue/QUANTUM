"""carga_datos.py — contrato de datos (02) y construcción del histórico.

Columnas exactas del CSV:
  Fecha (dd/mm/aaaa), Sdo.Inicial, Compras, Ventas, Ajustes/Consignados,
  Sdo.Final, Sdo.Real, Merma, % Merma
Excluye fila TOTALES. Encoding detectado (UTF-8 o Latin-1). Concatena
2025+2026 por producto sin duplicar fechas.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config

COLUMNAS = {
    "Fecha": "fecha",
    "Sdo.Inicial": "sdo_inicial",
    "Compras": "compras",
    "Ventas": "ventas",
    "Ajustes/Consignados": "ajustes",
    "Sdo.Final": "sdo_final",
    "Sdo.Real": "sdo_real",
    "Merma": "merma",
    "% Merma": "pct_merma",
}
NUMERICAS = ["sdo_inicial", "compras", "ventas", "ajustes", "sdo_final", "sdo_real", "merma", "pct_merma"]


def _leer_csv(ruta: Path) -> pd.DataFrame:
    """Lee un CSV detectando encoding (UTF-8 -> Latin-1)."""
    for enc in ("utf-8", "latin-1"):
        try:
            df = pd.read_csv(ruta, encoding=enc, dtype=str)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise UnicodeDecodeError("no se pudo decodificar", b"", 0, 1, str(ruta))

    faltantes = [c for c in COLUMNAS if c not in df.columns]
    if faltantes:
        raise ValueError(f"{ruta.name}: faltan columnas del contrato: {faltantes}")

    df = df.rename(columns=COLUMNAS)[list(COLUMNAS.values())]
    # Excluir TOTALES
    df = df[~df["fecha"].str.strip().str.upper().str.startswith("TOTAL")].copy()
    df["fecha"] = pd.to_datetime(df["fecha"].str.strip(), format="%d/%m/%Y", errors="coerce")
    df = df.dropna(subset=["fecha"])
    for c in NUMERICAS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def cargar_producto(producto: str, entrada: Path | None = None) -> pd.DataFrame:
    """Carga y concatena todos los PRODUCTO_*.CSV, sin duplicar fechas."""
    entrada = entrada or config.ENTRADA
    archivos = sorted(entrada.glob(f"{producto}_*.CSV")) + sorted(entrada.glob(f"{producto}_*.csv"))
    if not archivos:
        raise FileNotFoundError(f"No hay archivos {producto}_*.CSV en {entrada}")
    partes = [_leer_csv(a) for a in archivos]
    df = pd.concat(partes, ignore_index=True)
    df = df.sort_values("fecha").drop_duplicates(subset=["fecha"], keep="last").reset_index(drop=True)
    df["producto"] = producto
    return df


def construir_historico(productos: list[str], entrada: Path | None = None,
                        estacion: str | None = None) -> pd.DataFrame:
    """Histórico largo (una fila por fecha-producto) para todos los productos.

    Los CSV se leen SOLO de la carpeta de la estación (config.ENTRADA por
    defecto) — jamás se detecta la estación por contenido. Cada fila se etiqueta
    con `estacion` (PERMISO_NORM) para el assert de aislamiento (03.2 multi).
    """
    entrada = entrada or config.ENTRADA
    estacion = estacion or config.estacion_actual
    dfs = [cargar_producto(p, entrada) for p in productos]
    hist = pd.concat(dfs, ignore_index=True)
    hist["estacion"] = estacion
    return hist.sort_values(["producto", "fecha"]).reset_index(drop=True)


def assert_una_estacion(df: pd.DataFrame, contexto: str = "") -> None:
    """AISLAMIENTO OBLIGATORIO: ningún DataFrame de entrenamiento/histórico puede
    contener datos de más de una estación."""
    if "estacion" in df.columns:
        n = df["estacion"].nunique(dropna=False)
        if n > 1:
            raise AssertionError(
                f"Aislamiento violado{(' en ' + contexto) if contexto else ''}: "
                f"el DataFrame contiene {n} estaciones distintas "
                f"({sorted(map(str, df['estacion'].unique()))}).")
