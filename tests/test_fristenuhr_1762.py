"""Die Fristenuhr für die langen CRA-Fristen (#1762, Punkt 4).

Die Aufbewahrungs- und Update-Verfügbarkeitsfristen wurden gerechnet und
angezeigt, aber nicht überwacht: keine Ampel, kein Vorlauf. Eine 2035 ablaufende
Aufbewahrungsfrist fällt niemandem auf.

Der Kern von ``cra/fristenuhr.py`` ist absichtlich DB-frei — diese Datei braucht
deshalb kein Postgres und läuft überall.

Der wichtigste Test hier ist ``test_vorlauf_ist_absolut_nicht_anteilig``: Er hält
fest, **warum** es eine zweite Uhr neben ``cra/deadlines.py`` gibt. Mit der
Anteils-Ampel von dort stünde eine Zehnjahresfrist fünf Jahre lang auf Gelb.
"""
from __future__ import annotations

from datetime import date, timedelta

from cra import fristenuhr as fu


def _sp(markteintritt: str, jahre: int = 5) -> dict:
    """Zeile wie ``cra_support_period`` sie liefert — ohne DB nachgebaut."""
    mt = date.fromisoformat(markteintritt)
    return {
        "markteintritt_datum": markteintritt,
        "support_jahre": jahre,
        "eol_datum": (mt + timedelta(days=365 * jahre)).isoformat(),
        "update_availability_until": (mt + timedelta(days=365 * max(10, jahre))).isoformat(),
        "doku_retention_until": (mt + timedelta(days=365 * 10)).isoformat(),
        "doc_retention_until": (mt + timedelta(days=365 * 10)).isoformat(),
    }


# ── Ampel ─────────────────────────────────────────────────────────────────────

def test_ampel_stufen():
    assert fu.ampel_tage(2000) == "gruen"
    assert fu.ampel_tage(300) == "gelb"       # unter einem Jahr
    assert fu.ampel_tage(30) == "rot"         # unter 90 Tagen
    assert fu.ampel_tage(-1) == "verstrichen"
    assert fu.ampel_tage(None) == "unbekannt"


def test_vorlauf_ist_absolut_nicht_anteilig():
    """Eine Zehnjahresfrist mit fünf Jahren Restzeit ist **grün**.

    Das ist der Unterschied zu ``cra/deadlines.py``: Dessen Ampel rechnet den
    Anteil der Restzeit am Fenster und stünde hier bei 50 % auf Gelb — fünf
    Jahre lang. Eine Warnung, die fünf Jahre leuchtet, ist keine.
    """
    heute = date(2030, 1, 1)
    f = fu.frist("2035-01-01", heute=heute)
    assert f["ampel"] == "gruen", f


def test_grenzfall_heute_ist_nicht_verstrichen():
    """Am Fälligkeitstag ist die Frist rot, aber nicht verstrichen."""
    heute = date(2026, 10, 22)
    f = fu.frist(heute.isoformat(), heute=heute)
    assert f["tage_verbleibend"] == 0
    assert f["ampel"] == "rot"
    assert f["verstrichen"] is False


def test_unlesbares_datum_ist_unbekannt_nicht_abgelaufen():
    """Datenmüll darf keine Aussage erzeugen.

    „nächste Woche" im Datumsfeld ergibt ``unbekannt`` — nicht ``verstrichen``
    (das wäre eine erfundene Tatsache) und auch nicht ``gruen`` (das wäre eine
    erfundene Entlastung).
    """
    f = fu.frist("nächste Woche")
    assert f["datum"] is None
    assert f["ampel"] == "unbekannt"
    assert f["verstrichen"] is False


def test_behoerdenfrist_hat_kurze_vorlaufzeiten():
    """Eine Behörde setzt Tage, keine Jahre — 10 Tage sind dort schon grün."""
    heute = date(2026, 10, 22)
    assert fu.behoerdenfrist("2026-10-27", heute=heute)["ampel"] == "gelb"
    assert fu.behoerdenfrist("2026-10-24", heute=heute)["ampel"] == "rot"
    assert fu.behoerdenfrist("2026-11-20", heute=heute)["ampel"] == "gruen"


# ── Aufbewahrungsfristen ──────────────────────────────────────────────────────

def test_vier_fristen_werden_ueberwacht():
    u = fu.aufbewahrungsfristen(_sp("2026-01-01"), heute=date(2026, 6, 1))
    keys = [f["key"] for f in u["fristen"]]
    assert keys == ["support_ende", "update_verfuegbarkeit",
                    "doku_aufbewahrung", "doc_aufbewahrung"]
    assert u["berechenbar"] is True
    assert u["unbestimmbar"] == []
    # Nächste offene Frist ist das Support-Ende (5 J. < 10 J.).
    assert u["naechste"]["key"] == "support_ende"


def test_ohne_markteintritt_nicht_berechenbar():
    """Der eigentliche Mangel: Ohne Markteintritt weiß niemand, wie lange die
    Akte zu halten ist. Das muss sichtbar sein und nicht als „alles grün"
    durchgehen."""
    u = fu.aufbewahrungsfristen({}, heute=date(2026, 6, 1))
    assert u["berechenbar"] is False
    assert len(u["unbestimmbar"]) == 4
    assert u["schlechteste_ampel"] == "unbekannt"
    assert u["naechste"] is None


def test_none_wird_wie_leer_behandelt():
    u = fu.aufbewahrungsfristen(None)
    assert u["berechenbar"] is False


def test_laufende_zehnjahresfrist_ist_sichtbar_aber_gruen():
    """Der Fall aus dem Issue: Frist läuft 2035 ab, heute ist 2026.

    Sie ist grün — und sie **steht da**, mit Datum und Restlaufzeit. Genau das
    fehlte: Die Zahl war berechnet, aber nichts machte sie zur laufenden Pflicht.
    """
    u = fu.aufbewahrungsfristen(_sp("2025-06-01"), heute=date(2026, 10, 22))
    doku = next(f for f in u["fristen"] if f["key"] == "doku_aufbewahrung")
    assert doku["datum"].startswith("2035")
    assert doku["ampel"] == "gruen"
    assert doku["tage_verbleibend"] > 3000


def test_verstrichene_frist_wird_benannt():
    u = fu.aufbewahrungsfristen(_sp("2005-01-01"), heute=date(2026, 10, 22))
    assert u["schlechteste_ampel"] == "verstrichen"
    assert set(u["verstrichen"]) == {"support_ende", "update_verfuegbarkeit",
                                     "doku_aufbewahrung", "doc_aufbewahrung"}
    assert u["naechste"] is None   # eine verstrichene Frist ist nicht „nächste"


def test_schlechteste_ampel_nimmt_die_dringendste():
    assert fu.schlechteste_ampel(["gruen", "gelb", "rot"]) == "rot"
    assert fu.schlechteste_ampel(["gruen", "verstrichen"]) == "verstrichen"
    assert fu.schlechteste_ampel([]) == "unbekannt"
    assert fu.schlechteste_ampel(["unbekannt"]) == "unbekannt"
