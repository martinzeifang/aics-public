/**
 * Funktionstest über alle sechs Compliance-Module — über einen echten Firefox.
 *
 * Gegenstand ist die Oberfläche **nach v8.2.0**: die gemeinsame
 * Projekt-Werkzeugleiste (#1851), die zwei geteilten Bausteine am Objekt
 * (#1847/#1848) und der gemeinsame Modal-Rahmen (#1849). Ein Klick-Test zeigt,
 * ob ein Knopf da ist und wirkt — die Regeln dahinter prüft
 * `logikpruefung.mjs` über die Schnittstelle.
 *
 * WAS BEWUSST NICHT GEKLICKT WIRD
 * „🐙 Issues anlegen" legt Issues im **fremden** Repository an — eine
 * Nebenwirkung in einem System, die von hier niemand zurücknehmen kann. Die
 * beiden Massenbewertungen kosten KI-Läufe; ihre Auswahlschritte werden
 * geöffnet und wieder geschlossen. „📥 Issue-Feedback übernehmen" schreibt in
 * Freitexte und fragt vorher nach.
 *
 * Geklickt wird also: Audit-Log (GET), Neubewertungs-Übersicht (GET), die
 * Auswahlschritte der Massenbewertung, der Objekt-Editor mit seinen beiden
 * Bausteinen und das Anlegen-Formular (geöffnet, nicht abgesendet).
 *
 * Jeder Fund nennt seine Erwartung im Klartext — „erwartet X, bekam Y" ist das,
 * was in ein Issue gehört, „geht nicht" nicht.
 *
 * ENV: AICS_BASE (Vorgabe Dev) · AICS_EMAIL · AICS_PASSWORD · AICS_HEADED=1
 * Lauf: node tools/e2e/module_funktionstest.mjs
 */
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { firefox } from 'playwright';

const BASE = process.env.AICS_BASE || 'https://aics-dev.290985.intern:8444';
const OUT = new URL('./out/', import.meta.url).pathname;
const SHOTS = `${OUT}funktionstest/`;

// Die Beschriftungen stammen aus `frontend/src/utils/aktionen.ts`. Sie hier zu
// wiederholen ist Absicht: Der Test prüft, was der **Anwender sieht**. Liest er
// den Katalog ein, prüft er den Katalog gegen sich selbst.
const PROJEKT_KNOEPFE = [
  '🤖 Automatische Massenbewertung',
  '🧮 Massenbewertung (Sammel-Prompt)',
  '🐙 Issues anlegen',
  '🔄 Issue-Status abgleichen',
  '📥 Issue-Feedback übernehmen',
  '🧪 Neubewertung aus Issues',
  '📜 Audit-Log',
];

/** Je Modul: Route, Tab mit den Objekten, und wie eine Objektzeile aufgeht. */
const MODULE = [
  { key: 'cra', route: '/cra', name: 'CRA',
    tab: 'Anforderungen', zeile: '.anf-list table tbody tr' },
  { key: 'nis2', route: '/nis2', name: 'NIS2',
    tab: 'Anforderungen', zeile: '.anf-list table tbody tr' },
  { key: 'aiact', route: '/aiact', name: 'AI Act',
    tab: 'Anforderungen', zeile: '.anf-list table tbody tr' },
  { key: 'dsgvo', route: '/dsgvo', name: 'DSGVO',
    tab: 'Anforderungen', zeile: '.anf-list table tbody tr' },
  { key: 'wiba', route: '/wiba', name: 'WiBA',
    tab: 'Prüffragen', zeile: '.frage-row', vorher: '.thema-head' },
  { key: 'risikobewertung', route: '/risikobewertung', name: 'Risikobewertung',
    tab: 'Risiken', zeile: 'table tbody tr' },
];

const funde = [];
const ok = [];
let modul = '';

function fund(text, erwartet, bekommen, extra = {}) {
  funde.push({ modul, text, erwartet, bekommen, ...extra });
  console.log(`  ✖ ${text}\n      erwartet: ${erwartet}\n      bekommen: ${bekommen}`);
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

async function schuss(page, name) {
  try { await page.screenshot({ path: `${SHOTS}${name}.png` }); } catch { /* egal */ }
}

/** Ist ein Dialog des gemeinsamen Rahmens offen? */
const RAHMEN = '.mr-overlay';

async function rahmenOffen(page) {
  return (await page.locator(RAHMEN).count()) > 0
    && await page.locator(RAHMEN).first().isVisible();
}

(async () => {
  mkdirSync(SHOTS, { recursive: true });
  const { email, pw } = zugang();
  const browser = await firefox.launch({ headless: !process.env.AICS_HEADED });
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true,
                                         viewport: { width: 1600, height: 1000 } });
  const page = await ctx.newPage();

  // Fehler-Aufnahme über den ganzen Lauf (#1839: Fehler, die mit ihrer
  // Komponente verschwinden, sieht man in der Oberfläche nicht).
  const konsole = [];
  const http = [];
  page.on('console', (m) => {
    if (m.type() === 'error') konsole.push({ modul, text: m.text().slice(0, 300) });
  });
  page.on('pageerror', (e) => konsole.push({ modul, text: `pageerror: ${String(e).slice(0, 300)}` }));
  page.on('response', (r) => {
    if (r.status() >= 400 && r.url().includes('/api/')) {
      http.push({ modul, status: r.status(), url: r.url().replace(BASE, '') });
    }
  });

  // ── Anmelden ──────────────────────────────────────────────────────────
  console.log(`\n== Anmeldung an ${BASE} ==`);
  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.fill('input[type="email"], input[name="email"]', email);
  await page.fill('input[type="password"]', pw);
  await page.click('button[type="submit"]');
  try {
    await page.waitForSelector('nav, .app-layout, .sidebar', { timeout: 30000 });
    gut('Anmeldung');
  } catch {
    fund('Anmeldung', 'App-Layout erscheint', 'Zeitüberschreitung');
    await schuss(page, '00-anmeldung');
    await browser.close();
    process.exit(2);
  }
  await schuss(page, '00-angemeldet');

  // ── Je Modul ──────────────────────────────────────────────────────────
  for (const m of MODULE) {
    modul = m.name;
    console.log(`\n== ${m.name} ==`);
    // Über die Navigationsleiste, nicht über den Hash: Die App nutzt
    // History-Routing — ein `#/cra` landet auf der Startseite, und der Test
    // prüfte dann die Firmenübersicht statt des Moduls.
    await page.goto(`${BASE}${m.route}`, { waitUntil: 'domcontentloaded' })
      .catch(() => {});
    await warte(3500);
    if (!page.url().includes(m.route)) {
      await page.getByRole('link', { name: new RegExp(m.name.replace(/ /g, '\\s*')) })
        .first().click().catch(() => {});
      await warte(3500);
    }

    // Erstes Projekt in der Seitenleiste wählen.
    //
    // **Mit Wiederholung.** Die Leiste lädt ihre Projekte nach dem Wechsel
    // asynchron; nach einem Modul mit viel Interaktion dauert das länger als
    // die feste Wartezeit. Ein Durchlauf, der dann „0 Einträge" meldet,
    // beschreibt seine eigene Ungeduld und nicht die Anwendung.
    const projekte = page.locator('.proj-name, .projekt-item, .proj-switch option');
    let anzahl = 0;
    for (let v = 0; v < 16; v++) {
      anzahl = await projekte.count();
      if (anzahl > 0) break;
      await warte(1500);
    }
    if (anzahl === 0) {
      fund('Projektliste', 'mindestens ein Projekt in der Seitenleiste', '0 Einträge');
      await schuss(page, `${m.key}-00-leer`);
      continue;
    }
    // Der Projektwechsler im Kopf erscheint erst **mit** gewähltem Projekt —
    // vorher steht dort „Projekt wählen". Deshalb führt der Weg immer über die
    // Liste; der Wechsler bleibt der Ausweg.
    {
      // Erst alle Firmengruppen aufklappen (🏢), dann das erste echte Projekt
      // wählen — sonst steht nur die Firma da und kein Projekt ist aktiv.
      const firmen = page.locator('.proj-name');
      const nf = await firmen.count();
      for (let i = 0; i < nf; i++) {
        const t = ((await firmen.nth(i).textContent()) || '').trim();
        if (t.startsWith('🏢')) await firmen.nth(i).click({ timeout: 5000 }).catch(() => {});
      }
      await warte(1200);
      const alle = page.locator('.proj-name');
      const na = await alle.count();
      let gewaehlt = false;
      for (let i = 0; i < na; i++) {
        const t = ((await alle.nth(i).textContent()) || '').trim();
        if (t.startsWith('🏢') || t.startsWith('—')) continue;
        await alle.nth(i).click({ timeout: 5000 }).catch(() => {});
        gewaehlt = true;
        break;
      }
      if (!gewaehlt) {
        const wechsler = page.locator('select.proj-switch');
        if (await wechsler.count()) await wechsler.selectOption({ index: 0 }).catch(() => {});
      }
    }
    await warte(2500);
    await schuss(page, `${m.key}-01-projekt`);

    // ── 1) Die sieben Knöpfe der Werkzeugleiste ───────────────────────
    const leiste = page.locator('.pw-leiste');
    if (!(await leiste.count())) {
      fund('Projekt-Werkzeugleiste', '.pw-leiste im Projekt-Kopf',
           'nicht vorhanden — die Leiste ist nicht eingebunden oder kein Projekt gewählt');
      await schuss(page, `${m.key}-02-keine-leiste`);
      continue;
    }
    const sichtbar = (await leiste.first().innerText()).replace(/\s+/g, ' ');
    const fehlende = PROJEKT_KNOEPFE.filter((k) => !sichtbar.includes(k));
    if (fehlende.length) {
      fund('Beschriftungen der sieben Handlungen',
           PROJEKT_KNOEPFE.join(' · '),
           `fehlt: ${fehlende.join(' · ')} — vorhanden: ${sichtbar.slice(0, 200)}`);
    } else {
      gut('alle sieben Handlungen mit der Katalog-Beschriftung');
    }
    if (/\bSync\b|synchronisier/i.test(sichtbar)) {
      fund('kein „Sync" in der Oberfläche', 'keine Fundstelle in der Leiste',
           sichtbar.match(/[^·]*[Ss]ync[^·]*/)?.[0] || '(Treffer)');
    }

    // ── 2) Audit-Log: öffnen, Inhalt, Escape schließt ─────────────────
    await leiste.getByRole('button', { name: /Audit-Log/ }).first().click();
    await warte(2500);
    if (!(await rahmenOffen(page))) {
      fund('Audit-Log öffnet', 'Dialog im gemeinsamen Rahmen (.mr-overlay)',
           'kein Dialog sichtbar');
    } else {
      const text = await page.locator(RAHMEN).first().innerText();
      await schuss(page, `${m.key}-03-audit`);
      if (/Interner Serverfehler|konnte nicht geladen/.test(text)) {
        fund('Audit-Log lädt', 'Einträge oder „noch kein Eintrag"',
             text.split('\n').slice(0, 4).join(' | '));
      } else if (/Eintrag|Einträge/.test(text)) {
        gut(`Audit-Log zeigt Einträge (${(text.match(/^\d+/m) || ['?'])[0]})`);
      } else {
        gut('Audit-Log geöffnet (leer)');
      }
      // #1849: Escape schließt die oberste Ebene.
      await page.keyboard.press('Escape');
      await warte(1200);
      if (await rahmenOffen(page)) {
        fund('Escape schließt den Dialog', 'Dialog geschlossen', 'Dialog bleibt offen');
        await page.locator(`${RAHMEN} .mr-schliessen`).first().click().catch(() => {});
        await warte(800);
      } else {
        gut('Escape schließt den Dialog');
      }
    }

    // ── 3) Neubewertungs-Übersicht (GET, schreibt nichts) ─────────────
    await leiste.getByRole('button', { name: /Neubewertung aus Issues/ }).first().click();
    await warte(2500);
    if (!(await rahmenOffen(page))) {
      fund('Neubewertungs-Übersicht öffnet', 'Dialog im gemeinsamen Rahmen',
           'kein Dialog sichtbar');
    } else {
      const text = await page.locator(RAHMEN).first().innerText();
      await schuss(page, `${m.key}-04-neubewertung`);
      if (/Interner Serverfehler|konnten nicht geladen/.test(text)) {
        fund('Neubewertungs-Übersicht lädt', 'Objektliste oder „kein Issue verknüpft"',
             text.split('\n').slice(0, 4).join(' | '));
      } else {
        gut('Neubewertungs-Übersicht geöffnet');
      }
      await page.locator(`${RAHMEN} .mr-schliessen`).first().click().catch(() => {});
      await warte(1000);
    }

    // ── 4) Massenbewertung: Auswahlschritt öffnen, nicht starten ──────
    for (const [name, muster] of [['Sammel-Prompt', /Massenbewertung \(Sammel-Prompt\)/],
                                  ['automatisch', /Automatische Massenbewertung/]]) {
      const knopf = leiste.getByRole('button', { name: muster }).first();
      if (!(await knopf.count())) continue;
      await knopf.click().catch(() => {});
      await warte(2000);
      const dialog = page.locator('.modal-overlay, .mr-overlay').last();
      if (!(await dialog.count()) || !(await dialog.isVisible())) {
        fund(`Massenbewertung ${name} öffnet`, 'Auswahl-Dialog erscheint',
             'kein Dialog sichtbar — das war #1535');
      } else {
        gut(`Massenbewertung ${name}: Auswahl erscheint`);
        await schuss(page, `${m.key}-05-masse-${name.replace(/[^a-z]/gi, '')}`);
      }
      await page.keyboard.press('Escape');
      await warte(600);
      const zu = page.locator('.modal-overlay, .mr-overlay');
      if ((await zu.count()) && await zu.last().isVisible()) {
        await zu.last().locator('.btn-close, .mr-schliessen').first().click().catch(() => {});
        await warte(600);
      }
    }

    // ── 5) Objekt-Editor: die zwei geteilten Bausteine ────────────────
    // Zwei Tab-Formen im Haus: eine **gruppierte** Navigation
    // (`button.nav-group` → `button.nav-tab`) und eine flache Leiste. Ohne den
    // Griff in die Gruppe bleibt der Durchlauf auf „Überblick" stehen — und
    // meldet dann „0 Zeilen" für eine Liste, die er nie geöffnet hat.
    const gruppen = page.locator('button.nav-group:visible');
    const gN = await gruppen.count();
    let tabOffen = false;
    for (let g = 0; g < gN && !tabOffen; g++) {
      await gruppen.nth(g).click().catch(() => {});
      await warte(500);
      const reiter = page.locator('button.nav-tab:visible')
        .filter({ hasText: new RegExp(m.tab) }).first();
      if (await reiter.count()) { await reiter.click().catch(() => {}); tabOffen = true; }
    }
    if (!tabOffen) {
      // Flache Leiste (`TabBar` → `button.tab-btn`). **Nicht** über die Rolle
      // suchen: „Risiken" steht auch in der Seitenleiste („9 Risiken"), und
      // der Durchlauf klickte dann dorthin und blieb auf „Dashboard".
      for (const sel of ['button.tab-btn:visible', 'button.nav-tab:visible',
                         '.tab-bar button:visible']) {
        const b = page.locator(sel).filter({ hasText: new RegExp(m.tab) }).first();
        if (await b.count()) { await b.click().catch(() => {}); tabOffen = true; break; }
      }
    }
    await warte(2500);
    if (!tabOffen) {
      fund(`Tab „${m.tab}" öffnen`, 'Reiter in der Modul-Navigation',
           'nicht gefunden — ohne ihn ist die Objektliste nicht erreichbar');
    }
    if (m.vorher) {
      const auf = page.locator(m.vorher).first();
      if (await auf.count()) { await auf.click().catch(() => {}); await warte(1200); }
    }
    const zeilen = page.locator(m.zeile);
    if (!(await zeilen.count())) {
      await schuss(page, `${m.key}-06-keine-objekte`);
      // Eine leere Liste ist nicht immer ein Fund. WiBA lädt den BSI-Katalog
      // zur Laufzeit (er ist aus Urheberrechtsgründen nicht eingecheckt);
      // ohne ihn gibt es keine Prüffragen, und die Maske sagt das auch — das
      // ist das **behobene** Fehlerbild aus #1817, nicht ein neues.
      const text = await page.locator('body').innerText();
      if (/Katalog ist auf dieser Installation noch nicht eingelesen/.test(text)) {
        gut('Objektliste leer, weil der Katalog fehlt — mit Hinweis und Weg (#1817)');
      } else if (/Noch kein|Keine .* vorhanden|Lege ein/.test(text)) {
        gut('Objektliste leer — das Projekt hat noch keine Objekte');
      } else {
        fund('Objektliste', `Zeilen unter ${m.zeile}`,
             '0 Zeilen und kein erklärender Hinweis — hier fehlt entweder die '
             + 'Liste oder die Auskunft, warum sie leer ist');
      }
      continue;
    }
    await zeilen.first().click({ timeout: 8000 }).catch(() => {});
    await warte(2500);
    await schuss(page, `${m.key}-07-editor`);

    const seite = await page.locator('body').innerText();
    for (const [was, muster] of [
      ['KI-Bewertungs-Baustein', /KI-BEWERTUNG|KI-Bewertung/i],
      ['Issue-Baustein', /VERKNÜPFTE ISSUES|Verknüpfte Issues/i],
    ]) {
      if (muster.test(seite)) gut(`${was} im Editor`);
      else fund(`${was} im Editor`, 'Abschnitt vorhanden',
                'nicht gefunden — Baustein nicht eingebunden oder Editor nicht offen');
    }
    // Die Knöpfe des Issue-Bausteins (die Beschriftungen aus dem Katalog).
    for (const k of ['➕ Issue anlegen', '🔗 Bestehendes verknüpfen', '🔄 Status abgleichen']) {
      if (seite.includes(k)) gut(`Knopf „${k}"`);
      else fund(`Knopf „${k}"`, 'im Issue-Baustein sichtbar', 'fehlt');
    }

    // ── 6) Anlegen-Formular: Repo ist kein Pflichtfeld ───────────────
    const anlegen = page.getByRole('button', { name: /➕ Issue anlegen/ }).first();
    if (await anlegen.count()) {
      await anlegen.click().catch(() => {});
      await warte(1500);
      if (!(await rahmenOffen(page))) {
        fund('Anlegen-Formular öffnet', 'Dialog im gemeinsamen Rahmen', 'kein Dialog');
      } else {
        await schuss(page, `${m.key}-08-anlegen`);
        const primaer = page.locator(`${RAHMEN} .iv-primaer`).first();
        const gesperrt = await primaer.isDisabled().catch(() => null);
        if (gesperrt === true) {
          fund('Repository ist kein Pflichtfeld',
               'Anlegen bleibt bedienbar (der Server löst das Repo aus dem Projekt auf)',
               'Knopf ist gesperrt, solange das Feld leer ist');
        } else {
          gut('Anlegen-Formular: Repository ist kein Pflichtfeld');
        }
        await page.keyboard.press('Escape');
        await warte(800);
        if (await rahmenOffen(page)) {
          await page.locator(`${RAHMEN} .mr-schliessen`).first().click().catch(() => {});
        }
      }
    }
    await warte(500);
  }

  // ── Bericht ───────────────────────────────────────────────────────────
  modul = '';
  console.log('\n== Konsole / HTTP ==');
  for (const k of konsole.slice(0, 25)) console.log(`  ⚠ [${k.modul}] ${k.text}`);
  for (const h of http.slice(0, 25)) console.log(`  ⚠ [${h.modul}] HTTP ${h.status} ${h.url}`);

  const bericht = {
    base: BASE, zeitpunkt: new Date().toISOString(),
    geprueft: ok.length, funde, konsole, http,
  };
  writeFileSync(`${OUT}funktionstest.json`, JSON.stringify(bericht, null, 2));
  console.log(`\n${ok.length} Prüfungen gut · ${funde.length} Funde · `
    + `${konsole.length} Konsolenfehler · ${http.filter((h) => h.status >= 500).length} 5xx`);
  console.log(`Bericht: ${OUT}funktionstest.json · Bilder: ${SHOTS}`);
  await browser.close();
  process.exit(funde.length || konsole.length ? 1 : 0);
})().catch((e) => { console.error('Setup-Fehler:', e); process.exit(2); });
