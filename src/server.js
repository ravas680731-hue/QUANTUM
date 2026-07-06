#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { NotebookLMClient } from "./notebooklm.js";

/**
 * MCP server exposing Google NotebookLM as tools, driven by Playwright.
 *
 * Transport: stdio, so it plugs directly into Claude Desktop / Claude Code
 * `mcpServers` config or any MCP client.
 */

const client = new NotebookLMClient();

const TOOLS = [
  {
    name: "notebooklm_auth_status",
    description:
      "Check whether there is an active Google/NotebookLM session in the persistent browser profile. Call this first; if it reports authenticated:false the user must run the one-time interactive login.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
    handler: async () => client.authStatus(),
  },
  {
    name: "notebooklm_list_notebooks",
    description:
      "List the NotebookLM notebooks visible on the home page, with their index and title. Reference notebooks by title or index in other tools.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
    handler: async () => ({ notebooks: await client.listNotebooks() }),
  },
  {
    name: "notebooklm_open_notebook",
    description:
      "Open a specific notebook by title (case-insensitive substring match) or by its index from notebooklm_list_notebooks. Must be called before asking questions or adding sources to that notebook.",
    inputSchema: {
      type: "object",
      properties: {
        title: { type: "string", description: "Notebook title or substring." },
        index: { type: "integer", description: "Zero-based index from list_notebooks." },
      },
      additionalProperties: false,
    },
    handler: async (args) => client.openNotebook(args || {}),
  },
  {
    name: "notebooklm_create_notebook",
    description:
      "Create a new empty notebook and open it. Typically followed by notebooklm_add_source.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
    handler: async () => client.createNotebook(),
  },
  {
    name: "notebooklm_add_source",
    description:
      "Add a source to the currently open notebook. type='url' imports a website/link; type='text' pastes raw text.",
    inputSchema: {
      type: "object",
      properties: {
        type: { type: "string", enum: ["url", "text"] },
        value: {
          type: "string",
          description: "The URL (for type=url) or the raw text (for type=text).",
        },
        title: { type: "string", description: "Optional label for the source." },
      },
      required: ["type", "value"],
      additionalProperties: false,
    },
    handler: async (args) => client.addSource(args),
  },
  {
    name: "notebooklm_ask",
    description:
      "Ask a question in the currently open notebook's chat and return NotebookLM's grounded answer (based on that notebook's sources). Open a notebook first with notebooklm_open_notebook.",
    inputSchema: {
      type: "object",
      properties: {
        question: { type: "string", description: "The question to ask NotebookLM." },
      },
      required: ["question"],
      additionalProperties: false,
    },
    handler: async (args) => client.ask(args.question),
  },
];

const server = new Server(
  { name: "notebooklm-mcp", version: "0.1.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: TOOLS.map(({ name, description, inputSchema }) => ({
    name,
    description,
    inputSchema,
  })),
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const tool = TOOLS.find((t) => t.name === request.params.name);
  if (!tool) {
    return {
      isError: true,
      content: [{ type: "text", text: `Unknown tool: ${request.params.name}` }],
    };
  }
  try {
    const result = await tool.handler(request.params.arguments || {});
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  } catch (err) {
    return {
      isError: true,
      content: [{ type: "text", text: `Error: ${err?.message || String(err)}` }],
    };
  }
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  // Log to stderr so it never pollutes the stdio JSON-RPC channel.
  process.stderr.write("notebooklm-mcp server ready on stdio\n");
}

async function shutdown() {
  await client.close().catch(() => {});
  process.exit(0);
}
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

main().catch((err) => {
  process.stderr.write(`Fatal: ${err?.stack || err}\n`);
  process.exit(1);
});
