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
