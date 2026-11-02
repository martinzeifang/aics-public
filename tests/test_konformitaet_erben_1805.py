"""Die Konformitätsbewertung gehört dem Produkt, das Release erbt sie (#1805).

**Der Befund aus dem Betrieb**, Wort für Wort: „Der Bewertungsweg ist nicht als
abgeschlossen vermerkt — Haken ‚Bewertung abgeschlossen‘ im Tab ✅ Konformität
→ dort pflegen was fehlt hier. ich finde es nicht."

Er konnte es nicht finden, weil es die Stelle nicht gab. ``cra_konformitaet``
führt je ``(projekt, release_version)`` eine eigene Zeile. Der Konformitäts-Tab
pflegt **nur** die Zeile mit ``release_version=''`` — den Produkt-Datensatz.
``POST /releases/<version>`` legt eine zweite Zeile mit
``bewertung_abgeschlossen = 0`` an, und für die gab es keine Eingabestelle.

Das macht diesen Fall schlimmer als #1796 (dort fehlte ein Feld schlicht): Hier
*gab* es einen Haken, das Speichern meldete Erfolg, und das Release blieb
gesperrt. Eine Oberfläche, die „gespeichert" sagt und nichts bewirkt, schickt
den Anwender auf die Suche nach einem Fehler bei sich selbst.

Die Tests halten beide Richtungen fest: dass geerbt wird **und** dass ein
eigener Vermerk am Release gilt.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from cra import db as cdb
from cra import konformitaet_db as kdb

CRA_DB = Path("data/db/cra.sqlite")
PROJ = "pytest-erben-1805"
VER = "8.0.1"
ENTWICKLER = "aaaaaaaa-0000-0000-0000-000000000001"
PRUEFER = "bbbbbbbb-0000-0000-0000-000000000002"


@pytest.fixture
def projekt():
    cdb.ensure_db(CRA_DB)
    cdb.delete_projekt(CRA_DB, PROJ)
    cdb.save_projekt(CRA_DB, PROJ, unternehmen="pytest-firma-1805", produkt="Testprodukt")
    yield PROJ
    cdb.delete_projekt(CRA_DB, PROJ)


def _produkt_abgeschlossen(projekt: str) -> None:
    """Was der Anwender im Tab „✅ Konformität" tut: Haken setzen, speichern.

    Genau so schickt es ``KonformitaetPanel`` — **ohne** ``release_version``,
    also auf den Produkt-Datensatz.
    """
    kdb.save_konformitaet(CRA_DB, projekt, {"bewertungsweg": "A",
                                            "bewertung_abgeschlossen": True})


# ── Der Befund selbst ────────────────────────────────────────────────────────

def test_der_haken_am_produkt_macht_das_release_einreichbar(projekt):
    """Die Strecke, die vorher in einer Sackgasse endete."""
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER})   # wie POST /releases
    _produkt_abgeschlossen(projekt)

    rec = kdb.get_konformitaet(CRA_DB, projekt, VER)
    assert rec["bewertung_abgeschlossen"] is True, \
        "Das Release erbt den Abschluss nicht — der Haken bliebe ohne Wirkung"
    assert "bewertung_abgeschlossen" in rec["geerbt_vom_produkt"], \
        "Die Oberfläche muss sagen können, dass der Stand vom Produkt kommt"

    eingereicht = kdb.einreichen(CRA_DB, projekt, VER, von=ENTWICKLER)
    assert eingereicht["freigabe_status"] == "in_pruefung"
    frei = kdb.freigeben(CRA_DB, projekt, VER, von=PRUEFER)
    assert frei["freigabe_status"] == "freigegeben"


def test_reihenfolge_ist_gleichgueltig(projekt):
    """Erst Haken, dann Release anlegen — der häufigere Weg.

    Geerbt wird beim **Lesen**, nicht beim Anlegen kopiert. Sonst käme es auf
    die Reihenfolge an, und wer das Release zuerst anlegt (der Normalfall),
    stünde wieder vor der gesperrten Freigabe.
    """
    _produkt_abgeschlossen(projekt)
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER})
    assert kdb.get_konformitaet(CRA_DB, projekt, VER)["bewertung_abgeschlossen"] is True


def test_ohne_haken_am_produkt_bleibt_es_gesperrt(projekt):
    """Das Erben ist keine Aufweichung: Ohne Abschluss bleibt gesperrt."""
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER})
    with pytest.raises(ValueError) as e:
        kdb.einreichen(CRA_DB, projekt, VER, von=ENTWICKLER)
    text = str(e.value)
    assert "Bewertungsweg abgeschlossen" in text, \
        "Die Meldung muss die Beschriftung nennen, die im Formular steht"
    assert "Konformität" in text and "Produkt" in text


def test_die_meldung_nennt_die_beschriftung_aus_dem_formular():
    """Der zweite Teil des Befundes: Er hat den Text gesucht und nicht gefunden.

    Die Meldung zitierte „Bewertung abgeschlossen", das Formular ist mit
    „Bewertungsweg abgeschlossen" beschriftet. Eine Wegbeschreibung, die auf
    ein Wort verweist, das es nicht gibt, ist schlechter als keine.
    """
    panel = Path("frontend/src/views/cra/KonformitaetPanel.vue").read_text(encoding="utf-8")
    import re
    treffer = re.search(r"(Bewertungsweg abgeschlossen|Bewertung abgeschlossen)\s*\n?\s*</label>",
                        panel)
    assert treffer, "Der Haken ist nicht mehr zu finden — Beschriftung geändert?"
    beschriftung = treffer.group(1)

    quellen = [Path("cra/konformitaet_db.py").read_text(encoding="utf-8"),
               Path("frontend/src/views/cra/ReleasesPanel.vue").read_text(encoding="utf-8")]
    for quelle in quellen:
        for zitat in re.findall(r"Haken \S?(Bewertung[a-zäöüß]* abgeschlossen)", quelle):
            assert zitat == beschriftung, \
                (f"Verwiesen wird auf '{zitat}', im Formular steht aber "
                 f"'{beschriftung}' — genau die Suche, die ins Leere lief")


# ── Ein eigener Vermerk am Release gilt ──────────────────────────────────────

def test_release_darf_abweichen(projekt):
    """Nach einer wesentlichen Änderung ist die Bewertung eigens zu wiederholen.

    Das Erben darf diese Möglichkeit nicht nehmen: Ein am Release gesetzter Wert
    übersteuert den des Produkts.
    """
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER,
                                            "bewertungsweg": "H",
                                            "nb_kennnummer": "0999",
                                            "bewertung_abgeschlossen": True})
    rec = kdb.get_konformitaet(CRA_DB, projekt, VER)
    assert rec["bewertungsweg"] == "H"
    assert rec["nb_kennnummer"] == "0999"
    assert rec["geerbt_vom_produkt"] == [], "Eigene Angaben werden nicht als geerbt gemeldet"


def test_der_produkt_datensatz_erbt_von_niemandem(projekt):
    _produkt_abgeschlossen(projekt)
    rec = kdb.get_konformitaet(CRA_DB, projekt, "")
    assert rec["geerbt_vom_produkt"] == []


def test_roh_lesen_zeigt_den_ungeerbten_stand(projekt):
    """``erben=False`` braucht ``save_konformitaet``: Würde es den geerbten Wert
    zurückschreiben, wäre das Erben nach dem ersten Speichern eine Kopie."""
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER})
    _produkt_abgeschlossen(projekt)
    assert kdb.get_konformitaet(CRA_DB, projekt, VER)["bewertung_abgeschlossen"] is True
    roh = kdb.get_konformitaet(CRA_DB, projekt, VER, erben=False)
    assert roh["bewertung_abgeschlossen"] is False


def test_speichern_am_release_verfestigt_das_erben_nicht(projekt):
    """Nach einem Speichern am Release muss eine Änderung am Produkt weiter wirken."""
    _produkt_abgeschlossen(projekt)
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER,
                                            "notizen": "Zwischenstand"})
    # Haken am Produkt zurücknehmen → das Release folgt.
    kdb.save_konformitaet(CRA_DB, projekt, {"bewertungsweg": "A",
                                            "bewertung_abgeschlossen": False})
    assert kdb.get_konformitaet(CRA_DB, projekt, VER)["bewertung_abgeschlossen"] is False, \
        "Das Erben ist zur Kopie geworden — eine Rücknahme am Produkt wirkt nicht mehr"


# ── Der Bewertungsweg des Produkts gilt auch im Vorgang ──────────────────────

def test_release_uebernimmt_den_weg_des_produkts(projekt):
    """Vorher stand im Vorgang der **erste zulässige** Weg der Klasse.

    Bei einem Produkt mit Modul H trug der Release-Vorgang „B+C" — eine
    Abweichung, die niemand eingegeben hat und die im Nachweis wie eine
    Entscheidung aussieht.
    """
    kdb.save_konformitaet(CRA_DB, projekt, {"bewertungsweg": "H", "nb_kennnummer": "0123"})
    rec = kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER})
    assert rec["bewertungsweg"] == "H"
    assert rec["nb_kennnummer"] == "0123", "Die Angabe zur Stelle gehört dazu"


def test_unzulaessiger_weg_am_produkt_blockiert_das_anlegen_nicht(projekt):
    """Die Falle aus #1759: Ein Altbestand mit unzulässigem Weg darf nicht dazu
    führen, dass sich für dieses Produkt kein Release mehr anlegen lässt."""
    cdb.save_projekt(CRA_DB, PROJ, unternehmen="pytest-firma-1805",
                     produkt="Testprodukt", produktklasse="critical")
    # Modul A an einem Anhang-IV-Produkt — nur direkt in die Tabelle zu bekommen.
    con = cdb._connect(CRA_DB)
    try:
        con.execute("UPDATE cra_konformitaet SET bewertungsweg='A' "
                    "WHERE projekt_name=? AND release_version=''", (PROJ,))
        con.execute("INSERT INTO cra_konformitaet (projekt_name, release_version, "
                    "bewertungsweg, ce_status) VALUES (?,'','A','offen') "
                    "ON CONFLICT DO NOTHING", (PROJ,))
        con.commit()
    finally:
        con.close()
    rec = kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER})
    assert rec["bewertungsweg"] != "A", "Ein unzulässiger Weg darf nicht geerbt werden"


# ── Teil-Update: Speichern verliert nichts ───────────────────────────────────

def test_speichern_leert_keine_ungenannten_felder(projekt):
    """Jedes Speichern im Konformitäts-Tab leerte die ``notizen``.

    Das Formular nennt das Feld nicht, und ``save_konformitaet`` schrieb
    ``data.get("notizen", "")`` — dieselbe Klasse wie der ``artefakt``-Verlust
    in #1771 und der ``meta_json``-Verlust in #1540. Niemand merkt es, weil
    nichts fehlschlägt: Es steht nur plötzlich nichts mehr da.
    """
    kdb.save_konformitaet(CRA_DB, projekt, {
        "bewertungsweg": "H", "nb_kennnummer": "0123", "eucc_level": "",
        "notizen": "Prüfbericht TÜV vom 03.03., Az. 4711",
        "ce_status": "in_bewertung", "ce_ort": "Info-Dialog"})

    # Das Formular schickt nur, was es anzeigt.
    kdb.save_konformitaet(CRA_DB, projekt, {"bewertungsweg": "H",
                                            "nb_kennnummer": "0123"})
    rec = kdb.get_konformitaet(CRA_DB, projekt, "")
    assert rec["notizen"] == "Prüfbericht TÜV vom 03.03., Az. 4711"
    assert rec["ce_status"] == "in_bewertung"
    assert rec["ce_ort"] == "Info-Dialog"


def test_ausdruecklich_leer_bleibt_leer(projekt):
    """Die Gegenprobe — sonst ließe sich nichts mehr löschen."""
    kdb.save_konformitaet(CRA_DB, projekt, {"bewertungsweg": "A", "notizen": "weg damit"})
    kdb.save_konformitaet(CRA_DB, projekt, {"bewertungsweg": "A", "notizen": ""})
    assert kdb.get_konformitaet(CRA_DB, projekt, "")["notizen"] == ""


def test_teil_update_hebelt_die_pruefung_aus_1759_nicht_aus(projekt):
    """#1759 verlangt bei B+C/H/EUCC die Angabe zur notifizierten Stelle.

    Die Prüfung soll die **Eingabe** beanstanden. Wird die Kennnummer
    ausdrücklich geleert, während „abgeschlossen" gilt, muss sie anschlagen —
    ein Rückfall auf den Altwert wäre genau das Loch, das #1759 geschlossen hat.
    """
    kdb.save_konformitaet(CRA_DB, projekt, {"bewertungsweg": "H", "nb_kennnummer": "0123",
                                            "bewertung_abgeschlossen": True})
    with pytest.raises(ValueError, match="Kennnummer"):
        kdb.save_konformitaet(CRA_DB, projekt, {"bewertungsweg": "H", "nb_kennnummer": "",
                                                "bewertung_abgeschlossen": True})


def test_teil_update_loescht_den_haken_nicht(projekt):
    """Ein Speichern, das den Haken nicht nennt, darf ihn nicht zurücknehmen —
    sonst fiele die Freigabe-Berechtigung durch einen Klick auf „Speichern"
    in einer anderen Karte weg."""
    _produkt_abgeschlossen(projekt)
    kdb.save_konformitaet(CRA_DB, projekt, {"ce_ort": "Handbuch S. 1"})
    assert kdb.get_konformitaet(CRA_DB, projekt, "")["bewertung_abgeschlossen"] is True


# ── Die EU-Konformitätserklärung des Produkts zählt für das Release ──────────

def test_doc_des_produkts_zaehlt_fuer_das_release(projekt):
    """Derselbe Defekt eine Station weiter.

    Ausgestellt wird die Erklärung im Konformitäts-Tab — also am
    Produkt-Datensatz. Das Gate betrachtete bei gesetzter Version **nur** die
    Zeile dieser Version. Auf Produktiv stand Produkt ``doc_ausgestellt=1,
    doc_version=3`` und Release 8.0.1 auf ``0``: Der gerechnete Punkt meldete
    „keine EU-Konformitätserklärung", obwohl sie dreimal ausgestellt war, und
    verwies in genau den Tab, in dem sie steht.

    Tragend ist dieselbe Stelle wie beim Bewertungsweg: Nach Erwägungsgrund 39
    löst eine Sicherheitsaktualisierung keine neue Erklärung aus.
    """
    from cra.konformitaet_gate import evaluate

    _produkt_abgeschlossen(projekt)
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER})
    assert evaluate(projekt, version=VER)["doc_ausgestellt"] is False

    # Vollständig, weil #1814 eine unvollständige Erklärung nicht mehr
    # ausstellt — hier ist sie Vorbedingung, nicht Prüfgegenstand.
    kdb.issue_doc(CRA_DB, projekt, {
        "produkt_name": "Testprodukt", "produkt_typ": "Typ A",
        "produkt_charge": VER,
        "hersteller": "pytest-firma-1805",
        "hersteller_adresse": "Musterweg 1, 12345 Musterstadt",
        "gegenstand": f"Testprodukt, Version {VER}",
        "ort": "Musterstadt", "datum": "2026-10-25",
        "unterzeichner_name": "M. Muster",
        "unterzeichner_funktion": "Geschäftsführung",
    }, "")
    assert evaluate(projekt, version=VER)["doc_ausgestellt"] is True, \
        "Die am Produkt ausgestellte Erklärung zählt für das Release nicht"


def test_freigabestatus_des_produkts_ersetzt_keine_erklaerung(projekt):
    """Die Abgrenzung, die das Erben tragbar macht.

    Vom Produkt wird nur die **ausgestellte Erklärung** übernommen, nicht sein
    Freigabestatus: Stünde die Produkt-Zeile auf „freigegeben", gälte die
    Erklärung sonst für jedes Release als vorhanden, ohne dass je eine
    ausgestellt wurde — eine Konformitätsaussage ohne Dokument.
    """
    from cra.konformitaet_gate import evaluate

    _produkt_abgeschlossen(projekt)
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER})
    con = cdb._connect(CRA_DB)
    try:
        con.execute("UPDATE cra_konformitaet SET freigabe_status='freigegeben' "
                    "WHERE projekt_name=? AND release_version=''", (projekt,))
        con.commit()
    finally:
        con.close()
    assert evaluate(projekt, version=VER)["doc_ausgestellt"] is False
