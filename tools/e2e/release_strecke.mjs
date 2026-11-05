/**
 * Abnahme der Release-Strecke v8.0.0 über einen echten Firefox (#1750).
 *
 * Die Vorgabe war ausdrücklich: Deploy erst, wenn alle neuen Funktionen lokal
 * inklusive **Screenshot-Auswertung** geprüft sind. Ein grüner Playwright-Lauf
 * beweist, dass Elemente existieren — nicht, dass die Seite benutzbar ist.
 * Deshalb legt dieser Lauf je Schritt ein Bild ab und schreibt eine Übersicht
 * mit der Erwartung je Bild; die Bilder werden danach angesehen.
 *
 * Rücksicht auf eine laufende Sitzung: Alles **Schreibende** passiert in einem
 * eigenen Projekt (`E2E_PROJEKT`), das der Lauf selbst anlegt. Die Demo-Daten
 * einer parallelen Hand-Prüfung werden nur gelesen.
 *
 * ENV:
 *   AICS_BASE   Frontend-URL (Default https://127.0.0.1:5173)
 *   AICS_DEMO   Projekt für die lesenden Aufnahmen (Default s. u.)
 *   AICS_HEADED=1  Browser sichtbar
 *
 * Lauf:  node tools/e2e/release_strecke.mjs
 * Exit:  0 = alle Schritte erreicht, 1 = Funde, 2 = Setup-Fehler
 */
import { firefox } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE = process.env.AICS_BASE || 'https://127.0.0.1:5173';
const DEMO = process.env.AICS_DEMO || 'Cyberwoks Demo GmbH – Portalsoftware';
const E2E_FIRMA = 'E2E Abnahme GmbH';
const E2E_PROJEKT = 'E2E Abnahme GmbH – Testprodukt';
const HEADED = process.env.AICS_HEADED === '1';

const USER = {
  editor: ['editor@example.com', 'editor-password'],
  approver: ['approver@example.com', 'approver-password'],
  admin: ['admin@example.com', 'admin-password'],
};

const TAG = new Date().toISOString().slice(0, 10);
// Versionen je Lauf: Ein zweiter Durchlauf fände die Vorgänge des ersten
// bereits eingereicht oder freigegeben vor und meldete Fehler, die keine sind.
const LAUF = String(Date.now()).slice(-6);
const V_ENTWURF = `8.${LAUF}.0`;
const V_FREIGABE = `8.${LAUF}.1`;
const V_SELBST = `8.${LAUF}.2`;
const ROOT = path.dirname(new URL(import.meta.url).pathname);
const SHOTS = path.join(ROOT, 'screens', TAG);
fs.mkdirSync(SHOTS, { recursive: true });

const bilder = [];   // {datei, titel, erwartung}
const funde = [];    // Textbefunde (Konsolenfehler, HTTP >= 500, fehlende Elemente)
let n = 0;

async function shot(page, name, titel, erwartung) {
  const datei = `${String(++n).padStart(2, '0')}-${name}.png`;
  // Ganzseitig: Der geöffnete Vorgang liegt unterhalb des Sichtfelds, und
  // genau dort stehen die Dinge, die bewertet werden sollen.
  await page.screenshot({ path: path.join(SHOTS, datei), fullPage: true });
  bilder.push({ datei, titel, erwartung });
  console.log(`  📷 ${datei} — ${titel}`);
}

function fund(text) { funde.push(text); console.log(`  ⚠ ${text}`); }

/** Scrollt den **inneren** Scroll-Container ans Ende.
 *
 * Die App-Hülle scrollt nicht das Dokument, sondern einen Container darin.
 * Deshalb liefert `fullPage: true` nur den sichtbaren Ausschnitt und
 * `scrollIntoViewIfNeeded` greift ins Leere — der geöffnete Vorgang, also
 * genau das zu Bewertende, lag außerhalb jeder Aufnahme.
 */
async function zuText(page, muster) {
  /** Scrollt den inneren Container so, dass der erste Treffer oben steht. */
  const ok = await page.evaluate((m) => {
    const re = new RegExp(m, 'i');
    const treffer = [...document.querySelectorAll('h3, h4, .gruppe, .karte, section')]
      .find((el) => re.test(el.textContent || ''));
    if (!treffer) return false;
    treffer.scrollIntoView({ block: 'start' });
    return true;
  }, muster);
  await page.waitForTimeout(600);
  return ok;
}

async function nachUnten(page) {
  await page.evaluate(() => {
    let best = document.scrollingElement;
    let max = 0;
    for (const el of document.querySelectorAll('*')) {
      const d = el.scrollHeight - el.clientHeight;
      if (d > max && el.clientHeight > 200) { max = d; best = el; }
    }
    best.scrollTop = best.scrollHeight;
  });
  await page.waitForTimeout(600);
}

async function login(page, rolle) {
  const [email, pw] = USER[rolle];
  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(900);
  await page.locator('input[type=email], input[type=text]').first().fill(email);
  await page.locator('input[type=password]').first().fill(pw);
  await page.locator('button', { hasText: /Anmelden/i }).first().click();
  await page.waitForTimeout(2600);
  if (/\/login/.test(page.url())) throw new Error(`Login als ${rolle} fehlgeschlagen`);
  console.log(`  🔑 angemeldet als ${rolle}`);
}

async function logout(page) {
  await page.evaluate(() => { try { localStorage.clear(); sessionStorage.clear(); } catch (e) {} });
}

/** API-Aufruf aus dem Seiten-Kontext — nutzt das echte App-Token. */
async function api(page, methode, pfad, body) {
  return page.evaluate(async ([m, p, b]) => {
    // #1190: Das Token liegt in sessionStorage unter `auth_token`, nicht in
    // localStorage — ein falscher Schlüssel liefert lauter 401 und sieht aus
    // wie ein kaputtes Backend.
    const tok = sessionStorage.getItem('auth_token') || '';
    const r = await fetch(p, {
      method: m,
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${tok}` },
      body: b ? JSON.stringify(b) : undefined,
    });
    let d = null;
    try { d = await r.json(); } catch (e) { d = null; }
    return { status: r.status, data: d };
  }, [methode, pfad, body || null]);
}

/** Eigene Testdaten anlegen — nichts an den Demo-Daten anfassen. */
async function daten_vorbereiten(page) {
  const p = encodeURIComponent(E2E_PROJEKT);
  await api(page, 'POST', '/api/cra/projekte',
    { name: E2E_PROJEKT, unternehmen: E2E_FIRMA, produkt: 'Testprodukt' });
  // Zwei Vorgänge: einer bleibt Entwurf (Checkliste), einer wird eingereicht.
  for (const v of [V_ENTWURF, V_FREIGABE]) {
    const r = await api(page, 'POST', `/api/cra-konformitaet/projekte/${p}/releases/${v}`);
    if (r.status !== 200) fund(`Vorgang ${v} nicht angelegt: HTTP ${r.status}`);
  }
  await api(page, 'PUT', `/api/cra-konformitaet/projekte/${p}/konformitaet`,
    { bewertungsweg: 'A', bewertung_abgeschlossen: true, release_version: V_FREIGABE });
  console.log('  🧪 eigene Testdaten angelegt');
}

async function main() {
  const browser = await firefox.launch({ headless: !HEADED });
  const ctx = await browser.newContext({
    ignoreHTTPSErrors: true, viewport: { width: 1280, height: 900 },
  });
  const page = await ctx.newPage();

  page.on('console', (m) => {
    if (m.type() === 'error') fund(`Console-Error: ${m.text().slice(0, 160)}`);
  });
  page.on('pageerror', (e) => fund(`PageError: ${String(e).slice(0, 160)}`));
  page.on('response', (r) => {
    if (r.status() >= 500) fund(`HTTP ${r.status()} ${r.url().replace(BASE, '')}`);
  });

  // ── 1. Lesende Aufnahmen auf den Demo-Daten ──────────────────────────────
  await login(page, 'editor');
  await daten_vorbereiten(page);

  await page.goto(`${BASE}/cra?projekt=${encodeURIComponent(DEMO)}&tab=releases`,
    { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3200);

  await shot(page, 'nav-tagesbetrieb', 'Gruppen-Navigation mit „🚦 Releases"',
    'Der Tab steht in der Gruppe „🛠️ Tagesbetrieb", nicht in „Compliance & Register". '
    + 'Tab-Leiste bricht bei 1280 px nicht um.');

  const phase1 = page.locator('text=/CRA-ready/i').first();
  if (!(await phase1.count())) fund('Phase-1-Zeile nicht gefunden');
  await shot(page, 'phase1-zeile', 'Phase 1 als eine Zeile',
    'Ampel, Status und Aktion in EINER Zeile; kein Umbruch, keine zweite Zeile.');

  await shot(page, 'release-liste', 'Release-Liste mit Status-Pillen',
    'Fünf Vorgänge mit unterscheidbaren Pillen: veröffentlicht, freigegeben, '
    + 'zurückgewiesen, in Prüfung, Entwurf. Zurückweisungsgrund sichtbar.');

  // Vorgang öffnen (zweiter Eintrag = 2.0.0 freigegeben, laut Seed)
  // Über den Deep-Link statt über den Klick: Der Sprung aus Bericht und
  // Firmen-Dashboard nutzt genau diesen Weg, er ist also der Prüfgegenstand.
  await page.goto(`${BASE}/cra?projekt=${encodeURIComponent(DEMO)}&tab=releases&version=1.9.0`,
    { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
  if (!(await zuText(page, 'gerechnet'))) fund('Deep-Link öffnet den Vorgang nicht');
  await nachUnten(page);
  await shot(page, 'detail-drei-arten', 'Checkliste in drei Arten',
    'Drei Gruppen mit Überschrift und Badge („🔒 gerechnet", „✍️ Entscheidung", '
    + '„♻️ unverändert"), ohne Legende unterscheidbar. Gerechnete Punkte ohne Eingabefeld.');

  // ── 2. Schreibende Schritte im eigenen Projekt ───────────────────────────
  const E = encodeURIComponent(E2E_PROJEKT);
  await page.goto(`${BASE}/cra?projekt=${E}&tab=releases&version=${V_ENTWURF}`,
    { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
  await nachUnten(page);
  await shot(page, 'eigener-vorgang', 'Eigener Vorgang 4.0.0 (Entwurf)',
    'Entwurf mit bedienbarer Checkliste; Freigabe-Schaltflächen fehlen (Editor).');

  // Entscheidung ohne Begründung → Backend-Klartext muss erscheinen
  const r1 = await api(page, 'PUT',
    `/api/cra-konformitaet/projekte/${E}/releases/${V_ENTWURF}/checkliste/release_notes_veroeffentlicht`,
    { status: 'erledigt', begruendung: 'kurz' });
  if (r1.status !== 409) fund(`Entscheidung ohne Begründung: HTTP ${r1.status}, erwartet 409`);
  else console.log(`  ✓ 409: ${String(r1.data?.error).slice(0, 80)}…`);

  // Gerechneter Punkt nicht setzbar
  const r2 = await api(page, 'PUT',
    `/api/cra-konformitaet/projekte/${E}/releases/${V_ENTWURF}/checkliste/advisory_zu_behobenen`,
    { status: 'erledigt', begruendung: 'zwanzig Zeichen und mehr' });
  if (r2.status !== 409) fund(`gerechneter Punkt setzbar: HTTP ${r2.status}, erwartet 409`);

  // Editor darf nicht freigeben
  const r3 = await api(page, 'POST',
    `/api/cra-konformitaet/projekte/${E}/konformitaet/freigeben`, { release_version: V_FREIGABE });
  if (r3.status !== 403) fund(`Editor konnte freigeben: HTTP ${r3.status}, erwartet 403`);

  // Einreichen als Editor
  const r4 = await api(page, 'POST',
    `/api/cra-konformitaet/projekte/${E}/releases/${V_FREIGABE}/einreichen`);
  if (r4.status !== 200) fund(`Einreichen fehlgeschlagen: HTTP ${r4.status} ${JSON.stringify(r4.data).slice(0, 120)}`);

  await page.goto(`${BASE}/cra?projekt=${E}&tab=releases&version=${V_FREIGABE}`,
    { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2800);
  if (await zuText(page, 'gerechnet')) {
    await shot(page, 'checkliste-arten', 'Checkliste: die drei Arten im Vorgang',
      'Drei Gruppen mit Überschrift und Badge; gerechnete Punkte ohne Eingabefeld, '
      + 'Entscheidungen mit Begründungsfeld, gleichbleibende mit Bestätigung.');
  } else {
    fund('Checklisten-Gruppe „gerechnet" nicht gefunden');
  }
  await nachUnten(page);
  await shot(page, 'editor-ohne-freigabe', 'Eingereicht, Sicht des Editors',
    'Status „in Prüfung", Hinweis auf die Prüfung durch Compliance; KEINE '
    + 'Freigabe-/Zurückweisungs-Schaltflächen, keine Eingabefelder (gesperrt).');

  // Vorgangsbericht
  const ber = await page.evaluate(async ([p]) => {
    const tok = sessionStorage.getItem('auth_token') || '';
    const r = await fetch(`/api/cra/projekte/${p}/berichte/release?format=docx&version=${V_FREIGABE}`,
      { headers: { Authorization: `Bearer ${tok}` } });
    const b = await r.blob();
    return { status: r.status, size: b.size };
  }, [E]);
  if (ber.status !== 200 || ber.size < 5000) fund(`Vorgangsbericht: HTTP ${ber.status}, ${ber.size} Bytes`);
  else console.log(`  ✓ Vorgangsbericht ${ber.size} Bytes`);

  // Dashboard-KPI
  await page.goto(`${BASE}/cra?projekt=${E}&tab=dashboard`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2600);
  await shot(page, 'dashboard-kpi', 'Dashboard mit KPI „Releases in Prüfung"',
    'Zusätzliche Kachel neben den bestehenden; Zahl 1 (der eingereichte Vorgang).');

  // ── 3. Rolle Compliance ──────────────────────────────────────────────────
  await logout(page);
  await login(page, 'approver');
  await page.goto(`${BASE}/cra?projekt=${E}&tab=releases&version=${V_FREIGABE}`,
    { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
  await nachUnten(page);
  await shot(page, 'approver-sicht', 'Sicht der Compliance (cra_approver)',
    'Freigeben und Zurückweisen sichtbar; KEINE Eingabefelder in der Checkliste.');

  const r5 = await api(page, 'PUT',
    `/api/cra-konformitaet/projekte/${E}/releases/${V_FREIGABE}/checkliste/support_zeitraum`,
    { status: 'erledigt', begruendung: '' });
  if (r5.status !== 403) fund(`Approver konnte schreiben: HTTP ${r5.status}, erwartet 403`);

  const r6 = await api(page, 'POST',
    `/api/cra-konformitaet/projekte/${E}/konformitaet/freigeben`, { release_version: V_FREIGABE });
  if (r6.status !== 200) fund(`Freigabe fehlgeschlagen: HTTP ${r6.status} ${JSON.stringify(r6.data).slice(0, 140)}`);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2600);
  await nachUnten(page);
  await shot(page, 'freigegeben', 'Freigegeben durch zweite Person',
    'Status „freigegeben", Prüfer/Freigeber mit Zeitstempel sichtbar.');

  // ── 4. Selbstfreigabe: der Kern der Vier-Augen-Prüfung ───────────────────
  await logout(page);
  await login(page, 'admin');
  const E2 = E;
  await api(page, 'POST', `/api/cra-konformitaet/projekte/${E2}/releases/${V_SELBST}`);
  await api(page, 'PUT', `/api/cra-konformitaet/projekte/${E2}/konformitaet`,
    { bewertungsweg: 'A', bewertung_abgeschlossen: true, release_version: '4.2.0' });
  await api(page, 'POST', `/api/cra-konformitaet/projekte/${E2}/releases/${V_SELBST}/einreichen`);
  const r7 = await api(page, 'POST',
    `/api/cra-konformitaet/projekte/${E2}/konformitaet/freigeben`, { release_version: V_SELBST });
  if (r7.status !== 409 || !/zweite Person/i.test(String(r7.data?.error))) {
    fund(`Selbstfreigabe nicht abgewiesen: HTTP ${r7.status} ${JSON.stringify(r7.data).slice(0, 140)}`);
  } else {
    console.log(`  ✓ 409: ${String(r7.data.error).slice(0, 90)}…`);
  }
  await page.goto(`${BASE}/cra?projekt=${E2}&tab=releases&version=${V_SELBST}`,
    { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2800);
  await nachUnten(page);
  await shot(page, 'admin-selbstfreigabe', 'Admin: eigener Vorgang, Freigabe sichtbar',
    'Admin hat beide Rechte und sieht die Schaltfläche — die Freigabe wird aber '
    + 'mit „Wer einreicht, darf nicht freigeben" abgewiesen. Beide Rollen genügen nicht.');

  // ── 5. Quer-Sicht je Mandant ─────────────────────────────────────────────
  await page.goto(`${BASE}/firmen`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
  await shot(page, 'mandanten-uebersicht', 'Mandanten-Übersicht mit Spalte „Releases offen"',
    'Spalte vorhanden; „—" bei Mandanten ohne CRA-Projekt, Zahl sonst.');

  const firmaLink = page.locator(`text=${E2E_FIRMA}`).first();
  if (await firmaLink.count()) {
    try { await firmaLink.click({ timeout: 2500 }); await page.waitForTimeout(3000); } catch (e) {}
  }
  await nachUnten(page);
  await shot(page, 'firma-releases', 'Firmen-Dashboard: Abschnitt „🚦 Releases"',
    'Je Produkt eine Kachel mit CRA-Ready-Badge und Vorgangs-Liste; Zahlen gleich '
    + 'wie im Modul.');

  // ── 6. Vorlagen-Fehlermeldung (#1741) ────────────────────────────────────
  const r8 = await api(page, 'GET',
    `/api/cra/projekte/${E2}/berichte/gesamt?format=docx&template_id=999999`);
  if (r8.status !== 404 && r8.status !== 422) {
    fund(`unbekannte template_id: HTTP ${r8.status}, erwartet 404/422`);
  } else {
    console.log(`  ✓ HTTP ${r8.status}: ${String(r8.data?.error).slice(0, 90)}`);
  }

  await browser.close();

  // ── Übersicht schreiben ──────────────────────────────────────────────────
  const md = [
    `# Abnahme Release-Strecke v8.0.0 — ${TAG}`,
    '',
    'Erzeugt von `tools/e2e/release_strecke.mjs` (Firefox/Playwright, 1280×900).',
    'Die Bilder sind **anzusehen**: geprüft wird auf Überlauf, abgeschnittene',
    'Beschriftungen, Umbrüche und darauf, dass Ampelfarben zum Text passen.',
    '',
    '| # | Bild | Erwartung |',
    '|---|---|---|',
    ...bilder.map((b, i) => `| ${i + 1} | \`${b.datei}\` — ${b.titel} | ${b.erwartung} |`),
    '',
    `## Befunde des Laufs (${funde.length})`,
    '',
    ...(funde.length ? funde.map((f) => `- ${f}`) : ['- keine']),
  ].join('\n');
  fs.writeFileSync(path.join(SHOTS, 'INDEX.md'), md);
  console.log(`\n${bilder.length} Bilder in ${SHOTS}`);
  console.log(`Befunde: ${funde.length}`);
  return funde.length ? 1 : 0;
}

main().then((c) => process.exit(c)).catch((e) => {
  console.error('SETUP-FEHLER:', e);
  process.exit(2);
});
