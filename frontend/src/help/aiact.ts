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
  "areas": [
    {
      "id": "pflichtdoku",
      "title": "📋 Dokumentation",
      "zweck": "Zentrale Pflicht-Dokumentation des KI-Systems: Risikoklasse, Rolle (Anbieter/Betreiber), Stammdaten und Nachweis-Status der Hochrisiko-Pflichten als Einstieg in alle Fach-Tabs.",
      "rechtsgrundlage": "Art. 6/Annex III (Einstufung), Art. 11/Annex IV (technische Doku), Art. 16/26 (Pflichten Anbieter/Betreiber)",
      "pflichtfelder": [
        "Risikoklasse (verboten / hochrisiko / begrenzt / minimal) – steuert die ausgespielten Pflichten.",
        "Rolle: Anbieter (provider) oder Betreiber/Deployer – Pflichten unterscheiden sich.",
        "Use-Case-Beschreibung (Grundlage für Art.-5- und Annex-III-Prüfung).",
        "Firmen-/Projektzuordnung (für Cockpit und Berichte)."
      ],
      "anleitung": "1) Use Case beschreiben. 2) Art.-5-Verbote prüfen (Tab Art. 5). 3) Risikoklasse setzen (Annex III/Art. 6). 4) Rolle festlegen. 5) Bei Hochrisiko die Anforderungen (Art. 9–15) abarbeiten.",
      "tipps": ["Erst die Klassifizierung – sie entscheidet, welche Pflicht-Tabs überhaupt einschlägig sind."]
    },
    {
      "id": "cockpit",
      "title": "📊 Risiko-Cockpit",
      "zweck": "Firmenweite, modulübergreifende Read-only-Sicht auf offene Risiken (Risikobewertung) und Schwachstellen der zugeordneten Firma.",
      "rechtsgrundlage": "Art. 9 AI Act (Risikomanagement über den Lebenszyklus)",
      "pflichtfelder": [
        "Keine Eingabe – Aggregation pro Firma (firmen_id) aus den verknüpften Modulen."
      ],
      "anleitung": "1) Firmen-Zuordnung des Projekts sicherstellen. 2) Offene High/Critical zuerst sichten. 3) Behandlung in der verknüpften Risikobewertung.",
      "tipps": ["Risiken werden in der Risikobewertung gepflegt; das Cockpit spiegelt nur deren Stand."]
    },
    {
      "id": "anforderungen",
      "title": "✅ Anforderungen",
      "zweck": "Pflichten-Checkliste für Hochrisiko-KI (Art. 9–15) mit Reifegrad und Nachweisbezug – nur einschlägig bei Hochrisiko-Einstufung.",
      "rechtsgrundlage": "Art. 9–15 AI Act (Risikomanagement, Daten-Governance, techn. Doku, Logging, Transparenz, menschl. Aufsicht, Genauigkeit/Robustheit/Cybersicherheit), Annex IV",
      "pflichtfelder": [
        "Je Anforderung (Art. 9–15): Reifegrad/Status und Nachweis/Begründung.",
        "Daten-Governance (Art. 10): Herkunft/Qualität der Trainings-/Validierungs-/Testdaten.",
        "Logging (Art. 12) und menschliche Aufsicht (Art. 14) belegt.",
        "Technische Dokumentation nach Annex IV verknüpft."
      ],
      "anleitung": "1) Jede Art.-9–15-Anforderung durchgehen. 2) Reifegrad realistisch setzen. 3) Nachweis (Dokument/Beleg) verknüpfen. 4) Lücken in Maßnahmen/Issues überführen.",
      "tipps": ["Nur bei Hochrisiko verpflichtend; bei begrenztem Risiko genügen die Transparenzpflichten (Art. 50)."]
    },
    {
      "id": "art5",
      "title": "🚫 Art. 5 Verbote",
      "zweck": "Dokumentierte Negativprüfung gegen die 8 verbotenen Praktiken des Art. 5(1) – Gate vor jeder weiteren Bewertung.",
      "rechtsgrundlage": "Art. 5(1) a–h AI Act (verbotene Praktiken, anwendbar seit 2. Februar 2025)",
      "pflichtfelder": [
        "Je Tatbestand a–h: betroffen = ja / nein / offen.",
        "Begründung der Bewertung (insb. bei 'nein' – Negativnachweis).",
        "Geprüft von und geprüft am."
      ],
      "anleitung": "1) Alle 8 Tatbestände (a Manipulation … h Echtzeit-Fernidentifizierung) durchgehen. 2) Je Tatbestand betroffen/nicht betroffen entscheiden und begründen. 3) Prüfer und Datum erfassen. KI-Wizard kann eine Vorbewertung aus der Use-Case-Beschreibung liefern.",
      "tipps": [
        "Ein einziges 'ja' bedeutet i. d. R. Unzulässigkeit – Use Case anpassen.",
        "Auch 'nein' braucht eine nachvollziehbare Begründung (Negativnachweis)."
      ]
    },
    {
      "id": "literacy",
      "title": "🎓 AI-Literacy",
      "zweck": "Nachweis ausreichender KI-Kompetenz der mit dem System befassten Personen (Schulungsnachweise) und der Personen für die menschliche Aufsicht.",
      "rechtsgrundlage": "Art. 4 AI Act (KI-Kompetenz, anwendbar seit 2. Februar 2025); Bezug Art. 14 (menschliche Aufsicht)",
      "pflichtfelder": [
        "Person und Rolle.",
        "Schulungsmodul und Kompetenzlevel (grundlagen/…).",
        "Durchgeführt am und gültig bis (Ablauf-Status).",
        "Nachweis-Referenz (Zertifikat/Beleg).",
        "Oversight-Person (für Art.-14-Aufsicht), Kommentar."
      ],
      "anleitung": "1) Je beteiligter Person einen Nachweis anlegen. 2) Schulungsmodul, Level und Durchführungsdatum erfassen. 3) Gültigkeit setzen (Ablauf wird angezeigt). 4) Aufsichts-Personen markieren. 5) Optional Literacy-Konzept hinterlegen.",
      "tipps": ["Abgelaufene Nachweise werden markiert – rechtzeitig erneuern."]
    },
    {
      "id": "incidents",
      "title": "🚨 Art. 73 Vorfälle",
      "zweck": "Serious-Incident-Register mit Fristenuhr: Meldung schwerwiegender Vorfälle an die Marktüberwachungsbehörde mit gestaffelten Fristen.",
      "rechtsgrundlage": "Art. 73 AI Act (Meldung: 2 Tage bei weit verbreitetem Verstoß/KRITIS, 10 Tage bei Tod, 15 Tage Regelfrist)",
      "pflichtfelder": [
        "Titel und Beschreibung des Vorfalls.",
        "Eintritts-Datum und Kenntnis-Datum (Kenntnis startet die Fristenuhr).",
        "Schweregrad: weit_verbreitet (2 T.) / tod (10 T.) / schwere_schaedigung (15 T.) / standard (15 T.).",
        "Behörde (Marktüberwachung), Erstbericht-am / Vollbericht-am / Abgeschlossen-am.",
        "Einreichungsnachweis und CAPA-Referenz (Korrekturmaßnahme)."
      ],
      "anleitung": "1) Vorfall sofort bei Kenntnis anlegen, Kenntnis-Datum korrekt setzen. 2) Schweregrad wählen – bestimmt die Frist (2/10/15 Tage). 3) Erstbericht fristgerecht absetzen und Datum erfassen. 4) Vollbericht und Abschluss dokumentieren, Einreichungsnachweis hinterlegen.",
      "tipps": [
        "Die Ampel zeigt die Restzeit ab Kenntnis-Datum – Schweregrad bestimmt die Frist.",
        "CAPA-Referenz stellt den Bezug zur Korrekturmaßnahme her."
      ]
    },
    {
      "id": "fria",
      "title": "⚖️ Art. 27 FRIA",
      "zweck": "Grundrechte-Folgenabschätzung (Fundamental Rights Impact Assessment) für bestimmte Betreiber – geführter Stepper inkl. Mitteilung an die Behörde.",
      "rechtsgrundlage": "Art. 27 AI Act (FRIA; Pflicht u. a. für öffentliche Stellen und Annex III Nr. 5 b/c – Bonität, Versicherungs-Risikobewertung)",
      "pflichtfelder": [
        "Betreiber-Typ (löst die FRIA-Pflicht aus, z. B. öffentliche Stelle, Annex III 5b/5c).",
        "Nutzungsprozesse (Art. 27(1)a) und Zeitraum/Häufigkeit (b).",
        "Betroffene Personengruppen (c) und spezifische Schadensrisiken (d).",
        "Maßnahmen zur menschlichen Aufsicht (e) und Risikominderung (f).",
        "Mitteilung an die Marktüberwachungsbehörde (Art. 27(3)): gemeldet-am, Behörde."
      ],
      "anleitung": "1) Betreiber-Typ prüfen – nur bei FRIA-Pflicht erforderlich. 2) Stepper durchgehen: Prozesse, Zeitraum, Betroffene, Risiken, Aufsicht, Maßnahmen. 3) FRIA finalisieren. 4) Mitteilung erzeugen und an die Behörde übermitteln, Datum erfassen.",
      "tipps": [
        "Die FRIA ist VOR der ersten Inbetriebnahme durchzuführen.",
        "Bei nicht-FRIA-pflichtigen Betreibern kann der Tab leer bleiben (begründen)."
      ]
    },
    {
      "id": "conformity",
      "title": "🏷️ Art. 43/48 Konformität",
      "zweck": "Konformitätsbewertung für Hochrisiko-KI: Wahl des Verfahrenswegs (interne Kontrolle vs. notifizierte Stelle), Selbstprüfungs-Checkliste, EU-Konformitätserklärung und CE-Kennzeichnung.",
      "rechtsgrundlage": "Art. 43 (Konformitätsbewertung, Annex VI/VII), Art. 47/48 (EU-Konformitätserklärung, CE), Art. 11/Annex IV",
      "pflichtfelder": [
        "Verfahren: interne Kontrolle (Annex VI, Annex III Nr. 2–8) oder notifizierte Stelle (Annex VII, Biometrie / Annex III Nr. 1).",
        "Annex-VI-Selbstprüfungs-Checkliste (QMS, technische Doku Annex IV, Post-Market-Monitoring Art. 72).",
        "Bei notifizierter Stelle: Name + Kennnummer + Zertifikats-Upload (Annex VII).",
        "EU-Konformitätserklärung und CE-Status."
      ],
      "anleitung": "1) Verfahrensweg nach Risikotyp wählen (Biometrie/Annex III Nr. 1 → notifizierte Stelle). 2) Checkliste abarbeiten (QMS, Annex-IV-Doku, Post-Market-Plan). 3) Bei NB-Verfahren Kennnummer und Zertifikat erfassen. 4) Konformitätserklärung ausstellen, CE setzen.",
      "tipps": ["Biometrie (Annex III Nr. 1) erfordert i. d. R. eine notifizierte Stelle – interne Kontrolle genügt nicht."]
    },
    {
      "id": "gpai",
      "title": "🧠 Art. 51-55 GPAI",
      "zweck": "Pflichten für General-Purpose-AI-Modelle inkl. Schwellenwert-Auswertung für systemisches Risiko und der zugehörigen Dokumentations- und Notifikationspflichten.",
      "rechtsgrundlage": "Art. 51–55 AI Act (GPAI; systemisches Risiko ab 10^25 FLOP nach Art. 51(2); Annex XI Modell-Doku, Annex XII Downstream-Doku)",
      "pflichtfelder": [
        "Kumulierte Trainings-FLOP (≥ 10^25 ⇒ systemisches Risiko) bzw. manueller Override.",
        "Technische Modell-Dokumentation (Annex XI) und Downstream-Doku (Annex XII).",
        "Urheberrechts-Policy und Trainingsdaten-Zusammenfassung (Art. 53).",
        "Bei systemischem Risiko: Kommissions-Notifikation (Art. 52, 2-Wochen-Frist), Evaluierung/Adversarial Testing, Cybersicherheit (Art. 55).",
        "GPAI-Anforderungen (AIA-GPAI-01 ff.) mit Status."
      ],
      "anleitung": "1) Trainings-FLOP erfassen – das Modul ermittelt systemisches Risiko (Schwelle 10^25). 2) Annex-XI/XII-Doku und Copyright-Policy belegen. 3) Bei systemischem Risiko Kommission binnen 2 Wochen notifizieren (Fristenuhr) und Art.-55-Pflichten erfüllen.",
      "tipps": [
        "Die FLOP-Schwelle 10^25 entscheidet über die verschärften Art.-55-Pflichten.",
        "GPAI-Regeln gelten seit 2. August 2025.",
        "Im Tab Assistenten liefern der GPAI-Klassifikator (Prompt + Übernahme ins Register) sowie die Generatoren für Urheberrechts-/TDM-Policy (Art. 53(1)c) und Trainingsdaten-Zusammenfassung (Art. 53(1)d) Copy/Paste-Entwürfe; die Policy-/Summary-Ergebnisse sind als Dokument speicher- und exportierbar."
      ]
    },
    {
      "id": "owasp-llm",
      "title": "🛡️ OWASP-LLM",
      "zweck": "Sicherheits-Register für LLM-spezifische Risiken (OWASP Top 10 for LLM Applications) mit Status, Issue-Link und Auto-Detect – additive Stärkung von Art. 9 und Art. 15.",
      "rechtsgrundlage": "Art. 9 (Risikomanagement) + Art. 15 (Genauigkeit/Robustheit/Cybersicherheit) AI Act, operationalisiert über OWASP LLM Top 10",
      "pflichtfelder": [
        "Je LLM-Risiko (z. B. Prompt Injection, Data/Model Poisoning, Insecure Output Handling): Status 0–5.",
        "Nachweis/Maßnahme und ggf. Issue-Verknüpfung."
      ],
      "anleitung": "1) Auto-Detect laufen lassen (LLM-Heuristiken). 2) Je OWASP-LLM-Risiko Status setzen und Maßnahme/Nachweis verknüpfen. 3) Offene Risiken als Issue tracken. 4) Ergebnis fließt in Art. 9/15.",
      "tipps": ["Nur relevant, wenn das System ein LLM/GenAI nutzt; ergänzt – ersetzt nicht – die Art.-9–15-Anforderungen."]
    },
    {
      "id": "assistenten",
      "title": "🤖 Assistenten",
      "zweck": "KI-gestützte Wizards (Copy/Paste-Prompts), die Entwürfe für Klassifizierung, Art.-5-Screening, Anforderungs-/GPAI-Bewertung, AI-Literacy (Art. 4) und Pflichtdokumente (Annex-IV-Doku, Betriebsanleitung Art. 13, FRIA Art. 27, GPAI-Policies) liefern.",
      "rechtsgrundlage": "— (Hilfsmittel; die Konformitätsbewertung bleibt beim Anbieter/Betreiber)",
      "pflichtfelder": [
        "Keine Pflichtfelder – Eingaben sind je Assistent kontextabhängig."
      ],
      "anleitung": "1) Assistenten wählen. 2) Prompt mit Projektkontext erzeugen, in das KI-Tool kopieren. 3) Antwort zurückspielen/prüfen. 4) Register-Assistenten (GPAI-Klassifikator, AI-Literacy) übernehmen direkt; Dokument-Assistenten (Betriebsanleitung, FRIA, Annex-IV, GPAI-Policies) über die Aktion zum Speichern als Dokument editier-/exportierbar ablegen.",
      "tipps": ["KI-Vorschläge fachlich gegenprüfen – sie ersetzen keine regulatorische Bewertung."]
    },
    {
      "id": "dokumente",
      "title": "📄 Dokumente",
      "zweck": "Ablage und Verwaltung hochgeladener Nachweise (technische Doku, Schulungszertifikate, NB-Zertifikate, Testberichte) für die einzelnen Pflicht-Tabs.",
      "rechtsgrundlage": "Art. 11/Annex IV AI Act (technische Dokumentation/Nachweisführung)",
      "pflichtfelder": [
        "Datei + aussagekräftiger Name; Dokumenttyp.",
        "Zuordnung zum belegten Bereich/zur Anforderung."
      ],
      "anleitung": "1) Nachweis hochladen und eindeutig benennen. 2) Dem passenden Bereich/Anforderung zuordnen. 3) Bei Aktualisierung neue Version ablegen statt überschreiben.",
      "tipps": ["Konsequentes Tagging erleichtert die Vollständigkeitsprüfung der Annex-IV-Akte."]
    },
    {
      "id": "bericht",
      "title": "📄 Bericht",
      "zweck": "Export des AI-Act-Berichts (Klassifizierung, Pflichten-Status, offene Lücken, Nachweise) als Grundlage der technischen Dokumentation nach Annex IV.",
      "rechtsgrundlage": "Art. 11 AI Act i. V. m. Annex IV (technische Dokumentation)",
      "pflichtfelder": [
        "Auswahl der Berichtsabschnitte und Format (DOCX/PDF)."
      ],
      "anleitung": "1) Vorab alle Fach-Tabs (Art. 5, Anforderungen, Konformität, GPAI) finalisieren. 2) Abschnitte wählen. 3) Bericht erzeugen und als Teil der Annex-IV-Akte ablegen.",
      "tipps": ["Die Berichtsqualität hängt direkt vom gepflegten Reifegrad und den verknüpften Nachweisen ab."]
    }
  ],
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
