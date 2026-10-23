"""CRA Art. 13(4) — Wesentliche Änderung + Release-Versionierung (#1208).

Bei einer wesentlichen Änderung gilt das Produkt als neu in Verkehr gebracht:
erneute Risiko- + Konformitätsbewertung, Aktualisierung techn. Doku + DoC.

Modell: eine ``cra_release``-Achse pro Projekt (aktive Produkt-Version) +
``cra_release_snapshot`` für eingefrorene Vorgänger-Versionen. Die Aktion
``substantial_modification`` friert die aktuelle Version als Snapshot ein und
setzt die Re-Assessment-Checkliste der neuen Version auf offen.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from shared import db as _sdb

DB_PATH = Path("data/db/cra.sqlite")

# Re-Assessment-Bausteine (Art. 13(4)).
REASSESS_ITEMS = ("risikobewertung", "konformitaetsbewertung", "technische_doku", "doc")


def _connect(db_path: Path) -> Any:
    """Postgres-Verbindung (Schema je Modul) über den zentralen Kompat-Layer (#1332)."""
    return _sdb.connect(db_path)


def ensure_table(db_path: Path = DB_PATH) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = _connect(db_path)
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS cra_release (
                id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                projekt_name    TEXT NOT NULL UNIQUE,
                aktuelle_version TEXT NOT NULL DEFAULT 'v1.0',
                reassess_json   TEXT NOT NULL DEFAULT '{}',   -- {baustein: 'offen'|'erledigt'}
                letzte_aenderung_am TEXT,
                letzte_aenderung_grund TEXT NOT NULL DEFAULT '',
                created_at      TEXT DEFAULT (aics_now()),
                updated_at      TEXT DEFAULT (aics_now())
            );
            CREATE TABLE IF NOT EXISTS cra_release_snapshot (
                id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                projekt_name    TEXT NOT NULL,
                version         TEXT NOT NULL,
                grund           TEXT NOT NULL DEFAULT '',
                snapshot_json   TEXT NOT NULL DEFAULT '{}',
                eingefroren_am  TEXT DEFAULT (aics_now())
            );
            CREATE INDEX IF NOT EXISTS idx_cra_release_snap_projekt
                ON cra_release_snapshot(projekt_name);
            """
        )
        # #1746 (v8.0.0): Phase 1 — die CRA-Ready-Feststellung. Sie gehört
        # hierher und nicht zu einem Release: Sie gilt fuer das PRODUKT. Diese
        # Tabelle ist der Singleton je Projekt und damit der richtige Ort.
        #
        # Warum ueberhaupt eine Feststellung? Bisher war Phase 1 nur ein
        # Rechenergebnis: Das Gate sagt gruen, und damit galt das Produkt als
        # marktfähig. Fuer einen Nachweis fehlt die Aussage eines Menschen —
        # wer hat wann auf welcher Datenlage erklärt, dass dieses Produkt
        # CRA-ready ist? Ohne sie beginnt das Tagesgeschäft auf einer Annahme.
        for ddl in (
            "ALTER TABLE cra_release ADD COLUMN IF NOT EXISTS bereit_status TEXT NOT NULL DEFAULT 'offen'",
            "ALTER TABLE cra_release ADD COLUMN IF NOT EXISTS bereit_von TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE cra_release ADD COLUMN IF NOT EXISTS bereit_am TEXT",
            "ALTER TABLE cra_release ADD COLUMN IF NOT EXISTS bereit_gate_json TEXT NOT NULL DEFAULT '{}'",
            "ALTER TABLE cra_release ADD COLUMN IF NOT EXISTS bereit_entzug_grund TEXT NOT NULL DEFAULT ''",
        ):
            con.execute(ddl)
        con.commit()
    finally:
        con.close()


#: Zustände der Phase-1-Feststellung.
BEREIT_STATUS = ("offen", "bereit", "entzogen")

#: Mindestlänge der Entzugs-Begründung (wie #1744).
MIN_GRUND = 10


def _row(r: Any) -> dict[str, Any]:
    d = dict(r)
    try:
        d["reassess"] = json.loads(d.get("reassess_json") or "{}")
    except Exception:
        d["reassess"] = {}
    try:
        d["bereit_gate"] = json.loads(d.get("bereit_gate_json") or "{}")
    except Exception:
        d["bereit_gate"] = {}
    d.setdefault("bereit_status", "offen")
    return d


def cra_ready_feststellen(db_path: Path, projekt_name: str, *, von: str,
                          gate: dict[str, Any]) -> dict[str, Any]:
    """#1746: Feststellen, dass das Produkt CRA-ready ist (CRA_APPROVE).

    Nur bei grüner Phase-1-Ampel. Der Rechenstand wird mitgeschrieben, damit
    später sichtbar bleibt, worauf sich die Feststellung bezog — ein grüneres
    oder roteres Heute sagt nichts darüber, was damals vorlag.
    """
    if (gate or {}).get("ampel") != "gruen":
        offen = [p.get("titel") for p in (gate or {}).get("offene_punkte", [])][:5]
        raise ValueError(
            "Feststellung nur bei grüner Ampel möglich. Offen: "
            + ("; ".join(str(o) for o in offen) if offen else "unbekannt"))
    ensure_table(db_path)
    get_release(db_path, projekt_name) or save_release(
        db_path, projekt_name, {"aktuelle_version": "v1.0"})
    con = _connect(db_path)
    try:
        con.execute(
            """UPDATE cra_release
                   SET bereit_status='bereit', bereit_von=?, bereit_am=aics_now(),
                       bereit_gate_json=?, bereit_entzug_grund='', updated_at=aics_now()
                   WHERE projekt_name=?""",
            (von or "", json.dumps(gate or {}, ensure_ascii=False), projekt_name),
        )
        con.commit()
    finally:
        con.close()
    return get_release(db_path, projekt_name)


def cra_ready_entziehen(db_path: Path, projekt_name: str, *, von: str,
                        grund: str) -> dict[str, Any]:
    """#1746: Feststellung zurücknehmen (CRA_APPROVE, Begründung Pflicht).

    Bewusst ein ausdrücklicher Schritt: Kippt die Ampel später, wird die
    Feststellung **nicht** stillschweigend gelöscht, sondern als überholt
    angezeigt (siehe ``bereit_ueberholt``). Eine menschliche Aussage darf ein
    Rechenlauf nicht entfernen — unwidersprochen stehenbleiben darf sie aber
    auch nicht.
    """
    if len((grund or "").strip()) < MIN_GRUND:
        raise ValueError(f"Begründung erforderlich (mindestens {MIN_GRUND} Zeichen)")
    rec = get_release(db_path, projekt_name)
    if not rec or rec.get("bereit_status") != "bereit":
        raise ValueError("Es liegt keine Feststellung vor, die entzogen werden könnte")
    con = _connect(db_path)
    try:
        con.execute(
            """UPDATE cra_release
                   SET bereit_status='entzogen', bereit_entzug_grund=?,
                       bereit_von=?, bereit_am=aics_now(), updated_at=aics_now()
                   WHERE projekt_name=?""",
            (grund.strip(), von or "", projekt_name),
        )
        con.commit()
    finally:
        con.close()
    return get_release(db_path, projekt_name)


def bereit_ueberholt(rec: dict[str, Any] | None, gate_jetzt: dict[str, Any]) -> bool:
    """Ist eine bestehende Feststellung durch den heutigen Stand überholt?

    Reine Funktion, damit sie ohne Datenbank testbar ist.
    """
    if not rec or rec.get("bereit_status") != "bereit":
        return False
    return (gate_jetzt or {}).get("ampel") != "gruen"


def get_release(db_path: Path, projekt_name: str) -> Optional[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        r = con.execute(
            "SELECT * FROM cra_release WHERE projekt_name=?", (projekt_name,)
        ).fetchone()
        return _row(r) if r else None
    finally:
        con.close()


def save_release(db_path: Path, projekt_name: str, data: dict) -> dict[str, Any]:
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO cra_release (projekt_name, aktuelle_version, reassess_json, updated_at)
               VALUES (?,?,?,aics_now())
               ON CONFLICT(projekt_name) DO UPDATE SET
                   aktuelle_version=excluded.aktuelle_version,
                   reassess_json=excluded.reassess_json,
                   updated_at=aics_now()""",
            (projekt_name, data.get("aktuelle_version", "v1.0"),
             json.dumps(data.get("reassess") or {}, ensure_ascii=False)),
        )
        con.commit()
    finally:
        con.close()
    return get_release(db_path, projekt_name)


def list_snapshots(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM cra_release_snapshot WHERE projekt_name=? "
            "ORDER BY eingefroren_am DESC, id DESC",
            (projekt_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def _collect_snapshot(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """Aktuellen Nachweis-Stand für den Snapshot einsammeln (best effort)."""
    snap: dict[str, Any] = {}
    try:
        from cra.db import load_bewertungen
        snap["bewertungen"] = load_bewertungen(db_path, projekt_name)
    except Exception:
        snap["bewertungen"] = {}
    try:
        from cra import konformitaet_db as kdb
        snap["konformitaet"] = kdb.list_konformitaet(db_path, projekt_name)
    except Exception:
        snap["konformitaet"] = []
    # #1609: erweiterter, reproduzierbarer Nachweis-Stand je Release.
    try:
        from cra.konformitaet_gate import evaluate
        snap["gate"] = evaluate(projekt_name)
    except Exception:
        snap["gate"] = {}
    try:
        from cra.traceability_db import annex_vii_status
        snap["annex_vii"] = annex_vii_status(db_path, projekt_name)
    except Exception:
        snap["annex_vii"] = {}
    try:
        from cra.db import list_vuln, list_sbom
        snap["vuln"] = list_vuln(db_path, projekt_name)
        snap["sbom"] = list_sbom(db_path, projekt_name)
    except Exception:
        snap["vuln"] = []; snap["sbom"] = []
    return snap


def snapshot_einfrieren(db_path: Path, projekt_name: str, version: str,
                        *, grund: str = "") -> dict[str, Any]:
    """#1744: Stand zu einer Release-Version einfrieren.

    Bisher entstand ein Snapshot nur bei einer wesentlichen Änderung
    (``substantial_modification``). Für einen Release-Nachweis ist das zu
    selten: Der Nachweis muss auf einen Stand zeigen, der sich nicht mehr
    bewegt — sonst belegt er bei der nächsten Änderung etwas anderes als am Tag
    der Freigabe. Deshalb friert jede Einreichung ein.

    Idempotent je Version: Eine erneute Einreichung derselben Version ersetzt
    den Snapshot, statt einen zweiten anzulegen.
    """
    ensure_table(db_path)
    snapshot = _collect_snapshot(db_path, projekt_name)
    con = _connect(db_path)
    try:
        con.execute(
            "DELETE FROM cra_release_snapshot WHERE projekt_name=? AND version=?",
            (projekt_name, version),
        )
        con.execute(
            """INSERT INTO cra_release_snapshot
                   (projekt_name, version, grund, snapshot_json)
               VALUES (?,?,?,?)""",
            (projekt_name, version, grund,
             json.dumps(snapshot, ensure_ascii=False)),
        )
        con.commit()
    finally:
        con.close()
    return {"version": version, "eingefroren": True,
            "snapshots": list_snapshots(db_path, projekt_name)}


def substantial_modification(db_path: Path, projekt_name: str, *,
                             neue_version: str, grund: str) -> dict[str, Any]:
    """Wesentliche Änderung erfassen: alte Version einfrieren, Re-Assessment öffnen."""
    ensure_table(db_path)
    rec = get_release(db_path, projekt_name) or save_release(
        db_path, projekt_name, {"aktuelle_version": "v1.0"})
    alte_version = rec.get("aktuelle_version", "v1.0")
    snapshot = _collect_snapshot(db_path, projekt_name)
    con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO cra_release_snapshot
                   (projekt_name, version, grund, snapshot_json)
               VALUES (?,?,?,?)""",
            (projekt_name, alte_version, grund,
             json.dumps(snapshot, ensure_ascii=False)),
        )
        reassess = {item: "offen" for item in REASSESS_ITEMS}
        con.execute(
            """UPDATE cra_release SET aktuelle_version=?, reassess_json=?,
                      letzte_aenderung_am=aics_now(), letzte_aenderung_grund=?,
                      updated_at=aics_now()
               WHERE projekt_name=?""",
            (neue_version, json.dumps(reassess, ensure_ascii=False), grund, projekt_name),
        )
        con.commit()
    finally:
        con.close()
    return {
        "release": get_release(db_path, projekt_name),
        "eingefrorene_version": alte_version,
        "snapshots": list_snapshots(db_path, projekt_name),
    }
