"""Geteiltes Berichts-Center-Framework (Sprint #35, #1382).

Verallgemeinert das SOC-Berichts-Center (#1350) zu einer modul-übergreifenden
Basis, damit alle Module dasselbe Berichts-Center bekommen (gleiches UI/UX):
Berichtstyp-Katalog · frei wählbarer Zeitraum · DOCX/PDF · Lauf-Historie.

Was hier liegt (modul-unabhängig):
- Zeitraum-/Dauer-Helfer (``normalize_zeitraum``, ``quarter_range``, ``year_range``).
- Lauf-Historie je Modul-Schema (Tabelle ``<schema>_bericht_runs``) + Ablage unter
  ``data/<modul>/berichte/`` (``record_run``/``list_runs``/``read_stored``).
- ``generate_and_store`` — erzeugt einen Bericht über einen **Render-Callable** des
  Moduls (``render(typ, fmt, **ctx) -> bytes``) und protokolliert ihn.

Was die Module liefern (modul-spezifisch, bleibt im Modul):
- Katalog der Berichtstypen + die eigentliche Render-Funktion (wiederverwendet die
  bestehenden ``report_export``-Generatoren).

Die REST-Anbindung erfolgt über :mod:`shared.reports.api` (Blueprint-Helfer).
"""
from __future__ import annotations

from .core import (
    ReportSpec,
    ensure_history,
    generate_and_store,
    list_runs,
    normalize_zeitraum,
    quarter_range,
    read_stored,
    record_run,
    storage_dir,
    year_range,
)

__all__ = [
    "ReportSpec",
    "ensure_history",
    "generate_and_store",
    "list_runs",
    "normalize_zeitraum",
    "quarter_range",
    "read_stored",
    "record_run",
    "storage_dir",
    "year_range",
]
