"""Authentication & Authorization Module.

Supports:
- Local user authentication
- LDAP/Active Directory (optional)
- JWT token management
- Role-based access control (RBAC)
"""

from server.auth.ldap import get_ldap_authenticator, LDAPConfig

__all__ = ['get_ldap_authenticator', 'LDAPConfig']
