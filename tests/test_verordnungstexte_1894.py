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

def test_jeder_eintrag_steht_auch_im_download_dialog():
    """CELEX und Verzeichnis sind **dieselben** wie im Gutachten-Dialog.

    Eine zweite Ablage für denselben Text wäre eine zweite Wahrheit darüber,
    welche Fassung gilt — und ein zweiter CELEX wäre ein anderer Rechtsakt.
    """
    dialog = (REPO / "gutachten/_download_dialog.py").read_text(encoding="utf-8")
    gui = (REPO / "gutachten/gui_module.py").read_text(encoding="utf-8")
    for v in vo.VERORDNUNGEN:
        assert v.celex in dialog, f"{v.schluessel}: CELEX nicht im Dialog"
        assert str(v.verzeichnis) in dialog + gui, \
            f"{v.schluessel}: Verzeichnis {v.verzeichnis} nicht im Dialog"


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
