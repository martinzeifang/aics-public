/**
 * Tabs und Screenshots in einem Durchgang — direkt aus der laufenden Suite.
 *
 * Ersetzt die handgepflegte `tabs.mjs`: Eine Liste, die jemand nachträgt,
 * veraltet zwangsläufig — das Wiki stand zuletzt auf dem Stand von Juni 2026,
 * während die Anwendung bei v8.0.11 war und zwei Module dazubekommen hatte.
 * Hier wird gelesen, was wirklich da ist.
 *
 * Erzeugt:
 *   shots2/<modul>__<tabId>.png   — ein Bild je Tab
 *   shots/<modul>.png             — Landing je Modul
 *   tabs.generiert.json           — Modul → [[id, Label]], Quelle für gen.mts
 *
 * ENV: AICS_BASE · AICS_EMAIL · AICS_PASSWORD
 */
import { firefox } from 'playwright';
import { mkdirSync, writeFileSync, readFileSync } from 'node:fs';

const BASE = process.env.AICS_BASE || 'https://aics-demo.290985.intern:8445';
const EMAIL = process.env.AICS_EMAIL || '';
const PASSWORD = process.env.AICS_PASSWORD || '';
const HIER = new URL('./', import.meta.url).pathname;

/** Modul → Route. `mitProjekt` steuert, ob links erst etwas gewählt werden muss. */
const NUR = (process.env.AICS_MODULE || '').split(',').filter(Boolean);
const MODULE = [
  ['cra', '/cra', true],
  ['nis2', '/nis2', true],
  ['aiact', '/aiact', true],
  ['dsgvo', '/dsgvo', true],
  ['wiba', '/wiba', true],
  ['risikobewertung', '/risikobewertung', true],
  ['compliance-audit', '/compliance-audit', true],
  ['firmen', '/firmen', true],
  ['soc', '/soc', false],
];

const ruhe = (p, ms = 700) => p.waitForTimeout(ms);

/** Drei Tab-Varianten im Haus: GroupedModuleNav (`nav-tab`), TabBar
 *  (`tab-btn`, z. B. Risikobewertung und Compliance-Audit) und die eigene
 *  Leiste der Firmenverwaltung (`main-tab`). */
const TABS_SEL = 'button.nav-tab:visible, button.main-tab:visible, button.tab-btn:visible';

/** Offene Dialoge schließen — aber niemals „OK" drücken: in einem
 *  Bestätigungsdialog ist das die Zustimmung, nicht das Schließen. */
async function aufraeumen(page) {
  const SEL = '.modal-overlay:visible, .wizard-modal-overlay:visible, '
            + '[class*="modal"]:visible, [role="dialog"]:visible';
  for (let i = 0; i < 5; i++) {
    const ov = page.locator(SEL).first();
    if (!(await ov.count())) return;
    const zu = ov.locator('button:visible')
      .filter({ hasText: /^(Abbrechen|Schließen|Schliessen|✕|×|Zurück)$/ }).first();
    if (await zu.count()) await zu.click({ timeout: 1500 }).catch(() => {});
    else await page.keyboard.press('Escape').catch(() => {});
    await ruhe(page, 250);
  }
}

/** Projekt in der Seitenleiste wählen (📦 Produkt vor 🏢 Firma). */
async function projektWaehlen(page) {
  // Zuerst die Firmengruppen aufklappen. Mehrere Leisten gruppieren nach
  // Firma (🏢); ein Klick darauf öffnet die Firmenübersicht statt eines
  // Projekts, und der Lauf steht danach auf „Projekt wählen" — genau so sind
  // WiBA und SOC einmal leer erfasst worden.
  const firmen = page.locator('aside .proj-name, aside .firma-name');
  const nf = await firmen.count();
  for (let i = 0; i < nf; i++) {
    const t = ((await firmen.nth(i).textContent()) || '').trim();
    if (t.startsWith('🏢')) await firmen.nth(i).click({ timeout: 3000 }).catch(() => {});
  }
  if (nf) await ruhe(page, 900);

  for (const marke of ['📦', '🤖', '📋']) {
    const z = page.locator('aside').getByText(marke, { exact: false }).first();
    if (await z.count()) { await z.click({ timeout: 4000 }).catch(() => {}); await ruhe(page, 2200); return true; }
  }
  // Ein Eintrag, der keine Firma und keine Sammelzeile ist.
  const kandidaten = page.locator('aside .proj-name:visible');
  for (let i = 0; i < await kandidaten.count(); i++) {
    const t = ((await kandidaten.nth(i).textContent()) || '').trim();
    if (t.startsWith('🏢') || t.startsWith('—')) continue;
    await kandidaten.nth(i).click({ timeout: 4000 }).catch(() => {});
    await ruhe(page, 2200);
    return true;
  }
  // Letzter Ausweg: ein Projektwechsler im Kopf (WiBA).
  const wechsler = page.locator('select.proj-switch');
  if (await wechsler.count()) {
    const werte = await wechsler.locator('option').count();
    if (werte) { await wechsler.selectOption({ index: 0 }).catch(() => {}); await ruhe(page, 2200); return true; }
  }
  const erster = page.locator('aside [class*="item"]:visible, aside li:visible').first();
  if (await erster.count()) { await erster.click().catch(() => {}); await ruhe(page, 2200); return true; }
  return false;
}

/** Tab-ID aus dem Label ableiten, wenn das DOM keine hergibt. */
const alsId = (label) => label
  .replace(/[^\p{L}\p{N}\s-]/gu, '').trim().toLowerCase()
  .replace(/[\s-]+/g, '-').replace(/^-|-$/g, '');

(async () => {
  if (!PASSWORD) { console.error('AICS_PASSWORD fehlt'); process.exit(2); }
  mkdirSync(`${HIER}shots`, { recursive: true });
  mkdirSync(`${HIER}shots2`, { recursive: true });

  const browser = await firefox.launch({ headless: true });
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1680, height: 1100 } });
  const page = await ctx.newPage();

  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.locator('input[type="email"], input#email').first().fill(EMAIL);
  await page.locator('input[type="password"]').first().fill(PASSWORD);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL((u) => !String(u).includes('/login'), { timeout: 25000 });
  await ruhe(page, 1800);
  await page.screenshot({ path: `${HIER}shots/home.png`, fullPage: false });
  console.log('angemeldet');

  const ergebnis = {};
  for (const [modul, route, mitProjekt] of MODULE) {
    if (NUR.length && !NUR.includes(modul)) continue;
    await page.goto(`${BASE}${route}`, { waitUntil: 'domcontentloaded' });
    await ruhe(page, 2200);
    if (mitProjekt) await projektWaehlen(page);
    for (let v = 0; v < 3; v++) {
      if (await page.locator(TABS_SEL).count()) break;
      await ruhe(page, 1600);
    }
    await page.screenshot({ path: `${HIER}shots/${modul}.png`, fullPage: false }).catch(() => {});

    // Wege sammeln: Gruppe → Tabs (zweistufig) oder flache Reiter.
    const wege = [];
    const gruppen = page.locator('button.nav-group:visible');
    const gN = await gruppen.count();
    if (gN) {
      for (let g = 0; g < gN; g++) {
        const gt = ((await gruppen.nth(g).innerText()) || '').trim().split('\n')[0];
        await gruppen.nth(g).click().catch(() => {});
        await ruhe(page, 450);
        const t = page.locator('button.nav-tab:visible');
        for (let i = 0; i < await t.count(); i++) {
          wege.push([gt, ((await t.nth(i).innerText()) || '').trim()]);
        }
      }
    } else {
      const t = page.locator(TABS_SEL);
      for (let i = 0; i < await t.count(); i++) wege.push([null, ((await t.nth(i).innerText()) || '').trim()]);
    }

    const tabs = [];
    for (const [gruppe, label] of wege) {
      if (!label) continue;
      if (gruppe) {
        const g = page.locator('button.nav-group:visible').filter({ hasText: gruppe.slice(0, 12) }).first();
        if (await g.count()) { await g.click().catch(() => {}); await ruhe(page, 350); }
      }
      let b = page.locator(TABS_SEL).filter({ hasText: label }).first();
      if (!(await b.count())) {
        const alle = page.locator(TABS_SEL);
        for (let k = 0; k < await alle.count(); k++) {
          if (((await alle.nth(k).innerText()) || '').trim() === label) { b = alle.nth(k); break; }
        }
      }
      if (!(await b.count())) { console.log(`  ! ${modul}: „${label}" nicht erreichbar`); continue; }
      await b.click().catch(() => {});
      await ruhe(page, 1500);
      await aufraeumen(page);
      const id = alsId(label);
      await page.screenshot({ path: `${HIER}shots2/${modul}__${id}.png`, fullPage: false }).catch(() => {});
      tabs.push([id, label, gruppe]);
    }
    ergebnis[modul] = tabs;
    console.log(`${modul}: ${tabs.length} Tab(s)`);
  }

  let bisher = {};
  try { bisher = JSON.parse(readFileSync(`${HIER}tabs.generiert.json`, 'utf8')); } catch { /* erste Erfassung */ }

  // Eine **leere** Erfassung überschreibt nichts.
  //
  // Findet der Lauf in einem Modul keinen Tab — weil die Projektauswahl nicht
  // greift, das Modul auf dieser Instanz nicht lizenziert ist oder die Seite
  // langsamer lädt —, stand hier bisher `ergebnis[modul] = []`, und der Spread
  // ersetzte die gute Liste durch die leere. Im Wiki hätte das die Seiten des
  // Moduls gelöscht: WiBA 7, SOC 16. Ein Erfassungslauf, der etwas **nicht**
  // sieht, darf nicht so wirken, als gäbe es das nicht.
  const zusammen = { ...bisher };
  const verworfen = [];
  for (const [modul, tabs] of Object.entries(ergebnis)) {
    if (tabs.length) { zusammen[modul] = tabs; continue; }
    if ((bisher[modul] || []).length) { verworfen.push(modul); continue; }
    zusammen[modul] = tabs;   // noch nie erfasst → leer ist die Wahrheit
  }
  writeFileSync(`${HIER}tabs.generiert.json`, JSON.stringify(zusammen, null, 1));
  console.log('\ntabs.generiert.json geschrieben');
  if (verworfen.length) {
    console.log(`  ! nichts erfasst, Bestand behalten: ${verworfen.join(', ')}`);
    console.log('    (Prüfen: Projektauswahl, Lizenz, Ladezeit — die Seiten im');
    console.log('     Wiki bleiben auf dem vorigen Stand.)');
  }
  await browser.close();
})();
