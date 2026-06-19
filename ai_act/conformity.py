"""AI-Act Art. 43/48 — Konformitätsbewertung + CE-Kennzeichnung (#1198).

Modelliert das Konformitätsbewertungsverfahren VOR Inverkehrbringen statt eines
unstrukturierten String-Felds:

- Verfahrensweg: interne Kontrolle (Annex VI, Annex III Nr. 2-8) oder notifizierte
  Stelle (Annex VII, Biometrie / Annex III Nr. 1);
- geführte Annex-VI-Selbstprüfungs-Checkliste (QMS + Annex-IV-TechDoc-Konsistenz);
- Notified-Body-Verwaltung (Name + Kennnummer) + Zertifikats-Upload (Annex VII);
- CE-Kennzeichnungs-Register (``ce_angebracht_am``);
- „wesentliche Änderung → erneute Bewertung"-Logik (Re-Assessment-Trigger);
- DoC-Gate: DoC erst ausstellbar, wenn der Bewertungsweg abgeschlossen ist.

Self-contained DB-Layer auf ``data/db/ai_act.sqlite`` (1 Zeile je Projekt).
Tabelle: ``aiact_conformity``.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_act.db import _connect, load_projekt, update_projekt_meta

DB_PATH = Path("data/db/ai_act.sqlite")
CERT_DIR = Path("data/aiact/conformity")
# CRA-DB für die optionale, read-only Verknüpfung (#1243). Separate SQLite-Datei →
# kein Cross-DB-FK; gelesen wird ausschließlich (nie geschrieben).
CRA_DB_PATH = Path("data/db/cra.sqlite")

VERFAHREN = {
    "annex_vi_intern": "Interne Kontrolle (Annex VI, Annex III Nr. 2-8)",
    "annex_vii_nb": "Notifizierte Stelle (Annex VII, Biometrie / Annex III Nr. 1)",
}

ERGEBNIS = ("offen", "konform", "nicht_konform")

# Annex-VI-Selbstprüfungs-Checkliste (interne Kontrolle).
CHECKLISTE_ANNEX_VI: list[dict[str, str]] = [
    {"key": "qms", "label": "Qualitätsmanagementsystem vorhanden (Art. 17)"},
    {"key": "techdoc", "label": "Technische Doku nach Annex IV vollständig (Art. 11)"},
    {"key": "techdoc_konsistenz", "label": "TechDoc konsistent mit System-Doku (A1)"},
    {"key": "design_dev", "label": "Design-/Entwicklungsprozess kontrolliert"},
    {"key": "post_market", "label": "Post-Market-Monitoring-Plan etabliert (Art. 72)"},
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS aiact_conformity (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name        TEXT NOT NULL UNIQUE,
    verfahren           TEXT NOT NULL DEFAULT 'annex_vi_intern',
    qms_geprueft        INTEGER NOT NULL DEFAULT 0,
    techdoc_geprueft    INTEGER NOT NULL DEFAULT 0,
    checkliste_json     TEXT NOT NULL DEFAULT '{}',
    notified_body_name  TEXT NOT NULL DEFAULT '',
    notified_body_kennnummer TEXT NOT NULL DEFAULT '',
    nb_zertifikat_datei TEXT NOT NULL DEFAULT '',
    nb_zertifikat_sha256 TEXT NOT NULL DEFAULT '',
    ergebnis            TEXT NOT NULL DEFAULT 'offen',
    bewertungsdatum     TEXT NOT NULL DEFAULT '',
    ce_angebracht_am    TEXT NOT NULL DEFAULT '',
    wesentliche_aenderung_seit TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL DEFAULT (aics_now()),
    updated_at          TEXT NOT NULL DEFAULT (aics_now())
);
CREATE INDEX IF NOT EXISTS idx_conformity_projekt ON aiact_conformity(projekt_name);
"""


def ensure_table(db_path: Path = DB_PATH) -> None:
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def verfahren_katalog() -> list[dict[str, str]]:
    return [{"code": k, "label": v} for k, v in VERFAHREN.items()]


def checkliste_katalog() -> list[dict[str, str]]:
    return [dict(c) for c in CHECKLISTE_ANNEX_VI]


def _empty(projekt_name: str) -> dict[str, Any]:
    return {
        "projekt_name": projekt_name,
        "verfahren": "annex_vi_intern",
        "qms_geprueft": False,
        "techdoc_geprueft": False,
        "checkliste": {},
        "notified_body_name": "",
        "notified_body_kennnummer": "",
        "nb_zertifikat_datei": "",
        "nb_zertifikat_sha256": "",
        "ergebnis": "offen",
        "bewertungsdatum": "",
        "ce_angebracht_am": "",
        "wesentliche_aenderung_seit": "",
    }


def _row_to_dict(r) -> dict[str, Any]:
    import json
    d = dict(r)
    d["qms_geprueft"] = bool(d.get("qms_geprueft"))
    d["techdoc_geprueft"] = bool(d.get("techdoc_geprueft"))
    try:
        d["checkliste"] = json.loads(d.get("checkliste_json", "{}") or "{}")
    except (ValueError, TypeError):
        d["checkliste"] = {}
    return d


def get(db_path: Path, projekt_name: str) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        r = con.execute(
            "SELECT * FROM aiact_conformity WHERE projekt_name=?", (projekt_name,)
        ).fetchone()
    finally:
        con.close()
    return _enrich(_row_to_dict(r)) if r else None


def get_or_empty(db_path: Path, projekt_name: str) -> dict[str, Any]:
    return get(db_path, projekt_name) or _enrich(_empty(projekt_name))


def _enrich(d: dict[str, Any]) -> dict[str, Any]:
    """Abgeleitete Felder: Bewertungs-Abschluss, CE-Erlaubnis, Re-Assessment."""
    verfahren = d.get("verfahren", "annex_vi_intern")
    if verfahren == "annex_vii_nb":
        # Annex VII: NB-Bewertung mit Kennnummer + Zertifikat muss vorliegen.
        assessment_complete = bool(
            d.get("ergebnis") == "konform"
            and d.get("notified_body_kennnummer")
            and d.get("nb_zertifikat_sha256")
        )
    else:
        assessment_complete = bool(
            d.get("ergebnis") == "konform"
            and d.get("qms_geprueft")
            and d.get("techdoc_geprueft")
        )
    # Re-Assessment-Trigger: wesentliche Änderung NACH dem Bewertungsdatum.
    reassessment_required = False
    wa = d.get("wesentliche_aenderung_seit", "")
    bd = d.get("bewertungsdatum", "")
    if wa and (not bd or wa >= bd):
        reassessment_required = True
        assessment_complete = False
    d["assessment_complete"] = assessment_complete
    d["reassessment_required"] = reassessment_required
    # DoC-Gate: DoC nur ausstellbar, wenn Bewertungsweg abgeschlossen + kein
    # offenes Re-Assessment.
    d["doc_allowed"] = bool(assessment_complete and not reassessment_required)
    return d


_TEXT_FIELDS = (
    "verfahren", "notified_body_name", "notified_body_kennnummer",
    "ergebnis", "bewertungsdatum", "ce_angebracht_am", "wesentliche_aenderung_seit",
)


def _validate(data: dict[str, Any]) -> tuple[dict[str, str], int, int, str]:
    import json
    verfahren = str(data.get("verfahren", "annex_vi_intern") or "annex_vi_intern")
    if verfahren not in VERFAHREN:
        raise ValueError(f"Unbekanntes Verfahren: {verfahren!r}")
    ergebnis = str(data.get("ergebnis", "offen") or "offen")
    if ergebnis not in ERGEBNIS:
        raise ValueError(f"Ungültiges Ergebnis: {ergebnis!r}")
    vals = {f: str(data.get(f, "") or "") for f in _TEXT_FIELDS}
    vals["verfahren"] = verfahren
    vals["ergebnis"] = ergebnis
    qms = 1 if data.get("qms_geprueft") else 0
    techdoc = 1 if data.get("techdoc_geprueft") else 0
    cl = data.get("checkliste")
    checkliste_json = json.dumps(cl if isinstance(cl, dict) else {}, ensure_ascii=False)
    return vals, qms, techdoc, checkliste_json


def save(db_path: Path, projekt_name: str, data: dict[str, Any]) -> dict[str, Any]:
    ensure_table(db_path)
    vals, qms, techdoc, checkliste_json = _validate(data)
    con = _connect(Path(db_path))
    try:
        con.execute(
            """INSERT INTO aiact_conformity
                 (projekt_name, verfahren, qms_geprueft, techdoc_geprueft,
                  checkliste_json, notified_body_name, notified_body_kennnummer,
                  ergebnis, bewertungsdatum, ce_angebracht_am, wesentliche_aenderung_seit)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(projekt_name) DO UPDATE SET
                 verfahren=excluded.verfahren,
                 qms_geprueft=excluded.qms_geprueft,
                 techdoc_geprueft=excluded.techdoc_geprueft,
                 checkliste_json=excluded.checkliste_json,
                 notified_body_name=excluded.notified_body_name,
                 notified_body_kennnummer=excluded.notified_body_kennnummer,
                 ergebnis=excluded.ergebnis,
                 bewertungsdatum=excluded.bewertungsdatum,
                 ce_angebracht_am=excluded.ce_angebracht_am,
                 wesentliche_aenderung_seit=excluded.wesentliche_aenderung_seit,
                 updated_at=aics_now()""",
            (projekt_name, vals["verfahren"], qms, techdoc, checkliste_json,
             vals["notified_body_name"], vals["notified_body_kennnummer"],
             vals["ergebnis"], vals["bewertungsdatum"], vals["ce_angebracht_am"],
             vals["wesentliche_aenderung_seit"]),
        )
        con.commit()
    finally:
        con.close()
    return get_or_empty(db_path, projekt_name)


def store_certificate(db_path: Path, projekt_name: str, filename: str,
                      content: bytes) -> dict[str, Any]:
    """NB-Zertifikat (PDF) ablegen + SHA-256 in der DB hinterlegen (Annex VII)."""
    ensure_table(db_path)
    sha = hashlib.sha256(content).hexdigest()
    target_dir = CERT_DIR / projekt_name
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename).name or "zertifikat.pdf"
    target = target_dir / safe_name
    target.write_bytes(content)
    con = _connect(Path(db_path))
    try:
        con.execute(
            """INSERT INTO aiact_conformity
                 (projekt_name, nb_zertifikat_datei, nb_zertifikat_sha256)
               VALUES (?,?,?)
               ON CONFLICT(projekt_name) DO UPDATE SET
                 nb_zertifikat_datei=excluded.nb_zertifikat_datei,
                 nb_zertifikat_sha256=excluded.nb_zertifikat_sha256,
                 updated_at=aics_now()""",
            (projekt_name, str(target), sha),
        )
        con.commit()
    finally:
        con.close()
    return get_or_empty(db_path, projekt_name)


def doc_gate(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """Gate-Status für die DoC-Ausstellung (Art. 47/48)."""
    rec = get_or_empty(db_path, projekt_name)
    return {
        "doc_allowed": rec["doc_allowed"],
        "assessment_complete": rec["assessment_complete"],
        "reassessment_required": rec["reassessment_required"],
        "verfahren": rec["verfahren"],
        "ergebnis": rec["ergebnis"],
        "ce_angebracht_am": rec.get("ce_angebracht_am", ""),
    }


# ── Optionale CRA-Verknüpfung (Art. 43/48 · CRA, #1243) ─────────────────────────
# Persistenz im Projekt-meta_json (kein neues Schema): ``linked_cra_projekt`` (Name
# des CRA-Projekts, "" = keine Verknüpfung) + ``cra_link_override`` (sticky-Flag:
# manuell überstimmt → CRA-Daten werden NIE automatisch referenziert). Default leer.


def _meta(db_path: Path, projekt_name: str) -> dict[str, Any]:
    p = load_projekt(db_path, projekt_name) or {}
    m = p.get("meta")
    return dict(m) if isinstance(m, dict) else {}


def get_cra_link(db_path: Path, projekt_name: str,
                 cra_db_path: Path | None = None) -> dict[str, Any]:
    """Liefert die CRA-Verknüpfung + (falls aktiv) die read-only CRA-CE/Konformitätsdaten.

    Grundfall: ``linked_cra_projekt`` leer ⇒ ``linked=False``, keine Referenz.
    ``manual_override=True`` ⇒ Verknüpfung wird ignoriert (keine Automatik-Übernahme).
    """
    meta = _meta(db_path, projekt_name)
    linked_cra = str(meta.get("linked_cra_projekt", "") or "")
    override = bool(meta.get("cra_link_override"))
    out: dict[str, Any] = {
        "linked": bool(linked_cra) and not override,
        "linked_cra_projekt": linked_cra,
        "manual_override": override,
        "cra_record": None,
    }
    if not linked_cra or override:
        return out
    # CRA-Konformitäts-Record(s) read-only übernehmen (nie schreiben).
    try:
        from cra.konformitaet_db import list_konformitaet
        recs = list_konformitaet(Path(cra_db_path or CRA_DB_PATH), linked_cra) or []
    except Exception:  # noqa: BLE001 — CRA-Modul/DB optional
        recs = []
    if recs:
        # Jüngsten Record referenzieren (list_konformitaet sortiert nach
        # release_version aufsteigend → letzter Eintrag, read-only Projektion).
        r = recs[-1]
        out["cra_record"] = {
            "release_version": r.get("release_version", ""),
            "bewertungsweg": r.get("bewertungsweg", ""),
            "produktklasse": r.get("produktklasse", ""),
            "ce_status": r.get("ce_status", ""),
            "nb_kennnummer": r.get("nb_kennnummer", ""),
            "bewertung_abgeschlossen": bool(r.get("bewertung_abgeschlossen")),
            "doc_ausgestellt": bool(r.get("doc_ausgestellt")),
            "freigabe_status": r.get("freigabe_status", "entwurf"),
        }
    return out


def set_cra_link(db_path: Path, projekt_name: str, *,
                 linked_cra_projekt: str | None = None,
                 manual_override: bool | None = None,
                 cra_db_path: Path | None = None) -> dict[str, Any]:
    """Setzt/löscht die optionale CRA-Verknüpfung. Beides additiv (None = unverändert)."""
    p = load_projekt(db_path, projekt_name)
    if not p:
        raise ValueError("Projekt nicht gefunden")
    meta = dict(p.get("meta") or {})
    if linked_cra_projekt is not None:
        meta["linked_cra_projekt"] = str(linked_cra_projekt or "")
    if manual_override is not None:
        meta["cra_link_override"] = bool(manual_override)
    update_projekt_meta(db_path, projekt_name, meta)
    return get_cra_link(db_path, projekt_name, cra_db_path)
