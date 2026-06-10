"""AI-Act Art. 5 — Verbots-Screening (8 Tatbestände) mit dokumentierter Negativprüfung (#1206).

Self-contained, additiver DB-Layer auf der gemeinsamen ``data/db/ai_act.sqlite``
(via :func:`ai_act.db._connect`). Bildet die acht verbotenen KI-Praktiken nach
Art. 5(1) lit. a–h als strukturierte Negativprüfung ab. Ein Treffer (mindestens
ein ``betroffen='ja'``) ist das Compliance-Gate, das die Risiko-Klasse auf
``prohibited`` zwingt.

Tabelle: ``aiact_art5_screening`` (eine Zeile je Projekt × Tatbestand).
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from ai_act.db import _connect

DB_PATH = Path("data/db/ai_act.sqlite")

BETROFFEN = ("offen", "ja", "nein", "nicht_relevant")

# Die 8 Verbotstatbestände nach Art. 5(1) AI-Act (a–h).
TATBESTAENDE: list[dict[str, str]] = [
    {"code": "a", "kurz": "Unterschwellige/manipulative Beeinflussung",
     "ref": "Art. 5(1)a",
     "beschreibung": "Techniken zur unterschwelligen, manipulativen oder täuschenden "
                     "Beeinflussung, die das Verhalten wesentlich verzerren."},
    {"code": "b", "kurz": "Ausnutzung von Vulnerabilität",
     "ref": "Art. 5(1)b",
     "beschreibung": "Ausnutzung der Schwäche/Schutzbedürftigkeit (Alter, Behinderung, "
                     "soziale/wirtschaftliche Lage) zur Verhaltensverzerrung."},
    {"code": "c", "kurz": "Social Scoring",
     "ref": "Art. 5(1)c",
     "beschreibung": "Bewertung/Klassifizierung von Personen nach sozialem Verhalten/"
                     "Eigenschaften mit benachteiligender Behandlung."},
    {"code": "d", "kurz": "Predictive Policing (allein profilbasiert)",
     "ref": "Art. 5(1)d",
     "beschreibung": "Risikobewertung zur Vorhersage von Straftaten allein auf Basis "
                     "von Profiling/Persönlichkeitsmerkmalen."},
    {"code": "e", "kurz": "Ungezieltes Face-Scraping",
     "ref": "Art. 5(1)e",
     "beschreibung": "Aufbau/Erweiterung von Gesichtserkennungs-Datenbanken durch "
                     "ungezieltes Auslesen von Bildern aus Internet/CCTV."},
    {"code": "f", "kurz": "Emotionserkennung (Arbeit/Bildung)",
     "ref": "Art. 5(1)f",
     "beschreibung": "Emotionserkennung am Arbeitsplatz und in Bildungseinrichtungen "
                     "(außer aus medizinischen/Sicherheitsgründen)."},
    {"code": "g", "kurz": "Biometrische Kategorisierung sensibler Merkmale",
     "ref": "Art. 5(1)g",
     "beschreibung": "Biometrische Kategorisierung zur Ableitung sensibler Merkmale "
                     "(Rasse, politische Meinung, Religion, Sexualleben …)."},
    {"code": "h", "kurz": "Echtzeit-Fernidentifizierung (öffentlich)",
     "ref": "Art. 5(1)h",
     "beschreibung": "Biometrische Echtzeit-Fernidentifizierung in öffentlich "
                     "zugänglichen Räumen zu Strafverfolgungszwecken (eng begrenzt)."},
]

_VALID_CODES = {t["code"] for t in TATBESTAENDE}

SCHEMA = """
CREATE TABLE IF NOT EXISTS aiact_art5_screening (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_name  TEXT NOT NULL,
    tatbestand    TEXT NOT NULL,
    betroffen     TEXT NOT NULL DEFAULT 'offen',
    begruendung   TEXT NOT NULL DEFAULT '',
    geprueft_von  TEXT NOT NULL DEFAULT '',
    geprueft_am   TEXT NOT NULL DEFAULT '',
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(projekt_name, tatbestand)
);
CREATE INDEX IF NOT EXISTS idx_art5_projekt ON aiact_art5_screening(projekt_name);
"""


def ensure_table(db_path: Path = DB_PATH) -> None:
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def catalog() -> list[dict[str, str]]:
    """Statischer Katalog der 8 Tatbestände."""
    return [dict(t) for t in TATBESTAENDE]


def _row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(r) if r else None


def load_screening(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    """Liefert alle 8 Tatbestände, jeweils mit gespeichertem Befund (oder Default)."""
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        rows = con.execute(
            "SELECT * FROM aiact_art5_screening WHERE projekt_name=?",
            (projekt_name,),
        ).fetchall()
    finally:
        con.close()
    saved = {r["tatbestand"]: dict(r) for r in rows}
    out: list[dict[str, Any]] = []
    for t in TATBESTAENDE:
        row = saved.get(t["code"], {})
        out.append({
            **t,
            "betroffen": row.get("betroffen", "offen"),
            "begruendung": row.get("begruendung", ""),
            "geprueft_von": row.get("geprueft_von", ""),
            "geprueft_am": row.get("geprueft_am", ""),
        })
    return out


def save_befund(db_path: Path, projekt_name: str, tatbestand: str,
                betroffen: str, begruendung: str, geprueft_von: str,
                geprueft_am: str = "") -> None:
    if tatbestand not in _VALID_CODES:
        raise ValueError(f"Unbekannter Tatbestand: {tatbestand!r}")
    if betroffen not in BETROFFEN:
        raise ValueError(f"Ungültiger Wert für betroffen: {betroffen!r}")
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        con.execute(
            """INSERT INTO aiact_art5_screening
                 (projekt_name, tatbestand, betroffen, begruendung, geprueft_von,
                  geprueft_am, updated_at)
               VALUES (?,?,?,?,?,?,datetime('now'))
               ON CONFLICT(projekt_name, tatbestand) DO UPDATE SET
                 betroffen=excluded.betroffen,
                 begruendung=excluded.begruendung,
                 geprueft_von=excluded.geprueft_von,
                 geprueft_am=excluded.geprueft_am,
                 updated_at=datetime('now')""",
            (projekt_name, tatbestand, betroffen, begruendung, geprueft_von,
             geprueft_am or ""),
        )
        con.commit()
    finally:
        con.close()


def summary(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """Aggregierter Gate-Status der Negativprüfung.

    - ``has_prohibited``: mindestens ein Tatbestand ``betroffen='ja'`` → tier=prohibited.
    - ``complete``: jeder Tatbestand bewertet (nicht ``offen``).
    - ``offen``: Anzahl noch nicht bewerteter Tatbestände.
    """
    items = load_screening(db_path, projekt_name)
    offen = [i for i in items if i["betroffen"] == "offen"]
    treffer = [i for i in items if i["betroffen"] == "ja"]
    return {
        "has_prohibited": bool(treffer),
        "treffer": [i["code"] for i in treffer],
        "complete": not offen,
        "offen": len(offen),
        "gesamt": len(items),
    }


# ── KI-Wizard: Vorbewertung aus Use-Case-Beschreibung (#1206) ───────────────

def build_art5_prompt(projekt: dict[str, Any]) -> str:
    """Prompt-Builder für eine Art.-5-Vorbewertung aus der Projekt-/Use-Case-Beschreibung."""
    name = projekt.get("name", "")
    produkt = projekt.get("produkt", "")
    beschreibung = projekt.get("beschreibung", "")
    katalog = "\n".join(
        f"- {t['code']}) {t['kurz']} ({t['ref']}): {t['beschreibung']}"
        for t in TATBESTAENDE
    )
    return f"""Du bist KI-Compliance-Experte für den EU AI Act (Verordnung 2024/1689).

Bewerte das folgende KI-System gegen die acht VERBOTENEN Praktiken aus Art. 5(1):

{katalog}

## KI-System
- Name: {name}
- Produkt: {produkt}
- Beschreibung: {beschreibung}

## Aufgabe
Beurteile JEDEN Tatbestand (a–h): Ist er auf dieses System anwendbar?
Gib eine begründete Negativ- bzw. Positivprüfung. Im Zweifel "offen".

Antworte AUSSCHLIESSLICH als JSON:
{{"items": [
  {{"code": "a", "betroffen": "nein", "begruendung": "..."}},
  ...
]}}
- "betroffen": einer von "ja" | "nein" | "nicht_relevant" | "offen".
- Pro Code genau ein Eintrag, Codes a–h.
"""


def parse_art5_response(raw: str) -> list[dict[str, str]]:
    """Parst die JSON-Antwort des Wizards in eine Befund-Liste (a–h)."""
    if not raw:
        return []
    text = raw.strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return []
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    out: list[dict[str, str]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        code = str(it.get("code", "")).strip().lower()
        if code not in _VALID_CODES:
            continue
        betroffen = str(it.get("betroffen", "offen")).strip().lower()
        if betroffen not in BETROFFEN:
            betroffen = "offen"
        out.append({
            "code": code,
            "betroffen": betroffen,
            "begruendung": str(it.get("begruendung", "") or ""),
        })
    return out
