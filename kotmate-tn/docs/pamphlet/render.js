const { chromium } = require('playwright');
const path = require('path');

async function render(htmlFile, pdfFile) {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const fileUrl = 'file:///' + path.resolve(htmlFile).replace(/\\/g, '/');
  await page.goto(fileUrl, { waitUntil: 'networkidle' });
  await page.pdf({
    path: pdfFile,
    printBackground: true,
    preferCSSPageSize: true,
  });
  await browser.close();
  console.log('wrote', pdfFile);
}

(async () => {
  await render('pamphlet-en.html', 'KOTMate-TN-Pamphlet.pdf');
  await render('pamphlet-ta.html', 'KOTMate-TN-Pamphlet-Tamil.pdf');
})();
