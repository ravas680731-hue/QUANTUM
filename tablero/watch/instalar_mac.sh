#!/usr/bin/env bash
# Instala el watcher de tableros como servicio launchd en macOS (opción B).
# Al soltar un Excel nuevo en la carpeta de una EESS, genera su PDF automáticamente.
#
# Uso:   bash tablero/watch/instalar_mac.sh
set -euo pipefail

WATCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$WATCH_DIR/.." && pwd)"          # .../tablero
REPO="$(cd "$ROOT/.." && pwd)"               # raíz del repo
LABEL="com.quantum.tableros.watcher"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

echo "▶ Tablero watcher — instalación (macOS)"
[ "$(uname)" = "Darwin" ] || { echo "✗ Esto es solo para macOS."; exit 1; }

PYTHON="$(command -v python3 || true)"
NODE="$(command -v node || true)"
[ -n "$PYTHON" ] || { echo "✗ No encontré python3. Instálalo (brew install python) y reintenta."; exit 1; }
[ -n "$NODE" ]   || { echo "✗ No encontré node. Instálalo (brew install node) y reintenta."; exit 1; }
echo "  python3: $PYTHON"
echo "  node:    $NODE"

echo "▶ Instalando dependencias (una sola vez)…"
"$PYTHON" -m pip install --quiet --user -r "$ROOT/requirements.txt" || true
( cd "$REPO" && [ -d node_modules ] || npm install )
( cd "$REPO" && npx playwright install chromium >/dev/null 2>&1 || true )

# --- Carpetas a vigilar: se leen de config/*.yaml (resuelve la ruta iCloud) ---
# (compatible con el bash 3.2 de macOS: sin `mapfile`)
FOLDERS=()
while IFS= read -r _line; do
  [ -n "$_line" ] && FOLDERS+=("$_line")
done < <("$PYTHON" - "$ROOT" <<'PY'
import sys, os, glob, yaml
root = sys.argv[1]; sys.path.insert(0, root)
import generar_tablero as G
for c in sorted(glob.glob(os.path.join(root, "config", "*.yaml"))):
    cfg = yaml.safe_load(open(c, encoding="utf-8"))
    folder = os.path.join(G.icloud_base(cfg), cfg["carpeta_eess"])
    print(folder)
PY
)

WATCHXML=""
for f in ${FOLDERS[@]+"${FOLDERS[@]}"}; do
  if [ -d "$f" ]; then
    echo "  vigilando: $f"
    WATCHXML+="    <string>$f</string>"$'\n'
  else
    echo "  ⚠ no existe (se omite): $f"
  fi
done
[ -n "$WATCHXML" ] || { echo "✗ Ninguna carpeta de EESS existe todavía. Crea las carpetas en iCloud y reintenta."; exit 1; }

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string>
    <string>$WATCH_DIR/procesar_nuevos.py</string>
  </array>
  <key>WatchPaths</key>
  <array>
$WATCHXML  </array>
  <key>RunAtLoad</key><true/>
  <key>StartInterval</key><integer>300</integer>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    <key>TABLERO_NODE</key><string>$NODE</string>
  </dict>
  <key>StandardOutPath</key><string>$WATCH_DIR/launchd.out.log</string>
  <key>StandardErrorPath</key><string>$WATCH_DIR/launchd.err.log</string>
</dict>
</plist>
PLISTEOF

# (re)cargar el servicio
launchctl unload "$PLIST" >/dev/null 2>&1 || true
launchctl load "$PLIST"
echo "✔ Watcher instalado y activo."
echo "  Suelta GIN_07_2026.xlsx o SBH_07_2026.xlsx en su carpeta y el PDF aparecerá al lado."
echo "  Registro: $WATCH_DIR/watcher.log"
echo "  Desinstalar: bash $WATCH_DIR/desinstalar_mac.sh"
