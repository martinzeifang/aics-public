// Auto-generiert (#926) — Modul-Hilfe-Inhalt.
import type { ModuleHelp } from './types'

export const nis2Help: ModuleHelp = {
  "title": "NIS2",
  "regulation": "Richtlinie (EU) 2022/2555 (NIS2-Richtlinie) — in Deutschland umgesetzt durch das NIS2-Umsetzungsgesetz (NIS2UmsuCG, Änderungen u.a. im BSIG)",
  "purpose": "Das Modul unterstützt die strukturierte Umsetzung und Nachweisführung der NIS2-Cybersicherheitsanforderungen. Es bildet den Maßnahmenkatalog nach Art. 21, die Governance-Pflichten nach Art. 20 und die Meldepflichten nach Art. 23 ab und erfasst die Einstufung als wesentliche oder wichtige Einrichtung. Ergebnis ist ein bewerteter Anforderungskatalog mit Reifegrad und exportierbarem Bericht.",
  "legalBasis": {
    "title": "Rechtsgrundlage: NIS2-Richtlinie (EU) 2022/2555",
    "intro": "Die NIS2-Richtlinie verpflichtet wesentliche und wichtige Einrichtungen der in Anhang I und II genannten Sektoren zu einem risikobasierten Cybersicherheits-Management. Sie verlangt verbindliche technische und organisatorische Mindestmaßnahmen, eine aktive Verantwortung der Leitungsorgane sowie ein abgestuftes Meldeverfahren bei erheblichen Sicherheitsvorfällen. Verstöße sind bußgeldbewehrt; die Geschäftsleitung haftet persönlich.",
    "bullets": [
      "Art. 21 Abs. 1 NIS2-RL: Geeignete und verhältnismäßige technische, operative und organisatorische Risikomanagementmaßnahmen nach dem Stand der Technik (All-Hazards-Ansatz).",
      "Art. 21 Abs. 2 NIS2-RL: Mindestkatalog von 10 Maßnahmenbereichen — u.a. Risikoanalyse und Sicherheit der Informationssysteme (lit. a), Bewältigung von Sicherheitsvorfällen (lit. b), Business Continuity/Backup/Krisenmanagement (lit. c), Sicherheit der Lieferkette (lit. d), Sicherheit bei Erwerb, Entwicklung und Wartung (lit. e), Bewertung der Wirksamkeit (lit. f), Cyberhygiene und Schulungen (lit. g), Kryptografie/Verschlüsselung (lit. h), Personalsicherheit, Zugriffskontrolle und Asset Management (lit. i), MFA und gesicherte Kommunikation (lit. j).",
      "Art. 20 NIS2-RL: Leitungsorgane müssen die Risikomanagementmaßnahmen billigen, deren Umsetzung überwachen und an Schulungen teilnehmen; Verantwortung und Haftung liegen beim Management.",
      "Art. 23 NIS2-RL: Meldepflicht bei erheblichen Sicherheitsvorfällen — Frühwarnung innerhalb von 24 Stunden, Vorfallmeldung innerhalb von 72 Stunden, Abschlussbericht spätestens 1 Monat nach der Meldung (Zwischenbericht auf Anforderung).",
      "Anhang I (wesentliche Einrichtungen, z.B. Energie, Verkehr, Bankwesen, Gesundheit, Wasser, digitale Infrastruktur) und Anhang II (wichtige Einrichtungen, z.B. Post, Abfall, Chemie, Lebensmittel, verarbeitendes Gewerbe, digitale Dienste) bestimmen Einstufung und Aufsichtsregime.",
      "Art. 24-25 NIS2-RL: Möglichkeit, europäische Cybersicherheitszertifizierungsschemata und Normen zum Nachweis der Konformität heranzuziehen."
    ]
  },
  "implementation": {
    "title": "Vorgehen im Modul",
    "intro": "Im Modul wird zunächst die Einrichtungsklasse (wesentlich/wichtig) bestimmt; danach wird der Anforderungskatalog entlang der Kapitel Governance (Art. 20), Risikomanagement/technische Maßnahmen (Art. 21), Meldepflichten (Art. 23) und Lieferkettensicherheit bewertet. Jede Anforderung erhält einen Reifegrad auf der Skala 0-5 mit Nachweisbezug; der Gesamtstand wird verdichtet und als Bericht exportiert.",
    "bullets": [
      "Einrichtungsklasse zuerst festlegen — sie bestimmt Aufsichts- und Nachweistiefe und damit die Priorisierung der Maßnahmen.",
      "Jede der 10 Maßnahmen aus Art. 21 Abs. 2 einzeln bewerten und je Anforderung konkrete Nachweise hinterlegen (Richtlinien, Protokolle, Schulungsnachweise, Backup-/BCM-Konzepte).",
      "Reifegrad konsistent vergeben: 0 nicht bewertet, 1 nicht erfüllt, 2 in Planung, 3 teilweise, 4 weitgehend, 5 vollständig erfüllt; Gewichtung beachten.",
      "Leitungsverantwortung dokumentieren (Genehmigung der Maßnahmen, Überwachung, Management-Schulungen) als Nachweis zu Art. 20.",
      "Meldeprozess vorab definieren und üben: Eskalationswege, Zuständigkeiten und die Fristen 24h/72h/1 Monat als Runbook festhalten.",
      "Lieferkettensicherheit gesondert betrachten (Anbieterbewertung, Vertragsklauseln) — Art. 21 Abs. 2 lit. d.",
      "Offene und nur teilweise erfüllte Anforderungen in Maßnahmen mit Verantwortlichen und Terminen überführen und über den Bericht nachverfolgen."
    ]
  },
  "moduleSpecific": {
    "title": "Besonderheiten des NIS2-Moduls",
    "intro": "Das Modul ist auf die spezifische Struktur der NIS2-Pflichten zugeschnitten und verbindet Maßnahmenkatalog, Meldefristen und Einrichtungs-Einstufung in einem Bewertungsworkflow.",
    "bullets": [
      "Maßnahmenkatalog nach Art. 21: Die 10 Mindestmaßnahmen sind als bewertbare Einzelanforderungen mit Artikel-Referenz und Nachweishinweisen hinterlegt.",
      "Einrichtungs-Einstufung: Auswahl zwischen wesentlicher Einrichtung (Anhang I), wichtiger Einrichtung (Anhang II) oder beidem; steuert den Bewertungskontext.",
      "Meldefristen-Logik nach Art. 23: 24h-Frühwarnung, 72h-Vorfallmeldung, 1-Monats-Abschlussbericht als feste Referenzwerte im Modul.",
      "Kapitelgliederung: Governance (Art. 20), Risikomanagement/technisch (Art. 21), Meldepflichten (Art. 23), Lieferkette (Art. 21 Abs. 2 lit. d) sowie Implementierung/Zertifizierung (Art. 24-25).",
      "Bewertungsskala 0-5 mit Gewichtung je Anforderung und Reifegrad-Verdichtung für den Gesamtüberblick.",
      "Berichtsexport zur Dokumentation des Umsetzungsstands gegenüber Leitung und Aufsichtsbehörde."
    ]
  },
  "links": [
    {
      "label": "Modul-Dokumentation NIS2",
      "href": "docs/modules/nis2.md"
    },
    {
      "label": "NIS2-Richtlinie (EU) 2022/2555 (EUR-Lex)",
      "href": "https://eur-lex.europa.eu/eli/dir/2022/2555/oj"
    }
  ],
  "module": "nis2"
}
