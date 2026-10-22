#!/bin/bash
# AI Compliance Suite — Server-Update aus ghcr.io
#
# Ablauf:
#   1. Optional: Backup der DBs anlegen
#   2. Neue Images von ghcr.io ziehen
#   3. Container neu starten (Daten in Named Volumes bleiben)
#   4. Alte Images aufräumen
#
# Usage:
#   ./scripts/update.sh             # mit Backup
#   ./scripts/update.sh --no-backup
#   AICS_IMAGE_TAG=sha-abc1234 ./scripts/update.sh   # spezifische Version

set -e
cd "$(dirname "$0")/.."

DO_BACKUP=true
if [ "${1:-}" = "--no-backup" ]; then
  DO_BACKUP=false
fi

echo "═══════════════════════════════════════════════════════════════════"
echo "  AI Compliance Suite — Update"
echo "═══════════════════════════════════════════════════════════════════"
echo "  Image-Tag:  ${AICS_IMAGE_TAG:-latest}"
echo "  Backup:     $DO_BACKUP"
echo ""

if $DO_BACKUP; then
  STAMP=$(date +%F_%H-%M)
  mkdir -p backups
  echo "→ DB-Backup: backups/aics_data_${STAMP}.tar.gz"
  docker run --rm \
    -v aics_data:/data:ro \
    -v "$(pwd)/backups:/backup" \
    alpine \
    tar czf "/backup/aics_data_${STAMP}.tar.gz" -C /data . || {
      echo "WARN: Backup fehlgeschlagen — Update wird fortgesetzt"
    }
fi

echo "→ Neue Images von ghcr.io ziehen"
docker compose pull

echo "→ Container austauschen (Down-/Uptime ~10s)"
docker compose up -d

echo "→ Health-Check (max. 60s)"
for i in {1..30}; do
  if docker compose exec -T web curl -fs http://localhost:5000/health >/dev/null 2>&1; then
    echo "  ✓ Backend gesund"
    break
  fi
  sleep 2
  [ "$i" = "30" ] && { echo "  ✗ Health-Check fehlgeschlagen!"; exit 1; }
done

echo "→ Alte Image-Layer aufräumen"
docker image prune -f >/dev/null

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  ✓ Update abgeschlossen"
echo "═══════════════════════════════════════════════════════════════════"
docker compose ps
