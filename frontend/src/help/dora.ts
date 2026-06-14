// Auto-generiert (#926) — Modul-Hilfe-Inhalt.
import type { ModuleHelp } from './types'
import { docsUrl } from './docsUrl'

export const doraHelp: ModuleHelp = {
  "title": "DORA",
  "regulation": "Verordnung (EU) 2022/2554 (Digital Operational Resilience Act, DORA), ergänzt durch die Richtlinie (EU) 2022/2556 sowie technische Regulierungs- und Durchführungsstandards (RTS/ITS) der ESAs (EBA, ESMA, EIOPA). Anwendbar seit dem 17. Januar 2025.",
  "purpose": "Das Modul DORA unterstützt Finanzunternehmen dabei, die Anforderungen an die digitale operationale Resilienz strukturiert zu erheben, zu dokumentieren und nachzuweisen. Es bildet die fünf Säulen der Verordnung ab und hilft, Lücken im IKT-Risikomanagement, in der Vorfallbehandlung, beim Resilienztesting, im Drittparteienmanagement und beim Informationsaustausch zu identifizieren.",
  "legalBasis": {
    "title": "Was DORA verlangt",
    "intro": "DORA schafft einen einheitlichen Rahmen für die digitale operationale Resilienz im EU-Finanzsektor und gilt unmittelbar für ein breites Spektrum von Finanzunternehmen sowie über das Aufsichtsregime für kritische IKT-Drittdienstleister. Die Verordnung gliedert ihre Pflichten in fünf Säulen und wird durch verbindliche RTS/ITS der Europäischen Aufsichtsbehörden konkretisiert. Die Anforderungen unterliegen dem Proportionalitätsprinzip (Art. 4).",
    "bullets": [
      "Säule 1 - IKT-Risikomanagement: Einrichtung eines umfassenden, dokumentierten IKT-Risikomanagementrahmens unter Letztverantwortung des Leitungsorgans (Kapitel II, Art. 5-16); vereinfachter Rahmen für bestimmte Kleinunternehmen (Art. 16).",
      "Säule 2 - Behandlung und Meldung IKT-bezogener Vorfälle: Klassifizierung von Vorfällen und erheblichen Cyberbedrohungen sowie Meldung schwerwiegender IKT-Vorfälle an die zuständige Behörde mittels Erst-, Zwischen- und Abschlussmeldung (Kapitel III, Art. 17-23).",
      "Säule 3 - Tests der digitalen operationalen Resilienz: Regelmäßige Tests des IKT-Sicherheitsdispositivs sowie bedrohungsorientierte Penetrationstests (Threat-Led Penetration Testing, TLPT) mindestens alle drei Jahre für bedeutende Unternehmen (Kapitel IV, Art. 24-27).",
      "Säule 4 - Management des IKT-Drittparteienrisikos: Steuerung von Auslagerungen, vertragliche Mindestinhalte und Führung eines Informationsregisters über alle vertraglichen Vereinbarungen mit IKT-Drittdienstleistern (Kapitel V Abschnitt I, Art. 28-30).",
      "Aufsichtsrahmen für kritische IKT-Drittdienstleister: Benennung kritischer Anbieter (CTPPs) und deren direkte Überwachung durch einen federführenden Aufseher (Kapitel V Abschnitt II, Art. 31-44).",
      "Säule 5 - Informationsaustausch: Freiwilliger Austausch von Cyberbedrohungsinformationen und -erkenntnissen zwischen Finanzunternehmen (Kapitel VI, Art. 45)."
    ]
  },
  "implementation": {
    "title": "Vorgehen im Modul",
    "intro": "Im Modul werden die DORA-Anforderungen entlang der fünf Säulen als Fragenkatalog bzw. Anforderungsliste bearbeitet. Sie erfassen den Ist-Zustand pro Anforderung, dokumentieren Nachweise und leiten Maßnahmen für identifizierte Lücken ab. Der Workflow folgt dem Suite-Standard: Bestand erfassen (ingest), Bewertung vorbereiten (prepare) und Ergebnisse in das Ausgabedokument übernehmen (apply).",
    "bullets": [
      "Anwendungsbereich zuerst klären: Ist das Unternehmen ein Finanzunternehmen nach Art. 2 DORA und greift der vereinfachte Rahmen nach Art. 16 (Proportionalität)?",
      "IKT-Risikomanagementrahmen dokumentieren und die Letztverantwortung des Leitungsorgans (Art. 5) explizit nachweisen.",
      "Vorfall-Klassifizierungslogik und Meldewege anhand der RTS zu Art. 18/20 hinterlegen, inkl. Fristen für Erst-, Zwischen- und Abschlussmeldung.",
      "Testprogramm planen: jährliche Basistests dokumentieren und TLPT-Pflicht (Art. 26) für bedeutende Unternehmen prüfen.",
      "Informationsregister (Art. 28 Abs. 3) nach ITS-Vorgaben strukturiert pflegen und vertragliche Mindestinhalte (Art. 30) je Vertrag abgleichen.",
      "Lücken als Maßnahmen mit Verantwortlichen und Terminen erfassen; Nachweise (Policies, Verträge, Testberichte) referenzieren statt nur Freitext.",
      "Optional Issues für offene Maßnahmen in GitHub/GitLab erzeugen, um die Umsetzung nachzuverfolgen."
    ]
  },
  "moduleSpecific": {
    "title": "Besonderheiten des DORA-Moduls",
    "intro": "Das Modul ist auf die spezifische Struktur von DORA ausgerichtet und unterscheidet sich von rein zertifizierungsorientierten Modulen durch den direkten Bezug auf die Verordnungsartikel und die RTS/ITS.",
    "bullets": [
      "Strukturierung der gesamten Bewertung entlang der fünf DORA-Säulen.",
      "Berücksichtigung des Anwendungsbereichs nach Art. 2 (Finanzunternehmen) und des Proportionalitätsprinzips inkl. vereinfachtem Rahmen nach Art. 16.",
      "Eigener Block für das Management kritischer IKT-Drittdienstleister (CTPPs) und das Informationsregister.",
      "Abgrenzung der TLPT-Pflicht: Nicht jedes Finanzunternehmen ist TLPT-pflichtig - das Modul unterstützt die Identifikation bedeutender Unternehmen.",
      "Verweis auf einschlägige RTS/ITS der ESAs zu Vorfallmeldung, Informationsregister und IKT-Risikomanagementrahmen als Konkretisierung der Verordnung."
    ]
  },
  "areas": [
    {
      "id": "dashboard",
      "title": "📊 Dashboard",
      "zweck": "Überblick über den DORA-Umsetzungsstand: Reifegrad je Säule, kritische IKT-Drittdienstleister und offene Tests/Lücken des Projekts.",
      "rechtsgrundlage": "Art. 4 DORA (Proportionalität) i. V. m. Art. 5 (Letztverantwortung des Leitungsorgans)",
      "pflichtfelder": [
        "Keine direkte Eingabe – das Dashboard verdichtet die Daten der Fach-Tabs (Anforderungen, TPP, Testing).",
        "Voraussetzung: Anwendungsbereich nach Art. 2 geklärt (Finanzunternehmen, ggf. vereinfachter Rahmen Art. 16)."
      ],
      "anleitung": "1) Anwendungsbereich/Proportionalität prüfen. 2) Reifegrad je Säule und Zahl kritischer Drittdienstleister ablesen. 3) Lücken im jeweiligen Fach-Tab (Anforderungen, TPP-Register, Testing-Plan) schließen.",
      "tipps": ["Kennzahlen aktualisieren sich aus den Fach-Tabs – Lücken hier sind der Einstieg in die Bearbeitung."]
    },
    {
      "id": "requirements",
      "title": "📋 Anforderungen (5 Säulen)",
      "zweck": "Bewertung des DORA-Anforderungskatalogs entlang der fünf Säulen mit Reifegrad und Nachweisbezug; eigene Anforderungen ergänzbar.",
      "rechtsgrundlage": "DORA Kapitel II–VI: ICT-RM (Art. 5–16), ICT-IM (Art. 17–23), ICT-RT (Art. 24–27), ICT-TP (Art. 28–30), ICT-IS (Art. 45)",
      "pflichtfelder": [
        "Säule (pfeiler): ICT-RM | ICT-IM | ICT-RT | ICT-TP | ICT-IS.",
        "Je Anforderung: Reifegrad/Status und Nachweis/Begründung.",
        "Bei eigenen Anforderungen: Pfeiler, Titel, Beschreibung, Hinweise, Gewichtung.",
        "Letztverantwortung des Leitungsorgans (Art. 5) explizit nachweisen.",
        "Vorfall-Klassifizierung und Meldewege (Art. 18/20) inkl. Erst-/Zwischen-/Abschlussmeldung."
      ],
      "anleitung": "1) Säule für Säule durchgehen (ICT-RM → ICT-IM → ICT-RT → ICT-TP → ICT-IS). 2) Reifegrad je Anforderung realistisch setzen. 3) Nachweis verknüpfen (Policy, Vertrag, Testbericht) statt Freitext. 4) Lücken als Maßnahmen/Issues erfassen. 5) Vereinfachten Rahmen (Art. 16) berücksichtigen, falls einschlägig.",
      "tipps": [
        "Die Letztverantwortung des Leitungsorgans (Art. 5) ist ausdrücklich zu belegen.",
        "RTS/ITS der ESAs konkretisieren mehrere Anforderungen – die jeweils einschlägige Fassung heranziehen."
      ]
    },
    {
      "id": "tpp",
      "title": "🤝 TPP-Register (Art. 28–30)",
      "zweck": "Informationsregister aller IKT-Drittdienstleister mit Kritikalität, Risiko und Vertragsbezug – Grundlage des Drittparteien-Risikomanagements und der ITS-Meldung.",
      "rechtsgrundlage": "Art. 28 (Grundsätze, Informationsregister Abs. 3), Art. 29 (Vorabbewertung Konzentrationsrisiko), Art. 30 (vertragliche Mindestinhalte) DORA",
      "pflichtfelder": [
        "Name des Dienstleisters und Kategorie (cloud/saas/payment/data_center/security/other).",
        "Kritisch (Flag) – Dienstleister, die kritische/wichtige Funktionen unterstützen.",
        "Risiko-Score (0–5) und Status (active/onboarding/…).",
        "Beschreibung der erbrachten IKT-Dienstleistung.",
        "Vertrag-URL/-Referenz und Ansprechpartner."
      ],
      "anleitung": "1) Je Drittdienstleister einen Eintrag anlegen. 2) Kategorie und Kritikalität bestimmen (unterstützt er kritische/wichtige Funktionen?). 3) Risiko bewerten und Status setzen. 4) Vertrag verlinken und gegen die Mindestinhalte (Art. 30) abgleichen. 5) Register nach ITS-Vorgaben vollständig halten.",
      "tipps": [
        "Das Informationsregister (Art. 28 Abs. 3) ist der zuständigen Behörde vorzulegen – Vollständigkeit zählt.",
        "Kritische Dienstleister unterliegen strengeren vertraglichen Anforderungen (Art. 30 Abs. 3)."
      ]
    },
    {
      "id": "testing",
      "title": "🧪 Testing-Plan (Art. 24–27)",
      "zweck": "Planung und Nachweis der Resilienztests – von Basistests bis zum bedrohungsorientierten Penetrationstest (TLPT) für bedeutende Unternehmen.",
      "rechtsgrundlage": "Art. 24 (Programm), Art. 25 (Testarten), Art. 26 (TLPT mind. alle 3 Jahre), Art. 27 (Anforderungen an Tester) DORA",
      "pflichtfelder": [
        "Test-Typ: TLPT | vulnerability_scan | pen_test | bcm_drill | red_team | other.",
        "Scope (z. B. Online-Banking-Plattform inkl. Auth).",
        "Frequenz (z. B. jährlich, alle 3 Jahre) und nächster Termin.",
        "Status (planned/in_progress/…) und Verantwortlicher.",
        "Ergebnis/Testbericht."
      ],
      "anleitung": "1) Jährliche Basistests (Scans/Pen-Tests/BCM-Drills) planen und terminieren. 2) TLPT-Pflicht nach Art. 26 prüfen (bedeutende Unternehmen, mind. alle 3 Jahre). 3) Scope, Frequenz und Verantwortlichen je Test erfassen. 4) Durchführung, Ergebnis und Folgemaßnahmen dokumentieren.",
      "tipps": [
        "Nicht jedes Finanzunternehmen ist TLPT-pflichtig – die Bedeutsamkeit anhand Art. 26 prüfen.",
        "TLPT stellt besondere Anforderungen an die Tester (Art. 27) – das bei der Beauftragung berücksichtigen."
      ]
    }
  ],
  "links": [
    {
      "label": "DORA-Modul-Doku (Online)",
      "href": docsUrl('/modules/dora/')
    },
    {
      "label": "EUR-Lex: Verordnung (EU) 2022/2554 (DORA)",
      "href": "https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX:32022R2554"
    },
    {
      "label": "EUR-Lex: Richtlinie (EU) 2022/2556 (DORA-Begleitrichtlinie)",
      "href": "https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX:32022L2556"
    }
  ],
  "module": "dora"
}
