// Crea diario.pdf dalla dashboard: tutta la pagina con la settimana corrente,
// piu' il piano della settimana prossima. Uso: node pdf.js
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
(async () => {
  const here = __dirname;
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1100, height: 1400 }, colorScheme: 'light' });
  await p.goto('file://' + path.join(here, 'dashboard.html'));
  await p.waitForTimeout(800);
  const css = `
    @page { size: A4; margin: 12mm 10mm; }
    .card,.tile,.rec,.pri,table,.sess,.meals,.evs,.kday,.fuel,.wo,.pace { break-inside: avoid; }
    .days, .day, .sess { display: block !important; }
    .day { margin-bottom: 10px; break-inside: auto; }
    .day > * { margin-bottom: 8px; }
    .sess { margin-bottom: 10px; break-inside: auto; }
    .sess > * { margin-top: 5px; }
    .sess > div[style*="flex"] { display: flex !important; }
    section, .grid { break-inside: auto; }
    .day.today { box-shadow: none; }
    section { break-inside: auto; }
    h2 { break-after: avoid; }
    .tabs { display: none !important; }
    .tip { display: none !important; }`;
  await p.addStyleTag({ content: css });
  await p.emulateMedia({ media: 'print', colorScheme: 'light' });
  await p.evaluate(() => window.dispatchEvent(new Event('resize')));
  await p.waitForTimeout(400);
  const opts = { printBackground: true, format: 'A4', margin: { top: '12mm', bottom: '12mm', left: '10mm', right: '10mm' } };
  await p.pdf({ path: path.join(here, 'data', 'part1.pdf'), ...opts });
  const next = await p.$('#cw1');
  if (next) {
    await p.evaluate(() => document.getElementById('cw1').click());
    await p.evaluate(() => {
      document.querySelectorAll('#app > *').forEach(el => { if (el.id !== 'coachsec') el.style.display = 'none'; });
      document.querySelector('#coachsec h2').textContent = 'Il piano del coach: settimana prossima';
    });
    await p.pdf({ path: path.join(here, 'data', 'part2.pdf'), ...opts });
  }
  await b.close();
})();
