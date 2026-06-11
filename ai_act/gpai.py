"""AI-Act Art. 51-55 — GPAI-Modul (General-Purpose-AI-Modelle, #1195).

Eigenständige GPAI-Vertikale neben High-/Limited-Risk:

- **Klassifizierung** (``aiact_gpai_klassifizierung``): ist_gpai, training_flop,
  >10^25-FLOP-Schwellenwert-Auswertung → systemisches Risiko (Art. 51), Kommissions-
  Notifikation mit 2-Wochen-Fristenuhr (Art. 52, via :mod:`shared.deadlines`).
- **Pflicht-Register / Checks** (``aiact_gpai_checks``): Status 0-5 je
  GPAI-Anforderung (Annex XI Modell-Doku, Annex XII Downstream-Doku, Copyright/
  TDM-Opt-out-Policy, Trainingsdaten-Zusammenfassung; systemisch: Red-Teaming,
  Systemic-Risk-Assessment, Cybersecurity, Code-of-Practice).
- **AI-Office-Incident-Tracking** (``aiact_gpai_incidents``, nur systemische
  Modelle, Art. 55(1)c).

Self-contained DB-Layer auf ``data/db/ai_act.sqlite``.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_act.db import _connect, load_projekt

import shared.deadlines as dl

DB_PATH = Path("data/db/ai_act.sqlite")

# Schwellenwert für systemisches Risiko (Art. 51(2)): 10^25 FLOP kumulierte
# Trainings-Rechenleistung.
SYSTEMIC_FLOP_THRESHOLD = 1e25

# ── GPAI-Anforderungs-Katalog (AIA-GPAI-IDs) ────────────────────────────────
# ``systemic_only`` markiert Pflichten, die nur für GPAI mit systemischem Risiko
# gelten (Art. 55). ``annex`` referenziert die Doku-Anhänge.

GPAI_REQUIREMENTS: list[dict[str, Any]] = [
    {"id": "AIA-GPAI-01", "ref": "Art. 53(1)a / Annex XI",
     "titel": "Technische Modell-Dokumentation (Annex XI)",
     "hinweis": "Modellarchitektur, Trainingsprozess, Evaluierung, Energieverbrauch.",
     "systemic_only": False},
    {"id": "AIA-GPAI-02", "ref": "Art. 53(1)b / Annex XII",
     "titel": "Downstream-Dokumentation für Anbieter (Annex XII)",
     "hinweis": "Informationen für Integratoren/Deployer (Fähigkeiten, Limitierungen).",
     "systemic_only": False},
    {"id": "AIA-GPAI-03", "ref": "Art. 53(1)c",
     "titel": "Urheberrechts-/TDM-Opt-out-Policy",
     "hinweis": "Policy zur Wahrung des Urheberrechts inkl. TDM-Opt-out (Art. 4(3) DSM-RL).",
     "systemic_only": False},
    {"id": "AIA-GPAI-04", "ref": "Art. 53(1)d",
     "titel": "Öffentliche Trainingsdaten-Zusammenfassung",
     "hinweis": "Hinreichend detaillierte Zusammenfassung der Trainingsinhalte (AI-Office-Template).",
     "systemic_only": False},
    {"id": "AIA-GPAI-05", "ref": "Art. 55(1)a",
     "titel": "Red-Teaming / adversarielle Tests",
     "hinweis": "Modell-Evaluierung inkl. adversarieller Tests zur Risikoidentifikation.",
     "systemic_only": True},
    {"id": "AIA-GPAI-06", "ref": "Art. 55(1)b",
     "titel": "Systemic-Risk-Assessment & Mitigation",
     "hinweis": "Bewertung + Minderung systemischer Risiken auf EU-Ebene.",
     "systemic_only": True},
    {"id": "AIA-GPAI-07", "ref": "Art. 55(1)d",
     "titel": "Cybersicherheit (Modell + physische Infrastruktur)",
     "hinweis": "Angemessenes Cybersicherheitsniveau für Modell und Infrastruktur.",
     "systemic_only": True},
    {"id": "AIA-GPAI-08", "ref": "Art. 53(4) / 55(2)",
     "titel": "GPAI Code of Practice — Adhärenz",
     "hinweis": "Einhaltung des GPAI-Verhaltenskodex bis zum harmonisierten Standard.",
     "systemic_only": False},
]

_GPAI_IDS = {r["id"] for r in GPAI_REQUIREMENTS}

INCIDENT_STATUS = ("offen", "gemeldet", "abgeschlossen")

SCHEMA = """
CREATE TABLE IF NOT EXISTS aiact_gpai_klassifizierung (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_name           TEXT NOT NULL UNIQUE,
    ist_gpai               INTEGER NOT NULL DEFAULT 0,
    training_flop          REAL NOT NULL DEFAULT 0,
    systemisch_override    TEXT NOT NULL DEFAULT '',
    copyright_tdm_policy   TEXT NOT NULL DEFAULT '',
    trainingsdaten_summary TEXT NOT NULL DEFAULT '',
    notifikation_kommission_am TEXT NOT NULL DEFAULT '',
    schwellwert_erreicht_am TEXT NOT NULL DEFAULT '',
    kommentar              TEXT NOT NULL DEFAULT '',
    created_at             TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at             TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_gpai_klass_projekt ON aiact_gpai_klassifizierung(projekt_name);

CREATE TABLE IF NOT EXISTS aiact_gpai_checks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_name  TEXT NOT NULL,
    req_id        TEXT NOT NULL,
    status        INTEGER NOT NULL DEFAULT 0,
    kommentar     TEXT NOT NULL DEFAULT '',
    nachweis_ref  TEXT NOT NULL DEFAULT '',
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(projekt_name, req_id)
);
CREATE INDEX IF NOT EXISTS idx_gpai_checks_projekt ON aiact_gpai_checks(projekt_name);

CREATE TABLE IF NOT EXISTS aiact_gpai_incidents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_name  TEXT NOT NULL,
    titel         TEXT NOT NULL DEFAULT '',
    beschreibung  TEXT NOT NULL DEFAULT '',
    eingetreten_am TEXT NOT NULL DEFAULT '',
    gemeldet_ai_office_am TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'offen',
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_gpai_inc_projekt ON aiact_gpai_incidents(projekt_name);
"""


def ensure_table(db_path: Path = DB_PATH) -> None:
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def requirements() -> list[dict[str, Any]]:
    return [dict(r) for r in GPAI_REQUIREMENTS]


# ── Klassifizierung ─────────────────────────────────────────────────────────

def _is_systemic(training_flop: float, override: str) -> bool:
    if override == "ja":
        return True
    if override == "nein":
        return False
    return float(training_flop or 0) >= SYSTEMIC_FLOP_THRESHOLD


def _empty_klass(projekt_name: str) -> dict[str, Any]:
    return {
        "projekt_name": projekt_name,
        "ist_gpai": False,
        "training_flop": 0.0,
        "systemisch_override": "",
        "copyright_tdm_policy": "",
        "trainingsdaten_summary": "",
        "notifikation_kommission_am": "",
        "schwellwert_erreicht_am": "",
        "kommentar": "",
    }


def _enrich_klass(d: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    d["ist_gpai"] = bool(d.get("ist_gpai"))
    flop = float(d.get("training_flop") or 0)
    override = str(d.get("systemisch_override") or "")
    d["training_flop"] = flop
    d["flop_threshold"] = SYSTEMIC_FLOP_THRESHOLD
    d["ueber_schwellenwert"] = flop >= SYSTEMIC_FLOP_THRESHOLD
    d["systemisch"] = bool(d["ist_gpai"] and _is_systemic(flop, override))
    # 2-Wochen-Notifikationsfrist nur für systemische Modelle.
    if d["systemisch"]:
        base = d.get("schwellwert_erreicht_am") or d.get("updated_at") or ""
        fulfilled = ({"kommission_notifikation": d["notifikation_kommission_am"]}
                     if d.get("notifikation_kommission_am") else {})
        d["notifikation_deadline"] = dl.evaluate(
            base, "aiact_gpai_systemic", fulfilled=fulfilled, now=now)
    else:
        d["notifikation_deadline"] = None
    return d


def get_klassifizierung(db_path: Path, projekt_name: str, *,
                        now: datetime | None = None) -> dict[str, Any]:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        r = con.execute(
            "SELECT * FROM aiact_gpai_klassifizierung WHERE projekt_name=?",
            (projekt_name,),
        ).fetchone()
    finally:
        con.close()
    d = dict(r) if r else _empty_klass(projekt_name)
    return _enrich_klass(d, now=now)


def save_klassifizierung(db_path: Path, projekt_name: str,
                         data: dict[str, Any]) -> dict[str, Any]:
    ensure_table(db_path)
    override = str(data.get("systemisch_override", "") or "")
    if override not in ("", "ja", "nein"):
        raise ValueError(f"Ungültiger systemisch_override: {override!r}")
    try:
        flop = float(data.get("training_flop") or 0)
    except (TypeError, ValueError):
        raise ValueError("training_flop muss numerisch sein")
    con = _connect(Path(db_path))
    try:
        con.execute(
            """INSERT INTO aiact_gpai_klassifizierung
                 (projekt_name, ist_gpai, training_flop, systemisch_override,
                  copyright_tdm_policy, trainingsdaten_summary,
                  notifikation_kommission_am, schwellwert_erreicht_am, kommentar)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(projekt_name) DO UPDATE SET
                 ist_gpai=excluded.ist_gpai,
                 training_flop=excluded.training_flop,
                 systemisch_override=excluded.systemisch_override,
                 copyright_tdm_policy=excluded.copyright_tdm_policy,
                 trainingsdaten_summary=excluded.trainingsdaten_summary,
                 notifikation_kommission_am=excluded.notifikation_kommission_am,
                 schwellwert_erreicht_am=excluded.schwellwert_erreicht_am,
                 kommentar=excluded.kommentar,
                 updated_at=datetime('now')""",
            (projekt_name, 1 if data.get("ist_gpai") else 0, flop, override,
             str(data.get("copyright_tdm_policy", "") or ""),
             str(data.get("trainingsdaten_summary", "") or ""),
             str(data.get("notifikation_kommission_am", "") or ""),
             str(data.get("schwellwert_erreicht_am", "") or ""),
             str(data.get("kommentar", "") or "")),
        )
        con.commit()
    finally:
        con.close()
    return get_klassifizierung(db_path, projekt_name)


# ── Pflicht-Register / Checks ───────────────────────────────────────────────

def load_checks(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    klass = get_klassifizierung(db_path, projekt_name)
    systemic = klass["systemisch"]
    con = _connect(Path(db_path))
    try:
        rows = con.execute(
            "SELECT * FROM aiact_gpai_checks WHERE projekt_name=?", (projekt_name,)
        ).fetchall()
    finally:
        con.close()
    saved = {r["req_id"]: dict(r) for r in rows}
    out: list[dict[str, Any]] = []
    for req in GPAI_REQUIREMENTS:
        # systemic_only-Pflichten nur anzeigen, wenn systemisches Risiko vorliegt.
        if req["systemic_only"] and not systemic:
            continue
        s = saved.get(req["id"], {})
        out.append({
            **req,
            "status": int(s.get("status", 0) or 0),
            "kommentar": s.get("kommentar", ""),
            "nachweis_ref": s.get("nachweis_ref", ""),
        })
    return out


def save_check(db_path: Path, projekt_name: str, req_id: str, *,
               status: int, kommentar: str = "", nachweis_ref: str = "") -> None:
    if req_id not in _GPAI_IDS:
        raise ValueError(f"Unbekannte GPAI-Anforderung: {req_id!r}")
    status = max(0, min(5, int(status)))
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        con.execute(
            """INSERT INTO aiact_gpai_checks
                 (projekt_name, req_id, status, kommentar, nachweis_ref, updated_at)
               VALUES (?,?,?,?,?,datetime('now'))
               ON CONFLICT(projekt_name, req_id) DO UPDATE SET
                 status=excluded.status, kommentar=excluded.kommentar,
                 nachweis_ref=excluded.nachweis_ref, updated_at=datetime('now')""",
            (projekt_name, req_id, status, kommentar, nachweis_ref),
        )
        con.commit()
    finally:
        con.close()


# ── AI-Office-Incident-Tracking (nur systemisch, Art. 55(1)c) ────────────────

def list_incidents(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        rows = con.execute(
            "SELECT * FROM aiact_gpai_incidents WHERE projekt_name=? "
            "ORDER BY eingetreten_am DESC, id DESC", (projekt_name,)
        ).fetchall()
    finally:
        con.close()
    return [dict(r) for r in rows]


def create_incident(db_path: Path, projekt_name: str, data: dict[str, Any]) -> int:
    status = str(data.get("status", "offen") or "offen")
    if status not in INCIDENT_STATUS:
        raise ValueError(f"Ungültiger Status: {status!r}")
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        cur = con.execute(
            """INSERT INTO aiact_gpai_incidents
                 (projekt_name, titel, beschreibung, eingetreten_am,
                  gemeldet_ai_office_am, status)
               VALUES (?,?,?,?,?,?)""",
            (projekt_name, str(data.get("titel", "") or ""),
             str(data.get("beschreibung", "") or ""),
             str(data.get("eingetreten_am", "") or ""),
             str(data.get("gemeldet_ai_office_am", "") or ""), status),
        )
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def delete_incident(db_path: Path, projekt_name: str, incident_id: int) -> bool:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        cur = con.execute(
            "DELETE FROM aiact_gpai_incidents WHERE id=? AND projekt_name=?",
            (incident_id, projekt_name),
        )
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def summary(db_path: Path, projekt_name: str) -> dict[str, Any]:
    klass = get_klassifizierung(db_path, projekt_name)
    checks = load_checks(db_path, projekt_name)
    erfuellt = [c for c in checks if c["status"] >= 4]
    return {
        "ist_gpai": klass["ist_gpai"],
        "systemisch": klass["systemisch"],
        "ueber_schwellenwert": klass["ueber_schwellenwert"],
        "training_flop": klass["training_flop"],
        "checks_gesamt": len(checks),
        "checks_erfuellt": len(erfuellt),
        "notifikation_faellig": bool(
            klass.get("notifikation_deadline")
            and klass["notifikation_deadline"].get("any_overdue")),
    }


# ── KI-Wizard ─────────────────────────────────────────────────────────────────

def build_gpai_prompt(projekt: dict[str, Any]) -> str:
    req_block = "\n".join(
        f"- {r['id']} {r['titel']} ({r['ref']}"
        f"{'; nur systemisch' if r['systemic_only'] else ''})"
        for r in GPAI_REQUIREMENTS
    )
    return f"""Du bist KI-Compliance-Experte für den EU AI Act (Verordnung 2024/1689),
Kapitel V (GPAI-Modelle, Art. 51-55).

Bewerte das folgende KI-System hinsichtlich GPAI-Klassifizierung und der
GPAI-Pflichten.

## KI-System
- Name: {projekt.get('name', '')}
- Organisation: {projekt.get('organisation', '')}
- Produkt: {projekt.get('produkt', '')}
- Beschreibung: {projekt.get('beschreibung', '')}

## GPAI-Pflichten
{req_block}

Hinweis: Systemisches Risiko ab 10^25 FLOP kumulierter Trainings-Rechenleistung
(Art. 51(2)).

Antworte AUSSCHLIESSLICH als JSON:
{{
  "ist_gpai": true,
  "training_flop": 1.0e24,
  "checks": [
    {{"id": "AIA-GPAI-01", "status": 0, "kommentar": "..."}}
  ]
}}
- status: 0-5. Liste nur die zutreffenden Pflichten.
"""


def build_copyright_policy_prompt(projekt: dict[str, Any]) -> str:
    """Copy/Paste-Prompt für eine GPAI-Urheberrechts-/TDM-Policy (Art. 53(1)c, #1244).

    Erzeugt einen vollständigen, als Dokument speicher-/exportierbaren Markdown-Text.
    """
    return f"""Du bist KI-Compliance-Experte für den EU AI Act (Verordnung 2024/1689),
Art. 53(1)c (GPAI — Urheberrechts-Policy inkl. TDM-Opt-out nach Art. 4(3) DSM-RL).

Erstelle eine vollständige Urheberrechts-/TDM-Opt-out-Policy für das folgende
GPAI-Modell. Adressiere: Respektierung von Rechtevorbehalten (Text-and-Data-Mining-
Opt-out, robots.txt / maschinenlesbare Vorbehalte), Lizenz-Sorgfalt der Trainings-
quellen, Verfahren bei Rechteinhaber-Beschwerden, Verantwortliche/Kontakt.

## GPAI-Modell
- Name: {projekt.get('name', '')}
- Organisation: {projekt.get('organisation', '')}
- Produkt: {projekt.get('produkt', '')}
- Beschreibung: {projekt.get('beschreibung', '')}

Antworte als vollständige Policy in **Markdown** (Überschriften, Absätze, Listen).
Kein JSON. Beginne mit „# Urheberrechts- und TDM-Policy".
"""


def build_training_summary_prompt(projekt: dict[str, Any]) -> str:
    """Copy/Paste-Prompt für die GPAI-Trainingsdaten-Zusammenfassung (Art. 53(1)d, #1244).

    Orientiert sich am AI-Office-Template (Datenquellen-Kategorien, Umfang, Sprachen,
    Modalitäten, urheberrechtlich geschützte Inhalte, Datenverarbeitungsschritte).
    """
    return f"""Du bist KI-Compliance-Experte für den EU AI Act (Verordnung 2024/1689),
Art. 53(1)d (GPAI — öffentliche, hinreichend detaillierte Zusammenfassung der
Trainingsinhalte nach dem AI-Office-Template).

Erstelle die öffentliche Trainingsdaten-Zusammenfassung für das folgende GPAI-Modell.
Gliedere nach dem AI-Office-Template: (1) allgemeine Modell-/Datenbeschreibung,
(2) Datenquellen-Kategorien (öffentliche Datensätze, Web-Crawl, lizenzierte Daten,
nutzergenerierte/eigene Daten), (3) Modalitäten + Sprachen + ungefährer Umfang,
(4) urheberrechtlich geschützte Inhalte + TDM-Opt-out-Behandlung,
(5) Datenverarbeitungs-/Kuratierungsschritte (Filterung, Deduplizierung).

## GPAI-Modell
- Name: {projekt.get('name', '')}
- Organisation: {projekt.get('organisation', '')}
- Produkt: {projekt.get('produkt', '')}
- Beschreibung: {projekt.get('beschreibung', '')}

Antworte als vollständige Zusammenfassung in **Markdown**. Kein JSON. Beginne mit
„# Zusammenfassung der Trainingsinhalte".
"""


def parse_gpai_response(raw: str) -> dict[str, Any]:
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
    if "ist_gpai" in data:
        out["ist_gpai"] = bool(data.get("ist_gpai"))
    if "training_flop" in data:
        try:
            out["training_flop"] = float(data.get("training_flop") or 0)
        except (TypeError, ValueError):
            pass
    checks = data.get("checks")
    if isinstance(checks, list):
        parsed_checks = []
        seen: set[str] = set()
        for c in checks:
            if not isinstance(c, dict):
                continue
            cid = str(c.get("id", "")).strip().upper()
            if cid not in _GPAI_IDS or cid in seen:
                continue
            try:
                st = max(0, min(5, int(c.get("status", 0) or 0)))
            except (TypeError, ValueError):
                st = 0
            parsed_checks.append({"id": cid, "status": st,
                                  "kommentar": str(c.get("kommentar", "") or "")})
            seen.add(cid)
        out["checks"] = parsed_checks
    return out
