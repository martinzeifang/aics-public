#!/usr/bin/env bash
# test-public-sync.sh (#425)
# Lokaler Dry-Run der Public-Sync-Pipeline. Reproduziert was der
# .github/workflows/sync-to-public.yml-Workflow tut — ohne git push.
#
# Output: /tmp/aics-public-dryrun/  (kann inspiziert werden)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-/tmp/aics-public-dryrun}"

echo "═══════════════════════════════════════════════════════════════════"
echo "  Public-Sync Dry-Run"
echo "═══════════════════════════════════════════════════════════════════"
echo "  Source: $REPO_ROOT"
echo "  Target: $TARGET"
echo ""

# Clean
rm -rf "$TARGET"
mkdir -p "$TARGET"

# rsync (gleiche Excludes wie der Workflow)
echo "→ rsync mit .sync-exclude …"
rsync -a --delete \
  --exclude-from="$REPO_ROOT/.sync-exclude" \
  "$REPO_ROOT/" "$TARGET/"

# anonymize-configs
echo "→ Generiere *.config.example.json …"
bash "$REPO_ROOT/scripts/anonymize-configs.sh" "$TARGET" 2>&1 | sed 's/^/   /'

# LICENSE / NOTICE / README
echo "→ LICENSE + NOTICE + Public-README …"
cp "$REPO_ROOT/.public-templates/LICENSE" "$TARGET/LICENSE"
cp "$REPO_ROOT/.public-templates/NOTICE" "$TARGET/NOTICE"
cp "$REPO_ROOT/.public-templates/README.public.md" "$TARGET/README.md"

# CI-Workflows
echo "→ Public-CI-Workflows …"
mkdir -p "$TARGET/.github/workflows"
rm -rf "$TARGET/.github/workflows/"*
cp "$REPO_ROOT/.public-templates/.github-workflows-public/"*.yml "$TARGET/.github/workflows/"

# SECURITY
cat > "$TARGET/SECURITY.md" <<'EOF'
# Security Policy

Bug Reports zu Security-Themen bitte vertraulich an martin.zeifang@gmail.com.
EOF

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  Validierung"
echo "═══════════════════════════════════════════════════════════════════"

# Check: keine Excludes geleakt
echo ""
echo "→ Suche nach Excludes-Patterns die NICHT da sein sollten …"
LEAKS=0
for forbidden in bnits_suite docs/sales .claude data certs evidence \
                  ai_compliance_suite/gui.py ai_compliance_suite/auth.py \
                  ai_compliance_suite/license_dialog.py ai_compliance_suite/license_state.py \
                  ai_compliance_suite.config.json \
                  sync_linked_issues_to_docker .env \
                  start-suite.sh install-desktop-entry.sh install-ollama.sh \
                  cra/gui_module.py compliance/standalone.py \
                  vcs/issue_assistant.py shared/db_viewer.py prefill; do
  if [ -e "$TARGET/$forbidden" ]; then
    echo "   ✗ LEAK: $forbidden ist im Target"
    LEAKS=$((LEAKS+1))
  fi
done

# Tk-Import-Check: keine aktiven Tk-Frames erwarten (shared/errors.py darf,
# weil dort der Import in einer Funktion mit try/except gewrapped ist)
echo ""
echo "→ Tk-Imports im Target (außer shared/errors.py)…"
TK_FILES=$(grep -rl "^import tkinter\|^from tkinter" "$TARGET" 2>/dev/null \
  | grep -v "shared/errors.py" \
  | grep -v "\.md$" || true)
if [ -n "$TK_FILES" ]; then
  echo "$TK_FILES" | head -10 | sed 's/^/   ✗ Tk-Datei: /'
  LEAKS=$((LEAKS + $(echo "$TK_FILES" | wc -l)))
else
  echo "   ✓ keine aktiven Tk-Files"
fi
# Spezial: anonymize-configs.sh ist OK weil Public-User es auch braucht
if [ "$LEAKS" = "0" ]; then
  echo "   ✓ keine Internas im Target gefunden"
fi

# Check: erwartete Files vorhanden
echo ""
echo "→ Erwartete Files im Target …"
MISSING=0
for required in LICENSE NOTICE README.md SECURITY.md \
                docker-compose.yml Dockerfile docker/ \
                server/ shared/ vcs/ frontend/ tests/ \
                cra/ dsgvo/ nis2/ risikobewertung/ \
                ai_compliance_suite/config.py \
                ai_compliance_suite/ai/ \
                .github/workflows/docker-publish.yml \
                .github/workflows/tests.yml \
                ai_compliance_suite.config.example.json; do
  if [ ! -e "$TARGET/$required" ]; then
    echo "   ✗ FEHLT: $required"
    MISSING=$((MISSING+1))
  fi
done
if [ "$MISSING" = "0" ]; then
  echo "   ✓ alle erwarteten Files vorhanden"
fi

# Check: keine GH-Internal Workflows
echo ""
echo "→ Keine internen Workflows im Public …"
INTERNAL_WORKFLOWS=$(ls "$TARGET/.github/workflows/" 2>/dev/null)
echo "   Public-Workflows: $INTERNAL_WORKFLOWS"
case "$INTERNAL_WORKFLOWS" in
  *sync-to-public*|*sync-project*)
    echo "   ✗ LEAK: interner Workflow im Public!"
    LEAKS=$((LEAKS+1))
    ;;
esac

echo ""
echo "═══════════════════════════════════════════════════════════════════"
TOTAL=$((LEAKS+MISSING))
if [ "$TOTAL" = "0" ]; then
  echo "  ✓ Dry-Run erfolgreich. Target: $TARGET"
  echo "  $(find "$TARGET" -type f | wc -l) Dateien, $(du -sh "$TARGET" | cut -f1) Gesamtgröße"
  exit 0
else
  echo "  ✗ $LEAKS Leaks, $MISSING fehlende Files."
  exit 1
fi
