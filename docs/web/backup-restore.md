# Sicherung und Wiederherstellung

Die Suite sichert ihre Installation vollständig: die Datenbank, alle
hochgeladenen und erzeugten Dateien und die Konfiguration. Aus einer solchen
Sicherung lässt sich die Installation auf einem frischen Server wieder
aufbauen.

!!! warning "Archive aus Versionen bis 8.0.4"
    Ältere Archive enthalten nur die Dateien `data/db/*.sqlite` — Reste aus der
    Zeit vor der Umstellung auf PostgreSQL. Sie lassen sich weiterhin einspielen,
    stellen den Datenbestand aber **nicht** wieder her. In der Liste sind sie als
    „altes Format — ohne Datenbank" gekennzeichnet, und der
    Wiederherstellungs-Dialog sagt es noch einmal, bevor man bestätigt.

## Was gesichert wird

| Bereich | Inhalt |
|---|---|
| Datenbank | alle Schemata, Tabellen, Zeilen und Sequenzstände |
| Dateien | alles unter `data/` — Word-Vorlagen, Gutachten-Exporte, Nachweis-Store, Konformitätsnachweise, DSGVO-Jahresberichte und Kontroll-Anhänge, SBOM-Dateien, Handbuch, Zertifikate, Lizenzdatei |
| Konfiguration | `ai_compliance_suite.config.json` und die Modul-Konfigurationen |

Nicht gesichert werden Arbeitsdateien unter `data/tmp/` und Zwischenspeicher.
Die Auswahl ist eine Ausschlussliste: Legt ein neues Modul Dateien unter `data/`
ab, sind sie von sich aus mit gesichert.

!!! danger "Das Archiv ist vertraulich"
    Es enthält die Benutzertabelle, private Schlüssel aus `data/certs` und alle
    Mandantendaten. Jeder Download wird im Revisionspfad vermerkt
    (`admin.backup.downloaded`, mit Benutzerkennung). Die Datei gehört an einen
    Ort außerhalb dieses Servers — eine Sicherung auf demselben Volume wie die
    Daten hilft gegen deren Verlust nicht.

## Bedienung

**Administration → Backup-Verwaltung** (Berechtigung `admin:config`).

- **Neue Sicherung erstellen** — schreibt ein Archiv in `out/backup/`. Bei
  großen Installationen dauert das einige Minuten.
- **Herunterladen** — holt das Archiv auf den eigenen Rechner.
- **Archiv hochladen** — nimmt eine extern aufbewahrte Sicherung wieder an
  (Obergrenze über `backup.max_upload_mb`, Standard 4096 MB).
- **Wiederherstellen** — zeigt zuerst, was im Archiv steckt, und spielt es nach
  Bestätigung ein.

### Automatische Sicherung

Standardmäßig läuft jede Nacht um 02:00 UTC eine vollständige Sicherung. Sie
heißt `backup_<datum>_<zeit>_auto.zip`.

```json
{
  "backup": {
    "schedule_enabled": true,
    "schedule_cron": "0 2 * * *",
    "backup_retention_count": 5,
    "max_upload_mb": 4096
  }
}
```

`backup_retention_count` begrenzt die Zahl der aufbewahrten Sicherungen.
Sicherheitskopien, die vor einer Wiederherstellung entstehen
(`pre_restore_*`), zählen nicht mit — sie sind der Rückweg aus einem
misslungenen Restore.

!!! warning "Archive aus fremder Hand"
    Ein Archiv enthält neben den Daten auch Strukturangaben — Vorgabewerte,
    Constraints, Indizes —, die beim Einspielen ausgeführt werden, soweit die
    Zielinstallation die betreffende Tabelle noch nicht hat. Namen von Schemata,
    Tabellen und Spalten werden streng geprüft, und Angaben mit mehreren
    Anweisungen werden abgelehnt; die Ausdrücke selbst lassen sich aber nicht
    allgemein prüfen. Spielen Sie nur Archive ein, deren Herkunft Sie kennen.

## Wiederherstellung nach einem Totalverlust

1. Die Suite neu aufsetzen (Compose-Stack starten, siehe
   [Docker-Deployment](deployment.md)). Datenbank und Datenverzeichnis sind leer.
2. Anmelden und unter **Administration → Backup-Verwaltung** das Archiv über
   **Archiv hochladen** einspielen.
3. In der Zeile des Archivs **Wiederherstellen** wählen. Der Dialog zeigt
   Erstellungszeitpunkt, Suite-Version und Umfang; die Angaben gehören geprüft,
   bevor man bestätigt.
4. Nach dem Einspielen die Anwendung **neu starten**, damit alle Arbeitsprozesse
   den wiederhergestellten Stand lesen.

Die Wiederherstellung läuft als eine Transaktion: Entweder steht die Datenbank
anschließend auf dem Stand des Archivs, oder sie ist unverändert. Ein halb
eingespielter Datenbestand kann nicht entstehen.

### Wie das Schema dabei behandelt wird

Das Schema gehört der laufenden Version, nicht dem Archiv. Beim Einspielen legt
zuerst die Anwendung ihre Tabellen an (mit allen Migrationen), anschließend
ergänzt die Wiederherstellung nur, was dabei fehlt. Damit lässt sich eine
Sicherung auch in eine **neuere** Version einspielen — den üblichen Fall, denn
nach einem Verlust installiert man die aktuelle Fassung.

Was dabei auffällt, steht im Bericht nach dem Einspielen:

- *Spalte … aus der Sicherung ergänzt* — die Zielversion kannte eine Spalte
  nicht; ihre Werte wären sonst verloren gegangen.
- *Pflichtangabe … mit dem Vorgabewert gefüllt* — eine Spalte ist seit der
  Sicherung zur Pflicht geworden; eingetragen wird, was die Anwendung bei einem
  neuen Datensatz einträgt.
- *Spalte … gibt es nicht mehr* — seit der Sicherung entfernt, wird übergangen.

Diese Meldungen sind kein Fehler, sondern der Bericht darüber, was zwischen
Sicherungs- und Einspielzeitpunkt am Datenmodell passiert ist.

## Schnittstelle

| Methode | Pfad | Zweck |
|---|---|---|
| `GET` | `/api/admin/backup` | Liste mit Format und Umfang |
| `POST` | `/api/admin/backup` | Sicherung erstellen |
| `GET` | `/api/admin/backup/<id>/inhalt` | Umfang vor dem Einspielen |
| `GET` | `/api/admin/backup/<id>/download` | Archiv herunterladen |
| `POST` | `/api/admin/backup/upload` | Archiv hochladen (`multipart`, Feld `file`) |
| `POST` | `/api/admin/backup/<id>/restore` | Einspielen (`{"confirm": "<id>"}`) |
| `DELETE` | `/api/admin/backup/<id>` | Archiv löschen |

Alle Pfade verlangen die Berechtigung `admin:config`. Erstellen, Herunterladen
und Einspielen schreiben Einträge in den Revisionspfad
(`admin.backup.created`, `…downloaded`, `…restored`).
