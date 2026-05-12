# AI Compliance Suite Web - Quick Start

## Development Setup

### Backend
```bash
# Install dependencies
pip install -r requirements.txt

# Start dev server
python run_dev.py
# http://localhost:5000
```

### Frontend
```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
# http://localhost:5173 (proxies to localhost:5000/api)
```

### Demo Credentials
- **Admin**: admin@example.com / admin-password
- **Editor**: editor@example.com / editor-password

## Features (Phase-0 → Phase-4)

✅ **Phase-0**: Specifications & Refactoring
- API-Contract (OpenAPI)
- DB-Isolation (Multi-DB)
- prefill/ Refactoring
- Audit Logging
- Frontend Build-Pipeline
- RBAC Matrix

✅ **Phase-1**: Foundation + Auth
- Flask App-Factory
- JWT Authentication
- Role-based Access Control
- Vue.js 3 + Pinia
- Router with Auth Guards

✅ **Phase-2**: CRA API + Frontend
- Dashboard with Statistics
- OWASP Controls Management
- Requirements Tree-View
- Permission-based UI

✅ **Phase-3**: Docker & Deployment
- Dockerfile (Multi-Stage)
- docker-compose.yml
- Nginx Reverse Proxy
- Gunicorn + Health Checks

✅ **Phase-4+**: Testing & Features (In Progress)
- E2E Tests
- Integration Tests
- OpenAPI Documentation
- Dark Mode (Planned)
- i18n Support (Planned)

## API Endpoints

### Authentication
- `POST /api/auth/login` — Login with email/password
- `GET /api/auth/profile` — Current user profile
- `POST /api/auth/logout` — Logout
- `POST /api/auth/refresh` — Refresh token

### CRA Module
- `GET /api/cra/dashboard` — Dashboard statistics
- `GET /api/cra/chapters` — List chapters
- `GET /api/cra/chapters/{id}` — Chapter details
- `GET /api/cra/controls` — List OWASP controls
- `POST /api/cra/controls/{id}` — Update control

## Architecture

```
server/
├── app.py                 # Flask App-Factory
├── api/
│   ├── auth.py          # Authentication
│   ├── cra/             # CRA Module
│   └── docs.py          # OpenAPI
├── config/
│   └── database.py      # Multi-DB Management
├── db/
│   └── session.py       # Transaction Manager
├── middleware/
│   └── audit.py         # Audit Logging
└── models/
    └── permission.py    # RBAC

frontend/
├── src/
│   ├── main.ts          # Entry Point
│   ├── router/          # Vue Router
│   ├── stores/          # Pinia (Auth)
│   ├── views/           # Pages
│   └── components/      # Reusable Components
└── vite.config.ts       # Build Config
```

## Deployment

```bash
# Production Build
docker-compose up --build

# Environment Variables
export JWT_SECRET_KEY="your-secret-key-here"

# Access
- API: http://localhost:5000
- Web: http://localhost
- Nginx: Port 80 (proxies to Flask)
```

## Testing

```bash
# Unit Tests
pytest tests/

# E2E Tests (Playwright/Cypress)
npm run test:e2e

# Integration Tests
pytest tests/test_api_integration.py
```

## Next Steps

1. [ ] Implement Database Models (SQLAlchemy)
2. [ ] Add E2E Tests (Playwright)
3. [ ] Implement Dark Mode
4. [ ] Add i18n Support
5. [ ] Performance Optimization
6. [ ] Security Hardening
7. [ ] Production Deployment

## License

AI Compliance Suite - Compliance Management Platform
