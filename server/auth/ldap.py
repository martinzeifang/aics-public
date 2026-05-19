"""LDAP/Active Directory Authentication.

Optional LDAP integration for authentication.
Falls back to local authentication if LDAP is unavailable.
"""

from __future__ import annotations

import os
import logging
from typing import Optional

try:
    from ldap3 import Server, Connection, ALL
    LDAP_AVAILABLE = True
except ImportError:
    LDAP_AVAILABLE = False

logger = logging.getLogger(__name__)


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

    def test_connection(self) -> bool:
        """Test LDAP server connectivity."""
        try:
            server = Server(
                self.config.server_uri,
                get_info=ALL,
                connect_timeout=self.config.timeout,
                use_ssl=self.config.use_ssl,
            )
            conn = Connection(
                server,
                user=self.config.bind_dn,
                password=self.config.bind_password,
                auto_bind=True,
            )
            conn.unbind()
            logger.info(f"✓ LDAP connection successful: {self.config.server_uri}")
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

        try:
            server = Server(
                self.config.server_uri,
                get_info=ALL,
                connect_timeout=self.config.timeout,
                use_ssl=self.config.use_ssl,
            )

            # Bind as service account to search for user
            bind_conn = Connection(
                server,
                user=self.config.bind_dn,
                password=self.config.bind_password,
                auto_bind=True,
            )

            # Search for user
            search_filter = self.config.user_search_filter.replace(
                '{username}', username
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

            # Try to bind as the user to verify password
            user_conn = Connection(
                server,
                user=user_dn,
                password=password,
                auto_bind=True,
            )
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
