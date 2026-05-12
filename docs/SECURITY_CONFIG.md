# Security Configuration Guide

## Required Environment Variables

### 1. JWT Secret Key (CRITICAL)

**Generate a 32-byte random key:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**Set environment variable:**
```bash
export JWT_SECRET_KEY="<your-generated-key>"
```

**Validation:**
- Minimum 32 bytes (64 hex characters)
- Must be set before app startup
- App will fail to start without this

### 2. CORS Origins (CRITICAL)

**Configure trusted origins (comma-separated):**
```bash
export CORS_ORIGINS="https://yourdomain.com,https://app.yourdomain.com"
```

**Default (development only):**
```
http://localhost:5173,http://localhost:3000
```

**⚠️ Production:** Never use `*` or localhost URLs in production.

### 3. JWT Token Expiration (OPTIONAL)

**Set token lifetime in hours:**
```bash
export JWT_EXPIRES_HOURS="24"  # Default: 24 hours
```

## Security Features Implemented

### Authentication
- ✅ JWT-based authentication (HS256)
- ✅ Password hashing (Werkzeug PBKDF2)
- ✅ Email validation (regex)
- ✅ Minimum password length enforcement (8 chars)
- ✅ Rate limiting (5 login attempts per 5 minutes per IP)

### Network Security
- ✅ CORS restricted to configured origins
- ✅ Security headers (CSP, X-Frame-Options, HSTS, etc.)
- ✅ No demo credentials endpoint (removed)

### Data Protection
- ✅ Secure database file permissions (0600)
- ✅ Multi-database isolation
- ✅ Transaction rollback on errors
- ⏳ Token blacklist on logout (Issue #266)
- ⏳ HTTPS/TLS enforcement (Issue #269)

## Deployment Checklist

### Before Production

- [ ] Generate strong JWT_SECRET_KEY
- [ ] Configure CORS_ORIGINS for your domain
- [ ] Set up HTTPS with valid TLS certificates
- [ ] Enable database backups
- [ ] Configure rate limiting for production (currently 5/5min)
- [ ] Set up monitoring/alerting
- [ ] Rotate JWT_SECRET_KEY periodically
- [ ] Implement token blacklist (Redis recommended)

### Development Setup

```bash
# 1. Generate development JWT secret
export JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

# 2. Default CORS is already set for dev
# export CORS_ORIGINS="http://localhost:5173,http://localhost:3000"

# 3. Start backend
python run_dev.py

# 4. Start frontend
cd frontend && npm run dev
```

### Docker Production

```bash
# Set environment before docker-compose
export JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export CORS_ORIGINS="https://yourdomain.com"

# Build and run
docker-compose up --build
```

## Known Limitations & TODO

### High Priority
- **Token Blacklist on Logout** (Issue #266)
  - Currently logout doesn't invalidate tokens
  - Implement Redis-based blacklist
  - Check blacklist on @jwt_required() requests

- **HTTPS/TLS Enforcement** (Issue #269)
  - Add HTTPS to Dockerfile/nginx
  - Auto-generate self-signed certs for dev
  - Force HTTPS redirect

### Medium Priority
- **Frontend Token Storage** (Issue #268)
  - Move from localStorage to httpOnly cookie
  - Requires backend support for Set-Cookie

### Low Priority
- Account lockout mechanism (after N failed attempts)
- Two-factor authentication (2FA)
- API key authentication for service-to-service
- OAuth2/OIDC integration

## Security Headers Reference

The application sets these headers on every response:

```
X-Content-Type-Options: nosniff
  → Prevents MIME-type sniffing attacks

X-Frame-Options: DENY
  → Prevents clickjacking attacks

X-XSS-Protection: 1; mode=block
  → Enables XSS protection in older browsers

Strict-Transport-Security: max-age=31536000; includeSubDomains
  → Forces HTTPS for 1 year (requires valid TLS)

Content-Security-Policy: default-src 'self'; ...
  → Restricts script/style/resource loading
```

## Testing Security

### Test Rate Limiting
```bash
# Try logging in 6 times rapidly (should fail on 6th)
for i in {1..6}; do
  curl -X POST http://localhost:5000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "admin@example.com", "password": "wrong"}'
  echo "Attempt $i"
done
```

### Test Input Validation
```bash
# Test invalid email
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "not-an-email", "password": "test"}'

# Test short password
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "short"}'
```

### Test CORS
```bash
# Should fail from different origin
curl -X OPTIONS http://localhost:5000/api/auth/login \
  -H "Origin: https://attacker.com"
```

## References

- [OWASP Top 10 - Authentication](https://owasp.org/Top10/A07_2021-Identification_and_Authentication_Failures/)
- [OWASP Top 10 - Injection](https://owasp.org/Top10/A03_2021-Injection/)
- [Flask Security Best Practices](https://flask.palletsprojects.com/security/)
- [JWT Security](https://tools.ietf.org/html/rfc8949)
