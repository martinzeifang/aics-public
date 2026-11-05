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

## Verschlüsselung der Archive

Eine Sicherung ist ein **vollständiger Abzug** des Datenbestands — alle
Mandanten, alle Nachweisdokumente, die Benutzertabelle, die Konfiguration. Seit
Version 8.3.2 lässt sie sich verschlüsseln, seit 8.3.3 mit dem Schlüssel allein
— **und seit 8.3.4 erreicht der Schlüssel den Container.**

### Einschalten

| Schritt | |
|---|---|
| 1 | `AICS_BACKUP_KEY` in die Stack-Umgebung setzen — ein langes, zufälliges Geheimnis |
| 2 | Den Stack neu ausrollen, damit die Variable im Container ankommt |
| 3 | Im Container nachsehen, dass sie angekommen ist (nur *ob*, nicht *was*) |
| 4 | Eine Probesicherung erzeugen, herunterladen und **außerhalb** entschlüsseln |
| 5 | Den Schlüssel **außerhalb** der Installation verwahren |

Das Setzen des Schlüssels ist die Zustimmung; `encrypt_backups`
steht ohnehin auf `true`. Der Master-Schalter `security.at_rest_encryption.enabled`
wird dafür **nicht** gebraucht.

!!! warning "Schritt 3 ist nicht Zierde — bis 8.3.3 scheiterte genau hier alles"
    Eine Stack-Variable ist die `.env` für die **compose-Interpolation**. In den
    Container kommt ihr Wert nur über eine `environment:`-Zeile in
    `docker-compose.yml` — und für `AICS_BACKUP_KEY` gab es diese Zeile bis
    8.3.3 **nicht**. Folge: Der Schlüssel stand sichtbar im Stack, der Redeploy
    meldete Erfolg, und die nächtliche Sicherung entstand weiter im Klartext.
    Die Verschlüsselung war damit in **keiner** Installation einschaltbar.

    Nachsehen lässt sich das so (die Ausgabe nennt den Wert nicht):

    ```bash
    docker exec <web-container> sh -lc \
      'test -n "$AICS_BACKUP_KEY" && echo gesetzt || echo FEHLT'
    ```

    Steht dort `FEHLT`, obwohl die Variable im Stack steht, läuft eine Fassung
    vor 8.3.4 — oder die Live-Stack-Datei weicht vom Repository ab.

!!! warning "Warum `enabled` hier nicht gebraucht wird"
    Bis 8.3.2 war `enabled` + `encrypt_backups` der einzige Weg — und damit war
    das Einschalten auf einer Bestandsinstallation praktisch unmöglich.
    `enabled` ist der Master-Schalter der **gesamten** At-Rest-Verschlüsselung:
    Er verlangt einen separaten `AICS_AT_REST_KEY` (sonst bricht der
    Produktivstart ab, #1189), und sobald der gesetzt ist, wechselt die
    **Feldverschlüsselung** ihre Schlüsselquelle von `JWT_SECRET_KEY` auf ihn.
    Alle bereits verschlüsselten Felder — gespeicherte Zugangstoken,
    TOTP-Geheimnisse — werden dadurch unlesbar, und zwar ohne Fehlermeldung.

    Für die Sicherungen ist das unnötig: `AICS_BACKUP_KEY` hat keinen Rückfall,
    die Begründung von #1189 trifft auf ihn gar nicht zu. Seit 8.3.3 genügt
    deshalb der Schlüssel allein.

    Wer den Schlüssel in der Umgebung haben will, **ohne** zu verschlüsseln,
    setzt `encrypt_backups: false`.

!!! danger "Der Schlüssel wird nicht mitgesichert — und er hat keinen Rückfall"
    `AICS_BACKUP_KEY` und sonst nichts. **Ausdrücklich kein Rückfall** auf
    `AICS_AT_REST_KEY` oder `JWT_SECRET_KEY`: Wer das Sitzungsgeheimnis
    wechselt, würde sonst nebenbei alle Sicherungen unlesbar machen, und zwar
    lautlos. Dazu liegt ein Schlüssel, der aus der Installation abgeleitet
    wird, mit den Daten im selben Korb.

    **Ohne den Schlüssel ist kein verschlüsseltes Archiv wiederherstellbar.**
    Es gibt keine Hintertür und keine Wiederherstellungsfrage.

### Was passiert, wenn der Schlüssel fehlt

Die Sicherung **scheitert**, und zwar bevor etwas geschrieben wird. Sie
entsteht nicht still im Klartext: Ein unverschlüsseltes Archiv, das für
verschlüsselt gehalten wird, ist schlimmer als ein offen unverschlüsseltes.

### Ein Schlüssel oder einer je Instanz?

**In dieser Installation tragen alle vier Instanzen denselben Schlüssel**
(Dev, Test, Prod, Demo — entschieden am 04.11.2026). Der Grund ist nicht
Bequemlichkeit, sondern der Bedrohungsweg: Den Schlüssel kennt nur der
Betreiber, und es wird **kein** Archiv weitergegeben, auch kein Demo-Archiv.
Damit entfällt der Einwand, der gegen einen gemeinsamen Schlüssel spricht —
dass ein weitergegebenes Demo-Archiv den Produktiv-Schlüssel verrät. Ändert
sich diese Praxis, wird der Schlüssel gewechselt.

Vier eigene Schlüssel wären die vorsichtigere Wahl: Jede Installation ist
dann ein eigener Vertrauensbereich, und ein verlorener Schlüssel kostet nur
eine. Der Preis sind vier Geheimnisse, die über zehn Jahre
auseinanderlaufen können — und ein Archiv, dessen Schlüssel niemand mehr
zuordnen kann, ist so verloren wie eines ohne.

!!! danger "Beim Wechseln: der alte Schlüssel bleibt, solange die Frist läuft"
    **Ein Archiv ist an den Schlüssel gebunden, mit dem es entstanden ist.**
    Ein neuer Schlüssel macht alte Archive nicht lesbar — er macht sie
    unlesbar, wenn der alte verschwindet.

    Art. 13 Abs. 13 CRA verlangt zehn Jahre Aufbewahrung. Wer in dieser Zeit
    den Schlüssel wechselt, muss den alten **datiert daneben** verwahren, mit
    dem Zeitraum, für den er gilt. Ein Eintrag im Passwortmanager genügt,
    aber er muss das Datum tragen — sonst steht in acht Jahren ein Archiv
    da, zu dem drei Schlüssel existieren und niemand weiß, welcher.

    Das ist der Grund, warum der Schlüsselwechsel kein Routinevorgang ist:
    Er vergrößert die Zahl der Geheimnisse, die über die ganze Frist
    verwahrt werden müssen.

### Entschlüsseln

Innerhalb der Anwendung passiert es von selbst — Wiederherstellen und
Übernehmen erkennen das Format am Kopf und entschlüsseln vorübergehend. Die
Liste der Sicherungen entschlüsselt **nicht**; sie zeigt stattdessen
`verschlüsselt` an, weil sie sonst für jede Zeile das ganze Archiv lesen
müsste.

Von außen, ohne die Anwendung:

```bash
AICS_BACKUP_KEY='…' python3 scripts/ops/backup_entschluesseln.py     archiv_8.3.1_20261102_204500.zip ausgabe.zip
```

### Warum das Format offen dokumentiert ist

Neben jedem verschlüsselten Archiv liegt eine Beilegedatei
`*.ENTSCHLUESSELN.md` **im Klartext**. Sie enthält kein Geheimnis, sondern das
Format: `PBKDF2-HMAC-SHA256` für die Schlüsselableitung, `AES-256-GCM`
blockweise, Kopf von 44 Byte.

Das ist eine bewusste Entscheidung gegen ein geschlossenes Format. Art. 13
Abs. 13 der Verordnung (EU) 2024/2847 verlangt die Aufbewahrung über **zehn
Jahre**; ein Archiv, das nur eine bestimmte Fassung einer bestimmten Anwendung
lesen kann, taugt dafür nicht. Wer in zehn Jahren das Archiv und den Schlüssel
hat, kann den Entschlüsseler aus der Beilage nachschreiben.

### Der Schutz gegen Abschneiden

Jeder Block trägt seine Nummer und ein Kennzeichen, ob er der letzte ist, in
den authentifizierten Zusatzdaten. Ohne das ließe sich ein Archiv **kürzen**
oder umordnen, und jeder einzelne Block bliebe gültig — ein Archiv, das sich
unbemerkt kürzen lässt, ist als Nachweis nichts wert.

## Archivstand je Fassung

Ein **Archivstand** ist dasselbe Paket mit anderem Zweck: Er wird für die
Aufbewahrungsfrist behalten und **nicht rotiert**.

```
POST /api/admin/backup   {"art": "archiv", "version": "8.3.1"}
```

Die Fassung ist Pflicht — aufbewahrt wird je Fassung ab ihrem
Inverkehrbringen. Der Name entscheidet über die Rotation: `archiv_*` bleibt,
`backup_*` fällt nach `backup_retention_count` heraus. Ohne diese Trennung
räumte der Zeitplan nach fünf Nächten genau den Nachweis weg, den er bewahren
soll.

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
