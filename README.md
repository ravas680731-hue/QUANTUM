# NotebookLM MCP

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

## Project layout

```
src/config.js        env-driven config + Chromium auto-detection
src/notebooklm.js    Playwright automation client + SELECTORS
src/server.js        MCP stdio server (tool registration + dispatch)
scripts/login.js     one-time interactive Google sign-in
scripts/smoke.js     end-to-end MCP handshake smoke test
```

## License

MIT
