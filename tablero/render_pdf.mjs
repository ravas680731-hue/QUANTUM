#!/usr/bin/env node
// Render an HTML file to PDF with Chromium (Playwright). Máxima fidelidad.
// Uso: node render_pdf.mjs <input.html> <output.pdf>
import { chromium } from "playwright";
import path from "node:path";

const [, , inHtml, outPdf] = process.argv;
if (!inHtml || !outPdf) {
  console.error("Uso: node render_pdf.mjs <input.html> <output.pdf>");
  process.exit(1);
}

const exe = process.env.TABLERO_CHROMIUM_PATH || undefined;
const browser = await chromium.launch({ executablePath: exe });
const page = await browser.newPage();
await page.goto("file://" + path.resolve(inHtml), { waitUntil: "networkidle" });
await page.emulateMedia({ media: "print" });
await page.pdf({
  path: outPdf,
  printBackground: true,
  preferCSSPageSize: true,
});
await browser.close();
console.error("PDF escrito en " + outPdf);
