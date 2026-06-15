"""S15 (#1164) — Best-Effort-Migration von Freitext-Altbeständen in gemanagte
Dokumente.

Kopiert bestehende Freitext-Artefakte (z. B. ``aiact_system_doku.notizen`` mit
A8/A9-Abschnitten oder ``nis2_incident_response.kommunikationsplan``) idempotent
in ``<modul>_managed_docs``-Datensätze mit ``source='import'``. Die Originale
werden **nie** gelöscht oder verändert.

Idempotenz: Pro Projekt + ``doc_type`` wird höchstens ein ``import``-Dokument
angelegt; ein erneuter Lauf überspringt bereits vorhandene Importe.

Robustheit: fehlende Tabellen/Spalten führen nicht zu einem Fehler, sondern zu
``{"migrated": 0, "skipped": 0}``.
"""
from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from shared import db as _sdb

from .catalog import get_doc_spec
from .db import create_document, list_documents


# ── Hilfsfunktionen ────────────────────────────────────────────────────────────

def _table_exists(con: Any, table: str) -> bool:
    row = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema=current_schema() AND table_name=?",
        (table,),
    ).fetchone()
    return row is not None


def _columns(con: Any, table: str) -> set[str]:
    try:
        return {r[0] for r in con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema=current_schema() AND table_name=?",
            (table,))}
    except Exception:
        return set()


def _existing_import_doctypes(db_path: Path, modul: str, projekt: str) -> set[str]:
    """doc_types, für die bereits ein ``import``-Dokument existiert (Idempotenz)."""
    out: set[str] = set()
    try:
        for d in list_documents(db_path, modul, projekt, include_deleted=True):
            if (d.get("source") or "") == "import":
                out.add(d.get("doc_type") or "")
    except Exception:
        pass
    return out


def _titel(modul: str, doc_type: str, fallback: str) -> str:
    spec = get_doc_spec(modul, doc_type) or {}
    return str(spec.get("titel") or fallback)


def _as_pre(text: str) -> str:
    return "<pre>" + html.escape(text or "") + "</pre>"


# ── AI-Act ──────────────────────────────────────────────────────────────────────

# Marker, mit denen die A8/A9-Wizards ihre Ergebnisse in ``notizen`` anhängen
# (siehe server/api/aiact.py).
_AIACT_A8_MARKER = "--- EU-Konformitätserklärung ---"
_AIACT_A9_MARKER = "--- Transparenz-Hinweise (Art. 50) ---"


def _extract_section(notizen: str, marker: str) -> str:
    """Liefert den Text ab ``marker`` bis zum nächsten ``--- ... ---``-Marker."""
    idx = notizen.find(marker)
    if idx < 0:
        return ""
    start = idx + len(marker)
    rest = notizen[start:]
    # bis zum nächsten Marker (Zeile, die mit '---' beginnt) abschneiden
    end = rest.find("\n---")
    body = rest if end < 0 else rest[:end]
    return body.strip()


def migrate_aiact(db_path: Path | str) -> dict[str, int]:
    """Migriert A8/A9-Abschnitte aus ``aiact_system_doku.notizen``.

    Pro Projekt:
      - enthält ``notizen`` einen A8-/A9-Abschnitt → je ein gemanagtes Dokument
        (``konformitaetserklaerung`` / ``transparenzhinweise``).
      - sonst (notizen vorhanden, aber Struktur unklar) → ein ``import``-Dokument
        mit den rohen ``notizen`` als ``<pre>``-Inhalt
        (doc_type ``technische_doku_annex_iv``).
    Idempotent: bereits importierte doc_types werden übersprungen.
    """
    db_path = Path(db_path)
    modul = "ai_act"
    migrated = 0
    skipped = 0

    try:
        con = _sdb.connect(db_path)
    except Exception:
        return {"migrated": 0, "skipped": 0}
    try:
        if not _table_exists(con, "aiact_system_doku"):
            return {"migrated": 0, "skipped": 0}
        cols = _columns(con, "aiact_system_doku")
        if "notizen" not in cols or "projekt_name" not in cols:
            return {"migrated": 0, "skipped": 0}
        rows = con.execute(
            "SELECT projekt_name, notizen FROM aiact_system_doku"
        ).fetchall()
    except Exception:
        return {"migrated": 0, "skipped": 0}
    finally:
        con.close()

    for projekt_name, notizen in rows:
        projekt = (projekt_name or "").strip()
        text = (notizen or "").strip()
        if not projekt or not text:
            continue

        existing = _existing_import_doctypes(db_path, modul, projekt)

        a8 = _extract_section(text, _AIACT_A8_MARKER)
        a9 = _extract_section(text, _AIACT_A9_MARKER)
        produced_specific = False

        if a8:
            produced_specific = True
            dt = "konformitaetserklaerung"
            if dt in existing:
                skipped += 1
            else:
                create_document(
                    db_path, modul, projekt=projekt, doc_type=dt,
                    titel=_titel(modul, dt, "EU-Konformitätserklärung"),
                    content_html=_as_pre(a8), source="import")
                migrated += 1

        if a9:
            produced_specific = True
            dt = "transparenzhinweise"
            if dt in existing:
                skipped += 1
            else:
                create_document(
                    db_path, modul, projekt=projekt, doc_type=dt,
                    titel=_titel(modul, dt, "Transparenzhinweise"),
                    content_html=_as_pre(a9), source="import")
                migrated += 1

        if not produced_specific:
            # Struktur unklar → ein Roh-Import-Dokument pro Projekt
            dt = "technische_doku_annex_iv"
            if dt in existing:
                skipped += 1
            else:
                create_document(
                    db_path, modul, projekt=projekt, doc_type=dt,
                    titel=_titel(modul, dt, "Technische Dokumentation"),
                    content_html=_as_pre(text), source="import")
                migrated += 1

    return {"migrated": migrated, "skipped": skipped}


# ── NIS2 ────────────────────────────────────────────────────────────────────────

def migrate_nis2(db_path: Path | str) -> dict[str, int]:
    """Migriert ``nis2_incident_response.kommunikationsplan`` → ``incident_meldung``.

    Pro Projekt mit nicht-leerem ``kommunikationsplan`` wird ein gemanagtes
    Dokument (``source='import'``) angelegt. Idempotent.
    """
    db_path = Path(db_path)
    modul = "nis2"
    migrated = 0
    skipped = 0

    try:
        con = _sdb.connect(db_path)
    except Exception:
        return {"migrated": 0, "skipped": 0}
    try:
        if not _table_exists(con, "nis2_incident_response"):
            return {"migrated": 0, "skipped": 0}
        cols = _columns(con, "nis2_incident_response")
        if "kommunikationsplan" not in cols or "projekt_name" not in cols:
            return {"migrated": 0, "skipped": 0}
        rows = con.execute(
            "SELECT projekt_name, kommunikationsplan FROM nis2_incident_response"
        ).fetchall()
    except Exception:
        return {"migrated": 0, "skipped": 0}
    finally:
        con.close()

    dt = "incident_meldung"
    for projekt_name, plan in rows:
        projekt = (projekt_name or "").strip()
        text = (plan or "").strip()
        if not projekt or not text:
            continue
        if dt in _existing_import_doctypes(db_path, modul, projekt):
            skipped += 1
            continue
        create_document(
            db_path, modul, projekt=projekt, doc_type=dt,
            titel=_titel(modul, dt, "Incident-Meldung"),
            content_html=_as_pre(text), source="import")
        migrated += 1

    return {"migrated": migrated, "skipped": skipped}
