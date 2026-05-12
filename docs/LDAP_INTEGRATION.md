# LDAP/Active Directory Integration Guide

Enable optional LDAP/AD authentication while maintaining local user fallback.

## Overview

- **Local Auth**: Always available as fallback
- **LDAP Auth**: Optional, attempted first if enabled
- **Hybrid**: Users can authenticate via LDAP OR local credentials
- **Group Mapping**: LDAP groups → Application roles

## Installation

### 1. Install LDAP Library

```bash
pip install ldap3
```

(Optional dependency - app works without it)

### 2. Configuration

Set environment variables to enable LDAP:

```bash
# Enable LDAP authentication
export LDAP_ENABLED=true

# LDAP Server URI
export LDAP_SERVER_URI="ldap://ldap.example.com:389"
# Or for AD with TLS:
# export LDAP_SERVER_URI="ldaps://ad.example.com:636"

# Service account (read-only)
export LDAP_BIND_DN="cn=admin,dc=example,dc=com"
export LDAP_BIND_PASSWORD="service-password"

# Base DN for user search
export LDAP_USER_BASE_DN="ou=users,dc=example,dc=com"

# (Optional) Custom search filter
# export LDAP_USER_SEARCH_FILTER="(|(uid={username})(mail={username}))"

# (Optional) Timeout in seconds
# export LDAP_TIMEOUT="10"
```

## Group to Role Mapping

Map LDAP groups to application roles:

```bash
export LDAP_GROUP_MAPPING='{
  "cn=admins,ou=groups,dc=example,dc=com": "admin",
  "cn=editors,ou=groups,dc=example,dc=com": "cra_editor",
  "cn=viewers,ou=groups,dc=example,dc=com": "cra_viewer"
}'
```

**Format**: JSON with LDAP group DN or name → app role

**Default role** (if no group mapping matches): `cra_viewer`

## Authentication Flow

### With LDAP Enabled

```
User logs in (email + password)
    ↓
1. Try LDAP authentication
   - Search for user in LDAP
   - Verify password via LDAP bind
   - Extract groups and map to roles
   ↓
2. If LDAP fails, try local authentication
   - Check MOCK_USERS
   - Verify password hash
   ↓
3. If both fail, return 401 Unauthorized
    ↓
Generate JWT token with:
- User info (email, groups)
- Application roles
- Permissions based on roles
```

### Without LDAP (Default)

```
User logs in (email + password)
    ↓
Try local authentication only
    ↓
Return JWT token or 401
```

## Common LDAP Configurations

### OpenLDAP

```bash
export LDAP_ENABLED=true
export LDAP_SERVER_URI="ldap://ldap.example.com:389"
export LDAP_BIND_DN="cn=admin,dc=example,dc=com"
export LDAP_BIND_PASSWORD="admin-password"
export LDAP_USER_BASE_DN="ou=users,dc=example,dc=com"
export LDAP_USER_SEARCH_FILTER="(uid={username})"
```

### Active Directory

```bash
export LDAP_ENABLED=true
export LDAP_SERVER_URI="ldaps://ad.example.com:636"
export LDAP_BIND_DN="CN=Service Account,CN=Users,DC=company,DC=com"
export LDAP_BIND_PASSWORD="service-password"
export LDAP_USER_BASE_DN="CN=Users,DC=company,DC=com"
export LDAP_USER_SEARCH_FILTER="(|(sAMAccountName={username})(mail={username}))"
```

### Azure AD (via LDAP Proxy)

```bash
# Requires Azure AD Connect or similar LDAP proxy
export LDAP_ENABLED=true
export LDAP_SERVER_URI="ldap://aad-proxy.example.com:389"
export LDAP_BIND_DN="CN=Service Account,DC=sync,DC=example,DC=com"
export LDAP_BIND_PASSWORD="sync-password"
export LDAP_USER_BASE_DN="CN=Users,DC=company,DC=onmicrosoft,DC=com"
```

## Testing LDAP

### Test Connection

```python
from server.auth import get_ldap_authenticator

ldap = get_ldap_authenticator()
if ldap:
    success = ldap.test_connection()
    print("LDAP connection:", "✓ OK" if success else "✗ FAILED")
else:
    print("LDAP not configured")
```

### Test Authentication

```bash
# Via curl
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "john.doe@example.com", "password": "ldap-password"}'
```

### Debugging

Enable debug logging:

```python
import logging
logging.getLogger('ldap3').setLevel(logging.DEBUG)
```

## Troubleshooting

### "LDAP connection failed"

- Check LDAP_SERVER_URI is correct
- Verify LDAP_BIND_DN and LDAP_BIND_PASSWORD are valid
- Check firewall allows LDAP port (389 or 636)
- Check SSL/TLS if using ldaps://

### "LDAP user not found"

- Verify LDAP_USER_BASE_DN contains user
- Check LDAP_USER_SEARCH_FILTER matches your schema
- Test with ldapsearch: `ldapsearch -H ldap://server -x -b "ou=users,dc=example,dc=com" uid=john`

### "No group mapping found"

- LDAP_GROUP_MAPPING is optional
- Without mapping, users get default role: `cra_viewer`
- Check group DN/names in LDAP_GROUP_MAPPING

### "Authentication timeout"

- Increase LDAP_TIMEOUT (default: 10 seconds)
- Check network connectivity to LDAP server
- Check LDAP server is not overloaded

## Security Considerations

### Service Account

- Use **read-only** service account for LDAP bind
- Never use admin or user credentials
- Store password securely (env var, vault, etc.)
- Rotate password regularly

### TLS/SSL

- Use `ldaps://` (port 636) for production
- Verify LDAP server certificate
- Use strong ciphers

### Rate Limiting

- Rate limiting applies to login attempts (5 per 5 min per IP)
- Applies to both LDAP and local auth
- After 5 failed attempts, user is locked out for 5 minutes

## Hybrid Authentication Best Practices

### Keep Local Accounts

- Always maintain local admin account for:
  - Emergency access if LDAP is down
  - Testing
  - Service accounts

### Fallback to Local

- If LDAP fails, try local auth automatically
- Users can use either LDAP or local credentials
- Passwords never shared with LDAP

### Monitor Both

- Log failed LDAP and local auth attempts
- Alert on repeated failures
- Monitor LDAP server health

## Advanced Configuration

### Custom User Attribute Mapping

(Future enhancement) Map LDAP attributes to user profile:

```
LDAP Field          → App Field
cn / displayName    → name
mail                → email
uid / sAMAccountName → username
telephoneNumber     → phone
```

### Dynamic Role Assignment

(Future enhancement) Derive roles from:

- LDAP group membership
- LDAP user attributes
- Custom LDAP queries

### SSO/Session Management

(Future enhancement)

- Single Sign-On with LDAP
- Session management with LDAP token binding
- Multi-factor authentication (LDAP MFA)

## API Responses

### Successful LDAP Login

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": "john.doe@example.com",
    "email": "john.doe@example.com",
    "roles": ["cra_editor"],
    "permissions": ["cra:read", "cra:write"]
  }
}
```

### Successful Local Login

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": "user-001",
    "email": "admin@example.com",
    "roles": ["admin"],
    "permissions": ["cra:read", "cra:write", "admin:*"]
  }
}
```

### Failed Authentication

```json
{
  "error": "Invalid email or password"
}
```

(Same response for both LDAP and local failures for security)

## References

- [ldap3 Documentation](https://ldap3.readthedocs.io/)
- [LDAP Security Best Practices](https://owasp.org/www-community/attacks/LDAP_Injection)
- [RFC 4511 - LDAP Protocol](https://tools.ietf.org/html/rfc4511)
