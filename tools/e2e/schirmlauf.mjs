/**
 * Bildschirm für Bildschirm: jedes Modul, jeder Reiter, ein Screenshot.
 *
 * WOZU, NEBEN DEN ANDEREN LÄUFEN
 * `module_funktionstest` klickt Handlungen und prüft Zusagen;
 * `escape_und_tabellen` misst zwei Eigenschaften. Beide sagen nichts darüber,
 * ob ein Bildschirm **aussieht wie gewollt**. Das ist der Gegenstand hier:
 * Jeder Reiter wird geöffnet, abgelichtet und sein sichtbarer Text geprüft.
 *
 * WAS DIE TEXTPRÜFUNG FINDET, WAS EIN AUGE ÜBERSIEHT
 * Vier Muster, alle aus den Fehlerklassen dieses Sprints:
 *
 * * **Durchgereichte i18n-Schlüssel** (`geteilt.moduleDashboard.x`). Bei
 *   abgeschaltetem `strictTemplates` (#1858) zeigt ein Schlüssel ohne
 *   Nachricht **sich selbst** — in der Oberfläche, ohne dass etwas
 *   fehlschlägt (#1964).
 * * **`undefined` / `NaN` / `[object Object]`** — ein Feld, das der Server
 *   nicht mehr liefert, wird im Browser still dazu (#1830/#1858).
 * * **Rohes Markdown** (`**fett**`) — Modelltext gehört durch `ProsaText`
 *   (#1783).
 * * **Platzhalter** (`{v0}`) — eine Nachricht, deren Werte nicht ankommen.
 *
 * Dazu jede sichtbare Fehlermeldung der Maske und jede 5xx-Antwort.
 *
 * WAS NICHT PASSIERT
 * Nur Lesen: Reiter öffnen, ablichten, Text prüfen. Kein Klick auf eine
 * Handlung mit Nebenwirkung.
 *
 * ENV: AICS_BASE · AICS_EMAIL · AICS_PASSWORD · AICS_LOCALE · AICS_BREITE
 * Lauf: node tools/e2e/schirmlauf.mjs
 */
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { firefox } from 'playwright';

const BASE = process.env.AICS_BASE || 'https://aics-dev.290985.intern:8444';
const SPRACHE = process.env.AICS_LOCALE || 'de-DE';
const BREITE = Number(process.env.AICS_BREITE || 1500);
const OUT = new URL('./out/', import.meta.url).pathname;
const SHOTS = `${OUT}schirmlauf/`;

const MODULE = [
  { pfad: '/firmen', name: 'firmen' },
  { pfad: '/risikobewertung', name: 'rb' },
  { pfad: '/cra', name: 'cra' },
  { pfad: '/wiba', name: 'wiba' },
  { pfad: '/nis2', name: 'nis2' },
  { pfad: '/aiact', name: 'aiact' },
  { pfad: '/dsgvo', name: 'dsgvo' },
  { pfad: '/compliance-audit', name: 'audit' },
  { pfad: '/gutachten/gerichts', name: 'gutachten' },
  { pfad: '/admin', name: 'admin' },
];

//: Was im sichtbaren Text eines Bildschirms nichts zu suchen hat.
const VERDACHT = [
  // Ein i18n-Schlüssel, der als Text dasteht: `gruppe.datei.name`.
  { muster: /\b(geteilt|ansichten|common|cra|dsgvo|nis2|aiact|wiba|firmen|admin|sidebars|aktionen|fehler)\.[a-z][A-Za-z0-9]*\.[A-Za-z0-9]{3,}/g,
    was: 'i18n-Schlüssel sichtbar' },
  { muster: /\bundefined\b|\bNaN\b|\[object Object\]/g, was: 'undefined/NaN/Object' },
  { muster: /\*\*[^*\n]{3,40}\*\*/g, was: 'rohes Markdown' },
  { muster: /\{v[0-9]\}/g, was: 'Platzhalter nicht ersetzt' },
];

const funde = [];
const bilder = [];
let aktuell = '-';
const fund = (was, text) => {
  funde.push({ ort: aktuell, was, text });
  console.log(`  ✘ [${aktuell}] ${was}: ${text}`);
};

function zugang() {
  if (process.env.AICS_EMAIL && process.env.AICS_PASSWORD) {
    return { email: process.env.AICS_EMAIL, pw: process.env.AICS_PASSWORD };
  }
  const datei = `${process.env.HOME}/Downloads/aics-dev-zugangsdaten.md`;
  for (const z of readFileSync(datei, 'utf-8').split('\n')) {
    const t = z.match(/^\|\s*`(dev\.admin@[^`]+)`\s*\|\s*`([^`]+)`\s*\|/);
    if (t) return { email: t[1], pw: t[2] };
  }
  throw new Error('Kein Admin-Zugang gefunden');
}

const warte = (ms) => new Promise((r) => setTimeout(r, ms));

async function ablichten(page, name) {
  const datei = `${SHOTS}${name}.png`;
  try { await page.screenshot({ path: datei }); bilder.push(name); } catch { /* egal */ }
  return datei;
}

/** Sichtbarer Text ohne Navigation — die Leiste wiederholt sich auf jedem Schirm. */
async function schirmtext(page) {
  // Ist die Seite weg (Zeitlimit, Absturz), ist das **kein** Fund — der Lauf
  // sagt es und endet sauber, statt mit einer Ausnahme zu sterben.
  if (page.isClosed()) return '';
  return page.evaluate(() => {
    const w = document.querySelector('main, .content, .modul-inhalt') || document.body;
    return (w.innerText || '').slice(0, 20000);
  });
}

async function pruefe(page, name) {
  const text = await schirmtext(page);
  for (const { muster, was } of VERDACHT) {
    const t = [...new Set((text.match(muster) || []))].slice(0, 4);
    if (t.length) fund(was, t.join(' · '));
  }
  // Sichtbare Fehlermeldungen der Maske (FehlerHinweis, #1781).
  if (page.isClosed()) return 0;
  const meldungen = await page.$$eval('.alert-error, .err, [role=alert]', (els) => els
    .filter((e) => e.getClientRects().length > 0)
    .map((e) => (e.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 120))
    .filter(Boolean));
  for (const m of [...new Set(meldungen)]) fund('Fehlermeldung sichtbar', m);
  return text.length;
}

(async () => {
  mkdirSync(SHOTS, { recursive: true });
  const { email, pw } = zugang();
  const browser = await firefox.launch({ headless: !process.env.AICS_HEADED });
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true, locale: SPRACHE,
                                         viewport: { width: BREITE, height: 1000 } });
  const page = await ctx.newPage();
  const konsole = [];
  const serverfehler = [];
  page.on('console', (m) => { if (m.type() === 'error') konsole.push(m.text()); });
  page.on('response', (r) => { if (r.status() >= 500) serverfehler.push(`${r.status()} ${r.url()}`); });

  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
  await ablichten(page, '00-login');
  await page.fill('input[type="email"], input[name="email"]', email);
  await page.fill('input[type="password"]', pw);
  await page.click('button[type="submit"]');
  await page.waitForLoadState('networkidle').catch(() => {});
  await warte(1200);

  let schirme = 0;
  for (const m of MODULE) {
    aktuell = m.pfad;
    console.log(`\n── ${m.pfad}`);
    await page.goto(`${BASE}${m.pfad}`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle').catch(() => {});
    await warte(900);
    await ablichten(page, `${m.name}-00-start`);
    await pruefe(page, `${m.name}-start`);
    schirme += 1;

    // Projekt/Mandant wählen: erst 🏢, dann 📦; sonst der erste Listeneintrag.
    const firma = page.locator('aside >> text=🏢').first();
    if (await firma.count()) { await firma.click().catch(() => {}); await warte(600); }
    const produkt = page.locator('aside >> text=📦').first();
    if (await produkt.count()) {
      await produkt.click().catch(() => {});
    } else {
      const liste = page.locator('aside .sidebar-list > *');
      const n = Math.min(await liste.count(), 20);
      for (let i = 0; i < n; i++) {
        const t = ((await liste.nth(i).innerText().catch(() => '')) || '').trim();
        if (t.length < 4) continue;
        await liste.nth(i).click().catch(() => {});
        break;
      }
    }
    await page.waitForLoadState('networkidle').catch(() => {});
    await warte(1200);

    // Reitergruppen (falls vorhanden) × Reiter
    const gruppen = page.locator('button.nav-group:visible');
    const gz = await gruppen.count();
    const wege = gz ? [...Array(gz).keys()] : [null];
    for (const gi of wege) {
      let gname = '';
      if (gi !== null) {
        gname = ((await gruppen.nth(gi).innerText().catch(() => '')) || '')
          .replace(/\s+/g, ' ').trim().slice(0, 18);
        await gruppen.nth(gi).click().catch(() => {});
        await warte(500);
      }
      // **Nur `.nav-tab`, sobald es Gruppen gibt.** Die Gruppenknöpfe
      // tragen ebenfalls `.tabs button`; wurden sie mitgeklickt, entstanden
      // dieselben Schirme mehrfach (40 Bilder je Modul) und der Lauf lief in
      // sein Zeitlimit — der Abbruch danach sah aus wie ein Fund.
      const reiter = (gi !== null)
        ? page.locator('button.nav-tab:visible')
        : page.locator('button.nav-tab:visible, .tabs button:visible, [role=tab]:visible');
      const rz = Math.min(await reiter.count(), 16);
      for (let i = 0; i < rz; i++) {
        const rname = ((await reiter.nth(i).innerText().catch(() => '')) || `#${i}`)
          .replace(/\s+/g, ' ').trim().slice(0, 22);
        aktuell = `${m.pfad} ${gname} › ${rname}`;
        await reiter.nth(i).click().catch(() => {});
        await page.waitForLoadState('networkidle').catch(() => {});
        await warte(800);
        const sauber = (s) => s.replace(/[^\p{L}\p{N}]+/gu, '_').replace(/^_|_$/g, '').toLowerCase();
        await ablichten(page, `${m.name}-${sauber(gname) || 'x'}-${sauber(rname)}`);
        await pruefe(page);
        schirme += 1;
      }
    }
  }

  aktuell = 'Konsole';
  const echte = konsole.filter((f) => !/favicon|ResizeObserver/i.test(f));
  if (echte.length) fund('Konsolenfehler', `${echte.length}: ${echte.slice(0, 4).join(' | ')}`);
  for (const s of [...new Set(serverfehler)].slice(0, 6)) fund('Serverfehler', s);

  await browser.close();
  writeFileSync(`${OUT}schirmlauf.json`, JSON.stringify(
    { base: BASE, sprache: SPRACHE, breite: BREITE, schirme,
      bilder: bilder.length, funde }, null, 2));
  console.log(`\n=== ${schirme} Bildschirme · ${bilder.length} Bilder · ${funde.length} Funde`);
  console.log(`Bilder: ${SHOTS}`);
  process.exit(funde.length ? 1 : 0);
})();
