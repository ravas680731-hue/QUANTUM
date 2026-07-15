"""config.py — rutas del proyecto, carga de parámetros YAML y bootstrap de OpenMP.

En macOS sin Homebrew, XGBoost no encuentra libomp.dylib. Empaquetamos una copia
estable en .venv/libomp/ (tomada de scikit-learn) y, si hace falta, re-ejecutamos
el intérprete con DYLD_FALLBACK_LIBRARY_PATH apuntando a ella. Llamar a
`ensure_omp()` ANTES de importar xgboost.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# --- Rutas base -------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATOS = ROOT / "datos"
ENTRADA = DATOS / "entrada"
ESTADO = DATOS / "estado"
SALIDAS = ROOT / "salidas"
LOGS = SALIDAS / "logs"

PARAMETROS_YAML = ESTADO / "parametros.yaml"
HISTORICO_PARQUET = ESTADO / "historico.parquet"
BITACORA_CSV = ESTADO / "bitacora.csv"
CLIMA_CSV = ENTRADA / "clima.csv"


def ensure_omp() -> None:
    """Garantiza que libomp.dylib sea localizable por el loader (macOS).

    Idempotente: si ya está en el entorno, no hace nada. Si no, re-ejecuta el
    proceso con DYLD_FALLBACK_LIBRARY_PATH extendido (los DYLD_* solo se leen en
    exec, por eso re-ejecutamos en vez de solo mutar os.environ).
    """
    if sys.platform != "darwin":
        return
    if os.environ.get("_OMP_BOOTSTRAPPED") == "1":
        return

    candidatos = [ROOT / ".venv" / "libomp"]
    try:
        import sklearn  # noqa: F401

        candidatos.append(Path(sklearn.__file__).parent / ".dylibs")
    except Exception:
        pass

    ompdir = next((str(c) for c in candidatos if (c / "libomp.dylib").exists()), None)
    if ompdir is None:
        # Que xgboost falle con su propio mensaje claro más adelante.
        return

    actual = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    if ompdir in actual.split(":"):
        return

    os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = ompdir + (":" + actual if actual else "")
    os.environ["_OMP_BOOTSTRAPPED"] = "1"
    os.execv(sys.executable, [sys.executable] + sys.argv)


def cargar_parametros(ruta: Path | None = None) -> dict:
    """Carga parametros.yaml (fuente única de verdad)."""
    import yaml

    ruta = ruta or PARAMETROS_YAML
    with open(ruta, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def asegurar_directorios() -> None:
    for d in (ENTRADA, ESTADO, SALIDAS, LOGS):
        d.mkdir(parents=True, exist_ok=True)
