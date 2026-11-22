"""Mandanten-/Abrechnungsreport (#1706).

Beantwortet die Frage, die das Wholesale-Modell braucht: *Welche Mandanten hat
der Lizenznehmer diesen Monat gebucht, und was kostet das?*

Begriffsdefinition (bewusst hier kodiert, damit sie vertraglich zitierbar ist):

**Mandant** — ein nicht gelöschter Datensatz in ``firmen``.

**Gebuchtes Modul** — ein Modul, dessen Schalter am Mandanten (``firmen.module_*``)
an ist. Das ist die kaufmännische Buchung; sie ist unabhängig davon, ob schon
gearbeitet wurde. Zusatzmodule, die die Lizenz gar nicht umfasst, werden als
``nicht_lizenziert`` ausgewiesen und **nicht** berechnet.

**Abrechnungsrelevant (aktiv)** — der Mandant ist nicht gelöscht **und** es
existiert in mindestens einem Modul ein Projekt. Ein angelegter, aber nie
bespielter Mandant kostet nichts; damit kann der Lizenznehmer Mandanten anlegen,
ohne sofort zu zahlen, und es gibt keinen Streit über „Testkunden".

**Ruhend** — abrechnungsrelevant, aber seit ``inaktiv_ab_tagen`` (Default 180)
keine Projektänderung mehr. Bleibt abrechenbar, wird aber separat ausgewiesen,
damit Karteileichen sichtbar sind.

Der Report ist read-only und best effort: ein fehlendes Modul-Schema darf ihn
nie verhindern.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from shared.licensing.modules import (
    BASE_MODULES,
    FIRMEN_MODULE_COLUMNS,
    MODULE_LABELS,
    SELLABLE_MODULES,
    billable_modules,
)

DB_DIR = Path('data/db')

#: kanonisches Modul → (DB-Datei, Projekt-Tabelle, Firmen-Namensspalte)
USAGE_MODULES: dict[str, tuple[str, str, str]] = {
    'cra': ('cra.sqlite', 'cra_projekte', 'unternehmen'),
    'nis2': ('nis2.sqlite', 'nis2_projekte', 'unternehmen'),
    'aiact': ('ai_act.sqlite', 'ai_act_projekte', 'organisation'),
    'dsgvo': ('dsgvo.sqlite', 'dsgvo_projekte', 'unternehmen'),
    'wiba': ('wiba.sqlite', 'wiba_projekte', 'unternehmen'),
    'risikobewertung': ('risikobewertung.sqlite', 'rb_projekte', 'unternehmen'),
    # Tabellenname historisch: das Compliance-Audit war bis v7.4.0 Teil des
    # Gutachten-Moduls. Eigener Lizenzschluessel, aber dieselben Tabellen.
    'compliance_audit': ('gutachten.sqlite', 'gutachten_projects', 'unternehmen'),
}

DEFAULT_INAKTIV_AB_TAGEN = 180


# ── Hilfen ───────────────────────────────────────────────────────────────────

def _norm(value: Any) -> str:
    return ' '.join(str(value or '').casefold().split())


def _firmen_rows(db_dir: Path) -> list[dict[str, Any]]:
    """Alle nicht gelöschten Firmen in **einer** Abfrage (kein N+1)."""
    from shared.risk_cockpit import _open_ro, _table_columns

    con = _open_ro(db_dir / 'firmen.sqlite', 'firmen')
    if con is None:
        return []
    try:
        cols = _table_columns(con, 'firmen')
        wanted = ['id', 'name', 'unternehmen', 'berater', 'created_at', 'updated_at']
        # `sel` entsteht ausschließlich aus den hartkodierten Namen in `wanted`
        # bzw. FIRMEN_MODULE_COLUMNS, geschnitten mit den real vorhandenen Spalten.
        # Es gelangt kein Eingabewert in das Statement — Tabellenname ist literal.
        sel = [c for c in wanted if c in cols]
        sel += [c for c in FIRMEN_MODULE_COLUMNS.values() if c in cols]
        rows = con.execute(
            f"SELECT {', '.join(sel)} FROM firmen "  # nosec B608 — nur Konstanten
            "WHERE COALESCE(is_deleted, 0) = 0 ORDER BY LOWER(name)"
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:  # noqa: BLE001 — best effort
        return []
    finally:
        con.close()


def _projekt_rows(modul: str, db_dir: Path) -> list[dict[str, Any]]:
    """Projekte eines Moduls: ``name``, ``firmen_id``, Firmenname, ``updated_at``."""
    from shared.risk_cockpit import _open_ro, _table_columns

    dbfile, table, firm_col = USAGE_MODULES[modul]
    con = _open_ro(db_dir / dbfile, table)
    if con is None:
        return []
    try:
        cols = _table_columns(con, table)
        if 'name' not in cols:
            return []
        # Spalten: hartkodierte Kandidaten ∩ information_schema. Tabelle: Konstante
        # aus USAGE_MODULES. Keine Eingabewerte im Statement.
        sel = ['name'] + [c for c in (firm_col, 'firmen_id', 'updated_at') if c in cols]
        rows = con.execute(
            f"SELECT {', '.join(sel)} FROM {table}").fetchall()  # nosec B608 — nur Konstanten
        out = []
        for r in rows:
            d = dict(r)
            out.append({
                'name': d.get('name') or '',
                'firma_name': d.get(firm_col) or '',
                'firmen_id': d.get('firmen_id'),
                'updated_at': d.get('updated_at') or '',
            })
        return out
    except Exception:  # noqa: BLE001 — best effort
        return []
    finally:
        con.close()


def _assign(projekte: list[dict[str, Any]],
            by_id: dict[int, str], by_name: dict[str, str]) -> dict[str, list[dict[str, Any]]]:
    """Projekte den Firmen zuordnen: ``firmen_id`` (S1-FK) → Firmenname → Projektname.

    Returns: Firmenname → Projektliste. Nicht zuordenbare Projekte landen
    unter dem Schlüssel ``''`` (Waisen).
    """
    out: dict[str, list[dict[str, Any]]] = {}
    for p in projekte:
        firma = ''
        fid = p.get('firmen_id')
        if fid is not None:
            try:
                firma = by_id.get(int(fid), '')
            except (TypeError, ValueError):
                firma = ''
        if not firma:
            firma = by_name.get(_norm(p.get('firma_name')), '')
        if not firma:
            # Auto-Anlage (#430) benennt Modulprojekte nach der Firma.
            firma = by_name.get(_norm(p.get('name')), '')
        out.setdefault(firma, []).append(p)
    return out


def _max_datum(werte: list[str]) -> str:
    gefiltert = [w for w in werte if w]
    return max(gefiltert) if gefiltert else ''


def _tage_her(stamp: str) -> int | None:
    """Tage seit einem ISO-Zeitstempel; ``None`` wenn nicht parsebar."""
    if not stamp:
        return None
    text = str(stamp).strip().replace(' ', 'T')
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        try:
            dt = datetime.strptime(text[:10], '%Y-%m-%d')
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - dt).days)


# ── Report ───────────────────────────────────────────────────────────────────

def build_usage(*, db_dir: Path | None = None,
                lizenz_module: 'set[str] | None' = None,
                inaktiv_ab_tagen: int = DEFAULT_INAKTIV_AB_TAGEN) -> dict[str, Any]:
    """Mandanten-Nutzungsreport zum Stichtag „jetzt".

    **Ohne Beträge** (#1821). Der Report sagt, *was* genutzt wird — Mandanten,
    gebuchte Module, abrechnungsrelevant oder ruhend. Was das kostet, rechnet
    der Lizenzserver aus demselben Inventar, das der Heartbeat ohnehin meldet.
    Ein Preisblatt in der Installation des Kunden wäre eine zweite Preisliste
    neben der verbindlichen — und die beiden waren bereits auseinandergelaufen.

    Args:
        lizenz_module: Modul-Whitelist der Lizenz (``None`` = Wildcard ``*``).
        inaktiv_ab_tagen: ab wie vielen Tagen ohne Projektänderung „ruhend".
    """
    db_dir = db_dir or DB_DIR
    abrechenbar = billable_modules(lizenz_module)

    firmen = _firmen_rows(db_dir)
    by_id: dict[int, str] = {}
    by_name: dict[str, str] = {}
    for f in firmen:
        name = f.get('name') or ''
        if f.get('id') is not None:
            try:
                by_id[int(f['id'])] = name
            except (TypeError, ValueError):
                pass
        by_name.setdefault(_norm(name), name)
        if f.get('unternehmen'):
            by_name.setdefault(_norm(f['unternehmen']), name)

    # Projekte je Modul einmal laden und zuordnen.
    zuordnung: dict[str, dict[str, list[dict[str, Any]]]] = {}
    waisen: dict[str, list[str]] = {}
    for modul in USAGE_MODULES:
        gruppen = _assign(_projekt_rows(modul, db_dir), by_id, by_name)
        waise = [p['name'] for p in gruppen.pop('', [])]
        if waise:
            waisen[modul] = sorted(waise)
        zuordnung[modul] = gruppen

    # Erst alle Mandanten bewerten — die Staffel braucht die Gesamtzahl.
    vorlauf: list[dict[str, Any]] = []
    for f in firmen:
        name = f.get('name') or ''
        gebucht, nicht_lizenziert = [], []
        for modul in (*BASE_MODULES, *SELLABLE_MODULES):
            col = FIRMEN_MODULE_COLUMNS.get(modul)
            # Module ohne Firmen-Schalter (pentest) gelten als Teil des Grundpreises.
            an = True if col is None else bool(f.get(col, 1))
            if not an:
                continue
            if modul in SELLABLE_MODULES and modul not in abrechenbar:
                nicht_lizenziert.append(modul)
            else:
                gebucht.append(modul)

        projekte: dict[str, int] = {}
        stempel: list[str] = []
        for modul in USAGE_MODULES:
            liste = zuordnung[modul].get(name) or []
            if liste:
                projekte[modul] = len(liste)
                stempel.extend(p.get('updated_at') or '' for p in liste)

        letzte = _max_datum(stempel)
        tage = _tage_her(letzte)
        aktiv = bool(projekte)
        vorlauf.append({
            'firmen_id': f.get('id'),
            'name': name,
            'unternehmen': f.get('unternehmen') or '',
            'berater': f.get('berater') or '',
            'angelegt_am': f.get('created_at') or '',
            'module_gebucht': gebucht,
            'module_nicht_lizenziert': nicht_lizenziert,
            'module_genutzt': sorted(projekte),
            'projekte': projekte,
            'projekte_gesamt': sum(projekte.values()),
            'letzte_aktivitaet': letzte,
            'tage_seit_aktivitaet': tage,
            'aktiv': aktiv,
            'ruhend': bool(aktiv and tage is not None and tage > inaktiv_ab_tagen),
        })

    aktive = [m for m in vorlauf if m['aktiv']]

    return {
        'stichtag': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        'erzeugt_am': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'definition': {
            'aktiv': 'nicht gelöscht und mindestens ein Modulprojekt vorhanden',
            'ruhend': f'aktiv, aber > {inaktiv_ab_tagen} Tage ohne Projektänderung',
            'inaktiv_ab_tagen': inaktiv_ab_tagen,
        },
        'lizenz_module_abrechenbar': abrechenbar,
        'summe': {
            'mandanten_gesamt': len(vorlauf),
            'mandanten_aktiv': len(aktive),
            'mandanten_ruhend': sum(1 for m in vorlauf if m['ruhend']),
        },
        'mandanten': vorlauf,
        'waisen': waisen,
    }


def usage_csv(report: dict[str, Any]) -> str:
    """Nutzungsreport als CSV (Semikolon, für Excel). Ohne Beträge (#1821)."""
    module = [*BASE_MODULES, *SELLABLE_MODULES]
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=';', quoting=csv.QUOTE_MINIMAL,
                   lineterminator='\r\n')
    w.writerow([
        'Stichtag', 'Firmen-ID', 'Mandant', 'Unternehmen', 'Berater',
        'Abrechnungsrelevant', 'Ruhend', 'Projekte',
        *[f'Modul {MODULE_LABELS.get(m, m)}' for m in module],
    ])
    stichtag = report.get('stichtag', '')
    for m in report.get('mandanten') or []:
        gebucht = set(m.get('module_gebucht') or [])
        w.writerow([
            stichtag, m.get('firmen_id') or '', m.get('name', ''),
            m.get('unternehmen', ''), m.get('berater', ''),
            'ja' if m.get('aktiv') else 'nein',
            'ja' if m.get('ruhend') else 'nein',
            m.get('projekte_gesamt', 0),
            *['ja' if mod in gebucht else 'nein' for mod in module],
        ])
    s = report.get('summe') or {}
    w.writerow([])
    w.writerow(['SUMME', '', f"{s.get('mandanten_aktiv', 0)} aktiv von "
                             f"{s.get('mandanten_gesamt', 0)}", '', '', '', '',
                '', *[''] * len(module)])
    return buf.getvalue()


def count_firmen(db_dir: Path | None = None) -> tuple[int, int]:
    """``(mandanten_gesamt, mandanten_aktiv)`` — günstig, für den Heartbeat."""
    db_dir = db_dir or DB_DIR
    firmen = _firmen_rows(db_dir)
    if not firmen:
        return 0, 0
    by_id: dict[int, str] = {}
    by_name: dict[str, str] = {}
    for f in firmen:
        name = f.get('name') or ''
        if f.get('id') is not None:
            try:
                by_id[int(f['id'])] = name
            except (TypeError, ValueError):
                pass
        by_name.setdefault(_norm(name), name)
        if f.get('unternehmen'):
            by_name.setdefault(_norm(f['unternehmen']), name)
    mit_projekt: set[str] = set()
    for modul in USAGE_MODULES:
        gruppen = _assign(_projekt_rows(modul, db_dir), by_id, by_name)
        mit_projekt.update(k for k in gruppen if k)
    return len(firmen), len(mit_projekt)


def naechste_stichtage(anzahl: int = 3) -> list[str]:
    """Die nächsten Monatsersten — Vorschlag für den Abrechnungslauf."""
    heute = datetime.now(timezone.utc).date()
    out: list[str] = []
    cursor = heute.replace(day=1)
    while len(out) < anzahl:
        cursor = (cursor + timedelta(days=32)).replace(day=1)
        out.append(cursor.isoformat())
    return out
