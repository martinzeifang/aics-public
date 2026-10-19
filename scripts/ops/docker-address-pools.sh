#!/usr/bin/env bash
# Docker-Adress-Pools dauerhaft fixieren — verhindert Subnetz-Kollisionen mit den LANs.
#
# Hintergrund (2026-10-15): Sind die Standard-Pools 172.17–172.31 aufgebraucht, vergibt
# Docker automatisch 192.168.x.0/20-Netze. Auf docker02 entstand so ein Netz
# 192.168.0.0/20, das das PEN-Netz 192.168.10.0/24 (docker01/Portainer) überdeckte →
# docker02 schickte Antworten an docker01 in eine leere Bridge, Portainer-Endpoint „down".
#
# Das Skript setzt in /etc/docker/daemon.json
#   - "default-address-pools": [{"base": "10.200.0.0/16", "size": 24}]  (256 Netze, kein LAN-Overlap)
#   - "live-restore": true  (Container laufen beim Docker-Neustart weiter)
# und übernimmt alle übrigen vorhandenen Einstellungen unverändert. Idempotent.
#
# Ausführung (als root), z. B. vom Admin-Rechner:
#   ssh -t docker02@docker02 'sudo bash -s' < scripts/ops/docker-address-pools.sh
#   ssh -t docker01@docker01 'sudo bash -s' < scripts/ops/docker-address-pools.sh
#
# Ablauf: Backup → Merge → `dockerd --validate` → Reload (aktiviert live-restore ohne
# Neustart) → Restart (aktiviert die Pools; Container laufen dank live-restore weiter)
# → Kontrolle mit einem Wegwerf-Netz.
set -euo pipefail

POOL_BASE="${POOL_BASE:-10.200.0.0/16}"
POOL_SIZE="${POOL_SIZE:-24}"
CONF=/etc/docker/daemon.json

[ "$(id -u)" = 0 ] || { echo "Bitte als root ausführen (sudo)."; exit 1; }

# Pool darf weder lokale LAN-Routen noch bestehende Docker-Netze überdecken.
ip -4 route | grep -v -E " dev (docker|br-)" | awk '{print $1}' | grep -E '^[0-9]' > /tmp/pool-routes.$$ || true
docker network inspect $(docker network ls -q) -f '{{range .IPAM.Config}}{{.Subnet}} {{end}}' \
  | tr ' ' '\n' | grep -E '^[0-9]+\.' >> /tmp/pool-routes.$$ || true
python3 - "$POOL_BASE" /tmp/pool-routes.$$ <<'PY'
import ipaddress, sys
pool = ipaddress.ip_network(sys.argv[1])
clash = [n for n in open(sys.argv[2]).read().split()
         if ":" not in n and ipaddress.ip_network(n, strict=False).overlaps(pool)]
if clash:
    sys.exit(f"Abbruch: {pool} überschneidet sich mit {', '.join(clash)}")
PY
rm -f /tmp/pool-routes.$$

mkdir -p /etc/docker
[ -f "$CONF" ] && cp -a "$CONF" "${CONF}.bak.$(date +%Y%m%d%H%M%S)"

python3 - "$CONF" "$POOL_BASE" "$POOL_SIZE" <<'PY'
import json, sys, pathlib
p, base, size = pathlib.Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
cfg = json.loads(p.read_text()) if p.exists() and p.read_text().strip() else {}
cfg["default-address-pools"] = [{"base": base, "size": size}]
cfg["live-restore"] = True
tmp = p.with_suffix(".json.new")
tmp.write_text(json.dumps(cfg, indent=2) + "\n")
print(tmp.read_text())
PY

dockerd --validate --config-file "${CONF%.json}.json.new"
install -m 0644 "${CONF%.json}.json.new" "$CONF"
rm -f "${CONF%.json}.json.new"

systemctl reload docker                       # live-restore wird ohne Neustart aktiv
sleep 2
[ "$(docker info --format '{{.LiveRestoreEnabled}}')" = "true" ] || { echo "live-restore nicht aktiv — Abbruch vor Restart"; exit 1; }

systemctl restart docker                      # aktiviert default-address-pools
sleep 5

net="pool-check-$$"
docker network create "$net" >/dev/null
subnet=$(docker network inspect -f '{{range .IPAM.Config}}{{.Subnet}}{{end}}' "$net")
docker network rm "$net" >/dev/null
echo "Neues Docker-Netz bekommt: ${subnet}"
case "$subnet" in
  10.200.*) echo "OK — Pools aktiv, Container laufen weiter:"; docker ps --format '  {{.Names}}  {{.Status}}' | head -40 ;;
  *) echo "WARNUNG: Pool nicht aktiv (${subnet})"; exit 1 ;;
esac
