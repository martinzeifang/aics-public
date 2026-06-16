"""DS-J1 (#1132) — Jahresbericht-Datenaggregation (Rechenschaftspflicht Art. 5(2)).

Aggregiert alle relevanten Inhalte eines Datenschutz-Jahres für die Beispiel-/
Kundenfirma: durchgeführte Kontrollen, DSFAs, Datenpannen, Betroffenenrechte-
Anträge, Einwilligungs-Änderungen, TOM-Reifegrad, offene Punkte und (firmenweit)
offene Risiken. Liefert ein Jinja-sicheres, None-freies Dict.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

from dsgvo.db import _connect

DB_PATH = Path("data/db/dsgvo.sqlite")


def _s(v: Any) -> str:
    return "" if v is None else str(v)


def _cols(con: Any, table: str) -> set[str]:
    try:
        return {r[0] for r in con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = ?", (table,))}
    except Exception:
        return set()


def _in_year(value: str, jahr: int) -> bool:
    return bool(value) and str(value)[:4] == str(jahr)


def build_jahresbericht_context(db_path: Path, projekt_name: str, jahr: int) -> dict[str, Any]:
    db_path = Path(db_path)
    con = _connect(db_path)
    ctx: dict[str, Any] = {
        "projekt": {"name": projekt_name},
        "jahr": int(jahr),
        "erstellt_am": datetime.date.today().isoformat(),
    }
    try:
        # Projekt-Stammdaten
        if "dsgvo_projekte" in _tables(con):
            row = con.execute(
                "SELECT * FROM dsgvo_projekte WHERE name=?", (projekt_name,)).fetchone()
            if row:
                d = dict(row)
                ctx["projekt"].update({
                    "unternehmen": _s(d.get("unternehmen")),
                    "beschreibung": _s(d.get("beschreibung")),
                    "berater": _s(d.get("berater")),
                })

        # 1) Kontrollen des Jahres
        from dsgvo import kontrollen_db as kdb
        ks = kdb.list_kontrollen(db_path, projekt_name, jahr=int(jahr))
        ctx["kontrollen"] = [{
            "kontroll_id": _s(k.get("kontroll_id")), "titel": _s(k.get("titel")),
            "bereich": _s(k.get("bereich")), "status": _s(k.get("status")),
            "durchgefuehrt_am": _s(k.get("durchgefuehrt_am")),
            "ergebnis": _s(k.get("ergebnis")), "verantwortlich": _s(k.get("verantwortlich")),
            "anhaenge": int(k.get("anhaenge") or 0),
        } for k in ks]
        ctx["kontrollen_summary"] = {
            "gesamt": len(ks),
            "abgeschlossen": sum(1 for k in ks if k.get("status") == "abgeschlossen"),
            "offen": sum(1 for k in ks if k.get("status") != "abgeschlossen"),
        }

        # 2) DSFAs (alle, mit Restrisiko)
        ctx["dsfa"] = _list(con, "dsgvo_dpia", projekt_name,
                            ["dpia_id", "titel", "restrisiko", "status", "naechstes_review"])

        # 3) Datenpannen des Jahres (Art. 33/34)
        ctx["datenpannen"] = _list_year(con, "dsgvo_datenpannen", projekt_name, jahr,
                                        ["art", "risikoeinschaetzung", "status"],
                                        date_candidates=["entdeckt_am", "datum", "created_at"])

        # 4) Betroffenenrechte-Anträge des Jahres (Art. 15–22)
        ctx["betroffenenrechte"] = _list_year(con, "dsgvo_betroffenenrechte", projekt_name, jahr,
                                              ["antrag_id", "typ", "status", "eingang_datum"],
                                              date_candidates=["eingang_datum", "created_at"])

        # 5) Einwilligungs-Änderungen (Widerrufe im Jahr)
        ctx["einwilligung_widerrufe"] = _list_year(
            con, "dsgvo_einwilligung", projekt_name, jahr,
            ["einwilligung_id", "zweck", "status"], date_candidates=["widerruf_zeitpunkt"])

        # 6) TOM-Reifegrad (Art. 32)
        ctx["tom"] = _tom_reifegrad(con, projekt_name)

        # 7) Offene Risiken firmenweit (Risiko-Cockpit)
        ctx["risiken"] = _risiken(db_path, con, projekt_name)

    finally:
        con.close()

    ctx["meta"] = {
        "anzahl_kontrollen": len(ctx.get("kontrollen", [])),
        "anzahl_dsfa": len(ctx.get("dsfa", [])),
        "anzahl_datenpannen": len(ctx.get("datenpannen", [])),
        "anzahl_betroffenenrechte": len(ctx.get("betroffenenrechte", [])),
        "anzahl_risiken": len(ctx.get("risiken", [])),
        "tom_reifegrad": ctx.get("tom", {}).get("pct", 0),
    }
    return ctx


def _tables(con: Any) -> set[str]:
    return {r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = current_schema()")}


def _list(con, table, projekt_name, fields):
    if table not in _tables(con):
        return []
    cols = _cols(con, table)
    sel = [f for f in fields if f in cols]
    if "projekt_name" not in cols or not sel:
        return []
    rows = con.execute(
        f"SELECT {','.join(sel)} FROM {table} WHERE projekt_name=?", (projekt_name,)).fetchall()
    return [{k: _s(dict(r).get(k)) for k in sel} for r in rows]


def _list_year(con, table, projekt_name, jahr, fields, *, date_candidates):
    if table not in _tables(con):
        return []
    cols = _cols(con, table)
    if "projekt_name" not in cols:
        return []
    date_col = next((c for c in date_candidates if c in cols), None)
    sel = [f for f in fields if f in cols]
    if date_col and date_col not in sel:
        sel.append(date_col)
    rows = con.execute(
        f"SELECT {','.join(sel)} FROM {table} WHERE projekt_name=?", (projekt_name,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if date_col and not _in_year(_s(d.get(date_col)), jahr):
            continue
        out.append({k: _s(d.get(k)) for k in sel})
    return out


def _tom_reifegrad(con, projekt_name):
    if "dsgvo_tom_katalog" not in _tables(con):
        return {"pct": 0, "gesamt": 0, "umgesetzt": 0}
    rows = con.execute(
        "SELECT status FROM dsgvo_tom_katalog WHERE projekt_name=?", (projekt_name,)).fetchall()
    gesamt = len(rows)
    umgesetzt = sum(1 for r in rows if int(dict(r).get("status") or 0) >= 4)
    pct = round(umgesetzt / gesamt * 100, 1) if gesamt else 0
    return {"pct": pct, "gesamt": gesamt, "umgesetzt": umgesetzt}


def _risiken(db_path, con, projekt_name):
    try:
        firmen_id = None
        if "firmen_id" in _cols(con, "dsgvo_projekte"):
            row = con.execute(
                "SELECT firmen_id FROM dsgvo_projekte WHERE name=?", (projekt_name,)).fetchone()
            firmen_id = dict(row).get("firmen_id") if row else None
        if not firmen_id:
            return []
        from shared.risk_cockpit import build_cockpit
        data = build_cockpit(int(firmen_id),
                             rb_db=db_path.parent / "risikobewertung.sqlite",
                             cra_db=db_path.parent / "cra.sqlite")
        return [{
            "quelle": _s(i.get("source")), "titel": _s(i.get("titel") or i.get("risk_name")),
            "schwere": _s(i.get("severity") or i.get("risiko_label")),
            "projekt": _s(i.get("projekt")),
        } for i in (data.get("items") or [])]
    except Exception:  # noqa: BLE001
        return []
