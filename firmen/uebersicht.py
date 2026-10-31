"""Firmen-Gesamtüberblick (v7.0.0): Umsetzungsgrad aller Module, Risiko-Cockpit,
DSGVO-TOM/WiBA, offene Aufgaben, Produkte, Nachweise, Berichte und CRA-Release-
Vorgänge (#1749) einer Firma.

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


# ── CRA-Release-Vorgänge je Mandant (#1749) ───────────────────────────────────
#
# Die Release-Prüfung (#1742) hängt am CRA-Projekt, also am **Produkt**. Wer CRA
# as a Service betreibt, braucht die Gegenrichtung: welcher Mandant hat gerade
# ein Release in Prüfung, welches ist rot, wo wartet eine Freigabe.
#
# Hier wird nichts gerechnet, was das Modul rechnet — Vorgänge kommen aus
# ``konformitaet_db.list_konformitaet``, die Phase-1-Feststellung aus
# ``release_db.get_release``, die Ampel aus ``konformitaet_gate.evaluate`` bzw.
# dem eingefrorenen Stand. Ein eigener Rechenweg würde irgendwann eine andere
# Zahl zeigen als das Modul (die Lehre aus #1726), und das ist in einem
# Compliance-Werkzeug ein Vertrauensschaden, kein Schönheitsfehler.

#: Zustände, in denen am Vorgang noch Arbeit liegt.
OFFENE_RELEASE_STATUS: tuple[str, ...] = ('entwurf', 'in_pruefung', 'zurueckgewiesen')

#: Zustand, in dem auf eine Freigabe durch Compliance gewartet wird.
WARTET_STATUS = 'in_pruefung'

#: Wie viele Vorgänge je Produkt die Übersicht zeigt. Ein Produkt mit 40
#: Releases soll die Seite nicht fluten — die jüngsten sind die, an denen
#: gearbeitet wird.
RELEASES_JE_PRODUKT = 5


def _vorgang_recency(v: dict[str, Any]) -> tuple[str, str]:
    """Sortierschlüssel „jüngster zuerst".

    Bewusst nicht die Release-Version: ``1.10.0`` sortiert als String vor
    ``1.9.0``, und eine semantische Versionssortierung wäre ein zweiter
    Rechenweg für etwas, das die Zeitstempel bereits beantworten.
    """
    zeit = (v.get('veroeffentlicht_am') or v.get('geprueft_am')
            or v.get('eingereicht_am') or v.get('updated_at')
            or v.get('created_at') or '')
    return (str(zeit), str(v.get('release_version') or ''))


def _eingefrorene_ampel(v: dict[str, Any]) -> str:
    """Ampel aus dem bei der Einreichung eingefrorenen Rechenstand (``gate_json``).

    Für einen eingereichten Vorgang ist dieser Wert nicht nur der billigere,
    sondern der **richtige**: Geprüft und freigegeben wurde gegen diesen Stand,
    nicht gegen die Datenlage von heute.
    """
    gate = v.get('gate')
    ampel_wert = str((gate or {}).get('ampel') or '') if isinstance(gate, dict) else ''
    return ampel_wert if ampel_wert in ('gruen', 'bedingt', 'rot') else ''


def _vorgang_offen(status: str) -> bool:
    return status in OFFENE_RELEASE_STATUS


def cra_releases_fuer_projekte(projekte: list[Any], *, db: Path | None = None,
                               live_gate: bool = True) -> list[dict[str, Any]]:
    """Release-Vorgänge je CRA-Produkt, read-only.

    **Ampel-Kosten.** ``konformitaet_gate.evaluate`` liest Anforderungen,
    Schwachstellen, Anhang VII, DoC, SBOM, Support-Zeitraum und Meldefristen.
    Ein Lauf je Version je Produkt je Mandant wäre eine Ladebremse, und eine
    Übersicht, die 30 Sekunden lädt, benutzt niemand. Zwei Regeln begrenzen das:

    1. Eingereichte Vorgänge tragen ihren eingefrorenen Stand (``gate_json``,
       gesetzt von :func:`cra.konformitaet_db.einreichen`) — der wird gelesen,
       nicht neu gerechnet.
    2. Nur der **jüngste noch offene Vorgang ohne** eingefrorenen Stand (also
       ein Entwurf) löst einen Lauf aus. Damit gilt: höchstens **ein**
       ``evaluate`` je Produkt, unabhängig von der Zahl der Releases.

    ``live_gate=False`` schaltet den Lauf ganz ab (Listenansichten).

    ``db`` steuert nur die Vorgangs- und Phase-1-Abfragen; ``evaluate`` nutzt
    stets die CRA-DB des Moduls (``konformitaet_gate.CRA_DB``). Im Betrieb ist
    das dieselbe Datenbank — ein abweichender Pfad wirkt also nicht auf die
    Ampel.
    """
    from cra import konformitaet_db as kdb
    from cra import konformitaet_gate as kgate
    from cra import release_db as rdb

    db = db or _db('cra')
    out: list[dict[str, Any]] = []
    for p in projekte:
        name = str(p['name'] if isinstance(p, dict) else p)
        produkt = str((p.get('produkt') or '') if isinstance(p, dict) else '')
        alle = _safe(lambda name=name: kdb.list_konformitaet(db, name), [])
        # Der Datensatz ohne Version ist der Produkt-Datensatz (Phase 1,
        # Bewertungsweg/CE) und kein Release-Vorgang.
        vorgaenge = [v for v in alle if str(v.get('release_version') or '').strip()]
        vorgaenge.sort(key=_vorgang_recency, reverse=True)

        gate_frei = bool(live_gate)   # ein Lauf je Produkt, nicht je Vorgang
        eintraege: list[dict[str, Any]] = []
        for v in vorgaenge[:RELEASES_JE_PRODUKT]:
            status = str(v.get('freigabe_status') or 'entwurf')
            offen = _vorgang_offen(status)
            ampel_wert, quelle = _eingefrorene_ampel(v), 'eingefroren'
            if not ampel_wert and offen and gate_frei:
                gate_frei = False
                g = _safe(lambda name=name, v=v: kgate.evaluate(
                    name, version=str(v.get('release_version') or '')), {}) or {}
                ampel_wert, quelle = str(g.get('ampel') or ''), 'aktuell'
            if not ampel_wert:
                # Kein eingefrorener Stand und kein Lauf: „unbekannt" ist die
                # ehrliche Angabe. Ein Rückfall auf „grün" oder „rot" wäre eine
                # erfundene Zahl (#1741: fehlende Zahlen werden benannt).
                ampel_wert, quelle = '', 'unbekannt'
            eintraege.append({
                'projekt': name, 'produkt': produkt,
                'version': str(v.get('release_version') or ''),
                'status': status, 'offen': offen,
                'wartet_auf_freigabe': status == WARTET_STATUS,
                'ampel': ampel_wert, 'ampel_quelle': quelle,
                'erstellt_von': v.get('erstellt_von') or '',
                'geprueft_von': v.get('geprueft_von') or '',
                'freigegeben_von': v.get('freigegeben_von') or '',
                'eingereicht_am': v.get('eingereicht_am'),
                'geprueft_am': v.get('geprueft_am'),
                'veroeffentlicht_am': v.get('veroeffentlicht_am'),
                'zurueckweisung_grund': v.get('zurueckweisung_grund') or '',
            })

        rel = _safe(lambda name=name: rdb.get_release(db, name), None) or {}
        out.append({
            'projekt': name, 'produkt': produkt,
            'bereit_status': rel.get('bereit_status') or 'offen',
            'bereit_am': rel.get('bereit_am'),
            'bereit_von': rel.get('bereit_von') or '',
            'aktuelle_version': rel.get('aktuelle_version') or '',
            'vorgaenge': eintraege,
            'vorgaenge_gesamt': len(vorgaenge),
        })
    return out


def releases_summe(produkte: list[dict[str, Any]]) -> dict[str, int]:
    """Kennzahlen über alle gezeigten Vorgänge einer Firma."""
    v = [x for p in produkte for x in p.get('vorgaenge') or []]
    return {'gesamt': len(v),
            'offen': sum(1 for x in v if x.get('offen')),
            'in_pruefung': sum(1 for x in v if x.get('wartet_auf_freigabe')),
            'rot': sum(1 for x in v if x.get('ampel') == 'rot')}


def _firma_fuer_projekt(projekt: dict[str, Any], firmen: list[dict[str, Any]]) -> str | None:
    """Mandant eines CRA-Projekts — gleiche Regel wie :func:`module_projekte`.

    ``None`` heißt „Firma nicht bestimmbar". Solche Projekte werden **nicht**
    irgendeinem Mandanten zugeschlagen (fail-closed, wie ``shared/tenancy.py``).
    """
    for f in firmen:
        fid = f.get('firmen_id')
        namen = {_norm(f.get('name'))}
        for feld in ('unternehmen', 'company'):
            if _norm(f.get(feld)):
                namen.add(_norm(f.get(feld)))
        if ((fid is not None and projekt.get('firmen_id') == fid)
                or _norm(projekt.get('unternehmen')) in namen
                or _norm(projekt.get('name')) == _norm(f.get('name'))):
            return str(f.get('name') or '')
    return None


def releases_offen_je_firma(firmen: list[dict[str, Any]], *,
                            db: Path | None = None) -> dict[str, dict[str, int]]:
    """Release-Kennzahlen je Mandant für die Mandanten-Übersicht (Spalte „Releases offen").

    Bewusst **nicht** über :func:`cra_releases_fuer_projekte`: auf einer Liste mit
    50+ Mandanten wären das eine Abfrage je Produkt je Firma, und ein
    ``evaluate``-Lauf hat auf einer Listenseite ohnehin nichts zu suchen. Gezählt
    werden deshalb nur die beiden Angaben, die ohne Rechenlauf vorliegen: der
    Vorgangs-Status und die **eingefrorene** Ampel. Kosten: zwei Abfragen
    insgesamt, unabhängig von der Zahl der Mandanten.

    Die Zählregel ist dieselbe wie in :func:`releases_summe` (gleiche
    Status-Konstanten, gleiche Gate-Quelle) — die Liste kann also keine andere
    Zahl zeigen als das Firmen-Dashboard für einen eingereichten Vorgang.

    Ergebnis: ``{Firmenname: {gesamt, offen, in_pruefung, rot}}``, nur für
    Mandanten mit mindestens einem CRA-Projekt (keine leeren Kacheln).
    """
    db = db or _db('cra')

    # Projekte: eine Abfrage für alle Mandanten.
    projekte: list[dict[str, Any]] = []
    con = _open_ro(db, 'cra_projekte')
    if con is not None:
        try:
            cols = _table_columns(con, 'cra_projekte')
            sel = ['name'] + [c for c in ('unternehmen', 'firmen_id') if c in cols]
            projekte = [dict(r) for r in con.execute(
                f"SELECT {', '.join(sel)} FROM cra_projekte").fetchall()]  # nosec B608
        except Exception:  # noqa: BLE001 — best effort, Modul kann fehlen
            projekte = []
        finally:
            con.close()

    projekt_firma: dict[str, str] = {}
    out: dict[str, dict[str, int]] = {}
    for pr in projekte:
        fname = _firma_fuer_projekt(pr, firmen)
        if not fname:
            continue
        projekt_firma[str(pr.get('name') or '')] = fname
        out.setdefault(fname, {'gesamt': 0, 'offen': 0, 'in_pruefung': 0, 'rot': 0})
    if not projekt_firma:
        return out

    # Vorgänge: eine Abfrage für alle Projekte. ``gate_json`` trägt den
    # eingefrorenen Stand; dieselbe Quelle wie ``_eingefrorene_ampel``.
    con = _open_ro(db, 'cra_konformitaet')
    if con is None:
        return out
    try:
        rows = [dict(r) for r in con.execute(
            "SELECT projekt_name, release_version, freigabe_status, gate_json "
            "FROM cra_konformitaet").fetchall()]
    except Exception:  # noqa: BLE001
        return out
    finally:
        con.close()

    for r in rows:
        if not str(r.get('release_version') or '').strip():
            continue  # Produkt-Datensatz (Phase 1), kein Release-Vorgang
        fname = projekt_firma.get(str(r.get('projekt_name') or ''))
        if not fname:
            continue
        status = str(r.get('freigabe_status') or 'entwurf')
        gate = _safe(lambda r=r: json.loads(r.get('gate_json') or '{}'), {})
        eintrag = out[fname]
        eintrag['gesamt'] += 1
        if _vorgang_offen(status):
            eintrag['offen'] += 1
        if status == WARTET_STATUS:
            eintrag['in_pruefung'] += 1
        if _eingefrorene_ampel({'gate': gate if isinstance(gate, dict) else {}}) == 'rot':
            eintrag['rot'] += 1
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
    cra_projekte: list[dict[str, Any]] = []
    for key, (label, _t, _c, route) in MODULE.items():
        aktiv = bool(rec.get(f'module_{key}', 1))
        projekte = _safe(lambda key=key: module_projekte(key, firma, firmen_id, rec.get('unternehmen', '')), [])
        # AI Act: Organisation mit KI-Systemen hat keine eigenen Anforderungen (#1562)
        if key == 'ai_act' and any(p['meta'].get('scope') == 'system' for p in projekte):
            projekte = [p for p in projekte if p['meta'].get('scope') == 'system']
        if key == 'cra':
            cra_projekte = projekte      # für den Release-Block (#1749)
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
            return build_cockpit(firmen_id, rb_db=_db('risikobewertung'), cra_db=_db('cra'))
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

    # #1749: Release-Vorgänge nur bei vorhandenem CRA-Projekt — ein Mandant ohne
    # CRA bekommt den Abschnitt gar nicht geliefert (keine leere Kachel).
    cra_releases: dict[str, Any] | None = None
    if cra_projekte:
        rel_produkte = _safe(lambda: cra_releases_fuer_projekte(cra_projekte), [])
        cra_releases = {'produkte': rel_produkte, **releases_summe(rel_produkte)}

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
        'cra_releases': cra_releases,
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
