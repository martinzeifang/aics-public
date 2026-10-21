"""Sprint #28 / Milestone #30 — CRA Versions-/Klassifizierungs-Ausbau (#1247–#1249).

Deckt ab:
- #1247 Produktklasse manuell editierbar + C6/C7-Read-Back (sticky manual_override).
- #1248 Versions-Änderungen aus GitHub/GitLab importieren (Releases/Tags/Compare).
- #1249 Wesentliche Änderungen je Version per KI-Prompt zusammenfassen.

Wizard-Funktionen werden DB-frei getestet; API-Round-Trips über echte CRA-DB.
Repo-API wird gemockt (kein echter Netzzugriff).
"""
import pytest

CRA = '/api/cra'
FIRMA = 'pytest-firma-1247'
PROJ = 'pytest-cra-1247'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture
def projekt(client, auth_headers):
    client.delete(f'{CRA}/projekte/{PROJ}', headers=auth_headers)
    client.post(f'{CRA}/projekte', headers=auth_headers,
                json={'name': PROJ, 'unternehmen': FIRMA,
                      'produktklasse': 'default',
                      'beschreibung': 'Eine Firewall-Appliance'})
    yield PROJ
    client.delete(f'{CRA}/projekte/{PROJ}', headers=auth_headers)


# ════════════════════════════════════════════════════════════════════
# #1247 — Klassifizierung manuell + Read-Back + Sticky-Schutz
# ════════════════════════════════════════════════════════════════════

def test_klassifizierung_read_back_initial(client, auth_headers, projekt):
    r = client.get(f'{CRA}/projekte/{projekt}/klassifizierung', headers=auth_headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body['produktklasse'] == 'default'
    assert body['klassifikator'] is None  # noch kein C6 gelaufen
    assert 'branche' in body and 'defaults' in body['branche']


def test_klassifizierung_manuell_setzen_persistiert(client, auth_headers, projekt):
    r = client.put(f'{CRA}/projekte/{projekt}/klassifizierung',
                   headers=auth_headers, json={'produktklasse': 'important_ii',
                                               'begruendung': 'Firewall = Annex III Kl. 2'})
    assert r.status_code == 200
    assert r.get_json()['produktklasse'] == 'important_ii'
    # Read-Back zeigt source='manuell' + Begründung.
    rb = client.get(f'{CRA}/projekte/{projekt}/klassifizierung', headers=auth_headers).get_json()
    assert rb['produktklasse'] == 'important_ii'
    assert rb['klassifikator']['source'] == 'manuell'
    assert rb['klassifikator']['updated_at']
    assert 'Annex III' in rb['klassifikator']['begruendung']


def test_klassifizierung_invalid_klasse_400(client, auth_headers, projekt):
    r = client.put(f'{CRA}/projekte/{projekt}/klassifizierung',
                   headers=auth_headers, json={'produktklasse': 'bogus'})
    assert r.status_code == 400


def test_c6_wizard_respektiert_manuelle_klasse_sticky(client, auth_headers, projekt):
    # 1) manuell setzen → sticky.
    client.put(f'{CRA}/projekte/{projekt}/klassifizierung',
               headers=auth_headers, json={'produktklasse': 'important_ii'})
    # 2) C6-Wizard versucht eine andere Klasse → wird blockiert (kein stilles Übersteuern).
    raw = '{"klasse": "default", "begruendung": "x", "konfidenz": "hoch"}'
    r = client.post(f'{CRA}/projekte/{projekt}/wizards/klassifikator/parse',
                    headers=auth_headers, json={'response': raw})
    assert r.status_code == 200
    body = r.get_json()
    assert body['applied'] is False
    assert body['blocked_by_manual'] is True
    # Klasse unverändert important_ii.
    rb = client.get(f'{CRA}/projekte/{projekt}/klassifizierung', headers=auth_headers).get_json()
    assert rb['produktklasse'] == 'important_ii'
    assert rb['klassifikator']['source'] == 'manuell'


def test_c6_wizard_force_ueberschreibt_manuell(client, auth_headers, projekt):
    client.put(f'{CRA}/projekte/{projekt}/klassifizierung',
               headers=auth_headers, json={'produktklasse': 'important_ii'})
    raw = '{"klasse": "critical", "begruendung": "HSM", "konfidenz": "hoch"}'
    r = client.post(f'{CRA}/projekte/{projekt}/wizards/klassifikator/parse?force=true',
                    headers=auth_headers, json={'response': raw})
    assert r.status_code == 200
    body = r.get_json()
    assert body['applied'] is True and body['blocked_by_manual'] is False
    rb = client.get(f'{CRA}/projekte/{projekt}/klassifizierung', headers=auth_headers).get_json()
    assert rb['produktklasse'] == 'critical'
    assert rb['klassifikator']['source'] == 'wizard'


# ════════════════════════════════════════════════════════════════════
# #1248 — Versions-Import (Releases/Tags/Compare), Repo gemockt
# ════════════════════════════════════════════════════════════════════

def _link_repo(client, auth_headers, projekt, provider='github', repo='acme/fw'):
    """Repo pro Projekt verknüpfen (vcs_publish in meta)."""
    client.put(f'{CRA}/projekte/{projekt}', headers=auth_headers,
               json={'meta': {'vcs_publish': {'provider': provider, 'repo': repo}}})


def test_versions_ohne_repo_klare_meldung(client, auth_headers, projekt):
    r = client.get(f'{CRA}/projekte/{projekt}/versions', headers=auth_headers)
    assert r.status_code == 400
    body = r.get_json()
    assert body.get('repo_missing') is True
    assert 'Repository' in body['error']  # kein 500


def test_versions_github_gemockt(client, auth_headers, projekt, monkeypatch):
    _link_repo(client, auth_headers, projekt)

    def fake_gh(path):
        if 'releases' in path:
            return [{'tag_name': 'v1.1.0', 'name': 'Release 1.1.0',
                     'published_at': '2026-01-02T00:00:00Z', 'html_url': 'http://x/v1.1.0'}]
        if 'tags' in path:
            return [{'name': 'v1.1.0'}, {'name': 'v1.0.0'}]
        return []

    import cra.repo_alignment as ra
    monkeypatch.setattr(ra, '_gh_api_json', fake_gh)
    r = client.get(f'{CRA}/projekte/{projekt}/versions', headers=auth_headers)
    assert r.status_code == 200
    body = r.get_json()
    names = {v['name'] for v in body['versions']}
    assert names == {'v1.1.0', 'v1.0.0'}
    # Release-Eintrag behält Typ 'release'.
    rel = next(v for v in body['versions'] if v['name'] == 'v1.1.0')
    assert rel['typ'] == 'release'


def test_version_diff_github_gemockt_und_cache(client, auth_headers, projekt, monkeypatch):
    _link_repo(client, auth_headers, projekt)

    def fake_gh(path):
        if 'compare' in path:
            return {
                'commits': [
                    {'sha': 'abc1234567', 'commit': {'message': 'Add OAuth login',
                                                     'author': {'name': 'Dev'}}},
                    {'sha': 'def7654321', 'commit': {'message': 'Fix typo',
                                                     'author': {'name': 'Dev'}}},
                ],
                'files': [{'filename': 'auth.py'}, {'filename': 'README.md'}],
            }
        # CHANGELOG-Lookup schlägt fehl → leerer Changelog (best-effort).
        raise RuntimeError('404 Not Found')

    import cra.repo_alignment as ra
    monkeypatch.setattr(ra, '_gh_api_json', fake_gh)
    r = client.get(f'{CRA}/projekte/{projekt}/version-diff?base=v1.0.0&head=v1.1.0',
                   headers=auth_headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body['commit_count'] == 2 and body['file_count'] == 2
    assert any('OAuth' in c['message'] for c in body['commits'])
    # Cache: erneut über version-changes-Prompt nutzbar (meta.cra.version_changes).
    pr = client.get(f'{CRA}/projekte/{projekt}/wizards/version-changes/prompt',
                    headers=auth_headers)
    assert pr.status_code == 200
    assert 'OAuth' in pr.get_json()['prompt']


def test_version_diff_fehlende_params_400(client, auth_headers, projekt):
    _link_repo(client, auth_headers, projekt)
    r = client.get(f'{CRA}/projekte/{projekt}/version-diff?base=v1.0.0', headers=auth_headers)
    assert r.status_code == 400


def test_repo_changes_module_gitlab_ssrf_validiert(monkeypatch):
    """GitLab-Pfad nutzt safe_get (SSRF). Interne URL → RepoChangesError."""
    from vcs import repo_changes
    from shared.net_validation import SSRFError

    def boom(url, **kw):
        raise SSRFError('blocked')
    monkeypatch.setattr('shared.net_validation.safe_get', boom)
    with pytest.raises(repo_changes.RepoChangesError):
        repo_changes.list_versions('gitlab', 'group/proj', base_url='http://169.254.169.254')


def test_repo_changes_list_versions_ohne_repo_raises():
    from vcs import repo_changes
    with pytest.raises(repo_changes.RepoChangesError):
        repo_changes.list_versions('github', '')


# ════════════════════════════════════════════════════════════════════
# #1249 — Versions-Änderungen per KI zusammenfassen
# ════════════════════════════════════════════════════════════════════

def test_version_changes_prompt_enthaelt_commits():
    from cra.ai_wizards import build_version_changes_prompt
    changes = {'commits': [{'message': 'Add TLS 1.3 support', 'sha': 'a1b2c3'}],
               'changed_files': ['tls.py']}
    prompt = build_version_changes_prompt(changes, 'v1.0', 'v1.1',
                                          {'name': 'FW', 'unternehmen': 'ACME'})
    assert 'TLS 1.3' in prompt and 'wesentliche' in prompt.lower()
    assert 'v1.0' in prompt and 'v1.1' in prompt and 'ACME' in prompt


def test_version_changes_prompt_fallback_ohne_changes():
    from cra.ai_wizards import build_version_changes_prompt
    prompt = build_version_changes_prompt(None, '', '', {})
    assert 'keine Commits' in prompt  # kein harter Fehler


def test_version_changes_parse_heuristik_markiert_security():
    from cra.ai_wizards import parse_version_changes_response
    raw = ('{"version": "v1.1", "zusammenfassung": "Sicherheits-Release", '
           '"aenderungen": ['
           '{"titel": "Neuer OAuth-Login", "beschreibung": "Auth umgestellt", '
           '"cra_relevant": false, "moegliche_wesentliche_aenderung": true, "kategorie": "security"},'
           '{"titel": "Doku-Tippfehler", "beschreibung": "README", '
           '"cra_relevant": false, "kategorie": "fix"}'
           '], "konformitaet_pruefen": false}')
    parsed = parse_version_changes_response(raw)
    aend = {a['titel']: a for a in parsed['aenderungen']}
    # Heuristik hebt 'OAuth' als cra_relevant an, obwohl ChatGPT false lieferte.
    assert aend['Neuer OAuth-Login']['cra_relevant'] is True
    assert aend['Neuer OAuth-Login']['moegliche_wesentliche_aenderung'] is True
    # wesentliche Änderung → konformitaet_pruefen wird serverseitig erzwungen.
    assert parsed['konformitaet_pruefen'] is True
    # Reine Doku-Änderung bleibt unmarkiert.
    assert aend['Doku-Tippfehler']['cra_relevant'] is False


def test_version_changes_to_markdown():
    from cra.ai_wizards import version_changes_to_markdown, parse_version_changes_response
    parsed = parse_version_changes_response(
        '{"version": "v2.0", "zusammenfassung": "Major", "aenderungen": '
        '[{"titel": "Krypto-Update", "beschreibung": "AES-GCM", '
        '"moegliche_wesentliche_aenderung": true}], "konformitaet_pruefen": true, '
        '"hinweis": "Bewertung prüfen"}')
    md = version_changes_to_markdown(parsed)
    assert 'Wesentliche Änderungen' in md and 'v2.0' in md
    assert 'Krypto-Update' in md and 'wesentliche Änderung' in md
    assert 'Bewertung prüfen' in md


def test_version_changes_api_prompt_parse(client, auth_headers, projekt):
    pr = client.get(f'{CRA}/projekte/{projekt}/wizards/version-changes/prompt'
                    '?text=Add%20OAuth%20login', headers=auth_headers)
    assert pr.status_code == 200
    assert 'OAuth' in pr.get_json()['prompt']  # manueller Fallback-Text
    raw = ('{"version": "v1.1", "aenderungen": '
           '[{"titel": "TLS-Fix", "cra_relevant": true, '
           '"moegliche_wesentliche_aenderung": true}], "konformitaet_pruefen": true}')
    pa = client.post(f'{CRA}/projekte/{projekt}/wizards/version-changes/parse',
                     headers=auth_headers, json={'response': raw})
    assert pa.status_code == 200
    body = pa.get_json()
    assert body['applied'] is False
    assert 'markdown' in body and 'Wesentliche Änderungen' in body['markdown']
    assert body['konformitaet_pruefen'] is True


def test_tech_doku_suggested_assistant_version_changes():
    from shared.documents.catalog import get_doc_spec
    spec = get_doc_spec('cra', 'technische_doku_annex_vii')
    assert spec['suggested_assistant'] == 'version-changes'
