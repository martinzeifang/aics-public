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
        g.user_id = _get_user_id()

    @app.after_request
    def after_request(response):
        """Logge fertige HTTP-Request mit Audit-Trail."""
        if not hasattr(g, 'start_time'):
            return response

        duration_ms = (time.time() - g.start_time) * 1000
        user_id = getattr(g, 'user_id', None)

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
    """Extrahiere User-ID aus JWT-Claims (falls vorhanden)."""
    try:
        # Import here to avoid circular dependency
        from flask_jwt_extended import get_jwt_identity
        identity = get_jwt_identity()
        return identity if isinstance(identity, str) else identity.get('user_id') if identity else None
    except Exception:
        return None


def _get_client_ip() -> str:
    """Bestimme Client-IP-Adresse (auch hinter Proxy)."""
    # X-Forwarded-For (bei Proxy/Load-Balancer)
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    # X-Real-IP (Alternative)
    if request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    # Direct connection
    return request.remote_addr
