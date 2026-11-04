"""Die Stapel-Anlage kommt aus **einer** Stelle (#1851).

DER BEFUND
„🐙 Issues anlegen" stand fünfmal einzeln da, rund 90 Zeilen je Modul — und
WiBA hatte es gar nicht, weil die Route fehlte. **Drei der fünf Fassungen
trugen denselben Defekt, den #1846 an der Einzelanlage beseitigt hat:**
``gl_create(..., body=body)`` gegen eine Signatur, die ``description=``
verlangt (CRA, NIS2, AI Act). Die Stapel-Anlage über GitLab endete dort in
einem ``TypeError`` → 500 und kann in diesen Modulen **nie** funktioniert
haben. Ein Defekt, der in einer Kopie behoben wird, bleibt in den anderen
vier — genau deshalb ist der Weg aus der Fabrik nicht Geschmackssache.

Dazu kamen vier Abweichungen, die niemand entschieden hatte: AI Act schickte
als einziges Modul ``provider: 'github'`` fest mit (und überstimmte damit ein
auf GitLab konfiguriertes Projekt), NIS2 fragte doppelt nach, DSGVO lieferte
Zahlen statt Einträge, und die Erfolgsmeldung gab es in fünf Wortlauten.

Geprüft wird über die Routen, ohne Netz: Das Anlegen wird an der Fabrik
abgefangen, denn Gegenstand dieses Tests ist die **Auswahl** der Objekte und
die Verknüpfung, nicht der HTTP-Aufruf zur Gegenstelle.
"""
from __future__ import annotations

import sqlite3

import pytest

from cra.db import delete_projekt, ensure_db, save_projekt
from server.api.cra import DB_PATH
from shared.issue_links import add_link, ensure_tables, list_project_links

PROJ = "pytest-stapel-1851"
BASE = "/api/cra"


@pytest.fixture(autouse=True)
def _volle_lizenz():
    from server import license_state
    cur = license_state._current
    vorher = (cur.state, list(cur.modules))
    cur.state, cur.modules = "ok", ["*"]
    yield
    cur.state, cur.modules = vorher


@pytest.fixture()
def projekt(client, auth_headers):
    ensure_db(DB_PATH)
    _links_weg()
    # Repo in der Projekt-Konfiguration — der Server löst es daraus auf.
    save_projekt(DB_PATH, name=PROJ, unternehmen="U", produkt="P",
                 meta={"vcs_publish": {"provider": "github", "repo": "o/r"}})
    yield PROJ
    _links_weg()
    delete_projekt(DB_PATH, PROJ)


def _links_weg():
    try:
        con = sqlite3.connect(str(DB_PATH))
        con.execute("DELETE FROM linked_issues WHERE projekt_name=?", (PROJ,))
        con.commit()
        con.close()
    except Exception:  # noqa: BLE001
        pass


@pytest.fixture()
def erzeugt(monkeypatch):
    """Das Anlegen abfangen und mitschreiben, womit es gerufen wurde."""
    rufe: list[tuple] = []

    def _fake(provider, repo, titel, body, vcs):
        rufe.append((provider, repo, titel, body, vcs))
        n = len(rufe)
        return (f"https://github.com/{repo}/issues/{n}", n, None)

    import shared.issue_api as ia
    monkeypatch.setattr(ia, "erzeuge_issue", _fake)
    return rufe


def _erste_anforderungen(anzahl: int = 3) -> list[str]:
    from cra.requirements import load_merged_anforderungen
    reqs = load_merged_anforderungen(DB_PATH)
    assert reqs, "Der CRA-Anforderungskatalog ist leer"
    return [str(r["id"]) for r in reqs[:anzahl]]


# ── Die Route tut, was auf dem Knopf steht ──────────────────────────────────

def test_stapel_legt_fuer_offene_punkte_an(client, auth_headers, projekt, erzeugt):
    """Ohne Auswahl: alle offenen Punkte, und je einer eine Verknüpfung."""
    r = client.post(f"{BASE}/projekte/{projekt}/issues/bulk", json={},
                    headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["summary"]["created"] == len(erzeugt) > 0
    # Jedes angelegte Issue ist verknüpft — sonst legt der nächste Lauf ein
    # zweites an, und im Repository des Kunden stehen Dubletten.
    links = list_project_links(DB_PATH, projekt_name=projekt,
                               object_kind="requirement")
    assert len(links) == d["summary"]["created"]


def test_auswahl_schlaegt_den_offen_filter(client, auth_headers, projekt, erzeugt):
    """Wer Objekte ausdrücklich nennt, bekommt genau diese."""
    ids = _erste_anforderungen(2)
    r = client.post(f"{BASE}/projekte/{projekt}/issues/bulk",
                    json={"object_ids": ids}, headers=auth_headers)
    assert r.status_code == 200
    assert r.get_json()["summary"]["created"] == 2
    gewaehlt = {str(l.object_id) for l in
                list_project_links(DB_PATH, projekt_name=projekt,
                                   object_kind="requirement")}
    assert gewaehlt == set(ids)


def test_verknuepfte_werden_uebersprungen(client, auth_headers, projekt, erzeugt):
    """`skip_linked` ist Vorgabe — zweimal klicken legt nichts doppelt an."""
    ids = _erste_anforderungen(1)
    ensure_tables(DB_PATH)
    add_link(DB_PATH, projekt_name=projekt, object_kind="requirement",
             object_id=ids[0], provider="github", repo="o/r",
             url="https://github.com/o/r/issues/9", issue_number=9, title="T")
    r = client.post(f"{BASE}/projekte/{projekt}/issues/bulk",
                    json={"object_ids": ids}, headers=auth_headers)
    assert r.status_code == 200
    d = r.get_json()
    assert d["summary"]["created"] == 0
    assert d["summary"]["skipped"] == 1
    assert erzeugt == [], "Es wurde trotzdem ein Issue angelegt"


def test_ohne_repository_gibt_es_400_und_kein_issue(client, auth_headers, erzeugt):
    """Ein Projekt ohne Repo-Konfiguration bekommt eine Aussage, keinen 500."""
    ensure_db(DB_PATH)
    name = f"{PROJ}-ohne-repo"
    save_projekt(DB_PATH, name=name, unternehmen="U", produkt="P")
    try:
        r = client.post(f"{BASE}/projekte/{name}/issues/bulk", json={},
                        headers=auth_headers)
        assert r.status_code == 400
        assert "Repository" in r.get_json()["error"]
        assert erzeugt == []
    finally:
        delete_projekt(DB_PATH, name)


def test_unbekanntes_projekt_gibt_404(client, auth_headers):
    r = client.post(f"{BASE}/projekte/gibt-es-nicht-1851/issues/bulk", json={},
                    headers=auth_headers)
    assert r.status_code == 404


def test_der_provider_kommt_aus_dem_projekt(client, auth_headers, projekt, erzeugt):
    """Kein fest mitgesendetes `github`.

    AI Act schickte als einziges Modul ``provider: 'github'`` im Body — damit
    legte ein auf **GitLab** konfiguriertes Projekt GitHub-Issues an, und im
    Nachweis sah das wie eine Entscheidung des Anwenders aus.
    """
    ids = _erste_anforderungen(1)
    client.post(f"{BASE}/projekte/{projekt}/issues/bulk",
                json={"object_ids": ids}, headers=auth_headers)
    assert erzeugt, "nichts angelegt"
    assert erzeugt[0][0] == "github", "Provider nicht aus der Projekt-Konfig"
    assert erzeugt[0][1] == "o/r", "Repo nicht aus der Projekt-Konfig"


def test_override_im_request_gewinnt(client, auth_headers, projekt, erzeugt):
    """Der dokumentierte `repo`-Override muss ankommen."""
    ids = _erste_anforderungen(1)
    client.post(f"{BASE}/projekte/{projekt}/issues/bulk",
                json={"object_ids": ids, "repo": "anders/repo"},
                headers=auth_headers)
    assert erzeugt[0][1] == "anders/repo"


def test_ein_fehlschlag_stoppt_den_lauf_nicht(client, auth_headers, projekt,
                                              monkeypatch):
    """Ein Issue, das nicht entsteht, darf die übrigen nicht mitnehmen."""
    rufe = {"n": 0}

    def _manchmal(provider, repo, titel, body, vcs):
        rufe["n"] += 1
        if rufe["n"] == 1:
            raise RuntimeError("Gegenstelle antwortet nicht")
        return (f"https://github.com/{repo}/issues/{rufe['n']}", rufe["n"], None)

    import shared.issue_api as ia
    monkeypatch.setattr(ia, "erzeuge_issue", _manchmal)
    ids = _erste_anforderungen(3)
    r = client.post(f"{BASE}/projekte/{projekt}/issues/bulk",
                    json={"object_ids": ids}, headers=auth_headers)
    assert r.status_code == 200
    d = r.get_json()
    assert d["summary"]["failed"] == 1
    assert d["summary"]["created"] == 2
    # Der Fehler steht im Ergebnis, nicht nur im Log — die Maske zeigt ihn.
    assert d["failed"][0]["error"]


def test_die_antwort_traegt_beide_formen(client, auth_headers, projekt, erzeugt):
    """Einträge **und** Zahlen.

    Vier Module lasen `summary` (Zahlen) und Einträge unter `created`; DSGVO
    las die **Zahlen** unter `created`. Ein echter Obermengen-Schlüssel ist für
    denselben Namen nicht möglich, deshalb: Einträge unter `created`, Zahlen in
    `summary`, und `*_items` als Alias für die DSGVO-Form.
    """
    r = client.post(f"{BASE}/projekte/{projekt}/issues/bulk",
                    json={"object_ids": _erste_anforderungen(1)},
                    headers=auth_headers)
    d = r.get_json()
    assert isinstance(d["created"], list)
    assert isinstance(d["summary"]["created"], int)
    assert d["created_items"] == d["created"]
    assert d["ok"] is True
    eintrag = d["created"][0]
    # Bestandsschlüssel der Oberflächen (#1830): ein fehlender wird dort
    # still `undefined`.
    for schluessel in ("object_id", "req_id", "risk_id", "control_id", "url"):
        assert schluessel in eintrag, f"{schluessel} fehlt im Eintrag"


# ── Die Quelle ist je Modul **eine** Objektart ──────────────────────────────

def test_nur_eine_objektart_speist_den_stapel():
    """Sonst legte ein Klick in CRA Issues für vier Objektarten an.

    CRA führt Anforderungen, OWASP-Kontrollen, Risiken und Schwachstellen.
    Würden alle vier den Stapel speisen, entstünden aus einem Klick Hunderte
    Tickets im Repository des Kunden — eine Nebenwirkung in einem fremden
    System, die von hier niemand zurücknehmen kann.
    """
    from shared.issue_api import arten_fuer
    for modul in ("cra", "nis2", "aiact", "dsgvo", "wiba", "risikobewertung"):
        quellen = [a.art for a in arten_fuer(modul) if a.alle is not None]
        assert len(quellen) == 1, (
            f"{modul}: {len(quellen)} Stapel-Quellen ({quellen}) — genau eine "
            "erwartet.")


def test_jede_stapel_quelle_sagt_was_offen_heisst():
    """Ohne `ist_offen` legte `only_gaps` für **alles** an."""
    from shared.issue_api import arten_fuer
    for modul in ("cra", "nis2", "aiact", "dsgvo", "wiba", "risikobewertung"):
        art = next(a for a in arten_fuer(modul) if a.alle is not None)
        assert art.ist_offen is not None, (
            f"{modul}/{art.art}: `ist_offen` fehlt — der Stapel legte dann "
            "auch für erledigte Objekte an.")


def test_wiba_zaehlt_nur_nein_als_offenen_punkt():
    """Bewusst enger als `only_gaps` der Score-Module.

    Dort ist eine unbewertete Anforderung eine bekannte Pflicht mit offener
    Lücke. In WiBA wäre `offen` eine Frage, die noch niemand angesehen hat —
    ein Klick legte 257 Tickets an. Das Modul zieht seine Befunde ebenfalls
    aus „Nein" (Risiko-Ableitung, #1118).
    """
    import inspect

    from shared.issue_api import arten_fuer
    art = next(a for a in arten_fuer("wiba") if a.alle is not None)
    quelle = inspect.getsource(art.ist_offen)
    assert "'nein'" in quelle, (
        'WiBAs Offen-Begriff muss „nein“ sein — sonst entstehen aus einem '
        'Klick Tickets für jede unbeantwortete Prüffrage.')
