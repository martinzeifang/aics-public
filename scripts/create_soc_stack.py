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
# Optional: explizites Subnetz fürs stack-lokale Netz (gegen „Pool overlaps" auf Hosts
# mit ausgeschöpftem Adressraum, z.B. docker01). Leer = Docker wählt selbst.
local_subnet = sys.stdin.readline().strip()

ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
BASE = "https://localhost:9443/api"


def req(method, path, data=None, token=None):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = "Bearer " + token
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(BASE + path, data=body, headers=h, method=method)
    try:
        raw = urllib.request.urlopen(r, context=ctx).read()
        return json.loads(raw) if raw.strip() else None  # DELETE → leerer 204-Body
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

# 2) Externes Suite-Netz NUR an web hängen (Zugriff auf die Suite-DB).
# WICHTIG (Alias-Kollision): web/nginx heißen im SOC-Stack wie in der Suite. Hängt man
# sie ins Suite-Netz, beanspruchen sie dort die Aliase `web`/`nginx` → die Suite-nginx
# proxyt `web:5000` dann zufällig zur SOC-Web (Portal-Modus) → Suite-Login kaputt.
# Daher: nginx NICHT ins Suite-Netz; web nur mit EINDEUTIGEM Alias (kein `web`).
# Hinweis: Docker Compose ergänzt den Service-Namen-Alias trotz `aliases` ggf. weiterhin —
# nach einem Redeploy prüfen: `docker inspect aicssoc_web` darf auf dem Suite-Netz KEIN
# `web` führen; sonst `docker network disconnect`+`connect --alias aicssoc_web_db` + nginx-Restart.
nets_top = d.setdefault("networks", {})
nets_top[ext_net] = {"external": True}
if local_subnet:
    for nname in list(nets_top.keys()):
        if nname == ext_net:
            continue
        nets_top[nname] = {"ipam": {"config": [{"subnet": local_subnet}]}}
_w = svcs.get("web", {})
_wn = _w.get("networks")
own = ([n for n in _wn if n != ext_net][0] if isinstance(_wn, list) and _wn
       else (next((n for n in _wn if n != ext_net), None) if isinstance(_wn, dict) else None))
_w["networks"] = {}
if own:
    _w["networks"][own] = None
_w["networks"][ext_net] = {"aliases": ["aicssoc_web_db"]}

# 2b) Variablen DIREKT in die web-Environment schreiben (deterministisch). Grund:
# Portainer-Stack-Env erreicht den Container nur, wenn die Compose-`environment` sie
# referenziert. Der alte Prod-Compose referenziert weder AICS_PORTAL noch (zuverlässig)
# DATABASE_URL → daher hier hart setzen.
host = "aics.example.com" if endpoint == "3" else "192.168.10.100"
_web = svcs["web"]
_direct = {
    "DATABASE_URL": database_url,
    "AICS_PORTAL": "soc",                       # #1411 Portal-Modus
    "WEBAUTHN_RP_ORIGIN": f"https://{host}:8446",  # #1416 Passkey-Origin (RP-ID = Domain)
}
_envl = _web.get("environment")
if isinstance(_envl, list):
    _envl = [e for e in _envl if not any(str(e).startswith(k + "=") for k in _direct)
             and not str(e).startswith("POSTGRES_PASSWORD=")]
    _envl += [f"{k}={v}" for k, v in _direct.items()]
    _web["environment"] = _envl
elif isinstance(_envl, dict):
    _envl.pop("POSTGRES_PASSWORD", None)
    _envl.update(_direct)

# 3) nginx nur auf web-START warten + großzügiger web-start_period (wie Demo/SOC).
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

# Diese Vars referenziert der Compose (${...}) → Portainer-Stack-Env genügt.
# AICS_PORTAL / DATABASE_URL / WEBAUTHN_RP_ORIGIN stehen direkt in der web-Env (2b).
env = [
    {"name": "JWT_SECRET_KEY", "value": secrets.token_hex(32)},
    {"name": "ENABLE_DEMO_USERS", "value": "false"},              # Prod: echte Suite-User
    {"name": "AICS_HTTP_PORT", "value": "8086"},
    {"name": "AICS_HTTPS_PORT", "value": "8446"},
    {"name": "CORS_ORIGINS", "value": f"https://{host}:8446,https://localhost:8446"},
]
payload = {"name": "aics-soc", "stackFileContent": newc, "env": env}
res = req("POST", f"/stacks/create/standalone/string?endpointId={endpoint}", payload, token=jwt)
print("SOC-Portal-Stack erstellt:", res.get("Name"), "Id:", res.get("Id"),
      f"→ https://{host}:8446 (Shared-DB, Netz {ext_net})")
