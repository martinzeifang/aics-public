"""Überholtes finden und die Akte prüfen lassen (#1864).

Teil A rechnet, Teil B fragt — und beide halten sich an dieselbe Grenze: Es
entsteht **kein zweites Urteil**. Das Gate rechnet den Konformitätsstand; eine
Zahl aus diesen Wegen stünde irgendwann daneben, und niemand könnte die
Abweichung erklären (#1726/#1727/#1776).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cra.aktenpruefung import parse_antwort as akte_parsen
from shared.nachziehen import (BESCHREIBUNG, EREIGNISSE, WIRKSAM,
                               anlaesse, vergleiche)

WURZEL = Path(__file__).resolve().parents[1]


# ── Teil A: Überholtes, gerechnet ───────────────────────────────────────────

def _ev(aktion: str, tag: int) -> dict:
    return {"action": aktion, "created_at": f"2026-10-{tag:02d}T10:00:00Z"}


def test_nur_benannte_ereignisse_zaehlen():
    """Ein Anmeldevorgang überholt keine Bewertung. Wer bei allem anschlägt,
    wird abgeschaltet (#1774)."""
    liste = anlaesse([_ev("auth.login", 28), _ev("cra.sbom.eingelesen", 20)])
    assert [a[1] for a in liste] == ["cra.sbom.eingelesen"]


def test_juengster_anlass_steht_vorn():
    liste = anlaesse([_ev("cra.sbom.eingelesen", 20),
                      _ev("evidence.mapping.approved", 25)])
    assert liste[0][1] == "evidence.mapping.approved"


def test_ereignis_ohne_zeit_zaehlt_nicht():
    assert anlaesse([{"action": "cra.sbom.eingelesen"}]) == []
    assert anlaesse([{"action": "cra.sbom.eingelesen", "created_at": "gestern"}]) == []


def test_bewertung_vor_dem_ereignis_ist_ueberholt():
    liste = anlaesse([_ev("cra.sbom.eingelesen", 25)])
    treffer = vergleiche({"CRA-1": {"erzeugt_am": "2026-10-01T00:00:00Z"}}, liste)
    assert [t.objekt_id for t in treffer] == ["CRA-1"]
    assert "SBOM" in treffer[0].anlass


def test_bewertung_nach_dem_ereignis_ist_aktuell():
    liste = anlaesse([_ev("cra.sbom.eingelesen", 20)])
    assert vergleiche({"CRA-1": {"erzeugt_am": "2026-10-28T00:00:00Z"}}, liste) == []


def test_die_pruefung_eines_menschen_zaehlt():
    """Hat jemand die Bewertung nach dem Ereignis geprüft, ist sie nicht
    überholt — sonst hätte der Anwender dieselbe Arbeit zweimal."""
    liste = anlaesse([_ev("cra.sbom.eingelesen", 20)])
    herkunft = {"CRA-1": {"erzeugt_am": "2026-10-01T00:00:00Z",
                          "geprueft_am": "2026-10-25T00:00:00Z"}}
    assert vergleiche(herkunft, liste) == []


def test_ohne_zeitstempel_kein_befund():
    """„Nicht vergleichbar“ ist nicht „überholt“.

    Im Zweifel zu melden würde für jeden Bestandsdatensatz ohne Zeitstempel
    eine Überholung behaupten — die Liste wäre beim ersten Aufruf unbenutzbar.
    """
    liste = anlaesse([_ev("cra.sbom.eingelesen", 25)])
    assert vergleiche({"CRA-1": {"erzeugt_am": None, "geprueft_am": None}},
                      liste) == []


def test_ohne_anlass_keine_liste():
    assert vergleiche({"CRA-1": {"erzeugt_am": "2020-01-01T00:00:00Z"}}, []) == []


def test_ein_grund_je_objekt():
    """Eine Liste von Gründen je Objekt wäre für die Entscheidung
    „nochmal ansehen?“ ohne Wert."""
    liste = anlaesse([_ev("cra.sbom.eingelesen", 25),
                      _ev("evidence.mapping.approved", 26),
                      _ev("pentest.bericht.created", 27)])
    treffer = vergleiche({"CRA-1": {"erzeugt_am": "2026-10-01T00:00:00Z"}}, liste)
    assert len(treffer) == 1
    # Und zwar der jüngste.
    assert "Pentest" in treffer[0].anlass


def test_jedes_ereignis_hat_einen_satz():
    """Der Satz wird als Teilsatz in die Anzeige eingesetzt.

    Die erste Fassung dieses Tests verlangte Kleinschreibung — und wurde an
    \u201ePentest-Befunde wurden \u00fcbernommen\u201c rot, weil das ein
    Eigenname ist. Das war eine Regel, die ich mir gerade ausgedacht hatte,
    nicht die, auf die es ankommt: Der Satz darf **kein vollst\u00e4ndiger
    Satz mit Punkt** sein, sonst steht in der Anzeige ein Punkt mitten im
    Satz.
    """
    for aktion, satz in EREIGNISSE.items():
        assert satz, f"{aktion}: kein Satz"
        assert not satz.endswith("."), (
            f"{aktion}: endet mit einem Punkt \u2014 er wird als Teilsatz "
            "eingesetzt.")
        assert len(satz) > 15, f"{aktion}: zu knapp für die Anzeige"


# ── Alle Bewertungen, nicht nur die KI-generierten ──────────────────────────

def test_handbewertung_wird_auch_gesehen():
    """Der Nachtrag, der die Funktion erst brauchbar macht.

    Die erste Fassung las ausschließlich ``ki_herkunft`` — dort steht nur, was
    eine **KI** erzeugt hat. Wer 130 Anforderungen von Hand bewertet und danach
    einen Pentest-Bericht bekommt, hätte nie einen Hinweis erhalten;
    ausgerechnet diese Bewertungen sind die, auf die sich ein Prüfer verlässt.
    """
    liste = anlaesse([_ev("pentest.bericht.created", 25)])
    treffer = vergleiche({}, liste, objekt_art="requirement",
                         bewertet={"CRA-9": "2026-10-01T00:00:00Z"})
    assert [t.objekt_id for t in treffer] == ["CRA-9"]
    assert treffer[0].ki is False, "Von Hand bewertet — das soll die Anzeige sagen"


def test_spaetere_handaenderung_macht_aktuell():
    """Maßgeblich ist der jüngste bekannte Zeitpunkt — auch wenn er aus der
    Bewertung selbst stammt und nicht aus dem KI-Register."""
    liste = anlaesse([_ev("cra.sbom.eingelesen", 20)])
    treffer = vergleiche({"CRA-1": {"erzeugt_am": "2026-10-01T00:00:00Z"}}, liste,
                         bewertet={"CRA-1": "2026-10-28T00:00:00Z"})
    assert treffer == []


def test_beide_quellen_werden_vereinigt():
    liste = anlaesse([_ev("cra.sbom.eingelesen", 25)])
    treffer = vergleiche({"A": {"erzeugt_am": "2026-10-01T00:00:00Z"}}, liste,
                         bewertet={"B": "2026-10-02T00:00:00Z"})
    assert sorted(t.objekt_id for t in treffer) == ["A", "B"]
    assert [t.ki for t in sorted(treffer, key=lambda x: x.objekt_id)] == [True, False]


def test_jedes_modul_hat_eine_bewertungstabelle():
    """Die Namen sind historisch verschieden, die Struktur ist dieselbe —
    damit die Zuordnung nicht zur stillen Spiegel-Liste wird (#1731/#1735)."""
    from shared.nachziehen import BEWERTUNGEN
    erwartet = {"cra", "nis2", "aiact", "dsgvo", "wiba", "risikobewertung"}
    assert set(BEWERTUNGEN) == erwartet
    for modul, (db, tabelle, id_spalte, bedingung) in BEWERTUNGEN.items():
        quelle_db = {"cra": "cra/db.py", "nis2": "nis2/db.py",
                     "aiact": "ai_act/db.py", "dsgvo": "dsgvo/db.py",
                     "wiba": "wiba/db.py",
                     "risikobewertung": "risikobewertung/db.py"}[modul]
        text = (WURZEL / quelle_db).read_text(encoding="utf-8")
        assert tabelle in text, f"{modul}: Tabelle {tabelle} gibt es nicht mehr"
        assert "updated_at" in text, f"{modul}: kein Zeitstempel"
        assert id_spalte and bedingung


def test_route_haengt_unter_dem_modul_prefix():
    """Wörtlich die Lehre aus #1765/#1835/#1851: ``authz`` leitet Modul und
    Aktion aus dem URL-Prefix ab, und die Firmen-ACL löst die Firma über
    ``view_args['projekt_name']`` auf."""
    quelle = (WURZEL / "shared" / "nachziehen.py").read_text(encoding="utf-8")
    assert '"/projekte/<projekt_name>/ueberholt"' in quelle
    for pfad in ("server/api/cra/__init__.py", "server/api/nis2.py",
                 "server/api/aiact.py", "server/api/dsgvo.py",
                 "server/api/risikobewertung.py", "server/api/wiba/__init__.py"):
        text = (WURZEL / pfad).read_text(encoding="utf-8")
        assert "_register_ueberholt(" in text, f"{pfad}: Route fehlt"
        assert "objekt_art=" in text, (
            f"{pfad}: ohne Objektart stehen bei CRA Anforderungen, "
            "OWASP-Kontrollen, Risiken und Schwachstellen in einer Liste.")


def test_teil_a_braucht_keine_ki():
    quelle = (WURZEL / "shared" / "nachziehen.py").read_text(encoding="utf-8")
    for verboten in ("ki_lauf", "KiAuftrag", "generate_text"):
        assert verboten not in quelle, (
            f"{verboten} in nachziehen.py — der Vergleich \u201eBewertung "
            "\u00e4lter als Ereignis\u201c ist Arithmetik und kostet nichts.")


# ── Teil B: Aktenprüfung ────────────────────────────────────────────────────

def test_befunde_werden_nach_schwere_sortiert():
    b = akte_parsen({"befunde": [
        {"art": "luecke", "befund": "A", "schwere": "niedrig"},
        {"art": "widerspruch", "befund": "B", "schwere": "hoch"},
        {"art": "belegtiefe", "befund": "C", "schwere": "mittel"}]})
    assert [x["befund"] for x in b] == ["B", "C", "A"]


def test_kein_zweites_urteil():
    """Eine Ampel oder Punktzahl wird verworfen, auch wenn das Modell sie
    liefert. Sie stünde irgendwann neben der gerechneten."""
    b = akte_parsen({"ampel": "gruen", "score": 95, "konform": True,
                     "befunde": [{"art": "luecke", "befund": "X"}]})
    assert len(b) == 1
    assert set(b[0]) == {"art", "stelle", "befund", "rueckfrage", "schwere"}


def test_unbekannte_art_wird_eingeordnet_nicht_verworfen():
    """Der Befund selbst ist die Information; eine erfundene Kategorie macht
    ihn nicht wertlos."""
    b = akte_parsen({"befunde": [{"art": "phantasie", "befund": "X"}]})
    assert b[0]["art"] == "luecke"


def test_befund_ohne_text_entfaellt():
    assert akte_parsen({"befunde": [{"art": "luecke", "befund": "  "}]}) == []


def test_leere_antwort_ist_zulaessig():
    assert akte_parsen({"befunde": []}) == []
    assert akte_parsen({"etwas": "anderes"}) == []


def test_der_prompt_verlangt_kein_urteil():
    quelle = (WURZEL / "cra" / "aktenpruefung.py").read_text(encoding="utf-8")
    assert "keine Gesamtnote" in quelle and "keine Ampel" in quelle, (
        "Der Auftrag muss das Urteil ausdrücklich ausschließen — sonst liefert "
        "das Modell eines, und es landet neben dem gerechneten.")
    assert "Erfinde keine Dokumente" in quelle


def test_die_akte_ist_eigener_bestand_kein_fremdtext():
    """Sie wird **nicht** als ``BEGIN_UNTRUSTED_DATA`` gerahmt — anders als
    Kundendokumente in #1861. Genau sie soll beurteilt werden."""
    quelle = (WURZEL / "cra" / "aktenpruefung.py").read_text(encoding="utf-8")
    assert "add_untrusted_block" not in quelle


def test_aktenpruefung_laeuft_ueber_die_engine():
    quelle = (WURZEL / "cra" / "aktenpruefung.py").read_text(encoding="utf-8")
    assert "ki_lauf" in quelle
    assert 'aufgabe="aktenpruefung"' in quelle
    assert "egress_pflicht=True" in quelle
    from shared.ki_engine import budget_fuer
    assert budget_fuer("aktenpruefung") >= 4096


def test_der_lauf_schreibt_nichts_an_der_akte():
    """Er erzeugt eine Mängelliste, keine Bewertung."""
    quelle = (WURZEL / "cra" / "aktenpruefung.py").read_text(encoding="utf-8")
    for verboten in ("save_konformitaet", "upsert", "set_release", "INSERT"):
        assert verboten not in quelle, f"{verboten}: der Lauf schreibt"


def test_endpunkte_verlangen_nur_leserecht():
    """Der Lauf schreibt nichts; die Freigaberechte (#1743) bleiben der
    Freigabe vorbehalten."""
    quelle = (WURZEL / "server" / "api" / "cra_konformitaet.py").read_text(encoding="utf-8")
    block = quelle.split("#1864/B", 1)[1]
    assert "Permission.CRA_READ" in block
    assert "CRA_APPROVE" not in block and "CRA_WRITE" not in block


@pytest.mark.parametrize("weg", ["aktenpruefung", "aktenpruefung/prompt",
                                 "aktenpruefung/import"])
def test_beide_wege_sind_verdrahtet(weg: str):
    """Prompt zum Kopieren **und** Direktlauf — beide bleiben erhalten."""
    quelle = (WURZEL / "server" / "api" / "cra_konformitaet.py").read_text(encoding="utf-8")
    assert f'/projekte/<projekt_name>/{weg}"' in quelle


def test_die_masken_rechnen_nichts_selbst():
    for datei in ("shared/UeberholtModal.vue", "cra/AktenpruefungModal.vue"):
        inhalt = (WURZEL / "frontend" / "src" / "components" / datei).read_text(encoding="utf-8")
        # Keine eigene Schwere-Reihenfolge, keine eigene Überholt-Logik.
        assert "sort(" not in inhalt, f"{datei}: sortiert selbst — der Server tut es"


# ── #1870: Die Namen sind belegt, nicht abgeschrieben ───────────────────────

def _geschriebene_ereignisnamen() -> set[str]:
    """Alle Ereignisnamen, die der **Produktionscode** schreibt.

    Erfasst `audit_event("…")`, die Modul-Helfer (`_audit`, `_cra_audit`) und
    `audit_assessment`. Tests und Arbeitskopien unter `.claude/` zählen nicht
    — sonst bestätigte sich die Erfindung selbst, und genau das ist passiert.
    """
    muster = re.compile(
        r'(?:audit_event|_audit|_cra_audit|audit_assessment)\(\s*'
        r'["\']([a-zA-Z0-9_.]+)["\']')
    namen: set[str] = set()
    for p in WURZEL.rglob("*.py"):
        rel = p.relative_to(WURZEL).as_posix()
        if rel.startswith((".claude/", "tests/")) or "/.venv/" in f"/{rel}":
            continue
        namen |= set(muster.findall(p.read_text(encoding="utf-8")))
    return namen


def test_jeder_ereignisname_wird_auch_geschrieben():
    """Der Prüfer, der bei #1864 gefehlt hat (#1870).

    Fünf von neun Namen in `EREIGNISSE` waren erfunden — `cra.sbom.imported`
    statt `cra.sbom.eingelesen`, `pentest.bericht.created` statt
    `…created`, und `cra.vuln.synced` gab es überhaupt nicht. Der Dialog
    suchte nach Ereignissen, die nie eintreten, und das fiel niemandem auf:
    Die Bestandstests brachten ihre Ereignisse selbst mit und prüften damit
    nur, dass `anlaesse` eine Zuordnung anwendet — nicht, dass sie zu dieser
    Anwendung passt.
    """
    geschrieben = _geschriebene_ereignisnamen()
    assert geschrieben, "keine Ereignisnamen gefunden — das Muster greift nicht"
    fehlend = sorted(a for a in EREIGNISSE if a not in geschrieben)
    assert not fehlend, (
        "Ereignisnamen, die keine Stelle im Produktionscode schreibt: "
        + ", ".join(fehlend))


def test_ueberholte_liest_die_ereignisse_wirklich():
    """Der Hauptdefekt aus #1870 — und er saß **in** `ueberholte`.

    Gelesen wurde `roh.get("revisionspfad") or roh.get("items")`; beide
    Schlüssel gibt es nicht, `projekt_ereignisse` liefert `events`. Damit war
    die Anlassliste **immer** leer und `vergleiche` kehrte sofort um: Der
    Dialog war seit #1864 in jedem Modul auf jeder Instanz leer — und meldete
    `vollstaendig: True`, also „alles aktuell".

    Dieser Test geht **durch** `ueberholte()` statt an ihm vorbei. Genau das
    hat gefehlt: Die Bestandstests riefen `anlaesse` und `vergleiche` direkt.
    """
    from shared import nachziehen as nz

    ereignis = {"action": "cra.sbom.eingelesen",
                "created_at": "2026-10-20T10:00:00Z"}
    gerufen: dict[str, object] = {}

    def falsche_spur(modul, projekt, **kw):
        gerufen["modul"] = modul
        # Genau die Form, die der echte Revisionspfad liefert.
        return {"events": [ereignis], "total": 1, "limit": 200, "offset": 0,
                "fenster": 2000, "fenster_erschoepft": False}

    import shared.audit_db as adb
    alt_spur = adb.projekt_ereignisse
    alt_herkunft = nz.bewertungsstaende
    alt_firma = nz._firma_von
    adb.projekt_ereignisse = falsche_spur
    nz.bewertungsstaende = lambda m, p: {"CRA-1": "2026-10-10T10:00:00Z"}
    # Die Firmen-Auflösung ist hier nicht der Gegenstand — und ohne Datenbank
    # liefe sie 30 s in einen Pool-Timeout.
    nz._firma_von = lambda m, p: ""
    import shared.ki_herkunft as kh
    alt_kh = kh.fuer_projekt
    kh.fuer_projekt = lambda m, p, a="": {}
    try:
        erg = nz.ueberholte("cra", "Produkt X")
    finally:
        adb.projekt_ereignisse = alt_spur
        nz.bewertungsstaende = alt_herkunft
        nz._firma_von = alt_firma
        kh.fuer_projekt = alt_kh

    assert gerufen.get("modul") == "cra"
    assert erg["anlaesse"] == 1, "die Ereignisse kommen nicht an"
    assert erg["items"], "die überholte Bewertung wird nicht gemeldet"
    assert erg["items"][0]["objekt_id"] == "CRA-1"


def test_leere_liste_unterscheidet_die_beiden_faelle():
    """„Keine Ereignisse" ist nicht „nichts überholt" (#1870).

    Die Leermeldung behauptete das Zweite, obwohl das Erste vorlag — ein
    Satz, auf den sich ein Prüfer verlässt.
    """
    from shared import nachziehen as nz
    import shared.audit_db as adb

    leer = {"events": [], "total": 0, "limit": 200, "offset": 0,
            "fenster": 2000, "fenster_erschoepft": False}
    alt_spur, alt_bew = adb.projekt_ereignisse, nz.bewertungsstaende
    alt_firma = nz._firma_von
    adb.projekt_ereignisse = lambda m, p, **kw: leer
    nz.bewertungsstaende = lambda m, p: {"CRA-1": "2026-10-10T10:00:00Z"}
    nz._firma_von = lambda m, p: ""
    import shared.ki_herkunft as kh
    alt_kh = kh.fuer_projekt
    kh.fuer_projekt = lambda m, p, a="": {}
    try:
        erg = nz.ueberholte("cra", "Produkt X")
    finally:
        adb.projekt_ereignisse, nz.bewertungsstaende = alt_spur, alt_bew
        nz._firma_von = alt_firma
        kh.fuer_projekt = alt_kh

    assert erg["anlaesse"] == 0
    assert erg["bewertungen"] == 1, (
        "die Zahl der Bewertungen muss stehen — sonst kann die Maske nicht "
        "sagen, ob überhaupt etwas zu vergleichen war")


def test_firmenweite_ereignisse_ohne_firma_zaehlen_nicht():
    """Die ruhige Richtung (#1870).

    Ein Pentest-Bericht, der sich keiner Firma zuordnen lässt, würde sonst
    allen Mandanten eine Überholung anhängen — und eine Liste, die bei allen
    anschlägt, wird abgeschaltet (#1774).
    """
    from shared import nachziehen as nz
    alt = nz._firma_von
    nz._firma_von = lambda m, p: ""
    try:
        assert nz._firmenweite_anlaesse("cra", "Produkt X", 2000) == []
    finally:
        nz._firma_von = alt


# ── #1877: Ein Lauf ohne Wirkung ist kein Anlass ────────────────────────────

class TestWirkungslosesEreignis1877:
    """Aus dem Betrieb: Der Schwachstellen-Abgleich setzte jede Bewertung auf
    „überholt", obwohl er nichts gefunden hatte (`neu: 0, aktualisiert: 0`).

    Der Abgleich läuft häufig und auf Wunsch im Zeitplan. Zählte der leere
    Lauf mit, enthielte die Übersicht nach jedem Lauf **alles** — und eine
    Liste, die immer alles enthält, wird nicht mehr gelesen (#1774).
    """

    @staticmethod
    def _ereignis(action: str, details: dict, ts: str = "2026-10-29T22:42:49+00:00"):
        return {"action": action, "ts": ts, "details": details}

    def test_leerer_schwachstellen_abgleich_ist_kein_anlass(self):
        leer = self._ereignis("cra.vuln.sync",
                              {"neu": 0, "aktualisiert": 0, "neu_hoch_kritisch": 0})
        assert anlaesse([leer]) == [], (
            "Ein Abgleich ohne Fund darf keine Bewertung überholen — genau "
            "der gemeldete Fall aus #1877.")

    def test_abgleich_mit_fund_ist_ein_anlass(self):
        treffer = self._ereignis("cra.vuln.sync",
                                 {"neu": 3, "aktualisiert": 0, "neu_hoch_kritisch": 1})
        erg = anlaesse([treffer])
        assert len(erg) == 1
        satz = erg[0][2]
        assert "3 neue Schwachstelle" in satz, satz
        assert "hoch/kritisch" in satz, (
            "Die Zahlen stehen im Eintrag; sie nicht zu nennen zwingt zum "
            "Nachsehen an anderer Stelle.")

    def test_nur_aktualisierte_zaehlen_auch(self):
        erg = anlaesse([self._ereignis(
            "cra.vuln.sync", {"neu": 0, "aktualisiert": 2, "neu_hoch_kritisch": 0})])
        assert len(erg) == 1 and "2 aktualisierte" in erg[0][2]

    def test_leerer_komponenten_import_ist_kein_anlass(self):
        assert anlaesse([self._ereignis(
            "cra.sbom_komponenten.importiert", {"anzahl": 0})]) == []
        assert len(anlaesse([self._ereignis(
            "cra.sbom_komponenten.importiert", {"anzahl": 12})])) == 1

    def test_ereignisse_ohne_bedingung_zaehlen_unveraendert(self):
        """Bestandsverhalten: Wer nicht in WIRKSAM steht, zählt wie bisher.

        Auch ohne `details` — ältere Einträge führen keine Mengen, und sie
        nachträglich als wirkungslos zu werten hieße, den Bestand stumm zu
        schalten.
        """
        erg = anlaesse([self._ereignis("cra.sbom.eingelesen", {})])
        assert len(erg) == 1
        ohne = {"action": "cra.sbom.eingelesen", "ts": "2026-10-29T22:42:49+00:00"}
        assert len(anlaesse([ohne])) == 1

    def test_jede_bedingung_gilt_einem_bekannten_ereignis(self):
        """Ein Eintrag in WIRKSAM für einen Namen, den EREIGNISSE nicht kennt,
        wäre wirkungslos — und niemand merkte es."""
        unbekannt = set(WIRKSAM) - set(EREIGNISSE)
        assert not unbekannt, f"WIRKSAM nennt unbekannte Ereignisse: {unbekannt}"
        unbekannt2 = set(BESCHREIBUNG) - set(EREIGNISSE)
        assert not unbekannt2, f"BESCHREIBUNG nennt unbekannte: {unbekannt2}"
