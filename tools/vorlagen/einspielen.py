#!/usr/bin/env python3
"""Erzeugte Vorlagen in die Registry aufnehmen und als Standard setzen (#1790).

Läuft **in der Installation** (gleiche Datenbank, gleicher Storage-Pfad) und
geht denselben Weg wie der Upload über die Oberfläche
(:func:`shared.templates.storage.upload_template`) — keine zweite Schreibart
auf dieselben Tabellen.

    python3 tools/vorlagen/einspielen.py --ordner /tmp/cyberwoks-vorlagen

Die Zuordnung Modul/Berichtstyp kommt aus der ``zuordnung.json``, die der
Generator danebenlegt, **nicht** aus den Dateinamen: ``ohne_empfehlungen``
zerfällt dort am Unterstrich zu ``ohne``, und die Vorlage hängt dann an einem
Berichtstyp, den es nicht gibt.

Ohne ``--firma`` entstehen Haus-Vorlagen. Für einen Mandanten
(``--firma <id>``) gilt die Rangfolge aus #1777: Mandanten-Vorlage vor
Haus-Vorlage.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


#: Trägt eine Zeile diesen Namen, stammt sie aus diesem Werkzeug.
ERZEUGER = "Vorlagen-Generator"


def einspielen(ordner: Path, *, firmen_id: int | None, als_standard: bool,
               db_pfad: Path, ersetzen: bool = False) -> int:
    from shared.templates import db as tdb
    from shared.templates import storage

    zuordnung_datei = ordner / "zuordnung.json"
    if not zuordnung_datei.is_file():
        print(f"zuordnung.json fehlt in {ordner} — der Generator legt sie an.",
              file=sys.stderr)
        return 2
    eintraege = json.loads(zuordnung_datei.read_text(encoding="utf-8"))

    angelegt = fehler = 0
    for e in eintraege:
        datei = ordner / e["datei"]
        if not datei.is_file():
            print(f"  fehlt   : {e['datei']}")
            fehler += 1
            continue
        try:
            rec = storage.upload_template(
                datei, modul=e["modul"], name=e["name"], db_path=db_pfad,
                hochgeladen_von=ERZEUGER,
                notizen="Im Cyberwoks-Design erzeugt, je Berichtstyp eine Vorlage.",
                bericht_typ=e["bericht_typ"], firmen_id=firmen_id)
            if als_standard:
                tdb.set_default(db_pfad, int(rec["id"]))
            weg = _vorgaenger_stilllegen(tdb, db_pfad, rec) if ersetzen else 0
            angelegt += 1
            print(f"  angelegt: {e['modul']:<18} {e['bericht_typ']:<24} "
                  f"id={rec['id']} v{rec['version']}"
                  + (f" (ersetzt {weg})" if weg else ""))
        except Exception as ex:  # noqa: BLE001 — eine schlechte Datei stoppt nicht alle
            fehler += 1
            print(f"  FEHLER  : {e['datei']}: {type(ex).__name__}: {ex}")

    _vermerken(angelegt, firmen_id)
    print(f"\n{angelegt} angelegt, {fehler} Fehler")
    return 0 if not fehler else 1


def _vorgaenger_stilllegen(tdb, db_pfad: Path, neu: dict) -> int:
    """Frühere Fassungen desselben Berichts abschalten.

    Ein erneuter Upload legt eine **neue Version** an; die alte bleibt aktiv und
    steht weiter in der Liste. Bei einem Austausch ist das falsch: Die alte
    Fassung ist nicht eine Wahlmöglichkeit, sondern die fehlerhafte — wer sie
    greift, bekommt den Fehler zurück, den der Austausch beseitigen sollte.

    **Verglichen wird der Platz, nicht der Name.** Beim ersten Einspielen kam
    der Name aus dem Dateinamen und war deshalb umschrifttreu („Cyberwoks
    CRA-Massnahmenplan"); jetzt kommt er aus der ``zuordnung.json`` („Cyberwoks
    CRA-Maßnahmenplan"). Über den Namen gesucht blieben vierzehn alte Vorlagen
    stehen — ohne Standardmarkierung, aber auswählbar. Der Platz ist
    (Modul, Berichtstyp, Mandant); das ist dieselbe Zuständigkeit, in der auch
    ``set_default`` exklusiv ist (#1777/#1778).

    Angefasst wird nur, was dieses Werkzeug selbst angelegt hat. Eine von Hand
    hochgeladene Vorlage für denselben Bericht ist eine Entscheidung des Hauses
    und geht einen Austausch nichts an.

    Abgeschaltet wird mit ``soft_delete``: Zeile und Datei bleiben erhalten, nur
    unsichtbar. Ein Austausch, der sich nicht zurücknehmen lässt, wäre in einem
    Nachweiswerkzeug die schlechtere Richtung.
    """
    weg = 0
    for alt in tdb.list_templates(db_pfad, neu["modul"]):
        if alt["id"] == neu["id"]:
            continue
        gleicher_platz = (str(alt.get("bericht_typ") or "")
                          == str(neu.get("bericht_typ") or "")
                          and _f(alt.get("firmen_id")) == _f(neu.get("firmen_id")))
        if not gleicher_platz or (alt.get("hochgeladen_von") or "") != ERZEUGER:
            continue
        tdb.soft_delete(db_pfad, int(alt["id"]), by=ERZEUGER,
                        reason=f"ersetzt durch Fassung v{neu['version']} (id={neu['id']})")
        weg += 1
    return weg


def _f(wert) -> int | None:
    return None if wert in (None, "", 0) else int(wert)


def _vermerken(anzahl: int, firmen_id: int | None) -> None:
    """Das Einspielen gehört in den Revisionspfad.

    Über die Oberfläche schreibt der Upload-Endpunkt ein ``templates.uploaded``;
    dieser Weg geht an ihm vorbei und muss den Eintrag selbst setzen. Einer für
    den Vorgang, nicht einer je Datei.
    """
    try:
        from shared.audit import audit_event

        audit_event("templates.uploaded", module="templates", details={
            "user_id": "system",
            "vorgang": "Vorlagensatz eingespielt",
            "anzahl": anzahl,
            "firmen_id": firmen_id,
            "hinweis": "über die Storage-Schicht eingespielt, nicht über die Oberfläche",
        })
    except Exception:  # noqa: BLE001
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ordner", type=Path, required=True,
                    help="Verzeichnis mit den DOCX und der zuordnung.json")
    ap.add_argument("--firma", type=int, default=None,
                    help="firmen_id für Mandanten-Vorlagen (ohne: Haus-Vorlagen)")
    ap.add_argument("--kein-standard", action="store_true",
                    help="nur anlegen, nicht als Standard setzen")
    ap.add_argument("--ersetzen", action="store_true",
                    help="ältere Fassungen derselben Vorlage abschalten "
                         "(Soft-Delete, umkehrbar)")
    ap.add_argument("--db", type=Path, default=Path("data/db/templates.sqlite"))
    args = ap.parse_args()

    sys.path.insert(0, str(Path.cwd()))
    return einspielen(args.ordner, firmen_id=args.firma,
                      als_standard=not args.kein_standard, db_pfad=args.db,
                      ersetzen=args.ersetzen)


if __name__ == "__main__":
    raise SystemExit(main())
