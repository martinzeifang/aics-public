// Auto-generiert (#926) — Modul-Hilfe-Inhalt.
import type { ModuleHelp } from './types'
import { docsUrl } from './docsUrl'

export const aiactHelp: ModuleHelp = {
  "title": "AI Act",
  "regulation": "Verordnung (EU) 2024/1689 (EU AI Act) zur Festlegung harmonisierter Vorschriften für Künstliche Intelligenz",
  "purpose": "Das Modul unterstützt die Einordnung von KI-Systemen und KI-Modellen entlang des risikobasierten Ansatzes des EU AI Act und leitet daraus die jeweils geltenden Pflichten ab. Es dokumentiert die Risikoklassifizierung, prüft Hochrisiko-Anforderungen und verfolgt die regulatorischen Fristen.",
  "legalBasis": {
    "title": "Rechtsgrundlage: EU AI Act (VO (EU) 2024/1689)",
    "intro": "Der AI Act verfolgt einen risikobasierten Ansatz und stuft KI je nach Gefährdungspotenzial in verbotene Praktiken, Hochrisiko, begrenztes Risiko und minimales Risiko ein. Je Klasse gelten unterschiedliche Pflichten; für General-Purpose-AI-Modelle (GPAI) bestehen eigene Regelungen. Maßgeblich sind insbesondere die Pflichten für Hochrisiko-Systeme (Art. 9-15) sowie die Transparenzpflichten (Art. 50).",
    "bullets": [
      "Verbotene Praktiken: Untersagung bestimmter KI-Anwendungen (z. B. manipulatives Verhalten, Social Scoring, ungezieltes Scraping zur Gesichtsdatenbank-Erstellung) gemäß Art. 5.",
      "Hochrisiko-Einstufung: KI-Systeme nach Annex III (u. a. biometrische Identifizierung, kritische Infrastruktur, Beschäftigung, Bildung) sowie sicherheitsrelevante Produkte nach Annex I (Art. 6).",
      "Risikomanagementsystem über den gesamten Lebenszyklus (Art. 9).",
      "Daten-Governance und Qualität der Trainings-, Validierungs- und Testdaten (Art. 10).",
      "Technische Dokumentation gemäß Anforderungen des Annex IV (Art. 11) und automatische Protokollierung/Logging (Art. 12).",
      "Transparenz und Bereitstellung von Informationen an Betreiber (Art. 13).",
      "Menschliche Aufsicht ('human oversight'), Art. 14.",
      "Genauigkeit, Robustheit und Cybersicherheit (Art. 15).",
      "Transparenzpflichten bei begrenztem Risiko: Offenlegung von KI-Interaktion, Kennzeichnung synthetischer/Deepfake-Inhalte (Art. 50).",
      "GPAI-Modelle: Pflichten zu technischer Dokumentation, Urheberrechts-Policy und Trainingsdaten-Zusammenfassung (Art. 53); zusätzliche Pflichten bei systemischem Risiko (Art. 51, 55)."
    ]
  },
  "implementation": {
    "title": "Vorgehen im Modul",
    "intro": "Beginnen Sie mit der Risikoklassifizierung des KI-Systems und arbeiten Sie anschließend die für die ermittelte Klasse geltenden Pflichten ab. Das Modul führt durch Klassifizierung, Pflichten-Checkliste je Klasse und die Nachverfolgung der Anwendungsfristen.",
    "bullets": [
      "Zuerst Use Case beschreiben und gegen die verbotenen Praktiken (Art. 5) prüfen, bevor eine Hochrisiko-Bewertung erfolgt.",
      "Risikoklasse bestimmen: Abgleich mit Annex III und den Ausnahmen nach Art. 6 Abs. 3 dokumentieren.",
      "Für Hochrisiko-Systeme die Pflichten-Checkliste (Art. 9-15) Punkt für Punkt mit Nachweisen/Evidenzen belegen.",
      "Konformitätsbewertung und EU-Konformitätserklärung sowie Registrierung in der EU-Datenbank (Art. 49, 71) als To-dos einplanen.",
      "Bei begrenztem Risiko die Transparenzpflichten nach Art. 50 umsetzen (Hinweis auf KI-Nutzung, Kennzeichnung).",
      "Rollen klar zuordnen: Anbieter vs. Betreiber/Deployer, da sich die Pflichten unterscheiden.",
      "Bei Einsatz von GPAI/Foundation-Modellen die GPAI-Pflichten (Art. 53 ff.) separat erfassen.",
      "Klassifizierung, Begründung und Evidenzen versioniert ablegen, um Audit-Fähigkeit sicherzustellen."
    ]
  },
  "moduleSpecific": {
    "title": "Besonderheiten des AI-Act-Moduls",
    "intro": "Das Modul bildet die Eigenheiten der risikobasierten Logik und der gestaffelten Anwendbarkeit ab.",
    "bullets": [
      "Risikoklassifizierung als zentraler Einstieg: verbotene Praktiken, Hochrisiko, begrenztes Risiko, minimales Risiko.",
      "Pflichten werden klassenspezifisch ausgespielt; nur einschlägige Anforderungen werden zur Bearbeitung angeboten.",
      "Hochrisiko-Checkliste orientiert sich an Art. 9-15 und Annex IV (technische Dokumentation).",
      "Zeitplan/Fristen: Verbote gelten seit 2. Februar 2025, GPAI-Regeln seit 2. August 2025, Hochrisiko nach Annex III ab 2. August 2026, eingebettete Hochrisiko-Produkte (Annex I) ab 2. August 2027.",
      "Unterscheidung zwischen Anbieter- und Betreiberpflichten ist im Modul hinterlegt.",
      "GPAI-Modelle werden gesondert behandelt, inkl. Kriterium des systemischen Risikos."
    ]
  },
  "links": [
    {
      "label": "AI Act Modul-Dokumentation",
      "href": docsUrl('/modules/ai-act/')
    },
    {
      "label": "Verordnung (EU) 2024/1689 (EUR-Lex)",
      "href": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj"
    }
  ],
  "module": "aiact"
}
