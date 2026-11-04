"""Tests für Frontend-XSS-Härtung + strikte CSP (Issue #740, WP-07).

Deckt ab:
  (a) CSP-Header vorhanden; ``script-src`` OHNE ``unsafe-inline``/``unsafe-eval``.
  (b) Server-seitiger Sanitizer entfernt ``<img onerror>`` / ``<script>``.
  (c) Round-Trip: gespeichertes Gutachten-Textfeld wird server-seitig bereinigt.
"""
import uuid

import pytest

from shared.html_sanitize import sanitize_html


@pytest.fixture(autouse=True)
def _full_license():
    """CI hat keine Lizenz → Schreibzugriffe würden 423 liefern. Volllizenz mocken."""
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    # gutachten ist von der '*'-Wildcard ausgenommen → explizit auflisten.
    cur.state, cur.modules = 'ok', [
        'cra', 'nis2', 'aiact', 'dsgvo', 'risikobewertung', 'gutachten', 'firmen',
    ]
    yield
    cur.state, cur.modules = prev[0], prev[1]


# ── (a) CSP-Header ─────────────────────────────────────────────────────────
def test_csp_header_present_and_strict(client):
    resp = client.get('/api/auth/login')  # beliebige Route; Header werden immer gesetzt
    csp = resp.headers.get('Content-Security-Policy')
    assert csp, 'Content-Security-Policy header fehlt'

    # script-src-Direktive isolieren.
    directives = {
        part.strip().split(' ', 1)[0]: part.strip()
        for part in csp.split(';') if part.strip()
    }
    assert 'script-src' in directives
    script_src = directives['script-src']
    assert "'unsafe-inline'" not in script_src, f'unsafe-inline in script-src: {script_src}'
    assert "'unsafe-eval'" not in script_src, f'unsafe-eval in script-src: {script_src}'
    assert "'self'" in script_src
    # Sinnvolle Defaults vorhanden.
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp


# ── (b) Sanitizer-Unit-Tests ───────────────────────────────────────────────
def test_sanitizer_strips_img_onerror():
    dirty = '<p>ok</p><img src=x onerror=alert(1)>'
    clean = sanitize_html(dirty)
    assert '<img' not in clean
    assert 'onerror' not in clean
    assert '<p>ok</p>' in clean


def test_sanitizer_strips_script():
    dirty = "<script>alert('xss')</script><strong>bold</strong>"
    clean = sanitize_html(dirty)
    assert '<script' not in clean.lower()
    assert 'alert' not in clean
    assert '<strong>bold</strong>' in clean


def test_sanitizer_strips_javascript_url():
    dirty = '<a href="javascript:alert(1)">x</a>'
    clean = sanitize_html(dirty)
    assert 'javascript:' not in clean.lower()


def test_sanitizer_keeps_allowed_tags():
    dirty = '<p>a <strong>b</strong> <em>c</em> <a href="https://x.de">l</a></p>'
    clean = sanitize_html(dirty)
    assert '<strong>b</strong>' in clean
    assert '<em>c</em>' in clean
    assert 'href="https://x.de"' in clean


def test_sanitizer_strips_style_and_event_attrs():
    dirty = '<p style="color:red" onclick="evil()">x</p>'
    clean = sanitize_html(dirty)
    assert 'style' not in clean
    assert 'onclick' not in clean
    assert '<p>x</p>' in clean


# ── (c) Round-Trip über die API ────────────────────────────────────────────
def test_befund_save_sanitizes_html_field(client, auth_headers):
    pname = f'xss-test-{uuid.uuid4().hex[:8]}'
    # Gerichts-Projekt anlegen.
    r = client.post('/api/gutachten/gerichts',
                    json={'name': pname, 'aktenzeichen': 'AZ-1'},
                    headers=auth_headers)
    assert r.status_code in (200, 201), r.get_data(as_text=True)

    payload = {
        'nr': '1',
        'titel': 'Test',
        'beschreibung_text': '<p>safe</p><img src=x onerror=alert(1)><script>alert(2)</script>',
    }
    r = client.post(f'/api/gutachten/gerichts/{pname}/befunde',
                    json=payload, headers=auth_headers)
    assert r.status_code in (200, 201), r.get_data(as_text=True)

    r = client.get(f'/api/gutachten/gerichts/{pname}/befunde', headers=auth_headers)
    assert r.status_code == 200
    befunde = r.get_json()['befunde']
    stored = next(b for b in befunde if b['nr'] == '1')['beschreibung_text']
    assert '<img' not in stored
    assert 'onerror' not in stored
    assert '<script' not in stored.lower()
    assert '<p>safe</p>' in stored
