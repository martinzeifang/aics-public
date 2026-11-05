"""Compliance-Audit — Standortbestimmung gegen ein Framework.

Eigenes Modul seit v7.4.0. Vorher steckte der Audit im Gutachten-Modul, obwohl
es fachlich etwas anderes ist: Ein Gutachten ist eine gutachterliche Äußerung
(ggf. für ein Gericht, § 407a ZPO), ein Compliance-Audit erhebt per Fragenkatalog
den Umsetzungsstand des Kunden gegen ein Framework und meldet ihm den
Wasserstand.

Das Modul gehört zu den **Grundpreis-Modulen** (wie Risikobewertung) und ist
damit bei jeder gültigen Lizenz nutzbar — siehe ``shared/licensing/modules.py``.

Datenhaltung: weiterhin die Tabellen ``gutachten_projects`` /
``gutachten_questions`` / ``gutachten_assessments`` in ``data/db/gutachten.sqlite``
(:mod:`gutachten.db`). Die Namen bleiben bewusst, um bestehende Kundendaten nicht
migrieren zu müssen; sie sind historisch, nicht fachlich.
"""

from __future__ import annotations

from compliance_audit.status import (  # noqa: F401 — öffentliche Schnittstelle
    ERFUELLUNG,
    SCHWELLEN,
    STUFEN,
    STUFEN_LABELS,
    build_status,
    erfuellung_of,
    luecken,
    normalize_erfuellung,
    stufe_fuer,
)
