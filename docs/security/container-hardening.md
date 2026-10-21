# Container-Härtung & Image-Pinning (#1188)

OWASP Secure-by-Design (Supply Chain), ISO/IEC 27001:2022 (Lieferkette), ISO/IEC 27034.

## Image-Pinning im Produktivbetrieb

Die Basis-`docker-compose.yml` ist dev-freundlich (mutable Tags). Für Produktion das
Override `docker-compose.prod.yml` verwenden — es verbietet `:latest` und pinnt alle Images:

```bash
AICS_IMAGE_TAG=v6.23.0 docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

- **App-/nginx-Image:** `AICS_IMAGE_TAG` ist im Prod-Profil **Pflicht** (`:?`) — ein
  versehentliches `:latest` bricht den Start ab. Maximale Sicherheit: per Digest pinnen
  (`AICS_IMAGE=ghcr.io/martinzeifang/ai_compliance_suite@sha256:…`).
- **Drittanbieter-Images** (gotenberg/ollama/postgres/alpine): im Override auf konkrete
  Versionen gepinnt. Vor Produktivnahme Digest auflösen und `@sha256:…` eintragen:
  ```bash
  docker buildx imagetools inspect gotenberg/gotenberg:8.12.0   # → Digest
  ```

## Signatur-Verifikation (cosign, keyless)

App- und nginx-Image werden in der CI signiert (`.github/workflows/docker-publish.yml`, #744)
und tragen eine SBOM-Attestation (SPDX). Vor dem Deploy verifizieren:

```bash
cosign verify ghcr.io/martinzeifang/ai_compliance_suite@<digest> \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity-regexp '^https://github.com/martinzeifang/AI_Compliance_Suite/.*'

# SBOM-Attestation prüfen:
cosign verify-attestation --type spdxjson ghcr.io/martinzeifang/ai_compliance_suite@<digest> \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity-regexp '^https://github.com/martinzeifang/AI_Compliance_Suite/.*'
```

## Update-/Rotationsprozess

1. Neue Version bauen + signieren (CI auf Tag `vX.Y.Z`).
2. Digest aus GHCR auflösen + cosign verifizieren (s. o.).
3. `AICS_IMAGE_TAG`/Digest im Prod-`.env` setzen, Drittanbieter-Digests aktualisieren.
4. `docker compose … -f docker-compose.prod.yml up -d` (rolling).
5. Watchtower aktualisiert im Prod-Profil **nur** unkritische Sidecars (kein App-/nginx-Auto-Update;
   die werden release-gesteuert deployt — siehe Deploy-Doku).

## Gotenberg / `SYS_ADMIN` — Risikoakzeptanz

`aics_gotenberg` läuft mit `cap_drop: ALL` und exakt einem zurückgegebenen Capability:
**`SYS_ADMIN`**. Das ist für die Chromium-Sandbox (PDF-Rendering) zwingend; Gotenberg
unterstützt sonst nur den unsichereren `--no-sandbox`-Modus. Zusätzliche Eingrenzung:

- `security_opt: no-new-privileges:true`, kein Port-Publish (nur internes `app-network`,
  `expose: 3000`), eigener Sidecar ohne Zugriff auf die App-Volumes.
- **Rest-Risiko akzeptiert:** SYS_ADMIN bleibt erforderlich. Mitigation: Isolation im
  internen Netz, minimale sonstige Rechte, gepinntes Image, kein Daten-Volume.
- Optionale Verschärfung (Backlog): eigenes seccomp-Profil statt SYS_ADMIN evaluieren.
