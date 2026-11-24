"""Compliance-Audit-Adapter für die zentrale Word-Vorlagen-Engine (#1730).

Stellt ``COMPLIANCE_AUDIT_VARIABLES`` (die Variablenliste, die der Anwender im
Admin-UI vor dem Hochladen einsieht, #1092) und ``build_compliance_audit_context``
bereit; ``shared.templates.schema`` aggregiert beides über *guarded imports*.

Zwei Festlegungen, die den Aufbau erklären:

* **Der gerechnete Stand ist führend.** Stufe, Quote und Abdeckung kommen aus
  ``compliance_audit.status`` — derselben Quelle wie Wasserstandsmeldung,
  Dashboard und Berichts-Center (#1713). Eine Vorlage kann damit keine andere
  Zahl drucken als die App anzeigt.
* **Der KI-Text ist Beiwerk.** ``bericht`` trägt den gespeicherten
  Auditbericht-Entwurf, falls einer existiert; fehlt er, bleiben die Felder leer
  und die Vorlage rendert trotzdem.

Der Kontext ist Jinja-robust: **keine ``None``-Werte**. Jinja würde sie als
„None" in das Dokument drucken, und ein fehlendes Feld in einer Kundenvorlage
darf keinen Export verhindern.

Top-Level-Keys: ``projekt``, ``meta``, ``frameworks``, ``fragen``, ``luecken``,
``bericht``, ``wasserstand``.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

#: Historischer Dateiname — die Tabellen des Audits liegen weiter in der
#: Gutachten-DB (bewusst, siehe #1713: keine Migration auf Kundenbestand).
DB_PATH = Path("data/db/gutachten.sqlite")

# ── Variablen-Schema ────────────────────────────────────────────────────────
# Ein Eintrag: {"key", "typ", "beschreibung", "pflicht"}.
COMPLIANCE_AUDIT_VARIABLES: list[dict[str, Any]] = [
    {"key": "projekt.name", "typ": "text",
     "beschreibung": "Name des Audit-Projekts", "pflicht": True},
    {"key": "projekt.unternehmen", "typ": "text",
     "beschreibung": "Auditierte Organisation / auditiertes Unternehmen",
     "pflicht": True},
    {"key": "projekt.pruefungsfokus", "typ": "text",
     "beschreibung": "Prüfungsfokus / Auftragsgegenstand des Audits", "pflicht": False},
    {"key": "projekt.frameworks", "typ": "liste",
     "beschreibung": "Geprüfte Frameworks als Textliste (z. B. NIS2, CRA)",
     "pflicht": False},
    {"key": "projekt.frameworks_text", "typ": "text",
     "beschreibung": "Dieselben Frameworks als ein Text, mit Komma getrennt — "
                     "praktisch für Deckblatt und Fußzeile",
     "pflicht": False},

    {"key": "meta.stufe_label", "typ": "text",
     "beschreibung": "Gerechnete Compliance-Stufe im Klartext: vollständig / "
                     "weitgehend / teilweise / nicht compliant",
     "pflicht": False},
    {"key": "meta.stufe", "typ": "text",
     "beschreibung": "Dieselbe Stufe als Schlüsselwort "
                     "(vollstaendig|weitgehend|teilweise|nicht) — für Bedingungen "
                     "in der Vorlage",
     "pflicht": False},
    {"key": "meta.bedeutung", "typ": "text",
     "beschreibung": "Erläuterung der Stufe für den Kunden (ein Satz)",
     "pflicht": False},
    {"key": "meta.quote_prozent", "typ": "zahl",
     "beschreibung": "Erfüllungsquote in Prozent. Offene Fragen zählen wie "
                     "„nicht erfüllt“ — die belastbare Zahl für den Kunden",
     "pflicht": False},
    {"key": "meta.quote_bewertet_prozent", "typ": "zahl",
     "beschreibung": "Erfüllungsquote nur über die bereits beantworteten Fragen — "
                     "trennt „schlecht erfüllt“ von „noch nicht erhoben“",
     "pflicht": False},
    {"key": "meta.abdeckung_prozent", "typ": "zahl",
     "beschreibung": "Anteil der beantworteten Fragen in Prozent (Erhebungsstand)",
     "pflicht": False},
    {"key": "meta.fragen", "typ": "objekt",
     "beschreibung": "Zählung der Fragen: gesamt, anwendbar, bewertet, erfuellt, "
                     "teilweise, nicht_erfuellt, nicht_anwendbar, offen",
     "pflicht": False},
    {"key": "meta.anzahl_frameworks", "typ": "zahl",
     "beschreibung": "Anzahl der geprüften Frameworks", "pflicht": False},
    {"key": "meta.anzahl_luecken", "typ": "zahl",
     "beschreibung": "Anzahl der Lücken (nicht erfüllt, teilweise, offen)",
     "pflicht": False},
    {"key": "meta.datum", "typ": "text",
     "beschreibung": "Berichtsdatum (YYYY-MM-DD)", "pflicht": False},

    {"key": "frameworks", "typ": "liste",
     "beschreibung": "Stand je Framework (framework, stufe, stufe_label, "
                     "quote_prozent, abdeckung_prozent, fragen{…})",
     "pflicht": False},
    {"key": "fragen", "typ": "liste",
     "beschreibung": "Alle Fragen (nr, framework, fundstelle, thema, frage, "
                     "antwort, erfuellung, erfuellung_label, kommentar)",
     "pflicht": False},
    {"key": "luecken", "typ": "liste",
     "beschreibung": "Nur die Lücken, nicht erfüllt zuerst (framework, fundstelle, "
                     "thema, frage, erfuellung, erfuellung_label, kommentar)",
     "pflicht": False},

    {"key": "bericht.gesamtbewertung", "typ": "text",
     "beschreibung": "KI-Auditbericht-Entwurf: Gesamtbild in einem Satz "
                     "(leer, solange kein Entwurf erzeugt wurde)",
     "pflicht": False},
    {"key": "bericht.zusammenfassung", "typ": "text",
     "beschreibung": "KI-Entwurf: Zusammenfassung für die Leitung", "pflicht": False},
    {"key": "bericht.fazit", "typ": "text",
     "beschreibung": "KI-Entwurf: Fazit", "pflicht": False},
    {"key": "bericht.framework_bewertungen", "typ": "liste",
     "beschreibung": "KI-Entwurf je Framework (framework, bewertung, staerken[], "
                     "luecken[])",
     "pflicht": False},
    {"key": "bericht.handlungsempfehlungen", "typ": "liste",
     "beschreibung": "KI-Entwurf: Maßnahmen (massnahme, begruendung, prioritaet, "
                     "aufwand)",
     "pflicht": False},

    {"key": "wasserstand.stufe_label", "typ": "text",
     "beschreibung": "Stufe der letzten gespeicherten Wasserstandsmeldung "
                     "(leer, wenn noch keine erstellt wurde)",
     "pflicht": False},
    {"key": "wasserstand.datum", "typ": "text",
     "beschreibung": "Zeitpunkt der letzten Wasserstandsmeldung", "pflicht": False},
]


# ── Helfer ──────────────────────────────────────────────────────────────────

def _s(value: Any) -> str:
    """Niemals None: gibt einen sauberen String zurück."""
    return "" if value is None else str(value)


def _i(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _f(value: Any, default: float = 0.0) -> float:
    """Zahl oder Vorgabe — ``None`` wird zu 0, nicht zu „None“ im Dokument."""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _liste(value: Any) -> list[str]:
    """Textliste; Einzelwerte und Müll werden verträglich behandelt."""
    if isinstance(value, (list, tuple)):
        return [_s(v) for v in value if _s(v)]
    s = _s(value)
    return [s] if s else []


def _fragen_zaehlung(block: dict[str, Any]) -> dict[str, int]:
    """Die Zählung aus ``status`` — immer alle Schlüssel, immer ganze Zahlen."""
    roh = block.get("fragen") or {}
    felder = ("gesamt", "anwendbar", "bewertet", "erfuellt", "teilweise",
              "nicht_erfuellt", "nicht_anwendbar", "offen")
    return {f: _i(roh.get(f)) for f in felder}


def _bericht(roh: str | None) -> dict[str, Any]:
    """KI-Entwurf normalisieren — ein kaputter Entwurf darf nichts verhindern."""
    leer: dict[str, Any] = {
        "gesamtbewertung": "", "zusammenfassung": "", "fazit": "",
        "framework_bewertungen": [], "handlungsempfehlungen": [],
    }
    if not roh:
        return leer
    try:
        d = json.loads(roh)
    except (ValueError, TypeError):
        return leer
    if not isinstance(d, dict):
        return leer
    return {
        "gesamtbewertung": _s(d.get("gesamtbewertung")),
        "zusammenfassung": _s(d.get("zusammenfassung")),
        "fazit": _s(d.get("fazit")),
        "framework_bewertungen": [
            {"framework": _s(b.get("framework")),
             "bewertung": _s(b.get("bewertung")),
             "staerken": _liste(b.get("staerken")),
             "luecken": _liste(b.get("luecken"))}
            for b in (d.get("framework_bewertungen") or [])
            if isinstance(b, dict)
        ],
        "handlungsempfehlungen": [
            {"massnahme": _s(e.get("massnahme")),
             "begruendung": _s(e.get("begruendung")),
             "prioritaet": _s(e.get("prioritaet")),
             "aufwand": _s(e.get("aufwand"))}
            for e in (d.get("handlungsempfehlungen") or [])
            if isinstance(e, dict)
        ],
    }


def _letzter_wasserstand(db_path: Path, projekt: str) -> dict[str, Any]:
    """Kopf der letzten Wasserstandsmeldung (best effort)."""
    leer = {"stufe": "", "stufe_label": "", "quote_prozent": 0.0, "datum": "",
            "provider": ""}
    try:
        from compliance_audit.db import list_wasserstand
        from compliance_audit.status import STUFEN_LABELS

        rows = list_wasserstand(db_path, projekt, limit=1) or []
        if not rows:
            return leer
        r = rows[0]
        stufe = _s(r.get("stufe"))
        return {
            "stufe": stufe,
            "stufe_label": STUFEN_LABELS.get(stufe, stufe),
            "quote_prozent": _f(r.get("quote_prozent")),
            "datum": _s(r.get("created_at")),
            "provider": _s(r.get("provider")),
        }
    except Exception:
        return leer


# ── Kontext-Builder ─────────────────────────────────────────────────────────

def build_compliance_audit_context(db_path: Path | str,
                                   projekt_name: str) -> dict[str, Any]:
    """Baut einen Jinja-robusten Render-Kontext für ein Compliance-Audit.

    Liefert immer ein vollständiges, ``None``-freies Dict — auch für ein
    unbekanntes Projekt (dann leere Vorgaben mit dem übergebenen Namen), damit
    eine Kundenvorlage nie mit einem Rendering-Fehler abbricht.
    """
    db_path = Path(db_path)
    projekt_name = _s(projekt_name)

    from gutachten.db import load_gutachten_draft, load_project, load_questions

    from compliance_audit.status import (ERFUELLUNG_LABELS, build_status,
                                         erfuellung_of)

    roh = load_project(db_path, projekt_name) or {}
    fragen_roh = load_questions(db_path, projekt_name) or []
    stand = build_status(fragen_roh)

    frameworks = _liste(roh.get("frameworks"))
    projekt = {
        "name": _s(roh.get("name")) or projekt_name,
        "unternehmen": _s(roh.get("unternehmen")),
        "pruefungsfokus": _s(roh.get("pruefungsfokus")),
        "frameworks": frameworks,
        "frameworks_text": ", ".join(frameworks),
        "erstellt_am": _s(roh.get("created_at")),
    }

    fragen: list[dict[str, Any]] = []
    for q in fragen_roh:
        erf = erfuellung_of(q)
        fragen.append({
            "nr": _i(q.get("question_num")),
            "framework": _s(q.get("framework")),
            "fundstelle": _s(q.get("section_ref")),
            "thema": _s(q.get("thema")),
            "frage": _s(q.get("frage")),
            "antwort": _s(q.get("antwort")),
            "erfuellung": erf,
            "erfuellung_label": ERFUELLUNG_LABELS.get(erf, erf),
            "kommentar": _s(q.get("kommentar")),
        })

    je_framework: list[dict[str, Any]] = []
    for blk in (stand.get("frameworks") or []):
        je_framework.append({
            "framework": _s(blk.get("framework")),
            "stufe": _s(blk.get("stufe")),
            "stufe_label": _s(blk.get("label")),
            "quote_prozent": _f(blk.get("quote_prozent")),
            "abdeckung_prozent": _f(blk.get("abdeckung_prozent")),
            "fragen": _fragen_zaehlung(blk),
        })

    luecken: list[dict[str, Any]] = []
    for lk in (stand.get("luecken") or []):
        erf = _s(lk.get("erfuellung"))
        luecken.append({
            "framework": _s(lk.get("framework")),
            "fundstelle": _s(lk.get("section_ref")),
            "thema": _s(lk.get("thema")),
            "frage": _s(lk.get("frage")),
            "erfuellung": erf,
            "erfuellung_label": ERFUELLUNG_LABELS.get(erf, erf),
            "kommentar": _s(lk.get("kommentar")),
        })

    meta = {
        "stufe": _s(stand.get("stufe")),
        "stufe_label": _s(stand.get("label")),
        "bedeutung": _s(stand.get("bedeutung")),
        "quote_prozent": _f(stand.get("quote_prozent")),
        "quote_bewertet_prozent": _f(stand.get("quote_bewertet_prozent")),
        "abdeckung_prozent": _f(stand.get("abdeckung_prozent")),
        "fragen": _fragen_zaehlung(stand),
        "anzahl_frameworks": len(je_framework),
        "anzahl_luecken": len(luecken),
        "datum": datetime.date.today().isoformat(),
    }

    return {
        "projekt": projekt,
        "meta": meta,
        "frameworks": je_framework,
        "fragen": fragen,
        "luecken": luecken,
        "bericht": _bericht(load_gutachten_draft(db_path, projekt_name)),
        "wasserstand": _letzter_wasserstand(db_path, projekt_name),
    }
