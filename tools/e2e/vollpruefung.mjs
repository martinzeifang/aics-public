/**
 * Vollprüfung aller Module über einen echten Firefox.
 *
 * Etappe 1 — Breite: jedes Modul, jeder Tab, jeder lesende Knopf. Ziel ist
 * nicht, dass das Skript grün wird, sondern eine Liste von Funden mit Bildern,
 * die danach von Hand angesehen werden. Ein grüner Lauf beweist, dass Elemente
 * existieren; ob die Seite benutzbar ist, zeigt erst das Bild.
 *
 * Mitgeschnitten wird, was im Alltag niemand sieht:
 *  - HTTP 4xx/5xx je Anfrage (mit Pfad), getrennt nach „erwartbar" (401/403/409
 *    bei absichtlich leeren Formularen) und „Fund"
 *  - JavaScript-Fehler in der Konsole
 *  - Tabs, die nichts rendern, und Panels, die die Projektauswahl verlieren
 *
 * Bewusst NICHT geklickt: alles mit ⚡/🤖 (ohne Modell nur Fehlalarme) und
 * Löschen außerhalb eigener Testdaten.
 *
 * ENV: AICS_BASE · AICS_EMAIL · AICS_PASSWORD · AICS_MODULE (Komma-Liste)
 * Lauf: node tools/e2e/vollpruefung.mjs
 */
import { firefox } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';

const BASE = process.env.AICS_BASE || 'https://aics-dev.290985.intern:8444';
const EMAIL = process.env.AICS_EMAIL || 'dev.admin@mustermann.example';
const PASSWORD = process.env.AICS_PASSWORD || '';
const NUR = (process.env.AICS_MODULE || '').split(',').filter(Boolean);
const OUT = new URL('./out/', import.meta.url).pathname;
const SHOTS = `${OUT}voll/`;

/** Module mit ihrer Route. Projekt-Auswahl erfolgt über die Seitenleiste. */
const MODULE = [
  ['firmen', '/firmen', true],
  ['cra', '/cra', true],
  ['nis2', '/nis2', true],
  ['aiact', '/aiact', true],
  ['dsgvo', '/dsgvo', true],
  ['wiba', '/wiba', true],
  ['risikobewertung', '/risikobewertung', true],
  ['compliance-audit', '/compliance-audit', true],
  ['gutachten', '/gutachten/gerichts', true],
  ['soc', '/soc', false],
];

/** Admin-Seiten — ohne Projektauswahl, jede für sich. */
const ADMIN = [
  '/admin', '/admin/users', '/admin/groups', '/admin/audit', '/admin/db',
  '/admin/frameworks', '/admin/wiba-catalog', '/admin/backup', '/admin/settings',
  '/admin/ollama', '/admin/license', '/admin/licensing', '/admin/issues',
  '/admin/templates', '/admin/firmen-link', '/account/security',
];

const funde = [];
const schritte = [];
const httpFehler = [];
const jsFehler = [];
let aktuell = '';
const fund = (art, text, extra = {}) => funde.push({ art, text, schritt: aktuell, ...extra });
const ok = (text) => schritte.push({ schritt: aktuell, text });

const ruhe = (page, ms = 600) => page.waitForTimeout(ms);
const inhalt = (page) => page.locator('.tab-content').first();

/** Diese Antworten sind beim blinden Durchklicken normal und kein Fund. */
const ERWARTBAR = /\/(auth\/login|ai\/run-stream|ollama|version|update)/;

async function schritt(name, fn) {
  aktuell = name;
  try { await fn(); } catch (e) { fund('ausnahme', `${name}: ${String(e.message).slice(0, 200)}`); }
}

async function aufraeumen(page) {
  // Ein stehengebliebener Dialog verdeckt die Tab-Leiste, und der naechste
  // Schritt meldet dann „Tab nicht erreichbar" — ein Fund ueber das Skript,
  // nicht ueber die Anwendung. Genau so sind im ersten Lauf 25 Fehlalarme
  // entstanden. Deshalb breit suchen und hartnaeckig schliessen.
  const SEL = '.modal-overlay:visible, .modal:visible, .wizard-modal:visible, '
            + '.wizard-modal-overlay:visible, dialog[open]:visible, '
            + '[class*="modal"]:visible, [role="dialog"]:visible';
  for (let i = 0; i < 6; i++) {
    const ov = page.locator(SEL).first();
    if (!(await ov.count())) break;
    const zu = ov.locator('button:visible').filter({
      // „OK" gehört NICHT hierher: In einem Bestätigungsdialog ist es die
      // Zustimmung, nicht das Schließen. Im Lauf vom 25.10. hat genau das
      // fünf SBOM-Einträge gelöscht — ein Prüfer, der beim Aufräumen zustimmt,
      // verändert den Gegenstand, den er prüfen soll.
      hasText: /^(Abbrechen|Schließen|Schliessen|✕|×|✖|Zurück)$/ }).first();
    if (await zu.count()) await zu.click({ timeout: 2000 }).catch(() => {});
    else await page.keyboard.press('Escape').catch(() => {});
    await ruhe(page, 300);
  }
  // Letzte Rettung: Verbleibt etwas, wird die Seite neu geladen — besser als
  // ein Lauf, der ab hier nur noch Fehlalarme produziert.
  if (await page.locator(SEL).first().count()) {
    await page.reload({ waitUntil: 'domcontentloaded' }).catch(() => {});
    await ruhe(page, 1500);
    return false;
  }
  return true;
}

/** Alle <details> aufklappen — sonst bleibt der halbe Tab ungesehen. */
async function abschnitteOeffnen(page) {
  let n = 0;
  for (let i = 0; i < 25; i++) {
    const d = inhalt(page).locator('details:not([open])').first();
    if (!(await d.count())) break;
    await d.locator('summary').first().click({ timeout: 2500 }).catch(() => {});
    await ruhe(page, 120);
    n++;
  }
  return n;
}

const KI = /⚡|🤖|KI|Ollama|Prompt|automatische Bewertung|Massenbewertung/i;
const GEFAEHRLICH = /löschen|entfernen|zurücksetzen|reopen|widerrufen|entziehen|abbrechen|delete/i;
const SCHREIBT = /speichern|anlegen|erstellen|übernehmen|einreichen|freigeben|ausstellen|archivieren|hochladen|importieren|sync|generieren|feststellen|veröffentlichen|^\\s*\\+|neue[rsn]?\\s|neues\\s|hinzufügen|issue/i;

/** Lesende Knöpfe im Panel klicken (Downloads/Dialoge werden abgefangen). */
async function lesendeKnoepfe(page, max = 14) {
  const alle = inhalt(page).locator('button:visible:not([disabled])');
  const n = Math.min(await alle.count(), 40);
  let geklickt = 0;
  for (let i = 0; i < n && geklickt < max; i++) {
    const b = alle.nth(i);
    const t = ((await b.innerText().catch(() => '')) || '').trim();
    // Ein Knopf ohne Text ist meist ein Icon (🗑️, ✏️). Ohne Beschriftung
    // greift kein Filter, also wird er nicht angefasst.
    if (!t || t.length < 3 || KI.test(t) || GEFAEHRLICH.test(t) || SCHREIBT.test(t)) continue;
    if (/🗑|❌|✖|⛔|♻/.test(t)) continue;
    await b.click({ timeout: 2500 }).catch(() => {});
    geklickt++;
    await ruhe(page, 320);
    await aufraeumen(page);
  }
  return geklickt;
}

/** Zweistufige Tab-Leiste vollständig ablaufen. */
async function alleTabs(page, modul) {
  // Die Firmenverwaltung hat ihre eigene Reiter-Leiste (`main-tab`) ohne
  // Gruppen — ohne diesen Zweig bliebe sie ungeprüft.
  const haupt = page.locator('button.main-tab:visible');
  if (await haupt.count()) {
    const n = await haupt.count();
    for (let i = 0; i < n; i++) {
      const b = page.locator('button.main-tab:visible').nth(i);
      const tab = ((await b.innerText().catch(() => '')) || '').trim();
      await b.click().catch(() => {});
      await ruhe(page, 1400);
      const text = await page.locator('main, .view, body').first().innerText().catch(() => '');
      const id = `${modul}-${String(i + 1).padStart(2, '0')}-${tab.replace(/[^\wäöüÄÖÜß]+/g, '_').slice(0, 24)}`;
      if (!text || text.trim().length < 40) fund('leer', `${modul} / „${tab}" rendert (fast) nichts`, { tab });
      await abschnitteOeffnen(page);
      const kk = await lesendeKnoepfe(page);
      await aufraeumen(page);
      await page.screenshot({ path: `${SHOTS}${id}.png`, fullPage: true }).catch(() => {});
      ok(`${modul} / ${tab}: ${kk} Knopf/Knöpfe`);
    }
    return n;
  }
  const gruppen = page.locator('button.nav-group:visible');
  const gN = await gruppen.count();
  const wege = [];
  if (gN === 0) {
    const t = page.locator('button.nav-tab:visible');
    for (let i = 0; i < await t.count(); i++) wege.push([null, ((await t.nth(i).innerText()) || '').trim()]);
  } else {
    for (let g = 0; g < gN; g++) {
      const gt = ((await gruppen.nth(g).innerText()) || '').trim().split('\n')[0];
      await gruppen.nth(g).click().catch(() => {});
      await ruhe(page, 450);
      const t = page.locator('button.nav-tab:visible');
      for (let i = 0; i < await t.count(); i++) {
        wege.push([gt, ((await t.nth(i).innerText()) || '').trim()]);
      }
    }
  }
  let i = 0;
  for (const [gruppe, tab] of wege) {
    i++;
    if (gruppe) {
      const g = page.locator('button.nav-group:visible').filter({ hasText: gruppe.slice(0, 12) }).first();
      if (await g.count()) { await g.click().catch(() => {}); await ruhe(page, 350); }
    }
    let tb = page.locator('button.nav-tab:visible').filter({ hasText: tab }).first();
    if (!(await tb.count())) {
      // Gruppe und Tab heissen manchmal gleich; dann hilft der Textvergleich
      // ueber alle sichtbaren Tabs statt eines Teilstring-Filters.
      const alle = page.locator('button.nav-tab:visible');
      for (let k = 0; k < await alle.count(); k++) {
        if (((await alle.nth(k).innerText()) || '').trim() === tab) { tb = alle.nth(k); break; }
      }
    }
    if (!(await tb.count())) { fund('tab-weg', `${modul}: Tab „${tab}" nicht mehr erreichbar`); continue; }
    await tb.click().catch(() => {});
    await ruhe(page, 1300);
    const text = await inhalt(page).innerText().catch(() => '');
    const id = `${modul}-${String(i).padStart(2, '0')}-${tab.replace(/[^\wäöüÄÖÜß]+/g, '_').slice(0, 24)}`;
    if (!text || text.trim().length < 30) fund('leer', `${modul} / „${tab}" rendert (fast) nichts`, { tab });
    if (/Wähle links ein Projekt|Bitte zuerst ein .* auswählen/i.test(text) && i > 1) {
      fund('projekt-verloren', `${modul} / „${tab}" verlangt erneut eine Projektauswahl`, { tab });
    }
    // „Fehler" steht auch in Fließtexten (OWASP-Beschreibungen). Gewertet wird
    // nur, was wie eine Meldung aussieht: im Hinweisfeld, mit Doppelpunkt, oder
    // ein durchgereichter Programmierfehler.
    const meldung = await inhalt(page).locator('.alert:visible, .alert-error:visible, [role="alert"]:visible')
      .allInnerTexts().catch(() => []);
    for (const m of meldung) {
      const t = m.replace(/\s+/g, ' ').trim();
      if (t && !/^✔|^Keine offenen/.test(t)) fund('meldung', `${modul} / „${tab}": ${t.slice(0, 180)}`, { tab });
    }
    if (/undefined|NaN(?![a-z])|\[object Object\]|Traceback|500 Internal/.test(text)) {
      const stelle = (text.match(/.{0,70}(undefined|NaN|\[object Object\]|Traceback|500 Internal).{0,70}/) || [])[0];
      fund('rohwert', `${modul} / „${tab}": ${String(stelle).replace(/\s+/g, ' ').trim()}`, { tab });
    }
    const auf = await abschnitteOeffnen(page);
    const kk = await lesendeKnoepfe(page);
    await aufraeumen(page);
    await page.screenshot({ path: `${SHOTS}${id}.png`, fullPage: true }).catch(() => {});
    ok(`${modul} / ${tab}: ${auf} Abschnitt(e), ${kk} Knopf/Knöpfe`);
  }
  return wege.length;
}

(async () => {
  if (!PASSWORD) { console.error('AICS_PASSWORD fehlt'); process.exit(2); }
  mkdirSync(SHOTS, { recursive: true });
  const browser = await firefox.launch({ headless: true });
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1680, height: 1150 } });
  const page = await ctx.newPage();

  page.on('response', (r) => {
    const s = r.status(), u = r.url();
    if (s >= 400 && !ERWARTBAR.test(u)) {
      httpFehler.push({ status: s, url: u.replace(BASE, ''), schritt: aktuell });
    }
  });
  page.on('pageerror', (e) => jsFehler.push({ text: String(e.message).slice(0, 200), schritt: aktuell }));
  page.on('console', (m) => {
    if (m.type() === 'error') {
      const t = m.text();
      if (!/favicon|Download the Vue|sourcemap/i.test(t)) jsFehler.push({ text: t.slice(0, 200), schritt: aktuell });
    }
  });

  await schritt('login', async () => {
    await page.goto(BASE, { waitUntil: 'domcontentloaded' });
    await page.locator('input[type="email"], input#email').first().fill(EMAIL);
    await page.locator('input[type="password"]').first().fill(PASSWORD);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForURL((u) => !String(u).includes('/login'), { timeout: 25000 });
    await ruhe(page, 1500);
    await page.screenshot({ path: `${SHOTS}00-start.png`, fullPage: true }).catch(() => {});
    ok('angemeldet');
  });
  if (funde.length) { console.error('Login fehlgeschlagen'); await browser.close(); process.exit(2); }

  for (const [modul, route, mitProjekt] of MODULE) {
    if (NUR.length && !NUR.includes(modul)) continue;
    await schritt(`modul:${modul}`, async () => {
      await page.goto(`${BASE}${route}`, { waitUntil: 'domcontentloaded' });
      await ruhe(page, 2200);
      if (mitProjekt) {
        // Die Einträge der Seitenleiste sind keine <button>/<li>, sondern divs
        // mit Klick-Handler — über den Text ansteuern. 📦 ist das Produkt,
        // 🏢 die Firma: Ein Klick auf die Firma öffnet die Firmensicht, nicht
        // das Modul-Projekt.
        let gewaehlt = false;
        for (const marke of ['📦', '🤖', '📋']) {
          const ziel = page.locator('aside').getByText(marke, { exact: false }).first();
          if (await ziel.count()) {
            await ziel.click({ timeout: 4000 }).catch(() => {});
            await ruhe(page, 2300);
            gewaehlt = true;
            break;
          }
        }
        if (!gewaehlt) {
          // Module ohne Produktebene (Gutachten, Compliance-Audit): erster Eintrag
          const erster = page.locator('aside [class*="item"]:visible, aside [class*="projekt"]:visible, aside [role="button"]:visible').first();
          if (await erster.count()) { await erster.click().catch(() => {}); await ruhe(page, 2300); }
        }
        for (let v = 0; v < 3; v++) {
          if (await page.locator('button.nav-tab:visible, button.main-tab:visible').count()) break;
          await ruhe(page, 1800);
        }
        if (!(await page.locator('button.nav-tab:visible, button.main-tab:visible').count())) {
          const t = await page.locator('aside').first().innerText().catch(() => '');
          // „Keine Projekte" ist eine Aussage über die Daten, kein Defekt.
          if (/Keine .*(Projekte|Audits|Gutachten|Bewertungen)/i.test(t)) {
            fund('ohne-daten', `${modul}: Seitenleiste meldet „${t.replace(/\s+/g, ' ').slice(0, 60)}"`);
          } else {
            fund('keine-tabs', `${modul}: nach der Projektauswahl erscheint keine Tab-Leiste`);
          }
        }
      }
      const t0 = await page.locator('body').innerText().catch(() => '');
      if (/Modul nicht lizenziert|keine Berechtigung|403/i.test(t0)) {
        fund('gesperrt', `${modul}: Modul meldet fehlende Lizenz/Berechtigung`);
        return;
      }
      const n = await alleTabs(page, modul);
      ok(`${modul}: ${n} Tab(s) geprüft`);
    });
  }

  for (const route of ADMIN) {
    if (NUR.length && !NUR.includes('admin')) continue;
    await schritt(`admin:${route}`, async () => {
      await page.goto(`${BASE}${route}`, { waitUntil: 'domcontentloaded' });
      await ruhe(page, 1800);
      const text = await page.locator('body').innerText().catch(() => '');
      if (!text || text.trim().length < 60) fund('leer', `Admin ${route} rendert (fast) nichts`);
      if (/Fehler|fehlgeschlagen|undefined|NaN|\[object Object\]/.test(text)) {
        const stelle = (text.match(/.{0,70}(Fehler|fehlgeschlagen|undefined|NaN|\[object Object\]).{0,70}/) || [])[0];
        fund('fehlertext', `Admin ${route}: ${String(stelle).replace(/\s+/g, ' ').trim()}`);
      }
      await abschnitteOeffnen(page);
      await page.screenshot({ path: `${SHOTS}admin${route.replace(/\//g, '_')}.png`, fullPage: true }).catch(() => {});
      ok(`Admin ${route}`);
    });
  }

  // HTTP-/JS-Fehler verdichten: gleiche Meldung zehnmal ist ein Fund, nicht zehn.
  const gruppiert = (liste, schlu) => {
    const m = new Map();
    for (const e of liste) {
      const k = schlu(e);
      if (!m.has(k)) m.set(k, { ...e, anzahl: 0, schritte: new Set() });
      const g = m.get(k); g.anzahl++; g.schritte.add(e.schritt);
    }
    return [...m.values()].map((g) => ({ ...g, schritte: [...g.schritte].slice(0, 6) }));
  };
  const http = gruppiert(httpFehler, (e) => `${e.status} ${e.url.split('?')[0]}`);
  const js = gruppiert(jsFehler, (e) => e.text.slice(0, 90));

  writeFileSync(`${OUT}vollpruefung.json`, JSON.stringify(
    { base: BASE, konto: EMAIL, funde, schritte, http, js }, null, 2));

  console.log(`\n== ${schritte.length} Schritte, ${funde.length} Funde ==`);
  for (const f of funde) console.log(`  [${f.art}] ${f.text}`);
  console.log(`\n== HTTP-Fehler (${http.length} verschiedene) ==`);
  for (const h of http) console.log(`  ${h.status} ${h.url}  ×${h.anzahl}  (${h.schritte.join(', ')})`);
  console.log(`\n== JS-Fehler (${js.length} verschiedene) ==`);
  for (const j of js) console.log(`  ${j.text}  ×${j.anzahl}  (${j.schritte.join(', ')})`);
  console.log(`\nBilder: ${SHOTS}`);
  await browser.close();
  process.exit(0);
})();
