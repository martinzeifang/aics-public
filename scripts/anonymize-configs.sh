#!/usr/bin/env bash
# anonymize-configs.sh (#421)
# ────────────────────────────────────────────────────────────────────────────
# Erzeugt *.config.example.json aus den Modul-Defaults (default_config()
# Funktionen). Wird vom Sync-Workflow (sync-to-public.yml) aufgerufen,
# bevor das gepruefte Repo nach martinzeifang/aics-public gepusht wird.
#
# Verwendung:
#   bash scripts/anonymize-configs.sh /tmp/public-tree
#   bash scripts/anonymize-configs.sh --dry-run /tmp/public-tree
#
# Output:
#   - schreibt <module>.config.example.json je vorhandenem default_config()
#   - existierende *.config.json wurden bereits via .sync-exclude entfernt;
#     dieses Script ergaenzt nur die Beispieldateien als Vorlagen.
# ────────────────────────────────────────────────────────────────────────────

set -euo pipefail

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN=1
    shift
fi

TARGET="${1:-}"
if [ -z "$TARGET" ] || [ ! -d "$TARGET" ]; then
    echo "Usage: $0 [--dry-run] <target-dir>" >&2
    exit 1
fi

# Module mit default_config() — Liste konsistent zu *.config.json im Repo-Root
MODULES=(
    ai_act
    ai_compliance_suite
    baso
    compliance
    compliance_db
    cra
    dsgvo
    gutachten
    ict
    kunden
    nis2
    risikobewertung
)

# Repo-Root (Pfad in dem dieses Script liegt → parent)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

generate_one() {
    local module="$1"
    local out="$TARGET/${module}.config.example.json"

    # Python aufrufen mit Repo-Root im sys.path, damit  `import <module>.config`
    # funktioniert; wir lassen default_config() laufen.
    local json
    if ! json=$(cd "$REPO_ROOT" && python3 -c "
import json, sys, importlib
try:
    mod = importlib.import_module('${module}.config')
except ModuleNotFoundError:
    sys.exit(2)
fn = getattr(mod, 'default_config', None)
if fn is None:
    sys.exit(3)
cfg = fn()
print(json.dumps(cfg, indent=2, ensure_ascii=False, sort_keys=True))
" 2>/dev/null); then
        echo "  ⚠ ${module}: kein default_config — uebersprungen" >&2
        return 0
    fi

    if [ "$DRY_RUN" = "1" ]; then
        echo "  [dry-run] would write $out  (${#json} bytes)"
    else
        printf '%s\n' "$json" > "$out"
        echo "  ✓ $out  (${#json} bytes)"
    fi
}

echo "anonymize-configs → $TARGET (dry-run=$DRY_RUN)"
for m in "${MODULES[@]}"; do
    generate_one "$m"
done

echo "done."
