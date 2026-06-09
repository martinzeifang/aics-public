"""DS2 (#1102) — Accountability-/DSMS-Cockpit (Art. 5 Abs. 2 DSGVO).

Aggregiert pro Projekt eine bereichsübergreifende DSMS-Übersicht (Datenschutz-
Management-System) über ALLE DSGVO-Areas. Reine Lese-/Aggregations-Schicht: die
Area-DB-Module werden NUR gelesen, keine eigene Tabelle, kein Eingriff in
``dsgvo/db.py``.

``build_cockpit(db_path, projekt)`` liefert:
    {
      areas: [{key, label, reifegrad_pct, status, offen, faellig}],
      offene_aufgaben: [{area, text, due, overdue}],
      gesamt_reifegrad: int,
    }

Der Reifegrad je Bereich ist eine konservative Heuristik (0-100 %); die offenen
Aufgaben/Fristen sammeln überfällige Betroffenenanträge, fällige TOM-
Wirksamkeitsprüfungen, anstehende DSFA-Reviews und fällige Löschungen.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from dsgvo import db as core_db
from dsgvo import betroffenenrechte_db as br_db
from dsgvo import dsb_db
from dsgvo import einwilligung_db
from dsgvo import loeschkonzept_db
from dsgvo import tom_katalog
from dsgvo import transfer_db

DB_PATH = Path('data/db/dsgvo.sqlite')

# Reihenfolge + Anzeige-Label + (optionaler) Drilldown-Tab-Id je Bereich.
AREA_META: list[dict[str, str]] = [
    {'key': 'vvt', 'label': 'Verarbeitungsverzeichnis (Art. 30)', 'tab': 'pflichtdoku'},
    {'key': 'tom', 'label': 'TOM-Katalog (Art. 32)', 'tab': 'tom-katalog'},
    {'key': 'dsfa', 'label': 'Datenschutz-Folgenabschätzung (Art. 35)', 'tab': 'pflichtdoku'},
    {'key': 'betroffenenrechte', 'label': 'Betroffenenrechte (Art. 15-22)', 'tab': 'betroffenenrechte'},
    {'key': 'transfer', 'label': 'Drittlandtransfer (Art. 44-49)', 'tab': 'transfer'},
    {'key': 'loeschkonzept', 'label': 'Löschkonzept (Art. 17)', 'tab': 'loeschkonzept'},
    {'key': 'einwilligung', 'label': 'Einwilligungen (Art. 7)', 'tab': 'einwilligung'},
    {'key': 'dsb', 'label': 'Datenschutzbeauftragter (Art. 37-39)', 'tab': 'dsgvo-dsb'},
]


# ── Hilfsfunktionen ─────────────────────────────────────────────────────────

def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _pct(part: float, total: float) -> int:
    if total <= 0:
        return 0
    return max(0, min(100, round(part / total * 100)))


def _status_from_pct(pct: int, *, has_data: bool = True) -> str:
    """Ampel-Status: 'leer' (keine Daten), 'rot' (<40), 'gelb' (<80), 'gruen'."""
    if not has_data:
        return 'leer'
    if pct < 40:
        return 'rot'
    if pct < 80:
        return 'gelb'
    return 'gruen'


# ── Bereichs-Auswertungen ───────────────────────────────────────────────────

def _area_vvt(db_path: Path, projekt: str) -> dict[str, Any]:
    rows = core_db.list_vvt(db_path, projekt)
    total = len(rows)
    # Reifegrad: Anteil VVT-Einträge mit gepflegter Rechtsgrundlage (Art. 6).
    befuellt = sum(1 for r in rows if str(r.get('rechtsgrundlage') or '').strip())
    pct = _pct(befuellt, total) if total else 0
    return {
        'reifegrad_pct': pct,
        'status': _status_from_pct(pct, has_data=total > 0),
        'offen': total - befuellt,
        'faellig': 0,
        'aufgaben': [
            {'text': f"VVT-Eintrag „{r.get('name') or r.get('vvt_id')}“ ohne Rechtsgrundlage (Art. 6)",
             'due': '', 'overdue': False}
            for r in rows if not str(r.get('rechtsgrundlage') or '').strip()
        ],
    }


def _area_tom(db_path: Path, projekt: str) -> dict[str, Any]:
    rows = tom_katalog.list_massnahmen(db_path, projekt)
    total = len(rows)
    # Reifegrad: durchschnittlicher Ist-Status relativ zum Soll (Status 0-5).
    if total:
        soll_sum = sum(int(r.get('soll') or 0) for r in rows)
        ist_sum = sum(min(int(r.get('status') or 0), int(r.get('soll') or 0)) for r in rows)
        pct = _pct(ist_sum, soll_sum) if soll_sum else 0
    else:
        pct = 0
    offen = sum(1 for r in rows if int(r.get('status') or 0) < int(r.get('soll') or 0))
    aufgaben: list[dict[str, Any]] = []
    faellig = 0
    today = date.today()
    for r in rows:
        wd = _parse_date(r.get('wirksamkeit_datum'))
        # Fällige Wirksamkeitsprüfung: Datum gesetzt und in der Vergangenheit.
        if wd is not None and wd <= today:
            faellig += 1
            aufgaben.append({
                'text': f"Wirksamkeitsprüfung fällig: {r.get('titel') or r.get('massnahme_key')}",
                'due': wd.isoformat(),
                'overdue': wd < today,
            })
    return {
        'reifegrad_pct': pct,
        'status': _status_from_pct(pct, has_data=total > 0),
        'offen': offen,
        'faellig': faellig,
        'aufgaben': aufgaben,
    }


def _area_dsfa(db_path: Path, projekt: str) -> dict[str, Any]:
    rows = core_db.list_dpia(db_path, projekt)
    total = len(rows)
    stages = list(core_db.DSFA_STAGES)
    n_stages = len(stages)
    aufgaben: list[dict[str, Any]] = []
    faellig = 0
    offen = 0
    today = date.today()
    if total:
        progress_sum = 0.0
        for r in rows:
            status = str(r.get('status') or '').lower()
            if status in ('abgeschlossen', 'freigegeben'):
                progress = 1.0
            else:
                offen += 1
                stage = str(r.get('stage') or 'schwellwert')
                idx = stages.index(stage) if stage in stages else 0
                progress = (idx + 1) / n_stages if n_stages else 0.0
            progress_sum += progress
            rv = _parse_date(r.get('naechstes_review'))
            if rv is not None and rv <= today:
                faellig += 1
                aufgaben.append({
                    'text': f"DSFA-Review fällig: {r.get('titel') or r.get('dpia_id')}",
                    'due': rv.isoformat(),
                    'overdue': rv < today,
                })
        pct = _pct(progress_sum, total)
    else:
        pct = 0
    return {
        'reifegrad_pct': pct,
        'status': _status_from_pct(pct, has_data=total > 0),
        'offen': offen,
        'faellig': faellig,
        'aufgaben': aufgaben,
    }


def _area_betroffenenrechte(db_path: Path, projekt: str) -> dict[str, Any]:
    rows = br_db.list_antraege(db_path, projekt)
    total = len(rows)
    offene = [r for r in rows if r.get('status') not in ('abgeschlossen', 'abgelehnt')]
    erledigt = total - len(offene)
    # Reifegrad: Anteil bearbeiteter Anträge (kein offener Rückstand ⇒ 100 %).
    pct = _pct(erledigt, total) if total else 100
    aufgaben: list[dict[str, Any]] = []
    faellig = 0
    for r in offene:
        overdue = bool(r.get('overdue'))
        if overdue:
            faellig += 1
        aufgaben.append({
            'text': f"Offener Antrag {r.get('antrag_id') or r.get('typ')} ({r.get('typ')})",
            'due': r.get('frist_datum') or '',
            'overdue': overdue,
        })
    return {
        'reifegrad_pct': pct,
        'status': _status_from_pct(pct, has_data=True),
        'offen': len(offene),
        'faellig': faellig,
        'aufgaben': aufgaben,
    }


def _area_transfer(db_path: Path, projekt: str) -> dict[str, Any]:
    rows = transfer_db.list_transfers(db_path, projekt)
    total = len(rows)
    abgeschlossen = sum(1 for r in rows if str(r.get('tia_status')) == 'abgeschlossen')
    pct = _pct(abgeschlossen, total) if total else 0
    offen = total - abgeschlossen
    aufgaben = [
        {'text': f"TIA offen für Transfer „{r.get('transfer_id')}“ ({r.get('drittland') or '—'})",
         'due': '', 'overdue': False}
        for r in rows if str(r.get('tia_status')) != 'abgeschlossen'
    ]
    return {
        'reifegrad_pct': pct,
        'status': _status_from_pct(pct, has_data=total > 0),
        'offen': offen,
        'faellig': 0,
        'aufgaben': aufgaben,
    }


def _area_loeschkonzept(db_path: Path, projekt: str) -> dict[str, Any]:
    rows = loeschkonzept_db.list_regeln(db_path, projekt)
    total = len(rows)
    erledigt = sum(1 for r in rows if str(r.get('status')) in ('erledigt', 'deaktiviert'))
    pct = _pct(erledigt, total) if total else 0
    faellige = loeschkonzept_db.list_faellig(db_path, projekt)
    aufgaben = [
        {'text': f"Fällige Löschung: {r.get('datenkategorie') or r.get('regel_id')} ({r.get('loesch_trigger')})",
         'due': '', 'overdue': True}
        for r in faellige
    ]
    return {
        'reifegrad_pct': pct,
        'status': _status_from_pct(pct, has_data=total > 0),
        'offen': total - erledigt,
        'faellig': len(faellige),
        'aufgaben': aufgaben,
    }


def _area_einwilligung(db_path: Path, projekt: str) -> dict[str, Any]:
    rows = einwilligung_db.list_einwilligungen(db_path, projekt)
    total = len(rows)
    aktiv = sum(1 for r in rows if str(r.get('status')) == 'aktiv')
    # Reifegrad: Anteil aktiver (nachweisbar gepflegter) Einwilligungen.
    pct = _pct(aktiv, total) if total else 0
    return {
        'reifegrad_pct': pct,
        'status': _status_from_pct(pct, has_data=total > 0),
        'offen': total - aktiv,
        'faellig': 0,
        'aufgaben': [],
    }


def _area_dsb(db_path: Path, projekt: str) -> dict[str, Any]:
    rec = dsb_db.get_dsb(db_path, projekt)
    if not rec:
        return {
            'reifegrad_pct': 0,
            'status': 'leer',
            'offen': 1,
            'faellig': 0,
            'aufgaben': [{'text': 'Kein Datenschutzbeauftragter erfasst (Art. 37)',
                          'due': '', 'overdue': False}],
        }
    # Reifegrad aus Pflicht-Bausteinen: Name, Kontakt, Veröffentlichung, Meldung.
    checks = [
        bool(str(rec.get('name') or '').strip()),
        bool(str(rec.get('kontakt_email') or '').strip()),
        bool(rec.get('kontakt_veroeffentlicht')),
        bool(rec.get('gemeldet_aufsicht')),
    ]
    pct = _pct(sum(checks), len(checks))
    aufgaben: list[dict[str, Any]] = []
    if not rec.get('kontakt_veroeffentlicht'):
        aufgaben.append({'text': 'DSB-Kontaktdaten noch nicht veröffentlicht (Art. 37 Abs. 7)',
                         'due': '', 'overdue': False})
    if not rec.get('gemeldet_aufsicht'):
        aufgaben.append({'text': 'DSB der Aufsichtsbehörde noch nicht gemeldet (Art. 37 Abs. 7)',
                         'due': '', 'overdue': False})
    return {
        'reifegrad_pct': pct,
        'status': _status_from_pct(pct, has_data=True),
        'offen': sum(1 for c in checks if not c),
        'faellig': 0,
        'aufgaben': aufgaben,
    }


_AREA_FUNCS = {
    'vvt': _area_vvt,
    'tom': _area_tom,
    'dsfa': _area_dsfa,
    'betroffenenrechte': _area_betroffenenrechte,
    'transfer': _area_transfer,
    'loeschkonzept': _area_loeschkonzept,
    'einwilligung': _area_einwilligung,
    'dsb': _area_dsb,
}


def build_cockpit(db_path: Path, projekt: str) -> dict[str, Any]:
    """Bereichsübergreifende DSMS-Übersicht eines Projekts (Art. 5 Abs. 2)."""
    db_path = Path(db_path)
    areas: list[dict[str, Any]] = []
    offene_aufgaben: list[dict[str, Any]] = []
    reifegrade: list[int] = []

    for meta in AREA_META:
        key = meta['key']
        func = _AREA_FUNCS[key]
        try:
            res = func(db_path, projekt)
        except Exception:  # pragma: no cover - defensiv; ein Bereich darf andere nicht killen
            res = {'reifegrad_pct': 0, 'status': 'leer', 'offen': 0, 'faellig': 0, 'aufgaben': []}

        pct = int(res.get('reifegrad_pct', 0))
        reifegrade.append(pct)
        areas.append({
            'key': key,
            'label': meta['label'],
            'tab': meta.get('tab', ''),
            'reifegrad_pct': pct,
            'status': res.get('status', 'leer'),
            'offen': int(res.get('offen', 0)),
            'faellig': int(res.get('faellig', 0)),
        })
        for a in res.get('aufgaben', []):
            offene_aufgaben.append({
                'area': key,
                'area_label': meta['label'],
                'tab': meta.get('tab', ''),
                'text': a.get('text', ''),
                'due': a.get('due', ''),
                'overdue': bool(a.get('overdue')),
            })

    # Offene Aufgaben: überfällige zuerst, dann nach Fälligkeitsdatum.
    def _sort_key(a: dict[str, Any]):
        return (0 if a['overdue'] else 1, a['due'] or '9999-12-31')

    offene_aufgaben.sort(key=_sort_key)

    gesamt = round(sum(reifegrade) / len(reifegrade)) if reifegrade else 0

    return {
        'projekt': projekt,
        'areas': areas,
        'offene_aufgaben': offene_aufgaben,
        'gesamt_reifegrad': gesamt,
    }
