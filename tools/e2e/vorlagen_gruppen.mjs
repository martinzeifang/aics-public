/**
 * Abnahme von #1776–#1779 über einen echten Firefox.
 *
 * Geprüft wird, was auf dem Bild steht. Ein grüner Playwright-Lauf beweist nur,
 * dass Elemente existieren — in v8.0.2/8.0.3 trugen genau solche Elemente
 * plausiblen, falschen Text (ein Prüfpunkt meldete „nicht bestimmbar", obwohl
 * gerechnet wurde; ein Prüfvermerk nannte „user-001" statt einer Person).
 *
 * Erwartet: Dev-Instanz mit Demo-Benutzern, mindestens ein CRA-Projekt und eine
 * Firma mit firmen_id (für den Mandanten-Reiter).
 *
 * Lauf:  AICS_BASE=https://localhost:5173 node tools/e2e/vorlagen_gruppen.mjs
 * Exit:  0 = alle Schritte erreicht, 1 = Funde, 2 = Setup-Fehler
 */
import { firefox } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE = process.env.AICS_BASE || 'https://localhost:5173';
const PROJEKT = process.env.AICS_PROJEKT || 'E2E KI Firma – Chatbot';
const FIRMA = process.env.AICS_FIRMA || 'E2E KI Firma';
const GRUPPE = `E2E-Gruppe ${new Date().toISOString().slice(11, 19)}`;
// Derselbe Name wie oben: erzwingt beim zweiten Anlegen einen 409 und damit
// eine echte Fehlermeldung (#1781).
const GRUPPE_DOPPELT = GRUPPE;
const HEADED = process.env.AICS_HEADED === '1';
const TAG = new Date().toISOString().slice(0, 10);
const ROOT = path.dirname(new URL(import.meta.url).pathname);
const SHOTS = path.join(ROOT, 'screens', TAG);
fs.mkdirSync(SHOTS, { recursive: true });

const bilder = [];
const funde = [];
let n = 0;

async function shot(page, name, titel, erwartung) {
  const datei = `1777-${String(++n).padStart(2, '0')}-${name}.png`;
  await page.screenshot({ path: path.join(SHOTS, datei), fullPage: true });
  bilder.push({ datei, titel, erwartung });
  console.log(`  📷 ${datei} — ${titel}`);
}
function fund(t) { funde.push(t); console.log(`  ⚠ ${t}`); }
function ok(t) { console.log(`  ✓ ${t}`); }

async function login(page) {
  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(900);
  await page.locator('input[type=email], input[type=text]').first().fill('admin@example.com');
  await page.locator('input[type=password]').first().fill('admin-password');
  await page.locator('button', { hasText: /Anmelden/i }).first().click();
  await page.waitForTimeout(2800);
  if (/\/login/.test(page.url())) throw new Error('Login fehlgeschlagen');
}

async function text(page) { return (await page.locator('body').innerText()).replace(/\s+/g, ' '); }

/** Auf eine Bedingung im DOM warten. Feste Wartezeiten sind im Vite-Dev-Server
 *  unzuverlässig: Die Modul-Shell feuert ein halbes Dutzend Abrufe, bevor die
 *  Ansicht ihre eigenen startet — ein 3-Sekunden-Fenster erwischt die Tabelle
 *  mal und mal nicht, und der Lauf meldet dann einen Fehler, den es nicht gibt. */
async function warte(page, fn, was, ms = 15000) {
  try {
    await page.waitForFunction(fn, null, { timeout: ms });
    return true;
  } catch {
    fund(`Zeitüberschreitung: ${was}`);
    return false;
  }
}

/** Sichtbares Element mit passendem Text klicken. */
async function klick(page, muster, sel = 'button, a, .main-tab, .tile, summary') {
  const getan = await page.evaluate(([m, s]) => {
    const re = new RegExp(m, 'i');
    const el = [...document.querySelectorAll(s)]
      .find((e) => re.test(e.textContent || '') && e.offsetParent !== null);
    if (!el) return false;
    el.scrollIntoView({ block: 'center' });
    el.click();
    return true;
  }, [muster, sel]);
  await page.waitForTimeout(1500);
  return getan;
}

async function main() {
  const browser = await firefox.launch({ headless: !HEADED });
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true,
                                         viewport: { width: 1600, height: 1300 } });
  const page = await ctx.newPage();
  page.on('console', (m) => {
    if (m.type() === 'error') fund(`Konsole: ${m.text().slice(0, 180)}`);
  });
  page.on('dialog', async (d) => {
    console.log(`  💬 Dialog: ${d.message().slice(0, 120)}`);
    await d.accept();
  });

  await login(page);

  // ── 1 · Berichts-Center: Nachweis als Karte, Vorlage je Karte ─────────────
  await page.goto(`${BASE}/cra?projekt=${encodeURIComponent(PROJEKT)}&tab=berichte`,
                  { waitUntil: 'domcontentloaded' });
  await warte(page, () => document.querySelectorAll('.rc-card').length > 3,
              'Berichtskarten im CRA-Berichts-Center');
  let t = await text(page);
  if (!/Konformitätsnachweis \(je Release\)/.test(t)) {
    fund('Karte „Konformitätsnachweis (je Release)" fehlt im Berichts-Center');
  } else {
    ok('Nachweis-Karte vorhanden');
  }
  if (!/Aufbau rechtlich vorgegeben/.test(t)) {
    fund('Hinweis auf den vorgegebenen Aufbau fehlt an Erklärung/Nachweis');
  } else { ok('Pflicht-Hinweis sichtbar'); }

  // Die Auswahl muss AN der Karte stehen — und die Vorauswahl vom Server kommen.
  const karten = await page.evaluate(() => {
    return [...document.querySelectorAll('.rc-card')].map((c) => ({
      titel: (c.querySelector('.rc-card-title')?.textContent || '').trim(),
      hatAuswahl: !!c.querySelector('.rc-card-vorlage select'),
      gewaehlt: c.querySelector('.rc-card-vorlage select')?.selectedOptions?.[0]?.textContent?.trim() || '',
      pflicht: !!c.querySelector('.rc-card-pflicht'),
    }));
  });
  console.log('  Karten:', JSON.stringify(karten, null, 1).slice(0, 1200));
  const nachweis = karten.find((k) => /Konformitätsnachweis/.test(k.titel));
  if (!nachweis) fund('Nachweis-Karte nicht im DOM');
  else {
    if (!nachweis.pflicht) fund('Nachweis-Karte ohne Pflicht-Hinweis');
    if (!nachweis.hatAuswahl) fund('Nachweis-Karte ohne Vorlagen-Auswahl');
    else if (!/kunde_nachweis|haus_nachweis/.test(nachweis.gewaehlt)) {
      fund(`Nachweis-Karte: unerwartete Vorauswahl „${nachweis.gewaehlt}"`);
    } else { ok(`Nachweis-Vorauswahl: ${nachweis.gewaehlt}`); }
  }
  // Der Kern des Befunds aus dem Betrieb: Eine Nachweis-Vorlage darf den
  // Gesamtbericht nicht kapern. Zu einem Bericht ohne passende Vorlage gehört
  // gar keine Auswahl — das ist richtig, nicht fehlend.
  const gesamt = karten.find((k) => /^Gesamtbericht/.test(k.titel));
  if (!gesamt) fund('Karte „Gesamtbericht" fehlt');
  else if (gesamt.hatAuswahl && !/Standard-Bericht/.test(gesamt.gewaehlt)) {
    fund(`Gesamtbericht hat eine Vorlage vorgewählt: „${gesamt.gewaehlt}"`);
  } else { ok('Gesamtbericht ohne fremde Vorlage'); }
  await page.evaluate(() => document.querySelector('.rc-cards')?.scrollIntoView({ block: 'start' }));
  await page.waitForTimeout(500);
  await shot(page, 'berichts-center', 'CRA-Berichts-Center mit Nachweis-Karte',
             'Karte „Konformitätsnachweis (je Release)" mit eigener Vorlagen-Auswahl und '
             + 'dem Hinweis „Aufbau rechtlich vorgegeben"; der Gesamtbericht steht auf '
             + '„Standard-Bericht".');

  // ── 2 · Admin → Word-Vorlagen: Spalten Bericht und Firma ──────────────────
  await page.goto(`${BASE}/admin/templates`, { waitUntil: 'domcontentloaded' });
  await warte(page, () => document.querySelectorAll('.data-table tbody tr').length > 0,
              'Vorlagen-Tabelle im Admin');
  await warte(page, () => {
    const r = [...document.querySelectorAll('.form-row')]
      .find((x) => /Für welchen Mandanten/.test(x.textContent || ''));
    return (r?.querySelector('select')?.options?.length || 0) > 1;
  }, 'Mandanten-Auswahl im Upload-Formular');
  t = await text(page);
  for (const wort of ['Bericht', 'Firma', 'Für welchen Bericht?', 'Für welchen Mandanten?']) {
    if (!t.includes(wort)) fund(`Admin-Vorlagen: „${wort}" fehlt`);
  }
  const zeilen = await page.evaluate(() =>
    [...document.querySelectorAll('.data-table tbody tr')].map(
      (tr) => [...tr.querySelectorAll('td')].slice(0, 5).map((td) => td.textContent.trim())));
  console.log('  Vorlagen-Zeilen:', JSON.stringify(zeilen));
  if (!zeilen.some((z) => /Konformitätsnachweis/.test(z[2] || ''))) {
    fund('Spalte „Bericht" zeigt den Berichtstyp nicht im Klartext');
  } else { ok('Berichtstyp im Klartext'); }
  if (!zeilen.some((z) => (z[3] || '') === 'Haus')) {
    fund('Spalte „Firma" zeigt Haus-Vorlagen nicht als „Haus"');
  }
  if (!zeilen.some((z) => (z[3] || '') === FIRMA)) {
    fund(`Spalte „Firma" nennt den Mandanten „${FIRMA}" nicht`);
  } else { ok('Mandant im Klartext statt als Zahl'); }
  // Das Mandanten-Auswahlfeld muss gefüllt sein (firmen_id vs. id, siehe #1778).
  const firmenOptionen = await page.evaluate(() => {
    const feld = [...document.querySelectorAll('.form-row')]
      .find((r) => /Für welchen Mandanten/.test(r.textContent || ''))?.querySelector('select');
    return feld ? [...feld.options].map((o) => o.textContent.trim()) : null;
  });
  console.log('  Mandanten-Auswahl:', JSON.stringify(firmenOptionen));
  if (!firmenOptionen || firmenOptionen.length < 2) {
    fund('Mandanten-Auswahl beim Upload ist leer — firmen_id kommt nicht an');
  } else { ok(`Mandanten-Auswahl gefüllt (${firmenOptionen.length} Einträge)`); }
  await shot(page, 'admin-vorlagen', 'Admin → Word-Vorlagen',
             'Tabelle mit den Spalten „Bericht" und „Firma" (Klartext, nicht Zahl); '
             + 'Upload-Formular fragt Bericht und Mandanten.');

  // ── 3 · Firma → Reiter Vorlagen ───────────────────────────────────────────
  await page.goto(`${BASE}/firmen`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  if (!await klick(page, FIRMA, 'tr, .m-row, a, button')) {
    fund(`Firma „${FIRMA}" in der Übersicht nicht anklickbar`);
  }
  await page.waitForTimeout(2500);
  if (!await klick(page, 'Vorlagen', '.main-tab')) {
    fund('Reiter „🧾 Vorlagen" in der Firma fehlt');
  }
  await warte(page, () => !!document.querySelector('.firma-vorlagen'),
              'Vorlagen-Reiter der Firma');
  await page.waitForTimeout(1500);
  t = await text(page);
  if (!/Word-Vorlagen für/.test(t)) fund('Firmen-Vorlagen-Reiter ohne Inhalt');
  else ok('Firmen-Vorlagen-Reiter geladen');
  if (/noch keiner Firmen-ID zugeordnet/.test(t)) {
    fund('Firma ohne firmen_id — Mandanten-Vorlagen nicht möglich');
  }
  if (!/Haus-Vorlagen/.test(t)) {
    fund('Die geltenden Haus-Vorlagen werden nicht angezeigt');
  } else { ok('Haus-Vorlagen als Rückfall sichtbar'); }
  await shot(page, 'firma-vorlagen', 'Firma → Vorlagen',
             'Eigene Vorlagen des Mandanten, darunter die geltenden Haus-Vorlagen; '
             + 'Upload-Bereich für diesen Mandanten.');

  // ── 4 · Gruppen anlegen ───────────────────────────────────────────────────
  await page.goto(`${BASE}/admin/groups`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  if (!await klick(page, 'Neue Gruppe')) throw new Error('Knopf „+ Neue Gruppe" fehlt');
  await warte(page, () => document.querySelectorAll('.rollen label').length > 0,
              'Rollenliste in der Gruppen-Maske');
  await page.locator('.modal-content input').first().fill(GRUPPE);
  // Rolle wählen und prüfen, dass die Vorschau die Rechte nennt.
  const gewaehlt = await page.evaluate(() => {
    const lab = [...document.querySelectorAll('.rollen label')]
      .find((l) => /cra_editor/.test(l.textContent || ''));
    if (!lab) return null;
    const box = lab.querySelector('input');
    box.click();
    return lab.textContent.replace(/\s+/g, ' ').trim();
  });
  await page.waitForTimeout(800);
  if (!gewaehlt) fund('Rolle cra_editor in der Gruppen-Maske nicht wählbar');
  else ok(`Rolle gewählt: ${gewaehlt}`);
  const wirkung = await page.evaluate(() =>
    document.querySelector('.wirkung')?.textContent?.replace(/\s+/g, ' ').trim() || '');
  console.log(`  Wirkung: ${wirkung.slice(0, 120)}`);
  const zahl = Number((wirkung.match(/Effektive Berechtigungen:\s*(\d+)/) || [])[1] || 0);
  if (zahl < 1) fund(`Vorschau zeigt ${zahl} effektive Berechtigungen — die Rolle wirkt nicht`);
  else ok(`Vorschau: ${zahl} effektive Berechtigungen`);
  if (!/meldet alle Mitglieder ab/.test(await text(page))) {
    fund('Der Hinweis auf die Abmeldung der Mitglieder fehlt');
  } else { ok('Abmelde-Hinweis sichtbar'); }
  await shot(page, 'gruppe-anlegen', 'Gruppe anlegen',
             'Maske mit Rollen, Einzelrechten, der gerechneten Vorschau „Effektive '
             + 'Berechtigungen" und dem Hinweis, dass eine Änderung die Mitglieder abmeldet.');

  if (!await klick(page, 'Speichern')) throw new Error('Speichern nicht möglich');
  await page.waitForTimeout(2500);
  t = await text(page);
  if (!t.includes(GRUPPE)) fund('Die neue Gruppe erscheint nicht in der Liste');
  else ok('Gruppe gespeichert und gelistet');

  // ── 5 · Mitglied zuordnen ─────────────────────────────────────────────────
  const auf = await page.evaluate(([name]) => {
    const tr = [...document.querySelectorAll('tbody tr')]
      .find((r) => r.textContent.includes(name));
    if (!tr) return false;
    const b = [...tr.querySelectorAll('button')].find((x) => x.title === 'Mitglieder');
    if (!b) return false;
    b.click();
    return true;
  }, [GRUPPE]);
  if (!auf) fund('Mitglieder-Dialog nicht erreichbar');
  await page.waitForTimeout(1500);
  const konten = await page.evaluate(() => {
    const sel = document.querySelector('.modal-content select');
    return sel ? [...sel.options].map((o) => o.textContent.trim()) : null;
  });
  console.log('  Auswählbare Konten:', JSON.stringify(konten));
  if (!konten || konten.length < 2) fund('Keine Konten zur Auswahl im Mitglieder-Dialog');
  else {
    await page.evaluate(() => {
      const sel = document.querySelector('.modal-content select');
      const opt = [...sel.options].find((o) => /editor@/.test(o.textContent));
      if (opt) { sel.value = opt.value; sel.dispatchEvent(new Event('change')); }
    });
    await page.waitForTimeout(500);
    await klick(page, 'Hinzufügen');
    await page.waitForTimeout(2000);
    t = await text(page);
    if (!/editor@example\.com/.test(t)) fund('Mitglied erscheint nicht in der Liste');
    else ok('Mitglied zugeordnet und mit E-Mail benannt (nicht als user-00x)');
  }
  await shot(page, 'gruppe-mitglieder', 'Mitglieder der Gruppe',
             'Mitgliederliste mit E-Mail-Adresse statt interner ID; Auswahlfeld für '
             + 'weitere Konten und der Hinweis auf die Abmeldung.');

  // ── 6 · Benutzerverwaltung zeigt die Gruppe ───────────────────────────────
  await page.goto(`${BASE}/admin/users`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  const editorZeile = await page.evaluate(() => {
    const tr = [...document.querySelectorAll('tbody tr')]
      .find((r) => /editor@example\.com/.test(r.textContent || ''));
    return tr ? [...tr.querySelectorAll('td')].slice(0, 4).map((td) => td.textContent.trim()) : null;
  });
  console.log('  editor-Zeile:', JSON.stringify(editorZeile));
  if (!editorZeile) fund('editor@example.com nicht in der Benutzerliste');
  else if (!editorZeile.some((z) => z.includes(GRUPPE))) {
    fund('Die Spalte „Gruppen" nennt die neue Gruppe nicht — ein Konto mit '
         + 'Gruppenrechten sieht damit rechtlos aus');
  } else { ok('Gruppe in der Benutzerliste sichtbar'); }
  await shot(page, 'benutzer-gruppen', 'Benutzerverwaltung mit Gruppen-Spalte',
             'Die Zeile von editor@example.com trägt die neue Gruppe; die eigenen '
             + 'Rollen bleiben daneben unverändert stehen.');

  // ── 7 · Fehlermeldung: sichtbar schließbar (#1781) ────────────────────────
  await page.goto(`${BASE}/admin/groups`, { waitUntil: 'domcontentloaded' });
  await warte(page, () => !!document.querySelector('.groups-view'), 'Gruppenverwaltung');
  // Doppelter Name erzwingt einen 409 — die Meldung muss ein sichtbares ✕ haben.
  await klick(page, 'Neue Gruppe');
  await warte(page, () => !!document.querySelector('.modal-content input'),
              'Maske für die neue Gruppe');
  await page.locator('.modal-content input').first().fill(GRUPPE_DOPPELT);
  await klick(page, 'Speichern');
  await page.waitForTimeout(2000);
  const banner = await page.evaluate(() => {
    const el = document.querySelector('.fh.fehler');
    return el ? { text: el.textContent.trim().slice(0, 90),
                  schliesser: !!el.querySelector('.fh-close'),
                  label: el.querySelector('.fh-close')?.getAttribute('aria-label') || '' } : null;
  });
  console.log('  Fehlerleiste:', JSON.stringify(banner));
  if (!banner) fund('Keine Fehlerleiste trotz Fehler (409)');
  else {
    if (!banner.schliesser) fund('Fehlermeldung ohne sichtbares ✕');
    if (!/schließen/i.test(banner.label)) fund('Schließen-Knopf ohne aria-label');
    await page.evaluate(() => document.querySelector('.fh .fh-close')?.click());
    await page.waitForTimeout(600);
    const weg = await page.evaluate(() => !document.querySelector('.fh.fehler'));
    if (!weg) fund('Fehlermeldung ließ sich nicht wegklicken');
    else ok('Fehlermeldung schließbar und geschlossen');
  }
  await shot(page, 'fehlermeldung', 'Fehlermeldung mit Schließen-Knopf',
             'Die rote Leiste trägt rechts ein ✕; nach dem Klick ist sie weg.');
  await page.evaluate(() => {
    [...document.querySelectorAll('button')].find(b => /Abbrechen/.test(b.textContent||''))?.click();
  });
  await page.waitForTimeout(800);

  // ── 8 · Standardgruppen vorschlagen (#1780) ───────────────────────────────
  if (!await klick(page, 'Standardgruppen anlegen')) {
    fund('Knopf „Standardgruppen anlegen…" fehlt');
  }
  await warte(page, () => document.querySelectorAll('.v-karte').length > 0,
              'Vorschlagskatalog');
  const vorschlaege = await page.evaluate(() =>
    [...document.querySelectorAll('.v-karte')].map(k => ({
      name: k.querySelector('strong')?.textContent?.trim() || '',
      zahl: (k.textContent.match(/(\d+) Berechtigungen/) || [])[1] || null,
      rollen: [...k.querySelectorAll('.tag')].length,
    })));
  console.log('  Vorschläge:', JSON.stringify(vorschlaege));
  if (vorschlaege.length < 3) fund('Zu wenige Vorschläge im Katalog');
  else if (vorschlaege.some(v => !v.zahl || v.rollen < 1)) {
    fund('Vorschlag ohne Rollen oder ohne Rechtezahl — so lässt sich nicht entscheiden');
  } else { ok(`${vorschlaege.length} Vorschläge mit Rollen und Rechtezahl`); }
  await shot(page, 'standardgruppen', 'Standardgruppen vorschlagen',
             'Jeder Vorschlag nennt seine Rollen und die Zahl der Berechtigungen, '
             + 'die daraus folgen; angelegt wird nur das Angehakte.');
  await page.evaluate(() => {
    [...document.querySelectorAll('.modal-footer button')]
      .find(b => /Abbrechen/.test(b.textContent||''))?.click();
  });
  await page.waitForTimeout(600);

  // ── 9 · Aufräumen: Gruppe wieder löschen ──────────────────────────────────
  await page.goto(`${BASE}/admin/groups`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2000);
  await page.evaluate(([name]) => {
    const tr = [...document.querySelectorAll('tbody tr')]
      .find((r) => r.textContent.includes(name));
    [...(tr?.querySelectorAll('button') || [])].find((x) => x.title === 'Löschen')?.click();
  }, [GRUPPE]);
  await page.waitForTimeout(2500);
  if ((await text(page)).includes(GRUPPE)) fund('Gruppe ließ sich nicht löschen');
  else ok('Testgruppe wieder entfernt');

  // ── Abnahmebericht ────────────────────────────────────────────────────────
  const md = [`# Abnahme #1776–#1779 — ${TAG}`, '',
    `Basis: ${BASE} · Projekt: ${PROJEKT} · Firma: ${FIRMA}`, '',
    '## Bilder', ''];
  for (const b of bilder) {
    md.push(`### ${b.titel}`, '', `![${b.titel}](${b.datei})`, '',
            `**Zu sehen:** ${b.erwartung}`, '');
  }
  md.push('## Funde', '');
  md.push(funde.length ? funde.map((f) => `- ${f}`).join('\n') : '- keine');
  fs.writeFileSync(path.join(SHOTS, 'abnahme-1777.md'), md.join('\n'));
  console.log(`\n→ ${path.join(SHOTS, 'abnahme-1777.md')}`);
  console.log(funde.length ? `\n${funde.length} Fund(e)` : '\n0 Funde');

  await browser.close();
  process.exit(funde.length ? 1 : 0);
}

main().catch((e) => { console.error(`SETUP: ${e.message}`); process.exit(2); });
