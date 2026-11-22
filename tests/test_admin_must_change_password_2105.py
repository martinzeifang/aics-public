"""#2105 — Admin setzt Start-Kennwort + erzwingt Änderung bei nächster Anmeldung."""
import pytest

AUTH = '/api/auth'
ADMIN = '/api/admin'
START_PW = 'StartPwd!2026ABC'
NEW_PW = 'NeuesPwd!2026XYZ'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


def _mk_user(client, auth_headers, email):
    r = client.post(f'{ADMIN}/users', headers=auth_headers,
                    json={'email': email, 'password': START_PW, 'roles': ['cra_editor']})
    assert r.status_code in (200, 201), r.get_json()
    return r.get_json()['id'] if isinstance(r.get_json(), dict) and 'id' in r.get_json() \
        else r.get_json().get('user', {}).get('id')


def test_force_change_flow(client, auth_headers):
    uid = _mk_user(client, auth_headers, 'force2105@test.com')
    assert uid
    # Admin erzwingt Kennwortänderung
    r = client.put(f'{ADMIN}/users/{uid}', headers=auth_headers,
                   json={'must_change_password': True})
    assert r.status_code == 200, r.get_json()
    assert r.get_json().get('must_change_password') is True

    # Login -> Flag ist im Login-Response sichtbar
    lr = client.post(f'{AUTH}/login', json={'email': 'force2105@test.com', 'password': START_PW})
    assert lr.status_code == 200, lr.get_json()
    assert lr.get_json()['user']['must_change_password'] is True
    old_token = lr.get_json()['access_token']
    H = {'Authorization': f'Bearer {old_token}'}

    # Selbst-Änderung mit falschem alten Kennwort -> 400
    bad = client.post(f'{AUTH}/password/change', headers=H,
                      json={'old_password': 'FalschesPwd!2026', 'new_password': NEW_PW})
    assert bad.status_code == 400

    # Korrekte Änderung -> 200, frisches Token, Flag gelöscht
    ok = client.post(f'{AUTH}/password/change', headers=H,
                     json={'old_password': START_PW, 'new_password': NEW_PW})
    assert ok.status_code == 200, ok.get_json()
    assert ok.get_json()['user']['must_change_password'] is False
    new_token = ok.get_json()['access_token']

    # Altes Token ist nach dem Wechsel entwertet (token_version)
    prof_old = client.get(f'{AUTH}/profile', headers=H)
    assert prof_old.status_code in (401, 422), prof_old.status_code
    # Neues Token funktioniert
    prof_new = client.get(f'{AUTH}/profile', headers={'Authorization': f'Bearer {new_token}'})
    assert prof_new.status_code == 200

    # Erneuter Login mit neuem Kennwort -> Flag bleibt gelöscht
    lr2 = client.post(f'{AUTH}/login', json={'email': 'force2105@test.com', 'password': NEW_PW})
    assert lr2.status_code == 200
    assert lr2.get_json()['user']['must_change_password'] is False


def test_same_password_rejected(client, auth_headers):
    _mk_user(client, auth_headers, "same2105@test.com")
    lr = client.post(f'{AUTH}/login', json={'email': 'same2105@test.com', 'password': START_PW})
    H = {'Authorization': f'Bearer {lr.get_json()["access_token"]}'}
    r = client.post(f'{AUTH}/password/change', headers=H,
                    json={'old_password': START_PW, 'new_password': START_PW})
    assert r.status_code == 400
