"""Phase H — Audit-Bericht → Privatgutachten Konversion.

H-A Foundation (#680-#683):
- convert_audit_to_pg(): zentrale Konvert-Funktion
- get_audit_summary(): Audit-Bericht für Wizard zusammenfassen
- save_konvertierung(): Audit-Trail in gutachten_audit_to_pg_log
- get_vorbefassungs_warning(): Warning-Text für Step 1

H-B Prompts + Befund-Konverter (#684-#686):
- build_pg_questions_prompt(): 5-Kategorien-Beweisfragen-Generator
- parse_pg_questions_response()
- get_audit_gap_candidates(): Score<70 Sections als Befund-Kandidaten

H-C Smart Features (#687-#689):
- FRAMEWORK_TO_NORM_MAP: Auto-Mapping zu normen.json
- build_smart_suggestions_prompt(): Top-3-Lows-KI-Analyse
- generate_pg_thema_from_audit(): Auto-Befüllung Thema-Feld
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from shared import db as _sdb


# ─────────────────────────────────────────────────────────
# Schema — Audit-Trail
# ─────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gutachten_audit_to_pg_log (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    audit_projekt   TEXT NOT NULL,
    pg_projekt      TEXT NOT NULL,
    sv_user         TEXT NOT NULL DEFAULT '',
    konvertiert_am  TEXT NOT NULL DEFAULT (aics_now()),
    anzahl_fragen   INTEGER NOT NULL DEFAULT 0,
    anzahl_befunde  INTEGER NOT NULL DEFAULT 0,
    anzahl_beurteilungen INTEGER NOT NULL DEFAULT 0,
    audit_snapshot_sha256 TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_a2pg_audit ON gutachten_audit_to_pg_log(audit_projekt);
CREATE INDEX IF NOT EXISTS idx_a2pg_pg ON gutachten_audit_to_pg_log(pg_projekt);
"""


def _ensure(db_path: Path) -> None:
    con = _sdb.connect(db_path)
    try:
        con.executescript(_SCHEMA)
        con.commit()
    finally:
        con.close()


# ─────────────────────────────────────────────────────────
# H-A — Audit-Bericht zusammenfassen (für Wizard Step 1)
# ─────────────────────────────────────────────────────────

def get_audit_summary(db_path: Path, audit_projekt_name: str) -> dict[str, Any]:
    """Liefert Stammdaten + Score-Summary eines Audit-Berichts."""
    con = _sdb.connect(db_path)
    try:
        p_row = con.execute(
            "SELECT * FROM gutachten_projects WHERE name=?", (audit_projekt_name,)
        ).fetchone()
        if not p_row:
            return {}
        projekt = dict(p_row)
        try:
            projekt["meta"] = json.loads(projekt.get("meta_json", "{}") or "{}")
        except Exception:
            projekt["meta"] = {}

        # Frameworks aus questions/assessments
        try:
            frameworks = [r[0] for r in con.execute(
                "SELECT DISTINCT framework_section FROM gutachten_questions WHERE project_name=?",
                (audit_projekt_name,)
            ).fetchall() if r[0]]
        except Exception:
            frameworks = []

        # Assessments (Scores)
        assessments = []
        try:
            for r in con.execute(
                """SELECT framework_section, score, comment
                   FROM gutachten_assessments
                   WHERE project_name=?
                   ORDER BY score ASC""",
                (audit_projekt_name,),
            ).fetchall():
                assessments.append(dict(r))
        except Exception:
            pass

        scores = [int(a["score"] or 0) for a in assessments if a.get("score") is not None]
        return {
            "name": projekt["name"],
            "firma": projekt.get("meta", {}).get("unternehmen") or projekt.get("name", ""),
            "created_at": projekt.get("created_at", ""),
            "frameworks": frameworks,
            "anzahl_assessments": len(assessments),
            "min_score": min(scores) if scores else None,
            "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
            "top_3_lows": assessments[:3],
        }
    finally:
        con.close()


def list_audit_projekte(db_path: Path) -> list[dict[str, Any]]:
    """Liste aller Audit-Berichte mit Kurz-Summary."""
    con = _sdb.connect(db_path)
    try:
        out = []
        try:
            for r in con.execute(
                "SELECT name, created_at FROM gutachten_projects ORDER BY created_at DESC"
            ).fetchall():
                out.append(dict(r))
        except Exception:
            pass
        return out
    finally:
        con.close()


# ─────────────────────────────────────────────────────────
# H-I-3 — Audit-Gap-Kandidaten (Score < 70 als Befund-Kandidaten)
# ─────────────────────────────────────────────────────────

def get_audit_gap_candidates(db_path: Path, audit_projekt_name: str,
                             max_score: int = 70) -> list[dict[str, Any]]:
    """Liefert alle Audit-Sections mit Score < max_score — als Befund-Kandidaten."""
    con = _sdb.connect(db_path)
    try:
        try:
            rows = con.execute(
                """SELECT framework_section, score, comment
                   FROM gutachten_assessments
                   WHERE project_name=? AND score < ?
                   ORDER BY score ASC""",
                (audit_projekt_name, max_score),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []
    finally:
        con.close()


# ─────────────────────────────────────────────────────────
# H-A — Vorbefassungs-Warnung (#682)
# ─────────────────────────────────────────────────────────

VORBEFASSUNG_WARNING = (
    "⚠ Hinweis zur Vorbefassung\n"
    "Mit Erstellung dieses Privatgutachtens werden Sie zum Audit-Bericht-Ersteller "
    "UND PG-Ersteller für diesen Firmen.\n\n"
    "Folge: Sollte aus diesem Sachverhalt später ein Gerichtsverfahren entstehen, "
    "sind Sie für ein Gerichtsgutachten in dieser Sache befangen (§ 406 ZPO).\n\n"
    "Der Befangenheits-Check (G0-9) wird dies automatisch melden."
)

# #705 — Audit als integraler Teil desselben Gutachtenauftrags
EINHEITLICHER_AUFTRAG_HINWEIS = (
    "ℹ Audit ist Teil dieses Gutachtens (einheitlicher Auftrag)\n"
    "Der Compliance-Audit wurde im Rahmen desselben Gutachtenauftrags durchgeführt "
    "und bildet die Befundgrundlage (§ 407a ZPO — eigene Befunderhebung).\n\n"
    "Es liegt KEINE Vorbefassung i.S.d. § 406 ZPO vor, da der Audit keine separate "
    "frühere Tätigkeit (als Berater/Entwickler/Projektleiter) darstellt, sondern "
    "integraler Bestandteil der Begutachtung ist.\n\n"
    "Hinweis: Die Bewertung gilt nur, solange Audit und Gutachten tatsächlich auf "
    "EINEM Auftrag beruhen. Bei einem zeitlich/vertraglich getrennten Vor-Audit "
    "wählen Sie stattdessen 'Separater Vor-Audit'."
)

# #705 — rechtlicher Dokumentationstext für den Verfahrensgang (Variante 2)
EINHEITLICHER_AUFTRAG_DOKU = (
    "Der zugrunde liegende Compliance-Audit wurde im Rahmen desselben "
    "Gutachtenauftrags erstellt und bildet die Befundgrundlage (§ 407a ZPO eigene "
    "Befunderhebung). Eine Vorbefassung i.S.d. § 406 ZPO liegt nicht vor, da der "
    "Audit kein zeitlich/vertraglich getrennter früherer Auftrag ist, sondern "
    "integraler Bestandteil dieser Begutachtung."
)


def get_vorbefassungs_warning(db_path: Path, audit_projekt_name: str,
                              audit_teil_des_gutachtens: bool = False) -> dict[str, Any]:
    """Liefert variantenabhängigen Hinweis-Text + Sub-Hinweise.

    audit_teil_des_gutachtens=False (Default): Vorbefassung → Akzeptanz-Pflicht.
    audit_teil_des_gutachtens=True: einheitlicher Auftrag → keine Vorbefassung.
    """
    summary = get_audit_summary(db_path, audit_projekt_name)
    if audit_teil_des_gutachtens:
        return {
            "warning": EINHEITLICHER_AUFTRAG_HINWEIS,
            "audit_firma": summary.get("firma", ""),
            "audit_datum": summary.get("created_at", ""),
            "akzeptanz_pflicht": False,
            "einheitlicher_auftrag": True,
        }
    return {
        "warning": VORBEFASSUNG_WARNING,
        "audit_firma": summary.get("firma", ""),
        "audit_datum": summary.get("created_at", ""),
        "akzeptanz_pflicht": True,
        "einheitlicher_auftrag": False,
    }


# ─────────────────────────────────────────────────────────
# H-A — Audit-Trail (#683)
# ─────────────────────────────────────────────────────────

def save_konvertierung(
    db_path: Path,
    audit_projekt: str,
    pg_projekt: str,
    sv_user: str,
    anzahl_fragen: int = 0,
    anzahl_befunde: int = 0,
    anzahl_beurteilungen: int = 0,
    audit_snapshot_sha256: str = "",
) -> int:
    _ensure(db_path)
    con = _sdb.connect(db_path)
    try:
        cur = con.execute(
            """INSERT INTO gutachten_audit_to_pg_log
                 (audit_projekt, pg_projekt, sv_user, anzahl_fragen, anzahl_befunde,
                  anzahl_beurteilungen, audit_snapshot_sha256)
               VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id""",
            (audit_projekt, pg_projekt, sv_user, anzahl_fragen, anzahl_befunde,
             anzahl_beurteilungen, audit_snapshot_sha256),
        )
        row = cur.fetchone()
        con.commit()
        return int(row[0])
    finally:
        con.close()


def list_konvertierungen(db_path: Path, audit_projekt: str | None = None,
                         pg_projekt: str | None = None) -> list[dict[str, Any]]:
    _ensure(db_path)
    con = _sdb.connect(db_path)
    try:
        if audit_projekt:
            rows = con.execute(
                "SELECT * FROM gutachten_audit_to_pg_log WHERE audit_projekt=? ORDER BY konvertiert_am DESC",
                (audit_projekt,),
            ).fetchall()
        elif pg_projekt:
            rows = con.execute(
                "SELECT * FROM gutachten_audit_to_pg_log WHERE pg_projekt=? ORDER BY konvertiert_am DESC",
                (pg_projekt,),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM gutachten_audit_to_pg_log ORDER BY konvertiert_am DESC LIMIT 100"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


# ─────────────────────────────────────────────────────────
# H-A — Zentrale Konvert-Funktion (#680)
# ─────────────────────────────────────────────────────────

def convert_audit_to_pg(
    db_path: Path,
    audit_projekt_name: str,
    pg_name: str,
    sv_name: str,
    auftrags_art: str = "Tauglichkeitsprüfung",
    auftrags_datum: str | None = None,
    auftrags_nummer: str | None = None,
    honorarvereinbarung: str | None = None,
    thema: str | None = None,
    befangenheits_akzeptanz: bool = False,
    audit_teil_des_gutachtens: bool = False,
) -> dict[str, Any]:
    """Zentrale Konvert-Funktion.

    Legt neues PG an mit:
    - gutachten_art='privat'
    - meta_json.audit_source = {audit_projekt, audit_datum, snapshot_sha256, einheitlicher_auftrag}
    - Verfahrensgang-Eintrag 'Privatgutachten aus Audit-Bericht ... abgeleitet'

    audit_teil_des_gutachtens=True (#705): Audit ist Teil desselben Gutachtenauftrags
    → keine Vorbefassung i.S.d. § 406 ZPO → befangenheits_akzeptanz nicht erforderlich.

    Liefert {pg_name, audit_summary, konvertierungs_id}.
    """
    # #705 — Akzeptanz nur erforderlich, wenn der Audit eine separate Vorbefassung ist
    if not audit_teil_des_gutachtens and not befangenheits_akzeptanz:
        raise ValueError("Befangenheits-Akzeptanz ist Pflicht (#682)")

    from gutachten import gerichts_db as _gdb
    summary = get_audit_summary(db_path, audit_projekt_name)
    if not summary:
        raise ValueError(f"Audit-Bericht '{audit_projekt_name}' nicht gefunden")

    # H-I-10 Auto-Thema falls leer
    if not thema:
        thema = generate_pg_thema_from_audit(summary, auftrags_art)

    # SHA-256 des Audit-Snapshots (für Audit-Trail-Versionsanker)
    import hashlib
    snapshot_data = json.dumps(summary, sort_keys=True, default=str).encode("utf-8")
    snapshot_sha256 = hashlib.sha256(snapshot_data).hexdigest()

    # PG-Stammdaten anlegen
    _gdb.save_gerichts_projekt(
        db_path,
        name=pg_name,
        gutachten_art="privat",
        auftraggeber=summary.get("firma", ""),
        auftrags_art=auftrags_art,
        auftrags_datum=auftrags_datum or datetime.now().strftime("%Y-%m-%d"),
        auftrags_nummer=auftrags_nummer or "",
        honorarvereinbarung=honorarvereinbarung or "",
        thema=thema,
        sv_name=sv_name,
        meta={
            "audit_source": {
                "audit_projekt": audit_projekt_name,
                "audit_datum": summary.get("created_at", ""),
                "audit_firma": summary.get("firma", ""),
                "snapshot_sha256": snapshot_sha256,
                "konvertiert_am": datetime.now().isoformat(timespec="seconds"),
                "konvertiert_von": sv_name,
                "einheitlicher_auftrag": bool(audit_teil_des_gutachtens),
            },
        },
    )

    # Verfahrensereignis dokumentieren — variantenabhängige rechtliche Würdigung (#705)
    if audit_teil_des_gutachtens:
        rechts_doku = " " + EINHEITLICHER_AUFTRAG_DOKU
        ereignis_typ = "sonstiges"
    else:
        rechts_doku = (" Hinweis: Der Audit stellt eine Vorbefassung i.S.d. § 406 ZPO dar "
                       "(Befangenheit für ein späteres Gerichtsgutachten in dieser Sache).")
        ereignis_typ = "befangenheitspruefung"
    _gdb.save_verfahrensereignis(
        db_path,
        projekt_name=pg_name,
        ereignis_typ=ereignis_typ,
        titel=f"Privatgutachten aus Audit-Bericht '{audit_projekt_name}' abgeleitet",
        beschreibung=(
            f"Privatgutachten erstellt am {datetime.now().strftime('%d.%m.%Y')} "
            f"basierend auf Compliance-Audit-Bericht '{audit_projekt_name}' (Snapshot-SHA-256: "
            f"{snapshot_sha256[:16]}...). "
            f"Auftraggeber: {summary.get('firma', '')}. "
            f"Audit umfasst {summary.get('anzahl_assessments', 0)} Section-Bewertungen "
            f"(Frameworks: {', '.join(summary.get('frameworks', []))})."
            + rechts_doku
        ),
        empfaenger=[],
    )

    # Audit-Trail
    konv_id = save_konvertierung(
        db_path, audit_projekt=audit_projekt_name, pg_projekt=pg_name,
        sv_user=sv_name, audit_snapshot_sha256=snapshot_sha256,
    )

    return {
        "pg_name": pg_name,
        "audit_summary": summary,
        "konvertierungs_id": konv_id,
        "audit_snapshot_sha256": snapshot_sha256,
    }


# ─────────────────────────────────────────────────────────
# H-I-2 — Beweisfragen-Prompt-Generator (5 Kategorien) (#684)
# ─────────────────────────────────────────────────────────

PG_QUESTION_CATEGORIES = ("compliance", "prio", "sot", "wirkung", "empfehlung")

PG_TEMPLATES_PER_AUFTRAG = {
    "Tauglichkeitsprüfung": {
        "compliance": "Ist das Unternehmen {firma} compliant mit {frameworks}?",
        "prio": "Werden die identifizierten Hochrisiko-Gaps mit angemessener Priorität adressiert?",
        "sot": "Entspricht die IT-Sicherheits-Architektur dem aktuellen Stand der Technik?",
        "wirkung": "Welche betrieblichen Auswirkungen haben die festgestellten Compliance-Lücken?",
        "empfehlung": "Welche Sofortmaßnahmen sind zur Schließung der Top-3-Gaps erforderlich?",
    },
    "Beweissicherung": {
        "compliance": "Sind die Compliance-Nachweise aus dem Audit gerichtsfest dokumentiert?",
        "prio": "Welche Beweise sind für eine spätere gerichtliche Verwertung essentiell?",
        "sot": "Wurden Beweissicherung-Standards (ISO/IEC 27037) eingehalten?",
        "wirkung": "Welche Beweismittel rekonstruieren den IT-Zustand zum Zeitpunkt T?",
        "empfehlung": "Welche zusätzlichen Sicherungen sind sofort erforderlich?",
    },
    "Schaden-Gutachten": {
        "compliance": "Welche Compliance-Verstöße sind ursächlich für den Schaden?",
        "prio": "Welche Vorfälle hatten die höchste Schadenswirkung?",
        "sot": "Wäre der Schaden bei Einhaltung des Stands der Technik vermeidbar gewesen?",
        "wirkung": "Wie hoch ist der quantifizierte Schaden (direkt + indirekt)?",
        "empfehlung": "Welche Maßnahmen verhindern künftige Schäden?",
    },
    "Wertgutachten": {
        "compliance": "Erfüllt das System die Mindest-Compliance für den Marktwert?",
        "prio": "Welche Mängel reduzieren den Marktwert am stärksten?",
        "sot": "Entspricht der technische Zustand dem Stand der Technik?",
        "wirkung": "Wie hoch ist die Wertminderung durch Compliance-Mängel?",
        "empfehlung": "Welche Investition stellt den Marktwert wieder her?",
    },
    "Kaufberatung": {
        "compliance": "Erfüllt das System vor Kauf die Mindest-Compliance?",
        "prio": "Welche Mängel sind vor Kauf zu beheben?",
        "sot": "Welche Lücken zum Stand der Technik bestehen?",
        "wirkung": "Welche Folgekosten entstehen aus den Compliance-Lücken?",
        "empfehlung": "Sollte das System gekauft werden? Unter welchen Bedingungen?",
    },
    "Sonstiges": {
        "compliance": "Welche Compliance-Aspekte sind für die Fragestellung relevant?",
        "prio": "Was sind die kritischsten Punkte?",
        "sot": "Welche Standards sind anwendbar?",
        "wirkung": "Welche Auswirkungen entstehen aus den Befunden?",
        "empfehlung": "Welche Maßnahmen sind erforderlich?",
    },
}


def build_pg_questions_prompt(
    audit_summary: dict[str, Any],
    auftrags_art: str = "Tauglichkeitsprüfung",
    kategorien: list[str] | None = None,
) -> str:
    """ChatGPT-Prompt zur Generierung von 5-8 strukturierten Beweisfragen."""
    kategorien = kategorien or list(PG_QUESTION_CATEGORIES)
    templates = PG_TEMPLATES_PER_AUFTRAG.get(auftrags_art, PG_TEMPLATES_PER_AUFTRAG["Sonstiges"])

    frameworks = audit_summary.get("frameworks", [])
    fws = ", ".join(frameworks) or "(keine spezifiziert)"
    top_lows = audit_summary.get("top_3_lows", []) or []
    lows_text = "\n".join(
        f"- {a.get('framework_section', '?')}: Score {a.get('score', '?')}/100"
        for a in top_lows
    ) or "(keine niedrigen Scores)"

    templates_block = "\n".join(
        f"- **{k}**: {templates.get(k, '(kein Template)')}"
        for k in kategorien
    )

    return f"""Du unterstützt einen IT-Sachverständigen bei der Erstellung eines Privatgutachtens
(Auftrags-Art: {auftrags_art}). Aus einem vorliegenden Compliance-Audit-Bericht sollen
**strukturierte Beweisfragen** generiert werden.

# Audit-Kontext
- Firma: {audit_summary.get('firma', '?')}
- Frameworks: {fws}
- Anzahl Assessments: {audit_summary.get('anzahl_assessments', 0)}
- Durchschnitts-Score: {audit_summary.get('avg_score', '?')}/100
- Minimum-Score: {audit_summary.get('min_score', '?')}/100

# Top-3-Lows
{lows_text}

# Template-Vorlagen für Auftrags-Art '{auftrags_art}'
{templates_block}

Generiere **5-8 konkrete Beweisfragen**, gegliedert nach den oben aufgelisteten Kategorien.
Jede Frage soll präzise sein und sich auf den konkreten Audit-Kontext beziehen.

Antworte **ausschließlich** als JSON:
```json
{{
  "fragen": [
    {{
      "nr": 1,
      "kategorie": "compliance",
      "frage_text": "Ist das Unternehmen '{audit_summary.get('firma', 'X')}' compliant mit den Anforderungen von ...?"
    }}
  ]
}}
```
"""


def parse_pg_questions_response(raw: str) -> list[dict[str, Any]]:
    """Parst ChatGPT-Antwort und liefert Liste der Beweisfragen."""
    text = (raw or "").strip()
    for marker in ("```json", "```"):
        if marker in text:
            parts = text.split(marker)
            if len(parts) >= 2:
                text = parts[1].split("```")[0]
                break
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        return []
    try:
        data = json.loads(text[start:end + 1])
        return data.get("fragen", []) or []
    except json.JSONDecodeError:
        return []


def apply_questions_to_pg(db_path: Path, pg_name: str, fragen: list[dict[str, Any]]) -> int:
    """Speichert geparste Beweisfragen im PG."""
    from gutachten import gerichts_db as _gdb
    count = 0
    for q in fragen:
        try:
            _gdb.save_beweisfrage(
                db_path,
                projekt_name=pg_name,
                nr=int(q.get("nr") or count + 1),
                frage_text=q.get("frage_text", ""),
                antwort_kurz="",
                antwort_text="",
            )
            count += 1
        except Exception:
            pass
    return count


# ─────────────────────────────────────────────────────────
# H-I-3 — Befund-Kandidaten als leere Befunde anlegen (mit Disclaimer)
# ─────────────────────────────────────────────────────────

PG_BEFUND_DISCLAIMER = (
    "[KANDIDAT aus Audit-Bericht — bitte persönlich neu formulieren nach § 407a ZPO]"
)


def create_befund_skeleton_from_gap(
    db_path: Path, pg_name: str, gap: dict[str, Any], nr: str
) -> int:
    """Erzeugt einen leeren Befund-Skeleton, der den Audit-Gap als Memo enthält.

    Der Befund-Text bleibt LEER — SV muss persönlich formulieren (§ 407a).
    Der Audit-Gap-Inhalt wird in zeugen_text gespeichert als 'Quelle'.
    """
    from gutachten import gerichts_db as _gdb
    audit_section = gap.get("framework_section", "")
    audit_score = gap.get("score", 0)
    audit_comment = (gap.get("comment") or "")[:500]

    titel = f"Compliance-Lücke: {audit_section}"
    zeugen = (
        f"{PG_BEFUND_DISCLAIMER}\n"
        f"Quell-Audit-Section: {audit_section}\n"
        f"Score: {audit_score}/100\n"
        f"Audit-Kommentar: {audit_comment}"
    )

    return _gdb.save_befund(
        db_path,
        projekt_name=pg_name,
        nr=nr,
        titel=titel,
        beschreibung_text="",  # Pflicht: SV formuliert persönlich
        methode="interview",   # Default
        werkzeug_name=audit_section.split(".")[0] if "." in audit_section else "",
        werkzeug_version="",
        zeugen_text=zeugen,
    )


# ─────────────────────────────────────────────────────────
# H-I-4 — Norm-Mapping aus Frameworks (#687)
# ─────────────────────────────────────────────────────────

# Mapping Framework-Name → Norm-ID in gutachten/data/normen.json
FRAMEWORK_TO_NORM_MAP = {
    "ISO 27001": "iso-27001",
    "ISO/IEC 27001": "iso-27001",
    "ISO 27001:2022": "iso-27001",
    "OWASP": "owasp-asvs",
    "OWASP ASVS": "owasp-asvs",
    "OWASP ASVS 4.0.3": "owasp-asvs",
    "BSI": "bsi-grundschutz",
    "BSI IT-Grundschutz": "bsi-grundschutz",
    "BSI-Grundschutz": "bsi-grundschutz",
    "DSGVO": "dsgvo",
    "GDPR": "dsgvo",
    "ISO 25010": "iso-25010",
    "ISO/IEC 25010": "iso-25010",
    "ISO 27037": "iso-27037",
    "DIN EN 16775": "din-en-16775",
}


def map_framework_to_norm(framework: str) -> str | None:
    """Liefert Norm-ID (aus normen.json) für einen Framework-Namen."""
    if not framework:
        return None
    f = framework.strip()
    # Direct hit
    if f in FRAMEWORK_TO_NORM_MAP:
        return FRAMEWORK_TO_NORM_MAP[f]
    # Fuzzy: enthält Sub-Match
    for key, val in FRAMEWORK_TO_NORM_MAP.items():
        if key.lower() in f.lower() or f.lower() in key.lower():
            return val
    return None


# ─────────────────────────────────────────────────────────
# H-I-9 — Smart Suggestions (Top-3-Lows Analyse) (#688)
# ─────────────────────────────────────────────────────────

def build_smart_suggestions_prompt(audit_summary: dict[str, Any]) -> str:
    top_lows = audit_summary.get("top_3_lows", []) or []
    if not top_lows:
        return ""
    lows = "\n".join(
        f"- {a.get('framework_section', '?')}: Score {a.get('score', '?')}/100 — "
        f"{(a.get('comment') or '')[:200]}"
        for a in top_lows
    )
    return f"""Du bist IT-Sachverständiger. Analysiere die folgenden Top-3-Gaps aus einem
Compliance-Audit:

{lows}

Beantworte als JSON:
```json
{{
  "hoechste_auswirkung": "Welcher Gap hat die größte Wirkung? Warum?",
  "verknuepfungen": "Wie hängen die 3 Gaps untereinander zusammen?",
  "prio_reihenfolge": ["Gap-1-zuerst", "Gap-2-danach", "Gap-3-zuletzt"],
  "sofortmassnahme": "Welche Maßnahme schließt den ersten Gap am schnellsten?"
}}
```
"""


def parse_smart_suggestions_response(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    for m in ("```json", "```"):
        if m in text:
            text = text.split(m)[1].split("```")[0] if m == "```json" else text.split(m)[1]
            break
    s, e = text.find("{"), text.rfind("}")
    if s < 0 or e < 0:
        return {}
    try:
        return json.loads(text[s:e + 1])
    except json.JSONDecodeError:
        return {}


# ─────────────────────────────────────────────────────────
# H-I-10 — Thema-Auto-Befüllung (#689)
# ─────────────────────────────────────────────────────────

def generate_pg_thema_from_audit(audit_summary: dict[str, Any],
                                 auftrags_art: str = "Tauglichkeitsprüfung") -> str:
    firma = audit_summary.get("firma", "") or "(unbekannt)"
    frameworks = audit_summary.get("frameworks", []) or []
    fws = ", ".join(frameworks) if frameworks else "(keine spezifiziert)"
    datum = audit_summary.get("created_at", "")
    datum_str = (datum or "")[:10] or "(unbekannt)"
    return (
        f"{auftrags_art} der IT-Compliance des Unternehmens '{firma}' "
        f"basierend auf Compliance-Audit-Bericht vom {datum_str} "
        f"über die Frameworks: {fws}."
    )
