#!/usr/bin/env python3
"""Verlorene Herkunft an Risiken nachtragen (#1976).

``save_risiko`` hat ``felder_json`` bis 8.6.2 vollständig ersetzt, und jeder
Bewertungsweg schickt nur die Felder des Frameworks. Der **erste**
Speichervorgang nach dem Anlegen löschte damit ``felder._source``/
``_source_id`` — und mit ihnen die Zuordnung, die

* ``cra/konformitaet_gate._accepted_gap_for`` liest (ist eine Abweichung
  begründet akzeptiert?),
* ``cra/risk_import.provenance_key`` liest (Dubletten bei CVE-Import),
* ``cra/release_bericht`` liest (Nachweis-Zuordnung).

Der Code-Fix wirkt nur nach vorn. Wer den Defekt hatte, hat Risiken ohne
Herkunft im Bestand, und dort bleibt eine Akzeptanz unlesbar, bis sie
nachgetragen ist — dieselbe Lehre wie bei B6/#1966: Ein Schalter ohne Weg, den
Bestand nachzuziehen, ist eine Sackgasse.

**Woher die Wahrheit kommt.** Nicht geraten: ``risk_requirement_links`` hält je
Risiko Modul, Objektart und Anforderung (``modul``, ``object_kind``,
``anforderung_id``) — dieselbe Zeile, die die Maske an der
Anforderung anzeigt. Aus ihr wird ``_source_id`` als
``<modul>:<art>:<anforderung>`` zusammengesetzt, genau wie
``shared/req_risks`` es beim Anlegen tut.

**Was das Werkzeug nicht tut:** Es rät keine Herkunft für ein Risiko ohne
Verknüpfung. Ein aus einem CVE oder einem Threat-Model entstandenes Risiko
(``_source`` = ``cra-cve``/``cra-threat``) hat keine Zeile in dieser Tabelle;
seine Herkunft ist nicht rekonstruierbar und wird **benannt**, nicht erfunden.
Eine falsche Zuordnung sähe aus wie eine Aussage.

Aufruf (Trockenlauf ist die Vorgabe)::

    python3 scripts/ops/risiko_herkunft_nachtragen.py
    python3 scripts/ops/risiko_herkunft_nachtragen.py --nachtragen
    python3 scripts/ops/risiko_herkunft_nachtragen.py --projekt 'AI Compliance Suite'
"""

from __future__ import annotations

import argparse
import json
import sys


def _ist_anforderungslücke(felder: dict, name: str) -> bool:
    """Trägt dieses Risiko die Nichterfüllung einer Anforderung (#1564)?

    Zwei Anzeichen, beide aus dem Bestand und keines geraten: der halb
    erhaltene Marker ``_source == 'req-gap'`` (``_source_id`` fehlt, ``_source``
    nicht), und der Titel, den `shared/req_risks` vergibt.
    """
    if str((felder or {}).get("_source") or "") == "req-gap":
        return True
    return str(name or "").strip().lower().startswith("nichterfüllung")


def _argumente(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nachtragen", action="store_true",
                    help="wirklich schreiben (ohne dies: Trockenlauf)")
    ap.add_argument("--projekt", default="",
                    help="nur dieses Risikobewertungs-Projekt (Vorgabe: alle)")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    a = _argumente(argv)
    from shared.db import get_pool

    scharf = a.nachtragen
    pool = get_pool()
    conn = pool.getconn()
    nachgetragen = 0
    ohne_verknuepfung: list[str] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT r.id, r.projekt_name, r.risk_name, r.felder_json,
                          l.modul, l.object_kind, l.anforderung_id,
                          r.behandlung, r.akzeptanz_kategorie
                     FROM risikobewertung.rb_risiken r
                     LEFT JOIN risikobewertung.risk_requirement_links l
                            ON l.risk_id = r.id
                    WHERE (%s = '' OR r.projekt_name = %s)
                    ORDER BY r.projekt_name, r.id""",
                (a.projekt, a.projekt))
            zeilen = cur.fetchall()

        aenderungen: list[tuple[str, int]] = []
        for (rid, projekt, name, felder_roh, modul, art, req, behandlung,
             kategorie) in zeilen:
            try:
                felder = json.loads(felder_roh or "{}") or {}
            except Exception:  # noqa: BLE001
                felder = {}
            if not isinstance(felder, dict):
                felder = {}
            if felder.get("_source_id"):
                continue                      # Herkunft ist da — nichts zu tun
            if not (modul and art and req):
                # Keine Verknüpfung: nicht rekonstruierbar.
                #
                # **Gemeldet wird nur, was eine Herkunft haben müsste.** Die
                # gewöhnliche Akzeptanz eines Risikos braucht kein
                # ``_source_id`` — nur ein Risiko, das die *Nichterfüllung
                # einer Anforderung* trägt (#1564), wird vom Gate darüber
                # gefunden. Beim ersten Anlauf meldete dieser Lauf acht
                # richtige Zeilen je Instanz als zu klären; eine Warnung, die
                # bei allen anschlägt, trifft keinen (die Lehre aus
                # #1774/#1877).
                if (behandlung or "") == "akzeptiert" and _ist_anforderungslücke(felder, name):
                    ohne_verknuepfung.append(
                        f"{projekt} #{rid} „{(name or '')[:48]}" + "“ "
                        f"(akzeptiert/{kategorie or '-'}) — trägt keine "
                        "Verknüpfung, Anforderung nicht rekonstruierbar")
                continue
            felder["_source"] = felder.get("_source") or "req-gap"
            felder["_source_id"] = f"{modul}:{art}:{req}"
            aenderungen.append((json.dumps(felder, ensure_ascii=False), rid))
            marke = "akzeptiert" if (behandlung or "") == "akzeptiert" else behandlung or "offen"
            print(f"  {projekt} #{rid} [{marke}] → _source_id={modul}:{art}:{req}"
                  f"   („{(name or '')[:44]}“)")

        print(f"\n  {len(aenderungen)} Risiko/Risiken ohne Herkunft mit Verknüpfung"
              + ("" if scharf else "   (TROCKENLAUF)"))
        if scharf and aenderungen:
            # Eine Transaktion: Ein halb nachgetragener Bestand wäre nicht
            # nachvollziehbar — danach stünde nicht fest, welche Akzeptanz
            # gelesen wird und welche nicht.
            with conn.cursor() as cur:
                for felder_json, rid in aenderungen:
                    cur.execute(
                        "UPDATE risikobewertung.rb_risiken "
                        "SET felder_json = %s WHERE id = %s", (felder_json, rid))
            conn.commit()   # ohne dies wäre der ganze Lauf wirkungslos (#1966)
            nachgetragen = len(aenderungen)
        else:
            # Der Trockenlauf hat eine offene Lesetransaktion. Ohne dies warnt
            # der Pool beim Zurückgeben ("rolling back returned connection"),
            # und eine Warnung im Lauf eines Werkzeugs wird beim zweiten Mal
            # nicht mehr gelesen.
            conn.rollback()
    finally:
        pool.putconn(conn)   # niemals close() — der Pool gehört der Anwendung (#1808)

    if ohne_verknuepfung:
        print("\n  Akzeptiert, aber ohne Verknüpfung — von Hand zu klären:")
        for h in ohne_verknuepfung:
            print(f"    ⚠ {h}")
    print(f"\n  nachgetragen: {nachgetragen}")
    if not scharf:
        print("  Trockenlauf — nichts geschrieben. Mit --nachtragen scharf laufen lassen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
