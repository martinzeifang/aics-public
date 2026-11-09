/**
 * Escape schließt jede Schicht, breite Tabellen bleiben im Rahmen (#2045/#2062).
 *
 * WARUM DIESER LAUF NEBEN DEN WÄCHTERN STEHT
 * `tests/test_escape_schicht_2045.py` prüft die **Verdrahtung** — dass der
 * Fallback an `window` hängt, dass `ModalRahmen` Vorrang hat, dass kein Dialog
 * ihn nachbaut. Er kann nicht prüfen, ob ein Tastendruck im Browser wirklich
 * eine Schicht schließt: Dafür braucht es die Schicht, ihren `@mousedown.self`
 * und Vues Ereignisweg. Genau das ist hier der Gegenstand.
 *
 * Dasselbe bei #2062: Der Wächter prüft, dass ein Rahmen **da** ist. Ob die
 * Tabelle darin bleibt, sagt nur die gemessene Breite — und die 91 Screenshots
 * des Prüflaufs sind bei 1600 px aufgenommen, wo die Tabellen passen. Dieser
 * Lauf misst bei **1280 px**, der Breite eines geteilten Bildschirms.
 *
 * WAS BEWUSST NICHT PASSIERT
 * Keine Handlung mit Nebenwirkung: Dialoge werden geöffnet und mit Escape
 * geschlossen, nichts abgeschickt. „🐙 Issues anlegen" wird nicht angefasst —
 * es legt Tickets im Repository des Kunden an (die Regel aus
 * `module_funktionstest.mjs`).
 *
 * ENV: AICS_BASE · AICS_EMAIL · AICS_PASSWORD · AICS_HEADED=1
 * Lauf: node tools/e2e/escape_und_tabellen.mjs
 */
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { firefox } from 'playwright';

const BASE = process.env.AICS_BASE || 'https://aics-dev.290985.intern:8444';
const OUT = new URL('./out/', import.meta.url).pathname;
const SHOTS = `${OUT}escape_tabellen/`;

/** Module und der Tab, in dem eine breite Tabelle steht. */
const ZIELE = [
  { pfad: '/cra', tab: 'Dokumentation' },
  { pfad: '/nis2', tab: 'Dokumentation' },
  { pfad: '/aiact', tab: 'Art. 4' },
  { pfad: '/dsgvo', tab: 'Betroffenenrechte' },
  { pfad: '/wiba', tab: 'Prüffragen' },
  { pfad: '/risikobewertung', tab: 'Risiken' },
];

const funde = [];
const ok = [];
let modul = '-';

function fund(text, erwartet, bekommen) {
  funde.push({ modul, text, erwartet, bekommen });
  console.log(`  ✘ ${text}\n      erwartet: ${erwartet}\n      bekam:    ${bekommen}`);
}
function gut(text) { ok.push({ modul, text }); console.log(`  ✔ ${text}`); }

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
const schuss = async (page, name) => {
  try { await page.screenshot({ path: `${SHOTS}${name}.png` }); } catch { /* egal */ }
};

/** Jede sichtbare Schicht — gleich welche Klasse. */
async function schichten(page) {
  return page.$$eval('[class*="overlay"]', (els) => els
    .filter((e) => e.getClientRects().length > 0)
    .map((e) => e.className));
}

(async () => {
  mkdirSync(SHOTS, { recursive: true });
  const { email, pw } = zugang();
  const browser = await firefox.launch({ headless: !process.env.AICS_HEADED });
  // 1280 px: ein geteilter Bildschirm. Bei 1600 px passen die Tabellen, und
  // genau deshalb hat der Prüflauf #2062 nicht als Überlauf gesehen.
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true,
                                         viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const fehler = [];
  page.on('console', (m) => { if (m.type() === 'error') fehler.push(m.text()); });

  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[type="email"], input[name="email"]', email);
  await page.fill('input[type="password"]', pw);
  await page.click('button[type="submit"]');
  await page.waitForLoadState('networkidle').catch(() => {});
  await schuss(page, '00-angemeldet');

  for (const ziel of ZIELE) {
    modul = ziel.pfad;
    console.log(`\n── ${modul}`);
    // History-Routing: ein `#/cra` landet auf der Startseite (die Falle aus
    // #1854/#1856).
    await page.goto(`${BASE}${ziel.pfad}`, { waitUntil: 'domcontentloaded' });
    await warte(1200);

    // Projekt wählen: erst die Firmengruppe aufklappen (🏢), dann das Projekt.
    const gruppe = page.locator('aside >> text=🏢').first();
    if (await gruppe.count()) { await gruppe.click().catch(() => {}); await warte(400); }
    const eintrag = page.locator('aside li, aside .projekt, aside a').nth(1);
    if (await eintrag.count()) { await eintrag.click().catch(() => {}); await warte(1500); }

    // ── Escape: jede erreichbare Schicht ───────────────────────────────
    // Das Audit-Log ist der sichere Fall — ein GET ohne Nebenwirkung.
    const auditKnopf = page.locator('button:has-text("📜")').first();
    if (await auditKnopf.count()) {
      await auditKnopf.click().catch(() => {});
      await warte(900);
      const vorher = await schichten(page);
      await schuss(page, `${modul.slice(1)}-dialog-offen`);
      if (!vorher.length) {
        fund('Audit-Log öffnet eine Schicht', 'eine sichtbare Schicht',
             'keine Schicht gefunden');
      } else {
        await page.keyboard.press('Escape');
        await warte(600);
        const nachher = await schichten(page);
        if (nachher.length < vorher.length) {
          gut(`Escape schließt die Schicht (${vorher[vorher.length - 1]})`);
        } else {
          fund('Escape schließt die oberste Schicht', 'Schicht geschlossen',
               `${nachher.length} Schicht(en) weiter offen: ${nachher.join(' · ')}`);
          await schuss(page, `${modul.slice(1)}-escape-wirkungslos`);
        }
      }
    }

    // ── Tabellen: bleibt der Inhalt im Rahmen? ─────────────────────────
    if (ziel.tab) {
      const tab = page.locator(`button:has-text("${ziel.tab}"), [role=tab]:has-text("${ziel.tab}")`).first();
      if (await tab.count()) { await tab.click().catch(() => {}); await warte(1500); }
    }
    const ueber = await page.$$eval('table', (tabs) => tabs
      .filter((t) => t.querySelectorAll('thead th').length >= 7)
      .map((t) => {
        const r = t.getBoundingClientRect();
        // Der nächste Vorfahre mit eigenem Überlauf — dort darf gescrollt werden.
        let rahmen = t.parentElement;
        let imRahmen = false;
        while (rahmen && rahmen !== document.body) {
          const s = getComputedStyle(rahmen);
          if (s.overflowX === 'auto' || s.overflowX === 'scroll') { imRahmen = true; break; }
          rahmen = rahmen.parentElement;
        }
        return { breite: Math.round(r.width), scroll: t.scrollWidth,
                 seite: document.documentElement.scrollWidth,
                 fenster: window.innerWidth, imRahmen,
                 spalten: t.querySelectorAll('thead th').length };
      }));
    for (const t of ueber) {
      const name = `${modul} Tabelle (${t.spalten} Spalten)`;
      if (t.seite > t.fenster + 2) {
        fund(`${name} schiebt die Seite über den Rand`,
             `Seitenbreite ≤ ${t.fenster} px`, `${t.seite} px`);
        await schuss(page, `${modul.slice(1)}-tabelle-ueberlauf`);
      } else if (!t.imRahmen) {
        fund(`${name} hat keinen Überlauf-Rahmen`,
             'ein Vorfahre mit overflow-x: auto', 'keiner gefunden');
      } else {
        gut(`${name} bleibt im Rahmen (${t.breite} px von ${t.fenster} px)`);
      }
    }
    await schuss(page, `${modul.slice(1)}-tabellen`);
  }

  // Konsolenfehler sind ein eigener Fund: Ein stiller `ReferenceError` ist die
  // Klasse aus #1854 — die Maske meldet „Fehler beim Laden" für Daten, die da
  // sind.
  modul = 'Konsole';
  const echte = fehler.filter((f) => !/favicon|ResizeObserver/i.test(f));
  if (echte.length) {
    fund('keine Konsolenfehler', 'leere Konsole',
         `${echte.length}: ${echte.slice(0, 5).join(' | ')}`);
  } else {
    gut('keine Konsolenfehler');
  }

  await browser.close();
  const bericht = { base: BASE, viewport: '1280x900', ok: ok.length,
                    funde, geprueft: ok };
  writeFileSync(`${OUT}escape_tabellen.json`, JSON.stringify(bericht, null, 2));
  console.log(`\n=== ${ok.length} geprüft · ${funde.length} Funde`);
  console.log(`Screenshots: ${SHOTS}`);
  process.exit(funde.length ? 1 : 0);
})();
