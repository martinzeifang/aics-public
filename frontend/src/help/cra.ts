// Auto-generiert (#926) — Modul-Hilfe-Inhalt.
import type { ModuleHelp } from './types'
import { docsUrl } from './docsUrl'

export const craHelp: ModuleHelp = {
  "title": "CRA",
  "regulation": "Verordnung (EU) 2024/2847 (Cyber Resilience Act, CRA)",
  "purpose": "Das CRA-Modul unterstützt Hersteller von Produkten mit digitalen Elementen dabei, die Cybersicherheitsanforderungen des Cyber Resilience Act nachzuweisen. Es ordnet das Produkt in die korrekte Produktklasse ein, bewertet die Erfüllung der OWASP Proactive Controls (C1-C10) als Reifegrad und sammelt die verpflichtende Sicherheitsdokumentation für die Konformitätsbewertung.",
  "legalBasis": {
    "title": "Was der CRA verlangt",
    "intro": "Der Cyber Resilience Act verpflichtet Hersteller, Produkte mit digitalen Elementen über den gesamten Lebenszyklus sicher zu gestalten und mit dem Markt in Verkehr gebrachte Produkte zu pflegen. Die grundlegenden Cybersicherheitsanforderungen und die Anforderungen an das Schwachstellenmanagement sind in Anhang I festgelegt; Herstellerpflichten und Meldepflichten regeln Art. 13 und 14. Die Produktklasse bestimmt den zulässigen Konformitätsbewertungsweg.",
    "bullets": [
      "Grundlegende Cybersicherheitsanforderungen an das Produkt (secure by design/default, sichere Konfiguration, Schutz von Daten, Angriffsfläche minimieren): Anhang I Teil I.",
      "Anforderungen an das Schwachstellenmanagement (Erkennen/Beheben von Schwachstellen, regelmäßige Sicherheitsupdates, SBOM, Coordinated Vulnerability Disclosure): Anhang I Teil II.",
      "Sorgfaltspflichten des Herstellers (Risikobewertung, technische Dokumentation Anhang VII, Support-/Update-Zeitraum, CE-Kennzeichnung): Art. 13.",
      "Meldepflichten: aktiv ausgenutzte Schwachstellen und schwerwiegende Sicherheitsvorfälle sind über die Single-Reporting-Plattform an das CSIRT und die ENISA zu melden (Frühwarnung binnen 24 h): Art. 14.",
      "Konformitätsbewertung je nach Produktklasse: Selbstbewertung (Standardprodukte) bzw. einbezogene Verfahren/notifizierte Stelle für Important Klasse I/II und Critical: Art. 32 i. V. m. Anhang III/IV.",
      "Fristen: Meldepflichten nach Art. 14 gelten ab 11. September 2026; die vollständige Anwendung der Verordnung gilt ab 11. Dezember 2027."
    ]
  },
  "implementation": {
    "title": "Vorgehen im Modul",
    "intro": "Im Modul wird zunächst die Produktklasse bestimmt, daraus der Konformitätsweg abgeleitet, anschließend werden die OWASP Proactive Controls bewertet und die Pflicht-Dokumentation gesammelt. KI-Wizards und Repo-/Code-Analyse unterstützen das Vorausfüllen der Anforderungen; das Ergebnis wird als Konformitätsbericht exportiert.",
    "bullets": [
      "Produkt einordnen: Klasse (default / Important Klasse I / Important Klasse II / Critical) wählen; das Modul leitet daraus den zulässigen Konformitätsbewertungsweg ab.",
      "OWASP Proactive Controls C1-C10 durchgehen und je Control einen Reifegrad 0-5 vergeben; jede Control ist auf konkrete CRA-Artikel/Anhang-I-Punkte gemappt.",
      "Evidenzen hinterlegen: Für jede Anforderung Nachweise verknüpfen (z. B. SECURITY.md, Threat Model, SBOM, Scan-Reports). Der Evidence-Hint je Control nennt typische Belege.",
      "Repository-/Code-Analyse und Auto-Detect nutzen, um vorhandene Pflicht-Doku (SBOM, SECURITY.md, CVD-Policy) automatisch zu erkennen und Antworten vorzuschlagen.",
      "Pflicht-Dokumentation prüfen: SBOM, PSIRT/Coordinated Vulnerability Disclosure, Threat Model, CVE-/Schwachstellen-Handling und Support-Zeitraum vollständig dokumentieren.",
      "Konformitätsbericht exportieren (Reifegrad-Übersicht, offene Lücken, Evidenzliste) als Grundlage für die technische Dokumentation nach Anhang VII."
    ]
  },
  "moduleSpecific": {
    "title": "Besonderheiten des CRA-Moduls",
    "intro": "Das Modul kombiniert die regulatorische CRA-Struktur mit dem praxisnahen OWASP-Proactive-Controls-Framework und einer Reifegradbewertung. Klassifizierung und Fristen sind dabei zentral.",
    "bullets": [
      "Produktklassen steuern den Aufwand: default = Selbstbewertung; Important Klasse I/II und Critical erfordern strengere Verfahren bzw. notifizierte Stelle.",
      "OWASP Proactive Controls C1-C10 (v3) dienen als operationalisierte Checkliste mit Mapping auf Anhang I und Art. 13.",
      "Reifegrad-Skala 0-5 je Control macht Fortschritt und Lücken messbar und priorisierbar.",
      "Verpflichtende Artefakte werden gebündelt: SBOM, PSIRT/CVD-Prozess, Threat Model, CVE-Handling, definierter Support-/Update-Zeitraum.",
      "Zeitliche Planung: Meldepflichten ab September 2026, volle Anwendung ab Dezember 2027 - das Modul hilft, den Reifegrad rechtzeitig anzuheben.",
      "Auto-Detect und KI-Wizards reduzieren manuellen Aufwand, ersetzen aber nicht die fachliche Prüfung der Konformitätsbewertung."
    ]
  },
  "areas": [
    {
      "id": "dashboard",
      "title": "📊 Dashboard",
      "zweck": "Überblick über Produktklasse, Konformitätsweg, OWASP-/Anforderungs-Reifegrad und offene Lücken des Projekts.",
      "rechtsgrundlage": "Art. 13 CRA (Sorgfaltspflichten des Herstellers)",
      "pflichtfelder": [
        "Keine direkte Eingabe – das Dashboard verdichtet die Daten der Fach-Tabs.",
        "Voraussetzung: Produktklasse gewählt (steuert den zulässigen Bewertungsweg)."
      ],
      "anleitung": "1) Produktklasse/Projektstammdaten prüfen. 2) Reifegrad-Kacheln und offene Lücken ablesen. 3) Priorisierte Lücken im jeweiligen Fach-Tab (OWASP, Anforderungen, Dokumentation) schließen.",
      "tipps": ["Kennzahlen aktualisieren sich aus den Fach-Tabs – Lücken hier sind der Einstieg in die Bearbeitung."]
    },
    {
      "id": "risikocockpit",
      "title": "📊 Risiko-Cockpit",
      "zweck": "Firmenweite, modulübergreifende Read-only-Sicht auf offene Risiken (Risikobewertung) und Schwachstellen (cra_vuln) der zugeordneten Firma.",
      "rechtsgrundlage": "Anhang I Teil I CRA (risikobasierte Produktsicherheit)",
      "pflichtfelder": [
        "Keine Eingabe – Aggregation pro Firma (firmen_id); CRA-Schwachstellen werden gegen die Risikobewertung dedupliziert."
      ],
      "anleitung": "1) Firmen-Zuordnung des Projekts sicherstellen (sonst keine Aggregation). 2) Offene High/Critical zuerst sichten. 3) Behandlung in der verknüpften Risikobewertung bzw. über die Schwachstellen-/Korrektur-Tabs.",
      "tipps": ["Risiken werden in der Risikobewertung gepflegt; das Cockpit spiegelt nur deren Stand."]
    },
    {
      "id": "pflichtdoku",
      "title": "📋 Dokumentation (Pflicht-Doku)",
      "zweck": "Sammeln und Bewerten der CRA-Pflichtartefakte (SBOM, Coordinated Vulnerability Disclosure/SECURITY.md, Threat Model, CVE-Handling, Support-/Update-Zeitraum) inkl. Auto-Detect und Schwachstellen-Sync.",
      "rechtsgrundlage": "Anhang I Teil II CRA (Schwachstellenmanagement); Art. 13 (technische Doku)",
      "pflichtfelder": [
        "SBOM vorhanden + Format/Referenz (Anhang I Teil II Nr. 1).",
        "Coordinated Vulnerability Disclosure / SECURITY.md (Kontakt + Prozess).",
        "Sicherheitsupdate-Prozess und definierter Support-/Update-Zeitraum.",
        "Threat Model / Risikobewertung verknüpft.",
        "Schwachstellen-Sync (GitHub/GitLab) nach cra_vuln – mit Triage je Befund."
      ],
      "anleitung": "1) Repo-/Code-Analyse und Auto-Detect laufen lassen (erkennt SBOM, SECURITY.md, CVD-Policy). 2) Erkannte Artefakte bestätigen oder Nachweis ergänzen. 3) Schwachstellen-Sync ausführen und Befunde triagieren. 4) Fehlende Pflichtartefakte erzeugen und verlinken.",
      "tipps": [
        "Auto-Detect schlägt nur vor – die fachliche Bestätigung des Nachweises bleibt erforderlich.",
        "Support-/Update-Zeitraum muss explizit benannt sein (mind. 5 Jahre als Richtwert)."
      ]
    },
    {
      "id": "meldungen",
      "title": "🚨 Meldungen (Art. 14)",
      "zweck": "Fristengesteuertes Meldemanagement für aktiv ausgenutzte Schwachstellen und schwerwiegende Sicherheitsvorfälle an CSIRT/ENISA über die Single-Reporting-Plattform.",
      "rechtsgrundlage": "Art. 14 CRA (Frühwarnung 24h · Meldung 72h · Abschluss 14 Tage bzw. 1 Monat); Art. 14(8) Nutzer-Advisory",
      "pflichtfelder": [
        "Typ: 'vuln_exploited' (aktiv ausgenutzte Schwachstelle, Abschluss 14 Tage) oder Vorfall (Abschluss 1 Monat).",
        "Titel und Beschreibung des Vorfalls/der Schwachstelle.",
        "Erkannt am (startet die 24h/72h/14d-Fristenkette – siehe Ampel).",
        "Betroffene Mitgliedstaaten (betroffene_ms) und vermutete Ursache.",
        "Mitigation/Sofortmaßnahmen.",
        "Gemeldet-am je Stufe: Frühwarnung (24h), Meldung (72h), Abschlussbericht.",
        "Optional: Verknüpfung zur Schwachstelle (vuln_id) und Nutzer-Advisory (Art. 14(8))."
      ],
      "anleitung": "1) Meldung sofort bei Kenntnis anlegen, 'erkannt am' korrekt setzen. 2) Typ wählen (Schwachstelle vs. Vorfall) – bestimmt die Abschlussfrist. 3) Frühwarnung binnen 24h absetzen und Datum erfassen. 4) Vollständige Meldung binnen 72h. 5) Abschlussbericht binnen 14 Tagen (Schwachstelle) bzw. 1 Monat (Vorfall). 6) Bei Bedarf Nutzer-Advisory erstellen.",
      "tipps": [
        "Die Fristen laufen ab 'erkannt am' – die Ampel zeigt Restzeit (gelb < 50 %, rot < 10 %).",
        "Meldepflichten nach Art. 14 gelten ab 11.09.2026."
      ]
    },
    {
      "id": "konformitaet",
      "title": "✅ Konformität (Art. 32 / Annex VIII)",
      "zweck": "Konformitätsbewertung je Release: Wahl des Bewertungswegs, Nachweis-Checkliste je Modul, Notified-Body/EUCC, CE-Status und strukturierte EU-Konformitätserklärung (DoC) mit Freigabe-/Lock-Workflow.",
      "rechtsgrundlage": "Art. 32 CRA i. V. m. Anhang VIII (Bewertungsverfahren); Annex V (Inhalt DoC); CE nach Art. 30",
      "pflichtfelder": [
        "Release-Version (eindeutig je Bewertungsrecord).",
        "Produktklasse und Bewertungsweg: A (Selbstbewertung), B+C, H oder EUCC – je nach Klasse zulässig.",
        "Nachweis-Checkliste je Modul (z. B. technische Doku; bei B+C/H/EUCC zusätzliche Belege/Zertifikat).",
        "Bei NB-Verfahren: Notified-Body-Kennnummer; bei EUCC: EUCC-Level/-Zertifikat.",
        "CE-Status und strukturierter DoC (Annex V) inkl. Version.",
        "Freigabe-Status (entwurf → freigegeben) – nach Freigabe gesperrt (#1220-A)."
      ],
      "anleitung": "1) Release-Record anlegen, Produktklasse + zulässigen Bewertungsweg wählen. 2) Nachweis-Checkliste je Modul abarbeiten (Default = Selbstbewertung A). 3) Bei Important I/II/Critical NB-Kennnummer bzw. EUCC-Zertifikat erfassen. 4) Bewertung abschließen – erst dann ist die DoC ausstellbar. 5) DoC (Annex V) ausstellen, CE setzen. 6) Freigeben (Lock).",
      "tipps": [
        "Die DoC ist erst nach abgeschlossenem Bewertungsweg ausstellbar (Gate).",
        "Produktklasse bestimmt den zulässigen Weg – Selbstbewertung A genügt nicht für Important/Critical."
      ]
    },
    {
      "id": "akteure",
      "title": "🏷️ Akteure (Art. 19–22)",
      "zweck": "Erfassung und Pflichtnachweis der weiteren Wirtschaftsakteure (Importeur, Händler, Bevollmächtigter) mit rollenspezifischer Checkliste.",
      "rechtsgrundlage": "Art. 19 (Bevollmächtigter), Art. 20 (Importeure), Art. 22 (Händler) CRA",
      "pflichtfelder": [
        "Rolle: importeur | haendler | bevollmaechtigter.",
        "Name, Anschrift, Kontakt.",
        "Produkt (auf das sich die Rolle bezieht).",
        "Rollen-Checkliste (rollenspezifische Sorgfaltspflichten als Nachweise).",
        "Bei Bevollmächtigtem: Mandats-Referenz (mandat_ref) und Aufgabenumfang.",
        "Status (offen/erledigt)."
      ],
      "anleitung": "1) Je Akteur einen Eintrag mit Rolle anlegen. 2) Stammdaten (Name/Anschrift/Kontakt) und betroffenes Produkt erfassen. 3) Rollen-Checkliste abarbeiten (z. B. Importeur: Prüfung CE/DoC/technische Doku vor Inverkehrbringen). 4) Beim Bevollmächtigten Mandat hinterlegen und Aufgabenumfang beschreiben.",
      "tipps": [
        "Der Bevollmächtigte braucht ein schriftliches Mandat (Art. 19) – ohne mandat_ref unvollständig.",
        "Importeure/Händler dürfen nur Produkte bereitstellen, die CE-konform sind."
      ]
    },
    {
      "id": "korrektur",
      "title": "↩️ Korrekturmaßnahmen (Rückruf)",
      "zweck": "Management von Korrektur-, Rücknahme- und Rückruf­maßnahmen bei nicht-konformen Produkten inkl. Behördeninformation und Audit-Trail.",
      "rechtsgrundlage": "Art. 13 Abs. 19–22 CRA (Korrekturmaßnahmen, Rücknahme/Rückruf, Information der Marktüberwachung)",
      "pflichtfelder": [
        "Maßnahmentyp: korrektur | ruecknahme | rueckruf.",
        "Titel und Auslöser (Nicht-Konformitäts-Befund).",
        "Betroffene Versionen und betroffene Mitgliedstaaten.",
        "Behörde informiert (Flag) + Datum + Behördenname.",
        "Optional: Verknüpfung zu Schwachstelle (vuln_id) / Meldung (meldung_id).",
        "Status (offen → in_arbeit → abgeschlossen) + Abschlussdatum + Beschreibung."
      ],
      "anleitung": "1) Bei Nicht-Konformität eine Maßnahme mit Auslöser anlegen. 2) Maßnahmentyp und betroffene Versionen/Staaten bestimmen. 3) Bei Risiko die Marktüberwachungsbehörde(n) informieren und Datum/Name dokumentieren. 4) Maßnahme umsetzen, Beschreibung pflegen, abschließen. Alle Schritte werden im Audit-Trail festgehalten.",
      "tipps": [
        "Bei erheblichem Cyberrisiko sind die Behörden zu informieren (Art. 13(19) ff.) – Flag und Datum nicht vergessen.",
        "Verknüpfung mit Schwachstelle/Meldung stellt die Nachvollziehbarkeit her."
      ]
    },
    {
      "id": "traceability",
      "title": "🔗 Traceability (Annex VII)",
      "zweck": "Vollständigkeitsmatrix der technischen Akte: ordnet jedem Annex-VII-Baustein Nachweise/Anforderungen/OWASP-Controls zu und zeigt belegt/fehlt.",
      "rechtsgrundlage": "Art. 13 Abs. 1 CRA i. V. m. Anhang VII (Inhalt der technischen Dokumentation)",
      "pflichtfelder": [
        "Je Annex-VII-Baustein: zugeordnete(s) Dokument(e)/Nachweis(e).",
        "Verknüpfung zu Anforderung (anforderung_id) und/oder OWASP-Control (owasp_id).",
        "Baustein-Zuordnung (annex_baustein) je Dokument."
      ],
      "anleitung": "1) Dokumente im Dokumente-Tab hochladen und je Dokument Anforderung/OWASP/Annex-Baustein taggen. 2) In der Matrix prüfen, welche Annex-VII-Bausteine noch unbelegt sind (rot). 3) Lücken durch zusätzliche Nachweise schließen. 4) Vollständige Matrix als Grundlage für die technische Akte (Annex VII) nutzen.",
      "tipps": [
        "Ein rot markierter Baustein bedeutet: technische Akte unvollständig.",
        "Pflege primär über die Tags der Dokumente – die Matrix verdichtet daraus."
      ]
    },
    {
      "id": "dokumente",
      "title": "📄 Dokumente",
      "zweck": "Ablage und Verwaltung hochgeladener Nachweise (SBOM, SECURITY.md, Threat Model, Scan-Reports) mit Tagging für Anforderung/OWASP/Annex-Baustein.",
      "rechtsgrundlage": "Art. 13 CRA (technische Dokumentation/Nachweisführung)",
      "pflichtfelder": [
        "Datei + aussagekräftiger Name; Dokumenttyp.",
        "Tags: Anforderung (anforderung_id), OWASP-Control (owasp_id), Annex-Baustein (annex_baustein) – steuern die Traceability-Matrix."
      ],
      "anleitung": "1) Nachweis hochladen und eindeutig benennen. 2) Mit Anforderung/OWASP/Annex-Baustein taggen. 3) Bei Aktualisierung neue Version ablegen statt überschreiben.",
      "tipps": ["Konsequentes Tagging füllt automatisch die Traceability-Matrix (Annex VII)."]
    },
    {
      "id": "requirements",
      "title": "✅ Anforderungen",
      "zweck": "Bewertung der CRA-Detailanforderungen je Kapitel mit Reifegrad und Nachweisbezug; eigene Anforderungen ergänzbar.",
      "rechtsgrundlage": "Anhang I CRA (grundlegende Cybersicherheits- und Schwachstellen­management-Anforderungen); Art. 13",
      "pflichtfelder": [
        "Je Anforderung: Reifegrad 0–5 und Nachweis/Begründung.",
        "Bei eigenen Anforderungen: Kapitel, Titel, Beschreibung, Hinweise, Gewichtung."
      ],
      "anleitung": "1) Kapitelweise durchgehen. 2) Reifegrad je Anforderung realistisch setzen. 3) Nachweis verknüpfen (Dokument/Repo-Beleg). 4) Lücken in Korrektur-/Maßnahmen oder Issues überführen.",
      "tipps": ["Reifegrad 5 nur mit konkretem Nachweis – das fließt in den Gesamt-Reifegrad und die technische Akte."]
    },
    {
      "id": "owasp",
      "title": "🛡️ OWASP Secure by Design (C1–C10)",
      "zweck": "Operationalisierte Sicherheits-Checkliste: OWASP Proactive Controls C1–C10 mit Reifegrad und Mapping auf Anhang I / Art. 13.",
      "rechtsgrundlage": "Anhang I Teil I CRA (secure by design/default), gemappt über OWASP Proactive Controls v3",
      "pflichtfelder": [
        "Je Control C1–C10: Reifegrad 0–5.",
        "Evidenz/Nachweis je Control (Evidence-Hint nennt typische Belege)."
      ],
      "anleitung": "1) Jede Control C1–C10 durchgehen. 2) Reifegrad vergeben und mind. einen Nachweis verknüpfen. 3) Die Artikel-/Anhang-I-Zuordnung je Control beachten. 4) Schwache Controls in Maßnahmen überführen.",
      "tipps": ["Auto-Detect kann erste Reifegrade vorschlagen – fachlich prüfen, bevor sie als Nachweis gelten."]
    },
    {
      "id": "assistenten",
      "title": "🤖 Assistenten",
      "zweck": "KI-gestützte Wizards (Copy/Paste-Prompts), die Entwürfe für Pflicht-Doku, Anforderungs-/OWASP-Bewertung und Texte liefern.",
      "rechtsgrundlage": "— (Hilfsmittel; die Konformitätsbewertung bleibt beim Hersteller)",
      "pflichtfelder": [
        "Keine Pflichtfelder – Eingaben sind je Assistent kontextabhängig."
      ],
      "anleitung": "1) Assistenten wählen. 2) Prompt mit Projektkontext erzeugen, in das KI-Tool kopieren. 3) Antwort zurückspielen/prüfen. 4) Ergebnis in den jeweiligen Fach-Tab übernehmen.",
      "tipps": ["KI-Vorschläge fachlich gegenprüfen – sie ersetzen keine Konformitätsbewertung."]
    },
    {
      "id": "fragebogen",
      "title": "📥 Fragebogen",
      "zweck": "Import bestehender Fragebogen-Antworten als Ausgangsbasis für die Anforderungs-/OWASP-Bewertung.",
      "rechtsgrundlage": "— (Erhebungs-/Import-Hilfsmittel)",
      "pflichtfelder": [
        "Quelldatei/-eingabe des Fragebogens.",
        "Zuordnung der Antworten zu Anforderungen/Controls."
      ],
      "anleitung": "1) Fragebogen-Daten einlesen. 2) Antworten den passenden Anforderungen/Controls zuordnen. 3) In die Bewertung (Anforderungen/OWASP) übernehmen und mit Nachweisen verfeinern.",
      "tipps": ["Import liefert nur einen Startpunkt – Reifegrade und Nachweise anschließend fachlich verifizieren."]
    },
    {
      "id": "risikoanalyse",
      "title": "🔍 Risikoanalyse",
      "zweck": "Produktbezogene Cybersicherheits-Risikoanalyse als Grundlage für secure-by-design-Entscheidungen und die technische Doku.",
      "rechtsgrundlage": "Art. 13 Abs. 2/3 CRA i. V. m. Anhang I (Cybersicherheits-Risikobewertung)",
      "pflichtfelder": [
        "Identifizierte Risiken/Bedrohungen je Asset/Komponente.",
        "Bewertung (Eintritt/Auswirkung) und abgeleitete Maßnahmen.",
        "Bezug zu Anforderungen/OWASP-Controls und zur verknüpften Risikobewertung."
      ],
      "anleitung": "1) Produkt/Komponenten und Angriffsfläche erfassen. 2) Bedrohungen identifizieren und bewerten. 3) Maßnahmen ableiten und mit Anforderungen/Controls verknüpfen. 4) Ergebnis in die technische Doku übernehmen.",
      "tipps": ["Die Risikoanalyse ist Pflichtbestandteil der technischen Akte (Anhang VII) – Ergebnisse dort referenzieren."]
    },
    {
      "id": "bericht",
      "title": "📄 Bericht",
      "zweck": "Export des Konformitäts-/Reifegradberichts (Maßnahmenplan, Detailanforderungen, OWASP, Quellen) als Grundlage der technischen Dokumentation.",
      "rechtsgrundlage": "Art. 13 CRA i. V. m. Anhang VII (technische Dokumentation)",
      "pflichtfelder": [
        "Auswahl der Berichtsabschnitte (Maßnahmenplan, Detailanforderungen, OWASP, Quellen) und Format."
      ],
      "anleitung": "1) Vorab alle Fach-Tabs (OWASP, Anforderungen, Pflicht-Doku, Konformität) finalisieren. 2) Abschnitte wählen. 3) Bericht erzeugen und als Teil der technischen Akte ablegen.",
      "tipps": ["Die Berichtsqualität hängt direkt vom gepflegten Reifegrad und den verknüpften Nachweisen ab."]
    }
  ],
  "links": [
    {
      "label": "CRA-Modul-Doku (Online)",
      "href": docsUrl('/modules/cra/')
    },
    {
      "label": "OWASP Proactive Controls",
      "href": "https://owasp.org/www-project-proactive-controls/"
    },
    {
      "label": "Verordnung (EU) 2024/2847 (EUR-Lex)",
      "href": "https://eur-lex.europa.eu/eli/reg/2024/2847/oj"
    }
  ],
  "module": "cra"
}
