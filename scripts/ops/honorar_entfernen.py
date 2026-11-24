#!/usr/bin/env python3
"""Die Honorar-Daten aus der Datenbank entfernen — von Hand, nicht im Deploy (#2119).

WARUM DAS NICHT DER RÜCKBAU SELBST TUT
--------------------------------------
Das Honorar-Thema ist mit #2119 aus dem Code entfernt (Tab, API, honorar.py,
JVEG/Rechnung, Feld ``honorarvereinbarung``). Die **Daten** nicht: Ein ``DROP
TABLE`` / ``DROP COLUMN`` ist nicht umkehrbar, und ein Release, das Daten
vernichtet, hat keinen Rückweg — das Vor-Image ließe sich einspielen, die
Zeilen nicht. Darum dieser Aufruf: ein Mensch, ein Zeitpunkt, eine Entscheidung.

VORGABE IST DER TROCKENLAUF
---------------------------
Ohne ``--confirm`` wird **nichts** gelöscht. Das Skript nennt die betroffenen
Objekte und ihre Zeilenzahlen. Vorher **sichern** (Administration → Sicherung).

    python3 scripts/ops/honorar_entfernen.py                 # zeigt nur
    python3 scripts/ops/honorar_entfernen.py --confirm        # löscht

``DATABASE_URL`` muss gesetzt sein.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

SCHEMA = "gutachten"
TABELLE = "gutachten_zeitbuch"
SPALTEN_TABELLE = "gerichtsgutachten"
SPALTE = "honorarvereinbarung"


def _tabelle_zeilen(cur) -> int | None:
    cur.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema=%s AND table_name=%s",
        (SCHEMA, TABELLE))
    if cur.fetchone() is None:
        return None
    cur.execute(f'SELECT COUNT(*) FROM "{SCHEMA}"."{TABELLE}"')  # nosec B608
    return int(cur.fetchone()[0])


def _spalte_belegt(cur) -> int | None:
    cur.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema=%s AND table_name=%s AND column_name=%s",
        (SCHEMA, SPALTEN_TABELLE, SPALTE))
    if cur.fetchone() is None:
        return None
    cur.execute(
        f'SELECT COUNT(*) FROM "{SCHEMA}"."{SPALTEN_TABELLE}" '
        f'WHERE TRIM(COALESCE("{SPALTE}", \'\')) <> \'\'')  # nosec B608
    return int(cur.fetchone()[0])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--confirm", action="store_true",
                    help="wirklich löschen (ohne diesen Schalter wird nur gezeigt)")
    args = ap.parse_args()

    from shared.db import get_pool

    pool = get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name=%s",
                        (SCHEMA,))
            if cur.fetchone() is None:
                print(f"Schema „{SCHEMA}“ existiert nicht — nichts zu tun.")
                return 0
            zeitbuch = _tabelle_zeilen(cur)
            spalte = _spalte_belegt(cur)

        print(f"Schema „{SCHEMA}“:")
        if zeitbuch is None:
            print(f"  Tabelle {TABELLE}: existiert nicht (nichts zu tun)")
        else:
            print(f"  Tabelle {TABELLE}: {zeitbuch} Zeile(n) → wird gelöscht (DROP TABLE)")
        if spalte is None:
            print(f"  Spalte {SPALTEN_TABELLE}.{SPALTE}: existiert nicht (nichts zu tun)")
        else:
            print(f"  Spalte {SPALTEN_TABELLE}.{SPALTE}: {spalte} belegte Zeile(n) → "
                  f"wird gelöscht (DROP COLUMN)")

        if zeitbuch is None and spalte is None:
            print("\nNichts zu entfernen.")
            return 0

        if not args.confirm:
            print("\nTrockenlauf — nichts gelöscht.")
            print("Vorher sichern, dann mit --confirm erneut aufrufen.")
            return 0

        with conn.cursor() as cur:
            if zeitbuch is not None:
                cur.execute(f'DROP TABLE IF EXISTS "{SCHEMA}"."{TABELLE}" CASCADE')  # nosec B608
            if spalte is not None:
                cur.execute(
                    f'ALTER TABLE "{SCHEMA}"."{SPALTEN_TABELLE}" '
                    f'DROP COLUMN IF EXISTS "{SPALTE}"')  # nosec B608
        conn.commit()
        print("\nHonorar-Daten entfernt.")
        try:
            from shared.audit import audit_event
            audit_event("admin.honorar.geloescht", module="admin",
                        details={"schema": SCHEMA, "tabelle": TABELLE, "spalte": SPALTE,
                                 "zeitbuch_zeilen": zeitbuch or 0,
                                 "grund": "Honorar entfernt (#2119)"})
        except Exception as e:  # noqa: BLE001
            print(f"  (Revisionseintrag fehlgeschlagen: {e})")
        return 0
    finally:
        pool.putconn(conn)  # #1808: nie pool.close()


if __name__ == "__main__":
    raise SystemExit(main())
