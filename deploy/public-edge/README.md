# Externe Veröffentlichung — lic.cyberwoks.de + aics.cyberwoks.de

Risikoarmer Aufbau: **TLS-Terminierung am Caddy-Edge-Proxy auf docker02** mit
automatischem **Let's Encrypt**; die **Firewall macht nur reine DNAT** (Port-Forward
80/443 → docker02). **KEIN IPS/WAF/DPI** auf der vFW (Incident 2026-06-01: IPS
überlastete die 4-vCPU-vFW → Netzausfall).

## Routing
- `aics.cyberwoks.de` → docker02:6875 (BookStack-Wiki)
- `lic.cyberwoks.de`  → docker02:8089 (Lizenzportal-nginx)

## Schritte
1. **DNS:** A-Records `aics.cyberwoks.de` + `lic.cyberwoks.de` → öffentliche WAN-IP.
2. **Firewall (Sophos XGS, API nur von 192.168.30.154, Admin-Login):** reine **DNAT**
   WAN tcp/80 + tcp/443 → `aics.example.com` (docker02, Zone ZFG_DMZ). **Keine** „Web Server
   Protection"/WAF, **kein** IPS. (Ggf. ISP/Upstream-Router: öffentliche IP → WAN 192.168.179.71.)
3. **App-URLs anpassen** (für korrekte Links/Assets/CORS):
   - BookStack: `APP_URL=https://aics.cyberwoks.de` in `/config/www/.env` + restart.
   - Lizenzportal: Basis-URL/CORS auf `https://lic.cyberwoks.de`.
4. **Edge starten (docker02):** `docker compose -f docker-compose.caddy.yml up -d`
   → Caddy holt die LE-Zertifikate automatisch (sobald DNS + DNAT stehen).
5. **Verifizieren:** `https://aics.cyberwoks.de` + `https://lic.cyberwoks.de` extern erreichbar, gültiges LE-Cert.

## Sicherheit
- Lizenzportal: **MFA verpflichtend** (#1442) + Account-Lockout.
- Edge nur 80/443; interne Ports bleiben intern. Firewall ohne DPI → keine Überlast.
