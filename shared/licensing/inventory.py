"""Mandanten-Inventar für das Lizenzmanagement (#1713).

Im Wholesale-Modell ist die Abrechnungseinheit der **Mandant**, nicht der
Named-User und nicht die Installation. Eine Lizenz kann im größten Fall ~300
Endkunden enthalten. Damit abgerechnet werden kann, muss das Lizenzmanagement
die **angelegten Firmen sehen** — eine bloße Zahl im Heartbeat genügt nicht, weil
sich daraus keine Rechnung mit Positionen erzeugen lässt.

Dieses Modul baut ein kompaktes, übertragbares Inventar und meldet es über den
Heartbeat an den Lizenzserver. Entwurfsentscheidungen:

* **Kein hartes Limit.** ``max_firmen`` ist ein kaufmännisches *Kontingent*
  („300 Kunden inklusive"), keine Schranke. Der Überhang wird abgerechnet, die
  Anwendung läuft weiter (siehe ``server/api/firmen._mandanten_kontingent_hinweis``).
* **Digest-basiert.** Ohne Änderung reist nur ein SHA-256 über die Leitung, nicht
  die ganze Liste — bei 300 Mandanten und 6-stündigem Heartbeat sonst rund 50 MB
  pro Jahr völlig ohne Informationsgewinn.
* **Datensparsam.** Übertragen werden Mandantenname, Unternehmensbezeichnung,
  gebuchte Module und Zählwerte. **Nicht** übertragen werden Berater (kann ein
  Personenname sein), Beschreibungen, Projektnamen oder Inhalte.
* **Abschaltbar/pseudonymisierbar** über ``licensing.mandanten_melden``:
  ``'voll'`` (Default, mit Namen) · ``'anonym'`` (nur IDs + Namens-Hash) ·
  ``'aus'`` (nur Zählwerte).

Hinweis zur Vertragsgestaltung: Im Modus ``'voll'`` verlassen die Namen der
Endkunden des Lizenznehmers die Installation. Das gehört in den AVV bzw. die
Auftragsverarbeitungs-/Vertraulichkeitsregelung mit dem Lizenznehmer.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

#: Erlaubte Melde-Modi.
MODI = ('voll', 'anonym', 'aus')
DEFAULT_MODUS = 'voll'


def melde_modus(cfg: dict[str, Any] | None = None) -> str:
    """Konfigurierter Melde-Modus (``licensing.mandanten_melden``)."""
    if cfg is None:
        try:
            from ai_compliance_suite.config import load_config
            cfg = load_config()
        except Exception:  # noqa: BLE001
            cfg = {}
    raw = ((cfg or {}).get('licensing') or {}).get('mandanten_melden', DEFAULT_MODUS)
    if raw is True:
        return 'voll'
    if raw is False:
        return 'aus'
    wert = str(raw or DEFAULT_MODUS).strip().lower()
    return wert if wert in MODI else DEFAULT_MODUS


def _pseudonym(name: str) -> str:
    """Stabiles, kurzes Pseudonym eines Mandantennamens (Modus ``anonym``)."""
    return hashlib.sha256(name.strip().casefold().encode('utf-8')).hexdigest()[:16]


def build_inventar(*, db_dir: Path | None = None, modus: str | None = None,
                   usage: dict[str, Any] | None = None) -> dict[str, Any]:
    """Kompaktes Mandanten-Inventar für die Übertragung.

    Args:
        usage: ein bereits erzeugter Report aus :func:`usage.build_usage`
               (spart die zweite Erhebung, wenn ohnehin einer vorliegt).

    Returns:
        ``{modus, erzeugt_am, mandanten_gesamt, mandanten_aktiv, digest,
        mandanten: [...]}``. Im Modus ``'aus'`` ist ``mandanten`` leer.
    """
    from shared.licensing.usage import build_usage

    modus = modus if modus in MODI else melde_modus()
    report = usage if usage is not None else build_usage(db_dir=db_dir)

    zeilen: list[dict[str, Any]] = []
    if modus != 'aus':
        for m in report.get('mandanten') or []:
            name = str(m.get('name') or '')
            zeile: dict[str, Any] = {
                'fid': m.get('firmen_id'),
                'module': list(m.get('module_gebucht') or []),
                'projekte': int(m.get('projekte_gesamt') or 0),
                'aktiv': bool(m.get('aktiv')),
                'ruhend': bool(m.get('ruhend')),
                'seit': str(m.get('angelegt_am') or '')[:10],
                'letzte_aktivitaet': str(m.get('letzte_aktivitaet') or '')[:10],
            }
            if modus == 'voll':
                zeile['name'] = name
                zeile['unternehmen'] = str(m.get('unternehmen') or '')
            else:
                zeile['ref'] = _pseudonym(name)
            zeilen.append(zeile)
        zeilen.sort(key=lambda z: (str(z.get('name') or z.get('ref') or ''), z.get('fid') or 0))

    summe = report.get('summe') or {}
    inventar = {
        'modus': modus,
        'erzeugt_am': int(time.time()),
        'mandanten_gesamt': int(summe.get('mandanten_gesamt') or 0),
        'mandanten_aktiv': int(summe.get('mandanten_aktiv') or 0),
        'mandanten_ruhend': int(summe.get('mandanten_ruhend') or 0),
        'mandanten': zeilen,
    }
    inventar['digest'] = digest_of(inventar)
    return inventar


def digest_of(inventar: dict[str, Any]) -> str:
    """SHA-256 über den **inhaltlichen** Teil (ohne Zeitstempel/Digest selbst).

    Dadurch erzeugt ein unveränderter Mandantenbestand denselben Digest und der
    Heartbeat überträgt die Liste nicht erneut.
    """
    kern = {
        'modus': inventar.get('modus'),
        'mandanten_gesamt': inventar.get('mandanten_gesamt'),
        'mandanten_aktiv': inventar.get('mandanten_aktiv'),
        'mandanten_ruhend': inventar.get('mandanten_ruhend'),
        'mandanten': inventar.get('mandanten') or [],
    }
    roh = json.dumps(kern, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(roh.encode('utf-8')).hexdigest()


# ── Melde-Zustand (was wurde wann erfolgreich übertragen) ────────────────────

def _state_file() -> Path:
    data_dir = Path('/app/data') if Path('/app/data').exists() else Path('data')
    return data_dir / 'license_mandanten_report.json'


def load_report_state() -> dict[str, Any]:
    """Zuletzt erfolgreich gemeldeter Digest + Zeitpunkt. ``{}`` wenn unbekannt."""
    p = _state_file()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text('utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as e:
        log.warning('license_mandanten_report.json kaputt: %s', e)
        return {}


def save_report_state(*, digest: str, mandanten_gesamt: int,
                      mandanten_aktiv: int, modus: str) -> None:
    """Melde-Zustand persistieren (atomar, best effort)."""
    p = _state_file()
    payload = {
        'digest': digest,
        'gemeldet_am': int(time.time()),
        'mandanten_gesamt': int(mandanten_gesamt),
        'mandanten_aktiv': int(mandanten_aktiv),
        'modus': modus,
    }
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
        tmp.replace(p)
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass
    except OSError as e:
        log.warning('Melde-Zustand konnte nicht gespeichert werden: %s', e)


def heartbeat_payload(*, force: bool = False, db_dir: Path | None = None,
                      usage: dict[str, Any] | None = None) -> dict[str, Any]:
    """Die Mandanten-Felder für den Heartbeat-Body.

    Die vollständige Liste reist nur mit, wenn sich der Bestand seit der letzten
    erfolgreichen Meldung geändert hat — oder ``force=True`` (manuelles
    „jetzt melden"). Sonst nur Digest + Zählwerte.
    """
    inventar = build_inventar(db_dir=db_dir, usage=usage)
    zuletzt = load_report_state()
    geaendert = force or zuletzt.get('digest') != inventar['digest']

    payload: dict[str, Any] = {
        'firmen_count': inventar['mandanten_gesamt'],
        'active_firmen_count': inventar['mandanten_aktiv'],
        'mandanten_digest': inventar['digest'],
    }
    if geaendert and inventar['modus'] != 'aus':
        payload['mandanten'] = inventar['mandanten']
        payload['mandanten_modus'] = inventar['modus']
    # Für den Aufrufer, der nach erfolgreichem Senden den Zustand schreibt.
    payload['_inventar'] = inventar
    payload['_uebertragen'] = geaendert
    return payload


def quittieren(inventar: dict[str, Any]) -> None:
    """Nach erfolgreichem Heartbeat aufrufen — merkt den gemeldeten Digest."""
    save_report_state(
        digest=inventar.get('digest') or '',
        mandanten_gesamt=int(inventar.get('mandanten_gesamt') or 0),
        mandanten_aktiv=int(inventar.get('mandanten_aktiv') or 0),
        modus=str(inventar.get('modus') or DEFAULT_MODUS),
    )
