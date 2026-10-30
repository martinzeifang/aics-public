/** Nachprüfung zu #1854: Öffnet die Risikobewertung und sucht die Meldung. */
import { readFileSync, mkdirSync } from 'node:fs';
import { firefox } from 'playwright';
const BASE = process.env.PROBE_BASE, DATEI = process.env.PROBE_KONTEN;
const OUT = process.env.PROBE_OUT, NAME = process.env.PROBE_NAME || 'instanz';
function zugang() {
  for (const z of readFileSync(DATEI, 'utf-8').split('\n')) {
    const t = z.match(/^\|\s*`?([a-z.]+admin@[^`|\s]+)`?\s*\|\s*`?([^`|\s]+)`?\s*\|/);
    if (t) return { email: t[1], pw: t[2] };
  }
  throw new Error('kein Admin-Konto');
}
const warte = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  mkdirSync(OUT, { recursive: true });
  const { email, pw } = zugang();
  const b = await firefox.launch({ headless: true });
  const p = await (await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1600, height: 1000 } })).newPage();
  const fehler = [];
  p.on('pageerror', e => fehler.push('pageerror: ' + String(e).slice(0, 200)));
  p.on('console', m => { if (m.type() === 'error') fehler.push('console: ' + m.text().slice(0, 200)); });
  await p.goto(`${BASE}/`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await p.fill('input[type="email"], input[name="email"]', email);
  await p.fill('input[type="password"]', pw);
  await p.click('button[type="submit"]');
  await p.waitForSelector('nav, .app-layout, .sidebar', { timeout: 30000 });
  await p.getByRole('link', { name: /Risikobewertung/ }).first().click()
    .catch(async () => { await p.getByText('Risikobewertung', { exact: true }).first().click(); });
  await warte(5000);
  const txt = await p.locator('body').innerText();
  const meldungen = txt.split('\n').filter(z => /Fehler beim Laden|Fehler beim/i.test(z));
  const version = (txt.match(/v\d+\.\d+\.\d+|sha-[0-9a-f]+/) || ['?'])[0];
  await p.screenshot({ path: `${OUT}/${NAME}-rb.png` });
  console.log(`${NAME}: ${meldungen.length ? '✖ ' + JSON.stringify(meldungen.slice(0,3)) : '✔ keine Fehlermeldung'} · Fuß: ${version}`);
  if (fehler.length) console.log(`   Konsole: ${fehler.slice(0, 3).join(' | ')}`);
  await b.close();
})().catch(e => { console.error('Setup:', e); process.exit(2); });
