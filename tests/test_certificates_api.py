"""Tests für server/api/certificates.py — Self-Signed + CSR + Apply (API)."""

import pytest


class TestAuthRequired:
    @pytest.mark.parametrize('method,path', [
        ('get', '/api/admin/certificates/current'),
        ('get', '/api/admin/certificates/suggest'),
        ('post', '/api/admin/certificates/self-signed/generate'),
        ('post', '/api/admin/certificates/apply'),
        ('post', '/api/admin/certificates/csr/generate'),
        ('get', '/api/admin/certificates/csr/pending'),
        ('post', '/api/admin/certificates/csr/import-signed'),
    ])
    def test_requires_auth(self, client, method, path):
        assert getattr(client, method)(path).status_code in (401, 422)


class TestSelfSigned:
    def test_generate(self, client, auth_headers):
        r = client.post('/api/admin/certificates/self-signed/generate',
                        json={'common_name': 'aics.intern.local',
                              'sans': ['aics.example.com', 'www.aics.intern.local'],
                              'validity_days': 365, 'key_size': 2048},
                        headers=auth_headers)
        assert r.status_code == 201
        d = r.get_json()
        assert d['cert_pem'].startswith('-----BEGIN CERTIFICATE-----')
        assert d['key_pem'].startswith('-----BEGIN RSA PRIVATE KEY-----')
        assert d['info']['common_name'] == 'aics.intern.local'
        assert 'aics.example.com' in d['info']['sans']

    def test_generate_invalid(self, client, auth_headers):
        r = client.post('/api/admin/certificates/self-signed/generate',
                        json={'common_name': '', 'sans': []}, headers=auth_headers)
        assert r.status_code == 400


class TestApply:
    def test_apply_writes(self, client, auth_headers, tmp_path, monkeypatch):
        import server.api.certificates as mod
        monkeypatch.setattr(mod, '_CERT_DIR', tmp_path / 'certs')
        gen = client.post('/api/admin/certificates/self-signed/generate',
                          json={'common_name': 'apply.local'}, headers=auth_headers).get_json()
        r = client.post('/api/admin/certificates/apply',
                        json={'cert_pem': gen['cert_pem'], 'key_pem': gen['key_pem']},
                        headers=auth_headers)
        assert r.status_code == 200
        assert r.get_json()['applied'] is True
        assert (tmp_path / 'certs' / 'server.crt').exists()
        assert (tmp_path / 'certs' / 'certificate.crt').exists()

    def test_apply_mismatch(self, client, auth_headers, tmp_path, monkeypatch):
        import server.api.certificates as mod
        monkeypatch.setattr(mod, '_CERT_DIR', tmp_path / 'certs')
        a = client.post('/api/admin/certificates/self-signed/generate',
                        json={'common_name': 'a.local'}, headers=auth_headers).get_json()
        b = client.post('/api/admin/certificates/self-signed/generate',
                        json={'common_name': 'b.local'}, headers=auth_headers).get_json()
        r = client.post('/api/admin/certificates/apply',
                        json={'cert_pem': a['cert_pem'], 'key_pem': b['key_pem']},
                        headers=auth_headers)
        assert r.status_code == 400


class TestCSR:
    def test_generate_and_pending_and_import(self, client, auth_headers, tmp_path, monkeypatch):
        import server.api.certificates as mod
        monkeypatch.setattr(mod, '_PENDING_DIR', tmp_path / 'pending')
        gen = client.post('/api/admin/certificates/csr/generate',
                          json={'common_name': 'pki.example.com', 'organization': 'ACME',
                                'country': 'DE', 'sans': ['10.1.2.3']},
                          headers=auth_headers)
        assert gen.status_code == 201
        gd = gen.get_json()
        assert gd['csr_pem'].startswith('-----BEGIN CERTIFICATE REQUEST-----')
        csr_id = gd['csr_id']

        pend = client.get('/api/admin/certificates/csr/pending', headers=auth_headers).get_json()
        assert any(p['id'] == csr_id for p in pend['pending'])

        # "Signiertes" Cert simulieren: self-signed mit demselben Key wäre nötig;
        # hier prüfen wir nur den Mismatch-Pfad (fremdes Cert passt nicht zum Key).
        other = client.post('/api/admin/certificates/self-signed/generate',
                            json={'common_name': 'pki.example.com'}, headers=auth_headers).get_json()
        r = client.post('/api/admin/certificates/csr/import-signed',
                        json={'cert_pem': other['cert_pem'], 'csr_id': csr_id},
                        headers=auth_headers)
        assert r.status_code == 400  # fremder Key → kein Match

    def test_import_with_matching_key(self, client, auth_headers):
        # Eigenes Paar erzeugen und gegeneinander prüfen (Key mitgeliefert)
        gen = client.post('/api/admin/certificates/self-signed/generate',
                          json={'common_name': 'm.local'}, headers=auth_headers).get_json()
        r = client.post('/api/admin/certificates/csr/import-signed',
                        json={'cert_pem': gen['cert_pem'], 'key_pem': gen['key_pem']},
                        headers=auth_headers)
        assert r.status_code == 200
        assert r.get_json()['matches'] is True


class TestCertStore:
    def _isolate(self, monkeypatch, tmp_path):
        import server.api.certificates as mod
        monkeypatch.setattr(mod, '_STORE_DIR', tmp_path / 'store')
        monkeypatch.setattr(mod, '_CERT_DIR', tmp_path / 'active')
        return mod

    def test_generate_saves_to_store(self, client, auth_headers, tmp_path, monkeypatch):
        self._isolate(monkeypatch, tmp_path)
        gen = client.post('/api/admin/certificates/self-signed/generate',
                          json={'common_name': 's1.local'}, headers=auth_headers).get_json()
        assert 'store_id' in gen
        lst = client.get('/api/admin/certificates/store', headers=auth_headers).get_json()
        assert any(c['id'] == gen['store_id'] for c in lst['certificates'])

    def test_list_marks_active(self, client, auth_headers, tmp_path, monkeypatch):
        self._isolate(monkeypatch, tmp_path)
        gen = client.post('/api/admin/certificates/self-signed/generate',
                          json={'common_name': 's2.local'}, headers=auth_headers).get_json()
        client.post(f"/api/admin/certificates/store/{gen['store_id']}/apply", headers=auth_headers)
        lst = client.get('/api/admin/certificates/store', headers=auth_headers).get_json()
        entry = next(c for c in lst['certificates'] if c['id'] == gen['store_id'])
        assert entry['active'] is True

    def test_apply_by_id(self, client, auth_headers, tmp_path, monkeypatch):
        self._isolate(monkeypatch, tmp_path)
        gen = client.post('/api/admin/certificates/self-signed/generate',
                          json={'common_name': 's3.local'}, headers=auth_headers).get_json()
        r = client.post(f"/api/admin/certificates/store/{gen['store_id']}/apply", headers=auth_headers)
        assert r.status_code == 200 and r.get_json()['applied'] is True
        assert (tmp_path / 'active' / 'server.crt').exists()

    def test_cannot_delete_active(self, client, auth_headers, tmp_path, monkeypatch):
        self._isolate(monkeypatch, tmp_path)
        gen = client.post('/api/admin/certificates/self-signed/generate',
                          json={'common_name': 's4.local'}, headers=auth_headers).get_json()
        client.post(f"/api/admin/certificates/store/{gen['store_id']}/apply", headers=auth_headers)
        r = client.delete(f"/api/admin/certificates/store/{gen['store_id']}", headers=auth_headers)
        assert r.status_code == 409

    def test_delete_inactive(self, client, auth_headers, tmp_path, monkeypatch):
        self._isolate(monkeypatch, tmp_path)
        gen = client.post('/api/admin/certificates/self-signed/generate',
                          json={'common_name': 's5.local'}, headers=auth_headers).get_json()
        r = client.delete(f"/api/admin/certificates/store/{gen['store_id']}", headers=auth_headers)
        assert r.status_code == 200
        lst = client.get('/api/admin/certificates/store', headers=auth_headers).get_json()
        assert not any(c['id'] == gen['store_id'] for c in lst['certificates'])

    def test_import_to_store(self, client, auth_headers, tmp_path, monkeypatch):
        self._isolate(monkeypatch, tmp_path)
        gen = client.post('/api/admin/certificates/self-signed/generate',
                          json={'common_name': 's6.local'}, headers=auth_headers).get_json()
        r = client.post('/api/admin/certificates/store/import',
                        json={'cert_pem': gen['cert_pem'], 'key_pem': gen['key_pem'], 'label': 'X'},
                        headers=auth_headers)
        # gleicher Fingerprint wie schon gespeichert → idempotent (gleiche ID)
        assert r.status_code == 201

    def test_requires_auth(self, client):
        assert client.get('/api/admin/certificates/store').status_code in (401, 422)
