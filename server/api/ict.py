"""ICT Questionnaire Module API."""

import shutil
import tempfile

from server.api.workspace_tmp import workspace_tmpdir
from flask import current_app, Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from pathlib import Path
from ict.db import (
    fetch_answered_items,
    fetch_siko_paragraphs,
    fetch_report_paragraphs,
    ensure_db,
    ingest_questionnaires,
)

ict_bp = Blueprint('ict', __name__, url_prefix='/api/ict')

DB_PATH = Path('data/db/ict.sqlite')


@ict_bp.get('/questions')
@jwt_required()
def list_questions():
    """Liste alle ICT-Fragen aus der Datenbank."""
    try:
        items = fetch_answered_items(DB_PATH)
        result = []
        for i, item in enumerate(items):
            result.append({
                'id': item.get('question_id', f'q-{i}'),
                'file_name': item.get('file_name', ''),
                'title': item.get('title', ''),
                'question': item.get('question', ''),
                'answer': item.get('answer', ''),
                'maturity': item.get('maturity', 0),
                'explanation': item.get('explanation', ''),
                'guidance': item.get('guidance', ''),
            })
        return result, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@ict_bp.post('/import')
@jwt_required()
def import_questionnaire():
    """ICT-Fragebogen-XLSX hochladen + ingestieren (multipart, Feld 'file')."""
    files = request.files.getlist('file')
    if not files:
        return {'error': 'Datei-Feld "file" fehlt'}, 400
    for f in files:
        if not f.filename or not f.filename.lower().endswith('.xlsx'):
            return {'error': f'Nur .xlsx erlaubt: {f.filename}'}, 400

    from werkzeug.utils import secure_filename
    from shared.upload_validation import validate_upload_file
    tmp_dir = workspace_tmpdir('ict_import_')
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


@ict_bp.get('/sikos')
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


@ict_bp.get('/reports')
@jwt_required()
def list_reports():
    """Liste alle Report-Paragraph aus der Datenbank."""
    try:
        paragraphs = fetch_report_paragraphs(DB_PATH)
        result = []
        for para in paragraphs:
            result.append({
                'id': f"report-{para.get('file_name')}-{para.get('para_index')}",
                'file_name': para.get('file_name', ''),
                'para_index': para.get('para_index', 0),
                'text': para.get('text', ''),
            })
        return result, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)
