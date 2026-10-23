# Zwei-Faktor-Authentifizierung (2FA / TOTP)

Pfad in der App: **👤 Benutzer-Menü → 🔐 Sicherheit (2FA)** (`/account/security`)

Die AI Compliance Suite unterstützt **Time-based One-Time Passwords**
(TOTP, RFC 6238) als zweite Faktor neben Email/Passwort. Funktioniert mit
allen gängigen Authenticator-Apps:

- Google Authenticator
- Authy
- 1Password / Bitwarden / KeePassXC
- Microsoft Authenticator
- Aegis (Android)

---

## Einrichtung

1. **Anmelden** → Klick auf das Benutzer-Icon oben rechts → **🔐 Sicherheit (2FA)**
2. **„2FA einrichten"** klicken
3. **QR-Code mit der App scannen** (oder Secret manuell eintippen)
4. Den von der App angezeigten **6-stelligen Code eingeben** → **Bestätigen**
5. **Backup-Codes sichern** (Download als Datei oder Kopieren)

!!! warning "Backup-Codes nur einmal sichtbar"
    Nach dem Bestätigen werden 10 einmalig gültige Backup-Codes
    angezeigt. Diese **können später nicht erneut eingesehen werden**.
    Bewahren Sie die Codes an einem sicheren Ort auf
    (Passwort-Manager, Tresor-Notiz, ausgedruckt).
    Wenn Sie alle Backup-Codes und Ihre Authenticator-App verlieren,
    muss ein Admin Ihren Account zurücksetzen.

---

## Anmeldung mit aktivem 2FA

1. Email + Passwort eingeben → **Anmelden**
2. Es erscheint eine zweite Eingabe: **6-stelliger Code** aus der App
   (oder ein Backup-Code im Format `XXXX-XXXX`)
3. **Bestätigen & anmelden**

Der „Challenge-Token" zwischen den beiden Schritten läuft nach **5 Minuten** ab.
Wer länger braucht, wechselt zurück mit **„← Zurück zur Anmeldung"**.

---

## Backup-Codes

- **10 Codes** im Format `XXXX-XXXX` (8 Hex-Zeichen)
- **Einmalig gültig** — nach Verwendung gelöscht
- Im **Sicherheit**-Dialog sichtbar wieviele noch übrig sind
- **Neu erzeugen** möglich; alle alten werden dabei ungültig
  (erfordert aktuellen TOTP-Code)

---

## 2FA deaktivieren

**🔐 Sicherheit (2FA) → 2FA deaktivieren**

Erfordert:

- Aktuelles **Passwort**
- Aktueller **TOTP-Code** (oder Backup-Code)

Damit werden Secret und Backup-Codes gelöscht.

---

## Endpoints (für API-Clients)

Alle Endpoints erfordern einen Bearer-Token (Login). 2FA-Setup-Endpoints
verändern den eigenen Account des authentifizierten Users.

| Methode | Pfad | Zweck |
|---|---|---|
| `GET`  | `/api/auth/2fa/status` | Status: enabled, backup_codes_remaining |
| `POST` | `/api/auth/2fa/setup` | Neues Secret + QR-Code anfordern |
| `POST` | `/api/auth/2fa/verify` | Setup bestätigen, gibt Backup-Codes zurück |
| `POST` | `/api/auth/2fa/disable` | 2FA aus (Body: `password`, `code`) |
| `POST` | `/api/auth/2fa/regenerate-backup-codes` | Neue Backup-Codes |
| `POST` | `/api/auth/login` | Schritt 1 — bei 2FA: gibt `challenge_token` zurück |
| `POST` | `/api/auth/login/verify-2fa` | Schritt 2 — tauscht challenge + code → `access_token` |

### Beispiel-Flow (curl)

```bash
# Schritt 1
RESP=$(curl -sk -X POST https://localhost:5000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"admin-password"}')

CHAL=$(echo "$RESP" | jq -r .challenge_token)

# Schritt 2 (TOTP-Code aus der App):
curl -sk -X POST https://localhost:5000/api/auth/login/verify-2fa \
  -H 'Content-Type: application/json' \
  -d "{\"challenge_token\":\"$CHAL\",\"code\":\"123456\"}"
```

---

## Sicherheitseigenschaften

- **Secret-Länge:** 160 Bit Base32 (Standard für SHA-1-TOTP)
- **Drift-Toleranz:** ±30 s (`valid_window=1`)
- **Backup-Codes:** kryptografisch zufällig (`secrets.token_hex`),
  gespeichert als **PBKDF2-Hashes** (gleiche Funktion wie Passwörter)
- **Challenge-Token:** signiertes JWT, 5 min TTL, kann nur für den
  einen User verwendet werden, dessen 1.-Schritt-Login erfolgreich war
- **LDAP-User:** 2FA in dieser App nicht erzwingbar (verwende die
  LDAP-/SSO-eigene MFA-Mechanismen des Identity-Providers)
- **Brute-Force-Schutz:** Account-Lockout greift auch bei wiederholt
  falschen Codes (gleiche `failed_login_count`-Logik wie Passwort)

---

## Troubleshooting

### „Code ungültig oder abgelaufen"

- Uhr von Server und Authenticator-Gerät müssen synchron sein
  (Drift > 30 s führt zu Ablehnung)
- Code ggf. neu in der App ablesen (ändert sich alle 30 s)
- Bei wiederholten Fehlern: einen **Backup-Code** verwenden

### Handy verloren, keine Backup-Codes mehr

→ Ein Admin muss den Account zurücksetzen:

```bash
docker compose exec web python3 -c "
from server.auth.users_db import disable_totp
disable_totp('USER_ID_HIER')
print('2FA disabled')
"
```

Anschließend kann der User normal mit Passwort einloggen und 2FA neu einrichten.

### Backup-Codes verloren, aber Authenticator-App noch da

In **Sicherheit (2FA) → „Neue Backup-Codes erzeugen"** mit aktuellem TOTP-Code
bestätigen — die alten Codes werden ungültig, 10 neue werden angezeigt.

---

## Empfehlung für Production

In `docs/web/deployment.md` Hardening-Checkliste empfohlen:

- [ ] Für alle Admin-Konten 2FA verpflichtend
- [ ] Backup-Codes außerhalb der App (Passwort-Manager) gesichert
- [ ] Wiederherstellungs-Prozess (Admin-Reset) intern dokumentiert
