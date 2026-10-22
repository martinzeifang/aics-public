# Benutzerverwaltung

Pfad: **`/admin/users`** (nur für Rolle `admin` sichtbar)

Die Benutzerverwaltung steuert, **wer** sich anmelden darf, **was**
ein Benutzer sehen darf (Module) und **was** er tun darf (Permissions).

## Datenmodell

Ein Benutzer hat folgende Felder:

| Feld                  | Typ                  | Beschreibung |
|---|---|---|
| `email`               | string (unique)      | Login-Identifikator |
| `password_hash`       | string (scrypt)      | Werkzeug-generated, nie im Klartext |
| `display_name`        | string               | Anzeigename (optional) |
| `roles`               | array<string>        | Eine oder mehrere Rollen (siehe unten) |
| `allowed_modules`     | array<string> \| null| Whitelist sichtbarer Module. `null` = alle aus Rollen |
| `extra_permissions`   | array<string>        | Zusätzliche Permissions jenseits der Rolle |
| `active`              | bool                 | `false` = Login gesperrt |

## Rollen

Rollen sind Präsets von Permissions. Ein Benutzer kann **mehrere** Rollen haben
(additiv).

### Übergreifende Rollen

| Rolle          | Beschreibung |
|---|---|
| `admin`        | **Alle** Permissions (Modul + Admin) |
| `editor`       | Lesen + Schreiben + Export auf alle Module |
| `viewer`       | Nur-Lese auf alle Module |
| `auditor`      | `viewer` + `admin:audit` |

### Modul-spezifische Rollen

Pro Modul gibt es eine `<modul>_editor`-Rolle, z.B.:

- `cra_editor`, `cra_viewer`
- `nis2_editor`
- `dora_editor`
- `aiact_editor`
- `dsgvo_editor`
- `gutachten_editor`
- `risikobewertung_editor`
- `firmen_editor`

## Permissions

Pro Modul gibt es typischerweise drei Permissions:

| Permission                          | Bedeutung |
|---|---|
| `<module>:read`                     | Anforderungen + Bewertungen einsehen |
| `<module>:write`                    | Bewertungen anlegen / ändern |
| `<module>:export`                   | PDF/DOCX/XLSX-Reports erzeugen |

Modul-spezifische Permissions:

| Permission                      | Modul     | Bedeutung |
|---|---|---|
| `cra:prefill`                   | CRA       | KI-Vorbefüllung von Bewertungen |
| `cra:issue_link`                | CRA       | GitHub-/GitLab-Issues verknüpfen |
| `gutachten:frameworks`          | Gutachten | Framework-Bibliothek (Download/Ingest) |

Admin-Permissions:

| Permission        | Bedeutung |
|---|---|
| `admin:users`     | Benutzerverwaltung |
| `admin:roles`     | Rollen verwalten (Reserve) |
| `admin:audit`     | Audit-Log einsehen |
| `admin:config`    | Konfiguration / Framework-Bibliothek |

## Modul-Sichtbarkeit (`allowed_modules`)

Standardmäßig sieht ein Benutzer **alle** Module, für die er aufgrund
seiner Rollen mindestens eine `:read`-Permission hat.

Mit `allowed_modules` (Whitelist) lässt sich das **einschränken**:

| `allowed_modules` | Effekt |
|---|---|
| `null` (Standard) | Alle Module aus Rollen sichtbar |
| `["cra", "nis2"]` | Nur CRA und NIS2 sichtbar — auch wenn Rolle mehr erlaubt |
| `[]` (leer) | Keine Module sichtbar (nur Login möglich) |

Beispiel: Ein Admin, der die Suite verwaltet, aber nur DSGVO-Bearbeitung machen
soll, bekommt Rolle `admin` + `allowed_modules: ["dsgvo"]`.

## Effektive Permissions

Die im JWT eingebetteten effektiven Permissions ergeben sich aus:

```python
effective = (
    permissions_from_roles(user.roles)
  ∪ user.extra_permissions
)
```

Sie werden über das **Admin-Bearbeiten**-Modal in der Sektion
"**Effektive Permissions**" angezeigt.

## Workflow „Neuer Benutzer"

1. **Admin → 👥 Benutzerverwaltung → "+ Neuer Benutzer"**
2. E-Mail, Anzeigename, Passwort (≥ 8 Zeichen)
3. **Rollen** wählen (z.B. `dsgvo_editor` + `gutachten_editor`)
4. **Sichtbare Module**:
   - Standard: "Alle Module aus Rolle automatisch freischalten"
   - Oder Whitelist setzen
5. **Zusätzliche Permissions** (optional, z.B. `admin:audit` für reinen
   Audit-Zugriff)
6. **Aktiv** anhaken
7. Speichern

## API-Endpoints

| Endpoint                                  | Methode | Permission     |
|---|---|---|
| `/api/admin/users`                        | GET     | `admin:users`  |
| `/api/admin/users/<id>`                   | GET     | `admin:users`  |
| `/api/admin/users`                        | POST    | `admin:users`  |
| `/api/admin/users/<id>`                   | PUT     | `admin:users`  |
| `/api/admin/users/<id>`                   | DELETE  | `admin:users`  |
| `/api/admin/users/<id>/disable`           | POST    | `admin:users`  |
| `/api/admin/permissions/catalog`          | GET     | `admin:users`  |

`/permissions/catalog` liefert die UI-Datenstruktur:
- alle Module mit Modul-Permissions (für Checkbox-Grids)
- alle Rollen mit ihren Permission-Listen
- alle Admin-Permissions (separat)

## JWT-Inhalt

Nach erfolgreichem Login enthält der JWT-Identity-Block:

```json
{
  "user_id": "user-001",
  "email": "admin@example.com",
  "roles": ["admin"],
  "permissions": ["cra:read", "cra:write", "..."],
  "extra_permissions": [],
  "allowed_modules": null,
  "display_name": "Max Mustermann"
}
```

Permission-Checks im Backend nutzen `@require_permission('module:action')`,
das sowohl Rollen-Permissions als auch `extra_permissions` berücksichtigt.

## Demo-Benutzer

Im Dev-Modus (`ENABLE_DEMO_USERS=true`) werden zwei Default-User angelegt:

| E-Mail                  | Passwort         | Rollen          |
|---|---|---|
| admin@example.com       | admin-password   | `admin`         |
| editor@example.com      | editor-password  | `cra_editor`    |
