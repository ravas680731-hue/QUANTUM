"""alta.py — alta de una estación nueva por permiso CNE (comando --alta).

La estación NACE en estatus "calibración": genera pronóstico para aprender pero
NO pedido sugerido, hasta pasar SUS PROPIAS 5 validaciones con sus datos.

Este scaffold crea carpetas + parametros.yaml (plantilla desde la estación de
referencia, con TODO parámetro local marcado `# CALIBRAR`) y una entrada stub en
el registro. La verificación de identidad (CNE + L_CNE del SAT + geocodificación)
es un GATE asistido: se captura la ficha confirmada por el operador ANTES de
escribir datos reales de identidad — prohibido inventar (04.d).
"""
from __future__ import annotations

import re
from pathlib import Path

from . import config

# Parámetros locales que SIEMPRE deben calibrarse por estación
_MARCAR_CALIBRAR = [
    (re.compile(r"^(\s*fondo_muerto:\s*\d+)"), r"\1  # CALIBRAR (capacidad/fondo real del tanque)"),
    (re.compile(r"^(regimen_desde:.*)"), r"\1  # CALIBRAR (inicio de régimen de datos de ESTA estación)"),
    (re.compile(r"^(\s*(?:festivo_lft_\w+|festivo_escolar|jueves_viernes_santo|vacacion_semana_santa|quincena_laboral|partido_mx\w*):\s*\{.*\})"),
     r"\1  # CALIBRAR"),
    (re.compile(r"^(\s*(?:MAGNA|PREMIUM|DIESEL):\s*[\d.]+)(\s*$)"), r"\1  # CALIBRAR\2"),
]

_BANNER = """# ============================================================================
# ⚠️  ESTACIÓN EN CALIBRACIÓN — plantilla generada por --alta
# Todo parámetro marcado `# CALIBRAR` DEBE ajustarse con datos de ESTA estación
# (fondos muertos de tanque, multiplicadores de evento, regimen_desde, umbrales).
# La estación NO emite pedido sugerido hasta pasar sus propias 5 validaciones.
# ============================================================================
"""


def _plantilla_yaml(texto_ref: str, permiso: str) -> str:
    out = []
    for linea in texto_ref.splitlines():
        for patron, repl in _MARCAR_CALIBRAR:
            if patron.search(linea) and "# CALIBRAR" not in linea:
                linea = patron.sub(repl, linea)
                break
        out.append(linea)
    cuerpo = "\n".join(out)
    cuerpo = re.sub(r'estacion:\s*".*"', f'estacion: "CALIBRAR"   # permiso {permiso}', cuerpo, count=1)
    return _BANNER + "\n" + cuerpo + "\n"


def alta_estacion(permiso: str, referencia_norm: str = "PL-6812-EXP-ES-2015") -> dict:
    """Crea el scaffold de una estación en calibración. Devuelve info + checklist.

    NO escribe identidad real (razón social, dirección, coords): eso viene del
    GATE de ficha confirmada. El registro queda con placeholders `# CAPTURAR`.
    """
    norm = config.normalizar_permiso(permiso)
    base = config.ESTACIONES / norm
    if (base / "parametros.yaml").exists():
        return {"norm": norm, "ya_existe": True,
                "mensaje": f"La estación {norm} ya existe; no se sobrescribe."}

    (base / "datos" / "entrada").mkdir(parents=True, exist_ok=True)
    (base / "datos" / "estado").mkdir(parents=True, exist_ok=True)
    (config.SALIDAS_ROOT / norm).mkdir(parents=True, exist_ok=True)

    ref_yaml = (config.ESTACIONES / referencia_norm / "parametros.yaml").read_text(encoding="utf-8")
    (base / "parametros.yaml").write_text(_plantilla_yaml(ref_yaml, permiso), encoding="utf-8")

    checklist = [
        f"Estación {norm} creada en estatus «calibración».",
        "GATE de ficha (04.d) — capturar y CONFIRMAR antes de activar el registro:",
        "  1) Buscar el permiso en el registro público CNE (cne.gob.mx/Permisos; título en drive.cne.gob.mx).",
        "  2) Verificar vigencia en la L_CNE del SAT. Si NO está activo -> ALERTA CRÍTICA (no puede timbrar), alta en suspenso.",
        "  3) Geocodificar la dirección -> lat/lon.",
        "  4) Derivar: fuente de clima/PC de la entidad, política de riesgo por zona, productos autorizados",
        "     (sin Premium autorizado = sin pipeline de Premium), huso horario, competidores 5 km.",
        "  5) Poner los CSV de ventas de ESTA estación en su datos/entrada/ (jamás detectar por contenido).",
        "  6) Calibrar en parametros.yaml todo lo marcado # CALIBRAR.",
        "  7) Correr sus 5 validaciones; al pasarlas, cambiar estatus a «activa» (recién ahí emite pedido).",
    ]
    return {"norm": norm, "ya_existe": False, "base": str(base), "checklist": checklist}
