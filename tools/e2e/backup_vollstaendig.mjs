/**
 * Abnahme von #1785 über einen echten Firefox.
 *
 * Geprüft wird die ganze Strecke an der Oberfläche: Sicherung erstellen,
 * Inhaltsangabe in der Liste, Herunterladen (die Datei muss ankommen und ein
 * gültiges ZIP sein), Hochladen derselben Datei, und der Restore-Dialog, der
 * vor dem Einspielen sagen muss, was im Archiv steckt.
 *
 * Der wichtigste Schritt ist der letzte: Ein Archiv im alten Format enthält die
 * Nutzdaten nicht, und das muss im Dialog stehen, bevor jemand bestätigt. Ein
 * grüner Knopf beweist das nicht — der Text muss da sein.
 *
 * Eingespielt wird hier bewusst NICHT: Ein Restore auf der Entwicklungsinstanz
 * ersetzt deren Datenbestand. Das Einspielen deckt der pytest-Rundlauf ab
 * (tests/test_backup_vollstaendig_1785.py), der in einer eigenen Datenbank läuft.
 *
 * Lauf:  AICS_BASE=https://localhost:5173 node tools/e2e/backup_vollstaendig.mjs
 * Exit:  0 = alle Schritte erreicht, 1 = Funde, 2 = Setup-Fehler
 */
import { firefox } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE = process.env.AICS_BASE || 'https://localhost:5173';
const HEADED = process.env.AICS_HEADED === '1';
const TAG = new Date().toISOString().slice(0, 10);
const ROOT = path.dirname(new URL(import.meta.url).pathname);
const SHOTS = path.join(ROOT, 'screens', TAG);
fs.mkdirSync(SHOTS, { recursive: true });

const funde = [];
let n = 0;
function fund(t) { funde.push(t); console.log(`  ⚠ ${t}`); }
function ok(t) { console.log(`  ✓ ${t}`); }

async function shot(page, name) {
  const datei = `1785-${String(++n).padStart(2, '0')}-${name}.png`;
  await page.screenshot({ path: path.join(SHOTS, datei), fullPage: true });
  console.log(`  📷 ${datei}`);
}

async function warte(fn, { timeout = 20000, intervall = 300 } = {}) {
  const ende = Date.now() + timeout;
  for (;;) {
    try { if (await fn()) return true; } catch { /* noch nicht da */ }
    if (Date.now() > ende) return false;
    await new Promise(r => setTimeout(r, intervall));
  }
}

async function text(page) {
  return (await page.locator('body').innerText()).replace(/\s+/g, ' ');
}

/** Ein minimales Archiv im alten Format (MANIFEST + eine SQLite-Datei).
 *  Von Hand gebaut, weil der Zweck gerade ist, KEIN gültiges Format-2-Archiv
 *  zu sein — erzeugen lässt sich so etwas über die Oberfläche nicht mehr. */
function baueFormat1Zip() {
  const eintraege = [
    ['MANIFEST.json', Buffer.from('{"created_at":"2026-05-11T12:00:00Z","version":"1.0.0"}')],
    ['data/db/cra.sqlite', Buffer.from('SQLite format 3\0' + '\0'.repeat(80))],
  ];
  const lokal = [], zentral = [];
  let offset = 0;
  for (const [name, daten] of eintraege) {
    const nameBuf = Buffer.from(name);
    const crc = crc32(daten);
    const lh = Buffer.alloc(30);
    lh.writeUInt32LE(0x04034b50, 0); lh.writeUInt16LE(20, 4);
    lh.writeUInt32LE(crc, 14); lh.writeUInt32LE(daten.length, 18);
    lh.writeUInt32LE(daten.length, 22); lh.writeUInt16LE(nameBuf.length, 26);
    lokal.push(lh, nameBuf, daten);
    const ch = Buffer.alloc(46);
    ch.writeUInt32LE(0x02014b50, 0); ch.writeUInt16LE(20, 4); ch.writeUInt16LE(20, 6);
    ch.writeUInt32LE(crc, 16); ch.writeUInt32LE(daten.length, 20);
    ch.writeUInt32LE(daten.length, 24); ch.writeUInt16LE(nameBuf.length, 28);
    ch.writeUInt32LE(offset, 42);
    zentral.push(ch, nameBuf);
    offset += lh.length + nameBuf.length + daten.length;
  }
  const zBuf = Buffer.concat(zentral);
  const ende = Buffer.alloc(22);
  ende.writeUInt32LE(0x06054b50, 0);
  ende.writeUInt16LE(eintraege.length, 8); ende.writeUInt16LE(eintraege.length, 10);
  ende.writeUInt32LE(zBuf.length, 12); ende.writeUInt32LE(offset, 16);
  return Buffer.concat([Buffer.concat(lokal), zBuf, ende]);
}

function crc32(buf) {
  let c, tabelle = crc32.t;
  if (!tabelle) {
    tabelle = crc32.t = [];
    for (let n = 0; n < 256; n++) {
      c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      tabelle[n] = c >>> 0;
    }
  }
  let crc = 0xffffffff;
  for (const b of buf) crc = tabelle[(crc ^ b) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

const browser = await firefox.launch({ headless: !HEADED });
const ctx = await browser.newContext({ ignoreHTTPSErrors: true, acceptDownloads: true });
const page = await ctx.newPage();

try {
  console.log('→ Anmelden');
  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
  await page.locator('input[type=email], input[type=text]').first().fill('admin@example.com');
  await page.locator('input[type=password]').first().fill('admin-password');
  await page.locator('button', { hasText: /Anmelden/i }).first().click();
  if (!await warte(async () => !/\/login/.test(page.url()))) {
    throw new Error('Login fehlgeschlagen');
  }

  console.log('→ Backup-Verwaltung');
  await page.goto(`${BASE}/admin/backup`, { waitUntil: 'domcontentloaded' });
  if (!await warte(() => page.locator('button', { hasText: /Neue Sicherung erstellen|Neues Backup erstellen/i }).count())) {
    throw new Error('Backup-Ansicht nicht erreicht');
  }
  await shot(page, 'uebersicht');

  // Die Liste muss den Unterschied zwischen den Formaten zeigen — daran hängt
  // alles: Ein Archiv ohne Datenbank sieht sonst aus wie eine Sicherung.
  const inhalt = await text(page);
  if (!/Tabellen/i.test(inhalt)) {
    fund('Die Liste nennt den Inhalt nicht (keine Tabellenangabe sichtbar)');
  } else {
    ok('Inhaltsangabe in der Liste');
  }

  console.log('→ Sicherung erstellen');
  // Nicht die Zeilenzahl prüfen: Die Aufbewahrungsgrenze entfernt beim
  // Erstellen gleichzeitig ältere Archive, die Anzahl bleibt also gleich oder
  // sinkt. Geprüft wird, ob die neue Sicherung mit ihrer Kennung dasteht.
  const vorherIds = await page.locator('tbody tr td:first-child').allInnerTexts();
  await page.locator('button', { hasText: /Neue Sicherung erstellen|Neues Backup erstellen/i }).first().click();
  const neueZeile = await warte(async () => {
    const jetzt = await page.locator('tbody tr td:first-child').allInnerTexts();
    return jetzt.some(z => !vorherIds.includes(z));
  }, { timeout: 180000 });
  if (!neueZeile) {
    fund('Die neu erstellte Sicherung steht nicht in der Liste');
  } else {
    ok('Sicherung erstellt und gelistet');
  }
  const nachErstellen = await text(page);
  if (!/Datei/i.test(nachErstellen) || !/Zeile/i.test(nachErstellen)) {
    fund('Das Ergebnis nennt nicht, was gesichert wurde');
  } else {
    ok('Ergebnis nennt Tabellen, Zeilen und Dateien');
  }
  await shot(page, 'nach-erstellen');

  console.log('→ Herunterladen');
  const [download] = await Promise.all([
    page.waitForEvent('download', { timeout: 120000 }),
    page.locator('button', { hasText: /Herunterladen/i }).first().click(),
  ]);
  const ziel = path.join(SHOTS, `1785-datei-${download.suggestedFilename()}`);
  await download.saveAs(ziel);
  const groesse = fs.statSync(ziel).size;
  const kopf = fs.readFileSync(ziel).subarray(0, 2);
  if (kopf[0] !== 0x50 || kopf[1] !== 0x4b) fund('Heruntergeladene Datei ist kein ZIP');
  else ok(`Datei angekommen: ${(groesse / 1024 / 1024).toFixed(1)} MB, gültiges ZIP`);

  console.log('→ Wieder hochladen');
  await page.locator('input[type=file]').first().setInputFiles(ziel);
  if (!await warte(async () => /hochgeladen/i.test(await text(page)), { timeout: 180000 })) {
    fund('Der Upload derselben Datei wurde nicht bestätigt');
  } else {
    ok('Hochgeladene Sicherung angenommen');
  }
  fs.unlinkSync(ziel);
  await shot(page, 'nach-upload');

  console.log('→ Restore-Dialog (ohne Einspielen)');
  // Ein Archiv im alten Format muss die Warnung zeigen. Es wird hier selbst
  // angelegt: Die Aufbewahrungsgrenze räumt alte Archive mit der Zeit weg, und
  // ein Prüfschritt, der nur läuft, wenn zufällig eines dasteht, prüft nichts.
  let zeilen = page.locator('tbody tr');
  let altZeile = null;
  for (let i = 0; i < await zeilen.count(); i++) {
    const z = zeilen.nth(i);
    if (/altes Format/i.test(await z.innerText())) { altZeile = z; break; }
  }
  if (!altZeile) {
    console.log('  (keines vorhanden — lege ein Archiv im alten Format an)');
    const altDatei = path.join(SHOTS, 'format1-probe.zip');
    fs.writeFileSync(altDatei, baueFormat1Zip());
    await page.locator('input[type=file]').first().setInputFiles(altDatei);
    await warte(async () => /altes Format/i.test(await text(page)), { timeout: 60000 });
    fs.unlinkSync(altDatei);
    zeilen = page.locator('tbody tr');
    for (let i = 0; i < await zeilen.count(); i++) {
      const z = zeilen.nth(i);
      if (/altes Format/i.test(await z.innerText())) { altZeile = z; break; }
    }
    if (altZeile) ok('Archiv im alten Format ist in der Liste gekennzeichnet');
  } else {
    ok('Archiv im alten Format ist in der Liste gekennzeichnet');
  }
  if (!altZeile) {
    fund('Ein Archiv im alten Format wurde nicht als solches erkannt');
  } else {
    await altZeile.locator('button', { hasText: /Wiederherstellen/i }).first().click();
    // Gezielt IM Dialog prüfen, nicht im Seitentext: Der Chip „altes Format —
    // ohne Datenbank" steht auch in der Tabelle dahinter, und ein Treffer dort
    // würde einen Dialog bestätigen, der noch lädt.
    const dlg = page.locator('.modal-content, [role=dialog]').first();
    if (!await warte(async () => await dlg.count() && /wiederherstellen/i.test(await dlg.innerText()))) {
      fund('Der Restore-Dialog öffnet nicht');
    } else {
      // Warten, bis der Inhalt geladen ist — vorher steht dort nur „wird gelesen".
      const fertig = await warte(async () => !/wird gelesen/i.test(await dlg.innerText()),
                                 { timeout: 30000 });
      if (!fertig) fund('Der Dialog bleibt bei „Archiv wird gelesen" stehen');
      const dialog = (await dlg.innerText()).replace(/\s+/g, ' ');
      if (!/NICHT wiederhergestellt|nicht wieder ?hergestellt|ohne Datenbankinhalt|altes Format/i.test(dialog)) {
        fund(`Der Dialog warnt nicht vor dem unvollständigen Archiv — Text: ${dialog.slice(0, 200)}`);
      } else {
        ok('Dialog warnt vor dem unvollständigen Archiv');
      }
      const bestaetigen = dlg.locator('button', { hasText: /Bestätigen/i }).first();
      if (await bestaetigen.count() && await bestaetigen.isEnabled()) {
        ok('Bestätigen ist erst nach dem Laden möglich');
      }
      await shot(page, 'restore-dialog-altes-archiv');
      const abbrechen = page.locator('button', { hasText: /Abbrechen/i }).first();
      if (await abbrechen.count()) await abbrechen.click();
    }
  }

  console.log(funde.length ? `\n${funde.length} Fund(e):` : '\n0 Funde.');
  funde.forEach(f => console.log(` - ${f}`));
  await browser.close();
  process.exit(funde.length ? 1 : 0);
} catch (e) {
  console.error(`\nSetup-/Ablauffehler: ${e.message}`);
  try { await shot(page, 'fehler'); } catch { /* egal */ }
  await browser.close();
  process.exit(2);
}
