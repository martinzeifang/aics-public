/**
 * Etappe 2 — die Regeln, nicht die Oberflächen.
 *
 * Geprüft wird über die REST-Schnittstelle, weil es hier um Zusagen geht, die
 * die Anwendung einhalten muss, egal wer sie aufruft: Wer darf was, was
 * verhindert eine Freigabe, was rechnet das Gate, welche Pflichtangaben sind
 * wirklich Pflicht. Ein Klick-Test zeigt, ob ein Knopf da ist; diese Prüfungen
 * zeigen, ob die Regel dahinter trägt.
 *
 * Jede Prüfung nennt ihre Erwartung im Klartext. Weicht die Anwendung ab, ist
 * das ein Fund mit genau der Information, die in ein Issue gehört — nicht
 * „geht nicht", sondern „erwartet 409, bekam 200".
 *
 * ENV: AICS_BASE · Konten aus ~/Downloads/aics-dev-zugangsdaten.md
 * Lauf: node tools/e2e/logikpruefung.mjs
 */
import { writeFileSync, readFileSync, mkdirSync } from 'node:fs';
import { request as https } from 'node:https';

const BASE = process.env.AICS_BASE || 'https://aics-dev.290985.intern:8444';
const OUT = new URL('./out/', import.meta.url).pathname;

const funde = [];
const geprueft = [];
let bereich = '';

function fund(text, erwartet, bekommen, extra = {}) {
  funde.push({ bereich, text, erwartet, bekommen, ...extra });
  console.log(`  ✖ ${text}\n      erwartet: ${erwartet}\n      bekommen: ${bekommen}`);
}
function ok(text) { geprueft.push({ bereich, text }); console.log(`  ✔ ${text}`); }

/** Minimaler HTTPS-Client — self-signed Zertifikate sind hier normal. */
function ruf(pfad, { methode = 'GET', token = '', daten = null } = {}) {
  return new Promise((fertig) => {
    const url = new URL(pfad.startsWith('http') ? pfad : BASE + pfad);
    const body = daten === null ? null : JSON.stringify(daten);
    const req = https({
      hostname: url.hostname, port: url.port, path: url.pathname + url.search,
      method: methode, rejectUnauthorized: false,
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(body ? { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) } : {}),
      },
    }, (res) => {
      let roh = '';
      res.on('data', (c) => { roh += c; });
      res.on('end', () => {
        let j = null;
        try { j = JSON.parse(roh); } catch { /* kein JSON */ }
        fertig({ status: res.statusCode, json: j, text: roh.slice(0, 400) });
      });
    });
    req.on('error', (e) => fertig({ status: 0, json: null, text: String(e.message) }));
    if (body) req.write(body);
    req.end();
  });
}

function konten() {
  const datei = `${process.env.HOME}/Downloads/aics-dev-zugangsdaten.md`;
  const m = {};
  for (const z of readFileSync(datei, 'utf-8').split('\n')) {
    const t = z.match(/^\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|/);
    if (t) m[t[1]] = t[2];
  }
  return m;
}

async function anmelden(email, passwort) {
  const r = await ruf('/api/auth/login', { methode: 'POST', daten: { email, password: passwort } });
  return r.json?.access_token || '';
}

(async () => {
  mkdirSync(OUT, { recursive: true });
  const pw = konten();
  const T = {};
  for (const [rolle, mail] of Object.entries({
    admin: 'dev.admin@mustermann.example',
    cra: 'dev.cra@mustermann.example',
    freigabe: 'dev.freigabe@mustermann.example',
    viewer: 'dev.viewer@mustermann.example',
    auditor: 'dev.auditor@mustermann.example',
    gf: 'dev.gf@mustermann.example',
    dsb: 'dev.dsb@mustermann.example',
  })) {
    T[rolle] = await anmelden(mail, pw[mail] || '');
    if (!T[rolle]) { console.error(`Anmeldung ${mail} fehlgeschlagen`); process.exit(2); }
  }
  console.log(`Angemeldet: ${Object.keys(T).join(', ')}\n`);

  const P = 'Compliance Portal';          // CRA-Projekt mit vollem Datenbestand
  const V = `9.9.${String(Date.now()).slice(-5)}`;  // eigene Version je Lauf

  // ── 1 · Rollen: wer darf schreiben? ───────────────────────────────────────
  bereich = 'rollen';
  console.log('— Rollen und Rechte —');
  for (const [rolle, erlaubt] of [['viewer', false], ['auditor', false], ['cra', true]]) {
    const r = await ruf(`/api/cra/projekte/${encodeURIComponent(P)}/klassifizierung`,
      { methode: 'PUT', token: T[rolle], daten: { produktklasse: 'default' } });
    const darf = r.status < 300;
    if (darf === erlaubt) ok(`${rolle} darf ${erlaubt ? '' : 'nicht '}schreiben (HTTP ${r.status})`);
    else fund(`${rolle}: Schreibrecht stimmt nicht`,
              erlaubt ? 'Erfolg (2xx)' : 'Ablehnung (403)', `HTTP ${r.status} ${r.text.slice(0, 90)}`);
  }
  const rl = await ruf(`/api/cra/projekte`, { token: T.viewer });
  if (rl.status < 300) ok(`viewer darf lesen (HTTP ${rl.status})`);
  else fund('viewer darf nicht einmal lesen', 'HTTP 200', `HTTP ${rl.status}`);

  // ── 2 · Release-Zustandsmaschine + Vier-Augen ─────────────────────────────
  bereich = 'vier-augen';
  console.log('\n— Release-Strecke und Vier-Augen-Prinzip —');
  const anlegen = await ruf(`/api/cra-konformitaet/projekte/${encodeURIComponent(P)}/releases/${V}`,
    { methode: 'POST', token: T.cra });
  if (anlegen.status < 300) ok(`Release-Vorgang ${V} angelegt`);
  else fund(`Vorgang ${V} lässt sich nicht anlegen`, 'HTTP 2xx', `HTTP ${anlegen.status} ${anlegen.text.slice(0, 120)}`);

  // Der Haken am Produkt ist Voraussetzung (#1805) — Zustand feststellen.
  const konf = await ruf(`/api/cra-konformitaet/projekte/${encodeURIComponent(P)}/konformitaet`, { token: T.cra });
  const hakenGesetzt = !!konf.json?.bewertung_abgeschlossen;
  console.log(`      (Bewertungsweg am Produkt abgeschlossen: ${hakenGesetzt})`);

  const einreichen = await ruf(`/api/cra-konformitaet/projekte/${encodeURIComponent(P)}/releases/${V}/einreichen`,
    { methode: 'POST', token: T.cra, daten: {} });
  if (hakenGesetzt) {
    if (einreichen.status < 300) ok('Einreichen gelingt bei abgeschlossenem Bewertungsweg');
    else fund('Einreichen scheitert trotz abgeschlossenem Bewertungsweg',
              'HTTP 2xx', `HTTP ${einreichen.status} ${einreichen.text.slice(0, 140)}`);
  } else if (einreichen.status === 409 || einreichen.status === 400) {
    ok(`Einreichen ohne Bewertungsweg abgelehnt (HTTP ${einreichen.status}) — #1803`);
  } else {
    fund('Einreichen ohne abgeschlossenen Bewertungsweg ging durch',
         'Ablehnung mit Begründung', `HTTP ${einreichen.status}`);
  }

  if (einreichen.status < 300) {
    // Dieselbe Person darf nicht freigeben (Art. 13 Abs. 1).
    const selbst = await ruf(`/api/cra-konformitaet/projekte/${encodeURIComponent(P)}/releases/${V}/freigeben`,
      { methode: 'POST', token: T.cra, daten: { confirm_rot: true } });
    if (selbst.status === 409 || selbst.status === 403) ok(`Freigabe durch den Einreicher abgelehnt (HTTP ${selbst.status})`);
    else fund('Vier-Augen-Prinzip greift nicht: Einreicher konnte selbst freigeben',
              'HTTP 409', `HTTP ${selbst.status} ${selbst.text.slice(0, 140)}`);

    // Ein Konto ohne Freigaberecht darf auch nicht.
    const ohne = await ruf(`/api/cra-konformitaet/projekte/${encodeURIComponent(P)}/releases/${V}/freigeben`,
      { methode: 'POST', token: T.viewer, daten: { confirm_rot: true } });
    if (ohne.status === 403) ok('Freigabe ohne cra:approve abgelehnt (HTTP 403)');
    else fund('Freigabe ohne Berechtigung möglich', 'HTTP 403', `HTTP ${ohne.status}`);

    // Die zweite Person mit Freigaberecht darf.
    const zweite = await ruf(`/api/cra-konformitaet/projekte/${encodeURIComponent(P)}/releases/${V}/freigeben`,
      { methode: 'POST', token: T.freigabe, daten: { confirm_rot: true } });
    if (zweite.status < 300) ok('Freigabe durch die zweite Person gelingt');
    else fund('Freigabe durch berechtigte zweite Person scheitert',
              'HTTP 2xx', `HTTP ${zweite.status} ${zweite.text.slice(0, 160)}`);
  }

  // ── 3 · Gate: rechnet es, und ist es widerspruchsfrei? ────────────────────
  bereich = 'gate';
  console.log('\n— Konformitäts-Gate —');
  const gate = await ruf(`/api/cra-konformitaet/projekte/${encodeURIComponent(P)}/release-check?version=${V}`, { token: T.cra });
  const g = gate.json || {};
  if (gate.status >= 300) {
    fund('Release-Check nicht abrufbar', 'HTTP 200', `HTTP ${gate.status}`);
  } else {
    const summe = (g.erfuellt || 0) + (g.begruendet_akzeptiert || 0) + (g.offen || 0);
    if (g.gesamt_anforderungen && summe === g.gesamt_anforderungen) {
      ok(`Zahlen gehen auf: ${g.erfuellt}+${g.begruendet_akzeptiert}+${g.offen} = ${g.gesamt_anforderungen}`);
    } else {
      fund('Die Zahlen des Gates gehen nicht auf',
           `erfüllt+begründet+offen = ${g.gesamt_anforderungen}`,
           `${g.erfuellt}+${g.begruendet_akzeptiert}+${g.offen} = ${summe}`);
    }
    if (['gruen', 'bedingt', 'rot'].includes(g.ampel)) ok(`Ampel: ${g.ampel} (${g.reifegrad_pct}%)`);
    else fund('Unbekannter Ampelwert', 'gruen|bedingt|rot', String(g.ampel));
    // Ein rotes Gate mit null offenen Punkten wäre ein Widerspruch.
    if (g.ampel === 'rot' && (g.offene_punkte || []).length === 0) {
      fund('Ampel rot, aber kein offener Punkt genannt', 'mindestens ein offener Punkt', '0 Punkte');
    } else ok(`Ampel und offene Punkte passen zusammen (${(g.offene_punkte || []).length} Punkte)`);
  }

  // ── 4 · Pflichtangaben der EU-Konformitätserklärung (Anhang V) ───────────
  bereich = 'doc';
  console.log('\n— EU-Konformitätserklärung —');
  const leer = await ruf(`/api/cra-konformitaet/projekte/${encodeURIComponent(P)}/konformitaet/doc`,
    { methode: 'POST', token: T.cra, daten: { doc: {} } });
  if (leer.status >= 400) ok(`Erklärung ohne Pflichtangaben abgelehnt (HTTP ${leer.status})`);
  else fund('Erklärung ohne Pflichtangaben ausgestellt',
            'Ablehnung (400/409)', `HTTP ${leer.status}`);

  // ── 5 · Bewertungsweg gegen die Produktklasse (#1759) ────────────────────
  bereich = 'bewertungsweg';
  console.log('\n— Bewertungsweg und Produktklasse —');
  const klasse = await ruf(`/api/cra/projekte/${encodeURIComponent(P)}/klassifizierung`,
    { methode: 'PUT', token: T.cra, daten: { produktklasse: 'critical' } });
  if (klasse.status < 300) {
    const a = await ruf(`/api/cra-konformitaet/projekte/${encodeURIComponent(P)}/konformitaet`,
      { methode: 'PUT', token: T.cra, daten: { bewertungsweg: 'A' } });
    if (a.status >= 400) ok(`Modul A bei Anhang-IV-Produkt abgelehnt (HTTP ${a.status})`);
    else fund('Modul A für ein kritisches Produkt angenommen',
              'Ablehnung — Anhang IV lässt Selbstbewertung nicht zu', `HTTP ${a.status}`);
    await ruf(`/api/cra/projekte/${encodeURIComponent(P)}/klassifizierung`,
      { methode: 'PUT', token: T.cra, daten: { produktklasse: 'default' } });
  } else {
    fund('Produktklasse lässt sich nicht setzen', 'HTTP 2xx', `HTTP ${klasse.status}`);
  }

  // ── 6 · Mandantentrennung: fremdes Projekt ───────────────────────────────
  bereich = 'mandanten';
  console.log('\n— Projekt- und Mandantenzugriff —');
  const fremd = await ruf('/api/cra/projekte/Gibt-Es-Nicht-4711/reifegrad', { token: T.cra });
  if (fremd.status === 404 || fremd.status === 403) ok(`Unbekanntes Projekt: HTTP ${fremd.status}`);
  else fund('Unbekanntes Projekt liefert keinen klaren Fehler', 'HTTP 404', `HTTP ${fremd.status} ${fremd.text.slice(0, 90)}`);

  // ── 7 · Berichte: entsteht wirklich eine Datei? ──────────────────────────
  bereich = 'berichte';
  console.log('\n— Berichte —');
  const liste = await ruf(`/api/cra/projekte/${encodeURIComponent(P)}/berichte`, { token: T.cra });
  const typen = (liste.json?.berichte || liste.json?.specs || liste.json || []);
  const namen = Array.isArray(typen) ? typen.map((t) => t.typ || t.id || t).filter(Boolean) : [];
  if (namen.length) ok(`${namen.length} Berichtstyp(en): ${namen.slice(0, 8).join(', ')}`);
  else fund('Keine Berichtstypen gemeldet', 'mindestens einen Typ', JSON.stringify(liste.json).slice(0, 140));

  // ── 8 · Unangemeldet ist nichts zu holen ─────────────────────────────────
  bereich = 'auth';
  console.log('\n— Zugriff ohne Anmeldung —');
  for (const pfad of ['/api/cra/projekte', '/api/admin/users', '/api/firmen']) {
    const r = await ruf(pfad);
    if (r.status === 401 || r.status === 422) ok(`${pfad}: HTTP ${r.status}`);
    else fund(`${pfad} ohne Anmeldung erreichbar`, 'HTTP 401', `HTTP ${r.status} ${r.text.slice(0, 80)}`);
  }

  writeFileSync(`${OUT}logikpruefung.json`, JSON.stringify({ base: BASE, funde, geprueft }, null, 2));
  console.log(`\n== ${geprueft.length} Prüfungen bestanden, ${funde.length} Fund(e) ==`);
  process.exit(0);
})();
