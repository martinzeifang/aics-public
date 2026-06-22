// Inhalte des AICS-Benutzerhandbuchs (BookStack). Bilder via {{img:datei}}.
export const SHELF = {
  name: 'AI Compliance Suite — Benutzerhandbuch',
  description: 'Anwenderdokumentation für alle Module der AI Compliance Suite (ohne Gutachten). Mit Screenshots aus der Live-Umgebung.',
}

const KI_BOX = `
> **🤖 KI-Assistenten — Transparenz**
> KI-gestützte Funktionen laufen über den **konfigurierten Provider**: entweder eine **lokale LLM** (Ollama, datenschutzfreundlich, keine Datenübermittlung nach außen) oder eine **Cloud-API** (z. B. Anthropic/OpenAI/Google). Vor jeder Übermittlung zeigt eine **Datenvorschau** an, *welche* Daten gesendet werden; bei Cloud-Nutzung ist eine ausdrückliche Bestätigung nötig. Der Fortschritt ist **live einsehbar** (Tokens, Dauer, Provider), und das **Ergebnis** wird vor der Übernahme angezeigt. KI-Ausgaben sind fachlich zu prüfen.`

export const BOOKS = [
  {
    name: '1 · Erste Schritte',
    description: 'Anmeldung, Navigation, KI-Provider-Einstellungen und Stammdaten.',
    pages: [
      { name: 'Überblick', md: `# AI Compliance Suite — Überblick

Die **AI Compliance Suite (AICS)** ist eine Plattform zum Verwalten von Compliance-Anforderungen, Risiken, Nachweisen und Berichten über mehrere Regelwerke hinweg — u. a. **CRA, NIS2, EU AI Act, DSGVO, DORA, WiBA**, ergänzt um **Risikobewertung** und ein **SOC**-Modul.

Dieses Handbuch beschreibt die Bedienung aus Anwendersicht. Jedes Modul hat ein eigenes Kapitel. Wiederkehrende Konzepte:

- **Firmen/Projekte:** Arbeit wird je Firma in Projekten organisiert.
- **Bewertungen 0–5:** Anforderungen werden auf einer Reifegrad-Skala bewertet (0 = nicht bewertet … 5 = vollständig umgesetzt).
- **KI-Assistenten:** unterstützen Bewertung und Dokumenterstellung — lokal oder per Cloud, immer transparent.
- **Dokumente & Berichte:** rechtlich geforderte Dokumente werden erstellt, geprüft und als Word/PDF exportiert.
${KI_BOX}` },
      { name: 'Anmeldung', md: `# Anmeldung

Rufen Sie die Suite im Browser auf und melden Sie sich mit E-Mail und Passwort an. Alternativ ist die Anmeldung per **Passkey** möglich.

{{img:login.png}}

- **E-Mail / Passwort:** Standard-Anmeldung.
- **Auf diesem Gerät angemeldet bleiben:** verlängert die Sitzung auf vertrauenswürdigen Geräten.
- **Passkey:** passwortlose Anmeldung (sofern für Ihr Konto eingerichtet).

Nach der Anmeldung landen Sie auf der Startseite bzw. der Firmenübersicht. Ihre **Rolle** (unten rechts sichtbar) bestimmt, welche Module und Aktionen Ihnen zur Verfügung stehen.` },
      { name: 'Navigation & Bedienung', md: `# Navigation & Bedienung

Die obere Leiste enthält die **Modul-Navigation**; oben rechts finden Sie den **KI-Provider-Status**, Konto und Einstellungen.

{{img:home.png}}

- **Modulreiter:** wechseln zwischen Firmen, Risikobewertung, CRA, NIS2, AI-Act, DSGVO, DORA, WiBA, SOC.
- **Provider-Badge** (oben rechts): zeigt, ob aktuell eine **🖥️ lokale LLM** oder eine **☁️ Cloud** konfiguriert ist.
- **Hilfe (❓):** je Modul kontextbezogene Hilfe.
- **Statusleiste unten:** Verbindungsstatus, aktuelles Modul, Rolle und Version.

Innerhalb eines Moduls wählen Sie links ein **Projekt**; der Hauptbereich zeigt **Tabs** (z. B. Dashboard, Anforderungen, Dokumente, Berichte).` },
      { name: 'KI-Provider & Einstellungen', md: `# KI-Provider & Einstellungen

Die KI-Funktionen nutzen entweder eine **lokale LLM (Ollama)** oder eine **Cloud-API**. Die Auswahl erfolgt zentral in den Einstellungen (Admin).

{{img:admin-settings.png}}

**Lokale LLM (Ollama):** datenschutzfreundlich — Daten verlassen Ihr Netzwerk nicht. Modell und Adresse werden im Ollama-Bereich konfiguriert.

{{img:admin-ollama.png}}

**Cloud-Provider:** Über eine **Anbieter-Auswahl** (Anthropic, OpenAI, Google …) konfigurieren Sie API-Schlüssel und Modell; das passende Modell lässt sich per Dropdown wählen.
${KI_BOX}

**Word-/PDF-Vorlagen** (Admin) erlauben modulübergreifend eigene Export-Vorlagen.

{{img:admin-templates.png}}` },
      { name: 'Firmen & Stammdaten', md: `# Firmen & Stammdaten

Im Modul **Firmen** verwalten Sie die Unternehmen, für die Sie Compliance betreiben. Firmen verknüpfen modulübergreifend Projekte, Risiken und Nachweise.

{{img:firmen.png}}

- **Firma anlegen/bearbeiten:** Name, Organisationsdaten, ggf. zentrale SLAs.
- **Verknüpfung:** Projekte in CRA/NIS2/AI-Act/DSGVO/DORA/WiBA werden einer Firma zugeordnet (gemeinsames **Risiko-Cockpit**).
- **Nachweise/Evidence:** hochgeladene Belege stehen modulübergreifend als Nachweis-Vorschläge zur Verfügung.` },
    ],
  },
  {
    name: '2 · CRA — Cyber Resilience Act',
    description: 'Cyber Resilience Act (EU 2024/2847): Anforderungen, Pflicht-Dokumentation, Konformität.',
    pages: [
      { name: 'Überblick', md: `# CRA — Cyber Resilience Act

Das CRA-Modul unterstützt die Konformität nach **Verordnung (EU) 2024/2847**: **32 Anforderungen + 10 OWASP Proactive Controls**, Pflicht-Dokumentation, Schwachstellen-/SBOM-Verwaltung und Konformitätsbewertung.

{{img:cra.png}}

Links wählen Sie ein **CRA-Projekt** (je Produkt/Firma). Der Hauptbereich bietet Dashboard, Anforderungen, Pflicht-Dokumentation, Dokumente und Berichte.` },
      { name: 'Projekt anlegen & Dashboard', md: `# Projekt anlegen & Dashboard

Legen Sie über **„+ Neues CRA-Projekt"** ein Projekt an (Produktname, Firma, Produktklasse). Nach Auswahl zeigt das **Dashboard** den Gesamt-Reifegrad und die Kapitel.

{{img:cra-detail.png}}

- **Produktklasse** (Default / Important I+II / Critical) bestimmt den Konformitätsbewertungsweg (Annex III/IV).
- **Reifegrad-Gauge** und **Kapitelkarten** zeigen den Fortschritt je Bereich.` },
      { name: 'Anforderungen bewerten (KI)', md: `# Anforderungen bewerten

Im Reiter **Anforderungen** bewerten Sie jede CRA-Anforderung auf der Skala **0–5** mit Kommentar und Maßnahmen.

Zwei Wege:
1. **🤖 KI-Bewertung (Prompt → Antwort):** Prompt kopieren, in einen externen KI-Assistenten einfügen, JSON-Antwort zurückspielen.
2. **⚡ Automatische Bewertung:** direkter Aufruf des konfigurierten Providers (lokal **oder** Cloud) mit **Live-Fenster** (Phasen, Tokens, Provider) und **Ergebnis-Zusammenfassung** (Score, ausführliche Begründung, konkrete Maßnahmen, Normbezug).

${KI_BOX}

Die KI liefert eine **aussagekräftige, strukturierte** Bewertung; Sie prüfen und übernehmen sie. Maßnahmen lassen sich als **GitHub/GitLab-Issue** verfolgen.` },
      { name: 'Pflicht-Dokumentation & SBOM', md: `# Pflicht-Dokumentation (C1–C5) & SBOM

Der Bereich **Pflicht-Doku** erfasst die CRA-Nachweise:
- **C1 SBOM** — Software Bill of Materials je Release. SBOMs werden aus dem Repository **automatisch erkannt** und sind als **„📄 Abrufen"-Link** direkt zugänglich.
- **C2 PSIRT** — Schwachstellen-Meldeprozess (Intake, SLAs, Disclosure-Policy).
- **C3 Schwachstellen** — Vulnerability-Sync (GitHub/GitLab).
- **C4 Supportzeitraum** — Zeitraum für Sicherheitsupdates (Art. 13(8)).
- **C5 Threat-Model** — Bedrohungsmodell-Framework.

{{img:cra.png}}

Per **Auto-Erkennung** werden vorhandene Belege aus dem verknüpften Repository (SECURITY.md, Releases, Advisories, CI-Artefakte) idempotent übernommen.` },
      { name: 'KI-Vollständigkeitsprüfung & Issues', md: `# KI-Vollständigkeitsprüfung & Knopfdruck-Issue

Pflicht-Dokumente (z. B. **Technische Dokumentation nach Annex VII**) lassen sich gegen ihre rechtliche **Soll-Checkliste** automatisch prüfen.

Im Dokument-Editor öffnet **„⚡ Vollständigkeit prüfen (KI)"** eine Datenvorschau, anschließend läuft die Prüfung live über den konfigurierten Provider (lokal oder Cloud). Je Pflichtpunkt erhalten Sie **erfüllt / teilweise / fehlt** mit Begründung; der Checklisten-Status wird automatisch gesetzt.

Sind Punkte offen, erzeugt **„Issue für fehlende Inhalte erstellen"** ein GitHub/GitLab-Issue mit den fehlenden Inhalten als Aufgabenliste.
${KI_BOX}` },
      { name: 'Konformität, Berichte & CE', md: `# Konformität, Berichte & CE

- **Konformitätsbewertung:** Bewertungsweg (Modul A / B+C / H / EUCC) je Produktklasse; EU-Konformitätserklärung (Annex V) und CE-Status.
- **Berichte:** Im **Berichts-Center** erzeugen Sie Readiness-/Nachweis-Berichte als **Word/PDF** über einen Zeitraum; eine **KI-Management-Zusammenfassung** ist optional zuschaltbar.
- **Dokumente:** versionierte, freigebbare Dokumente (Status Entwurf → final → freigegeben) mit DOCX/PDF-Export.` },
      { name: 'CRA-Konformität dieser Dokumentation (Annex II)', md: `# CRA-Konformität dieser Dokumentation

Dieses Benutzerhandbuch ist Teil der nach CRA geforderten **Informationen und Anleitungen für den Nutzer (Annex II)**. Es deckt insbesondere ab:

| Annex-II-Punkt | Abschnitt in dieser Doku |
|---|---|
| (1) Hersteller/Kontakt | Erste Schritte · Firmen & Stammdaten |
| (2) Anlaufstelle für Schwachstellen | CRA · Pflicht-Doku (PSIRT) |
| (3) Produkt-Identifikation | CRA · Projekt anlegen |
| (4) Bestimmungsgemäße Verwendung | CRA · Überblick |
| (5) Cybersicherheitsrelevante Eigenschaften | CRA · Anforderungen |
| (6) Sichere Inbetrieb-/Außerbetriebnahme | Erste Schritte · Navigation |
| (7) Bezug von Sicherheitsupdates | CRA · Pflicht-Doku (Supportzeitraum) |
| (8) Ende des Supportzeitraums | CRA · Konformität (Art. 13(8)) |

Ergänzend stellt das CRA-Modul die **Technische Dokumentation (Annex VII)** und die **EU-Konformitätserklärung (Annex V)** als verwaltete, exportierbare Dokumente bereit.` },
    ],
  },
  {
    name: '3 · NIS2',
    description: 'NIS2-Richtlinie (EU 2022/2555): Anforderungen, Assistenten, Meldewesen.',
    pages: [
      { name: 'Überblick', md: `# NIS2

Das NIS2-Modul unterstützt die Umsetzung der **NIS2-Richtlinie (EU 2022/2555)** mit Anforderungskatalog (N1–N5-Bereiche), Risiko-Cockpit, Assistenten und Meldewesen.

{{img:nis2.png}}` },
      { name: 'Dashboard & Anforderungen', md: `# Dashboard & Anforderungen

Nach Projektauswahl zeigt das Dashboard den Reifegrad über die NIS2-Bereiche.

{{img:nis2-dashboard.png}}

Im Reiter **Anforderungen** bewerten Sie wie in CRA (0–5) — wahlweise per Copy/Paste-Prompt oder **automatisch** über den konfigurierten Provider (lokal/Cloud) mit Live-Ansicht und Ergebnis-Zusammenfassung.

{{img:nis2-detail.png}}
${KI_BOX}` },
      { name: 'Assistenten & Dokumente', md: `# Assistenten & Dokumente

Der Tab **🤖 Assistenten** bündelt NIS2-Wizards (z. B. Klassifizierung, Incident-Meldungen 24h/72h/Final, Lieferketten-Assessment, Richtlinien). Ergebnisse lassen sich als **Dokument speichern**.

Der Tab **📄 Dokumente** verwaltet die rechtlich erzeugungspflichtigen Dokumente (Soll-Ist-Katalog, Editor, DOCX/PDF-Export) inkl. KI-Vollständigkeitsprüfung.` },
    ],
  },
  {
    name: '4 · EU AI Act',
    description: 'EU AI Act (EU 2024/1689): Anforderungen, Risikoklasse, Konformität, OWASP-LLM.',
    pages: [
      { name: 'Überblick', md: `# EU AI Act

Das AI-Act-Modul unterstützt die **Verordnung (EU) 2024/1689**: Risikoklassifizierung, Anforderungen (HR/GOV/DATA/OPS), Konformität/CE und ein **OWASP-LLM-Register**.

{{img:aiact.png}}` },
      { name: 'Dashboard, Anforderungen & Assistenten', md: `# Dashboard, Anforderungen & Assistenten

{{img:aiact-dashboard.png}}

- **Anforderungen** bewerten (0–5) per Copy/Paste oder automatisch (lokal/Cloud).
- **Assistenten:** Art.-5-Screening, FRIA, High-Risk-Assessment, Transparenz, Human Oversight, Post-Market-Monitoring, Model-Card u. a.
- **OWASP-LLM-Register:** LLM-spezifische Risiken mit Auto-Detect und Issue-Anbindung.

{{img:aiact-detail.png}}
${KI_BOX}` },
    ],
  },
  {
    name: '5 · DSGVO (DSMS)',
    description: 'Datenschutz-Management-System: VVT, TOM, DSFA, Betroffenenrechte, Berichte.',
    pages: [
      { name: 'Überblick', md: `# DSGVO — Datenschutz-Management-System

Das DSGVO-Modul ist ein vollständiges **DSMS**: Verzeichnis von Verarbeitungstätigkeiten (VVT, Art. 30), TOM-Katalog (Art. 32 + SDM), DSFA (Art. 35/36), Betroffenenrechte, Drittlandtransfer, Löschkonzept, Einwilligung, DSB.

{{img:dsgvo.png}}` },
      { name: 'Bereiche, Kontrollen & Berichte', md: `# Bereiche, Kontrollen & Berichte

{{img:dsgvo-detail.png}}

- **Dashboard:** Reifegrad und offene Fristen über alle DSMS-Bereiche.
- **VVT / TOM / DSFA / weitere Register:** je eigener Tab mit strukturierter Erfassung.
- **Kontrollen & Jahresbericht:** jährlicher Kontrollplan mit Freigaben (GF/DSB) und signiertem Jahresbericht.
- **Berichts-Center:** Einzelberichte je Bereich als Word/PDF.
${KI_BOX}` },
    ],
  },
  {
    name: '6 · DORA',
    description: 'Digital Operational Resilience Act (EU 2022/2554): 5 Pfeiler.',
    pages: [
      { name: 'Überblick & Anforderungen', md: `# DORA

Das DORA-Modul deckt den **Digital Operational Resilience Act (EU 2022/2554)** über fünf Pfeiler ab. Anforderungen werden wie in den anderen Modulen bewertet (0–5, Copy/Paste oder automatisch lokal/Cloud).

{{img:dora.png}}

{{img:dora-detail.png}}
${KI_BOX}` },
    ],
  },
  {
    name: '7 · WiBA',
    description: 'BSI „Weg in die Basis-Absicherung": Prüffragen als Kontrollen.',
    pages: [
      { name: 'Überblick & Prüffragen', md: `# WiBA — Weg in die Basis-Absicherung

Das WiBA-Modul bildet die **BSI-WiBA-Prüffragen** als Kontrollen ab (19 Themen / 257 Prüffragen) für einen KMU-Nachweis eines sicheren IT-Betriebs.

{{img:wiba.png}}

- **Antwortmodell:** offen / ja / nein / nicht relevant.
- **Nachweise:** bei der Firma hochgeladene Belege + DSGVO-TOM-Maßnahmen als Vorschläge.
- **Befunde:** „Nein"-Antworten lassen sich als Risiken in einer verknüpften Risikobewertung führen.

{{img:wiba-detail.png}}
${KI_BOX}` },
    ],
  },
  {
    name: '8 · SOC',
    description: 'Security Operations Center: Alarm-Triage, Incidents, Berichte.',
    pages: [
      { name: 'Überblick', md: `# SOC — Security Operations Center

Das SOC-Modul unterstützt Alarm-Triage (Wazuh), Incident-Bearbeitung, MITRE-ATT&CK-Zuordnung, Use-Cases und ein Berichts-Center. KI-Analysen (Alarm/Incident/Lagebericht) laufen über den konfigurierten Provider (lokal/Cloud).

{{img:soc.png}}
${KI_BOX}` },
    ],
  },
  {
    name: '9 · Risikobewertung',
    description: 'Framework-basierte Risikobewertung mit automatischer KI-Bewertung.',
    pages: [
      { name: 'Überblick & automatische Bewertung', md: `# Risikobewertung

Das Modul bewertet Risiken anhand wählbarer Frameworks (z. B. STRIDE). Risiken können **automatisch** bewertet werden — über die lokale LLM **oder** die Cloud.

{{img:risikobewertung.png}}

- **Automatische Bewertung:** Live-Fenster (Phasen, Tokens, Provider) + Ergebnis-Zusammenfassung (Risiko-Label/-Wert, Begründung, Empfehlungen, Normbezug).
- **Neubewertung mit Issue-Feedback:** aktualisiert die Bewertung anhand von Issue-/Audit-Kontext und zeigt die Risiko-Veränderung.
- **Massenbewertung:** mehrere Risiken über einen Sammel-Prompt.
${KI_BOX}` },
    ],
  },
]
