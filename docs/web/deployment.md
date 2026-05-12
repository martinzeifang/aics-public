# Docker-Deployment (Web-Anwendung)

Diese Anleitung beschreibt das vollständige Setup der **Web-Variante** der
AI Compliance Suite über Docker. Sie deckt Erstinstallation, Updates,
Backups und Troubleshooting ab.

!!! info "Architektur in 30 Sekunden"
    - **`aics_web`**: Flask + Gunicorn (Backend, intern HTTP auf Port 5000)
    - **`aics_nginx`**: Reverse-Proxy mit HTTPS-Termination (Ports 8443/8082)
    - **Named Volumes**: `aics_data`, `aics_logs`, `aics_backups`,
      `aics_certs`, `aics_frontend` (persistent über Updates)
    - **Image-Quelle**: `ghcr.io/martinzeifang/ai_compliance_suite:latest`
      (privates GitHub-Container-Registry, gebaut bei jedem push auf `main`)

---

## 1. Voraussetzungen

| Komponente   | Mindest-Version | Hinweis |
|---|---|---|
| Linux        | Ubuntu 20.04+ / Debian 11+ / RHEL 9 | systemd empfohlen |
| Docker       | 24.0+           | `docker --version` |
| Docker-Compose | v2 (Plugin)   | `docker compose version` (nicht `docker-compose`) |
| Festplatte   | ≥ 10 GB frei    | für Image + Volumes (Backups wachsen) |
| RAM          | ≥ 2 GB          | 4 GB empfohlen wenn KI-Module aktiv |
| Ports        | 8082, 8443 frei | konfigurierbar in `.env` |
| Netzwerk     | Outbound zu     | `ghcr.io`, `pypi.org` (für Image-Pull) |

**User-Setup:** Der Deploy-User muss in der `docker`-Gruppe sein:

```bash
sudo usermod -aG docker $USER
newgrp docker   # oder neu einloggen
```

---

## 2. GitHub Container Registry — Zugriff einrichten

Das Image liegt in einem **privaten** GHCR-Repo. Der Server braucht
einen **Personal Access Token (PAT)** zum Pullen.

### 2.1 PAT erstellen

1. Auf [github.com/settings/tokens](https://github.com/settings/tokens) →
   **„Generate new token (classic)"**
2. Scopes: nur **`read:packages`** ankreuzen (kein Repo-Zugriff nötig)
3. Expiration: 90 Tage oder „No expiration" (deine Wahl)
4. Token wird **einmalig** angezeigt — sofort kopieren

!!! warning "Sicherheit"
    Der PAT ist quasi ein Passwort. Niemals in git committen, niemals
    im Klartext in Chats teilen, periodisch rotieren.

### 2.2 Docker bei GHCR anmelden

```bash
echo 'ghp_DEIN_PAT' | docker login ghcr.io \
  -u DEIN_GITHUB_USERNAME \
  --password-stdin
```

Erfolg: `Login Succeeded`. Credentials werden in `~/.docker/config.json`
gespeichert — der PAT wird ab jetzt automatisch verwendet.

---

## 3. Erstinstallation (Step-by-Step)

### 3.1 Deployment-Verzeichnis anlegen

```bash
sudo mkdir -p /opt/ai-compliance-suite
sudo chown $USER:$USER /opt/ai-compliance-suite
cd /opt/ai-compliance-suite
```

### 3.2 Konfigurationsdateien holen

Die Dateien werden mitversioniert im Repo — du brauchst sie auf dem Server:

```bash
# Sparse-Clone — nur die Deployment-Files
git clone --filter=blob:none --no-checkout \
  https://github.com/martinzeifang/AI_Compliance_Suite.git /tmp/aics-src
cd /tmp/aics-src
git sparse-checkout init --cone
git sparse-checkout set docker scripts docker-compose.yml docker-compose.build.yml
git checkout main

# Nach /opt/ kopieren
cp -r docker-compose.yml docker-compose.build.yml docker scripts /opt/ai-compliance-suite/
cd /opt/ai-compliance-suite
rm -rf /tmp/aics-src
```

Alternative (ohne git):

```bash
cd /opt/ai-compliance-suite
curl -L https://github.com/martinzeifang/AI_Compliance_Suite/archive/refs/heads/main.tar.gz | \
  tar xz --strip-components=1 \
  'AI_Compliance_Suite-main/docker-compose.yml' \
  'AI_Compliance_Suite-main/docker-compose.build.yml' \
  'AI_Compliance_Suite-main/docker' \
  'AI_Compliance_Suite-main/scripts'
chmod +x scripts/update.sh docker/entrypoint.sh
```

### 3.3 `.env`-Datei erstellen

```bash
cd /opt/ai-compliance-suite
cat > .env <<EOF
# ─── JWT (verpflichtend, ≥ 32 Zeichen) ────────────────────────────────
JWT_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
JWT_EXPIRES_HOURS=24

# ─── CORS (Whitelist der Browser-Origins) ─────────────────────────────
# Hier deinen Server-Hostnamen / IP eintragen. Komma-getrennt.
CORS_ORIGINS=https://aics.example.com:8443,https://compliance.example.com

# ─── Account-Sicherheit (Phase 6.2) ───────────────────────────────────
ACCOUNT_LOCKOUT_THRESHOLD=5      # Lockout nach n Fehlversuchen
ACCOUNT_LOCKOUT_SECONDS=900      # 15 Minuten
PASSWORD_MIN_LENGTH=12

# ─── Demo-Modus ───────────────────────────────────────────────────────
# true = admin@example.com / admin-password werden angelegt
# In PROD: false (eigenen Admin über Admin-API anlegen)
ENABLE_DEMO_USERS=true

# ─── Image-Pinning ────────────────────────────────────────────────────
# latest = jeweils neuester main-Build
# main = identisch
# v1.2.3 = Release-Tag
# sha-abc1234 = exakte Revision (empfohlen für Production)
AICS_IMAGE_TAG=latest

# ─── Nginx-Ports auf dem Host ─────────────────────────────────────────
# 80/443 wenn frei, sonst alternative Ports
AICS_HTTP_PORT=8082
AICS_HTTPS_PORT=8443

# ─── Gunicorn ─────────────────────────────────────────────────────────
GUNICORN_WORKERS=4

# ─── Optional: LDAP ──────────────────────────────────────────────────
LDAP_ENABLED=false
LDAP_SERVER=
LDAP_BASE_DN=
LDAP_BIND_DN=
LDAP_BIND_PASSWORD=
LDAP_GROUP_MAPPING={}

# ─── Optional: Cloud-KI ──────────────────────────────────────────────
AI_CLOUD_API_KEY=
EOF

chmod 600 .env
```

!!! danger ".env enthält Secrets"
    `chmod 600` ist wichtig — die Datei darf nur dem Owner lesbar sein.
    **Niemals committen!**

### 3.4 Image pullen + Stack starten

```bash
cd /opt/ai-compliance-suite

# Image von GHCR ziehen
docker compose pull

# Container starten (-d = detached)
docker compose up -d

# Status prüfen
docker compose ps
```

Erwartete Ausgabe:
```
NAME         IMAGE                                       STATUS              PORTS
aics_web     ghcr.io/martinzeifang/ai_compliance_suite   running (healthy)   5000/tcp
aics_nginx   nginx:1.27-alpine                            running             0.0.0.0:8082->80/tcp, 0.0.0.0:8443->443/tcp
```

### 3.5 Logs überprüfen

```bash
# Live folgen
docker compose logs -f web

# Letzte 50 Zeilen
docker compose logs --tail=50 web nginx

# Nur Errors
docker compose logs web | grep -E 'ERROR|Traceback'
```

### 3.6 Erster Login

Im Browser: **`https://<deine-server-ip>:8443`**

- Browser warnt vor dem Self-Signed-Cert (erwartet im Dev/Intranet)
- Login: `admin@example.com` / `admin-password` (Demo-Modus)

!!! warning "Sofort nach erstem Login"
    1. Admin → 👥 Benutzerverwaltung → **eigenen Admin anlegen**
       (Passwort ≥ 12 Zeichen, Rolle `admin`)
    2. In `.env`: `ENABLE_DEMO_USERS=false`
    3. `docker compose restart web`
    4. Demo-User `admin@example.com` deaktivieren (über UI oder `/api/admin/users/<id>/disable`)

---

## 4. Update-Workflow

Bei jedem Push auf `main` baut GitHub Actions automatisch ein neues Image.
Auf dem Server:

### 4.1 Standard-Update (mit Backup)

```bash
cd /opt/ai-compliance-suite
./scripts/update.sh
```

Das Skript macht **vier Schritte**:

1. **DB-Backup** → `backups/aics_data_YYYY-MM-DD_HH-MM.tar.gz`
2. `docker compose pull` → neues Image von GHCR
3. `docker compose up -d` → Container austauschen (Downtime ≈ 10 s)
4. Health-Check + alte Image-Layer aufräumen

### 4.2 Update ohne Backup

```bash
./scripts/update.sh --no-backup
```

Geht wenn du regelmäßig anders backupst (z.B. Admin-UI).

### 4.3 Update auf bestimmten Tag/Commit

```bash
# In .env die Zeile AICS_IMAGE_TAG anpassen, dann:
docker compose pull && docker compose up -d
```

| Tag-Format        | Beispiel       | Wann nutzen |
|---|---|---|
| `latest`          | (default)      | Dev/Test — automatisch auf neuestem Stand |
| `main`            | identisch      | wie `latest` |
| `v1.2.3`          | bei Release-Tags | Production — bei Release-Workflow |
| `sha-abc1234`     | jeder Commit   | **Empfohlen Production** — exakt reproduzierbar |

### 4.4 Rollback auf vorherige Version

```bash
# Letztes funktionierendes Image war z.B. sha-deadbee
AICS_IMAGE_TAG=sha-deadbee docker compose up -d
```

Falls Daten beschädigt → DB aus Backup:

```bash
docker run --rm \
  -v aics_data:/data \
  -v $(pwd)/backups:/backup:ro \
  alpine sh -c 'rm -rf /data/* && tar xzf /backup/aics_data_2026-05-11_14-00.tar.gz -C /data'

docker compose restart web
```

---

## 5. Backups

### 5.1 Über die Web-UI

**Admin (🛡️) → 💾 Backup-Verwaltung**

| Aktion | Wirkung |
|---|---|
| **+ Neues Backup erstellen** | ZIP aller SQLite-DBs + `*.config.json` in `aics_backups` |
| **⬆️ Backup hochladen** | externes ZIP (z.B. von anderem Server) einspielen |
| **Wiederherstellen** | Restore mit automatischem Pre-Restore-Safety-Backup |
| **Löschen** | Backup-Datei entfernen |

### 5.2 Per CLI

```bash
# Backup erstellen (DB-Volume → Host-Tarball)
docker run --rm \
  -v aics_data:/data:ro \
  -v $(pwd)/backups:/backup \
  alpine tar czf "/backup/manual_$(date +%F_%H-%M).tar.gz" -C /data .

# Wiederherstellen (Service stoppen, Volume leeren, Tarball entpacken)
docker compose stop web
docker run --rm \
  -v aics_data:/data \
  -v $(pwd)/backups:/backup:ro \
  alpine sh -c 'rm -rf /data/* && tar xzf /backup/manual_2026-05-11.tar.gz -C /data'
docker compose start web
```

### 5.3 Backup-Inhalt

Ein Backup-ZIP enthält:

```
data/db/
  users.sqlite         ← Konten, Rollen, Lockout-Status
  cra.sqlite           ← CRA-Projekte + Bewertungen + OWASP
  dsgvo.sqlite         ← DSGVO + TOM-Drafts + Privacy-Intake
  nis2.sqlite          ← NIS2-Projekte
  dora.sqlite          ← DORA + TPP + Resilience-Tests
  ai_act.sqlite        ← AI Act
  gutachten.sqlite     ← Audit-Fragen + Drafts + Sections
  risikobewertung.sqlite
  kunden.sqlite        ← Kundenstamm
  evidence.sqlite      ← Hochgeladene Evidence-PDFs + Chunks
  audit.sqlite         ← Audit-Log
ai_compliance_suite.config.json   ← UI-Einstellungen
MANIFEST.json                      ← Backup-Metadaten
```

---

## 6. Logs

| Datei                 | Inhalt | Aufruf |
|---|---|---|
| `logs/app.log`        | Flask Application-Log + Tracebacks | `docker compose exec web tail -f /app/logs/app.log` |
| `logs/audit.log`      | JSON-Lines pro HTTP-Request        | `docker compose exec web tail -f /app/logs/audit.log` |
| `docker compose logs` | Stdout/Stderr der Container        | `docker compose logs -f web` |

### Logs vom Host exportieren

```bash
docker cp aics_web:/app/logs/app.log ./local_app.log
```

---

## 7. Troubleshooting

### 7.1 `docker compose pull` schlägt fehl

```
Error response from daemon: Head "https://ghcr.io/v2/martinzeifang/...":
denied: denied
```

→ Nicht (mehr) bei GHCR eingeloggt. Erneut:

```bash
echo 'ghp_NEUER_PAT' | docker login ghcr.io -u <user> --password-stdin
```

PAT abgelaufen? Neuen in [github.com/settings/tokens](https://github.com/settings/tokens) erstellen.

### 7.2 Container restartet permanent

```bash
docker compose logs --tail=80 web
```

Häufige Ursachen:

| Fehler im Log | Ursache | Fix |
|---|---|---|
| `JWT_SECRET_KEY environment variable is required` | `.env` fehlt/leer | `.env` prüfen, `docker compose up -d` |
| `Permission denied: 'ai_compliance_suite.config.json.tmp'` | Container-WORKDIR root-owned | siehe `AICS_CONFIG_PATH` in compose.yml |
| `ModuleNotFoundError: No module named 'X'` | falsches Image | `docker compose pull` → neues Image |

### 7.3 „Keine Verbindung" im Footer

- Backend gesund? `curl -k https://<server>:8443/api/health`
- Nginx-Cert? `docker compose logs nginx | grep -i cert`
- Volume `aics_certs` leer? Neu erstellen:

```bash
docker compose down
docker volume rm <projectdir>_aics_certs
docker compose up -d
```

Der `aics_web`-Entrypoint generiert dann ein Self-Signed-Cert.

### 7.4 Login nach Backup-Restore „Zugangsdaten falsch"

Behoben in `d3880a9` — Server muss auf neuestes Image laufen
(`./scripts/update.sh`).

Manuelle Reparatur falls noch alte Daten:

```bash
docker compose exec web python3 -c "
import sqlite3
con = sqlite3.connect('/app/data/db/users.sqlite')
con.execute(\"UPDATE users SET active=1 WHERE typeof(active)!='integer' OR active IS NULL\")
con.commit()
print('Repaired:', con.total_changes)
"
```

### 7.4b „Config integrity check failed (sha256 mismatch)" in Einstellungen

Behoben in Issue **#357** — Server muss auf neuestes Image laufen.

Hintergrund: nach einem Backup-Restore konnte ein stale `.sha256`-Sidecar
neben der Config-Datei zurückbleiben und passte nicht mehr zur frisch
restorten Datei. Der neue Restore-Flow:

1. **Räumt** alle alten Sidecars vor der Wiederherstellung weg
2. **Restored** Config + passendes Sidecar gemeinsam aus dem ZIP
3. **Regeneriert** das Sidecar deterministisch falls keines im Backup war

Zusätzlich greift im Compose-File die ENV `AICS_CONFIG_AUTO_REPAIR_SIDECAR=1`
als zweite Verteidigungslinie: wenn doch mal ein Mismatch auftritt, wird das
Sidecar mit einem Audit-Eintrag (`config.load outcome=repaired`) regeneriert
statt einen Fehler zu werfen.

**Manueller Workaround** wenn die UI hängt:

```bash
docker compose exec web rm -f /app/data/ai_compliance_suite.config.json.sha256
docker compose restart web
```

### 7.5 Frontend zeigt „Welcome to nginx!"

Das `aics_frontend`-Volume ist leer. Im aktuellen Image kopiert der
Entrypoint automatisch — falls trotzdem leer:

```bash
docker compose exec web cp -r /app/frontend/dist/. /srv/frontend/
docker compose restart nginx
```

### 7.6 Port-Konflikt mit Nextcloud / anderen Apps

Ports in `.env` ändern:

```bash
AICS_HTTP_PORT=8090
AICS_HTTPS_PORT=8453

docker compose up -d
```

---

## 8. Production-Hardening-Checkliste

Nach Erstinstallation prüfen:

- [ ] `ENABLE_DEMO_USERS=false` in `.env`, Demo-User deaktiviert
- [ ] Eigener Admin-Account angelegt, Passwort ≥ 12 Zeichen
- [ ] `JWT_SECRET_KEY` mit `secrets.token_hex(32)` generiert (nicht aus Doku kopiert)
- [ ] `.env` mit `chmod 600`
- [ ] **AICS_IMAGE_TAG=sha-…** statt `latest` (exakte Revision pinnen)
- [ ] Echtes TLS-Cert statt Self-Signed
  ([Let's-Encrypt-Anleitung](#9-tls-mit-lets-encrypt))
- [ ] Reverse-Proxy hinter weiterer Firewall (z.B. Cloudflare)
- [ ] Backup-Cron eingerichtet (siehe unten)
- [ ] Monitoring: `docker compose ps` + Health-Endpoint via Uptime-Robot
- [ ] CORS_ORIGINS enthält **nur** den tatsächlichen Frontend-Origin

### Backup-Cron

```bash
# /etc/cron.d/aics-backup
0 2 * * * docker02 cd /opt/ai-compliance-suite && ./scripts/update.sh --no-backup >/dev/null 2>&1
0 3 * * * docker02 docker run --rm -v aics_data:/data:ro -v /opt/ai-compliance-suite/backups:/backup alpine tar czf /backup/cron_$(date +\%F).tar.gz -C /data .
0 4 * * * docker02 find /opt/ai-compliance-suite/backups -name 'cron_*.tar.gz' -mtime +14 -delete
```

---

## 9. TLS mit Let's-Encrypt

Self-Signed reicht im LAN. Für öffentliche Endpoints:

```bash
# 1. Certbot-Container starten (HTTP-Challenge)
docker run --rm -p 80:80 \
  -v /opt/ai-compliance-suite/letsencrypt:/etc/letsencrypt \
  certbot/certbot certonly --standalone \
  -d compliance.example.com --agree-tos -m admin@example.com

# 2. Certs ins aics_certs-Volume kopieren
docker run --rm \
  -v /opt/ai-compliance-suite/letsencrypt:/le:ro \
  -v aics_certs:/dest \
  alpine sh -c '
    cp /le/live/compliance.example.com/fullchain.pem /dest/server.crt
    cp /le/live/compliance.example.com/privkey.pem  /dest/server.key
    chmod 644 /dest/server.crt && chmod 600 /dest/server.key
  '

# 3. Nginx neu laden
docker compose restart nginx
```

Erneuerung alle 60 Tage automatisieren (cron + Skript).

---

## 10. Portainer-Integration

Wenn auf dem Server **Portainer** läuft (z.B. Port 9443):

1. Portainer → **Local** → **Stacks** → **Add stack**
2. Name: `ai-compliance-suite`
3. Build-Methode: **Repository**
   - URL: `https://github.com/martinzeifang/AI_Compliance_Suite`
   - Compose-Pfad: `docker-compose.yml`
   - Authentifizierung: GitHub-Token mit `repo`-Scope
4. Environment Variables aus `.env` hochladen
5. **Deploy the stack**

Updates dann per Portainer-UI: Stack → **Update the stack** →
"Pull and redeploy" angekreuzt.

---

## Referenzen

- [Web-App-Übersicht](index.md)
- [Benutzerverwaltung](user-management.md)
- [Framework-Bibliothek](framework-library.md)
- [Ollama-Setup (KI-Modelle)](ollama-setup.md)
- Image-Registry: [ghcr.io/martinzeifang/ai_compliance_suite](https://github.com/martinzeifang/AI_Compliance_Suite/pkgs/container/ai_compliance_suite)
- CI-Workflow: [.github/workflows/docker-publish.yml](https://github.com/martinzeifang/AI_Compliance_Suite/blob/main/.github/workflows/docker-publish.yml)
