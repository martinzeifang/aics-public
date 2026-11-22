"""Die amtlichen Verordnungstexte sind aus der Webanwendung erreichbar (#1894).

DER BEFUND
----------
Mehrere Module zitieren Fundstellen, die in unterschriebene Dokumente gedruckt
werden — Anhang V der CRA, Anhang V der KI-VO, Artikel der DSGVO. Beide
Erklärungs-Module sagen: Maßgeblich ist das Amtsblatt.

**Nur ließ sich der Text nicht beschaffen.** Herunterladen konnte ihn
ausschließlich der Tkinter-Dialog des Gutachten-Moduls — eine
Desktop-Oberfläche, die der Administrator einer gehosteten Installation nicht
hat. Die Fähigkeit war da und nicht bedienbar: dieselbe Form wie die SBOM, die
sich holen aber nicht herunterladen ließ (#1823), und wie das Handbuch, das
nicht im Image lag (#1878).

Dazu eine **Richtigstellung**: Ich hatte behauptet, „für die KI-VO fehlt das
Gegenstück zum CRA-Text". Das war falsch — der Dialog holt CELEX ``32024R1689``
seit jeher nach ``data/ai_act_resources``. Fehlte nur der Weg ohne Tkinter.
"""
from __future__ import annotations

import io
import tokenize
from pathlib import Path

import pytest

from shared import verordnungen as vo

REPO = Path(__file__).resolve().parents[1]
FRONTEND = REPO / "frontend/src"


def _ohne_kommentare(text: str) -> str:
    behalten = [t for t in tokenize.generate_tokens(io.StringIO(text).readline)
                if t.type != tokenize.COMMENT]
    try:
        return tokenize.untokenize(behalten)
    except Exception:  # noqa: BLE001
        return text


# ── Die Positivliste stimmt mit dem vorhandenen Weg überein ────────────────

#: CELEX-Nummer und Ablage je Rechtsakt — **festgenagelt**.
#:
#: Bis #1955 verglich dieser Test die Liste gegen
#: ``gutachten/_download_dialog.py``: Der Tkinter-Dialog war der erprobte Weg,
#: und die Web-Liste musste zu ihm passen. Mit dem Desktop-Rückbau ist der
#: Dialog entfernt — die Gegenprobe wäre damit **gegenstandslos**, und ein Test,
#: der eine gelöschte Datei liest, ist kein Wächter, sondern ein Fehlschlag.
#:
#: Ersatzlos streichen durfte er nicht: Was er geprüft hat, sind **Fundstellen,
#: die in unterschriebene Dokumente gedruckt werden** (Anhang V der CRA, Anhang
#: V der KI-VO). Ein falscher CELEX ist dort ein anderer Rechtsakt, und eine
#: erfundene Nummer ist schlimmer als keine Angabe (#1763/#1792). Die Werte
#: stehen deshalb jetzt hier und wurden am 05.11.2026 gegen die vorherige
#: Fassung der Positivliste übernommen, nicht neu geraten.
#:
#: Seit #2061 stehen auch die **nationalen** Gesetze darin. Sie tragen keine
#: CELEX-Nummer (EUR-Lex kennt sie nicht), deshalb ist der erste Wert leer und
#: die Kennung ist der kanonische Dateiname. Festgenagelt ist auch hier beides:
#: Ein anderer Dateiname heißt, dass ein von Hand abgelegter Text nicht mehr
#: gefunden wird, und ein anderes Verzeichnis wäre eine zweite Ablage.
ERWARTET: dict[str, tuple[str, str]] = {
    "cra":   ("32024R2847", "data/cra_resources"),
    "ki-vo": ("32024R1689", "data/ai_act_resources"),
    "dsgvo": ("32016R0679", "data/dsgvo_resources"),
    "nis2":  ("32022L2555", "data/nis2_resources"),
    "zpo":   ("", "data/de_resources"),
    "bdsg":  ("", "data/de_resources"),
    "ao":    ("", "data/de_resources"),
    "hgb":   ("", "data/de_resources"),
    "enwg":  ("", "data/de_resources"),
    "bsig":  ("", "data/nis2_resources"),
}

#: Quelle und Dateiname der nationalen Gesetze — am 09.11.2026 einzeln gegen
#: die Gegenstelle geprüft (HTTP 200, ``application/pdf``), nicht aus dem
#: Muster abgeleitet. Die Verzeichnisnamen dort folgen keiner Regel
#: (``ao_1977``, ``bdsg_2018``, ``enwg_2005``, ``hgb``), und eine geratene
#: URL wäre ein Knopf, der nichts holt.
ERWARTET_NATIONAL: dict[str, tuple[str, str]] = {
    "zpo":  ("https://www.gesetze-im-internet.de/zpo/ZPO.pdf", "DE_ZPO.pdf"),
    "bdsg": ("https://www.gesetze-im-internet.de/bdsg_2018/BDSG.pdf",
             "DE_BDSG.pdf"),
    "ao":   ("https://www.gesetze-im-internet.de/ao_1977/AO.pdf", "DE_AO.pdf"),
    "hgb":  ("https://www.gesetze-im-internet.de/hgb/HGB.pdf", "DE_HGB.pdf"),
    "enwg": ("https://www.gesetze-im-internet.de/enwg_2005/EnWG.pdf",
             "DE_EnWG.pdf"),
    # Derselbe Dateiname wie in ``gutachten/file_download`` (dort
    # ``DE_BSIG_2025.pdf`` im NIS2-Verzeichnis) — zwei Ablagen für dasselbe
    # Gesetz wären zwei Wahrheiten darüber, welche Fassung gilt.
    "bsig": ("https://www.gesetze-im-internet.de/bsig_2025/BSIG.pdf",
             "DE_BSIG_2025.pdf"),
}


def test_celex_und_ablage_stehen_fest():
    """CELEX und Verzeichnis dürfen sich nicht unbemerkt ändern.

    Eine zweite Ablage für denselben Text wäre eine zweite Wahrheit darüber,
    welche Fassung gilt — und ein zweiter CELEX wäre ein anderer Rechtsakt.
    """
    assert {v.schluessel for v in vo.VERORDNUNGEN} == set(ERWARTET), \
        "Die Positivliste hat sich geändert — bitte die Fundstellen prüfen."
    for v in vo.VERORDNUNGEN:
        celex, verzeichnis = ERWARTET[v.schluessel]
        assert v.celex == celex, f"{v.schluessel}: CELEX {v.celex} != {celex}"
        assert str(v.verzeichnis) == verzeichnis, \
            f"{v.schluessel}: Ablage {v.verzeichnis} != {verzeichnis}"


def test_die_module_erwarten_dieselbe_ablage():
    """Die Erklärungs-Module schlagen den Text dort nach, wo er abgelegt wird.

    Das ist die Gegenprobe, die nach dem Desktop-Rückbau (#1955) an die Stelle
    des Dialog-Vergleichs tritt — und die bessere: Sie hält die Ablage gegen
    den **Verbraucher** der Datei statt gegen einen zweiten Beschaffungsweg.
    """
    from ai_act import doc_export as aiact_de

    ki_vo = vo.nach_schluessel("ki-vo")
    assert ki_vo is not None
    assert str(aiact_de.VERORDNUNG_VERZEICHNIS) == str(ki_vo.verzeichnis)
    assert aiact_de.VERORDNUNG_CELEX == ki_vo.celex


def test_die_liste_ist_abschliessend():
    """Ein Endpunkt, der eine beliebige Kennung annimmt, spricht am Ende mit
    einem beliebigen Host (die Linie aus #1761/#1770)."""
    assert vo.nach_schluessel("gibt-es-nicht") is None
    with pytest.raises(vo.DownloadFehlgeschlagen, match="Unbekannter Rechtsakt"):
        vo.hole("http://beliebig.example/x.pdf")


def test_jeder_eintrag_sagt_wo_er_zitiert_wird():
    """Ohne das steht in der Oberfläche eine Liste von Rechtsakten, und
    niemand weiß, warum dieser Text gebraucht wird."""
    for v in vo.VERORDNUNGEN:
        assert v.zitiert_in, v.schluessel


def test_die_beiden_erklaerungs_module_sind_dabei():
    schluessel = {v.schluessel for v in vo.VERORDNUNGEN}
    assert {"cra", "ki-vo"} <= schluessel


# ── „Liegt vor" ist eine Aussage, keine Vermutung ──────────────────────────

def test_eine_datei_ohne_celex_im_namen_zaehlt_nicht(tmp_path):
    """Sie könnte alles sein, und „liegt vor" wäre dann eine Behauptung."""
    (tmp_path / "irgendwas.pdf").write_bytes(b"%PDF-1.7\n")
    assert vo._dateien(tmp_path, "32024R1689") == []


def test_eine_waf_antwort_zaehlt_nicht_als_amtliche_fassung(tmp_path):
    """**Der Grund für die Magic-Bytes-Prüfung.** Die direkten PDF-Links auf
    eur-lex stehen hinter einer AWS-WAF-Prüfung und liefern HTML mit Status
    202. Eine so entstandene Datei mit ``.pdf``-Endung hätte als amtliche
    Fassung gezählt — genau der Fehler, den der Downloader umgeht.
    """
    (tmp_path / "32024R1689_DEU.pdf").write_bytes(b"<html>Access denied</html>")
    dateien = vo._dateien(tmp_path, "32024R1689")
    assert dateien and not dateien[0]["ist_pdf"]


def test_ein_pdf_mit_celex_zaehlt(tmp_path):
    (tmp_path / "32024R1689_DEU.pdf").write_bytes(b"%PDF-1.7\n" + b"x" * 100)
    dateien = vo._dateien(tmp_path, "32024R1689")
    assert dateien and dateien[0]["ist_pdf"] and dateien[0]["sha256"]


def test_der_status_unterscheidet_fehlt_und_fragment(monkeypatch, tmp_path):
    leer, kaputt = tmp_path / "leer", tmp_path / "kaputt"
    leer.mkdir()
    kaputt.mkdir()
    (kaputt / "32024R1689_DEU.pdf").write_bytes(b"<html>")
    monkeypatch.setattr(vo, "VERORDNUNGEN", (
        vo.Verordnung("a", "32024R1689", "A", leer, "x"),
        vo.Verordnung("b", "32024R1689", "B", kaputt, "x"),
    ))
    monkeypatch.setattr(vo, "_NACH_SCHLUESSEL",
                        {v.schluessel: v for v in vo.VERORDNUNGEN})
    a, b = vo.status()
    assert not a["vorhanden"] and not a["nur_fragment"]
    assert not b["vorhanden"] and b["nur_fragment"]


# ── Kein eigener Transport ─────────────────────────────────────────────────

def test_kein_eigener_download_weg():
    """Die WAF-Umgehung über die Publikationsstelle steht in
    ``gutachten/file_download``. Sie zweimal zu bauen hieße, sie zweimal zu
    pflegen — und der erste Anlauf scheiterte genau an der WAF."""
    programm = _ohne_kommentare(
        (REPO / "shared/verordnungen.py").read_text(encoding="utf-8"))
    for verboten in ("requests.get", "urlopen", "httpx", "curl"):
        assert verboten not in programm
    assert "gutachten.file_download" in programm


def test_ein_fehlschlag_nennt_den_weg_von_hand(monkeypatch):
    """Der häufigste Fehlschlag ist kein Defekt — kein Netz, oder die
    Gegenstelle antwortet nicht. Dann liegt die Lösung beim Menschen, und
    dafür muss er wissen, woran es lag und wohin die Datei gehört."""
    monkeypatch.setattr(vo, "status", lambda nur="": [
        {**vo.nach_schluessel("ki-vo").as_dict(), "dateien": [],
         "vorhanden": False, "nur_fragment": False}])

    def kaputt(*a, **k):
        raise RuntimeError("Netz weg")

    import gutachten.file_download as fd
    monkeypatch.setattr(fd, "build_requests_session", kaputt)
    with pytest.raises(vo.DownloadFehlgeschlagen) as exc:
        vo.hole("ki-vo")
    text = str(exc.value)
    assert "32024R1689" in text and "data/ai_act_resources" in text


def test_ein_vorhandener_text_wird_nicht_erneut_geholt(monkeypatch):
    """Eine amtliche Fassung ändert sich nicht; ein unnötiger Abruf belastet
    die Gegenstelle."""
    monkeypatch.setattr(vo, "status", lambda nur="": [
        {**vo.nach_schluessel("cra").as_dict(), "dateien": [],
         "vorhanden": True, "nur_fragment": False}])
    erg = vo.hole("cra")
    assert erg["geholt"] is False and erg["hinweis"]


# ── Aus der Webanwendung bedienbar ─────────────────────────────────────────

def test_die_admin_endpunkte_existieren():
    api = (REPO / "server/api/admin.py").read_text(encoding="utf-8")
    assert "@admin_bp.get('/verordnungen')" in api
    assert "@admin_bp.post('/verordnungen/<schluessel>')" in api
    # Verwaltungsrecht, und der Abruf steht im Revisionspfad (#1784).
    block = api.split("def verordnungen_holen", 1)[1][:1800]
    assert "_audit_admin" in block
    assert "admin:config" in api.split("@admin_bp.post('/verordnungen", 1)[1][:200]


def test_die_admin_kachel_existiert():
    """Der Grund für das Issue: Ohne Oberfläche war die Fähigkeit nicht
    bedienbar."""
    view = (FRONTEND / "views/admin/AdminSettingsView.vue").read_text(
        encoding="utf-8")
    assert "verordnungen" in view
    assert "Verordnungstexte" in view
    assert "/api/admin/verordnungen" in view


def test_die_erklaerungsmaske_sagt_ob_der_text_vorliegt():
    """Wer eine Fundstelle prüfen will, soll sehen, ob das Original zur Hand
    ist — nicht erst suchen."""
    api = (REPO / "server/api/aiact_conformity.py").read_text(encoding="utf-8")
    assert "verordnung_liegt_vor" in api
    form = (FRONTEND / "components/aiact/KonformitaetserklaerungForm.vue").read_text(
        encoding="utf-8")
    assert "verordnungLiegtVor" in form
    assert "2024/1689" in form


def test_liegt_vor_ist_kurz_und_ohne_dateiinhalte():
    """Die Module brauchen ja/nein, nicht Prüfsummen — und eine Antwort, die
    Dateilisten mitschickt, lädt zum Mitprotokollieren ein."""
    assert vo.liegt_vor("ki-vo") in (True, False)
    assert vo.liegt_vor("gibt-es-nicht") is False


# ── Die deutschen Gesetze sind beschaffbar (#2061) ─────────────────────────
#
# Der Befund: Die Suite zitiert § 406/§ 407a ZPO in **jedem**
# Gerichtsgutachten, § 38 BDSG in der DSB-Pflichtprüfung, § 147 AO und
# § 257 HGB in den Aufbewahrungsfristen des Löschkonzepts, § 11 EnWG im
# NIS2-Assistenten und das BSIG als nationale Umsetzung der NIS-2-Richtlinie —
# und keiner dieser Texte ließ sich beschaffen. Die Positivliste kannte nur
# EUR-Lex, und ein nationales Gesetz hat dort keine CELEX-Nummer.
#
# Dieselbe Form wie der Befund, der #1894 ausgelöst hat: Die Module sagen
# „maßgeblich ist der Gesetzestext", und der Administrator hatte keinen Weg
# dorthin.


def test_die_zitierten_deutschen_gesetze_stehen_in_der_liste():
    """Was die Anwendung zitiert, muss sie auch beschaffen können.

    Nicht mehr: Die Liste ist eine Positivliste, und ein Eintrag für ein
    Gesetz, das nirgends zitiert wird, wäre ein Knopf ohne Zweck.
    """
    schluessel = {v.schluessel for v in vo.VERORDNUNGEN}
    assert set(ERWARTET_NATIONAL) <= schluessel


def test_quelle_und_dateiname_der_gesetze_stehen_fest():
    """Eine geratene URL ist ein Knopf, der nichts holt.

    Die Verzeichnisnamen auf gesetze-im-internet.de folgen keiner Regel
    (``ao_1977``, ``bdsg_2018``, ``enwg_2005``, ``hgb``) — sie wurden einzeln
    gegen die Gegenstelle geprüft, und dieser Test hält sie fest.
    """
    nach = {v.schluessel: v for v in vo.VERORDNUNGEN}
    for schluessel, (quelle, dateiname) in ERWARTET_NATIONAL.items():
        v = nach[schluessel]
        assert v.quelle == quelle, schluessel
        assert v.dateiname == dateiname, schluessel
        assert v.celex == "", f"{schluessel}: EUR-Lex kennt dieses Gesetz nicht"
        assert v.kennung == dateiname, schluessel


def test_ein_eu_rechtsakt_hat_keine_direkte_quelle():
    """Der CELEX-Weg bleibt der CELEX-Weg.

    Eine direkte PDF-Adresse auf eur-lex.europa.eu steht hinter einer
    WAF-Prüfung und liefert HTTP 202 mit HTML — genau der Fehler, den der
    Umweg über die Publikationsstelle vermeidet. Ein ``quelle``-Eintrag an
    einem EU-Rechtsakt würde ihn zurückholen.
    """
    for v in vo.VERORDNUNGEN:
        if v.celex:
            assert not v.quelle, f"{v.schluessel}: CELEX-Weg plus direkte URL"


def test_der_dateiname_wird_exakt_verglichen(tmp_path):
    """Der Teilvergleich zählt einen Anhang am Namen mit.

    Beim CELEX genügt ``in``, weil ``32024R2847`` nicht zufällig vorkommt.
    Beim Dateinamen nicht: ``DE_AO.pdf.part`` — der Rest eines abgebrochenen
    Abrufs — enthält ``DE_AO.pdf`` als Teilzeichenkette, fängt mit ``%PDF-``
    an und hätte als amtliche Fassung gezählt. Genau der Zustand, den diese
    Datei sonst auseinanderhält: „da, aber keine amtliche Fassung".

    **Der erste Testwert hier war ``DE_KAKAO_Richtlinie.pdf`` und löste die
    Unterscheidung nicht aus** — der Teilvergleich wäre darauf ebenfalls
    leer geblieben, und die Gegenprobe (exakten Vergleich zurückbauen) blieb
    grün. Die Lehre aus #1999 wörtlich: Ein Testwert, der die geprüfte
    Unterscheidung nicht auslöst, macht den Test zur Behauptung.
    """
    (tmp_path / "DE_AO.pdf.part").write_bytes(b"%PDF-1.7 abgebrochen")
    assert vo._dateien(tmp_path, "DE_AO.pdf", exakt=True) == []
    # Gegenrichtung: ohne ``exakt`` zählt der Rest mit — das ist der Defekt.
    assert vo._dateien(tmp_path, "DE_AO.pdf") != []
    (tmp_path / "DE_AO.pdf").write_bytes(b"%PDF-1.7 x")
    gefunden = vo._dateien(tmp_path, "DE_AO.pdf", exakt=True)
    assert [d["name"] for d in gefunden] == ["DE_AO.pdf"]


def test_ein_gesetz_ohne_pdf_gilt_nicht_als_vorhanden(monkeypatch, tmp_path):
    """Dieselbe Regel wie bei den EU-Texten: „Datei da, aber kein PDF" ist
    ein eigener Zustand und nicht „liegt vor"."""
    (tmp_path / "DE_ZPO.pdf").write_bytes(b"<html>Access denied</html>")
    monkeypatch.setattr(vo, "VERORDNUNGEN", (
        vo.Verordnung("zpo", "", "ZPO", tmp_path, "test",
                      quelle="https://example.invalid/ZPO.pdf",
                      dateiname="DE_ZPO.pdf"),
    ))
    monkeypatch.setattr(vo, "_NACH_SCHLUESSEL",
                        {v.schluessel: v for v in vo.VERORDNUNGEN})
    eintrag = vo.status("zpo")[0]
    assert eintrag["vorhanden"] is False
    assert eintrag["nur_fragment"] is True


def test_der_fehlschlag_nennt_den_dateinamen(monkeypatch, tmp_path):
    """Ohne CELEX muss die Meldung den **Dateinamen** nennen.

    Sonst legt der Administrator ``ZPO.pdf`` ab und die Anwendung findet ihn
    nicht — ein Fehlschlag, der aussieht wie ein Defekt.
    """
    monkeypatch.setattr(vo, "VERORDNUNGEN", (
        vo.Verordnung("zpo", "", "Zivilprozessordnung (ZPO)", tmp_path, "test",
                      quelle="https://example.invalid/ZPO.pdf",
                      dateiname="DE_ZPO.pdf"),
    ))
    monkeypatch.setattr(vo, "_NACH_SCHLUESSEL",
                        {v.schluessel: v for v in vo.VERORDNUNGEN})
    import gutachten.file_download as fd

    def _scheitert(*a, **k):
        raise RuntimeError("kein Netz")

    monkeypatch.setattr(fd, "download_extra_resource", _scheitert)
    with pytest.raises(vo.DownloadFehlgeschlagen) as exc:
        vo.hole("zpo")
    assert "DE_ZPO.pdf" in str(exc.value)
    assert str(tmp_path) in str(exc.value)


def test_das_bsig_liegt_bei_den_nis2_texten():
    """Eine zweite Ablage für dasselbe Gesetz wäre eine zweite Wahrheit.

    ``gutachten/file_download`` holt das BSIG seit Langem als
    ``DE_BSIG_2025.pdf`` in das NIS2-Verzeichnis. Würde dieser Weg es woanders
    oder anders benannt ablegen, stünde dasselbe Gesetz zweimal in der
    Installation — und die Oberfläche würde für den einen Ort „fehlt" melden,
    während der Text im anderen liegt.
    """
    bsig = vo.nach_schluessel("bsig")
    assert bsig is not None
    assert bsig.verzeichnis == Path("data/nis2_resources")
    quelle = (REPO / "gutachten/file_download.py").read_text(encoding="utf-8")
    assert bsig.dateiname in quelle
    assert bsig.quelle in quelle
