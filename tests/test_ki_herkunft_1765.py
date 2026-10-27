"""KI-Kennzeichnung gehört in die Anwendung, nicht in das Dokument (#1765).

Aus der Rückmeldung des Anwenders: „Der Report beim Compliance-Bericht hat noch
den Hinweis, dass KI-generiert. Das muss aus dem Dokument raus. Die Überprüfung
muss vorher in der Anwendung erfolgen."

Die Kennzeichnungspflicht (#1551/#1552) bleibt richtig — sie gilt gegenüber
denen, die mit dem System arbeiten, nicht gegenüber dem Empfänger eines
Konformitätsdokuments. Und „fachlich zu prüfen" in einem freigegebenen
Dokument nimmt diesem seine Aussage: Entweder die Bewertung steht, dann gehört
der Vorbehalt nicht hinein — oder sie steht nicht, dann gehört sie nicht in
ein freigegebenes Dokument.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
MODUL = "cra"
PROJ = "pytest-ki-1765"

ALT = ("Die Anforderung ist durch die Protokollierung erfüllt.\n\n"
       "— 🤖 KI-generiert (ollama, 2026-10-22) — fachlich zu prüfen.")


# ── Der Text bleibt sauber ──────────────────────────────────────────────────
def test_marker_wird_nicht_mehr_in_den_text_geschrieben():
    from server.services.auto_bewertung import ki_kennzeichnung

    text = ki_kennzeichnung("Die Anforderung ist erfüllt.", "ollama")
    assert "KI-generiert" not in text
    assert text == "Die Anforderung ist erfüllt."


def test_bestandstext_wird_bereinigt():
    """In vorhandenen Bewertungen steht der Marker. Ihn beim Drucken stehen zu
    lassen hieße, den Fehler weiter auszuliefern."""
    from shared.ki_herkunft import ohne_marker

    assert ohne_marker(ALT) == "Die Anforderung ist durch die Protokollierung erfüllt."
    assert ohne_marker("") == ""
    assert ohne_marker("ganz ohne Marker") == "ganz ohne Marker"
    # Auch wenn nur der Hinweis dasteht, bleibt nichts übrig.
    assert ohne_marker("— 🤖 KI-generiert (cloud, 2026-01-01) — fachlich zu prüfen.") == ""


def test_jeder_berichts_renderer_bereinigt():
    """Sechs Renderer drucken Bewertungstexte. Einer, der es vergisst, liefert
    den Hinweis weiter — und zwar genau dorthin, wo er am meisten schadet."""
    renderer = ("cra/report_export.py", "nis2/report_export.py",
                "dsgvo/report_export.py", "ai_act/report_export.py",
                "risikobewertung/report_export.py", "risikobewertung/risk_export.py")
    fehlend = [r for r in renderer
               if "_ohne_ki_marker" not in (REPO / r).read_text()]
    assert not fehlend, f"ohne Bereinigung: {fehlend}"


def test_oberflaeche_behaelt_ihre_hinweise():
    """Was in der Anwendung steht, bleibt: Dort sagt der Hinweis dem
    Bearbeiter, woher der Vorschlag kommt."""
    panel = (REPO / "frontend/src/components/shared/RequirementActions.vue").read_text()
    assert "KI-generiert" in panel


# ── Das Register ────────────────────────────────────────────────────────────
@pytest.fixture
def register(tmp_path):
    return tmp_path / "ki_herkunft.sqlite"


def test_ohne_eintrag_gilt_als_nicht_ki(register):
    from shared import ki_herkunft as kh

    s = kh.status(MODUL, PROJ, "requirement", "CRA-A-01", db_path=register)
    assert s["ki"] is False and s["geprueft"] is True


def test_vermerken_und_pruefen(register):
    from shared import ki_herkunft as kh

    kh.vermerken(MODUL, PROJ, "requirement", "CRA-A-01", provider="ollama",
                 db_path=register)
    s = kh.status(MODUL, PROJ, "requirement", "CRA-A-01", db_path=register)
    assert s["ki"] is True and s["geprueft"] is False and s["provider"] == "ollama"

    s = kh.pruefen(MODUL, PROJ, "requirement", "CRA-A-01",
                   von="pruefer@example.com", db_path=register)
    assert s["geprueft"] is True and s["geprueft_von"] == "pruefer@example.com"
    assert s["geprueft_am"]


def test_pruefung_ohne_person_wird_abgewiesen(register):
    """Eine Prüfung ohne Prüfer ist keine."""
    from shared import ki_herkunft as kh

    kh.vermerken(MODUL, PROJ, "requirement", "CRA-A-02", db_path=register)
    with pytest.raises(ValueError, match="Person"):
        kh.pruefen(MODUL, PROJ, "requirement", "CRA-A-02", von="  ", db_path=register)


def test_neue_erzeugung_hebt_die_pruefung_auf(register):
    """Der gefährlichste Fall: Wird die Bewertung neu erzeugt, ist die alte
    Prüfung erledigt — geprüft wurde ein anderer Text. Bliebe sie stehen,
    wiese ein Dokument einen ungeprüften Inhalt als geprüft aus."""
    from shared import ki_herkunft as kh

    kh.vermerken(MODUL, PROJ, "requirement", "CRA-A-03", provider="ollama",
                 db_path=register)
    kh.pruefen(MODUL, PROJ, "requirement", "CRA-A-03", von="p@example.com",
               db_path=register)
    kh.vermerken(MODUL, PROJ, "requirement", "CRA-A-03", provider="cloud",
                 db_path=register)

    s = kh.status(MODUL, PROJ, "requirement", "CRA-A-03", db_path=register)
    assert s["geprueft"] is False, "die alte Prüfung gilt weiter"
    assert s["geprueft_von"] == ""


def test_sammelabruf_statt_einzelabfragen(register):
    """32 CRA-Anforderungen sollen nicht 32 Abfragen kosten."""
    from shared import ki_herkunft as kh

    for i in range(5):
        kh.vermerken(MODUL, PROJ, "requirement", f"CRA-B-{i:02d}", db_path=register)
    alle = kh.fuer_projekt(MODUL, PROJ, "requirement", db_path=register)
    assert len(alle) == 5 and all(v["ki"] for v in alle.values())


def test_druckbar_nur_nach_pruefung(register):
    from shared import ki_herkunft as kh

    kh.vermerken(MODUL, PROJ, "requirement", "CRA-C-01", db_path=register)
    assert kh.ist_druckbar(MODUL, PROJ, "requirement", "CRA-C-01", db_path=register) is False
    kh.pruefen(MODUL, PROJ, "requirement", "CRA-C-01", von="p@example.com",
               db_path=register)
    assert kh.ist_druckbar(MODUL, PROJ, "requirement", "CRA-C-01", db_path=register) is True


def test_bestandstext_mit_marker_gilt_als_ungeprueft(register):
    """Ohne Registereintrag, aber mit altem Marker: Der Text sagt selbst, dass
    er zu prüfen ist."""
    from shared import ki_herkunft as kh

    assert kh.ist_druckbar(MODUL, PROJ, "requirement", "CRA-D-01", ALT,
                           db_path=register) is False
    assert kh.ist_druckbar(MODUL, PROJ, "requirement", "CRA-D-01", "sauber",
                           db_path=register) is True


# ── Zweite Hälfte: Prüfung in der Anwendung (#1765) ─────────────────────────
#
# Ohne sie wäre die Änderung eine Verschlechterung: Der Vorbehalt wäre aus den
# Dokumenten verschwunden, ohne dass irgendwo ein Mensch die Bewertung
# bestätigt hätte. Diese Tests halten den Gegenpart fest.

PROJ2 = "pytest-ki-1765-ui"


def _frisch(art: str = "requirement", oid: str = "CRA-01"):
    """Register für einen Testfall zurücksetzen."""
    from shared import ki_herkunft as kh

    kh.vermerken(MODUL, PROJ2, art, oid, provider="ollama")
    return kh


def test_bericht_text_weist_ungepruefte_entwuerfe_aus():
    """Der interne Bericht ist der Ort, an dem der Vorbehalt hingehört.

    Entscheidend ist der Unterschied zur alten Lösung: Die Kennzeichnung ist
    eine Entscheidung **beim Drucken**. Deshalb kann sie hier stehen und im
    Konformitätsdokument fehlen — vorher ging das nicht, weil sie im
    gespeicherten Text klebte.
    """
    from shared.ki_herkunft import ENTWURF_VORSATZ, bericht_text

    ungeprueft = {"ki": True, "geprueft": False}
    geprueft = {"ki": True, "geprueft": True}

    assert bericht_text("Erfüllt.", ungeprueft) == ENTWURF_VORSATZ + "Erfüllt."
    # Geprüft → der Text steht für sich, ohne jeden Zusatz.
    assert bericht_text("Erfüllt.", geprueft) == "Erfüllt."
    # Kein Eintrag = nicht KI-erzeugt.
    assert bericht_text("Erfüllt.", None) == "Erfüllt."
    # Leerer Text bleibt leer — kein Vorsatz ohne Inhalt.
    assert bericht_text("", ungeprueft) == ""
    # Und der alte Inline-Marker wird auf jedem Weg entfernt.
    assert "KI-generiert" not in bericht_text(ALT, ungeprueft)


def test_pruefung_ueber_die_rest_schnittstelle(client, auth_token):
    """Die Schaltfläche „Fachlich geprüft" braucht einen Endpunkt — und er muss
    die Person festhalten, die geprüft hat."""
    kh = _frisch()
    kopf = {"Authorization": f"Bearer {auth_token}"}

    r = client.get(f"/api/cra/projekte/{PROJ2}/ki-herkunft?art=requirement", headers=kopf)
    assert r.status_code == 200, r.data
    items = r.get_json()["items"]
    assert items["CRA-01"]["ki"] is True
    assert items["CRA-01"]["geprueft"] is False

    r = client.post(f"/api/cra/projekte/{PROJ2}/ki-herkunft/requirement/CRA-01/geprueft",
                    headers=kopf)
    assert r.status_code == 200, r.data
    st = r.get_json()["status"]
    assert st["geprueft"] is True
    # Ohne Person keine Prüfung — der Endpunkt nimmt den angemeldeten Benutzer.
    assert st["geprueft_von"]
    assert kh.status(MODUL, PROJ2, "requirement", "CRA-01")["geprueft"] is True


def test_pruefung_ohne_ki_eintrag_ist_404(client, auth_token):
    """Eine Prüfung zu quittieren, wo keine KI im Spiel war, wäre eine Aussage
    über etwas, das das Register nicht kennt."""
    kopf = {"Authorization": f"Bearer {auth_token}"}
    r = client.post(
        f"/api/cra/projekte/{PROJ2}/ki-herkunft/requirement/GIBT-ES-NICHT/geprueft",
        headers=kopf)
    assert r.status_code == 404


def test_unbekannte_objektart_wird_abgewiesen(client, auth_token):
    """Die Artenliste ist eng gehalten; sie beschreibt, wo es KI-Bewertungen
    gibt. Ein Tippfehler darf keinen stillen Eintrag anlegen."""
    kopf = {"Authorization": f"Bearer {auth_token}"}
    r = client.post(f"/api/cra/projekte/{PROJ2}/ki-herkunft/quatsch/CRA-01/geprueft",
                    headers=kopf)
    assert r.status_code == 400


def test_neue_erzeugung_hebt_die_pruefung_auf_auch_ueber_rest(client, auth_token):
    """Der gefährliche Fall: Nach einer neuen KI-Bewertung wäre der geprüfte
    Haken eine Aussage über einen Text, den niemand gesehen hat."""
    kh = _frisch(oid="CRA-02")
    kopf = {"Authorization": f"Bearer {auth_token}"}
    client.post(f"/api/cra/projekte/{PROJ2}/ki-herkunft/requirement/CRA-02/geprueft",
                headers=kopf)
    assert kh.status(MODUL, PROJ2, "requirement", "CRA-02")["geprueft"] is True

    kh.vermerken(MODUL, PROJ2, "requirement", "CRA-02", provider="cloud")
    assert kh.status(MODUL, PROJ2, "requirement", "CRA-02")["geprueft"] is False


def test_routen_haengen_an_allen_sechs_modulen(app):
    """Unter dem Modul-Prefix, damit Modul-Guard und Firmen-ACL greifen.

    Ein eigener Prefix (``/api/ki-herkunft/…``) wäre für den zentralen Guard
    kein Modul-Pfad gewesen — jeder angemeldete Nutzer hätte fremde Bewertungen
    als geprüft ausweisen können.
    """
    pfade = {str(r.rule) for r in app.url_map.iter_rules()}
    for prefix in ("cra", "nis2", "aiact", "dsgvo", "wiba", "risikobewertung"):
        assert f"/api/{prefix}/projekte/<projekt_name>/ki-herkunft" in pfade, prefix
        assert (f"/api/{prefix}/projekte/<projekt_name>/ki-herkunft/"
                f"<art>/<objekt_id>/geprueft") in pfade, prefix


def test_gate_meldet_ungepruefte_ki_bewertungen():
    """Eine EU-Konformitätserklärung ist die Aussage eines Herstellers, nicht
    die Ausgabe eines Modells. Das Gate macht den Unterschied sichtbar.

    Wirkung **bedingt**: Den Vorgang trägt die Freigabe durch einen Menschen
    (#1743); ein ungeprüfter Entwurf ist ein Mangel in der Nachweiskette, keine
    Eigenschaft des Produkts. Rot bleibt der Nicht-Konformität vorbehalten.
    """
    from cra.konformitaet_gate import _check_ki_pruefung
    from shared import ki_herkunft as kh

    proj = "pytest-ki-1765-gate"
    kh.vermerken("cra", proj, "requirement", "CRA-07", provider="ollama")
    befunde, punkte = {}, []
    _check_ki_pruefung(proj, "1.0.0", befunde, punkte)
    assert befunde["ki_ungeprueft"] == 1
    assert len(punkte) == 1
    assert punkte[0]["ampel_wirkung"] == "bedingt"
    assert "nicht geprüft" in punkte[0]["titel"]

    kh.pruefen("cra", proj, "requirement", "CRA-07", von="pruefer@example.com")
    befunde, punkte = {}, []
    _check_ki_pruefung(proj, "1.0.0", befunde, punkte)
    assert befunde["ki_ungeprueft"] == 0
    assert punkte == []


def test_pruefvermerk_nennt_die_person_nicht_die_id():
    """`get_jwt_identity()` liefert „user-001". In einem Prüfvermerk ist das
    wertlos: Das Feld beantwortet die Frage „wer hat das bestätigt?".

    Im Firefox-Durchlauf stand genau das in der Oberfläche — ein Fund, den der
    grüne Lauf nicht gemeldet hat, weil das Element ja da war.
    """
    from shared.ki_herkunft_api import _person

    assert _person("user-001") == "admin@example.com"
    # Unbekannte ID: lieber die ID als „unbekannt" — sie lässt sich nachschlagen.
    assert _person("user-gibt-es-nicht") == "user-gibt-es-nicht"
    assert _person("") == "unbekannt"
