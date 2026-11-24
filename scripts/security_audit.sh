#!/bin/bash
# Phase 6.2 Security-Audit-Helper
# Läuft pip-audit gegen requirements.txt + scannt frontend/package.json
#
# Usage: ./scripts/security_audit.sh [--fix]

set -e

cd "$(dirname "$0")/.."

echo "═══════════════════════════════════════════════════════════════════"
echo "  Backend (Python) — pip-audit"
echo "═══════════════════════════════════════════════════════════════════"

if ! command -v pip-audit &>/dev/null; then
  echo "pip-audit nicht installiert. Installiere…"
  pip install --break-system-packages pip-audit
fi

pip-audit -r requirements.txt --skip-editable

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  Frontend (npm) — npm audit"
echo "═══════════════════════════════════════════════════════════════════"

if [ -d frontend ]; then
  cd frontend
  if [ "$1" = "--fix" ]; then
    npm audit fix --force || true
  else
    npm audit --audit-level=moderate || true
  fi
  cd ..
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  ✓ Security-Audit abgeschlossen"
echo "═══════════════════════════════════════════════════════════════════"
