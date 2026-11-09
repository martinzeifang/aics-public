#!/usr/bin/env python3
"""Das ``soc``-Schema aus der Datenbank entfernen — von Hand, nicht im Deploy (#1905).

WARUM DAS NICHT DER RÜCKBAU SELBST TUT
--------------------------------------
Das SOC-Modul ist mit v8.3.0 aus dem Code entfernt. Seine Daten **nicht**:
Ein ``DROP SCHEMA`` ist nicht umkehrbar, und das Schema führt Vorfälle und
Meldetracks (Art. 23 NIS-2). Wer eine Nachweisakte verkauft, löscht keine
Nachweise im Rahmen eines Code-Rückbaus — und ein Release, das Daten
vernichtet, hat keinen Rückweg: Das Vor-Image ließe sich einspielen, die
Zeilen nicht.

Darum dieser Aufruf: ein Mensch, ein Zeitpunkt, eine Entscheidung.

VORGABE IST DER TROCKENLAUF
---------------------------
Ohne ``--confirm`` wird **nichts** gelöscht. Das Skript nennt die Tabellen und
ihre Zeilenzahlen, damit die Entscheidung auf Zahlen beruht und nicht auf der
Annahme, da sei schon nichts mehr. Vorher **sichern** (Administration →
Sicherung, oder ``GET /api/admin/backup``): Ein Archiv im Format 2 enthält das
Schema vollständig.

    python3 scripts/ops/soc_daten_entfernen.py                 # zeigt nur
    python3 scripts/ops/soc_daten_entfernen.py --confirm        # löscht

``DATABASE_URL`` muss gesetzt sein (wie für jeden anderen Zugriff auch).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

SCHEMA = "soc"


def _tabellen(cur) -> list[tuple[str, int]]:
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = %s AND table_type = 'BASE TABLE' "
        "ORDER BY table_name", (SCHEMA,))
    namen = [r[0] for r in cur.fetchall()]
    out: list[tuple[str, int]] = []
    for name in namen:
        # Bezeichner kommen aus dem Katalog, nicht aus einer Eingabe — die
        # Regel aus #1785 (`_q`) gilt trotzdem: Positivliste statt Vertrauen.
        if not name.replace("_", "").isalnum():
            print(f"  ! Tabellenname übersprungen (unerwartete Zeichen): {name!r}")
            continue
        cur.execute(f'SELECT COUNT(*) FROM "{SCHEMA}"."{name}"')  # nosec B608
        out.append((name, int(cur.fetchone()[0])))
    return out


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
            cur.execute("SELECT 1 FROM information_schema.schemata "
                        "WHERE schema_name = %s", (SCHEMA,))
            if cur.fetchone() is None:
                print(f"Schema „{SCHEMA}“ existiert nicht — nichts zu tun.")
                return 0
            tabellen = _tabellen(cur)

        gesamt = sum(n for _t, n in tabellen)
        print(f"Schema „{SCHEMA}“: {len(tabellen)} Tabelle(n), {gesamt} Zeile(n)")
        for name, n in tabellen:
            print(f"  {n:>8}  {name}")

        if not args.confirm:
            print("\nTrockenlauf — nichts gelöscht.")
            print("Vorher sichern, dann mit --confirm erneut aufrufen.")
            return 0

        with conn.cursor() as cur:
            cur.execute(f'DROP SCHEMA "{SCHEMA}" CASCADE')  # nosec B608
        conn.commit()
        print(f"\nSchema „{SCHEMA}“ gelöscht ({gesamt} Zeilen).")
        try:
            from shared.audit import audit_event
            audit_event("admin.schema.geloescht", module="admin",
                        details={"schema": SCHEMA, "tabellen": len(tabellen),
                                 "zeilen": gesamt, "grund": "Modul entfernt (#1905)"})
        except Exception as e:  # noqa: BLE001
            print(f"  (Revisionseintrag fehlgeschlagen: {e})")
        return 0
    finally:
        # #1808: `putconn`, niemals `pool.close()` — das schloss den Pool der
        # Anwendung und ergab `PoolClosed` im nächsten Zugriff.
        pool.putconn(conn)


if __name__ == "__main__":
    raise SystemExit(main())
