# BISG-Sachverständigengutachten — Modul-Doku

> Modul `gutachten/gerichts*` — gerichtsfeste Sachverständigengutachten und
> Privatgutachten nach BISG/DIN EN 16775/ISO/IEC 27037/25010/ZPO.

## Inhalt

- [Übersicht](#übersicht)
- [Quickstart](#quickstart)
- [Datenmodell](#datenmodell)
- [Workflow](#workflow)
- [REST-API](#rest-api)
- [DOCX-Pflicht-Gliederung](#docx-pflicht-gliederung)
- [Privatgutachten-Variante](#privatgutachten-variante)
- [Methodische Schutzschilde](#methodische-schutzschilde)
- [Frontend (Web + Desktop)](#frontend)
- [Demo-Daten](#demo-daten)

---

## Übersicht

Das Gutachten-Modul der AI Compliance Suite kennt **zwei klar getrennte
Generator-Varianten**:

| Variante | Zweck | DB-Tabellen-Präfix | DOCX-Titel |
|---|---|---|---|
| **Audit-Bericht** | Compliance-Reifegrad-Bericht (Frameworks) | `gutachten_*` | „Compliance-Audit-Bericht" |
| **Gerichtsgutachten (BISG)** | Sachverständigengutachten (gerichtsbestellt) | `gerichts*` | „SACHVERSTÄNDIGENGUTACHTEN" |
| **Privatgutachten (BISG)** | Mandanten-Auftrag (kein Gericht) | `gerichts*` mit `gutachten_art='privat'` | „PRIVATGUTACHTEN" |

**Rote Linie:** Die Output-DOCX dürfen NICHT vermischt werden (andere Adressaten,
andere Pflichten). Geteilt sind nur Infrastruktur-Module (Normen-Library,
Linter, Werkzeug-Register, Honorar-Tracker, Befangenheits-Schutz).

---

## Quickstart

### Lokaler Dev-Server starten

```bash
./start-dev.sh   # startet Backend (https://localhost:5000) + Frontend (https://localhost:5173)
# Login: admin@example.com / admin-password
```

### Demo-Daten erzeugen

```bash
python3 scripts/seed_gerichtsgutachten_demo.py
# erzeugt 'GG-2026-DEMO' (Gerichtsgutachten) + 'PG-2026-DEMO' (Privatgutachten)
```

### Web-UI öffnen

1. https://localhost:5173 (oder https://aics.example.com:8443 für Production)
2. Sidebar → **Gutachten**
3. Switcher → **⚖ Gerichtsgutachten (BISG)**
4. Verfahren wählen oder „+ Neues Gerichtsgutachten" anlegen
5. Toggle: **⚖ Gerichtsgutachten** vs. **📋 Privatgutachten**
6. Editor: 9 Tabs (Deckblatt, Selbstcheck, Beweisfragen, Befunde, Beurteilungen,
   Asservaten, Verfahren, Honorar, Validator)
7. **📄 DOCX** exportieren

### Desktop-Tk

```bash
python3 -m ai_compliance_suite
# Modul „Gutachten" → Navigation „⚖ Gerichtsgutachten (BISG)"
```

---

## Datenmodell

```
gerichtsgutachten                    (Stammdaten — gutachten_art = gericht|privat)
├── gerichtsgutachten_beweisfragen   (II — n Beweisfragen)
├── gerichtsgutachten_befunde        (IV — Tatsachen)
├── gerichtsgutachten_beurteilungen  (V — Soll/Ist/Kausalität, Norm-Ref)
├── gerichtsgutachten_assets         (Asservaten mit SHA-256, ISO/IEC 27037 CoC)
├── gerichtsgutachten_verfahrensereignisse  (III — Timeline)
├── gerichtsgutachten_macb           (G4-3 — Modified/Accessed/Changed/Born)
├── gerichtsgutachten_hypothesen     (G6-1 — Hypothesen-Tree pro Beurteilung)
├── gerichtsgutachten_peer_review    (G5-2)
├── gerichtsgutachten_aufbewahrung   (G5-5 — 10-Jahre-Reminder)
├── gerichtsgutachten_ki_akzeptanz   (G3-4 — § 407a-Log)
├── gerichtsgutachten_werkzeug_verwendung (Verknüpfung zum Werkzeug-Register)
└── gerichtsgutachten_norm_subscriptions  (Living-Norms-Watcher)

Geteilt SV-weit:
├── gutachten_werkzeuge_register     (G0-3 — Tool + Version + Zweck)
├── gutachten_zeitbuch               (G0-4 — Honorar/Auslagen)
├── gutachten_norm_versions          (G0-5 — Versions-Tracker)
├── gutachten_norm_notifications     (G0-5 — Notifications)
└── gutachten_befangenheits_log      (G0-9)
```

---

## Workflow

**Reihenfolge nach BISG 5-Phasen-Modell:**

1. **G2-1 Selbstcheck** — vor Annahme: 5 Fragen + DB-Vorbefassungs-Check
   (G0-9, mit Self-Exclude via #654)
2. **Stammdaten** — Deckblatt-Felder ausfüllen (Pflicht-Validator je nach Art)
3. **II. Beweisfragen** — wörtlich vom Gericht (Gerichtsgutachten) oder
   Auftraggeber (Privatgutachten)
4. **III. Verfahrensgang** — symmetrische Parteikommunikation protokollieren
   (G3-2 Symmetrie-Check)
5. **Asservaten** — Upload, SHA-256 wird live berechnet, ggz. von Parteien
6. **IV. Befunderhebung** — Tatsachen-only-Editor mit Live-Linter
   (G3-1 Jura-Sperre, blockt nicht, warnt nur)
7. **V. Beurteilung** — Soll/Ist/Kausalität/Würdigung; Norm-Picker aus G0-1;
   KI-Vorschlag möglich (mit § 407a-Disclaimer + Akzeptanz-Log G3-4)
8. **Hypothesen-Tree** (G6-1) — alternative Erklärungen sammeln + verwerfen
9. **VI. Antworten** — Beweisfragen mit Beurteilungs-Verweisen
10. **G5-1 Validator** — Pflichtfelder + Sprach-Linter + Cross-Ref-Linter (G6-6)
11. **G5-2 Peer-Review** — zweiter SV kann annotieren
12. **G5-3 DOCX + PDF** — mit QES-Hinweis nach § 130a ZPO
13. **G5-5 Archiv-ZIP** — 10-Jahres-Aufbewahrung mit Hash-Manifest

---

## REST-API

Alle Endpoints unter `/api/gutachten/gerichts/*`, JWT-geschützt.

**Projekt-CRUD:**
- `GET /gerichts` — alle Verfahren
- `POST /gerichts` — neues Verfahren (Body: gutachten_art + Felder)
- `GET /gerichts/{name}` · `PUT /gerichts/{name}` · `DELETE /gerichts/{name}`

**Editor:**
- `GET/POST /gerichts/{name}/beweisfragen`
- `GET/POST /gerichts/{name}/befunde`
- `GET/POST /gerichts/{name}/beurteilungen`
- `GET/POST /gerichts/{name}/assets`
- `GET/POST /gerichts/{name}/verfahren`
- `POST /gerichts/sha256` (multipart file → SHA-256)

**Wizards:**
- `GET /gerichts/wizards/selbstcheck-fragen`
- `POST /gerichts/{name}/wizards/selbstcheck`
- `POST /gerichts/wizards/befund-validate`
- `POST /gerichts/{name}/wizards/beurteilung/prompt` + `/parse`
- `GET /gerichts/{name}/wizards/schluss-validator`

**Forensik:**
- `GET /gerichts/{name}/macb` · `POST` · `DELETE /gerichts/macb/{id}`
- `GET /gerichts/volatility-checklist`
- `GET /gerichts/{name}/werkzeug-validator`
- `POST /gerichts/log-classify`
- `GET /gerichts/assets/{id}/sicherungsprotokoll.pdf`

**Qualität:**
- `GET /gerichts/{name}/symmetrie-check`
- `GET /gerichts/{name}/cross-ref-check`
- `POST /gerichts/befunde/{bid}/non-liquet` · `/gerichts/beurteilungen/{uid}/non-liquet`
- `POST /gerichts/{name}/peer-review/request` · `/peer-review/{id}/kommentar` · `/close`
- `POST /gerichts/{name}/aufbewahrung` · `GET`
- `GET /gerichts/{name}/docx` · `/pdf` · `/pdf/sha256` · `/archiv.zip` · `/rechnung.pdf`

**Schutzschilde:**
- `POST /befangenheits-check` (Kunde/System/Parteien → Treffer)
- `POST /lint` (kontext=audit|gerichts, kind=sprache|cross_ref|anonym)
- `POST /gerichts/{name}/ki-akzeptanz`

**G6:**
- `GET/POST /gerichts/hypothesen` · `PUT/DELETE /gerichts/hypothesen/{id}`
- `POST /gerichts/befunde/{bid}/drittgutachter/prompt`
- `GET /gerichts/{name}/anonymized`

---

## DOCX-Pflicht-Gliederung

```
[STRENG VERTRAULICH]
SACHVERSTÄNDIGENGUTACHTEN (oder PRIVATGUTACHTEN)

Deckblatt:
  Verfahren (Gericht/Kammer/AZ/Beweisbeschluss) ODER Auftrag (Auftraggeber/...)
  Parteien (Kläger/Beklagter mit Anwälten) — nur Gericht
  Sachverständiger (Name/Zertifizierung/Anschrift/Kontakt)
  Datum

Inhaltsverzeichnis

II. Untersuchungsauftrag           — Beweisfragen wörtlich
III. Verfahrensgang                — Timeline + Empfänger-Markierung
IV. Befunderhebung                 — Tatsachen + Methode + Werkzeug + Non-liquet
V. Technische Beurteilung          — Norm-Ref/Soll/Ist/Kausalität/Würdigung
VI. Beantwortung der Beweisfragen  — kurz + Verweis zu V
VII. Schlussformel                 — Eigenversicherung + § 407a-Hinweis
VIII. Anhang                       — Asservatentabelle mit SHA-256

Footer: AZ + Erstellungsdatum
```

---

## Privatgutachten-Variante

Bei `gutachten_art = 'privat'`:

- **Pflicht:** `name`, `sv_name`, `auftraggeber`, `auftrags_art`
- **Optional:** `auftrags_datum`, `auftrags_nummer`, `honorarvereinbarung`
- **Leer:** `gericht`, `aktenzeichen`, `klaeger_*`, `beklagter_*`, `beweisbeschluss_datum`
- **DOCX-Deckblatt:** zeigt „Auftrag"-Block (Auftraggeber, Auftrags-Art, etc.)
  statt „Verfahren"+„Parteien"

**Workflow ist identisch** zum Gerichtsgutachten — gleiche Tabs, gleiche Wizards,
gleiche Linter. Validator wählt automatisch die richtige Pflichtfeld-Liste.

---

## Methodische Schutzschilde

| ID | Schutz | Wo aktiv |
|---|---|---|
| G3-1 | Jura-Sperre-Linter (gelb-Markierung „mangelhaft im Rechtssinne" etc.) | Befund-Editor (live), Schluss-Validator |
| G3-2 | Symmetrie-Check (jede Parteikommunikation muss Kläger UND Beklagter haben) | Verfahren-Tab |
| G3-3 | Non-liquet-Marker (sachlich „nicht abschließend feststellbar") | Befund + Beurteilung |
| G3-4 | § 407a-KI-Disclaimer + Akzeptanz-Log | Beurteilungs-Wizard |
| G0-9 | Befangenheits-Warnung beim Anlegen (Vorbefassung-Check via Audit-DB) | Anlegen-Dialog (#654 Self-Exclude) |
| G6-5 | Sprach-Linter (Slogans + AI-Phrasen) | Befund + Beurteilung |
| G6-6 | Cross-Reference-Linter (Befund↔Beurteilung↔Beweisfrage) | Hypothesen-Tab |
| G6-7 | Anonymisierungs-Tool (PII + Firmennamen) | Peer-Review-Tab |

---

## Frontend

### Web (Vue 3)

- Store: `frontend/src/stores/gerichtsgutachten.ts`
- View: `frontend/src/views/gutachten/GerichtsgutachtenView.vue`
- Sidebar-Switcher: `frontend/src/components/sidebars/GutachtenSidebar.vue`
- Route: `/gutachten/gerichts`

### Desktop (Tkinter)

- Panel: `gutachten/_panel_gerichts.py` (`GerichtsgutachtenPanel`)
- Integration: `gutachten/gui_module.py` Navigation-Eintrag
  „⚖ Gerichtsgutachten (BISG)"
- 5 Editor-Tabs: Stammdaten + II/IV/V + Asservaten
- Lokale SHA-256-Berechnung via `hashlib`

---

## Demo-Daten

```bash
python3 scripts/seed_gerichtsgutachten_demo.py
# --db DATA/db/gutachten.sqlite (default)
# --only gericht|privat|alle
```

Erzeugt zwei vollständige Beispiele basierend auf der BISG-Übungsaufgabe:

1. **GG-2026-DEMO** — Gerichtsgutachten LG Musterstadt X 0815/26
   (Beta-Core v1.0 ERP-Migration mit fehlendem Exception-Handling)
2. **PG-2026-DEMO** — Privatgutachten ACME GmbH Tauglichkeitsprüfung
   (AcmePortal v2.5 mit OWASP-ASVS-Findings)

Beide Demos sind sofort DOCX-exportierbar (40 KB Gericht / 38 KB Privat).

---

## Referenzen

- BISG-Sachverständigen-Schulung (Tag 1+2)
- DIN EN 16775 — Allgemeine Anforderungen an Sachverständigenleistungen
- ISO/IEC 27037 — Digitale Beweissicherung (Chain of Custody)
- ISO/IEC 25010 — Product Quality Model
- ZPO §§ 406, 407, 407a, 410, 411, 130a
- BGB § 839a — Haftung des gerichtlichen SV
- StGB § 203 — Schweigepflicht
