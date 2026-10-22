/**
 * Abnahme der fachlichen Prüfung KI-erzeugter Bewertungen (#1765) in Firefox.
 *
 * Geprüft wird das, was den Unterschied macht: Steht der Hinweis an der
 * Bewertung, auf die er sich bezieht — und lässt sich die Prüfung dort
 * bestätigen, ohne die Seite neu zu laden? Je Schritt ein Bild; die Bilder
 * werden danach angesehen, ein grüner Lauf allein beweist nichts.
 *
 * Voraussetzung: Im Register stehen für das Demo-Projekt zwei Einträge —
 * AI1-01 ungeprüft, AI1-02 geprüft.
 *
 * Lauf:  node tools/e2e/ki_pruefung.mjs
 * Exit:  0 = alle Schritte erreicht, 1 = Funde, 2 = Setup-Fehler
 */
import { firefox } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE = process.env.AICS_BASE || 'https://127.0.0.1:5173';
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
  const datei = `ki-${String(++n).padStart(2, '0')}-${name}.png`;
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

/** Öffnet eine Anforderung im Anforderungsreiter. */
async function anforderung_oeffnen(page, rid) {
  await page.goto(`${BASE}/cra?projekt=${encodeURIComponent(PROJEKT)}&tab=anforderungen`,
    { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2200);
  const zeile = page.locator(`text=${rid}`).first();
  if (!(await zeile.count())) { fund(`Anforderung ${rid} nicht in der Liste`); return false; }
  await zeile.click();
  await page.waitForTimeout(1400);
  // Der Hinweis sitzt am Bewertungsfeld, also unterhalb des Sichtfelds.
  await page.evaluate(() => {
    const el = [...document.querySelectorAll('*')]
      .find((e) => /KI-Entwurf|Fachlich geprüft/i.test(e.textContent || '')
                   && e.children.length <= 4);
    if (el) el.scrollIntoView({ block: 'center' });
  });
  await page.waitForTimeout(500);
  return true;
}

async function main() {
  const browser = await firefox.launch({ headless: !HEADED });
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1600, height: 1000 } });
  const page = await ctx.newPage();
  page.on('console', (m) => { if (m.type() === 'error') fund(`Konsole: ${m.text().slice(0, 160)}`); });
  page.on('response', (r) => { if (r.status() >= 500) fund(`HTTP ${r.status()} ${r.url().slice(0, 120)}`); });

  await login(page);
  console.log('  🔑 angemeldet');

  // 1 — ungeprüfter Entwurf
  if (await anforderung_oeffnen(page, 'AI1-01')) {
    const hin = await page.locator('text=/KI-Entwurf/i').count();
    if (!hin) fund('AI1-01: Hinweis „KI-Entwurf" fehlt');
    const knopf = page.locator('button', { hasText: /Fachlich geprüft/i }).first();
    if (!(await knopf.count())) fund('AI1-01: Schaltfläche „Fachlich geprüft" fehlt');
    await shot(page, 'entwurf-ungepruueft', 'AI1-01 — ungeprüfter KI-Entwurf',
      'Hinweis „🤖 KI-Entwurf (ollama, …) — fachlich nicht geprüft" plus Schaltfläche, direkt am Bewertungsfeld');

    // 2 — Prüfung bestätigen, ohne Neuladen
    if (await knopf.count()) {
      await knopf.click();
      await page.waitForTimeout(1800);
      const jetzt = await page.locator('text=/Fachlich geprüft von/i').count();
      if (!jetzt) fund('AI1-01: nach dem Klick keine Bestätigung „Fachlich geprüft von …"');
      await shot(page, 'entwurf-bestaetigt', 'AI1-01 — nach der Bestätigung',
        'Umschaltung ohne Neuladen: „✓ Fachlich geprüft von admin@example.com am …"');
    }
  }

  // 3 — bereits geprüft: ruhig, keine Schaltfläche
  if (await anforderung_oeffnen(page, 'AI1-02')) {
    if (!(await page.locator('text=/Fachlich geprüft von/i').count()))
      fund('AI1-02: Bestätigung fehlt, obwohl im Register geprüft');
    await shot(page, 'bereits-gepruueft', 'AI1-02 — bereits geprüft',
      'Nur die unaufdringliche Zeile „✓ Fachlich geprüft von … am …", keine Schaltfläche');
  }

  // 4 — eine Anforderung ohne Registereintrag zeigt nichts
  if (await anforderung_oeffnen(page, 'AI1-04')) {
    if (await page.locator('text=/KI-Entwurf/i').count())
      fund('AI1-04: Hinweis erscheint, obwohl kein Registereintrag besteht');
    await shot(page, 'ohne-eintrag', 'AI1-04 — nicht KI-erzeugt',
      'Kein Hinweis, keine leere Zeile — nicht KI-erzeugt heißt: nichts anzeigen');
  }

  fs.writeFileSync(path.join(SHOTS, 'ki-pruefung.md'),
    `# Abnahme KI-Prüfung (#1765) — ${TAG}\n\n` +
    bilder.map((b) => `## ${b.datei}\n**${b.titel}**\n\nErwartung: ${b.erwartung}\n`).join('\n') +
    (funde.length ? `\n## Funde\n${funde.map((f) => `- ${f}`).join('\n')}\n` : '\n## Funde\nkeine\n'));

  await browser.close();
  console.log(funde.length ? `\n${funde.length} Fund(e)` : '\nkeine Funde');
  process.exit(funde.length ? 1 : 0);
}

main().catch((e) => { console.error('Setup-Fehler:', e.message); process.exit(2); });
