# Deployment-Guide — AI Compliance Suite

## Voraussetzungen

- Docker 24+
- Docker Compose v2
- Server mit min. 2 GB RAM, 10 GB freiem Speicherplatz
- (Optional) Eigene HTTPS-Zertifikate (sonst werden Self-Signed Certs erzeugt)

## Schnellstart

### 1. Repository klonen

```bash
git clone https://github.com/martinzeifang/AI_Compliance_Suite.git
cd AI_Compliance_Suite
```

### 2. Environment-Datei anlegen

```bash
cp .env.example .env

# JWT-Secret generieren
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_hex(32))" >> .env

# CORS-Origins anpassen (eigene Domain!)
nano .env  # oder vi/code
```

**Pflicht-Variablen:**
- `JWT_SECRET_KEY` — min. 32 Zeichen, generieren mit Python-Befehl oben
- `CORS_ORIGINS` — komma-separierte Liste deiner echten Domains

### 3. HTTPS-Zertifikate

**Option A — Self-Signed (für Dev/Intern):**

Werden automatisch beim ersten Start im Container generiert.

**Option B — Eigene Zertifikate:**

```bash
mkdir -p certs
cp /pfad/zu/server.crt certs/server.crt
cp /pfad/zu/server.key certs/server.key
chmod 600 certs/server.key
```

### 4. Starten

```bash
docker compose up -d
```

Log-Ausgabe verfolgen:
```bash
docker compose logs -f
```

### 5. Erste Anmeldung

- Frontend: `https://<dein-server>` (Port 443)
- Backend-Health: `https://<dein-server>/health`

**Admin-User anlegen** (nicht Demo):

```bash
docker compose exec web python3 -c "
from server.auth.users_db import create_user
create_user(email='admin@deine-firma.com', password='SicheresPasswort123', roles=['admin'])
print('Admin-User created.')
"
```

## Update / Upgrade

### Standardweg (Pull aus GitHub Container Registry)

`docker-compose.yml` zieht standardmäßig ein vorgebautes Image aus
`ghcr.io/martinzeifang/ai_compliance_suite`. Bei jedem Push auf `main`
oder beim Setzen eines `v*`-Tags baut GitHub Actions automatisch ein
neues Image (Workflow: `.github/workflows/docker-publish.yml`).

**Update auf dem Server:**

```bash
./scripts/update.sh           # mit automatischem DB-Backup vor Update
./scripts/update.sh --no-backup
```

Das Skript:
1. Erstellt ein Backup der DB-Volumes (`backups/aics_data_YYYY-MM-DD.tar.gz`)
2. Zieht das neueste Image: `docker compose pull`
3. Wechselt die Container: `docker compose up -d` (Daten in Named Volumes bleiben)
4. Health-Check + alte Images aufräumen

**Manuell:**
```bash
docker compose pull
docker compose up -d
```

**Auf eine bestimmte Version pinnen:**
```bash
# .env oder vorher exportieren
export AICS_IMAGE_TAG=v1.2.3       # Tag
# oder
export AICS_IMAGE_TAG=sha-abc1234   # Git-SHA
# oder
export AICS_IMAGE_TAG=main          # immer neuester main

docker compose pull && docker compose up -d
```

Verfügbare Tags pro Build:
- `latest` (nur main-pushes)
- `main`
- `v1.2.3`, `1.2`
- `sha-abc1234` (immer)

### Lokal bauen (Eigene Forks / Entwicklung)

Wenn du eigene Änderungen ohne Push einspielen willst:

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build
```

### Rollback

```bash
AICS_IMAGE_TAG=sha-<vorher> docker compose up -d
```

Falls Daten beschädigt sind:
```bash
docker run --rm -v aics_data:/data -v $(pwd)/backups:/backup alpine \
  sh -c 'rm -rf /data/* && tar xzf /backup/aics_data_2026-05-11_14-00.tar.gz -C /data'
docker compose restart web
```

## Backup

Manuell:
```bash
docker compose exec web python3 -c "
from pathlib import Path
import shutil, datetime, zipfile
backup = Path('/app/out/backup') / f'backup_{datetime.datetime.now().strftime(\"%Y%m%d_%H%M%S\")}.zip'
with zipfile.ZipFile(backup, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in Path('/app/data/db').glob('*.sqlite'):
        z.write(f, f'db/{f.name}')
print(f'Backup: {backup}')
"
```

Oder über die Web-UI: User-Menü → Administration → Backup-Verwaltung.

## Monitoring

- **Health-Check**: `https://<server>/health` (sollte 200 OK liefern)
- **Logs**: `docker compose logs web` und `docker compose logs nginx`
- **Audit-Log**: User-Menü → Administration → Audit-Log
- **Backup-Liste**: User-Menü → Administration → Backup-Verwaltung

## Troubleshooting

### Web-Container startet nicht

```bash
docker compose logs web
```

Häufige Ursachen:
- `JWT_SECRET_KEY` zu kurz (< 32 Zeichen)
- Datei-Permissions in `data/` falsch
- Port 5000 bereits belegt

### Nginx-502-Bad-Gateway

Backend nicht erreichbar:
```bash
docker compose ps
docker compose exec web curl -fs http://localhost:5000/health
```

### "Token has been revoked" nach Login

Browser-Cache leeren (F5 + Hard-Refresh `Ctrl+Shift+R`).

## Sicherheits-Hardening (Phase 6 abgeschlossen)

✅ **JWT**:
- ENV-Pflicht (≥32 Zeichen)
- Token-Blacklist via `revoked_tokens`-Tabelle
- HSTS-Header gesetzt

✅ **CORS**: Whitelist via `CORS_ORIGINS`

✅ **Frontend**: Token in `sessionStorage` (nicht `localStorage`)

✅ **Rate-Limiting**: Flask-Limiter (1000/h, 100/min global, 20/min Login)

✅ **Dependencies**: Alle CVE-relevanten Pakete auf Mindest-Versionen gepinnt

✅ **HTTPS**: Nginx terminiert TLS 1.2/1.3, HTTP→HTTPS Redirect

## Architektur

```
┌─────────────────────────────────────────┐
│            Browser (HTTPS)              │
└────────────────┬────────────────────────┘
                 │
         ┌───────▼────────┐
         │ Nginx (443)    │
         │ - TLS-Term.    │
         │ - Static Files │
         │ - /api → Web   │
         └───────┬────────┘
                 │ HTTP (intern)
         ┌───────▼────────┐
         │ Web (5000)     │
         │ - Flask App    │
         │ - Gunicorn 4w  │
         └───────┬────────┘
                 │
    ┌────────────┼─────────────────┐
    │            │                 │
┌───▼───┐   ┌────▼──────┐   ┌──────▼───────┐
│ DBs   │   │ Logs/Audit│   │ Backups (ZIP)│
│ SQLite│   │           │   │              │
└───────┘   └───────────┘   └──────────────┘
```

## Weiterführende Dokumentation

- API-Referenz (OpenAPI): `/api/docs/swagger.json` (TODO)
- Architektur-Details: `docs/ARCHITECTURE.md` (TODO)
- Sicherheits-Konzept: `docs/SECURITY.md` (TODO)
