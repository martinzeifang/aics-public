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

# #1516: App-Version build-zeitlich ins Image injizieren (frontend/package.json liegt
# im Runtime-Image NICHT vor). Wird von docker-publish.yml als --build-arg gesetzt und
# von server.api.admin._app_version() ausgewertet.
ARG APP_VERSION=unknown
ENV APP_VERSION=${APP_VERSION}

# System-Dependencies + Cleanup
# #1593 (Härtung, Angriffsfläche minimieren): KEIN gh-CLI, kein gnupg, kein curl
# im Laufzeit-Image. GitHub-Operationen laufen über PAT-Token (verschlüsselt in
# den Settings bzw. pro Projekt, #862) via requests/urllib — der gh-CLI-Fallback
# ist in Server-Deployments nicht nötig und zog CRITICAL/HIGH-CVEs (gh/gnupg/curl)
# ins Image. openssl bleibt (Self-Signed-Cert + JWT-Secret im entrypoint),
# ca-certificates bleibt (ausgehendes HTTPS zu Cloud-LLM / GitHub-API).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        openssl \
    && rm -rf /var/lib/apt/lists/*

# DOCX→PDF läuft NICHT mehr im App-Image (#1032), sondern im separaten
# Gotenberg-Sidecar (docker-compose Service `gotenberg`). Das hält dieses Image
# schlank und LibreOffice muss bei App-Updates nicht neu gezogen werden.
# Konfiguration: ENV GOTENBERG_URL (Default http://gotenberg:3000).

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
COPY --chown=aics:aics dsgvo/ /app/dsgvo/
COPY --chown=aics:aics evidence/ /app/evidence/
COPY --chown=aics:aics gutachten/ /app/gutachten/
COPY --chown=aics:aics ict/ /app/ict/
COPY --chown=aics:aics firmen/ /app/firmen/
COPY --chown=aics:aics nis2/ /app/nis2/
COPY --chown=aics:aics prefill/ /app/prefill/
COPY --chown=aics:aics pentest/ /app/pentest/
COPY --chown=aics:aics risikobewertung/ /app/risikobewertung/
COPY --chown=aics:aics soc/ /app/soc/
COPY --chown=aics:aics wiba/ /app/wiba/
COPY --chown=aics:aics server/ /app/server/
COPY --chown=aics:aics shared/ /app/shared/
COPY --chown=aics:aics vcs/ /app/vcs/
COPY --chown=aics:aics wsgi.py run_dev.py security_utils.py README.md /app/

# Frontend-Build aus Stage 1
COPY --from=frontend-builder --chown=aics:aics /frontend/dist /app/frontend/dist

# Auto-Cert-Generation Script (Self-Signed HTTPS, #271)
COPY --chown=aics:aics docker/entrypoint.sh /app/entrypoint.sh
# #1593: Healthcheck ohne curl (Python-stdlib)
COPY --chown=aics:aics docker/healthcheck.py /app/healthcheck.py
RUN chmod +x /app/entrypoint.sh

# Verzeichnisse für Daten
# /srv/frontend MUSS hier mit aics-Ownership vor-angelegt werden — sonst
# erbt das Compose-Volume (aics_frontend) beim ersten Mount root:root und
# entrypoint.sh kann die Frontend-Assets nicht reinkopieren (Permission denied).
RUN mkdir -p /app/data/db /app/data/evidence /app/logs /app/out/backup /app/certs /srv/frontend && \
    chown -R aics:aics /app/data /app/logs /app/out /app/certs /srv/frontend

USER aics

# Health-Check
# #1593: curl ist nicht mehr im Image → Python-stdlib-Check (urllib). gunicorn
# lauscht auf Port 5000 als KLARTEXT-HTTP (TLS macht nginx); HTTPS-Fallback für
# den Fall HTTPS_ENABLED=true. Harte Timeouts, sonst hängt der Check bis ins
# Docker-Timeout. start-period großzügig für Cold-Start.
HEALTHCHECK --interval=15s --timeout=10s --start-period=90s --retries=6 \
    CMD ["python3", "/app/healthcheck.py"]

EXPOSE 5000

ENTRYPOINT ["/app/entrypoint.sh"]
# #415: gthread + 1800s timeout für Ollama-SSE-Streams.
#   - sync-Workers blockieren bei langlaufenden SSE-Requests den ganzen Worker
#   - 60s Default-Timeout killt den Worker während Ollama-Cold-Start (Modell laden)
#   - 1800s passt zu nginx proxy_read_timeout 1800s
CMD ["gunicorn", "-b", "0.0.0.0:5000", "-w", "2", "-k", "gthread", "--threads", "8", "--timeout", "1800", "--graceful-timeout", "30", "wsgi:app"]
