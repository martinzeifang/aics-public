// Auto-generiert (#926) — Modul-Hilfe-Inhalt.
import type { ModuleHelp } from './types'
import { docsUrl } from './docsUrl'

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
      "Sieben Frameworks stehen zur Verfuegung: Finanzinstitute, STRIDE, STRIDE-LLM, HEAVENS, OCTAVE Allegro, TARA und EU-AI-Act (Art. 9 KI-Verordnung).",
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
    },
    {
      "name": "EU-AI-Act",
      "ref": "Verordnung (EU) 2024/1689 (KI-Verordnung), Art. 9 Risikomanagementsystem",
      "whenToUse": "Fuer Hochrisiko-KI-Systeme nach EU AI Act. Bewertet Risiken ueber den gesamten KI-Lebenszyklus (Design, Development, Deployment, Monitoring) je Risikokategorie (Safety, Fundamental Rights, Bias u. a.) als Eintrittswahrscheinlichkeit x Auswirkung (5x5-Matrix). Direkt mit dem AI-Act-Modul (A3 Risikomanagement) verknuepfbar."
    }
  ],
  "areas": [
    {
      "id": "dashboard",
      "title": "📊 Dashboard",
      "zweck": "Einstieg und Überblick je Projekt: gewähltes Framework, Risikoverteilung nach Level und Bearbeitungsstand – Ausgangspunkt für die Risikoarbeit.",
      "rechtsgrundlage": "CRA Art. 13 Abs. 2 (Risikobewertung über den Lebenszyklus); methodisch ISO/IEC 27005",
      "pflichtfelder": [
        "Projekt anlegen: Name (eindeutig, stabil), Framework (siehe Framework-Übersicht), optional Beschreibung und Unternehmen/Firma.",
        "Firmen-Zuordnung (unternehmen): nötig, damit das Risiko-Cockpit firmenweit aggregieren kann."
      ],
      "anleitung": "1) Projekt mit passendem Framework anlegen (Framework je Produktklasse konsistent wählen). 2) Firma/Unternehmen zuordnen. 3) Risikoverteilung im Dashboard als Steuerungssicht nutzen und in den Tab ‚Risiken' wechseln.",
      "tipps": [
        "Framework vor der ersten Risikoerfassung festlegen – ein späterer Wechsel ändert die Skala und macht Werte unvergleichbar.",
        "Ohne Firmen-Zuordnung erscheint das Projekt nicht im firmenweiten Cockpit."
      ]
    },
    {
      "id": "cockpit",
      "title": "📊 Risiko-Cockpit",
      "zweck": "Firmenweite, modulübergreifende Read-only-Aggregation aller offenen Risiken (Risikobewertung + CRA-Schwachstellen) der zugeordneten Firma.",
      "rechtsgrundlage": "Risikobasierter Ansatz (CRA Art. 13; NIS2 Art. 21; DSGVO Art. 24/32)",
      "pflichtfelder": [
        "Keine Eingabe – read-only Aggregation pro Firma (firmen_id).",
        "Voraussetzung: Das Projekt ist einer Firma zugeordnet."
      ],
      "anleitung": "1) Firmen-Zuordnung des Projekts sicherstellen. 2) Offene Risiken firmenweit sichten. 3) Behandlung in den jeweiligen Risiko-Einträgen (Tab ‚Risiken') bzw. CRA vornehmen – das Cockpit spiegelt deren Stand.",
      "tipps": [
        "CRA-Schwachstellen werden gegen Risikobewertungs-Risiken dedupliziert (CRA primär).",
        "Das Cockpit ist eine Sicht, kein Eingabeort – Risiken werden in ihren Quellen gepflegt."
      ]
    },
    {
      "id": "risiken",
      "title": "⚠️ Risiken",
      "zweck": "Kern des Moduls: Erfassung und Bewertung der einzelnen Risiken nach dem gewählten Framework mit automatisch berechnetem, quantifiziertem Risikowert.",
      "rechtsgrundlage": "CRA Art. 13 Abs. 2/3 i. V. m. Anhang I; ISO/IEC 27005:2022 (Risikoidentifikation, -analyse, -bewertung, -behandlung)",
      "pflichtfelder": [
        "Bezeichnung/Name des Risikos und Beschreibung.",
        "Bedrohung und betroffene Schwachstelle (was wird wodurch bedroht).",
        "Bewertungsfaktoren des Frameworks: je nach Framework Eintrittswahrscheinlichkeit × Auswirkung (STRIDE/STRIDE-LLM/AI-Act, 5×5) bzw. Angriffspotenzial + SFOP-Impact (HEAVENS/TARA) bzw. additive Skala (Finanzinstitute) bzw. Impact-Summe (OCTAVE).",
        "Maßnahmen (Risikobehandlung) und Verantwortlicher.",
        "Status (offen/behandelt – is_resolved) zur Nachverfolgung."
      ],
      "anleitung": "1) Risiko mit Bedrohung und Schwachstelle benennen. 2) Alle Bewertungsfaktoren über die vordefinierten Skalen setzen – der Score (mit Level und Berechnungsdetail) entsteht erst bei vollständigen Pflichtfeldern. 3) Maßnahmen ableiten und Verantwortlichen zuordnen. 4) Bei neuen Erkenntnissen (z. B. CVE-Eingang) neu bewerten und versioniert dokumentieren (CRA-Lebenszyklus). 5) Behandelte Risiken auf ‚resolved' setzen.",
      "tipps": [
        "Score erst vollständig, wenn alle Faktoren gesetzt sind – das Detail-Feld zeigt die Formel transparent.",
        "Innerhalb eines Projekts dasselbe Framework durchhalten, damit Werte vergleichbar bleiben.",
        "Aus offenen Risiken lassen sich GitHub/GitLab-Issues erzeugen und überwachen (Auto-Resolve bei Issue-Schluss)."
      ]
    },
    {
      "id": "bericht",
      "title": "📄 Bericht",
      "zweck": "Export der Risikobewertung als Nachweis-/Berichtsdokument für die technische Dokumentation und das Risikomanagement.",
      "rechtsgrundlage": "CRA Art. 13 Abs. 3/5 i. V. m. Anhang VII (Bestandteil der technischen Dokumentation)",
      "pflichtfelder": [
        "Auswahl des Projekts und ggf. Berichtsformat/Vorlage.",
        "Voraussetzung: Risiken sind im Tab ‚Risiken' vollständig bewertet."
      ],
      "anleitung": "1) Projekt mit vollständig bewerteten Risiken wählen. 2) Bericht erzeugen. 3) Als Bestandteil der technischen Dokumentation ablegen und bei Aktualisierungen neu erzeugen.",
      "tipps": [
        "Die Berichtsqualität hängt direkt von der Vollständigkeit der Risikobewertung ab.",
        "Bericht bei jeder Neubewertung aktualisieren – die CRA-Doku ist über den Unterstützungszeitraum fortzuschreiben."
      ]
    }
  ],
  "links": [
    {
      "label": "Modul-Dokumentation",
      "href": docsUrl('/modules/risikobewertung/')
    }
  ],
  "module": "risikobewertung"
}
