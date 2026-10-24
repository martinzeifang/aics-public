"""Anhang VII hat eine Liste, und die wesentliche Änderung eine Eingabestelle (#1763).

Zwei Funde aus der Lückenanalyse vor der 8.0.0-Freigabe, beide aus derselben
Familie: Dieselbe Sache war zweimal modelliert, und die beiden Fassungen
widersprachen sich.

* **Anhang VII**: acht Bausteine in der Beleg-Matrix, zehn Punkte in der
  Inhalts-Checkliste. Beide zeigten eine Vollständigkeitsquote; welche galt,
  hing vom geöffneten Reiter ab. Der Beleg-Matrix fehlten „angewandte Normen",
  die „Bewertung der grundlegenden Anforderungen" und der
  Unterstützungszeitraum.
* **Wesentliche Änderung**: ein vollständiges zweites Eingabeformular im
  Konformitäts-Reiter neben dem Release-Vorgang (#1755) — zwei Begründungen,
  zwei Audit-Spuren, und im Nachweis wäre nicht zu sagen, welche gilt.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_beide_listen_stammen_aus_einer_quelle():
    from cra import annex_vii
    from cra.traceability_db import ANNEX_VII_BAUSTEINE
    from shared.documents.catalog import _CL_CRA_TECH_DOKU

    assert {c.id for c in _CL_CRA_TECH_DOKU} == {p.key for p in annex_vii.inhalts_punkte()}
    assert {b["key"] for b in ANNEX_VII_BAUSTEINE} == {
        p.baustein_key or p.key for p in annex_vii.PUNKTE}


def test_beide_schluesselraeume_bleiben_wie_sie_waren():
    """Die Schlüssel sind **persistiert** — der Checklisten-Schlüssel hält den
    Ist-Status je Dokument, der Baustein-Schlüssel steht in
    ``cra_dokumente.annex_baustein``.

    Sie zusammenzuführen hätte in jeder laufenden Installation die gesetzten
    Haken und die zugeordneten Nachweise verwaisen lassen — ohne Fehlermeldung,
    einfach als plötzlich leere Spalten. Deshalb bleiben beide Namen, und die
    Zuordnung steht an einer Stelle. Dieser Test hält die historischen Namen
    fest, damit niemand sie „aufräumt".
    """
    from cra import annex_vii

    checkliste = {p.key for p in annex_vii.inhalts_punkte()}
    for alt in ("beschreibung", "design_entwicklung", "schwachstellenbehandlung",
                "konformitaetserklaerung_ref", "risikobewertung", "testberichte",
                "sbom"):
        assert alt in checkliste, alt

    bausteine = {p.baustein_key or p.key for p in annex_vii.PUNKTE}
    for alt in ("produktbeschreibung", "design", "vuln_handling", "doc",
                "risikobewertung", "testberichte", "sbom", "anleitung"):
        assert alt in bausteine, alt


def test_die_frueher_fehlenden_punkte_sind_in_der_beleg_matrix():
    """Der Kern des Fundes: Diese drei standen nur in der Checkliste."""
    from cra.traceability_db import ANNEX_VII_BAUSTEINE

    keys = {b["key"] for b in ANNEX_VII_BAUSTEINE}
    for fehlte in ("normen", "essentielle_anforderungen", "support_zeitraum"):
        assert fehlte in keys, fehlte


def test_unterschied_der_beiden_listen_ist_begruendet():
    """Ein Unterschied darf bleiben — aber nur ein erklärter.

    Die Benutzeranleitung gehört zu den vorzulegenden Unterlagen, ist aber ein
    eigenes Dokument nach Anhang II und **kein Inhalt** der technischen
    Dokumentation. Sie steht deshalb in der Beleg-Matrix und nicht in der
    Inhalts-Checkliste.
    """
    from cra.traceability_db import ANNEX_VII_BAUSTEINE
    from shared.documents.catalog import _CL_CRA_TECH_DOKU

    from cra import annex_vii

    # Verglichen wird über die Punkte, nicht über die Schlüssel: Beide Listen
    # benennen dieselben Punkte historisch verschieden (siehe
    # ``test_beide_schluesselraeume_bleiben_wie_sie_waren``).
    in_matrix = {p.key for p in annex_vii.PUNKTE}
    in_checkliste = {p.key for p in annex_vii.inhalts_punkte()}
    assert in_matrix - in_checkliste == {"anleitung"}, in_matrix - in_checkliste
    assert len(ANNEX_VII_BAUSTEINE) == len(_CL_CRA_TECH_DOKU) + 1


def test_jeder_punkt_nennt_seine_rechtsstelle():
    from cra import annex_vii

    ohne = [p.key for p in annex_vii.PUNKTE if not p.rechtsbezug.strip()]
    assert not ohne, ohne


def test_belege_der_drei_neuen_punkte_kommen_aus_den_registern():
    """Ihr Nachweis liegt nicht in einem hochgeladenen Dokument — er steht in
    den Registern der Anwendung und muss dort abgeholt werden."""
    quelle = (REPO / "cra/annex_evidence.py").read_text()
    for baustein in ("essentielle_anforderungen", "support_zeitraum", "normen"):
        assert f'"{baustein}"' in quelle, baustein


# ── Wesentliche Änderung: eine Eingabestelle ────────────────────────────────
def test_konformitaets_reiter_hat_kein_zweites_formular():
    roh = (REPO / "frontend/src/views/cra/KonformitaetPanel.vue").read_text()
    # Kommentare raus: Der Verweis auf die entfernte Funktion steht dort
    # absichtlich, damit nachvollziehbar bleibt, warum sie fehlt.
    panel = re.sub(r"<!--.*?-->|//[^\n]*", "", roh, flags=re.S)
    for weg in ("function doSubstantialMod", "doSubstantialMod(",
                "function toggleReassess", "toggleReassess("):
        assert weg not in panel, (
            f"{weg} ist zurueck: das zweite Erfassungsformular fuer die "
            f"wesentliche Aenderung")
    assert "'releases'" in panel, "der Sprung in den Release-Vorgang fehlt"


def test_wesentliche_aenderung_wird_einheitlich_zitiert():
    """„Art. 13(4)" und „Art. 3 Nr. 30" standen für dieselbe Sache
    nebeneinander. Sichtbare Artikelnummern sind das Erste, was ein
    fachkundiger Leser prüft — eine falsche kostet mehr Glaubwürdigkeit als
    eine fehlende Funktion."""
    panel = (REPO / "frontend/src/views/cra/KonformitaetPanel.vue").read_text()
    stelle = panel[panel.index("Wesentliche Änderung"):][:200]
    assert "Art. 3 Nr. 30" in stelle, stelle[:120]
    assert "13(4)" not in stelle, stelle[:120]

    katalog = (REPO / "cra/release_checkliste.py").read_text()
    assert "Art. 3 Nr. 30" in katalog


def test_normen_hinweis_steht_in_der_oberflaeche():
    """Dass es für die CRA noch keine harmonisierten Normen gibt, wusste
    bisher nur der Quelltext."""
    panel = (REPO / "frontend/src/views/cra/KonformitaetPanel.vue").read_text()
    assert re.search(r"keine[^<]{0,20}harmonisierten", panel, re.I), (
        "der Hinweis auf die fehlenden harmonisierten Normen fehlt")
