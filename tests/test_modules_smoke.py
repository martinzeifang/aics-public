"""Smoke-Tests für alle Module: existiert die API + liefert sie sinnvolle Daten?"""

import pytest


class TestModuleConstants:
    """Pro Modul: Konstanten-Endpoint sollte erreichbar sein."""

    def test_cra_constants(self, client, auth_headers):
        r = client.get('/api/cra/constants', headers=auth_headers)
        assert r.status_code == 200
        assert 'kapitel' in r.json
        assert 'bewertung_skala' in r.json

    def test_cra_owasp_catalog(self, client, auth_headers):
        r = client.get('/api/cra/owasp', headers=auth_headers)
        assert r.status_code == 200
        # 10 OWASP Proactive Controls
        assert len(r.json) == 10
        assert r.json[0]['id'] == 'OWASP-PC-C1'

    def test_dora_constants(self, client, auth_headers):
        r = client.get('/api/dora/constants', headers=auth_headers)
        assert r.status_code == 200
        assert 'pfeiler' in r.json
        # 5 DORA-Pfeiler
        assert len(r.json['pfeiler']) == 5

    def test_dora_pfeiler_full_catalog(self, client, auth_headers):
        r = client.get('/api/dora/pfeiler', headers=auth_headers)
        assert r.status_code == 200
        # 5 Pfeiler
        assert set(r.json.keys()) == {'ICT-RM', 'ICT-IM', 'ICT-RT', 'ICT-TP', 'ICT-IS'}
        # ~32 Anforderungen total
        total = sum(len(v) for v in r.json.values())
        assert total >= 30

    def test_rb_frameworks(self, client, auth_headers):
        r = client.get('/api/risikobewertung/frameworks', headers=auth_headers)
        assert r.status_code == 200
        ids = [f['id'] for f in r.json]
        assert 'STRIDE' in ids
        assert 'TARA' in ids
        assert 'STRIDE-LLM' in ids  # #540: LLM-Framework ergänzt
        assert 'EU-AI-Act' in ids   # #1044: Bewertungsart EU-AI-Act ergänzt
        assert 'DSGVO-DSFA' in ids  # #1084: DSFA-Framework ergänzt
        assert len(ids) == 8


class TestProjekteList:
    """GET /projekte für jedes Modul liefert Liste (auch leer = 200)."""

    @pytest.mark.parametrize('module', ['cra', 'nis2', 'aiact', 'dora', 'risikobewertung'])
    def test_projekte_endpoint_works(self, client, auth_headers, module):
        r = client.get(f'/api/{module}/projekte', headers=auth_headers)
        assert r.status_code == 200
        assert isinstance(r.json, list)


class TestPermissionGuard:
    """Endpoints ohne Token müssen 401 liefern."""

    @pytest.mark.parametrize('path', [
        '/api/cra/projekte',
        '/api/nis2/projekte',
        '/api/dora/projekte',
        '/api/aiact/projekte',
        '/api/risikobewertung/projekte',
        '/api/firmen',
    ])
    def test_unauthenticated_blocked(self, client, path):
        r = client.get(path)
        assert r.status_code == 401


class TestSwaggerDocs:
    """Phase 7.1: Swagger-UI + OpenAPI-Spec."""

    def test_swagger_ui_loads(self, client):
        r = client.get('/api/docs/')
        assert r.status_code == 200
        assert b'swagger' in r.data.lower() or b'openapi' in r.data.lower()

    def test_apispec_json(self, client):
        r = client.get('/api/apispec.json')
        assert r.status_code == 200
        data = r.json
        assert data['info']['title'] == 'AI Compliance Suite API'
        assert '/auth/login' in data['paths']


class TestServicesPrefill:
    """Phase 5.7: Prefill-Service mit Repo-Helfern."""

    def test_parse_github_repo(self):
        from server.services.prefill import parse_github_repo
        assert parse_github_repo('owner/repo') == ('owner', 'repo')
        assert parse_github_repo('https://github.com/owner/repo') == ('owner', 'repo')
        assert parse_github_repo('https://github.com/owner/repo.git') == ('owner', 'repo')
        assert parse_github_repo('') is None

    def test_get_ai_provider_config(self):
        from server.services.prefill import get_ai_provider_config
        cfg = get_ai_provider_config()
        assert 'provider' in cfg
        assert cfg['provider'] in ('on_prem', 'cloud')


class TestServicesReports:
    """Phase 5.7: Reports-Service-Helfer."""

    def test_score_label(self):
        from server.services.reports import score_label
        assert score_label(0) == 'Nicht bewertet'
        assert score_label(5) == 'Vollständig'
        assert score_label(99) == 'Vollständig'  # clamped to max
        assert score_label(-1) == 'Nicht bewertet'

    def test_score_color(self):
        from server.services.reports import score_color_hex
        assert score_color_hex(0) == '9E9E9E'
        assert score_color_hex(5) == '2E7D32'

    def test_ampel(self):
        from server.services.reports import ampel_for_percent
        assert ampel_for_percent(80) == 'gruen'
        assert ampel_for_percent(50) == 'orange'
        assert ampel_for_percent(20) == 'rot'

    def test_safe_filename(self):
        from server.services.reports import safe_filename
        assert safe_filename('Hello World') == 'Hello_World'
        assert safe_filename('foo/bar:baz!') == 'foobarbaz'
        assert safe_filename('') == 'report'
