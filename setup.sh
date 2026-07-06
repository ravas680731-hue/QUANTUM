#!/usr/bin/env bash
#
# Conexión en un paso: NotebookLM  ->  Claude Cowork / Claude Code
#
# Ejecuta en tu propio computador:
#     bash setup.sh
#
# Hace todo por ti:
#   1) instala lo que el servidor necesita
#   2) abre una ventana para que inicies sesión en Google (una sola vez)
#   3) registra el servidor en Claude para que aparezca en Cowork
#
# Tus datos de Google se guardan SOLO en tu equipo (carpeta local, no se sube
# a ningún sitio, ver SECURITY.md).

set -euo pipefail
cd "$(dirname "$0")"

say() { printf "\n\033[1;36m==>\033[0m %s\n" "$1"; }
err() { printf "\n\033[1;31mError:\033[0m %s\n" "$1" >&2; }

# --- 1. Requisitos ---------------------------------------------------------
if ! command -v node >/dev/null 2>&1; then
  err "No encuentro Node.js. Instálalo desde https://nodejs.org (versión 20 o superior) y vuelve a ejecutar."
  exit 1
fi
say "Node.js detectado: $(node --version)"

# --- 2. Dependencias -------------------------------------------------------
say "Instalando dependencias (una vez)…"
npm install

say "Preparando el navegador (Chromium)…"
npx playwright install chromium >/dev/null 2>&1 || true

# --- 3. Inicio de sesión de Google (interactivo, una sola vez) -------------
say "Ahora se abrirá una ventana de navegador."
echo "   Inicia sesión con TU cuenta de Google y espera a ver tus notebooks."
echo "   Luego vuelve a esta terminal y pulsa Enter."
node scripts/login.js

# --- 4. Registrar el servidor en la app de Claude --------------------------
SERVER_PATH="$(pwd)/src/server.js"

# 4a. Aplicación de escritorio de Claude (Claude Desktop): configura el archivo
#     por ti, sin editar nada a mano.
say "Configurando la aplicación de Claude…"
node scripts/register-claude.js || err "No pude configurar la app de Claude automáticamente (revisa el mensaje de arriba)."

# 4b. Si además usas Claude Code (comando 'claude'), lo registramos también.
if command -v claude >/dev/null 2>&1; then
  say "También detecté Claude Code; registrando ahí…"
  claude mcp add notebooklm -s user -e NOTEBOOKLM_HEADLESS=1 -- node "$SERVER_PATH" || true
fi

say "Verificación rápida del servidor…"
npm run smoke || true

echo ""
echo "──────────────────────────────────────────────────────────────"
echo " Conexión completada. En Cowork/Claude Code tendrás estas acciones:"
echo "   • ver tus notebooks           • crear un notebook"
echo "   • abrir un notebook           • agregar una fuente"
echo "   • preguntarle a un notebook"
echo " Seguridad: tu sesión de Google queda solo en este equipo. Ver SECURITY.md"
echo "──────────────────────────────────────────────────────────────"
