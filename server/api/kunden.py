"""Kunden Management API — vollständige CRUD + Multi-Produkt + Evidence + Impressum."""

from flask import current_app, Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from pathlib import Path
from typing import Any, Dict, List
import json
import sqlite3

from werkzeug.utils import secure_filename
import tempfile
import os

from evidence.db import (
    ensure_db as evidence_ensure_db,
    add_document,
    add_web_document,
    list_documents,
    delete_document,
    upsert_extracted_text,
    get_extracted_text,
)

EVIDENCE_DB = Path('data/db/evidence.sqlite')
EVIDENCE_STORE = Path('data/evidence')
ALLOWED_FILE_EXTENSIONS = {'.pdf', '.docx', '.txt', '.md', '.csv', '.xlsx'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

evidence_ensure_db(EVIDENCE_DB)

from kunden.db import (
    list_kunden,
    list_deleted_kunden,
    load_kunde,
    save_kunde,
    delete_kunde as db_delete_kunde,
    restore_kunde as db_restore_kunde,
    hard_delete_kunde as db_hard_delete_kunde,
    disable_module as db_disable_module,
    list_produkte,
    save_produkt,
    delete_produkt as db_delete_produkt,
    restore_produkt as db_restore_produkt,
    hard_delete_produkt as db_hard_delete_produkt,
    set_default_produkt as db_set_default_produkt,
    ensure_db,
)

# Issue #430: Auto-Anlage von Modul-Projekten beim Aktivieren eines Moduls
# am Kunden. Jedes Modul hat eine eigene save_projekt-Signatur, die wir
# hier wrappen. Gutachten ist ausgenommen (braucht Frameworks-Auswahl).
from cra.db import (
    save_projekt as cra_save_projekt,
    load_projekt as cra_load_projekt,
    list_projekte_fuer_kunde as cra_list_fuer_kunde,
)
from nis2.db import save_projekt as nis2_save_projekt, load_projekt as nis2_load_projekt
from dsgvo.db import save_projekt as dsgvo_save_projekt, load_projekt as dsgvo_load_projekt
from ai_act.db import save_projekt as aiact_save_projekt, load_projekt as aiact_load_projekt
from risikobewertung.db import (
    save_projekt as rb_save_projekt,
    load_projekt as rb_load_projekt,
    list_projekte_fuer_kunde as rb_list_fuer_kunde,
)

kunden_bp = Blueprint('kunden', __name__)

DB_PATH = Path('data/db/kunden.sqlite')

# Sicherstellen, dass DB initialisiert ist
ensure_db(DB_PATH)


# ============================================================
# Hilfsfunktionen
# ============================================================

ALLOWED_MODULES = {'risikobewertung', 'gutachten', 'cra', 'dsgvo', 'nis2', 'ai_act'}
ALLOWED_RB_FRAMEWORKS = {'STRIDE', 'Finanzinstitute', 'HEAVENS', 'OCTAVE', 'TARA'}
ALLOWED_GUTACHTEN_FRAMEWORKS = {'DORA', 'NIS2', 'CRA', 'ISO27001', 'DSGVO', 'AI_ACT', 'BSI'}
ALLOWED_PRODUKTKLASSEN = {'default', 'important_i', 'important_ii', 'critical_i', 'critical_ii'}


def _serialize_kunde(kunde: Dict[str, Any]) -> Dict[str, Any]:
    """Konvertiert DB-Kunde zu API-Response-Format (deutsche und englische Felder)."""
    if not kunde:
        return {}

    # frameworks_json kann String oder Liste sein
    frameworks = kunde.get('frameworks_json') or []
    if isinstance(frameworks, str):
        try:
            frameworks = json.loads(frameworks)
        except Exception:
            frameworks = []

    return {
        'id': kunde.get('name'),
        'name': kunde.get('name', ''),
        'company': kunde.get('unternehmen', ''),
        'unternehmen': kunde.get('unternehmen', ''),
        'advisor': kunde.get('berater', ''),
        'berater': kunde.get('berater', ''),
        'description': kunde.get('beschreibung', ''),
        'beschreibung': kunde.get('beschreibung', ''),
        'frameworks': frameworks,
        'pruefungsfokus': kunde.get('pruefungsfokus', ''),
        'rb_framework': kunde.get('rb_framework', 'STRIDE'),
        'produkt': kunde.get('produkt', ''),
        'produktklasse': kunde.get('produktklasse', 'default'),
        'modules': {
            'risikobewertung': bool(kunde.get('module_risikobewertung', 1)),
            'gutachten': bool(kunde.get('module_gutachten', 1)),
            'cra': bool(kunde.get('module_cra', 1)),
            'dsgvo': bool(kunde.get('module_dsgvo', 1)),
            'nis2': bool(kunde.get('module_nis2', 1)),
            'ai_act': bool(kunde.get('module_ai_act', 1)),
        },
        'created_at': kunde.get('created_at'),
        'updated_at': kunde.get('updated_at'),
    }


def _kunde_save_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """Mapping von API-Body zu kunden/db.py-save_kunde-Argumenten."""
    fields: Dict[str, Any] = {}

    # Allgemeine Felder
    for src, dst in [('company', 'unternehmen'), ('unternehmen', 'unternehmen'),
                     ('advisor', 'berater'), ('berater', 'berater'),
                     ('description', 'beschreibung'), ('beschreibung', 'beschreibung'),
                     ('pruefungsfokus', 'pruefungsfokus'),
                     ('produkt', 'produkt')]:
        if src in data:
            fields[dst] = data[src] or ''

    # rb_framework validieren
    if 'rb_framework' in data:
        v = data['rb_framework']
        if v and v not in ALLOWED_RB_FRAMEWORKS:
            raise ValueError(f'rb_framework muss eines sein von: {sorted(ALLOWED_RB_FRAMEWORKS)}')
        fields['rb_framework'] = v or 'STRIDE'

    # produktklasse validieren
    if 'produktklasse' in data:
        v = data['produktklasse']
        if v and v not in ALLOWED_PRODUKTKLASSEN:
            raise ValueError(f'produktklasse muss eines sein von: {sorted(ALLOWED_PRODUKTKLASSEN)}')
        fields['produktklasse'] = v or 'default'

    # frameworks (Gutachten-Frameworks-Auswahl)
    if 'frameworks' in data:
        fws = data['frameworks'] or []
        if not isinstance(fws, list):
            raise ValueError('frameworks muss eine Liste sein')
        invalid = [f for f in fws if f not in ALLOWED_GUTACHTEN_FRAMEWORKS]
        if invalid:
            raise ValueError(f'Ungültige Gutachten-Frameworks: {invalid}')
        fields['frameworks_json'] = json.dumps(fws)

    # Module
    if 'modules' in data:
        mods = data['modules'] or {}
        if not isinstance(mods, dict):
            raise ValueError('modules muss ein Objekt sein')
        for m in ALLOWED_MODULES:
            if m in mods:
                fields[f'module_{m}'] = 1 if mods[m] else 0

    return fields


# Issue #430: Auto-Anlage von Modul-Projekten
# DB-Pfade liegen relativ zum Workspace.
_RB_DB = Path('data/db/risikobewertung.sqlite')
_CRA_DB = Path('data/db/cra.sqlite')
_NIS2_DB = Path('data/db/nis2.sqlite')
_DSGVO_DB = Path('data/db/dsgvo.sqlite')
_AIACT_DB = Path('data/db/ai_act.sqlite')


def _ensure_module_projects(kunde: Dict[str, Any]) -> List[str]:
    """Legt fuer jedes aktivierte Modul ein Projekt mit dem Kunden-Namen
    an, falls noch nicht existent. Idempotent.

    Gutachten ausgenommen — braucht eine Frameworks-Auswahl, die hier
    nicht sinnvoll vorbelegbar ist.

    Returns die Liste der angelegten/gefundenen Modul-Schluessel.
    """
    if not kunde:
        return []
    name = (kunde.get('name') or '').strip()
    if not name:
        return []

    unternehmen = (kunde.get('unternehmen') or kunde.get('name') or '').strip()
    beschreibung = (kunde.get('beschreibung') or '').strip()
    berater = (kunde.get('berater') or '').strip()
    produkt = (kunde.get('produkt') or '').strip()
    produktklasse = (kunde.get('produktklasse') or 'default').strip()
    rb_framework = (kunde.get('rb_framework') or 'STRIDE').strip()

    created: List[str] = []

    def _safe_save(label: str, exists_fn, save_fn) -> None:
        try:
            if exists_fn() is None:
                save_fn()
                created.append(label)
        except Exception as e:  # noqa: BLE001
            # Nicht den Kunden-Save fallen lassen, nur protokollieren.
            current_app.logger.warning(
                'Auto-Anlage Modul-Projekt %s fuer Kunde %s fehlgeschlagen: %s',
                label, name, e,
            )

    if bool(kunde.get('module_risikobewertung', 1)):
        # Issue #433: RB erlaubt mehrere Projekte pro Kunde. Auto-Anlage
        # nur, wenn der Kunde noch GAR KEIN RB-Projekt hat (per
        # unternehmen-Match). Existiert bereits eines, ueberlassen wir
        # weitere Projekte dem User.
        rb_projekt_name = name  # initial: Kunden-Name als Default
        # Falls bereits ein Projekt mit name=kunde.name existiert, aber
        # ohne unternehmen-Feld (Altdaten), nichts tun. Sonst frischer
        # Default-Name '<Kunde> - Risikoanalyse', falls Konflikt.
        existing_for_kunde = []
        try:
            existing_for_kunde = rb_list_fuer_kunde(_RB_DB, name)
        except Exception:  # noqa: BLE001
            pass
        if not existing_for_kunde:
            # Kein Projekt fuer den Kunden vorhanden — Initialprojekt
            # anlegen. Namens-Konflikt mit anderem Kunden-Projekt
            # auffangen.
            try:
                if rb_load_projekt(_RB_DB, rb_projekt_name) is not None:
                    rb_projekt_name = f"{name} – Risikoanalyse"
            except Exception:  # noqa: BLE001
                pass
            _safe_save(
                'risikobewertung',
                lambda: rb_load_projekt(_RB_DB, rb_projekt_name),
                lambda: rb_save_projekt(
                    _RB_DB, name=rb_projekt_name, framework=rb_framework,
                    beschreibung=beschreibung,
                    unternehmen=unternehmen, produkt=produkt, berater=berater,
                ),
            )

    if bool(kunde.get('module_cra', 1)):
        _safe_save(
            'cra',
            lambda: cra_load_projekt(_CRA_DB, name),
            lambda: cra_save_projekt(
                _CRA_DB, name=name, unternehmen=unternehmen, produkt=produkt,
                produktklasse=produktklasse, beschreibung=beschreibung,
                berater=berater,
            ),
        )

    if bool(kunde.get('module_nis2', 1)):
        _safe_save(
            'nis2',
            lambda: nis2_load_projekt(_NIS2_DB, name),
            lambda: nis2_save_projekt(
                _NIS2_DB, name=name, unternehmen=unternehmen,
                beschreibung=beschreibung, berater=berater,
            ),
        )

    if bool(kunde.get('module_dsgvo', 1)):
        _safe_save(
            'dsgvo',
            lambda: dsgvo_load_projekt(_DSGVO_DB, name),
            lambda: dsgvo_save_projekt(
                _DSGVO_DB, name=name, unternehmen=unternehmen,
                beschreibung=beschreibung, berater=berater,
            ),
        )

    if bool(kunde.get('module_ai_act', 1)):
        _safe_save(
            'ai_act',
            lambda: aiact_load_projekt(_AIACT_DB, name),
            lambda: aiact_save_projekt(
                _AIACT_DB, name=name, organisation=unternehmen,
                produkt=produkt, beschreibung=beschreibung,
            ),
        )

    return created


def _ensure_cra_projekt_fuer_produkt(kunde: Dict[str, Any], produkt: Dict[str, Any]) -> str | None:
    """Issue #435: Pro Produkt eines Kunden ein CRA-Projekt anlegen
    (idempotent). Naming: '<Kunde> – <Produkt>'. Default-Produkt nutzt
    nur den Kunden-Namen, damit ein bereits via _ensure_module_projects
    angelegtes Projekt nicht doppelt entsteht.

    Returns den Projekt-Namen, falls neu angelegt; sonst None.
    """
    if not kunde or not produkt:
        return None
    if not bool(kunde.get('module_cra', 1)):
        # CRA fuer diesen Kunden nicht aktiv → kein Auto-Anlage
        return None
    kunde_name = (kunde.get('name') or '').strip()
    produkt_name = (produkt.get('name') or '').strip()
    if not kunde_name or not produkt_name:
        return None

    is_default = bool(produkt.get('is_default'))
    # Standard-Produkt → CRA-Projekt hat den Kunden-Namen (kompatibel mit
    # _ensure_module_projects). Andere Produkte bekommen den Composite-Namen.
    cra_name = kunde_name if is_default else f"{kunde_name} – {produkt_name}"

    try:
        if cra_load_projekt(_CRA_DB, cra_name) is not None:
            # Vorhandenes Projekt updaten — Produkt-Felder synchronisieren.
            cra_save_projekt(
                _CRA_DB,
                name=cra_name,
                unternehmen=kunde_name,
                produkt=produkt_name,
                produktklasse=(produkt.get('produktklasse') or 'default'),
                beschreibung=(produkt.get('beschreibung') or ''),
                berater=(kunde.get('berater') or ''),
            )
            return None
        # Neu anlegen
        cra_save_projekt(
            _CRA_DB,
            name=cra_name,
            unternehmen=kunde_name,
            produkt=produkt_name,
            produktklasse=(produkt.get('produktklasse') or 'default'),
            beschreibung=(produkt.get('beschreibung') or ''),
            berater=(kunde.get('berater') or ''),
        )
        return cra_name
    except Exception as e:  # noqa: BLE001
        current_app.logger.warning(
            'CRA-Auto-Anlage fuer Produkt %s (Kunde %s) fehlgeschlagen: %s',
            produkt_name, kunde_name, e,
        )
        return None


def _sync_cra_projekte_fuer_kunde(kunde_name: str) -> List[str]:
    """Issue #435: Alle Produkte eines Kunden in CRA durchsyncen.
    Wird aus dem sync-projekte-Endpoint aufgerufen. Returns Liste der
    neu angelegten CRA-Projekt-Namen."""
    k = load_kunde(DB_PATH, kunde_name)
    if not k or not bool(k.get('module_cra', 1)):
        return []
    created: List[str] = []
    try:
        produkte = list_produkte(DB_PATH, kunde_name)
    except Exception:  # noqa: BLE001
        return created
    for p in produkte:
        n = _ensure_cra_projekt_fuer_produkt(k, p)
        if n:
            created.append(n)
    return created


# ============================================================
# Kunden CRUD
# ============================================================

@kunden_bp.get('')
@jwt_required()
def list_all_kunden():
    """Liste aller aktiven Kunden."""
    try:
        names = list_kunden(DB_PATH)
        out = []
        for name in names:
            k = load_kunde(DB_PATH, name)
            if k:
                out.append(_serialize_kunde(k))
        return out, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@kunden_bp.get('/deleted')
@jwt_required()
def list_deleted():
    """Liste gelöschter Kunden mit Lösch-Datum."""
    try:
        return list_deleted_kunden(DB_PATH), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@kunden_bp.get('/<kunde_name>')
@jwt_required()
def get_kunde(kunde_name: str):
    """Einen Kunden vollständig laden."""
    try:
        k = load_kunde(DB_PATH, kunde_name)
        if not k:
            return {'error': 'Kunde nicht gefunden'}, 404
        return _serialize_kunde(k), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@kunden_bp.post('')
@jwt_required()
def create_kunde():
    """Neuen Kunden anlegen."""
    try:
        data = request.json or {}
        name = (data.get('name') or '').strip()
        if not name:
            return {'error': 'Feld "name" ist Pflicht'}, 400
        if load_kunde(DB_PATH, name):
            return {'error': 'Kunde existiert bereits'}, 409

        fields = _kunde_save_fields(data)
        save_kunde(DB_PATH, name, **fields)

        k = load_kunde(DB_PATH, name)
        # Issue #430: Modul-Projekte fuer aktivierte Module idempotent anlegen
        if k:
            _ensure_module_projects(k)
        return _serialize_kunde(k), 201
    except ValueError as e:
        return {'error': str(e)}, 400
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@kunden_bp.put('/<kunde_name>')
@jwt_required()
def update_kunde(kunde_name: str):
    """Kunden aktualisieren."""
    try:
        k = load_kunde(DB_PATH, kunde_name)
        if not k:
            return {'error': 'Kunde nicht gefunden'}, 404

        data = request.json or {}
        fields = _kunde_save_fields(data)
        save_kunde(DB_PATH, kunde_name, **fields)

        updated = load_kunde(DB_PATH, kunde_name)
        # Issue #430: Modul-Projekte synchronisieren (idempotent — nur neue
        # Modul-Aktivierungen erzeugen Projekte, vorhandene bleiben unangetastet)
        if updated:
            _ensure_module_projects(updated)
        return _serialize_kunde(updated), 200
    except ValueError as e:
        return {'error': str(e)}, 400
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@kunden_bp.get('/<kunde_name>/rb-projekte')
@jwt_required()
def list_rb_projekte_fuer_kunde(kunde_name: str):
    """Issue #433: Liste aller RB-Projekte fuer einen Kunden.
    Wird von KundenView genutzt, um pro Kunde mehrere Projekte zu zeigen."""
    try:
        from risikobewertung.db import load_risiken as rb_load_risiken
        rows = rb_list_fuer_kunde(_RB_DB, kunde_name)
        out = []
        for r in rows:
            try:
                risiken_count = len(rb_load_risiken(_RB_DB, r['name']))
            except Exception:  # noqa: BLE001
                risiken_count = 0
            out.append({
                'name': r.get('name', ''),
                'framework': r.get('framework', 'STRIDE'),
                'beschreibung': r.get('beschreibung', ''),
                'unternehmen': r.get('unternehmen', ''),
                'produkt': r.get('produkt', ''),
                'berater': r.get('berater', ''),
                'risiken_count': risiken_count,
                'updated_at': r.get('updated_at'),
            })
        return out, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@kunden_bp.get('/<kunde_name>/cra-projekte')
@jwt_required()
def list_cra_projekte_fuer_kunde(kunde_name: str):
    """Issue #435: CRA-Projekte fuer einen Kunden — pro Produkt eines."""
    try:
        rows = cra_list_fuer_kunde(_CRA_DB, kunde_name)
        out = []
        for r in rows:
            out.append({
                'name': r.get('name', ''),
                'unternehmen': r.get('unternehmen', ''),
                'produkt': r.get('produkt', ''),
                'produktklasse': r.get('produktklasse', 'default'),
                'beschreibung': r.get('beschreibung', ''),
                'berater': r.get('berater', ''),
                'updated_at': r.get('updated_at'),
            })
        return out, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@kunden_bp.post('/<kunde_name>/sync-projekte')
@jwt_required()
def sync_module_projects(kunde_name: str):
    """Issue #430 + #435: Modul-Projekte fuer einen Kunden nachtraeglich
    anlegen — fuer alle aktivierten Module + fuer jedes Produkt ein
    CRA-Projekt."""
    try:
        k = load_kunde(DB_PATH, kunde_name)
        if not k:
            return {'error': 'Kunde nicht gefunden'}, 404
        created = _ensure_module_projects(k)
        cra_created = _sync_cra_projekte_fuer_kunde(kunde_name)
        return {
            'created': created,
            'cra_per_produkt': cra_created,
            'kunde': kunde_name,
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@kunden_bp.delete('/<kunde_name>')
@jwt_required()
def soft_delete_kunde(kunde_name: str):
    """Kunden soft-delete (Archivierung)."""
    try:
        if not load_kunde(DB_PATH, kunde_name):
            return {'error': 'Kunde nicht gefunden'}, 404
        db_delete_kunde(DB_PATH, kunde_name)
        return {'deleted': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@kunden_bp.post('/<kunde_name>/restore')
@jwt_required()
def restore_kunde(kunde_name: str):
    """Gelöschten Kunden reaktivieren."""
    try:
        db_restore_kunde(DB_PATH, kunde_name)
        k = load_kunde(DB_PATH, kunde_name)
        if not k:
            return {'error': 'Restore fehlgeschlagen'}, 500
        return _serialize_kunde(k), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@kunden_bp.delete('/<kunde_name>/permanent')
@jwt_required()
def hard_delete_kunde(kunde_name: str):
    """Kunden endgültig löschen."""
    try:
        db_hard_delete_kunde(DB_PATH, kunde_name)
        return {'deleted': True, 'permanent': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@kunden_bp.patch('/<kunde_name>/modules')
@jwt_required()
def patch_modules(kunde_name: str):
    """Nur Module-Aktivierung aktualisieren."""
    try:
        if not load_kunde(DB_PATH, kunde_name):
            return {'error': 'Kunde nicht gefunden'}, 404
        data = request.json or {}
        mods = data.get('modules') or data
        if not isinstance(mods, dict):
            return {'error': 'modules muss ein Objekt sein'}, 400
        fields = {}
        for m in ALLOWED_MODULES:
            if m in mods:
                fields[f'module_{m}'] = 1 if mods[m] else 0
        save_kunde(DB_PATH, kunde_name, **fields)
        return _serialize_kunde(load_kunde(DB_PATH, kunde_name)), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# Produkte (Sub-Entity je Kunde)
# ============================================================

@kunden_bp.get('/<kunde_name>/produkte')
@jwt_required()
def get_produkte(kunde_name: str):
    """Produkte eines Kunden listen."""
    try:
        if not load_kunde(DB_PATH, kunde_name):
            return {'error': 'Kunde nicht gefunden'}, 404
        produkte = list_produkte(DB_PATH, kunde_name)
        return produkte, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@kunden_bp.post('/<kunde_name>/produkte')
@jwt_required()
def create_produkt(kunde_name: str):
    """Produkt zu einem Kunden anlegen."""
    try:
        if not load_kunde(DB_PATH, kunde_name):
            return {'error': 'Kunde nicht gefunden'}, 404
        data = request.json or {}
        name = (data.get('name') or '').strip()
        if not name:
            return {'error': 'Feld "name" ist Pflicht'}, 400

        produktklasse = data.get('produktklasse', 'default')
        if produktklasse not in ALLOWED_PRODUKTKLASSEN:
            return {'error': f'Ungültige produktklasse: {produktklasse}'}, 400

        produkt_id = save_produkt(
            DB_PATH,
            kunde_name,
            name=name,
            beschreibung=data.get('beschreibung', '') or data.get('description', ''),
            produktklasse=produktklasse,
            is_default=bool(data.get('is_default', False)),
        )
        # Issue #435: CRA-Projekt fuer dieses Produkt anlegen
        k = load_kunde(DB_PATH, kunde_name)
        produkt = {
            'id': produkt_id, 'name': name,
            'beschreibung': data.get('beschreibung', '') or data.get('description', ''),
            'produktklasse': produktklasse,
            'is_default': bool(data.get('is_default', False)),
        }
        _ensure_cra_projekt_fuer_produkt(k or {}, produkt)
        return {'id': produkt_id, 'name': name, 'created': True}, 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@kunden_bp.put('/<kunde_name>/produkte/<int:produkt_id>')
@jwt_required()
def update_produkt(kunde_name: str, produkt_id: int):
    """Produkt aktualisieren."""
    try:
        if not load_kunde(DB_PATH, kunde_name):
            return {'error': 'Kunde nicht gefunden'}, 404
        data = request.json or {}
        produktklasse = data.get('produktklasse', 'default')
        if produktklasse not in ALLOWED_PRODUKTKLASSEN:
            return {'error': f'Ungültige produktklasse: {produktklasse}'}, 400

        save_produkt(
            DB_PATH,
            kunde_name,
            name=data.get('name'),
            beschreibung=data.get('beschreibung', '') or data.get('description', ''),
            produktklasse=produktklasse,
            is_default=bool(data.get('is_default', False)),
            produkt_id=produkt_id,
        )
        # Issue #435: CRA-Projekt-Daten mitziehen
        k = load_kunde(DB_PATH, kunde_name)
        produkt = {
            'id': produkt_id,
            'name': data.get('name'),
            'beschreibung': data.get('beschreibung', '') or data.get('description', ''),
            'produktklasse': produktklasse,
            'is_default': bool(data.get('is_default', False)),
        }
        _ensure_cra_projekt_fuer_produkt(k or {}, produkt)
        return {'id': produkt_id, 'updated': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@kunden_bp.post('/<kunde_name>/produkte/<int:produkt_id>/default')
@jwt_required()
def set_default(kunde_name: str, produkt_id: int):
    """Produkt als Standard markieren."""
    try:
        db_set_default_produkt(DB_PATH, kunde_name, produkt_id)
        return {'updated': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@kunden_bp.delete('/<kunde_name>/produkte/<int:produkt_id>')
@jwt_required()
def delete_produkt(kunde_name: str, produkt_id: int):
    """Produkt soft-delete."""
    try:
        db_delete_produkt(DB_PATH, produkt_id)
        return {'deleted': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@kunden_bp.post('/<kunde_name>/produkte/<int:produkt_id>/restore')
@jwt_required()
def restore_produkt(kunde_name: str, produkt_id: int):
    """Gelöschtes Produkt reaktivieren."""
    try:
        db_restore_produkt(DB_PATH, produkt_id)
        return {'restored': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# Impressum-Parser (F1d Vorbereitung)
# ============================================================

@kunden_bp.post('/parse-impressum')
@jwt_required()
def parse_impressum():
    """Website crawlen und Impressum-Daten extrahieren."""
    try:
        data = request.json or {}
        url = (data.get('url') or '').strip()
        max_pages = int(data.get('max_pages', 5))
        if not url:
            return {'error': 'Feld "url" ist Pflicht'}, 400
        if max_pages < 1 or max_pages > 50:
            return {'error': 'max_pages muss zwischen 1 und 50 sein'}, 400

        try:
            from kunden.impressum import bootstrap_from_url
        except Exception as e:
            return {'error': f'Impressum-Parser nicht verfügbar: {e}'}, 503

        result = bootstrap_from_url(url, max_pages=max_pages)
        if not result:
            return {'error': 'Keine Impressum-Daten erkannt'}, 404

        # Result ist ImpressumData-Dataclass — als Dict zurückgeben
        return {
            'unternehmen': getattr(result, 'unternehmen', '') or '',
            'rechtsform': getattr(result, 'rechtsform', '') or '',
            'strasse': getattr(result, 'strasse', '') or '',
            'plz': getattr(result, 'plz', '') or '',
            'ort': getattr(result, 'ort', '') or '',
            'vertreter': getattr(result, 'vertreter', []) or [],
            'email': getattr(result, 'email', '') or '',
            'telefon': getattr(result, 'telefon', '') or '',
            'ust_id': getattr(result, 'ust_id', '') or '',
            'hrb': getattr(result, 'hrb', '') or '',
            'pages_crawled': getattr(result, 'pages_crawled', 0),
            'beschreibung': result.as_beschreibung() if hasattr(result, 'as_beschreibung') else '',
            'source_url': url,
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# Konstanten-Endpoints (für Frontend-Dropdowns)
# ============================================================

@kunden_bp.get('/constants')
@jwt_required()
def get_constants():
    """Konstanten für Dropdowns: rb_frameworks, gutachten_frameworks, produktklassen."""
    return {
        'rb_frameworks': sorted(ALLOWED_RB_FRAMEWORKS),
        'gutachten_frameworks': sorted(ALLOWED_GUTACHTEN_FRAMEWORKS),
        'produktklassen': [
            {'key': 'default', 'label': '— Nicht gelistet —'},
            {'key': 'important_i', 'label': 'Important Class I (Annex III)'},
            {'key': 'important_ii', 'label': 'Important Class II (Annex III)'},
            {'key': 'critical_i', 'label': 'Critical Class I (Annex IV)'},
            {'key': 'critical_ii', 'label': 'Critical Class II (Annex IV)'},
        ],
    }, 200


# ============================================================
# Evidence (Sub-Entity je Kunde)
# ============================================================

@kunden_bp.get('/<kunde_name>/evidence')
@jwt_required()
def list_evidence(kunde_name: str):
    """Evidence-Dokumente eines Kunden listen."""
    try:
        if not load_kunde(DB_PATH, kunde_name):
            return {'error': 'Kunde nicht gefunden'}, 404
        docs = list_documents(EVIDENCE_DB, kunden_id=kunde_name)
        result = []
        for d in docs:
            # EvidenceDocument-Dataclass zu Dict
            entry = {
                'id': d.id,
                'filename': d.filename,
                'doc_type': d.doc_type,
                'doc_kind': getattr(d, 'doc_kind', 'file'),
                'url': getattr(d, 'url', ''),
                'tags': d.tags if isinstance(d.tags, list) else [],
                'added_at': d.added_at,
                'updated_at': d.updated_at,
                'owner': d.owner,
                'version': d.version,
            }
            result.append(entry)
        return result, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@kunden_bp.post('/<kunde_name>/evidence/file')
@jwt_required()
def upload_evidence_file(kunde_name: str):
    """Evidence-Datei hochladen."""
    try:
        if not load_kunde(DB_PATH, kunde_name):
            return {'error': 'Kunde nicht gefunden'}, 404

        if 'file' not in request.files:
            return {'error': 'Feld "file" (multipart) erforderlich'}, 400
        upload = request.files['file']
        if not upload.filename:
            return {'error': 'Keine Datei ausgewählt'}, 400

        filename = secure_filename(upload.filename)
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_FILE_EXTENSIONS:
            return {'error': f'Dateityp {ext} nicht erlaubt. Erlaubt: {sorted(ALLOWED_FILE_EXTENSIONS)}'}, 400

        # Größe prüfen
        upload.seek(0, os.SEEK_END)
        size = upload.tell()
        upload.seek(0)
        if size > MAX_FILE_SIZE:
            return {'error': f'Datei zu groß: max {MAX_FILE_SIZE // (1024*1024)} MB'}, 413

        # Temporär speichern, dann via add_document() in den Store kopieren
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            upload.save(tmp.name)
            tmp_path = Path(tmp.name)

        try:
            tags = request.form.get('tags', '').split(',')
            tags = [t.strip() for t in tags if t.strip()]
            doc_type = request.form.get('doc_type', '')

            doc = add_document(
                EVIDENCE_DB,
                tmp_path,
                store_dir=EVIDENCE_STORE,
                doc_type=doc_type,
                tags=tags,
                kunden_id=kunde_name,
            )
            return {
                'id': doc.id,
                'filename': doc.filename,
                'doc_type': doc.doc_type,
                'tags': doc.tags if isinstance(doc.tags, list) else [],
            }, 201
        finally:
            tmp_path.unlink(missing_ok=True)
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@kunden_bp.post('/<kunde_name>/evidence/url')
@jwt_required()
def add_evidence_url(kunde_name: str):
    """Evidence von URL crawlen."""
    try:
        if not load_kunde(DB_PATH, kunde_name):
            return {'error': 'Kunde nicht gefunden'}, 404
        data = request.json or {}
        url = (data.get('url') or '').strip()
        max_pages = int(data.get('max_pages', 5))
        doc_type = data.get('doc_type', 'web')
        tags = data.get('tags', [])
        if not url:
            return {'error': 'Feld "url" ist Pflicht'}, 400

        doc = add_web_document(
            EVIDENCE_DB,
            url=url,
            store_dir=EVIDENCE_STORE,
            doc_type=doc_type,
            tags=tags,
            kunden_id=kunde_name,
            max_pages=max_pages,
        )
        return {
            'id': doc.id,
            'filename': doc.filename,
            'url': getattr(doc, 'url', url),
            'doc_type': doc.doc_type,
            'tags': doc.tags if isinstance(doc.tags, list) else [],
        }, 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@kunden_bp.post('/<kunde_name>/evidence/<doc_id>/extract')
@jwt_required()
def extract_evidence(kunde_name: str, doc_id: str):
    """Text aus Evidence-Dokument extrahieren."""
    try:
        from evidence.extract import extract_text
        # Das Doc finden
        docs = list_documents(EVIDENCE_DB, kunden_id=kunde_name)
        doc = next((d for d in docs if d.id == doc_id), None)
        if not doc:
            return {'error': 'Dokument nicht gefunden'}, 404
        if doc.stored_path:
            text = extract_text(Path(doc.stored_path))
            upsert_extracted_text(EVIDENCE_DB, doc_id, text)
            return {'extracted': True, 'chars': len(text)}, 200
        return {'error': 'Kein Pfad für Extraktion'}, 400
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@kunden_bp.delete('/<kunde_name>/evidence/<doc_id>')
@jwt_required()
def delete_evidence(kunde_name: str, doc_id: str):
    """Evidence-Dokument löschen."""
    try:
        delete_document(EVIDENCE_DB, doc_id, delete_file=True)
        return {'deleted': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500
