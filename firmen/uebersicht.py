"""Firmen-Gesamtüberblick (v7.0.0): Umsetzungsgrad aller Module, Risiko-Cockpit,
DSGVO-TOM/WiBA, offene Aufgaben, Produkte, Nachweise und Berichte einer Firma.

Read-only Aggregation. Die Reifegrade werden **exakt wie in den Modul-Endpunkten**
berechnet (gleiche Funktionen), damit Firmen-Dashboard und Modul-Dashboards
übereinstimmen. Jeder Baustein ist best effort — ein fehlendes Modul-Schema oder ein
Fehler in einem Modul darf den Überblick nie verhindern.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from shared.risk_cockpit import _open_ro, _table_columns

DB_DIR = Path('data/db')

# key → (Label, Projekt-Tabelle, Firmen-Spalte, Route)
MODULE: dict[str, tuple[str, str, str, str]] = {
    'cra': ('CRA', 'cra_projekte', 'unternehmen', '/cra'),
    'nis2': ('NIS2', 'nis2_projekte', 'unternehmen', '/nis2'),
    'ai_act': ('AI Act', 'ai_act_projekte', 'organisation', '/aiact'),
    'dsgvo': ('DSGVO', 'dsgvo_projekte', 'unternehmen', '/dsgvo'),
    'wiba': ('WiBA', 'wiba_projekte', 'unternehmen', '/wiba'),
    'risikobewertung': ('Risikobewertung', 'rb_projekte', 'unternehmen', '/risikobewertung'),
}


def _db(modul: str) -> Path:
    return DB_DIR / f"{modul}.sqlite"


def _safe(fn: Callable[[], Any], default: Any) -> Any:
    try:
        return fn()
    except Exception:  # noqa: BLE001 — best effort je Baustein
        return default


def _norm(s: Any) -> str:
    return ' '.join(str(s or '').casefold().split())


def module_projekte(modul: str, firma: str, firmen_id: int | None,
                    unternehmen: str = '') -> list[dict[str, Any]]:
    """Projekte einer Firma in einem Modul: über ``firmen_id`` (S1), den Firmennamen bzw. die
    Unternehmensbezeichnung (Auto-Anlage #430 setzt ``unternehmen`` = Firmen-Unternehmen) oder
    den Projektnamen (= Firmenname)."""
    _label, table, firm_col, _route = MODULE[modul]
    con = _open_ro(_db(modul), table)
    if con is None:
        return []
    try:
        cols = _table_columns(con, table)
        sel = ['name'] + [c for c in (firm_col, 'firmen_id', 'meta_json', 'framework', 'produkt',
                                       'updated_at') if c in cols]
        rows = [dict(r) for r in con.execute(f"SELECT {', '.join(sel)} FROM {table}").fetchall()]
    finally:
        con.close()
    namen = {_norm(firma)} | ({_norm(unternehmen)} if _norm(unternehmen) else set())
    out = []
    for r in rows:
        if ((firmen_id is not None and r.get('firmen_id') == firmen_id)
                or _norm(r.get(firm_col)) in namen or _norm(r.get('name')) == _norm(firma)):
            meta = _safe(lambda: json.loads(r.get('meta_json') or '{}'), {})
            out.append({'name': r['name'], 'meta': meta if isinstance(meta, dict) else {},
                        'framework': r.get('framework', ''), 'produkt': r.get('produkt', ''),
                        'updated_at': r.get('updated_at')})
    return sorted(out, key=lambda x: x['name'])


# ── Reifegrad je Modul (identisch zu den Modul-Endpunkten) ─────────────────────

def _scores(load_bewertungen, db: Path, projekt: str) -> dict[str, int]:
    return {k: int((v or {}).get('bewertung', 0) or 0) for k, v in load_bewertungen(db, projekt).items()}


def pct_cra(projekt: str) -> float:
    from cra.db import load_bewertungen
    from cra.requirements import load_merged_anforderungen
    db = _db('cra')
    scores = _scores(load_bewertungen, db, projekt)
    ist = soll = 0
    for req in load_merged_anforderungen(db):
        gew = int(req.get('gewichtung', 1))
        soll += 5 * gew
        ist += scores.get(req.get('id'), 0) * gew
    return round(ist / soll * 100, 1) if soll else 0.0


def pct_nis2(projekt: str) -> float:
    from nis2.db import load_bewertungen
    from nis2.requirements import berechne_reifegrad, load_merged_anforderungen
    db = _db('nis2')
    return float(berechne_reifegrad(load_bewertungen(db, projekt), load_merged_anforderungen(db)).get('prozent', 0) or 0)


def pct_ai_act(projekt: str) -> float:
    from ai_act.db import load_bewertungen
    from ai_act.requirements import berechne_reifegrad
    return float(berechne_reifegrad(_scores(load_bewertungen, _db('ai_act'), projekt)).get('gesamt_pct', 0) or 0)


def pct_dsgvo(projekt: str) -> float:
    from dsgvo.db import load_bewertungen
    from dsgvo.requirements import berechne_reifegrad
    return float(berechne_reifegrad(_scores(load_bewertungen, _db('dsgvo'), projekt)).get('gesamt_pct', 0) or 0)


def pct_wiba(projekt: str) -> float:
    from wiba.db import compute_reifegrad
    return float(compute_reifegrad(_db('wiba'), projekt).get('gesamt_pct', 0) or 0)


PCT: dict[str, Callable[[str], float]] = {
    'cra': pct_cra, 'nis2': pct_nis2, 'ai_act': pct_ai_act, 'dsgvo': pct_dsgvo, 'wiba': pct_wiba,
}


def ampel(p: float | None) -> str:
    if p is None:
        return 'grau'
    return 'gruen' if p >= 70 else 'orange' if p >= 40 else 'rot'


def _tom(projekt: str) -> dict[str, Any] | None:
    from dsgvo import tom_katalog as tk
    items = tk.list_massnahmen(_db('dsgvo'), projekt)
    if not items:
        return None
    wiba = sum(1 for m in items if m.get('status_quelle') == 'wiba')
    return {'anzahl': len(items),
            'pct': round(sum(int(m.get('status') or 0) for m in items) / (5 * len(items)) * 100, 1),
            'aus_wiba': wiba, 'mit_umsetzung': sum(1 for m in items if (m.get('umsetzung') or '').strip())}


def _aufgaben(projekt: str) -> list[dict[str, Any]]:
    from dsgvo.dsms_cockpit import build_cockpit
    return list(build_cockpit(_db('dsgvo'), projekt).get('offene_aufgaben') or [])


def _berichte(modul: str, projekte: list[str], limit: int = 5) -> list[dict[str, Any]]:
    from shared.reports.core import list_runs
    out = []
    for p in projekte:
        for r in _safe(lambda p=p: list_runs(_db(modul), projekt=p, limit=limit), []):
            if r.get('status') == 'finished':
                out.append({'modul': modul, 'projekt': p, 'id': r.get('id'), 'typ': r.get('typ'),
                            'format': r.get('format'), 'dateiname': r.get('dateiname'),
                            'erstellt': str(r.get('created_at') or r.get('erstellt_am') or '')})
    return out


def build_uebersicht(firma: str) -> dict[str, Any]:
    """Gesamtüberblick einer Firma (siehe Moduldoku)."""
    from firmen.db import load_firma, list_produkte
    rec = load_firma(_db('firmen'), firma)
    if not rec:
        raise LookupError('Firma nicht gefunden')
    firmen_id = rec.get('id')
    firmen_id = int(firmen_id) if firmen_id is not None else None

    module: list[dict[str, Any]] = []
    berichte: list[dict[str, Any]] = []
    aufgaben: list[dict[str, Any]] = []
    tom: list[dict[str, Any]] = []
    for key, (label, _t, _c, route) in MODULE.items():
        aktiv = bool(rec.get(f'module_{key}', 1))
        projekte = _safe(lambda key=key: module_projekte(key, firma, firmen_id, rec.get('unternehmen', '')), [])
        # AI Act: Organisation mit KI-Systemen hat keine eigenen Anforderungen (#1562)
        if key == 'ai_act' and any(p['meta'].get('scope') == 'system' for p in projekte):
            projekte = [p for p in projekte if p['meta'].get('scope') == 'system']
        eintraege = []
        for p in projekte:
            e = {'name': p['name'], 'produkt': p.get('produkt') or '', 'framework': p.get('framework') or ''}
            if key in PCT:
                e['pct'] = _safe(lambda p=p: PCT[key](p['name']), None)
            eintraege.append(e)
            if key == 'dsgvo':
                t = _safe(lambda p=p: _tom(p['name']), None)
                if t:
                    tom.append({'projekt': p['name'], **t})
                for a in _safe(lambda p=p: _aufgaben(p['name']), []):
                    aufgaben.append({'modul': 'DSGVO', 'projekt': p['name'], **a})
        werte = [e['pct'] for e in eintraege if e.get('pct') is not None]
        pct = round(sum(werte) / len(werte), 1) if werte else None
        module.append({'key': key, 'label': label, 'route': route, 'aktiv': aktiv,
                       'projekte': eintraege, 'pct': pct, 'ampel': ampel(pct)})
        berichte += _berichte(key, [p['name'] for p in projekte])

    # Risiko-Cockpit (firmenweit, read-only)
    risiken: dict[str, Any] = {'total': 0, 'by_severity': {}, 'by_source': {}, 'top': [], 'unassigned': firmen_id is None}
    if firmen_id is not None:
        def _cockpit():
            from shared.risk_cockpit import build_cockpit
            return build_cockpit(firmen_id, rb_db=_db('risikobewertung'), cra_db=_db('cra'), soc_db=_db('soc'))
        c = _safe(_cockpit, None)
        if c:
            s = c.get('summary') or {}
            risiken.update({'total': s.get('total', 0), 'by_severity': s.get('by_severity', {}),
                            'by_source': s.get('by_source', {}),
                            'top': [{k: it.get(k) for k in ('source', 'projekt', 'ref', 'titel', 'severity')}
                                    for it in (c.get('items') or [])[:6]]})

    rb = next((m for m in module if m['key'] == 'risikobewertung'), None)
    if rb:  # Risikobewertung: Anzahl Risiken statt Reifegrad
        from risikobewertung.db import load_risiken
        for e in rb['projekte']:
            rs = _safe(lambda e=e: load_risiken(_db('risikobewertung'), e['name']), [])
            e['risiken'] = len(rs)
            e['offen'] = sum(1 for r in rs if not r.get('is_resolved'))
            e['unbewertet'] = sum(1 for r in rs if not r.get('risiko_label'))

    bewertbar = [m['pct'] for m in module if m['pct'] is not None and m['key'] in PCT]
    gesamt = round(sum(bewertbar) / len(bewertbar), 1) if bewertbar else None
    berichte.sort(key=lambda b: (b.get('erstellt') or '', b.get('id') or 0), reverse=True)

    produkte = _safe(lambda: list_produkte(_db('firmen'), firma), [])
    def _nachweise() -> int:
        from evidence.db import list_documents
        return len(list_documents(_db('evidence'), firmen_id=firma))
    nachweise = _safe(_nachweise, 0)
    pentest = _safe(lambda: _pentest(firma), None)
    return {
        'firma': firma, 'firmen_id': firmen_id, 'unternehmen': rec.get('unternehmen', ''),
        'berater': rec.get('berater', ''),
        'gesamt_pct': gesamt, 'gesamt_ampel': ampel(gesamt),
        'module': module, 'risiken': risiken, 'tom': tom,
        'aufgaben': aufgaben[:10], 'aufgaben_gesamt': len(aufgaben),
        'berichte': berichte[:8],
        'produkte': [{'name': p.get('name'), 'produktklasse': p.get('produktklasse')} for p in produkte],
        'nachweise': nachweise,
        'pentest': pentest,
    }


def _pentest(firma: str) -> dict[str, Any]:
    """Pentest-Berichte der Firma (#1582): Anzahl, offene Findings je Schwere, letzter Bericht."""
    from pentest.db import DB_PATH, SCHWEREN, list_berichte
    berichte = list_berichte(DB_PATH, firma)
    offen = {s: 0 for s in SCHWEREN}
    for b in berichte:
        for s, n in (b.get('zaehler') or {}).get('offen_nach_schwere', {}).items():
            offen[s] = offen.get(s, 0) + n
    letzter = berichte[0] if berichte else None
    return {'berichte': len(berichte), 'offen': sum(offen.values()), 'offen_nach_schwere': offen,
            'letzter': {k: letzter.get(k) for k in ('id', 'titel', 'art', 'datum_bis', 'pruefer')}
            if letzter else None}
