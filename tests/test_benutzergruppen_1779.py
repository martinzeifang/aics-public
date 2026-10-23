"""Benutzergruppen mit Berechtigungen (#1779).

Rechte hingen bis v8.0.3 an jedem Konto einzeln. Die Gruppe ist die Stelle, an
der eine Rechte-Entscheidung **einmal** steht. Vier Zusagen tragen das, und
jede hat hier einen Test:

1. **Additiv.** Gruppenrechte kommen zu den eigenen hinzu; Whitelists
   (``allowed_modules``/``allowed_firmen``) bleiben am Konto — sie sind
   Beschränkungen und müssten sich schneiden, nicht vereinigen.
2. **Im Token.** Berechtigungen stehen im JWT. Wer die Gruppe nicht bei der
   Anmeldung auflöst, hat sie nirgends.
3. **Sofort wirksam.** Eine Rechteänderung an der Gruppe erhöht die
   ``token_version`` der Mitglieder. Ein entzogenes Recht, das bis zum Ablauf
   des Tokens weitergilt, ist in einem Nachweiswerkzeug schlechter als ein
   Logout.
4. **Keine Rückschreibung.** Die Gruppe schreibt nichts in das Konto — sonst
   blieben ihre Rollen beim Verlassen der Gruppe stehen, und niemand könnte
   sagen, woher ein Recht kam.

Die Gruppentabellen liegen im ``users``-Schema (App-State) und werden von der
Per-Test-Isolation **nicht** geleert; dieses Modul räumt deshalb selbst auf.
"""
from __future__ import annotations

import uuid

import pytest

from server.auth import groups_db as gdb
from server.auth import users_db as udb


PREFIX = "pytest-1779-"


@pytest.fixture(autouse=True)
def _aufraeumen(pg):
    """Eigene Gruppen vor und nach dem Test entfernen."""
    def _weg():
        try:
            for g in gdb.list_groups():
                if str(g.get("name", "")).startswith(PREFIX):
                    gdb.delete_group(g["id"])
        except Exception:  # noqa: BLE001
            pass
    _weg()
    yield
    _weg()


@pytest.fixture
def gruppe():
    def _neu(**felder):
        felder.setdefault("name", f"{PREFIX}{uuid.uuid4().hex[:8]}")
        return gdb.create_group(felder.pop("name"), **felder)
    return _neu


@pytest.fixture
def konto():
    def _neu(**felder):
        felder.setdefault("email", f"{PREFIX}{uuid.uuid4().hex[:8]}@test.local")
        felder.setdefault("password", "Str0ng-Passw0rd!x")
        felder.setdefault("roles", [])
        return udb.create_user(**felder)
    return _neu


@pytest.fixture
def rest(pg, request):
    """Testclient + Admin-Header, erst nach dem Postgres-Check (Muster #1741)."""
    return request.getfixturevalue("client"), request.getfixturevalue("auth_headers")


# ──────────────────────────────────────────────────────────────────────────────
# 1 · Datenschicht
# ──────────────────────────────────────────────────────────────────────────────
def test_gruppe_anlegen_und_lesen(gruppe):
    g = gruppe(beschreibung="CRA-Team", roles=["cra_editor"],
               extra_permissions=["admin:audit"])
    assert g["roles"] == ["cra_editor"]
    assert g["extra_permissions"] == ["admin:audit"]
    assert g["mitglieder"] == [] and g["mitglieder_count"] == 0

    wieder = gdb.get_group(g["id"])
    assert wieder is not None and wieder["beschreibung"] == "CRA-Team"


def test_mitgliedschaft_ist_idempotent(gruppe, konto):
    g, u = gruppe(roles=["cra_viewer"]), konto()
    gdb.add_member(g["id"], u["id"])
    gdb.add_member(g["id"], u["id"])
    assert gdb.members(g["id"]) == [u["id"]]

    assert gdb.remove_member(g["id"], u["id"]) is True
    assert gdb.members(g["id"]) == []
    # Zweites Entfernen ändert nichts und meldet das.
    assert gdb.remove_member(g["id"], u["id"]) is False


def test_rechte_werden_vereinigt_nicht_ersetzt(gruppe, konto):
    g = gruppe(roles=["cra_viewer"], extra_permissions=["admin:audit"])
    u = konto(roles=["nis2_editor"], extra_permissions=["admin:config"])
    gdb.add_member(g["id"], u["id"])

    eff = gdb.effektiv(udb.get_user_by_id(u["id"]))
    assert set(eff["roles"]) == {"nis2_editor", "cra_viewer"}
    assert set(eff["extra_permissions"]) == {"admin:config", "admin:audit"}
    # Und die Herkunft bleibt unterscheidbar.
    assert eff["eigene_rollen"] == ["nis2_editor"]
    assert [x["name"] for x in eff["gruppen"]] == [g["name"]]


def test_effektiv_veraendert_das_konto_nicht(gruppe, konto):
    """Die Rückschreibung ist die Falle: Gruppenrollen würden eigene Rollen."""
    g, u = gruppe(roles=["cra_editor"]), konto(roles=[])
    gdb.add_member(g["id"], u["id"])

    gdb.effektiv(udb.get_user_by_id(u["id"]))
    assert udb.get_user_by_id(u["id"])["roles"] == []


def test_stillgelegte_gruppe_gibt_keine_rechte(gruppe, konto):
    g, u = gruppe(roles=["cra_editor"]), konto()
    gdb.add_member(g["id"], u["id"])
    gdb.update_group(g["id"], active=False)

    eff = gdb.effektiv(udb.get_user_by_id(u["id"]))
    assert eff["roles"] == []
    assert eff["gruppen"] == []
    # Die Mitgliederliste bleibt aber lesbar — abschalten ist nicht löschen.
    assert gdb.members(g["id"]) == [u["id"]]


def test_gruppen_fuer_viele_konten_in_einer_abfrage(gruppe, konto):
    g = gruppe(roles=["cra_viewer"])
    a, b = konto(), konto()
    gdb.add_member(g["id"], a["id"])

    karte = gdb.groups_for_users([a["id"], b["id"]])
    assert [x["name"] for x in karte[a["id"]]] == [g["name"]]
    assert karte[b["id"]] == []


def test_set_groups_for_user_meldet_die_aenderungen(gruppe, konto):
    a, b = gruppe(), gruppe()
    u = konto()
    assert gdb.set_groups_for_user(u["id"], [a["id"]]) == [a["id"]]
    # Umhängen berührt beide Gruppen.
    assert set(gdb.set_groups_for_user(u["id"], [b["id"]])) == {a["id"], b["id"]}
    # Gleicher Stand → keine Änderung.
    assert gdb.set_groups_for_user(u["id"], [b["id"]]) == []


def test_gruppe_loeschen_entfernt_mitgliedschaften_nicht_konten(gruppe, konto):
    g, u = gruppe(roles=["cra_editor"]), konto()
    gdb.add_member(g["id"], u["id"])
    assert gdb.delete_group(g["id"]) is True

    assert udb.get_user_by_id(u["id"]) is not None
    assert gdb.groups_for_user(u["id"]) == []


# ──────────────────────────────────────────────────────────────────────────────
# 2 · Das Token — ohne diesen Schritt hat die Gruppe keine Wirkung
# ──────────────────────────────────────────────────────────────────────────────
def test_login_token_traegt_die_gruppenrechte(gruppe, konto, app):
    from server.api.auth import build_login_response
    from server.models.permission import Permission

    g = gruppe(roles=["cra_editor"])
    u = konto(roles=[])
    gdb.add_member(g["id"], u["id"])

    with app.app_context():
        antwort = build_login_response(udb.get_user_by_id(u["id"]))
    assert Permission.CRA_WRITE.value in antwort["user"]["permissions"]
    assert "cra" in antwort["user"]["allowed_modules"]
    assert g["name"] in antwort["user"]["gruppen"]


def test_ohne_gruppe_bleibt_das_konto_ohne_rechte(konto, app):
    """Gegenprobe: Die Rechte kommen wirklich aus der Gruppe."""
    from server.api.auth import build_login_response

    u = konto(roles=[])
    with app.app_context():
        antwort = build_login_response(udb.get_user_by_id(u["id"]))
    assert antwort["user"]["permissions"] == []


def test_admin_rolle_aus_der_gruppe_hebt_die_firmen_whitelist(gruppe, konto, app):
    """``allowed_firmen`` folgt der Admin-Erkennung — die muss die Gruppe sehen."""
    from server.api.auth import build_login_response
    import jwt as _jwt

    g = gruppe(roles=["admin"])
    u = konto(roles=[], allowed_firmen=[1])
    gdb.add_member(g["id"], u["id"])

    with app.app_context():
        antwort = build_login_response(udb.get_user_by_id(u["id"]))
        claims = _jwt.decode(antwort["access_token"],
                             app.config["JWT_SECRET_KEY"], algorithms=["HS256"])
    assert claims["allowed_firmen"] is None


# ──────────────────────────────────────────────────────────────────────────────
# 3 · Sofort wirksam
# ──────────────────────────────────────────────────────────────────────────────
def test_rechteaenderung_an_der_gruppe_meldet_mitglieder_ab(gruppe, konto, rest):
    client, headers = rest
    g = gruppe(roles=["cra_viewer"])
    u = konto()
    gdb.add_member(g["id"], u["id"])
    vorher = udb.get_token_version(u["id"])

    res = client.put(f"/api/admin/groups/{g['id']}",
                     json={"roles": ["cra_editor"]}, headers=headers)
    assert res.status_code == 200, res.get_data(as_text=True)
    assert res.get_json()["abgemeldete_mitglieder"] == 1
    assert udb.get_token_version(u["id"]) > vorher


def test_namensaenderung_meldet_niemanden_ab(gruppe, konto, rest):
    """Nur Rechte wirken auf Tokens — ein neuer Name ist keine Rechteänderung."""
    client, headers = rest
    g = gruppe(roles=["cra_viewer"])
    u = konto()
    gdb.add_member(g["id"], u["id"])
    vorher = udb.get_token_version(u["id"])

    res = client.put(f"/api/admin/groups/{g['id']}",
                     json={"beschreibung": "neu"}, headers=headers)
    assert res.status_code == 200
    assert udb.get_token_version(u["id"]) == vorher


def test_gruppe_loeschen_meldet_mitglieder_ab(gruppe, konto, rest):
    client, headers = rest
    g = gruppe(roles=["cra_editor"])
    u = konto()
    gdb.add_member(g["id"], u["id"])
    vorher = udb.get_token_version(u["id"])

    res = client.delete(f"/api/admin/groups/{g['id']}", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["abgemeldete_mitglieder"] == 1
    assert udb.get_token_version(u["id"]) > vorher


# ──────────────────────────────────────────────────────────────────────────────
# 4 · REST
# ──────────────────────────────────────────────────────────────────────────────
def test_crud_ueber_die_api(rest):
    client, headers = rest
    name = f"{PREFIX}{uuid.uuid4().hex[:8]}"

    res = client.post("/api/admin/groups",
                      json={"name": name, "roles": ["cra_viewer"],
                            "beschreibung": "Lesezugriff CRA"}, headers=headers)
    assert res.status_code == 201, res.get_data(as_text=True)
    gid = res.get_json()["id"]

    assert any(g["id"] == gid for g in
               client.get("/api/admin/groups", headers=headers).get_json())

    res = client.get(f"/api/admin/groups/{gid}", headers=headers)
    assert res.status_code == 200 and res.get_json()["name"] == name

    assert client.delete(f"/api/admin/groups/{gid}",
                         headers=headers).status_code == 200
    assert client.get(f"/api/admin/groups/{gid}",
                      headers=headers).status_code == 404


def test_doppelter_name_wird_abgelehnt(gruppe, rest):
    client, headers = rest
    g = gruppe()
    res = client.post("/api/admin/groups", json={"name": g["name"]}, headers=headers)
    assert res.status_code == 409


def test_unbekannte_rolle_wird_abgelehnt(rest):
    """``resolve_permissions`` überspringt unbekannte Rollen stillschweigend.

    Eine vertippte Rolle wäre damit eine Gruppe, die Rechte verspricht und
    keine gibt.
    """
    client, headers = rest
    res = client.post("/api/admin/groups",
                      json={"name": f"{PREFIX}tippfehler", "roles": ["cra_editr"]},
                      headers=headers)
    assert res.status_code == 400
    assert "cra_editr" in res.get_json()["error"]


def test_unbekannte_berechtigung_wird_abgelehnt(rest):
    client, headers = rest
    res = client.post("/api/admin/groups",
                      json={"name": f"{PREFIX}perm", "extra_permissions": ["cra:alles"]},
                      headers=headers)
    assert res.status_code == 400


def test_mitglied_ueber_die_api_hinzufuegen_und_entfernen(gruppe, konto, rest):
    client, headers = rest
    g, u = gruppe(roles=["cra_viewer"]), konto()

    res = client.post(f"/api/admin/groups/{g['id']}/members",
                      json={"user_id": u["id"]}, headers=headers)
    assert res.status_code == 200
    assert res.get_json()["mitglieder"] == [u["id"]]

    res = client.delete(f"/api/admin/groups/{g['id']}/members/{u['id']}",
                        headers=headers)
    assert res.status_code == 200 and res.get_json()["mitglieder"] == []


def test_unbekanntes_konto_wird_nicht_aufgenommen(gruppe, rest):
    client, headers = rest
    g = gruppe()
    res = client.post(f"/api/admin/groups/{g['id']}/members",
                      json={"user_id": "gibt-es-nicht"}, headers=headers)
    assert res.status_code == 404


def test_benutzerliste_zeigt_gruppen_und_effektive_rechte(gruppe, konto, rest):
    client, headers = rest
    g = gruppe(roles=["cra_editor"])
    u = konto(roles=[])
    gdb.add_member(g["id"], u["id"])

    daten = client.get("/api/admin/users", headers=headers).get_json()
    eintrag = next(x for x in daten if x["id"] == u["id"])
    assert [x["name"] for x in eintrag["gruppen"]] == [g["name"]]
    # Eigene Rollen bleiben leer — die Gruppe schreibt nicht ins Konto.
    assert eintrag["roles"] == []
    assert "cra:write" in eintrag["effective_permissions"]
    assert "cra" in eintrag["effective_modules"]


def test_benutzer_put_speichert_keine_gruppenrolle_als_eigene(gruppe, konto, rest):
    """Der Weg, auf dem Gruppenrechte am Konto kleben blieben.

    Das Formular sendet zurück, was es gelesen hat — liest es die Vereinigung,
    speichert es sie als eigene Rollen.
    """
    client, headers = rest
    g = gruppe(roles=["cra_editor"])
    u = konto(roles=["nis2_editor"])
    gdb.add_member(g["id"], u["id"])

    gelesen = client.get(f"/api/admin/users/{u['id']}", headers=headers).get_json()
    res = client.put(f"/api/admin/users/{u['id']}",
                     json={"roles": gelesen["roles"]}, headers=headers)
    assert res.status_code == 200
    assert udb.get_user_by_id(u["id"])["roles"] == ["nis2_editor"]


def test_gruppen_im_benutzerformular_setzen(gruppe, konto, rest):
    client, headers = rest
    a, b = gruppe(roles=["cra_viewer"]), gruppe(roles=["nis2_editor"])
    u = konto()

    res = client.put(f"/api/admin/users/{u['id']}",
                     json={"gruppen": [a["id"], b["id"]]}, headers=headers)
    assert res.status_code == 200
    assert {x["name"] for x in res.get_json()["gruppen"]} == {a["name"], b["name"]}

    # Leere Liste entfernt alle — das ist nicht dasselbe wie „Feld weggelassen".
    res = client.put(f"/api/admin/users/{u['id']}", json={"gruppen": []},
                     headers=headers)
    assert res.get_json()["gruppen"] == []

    res = client.put(f"/api/admin/users/{u['id']}", json={"display_name": "X"},
                     headers=headers)
    assert res.status_code == 200


def test_konto_loeschen_entfernt_die_mitgliedschaft(gruppe, konto, rest):
    """Sonst gäbe eine Zeile bei gleicher ID die Rechte unbemerkt wieder her."""
    client, headers = rest
    g, u = gruppe(roles=["cra_editor"]), konto()
    gdb.add_member(g["id"], u["id"])

    assert client.delete(f"/api/admin/users/{u['id']}",
                         headers=headers).status_code == 200
    assert gdb.members(g["id"]) == []


# ──────────────────────────────────────────────────────────────────────────────
# 5 · Standardgruppen vorschlagen (#1780)
# ──────────────────────────────────────────────────────────────────────────────
def test_vorschlaege_nennen_die_rechte_die_sie_ergeben(rest):
    """„cra_editor, risikobewertung_editor" sagt niemandem, was jemand darf.

    Eine Gruppe anzulegen heißt, Rechte zu vergeben — die Zahl gehört in die
    Auswahl.
    """
    client, headers = rest
    daten = client.get('/api/admin/groups/vorschlaege', headers=headers).get_json()
    assert daten, 'kein Vorschlag im Katalog'
    for v in daten:
        assert v['roles'], v
        assert v['permissions_count'] > 0, v
        assert v['beschreibung'].strip(), v


def test_kein_vorschlag_haeuft_schreiben_und_freigeben_erst_an():
    """Unsere **Bündelung** darf die Rollentrennung nicht aufheben.

    Geprüft wird nicht, ob am Ende Schreib- und Freigaberecht zusammenliegen —
    die Rolle ``dsb`` trägt seit #1128 bewusst beides (sie pflegt das DSMS und
    signiert den Jahresbericht), und die Trennung wirkt ohnehin an der Handlung
    (#1780, ``shared/vier_augen``). Geprüft wird, ob die Kombination mehrerer
    Rollen eine Häufung erzeugt, die **keine** der Rollen für sich hat. Genau
    das wäre ein Zuschnitt, den wir vorschlagen und niemand bestellt hat.
    """
    from server.auth.group_vorschlaege import VORSCHLAEGE
    from server.models.permission import SIGN_OFF_PERMISSIONS, resolve_permissions

    def konflikte(rollen, extra=()):
        rechte = set(resolve_permissions(list(rollen), list(extra)))
        return {s.value for s in SIGN_OFF_PERMISSIONS
                if s.value in rechte
                and f"{s.value.split(':', 1)[0]}:write" in rechte}

    for v in VORSCHLAEGE:
        gesamt = konflikte(v.roles, v.extra_permissions)
        einzeln = set().union(*(konflikte([r]) for r in v.roles)) if v.roles else set()
        neu_entstanden = gesamt - einzeln
        assert not neu_entstanden, (
            f'Vorschlag „{v.name}" häuft erst durch die Kombination an: '
            f'{sorted(neu_entstanden)}')


def test_vorschlaege_nutzen_nur_bekannte_rollen():
    """Eine vertippte Rolle wäre eine Gruppe, die Rechte verspricht und keine gibt."""
    from server.auth.group_vorschlaege import VORSCHLAEGE
    from server.models.permission import Permission, RoleEnum

    rollen = {r.value for r in RoleEnum}
    rechte = {p.value for p in Permission}
    for v in VORSCHLAEGE:
        assert set(v.roles) <= rollen, v.name
        assert set(v.extra_permissions) <= rechte, v.name


def test_anlegen_ist_idempotent_und_ueberschreibt_nicht(rest):
    client, headers = rest
    erst = client.post('/api/admin/groups/vorschlaege',
                       json={'keys': ['produktteam']}, headers=headers)
    assert erst.status_code == 201, erst.get_data(as_text=True)
    gid = erst.get_json()['angelegt'][0]['id']

    # Die Gruppe wird angepasst — ein zweiter Lauf darf das nicht zurückdrehen.
    client.put(f'/api/admin/groups/{gid}', json={'roles': ['cra_viewer']},
               headers=headers)
    zweit = client.post('/api/admin/groups/vorschlaege',
                        json={'keys': ['produktteam']}, headers=headers)
    assert zweit.status_code == 201
    assert zweit.get_json()['angelegt'] == []
    assert zweit.get_json()['uebersprungen']
    assert gdb.get_group(gid)['roles'] == ['cra_viewer']
    gdb.delete_group(gid)


def test_unbekannter_vorschlag_wird_abgewiesen(rest):
    client, headers = rest
    res = client.post('/api/admin/groups/vorschlaege',
                      json={'keys': ['gibt-es-nicht']}, headers=headers)
    assert res.status_code == 400


def test_rechte_katalog_ist_lesbar(rest):
    """Die Gruppen-Maske ist ein Rechte-Formular — Rohwerte helfen dort nicht.

    Zwei Stellen fielen beim Durchsehen der Oberfläche auf: ``cra:approve``
    stand als Schlüssel da (ausgerechnet das Recht, das die Vier-Augen-Trennung
    trägt), und unter „Gutachten" erschienen vier Rechte doppelt — die Rolle
    führt seit #1713 die Audit-Rechte mit, und ohne Herkunft sind sie nicht
    auseinanderzuhalten. Beides betrifft auch die Benutzerverwaltung, die
    denselben Katalog liest.
    """
    client, headers = rest
    d = client.get('/api/admin/permissions/catalog', headers=headers).get_json()
    module = {m['id']: m for m in d['modules']}

    cra = {p['value']: p['label'] for p in module['cra']['permissions']}
    assert cra['cra:approve'] == 'Freigeben (Vier-Augen)'
    dsgvo = {p['value']: p['label'] for p in module['dsgvo']['permissions']}
    assert dsgvo['dsgvo:sign'] == 'Signieren'

    labels = [p['label'] for p in module['gutachten']['permissions']]
    assert len(labels) == len(set(labels)), labels
    assert 'Lesen (Compliance-Audit)' in labels


def test_gruppen_api_verlangt_benutzerverwaltung(client, pg):
    """Ohne ``admin:users`` keine Gruppen — sie vergeben Rechte."""
    res = client.get("/api/admin/groups")
    assert res.status_code in (401, 403, 422)
