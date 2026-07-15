#!/bin/bash
# ejecutar_lunes.sh — corre el pronóstico semanal SBH (invocado por launchd los lunes 07:00).
# Activa el venv propio, resuelve libomp (OpenMP) y ejecuta el pipeline con bitácora.
set -uo pipefail

PROYECTO="/Users/radamesvargasramirez/QUANTUM/norte-b/pronostico-sbh"
VENV="$PROYECTO/.venv"
PY="$VENV/bin/python"
LOGDIR="$PROYECTO/salidas/logs"
STAMP="$(date +%Y-%m-%d_%H%M%S)"
LOG="$LOGDIR/ejecutar_lunes_$STAMP.log"

mkdir -p "$LOGDIR"

# libomp (macOS sin Homebrew): la copia estable vive en .venv/libomp.
# El propio pronostico_semanal.py también se auto-configura, pero lo fijamos aquí.
export DYLD_FALLBACK_LIBRARY_PATH="$VENV/libomp${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}"

{
  echo "==== ejecutar_lunes.sh · $STAMP ===="
  if [ ! -x "$PY" ]; then
    echo "ERROR: no existe el intérprete del venv en $PY"
    exit 1
  fi
  cd "$PROYECTO" || { echo "ERROR: no pude entrar a $PROYECTO"; exit 1; }
  # --todas: corre todas las estaciones del registro (cada una aislada).
  # Nota: el agente dispara a las 07:00 hora local del Mac. Si en el futuro hay
  # estaciones en otro huso horario, crear un LaunchAgent por huso.
  "$PY" pronostico_semanal.py --todas --validar
  CODE=$?
  if [ $CODE -eq 0 ]; then
    echo "==== OK (corrida exitosa) ===="
  else
    echo "==== ERROR (código $CODE) ===="
  fi
  exit $CODE
} >>"$LOG" 2>&1
