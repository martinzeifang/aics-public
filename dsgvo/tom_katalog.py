"""DSGVO DS3+DS4 (#1103/#1104) — Strukturierter TOM-Katalog.

Self-contained area entlang der 7 SDM-Gewährleistungsziele + Art. 32 DSGVO.
Bewusst getrennt von der Legacy-Tabelle ``dsgvo_tom`` (in ``dsgvo/db.py``).

Pattern wie ``shared/templates/db.py``: ``ensure_table()`` läuft idempotent zu
Beginn jeder Lese-/Schreiboperation; CRUD-Funktionen reichen ``db_path`` durch.
Die SQLite-Verbindung wird über ``dsgvo.db._connect`` wiederverwendet
(``row_factory=Row`` ist dort bereits gesetzt).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from dsgvo.db import _connect

DB_PATH = Path('data/db/dsgvo.sqlite')

# Die 7 SDM-Gewährleistungsziele (Standard-Datenschutzmodell) + Art. 32.
ZIELE: list[str] = [
    'Datenminimierung',
    'Verfügbarkeit',
    'Integrität',
    'Vertraulichkeit',
    'Nichtverkettung',
    'Transparenz',
    'Intervenierbarkeit',
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS dsgvo_tom_katalog (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_name        TEXT NOT NULL,
    ziel                TEXT NOT NULL,
    massnahme_key       TEXT NOT NULL,
    titel               TEXT NOT NULL DEFAULT '',
    beschreibung        TEXT NOT NULL DEFAULT '',
    status              INTEGER NOT NULL DEFAULT 0,
    soll                INTEGER NOT NULL DEFAULT 5,
    verantwortlich      TEXT NOT NULL DEFAULT '',
    wirksamkeit_datum   TEXT NOT NULL DEFAULT '',
    wirksamkeit_ergebnis TEXT NOT NULL DEFAULT '',
    vvt_ref             TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(projekt_name, massnahme_key)
);
CREATE INDEX IF NOT EXISTS idx_tomkat_projekt ON dsgvo_tom_katalog(projekt_name);
CREATE INDEX IF NOT EXISTS idx_tomkat_ziel ON dsgvo_tom_katalog(projekt_name, ziel);
"""

# Standard-Maßnahmen-Katalog je Ziel (Seed). massnahme_key ist global eindeutig.
SEED_KATALOG: list[dict[str, str]] = [
    # Datenminimierung
    {'ziel': 'Datenminimierung', 'massnahme_key': 'DM-01',
     'titel': 'Erforderlichkeitsprüfung der Datenfelder',
     'beschreibung': 'Erhebung auf das für den Zweck erforderliche Minimum beschränken; Pflicht-/Wahlfelder dokumentieren.'},
    {'ziel': 'Datenminimierung', 'massnahme_key': 'DM-02',
     'titel': 'Pseudonymisierung / Anonymisierung',
     'beschreibung': 'Personenbezug reduzieren, wo der Zweck es zulässt (Art. 32 Abs. 1 lit. a).'},
    {'ziel': 'Datenminimierung', 'massnahme_key': 'DM-03',
     'titel': 'Lösch- und Aufbewahrungskonzept',
     'beschreibung': 'Definierte Aufbewahrungsfristen und automatisierte/regelmäßige Löschroutinen (Art. 5 Abs. 1 lit. e).'},
    # Verfügbarkeit
    {'ziel': 'Verfügbarkeit', 'massnahme_key': 'VF-01',
     'titel': 'Backup- und Restore-Konzept',
     'beschreibung': 'Regelmäßige, getestete Datensicherungen mit dokumentierten Wiederherstellungszeiten (Art. 32 Abs. 1 lit. c).'},
    {'ziel': 'Verfügbarkeit', 'massnahme_key': 'VF-02',
     'titel': 'Redundanz / Hochverfügbarkeit',
     'beschreibung': 'Ausfallsichere Auslegung kritischer Systeme (USV, Cluster, georedundante Standorte).'},
    {'ziel': 'Verfügbarkeit', 'massnahme_key': 'VF-03',
     'titel': 'Notfall- und Wiederanlaufplan (BCM)',
     'beschreibung': 'Dokumentierte Verfahren zur Wiederherstellung der Verfügbarkeit nach Zwischenfall (Art. 32 Abs. 1 lit. c).'},
    # Integrität
    {'ziel': 'Integrität', 'massnahme_key': 'IN-01',
     'titel': 'Eingabe- und Verarbeitungsprotokollierung',
     'beschreibung': 'Nachvollziehbare Protokolle über Eingabe, Änderung und Löschung von Daten.'},
    {'ziel': 'Integrität', 'massnahme_key': 'IN-02',
     'titel': 'Prüfsummen / Hashing',
     'beschreibung': 'Sicherstellung der Unverändertheit gespeicherter und übertragener Daten.'},
    {'ziel': 'Integrität', 'massnahme_key': 'IN-03',
     'titel': 'Schutz vor Schadsoftware',
     'beschreibung': 'Aktueller Malware-Schutz und Patch-Management zur Wahrung der Datenintegrität.'},
    # Vertraulichkeit
    {'ziel': 'Vertraulichkeit', 'massnahme_key': 'VT-01',
     'titel': 'Zugriffs- und Berechtigungskonzept',
     'beschreibung': 'Rollenbasierte Zugriffe nach Need-to-know, regelmäßige Rezertifizierung.'},
    {'ziel': 'Vertraulichkeit', 'massnahme_key': 'VT-02',
     'titel': 'Verschlüsselung at-rest und in-transit',
     'beschreibung': 'Verschlüsselung gespeicherter Daten und der Übertragungswege (TLS) (Art. 32 Abs. 1 lit. a).'},
    {'ziel': 'Vertraulichkeit', 'massnahme_key': 'VT-03',
     'titel': 'Physische Zutrittskontrolle',
     'beschreibung': 'Schutz der Räume/Server vor unbefugtem physischem Zutritt.'},
    # Nichtverkettung
    {'ziel': 'Nichtverkettung', 'massnahme_key': 'NV-01',
     'titel': 'Zweckbindung und logische Trennung',
     'beschreibung': 'Daten getrennt nach Verarbeitungszweck halten; keine zweckfremde Zusammenführung (Art. 5 Abs. 1 lit. b).'},
    {'ziel': 'Nichtverkettung', 'massnahme_key': 'NV-02',
     'titel': 'Mandantentrennung',
     'beschreibung': 'Technische/organisatorische Trennung von Datenbeständen unterschiedlicher Verantwortlicher.'},
    # Transparenz
    {'ziel': 'Transparenz', 'massnahme_key': 'TR-01',
     'titel': 'Verfahrensdokumentation (VVT)',
     'beschreibung': 'Verzeichnis von Verarbeitungstätigkeiten aktuell halten (Art. 30).'},
    {'ziel': 'Transparenz', 'massnahme_key': 'TR-02',
     'titel': 'Information der Betroffenen',
     'beschreibung': 'Datenschutzhinweise nach Art. 13/14 bereitstellen und aktuell halten.'},
    {'ziel': 'Transparenz', 'massnahme_key': 'TR-03',
     'titel': 'Protokollierung administrativer Tätigkeiten',
     'beschreibung': 'Nachvollziehbarkeit von Konfigurations- und Administrationsvorgängen.'},
    # Intervenierbarkeit
    {'ziel': 'Intervenierbarkeit', 'massnahme_key': 'IV-01',
     'titel': 'Betroffenenrechte-Prozess',
     'beschreibung': 'Verfahren für Auskunft, Berichtigung, Löschung, Einschränkung, Widerspruch (Art. 15–21).'},
    {'ziel': 'Intervenierbarkeit', 'massnahme_key': 'IV-02',
     'titel': 'Datenportabilität',
     'beschreibung': 'Bereitstellung von Daten in strukturiertem, gängigem Format (Art. 20).'},
    {'ziel': 'Intervenierbarkeit', 'massnahme_key': 'IV-03',
     'titel': 'Einwilligungs- und Widerrufsmanagement',
     'beschreibung': 'Erteilung und Widerruf von Einwilligungen nachweisbar verwalten (Art. 7 Abs. 3).'},
]

_COLUMNS = [
    'titel', 'beschreibung', 'status', 'soll', 'verantwortlich',
    'wirksamkeit_datum', 'wirksamkeit_ergebnis', 'vvt_ref',
]


def ensure_table(db_path: Path = DB_PATH) -> None:
    """Legt Tabelle + Indizes idempotent an."""
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def _row_to_dict(r: sqlite3.Row) -> dict[str, Any]:
    return dict(r)


def list_massnahmen(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    """Alle Katalog-Maßnahmen eines Projekts (sortiert nach Ziel-Reihenfolge)."""
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        rows = con.execute(
            "SELECT * FROM dsgvo_tom_katalog WHERE projekt_name=?",
            (projekt_name,),
        ).fetchall()
    finally:
        con.close()
    items = [_row_to_dict(r) for r in rows]
    order = {z: i for i, z in enumerate(ZIELE)}
    items.sort(key=lambda x: (order.get(x['ziel'], 99), x['massnahme_key']))
    return items


def get_massnahme(db_path: Path, projekt_name: str, massnahme_key: str) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        r = con.execute(
            "SELECT * FROM dsgvo_tom_katalog WHERE projekt_name=? AND massnahme_key=?",
            (projekt_name, massnahme_key),
        ).fetchone()
    finally:
        con.close()
    return _row_to_dict(r) if r is not None else None


def upsert_massnahme(db_path: Path, projekt_name: str, data: dict[str, Any]) -> dict[str, Any]:
    """Legt eine Maßnahme an oder aktualisiert sie (idempotent über massnahme_key)."""
    ensure_table(db_path)
    key = str(data.get('massnahme_key', '')).strip()
    if not key:
        raise ValueError('massnahme_key erforderlich')
    ziel = str(data.get('ziel', '')).strip()
    if ziel and ziel not in ZIELE:
        raise ValueError(f'unbekanntes Ziel: {ziel}')

    status = int(data.get('status', 0) or 0)
    status = max(0, min(5, status))
    soll = int(data.get('soll', 5) or 0)
    soll = max(0, min(5, soll))

    con = _connect(Path(db_path))
    try:
        existing = con.execute(
            "SELECT id, ziel FROM dsgvo_tom_katalog WHERE projekt_name=? AND massnahme_key=?",
            (projekt_name, key),
        ).fetchone()
        if existing is None:
            con.execute(
                """INSERT INTO dsgvo_tom_katalog
                   (projekt_name, ziel, massnahme_key, titel, beschreibung, status, soll,
                    verantwortlich, wirksamkeit_datum, wirksamkeit_ergebnis, vvt_ref)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    projekt_name,
                    ziel or 'Datenminimierung',
                    key,
                    str(data.get('titel', '')),
                    str(data.get('beschreibung', '')),
                    status,
                    soll,
                    str(data.get('verantwortlich', '')),
                    str(data.get('wirksamkeit_datum', '')),
                    str(data.get('wirksamkeit_ergebnis', '')),
                    str(data.get('vvt_ref', '')),
                ),
            )
        else:
            con.execute(
                """UPDATE dsgvo_tom_katalog
                   SET ziel=?, titel=?, beschreibung=?, status=?, soll=?, verantwortlich=?,
                       wirksamkeit_datum=?, wirksamkeit_ergebnis=?, vvt_ref=?,
                       updated_at=datetime('now')
                   WHERE projekt_name=? AND massnahme_key=?""",
                (
                    ziel or existing['ziel'],
                    str(data.get('titel', '')),
                    str(data.get('beschreibung', '')),
                    status,
                    soll,
                    str(data.get('verantwortlich', '')),
                    str(data.get('wirksamkeit_datum', '')),
                    str(data.get('wirksamkeit_ergebnis', '')),
                    str(data.get('vvt_ref', '')),
                    projekt_name,
                    key,
                ),
            )
        con.commit()
    finally:
        con.close()
    result = get_massnahme(db_path, projekt_name, key)
    assert result is not None
    return result


def set_wirksamkeit(
    db_path: Path,
    projekt_name: str,
    massnahme_key: str,
    datum: str,
    ergebnis: str,
    status: int | None = None,
) -> dict[str, Any] | None:
    """Wirksamkeitsprüfung dokumentieren (Datum + Ergebnis, optional Status anheben)."""
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        if status is None:
            con.execute(
                """UPDATE dsgvo_tom_katalog
                   SET wirksamkeit_datum=?, wirksamkeit_ergebnis=?, updated_at=datetime('now')
                   WHERE projekt_name=? AND massnahme_key=?""",
                (str(datum), str(ergebnis), projekt_name, massnahme_key),
            )
        else:
            st = max(0, min(5, int(status)))
            con.execute(
                """UPDATE dsgvo_tom_katalog
                   SET wirksamkeit_datum=?, wirksamkeit_ergebnis=?, status=?, updated_at=datetime('now')
                   WHERE projekt_name=? AND massnahme_key=?""",
                (str(datum), str(ergebnis), st, projekt_name, massnahme_key),
            )
        con.commit()
    finally:
        con.close()
    return get_massnahme(db_path, projekt_name, massnahme_key)


def delete_massnahme(db_path: Path, projekt_name: str, massnahme_key: str) -> bool:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        cur = con.execute(
            "DELETE FROM dsgvo_tom_katalog WHERE projekt_name=? AND massnahme_key=?",
            (projekt_name, massnahme_key),
        )
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def seed_projekt(db_path: Path, projekt_name: str, *, force: bool = False) -> int:
    """Standard-Maßnahmenkatalog in ein Projekt einspielen.

    Idempotent: bestehende massnahme_key bleiben unangetastet (manuelle Bewertung
    geht nicht verloren), nur fehlende Einträge werden ergänzt. Mit ``force`` wird
    auch Titel/Beschreibung/Ziel bestehender Seed-Einträge auf den Stand gebracht
    (Status/Soll/Wirksamkeit bleiben dennoch erhalten).
    """
    ensure_table(db_path)
    existing = {m['massnahme_key'] for m in list_massnahmen(db_path, projekt_name)}
    inserted = 0
    con = _connect(Path(db_path))
    try:
        for entry in SEED_KATALOG:
            key = entry['massnahme_key']
            if key in existing:
                if force:
                    con.execute(
                        """UPDATE dsgvo_tom_katalog
                           SET ziel=?, titel=?, beschreibung=?, updated_at=datetime('now')
                           WHERE projekt_name=? AND massnahme_key=?""",
                        (entry['ziel'], entry['titel'], entry['beschreibung'],
                         projekt_name, key),
                    )
                continue
            con.execute(
                """INSERT INTO dsgvo_tom_katalog
                   (projekt_name, ziel, massnahme_key, titel, beschreibung, status, soll)
                   VALUES (?,?,?,?,?,0,5)""",
                (projekt_name, entry['ziel'], key, entry['titel'], entry['beschreibung']),
            )
            inserted += 1
        con.commit()
    finally:
        con.close()
    return inserted


def ki_vorschlag(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """KI-Vorschlag-Stub: heuristische Empfehlungen für nicht/teilbewertete Ziele.

    Liefert (ohne externen LLM-Call) je untererfülltem Ziel einen Hinweistext.
    Echte KI-Anbindung folgt; bewusst als Stub gehalten (#1104).
    """
    items = list_massnahmen(db_path, projekt_name)
    by_ziel: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        by_ziel.setdefault(it['ziel'], []).append(it)

    vorschlaege: list[dict[str, Any]] = []
    for ziel in ZIELE:
        ms = by_ziel.get(ziel, [])
        if not ms:
            vorschlaege.append({
                'ziel': ziel,
                'empfehlung': f'Für das Ziel „{ziel}" sind noch keine Maßnahmen erfasst. '
                              f'Katalog seeden und mindestens eine Maßnahme bewerten.',
                'prioritaet': 'hoch',
            })
            continue
        luecken = [m for m in ms if int(m['status']) < int(m['soll'])]
        if luecken:
            namen = ', '.join(m['titel'] or m['massnahme_key'] for m in luecken[:3])
            vorschlaege.append({
                'ziel': ziel,
                'empfehlung': f'Ist < Soll bei: {namen}. Wirksamkeit prüfen und Maßnahmen ausbauen.',
                'prioritaet': 'mittel',
            })
    return {
        'projekt': projekt_name,
        'stub': True,
        'hinweis': 'KI-Vorschlag-Stub (#1104) — heuristisch, kein LLM-Call.',
        'vorschlaege': vorschlaege,
    }
