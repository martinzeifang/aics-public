"""AI-Act Art. 4 — AI-Literacy-/Schulungsnachweis-Register (#1199).

Self-contained DB-Layer auf der gemeinsamen ``data/db/ai_act.sqlite``
(via :func:`ai_act.db._connect`). Erfasst je Projekt:

- ein **Kompetenzkonzept** (Freitext + Stand) im Projekt-``meta_json``
  (``ai_literacy_konzept`` / ``ai_literacy_konzept_stand``);
- **Schulungsnachweise** je Rolle/Person (Modul, Kompetenzlevel,
  durchgeführt am, gültig bis, Nachweis-Referenz) in ``aiact_ai_literacy``.

Ablauf-/Auffrischungslogik nutzt das Datum ``gueltig_bis`` (Ampel: abgelaufen /
läuft bald ab / gültig).
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from ai_act.db import _connect, load_projekt, update_projekt_meta

DB_PATH = Path("data/db/ai_act.sqlite")

KOMPETENZLEVEL = ("grundlagen", "anwender", "fortgeschritten", "experte")

# Tage vor gueltig_bis, ab denen "läuft bald ab" gemeldet wird.
_SOON_DAYS = 30

SCHEMA = """
CREATE TABLE IF NOT EXISTS aiact_ai_literacy (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    rolle           TEXT NOT NULL DEFAULT '',
    person          TEXT NOT NULL DEFAULT '',
    schulungsmodul  TEXT NOT NULL DEFAULT '',
    kompetenzlevel  TEXT NOT NULL DEFAULT 'grundlagen',
    durchgefuehrt_am TEXT NOT NULL DEFAULT '',
    gueltig_bis     TEXT NOT NULL DEFAULT '',
    nachweis_ref    TEXT NOT NULL DEFAULT '',
    oversight_person TEXT NOT NULL DEFAULT '',
    kommentar       TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (aics_now()),
    updated_at      TEXT NOT NULL DEFAULT (aics_now())
);
CREATE INDEX IF NOT EXISTS idx_ailit_projekt ON aiact_ai_literacy(projekt_name);
"""


def ensure_table(db_path: Path = DB_PATH) -> None:
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def _row(r: Any) -> dict[str, Any]:
    return dict(r)


def _ablauf_status(gueltig_bis: str) -> str:
    """'abgelaufen' | 'bald' | 'gueltig' | 'unbefristet'."""
    if not gueltig_bis:
        return "unbefristet"
    try:
        d = datetime.fromisoformat(gueltig_bis[:10]).date()
    except ValueError:
        return "unbefristet"
    today = datetime.now(timezone.utc).date()
    if d < today:
        return "abgelaufen"
    if (d - today).days <= _SOON_DAYS:
        return "bald"
    return "gueltig"


def list_nachweise(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        rows = con.execute(
            "SELECT * FROM aiact_ai_literacy WHERE projekt_name=? "
            "ORDER BY gueltig_bis, person",
            (projekt_name,),
        ).fetchall()
    finally:
        con.close()
    out = []
    for r in rows:
        d = _row(r)
        d["ablauf_status"] = _ablauf_status(d.get("gueltig_bis", ""))
        out.append(d)
    return out


def save_nachweis(db_path: Path, projekt_name: str, data: dict[str, Any]) -> int:
    level = str(data.get("kompetenzlevel", "grundlagen") or "grundlagen")
    if level not in KOMPETENZLEVEL:
        raise ValueError(f"Ungültiger Kompetenzlevel: {level!r}")
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        pk = data.get("id")
        fields = (
            str(data.get("rolle", "") or ""),
            str(data.get("person", "") or ""),
            str(data.get("schulungsmodul", "") or ""),
            level,
            str(data.get("durchgefuehrt_am", "") or ""),
            str(data.get("gueltig_bis", "") or ""),
            str(data.get("nachweis_ref", "") or ""),
            str(data.get("oversight_person", "") or ""),
            str(data.get("kommentar", "") or ""),
        )
        if pk:
            con.execute(
                """UPDATE aiact_ai_literacy SET
                     rolle=?, person=?, schulungsmodul=?, kompetenzlevel=?,
                     durchgefuehrt_am=?, gueltig_bis=?, nachweis_ref=?,
                     oversight_person=?, kommentar=?, updated_at=aics_now()
                   WHERE id=? AND projekt_name=?""",
                (*fields, int(pk), projekt_name),
            )
            out_id = int(pk)
        else:
            cur = con.execute(
                """INSERT INTO aiact_ai_literacy
                     (projekt_name, rolle, person, schulungsmodul, kompetenzlevel,
                      durchgefuehrt_am, gueltig_bis, nachweis_ref, oversight_person,
                      kommentar)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (projekt_name, *fields),
            )
            out_id = int(cur.lastrowid)
        con.commit()
    finally:
        con.close()
    return out_id


def delete_nachweis(db_path: Path, projekt_name: str, pk: int) -> None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        con.execute(
            "DELETE FROM aiact_ai_literacy WHERE id=? AND projekt_name=?",
            (int(pk), projekt_name),
        )
        con.commit()
    finally:
        con.close()


def get_konzept(db_path: Path, projekt_name: str) -> dict[str, str]:
    p = load_projekt(db_path, projekt_name) or {}
    meta = p.get("meta") if isinstance(p.get("meta"), dict) else {}
    return {
        "konzept": str(meta.get("ai_literacy_konzept", "") or ""),
        "stand": str(meta.get("ai_literacy_konzept_stand", "") or ""),
    }


def save_konzept(db_path: Path, projekt_name: str, konzept: str) -> dict[str, str]:
    p = load_projekt(db_path, projekt_name)
    if not p:
        raise ValueError("Projekt nicht gefunden")
    meta = dict(p.get("meta") or {})
    meta["ai_literacy_konzept"] = str(konzept or "")
    meta["ai_literacy_konzept_stand"] = date.today().isoformat()
    update_projekt_meta(db_path, projekt_name, meta)
    return {"konzept": meta["ai_literacy_konzept"], "stand": meta["ai_literacy_konzept_stand"]}


def summary(db_path: Path, projekt_name: str) -> dict[str, Any]:
    items = list_nachweise(db_path, projekt_name)
    abgelaufen = [i for i in items if i["ablauf_status"] == "abgelaufen"]
    bald = [i for i in items if i["ablauf_status"] == "bald"]
    return {
        "gesamt": len(items),
        "abgelaufen": len(abgelaufen),
        "bald_faellig": len(bald),
        "personen": len({i["person"] for i in items if i["person"]}),
    }


def oversight_personen(db_path: Path, projekt_name: str) -> list[str]:
    """A4-Oversight-Personen (Art. 14) als Vorschlag für Schulungs-Zuordnung.

    Liest – falls vorhanden – die Human-Oversight-Tabelle des Moduls. Tolerant
    gegenüber abweichenden Schemata; Fehler ergeben eine leere Liste.
    """
    try:
        from ai_act.db import load_human_oversight
        ho = load_human_oversight(db_path, projekt_name)
    except Exception:
        return []
    out: list[str] = []
    if isinstance(ho, dict):
        persons = ho.get("oversight_persons")
        if isinstance(persons, list):
            for p in persons:
                if isinstance(p, dict):
                    name = p.get("person") or p.get("name") or p.get("rolle")
                    if name:
                        out.append(str(name))
                elif isinstance(p, str) and p:
                    out.append(p)
    return out


# ── KI-Ausfüll-Assistent (Art. 4, #1242) ────────────────────────────────────────
# Copy/Paste-Wizard: schlägt rollenbasiert Schulungsmaßnahmen + einen vollständigen
# AI-Literacy-Plan vor (Entwickler / Fachanwender / Management / Betroffene),
# risikoangemessen zum Use-Case. Kein API-Call — Prompt raus, JSON-Antwort rein.

# Standard-Zielgruppen für den rollenbasierten Vorschlag (Art. 4 nennt „Personal
# und sonstige Personen, die in ihrem Auftrag mit dem Betrieb … befasst sind").
LITERACY_ZIELGRUPPEN = (
    "Entwickler/Data-Science",
    "Fachanwender/Operatoren",
    "Management/Governance",
    "Aufsichtspersonen (Art. 14)",
    "Betroffene/Endnutzer",
)


def build_literacy_prompt(projekt: dict[str, Any], *,
                          risiko_stufe: str = "", konzept: str = "") -> str:
    """Copy/Paste-Prompt für rollenbasierte AI-Literacy-Vorschläge (Art. 4).

    Liefert dem Modell den Projekt-Kontext + die Standard-Zielgruppen und fordert
    JSON mit (a) rollenbezogenen Schulungsmaßnahmen für das Register und (b) einem
    Fließtext-Plan, der als AI-Literacy-Plan-Dokument speicher-/exportierbar ist.
    """
    zg = "\n".join(f"- {z}" for z in LITERACY_ZIELGRUPPEN)
    stufe = (risiko_stufe or "").strip() or "(nicht gesetzt)"
    konzept_block = (konzept or "").strip()
    konzept_hint = (f"\n## Bisheriges Kompetenzkonzept\n{konzept_block}\n"
                    if konzept_block else "")
    return f"""Du bist KI-Compliance-Experte für den EU AI Act (Verordnung 2024/1689).

Erstelle einen risikoangemessenen AI-Literacy-Plan (Art. 4 — KI-Kompetenz, gilt
seit 02.02.2025 für ALLE Risikoklassen, Anbieter UND Betreiber) für das folgende
KI-System. Schlage je Zielgruppe konkrete, kontextpassende Schulungsmaßnahmen vor.

## KI-System
- Name: {projekt.get('name', '')}
- Organisation: {projekt.get('organisation', '')}
- Produkt: {projekt.get('produkt', '')}
- Beschreibung: {projekt.get('beschreibung', '')}
- Risikoklasse: {stufe}
{konzept_hint}
## Zielgruppen (rollenbasiert)
{zg}

Antworte AUSSCHLIESSLICH als JSON:
{{
  "konzept": "Kurzes übergeordnetes Kompetenzkonzept (2-4 Sätze).",
  "massnahmen": [
    {{"rolle": "Entwickler/Data-Science", "schulungsmodul": "...",
      "kompetenzlevel": "grundlagen|anwender|fortgeschritten|experte",
      "turnus": "z.B. jährlich", "inhalte": "Stichpunkte zu Lerninhalten"}}
  ],
  "plan_markdown": "# AI-Literacy-Plan\\n\\nVollständiger, exportierbarer Plan in Markdown ..."
}}
- kompetenzlevel muss exakt einer der vier Werte sein.
- massnahmen: je Zielgruppe mindestens einen Eintrag.
"""


def parse_literacy_response(raw: str) -> dict[str, Any]:
    """Parst die KI-Antwort des Ausfüll-Assistenten (tolerant, #1242)."""
    if not raw:
        return {}
    text = raw.strip()
    for marker in ("```json", "```"):
        if marker in text:
            parts = text.split(marker)
            if len(parts) >= 2:
                text = parts[1].split("```")[0] if marker == "```json" else parts[1]
                break
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, Any] = {}
    if "konzept" in data:
        out["konzept"] = str(data.get("konzept", "") or "")
    if "plan_markdown" in data:
        out["plan_markdown"] = str(data.get("plan_markdown", "") or "")
    massnahmen = data.get("massnahmen")
    if isinstance(massnahmen, list):
        parsed: list[dict[str, Any]] = []
        for mn in massnahmen:
            if not isinstance(mn, dict):
                continue
            level = str(mn.get("kompetenzlevel", "grundlagen") or "grundlagen").lower()
            if level not in KOMPETENZLEVEL:
                level = "grundlagen"
            parsed.append({
                "rolle": str(mn.get("rolle", "") or ""),
                "schulungsmodul": str(mn.get("schulungsmodul", "") or ""),
                "kompetenzlevel": level,
                "turnus": str(mn.get("turnus", "") or ""),
                "inhalte": str(mn.get("inhalte", "") or ""),
            })
        out["massnahmen"] = parsed
    return out


def apply_literacy_suggestions(db_path: Path, projekt_name: str,
                               parsed: dict[str, Any]) -> dict[str, Any]:
    """Übernimmt geparste Vorschläge: Konzept + je Maßnahme einen Register-Eintrag.

    Idempotenz-arm: legt je Vorschlag einen neuen Nachweis an (ohne Person/Datum —
    als Planungs-Eintrag). Der Anwender vervollständigt Person/Datum/Nachweis später.
    """
    created = 0
    if parsed.get("konzept"):
        try:
            save_konzept(db_path, projekt_name, str(parsed["konzept"]))
        except ValueError:
            pass
    for mn in parsed.get("massnahmen", []) or []:
        save_nachweis(db_path, projekt_name, {
            "rolle": mn.get("rolle", ""),
            "schulungsmodul": mn.get("schulungsmodul", ""),
            "kompetenzlevel": mn.get("kompetenzlevel", "grundlagen"),
            "kommentar": (mn.get("inhalte", "") + (
                f"  · Turnus: {mn.get('turnus')}" if mn.get("turnus") else "")).strip(),
        })
        created += 1
    return {"created": created}
