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
