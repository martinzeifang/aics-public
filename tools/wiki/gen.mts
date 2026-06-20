// Reichhaltige Wiki-Generierung aus der echten In-App-Hilfe (help/*.ts) + Screenshots.
// Baut die Modul-Bücher (Überblick + je Tab) neu auf und ein Einstellungen-Buch.
import fs from 'node:fs'
import { MODULE_HELP } from './help/index.ts'
import { MOD_TABS } from './tabs.mjs'
import { MODULE_BOOK, DESC, cleanTitle } from './content2.mjs'

const BASE = 'http://aics.example.com:6875'
const TOKEN = fs.readFileSync(new URL('./.bs_token', import.meta.url), 'utf8').trim()
const H = { Authorization: 'Token ' + TOKEN }
const api = async (m, ep, body) => {
  const r = await fetch(BASE + ep, { method: m, headers: { ...H, 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined })
  const t = await r.text(); if (!r.ok) throw new Error(`${m} ${ep} ${r.status} ${t.slice(0, 150)}`)
  return t ? JSON.parse(t) : {}
}
const upload = async (pageId, dir, file) => {
  const fp = new URL(`./${dir}/${file}`, import.meta.url).pathname
  if (!fs.existsSync(fp)) return null
  const fd = new FormData(); fd.set('type', 'gallery'); fd.set('uploaded_to', String(pageId))
  fd.set('image', new Blob([fs.readFileSync(fp)], { type: 'image/png' }), file)
  const r = await fetch(BASE + '/api/image-gallery', { method: 'POST', headers: H, body: fd })
  return r.ok ? (await r.json()).url : null
}
const pad = n => String(n).padStart(2, '0')
const sec = s => s ? `\n## ${s.title}\n\n${s.intro || ''}\n\n${(s.bullets || []).map(b => '- ' + b).join('\n')}\n` : ''
const KI_IDS = /assistent|anforderung|requirement|risiken|owasp|fria|art5|literacy|privacy|tom|alerts|incidents|conformity|klass/i
const KI = '\n\n> **🤖 KI-Unterstützung:** läuft über den konfigurierten Provider — **lokale LLM** (Ollama, kein Datenabfluss) **oder Cloud-API**. Vor dem Senden zeigt eine **Datenvorschau**, was übermittelt wird; der Lauf ist **live** sichtbar und das **Ergebnis** wird vor der Übernahme angezeigt. KI-Ausgaben sind fachlich zu prüfen.'

async function ensureBook(books, name, description) {
  let b = books.find(x => x.name === name)
  if (!b) b = await api('POST', '/api/books', { name, description })
  // alle Seiten löschen (sauberer Neuaufbau)
  const d = await api('GET', `/api/books/${b.id}`)
  for (const c of (d.contents || [])) if (c.type === 'page') await api('DELETE', `/api/pages/${c.id}`).catch(() => {})
  return b
}
async function addPage(bookId, name, md, imgDir, imgFile) {
  const page = await api('POST', '/api/pages', { book_id: bookId, name, markdown: '_(wird befüllt)_' })
  let body = md
  if (imgFile) {
    const url = await upload(page.id, imgDir, imgFile)
    body += url ? `\n\n![${name}](${url})` : '\n\n_(Screenshot folgt.)_'
  }
  await api('PUT', `/api/pages/${page.id}`, { name, markdown: body })
  return page
}

// ---- Einstellungen-Buch (eigene, ausführliche Inhalte) ----
const SETTINGS = [
  ['Überblick', `# Einstellungen & Administration\n\nDie Administration steuert das Verhalten der gesamten Suite: **KI-Provider** (lokal oder Cloud), **Word-/PDF-Vorlagen**, **Benutzer & Rollen**, **Audit**, **Backup**, **Lizenz**, **Frameworks**, **Firmen-Verknüpfung** und den **WiBA-Katalog**. Diese Bereiche sind nur für Administratoren sichtbar (Rolle mit den \`admin:*\`-Rechten). Die folgenden Seiten erklären jeden Bereich und wofür er da ist.`, 'admin-settings.png'],
  ['KI-Provider — Grundlagen & Auswahl', `# KI-Provider — Grundlagen\n\nAlle KI-Funktionen der Suite (automatische Bewertungen, Wizards, Zusammenfassungen) nutzen **einen zentral konfigurierten Provider**. Es gibt zwei Betriebsarten:\n\n- **🖥️ Lokal (Ollama):** Die Modelle laufen auf einem eigenen Server. **Es verlassen keine Daten Ihr Netzwerk** — ideal für sensible Inhalte.\n- **☁️ Cloud (API):** Anthropic, OpenAI, Google u. a. Höhere Qualität/Geschwindigkeit, aber **Daten werden an den Anbieter übermittelt** (Egress). Vor jeder Übermittlung erscheint eine **Datenvorschau mit Bestätigung**.\n\nDer aktive Provider ist oben rechts in der Suite als Badge sichtbar (☁️/🖥️). Die Auswahl gilt suite-weit.`, 'admin-settings.png'],
  ['KI-Provider — Lokal (Ollama)', `# Lokale LLM (Ollama)\n\nKonfiguration der lokalen KI: **Server-Adresse** (Standard \`http://localhost:11434\`), **Modell** (z. B. \`llama3.1\`, \`qwen2.5\`) und Timeouts. Das Modell muss auf dem Ollama-Server installiert sein (\`ollama pull <modell>\`).\n\n**Wofür:** datenschutzfreundliche KI-Bewertung/-Generierung ohne Datenabfluss. Empfohlen für personenbezogene oder vertrauliche Inhalte. Der erste Aufruf kann durch das Laden des Modells 10–30 s dauern.`, 'admin-ollama.png'],
  ['KI-Provider — Cloud (Anthropic/OpenAI/Google)', `# Cloud-Provider\n\nÜber eine **Anbieter-Auswahl** wählen Sie den Cloud-Dienst (Anthropic, OpenAI, Google …) und hinterlegen **API-Schlüssel** und **Modell** (per Dropdown wählbar). \n\n**Wofür:** höhere Antwortqualität/Geschwindigkeit. **Wichtig:** Inhalte werden an den Anbieter gesendet. Die Suite erzwingt eine **Datenübermittlungs-Bestätigung** und zeigt vorab, welche Felder übertragen werden. API-Schlüssel werden serverseitig gespeichert und nie im Klartext angezeigt.`, 'admin-settings.png'],
  ['Word-/PDF-Vorlagen', `# Word-/PDF-Vorlagen\n\nZentrale, admin-verwaltete **Export-Vorlagen** für CRA, NIS2, AI-Act, DSGVO und Risikobewertung. Eine hochgeladene DOCX/DOTX mit Platzhaltern wird beim Export befüllt; PDF wird über den Konverter (Gotenberg) erzeugt.\n\n**Wofür:** einheitliches Corporate Design und kanzlei-/normspezifische Layouts. Pro Vorlage: Variablen/Mapping ansehen, Standard setzen, Test-Export (DOCX/PDF).`, 'admin-templates.png'],
  ['Benutzer & Rollen', `# Benutzer & Rollen\n\nVerwaltung der Konten und Berechtigungen. Rollen bündeln **Permissions** (z. B. \`cra:read\`, \`dsgvo:approve\`, \`admin:users\`); Module können pro Benutzer freigeschaltet werden.\n\n**Wofür:** Zugriffssteuerung nach Funktionstrennung (z. B. Geschäftsführer-Freigabe, DSB-Signatur). Neue Benutzer anlegen, Rollen/Module zuweisen, Konten deaktivieren.`, 'admin-users.png'],
  ['Audit-Log', `# Audit-Log\n\nRevisionssicheres Protokoll sicherheits-/compliance-relevanter Aktionen (Anmeldungen, Freigaben, Exporte, Löschungen …).\n\n**Wofür:** Nachweis- und Rechenschaftspflichten (z. B. DSGVO Art. 5(2)). Filter nach Modul, Aktion, Benutzer und Zeitraum.`, 'admin-audit.png'],
  ['Backup & Wiederherstellung', `# Backup & Wiederherstellung\n\nSicherung und Rückspielung der Datenbestände.\n\n**Wofür:** Datensicherheit und Aufbewahrung (z. B. CRA-/DSGVO-Aufbewahrungspflichten). Backups planmäßig erstellen, herunterladen und im Bedarfsfall wiederherstellen.`, 'admin-backup.png'],
  ['Lizenz', `# Lizenz\n\nVerwaltung der Modul-Lizenzierung. Nicht lizenzierte Module sind in der Navigation gesperrt (Ausnahme: Firmen ist immer verfügbar).\n\n**Wofür:** Freischaltung der gebuchten Module; Anzeige des Lizenzstatus und der verknüpften Module.`, 'admin-license.png'],
  ['Datenbank-Viewer', `# Datenbank-Viewer\n\nLesender Einblick in die gespeicherten Daten je Modul.\n\n**Wofür:** Transparenz und Fehleranalyse — nachvollziehen, welche Daten tatsächlich gespeichert sind.`, 'admin-db.png'],
  ['Frameworks', `# Frameworks\n\nKonfiguration der Bewertungs-Frameworks (insbesondere für die Risikobewertung, z. B. STRIDE) und übergreifender Kataloge.\n\n**Wofür:** Auswahl der methodischen Grundlage für Risiko- und Bedrohungsbewertungen.`, 'admin-frameworks.png'],
  ['Firmen-Verknüpfung', `# Firmen-Verknüpfung\n\nOrdnet Projekte aller Module einer **Firma** zu (gemeinsames Risiko-Cockpit). Nicht zugeordnete Projekte können per Namensabgleich oder manuell verknüpft werden.\n\n**Wofür:** modulübergreifende, firmenbezogene Auswertung von Risiken und Nachweisen.`, 'admin-firmenlink.png'],
  ['WiBA-Katalog', `# WiBA-Katalog\n\nDownload/Import des BSI-WiBA-Prüffragenkatalogs (Themen + Prüffragen). Der Katalog ist aktualisierbar; BSI-Originale werden nicht mitgeliefert, sondern zur Laufzeit geladen.\n\n**Wofür:** den WiBA-Fragenkatalog aktuell halten (Grundlage des WiBA-Moduls).`, 'admin-wibacatalog.png'],
  ['Issue-Integration (GitHub/GitLab)', `# Issue-Integration\n\nVerbindung zu GitHub/GitLab, um aus Anforderungen, Risiken und Doku-Lücken **Issues** zu erzeugen und deren Status zu synchronisieren.\n\n**Wofür:** Maßnahmen aus der Compliance-Arbeit direkt im Entwicklungs-/Ticketsystem nachverfolgen.`, 'admin-issues.png'],
]

const ERSTE = [
  ['Überblick', `# AI Compliance Suite — Überblick\n\nDie AI Compliance Suite bündelt Compliance-Arbeit über mehrere Regelwerke (CRA, NIS2, EU AI Act, DSGVO, DORA, WiBA) plus Risikobewertung und ein SOC. Arbeit wird je **Firma** in **Projekten** organisiert; Anforderungen werden auf einer **Reifegrad-Skala 0–5** bewertet, Nachweise gesammelt und als **Word/PDF** exportiert. **KI-Assistenten** unterstützen — lokal oder per Cloud, stets transparent. Dieses Handbuch erklärt jedes Modul und jede Funktion.`, 'home.png'],
  ['Anmeldung', `# Anmeldung\n\nMit E-Mail und Passwort anmelden oder per **Passkey**. „Auf diesem Gerät angemeldet bleiben" verlängert die Sitzung auf vertrauenswürdigen Geräten. Ihre **Rolle** (unten rechts) bestimmt die verfügbaren Module und Aktionen.`, 'login.png'],
  ['Navigation & Bedienung', `# Navigation & Bedienung\n\nObere Leiste: **Modul-Navigation**; oben rechts **KI-Provider-Status** (☁️/🖥️), Konto und Einstellungen. Innerhalb eines Moduls links ein **Projekt** wählen; der Hauptbereich zeigt gruppierte **Tabs** (Dashboard, Anforderungen, Dokumentation, Berichte …). Der **❓-Hilfe**-Knopf bietet kontextbezogene Hilfe je Bereich.`, 'home.png'],
]

const MOD_KEYS = ['cra','nis2','aiact','dsgvo','wiba','soc','risikobewertung']
const LANDING = { cra:'cra.png', nis2:'nis2.png', aiact:'aiact.png', dsgvo:'dsgvo.png', wiba:'wiba.png', soc:'soc.png', risikobewertung:'risikobewertung.png' }

function overviewMd(h) {
  let m = `# ${h.title}\n\n**Regelwerk:** ${h.regulation}\n\n${h.purpose}\n`
  m += sec(h.legalBasis) + sec(h.implementation) + sec(h.moduleSpecific)
  if (h.frameworks?.length) {
    m += `\n## Frameworks\n\n| Framework | Bezug | Wann sinnvoll |\n|---|---|---|\n`
    m += h.frameworks.map(f => `| ${f.name} | ${f.ref} | ${f.whenToUse} |`).join('\n') + '\n'
  }
  return m
}
function areaMd(mod, id, label, area) {
  let m = `# ${cleanTitle(label)}\n\n`
  if (area) {
    m += `**Zweck:** ${area.zweck}\n\n`
    if (area.rechtsgrundlage) m += `**Rechtsgrundlage:** ${area.rechtsgrundlage}\n\n`
    if (area.pflichtfelder?.length) m += `**Pflichtangaben / Inhalte:**\n\n${area.pflichtfelder.map(p => '- ' + p).join('\n')}\n\n`
    if (area.anleitung) m += `**Schritt für Schritt:**\n\n${area.anleitung}\n\n`
    if (area.tipps?.length) m += `**Tipps & häufige Fehler:**\n\n${area.tipps.map(t => '- ' + t).join('\n')}\n`
  } else {
    m += (DESC[mod]?.[id] || '_(Beschreibung folgt.)_') + '\n'
  }
  if (KI_IDS.test(id)) m += KI
  return m
}

const run = async () => {
  const books = (await api('GET', '/api/books?count=200')).data || []
  const order: number[] = []

  // 1 · Erste Schritte
  const erste = await ensureBook(books, '1 · Erste Schritte', 'Anmeldung, Navigation und Grundlagen der Suite.')
  for (let i = 0; i < ERSTE.length; i++) await addPage(erste.id, `${pad(i + 1)} · ${ERSTE[i][0]}`, ERSTE[i][1], 'shots', ERSTE[i][2])
  order.push(erste.id); console.log('Erste Schritte:', ERSTE.length)

  // Modul-Bücher aus der Hilfe
  for (const mod of MOD_KEYS) {
    const h = MODULE_HELP[mod]; const bookName = MODULE_BOOK[mod]
    const book = await ensureBook(books, bookName, h?.purpose?.slice(0, 180) || bookName)
    await addPage(book.id, 'Überblick', overviewMd(h), 'shots', LANDING[mod])
    const areas = new Map((h?.areas || []).map(a => [a.id, a]))
    let i = 0
    for (const [id, label] of MOD_TABS[mod]) { i++; await addPage(book.id, `${pad(i)} · ${cleanTitle(label)}`, areaMd(mod, id, label, areas.get(id)), 'shots2', `${mod}__${id}.png`) }
    order.push(book.id); console.log(bookName, '— Überblick +', i, 'Funktionen')
  }

  // 10 · Einstellungen & Administration
  const eb = await ensureBook(books, '10 · Einstellungen & Administration', 'Vollständige Erklärung aller Administrations- und Einstellungsbereiche.')
  for (let i = 0; i < SETTINGS.length; i++) await addPage(eb.id, `${pad(i)} · ${SETTINGS[i][0]}`, SETTINGS[i][1], 'shots', SETTINGS[i][2])
  order.push(eb.id); console.log('Einstellungen:', SETTINGS.length)

  // Shelf-Reihenfolge setzen
  const shelves = (await api('GET', '/api/shelves')).data || []
  const shelf = shelves.find(s => /Benutzerhandbuch/.test(s.name))
  if (shelf) await api('PUT', `/api/shelves/${shelf.id}`, { books: order })
  console.log('DONE — Bücher:', order.length)
}
run().catch(e => { console.error('ERR', e); process.exit(1) })
