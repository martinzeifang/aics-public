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


@ai_status_bp.get('/models')
@jwt_required()
def list_models():
    """Verfügbare Modelle des aktuell konfigurierten Providers abrufen (für Auswahl-
    Dropdown). Cloud → Provider-``GET /models``; on_prem → Ollama-``/api/tags``.
    Keine Secrets in der Antwort. Fehler (z. B. ungültiger Key) → 502 mit Hinweis."""
    try:
        from ai_compliance_suite.ai.dispatch import build_provider, current_provider_name
        provider = build_provider()
        if not hasattr(provider, 'list_models'):
            return {'models': [], 'provider': current_provider_name(),
                    'error': 'Provider unterstützt keine Modell-Liste'}, 200
        models = provider.list_models()
        return {'models': sorted(set(models)), 'provider': current_provider_name()}, 200
    except Exception as e:  # noqa: BLE001 — Provider-/Konfig-Fehler an die UI durchreichen
        current_app.logger.warning('%s %s — %s: %s', request.method, request.path,
                                    type(e).__name__, e)
        return {'models': [], 'error': str(e)[:300]}, 502
