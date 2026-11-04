/**
 * Abnahme von #1773/#1774 über einen echten Firefox.
 *
 * Geprüft wird, was auf dem Bild zu sehen ist. Ein grüner Playwright-Lauf
 * beweist nur, dass Elemente existieren — in v8.0.2 waren vier Fehler genau
 * dieser Art: Das Element war da und trug plausiblen, falschen Text.
 *
 * Erwartet die Demo-Daten aus der Abnahme: ein CRA-Projekt mit zwei Releases,
 * gemischten Ökosystemen und zwei offenen Befunden.
 *
 * Lauf:  AICS_BASE=https://localhost:5173 node tools/e2e/komponenten_klassen.mjs
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
  const datei = `1773-${String(++n).padStart(2, '0')}-${name}.png`;
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
  await page.waitForTimeout(2800);
  if (/\/login/.test(page.url())) throw new Error('Login fehlgeschlagen');
}

/** Klappt das erste Element auf, dessen Text passt. */
async function klick(page, muster, wahl = 'button, summary, tr, .kl-g-kopf, .zeile') {
  const ok = await page.evaluate(([m, sel]) => {
    const re = new RegExp(m, 'i');
    const el = [...document.querySelectorAll(sel)]
      .find((e) => re.test(e.textContent || '') && e.offsetParent !== null);
    if (!el) return false;
    el.scrollIntoView({ block: 'center' });
    el.click();
    return true;
  }, [muster, wahl]);
  await page.waitForTimeout(1500);
  return ok;
}

async function text(page) { return (await page.locator('body').innerText()).replace(/\s+/g, ' '); }

async function main() {
  const browser = await firefox.launch({ headless: !HEADED });
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true,
                                         viewport: { width: 1600, height: 1300 } });
  const page = await ctx.newPage();
  page.on('console', (m) => {
    if (m.type() === 'error') fund(`Konsole: ${m.text().slice(0, 180)}`);
  });

  // #1773: Die Gruppe „Einzelprüfung" fragt über window.confirm nach. Beim
  // ersten Mal wird abgelehnt — die Frage muss erscheinen, nicht nur der Code
  // dahinter stimmen.
  let dialogText = '';
  let dialogAnnehmen = false;
  page.on('dialog', async (d) => {
    dialogText = d.message();
    console.log(`  💬 Dialog: ${d.message().slice(0, 120)}`);
    if (dialogAnnehmen) await d.accept(); else await d.dismiss();
  });

  await login(page);

  // ── Schritt 1: Komponentenliste mit Befund-Spalte (#1774) ─────────────────
  await page.goto(`${BASE}/cra?projekt=${encodeURIComponent(PROJEKT)}&tab=pflichtdoku`,
                  { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
  // Aufklappen und **prüfen**, dass es offen ist: Ein Klick auf ein <summary>
  // schaltet um — war der Abschnitt schon offen, schließt er. Das Bild zeigte
  // daraufhin eine leere Seite, obwohl die Daten geladen waren.
  const c1Offen = await page.evaluate(() => {
    const d = [...document.querySelectorAll('details')]
      .find((x) => /C1\s*[—-]\s*SBOM/.test(x.querySelector('summary')?.textContent || ''));
    if (!d) return false;
    d.open = true;
    d.scrollIntoView({ block: 'start' });
    return true;
  });
  if (!c1Offen) throw new Error('Abschnitt „C1 — SBOM-Verzeichnis" nicht gefunden');
  await page.waitForTimeout(1500);
  // Die 1.1.0-Zeile aufklappen: „▸ Liste & Vergleich" in der Zeile mit 1.1.0.
  const auf = await page.evaluate(() => {
    const zeile = [...document.querySelectorAll('tr')]
      .find((tr) => /1\.1\.0/.test(tr.textContent || '') && /Liste/.test(tr.textContent || ''));
    if (!zeile) return false;
    const b = [...zeile.querySelectorAll('button')].find((x) => /Liste/.test(x.textContent || ''));
    if (!b) return false;
    b.scrollIntoView({ block: 'center' });
    b.click();
    return true;
  });
  if (!auf) throw new Error('Knopf „Liste & Vergleich" für 1.1.0 nicht gefunden');
  await page.waitForTimeout(2800);
  await page.evaluate(() => {
    document.querySelector('.komp-table')?.scrollIntoView({ block: 'center' });
  });
  await page.waitForTimeout(600);

  let t = await text(page);
  if (!/Befunde/.test(t)) fund('Spalte „Befunde" fehlt in der Komponentenliste');
  if (!/🛡️/.test(t)) fund('Kein Befund-Abzeichen an einer Komponente sichtbar');
  if (!/Widerspruch/.test(t)) fund('„⚠️ Widerspruch" fehlt, obwohl libssl3 nicht_relevant mit offenem Befund ist');
  await shot(page, 'komponentenliste',
             'Komponentenliste mit Befund-Spalte',
             'Spalte „Befunde": 🛡️ 1 offen an cryptography und libssl3; '
             + 'an libssl3 zusätzlich „⚠️ Widerspruch" neben „nicht relevant"');

  // ── Schritt 2: Gruppen nach Klasse (#1773) ────────────────────────────────
  if (!await klick(page, 'Nach Klassen bewerten', 'button')) {
    throw new Error('Knopf „🧩 Nach Klassen bewerten" nicht gefunden');
  }
  await page.waitForTimeout(2600);
  t = await text(page);
  for (const erwartet of ['Einzelprüfung', 'Betriebssystem-Paket', 'Anwendungsabhängigkeit',
                          'Basis-Image', 'Herkunft unbestimmt']) {
    if (!t.includes(erwartet)) fund(`Gruppe fehlt: ${erwartet}`);
  }
  if (!/44 Komponenten/.test(t)) fund('Gesamtzahl 44 Komponenten nicht angezeigt');
  if (!/6 Gruppe/.test(t)) fund('Gruppenzahl 6 nicht angezeigt');
  await shot(page, 'gruppen',
             'Gruppen nach Klasse × Ökosystem',
             '6 Gruppen; „Einzelprüfung — eigener Befund vorhanden" steht oben und '
             + 'ist rötlich hinterlegt; je Gruppe Anzahl, offen, neu/angehoben');

  // ── Schritt 3: Prompt je Gruppe ───────────────────────────────────────────
  if (!await klick(page, 'Betriebssystem-Paket', '.kl-g-kopf')) {
    fund('Gruppe „Betriebssystem-Paket" nicht aufklappbar');
  }
  await page.waitForTimeout(1200);
  if (!await klick(page, 'Prompt erzeugen', 'button')) fund('Knopf „Prompt erzeugen" fehlt');
  await page.waitForTimeout(2200);
  await klick(page, 'Prompt ansehen', 'summary');
  t = await text(page);
  if (!/Art\. 13 Abs\. 5/.test(t)) fund('Prompt nennt Art. 13 Abs. 5 nicht');
  if (!/GHCR/.test(t)) fund('Nachweise aus der Anwendung fehlen im Prompt (GHCR-Kanal)');
  await shot(page, 'prompt',
             'Serverseitig gebauter Prompt der Gruppe',
             'Prompt mit Produkt/Release, Klasse, Sorgfaltsmaßstab, „Nachweise aus '
             + 'der Anwendung" (GHCR, 7 Jahre) und dem engen Auftrag');

  // ── Schritt 4: Begründung für die Gruppe übernehmen ───────────────────────
  const feld = page.locator('.kl-form textarea').first();
  await feld.fill('Die Pakete stammen aus der Distribution des Basis-Images und werden '
                  + 'über deren Sicherheitsupdates versorgt. Ein neuer Stand gelangt über '
                  + 'einen Image-Rebuild und ein Release in das Produkt; ausgeliefert wird '
                  + 'über GHCR-Image-Tags. Sicherheitsupdates sind für sieben Jahre '
                  + 'kostenlos zugesagt. Der Überwachungsweg für Einzelpakete ist zu '
                  + 'dokumentieren.');
  await page.waitForTimeout(400);
  if (!await klick(page, 'Komponente\\(n\\) übernehmen', 'button.btn-primary')) {
    throw new Error('Übernahme-Knopf nicht gefunden');
  }
  await page.waitForTimeout(3000);
  t = await text(page);
  if (!/Komponente\(n\) bewertet/.test(t)) fund('Keine Erfolgsmeldung nach der Übernahme');
  await shot(page, 'uebernommen',
             'Gruppe übernommen',
             '„✓ 15 Komponente(n) bewertet"; die Gruppe zeigt danach 0 offen');

  // ── Schritt 5: Einzelprüfung verlangt eine Bestätigung (#1774) ────────────
  await klick(page, 'Einzelprüfung', '.kl-g-kopf');
  await page.waitForTimeout(1000);
  const feld2 = page.locator('.kl-gruppe.einzel .kl-form textarea').first();
  if (await feld2.count()) {
    await feld2.fill('Der Befund wird in C3 behandelt; ein Fix ist für das nächste '
                     + 'Release eingeplant.');
    await page.waitForTimeout(300);
    await page.locator('.kl-gruppe.einzel button.btn-primary').first().click();
    await page.waitForTimeout(2600);
    if (!dialogText) fund('Einzelprüfung wurde ohne Rückfrage übernommen');
    else if (!/offener Befund/i.test(dialogText)) fund(`Rückfrage ohne Begründung: ${dialogText}`);
  } else {
    fund('Gruppe „Einzelprüfung" hat kein Begründungsfeld');
  }
  await shot(page, 'einzelpruefung',
             'Einzelprüfung — Sammelübernahme nur mit Bestätigung',
             'Warnhinweis „Gegen diese Komponenten steht ein offener Befund"; die '
             + 'Übernahme fragt über einen Dialog nach und wurde hier abgelehnt');

  // ── Schritt 6: Der Widerspruch im Release-Check ───────────────────────────
  await page.keyboard.press('Escape');
  await page.goto(`${BASE}/cra?projekt=${encodeURIComponent(PROJEKT)}&tab=releases`,
                  { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000);
  const feldVersion = page.locator('input[placeholder*="ersion"], input[placeholder*="1."]').first();
  if (await feldVersion.count()) {
    await feldVersion.fill('1.1.0');
    await page.waitForTimeout(500);
  }
  if (!await klick(page, 'Vorgang öffnen', 'button')) {
    fund('Knopf „Vorgang öffnen" im Releases-Tab nicht gefunden');
  }
  await page.waitForTimeout(5000);
  // Der Vorgang muss angelegt sein, sonst zeigt der Reiter nur die Vorschau-Ampel.
  if (await klick(page, 'Vorgang für .* anlegen', 'button')) await page.waitForTimeout(5000);
  // Der Prüfpunkt steht weit unten in der Liste. `fullPage` erfasst in Firefox
  // nur den Viewport (Lehre aus #1745) — also hinscrollen, dann auslösen.
  const gefunden = await page.evaluate(() => {
    const el = [...document.querySelectorAll('*')]
      .find((e) => /widerspruchsfrei zu den eigenen Befunden/.test(e.textContent || '')
                   && e.children.length === 0);
    if (!el) return false;
    el.scrollIntoView({ block: 'center' });
    return true;
  });
  if (!gefunden) fund('Katalog-Eintrag „widerspruchsfrei zu den eigenen Befunden" fehlt');
  await page.waitForTimeout(800);
  t = await text(page);
  if (!/nicht relevant/.test(t) || !/offener Befund/.test(t)) {
    fund('Der gerechnete Widerspruch erscheint nicht im Release-Check');
  }
  await shot(page, 'releasecheck',
             'Release-Check mit dem gerechneten Widerspruch',
             'Offener Punkt „1 Fremdkomponente(n) als „nicht relevant" bewertet, '
             + 'obwohl ein offener Befund gegen sie vorliegt"');

  await browser.close();

  const md = [`# Abnahme #1773/#1774 — ${TAG}`, '',
              `Projekt: ${PROJEKT}`, '',
              ...bilder.flatMap((b) => [`## ${b.titel}`, '', `![${b.titel}](${b.datei})`, '',
                                        `**Erwartung:** ${b.erwartung}`, '']),
              funde.length ? '## Funde' : '## Funde: keine', '',
              ...funde.map((f) => `- ${f}`)].join('\n');
  fs.writeFileSync(path.join(SHOTS, 'abnahme-1773.md'), md);
  console.log(`\n${bilder.length} Bilder, ${funde.length} Fund(e) → ${SHOTS}`);
  process.exit(funde.length ? 1 : 0);
}

main().catch((e) => { console.error('Setup-Fehler:', e.message); process.exit(2); });
