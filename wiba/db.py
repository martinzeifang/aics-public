"""WiBA-Modul – SQLite-Datenzugriff.

Tabellen:
- ``wiba_projekte``      – Projekte (mit logischer ``firmen_id``-Referenz, #1071).
- ``wiba_antworten``     – Antworten je Prüffrage (status/notiz/evidence).
- ``wiba_themen``        – Katalog: Themen/Bausteine (aus BSI-Checklisten).
- ``wiba_prueffragen``   – Katalog: Prüffragen je Thema (aus WiBA-Tool).
- ``wiba_catalog_meta``  – Katalog-Version/Quelle (updatefähig per Admin-Download).

Der Prüffragen-Katalog ist DB-gestützt (nicht im Code), damit BSI-Updates per
Admin-Download eingespielt werden können (#1119). Vorbild: ``cra/db.py``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared import db as _sdb
from wiba.constants import normalize_status, reifegrad_pct

SCHEMA = """

CREATE TABLE IF NOT EXISTS wiba_projekte (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    unternehmen   TEXT NOT NULL DEFAULT '',
    beschreibung  TEXT NOT NULL DEFAULT '',
    berater       TEXT NOT NULL DEFAULT '',
    meta_json     TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT DEFAULT (aics_now()),
    updated_at    TEXT DEFAULT (aics_now())
);

CREATE TABLE IF NOT EXISTS wiba_antworten (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name      TEXT NOT NULL,
    control_id        TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'offen',
    notiz             TEXT NOT NULL DEFAULT '',
    verantwortlich    TEXT NOT NULL DEFAULT '',
    zieldatum         TEXT NOT NULL DEFAULT '',
    evidence_doc_ids  TEXT NOT NULL DEFAULT '[]',
    updated_at        TEXT DEFAULT (aics_now()),
    UNIQUE(projekt_name, control_id)
);
CREATE INDEX IF NOT EXISTS idx_wiba_antworten_projekt ON wiba_antworten(projekt_name);

CREATE TABLE IF NOT EXISTS wiba_themen (
    theme_key      TEXT PRIMARY KEY,
    titel          TEXT NOT NULL DEFAULT '',
    bausteine      TEXT NOT NULL DEFAULT '',
    ziel           TEXT NOT NULL DEFAULT '',
    hinweis        TEXT NOT NULL DEFAULT '',
    weiterfuehrend TEXT NOT NULL DEFAULT '',
    reihenfolge    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS wiba_prueffragen (
    control_id   TEXT PRIMARY KEY,
    theme_key    TEXT NOT NULL,
    nr           INTEGER NOT NULL DEFAULT 0,
    frage        TEXT NOT NULL DEFAULT '',
    hilfsmittel  TEXT NOT NULL DEFAULT '',
    aufwand      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_wiba_prueffragen_theme ON wiba_prueffragen(theme_key);

CREATE TABLE IF NOT EXISTS wiba_catalog_meta (
    id           INTEGER PRIMARY KEY CHECK (id = 1),
    version      TEXT NOT NULL DEFAULT '',
    quelle       TEXT NOT NULL DEFAULT '',
    anzahl       INTEGER NOT NULL DEFAULT 0,
    imported_at  TEXT
);
"""


def _connect(db_path: Path) -> Any:
    """Postgres-Verbindung (Schema je Modul) über den zentralen Kompat-Layer (#1332)."""
    return _sdb.connect(db_path)


def ensure_db(db_path: Path) -> None:
    con = _connect(db_path)
    try:
        con.executescript(SCHEMA)
        con.commit()
        from shared.firmen_link import ensure_firmen_id_column
        ensure_firmen_id_column(con, "wiba_projekte")
    finally:
        con.close()


# ── Projekte ────────────────────────────────────────────────────────────────

def list_projekte(db_path: Path) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute("SELECT * FROM wiba_projekte ORDER BY name").fetchall()
        return [_projekt_to_dict(r) for r in rows]
    finally:
        con.close()


def load_projekt(db_path: Path, name: str) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        r = con.execute("SELECT * FROM wiba_projekte WHERE name=?", (name,)).fetchone()
        return _projekt_to_dict(r) if r else None
    finally:
        con.close()


def save_projekt(db_path: Path, *, name: str, unternehmen: str = "",
                 beschreibung: str = "", berater: str = "",
                 meta: dict | None = None) -> int:
    ensure_db(db_path)
    if not name or not name.strip():
        raise ValueError("'name' ist Pflicht")
    con = _connect(db_path)
    try:
        cur = con.execute(
            """INSERT INTO wiba_projekte(name, unternehmen, beschreibung, berater, meta_json)
               VALUES(?,?,?,?,?)
               ON CONFLICT(name) DO UPDATE SET
                 unternehmen=excluded.unternehmen,
                 beschreibung=excluded.beschreibung,
                 berater=excluded.berater,
                 meta_json=excluded.meta_json,
                 updated_at=aics_now()""",
            (name.strip(), unternehmen, beschreibung, berater,
             json.dumps(meta or {}, ensure_ascii=False)),
        )
        con.commit()
        rid = cur.lastrowid or con.execute(
            "SELECT id FROM wiba_projekte WHERE name=?", (name.strip(),)).fetchone()[0]
        # firmen_id per Name-Match nachziehen (best effort)
        try:
            from shared.firmen_link import firmen_db_path, firmen_name_to_id
            if unternehmen.strip():
                fid = firmen_name_to_id(firmen_db_path(Path(db_path))).get(
                    unternehmen.strip().casefold())
                if fid:
                    con.execute("UPDATE wiba_projekte SET firmen_id=? WHERE name=?",
                                (fid, name.strip()))
                    con.commit()
        except Exception:
            pass
        return int(rid)
    finally:
        con.close()


def update_projekt_meta(db_path: Path, name: str, meta: dict) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute(
            "UPDATE wiba_projekte SET meta_json=?, updated_at=aics_now() WHERE name=?",
            (json.dumps(meta or {}, ensure_ascii=False), name))
        con.commit()
    finally:
        con.close()


def delete_projekt(db_path: Path, name: str) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM wiba_antworten WHERE projekt_name=?", (name,))
        con.execute("DELETE FROM wiba_projekte WHERE name=?", (name,))
        con.commit()
    finally:
        con.close()


def _projekt_to_dict(r: Any) -> dict[str, Any]:
    d = dict(r)
    try:
        d["meta"] = json.loads(d.get("meta_json") or "{}")
    except Exception:
        d["meta"] = {}
    return d


# ── Antworten ───────────────────────────────────────────────────────────────

def load_antworten(db_path: Path, projekt_name: str) -> dict[str, dict[str, Any]]:
    """``{control_id: {status, notiz, verantwortlich, zieldatum, evidence_doc_ids}}``."""
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM wiba_antworten WHERE projekt_name=?", (projekt_name,)).fetchall()
        out: dict[str, dict[str, Any]] = {}
        for r in rows:
            d = dict(r)
            try:
                d["evidence_doc_ids"] = json.loads(d.get("evidence_doc_ids") or "[]")
            except Exception:
                d["evidence_doc_ids"] = []
            out[d["control_id"]] = d
        return out
    finally:
        con.close()


def save_antwort(db_path: Path, projekt_name: str, control_id: str, *,
                 status: str | None = None, notiz: str = "",
                 verantwortlich: str = "", zieldatum: str = "",
                 evidence_doc_ids: list | None = None) -> None:
    ensure_db(db_path)
    if not control_id:
        raise ValueError("'control_id' ist Pflicht")
    st = normalize_status(status)
    con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO wiba_antworten
                 (projekt_name, control_id, status, notiz, verantwortlich, zieldatum, evidence_doc_ids)
               VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(projekt_name, control_id) DO UPDATE SET
                 status=excluded.status, notiz=excluded.notiz,
                 verantwortlich=excluded.verantwortlich, zieldatum=excluded.zieldatum,
                 evidence_doc_ids=excluded.evidence_doc_ids,
                 updated_at=aics_now()""",
            (projekt_name, control_id, st, notiz, verantwortlich, zieldatum,
             json.dumps(evidence_doc_ids or [], ensure_ascii=False)),
        )
        con.commit()
    finally:
        con.close()


# ── Katalog (Themen + Prüffragen) ─────────────────────────────────────────────

def list_themen(db_path: Path) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        return [dict(r) for r in con.execute(
            "SELECT * FROM wiba_themen ORDER BY reihenfolge, titel")]
    finally:
        con.close()


def list_prueffragen(db_path: Path, theme_key: str | None = None) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        if theme_key:
            rows = con.execute(
                "SELECT * FROM wiba_prueffragen WHERE theme_key=? ORDER BY nr",
                (theme_key,))
        else:
            rows = con.execute("SELECT * FROM wiba_prueffragen ORDER BY theme_key, nr")
        return [dict(r) for r in rows]
    finally:
        con.close()


def catalog_meta(db_path: Path) -> dict[str, Any]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        r = con.execute("SELECT * FROM wiba_catalog_meta WHERE id=1").fetchone()
        anzahl = con.execute("SELECT COUNT(*) FROM wiba_prueffragen").fetchone()[0]
        themen = con.execute("SELECT COUNT(*) FROM wiba_themen").fetchone()[0]
        meta = dict(r) if r else {}
        meta.update({"anzahl_prueffragen": anzahl, "anzahl_themen": themen})
        return meta
    finally:
        con.close()


def replace_catalog(db_path: Path, themen: list[dict], prueffragen: list[dict],
                    *, version: str = "", quelle: str = "") -> dict[str, int]:
    """Katalog vollständig ersetzen (idempotenter Re-Import / Update).

    Antworten der Projekte (``wiba_antworten``) bleiben unangetastet.
    """
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM wiba_prueffragen")
        con.execute("DELETE FROM wiba_themen")
        for t in themen:
            con.execute(
                """INSERT INTO wiba_themen
                     (theme_key, titel, bausteine, ziel, hinweis, weiterfuehrend, reihenfolge)
                   VALUES(?,?,?,?,?,?,?)""",
                (t["theme_key"], t.get("titel", ""), t.get("bausteine", ""),
                 t.get("ziel", ""), t.get("hinweis", ""), t.get("weiterfuehrend", ""),
                 int(t.get("reihenfolge", 0) or 0)),
            )
        for p in prueffragen:
            con.execute(
                """INSERT INTO wiba_prueffragen
                     (control_id, theme_key, nr, frage, hilfsmittel, aufwand)
                   VALUES(?,?,?,?,?,?)""",
                (p["control_id"], p["theme_key"], int(p.get("nr", 0) or 0),
                 p.get("frage", ""), p.get("hilfsmittel", ""), str(p.get("aufwand", ""))),
            )
        con.execute(
            """INSERT INTO wiba_catalog_meta(id, version, quelle, anzahl, imported_at)
               VALUES(1, ?, ?, ?, aics_now())
               ON CONFLICT(id) DO UPDATE SET
                 version=excluded.version, quelle=excluded.quelle,
                 anzahl=excluded.anzahl, imported_at=excluded.imported_at""",
            (version, quelle, len(prueffragen)),
        )
        con.commit()
        return {"themen": len(themen), "prueffragen": len(prueffragen)}
    finally:
        con.close()


# ── Reifegrad ─────────────────────────────────────────────────────────────────

def compute_reifegrad(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """Reifegrad gesamt + je Thema (ja=100, nein/offen=0, nicht_relevant exkl.)."""
    themen = list_themen(db_path)
    fragen = list_prueffragen(db_path)
    antworten = load_antworten(db_path, projekt_name)

    per_theme: dict[str, dict[str, Any]] = {
        t["theme_key"]: {"titel": t["titel"], "total": 0, "ja": 0, "nein": 0,
                         "offen": 0, "nicht_relevant": 0, "pct": 0.0}
        for t in themen
    }
    g_sum = 0.0
    g_scope = 0       # in-Scope (ja+nein+offen) = Nenner des Reifegrads
    g_beantwortet = 0  # tatsächlich beantwortet (ja+nein)
    for f in fragen:
        tk = f["theme_key"]
        bucket = per_theme.setdefault(
            tk, {"titel": tk, "total": 0, "ja": 0, "nein": 0, "offen": 0,
                 "nicht_relevant": 0, "pct": 0.0})
        a = antworten.get(f["control_id"], {})
        st = normalize_status(a.get("status"))
        bucket["total"] += 1
        bucket[st] = bucket.get(st, 0) + 1
        pct = reifegrad_pct(st)
        if pct is not None:  # in Scope (offen zählt mit 0 %)
            bucket["_sum"] = bucket.get("_sum", 0.0) + pct
            bucket["_scope"] = bucket.get("_scope", 0) + 1
            g_sum += pct
            g_scope += 1
            if st != "offen":
                g_beantwortet += 1
    for b in per_theme.values():
        scope = b.pop("_scope", 0)
        s = b.pop("_sum", 0.0)
        b["pct"] = round(s / scope, 1) if scope else 0.0
    return {
        "gesamt_pct": round(g_sum / g_scope, 1) if g_scope else 0.0,
        "bewertet": g_beantwortet,
        "in_scope": g_scope,
        "themen": per_theme,
    }
