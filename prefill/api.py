"""Flask-API für Prefill-Engine.

Bietet REST-Endpunkte für KI-gestützte Compliance-Bewertungen.
Adaptet prefill/engine.py (pure Python) für Web-Nutzung.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Blueprint, request, jsonify
from werkzeug.exceptions import BadRequest

from prefill.engine import (
    PrefillField,
    PrefillSuggestion,
    PrefillError,
    run_prefill,
)
from prefill.db import (
    get_suggestions,
    set_suggestion,
    get_suggestion,
)

logger = logging.getLogger(__name__)

# Blueprint für CRA-Module (später: /api/cra/prefill)
bp = Blueprint('prefill', __name__, url_prefix='/api/cra/prefill')


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────


@bp.post('/generate')
def generate_prefill():
    """Generiere KI-Vorschläge für Compliance-Anforderungen.

    Request Body:
    {
        "suite_cfg": {...},  // Suite-Konfiguration
        "fields": [
            {
                "id": "REQ-001",
                "titel": "Datenklassifizierung",
                "beschreibung": "...",
                "kapitel": "1. Datenschutz"
            }
        ],
        "evidence_chunks": [
            {
                "doc_id": "doc-123",
                "chunk_idx": 0,
                "text": "..."
            }
        ]
    }

    Response:
    {
        "suggestions": [
            {
                "field_id": "REQ-001",
                "score": 4,
                "kommentar": "...",
                "confidence": 0.95,
                "rationale": "...",
                "citations": [...],
                "suggestion_id": "uuid"
            }
        ],
        "generated_at": "2026-05-08T12:34:56Z"
    }

    Errors:
    - 400: Validation error (missing fields, invalid format)
    - 401: Unauthorized
    - 403: Forbidden (permission check)
    - 500: KI-Provider error
    """
    # Validate request
    data = request.get_json()
    if not data:
        raise BadRequest("Request body must be JSON")

    suite_cfg = data.get('suite_cfg')
    fields_data = data.get('fields', [])
    evidence_chunks = data.get('evidence_chunks', [])

    if not suite_cfg:
        raise BadRequest("Missing required field: suite_cfg")
    if not fields_data:
        raise BadRequest("Missing required field: fields")
    if not evidence_chunks:
        raise BadRequest("Missing required field: evidence_chunks")

    # Convert to PrefillField objects
    try:
        fields = [
            PrefillField(
                id=f['id'],
                titel=f['titel'],
                beschreibung=f.get('beschreibung', ''),
                kapitel=f.get('kapitel', ''),
            )
            for f in fields_data
        ]
    except (KeyError, TypeError) as e:
        raise BadRequest(f"Invalid field format: {e}")

    # Run prefill engine
    try:
        suggestions = run_prefill(
            suite_cfg,
            fields,
            evidence_chunks,
            # Optional: Progress callback (WebSocket later?)
        )
    except PrefillError as e:
        logger.error(f"Prefill engine error: {e}")
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.exception(f"Unexpected error in prefill: {e}")
        return jsonify({'error': 'Internal server error'}), 500

    # Convert PrefillSuggestion to JSON-serializable
    response = {
        'suggestions': [
            {
                'field_id': s.field_id,
                'score': s.score,
                'kommentar': s.kommentar,
                'confidence': s.confidence,
                'rationale': s.rationale,
                'citations': s.citations,
                'suggestion_id': s.suggestion_id,
                'suggested_at': s.suggested_at,
            }
            for s in suggestions
        ],
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'count': len(suggestions),
    }

    return jsonify(response), 200


@bp.post('/accept/<string:suggestion_id>')
def accept_prefill(suggestion_id: str):
    """Akzeptiere einen KI-Vorschlag und speichere ihn.

    Request Body:
    {
        "field_id": "REQ-001",
        "score": 4,
        "kommentar": "Überprüft und bestätigt",
        "db_path": "data/db/cra.sqlite",
        "projekt_name": "Projekt-X"
    }

    Response:
    {
        "status": "accepted",
        "suggestion_id": "uuid",
        "saved_at": "2026-05-08T12:34:56Z"
    }

    Errors:
    - 400: Validation error
    - 401: Unauthorized
    - 403: Forbidden (permission check)
    - 404: Suggestion not found
    """
    data = request.get_json() or {}

    field_id = data.get('field_id')
    score = data.get('score')
    kommentar = data.get('kommentar', '')
    db_path = data.get('db_path', 'data/db/cra.sqlite')
    projekt_name = data.get('projekt_name')

    if not field_id or score is None or not projekt_name:
        raise BadRequest(
            "Missing required fields: field_id, score, projekt_name"
        )

    if not 0 <= int(score) <= 5:
        raise BadRequest("Score must be between 0 and 5")

    # Save to DB
    try:
        suggestion = get_suggestion(Path(db_path), projekt_name, field_id)
        if not suggestion:
            return jsonify({'error': 'Suggestion not found'}), 404

        # Update with user-reviewed values
        suggestion['status'] = 'accepted'
        suggestion['score'] = int(score)
        suggestion['kommentar'] = kommentar
        suggestion['reviewed_by'] = request.headers.get('X-User-ID', 'unknown')
        suggestion['reviewed_at'] = int(datetime.utcnow().timestamp())

        set_suggestion(Path(db_path), projekt_name, field_id, suggestion)
    except Exception as e:
        logger.exception(f"Error saving suggestion: {e}")
        return jsonify({'error': 'Failed to save suggestion'}), 500

    return jsonify({
        'status': 'accepted',
        'suggestion_id': suggestion_id,
        'saved_at': datetime.utcnow().isoformat() + 'Z',
    }), 200


@bp.post('/reject/<string:suggestion_id>')
def reject_prefill(suggestion_id: str):
    """Lehne einen KI-Vorschlag ab.

    Request Body:
    {
        "field_id": "REQ-001",
        "reason": "Nicht anwendbar",
        "db_path": "data/db/cra.sqlite",
        "projekt_name": "Projekt-X"
    }

    Response:
    {
        "status": "rejected",
        "suggestion_id": "uuid"
    }
    """
    data = request.get_json() or {}

    field_id = data.get('field_id')
    reason = data.get('reason', '')
    db_path = data.get('db_path', 'data/db/cra.sqlite')
    projekt_name = data.get('projekt_name')

    if not field_id or not projekt_name:
        raise BadRequest("Missing required fields: field_id, projekt_name")

    try:
        suggestion = get_suggestion(Path(db_path), projekt_name, field_id)
        if not suggestion:
            return jsonify({'error': 'Suggestion not found'}), 404

        suggestion['status'] = 'rejected'
        suggestion['rejection_reason'] = reason
        suggestion['rejected_by'] = request.headers.get('X-User-ID', 'unknown')
        suggestion['rejected_at'] = int(datetime.utcnow().timestamp())

        set_suggestion(Path(db_path), projekt_name, field_id, suggestion)
    except Exception as e:
        logger.exception(f"Error rejecting suggestion: {e}")
        return jsonify({'error': 'Failed to reject suggestion'}), 500

    return jsonify({
        'status': 'rejected',
        'suggestion_id': suggestion_id,
    }), 200


@bp.get('/suggestions/<string:projekt_name>')
def list_suggestions(projekt_name: str):
    """Liste alle Vorschläge für ein Projekt auf.

    Query Parameters:
    - db_path: Pfad zur CRA-Datenbank (default: data/db/cra.sqlite)
    - status: Filter (pending, accepted, rejected) - optional
    - limit: Max. Ergebnisse (default: 100)
    - offset: Offset für Pagination (default: 0)

    Response:
    {
        "suggestions": [...],
        "total": 42,
        "limit": 100,
        "offset": 0
    }
    """
    db_path = request.args.get('db_path', 'data/db/cra.sqlite')
    status_filter = request.args.get('status')
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))

    try:
        all_suggestions = get_suggestions(Path(db_path), projekt_name)

        # Filter by status if provided
        if status_filter:
            all_suggestions = [
                s for s in all_suggestions
                if s.get('status') == status_filter
            ]

        # Apply pagination
        total = len(all_suggestions)
        paginated = all_suggestions[offset:offset + limit]

        return jsonify({
            'suggestions': paginated,
            'total': total,
            'limit': limit,
            'offset': offset,
        }), 200
    except Exception as e:
        logger.exception(f"Error listing suggestions: {e}")
        return jsonify({'error': 'Failed to list suggestions'}), 500


@bp.get('/health')
def health_check():
    """Health check für Prefill-Service."""
    return jsonify({
        'status': 'healthy',
        'service': 'prefill',
        'version': '1.0',
    }), 200


# ──────────────────────────────────────────────────────────────────────────────
# Error Handlers
# ──────────────────────────────────────────────────────────────────────────────


@bp.errorhandler(BadRequest)
def handle_bad_request(e):
    return jsonify({'error': e.description}), 400


@bp.errorhandler(500)
def handle_server_error(e):
    logger.exception(f"Server error: {e}")
    return jsonify({'error': 'Internal server error'}), 500
