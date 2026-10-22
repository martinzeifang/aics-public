"""Ampel für eine Änderung am KI-System (#1756) — die gerechneten Prüfpunkte.

Was aus den vorhandenen Registern ableitbar ist, wird gerechnet; alles andere ist
eine ausdrückliche Entscheidung mit Begründung (``aenderung_checkliste``). Eine
Checkliste, die sich selbst abhakt, ist als Nachweis wertlos — und ein Rechenweg,
den ein Mensch überstimmen kann, ebenfalls.

Gelesen, nie geschrieben, werden:

* ``aiact_incidents`` (Art. 73) — offene und überfällige Meldefristen, über die
  kanonische Fristenuhr aus :mod:`ai_act.incidents`;
* ``aiact_post_market_monitoring`` (Art. 72) — Beobachtungsplan;
* ``aiact_conformity`` (Art. 43/47/48) — Bewertungsergebnis, DoC-Gate, CE;
* ``aiact_system_doku`` (Art. 11/Anhang IV) und die verwalteten Dokumente aus
  :mod:`shared.documents` — technische Dokumentation und
  EU-Datenbank-Registrierung.

**Ampel-Zuordnung — bewusst so und nicht anders**

``rot``
    Überfällige Vorfallmeldung (Art. 73) und, bei einer **wesentlichen**
    Änderung, eine fehlende erneute Konformitätsbewertung bzw.
    Konformitätserklärung (Art. 43 Abs. 4 i.V.m. Art. 47). Beides ist eine
    Pflichtverletzung gegenüber Behörde bzw. Markt, kein Nachweismangel: Das
    System darf in diesem Stand nicht weiter angeboten werden. Ebenfalls rot:
    gar keine technische Dokumentation (Art. 11) — ohne sie gibt es nichts
    nachzuziehen und das System ist von Anfang an nicht konform.

``bedingt``
    Technische Dokumentation vorhanden, aber nach der Änderung nicht
    fortgeschrieben; EU-Datenbank-Registrierung nicht nachgetragen (Art. 49/71);
    kein Beobachtungsplan (Art. 72); laufende Meldefristen; CE-Kennzeichnung ohne
    Datum. Begründung: Die Akte ist unvollständig, der Inhalt kann stimmen — das
    ist ein Nachweismangel und keine Rechtsverletzung.

``gruen``
    Kein offener Punkt, **und** keine Prüfung musste ausfallen.

**Ungeprüft ist nicht erfüllt.** Fällt eine Quelle aus, entsteht ein sichtbarer
Punkt mit ``ungeprueft: True``, und „grün" ist ausgeschlossen. Ein stilles
``except: pass`` ließe den Punkt verschwinden, die Ampel würde grün — und der
Anwender hielte für geprüft, was niemand geprüft hat. In einem Konformitäts-Gate
ist das der gefährlichste Fehler, weil er wie ein gutes Ergebnis aussieht (die
Lehre aus #1751).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path("data/db/ai_act.sqlite")

_WIRKUNG_ROT = "rot"
_WIRKUNG_BEDINGT = "bedingt"


def _punkt(typ: str, titel: str, hinweis: str, link: str,
           *, wirkung: str = _WIRKUNG_BEDINGT, **extra: Any) -> dict[str, Any]:
    p: dict[str, Any] = {"typ": typ, "titel": titel, "hinweis": hinweis,
                         "link": link, "ampel_wirkung": wirkung}
    p.update(extra)
    return p


def _ungeprueft(typ: str, titel: str, link: str, exc: BaseException) -> dict[str, Any]:
    """Punkt für eine Prüfung, die nicht laufen konnte — sichtbar, nicht verschluckt."""
    return _punkt(typ, titel,
                  f"konnte nicht geprüft werden ({type(exc).__name__}: {exc}) — "
                  "Datenquelle prüfen und erneut bewerten",
                  link, ungeprueft=True)


def _iso(value: Any) -> datetime | None:
    """Zeitstempel aus der Datenbank lesbar machen (Postgres liefert datetime,
    SQLite einen String). ``None`` bei allem, was nicht lesbar ist — daraus wird
    nie eine Aussage abgeleitet."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).strip().replace(" ", "T")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ── Art. 11 / Anhang IV: technische Dokumentation ───────────────────────────

def _check_annex_iv(ctx: dict[str, Any], befunde: dict[str, Any],
                    punkte: list[dict[str, Any]]) -> None:
    """Ist die technische Dokumentation nach dieser Änderung fortgeschrieben?

    Zwei Quellen zählen, weil das Modul zwei Wege kennt: die strukturierte
    A1-Tabelle ``aiact_system_doku`` und ein freigegebenes Dokument
    ``technische_doku_annex_iv`` aus dem Dokumente-Register. Eine davon genügt —
    verlangt ist die aktuelle Dokumentation, nicht ein bestimmtes Werkzeug.

    Maßstab für „fortgeschrieben" ist der Zeitpunkt, zu dem der Änderungsvorgang
    angelegt wurde (``seit``). Fehlt er, wird nur auf Vorhandensein geprüft:
    Ein erfundener Maßstab wäre schlechter als keiner.
    """
    db_path, projekt, seit = ctx["db_path"], ctx["projekt"], ctx["seit"]
    try:
        from ai_act.db import load_system_doku
        doku = load_system_doku(db_path, projekt) or {}
        doku_stand = _iso(doku.get("updated_at")) if doku else None
        dokumente: list[dict[str, Any]] = []
        try:
            from shared.documents.db import list_documents
            dokumente = [d for d in list_documents(db_path, "ai_act", projekt)
                         if str(d.get("doc_type")) == "technische_doku_annex_iv"]
        except Exception:  # noqa: BLE001 — Nebenquelle; die Hauptquelle trägt
            dokumente = []
        doc_stand = max((_iso(d.get("updated_at")) for d in dokumente
                         if _iso(d.get("updated_at"))), default=None)
        neuester = max([s for s in (doku_stand, doc_stand) if s], default=None)
        befunde["annex_iv"] = {
            "system_doku": bool(doku),
            "dokumente": len(dokumente),
            "zuletzt_geaendert": neuester.isoformat() if neuester else None,
        }
        if not doku and not dokumente:
            befunde["annex_iv_aktuell"] = False
            punkte.append(_punkt(
                "annex_iv", "Keine technische Dokumentation nach Anhang IV vorhanden",
                "Technische Dokumentation anlegen (A1-Systemdokumentation oder "
                "Dokument „Technische Dokumentation (Annex IV)“) — ohne sie gibt "
                "es nach einer Änderung nichts nachzuziehen",
                "pflichtdoku", wirkung=_WIRKUNG_ROT, ref="Art. 11, Anhang IV"))
            return
        grenze = _iso(seit)
        if grenze is None or neuester is None:
            # Nicht entscheidbar: vorhanden ja, aktuell unbekannt. ``None`` statt
            # ``True`` — ein ``True`` wäre die Aussage „nachgezogen".
            befunde["annex_iv_aktuell"] = None
            if neuester is None:
                punkte.append(_punkt(
                    "annex_iv", "Stand der technischen Dokumentation nicht lesbar",
                    "Änderungszeitpunkt der Dokumentation fehlt — Fortschreibung "
                    "nicht nachweisbar",
                    "pflichtdoku", ungeprueft=True, ref="Art. 11"))
            return
        befunde["annex_iv_aktuell"] = neuester >= grenze
        if neuester < grenze:
            punkte.append(_punkt(
                "annex_iv", "Technische Dokumentation seit dieser Änderung nicht fortgeschrieben",
                f"letzte Änderung der Dokumentation: {neuester.date().isoformat()} — "
                "Anhang-IV-Angaben (Architektur, Training, Leistung) nachziehen",
                "pflichtdoku", ref="Art. 11, Anhang IV"))
    except Exception as exc:  # noqa: BLE001
        befunde["annex_iv_aktuell"] = None
        punkte.append(_ungeprueft("annex_iv",
                                  "Technische Dokumentation (Anhang IV) ungeprüft",
                                  "pflichtdoku", exc))


# ── Art. 43 Abs. 4 / 47 / 48: Konformitätsbewertung, DoC, CE ────────────────

def _check_doc_ce(ctx: dict[str, Any], befunde: dict[str, Any],
                  punkte: list[dict[str, Any]]) -> None:
    """Erneute Konformitätsbewertung samt Erklärung und CE — nur bei ``wesentlich='ja'``.

    Das ist die Stelle, an der sich der AI Act vom CRA unterscheidet: Für
    ``vorab_bewertet`` greift die Ausnahme des Art. 43 Abs. 4, und es darf kein
    Punkt entstehen. Täte er es doch, meldete die Anwendung bei jedem
    fortlernenden System Alarm für etwas, das die Verordnung ausdrücklich
    erlaubt.
    """
    db_path, projekt, seit = ctx["db_path"], ctx["projekt"], ctx["seit"]
    try:
        from ai_act import conformity as conf
        rec = conf.get_or_empty(db_path, projekt) or {}
        bewertungsdatum = str(rec.get("bewertungsdatum") or "").strip()
        befunde["doc_ce"] = {
            "ergebnis": rec.get("ergebnis") or "offen",
            "bewertungsdatum": bewertungsdatum or None,
            "ce_angebracht_am": str(rec.get("ce_angebracht_am") or "") or None,
            # ``assessment_complete`` ist das abgeleitete Feld des Registers
            # (Ergebnis „konform" **plus** die Verfahrensvoraussetzungen: QMS
            # und TechDoc geprüft, bei Anhang VII Kennnummer und Zertifikat).
            # Nur das Ergebnis zu lesen wäre zu wenig.
            "bewertung_abgeschlossen": bool(rec.get("assessment_complete")),
            "neubewertung_offen": bool(rec.get("reassessment_required")),
            "doc_erlaubt": bool(rec.get("doc_allowed")),
            "verfahren": rec.get("verfahren") or "",
        }
        if ctx["wesentlich"] != "ja":
            # Kein Punkt, aber nachvollziehbar festhalten, warum nicht geprüft
            # wurde — das ist die Antwort auf die erste Audit-Frage.
            befunde["doc_ce_geprueft"] = False
            befunde["doc_ce_grund"] = (
                "Art. 43 Abs. 4 verlangt die erneute Bewertung nur bei einer "
                "wesentlichen Änderung" if ctx["wesentlich"] == "nein" else
                "vorab festgelegte und mitbewertete Änderung — Ausnahme des "
                "Art. 43 Abs. 4" if ctx["wesentlich"] == "vorab_bewertet" else
                "Kernfrage noch nicht beantwortet")
            return
        befunde["doc_ce_geprueft"] = True
        if not rec.get("assessment_complete"):
            punkte.append(_punkt(
                "konformitaet",
                "Erneute Konformitätsbewertung nicht abgeschlossen",
                "Die Änderung ist als wesentlich eingeordnet — das "
                "Konformitätsbewertungsverfahren ist erneut zu durchlaufen und "
                "mit Ergebnis „konform“ abzuschließen",
                "conformity", wirkung=_WIRKUNG_ROT, ref="Art. 43 Abs. 4, Art. 47"))
        else:
            # Abgeschlossen ja — aber **wann**? Eine Bewertung, die älter ist als
            # die Änderung, hat diese Änderung nicht gesehen. Genau das ist der
            # Fall, den Art. 43 Abs. 4 verbietet, und ohne diesen Vergleich
            # würde eine alte Bewertung den Punkt still abdecken.
            grenze, bewertet = _iso(seit), _iso(bewertungsdatum)
            if grenze is not None and bewertet is not None and bewertet < grenze:
                punkte.append(_punkt(
                    "konformitaet",
                    "Konformitätsbewertung stammt von vor dieser Änderung",
                    f"bewertet am {bewertet.date().isoformat()} — die wesentliche "
                    "Änderung ist danach eingetreten und noch nicht bewertet",
                    "conformity", wirkung=_WIRKUNG_ROT, ref="Art. 43 Abs. 4"))
            elif grenze is not None and bewertet is None:
                punkte.append(_punkt(
                    "konformitaet", "Bewertungsdatum der Konformitätsbewertung fehlt",
                    "ohne Datum ist nicht nachweisbar, ob die Bewertung diese "
                    "Änderung umfasst",
                    "conformity", ungeprueft=True, ref="Art. 43 Abs. 4"))
            elif not str(rec.get("ce_angebracht_am") or "").strip():
                punkte.append(_punkt(
                    "konformitaet", "CE-Kennzeichnung für den neuen Stand nicht erfasst",
                    "Datum der CE-Kennzeichnung nachtragen",
                    "conformity", ref="Art. 48"))
    except Exception as exc:  # noqa: BLE001
        befunde["doc_ce"] = None
        punkte.append(_ungeprueft("konformitaet",
                                  "Konformitätsbewertung und CE ungeprüft",
                                  "conformity", exc))


# ── Art. 49 / 71: EU-Datenbank-Registrierung ────────────────────────────────

def _check_eu_registrierung(ctx: dict[str, Any], befunde: dict[str, Any],
                            punkte: list[dict[str, Any]]) -> None:
    """Ist die Registrierung in der EU-Datenbank nachgetragen?

    Quelle ist das verwaltete Dokument ``eu_db_registrierung`` — das Modul führt
    die Registrierung dort und nicht in einer eigenen Tabelle.
    """
    db_path, projekt, seit = ctx["db_path"], ctx["projekt"], ctx["seit"]
    try:
        from shared.documents.db import list_documents
        eintraege = [d for d in list_documents(db_path, "ai_act", projekt)
                     if str(d.get("doc_type")) == "eu_db_registrierung"]
        neuester = max((_iso(d.get("updated_at")) for d in eintraege
                        if _iso(d.get("updated_at"))), default=None)
        befunde["eu_registrierung"] = {
            "eintraege": len(eintraege),
            "zuletzt_geaendert": neuester.isoformat() if neuester else None,
        }
        if not eintraege:
            befunde["eu_registrierung_aktuell"] = False
            punkte.append(_punkt(
                "registrierung", "EU-Datenbank-Registrierung nicht dokumentiert",
                "Registrierung nach Art. 49 im Dokumente-Register erfassen und "
                "nach dieser Änderung aktualisieren",
                "dokumente", ref="Art. 49, Art. 71"))
            return
        grenze = _iso(seit)
        if grenze is None or neuester is None:
            befunde["eu_registrierung_aktuell"] = None
            return
        befunde["eu_registrierung_aktuell"] = neuester >= grenze
        if neuester < grenze:
            punkte.append(_punkt(
                "registrierung", "EU-Datenbank-Registrierung seit dieser Änderung nicht aktualisiert",
                f"letzte Änderung: {neuester.date().isoformat()} — Angaben in der "
                "EU-Datenbank nachtragen",
                "dokumente", ref="Art. 49, Art. 71"))
    except Exception as exc:  # noqa: BLE001
        befunde["eu_registrierung_aktuell"] = None
        punkte.append(_ungeprueft("registrierung",
                                  "EU-Datenbank-Registrierung ungeprüft",
                                  "dokumente", exc))


# ── Art. 72: Beobachtungsplan ───────────────────────────────────────────────

def _check_pmm(ctx: dict[str, Any], befunde: dict[str, Any],
               punkte: list[dict[str, Any]]) -> None:
    """Gibt es einen Beobachtungsplan, und passt er noch zum System?"""
    db_path, projekt, seit = ctx["db_path"], ctx["projekt"], ctx["seit"]
    try:
        from ai_act.db import load_pmm
        pmm = load_pmm(db_path, projekt) or {}
        plan = str(pmm.get("monitoring_plan") or "").strip()
        stand = _iso(pmm.get("updated_at")) if pmm else None
        befunde["pmm"] = {
            "plan_vorhanden": bool(plan),
            "drift_detection": bool(str(pmm.get("drift_detection") or "").strip()),
            "zuletzt_geaendert": stand.isoformat() if stand else None,
        }
        if not plan:
            befunde["pmm_aktuell"] = False
            punkte.append(_punkt(
                "pmm", "Kein Beobachtungsplan nach dem Inverkehrbringen",
                "Plan nach Art. 72 erfassen — er ist auch die Grundlage dafür, "
                "abweichende Leistung überhaupt zu erkennen",
                "pflichtdoku", ref="Art. 72"))
            return
        grenze = _iso(seit)
        if grenze is None or stand is None:
            befunde["pmm_aktuell"] = None
            return
        befunde["pmm_aktuell"] = stand >= grenze
        if stand < grenze:
            punkte.append(_punkt(
                "pmm", "Beobachtungsplan seit dieser Änderung nicht angepasst",
                f"letzte Änderung: {stand.date().isoformat()} — Kennzahlen und "
                "Drift-Erkennung auf den neuen Stand beziehen",
                "pflichtdoku", ref="Art. 72"))
    except Exception as exc:  # noqa: BLE001
        befunde["pmm_aktuell"] = None
        punkte.append(_ungeprueft("pmm", "Beobachtungsplan (Art. 72) ungeprüft",
                                  "pflichtdoku", exc))


# ── Art. 73: Vorfallmeldungen ───────────────────────────────────────────────

def _check_vorfaelle(ctx: dict[str, Any], befunde: dict[str, Any],
                     punkte: list[dict[str, Any]]) -> None:
    """Offene und überfällige Meldefristen — über die Fristenuhr des Registers.

    Die Fristenuhr wird nicht nachgebaut: ``ai_act.incidents.list_incidents``
    reichert jeden Vorfall mit ``deadlines`` aus :mod:`shared.deadlines` an. Ein
    zweiter Rechenweg wäre eine zweite Wahrheit.
    """
    db_path, projekt = ctx["db_path"], ctx["projekt"]
    try:
        from ai_act import incidents as inc
        ueberfaellig: list[dict[str, Any]] = []
        laufend: list[dict[str, Any]] = []
        for v in inc.list_incidents(db_path, projekt):
            dl = v.get("deadlines") or {}
            for st in dl.get("stages", []):
                if st.get("fulfilled") or st.get("status") == "no_base":
                    continue
                eintrag = {"incident_id": v.get("id"), "titel": v.get("titel"),
                           "stufe": st.get("label"), "due_at": st.get("due_at")}
                if st.get("status") == "overdue" or st.get("overdue"):
                    ueberfaellig.append(eintrag)
                else:
                    laufend.append(eintrag)
        befunde["vorfaelle"] = {"ueberfaellig": ueberfaellig, "laufend": laufend}
        befunde["ueberfaellige_meldungen"] = ueberfaellig
        if ueberfaellig:
            liste = "; ".join(f"{e['titel'] or 'Vorfall'} — {e['stufe']}"
                              for e in ueberfaellig[:5])
            punkte.append(_punkt(
                "vorfall", f"{len(ueberfaellig)} überfällige Meldefrist(en) nach Art. 73",
                f"Meldung an die Marktaufsichtsbehörde nachholen und "
                f"dokumentieren ({liste})",
                "incidents", wirkung=_WIRKUNG_ROT, ref="Art. 73"))
        if laufend:
            liste = "; ".join(f"{e['titel'] or 'Vorfall'} — {e['stufe']} bis {e['due_at']}"
                              for e in laufend[:5])
            punkte.append(_punkt(
                "vorfall", f"{len(laufend)} laufende Meldefrist(en) zum Änderungszeitpunkt",
                f"Frist vor dem Ausrollen der Änderung bedienen ({liste})",
                "incidents", ref="Art. 73"))
    except Exception as exc:  # noqa: BLE001
        befunde["vorfaelle"] = None
        befunde["ueberfaellige_meldungen"] = None
        punkte.append(_ungeprueft("vorfall", "Vorfallmeldungen (Art. 73) ungeprüft",
                                  "incidents", exc))


# Reihenfolge = Reihenfolge in der Oberfläche. Jede Prüfung kapselt ihre Fehler
# selbst, damit ein Ausfall die folgenden nicht mitnimmt.
_CHECKS = (_check_annex_iv, _check_doc_ce, _check_eu_registrierung, _check_pmm,
           _check_vorfaelle)


def evaluate(projekt_name: str, *, wesentlich: str = "", grund_art: str = "",
             seit: str = "", db_path: Path | None = None) -> dict[str, Any]:
    """Bewertet eine Änderung am KI-System. Best effort, nie Exception nach außen.

    ``wesentlich`` steuert, ob die Art.-43-Abs.-4-Prüfung greift (nur ``ja``),
    ``seit`` ist der Zeitpunkt, ab dem eine Fortschreibung als „nachgezogen"
    zählt (in der Regel die Anlage des Vorgangs).
    """
    ctx = {"db_path": Path(db_path or DB_PATH), "projekt": projekt_name,
           "wesentlich": (wesentlich or "").strip(),
           "grund_art": (grund_art or "").strip(),
           "seit": seit or ""}
    punkte: list[dict[str, Any]] = []
    befunde: dict[str, Any] = {}
    for check in _CHECKS:
        try:
            check(ctx, befunde, punkte)
        except Exception as exc:  # noqa: BLE001 — Netz unter dem Netz
            punkte.append(_ungeprueft(
                getattr(check, "__name__", "aenderung"),
                f"Prüfung {getattr(check, '__name__', '?')} ungeprüft",
                "pflichtdoku", exc))

    ungeprueft = [p for p in punkte if p.get("ungeprueft")]
    if any(p.get("ampel_wirkung") == _WIRKUNG_ROT for p in punkte):
        ampel = "rot"
    elif punkte:
        # Jeder offene Punkt — auch ein ungeprüfter — schließt „grün" aus.
        ampel = "bedingt"
    else:
        ampel = "gruen"

    return {
        "projekt": projekt_name,
        "stand_wesentlich": ctx["wesentlich"],
        "grund_art": ctx["grund_art"],
        "ampel": ampel,
        "offene_punkte": punkte,
        "ungeprueft": [p["titel"] for p in ungeprueft],
        "befunde": befunde,
        # Die eine Aussage, auf die der Vorgang hinausläuft. ``vorab_bewertet``
        # steht hier bewusst wie ``nein``: Die Ausnahme des Art. 43 Abs. 4 ist
        # kein Sonderfall mit halber Wirkung, sie verneint die wesentliche
        # Änderung.
        "neubewertung_erforderlich": ctx["wesentlich"] == "ja",
        "bewertet_am": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
