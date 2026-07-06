#!/usr/bin/env node
/**
 * Registra el servidor NotebookLM en la configuración de la aplicación de
 * Claude para escritorio (Claude Desktop), sin que el usuario tenga que editar
 * archivos a mano.
 *
 * - Localiza el archivo de configuración según el sistema operativo.
 * - Si no existe, lo crea (incluyendo carpetas).
 * - Fusiona (no sobrescribe) la entrada "notebooklm" dentro de mcpServers,
 *   respetando cualquier otro servidor ya configurado.
 *
 * Se puede probar de forma segura apuntando a otro archivo con la variable
 * NOTEBOOKLM_CLAUDE_CONFIG.
 */
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const serverPath = path.resolve(__dirname, "..", "src", "server.js");

function claudeDesktopConfigPath() {
  if (process.env.NOTEBOOKLM_CLAUDE_CONFIG) {
    return process.env.NOTEBOOKLM_CLAUDE_CONFIG;
  }
  const home = os.homedir();
  switch (process.platform) {
    case "darwin":
      return path.join(
        home,
        "Library",
        "Application Support",
        "Claude",
        "claude_desktop_config.json"
      );
    case "win32":
      return path.join(
        process.env.APPDATA || path.join(home, "AppData", "Roaming"),
        "Claude",
        "claude_desktop_config.json"
      );
    default:
      return path.join(home, ".config", "Claude", "claude_desktop_config.json");
  }
}

function main() {
  const cfgPath = claudeDesktopConfigPath();
  let config = {};
  if (fs.existsSync(cfgPath)) {
    try {
      const raw = fs.readFileSync(cfgPath, "utf8").trim();
      config = raw ? JSON.parse(raw) : {};
    } catch (e) {
      console.error(
        `\n⚠️  No pude leer la configuración existente en:\n   ${cfgPath}\n   (${e.message})\n` +
          "   Para no dañar nada, no la modificaré. Ábrela y revisa que sea un JSON válido, o pide ayuda."
      );
      process.exit(1);
    }
  }

  if (!config.mcpServers || typeof config.mcpServers !== "object") {
    config.mcpServers = {};
  }

  const existed = Boolean(config.mcpServers.notebooklm);
  config.mcpServers.notebooklm = {
    command: process.execPath, // ruta absoluta al Node que estás usando
    args: [serverPath],
    env: { NOTEBOOKLM_HEADLESS: "1" },
  };

  fs.mkdirSync(path.dirname(cfgPath), { recursive: true });
  fs.writeFileSync(cfgPath, JSON.stringify(config, null, 2) + "\n", "utf8");

  console.log(
    `\n✅ ${existed ? "Actualicé" : "Agregué"} el servidor "notebooklm" en la app de Claude:\n   ${cfgPath}`
  );
  console.log(
    "   👉 Cierra y vuelve a abrir la aplicación de Claude para que aparezcan las herramientas de NotebookLM."
  );
}

main();
