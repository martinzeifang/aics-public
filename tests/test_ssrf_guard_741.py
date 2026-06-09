"""Tests für SSRF-Schutz ausgehender Requests (#741 / WP-08).

INJ-1/INJ-2 · OWASP A10 · ASVS V12.6 · BSI APP.3.1.
Deckt: URL-Validierung (Schema, private/reservierte IPs, Cloud-Metadata),
Per-Redirect-Hop-Prüfung, Cloud-LLM-Provider-Allowlist.
"""

import pytest

from shared.net_validation import (
    SSRFError,
    validate_outbound_url,
    is_allowed_cloud_llm_host,
    enforce_cloud_llm_base_url,
    _ip_is_forbidden,
)
import ipaddress


class TestValidateOutboundUrl:
    @pytest.mark.parametrize('url', [
        'http://127.0.0.1/',
        'http://127.0.0.1:8080/admin',
        'http://localhost/',
        'http://169.254.169.254/latest/meta-data/',   # AWS-Metadata
        'http://[::1]/',
        'http://10.0.0.5/',                            # RFC1918
        'http://192.168.1.1/',                         # RFC1918
        'http://172.16.0.1/',                          # RFC1918
        'http://0.0.0.0/',                             # unspecified
    ])
    def test_blocks_private_and_reserved(self, url):
        with pytest.raises(SSRFError):
            validate_outbound_url(url)

    @pytest.mark.parametrize('url', [
        'ftp://example.com/',
        'file:///etc/passwd',
        'gopher://127.0.0.1/',
        'data:text/html,<script>',
    ])
    def test_blocks_non_http_schemes(self, url):
        with pytest.raises(SSRFError):
            validate_outbound_url(url)

    def test_blocks_url_without_host(self):
        with pytest.raises(SSRFError):
            validate_outbound_url('http:///nohost')

    def test_allows_public_ip_literal(self):
        # 8.8.8.8 ist öffentlich → keine DNS-Auflösung nötig, kein Block
        assert validate_outbound_url('https://8.8.8.8/') == 'https://8.8.8.8/'


class TestIpClassification:
    @pytest.mark.parametrize('ip', [
        '127.0.0.1', '10.1.2.3', '192.168.0.1', '172.31.255.255',
        '169.254.169.254', '::1', 'fc00::1', 'fe80::1', '224.0.0.1',
        '::ffff:127.0.0.1',   # IPv4-mapped Loopback
    ])
    def test_forbidden(self, ip):
        assert _ip_is_forbidden(ipaddress.ip_address(ip)) is True

    @pytest.mark.parametrize('ip', ['8.8.8.8', '1.1.1.1', '93.184.216.34'])
    def test_allowed_public(self, ip):
        assert _ip_is_forbidden(ipaddress.ip_address(ip)) is False


class TestCloudLlmAllowlist:
    @pytest.mark.parametrize('url', [
        'https://api.openai.com/v1',
        'https://api.anthropic.com',
        'https://generativelanguage.googleapis.com/v1beta',
    ])
    def test_allowed_hosts(self, url):
        assert is_allowed_cloud_llm_host(url) is True
        enforce_cloud_llm_base_url(url, context='test')  # raises nicht

    @pytest.mark.parametrize('url', [
        'https://evil.example.com/v1',
        'https://api.openai.com.evil.com/',   # Suffix-Trick
        'http://api.openai.com/v1',            # kein HTTPS
    ])
    def test_rejected(self, url):
        with pytest.raises(ValueError):
            enforce_cloud_llm_base_url(url, context='test')


class TestSafeGetRedirectValidation:
    def test_redirect_to_internal_is_blocked(self, monkeypatch):
        """safe_get muss einen Redirect auf eine interne IP ablehnen."""
        from shared import net_validation as nv

        class _Resp:
            def __init__(self, status, location=None):
                self.status_code = status
                self.headers = {'Location': location} if location else {}

            def close(self):
                pass

        # Erster (öffentlicher) Hop liefert Redirect auf Cloud-Metadata-IP.
        def _fake_get(url, allow_redirects=False, **kw):
            return _Resp(302, 'http://169.254.169.254/latest/')

        import requests
        monkeypatch.setattr(requests, 'get', _fake_get)

        # DNS-Auflösung deterministisch: example.com → öffentlich, IP-Literale 1:1.
        def _resolve(host):
            if host == 'example.com':
                return [ipaddress.ip_address('93.184.216.34')]
            return [ipaddress.ip_address(host)]
        monkeypatch.setattr(nv, '_resolve_host_ips', _resolve)

        with pytest.raises(SSRFError):
            nv.safe_get('http://example.com/', timeout=5)

    def test_direct_success_returns_response(self, monkeypatch):
        """Öffentliche URL ohne Redirect → Response wird durchgereicht."""
        from shared import net_validation as nv

        class _Resp:
            status_code = 200
            headers = {}

        import requests
        monkeypatch.setattr(requests, 'get', lambda url, **kw: _Resp())
        monkeypatch.setattr(nv, '_resolve_host_ips',
                            lambda host: [ipaddress.ip_address('93.184.216.34')])
        resp = nv.safe_get('http://example.com/', timeout=5)
        assert resp.status_code == 200
