# Docker-Deployment

Die AI Compliance Suite wird als Docker-Compose-Stack ausgeliefert.
Das Image liegt **public** auf GitHub Container Registry — kein Login,
kein PAT, keine Registrierung.

## Voraussetzungen

- Docker 24+ und Docker-Compose v2 (`docker compose version`)
- Freie Ports **8443** (HTTPS-UI) und **8082** (HTTP-Redirect)
- ≥ 2 GB RAM, ≥ 10 GB freier Plattenplatz

## Quickstart

```bash
# 1. docker-compose.yml holen
curl -O https://raw.githubusercontent.com/martinzeifang/aics-public/main/docker-compose.yml

# 2. Stack starten
docker compose up -d

# 3. Im Browser öffnen
#    https://localhost:8443
```

Beim ersten Start erzeugt der Container:

- ein zufälliges JWT-Secret
- ein Self-Signed TLS-Zertifikat
- einen Initial-Admin mit zufälligem Passwort
  → in den Logs nachschauen:

```bash
docker compose logs aics_web | grep -i "initial admin"
```

## Mit lokaler KI (Ollama)

```bash
COMPOSE_PROFILES=ai docker compose up -d
```

Der Ollama-Container zieht beim ersten Start ein Default-Modell
(~5 GB). Modelle werden in der App unter **Admin → KI-Modelle** verwaltet.

## Konfiguration (`.env`)

Für Produktivumgebungen leg eine `.env`-Datei neben die `docker-compose.yml`:

```dotenv
# Für Browser-Zugriff zugelassene Origins (komma-getrennt)
CORS_ORIGINS=https://aics.example.com:8443

# Image-Pinning (Production: nicht 'latest', sondern ein Release-Tag)
AICS_IMAGE_TAG=v0.1.0

# Demo-Admin beim ersten Start anlegen? In Produktion auf false.
AICS_DEMO_MODE=false
```

Stack neu starten:

```bash
docker compose up -d
```

## Update

```bash
# Neueres Image ziehen + Stack neu hochfahren
docker compose pull
docker compose up -d
```

Rollback: `AICS_IMAGE_TAG` in `.env` auf das vorherige Tag setzen und
`docker compose up -d` erneut ausführen.

## Backup

Alle Persistenten Daten liegen in Named Volumes (`aics_data`,
`aics_certs`, `aics_backups`, `aics_logs`). Backup als Tarball:

```bash
docker run --rm \
  -v ai-compliance-suite_aics_data:/data:ro \
  -v "$PWD":/backup \
  alpine tar czf /backup/aics-data-$(date +%F).tgz -C / data
```

Restore: Volume leeren und Tarball entpacken — Service vorher stoppen.

## Logs

```bash
docker compose logs -f aics_web      # live folgen
docker compose logs --tail=200 aics_web
docker compose logs aics_web | grep -i error
```

## TLS mit echtem Zertifikat

Ersetze den Inhalt des Volumes `aics_certs` durch deine `fullchain.pem`
und `privkey.pem` (z. B. via Let's Encrypt + certbot-Container) und
starte den Nginx-Container neu:

```bash
docker compose restart aics_nginx
```

## Troubleshooting

| Symptom | Ursache | Lösung |
|---|---|---|
| `port 8443 already in use` | Anderer Service auf 8443 | Port in `docker-compose.yml` mappen: `"9443:8443"` |
| Browser zeigt „nicht sicher" | Self-Signed-Cert | Akzeptieren oder echtes Cert installieren |
| Login schlägt fehl | Initial-Passwort vergessen | `docker compose logs aics_web | grep "initial admin"` |
| Container neu, leere DB | Volume entfernt | Backup einspielen (siehe oben) |

## Lizenz

Der Stack startet im Demo-Modus mit eingebauter Demo-Lizenz (30 Tage,
alle Module außer Gutachten). Für Produktivnutzung siehe
[Lizenz-Setup](license-setup.md).
