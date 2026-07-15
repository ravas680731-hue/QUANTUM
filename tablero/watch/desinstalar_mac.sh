#!/usr/bin/env bash
# Desinstala el watcher de tableros (launchd) en macOS.
set -euo pipefail
LABEL="com.quantum.tableros.watcher"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
launchctl unload "$PLIST" >/dev/null 2>&1 || true
rm -f "$PLIST"
echo "✔ Watcher desinstalado. (Los PDFs ya generados se conservan.)"
