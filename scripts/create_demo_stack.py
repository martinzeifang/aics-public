#!/usr/bin/env python3
"""Erstellt den unabhängigen Demo-Stack 'aics-demo' auf docker02 (endpoint 3).
Eigene Container (aicsdemo_*), Ports 8085/8445, eigenes Postgres + JWT.
Portainer-Admin-PW via STDIN (Zeile 1)."""
import json, secrets, ssl, sys, urllib.request, urllib.error
import yaml

admin_pw = sys.stdin.readline().strip()
assert admin_pw, "STDIN Zeile1 = Portainer-Admin-PW"

ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
BASE = "https://localhost:9443/api"

def req(method, path, data=None, token=None):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = "Bearer " + token
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(BASE + path, data=body, headers=h, method=method)
    try:
        return json.load(urllib.request.urlopen(r, context=ctx))
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, "BODY:", e.read().decode()[:500]); raise

jwt = req("POST", "/auth", {"Username": "admin", "Password": admin_pw})["jwt"]

# Basis: Prod-Compose von Stack 50, dann auf Demo umbauen.
content = req("GET", "/stacks/50/file", token=jwt)["StackFileContent"]
d = yaml.safe_load(content)

for name, svc in d.get("services", {}).items():
    cn = svc.get("container_name")
    if cn and cn.startswith("aics_"):
        svc["container_name"] = cn.replace("aics_", "aicsdemo_", 1)
    if isinstance(svc.get("labels"), dict) and "io.portainer.stack" in svc["labels"]:
        svc["labels"]["io.portainer.stack"] = "aics-demo"

# Kaltstart der frischen Demo-DB (alle Schemata anlegen) braucht Zeit → großzügiger
# start_period; ZUSÄTZLICH nginx nur auf web-START (nicht -HEALTH) warten lassen,
# damit der Portainer-Deploy nicht im Health-Wait ins 500 läuft (web wird danach
# eigenständig healthy). web bleibt vom Postgres-Health abhängig.
_web = d["services"]["web"]
_hc = _web.get("healthcheck") or {}
_hc["start_period"] = "300s"
_web["healthcheck"] = _hc
_ng = d["services"].get("nginx", {})
_dep = _ng.get("depends_on")
if isinstance(_dep, dict) and "web" in _dep:
    _dep["web"]["condition"] = "service_started"

newc = yaml.dump(d, sort_keys=False, default_flow_style=False, width=4096)

# Bereits vorhandenen aics-demo-Stack (falls Re-Run) finden → löschen für sauberen Neuaufbau.
for s in req("GET", "/stacks", token=jwt):
    if s.get("Name") == "aics-demo" and s.get("EndpointId") == 3:
        print("Vorhandenen aics-demo-Stack löschen:", s["Id"])
        req("DELETE", f"/stacks/{s['Id']}?endpointId=3", token=jwt)

env = [
    {"name": "POSTGRES_PASSWORD", "value": secrets.token_urlsafe(24)},
    {"name": "JWT_SECRET_KEY", "value": secrets.token_hex(32)},
    {"name": "ENABLE_DEMO_USERS", "value": "true"},
    {"name": "AICS_HTTP_PORT", "value": "8085"},
    {"name": "AICS_HTTPS_PORT", "value": "8445"},
    {"name": "CORS_ORIGINS", "value": "https://aics.example.com:8445,https://localhost:8445"},
]
payload = {"name": "aics-demo", "stackFileContent": newc, "env": env}
res = req("POST", "/stacks/create/standalone/string?endpointId=3", payload, token=jwt)
print("Stack erstellt:", res.get("Name"), "Id:", res.get("Id"))
