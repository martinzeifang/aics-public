#!/bin/bash
# Entrypoint für AI Compliance Suite Docker-Container.
# - Generiert Self-Signed HTTPS-Cert wenn keiner vorhanden (#271)
# - Validiert kritische Env-Variablen
# - Startet die App via gunicorn
set -e

CERT_DIR="${CERT_DIR:-/app/certs}"
CERT_FILE="$CERT_DIR/server.crt"
KEY_FILE="$CERT_DIR/server.key"

# ---- Self-Signed Cert für Nginx-TLS-Termination ----
# Immer generieren wenn noch kein Cert da (auch wenn Backend HTTP läuft).
# Nginx mountet dasselbe Named Volume read-only und braucht die Certs.
if [ ! -f "$CERT_FILE" ]; then
    echo "🔐 Generating self-signed HTTPS certificate ..."
    mkdir -p "$CERT_DIR"
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$KEY_FILE" \
        -out "$CERT_FILE" \
        -subj "/C=DE/ST=NRW/L=City/O=AI-Compliance-Suite/CN=${HOSTNAME:-localhost}" \
        2>/dev/null
    chmod 600 "$KEY_FILE"
    chmod 644 "$CERT_FILE"
    echo "✓ Cert generated at $CERT_FILE"
fi

# ---- JWT Secret: ENV gewinnt, sonst aus persistentem Volume (auto-generiert) ----
JWT_SECRET_FILE="/app/data/.jwt-secret"
if [ -z "${JWT_SECRET_KEY:-}" ] || [ "${#JWT_SECRET_KEY}" -lt 32 ]; then
    if [ -f "$JWT_SECRET_FILE" ]; then
        export JWT_SECRET_KEY="$(cat "$JWT_SECRET_FILE")"
        echo "🔑 JWT-Secret aus $JWT_SECRET_FILE geladen ($(echo -n "$JWT_SECRET_KEY" | wc -c) Zeichen)"
    else
        echo "🔑 Kein JWT_SECRET_KEY gesetzt — generiere stabilen Secret in $JWT_SECRET_FILE"
        mkdir -p /app/data
        # 64 Hex-Zeichen = 32 Bytes Entropie (openssl ist bereits im Image,
        # xxd ist NICHT installiert → openssl statt `head | xxd` verwenden).
        openssl rand -hex 32 > "$JWT_SECRET_FILE"
        chmod 600 "$JWT_SECRET_FILE"
        export JWT_SECRET_KEY="$(cat "$JWT_SECRET_FILE")"
        echo "✓ JWT-Secret erzeugt (64 chars)"
    fi
fi

if [ ${#JWT_SECRET_KEY} -lt 32 ]; then
    echo "ERROR: JWT_SECRET_KEY ist immer noch < 32 Zeichen — Volume schreibgeschützt?"
    exit 1
fi

# ---- Frontend-Assets ins shared volume kopieren ----
# Wenn FRONTEND_PUBLISH_DIR gesetzt (= Pfad eines gemounteten shared Volume),
# kopieren wir die Frontend-Build-Dateien dorthin, damit Nginx sie servieren kann.
if [ -n "${FRONTEND_PUBLISH_DIR:-}" ] && [ -d "/app/frontend/dist" ]; then
    echo "📦 Publishing frontend assets to $FRONTEND_PUBLISH_DIR ..."
    mkdir -p "$FRONTEND_PUBLISH_DIR"
    # Alte Builds wegräumen — sonst sammeln sich content-hashed Assets vergangener
    # Releases im Volume und Disk-Space wächst monoton.
    rm -rf "$FRONTEND_PUBLISH_DIR"/assets 2>/dev/null || true
    rm -f "$FRONTEND_PUBLISH_DIR"/*.html "$FRONTEND_PUBLISH_DIR"/*.css "$FRONTEND_PUBLISH_DIR"/*.js 2>/dev/null || true
    cp -r /app/frontend/dist/. "$FRONTEND_PUBLISH_DIR/"
    echo "   ✓ $(ls "$FRONTEND_PUBLISH_DIR/assets" 2>/dev/null | wc -l) Asset-Dateien kopiert"
fi

# ---- Initialize DBs ----
mkdir -p /app/data/db /app/logs /app/out/backup

# ---- Start App ----
echo "🚀 Starting AI Compliance Suite..."
echo "   Demo-Users: ${ENABLE_DEMO_USERS:-false}"
echo "   HTTPS: ${HTTPS_ENABLED:-false}"
echo "   Workers: ${GUNICORN_WORKERS:-4}"

exec "$@"
