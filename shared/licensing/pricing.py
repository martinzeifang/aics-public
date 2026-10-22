"""Preisblatt für das MSP-/Wholesale-Modell (#1705).

Das Geschäftsmodell ist: eine Installation, viele Mandanten (Firmen). Abgerechnet
wird **je Mandant**: ein Grundpreis plus die kostenpflichtigen Zusatzmodule, die
für diesen Mandanten gebucht sind. Ab einer Mandantenzahl greift eine Mengenstaffel.

Die Zahlen sind **Konfiguration**, nicht Code: ``licensing.preisblatt`` in der
Suite-Config.

Default (marktabgeglichen 2026-10-20): **Grundpreis 95 €** inkl. WiBA ·
CRA 190 € · EU AI Act 110 € · NIS2 110 € · DSGVO 85 €; Staffel −10 % ab 11 /
−15 % ab 26 / −20 % ab 51 / −25 % ab 101 / −30 % ab 201 Mandanten.
Vollausbau **590 €** je Mandant.

**Wichtig für jeden Preisvergleich:** Das sind *Wholesale*-Preise an den
Lizenznehmer, der sie an Endkunden weiterverkauft. Marktpreise von heyData,
Proliance, Kopexa, DataGuard & Co. sind *Endkunden*-Preise. Ein Vergleich muss den
Aufschlag des Lizenznehmers einrechnen (Richtwert 2×), sonst erscheint das eigene
Angebot doppelt so günstig, wie es beim Endkunden ankommt. Herleitung der Preise:

===================== ======================= =========================
Modul                 Markt (Endkunde, Med.)  AICS Wholesale (≈ 50 %)
===================== ======================= =========================
DSGVO                 120 € (Software-only)   85 € (DSMS-Vollausbau)
NIS2                  250 €                   110 €
EU AI Act             200 €                   110 €
CRA                   399 € (kaum Wettbew.)   190 €
WiBA/ISMS             150 €                   im Grundpreis
===================== ======================= =========================

Markt-Korb aller Funktionen ≈ 1.120 €/Monat beim Endkunden; AICS-Vollausbau
590 € Wholesale → ≈ 1.180 € beim Endkunden. Das liegt knapp über dem Korb und
ist durch den Funktionsumfang gedeckt (ein Risikoregister für alle Rahmenwerke,
Pentest-Verwertung, gemeinsames Cockpit).

**CRA-Erhöhung 150 → 190 € (v8.0.0):** Mit dem Release-Nachweis je Version ist
CRA kein Fragebogen-Modul mehr, sondern der laufende Konformitätsvorgang —
Vier-Augen-Freigabe (Entwicklung reicht ein, Compliance gibt frei),
EU-Konformitätserklärung als erzeugtes Dokument mit CE-Kennzeichnung,
Kundenfassung zur Weitergabe, Prüfung des Bewertungswegs gegen die
Produktklasse und erzwungene Neubewertung bei wesentlichen Änderungen. Das
ersetzt beim Endkunden Beratungsleistung, nicht Software; 399 € Marktwert
bleiben damit weiterhin deutlich unterschritten.

Hintergrund WiBA im Grundpreis: 19 der 24 DSGVO-TOM-Maßnahmen (79 %) werden aus
WiBA abgeleitet (``dsgvo/tom_wiba.py``) — ohne WiBA ist Art. 32 reine
Selbsteinschätzung. WiBA ist damit Nachweis-Rückgrat, wie die Risikobewertung
Risiko-Rückgrat ist (siehe ``modules.BASE_MODULES``). Der frühere 75-€-Einzelpreis
ist ersatzlos entfallen. WiBA behält hier eine Preiszeile mit Wert 0, damit die
Entscheidung ohne Code-Eingriff umkehrbar bleibt.

Alle Beträge sind **Netto-Monatspreise je Mandant** in der konfigurierten Währung.
"""

from __future__ import annotations

from typing import Any

from shared.licensing.modules import SELLABLE_MODULES, canonical

#: Default-Preisblatt (marktabgeglichen 2026-10-20, Wholesale je Mandant).
DEFAULT_PREISBLATT: dict[str, Any] = {
    'waehrung': 'EUR',
    'grundpreis': 95,
    'module': {
        'cra': 190,
        'aiact': 110,
        'nis2': 110,
        'dsgvo': 85,
        # 0 = im Grundpreis enthalten (Grundpreis-Modul, siehe modules.BASE_MODULES).
        # Die Zeile bleibt, damit die Bündelung ohne Code-Eingriff umkehrbar ist.
        'wiba': 0,
    },
    # Mengenstaffel: ab `ab` aktiven Mandanten gilt `rabatt` Prozent auf alles.
    # Die oberen Stufen zielen auf den Großfall „eine Lizenz, ~300 Endkunden":
    # dort entscheidet Menge, nicht Stückpreis.
    'staffel': [
        {'ab': 11, 'rabatt': 10},
        {'ab': 26, 'rabatt': 15},
        {'ab': 51, 'rabatt': 20},
        {'ab': 101, 'rabatt': 25},
        {'ab': 201, 'rabatt': 30},
    ],
}

#: Module, die überhaupt einen Einzelpreis haben können.
PREIS_MODULE: tuple[str, ...] = (*SELLABLE_MODULES, 'wiba')


def load_preisblatt(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Preisblatt aus der Config lesen, fehlende Werte aus dem Default ergänzen."""
    if cfg is None:
        try:
            from ai_compliance_suite.config import load_config
            cfg = load_config()
        except Exception:  # noqa: BLE001 — ohne Config gilt der Default
            cfg = {}
    raw = ((cfg or {}).get('licensing') or {}).get('preisblatt') or {}
    return normalize_preisblatt(raw)


def normalize_preisblatt(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Rohwerte validieren/auffüllen. Unbekannte Module werden verworfen."""
    raw = raw if isinstance(raw, dict) else {}
    out: dict[str, Any] = {
        'waehrung': str(raw.get('waehrung') or DEFAULT_PREISBLATT['waehrung']),
        'grundpreis': _money(raw.get('grundpreis'), DEFAULT_PREISBLATT['grundpreis']),
        'module': {},
        'staffel': [],
    }
    raw_mods = raw.get('module') if isinstance(raw.get('module'), dict) else {}
    for mod in PREIS_MODULE:
        default = DEFAULT_PREISBLATT['module'].get(mod, 0)
        # Alias-tolerant lesen (``ai_act`` schreibt auf ``aiact``).
        value = None
        for key, val in (raw_mods or {}).items():
            if canonical(str(key)) == mod:
                value = val
                break
        out['module'][mod] = _money(value, default)

    raw_staffel = raw.get('staffel')
    if isinstance(raw_staffel, list):
        for stufe in raw_staffel:
            if not isinstance(stufe, dict):
                continue
            try:
                ab = int(stufe.get('ab'))
                rabatt = float(stufe.get('rabatt'))
            except (TypeError, ValueError):
                continue
            if ab < 1 or not (0 <= rabatt <= 100):
                continue
            out['staffel'].append({'ab': ab, 'rabatt': round(rabatt, 2)})
    else:
        out['staffel'] = [dict(s) for s in DEFAULT_PREISBLATT['staffel']]
    out['staffel'].sort(key=lambda s: s['ab'])
    return out


def save_preisblatt(raw: dict[str, Any]) -> dict[str, Any]:
    """Preisblatt persistieren (``licensing.preisblatt``) und normalisiert zurückgeben."""
    from ai_compliance_suite.config import load_config, save_config

    clean = normalize_preisblatt(raw)
    cfg = load_config()
    cfg.setdefault('licensing', {})['preisblatt'] = clean
    save_config(cfg)
    return clean


def rabatt_prozent(anzahl_mandanten: int, preisblatt: dict[str, Any] | None = None) -> float:
    """Staffelrabatt für eine Mandantenzahl (höchste erreichte Stufe gewinnt)."""
    pb = preisblatt or load_preisblatt()
    rabatt = 0.0
    for stufe in pb.get('staffel') or []:
        if anzahl_mandanten >= int(stufe['ab']):
            rabatt = float(stufe['rabatt'])
    return rabatt


def preis_fuer_mandant(module: list[str] | set[str], *, anzahl_mandanten: int = 1,
                       preisblatt: dict[str, Any] | None = None) -> dict[str, Any]:
    """Monatspreis eines Mandanten: Grundpreis + gebuchte Zusatzmodule − Staffel.

    ``module`` sind die für diesen Mandanten **gebuchten** Module; Module ohne
    Einzelpreis (im Grundpreis enthalten, Preis 0) zählen nicht mit.
    """
    pb = preisblatt or load_preisblatt()
    preise = pb['module']
    gebucht = {canonical(m) for m in (module or [])}
    posten = {m: preise[m] for m in PREIS_MODULE if m in gebucht and preise.get(m)}
    grundpreis = float(pb['grundpreis'])
    modulsumme = float(sum(posten.values()))
    listenpreis = grundpreis + modulsumme
    rabatt = rabatt_prozent(anzahl_mandanten, pb)
    monatspreis = round(listenpreis * (1 - rabatt / 100), 2)
    return {
        'grundpreis': grundpreis,
        'module': posten,
        'modulsumme': modulsumme,
        'listenpreis': listenpreis,
        'rabatt_prozent': rabatt,
        'monatspreis': monatspreis,
        'waehrung': pb['waehrung'],
    }


def _money(value: Any, default: float) -> float:
    """Betrag robust parsen; negative/kaputte Werte fallen auf den Default zurück."""
    if value is None or value == '':
        return float(default)
    try:
        num = float(value)
    except (TypeError, ValueError):
        return float(default)
    if num < 0:
        return float(default)
    return round(num, 2)
