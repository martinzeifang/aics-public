"""#1941 — eine Risiko-Akzeptanz muss sich zurücknehmen lassen.

Meldung aus dem Betrieb: *„bei den CRA-Anforderungen hab ich die Akzeptanzen
rausgenommen und die Verknüpfung gelöst."* Gemessen auf Produktiv **und** Test:
Die Akzeptanzen waren unverändert da, mit ``updated_at`` vom 19. Oktober — nur
die Verknüpfungen fehlten.

Drei Befunde griffen ineinander:

1. ``RequirementRiskLinks.vue`` zeigte „akzeptieren" nur bei
   ``behandlung !== 'akzeptiert'``. Ist akzeptiert, verschwand der Knopf, und
   einen zum Zurücknehmen gab es nicht — eine Einbahnstraße, obwohl
   ``set_risiko_behandlung`` den Rückweg konnte.
2. Übrig blieb „lösen", und das tut etwas anderes.
3. **Und das Lösen nimmt die Akzeptanz dem Gate nicht.** ``_accepted_gap_for``
   liest ``felder._source_id`` aus dem Risiko; das Lösen entfernt eine Zeile aus
   ``risk_requirement_links`` und lässt ``felder_json`` unberührt. Belegt: nach
   dem Lösen meldete das Gate ``IMPL-06`` weiter als ``begruendet`` mit dem
   Grund „Schulung nicht notwendig, da keine Anwender".

Daraus wurde eine falsche Begründung, die das Gate trägt **und** an der
Anforderung nicht mehr zu sehen ist — schlechter als vor der Handlung.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

# #1954: Die Oberfläche trägt den Text nicht mehr als Literal — er steht
# im Nachrichten-Katalog. `vue_text` löst die `$t('…')`-Schlüssel auf, damit
# dieser Wächter weiter die **Oberfläche** prüft und nicht die Benennung.
from tests.i18n_text import vue_text  # noqa: E402

_WURZEL = Path(__file__).resolve().parents[1]


# ── ohne Datenbank prüfbar ────────────────────────────────────────────────────

def test_ruecknahme_verlangt_eine_begruendung_von_substanz() -> None:
    from risikobewertung.db import RUECKNAHME_GRUND_MIN
    assert RUECKNAHME_GRUND_MIN == 20, (
        "Dieselbe Zahl wie beim Testverzicht (#1824) und beim Verwerfen eines "
        "Release-Vorgangs (#1876). Eine Entscheidung, die sich in weniger als "
        "zwanzig Zeichen begründen lässt, ist nicht begründet."
    )


def test_vermerk_nennt_datum_person_und_grund() -> None:
    from risikobewertung.db import _ruecknahme_vermerk
    v = _ruecknahme_vermerk("Die Begründung verkennt die Anforderung.", "Martin Zeifang")
    assert "zurückgenommen" in v
    assert "Martin Zeifang" in v
    assert "Die Begründung verkennt die Anforderung." in v
    assert re.search(r"\d{4}-\d{2}-\d{2}", v), "Das Datum gehört in den Vermerk"


def test_ruecknahme_setzt_auch_rechtsgrundlage_zurueck() -> None:
    """Der Nebenbefund, der erst beim Lesen auffiel.

    Der Nicht-Akzeptanz-Zweig setzte ``akzeptanz_*`` zurück, aber **nicht**
    ``rechtsgrundlage`` und nicht ``resolved_reason``. Eine zurückgenommene
    Akzeptanz behielt damit ihre Fundstelle und den Satz
    „Akzeptiert (restrisiko): …" — beides liest sich wie eine Begründung für
    eine Entscheidung, die niemand mehr trifft.
    """
    from risikobewertung.db import set_risiko_behandlung
    quelle = inspect.getsource(set_risiko_behandlung)
    zweig = quelle.split("else:", 1)[1]
    assert "rechtsgrundlage=''" in zweig, "rechtsgrundlage bleibt sonst stehen"
    assert "resolved_reason" in zweig, "resolved_reason bleibt sonst stehen"


def test_die_person_stempelt_der_server() -> None:
    """Muster ``set_release_art`` (#1793) und ``bestaetige_marker`` (#1868).

    Eine Entscheidung, deren Urheber der Browser mitschickt, ist keine. Geprüft
    wird der kommentarfreie Quelltext — zweimal hat in diesem Haus ein Wächter
    auf einen Kommentar angeschlagen, der den alten Zustand zitierte.
    """
    quelle = (_WURZEL / "server" / "api" / "risikobewertung.py").read_text(encoding="utf-8")
    start = quelle.index("def behandlung_risiko")
    abschnitt = re.sub(r"#.*", "", quelle[start:start + 2400])
    assert "_person(" in abschnitt, (
        "Bei einer Rücknahme muss der Server die Person aus dem Token setzen, "
        "nicht der Browser sie mitschicken."
    )
    assert "'user_id'" in abschnitt or '"user_id"' in abschnitt, (
        "#1784: Ohne `user_id` schreibt der Revisionspfad nur, dass "
        "irgendwer gehandelt hat - und bei einer Rücknahme ist genau das "
        "die Frage."
    )


def test_die_maske_bietet_den_rueckweg_und_warnt_beim_loesen() -> None:
    datei = _WURZEL / "frontend" / "src" / "components" / "shared" / "RequirementRiskLinks.vue"
    quelle = vue_text(datei)
    ohne = re.sub(r"<!--.*?-->", "", quelle, flags=re.S)
    assert "zurücknehmen" in ohne, "Der Rücknahme-Knopf fehlt"
    assert "ruecknahme_grund" in ohne, "Die Maske schickt keine Begründung mit"
    assert re.search(r"behandlung === 'akzeptiert'[^\n]*\n[^\n]*zurücknehmen|"
                     r"v-if=\"r\.behandlung === 'akzeptiert'\"", ohne), (
        "Der Rücknahme-Knopf muss genau dann erscheinen, wenn akzeptiert ist — "
        "das Gegenstück zur Bedingung am 'akzeptieren'-Knopf."
    )
    # Das Lösen muss vorher sagen, dass es die Akzeptanz nicht wegnimmt.
    assert "wirkt weiter im Konformitäts-Gate" in ohne, (
        "Beim Lösen eines akzeptierten Risikos fehlt die Warnung. Der Anwender "
        "findet sonst genau einen Knopf, der wie der Weg heraus aussieht."
    )


# ── Rundlauf (braucht Postgres, läuft in der CI) ─────────────────────────────

@pytest.mark.usefixtures("_pg_isolate")
def test_rundlauf_akzeptieren_zuruecknehmen() -> None:
    """Die Behauptung „setzt die Felder zurück" lässt sich nicht aus dem
    Quelltext ablesen — das ist die Lehre aus #1785."""
    # Namen gegen `dir(risikobewertung.db)` geprüft, nicht geraten. Dreimal
    # falsch geraten, bevor ich nachgesehen habe: Es gibt **keinen**
    # `DEFAULT_DB_PATH` (die Bestandstests tragen den Pfad selbst), **kein**
    # `ensure_db` (`_connect` legt das Schema bei jeder Verbindung selbst an)
    # und **kein** `upsert_risiko` — die Funktion heißt `save_risiko(db, risk)`
    # und erwartet `projekt_name` im Dict. Dieselbe Klasse wie #1892; dort hat
    # der `_sicher`-Wrapper es verschluckt, hier scheitert der Import hart.
    from risikobewertung.db import save_risiko, set_risiko_behandlung

    db = Path("data/db/risikobewertung.sqlite")
    projekt = "Rücknahme-Test 1941"
    rid = int(save_risiko(db, {"projekt_name": projekt, "nr": 1,
                               "risk_name": "Nichterfüllung TEST-01",
                               "beschreibung": "für den Rundlauf",
                               "framework": "STRIDE", "felder": {}}))

    nach = set_risiko_behandlung(
        db, rid, behandlung="akzeptiert", kategorie="restrisiko",
        grund="Restrisiko mit Begründung, die Substanz hat.",
        von="Prüferin", review="2027-03-31", rechtsgrundlage="Art. 13 Abs. 4")
    assert nach and nach["behandlung"] == "akzeptiert"
    assert nach["rechtsgrundlage"] == "Art. 13 Abs. 4"
    assert nach["is_resolved"]

    # Ohne Begründung geht die Rücknahme nicht.
    with pytest.raises(ValueError, match="Rücknahme"):
        set_risiko_behandlung(db, rid, behandlung="offen")
    with pytest.raises(ValueError):
        set_risiko_behandlung(db, rid, behandlung="offen", ruecknahme_grund="zu kurz")

    zurueck = set_risiko_behandlung(
        db, rid, behandlung="offen", von="Prüferin",
        ruecknahme_grund="Die Begründung verkennt die Anforderung und hält nicht.")
    assert zurueck
    assert zurueck["behandlung"] == "offen"
    assert not zurueck["akzeptanz_kategorie"]
    assert not zurueck["akzeptanz_grund"]
    assert not zurueck["rechtsgrundlage"], "die Fundstelle muss mit weg"
    assert not zurueck["resolved_reason"], "'Akzeptiert (…)' darf nicht stehen bleiben"
    assert not zurueck["is_resolved"]
    assert "zurückgenommen" in str(zurueck["bewertung_text"] or ""), (
        "Die Spur, dass eine Akzeptanz bestand, gehört in die Akte — genau sie "
        "hat das Löschen der Risiken zerstört."
    )

    # Ein Wechsel, der KEINE Rücknahme ist, bleibt ohne Begründungspflicht.
    set_risiko_behandlung(db, rid, behandlung="reduziert")


# ── der gerechnete Widerspruch (ohne Datenbank) ──────────────────────────────

def test_akzeptanz_ohne_verknuepfung_wird_benannt(monkeypatch) -> None:
    """Der Kern des Befunds: Das Lösen nimmt die Akzeptanz dem Gate nicht.

    Nachgestellt wird der gemessene Zustand — eine Akzeptanz, deren Zeile in
    ``risk_requirement_links`` fehlt. Der Punkt muss erscheinen, **und die
    Akzeptanz muss weiter zählen**: Sie zu verwerfen, weil eine Zeile in einer
    Anzeigetabelle fehlt, wäre dieselbe stille Entscheidung in die andere
    Richtung.
    """
    from shared import risk_req_links
    from cra import konformitaet_gate as kg

    monkeypatch.setattr(risk_req_links, "list_for_project",
                        lambda *a, **k: [], raising=True)
    punkte: list[dict] = []
    ohne = kg._check_akzeptanz_verknuepfung(
        "RB-Projekt", {"IMPL-06": {"id": 104, "akzeptanz_grund": "…"}}, punkte)
    assert ohne == ["IMPL-06"]
    assert len(punkte) == 1
    assert "IMPL-06" in punkte[0]["titel"]
    assert "zurücknehmen" in punkte[0]["hinweis"], (
        "Der Hinweis muss den Rückweg nennen — sonst löst der Anwender wieder "
        "die Verknüpfung, und genau das hilft nicht."
    )


def test_vorhandene_verknuepfung_schlaegt_nicht_an(monkeypatch) -> None:
    """Ein Prüfpunkt, der bei richtigem Verhalten anschlägt, wird abgeschaltet
    (die Lehre aus #1774 und #1877)."""
    from types import SimpleNamespace
    from shared import risk_req_links
    from cra import konformitaet_gate as kg

    monkeypatch.setattr(
        risk_req_links, "list_for_project",
        lambda *a, **k: [SimpleNamespace(modul="cra", object_kind="requirement",
                                         anforderung_id="IMPL-06", risk_id=104)],
        raising=True)
    punkte: list[dict] = []
    assert kg._check_akzeptanz_verknuepfung(
        "RB-Projekt", {"IMPL-06": {"id": 104}}, punkte) == []
    assert punkte == []


def test_ohne_akzeptanz_wird_nicht_geprueft(monkeypatch) -> None:
    from shared import risk_req_links
    from cra import konformitaet_gate as kg
    def _nie(*a, **k):  # pragma: no cover
        raise AssertionError("ohne Akzeptanz darf die Tabelle nicht gelesen werden")
    monkeypatch.setattr(risk_req_links, "list_for_project", _nie, raising=True)
    punkte: list[dict] = []
    assert kg._check_akzeptanz_verknuepfung("RB-Projekt", {}, punkte) == []
    assert kg._check_akzeptanz_verknuepfung("", {"X": {"id": 1}}, punkte) == []
