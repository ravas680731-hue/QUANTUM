#!/usr/bin/env node
/**
 * One-time interactive login.
 *
 * Opens a visible Chromium window using the SAME persistent profile the MCP
 * server uses, navigates to NotebookLM, and waits for you to sign in with your
 * Google account. Once you reach the NotebookLM home the session cookies are
 * saved in the profile directory and the headless MCP server can reuse them.
 *
 * Run on a machine with a display:  npm run login
 */
import { chromium } from "playwright";
import { config } from "../src/config.js";

async function main() {
  console.log("Launching NotebookLM in a visible browser for sign-in…");
  console.log("Profile dir:", config.userDataDir);

  const context = await chromium.launchPersistentContext(config.userDataDir, {
    headless: false, // must be visible so you can complete the Google flow
    executablePath: config.executablePath,
    locale: config.locale,
    viewport: { width: 1400, height: 900 },
    args: ["--no-sandbox"],
  });

  const page = context.pages()[0] || (await context.newPage());
  await page.goto(config.baseUrl, { waitUntil: "domcontentloaded" });

  console.log("\n👉 Sign in with your Google account in the opened window.");
  console.log("   When you can see your NotebookLM notebooks, come back here and press Enter.\n");

  await waitForEnter();

  await context.close();
  console.log("✅ Session saved. You can now run the MCP server (npm start) headless.");
  process.exit(0);
}

function waitForEnter() {
  return new Promise((resolve) => {
    process.stdin.resume();
    process.stdin.once("data", () => resolve());
  });
}

main().catch((err) => {
  console.error("Login failed:", err);
  process.exit(1);
});
