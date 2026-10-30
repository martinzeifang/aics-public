/**
 * AI Compliance Suite — wiederholbarer Firefox-Smoke-Test (E2E).
 *
 * Konsolidiert den exhaustiven Funktionstest (2026-06-22) in einen wiederholbaren
 * Lauf. Testet *über einen echten Firefox* (Playwright):
 *   1. Login über die UI
 *   2. Navigation aller Modul-Routen + Admin-Routen
 *   3. Durchklicken aller Tab-Gruppen + Untertabs je Modul (mit erstem Projekt)
 *   4. Erfassung von Console-Errors/-Warnings, pageerrors und HTTP >= 400
 *   5. GET-Endpoint-Stichprobe + Bericht-DOCX-Erzeugung aus dem Seiten-Kontext
 *      (echtes fetch mit dem App-Token → zählt als "über Firefox")
 *
 * Exit-Code: 0 = sauber, 1 = Funde (Errors/5xx/Report-Fehler), 2 = Setup-Fehler.
 * Console-Warnings sind per Default nicht fatal (--strict macht sie fatal).
 *
 * Konfiguration über ENV:
 *   AICS_BASE      Frontend-URL   (Default https://127.0.0.1:5173)
 *   AICS_EMAIL     Login-E-Mail   (Default admin@example.com)
 *   AICS_PASSWORD  Login-Passwort (Default admin-password)
 *   AICS_HEADED=1  Browser sichtbar starten
 *   AICS_SHOTS=1   Screenshot je Tab nach out/shots/
 *
 * Lauf:  node tools/e2e/smoke.mjs   (siehe tools/e2e/README.md)
 */
import { firefox } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE = process.env.AICS_BASE || 'https://127.0.0.1:5173';
const EMAIL = process.env.AICS_EMAIL || 'admin@example.com';
const PASSWORD = process.env.AICS_PASSWORD || 'admin-password';
const STRICT = process.argv.includes('--strict');
const SHOTS = process.env.AICS_SHOTS === '1';
const OUT = path.join(path.dirname(new URL(import.meta.url).pathname), 'out');
const SHOTDIR = path.join(OUT, 'shots');
fs.mkdirSync(OUT, { recursive: true });
if (SHOTS) fs.mkdirSync(SHOTDIR, { recursive: true });

// Module mit Projekt-/Objekt-Sidebar (erst Projekt wählen, dann Tabs).
// DORA ist bewusst NICHT enthalten (Modul entfernt, #1500).
const MODULES = ['/firmen', '/risikobewertung', '/cra', '/wiba', '/dsgvo', '/nis2', '/aiact', '/soc'];
const ADMIN = ['/admin', '/admin/users', '/admin/audit', '/admin/db', '/admin/frameworks',
  '/admin/backup', '/admin/settings', '/admin/templates', '/admin/firmen-link', '/account/security'];
// Module mit projekt-skaliertem Berichts-Center (DOCX-Erzeugung).
const REPORT_MODULES = ['cra', 'nis2', 'dsgvo', 'aiact', 'wiba', 'risikobewertung'];

const findings = [];   // fatal
const warns = [];      // nicht fatal (außer --strict)
let ctx = 'init';
const NOISE = /vite|\[hmr\]|sourcemap|DevTools|Download the Vue|favicon/i;
const rec = (o) => {
  if (o.kind === 'console' && o.type === 'warning') { warns.push({ where: ctx, ...o }); return; }
  findings.push({ where: ctx, ...o });
};

const browser = await firefox.launch({ headless: !process.env.AICS_HEADED });
const c = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1600, height: 1000 } });
const page = await c.newPage();
page.on('console', (m) => {
  const t = m.type();
  if ((t === 'error' || t === 'warning') && !NOISE.test(m.text()))
    rec({ kind: 'console', type: t, text: m.text().slice(0, 280) });
});
page.on('pageerror', (e) => rec({ kind: 'pageerror', text: String(e).slice(0, 280) }));
page.on('response', (r) => {
  const s = r.status();
  // KI-Streaming-Endpunkte können 409 liefern (kein Provider) — kein Defekt.
  if (s >= 400 && !/ki-summary|run-stream|\/stream/.test(r.url()))
    rec({ kind: 'http', status: s, method: r.request().method(), url: r.url().replace(BASE, '') });
});

const safe = (s) => s.replace(/[^a-z0-9]+/gi, '_').slice(0, 28);
async function nav(p) {
  ctx = p;
  await page.evaluate((x) => {
    try { document.querySelector('#app').__vue_app__.config.globalProperties.$router.push(x); } catch (e) {}
  }, p);
  await page.waitForTimeout(1400);
}
async function pickFirstProject() {
  // 1) bekannte CSS-Hooks
  for (const s of ['.proj-name', '.projekt-name', 'aside [class*="proj-"]', '.projekt-list li',
    '.projekt-item', '.sidebar li', 'aside li', '.list-item', 'tbody tr']) {
    const l = page.locator(s);
    if (await l.count()) { try { await l.first().click({ timeout: 1500 }); await page.waitForTimeout(1100); return true; } catch (e) {} }
  }
  // 2) Fallback: erstes klickbares (cursor:pointer) Blatt in der Sidebar, das kein
  //    ALL-CAPS-Gruppenheader ist (Firma-Header sind via text-transform groß).
  const ok = await page.evaluate(() => {
    const aside = document.querySelector('aside') || document.querySelector('.sidebar');
    if (!aside) return false;
    for (const el of aside.querySelectorAll('*')) {
      const t = (el.textContent || '').trim();
      if (el.children.length <= 1 && t.length >= 2 && t.length <= 40 &&
          getComputedStyle(el).cursor === 'pointer' && t !== t.toUpperCase()) {
        el.click(); return true;
      }
    }
    return false;
  }).catch(() => false);
  if (ok) await page.waitForTimeout(1100);
  return ok;
}
async function clickAllTabs(route) {
  const groupsSel = '.grouped-nav .nav-group, .nav-groups [role=tab]';
  const tabsSel = '.grouped-nav .nav-tab, .nav-tabs [role=tab], .tabs button, button.tab, button.tab-btn';
  const gN = await page.locator(groupsSel).count();
  let idx = 0;
  const visit = async (glabel) => {
    const tN = await page.locator(tabsSel).count();
    for (let j = 0; j < tN; j++) {
      const t = page.locator(tabsSel).nth(j);
      let label = '';
      try { label = (await t.innerText()).split('\n')[0].trim().slice(0, 40); } catch (e) { continue; }
      ctx = `${route} › ${glabel}${label}`;
      try { await t.click({ timeout: 2500 }); await page.waitForTimeout(750); } catch (e) { rec({ kind: 'tab-click-fail', text: label }); continue; }
      if (SHOTS) await page.screenshot({ path: path.join(SHOTDIR, `${safe(route)}_${String(idx++).padStart(2, '0')}_${safe(label)}.png`) }).catch(() => {});
    }
  };
  if (gN === 0) { ctx = route; await visit(''); }
  else for (let i = 0; i < gN; i++) {
    const g = page.locator(groupsSel).nth(i);
    let gl = '';
    try { gl = (await g.innerText()).split('\n')[0].trim() + ' › '; } catch (e) {}
    try { await g.click({ timeout: 2000 }); await page.waitForTimeout(500); } catch (e) {}
    await visit(gl);
  }
}

// Bericht-DOCX-Erzeugung aus dem Seiten-Kontext (echtes fetch mit App-Token).
async function reportSweep() {
  ctx = 'reports';
  return page.evaluate(async (modules) => {
    const tok = sessionStorage.getItem('auth_token') || localStorage.getItem('auth_token');
    const H = { Authorization: `Bearer ${tok}` };
    const out = [];
    for (const mod of modules) {
      // erstes Projekt holen
      let proj = null;
      try {
        const pr = await fetch(`/api/${mod}/projekte`, { headers: H });
        if (pr.ok) { const d = await pr.json(); const arr = Array.isArray(d) ? d : (d.projekte || d.items || []); proj = arr[0] && (arr[0].name || arr[0].projekt); }
      } catch (e) {}
      if (!proj) { out.push({ mod, ok: false, note: 'kein Projekt' }); continue; }
      const p = encodeURIComponent(proj);
      let types = [];
      try {
        const lr = await fetch(`/api/${mod}/projekte/${p}/berichte`, { headers: H });
        if (lr.ok) { const d = await lr.json(); const tl = d.typen || d.berichte || d.reports || (Array.isArray(d) ? d : []); types = tl.map((t) => t.id || t.typ || t.key).filter(Boolean); }
      } catch (e) {}
      for (const tid of types) {
        try {
          const rr = await fetch(`/api/${mod}/projekte/${p}/berichte/${encodeURIComponent(tid)}?format=docx&projekt=${p}`, { headers: H });
          out.push({ mod, typ: tid, status: rr.status, ok: rr.ok, ct: rr.headers.get('content-type') });
        } catch (e) { out.push({ mod, typ: tid, ok: false, note: String(e).slice(0, 80) }); }
      }
    }
    return out;
  }, REPORT_MODULES).catch((e) => { rec({ kind: 'report-sweep-error', text: String(e).slice(0, 200) }); return []; });
}

let reportResults = [];
try {
  ctx = 'login';
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.locator('input[type=email], input[type=text]').first().fill(EMAIL);
  await page.locator('input[type=password]').first().fill(PASSWORD);
  await page.locator('button', { hasText: /Anmelden/i }).first().click();
  await page.waitForTimeout(3000);
  // Login erfolgreich?
  const stillLogin = await page.locator('input[type=password]').count();
  if (stillLogin) { console.error('FATAL: Login fehlgeschlagen'); await browser.close(); process.exit(2); }

  for (const r of MODULES) {
    await nav(r);
    const picked = await pickFirstProject();
    const before = findings.length;
    await clickAllTabs(r);
    console.log(`  ${r.padEnd(20)} projekt:${picked ? 'ja' : 'nein'}  funde:+${findings.length - before}`);
  }
  for (const r of ADMIN) {
    await nav(r); ctx = r;
    const before = findings.length;
    await clickAllTabs(r);
    console.log(`  ${r.padEnd(20)} funde:+${findings.length - before}`);
  }

  console.log('\n  Bericht-DOCX-Erzeugung …');
  reportResults = await reportSweep();
  for (const rr of reportResults) {
    const bad = rr.ok === false || (rr.status && rr.status >= 400);
    if (bad) rec({ kind: 'report', text: `${rr.mod}/${rr.typ || '?'} → ${rr.status || rr.note}` });
    if (!rr.note || rr.typ) console.log(`    ${rr.mod}/${(rr.typ || rr.note || '').toString().padEnd(20)} ${rr.status || ''} ${rr.ok ? 'OK' : 'FEHLER'}`);
  }
} catch (e) {
  console.error('CRAWL-FEHLER:', e.message);
  rec({ kind: 'crawl-error', text: e.message });
} finally {
  const report = { ts: new Date().toISOString(), base: BASE, findings, warnings: warns, reports: reportResults };
  fs.writeFileSync(path.join(OUT, 'smoke-report.json'), JSON.stringify(report, null, 2));
  console.log('\n================ ERGEBNIS ================');
  console.log(`  Fatale Funde:    ${findings.length}`);
  console.log(`  Warnungen:       ${warns.length}`);
  if (findings.length) { console.log('\n  --- FUNDE ---'); for (const f of findings.slice(0, 60)) console.log(`   [${f.kind}${f.status ? ' ' + f.status : ''}] ${f.where}\n       ${f.text || f.url || ''}`); }
  if (warns.length) { console.log('\n  --- WARNUNGEN ---'); for (const w of warns.slice(0, 30)) console.log(`   ${w.where}: ${w.text}`); }
  console.log(`\n  Report: ${path.join(OUT, 'smoke-report.json')}`);
  await browser.close();
  const fail = findings.length > 0 || (STRICT && warns.length > 0);
  process.exit(fail ? 1 : 0);
}
