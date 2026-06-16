"""AI-Act Art. 27 — FRIA (Fundamental Rights Impact Assessment, #1196).

Grundrechte-Folgenabschätzung durch Betreiber (öffentliche Stellen, private
Erbringer öffentlicher Dienste, Annex III Nr. 5 b/c) VOR der ersten
Inbetriebnahme eines Hochrisiko-KI-Systems. Eigenständige, von der DSFA getrennte
Pflicht mit Behörden-Notifikation.

Self-contained DB-Layer auf der gemeinsamen ``data/db/ai_act.sqlite`` (via
:func:`ai_act.db._connect`). Eine Zeile je Projekt (1:1-Record + geführter
Stepper analog DSGVO-DSFA).

Tabelle: ``aiact_fria``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_act.db import _connect, load_projekt

DB_PATH = Path("data/db/ai_act.sqlite")

# Betreiber-Typen, die eine FRIA-Pflicht auslösen (Art. 27(1)).
BETREIBER_TYPEN: dict[str, str] = {
    "keine": "Kein FRIA-pflichtiger Betreiber",
    "oeffentliche_stelle": "Einrichtung des öffentlichen Rechts",
    "privat_oeffentliche_dienste": "Privater Erbringer öffentlicher Dienste",
    "annex_iii_5b": "Annex III Nr. 5b (Kreditwürdigkeit/Bonität)",
    "annex_iii_5c": "Annex III Nr. 5c (Risikobewertung/Tarifierung Lebens-/Krankenversicherung)",
}

# Geführter Stepper (analog DSGVO-DSFA stage-Modell).
STAGES: tuple[str, ...] = (
    "betreiber",      # Betreiber-Typ + Trigger-Bestätigung
    "prozesse",       # Nutzungsprozesse, Zeitraum/Frequenz
    "betroffene",     # betroffene Personengruppen
    "risiken",        # spezifische Schadensrisiken
    "massnahmen",     # Aufsicht + Maßnahmen bei Risikoeintritt + Governance
    "mitteilung",     # Mitteilung an Behörde
)

STATUS = ("offen", "in_bearbeitung", "abgeschlossen", "an_behoerde_gemeldet")

SCHEMA = """
CREATE TABLE IF NOT EXISTS aiact_fria (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name      TEXT NOT NULL UNIQUE,
    betreiber_typ     TEXT NOT NULL DEFAULT 'keine',
    nutzungsprozesse  TEXT NOT NULL DEFAULT '',
    zeitraum_frequenz TEXT NOT NULL DEFAULT '',
    betroffene_gruppen TEXT NOT NULL DEFAULT '',
    schadensrisiken_json TEXT NOT NULL DEFAULT '[]',
    oversight_massnahmen TEXT NOT NULL DEFAULT '',
    massnahmen_bei_risiko TEXT NOT NULL DEFAULT '',
    governance        TEXT NOT NULL DEFAULT '',
    beschwerdemechanismus TEXT NOT NULL DEFAULT '',
    stage             TEXT NOT NULL DEFAULT 'betreiber',
    status            TEXT NOT NULL DEFAULT 'offen',
    mitteilung_behoerde_am TEXT NOT NULL DEFAULT '',
    behoerde          TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL DEFAULT (aics_now()),
    updated_at        TEXT NOT NULL DEFAULT (aics_now())
);
CREATE INDEX IF NOT EXISTS idx_fria_projekt ON aiact_fria(projekt_name);
"""

_TEXT_FIELDS = (
    "betreiber_typ", "nutzungsprozesse", "zeitraum_frequenz", "betroffene_gruppen",
    "oversight_massnahmen", "massnahmen_bei_risiko", "governance",
    "beschwerdemechanismus", "stage", "status", "mitteilung_behoerde_am", "behoerde",
)


def ensure_table(db_path: Path = DB_PATH) -> None:
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def betreiber_typen() -> list[dict[str, str]]:
    return [{"code": k, "label": v} for k, v in BETREIBER_TYPEN.items()]


def _project_risk_tier(db_path: Path, projekt_name: str) -> str:
    """Ermittelt das Risk-Tier aus dem Projekt-Meta (art5-Gate oder Risk-Tier-Wizard)."""
    p = load_projekt(db_path, projekt_name)
    if not p:
        return ""
    meta = p.get("meta") if isinstance(p.get("meta"), dict) else {}
    # art5-Gate (#1206) schreibt meta.risk_tier direkt; Risk-Tier-Wizard schreibt
    # meta.aiact.risk_tier.tier.
    tier = meta.get("risk_tier")
    if isinstance(tier, str) and tier:
        return tier
    aiact_meta = meta.get("aiact") if isinstance(meta.get("aiact"), dict) else {}
    rt = aiact_meta.get("risk_tier")
    if isinstance(rt, dict):
        return str(rt.get("tier", "") or "")
    if isinstance(rt, str):
        return rt
    return ""


def _empty_record(projekt_name: str) -> dict[str, Any]:
    return {
        "projekt_name": projekt_name,
        "betreiber_typ": "keine",
        "nutzungsprozesse": "",
        "zeitraum_frequenz": "",
        "betroffene_gruppen": "",
        "schadensrisiken_json": "[]",
        "schadensrisiken": [],
        "oversight_massnahmen": "",
        "massnahmen_bei_risiko": "",
        "governance": "",
        "beschwerdemechanismus": "",
        "stage": "betreiber",
        "status": "offen",
        "mitteilung_behoerde_am": "",
        "behoerde": "",
    }


def trigger(db_path: Path, projekt_name: str,
            betreiber_typ: str | None = None) -> dict[str, Any]:
    """FRIA-Pflicht-Trigger: high-risk + FRIA-pflichtiger Betreiber-Typ.

    ``betreiber_typ`` überschreibt den gespeicherten Wert (für Live-Vorschau im UI).
    """
    tier = _project_risk_tier(db_path, projekt_name)
    is_high_risk = tier in ("high-risk", "high_risk", "hochrisiko")
    if betreiber_typ is None:
        rec = get(db_path, projekt_name)
        betreiber_typ = rec.get("betreiber_typ", "keine") if rec else "keine"
    betreiber_pflicht = betreiber_typ in BETREIBER_TYPEN and betreiber_typ != "keine"
    required = bool(is_high_risk and betreiber_pflicht)
    return {
        "required": required,
        "risk_tier": tier or "(nicht klassifiziert)",
        "is_high_risk": is_high_risk,
        "betreiber_typ": betreiber_typ,
        "betreiber_pflicht": betreiber_pflicht,
    }


def get(db_path: Path, projekt_name: str) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        r = con.execute(
            "SELECT * FROM aiact_fria WHERE projekt_name=?", (projekt_name,)
        ).fetchone()
    finally:
        con.close()
    if not r:
        return None
    d = dict(r)
    try:
        d["schadensrisiken"] = json.loads(d.get("schadensrisiken_json", "[]") or "[]")
    except (ValueError, TypeError):
        d["schadensrisiken"] = []
    return d


def get_or_empty(db_path: Path, projekt_name: str) -> dict[str, Any]:
    return get(db_path, projekt_name) or _empty_record(projekt_name)


def _validate(data: dict[str, Any]) -> tuple[dict[str, str], str]:
    bt = str(data.get("betreiber_typ", "keine") or "keine")
    if bt not in BETREIBER_TYPEN:
        raise ValueError(f"Unbekannter Betreiber-Typ: {bt!r}")
    stage = str(data.get("stage", "betreiber") or "betreiber")
    if stage not in STAGES:
        raise ValueError(f"Unbekannte Stufe: {stage!r}")
    status = str(data.get("status", "offen") or "offen")
    if status not in STATUS:
        raise ValueError(f"Ungültiger Status: {status!r}")
    vals = {f: str(data.get(f, "") or "") for f in _TEXT_FIELDS}
    vals["betreiber_typ"] = bt
    vals["stage"] = stage
    vals["status"] = status
    risiken = data.get("schadensrisiken")
    risiken_json = json.dumps(risiken if isinstance(risiken, list) else [],
                              ensure_ascii=False)
    return vals, risiken_json


def save(db_path: Path, projekt_name: str, data: dict[str, Any]) -> dict[str, Any]:
    ensure_table(db_path)
    vals, risiken_json = _validate(data)
    cols = list(_TEXT_FIELDS) + ["schadensrisiken_json"]
    con = _connect(Path(db_path))
    try:
        set_clause = ", ".join(f"{c}=excluded.{c}" for c in cols)
        placeholders = ", ".join("?" for _ in cols)
        con.execute(
            f"""INSERT INTO aiact_fria (projekt_name, {", ".join(cols)})
                 VALUES (?, {placeholders})
               ON CONFLICT(projekt_name) DO UPDATE SET
                 {set_clause}, updated_at=aics_now()""",
            (projekt_name, *[vals[f] for f in _TEXT_FIELDS], risiken_json),
        )
        con.commit()
    finally:
        con.close()
    return get_or_empty(db_path, projekt_name)


def mark_reported(db_path: Path, projekt_name: str, *, behoerde: str = "",
                  am: str = "") -> dict[str, Any]:
    """Status 'an Behörde gemeldet' + Mitteilungs-Zeitpunkt setzen."""
    ensure_table(db_path)
    am = am or datetime.now(timezone.utc).date().isoformat()
    con = _connect(Path(db_path))
    try:
        con.execute(
            """INSERT INTO aiact_fria (projekt_name, status, mitteilung_behoerde_am, behoerde)
                 VALUES (?, 'an_behoerde_gemeldet', ?, ?)
               ON CONFLICT(projekt_name) DO UPDATE SET
                 status='an_behoerde_gemeldet',
                 mitteilung_behoerde_am=excluded.mitteilung_behoerde_am,
                 behoerde=excluded.behoerde,
                 updated_at=aics_now()""",
            (projekt_name, am, behoerde),
        )
        con.commit()
    finally:
        con.close()
    return get_or_empty(db_path, projekt_name)


# ── Mitteilungs-Template-Export (Behörden-Notifikation) ──────────────────────

def build_mitteilung(db_path: Path, projekt_name: str) -> str:
    """Mitteilungs-Template an die Marktüberwachungsbehörde (Art. 27(3))."""
    rec = get_or_empty(db_path, projekt_name)
    p = load_projekt(db_path, projekt_name) or {}
    risiken = rec.get("schadensrisiken") or []
    risiken_block = "\n".join(f"- {r}" for r in risiken) if risiken else "—"
    return f"""# Mitteilung einer Grundrechte-Folgenabschätzung (FRIA) — Art. 27(3) AI-Act

Projekt: {projekt_name}
Organisation: {p.get('organisation', '')}
Betreiber-Typ: {BETREIBER_TYPEN.get(rec.get('betreiber_typ', 'keine'), '')}
Stand: {datetime.now(timezone.utc).date().isoformat()}

## 1. Nutzungsprozesse (Art. 27(1)a)
{rec.get('nutzungsprozesse') or '—'}

## 2. Zeitraum & Häufigkeit (Art. 27(1)b)
{rec.get('zeitraum_frequenz') or '—'}

## 3. Betroffene Personengruppen (Art. 27(1)c)
{rec.get('betroffene_gruppen') or '—'}

## 4. Spezifische Schadensrisiken (Art. 27(1)d)
{risiken_block}

## 5. Menschliche Aufsicht (Art. 27(1)e)
{rec.get('oversight_massnahmen') or '—'}

## 6. Maßnahmen bei Risikoeintritt / Governance / Beschwerde (Art. 27(1)f)
- Maßnahmen: {rec.get('massnahmen_bei_risiko') or '—'}
- Governance: {rec.get('governance') or '—'}
- Beschwerdemechanismus: {rec.get('beschwerdemechanismus') or '—'}

---
_Generiert aus dem AI Compliance Suite AI-Act-Modul (FRIA · Art. 27 · #1196)._
"""


# ── KI-Wizard: Vorbefüllung aus Projekt-/Use-Case-Beschreibung ───────────────

def build_fria_prompt(projekt: dict[str, Any]) -> str:
    return f"""Du bist KI-Compliance-Experte für den EU AI Act (Verordnung 2024/1689).

Erstelle einen Entwurf für eine Grundrechte-Folgenabschätzung (FRIA) nach Art. 27
für das folgende Hochrisiko-KI-System.

## KI-System
- Name: {projekt.get('name', '')}
- Organisation: {projekt.get('organisation', '')}
- Produkt: {projekt.get('produkt', '')}
- Beschreibung: {projekt.get('beschreibung', '')}

## Aufgabe
Liefere Entwürfe zu den Art.-27-Pflichtfeldern.

Antworte AUSSCHLIESSLICH als JSON:
{{
  "nutzungsprozesse": "...",
  "zeitraum_frequenz": "...",
  "betroffene_gruppen": "...",
  "schadensrisiken": ["Risiko 1", "Risiko 2"],
  "oversight_massnahmen": "...",
  "massnahmen_bei_risiko": "...",
  "governance": "...",
  "beschwerdemechanismus": "..."
}}
"""


def parse_fria_response(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    import re
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
    for f in ("nutzungsprozesse", "zeitraum_frequenz", "betroffene_gruppen",
              "oversight_massnahmen", "massnahmen_bei_risiko", "governance",
              "beschwerdemechanismus"):
        if f in data:
            out[f] = str(data.get(f, "") or "")
    risiken = data.get("schadensrisiken")
    if isinstance(risiken, list):
        out["schadensrisiken"] = [str(r) for r in risiken]
    return out
