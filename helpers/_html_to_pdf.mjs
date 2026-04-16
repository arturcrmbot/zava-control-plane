// Render an HTML file to PDF via puppeteer (bundled with mermaid-cli).
// Usage: node _html_to_pdf.mjs <input.html> <output.pdf>
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';

const puppeteerPath = 'C:/Users/arzielinski/AppData/Roaming/npm/node_modules/@mermaid-js/mermaid-cli/node_modules/puppeteer/lib/esm/puppeteer/puppeteer.js';
const puppeteer = (await import(pathToFileURL(puppeteerPath).href)).default;

const [htmlPath, pdfPath] = process.argv.slice(2);
if (!htmlPath || !pdfPath) {
    console.error('Usage: node _html_to_pdf.mjs <input.html> <output.pdf>');
    process.exit(2);
}

const htmlUrl = pathToFileURL(resolve(htmlPath)).href;
const browser = await puppeteer.launch({ headless: 'new' });
try {
    const page = await browser.newPage();
    await page.goto(htmlUrl, { waitUntil: 'networkidle0' });
    await page.pdf({
        path: resolve(pdfPath),
        format: 'A4',
        printBackground: true,
        margin: { top: '15mm', right: '15mm', bottom: '15mm', left: '15mm' },
    });
    console.log(`Wrote: ${pdfPath}`);
} finally {
    await browser.close();
}
