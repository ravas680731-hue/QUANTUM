# NotebookLM MCP

[![CI](https://github.com/ravas680731-hue/QUANTUM/actions/workflows/ci.yml/badge.svg)](https://github.com/ravas680731-hue/QUANTUM/actions/workflows/ci.yml)

An [MCP](https://modelcontextprotocol.io) server that connects Claude (or any
MCP client) to **Google NotebookLM**.

NotebookLM has **no public API and no official MCP server**, so this bridge
works the only way possible: it *takes control of the web* — it drives the
NotebookLM web app in a real Chromium browser via [Playwright](https://playwright.dev),
reusing your own Google login. From the MCP client's side it looks like a normal
set of tools; under the hood each call clicks and types in the NotebookLM UI.

## What it exposes

| Tool | What it does |
|------|--------------|
| `notebooklm_auth_status`   | Report whether a Google/NotebookLM session is active. Call first. |
| `notebooklm_list_notebooks`| List your notebooks (index + title). |
| `notebooklm_open_notebook` | Open a notebook by `title` (substring) or `index`. |
| `notebooklm_create_notebook`| Create and open a new empty notebook. |
| `notebooklm_add_source`    | Add a source to the open notebook (`type: "url"` or `"text"`). |
| `notebooklm_ask`           | Ask a question in the open notebook and return the grounded answer. |

## How it works

```
MCP client (Claude)  ──stdio JSON-RPC──►  src/server.js
                                              │
                                              ▼
                                     NotebookLMClient (Playwright)
                                              │
                                              ▼
                             Persistent Chromium profile  ──►  notebooklm.google.com
                             (holds your Google session)
```

The Google session lives in a **persistent browser profile** on disk
(`~/.notebooklm-mcp/profile` by default). You sign in **once** interactively;
after that the headless server reuses the cookies. The profile is git-ignored
and must never be committed — it contains your live auth cookies.

## Requirements

- Node.js ≥ 20
- A Google account with NotebookLM access
- A machine with a display for the **one-time** login (the server itself runs
  headless afterwards)

## Setup

```bash
npm install
```

Playwright downloads its own Chromium on install. On the pre-provisioned Claude
cloud image, the server auto-detects the Chromium already under
`/opt/pw-browsers` — no extra download needed.

### 1. One-time login (captures your Google session)

Run on a machine with a display:

```bash
npm run login
```

A Chromium window opens on notebooklm.google.com. Sign in with Google, wait
until you see your notebooks, then return to the terminal and press **Enter**.
The session is now saved in the profile directory.

### 2. Verify

```bash
npm run smoke     # checks server wiring + browser launch
npm start         # runs the MCP server on stdio (Ctrl-C to stop)
```

## Connect it to Claude

### Claude Cowork / Claude Code — zero-config (`.mcp.json`)

This repo ships a project-scoped [`.mcp.json`](.mcp.json). When you open the
project in **Claude Cowork / Claude Code**, it detects the server and asks you
to approve it; once approved the six `notebooklm_*` tools are available in that
workspace. No manual config needed — just:

```bash
npm install          # once, so the server's dependencies exist
npm run login        # once, on a machine with a display, to capture your Google session
```

Then open the folder in Cowork/Claude Code and approve the `notebooklm` server
when prompted (or run `/mcp` to review it). To register it explicitly from the
CLI instead:

```bash
claude mcp add notebooklm -- node /absolute/path/to/QUANTUM/src/server.js
```

> **Why local:** this server drives *your* logged-in browser, so it must run on
> the same machine as your Google session and the persistent profile. That is
> why it connects to Cowork/Claude Code as a local **stdio** server rather than
> a hosted remote connector.

### Claude Desktop / Claude Code — `mcpServers` config

```json
{
  "mcpServers": {
    "notebooklm": {
      "command": "node",
      "args": ["/absolute/path/to/QUANTUM/src/server.js"],
      "env": {
        "NOTEBOOKLM_HEADLESS": "1"
      }
    }
  }
}
```

Add this to your Claude Desktop config
(`claude_desktop_config.json`) or via `claude mcp add`. Restart the client and
the six `notebooklm_*` tools appear.

A typical flow the model can run:

1. `notebooklm_auth_status` → confirm signed in
2. `notebooklm_list_notebooks` → find the notebook
3. `notebooklm_open_notebook { "title": "Research" }`
4. `notebooklm_ask { "question": "Summarize the key findings" }`

## Configuration

All optional; set as env vars (see `.env.example`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `NOTEBOOKLM_USER_DATA_DIR` | `~/.notebooklm-mcp/profile` | Persistent browser profile |
| `NOTEBOOKLM_HEADLESS` | `0` (visible) | Run browser headless (`1`) |
| `NOTEBOOKLM_CHROMIUM_PATH` | auto-detect | Explicit Chromium binary |
| `NOTEBOOKLM_PROXY` / `HTTPS_PROXY` | none | Outbound proxy for the browser |
| `NOTEBOOKLM_ACTION_TIMEOUT_MS` | `45000` | Per-action timeout |
| `NOTEBOOKLM_ANSWER_TIMEOUT_MS` | `120000` | Max wait for a chat answer |
| `NOTEBOOKLM_LOCALE` | `en-US` | Browser locale |

## Maintenance & limitations

- **UI drift:** NotebookLM ships no stable test IDs. All selectors live in one
  place — `SELECTORS` at the bottom of [`src/notebooklm.js`](src/notebooklm.js).
  If a tool fails with a "could not click …" error, the UI changed; update the
  matching selector there.
- **Terms of service:** This automates a logged-in Google product with your own
  credentials. Use it for your own account and within Google's terms.
- **Not affiliated** with Google. NotebookLM is a trademark of Google.
- **One session at a time:** the persistent profile is single-writer; don't run
  the login script and the server against the same profile simultaneously.

## iCloud Drive MCP

A second, independent MCP server in this repo — [`src/icloud-server.js`](src/icloud-server.js) —
exposes your **iCloud Drive** files to Claude.

iCloud Drive has no public file API, so this server takes the reliable route:
it reads the folder that the iCloud client already keeps **synced on disk**. No
Apple ID, no password, no network — it just reads local files. Because of that
it **must run on a machine that is signed in to iCloud** (your Mac, or a Windows
PC with the iCloud client), not on a remote/cloud host.

It understands iCloud's *"optimize storage"* eviction: when a file lives in the
cloud but its local copy has been removed, iCloud leaves a hidden
`.<name>.icloud` placeholder. The server reports such files as **`cloudOnly`**
(they exist) instead of missing, and can pull them down on demand.

### Tools

| Tool | What it does |
|------|--------------|
| `icloud_status`     | Report the iCloud Drive folder in use and whether it's accessible. Call first. |
| `icloud_list`       | List files/folders in a directory (relative to the iCloud Drive root). |
| `icloud_check_file` | Check a specific file → `present` / `cloudOnly` / `missing`. |
| `icloud_search`     | Recursively find files/folders by name (includes cloud-only files). |
| `icloud_read_file`  | Read a file's contents (utf-8 text, or base64 for binaries like `.xlsx`). |
| `icloud_download`   | Materialize a `cloudOnly` file locally (macOS `brctl`). |

### Verify & connect

```bash
npm install
npm run smoke:icloud   # end-to-end test with a simulated iCloud folder (no account needed)
npm run start:icloud   # run the server on stdio (Ctrl-C to stop)
```

Register it with Claude Desktop / Claude Code:

```json
{
  "mcpServers": {
    "icloud-drive": {
      "command": "node",
      "args": ["/absolute/path/to/QUANTUM/src/icloud-server.js"]
    }
  }
}
```

Or from the CLI: `claude mcp add icloud-drive -- node /absolute/path/to/QUANTUM/src/icloud-server.js`.

A typical flow — validating a file exists:

1. `icloud_status` → confirm iCloud Drive is reachable
2. `icloud_check_file { "path": "001-QUANTUM/Financieros EESS/GIN/GIN_06_2026.xlsx" }`
3. If it comes back `cloudOnly`: `icloud_download { "path": "…/GIN_06_2026.xlsx" }`, then read it.

### Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `ICLOUD_DRIVE_PATH` | macOS: `~/Library/Mobile Documents/com~apple~CloudDocs` · Windows: `~/iCloudDrive` | Root folder the server reads |

## Project layout

```
src/config.js        env-driven config + Chromium auto-detection
src/notebooklm.js    Playwright automation client + SELECTORS
src/server.js        NotebookLM MCP stdio server (tool registration + dispatch)
src/icloud.js        local iCloud Drive reader (placeholder-aware, path-guarded)
src/icloud-server.js iCloud Drive MCP stdio server
scripts/login.js     one-time interactive Google sign-in
scripts/smoke.js     NotebookLM end-to-end MCP handshake smoke test
scripts/icloud-smoke.js  iCloud MCP smoke test (simulated drive, no account)
```

## License

MIT
