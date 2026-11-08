"""SQLite persistence for the Risikobewertung module."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from shared.audit import audit_event
from shared.redaction import redact_secrets
from security_utils import sanitize_untrusted_text

from shared import db as _sdb

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

CREATE TABLE IF NOT EXISTS rb_projekte (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    framework   TEXT NOT NULL DEFAULT 'TARA',
    beschreibung TEXT NOT NULL DEFAULT '',
    unternehmen TEXT NOT NULL DEFAULT '',
    produkt     TEXT NOT NULL DEFAULT '',
    berater     TEXT NOT NULL DEFAULT '',
    meta_json   TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT DEFAULT (aics_now()),
    updated_at  TEXT DEFAULT (aics_now())
);

CREATE TABLE IF NOT EXISTS rb_risiken (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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
    created_at   TEXT DEFAULT (aics_now()),
    updated_at   TEXT DEFAULT (aics_now())
);
CREATE INDEX IF NOT EXISTS idx_rb_risiken_projekt ON rb_risiken(projekt_name);

-- Append-only change log for versioning/audit trail
CREATE TABLE IF NOT EXISTS rb_change_log (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name TEXT NOT NULL,
    object_kind  TEXT NOT NULL,          -- 'projekt' | 'risk'
    object_id    INTEGER,                -- rb_risiken.id or NULL
    action       TEXT NOT NULL,          -- create|update|resolve|unresolve|delete
    before_json  TEXT NOT NULL DEFAULT '',
    after_json   TEXT NOT NULL DEFAULT '',
    created_at   TEXT DEFAULT (aics_now())
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
    con: Any,
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


def _connect(db_path: Path) -> Any:
    con = _sdb.connect(db_path)
    con.executescript(_DDL)
    # Migrations for older DBs (Postgres: ADD COLUMN IF NOT EXISTS)
    for stmt in [
        "ALTER TABLE rb_projekte ADD COLUMN IF NOT EXISTS meta_json TEXT NOT NULL DEFAULT '{}' ",
        # Issue #428: Konsistenz mit cra/nis2/dsgvo/aiact-Schema
        "ALTER TABLE rb_projekte ADD COLUMN IF NOT EXISTS unternehmen TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE rb_projekte ADD COLUMN IF NOT EXISTS produkt TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE rb_projekte ADD COLUMN IF NOT EXISTS berater TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE rb_risiken ADD COLUMN IF NOT EXISTS is_resolved INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE rb_risiken ADD COLUMN IF NOT EXISTS resolved_at TEXT",
        "ALTER TABLE rb_risiken ADD COLUMN IF NOT EXISTS resolved_reason TEXT NOT NULL DEFAULT ''",
        # #1608/#1613: formale Risikobehandlung + CRA-Akzeptanz (ISO 27005)
        "ALTER TABLE rb_risiken ADD COLUMN IF NOT EXISTS behandlung TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE rb_risiken ADD COLUMN IF NOT EXISTS akzeptanz_kategorie TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE rb_risiken ADD COLUMN IF NOT EXISTS akzeptanz_grund TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE rb_risiken ADD COLUMN IF NOT EXISTS akzeptanz_von TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE rb_risiken ADD COLUMN IF NOT EXISTS akzeptanz_am TEXT",
        "ALTER TABLE rb_risiken ADD COLUMN IF NOT EXISTS akzeptanz_review TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE rb_risiken ADD COLUMN IF NOT EXISTS rechtsgrundlage TEXT NOT NULL DEFAULT ''",
        # S1 (#1071): logischer firmen_id-FK (NULL = nicht zugeordnet)
        "ALTER TABLE rb_projekte ADD COLUMN IF NOT EXISTS firmen_id INTEGER",
        "CREATE INDEX IF NOT EXISTS idx_rb_projekte_firmen ON rb_projekte(firmen_id)",
    ]:
        try:
            con.execute(stmt)
        except Exception:
            pass
    _migrate_auto_titel(con)
    return con


def _migrate_auto_titel(con: Any) -> None:
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
            "AND (TRIM(COALESCE(risk_name,'')) = '' OR risk_name ~ '^Risiko [0-9]+')"
        ).fetchall()
    except Exception:
        return
    for r in rows:
        name = r["risk_name"]
        # ~ '^Risiko [0-9]+' kann Nicht-Generika (z. B. 'Risiko 1 Foo') fangen
        # — die strikte Regex in is_generic_title() schützt diese.
        if not is_generic_title(name):
            continue
        titel = first_sentence_title(r["beschreibung"] or "")
        if not titel:
            continue
        con.execute(
            "UPDATE rb_risiken SET risk_name=?, updated_at=aics_now() WHERE id=?",
            (titel, r["id"]),
        )
    con.commit()


# ── Projekte ──────────────────────────────────────────────────────────────────

def list_projekte(db_path: Path) -> list[str]:
    con = _connect(db_path)
    rows = con.execute("SELECT name FROM rb_projekte ORDER BY LOWER(name)").fetchall()
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
        "SELECT * FROM rb_projekte WHERE unternehmen=? ORDER BY LOWER(name)",
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
           VALUES(?,?,?,?,?,?,?,aics_now())
           ON CONFLICT(name) DO UPDATE SET
              framework=excluded.framework,
              beschreibung=excluded.beschreibung,
              unternehmen=excluded.unternehmen,
              produkt=excluded.produkt,
              berater=excluded.berater,
              meta_json=excluded.meta_json,
              updated_at=aics_now()""",
        (name, framework, beschreibung, unternehmen, produkt, berater, json.dumps(meta or {}, ensure_ascii=False)),
    )
    con.commit()
    # #1511: firmen_id bei Anlage per Name-Match setzen (Risiko-Cockpit).
    try:
        from shared.firmen_link import assign_firmen_id_on_save
        assign_firmen_id_on_save(con, db_path, "rb_projekte", name, unternehmen)
    except Exception:
        pass
    after = load_projekt(db_path, name)
    _record_change(con, projekt_name=name, object_kind="projekt", object_id=None, action="update" if before else "create", before=before, after=after)
    con.close()


def update_projekt_meta(db_path: Path, name: str, meta: dict) -> None:
    """Nur die ``meta_json``-Spalte eines bestehenden Projekts aktualisieren.

    Genutzt für die CRA↔Risikobewertung-Verknüpfung (#880); bewahrt alle übrigen
    Felder und vermeidet einen vollen save_projekt-Roundtrip."""
    con = _connect(db_path)
    con.execute(
        "UPDATE rb_projekte SET meta_json=?, updated_at=aics_now() WHERE name=?",
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


def rename_projekt(db_path: Path, old_name: str, new_name: str) -> bool:
    """Benennt ein Projekt (Primärschlüssel ``rb_projekte.name``) inkl. aller
    referenzierenden Tabellen um. Idempotent/sicher:

    - ``old_name == new_name`` oder altes Projekt fehlt → kein-Op, ``False``.
    - existiert ``new_name`` bereits → kein Clobber, ``ValueError``.

    Genutzt für die Migration der DSFA↔Risikobewertung-Verknüpfung (#1116): der
    alte deterministische Name enthielt ein '/', das die URL-Routen brach.
    """
    if not old_name or not new_name or old_name == new_name:
        return False
    con = _connect(db_path)
    try:
        if con.execute("SELECT 1 FROM rb_projekte WHERE name=?", (old_name,)).fetchone() is None:
            return False
        if con.execute("SELECT 1 FROM rb_projekte WHERE name=?", (new_name,)).fetchone() is not None:
            raise ValueError(f"Zielprojekt existiert bereits: {new_name!r}")
        con.execute("UPDATE rb_projekte SET name=?, updated_at=aics_now() WHERE name=?", (new_name, old_name))
        for tbl in ("rb_risiken", "linked_issues", "rb_change_log"):
            # #1530: Existenz PRÜFEN statt try/except — unter PG abortiert ein
            # fehlgeschlagenes UPDATE (fehlende Tabelle) die gesamte Transaktion, sodass
            # das folgende commit() auch den rb_projekte-Rename verwirft (alter Name blieb).
            exists = con.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_name=? AND table_schema=current_schema()", (tbl,)).fetchone()
            if exists:
                con.execute(f"UPDATE {tbl} SET projekt_name=? WHERE projekt_name=?", (new_name, old_name))
        con.commit()
        return True
    finally:
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


def hat_erstbewertung(risk: dict) -> bool:
    """Wurde dieses Risiko mindestens einmal bewertet?

    Signal: ``felder`` ist ein nicht-leeres Dict ODER ``bewertung_text`` ist
    gesetzt. Genau diese Felder befüllen die (Initial-)Bewertungs-Pfade
    (Neubewertung/Stream, Massen-Apply, Editor); ein frisch angelegtes Risiko
    mit ``felder: {}`` und ohne Bewertungstext gilt daher als *nicht* bewertet.

    Stand bis v8.1.1 als ``_risk_has_initial_assessment`` in
    ``server/api/risikobewertung`` (#832) und wird seit #1846 auch vom
    CRA-Modul gebraucht — ein Risiko-Issue kann dort angelegt werden. Zwei
    Kopien derselben Frage wären zwei Antworten darauf.
    """
    felder = risk.get("felder") or {}
    if isinstance(felder, str):
        try:
            felder = json.loads(felder)
        except Exception:  # noqa: BLE001
            felder = {}
    if isinstance(felder, dict) and felder:
        return True
    return bool(str(risk.get("bewertung_text") or "").strip())


def _felder_mit_herkunft(neu: Any, bestand: Any) -> dict:
    """Herkunftsschlüssel überleben ein Teil-Update von ``felder`` (#1976).

    ``felder`` trägt zwei Dinge in einem JSON-Objekt: die **Bewertung** nach
    dem Framework (``octave_*``, ``impact_*`` …) und die **Herkunft** des
    Risikos unter Schlüsseln mit führendem ``_`` — ``_source``/``_source_id``
    aus `shared/req_risks` (Nichterfüllung einer Anforderung, #1564) und aus
    `cra/risk_import` (CVE, Threat-Model), ``_vorher`` aus dem
    Framework-Wechsel (#1577).

    Jeder Bewertungsweg schickt nur die Framework-Felder. Ein vollständiges
    Ersetzen löschte damit die Herkunft, und zwar beim **ersten** Speichern
    nach dem Anlegen: Die Bewertung eines Risikos nahm ihm seine Zuordnung.
    Gelesen wird die Zuordnung von `cra/konformitaet_gate._accepted_gap_for`
    (ob eine Abweichung begründet akzeptiert ist), von
    `cra/risk_import.provenance_key` (Dubletten-Erkennung bei CVE-Import) und
    von `cra/release_bericht` (Nachweis-Zuordnung) — es fiel nur nichts aus,
    es stand bloß eine falsche Aussage in der Akte.

    Dieselbe Fehlerklasse wie ``notizen`` (#1805), ``artefakt`` (#1771),
    ``meta_json`` (#1540) und ``aktuelle_version`` (#1820), und mit derselben
    Lehre: **Der Schutz gehört in die Speicherfunktion, nicht in den
    Aufrufer.** Vierzehn Aufrufwege einzeln zu korrigieren wäre die
    Spiegel-Liste aus #1731/#1735 — beim fünfzehnten fehlte sie wieder.

    **Ausdrücklich mitgeschickt gewinnt** (Linie aus #1805): Der
    Framework-Wechsel setzt ``_vorher`` absichtlich, und ein Umhängen der
    Herkunft muss möglich bleiben. Übernommen wird nur, was der Aufrufer
    **nicht nennt**.
    """
    neu = neu if isinstance(neu, dict) else {}
    alt = bestand if isinstance(bestand, dict) else {}
    zusammen = dict(neu)
    for schluessel, wert in alt.items():
        if str(schluessel).startswith("_") and schluessel not in neu:
            zusammen[schluessel] = wert
    return zusammen


def setze_risiko_herkunft(db_path: Path, risk_id: int, *, source: str, source_id: str,
                          source_projekt: str = "") -> bool:
    """Herkunft eines Risikos nachtragen — **nur in einen leeren Platz** (#1965).

    Gebraucht beim Verknüpfen eines **vorhandenen** Risikos mit einer
    Anforderung (`shared/req_risks.link_risk`, der Weg aus #1564). Bis v8.6.2
    schrieb nur das *Anlegen* eines Nichterfüllungs-Risikos ``_source_id``;
    das Verknüpfen legte allein eine Zeile in ``risk_requirement_links`` —
    und die liest ``cra/konformitaet_gate._accepted_gap_for`` nicht. Eine
    Akzeptanz an einem so verknüpften Risiko zählte deshalb nicht, ohne dass
    etwas fehlschlug: die Anforderung blieb ein offener Punkt.

    **Teil-Update** (die Lehre aus #1540/#1771/#1805): Berührt werden
    ausschließlich die drei Herkunftsschlüssel in ``felder_json``; die
    Bewertungsfelder des Frameworks bleiben, wie sie sind. ``save_risiko``
    taugt dafür nicht — es ist ein voller UPDATE über alle Spalten und würde
    Titel, Beschreibung und Bewertung des Aufrufers erwarten.

    **Ein gesetztes ``_source_id`` wird nie überschrieben**, und das ist der
    Kern: Der Schlüssel trägt die *Herkunft* des Risikos, nicht seine
    Zuordnung. Bei einem aus einem CVE oder einem Threat-Model entstandenen
    Risiko liest ``cra/risk_import.provenance_key`` ihn zur
    Dubletten-Erkennung und ``cra/release_bericht`` zur Nachweis-Zuordnung;
    ihn umzuhängen hieße, einen CVE beim nächsten Abgleich doppelt
    aufzunehmen. Dasselbe gilt für ein Risiko, das schon die Nichterfüllung
    einer *anderen* Anforderung trägt — ``felder`` hält genau eine Herkunft,
    die Verknüpfung ist n:m. Dass die Akzeptanz dann an der zweiten
    Anforderung **nicht** zählt, ist kein Nebenbefund, sondern wird vom Gate
    benannt (``_check_akzeptanz_nicht_gelesen``).

    Rückgabe: ``True``, wenn die Herkunft nachgetragen wurde; ``False``, wenn
    das Risiko fehlt oder schon eine trägt.
    """
    con = _connect(db_path)
    try:
        row = con.execute("SELECT * FROM rb_risiken WHERE id=?", (int(risk_id),)).fetchone()
        if not row:
            return False
        before = dict(row)
        try:
            felder = json.loads(before.get("felder_json") or "{}") or {}
        except Exception:  # noqa: BLE001
            felder = {}
        if not isinstance(felder, dict):
            felder = {}
        if str(felder.get("_source_id") or "").strip():
            return False
        felder_vorher = dict(felder)
        felder["_source"] = felder.get("_source") or source
        felder["_source_id"] = source_id
        if source_projekt:
            felder["_source_projekt"] = felder.get("_source_projekt") or source_projekt
        con.execute(
            "UPDATE rb_risiken SET felder_json=?, updated_at=aics_now() WHERE id=?",
            (json.dumps(felder, ensure_ascii=False), int(risk_id)),
        )
        after_row = con.execute("SELECT * FROM rb_risiken WHERE id=?", (int(risk_id),)).fetchone()
        after = dict(after_row) if after_row else None
        # Wie in ``save_risiko``: das Änderungsprotokoll zeigt ``felder`` als
        # Objekt, nicht als JSON-Zeichenkette — sonst ist genau die Änderung,
        # um die es hier geht, im Protokoll nicht lesbar.
        before["felder"] = dict(felder_vorher)
        before.pop("felder_json", None)
        if after is not None:
            after["felder"] = dict(felder)
            after.pop("felder_json", None)
        _record_change(
            con,
            projekt_name=str(before.get("projekt_name") or ""),
            object_kind="risk",
            object_id=int(risk_id),
            action="update",
            before=before,
            after=after,
        )
        con.commit()
        return True
    finally:
        con.close()


def save_risiko(db_path: Path, risk: dict) -> int:
    """Insert or update a risk. Returns the row id."""
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
        # Die Herkunft wird aus dem Bestand übernommen, nicht vom Aufrufer erwartet.
        felder_json = json.dumps(
            _felder_mit_herkunft(risk.get("felder"), (before or {}).get("felder")),
            ensure_ascii=False)
        con.execute(
            """UPDATE rb_risiken SET
               nr=?, risk_name=?, beschreibung=?, framework=?,
               felder_json=?, risikowert=?, risiko_label=?, detail_text=?,
               bewertung_text=?, prompt_text=?, updated_at=aics_now()
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
        felder_json = json.dumps(risk.get("felder") or {}, ensure_ascii=False)
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
                "UPDATE rb_risiken SET is_resolved=1, resolved_at=aics_now(), resolved_reason=?, updated_at=aics_now() WHERE id=?",
                (reason or "", int(risk_id)),
            )
        else:
            con.execute(
                "UPDATE rb_risiken SET is_resolved=0, resolved_at=NULL, resolved_reason='', updated_at=aics_now() WHERE id=?",
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


# #1608/#1613: Formale Risikobehandlung inkl. CRA-konformer Akzeptanz.
BEHANDLUNGEN = ("offen", "reduziert", "akzeptiert", "vermieden", "uebertragen")
# Begründungskategorien für eine akzeptierte Abweichung (CRA-konform, #1613).
AKZEPTANZ_KATEGORIEN = ("nicht_anwendbar", "restrisiko", "kompensierend")


#: #1941 — Mindestlänge der Begründung für eine Rücknahme. Dieselbe Zahl wie
#: beim Testverzicht (#1824) und beim Verwerfen eines Release-Vorgangs (#1876):
#: Eine Entscheidung, die sich in weniger als zwanzig Zeichen begründen lässt,
#: ist nicht begründet.
RUECKNAHME_GRUND_MIN = 20

_RUECKNAHME_PREFIX = "↩️ Akzeptanz zurückgenommen"


def _ruecknahme_vermerk(grund: str, von: str) -> str:
    from datetime import date
    wer = (von or "").strip() or "unbekannt"
    return (f"{_RUECKNAHME_PREFIX} am {date.today().isoformat()} durch {wer} – "
            f"{grund.strip()}\n\n")


def set_risiko_behandlung(db_path: Path, risk_id: int, *, behandlung: str,
                          kategorie: str = "", grund: str = "", von: str = "",
                          review: str = "", rechtsgrundlage: str = "",
                          ruecknahme_grund: str = "") -> dict | None:
    """Setzt die Risikobehandlung. Für ``behandlung='akzeptiert'`` sind Kategorie +
    Grund Pflicht (CRA: begründete Abweichung statt pauschaler Akzeptanz).

    Bei ``akzeptiert`` wird das Risiko zugleich als ``is_resolved`` (Restrisiko
    behandelt) geführt; andere Behandlungen setzen die Akzeptanz-Felder zurück.

    #1941 — **Die Rücknahme einer Akzeptanz braucht eine Begründung.** Meldung
    aus dem Betrieb: Die Maske bot an der Anforderung keinen Rückweg (der Knopf
    „akzeptieren" verschwindet, sobald akzeptiert ist), also wurde die
    Verknüpfung gelöst — was die Akzeptanz nicht wegnimmt, weil das Gate
    ``felder._source_id`` liest und nicht die Verknüpfungstabelle. Am Ende
    wurden die Risiken gelöscht, und damit auch die Spur, dass die Lücke je
    abgewogen wurde.

    Verlangt wird die Begründung **nur** beim Verlassen einer bestehenden
    Akzeptanz. Der Wechsel von ``offen`` auf ``reduziert`` ist keine Rücknahme
    und bleibt unberührt — eine pauschale Pflicht hätte Bestandsaufrufe
    gebrochen, die nichts zurücknehmen."""
    behandlung = (behandlung or "offen").strip()
    if behandlung not in BEHANDLUNGEN:
        raise ValueError(f"Unbekannte Behandlung: {behandlung}")
    if behandlung == "akzeptiert":
        if kategorie not in AKZEPTANZ_KATEGORIEN:
            raise ValueError("Für eine Akzeptanz ist eine Begründungskategorie erforderlich.")
        if not (grund or "").strip():
            raise ValueError("Für eine Akzeptanz ist eine Begründung erforderlich.")
    con = _connect(db_path)
    try:
        before_row = con.execute("SELECT * FROM rb_risiken WHERE id=?", (int(risk_id),)).fetchone()
        if not before_row:
            return None
        war_akzeptiert = str(dict(before_row).get("behandlung") or "") == "akzeptiert"
        if war_akzeptiert and behandlung != "akzeptiert":
            if len((ruecknahme_grund or "").strip()) < RUECKNAHME_GRUND_MIN:
                raise ValueError(
                    "Für die Rücknahme einer Akzeptanz ist eine Begründung von "
                    f"mindestens {RUECKNAHME_GRUND_MIN} Zeichen erforderlich. "
                    "Die Rücknahme ist selbst eine Entscheidung und gehört in die Akte.")
        if behandlung == "akzeptiert":
            con.execute(
                "UPDATE rb_risiken SET behandlung=?, akzeptanz_kategorie=?, akzeptanz_grund=?, "
                "akzeptanz_von=?, akzeptanz_am=aics_now(), akzeptanz_review=?, rechtsgrundlage=?, "
                "is_resolved=1, resolved_at=aics_now(), resolved_reason=?, updated_at=aics_now() WHERE id=?",
                (behandlung, kategorie, grund, von, review, rechtsgrundlage,
                 f"Akzeptiert ({kategorie}): {grund}", int(risk_id)),
            )
        else:
            resolved = 1 if behandlung in ("reduziert", "vermieden", "uebertragen") else 0
            # #1941: `rechtsgrundlage` und `resolved_reason` wurden bisher NICHT
            # mitzurückgesetzt. Eine zurückgenommene Akzeptanz behielt damit ihre
            # Fundstelle und den Satz „Akzeptiert (restrisiko): …" — beides liest
            # sich wie eine Begründung für eine Entscheidung, die niemand mehr
            # trifft. Dieselbe Linie wie das Löschen des Verzichts in #1824.
            con.execute(
                "UPDATE rb_risiken SET behandlung=?, akzeptanz_kategorie='', akzeptanz_grund='', "
                "akzeptanz_von='', akzeptanz_am=NULL, akzeptanz_review='', rechtsgrundlage='', "
                "resolved_reason=CASE WHEN ?=0 THEN '' ELSE resolved_reason END, "
                "is_resolved=?, updated_at=aics_now() WHERE id=?",
                (behandlung, resolved, resolved, int(risk_id)),
            )
            if war_akzeptiert and ruecknahme_grund:
                # Die Spur, die das Löschen des Risikos zerstört hätte: dass eine
                # Akzeptanz bestand und von wem sie zurückgenommen wurde.
                vorher_text = str(dict(before_row).get("bewertung_text") or "")
                con.execute(
                    "UPDATE rb_risiken SET bewertung_text=? WHERE id=?",
                    (_ruecknahme_vermerk(ruecknahme_grund, von) + vorher_text, int(risk_id)),
                )
        after_row = con.execute("SELECT * FROM rb_risiken WHERE id=?", (int(risk_id),)).fetchone()
        con.commit()
        return dict(after_row) if after_row else None
    finally:
        con.close()
