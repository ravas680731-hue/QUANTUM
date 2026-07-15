#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { ICloudClient } from "./icloud.js";

/**
 * MCP server exposing the local iCloud Drive folder as tools.
 *
 * Transport: stdio, so it plugs directly into Claude Desktop / Claude Code
 * `mcpServers` config or any MCP client. It reads the iCloud Drive folder that
 * the iCloud client keeps synced on disk — no Apple ID, password, or network
 * required. It must run on a machine signed in to iCloud.
 */

const client = new ICloudClient();

const TOOLS = [
  {
    name: "icloud_status",
    description:
      "Report the iCloud Drive folder this server is reading and whether it is accessible on this machine. Call this first; if exists is false the server is not running on a machine with iCloud Drive synced (set ICLOUD_DRIVE_PATH to point at it).",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
    handler: async () => client.status(),
  },
  {
    name: "icloud_list",
    description:
      "List the files and folders inside a directory of iCloud Drive. The path is relative to the iCloud Drive root (empty for the root). Each entry reports whether it is downloaded locally or cloudOnly (present in iCloud but not yet downloaded).",
    inputSchema: {
      type: "object",
      properties: {
        path: {
          type: "string",
          description:
            "Directory path relative to the iCloud Drive root, e.g. '01-QUANTUM/Financieros EESS'. Empty or omitted for the root.",
        },
      },
      additionalProperties: false,
    },
    handler: async (args) => client.list(args?.path || ""),
  },
  {
    name: "icloud_check_file",
    description:
      "Check whether a specific file exists in iCloud Drive. Returns status 'present' (downloaded locally), 'cloudOnly' (exists in iCloud but not downloaded to this machine), or 'missing'. Use this to validate that a file such as 'GIN_06_2026.xlsx' exists.",
    inputSchema: {
      type: "object",
      properties: {
        path: {
          type: "string",
          description:
            "File path relative to the iCloud Drive root, e.g. '01-QUANTUM/Financieros EESS/GIN/GIN_06_2026.xlsx'.",
        },
      },
      required: ["path"],
      additionalProperties: false,
    },
    handler: async (args) => client.checkFile(args.path),
  },
  {
    name: "icloud_search",
    description:
      "Recursively search iCloud Drive for files or folders whose name contains the query (case-insensitive). Includes cloud-only files that are not downloaded locally.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Substring to match in file/folder names." },
        path: {
          type: "string",
          description: "Optional subdirectory to search under (relative to root). Empty for whole drive.",
        },
        maxDepth: { type: "integer", description: "Max recursion depth (default 6)." },
        maxResults: { type: "integer", description: "Max results to return (default 200)." },
      },
      required: ["query"],
      additionalProperties: false,
    },
    handler: async (args) =>
      client.search(args.query, {
        relPath: args.path || "",
        maxDepth: args.maxDepth,
        maxResults: args.maxResults,
      }),
  },
  {
    name: "icloud_read_file",
    description:
      "Read the contents of a file in iCloud Drive. Text files return decoded text; use encoding='base64' for binary files (e.g. .xlsx, .pdf, images). The file must be downloaded locally (use icloud_download first if it is cloudOnly).",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "File path relative to the iCloud Drive root." },
        encoding: {
          type: "string",
          enum: ["utf-8", "base64"],
          description: "How to return the content. Default 'utf-8'.",
        },
        maxBytes: {
          type: "integer",
          description: "Refuse to read files larger than this (default 1000000).",
        },
      },
      required: ["path"],
      additionalProperties: false,
    },
    handler: async (args) =>
      client.readFile(args.path, { encoding: args.encoding, maxBytes: args.maxBytes }),
  },
  {
    name: "icloud_download",
    description:
      "Ask iCloud to download a cloud-only file to this machine and wait for it to materialize (macOS only, uses `brctl`). Use when icloud_check_file reports status 'cloudOnly' before reading the file.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "File path relative to the iCloud Drive root." },
        timeoutMs: { type: "integer", description: "How long to wait for the download (default 60000)." },
      },
      required: ["path"],
      additionalProperties: false,
    },
    handler: async (args) => client.download(args.path, { timeoutMs: args.timeoutMs }),
  },
];

const server = new Server(
  { name: "icloud-drive-mcp", version: "0.1.0" },
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
  process.stderr.write("icloud-drive-mcp server ready on stdio\n");
}

main().catch((err) => {
  process.stderr.write(`Fatal: ${err?.stack || err}\n`);
  process.exit(1);
});
