#!/usr/bin/env python3
"""#1415/#1416: SOC-Operations-Portal-Stack 'aics-soc' (Portainer, gleiches Image).

Runtime-Flag AICS_PORTAL=soc, eigene Container (aicssoc_*), Ports 8086/8446.
**Shared-DB:** das Portal nutzt die SUITE-Datenbank (gemeinsame User/Passkeys/Incidents),
damit sich jeder mit seinem Suite-Account anmelden kann. Dazu wird der mitgelieferte
postgres-Service ENTFERNT, das Portal hängt am externen Netz der Suite und zeigt per
DATABASE_URL auf die Suite-DB.

STDIN (je 1 Zeile):
  1) Portainer-Admin-Passwort
  2) Endpoint-Id (2=docker01, 3=docker02; Default 3)
  3) DATABASE_URL der Suite (z.B. postgresql://aics:<pw>@aics_postgres:5432/aics)
     -> Host = CONTAINER-Name der Suite-DB (eindeutig auf dem externen Netz).
  4) externer Netzwerk-Name der Suite (Default ai-compliance-suite_app-network)
"""
import json, secrets, ssl, sys, urllib.request, urllib.error
import yaml

admin_pw = sys.stdin.readline().strip()
assert admin_pw, "STDIN Zeile1 = Portainer-Admin-PW"
endpoint = (sys.stdin.readline().strip() or "3")
database_url = sys.stdin.readline().strip()
assert database_url.startswith("postgresql://"), "STDIN Zeile3 = DATABASE_URL der Suite"
ext_net = (sys.stdin.readline().strip() or "ai-compliance-suite_app-network")

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

src_stack = "50" if endpoint == "3" else "45"
content = req("GET", f"/stacks/{src_stack}/file", token=jwt)["StackFileContent"]
d = yaml.safe_load(content)
svcs = d.get("services", {})

# 1) Eigenes Postgres entfernen (Shared-DB) + Referenzen aufräumen.
svcs.pop("postgres", None)
d.setdefault("volumes", {}).pop("aics_pgdata", None)
for name, svc in svcs.items():
    dep = svc.get("depends_on")
    if isinstance(dep, dict):
        dep.pop("postgres", None)
    elif isinstance(dep, list) and "postgres" in dep:
        dep.remove("postgres")
    # Container-Namen aicssoc_*
    cn = svc.get("container_name")
    if cn and cn.startswith("aics_"):
        svc["container_name"] = cn.replace("aics_", "aicssoc_", 1)
    if isinstance(svc.get("labels"), dict) and "io.portainer.stack" in svc["labels"]:
        svc["labels"]["io.portainer.stack"] = "aics-soc"

# 2) Externes Suite-Netz an web + nginx hängen (Zugriff auf die Suite-DB).
d.setdefault("networks", {})[ext_net] = {"external": True}
for sname in ("web", "nginx"):
    svc = svcs.get(sname)
    if not svc:
        continue
    nets = svc.get("networks")
    if isinstance(nets, list):
        if ext_net not in nets:
            nets.append(ext_net)
    elif isinstance(nets, dict):
        nets.setdefault(ext_net, None)
    else:
        svc["networks"] = [ext_net]

# 3) nginx nur auf web-START warten + großzügiger web-start_period (wie Demo/SOC).
_web = svcs["web"]
_hc = _web.get("healthcheck") or {}
_hc["start_period"] = "300s"
_web["healthcheck"] = _hc
_ng = svcs.get("nginx", {})
_dep = _ng.get("depends_on")
if isinstance(_dep, dict) and "web" in _dep:
    _dep["web"]["condition"] = "service_started"

newc = yaml.dump(d, sort_keys=False, default_flow_style=False, width=4096)

for s in req("GET", "/stacks", token=jwt):
    if s.get("Name") == "aics-soc" and str(s.get("EndpointId")) == endpoint:
        print("Vorhandenen aics-soc-Stack löschen:", s["Id"])
        req("DELETE", f"/stacks/{s['Id']}?endpointId={endpoint}", token=jwt)

host = "aics.example.com" if endpoint == "3" else "192.168.10.100"
env = [
    {"name": "JWT_SECRET_KEY", "value": secrets.token_hex(32)},
    {"name": "AICS_PORTAL", "value": "soc"},                       # #1411 Portal-Modus
    {"name": "ENABLE_DEMO_USERS", "value": "false"},              # Prod: echte Suite-User
    {"name": "AICS_HTTP_PORT", "value": "8086"},
    {"name": "AICS_HTTPS_PORT", "value": "8446"},
    {"name": "DATABASE_URL", "value": database_url},              # Shared-DB (Suite)
    {"name": "CORS_ORIGINS", "value": f"https://{host}:8446,https://localhost:8446"},
    # #1416: Passkey-Origin inkl. Portal-Port; RP-ID bleibt die Domain (port-unabhängig).
    {"name": "WEBAUTHN_RP_ORIGIN", "value": f"https://{host}:8446"},
]
payload = {"name": "aics-soc", "stackFileContent": newc, "env": env}
res = req("POST", f"/stacks/create/standalone/string?endpointId={endpoint}", payload, token=jwt)
print("SOC-Portal-Stack erstellt:", res.get("Name"), "Id:", res.get("Id"),
      f"→ https://{host}:8446 (Shared-DB, Netz {ext_net})")
