"""Tagesgenaue Fristenuhr für die langen CRA-Fristen (#1762).

WARUM NICHT ``cra/deadlines.py``
Für Art. 14 gibt es dort eine Fristenuhr — stundengenau, mit einer Ampel aus dem
**Anteil** der verbleibenden Zeit am Fenster der Stufe. Für 24h/72h ist das
richtig. Für die Fristen aus Art. 13 ist es unbrauchbar: 50 % Restzeit einer
Zehnjahresfrist sind fünf Jahre, die Ampel stünde also ein halbes Jahrzehnt auf
Gelb und wäre genau dann grün, wenn die Frist frisch ist. Diese Uhr rechnet
deshalb in **Tagen und absoluten Vorlaufzeiten**: Was mich interessiert, ist
„fällt das noch in dieses Haushaltsjahr?", nicht „wie viel Prozent sind um?".

``deadlines.py`` wird hier nur gelesen, nicht verändert — beides sind Uhren,
aber mit verschiedenen Zeigern.

WAS „VERSTRICHEN" HIER BEDEUTET
Die Fristen aus Art. 13 sind **endende Pflichten**, keine Termine, an denen man
etwas abliefern muss: Läuft die Aufbewahrungsfrist der technischen Dokumentation
ab, darf man sie wegwerfen — das ist kein Versäumnis. Die Ampel heißt deshalb im
Endzustand ``verstrichen`` und nicht ``overdue``; das Wort trägt keine Schuld.
Dieselbe Funktion bedient die Behördenfristen des Marktüberwachungsregisters
(``cra/marktueberwachung_db.py``) — dort ist eine verstrichene Frist sehr wohl
ein Versäumnis. Die Bewertung macht der Aufrufer, nicht die Uhr.

Das eigentliche Risiko, gegen das diese Uhr gebaut ist: Eine 2035 ablaufende
Aufbewahrungsfrist fällt niemandem auf — und wer sie nicht kennt, wirft die Akte
2030 weg. Sichtbar ist die laufende Pflicht, nicht erst ihr Ende.

Reines Python (stdlib), keine DB im Kern — ``fristen_fuer_projekt`` ist die
einzige Funktion, die lädt.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

CRA_DB = Path("data/db/cra.sqlite")

#: Vorlaufzeiten der langen Fristen (Art. 13). Ein Jahr Vorlauf auf Gelb, weil
#: die Entscheidung „Akte weiter aufbewahren oder Support verlängern" eine
#: Budget- und Planungsentscheidung ist und in die Jahresplanung gehört; 90 Tage
#: auf Rot, weil darunter nur noch handeln hilft.
VORLAUF_GELB_TAGE = 365
VORLAUF_ROT_TAGE = 90

#: Vorlaufzeiten für Behördenfristen (Art. 52-56). Dieselbe Mechanik, andere
#: Größenordnung: Eine Behörde setzt Tage, keine Jahre.
BEHOERDE_GELB_TAGE = 7
BEHOERDE_ROT_TAGE = 3

#: Die überwachten Fristen des Unterstützungszeitraums. ``ref`` ist die Stelle,
#: die dieses Repo zitiert — die Nummern stammen aus #1209 und sind hier nicht
#: nachgeprüft worden (in diesem Repo sind schon widersprüchliche Artikelzitate
#: aufgefallen, #1763). Wer sie belastbar braucht, prüft sie am Verordnungstext;
#: die Rechnung dahinter stimmt unabhängig von der Absatznummer.
AUFBEWAHRUNGSFRISTEN: tuple[dict[str, str], ...] = (
    {"key": "support_ende", "spalte": "eol_datum",
     "label": "Support-Ende — bis hierhin werden Sicherheitsupdates zugesagt",
     "ref": "Art. 13 Abs. 8"},
    {"key": "update_verfuegbarkeit", "spalte": "update_availability_until",
     "label": "Updates müssen verfügbar bleiben",
     "ref": "Art. 13 Abs. 9 (Zitat des Repos)"},
    {"key": "doku_aufbewahrung", "spalte": "doku_retention_until",
     "label": "Technische Dokumentation aufbewahren",
     "ref": "Art. 13 Abs. 13 (Zitat des Repos)"},
    {"key": "doc_aufbewahrung", "spalte": "doc_retention_until",
     "label": "EU-Konformitätserklärung aufbewahren",
     "ref": "Art. 13 Abs. 13 (Zitat des Repos)"},
)

#: Reihenfolge von harmlos nach dringend — für ``schlechteste_ampel``.
RANG = ("gruen", "gelb", "rot", "verstrichen")


def schlechteste_ampel(ampeln: Any) -> str:
    """Die dringendste Ampel einer Menge; ``unbekannt`` bei leerer Eingabe.

    Öffentlich, weil zwei Register danach fragen (Aufbewahrungsfristen und das
    Marktüberwachungsregister) und eine private Rangliste sonst zweimal
    nachgebaut würde — mit der Gefahr, dass die Reihenfolgen auseinanderlaufen.
    """
    bekannt = [a for a in (ampeln or []) if a in RANG]
    return max(bekannt, key=RANG.index) if bekannt else "unbekannt"


def parse_datum(wert: Any) -> Optional[date]:
    """ISO-Datum robust lesen; ``None`` bei leer **oder unlesbar**.

    Ein unlesbares Datum liefert bewusst ``None`` und nicht „heute": Eine Uhr,
    die bei Datenmüll irgendeine Zahl zeigt, ist schlimmer als eine, die
    zugibt, dass sie nichts weiß. Der Aufrufer sieht die Lücke in
    ``unbestimmbar`` bzw. ``ampel == 'unbekannt'``.
    """
    if isinstance(wert, datetime):
        return wert.date()
    if isinstance(wert, date):
        return wert
    s = str(wert or "").strip()[:10]
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def ampel_tage(tage_verbleibend: Optional[int], *,
               gelb_tage: int = VORLAUF_GELB_TAGE,
               rot_tage: int = VORLAUF_ROT_TAGE) -> str:
    """``gruen|gelb|rot|verstrichen|unbekannt`` aus der Restlaufzeit in Tagen."""
    if tage_verbleibend is None:
        return "unbekannt"
    if tage_verbleibend < 0:
        return "verstrichen"
    if tage_verbleibend <= rot_tage:
        return "rot"
    if tage_verbleibend <= gelb_tage:
        return "gelb"
    return "gruen"


def frist(wert: Any, *, heute: Optional[date] = None,
          gelb_tage: int = VORLAUF_GELB_TAGE,
          rot_tage: int = VORLAUF_ROT_TAGE) -> dict[str, Any]:
    """Eine einzelne Frist auswerten.

    Returns ``{datum, tage_verbleibend, ampel, verstrichen}``. ``datum`` ist
    ``None``, wenn nichts Lesbares vorlag — dann ist ``ampel='unbekannt'`` und
    ``verstrichen`` ist ``False``, nicht ``True``: Unbekannt ist nicht abgelaufen.
    """
    ref = heute or date.today()
    d = parse_datum(wert)
    tage = (d - ref).days if d is not None else None
    a = ampel_tage(tage, gelb_tage=gelb_tage, rot_tage=rot_tage)
    return {"datum": d.isoformat() if d else None, "tage_verbleibend": tage,
            "ampel": a, "verstrichen": a == "verstrichen"}


def behoerdenfrist(wert: Any, *, heute: Optional[date] = None) -> dict[str, Any]:
    """Behördenfrist (Art. 52-56) mit den kurzen Vorlaufzeiten."""
    return frist(wert, heute=heute, gelb_tage=BEHOERDE_GELB_TAGE,
                 rot_tage=BEHOERDE_ROT_TAGE)


def aufbewahrungsfristen(support_period: Optional[dict],
                         *, heute: Optional[date] = None) -> dict[str, Any]:
    """Fristenlauf der Aufbewahrungs- und Update-Verfügbarkeitsfristen.

    Erwartet eine Zeile aus ``cra_support_period`` (oder ``None``). Rein
    rechnend, damit sie ohne DB testbar bleibt.

    Returns::

        {"heute", "fristen": [{key,label,ref,datum,tage_verbleibend,ampel,
                               verstrichen}],
         "schlechteste_ampel", "naechste", "unbestimmbar": [keys],
         "berechenbar": bool, "markteintritt"}

    ``berechenbar`` ist ``False``, solange **keine** der vier Fristen ein Datum
    hat — das ist der eigentliche Mangel: Ohne Markteintritt weiß niemand, wie
    lange die Akte zu halten ist.
    """
    sp = support_period or {}
    ref = heute or date.today()
    fristen: list[dict[str, Any]] = []
    unbestimmbar: list[str] = []
    for spec in AUFBEWAHRUNGSFRISTEN:
        f = frist(sp.get(spec["spalte"]), heute=ref)
        f.update({"key": spec["key"], "label": spec["label"], "ref": spec["ref"]})
        if f["datum"] is None:
            unbestimmbar.append(spec["key"])
        fristen.append(f)

    bekannt = [f for f in fristen if f["datum"] is not None]
    schlechteste = schlechteste_ampel([f["ampel"] for f in bekannt])

    offen = sorted((f for f in bekannt if not f["verstrichen"]),
                   key=lambda f: f["datum"])
    return {
        "heute": ref.isoformat(),
        "markteintritt": str(sp.get("markteintritt_datum") or "")[:10] or None,
        "fristen": fristen,
        "schlechteste_ampel": schlechteste,
        "naechste": offen[0] if offen else None,
        "unbestimmbar": unbestimmbar,
        "berechenbar": bool(bekannt),
        "verstrichen": [f["key"] for f in bekannt if f["verstrichen"]],
    }


def fristen_fuer_projekt(db_path: Path = CRA_DB, projekt_name: str = "",
                         *, heute: Optional[date] = None) -> dict[str, Any]:
    """``aufbewahrungsfristen`` für ein Projekt — die einzige ladende Funktion."""
    from cra.db import load_support_period

    sp = load_support_period(db_path, projekt_name)
    ergebnis = aufbewahrungsfristen(sp, heute=heute)
    ergebnis["projekt_name"] = projekt_name
    ergebnis["erfasst"] = sp is not None
    return ergebnis
