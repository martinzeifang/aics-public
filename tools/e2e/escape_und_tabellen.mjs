/**
 * Escape schließt jede Schicht, breite Tabellen bleiben im Rahmen (#2045/#2062).
 *
 * WARUM DIESER LAUF NEBEN DEN WÄCHTERN STEHT
 * `tests/test_escape_schicht_2045.py` prüft die **Verdrahtung** — dass der
 * Fallback an `window` hängt, dass `ModalRahmen` Vorrang hat, dass kein Dialog
 * ihn nachbaut. Er kann nicht prüfen, ob ein Tastendruck im Browser wirklich
 * eine Schicht schließt: Dafür braucht es die Schicht, ihren `@mousedown.self`
 * und Vues Ereignisweg.
 *
 * Dasselbe bei #2062: Der Wächter prüft, dass ein Rahmen **da** ist. Ob die
 * Tabelle darin bleibt, sagt nur die gemessene Breite — und die 91 Screenshots
 * des Prüflaufs sind bei 1600 px aufgenommen, wo die Tabellen passen. Deshalb
 * stand #2062 als PLAUSIBLE und nicht als CONFIRMED da. Dieser Lauf misst bei
 * **1280 px**, der Breite eines geteilten Bildschirms.
 *
 * DREI FALLEN, DIE DER ERSTE ANLAUF GESTELLT HAT
 * 1. **Sprache.** Playwright schickt `en-US`, die Oberfläche schaltet auf
 *    Englisch (#1954), und ein Lauf, der die Sprache nicht nennt, prüft je
 *    nach Umgebung eine andere. `locale` steht jetzt ausdrücklich da.
 * 2. **Der Klick auf die Firma ist nicht der Klick auf das Projekt.** Ein
 *    Klick auf 🏢 öffnet die Firmenübersicht (#1569) — dort gibt es weder
 *    Werkzeugleiste noch breite Tabelle. Der Lauf meldete „keine Tabelle
 *    sichtbar", und das war eine Aussage über den Lauf.
 * 3. **Geratene Reiternamen.** Vier von sechs waren falsch. Geraten ist
 *    dieselbe Spiegel-Liste wie im Backend (#1731/#1735), nur im Werkzeug —
 *    deshalb geht der Lauf jetzt **alle** Reiter durch.
 *
 * WAS BEWUSST NICHT PASSIERT
 * Keine Handlung mit Nebenwirkung: Dialoge werden geöffnet und mit Escape
 * geschlossen, nichts abgeschickt. „🐙 Issues anlegen" bleibt unangetastet —
 * es legt Tickets im Repository des Kunden an.
 *
 * ENV: AICS_BASE · AICS_EMAIL · AICS_PASSWORD · AICS_LOCALE · AICS_HEADED=1
 * Lauf: node tools/e2e/escape_und_tabellen.mjs
 */
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { firefox } from 'playwright';

const BASE = process.env.AICS_BASE || 'https://aics-dev.290985.intern:8444';
const SPRACHE = process.env.AICS_LOCALE || 'de-DE';
const OUT = new URL('./out/', import.meta.url).pathname;
const SHOTS = `${OUT}escape_tabellen/`;
const MODULE = ['/cra', '/nis2', '/aiact', '/dsgvo', '/wiba', '/risikobewertung'];
const BREIT_AB = 7;

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
const schichten = (page) => page.$$eval('[class*="overlay"]', (els) => els
  .filter((e) => e.getClientRects().length > 0)
  .map((e) => e.className));

/** Alle breiten Tabellen der aktuellen Ansicht, gemessen. */
const messe = (page, ab) => page.$$eval('table', (tabs, grenze) => tabs
  .filter((t) => t.querySelectorAll('thead th').length >= grenze
                 && t.getClientRects().length > 0)
  .map((t) => {
    // Der nächste Vorfahre mit eigenem Überlauf — dort darf gescrollt werden.
    // Über den **Vorfahren** statt über einen Klassennamen: So zählt die
    // Lösung aus #1782 (`.tbl-wrap`) genauso wie die neue `.tabelle-scroll`,
    // und der Lauf schreibt keine zweite Liste fest.
    let rahmen = t.parentElement;
    let imRahmen = false;
    while (rahmen && rahmen !== document.body) {
      const s = getComputedStyle(rahmen);
      if (s.overflowX === 'auto' || s.overflowX === 'scroll') { imRahmen = true; break; }
      rahmen = rahmen.parentElement;
    }
    return { breite: Math.round(t.getBoundingClientRect().width),
             seite: document.documentElement.scrollWidth,
             fenster: window.innerWidth, imRahmen,
             spalten: t.querySelectorAll('thead th').length };
  }), ab);

(async () => {
  mkdirSync(SHOTS, { recursive: true });
  const { email, pw } = zugang();
  const browser = await firefox.launch({ headless: !process.env.AICS_HEADED });
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true, locale: SPRACHE,
                                         viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const konsole = [];
  page.on('console', (m) => { if (m.type() === 'error') konsole.push(m.text()); });

  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[type="email"], input[name="email"]', email);
  await page.fill('input[type="password"]', pw);
  await page.click('button[type="submit"]');
  await page.waitForLoadState('networkidle').catch(() => {});
  await schuss(page, '00-angemeldet');

  let tabellen = 0;
  for (const pfad of MODULE) {
    modul = pfad;
    console.log(`\n── ${modul}`);
    // History-Routing: ein `#/cra` landet auf der Startseite (#1854/#1856).
    await page.goto(`${BASE}${pfad}`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle').catch(() => {});
    await warte(800);

    // Erst die Firmengruppe aufklappen (🏢), dann das **Produkt** (📦).
    const gruppe = page.locator('aside >> text=🏢').first();
    if (await gruppe.count()) { await gruppe.click().catch(() => {}); await warte(600); }
    const produkt = page.locator('aside >> text=📦').first();
    if (await produkt.count()) {
      await produkt.click().catch(() => {});
    } else {
      // **NIS2, DSGVO und WiBA sind firmenweit** — ihre Seitenleiste führt
      // Mandanten ohne 🏢/📦 (`FirmenSidebarModul`). Der frühere Rückfall
      // „zweites klickbares Element" traf dort das Sortierfeld, das Modul
      // blieb auf „Firma wählen", und der Lauf meldete „Reiter: (keine)" —
      // wieder eine Aussage über den Lauf statt über die Anwendung.
      //
      // Deshalb: das erste Element mit **Text**, das kein Bedienelement der
      // Leiste ist. Die Namen stehen bewusst nicht hier; sie wären
      // datenabhängig und machten den Lauf an einen Bestand gebunden.
      // `.sidebar-list` ist die Liste selbst — **strukturell**, nicht über
      // Beschriftungen oder Datenwerte. Der vorige Rückfall suchte
      // `li`/`button`/`a`; die Einträge sind aber `div`, und die Schleife
      // traf stattdessen die `<option>`-Elemente der Sortierung.
      const liste = page.locator('aside .sidebar-list > *');
      const anzahl = Math.min(await liste.count(), 30);
      for (let i = 0; i < anzahl; i++) {
        const txt = ((await liste.nth(i).innerText().catch(() => '')) || '').trim();
        if (txt.length < 4) continue;
        await liste.nth(i).click().catch(() => {});
        await warte(500);
        // Firmen-Seitenleisten klappen beim ersten Klick nur auf; steht
        // danach ein Projekt darunter, ist das der zweite Schritt.
        const tiefer = page.locator('aside .sidebar-list .projekt, '
                                    + 'aside .sidebar-list [class*="produkt"]').first();
        if (await tiefer.count()) await tiefer.click().catch(() => {});
        break;
      }
    }
    await page.waitForLoadState('networkidle').catch(() => {});
    await warte(1200);

    if (await page.locator('button').count() < 3) {
      fund('Modul geöffnet und Projekt gewählt', 'eine Maske mit Bedienelementen',
           'kaum Knöpfe sichtbar — die Navigation griff nicht');
      await schuss(page, `${modul.slice(1)}-keine-maske`);
      continue;
    }

    // ── Escape am Audit-Log: ein GET ohne Nebenwirkung ────────────────
    const auditKnopf = page.locator('button:has-text("📜")').first();
    if (await auditKnopf.count()) {
      await auditKnopf.click().catch(() => {});
      await warte(900);
      const vorher = await schichten(page);
      if (!vorher.length) {
        fund('Audit-Log öffnet eine Schicht', 'eine sichtbare Schicht', 'keine');
      } else {
        await schuss(page, `${modul.slice(1)}-dialog-offen`);
        await page.keyboard.press('Escape');
        await warte(600);
        const nachher = await schichten(page);
        if (nachher.length < vorher.length) {
          gut(`Escape schließt die Schicht (${vorher[vorher.length - 1]})`);
        } else {
          fund('Escape schließt die oberste Schicht', 'Schicht geschlossen',
               `${nachher.length} weiter offen: ${nachher.join(' · ')}`);
          await schuss(page, `${modul.slice(1)}-escape-wirkungslos`);
        }
      }
    }

    // ── Tabellen in **jedem** Reiter ──────────────────────────────────
    const reiter = page.locator('.tabs button, [role=tablist] button, nav.tabs button');
    const n = Math.min(await reiter.count(), 14);
    const namen = [];
    for (let i = 0; i < Math.max(n, 1); i++) {
      let name = '—';
      if (n) {
        name = ((await reiter.nth(i).innerText().catch(() => '')) || `#${i}`)
          .replace(/\s+/g, ' ').trim().slice(0, 26);
        await reiter.nth(i).click().catch(() => {});
        await page.waitForLoadState('networkidle').catch(() => {});
        await warte(600);
        namen.push(name);
      }
      for (const t of await messe(page, BREIT_AB)) {
        tabellen += 1;
        const was = `${modul} „${name}" (${t.spalten} Spalten)`;
        if (t.seite > t.fenster + 2) {
          fund(`${was} schiebt die Seite über den Rand`,
               `Seitenbreite ≤ ${t.fenster} px`, `${t.seite} px`);
          await schuss(page, `${modul.slice(1)}-${i}-ueberlauf`);
        } else if (!t.imRahmen) {
          fund(`${was} hat keinen Überlauf-Rahmen`,
               'ein Vorfahre mit overflow-x: auto', 'keiner gefunden');
          await schuss(page, `${modul.slice(1)}-${i}-ohne-rahmen`);
        } else {
          gut(`${was} bleibt im Rahmen (${t.breite} von ${t.fenster} px)`);
        }
      }
    }
    console.log(`  · Reiter: ${namen.join(' · ') || '(keine)'}`);
    await schuss(page, `${modul.slice(1)}-zuletzt`);
  }

  // Ein stiller `ReferenceError` ist die Klasse aus #1854 — die Maske meldet
  // „Fehler beim Laden" für Daten, die da sind.
  modul = 'Konsole';
  const echte = konsole.filter((f) => !/favicon|ResizeObserver/i.test(f));
  if (echte.length) {
    fund('keine Konsolenfehler', 'leere Konsole',
         `${echte.length}: ${echte.slice(0, 5).join(' | ')}`);
  } else {
    gut('keine Konsolenfehler');
  }

  await browser.close();
  writeFileSync(`${OUT}escape_tabellen.json`, JSON.stringify(
    { base: BASE, sprache: SPRACHE, viewport: '1280x900',
      breite_tabellen: tabellen, ok: ok.length, funde, geprueft: ok }, null, 2));
  console.log(`\n=== ${ok.length} geprüft (${tabellen} breite Tabellen) · ${funde.length} Funde`);
  console.log(`Screenshots: ${SHOTS}`);
  process.exit(funde.length ? 1 : 0);
})();
