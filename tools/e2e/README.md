# E2E-Smoke-Test (Firefox / Playwright)

Wiederholbarer Funktionstest **über einen echten Firefox**. Konsolidiert den
exhaustiven manuellen Funktionstest vom 2026-06-22 in einen reproduzierbaren Lauf.

## Was wird getestet

1. **Login** über die UI
2. **Navigation** aller Modul-Routen (`/firmen`, `/risikobewertung`, `/cra`, `/wiba`,
   `/dsgvo`, `/nis2`, `/aiact`, `/soc`) + Admin-Routen
3. **Alle Tab-Gruppen + Untertabs** je Modul (erstes Projekt vorausgewählt)
4. **Fehler-Capture**: Console-Errors/-Warnings, `pageerror`, HTTP ≥ 400
5. **Bericht-DOCX-Erzeugung** je Modul aus dem Seiten-Kontext (echtes `fetch` mit
   dem App-Token — läuft also über die Browser-Session)

Ergebnis als JSON unter `out/smoke-report.json`. Exit-Code:
`0` sauber · `1` fatale Funde (Errors/5xx/Report-Fehler) · `2` Setup-Fehler.
Console-*Warnings* sind per Default nicht fatal (`--strict` macht sie fatal).

## Voraussetzungen

Die Suite muss laufen (Dev-Stack oder Deploy). Lokaler Dev-Stack:

```bash
python run_dev.py            # Backend https://127.0.0.1:5000
# + Vite-Frontend https://127.0.0.1:5173
```

## Lauf

```bash
cd tools/e2e
npm install                  # zieht Playwright + Firefox (einmalig)
npm run smoke                # gegen https://127.0.0.1:5173

# oder gegen eine andere Instanz:
AICS_BASE=https://aics.example.com:8445 \
AICS_EMAIL=admin@example.com AICS_PASSWORD=… \
npm run smoke
```

## Konfiguration (ENV)

| Variable        | Default                     | Zweck                         |
|-----------------|-----------------------------|-------------------------------|
| `AICS_BASE`     | `https://127.0.0.1:5173`    | Frontend-URL                  |
| `AICS_EMAIL`    | `admin@example.com`         | Login                         |
| `AICS_PASSWORD` | `admin-password`            | Login                         |
| `AICS_HEADED=1` | (headless)                  | Browser sichtbar              |
| `AICS_SHOTS=1`  | (aus)                       | Screenshot je Tab → `out/shots/` |

## Hinweise

- Der Test ist **lesend/erzeugend** und mutiert keine Daten (klickt keine
  Speichern-/Löschen-/Sync-Aktionen). Bericht-Erzeugung schreibt keine Projektdaten.
- DORA ist bewusst nicht enthalten (Modul entfernt, #1500).
- Bei Bedarf `out/shots/` für eine visuelle Sichtung mit `AICS_SHOTS=1` erzeugen.
