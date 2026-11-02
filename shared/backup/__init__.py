"""Sicherung und Wiederherstellung der gesamten Installation (#1785).

WARUM ES DIESES PAKET GIBT
Bis v8.0.4 sicherte ``create_backup`` die Dateien ``data/db/*.sqlite``. Die Suite
läuft aber seit Juni 2026 auf PostgreSQL (``shared/db.py`` kennt keinen
SQLite-Pfad mehr; die ``.sqlite``-Namen sind nur noch Schlüssel für den
Schema-Namen). Die Dateien im Volume waren damit tote Reste — ein Backup vom
Oktober enthielt den Stand von Juni, und ein Restore daraus meldete Erfolg, ohne
etwas zu ändern. Ein Archiv, das aussieht wie eine Sicherung und keine ist, ist
schlechter als gar keins: Es verhindert, dass sich jemand um eine echte kümmert.

WAS GESICHERT WIRD
Alles, was eine Neuinstallation braucht, um wieder dieselbe Installation zu sein:

* **die Datenbank** — alle Schemata, Tabellen, Daten, Sequenzstände
  (:mod:`shared.backup.datenbank`),
* **die Dateien** unter ``data/`` — Word-Vorlagen, Gutachten-Exporte,
  Nachweis-Store, SBOM-Dateien, Zertifikate, Handbuch
  (:mod:`shared.backup.dateien`),
* **die Konfiguration** samt Integritäts-Sidecars.

Die Dateiauswahl ist eine **Ausschlussliste**, keine Einschlussliste. Ein neues
Modul, das etwas unter ``data/`` ablegt, ist damit von sich aus gesichert. Die
umgekehrte Richtung — jedes Verzeichnis einzeln eintragen — ist genau die
Spiegel-Liste, die in diesem Projekt schon mehrfach auseinandergelaufen ist
(#1731/#1735), und beim Backup merkt man es erst im Ernstfall.

WARUM KEIN ``pg_dump``
Das Schema dieser Anwendung gehört der Anwendung: Die ``ensure_db``-Funktionen
legen Tabellen und Migrationen idempotent an, der Warmup führt sie beim Start
aus. Ein ``pg_restore --clean`` würde den Schemastand der Backup-Zeit
zurückschreiben und damit Migrationen **zurückdrehen** — aus einer
Wiederherstellung würde ein Downgrade. Deshalb sichert dieses Paket Daten und
Struktur getrennt: Beim Einspielen gilt das Schema der laufenden Version, und
die Struktur aus dem Archiv dient nur dazu, Tabellen anzulegen, die es im Ziel
noch nicht gibt (frische Installation). Nebeneffekt, der hier zählt: Es braucht
kein zusätzliches Programm im Image, läuft über ``psycopg`` und ist damit
überall testbar, wo die Anwendung selbst läuft.
"""

from shared.backup.paket import (  # noqa: F401
    FORMAT_VERSION,
    BackupFehler,
    beschreibe,
    erstelle_backup,
    lies_manifest,
    stelle_wieder_her,
)
