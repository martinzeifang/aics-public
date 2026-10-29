// Reichhaltige Wiki-Generierung aus der echten In-App-Hilfe (help/*.ts) + Screenshots.
// Baut die Modul-Bücher (Überblick + je Tab) neu auf und ein Einstellungen-Buch.
import fs from 'node:fs'
import { MODULE_HELP } from './help/index.ts'
import { MOD_TABS as MOD_TABS_ALT } from './tabs.mjs'
import { CRA_PROZESS } from './cra_prozess.mjs'
// Erfasste Tabs haben Vorrang: `erfassen.mjs` liest sie aus der laufenden
// Anwendung, die gepflegte Liste ist nur noch Rückfall.
const ERFASST = (() => {
  try {
    const roh = JSON.parse(fs.readFileSync(new URL('./tabs.generiert.json', import.meta.url), 'utf8'))
    const m = {}
    for (const [mod, tabs] of Object.entries(roh)) m[mod] = tabs.map(t => [t[0], t[1]])
    return m
  } catch { return {} }
})()
const MOD_TABS = { ...MOD_TABS_ALT, ...ERFASST }
import { MODULE_BOOK, DESC, cleanTitle } from './content2.mjs'

const BASE = process.env.WIKI_BASE || 'http://docker02:6875'
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
  ['Navigation & Bedienung', `# Navigation & Bedienung\n\nObere Leiste: **Modul-Navigation**; oben rechts **KI-Provider-Status** (☁️/🖥️), Konto und Einstellungen. Innerhalb eines Moduls links ein **Projekt** wählen; der Hauptbereich zeigt gruppierte **Tabs** (Dashboard, Anforderungen, Dokumentation, Berichte …). Der **❓-Hilfe**-Knopf bietet kontextbezogene Hilfe je Bereich.\n\n## Die Projektliste links\n\nDie Liste ist in **allen** Modulen gleich aufgebaut und bietet ab zwei Einträgen drei Werkzeuge:\n\n- **🔍 Suche** über Firma, Produkt und Projektname. Mehrere Begriffe werden UND-verknüpft; **Esc** leert das Feld. Unter dem Feld steht, wie viele der Einträge noch sichtbar sind.\n- **↕ Sortierung** — *Name A–Z* oder *Zuletzt geändert*. Bei „zuletzt geändert" wandern auch die **Firmengruppen** mit nach oben, sonst stünde die eben bearbeitete Bewertung unter einer alphabetisch weit hinten liegenden Firma.\n- **Filter** je Modul: Produktklasse (CRA), Framework (Risikobewertung), Einrichtungsklasse (NIS2), Rolle (DSGVO), Organisation/KI-System (AI Act), Berater. Ein Filter erscheint nur, wenn es im Bestand **mindestens zwei verschiedene Werte** gibt — ein Auswahlfeld mit einer Option könnte nichts eingrenzen.\n\nFirmen lassen sich mit **▸/▾** ein- und ausklappen; der Zustand bleibt erhalten. Bei aktiver Suche sind alle Gruppen offen, damit kein Treffer verborgen bleibt.`, 'home.png'],
  ['Die Projekt-Werkzeugleiste', `# Die Projekt-Werkzeugleiste\n\nÜber dem Inhalt steht in **jedem** der sechs Compliance-Module dieselbe Leiste mit sieben Handlungen. Sie gelten dem **ganzen Projekt**, nicht der Liste, die gerade offen ist — deshalb sind sie aus jedem Tab erreichbar.\n\n| Knopf | Was er tut |\n|---|---|\n| 🤖 **Automatische Massenbewertung** | Mehrere Objekte auswählen und je Objekt von der KI bewerten lassen — mit Fortschritt und Abbruch. |\n| 🧮 **Massenbewertung (Sammel-Prompt)** | Einen gemeinsamen Prompt für mehrere Objekte erzeugen, in die KI einfügen und die Antwort geprüft übernehmen. |\n| 🐙 **Issues anlegen** | Für die offenen Punkte des Projekts GitHub-/GitLab-Issues im Stapel anlegen. Bereits verknüpfte Objekte werden übersprungen. |\n| 🔄 **Issue-Status abgleichen** | Status und neue Kommentare aller verknüpften Issues abrufen. **Bewertungen ändert das nie** — ein geschlossenes Issue ist kein Nachweis. Stattdessen wird das Objekt sichtbar als „⚠️ Neubewertung erforderlich" markiert, mit Anlass und Ticketnummer. |\n| 📥 **Issue-Feedback übernehmen** | Inhalt und Kommentare der verknüpften Issues in den Freitext des Objekts übernehmen (Kommentar, Notiz, Bemerkung). Die Bewertung bleibt unverändert. |\n| 🧪 **Neubewertung aus Issues** | Zeigt je Objekt, was die verknüpften Issues sagen: Status, Kommentarzahl und ob die Markierung schon steht. Diese Ansicht **liest nur** — frisch geholt wird mit „Issue-Status abgleichen". |\n| 📜 **Audit-Log** | Der Revisionspfad dieses Projekts: wer wann welche Handlung ausgelöst hat. Wo das Modul zusätzlich ein Änderungsprotokoll auf Feldebene führt (Risikobewertung), steht es mit in derselben Liste, je Zeile mit seiner Quelle. |\n\nRechts daneben stehen die Knöpfe, die es nur in diesem Modul gibt — etwa „➕ KI-System anlegen" (AI Act), „🔍 Repo-Scan" (CRA) oder „🗑️ Projekt löschen".\n\n> **Warum der Abgleich nichts erledigt:** Ein geschlossenes Ticket belegt nicht, dass eine Anforderung erfüllt ist. Die Anwendung markiert deshalb nur und überlässt die Bewertung dem Menschen. Das gilt in allen sechs Modulen gleich.`, 'home.png'],
  ['Issues und KI am einzelnen Objekt', `# Issues und KI am einzelnen Objekt\n\nÖffnet man eine Anforderung, eine Prüffrage, ein Risiko oder eine Kontrolle, stehen unter den Bewertungsfeldern zwei Abschnitte — in allen Modulen gleich aufgebaut.\n\n## 🤖 KI-Bewertung\n\n- **🤖 KI-Bewertung (Prompt → Antwort)** — Prompt erzeugen, in ChatGPT/Claude einfügen, Antwort zurückgeben. Vor dem Senden zeigt eine **Datenvorschau**, was übermittelt wird.\n- **🤖 Automatische Bewertung** — ruft den konfigurierten Provider direkt auf; der Lauf ist live sichtbar und abbrechbar.\n- **🔄 Neubewertung mit Issue-Feedback** — bezieht den Inhalt der verknüpften Issues in die Bewertung ein.\n- Im Prompt-Fenster lassen sich **eigene Hinweise** ergänzen („Der Schwerpunkt liegt in der Fertigung, die IT ist ausgelagert"). Sie wirken zusätzlich, ohne die geforderte Antwortform zu gefährden, und lassen sich je Projekt merken.\n- Steht am Text ein **Herkunftshinweis**, stammt der Entwurf von der KI und ist noch nicht fachlich geprüft. Ein Klick bestätigt die Prüfung mit Namen und Zeitpunkt.\n\n## 🔗 Verknüpfte Issues\n\n- **➕ Issue anlegen** — Provider, Repository, Titel und Beschreibung sind vorbelegt; leer gelassen gilt das im Projekt hinterlegte Repository.\n- **🔗 Bestehendes verknüpfen** — ein vorhandenes Issue über seine URL anhängen; Provider und Nummer werden erkannt.\n- **🔄 Status abgleichen** — wie in der Projektleiste, nur für dieses Objekt.\n- **📥 Issue-Inhalt importieren** — Text einfügen oder aus den verknüpften Issues laden. Der Text landet im Freitext, die Bewertung bleibt unverändert.\n- **✕** löst eine Verknüpfung wieder.`, 'home.png'],
]

const MOD_KEYS = ['cra','nis2','aiact','dsgvo','compliance-audit','wiba','soc','risikobewertung','firmen']
const LANDING = { cra:'cra.png', nis2:'nis2.png', aiact:'aiact.png', dsgvo:'dsgvo.png',
  'compliance-audit':'compliance-audit.png', wiba:'wiba.png', soc:'soc.png',
  risikobewertung:'risikobewertung.png', firmen:'firmen.png' }
// Hilfe-Schlüssel (camelCase) gegen Screenshot-/Routen-Schlüssel (kebab).
// Hilfe-, Screenshot- und Routen-Schlüssel sind identisch (z. B. 'compliance-audit').
const SHOT_KEY = {}

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
    if (mod === 'cra') {
      let p = 0
      for (const [titel, md, img] of CRA_PROZESS) {
        p++
        await addPage(book.id, `A${p} · ${titel}`, md, 'shots2', img)
      }
      console.log('  CRA-Prozess:', CRA_PROZESS.length, 'Seiten')
    }
    const areas = new Map((h?.areas || []).map(a => [a.id, a]))
    let i = 0
    const sk = SHOT_KEY[mod] || mod
    for (const [id, label] of (MOD_TABS[sk] || MOD_TABS[mod] || [])) {
      i++
      await addPage(book.id, `${pad(i)} · ${cleanTitle(label)}`,
                    areaMd(mod, id, label, areas.get(id)), 'shots2', `${sk}__${id}.png`)
    }
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
