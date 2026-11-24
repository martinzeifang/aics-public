"""LDAP/Active Directory Authentication.

Optional LDAP integration for authentication.
Falls back to local authentication if LDAP is unavailable.
"""

from __future__ import annotations

import os
import logging
from typing import Optional

try:
    from ldap3 import Server, Connection, ALL, Tls
    from ldap3.utils.conv import escape_filter_chars
    LDAP_AVAILABLE = True
except ImportError:
    LDAP_AVAILABLE = False
    Tls = None  # type: ignore[assignment]

    def escape_filter_chars(text, encoding=None):  # type: ignore[misc]
        """Pure-Python-Fallback für ``ldap3.utils.conv.escape_filter_chars`` (#743).

        Neutralisiert LDAP-Filter-Metazeichen gemäß RFC 4515, falls ldap3 nicht
        installiert ist (z. B. CI ohne LDAP-Extra). Schützt vor
        LDAP-Filter-Injection (OWASP A03, ASVS V5).
        """
        if text is None:
            return text
        replacements = {
            '\\': '\\5c',
            '*': '\\2a',
            '(': '\\28',
            ')': '\\29',
            '\x00': '\\00',
        }
        return ''.join(replacements.get(ch, ch) for ch in str(text))

logger = logging.getLogger(__name__)


def build_search_filter(template: str, username: str) -> str:
    """Baue einen LDAP-Suchfilter mit escaptem Benutzernamen (#743).

    ``{username}`` im Template wird durch den per ``escape_filter_chars``
    neutralisierten Wert ersetzt, sodass Eingaben wie ``*)(uid=*`` keine
    Filter-Injection erlauben.
    """
    safe_username = escape_filter_chars(username or '')
    return template.replace('{username}', safe_username)


class LDAPConfig:
    """LDAP Configuration from Environment."""

    def __init__(self):
        self.enabled = os.getenv('LDAP_ENABLED', 'false').lower() == 'true'
        self.server_uri = os.getenv('LDAP_SERVER_URI', 'ldap://localhost:389')
        self.bind_dn = os.getenv('LDAP_BIND_DN', '')
        self.bind_password = os.getenv('LDAP_BIND_PASSWORD', '')
        self.user_base_dn = os.getenv('LDAP_USER_BASE_DN', 'ou=users,dc=example,dc=com')
        self.user_search_filter = os.getenv(
            'LDAP_USER_SEARCH_FILTER',
            '(|(uid={username})(mail={username}))'
        )
        self.timeout = int(os.getenv('LDAP_TIMEOUT', '10'))
        self.use_ssl = self.server_uri.startswith('ldaps://')
        # #1184: TLS-Härtung. StartTLS für ldap:// (Upgrade auf TLS nach Connect),
        # Zertifikatsvalidierung (required|optional|none) + optionale CA-Datei.
        # Klartext-LDAP (weder LDAPS noch StartTLS) ist nur mit expliziter
        # Risikoakzeptanz (LDAP_ALLOW_INSECURE=true) erlaubt → sonst fail-closed.
        self.use_starttls = os.getenv('LDAP_USE_STARTTLS', 'false').lower() == 'true'
        self.allow_insecure = os.getenv('LDAP_ALLOW_INSECURE', 'false').lower() == 'true'
        self.ca_cert_file = (os.getenv('LDAP_CA_CERT') or '').strip() or None
        self.tls_validate = (os.getenv('LDAP_TLS_VALIDATE', 'required') or 'required').lower()

    @property
    def is_secure(self) -> bool:
        """True, wenn die Verbindung TLS-geschützt ist (LDAPS oder StartTLS)."""
        return bool(self.use_ssl or self.use_starttls)

    def security_error(self) -> Optional[str]:
        """Fail-closed-Check: Klartext-LDAP ohne Risikoakzeptanz wird abgelehnt (#1184)."""
        if not self.is_secure and not self.allow_insecure:
            return (f'Unsichere LDAP-Konfiguration: {self.server_uri} nutzt weder LDAPS '
                    'noch StartTLS. Für den Produktivbetrieb LDAPS (ldaps://) oder '
                    'LDAP_USE_STARTTLS=true setzen. Klartext nur mit expliziter '
                    'Risikoakzeptanz LDAP_ALLOW_INSECURE=true.')
        return None

    def build_tls(self):
        """ldap3.Tls-Objekt mit Zertifikatsvalidierung (oder None ohne TLS/Validierung)."""
        if Tls is None or (not self.is_secure):
            return None
        import ssl
        if self.tls_validate == 'none' or self.allow_insecure:
            return Tls(validate=ssl.CERT_NONE)
        validate = ssl.CERT_OPTIONAL if self.tls_validate == 'optional' else ssl.CERT_REQUIRED
        return Tls(validate=validate, ca_certs_file=self.ca_cert_file)

    def is_configured(self) -> bool:
        """Check if LDAP is properly configured."""
        return (
            self.enabled
            and self.server_uri
            and self.bind_dn
            and self.bind_password
            and self.user_base_dn
        )


class LDAPAuthenticator:
    """LDAP Authentication Handler."""

    def __init__(self, config: LDAPConfig):
        if not LDAP_AVAILABLE:
            raise RuntimeError('ldap3 library required. Install with: pip install ldap3')
        self.config = config
        self._connection: Optional[Connection] = None

    def _make_server(self) -> "Server":
        """Server mit TLS-Konfiguration (#1184)."""
        return Server(
            self.config.server_uri,
            get_info=ALL,
            connect_timeout=self.config.timeout,
            use_ssl=self.config.use_ssl,
            tls=self.config.build_tls(),
        )

    def _bind(self, server, user, password):
        """Connection herstellen; bei StartTLS vor dem Bind auf TLS upgraden (#1184)."""
        if self.config.use_starttls and not self.config.use_ssl:
            conn = Connection(server, user=user, password=password, auto_bind=False)
            conn.open()
            conn.start_tls()
            if not conn.bind():
                conn.unbind()
                raise RuntimeError('LDAP bind failed after StartTLS')
            return conn
        return Connection(server, user=user, password=password, auto_bind=True)

    def test_connection(self) -> bool:
        """Test LDAP server connectivity."""
        sec_err = self.config.security_error()
        if sec_err:
            logger.error("✗ %s", sec_err)
            return False
        try:
            server = self._make_server()
            conn = self._bind(server, self.config.bind_dn, self.config.bind_password)
            conn.unbind()
            logger.info(f"✓ LDAP connection successful ({'TLS' if self.config.is_secure else 'PLAINTEXT'}): {self.config.server_uri}")
            return True
        except Exception as e:
            logger.error(f"✗ LDAP connection failed: {e}")
            return False

    def authenticate(self, username: str, password: str) -> Optional[dict]:
        """Authenticate user against LDAP.

        Args:
            username: Username or email
            password: User password

        Returns:
            Dict with user info if successful, None otherwise
        """
        if not password:
            return None

        # #1184: fail-closed — Klartext-LDAP ohne Risikoakzeptanz ablehnen.
        sec_err = self.config.security_error()
        if sec_err:
            logger.error("LDAP-Authentifizierung abgelehnt: %s", sec_err)
            return None

        try:
            server = self._make_server()

            # Bind as service account to search for user
            bind_conn = self._bind(server, self.config.bind_dn, self.config.bind_password)

            # Search for user — #743: Benutzernamen gegen LDAP-Filter-Injection
            # escapen (RFC 4515) bevor er in den Filter eingesetzt wird.
            search_filter = build_search_filter(
                self.config.user_search_filter, username
            )
            bind_conn.search(
                search_base=self.config.user_base_dn,
                search_filter=search_filter,
                attributes=['*', '+'],
            )

            if not bind_conn.entries:
                logger.warning(f"LDAP user not found: {username}")
                bind_conn.unbind()
                return None

            user_entry = bind_conn.entries[0]
            user_dn = user_entry.entry_dn
            bind_conn.unbind()

            # Try to bind as the user to verify password (TLS-/StartTLS-bewusst)
            user_conn = self._bind(server, user_dn, password)
            user_conn.unbind()

            # Extract user info
            user_info = {
                'id': str(user_entry.get('uid', username)),
                'email': str(user_entry.get('mail', f'{username}@company.com')),
                'name': str(user_entry.get('displayName', username)),
                'dn': user_dn,
                'groups': _extract_groups(user_entry),
            }

            logger.info(f"✓ LDAP authentication successful: {username}")
            return user_info

        except Exception as e:
            logger.warning(f"LDAP authentication failed for {username}: {e}")
            return None


def get_ldap_authenticator() -> Optional[LDAPAuthenticator]:
    """Get LDAP authenticator if configured.

    Returns:
        LDAPAuthenticator if enabled and available, None otherwise
    """
    config = LDAPConfig()

    if not config.enabled:
        return None

    if not LDAP_AVAILABLE:
        logger.warning(
            'LDAP_ENABLED=true but ldap3 not installed. '
            'Install with: pip install ldap3'
        )
        return None

    if not config.is_configured():
        logger.warning(
            'LDAP enabled but not properly configured. '
            'Required env vars: LDAP_SERVER_URI, LDAP_BIND_DN, LDAP_BIND_PASSWORD'
        )
        return None

    # #1184: Klartext-LDAP ohne Risikoakzeptanz → LDAP deaktivieren + klar melden.
    sec_err = config.security_error()
    if sec_err:
        logger.error('LDAP deaktiviert (Sicherheits-Fehlkonfiguration): %s', sec_err)
        try:
            from shared.audit import audit_event
            audit_event('auth.ldap.insecure_config', module='auth', outcome='fail',
                        details={'server_uri': config.server_uri,
                                 'use_ssl': config.use_ssl, 'use_starttls': config.use_starttls})
        except Exception:
            pass
        return None

    try:
        authenticator = LDAPAuthenticator(config)
        if authenticator.test_connection():
            return authenticator
    except Exception as e:
        logger.error(f"Failed to initialize LDAP: {e}")

    return None


def _extract_groups(user_entry) -> list[str]:
    """Extract group membership from LDAP entry.

    Args:
        user_entry: LDAP entry object

    Returns:
        List of group names
    """
    groups = []
    for group_attr in ['memberOf', 'groups', 'groupMembership']:
        if hasattr(user_entry, group_attr):
            group_list = getattr(user_entry, group_attr)
            if group_list:
                for group_dn in group_list:
                    # Extract CN from DN (e.g., "cn=admins,ou=groups,dc=example,dc=com")
                    group_name = group_dn.split(',')[0].replace('cn=', '').strip()
                    groups.append(group_name)
    return groups


def map_ldap_groups_to_roles(ldap_groups: list[str], group_mapping: dict) -> list[str]:
    """Map LDAP groups to application roles.

    Args:
        ldap_groups: List of LDAP group names
        group_mapping: Dict mapping LDAP group → app role
                      e.g., {'admins': 'admin', 'editors': 'cra_editor'}

    Returns:
        List of application roles
    """
    roles = []
    for ldap_group in ldap_groups:
        if ldap_group in group_mapping:
            role = group_mapping[ldap_group]
            if role not in roles:
                roles.append(role)
    return roles


# Example configuration for environment variables:
"""
# Enable LDAP authentication
export LDAP_ENABLED=true

# LDAP Server
export LDAP_SERVER_URI=ldap://ldap.example.com:389
# Or for Active Directory with TLS:
# export LDAP_SERVER_URI=ldaps://ad.example.com:636

# Service account for LDAP bind (read-only)
export LDAP_BIND_DN=cn=admin,dc=example,dc=com
export LDAP_BIND_PASSWORD=service-account-password

# User search base
export LDAP_USER_BASE_DN=ou=users,dc=example,dc=com

# Optional: customize search filter
# export LDAP_USER_SEARCH_FILTER=(|(uid={username})(mail={username}))

# Optional: timeout in seconds
# export LDAP_TIMEOUT=10

# Group to role mapping (JSON)
# export LDAP_GROUP_MAPPING='{"admins": "admin", "editors": "cra_editor"}'
"""
