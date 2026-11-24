"""Hochgeladene und erzeugte Dateien sichern (#1785).

Was in der Datenbank steht, ist nur die halbe Installation. Die andere Hälfte
liegt als Datei: Word-Vorlagen (``data/templates``, ``data/gutachten/templates``),
finalisierte Gutachten (``data/gutachten/final_exports``), der Nachweis-Store
(``data/evidence``), ausgestellte Konformitätsnachweise (``data/cra/…``),
DSGVO-Jahresberichte und Kontroll-Anhänge, SBOM-Dateien, das Handbuch,
Zertifikate und die Lizenzdatei. Eine Datenbank ohne diese Dateien ergibt eine
Installation, die ihre eigenen Dokumente nicht mehr ausliefern kann — die
Registry nennt eine Vorlage, die Datei dahinter fehlt.

AUSSCHLUSSLISTE, NICHT EINSCHLUSSLISTE
Gesichert wird ``data/`` vollständig; ausgenommen ist nur, was nachweislich
nichts enthält, was man vermissen könnte. Umgekehrt — jedes Verzeichnis einzeln
eintragen — wäre eine weitere Spiegel-Liste, und anders als bei einem falschen
Menüeintrag merkt man den Fehler hier erst im Ernstfall.

ZUR VERTRAULICHKEIT
Das Archiv enthält damit auch ``data/certs`` (private Schlüssel) und die
Lizenzdatei. Das ist gewollt — ohne sie ist die Wiederherstellung unvollständig
— und der Grund, warum der Download im Revisionspfad steht (#1784) und die
Datei außerhalb des Servers aufbewahrt gehört.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

#: Wird nicht gesichert. Kurz halten und jede Zeile begründen.
AUSSCHLUSS_ORDNER = {
    "tmp",            # Arbeitsdateien einzelner Requests (workspace_tmpdir)
    "__pycache__",
    ".cache",
}

AUSSCHLUSS_ENDUNGEN = (".pyc", ".pyo", ".sock", ".lock")

#: Dateien, die nur während eines Schreibvorgangs existieren. Ein halb
#: geschriebenes WAL im Archiv wäre schlimmer als keins.
AUSSCHLUSS_NAMEN = {".DS_Store", "Thumbs.db"}


def _ueberspringen(pfad: Path, wurzel: Path) -> bool:
    rel = pfad.relative_to(wurzel)
    if any(teil in AUSSCHLUSS_ORDNER for teil in rel.parts):
        return True
    if pfad.name in AUSSCHLUSS_NAMEN:
        return True
    return pfad.suffix.lower() in AUSSCHLUSS_ENDUNGEN


def sammle(wurzel: Path) -> Iterator[tuple[Path, str]]:
    """Alle zu sichernden Dateien unter ``wurzel`` mit ihrem Archivpfad.

    Symbolische Verweise werden übersprungen statt verfolgt: Ein Verweis nach
    außerhalb würde fremde Dateien ins Archiv ziehen, und beim Einspielen wäre
    aus dem Verweis eine Kopie geworden — eine stille Veränderung der Ablage.
    """
    if not wurzel.exists():
        return
    for ordner, unterordner, dateien in os.walk(wurzel, followlinks=False):
        p_ordner = Path(ordner)
        unterordner[:] = [
            u for u in unterordner
            if u not in AUSSCHLUSS_ORDNER and not (p_ordner / u).is_symlink()
        ]
        for name in sorted(dateien):
            pfad = p_ordner / name
            if pfad.is_symlink() or not pfad.is_file():
                continue
            if _ueberspringen(pfad, wurzel):
                continue
            yield pfad, pfad.relative_to(wurzel).as_posix()


def groesse(wurzel: Path) -> tuple[int, int]:
    """(Anzahl, Bytes) — für das Manifest und die Anzeige vor dem Lauf."""
    anzahl = summe = 0
    for pfad, _ in sammle(wurzel):
        try:
            summe += pfad.stat().st_size
            anzahl += 1
        except OSError:
            continue
    return anzahl, summe


def ziel_pruefen(archivpfad: str, wurzel: Path) -> Path | None:
    """Zielpfad für einen Archiveintrag, oder ``None`` wenn er ausbricht.

    Ein Archiv kann von außerhalb kommen (Upload). ``..`` und absolute Pfade
    schreiben sonst an beliebige Stellen des Dateisystems — und ein Restore
    läuft mit den Rechten der Anwendung.
    """
    roh = (archivpfad or "").replace("\\", "/")
    if not roh or roh.startswith("/") or ".." in Path(roh).parts:
        return None
    ziel = (wurzel / roh).resolve()
    if wurzel.resolve() != ziel and wurzel.resolve() not in ziel.parents:
        return None
    return ziel
