// Auto-generiert (#926) — Modul-Hilfe-Inhalt.
import type { ModuleHelp } from './types'
import { docsUrl } from './docsUrl'

export const wibaHelp: ModuleHelp = {
  "title": "WiBA",
  "regulation": "BSI „Weg in die Basis-Absicherung\" (WiBA) – Teil des BSI IT-Grundschutz",
  "purpose": "Das WiBA-Modul unterstützt kleine und mittlere Organisationen (KMU, Kommunen, Vereine) dabei, mit dem BSI-Vorgehen „Weg in die Basis-Absicherung\" einen strukturierten, prüffähigen Nachweis für einen sicheren IT-Betrieb (insbesondere mit Blick auf den Datenschutz) zu führen. Anhand der BSI-Themen-Checklisten (19 Themen / 257 Prüffragen) werden Prüffragen mit Ja/Nein/Nicht relevant beantwortet und daraus ein Reifegrad abgeleitet.",
  "legalBasis": {
    "title": "Was WiBA verlangt",
    "intro": "WiBA ist ein niedrigschwelliger Einstieg des BSI in den IT-Grundschutz. Statt der vollständigen Basis-Absicherung arbeiten Organisationen anhand von Themen-Checklisten mit konkreten Prüffragen, die auf die zugrundeliegenden IT-Grundschutz-Bausteine verweisen. Ziel ist ein nachvollziehbarer Mindeststandard für einen sicheren IT-Betrieb.",
    "bullets": [
      "Themen-Checklisten: WiBA gliedert die Basis-Absicherung in 19 Themen mit insgesamt 257 Prüffragen (Stand WiBA 2.0 / 2023).",
      "Prüffragen je Thema verweisen auf die zugrundeliegenden IT-Grundschutz-Bausteine (z. B. CON.3 Datensicherungskonzept), ein Ziel, einen allgemeinen Hinweis und weiterführende Informationen.",
      "Natives Antwortmodell: jede Prüffrage wird mit Ja (umgesetzt), Nein (offen) oder Nicht relevant (außer Scope) beantwortet.",
      "WiBA ist Teil des BSI IT-Grundschutz und als Einstieg für KMU, Kommunen und Vereine gedacht, die noch kein vollständiges ISMS betreiben.",
      "Die BSI-Quelldateien (WiBA-Tool, Checklisten) unterliegen dem Copyright des BSI und werden zur Laufzeit von der BSI-Website geladen, nicht mitgeliefert."
    ]
  },
  "implementation": {
    "title": "Vorgehen im Modul",
    "intro": "Zunächst spielt der Administrator den aktuellen WiBA-Prüffragen-Katalog ein (BSI-Download + Import). Anschließend legen Sie ein Projekt an, ordnen es einer Firma zu, beantworten die Prüffragen je Thema und lesen den Reifegrad ab. KI-Prompts und Nachweis-Vorschläge unterstützen das Vorausfüllen; offene Punkte lassen sich als Risiken und Issues weiterverarbeiten.",
    "bullets": [
      "Katalog pflegen (Admin): BSI-Quellen herunterladen und importieren; der Katalog ist updatefähig und ersetzt bei einem Re-Import nur die Prüffragen, nicht die bereits erfassten Antworten.",
      "Projekt anlegen und einer Firma zuordnen (Feld Unternehmen); die Firmenzuordnung ist Grundlage für Nachweis-Vorschläge und das Risiko-Cockpit.",
      "Prüffragen je Thema mit Ja/Nein/Nicht relevant beantworten und Notiz, Verantwortlichen, Zieldatum sowie Evidenz-Verweise erfassen.",
      "Reifegrad ablesen (gesamt und je Thema): Ja = 100 %, Nein/Offen = 0 %, Nicht relevant wird aus dem Nenner ausgeklammert.",
      "KI-Assistent (Copy/Paste) nutzen: Prompt je Prüffrage erzeugen — inklusive der bei der Firma hinterlegten Nachweise — in ChatGPT beantworten und die JSON-Antwort zurück einfügen.",
      "DSGVO-TOM-Maßnahmen der Firma als Nachweis-Vorschlag übernehmen; Nein-Befunde als Risiken in die Risikobewertung übergeben; Prüffragen als GitHub-/GitLab-Issue tracken.",
      "Nachweis-Report (DOCX/PDF) mit Reifegrad-Übersicht und offenen Punkten exportieren."
    ]
  },
  "moduleSpecific": {
    "title": "Besonderheiten des WiBA-Moduls",
    "intro": "Das Modul kombiniert den DB-gestützten, updatefähigen BSI-Katalog mit der suite-einheitlichen Reifegrad-Logik und verzahnt WiBA mit DSGVO, Risikobewertung und Issue-Tracking.",
    "bullets": [
      "DB-gestützter Katalog: Themen und Prüffragen liegen in der Datenbank (nicht im Code), damit BSI-Updates per Admin-Download eingespielt werden können.",
      "BSI-Quelldateien werden aus urheberrechtlichen Gründen nicht mitgeliefert, sondern zur Laufzeit von der BSI-Website geladen.",
      "Reifegrad-Mapping: Nicht relevant zählt nicht zur Basis (außer Scope); Offen zählt mit 0 % zum Scope, damit unbearbeitete Fragen den Reifegrad nicht beschönigen.",
      "KI-Prompt bezieht den Thema-/Baustein-Kontext und optional die bei der Firma hochgeladenen Nachweise (Evidence Library) ein.",
      "Verzahnung: DSGVO-TOM als Nachweis-Vorschlag, Nein-Befunde als Risiken (verknüpftes RB-Projekt), Sichtbarkeit im Risiko-Cockpit, Issue-Tracking pro Prüffrage (GitHub/GitLab)."
    ]
  },
  "areas": [
    {
      "id": "dashboard",
      "title": "📊 Dashboard",
      "zweck": "Überblick über den Reifegrad gesamt und je Thema, Antwort-Verteilung (Ja/Nein/Nicht relevant/Offen) und offene Punkte des WiBA-Projekts.",
      "rechtsgrundlage": "BSI „Weg in die Basis-Absicherung\" (WiBA), IT-Grundschutz",
      "pflichtfelder": [
        "Keine direkte Eingabe – das Dashboard verdichtet die Daten der Prüffragen.",
        "Voraussetzung: Katalog eingespielt und Projekt einer Firma zugeordnet."
      ],
      "anleitung": "1) Projekt-/Firmenzuordnung prüfen. 2) Reifegrad gesamt und je Thema ablesen. 3) Themen mit vielen offenen/Nein-Fragen priorisiert im Tab Prüffragen bearbeiten.",
      "tipps": ["Reifegrad: Ja = 100 %, Nein/Offen = 0 %, Nicht relevant zählt nicht zum Nenner."]
    },
    {
      "id": "risikocockpit",
      "title": "📊 Risiko-Cockpit",
      "zweck": "Firmenweite, modulübergreifende Read-only-Sicht auf offene Risiken der zugeordneten Firma – inklusive der aus WiBA-Nein-Befunden erzeugten Risiken.",
      "rechtsgrundlage": "BSI IT-Grundschutz (risikoorientierte Basis-Absicherung)",
      "pflichtfelder": [
        "Keine Eingabe – Aggregation pro Firma (firmen_id) aus den verknüpften Modulen."
      ],
      "anleitung": "1) Firmen-Zuordnung des Projekts sicherstellen. 2) Offene Risiken sichten. 3) Aus Prüffragen erzeugte Nein-Befunde im verknüpften Risikobewertungs-Projekt behandeln.",
      "tipps": ["Nein-Befunde werden über „Als Risiko\" im Prüffragen-Tab ins verknüpfte RB-Projekt überführt und erscheinen hier."]
    },
    {
      "id": "dokumentation",
      "title": "📋 Dokumentation",
      "zweck": "Verwaltung des BSI-WiBA-Prüffragen-Katalogs (Themen + Prüffragen): Download der BSI-Quellen, Import und Update auf neue WiBA-Versionen (Admin).",
      "rechtsgrundlage": "BSI WiBA-Checklisten + WiBA-Tool (19 Themen / 257 Prüffragen); BSI-Copyright (Quellen nur zur Laufzeit geladen)",
      "pflichtfelder": [
        "BSI-Quelldateien (Checklisten-ZIP + WiBA-Tool-XLSX) herunterladen (Admin-Recht WIBA_CATALOG).",
        "Katalog importieren/aktualisieren (ersetzt nur die Prüffragen, nicht die erfassten Antworten).",
        "Katalog-Version/Quelle prüfen (Aktualität)."
      ],
      "anleitung": "1) BSI-Quellen über den Download-/Refresh-Button laden. 2) Import ausführen – Themen und Prüffragen werden in der DB angelegt/aktualisiert. 3) Version kontrollieren. Erst danach steht der Tab Prüffragen vollständig bereit.",
      "tipps": [
        "Die BSI-Originale werden aus Urheberrechtsgründen nicht mitgeliefert, sondern zur Laufzeit geladen.",
        "Ein Re-Import lässt bereits erfasste Antworten unangetastet."
      ]
    },
    {
      "id": "prueffragen",
      "title": "✅ Prüffragen",
      "zweck": "Eigentliche Beantwortung der WiBA-Prüffragen je Thema mit Status, Notiz, Verantwortlichem, Zieldatum und Nachweisen – Grundlage des Reifegrads.",
      "rechtsgrundlage": "BSI WiBA-Prüffragen (verweisen auf IT-Grundschutz-Bausteine, z. B. CON.3 Datensicherung)",
      "pflichtfelder": [
        "Status je Prüffrage: Ja (umgesetzt) / Nein (offen) / Nicht relevant (außer Scope) / Offen (unbearbeitet).",
        "Notiz/Begründung – insb. bei „Nicht relevant\" (Begründung des Ausschlusses) und „Nein\".",
        "Verantwortlich (Name/Rolle) und Zieldatum bei offenen Punkten.",
        "Evidenz/Nachweis(e) verknüpfen (evidence_doc_ids; optional DSGVO-TOM als Vorschlag)."
      ],
      "anleitung": "1) Thema wählen, Prüffrage öffnen. 2) Status setzen (Ja/Nein/Nicht relevant). 3) Notiz, Verantwortlichen und Zieldatum erfassen. 4) Nachweise anhängen. 5) Speichern. 6) Nein-Befunde optional „Als Risiko\" übergeben oder als Issue tracken.",
      "tipps": [
        "„Nicht relevant\" immer begründen – sonst ist der Scope-Ausschluss nicht prüffähig.",
        "Offene Fragen zählen mit 0 % – sie beschönigen den Reifegrad nicht.",
        "Der KI-Assistent kann je Prüffrage einen Antwort-Entwurf liefern (Copy/Paste)."
      ]
    },
    {
      "id": "assistenten",
      "title": "🤖 Assistenten",
      "zweck": "KI-gestützte Wizards (Copy/Paste-Prompts), die Antwort-Entwürfe je Prüffrage/Thema liefern – inklusive der bei der Firma hinterlegten Nachweise.",
      "rechtsgrundlage": "— (Hilfsmittel; die fachliche Bewertung der Prüffrage bleibt beim Anwender)",
      "pflichtfelder": [
        "Keine Pflichtfelder – der Prompt zieht den Thema-/Baustein-Kontext und Firmen-Nachweise automatisch."
      ],
      "anleitung": "1) Assistenten/Prüffrage wählen. 2) Prompt erzeugen, in das KI-Tool kopieren. 3) JSON-Antwort zurück einfügen. 4) Status/Notiz im Prüffragen-Tab übernehmen und prüfen.",
      "tipps": ["KI-Vorschläge fachlich gegenprüfen – sie ersetzen keine Bewertung des sicheren Betriebs."]
    },
    {
      "id": "dokumente",
      "title": "📄 Dokumente",
      "zweck": "Ablage und Verwaltung der Nachweise (Konzepte, Screenshots, Konfigurationen), die als Evidenz an Prüffragen verknüpft werden.",
      "rechtsgrundlage": "BSI IT-Grundschutz (Nachweisführung zur Basis-Absicherung)",
      "pflichtfelder": [
        "Datei + aussagekräftiger Name; Dokumenttyp.",
        "Verknüpfung mit der/den belegten Prüffrage(n) im Prüffragen-Tab."
      ],
      "anleitung": "1) Nachweis hochladen und eindeutig benennen. 2) Im Prüffragen-Tab als Evidenz auswählen. 3) Bei Aktualisierung neue Version ablegen statt überschreiben.",
      "tipps": ["Bei der Firma hinterlegte Nachweise (Evidence Library) fließen auch in die KI-Prompts ein."]
    },
    {
      "id": "bericht",
      "title": "📄 Bericht",
      "zweck": "Export des WiBA-Nachweis-Reports (Reifegrad-Übersicht, Antworten je Thema, offene Punkte) als DOCX/PDF.",
      "rechtsgrundlage": "BSI WiBA (prüffähiger Nachweis sicheren IT-Betriebs)",
      "pflichtfelder": [
        "Auswahl der Berichtsabschnitte und Format (DOCX/PDF)."
      ],
      "anleitung": "1) Vorab die Prüffragen weitgehend beantworten. 2) Abschnitte wählen. 3) Bericht erzeugen und als Nachweis ablegen/weitergeben.",
      "tipps": ["Die Berichtsqualität hängt direkt von vollständig beantworteten Prüffragen und verknüpften Nachweisen ab."]
    }
  ],
  "links": [
    {
      "label": "WiBA-Modul-Doku (Online)",
      "href": docsUrl('/modules/wiba/')
    },
    {
      "label": "BSI – Weg in die Basis-Absicherung (WiBA)",
      "href": "https://www.bsi.bund.de/dok/wiba"
    },
    {
      "label": "BSI IT-Grundschutz",
      "href": "https://www.bsi.bund.de/grundschutz"
    }
  ],
  "module": "wiba"
}
