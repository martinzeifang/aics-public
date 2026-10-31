# Passkeys (WebAuthn/FIDO2) & Mehr-Faktor-Authentifizierung (MFA)

Sprint ε. Dieses Dokument beschreibt Einrichtung, Konfiguration und Betrieb der
Passkey- und MFA-Funktionen der Web-Anwendung.

## Überblick

Die Web-Anwendung unterstützt zwei MFA-Methoden, die jeder Benutzer im
Self-Service unter **Konto → Sicherheit** aktivieren kann:

| Methode | Beschreibung |
|---------|--------------|
| **TOTP** | 6-stelliger Code aus einer Authenticator-App (Google Authenticator, Authy, 1Password) + Backup-Codes |
| **Passkey** | WebAuthn/FIDO2 — Fingerabdruck, Gesichtserkennung, Geräte-PIN oder Sicherheitsschlüssel |

Passkeys können:
- **passwortlos** zum Login verwendet werden (Button „Mit Passkey anmelden"), und
- als **zweiter Faktor** nach Email+Passwort dienen.

> **Scope:** Passkeys sind eine reine Browser-/Plattform-Technik und nur in der
> **Web-Anwendung** verfügbar. Die **Desktop-GUI (Tkinter)** bleibt bei
> Passwort + TOTP.

## Konfiguration (RP-ID / Origin)

WebAuthn bindet Credentials an die **Relying-Party-ID (RP-ID)** = die
registrierbare Domain **ohne** Schema/Port. Origin = die vollständige
https-Adresse. Diese Werte **müssen** zur ausliefernden Domain passen — sonst
verweigert der Browser die Passkey-Nutzung **stillschweigend** (kein Fehler,
nur „funktioniert nicht").

### Empfohlen: über die Weboberfläche

**Admin → Einstellungen → „Passkey / WebAuthn"** — RP-ID, RP-Name und Origin
eintragen und speichern. Kein Eingriff in Config-Files/ENV nötig. Web-Einstellungen
haben **Vorrang vor ENV**.

### Fallback: Umgebungsvariablen

Nur als Bootstrap/Fallback, solange noch nichts über die Web-UI gesetzt wurde
(siehe `.env.example`):

```bash
WEBAUTHN_RP_ID=localhost                  # registrierbare Domain, OHNE Schema/Port
WEBAUTHN_RP_NAME=AI Compliance Suite      # Anzeigename im Authenticator
WEBAUTHN_RP_ORIGIN=https://localhost:8443 # vollständige Origin(s), komma-separiert
```

Priorität: **Web-Einstellungen (`auth.webauthn`) > ENV-Variablen > Defaults.**

### Beispiele

| Deployment | RP_ID | RP_ORIGIN |
|------------|-------|-----------|
| Lokal (Dev) | `localhost` | `https://localhost:8443` |
| Produktion | `aics.example.com` | `https://aics.example.com` |
| Subdomain + www | `example.com` | `https://aics.example.com,https://www.example.com` |

Regeln:
- RP_ID muss ein **registrierbares Suffix** der Origin-Domain sein
  (`aics.example.com` darf RP_ID `aics.example.com` **oder** `example.com` nutzen,
  aber **nicht** `example.org`).
- RP_ID enthält **niemals** Schema (`https://`) oder Port (`:8443`).
- Mehrere Origins komma-separiert (z. B. App-Domain + www).

### Hinter (mehrstufigem) Reverse-Proxy

Wird die Anwendung über einen vorgelagerten Proxy unter einem anderen Hostnamen
veröffentlicht (z. B. Browser → `https://app.firma.intern:8443` → Docker
`https://10.0.0.x:9443`), muss das Backend den **echten Browser-Host** erfahren,
sonst leitet es eine falsche RP-ID ab → Fehler
`'rp.id' cannot be used with the current origin`.

Reihenfolge der Ableitung: `Origin`-Header → `X-Forwarded-Host` (+`X-Forwarded-Proto`)
→ `Host`. Der vorgelagerte Proxy sollte daher mindestens setzen:
```nginx
proxy_set_header X-Forwarded-Host  $host;
proxy_set_header X-Forwarded-Proto $scheme;
# (Origin wird, falls vom Client gesendet, ohnehin durchgereicht)
```
**Am robustesten:** RP-ID/Origin **explizit** unter Admin → Einstellungen →
„Passkey / WebAuthn" setzen — das überschreibt jede Ableitung, unabhängig vom Proxy.

**Diagnose:** `GET /api/auth/webauthn/debug` (admin) zeigt die effektive RP-ID/Origin
und die tatsächlich empfangenen Header (`Origin`, `Host`, `X-Forwarded-Host`).

### Hinter Nginx (TLS-Termination)

Wenn Nginx TLS terminiert und an das Flask-Backend weiterleitet:
- `WEBAUTHN_RP_ORIGIN` = **öffentliche** https-Adresse (die der Browser sieht),
  **nicht** die interne `http://backend:5000`.
- Nginx muss `X-Forwarded-For` / `X-Real-IP` durchreichen (für Rate-Limiting +
  Audit-IP). Beispiel:
  ```nginx
  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;
  ```
- WebAuthn erfordert einen **sicheren Kontext** (HTTPS). Ausnahme: `localhost`
  funktioniert auch über http (Browser-Sonderregel für Entwicklung).

## MFA-Richtlinie (Admin)

Unter **Admin → Einstellungen → MFA-Richtlinie** lässt sich MFA verpflichtend
machen:

| Modus | Wirkung |
|-------|---------|
| `optional` | Jeder kann MFA selbst aktivieren (Default) |
| `required_all` | MFA-Pflicht für alle Benutzer |
| `required_roles` | MFA-Pflicht für ausgewählte Rollen |

**Grace-Period:** Betroffene Benutzer ohne MFA erhalten eine Frist (Tage), die
beim ersten Login unter Policy gesetzt wird. Innerhalb der Frist wird die
Einrichtung **empfohlen** (Banner). Nach Ablauf wird sie **erzwungen**: Der
Login bleibt möglich (kein Lockout), das Frontend leitet aber zwingend nach
**Konto → Sicherheit**, bis eine Methode eingerichtet ist.

Persistenz: Suite-Config unter `auth.mfa_policy`. Grace-Ende pro User in
`users.mfa_grace_until`.

## API-Endpoints

Alle unter `/api/auth/webauthn`:

| Methode | Pfad | Auth | Zweck |
|---------|------|------|-------|
| POST | `/register/options` | JWT | Optionen für Registrierung |
| POST | `/register/verify` | JWT | Passkey speichern |
| GET | `/credentials` | JWT | Eigene Passkeys auflisten |
| PATCH | `/credentials/<id>` | JWT | Passkey umbenennen |
| DELETE | `/credentials/<id>` | JWT | Passkey entfernen |
| POST | `/login/options` | — | Passwortlos: Optionen (discoverable) |
| POST | `/login/verify` | — | Passwortlos: Assertion → Access-Token |
| POST | `/login/2fa-options` | — | Passkey als 2. Faktor: Optionen |
| POST | `/login/2fa-verify` | — | Passkey als 2. Faktor: → Access-Token |

MFA-Policy (Admin, Permission `admin:config`):
`GET/PUT /api/admin/mfa-policy`.

## Sicherheit

- **Challenges** sind serverseitig, ephemer (5 min), single-use (`webauthn_challenges`).
- **sign_count-Replay-Schutz:** Ein neuer Zählerstand muss größer als der
  gespeicherte sein (sonst 401 „möglicher Replay").
- **Rate-Limiting:** Unauthentifizierte Login-Endpoints sind pro Client-IP
  limitiert (20 Versuche / 5 min → HTTP 429).
- **Public-Keys** werden nie über die API ausgeliefert (nur Metadaten).
- **Audit-Events** (`shared.audit`): `passkey.registered`, `passkey.deleted`,
  `passkey.login` (success/fail, mode=passwordless|2fa), `mfa.totp.enabled`,
  `mfa.totp.disabled`, `mfa.policy.changed`.

## Datenbank

`users.sqlite`:
- `webauthn_credentials` (credential_id UNIQUE, public_key, sign_count,
  transports, aaguid, nickname, backup_eligible/state, last_used_at)
- `webauthn_challenges` (challenge_id, user_id, challenge, typ, expires_at)
- `users.mfa_grace_until` (Unix-ts, MFA-Enforcement-Grace)

## Troubleshooting

| Symptom | Ursache / Lösung |
|---------|------------------|
| „Mit Passkey anmelden" tut nichts / bricht ab | RP_ID/Origin passt nicht zur Domain → `WEBAUTHN_RP_ID`/`WEBAUTHN_RP_ORIGIN` prüfen |
| Registrierung schlägt fehl (kein Prompt) | Kein sicherer Kontext (HTTPS) — außer `localhost` |
| 401 „möglicher Replay" | Authenticator-Klon oder zurückgesetzter Zähler; Passkey neu registrieren |
| 429 Too many attempts | Rate-Limit; 5 min warten |
| Passkey-Button fehlt | Browser ohne WebAuthn-Support oder kein HTTPS |
| Login fordert nach Grace immer Security-Seite | MFA-Policy verlangt MFA; Methode unter Konto → Sicherheit einrichten |

## Abhängigkeiten

- Backend: `webauthn` (py_webauthn), `pyotp`, `qrcode`
- Frontend: `@simplewebauthn/browser`
