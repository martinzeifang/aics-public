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
    Es enthält die Benutzertabelle, alle Mandantendaten, private Schlüssel aus
    `data/certs` und die Schlüsseldateien der Installation (`.jwt-secret`,
    `.fingerprint-seed`). Letztere gehören dazu, weil ohne sie die at-rest
    verschlüsselten Zugangsdaten — GitHub-Token, Portainer-Schlüssel — nach einer
    Wiederherstellung nicht mehr lesbar wären. Wer das Archiv hat, hat damit
    faktisch die Installation. Jeder Download wird im Revisionspfad vermerkt
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
- **Übernehmen** — fügt die Mandanten eines fremden Archivs **hinzu**, ohne den
  eigenen Bestand anzutasten (siehe unten).

## Übernehmen ist nicht Wiederherstellen

Die beiden Knöpfe tun Gegenteiliges, und die Verwechslung hat einmal Daten
gekostet:

| | Wiederherstellen | Übernehmen |
|---|---|---|
| Zweck | Wiederanlauf nach einem Verlust | Daten einer anderen Installation holen |
| Vorhandene Daten | werden **ersetzt** | bleiben unberührt |
| Auswahl | ganzes Archiv | je Mandant |
| Sicherheitskopie | wird vorher angelegt | nur beim *Ersetzen* — sonst geht nichts verloren |

Aus dem Betrieb: Ein Archiv der Testinstanz wurde auf der Produktivinstallation
**wiederhergestellt**, in der Erwartung, die Daten kämen dazu. Danach waren elf
von zwölf Mandanten weg. Der Restore leert jede Tabelle, die im Archiv steht;
das Archiv kannte die Mandanten des Ziels nicht.

### Ablauf

1. Archiv der Quellinstallation dort herunterladen und hier **hochladen**.
2. In der Zeile des Archivs **📥 Übernehmen** wählen. Der Dialog listet die
   Mandanten des Archivs mit ihren Projekten und sagt je Zeile, ob es sie hier
   schon gibt. Vorausgewählt ist, was hier fehlt.
3. **Probelauf** rechnet alles durch und schreibt nichts — dieselben Zahlen,
   ohne Wirkung.
4. **Übernehmen** fügt ein.

### Entscheidungen, die der Dialog stellt

- **Namensgleichstand.** Gibt es einen ausgewählten Mandanten hier schon, wird
  er standardmäßig **übersprungen** — der hiesige Stand ist eine Aussage.
  *Ersetzen* entfernt die Daten genau dieser Mandanten und fügt die des Archivs
  ein; andere Mandanten sind nicht betroffen. Weil das der einzige Weg ist, auf
  dem hier etwas gelöscht wird, legt der Server davor eine Sicherheitskopie an —
  wie beim Wiederherstellen. Scheitert sie, wird abgebrochen.
- **Benutzerkonten.** Optional. Nötig, damit in übernommenen Vorgängen Namen
  statt roher Kennungen stehen. **Passkeys bleiben zurück** — sie gelten nur für
  die Domain, unter der sie angelegt wurden, und würden hier ein Konto erzeugen,
  das einen zweiten Faktor verlangt, den niemand erfüllen kann. Kennwörter
  vorhandener Konten werden nicht angetastet.
- **Als gelöscht markierte Mandanten.** Deren Zeile bleibt in der Datenbank und
  belegt den Namen. Die Übernahme setzt sie wieder ein und sagt es im Bericht.
- **Dateien kommen mit.** Word-Vorlagen, Nachweisdokumente, finalisierte
  Gutachten, Pentest-Berichte und Kontroll-Anhänge liegen im Archiv und werden
  **ergänzt**. Eine Datei, die hier schon liegt, bleibt unberührt — die
  Dateinamen tragen Prüfsummen, und eine ersetzte Datei passte nicht mehr zum
  SHA-256 im hiesigen Datensatz. Ohne diesen Schritt wäre die Übernahme halb:
  Jeder Download zeigte ins Leere und sähe nach einem Defekt aus.

### Was dabei nicht mitwandert

Revisionspfad und Zeitpläne gehören zu der Installation, auf der gehandelt
wurde. SOC-Betriebsdaten sind Telemetrie dieser Installation und über
Vorgangs-IDs tief verkettet. Kataloge (BSI-WiBA-Prüffragen, Normen,
Framework-Abschnitte) sind Installationsdaten. Der Bericht nennt jede dieser
Positionen mit Grund.

### Warum technische Schlüssel kein Problem sind

Zwischen zwei Installationen bedeutet dieselbe Zahl etwas anderes. Zugeordnet
wird deshalb über den **fachlichen Namen** (`firmen.name`, `projekt_name`), und
alle technischen Schlüssel eines Laufs wandern um **denselben Versatz** — er
liegt über dem höchsten Wert, den das Ziel kennt. Damit bleibt jeder Verweis
innerhalb des Archivs richtig und eine Kollision ist ausgeschlossen. Einzige
Ausnahme ist `firmen_id`: Existiert der Mandant hier schon, muss der Verweis auf
**dessen** Zeile zeigen; diese Zuordnung läuft über den Namen.

Das Einspielen läuft als **eine** Transaktion. Ein halb übernommener Mandant
kann nicht entstehen — er sähe aus wie ein Mandant.

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
| `GET` | `/api/admin/backup/<id>/vorschau` | Was das Einspielen entfernen würde (`?umfang=`) |
| `GET` | `/api/admin/backup/<id>/mandanten` | Mandanten und Projekte im Archiv |
| `POST` | `/api/admin/backup/<id>/uebernehmen` | Mandanten einfügen (`{"mandanten": [...]}`) |
| `GET` | `/api/admin/backup/<id>/download` | Archiv herunterladen |
| `POST` | `/api/admin/backup/upload` | Archiv hochladen (`multipart`, Feld `file`) |
| `POST` | `/api/admin/backup/<id>/restore` | Einspielen (`{"confirm": "<id>"}`) |
| `DELETE` | `/api/admin/backup/<id>` | Archiv löschen |

Alle Pfade verlangen die Berechtigung `admin:config`. Erstellen, Herunterladen,
Einspielen und Übernehmen schreiben Einträge in den Revisionspfad
(`admin.backup.created`, `…downloaded`, `…restored`, `…uebernommen`) — mit dem
Handelnden, dem Umfang und den Zahlen.
