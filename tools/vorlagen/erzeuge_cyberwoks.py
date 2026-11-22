#!/usr/bin/env python3
"""Word-Vorlagen im Cyberwoks-Design erzeugen — eine je Berichtstyp (#1790).

Ausgangslage: Für Cyberwoks gab es zwei Vorlagen, beide ohne Berichtstyp und
damit **modulweit**. Seit #1777 wählt das Berichts-Center die Vorlage je Bericht;
eine modulweite liefert für alle sieben CRA-Dokumente dasselbe Papier, bis hin
zur EU-Konformitätserklärung. Dieses Werkzeug erzeugt für jeden Berichtstyp eine
eigene Vorlage im selben Design.

    python3 tools/vorlagen/erzeuge_cyberwoks.py --ziel out/vorlagen
    python3 tools/vorlagen/erzeuge_cyberwoks.py --ziel out/vorlagen --nur cra

Das Design wird vom Rohling geerbt (``--rohling``), nicht nachgebaut: Styles,
Theme, Nummerierung und der Aufbau von Kopf- und Fußzeile bleiben erhalten.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.vorlagen import cyberwoks_bausteine as b  # noqa: E402
from tools.vorlagen.cyberwoks_plaene import PLAENE  # noqa: E402

#: Der Rohling, aus dem Briefpapier und Formatvorlagen stammen. Er liegt
#: nicht im Repository — es ist das Briefpapier eines Hauses, kein Quelltext.
#: Zu holen aus der Installation, z. B.:
#:   docker exec -u aics aics_web cat \
#:     /app/data/templates/cra/3__Vorlage_CRA_Readiness_Cyberwoks.docx > rohling.docx
STANDARD_ROHLING = Path("rohling.docx")


def dateiname(modul: str, typ: str, dokumentart: str) -> str:
    # Doppelpunkt und Schrägstrich raus: Solche Dateinamen lassen sich unter
    # Windows nicht speichern, und die Datei wandert über den Browser.
    sauber = (dokumentart.replace(" — ", "_").replace(" ", "_")
              .replace("·", "").replace("/", "-").replace(":", "")
              .replace("__", "_"))
    for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"),
                     ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue")):
        sauber = sauber.replace(alt, neu)
    return f"Cyberwoks_{modul}_{typ}_{sauber}.docx"


def erzeuge(rohling: Path, ziel_ordner: Path, *, nur: str | None = None) -> list[Path]:
    """Alle Vorlagen erzeugen und eine Zuordnungsdatei danebenlegen.

    Die Zuordnung (``zuordnung.json``) sagt, welche Datei zu welchem Modul und
    Berichtstyp gehört. Sie ist nicht Beiwerk: Beim ersten Einspielen wurde der
    Typ aus dem **Dateinamen** abgeleitet, und ``ohne_empfehlungen`` zerfiel am
    Unterstrich zu ``ohne`` — einem Berichtstyp, den es nicht gibt. Die Vorlage
    hing damit an einem Bericht, den niemand aufruft.
    """
    ziel_ordner.mkdir(parents=True, exist_ok=True)
    erzeugt: list[Path] = []
    zuordnung: list[dict[str, str]] = []

    for (modul, typ), plan in sorted(PLAENE.items()):
        if nur and modul != nur:
            continue
        dokumentart, titel_ausdruck, zeile_unten, untertitel, inhalt = plan

        doc = b.oeffne_rohling(rohling)
        b.titelblock(doc, dokumentart=dokumentart, titel_ausdruck=titel_ausdruck,
                     zeile_unten=zeile_unten, untertitel=untertitel)
        b.infotabelle(doc, _infozeilen(modul, dokumentart))
        inhalt(doc)
        b.kopf_und_fuss(
            doc, dokumentart=dokumentart, titel_ausdruck=titel_ausdruck,
            fuss_mitte=("Vertraulich · {{ projekt.unternehmen }} · "
                        f"{untertitel} · Stand {{{{ meta.datum or meta.erstellt_am }}}}"))
        b.setze_titel(doc, dokumentart)

        ziel = ziel_ordner / dateiname(modul, typ, dokumentart)
        doc.save(str(ziel))
        erzeugt.append(ziel)
        zuordnung.append({"datei": ziel.name, "modul": modul, "bericht_typ": typ,
                          "name": f"Cyberwoks {dokumentart}"})
        print(f"  {modul:<18} {typ:<24} → {ziel.name}")

    (ziel_ordner / "zuordnung.json").write_text(
        json.dumps(zuordnung, ensure_ascii=False, indent=1), encoding="utf-8")
    return erzeugt


def _infozeilen(modul: str, dokumentart: str) -> list[tuple[str, str]]:
    from tools.vorlagen.cyberwoks_plaene import _infos

    return _infos(modul, dokumentart)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rohling", type=Path, default=STANDARD_ROHLING,
                    help="DOCX, von der Design und Briefpapier geerbt werden")
    ap.add_argument("--ziel", type=Path, required=True, help="Ausgabeverzeichnis")
    ap.add_argument("--nur", help="nur dieses Modul erzeugen")
    args = ap.parse_args()

    if not args.rohling.exists():
        print(f"Rohling nicht gefunden: {args.rohling}", file=sys.stderr)
        return 2

    print(f"Rohling: {args.rohling}")
    erzeugt = erzeuge(args.rohling, args.ziel, nur=args.nur)
    print(f"\n{len(erzeugt)} Vorlage(n) in {args.ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
