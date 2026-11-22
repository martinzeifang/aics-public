"""Eine freigegebene Zuordnung schließt die Anforderung ab (#1991).

DER WUNSCH AUS DEM BETRIEB
„Ich will beim Einlesen die Möglichkeit haben, das Thema abschließend zu
machen. Sonst bringt das ja alles nichts. Hinweise sind ok, aber wenn ich
übernehmen klicke, dann erwarte ich, dass die Frage beantwortet ist. Ich habe
das ja gelesen und geprüft." — und auf Rückfrage: **für alle Module.**

WARUM DAS DIE #1526-REGEL NICHT BRICHT
Die Regel lautet: **der Abgleich bewertet nicht.** Ein geschlossenes Issue, ein
eingetroffener Befund, ein KI-Lauf — keiner darf eine Bewertung setzen, weil
keiner von ihnen ein Mensch ist. Hier ist es umgekehrt: Der Bearbeiter liest
die belegte Aussage, prüft sie gegen das Dokument und klickt. **Das ist die
fachliche Prüfung**, dieselbe Handlung wie der Haken an einer Einzelbewertung
(die Linie aus #1773 — „der Akt selbst ist die Prüfung" — und #1868).

Vor #1991 war die Freigabe schreib-nur in einem zweiten Sinn: Sie legte einen
Beleg ab, der *irgendwann* in einem KI-Lauf wirken würde. Wer 65 Prüffragen
belegt hatte, brauchte danach **65 KI-Läufe**, um sie beantwortet zu bekommen —
und der Sammel-Prompt trägt den Nachweis-Block bewusst nicht. Die Arbeit lag
damit auf dem einen Weg, den man bei 65 Fragen nicht geht.

DIE VIER ENTSCHEIDUNGEN, DIE DAS VERTRETBAR MACHEN

1. **Die Antwort wählt der Mensch, sie wird nicht erraten.** Eine belegte
   Aussage ist meist ein „ja" bzw. „überwiegend umgesetzt" — aber nicht immer:
   Dokument 15 eines Mandanten heißt „Offene Punkte und begründete
   Abweichungen", und ein Beleg daraus stützt ein **nein**. ``antwort`` hat in
   dieser Funktion **keine** Vorgabe; die Maske schlägt eine vor und zeigt sie.
2. **Die Spur nennt die Grundlage.** Fundstelle, belegte Aussage, Person,
   Datum. Eine Bewertung, deren Grundlage nicht in der Akte steht, ist in
   einem Nachweiswerkzeug keine Bewertung.
3. **Ein bestehender Stand wird nicht stillschweigend ersetzt.** Der Bericht
   nennt den Vorzustand, und der vorige Kommentar bleibt darunter stehen — die
   Lehre aus #1988, wo 50 von 179 Freigaben lautlos eine frühere überschrieben
   haben.
4. **Geschrieben wird über die Speicherfunktion des Moduls**, nicht daneben.
   Ein zweiter Schreibweg wäre eine zweite Wahrheit über denselben
   Erfüllungsstand (#1726/#1727).

WARUM DIE VORGABE BEI DEN SCORE-MODULEN **4** IST UND NICHT 5
``cra/konformitaet_gate._ERFUELLT_AB`` ist 4 — das ist die Schwelle, ab der das
Gate eine Anforderung als *erfüllt* zählt. Die Skala nennt 4 „Überwiegend
umgesetzt" und 5 „Vollständig umgesetzt". **Ein** belegter Satz trägt die
erfüllte Anforderung, nicht die Vollständigkeit; 5 bleibt eine eigene,
ausdrückliche Entscheidung.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Stabiler Vorsatz der Kommentarzeile. Daran erkennt ein Leser die Herkunft
#: wieder — und sieht sofort, dass **kein** KI-Lauf sie gesetzt hat.
MARKER = "✅ Abschließend bewertet aus freigegebenem Nachweis"

#: Die Punkteskala der vier Score-Module, als Antwortmöglichkeiten.
#: Eine ``""`` heißt ausdrücklich „nur Beleg, nicht bewerten" — der Weg, der
#: vor #1991 der einzige war und der bleiben muss: Nicht jeder Beleg ist ein
#: Urteil.
SCORE_ANTWORTEN = ("", "5", "4", "3", "2", "1")
STATUS_ANTWORTEN = ("", "ja", "nein", "nicht_relevant")


@dataclass(frozen=True)
class Abschluss:
    """Wie ein Modul eine Anforderung abschließt."""

    db: str
    art: str          #: ``score`` (0–5) oder ``status`` (ja/nein/…)
    vorgabe: str      #: Was die Maske vorschlägt
    objekt: str       #: Wie das Objekt in der Oberfläche heißt


#: Modul → Abschlussart. Die Schlüssel sind die des Erschließungs-Katalogs
#: (``evidence/erschliessung.MODULE``) — ein Modul, das dort erschlossen werden
#: kann, muss hier stehen, sonst ist die Freigabe wieder schreib-nur.
MODULE: dict[str, Abschluss] = {
    "cra": Abschluss("data/db/cra.sqlite", "score", "4", "Anforderung"),
    "nis2": Abschluss("data/db/nis2.sqlite", "score", "4", "Anforderung"),
    "aiact": Abschluss("data/db/ai_act.sqlite", "score", "4", "Anforderung"),
    "dsgvo": Abschluss("data/db/dsgvo.sqlite", "score", "4", "Anforderung"),
    "wiba": Abschluss("data/db/wiba.sqlite", "status", "ja", "Prüffrage"),
}

#: Modul → (Paket, Firmen-Namensfeld). AI Act nutzt ``organisation``
#: (die Warnung steht so in ``shared/firmen_link``).
_PAKET: dict[str, tuple[str, str]] = {
    "cra": ("cra.db", "unternehmen"),
    "nis2": ("nis2.db", "unternehmen"),
    "aiact": ("ai_act.db", "organisation"),
    "dsgvo": ("dsgvo.db", "unternehmen"),
    "wiba": ("wiba.db", "unternehmen"),
}


class AbschlussFehler(RuntimeError):
    """Nicht abschließbar (→ 400/409 im Endpunkt)."""


def antworten(modul: str) -> tuple[str, ...]:
    """Die zulässigen Antworten eines Moduls."""
    eintrag = MODULE.get((modul or "").lower())
    if not eintrag:
        return ("",)
    return SCORE_ANTWORTEN if eintrag.art == "score" else STATUS_ANTWORTEN


def _modul(modul: str) -> Abschluss:
    eintrag = MODULE.get((modul or "").lower())
    if not eintrag:
        raise AbschlussFehler(
            f"Für „{modul}“ ist kein Abschluss vorgesehen.")
    return eintrag


def projekte_der_firma(modul: str, firma: str) -> list[str]:
    """Die Projekte eines Mandanten in diesem Modul.

    Gesucht wird über das **Namensfeld** und über ``firmen_id``, weil beides
    vorkommt: Auf Produktiv heißt das WiBA-Projekt ``Cyberwoks`` und trägt
    ``unternehmen = 'Firma Cyberwoks'`` bei ``firmen_id = 500003``. Eine Suche
    über nur eins von beiden findet je nach Installation nichts.
    """
    import importlib

    eintrag = _modul(modul)
    paket, feld = _PAKET[(modul or "").lower()]
    db = Path(eintrag.db)
    mod = importlib.import_module(paket)
    gesucht = (firma or "").strip().casefold()
    if not gesucht:
        return []

    kennungen: set[str] = set()
    try:
        from firmen.db import firmen_zeilen
        kennungen = {str(z.get("id")) for z in firmen_zeilen()
                     if str(z.get("name") or "").casefold() == gesucht}
    except Exception:  # noqa: BLE001 — ohne Firmentabelle bleibt der Name
        pass

    treffer: list[str] = []
    for eintrag_ in mod.list_projekte(db) or []:
        # **Die Module liefern zwei verschiedene Formen**, und das ist kein
        # Versehen, sondern Bestand: CRA, NIS2, AI Act und DSGVO geben
        # ``list[str]`` (nur Namen), WiBA ``list[dict]`` (ganze Zeilen). Eine
        # Schleife, die Namen annimmt, übergibt WiBA ein Dict an
        # ``load_projekt`` — unter PostgreSQL „cannot adapt type 'dict'".
        # Gefunden beim Lauf gegen die echte Testinstanz, nicht im Test (#1993).
        if isinstance(eintrag_, dict):
            p = eintrag_
            name = str(p.get("name") or "")
            if not name:
                continue
        else:
            name = str(eintrag_)
            p = mod.load_projekt(db, name) or {}
        if str(p.get(feld) or "").strip().casefold() == gesucht:
            treffer.append(name)
            continue
        kennung = str(p.get("firmen_id") or "")
        if kennung and kennung in kennungen:
            treffer.append(name)
    return sorted(set(treffer))


def _kommentar(*, claim: str, dokumente: list[str], rationale: str,
               person: str, datum: str, vorher: str) -> str:
    """Grundlage zuerst, Vorzustand darunter."""
    teile = [f"{MARKER} am {datum} durch {person or 'unbekannt'}."]
    if dokumente:
        teile.append(f"Fundstelle: {', '.join(dokumente)}.")
    teile.append(f"Belegte Aussage: {claim.strip()}")
    if rationale.strip():
        teile.append(f"Begründung: {rationale.strip()}")
    neu = "\n".join(teile)
    if vorher.strip() and MARKER not in vorher:
        # Der vorige Text ist die Aussage eines Menschen und darf nicht
        # verschwinden, weil ein neuer dazukommt (#1988). Ein früherer
        # Abschluss derselben Art wird dagegen ersetzt — sonst wächst der
        # Kommentar bei jedem Beleg um einen Block.
        neu += "\n\n--- vorheriger Kommentar ---\n" + vorher.strip()
    return neu


def abschliessen(
    modul: str,
    *,
    projekt: str,
    objekt_id: str,
    antwort: str,
    claim: str,
    dokumente: list[str] | None = None,
    doc_ids: list[str] | None = None,
    rationale: str = "",
    person: str = "",
    datum: str = "",
) -> dict[str, Any]:
    """Setzt Bewertung bzw. Antwort aus einer freigegebenen Zuordnung.

    Returns:
        ``{modul, projekt, objekt_id, antwort, vorher, ersetzt, text}``.
        ``antwort == ""`` heißt „nur Beleg" — es wird **nichts** geschrieben.

    Raises:
        AbschlussFehler: unbekanntes Modul, unzulässige Antwort, fehlende
            Angaben.
    """
    import importlib

    eintrag = _modul(modul)
    schluessel = (modul or "").lower()
    erlaubt = antworten(schluessel)
    if antwort not in erlaubt:
        raise AbschlussFehler(
            f"Unzulässige Antwort {antwort!r} für {schluessel} — erlaubt sind "
            + ", ".join(a or "(nur Beleg)" for a in erlaubt))
    leer = {"modul": schluessel, "projekt": projekt, "objekt_id": objekt_id,
            "antwort": "", "vorher": "", "ersetzt": False, "text": ""}
    if not antwort:
        return leer
    if not projekt or not objekt_id:
        raise AbschlussFehler("Projekt und Objekt sind Pflicht.")
    if not claim.strip():
        raise AbschlussFehler(
            "Ohne belegte Aussage kein Abschluss — sie ist die Grundlage.")

    paket, _feld = _PAKET[schluessel]
    mod = importlib.import_module(paket)
    db = Path(eintrag.db)

    if eintrag.art == "status":
        bestand = mod.load_antworten(db, projekt).get(objekt_id, {}) or {}
        vorher = str(bestand.get("status") or "offen")
        alte_ids = bestand.get("evidence_doc_ids") or []
        if isinstance(alte_ids, str):
            try:
                alte_ids = json.loads(alte_ids)
            except Exception:  # noqa: BLE001
                alte_ids = []
        # Belege kommen dazu, sie ersetzen nicht: An einer Prüffrage können
        # mehrere hängen, und der zweite macht den ersten nicht ungültig.
        ids = list(dict.fromkeys([*(str(i) for i in alte_ids if i),
                                  *(str(i) for i in (doc_ids or []) if i)]))
        text = _kommentar(claim=claim, dokumente=list(dokumente or []),
                          rationale=rationale, person=person, datum=datum,
                          vorher=str(bestand.get("notiz") or ""))
        mod.save_antwort(db, projekt, objekt_id, status=antwort, notiz=text,
                         verantwortlich=str(bestand.get("verantwortlich") or ""),
                         zieldatum=str(bestand.get("zieldatum") or ""),
                         evidence_doc_ids=ids)
        ersetzt = vorher not in ("", "offen") and vorher != antwort
    else:
        bestand = mod.load_bewertungen(db, projekt).get(objekt_id, {}) or {}
        vorher = str(bestand.get("bewertung") or 0)
        text = _kommentar(claim=claim, dokumente=list(dokumente or []),
                          rationale=rationale, person=person, datum=datum,
                          vorher=str(bestand.get("kommentar") or ""))
        mod.save_bewertung(db, projekt, objekt_id, int(antwort),
                           kommentar=text,
                           massnahme=str(bestand.get("massnahme") or ""),
                           verantwortlich=str(bestand.get("verantwortlich") or ""),
                           zieldatum=str(bestand.get("zieldatum") or ""))
        ersetzt = vorher not in ("", "0") and vorher != antwort

    return {"modul": schluessel, "projekt": projekt, "objekt_id": objekt_id,
            "antwort": antwort, "vorher": vorher, "ersetzt": ersetzt,
            "text": text}


__all__ = [
    "MARKER",
    "MODULE",
    "SCORE_ANTWORTEN",
    "STATUS_ANTWORTEN",
    "Abschluss",
    "AbschlussFehler",
    "abschliessen",
    "antworten",
    "projekte_der_firma",
]
