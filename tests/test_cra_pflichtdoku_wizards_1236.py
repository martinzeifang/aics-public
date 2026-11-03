"""Sprint #28 / Milestone #30 — CRA Pflichtdokumente-Ausbau (#1236–#1239).

Deckt ab:
- #1236 Technische Dokumentation (Annex VII): Checkliste + Querverweis-Bausteine.
- #1237 EU-Konformitätserklärung-Wizard (Annex V, Art. 28).
- #1238 Benutzerinformationen (Annex II): Checkliste.
- #1239 SBOM-Begleitdokument-Wizard (Annex I Teil II).

Wizard-Funktionen werden DB-frei getestet; API-Round-Trips über echte CRA-DB
(license-fixture + Projekt anlegen/löschen, Muster wie test_cra_konformitaet_1201).
"""
import pytest

CRA = '/api/cra'
DOKU = '/api/cra-dokumente'
FIRMA = 'pytest-firma-1236'
PROJ = 'pytest-cra-1236'


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
                      'produktklasse': 'important_ii',
                      'beschreibung': 'Eine Firewall-Appliance'})
    yield PROJ
    client.delete(f'{CRA}/projekte/{PROJ}', headers=auth_headers)


# ── #1236: Annex-VII-Checkliste + Querverweis-Bausteine ──────────────────────

def test_annex_vii_checkliste_inhalte():
    from shared.documents.catalog import get_checklist
    ids = {c['id'] for c in get_checklist('cra', 'technische_doku_annex_vii')}
    # Mindestinhalte aus Annex VII (inkl. neuer Testberichte).
    for required in ('beschreibung', 'design_entwicklung', 'sbom', 'risikobewertung',
                     'normen', 'schwachstellenbehandlung', 'support_zeitraum',
                     'testberichte', 'konformitaetserklaerung_ref'):
        assert required in ids, f'Annex-VII-Pflichtinhalt fehlt: {required}'


def test_annex_vii_bausteine():
    from shared.documents.catalog import get_bausteine
    b = get_bausteine('cra', 'technische_doku_annex_vii')
    ziele = {x['ziel'] for x in b}
    assert {'sbom', 'threatmodel'} <= ziele  # C1-SBOM + C5-Threat-Model
    # Andere Dokumenttypen haben keine Bausteine.
    assert get_bausteine('cra', 'konformitaetserklaerung') == []


def test_checklist_api_liefert_bausteine(client, auth_headers, projekt):
    # Tech-Doku-Dokument anlegen, Checkliste + Bausteine abrufen.
    r = client.post(f'{DOKU}/{projekt}', headers=auth_headers,
                    json={'doc_type': 'technische_doku_annex_vii',
                          'content_html': '<p>x</p>'})
    assert r.status_code == 201
    did = r.get_json()['id']
    cl = client.get(f'{DOKU}/{projekt}/{did}/checklist', headers=auth_headers).get_json()
    assert any(i['id'] == 'testberichte' for i in cl['items'])
    assert any(x['ziel'] == 'sbom' for x in cl.get('bausteine', []))
    client.delete(f'{DOKU}/{projekt}/{did}', headers=auth_headers)


# ── #1238: Annex-II-Checkliste ───────────────────────────────────────────────

def test_annex_ii_checkliste_inhalte():
    from shared.documents.catalog import get_checklist
    ids = {c['id'] for c in get_checklist('cra', 'benutzeranleitung_annex_ii')}
    for required in ('hersteller', 'kontakt_schwachstellen', 'support_ende',
                     'inbetriebnahme', 'update_handhabung', 'ausserbetriebnahme'):
        assert required in ids, f'Annex-II-Pflichtinhalt fehlt: {required}'


# ── #1237: EU-Konformitätserklärung-Wizard ───────────────────────────────────

def test_eu_doc_prompt_enthaelt_annex_v_felder():
    from cra.ai_wizards import build_konformitaetserklaerung_prompt
    p = {'name': 'FW', 'unternehmen': 'ACME', 'produktklasse': 'important_ii'}
    konf = {'bewertungsweg': 'B+C', 'nb_kennnummer': '0123'}
    prompt = build_konformitaetserklaerung_prompt(p, konf, ['EN 18031'])
    assert 'Annex V' in prompt and '2024/2847' in prompt
    assert 'ACME' in prompt and 'EN 18031' in prompt
    assert '0123' in prompt  # NB-Kennnummer aus Konformitäts-Record


def test_eu_doc_parse_plausibilitaet_nb_pflicht():
    """#1885: Die NB-Pflicht wird weiter gemeldet — der **Hinweis** dazu nicht.

    Bis v8.2.2 rechnete ``parse_konformitaetserklaerung_response`` vier eigene
    Hinweise aus der **KI-Antwort**: fehlender Herstellername, fehlende
    Produktidentifikation, keine Normen, fehlende NB-Kennnummer. Drei
    wiederholten ``doc_export.fehlende_pflichtfelder``, der vierte (Nr. 6) war
    sogar falsch — ``ANHANG_V`` führt Nr. 6 bewusst nicht als Pflichtangabe.

    Entscheidend ist, **woraus** sie gerechnet wurden: aus dem, was das Modell
    zurückschickt, nicht aus der Akte. Der Hinweis konnte also „Kennnummer
    fehlt" sagen, während sie im Konformitäts-Record stand — und umgekehrt. Die
    Kennnummer ist seit #1887 ohnehin ein **übernommenes** Feld (aus der
    Bewertung) und keines, das die KI setzen darf; was sie dazu liefert, wird
    verworfen.

    Geprüft wird die Pflicht weiter, nur an der richtigen Stelle:
    ``fehlende_pflichtfelder`` gegen den Datensatz, und das Ausstellen bricht
    ohne Nr. 7 ab (#1814). ``notified_body_pflicht`` in der Antwort bleibt
    unverändert — daran hängt die Anzeige.
    """
    from cra.ai_wizards import parse_konformitaetserklaerung_response
    from cra.doc_export import fehlende_pflichtfelder

    raw = '{"titel": "DoC", "doc_text": "Volltext", "produkt_identifikation": "FW v1", ' \
          '"angewandte_normen": ["EN 18031"], "notified_body_kennnummer": ""}'
    parsed = parse_konformitaetserklaerung_response(
        raw, {'unternehmen': 'ACME', 'produktklasse': 'critical'})
    assert parsed['doc_text'] == 'Volltext'
    assert parsed['notified_body_pflicht'] is True

    # Die Pflicht selbst: Ohne NB-Angaben ist die Erklärung unvollständig.
    fehlend = fehlende_pflichtfelder({}, nb_pflichtig=True)
    assert any(f['nr'] == 7 for f in fehlend)


def test_eu_doc_parse_default_klasse_keine_nb_pflicht():
    from cra.ai_wizards import parse_konformitaetserklaerung_response
    raw = '{"doc_text": "x", "produkt_identifikation": "P", "angewandte_normen": ["N"]}'
    parsed = parse_konformitaetserklaerung_response(
        raw, {'unternehmen': 'ACME', 'produktklasse': 'default'})
    assert parsed['notified_body_pflicht'] is False
    assert not any('notifizierten Stelle' in h for h in parsed['plausibilitaet_hinweise'])


#: Die Pflichtangaben, die die KI **nicht** setzen darf (``KI_FELDER`` sind
#: nur produkt_typ, zusatzangaben, gegenstand). Ohne sie sperrt der Assistent
#: seit #1901 — in der Oberfläche füllt sie „⚙ Aus den Quellen füllen".
_PFLICHT_OHNE_KI = {
    'produkt_name': 'Testprodukt', 'produkt_charge': '1.0',
    'hersteller': 'ACME GmbH', 'hersteller_adresse': 'Weg 1, 12345 Ort',
    'verantwortungssatz': 'Alleinverantwortung des Herstellers.',
    'konformitaetsaussage': 'Entspricht der Verordnung (EU) 2024/2847.',
    'ort': 'Ort', 'datum': '2026-01-01',
    'unterzeichner_name': 'A. Person', 'unterzeichner_funktion': 'GF',
    # Nr. 7 gilt „soweit zutreffend" — bei einem Weg mit notifizierter Stelle
    # zutreffend, und das Fixture-Projekt verlangt so einen Weg (#1759).
    'nb_name': 'Prüfstelle GmbH', 'nb_kennnummer': '0123',
    'nb_zertifikat': 'ZERT-1',
}


def test_eu_doc_prompt_sperrt_bei_luecken(client, auth_headers, projekt):
    """#1901: Kein Lauf, solange die Akte ihn nicht trägt.

    Aus dem Betrieb kam ein Entwurf zurück, dessen Inhalt „Fehlende
    Pflichtfelder" war — das Modell las vor, was die Anwendung schon wusste,
    und kostete dafür einen Lauf. Was es nicht erfinden kann, soll es nicht
    benennen müssen.
    """
    r = client.get(f'{CRA}/projekte/{projekt}/wizards/eu-doc/prompt',
                   headers=auth_headers)
    assert r.status_code == 409, r.get_json()
    body = r.get_json()
    assert body['code'] == 'erklaerung-nicht-bereit'
    assert body['fehlend'], body
    # Die Vollständigkeitsanzeige fällt dasselbe Urteil — aus derselben
    # Funktion, nicht aus einer zweiten Regel (#1703/S9).
    v = client.get(f'{CRA}/projekte/{projekt}/wizards/eu-doc/vollstaendigkeit',
                   headers=auth_headers)
    assert v.status_code == 200 and v.get_json()['bereit'] is False


def test_eu_doc_api_prompt_parse(client, auth_headers, projekt):
    # Erst die Angaben, die die KI nicht setzen darf — danach läuft der
    # Assistent (#1901).
    KONF = '/api/cra-konformitaet'
    # `save_doc` braucht einen Konformitäts-Record. Die Produktklasse des
    # Fixture-Projekts lässt Modul A nicht zu (#1759) — also B+C, und damit
    # sind die drei Nr.-7-Angaben ebenfalls Pflicht.
    rk = client.put(f'{KONF}/projekte/{projekt}/konformitaet', headers=auth_headers,
                    json={'bewertungsweg': 'B+C', 'nb_kennnummer': '0123',
                          'ce_status': 'in_bewertung'})
    assert rk.status_code == 200, rk.get_json()
    sp = client.put(f'{KONF}/projekte/{projekt}/konformitaet/doc',
                    headers=auth_headers, json={'doc': _PFLICHT_OHNE_KI})
    assert sp.status_code == 200, sp.get_json()
    pr = client.get(f'{CRA}/projekte/{projekt}/wizards/eu-doc/prompt', headers=auth_headers)
    assert pr.status_code == 200, pr.get_json()
    assert 'Annex V' in pr.get_json()['prompt']
    raw = '{"doc_text": "DoC-Text", "produkt_identifikation": "FW", ' \
          '"angewandte_normen": ["EN 18031"], "notified_body_kennnummer": "0123"}'
    pa = client.post(f'{CRA}/projekte/{projekt}/wizards/eu-doc/parse',
                     headers=auth_headers, json={'response': raw})
    assert pa.status_code == 200
    body = pa.get_json()
    assert body['doc_text'] == 'DoC-Text' and body['applied'] is False
    assert 'plausibilitaet_hinweise' in body


def test_eu_doc_suggested_assistant_gesetzt():
    from shared.documents.catalog import get_doc_spec
    spec = get_doc_spec('cra', 'konformitaetserklaerung')
    assert spec['suggested_assistant'] == 'eu-doc'


# ── #1239: SBOM-Begleitdokument-Wizard ───────────────────────────────────────

def test_sbom_doc_prompt_mit_sbom_daten():
    from cra.ai_wizards import build_sbom_begleitdoc_prompt
    sboms = [{'release_version': '1.0', 'sbom_format': 'cyclonedx',
              'komponenten_count': 42, 'quelle': 'ci', 'lizenzen': ['MIT', 'Apache-2.0']}]
    prompt = build_sbom_begleitdoc_prompt({'name': 'P', 'unternehmen': 'ACME'}, sboms)
    assert 'Annex I Teil II' in prompt and 'CYCLONEDX' in prompt
    assert '42 Komponenten' in prompt and 'MIT' in prompt


def test_sbom_doc_prompt_ohne_sbom_daten():
    from cra.ai_wizards import build_sbom_begleitdoc_prompt
    prompt = build_sbom_begleitdoc_prompt({'name': 'P', 'unternehmen': 'ACME'}, [])
    # Kein harter Fehler, Hinweis auf manuelle Erfassung.
    assert 'Noch kein SBOM' in prompt


def test_sbom_doc_parse():
    from cra.ai_wizards import parse_sbom_begleitdoc_response
    raw = '{"titel": "SBOM-Doc", "doc_text": "Volltext", "sbom_format": "CycloneDX", ' \
          '"geltungsbereich": "alle Releases", "aktualisierungszyklus": "je Build"}'
    parsed = parse_sbom_begleitdoc_response(raw)
    assert parsed['doc_text'] == 'Volltext' and parsed['sbom_format'] == 'CycloneDX'
    assert parsed['aktualisierungszyklus'] == 'je Build'


def test_sbom_doc_api_prompt_parse(client, auth_headers, projekt):
    pr = client.get(f'{CRA}/projekte/{projekt}/wizards/sbom-doc/prompt', headers=auth_headers)
    assert pr.status_code == 200 and 'Annex I Teil II' in pr.get_json()['prompt']
    raw = '{"doc_text": "SBOM-Begleit", "sbom_format": "SPDX"}'
    pa = client.post(f'{CRA}/projekte/{projekt}/wizards/sbom-doc/parse',
                     headers=auth_headers, json={'response': raw})
    assert pa.status_code == 200
    body = pa.get_json()
    assert body['doc_text'] == 'SBOM-Begleit' and body['applied'] is False


def test_sbom_doc_suggested_assistant_gesetzt():
    from shared.documents.catalog import get_doc_spec
    spec = get_doc_spec('cra', 'sbom_begleitdoc')
    assert spec['suggested_assistant'] == 'sbom-doc'


# ── #1237/#1239: Wizard-Ergebnis → editier-/exportierbares Dokument ──────────

def test_wizard_doc_round_trip_export(client, auth_headers, projekt):
    """Annex-V-DoC als managed_doc speichern, freigeben, exportieren (DOCX)."""
    r = client.post(f'{DOKU}/{projekt}', headers=auth_headers,
                    json={'doc_type': 'konformitaetserklaerung', 'source': 'assistant',
                          'assistant_key': 'eu-doc',
                          'content_html': '<h1>EU-Konformitätserklärung</h1>'})
    assert r.status_code == 201
    did = r.get_json()['id']
    doc = client.get(f'{DOKU}/{projekt}/{did}', headers=auth_headers).get_json()
    assert doc['source'] == 'assistent' and doc['assistant_key'] == 'eu-doc'
    st = client.post(f'{DOKU}/{projekt}/{did}/status',
                     json={'status': 'freigegeben'}, headers=auth_headers)
    assert st.status_code == 200 and st.get_json()['dokument']['sha256']
    dx = client.post(f'{DOKU}/{projekt}/{did}/export?format=docx', headers=auth_headers)
    assert dx.status_code == 200 and dx.data[:2] == b'PK'
    client.delete(f'{DOKU}/{projekt}/{did}', headers=auth_headers)
