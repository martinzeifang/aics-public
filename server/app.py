"""Flask Application Factory.

Erstellt und konfiguriert die Flask-App mit allen Blueprints und Middleware.
"""

from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path

from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from flask_cors import CORS

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    HAS_LIMITER = True
except ImportError:
    HAS_LIMITER = False

try:
    from flasgger import Swagger
    HAS_SWAGGER = True
except ImportError:
    HAS_SWAGGER = False

from server.config.database import initialize_databases
from server.middleware.audit import register_audit_middleware


def create_app(config_file: str | None = None) -> Flask:
    """Erstelle und konfiguriere Flask-App.

    Args:
        config_file: Pfad zu Konfigurationsdatei (optional)

    Returns:
        Konfigurierte Flask-App
    """
    app = Flask(__name__)

    # Konfiguration
    _configure_security(app)

    # CORS
    _configure_cors(app)

    # Rate Limiting (Legacy für Login)
    app.login_attempts = {}  # {ip: (count, timestamp)}

    # Flask-Limiter (global rate limiting)
    if HAS_LIMITER:
        limiter = Limiter(
            app=app,
            key_func=get_remote_address,
            default_limits=['1000 per hour', '100 per minute'],
            storage_uri='memory://',
        )
        # Strenge Limits für Auth + Admin
        limiter.limit('20 per minute')(app.view_functions.get('auth.login') or (lambda: None))
        app.limiter = limiter
    else:
        app.logger.warning('flask-limiter not installed — using fallback Rate-Limiting only on Login')

    # JWT
    jwt = JWTManager(app)

    # Token-Blacklist-Hook: prüft jeden Token gegen revoked_tokens
    @jwt.token_in_blocklist_loader
    def _check_token_revoked(jwt_header, jwt_payload):
        from server.auth.users_db import is_token_revoked
        jti = jwt_payload.get('jti', '')
        return is_token_revoked(jti)

    # Logging
    _setup_logging(app)

    # Middleware
    register_audit_middleware(app)

    # Database
    with app.app_context():
        if not initialize_databases():
            app.logger.warning("⚠ Some databases failed health check")

    # OpenAPI/Swagger
    if HAS_SWAGGER:
        _configure_swagger(app)

    # Blueprints (später: prefill, cra, etc.)
    _register_blueprints(app)

    # License-State + Heartbeat (Issue #365)
    try:
        from server import license_state
        license_state.init_app(app)
    except Exception as e:  # noqa: BLE001
        app.logger.warning('License-State-Init fehlgeschlagen: %s', e)

    # Read-Only-Mode: bei Lizenz-Verstoß alle Schreib-Endpoints blockieren
    # außer /api/license/*, /api/auth/*, /api/admin/* (Issue #369)
    @app.before_request
    def _enforce_read_only():
        from flask import request as _req
        if _req.method in ('GET', 'HEAD', 'OPTIONS'):
            return None
        path = _req.path or ''
        if not path.startswith('/api/'):
            return None
        # Whitelist: Auth/Admin/License immer durchlassen damit Recovery möglich
        for white in ('/api/auth/', '/api/admin/', '/api/license/', '/api/health'):
            if path.startswith(white):
                return None
        try:
            from server import license_state
            st = license_state.get_state()
            if st.is_read_only:
                return jsonify({
                    'error': 'license-read-only',
                    'reason': st.reason or 'license-violation',
                    'license_state': st.state,
                }), 423

            # #413: Modul-spezifischer Schutz — Schreib-Endpoints in nicht-
            # lizenzierten Modulen blocken (423). Endpoint-Path-Beispiele:
            #   /api/cra/...     /api/risikobewertung/...   /api/gutachten/...
            # Spezial: 'kunden' immer erlaubt, '*' erlaubt alle außer 'gutachten'.
            LIC_MODULES = {'cra', 'nis2', 'dora', 'aiact', 'dsgvo', 'risikobewertung', 'gutachten'}
            parts = path.lstrip('/').split('/')
            if len(parts) >= 2 and parts[0] == 'api' and parts[1] in LIC_MODULES:
                mod = parts[1]
                allowed = st.is_module_allowed  # None=alle | set | empty
                if isinstance(allowed, set):
                    is_ok = (mod in allowed) and (mod != 'gutachten' or 'gutachten' in allowed)
                elif allowed is None:
                    # Wildcard: alles erlaubt AUSSER gutachten
                    is_ok = (mod != 'gutachten')
                else:
                    is_ok = False
                if not is_ok:
                    return jsonify({
                        'error': 'module-not-licensed',
                        'module': mod,
                        'license_state': st.state,
                    }), 423
        except Exception:
            pass
        return None

    # Health Check (sowohl /health für Docker/Nginx-Healthchecks als auch
    # /api/health für die Frontend-StatusBar, damit beide via baseURL=/api funktionieren)
    def _health():
        return {'status': 'healthy', 'service': 'ai-compliance-suite-web'}, 200
    app.add_url_rule('/health', 'health', _health, methods=['GET'])
    app.add_url_rule('/api/health', 'api_health', _health, methods=['GET'])

    # Security Headers
    _register_security_headers(app)

    # Error Handlers
    _register_error_handlers(app)

    app.logger.info("✓ Flask app initialized")
    return app


def _setup_logging(app: Flask):
    """Konfiguriere Logging.

    - app.log: alle Application-Logs (INFO + Exceptions inkl. Traceback)
    - audit.log: HTTP-Request-Audit (separates Format)
    """
    from pathlib import Path
    Path('logs').mkdir(exist_ok=True)

    # App-Logger: schreibt in stderr UND logs/app.log
    fmt = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S',
    )

    # Vorhandene Handler entfernen, damit wir nicht doppelt loggen
    app.logger.handlers.clear()
    app.logger.setLevel(logging.INFO)

    stream_h = logging.StreamHandler()
    stream_h.setLevel(logging.INFO)
    stream_h.setFormatter(fmt)
    app.logger.addHandler(stream_h)

    file_h = logging.FileHandler('logs/app.log', encoding='utf-8')
    file_h.setLevel(logging.INFO)
    file_h.setFormatter(fmt)
    app.logger.addHandler(file_h)

    # Werkzeug-Logger anhängen (sonst landen 500-Tracebacks nicht in app.log)
    wz = logging.getLogger('werkzeug')
    wz.addHandler(file_h)
    wz.setLevel(logging.INFO)

    # Globale Error-Handler: jeder unbehandelte Fehler → app.log + 500
    @app.errorhandler(Exception)
    def _handle_uncaught(exc):
        from flask import request as _req, jsonify as _jsonify
        from werkzeug.exceptions import HTTPException
        if isinstance(exc, HTTPException):
            return exc
        app.logger.exception(
            'Unhandled %s on %s %s — %s',
            type(exc).__name__, _req.method, _req.path, str(exc),
        )
        return _jsonify({
            'error': str(exc),
            'type': type(exc).__name__,
            'path': _req.path,
        }), 500

    # Audit Logger (HTTP-Requests)
    audit_logger = logging.getLogger('audit')
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False
    if not audit_logger.handlers:
        h = logging.FileHandler('logs/audit.log', encoding='utf-8')
        h.setFormatter(logging.Formatter('%(message)s'))
        audit_logger.addHandler(h)


def _configure_swagger(app: Flask):
    """OpenAPI 3.0 / Swagger-UI unter /api/docs."""
    swagger_config = {
        'headers': [],
        'specs': [
            {
                'endpoint': 'apispec',
                'route': '/api/apispec.json',
                'rule_filter': lambda rule: True,
                'model_filter': lambda tag: True,
            }
        ],
        'static_url_path': '/api/flasgger_static',
        'swagger_ui': True,
        'specs_route': '/api/docs/',
    }
    swagger_template = {
        'swagger': '2.0',
        'info': {
            'title': 'AI Compliance Suite API',
            'description': 'REST API für Multi-Modul-Compliance-Verwaltung (CRA, NIS2, AI-Act, DORA, Risikobewertung, Kunden).',
            'version': '1.0.0',
            'contact': {
                'name': 'Martin Zeifang',
                'url': 'https://github.com/martinzeifang/AI_Compliance_Suite',
            },
        },
        'basePath': '/api',
        'schemes': ['https', 'http'],
        'securityDefinitions': {
            'Bearer': {
                'type': 'apiKey',
                'name': 'Authorization',
                'in': 'header',
                'description': 'JWT-Token. Login via POST /auth/login → access_token. Format: "Bearer <token>"',
            }
        },
        'security': [{'Bearer': []}],
        'tags': [
            {'name': 'auth', 'description': 'Authentifizierung + JWT-Token'},
            {'name': 'admin', 'description': 'Admin-Funktionen (Settings, Audit, Backup, DB-Viewer)'},
            {'name': 'kunden', 'description': 'Kundenverwaltung + Multi-Produkt + Evidence'},
            {'name': 'cra', 'description': 'Cyber Resilience Act (EU 2024/2847)'},
            {'name': 'nis2', 'description': 'NIS2-Richtlinie (EU 2022/2555)'},
            {'name': 'aiact', 'description': 'EU AI Act (EU 2024/1689)'},
            {'name': 'dora', 'description': 'DORA (EU 2022/2554)'},
            {'name': 'risikobewertung', 'description': 'Multi-Framework-Risikobewertung'},
            {'name': 'issues', 'description': 'Cross-Modul Issue-Übersicht'},
        ],
    }
    Swagger(app, config=swagger_config, template=swagger_template)


def _configure_security(app: Flask):
    """Konfiguriere Security-Settings."""
    app.config['JSON_SORT_KEYS'] = False
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

    jwt_secret = os.getenv('JWT_SECRET_KEY')
    if not jwt_secret:
        raise RuntimeError(
            'JWT_SECRET_KEY environment variable is required. '
            'Generate with: python -c "import secrets; print(secrets.token_hex(32))"'
        )

    if len(jwt_secret) < 32:
        raise RuntimeError(f'JWT_SECRET_KEY must be at least 32 bytes, got {len(jwt_secret)}')

    app.config['JWT_SECRET_KEY'] = jwt_secret
    app.config['PREFERRED_URL_SCHEME'] = 'https'


def _configure_cors(app: Flask):
    """Konfiguriere CORS restrictiv."""
    # Default: allow Vite dev ports (5173-5175) with both HTTP and HTTPS, plus alternative (3000)
    default_origins = 'https://localhost:5173,https://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5173,https://localhost:5174,https://127.0.0.1:5174,http://localhost:5174,http://127.0.0.1:5174,https://localhost:5175,https://127.0.0.1:5175,http://localhost:5175,http://127.0.0.1:5175,http://localhost:3000'
    allowed_origins = os.getenv('CORS_ORIGINS', default_origins).split(',')
    allowed_origins = [o.strip() for o in allowed_origins if o.strip()]

    cors_config = {
        "origins": allowed_origins,
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": True,
        "max_age": 3600,
    }

    CORS(app, resources={r"/api/*": cors_config})


def _register_blueprints(app: Flask):
    """Registriere alle Blueprints."""
    # Auth
    from server.api.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')

    # License (Issue #367)
    from server.api.license import license_bp
    app.register_blueprint(license_bp, url_prefix='/api/license')

    # 2FA / TOTP (Phase 7.3)
    from server.api.twofa import twofa_bp
    app.register_blueprint(twofa_bp, url_prefix='/api/auth/2fa')

    # Admin
    from server.api.admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/api/admin')

    # Kunden Management
    from server.api.kunden import kunden_bp
    app.register_blueprint(kunden_bp, url_prefix='/api/kunden')

    # CRA Module
    from server.api.cra import cra_bp
    app.register_blueprint(cra_bp, url_prefix='/api/cra')

    # Risikobewertung Module
    from server.api.risikobewertung import rb_bp
    app.register_blueprint(rb_bp, url_prefix='/api/risikobewertung')

    # DSGVO Module
    from server.api.dsgvo import dsgvo_bp
    app.register_blueprint(dsgvo_bp, url_prefix='/api/dsgvo')

    # NIS2 Module
    from server.api.nis2 import nis2_bp
    app.register_blueprint(nis2_bp, url_prefix='/api/nis2')

    # BASO Module
    from server.api.baso import baso_bp
    app.register_blueprint(baso_bp, url_prefix='/api/baso')

    # ICT Module
    from server.api.ict import ict_bp
    app.register_blueprint(ict_bp, url_prefix='/api/ict')

    # Gutachten Module
    from server.api.gutachten import gutachten_bp
    app.register_blueprint(gutachten_bp, url_prefix='/api/gutachten')

    # AI Act Module
    from server.api.aiact import aiact_bp
    app.register_blueprint(aiact_bp, url_prefix='/api/aiact')

    # DORA Module
    from server.api.dora import dora_bp
    app.register_blueprint(dora_bp, url_prefix='/api/dora')

    # Cross-Modul Issues Overview
    from server.api.issues import issues_bp
    app.register_blueprint(issues_bp, url_prefix='/api/issues')


def _register_security_headers(app: Flask):
    """Registriere Security Headers."""
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';"
        return response


def _register_error_handlers(app: Flask):
    """Registriere Error-Handler."""

    @app.errorhandler(401)
    def unauthorized(e):
        return {'error': 'Unauthorized'}, 401

    @app.errorhandler(403)
    def forbidden(e):
        return {'error': 'Forbidden'}, 403

    @app.errorhandler(404)
    def not_found(e):
        return {'error': 'Not Found'}, 404

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.exception(e)
        return {'error': 'Internal Server Error'}, 500
