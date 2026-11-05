/**
 * Abnahme von #1784 über einen echten Firefox.
 *
 * Geprüft wird nicht nur, dass der Knopf existiert, sondern dass tatsächlich
 * eine Datei beim Browser ankommt und ein gültiges ZIP ist. Ein Download-Knopf,
 * der eine Fehlerseite oder eine 0-Byte-Datei liefert, sieht im DOM genauso aus
 * wie einer, der funktioniert.
 *
 * Erwartet: Dev-Instanz mit Demo-Benutzern.
 *
 * Lauf:  AICS_BASE=https://localhost:5173 node tools/e2e/backup_download.mjs
 * Exit:  0 = alle Schritte erreicht, 1 = Funde, 2 = Setup-Fehler
 */
import { firefox } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE = process.env.AICS_BASE || 'https://localhost:5173';
const HEADED = process.env.AICS_HEADED === '1';
const TAG = new Date().toISOString().slice(0, 10);
const ROOT = path.dirname(new URL(import.meta.url).pathname);
const SHOTS = path.join(ROOT, 'screens', TAG);
fs.mkdirSync(SHOTS, { recursive: true });

const funde = [];
let n = 0;

function fund(t) { funde.push(t); console.log(`  ⚠ ${t}`); }
function ok(t) { console.log(`  ✓ ${t}`); }

async function shot(page, name) {
  const datei = `1784-${String(++n).padStart(2, '0')}-${name}.png`;
  await page.screenshot({ path: path.join(SHOTS, datei), fullPage: true });
  console.log(`  📷 ${datei}`);
}

async function warte(fn, { timeout = 15000, intervall = 250 } = {}) {
  const ende = Date.now() + timeout;
  for (;;) {
    try { if (await fn()) return true; } catch { /* noch nicht da */ }
    if (Date.now() > ende) return false;
    await new Promise(r => setTimeout(r, intervall));
  }
}

async function login(page) {
  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
  await page.locator('input[type=email], input[type=text]').first().fill('admin@example.com');
  await page.locator('input[type=password]').first().fill('admin-password');
  await page.locator('button', { hasText: /Anmelden/i }).first().click();
  if (!await warte(async () => !/\/login/.test(page.url()))) {
    throw new Error('Login fehlgeschlagen');
  }
}

const browser = await firefox.launch({ headless: !HEADED });
const ctx = await browser.newContext({ ignoreHTTPSErrors: true, acceptDownloads: true });
const page = await ctx.newPage();

try {
  console.log('→ Anmelden');
  await login(page);

  console.log('→ Backup-Verwaltung');
  await page.goto(`${BASE}/admin/backup`, { waitUntil: 'domcontentloaded' });
  if (!await warte(() => page.locator('button', { hasText: /Neues Backup erstellen/i }).count())) {
    throw new Error('Backup-Ansicht nicht erreicht');
  }
  await shot(page, 'uebersicht');

  // Mindestens ein Backup muss da sein, sonst gibt es keine Zeile zum Testen.
  const zeilen = () => page.locator('tbody tr').filter({ has: page.locator('code') }).count();
  if (!(await zeilen())) {
    console.log('→ Backup erstellen (noch keines vorhanden)');
    await page.locator('button', { hasText: /Neues Backup erstellen/i }).first().click();
    if (!await warte(async () => (await zeilen()) > 0, { timeout: 60000 })) {
      throw new Error('Backup wurde nicht erstellt');
    }
  }
  ok(`${await zeilen()} Backup(s) in der Liste`);

  console.log('→ Herunterladen');
  const knopf = page.locator('button', { hasText: /Herunterladen/i }).first();
  if (!(await knopf.count())) {
    fund('Kein Knopf „Herunterladen" in der Backup-Tabelle (#1784 nicht wirksam)');
  } else {
    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 30000 }),
      knopf.click(),
    ]);
    const name = download.suggestedFilename();
    const ziel = path.join(SHOTS, `1784-datei-${name}`);
    await download.saveAs(ziel);
    const groesse = fs.statSync(ziel).size;

    if (!/^backup_.*\.zip$/.test(name)) fund(`Dateiname unerwartet: ${name}`);
    else ok(`Datei angekommen: ${name}`);

    if (groesse < 200) fund(`Datei ist ${groesse} Byte groß — kein brauchbares Backup`);
    else ok(`${(groesse / 1024).toFixed(1)} KB`);

    // Ein ZIP beginnt mit PK\x03\x04. Eine HTML-Fehlerseite täte das nicht und
    // käme als „Download" trotzdem an.
    const kopf = fs.readFileSync(ziel).subarray(0, 4);
    if (kopf[0] !== 0x50 || kopf[1] !== 0x4b) fund('Datei ist kein ZIP-Archiv');
    else ok('gültiges ZIP-Archiv');

    fs.unlinkSync(ziel);
  }

  // Der Hinweis nach dem Download soll sagen, was zu tun ist: Die Datei gehört
  // vom Server weg, sonst war der Download zwecklos.
  const text = (await page.locator('body').innerText()).replace(/\s+/g, ' ');
  if (!/außerhalb dieses Servers/i.test(text)) {
    fund('Nach dem Download fehlt der Hinweis zur Aufbewahrung');
  } else {
    ok('Hinweis zur Aufbewahrung steht da');
  }
  await shot(page, 'nach-download');

  console.log(funde.length ? `\n${funde.length} Fund(e):` : '\n0 Funde.');
  funde.forEach(f => console.log(` - ${f}`));
  await browser.close();
  process.exit(funde.length ? 1 : 0);
} catch (e) {
  console.error(`\nSetup-/Ablauffehler: ${e.message}`);
  try { await shot(page, 'fehler'); } catch { /* egal */ }
  await browser.close();
  process.exit(2);
}
