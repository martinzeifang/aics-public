"""Freigabe-Rollen müssen freigeben können (#1754).

Der modulweite Guard leitet die benötigte Permission aus der HTTP-Methode ab:
jeder POST verlangt `<modul>:write`. Eine Freigabe ist ein POST — und eine
Freigabe-Rolle hat bewusst **kein** Schreibrecht. Damit konnte

* `cra_approver` (#1743) nichts freigeben — die Rollentrennung wäre wirkungslos,
* `geschaeftsfuehrer` seit #1128 **keinen Jahresbericht freigeben**, obwohl die
  Rolle genau dafür eingeführt wurde. Nur `dsb` war nicht betroffen, weil sie
  zusätzlich Schreibrecht hat; deshalb ist es nie aufgefallen.

Gefunden wurde das erst im Durchlauf über einen echten Browser: Die
Unit-Tests rufen die Datenbankschicht direkt auf und sehen den Guard nie.
"""
import pytest

CRA = '/api/cra'
KONF = '/api/cra-konformitaet'
FIRMA = 'pytest-firma-1754'
PROJ = 'pytest-cra-1754'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture(autouse=True)
def _demo_user_approver():
    """Stellt `approver@example.com` sicher.

    Die Demo-User werden idempotent beim ersten `users_ensure_db` gesetzt — in
    einer Datenbank, die aus der Zeit VOR dieser Rolle stammt, fehlt der
    Benutzer sonst, und der Test scheitert an einem Login statt an der Sache.
    """
    from server.auth import users_db as u
    u._ENSURED_PATHS.clear()
    u.ensure_db()
    yield


def _token(client, email, pw):
    r = client.post('/api/auth/login', json={'email': email, 'password': pw})
    assert r.status_code == 200, f'Login {email}: {r.json}'
    return {'Authorization': f"Bearer {r.json['access_token']}"}


@pytest.fixture
def projekt(client, auth_headers):
    client.delete(f'{CRA}/projekte/{PROJ}', headers=auth_headers)
    client.post(f'{CRA}/projekte', headers=auth_headers,
                json={'name': PROJ, 'unternehmen': FIRMA})
    yield PROJ
    client.delete(f'{CRA}/projekte/{PROJ}', headers=auth_headers)


def test_approver_erreicht_den_freigabe_endpunkt(client, projekt):
    """Der Kern: Der Guard darf eine Freigabe-Rolle nicht an der Tür abweisen.

    Erwartet wird **nicht** 200 — ohne Einreichung lehnt der Endpunkt mit 409 ab.
    Entscheidend ist, dass es **kein 403** mehr ist: Die Entscheidung gehört zum
    Endpunkt, nicht zur Methoden-Heuristik des Guards.
    """
    h = _token(client, 'approver@example.com', 'approver-password')
    r = client.post(f'{KONF}/projekte/{projekt}/konformitaet/freigeben',
                    headers=h, json={'release_version': '1.0.0'})
    assert r.status_code != 403, r.json
    assert r.status_code == 409, r.json


def test_editor_kommt_weiterhin_durch(client, projekt, auth_headers):
    """Der Fix darf niemandem etwas nehmen: Schreibrecht trägt weiter."""
    client.put(f'{KONF}/projekte/{projekt}/konformitaet', headers=auth_headers,
               json={'bewertungsweg': 'A', 'bewertung_abgeschlossen': True})
    h = _token(client, 'editor@example.com', 'editor-password')
    r = client.post(f'{KONF}/projekte/{projekt}/releases/1.0.0/einreichen', headers=h)
    assert r.status_code in (200, 409), r.json
    assert r.status_code != 403, 'der Editor hat Schreibrecht und muss durchkommen'


def test_approver_darf_trotzdem_nicht_schreiben(client, projekt):
    """Die Lockerung gilt nur für Sign-off-Pfade — sonst wäre sie ein Loch."""
    h = _token(client, 'approver@example.com', 'approver-password')
    r = client.put(f'{KONF}/projekte/{projekt}/konformitaet', headers=h,
                   json={'bewertungsweg': 'H'})
    assert r.status_code == 403, r.json

    r2 = client.post(f'{KONF}/projekte/{projekt}/releases/1.0.0/einreichen', headers=h)
    assert r2.status_code == 403, r2.json


def test_marker_decken_die_bekannten_signoff_pfade():
    """Namentlich, damit niemand einen Pfad umbenennt und die Rolle still
    wieder ausfällt — so ist #1128 zwei Jahre unbemerkt geblieben."""
    from server.middleware.authz import _SIGNOFF_MARKERS

    pfade = (
        '/api/cra-konformitaet/projekte/P/konformitaet/freigeben',
        '/api/cra-konformitaet/projekte/P/releases/1.0.0/zurueckweisen',
        '/api/cra-konformitaet/projekte/P/cra-ready/feststellen',
        '/api/cra-konformitaet/projekte/P/cra-ready/entziehen',
        '/api/dsgvo-jahresbericht/projekte/P/2026/freigeben',
        '/api/dsgvo-kontrollen/projekte/P/kontrollen/1/freigeben',
    )
    for pfad in pfade:
        assert any(m in pfad.lower() for m in _SIGNOFF_MARKERS), pfad


def test_geschaeftsfuehrer_hat_kein_schreibrecht_und_braucht_keines():
    """Die Rolle aus #1128 ist genau so gebaut: freigeben ohne bearbeiten.
    Dieser Test hält fest, warum der Guard sie durchlassen muss."""
    from server.models.permission import resolve_permissions

    gf = set(resolve_permissions(['geschaeftsfuehrer']))
    assert 'dsgvo:approve' in gf
    assert 'dsgvo:write' not in gf
