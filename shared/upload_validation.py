"""Upload-Validierung über Magic-Bytes / Dateiinhalt (#743, WP-10).

Prüft hochgeladene Dateien anhand ihres tatsächlichen Inhalts (Magic-Bytes),
nicht nur anhand der Dateiendung. Schützt gegen MIME-Spoofing (OWASP A03/A04,
ASVS V12) und – in Kombination mit ``validate_office_archive`` – gegen
Zip-Bombs.

Reines Python, keine libmagic/python-magic-Abhängigkeit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


# Magic-Byte-Signaturen pro Dateiendung. ZIP-basierte Office-Formate
# (.docx/.xlsx/.pptx) beginnen mit dem ZIP-Local-File-Header "PK\x03\x04".
_PDF_MAGIC = b"%PDF"
_ZIP_MAGIC = b"PK\x03\x04"
# Leeres ZIP-Archiv ("PK\x05\x06") bzw. Spanned ("PK\x07\x08") zulassen, da
# manche Tools solche Header schreiben.
_ZIP_EMPTY_MAGIC = b"PK\x05\x06"
_ZIP_SPANNED_MAGIC = b"PK\x07\x08"

_ZIP_OFFICE_SUFFIXES = {".docx", ".xlsx", ".pptx"}
_PDF_SUFFIXES = {".pdf"}
# Textbasierte Formate: keine zuverlässigen Magic-Bytes → Inhalt nur grob
# (kein NUL-Byte am Anfang) prüfen.
_TEXT_SUFFIXES = {".txt", ".csv", ".md", ".json", ".xml"}


class UploadValidationError(ValueError):
    """Wird ausgelöst, wenn ein Upload die Inhaltsprüfung nicht besteht."""


def _read_header(source: bytes | Path | str, n: int = 8) -> bytes:
    if isinstance(source, (bytes, bytearray)):
        return bytes(source[:n])
    path = Path(source)
    with open(path, "rb") as fh:  # noqa: PTH123
        return fh.read(n)


def _looks_like_zip(header: bytes) -> bool:
    return header.startswith(
        (_ZIP_MAGIC, _ZIP_EMPTY_MAGIC, _ZIP_SPANNED_MAGIC)
    )


def validate_magic_bytes(source: bytes | Path | str, *, suffix: str) -> None:
    """Validiere Magic-Bytes gegen die behauptete Dateiendung.

    Args:
        source: Pfad zur Datei ODER die ersten Bytes als ``bytes``.
        suffix: Erwartete (bereits geprüfte/normalisierte) Dateiendung inkl. Punkt.

    Raises:
        UploadValidationError: wenn der Inhalt der Endung widerspricht.
    """
    sfx = (suffix or "").lower()
    header = _read_header(source)

    if not header:
        raise UploadValidationError("Leere Datei wird abgelehnt")

    if sfx in _PDF_SUFFIXES:
        if not header.startswith(_PDF_MAGIC):
            raise UploadValidationError(
                "Dateiinhalt ist kein PDF (Magic-Bytes %PDF fehlen)"
            )
        return

    if sfx in _ZIP_OFFICE_SUFFIXES:
        if not _looks_like_zip(header):
            raise UploadValidationError(
                f"Dateiinhalt ist kein ZIP/Office-Dokument für {sfx}"
            )
        return

    if sfx in _TEXT_SUFFIXES:
        # Textdateien dürfen nicht mit einem NUL-Byte beginnen (Indiz für Binär).
        if header[:1] == b"\x00":
            raise UploadValidationError(
                f"Dateiinhalt scheint binär zu sein, erwartet Text für {sfx}"
            )
        return

    # Unbekannte Endung: konservativ ablehnen.
    raise UploadValidationError(f"Dateityp {sfx or '(leer)'} nicht erlaubt")


def validate_upload_file(
    path: Path | str,
    *,
    suffix: Optional[str] = None,
    office_zipbomb_check: bool = True,
) -> None:
    """Vollständige Inhaltsprüfung einer auf Platte liegenden Upload-Datei.

    1. Magic-Byte-Prüfung gegen die Endung.
    2. Für Office-/ZIP-Formate zusätzlich ``validate_office_archive`` als
       Zip-Bomb-/Größen-Schutz.

    Raises:
        UploadValidationError / ValueError bei ungültigem Inhalt.
    """
    p = Path(path)
    sfx = (suffix if suffix is not None else p.suffix).lower()

    validate_magic_bytes(p, suffix=sfx)

    if office_zipbomb_check and sfx in _ZIP_OFFICE_SUFFIXES:
        # validate_office_archive prüft auf .suffix der Datei – sicherstellen,
        # dass der temporäre Pfad die korrekte Endung trägt.
        from security_utils import validate_office_archive

        if p.suffix.lower() != sfx:
            raise UploadValidationError(
                f"Temporärer Pfad hat falsche Endung für {sfx}"
            )
        validate_office_archive(p, expected_suffix=sfx)
