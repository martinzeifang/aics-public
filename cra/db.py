"""CRA-Modul – SQLite-Datenzugriff."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared import db as _sdb

SCHEMA = """

CREATE TABLE IF NOT EXISTS cra_projekte (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    unternehmen     TEXT NOT NULL DEFAULT '',
    produkt         TEXT NOT NULL DEFAULT '',
    produktklasse   TEXT NOT NULL DEFAULT 'default',
    beschreibung    TEXT NOT NULL DEFAULT '',
    berater         TEXT NOT NULL DEFAULT '',
    meta_json       TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT DEFAULT (aics_now()),
    updated_at      TEXT DEFAULT (aics_now())
);

CREATE TABLE IF NOT EXISTS cra_bewertungen (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    anforderung_id  TEXT NOT NULL,
    bewertung       INTEGER NOT NULL DEFAULT 0,
    kommentar       TEXT NOT NULL DEFAULT '',
    massnahme       TEXT NOT NULL DEFAULT '',
    verantwortlich  TEXT NOT NULL DEFAULT '',
    zieldatum       TEXT NOT NULL DEFAULT '',
    updated_at      TEXT DEFAULT (aics_now()),
    UNIQUE(projekt_name, anforderung_id)
);

CREATE INDEX IF NOT EXISTS idx_cb_projekt ON cra_bewertungen(projekt_name);

CREATE TABLE IF NOT EXISTS cra_anforderungen_custom (
    id              TEXT PRIMARY KEY,
    kapitel         TEXT NOT NULL DEFAULT 'IMPL',
    ref             TEXT NOT NULL DEFAULT '',
    titel           TEXT NOT NULL DEFAULT '',
    beschreibung    TEXT NOT NULL DEFAULT '',
    hinweise        TEXT NOT NULL DEFAULT '',
    gewichtung      INTEGER NOT NULL DEFAULT 1,
    ist_override    INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT DEFAULT (aics_now()),
    updated_at      TEXT DEFAULT (aics_now())
);

CREATE TABLE IF NOT EXISTS cra_dokumente (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    doc_name        TEXT NOT NULL,
    doc_path        TEXT NOT NULL,
    doc_type        TEXT NOT NULL DEFAULT 'resource',
    anforderung_id  TEXT NOT NULL DEFAULT '',   -- #1217: Nachweis↔Anforderung
    owasp_id        TEXT NOT NULL DEFAULT '',   -- #1217: Nachweis↔OWASP-Control
    annex_baustein  TEXT NOT NULL DEFAULT '',   -- #1217: Annex-VII-Bausteinschlüssel
    created_at      TEXT DEFAULT (aics_now())
);

CREATE INDEX IF NOT EXISTS idx_cd_projekt ON cra_dokumente(projekt_name);

-- OWASP Security-by-Design (Proactive Controls) checklist results
CREATE TABLE IF NOT EXISTS cra_owasp_checks (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    owasp_id        TEXT NOT NULL,
    status          INTEGER NOT NULL DEFAULT 0, -- 0..5 (aligned with BEWERTUNG_SKALA)
    kommentar       TEXT NOT NULL DEFAULT '',
    evidence_json   TEXT NOT NULL DEFAULT '[]',
    updated_at      TEXT DEFAULT (aics_now()),
    UNIQUE(projekt_name, owasp_id)
);

CREATE INDEX IF NOT EXISTS idx_coc_projekt ON cra_owasp_checks(projekt_name);

-- ───────────────────────────────────────────────────────────────────
-- Phase A: CRA-Pflicht-Doku-Manager (Issues #472-#476)
-- ───────────────────────────────────────────────────────────────────

-- C1: SBOM-Verzeichnis (pro Projekt + Release)
CREATE TABLE IF NOT EXISTS cra_sbom (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    release_version TEXT NOT NULL,
    sbom_format     TEXT NOT NULL DEFAULT 'spdx',  -- spdx | cyclonedx
    sbom_datum      TEXT NOT NULL DEFAULT (aics_now()),
    komponenten_count INTEGER NOT NULL DEFAULT 0,
    lizenzen_json   TEXT NOT NULL DEFAULT '[]',
    quelle          TEXT NOT NULL DEFAULT '',     -- z.B. "ci-artifact:gh-run-12345" oder "manual"
    blob_path       TEXT NOT NULL DEFAULT '',
    notizen         TEXT NOT NULL DEFAULT '',
    -- #1771: Ein Produkt besteht oft aus mehreren Artefakten (Anwendung,
    -- Webserver, Agent). Jedes bringt seine eigene SBOM mit — im selben
    -- Format und zur selben Release-Version. Ohne dieses Feld kollidierten
    -- sie, und die zweite liess sich nicht speichern.
    artefakt        TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (aics_now()),
    updated_at      TEXT DEFAULT (aics_now()),
    UNIQUE(projekt_name, release_version, sbom_format, artefakt)
);

CREATE INDEX IF NOT EXISTS idx_cra_sbom_projekt ON cra_sbom(projekt_name);

-- C2: PSIRT-Prozess-Doku (1 Eintrag pro Projekt)
CREATE TABLE IF NOT EXISTS cra_psirt (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL UNIQUE,
    intake_kanal    TEXT NOT NULL DEFAULT '',
    triage_sla      TEXT NOT NULL DEFAULT '',     -- z.B. "24h"
    fix_sla_critical TEXT NOT NULL DEFAULT '',    -- z.B. "7 Tage"
    fix_sla_high    TEXT NOT NULL DEFAULT '',
    fix_sla_medium  TEXT NOT NULL DEFAULT '',
    disclosure_policy_url TEXT NOT NULL DEFAULT '',
    security_md_url TEXT NOT NULL DEFAULT '',
    psirt_contacts  TEXT NOT NULL DEFAULT '[]',   -- JSON-Liste
    notizen         TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (aics_now()),
    updated_at      TEXT DEFAULT (aics_now())
);

-- C3: Vulnerability-Handling-Tracker (offene CVEs pro Projekt)
CREATE TABLE IF NOT EXISTS cra_vuln (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    cve_id          TEXT NOT NULL,              -- z.B. CVE-2024-12345
    titel           TEXT NOT NULL DEFAULT '',
    schwere         TEXT NOT NULL DEFAULT 'unknown',  -- low|medium|high|critical|unknown
    cvss_score      REAL NOT NULL DEFAULT 0.0,
    cvss_vector     TEXT NOT NULL DEFAULT '',
    affected_component TEXT NOT NULL DEFAULT '',
    affected_versions  TEXT NOT NULL DEFAULT '',
    fixed_in_version   TEXT NOT NULL DEFAULT '',
    advisory_url    TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'open',  -- open|triaging|fixed|disclosed|wontfix
    triage_kommentar TEXT NOT NULL DEFAULT '',
    source          TEXT NOT NULL DEFAULT 'manual',  -- manual|github_advisory|github_dependabot|gitlab (#937)
    last_synced_at  TEXT,
    -- Art. 13 Abs. 6 (#1761): Meldung an den Hersteller der Fremdkomponente.
    -- Regel, Befund und Prüfpunkt stehen in cra/upstream_meldung.py.
    upstream_status TEXT NOT NULL DEFAULT 'offen',  -- offen|gemeldet|nicht_erforderlich
    upstream_gemeldet_am TEXT,
    upstream_kanal  TEXT NOT NULL DEFAULT '',
    upstream_referenz TEXT NOT NULL DEFAULT '',
    upstream_begruendung TEXT NOT NULL DEFAULT '',
    upstream_von    TEXT NOT NULL DEFAULT '',
    discovered_at   TEXT DEFAULT (aics_now()),
    fixed_at        TEXT,
    disclosed_at    TEXT,
    created_at      TEXT DEFAULT (aics_now()),
    updated_at      TEXT DEFAULT (aics_now()),
    UNIQUE(projekt_name, cve_id)
);

CREATE INDEX IF NOT EXISTS idx_cra_vuln_projekt ON cra_vuln(projekt_name);
CREATE INDEX IF NOT EXISTS idx_cra_vuln_status ON cra_vuln(projekt_name, status);

-- C4: Support-Period-Calculator (1 Eintrag pro Projekt)
CREATE TABLE IF NOT EXISTS cra_support_period (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL UNIQUE,
    markteintritt_datum TEXT,                   -- "Date placed on market"
    support_jahre   INTEGER NOT NULL DEFAULT 5, -- CRA Default: 5 J. (oder erwartete Lebensdauer)
    eol_datum       TEXT,                       -- Berechnet oder manuell
    update_kanal    TEXT NOT NULL DEFAULT '',
    rationale       TEXT NOT NULL DEFAULT '',
    notizen         TEXT NOT NULL DEFAULT '',
    -- Retention-/Update-Verfügbarkeits-Fristen (#1209, Art. 13(9)/(13)/(16))
    update_availability_until TEXT,               -- Art. 13(9): Updates ≥10 J. (berechnet)
    doku_retention_until      TEXT,               -- Art. 13(13): techn. Doku ≥10 J. (berechnet)
    doc_retention_until       TEXT,               -- Art. 13(13): DoC ≥10 J. (berechnet)
    support_end_kaufhinweis_url TEXT NOT NULL DEFAULT '',   -- Art. 13(16): Support-Ende beim Kauf sichtbar
    support_end_kaufhinweis_nachweis TEXT NOT NULL DEFAULT '',
    -- Update-Zusagen (#1762): zwei getrennte Kanäle + die zwei harten Zusagen.
    -- ``update_kanal`` bleibt als Alt-Feld bestehen (ein Kanal, Freitext) und wird
    -- nicht umgeschrieben — Bestandsdaten bleiben lesbar.
    sicherheitsupdate_kanal TEXT NOT NULL DEFAULT '',
    funktionsupdate_kanal   TEXT NOT NULL DEFAULT '',
    sicherheitsupdates_kostenlos INTEGER NOT NULL DEFAULT 0,
    kanaele_getrennt        INTEGER NOT NULL DEFAULT 0,
    update_zusagen_nachweis TEXT NOT NULL DEFAULT '',   -- wo die Zusagen stehen (URL/Dokument)
    created_at      TEXT DEFAULT (aics_now()),
    updated_at      TEXT DEFAULT (aics_now())
);

-- C5: Threat-Model-Doku (1 Eintrag pro Projekt, mit Framework-Wahl)
CREATE TABLE IF NOT EXISTS cra_threatmodel (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL UNIQUE,
    framework       TEXT NOT NULL DEFAULT 'STRIDE',  -- STRIDE|STRIDE-LLM|PASTA|LINDDUN|HEAVENS|OCTAVE|TARA|Finanzinstitute (#938)
    framework_source TEXT NOT NULL DEFAULT 'manual',  -- manual|risk_link|manual_override|legacy (#938)
    scope           TEXT NOT NULL DEFAULT '',
    assets_json     TEXT NOT NULL DEFAULT '[]',
    threats_json    TEXT NOT NULL DEFAULT '[]',
    mitigations_json TEXT NOT NULL DEFAULT '[]',
    diagram_url     TEXT NOT NULL DEFAULT '',
    notizen         TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (aics_now()),
    updated_at      TEXT DEFAULT (aics_now())
);

-- C3 In-App-Sync: letzter Sync-Stand pro Projekt (#947, Story A)
CREATE TABLE IF NOT EXISTS cra_sync_state (
    projekt_name    TEXT PRIMARY KEY,
    last_run_at     TEXT,
    inserted        INTEGER NOT NULL DEFAULT 0,
    updated         INTEGER NOT NULL DEFAULT 0,
    unchanged       INTEGER NOT NULL DEFAULT 0,
    new_hc          INTEGER NOT NULL DEFAULT 0,   -- neue High/Critical
    total           INTEGER NOT NULL DEFAULT 0,
    source          TEXT NOT NULL DEFAULT ''
);

-- C3 In-App-Sync: Lauf-Historie + Concurrency-Lock (#948, Story B)
CREATE TABLE IF NOT EXISTS cra_sync_runs (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    started_at      TEXT NOT NULL DEFAULT (aics_now()),
    finished_at     TEXT,
    status          TEXT NOT NULL DEFAULT 'running',  -- running|finished|failed
    report_json     TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_cra_sync_runs_projekt ON cra_sync_runs(projekt_name, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_cra_sync_runs_status ON cra_sync_runs(projekt_name, status);
"""


def _connect(db_path: Path) -> Any:
    """Postgres-Verbindung (Schema je Modul) über den zentralen Kompat-Layer (#1332)."""
    return _sdb.connect(db_path)


# Nachträglich ergänzte Spalten (Migration für bestehende DBs). CREATE TABLE
# IF NOT EXISTS legt sie bei neuen DBs an; für vorhandene DBs ALTERn wir.
_COLUMN_MIGRATIONS: dict[str, list[tuple[str, str]]] = {
    "cra_vuln": [
        ("source", "TEXT NOT NULL DEFAULT 'manual'"),       # #937
        ("last_synced_at", "TEXT"),                          # #937
        # #1761 — Art. 13 Abs. 6, Upstream-Meldung (additiv, kein Bestandseingriff)
        ("upstream_status", "TEXT NOT NULL DEFAULT 'offen'"),
        ("upstream_gemeldet_am", "TEXT"),
        ("upstream_kanal", "TEXT NOT NULL DEFAULT ''"),
        ("upstream_referenz", "TEXT NOT NULL DEFAULT ''"),
        ("upstream_begruendung", "TEXT NOT NULL DEFAULT ''"),
        ("upstream_von", "TEXT NOT NULL DEFAULT ''"),
    ],
    "cra_sbom": [  # #1771 — mehrere Artefakte je Release
        ("artefakt", "TEXT NOT NULL DEFAULT ''"),
    ],
    "cra_threatmodel": [
        ("framework_source", "TEXT NOT NULL DEFAULT 'manual'"),  # #938
    ],
    "cra_support_period": [  # #1209
        ("update_availability_until", "TEXT"),
        ("doku_retention_until", "TEXT"),
        ("doc_retention_until", "TEXT"),
        ("support_end_kaufhinweis_url", "TEXT NOT NULL DEFAULT ''"),
        ("support_end_kaufhinweis_nachweis", "TEXT NOT NULL DEFAULT ''"),
        # #1762 — Update-Zusagen. Additiv: Bestandszeilen bekommen die Defaults
        # (''/0), also „keine Zusage dokumentiert". Das ist die ehrliche Vorbelegung;
        # ein Default von 1 hätte jedem Altprojekt eine Zusage angedichtet, die
        # niemand gegeben hat.
        ("sicherheitsupdate_kanal", "TEXT NOT NULL DEFAULT ''"),
        ("funktionsupdate_kanal", "TEXT NOT NULL DEFAULT ''"),
        ("sicherheitsupdates_kostenlos", "INTEGER NOT NULL DEFAULT 0"),
        ("kanaele_getrennt", "INTEGER NOT NULL DEFAULT 0"),
        ("update_zusagen_nachweis", "TEXT NOT NULL DEFAULT ''"),
    ],
    "cra_dokumente": [  # #1217 — Nachweis↔Anforderung-Traceability
        ("anforderung_id", "TEXT NOT NULL DEFAULT ''"),
        ("owasp_id", "TEXT NOT NULL DEFAULT ''"),
        ("annex_baustein", "TEXT NOT NULL DEFAULT ''"),
    ],
}


def _migrate_columns(con: Any) -> None:
    for table, cols in _COLUMN_MIGRATIONS.items():
        for name, decl in cols:
            con.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {decl}")
    _migrate_sbom_unique(con)


def _migrate_sbom_unique(con) -> None:
    """Eindeutigkeit von ``cra_sbom`` um das Artefakt erweitern (#1771).

    Bestandsdatenbanken tragen noch
    ``UNIQUE(projekt_name, release_version, sbom_format)``. Damit lässt sich zu
    einer Version **keine zweite SBOM** anlegen — und genau das braucht ein
    Produkt aus mehreren Artefakten (Anwendung + Webserver + …).

    Die alte Regel wird gelöst und die neue gesetzt; beides idempotent und
    fehlertolerant, denn eine nicht gelungene Lockerung darf den Start nicht
    verhindern. Sie **lockert** nur: Was vorher eindeutig war, ist es weiter.
    """
    alt = "cra_sbom_projekt_name_release_version_sbom_format_key"
    neu = "cra_sbom_projekt_release_format_artefakt_key"
    try:
        con.execute(f"ALTER TABLE cra_sbom DROP CONSTRAINT IF EXISTS {alt}")
        con.execute(
            f"ALTER TABLE cra_sbom ADD CONSTRAINT {neu} "
            "UNIQUE (projekt_name, release_version, sbom_format, artefakt)")
    except Exception as e:  # noqa: BLE001 — z.B. weil die neue Regel schon steht
        import logging
        logging.getLogger(__name__).debug("cra_sbom-Eindeutigkeit unverändert: %s", e)


def ensure_db(db_path: Path) -> None:
    con = _connect(db_path)
    try:
        con.executescript(SCHEMA)
        _migrate_columns(con)
        con.commit()
        from shared.firmen_link import ensure_firmen_id_column  # S1 (#1071)
        ensure_firmen_id_column(con, "cra_projekte")
    finally:
        con.close()


# ── Projekte ──────────────────────────────────────────────────────────────────

def save_projekt(
    db_path: Path,
    name: str,
    unternehmen: str = "",
    produkt: str = "",
    produktklasse: str = "default",
    beschreibung: str = "",
    berater: str = "",
    meta: dict[str, Any] | None = None,
) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO cra_projekte
                (name, unternehmen, produkt, produktklasse, beschreibung, berater, meta_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, aics_now())
            ON CONFLICT(name) DO UPDATE SET
                unternehmen   = excluded.unternehmen,
                produkt       = excluded.produkt,
                produktklasse = excluded.produktklasse,
                beschreibung  = excluded.beschreibung,
                berater       = excluded.berater,
                meta_json     = excluded.meta_json,
                updated_at    = aics_now()
            """,
            (name, unternehmen, produkt, produktklasse, beschreibung, berater,
             json.dumps(meta or {}, ensure_ascii=False)),
        )
        con.commit()
        # #1511: firmen_id bei Anlage per Name-Match setzen (Risiko-Cockpit).
        try:
            from shared.firmen_link import assign_firmen_id_on_save
            assign_firmen_id_on_save(con, db_path, "cra_projekte", name, unternehmen)
        except Exception:
            pass
    finally:
        con.close()


def update_projekt_meta(db_path: Path, name: str, meta: dict[str, Any]) -> None:
    """Nur die ``meta_json``-Spalte eines bestehenden Projekts aktualisieren.

    Bewahrt alle übrigen Felder; genutzt für die CRA↔Risikobewertung-Verknüpfung
    (#880)."""
    con = _connect(db_path)
    try:
        con.execute(
            "UPDATE cra_projekte SET meta_json=?, updated_at=aics_now() WHERE name=?",
            (json.dumps(meta or {}, ensure_ascii=False), name),
        )
        con.commit()
    finally:
        con.close()


def load_projekt(db_path: Path, name: str) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute("SELECT * FROM cra_projekte WHERE name=?", (name,))
        row = cur.fetchone()
        if row is None:
            return None
        d = dict(row)
        try:
            d["meta"] = json.loads(d.get("meta_json", "{}"))
        except Exception:
            d["meta"] = {}
        return d
    finally:
        con.close()


def list_projekte(db_path: Path) -> list[str]:
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT name FROM cra_projekte ORDER BY updated_at DESC, name"
        )
        return [r["name"] for r in cur.fetchall()]
    finally:
        con.close()


def list_projekte_fuer_firma(db_path: Path, firma_name: str) -> list[dict]:
    """Issue #435: Liefert volle CRA-Projekt-Records fuer einen Firmen,
    via `unternehmen`-Match."""
    if not firma_name:
        return []
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT * FROM cra_projekte WHERE unternehmen=? ORDER BY LOWER(name)",
            (firma_name,),
        )
        out: list[dict] = []
        for r in cur.fetchall():
            d = dict(r)
            try:
                d["meta"] = json.loads(d.get("meta_json", "{}") or "{}")
            except Exception:
                d["meta"] = {}
            out.append(d)
        return out
    finally:
        con.close()


#: Alle projekt-bezogenen Tabellen des CRA-Moduls mit ihrer Projekt-Spalte
#: (#1752). Diese Liste ist die **einzige** Quelle für das Aufräumen beim
#: Löschen eines Projekts.
#:
#: Vorher nannte ``delete_projekt`` fünf Tabellen direkt im Code und ließ
#: mindestens acht stehen — darunter ``cra_vuln`` (Schwachstellen mit
#: CVE-Bezug und Triage-Kommentaren) und ``cra_psirt`` (Kontaktdaten von
#: Personen). Bei einem Mandanten, der die Löschung seiner Daten verlangt, ist
#: das keine Formalie. Unter Postgres fiel es zusätzlich in Tests nicht auf:
#: SQLite-Pfade sind nur Schema-Selektoren (#1332), das ``unlink()``-Teardown
#: älterer Tests ist dort ein No-op, also sammelten sich Zeilen über Läufe
#: hinweg und ein neuer Test sah Daten eines alten Projekts gleichen Namens.
PROJEKT_TABELLEN: tuple[tuple[str, str], ...] = (
    ("cra_bewertungen", "projekt_name"),
    ("cra_dokumente", "projekt_name"),
    ("cra_meldung", "projekt_name"),
    ("cra_akteure", "projekt_name"),
    ("cra_korrektur", "projekt_name"),
    # #1762: Vorgänge der Marktüberwachung (Art. 52-56) — Behördenname,
    # Aktenzeichen und bereitgestellte Unterlagen; gehört genauso gelöscht.
    ("cra_marktaufsicht", "projekt_name"),
    ("cra_vuln", "projekt_name"),
    ("cra_sbom", "projekt_name"),
    # #1761: Komponentenliste je SBOM (Art. 13 Abs. 5). Enthält Lieferanten-
    # und Lizenzangaben Dritter — gehört beim Löschen eines Projekts mit weg.
    ("cra_sbom_komponenten", "projekt_name"),
    ("cra_psirt", "projekt_name"),
    ("cra_support_period", "projekt_name"),
    ("cra_threatmodel", "projekt_name"),
    ("cra_owasp_checks", "projekt_name"),
    ("cra_anforderungen_custom", "projekt_name"),
    ("cra_konformitaet", "projekt_name"),
    ("cra_konformitaet_final", "projekt_name"),
    # #1753: Archiv der ausgestellten EU-Konformitätserklärungen (eigene
    # Tabelle, Begründung im Docstring von ``cra/doc_export.py``).
    ("cra_doc_final", "projekt_name"),
    ("cra_release", "projekt_name"),
    ("cra_release_snapshot", "projekt_name"),
    ("cra_sync_state", "projekt_name"),
    ("cra_sync_runs", "projekt_name"),
)

#: Tabellen des Moduls ohne Projektbezug — ausdrücklich aufgeführt, damit der
#: Test in ``tests/test_cra_delete_cleanup_1752.py`` eine **neue** Tabelle
#: bemerkt, die in keiner der beiden Listen steht. Ohne diese Gegenliste fehlt
#: beim nächsten Register wieder eines.
TABELLEN_OHNE_PROJEKTBEZUG: frozenset[str] = frozenset({"cra_projekte"})


def _loesche_archiv_dateien(db_path: Path, name: str) -> int:
    """Entfernt die archivierten PDFs eines Projekts von der Platte.

    Zwei Archive, gleiche Regel: der freigegebene Konformitäts**nachweis**
    (``cra_konformitaet_final``) und die ausgestellte EU-Konformitäts**erklärung**
    (``cra_doc_final``, #1753).

    Die Dateien gehen mit den Datenbankzeilen — nicht aus Ordnungsliebe: Eine
    Datei ohne Zeile ist für die Anwendung unsichtbar, also kann sie niemand
    mehr finden, zuordnen oder löschen. Beim Löschen eines Mandanten wäre das
    das schlechtere Ergebnis als die Löschung selbst.

    **Folge, die jemand wissen muss:** Mit dem Projekt verschwindet sein
    Konformitäts-Archiv (PDF + SHA-256). Wer den Nachweis behalten will, lädt
    ihn vorher herunter. Best effort — ein nicht löschbarer Pfad darf das
    Löschen des Projekts nicht verhindern.
    """
    entfernt = 0

    def _weg(rows: list[dict[str, Any]]) -> int:
        weg = 0
        for rec in rows:
            pfad = str(rec.get("pdf_path") or "")
            if not pfad:
                continue
            try:
                Path(pfad).unlink(missing_ok=True)
                weg += 1
            except OSError:
                continue
        return weg

    try:
        from cra import konformitaet_final_db as fdb
        entfernt += _weg(list(fdb.list_final(db_path, name)))
    except Exception:  # noqa: BLE001 — best effort je Archiv
        pass
    try:
        from cra import doc_export
        entfernt += _weg(list(doc_export.list_archiv(db_path, name)))
    except Exception:  # noqa: BLE001
        pass
    return entfernt


def delete_projekt(db_path: Path, name: str) -> None:
    """Projekt und **alle** seine Daten entfernen (#1752).

    Reihenfolge: erst die Dateien (solange die Zeilen noch da sind, die auf sie
    zeigen), dann die Zeilen, zuletzt das Projekt selbst.
    """
    _loesche_archiv_dateien(db_path, name)
    con = _connect(db_path)
    try:
        # PG-sicher über Savepoint: Eine Tabelle kann fehlen, wenn das Vertikal
        # in dieser Installation nie genutzt wurde. Ohne Savepoint bricht die
        # Transaktion ab (InFailedSqlTransaction) und das Projekt selbst bliebe
        # stehen — das Löschen würde also an einer ungenutzten Tabelle scheitern.
        for tbl, spalte in PROJEKT_TABELLEN:
            con.try_execute(f"DELETE FROM {tbl} WHERE {spalte}=?", (name,))
        con.execute("DELETE FROM cra_projekte WHERE name=?", (name,))
        con.commit()
    finally:
        con.close()


# ── Bewertungen ───────────────────────────────────────────────────────────────

def save_bewertung(
    db_path: Path,
    projekt_name: str,
    anforderung_id: str,
    bewertung: int,
    kommentar: str = "",
    massnahme: str = "",
    verantwortlich: str = "",
    zieldatum: str = "",
) -> None:
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO cra_bewertungen
                (projekt_name, anforderung_id, bewertung, kommentar,
                 massnahme, verantwortlich, zieldatum, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, aics_now())
            ON CONFLICT(projekt_name, anforderung_id) DO UPDATE SET
                bewertung      = excluded.bewertung,
                kommentar      = excluded.kommentar,
                massnahme      = excluded.massnahme,
                verantwortlich = excluded.verantwortlich,
                zieldatum      = excluded.zieldatum,
                updated_at     = aics_now()
            """,
            (projekt_name, anforderung_id, bewertung, kommentar,
             massnahme, verantwortlich, zieldatum),
        )
        con.commit()
    finally:
        con.close()


def bulk_save_bewertungen(
    db_path: Path,
    projekt_name: str,
    rows: list[dict[str, Any]],
) -> int:
    con = _connect(db_path)
    try:
        count = 0
        for r in rows:
            aid = str(r.get("anforderung_id", "")).strip()
            if not aid:
                continue
            bew = int(r.get("bewertung", 0))
            if bew < 0 or bew > 5:
                bew = 0
            con.execute(
                """
                INSERT INTO cra_bewertungen
                    (projekt_name, anforderung_id, bewertung, kommentar,
                     massnahme, verantwortlich, zieldatum, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, aics_now())
                ON CONFLICT(projekt_name, anforderung_id) DO UPDATE SET
                    bewertung      = excluded.bewertung,
                    kommentar      = excluded.kommentar,
                    massnahme      = excluded.massnahme,
                    verantwortlich = excluded.verantwortlich,
                    zieldatum      = excluded.zieldatum,
                    updated_at     = aics_now()
                """,
                (projekt_name, aid, bew,
                 str(r.get("kommentar", "")),
                 str(r.get("massnahme", "")),
                 str(r.get("verantwortlich", "")),
                 str(r.get("zieldatum", ""))),
            )
            count += 1
        con.commit()
        return count
    finally:
        con.close()


def load_bewertungen(db_path: Path, projekt_name: str) -> dict[str, dict[str, Any]]:
    """Gibt {anforderung_id: {bewertung, kommentar, massnahme, ...}} zurück."""
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT * FROM cra_bewertungen WHERE projekt_name=?", (projekt_name,)
        )
        return {row["anforderung_id"]: dict(row) for row in cur.fetchall()}
    finally:
        con.close()


# ── OWASP checklist ───────────────────────────────────────────────────────────

def upsert_owasp_check(
    db_path: Path,
    projekt_name: str,
    owasp_id: str,
    status: int,
    kommentar: str = "",
    evidence: list[dict[str, Any]] | None = None,
) -> None:
    status = int(status)
    if status < 0 or status > 5:
        status = 0
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO cra_owasp_checks
                (projekt_name, owasp_id, status, kommentar, evidence_json, updated_at)
            VALUES (?, ?, ?, ?, ?, aics_now())
            ON CONFLICT(projekt_name, owasp_id) DO UPDATE SET
                status        = excluded.status,
                kommentar     = excluded.kommentar,
                evidence_json = excluded.evidence_json,
                updated_at    = aics_now()
            """,
            (
                projekt_name,
                str(owasp_id).strip(),
                status,
                str(kommentar or ""),
                json.dumps(evidence or [], ensure_ascii=False),
            ),
        )
        con.commit()
    finally:
        con.close()


def load_owasp_checks(db_path: Path, projekt_name: str) -> dict[str, dict[str, Any]]:
    """Gibt {owasp_id: rowdict} zurück (inkl. evidence parsed)."""
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT * FROM cra_owasp_checks WHERE projekt_name=?",
            (projekt_name,),
        )
        out: dict[str, dict[str, Any]] = {}
        for row in cur.fetchall():
            d = dict(row)
            try:
                d["evidence"] = json.loads(d.get("evidence_json", "[]"))
            except Exception:
                d["evidence"] = []
            out[str(d.get("owasp_id", "")).strip()] = d
        return out
    finally:
        con.close()


# ── Benutzerdefinierte Anforderungen ──────────────────────────────────────────

def save_custom_anforderung(db_path: Path, req: dict[str, Any]) -> None:
    """Speichert eine benutzerdefinierte Anforderung oder überschreibt eine Standardanforderung."""
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO cra_anforderungen_custom
                (id, kapitel, ref, titel, beschreibung, hinweise, gewichtung, ist_override, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, aics_now())
            ON CONFLICT(id) DO UPDATE SET
                kapitel      = excluded.kapitel,
                ref          = excluded.ref,
                titel        = excluded.titel,
                beschreibung = excluded.beschreibung,
                hinweise     = excluded.hinweise,
                gewichtung   = excluded.gewichtung,
                ist_override = excluded.ist_override,
                updated_at   = aics_now()
            """,
            (
                req["id"], req.get("kapitel", "IMPL"), req.get("ref", ""),
                req.get("titel", ""), req.get("beschreibung", ""),
                req.get("hinweise", ""), int(req.get("gewichtung", 1)),
                1 if req.get("ist_override") else 0,
            ),
        )
        con.commit()
    finally:
        con.close()


def delete_custom_anforderung(db_path: Path, req_id: str) -> None:
    """Löscht einen benutzerdefinierten Eintrag oder eine Override-Definition."""
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM cra_anforderungen_custom WHERE id=?", (req_id,))
        con.commit()
    finally:
        con.close()


def load_custom_anforderungen(db_path: Path) -> list[dict[str, Any]]:
    """Lädt alle benutzerdefinierten / überschriebenen Anforderungen."""
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT * FROM cra_anforderungen_custom ORDER BY kapitel, id"
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()


# ═══════════════════════════════════════════════════════════════════════════
# Phase A — Pflicht-Doku-Helper (Issues #472-#476)
# ═══════════════════════════════════════════════════════════════════════════

import json as _json


def _row_with_json(row, json_fields: tuple[str, ...]) -> dict:
    d = dict(row)
    for f in json_fields:
        try:
            d[f] = _json.loads(d.get(f) or '[]') if f.endswith('_json') or 'json' in f else d[f]
        except Exception:
            d[f] = []
    return d


# ─── C1: SBOM ──────────────────────────────────────────────────────────────

def list_sbom(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM cra_sbom WHERE projekt_name=? ORDER BY sbom_datum DESC",
            (projekt_name,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d['lizenzen'] = _json.loads(d.get('lizenzen_json', '[]') or '[]')
            except Exception:
                d['lizenzen'] = []
            out.append(d)
        return out
    finally:
        con.close()


def save_sbom(db_path: Path, projekt_name: str, data: dict) -> int:
    ensure_db(db_path)
    if not data.get('release_version'):
        raise ValueError("Feld 'release_version' ist Pflicht")
    from datetime import datetime as _dt
    sbom_datum = data.get('sbom_datum') or _dt.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    lizenzen_json = _json.dumps(data.get('lizenzen') or [], ensure_ascii=False)
    con = _connect(db_path)
    try:
        sid = data.get('id')
        if sid:
            con.execute(
                """UPDATE cra_sbom SET release_version=?, sbom_format=?, sbom_datum=?,
                          komponenten_count=?, lizenzen_json=?, quelle=?, blob_path=?,
                          notizen=?, artefakt=COALESCE(?, artefakt),
                          updated_at=aics_now() WHERE id=?""",
                (data['release_version'], data.get('sbom_format', 'spdx'),
                 sbom_datum, int(data.get('komponenten_count', 0)),
                 lizenzen_json, data.get('quelle', ''), data.get('blob_path', ''),
                 data.get('notizen', ''),
                 # #1771: Nur setzen, wenn der Aufrufer das Feld **nennt**.
                 # Sonst löscht jeder Teil-Update den Artefakt-Namen — genau
                 # das ist beim Komponenten-Import passiert, und es ist
                 # dieselbe Falle wie beim `meta_json`-Verlust in #1540.
                 (str(data['artefakt'] or '') if 'artefakt' in data else None),
                 int(sid)),
            )
            con.commit()
            return int(sid)
        cur = con.execute(
            """INSERT INTO cra_sbom (projekt_name, release_version, sbom_format, sbom_datum,
                       komponenten_count, lizenzen_json, quelle, blob_path, notizen, artefakt)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (projekt_name, data['release_version'], data.get('sbom_format', 'spdx'),
             sbom_datum, int(data.get('komponenten_count', 0)),
             lizenzen_json, data.get('quelle', ''), data.get('blob_path', ''),
             data.get('notizen', ''), str(data.get('artefakt') or '')),
        )
        con.commit()
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def delete_sbom(db_path: Path, sbom_id: int) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        # #1761: Die Komponentenliste hängt an der SBOM. Bliebe sie stehen,
        # zählte sie beim nächsten Vergleich als Bestand einer SBOM, die es
        # nicht mehr gibt — ein Befund aus Resten.
        con.try_execute("DELETE FROM cra_sbom_komponenten WHERE sbom_id=?", (int(sbom_id),))
        con.execute("DELETE FROM cra_sbom WHERE id=?", (int(sbom_id),))
        con.commit()
    finally:
        con.close()


# ─── C2: PSIRT ─────────────────────────────────────────────────────────────

def load_psirt(db_path: Path, projekt_name: str) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        row = con.execute("SELECT * FROM cra_psirt WHERE projekt_name=?", (projekt_name,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d['psirt_contacts'] = _json.loads(d.get('psirt_contacts', '[]') or '[]')
        except Exception:
            d['psirt_contacts'] = []
        return d
    finally:
        con.close()


def save_psirt(db_path: Path, projekt_name: str, data: dict) -> None:
    ensure_db(db_path)
    contacts_json = _json.dumps(data.get('psirt_contacts') or [], ensure_ascii=False)
    con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO cra_psirt (projekt_name, intake_kanal, triage_sla,
                       fix_sla_critical, fix_sla_high, fix_sla_medium,
                       disclosure_policy_url, security_md_url, psirt_contacts, notizen, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,aics_now())
               ON CONFLICT(projekt_name) DO UPDATE SET
                   intake_kanal=excluded.intake_kanal,
                   triage_sla=excluded.triage_sla,
                   fix_sla_critical=excluded.fix_sla_critical,
                   fix_sla_high=excluded.fix_sla_high,
                   fix_sla_medium=excluded.fix_sla_medium,
                   disclosure_policy_url=excluded.disclosure_policy_url,
                   security_md_url=excluded.security_md_url,
                   psirt_contacts=excluded.psirt_contacts,
                   notizen=excluded.notizen,
                   updated_at=aics_now()""",
            (projekt_name, data.get('intake_kanal', ''), data.get('triage_sla', ''),
             data.get('fix_sla_critical', ''), data.get('fix_sla_high', ''),
             data.get('fix_sla_medium', ''), data.get('disclosure_policy_url', ''),
             data.get('security_md_url', ''), contacts_json, data.get('notizen', '')),
        )
        con.commit()
    finally:
        con.close()


# ─── C3: Vulnerability-Tracker ─────────────────────────────────────────────

_VULN_ALLOWED_STATUS = {'open', 'triaging', 'fixed', 'disclosed', 'wontfix'}


def list_vuln(db_path: Path, projekt_name: str, status: str | None = None) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        if status:
            rows = con.execute(
                "SELECT * FROM cra_vuln WHERE projekt_name=? AND status=? ORDER BY cvss_score DESC, cve_id",
                (projekt_name, status),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM cra_vuln WHERE projekt_name=? ORDER BY status, cvss_score DESC, cve_id",
                (projekt_name,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def save_vuln(db_path: Path, projekt_name: str, data: dict) -> int:
    ensure_db(db_path)
    if not data.get('id') and not data.get('cve_id'):
        raise ValueError("Feld 'cve_id' ist Pflicht")
    status = data.get('status', 'open')
    if status not in _VULN_ALLOWED_STATUS:
        raise ValueError(f"status muss eines sein von: {sorted(_VULN_ALLOWED_STATUS)}")
    con = _connect(db_path)
    try:
        vid = data.get('id')
        if vid:
            con.execute(
                """UPDATE cra_vuln SET titel=?, schwere=?, cvss_score=?, cvss_vector=?,
                          affected_component=?, affected_versions=?, fixed_in_version=?,
                          advisory_url=?, status=?, triage_kommentar=?, fixed_at=?,
                          disclosed_at=?, updated_at=aics_now() WHERE id=?""",
                (data.get('titel', ''), data.get('schwere', 'unknown'),
                 float(data.get('cvss_score') or 0), data.get('cvss_vector', ''),
                 data.get('affected_component', ''), data.get('affected_versions', ''),
                 data.get('fixed_in_version', ''), data.get('advisory_url', ''),
                 status, data.get('triage_kommentar', ''),
                 data.get('fixed_at'), data.get('disclosed_at'), int(vid)),
            )
            con.commit()
            return int(vid)
        cur = con.execute(
            """INSERT INTO cra_vuln (projekt_name, cve_id, titel, schwere, cvss_score, cvss_vector,
                       affected_component, affected_versions, fixed_in_version, advisory_url,
                       status, triage_kommentar, fixed_at, disclosed_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (projekt_name, data['cve_id'], data.get('titel', ''), data.get('schwere', 'unknown'),
             float(data.get('cvss_score') or 0), data.get('cvss_vector', ''),
             data.get('affected_component', ''), data.get('affected_versions', ''),
             data.get('fixed_in_version', ''), data.get('advisory_url', ''),
             status, data.get('triage_kommentar', ''),
             data.get('fixed_at'), data.get('disclosed_at')),
        )
        con.commit()
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def delete_vuln(db_path: Path, vuln_id: int) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM cra_vuln WHERE id=?", (int(vuln_id),))
        con.commit()
    finally:
        con.close()


# Rangfolge der Schwere — eine Sync-Quelle darf eine bestehende Bewertung nur
# anheben, nicht heimlich abschwächen (Idempotenz, #937).
_SEVERITY_RANK = {'unknown': 0, 'low': 1, 'medium': 2, 'high': 3, 'critical': 4}


def upsert_vuln(db_path: Path, projekt_name: str, finding: dict) -> dict:
    """Idempotenter Upsert eines Sync-Funds (#937).

    - INSERT bei neuem ``cve_id``; sonst UPDATE des bestehenden Eintrags.
    - ``triage_kommentar`` wird **nie** überschrieben (manueller Inhalt).
    - ``discovered_at`` wird nur beim INSERT gesetzt.
    - Schwere/CVSS werden nur angehoben, nie abgesenkt.
    - ``status`` wird nicht überschrieben, wenn der Auditor bereits manuell
      triagiert/abgeschlossen hat (triaging/fixed/disclosed/wontfix).

    Rückgabe: ``{'action': 'inserted'|'updated'|'unchanged', 'cve_id': ...}``.
    """
    ensure_db(db_path)
    cve = (finding.get('cve_id') or '').strip()
    if not cve:
        raise ValueError("Feld 'cve_id' ist Pflicht")
    new_status = finding.get('status', 'open')
    if new_status not in _VULN_ALLOWED_STATUS:
        raise ValueError(f"status muss eines sein von: {sorted(_VULN_ALLOWED_STATUS)}")
    source = finding.get('source', 'manual')
    new_sev = finding.get('schwere', 'unknown')
    new_cvss = float(finding.get('cvss_score') or 0)

    con = _connect(db_path)
    try:
        row = con.execute(
            "SELECT * FROM cra_vuln WHERE projekt_name=? AND cve_id=?",
            (projekt_name, cve),
        ).fetchone()
        if row is None:
            con.execute(
                """INSERT INTO cra_vuln (projekt_name, cve_id, titel, schwere, cvss_score,
                           cvss_vector, affected_component, affected_versions, fixed_in_version,
                           advisory_url, status, source, last_synced_at, fixed_at, disclosed_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,aics_now(),?,?)""",
                (projekt_name, cve, finding.get('titel', ''), new_sev, new_cvss,
                 finding.get('cvss_vector', ''), finding.get('affected_component', ''),
                 finding.get('affected_versions', ''), finding.get('fixed_in_version', ''),
                 finding.get('advisory_url', ''), new_status, source,
                 finding.get('fixed_at'), finding.get('disclosed_at')),
            )
            con.commit()
            return {'action': 'inserted', 'cve_id': cve}

        cur = dict(row)
        # Schwere/CVSS nur anheben.
        keep_sev = cur.get('schwere', 'unknown')
        sev = new_sev if _SEVERITY_RANK.get(new_sev, 0) > _SEVERITY_RANK.get(keep_sev, 0) else keep_sev
        cvss = max(new_cvss, float(cur.get('cvss_score') or 0))
        # Status: manuelle Triage des Auditors nicht zurücksetzen.
        manual_locked = cur.get('status') in ('triaging', 'fixed', 'disclosed', 'wontfix')
        status = cur.get('status') if manual_locked else new_status
        con.execute(
            """UPDATE cra_vuln SET titel=?, schwere=?, cvss_score=?, cvss_vector=?,
                      affected_component=?, affected_versions=?, fixed_in_version=?,
                      advisory_url=?, status=?, source=?, last_synced_at=aics_now(),
                      fixed_at=COALESCE(?, fixed_at), disclosed_at=COALESCE(?, disclosed_at),
                      updated_at=aics_now()
               WHERE id=?""",
            (finding.get('titel') or cur.get('titel', ''), sev, cvss,
             finding.get('cvss_vector') or cur.get('cvss_vector', ''),
             finding.get('affected_component') or cur.get('affected_component', ''),
             finding.get('affected_versions') or cur.get('affected_versions', ''),
             finding.get('fixed_in_version') or cur.get('fixed_in_version', ''),
             finding.get('advisory_url') or cur.get('advisory_url', ''),
             status, source, finding.get('fixed_at'), finding.get('disclosed_at'),
             cur['id']),
        )
        con.commit()
        # "unchanged" für den Sync-Report: nichts Inhaltliches verändert.
        changed = (sev != keep_sev or cvss != float(cur.get('cvss_score') or 0)
                   or status != cur.get('status'))
        return {'action': 'updated' if changed else 'unchanged', 'cve_id': cve}
    finally:
        con.close()


# ─── C4: Support-Period ────────────────────────────────────────────────────

#: Regel-Mindestdauer des Unterstützungszeitraums in Jahren (Art. 13 Abs. 8).
#: Kürzer ist zulässig — aber nur, wenn die **erwartete Nutzungsdauer** des
#: Produkts kürzer ist. Genau diese Erwartung ist die Begründung, und ohne sie
#: ist die Ausnahme eine Behauptung (#1762).
MINDEST_SUPPORT_JAHRE = 5

#: Mindestlänge der Begründung. Eine Begründung von drei Zeichen ist keine; die
#: Zahl ist bewusst niedrig — sie soll ein leeres Feld und ein „n/a" abfangen,
#: nicht Prosa erzwingen.
BEGRUENDUNG_MIN_ZEICHEN = 20


def _bool01(wert: Any) -> int:
    """Checkbox-Werte aus JSON (``true``/``1``/``"ja"``) auf 0/1 normalisieren."""
    if isinstance(wert, str):
        return 1 if wert.strip().lower() in ("1", "true", "ja", "yes", "on") else 0
    return 1 if wert else 0


def pruefe_support_period(data: dict) -> int:
    """Pflichtangaben des Unterstützungszeitraums prüfen; liefert die Support-Jahre.

    Serverseitig, nicht nur im Formular — das Feld wird auch vom Autodetect und
    von Tests beschrieben, und eine Prüfung, die nur im Browser steht, ist bei
    einem Audit kein Argument. ``ValueError`` nennt, **was** fehlt und **warum**;
    die API gibt den Text unverändert als 400 weiter.
    """
    rohwert = data.get('support_jahre', MINDEST_SUPPORT_JAHRE)
    if rohwert in (None, ''):
        rohwert = MINDEST_SUPPORT_JAHRE
    try:
        jahre = int(rohwert)
    except (TypeError, ValueError):
        raise ValueError(
            f"Support-Jahre: '{rohwert}' ist keine Zahl. Der Unterstützungszeitraum "
            "wird in ganzen Jahren ab Markteintritt angegeben.") from None
    if jahre < 1:
        raise ValueError(
            "Der Unterstützungszeitraum muss mindestens 1 Jahr betragen. Ein "
            "Zeitraum von 0 Jahren lässt sich auch mit einer kurzen erwarteten "
            "Nutzungsdauer nicht begründen — ein Produkt ohne jede Zusage von "
            "Sicherheitsupdates darf nicht in Verkehr gebracht werden.")
    begruendung = str(data.get('rationale') or '').strip()
    if jahre < MINDEST_SUPPORT_JAHRE and len(begruendung) < BEGRUENDUNG_MIN_ZEICHEN:
        raise ValueError(
            f"Begründung fehlt: {jahre} Jahre liegen unter der Regel von "
            f"{MINDEST_SUPPORT_JAHRE} Jahren (Art. 13 Abs. 8). Ein kürzerer "
            "Unterstützungszeitraum ist nur zulässig, wenn die erwartete "
            "Nutzungsdauer des Produkts kürzer ist. Diese Erwartung im Feld "
            f"Begründung festhalten (mindestens {BEGRUENDUNG_MIN_ZEICHEN} Zeichen) "
            "— ohne sie ist die Abweichung gegenüber einer Marktaufsichtsbehörde "
            "nicht haltbar.")
    url = str(data.get('support_end_kaufhinweis_url') or '').strip()
    if url and not url.lower().startswith(('http://', 'https://')):
        raise ValueError(
            f"Kaufhinweis-URL: '{url}' ist keine Adresse. Das Support-Ende muss "
            "vor dem Kauf einsehbar sein — ein Hinweis darauf, dass es irgendwo "
            "stehe, ist nicht einsehbar. Eine Adresse (http://… oder https://…) "
            "angeben; freie Beschreibungen gehören ins Nachweis-Feld.")
    return jahre


def load_support_period(db_path: Path, projekt_name: str) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        row = con.execute(
            "SELECT * FROM cra_support_period WHERE projekt_name=?", (projekt_name,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        # #1762: Die zwei Zusagen sind im Schema 0/1 — nach außen Wahrheitswerte,
        # damit Panel, Gate und Kundenfassung nicht jeder für sich casten.
        for f in ('sicherheitsupdates_kostenlos', 'kanaele_getrennt'):
            d[f] = bool(d.get(f))
        return d
    finally:
        con.close()


def save_support_period(db_path: Path, projekt_name: str, data: dict) -> None:
    ensure_db(db_path)
    from datetime import datetime, timedelta
    jahre = pruefe_support_period(data)
    # eol_datum aus markteintritt + support_jahre berechnen, falls nicht gesetzt
    eol = data.get('eol_datum')
    mt_obj = None
    if data.get('markteintritt_datum'):
        try:
            mt_obj = datetime.fromisoformat(data['markteintritt_datum'][:10])
        except Exception:
            mt_obj = None
    if not eol and mt_obj is not None:
        eol = (mt_obj + timedelta(days=jahre * 365)).date().isoformat()
    # #1209: Retention-/Update-Verfügbarkeits-Fristen berechnen.
    # Art. 13(9): Updates mind. max(10 J., Support-Zeitraum) ab Markteintritt.
    # Art. 13(13): techn. Doku + DoC mind. 10 J. ab Markteintritt.
    upd_until = doku_until = doc_until = None
    if mt_obj is not None:
        update_jahre = max(10, jahre)
        upd_until = (mt_obj + timedelta(days=update_jahre * 365)).date().isoformat()
        doku_until = (mt_obj + timedelta(days=10 * 365)).date().isoformat()
        doc_until = doku_until
    con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO cra_support_period (projekt_name, markteintritt_datum,
                       support_jahre, eol_datum, update_kanal, rationale, notizen,
                       update_availability_until, doku_retention_until, doc_retention_until,
                       support_end_kaufhinweis_url, support_end_kaufhinweis_nachweis,
                       sicherheitsupdate_kanal, funktionsupdate_kanal,
                       sicherheitsupdates_kostenlos, kanaele_getrennt,
                       update_zusagen_nachweis, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,aics_now())
               ON CONFLICT(projekt_name) DO UPDATE SET
                   markteintritt_datum=excluded.markteintritt_datum,
                   support_jahre=excluded.support_jahre,
                   eol_datum=excluded.eol_datum,
                   update_kanal=excluded.update_kanal,
                   rationale=excluded.rationale,
                   notizen=excluded.notizen,
                   update_availability_until=excluded.update_availability_until,
                   doku_retention_until=excluded.doku_retention_until,
                   doc_retention_until=excluded.doc_retention_until,
                   support_end_kaufhinweis_url=excluded.support_end_kaufhinweis_url,
                   support_end_kaufhinweis_nachweis=excluded.support_end_kaufhinweis_nachweis,
                   sicherheitsupdate_kanal=excluded.sicherheitsupdate_kanal,
                   funktionsupdate_kanal=excluded.funktionsupdate_kanal,
                   sicherheitsupdates_kostenlos=excluded.sicherheitsupdates_kostenlos,
                   kanaele_getrennt=excluded.kanaele_getrennt,
                   update_zusagen_nachweis=excluded.update_zusagen_nachweis,
                   updated_at=aics_now()""",
            (projekt_name, data.get('markteintritt_datum'), jahre,
             eol, data.get('update_kanal', ''), data.get('rationale', ''),
             data.get('notizen', ''), upd_until, doku_until, doc_until,
             data.get('support_end_kaufhinweis_url', ''),
             data.get('support_end_kaufhinweis_nachweis', ''),
             data.get('sicherheitsupdate_kanal', ''),
             data.get('funktionsupdate_kanal', ''),
             _bool01(data.get('sicherheitsupdates_kostenlos')),
             _bool01(data.get('kanaele_getrennt')),
             data.get('update_zusagen_nachweis', '')),
        )
        con.commit()
    finally:
        con.close()


# ─── C5: Threat-Model ──────────────────────────────────────────────────────

def load_threatmodel(db_path: Path, projekt_name: str) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        row = con.execute(
            "SELECT * FROM cra_threatmodel WHERE projekt_name=?", (projekt_name,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        for f in ('assets_json', 'threats_json', 'mitigations_json'):
            try:
                d[f.replace('_json', '')] = _json.loads(d.get(f, '[]') or '[]')
            except Exception:
                d[f.replace('_json', '')] = []
        return d
    finally:
        con.close()


def save_threatmodel(db_path: Path, projekt_name: str, data: dict) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO cra_threatmodel (projekt_name, framework, framework_source, scope,
                       assets_json, threats_json, mitigations_json, diagram_url, notizen, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,aics_now())
               ON CONFLICT(projekt_name) DO UPDATE SET
                   framework=excluded.framework, framework_source=excluded.framework_source,
                   scope=excluded.scope,
                   assets_json=excluded.assets_json, threats_json=excluded.threats_json,
                   mitigations_json=excluded.mitigations_json,
                   diagram_url=excluded.diagram_url, notizen=excluded.notizen,
                   updated_at=aics_now()""",
            (projekt_name, data.get('framework', 'STRIDE'),
             data.get('framework_source', 'manual'), data.get('scope', ''),
             _json.dumps(data.get('assets') or [], ensure_ascii=False),
             _json.dumps(data.get('threats') or [], ensure_ascii=False),
             _json.dumps(data.get('mitigations') or [], ensure_ascii=False),
             data.get('diagram_url', ''), data.get('notizen', '')),
        )
        con.commit()
    finally:
        con.close()


def adopt_threatmodel_framework(db_path: Path, projekt_name: str, framework: str) -> dict:
    """Übernimmt ``framework`` aus der verknüpften Risikobewertung ins C5-Threat-Model (#938).

    Respektiert einen manuellen Override (``framework_source == 'manual_override'``)
    und ändert dann nichts. Legt einen Threat-Model-Eintrag an, falls noch keiner
    existiert. Rückgabe beschreibt das Ergebnis für die API-Antwort/Audit.
    """
    if not framework:
        return {'adopted': False, 'reason': 'no_source_framework'}
    tm = load_threatmodel(db_path, projekt_name) or {}
    if tm.get('framework_source') == 'manual_override':
        return {'adopted': False, 'reason': 'manual_override',
                'framework': tm.get('framework')}
    if tm.get('framework') == framework and tm.get('framework_source') == 'risk_link':
        return {'adopted': False, 'reason': 'unchanged', 'framework': framework}
    payload = dict(tm)
    payload['framework'] = framework
    payload['framework_source'] = 'risk_link'
    save_threatmodel(db_path, projekt_name, payload)
    return {'adopted': True, 'framework': framework,
            'previous': tm.get('framework') or None}


# ─── C3 In-App-Sync: Last-Sync-State (#947) ────────────────────────────────

def record_sync_state(db_path: Path, projekt_name: str, report: dict) -> None:
    """Persistiert den letzten Sync-Stand (am Ende von vuln_sync.sync_vulns, #947)."""
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO cra_sync_state
                   (projekt_name, last_run_at, inserted, updated, unchanged, new_hc, total, source)
               VALUES (?, aics_now(), ?, ?, ?, ?, ?, ?)
               ON CONFLICT(projekt_name) DO UPDATE SET
                   last_run_at=aics_now(), inserted=excluded.inserted,
                   updated=excluded.updated, unchanged=excluded.unchanged,
                   new_hc=excluded.new_hc, total=excluded.total, source=excluded.source""",
            (projekt_name, int(report.get('inserted', 0)), int(report.get('updated', 0)),
             int(report.get('unchanged', 0)), int(report.get('new_high_critical', 0)),
             int(report.get('total', 0)), report.get('repo') or report.get('source') or ''),
        )
        con.commit()
    finally:
        con.close()


def load_sync_state(db_path: Path, projekt_name: str) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        row = con.execute(
            "SELECT * FROM cra_sync_state WHERE projekt_name=?", (projekt_name,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


# ─── C3 In-App-Sync: Run-Historie + Concurrency-Lock (#948) ────────────────

def get_running_sync_run(db_path: Path, projekt_name: str) -> dict[str, Any] | None:
    """Aktiver Lauf (status='running') für ein Projekt, sonst None — Concurrency-Lock."""
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        row = con.execute(
            "SELECT * FROM cra_sync_runs WHERE projekt_name=? AND status='running' ORDER BY started_at DESC LIMIT 1",
            (projekt_name,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def start_sync_run(db_path: Path, projekt_name: str) -> int:
    """Legt einen laufenden Run an und liefert dessen id (run_id)."""
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute(
            "INSERT INTO cra_sync_runs (projekt_name, status) VALUES (?, 'running')",
            (projekt_name,),
        )
        con.commit()
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def finish_sync_run(db_path: Path, run_id: int, status: str, report: dict | None = None) -> None:
    """Schließt einen Run ab (status='finished'|'failed') + speichert den Report."""
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute(
            """UPDATE cra_sync_runs SET status=?, finished_at=aics_now(), report_json=?
               WHERE id=?""",
            (status, _json.dumps(report or {}, ensure_ascii=False), int(run_id)),
        )
        con.commit()
    finally:
        con.close()


def list_sync_runs(db_path: Path, projekt_name: str, limit: int = 20) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM cra_sync_runs WHERE projekt_name=? ORDER BY started_at DESC LIMIT ?",
            (projekt_name, int(limit)),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d['report'] = _json.loads(d.get('report_json') or '{}')
            except Exception:
                d['report'] = {}
            out.append(d)
        return out
    finally:
        con.close()
