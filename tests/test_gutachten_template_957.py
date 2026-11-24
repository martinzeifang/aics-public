"""Sprint #19 — #957 Custom-Word-Vorlagen.

Testet die docxtpl-unabhängigen Kernteile: Schema-Klassifikation,
Sicherheits-Validierung (verbotene Jinja-Konstrukte, Format, Größe) und das
Template-CRUD inkl. Default-Logik.
"""
import io
import zipfile
from pathlib import Path

import pytest

from gutachten import gerichts_db as gdb
from gutachten import template_schema as ts
from gutachten import template_render as tr


# ── Schema-Klassifikation ──────────────────────────────────────────────────

def test_classify_variables():
    res = ts.classify_variables({'projekt.aktenzeichen', 'beweisfragen', 'mein_logo', ''})
    assert 'projekt.aktenzeichen' in res['erkannt']
    assert 'beweisfragen' in res['erkannt']
    assert 'mein_logo' in res['frei']
    assert '' in res['ungueltig']


def test_required_keys_present():
    assert 'projekt.sv_name' in ts.REQUIRED_KEYS
    assert 'projekt.name' in ts.REQUIRED_KEYS


# ── Sicherheits-Validierung (ohne docxtpl) ─────────────────────────────────

def _docx_bytes(document_xml: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('[Content_Types].xml', '<Types/>')
        zf.writestr('word/document.xml', document_xml)
    return buf.getvalue()


def test_validate_rejects_non_docx():
    errors = tr.validate_template_bytes(b'not a zip at all', 'x.docx')
    assert any('ZIP' in e or 'DOCX' in e for e in errors)


def test_validate_rejects_wrong_extension():
    data = _docx_bytes('<w:document>{{ projekt.name }}</w:document>')
    errors = tr.validate_template_bytes(data, 'evil.exe')
    assert any('docx' in e.lower() for e in errors)


def test_validate_rejects_forbidden_jinja():
    data = _docx_bytes('<w:document>{% include "/etc/passwd" %}</w:document>')
    errors = tr.validate_template_bytes(data, 'tpl.docx')
    assert any('Verbotenes' in e for e in errors)


def test_validate_accepts_clean_template():
    data = _docx_bytes('<w:document>{{ projekt.aktenzeichen }} {% for f in beweisfragen %}{{ f.nr }}{% endfor %}</w:document>')
    assert tr.validate_template_bytes(data, 'tpl.docx') == []


def test_validate_rejects_empty():
    assert tr.validate_template_bytes(b'', 'x.docx') == ['Datei ist leer']


# ── Template-CRUD ──────────────────────────────────────────────────────────

@pytest.fixture
def db():
    repo_root = Path(__file__).resolve().parent.parent
    p = repo_root / 'data' / 'db' / 'pytest_template_957.sqlite'
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        p.unlink()
    gdb.ensure_db(p)
    yield p
    if p.exists():
        p.unlink()


def test_template_crud_and_default(db):
    t1 = gdb.save_template(db, name='Kanzlei A', gutachten_art='beide', datei_pfad='/x/a.docx', datei_sha256='aa')
    t2 = gdb.save_template(db, name='Kanzlei B', gutachten_art='beide', datei_pfad='/x/b.docx', datei_sha256='bb')
    assert len(gdb.list_templates(db)) == 2
    gdb.set_default_template(db, t1, 'beide')
    assert gdb.get_template(db, t1)['ist_default'] == 1
    # zweite als Default → erste verliert das Flag
    gdb.set_default_template(db, t2, 'beide')
    assert gdb.get_template(db, t1)['ist_default'] == 0
    assert gdb.get_template(db, t2)['ist_default'] == 1
    pfad = gdb.delete_template(db, t1)
    assert pfad == '/x/a.docx'
    assert gdb.get_template(db, t1) is None


def test_template_name_required(db):
    with pytest.raises(ValueError):
        gdb.save_template(db, name='', datei_pfad='/x/y.docx')
