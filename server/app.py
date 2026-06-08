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

    # #739 (AUTH-3/CFG-4): Hinter Reverse-Proxy die echte Client-IP aus
    # X-Forwarded-* übernehmen (für Rate-Limiting/Audit). Anzahl vertrauenswürdiger
    # Proxies über TRUSTED_PROXY_COUNT (Default 1 = nginx). 0 = deaktiviert.
    try:
        import os as _os
        _hops = int(_os.getenv('TRUSTED_PROXY_COUNT', '1'))
        if _hops > 0:
            from werkzeug.middleware.proxy_fix import ProxyFix
            app.wsgi_app = ProxyFix(app.wsgi_app, x_for=_hops, x_proto=_hops,
                                    x_host=_hops, x_port=_hops)
    except Exception:  # noqa: BLE001
        pass

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

    # Token-Blacklist-Hook: prüft jeden Token gegen revoked_tokens UND die
    # Token-Version des Users (#738 / AUTH-13: Deaktivierung/Rollenänderung
    # invalidiert bestehende Tokens sofort).
    @jwt.token_in_blocklist_loader
    def _check_token_revoked(jwt_header, jwt_payload):
        from server.auth.users_db import is_token_revoked, get_token_version
        jti = jwt_payload.get('jti', '')
        if is_token_revoked(jti):
            return True
        # 2FA-Challenge-Tokens tragen kein 'tv' und sind kurzlebig → nicht prüfen
        if jwt_payload.get('twofa_challenge'):
            return False
        sub = jwt_payload.get('sub')
        tv_claim = jwt_payload.get('tv')
        if sub and tv_claim is not None:
            try:
                if get_token_version(sub) != int(tv_claim):
                    return True  # Token-Version veraltet → revoziert
            except Exception:
                return False
        return False

    # Logging
    _setup_logging(app)

    # Middleware
    register_audit_middleware(app)

    # Database
    with app.app_context():
        if not initialize_databases():
            app.logger.warning("⚠ Some databases failed health check")

    # OpenAPI/Swagger (#744 / WP-11, OWASP A05): Die Swagger-UI + OpenAPI-Spec
    # legen die komplette API-Oberfläche offen. In Produktion ist das eine
    # unnötige Angriffsfläche → nur ausserhalb von FLASK_ENV=production
    # registrieren (Dev/Test/Staging). Tests laufen mit FLASK_ENV=testing.
    if HAS_SWAGGER and os.getenv('FLASK_ENV', '').lower() != 'production':
        _configure_swagger(app)

    # Blueprints (später: prefill, cra, etc.)
    _register_blueprints(app)

    # License-State + Heartbeat (Issue #365)
    try:
        from server import license_state
        license_state.init_app(app)
    except Exception as e:  # noqa: BLE001
        app.logger.warning('License-State-Init fehlgeschlagen: %s', e)

    # C3 In-App-Scheduler (#949) — opt-in via cra.config.json, nie in Tests,
    # nur ein Worker (File-Lock). Schlägt nie hart fehl.
    if os.getenv('FLASK_ENV', '').lower() != 'testing':
        try:
            import atexit
            from cra.config import load_config as _load_cra_cfg
            from shared.scheduler import start_scheduler, stop_scheduler
            start_scheduler(app, _load_cra_cfg())
            atexit.register(stop_scheduler)
        except Exception as e:  # noqa: BLE001
            app.logger.warning('In-App-Scheduler-Init fehlgeschlagen: %s', e)

    # #738 (AUTH-5): 2FA-Challenge-Tokens dürfen NUR die 2FA-Verify-Endpunkte
    # ansprechen — sonst ließe sich der halbfertige 1-Faktor-Token z.B. an
    # /api/auth/refresh zu einem Vollzugriff eskalieren (2FA-Bypass).
    @app.before_request
    def _reject_challenge_tokens():
        from flask import request as _req, jsonify as _jsonify
        if _req.method == 'OPTIONS':
            return None
        allow = (
            '/api/auth/login/verify-2fa',
            '/api/auth/webauthn/login/2fa-options',
            '/api/auth/webauthn/login/2fa-verify',
        )
        if _req.path in allow:
            return None
        try:
            from flask_jwt_extended import verify_jwt_in_request, get_jwt
            verify_jwt_in_request(optional=True)
            claims = get_jwt() or {}
        except Exception:
            return None  # ungültiger/kein Token → normale Handler greifen
        if claims.get('twofa_challenge'):
            return _jsonify({'error': '2FA-Challenge-Token hier nicht gültig'}), 401
        return None

    # Zentrale serverseitige Autorisierung für Fach-Module (#734 / WP-01).
    # MUSS vor dem Lizenz-Read-Only-Guard registriert werden, damit Unberechtigte
    # 401/403 erhalten und der Lizenzstatus (423) ihnen nicht offenbart wird.
    from server.middleware.authz import register_module_authz
    register_module_authz(app)

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
            # Spezial: 'firmen' immer erlaubt, '*' erlaubt alle außer 'gutachten'.
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
    # #744 (WP-11, OWASP A05): Health-Body minimal halten — keine internen
    # Details (Service-Namen/Versionen) preisgeben. Behält 200 + JSON mit
    # status-Feld, damit Docker/Nginx-Healthchecks + /api/health-Tests grün
    # bleiben.
    def _health():
        return {'status': 'healthy'}, 200
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
        import uuid as _uuid
        request_id = _uuid.uuid4().hex[:12]
        app.logger.exception(
            'Unhandled %s on %s %s [req=%s] — %s',
            type(exc).__name__, _req.method, _req.path, request_id, str(exc),
        )
        # #737: keine internen Details an den Client (Information Disclosure).
        # Exception-Text/Typ nur im Server-Log; Client erhält Korrelations-ID.
        return _jsonify({
            'error': 'Interner Serverfehler',
            'request_id': request_id,
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
            'description': 'REST API für Multi-Modul-Compliance-Verwaltung (CRA, NIS2, AI-Act, DORA, Risikobewertung, Firmen).',
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
            {'name': 'firmen', 'description': 'Firmenverwaltung + Multi-Produkt + Evidence'},
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

    # #743 (WP-10 / OWASP A04, ASVS V12): Globales Limit für Request-Bodies.
    # Flask lehnt zu große Uploads/Requests automatisch mit 413 ab, bevor sie
    # vollständig in den Speicher gelesen werden. Default 64 MB, per ENV
    # MAX_CONTENT_LENGTH_MB überschreibbar.
    try:
        max_mb = int(os.getenv('MAX_CONTENT_LENGTH_MB', '64'))
    except (TypeError, ValueError):
        max_mb = 64
    if max_mb <= 0:
        max_mb = 64
    app.config['MAX_CONTENT_LENGTH'] = max_mb * 1024 * 1024


def _configure_cors(app: Flask):
    """Konfiguriere CORS restrictiv (#744 / WP-11, OWASP A05).

    Fail-closed: ohne explizite CORS_ORIGINS-Konfiguration werden in Produktion
    KEINE Cross-Origin-Requests erlaubt (leere Allow-Liste). HTTP-Origins
    (unverschlüsselt) gibt es nur als Default im Dev-Profil
    (FLASK_ENV != production), wo Vite über localhost spricht. In Produktion
    müssen erlaubte (HTTPS-)Origins explizit per CORS_ORIGINS gesetzt werden.
    """
    is_production = os.getenv('FLASK_ENV', '').lower() == 'production'

    if is_production:
        # Produktion: keine HTTP-Defaults — nur was explizit gesetzt wurde.
        default_origins = ''
    else:
        # Dev/Test: Vite-Dev-Ports (5173-5175) mit HTTP+HTTPS, plus 3000.
        default_origins = (
            'https://localhost:5173,https://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5173,'
            'https://localhost:5174,https://127.0.0.1:5174,http://localhost:5174,http://127.0.0.1:5174,'
            'https://localhost:5175,https://127.0.0.1:5175,http://localhost:5175,http://127.0.0.1:5175,'
            'http://localhost:3000'
        )

    allowed_origins = os.getenv('CORS_ORIGINS', default_origins).split(',')
    allowed_origins = [o.strip() for o in allowed_origins if o.strip()]

    # In Produktion zusätzlich unverschlüsselte (http://) Origins verwerfen —
    # auch wenn sie versehentlich per CORS_ORIGINS gesetzt wurden.
    if is_production:
        allowed_origins = [o for o in allowed_origins if not o.lower().startswith('http://')]

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

    # WebAuthn / Passkeys (Sprint ε)
    from server.api.webauthn import webauthn_bp
    app.register_blueprint(webauthn_bp, url_prefix='/api/auth/webauthn')

    # Zertifikats-Verwaltung (Self-Signed-Wizard + CSR für PKI)
    from server.api.certificates import certificates_bp
    app.register_blueprint(certificates_bp, url_prefix='/api/admin/certificates')

    # Admin
    from server.api.admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/api/admin')

    # Cross-Module Word-Vorlagen-Engine (#988)
    from server.api.templates import templates_bp
    app.register_blueprint(templates_bp, url_prefix='/api/templates')

    # Firmen Management (vormals „Kunden", #1003)
    from server.api.firmen import firmen_bp
    app.register_blueprint(firmen_bp, url_prefix='/api/firmen')
    # Deprecation-Alias: alte Route /api/kunden bleibt ≥1 Release erhalten
    app.register_blueprint(firmen_bp, url_prefix='/api/kunden', name='kunden_alias')

    # CRA Module
    from server.api.cra import cra_bp
    app.register_blueprint(cra_bp, url_prefix='/api/cra')

    # WiBA Module (BSI Weg in die Basis-Absicherung)
    from server.api.wiba import wiba_bp
    app.register_blueprint(wiba_bp, url_prefix='/api/wiba')

    # Risikobewertung Module
    from server.api.risikobewertung import rb_bp
    app.register_blueprint(rb_bp, url_prefix='/api/risikobewertung')

    # DSGVO Module
    from server.api.dsgvo import dsgvo_bp
    app.register_blueprint(dsgvo_bp, url_prefix='/api/dsgvo')

    # DSGVO DSMS-Bereiche (Sprint #23): eigene Blueprints je Bereich
    from server.api.dsgvo_tom import dsgvo_tom_bp
    app.register_blueprint(dsgvo_tom_bp, url_prefix='/api/dsgvo-tom')
    from server.api.dsgvo_betroffenenrechte import dsgvo_betroffenenrechte_bp
    app.register_blueprint(dsgvo_betroffenenrechte_bp, url_prefix='/api/dsgvo-betroffenenrechte')
    from server.api.dsgvo_transfer import dsgvo_transfer_bp
    app.register_blueprint(dsgvo_transfer_bp, url_prefix='/api/dsgvo-transfer')
    from server.api.dsgvo_loeschkonzept import dsgvo_loeschkonzept_bp
    app.register_blueprint(dsgvo_loeschkonzept_bp, url_prefix='/api/dsgvo-loeschkonzept')
    from server.api.dsgvo_einwilligung import dsgvo_einwilligung_bp
    app.register_blueprint(dsgvo_einwilligung_bp, url_prefix='/api/dsgvo-einwilligung')
    from server.api.dsgvo_dsb import dsgvo_dsb_bp
    app.register_blueprint(dsgvo_dsb_bp, url_prefix='/api/dsgvo-dsb')
    from server.api.dsgvo_cockpit import dsgvo_cockpit_bp
    app.register_blueprint(dsgvo_cockpit_bp, url_prefix='/api/dsgvo-cockpit')

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

    # Zentrales Risiko-Cockpit (Sprint #21 — S8, #1078)
    from server.api.risk_cockpit import risk_cockpit_bp
    app.register_blueprint(risk_cockpit_bp, url_prefix='/api/risk-cockpit')

    # KI-Provider-Status (Sprint #16 — KI-Transparenz, #867/#877)
    from server.api.ai_status import ai_status_bp
    app.register_blueprint(ai_status_bp, url_prefix='/api/ai')


def _build_csp() -> str:
    """Baue eine strikte Content-Security-Policy (Issue #740, WP-07).

    Sicher per Default: ``script-src 'self'`` OHNE ``unsafe-inline``/``unsafe-eval``.
    Ein Vue-3-Production-Build (vorkompilierte Templates) benötigt KEIN ``unsafe-eval``.
    ``style-src`` behält ``'unsafe-inline'``, da Vue Inline-Styles injiziert.

    Vollständig per Umgebungsvariable ``CONTENT_SECURITY_POLICY`` überschreibbar.
    """
    override = os.getenv('CONTENT_SECURITY_POLICY')
    if override:
        return override
    return '; '.join([
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "frame-ancestors 'none'",
    ])


def _register_security_headers(app: Flask):
    """Registriere Security Headers."""
    csp = _build_csp()

    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = csp
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
