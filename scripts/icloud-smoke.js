#!/usr/bin/env node
/**
 * Smoke test for the iCloud Drive MCP server.
 *
 * Builds a fake iCloud Drive folder in a temp dir (pointed to via
 * ICLOUD_DRIVE_PATH), including a downloaded file and a `.icloud` placeholder
 * for a cloud-only file, then spawns the server over stdio, runs the MCP
 * handshake, and exercises the tools — asserting present / cloudOnly / missing
 * are reported correctly. Needs no real iCloud account, so it runs anywhere.
 */
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import os from "node:os";
import fs from "node:fs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const serverPath = path.join(__dirname, "..", "src", "icloud-server.js");

// --- Build a fake iCloud Drive that mirrors the real Financieros EESS layout.
const root = fs.mkdtempSync(path.join(os.tmpdir(), "icloud-smoke-"));
const financieros = path.join(root, "01-QUANTUM", "Financieros EESS");
const ginDir = path.join(financieros, "GIN");
const sbhDir = path.join(financieros, "SBH");
fs.mkdirSync(ginDir, { recursive: true });
fs.mkdirSync(sbhDir, { recursive: true });
// GIN file is downloaded locally; SBH file exists only in iCloud (placeholder).
fs.writeFileSync(path.join(ginDir, "GIN_06_2026.xlsx"), "fake xlsx bytes");
fs.writeFileSync(path.join(sbhDir, ".SBH_06_2026.xlsx.icloud"), "");

const child = spawn(process.execPath, [serverPath], {
  stdio: ["pipe", "pipe", "inherit"],
  env: { ...process.env, ICLOUD_DRIVE_PATH: root },
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
  child.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n");
  return new Promise((resolve, reject) => {
    pending.set(id, resolve);
    setTimeout(() => reject(new Error(`Timeout waiting for ${method}`)), 30_000);
  });
}

function notify(method, params) {
  child.stdin.write(JSON.stringify({ jsonrpc: "2.0", method, params }) + "\n");
}

function callTool(name, args) {
  return rpc("tools/call", { name, arguments: args || {} }).then((r) =>
    JSON.parse(r.result?.content?.[0]?.text || "{}")
  );
}

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

async function main() {
  const init = await rpc("initialize", {
    protocolVersion: "2024-11-05",
    capabilities: {},
    clientInfo: { name: "icloud-smoke", version: "0" },
  });
  console.log("initialize OK:", init.result?.serverInfo);
  notify("notifications/initialized", {});

  const tools = await rpc("tools/list", {});
  const names = (tools.result?.tools || []).map((t) => t.name);
  console.log("tools/list OK:", names.join(", "));
  assert(names.length === 6, `Expected 6 tools, got ${names.length}`);

  const status = await callTool("icloud_status", {});
  assert(status.exists && status.isDirectory, "status should see the fake iCloud folder");
  console.log("icloud_status OK:", status.basePath);

  const gin = await callTool("icloud_check_file", {
    path: "01-QUANTUM/Financieros EESS/GIN/GIN_06_2026.xlsx",
  });
  assert(gin.status === "present", `GIN file should be present, got ${gin.status}`);
  console.log("GIN_06_2026.xlsx ->", gin.status);

  const sbh = await callTool("icloud_check_file", {
    path: "01-QUANTUM/Financieros EESS/SBH/SBH_06_2026.xlsx",
  });
  assert(sbh.status === "cloudOnly", `SBH file should be cloudOnly, got ${sbh.status}`);
  console.log("SBH_06_2026.xlsx ->", sbh.status, "(exists in iCloud, not downloaded)");

  const missing = await callTool("icloud_check_file", {
    path: "01-QUANTUM/Financieros EESS/GIN/GIN_07_2026.xlsx",
  });
  assert(missing.status === "missing", `nonexistent file should be missing, got ${missing.status}`);
  console.log("GIN_07_2026.xlsx ->", missing.status);

  const listing = await callTool("icloud_list", { path: "01-QUANTUM/Financieros EESS" });
  const dirNames = listing.entries.map((e) => e.name).sort();
  assert(
    dirNames.join(",") === "GIN,SBH",
    `expected GIN and SBH folders, got ${dirNames.join(",")}`
  );
  console.log("icloud_list OK:", dirNames.join(", "));

  const found = await callTool("icloud_search", { query: "SBH_06_2026" });
  assert(found.count === 1 && found.results[0].cloudOnly, "search should find the cloud-only SBH file");
  console.log("icloud_search OK: found", found.results[0].name, "(cloudOnly)");

  const traversal = await rpc("tools/call", {
    name: "icloud_check_file",
    arguments: { path: "../../../etc/passwd" },
  });
  assert(traversal.result?.isError, "path traversal outside the root must be rejected");
  console.log("path-traversal guard OK: escape rejected");

  console.log("\n✅ iCloud smoke test passed (wiring + present/cloudOnly/missing + guards).");
  child.kill("SIGTERM");
  fs.rmSync(root, { recursive: true, force: true });
  process.exit(0);
}

main().catch((err) => {
  console.error("❌ iCloud smoke test failed:", err.message);
  child.kill("SIGTERM");
  fs.rmSync(root, { recursive: true, force: true });
  process.exit(1);
});
