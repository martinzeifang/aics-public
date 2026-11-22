"""#2114 — KI-Assistenten (Recherche, Formulierung, Beweisfragen) + Projekt-Dokumente;
#2120 Selbstcheck je Prüfer + DIN EN 16775 statt ZPO beim Privatgutachten.

Leitplanke: alles bleibt Vorschlag; Prompts tragen die Sachverständigenvorgaben.
"""
import io
from pathlib import Path

import pytest

from gutachten import gerichts_db as gdb
from gutachten import ki_assistenten as kia
from gutachten import wizards as wiz

GUT = '/api/gutachten'


@pytest.fixture
def db():
    p = Path(__file__).resolve().parent.parent / 'data' / 'db' / 'pytest_ki_2114.sqlite'
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        p.unlink()
    gdb.ensure_db(p)
    yield p
    if p.exists():
        p.unlink()


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['gutachten']
    yield
    cur.state, cur.modules = prev[0], prev[1]


# ── Prompt-Bauer (reine Funktionen) ─────────────────────────────────────────

def test_recherche_prompt_art_abhaengig_und_quellen():
    r = kia.build_recherche_prompt(
        "SHA-256 Integrität Beweissicherung",
        {"gutachten_art": "privat", "name": "P"},
        [{"id": 1, "dateiname": "handbuch.pdf", "auszug": "SHA-256 bei Akquisition."}],
        [{"titel": "ISO/IEC 27037", "soll_kurz": "Chain of Custody"}])
    assert "handbuch.pdf" in r["prompt"]
    assert "amtliche" in r["prompt"] or "lizenzierte" in r["prompt"]
    assert "Erfinde keine" in r["prompt"]
    assert "§ 407a" not in r["prompt"]  # privat ohne ZPO
    assert len(r["quellen"]) == 2
    g = kia.build_recherche_prompt("x", {"gutachten_art": "gericht", "name": "G"}, [], [])
    assert "§ 407a" in g["prompt"]


def test_formulierung_prompt_wuerdigung_sperrt_recht():
    p = kia.build_formulierung_prompt("Server ungepatcht", "wuerdigung",
                                      {"gutachten_art": "gericht", "name": "G"})
    assert "informationstechnischer Sicht" in p
    assert "keine neuen" in p.lower() and "rechtlichen begriffe" in p.lower()


def test_beweisfragen_prompt_und_parser():
    p = kia.build_beweisfragen_prompt("Die DB war kompromittiert.",
                                      {"gutachten_art": "gericht", "name": "G"})
    assert "Beweisfragen" in p and "Keine rechtlichen Fragen" in p
    assert kia.parse_beweisfragen('```json\n{"fragen":["A","B"]}\n```') == ["A", "B"]
    assert kia.parse_beweisfragen('{"fragen":["Nur A"') == ["Nur A"]  # abgeschnitten
    assert kia.parse_beweisfragen("Müll") == []


# ── Projekt-Dokumente (DB) ──────────────────────────────────────────────────

def test_dokumente_crud_und_suche(db):
    gdb.save_gerichts_projekt(db, name='D1', gutachten_art='privat',
                              auftraggeber='X', auftrags_art='Schaden-Gutachten', sv_name='Dr')
    did = gdb.save_dokument(db, projekt_name='D1', dateiname='norm.txt', mime='text/plain',
                            text='Die Beweissicherung erfolgt mit SHA-256 Hashwert.')
    lst = gdb.list_dokumente(db, 'D1')
    assert len(lst) == 1 and lst[0]['zeichen'] > 0 and 'text' not in lst[0]
    full = gdb.get_dokument(db, did, mit_text=True)
    assert 'SHA-256' in full['text']
    treffer = kia.waehle_dokument_treffer('SHA-256 Hashwert',
                                          gdb.list_dokumente(db, 'D1', mit_text=True))
    assert treffer and treffer[0]['dateiname'] == 'norm.txt'
    gdb.delete_dokument(db, did)
    assert gdb.list_dokumente(db, 'D1') == []


# ── #2120 Selbstcheck je Prüfer + Art-Abhängigkeit (DB) ─────────────────────

@pytest.mark.parametrize('art,zpo_erlaubt', [('privat', False), ('gericht', True)])
def test_selbstcheck_art_und_pruefer(db, art, zpo_erlaubt):
    kw = dict(name=f'SC_{art}', gutachten_art=art, sv_name='Dr')
    kw.update(dict(auftraggeber='X', auftrags_art='Schaden-Gutachten') if art == 'privat'
              else dict(gericht='LG', aktenzeichen='1/26'))
    gdb.save_gerichts_projekt(db, **kw)
    pid = gdb.save_pruefer(db, projekt_name=f'SC_{art}', name='Dr', rolle='hauptgutachter')
    wiz.selbstcheck(db, f'SC_{art}',
                    {'wirtschaftlich': 'nein', 'familiaer': 'nein', 'vorbefassung': 'nein',
                     'social_media': 'nein', 'kompetenz': 'ja'}, pruefer_id=pid)
    ev = [e for e in gdb.list_verfahrensereignisse(db, f'SC_{art}')
          if e['ereignis_typ'] == 'selbstcheck'][-1]
    txt = ev['beschreibung']
    assert ('§ 406 ZPO' in txt or '§ 407' in txt) == zpo_erlaubt
    assert 'DIN EN 16775' in txt
    sp = gdb.list_selbstpruefung(db, f'SC_{art}')
    assert len(sp) == 1 and sp[0]['status'] == 'bestanden'


# ── API-Ebene: Prompt-Endpunkte + Dokument-Upload ───────────────────────────

def _mk(client, auth_headers, name, art='gericht'):
    body = {'name': name, 'gutachten_art': art, 'sv_name': 'Dr'}
    body.update({'gericht': 'LG', 'aktenzeichen': '1/26'} if art == 'gericht'
                else {'auftraggeber': 'X', 'auftrags_art': 'Schaden-Gutachten'})
    r = client.post(f'{GUT}/gerichts', json=body, headers=auth_headers)
    assert r.status_code == 201, r.json


def test_api_ki_prompts(client, auth_headers):
    _mk(client, auth_headers, 'KIAPI')
    r = client.post(f'{GUT}/gerichts/KIAPI/ki/recherche/prompt',
                    json={'frage': 'Wie wird Integrität gesichert?'}, headers=auth_headers)
    assert r.status_code == 200 and 'prompt' in r.json and 'quellen' in r.json
    r2 = client.post(f'{GUT}/gerichts/KIAPI/ki/formulierung/prompt',
                     json={'stichworte': 'Patch fehlt', 'feld': 'wuerdigung'}, headers=auth_headers)
    assert r2.status_code == 200 and 'informationstechnischer Sicht' in r2.json['prompt']
    r3 = client.post(f'{GUT}/gerichts/KIAPI/ki/beweisfragen/prompt',
                     json={'fliesstext': 'Die Datenbank war offen erreichbar.'}, headers=auth_headers)
    assert r3.status_code == 200 and 'Beweisfragen' in r3.json['prompt']
    r4 = client.post(f'{GUT}/gerichts/KIAPI/ki/beweisfragen/parse',
                     json={'response': '{"fragen":["War die DB offen?"]}'}, headers=auth_headers)
    assert r4.status_code == 200 and r4.json['fragen'] == ['War die DB offen?']


def test_api_dokument_upload_list_delete(client, auth_headers):
    _mk(client, auth_headers, 'DOKAPI')
    datei = (io.BytesIO('Die Beweissicherung nutzt SHA-256.'.encode('utf-8')), 'norm.txt')
    r = client.post(f'{GUT}/gerichts/DOKAPI/dokumente',
                    data={'file': datei}, content_type='multipart/form-data',
                    headers=auth_headers)
    assert r.status_code == 201, r.json
    assert r.json['zeichen'] > 0 and r.json['kein_text'] is False
    lst = client.get(f'{GUT}/gerichts/DOKAPI/dokumente', headers=auth_headers).json['dokumente']
    assert len(lst) == 1
    did = lst[0]['id']
    dl = client.get(f'{GUT}/gerichts/dokumente/{did}/download', headers=auth_headers)
    assert dl.status_code == 200
    assert client.delete(f'{GUT}/gerichts/dokumente/{did}', headers=auth_headers).status_code == 204
