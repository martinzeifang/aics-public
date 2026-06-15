# WiBA (Weg in die Basis-Absicherung)

Das WiBA-Modul unterstützt kleine und mittlere Organisationen (KMU, Kommunen,
Vereine) dabei, mit dem BSI-Vorgehen **„Weg in die Basis-Absicherung" (WiBA)**
einen strukturierten, prüffähigen Nachweis für einen sicheren IT-Betrieb zu führen.

## Zweck

WiBA ist ein niedrigschwelliger Einstieg des BSI in den IT-Grundschutz. Statt der
vollständigen Basis-Absicherung arbeiten Anwender:innen anhand von Themen-Checklisten
mit konkreten **Prüffragen** und beantworten diese mit *Ja / Nein / Nicht relevant*.

Das Modul hilft, daraus einen nachvollziehbaren Reifegrad und einen Nachweis für
einen sicheren IT-Betrieb (insbesondere mit Blick auf den Datenschutz) zu erzeugen:

- Pflege des WiBA-Prüffragen-Katalogs (**19 Themen-Checklisten / 257 Prüffragen**,
  Stand WiBA 2.0 / 2023) als Kontrollen — vergleichbar zu CRA/DSGVO.
- Bewertung je Prüffrage (*Ja* = umgesetzt, *Nein* = offen, *Nicht relevant* = außer
  Scope) mit Notiz, Verantwortlichem und Zieldatum.
- Ableitung eines **Reifegrads** gesamt und je Thema.
- KI-gestütztes Vorausfüllen per Copy/Paste-Prompt unter Einbeziehung der bei der
  Firma hinterlegten Nachweise.
- Verzahnung mit DSGVO-TOM, Risikobewertung, Risiko-Cockpit und Issue-Tracking.

> Hinweis: Die Prozessbeschreibungen in dieser Doku sind technische Guidance und
> keine Rechtsberatung. Maßgeblich ist das jeweils aktuelle BSI-WiBA-Material.

### Bezug zum BSI-WiBA

WiBA ist Teil des [BSI IT-Grundschutz](https://www.bsi.bund.de/dok/wiba). Die
Prüffragen je Thema verweisen auf die zugrundeliegenden IT-Grundschutz-Bausteine
(z. B. `CON.3 Datensicherungskonzept`), ein Ziel, einen allgemeinen Hinweis sowie
weiterführende Informationen — diese Metadaten werden aus den BSI-Checklisten
übernommen und im Modul je Thema angezeigt.

## Verzeichnisstruktur

```
wiba/
├── __init__.py
├── constants.py      # Antwort-/Status-Modell (ja/nein/nicht_relevant) + Reifegrad-Mapping
├── db.py             # SQLite (Projekte, Antworten, Katalog, Katalog-Meta)
├── io_source.py      # BSI-Download + Parser (WiBA-Tool-XLSX + Checklisten-ZIP)
└── prompts.py        # Copy/Paste-KI-Prompts je Prüffrage
```

## Datenhaltung

WiBA-Projekte, Antworten und der Prüffragen-Katalog liegen in `data/db/wiba.sqlite`.

WiBA-DB-Tabellen (Auszug):

- `wiba_projekte` (inkl. logischer `firmen_id`-Referenz, #1071, und `meta_json`)
- `wiba_antworten` (Antwort je Prüffrage: `status`, `notiz`, `verantwortlich`,
  `zieldatum`, `evidence_doc_ids`)
- `wiba_themen` (Katalog: Themen/Bausteine aus den BSI-Checklisten)
- `wiba_prueffragen` (Katalog: Prüffragen je Thema aus dem WiBA-Tool)
- `wiba_catalog_meta` (Katalog-Version/Quelle, updatefähig per Admin-Download)

Der Prüffragen-Katalog ist **DB-gestützt** (nicht im Code hinterlegt), damit
BSI-Updates per Admin-Download eingespielt werden können.

## Katalog-Update (Admin)

> **Wichtig: Die BSI-Quelldateien werden nicht mitgeliefert.** Aus urheberrechtlichen
> Gründen (Copyright BSI) lädt das Modul die WiBA-Originaldateien zur Laufzeit von
> der BSI-Website herunter und importiert sie in den lokalen Katalog. Sie werden
> nicht ins Repository eingecheckt.

Der Katalog wird vom Administrator über das WiBA-Modul gepflegt (Permission
`WIBA_CATALOG`). Zwei BSI-Quellen werden verarbeitet:

| Quelle | Datei | Inhalt |
|--------|-------|--------|
| WiBA-Tool | `WiBA_Tool.xlsx` (Sheet „Dokumentation WiBA") | Prüffragen je Thema (Nr, Frage, Hilfsmittel, Aufwand) |
| Checklisten | `WiBA_Checklisten.zip` (je Thema eine DOCX) | Themen-Metadaten (Bausteine, Ziel, Hinweis, weiterführende Links) |

### Ablauf

1. **Herunterladen**: Das Modul lädt die aktuellen BSI-Quelldateien in ein lokales
   Datenverzeichnis. Schlägt ein Download fehl, gibt der Statusreport an, welche
   Datei betroffen ist.
2. **Importieren**: Die Quelldateien werden geparst und der Katalog
   (`wiba_themen` + `wiba_prueffragen`) **vollständig ersetzt** (idempotenter
   Re-Import). Die Antworten der Projekte (`wiba_antworten`) bleiben dabei erhalten.
3. **Aktualisieren**: Download und Import können in einem Schritt ausgeführt werden
   („Refresh"); so lässt sich der Katalog bei einer neuen BSI-Version updaten.

Die Katalog-Version (z. B. *„WiBA 2.0 (2023)"*), die Quelle sowie die Anzahl der
Themen/Prüffragen und der Import-Zeitpunkt werden in `wiba_catalog_meta` gespeichert
und im Modul angezeigt.

### REST-Endpoints (`server/api/wiba`)

| Methode & Pfad | Zweck | Permission |
|----------------|-------|------------|
| `GET /api/wiba/catalog` | Katalog (Themen + Prüffragen) + Meta | `WIBA_READ` |
| `GET /api/wiba/catalog/status` | Katalog-Version/Anzahl/Import-Zeitpunkt | `WIBA_READ` |
| `POST /api/wiba/catalog/download` | BSI-Quelldateien herunterladen (`502` bei Download-Fehler) | `WIBA_CATALOG` |
| `POST /api/wiba/catalog/ingest` | heruntergeladene Quellen importieren | `WIBA_CATALOG` |
| `POST /api/wiba/catalog/refresh` | Download + Import in einem Schritt | `WIBA_CATALOG` |

## Workflow

1. **Projekt anlegen**: WiBA-Projekt mit Name, Organisation/Unternehmen,
   Beschreibung und Berater anlegen.
2. **Firma zuordnen**: Über das Feld *Unternehmen* wird das Projekt einer Firma aus
   der [Firmenverwaltung](firmen.md) zugeordnet. Die logische `firmen_id` wird per
   Name-Match nachgezogen (#1071) und bildet die Grundlage für Nachweis-Vorschläge
   und das Risiko-Cockpit.
3. **Prüffragen beantworten**: Die Prüffragen sind nach Themen gruppiert. Jede Frage
   wird mit einem Status bewertet:

    | Status | Bedeutung | Reifegrad-Beitrag |
    |--------|-----------|-------------------|
    | `offen` | noch nicht bewertet | 0 % (zählt zum Scope) |
    | `ja` | umgesetzt | 100 % |
    | `nein` | offen / nicht umgesetzt | 0 % |
    | `nicht_relevant` | außerhalb des Scopes | — (nicht im Nenner) |

    Zu jeder Antwort können Notiz, Verantwortlicher, Zieldatum und Evidenz-Verweise
    erfasst werden.

4. **Reifegrad**: Das Modul berechnet den Reifegrad in Prozent — gesamt und je
   Thema. `nicht_relevant`-Fragen werden aus dem Nenner ausgeklammert; `offen` und
   `nein` zählen mit 0 %. So zeigt der Reifegrad den realen Umsetzungsstand der
   in-Scope-Prüffragen.

### REST-Endpoints (Auszug)

| Methode & Pfad | Zweck |
|----------------|-------|
| `GET\|POST /api/wiba/projekte` | Projekte auflisten / anlegen |
| `GET\|PUT\|DELETE /api/wiba/projekte/<p>` | Projekt lesen / ändern / löschen |
| `GET /api/wiba/projekte/<p>/controls` | Prüffragen + Antworten + Reifegrad |
| `POST /api/wiba/projekte/<p>/antworten` | Antwort einer Prüffrage speichern |

## KI-Assistent (Copy/Paste)

WiBA folgt dem suite-typischen **Copy/Paste-KI-Workflow** (keine direkte API): Das
Modul erzeugt je Prüffrage einen Prompt, den Sie in ChatGPT o. ä. einfügen; die
JSON-Antwort fügen Sie zurück ein, und das Modul übernimmt Status, Notiz und
Empfehlung.

- Der Prompt enthält die **Prüffrage**, das **Hilfsmittel** sowie den
  **Thema-/Baustein-Kontext** (Bausteine, Ziel, Hinweis) aus dem Katalog.
- Optional werden die bei der **Firma hinterlegten Nachweise** (Evidence Library)
  als Volltext mitgegeben (#1123), damit die KI auf Basis der vorhandenen
  Dokumentation prüffähig antworten kann. Liegen keine Nachweise vor, antwortet die
  KI konservativ und fordert fehlende Nachweise an.
- Das erwartete Antwortformat ist ein JSON-Objekt mit `status`
  (`ja`/`nein`/`nicht_relevant`), `notiz` (prüffähige Begründung) und `empfehlung`
  (bei *Nein*: konkrete nächste Maßnahme).

REST-Endpoints (`server/api/wiba`):

| Methode & Pfad | Zweck |
|----------------|-------|
| `POST /api/wiba/projekte/<p>/controls/<control_id>/prompt` | Prompt erzeugen (`include_evidence`-Flag steuert die Nachweis-Einbindung) |
| `POST /api/wiba/projekte/<p>/controls/<control_id>/parse-response` | JSON-Antwort der KI parsen |

## Verknüpfungen

### DSGVO-TOM als Nachweis-Vorschlag

Sind für die zugeordnete Firma technische und organisatorische Maßnahmen im
[DSGVO-Modul](dsgvo.md) (TOM-Katalog, Art. 32 / SDM) dokumentiert, schlägt WiBA
diese als mögliche Nachweise vor. Berücksichtigt werden umgesetzte Maßnahmen
(Status > 0) inkl. Soll/Ist und Wirksamkeitsergebnis. So lassen sich bereits
geführte Datenschutz-Maßnahmen direkt als WiBA-Belege wiederverwenden.

- Endpoint: `GET /api/wiba/projekte/<p>/tom-evidence`
- Firmen-Dokumente der Evidence Library: `GET /api/wiba/projekte/<p>/firmen-evidence`

### „Nein"-Befunde als Risiken in die Risikobewertung

Offene Punkte der Basis-Absicherung (Prüffragen mit Status *Nein*) lassen sich per
Knopfdruck als **Risiko** in die [Risikobewertung](risikobewertung.md) übernehmen.

- Beim ersten Befund wird automatisch ein verknüpftes Risikobewertungs-Projekt
  („WiBA-Befunde: &lt;Projekt&gt;") angelegt und im WiBA-Projekt unter
  `meta.linked_risk_projekt` vermerkt.
- Das Risiko wird mit dem Framework des RB-Projekts (Standard STRIDE) bewertet;
  Name und Beschreibung werden aus Prüffrage, Thema und Baustein vorbefüllt.

REST-Endpoints:

| Methode & Pfad | Zweck |
|----------------|-------|
| `POST /api/wiba/projekte/<p>/controls/<control_id>/risk` | „Nein"-Befund als Risiko übernehmen |
| `GET /api/wiba/projekte/<p>/risiken` | Risiken des verknüpften RB-Projekts |

### Risiko-Cockpit

Da die WiBA-Befunde als Risiken in die Risikobewertung fließen und das Projekt
einer Firma zugeordnet ist, erscheinen sie modulübergreifend im
**[Risiko-Cockpit](risikobewertung.md)** (read-only Aggregation aller offenen
Risiken pro Firma, #1078/#1079).

## Issue-Tracking (GitHub/GitLab)

Jede Prüffrage kann als **GitHub-/GitLab-Issue** erzeugt und überwacht werden
(Object-Kind `wiba_control` in `shared/issue_links`) — analog zu CRA-Anforderungen.

- **Repo konfigurieren**: pro Projekt wird das Ziel-Repo/-Projekt hinterlegt.
- **Issue erstellen**: pro Prüffrage öffnet/erstellt das Modul ein Issue im
  verknüpften Repo.
- **Sync**: der aktuelle Issue-Status wird vom Provider abgeholt und angezeigt.

REST-Endpoints (`server/api/wiba`):

| Methode & Pfad | Zweck |
|----------------|-------|
| `GET\|PUT /api/wiba/projekte/<p>/repo-config` | Ziel-Repo/-Projekt lesen/setzen |
| `GET\|POST /api/wiba/projekte/<p>/controls/<control_id>/issues` | Issues lesen / erstellen |
| `POST /api/wiba/projekte/<p>/controls/<control_id>/issues/sync` | Issue-Status synchronisieren |
| `DELETE /api/wiba/projekte/<p>/controls/<control_id>/issues/<link_id>` | Verknüpfung lösen |

## Nachweis-Report (DOCX/PDF)

Aus dem WiBA-Projekt lässt sich ein **Nachweis-Report** mit Reifegrad-Übersicht,
Antworten je Thema und offenen Punkten erzeugen. Der Export läuft über die
zentrale, Admin-verwaltete [Word-Vorlagen-Engine](../index.md) (DOCX und PDF;
PDF via Gotenberg) und erfordert die Permission `WIBA_EXPORT`. Der Report dient als
prüffähiger Beleg für einen sicheren IT-Betrieb gegenüber Dritten (z. B. Kunden,
Aufsicht, Versicherung).

## Berechtigungen

| Permission | Zweck |
|------------|-------|
| `WIBA_READ` | Projekte, Katalog und Antworten lesen |
| `WIBA_WRITE` | Projekte/Antworten pflegen, Issues, Risiko-Übernahme |
| `WIBA_EXPORT` | Nachweis-Report exportieren |
| `WIBA_CATALOG` | BSI-Quellen herunterladen/importieren (Admin) |

## Weiterführende Links

- [BSI – Weg in die Basis-Absicherung (WiBA)](https://www.bsi.bund.de/dok/wiba)
- [BSI IT-Grundschutz](https://www.bsi.bund.de/grundschutz)
- [DSGVO-Modul](dsgvo.md)
- [Risikobewertungs-Modul](risikobewertung.md)
- [Firmenverwaltung](firmen.md)
</content>
</invoke>
