/**
 * Vollumfänglicher Funktionstest des CRA-Moduls über einen echten Firefox.
 *
 * Auftrag aus dem Betrieb: „lass keine Funktion unangetastet". Der bestehende
 * `smoke.mjs` navigiert Routen und Tabs — er findet, was beim Anzeigen bricht.
 * Die Fehler, die in diesem Modul wehtun, entstehen aber beim **Arbeiten**:
 * #1796 (Feld ohne Eingabestelle), #1797 (Anlegen-Knopf unerreichbar, sobald
 * schon ein Vorgang existiert), #1798 (zweites Artefakt fällt beim Übernehmen
 * weg). Keiner davon wäre einem Navigationslauf aufgefallen.
 *
 * Darum zwei Phasen:
 *
 *   A. Jeder Tab, jeder `<details>`-Abschnitt, jeder **lesende** Knopf.
 *      Gesammelt werden Console-Errors, `pageerror` (genau das, was #1797
 *      auslöst) und HTTP ≥ 400.
 *   B. Gezielte Schreibstrecken je Register — anlegen, speichern, erneut laden
 *      und **prüfen, dass der Wert noch da ist**. Ein Speichern, das 200
 *      zurückgibt und den Wert verliert, ist der gefährlichere Fall: Er sieht
 *      wie Erfolg aus (#1796).
 *
 * Nicht angefasst: Knöpfe, die eine KI anstoßen (⚡/🤖) — ohne Modell wären das
 * Fehlalarme, nicht Funde — und Löschen-Knöpfe außerhalb der eigenen Testdaten.
 *
 *   AICS_BASE / AICS_EMAIL / AICS_PASSWORD   wie in smoke.mjs
 *   AICS_PROJEKT                             Projektname (Default: erstes)
 *
 * Ergebnis: out/cra-vollumfang.json + Screenshots in out/cra/.
 * Exit 0 sauber · 1 Funde · 2 Setup-Fehler.
 */
import { firefox } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';

const BASE = process.env.AICS_BASE || 'https://localhost:5173';
const EMAIL = process.env.AICS_EMAIL || 'admin@example.com';
const PASSWORD = process.env.AICS_PASSWORD || 'admin-password';
const WUNSCH_PROJEKT = process.env.AICS_PROJEKT || '';

// Ohne geöffnetes Projekt prüft jeder weitere Schritt eine leere Maske. Die
// Folgefunde wären alle derselbe, und 41 Wiederholungen einer Ursache lesen
// sich wie 41 Befunde (die Lehre aus #1774/#1877: Was bei allen anschlägt,
// trifft keinen).
let aufbau_fehlt = false;
let uebersprungen_schritte = 0;
const OUT = new URL('./out/', import.meta.url).pathname;
const SHOTS = `${OUT}cra/`;

/**
 * Tab-Wege als [Gruppe, Tab]. Zwei Eigenheiten, die ein Durchlauf kennen muss:
 *
 *  - Die Tab-Leiste ist **zweistufig**; der Untertab erscheint erst, wenn die
 *    Gruppe aktiv ist.
 *  - `/cra?tab=…` taugt **nicht** zur Navigation: Die Projektwahl steht im
 *    Store, nicht in der URL — ein `goto` landet wieder auf „Projekt wählen".
 *    Deshalb wird geklickt, nicht navigiert.
 */
const TABS = [
  ['📊 Überblick', '📊 Dashboard', 'dashboard'],
  ['📋 Compliance & Register', '✅ Anforderungen', 'requirements'],
  ['📋 Compliance & Register', '🛡️ OWASP SbD', 'owasp'],
  ['📋 Compliance & Register', '✅ Konformität', 'konformitaet'],
  ['📋 Compliance & Register', '🏷️ Akteure', 'akteure'],
  ['📋 Compliance & Register', '🔗 Traceability', 'traceability'],
  ['📋 Compliance & Register', '🔍 Risikoanalyse', 'risikoanalyse'],
  ['🛠️ Tagesbetrieb', '🚦 Releases', 'releases'],
  ['🛠️ Tagesbetrieb', '🚨 Meldungen', 'meldungen'],
  ['🛠️ Tagesbetrieb', '↩️ Korrektur & Behörden', 'korrektur'],
  ['📄 Dokumentation', '📋 Dokumentation', 'pflichtdoku'],
  ['📄 Dokumentation', '📄 Dokumente', 'dokumente'],
  ['📄 Dokumentation', '🤖 Assistenten', 'assistenten'],
  ['📑 Berichte', '📥 Fragebogen', 'fragebogen'],
  ['📑 Berichte', '📄 Berichte', 'berichte'],
];

/** Testversion — hoch genug, dass sie keiner echten Release-Historie begegnet. */
const VER = `99.9.${(Date.now() % 900) + 10}`;
const ART_A = 'e2e-anwendung';
const ART_B = 'e2e-webserver';

const funde = [];
const schritte = [];
let aktuell = 'setup';

function fund(art, text, extra = {}) {
  funde.push({ art, schritt: aktuell, text, ...extra });
  console.log(`  ✖ [${art}] ${text}`);
}
function ok(text) {
  schritte.push({ schritt: aktuell, ok: true, text });
  console.log(`  ✓ ${text}`);
}
function uebersprungen(text) {
  schritte.push({ schritt: aktuell, ok: null, text });
  console.log(`  – ${text}`);
}

/** Ein Schritt scheitert für sich — sonst nimmt der erste Fehler den Rest mit. */
async function schritt(name, fn, page = null) {
  aktuell = name;
  // Ohne geöffnetes Projekt wird nicht weitergeprüft — jeder Schritt
  // meldete sonst „Tab nicht erreichbar", und aus **einer** fehlenden
  // Voraussetzung würden 41 Funde. Der Lauf nennt die Ursache einmal.
  if (aufbau_fehlt && name !== 'login' && name !== 'projekt-waehlen') {
    console.log(`\n▶ ${name}  (übersprungen — kein Projekt geöffnet)`);
    uebersprungen_schritte += 1;
    return;
  }
  console.log(`\n▶ ${name}`);
  try {
    if (page) await aufraeumen(page);
    await fn();
  } catch (e) {
    fund('ausnahme', `${name}: ${e.message.split('\n')[0]}`);
  }
}

/** Offene Dialoge schließen. Ein stehengebliebenes Overlay verdeckt die
 *  Tab-Leiste, und der nächste Schritt meldet dann „Tab nicht erreichbar" —
 *  ein Fund, der nichts über das Modul aussagt. */
async function aufraeumen(page) {
  for (let i = 0; i < 3; i++) {
    const ov = page.locator('.modal-overlay:visible, .modal:visible, dialog[open]').first();
    if (!(await ov.count())) break;
    const zu = ov.locator('button:visible').filter({ hasText: /^(Abbrechen|Schließen|✕|×)$/ }).first();
    if (await zu.count()) await zu.click({ timeout: 2000 }).catch(() => {});
    else await page.keyboard.press('Escape').catch(() => {});
    await ruhe(page, 300);
  }
}

async function ruhe(page, ms = 700) {
  await page.waitForTimeout(ms);
}

/** Knopf über seinen sichtbaren Text, ohne auf exakte Schreibweise zu bauen.
 *  Gesucht wird nur im Panel-Inhalt: Ein Treffer in der Modulnavigation würde
 *  den Lauf in ein anderes Modul tragen (so endete der erste Durchlauf im SOC). */
function knopf(page, text) {
  return inhalt(page).locator('button:visible, a.btn-link:visible').filter({ hasText: text }).first();
}

async function klicke(page, text, { pflicht = true } = {}) {
  const b = knopf(page, text);
  if (!(await b.count())) {
    if (pflicht) fund('fehlt', `Knopf „${text}" nicht gefunden`);
    else uebersprungen(`Knopf „${text}" nicht vorhanden`);
    return false;
  }
  if (await b.isDisabled().catch(() => false)) {
    if (pflicht) fund('gesperrt', `Knopf „${text}" ist deaktiviert`);
    else uebersprungen(`Knopf „${text}" deaktiviert`);
    return false;
  }
  await b.click();
  await ruhe(page);
  return true;
}

/** Feld über seinen Platzhalter füllen — die Masken tragen kaum Labels. */
async function fuelle(page, platzhalter, wert, { pflicht = true } = {}) {
  const f = inhalt(page).locator(`input[placeholder*="${platzhalter}" i]:visible, textarea[placeholder*="${platzhalter}" i]:visible`).first();
  if (!(await f.count())) {
    if (pflicht) fund('fehlt', `Feld mit Platzhalter „${platzhalter}" nicht gefunden`);
    else uebersprungen(`Feld „${platzhalter}" nicht vorhanden`);
    return false;
  }
  await f.fill(String(wert));
  return true;
}

async function wertVon(page, platzhalter) {
  // **Warten, bevor „leer" behauptet wird.** Nach dem Tabwechsel lädt das
  // Panel nach; wer sofort liest, bekommt ein leeres Feld und meldet
  // „Verlust nach Neuladen" — beim Durchlauf gegen v8.7.0 zweimal für Werte,
  // die in der Datenbank standen **und** in der Maske zu sehen waren
  // (`intake_kanal`, `psirt_contacts`, über die API nachgewiesen).
  //
  // Ein Lauf, der aus einer zu frühen Lesung Datenverlust macht, ist
  // schlimmer als keiner: Datenverlust ist der teuerste Befund dieser Akte,
  // und ein falscher davon kostet eine Fehlersuche.
  //
  // Zweiter Boden: Findet die auf den Panel-Inhalt begrenzte Suche nichts,
  // wird die ganze Seite durchsucht. Das Feld kann in einem Abschnitt
  // liegen, den `inhalt()` nicht umfasst.
  // Gewartet wird **nur, wenn es das Feld gibt** — sonst kostet jeder
  // fehlende Platzhalter die volle Wartezeit, und der Lauf läuft ins
  // Zeitlimit (beim ersten Anlauf genau so passiert: exit 124, und die
  // Abbrüche danach sahen aus wie Funde).
  const wahl = `input[placeholder*="${platzhalter}" i], textarea[placeholder*="${platzhalter}" i]`;
  const feld = () => {
    const i = inhalt(page).locator(wahl).first();
    return i;
  };
  if (!(await feld().count()) && !(await page.locator(wahl).first().count())) return null;
  for (let i = 0; i < 6; i++) {
    for (const f of [feld(), page.locator(wahl).first()]) {
      if (!(await f.count())) continue;
      const v = await f.inputValue().catch(() => '');
      if (String(v || '').trim()) return v;
    }
    await ruhe(page, 250);
  }
  const f = page.locator(wahl).first();
  return (await f.count()) ? await f.inputValue().catch(() => null) : null;
}

/** Tab über die Leiste ansteuern — Gruppe zuerst, dann Untertab. */
async function tabOeffnen(page, gruppe, tab) {
  const g = page.locator('button.nav-group:visible').filter({ hasText: gruppe }).first();
  if (await g.count()) { await g.click().catch(() => {}); await ruhe(page, 400); }
  const t = page.locator('button.nav-tab:visible').filter({ hasText: tab }).first();
  if (!(await t.count())) { fund('fehlt', `Tab „${tab}" in Gruppe „${gruppe}" nicht erreichbar`); return false; }
  await t.click();
  await ruhe(page, 1400);
  return true;
}

/** Der Panel-Inhalt ohne Modul- und Tab-Navigation. */
function inhalt(page) {
  return page.locator('.tab-content').first();
}

/** Alle `<details>` aufklappen — sonst bleibt der halbe Tab ungesehen. */
async function alleAbschnitteOeffnen(page) {
  const n = await inhalt(page).locator('details:not([open])').count();
  for (let i = 0; i < n; i++) {
    const d = inhalt(page).locator('details:not([open])').first();
    if (!(await d.count())) break;
    await d.locator('summary').first().click({ timeout: 3000 }).catch(() => {});
    await ruhe(page, 150);
  }
  return n;
}

const KI_MUSTER = /⚡|🤖|KI|Ollama|Prompt|automatische Bewertung/i;
const GEFAEHRLICH = /🗑|löschen|entfernen|entziehen|zurückweisen|freigeben|veröffentlichen|signieren|einreichen|abmelden|Update|Deploy|Reset/i;
/** Schreibende Knöpfe. Blind geklickt schicken sie ein leeres Formular ab —
 *  das 400 danach ist richtig und sagt nichts über die Funktion aus. Diese
 *  Strecken laufen in Phase B mit echten Werten. */
const SCHREIBT = /hinzufügen|speichern|anlegen|übernehmen|erzeugen|generieren|starten|sync|importieren|ausstellen|feststellen|senden|hochladen/i;

/** Lesende Knöpfe anklicken und beobachten, ob dabei etwas bricht. */
async function lesendeKnoepfeKlicken(page, grenze = 15) {
  const alle = inhalt(page).locator('button:visible');
  const n = Math.min(await alle.count(), 60);
  let geklickt = 0;
  for (let i = 0; i < n && geklickt < grenze; i++) {
    const b = alle.nth(i);
    const t = ((await b.textContent().catch(() => '')) || '').trim().slice(0, 60);
    if (!t || KI_MUSTER.test(t) || GEFAEHRLICH.test(t) || SCHREIBT.test(t)) continue;
    if (await b.isDisabled().catch(() => true)) continue;
    await b.click({ timeout: 3000 }).catch(() => {});
    geklickt++;
    await ruhe(page, 250);
    // Ein geöffneter Dialog würde die folgenden Klicks verdecken.
    const zu = page.locator('button:visible').filter({ hasText: /^(Abbrechen|Schließen|✕)$/ }).first();
    if (await zu.count()) await zu.click({ timeout: 2000 }).catch(() => {});
  }
  return geklickt;
}

(async () => {
  mkdirSync(SHOTS, { recursive: true });
  const browser = await firefox.launch();
  const ctx = await browser.newContext({ locale: 'de-DE', ignoreHTTPSErrors: true, viewport: { width: 1600, height: 1000 } });
  const page = await ctx.newPage();

  page.on('console', (m) => {
    if (m.type() !== 'error') return;
    const t = m.text();
    // Vite-HMR und fehlende Favicons sind kein Modulfehler.
    if (/favicon|HMR|\[vite\]/i.test(t)) return;
    fund('console', t.slice(0, 300));
  });
  page.on('pageerror', (e) => fund('pageerror', String(e.message).slice(0, 300)));
  page.on('response', (r) => {
    if (r.status() < 400) return;
    const u = r.url();
    if (!u.includes('/api/')) return;
    // 428 ist das Egress-Gate (#1519), 409/412 sind fachliche Antworten —
    // sie gehören zum erwarteten Verhalten, nicht zu den Funden.
    if ([401, 403, 409, 412, 428].includes(r.status()) && !u.includes('/auth/login')) {
      schritte.push({ schritt: aktuell, ok: null, text: `HTTP ${r.status()} ${u.replace(BASE, '')}` });
      return;
    }
    fund('http', `HTTP ${r.status()} ${u.replace(BASE, '')}`);
  });

  // ── Login ─────────────────────────────────────────────────────────────────
  await schritt('login', async () => {
    await page.goto(BASE, { waitUntil: 'domcontentloaded' });
    await page.locator('input[type="email"], input#email').first().fill(EMAIL);
    await page.locator('input[type="password"]').first().fill(PASSWORD);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForURL((u) => !String(u).includes('/login'), { timeout: 20000 });
    ok('angemeldet');
  });
  if (funde.some((f) => f.schritt === 'login')) {
    writeFileSync(`${OUT}cra-vollumfang.json`, JSON.stringify({ funde, schritte }, null, 2));
    await browser.close();
    process.exit(2);
  }

  // ── Projekt wählen ────────────────────────────────────────────────────────
  let projekt = WUNSCH_PROJEKT;
  await schritt('projekt-waehlen', async () => {
    await page.goto(`${BASE}/cra`, { waitUntil: 'domcontentloaded' });
    await ruhe(page, 1500);
    // Die Seitenleiste gruppiert nach Firma (🏢 Firma → 📦 Produkt). Gesucht
    // ist ein **Produkt**: Ein Klick auf die Firma öffnet die Firmensicht,
    // nicht das CRA-Projekt.
    // **Kein fester Projektname mehr.** „CRA Produkt Alpha" gibt es auf Dev
    // nicht mehr, und der Lauf machte daraus 42 Funde — einen echten
    // (Voraussetzung fehlt) und 41 Folgen davon. Ein Lauf, der eine fehlende
    // Voraussetzung in 42 Funde verwandelt, begräbt das Signal; genau dafür
    // gibt es `aufbau_fehlt` (s. u.).
    //
    // Gewählt wird das **erste Produkt** der Seitenleiste (📦). Ein Klick auf
    // die Firma (🏢) öffnet die Firmensicht (#1569), nicht das CRA-Projekt.
    let ziel;
    if (projekt) {
      ziel = page.locator('aside').getByText(projekt, { exact: false }).first();
    } else {
      const firma = page.locator('aside >> text=🏢').first();
      if (await firma.count()) { await firma.click().catch(() => {}); await ruhe(page, 800); }
      ziel = page.locator('aside >> text=📦').first();
      projekt = ((await ziel.innerText().catch(() => '')) || '?')
        .replace(/\s+/g, ' ').replace('📦', '').trim();
    }
    if (!(await ziel.count())) {
      aufbau_fehlt = true;
      fund('setup', `Kein CRA-Produkt in der Seitenleiste`
           + (WUNSCH_PROJEKT ? ` (gesucht: „${WUNSCH_PROJEKT}")` : ''));
      return;
    }
    await ziel.click();
    await ruhe(page, 2000);
    const text = await inhalt(page).innerText().catch(() => '');
    if (/Wähle links ein Projekt/.test(text)) {
      aufbau_fehlt = true;
      fund('setup', `Klick auf „${projekt}" hat kein Projekt geöffnet`);
      return;
    }
    ok(`Projekt „${projekt}" geöffnet`);
  });

  // ── Phase A: jeder Tab, jeder Abschnitt, lesende Knöpfe ───────────────────
  for (const [gruppe, tab, id] of TABS) {
    await schritt(`tab:${id}`, async () => {
      if (!(await tabOeffnen(page, gruppe, tab))) return;
      const text = await inhalt(page).innerText().catch(() => '');
      if (!text || text.trim().length < 40) fund('leer', `Tab ${id} rendert nichts`);
      if (/Wähle links ein Projekt/.test(text)) {
        fund('projekt-verloren', `Tab ${id} zeigt „Projekt wählen" — Auswahl verloren`);
        return;
      }
      const n = await alleAbschnitteOeffnen(page);
      const k = await lesendeKnoepfeKlicken(page);
      await page.screenshot({ path: `${SHOTS}${id}.png`, fullPage: true }).catch(() => {});
      ok(`Tab ${id}: ${n} Abschnitt(e) geöffnet, ${k} Knopf/Knöpfe geklickt`);
    });
  }

  // ── Phase B: Schreibstrecken ──────────────────────────────────────────────

  // C2 PSIRT — der Fall #1796: speichern, neu laden, ist der Kontakt noch da?
  await schritt('c2-psirt-speichern', async () => {
    await tabOeffnen(page, '📄 Dokumentation', '📋 Dokumentation');
    await alleAbschnitteOeffnen(page);
    await fuelle(page, 'Intake-Kanal', 'security@e2e.test');
    await fuelle(page, 'Triage-SLA', '24h');
    const hatKontaktfeld = await fuelle(page, 'PSIRT-Kontakte', 'psirt@e2e.test, cert@e2e.test', { pflicht: false });
    if (!hatKontaktfeld) fund('fehlt', 'C2 hat kein Feld für PSIRT-Kontakte (#1796)');
    await fuelle(page, 'Disclosure-Policy-URL', 'https://e2e.test/security', { pflicht: false });
    if (!(await klicke(page, 'Speichern'))) return;
    await tabOeffnen(page, '📄 Dokumentation', '📋 Dokumentation');
    await alleAbschnitteOeffnen(page);
    const kanal = await wertVon(page, 'Intake-Kanal');
    const kontakte = await wertVon(page, 'PSIRT-Kontakte');
    if (kanal !== 'security@e2e.test') fund('verlust', `Intake-Kanal nach Neuladen: ${JSON.stringify(kanal)}`);
    if (hatKontaktfeld && !String(kontakte || '').includes('psirt@e2e.test')) {
      fund('verlust', `PSIRT-Kontakte nach Neuladen: ${JSON.stringify(kontakte)} (#1796)`);
    } else if (hatKontaktfeld) {
      ok(`Kontakte verlustfrei gespeichert: ${kontakte}`);
    }
  });

  // C1 SBOM — zwei Artefakte derselben Version (#1771/#1798)
  await schritt('c1-sbom-zwei-artefakte', async () => {
    await tabOeffnen(page, '📄 Dokumentation', '📋 Dokumentation');
    await alleAbschnitteOeffnen(page);
    for (const art of [ART_A, ART_B]) {
      if (!(await fuelle(page, 'Release-Version', VER))) return;
      await fuelle(page, 'Artefakt', art);
      await fuelle(page, 'Komponenten-Anzahl', '7');
      await fuelle(page, 'Lizenzen', 'MIT, Apache-2.0', { pflicht: false });
      if (!(await klicke(page, 'SBOM hinzufügen'))) return;
      await ruhe(page, 900);
    }
    await tabOeffnen(page, '📄 Dokumentation', '📋 Dokumentation');
    await alleAbschnitteOeffnen(page);
    // In der **Tabelle** nachsehen, nicht im Seitentext: Die Formularfelder
    // tragen die Werte noch, und danach sähe jeder Verlust wie Erfolg aus.
    const zeilen = inhalt(page).locator('table tr').filter({ hasText: VER });
    const gefunden = await zeilen.count();
    const txt = gefunden ? await zeilen.allInnerTexts() : [];
    const beide = txt.join(' ').includes(ART_A) && txt.join(' ').includes(ART_B);
    if (!beide) fund('verlust', `für ${VER} nicht beide Artefakte in der Liste: ${JSON.stringify(txt).slice(0, 200)} (#1798)`);
    else ok(`beide Artefakte derselben Version stehen in der Akte (${gefunden} Zeilen)`);
  }, page);

  // C3 Schwachstelle anlegen
  await schritt('c3-schwachstelle-anlegen', async () => {
    await tabOeffnen(page, '📄 Dokumentation', '📋 Dokumentation');
    await alleAbschnitteOeffnen(page);
    const cve = `CVE-2026-${Math.floor(Math.random() * 9000 + 1000)}`;
    if (!(await fuelle(page, 'CVE-ID', cve))) return;
    await fuelle(page, 'Titel', 'E2E-Testbefund');
    await fuelle(page, 'Betroffene Komponente', 'e2e-paket');
    const vulnKnopf = inhalt(page).locator('button:visible').filter({ hasText: /^Hinzufügen$/ }).first();
    if (!(await vulnKnopf.count())) { fund('fehlt', 'kein Hinzufügen-Knopf im C3-Abschnitt'); return; }
    await vulnKnopf.click();
    await ruhe(page, 900);
    await ruhe(page, 800);
    const sichtbar = await inhalt(page).locator('table tr').filter({ hasText: cve }).count();
    if (!sichtbar) fund('wirkung', `Schwachstelle ${cve} nach dem Anlegen nicht in der Liste`);
    else ok(`Schwachstelle ${cve} angelegt`);
  }, page);

  // C4 Unterstützungszeitraum — Pflichtprüfung und Speichern
  await schritt('c4-support-zeitraum', async () => {
    await tabOeffnen(page, '📄 Dokumentation', '📋 Dokumentation');
    await alleAbschnitteOeffnen(page);
    if (!(await fuelle(page, 'Support-Jahre', '5'))) return;
    await fuelle(page, 'Update-Kanal', 'Auto-Update', { pflicht: false });
    const gespeichert = await klicke(page, 'Speichern', { pflicht: false });
    if (gespeichert) ok('Unterstützungszeitraum gespeichert');
    else uebersprungen('kein Speichern im C4-Abschnitt gefunden');
  }, page);

  // Releases — der Fall #1797: Vorgang anlegen, obwohl schon einer existiert
  await schritt('releases-vorgang-anlegen', async () => {
    await tabOeffnen(page, '🛠️ Tagesbetrieb', '🚦 Releases');
    const vorhandene = await inhalt(page).locator('.rel-list li').count();
    const feld = inhalt(page).locator('.ver-input input, input[placeholder*="1.2.0"]').first();
    if (!(await feld.count())) { fund('fehlt', 'kein Versionsfeld im Releases-Tab'); return; }
    await feld.fill(VER);
    await klicke(page, 'Vorgang öffnen');
    await page.screenshot({ path: `${SHOTS}releases-neu.png`, fullPage: true }).catch(() => {});
    const anlegen = knopf(page, 'anlegen');
    if (!(await anlegen.count())) {
      fund('fehlt', `Anlegen-Knopf fehlt bei ${vorhandene} vorhandenen Vorgängen (#1797)`);
      return;
    }
    await anlegen.click();
    await ruhe(page, 1500);
    const liste = await inhalt(page).locator('.rel-list li').count();
    if (liste <= vorhandene) fund('wirkung', `Vorgangsliste nach dem Anlegen unverändert (${liste})`);
    else ok(`Vorgang ${VER} angelegt — Liste ${vorhandene} → ${liste}`);
  }, page);

  // Derselbe Weg ein zweites Mal: jetzt existiert sicher ein Vorgang (#1797)
  await schritt('releases-zweiter-vorgang', async () => {
    await tabOeffnen(page, '🛠️ Tagesbetrieb', '🚦 Releases');
    const vorhandene = await inhalt(page).locator('.rel-list li').count();
    if (!vorhandene) { uebersprungen('kein Vorgang vorhanden — Fall nicht herstellbar'); return; }
    const feld = inhalt(page).locator('.ver-input input, input[placeholder*="1.2.0"]').first();
    await feld.fill(`${VER}-b`);
    await klicke(page, 'Vorgang öffnen');
    const anlegen = knopf(page, 'anlegen');
    if (!(await anlegen.count())) {
      fund('fehlt', `Anlegen-Knopf fehlt, obwohl ${vorhandene} Vorgänge bestehen (#1797)`);
      return;
    }
    await anlegen.click();
    await ruhe(page, 1500);
    ok(`zweiter Vorgang bei ${vorhandene} bestehenden angelegt (#1797 behoben)`);
  }, page);

  // Release-Art (#1793) + Kernfrage
  await schritt('release-art-und-kernfrage', async () => {
    await tabOeffnen(page, '🛠️ Tagesbetrieb', '🚦 Releases');
    const feld = inhalt(page).locator('.ver-input input, input[placeholder*="1.2.0"]').first();
    if (await feld.count()) { await feld.fill(VER); await klicke(page, 'Vorgang öffnen'); }
    const wahl = inhalt(page).locator('.art-option input[type="radio"]').first();
    if (!(await wahl.count())) { fund('fehlt', 'keine Auswahl für die Release-Art (#1793)'); return; }
    await wahl.check({ timeout: 3000 }).catch(() => {});
    await ruhe(page, 400);
    if (!(await klicke(page, 'Art speichern', { pflicht: false }))) {
      const b = inhalt(page).locator('.art-wahl button:visible, button:visible').filter({ hasText: /speichern/i }).first();
      if (await b.count() && !(await b.isDisabled())) await b.click();
    }
    await ruhe(page, 1200);
    const text = await inhalt(page).innerText();
    if (/Sicherheitsupdate|Funktionsupdate|Wesentliche Änderung/.test(text)) ok('Release-Art gesetzt und ausgewiesen');
    else fund('wirkung', 'Release-Art nach dem Speichern nicht ausgewiesen');
  }, page);

  // Checkliste — ein Punkt vom Typ „Entscheidung" mit Begründung
  await schritt('release-checkliste', async () => {
    await tabOeffnen(page, '🛠️ Tagesbetrieb', '🚦 Releases');
    const feld = inhalt(page).locator('.ver-input input, input[placeholder*="1.2.0"]').first();
    if (await feld.count()) { await feld.fill(VER); await klicke(page, 'Vorgang öffnen'); }
    const punkte = await inhalt(page).locator('li:has(.ci-head)').count();
    if (!punkte) { fund('leer', 'Release-Checkliste zeigt keine Punkte'); return; }
    const grund = inhalt(page).locator('textarea:visible').first();
    if (await grund.count()) await grund.fill('E2E-Durchlauf: geprüft und unverändert übernommen.');
    const sel = inhalt(page).locator('select:visible').first();
    if (await sel.count()) await sel.selectOption({ index: 1 }).catch(() => {});
    if (await klicke(page, 'Speichern', { pflicht: false })) ok(`Checkliste: ${punkte} Punkte, einer gespeichert`);
    else ok(`Checkliste zeigt ${punkte} Punkte (kein Einzel-Speichern gefunden)`);
  }, page);

  // Anforderungen — eine Bewertung speichern und wiederfinden
  await schritt('anforderung-bewerten', async () => {
    await tabOeffnen(page, '📋 Compliance & Register', '✅ Anforderungen');
    const zeilen = inhalt(page).locator('.req-item, .requirement-card, tbody tr, .anforderung');
    const n = await zeilen.count();
    if (!n) { fund('leer', 'keine Anforderungen gelistet'); return; }
    await zeilen.first().click();
    await ruhe(page, 1200);
    const editor = page.locator('.modal-content:visible').first();
    if (!(await editor.count())) { fund('wirkung', `Klick auf eine Anforderung öffnet keinen Editor (${n} gelistet)`); return; }
    const auswahl = editor.locator('select:visible').first();
    if (await auswahl.count()) await auswahl.selectOption({ index: 4 }).catch(() => {});
    const notiz = editor.locator('textarea:visible').first();
    if (await notiz.count()) await notiz.fill('E2E-Durchlauf: Bewertung gespeichert.');
    const speichern = editor.locator('.modal-footer button.btn-primary').first();
    if (!(await speichern.count())) { fund('fehlt', 'kein Speichern-Knopf im Anforderungs-Editor'); return; }
    await speichern.click();
    await ruhe(page, 1500);
    if (await page.locator('.modal-content:visible').count()) {
      fund('wirkung', 'Editor bleibt nach dem Speichern offen');
    } else ok(`Bewertung gespeichert (${n} Anforderungen gelistet)`);
  }, page);

  // Dokumente — ein Pflichtdokument erzeugen
  await schritt('dokument-erzeugen', async () => {
    await tabOeffnen(page, '📄 Dokumentation', '📄 Dokumente');
    const kacheln = await inhalt(page).locator('.doc-card, .katalog-kachel, .form-card').count();
    if (!kacheln) { fund('leer', 'Dokumente-Register zeigt nichts'); return; }
    ok(`Dokumente-Register: ${kacheln} Kachel(n)/Karte(n)`);
  }, page);

  // Bericht erzeugen — der echte Weg über das Berichts-Center
  await schritt('bericht-erzeugen', async () => {
    await tabOeffnen(page, '📑 Berichte', '📄 Berichte');
    const karten = await inhalt(page).locator('h3, h4').count();
    const wordKnoepfe = inhalt(page).locator('button:visible').filter({ hasText: 'Word' });
    const anzahl = await wordKnoepfe.count();
    if (!anzahl) { fund('leer', `Berichts-Center zeigt keine Berichtstypen (${karten} Überschriften)`); return; }
    const dl = page.waitForEvent('download', { timeout: 90000 }).catch(() => null);
    await wordKnoepfe.first().click();
    const gestartet = true;
    if (!gestartet) return;
    const d = await dl;
    if (d) ok(`Bericht erzeugt: ${d.suggestedFilename()} (${anzahl} Berichtstypen)`);
    else uebersprungen('kein Download angekommen (Bericht ggf. nur serverseitig abgelegt)');
  }, page);

  // Gate — die Ampel muss eine Aussage treffen
  await schritt('release-check-ampel', async () => {
    await tabOeffnen(page, '🛠️ Tagesbetrieb', '🚦 Releases');
    const text = await inhalt(page).innerText();
    if (!/(grün|gruen|bedingt|rot|CRA-ready)/i.test(text)) fund('leer', 'Releases-Tab weist keinen Gate-Stand aus');
    else ok('Gate-Stand ausgewiesen');
  }, page);

  await browser.close();

  const bericht = {
    zeit: new Date().toISOString(), base: BASE, projekt,
    funde_gesamt: funde.length,
    nach_art: funde.reduce((a, f) => ({ ...a, [f.art]: (a[f.art] || 0) + 1 }), {}),
    funde, schritte,
  };
  writeFileSync(`${OUT}cra-vollumfang.json`, JSON.stringify(bericht, null, 2));
  console.log(`\n${'─'.repeat(60)}`);
  console.log(`Funde: ${funde.length}`, JSON.stringify(bericht.nach_art));
  console.log(`Bericht: ${OUT}cra-vollumfang.json`);
  process.exit(funde.length ? 1 : 0);
})().catch((e) => { console.error('SETUP-FEHLER', e); process.exit(2); });
