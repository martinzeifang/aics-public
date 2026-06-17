"""KI-Provider-Status API (Sprint #16 — KI-Transparenz).

Stellt einen read-only Endpoint bereit, der den aktiven KI-Provider
(lokal/Ollama vs. Cloud) und dessen Konfigurations-/Egress-Status meldet.

WICHTIG (Information Disclosure, #737): Es werden KEINE Secrets ausgeliefert.
API-Keys, Token-Werte oder vollständige interne URLs gehören NICHT in die
Antwort — nur abgeleitete Status-Flags (konfiguriert ja/nein, Egress erlaubt
ja/nein) sowie ein menschenlesbares Label.

Teil von #865 (#867/#877).
"""

from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, current_app, request
from flask_jwt_extended import jwt_required

from ai_compliance_suite.config import cfg_get, load_config

ai_status_bp = Blueprint('ai_status', __name__)


def _config_path() -> Path | None:
    """Aktueller Konfig-Pfad (zur Laufzeit aufgelöst).

    ``load_config`` cached den Default-Pfad beim Import; wir lösen daher die
    Umgebungsvariable ``AICS_CONFIG_PATH`` bei jedem Aufruf erneut auf, damit
    Konfig-Änderungen (und Tests) ohne Neustart wirken.
    """
    env = os.getenv('AICS_CONFIG_PATH')
    return Path(env) if env else None


def _build_provider_status() -> dict:
    """Ermittelt den aktiven Provider + Status aus der Suite-Konfiguration.

    Rückgabe-Schema:
        {
            "provider": "on_prem" | "cloud" | "none",
            "label": str,
            "configured": bool,
            "allow_data_egress": bool,
        }

    - ``provider``: Konfigurierter Provider. ``none`` falls unbekannt/ungültig.
    - ``configured``: Ist der Provider einsatzbereit konfiguriert?
        * on_prem: ``ai.on_prem.model`` gesetzt (Ollama-Modell erforderlich).
        * cloud:   ``ai.cloud.model`` gesetzt UND ``allow_data_egress`` aktiv.
    - ``allow_data_egress``: Spiegelt ``ai.cloud.allow_data_egress`` wider
      (relevant für die Cloud-Egress-Transparenz, #877). Bei on_prem stets False,
      da keine Daten das Netzwerk verlassen.
    """
    cfg = load_config(_config_path())

    provider = str(cfg_get(cfg, 'ai.provider', 'on_prem') or 'on_prem')

    if provider == 'on_prem':
        model = str(cfg_get(cfg, 'ai.on_prem.model', '') or '').strip()
        return {
            'provider': 'on_prem',
            'label': 'Lokal (Ollama)',
            'configured': bool(model),
            'allow_data_egress': False,
        }

    if provider == 'cloud':
        model = str(cfg_get(cfg, 'ai.cloud.model', '') or '').strip()
        allow_egress = bool(cfg_get(cfg, 'ai.cloud.allow_data_egress', False))
        return {
            'provider': 'cloud',
            'label': 'Cloud',
            'configured': bool(model) and allow_egress,
            'allow_data_egress': allow_egress,
        }

    # Unbekannter/ungültiger Provider-Wert.
    return {
        'provider': 'none',
        'label': 'Kein Provider',
        'configured': False,
        'allow_data_egress': False,
    }


@ai_status_bp.get('/provider-status')
@jwt_required()
def provider_status():
    """Liefert den aktiven KI-Provider + Konfig-/Egress-Status (read-only).

    Keine Secrets in der Antwort (#737).
    """
    try:
        return _build_provider_status(), 200
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception(
            '%s %s — %s: %s', request.method, request.path, type(e).__name__, e
        )
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@ai_status_bp.route('/models', methods=['GET', 'POST'])
@jwt_required()
def list_models():
    """Verfügbare Modelle abrufen (für das Auswahl-Dropdown). Cloud → Provider-
    ``GET /models``; on_prem → Ollama-``/api/tags``. Keine Secrets in der Antwort.

    #1406: Per POST können die **aktuellen Formularwerte** (provider/base_url/api_key/
    api_key_env) übergeben werden, sodass das Dropdown bereits VOR dem Speichern
    befüllt wird. Der Key wird nur transient genutzt, nie geloggt/zurückgegeben."""
    try:
        from ai_compliance_suite.ai.dispatch import build_provider, current_provider_name
        from ai_compliance_suite.ai.provider import provider_from_config

        body = (request.get_json(silent=True) or {}) if request.method == 'POST' else {}
        if body.get('provider'):  # Overrides aus dem Formular
            prov_name = str(body.get('provider'))
            if prov_name == 'cloud':
                cfg = {'ai': {'provider': 'cloud', 'cloud': {
                    'base_url': body.get('base_url') or 'https://api.openai.com/v1',
                    'api_key': body.get('api_key') or '',
                    'api_key_env': body.get('api_key_env') or 'AI_CLOUD_API_KEY',
                    'model': body.get('model') or '',
                    'allow_data_egress': True, 'timeout_s': 30,
                }}}
            else:
                cfg = {'ai': {'provider': 'on_prem', 'on_prem': {
                    'base_url': body.get('base_url') or 'http://127.0.0.1:11434',
                    'timeout_s': 30,
                }}}
            provider = provider_from_config(cfg)
        else:
            provider = build_provider()
            prov_name = current_provider_name()

        if not hasattr(provider, 'list_models'):
            return {'models': [], 'provider': prov_name,
                    'error': 'Provider unterstützt keine Modell-Liste'}, 200
        models = provider.list_models()
        return {'models': sorted(set(models)), 'provider': prov_name}, 200
    except Exception as e:  # noqa: BLE001 — Provider-/Konfig-Fehler an die UI durchreichen
        current_app.logger.warning('%s %s — %s: %s', request.method, request.path,
                                    type(e).__name__, e)
        return {'models': [], 'error': str(e)[:300]}, 502


@ai_status_bp.post('/run-stream')
@jwt_required()
def run_stream():
    """#1366/Assistenten — generisches Live-Ausführen eines (serverseitig erzeugten)
    KI-Assistenten-Prompts über den konfigurierten Provider (lokal ODER Cloud) als
    SSE-Stream. Ersetzt für die Wizards das reine Copy/Paste: derselbe Prompt, aber
    direkt über die API mit Live-Ansicht. Das Ergebnis (`text`) wird im Frontend wie
    eine eingefügte KI-Antwort weiterverarbeitet (bestehende parse-/apply-Logik).

    Body: {prompt: str, system?: str, force_json?: bool}. Kein stiller Fallback:
    ist die KI nicht verfügbar → 409.
    """
    data = request.get_json(silent=True) or {}
    prompt = (data.get('prompt') or '').strip()
    if not prompt:
        return {'error': 'Feld "prompt" ist Pflicht'}, 400
    system = (data.get('system') or
              'Du bist ein erfahrener Compliance-Experte. Antworte präzise und genau '
              'im geforderten Format (JSON, wenn der Prompt es verlangt).')
    from server.services.prefill import is_ai_available
    ok, reason = is_ai_available()
    if not ok:
        return {'error': reason or 'KI-Provider nicht verfügbar.'}, 409
    from shared.sse import stream_ai_sse
    return stream_ai_sse(system, prompt, finalize=lambda full: {'text': full},
                         force_json=bool(data.get('force_json')), temperature=0.2,
                         num_predict=2048)
