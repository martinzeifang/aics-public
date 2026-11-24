"""Anhang-V-Angaben der KI-VO aus den Quellen vorschlagen — ohne KI (#1889).

Der Bauplan ist der aus #1884–#1887; die Mechanik liegt seit #1893 in
:mod:`shared.formular_vorschlag`. Hier steht, **welche Quelle welches Feld
speist** — und das ist beim AI Act anders als beim CRA:

* Das KI-System heißt in der Akte ``produkt`` eines Projekts mit
  ``meta.scope='system'`` (#1540); die **Organisation** trägt keine Erklärung.
* Die Risikoeinstufung kommt aus Assistent A1 (``meta.aiact.risk_tier``) — der
  Wert, der in #1858 nie ankam, weil ``_serialize_projekt`` eine Positivliste
  ist und ``meta_json`` nicht herausgab.
* Anbietername und Anschrift kommen vom **Mandanten** (#1892), nicht vom
  Projekt: Ein Anbieter hat mehrere KI-Systeme.
* Verfahren und Kennnummer der notifizierten Stelle stehen in
  ``aiact_conformity``.

**Es gibt keinen Gegenstands-Satz wie im CRA.** Anhang V der KI-VO verlangt
unter Nr. 1 die Bezeichnung und eine eindeutige Kennung, nicht eine
Beschreibung des Artefakts mit Image und Digest. Einen solchen Satz hier zu
bauen hieße, eine Pflicht zu erfinden, die der Rechtstext nicht nennt.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.formular_vorschlag import (KLASSE_AUSWAHL, KLASSE_GERECHNET,
                                       KLASSE_KI, KLASSE_UEBERNOMMEN, Sammler,
                                       filter_ki)

DB_PATH = Path("data/db/ai_act.sqlite")

#: Welche Klasse ein Feld der Erklärung hat (#1887/#1893).
FELD_KLASSE: dict[str, str] = {
    "system_kennung": KLASSE_GERECHNET,
    "nb_verfahren": KLASSE_GERECHNET,
    "datum": KLASSE_GERECHNET,
    "system_name": KLASSE_UEBERNOMMEN,
    "anbieter": KLASSE_UEBERNOMMEN,
    "anbieter_adresse": KLASSE_UEBERNOMMEN,
    "ort": KLASSE_UEBERNOMMEN,
    "unterzeichner_name": KLASSE_UEBERNOMMEN,
    "unterzeichner_funktion": KLASSE_UEBERNOMMEN,
    "unterzeichner_fuer": KLASSE_UEBERNOMMEN,
    "bevollmaechtigter": KLASSE_UEBERNOMMEN,
    "nb_name": KLASSE_UEBERNOMMEN,
    "nb_kennnummer": KLASSE_UEBERNOMMEN,
    "normen": KLASSE_AUSWAHL,
    "weiteres_unionsrecht": KLASSE_AUSWAHL,
    "system_typ": KLASSE_KI,
    "zusatzangaben": KLASSE_KI,
}

#: Felder, die eine KI-Antwort setzen darf — **abschließend**.
#:
#: Dieselbe Grenze wie im CRA (#1887), und aus demselben Grund: Anbieter,
#: Anschrift, Unterzeichner, Datum, Kennnummer und die eindeutige Kennung
#: stammen aus der Akte. Ein Modell, das sie plausibel ausfüllt, erzeugt eine
#: Falschaussage, die wie eine Feststellung aussieht — in einem Dokument, das
#: zehn Jahre bereitzuhalten ist (Art. 47 Abs. 2).
KI_FELDER: frozenset[str] = frozenset({"system_typ", "zusatzangaben"})


def _s(wert: Any) -> str:
    return "" if wert is None else str(wert).strip()


def feld_vorschlaege(*, projekt: dict[str, Any] | None = None,
                     anbieter_stamm: dict[str, Any] | None = None,
                     bevollmaechtigter: str = "",
                     verfahren_label: str = "", nb_name: str = "",
                     nb_kennnummer: str = "", risk_tier: str = "",
                     heute: str = "") -> dict[str, dict[str, Any]]:
    """Was die Anwendung zu jedem Feld aus den Quellen sagen kann.

    Reine Funktion; gelesen wird in :func:`vorschlag`.
    """
    projekt = projekt or {}
    anbieter_stamm = anbieter_stamm or {}
    sammler = Sammler(FELD_KLASSE)
    s = sammler.setze

    name = _s(projekt.get("produkt")) or _s(projekt.get("name"))
    s("system_name", name, "Projekt-Stammdaten")
    # Die eindeutige Kennung (Anhang V Nr. 1) aus Bezeichnung und
    # Risikoeinstufung — mehr weiß die Akte nicht, und Geratenes sieht in
    # einem unterschriebenen Dokument aus wie eine Feststellung.
    if name and _s(risk_tier):
        s("system_kennung", f"{name} ({_s(risk_tier)})",
          "Projekt und Risikoeinstufung aus Assistent A1")
    s("anbieter", _s(projekt.get("organisation")), "Projekt-Stammdaten")
    s("anbieter_adresse", _s(anbieter_stamm.get("anschrift")),
      "Stammdaten des Mandanten")
    s("ort", _s(anbieter_stamm.get("ort")), "Stammdaten des Mandanten")
    s("unterzeichner_name", _s(anbieter_stamm.get("unterzeichner_name")),
      "Stammdaten des Mandanten")
    s("unterzeichner_funktion",
      _s(anbieter_stamm.get("unterzeichner_funktion")),
      "Stammdaten des Mandanten")
    s("unterzeichner_fuer", _s(projekt.get("organisation")),
      "Projekt-Stammdaten")
    s("bevollmaechtigter", _s(bevollmaechtigter), "Stammdaten des Mandanten")
    s("nb_name", _s(nb_name), "Konformitätsbewertung")
    s("nb_kennnummer", _s(nb_kennnummer), "Konformitätsbewertung")
    s("nb_verfahren", _s(verfahren_label), "Gewähltes Verfahren (Art. 43)")
    s("datum", _s(heute), "Heutiges Datum")
    return sammler.ergebnis()


def uebernahme_filter(felder: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Was eine KI-Antwort setzen darf — serverseitig (#1887/#1893)."""
    return filter_ki(felder, KI_FELDER)


def vorschlag(db_path: Path | str = DB_PATH,
              projekt_name: str = "") -> dict[str, Any]:
    """Vorschläge, Kataloge und der Stand des Mandanten — rein lesend."""
    from datetime import date as _date

    from ai_act import conformity as conf
    from ai_act.db import load_projekt
    from cra import normen_katalog as nk

    db_path = Path(db_path)

    def _sicher(fn, standard):
        """Eine ausgefallene Teilquelle darf den Vorschlag nicht verhindern.

        ``ImportError`` und ``AttributeError`` bleiben **ungefangen**: Sie sind
        Programmierfehler. Die erste Fassung im CRA fing sie mit und
        verschluckte einen falschen Importnamen — der Mandant wurde nie
        aufgelöst, und nichts schlug fehl (#1892).
        """
        try:
            return fn()
        except (ImportError, AttributeError):
            raise
        except Exception:  # noqa: BLE001
            return standard

    proj = _sicher(lambda: load_projekt(db_path, projekt_name) or {}, {})
    rec = _sicher(lambda: conf.get_or_empty(db_path, projekt_name) or {}, {})
    meta = proj.get("meta") if isinstance(proj.get("meta"), dict) else {}
    aiact_meta = meta.get("aiact") if isinstance(meta.get("aiact"), dict) else {}

    firma = _sicher(lambda: _firma_des_projekts(db_path, projekt_name), {})
    stamm = _sicher(lambda: _anbieter_stammdaten(firma), {})

    verfahren = _s(rec.get("verfahren"))
    felder = feld_vorschlaege(
        projekt=proj, anbieter_stamm=stamm,
        verfahren_label=_s(conf.VERFAHREN.get(verfahren, verfahren)),
        nb_name=_s(rec.get("notified_body_name")),
        nb_kennnummer=_s(rec.get("notified_body_kennnummer")),
        risk_tier=_s(aiact_meta.get("risk_tier")),
        heute=_date.today().isoformat())

    return {
        "felder": felder,
        "klassen": dict(FELD_KLASSE),
        "ki_felder": sorted(KI_FELDER),
        # Der Normen-Katalog ist derselbe wie im CRA — die Spezifikationen
        # sind dieselben, und zwei Kataloge wären zwei Stände. **Die Gruppe
        # „harmonisiert" ist auch hier leer**: Zur KI-VO ist nach unserem
        # Stand keine Fundstelle im Amtsblatt veröffentlicht.
        "katalog": nk.katalog(),
        "unionsrecht": nk.unionsrecht_katalog(),
        "anbieter_stamm": stamm,
        "firma": _s((firma or {}).get("name")),
        "scope": _s(meta.get("scope")),
        "risk_tier": _s(aiact_meta.get("risk_tier")),
    }


def _firma_des_projekts(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """Den Mandanten zum AI-Act-Projekt auflösen.

    ``projekt_firmen_id`` nimmt den **DB-Pfad**, nicht den Modulnamen —
    ``MODULE_PROJECT_TABLES`` ist nach Dateinamen geschlüsselt. Mit dem
    Modulnamen käme immer ``None`` zurück, und weil der Aufrufer fail-open
    ist, bliebe es stumm (der Fehler aus #1892).
    """
    from firmen.db import DEFAULT_DB_PATH as FIRMEN_DB, load_firma
    from shared.firmen_link import firmen_name_to_id, projekt_firmen_id

    fid = projekt_firmen_id(db_path, projekt_name)
    if not fid:
        return {}
    for name, kennung in (firmen_name_to_id(FIRMEN_DB) or {}).items():
        if int(kennung) == int(fid):
            return load_firma(FIRMEN_DB, str(name)) or {}
    return {}


def _anbieter_stammdaten(firma: dict[str, Any] | None) -> dict[str, Any]:
    """Anschrift und Unterzeichner des Anbieters (#1892).

    Dieselbe Quelle wie beim CRA — die Spalten des Mandanten. Eine eigene
    Ablage für den AI Act wäre die Doppelpflege, die #1892 beendet hat: Ein
    Anbieter, der ein Produkt und ein KI-System führt, hätte zwei Anschriften.
    """
    from cra.doc_vorschlag import hersteller_stammdaten

    return hersteller_stammdaten(firma)


__all__ = ["FELD_KLASSE", "KI_FELDER", "feld_vorschlaege",
           "uebernahme_filter", "vorschlag"]
