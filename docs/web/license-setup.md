# Lizenz-Setup

Die AI Compliance Suite läuft im **Mietmodell**: jede Installation
aktiviert sich gegen einen Lizenzserver. Dieses Dokument beschreibt
die Aktivierung auf Operator-Seite.

## 1. Lizenzserver

Public-Key + Default-Server-URL sind in `shared/licensing/config.py`
fest eingebrannt. Override per Environment-Variable:

```
AICS_LICENSE_SERVER_URL=https://licensing.example.com:8444
AICS_LICENSE_VERIFY_TLS=true        # Self-Signed-Dev: 'false'
AICS_LICENSE_HEARTBEAT_INTERVAL=21600  # 6 h
```

## 2. Aktivierung

1. Login als Admin
2. → **Admin** → **Lizenz**
3. Lizenzschlüssel einkleben → **Aktivieren**
4. Status-Karte zeigt Plan, Module, Ablauf

### Demo-Lizenz (ohne Schlüssel)

Auf der Aktivierungsseite den Button **Demo (30 Tage)** verwenden — der
Server liefert eine Demo-Lizenz für alle Module zurück.

## 3. Read-Only-Modus

Wenn keine gültige Lizenz vorliegt oder die Lizenz abgelaufen ist,
schaltet die App in den Read-Only-Modus:

- Oben im Header erscheint ein rotes Banner
- Alle Schreib-Endpunkte antworten mit HTTP **423 Locked**
- Daten bleiben lesbar und exportierbar

## 4. Offline-Aktivierung (Air-Gap)

Wenn der Lizenzserver nicht erreichbar ist:

1. Im Aktivierungsdialog **Request-Datei exportieren** (`.aicsreq`)
2. Datei an den Lizenzgeber senden
3. Signierte Lizenz-Datei (`.aicslic`) zurück importieren

Tokens sind Ed25519-signiert; der Client kann lokal verifizieren — kein
Server-Roundtrip erforderlich.

## 5. Heartbeat / Renewal

Die App sendet alle 6 h einen Heartbeat. Der Server kann den Token
verlängern oder einen neuen ausstellen. Bei Verlust der Server-Verbindung
gilt das **grace_until**-Feld im Token (default 7 Tage).

## 6. Modul-Einschränkung

Lizenzen können auf bestimmte Module beschränkt sein (z. B. nur
CRA + Risikobewertung). Die Sidebar blendet alle nicht-erlaubten
Tabs aus.

## 7. Troubleshooting

| Symptom | Ursache | Lösung |
|---------|---------|--------|
| Banner „Keine Lizenz aktiv" | Cache leer / abgelaufen | Re-Aktivieren via Admin → Lizenz |
| Banner „Lizenz läuft in N Tagen ab" | Ablauf naht | Verlängerung anfordern |
| Modul-Tab fehlt | Lizenz erlaubt Modul nicht | Lizenz-Upgrade nötig |
| HTTP 423 beim Speichern | Read-Only-Mode | Lizenz aktivieren |
| Aktivierung schlägt fehl | TLS-/Verbindungsproblem | `AICS_LICENSE_VERIFY_TLS=false` oder Server-URL prüfen |

## Referenzen

- [Ollama-Setup](ollama-setup.md)
- [Benutzerverwaltung](user-management.md)
