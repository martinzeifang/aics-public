/**
 * Abnahme Sortierung/Filter in den Seitenleisten (#1764) über Firefox.
 *
 * Geprüft wird, was man am Bild sieht und nicht am Selektor: Erscheint die
 * Leiste überhaupt, stimmen die Trefferzähler der Chips, und sortiert
 * „Zuletzt geändert" auch die **Firmen-Gruppen** mit — sonst stünde die zuletzt
 * angefasste Bewertung weit unten in einer alphabetischen Firmenliste.
 *
 * Lauf:  AICS_BASE=https://localhost:5173 node tools/e2e/sidebar_filter.mjs
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

const bilder = [];
const funde = [];
let n = 0;

async function shot(page, name, titel, erwartung) {
  const datei = `sb-${String(++n).padStart(2, '0')}-${name}.png`;
  await page.screenshot({ path: path.join(SHOTS, datei), fullPage: true });
  bilder.push({ datei, titel, erwartung });
  console.log(`  📷 ${datei} — ${titel}`);
}
function fund(t) { funde.push(t); console.log(`  ⚠ ${t}`); }

async function login(page) {
  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(900);
  await page.locator('input[type=email], input[type=text]').first().fill('admin@example.com');
  await page.locator('input[type=password]').first().fill('admin-password');
  await page.locator('button', { hasText: /Anmelden/i }).first().click();
  await page.waitForTimeout(2600);
  if (/\/login/.test(page.url())) throw new Error('Login fehlgeschlagen');
}

/** Reihenfolge der Einträge in der Seitenleiste, von oben nach unten. */
async function reihenfolge(page) {
  return page.evaluate(() => {
    const sb = document.querySelector('aside, .sidebar, nav.sidebar');
    if (!sb) return [];
    return [...sb.querySelectorAll('*')]
      .filter((e) => e.children.length === 0 && (e.textContent || '').trim().length > 3)
      .map((e) => (e.textContent || '').trim()).slice(0, 40);
  });
}

async function main() {
  const browser = await firefox.launch({ headless: !HEADED });
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1600, height: 1100 } });
  const page = await ctx.newPage();
  page.on('console', (m) => { if (m.type() === 'error') fund(`Konsole: ${m.text().slice(0, 160)}`); });
  page.on('response', (r) => { if (r.status() >= 500) fund(`HTTP ${r.status()} ${r.url().slice(0, 120)}`); });

  await login(page);
  console.log('  🔑 angemeldet');

  await page.goto(`${BASE}/risikobewertung`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2600);
  await shot(page, 'rb-start', 'Risikobewertung — Seitenleiste im Ausgangszustand',
    'Such-, Sortier- und Filterleiste sichtbar (13 Bewertungen, Schwelle 5); Sortierung „Name A–Z"');

  const vorher = await reihenfolge(page);

  // Sortierung umstellen
  const sel = page.locator('aside select, .sidebar select').first();
  if (!(await sel.count())) {
    fund('Kein Sortier-/Filter-Auswahlfeld in der Seitenleiste gefunden');
  } else {
    const opts = await page.locator('aside select, .sidebar select').first()
      .locator('option').allTextContents();
    console.log(`  Auswahlfeld 1 Optionen: ${opts.join(' | ')}`);
    await sel.selectOption({ label: /Zuletzt geändert/i }).catch(() => sel.selectOption({ index: 1 }));
    await page.waitForTimeout(1200);
    const nachher = await reihenfolge(page);
    if (JSON.stringify(vorher) === JSON.stringify(nachher))
      fund('Sortierung „Zuletzt geändert" ändert die Reihenfolge nicht');
    await shot(page, 'rb-sortiert', 'Risikobewertung — nach „Zuletzt geändert"',
      'Andere Reihenfolge als im ersten Bild; die Firmen-Gruppen folgen der Sortierung mit');
  }

  // Filter-Chip „offene Risiken"
  const chip = page.locator('aside button, .sidebar button').filter({ hasText: /offene Risiken/i }).first();
  if (!(await chip.count())) {
    fund('Filter-Chip „offene Risiken" nicht gefunden');
  } else {
    console.log(`  Chip-Text: ${(await chip.textContent() || '').trim()}`);
    await chip.click();
    await page.waitForTimeout(1200);
    await shot(page, 'rb-filter-offen', 'Risikobewertung — Filter „offene Risiken"',
      'Nur Bewertungen mit offenen Risiken; Trefferzahl am Chip passt zur Liste; „Filter zurücksetzen" sichtbar');
  }

  // CRA
  await page.goto(`${BASE}/cra`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2600);
  await shot(page, 'cra-start', 'CRA — Seitenleiste',
    'Bei 3 Projekten: KEINE Sortier-/Filterleiste (Schwelle 5) — die Leiste darf hier nicht erscheinen');

  fs.writeFileSync(path.join(SHOTS, 'sidebar-filter.md'),
    `# Abnahme Seitenleisten-Filter (#1764) — ${TAG}\n\n` +
    bilder.map((b) => `## ${b.datei}\n**${b.titel}**\n\nErwartung: ${b.erwartung}\n`).join('\n') +
    (funde.length ? `\n## Funde\n${funde.map((f) => `- ${f}`).join('\n')}\n` : '\n## Funde\nkeine\n'));

  await browser.close();
  console.log(funde.length ? `\n${funde.length} Fund(e)` : '\nkeine Funde');
  process.exit(funde.length ? 1 : 0);
}

main().catch((e) => { console.error('Setup-Fehler:', e.message); process.exit(2); });
