import path from "node:path";
import os from "node:os";
import fs from "node:fs";
import fsp from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

/**
 * Local iCloud Drive access.
 *
 * iCloud Drive has no public file API. What it does have is a folder that the
 * macOS/Windows iCloud client keeps in sync on disk. This client simply reads
 * that folder, so it needs no credentials and no network — it just works with
 * whatever iCloud has already synced locally.
 *
 * Default location on macOS:
 *   ~/Library/Mobile Documents/com~apple~CloudDocs
 * On Windows the iCloud client exposes an "iCloud Drive" folder (often
 * %USERPROFILE%\iCloudDrive); point ICLOUD_DRIVE_PATH at it.
 *
 * Eviction / "optimize storage": iCloud can remove a file's local copy to save
 * space while keeping it in the cloud. On disk that shows up as a hidden
 * placeholder named `.<original>.icloud`. This client understands those
 * placeholders, so a file that lives only in the cloud is reported as
 * `cloudOnly` (it exists) rather than missing.
 */
export class ICloudClient {
  constructor(options = {}) {
    this.basePath = options.basePath || defaultBasePath();
  }

  /** Report where we're looking and whether that folder is actually there. */
  async status() {
    const base = this.basePath;
    let exists = false;
    let isDirectory = false;
    try {
      const st = await fsp.stat(base);
      exists = true;
      isDirectory = st.isDirectory();
    } catch {
      /* not present */
    }
    return {
      basePath: base,
      exists,
      isDirectory,
      platform: process.platform,
      note:
        exists && isDirectory
          ? "iCloud Drive folder is accessible."
          : "iCloud Drive folder was not found. This server must run on a machine where iCloud Drive is signed in and synced locally. Override the location with the ICLOUD_DRIVE_PATH environment variable.",
    };
  }

  /** List the entries of a directory (relative to the iCloud Drive root). */
  async list(relPath = "") {
    const dir = this._resolve(relPath);
    const dirents = await fsp.readdir(dir, { withFileTypes: true });

    // Merge real files with their `.icloud` placeholders so each logical name
    // appears once, whether or not it has been downloaded locally.
    const byName = new Map();
    for (const d of dirents) {
      const ph = parsePlaceholder(d.name);
      const name = ph ? ph : d.name;
      const isPlaceholder = ph != null;
      const full = path.join(dir, d.name);
      let entry = byName.get(name);
      if (!entry) {
        entry = { name, type: "file", downloaded: false, cloudOnly: false };
        byName.set(name, entry);
      }
      let st;
      try {
        st = await fsp.stat(full); // follow symlinks; size/mtime of real content
      } catch {
        st = null;
      }
      if (isPlaceholder) {
        entry.cloudOnly = !byName.get(name)?.downloaded;
      } else {
        entry.downloaded = true;
        entry.cloudOnly = false;
        entry.type = d.isDirectory() ? "directory" : "file";
        if (st) {
          entry.size = st.size;
          entry.modified = st.mtime.toISOString();
        }
      }
    }

    const entries = [...byName.values()]
      .map((e) => ({ ...e, cloudOnly: e.cloudOnly && !e.downloaded }))
      .sort((a, b) => {
        if (a.type !== b.type) return a.type === "directory" ? -1 : 1;
        return a.name.localeCompare(b.name);
      });

    return { path: relPath || "/", absolutePath: dir, count: entries.length, entries };
  }

  /**
   * Check whether a specific file exists, distinguishing three states:
   *   present   – downloaded and available locally
   *   cloudOnly – exists in iCloud but not downloaded to this machine
   *   missing   – not found at all
   */
  async checkFile(relPath) {
    if (!relPath) throw new Error("A file path (relative to iCloud Drive) is required.");
    const target = this._resolve(relPath);
    const dir = path.dirname(target);
    const name = path.basename(target);

    let st = null;
    try {
      st = await fsp.stat(target);
    } catch {
      /* fall through to placeholder check */
    }
    if (st) {
      return {
        path: relPath,
        status: "present",
        exists: true,
        downloaded: true,
        type: st.isDirectory() ? "directory" : "file",
        size: st.size,
        modified: st.mtime.toISOString(),
        absolutePath: target,
      };
    }

    // Not present as a real file — is there an iCloud placeholder for it?
    const placeholder = path.join(dir, `.${name}.icloud`);
    let phSt = null;
    try {
      phSt = await fsp.stat(placeholder);
    } catch {
      /* no placeholder either */
    }
    if (phSt) {
      return {
        path: relPath,
        status: "cloudOnly",
        exists: true,
        downloaded: false,
        note: "File exists in iCloud but is not downloaded to this machine. Use icloud_download to materialize it locally.",
        absolutePath: target,
      };
    }

    return {
      path: relPath,
      status: "missing",
      exists: false,
      downloaded: false,
      note: "No file or iCloud placeholder found at this path.",
      absolutePath: target,
    };
  }

  /**
   * Recursively search for entries whose name contains `query`
   * (case-insensitive), including cloud-only placeholders.
   */
  async search(query, { relPath = "", maxDepth = 6, maxResults = 200 } = {}) {
    if (!query) throw new Error("A search query is required.");
    const root = this._resolve(relPath);
    const q = query.toLowerCase();
    const results = [];

    const walk = async (dir, depth) => {
      if (depth > maxDepth || results.length >= maxResults) return;
      let dirents;
      try {
        dirents = await fsp.readdir(dir, { withFileTypes: true });
      } catch {
        return;
      }
      for (const d of dirents) {
        if (results.length >= maxResults) return;
        const ph = parsePlaceholder(d.name);
        const name = ph ? ph : d.name;
        const full = path.join(dir, d.name);
        if (name.toLowerCase().includes(q)) {
          results.push({
            name,
            relativePath: path.relative(this.basePath, ph ? path.join(dir, name) : full),
            cloudOnly: ph != null,
            type: !ph && d.isDirectory() ? "directory" : "file",
          });
        }
        if (!ph && d.isDirectory()) await walk(full, depth + 1);
      }
    };

    await walk(root, 0);
    return { query, count: results.length, truncated: results.length >= maxResults, results };
  }

  /**
   * Read a file's contents. Text files return decoded text; anything else (or
   * when `encoding: "base64"` is requested) returns base64 so binary files such
   * as .xlsx can be transported. Bounded by `maxBytes` to stay MCP-friendly.
   */
  async readFile(relPath, { encoding = "utf-8", maxBytes = 1_000_000 } = {}) {
    if (!relPath) throw new Error("A file path is required.");
    const target = this._resolve(relPath);
    let st;
    try {
      st = await fsp.stat(target);
    } catch {
      const check = await this.checkFile(relPath);
      if (check.status === "cloudOnly") {
        throw new Error(
          "File is in iCloud but not downloaded locally. Run icloud_download first."
        );
      }
      throw new Error(`File not found: ${relPath}`);
    }
    if (st.isDirectory()) throw new Error(`Path is a directory, not a file: ${relPath}`);
    if (st.size > maxBytes) {
      throw new Error(
        `File is ${st.size} bytes, larger than the ${maxBytes}-byte limit. Increase maxBytes to read it.`
      );
    }
    const buf = await fsp.readFile(target);
    if (encoding === "base64") {
      return { path: relPath, size: st.size, encoding: "base64", content: buf.toString("base64") };
    }
    return { path: relPath, size: st.size, encoding: "utf-8", content: buf.toString("utf-8") };
  }

  /**
   * Ask iCloud to download a cloud-only file to this machine (macOS `brctl`),
   * then wait briefly for it to materialize. No-op if already present.
   */
  async download(relPath, { timeoutMs = 60_000, pollMs = 1000 } = {}) {
    if (process.platform !== "darwin") {
      throw new Error("icloud_download is only supported on macOS (uses the `brctl` tool).");
    }
    const before = await this.checkFile(relPath);
    if (before.status === "present") return { path: relPath, status: "present", alreadyLocal: true };
    if (before.status === "missing") throw new Error(`Nothing to download: ${relPath} does not exist.`);

    const target = this._resolve(relPath);
    await execFileAsync("brctl", ["download", target]).catch((err) => {
      throw new Error(`brctl download failed: ${err?.stderr || err?.message || err}`);
    });

    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const now = await this.checkFile(relPath);
      if (now.status === "present") return { path: relPath, status: "present", downloaded: true };
      await sleep(pollMs);
    }
    return {
      path: relPath,
      status: "cloudOnly",
      downloaded: false,
      note: "Download was requested but the file has not finished materializing yet. Try icloud_check_file again shortly.",
    };
  }

  /** Resolve a user-supplied relative path and keep it inside the iCloud root. */
  _resolve(relPath) {
    const base = path.resolve(this.basePath);
    const resolved = path.resolve(base, relPath || "");
    const rel = path.relative(base, resolved);
    if (rel === ".." || rel.startsWith(`..${path.sep}`) || path.isAbsolute(rel)) {
      throw new Error("Path escapes the iCloud Drive root and was rejected.");
    }
    return resolved;
  }
}

/** `.Report.pages.icloud` -> `Report.pages`; non-placeholders -> null. */
function parsePlaceholder(name) {
  const m = /^\.(.+)\.icloud$/.exec(name);
  return m ? m[1] : null;
}

function defaultBasePath() {
  if (process.env.ICLOUD_DRIVE_PATH) return process.env.ICLOUD_DRIVE_PATH;
  if (process.platform === "darwin") {
    return path.join(os.homedir(), "Library", "Mobile Documents", "com~apple~CloudDocs");
  }
  // Best-effort default for the Windows iCloud client.
  return path.join(os.homedir(), "iCloudDrive");
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}
