"""#1685 — bestehende Issues an ein RB-Risiko verknüpfen (mehrere möglich).

Die URL-Erkennung prüft seit #1851 die **gemeinsame** Funktion
``shared.issue_sync._parse_issue_url``. Die Risikobewertung hatte eine eigene
Kopie; sie wurde mit der Stapel-Anlage entfernt, weil sie im Betrieb niemand
mehr gerufen hat — die Verknüpfung läuft seit #1846 über die Fabrik, und die
benutzt die gemeinsame. Zwei Parser für dieselbe URL sind zwei Wahrheiten
darüber, was ein Issue-Link ist; dass nur die Kopie getestet war, hat genau das
verdeckt.

Zwei Unterschiede im Vertrag, beide hier festgehalten: Die gemeinsame Funktion
liefert fünf Werte (zusätzlich die Basis-URL, die GitLab braucht) und bei einer
nicht erkannten Adresse ``None`` statt einer leeren Zeichenkette.
"""
import pytest

from shared.issue_sync import _parse_issue_url


def test_parse_github_issue_url():
    provider, repo, number, iid, basis = _parse_issue_url(
        "https://github.com/acme/widget/issues/42")
    assert provider == "github"
    assert repo == "acme/widget"
    assert number == 42
    assert iid is None
    # GitHub braucht keine Basis-URL — die API-Adresse ist fest.
    assert basis is None


def test_parse_gitlab_issue_url():
    provider, repo, number, iid, basis = _parse_issue_url(
        "https://gitlab.com/group/sub/proj/-/issues/7")
    assert provider == "gitlab"
    assert repo == "group/sub/proj"
    assert iid == 7
    assert number is None
    # Die Basis-URL muss mit: Eine selbst gehostete GitLab-Instanz ist der
    # Normalfall, und ohne sie ginge der Abruf an gitlab.com.
    assert basis == "https://gitlab.com"


@pytest.mark.parametrize("url", [
    "", "not a url", "https://github.com/acme/widget",            # kein /issues/<n>
    "https://github.com/acme/widget/pull/42",                     # PR, kein Issue
    "https://example.com/x/y/z",
])
def test_parse_unrecognized(url):
    """Nicht erkannt heißt ``None`` — und **nicht** eine Ausnahme.

    Darauf beruht die 400er-Antwort der Fabrik: `_parse_issue_url` wirft nicht,
    es liefert Leerwerte. Wer eine Ausnahme erwartet, bekommt einen 500 — das
    war einer der vier Defekte aus #1846.
    """
    provider, repo, number, iid, basis = _parse_issue_url(url)
    assert provider is None


def test_link_list_unlink_roundtrip(client, auth_headers):
    """End-to-end gegen echte DB: Risiko anlegen → Issue verknüpfen → listen → entfernen."""
    proj = "RB-Link-1685"
    # Projekt + Risiko anlegen
    r = client.post('/api/risikobewertung/projekte',
                    json={'name': proj, 'framework': 'STRIDE', 'unternehmen': 'ACME'},
                    headers=auth_headers)
    assert r.status_code in (200, 201), r.get_data(as_text=True)
    r = client.post(f'/api/risikobewertung/projekte/{proj}/risiken',
                    json={'risk_name': 'Testrisiko', 'framework': 'STRIDE'},
                    headers=auth_headers)
    assert r.status_code in (200, 201), r.get_data(as_text=True)
    rid = r.get_json()['id']

    url1 = "https://github.com/acme/widget/issues/101"
    url2 = "https://github.com/acme/widget/issues/202"

    # zwei bestehende Issues verknüpfen (mehrere möglich)
    for u in (url1, url2):
        res = client.post(f'/api/risikobewertung/projekte/{proj}/risiken/{rid}/issues/link',
                          json={'url': u}, headers=auth_headers)
        assert res.status_code == 201, res.get_data(as_text=True)
        assert res.get_json()['linked'] is True

    # listen → beide da
    res = client.get(f'/api/risikobewertung/projekte/{proj}/risiken/{rid}/linked-issues',
                     headers=auth_headers)
    assert res.status_code == 200
    items = res.get_json()['items']
    assert len(items) == 2
    urls = {it['url'] for it in items}
    assert urls == {url1, url2}
    link_id = items[0]['id']

    # entfernen → nur noch eins
    res = client.delete(f'/api/risikobewertung/projekte/{proj}/risiken/{rid}/issues/{link_id}',
                        headers=auth_headers)
    assert res.status_code == 200
    res = client.get(f'/api/risikobewertung/projekte/{proj}/risiken/{rid}/linked-issues',
                     headers=auth_headers)
    assert len(res.get_json()['items']) == 1

    # ungültige URL → 400
    res = client.post(f'/api/risikobewertung/projekte/{proj}/risiken/{rid}/issues/link',
                      json={'url': 'kein-issue'}, headers=auth_headers)
    assert res.status_code == 400
