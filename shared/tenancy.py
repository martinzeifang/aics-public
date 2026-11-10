"""Mandantenfähigkeit: Listen-Scoping und Selbstprüfung (#1707).

Das Objekt-RBAC aus #1185 (``allowed_firmen``) greift bisher nur auf
**Detail**-Routen: der Guard löst die Firma aus den URL-Parametern auf. Bei den
``GET /api/<modul>/projekte``-**Listen** gibt es keine URL-Firma — sie liefern
deshalb bis v7.3.0 alle Projekte aller Mandanten aus. Für einen Nutzer mit
Firmen-Whitelist ist schon die Projektliste eine Preisgabe fremder
Mandantennamen.

Dieses Modul schließt die Lücke:

* :func:`allowed_firma_keys` löst die Whitelist einmal je Request in die
  Namensschlüssel der freigegebenen Firmen auf.
* :func:`scope_projekt_items` filtert eine serialisierte Projektliste darauf.
* :func:`tenancy_report` prüft die Installation auf Mandanten-Hygiene
  (Projekte ohne ``firmen_id``, Waisen) und liefert einen Score.

Scoping-Regel bei aktiver Whitelist: ein Projekt, dessen Firma **nicht
bestimmbar** ist, wird **ausgeblendet** (fail-closed). Anders als beim
Detail-Guard ist das hier richtig — ein Projekt ohne Mandantenzuordnung gehört
keinem der freigegebenen Mandanten. Nutzer ohne Whitelist (``None``, u. a.
Admins) sehen weiterhin alles.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

DB_DIR = Path('data/db')

#: Felder einer serialisierten Projektzeile, die den Firmennamen tragen können.
FIRMA_FELDER: tuple[str, ...] = ('unternehmen', 'organisation', 'company', 'firma')


def _norm(value: Any) -> str:
    return ' '.join(str(value or '').casefold().split())


# ── Listen-Scoping ───────────────────────────────────────────────────────────

def allowed_firma_keys(claims: dict[str, Any] | None,
                       db_dir: Path | None = None) -> set[str] | None:
    """Namensschlüssel der freigegebenen Firmen, oder ``None`` = keine Einschränkung.

    Der Schlüsselsatz enthält je Firma den Namen **und** die Unternehmensbezeichnung
    normalisiert, weil die Modulprojekte je nach Entstehungsweg das eine oder das
    andere in ``unternehmen``/``organisation`` tragen (Auto-Anlage #430).
    """
    allowed = (claims or {}).get('allowed_firmen')
    if not isinstance(allowed, list):
        return None  # None = alle Firmen (z. B. Admin)
    try:
        ids = {int(x) for x in allowed}
    except (TypeError, ValueError):
        return None
    if not ids:
        return set()  # leere Whitelist = kein Mandant freigegeben

    from shared.risk_cockpit import _open_ro

    keys: set[str] = set()
    con = _open_ro((db_dir or DB_DIR) / 'firmen.sqlite', 'firmen')
    if con is None:
        return set()
    try:
        rows = con.execute(
            "SELECT id, name, unternehmen FROM firmen "
            "WHERE COALESCE(is_deleted, 0) = 0"
        ).fetchall()
    except Exception:  # noqa: BLE001 — ohne Firmentabelle nichts freigeben
        return set()
    finally:
        con.close()
    for row in rows:
        try:
            if int(row[0]) not in ids:
                continue
        except (TypeError, ValueError):
            continue
        for value in (row[1], row[2]):
            if value and str(value).strip():
                keys.add(_norm(value))
    return keys


def item_firma_keys(item: dict[str, Any]) -> set[str]:
    """Alle Namensschlüssel, unter denen ein Projekt einem Mandanten gehören kann."""
    keys = {_norm(item.get(f)) for f in FIRMA_FELDER if item.get(f)}
    # Auto-Anlage (#430) benennt Modulprojekte nach der Firma.
    if item.get('name'):
        keys.add(_norm(item['name']))
    return {k for k in keys if k}


def scope_projekt_items(items: list[dict[str, Any]], claims: dict[str, Any] | None,
                        db_dir: Path | None = None) -> list[dict[str, Any]]:
    """Projektliste auf die für den Nutzer freigegebenen Mandanten filtern."""
    keys = allowed_firma_keys(claims, db_dir)
    if keys is None:
        return items
    return [it for it in items if item_firma_keys(it) & keys]


def scope_current_request(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Wie :func:`scope_projekt_items`, holt die Claims aus dem aktiven Request.

    Best effort: ohne JWT-Kontext (Tests, CLI) wird nichts gefiltert.
    """
    try:
        from flask_jwt_extended import get_jwt
        claims = get_jwt() or {}
    except Exception:  # noqa: BLE001 — kein Request-/JWT-Kontext
        return items
    try:
        return scope_projekt_items(items, claims)
    except Exception:  # noqa: BLE001 — Scoping darf die Liste nie kaputt machen
        return items


# ── Selbstprüfung ────────────────────────────────────────────────────────────

def tenancy_report(db_dir: Path | None = None) -> dict[str, Any]:
    """Mandanten-Hygiene je Modul-Projekttabelle + Gesamtscore.

    Befunde:
      * ``ohne_firmen_id`` — Projekt trägt einen Firmennamen, aber keine ``firmen_id``
        (Risiko-Cockpit und Objekt-RBAC greifen dort nicht).
      * ``ohne_firma`` — Projekt trägt überhaupt keine Mandantenzuordnung.
      * ``waisen`` — Firmenname gesetzt, aber keine passende Firma vorhanden.
    """
    from shared.licensing.usage import USAGE_MODULES
    from shared.risk_cockpit import _open_ro, _table_columns

    db_dir = db_dir or DB_DIR

    # Bekannte Firmennamen/Unternehmen (für die Waisen-Erkennung).
    bekannt: set[str] = set()
    con = _open_ro(db_dir / 'firmen.sqlite', 'firmen')
    if con is not None:
        try:
            for row in con.execute(
                "SELECT name, unternehmen FROM firmen WHERE COALESCE(is_deleted,0)=0"
            ).fetchall():
                for value in (row[0], row[1]):
                    if value and str(value).strip():
                        bekannt.add(_norm(value))
        except Exception:  # noqa: BLE001
            pass
        finally:
            con.close()

    module: dict[str, Any] = {}
    befunde: list[dict[str, Any]] = []
    gesamt = zugeordnet = 0

    for modul, (dbfile, table, firm_col) in USAGE_MODULES.items():
        eintrag = {
            'tabelle': table, 'projekte': 0, 'mit_firmen_id': 0,
            'ohne_firmen_id': [], 'ohne_firma': [], 'waisen': [],
            'verfuegbar': False,
        }
        module[modul] = eintrag
        mcon = _open_ro(db_dir / dbfile, table)
        if mcon is None:
            continue
        try:
            cols = _table_columns(mcon, table)
            if 'name' not in cols:
                continue
            eintrag['verfuegbar'] = True
            # Spalten: hartkodierte Kandidaten ∩ information_schema. Tabelle: Konstante
            # aus USAGE_MODULES. Keine Eingabewerte im Statement.
            sel = ['name'] + [c for c in (firm_col, 'firmen_id') if c in cols]
            rows = [dict(r) for r in mcon.execute(
                f"SELECT {', '.join(sel)} FROM {table}").fetchall()]  # nosec B608
        except Exception:  # noqa: BLE001
            continue
        finally:
            mcon.close()

        for r in rows:
            name = r.get('name') or ''
            firma = str(r.get(firm_col) or '').strip()
            fid = r.get('firmen_id')
            eintrag['projekte'] += 1
            gesamt += 1
            if fid is not None:
                eintrag['mit_firmen_id'] += 1
                zugeordnet += 1
                continue
            # Projektname = Firmenname ist eine gültige, wenn auch implizite Zuordnung.
            if not firma and _norm(name) not in bekannt:
                eintrag['ohne_firma'].append(name)
            elif firma and _norm(firma) not in bekannt:
                eintrag['waisen'].append({'projekt': name, 'firma': firma})
            else:
                eintrag['ohne_firmen_id'].append(name)

        for key, text in (
            ('ohne_firma', 'ohne jede Mandantenzuordnung'),
            ('waisen', 'mit unbekanntem Firmennamen'),
            ('ohne_firmen_id', 'ohne firmen_id (nur Namens-Match)'),
        ):
            anzahl = len(eintrag[key])
            if anzahl:
                befunde.append({
                    'modul': modul, 'art': key, 'anzahl': anzahl,
                    'text': f'{MODUL_TEXT.get(modul, modul)}: {anzahl} Projekt(e) {text}.',
                    'schwere': 'hoch' if key in ('ohne_firma', 'waisen') else 'mittel',
                })

    score = round(100.0 * zugeordnet / gesamt, 1) if gesamt else 100.0
    return {
        'score_prozent': score,
        'projekte_gesamt': gesamt,
        'projekte_mit_firmen_id': zugeordnet,
        'module': module,
        'befunde': sorted(befunde, key=lambda b: (b['schwere'] != 'hoch', -b['anzahl'])),
        'hinweis': ('Projekte ohne firmen_id lassen sich im Admin unter '
                    '„Firmen-Zuordnung" per Backfill nachziehen.'),
    }


MODUL_TEXT: dict[str, str] = {
    'cra': 'CRA', 'nis2': 'NIS2', 'aiact': 'AI Act', 'dsgvo': 'DSGVO',
    'wiba': 'WiBA', 'risikobewertung': 'Risikobewertung',
}
