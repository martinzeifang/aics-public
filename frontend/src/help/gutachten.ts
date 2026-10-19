// Auto-generiert (#926) — Modul-Hilfe-Inhalt.
import type { ModuleHelp } from './types'
import { docsUrl } from './docsUrl'

export const gutachtenHelp: ModuleHelp = {
  "title": "Gutachten",
  "regulation": "§§ 402–414 ZPO (Sachverständigenbeweis), insb. § 407a ZPO und § 404a ZPO; methodischer Rahmen: BISG-Standard für IT-forensische Sachverständigengutachten",
  "purpose": "Das Modul unterstützt die Erstellung von Sachverständigen- und IT-Forensik-Gerichtsgutachten nach BISG-Standard. Es strukturiert den Gutachtenaufbau, hält die prozessualen Pflichten des Sachverständigen nach ZPO ein und stellt methodische Bausteine für die forensische Beweisführung bereit.",
  "legalBasis": {
    "title": "Rechtliche Grundlagen des Sachverständigenbeweises",
    "intro": "Der gerichtliche Sachverständige unterliegt den prozessualen Pflichten der ZPO. Zentral sind die persönliche Erstattungspflicht und die eigene Sachkundeprüfung (§ 407a ZPO) sowie die Bindung an die Leitung und den Beweisbeschluss des Gerichts (§ 404a ZPO). Der Sachverständige liefert keine rechtliche Würdigung, sondern beantwortet ausschließlich die ihm gestellten Beweisfragen auf Basis seiner Fachkunde.",
    "bullets": [
      "§ 407a Abs. 1 ZPO: Prüfung, ob der Auftrag in das eigene Fachgebiet fällt und ohne Zuziehung weiterer Sachverständiger erledigt werden kann; andernfalls unverzügliche Mitteilung an das Gericht.",
      "§ 407a Abs. 1 ZPO: Das Gutachten ist persönlich zu erstatten; Hilfskräfte dürfen nur unterstützend tätig werden und sind offenzulegen.",
      "§ 407a Abs. 3 ZPO: Anzeigepflicht bei Zweifeln über Inhalt/Umfang des Auftrags sowie bei voraussichtlicher Überschreitung des angenommenen Kostenrahmens.",
      "§ 407a Abs. 4 ZPO: Herausgabe der überlassenen Akten/Untersuchungsgegenstände nach Abschluss; sorgfältiger Umgang mit Beweismitteln (Integrität der Beweiskette).",
      "§ 404a ZPO: Leitung der Tätigkeit durch das Gericht; Bindung an Weisungen und den Beweisbeschluss, Abgrenzung von Tat- und Rechtsfragen.",
      "§ 410 ZPO: Beeidigung/Versicherung der unparteiischen und gewissenhaften Erstattung des Gutachtens.",
      "§ 411 ZPO: Form (schriftliches Gutachten), Fristsetzung sowie Pflicht zur mündlichen Erläuterung und Beantwortung von Ergänzungsfragen."
    ]
  },
  "implementation": {
    "title": "Vorgehen im Modul",
    "intro": "Das Modul führt strukturiert vom Beweisbeschluss zur fertigen Gutachtenfassung: Beweisfragen werden erfasst, forensische Befunde gesichert und dokumentiert, Hypothesen gebildet und gegen die Befundlage geprüft. Jeder Schritt wird nachvollziehbar und reproduzierbar protokolliert.",
    "bullets": [
      "Beweisfragen wörtlich aus dem Beweisbeschluss übernehmen und einzeln gegliedert beantworten; keine über den Auftrag hinausgehenden Aussagen.",
      "Eingangsprüfung nach § 407a ZPO dokumentieren: eigene Sachkunde, Vollständigkeit der Anknüpfungstatsachen, ggf. Anzeige an das Gericht.",
      "Forensische Sicherung lückenlos festhalten: Hashwerte (z. B. SHA-256), Datenträger-Images, MACB-Zeitstempel (Modified, Accessed, Changed, Birth) und Chain of Custody.",
      "Eingesetzte Werkzeuge validieren und versionieren (Tool-Name, Version, Konfiguration), um Reproduzierbarkeit der Ergebnisse sicherzustellen.",
      "Befunde von Bewertung trennen: zuerst objektive Befunddarstellung, dann Hypothesenbildung und begründete Schlussfolgerung mit Sicherheitsgrad.",
      "Quellen und Anknüpfungstatsachen cross-referenzieren; jede Aussage auf einen dokumentierten Befund zurückführen.",
      "Vor Abgabe: Peer-Review einplanen und kritische Befunde auf Drittgutachter-Reproduzierbarkeit prüfen.",
      "Gutachten mit Zusammenfassung, Methodik, Befunden, Beantwortung der Beweisfragen und Anlagenverzeichnis abschließen; Versicherung nach § 410 ZPO ergänzen."
    ]
  },
  "moduleSpecific": {
    "title": "Besonderheiten des Gutachten-Moduls",
    "intro": "Das Modul ist auf IT-forensische Sachverständigengutachten nach BISG-Standard zugeschnitten und bildet die spezifischen Anforderungen an Aufbau, prozessuale Pflichten und forensische Methodik ab.",
    "bullets": [
      "Vorlage für den BISG-konformen Gutachtenaufbau (Auftrag/Beweisfragen, Sachverhalt, Methodik, Befunde, Würdigung, Beantwortung, Anlagen).",
      "Checkliste der § 407a-ZPO-Pflichten als Eingangsprüfung vor Beginn der eigentlichen Untersuchung.",
      "Methodik-Bausteine: forensische Sicherung (MACB-Zeiten, Hashing, Imaging), Werkzeug-Validierung, Hypothesenbildung und Cross-Referenzierung.",
      "Qualitätssicherung über Peer-Review und Hinweise zur Drittgutachter-Reproduktion.",
      "Strikte Trennung von Tatfrage (Sachverständiger) und Rechtsfrage (Gericht) gemäß § 404a ZPO ist im Aufbau verankert.",
      "Nachvollziehbare Dokumentation der Beweiskette als durchgängiges Prinzip aller Bausteine."
    ]
  },
  "areas": [
    {
      "id": "stammdaten",
      "title": "Deckblatt (Stammdaten)",
      "zweck": "Stammdaten des Gutachtens und Deckblatt-Angaben – unterscheidet Gerichts- und Privatgutachten und steuert Status/Vertraulichkeit.",
      "rechtsgrundlage": "§ 404a ZPO (Bindung an Beweisbeschluss/Gericht); § 411 ZPO (Form/Frist)",
      "pflichtfelder": [
        "Gutachten-Art (Gericht/Privat) – steuert das Deckblatt.",
        "Gericht: Gericht, Kammer, Aktenzeichen, Beweisbeschluss-Datum, Kläger, Beklagter.",
        "Privat: Auftraggeber, Auftrags-Art, -Datum, -Nummer, Honorarvereinbarung.",
        "Thema (Gegenstand des Gutachtens), Sachverständigen-Name (SV-Name).",
        "Vertraulichkeit (nach Statuswechsel finalisiert/eingereicht gesperrt).",
        "Status (in_bearbeitung → finalisiert → eingereicht)."
      ],
      "anleitung": "1) Art wählen (Gericht/Privat). 2) Verfahrens-/Auftragsdaten exakt aus Beweisbeschluss bzw. Auftrag übernehmen. 3) Thema und SV-Name setzen. 4) Vertraulichkeit festlegen, solange noch in Bearbeitung. 5) Status erst final setzen, wenn der Validator release-ready meldet.",
      "tipps": [
        "Vertraulichkeit ist nach Statuswechsel gesperrt – vorher final festlegen.",
        "Wird aus einem Compliance-Audit abgeleitet: übernommene Befund-Skeletons sind leer und müssen nach § 407a ZPO persönlich neu formuliert werden."
      ]
    },
    {
      "id": "selbstcheck",
      "title": "Selbstcheck (§ 406)",
      "zweck": "Befangenheits-Selbstprüfung des Sachverständigen vor Auftragsannahme; erzeugt den editierbaren Befangenheits-Fließtext für Kap. III des Gutachtens.",
      "rechtsgrundlage": "§ 406 ZPO (Ablehnung), § 407a Abs. 2 ZPO (Mitteilungspflichten); § 404a ZPO",
      "pflichtfelder": [
        "Antwort (ja/nein/unklar) auf jede Selbstcheck-Frage (z. B. Vorbefassung, persönliche/wirtschaftliche Nähe zu Parteien).",
        "Befangenheits-Fließtext: generierten Text prüfen/anpassen und speichern (geht in DOCX Kap. III)."
      ],
      "anleitung": "1) Alle Fragen wahrheitsgemäß beantworten. 2) Auswerten – das Ergebnis gibt eine Empfehlung (unbedenklich/Anzeige ans Gericht/Ablehnung). 3) Befangenheits-Fließtext gegenlesen, ggf. anpassen und speichern.",
      "tipps": [
        "Bei ‚unklar' oder Nähebeziehungen das Gericht aktiv informieren (§ 407a Abs. 2) statt zu schweigen.",
        "Der gespeicherte Fließtext erscheint im Export – ohne ihn fehlt der Befangenheits-Abschnitt."
      ]
    },
    {
      "id": "beweisfragen",
      "title": "II. Beweisfragen",
      "zweck": "Wörtliche Erfassung der Beweisfragen aus dem Beweisbeschluss und ihre fachliche Beantwortung – der inhaltliche Kern des Auftrags.",
      "rechtsgrundlage": "§ 404a ZPO (Bindung an den Beweisbeschluss); § 407a Abs. 3 ZPO (Auftragsumfang)",
      "pflichtfelder": [
        "Nr (Reihenfolge), Frage (wörtlich aus dem Beweisbeschluss).",
        "Antwort kurz (ja/nein/teilweise/non-liquet).",
        "Antwort ausführlich (2–3 Sätze, mit Verweis auf die Beurteilungen in Kap. V)."
      ],
      "anleitung": "1) Jede Beweisfrage wörtlich übernehmen. 2) Kurzantwort wählen. 3) Ausführliche Antwort formulieren und auf die tragende Beurteilung (Kap. V) verweisen. 4) Keine Aussagen über den Auftrag hinaus treffen.",
      "tipps": [
        "‚non-liquet' ist eine zulässige, ehrliche Antwort, wenn die Befundlage keine Aussage trägt.",
        "Die Antwort ist Schlussfolgerung – die Begründung gehört in Befunde (IV) und Beurteilungen (V)."
      ]
    },
    {
      "id": "befunde",
      "title": "IV. Befunde",
      "zweck": "Reine Tatsachenfeststellung: was mit welcher Methode und welchem Werkzeug objektiv festgestellt wurde – ohne Wertung.",
      "rechtsgrundlage": "§ 404a ZPO (Tat- vs. Rechtsfrage); Reproduzierbarkeit nach ISO/IEC 27037",
      "pflichtfelder": [
        "Nr (z. B. 4.1) und Titel.",
        "Methode (statisch/dynamisch/db/netzwerk/interview/live-forensik).",
        "Werkzeug (Name + Version) zur Reproduzierbarkeit.",
        "Beschreibung – ausschließlich Tatsachen (Sprach-Linter prüft auf Wertungen)."
      ],
      "anleitung": "1) Befund nummerieren und betiteln. 2) Methode und eingesetztes Werkzeug inkl. Version angeben. 3) Nur beobachtbare Tatsachen beschreiben. 4) Linter-Hinweise (wertende Formulierungen) beheben.",
      "tipps": [
        "Strikte Trennung: Befunde = Tatsachen, Bewertung erst in Kap. V (§ 404a ZPO).",
        "Werkzeug-Version ist Pflicht für die Reproduzierbarkeit und die Werkzeug-Validierung (Forensik-Tab)."
      ]
    },
    {
      "id": "beurteilungen",
      "title": "V. Beurteilungen",
      "zweck": "Technische Würdigung der Befunde gegen eine Norm im Soll/Ist-Vergleich mit Kausalität – die fachliche Schlussfolgerung (ohne Rechtswürdigung).",
      "rechtsgrundlage": "§ 404a ZPO (Tatfrage des Sachverständigen, keine Rechtswürdigung)",
      "pflichtfelder": [
        "Nr (z. B. 5.1), Titel, Norm (Auswahl) + Norm-Referenz.",
        "Verknüpfte Befund-IDs (worauf sich die Beurteilung stützt).",
        "Soll (was die Norm verlangt), Ist (Befund-Vergleich), Kausalität.",
        "Würdigung – fachlich, mit ‚Jura-Sperre' (keine rechtliche Bewertung)."
      ],
      "anleitung": "1) Norm und Referenz wählen. 2) Tragende Befunde verknüpfen. 3) Soll aus der Norm, Ist aus den Befunden, dann Kausalität herleiten. 4) Fachlich würdigen, ohne Rechtsfragen zu beantworten. 5) Optional KI-Vorschlag generieren und fachlich prüfen.",
      "tipps": [
        "Jede Beurteilung muss auf verknüpfte Befunde gestützt sein – sonst greift der Cross-Reference-Linter.",
        "Rechtliche Schlüsse (z. B. ‚Mangel im Rechtssinne') vermeiden – das entscheidet das Gericht."
      ]
    },
    {
      "id": "assets",
      "title": "Asservaten (Chain of Custody)",
      "zweck": "Lückenlose Beweismittel-Dokumentation mit Hashwerten und Akquisitionsdaten – die Beweiskette nach ISO/IEC 27037.",
      "rechtsgrundlage": "§ 407a Abs. 4 ZPO (Umgang mit Untersuchungsgegenständen); ISO/IEC 27037 (Chain of Custody)",
      "pflichtfelder": [
        "Bezeichnung des Asservats.",
        "SHA-256 (wird beim Datei-Upload automatisch berechnet) – Pflicht.",
        "Akquisitions-Zeitpunkt (UTC) und -Ort.",
        "Werkzeug (Name + Version), gegengezeichnet von."
      ],
      "anleitung": "1) Asservat benennen und Datei hochladen (SHA-256 entsteht automatisch). 2) Akquisitionszeit (UTC) und -ort erfassen. 3) Sicherungswerkzeug + Version und Gegenzeichnung dokumentieren. 4) Sicherungsprotokoll-PDF je Asservat erzeugen.",
      "tipps": [
        "Ohne Hashwert keine belastbare Integrität – SHA-256 ist Pflicht.",
        "Zeit immer in UTC erfassen, um Zeitzonen-Mehrdeutigkeit zu vermeiden."
      ]
    },
    {
      "id": "verfahren",
      "title": "III. Verfahren",
      "zweck": "Chronologischer Verfahrensgang inkl. Parteikommunikation mit Symmetrie-Check (Gleichbehandlung der Parteien).",
      "rechtsgrundlage": "§ 404a ZPO (Leitung durch das Gericht); rechtliches Gehör / Gleichbehandlung der Parteien",
      "pflichtfelder": [
        "Datum, Ereignis-Typ, Titel und Beschreibung je Verfahrensschritt.",
        "Empfänger der Kommunikation (Kläger/Beklagter/Gericht) – Grundlage des Symmetrie-Checks."
      ],
      "anleitung": "1) Jeden relevanten Schritt chronologisch erfassen (Reihenfolge per ▲/▼ korrigierbar). 2) Bei Parteikommunikation die Empfänger markieren. 3) Symmetrie prüfen – einseitige Kommunikation an nur eine Partei beheben.",
      "tipps": [
        "Symmetrieverletzungen (Information nur einer Partei) gefährden das rechtliche Gehör – stets beide Parteien einbeziehen.",
        "Ortstermine und Schriftverkehr lückenlos protokollieren."
      ]
    },
    {
      "id": "forensik",
      "title": "Forensik (MACB/Tools)",
      "zweck": "IT-forensische Werkzeuge und Methodik: Werkzeug-Validator, MACB-Zeitstempel (Timestomping-Erkennung), Order of Volatility und Log-Klassifikation.",
      "rechtsgrundlage": "ISO/IEC 27037 (Identifizierung, Sammlung, Sicherung digitaler Beweise); Order of Volatility (RFC 3227)",
      "pflichtfelder": [
        "Werkzeug-Validator: alle in Befunden genutzten Werkzeuge sollten im SV-Register stehen.",
        "MACB-Einträge: Datei-Pfad + Modified/Accessed/Changed/Born-Zeitstempel.",
        "Bei Methode ‚live-forensik': Order of Volatility (Reihenfolge der Sicherung) beachten."
      ],
      "anleitung": "1) Werkzeug-Validator ausführen – unbekannte Werkzeuge ins Register aufnehmen. 2) MACB-Zeitstempel je relevanter Datei erfassen; Timestomping-Warnungen bewerten. 3) Bei Live-Forensik die Volatility-Reihenfolge einhalten. 4) Logs per Klassifikator einordnen.",
      "tipps": [
        "Timestomping-Verdacht (inkonsistente MACB-Zeiten) im Gutachten ausdrücklich würdigen.",
        "Nur validierte, versionierte Werkzeuge sichern die Reproduzierbarkeit."
      ]
    },
    {
      "id": "hypothesen",
      "title": "Hypothesen-Tree",
      "zweck": "Systematisches Sammeln alternativer Erklärungen und ihr begründetes Verwerfen/Akzeptieren – plus Drittgutachter-Simulation und Cross-Reference-Linter.",
      "rechtsgrundlage": "Wissenschaftliche Nachvollziehbarkeit; DIN EN 16775 (Sachverständigen-Dienstleistungen)",
      "pflichtfelder": [
        "Je Hypothese: zugehörige Beurteilung, Hypothesen-Text, Status (offen/verworfen/akzeptiert), Begründung.",
        "Begründung ist Pflicht beim Verwerfen/Akzeptieren."
      ],
      "anleitung": "1) Zu jeder tragenden Beurteilung alternative Erklärungen sammeln. 2) Jede Hypothese begründet verwerfen oder akzeptieren. 3) Drittgutachter-Prompt für kritische Befunde erzeugen (Reproduktionsanleitung). 4) Cross-Reference-Linter zur Strukturprüfung laufen lassen.",
      "tipps": [
        "Eine Hypothese ohne Begründung schwächt die Beweiskraft – immer begründen.",
        "Den Cross-Reference-Linter vor dem Validator nutzen, um Verknüpfungslücken früh zu finden."
      ]
    },
    {
      "id": "peer",
      "title": "Peer-Review",
      "zweck": "Vier-Augen-Qualitätssicherung vor Abgabe, 10-Jahre-Aufbewahrung und anonymisierte Vorschau.",
      "rechtsgrundlage": "Qualitätssicherung; berufliche Sorgfalt; Aufbewahrungspflichten",
      "pflichtfelder": [
        "Reviewer-Name (Review anfordern).",
        "Kommentare je Kapitel (Kapitel, Text, Author) während des Reviews.",
        "Review abschließen, bevor das Gutachten finalisiert wird."
      ],
      "anleitung": "1) Review anfordern. 2) Reviewer kommentiert kapitelbezogen. 3) Kommentare einarbeiten, Review abschließen. 4) 10-Jahre-Aufbewahrung aktivieren. 5) Bei Bedarf anonymisierte Vorschau prüfen.",
      "tipps": [
        "Peer-Review vor dem Statuswechsel auf ‚finalisiert' abschließen.",
        "Anonymisierte Vorschau eignet sich für Schulung/Muster ohne Personenbezug."
      ]
    },
    {
      "id": "honorar",
      "title": "Honorar",
      "zweck": "Zeitbuch und Honorar-/Auslagen-Tracking als Grundlage der Rechnungsstellung (JVEG bei Gerichtsgutachten).",
      "rechtsgrundlage": "JVEG (Vergütung gerichtlicher Sachverständiger); § 407a Abs. 3 ZPO (Kostenanzeige)",
      "pflichtfelder": [
        "Je Eintrag: Kategorie (Aktenstudium/Asservaten/Labor/Bericht/Kommunikation/Ortstermin/…), Dauer (Min), Stundensatz (€), Beschreibung."
      ],
      "anleitung": "1) Tätigkeiten zeitnah als Zeitbuch-Einträge erfassen. 2) Stundensatz je Eintrag setzen. 3) Summen prüfen (Honorar/Auslagen/offen). 4) Rechnungs-PDF erzeugen.",
      "tipps": [
        "Bei absehbarer Überschreitung des Kostenrahmens das Gericht rechtzeitig informieren (§ 407a Abs. 3 ZPO).",
        "Zeiten zeitnah buchen – nachträgliche Schätzungen sind angreifbar."
      ]
    },
    {
      "id": "validator",
      "title": "Validator + Export",
      "zweck": "Pre-Export-Prüfung (Release-Readiness) und Sprach-Linter sowie DOCX-Vorschau/Export der Endfassung.",
      "rechtsgrundlage": "§ 411 ZPO (schriftliches Gutachten); § 404a ZPO (Tat-/Rechtsfrage)",
      "pflichtfelder": [
        "Keine direkte Eingabe – prüft Vollständigkeit/Struktur und Sprache aus den Fach-Tabs.",
        "Voraussetzung für Export: Validator meldet ‚release-ready' (keine Errors)."
      ],
      "anleitung": "1) Validator ausführen. 2) Errors beheben (blockieren den Export). 3) Sprach-Warnungen prüfen und wertende Formulierungen in Befunden entschärfen. 4) DOCX-Vorschau ansehen, dann exportieren.",
      "tipps": [
        "Sprach-Warnungen zeigen oft unzulässige Wertungen in Tatsachen-Kapiteln (Kap. IV).",
        "Erst nach ‚release-ready' den Status auf finalisiert setzen."
      ]
    },
    {
      "id": "glossar",
      "title": "📖 Glossar",
      "zweck": "Fachbegriff-/Norm-Glossar, das im Anhang alphabetisch erscheint; automatisch aus Normen/Werkzeugen/Methoden + Seed-Katalog erstellbar.",
      "rechtsgrundlage": "Verständlichkeit/Transparenz des Gutachtens für das Gericht",
      "pflichtfelder": [
        "Je Eintrag: Begriff (Pflicht) und Erklärung; Typ/Quelle werden geführt.",
        "Manuelle Einträge (quelle='manuell') bleiben bei Auto-Erstellung erhalten."
      ],
      "anleitung": "1) ‚Automatisch erstellen' ausführen – zieht Normen, Werkzeuge und Methoden aus dem Gutachten plus Seed-Katalog. 2) Erklärungen prüfen/präzisieren. 3) Fehlende Fachbegriffe manuell ergänzen.",
      "tipps": [
        "Auto-Erstellung überschreibt manuelle Einträge nicht – eigene Präzisierungen bleiben erhalten.",
        "Ein gutes Glossar erhöht die Verständlichkeit für das nicht-fachkundige Gericht."
      ]
    },
    {
      "id": "finalarchiv",
      "title": "🔒 Final-Archiv",
      "zweck": "Unveränderliche, SHA-256-gesicherte Ablage der final korrigierten Endfassung (DOCX/PDF) mit Audit-Nachweis.",
      "rechtsgrundlage": "Revisionssicherheit/Integrität; § 411 ZPO (verbindliche schriftliche Fassung)",
      "pflichtfelder": [
        "Endfassungs-Datei (DOCX/PDF) und optionale Bemerkung.",
        "Hochladen erzeugt SHA-256 + Audit-Eintrag (hochgeladen_von/am)."
      ],
      "anleitung": "1) Final korrigierte Endfassung hochladen. 2) Datei wird mit SHA-256 abgesichert und protokolliert. 3) Bei Bedarf herunterladen; Löschen nur Administratoren mit Pflicht-Begründung (Soft-Delete).",
      "tipps": [
        "Erst nach Peer-Review/Validator die wirklich finale Fassung archivieren.",
        "Löschen ist nur als auditierter Soft-Delete (Admin + Begründung) möglich – die Endfassung bleibt nachweisbar."
      ]
    }
  ],
  "links": [
    {
      "label": "Gutachten-Modul-Doku (Online)",
      "href": docsUrl('/modules/gutachten/')
    },
    {
      "label": "BISG e.V. - Bundesfachverband der IT-Sachverständigen und -Gutachter",
      "href": "https://www.bisg-ev.de/"
    },
    {
      "label": "§ 407a ZPO - Weitere Pflichten des Sachverständigen",
      "href": "https://www.gesetze-im-internet.de/zpo/__407a.html"
    },
    {
      "label": "§ 404a ZPO - Leitung der Tätigkeit des Sachverständigen",
      "href": "https://www.gesetze-im-internet.de/zpo/__404a.html"
    }
  ],
  "module": "gutachten"
}
