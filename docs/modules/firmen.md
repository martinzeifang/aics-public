# Firmenverwaltung

Das Firmen-Modul (`firmen/`) ist die zentrale Stammdaten- und
Strukturklammer der AI Compliance Suite. Es verwaltet Firmen- und
Produktdaten und steuert, welche Compliance-Module pro Mandant sichtbar
und aktiv sind. Alle fachlichen Module (CRA, NIS2, DSGVO, KI-VO,
Risikobewertung, Gutachten) setzen auf dieser Grundordnung auf.

## Zweck

Eine Firma ist die oberste Organisationseinheit (Mandant) in der Suite.
Die Hierarchie ist dreistufig:

```
Firma → Produkt → Projekt je Compliance-Rahmen
```

- **Firma**: Organisation/Mandant mit eindeutigem Namen sowie optionalen
  Impressums- und Stammdaten (Unternehmen, Berater, Beschreibung).
- **Produkt**: Eine Bewertungseinheit je Firma (z. B. ein Software-/
  KI-Produkt oder ein Dienst). Jede Firma hat mindestens ein
  Standard-Produkt; weitere Produkte lassen sich frei anlegen.
- **Projekt**: Pro Produkt entsteht je benötigtem Compliance-Rahmen ein
  eigenes Projekt im jeweiligen Fachmodul. Ein Produkt kann mehrere
  Rahmen-Projekte besitzen (z. B. CRA *und* NIS2).

Das Modul selbst enthält keine Fragebogen-, Bewertungs- oder
Berichtslogik. Es liefert die mandantenfähige Single Source of Truth, aus
der die fachlichen Projekte hervorgehen. Änderungen an den Stammdaten
wirken modulübergreifend auf alle nachgelagerten Projekte.

### Rechtlicher und organisatorischer Rahmen

Für die Firmenverwaltung selbst gibt es kein eigenes Fachgesetz. Das Modul
setzt aber die Rechenschafts- und Nachweispflichten der einschlägigen
Regelwerke organisatorisch um — saubere Stammdaten je Firma/Produkt sind
die Voraussetzung, um Nachweise konsistent und prüffest zu führen:

- **DSGVO Art. 5 Abs. 2 i. V. m. Art. 24** — Rechenschaftspflicht: Der
  Verantwortliche muss die Einhaltung nachweisen können, was eine klare
  Zuordnung von Verarbeitungen zu Verantwortlichen/Produkten erfordert.
- **DSGVO Art. 30** — Verzeichnis von Verarbeitungstätigkeiten: pro
  Verantwortlichem zu führen; die produktbezogene Struktur liefert die
  Grundlage für vollständige Einträge.
- **CRA (VO (EU) 2024/2847) Art. 13 / Anhang VII** — produktbezogene
  technische Dokumentation und Konformitätsnachweise setzen eine
  eindeutige Produkt-/Hersteller-Zuordnung voraus.
- **NIS2 (RL (EU) 2022/2555) Art. 20–21** — Verantwortung der
  Leitungsorgane und Risikomanagement je Einrichtung verlangen eine
  eindeutige Zuordnung von Maßnahmen zur jeweiligen Organisation/Dienst.
- **KI-VO (VO (EU) 2024/1689) Art. 11 / Anhang IV** — technische
  Dokumentation je KI-System benötigt eine klare Bindung an Anbieter und
  konkretes System/Produkt.

Der vollständige DSGVO-Text ist über
[EUR-Lex](https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX:32016R0679)
abrufbar.

## Mandantenfähigkeit

Alle Firmen- und Produktdaten liegen in einer eigenen Datenbank:

| Aspekt | Details |
|---|---|
| **Datenbank** | `data/db/firmen.sqlite` |
| **Tabellen** | `firmen` (Mandanten), `produkte` (Bewertungseinheiten) |
| **LLM** | nicht erforderlich (reines Stammdaten-/CRUD-Modul) |

Die Daten sind je Firma sauber getrennt. Diese Mandantentrennung wirkt
sich auf alle nachgelagerten Bereiche aus:

- **Datenisolation**: Jede Firma ist über ihren eindeutigen Namen
  referenziert; Produkte hängen per Fremdschlüssel an genau einer Firma
  (`ON DELETE CASCADE`).
- **Modul-Projekte**: Beim Anlegen einer Firma werden für die aktivierten
  Module idempotent Projekte angelegt — getrennt nach Firma und Produkt.
  Pro Produkt entsteht z. B. ein eigenes CRA-Projekt.
- **Nachweisbibliothek**: Die hochgeladenen Nachweise (`evidence/`) sind
  je Firma getrennt, sodass Belege und Verantwortlichkeiten nicht
  vermischt werden.
- **Soft-Delete**: Firmen und Produkte werden zunächst nur archiviert
  (`is_deleted`-Flag) und lassen sich wiederherstellen; das endgültige
  Löschen ist ein separater Schritt.

## Framework-Selektion pro Firma

Pro Firma legst du fest, welche Compliance-Module aktiv sind und welche
Methodik gilt. Diese Auswahl steuert, was in den Modul-Wizards angeboten
wird:

- **Modul-Steuerung**: Über Schalter aktivierst/deaktivierst du die Module
  Risikobewertung, Gutachten, CRA, DSGVO, NIS2 und KI-VO (AI Act) pro
  Firma. Nur tatsächlich anwendbare Rahmen aktivieren — das vermeidet
  Scheinpflichten.
- **Risikomethodik (`rb_framework`)**: Auswahl der
  Risikobewertungsmethodik für die Firma (STRIDE, Finanzinstitute,
  HEAVENS, OCTAVE, TARA). Wird eine Firma im Risikobewertungs-Wizard
  ausgewählt, wird ihre Methodik vorbelegt.
- **Gutachten-Frameworks**: Auswahl der für Gutachten relevanten Rahmen
  (DORA, NIS2, CRA, ISO 27001, DSGVO, KI-VO, BSI).
- **Produktklasse (CRA)**: Pro Produkt wählbar zwischen *Nicht gelistet*
  (default), *Important Class I/II* (Annex III) und *Critical Class I/II*
  (Annex IV). Die Klasse wird in die CRA-Projekte des Produkts übernommen.

Wird eine Firma in einem Modul-Wizard ausgewählt, übernimmt das jeweilige
Fachmodul die hinterlegten Stammdaten (Unternehmen, Berater, Produkt,
Produktklasse, Methodik) als Vorbelegung. So entstehen keine doppelten
Anlagen und keine inkonsistenten Zuordnungen.

## Impressum & Produkte

Zwei Dialoge beschleunigen die Stammdatenpflege:

### Impressum-Import

Über *„Aus Website-Impressum anlegen"* trägst du eine Website-URL ein. Die
Suite crawlt die Seite (standardmäßig bis zu fünf Unterseiten, maximal 50)
und versucht, das Impressum zu erkennen. Erkannte Felder (Unternehmen,
Rechtsform, Adresse, Vertreter, E-Mail, Telefon, USt-ID, HRB) werden in
einer Vorschau angezeigt und lassen sich per Klick direkt ins
Firmen-Formular übernehmen. Ausgehende URLs werden serverseitig gegen
SSRF-Angriffe geprüft (Loopback-, interne und Cloud-Metadaten-Adressen
sind blockiert).

### Produkt-Anlage und Standard-Produkt

Im Produkt-Dialog legst du je Firma ein Produkt mit Name, Beschreibung und
CRA-Produktklasse an. Über die Option *„Als Standard-Produkt setzen"*
bestimmst du das Default-Produkt der Firma — pro Firma ist immer genau ein
Produkt als Standard markiert. Beim Anlegen oder Ändern eines Produkts
wird (sofern CRA für die Firma aktiv ist) idempotent ein passendes
CRA-Projekt angelegt bzw. synchronisiert: Das Standard-Produkt nutzt den
Firmennamen, weitere Produkte den Namen *„Firma – Produkt"*.

## Migrations-Hinweis

Das Firmen-Modul hieß früher „Kunden" und wurde mit #1003 umbenannt. Für
Rückwärtskompatibilität bleibt der alte Zugang bestehen:

- **REST-Alias**: Die alte Route `/api/kunden` funktioniert weiterhin als
  Deprecation-Alias der neuen Route `/api/firmen` (gleiche Funktionen,
  gleiche Zugriffsberechtigungen). Der Alias bleibt mindestens einen
  Release lang erhalten; neue Integrationen sollten `/api/firmen`
  verwenden.
- **DB-Auto-Migration**: Existiert beim Start nur die alte
  `kunden.sqlite` (ohne `firmen.sqlite`), wird sie samt WAL-/SHM-Dateien
  automatisch zu `firmen.sqlite` umbenannt. Zusätzlich werden — falls noch
  vorhanden — die alte Tabelle `kunden` zu `firmen` und die Spalte
  `produkte.kunden_id` zu `produkte.firmen_id` migriert. Die Migration ist
  idempotent und greift nur, solange die neuen Namen fehlen.

## GUI-Start

Das Firmen-Modul ist als Tab in der AI Compliance Suite verfügbar und in
der Web-App unter `/firmen` erreichbar (kein eigenständiger Standalone-
oder CLI-Start).

## Querbezüge

- [Module-Übersicht](index.md)
- [CRA-Readiness](cra.md)
- [Risikobewertung](risikobewertung.md)
- [Gutachten](gutachten.md)

## Firmen-Dashboard, Risiko-Cockpit und Berichte (v7.0.0)

Nach Auswahl einer Firma stehen fünf Reiter zur Verfügung:

| Reiter | Inhalt |
|---|---|
| **📊 Dashboard** | Gesamt-Umsetzungsgrad (Ø der Module CRA, NIS2, AI Act, DSGVO, WiBA), Umsetzungsgrad je Modul und Projekt (gleiche Berechnung wie die Modul-Dashboards), offene Risiken nach Schwere, DSGVO-TOM und BSI-WiBA, offene Aufgaben und Fristen, Produkte, Nachweise, zuletzt erzeugte Berichte |
| **🏢 Stammdaten & Module** | Stammdaten, Modul-Aktivierung, Risiko-Projekte, Produkte, Nachweise, Gutachten-Frameworks |
| **⚠️ Risiko-Cockpit** | Alle offenen Risiken/Schwachstellen der Firma modulübergreifend (Risikobewertung, CRA, SOC) |
| **🛡️ Pentests** | Pentest-Berichte (PDF) mit Findings, Status und Nachtest; Übernahme nach CRA, DSGVO-TOM und WiBA (siehe unten) |
| **📄 Berichte** | **Firmen-Gesamtbericht** (Management-Überblick) und **Risikobericht** als Word/PDF, Ablage mit Historie, KI-Management-Zusammenfassung |

Projekte werden der Firma über die Firmen-ID, den Firmennamen bzw. die Unternehmensbezeichnung
zugeordnet. API: `GET /api/firmen/<firma>/uebersicht`, Berichte unter
`/api/firmen/projekte/<firma>/berichte…`.

## Pentest-Berichte als Nachweis (v7.1.0)

Ein Pentest-Bericht wird **einmal bei der Firma** hochgeladen (Reiter **🛡️ Pentests**). Die Datei
liegt im Firmen-Nachweis-Store (Magic-Bytes-Prüfung, optional verschlüsselt) und erscheint auch unter
*Nachweise*. Der Text wird beim Upload extrahiert.

**Findings herauslösen.** „🤖 Findings extrahieren“ teilt lange Berichte in Teile (je ca. 16 000
Zeichen), damit auch lokale Modelle jeden Teil vollständig lesen. Zwei Wege:

- **⚡ Direkt mit KI** über den konfigurierten Anbieter – erst nach ausdrücklicher Bestätigung; der
  Abfluss wird ohne Inhalte (Länge, SHA-256) im Audit-Trail festgehalten. Ist ein Cloud-Anbieter
  konfiguriert, weist die Suite deutlich auf die Sensibilität hin.
- **📋 Copy/Paste**: Prompt je Teil kopieren, Antwort einfügen.

Die Vorschau zeigt alle Findings (Ref, Titel, Schwere, CVSS, Kategorie, System) zur Prüfung und
Auswahl. Erneutes Extrahieren aktualisiert Inhalte, **Status und Zuordnungen bleiben erhalten**.

**Übernahme in die Module** (Vorschlag → Bestätigung):

| Ziel | Wirkung |
|---|---|
| **CRA** (Anwendungs-Pentest) | Findings werden Schwachstellen (`cra_vuln`, Quelle `pentest`, ID `PT-<Bericht>-<Ref>`) mit Fristen und Issue-Anbindung; optional Risiken in der verknüpften Risikobewertung (Provenienz wie CVE-Import → keine Dubletten im Risiko-Cockpit); der Bericht wird in der technischen Akte unter Anhang VII „Testberichte“ abgelegt; bereits bewertete OWASP-Kontrollen der betroffenen Kategorie erhalten „⚠️ Neubewertung erforderlich“ (Score bleibt). |
| **DSGVO-TOM** (Infrastruktur) | Zuordnung Finding → TOM (Vorschlag aus der Kategorie). Je TOM eine Zeile in der **Wirksamkeitsprüfung** (Art. 32 Abs. 1 lit. d) – auch „geprüft ohne Befund“. Der TOM-Katalog zeigt „🛡️ Pentest: n offene Finding(s) – Wirksamkeit eingeschränkt“. Der TOM-**Status wird nicht verändert**. Optional Risiken in der Risikobewertung. |
| **WiBA** | Bericht als Beleg an den gewählten Prüffragen. Ist eine Prüffrage mit „Ja“ beantwortet und das Finding offen, wird sie zur Neubewertung markiert – die Antwort ändert sich nie automatisch. |

**Status und Nachtest.** Status je Finding: offen, behoben, akzeptiert (Restrisiko), False Positive.
Ein Statuswechsel fließt zurück: CRA-Schwachstelle (`fixed`/`wontfix`), Risiko erledigt/wieder offen,
Wirksamkeitszeile der TOM. Ein Bericht mit „Nachtest von …“ schlägt vor, welche offenen Findings des
Ursprungsberichts nicht mehr gefunden wurden; sie lassen sich mit dem Nachtest als Beleg als behoben
markieren.

API: `/api/pentest/<firma>/berichte[/<id>]`, `…/extract/{prompt,parse,stream}`, `…/findings`,
`/api/pentest/<firma>/findings/<id>`, `…/nachtest-vorschlag`, `…/{cra,dsgvo,wiba}` (+ `…/dsgvo/vorschlag`,
`…/wiba/vorschlag`), `/api/pentest/dsgvo/<projekt>/tom-hinweise`.

## Word-Vorlagen je Mandant (v8.0.4)

Reiter „🧾 Vorlagen" in der Firma. Hintergrund ist keine Frage des Geschmacks:
**EU-Konformitätserklärung, Konformitätsnachweis und Kundenfassung stellt nicht
der Dienstleister aus, sondern der Hersteller.** Die Erklärung nach Art. 28
i.V.m. Anhang V der Verordnung (EU) 2024/2847 unterschreibt der Mandant unter
seinem Namen und trägt dafür die Alleinverantwortung — ein Dokument, das er in
eigenem Namen in Verkehr gibt, darf nicht im Papier des Beraters erscheinen.

* Eine hier hinterlegte Vorlage gilt **nur für diesen Mandanten** und geht der
  Haus-Vorlage vor. Ohne eigene Vorlage entstehen die Dokumente weiter im
  Hausformat; der Reiter zeigt die geltenden Haus-Vorlagen mit an.
* Die Zuordnung läuft über `firmen_id`. Ist die Firma noch nicht verknüpft
  (Admin → „Firmen-Zuordnung"), sind keine eigenen Vorlagen möglich — das sagt
  der Reiter, statt sie stillschweigend wirkungslos abzulegen.
* **Form, nicht Inhalt:** Die Pflichtangaben bleiben serverseitig erzwungen. Eine
  Kundenvorlage, die eine Anhang-V-Angabe oder beim Nachweis Produkt und Release
  auslässt, kann nicht Standard werden.
* Fremde Mandantenvorlagen erscheinen nirgends: Die Liste ist gegen die
  Firmen-Whitelist (`allowed_firmen`) **fail-closed** — eine Vorlagenliste nennt
  sonst die Namen fremder Mandanten.
* Haus-Vorlagen bleiben im Admin-Bereich unter „📄 Word-Vorlagen"; dort ist auch
  die Variablenliste je Modul.
