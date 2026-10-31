/**
 * Abnahme der v8.0.1-Funktionen über einen echten Firefox (#1760–#1764).
 *
 * Geprüft wird, was auf dem Bild zu sehen ist — ein grüner Playwright-Lauf
 * beweist nur, dass Elemente existieren. Je Schritt ein Bild mit der
 * Erwartung; die Bilder werden danach angesehen.
 *
 * Lauf:  AICS_BASE=https://localhost:5173 node tools/e2e/luecken_801.mjs
 * Exit:  0 = alle Schritte erreicht, 1 = Funde, 2 = Setup-Fehler
 */
import { firefox } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE = process.env.AICS_BASE || 'https://localhost:5173';
const PROJEKT = process.env.AICS_DEMO || 'Cyberwoks Demo GmbH – Gateway';
const HEADED = process.env.AICS_HEADED === '1';
const TAG = new Date().toISOString().slice(0, 10);
const ROOT = path.dirname(new URL(import.meta.url).pathname);
const SHOTS = path.join(ROOT, 'screens', TAG);
fs.mkdirSync(SHOTS, { recursive: true });

const bilder = [];
const funde = [];
let n = 0;

async function shot(page, name, titel, erwartung) {
  const datei = `801-${String(++n).padStart(2, '0')}-${name}.png`;
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

async function tab(page, id) {
  await page.goto(`${BASE}/cra?projekt=${encodeURIComponent(PROJEKT)}&tab=${id}`,
    { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2600);
}

/** Klappt den ersten Abschnitt auf, dessen Text passt. */
async function aufklappen(page, muster) {
  const ok = await page.evaluate((m) => {
    const re = new RegExp(m, 'i');
    const kandidat = [...document.querySelectorAll('button, summary, .zeile, tr, .kopf')]
      .find((el) => re.test(el.textContent || ''));
    if (!kandidat) return false;
    kandidat.scrollIntoView({ block: 'center' });
    kandidat.click();
    return true;
  }, muster);
  await page.waitForTimeout(1400);
  return ok;
}

async function main() {
  const browser = await firefox.launch({ headless: !HEADED });
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1600, height: 1200 } });
  const page = await ctx.newPage();
  page.on('console', (m) => { if (m.type() === 'error') fund(`Konsole: ${m.text().slice(0, 160)}`); });
  page.on('response', (r) => { if (r.status() >= 500) fund(`HTTP ${r.status()} ${r.url().slice(0, 120)}`); });

  await login(page);
  console.log('  🔑 angemeldet');

  // ── #1760 Meldeakte ──────────────────────────────────────────────────────
  await tab(page, 'meldungen');
  if (!(await page.locator('text=/Nachweis/i').count())) fund('Meldungen: Nachweis-Spalte fehlt');
  await shot(page, 'meldungen-liste', '#1760 — Meldungen mit Nachweis-Spalte',
    'Je Meldung „✓ belegt" bzw. „⚠ n Pflichtangabe(n) fehlen"; die zweite Akte ohne Adressat fällt auf');

  if (await aufklappen(page, 'Aktiv ausgenutzte Schwachstelle')) {
    const hatCsirt = await page.locator('text=/CSIRT/i').count();
    const hatEnisa = await page.locator('text=/ENISA/i').count();
    if (!hatCsirt || !hatEnisa) fund('Meldeakte: CSIRT/ENISA-Karte nicht sichtbar');
    await shot(page, 'meldeakte-offen', '#1760 — geöffnete Meldeakte',
      'Fristenliste, Adressatenkarte je Stufe mit CSIRT (Mitgliedstaat, Referenz) und ENISA, Nutzerunterrichtung, „Was die Akte (noch) nicht belegt"');
  } else { fund('Meldeakte ließ sich nicht aufklappen'); }

  // ── #1761 SBOM-Komponenten ───────────────────────────────────────────────
  await tab(page, 'pflichtdoku');
  await page.evaluate(() => {
    const el = [...document.querySelectorAll('*')].find((e) => /SBOM/i.test(e.textContent || '') && e.children.length <= 6);
    if (el) el.scrollIntoView({ block: 'center' });
  });
  await page.waitForTimeout(600);
  await shot(page, 'sbom-uebersicht', '#1761 — SBOM-Abschnitt (C1)',
    'SBOM-Zeilen je Release-Version, aufklappbar; 2.1.0 und 2.0.0 vorhanden');

  if (await aufklappen(page, '2\\.1\\.0')) {
    const hatVergleich = await page.locator('text=/neu|angehoben|entfallen/i').count();
    if (!hatVergleich) fund('SBOM: Vergleichs-Pillen (neu/angehoben/entfallen) fehlen');
    await shot(page, 'sbom-komponenten', '#1761 — Komponentenliste + Release-Vergleich',
      'Pillen neu/angehoben/entfallen gegen 2.0.0 (2 neu: jinja2, httpx · 2 angehoben: requests, cryptography · 1 entfallen: pyyaml) und die Komponententabelle mit Bewertungsstand');
  } else { fund('SBOM-Zeile 2.1.0 ließ sich nicht aufklappen'); }

  // ── #1762 Marktüberwachung ───────────────────────────────────────────────
  await tab(page, 'korrektur');
  const hatBehoerden = await page.locator('text=/Marktüberwachung|Behörde/i').count();
  if (!hatBehoerden) fund('Korrektur-Reiter: Marktüberwachungs-Abschnitt fehlt');
  await page.evaluate(() => {
    const el = [...document.querySelectorAll('*')].find((e) => /Marktüberwachung/i.test(e.textContent || '') && e.children.length <= 6);
    if (el) el.scrollIntoView({ block: 'center' });
  });
  await page.waitForTimeout(600);
  await shot(page, 'marktueberwachung', '#1762 — Marktüberwachungsregister',
    'Zwei Vorgänge: BNetzA (Frist in 5 Tagen, laufend) und AT (Frist vor 12 Tagen → versäumt, rot)');

  // ── #1762 Update-Zusagen + Fristenuhr ────────────────────────────────────
  await tab(page, 'konformitaet');
  await page.evaluate(() => {
    const el = [...document.querySelectorAll('*')].find((e) => /Unterstützungszeitraum|Support/i.test(e.textContent || '') && e.children.length <= 6);
    if (el) el.scrollIntoView({ block: 'center' });
  });
  await page.waitForTimeout(600);
  await shot(page, 'support-zusagen', '#1762 — Update-Zusagen und Fristenuhr',
    'Getrennte Kanäle für Sicherheits-/Funktionsupdates, beide Zusagen angehakt, Kaufhinweis, Fristenampel');

  // ── Gate: wirken die neuen Punkte? ───────────────────────────────────────
  await tab(page, 'releases');
  await shot(page, 'releases', 'Gate — Release-Übersicht',
    'Die neuen gerechneten Punkte dürfen NICHT als „nicht geprüft" erscheinen, wenn Daten vorliegen');

  fs.writeFileSync(path.join(SHOTS, 'luecken-801.md'),
    `# Abnahme v8.0.1 (#1760–#1764) — ${TAG}\n\n` +
    bilder.map((b) => `## ${b.datei}\n**${b.titel}**\n\nErwartung: ${b.erwartung}\n`).join('\n') +
    (funde.length ? `\n## Funde\n${funde.map((f) => `- ${f}`).join('\n')}\n` : '\n## Funde\nkeine\n'));

  await browser.close();
  console.log(funde.length ? `\n${funde.length} Fund(e)` : '\nkeine Funde');
  process.exit(funde.length ? 1 : 0);
}

main().catch((e) => { console.error('Setup-Fehler:', e.message); process.exit(2); });
