"""Admin REST API - User Management, Settings, Audit, DB-Viewer, Backup."""

from flask import current_app, Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from pathlib import Path
from contextlib import closing
import json
import re
import zipfile
import shutil
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from server.models.permission import require_permission
from ai_compliance_suite.config import load_config, save_config, DEFAULT_CONFIG_PATH
from shared import db as _sdb

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

DB_DIR = Path('data/db')
BACKUP_DIR = Path('out/backup')
AUDIT_DB = DB_DIR / 'audit.sqlite'

# Whitelist for DB-Viewer to prevent path traversal
ALLOWED_DBS = {
    'firmen': 'firmen.sqlite',
    'cra': 'cra.sqlite',
    'risikobewertung': 'risikobewertung.sqlite',
    'nis2': 'nis2.sqlite',
    'dsgvo': 'dsgvo.sqlite',
    'aiact': 'ai_act.sqlite',
    'gutachten': 'gutachten.sqlite',
    'soc': 'soc.sqlite',
    'compliance': 'compliance.sqlite',
    'audit': 'audit.sqlite',
    'evidence': 'evidence.sqlite',
    'users': 'users.sqlite',
}


def _serialize_user(u: dict, *, aufgeloest: dict | None = None) -> dict:
    """User-Dict → API-Response (ohne password_hash).

    ``roles``/``extra_permissions`` bleiben die **eigenen** des Kontos. Würden
    hier die Gruppenrechte mit hineingeschrieben, speicherte das Formular sie
    beim nächsten ``PUT`` als eigene Rollen zurück — und sie blieben beim
    Verlassen der Gruppe stehen (#1779). Die Vereinigung steht getrennt in
    ``effective_permissions``/``effective_modules`` und in ``gruppen``.
    """
    from server.models.permission import resolve_permissions, allowed_modules_for
    roles = u.get('roles') or []
    extra = u.get('extra_permissions') or []
    eff = aufgeloest if aufgeloest is not None else _mit_gruppen(u)
    eff_roles = eff.get('roles') or roles
    eff_extra = eff.get('extra_permissions') or extra
    return {
        'id': u.get('id'),
        'email': u.get('email'),
        'display_name': u.get('display_name', ''),
        'roles': roles,
        'extra_permissions': extra,
        'allowed_modules': u.get('allowed_modules'),
        'allowed_firmen': u.get('allowed_firmen'),  # #1185 (None = alle Firmen)
        # #1779: Gruppen des Kontos und die Rechte, die daraus kommen.
        'gruppen': eff.get('gruppen') or [],
        'effective_permissions': resolve_permissions(eff_roles, eff_extra),
        'effective_modules': allowed_modules_for(eff_roles, eff_extra,
                                                 u.get('allowed_modules')),
        'active': bool(u.get('active', 1)),
        'created_at': u.get('created_at'),
        'updated_at': u.get('updated_at'),
        'last_login': u.get('last_login'),
    }


def _mit_gruppen(u: dict) -> dict:
    """Gruppenrechte eines Kontos auflösen (best effort, #1779)."""
    try:
        from server.auth.groups_db import effektiv
        return effektiv(u)
    except Exception:  # noqa: BLE001
        return dict(u)


@admin_bp.get('/users')
@require_permission('admin:users')
def get_users():
    """Liste alle Benutzer (echte DB-Daten)."""
    from server.auth.users_db import list_users
    users = list_users()
    # #1779: Gruppen für alle Konten in einer Abfrage — je Konto zu fragen wäre
    # bei 50 Benutzern 50 Abfragen.
    try:
        from server.auth.groups_db import effektiv_viele
        aufgeloest = effektiv_viele(users)
    except Exception:  # noqa: BLE001
        aufgeloest = [dict(u) for u in users]
    return [_serialize_user(u, aufgeloest=e)
            for u, e in zip(users, aufgeloest)], 200


@admin_bp.get('/users/<user_id>')
@require_permission('admin:users')
def get_user(user_id: str):
    from server.auth.users_db import get_user_by_id
    u = get_user_by_id(user_id)
    if not u:
        return {'error': 'User not found'}, 404
    return _serialize_user(u), 200


@admin_bp.post('/users')
@require_permission('admin:users')
def create_user():
    """Erstelle einen neuen Benutzer."""
    from server.auth.users_db import create_user as db_create_user, get_user_by_email
    from server.auth.password_policy import validate_password, PasswordPolicyError
    data = request.json or {}
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    if not email or not password:
        return {'error': 'Email und Passwort sind Pflicht'}, 400
    try:
        validate_password(password, email=email)
    except PasswordPolicyError as e:
        return {'error': str(e)}, 400
    if get_user_by_email(email):
        return {'error': 'E-Mail existiert bereits'}, 409

    roles = data.get('roles') or []
    if isinstance(roles, str):
        roles = [r.strip() for r in roles.split(',') if r.strip()]

    af = data.get('allowed_firmen')  # #1185: Liste von firmen_id oder None = alle
    user = db_create_user(
        email=email,
        password=password,
        roles=roles,
        allowed_modules=data.get('allowed_modules'),
        allowed_firmen=[int(x) for x in af] if isinstance(af, list) else None,
        extra_permissions=data.get('extra_permissions') or [],
        display_name=data.get('display_name') or '',
    )
    _gruppen_setzen(user.get('id'), data)
    antwort = _serialize_user(user)
    hinweis = _benutzer_lizenzhinweis()
    if hinweis:
        antwort['lizenz_hinweis'] = hinweis
    return antwort, 201


def _kontingent_verwerfen() -> None:
    """Zwischenspeicher der Benutzerzählung leeren (#1819, best effort)."""
    try:
        from server import license_state as _ls
        _ls.kontingent_neu_rechnen()
    except Exception:  # noqa: BLE001
        pass


def _benutzer_lizenzhinweis() -> dict[str, Any] | None:
    """Überhang melden statt sperren (#1819).

    Bis v8.0.11 gab die Benutzeranlage **423** zurück, sobald das Named-User-
    Kontingent erreicht war. Das war aus zwei Gründen falsch:

    * Das Kontingent ist eine kaufmännische Zusage, kein technischer Riegel —
      genauso wie das Mandanten-Kontingent, das aus eben diesem Grund in #1713
      von der Sperre auf einen Hinweis umgestellt wurde. Zwei gleichartige
      Zusagen, die sich entgegengesetzt verhalten, sind für niemanden
      erklärbar.
    * Die Sperre traf den Falschen. Wer am Freitagnachmittag einen Kollegen
      anlegen muss, kann den Vertrag nicht ändern; er bekommt einen Fehler, den
      er nicht abstellen kann, und ruft im Support an.

    Der Überhang steht jetzt im Fuß der Anwendung und geht über den Heartbeat
    an den Lizenzserver. ``None`` = alles im Rahmen oder nicht ermittelbar;
    eine Überschreitung zu behaupten, weil eine Zählung scheiterte, wäre die
    falsche Richtung.
    """
    try:
        from server import license_state as _ls
        _ls.kontingent_neu_rechnen()
        k = _ls._kontingent()
        if not k['zaehlbar'] or k['user_ueberhang'] <= 0:
            return None
        return {
            'code': 'benutzer-kontingent-ueberschritten',
            'message': (
                f"{k['user_count']} Named-User bei {k['max_users_effektiv']} "
                f"inbegriffenen — {k['user_ueberhang']} über dem Kontingent. "
                'Die Anlage ist erfolgt; der Überhang wird abgerechnet.'
            ),
            'user_count': k['user_count'],
            'erlaubt': k['max_users_effektiv'],
            'ueberhang': k['user_ueberhang'],
        }
    except Exception:  # noqa: BLE001 — ein Hinweis darf keine Anlage verhindern
        return None


def _gruppen_setzen(user_id: Any, data: Dict[str, Any]) -> int:
    """Gruppenzuordnung aus dem Benutzerformular übernehmen (#1779).

    ``gruppen`` fehlt im Body → die Zuordnung bleibt, wie sie ist. Eine leere
    Liste entfernt alle Mitgliedschaften; das ist der Unterschied zwischen „hat
    mich nicht interessiert" und „soll in keiner Gruppe sein".
    """
    if 'gruppen' not in data or not user_id:
        return 0
    roh = data.get('gruppen') or []
    ids = [int(g) for g in roh if str(g).strip().isdigit()] if isinstance(roh, list) else []
    try:
        from server.auth.groups_db import set_groups_for_user
        geaendert = set_groups_for_user(str(user_id), ids)
    except Exception:  # noqa: BLE001
        current_app.logger.warning('Gruppenzuordnung fehlgeschlagen', exc_info=True)
        return 0
    if geaendert:
        _audit_gruppe('admin.group.membership_changed', benutzer=str(user_id),
                      gruppen=ids)
    return len(geaendert)


@admin_bp.put('/users/<user_id>')
@require_permission('admin:users')
def update_user(user_id: str):
    """Update einen Benutzer."""
    from server.auth.users_db import update_user as db_update_user, get_user_by_id
    if not get_user_by_id(user_id):
        return {'error': 'User not found'}, 404
    data = request.json or {}

    # 'allowed_modules' in payload kann None bedeuten "alle erlauben (Whitelist entfernen)"
    kwargs = {}
    if 'email' in data:
        kwargs['email'] = data['email']
    if 'password' in data and data['password']:
        from server.auth.password_policy import validate_password, PasswordPolicyError
        try:
            validate_password(data['password'], email=data.get('email', ''))
        except PasswordPolicyError as e:
            return {'error': str(e)}, 400
        kwargs['password'] = data['password']
    if 'roles' in data:
        kwargs['roles'] = data['roles']
    if 'allowed_modules' in data:
        kwargs['allowed_modules'] = data['allowed_modules']  # None erlaubt
    if 'allowed_firmen' in data:  # #1185: None = alle Firmen, [ids] = Whitelist
        af = data['allowed_firmen']
        kwargs['allowed_firmen'] = [int(x) for x in af] if isinstance(af, list) else None
    if 'extra_permissions' in data:
        kwargs['extra_permissions'] = data['extra_permissions']
    if 'display_name' in data:
        kwargs['display_name'] = data['display_name']
    if 'active' in data:
        kwargs['active'] = bool(data['active'])

    db_update_user(user_id, **kwargs)
    # #1779: Gruppenzuordnung gehört zu denselben Rechten — sie wird deshalb
    # hier mitgeführt und zählt für die Token-Invalidierung mit.
    gruppen_geaendert = _gruppen_setzen(user_id, data)
    # #738 (AUTH-13): Bei Rechte-/Status-Änderung bestehende Tokens invalidieren,
    # damit Rollenentzug/Deaktivierung sofort greift (nicht erst nach Ablauf).
    if gruppen_geaendert or any(k in kwargs for k in ('roles', 'allowed_modules', 'allowed_firmen', 'extra_permissions', 'active', 'password')):
        from server.auth.users_db import bump_token_version
        bump_token_version(user_id)
    # #1819: Ein deaktiviertes Konto zählt nicht mehr mit — der Fuß soll das
    # sofort zeigen und nicht bis zum Ablauf des Zwischenspeichers behaupten,
    # das Kontingent sei weiter überschritten.
    if 'active' in kwargs or 'roles' in kwargs:
        _kontingent_verwerfen()
    u = get_user_by_id(user_id)
    antwort = _serialize_user(u)
    hinweis = _benutzer_lizenzhinweis()
    if hinweis:
        antwort['lizenz_hinweis'] = hinweis
    return antwort, 200


@admin_bp.delete('/users/<user_id>')
@require_permission('admin:users')
def delete_user(user_id: str):
    """Lösche einen Benutzer."""
    from server.auth.users_db import delete_user as db_delete_user
    ok = db_delete_user(user_id)
    if ok:
        # #1779: Mitgliedschaften mitnehmen. Eine Zeile zu einem gelöschten
        # Konto zählt sonst weiter als Mitglied — und bei gleicher ID eines
        # neuen Kontos gäbe sie dessen Rechte unbemerkt wieder her.
        try:
            from server.auth.groups_db import set_groups_for_user
            set_groups_for_user(user_id, [])
        except Exception:  # noqa: BLE001
            current_app.logger.warning('Mitgliedschaften nicht entfernt', exc_info=True)
        _kontingent_verwerfen()
    return {'id': user_id, 'deleted': ok}, (200 if ok else 404)


@admin_bp.post('/users/<user_id>/disable')
@require_permission('admin:users')
def disable_user(user_id: str):
    from server.auth.users_db import update_user as db_update_user, bump_token_version
    db_update_user(user_id, active=False)
    bump_token_version(user_id)  # #738 (AUTH-13): bestehende Tokens sofort ungültig
    return {'id': user_id, 'active': False}, 200


@admin_bp.post('/users/<user_id>/unlock')
@require_permission('admin:users')
def unlock_user_account(user_id: str):
    """Account-Sperre aufheben (Phase 6.2 Lockout)."""
    from server.auth.users_db import unlock_account
    ok = unlock_account(user_id)
    return {'id': user_id, 'unlocked': ok}, (200 if ok else 404)


# ─────────────────────────────────────────────────────────────────────────────
# Gruppen (#1779) — eine Rechte-Entscheidung an einer Stelle
# ─────────────────────────────────────────────────────────────────────────────

def _audit_admin(aktion: str, **details: Any) -> None:
    """Ein Verwaltungsvorgang in den Revisionspfad, **mit Akteur**.

    ``shared.audit.audit_event`` trägt den Handelnden nicht von selbst nach: Die
    Spalte ``actor`` wird aus ``details['user_id']`` gelesen (siehe
    :func:`shared.audit.audit_event`). Wer das Feld nicht mitgibt, schreibt
    „irgendwer hat Rechte vergeben" — ein Eintrag, der die Frage, für die er
    angelegt wurde, nicht beantwortet. Deshalb steht das Nachtragen hier und
    nicht in jedem Aufruf.
    """
    try:
        from shared.audit import audit_event
        try:
            identity = get_jwt_identity()
        except Exception:  # noqa: BLE001 — außerhalb eines Requests aufgerufen
            identity = None
        if identity and 'user_id' not in details:
            details = {**details, 'user_id': (
                identity if isinstance(identity, str) else str(identity))}
        audit_event(aktion, module='admin', details=details)
    except Exception:  # noqa: BLE001
        pass


def _audit_gruppe(aktion: str, **details: Any) -> None:
    """Gruppenänderungen gehören in den Revisionspfad.

    Wer wann wem welche Rechte gegeben hat, ist genau die Frage, die später
    jemand stellt — und die Gruppe ist der Ort, an dem die Antwort für viele
    Konten gleichzeitig entsteht.
    """
    _audit_admin(aktion, **details)


def _rollen_pruefen(roles: Any) -> tuple[list[str], str]:
    """Nur bekannte Rollen zulassen.

    ``resolve_permissions`` überspringt unbekannte Rollen stillschweigend — eine
    vertippte Rolle in einer Gruppe wäre damit eine Gruppe, die sichtbar Rechte
    verspricht und keine gibt.
    """
    from server.models.permission import RoleEnum
    bekannt = {r.value for r in RoleEnum}
    liste = [str(r).strip() for r in (roles or []) if str(r).strip()]
    unbekannt = [r for r in liste if r not in bekannt]
    if unbekannt:
        return liste, f"Unbekannte Rolle(n): {', '.join(unbekannt)}"
    return liste, ''


def _permissions_pruefen(perms: Any) -> tuple[list[str], str]:
    """Nur bekannte Einzelberechtigungen zulassen (gleicher Grund wie oben)."""
    from server.models.permission import Permission
    bekannt = {p.value for p in Permission}
    liste = [str(p).strip() for p in (perms or []) if str(p).strip()]
    unbekannt = [p for p in liste if p not in bekannt]
    if unbekannt:
        return liste, f"Unbekannte Berechtigung(en): {', '.join(unbekannt)}"
    return liste, ''


@admin_bp.get('/groups')
@require_permission('admin:users')
def get_groups():
    from server.auth.groups_db import list_groups
    return list_groups(), 200


@admin_bp.post('/groups')
@require_permission('admin:users')
def create_group_endpoint():
    from server.auth.groups_db import create_group, get_group_by_name
    data = request.json or {}
    name = str(data.get('name') or '').strip()
    if not name:
        return {'error': 'Feld "name" ist Pflicht'}, 400
    if get_group_by_name(name):
        return {'error': f'Es gibt bereits eine Gruppe „{name}“'}, 409
    roles, fehler = _rollen_pruefen(data.get('roles'))
    if fehler:
        return {'error': fehler}, 400
    perms, fehler = _permissions_pruefen(data.get('extra_permissions'))
    if fehler:
        return {'error': fehler}, 400
    try:
        g = create_group(name, beschreibung=str(data.get('beschreibung') or ''),
                         roles=roles, extra_permissions=perms,
                         active=bool(data.get('active', True)))
    except ValueError as e:
        return {'error': str(e)}, 400
    _audit_gruppe('admin.group.created', gruppe=name, roles=roles,
                  extra_permissions=perms)
    return g, 201


@admin_bp.get('/groups/vorschlaege')
@require_permission('admin:users')
def group_vorschlaege_list():
    """Standardgruppen zur Auswahl — angelegt wird nichts (#1780)."""
    from server.auth.group_vorschlaege import katalog
    from server.auth.groups_db import get_group_by_name

    out = []
    for v in katalog():
        vorhanden = get_group_by_name(v['name'])
        out.append({**v, 'vorhanden': bool(vorhanden),
                    'gruppe_id': (vorhanden or {}).get('id')})
    return out, 200


@admin_bp.post('/groups/vorschlaege')
@require_permission('admin:users')
def group_vorschlaege_anlegen():
    """Ausgewählte Standardgruppen anlegen.

    Idempotent über den Namen: Eine vorhandene Gruppe wird **übersprungen**,
    nicht überschrieben — sie kann längst angepasst worden sein, und ein
    „Standard wiederherstellen" wäre ein stiller Rechteeingriff.
    """
    from server.auth.group_vorschlaege import finde, katalog
    from server.auth.groups_db import create_group, get_group_by_name

    data = request.json or {}
    keys = data.get('keys')
    if not isinstance(keys, list) or not keys:
        return {'error': 'Feld "keys" ist Pflicht (Liste der Vorschläge)'}, 400

    angelegt, uebersprungen, unbekannt = [], [], []
    for key in keys:
        v = finde(str(key))
        if not v:
            unbekannt.append(str(key))
            continue
        if get_group_by_name(v.name):
            uebersprungen.append(v.name)
            continue
        g = create_group(v.name, beschreibung=v.beschreibung,
                         roles=list(v.roles),
                         extra_permissions=list(v.extra_permissions))
        angelegt.append({'id': g['id'], 'name': g['name']})
        _audit_gruppe('admin.group.created', gruppe=v.name, roles=list(v.roles),
                      extra_permissions=list(v.extra_permissions),
                      herkunft='vorschlag')
    if unbekannt and not angelegt:
        return {'error': f"Unbekannte Vorschläge: {', '.join(unbekannt)}"}, 400
    return {'angelegt': angelegt, 'uebersprungen': uebersprungen,
            'unbekannt': unbekannt, 'katalog': katalog()}, 201


@admin_bp.get('/groups/<int:group_id>')
@require_permission('admin:users')
def get_group_endpoint(group_id: int):
    from server.auth.groups_db import get_group
    g = get_group(group_id)
    return (g, 200) if g else ({'error': 'Gruppe nicht gefunden'}, 404)


@admin_bp.put('/groups/<int:group_id>')
@require_permission('admin:users')
def update_group_endpoint(group_id: int):
    from server.auth.groups_db import (get_group, get_group_by_name, members,
                                       tokens_invalidieren, update_group)
    if not get_group(group_id):
        return {'error': 'Gruppe nicht gefunden'}, 404
    data = request.json or {}
    felder: Dict[str, Any] = {}
    if 'name' in data:
        name = str(data['name'] or '').strip()
        andere = get_group_by_name(name)
        if andere and int(andere['id']) != int(group_id):
            return {'error': f'Es gibt bereits eine Gruppe „{name}“'}, 409
        felder['name'] = name
    if 'beschreibung' in data:
        felder['beschreibung'] = data['beschreibung']
    if 'roles' in data:
        roles, fehler = _rollen_pruefen(data.get('roles'))
        if fehler:
            return {'error': fehler}, 400
        felder['roles'] = roles
    if 'extra_permissions' in data:
        perms, fehler = _permissions_pruefen(data.get('extra_permissions'))
        if fehler:
            return {'error': fehler}, 400
        felder['extra_permissions'] = perms
    if 'active' in data:
        felder['active'] = bool(data['active'])
    try:
        g = update_group(group_id, **felder)
    except ValueError as e:
        return {'error': str(e)}, 400
    # Rechteänderung wirkt sofort: Die Berechtigungen stehen im Token, also
    # müssen die Tokens der Mitglieder fallen (#738, Begründung in groups_db).
    betroffen = 0
    if any(k in felder for k in ('roles', 'extra_permissions', 'active')):
        betroffen = tokens_invalidieren(members(group_id))
    _audit_gruppe('admin.group.updated', gruppe=(g or {}).get('name'),
                  felder=sorted(felder), abgemeldete_mitglieder=betroffen)
    out = dict(g or {})
    out['abgemeldete_mitglieder'] = betroffen
    return out, 200


@admin_bp.delete('/groups/<int:group_id>')
@require_permission('admin:users')
def delete_group_endpoint(group_id: int):
    from server.auth.groups_db import delete_group, get_group, tokens_invalidieren
    g = get_group(group_id)
    if not g:
        return {'error': 'Gruppe nicht gefunden'}, 404
    mitglieder = list(g.get('mitglieder') or [])
    delete_group(group_id)
    betroffen = tokens_invalidieren(mitglieder)
    _audit_gruppe('admin.group.deleted', gruppe=g.get('name'),
                  mitglieder=len(mitglieder), abgemeldete_mitglieder=betroffen)
    return {'id': group_id, 'deleted': True,
            'abgemeldete_mitglieder': betroffen}, 200


@admin_bp.post('/groups/<int:group_id>/members')
@require_permission('admin:users')
def add_group_member(group_id: int):
    from server.auth.groups_db import add_member, get_group, tokens_invalidieren
    from server.auth.users_db import get_user_by_id
    if not get_group(group_id):
        return {'error': 'Gruppe nicht gefunden'}, 404
    data = request.json or {}
    user_id = str(data.get('user_id') or '').strip()
    if not user_id:
        return {'error': 'Feld "user_id" ist Pflicht'}, 400
    if not get_user_by_id(user_id):
        return {'error': 'Benutzer nicht gefunden'}, 404
    add_member(group_id, user_id)
    tokens_invalidieren([user_id])
    _audit_gruppe('admin.group.member_added', gruppe_id=group_id, benutzer=user_id)
    return get_group(group_id), 200


@admin_bp.delete('/groups/<int:group_id>/members/<user_id>')
@require_permission('admin:users')
def remove_group_member(group_id: int, user_id: str):
    from server.auth.groups_db import get_group, remove_member, tokens_invalidieren
    if not get_group(group_id):
        return {'error': 'Gruppe nicht gefunden'}, 404
    entfernt = remove_member(group_id, user_id)
    if entfernt:
        tokens_invalidieren([user_id])
        _audit_gruppe('admin.group.member_removed', gruppe_id=group_id,
                      benutzer=user_id)
    return get_group(group_id), 200


@admin_bp.get('/password-policy')
@require_permission('admin:users')
def get_password_policy_endpoint():
    """Liefert aktuelle Password-Policy für UI-Anzeige."""
    from server.auth.password_policy import get_policy
    return get_policy(), 200


@admin_bp.get('/webauthn-config')
@require_permission('admin:config')
def get_webauthn_config_endpoint():
    """Liefert die aktuelle Passkey/WebAuthn-RP-Konfiguration (über Web pflegbar).

    Liefert die effektiven Werte (Settings > ENV > Default) plus die Quelle,
    damit das UI anzeigen kann, ob ENV/Default greift.
    """
    from server.auth.webauthn import get_rp_config, _settings_rp_config
    eff = get_rp_config()
    raw = _settings_rp_config()
    return {
        'rp_id': eff['rp_id'],
        'rp_name': eff['rp_name'],
        'rp_origin': ','.join(eff['origins']),
        'from_settings': bool(raw),
    }, 200


@admin_bp.put('/webauthn-config')
@require_permission('admin:config')
def update_webauthn_config_endpoint():
    """Setzt die Passkey/WebAuthn-RP-Konfiguration über die Weboberfläche.

    Body: { "rp_id": "aics.intern.local", "rp_name": "...", "rp_origin": "https://..." }
    Validierung: rp_id darf keine IP/kein Schema/Port sein.
    """
    from server.auth.webauthn import save_rp_config
    data = request.get_json(silent=True) or {}
    rp_id = (data.get('rp_id') or '').strip()
    rp_origin = (data.get('rp_origin') or '').strip()

    import re as _re
    if rp_id:
        if '://' in rp_id or ':' in rp_id or '/' in rp_id:
            return {'error': 'RP-ID ohne Schema/Port/Pfad angeben (z.B. aics.intern.local)'}, 400
        if _re.fullmatch(r'\d{1,3}(\.\d{1,3}){3}', rp_id):
            return {'error': 'RP-ID darf keine IP-Adresse sein — Hostname verwenden'}, 400
    if rp_origin and not rp_origin.startswith(('https://', 'http://localhost')):
        return {'error': 'Origin muss mit https:// beginnen (Ausnahme: http://localhost)'}, 400

    # Härtung #729: rp_id MUSS ein registrierbares Suffix des Origin-Hostnamens sein
    # (verhindert den Vorfall rp_id='compliancesuite' bei Origin
    # 'compliancesuite.c99781.intern' → 'rp.id cannot be used with the current origin').
    if rp_id and rp_origin:
        from urllib.parse import urlparse
        origin_host = (urlparse(rp_origin).hostname or '').lower().strip('.')
        rid = rp_id.lower().strip('.')
        if origin_host and not (origin_host == rid or origin_host.endswith('.' + rid)):
            return {'error': (
                f"RP-ID '{rp_id}' passt nicht zum Origin-Host '{origin_host}'. "
                f"Die RP-ID muss der vollständige Hostname oder ein registrierbares "
                f"Suffix sein (z.B. '{origin_host}' oder die übergeordnete Domain)."
            )}, 400

    try:
        saved = save_rp_config(rp_id, data.get('rp_name', ''), rp_origin)
        try:
            from shared.audit import audit_event
            audit_event('webauthn.config.changed', module='auth.admin',
                        details={'rp_id': saved['rp_id'], 'rp_origin': saved['rp_origin']})
        except Exception:
            pass
        return {'updated': True, 'config': saved}, 200
    except Exception as e:
        current_app.logger.exception('update_webauthn_config: %s', e)
        return {'error': str(e)}, 500


@admin_bp.get('/mfa-policy')
@require_permission('admin:config')
def get_mfa_policy_endpoint():
    """Liefert die aktuelle MFA-Policy (Sprint ε Phase D)."""
    from server.auth.mfa_policy import get_policy
    return get_policy(), 200


@admin_bp.put('/mfa-policy')
@require_permission('admin:config')
def update_mfa_policy_endpoint():
    """Setzt die MFA-Policy.

    Body: { "mode": "optional|required_all|required_roles",
            "required_roles": [...], "grace_days": int }
    """
    from server.auth.mfa_policy import save_policy
    data = request.get_json(silent=True) or {}
    try:
        policy = save_policy(
            mode=data.get('mode', 'optional'),
            required_roles=data.get('required_roles', []),
            grace_days=int(data.get('grace_days', 7)),
        )
        try:
            from shared.audit import audit_event
            audit_event('mfa.policy.changed', module='auth.admin',
                        details={'mode': policy['mode'],
                                 'required_roles': policy['required_roles'],
                                 'grace_days': policy['grace_days']})
        except Exception:
            pass
        return {'updated': True, 'policy': policy}, 200
    except ValueError as e:
        return {'error': str(e)}, 400
    except Exception as e:
        current_app.logger.exception('update_mfa_policy: %s', e)
        return {'error': str(e)}, 500


@admin_bp.get('/permissions/catalog')
@require_permission('admin:users')
def permissions_catalog():
    """Liefert Module + Permissions + Rollen für UI-Auswahl."""
    from server.models.permission import (
        MODULES, MODULE_PERMISSIONS, RoleEnum, ROLE_PERMISSIONS,
    )

    module_labels = {
        'firmen': 'Firmen',
        'risikobewertung': 'Risikobewertung',
        'cra': 'CRA – Cyber Resilience Act',
        'nis2': 'NIS2',
        'aiact': 'AI Act',
        'dsgvo': 'DSGVO',
        'gutachten': 'Gutachten',
        'wiba': 'WiBA',
        'soc': 'SOC – Security Operations Center',
        # Nicht in MODULES (das steuert die allowed_modules-Whitelist), aber als
        # Herkunftsangabe nötig: Die Gutachten-Rolle führt die Audit-Rechte mit
        # (#1713).
        'compliance_audit': 'Compliance-Audit',
    }
    perm_labels = {
        ':read': 'Lesen',
        ':write': 'Bearbeiten',
        ':export': 'Export',
        ':prefill': 'Prefill (KI-Vorbefüllung)',
        ':issue_link': 'Issue-Verknüpfung',
        ':frameworks': 'Framework-Bibliothek',
        ':catalog': 'Katalog (Download/Ingest)',
        ':triage': 'Triage (Alarm-Status)',
        ':incident': 'Incidents & Meldetracks',
        ':config': 'Verbindung/Einrichtung',
        # Freigabe und Signatur fehlten — sie standen als Rohwert („cra:approve")
        # in der Auswahl. Bei einem Recht, das die Vier-Augen-Trennung trägt
        # (#1743/#1128), ist das die unpassendste Stelle für einen Schlüssel.
        ':approve': 'Freigeben (Vier-Augen)',
        ':sign': 'Signieren',
    }

    def _label(perm_value: str, modul: str = '') -> str:
        modul_key, _, aktion = perm_value.partition(':')
        name = perm_labels.get(':' + aktion, perm_value)
        # Ein Modul kann Rechte **eines anderen** Moduls mitführen: Die
        # Gutachten-Rolle enthält seit #1713 bewusst die Audit-Rechte. Ohne
        # Herkunft stehen dort „Lesen, Bearbeiten, Export, Framework-Bibliothek"
        # zweimal untereinander, und niemand kann sie auseinanderhalten.
        if modul and modul_key != modul:
            herkunft = module_labels.get(modul_key, modul_key)
            return f'{name} ({herkunft})'
        return name

    modules = []
    for mid in MODULES:
        modules.append({
            'id': mid,
            'label': module_labels.get(mid, mid),
            'permissions': [
                {'value': p.value, 'label': _label(p.value, mid)}
                for p in MODULE_PERMISSIONS.get(mid, [])
            ],
        })

    roles = []
    for r in RoleEnum:
        roles.append({
            'value': r.value,
            'permissions': [p.value for p in ROLE_PERMISSIONS.get(r, [])],
        })

    admin_perms = [
        {'value': 'admin:users',  'label': 'Benutzerverwaltung'},
        {'value': 'admin:roles',  'label': 'Rollen verwalten'},
        {'value': 'admin:audit',  'label': 'Audit-Log einsehen'},
        {'value': 'admin:config', 'label': 'Konfiguration / Framework-Bibliothek'},
    ]

    return {
        'modules': modules,
        'roles': roles,
        'admin_permissions': admin_perms,
    }, 200


@admin_bp.post('/users/<user_id>/enable')
@require_permission('admin:users')
def enable_user(user_id: str):
    """Aktiviere einen Benutzer."""
    return {
        'id': user_id,
        'active': True,
        'updated': True
    }, 200


# ============================================================
# F0b — Settings (KI-Provider, Module, Backup, Appearance, Auth)
# ============================================================

@admin_bp.get('/settings')
@require_permission('admin:config')
def get_settings():
    """Globale Settings holen (Desktop-config-kompatibel)."""
    try:
        cfg = load_config()
        # Sensitive Felder maskieren
        cfg = _mask_sensitive(cfg)
        return cfg, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@admin_bp.put('/settings')
@require_permission('admin:config')
def update_settings():
    """Globale Settings aktualisieren.

    #416: vorher überschrieb das die ganze Config — inkl. maskierter
    Tokens ('***'). Jetzt:
      1. Bestehende Config laden
      2. Sensitive Felder mit Wert '***' aus dem Request entfernen
         (User hat sie nicht editiert; sie wurden nur maskiert ausgeliefert)
      3. Tiefen-Merge: Request-Daten überschreiben nur was sie explizit setzen
    """
    import logging as _logging
    _log = _logging.getLogger(__name__)
    try:
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return {'error': 'Body must be a JSON object'}, 400

        # Härtung #730: auth.* (Passkey/WebAuthn, MFA-Policy) wird AUSSCHLIESSLICH
        # über die dedizierten Endpoints /webauthn-config und /mfa-policy verwaltet.
        # Aus dem allgemeinen Settings-Save entfernen, damit ein veralteter
        # Client-Stand diese Werte nicht überschreibt (Clobbering).
        data.pop('auth', None)

        # 'Maskierungs-Müll' aus dem Request entfernen — sonst werden echte
        # Werte mit '***' überschrieben.
        _strip_masked(data)
        # Defensive (#416 reopen #2): bekannte sensitive Felder mit LEEREM Wert
        # auch entfernen — Client darf einen frisch gesetzten Token nicht durch
        # einen veralteten leeren Wert überschreiben.
        _strip_empty_sensitive(data)
        # Response-only Felder (z.B. token_set, token_masked, source) aus
        # geschicktem Body entfernen — sie haben in der Persistenz nichts verloren.
        _strip_response_only(data)

        # Tiefen-Merge gegen bestehende Config
        from copy import deepcopy
        existing = deepcopy(load_config())
        merged = _deep_merge(existing, data)

        # Cloud-Egress nur mit ausdrücklicher Zustimmung — geprüft wird der
        # Stand NACH dem Zusammenführen (#1827). Vorher las die Prüfung nur das
        # Bruchstück aus dem Request: Ein Teil-Update, das allein den Provider
        # umstellt, wurde abgewiesen, obwohl der Datenausgang längst erlaubt
        # war — und über eine Sicherheitsfrage entschied, was der Client
        # zufällig mitschickte, statt der Zustand, der anschließend gilt.
        fehler = _pruefe_ki_egress(merged)
        if fehler:
            return fehler, 400

        _encrypt_github_token_in_place(merged)  # #1174
        _encrypt_portainer_key_in_place(merged)  # #1534

        _log.info(
            'update_settings: keys=%s github.token_kept=%s',
            list(data.keys()),
            bool((existing.get('integrations') or {}).get('github', {}).get('token')) and
            ((merged.get('integrations') or {}).get('github', {}).get('token') ==
             (existing.get('integrations') or {}).get('github', {}).get('token')),
        )
        save_config(merged)
        return {'updated': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


#: Beschriftung des Hakens im Einstellungsdialog. Die Meldung zitiert sie
#: wörtlich: Eine Wegbeschreibung auf ein Wort, das in der Oberfläche nicht
#: vorkommt, ist schlechter als keine (#1805, #1827).
EGRESS_HAKEN = 'Datenausgang erlauben (Pflicht für Cloud)'


def _pruefe_ki_egress(cfg: Dict[str, Any]) -> 'Dict[str, Any] | None':
    """Cloud-Betrieb nur mit erlaubtem Datenausgang und geprüfter Base-URL.

    Bekommt die **zusammengeführte** Konfiguration, nicht den Request: Geprüft
    wird der Zustand, der nach dem Speichern gilt. Das schließt nebenbei eine
    Lücke in der SSRF-Prüfung aus #741 — stand die Base-URL schon in der
    Konfiguration und schickte der Client sie nicht mit, lief die Umstellung
    auf Cloud bisher ganz ohne Adressprüfung durch.

    Liefert ``None``, wenn alles passt, sonst den Antwortkörper für 400.
    """
    ai = cfg.get('ai') or {}
    if str(ai.get('provider') or '') != 'cloud':
        return None
    cloud = ai.get('cloud') or {}
    if not cloud.get('allow_data_egress'):
        return {
            'error': ('Für den Cloud-Betrieb muss der Datenausgang ausdrücklich '
                      f'erlaubt sein. Setzen Sie im Abschnitt „Cloud" den Haken '
                      f'„{EGRESS_HAKEN}" — oder wählen Sie einen anderen '
                      'KI-Provider. Dabei verlassen Daten den lokalen Rechner.'),
            'code': 'cloud-egress-nicht-erlaubt',
            'feld': 'ai.cloud.allow_data_egress',
        }
    # #741 (SSRF): Cloud-Base-URL gegen Provider-Allowlist (nur HTTPS, bekannte
    # Hosts) — verhindert Exfiltration an beliebige Endpunkte.
    cloud_url = str(cloud.get('base_url') or '').strip()
    if cloud_url:
        from shared.net_validation import enforce_cloud_llm_base_url
        try:
            enforce_cloud_llm_base_url(
                cloud_url, context='settings.ai.cloud',
                allow_custom_host=bool(cloud.get('allow_custom_host', False)))
        except ValueError as e:
            return {'error': str(e), 'code': 'cloud-base-url-unzulaessig',
                    'feld': 'ai.cloud.base_url'}
    return None


def _encrypt_github_token_in_place(cfg: Dict[str, Any]) -> None:
    """#1174: GitHub-PAT vor der Persistenz at-rest verschlüsseln.

    Idempotent — bereits verschlüsselte Werte (AICSFLD1-Prefix) bleiben
    unangetastet, leere Werte werden nicht verschlüsselt.
    """
    gh = (cfg.get('integrations') or {}).get('github') or {}
    tok = str(gh.get('token') or '').strip()
    if not tok:
        return
    try:
        from shared.crypto_at_rest import encrypt_field, is_encrypted_field
        if not is_encrypted_field(tok):
            cfg['integrations']['github']['token'] = encrypt_field(tok)
    except Exception:
        current_app.logger.warning('GitHub-Token konnte nicht verschlüsselt werden (#1174)')


def _encrypt_portainer_key_in_place(cfg: Dict[str, Any]) -> None:
    """#1534: Portainer-API-Key vor der Persistenz at-rest verschlüsseln (idempotent)."""
    port = (cfg.get('integrations') or {}).get('portainer') or {}
    key = str(port.get('api_key') or '').strip()
    if not key:
        return
    try:
        from shared.crypto_at_rest import encrypt_field, is_encrypted_field
        if not is_encrypted_field(key):
            cfg['integrations']['portainer']['api_key'] = encrypt_field(key)
    except Exception:
        current_app.logger.warning('Portainer-API-Key konnte nicht verschlüsselt werden (#1534)')


def _resolve_portainer_key(portainer: Dict[str, Any]) -> 'str | None':
    """#1534: Portainer-API-Key auflösen — Vorrang Env-Var (api_key_env, Secret-Hygiene),
    sonst der in der Config at-rest verschlüsselt hinterlegte api_key."""
    env_name = str(portainer.get('api_key_env') or '').strip()
    if env_name and os.environ.get(env_name):
        return os.environ.get(env_name)
    raw = str(portainer.get('api_key') or '').strip()
    if not raw or raw == '***':
        return None
    try:
        from shared.crypto_at_rest import decrypt_field, is_encrypted_field
        return decrypt_field(raw) if is_encrypted_field(raw) else raw
    except Exception:
        return raw


def _strip_masked(d: Any) -> None:
    """Entfernt Felder mit Wert '***' rekursiv (vom _mask_sensitive maskiert).

    Damit überschreibt ein Frontend, das das ganze Settings-Object zurückschickt,
    KEINE sensitiven Felder mehr — sondern lässt sie unverändert.
    """
    if isinstance(d, dict):
        for k in list(d.keys()):
            if d[k] == '***':
                del d[k]
            elif isinstance(d[k], (dict, list)):
                _strip_masked(d[k])
    elif isinstance(d, list):
        for item in d:
            _strip_masked(item)


# Bekannte sensitive Pfade (dotted) — leere Strings werden nicht persistiert.
# Damit ein veraltetes "" aus dem Frontend-Form niemals einen frisch gesetzten
# Token überschreibt (#416 reopen #2).
_SENSITIVE_PATHS = {
    'integrations.github.token',
    'integrations.portainer.api_key',  # #1534
    'auth.password_hash',
    'ai.cloud.api_key',
}

# Reine Response-Felder, die niemals persistiert werden dürfen.
_RESPONSE_ONLY_FIELDS = {
    'integrations.github.token_set',
    'integrations.github.token_masked',
    'integrations.github.source',
    'integrations.portainer.api_key_set',  # #1534
}


def _walk_path(d: Any, dotted: str):
    """Yields (parent_dict, last_key) for every match of dotted path."""
    parts = dotted.split('.')
    def _go(cur: Any, idx: int):
        if idx == len(parts) - 1:
            if isinstance(cur, dict) and parts[idx] in cur:
                yield cur, parts[idx]
            return
        if isinstance(cur, dict) and parts[idx] in cur:
            yield from _go(cur[parts[idx]], idx + 1)
    yield from _go(d, 0)


def _strip_empty_sensitive(d: Any) -> None:
    for path in _SENSITIVE_PATHS:
        for parent, key in list(_walk_path(d, path)):
            v = parent.get(key)
            if v == '' or v is None:
                del parent[key]


def _strip_response_only(d: Any) -> None:
    for path in _RESPONSE_ONLY_FIELDS:
        for parent, key in list(_walk_path(d, path)):
            del parent[key]


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """Rekursives Merge: overlay-Werte überschreiben, Listen werden ersetzt."""
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


_SECRET_KEY_HINTS = (
    'token', 'api_key', 'apikey', 'secret', 'password', 'passwd',
    'private_key', 'credential',
)


def _deep_redact_secrets(obj: Any) -> Any:
    """Defense-in-Depth: maskiert rekursiv JEDES String-Feld, dessen Schlüssel auf
    ein Secret hindeutet (Token/API-Key/Secret/Passwort/…), unabhängig vom Pfad.

    Für das Support-Bundle (#1509): eine kuratierte Pfadliste (``_SENSITIVE_PATHS``)
    ist zu fragil — z. B. ``ai.cloud.api_key`` wird von ``_mask_sensitive`` nicht
    maskiert. Boolean-/Leerwerte bleiben unverändert (z. B. ``token_set``)."""
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            kl = str(k).lower()
            if isinstance(v, str) and v and any(h in kl for h in _SECRET_KEY_HINTS):
                out[k] = '***'
            else:
                out[k] = _deep_redact_secrets(v)
        return out
    if isinstance(obj, list):
        return [_deep_redact_secrets(x) for x in obj]
    return obj


def _mask_sensitive(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Maskiert sensitive Felder für Read-Endpoint.

    #416: ALLE bekannten Token-Felder werden IMMER mit '***' ersetzt — auch wenn
    leer. Sonst sendet der Client beim Save ein leeres Token zurück, das den
    serverseitig frisch gespeicherten Token überschreibt (kein '***' = wird
    nicht durch _strip_masked entfernt).
    """
    out = json.loads(json.dumps(cfg))  # deep copy
    auth = out.get('auth', {})
    if 'password_hash' in auth:
        auth['password_hash'] = '***'
    # GitHub-Token: IMMER maskieren, damit der Client niemals echte Werte zurückspielt
    out.setdefault('integrations', {}).setdefault('github', {})
    gh = out['integrations']['github']
    gh['token_set'] = bool(gh.get('token'))
    gh['token'] = '***'  # immer maskieren — auch wenn leer
    # #1534: Portainer-API-Key analog IMMER maskieren + Set-Status ausweisen.
    port = out['integrations'].setdefault('portainer', {})
    port['api_key_set'] = bool(port.get('api_key'))
    port['api_key'] = '***'
    return out


# ============================================================
# GitHub-Integration (Settings + Verbindungstest)
# ============================================================

@admin_bp.get('/github')
@require_permission('admin:config')
def github_get():
    """Liefert (maskiert) Token-Status + Username + Default-Repo + source."""
    from shared.github_config import get_github_config
    gc = get_github_config()
    return {
        'token_set': bool(gc.token),
        'token_masked': (gc.token[:4] + '…' + gc.token[-4:]) if gc.token else '',
        'username': gc.username,
        'default_repo': gc.default_repo,
        'source': gc.source,
    }, 200


@admin_bp.put('/github')
@require_permission('admin:config')
def github_set():
    """Speichert GitHub-Konfig in der globalen Suite-Config.

    Body: { token: str, username?: str, default_repo?: str }
    Leerer token = Token löschen.
    """
    import logging as _logging
    _log = _logging.getLogger(__name__)

    data = request.get_json(silent=True) or {}
    token = str(data.get('token') or '').strip()
    username = str(data.get('username') or '').strip()
    default_repo = str(data.get('default_repo') or '').strip()

    # Diagnose: jeden PUT mit Token-Länge protokollieren (nicht den Token selbst!)
    _log.info(
        'github_set: token_in_body=%s token_len=%d username=%r repo=%r',
        'token' in data, len(token), username, default_repo,
    )

    # Sanity-Check: ein realer GH-Token ist mindestens 20 Zeichen lang
    if 'token' in data and token and len(token) < 20:
        _log.warning('github_set: rejected token of suspicious length %d', len(token))
        return {
            'error': 'token-too-short',
            'message': f'Token ist nur {len(token)} Zeichen — Browser-Autofill? '
                       'GitHub-Tokens sind 40+ Zeichen (classic) bzw. 80+ (fine-grained).',
        }, 400

    cfg = load_config()
    cfg.setdefault('integrations', {}).setdefault('github', {})
    if 'token' in data:
        cfg['integrations']['github']['token'] = token
    cfg['integrations']['github']['username'] = username
    cfg['integrations']['github']['default_repo'] = default_repo
    _encrypt_github_token_in_place(cfg)  # #1174: PAT at-rest verschlüsseln
    save_config(cfg)
    _log.info('github_set: gespeichert token_set=%s', bool(token))
    return {'saved': True, 'token_set': bool(token), 'token_len': len(token)}, 200


@admin_bp.get('/ollama/models')
@require_permission('admin:config')
def ollama_models():
    """Listet installierte Modelle vom Ollama-Server + kuratierte Empfehlungen."""
    import requests
    from shared.ollama_config import get_ollama_config

    override_url = request.args.get('base_url', '').strip()
    oc = get_ollama_config()
    base_url = (override_url or oc.base_url).rstrip('/')

    installed: list[Dict[str, Any]] = []
    error = None
    try:
        r = requests.get(f'{base_url}/api/tags', timeout=5)
        if r.status_code == 200:
            for m in (r.json().get('models') or []):
                installed.append({
                    'name': m.get('name', ''),
                    'size_bytes': m.get('size', 0),
                    'modified_at': m.get('modified_at'),
                    'family': (m.get('details') or {}).get('family', ''),
                    'parameter_size': (m.get('details') or {}).get('parameter_size', ''),
                })
        else:
            error = f'HTTP {r.status_code}'
    except Exception as e:
        error = f'{type(e).__name__}: {e}'

    # Kuratierte Empfehlungen — nach RAM-Bedarf sortiert
    recommendations = [
        {'tag': 'llama3.2:1b', 'size_gb': 1.3, 'desc': 'Sehr schnell, gut für leichte Tasks (≥ 2 GB RAM)'},
        {'tag': 'qwen2.5:3b', 'size_gb': 2.0, 'desc': 'Gute Balance Speed/Qualität (≥ 4 GB RAM)'},
        {'tag': 'phi3.5:3.8b', 'size_gb': 2.3, 'desc': 'Microsoft Phi-3.5, kompakt + stark (≥ 4 GB RAM)'},
        {'tag': 'mistral:7b', 'size_gb': 4.1, 'desc': 'Mistral 7B — allround (≥ 8 GB RAM)'},
        {'tag': 'llama3.1:8b', 'size_gb': 4.7, 'desc': 'Meta Llama 3.1 8B — Standard (≥ 8 GB RAM)'},
        {'tag': 'qwen2.5:7b', 'size_gb': 4.4, 'desc': 'Qwen 2.5 7B — sehr stark im Reasoning (≥ 8 GB RAM)'},
        {'tag': 'llama3.1:70b', 'size_gb': 40.0, 'desc': 'Großes Modell — nur mit ≥ 64 GB RAM oder GPU'},
    ]

    return {
        'base_url': base_url,
        'installed': installed,
        'recommendations': recommendations,
        'error': error,
    }, 200


@admin_bp.get('/ollama/diagnose')
@require_permission('admin:config')
def ollama_diagnose():
    """Diagnose-Suite für Ollama-Konfiguration.

    Query-Args (optional, überschreiben gespeicherte Config für Test-vor-Speichern):
      - base_url
      - model
      - timeout_s (default 10)
      - gen_timeout (default 60)

    Returns: { config, checks: [{name, ok, detail, meta}] }
    """
    import time
    import requests
    from shared.ollama_config import get_ollama_config

    override_url = request.args.get('base_url', '').strip()
    override_model = request.args.get('model', '').strip()
    timeout_s = int(request.args.get('timeout_s', '10'))
    gen_timeout = int(request.args.get('gen_timeout', '60'))

    oc = get_ollama_config()
    base_url = (override_url or oc.base_url).rstrip('/')
    model = override_model or oc.model

    out: Dict[str, Any] = {
        'config': {
            'base_url': base_url, 'model': model,
            'source': oc.source, 'override': bool(override_url or override_model),
        },
        'checks': [],
    }

    def add(name: str, ok: bool, detail: str = '', meta: Dict[str, Any] | None = None):
        out['checks'].append({'name': name, 'ok': ok, 'detail': detail, 'meta': meta or {}})

    # 1. URL-Format
    if not base_url:
        add('Konfiguration: Base-URL', False, 'Keine Base-URL gesetzt.')
        return out, 200
    if not base_url.startswith(('http://', 'https://')):
        add('Konfiguration: Base-URL', False, f'Ungültige URL (http/https erwartet): {base_url}')
        return out, 200
    add('Konfiguration: Base-URL', True, base_url)

    # 2. Modell konfiguriert
    if model:
        add('Konfiguration: Modell', True, model)
    else:
        add('Konfiguration: Modell', False, 'Kein Modell konfiguriert')

    # 3. TCP/HTTP-Erreichbarkeit
    t0 = time.monotonic()
    try:
        r = requests.get(f'{base_url}/', timeout=timeout_s)
        lat = int((time.monotonic() - t0) * 1000)
        ok = r.status_code < 500
        add('Netzwerk: Erreichbarkeit', ok,
            f'HTTP {r.status_code} in {lat} ms',
            {'latency_ms': lat, 'http_status': r.status_code})
    except requests.exceptions.ConnectionError as e:
        add('Netzwerk: Erreichbarkeit', False,
            f'Verbindung verweigert / Host nicht erreichbar — Ollama läuft? ({e.__class__.__name__})',
            {'error_type': 'connection-refused'})
        return out, 200
    except requests.exceptions.Timeout:
        add('Netzwerk: Erreichbarkeit', False,
            f'Timeout nach {timeout_s}s', {'error_type': 'timeout'})
        return out, 200
    except Exception as e:
        add('Netzwerk: Erreichbarkeit', False, f'{type(e).__name__}: {e}')
        return out, 200

    # 4. /api/tags → installierte Modelle
    t0 = time.monotonic()
    installed: list[str] = []
    try:
        r = requests.get(f'{base_url}/api/tags', timeout=timeout_s)
        if r.status_code == 200:
            data = r.json()
            installed = [m.get('name', '') for m in (data.get('models') or [])]
            lat = int((time.monotonic() - t0) * 1000)
            add('API: /api/tags', True,
                f'{len(installed)} Modelle installiert ({lat} ms)',
                {'models': installed, 'latency_ms': lat})
        else:
            add('API: /api/tags', False,
                f'HTTP {r.status_code} — Ollama-API antwortet nicht wie erwartet')
            return out, 200
    except Exception as e:
        add('API: /api/tags', False, f'{type(e).__name__}: {e}')
        return out, 200

    def _exact(installed_name: str, requested: str) -> bool:
        return (installed_name == requested
                or installed_name.startswith(requested + ':'))

    def _family(installed_name: str, requested: str) -> bool:
        return installed_name.split(':')[0] == requested.split(':')[0]

    # 5. Modell installiert? (exact vs family-match)
    effective_model = None
    if model:
        exact_hit = next((m for m in installed if _exact(m, model)), None)
        family_hit = next((m for m in installed if _family(m, model)), None) if not exact_hit else None
        if exact_hit:
            effective_model = exact_hit
            add('Modell verfügbar', True, f'{model} ist installiert',
                {'installed': installed, 'effective_model': exact_hit})
        elif family_hit:
            # Family-Match: anderer Tag derselben Modell-Familie
            effective_model = family_hit
            add('Modell verfügbar', False,
                f'Exakt {model} fehlt, aber {family_hit} (gleiche Familie) ist da. '
                f'Generation-Test nutzt {family_hit}. Empfehlung: in Config auf {family_hit} '
                f'umstellen ODER mit "ollama pull {model}" exakt installieren.',
                {'installed': installed, 'effective_model': family_hit,
                 'install_hint': f'ollama pull {model}'})
        else:
            add('Modell verfügbar', False,
                f'{model} fehlt. Vorhanden: {", ".join(installed[:5]) or "(keine)"}',
                {'installed': installed, 'install_hint': f'ollama pull {model}'})

    # 6. Test-Generation — nutzt den effektiv installierten Tag
    if effective_model:
        test_model = effective_model
        t0 = time.monotonic()
        try:
            r = requests.post(
                f'{base_url}/api/generate',
                json={
                    'model': test_model,
                    'prompt': 'Antworte nur mit dem Wort "OK". Nichts anderes.',
                    'stream': False,
                    'options': {'temperature': 0.0, 'num_predict': 10},
                },
                timeout=gen_timeout,
            )
            lat = int((time.monotonic() - t0) * 1000)
            if r.status_code == 200:
                data = r.json()
                response_text = (data.get('response') or '').strip()
                eval_count = int(data.get('eval_count') or 0)
                eval_dur_ns = int(data.get('eval_duration') or 0)
                tokens_per_s = (eval_count * 1e9 / eval_dur_ns) if eval_dur_ns else 0
                add('Generation-Test', True,
                    f'Antwort von {test_model}: "{response_text[:60]}" — {lat} ms, ~{tokens_per_s:.1f} Token/s',
                    {'latency_ms': lat, 'response': response_text,
                     'tokens_per_second': round(tokens_per_s, 1),
                     'eval_count': eval_count, 'total_duration_ns': data.get('total_duration'),
                     'tested_model': test_model})
            else:
                add('Generation-Test', False,
                    f'HTTP {r.status_code}: {r.text[:200]}')
        except requests.exceptions.Timeout:
            add('Generation-Test', False,
                f'Timeout nach {gen_timeout}s. Erstes Laden eines Modells dauert oft mehrere Minuten.')
        except Exception as e:
            add('Generation-Test', False, f'{type(e).__name__}: {e}')

    return out, 200


@admin_bp.post('/ollama/echo-test')
@require_permission('admin:config')
def ollama_echo_test():
    """Live-Streaming-"Hello World"-Test: schickt einen Mini-Prompt an Ollama
    und streamt die Antwort tokenweise. Zeigt im UI sofort, ob das Modell
    überhaupt antwortet (vs. hängt). Mit Time-To-First-Token (TTFT) und
    Token/s-Messung.

    Body: { base_url?, model?, prompt? }
    """
    import json as _json
    import time as _time
    import urllib.request as _ur
    import urllib.error as _ue
    from flask import Response, stream_with_context
    from shared.ollama_config import get_ollama_config

    data = request.get_json(silent=True) or {}
    oc = get_ollama_config()
    base_url = (str(data.get('base_url') or '').strip() or oc.base_url).rstrip('/')
    model = str(data.get('model') or '').strip() or oc.model
    prompt = (str(data.get('prompt') or '').strip()
              or 'Sag "Hello, World!" und nichts anderes.')

    @stream_with_context
    def _gen():
        def _ev(name, payload):
            return f'event: {name}\ndata: {_json.dumps(payload, ensure_ascii=False)}\n\n'

        yield _ev('status', {'message': f'Verbinde mit {base_url} (Modell {model}) …'})
        t_start = _time.monotonic()
        try:
            req = _ur.Request(
                base_url + '/api/generate',
                data=_json.dumps({
                    'model': model, 'prompt': prompt, 'stream': True,
                    'options': {'temperature': 0.0, 'num_predict': 60},
                }).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            yield _ev('status', {'message': 'Sende Anfrage …'})
            chunks = []
            first_token_at = None
            with _ur.urlopen(req, timeout=oc.timeout_s) as resp:
                yield _ev('status', {'message': 'Warte auf erstes Token …'})
                for raw_line in resp:
                    line = raw_line.decode('utf-8', errors='replace').strip()
                    if not line:
                        continue
                    try:
                        obj = _json.loads(line)
                    except Exception:
                        continue
                    chunk = obj.get('response', '')
                    if chunk:
                        if first_token_at is None:
                            first_token_at = _time.monotonic() - t_start
                            yield _ev('first-token', {'ttft_ms': int(first_token_at * 1000)})
                        chunks.append(chunk)
                        yield _ev('chunk', {'text': chunk})
                    if obj.get('done'):
                        total_dur = _time.monotonic() - t_start
                        eval_count = int(obj.get('eval_count') or 0)
                        eval_dur_ns = int(obj.get('eval_duration') or 0)
                        tok_per_s = (eval_count * 1e9 / eval_dur_ns) if eval_dur_ns else 0
                        yield _ev('done', {
                            'ok': True,
                            'response': ''.join(chunks),
                            'eval_count': eval_count,
                            'tokens_per_second': round(tok_per_s, 1),
                            'total_duration_ms': int(total_dur * 1000),
                            'ttft_ms': int((first_token_at or 0) * 1000),
                            'model': model, 'base_url': base_url,
                        })
                        return
            yield _ev('done', {
                'ok': True,
                'response': ''.join(chunks),
                'total_duration_ms': int((_time.monotonic() - t_start) * 1000),
            })
        except _ue.HTTPError as e:
            try:
                body = e.read().decode('utf-8', errors='replace')
            except Exception:
                body = ''
            yield _ev('done', {
                'ok': False,
                'error': f'HTTP {e.code} {e.reason}: {body[:300]}',
                'base_url': base_url, 'model': model,
            })
        except OSError as e:
            yield _ev('done', {
                'ok': False,
                'error': f'Verbindung fehlgeschlagen: {e}',
                'base_url': base_url, 'model': model,
            })
        except Exception as e:
            yield _ev('done', {'ok': False, 'error': f'{type(e).__name__}: {e}'})

    return Response(_gen(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
    })


@admin_bp.post('/ollama/pull')
@require_permission('admin:config')
def ollama_pull():
    """Streamt einen Pull als SSE — vermeidet nginx-504-Timeouts bei großen
    Modellen (10–60 min möglich).

    Body: { "model": "llama3.1:8b" }
    Events: status, progress {completed, total, percent}, done {ok, error?}.
    """
    import json as _json
    import requests as _requests
    from flask import Response, stream_with_context
    from shared.ollama_config import get_ollama_config

    data = request.get_json(silent=True) or {}
    model = str(data.get('model') or '').strip()
    if not model:
        return {'error': 'model fehlt'}, 400

    oc = get_ollama_config()
    url = f'{oc.base_url.rstrip("/")}/api/pull'

    @stream_with_context
    def _gen():
        def _ev(name, payload):
            return f'event: {name}\ndata: {_json.dumps(payload, ensure_ascii=False)}\n\n'

        yield _ev('status', {'message': f'Starte pull für {model} …'})
        try:
            # Stream=True bei Ollama → newline-delimited JSON mit Progress
            with _requests.post(url, json={'model': model, 'stream': True},
                                stream=True, timeout=(10, None)) as r:
                if r.status_code != 200:
                    yield _ev('done', {'ok': False, 'error': f'HTTP {r.status_code}: {r.text[:200]}'})
                    return
                last_pct = -1
                for line in r.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        obj = _json.loads(line)
                    except Exception:
                        continue
                    status_msg = obj.get('status') or ''
                    completed = int(obj.get('completed') or 0)
                    total = int(obj.get('total') or 0)
                    if total > 0:
                        pct = int(completed * 100 / total)
                        if pct != last_pct:
                            last_pct = pct
                            yield _ev('progress', {
                                'status': status_msg,
                                'completed': completed, 'total': total, 'percent': pct,
                            })
                    elif status_msg:
                        yield _ev('status', {'message': status_msg})
                yield _ev('done', {'ok': True, 'model': model})
        except _requests.exceptions.ConnectionError as e:
            yield _ev('done', {'ok': False, 'error': f'Ollama nicht erreichbar: {e}'})
        except Exception as e:
            yield _ev('done', {'ok': False, 'error': f'{type(e).__name__}: {e}'})

    return Response(_gen(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',  # nginx: kein Buffering
    })


@admin_bp.delete('/ollama/models/<path:model>')
@require_permission('admin:config')
def ollama_delete_model(model: str):
    """Löscht ein installiertes Ollama-Modell (#401)."""
    import requests as _requests
    from shared.ollama_config import get_ollama_config

    oc = get_ollama_config()
    url = f'{oc.base_url.rstrip("/")}/api/delete'
    try:
        r = _requests.delete(url, json={'name': model}, timeout=30)
        if r.status_code in (200, 204):
            return {'ok': True, 'model': model}, 200
        return {'error': f'HTTP {r.status_code}: {r.text[:200]}'}, 502
    except Exception as e:
        return {'error': f'{type(e).__name__}: {e}'}, 502


@admin_bp.post('/github/test')
@require_permission('admin:config')
def github_test():
    """Verifiziert die GitHub-Verbindung mit dem aktuell konfigurierten Token.

    Macht GET /user gegen die GitHub-API; gibt user-login, scopes (falls verfügbar)
    und das Default-Repo-Existenz-Check zurück.
    Optional: Body { token: ... } um einen *noch nicht gespeicherten* Token zu testen.
    """
    import requests
    from shared.github_config import get_github_config

    data = request.get_json(silent=True) or {}
    override_token = str(data.get('token') or '').strip()

    if override_token:
        token = override_token
        gc_source = 'request'
    else:
        gc = get_github_config()
        token = gc.token
        gc_source = gc.source

    if not token:
        return {
            'ok': False, 'error': 'Kein Token konfiguriert',
            'hint': 'Token unter Einstellungen → GitHub eintragen oder ENV GH_TOKEN setzen.',
        }, 400

    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'aics-compliance-suite',
    }
    try:
        r = requests.get('https://api.github.com/user', headers=headers, timeout=10)
    except requests.RequestException as e:
        return {'ok': False, 'error': f'Netzwerkfehler: {e}'}, 502

    if r.status_code == 401:
        return {'ok': False, 'error': 'Token ungültig (401 Unauthorized)'}, 200
    if r.status_code >= 300:
        return {'ok': False, 'error': f'HTTP {r.status_code}: {r.text[:200]}'}, 200

    body = r.json()
    scopes_header = r.headers.get('X-OAuth-Scopes', '').strip()

    # Default-Repo prüfen falls gesetzt
    cfg = get_github_config()
    repo_status = None
    repo_to_check = data.get('default_repo') or cfg.default_repo
    if repo_to_check and '/' in repo_to_check:
        try:
            rr = requests.get(
                f'https://api.github.com/repos/{repo_to_check}',
                headers=headers, timeout=10,
            )
            repo_status = {
                'repo': repo_to_check,
                'exists': rr.status_code == 200,
                'private': bool(rr.json().get('private')) if rr.status_code == 200 else None,
            }
        except requests.RequestException:
            repo_status = {'repo': repo_to_check, 'exists': None, 'error': 'request-failed'}

    # #563: Probe-Read auf /contents um Fine-Grained-PAT-Permissions zu prüfen
    contents_permission = None
    if repo_to_check and '/' in repo_to_check:
        try:
            cr = requests.get(
                f'https://api.github.com/repos/{repo_to_check}/contents/README.md',
                headers=headers, timeout=10,
            )
            if cr.status_code == 200 or cr.status_code == 404:
                contents_permission = {'ok': True, 'note': 'Contents:Read funktioniert'}
            elif cr.status_code == 403:
                contents_permission = {
                    'ok': False, 'status': 403,
                    'note': "Token hat KEINE 'Contents:Read'-Permission — Repo-Scan und Pflicht-Doku-Detect funktionieren nicht. "
                            "Fix: Token bei GitHub editieren → Repository permissions → Contents: Read-only.",
                }
            else:
                contents_permission = {'ok': False, 'status': cr.status_code, 'note': cr.text[:200]}
        except requests.RequestException:
            contents_permission = {'ok': None, 'note': 'Probe-Request fehlgeschlagen'}

    return {
        'ok': True,
        'source': gc_source,
        'login': body.get('login'),
        'name': body.get('name'),
        'avatar_url': body.get('avatar_url'),
        'scopes': [s.strip() for s in scopes_header.split(',')] if scopes_header else [],
        'rate_limit_remaining': r.headers.get('X-RateLimit-Remaining'),
        'default_repo_check': repo_status,
        'contents_permission': contents_permission,
    }, 200


# ============================================================
# F0c — Audit-Log-Viewer
# ============================================================

@admin_bp.get('/audit/events')
@require_permission('admin:audit')
def list_audit_events():
    """Audit-Events listen mit Filter und Pagination."""
    module = request.args.get('module')
    outcome = request.args.get('outcome')
    action = request.args.get('action')  # #1519: z. B. ai.egress.confirmed im Revisionsbericht
    since = request.args.get('since')  # ISO-Datum
    limit = min(int(request.args.get('limit', 200)), 1000)
    offset = int(request.args.get('offset', 0))

    # #1338: KEIN Datei-Existenz-Check mehr — unter Postgres existiert die .sqlite-Datei
    # nie, der Audit-Trail liegt im Schema „audit". Tabelle bei Bedarf anlegen, dann lesen.
    try:
        from shared.audit_db import ensure_audit_db
        with closing(_sdb.connect(str(AUDIT_DB))) as conn:
            ensure_audit_db(conn)
            cur = conn.cursor()

            # Tabellen-Schema vorsichtig prüfen
            cur.execute("SELECT table_name AS name FROM information_schema.tables WHERE table_schema=current_schema()")
            tables = [r['name'] for r in cur.fetchall()]
            table = 'audit_events' if 'audit_events' in tables else (tables[0] if tables else None)
            if not table:
                return {'events': [], 'total': 0}, 200

            # Spalten dynamisch ermitteln
            cur.execute("SELECT column_name AS name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=?", (table,))
            cols = [r['name'] for r in cur.fetchall()]

            where_clauses = []
            params: List[Any] = []
            if module and 'module' in cols:
                where_clauses.append('module = ?')
                params.append(module)
            if outcome and 'outcome' in cols:
                where_clauses.append('outcome = ?')
                params.append(outcome)
            if action and 'action' in cols:
                where_clauses.append('action = ?')
                params.append(action)
            if since and 'ts' in cols:
                where_clauses.append('ts >= ?')
                params.append(since)

            where_sql = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''
            order_col = 'ts' if 'ts' in cols else cols[0]

            cur.execute(f'SELECT COUNT(*) AS c FROM "{table}" {where_sql}', params)
            total = cur.fetchone()['c']

            cur.execute(
                f'SELECT * FROM "{table}" {where_sql} ORDER BY "{order_col}" DESC LIMIT ? OFFSET ?',
                params + [limit, offset]
            )
            events = [dict(r) for r in cur.fetchall()]
        return {'events': events, 'total': total, 'limit': limit, 'offset': offset}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@admin_bp.get('/audit/export.csv')
@require_permission('admin:audit')
def export_audit_csv():
    """Audit-Events als CSV exportieren."""
    import csv
    from io import StringIO
    module = request.args.get('module')
    outcome = request.args.get('outcome')
    since = request.args.get('since')

    from shared.audit_db import ensure_audit_db
    with closing(_sdb.connect(str(AUDIT_DB))) as conn:
        ensure_audit_db(conn)
        cur = conn.cursor()
        cur.execute("SELECT table_name AS name FROM information_schema.tables WHERE table_schema=current_schema()")
        tables = [r['name'] for r in cur.fetchall()]
        table = 'audit_events' if 'audit_events' in tables else (tables[0] if tables else None)
        if not table:
            return '', 200

        cur.execute("SELECT column_name AS name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=?", (table,))
        cols = [r['name'] for r in cur.fetchall()]
        where_clauses = []
        params: List[Any] = []
        if module and 'module' in cols:
            where_clauses.append('module = ?'); params.append(module)
        if outcome and 'outcome' in cols:
            where_clauses.append('outcome = ?'); params.append(outcome)
        if since and 'ts' in cols:
            where_clauses.append('ts >= ?'); params.append(since)
        where_sql = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''

        # #1338: ORDER BY rowid war SQLite-only → unter Postgres nach id/ts sortieren.
        ocol = 'id' if 'id' in cols else ('ts' if 'ts' in cols else cols[0])
        cur.execute(f'SELECT * FROM "{table}" {where_sql} ORDER BY "{ocol}" DESC LIMIT 10000', params)
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow(cols)
        from shared.encoding import escape_csv_cell
        for row in cur.fetchall():
            writer.writerow([escape_csv_cell(row[c]) for c in cols])

    from flask import Response
    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=audit.csv'}
    )


@admin_bp.get('/audit/verify')
@require_permission('admin:audit')
def verify_audit_chain():
    """#1338: Integritätskette des Audit-Trails prüfen (SHA-256-Verkettung).

    Liefert ``{ok, count, broken_at}`` — ``broken_at`` ist die erste manipulierte/fehlende
    Zeilen-id (oder ``null``), ``count`` die Anzahl geprüfter Zeilen.
    """
    try:
        from shared.audit_db import verify_chain
        return verify_chain(), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


# ============================================================
# F0d — DB-Viewer (read-only)
# ============================================================

@admin_bp.get('/db/list')
@require_permission('admin:audit')
def list_dbs():
    """Verfügbare DBs auflisten."""
    result = []
    for key, fname in ALLOWED_DBS.items():
        path = DB_DIR / fname
        if path.exists():
            result.append({
                'key': key,
                'file': fname,
                'size_bytes': path.stat().st_size,
            })
    return result, 200


@admin_bp.get('/db/<db_key>/tables')
@require_permission('admin:audit')
def list_db_tables(db_key: str):
    """Tabellen einer DB auflisten."""
    if db_key not in ALLOWED_DBS:
        return {'error': 'Unknown DB'}, 404
    path = DB_DIR / ALLOWED_DBS[db_key]
    if not path.exists():
        return {'error': 'DB does not exist'}, 404
    with closing(_sdb.connect(str(path))) as conn:
        cur = conn.cursor()
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() ORDER BY table_name")
        tables = [r[0] for r in cur.fetchall()]
    return {'tables': tables}, 200


@admin_bp.get('/db/<db_key>/<table>')
@require_permission('admin:audit')
def query_db_table(db_key: str, table: str):
    """Tabellen-Inhalt mit Suche und Pagination (read-only)."""
    if db_key not in ALLOWED_DBS:
        return {'error': 'Unknown DB'}, 404
    if not table.replace('_', '').replace('-', '').isalnum():
        return {'error': 'Invalid table name'}, 400

    q = (request.args.get('q') or '').strip()
    limit = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))

    path = DB_DIR / ALLOWED_DBS[db_key]
    if not path.exists():
        return {'error': 'DB does not exist'}, 404

    try:
        with closing(_sdb.connect(str(path))) as conn:
            cur = conn.cursor()

            # Tabelle existiert?
            cur.execute("SELECT table_name AS name FROM information_schema.tables WHERE table_schema=current_schema() AND table_name = ?", (table,))
            if not cur.fetchone():
                return {'error': 'Table not found'}, 404

            cur.execute("SELECT column_name AS name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=?", (table,))
            cols = [r['name'] for r in cur.fetchall()]

            where_sql = ''
            params: List[Any] = []
            if q and cols:
                like_clauses = ' OR '.join([f'CAST("{c}" AS TEXT) LIKE ?' for c in cols])
                where_sql = f'WHERE {like_clauses}'
                params = [f'%{q}%' for _ in cols]

            cur.execute(f'SELECT COUNT(*) AS c FROM "{table}" {where_sql}', params)
            total = cur.fetchone()['c']

            cur.execute(
                f'SELECT * FROM "{table}" {where_sql} LIMIT ? OFFSET ?',
                params + [limit, offset]
            )
            rows = [dict(r) for r in cur.fetchall()]

        return {
            'columns': cols,
            'rows': rows,
            'total': total,
            'limit': limit,
            'offset': offset,
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


# ============================================================
# F0e — Backup (Liste, Erstellen, Restore, Löschen)
# ============================================================

@admin_bp.get('/backup')
@require_permission('admin:config')
def list_backups():
    """Vorhandene Backups auflisten."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    result = []
    # Sicherheitskopien vor einer Wiederherstellung gehören mit in die Liste —
    # sie sind der Rückweg, und wer ihn braucht, sucht ihn hier.
    archive = list(BACKUP_DIR.glob('backup_*.zip')) + list(BACKUP_DIR.glob('pre_restore_*.zip'))
    for f in sorted(archive, key=lambda p: p.name, reverse=True):
        try:
            stat = f.stat()
            result.append({
                'id': f.stem,
                'filename': f.name,
                'size_bytes': stat.st_size,
                'created_at': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                'art': 'pre_restore' if f.name.startswith('pre_restore_') else 'backup',
                **_kurzinfo(f),
            })
        except Exception:
            continue
    return result, 200


def _kurzinfo(archiv: Path) -> dict[str, Any]:
    """Format und Umfang aus dem Manifest — ohne das Archiv auszupacken.

    Steht in der Liste, weil der Unterschied zwischen einer vollständigen
    Sicherung und einem Archiv aus der SQLite-Zeit am Dateinamen nicht zu
    erkennen ist, am Inhalt aber alles hängt.
    """
    try:
        from shared.backup import lies_manifest

        m = lies_manifest(archiv)
        return {
            'format': int(m.get('format', 1)),
            'inhalt': {
                'tabellen': (m.get('datenbank') or {}).get('tabellen', 0),
                'zeilen': (m.get('datenbank') or {}).get('zeilen', 0),
                'dateien': (m.get('dateien') or {}).get('anzahl', 0),
            },
            'app_version': m.get('app_version'),
        }
    except Exception:  # noqa: BLE001 — unlesbares Archiv soll die Liste nicht kippen
        return {'format': 0, 'inhalt': None, 'app_version': None}


@admin_bp.post('/backup')
@require_permission('admin:config')
def create_backup():
    """Vollständige Sicherung erstellen (Datenbank + Dateien + Konfiguration).

    Bis v8.0.4 sammelte diese Funktion ``data/db/*.sqlite`` ein — Dateien, die
    seit der Umstellung auf PostgreSQL niemand mehr beschreibt. Die Archive
    sahen aus wie Sicherungen und enthielten den Stand der Umstellung (#1785).
    Der Inhalt steckt jetzt in :mod:`shared.backup`.
    """
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = BACKUP_DIR / f'backup_{timestamp}.zip'

    try:
        from shared.backup import erstelle_backup

        manifest = erstelle_backup(backup_path, erstellt_von=_wer_bin_ich())
        _aufraeumen_nach_aufbewahrung()

        stat = backup_path.stat()
        _audit_admin('admin.backup.created', backup_id=backup_path.stem,
                     size_bytes=stat.st_size,
                     tabellen=manifest['datenbank']['tabellen'],
                     zeilen=manifest['datenbank']['zeilen'],
                     dateien=manifest['dateien']['anzahl'])
        return {
            'id': backup_path.stem,
            'filename': backup_path.name,
            'size_bytes': stat.st_size,
            'created_at': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            'inhalt': {
                'tabellen': manifest['datenbank']['tabellen'],
                'zeilen': manifest['datenbank']['zeilen'],
                'dateien': manifest['dateien']['anzahl'],
                'konfiguration': manifest['konfiguration']['anzahl'],
            },
            'hinweise': manifest.get('hinweise', []),
        }, 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


def _wer_bin_ich() -> str:
    try:
        identity = get_jwt_identity()
    except Exception:  # noqa: BLE001
        return 'system'
    return identity if isinstance(identity, str) else str(identity or 'system')


def _aufraeumen_nach_aufbewahrung() -> None:
    """Alte Sicherungen nach der eingestellten Anzahl entfernen.

    Die Sicherheitskopien vor einer Wiederherstellung (``pre_restore_*``) zählen
    bewusst nicht mit: Sie sind der Rückweg aus einem misslungenen Restore und
    dürfen nicht von den turnusmäßigen Sicherungen verdrängt werden.
    """
    try:
        cfg = load_config()
        behalten = int(cfg.get('backup', {}).get('backup_retention_count', 5))
    except Exception:  # noqa: BLE001 — Konfiguration unlesbar: lieber nichts löschen
        return
    if behalten <= 0:
        return
    archive = sorted(BACKUP_DIR.glob('backup_*.zip'),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    for alt in archive[behalten:]:
        try:
            alt.unlink()
        except OSError:
            pass


def _upload_grenze() -> int:
    """Obergrenze für hochgeladene Archive.

    Die alten 200 MB stammten aus der Zeit, als ein Backup ein paar
    SQLite-Dateien waren. Eine vollständige Sicherung enthält jetzt auch den
    Nachweis-Store und die Gutachten-Exporte und wächst mit dem Mandanten;
    eine Grenze, die das Zurückspielen der eigenen Sicherung verhindert, ist
    keine Schutzmaßnahme, sondern ein Ausfall.
    """
    try:
        cfg = load_config()
        wert = int(cfg.get('backup', {}).get('max_upload_mb', 0) or 0)
    except Exception:  # noqa: BLE001
        wert = 0
    return (wert if wert > 0 else 4096) * 1024 * 1024


@admin_bp.post('/backup/upload')
@require_permission('admin:config')
def upload_backup():
    """Externes Backup-ZIP hochladen (Issue #356).

    Multipart: Feld `file`. Max 200 MB. Akzeptiert nur .zip mit gültiger
    Struktur (MANIFEST.json + mind. eine data/db/*.sqlite).
    """
    MAX_SIZE = _upload_grenze()
    # Das globale Limit aus #743 (64 MB) greift, bevor dieser Endpunkt
    # überhaupt läuft — eine vollständige Sicherung ist größer, und ein
    # Werkzeug, das die eigene Sicherung nicht mehr annimmt, ist im Ernstfall
    # wertlos. Flask erlaubt die Ausnahme je Request; für alle anderen
    # Endpunkte bleibt die Härtung unverändert.
    request.max_content_length = MAX_SIZE

    f = request.files.get('file')
    if not f or not f.filename:
        return {'error': 'Datei-Feld "file" fehlt'}, 400
    if not f.filename.lower().endswith('.zip'):
        return {'error': 'Nur .zip-Dateien werden akzeptiert'}, 400

    # Größe prüfen
    f.stream.seek(0, 2)  # end
    size = f.stream.tell()
    f.stream.seek(0)
    if size > MAX_SIZE:
        return {'error': f'Datei zu groß ({size // (1024*1024)} MB, '
                         f'max {MAX_SIZE // (1024*1024)} MB)'}, 413
    if size < 100:
        return {'error': 'Datei zu klein, vermutlich kein gültiges Backup'}, 400

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    # Sicherer Filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    target_name = f'backup_{timestamp}_uploaded.zip'
    target = BACKUP_DIR / target_name

    # Erst in temp speichern, dann validieren, dann verschieben
    import tempfile, shutil
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            tmp_path = tmp.name
            f.save(tmp.name)

        # Validierung: ZIP korrekt + MANIFEST + Inhalt eines der beiden Formate
        with zipfile.ZipFile(tmp_path, 'r') as zf:
            try:
                bad = zf.testzip()
                if bad:
                    return {'error': f'ZIP enthält beschädigte Datei: {bad}'}, 400
            except Exception as e:
                return {'error': f'Kein gültiges ZIP-Archiv: {e}'}, 400
            names = zf.namelist()
            if not any(n.lower() == 'manifest.json' for n in names):
                return {'error': 'MANIFEST.json fehlt — vermutlich kein Suite-Backup'}, 400
            # Format 2 trägt die Datenbank als Tabellen-Dateien, Format 1 (bis
            # v8.0.4) als SQLite-Dateien. Beides wird angenommen — ein altes
            # Archiv muss man zurückspielen können, auch wenn es nur die
            # SQLite-Reste enthält (der Bericht sagt das dann deutlich).
            hat_tabellen = any(n.startswith('db/') and n.endswith('.csv') for n in names)
            hat_sqlite = any(n.lower().startswith('data/db/')
                             and n.lower().endswith('.sqlite') for n in names)
            if not hat_tabellen and not hat_sqlite:
                return {'error': 'Weder Tabellendaten noch SQLite-Dateien gefunden — '
                                 'vermutlich kein Suite-Backup'}, 400
            # Path-Traversal-Schutz
            for n in names:
                if n.startswith('/') or '..' in Path(n).parts:
                    return {'error': f'Unsicherer Pfad im ZIP: {n}'}, 400

        shutil.move(tmp_path, target)
        tmp_path = None
        stat = target.stat()
        identity = get_jwt_identity()
        user_email = identity if isinstance(identity, str) else identity.get('email', '?')
        current_app.logger.info(
            'Backup uploaded: %s (%d bytes) by %s', target.name, stat.st_size, user_email,
        )
        return {
            'id': target.stem,
            'filename': target.name,
            'size_bytes': stat.st_size,
            'created_at': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            'uploaded': True,
        }, 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)
    finally:
        if tmp_path:
            try: os.unlink(tmp_path)
            except Exception: pass


_BACKUP_ID = re.compile(r'^backup_[A-Za-z0-9_.-]+$')


def _backup_pfad(backup_id: str) -> Path | None:
    """Pfad zum Backup, oder ``None`` wenn die ID nicht taugt.

    Die Prüfung stand dreimal als Negativliste da (``'/' in …``, ``'..' in …``)
    und wird mit jedem neuen Endpunkt ein weiteres Mal kopiert. Positivliste,
    weil hier ein Dateiname aus einer Eingabe entsteht: Was nicht ausdrücklich
    erlaubt ist, fällt durch — und ein Punkt-Segment kann so nicht entstehen,
    auch nicht in einer Schreibweise, an die die Negativliste nicht gedacht hat.
    """
    if not _BACKUP_ID.match(str(backup_id or '')) or '..' in backup_id:
        return None
    pfad = (BACKUP_DIR / f'{backup_id}.zip').resolve()
    # Doppelter Boden: Der Pfad muss im Backup-Verzeichnis liegen.
    if BACKUP_DIR.resolve() not in pfad.parents:
        return None
    return pfad


@admin_bp.get('/backup/<backup_id>/download')
@require_permission('admin:config')
def download_backup(backup_id: str):
    """Backup herunterladen.

    Ohne diesen Weg lag das Backup nur dort, wo auch die Daten liegen — im
    Container bzw. auf demselben Volume. Gegen einen Hardware- oder
    Volume-Verlust hilft es damit nicht, und genau dafür macht man es. Der
    Upload (#356) konnte eine Sicherung zurückbringen, aber niemand kam an die
    Datei, die man dafür braucht; herausholen ließ sie sich nur über eine Shell
    im Container.

    Der Abzug ist vollständig (alle Modul-Datenbanken inkl. Benutzertabelle und
    Live-Config) und gehört deshalb in den Revisionspfad, nicht nur ins
    Server-Log: Wer eine Kopie des gesamten Datenbestands aus dem Haus trägt,
    ist die Frage, die nach einem Vorfall gestellt wird — und das Log rotiert,
    der Audit-Trail nicht.
    """
    pfad = _backup_pfad(backup_id)
    if pfad is None:
        return {'error': 'Invalid backup id'}, 400
    if not pfad.exists():
        return {'error': 'Backup not found'}, 404
    try:
        groesse = pfad.stat().st_size
        _audit_admin('admin.backup.downloaded', backup_id=backup_id,
                     size_bytes=groesse)
        return send_file(pfad, mimetype='application/zip', as_attachment=True,
                         download_name=pfad.name)
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@admin_bp.delete('/backup/<backup_id>')
@require_permission('admin:config')
def delete_backup(backup_id: str):
    """Backup löschen."""
    path = _backup_pfad(backup_id)
    if path is None:
        return {'error': 'Invalid backup id'}, 400
    if not path.exists():
        return {'error': 'Backup not found'}, 404
    try:
        path.unlink()
        return {'deleted': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@admin_bp.get('/backup/<backup_id>/inhalt')
@require_permission('admin:config')
def backup_inhalt(backup_id: str):
    """Was in einem Archiv steckt — **vor** dem Einspielen.

    Eine Wiederherstellung überschreibt den Datenbestand. Wer sie auslöst, soll
    vorher sehen, was er einspielt, statt sich auf einen Dateinamen zu verlassen
    — besonders seit es Archive in zwei Formaten gibt und die alten die
    Nutzdaten gar nicht enthalten.
    """
    pfad = _backup_pfad(backup_id)
    if pfad is None:
        return {'error': 'Invalid backup id'}, 400
    if not pfad.exists():
        return {'error': 'Backup not found'}, 404
    try:
        from shared.backup import beschreibe

        return beschreibe(pfad), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': f'Archiv nicht lesbar: {e}'}, 400


@admin_bp.post('/users/<user_id>/mfa/reset')
@require_permission('admin:users')
def reset_mfa(user_id: str):
    """Zweiten Faktor eines Kontos zurücksetzen (#1811).

    Gebraucht, wenn ein Passkey durch einen Hostnamen-Wechsel wertlos geworden
    ist: Das Konto verlangt dann einen Faktor, den es nicht mehr erfüllen kann,
    und sperrt sich selbst aus. Der Vorgang gehört in den Revisionspfad — wer
    einem Konto den zweiten Faktor nimmt, ist nach einem Vorfall die erste
    Frage.
    """
    from server.auth import users_db as _u

    konto = _u.get_user_by_id(user_id) if hasattr(_u, 'get_user_by_id') else None
    if konto is None:
        for k in _u.list_users():
            if str(k.get('id')) == str(user_id):
                konto = k
                break
    if konto is None:
        return {'error': 'Benutzer nicht gefunden'}, 404

    weg = _u.zweiten_faktor_zuruecksetzen(user_id)
    _audit_admin('admin.user.mfa_reset', ziel_user=user_id,
                 ziel_email=konto.get('email'),
                 passkeys=weg.get('passkeys'))
    current_app.logger.info('MFA zurückgesetzt für %s (%s Passkey(s))',
                            konto.get('email'), weg.get('passkeys'))
    return {
        'reset': True,
        'email': konto.get('email'),
        'entfernte_passkeys': weg.get('passkeys'),
        'hinweis': 'Das Konto meldet sich jetzt mit Kennwort an und kann einen '
                   'neuen Passkey unter dem aktuellen Hostnamen registrieren. '
                   'Alle offenen Sitzungen wurden beendet.',
    }, 200


@admin_bp.get('/backup/<backup_id>/vorschau')
@require_permission('admin:config')
def backup_vorschau(backup_id: str):
    """Was das Einspielen ändern würde — vor dem Klick (#1809).

    Der Bestätigungsdialog fragte bisher, ob man sicher sei, nannte aber keine
    Zahlen. Dabei weiß die Anwendung alles Nötige: Das Archiv trägt seine
    Zeilenzahlen, das Ziel die eigenen. Ein „Sind Sie sicher?" ohne Zahlen ist
    keine Warnung.
    """
    path = _backup_pfad(backup_id)
    if path is None:
        return {'error': 'Invalid backup id'}, 400
    if not path.exists():
        return {'error': 'Backup not found'}, 404
    umfang = str(request.args.get('umfang') or 'fachdaten')
    try:
        from shared.backup.paket import UMFAENGE, vergleiche
        if umfang not in UMFAENGE:
            return {'error': f'Unbekannter Umfang: {umfang}', 'erlaubt': list(UMFAENGE)}, 400
        return vergleiche(path, umfang=umfang), 200
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception('Backup-Vorschau fehlgeschlagen')
        return {'error': f'Archiv nicht lesbar: {e}'}, 400

@admin_bp.post('/backup/<backup_id>/restore')
@require_permission('admin:config')
def restore_backup(backup_id: str):
    """Sicherung einspielen: Datenbank, Dateien und Konfiguration.

    Vorher wird der aktuelle Stand als ``pre_restore_*`` gesichert — der Rückweg,
    wenn sich das eingespielte Archiv als das falsche erweist.
    """
    path = _backup_pfad(backup_id)
    if path is None:
        return {'error': 'Invalid backup id'}, 400
    if not path.exists():
        return {'error': 'Backup not found'}, 404

    daten = request.get_json(silent=True) or {}
    if daten.get('confirm') != backup_id:
        return {'error': 'Confirmation required: send {"confirm": "<backup_id>"}'}, 400

    # #1813: Was eingespielt wird, entscheidet der Betreiber.
    # Vorgabe bleibt `alles` — bestehende Aufrufer und gespeicherte Abläufe
    # sollen sich nicht stillschweigend anders verhalten. Die Oberfläche
    # wählt `fachdaten` vor, weil das der häufigere Fall ist.
    from shared.backup.paket import UMFAENGE
    umfang = str(daten.get('umfang') or 'alles')
    if umfang not in UMFAENGE:
        return {'error': f'Unbekannter Umfang: {umfang}',
                'erlaubt': list(UMFAENGE)}, 400

    try:
        from shared.backup import erstelle_backup, stelle_wieder_her

        sicherheitskopie = None
        try:
            ziel = BACKUP_DIR / f'pre_restore_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
            erstelle_backup(ziel, erstellt_von=f'vor Restore {backup_id}')
            sicherheitskopie = ziel.stem
        except Exception as e:  # noqa: BLE001
            # Keine Sicherheitskopie heißt: kein Rückweg. Das ist eine
            # Entscheidung des Menschen, nicht der Anwendung — ohne
            # ausdrückliches Einverständnis wird hier abgebrochen.
            if not daten.get('ohne_sicherheitskopie'):
                current_app.logger.exception('Sicherheitskopie vor Restore fehlgeschlagen')
                return {
                    'error': 'Sicherheitskopie vor der Wiederherstellung fehlgeschlagen — '
                             'abgebrochen. Mit "ohne_sicherheitskopie": true trotzdem fortfahren.',
                    'detail': str(e)[:300],
                }, 409

        bericht = stelle_wieder_her(path, umfang=umfang)

        _audit_admin('admin.backup.restored', backup_id=backup_id,
                     umfang=umfang,
                     format=bericht.get('format'),
                     tabellen=bericht.get('tabellen'), zeilen=bericht.get('zeilen'),
                     dateien=bericht.get('dateien'),
                     warnungen=len(bericht.get('warnungen') or []),
                     safety_backup=sicherheitskopie)
        current_app.logger.info(
            'Backup-Restore: id=%s format=%s tabellen=%s zeilen=%s dateien=%s safety=%s',
            backup_id, bericht.get('format'), bericht.get('tabellen'),
            bericht.get('zeilen'), bericht.get('dateien'), sicherheitskopie)

        return {
            'restored': True,
            'umfang': umfang,
            'uebersprungen': bericht.get('uebersprungen') or [],
            'safety_backup': sicherheitskopie,
            'format': bericht.get('format'),
            'tabellen': bericht.get('tabellen'),
            'zeilen': bericht.get('zeilen'),
            'dateien': bericht.get('dateien'),
            'konfiguration': bericht.get('konfiguration'),
            'warnungen': bericht.get('warnungen') or [],
            'hinweis': 'Die Anwendung sollte jetzt neu gestartet werden, damit alle '
                       'Arbeitsprozesse den wiederhergestellten Stand lesen.',
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@admin_bp.get('/backup/<backup_id>/mandanten')
@require_permission('admin:config')
def backup_mandanten(backup_id: str):
    """Welche Mandanten und Projekte das Archiv enthält (#1808).

    Grundlage für die Auswahl beim Übernehmen — und für die Kollisionsfrage:
    Je Position steht dabei, ob es sie auf dieser Installation schon gibt.

    Eigener Pfad neben ``/inhalt``: Das beschreibt das Archiv als Ganzes
    (Format, Zahlen, Warnungen) und wird vor jedem Einspielen geladen. Hier
    geht es um die Auswahl, und dafür muss jede Projekttabelle gelesen werden —
    das gehört nicht in einen Aufruf, der nur den Dateinamen bestätigen soll.
    """
    path = _backup_pfad(backup_id)
    if path is None:
        return {'error': 'Invalid backup id'}, 400
    if not path.exists():
        return {'error': 'Backup not found'}, 404
    try:
        from shared.backup.uebernehmen import inhalt
        return inhalt(path), 200
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception('Archiv-Inhalt nicht lesbar')
        return {'error': f'Archiv nicht lesbar: {e}'}, 400


@admin_bp.post('/backup/<backup_id>/uebernehmen')
@require_permission('admin:config')
def backup_uebernehmen(backup_id: str):
    """Daten eines Mandanten **einfügen**, ohne den Bestand zu löschen (#1808/#1810).

    Der Gegenentwurf zum Restore: kein ``TRUNCATE``, keine Sicherheitskopie
    nötig, weil nichts verloren gehen kann. Was im Ziel schon steht, bleibt —
    es sei denn, der Betreiber wählt für einen Mandanten ausdrücklich
    ``bei_kollision: "ersetzen"``.

    Aus dem Betrieb (der Befund hinter diesem Endpunkt): Ein Archiv der
    Testinstanz wurde auf der Produktivinstallation eingespielt, in der
    Erwartung, die Daten kämen dazu. Elf von zwölf Mandanten waren danach weg.
    """
    path = _backup_pfad(backup_id)
    if path is None:
        return {'error': 'Invalid backup id'}, 400
    if not path.exists():
        return {'error': 'Backup not found'}, 404

    daten = request.get_json(silent=True) or {}
    mandanten = [str(m) for m in (daten.get('mandanten') or []) if str(m).strip()]
    if not mandanten:
        return {'error': 'Es wurde kein Mandant ausgewählt.'}, 400

    from shared.backup.uebernehmen import KOLLISIONEN, UebernahmeFehler, uebernimm
    bei_kollision = str(daten.get('bei_kollision') or 'behalten')
    if bei_kollision not in KOLLISIONEN:
        return {'error': f'Unbekannte Kollisionsregel: {bei_kollision}',
                'erlaubt': list(KOLLISIONEN)}, 400

    trockenlauf = bool(daten.get('trockenlauf'))
    mit_benutzern = bool(daten.get('mit_benutzern'))
    # Vorgabe an: Die Datensätze verweisen auf Dateien (Vorlagen, Nachweise,
    # finalisierte Gutachten). Ohne sie zeigt jeder Download ins Leere, und das
    # sieht nach einem Defekt aus statt nach einer halben Übernahme.
    mit_dateien = bool(daten.get('mit_dateien', True))
    # Ersetzen löscht Zeilen — das bestätigt der Betreiber ausdrücklich, wie
    # beim Restore. Der Trockenlauf braucht keine Bestätigung: Er schreibt nicht.
    if bei_kollision == 'ersetzen' and not trockenlauf and daten.get('confirm') != backup_id:
        return {'error': 'Confirmation required: send {"confirm": "<backup_id>"}',
                'grund': 'ersetzen entfernt die vorhandenen Daten dieser Mandanten'}, 428

    # Die Zusage dieses Endpunkts ist „es geht nichts verloren" — `ersetzen`
    # bricht sie als einziger Weg. Dann gilt dieselbe Regel wie beim Restore:
    # erst eine Sicherheitskopie, und kein Rückweg ist eine Entscheidung des
    # Menschen, nicht der Anwendung. Beim Übernehmen *ohne* Ersetzen entfällt
    # sie — eine minutenlange Vollsicherung für einen Vorgang, der nur einfügt,
    # wäre Zeremonie.
    sicherheitskopie = None
    if bei_kollision == 'ersetzen' and not trockenlauf:
        try:
            ziel = BACKUP_DIR / f'pre_restore_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
            from shared.backup import erstelle_backup
            erstelle_backup(ziel, erstellt_von=f'vor Übernahme (ersetzen) aus {backup_id}')
            sicherheitskopie = ziel.stem
        except Exception as e:  # noqa: BLE001
            if not daten.get('ohne_sicherheitskopie'):
                current_app.logger.exception('Sicherheitskopie vor Übernahme fehlgeschlagen')
                return {
                    'error': 'Sicherheitskopie vor dem Ersetzen fehlgeschlagen — '
                             'abgebrochen. Mit "ohne_sicherheitskopie": true trotzdem '
                             'fortfahren.',
                    'detail': str(e)[:300],
                }, 409

    try:
        bericht = uebernimm(path, mandanten=mandanten,
                            bei_kollision=bei_kollision,
                            mit_benutzern=mit_benutzern,
                            mit_dateien=mit_dateien,
                            trockenlauf=trockenlauf)
    except (UebernahmeFehler, ValueError) as e:
        return {'error': str(e)}, 400
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path,
                                     type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Log (#737)

    if not trockenlauf:
        _audit_admin('admin.backup.uebernommen', backup_id=backup_id,
                     mandanten=bericht.get('mandanten'),
                     uebersprungen=bericht.get('uebersprungen'),
                     mit_benutzern=mit_benutzern, bei_kollision=bei_kollision,
                     tabellen=bericht.get('tabellen'), zeilen=bericht.get('zeilen'),
                     warnungen=len(bericht.get('warnungen') or []),
                     safety_backup=sicherheitskopie)
    return {'uebernommen': not trockenlauf,
            'safety_backup': sicherheitskopie, **bericht}, 200


# ════════════════════════════════════════════════════════════════════
# Support-Bundle (#1509): ZIP aller fehlersuche-relevanten Logs + Diagnose
# ════════════════════════════════════════════════════════════════════

LOG_DIR = Path('logs')

# Nur unkritische Env-Variablen ins Bundle (NIEMALS DATABASE_URL/JWT/Secrets/Token).
_ENV_WHITELIST = (
    'AICS_PORTAL', 'FLASK_ENV', 'GOTENBERG_URL', 'ENABLE_DEMO_USERS',
    'GUNICORN_WORKERS', 'TZ', 'LANG', 'PYTHONUNBUFFERED', 'DB_NAME', 'DB_HOST',
    'DB_PORT',  # nur Name/Host/Port — KEIN Passwort/URL
)


def _app_version() -> str:
    """App-Version mit Fallback-Kette (#1516):
    1. ENV ``APP_VERSION`` (build-zeitlich ins Image injiziert, siehe Dockerfile),
    2. ``/app/VERSION`` (falls vorhanden),
    3. ``frontend/package.json`` (Dev-Lauf aus dem Repo-Root),
    sonst ``'unknown'``."""
    env_v = (os.environ.get('APP_VERSION') or '').strip()
    if env_v and env_v.lower() != 'unknown':
        return env_v
    try:
        vf = Path('/app/VERSION')
        if vf.exists():
            v = vf.read_text(encoding='utf-8').strip()
            if v:
                return v
    except Exception:
        pass
    try:
        pkg = json.loads(Path('frontend/package.json').read_text(encoding='utf-8'))
        return str(pkg.get('version') or 'unknown')
    except Exception:
        return 'unknown'


def _build_support_manifest() -> Dict[str, Any]:
    import platform
    import sys
    dbs = []
    for key, fname in ALLOWED_DBS.items():
        fp = DB_DIR / fname
        try:
            size = fp.stat().st_size if fp.exists() else None
        except Exception:
            size = None
        dbs.append({'key': key, 'file': fname, 'size_bytes': size})
    return {
        'generated_at': datetime.now(tz=timezone.utc).isoformat(),
        'app_version': _app_version(),
        'python_version': sys.version,
        'platform': platform.platform(),
        'database_engine': 'postgresql' if os.environ.get('DATABASE_URL') else 'sqlite/local',
        'databases': dbs,
        'env_whitelist': {k: os.environ.get(k) for k in _ENV_WHITELIST if os.environ.get(k) is not None},
        'note': (
            'Container-stdout/stderr ist hier NICHT enthalten — bei Bedarf '
            'zusätzlich `docker logs <container>` beilegen. Secrets/PII sind '
            'redigiert (Config maskiert, Env nur Whitelist, kein users.sqlite).'
        ),
    }


@admin_bp.get('/support-bundle')
@require_permission('admin:config')
def support_bundle():
    """Support-Bundle als ZIP: alle relevanten Logdateien + Diagnose, Secrets
    redigiert (#1509). GET → streamt direkt als Download."""
    import io
    try:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 1) Logdateien (app.log + rotiert, audit.log + rotiert)
            if LOG_DIR.exists():
                for p in sorted(LOG_DIR.glob('*.log*')):
                    if p.is_file():
                        zf.write(p, f'logs/{p.name}')
            # Backup-Operationslog (falls vorhanden)
            backup_log = BACKUP_DIR / 'backup.log'
            if backup_log.exists():
                zf.write(backup_log, 'logs/backup.log')
            # 2) Diagnose-DBs: Audit-Trail + Scheduler (KEINE users.sqlite/PII-DBs)
            for fname in ('audit.sqlite', 'scheduler.sqlite'):
                fp = DB_DIR / fname
                if fp.exists():
                    zf.write(fp, f'data/db/{fname}')
            # 3) Redigierte Live-Config (Secrets maskiert)
            try:
                # _mask_sensitive (bekannte Pfade) + rekursive Secret-Redaction
                # (alle token/api_key/secret/password-Felder) als Sicherheitsnetz.
                cfg_redacted = _deep_redact_secrets(_mask_sensitive(load_config()))
            except Exception:
                cfg_redacted = {'error': 'config konnte nicht geladen werden'}
            zf.writestr('config.redacted.json',
                        json.dumps(cfg_redacted, indent=2, ensure_ascii=False))
            # 4) Manifest mit Version/Plattform/DB-Übersicht/Env-Whitelist
            zf.writestr('MANIFEST.json',
                        json.dumps(_build_support_manifest(), indent=2, ensure_ascii=False))
        buf.seek(0)
        try:
            from shared.audit import audit_event
            audit_event('admin.support_bundle.created', outcome='success')
        except Exception:
            pass
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        return send_file(buf, mimetype='application/zip', as_attachment=True,
                         download_name=f'support-bundle_{ts}.zip')
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


# ════════════════════════════════════════════════════════════════════
# Update- & Versionskontrolle (#1512): Version-Check + Portainer-Redeploy
# ════════════════════════════════════════════════════════════════════

def _parse_semver(v: str):
    """'6.25.0' → (6,25,0); robust gegen 'v'-Präfix/Suffixe. Fehler → None."""
    try:
        core = str(v or '').strip().lstrip('vV').split('-')[0].split('+')[0]
        parts = [int(x) for x in core.split('.')[:3]]
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    except Exception:
        return None


def _fetch_latest_version(cfg: Dict[str, Any]) -> 'str | None':
    """Neueste Version best-effort ermitteln. Quellen (in dieser Reihenfolge):
    1. Manueller Override ``update.latest_version`` (Air-Gapped/Offline-Betrieb).
    2. ``update.version_check_url`` → JSON, Feld ``version``/``tag_name``/``latest``.
    Netz-/Parse-Fehler → None (kein Hard-Fail)."""
    upd = (cfg.get('update') or {}) if isinstance(cfg, dict) else {}
    manual = str(upd.get('latest_version') or '').strip()
    if manual:
        return manual
    url = str(upd.get('version_check_url') or '').strip()
    if not url:
        return None
    try:
        import requests
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return None
        data = resp.json()
        for key in ('version', 'tag_name', 'latest', 'name'):
            if isinstance(data, dict) and data.get(key):
                return str(data[key]).strip()
    except Exception:
        return None
    return None


@admin_bp.get('/version')
@require_permission('admin:config')
def get_version_info():
    """Installierte Version + (best-effort) neueste verfügbare Version (#1512)."""
    cfg = {}
    try:
        cfg = load_config()
    except Exception:
        pass
    current = _app_version()
    latest = _fetch_latest_version(cfg)
    update_available = None
    if latest:
        cv, lv = _parse_semver(current), _parse_semver(latest)
        if cv is not None and lv is not None:
            update_available = lv > cv
        else:
            update_available = (latest != current)
    # Update-Trigger nur möglich, wenn Portainer-Zugangsdaten hinterlegt sind.
    portainer = (cfg.get('integrations', {}) or {}).get('portainer', {}) if isinstance(cfg, dict) else {}
    update_configured = bool(
        portainer.get('base_url') and portainer.get('stack_id')
        and _resolve_portainer_key(portainer)  # #1534: Env-Var ODER verschlüsselte Config
    )
    return jsonify({
        'current': current,
        'latest': latest,
        'update_available': update_available,
        'update_configured': update_configured,
        'checked_at': datetime.now(tz=timezone.utc).isoformat(),
    }), 200


@admin_bp.post('/update')
@require_permission('admin:config')
def trigger_update():
    """Stößt ein Update an: Portainer-Stack mit Image-Pull redeployen (#1512).

    Nur möglich, wenn ``integrations.portainer`` (base_url, stack_id, endpoint_id,
    api_key_env) hinterlegt **und** der API-Key in der Umgebung gesetzt ist. Sonst
    412. Mächtige, outward-facing Aktion → admin-only + Audit."""
    try:
        cfg = load_config()
    except Exception:
        cfg = {}
    portainer = (cfg.get('integrations', {}) or {}).get('portainer', {}) if isinstance(cfg, dict) else {}
    base_url = str(portainer.get('base_url') or '').strip().rstrip('/')
    stack_id = portainer.get('stack_id')
    endpoint_id = portainer.get('endpoint_id')
    api_key = _resolve_portainer_key(portainer)  # #1534: Env-Var ODER verschlüsselte Config
    # #1512/#1534: TLS-Verifikation. Default True (sicher); für internes self-signed
    # Portainer über verify_tls=false abschaltbar (nur vertrauenswürdige interne Hosts).
    verify_tls = bool(portainer.get('verify_tls', True))

    if not (base_url and stack_id and api_key):
        return jsonify({
            'error': 'Update nicht konfiguriert',
            'detail': 'Es sind keine Portainer-Zugangsdaten hinterlegt '
                      '(base_url, stack_id, api_key_env/api_key + gesetzter API-Key).',
        }), 412

    try:
        import requests
        if not verify_tls:
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except Exception:
                pass
        headers = {'X-API-Key': api_key}
        # Aktuelle Stack-Definition holen (Compose-File + Env benötigt Portainer beim Update).
        params = {'endpointId': endpoint_id} if endpoint_id else {}
        sf = requests.get(f'{base_url}/api/stacks/{stack_id}/file', headers=headers,
                          params=params, timeout=15, verify=verify_tls)
        stack_file = ''
        if sf.status_code == 200:
            stack_file = (sf.json() or {}).get('StackFileContent', '')
        # Redeploy mit Image-Pull.
        payload = {'pullImage': True, 'prune': False}
        if stack_file:
            payload['stackFileContent'] = stack_file
        up = requests.put(f'{base_url}/api/stacks/{stack_id}', headers=headers,
                          params=params, json=payload, timeout=120, verify=verify_tls)
        ok = up.status_code in (200, 201)
        try:
            from shared.audit import audit_event
            audit_event('admin.update.triggered',
                        outcome='success' if ok else 'failure',
                        details={'stack_id': stack_id, 'status': up.status_code})
        except Exception:
            pass
        if not ok:
            current_app.logger.warning('Portainer-Update fehlgeschlagen: %s %s',
                                       up.status_code, up.text[:300])
            return jsonify({'error': 'Update-Trigger fehlgeschlagen',
                            'status': up.status_code}), 502
        return jsonify({'ok': True, 'message': 'Update angestoßen (Stack-Redeploy mit Image-Pull).'}), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return jsonify({'error': 'Interner Serverfehler'}), 500


@admin_bp.post('/update/test-connection')
@require_permission('admin:config')
def test_portainer_connection():
    """#1534: Portainer-Zugangsdaten read-only prüfen (GET Stack-File, KEIN Redeploy).
    Liefert ok/Fehler fürs Settings-Formular (200 auch bei Verbindungsfehler → UI-Feedback)."""
    try:
        cfg = load_config()
    except Exception:
        cfg = {}
    portainer = (cfg.get('integrations', {}) or {}).get('portainer', {}) if isinstance(cfg, dict) else {}
    base_url = str(portainer.get('base_url') or '').strip().rstrip('/')
    stack_id = portainer.get('stack_id')
    endpoint_id = portainer.get('endpoint_id')
    api_key = _resolve_portainer_key(portainer)
    verify_tls = bool(portainer.get('verify_tls', True))
    if not (base_url and stack_id and api_key):
        return jsonify({'ok': False, 'error': 'base_url, stack_id und ein API-Key sind erforderlich.'}), 412
    try:
        import requests
        if not verify_tls:
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except Exception:
                pass
        params = {'endpointId': endpoint_id} if endpoint_id else {}
        r = requests.get(f'{base_url}/api/stacks/{stack_id}/file',
                         headers={'X-API-Key': api_key}, params=params, timeout=15, verify=verify_tls)
        if r.status_code == 200:
            return jsonify({'ok': True, 'message': f'Verbindung OK — Stack {stack_id} erreichbar.'}), 200
        return jsonify({'ok': False, 'error': f'Portainer antwortete mit HTTP {r.status_code}.'}), 200
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Verbindung fehlgeschlagen: {type(e).__name__}'}), 200


# ════════════════════════════════════════════════════════════════════
# S1 (#1071): Firmen-FK-Härtung — Backfill, Übersicht, manuelle Zuordnung
# ════════════════════════════════════════════════════════════════════

from shared.firmen_link import (  # noqa: E402
    MODULE_PROJECT_TABLES as _FK_TABLES,
    backfill_firmen_ids as _fk_backfill,
    ensure_firmen_id_column as _fk_ensure,
)


@admin_bp.post('/firmen-link/backfill')
@require_permission('admin:users')
def firmen_link_backfill():
    """firmen_id in allen Modul-Projekttabellen per Name-Match befüllen."""
    out: Dict[str, Any] = {}
    for dbfile, (table, name_col) in _FK_TABLES.items():
        p = DB_DIR / dbfile
        # #1511: Kein .exists()-Guard — unter Postgres existieren keine .sqlite-
        # Dateien (Schema-Mapping). Fehlt Schema/Tabelle, fängt der except sauber ab.
        try:
            out[dbfile] = _fk_backfill(p, table, name_col=name_col)
        except Exception as e:  # pragma: no cover - defensiv
            out[dbfile] = {'error': str(e)}
    return jsonify({'results': out}), 200


@admin_bp.get('/firmen-link/unassigned')
@require_permission('admin:users')
def firmen_link_unassigned():
    """Projekte mit nicht-leerem Firmennamen, aber ohne firmen_id (unklare Fälle)."""
    out: Dict[str, Any] = {}
    for dbfile, (table, name_col) in _FK_TABLES.items():
        p = DB_DIR / dbfile
        # #1511: kein .exists()-Guard (Postgres-Schema-Mapping). Antwort ist
        # IMMER eine Liste (frontend-sicher) — auch bei Fehlern/fehlenden Spalten.
        out[dbfile] = []
        try:
            con = _sdb.connect(str(p))
            try:
                _fk_ensure(con, table)
                cols = {r[0] for r in con.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema=current_schema() AND table_name=?", (table,))}
                # Manche Tabellen (z. B. SOC soc_assets) haben keine 'name'-Projekt-
                # spalte → für diese Übersicht nicht relevant, sauber überspringen.
                if 'name' not in cols or name_col not in cols:
                    continue
                rows = con.execute(
                    f"SELECT name, {name_col} FROM {table} "
                    f"WHERE firmen_id IS NULL AND TRIM(COALESCE({name_col},'')) <> ''"
                ).fetchall()
                out[dbfile] = [{'projekt': r[0], 'unternehmen': r[1]} for r in rows]
            finally:
                con.close()
        except Exception as e:  # pragma: no cover - defensiv
            current_app.logger.warning('firmen-link/unassigned %s: %s', dbfile, e)
    return jsonify({'unassigned': out}), 200


@admin_bp.post('/firmen-link/assign')
@require_permission('admin:users')
def firmen_link_assign():
    """Manuelle Zuordnung Projekt → Firma (firmen_id)."""
    data = request.get_json(silent=True) or {}
    dbfile = data.get('module')
    projekt = (data.get('projekt') or '').strip()
    firmen_id = data.get('firmen_id')
    entry = _FK_TABLES.get(dbfile)
    if not entry or not projekt or not firmen_id:
        return jsonify({'error': 'module, projekt, firmen_id erforderlich'}), 400
    table = entry[0]
    p = DB_DIR / dbfile
    # #1511: kein .exists()-Guard (Postgres-Schema-Mapping).
    con = _sdb.connect(str(p))
    try:
        _fk_ensure(con, table)
        cur = con.execute(
            f"UPDATE {table} SET firmen_id=? WHERE name=?", (int(firmen_id), projekt)
        )
        con.commit()
        if cur.rowcount == 0:
            return jsonify({'error': 'Projekt nicht gefunden'}), 404
    finally:
        con.close()
    return jsonify({'ok': True}), 200


# ════════════════════════════════════════════════════════════════════
# Sprint #50: Lizenzmanagement — Mandanten, Abrechnung, Preisblatt
# (#1705/#1706/#1707/#1708)
# ════════════════════════════════════════════════════════════════════

def _lizenz_module() -> 'set[str] | None':
    """Modul-Whitelist der aktiven Lizenz (``None`` = Wildcard ``*``)."""
    try:
        from server.license_state import get_state
        return get_state().is_module_allowed
    except Exception:  # noqa: BLE001 — ohne Lizenz-State alles ausweisen
        return None


@admin_bp.get('/licensing/usage')
@require_permission('admin:config')
def licensing_usage():
    """Mandanten-/Abrechnungsreport zum Stichtag.

    Query: ``format=csv`` liefert den Report als CSV-Download,
    ``inaktiv_ab_tagen`` verschiebt die „ruhend"-Schwelle (Default 180).
    """
    from shared.licensing.usage import build_usage, usage_csv, DEFAULT_INAKTIV_AB_TAGEN
    try:
        tage = int(request.args.get('inaktiv_ab_tagen') or DEFAULT_INAKTIV_AB_TAGEN)
    except ValueError:
        return {'error': 'inaktiv_ab_tagen muss eine Zahl sein'}, 400
    if not (1 <= tage <= 3650):
        return {'error': 'inaktiv_ab_tagen muss zwischen 1 und 3650 liegen'}, 400

    try:
        report = build_usage(lizenz_module=_lizenz_module(), inaktiv_ab_tagen=tage)
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path,
                                     type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500

    if (request.args.get('format') or '').lower() == 'csv':
        from flask import Response
        name = f"aics-abrechnung-{report['stichtag']}.csv"
        # BOM, damit Excel die UTF-8-Umlaute ohne Nachfrage richtig liest.
        return Response(
            '﻿' + usage_csv(report),
            mimetype='text/csv; charset=utf-8',
            headers={'Content-Disposition': f'attachment; filename="{name}"'},
        )
    return jsonify(report), 200


# Preisblatt-Endpunkte gab es bis v8.0.11 an dieser Stelle (GET/PUT
# /licensing/preisblatt). Sie sind entfallen (#1821): Preise gehören auf die
# Seite des Vermieters, nicht in die Installation des Kunden. Gepflegt wird das
# Preisblatt im Lizenzserver, der die Abrechnung ohnehin aus dem gemeldeten
# Mandanten-Inventar rechnet; die Suite meldet Zahlen und zeigt Zahlen —
# Mandanten, Module, Benutzer — aber keine Beträge.
#
# Der zweite Grund ist handfester: Es gab das Preisblatt zweimal, hier und im
# Lizenzserver, und beide waren bereits auseinandergelaufen (CRA 150 gegen
# 190 €). Zwei Preislisten sind eine zu viel.


@admin_bp.get('/tenancy/report')
@require_permission('admin:config')
def tenancy_report_endpoint():
    """Mandantenfähigkeits-Selbstprüfung: Projekte ohne firmen_id, Waisen, Score."""
    from shared.tenancy import tenancy_report
    try:
        return jsonify(tenancy_report()), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path,
                                     type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


@admin_bp.get('/licensing/modules')
@require_permission('admin:config')
def licensing_modules():
    """Modul-Registry + Lizenzstatus je Modul (was ist an, was kostet extra)."""
    from shared.licensing import modules as lic
    allowed = _lizenz_module()
    return jsonify({
        'grundpreis_module': list(lic.BASE_MODULES),
        'zusatzmodule': list(lic.SELLABLE_MODULES),
        'nicht_im_angebot': list(lic.EXPLICIT_MODULES),
        'ungegated': list(lic.UNGATED_MODULES),
        'labels': lic.MODULE_LABELS,
        'effektiv': lic.effective_modules(allowed),
        'abrechenbar': lic.billable_modules(allowed),
    }), 200


@admin_bp.post('/licensing/report-now')
@require_permission('admin:config')
def licensing_report_now():
    """#1713: Mandanten-Inventar sofort an den Lizenzserver melden.

    Erzwingt die Übertragung der vollständigen Liste (sonst reist sie nur bei
    Änderung mit) — für „ich will jetzt abrechnen" ohne auf den nächsten
    Heartbeat zu warten.
    """
    from server import license_state
    if not license_state.get_state().token:
        return {'error': 'no-token',
                'message': 'Keine aktive Lizenz — bitte erst aktivieren.'}, 400
    try:
        resp = license_state.send_heartbeat(force_inventory=True)
    except Exception as e:
        current_app.logger.warning('Mandanten-Meldung fehlgeschlagen: %s', e)
        return {'error': 'report-failed', 'message': str(e)}, 502
    try:
        from shared.audit import audit_event
        audit_event('licensing.mandanten_reported', module='licensing',
                    details={'digest': resp.get('mandanten_digest'),
                             'uebertragen': resp.get('mandanten_uebertragen')})
    except Exception:  # noqa: BLE001
        pass
    return jsonify({'ok': True, **{k: v for k, v in resp.items() if k != 'token'}}), 200


@admin_bp.get('/licensing/report-state')
@require_permission('admin:config')
def licensing_report_state():
    """Was wurde wann an den Lizenzserver gemeldet + aktueller Melde-Modus."""
    from shared.licensing import inventory
    try:
        inv = inventory.build_inventar()
        zuletzt = inventory.load_report_state()
        return jsonify({
            'modus': inv['modus'],
            'aktueller_digest': inv['digest'],
            'mandanten_gesamt': inv['mandanten_gesamt'],
            'mandanten_aktiv': inv['mandanten_aktiv'],
            'zuletzt_gemeldet': zuletzt or None,
            'aenderung_offen': bool(zuletzt.get('digest') != inv['digest']),
        }), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path,
                                     type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500
