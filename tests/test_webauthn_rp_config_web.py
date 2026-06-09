"""Tests: Passkey/WebAuthn-RP-Konfiguration über Web-Settings (statt nur ENV)."""

import pytest

from server.auth import webauthn as wa


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Isolierte Suite-Config-Datei pro Test.

    DEFAULT_CONFIG_PATH wird beim Import fixiert → wir patchen die Modul-Variable
    direkt (ENV-Patch nach Import würde nicht greifen).
    """
    cfg = tmp_path / 'aics.config.json'
    cfg.write_text('{}', encoding='utf-8')
    import ai_compliance_suite.config as _cfgmod
    monkeypatch.setattr(_cfgmod, 'DEFAULT_CONFIG_PATH', cfg)
    return cfg


class TestRpConfigPriority:
    def test_env_fallback(self, isolated_config, monkeypatch):
        monkeypatch.setenv('WEBAUTHN_RP_ID', 'env-host.local')
        monkeypatch.delenv('WEBAUTHN_RP_ORIGIN', raising=False)
        cfg = wa.get_rp_config()
        assert cfg['rp_id'] == 'env-host.local'

    def test_settings_overrides_env(self, isolated_config, monkeypatch):
        monkeypatch.setenv('WEBAUTHN_RP_ID', 'env-host.local')
        wa.save_rp_config('settings-host.local', 'My RP', 'https://settings-host.local:8443')
        cfg = wa.get_rp_config()
        assert cfg['rp_id'] == 'settings-host.local'
        assert cfg['rp_name'] == 'My RP'
        assert cfg['origins'] == ['https://settings-host.local:8443']

    def test_multi_origin(self, isolated_config):
        wa.save_rp_config('h.local', 'RP', 'https://a.local,https://b.local')
        assert wa.get_rp_config()['origins'] == ['https://a.local', 'https://b.local']

    def test_default_when_nothing_set(self, isolated_config, monkeypatch):
        for v in ('WEBAUTHN_RP_ID', 'WEBAUTHN_RP_NAME', 'WEBAUTHN_RP_ORIGIN'):
            monkeypatch.delenv(v, raising=False)
        cfg = wa.get_rp_config()
        assert cfg['rp_id'] == wa.DEFAULT_RP_ID


class TestAdminEndpoint:
    def test_requires_auth(self, client):
        assert client.get('/api/admin/webauthn-config').status_code in (401, 422)
        assert client.put('/api/admin/webauthn-config', json={}).status_code in (401, 422)

    def test_rejects_ip_as_rp_id(self, client, auth_headers):
        r = client.put('/api/admin/webauthn-config',
                       json={'rp_id': 'aics.example.com', 'rp_origin': 'https://aics.example.com:8443'},
                       headers=auth_headers)
        assert r.status_code == 400
        assert 'IP' in (r.get_json().get('error') or '')

    def test_rejects_schema_in_rp_id(self, client, auth_headers):
        r = client.put('/api/admin/webauthn-config',
                       json={'rp_id': 'https://aics.local', 'rp_origin': 'https://aics.local'},
                       headers=auth_headers)
        assert r.status_code == 400

    def test_rejects_non_https_origin(self, client, auth_headers):
        r = client.put('/api/admin/webauthn-config',
                       json={'rp_id': 'aics.local', 'rp_origin': 'ftp://aics.local'},
                       headers=auth_headers)
        assert r.status_code == 400

    def test_get_returns_shape(self, client, auth_headers):
        r = client.get('/api/admin/webauthn-config', headers=auth_headers)
        assert r.status_code == 200
        d = r.get_json()
        for k in ('rp_id', 'rp_name', 'rp_origin', 'from_settings'):
            assert k in d


class TestRpAutoDerive:
    """RP-ID/Origin werden aus dem Request-Origin abgeleitet, wenn nichts konfiguriert ist."""

    def test_register_options_derives_rp_from_origin(self, client, auth_headers, isolated_config, monkeypatch):
        for v in ('WEBAUTHN_RP_ID', 'WEBAUTHN_RP_ORIGIN'):
            monkeypatch.delenv(v, raising=False)
        r = client.post('/api/auth/webauthn/register/options',
                        headers={**auth_headers, 'Origin': 'https://aics.intern.local:8443'})
        assert r.status_code == 200
        assert r.get_json()['options']['rp']['id'] == 'aics.intern.local'

    def test_register_options_ip_rejected(self, client, auth_headers, isolated_config, monkeypatch):
        for v in ('WEBAUTHN_RP_ID', 'WEBAUTHN_RP_ORIGIN'):
            monkeypatch.delenv(v, raising=False)
        r = client.post('/api/auth/webauthn/register/options',
                        headers={**auth_headers, 'Origin': 'https://aics.example.com:8443'})
        assert r.status_code == 400
        assert 'Hostnamen' in (r.get_json().get('error') or '')

    def test_login_options_ip_rejected(self, client, isolated_config, monkeypatch):
        for v in ('WEBAUTHN_RP_ID', 'WEBAUTHN_RP_ORIGIN'):
            monkeypatch.delenv(v, raising=False)
        r = client.post('/api/auth/webauthn/login/options',
                        headers={'Origin': 'https://10.0.0.5:8443'})
        assert r.status_code == 400

    def test_settings_override_beats_derive(self, client, auth_headers, isolated_config, monkeypatch):
        from server.auth import webauthn as wa
        wa.save_rp_config('configured.example.com', 'RP', 'https://configured.example.com')
        r = client.post('/api/auth/webauthn/register/options',
                        headers={**auth_headers, 'Origin': 'https://other.host.local:8443'})
        assert r.status_code == 200
        assert r.get_json()['options']['rp']['id'] == 'configured.example.com'


class TestProxyDerive:
    """Ableitung hinter Reverse-Proxy via X-Forwarded-Host + Debug-Endpoint (#727)."""

    def test_derive_from_xforwarded_host(self, client, auth_headers, isolated_config, monkeypatch):
        for v in ('WEBAUTHN_RP_ID', 'WEBAUTHN_RP_ORIGIN'):
            monkeypatch.delenv(v, raising=False)
        r = client.post('/api/auth/webauthn/register/options',
                        headers={**auth_headers,
                                 'X-Forwarded-Host': 'compliancesuite.c99781.intern:8443',
                                 'X-Forwarded-Proto': 'https'})
        assert r.status_code == 200
        assert r.get_json()['options']['rp']['id'] == 'compliancesuite.c99781.intern'

    def test_origin_beats_xforwarded(self, client, auth_headers, isolated_config, monkeypatch):
        for v in ('WEBAUTHN_RP_ID', 'WEBAUTHN_RP_ORIGIN'):
            monkeypatch.delenv(v, raising=False)
        r = client.post('/api/auth/webauthn/register/options',
                        headers={**auth_headers,
                                 'Origin': 'https://real.host.intern:8443',
                                 'X-Forwarded-Host': 'other.host:9443'})
        assert r.get_json()['options']['rp']['id'] == 'real.host.intern'

    def test_debug_endpoint(self, client, auth_headers, isolated_config, monkeypatch):
        for v in ('WEBAUTHN_RP_ID', 'WEBAUTHN_RP_ORIGIN'):
            monkeypatch.delenv(v, raising=False)
        r = client.get('/api/auth/webauthn/debug',
                       headers={**auth_headers, 'X-Forwarded-Host': 'h.intern:8443', 'X-Forwarded-Proto': 'https'})
        assert r.status_code == 200
        d = r.get_json()
        assert d['effective_rp_id'] == 'h.intern'
        assert d['rp_id_is_ip'] is False
        assert d['request_headers']['X-Forwarded-Host'] == 'h.intern:8443'

    def test_debug_requires_auth(self, client):
        assert client.get('/api/auth/webauthn/debug').status_code in (401, 422)


class TestHardening:
    """#729: RP-ID muss Suffix des Origin-Hosts sein. #730: auth nicht im allg. Settings-Save."""

    def test_rp_id_must_match_origin(self, client, auth_headers):
        r = client.put('/api/admin/webauthn-config',
                       json={'rp_id': 'compliancesuite',
                             'rp_origin': 'https://compliancesuite.c99781.intern:8443'},
                       headers=auth_headers)
        assert r.status_code == 400
        assert 'passt nicht' in (r.get_json().get('error') or '')

    def test_rp_id_full_fqdn_ok(self, client, auth_headers, isolated_config):
        r = client.put('/api/admin/webauthn-config',
                       json={'rp_id': 'compliancesuite.c99781.intern',
                             'rp_origin': 'https://compliancesuite.c99781.intern:8443'},
                       headers=auth_headers)
        assert r.status_code == 200

    def test_rp_id_parent_suffix_ok(self, client, auth_headers, isolated_config):
        r = client.put('/api/admin/webauthn-config',
                       json={'rp_id': 'c99781.intern',
                             'rp_origin': 'https://compliancesuite.c99781.intern:8443'},
                       headers=auth_headers)
        assert r.status_code == 200

    def test_settings_save_does_not_clobber_auth(self, client, auth_headers, isolated_config):
        from server.auth import webauthn as wa
        wa.save_rp_config('keep.example.com', 'RP', 'https://keep.example.com')
        # allgemeines Settings-Save mit (veraltetem) auth-Block
        client.put('/api/admin/settings',
                   json={'auth': {'webauthn': {'rp_id': 'HIJACK', 'rp_origin': 'https://evil'}},
                         'appearance': {'dark_mode': True}},
                   headers=auth_headers)
        # auth.webauthn bleibt unangetastet
        assert wa.get_rp_config()['rp_id'] == 'keep.example.com'
