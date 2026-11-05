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

## Gruppen (v8.0.4)

Pfad: **`/admin/groups`**. Eine Gruppe bündelt **Rollen und einzelne
Berechtigungen** und gibt sie an ihre Mitglieder weiter — damit steht eine
Rechte-Entscheidung an einer Stelle statt an jedem Konto.

| Feld                  | Typ                  | Beschreibung |
|---|---|---|
| `name`                | string (unique)      | Anzeigename |
| `beschreibung`        | string               | Wofür die Gruppe gedacht ist |
| `roles`               | array<string>        | Rollen, die alle Mitglieder erhalten |
| `extra_permissions`   | array<string>        | zusätzliche Einzelberechtigungen |
| `active`              | bool                 | `false` = Rechte wirken nicht (Mitglieder bleiben) |

**Additiv, nicht einschränkend.** Gruppenrechte kommen zu den eigenen Rollen
hinzu. `allowed_modules` und `allowed_firmen` bleiben am Konto: Das sind
*Whitelists*, also Beschränkungen, die sich schneiden müssten, während Rollen
sich vereinigen. Eine Gruppe, die den Zugriff auf zwei Mandanten begrenzen soll,
würde ein Konto ohne Whitelist nicht begrenzen, sondern alles offen lassen —
deshalb gibt es das hier bewusst nicht.

**Eine Rechteänderung meldet die Mitglieder ab.** Berechtigungen stehen im JWT
(siehe „JWT-Inhalt"), nicht in einer Abfrage je Request. Wird die Gruppe geändert
oder gelöscht oder eine Mitgliedschaft angefasst, steigt die `token_version` der
betroffenen Konten (#738) — sie müssen sich neu anmelden. Genau so wirkt ein
entzogenes Recht sofort; ein Recht, das bis zum Ablauf des Tokens weitergilt,
wäre in einem Nachweiswerkzeug der schlechtere Tausch. Die Antwort nennt die Zahl
der abgemeldeten Mitglieder.

**Die Gruppe schreibt nichts in das Konto.** In der Benutzerverwaltung bleiben
`roles` die eigenen Rollen; die Gruppen stehen in der Spalte „Gruppen" und ihre
Rechte in `effective_permissions`. Würde das Formular die Vereinigung
zurückspeichern, blieben Gruppenrollen beim Verlassen der Gruppe stehen.

| Endpoint | Zweck |
|---|---|
| `GET/POST /api/admin/groups` | Liste / anlegen |
| `GET/PUT/DELETE /api/admin/groups/<id>` | lesen / ändern / löschen |
| `POST /api/admin/groups/<id>/members` | Konto aufnehmen (`{"user_id": …}`) |
| `DELETE /api/admin/groups/<id>/members/<user_id>` | Konto entfernen |
| `PUT /api/admin/users/<id>` mit `gruppen: [ids]` | Zuordnung aus dem Benutzerformular |
| `GET/POST /api/admin/groups/vorschlaege` | Standardgruppen ansehen / ausgewählte anlegen |

Alles verlangt `admin:users` — Gruppen vergeben Rechte, also dieselbe
Berechtigung wie die Benutzerverwaltung. Änderungen stehen im Audit-Trail
(`admin.group.created|updated|deleted|member_added|member_removed|membership_changed`).

Unbekannte Rollen und Berechtigungen werden abgelehnt (400): `resolve_permissions`
überspringt sie stillschweigend, eine vertippte Rolle wäre also eine Gruppe, die
sichtbar Rechte verspricht und keine gibt.

### Standardgruppen (Vorschläge)

Der Knopf „📋 Standardgruppen anlegen…" zeigt fünf Zuschnitte, die sich in der
Praxis wiederholen — **angelegt wird nur, was man auswählt**. Automatisch
angelegte Gruppen gibt es bewusst nicht: Eine Gruppe mit Rechten, die niemand
vergeben hat, ist eine stehende Rechtevergabe ohne Entscheider, und eine frische
Installation kennt den Zuschnitt des Hauses nicht.

| Gruppe | Rollen | Wofür |
|---|---|---|
| Mandantenbetreuung | firmen, cra, nis2, aiact, dsgvo, wiba, risikobewertung (je Editor) | Führt einen Mandanten fachlich über alle Module; über `firmen:*` auch die Pentest-Berichte. Ohne Freigabe, ohne Administration. |
| Produktteam / Entwicklung | cra_editor, risikobewertung_editor | Reicht Release-Vorgänge ein, gibt sie nicht frei. |
| Compliance-Freigabe | cra_approver, aiact_approver | Die Gegenseite der Vier-Augen-Trennung, bewusst ohne Schreibrecht. |
| Geschäftsführung | geschaeftsfuehrer, viewer | Liest mit, gibt den DSGVO-Jahresbericht frei. |
| Datenschutz | dsb, wiba_editor, risikobewertung_editor | DSFA läuft über ein verknüpftes RB-Projekt, TOM hängen an den WiBA-Prüffragen. |

Der Katalog ist kurz, weil eine Gruppe mit genau **einer** Rolle nichts bringt —
sie ist ein zweiter Name für dieselbe Sache. Ein zweiter Lauf legt nichts doppelt
an und überschreibt eine vorhandene Gruppe **nie**: Sie kann längst angepasst
worden sein.

### Vier-Augen-Prinzip: niemand leistet beide Unterschriften

Die Trennung wirkt an der **Handlung**, nicht an der Rechtevergabe. Wer beide
Rechte hält, ist in kleinen Häusern der Normalfall; unzulässig ist, dass dieselbe
Person beide Unterschriften unter denselben Vorgang setzt. `shared/vier_augen.py`
ist die einzige Stelle, an der diese Regel steht:

| Strecke | Erste Unterschrift | Zweite Unterschrift |
|---|---|---|
| CRA-Release-Vorgang | einreichen (`cra:write`) | freigeben (`cra:approve`) |
| AI-Act-Änderung | einreichen (`aiact:write`) | freigeben (`aiact:approve`) |
| DSGVO-Jahresbericht | Freigabe (`dsgvo:approve`, GF) | Signatur (`dsgvo:sign`, DSB) |

Der zweite Schritt antwortet mit **409** und benennt die Handlung, wenn ihn
dieselbe Benutzer-ID auslösen will. Verglichen wird die ID, nicht der
Anzeigename — Namen sind nicht eindeutig und ändern sich. Ist die erste
Unterschrift nicht zugeordnet (Altbestand vor Einführung der Felder), bleibt die
zweite möglich: Eine Sperre, die niemand auflösen kann, würde Bestandsvorgänge
dauerhaft blockieren.

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
