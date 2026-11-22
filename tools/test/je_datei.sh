#!/usr/bin/env bash
# Lokales Gegenstueck zur CI: JEDE Testdatei in EIGENEM pytest-Prozess.
#
# WARUM NICHT `pytest tests/`
# Ein Gesamtlauf in EINEM Prozess erschoepft den DB-Pool und kontaminiert
# App-State (steht so in `.github/workflows/ci.yml`, #1546/#1530). Gemessen am
# 30.10.2026: 461 Fehlschlaege auf `origin/main` und 463 auf einem Branch mit
# acht Fixes — die Zahl sagt ueber den Code nichts, die Fehlerbilder sind
# `401 Authentication required` und `KeyError: 'id'` in Fixtures. Dateiweise
# sind dieselben Tests gruen. Wer den Volllauf als Freigabekriterium nimmt,
# sucht den Fehler im Code, und er steckt im Messinstrument.
#
# Aufruf:
#   tools/test/je_datei.sh /tmp/lauf.log tests/test_a.py tests/test_b.py
#   tools/test/je_datei.sh /tmp/lauf.log $(ls tests/test_*.py)     # alles
#
# Voraussetzung: Postgres erreichbar. `DATABASE_URL` und `JWT_SECRET_KEY` aus
# der Umgebung gewinnen, sonst gelten lokale Vorgabewerte. NIE zwei Laeufe
# gleichzeitig gegen dieselbe Datenbank — `_pg_isolate` droppt vor jedem Test
# alle Schemata, der eine Lauf reisst dem anderen das Schema weg.
set -uo pipefail
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"

# Vorhandene Werte gewinnen — wer eine eigene Test-Datenbank fährt, soll sie
# nicht im Skript suchen müssen.
: "${DATABASE_URL:=postgresql://test:test@localhost:55432/test}"
: "${JWT_SECRET_KEY:=0123456789abcdef0123456789abcdef0123456789abcdef}"
export DATABASE_URL JWT_SECRET_KEY
export AICS_TRACK_SCHEMAS=1 ENABLE_DEMO_USERS=true FLASK_ENV=testing
LOG="$1"; shift
: > "$LOG"
rot=0; gruen=0
for f in "$@"; do
  aus=$(timeout -k 20 600 python3 -m pytest -q -p no:cacheprovider -o addopts="" "$f" 2>&1)
  code=$?
  zeile=$(grep -E "^[0-9]+ (passed|failed)|passed|failed|error" <<<"$aus" | tail -1)
  if [ $code -eq 0 ]; then
    gruen=$((gruen+1)); echo "OK   $f  ${zeile}" >> "$LOG"
  else
    rot=$((rot+1)); echo "ROT  $f  (exit $code)  ${zeile}" >> "$LOG"
    echo "--- Ausgabe $f ---" >> "$LOG"; echo "$aus" | tail -40 >> "$LOG"
  fi
done
echo "=== gruen: $gruen · rot: $rot ===" | tee -a "$LOG"
grep "^ROT" "$LOG" || true
