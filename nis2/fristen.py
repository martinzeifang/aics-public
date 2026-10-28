"""N-FRIST (#1213) — NIS2 Kontrollzyklus-/Wiedervorlage-Aggregation (Art. 21(2)f/27(4)).

Reine Auswertungs-/Dashboard-Schicht (KEINE neue Fachtabelle). Sammelt die
vorhandenen Datums-/Intervall-Felder aus den NIS2-Bereichen und berechnet je
Eintrag mit der **kanonischen** ``shared.deadlines``-Engine eine Ampel
(faellig/ueberfaellig):

- N2 Risiko-Register      → ``review_datum``        (Review-Wiedervorlage)
- N4 Supply-Chain         → ``review_datum`` / ``assessment_datum``
- N5 BCP                  → ``test_datum`` + ``test_frequenz`` (zyklischer Test)
- Bewertungen            → ``zieldatum``           (Maßnahmen-Zieltermin)
- Audit-Register (#1204)  → ``naechster_audit_soll`` (3-Jahres-Zyklus)
- Registrierung (#1203)   → ``naechste_jahres_bestaetigung``

Für zyklische Tests (N5) wird über ``deadlines.add_months_iso`` aus dem letzten
Testdatum + Frequenz der nächste Soll-Termin abgeleitet.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

DB_PATH = Path("data/db/nis2.sqlite")

# Test-/Review-Frequenz-Stichworte → Monate (für add_months_iso).
FREQ_MONATE = {
    "monatlich": 1, "monthly": 1,
    "quartalsweise": 3, "vierteljaehrlich": 3, "quarterly": 3,
    "halbjaehrlich": 6, "semi-annual": 6,
    "jaehrlich": 12, "jährlich": 12, "annual": 12, "yearly": 12,
    "zweijaehrlich": 24, "alle-2-jahre": 24,
    "dreijaehrlich": 36, "alle-3-jahre": 36,
}


def _freq_months(freq: str | None) -> int:
    return FREQ_MONATE.get((freq or "").strip().lower(), 12)


def _ampel_for(due_at: str, *, warn_days: float = 30.0) -> dict[str, Any]:
    """Ampel für einen einzelnen Soll-Termin (relativ zu jetzt)."""
    from shared import deadlines as dl
    base_dt = dl.parse_dt(due_at)
    if base_dt is None:
        return {"ampel": "grey", "status": "no_base", "due_at": due_at or "",
                "days_left": None}
    days_left = (base_dt - dl.now_utc()).total_seconds() / 86400.0
    if days_left < 0:
        status, ampel = "ueberfaellig", "red"
    elif days_left <= warn_days:
        status, ampel = "faellig", "amber"
    else:
        status, ampel = "on_track", "green"
    return {"ampel": ampel, "status": status, "due_at": base_dt.isoformat(),
            "days_left": round(days_left, 1)}


def collect_fristen(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """Aggregiert alle Wiedervorlagen/Kontrollzyklen eines Projekts.

    Returns {items:[...], counts:{ueberfaellig,faellig,on_track,grey},
             overall_ampel}.
    """
    from nis2 import db as ndb

    items: list[dict[str, Any]] = []

    def add(*, bereich: str, ref: str, titel: str, due_at: str,
            quelle_feld: str, warn_days: float = 30.0) -> None:
        if not (due_at and str(due_at).strip()):
            return
        ev = _ampel_for(str(due_at), warn_days=warn_days)
        items.append({"bereich": bereich, "ref": ref, "titel": titel,
                      "quelle_feld": quelle_feld, **ev})

    # N2 Risiken (review_datum)
    for r in ndb.list_risiken(db_path, projekt_name):
        add(bereich="N2 Risiko", ref=r.get("risiko_id", str(r.get("id", ""))),
            titel=r.get("titel", ""), due_at=r.get("review_datum") or "",
            quelle_feld="review_datum")

    # N4 Vendoren (review_datum, sonst assessment_datum)
    for v in ndb.list_vendors(db_path, projekt_name):
        due = v.get("review_datum") or v.get("assessment_datum") or ""
        add(bereich="N4 Lieferant", ref=v.get("vendor_name", ""),
            titel=v.get("leistung", ""), due_at=due,
            quelle_feld="review_datum" if v.get("review_datum") else "assessment_datum")

    # N5 BCP (test_datum + test_frequenz → nächster Soll-Test)
    bcp = ndb.load_bcp(db_path, projekt_name) or {}
    if bcp.get("test_datum"):
        from shared import deadlines as dl
        naechster = dl.add_months_iso(
            bcp["test_datum"], _freq_months(bcp.get("test_frequenz")))
        add(bereich="N5 BCP-Test", ref="BCP", titel="Business-Continuity-Test",
            due_at=naechster, quelle_feld="test_datum+test_frequenz")

    # Bewertungen (zieldatum der Maßnahmen)
    for aid, b in (ndb.load_bewertungen(db_path, projekt_name) or {}).items():
        add(bereich="Maßnahme", ref=aid, titel=b.get("massnahme", "") or aid,
            due_at=b.get("zieldatum") or "", quelle_feld="zieldatum")

    # Audit-Register (#1204) — guarded (Tabelle evtl. noch nicht angelegt)
    try:
        from nis2 import audit_db as adb
        for a in adb.list_audits(db_path, projekt_name):
            add(bereich="Audit", ref=str(a.get("id", "")),
                titel=a.get("titel", "") or "Audit",
                due_at=a.get("naechster_audit_soll") or "",
                quelle_feld="naechster_audit_soll", warn_days=90.0)
    except Exception:  # noqa: BLE001
        pass

    # Registrierung (#1203) — jährliche Bestätigung
    try:
        from nis2 import registrierung_db as rdb
        reg = rdb.get_registrierung(db_path, projekt_name)
        if reg and reg.get("naechste_jahres_bestaetigung"):
            add(bereich="Registrierung", ref="Art. 27",
                titel="Jährliche BSI-Bestätigung",
                due_at=reg["naechste_jahres_bestaetigung"],
                quelle_feld="naechste_jahres_bestaetigung", warn_days=90.0)
    except Exception:  # noqa: BLE001
        pass

    # Sortierung: überfällig zuerst, dann nach Restzeit aufsteigend.
    items.sort(key=lambda i: (i["status"] != "ueberfaellig",
                              i.get("days_left") if i.get("days_left") is not None else 1e9))

    counts = {"ueberfaellig": 0, "faellig": 0, "on_track": 0, "grey": 0}
    for i in items:
        if i["status"] == "ueberfaellig":
            counts["ueberfaellig"] += 1
        elif i["status"] == "faellig":
            counts["faellig"] += 1
        elif i["status"] == "on_track":
            counts["on_track"] += 1
        else:
            counts["grey"] += 1

    if counts["ueberfaellig"]:
        overall = "red"
    elif counts["faellig"]:
        overall = "amber"
    elif items:
        overall = "green"
    else:
        overall = "grey"

    return {"items": items, "counts": counts, "overall_ampel": overall}
