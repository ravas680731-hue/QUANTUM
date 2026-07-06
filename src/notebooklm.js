import { chromium } from "playwright";
import { config } from "./config.js";

/**
 * NotebookLMClient drives the Google NotebookLM web application through a
 * persistent Playwright browser context.
 *
 * NotebookLM has no public API, so every capability here is expressed as UI
 * automation. The UI is an Angular Material app whose DOM changes over time;
 * selectors are therefore centralised in SELECTORS below and each lookup uses
 * resilient role/text based fallbacks so a single class rename does not break
 * everything at once.
 */
export class NotebookLMClient {
  constructor() {
    /** @type {import('playwright').BrowserContext | null} */
    this.context = null;
    /** @type {import('playwright').Page | null} */
    this.page = null;
    this._launching = null;
  }

  /** Lazily launch (or reuse) the persistent browser context. */
  async ensureBrowser() {
    if (this.context) return;
    // Guard against concurrent tool calls racing to launch.
    if (this._launching) {
      await this._launching;
      return;
    }
    this._launching = this._launch();
    try {
      await this._launching;
    } finally {
      this._launching = null;
    }
  }

  async _launch() {
    this.context = await chromium.launchPersistentContext(config.userDataDir, {
      headless: config.headless,
      executablePath: config.executablePath,
      locale: config.locale,
      viewport: { width: 1400, height: 900 },
      ...(config.proxyServer ? { proxy: { server: config.proxyServer } } : {}),
      args: ["--no-sandbox", "--disable-blink-features=AutomationControlled"],
    });
    this.context.setDefaultTimeout(config.actionTimeoutMs);
    this.page = this.context.pages()[0] || (await this.context.newPage());
  }

  async close() {
    if (this.context) {
      await this.context.close().catch(() => {});
      this.context = null;
      this.page = null;
    }
  }

  /** Navigate to the NotebookLM home (list of notebooks). */
  async goHome() {
    await this.ensureBrowser();
    await this.page.goto(config.baseUrl, { waitUntil: "domcontentloaded" });
    await this._settle();
  }

  /**
   * Determine whether we currently have a valid Google session.
   * @returns {Promise<{authenticated: boolean, url: string, reason: string}>}
   */
  async authStatus() {
    await this.goHome();
    const url = this.page.url();
    // If Google bounced us to an accounts login/consent screen we are not in.
    const onLogin =
      /accounts\.google\.com|\/signin|ServiceLogin/i.test(url) ||
      (await this._exists('input[type="email"], input[type="password"]'));
    if (onLogin) {
      return {
        authenticated: false,
        url,
        reason:
          "Redirected to a Google sign-in page. Run the one-time login (npm run login) to capture a session.",
      };
    }
    // NotebookLM home shows a "Create new" / notebook grid when signed in.
    const looksReady =
      (await this._exists(SELECTORS.createButton)) ||
      (await this._exists(SELECTORS.notebookCard)) ||
      /notebooklm\.google\.com/i.test(url);
    return {
      authenticated: looksReady,
      url,
      reason: looksReady
        ? "Active NotebookLM session."
        : "Loaded but could not confirm a signed-in NotebookLM UI.",
    };
  }

  /** List notebooks visible on the home page. */
  async listNotebooks() {
    await this.goHome();
    await this._requireAuth();
    // Notebook cards render as project tiles. Collect their titles + index so
    // callers can reference them by title in later calls.
    const cards = this.page.locator(SELECTORS.notebookCard);
    await cards.first().waitFor({ state: "visible", timeout: 8000 }).catch(() => {});
    const count = await cards.count();
    const notebooks = [];
    for (let i = 0; i < count; i++) {
      const card = cards.nth(i);
      const title =
        (await card.locator(SELECTORS.notebookCardTitle).first().textContent().catch(() => null)) ||
        (await card.textContent().catch(() => "")) ||
        "";
      notebooks.push({ index: i, title: title.trim() });
    }
    return notebooks;
  }

  /**
   * Open a notebook by title (case-insensitive substring match) or by index.
   * @param {{title?: string, index?: number}} ref
   */
  async openNotebook(ref) {
    await this.goHome();
    await this._requireAuth();
    const cards = this.page.locator(SELECTORS.notebookCard);
    await cards.first().waitFor({ state: "visible", timeout: 8000 }).catch(() => {});
    const count = await cards.count();

    let target = -1;
    if (typeof ref.index === "number") {
      target = ref.index;
    } else if (ref.title) {
      const needle = ref.title.trim().toLowerCase();
      for (let i = 0; i < count; i++) {
        const t = (await cards.nth(i).textContent().catch(() => "")) || "";
        if (t.toLowerCase().includes(needle)) {
          target = i;
          break;
        }
      }
    }
    if (target < 0 || target >= count) {
      throw new Error(
        `Notebook not found (ref=${JSON.stringify(ref)}). Use list_notebooks to see available titles.`
      );
    }
    await cards.nth(target).click();
    await this._settle();
    await this.page
      .locator(SELECTORS.chatInput)
      .first()
      .waitFor({ state: "visible", timeout: 15000 })
      .catch(() => {});
    return { opened: true, url: this.page.url() };
  }

  /**
   * Create a new empty notebook and return its URL.
   */
  async createNotebook() {
    await this.goHome();
    await this._requireAuth();
    await this._click(SELECTORS.createButton, "Create new notebook button");
    await this._settle();
    // Creating a notebook usually opens the "add source" dialog immediately.
    return { created: true, url: this.page.url() };
  }

  /**
   * Add a source to the currently open notebook.
   * @param {{type: 'url'|'text', value: string, title?: string}} source
   */
  async addSource(source) {
    await this.ensureBrowser();
    await this._requireAuth();
    // Open the add-source dialog if it is not already present.
    if (!(await this._exists(SELECTORS.sourceDialog))) {
      await this._click(SELECTORS.addSourceButton, "Add source button");
      await this._settle();
    }

    if (source.type === "url") {
      // Choose the "Website" / link import chip, then paste the URL.
      await this._clickIfExists(SELECTORS.sourceWebsiteChip);
      const urlInput = this.page.locator(SELECTORS.sourceUrlInput).first();
      await urlInput.waitFor({ state: "visible", timeout: 10000 });
      await urlInput.fill(source.value);
    } else if (source.type === "text") {
      await this._clickIfExists(SELECTORS.sourcePasteTextChip);
      const textInput = this.page.locator(SELECTORS.sourceTextInput).first();
      await textInput.waitFor({ state: "visible", timeout: 10000 });
      await textInput.fill(source.value);
    } else {
      throw new Error(`Unsupported source type: ${source.type}`);
    }

    await this._click(SELECTORS.sourceInsertButton, "Insert/Add source confirm button");
    await this._settle();
    return { added: true, type: source.type };
  }

  /**
   * Ask a question in the currently open notebook's chat and return the answer
   * text once the response has finished streaming.
   * @param {string} question
   */
  async ask(question) {
    await this.ensureBrowser();
    await this._requireAuth();
    const input = this.page.locator(SELECTORS.chatInput).first();
    await input.waitFor({ state: "visible", timeout: 15000 });
    await input.click();
    await input.fill(question);

    // Count existing answer bubbles so we can detect the new one.
    const answers = this.page.locator(SELECTORS.chatAnswer);
    const before = await answers.count().catch(() => 0);

    // Submit: prefer the send button, fall back to Enter.
    if (await this._exists(SELECTORS.chatSendButton)) {
      await this._click(SELECTORS.chatSendButton, "Chat send button");
    } else {
      await input.press("Enter");
    }

    // Wait for a new answer bubble to appear.
    await this.page
      .waitForFunction(
        ([sel, prev]) => document.querySelectorAll(sel).length > prev,
        [SELECTORS.chatAnswer, before],
        { timeout: config.answerTimeoutMs }
      )
      .catch(() => {});

    const answer = answers.last();
    // Wait for streaming to settle: text stops changing for ~1.2s.
    const text = await this._waitForStableText(answer, config.answerTimeoutMs);
    return { question, answer: text };
  }

  // ---- internal helpers ---------------------------------------------------

  async _requireAuth() {
    // Cheap check: if a login form is on screen we are not authenticated.
    if (await this._exists('input[type="password"], input[type="email"]')) {
      throw new Error(
        "Not signed in to Google/NotebookLM. Run the one-time interactive login (npm run login) to capture a session in the persistent profile."
      );
    }
  }

  async _settle() {
    // NotebookLM is a SPA; wait for network to quiet down but never hang.
    await this.page.waitForLoadState("networkidle", { timeout: 8000 }).catch(() => {});
  }

  async _exists(selector) {
    try {
      return (await this.page.locator(selector).count()) > 0;
    } catch {
      return false;
    }
  }

  async _click(selector, label) {
    const loc = this.page.locator(selector).first();
    try {
      await loc.waitFor({ state: "visible", timeout: config.actionTimeoutMs });
      await loc.click();
    } catch (e) {
      throw new Error(
        `Could not click ${label || selector}. The NotebookLM UI may have changed; update SELECTORS in src/notebooklm.js. (${e.message})`
      );
    }
  }

  async _clickIfExists(selector) {
    if (await this._exists(selector)) {
      await this.page.locator(selector).first().click().catch(() => {});
    }
  }

  async _waitForStableText(locator, timeoutMs) {
    const start = Date.now();
    let last = "";
    let stableSince = Date.now();
    while (Date.now() - start < timeoutMs) {
      const cur = (await locator.textContent().catch(() => "")) || "";
      if (cur !== last) {
        last = cur;
        stableSince = Date.now();
      } else if (Date.now() - stableSince > 1200 && cur.trim().length > 0) {
        break;
      }
      await this.page.waitForTimeout(300);
    }
    return last.trim();
  }
}

/**
 * Centralised, best-effort selectors for the NotebookLM UI.
 *
 * NotebookLM ships no stable data-testids, so these lean on aria roles and
 * visible text where possible and fall back to Material component tags. If a
 * tool starts failing with a "could not click" error, update the matching
 * entry here — that is the single maintenance surface for UI drift.
 */
export const SELECTORS = {
  createButton:
    'button:has-text("Create new"), button:has-text("New notebook"), button:has-text("Create"), [aria-label*="Create" i]',
  notebookCard:
    'project-button, mat-card.project-button, [role="button"].project-button, a[href*="/notebook/"]',
  notebookCardTitle: '.project-button-title, .title, h2, h3',
  chatInput:
    'textarea[aria-label*="Ask" i], textarea[placeholder*="Ask" i], textarea, div[contenteditable="true"]',
  chatSendButton:
    'button[aria-label*="Send" i], button[type="submit"]:has(mat-icon), button:has-text("Send")',
  chatAnswer:
    'chat-message.from-assistant, .chat-message.model, .to-user-message, .message-text-content',
  addSourceButton:
    'button:has-text("Add source"), button:has-text("Add sources"), [aria-label*="Add source" i]',
  sourceDialog: 'mat-dialog-container, [role="dialog"]',
  sourceWebsiteChip:
    'button:has-text("Website"), button:has-text("Link"), [aria-label*="Website" i]',
  sourcePasteTextChip:
    'button:has-text("Paste text"), button:has-text("Copied text"), [aria-label*="Paste" i]',
  sourceUrlInput:
    'input[type="url"], input[placeholder*="URL" i], input[placeholder*="link" i]',
  sourceTextInput:
    'textarea[placeholder*="text" i], textarea[aria-label*="text" i], div[contenteditable="true"]',
  sourceInsertButton:
    'button:has-text("Insert"), button:has-text("Add"), button:has-text("Upload"), button[type="submit"]',
};
