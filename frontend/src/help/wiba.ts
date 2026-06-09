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
