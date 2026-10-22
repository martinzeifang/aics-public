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
