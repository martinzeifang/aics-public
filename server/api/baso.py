"""BASO Questionnaire Module API."""

import shutil
import tempfile

from server.api.workspace_tmp import workspace_tmpdir
from flask import current_app, Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from pathlib import Path
from baso.db import fetch_answered_items, fetch_siko_paragraphs, ensure_db, ingest_questionnaires

baso_bp = Blueprint('baso', __name__, url_prefix='/api/baso')

DB_PATH = Path('data/db/baso.sqlite')


@baso_bp.get('/questions')
@jwt_required()
def list_questions():
    """Liste alle BASO-Fragen aus der Datenbank."""
    try:
        items = fetch_answered_items(DB_PATH)
        result = []
        for i, item in enumerate(items):
            result.append({
                'id': f'q-{i}',
                'file_name': item.get('file_name', ''),
                'layout': item.get('layout', ''),
                'title': item.get('title', ''),
                'question': item.get('question', ''),
                'schutzziel': item.get('schutzziel', ''),
                'status': item.get('status', ''),
                'answer': item.get('answer', ''),
            })
        return result, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@baso_bp.post('/import')
@jwt_required()
def import_questionnaire():
    """BASO-Fragebogen-XLSX hochladen + ingestieren (multipart, Feld 'file').
    Eine oder mehrere Dateien (file kann mehrfach gesetzt werden).
    """
    files = request.files.getlist('file')
    if not files:
        return {'error': 'Datei-Feld "file" fehlt'}, 400
    for f in files:
        if not f.filename or not f.filename.lower().endswith('.xlsx'):
            return {'error': f'Nur .xlsx erlaubt: {f.filename}'}, 400

    from werkzeug.utils import secure_filename
    from shared.upload_validation import validate_upload_file
    tmp_dir = workspace_tmpdir('baso_import_')
    try:
        for f in files:
            # #743 (WP-10): secure_filename gegen Path-Traversal; leere Namen ablehnen.
            safe_name = secure_filename(f.filename)
            if not safe_name or not safe_name.lower().endswith('.xlsx'):
                return {'error': f'Ungültiger Dateiname: {f.filename}'}, 400
            dest = tmp_dir / safe_name
            f.save(str(dest))
            # Magic-Byte- + Zip-Bomb-Prüfung vor dem Ingest.
            validate_upload_file(dest, suffix='.xlsx')
        ensure_db(DB_PATH)
        ingest_questionnaires(tmp_dir, DB_PATH)
        return {'imported': len(files)}, 200
    except ValueError as e:
        return {'error': str(e)}, 400
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@baso_bp.get('/sikos')
@jwt_required()
def list_sikos():
    """Liste alle SIKO-Paragraph aus der Datenbank."""
    try:
        paragraphs = fetch_siko_paragraphs(DB_PATH)
        result = []
        for para in paragraphs:
            result.append({
                'id': f"siko-{para.get('doc_name')}-{para.get('para_index')}",
                'doc_name': para.get('doc_name', ''),
                'para_index': para.get('para_index', 0),
                'text': para.get('text', ''),
            })
        return result, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)
