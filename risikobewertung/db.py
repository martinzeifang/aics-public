"""SQLite persistence for the Risikobewertung module."""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from shared.audit import audit_event
from shared.redaction import redact_secrets
from security_utils import sanitize_untrusted_text

from security_utils import safe_generated_file, workspace_root_from
from shared.db_security import connect_sqlite

# ── Auto-Titel aus Beschreibung (#832) ──────────────────────────────────────
# Generische Alt-Fallback-Titel, die als "kein manueller Titel" gelten und beim
# Backfill durch den ersten Satz der Beschreibung ersetzt werden dürfen.
_GENERIC_TITLE_RE = re.compile(r"^Risiko\s+\d+$")
# Satzende: . ! ? gefolgt von Whitespace/Ende; Zeilenumbruch beendet ebenfalls.
_SENTENCE_END_RE = re.compile(r"[.!?](?=\s|$)|\n")


def is_generic_title(risk_name: str | None) -> bool:
    """True, wenn kein manuell vergebener Titel vorliegt: leer/whitespace oder
    der alte Auto-Fallback `Risiko <nr>` (#832)."""
    s = (risk_name or "").strip()
    if not s:
        return True
    return bool(_GENERIC_TITLE_RE.match(s))


def first_sentence_title(beschreibung: str, max_len: int = 200) -> str:
    """Leitet einen Titel aus dem ERSTEN SATZ der Beschreibung ab (#832).

    Erster Satz = Text bis zum ersten Satzende-Zeichen (``.``, ``!``, ``?``),
    gefolgt von Whitespace/Ende, oder bis zum ersten Zeilenumbruch. Whitespace
    wird kollabiert, das Resultat auf ``max_len`` Zeichen begrenzt (Schnitt an
    Wortgrenze, ``…`` angehängt bei Kürzung). Leere Beschreibung → ''.
    """
    text = (beschreibung or "").strip()
    if not text:
        return ""
    m = _SENTENCE_END_RE.search(text)
    sentence = text[: m.start()] if m else text
    # Whitespace (inkl. Zeilenumbrüche) zu einzelnen Leerzeichen kollabieren.
    sentence = re.sub(r"\s+", " ", sentence).strip()
    if not sentence:
        return ""
    if len(sentence) <= max_len:
        return sentence
    # An Wortgrenze kürzen, dann … anhängen.
    cut = sentence[:max_len].rstrip()
    if " " in cut:
        cut = cut[: cut.rfind(" ")].rstrip()
    return (cut or sentence[:max_len].rstrip()) + "…"


_DDL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=-32000;

CREATE TABLE IF NOT EXISTS rb_projekte (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    framework   TEXT NOT NULL DEFAULT 'TARA',
    beschreibung TEXT NOT NULL DEFAULT '',
    unternehmen TEXT NOT NULL DEFAULT '',
    produkt     TEXT NOT NULL DEFAULT '',
    berater     TEXT NOT NULL DEFAULT '',
    meta_json   TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rb_risiken (
    id           INTEGER PRIMARY KEY,
    projekt_name TEXT NOT NULL,
    nr           INTEGER NOT NULL DEFAULT 0,
    risk_name    TEXT NOT NULL,
    beschreibung TEXT NOT NULL DEFAULT '',
    framework    TEXT NOT NULL DEFAULT '',
    felder_json  TEXT NOT NULL DEFAULT '{}',
    risikowert   INTEGER,
    risiko_label TEXT NOT NULL DEFAULT '',
    detail_text  TEXT NOT NULL DEFAULT '',
    bewertung_text TEXT NOT NULL DEFAULT '',
    prompt_text  TEXT NOT NULL DEFAULT '',
    is_resolved  INTEGER NOT NULL DEFAULT 0,
    resolved_at  TEXT,
    resolved_reason TEXT NOT NULL DEFAULT '',
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_rb_risiken_projekt ON rb_risiken(projekt_name);

-- Append-only change log for versioning/audit trail
CREATE TABLE IF NOT EXISTS rb_change_log (
    id           INTEGER PRIMARY KEY,
    projekt_name TEXT NOT NULL,
    object_kind  TEXT NOT NULL,          -- 'projekt' | 'risk'
    object_id    INTEGER,                -- rb_risiken.id or NULL
    action       TEXT NOT NULL,          -- create|update|resolve|unresolve|delete
    before_json  TEXT NOT NULL DEFAULT '',
    after_json   TEXT NOT NULL DEFAULT '',
    created_at   TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_rb_changelog_proj ON rb_change_log(projekt_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rb_changelog_obj ON rb_change_log(object_kind, object_id, created_at DESC);
"""


def _state_for_log(state: dict | None) -> str:
    """Serialize state for change log with redaction/truncation."""
    if not state:
        return ""
    try:
        # Copy and bound large text fields
        s = dict(state)
        for k in ("beschreibung", "detail_text", "bewertung_text", "prompt_text"):
            if k in s and s[k] is not None:
                s[k] = sanitize_untrusted_text(redact_secrets(str(s[k])), max_len=4000)
        # Bound nested felder
        if "felder" in s and isinstance(s["felder"], dict):
            s["felder"] = {str(k)[:80]: sanitize_untrusted_text(str(v), max_len=200) for k, v in list(s["felder"].items())[:100]}
        return json.dumps(s, ensure_ascii=False)
    except Exception:
        return ""


def _record_change(
    con: sqlite3.Connection,
    *,
    projekt_name: str,
    object_kind: str,
    object_id: int | None,
    action: str,
    before: dict | None,
    after: dict | None,
) -> None:
    con.execute(
        """INSERT INTO rb_change_log(projekt_name, object_kind, object_id, action, before_json, after_json)
           VALUES(?,?,?,?,?,?)""",
        (
            projekt_name,
            object_kind,
            int(object_id) if object_id is not None else None,
            action,
            _state_for_log(before),
            _state_for_log(after),
        ),
    )
    audit_event(
        "data.change",
        module="risikobewertung",
        outcome="success",
        details={"projekt": projekt_name, "object_kind": object_kind, "object_id": object_id, "action": action},
    )


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path = safe_generated_file(db_path, workspace_root_from(Path(__file__)))
    con = connect_sqlite(db_path, anchor=Path(__file__))
    con.row_factory = sqlite3.Row
    con.executescript(_DDL)
    # Migrations for older DBs
    for stmt in [
        "ALTER TABLE rb_projekte ADD COLUMN meta_json TEXT NOT NULL DEFAULT '{}' ",
        # Issue #428: Konsistenz mit cra/nis2/dsgvo/aiact-Schema
        "ALTER TABLE rb_projekte ADD COLUMN unternehmen TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE rb_projekte ADD COLUMN produkt TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE rb_projekte ADD COLUMN berater TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE rb_risiken ADD COLUMN is_resolved INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE rb_risiken ADD COLUMN resolved_at TEXT",
        "ALTER TABLE rb_risiken ADD COLUMN resolved_reason TEXT NOT NULL DEFAULT ''",
        # S1 (#1071): logischer firmen_id-FK (NULL = nicht zugeordnet)
        "ALTER TABLE rb_projekte ADD COLUMN firmen_id INTEGER",
        "CREATE INDEX IF NOT EXISTS idx_rb_projekte_firmen ON rb_projekte(firmen_id)",
    ]:
        try:
            con.execute(stmt)
        except sqlite3.OperationalError:
            pass
    _migrate_auto_titel(con)
    return con


def _migrate_auto_titel(con: sqlite3.Connection) -> None:
    """Backfill (#832): Risiken ohne manuellen Titel (leer ODER generisch
    `Risiko <nr>`) mit nicht-leerer Beschreibung erhalten als ``risk_name`` den
    ersten Satz der Beschreibung. Idempotent — generische/leere Titel, die kein
    sinnvolles Resultat liefern, bleiben unverändert; bereits abgeleitete Titel
    matchen das Generik-Muster nicht mehr und werden nicht erneut angefasst.
    """
    try:
        rows = con.execute(
            "SELECT id, risk_name, beschreibung FROM rb_risiken "
            "WHERE TRIM(COALESCE(beschreibung,'')) <> '' "
            "AND (TRIM(COALESCE(risk_name,'')) = '' OR risk_name GLOB 'Risiko [0-9]*')"
        ).fetchall()
    except sqlite3.OperationalError:
        return
    for r in rows:
        name = r["risk_name"]
        # GLOB 'Risiko [0-9]*' kann Nicht-Generika (z. B. 'Risiko 1 Foo') fangen
        # — die strikte Regex in is_generic_title() schützt diese.
        if not is_generic_title(name):
            continue
        titel = first_sentence_title(r["beschreibung"] or "")
        if not titel:
            continue
        con.execute(
            "UPDATE rb_risiken SET risk_name=?, updated_at=datetime('now') WHERE id=?",
            (titel, r["id"]),
        )
    con.commit()


# ── Projekte ──────────────────────────────────────────────────────────────────

def list_projekte(db_path: Path) -> list[str]:
    con = _connect(db_path)
    rows = con.execute("SELECT name FROM rb_projekte ORDER BY name COLLATE NOCASE").fetchall()
    con.close()
    return [r["name"] for r in rows]


def list_projekte_fuer_firma(db_path: Path, firma_name: str) -> list[dict]:
    """Issue #433: Alle Projekte zurueckliefern, deren `unternehmen` auf
    den uebergebenen Firmennamen zeigt. Liefert volle Records (nicht nur
    Namen), damit der Caller einen Counter, das Framework etc. anzeigen
    kann."""
    if not firma_name:
        return []
    con = _connect(db_path)
    rows = con.execute(
        "SELECT * FROM rb_projekte WHERE unternehmen=? ORDER BY name COLLATE NOCASE",
        (firma_name,),
    ).fetchall()
    con.close()
    out: list[dict] = []
    for r in rows:
        d = dict(r)
        try:
            d["meta"] = json.loads(d.get("meta_json", "{}") or "{}")
        except Exception:
            d["meta"] = {}
        out.append(d)
    return out


def save_projekt(
    db_path: Path,
    name: str,
    framework: str,
    beschreibung: str,
    *,
    meta: dict | None = None,
    unternehmen: str = "",
    produkt: str = "",
    berater: str = "",
) -> None:
    con = _connect(db_path)
    before = load_projekt(db_path, name)
    con.execute(
        """INSERT INTO rb_projekte(name, framework, beschreibung, unternehmen, produkt, berater, meta_json, updated_at)
           VALUES(?,?,?,?,?,?,?,datetime('now'))
           ON CONFLICT(name) DO UPDATE SET
              framework=excluded.framework,
              beschreibung=excluded.beschreibung,
              unternehmen=excluded.unternehmen,
              produkt=excluded.produkt,
              berater=excluded.berater,
              meta_json=excluded.meta_json,
              updated_at=datetime('now')""",
        (name, framework, beschreibung, unternehmen, produkt, berater, json.dumps(meta or {}, ensure_ascii=False)),
    )
    con.commit()
    after = load_projekt(db_path, name)
    _record_change(con, projekt_name=name, object_kind="projekt", object_id=None, action="update" if before else "create", before=before, after=after)
    con.close()


def update_projekt_meta(db_path: Path, name: str, meta: dict) -> None:
    """Nur die ``meta_json``-Spalte eines bestehenden Projekts aktualisieren.

    Genutzt für die CRA↔Risikobewertung-Verknüpfung (#880); bewahrt alle übrigen
    Felder und vermeidet einen vollen save_projekt-Roundtrip."""
    con = _connect(db_path)
    con.execute(
        "UPDATE rb_projekte SET meta_json=?, updated_at=datetime('now') WHERE name=?",
        (json.dumps(meta or {}, ensure_ascii=False), name),
    )
    con.commit()
    con.close()


def load_projekt(db_path: Path, name: str) -> dict | None:
    con = _connect(db_path)
    row = con.execute("SELECT * FROM rb_projekte WHERE name=?", (name,)).fetchone()
    con.close()
    if not row:
        return None
    d = dict(row)
    try:
        d["meta"] = json.loads(d.get("meta_json", "{}") or "{}")
    except Exception:
        d["meta"] = {}
    return d


def delete_projekt(db_path: Path, name: str) -> None:
    con = _connect(db_path)
    before = load_projekt(db_path, name)
    con.execute("DELETE FROM rb_risiken WHERE projekt_name=?", (name,))
    con.execute("DELETE FROM rb_projekte WHERE name=?", (name,))
    _record_change(con, projekt_name=name, object_kind="projekt", object_id=None, action="delete", before=before, after=None)
    con.commit()
    con.close()


# ── Risiken ───────────────────────────────────────────────────────────────────

def load_risiken(db_path: Path, projekt_name: str) -> list[dict]:
    con = _connect(db_path)
    rows = con.execute(
        "SELECT * FROM rb_risiken WHERE projekt_name=? ORDER BY nr, id",
        (projekt_name,),
    ).fetchall()
    con.close()
    result = []
    for r in rows:
        d = dict(r)
        d["felder"] = json.loads(d.pop("felder_json", "{}") or "{}")
        result.append(d)
    return result


def _auto_titel(risk: dict) -> str:
    """Liefert den zu speichernden Titel: manueller Titel hat Vorrang; bei
    leerem/generischem Titel wird der erste Satz der Beschreibung verwendet
    (#832). Bleibt auch dieser leer, wird der bisherige Wert beibehalten."""
    name = risk.get("risk_name", "") or ""
    if not is_generic_title(name):
        return name
    titel = first_sentence_title(risk.get("beschreibung", "") or "")
    return titel or name


def save_risiko(db_path: Path, risk: dict) -> int:
    """Insert or update a risk. Returns the row id."""
    felder_json = json.dumps(risk.get("felder", {}), ensure_ascii=False)
    con = _connect(db_path)
    rid = risk.get("id")
    if rid:
        before_row = con.execute("SELECT * FROM rb_risiken WHERE id=?", (int(rid),)).fetchone()
        before = dict(before_row) if before_row else None
        if before and "felder_json" in before:
            try:
                before["felder"] = json.loads(before.pop("felder_json", "{}") or "{}")
            except Exception:
                before["felder"] = {}
        con.execute(
            """UPDATE rb_risiken SET
               nr=?, risk_name=?, beschreibung=?, framework=?,
               felder_json=?, risikowert=?, risiko_label=?, detail_text=?,
               bewertung_text=?, prompt_text=?, updated_at=datetime('now')
               WHERE id=?""",
            (
                risk.get("nr", 0),
                risk.get("risk_name", ""),
                risk.get("beschreibung", ""),
                risk.get("framework", ""),
                felder_json,
                risk.get("risikowert"),
                risk.get("risiko_label", ""),
                risk.get("detail_text", ""),
                risk.get("bewertung_text", ""),
                risk.get("prompt_text", ""),
                rid,
            ),
        )
        after_row = con.execute("SELECT * FROM rb_risiken WHERE id=?", (int(rid),)).fetchone()
        after = dict(after_row) if after_row else None
        if after and "felder_json" in after:
            try:
                after["felder"] = json.loads(after.pop("felder_json", "{}") or "{}")
            except Exception:
                after["felder"] = {}
        _record_change(
            con,
            projekt_name=str(risk.get("projekt_name") or before.get("projekt_name") if before else ""),
            object_kind="risk",
            object_id=int(rid),
            action="update",
            before=before,
            after=after,
        )
    else:
        max_nr = con.execute(
            "SELECT COALESCE(MAX(nr),0) FROM rb_risiken WHERE projekt_name=?",
            (risk["projekt_name"],),
        ).fetchone()[0]
        nr = max_nr + 1
        cur = con.execute(
            """INSERT INTO rb_risiken(
               projekt_name, nr, risk_name, beschreibung, framework,
               felder_json, risikowert, risiko_label, detail_text, bewertung_text, prompt_text)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                risk["projekt_name"],
                nr,
                _auto_titel(risk),  # #832: erster Satz, falls kein manueller Titel
                risk.get("beschreibung", ""),
                risk.get("framework", ""),
                felder_json,
                risk.get("risikowert"),
                risk.get("risiko_label", ""),
                risk.get("detail_text", ""),
                risk.get("bewertung_text", ""),
                risk.get("prompt_text", ""),
            ),
        )
        rid = cur.lastrowid
        after_row = con.execute("SELECT * FROM rb_risiken WHERE id=?", (int(rid),)).fetchone()
        after = dict(after_row) if after_row else None
        if after and "felder_json" in after:
            try:
                after["felder"] = json.loads(after.pop("felder_json", "{}") or "{}")
            except Exception:
                after["felder"] = {}
        _record_change(
            con,
            projekt_name=str(risk.get("projekt_name") or ""),
            object_kind="risk",
            object_id=int(rid),
            action="create",
            before=None,
            after=after,
        )
    con.commit()
    con.close()
    return rid  # type: ignore[return-value]


def delete_risiko(db_path: Path, risk_id: int) -> None:
    con = _connect(db_path)
    row = con.execute("SELECT * FROM rb_risiken WHERE id=?", (risk_id,)).fetchone()
    if not row:
        con.close()
        return
    projekt = row["projekt_name"]
    before = dict(row)
    if "felder_json" in before:
        try:
            before["felder"] = json.loads(before.pop("felder_json", "{}") or "{}")
        except Exception:
            before["felder"] = {}
    con.execute("DELETE FROM rb_risiken WHERE id=?", (risk_id,))
    _record_change(con, projekt_name=str(projekt), object_kind="risk", object_id=int(risk_id), action="delete", before=before, after=None)
    # Renumber
    rows = con.execute(
        "SELECT id FROM rb_risiken WHERE projekt_name=? ORDER BY nr, id", (projekt,)
    ).fetchall()
    for i, r in enumerate(rows, start=1):
        con.execute("UPDATE rb_risiken SET nr=? WHERE id=?", (i, r["id"]))
    con.commit()
    con.close()


def bulk_insert_risiken(db_path: Path, projekt_name: str, risks: list[dict]) -> int:
    """Insert multiple risks at once. Returns count inserted."""
    con = _connect(db_path)
    max_nr = con.execute(
        "SELECT COALESCE(MAX(nr),0) FROM rb_risiken WHERE projekt_name=?", (projekt_name,)
    ).fetchone()[0]
    count = 0
    for i, r in enumerate(risks, start=max_nr + 1):
        felder_json = json.dumps(r.get("felder", {}), ensure_ascii=False)
        con.execute(
            """INSERT INTO rb_risiken(
               projekt_name, nr, risk_name, beschreibung, framework,
               felder_json, risikowert, risiko_label, detail_text, bewertung_text, prompt_text)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                projekt_name,
                i,
                _auto_titel(r),  # #832: erster Satz, falls kein manueller Titel
                r.get("beschreibung", ""),
                r.get("framework", ""),
                felder_json,
                r.get("risikowert"),
                r.get("risiko_label", ""),
                r.get("detail_text", ""),
                r.get("bewertung_text", ""),
                r.get("prompt_text", ""),
            ),
        )
        count += 1
    con.commit()
    con.close()
    return count


def set_risiko_resolved(db_path: Path, risk_id: int, *, resolved: bool, reason: str = "") -> None:
    con = _connect(db_path)
    try:
        before_row = con.execute("SELECT * FROM rb_risiken WHERE id=?", (int(risk_id),)).fetchone()
        before = dict(before_row) if before_row else None
        if before and "felder_json" in before:
            try:
                before["felder"] = json.loads(before.pop("felder_json", "{}") or "{}")
            except Exception:
                before["felder"] = {}
        if resolved:
            con.execute(
                "UPDATE rb_risiken SET is_resolved=1, resolved_at=datetime('now'), resolved_reason=?, updated_at=datetime('now') WHERE id=?",
                (reason or "", int(risk_id)),
            )
        else:
            con.execute(
                "UPDATE rb_risiken SET is_resolved=0, resolved_at=NULL, resolved_reason='', updated_at=datetime('now') WHERE id=?",
                (int(risk_id),),
            )
        after_row = con.execute("SELECT * FROM rb_risiken WHERE id=?", (int(risk_id),)).fetchone()
        after = dict(after_row) if after_row else None
        if after and "felder_json" in after:
            try:
                after["felder"] = json.loads(after.pop("felder_json", "{}") or "{}")
            except Exception:
                after["felder"] = {}
        proj = str((after or before or {}).get("projekt_name") or "")
        _record_change(
            con,
            projekt_name=proj,
            object_kind="risk",
            object_id=int(risk_id),
            action="resolve" if resolved else "unresolve",
            before=before,
            after=after,
        )
        con.commit()
    finally:
        con.close()
