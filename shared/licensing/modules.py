"""Modul-Registry für das Lizenz-Gate — Single Source of Truth (#1704).

Bis v7.3.0 stand die Liste der lizenzierten Module als Literal-Set mitten im
``before_request``-Guard von ``server/app.py``. Das hatte drei Löcher:

* ``wiba`` und ``pentest`` fehlten → beide Module waren **nie** abschaltbar,
  obwohl WiBA im Preisblatt steht.
* Die Unterscheidung „im Grundpreis enthalten" vs. „kostenpflichtiges
  Zusatzmodul" existierte nicht, obwohl das Geschäftsmodell darauf aufbaut.
* Der Alias ``ai_act`` ↔ ``aiact`` war nur implizit (Token sagt ``aiact``,
  Firmen-Tabelle sagt ``module_ai_act``).

Diese Datei kodiert das Preisblatt technisch:

``BASE_MODULES``
    Im **Grundpreis** enthalten. Jede gültige Lizenz schließt sie ein; sie
    müssen nicht einzeln im Token stehen. Fachlich sind das die
    Querschnitts-Rückgrate: Risikobewertung (Risiko), WiBA + Pentest (Nachweis),
    Compliance-Audit (Standortbestimmung gegen ein Framework).

``SELLABLE_MODULES``
    Kostenpflichtige Zusatzmodule. Nur erlaubt, wenn sie **explizit** im Token
    stehen (oder das Wildcard ``*`` gesetzt ist).

``WEITERE_MODULE``
    Vorhanden, aber nicht Teil des Angebotsumfangs. Wird wie ein Zusatzmodul
    gegated. **Seit #1905 leer** — der einzige Eintrag war ``soc``, und das
    Modul ist abgekündigt und entfernt. Die Kategorie bleibt, weil sie von
    ``GATED_MODULES`` und ``effective_modules`` gelesen wird und das nächste
    Modul dieser Art hier hingehört.

    Ein **Bestandstoken, das ``soc`` nennt, bleibt gültig**: Die
    Gate-Entscheidung geht immer von einem Pfad aus
    (:func:`module_for_path`), und auf ``soc`` zeigt kein Pfad mehr. Ein
    unbekannter Name in der Token-Liste bedeutet damit nichts — nicht alles
    und nicht nichts. :func:`effective_modules` zählt ebenfalls nur die
    bekannten Kategorien auf.

``EXPLICIT_MODULES``
    Auch bei Wildcard ``*`` nur mit expliziter Nennung erlaubt (Gutachten) —
    das war schon vor #1704 so und bleibt bewusst konservativ.

``UNGATED_MODULES``
    ``firmen`` ist das Mandantenregister selbst und wird nie modul-gegated:
    ohne Firmen gibt es keinen Wiederanlauf nach einem Lizenzproblem. Die
    kaufmännische Begrenzung läuft über ``max_firmen`` (Mandanten-Limit).
"""

from __future__ import annotations

# ── Kategorien ───────────────────────────────────────────────────────────────

#: Im Grundpreis enthalten — jede gültige Lizenz schließt sie ein.
BASE_MODULES: tuple[str, ...] = (
    'risikobewertung', 'wiba', 'pentest', 'compliance_audit')

#: Kostenpflichtige Zusatzmodule — müssen im Lizenz-Token stehen.
SELLABLE_MODULES: tuple[str, ...] = ('cra', 'nis2', 'aiact', 'dsgvo')

#: Vorhanden, aber nicht im Angebotsumfang — wie ein Zusatzmodul gegated.
#: Leer seit #1905 (SOC abgekündigt und entfernt); siehe Dateikopf.
WEITERE_MODULE: tuple[str, ...] = ()

#: Nur bei expliziter Nennung, auch bei Wildcard ``*`` (Verhalten vor #1704).
EXPLICIT_MODULES: tuple[str, ...] = ('gutachten',)

#: Nie modul-gegated (Mandantenregister; Begrenzung über ``max_firmen``).
UNGATED_MODULES: tuple[str, ...] = ('firmen',)

#: Alle Module, die das Gate kennt (gegated).
GATED_MODULES: frozenset[str] = frozenset(
    BASE_MODULES + SELLABLE_MODULES + WEITERE_MODULE + EXPLICIT_MODULES)

#: Alle Module überhaupt (inkl. ungegated).
ALL_MODULES: frozenset[str] = GATED_MODULES | frozenset(UNGATED_MODULES)

#: URL-/Config-Schreibweisen → kanonischer Lizenz-Schlüssel.
MODULE_ALIASES: dict[str, str] = {
    'ai_act': 'aiact',
    'aiact': 'aiact',
    'kunden': 'firmen',   # Deprecation-Alias (#1003)
    # Compliance-Audit: Bindestrich wird in canonical() zu '_', die Kurzform
    # 'audit' kommt in Konfigurationen und Lizenz-Token vor.
    'audit': 'compliance_audit',
    'complianceaudit': 'compliance_audit',
}

#: Kanonischer Schlüssel → Anzeigename.
MODULE_LABELS: dict[str, str] = {
    'cra': 'CRA',
    'nis2': 'NIS2',
    'aiact': 'EU AI Act',
    'dsgvo': 'DSGVO',
    'wiba': 'WiBA',
    'risikobewertung': 'Risikobewertung',
    'pentest': 'Pentest',
    'firmen': 'Firmen',
    'gutachten': 'Gutachten',
    'compliance_audit': 'Compliance-Audit',
}

#: Kanonischer Schlüssel → Spalte in ``firmen`` (Modul je Mandant gebucht?).
FIRMEN_MODULE_COLUMNS: dict[str, str] = {
    'cra': 'module_cra',
    'nis2': 'module_nis2',
    'aiact': 'module_ai_act',
    'dsgvo': 'module_dsgvo',
    'wiba': 'module_wiba',
    'risikobewertung': 'module_risikobewertung',
    'gutachten': 'module_gutachten',
    'compliance_audit': 'module_compliance_audit',
}


# ── Normalisierung ───────────────────────────────────────────────────────────

def canonical(module: str) -> str:
    """Beliebige Schreibweise → kanonischer Lizenz-Schlüssel (``ai_act`` → ``aiact``)."""
    key = (module or '').strip().lower().replace('-', '_')
    return MODULE_ALIASES.get(key, key)


def module_for_path(path: str) -> str | None:
    """Request-Pfad → kanonisches Modul, oder ``None`` wenn nicht modulbezogen.

    Berücksichtigt die Bindestrich-Geschwister-Blueprints (#1169): ``/api/dsgvo-tom``,
    ``/api/cra-konformitaet``, ``/api/aiact-literacy`` … gehören zum Basis-Modul.
    ``/api/risk-cockpit`` ist read-only und kein Modul-Prefix → ``None``.
    """
    parts = (path or '').lstrip('/').split('/')
    if len(parts) < 2 or parts[0] != 'api':
        return None
    seg = parts[1].strip().lower()
    if not seg:
        return None
    # Erst die ganze Segment-Schreibweise prüfen (``ai_act``), dann das
    # Basis-Modul vor dem ersten Bindestrich (``dsgvo-tom`` → ``dsgvo``).
    for candidate in (seg, seg.split('-', 1)[0]):
        key = canonical(candidate)
        if key in ALL_MODULES:
            return key
    return None


# ── Gate-Entscheidung ────────────────────────────────────────────────────────

def is_allowed(module: str, allowed: 'set[str] | None') -> bool | None:
    """Darf auf ``module`` schreibend zugegriffen werden?

    Args:
        module: kanonisches Modul (aus :func:`module_for_path`).
        allowed: ``None`` = Wildcard ``*`` · leeres Set = keine bestätigte Lizenz ·
                 sonst das Set der im Token genannten Module.

    Returns:
        ``True``/``False`` für gegatete Module, ``None`` wenn das Modul nicht
        dem Lizenz-Gate unterliegt (Aufrufer lässt dann durch).
    """
    mod = canonical(module)
    if mod in UNGATED_MODULES or mod not in GATED_MODULES:
        return None

    if allowed is None:
        # Wildcard: alles außer den bewusst ausgenommenen Modulen.
        return mod not in EXPLICIT_MODULES
    if not allowed:
        # Keine (bestätigte) Lizenz → keine Schreibzugriffe auf Fachmodule.
        return False
    if mod in BASE_MODULES:
        # Im Grundpreis enthalten — jede gültige Lizenz schließt sie ein,
        # auch wenn der Token sie nicht einzeln aufführt.
        return True
    return mod in allowed


def effective_modules(allowed: 'set[str] | None') -> list[str]:
    """Die für diese Lizenz tatsächlich nutzbaren Module (für UI/Report)."""
    out = [m for m in (*BASE_MODULES, *SELLABLE_MODULES, *WEITERE_MODULE,
                       *EXPLICIT_MODULES)
           if is_allowed(m, allowed)]
    return [*UNGATED_MODULES, *out]


def billable_modules(allowed: 'set[str] | None') -> list[str]:
    """Kostenpflichtige Zusatzmodule dieser Lizenz (Basis für die Abrechnung)."""
    return [m for m in SELLABLE_MODULES if is_allowed(m, allowed)]
