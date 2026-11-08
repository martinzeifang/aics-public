#!/usr/bin/env python3
"""Vorhandene Nachweisdateien nachträglich verschlüsseln (#1966, B2).

``security.at_rest_encryption.encrypt_evidence`` wirkt nur auf **neue**
Uploads (``evidence/db.py``: die Verschlüsselung sitzt im Speicherpfad). Wer den
Schalter einschaltet, hat damit einen Bestand im Klartext und eine
Konfiguration, die etwas anderes behauptet — auf Produktiv am 05.11.2026
**34 Mandanten-Nachweisdateien**.

Das ist die Hälfte von **B2**, die nach der Umschlüsselung (#1966) übrig
bleibt. Der Datenbestand selbst gehört nicht dazu: Er liegt in PostgreSQL und
braucht Datenträgerverschlüsselung, keine Anwendungsänderung (C10).

**Die Reihenfolge je Datei ist die ganze Sicherheit:**

1. verschlüsselte Fassung daneben schreiben (``<pfad>.enc``),
2. sie **zurücklesen** und mit dem Original vergleichen — Byte für Byte,
3. erst wenn *alle* Dateien das überstanden haben: ``stored_path`` in **einer**
   Transaktion umstellen,
4. erst danach die Klartext-Originale löschen.

Scheitert etwas, bleiben Original und Datenbank unberührt; übrig bliebe
höchstens eine ungenutzte ``.enc``-Datei, und die stört niemanden. Die
umgekehrte Reihenfolge — erst umstellen, dann prüfen — hätte im Fehlerfall
Nachweise unlesbar gemacht, und das sind die Belege der Mandanten.

Aufruf (Trockenlauf ist die Vorgabe)::

    AICS_AT_REST_KEY='…' python3 scripts/ops/nachweise_verschluesseln.py
    AICS_AT_REST_KEY='…' python3 scripts/ops/nachweise_verschluesseln.py --verschluesseln

**Lesbar bleiben sie**, weil jeder Leser über ``evidence/extract.extract_text``
oder den Download-Endpunkt geht und beide ``.enc`` entschlüsseln. Die eine
Ausnahme ist ``cra/ci_autoanswer._load_osv_stats`` — sie liest direkt und
entschlüsselt nicht; betroffen wären nur Dokumente der Art ``osv``, und davon
gibt es keine (geprüft). Wer diese Art einführt, muss sie dort nachziehen.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BASIS = Path("/app")


def _argumente(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verschluesseln", action="store_true",
                    help="wirklich schreiben (ohne dies: Trockenlauf)")
    ap.add_argument("--basis", default=str(BASIS),
                    help="Wurzel, gegen die relative stored_path aufgelöst werden")
    ap.add_argument("--key-env", default="AICS_AT_REST_KEY")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    a = _argumente(argv)
    if not (os.environ.get(a.key_env) or "").strip():
        print(f"{a.key_env} ist nicht gesetzt.", file=sys.stderr)
        return 2

    from shared.crypto_at_rest import decrypt_bytes, encrypt_bytes
    from shared.db import get_pool

    basis = Path(a.basis)
    scharf = a.verschluesseln
    pool = get_pool()
    conn = pool.getconn()
    fertig: list[tuple[str, str, Path, Path]] = []   # id, neuer_pfad, enc, klartext
    hinweise: list[str] = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, filename, stored_path FROM evidence.evidence_documents "
                        "WHERE coalesce(stored_path,'') <> '' AND stored_path NOT LIKE '%.enc'")
            zeilen = cur.fetchall()

        print(f"{len(zeilen)} Nachweisdatei(en) ohne Verschlüsselung"
              + ("" if scharf else "   (TROCKENLAUF)"))
        for doc_id, name, pfad in zeilen:
            quelle = basis / pfad if not str(pfad).startswith("/") else Path(pfad)
            if not quelle.is_file():
                hinweise.append(f"{name}: {quelle} gibt es nicht — übersprungen")
                continue
            roh = quelle.read_bytes()
            ziel = quelle.with_suffix(quelle.suffix + ".enc")
            if not scharf:
                print(f"  {name} ({len(roh)} Byte) → {ziel.name}")
                continue
            ziel.write_bytes(encrypt_bytes(roh, key_env=a.key_env))
            # **Zurücklesen, nicht annehmen.** Eine Verschlüsselung, die sich
            # nicht wieder lesen lässt, ist ein Datenverlust mit Erfolgsmeldung.
            if decrypt_bytes(ziel.read_bytes(), key_env=a.key_env) != roh:
                ziel.unlink(missing_ok=True)
                hinweise.append(f"{name}: Rücklesen ergab andere Bytes — "
                                "nicht umgestellt, Original unberührt")
                continue
            neu = str(ziel.relative_to(basis).as_posix()) if not str(pfad).startswith("/") \
                else str(ziel)
            fertig.append((str(doc_id), neu, ziel, quelle))
            print(f"  {name} ({len(roh)} Byte) → {ziel.name} ✓ zurückgelesen")

        if scharf and fertig:
            # Eine Transaktion für alle: Ein halb umgestellter Bestand wäre
            # nicht nachvollziehbar, weil danach nicht feststeht, welcher Pfad
            # zu welcher Fassung gehört.
            with conn.cursor() as cur:
                for doc_id, neu, _enc, _klar in fertig:
                    cur.execute("UPDATE evidence.evidence_documents SET stored_path = %s "
                                "WHERE id = %s", (neu, doc_id))
            conn.commit()
            # Erst jetzt die Originale — vorher wäre ein Abbruch ein Verlust.
            for _id, _neu, _enc, klar in fertig:
                klar.unlink(missing_ok=True)
    finally:
        pool.putconn(conn)   # niemals close() — der Pool gehört der Anwendung (#1808)

    print(f"\n  umgestellt: {len(fertig)}")
    for h in hinweise:
        print(f"  ⚠ {h}")
    if not scharf:
        print("\n  Trockenlauf — nichts geschrieben. Mit --verschluesseln scharf laufen lassen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
