#!/usr/bin/env python3
"""Die At-Rest-Feldverschlüsselung auf einen neuen Schlüssel umstellen (#1966).

**Warum es dieses Werkzeug gibt.** ``shared/crypto_at_rest._field_passphrase``
leitet die Passphrase in der Reihenfolge ``AICS_AT_REST_KEY`` →
``JWT_SECRET_KEY`` ab. Wer den eigenen Schlüssel **setzt**, wechselt damit die
Quelle — und jeder bereits verschlüsselte Wert wird unlesbar, ohne
Fehlermeldung: GitHub-Token, Portainer-API-Schlüssel,
Zertifikat-Privatschlüssel, TOTP-Geheimnisse, Projekt-Token der
Issue-Anbindung.

Deshalb stand die Abweichung **B6** monatelang: Sie liest sich wie eine
Nachlässigkeit und war eine **Sackgasse** — den Schlüssel zu setzen war ohne
dieses Werkzeug nicht möglich, und ohne ihn ist auch die Verschlüsselung der
Nachweisdateien nicht einschaltbar (``evidence/db.py`` verlangt den
Hauptschalter, und der verlangt den Schlüssel).

**Gefunden wird durch Suchen, nicht durch eine Liste.** Eine Positivliste der
verschlüsselten Felder wäre die Spiegel-Liste aus #1731/#1735, und ein
übersehenes Feld ist hier kein Fehlbetrag, sondern ein **endgültig unlesbarer**
Wert. Dieses Werkzeug durchsucht darum alle Textspalten aller Fachschemata nach
dem Präfix ``AICSFLD1:`` und dazu die Konfigurationsdatei. Ein neues
verschlüsseltes Feld ist damit von sich aus abgedeckt — dieselbe Entscheidung
wie die Ausschlussliste der Dateiauswahl in #1785.

Aufruf (Trockenlauf ist die Vorgabe)::

    # 1. sehen, was betroffen ist — ändert nichts
    JWT_SECRET_KEY='<alt>' AICS_AT_REST_KEY='<neu>' \\
        python3 scripts/ops/at_rest_umschluesseln.py

    # 2. scharf, in einer Transaktion
    JWT_SECRET_KEY='<alt>' AICS_AT_REST_KEY='<neu>' \\
        python3 scripts/ops/at_rest_umschluesseln.py --umschluesseln

Beide Schlüssel müssen gesetzt sein: der **alte** als Quelle, der **neue** als
Ziel. ``--von`` und ``--nach`` benennen die Umgebungsvariablen, falls die
Richtung einmal anders ist (etwa zurück).

**Reihenfolge im Betrieb, und sie ist nicht beliebig:** umschlüsseln, *dann*
den neuen Schlüssel an den Container geben. Umgekehrt läuft die Anwendung
zwischenzeitlich mit dem neuen Schlüssel auf alten Werten — und schreibt
womöglich neue Werte dazu, die dieses Werkzeug dann mit der falschen Quelle
anfasst.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PREFIX = "AICSFLD1:"

#: Schemata, die PostgreSQL selbst gehören — dort liegt nichts von uns.
FREMD = ("pg_catalog", "information_schema", "pg_toast")

#: Verschlüsselte Werte in der Konfigurationsdatei (``server/api/admin.py``).
#: Hier ist eine Liste richtig: Es ist **eine** Datei mit bekanntem Aufbau, und
#: ein JSON-Baum lässt sich ohnehin vollständig durchlaufen — was dieses
#: Werkzeug auch tut. Die Liste dient nur der Meldung.
KONFIG_PFADE = (
    "integrations.github.token",
    "integrations.portainer.api_key",
)


def _argumente(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--von", default="JWT_SECRET_KEY",
                    help="Umgebungsvariable mit dem ALTEN Schlüssel (Vorgabe: JWT_SECRET_KEY)")
    ap.add_argument("--nach", default="AICS_AT_REST_KEY",
                    help="Umgebungsvariable mit dem NEUEN Schlüssel (Vorgabe: AICS_AT_REST_KEY)")
    ap.add_argument("--umschluesseln", action="store_true",
                    help="wirklich schreiben (ohne dies: Trockenlauf)")
    ap.add_argument("--konfig", default="data/ai_compliance_suite.config.json",
                    help="Pfad der Suite-Konfiguration")
    return ap.parse_args(argv)


def _textspalten(conn) -> list[tuple[str, str, str, str]]:
    """``(schema, tabelle, spalte, primaerschluessel)`` für alle Textspalten.

    Ohne Primärschlüssel kann eine Zeile nicht eindeutig angefasst werden; so
    eine Tabelle wird **gemeldet und übersprungen** statt über den Wert selbst
    aktualisiert — ein ``WHERE spalte = '<alter Wert>'`` träfe bei Dubletten
    mehrere Zeilen.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.table_schema, c.table_name, c.column_name,
                   (SELECT kcu.column_name
                      FROM information_schema.table_constraints tc
                      JOIN information_schema.key_column_usage kcu
                        ON kcu.constraint_name = tc.constraint_name
                       AND kcu.table_schema = tc.table_schema
                     WHERE tc.table_schema = c.table_schema
                       AND tc.table_name = c.table_name
                       AND tc.constraint_type = 'PRIMARY KEY'
                     ORDER BY kcu.ordinal_position
                     LIMIT 1)
              FROM information_schema.columns c
              JOIN information_schema.tables t
                ON t.table_schema = c.table_schema AND t.table_name = c.table_name
             WHERE c.data_type IN ('text', 'character varying', 'character')
               AND t.table_type = 'BASE TABLE'
               AND c.table_schema <> ALL(%s)
               AND c.table_schema NOT LIKE 'pg_%%'
             ORDER BY 1, 2, 3
            """,
            (list(FREMD),),
        )
        return [tuple(r) for r in cur.fetchall()]


def _ueberschrift(text: str) -> None:
    print(f"\n{text}\n" + "-" * len(text))


def _datenbank(args, umschluesseln: bool) -> tuple[int, list[str]]:
    from psycopg import sql

    from shared.crypto_at_rest import decrypt_field, encrypt_field
    from shared.db import get_pool

    pool = get_pool()
    conn = pool.getconn()
    geaendert = 0
    hinweise: list[str] = []
    try:
        spalten = _textspalten(conn)
        print(f"{len(spalten)} Textspalten in den Fachschemata werden durchsucht …")
        for schema, tabelle, spalte, pk in spalten:
            q_tab = sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(tabelle))
            q_sp = sql.Identifier(spalte)
            with conn.cursor() as cur:
                if not pk:
                    cur.execute(
                        sql.SQL("SELECT count(*) FROM {} WHERE {} LIKE %s").format(q_tab, q_sp),
                        (PREFIX + "%",))
                    (n,) = cur.fetchone()
                    if n:
                        hinweise.append(
                            f"{schema}.{tabelle}.{spalte}: {n} Wert(e) OHNE "
                            "Primärschlüssel — nicht angefasst, bitte von Hand prüfen")
                    continue
                q_pk = sql.Identifier(pk)
                cur.execute(
                    sql.SQL("SELECT {}, {} FROM {} WHERE {} LIKE %s").format(
                        q_pk, q_sp, q_tab, q_sp),
                    (PREFIX + "%",))
                zeilen = cur.fetchall()
            if not zeilen:
                continue
            print(f"  {schema}.{tabelle}.{spalte}: {len(zeilen)} Wert(e)")
            for schluessel, wert in zeilen:
                try:
                    klar = decrypt_field(wert, key_env=args.von)
                except Exception as exc:  # noqa: BLE001
                    # **Nicht überspringen und weiterlaufen.** Ein Wert, der
                    # sich mit der alten Quelle nicht lesen lässt, ist entweder
                    # schon umgeschlüsselt oder mit einem dritten Schlüssel
                    # entstanden. Beides stillschweigend zu übergehen hieße,
                    # einen unlesbaren Wert als erledigt zu melden.
                    hinweise.append(
                        f"{schema}.{tabelle}.{spalte} [{schluessel}]: mit "
                        f"`{args.von}` nicht lesbar ({type(exc).__name__}) — "
                        "unangetastet")
                    continue
                neu = encrypt_field(klar, key_env=args.nach)
                if umschluesseln:
                    with conn.cursor() as cur:
                        cur.execute(
                            sql.SQL("UPDATE {} SET {} = %s WHERE {} = %s").format(
                                q_tab, q_sp, q_pk),
                            (neu, schluessel))
                geaendert += 1
    finally:
        # `putconn`, niemals `close()` — der Pool gehört der Anwendung (#1808).
        pool.putconn(conn)
    return geaendert, hinweise


def _konfiguration(args, umschluesseln: bool) -> tuple[int, list[str]]:
    """Jeden verschlüsselten Wert im JSON-Baum, nicht nur die bekannten Pfade."""
    from shared.crypto_at_rest import decrypt_field, encrypt_field

    pfad = Path(args.konfig)
    if not pfad.is_file():
        return 0, [f"{pfad} gibt es nicht — Konfiguration übersprungen"]
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    hinweise: list[str] = []
    zaehler = 0

    def lauf(knoten, ort=""):
        nonlocal zaehler
        if isinstance(knoten, dict):
            for k, v in list(knoten.items()):
                stelle = f"{ort}.{k}" if ort else k
                if isinstance(v, str) and v.startswith(PREFIX):
                    try:
                        klar = decrypt_field(v, key_env=args.von)
                    except Exception as exc:  # noqa: BLE001
                        hinweise.append(f"{stelle}: mit `{args.von}` nicht "
                                        f"lesbar ({type(exc).__name__}) — unangetastet")
                        continue
                    knoten[k] = encrypt_field(klar, key_env=args.nach)
                    zaehler += 1
                    print(f"  {stelle}")
                else:
                    lauf(v, stelle)
        elif isinstance(knoten, list):
            for i, v in enumerate(knoten):
                lauf(v, f"{ort}[{i}]")

    lauf(daten)
    if zaehler and umschluesseln:
        # Das HMAC-Sidecar wird von der Anwendung neu gerechnet
        # (`shared/config_io`), sobald sie die Datei schreibt. Hier wird es
        # bewusst **nicht** mitgeschrieben: Ein Sidecar, das zu einem Schlüssel
        # passt, den dieser Prozess nicht kennt, wäre schlimmer als keins
        # (die Lehre aus #1785).
        pfad.write_text(json.dumps(daten, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        hinweise.append(
            f"{pfad} geschrieben — das Sidecar rechnet die Anwendung beim "
            "nächsten Speichern neu; prüfe den Start auf eine "
            "Integritätswarnung")
    return zaehler, hinweise


def main(argv: list[str] | None = None) -> int:
    args = _argumente(argv)
    for name in (args.von, args.nach):
        if not (os.environ.get(name) or "").strip():
            print(f"{name} ist nicht gesetzt — beide Schlüssel sind nötig: der "
                  "alte als Quelle, der neue als Ziel.", file=sys.stderr)
            return 2
    if os.environ[args.von].strip() == os.environ[args.nach].strip():
        print(f"{args.von} und {args.nach} sind identisch — nichts zu tun.",
              file=sys.stderr)
        return 2

    scharf = args.umschluesseln
    _ueberschrift(f"At-Rest-Umschlüsselung {args.von} → {args.nach}"
                  + ("" if scharf else "   (TROCKENLAUF)"))

    db_n, db_hinweise = _datenbank(args, scharf)
    _ueberschrift("Konfiguration")
    cfg_n, cfg_hinweise = _konfiguration(args, scharf)

    _ueberschrift("Ergebnis")
    print(f"  Datenbank:     {db_n} Wert(e)")
    print(f"  Konfiguration: {cfg_n} Wert(e)")
    for h in db_hinweise + cfg_hinweise:
        print(f"  ⚠ {h}")
    if not scharf:
        print("\n  Trockenlauf — nichts geschrieben. Mit --umschluesseln scharf "
              "laufen lassen.")
        print("  Danach erst den neuen Schlüssel an den Container geben, nicht "
              "vorher (siehe Dateikopf).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
