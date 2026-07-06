import path from "node:path";
import os from "node:os";
import fs from "node:fs";

/**
 * Locate a usable Chromium binary.
 *
 * On a normal workstation we return undefined so Playwright uses the browser it
 * downloaded itself. On the pre-provisioned cloud image Playwright's bundled
 * revision may not match what is on disk under /opt/pw-browsers, so we detect
 * the installed full-Chromium build and point at it directly (this also covers
 * the missing headless-shell, since full Chromium can run headless).
 */
function detectChromium() {
  if (process.env.NOTEBOOKLM_CHROMIUM_PATH) return process.env.NOTEBOOKLM_CHROMIUM_PATH;
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH;
  if (!root) return undefined;
  try {
    const builds = fs
      .readdirSync(root)
      .filter((d) => d.startsWith("chromium-") && !d.includes("headless"))
      .sort()
      .reverse();
    for (const b of builds) {
      const candidate = path.join(root, b, "chrome-linux", "chrome");
      if (fs.existsSync(candidate)) return candidate;
    }
  } catch {
    /* fall through to Playwright default */
  }
  return undefined;
}

/**
 * Central configuration, all overridable via environment variables so the
 * server can be dropped into Claude Desktop / Claude Code `mcpServers` config
 * without editing code.
 */
export const config = {
  // Where Playwright stores the persistent browser profile (cookies, Google
  // login session). Keeping it out of the repo means the auth session survives
  // between runs. Defaults to a folder in the user's home dir.
  userDataDir:
    process.env.NOTEBOOKLM_USER_DATA_DIR ||
    path.join(os.homedir(), ".notebooklm-mcp", "profile"),

  // NotebookLM entry point.
  baseUrl: process.env.NOTEBOOKLM_BASE_URL || "https://notebooklm.google.com",

  // Run the browser visibly. Required for the one-time interactive login and
  // useful for debugging. Set NOTEBOOKLM_HEADLESS=1 for unattended operation
  // once a session has been captured.
  headless: envBool("NOTEBOOKLM_HEADLESS", false),

  // Explicit Chromium path. The pre-provisioned cloud image ships one under
  // /opt/pw-browsers; Playwright normally finds it automatically, but allow an
  // override for locked-down environments.
  executablePath: detectChromium(),

  // Per-action timeout (ms). NotebookLM answers can take a while to stream.
  actionTimeoutMs: envInt("NOTEBOOKLM_ACTION_TIMEOUT_MS", 45_000),

  // How long to wait for a chat answer to finish streaming (ms).
  answerTimeoutMs: envInt("NOTEBOOKLM_ANSWER_TIMEOUT_MS", 120_000),

  // Optional locale for the browser context.
  locale: process.env.NOTEBOOKLM_LOCALE || "en-US",

  // Optional outbound HTTP(S) proxy for the browser. On a normal machine leave
  // this unset (direct connection). In sandboxes that force egress through a
  // proxy, set NOTEBOOKLM_PROXY or rely on the standard HTTPS_PROXY env var.
  proxyServer:
    process.env.NOTEBOOKLM_PROXY ||
    process.env.HTTPS_PROXY ||
    process.env.https_proxy ||
    undefined,
};

function envBool(name, def) {
  const v = process.env[name];
  if (v == null || v === "") return def;
  return ["1", "true", "yes", "on"].includes(v.toLowerCase());
}

function envInt(name, def) {
  const v = process.env[name];
  if (v == null || v === "") return def;
  const n = Number.parseInt(v, 10);
  return Number.isFinite(n) ? n : def;
}
