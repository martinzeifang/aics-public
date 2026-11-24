"""Datenbank sichern und einspielen — über psycopg, ohne externes Werkzeug (#1785).

AUFTEILUNG IN STRUKTUR UND DATEN
Gesichert werden beide, eingespielt werden sie verschieden:

* **Daten** werden immer eingespielt. Sie sind der Zweck der Sicherung.
* **Struktur** wird nur benutzt, um anzulegen, was im Ziel fehlt. Existiert eine
  Tabelle bereits, bleibt sie, wie die laufende Version sie angelegt hat.

Das ist die wichtige Entscheidung dieses Moduls. Spielt man ein Backup in eine
neuere Version ein, ist deren Schema das richtige — es trägt die Migrationen,
die seit der Sicherung dazugekommen sind. Würde das Archiv seine Struktur
durchsetzen (wie ``pg_restore --clean`` es täte), wäre die Wiederherstellung
zugleich ein Rückbau der Anwendung, und der fiele erst auf, wenn ein Modul eine
Spalte nicht mehr findet.

Eingespielt wird deshalb **spaltenweise**: Jede Tabelle im Archiv bringt ihre
Spaltennamen mit, und übertragen wird der Schnitt aus Archiv und Ziel. Eine
Spalte, die es nur im Ziel gibt, bleibt auf ihrem Default (neue Migration); eine
Spalte, die es nur im Archiv gibt, wird gemeldet (sie wurde seit der Sicherung
entfernt) statt den ganzen Vorgang scheitern zu lassen.

WOHER DIE STRUKTUR-ANGABEN KOMMEN
Nicht aus selbstgebautem SQL, sondern aus den Textausgaben, die PostgreSQL
selbst liefert: ``format_type`` für Spaltentypen, ``pg_get_constraintdef`` für
Constraints, ``pg_indexes.indexdef`` für Indizes. Zusammengebaut wird nur die
Hülle. Was dabei schiefgehen kann, ist eine fehlende Nebensache (ein Index, den
der nächste ``ensure_db``-Lauf ohnehin wieder anlegt), nicht ein falscher
Datentyp.

WAS ABSICHTLICH FEHLT
Rollen, Tablespaces, Extensions und Datenbank-Eigenschaften. Die gehören der
Installation, nicht dem Datenbestand — sie stehen im Compose-Stack und werden
beim Aufsetzen erzeugt. Ein Backup, das sie mitbrächte, wäre nur dann
einspielbar, wenn das Ziel ihnen zufällig entspricht.
"""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any, Iterable, Iterator

from psycopg import sql as _pgsql

# Schemata, die PostgreSQL selbst gehören.
_SYSTEM_SCHEMATA = ("pg_catalog", "information_schema", "pg_toast")

# Nur die temporären Schemata von PostgreSQL selbst. Eine darüber hinausgehende
# Ausnahme — etwa für Schemata aus Testläufen — wäre doppelt falsch: In einer
# Installation gibt es sie nicht, und sie nähme den Tests genau den Gegenstand,
# den sie prüfen; gesichert würde dann etwas anderes, als getestet wurde.
_WEGWERF_PRAEFIXE = ("pg_temp", "pg_toast_temp")


class BezeichnerFehler(ValueError):
    """Ein Name aus dem Archiv taugt nicht als Datenbank-Bezeichner."""


# Beim Sichern stammen Schema-, Tabellen- und Spaltennamen aus den Katalogen
# dieser Datenbank. Beim **Einspielen** stammen sie aus ``struktur.json`` eines
# Archivs — und ein Archiv kann hochgeladen worden sein. SQL kennt keine
# Parameter für Bezeichner, also muss an dieser einen Stelle entschieden
# werden, was ein Bezeichner sein darf: Positivliste, und gequotet wird mit der
# Funktion der Datenbank-Bibliothek, nicht mit Anführungszeichen von Hand.
_BEZEICHNER = re.compile(r"^[A-Za-z0-9_]{1,63}$")


def _q(*teile: str) -> str:
    """Einen (ggf. qualifizierten) Bezeichner prüfen und quoten."""
    raus = []
    for teil in teile:
        if not _BEZEICHNER.match(str(teil or "")):
            raise BezeichnerFehler(f"Unzulässiger Name im Archiv: {teil!r}")
        raus.append(_pgsql.Identifier(str(teil)).as_string(None))
    return ".".join(raus)


#: Spaltentypen, wie ``format_type`` sie schreibt: ``text``, ``character
#: varying(200)``, ``numeric(10,2)``, ``integer[]``, ``public.meintyp``.
_TYP = re.compile(r"^[A-Za-z0-9_ ().,\[\]\"]{1,200}$")


def _pruefe_typ(typ: str) -> str:
    roh = str(typ or "").strip()
    if not _TYP.match(roh) or ";" in roh or "--" in roh:
        raise BezeichnerFehler(f"Unzulässiger Spaltentyp im Archiv: {typ!r}")
    return roh


def pruefe_ausdruck(sql_text: str, wofuer: str) -> str:
    """Ein SQL-Fragment aus dem Archiv (Vorgabewert, Constraint, Index).

    Diese Fragmente lassen sich nicht auf eine Positivliste bringen — es sind
    beliebige Ausdrücke, und genau als solche müssen sie wieder in die
    Datenbank. Geprüft wird deshalb nur das, was sich eindeutig prüfen lässt:
    dass daraus **eine** Anweisung wird und kein Rattenschwanz weiterer.

    Darüber hinaus bleibt es eine Vertrauensfrage: Ein Archiv aus fremder Hand
    einzuspielen heißt, dessen Strukturangaben auszuführen. Wer einspielen darf,
    hat ``admin:config`` und könnte dasselbe auch direkt — aber die Datei kann
    von außen kommen, und das steht so in ``docs/web/backup-restore.md``.
    """
    roh = str(sql_text or "").strip().rstrip(";").strip()
    if ";" in roh:
        raise BezeichnerFehler(
            f"{wofuer}: mehrere Anweisungen in einer Strukturangabe — abgelehnt")
    return roh


def _echte_schemata(cur) -> list[str]:
    cur.execute(
        """
        SELECT nspname FROM pg_namespace
        WHERE nspname <> ALL(%s) AND nspname NOT LIKE 'pg\\_%%'
        ORDER BY nspname
        """,
        (list(_SYSTEM_SCHEMATA),),
    )
    raus = []
    for (name,) in cur.fetchall():
        if any(name.startswith(p) for p in _WEGWERF_PRAEFIXE):
            continue
        raus.append(name)
    return raus


def _tabellen(cur, schema: str) -> list[str]:
    cur.execute(
        """
        SELECT c.relname FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = %s AND c.relkind = 'r'
        ORDER BY c.relname
        """,
        (schema,),
    )
    return [r[0] for r in cur.fetchall()]


def _spalten(cur, schema: str, tabelle: str) -> list[dict[str, Any]]:
    """Spalten mit dem Typ, wie PostgreSQL ihn selbst schreibt."""
    cur.execute(
        """
        SELECT a.attname,
               format_type(a.atttypid, a.atttypmod) AS typ,
               a.attnotnull,
               pg_get_expr(d.adbin, d.adrelid) AS vorgabe,
               a.attidentity
        FROM pg_attribute a
        LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
        WHERE a.attrelid = format('%%I.%%I', %s::text, %s::text)::regclass
          AND a.attnum > 0 AND NOT a.attisdropped
        ORDER BY a.attnum
        """,
        (schema, tabelle),
    )
    # ``attidentity``: 'a' = GENERATED ALWAYS, 'd' = BY DEFAULT, '' = keine.
    # Ohne diese Angabe entstünde beim Anlegen aus dem Archiv eine gewöhnliche
    # Zahlenspalte: Die Daten passten hinein, aber jedes spätere Einfügen ohne
    # ausdrücklichen Schlüssel schlüge fehl — die Tabelle wäre wiederhergestellt
    # und unbenutzbar.
    return [
        {"name": n, "typ": t, "notnull": bool(nn), "vorgabe": v,
         "identity": (i or "")}
        for n, t, nn, v, i in cur.fetchall()
    ]


def _constraints(cur, schema: str, tabelle: str) -> list[dict[str, str]]:
    cur.execute(
        """
        SELECT conname, pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = format('%%I.%%I', %s::text, %s::text)::regclass
        ORDER BY contype DESC, conname
        """,
        (schema, tabelle),
    )
    return [{"name": n, "def": d} for n, d in cur.fetchall()]


def _indizes(cur, schema: str, tabelle: str) -> list[dict[str, str]]:
    """Indizes ohne die, die schon zu einem Constraint gehören (sonst doppelt)."""
    cur.execute(
        """
        SELECT i.indexname, i.indexdef
        FROM pg_indexes i
        WHERE i.schemaname = %s AND i.tablename = %s
          AND NOT EXISTS (
              SELECT 1 FROM pg_constraint c
              WHERE c.conname = i.indexname
                AND c.connamespace = (SELECT oid FROM pg_namespace WHERE nspname = %s)
          )
        ORDER BY i.indexname
        """,
        (schema, tabelle, schema),
    )
    return [{"name": n, "def": d} for n, d in cur.fetchall()]


def _sequenzen(cur, schema: str) -> list[dict[str, Any]]:
    """Sequenzen mit Stand. Ohne sie vergibt die Zielinstanz Schlüssel neu ab 1."""
    cur.execute(
        """
        SELECT c.relname
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = %s AND c.relkind = 'S'
        ORDER BY c.relname
        """,
        (schema,),
    )
    raus: list[dict[str, Any]] = []
    for (name,) in cur.fetchall():
        cur.execute(f'SELECT last_value, is_called FROM {_q(schema, name)}')  # nosec B608 — Bezeichner über _q()
        zeile = cur.fetchone()
        # Besitz (OWNED BY) erhalten: sonst bleibt die Sequenz beim Löschen der
        # Tabelle zurück und kollidiert beim nächsten Anlegen.
        # ``deptype`` unterscheidet die beiden Bauarten: ``a`` ist eine Sequenz
        # hinter einem ``serial``-Vorgabewert, ``i`` gehört untrennbar zu einer
        # IDENTITY-Spalte. Bei letzterer ist ``ALTER SEQUENCE … OWNED BY``
        # verboten; der Besitz steht ohnehin fest, sobald die Spalte existiert.
        cur.execute(
            """
            SELECT a.attrelid::regclass::text, a.attname, d.deptype
            FROM pg_depend d
            JOIN pg_attribute a ON a.attrelid = d.refobjid AND a.attnum = d.refobjsubid
            WHERE d.objid = format('%%I.%%I', %s::text, %s::text)::regclass
              AND d.deptype IN ('a', 'i')
            LIMIT 1
            """,
            (schema, name),
        )
        besitzer = cur.fetchone()
        raus.append({
            "name": name,
            "last_value": int(zeile[0]) if zeile else 1,
            "is_called": bool(zeile[1]) if zeile else False,
            "owned_by": list(besitzer[:2]) if besitzer and besitzer[2] == "a" else None,
            "identity": bool(besitzer and besitzer[2] == "i"),
        })
    return raus


def _funktionen(cur) -> list[dict[str, str]]:
    """Selbst angelegte SQL-Funktionen, als fertiges ``CREATE``-SQL.

    Es ist heute genau eine (``public.aics_now()``, angelegt vom Bootstrap in
    ``shared/db``), aber sie steht als Vorgabewert in fast jeder Tabelle dieser
    Anwendung: Ohne sie lässt sich keine einzige Tabelle anlegen. Das hat der
    erste Wiederherstellungs-Versuch in eine leere Datenbank gezeigt — 137
    Tabellen fehlten mit „function aics_now() does not exist".
    """
    cur.execute(
        """
        SELECT n.nspname, p.proname, pg_get_functiondef(p.oid)
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
          AND p.prokind = 'f'
        ORDER BY 1, 2
        """
    )
    return [{"schema": s, "name": n, "def": d} for s, n, d in cur.fetchall()]


def struktur_lesen(cur) -> dict[str, Any]:
    """Das Gerüst der Datenbank als einfache Datenstruktur."""
    schemata: dict[str, Any] = {}
    for schema in _echte_schemata(cur):
        tabellen = {}
        for tab in _tabellen(cur, schema):
            tabellen[tab] = {
                "spalten": _spalten(cur, schema, tab),
                "constraints": _constraints(cur, schema, tab),
                "indizes": _indizes(cur, schema, tab),
            }
        schemata[schema] = {
            "tabellen": tabellen,
            "sequenzen": _sequenzen(cur, schema),
        }
    return {"schemata": schemata, "funktionen": _funktionen(cur)}


# ── Daten heraus ────────────────────────────────────────────────────────────

def daten_als_csv(conn, schema: str, tabelle: str, spalten: list[str]) -> Iterator[bytes]:
    """Tabelleninhalt als CSV-Strom.

    CSV, weil ein Mensch im Ernstfall hineinsehen kann und ``bytea`` als
    Hex-Text verlustfrei zurückläuft.

    ``FORCE_QUOTE *`` ist hier **nicht** Kosmetik. Ohne diese Angabe schreibt
    PostgreSQL die leere Zeichenkette als nichts — genau wie NULL. Beim
    Zurücklesen wird daraus NULL, und aus ``pruefungsfokus = ''`` wird
    ``pruefungsfokus IS NULL``. Bei einer Spalte mit NOT NULL fällt das beim
    Einspielen auf; bei allen anderen wäre es eine stille Veränderung des
    Datenbestands durch die Sicherung selbst. Mit erzwungenen Anführungszeichen
    ist NULL (nichts) von der leeren Zeichenkette (``""``) eindeutig
    unterschieden.
    """
    liste = ", ".join(_q(s) for s in spalten)
    sql = (f'COPY (SELECT {liste} FROM {_q(schema, tabelle)}) '  # nosec B608 — Bezeichner über _q()
           f"TO STDOUT WITH (FORMAT csv, FORCE_QUOTE *)")
    with conn.cursor().copy(sql) as copy:
        for block in copy:
            yield bytes(block)


def zeilen_zahl(cur, schema: str, tabelle: str) -> int:
    cur.execute(f'SELECT count(*) FROM {_q(schema, tabelle)}')  # nosec B608 — Bezeichner über _q()
    return int(cur.fetchone()[0])


# ── Struktur herstellen ─────────────────────────────────────────────────────

def _schema_anlegen(cur, schema: str) -> None:
    cur.execute(f'CREATE SCHEMA IF NOT EXISTS {_q(schema)}')


def _vorhandene_spalten(cur, schema: str, tabelle: str) -> list[str] | None:
    cur.execute(
        """
        SELECT a.attname FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = %s AND c.relname = %s
          AND a.attnum > 0 AND NOT a.attisdropped
        ORDER BY a.attnum
        """,
        (schema, tabelle),
    )
    zeilen = cur.fetchall()
    return [r[0] for r in zeilen] if zeilen else None


def _tabelle_anlegen(cur, schema: str, tabelle: str, bau: dict[str, Any]) -> None:
    """Eine fehlende Tabelle aus den gesicherten Angaben anlegen.

    Nur die Hülle: Spalten mit Typ, NOT NULL und Vorgabewert. Primärschlüssel,
    Fremdschlüssel und Indizes kommen danach — und was dabei nicht gelingt,
    legt der nächste ``ensure_db``-Lauf der Anwendung an (alle Migrationen sind
    ``IF NOT EXISTS``). Die Daten müssen hinein können; der Rest ist reparabel.
    """
    teile = []
    for sp in bau["spalten"]:
        stueck = f'{_q(sp["name"])} {_pruefe_typ(sp["typ"])}'
        kennung = sp.get("identity") or ""
        if kennung in ("a", "d"):
            art = "ALWAYS" if kennung == "a" else "BY DEFAULT"
            stueck += f" GENERATED {art} AS IDENTITY"
        elif sp.get("vorgabe"):
            stueck += f' DEFAULT {pruefe_ausdruck(sp["vorgabe"], "Vorgabewert")}'
        if sp.get("notnull"):
            stueck += " NOT NULL"
        teile.append(stueck)
    cur.execute(f'CREATE TABLE IF NOT EXISTS {_q(schema, tabelle)} ({", ".join(teile)})')


def _beiwerk_anlegen(conn, schema: str, tabelle: str, bau: dict[str, Any],
                     warnungen: list[str]) -> None:
    """Constraints und Indizes — einzeln, und ein Fehlschlag ist kein Abbruch.

    Jeder Einzelschritt läuft in einem Savepoint. Ohne ihn risse der erste
    abgelehnte Index die **ganze** Wiederherstellung auf, denn PostgreSQL lässt
    nach einem Fehler in einer Transaktion keinen weiteren Befehl mehr zu.
    """
    for c in bau.get("constraints", []):
        try:
            with conn.transaction():
                conn.cursor().execute(
                    f'ALTER TABLE {_q(schema, tabelle)} '
                    f'ADD CONSTRAINT {_q(c["name"])} '
                    f'{pruefe_ausdruck(c["def"], "Constraint")}'
                )
        except Exception as e:  # noqa: BLE001 — existiert schon oder passt nicht mehr
            warnungen.append(f'{schema}.{tabelle}: Constraint {c["name"]} übersprungen ({_kurz(e)})')
    for i in bau.get("indizes", []):
        try:
            with conn.transaction():
                conn.cursor().execute(pruefe_ausdruck(i["def"], "Index"))
        except Exception as e:  # noqa: BLE001
            warnungen.append(f'{schema}.{tabelle}: Index {i["name"]} übersprungen ({_kurz(e)})')


def _spalten_ergaenzen(conn, schema: str, tabelle: str, bau: dict[str, Any],
                       vorhanden: list[str], warnungen: list[str]) -> None:
    """Spalten anlegen, die das Archiv kennt und die Zieltabelle nicht.

    Zwei Fälle führen hierher, und sie sind von außen nicht zu unterscheiden:
    Die Spalte wurde seit der Sicherung **entfernt**, oder die Zielinstallation
    hat sie noch nicht angelegt (manche Migrationen laufen erst beim ersten
    Zugriff eines Moduls, nicht im Warmup — ``firmen_id`` ist so eine).

    Der Schaden ist aber sehr verschieden: Im ersten Fall bleibt eine ungenutzte
    Spalte stehen, die niemanden stört. Im zweiten gingen die Werte **verloren**,
    und zwar lautlos — die Wiederherstellung meldete Erfolg. Deshalb wird
    ergänzt und im Bericht genannt.

    Ohne NOT NULL und ohne Constraints: Die Tabelle kann bereits Zeilen haben,
    und die Angaben aus dem Archiv kommen unmittelbar danach.
    """
    fehlend = [s for s in bau.get("spalten", []) if s["name"] not in vorhanden]
    for sp in fehlend:
        stueck = f'{_q(sp["name"])} {_pruefe_typ(sp["typ"])}'
        if sp.get("vorgabe") and "nextval(" not in str(sp["vorgabe"]):
            stueck += f' DEFAULT {pruefe_ausdruck(sp["vorgabe"], "Vorgabewert")}'
        try:
            with conn.transaction():
                conn.cursor().execute(
                    f'ALTER TABLE {_q(schema, tabelle)} ADD COLUMN IF NOT EXISTS {stueck}')
            warnungen.append(
                f'{schema}.{tabelle}: Spalte {sp["name"]} aus der Sicherung ergänzt '
                "(in dieser Version nicht angelegt)")
        except Exception as e:  # noqa: BLE001
            warnungen.append(
                f'{schema}.{tabelle}: Spalte {sp["name"]} nicht ergänzbar ({_kurz(e)}) — '
                "ihre Werte werden nicht eingespielt")


def _kurz(e: Exception) -> str:
    return str(e).strip().splitlines()[0][:120]


def struktur_herstellen(conn, struktur: dict[str, Any]) -> list[str]:
    """Fehlende Schemata und Tabellen anlegen. Vorhandene bleiben unberührt."""
    warnungen: list[str] = []
    cur = conn.cursor()

    # Erst die Schemahüllen, dann die Funktionen: Letztere stehen als
    # Vorgabewert in den Tabellen und müssen vor ihnen da sein.
    for schema in struktur.get("schemata", {}):
        _schema_anlegen(cur, schema)
    for fn in struktur.get("funktionen", []):
        try:
            with conn.transaction():
                conn.cursor().execute(fn["def"])
        except Exception as e:  # noqa: BLE001
            warnungen.append(
                f'{fn["schema"]}.{fn["name"]}: Funktion übersprungen ({_kurz(e)})')

    for schema, inhalt in struktur.get("schemata", {}).items():
        _schema_anlegen(cur, schema)
        # Sequenzen zuerst, weil Spalten-Vorgaben auf sie verweisen — aber nur
        # die eigenständigen. Die Sequenz hinter einer IDENTITY-Spalte entsteht
        # mit der Tabelle; legte man sie vorher unter ihrem Namen an, bekäme die
        # Tabelle eine zweite mit angehängter Ziffer, und der Stand würde
        # anschließend auf der falschen gesetzt.
        for seq in inhalt.get("sequenzen", []):
            if seq.get("identity"):
                continue
            try:
                with conn.transaction():
                    conn.cursor().execute(
                        f'CREATE SEQUENCE IF NOT EXISTS {_q(schema, seq["name"])}')
            except Exception as e:  # noqa: BLE001
                warnungen.append(f'{schema}: Sequenz {seq["name"]} übersprungen ({_kurz(e)})')
        for tabelle, bau in inhalt.get("tabellen", {}).items():
            vorhanden = _vorhandene_spalten(cur, schema, tabelle)
            if vorhanden is not None:
                # Die laufende Version hat die Tabelle angelegt — ihre Fassung
                # gilt. Fehlende Spalten werden aber ergänzt, siehe unten.
                _spalten_ergaenzen(conn, schema, tabelle, bau, vorhanden, warnungen)
                continue
            try:
                with conn.transaction():
                    _tabelle_anlegen(conn.cursor(), schema, tabelle, bau)
            except Exception as e:  # noqa: BLE001
                warnungen.append(f"{schema}.{tabelle}: nicht anlegbar ({_kurz(e)})")
                continue
            _beiwerk_anlegen(conn, schema, tabelle, bau, warnungen)
    return warnungen


def sequenzen_setzen(conn, struktur: dict[str, Any], warnungen: list[str]) -> None:
    """Sequenzstände nachziehen.

    Ohne diesen Schritt beginnt eine wiederhergestellte Installation bei 1 und
    kollidiert mit den gerade eingespielten Schlüsseln — ein Fehler, der erst
    beim nächsten Anlegen auftritt und dann nach einem Datenfehler aussieht.
    """
    for schema, inhalt in struktur.get("schemata", {}).items():
        for seq in inhalt.get("sequenzen", []):
            name = _q(schema, seq["name"])
            # Besitz und Stand in getrennten Savepoints: Der Stand ist das
            # Wichtige. Scheiterte er zusammen mit dem Besitz in einem Schritt,
            # begänne die Zielinstallation bei 1 und die erste neue Zeile liefe
            # in einen Schlüsselkonflikt — ein Fehler, der nach einem
            # Datenfehler aussieht und keiner ist.
            if seq.get("owned_by"):
                try:
                    with conn.transaction():
                        tab, spalte = seq["owned_by"]
                        conn.cursor().execute(
                            f'ALTER SEQUENCE {name} OWNED BY {tab}.{_q(spalte)}')
                except Exception as e:  # noqa: BLE001
                    warnungen.append(
                        f'{schema}: Sequenz {seq["name"]} ohne Besitzangabe ({_kurz(e)})')
            try:
                with conn.transaction():
                    conn.cursor().execute(
                        "SELECT setval(%s, %s, %s)",
                        (f'{schema}.{seq["name"]}', max(int(seq["last_value"]), 1),
                         bool(seq["is_called"])),
                    )
            except Exception as e:  # noqa: BLE001
                warnungen.append(f'{schema}: Sequenz {seq["name"]} nicht gesetzt ({_kurz(e)})')


# ── Daten hinein ────────────────────────────────────────────────────────────

def tabelle_einspielen(conn, schema: str, tabelle: str, spalten_im_archiv: list[str],
                       csv_bytes: bytes, warnungen: list[str]) -> int:
    """Eine Tabelle leeren und neu füllen. Liefert die Zeilenzahl.

    Übertragen wird der **Schnitt** aus Archiv- und Zielspalten: Eine Spalte,
    die die laufende Version dazugenommen hat, bleibt auf ihrem Vorgabewert;
    eine, die sie nicht mehr kennt, wird gemeldet und übersprungen. Sonst
    scheiterte jede Wiederherstellung über eine Migration hinweg — also genau
    die, für die man ein Backup hat.
    """
    cur = conn.cursor()
    ziel = _vorhandene_spalten(cur, schema, tabelle)
    if ziel is None:
        warnungen.append(f"{schema}.{tabelle}: Tabelle fehlt im Ziel — Daten nicht eingespielt")
        return 0

    nehmen = [s for s in spalten_im_archiv if s in ziel]
    fehlend = [s for s in spalten_im_archiv if s not in ziel]
    if fehlend:
        warnungen.append(
            f"{schema}.{tabelle}: Spalte(n) {', '.join(fehlend)} gibt es nicht mehr — übergangen")
    if not nehmen:
        warnungen.append(f"{schema}.{tabelle}: keine gemeinsame Spalte — übersprungen")
        return 0

    daten = list(_csv_auf_spalten(csv_bytes, spalten_im_archiv, nehmen))

    try:
        with conn.transaction():
            return _direkt(conn, schema, tabelle, nehmen, daten)
    except Exception as e:  # noqa: BLE001
        if not _ist_notnull_verstoss(e):
            raise
    # Zweiter Anlauf über eine Zwischentabelle (siehe unten).
    with conn.transaction():
        zeilen = _ueber_zwischentabelle(conn, schema, tabelle, nehmen, daten, warnungen)
    return zeilen


def _direkt(conn, schema: str, tabelle: str, nehmen: list[str],
            daten: list[bytes]) -> int:
    cur = conn.cursor()
    cur.execute(f'TRUNCATE TABLE {_q(schema, tabelle)} CASCADE')
    liste = ", ".join(_q(s) for s in nehmen)
    sql = f'COPY {_q(schema, tabelle)} ({liste}) FROM STDIN WITH (FORMAT csv)'
    zeilen = 0
    with cur.copy(sql) as copy:
        for block in daten:
            copy.write(block)
            zeilen += block.count(b"\n")
    return zeilen


def _ist_notnull_verstoss(e: Exception) -> bool:
    return getattr(e, "sqlstate", "") == "23502"


def _ueber_zwischentabelle(conn, schema: str, tabelle: str, nehmen: list[str],
                           daten: list[bytes], warnungen: list[str]) -> int:
    """Einspielen über eine Zwischentabelle ohne NOT-NULL-Pflicht.

    Der Fall: Eine Spalte durfte zur Zeit der Sicherung leer sein und ist
    inzwischen Pflicht geworden. Genau dann braucht man das Backup — nach einem
    Verlust installiert man die **neueste** Version, nicht die von damals — und
    genau dann würde ein direkter Weg scheitern.

    Die Zwischentabelle nimmt die Daten ungeprüft auf; beim Übernehmen tritt für
    jede fehlende Pflichtangabe der Vorgabewert der Spalte ein. Das ist dieselbe
    Antwort, die die Anwendung einer neu angelegten Zeile gäbe. Hat die Spalte
    keinen Vorgabewert, bleibt es beim Fehler — dann ist der Datensatz wirklich
    unvollständig, und darüber darf eine Sicherung nicht hinweggehen.
    """
    cur = conn.cursor()
    zwischen = f"_backup_{tabelle}"[:63]
    liste = ", ".join(f'"{s}"' for s in nehmen)

    cur.execute(f'DROP TABLE IF EXISTS pg_temp.{_q(zwischen)}')
    cur.execute(
        f'CREATE TEMP TABLE {_q(zwischen)} (LIKE {_q(schema, tabelle)} '
        f"INCLUDING DEFAULTS EXCLUDING CONSTRAINTS EXCLUDING INDEXES)")
    for spalte in nehmen:
        cur.execute(
            f'ALTER TABLE pg_temp.{_q(zwischen)} ALTER COLUMN {_q(spalte)} DROP NOT NULL')

    zeilen = 0
    with cur.copy(
        f'COPY pg_temp.{_q(zwischen)} ({liste}) FROM STDIN WITH (FORMAT csv)'
    ) as copy:
        for block in daten:
            copy.write(block)
            zeilen += block.count(b"\n")

    pflicht = _pflichtspalten_mit_vorgabe(cur, schema, tabelle)
    auswahl = ", ".join(
        f'COALESCE({_q(s)}, {pruefe_ausdruck(pflicht[s], "Vorgabewert")})'
        if s in pflicht else _q(s) for s in nehmen)
    ersetzt = [s for s in nehmen if s in pflicht]

    cur.execute(f'TRUNCATE TABLE {_q(schema, tabelle)} CASCADE')
    # OVERRIDING SYSTEM VALUE: Die Schlüsselspalten dieser Anwendung sind
    # ``GENERATED ALWAYS AS IDENTITY``. COPY darf sie setzen, INSERT nicht —
    # ohne diese Angabe käme die Wiederherstellung mit neu vergebenen
    # Schlüsseln zurück, und jede Verknüpfung zwischen zwei Tabellen zeigte
    # danach auf einen anderen Datensatz.
    cur.execute(
        f'INSERT INTO {_q(schema, tabelle)} ({liste}) OVERRIDING SYSTEM VALUE '  # nosec B608 — Bezeichner über _q()
        f'SELECT {auswahl} FROM pg_temp.{_q(zwischen)}')
    cur.execute(f'DROP TABLE pg_temp.{_q(zwischen)}')

    warnungen.append(
        f"{schema}.{tabelle}: Pflichtangabe(n) {', '.join(ersetzt)} fehlten in der "
        "Sicherung und wurden mit dem Vorgabewert gefüllt (Spalte wurde seither "
        "zur Pflicht).")
    return zeilen


def _pflichtspalten_mit_vorgabe(cur, schema: str, tabelle: str) -> dict[str, str]:
    cur.execute(
        """
        SELECT a.attname, pg_get_expr(d.adbin, d.adrelid)
        FROM pg_attribute a
        JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
        WHERE a.attrelid = format('%%I.%%I', %s::text, %s::text)::regclass
          AND a.attnum > 0 AND NOT a.attisdropped AND a.attnotnull
        """,
        (schema, tabelle),
    )
    return {name: ausdruck for name, ausdruck in cur.fetchall() if ausdruck}


def _csv_auf_spalten(roh: bytes, archiv_spalten: list[str],
                     nehmen: list[str]) -> Iterable[bytes]:
    """CSV auf die gemeinsamen Spalten beschneiden.

    Im Normalfall (gleiche Spalten) wird nichts umgeschrieben — das Archiv geht
    unverändert durch, und eine Tabelle mit Hunderttausend Zeilen läuft nicht
    durch den Python-CSV-Leser.
    """
    if archiv_spalten == nehmen:
        return [roh]
    halten = [archiv_spalten.index(s) for s in nehmen]
    quelle = io.StringIO(roh.decode("utf-8"), newline="")
    ziel = io.StringIO(newline="")
    schreiber = csv.writer(ziel, lineterminator="\n")
    for zeile in csv.reader(quelle):
        schreiber.writerow([zeile[i] for i in halten])
    return [ziel.getvalue().encode("utf-8")]


def fremdschluessel_aussetzen(cur) -> None:
    """Prüfungen für die Dauer des Einspielens zurückstellen.

    Die Tabellen kommen in alphabetischer Reihenfolge; eine Zeile kann auf eine
    Tabelle verweisen, die noch leer ist. Eine Reihenfolge nach Abhängigkeiten
    zu errechnen wäre möglich, hülfe aber nicht bei gegenseitigen Verweisen.
    """
    cur.execute("SET session_replication_role = replica")


def fremdschluessel_wieder(cur) -> None:
    cur.execute("SET session_replication_role = origin")


def struktur_aus_json(roh: bytes) -> dict[str, Any]:
    return json.loads(roh.decode("utf-8"))


def struktur_nach_json(struktur: dict[str, Any]) -> bytes:
    return json.dumps(struktur, ensure_ascii=False, indent=1).encode("utf-8")
