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
