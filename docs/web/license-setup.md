# Lizenz-Setup (Operator-Handbuch)

Die AI Compliance Suite läuft im **Mietmodell**: jede Installation aktiviert
sich gegen den zentralen Lizenzserver `aics-licensing`. Dieses Dokument
beschreibt das Setup auf Operator-Seite.

## 1. Lizenzserver kennen

Der Lizenzserver läuft typischerweise unter `https://lic.example.de:8444`.
Public-Key + Server-URL sind in `shared/licensing/config.py` fest eingebrannt.

Per Default geht der Client auf `https://192.168.20.10:8444` — Override via:

```
AICS_LICENSE_SERVER_URL=https://lic.example.de:8444
AICS_LICENSE_VERIFY_TLS=true       # Self-Signed in Dev: 'false'
AICS_LICENSE_HEARTBEAT_INTERVAL=21600  # 6 h
```

## 2. Web-App aktivieren

1. Login als Admin
2. → `Admin` → `Lizenz`
3. Lizenzschlüssel einkleben → **Aktivieren**
4. Status-Karte zeigt Plan, Module, Ablauf

### Demo-Lizenz (ohne Schlüssel)

Auf der Aktivierungsseite den Button **Demo (30 Tage)** verwenden — der Server
liefert eine Demo-Lizenz für alle Module zurück.

## 3. Desktop aktivieren

Beim ersten Start der Suite-GUI öffnet sich automatisch der
**Lizenz-Aktivierungs-Dialog**. Optionen:

- **Online aktivieren**: Lizenzschlüssel eingeben → Server-Request
- **Demo (30 Tage)**: ohne Schlüssel
- **Offline aktivieren**: Request-Datei exportieren → an Hersteller schicken
  → erhaltene License-Datei importieren
- **Später**: Suite startet im Read-Only-Modus

Token-Cache liegt unter `data/license.token` (Permission 0600).

## 4. Read-Only-Modus

Wenn keine gültige Lizenz vorhanden ist oder die Lizenz abgelaufen ist:

- **Web**: rotes Banner oben, alle nicht-readonly Module + alle Schreib-Endpunkte
  werden vom Backend mit 423 Locked beantwortet
- **Desktop**: rotes Banner unter Header, license_state.is_read_only() == True

## 5. Offline-Aktivierung (Air-Gap)

Wenn der Lizenzserver nicht erreichbar ist:

1. Im Aktivierungsdialog **Request-Datei exportieren**
2. Datei (`.aicsreq`) an `martin.zeifang@gmail.com` schicken
3. Wir generieren im aics-licensing Admin-UI eine signierte License-Datei
4. Datei (`.aicslic`) zurückspielen → **License-Datei importieren**

Tokens sind Ed25519-signiert; ohne Server-Verbindung kann der Client lokal
verifizieren.

## 6. Heartbeat / Renewal

Web + Desktop senden alle 6 h einen Heartbeat. Der Server kann den Token
verlängern (gleichen Token zurück oder neuen Token signieren). Bei Verlust
der Server-Verbindung gilt **grace_until** im Token (default 7 Tage).

## 7. Modul-Einschränkung

Lizenz kann auf bestimmte Module beschränkt sein (z. B. nur CRA + Risikobewertung).
Die Suite blendet alle nicht-erlaubten Tabs aus. Web: gleichermaßen, der
`sidebar.visibleModules`-Filter berücksichtigt `license_modules`.

## 8. Troubleshooting

| Symptom | Ursache | Lösung |
|---------|---------|--------|
| Banner: „Keine Lizenz aktiv" | Cache leer / abgelaufen | Re-Aktivieren via Admin → Lizenz |
| Banner: „Lizenz läuft in N Tagen ab" | Ablauf naht | Verlängerung beim Vertrieb anfordern |
| Modul-Tab fehlt | Lizenz erlaubt Modul nicht | Lizenz-Upgrade nötig |
| HTTP 423 beim Speichern | Read-Only-Mode | Lizenz aktivieren |
| Aktivierung schlägt fehl | Server-Verbindung / TLS-Issue | `AICS_LICENSE_VERIFY_TLS=false` oder Server-URL prüfen |

## Referenzen

- [Ollama-Setup](ollama-setup.md)
- [Benutzerverwaltung](user-management.md)
- Lizenzserver-Repo: [aics-licensing](https://github.com/martinzeifang/aics-licensing)
