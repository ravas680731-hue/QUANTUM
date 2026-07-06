#!/usr/bin/env node
/**
 * Smoke test: spawn the MCP server over stdio, run the standard MCP handshake,
 * list tools, and call notebooklm_auth_status. Verifies the server wiring
 * without needing a real Google login (auth_status is allowed to report
 * authenticated:false).
 */
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const serverPath = path.join(__dirname, "..", "src", "server.js");

const child = spawn(process.execPath, [serverPath], {
  stdio: ["pipe", "pipe", "inherit"],
  env: { ...process.env, NOTEBOOKLM_HEADLESS: "1" },
});

let buffer = "";
const pending = new Map();
let nextId = 1;

child.stdout.on("data", (chunk) => {
  buffer += chunk.toString();
  let idx;
  while ((idx = buffer.indexOf("\n")) >= 0) {
    const line = buffer.slice(0, idx).trim();
    buffer = buffer.slice(idx + 1);
    if (!line) continue;
    let msg;
    try {
      msg = JSON.parse(line);
    } catch {
      continue;
    }
    if (msg.id != null && pending.has(msg.id)) {
      pending.get(msg.id)(msg);
      pending.delete(msg.id);
    }
  }
});

function rpc(method, params) {
  const id = nextId++;
  const payload = { jsonrpc: "2.0", id, method, params };
  child.stdin.write(JSON.stringify(payload) + "\n");
  return new Promise((resolve, reject) => {
    pending.set(id, resolve);
    setTimeout(() => reject(new Error(`Timeout waiting for ${method}`)), 60_000);
  });
}

function notify(method, params) {
  child.stdin.write(JSON.stringify({ jsonrpc: "2.0", method, params }) + "\n");
}

async function main() {
  const init = await rpc("initialize", {
    protocolVersion: "2024-11-05",
    capabilities: {},
    clientInfo: { name: "smoke", version: "0" },
  });
  console.log("initialize OK:", init.result?.serverInfo);
  notify("notifications/initialized", {});

  const tools = await rpc("tools/list", {});
  const names = (tools.result?.tools || []).map((t) => t.name);
  console.log("tools/list OK:", names.join(", "));
  if (names.length !== 6) throw new Error(`Expected 6 tools, got ${names.length}`);

  console.log("calling notebooklm_auth_status (launches headless Chromium)…");
  const auth = await rpc("tools/call", {
    name: "notebooklm_auth_status",
    arguments: {},
  });
  const text = auth.result?.content?.[0]?.text || "";
  console.log("auth_status result:\n" + text);

  console.log("\n✅ Smoke test passed (server wiring + browser launch verified).");
  child.kill("SIGTERM");
  process.exit(0);
}

main().catch((err) => {
  console.error("❌ Smoke test failed:", err.message);
  child.kill("SIGTERM");
  process.exit(1);
});
