# ============================================================
# Multi-Stage-Build für AI Compliance Suite
# ============================================================

# ---- Stage 1: Frontend-Build (Node 22) ----
# Node 22 erfüllt die Anforderungen aktueller Vite-Versionen (>= 20.19 / >= 22.12).
FROM node:22-alpine AS frontend-builder

WORKDIR /frontend

# Dependency-Install (caching layer)
COPY frontend/package*.json ./
RUN npm ci

# Frontend kompilieren
COPY frontend/ .
RUN npm run build || npx vite build --mode production --minify false

# ---- Stage 2: Python-Backend (Python 3.11 slim) ----
FROM python:3.11-slim AS backend-runtime

WORKDIR /app

# System-Dependencies + Cleanup
# gh CLI für GitHub-Operations falls kein PAT-Token in der Settings-UI
# konfiguriert ist (Fallback-Pfad in shared/github_config.py).
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        openssl \
        gnupg \
    && (curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | \
        dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg) \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# Non-root User für Security
RUN useradd -r -u 1000 -m -d /home/aics -s /bin/bash aics

# Python-Dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# Backend-Code
COPY --chown=aics:aics ai_compliance_suite/ /app/ai_compliance_suite/
COPY --chown=aics:aics ai_act/ /app/ai_act/
COPY --chown=aics:aics baso/ /app/baso/
COPY --chown=aics:aics compliance/ /app/compliance/
COPY --chown=aics:aics cra/ /app/cra/
COPY --chown=aics:aics dora/ /app/dora/
COPY --chown=aics:aics dsgvo/ /app/dsgvo/
COPY --chown=aics:aics evidence/ /app/evidence/
COPY --chown=aics:aics gutachten/ /app/gutachten/
COPY --chown=aics:aics ict/ /app/ict/
COPY --chown=aics:aics kunden/ /app/kunden/
COPY --chown=aics:aics nis2/ /app/nis2/
COPY --chown=aics:aics prefill/ /app/prefill/
COPY --chown=aics:aics risikobewertung/ /app/risikobewertung/
COPY --chown=aics:aics server/ /app/server/
COPY --chown=aics:aics shared/ /app/shared/
COPY --chown=aics:aics vcs/ /app/vcs/
COPY --chown=aics:aics wsgi.py run_dev.py security_utils.py README.md /app/

# Frontend-Build aus Stage 1
COPY --from=frontend-builder --chown=aics:aics /frontend/dist /app/frontend/dist

# Auto-Cert-Generation Script (Self-Signed HTTPS, #271)
COPY --chown=aics:aics docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Verzeichnisse für Daten
# /srv/frontend MUSS hier mit aics-Ownership vor-angelegt werden — sonst
# erbt das Compose-Volume (aics_frontend) beim ersten Mount root:root und
# entrypoint.sh kann die Frontend-Assets nicht reinkopieren (Permission denied).
RUN mkdir -p /app/data/db /app/data/evidence /app/logs /app/out/backup /app/certs /srv/frontend && \
    chown -R aics:aics /app/data /app/logs /app/out /app/certs /srv/frontend

USER aics

# Health-Check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -fsk https://localhost:5000/health || curl -fs http://localhost:5000/health || exit 1

EXPOSE 5000

ENTRYPOINT ["/app/entrypoint.sh"]
# #415: gthread + 1800s timeout für Ollama-SSE-Streams.
#   - sync-Workers blockieren bei langlaufenden SSE-Requests den ganzen Worker
#   - 60s Default-Timeout killt den Worker während Ollama-Cold-Start (Modell laden)
#   - 1800s passt zu nginx proxy_read_timeout 1800s
CMD ["gunicorn", "-b", "0.0.0.0:5000", "-w", "2", "-k", "gthread", "--threads", "8", "--timeout", "1800", "--graceful-timeout", "30", "wsgi:app"]
