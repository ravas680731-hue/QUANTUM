"""config.py — rutas del proyecto (multi-estación), YAML y bootstrap de OpenMP.

Arquitectura multi-estación: cada estación vive en estaciones/<PERMISO_NORM>/
con sus propios datos, estado y parametros.yaml, y sus salidas en
salidas/<PERMISO_NORM>/. Las rutas "scoped" se fijan con `usar_estacion()`.

En macOS sin Homebrew, XGBoost no encuentra libomp.dylib; empaquetamos una
copia en .venv/libomp/ y re-ejecutamos con DYLD_FALLBACK_LIBRARY_PATH.
Llamar a `ensure_omp()` ANTES de importar xgboost.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# --- Rutas base (no dependen de estación) -----------------------------------
ROOT = Path(__file__).resolve().parent.parent
ESTACIONES = ROOT / "estaciones"
SALIDAS_ROOT = ROOT / "salidas"
LOGS = SALIDAS_ROOT / "logs"                 # logs de orquestación (global)
REGISTRO_YAML = ROOT / "registro_estaciones.yaml"

# --- Rutas "scoped" a la estación activa (se fijan con usar_estacion) --------
estacion_actual: str | None = None
ENTRADA: Path | None = None
ESTADO: Path | None = None
SALIDAS: Path | None = None
PARAMETROS_YAML: Path | None = None
HISTORICO_PARQUET: Path | None = None
BITACORA_CSV: Path | None = None
CLIMA_CSV: Path | None = None


def usar_estacion(permiso_norm: str) -> Path:
    """Fija las rutas scoped a la estación `permiso_norm`. Devuelve su carpeta base."""
    global estacion_actual, ENTRADA, ESTADO, SALIDAS
    global PARAMETROS_YAML, HISTORICO_PARQUET, BITACORA_CSV, CLIMA_CSV
    base = ESTACIONES / permiso_norm
    estacion_actual = permiso_norm
    ENTRADA = base / "datos" / "entrada"
    ESTADO = base / "datos" / "estado"
    PARAMETROS_YAML = base / "parametros.yaml"      # yaml al RAÍZ de la estación
    HISTORICO_PARQUET = ESTADO / "historico.parquet"
    BITACORA_CSV = ESTADO / "bitacora.csv"
    CLIMA_CSV = ENTRADA / "clima.csv"
    SALIDAS = SALIDAS_ROOT / permiso_norm
    return base


def ensure_omp() -> None:
    """Garantiza que libomp.dylib sea localizable por el loader (macOS). Idempotente."""
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
        return
    actual = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    if ompdir in actual.split(":"):
        return
    os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = ompdir + (":" + actual if actual else "")
    os.environ["_OMP_BOOTSTRAPPED"] = "1"
    os.execv(sys.executable, [sys.executable] + sys.argv)


def cargar_parametros(ruta: Path | None = None) -> dict:
    """Carga el parametros.yaml de la estación activa (o de `ruta`)."""
    import yaml

    ruta = ruta or PARAMETROS_YAML
    if ruta is None:
        raise RuntimeError("No hay estación activa: llama a usar_estacion() primero.")
    with open(ruta, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def cargar_registro(ruta: Path | None = None) -> dict:
    """Carga registro_estaciones.yaml."""
    import yaml

    ruta = ruta or REGISTRO_YAML
    if not ruta.exists():
        return {"estaciones": {}}
    with open(ruta, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {"estaciones": {}}


def estaciones_registradas(solo_estatus: set[str] | None = None) -> list[str]:
    """Lista de PERMISO_NORM en el registro, opcionalmente filtrando por estatus."""
    reg = cargar_registro()
    out = []
    for norm, meta in (reg.get("estaciones") or {}).items():
        if solo_estatus is None or meta.get("estatus") in solo_estatus:
            out.append(norm)
    return out


def normalizar_permiso(permiso: str) -> str:
    """PL/6812/EXP/ES/2015 -> PL-6812-EXP-ES-2015 (clave de carpeta)."""
    return permiso.strip().replace("/", "-")


# lunes=0 ... domingo=6 (convención Python weekday)
DIAS_SEMANA = {
    "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2, "jueves": 3,
    "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6,
}


def fecha_inicio_operativo(fecha_origen, params: dict):
    """Primer día de la ventana de pronóstico según la programación.

    `programacion.dia_inicio_operativo` (p.ej. "martes") -> el día más próximo con
    ese día-de-semana tal que sea > fecha_origen. Si no se configura, origen+1.
    Ej.: origen=domingo, inicio=martes -> origen+2 (el lunes queda como HUECO,
    se imputa; ver features.construir_frame).
    """
    import pandas as pd

    origen = pd.Timestamp(fecha_origen)
    prog = (params.get("programacion") or {})
    dia = prog.get("dia_inicio_operativo")
    wd = DIAS_SEMANA.get(str(dia).strip().lower()) if dia else None
    if wd is None:
        return origen + pd.Timedelta(days=1)
    d = origen + pd.Timedelta(days=1)
    for _ in range(7):
        if d.weekday() == wd:
            return d
        d += pd.Timedelta(days=1)
    return origen + pd.Timedelta(days=1)


def asegurar_directorios() -> None:
    for d in (ENTRADA, ESTADO, SALIDAS, LOGS):
        if d is not None:
            d.mkdir(parents=True, exist_ok=True)
