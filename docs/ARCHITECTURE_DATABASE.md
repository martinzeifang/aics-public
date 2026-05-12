# Database Architecture: Multi-DB Isolation Strategy

**Document:** ARCHITECTURE_DATABASE.md  
**Version:** 1.0  
**Date:** 2026-05-08  
**Author:** ai-compliance-engineer Agent  

---

## Overview

Die AI Compliance Suite Web-Variante nutzt **mehrere SQLite-Datenbanken**, um Datensilos klar zu trennen:

| Datenbank | Dateiname | Inhalt | Beispiel-Größe |
|-----------|-----------|--------|-----------------|
| **users** | `data/db/users.sqlite` | User, Rollen, Permissions, API-Keys | ~100KB |
| **cra** | `data/db/cra.sqlite` | CRA-Daten, Kontrollen, Bewertungen | ~5MB |
| **audit** | `data/db/audit.sqlite` | Audit-Logs, HTTP-Requests, Änderungen | ~10MB/Monat |

**Ziel:** Datensilos trennen, Skalierbarkeit ermöglichen, Sicherheit erhöhen

---

## Architecture

### 1. DbManager Pattern

```python
from server.config.database import DbManager, get_db_manager, transaction

# Option A: DbManager direkt
manager = get_db_manager('users')
session = manager.session()

# Option B: Context-Manager (empfohlen)
with transaction('users') as session:
    user = session.query(User).first()
    user.email = 'new@example.com'
    # Auto-commit bei Success, Auto-rollback bei Exception
```

### 2. Session Management

```python
from server.db.session import managed_session

# ManagedSession mit zusätzlichen Features
with managed_session('cra') as session:
    control = session.query(Control).get(control_id)
    control.status = 'reviewed'
    # Auto-commit
```

### 3. Connection Pooling

Jede Datenbank hat einen separaten Connection-Pool:

```
DbManager('users')
  ↓
  SQLAlchemy Engine (pool_size=10, max_overflow=5)
    ↓
    SQLite Connection Pool (max 10+5 connections)
```

**Konfiguration:**
- `pool_size=10` — Max idle connections im Pool
- `max_overflow=5` — Zusätzliche Connections wenn Pool voll
- `pool_pre_ping=True` — Verbindungen vor Nutzung prüfen
- `timeout=30` — Warten auf DB-Lock (Sekunden)

---

## Usage Patterns

### Pattern 1: Simple Query

```python
from server.config.database import get_db_manager

manager = get_db_manager('cra')
session = manager.session()
try:
    controls = session.query(Control).all()
    print(f"Found {len(controls)} controls")
finally:
    session.close()
```

### Pattern 2: Transactional Write (mit Auto-Commit)

```python
from server.config.database import transaction

with transaction('users') as session:
    user = session.query(User).get(user_id)
    user.last_login = datetime.now()
    # Auto-commit when exiting context
```

### Pattern 3: Multi-Database Transaction

```python
from server.config.database import transaction

# Erste DB: users
with transaction('users') as users_session:
    user = users_session.query(User).get(user_id)

    # Zweite DB: audit
    with transaction('audit') as audit_session:
        log = AuditLog(
            user_id=user.id,
            action='cra.control.updated',
            timestamp=datetime.now()
        )
        audit_session.add(log)
        # Beide werden committed bei Success,
        # beide gerollt back bei Exception
```

### Pattern 4: Managed Session mit Debugging

```python
from server.db.session import managed_session

with managed_session('cra') as session:
    # session hat zusätzliche Features
    session.flush()  # Flush ohne Commit
    session.refresh(obj)  # Refresh vom DB
```

---

## Error Handling

### Scenario 1: Constraint Violation

```python
from sqlalchemy.exc import IntegrityError
from server.config.database import transaction

try:
    with transaction('users') as session:
        user = User(email='duplicate@example.com')
        session.add(user)  # Wirft IntegrityError bei Duplicate
except IntegrityError:
    print("Email already exists")
    # Session wird auto-rolled back
```

### Scenario 2: Connection Timeout

```python
from sqlalchemy.exc import OperationalError
from server.config.database import get_db_manager

manager = get_db_manager('cra')
try:
    with manager.transaction() as session:
        result = session.execute("SELECT * FROM controls")
except OperationalError as e:
    print(f"Database connection failed: {e}")
    # Session wird auto-rolled back
```

### Scenario 3: Health Check

```python
from server.config.database import get_db_manager

manager = get_db_manager('users')
if manager.health_check():
    print("✓ Users DB OK")
else:
    print("✗ Users DB FAIL")
```

---

## Migration Strategy (Alembic)

### Separate Alembic Directories

```
alembic/
├── users/
│   ├── versions/
│   │   ├── 001_create_user_table.py
│   │   └── 002_add_email_index.py
│   └── alembic.ini
│
├── cra/
│   ├── versions/
│   │   ├── 001_create_control_table.py
│   │   └── ...
│   └── alembic.ini
│
└── audit/
    ├── versions/
    │   ├── 001_create_audit_log_table.py
    │   └── ...
    └── alembic.ini
```

### Migration Execution

```bash
# Migrate all databases
alembic -c alembic/users/alembic.ini upgrade head
alembic -c alembic/cra/alembic.ini upgrade head
alembic -c alembic/audit/alembic.ini upgrade head

# Or: Custom script
python migrate_databases.py
```

---

## Backup & Restore

### Backup-Strategie

```bash
# Tägliche Backups
mysqldump -u root -p compliance > backups/cra_$(date +%Y%m%d).sql
cp data/db/users.sqlite backups/users_$(date +%Y%m%d).sqlite
cp data/db/audit.sqlite backups/audit_$(date +%Y%m%d).sqlite
```

### Restore

```bash
# Restore aus Backup
cp backups/users_20260508.sqlite data/db/users.sqlite
```

---

## Performance Considerations

### Connection Pool Sizing

```python
# Für Single-Server (kleine Deployments)
pool_size=5,      # 5 idle connections
max_overflow=2,   # +2 additional if needed
timeout=15,       # 15s wait for lock

# Für Multi-Worker (large deployments)
pool_size=10,     # 10 idle connections
max_overflow=5,   # +5 additional
timeout=30,       # 30s wait for lock
```

### Query Optimization

```python
# ❌ N+1 Problem
users = session.query(User).all()
for user in users:
    print(user.roles)  # Extra query pro user

# ✅ Eager Loading
users = session.query(User).options(
    joinedload(User.roles)
).all()
for user in users:
    print(user.roles)  # Kein extra query
```

---

## Testing

### Unit Tests

```python
def test_transaction_commit():
    """Test: Transaktionen werden committed."""
    with transaction('users') as session:
        user = User(email='test@example.com')
        session.add(user)
    
    # Verify commit
    with transaction('users') as session:
        found = session.query(User).filter_by(
            email='test@example.com'
        ).first()
        assert found is not None
```

### Integration Tests

```python
def test_multi_database_transaction():
    """Test: Multi-DB Transaktionen."""
    with transaction('users') as users_session:
        user = User(email='test@example.com')
        users_session.add(user)
        
        with transaction('audit') as audit_session:
            log = AuditLog(action='user.created')
            audit_session.add(log)
    
    # Verify both DBs
    # ...
```

---

## Migration from SQLite to PostgreSQL

Für Production-Deployments kann später auf PostgreSQL migriert werden:

```python
# Aktuell: SQLite
db_uri = f"sqlite:///{db_path}"

# Zukünftig: PostgreSQL
db_uri = f"postgresql://user:pass@localhost/cra"

# Code bleibt gleich (SQLAlchemy abstrahiert)
```

---

## Related Docs

- [Phase-6 Production-Ready Plan](plans/PHASE-6-PRODUCTION-READY.md) — Roadmap
- [SPEC #253](https://github.com/martinzeifang/AI_Compliance_Suite/issues/253) — DB-Isolation-Spec
- `server/config/database.py` — Implementierung
- `server/db/session.py` — Session-Management

---

**Status:** ✅ SPEC-253 dokumentiert  
**Next:** Alembic-Setup für Migrationen
