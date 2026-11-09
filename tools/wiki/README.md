# Benutzer-Wiki — Build-Pipeline (Sprint #37, #1424)

Reproduzierbare Erzeugung des Anwender-Wikis (BookStack, OSS/MIT) für alle Module
**außer Gutachten**, mit Screenshots aus der Demo-Umgebung.

## Komponenten
- `docker-compose.bookstack.yml` — BookStack + MariaDB (deployt auf **docker02**, Port **6875**).
  Live: http://aics.example.com:6875 — Shelf „AI Compliance Suite — Benutzerhandbuch".
- `shoot.mjs` — Playwright/Firefox: Login (Token aus `.demo_user`) + Landing-Screenshots aller Module.
- `detail.mjs` — öffnet je Modul das erste Projekt + klickt Tabs → Detail-/Dashboard-Screenshots.
- `content.mjs` — Inhaltsmodell (Bücher/Seiten als Markdown; `{{img:datei.png}}`-Tokens).
- `publish.mjs` — legt Shelf/Bücher/Seiten via BookStack-REST-API an, lädt Screenshots hoch
  und ersetzt die Tokens durch eingebettete Bilder. Idempotent (Update per Seitenname).

## Voraussetzungen (lokal, einmalig)
```
npm install playwright && npx playwright install firefox
```
Secrets (NICHT eingecheckt), im Arbeitsverzeichnis der Skripte:
- `.demo_user`  →  `doku@aics.local / <passwort>` (Demo-User, per `docker exec aicsdemo_web` angelegt)
- `.bs_token`   →  `<token_id>:<secret>` (BookStack-API-Token; via `artisan tinker` erzeugt,
  abgelegt im Container unter `/config/aics_api_token.txt`)

## Ablauf
```
node shoot.mjs        # Landing-Screenshots -> ./shots/
node detail.mjs       # Detail-/Tab-Screenshots -> ./shots/
node publish.mjs      # nach BookStack publizieren (Bilder-Upload + Markdown)
```

## CRA-Konformität
Das Wiki deckt die CRA **Annex-II**-Nutzerinformationen ab (Mapping-Seite im Buch „2 · CRA").
Siehe Issues #852 / #1424.

## Tiefen-Doku (v2, hilfe-basiert)
- `tabs.mjs` — autoritative Tab-Liste je Modul (id+Label).
- `captureall.mjs` / `riskshot.mjs` — Screenshot je Tab/Funktion (Projekt öffnen → jede Gruppe+Tab) → `shots2/`.
- `content2.mjs` — Fallback-Beschreibungen + Buch-/Titel-Mapping.
- `gen.mts` — **Hauptgenerator**: erzeugt Modul-Bücher aus der echten In-App-Hilfe (`frontend/src/help/*.ts`: Zweck/Rechtsgrundlage/Anleitung/Tipps) + Screenshots, plus das Buch „Einstellungen & Administration". Lauf: `cp -r ../../frontend/src/help ./help && npx tsx gen.mts`.
- Wiki ist auf **Deutsch** (`APP_LANG=de`) und im **Suite-Design** (Logo `logo_header.png`, Primärfarbe `#1565c0`) gebrandet (BookStack-Settings via `artisan tinker`).

## Stand 2026-10-25 — Erfassung statt Pflege

Das Wiki stand zuletzt auf dem Stand von Juni 2026, während die Anwendung bei
v8.0.11 war; **Compliance-Audit** und **Firmen** fehlten ganz. Ursache war die
handgepflegte `tabs.mjs`: Eine Liste, die jemand nachtragen muss, veraltet.

Deshalb jetzt:

```
node erfassen.mjs      # Tabs UND Screenshots live aus der Anwendung
                       #   -> shots/, shots2/, tabs.generiert.json
cp -r ../../frontend/src/help ./help
npx tsx gen.mts        # Bücher erzeugen und nach BookStack publizieren
```

`erfassen.mjs` liest, was wirklich da ist — inklusive der drei Tab-Varianten im
Haus: `GroupedModuleNav` (`nav-tab`), `TabBar` (`tab-btn`, z. B.
Risikobewertung und Compliance-Audit) und die eigene Leiste der
Firmenverwaltung (`main-tab`). `gen.mts` bevorzugt `tabs.generiert.json` und
fällt auf `tabs.mjs` zurück.

ENV: `AICS_BASE` (Default Demo-Instanz), `AICS_EMAIL`, `AICS_PASSWORD`,
`AICS_MODULE` (Komma-Liste für einen Teillauf), `WIKI_BASE`.

### CRA-Prozessseiten

`cra_prozess.mjs` enthält drei Seiten, die dem CRA-Buch vorangestellt werden
(A1–A3): der Weg in zwei Phasen, „Produkt CRA-ready machen" (9 Schritte) und
„Ein Release veröffentlichen" (7 Schritte). Sie beantworten die Frage, mit der
ein Anwender kommt — *wie werde ich fertig?* —, die eine Tab-für-Tab-Liste
nicht beantwortet. Inhaltlich gegen `cra/release_checkliste.py` und
`cra/release_db.cra_ready_feststellen` geprüft.

**Beim Aufräumen von Dialogen niemals „OK" klicken** — in einem
Bestätigungsdialog ist das die Zustimmung, nicht das Schließen. Im E2E-Lauf vom
25.10. hat genau das fünf SBOM-Einträge gelöscht.

## Handbuch-PDF (`handbuch.py`)

Setzt die Bücher des Wikis zu **einem** PDF zusammen — Deckblatt,
Inhaltsverzeichnis, Kopf-/Fußzeile, A4. Die Screenshots kommen mit, weil
BookStacks HTML-Export sie als `data:`-URI einbettet.

```bash
python3 tools/wiki/handbuch.py tools/wiki/.bs_token \
  ~/Downloads/AI-Compliance-Suite-Handbuch-8.0.11.pdf 8.0.11 "25. Oktober 2026"
```

Braucht `weasyprint` (`pip install weasyprint`). Die Reihenfolge folgt der
**Nummer im Buchtitel**, nicht der Datenbank-ID: Die Bücher sind zu
verschiedenen Zeiten entstanden, und `0 · Installation` hat die höchste ID.

Das Wiki bleibt die Quelle. Das PDF ist die Fassung für Druck und Weitergabe —
bei Abweichungen gilt das Wiki, und genau das steht auch im Dokument.
