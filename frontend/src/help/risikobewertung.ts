// Auto-generiert (#926) — Modul-Hilfe-Inhalt.
import type { ModuleHelp } from './types'

export const risikobewertungHelp: ModuleHelp = {
  "title": "Risikobewertung",
  "regulation": "EU Cyber Resilience Act (Verordnung (EU) 2024/2847), insb. Art. 13 und Anhang I; methodisch gestützt auf ISO/IEC 27005:2022, IEC 62443-3-2:2020 und ISO/SAE 21434:2021",
  "purpose": "Das Modul Risikobewertung dient der strukturierten Cyber- und Software-Risikoabschätzung von Produkten, Systemen und einzelnen Schwachstellen. Es stellt mehrere etablierte Bewertungsframeworks bereit, berechnet je Bedrohung einen quantifizierten Risikowert und unterstützt damit Risikoanalyse, Maßnahmenableitung und Konformitätsnachweis.",
  "legalBasis": {
    "title": "Regulatorische und normative Grundlagen",
    "intro": "Der Cyber Resilience Act verlangt von Herstellern eine Cybersicherheits-Risikobewertung über den gesamten Produktlebenszyklus; deren Ergebnisse müssen die Auswahl der Sicherheitsanforderungen begründen und dokumentiert werden. Die hier hinterlegten Frameworks setzen anerkannte Normen für das Informationssicherheits- und Cybersecurity-Risikomanagement um, sodass die Bewertung methodisch nachvollziehbar und prüffähig ist.",
    "bullets": [
      "CRA Art. 13 Abs. 2 i.V.m. Anhang I Teil I: Produkte mit digitalen Elementen sind auf Basis einer Cybersicherheits-Risikobewertung zu konzipieren, zu entwickeln und herzustellen (Security by Design).",
      "CRA Art. 13 Abs. 3 und Abs. 5: Die Risikobewertung ist Teil der technischen Dokumentation (Anhang VII) und während des Unterstützungszeitraums fortzuschreiben.",
      "ISO/IEC 27005:2022: Leitlinien fuer den Prozess des Informationssicherheits-Risikomanagements (Identifikation, Analyse, Bewertung und Behandlung von Risiken).",
      "IEC 62443-3-2:2020: Risikobewertung und Security-Level-Festlegung (SL-T) fuer industrielle Automatisierungs- und Steuerungssysteme (IACS).",
      "ISO/SAE 21434:2021: Threat Analysis and Risk Assessment (TARA) als verbindliche Methodik des Cybersecurity-Engineerings fuer Strassenfahrzeuge, ergaenzend zu UNECE R155 (WP.29).",
      "Branchenspezifisch fuer Finanzinstitute: IT-Risikoanforderungen aus BAIT/VAIT, MaRisk, EBA-Leitlinien zur IKT- und Sicherheitsrisikosteuerung sowie DORA (Verordnung (EU) 2022/2554)."
    ]
  },
  "implementation": {
    "title": "Vorgehen im Modul",
    "intro": "Sie waehlen pro Bewertungsobjekt ein passendes Framework, erfassen die geforderten Bewertungsfaktoren ueber Auswahlfelder und erhalten automatisch einen Risikowert mit Risikolevel und Berechnungsdetail. Die Ergebnisse lassen sich exportieren und in Berichte uebernehmen.",
    "bullets": [
      "Framework gemaess Einsatzkontext waehlen (siehe Framework-Uebersicht): allgemeine Software, KI/LLM, Embedded/Automotive, organisationszentriert oder Finanzbereich.",
      "Bewertungsfaktoren ueber die vordefinierten Skalen erfassen; das Modul berechnet den Score erst, wenn alle Pflichtfelder gesetzt sind.",
      "Die Berechnungslogik je Framework ist transparent: das Detail-Feld zeigt die Formel (z. B. Wahrscheinlichkeit x Impact oder AP-Summe -> Security/Feasibility-Level).",
      "Risikolevel werden farblich gekennzeichnet (gruen = vernachlaessigbar/akzeptabel bis rot = hoch/kritisch), um Priorisierung und Maßnahmenbedarf sichtbar zu machen.",
      "Bewertungen versioniert dokumentieren und bei neuen Erkenntnissen oder Schwachstellen (z. B. CVE-Eingang) neu bewerten, um die CRA-Lebenszyklus-Pflicht zu erfuellen.",
      "Konsistent dasselbe Framework je Produktklasse verwenden, damit Risikowerte vergleichbar bleiben; Framework-Wechsel begruenden und dokumentieren."
    ]
  },
  "moduleSpecific": {
    "title": "Besonderheiten des Moduls",
    "intro": "Kern des Moduls ist die Auswahl des richtigen Frameworks fuer den jeweiligen Bewertungskontext. Jedes Framework bringt eine eigene Skala, Berechnungsformel und einen erlaeuternden Infotext mit.",
    "bullets": [
      "Sechs Frameworks stehen zur Verfuegung: Finanzinstitute, STRIDE, STRIDE-LLM, HEAVENS, OCTAVE Allegro und TARA.",
      "STRIDE und STRIDE-LLM nutzen eine 5x5-Matrix (Eintrittswahrscheinlichkeit x Auswirkung, 1-25); STRIDE-LLM ergaenzt LLM-spezifische Bedrohungskategorien nach OWASP LLM Top 10 (Prompt-Injection, Insecure Output Handling, Training-Data-Poisoning u. a.) sowie Bias und Halluzination.",
      "HEAVENS und TARA bewerten zunaechst das Angriffspotenzial nach Common-Criteria-Faktoren (Expertise, Systemkenntnis, Zeitfenster, Ausruestung, bei TARA zusaetzlich Zeitaufwand) und kombinieren es mit dem Impact ueber die SFOP-Dimensionen (Safety, Financial, Operational, Privacy).",
      "OCTAVE Allegro ist qualitativ und asset-/organisationszentriert: Eintrittswahrscheinlichkeit x Summe aus fuenf Impact-Bereichen (Reputation, Finanzen, Produktivitaet, Sicherheit/Gesundheit, Bußgelder).",
      "Das Framework Finanzinstitute verwendet die einfache additive Skala (Eintrittswahrscheinlichkeit + Schadenspotenzial - 1, Bereich 1-7) und dient zugleich als Basis fuer die CVE-Bewertung.",
      "Zu jedem Framework liefert ein Infopanel Herkunft, Bewertungsparameter, Formel, Risikolevel und CRA-Relevanz."
    ]
  },
  "frameworks": [
    {
      "name": "STRIDE",
      "ref": "Microsoft Security Development Lifecycle (Kohnfelder & Garg, 1999); im Modul um 5x5-Matrix quantifiziert",
      "whenToUse": "Allgemeines Software-Threat-Modeling in der Entwurfs- und Entwicklungsphase. Die sechs Kategorien (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege) helfen, Bedrohungen systematisch zu identifizieren und Gegenmaßnahmen abzuleiten (CRA Art. 13, Security by Design)."
    },
    {
      "name": "STRIDE-LLM",
      "ref": "OWASP Top 10 for LLM Applications (LLM01-LLM10), Erweiterung von STRIDE",
      "whenToUse": "Fuer KI- und LLM-basierte Produkte und Funktionen. Deckt LLM-spezifische Risiken wie Prompt-Injection, Insecure Output Handling, Training-Data-Poisoning, Excessive Agency sowie Bias und Halluzination ab; sinnvoll im Zusammenspiel mit Anforderungen des EU AI Act."
    },
    {
      "name": "HEAVENS",
      "ref": "Volvo Cars Research & Technology (2014) auf Basis ISO/SAE 21434 und Common Criteria",
      "whenToUse": "Fuer eingebettete und cyber-physische Systeme sowie IoT-Geraete. Bewertet das Angriffspotenzial nach Common-Criteria-Faktoren und kombiniert es mit den SFOP-Impact-Dimensionen; geeignet fuer wesentliche/kritische Produkte nach CRA Anhang I/II."
    },
    {
      "name": "OCTAVE Allegro",
      "ref": "CERT Coordination Center, Carnegie Mellon University (2007); verwandt mit ISO/IEC 27001",
      "whenToUse": "Asset- und organisationszentrierte, qualitative Risikobewertung aus der Betreiberperspektive. Geeignet fuer kleinere Teams und ISMS-Kontexte sowie fuer Lebenszyklus-Risiken nach CRA Art. 13 Abs. 2 und NIS2-Pflichten."
    },
    {
      "name": "TARA",
      "ref": "ISO/SAE 21434:2021 (Road Vehicles - Cybersecurity Engineering); auch UNECE WP.29 / R155",
      "whenToUse": "Fuer vernetzte Fahrzeuge und sicherheitskritische E/E- bzw. Embedded-Systeme. Empfohlene Methode fuer CRA-konforme Risikoanalysen vernetzter Produkte: Attack Feasibility Rating x Impact Rating ueber eine Risikomatrix."
    },
    {
      "name": "Risikobewertung Finanzinstitute",
      "ref": "BAIT/VAIT, MaRisk, EBA-Leitlinien zur IKT-Sicherheit; ergaenzt durch DORA (Verordnung (EU) 2022/2554)",
      "whenToUse": "Fuer Banken, Versicherer und Finanzdienstleister. Einfache Skala Eintrittswahrscheinlichkeit x Schadenspotenzial fuer schnelle, aufsichtskonforme Einstufung; dient im Modul zugleich als Basis der CVE-Bewertung."
    }
  ],
  "links": [
    {
      "label": "Risikobewertung-Quellcode (frameworks.py)",
      "href": "/home/mzeifang/Dokumente/github/AI_Compliance_Suite/risikobewertung/frameworks.py"
    },
    {
      "label": "Modul-Dokumentation",
      "href": "docs/modules/"
    }
  ],
  "module": "risikobewertung"
}
