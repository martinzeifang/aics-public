"""Flask-Middleware für automatisches Audit-Logging von HTTP-Requests."""

import time
from flask import Flask, request, g

from shared.audit import log_http_request


def register_audit_middleware(app: Flask):
    """Registriere Audit-Logging Middleware in Flask-App.

    Usage:
        app = Flask(__name__)
        register_audit_middleware(app)
    """

    @app.before_request
    def before_request():
        """Markiere Start der Request-Verarbeitung."""
        g.start_time = time.time()

    @app.after_request
    def after_request(response):
        """Logge fertige HTTP-Request mit Audit-Trail."""
        if not hasattr(g, 'start_time'):
            return response

        duration_ms = (time.time() - g.start_time) * 1000
        # #1187: Actor erst NACH der JWT-Verifikation ermitteln (im before_request
        # ist die JWT noch nicht geprüft → Actor blieb meist leer).
        user_id = _get_user_id()

        log_http_request(
            method=request.method,
            path=request.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            user_id=user_id,
            ip_address=_get_client_ip(),
            user_agent=request.headers.get('User-Agent'),
        )

        return response


def _get_user_id() -> str | None:
    """Extrahiere User-ID aus JWT-Claims — mit eigener (optionaler) Verifikation.

    #1187: ``verify_jwt_in_request(optional=True)`` stellt sicher, dass die JWT
    tatsächlich geprüft ist, bevor die Identity gelesen wird (sonst leerer Actor).
    """
    try:
        from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        if not identity:
            return None
        return identity if isinstance(identity, str) else identity.get('user_id')
    except Exception:
        return None


def _get_client_ip() -> str:
    """Bestimme Client-IP-Adresse.

    #1187: ``ProxyFix`` setzt ``request.remote_addr`` bereits korrekt aus dem
    vertrauenswürdigen X-Forwarded-For (vom konfigurierten Proxy). Daher NICHT
    blind dem rohen X-Forwarded-For-Header trauen, sondern ``remote_addr`` nutzen.
    """
    return request.remote_addr or 'unknown'
