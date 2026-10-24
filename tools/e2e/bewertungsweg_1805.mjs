/**
 * Die Strecke aus dem Betriebsbefund, über einen echten Firefox (#1805).
 *
 * Geprüft wird genau das, was gemeldet wurde:
 *
 *  1. Im Tab „✅ Konformität" gibt es den Haken — mit **der** Beschriftung, die
 *     die Fehlermeldung nennt. („Ich finde es nicht" kam daher, dass die
 *     Meldung „Bewertung abgeschlossen" sagte und das Formular
 *     „Bewertungsweg abgeschlossen".)
 *  2. Der Knopf „→ Im Release-Vorgang erfassen" **tut etwas**: Er wechselt in
 *     den Releases-Tab. Vorher fehlte der `@goto`-Zuhörer, und er tat nichts.
 *  3. Der am Produkt gesetzte Haken wirkt auf den Release-Vorgang: Die
 *     Hindernis-Liste nennt den Bewertungsweg nicht mehr, „Zur Prüfung geben"
 *     ist nicht gesperrt, und der Vorgang weist die Herkunft aus.
 *
 * **Bewusst lesend am echten Vorgang.** Der Lauf richtet sich gegen die
 * Testinstanz und darf deren Daten nicht verändern: Geprüft wird, dass der
 * Knopf *freigeschaltet* ist — nicht, was ein Klick auslöst. Eingereicht wird
 * nur in einem eigens angelegten Vorgang mit einer Version, die es sonst nicht
 * gibt (`E2E_VERSION`), damit ein zweiter Lauf nicht auf den ersten trifft.
 *
 * ENV: AICS_BASE · AICS_EMAIL · AICS_PASSWORD · AICS_PROJEKT · AICS_HEADED=1
 * Lauf:  node tools/e2e/bewertungsweg_1805.mjs
 * Exit:  0 sauber · 1 Funde · 2 Setup-Fehler
 */
import { firefox } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';

const BASE = process.env.AICS_BASE || 'https://localhost:5173';
const EMAIL = process.env.AICS_EMAIL || 'admin@example.com';
const PASSWORD = process.env.AICS_PASSWORD || 'admin-password';
const PROJEKT = process.env.AICS_PROJEKT || 'AI Compliance Suite';
const HEADED = process.env.AICS_HEADED === '1';
const E2E_VERSION = `0.0.0-e2e-${String(Date.now()).slice(-6)}`;
const OUT = new URL('./out/', import.meta.url).pathname;
const SHOTS = `${OUT}bewertungsweg/`;

const funde = [];
const schritte = [];
const fund = (art, text) => funde.push({ art, text, schritt: aktuell });
const ok = (text) => schritte.push({ schritt: aktuell, text });
let aktuell = '';

const ruhe = (page, ms = 700) => page.waitForTimeout(ms);
const inhalt = (page) => page.locator('.tab-content').first();

async function schritt(name, fn) {
  aktuell = name;
  try {
    await fn();
  } catch (e) {
    fund('ausnahme', `${name}: ${e.message}`);
  }
}

/** Tab über die zweistufige Leiste (Gruppe → Untertab). */
async function tabOeffnen(page, gruppe, tab) {
  const g = page.locator('button.nav-group:visible').filter({ hasText: gruppe }).first();
  if (await g.count()) { await g.click().catch(() => {}); await ruhe(page, 400); }
  const t = page.locator('button.nav-tab:visible').filter({ hasText: tab }).first();
  if (!(await t.count())) { fund('fehlt', `Tab „${tab}" nicht erreichbar`); return false; }
  await t.click();
  await ruhe(page, 1500);
  return true;
}

/** Welcher Untertab ist aktiv? Für den Nachweis, dass der Knopf gewechselt hat. */
async function aktiverTab(page) {
  const a = page.locator('button.nav-tab.active:visible, button.nav-tab[aria-selected="true"]:visible').first();
  return (await a.count()) ? (await a.innerText()).trim() : '';
}

(async () => {
  mkdirSync(SHOTS, { recursive: true });
  const browser = await firefox.launch({ headless: !HEADED });
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1600, height: 1100 } });
  const page = await ctx.newPage();

  const tracebacks = [];
  page.on('response', async (r) => {
    if (r.status() >= 500) tracebacks.push(`${r.status()} ${r.url()}`);
  });

  await schritt('login', async () => {
    await page.goto(BASE, { waitUntil: 'domcontentloaded' });
    await page.locator('input[type="email"], input#email').first().fill(EMAIL);
    await page.locator('input[type="password"]').first().fill(PASSWORD);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForURL((u) => !String(u).includes('/login'), { timeout: 25000 });
    ok('angemeldet');
  });
  if (funde.length) return abbruch(browser, 2);

  await schritt('projekt', async () => {
    await page.goto(`${BASE}/cra`, { waitUntil: 'domcontentloaded' });
    await ruhe(page, 2000);
    const ziel = page.locator('aside').getByText(PROJEKT, { exact: false }).last();
    if (!(await ziel.count())) { fund('setup', `Projekt „${PROJEKT}" nicht in der Seitenleiste`); return; }
    await ziel.click();
    await ruhe(page, 2500);
    ok(`Projekt „${PROJEKT}" geöffnet`);
  });
  if (funde.length) return abbruch(browser, 2);

  // ── 1 · Der Haken ist da und heißt, wie die Meldung sagt ──────────────────
  await schritt('haken-vorhanden', async () => {
    if (!(await tabOeffnen(page, '✅ Konformität', '✅ Konformität'))
        && !(await tabOeffnen(page, 'Konformität', 'Konformität'))) return;
    const text = await inhalt(page).innerText();
    if (!/Bewertungsweg abgeschlossen/.test(text)) {
      fund('fehlt', 'Der Haken „Bewertungsweg abgeschlossen" ist im Tab nicht zu finden');
      return;
    }
    if (!/Gilt für das Produkt/i.test(text)) {
      fund('unklar', 'Es steht nicht dabei, dass der Haken für das Produkt gilt');
    }
    await page.screenshot({ path: `${SHOTS}1-konformitaet.png`, fullPage: true }).catch(() => {});
    ok('Haken samt Geltungs-Hinweis gefunden');
  });

  // ── 2 · Der gemeldete Knopf tut etwas ─────────────────────────────────────
  await schritt('knopf-im-release-vorgang-erfassen', async () => {
    const b = inhalt(page).locator('button:visible').filter({ hasText: /Im Release-Vorgang erfassen/ }).first();
    if (!(await b.count())) { fund('fehlt', 'Knopf „→ Im Release-Vorgang erfassen" nicht gefunden'); return; }
    const vorher = await aktiverTab(page);
    await b.click();
    await ruhe(page, 1800);
    const nachher = await aktiverTab(page);
    const text = await inhalt(page).innerText().catch(() => '');
    if (!/Release-Vorgänge|🚦 Releases/.test(text)) {
      fund('ohne-wirkung',
           `Der Knopf wechselt nicht in den Releases-Tab (aktiv vorher „${vorher}", nachher „${nachher}") `
           + '— genau der gemeldete Defekt');
      return;
    }
    await page.screenshot({ path: `${SHOTS}2-nach-klick.png`, fullPage: true }).catch(() => {});
    ok(`Knopf wechselt in den Releases-Tab (aktiv: „${nachher}")`);
  });

  // ── 3 · Der Produkt-Haken wirkt auf den Release-Vorgang ───────────────────
  await schritt('release-erbt-den-haken', async () => {
    if (!/Release-Vorgänge/.test(await inhalt(page).innerText().catch(() => ''))) {
      if (!(await tabOeffnen(page, '🚦 Releases', '🚦 Releases'))
          && !(await tabOeffnen(page, 'Releases', 'Releases'))) return;
    }
    // Eigener Vorgang: Der Lauf darf die echten Release-Vorgänge nicht anfassen.
    const feld = inhalt(page).locator('input[placeholder*="1.2.0" i], input[list="rel-versions"]').first();
    if (!(await feld.count())) { fund('fehlt', 'Versions-Eingabe im Releases-Tab nicht gefunden'); return; }
    await feld.fill(E2E_VERSION);
    const oeffnen = inhalt(page).locator('button:visible').filter({ hasText: /Vorgang öffnen/ }).first();
    if (!(await oeffnen.count())) { fund('fehlt', 'Knopf „Vorgang öffnen" nicht gefunden'); return; }
    await oeffnen.click();
    await ruhe(page, 1800);

    const anlegen = inhalt(page).locator('button:visible').filter({ hasText: /Vorgang für .* anlegen/ }).first();
    if (await anlegen.count()) { await anlegen.click(); await ruhe(page, 2000); }

    const text = await inhalt(page).innerText().catch(() => '');
    if (/nicht als abgeschlossen vermerkt/.test(text)) {
      fund('erbt-nicht',
           'Der Vorgang meldet weiter „Bewertungsweg nicht als abgeschlossen vermerkt", '
           + 'obwohl der Haken am Produkt gesetzt ist — der Kern des Befundes');
    }
    if (!/Aus der Produktbewertung übernommen/.test(text)) {
      fund('unklar', 'Der Vorgang weist die Herkunft des Stands nicht aus');
    }
    const einreichen = inhalt(page).locator('button:visible').filter({ hasText: /Zur Prüfung geben/ }).first();
    if (!(await einreichen.count())) {
      fund('fehlt', 'Knopf „Zur Prüfung geben" nicht vorhanden');
    } else if (await einreichen.isDisabled().catch(() => false)) {
      fund('gesperrt', '„Zur Prüfung geben" ist gesperrt, obwohl der Bewertungsweg abgeschlossen ist');
    }
    await page.screenshot({ path: `${SHOTS}3-vorgang.png`, fullPage: true }).catch(() => {});
    ok(`Vorgang ${E2E_VERSION} geprüft`);
  });

  // ── 4 · Einreichen wirklich durchführen (im eigenen Vorgang) ──────────────
  await schritt('einreichen-geht-durch', async () => {
    const b = inhalt(page).locator('button:visible').filter({ hasText: /Zur Prüfung geben/ }).first();
    if (!(await b.count()) || await b.isDisabled().catch(() => false)) {
      fund('gesperrt', 'Einreichen nicht möglich — siehe vorigen Schritt');
      return;
    }
    await b.click();
    await ruhe(page, 2200);
    const text = await inhalt(page).innerText().catch(() => '');
    if (/nicht als abgeschlossen vermerkt|Bewertungsweg/.test(text) && /⚠|Fehler/.test(text)) {
      fund('serverseitig', `Das Einreichen wurde abgelehnt: ${text.slice(0, 300)}`);
      return;
    }
    if (!/In Prüfung|in_pruefung|zur Prüfung/i.test(text)) {
      fund('unklar', 'Nach dem Einreichen ist der Zustand „In Prüfung" nicht zu sehen');
    }
    await page.screenshot({ path: `${SHOTS}4-eingereicht.png`, fullPage: true }).catch(() => {});
    ok('Vorgang eingereicht — die Strecke ist durchgängig');
  });

  if (tracebacks.length) fund('http500', `Serverfehler: ${tracebacks.join(' · ')}`);

  writeFileSync(`${OUT}bewertungsweg-1805.json`,
                JSON.stringify({ base: BASE, projekt: PROJEKT, version: E2E_VERSION,
                                 funde, schritte, tracebacks }, null, 2));
  console.log(`\nSchritte:\n${schritte.map((s) => `  ✔ ${s.schritt}: ${s.text}`).join('\n')}`);
  console.log(funde.length
    ? `\nFUNDE (${funde.length}):\n${funde.map((f) => `  ✖ [${f.art}] ${f.schritt}: ${f.text}`).join('\n')}`
    : '\nKeine Funde.');
  console.log(`\nBilder: ${SHOTS}`);
  await browser.close();
  process.exit(funde.length ? 1 : 0);
})();

async function abbruch(browser, code) {
  console.error(funde.map((f) => `[${f.art}] ${f.schritt}: ${f.text}`).join('\n'));
  await browser.close();
  process.exit(code);
}
