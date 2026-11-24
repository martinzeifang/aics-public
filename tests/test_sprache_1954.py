"""Die Sprache: zwei Kanäle, eine Quelle, und die KI folgt dem Mandanten (#1954).

Bewusst **ohne** Datenbank: Alles hier ist reine Logik, und genau die soll
nachprüfbar sein, ohne dass ein Postgres läuft. Die Auflösung Projekt → Firma
hat ihren eigenen Rundlauf in `test_sprache_firma_1954.py`.

WAS DIESER TEST FESTHÄLT, UND WARUM GERADE DAS
Der gefährlichste Teil der Zweisprachigkeit ist nicht eine fehlende
Übersetzung — die sieht man. Es ist eine Sprachanweisung, die mehr umstellt,
als sie soll: Verlangt ein Prompt JSON und übersetzt das Modell daraufhin die
**Feldnamen**, scheitert der Parser an einer Antwort, die inhaltlich richtig
ist. Bei Anthropic weist `ki_engine` `force_json` ausdrücklich als
`nicht_abbildbar` aus — dort hängt die Struktur allein am Prompt. Deshalb
prüft `test_die_sprachvorgabe_schuetzt_den_schluesselraum` nicht, dass der
Block vorhanden ist, sondern dass er seine Grenze nennt.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from shared import prompt_zusatz as pz
from shared import sprache as sp

WURZEL = Path(__file__).resolve().parents[1]


# --- Die Kanäle ------------------------------------------------------------


def test_normalisiere_ist_eine_positivliste():
    """Was nicht ausdrücklich erlaubt ist, fällt durch.

    Eine Negativliste hätte dieselbe Schwäche wie die drei ID-Prüfungen vor
    #1784: Sie denkt nicht an die Schreibweise, die noch kommt. `de-DE` und
    `EN` werden angenommen, weil sie so aus `Accept-Language` kommen.
    """
    assert sp.normalisiere("de") == "de"
    assert sp.normalisiere("EN") == "en"
    assert sp.normalisiere("en-GB") == "en"
    assert sp.normalisiere("de_DE") == "de"
    for unbekannt in ("eng", "ger", "fr", "klingon", "", "  ", None, 7, [], {"de": 1}):
        assert sp.normalisiere(unbekannt) == "", f"{unbekannt!r} durfte nicht durchgehen"


def test_nicht_gesetzt_ist_nicht_deutsch():
    """Der Unterschied, den `firmen.sprache` tragen muss.

    Leer heisst „nie entschieden": So bleibt sichtbar, bei welchen Mandanten
    noch niemand hingesehen hat. Eine Spalte, die „nein" und „nicht gesetzt"
    nicht unterscheiden kann, war die Falle in #1805.
    """
    assert sp.normalisiere("") == ""
    assert sp.oder_standard("") == sp.STANDARD
    assert sp.oder_standard("en") == "en"


def test_ohne_request_gilt_die_standardsprache():
    """Zeitplan, CLI und Tests haben keinen Request — und keinen Fehler."""
    assert sp.anzeige_sprache() == sp.STANDARD
    assert sp.inhalt_aus_request() == ""
    assert sp.fuer_lauf("cra", "") == ""


def test_die_docx_sprache_ist_gesetzt():
    """Ohne `w:lang` unterstreicht Word jedes Wort eines englischen Berichts rot.

    Bis 8.3.4 setzte das **nur** `gutachten/gerichtsgutachten_gen.py`, und
    zwar hart auf `de-DE` (#701) — kein anderer der acht Berichts-Renderer
    setzte überhaupt eine Dokumentsprache.
    """
    assert sp.docx_lang("de") == "de-DE"
    assert sp.docx_lang("en") == "en-GB"
    # Unbekanntes fällt auf den Standard, nicht auf eine leere Kennung:
    # ein leeres `w:lang` wäre schlimmer als ein falsches.
    assert sp.docx_lang("klingon") == sp.DOCX_LANG[sp.STANDARD]


def test_jede_sprache_hat_einen_namen_in_jeder_sprache():
    for anzeige in sp.SPRACHEN:
        namen = {e["code"] for e in sp.auswahl(anzeige)}
        assert namen == set(sp.SPRACHEN)
        for e in sp.auswahl(anzeige):
            assert e["name"] and e["name"] != e["code"], (
                f"Sprache {e['code']} hat in {anzeige} keinen Anzeigenamen")


def test_frontend_und_backend_kennen_dieselben_sprachen():
    """Zwei Listen derselben Sache sind zwei Gelegenheiten, sie zu trennen.

    Die Spiegel-Liste aus #1731/#1735, hier über die Sprachgrenze des
    Programms hinweg: Stünde im Frontend eine Sprache, die der Server nicht
    kennt, liesse sie sich auswählen und die Validierung wiese sie ab — mit
    einer Meldung über einen Wert, den die Oberfläche selbst angeboten hat.
    """
    idx = (WURZEL / "frontend" / "src" / "i18n" / "index.ts").read_text(encoding="utf-8")
    treffer = re.search(r"SPRACHEN:\s*readonly LocaleCode\[\]\s*=\s*\[([^\]]*)\]", idx)
    assert treffer, "SPRACHEN nicht in frontend/src/i18n/index.ts gefunden"
    vorne = tuple(re.findall(r"'(\w+)'", treffer.group(1)))
    assert vorne == sp.SPRACHEN, (
        f"Frontend kennt {vorne}, Backend {sp.SPRACHEN}")

    standard = re.search(r"STANDARD:\s*LocaleCode\s*=\s*'(\w+)'", idx)
    assert standard and standard.group(1) == sp.STANDARD, (
        "Die Standardsprache weicht zwischen Frontend und Backend ab")


def test_zu_jeder_sprache_gibt_es_einen_katalog():
    """Eine wählbare Sprache ohne Katalog ist eine Oberfläche voller Rohschlüssel."""
    for code in sp.SPRACHEN:
        verzeichnis = WURZEL / "frontend" / "src" / "i18n" / code
        assert verzeichnis.is_dir(), f"Katalogverzeichnis für {code} fehlt"
        assert list(verzeichnis.glob("*.json")), f"Katalog für {code} ist leer"


# --- Die KI folgt dem Mandanten -------------------------------------------


BASIS = "## Format\nAntworte NUR mit JSON. Felder: bewertung, kommentar."


def test_ohne_abweichende_sprache_bleibt_der_prompt_byte_identisch():
    """Die Zusage, die jeden Bestandstest zum Regressionsschutz macht.

    Dieselbe Zusage wie `evidence_section` und `issue_feedback_section`: Ohne
    Anlass wird nichts angehängt. Ein deutscher Prompt bringt eine deutsche
    Antwort von selbst — deshalb erzeugt `sprache='de'` keine Vorgabe.
    """
    assert pz.komponiere(BASIS, "") == BASIS
    assert pz.komponiere(BASIS, "", sprache="") == BASIS
    assert pz.komponiere(BASIS, "", sprache="de") == BASIS
    # Unbekanntes wird ignoriert, nicht zum Fehler: Eine kaputte
    # Sprachzuordnung darf keinen KI-Lauf zerreissen.
    assert pz.komponiere(BASIS, "", sprache="klingon") == BASIS
    assert pz.komponiere(BASIS, "", sprache=None) == BASIS


def test_der_vorrang_block_ist_unveraendert_wenn_keine_sprache_gilt():
    """Der Text von 8.3.4, byte-genau — er wurde aus Teilen neu zusammengesetzt."""
    mit_hinweis = pz.komponiere(BASIS, "Schwerpunkt ist die Fertigung.")
    assert pz.komponiere(BASIS, "Schwerpunkt ist die Fertigung.", sprache="de") == mit_hinweis
    assert pz._VORRANG in mit_hinweis
    assert "Die Hinweise ergänzen den Auftrag" in mit_hinweis


def test_eine_abweichende_sprache_wirkt():
    ergebnis = pz.komponiere(BASIS, "", sprache="en")
    assert ergebnis != BASIS
    assert ergebnis.startswith(BASIS)
    assert pz.MARKER_VORRANG in ergebnis
    # Ohne Hinweis darf der Block auch nicht von Hinweisen reden.
    assert pz.MARKER not in ergebnis
    assert "Die Hinweise ergänzen den Auftrag" not in ergebnis


def test_die_sprachvorgabe_schuetzt_den_schluesselraum():
    """Der eigentliche Grund für diesen Test — siehe Modul-Docstring.

    Eine Anweisung „antworte auf Englisch" lässt ein Modell auch `bewertung`
    zu `assessment` machen. Dann ist die Antwort inhaltlich richtig und der
    Parser scheitert. Die Vorgabe muss ihre Grenze im selben Atemzug nennen.
    """
    ergebnis = pz.komponiere(BASIS, "", sprache="en")
    assert "Übersetze keinen Schlüssel" in ergebnis
    assert "Feldnamen" in ergebnis
    for beispiel in ("erfuellt", "nicht_relevant"):
        assert beispiel in ergebnis, (
            f"Die Vorgabe nennt {beispiel!r} nicht als Beispiel eines Werts, "
            "der unverändert bleibt")


def test_die_sprache_steht_hinter_dem_hinweis_des_bearbeiters():
    """Die Akte gehört dem Mandanten, nicht dem Tagesgeschmack.

    Ein Sprachmodell gewichtet die letzte Anweisung am stärksten. Steht die
    Sprachvorgabe des Mandanten hinter dem Hinweis des Bearbeiters, gewinnt
    sie — und zwar ohne Wissen über den Aufbau des einzelnen Prompts
    (derselbe Mechanismus wie in #1832).
    """
    ergebnis = pz.komponiere(BASIS, "Bitte sehr ausführlich.", sprache="en")
    assert ergebnis.index(pz.MARKER) < ergebnis.index(pz.MARKER_VORRANG)
    assert ergebnis.index(pz.MARKER_VORRANG) < ergebnis.index("Antwortsprache")


def test_ein_anderslautender_hinweis_setzt_sich_nicht_durch():
    """Wer „antworte auf Englisch" schreibt, während der Mandant Deutsch führt.

    Es wird **keine** Sprachvorgabe erzeugt (Deutsch ist die Prompt-Sprache),
    und der Hinweis landet eingezäunt im Hinweis-Block — der Vorrang-Block
    dahinter sagt, dass Vorgaben gewinnen.
    """
    ergebnis = pz.komponiere(BASIS, "Antworte bitte auf Englisch.", sprache="de")
    assert "Antwortsprache" not in ergebnis
    assert pz._ZAUN_AUF in ergebnis and pz._ZAUN_ZU in ergebnis


def test_idempotent_auch_bei_reiner_sprachvorgabe():
    """Der Rückweg des WizardPromptModal — der Grund für #1954s Marker-Erweiterung.

    Die Maske schickt den **angezeigten**, schon komponierten Prompt an
    `/api/ai/run-stream` zurück. Bis 8.3.4 genügte dafür der Hinweis-Marker,
    weil ohne Hinweis nie etwas angehängt wurde. Eine Sprachvorgabe allein
    trägt ihn nicht — ohne die Erweiterung stünde der Block zweimal da.
    """
    einmal = pz.komponiere(BASIS, "", sprache="en")
    assert pz.komponiere(einmal, "", sprache="en") == einmal
    assert pz.komponiere(einmal, "Noch ein Hinweis", sprache="en") == einmal
    assert einmal.count(pz.MARKER_VORRANG) == 1
    assert pz.ist_komponiert(einmal)
    assert not pz.ist_komponiert(BASIS)


def test_die_engine_loest_die_sprache_selbst_auf():
    """Sie darf nicht in `KiAuftrag` verlangt werden.

    `shared/sse.py` setzt `projekt` nicht — auf dem SSE-Weg (rund 45
    Assistenten und `/api/ai/run-stream`) kennt die Engine das Projekt nicht.
    Die Sprache durch alle Aufrufer zu reichen wäre eine Signaturänderung an
    Dutzenden Stellen, bei der die nächste wieder fehlt (#1731/#1735). Der
    Wächter hält fest, dass die Auflösung in `_vorbereiten` steht.
    """
    import inspect

    from shared import ki_engine

    quelle = inspect.getsource(ki_engine._vorbereiten)
    quelle = re.sub(r"#.*", "", quelle)  # das Programm, nicht die Erzählung
    assert "fuer_lauf" in quelle, (
        "`_vorbereiten` löst die Mandantensprache nicht auf — dann wirkt sie "
        "auf keinem Engine-Weg")
    assert "sprache=sprache" in quelle, (
        "Die aufgelöste Sprache wird nicht an `komponiere` übergeben")


def test_alle_einspeisungen_reichen_die_sprache_durch():
    """Drei Engstellen, und keine darf fehlen.

    `server/middleware/prompt_zusatz` (Copy/Paste, ~58 Routen),
    `shared/ki_engine._vorbereiten` (jeder Engine-Lauf) und
    `server/api/ai_status` (`run-stream` plus die Anzeige-Komposition). Fehlt
    eine, verhält sich dieselbe Schaltfläche je nach Weg anders — und das
    fällt erst auf, wenn jemand eine Antwort nicht mehr erklären kann.
    """
    stellen = {
        "server/middleware/prompt_zusatz.py": 2,   # prompt + prompts-Liste
        "shared/ki_engine.py": 1,
        "server/api/ai_status.py": 2,              # komponieren + run-stream
    }
    for datei, mindestens in stellen.items():
        quelle = (WURZEL / datei).read_text(encoding="utf-8")
        quelle = re.sub(r"(?m)#.*$", "", quelle)
        anzahl = len(re.findall(r"komponiere\([^)]*sprache=", quelle))
        assert anzahl >= mindestens, (
            f"{datei}: {anzahl} von {mindestens} `komponiere`-Aufrufen reichen "
            "die Sprache durch")


def test_die_firmensprache_erreicht_das_frontend():
    """Eine Spalte, die `_serialize_firma` nicht nennt, kommt nie an.

    Genau das war der Mangel, den #1892 an `meta.hersteller` fand: richtige
    Ebene, aber in keiner Maske sichtbar.
    """
    rest = (WURZEL / "server" / "api" / "firmen.py").read_text(encoding="utf-8")
    assert "'sprache':" in rest and "'sprache_wirksam':" in rest, (
        "`_serialize_firma` liefert die Sprache nicht aus")
    assert "'sprachen':" in rest, "GET /constants bietet keine Sprachauswahl an"

    # Die Whitelist in firmen/db.py — ohne sie filtert `save_firma` still weg.
    db = (WURZEL / "firmen" / "db.py").read_text(encoding="utf-8")
    assert '"sprache",' in db, "`sprache` fehlt in _ALLOWED_FIELDS"
    assert "ADD COLUMN IF NOT EXISTS sprache" in db, (
        "Die Spalte wird für den Bestand nicht migriert")

    # Und im Formular, inklusive blankForm (die Falle aus #1858).
    maske = (WURZEL / "frontend" / "src" / "views" / "firmen" / "FirmenView.vue").read_text(encoding="utf-8")
    assert "form.sprache" in maske, "Die Firmenmaske hat kein Sprachfeld"
    assert re.search(r"sprache:\s*''", maske), (
        "`blankForm()` nennt `sprache` nicht — dann laufen Anzeige und "
        "Wirkung auseinander (#1858)")


def test_die_oberflaeche_schickt_ihre_sprachwahl_mit():
    """Bis 8.3.4 verliess die Sprachwahl den Browser nie.

    Damit konnte der Server nicht wissen, in welcher Sprache er antworten
    soll — seine Meldungen waren zwangsläufig deutsch, auch in einer
    englischen Oberfläche.
    """
    client = (WURZEL / "frontend" / "src" / "api" / "client.ts").read_text(encoding="utf-8")
    ohne_kommentar = re.sub(r"(?m)^\s*//.*$", "", client)
    assert "Accept-Language" in ohne_kommentar, (
        "Der Client schickt die Sprachwahl nicht mit")
    assert "getLocale()" in ohne_kommentar, (
        "Geschickt wird nicht die ausdrückliche Wahl des Anwenders")


def test_die_kataloge_sind_gueltiges_json():
    """Ein Tippfehler im Katalog bricht den Bau — hier fällt er früher auf."""
    for code in sp.SPRACHEN:
        for datei in sorted((WURZEL / "frontend" / "src" / "i18n" / code).glob("*.json")):
            json.loads(datei.read_text(encoding="utf-8"))
