# E2E-Smoke-Test (Firefox / Playwright)

Wiederholbarer Funktionstest **über einen echten Firefox**. Konsolidiert den
exhaustiven manuellen Funktionstest vom 2026-06-22 in einen reproduzierbaren Lauf.

## Was wird getestet

1. **Login** über die UI
2. **Navigation** aller Modul-Routen (`/firmen`, `/risikobewertung`, `/cra`, `/wiba`,
   `/dsgvo`, `/nis2`, `/aiact`) + Admin-Routen
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

## Vollumfänglicher CRA-Durchlauf (`cra_vollumfang.mjs`)

```bash
npm run cra          # gegen https://localhost:5173
AICS_PROJEKT="CRA Produkt Alpha" npm run cra
```

`smoke.mjs` navigiert Routen und Tabs — er findet, was beim **Anzeigen** bricht.
Die Fehler, die im CRA-Modul wehtun, entstehen beim **Arbeiten**: ein Feld ohne
Eingabestelle (#1796), ein Knopf, der nur bei leerem Projekt erscheint (#1797),
ein zweites Artefakt, das beim Übernehmen wegfällt (#1798). Darum zwei Phasen:

1. **Jeder Tab, jeder `<details>`-Abschnitt, jeder lesende Knopf** — gesammelt
   werden Console-Errors, `pageerror` und HTTP ≥ 400.
2. **Schreibstrecken je Register** — anlegen, speichern, neu laden und prüfen,
   dass der Wert noch da ist. Ein Speichern, das 200 liefert und den Wert
   verliert, sieht sonst wie Erfolg aus.

Drei Dinge, die der Durchlauf über das Modul gelernt hat und die man kennen muss,
wenn man ihn erweitert:

* **`/cra?tab=…` taugt nicht zur Navigation.** Die Projektauswahl steht im Store,
  nicht in der URL — ein `goto` landet auf „Projekt wählen". Geklickt wird über
  die **zweistufige** Tab-Leiste (Gruppe, dann Untertab).
* **Nur innerhalb `.tab-content` klicken.** Der erste Durchlauf traf die
  Modulnavigation und testete fröhlich im SOC-Portal weiter.
* **Schreibende Knöpfe nicht blind klicken.** Ein leeres Formular abzuschicken
  erzeugt ein berechtigtes HTTP 400 — Rauschen, in dem echte Funde untergehen.
  Diese Strecken laufen in Phase B mit echten Werten.

Wiederholbarkeit ist Teil des Tests: #1800 (zweites Erfassen derselben SBOM →
HTTP 500) fiel erst im **zweiten** Lauf auf, weil die Zeile beim ersten neu war.

## Vollprüfung und Logikprüfung (25.10.2026)

Zwei weitere Läufe, aus denen die Funde #1808–#1817 stammen. Sie ergänzen den
Smoke-Test, sie ersetzen ihn nicht: Der Smoke-Test fragt „kommt jede Seite
hoch?", diese beiden fragen „tut jeder Knopf, was er verspricht?".

```bash
node tools/e2e/vollpruefung.mjs     # jeden Tab, jeden Knopf, jeden Link
node tools/e2e/logikpruefung.mjs    # die Rechenwege und Zustandsübergänge
```

Beide erwarten `AICS_BASE`, `AICS_EMAIL`, `AICS_PASSWORD` und legen
Screenshots unter `tools/e2e/screens/<datum>/` ab.

**Zwei Lehren aus dem Lauf, die im Skript stehen:**

- **„OK" gehört nicht in den Aufräum-Filter.** Ein Durchlauf, der am Ende alle
  Dialoge wegklickt, hat beim Treffer auf „OK" fünf SBOM-Einträge gelöscht.
  Icon-Knöpfe (🗑) sind ausgeschlossen, Bestätigungen werden nicht geklickt.
- **Tag-Enden zeichenweise suchen, nicht per `[^>]*`.** Arrow-Funktionen in
  Vue-Attributen enthalten `>`; die naive Regex meldete 25 Fehlalarme.

Von 33 Meldungen des Durchlaufs blieben nach Nachprüfung **vier echte Funde**.
Das ist der Normalfall: Ein Testskript, das die Anwendung nicht kennt, meldet
vor allem seine eigenen Erwartungsfehler. Jeder Fund gehört einzeln am
laufenden System belegt, bevor er ein Issue wird.
