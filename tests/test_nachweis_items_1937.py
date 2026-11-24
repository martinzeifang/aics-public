"""#1937 — verknüpfte Nachweise müssen die KI-Bewertung erreichen.

Am 02.11.2026 hingen die Dossier-Dokumente als Nachweise an den Anforderungen
(20 Zeilen in ``cra_dokumente`` auf Produktiv). Die Massenbewertung danach hat
sie **nicht angerechnet** — ``cra/evidence_provider.py`` hatte vier
Sammelfunktionen, und keine las ``cra_dokumente``. Ergebnis: Bewertungen, die
vorhandene Nachweise als fehlend melden („keine dokumentierte Benennung eines
CRA-Verantwortlichen" für IMPL-01 — sie steht namentlich in
``docs/cra/governance.md``).

Geprüft wird hier **verhaltensseitig**: Der Provider wird mit einer
nachgestellten Nachweiszeile aufgerufen und muss sie herausgeben. Ein Test, der
nur ``"cra_dokumente" in getsource(...)`` prüft, bleibt grün, wenn die Zeile
durch ``pass`` ersetzt wird — das Wort steht dann noch im Kommentar darüber
(die Lehre aus #1834, zweimal gemacht).
"""

from __future__ import annotations

from pathlib import Path

_CRA_DB = Path("data/db/cra.sqlite")


def _zeile(**kw):
    grund = {"id": 1, "doc_name": "CRA-Dossier: Governance", "doc_type": "resource",
             "anforderung_id": "IMPL-01", "annex_baustein": "design",
             "doc_path": "docs/cra/governance.md"}
    grund.update(kw)
    return grund


# ── Zusammenführung (die Falle aus #1824) ────────────────────────────────────

def test_dieselbe_datei_zaehlt_einmal() -> None:
    """Auf Produktiv lag derselbe Pentest-Bericht achtmal in `cra_dokumente`.

    Acht „Nachweise" für einen Test im Prompt sind keine acht Nachweise — sie
    sehen nur so aus, und genau das darf ein Nachweisblock nicht tun.
    """
    from shared.nachweis_items import _zusammenfuehren
    acht = [_zeile(id=i, doc_path="evidence:abc-123",
                   doc_name=f"Pentest-Bericht (Kopie {i})") for i in range(8)]
    assert len(_zusammenfuehren(acht)) == 1


def test_verschiedene_dateien_bleiben_getrennt() -> None:
    from shared.nachweis_items import _zusammenfuehren
    zwei = [_zeile(id=1, doc_path="evidence:aaa"), _zeile(id=2, doc_path="evidence:bbb")]
    assert len(_zusammenfuehren(zwei)) == 2


def test_ohne_dateikennung_faellt_nur_die_exakte_wiederholung_weg() -> None:
    """Über Quellen hinweg wird **nicht** nach Namen zusammengeführt —
    gleiche Namen sind ein Indiz, keine Identität (#1824)."""
    from shared.nachweis_items import _zusammenfuehren
    zeilen = [_zeile(id=1), _zeile(id=2), _zeile(id=3, doc_type="pentest")]
    raus = _zusammenfuehren(zeilen)
    assert len(raus) == 2, "gleicher Name + gleicher Typ ist eine Wiederholung"


# ── Was im Block steht ───────────────────────────────────────────────────────

def test_text_nennt_titel_art_und_baustein() -> None:
    from shared.nachweis_items import _text
    t = _text(_zeile(), "IMPL-01")
    assert "IMPL-01" in t
    assert "Governance" in t
    assert "resource" in t
    assert "design" in t


def test_text_gibt_den_titel_nicht_als_erfuellung_aus() -> None:
    """Der Vorsatz „verknüpfter Nachweis" ist der Kern dieser Umsetzung.

    Ohne ihn rechnet ein Modell einen Dateinamen als Erfüllung an — und das
    wäre schlimmer als die Lücke, die hier behoben wird.
    """
    from shared.nachweis_items import _text
    t = _text(_zeile(), "IMPL-01")
    assert t.startswith("verknüpfter Nachweis"), t[:60]
    assert "erfüllt" not in t.lower()


def test_datei_ohne_erschlossenen_text_wird_benannt(monkeypatch) -> None:
    """„Text nicht erschlossen" ist eine ehrliche Aussage über die Akte —
    ein Scan ohne Texterkennung ist kein Fehler der Anwendung (#1861)."""
    import shared.nachweis_items as ni
    monkeypatch.setattr(ni, "_volltext", lambda _k: "", raising=True)
    t = ni._text(_zeile(doc_path="evidence:xyz"), "IMPL-01")
    assert "nicht erschlossen" in t


# ── der Provider gibt sie wirklich heraus ────────────────────────────────────

def test_cra_provider_rechnet_verknuepfte_nachweise_an(monkeypatch) -> None:
    import cra.traceability_db as tdb
    from cra import evidence_provider as ep

    monkeypatch.setattr(tdb, "list_dokumente",
                        lambda *a, **k: [_zeile(), _zeile(id=9, anforderung_id="AI1-01")],
                        raising=True)
    # Die übrigen Quellen stumm schalten — geprüft wird dieser Weg.
    for fn in ("_vuln_items", "_sbom_items", "_threat_items", "_linked_risk_items"):
        monkeypatch.setattr(ep, fn, lambda *a, **k: [], raising=True)
    monkeypatch.setattr("shared.nachweis_items.managed_doc_items",
                        lambda *a, **k: [], raising=True)

    items = ep.relevant_for({"name": "AI Compliance Suite"},
                            {"id": "IMPL-01", "kapitel": "IMPL"})
    refs = [i.ref for i in items]
    assert refs == ["cra_dokumente:1"], (
        "Der Nachweis zu IMPL-01 muss herauskommen, der zu AI1-01 nicht. "
        f"Erhalten: {refs}"
    )
    assert "Governance" in items[0].text


def test_anforderung_ohne_nachweis_bleibt_leer(monkeypatch) -> None:
    import cra.traceability_db as tdb
    from shared.nachweis_items import cra_dokument_items
    monkeypatch.setattr(tdb, "list_dokumente", lambda *a, **k: [_zeile()], raising=True)
    assert cra_dokument_items("P", "ART13-09", _CRA_DB) == []


def test_alle_sechs_provider_sind_verdrahtet() -> None:
    """Die Falle aus Punkt 3 des Issues: eine Lösung nur für CRA wäre die
    nächste Spiegel-Liste (#1731/#1735)."""
    import re
    wurzel = Path(__file__).resolve().parents[1]
    for datei in ("cra", "nis2", "ai_act", "dsgvo", "wiba"):
        p = wurzel / datei / "evidence_provider.py"
        quelle = re.sub(r"#.*", "", p.read_text(encoding="utf-8"))
        assert "managed_doc_items" in quelle or "cra_dokument_items" in quelle, (
            f"{datei}/evidence_provider.py rechnet verknüpfte Dokumente nicht an"
        )


def test_kein_abruf_der_adresse() -> None:
    """Die Trennlinie aus #1761 verschiebt sich nicht.

    Ein ``doc_path``, der mit ``http`` beginnt, ist eine Eingabe des Anwenders.
    Ihn serverseitig zu holen wäre die SSRF-Lücke, die dort ausdrücklich
    ausgeschlossen wurde.
    """
    import re
    quelle = (Path(__file__).resolve().parents[1] / "shared" / "nachweis_items.py") \
        .read_text(encoding="utf-8")
    ohne = re.sub(r'""".*?"""', "", quelle, flags=re.S)
    ohne = re.sub(r"#.*", "", ohne)
    for verboten in ("requests.get", "urlopen", "httpx."):
        assert verboten not in ohne, f"{verboten} hat hier nichts zu suchen"


def test_nur_freigegebene_managed_docs_zaehlen(monkeypatch) -> None:
    """Ein Entwurf ist kein Nachweis — ihn als einen auszugeben wäre die
    Falschaussage, die #1765 beim KI-Entwurf verhindert."""
    import shared.documents.db as sdb
    from shared.nachweis_items import managed_doc_items
    monkeypatch.setattr(sdb, "list_documents", lambda *a, **k: [
        {"titel": "Entwurf", "status": "entwurf"},
        {"titel": "Fertig", "status": "freigegeben"},
    ], raising=True)
    items = managed_doc_items("nis2", "P", "N1", Path("data/db/nis2.sqlite"))
    assert len(items) == 1
    assert "Fertig" in items[0].text
    assert "Entwurf" not in items[0].text
