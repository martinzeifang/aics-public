"""Widersprüche in einem Formular rechnen — modulübergreifend (#1893).

WARUM DIESE DATEI EXISTIERT
---------------------------
#1885 hat die Prüfung für die CRA-Konformitätserklärung gebaut: Platzhalter,
Versions-Widersprüche, Wirkungsstufen. Dieselben drei Fehlerbilder treten in
jedem rechtlich vorgeschriebenen Formular auf — die AI-Act-Erklärung (#1889)
führt dieselbe Nummer und denselben Digest, das DSGVO-VVT (#1890) dieselbe
Art von Querverweis.

Die Muster hier je Modul zu wiederholen hieße, sie vier Mal unterschiedlich
falsch zu machen. Besonders die beiden Fallen, die #1885 gefunden hat, sind
teuer und nicht naheliegend:

1. **Ein blockierender Fehlalarm macht die Anwendung unbenutzbar.** Ein Regex
   auf jede Zahlenfolge liest „TLS 1.3" und „ISO/IEC 27001:2022" als
   Produktversion. Erkannt wird deshalb nur, was der Text **als Version
   ausgibt**.
2. **Der Prüfer darf nicht auf seinen eigenen Hinweistext anschlagen.**
   Abgeleitete Felder tragen absichtlich Texte wie ``[fehlt — Nr. 6 …]``.
   Geprüft wird eine **Positivliste** der Eingabefelder; eine Negativliste
   bricht beim nächsten abgeleiteten Feld.

DREI WIRKUNGEN, JE MIT GRUND
----------------------------
* :data:`WIRKUNG_BLOCKIERT` — **ohne** Bestätigungsmöglichkeit. Nur für Fälle
  ohne richtige Lesart. Eine Bestätigung anzubieten hieße, einen Weg um eine
  nachweislich falsche Aussage herum zu bauen (#1814/#1751).
* :data:`WIRKUNG_BESTAETIGUNG` — 428 mit benanntem Schlüssel, für echte
  Grenzfälle (Muster ``confirm_rot`` aus #1611).
* :data:`WIRKUNG_HINWEIS` — sichtbar, blockiert nicht. Für alles, was
  rechtlich zulässig ist und eine Entscheidung eines Menschen verlangt.

WAS HIER **NICHT** STEHT
------------------------
Feldnamen, Rechtsbezüge, Beschriftungen. Die Beschriftung eines Feldes kommt
als Callable vom Modul — sie steht in einer Fehlermeldung, also genau da, wo
ein Anwender sich auf sie verlässt, und eine zweite Zuordnung dafür wäre die
Spiegel-Liste aus #1731/#1735.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Iterable, Mapping

WIRKUNG_BLOCKIERT = "blockiert"
WIRKUNG_BESTAETIGUNG = "bestaetigung"
WIRKUNG_HINWEIS = "hinweis"

#: Eindeutige Platzhalter. Jedes Muster hier blockiert, muss also so
#: beschaffen sein, dass es in einem ernst gemeinten Formular **keine**
#: richtige Lesart hat. Ein bloßes „…" steht deshalb unter
#: :data:`MUSTER_HINWEIS`: Drei Punkte können in Prosa legitim vorkommen.
MUSTER_BLOCKIEREND: tuple[tuple[str, str], ...] = (
    (r"\[\s*zu\s+ergänzen\s*\]", "[zu ergänzen]"),
    (r"\[\s*FEHLT\s*\]", "[FEHLT]"),
    (r"\[\s*fehlt\b[^\]]*\]", "[fehlt …]"),
    (r"\[\s*(?:\.\.\.|…)\s*\]", "[…]"),
    (r"<\s*(?:\.\.\.|…)\s*>", "<…>"),
    (r"\bTBD\b", "TBD"),
    (r"\bTODO\b", "TODO"),
    (r"\bXXX\b", "XXX"),
    (r"\bplatzhalter\b", "Platzhalter"),
)

#: Schwächere Anzeichen — sie stehen zur Entscheidung, nicht im Weg.
MUSTER_HINWEIS: tuple[tuple[str, str], ...] = (
    (r"(?:\.\.\.|…)", "Auslassungszeichen"),
)

#: Ein Digest ist ``sha256:`` plus **64** Hex-Zeichen.
SHA_VOLL = re.compile(r"sha256:[0-9a-f]{64}\b")
SHA_ANFANG = re.compile(r"sha256:", re.IGNORECASE)

#: Eine Version **im Kontext** — siehe Falle 1 im Modul-Docstring.
VERSION_IM_KONTEXT = re.compile(
    r"(?:Release|Version|Fassung|Stand|Ausgabe)\s+v?(\d+(?:\.\d+){1,3})\b"
    r"|(?<![\w.])v(\d+(?:\.\d+){1,3})\b")

#: Freistehende Version (für Felder, die nur die Version enthalten).
VERSION_FREI = re.compile(r"\b[vV]?(\d+(?:\.\d+){1,3})\b")


class FormularUnstimmig(ValueError):
    """Das Formular trägt eine nachweislich falsche Aussage.

    Erbt von ``ValueError``, weil die REST-Schicht Fachfehler bereits als 409
    ausliefert.
    """

    def __init__(self, befunde: list[dict[str, Any]], *,
                 einleitung: str = "Das Formular kann nicht abgeschlossen "
                                   "werden") -> None:
        self.befunde = list(befunde)
        namen = "; ".join(b.get("text", "") for b in self.befunde[:4])
        super().__init__(f"{einleitung}: {namen}"
                         + (" …" if len(self.befunde) > 4 else ""))


class BestaetigungErforderlich(ValueError):
    """Ein Grenzfall, den nur ein Mensch verantworten kann."""

    def __init__(self, befunde: list[dict[str, Any]]) -> None:
        self.befunde = list(befunde)
        self.schluessel = sorted({b.get("confirm", "") for b in self.befunde
                                  if b.get("confirm")})
        super().__init__("; ".join(b.get("text", "") for b in self.befunde))


def _s(wert: Any) -> str:
    return "" if wert is None else str(wert).strip()


def befund(bid: str, *, feld: str = "", nr: int = 0, art: str = "",
           wirkung: str = WIRKUNG_HINWEIS, text: str = "", hinweis: str = "",
           confirm: str = "") -> dict[str, Any]:
    """Ein Befund in der Form, die alle Masken lesen."""
    b: dict[str, Any] = {"id": bid, "nr": int(nr), "feld": feld, "art": art,
                         "wirkung": wirkung, "text": text, "hinweis": hinweis}
    if confirm:
        b["confirm"] = confirm
    return b


def texte(werte: Mapping[str, Any], pruefbar: Iterable[str]
          ) -> list[tuple[str, str]]:
    """Die **Eingabewerte** als ``(feld, text)`` — Listen aufgelöst.

    ``pruefbar`` ist eine **Positivliste** (Falle 2 im Modul-Docstring).
    """
    erlaubt = {str(f) for f in pruefbar}
    out: list[tuple[str, str]] = []
    for feld, wert in (werte or {}).items():
        if str(feld) not in erlaubt:
            continue
        if isinstance(wert, (list, tuple)):
            out.extend((str(feld), _s(t)) for t in wert if _s(t))
        elif isinstance(wert, bool):
            continue
        elif _s(wert):
            out.append((str(feld), _s(wert)))
    return out


def versionen_im_kontext(text: Any) -> list[str]:
    """Versionen, die der Text als Version ausgibt (Reihenfolge erhalten)."""
    out: list[str] = []
    for m in VERSION_IM_KONTEXT.finditer(_s(text)):
        nummer = m.group(1) or m.group(2)
        if nummer and nummer not in out:
            out.append(nummer)
    return out


def version_nummer(wert: Any) -> str:
    """``Version 8.2.3`` → ``8.2.3``; ``v1.0`` → ``1.0``.

    Als Zeichenkette sind ``v1.0`` und ``1.0`` verschieden; sie bezeichnen
    dasselbe Release, und ein Abgleich auf der Zeichenkette hätte einen
    Widerspruch gemeldet, den es nicht gibt.
    """
    m = VERSION_FREI.search(_s(wert))
    return m.group(1) if m else ""


# ── Die drei wiederkehrenden Prüfungen ──────────────────────────────────────

def platzhalter_befunde(werte: Mapping[str, Any], pruefbar: Iterable[str],
                        label: Callable[[str], str],
                        nummer: Callable[[str], int]) -> list[dict[str, Any]]:
    """Platzhalter in den Eingabefeldern — blockierend, plus schwache Hinweise."""
    out: list[dict[str, Any]] = []
    gefunden = texte(werte, pruefbar)
    for feld, text in gefunden:
        for muster, bezeichnung in MUSTER_BLOCKIEREND:
            if re.search(muster, text, re.IGNORECASE):
                out.append(befund(
                    "platzhalter", feld=feld, nr=nummer(feld), art="platzhalter",
                    wirkung=WIRKUNG_BLOCKIERT,
                    text=f"Im Feld „{label(feld)}“ steht der Platzhalter "
                         f"„{bezeichnung}“.",
                    hinweis="Ein abgeschlossenes Formular darf keinen "
                            "Platzhalter tragen — es würde eine Angabe "
                            "behaupten, die nicht gemacht wurde."))
                break
    for feld, text in gefunden:
        for muster, bezeichnung in MUSTER_HINWEIS:
            if re.search(muster, text):
                out.append(befund(
                    "auslassung", feld=feld, nr=nummer(feld), art="platzhalter",
                    wirkung=WIRKUNG_HINWEIS,
                    text=f"Im Feld „{label(feld)}“ steht ein {bezeichnung} — "
                         "prüfe, ob die Angabe vollständig ist.",
                    hinweis="In Prosa kann das gewollt sein; in einer Angabe, "
                            "die den Gegenstand bezeichnet, ist es meist ein "
                            "Rest."))
                break
    return out


def digest_befunde(werte: Mapping[str, Any], pruefbar: Iterable[str],
                   label: Callable[[str], str], nummer: Callable[[str], int],
                   *, hinweis: str = "") -> list[dict[str, Any]]:
    """Ein angefangener, aber unvollständiger ``sha256:``-Digest."""
    out: list[dict[str, Any]] = []
    for feld, text in texte(werte, pruefbar):
        if not SHA_ANFANG.search(text):
            continue
        if len(SHA_VOLL.findall(text)) < len(SHA_ANFANG.findall(text)):
            out.append(befund(
                "digest_unvollstaendig", feld=feld, nr=nummer(feld),
                art="platzhalter", wirkung=WIRKUNG_BLOCKIERT,
                text=f"Im Feld „{label(feld)}“ steht ein unvollständiger "
                     "Digest (sha256 ohne die 64 Hex-Zeichen).",
                hinweis=hinweis or "Der Digest bezeichnet das Artefakt, das in "
                                   "Verkehr geht."))
    return out


def version_befunde(werte: Mapping[str, Any], felder: Iterable[str],
                    erlaubt: Iterable[str],
                    label: Callable[[str], str], nummer: Callable[[str], int],
                    *, hinweis: str = "") -> list[dict[str, Any]]:
    """Eine genannte Version, die die Akte für diesen Stand nicht kennt.

    Ist ``erlaubt`` leer, findet **kein** Abgleich statt — ohne
    Vergleichsmaßstab wäre jede genannte Version „falsch", und ein Prüfer, der
    immer anschlägt, wird abgeschaltet (#1805).
    """
    menge = {v for v in (str(e) for e in erlaubt) if v}
    if not menge:
        return []
    out: list[dict[str, Any]] = []
    for feld in felder:
        for genannt in versionen_im_kontext(werte.get(feld)):
            if genannt not in menge:
                out.append(befund(
                    "version_widerspruch", feld=feld, nr=nummer(feld),
                    art="widerspruch", wirkung=WIRKUNG_BLOCKIERT,
                    text=f"Im Feld „{label(feld)}“ steht Version {genannt}; "
                         f"die Akte kennt für diesen Stand "
                         f"{', '.join(sorted(menge))}.",
                    hinweis=hinweis or "Eine der Angaben ist falsch. "
                                       "Maßgeblich ist die Version, die "
                                       "herausgegeben wird."))
    return out


def versions_konflikt_befunde(
        paare: Iterable[tuple[str, Iterable[str]]],
        label: Callable[[str], str], nummer: Callable[[str], int],
        *, hinweis: str = "", bid: str = "versionen_widersprechen",
) -> list[dict[str, Any]]:
    """Zwei Felder desselben Formulars, die **verschiedene** Versionen nennen.

    Das ist die andere Frage als :func:`version_befunde` — und genau die, die
    im Betrieb durchfiel (#1901). Dort wird jedes Feld **gegen die Akte**
    geprüft („kennt die Akte diese Version?"); hier werden die Felder
    **gegeneinander** geprüft. Im gemeldeten Fall nannte Nr. 1 die Version
    8.0.11 und Nr. 4 „Release 8.0.1": Beide sind der Akte bekannt, also war
    jede Angabe einzeln plausibel — zusammen widersprechen sie sich, und kein
    Abgleich gegen die Akte kann das sehen.

    ``paare`` sind ``(feld, versionen)``. Die **Gewinnung** der Versionen
    bleibt beim Aufrufer: Ein Freitextfeld durchsucht man mit
    :func:`versionen_im_kontext` (nur „Release 8.0.1", nie „TLS 1.3"), ein
    Feld, das nichts als die Version enthält, mit :func:`version_nummer`. Diese
    Unterscheidung ist fachlich und gehört nicht hierher.

    **Blockierend**, weil es keine richtige Lesart gibt: Eine Erklärung, die
    zwei Releases nennt, bezeichnet nicht, was in Verkehr geht — dieselbe
    Begründung wie beim Platzhalter. Welche der beiden Angaben stimmt, kann
    die Anwendung nicht entscheiden; **dass** sie auseinanderfallen, kann sie.
    """
    je_feld: list[tuple[str, set[str]]] = []
    for feld, versionen in paare:
        menge = {v for v in (str(x) for x in versionen) if v}
        if menge:
            je_feld.append((feld, menge))
    alle = {v for _f, m in je_feld for v in m}
    if len(je_feld) < 2 or len(alle) < 2:
        return []
    # Felder, die für sich mehrere Versionen nennen, sind kein Widerspruch:
    # Ein Gegenstandstext darf „ersetzt Release 8.0.1" sagen. Beanstandet wird
    # nur, wenn zwei Felder **keine** gemeinsame Version haben.
    konflikt = any(not (m1 & m2)
                   for i, (_f1, m1) in enumerate(je_feld)
                   for _f2, m2 in je_feld[i + 1:])
    if not konflikt:
        return []
    genannt ="; ".join(f"„{label(f)}“ nennt {', '.join(sorted(m))}"
                        for f, m in je_feld)
    return [befund(
        bid, feld=je_feld[0][0], nr=nummer(je_feld[0][0]), art="widerspruch",
        wirkung=WIRKUNG_BLOCKIERT,
        text=f"Die Angaben widersprechen sich: {genannt}.",
        hinweis=hinweis or "Eine der Angaben ist falsch. Kläre in der Akte, "
                           "welcher Stand erklärt wird — mit diesem "
                           "Widerspruch darf nicht unterschrieben werden.")]


def unbelegte_angaben_befunde(
        angaben: Iterable[Any], *, belegt: Iterable[str], katalog: Iterable[str],
        feld: str, nr: int, bid: str, was: str, akte: str,
        hinweis: str = "") -> list[dict[str, Any]]:
    """Genannt, aber von der Akte nicht belegt — ein Hinweis, keine Sperre.

    Der gemeldete Fall (#1901): Nr. 6 der EU-Konformitätserklärung nannte
    CycloneDX, SLSA, Sigstore/cosign und OWASP Top 10, belegt waren in der
    Akte nur OWASP Proactive Controls und SPDX. Das ist eine unbelegte Aussage
    in einem Dokument, das der Hersteller unter Alleinverantwortung
    unterschreibt — und sie war **nicht gerechnet**, sondern kam als Bemerkung
    des Modells zurück.

    **Nie blockierend.** Ein Haus darf eine Spezifikation anwenden, die diese
    Anwendung nicht führt oder nicht erkennt; die Angabe wäre dann richtig und
    die Akte unvollständig. Ein blockierender Befund würde hier das Formular
    gegen den Anwender wenden. Gesagt werden muss es trotzdem, und zwar vor
    der Unterschrift.
    """
    bel = {_s(b).casefold() for b in belegt if _s(b)}
    kat = {_s(k).casefold() for k in katalog if _s(k)}
    ohne_beleg = [a for a in (_s(x) for x in angaben or ())
                  if a and a.casefold() not in bel]
    if not ohne_beleg:
        return []
    fremd = [a for a in ohne_beleg if a.casefold() not in kat]
    teile = [f"„{a}“" for a in ohne_beleg]
    zusatz = ("" if not fremd else
              f" Nicht aus der Auswahlliste gewählt: {', '.join(f'„{a}“' for a in fremd)}.")
    return [befund(
        bid, feld=feld, nr=nr, art="unbelegt", wirkung=WIRKUNG_HINWEIS,
        text=f"{was}: {', '.join(teile)} — dazu liegt in der Akte kein "
             f"Beleg vor.{zusatz}",
        hinweis=hinweis or (f"Belegt ist {akte}. Entweder die Angabe auf das "
                            "Belegte zurückführen oder den Nachweis in der "
                            "Akte erfassen — sonst enthält die unterschriebene "
                            "Erklärung eine unbelegte Aussage."))]


def datum_vor_befund(datum: Any, bezug: Any, *, feld: str, nr: int,
                     confirm: str, was: str, bezug_label: str,
                     bid: str = "datum_vor_bezug") -> list[dict[str, Any]]:
    """Ein Datum, das vor einem Bezugszeitpunkt liegt — Bestätigung, keine Sperre.

    Grenzfälle existieren (Zeitzonen, „Teil des Freigabepakets"), also wäre ein
    hartes Verbot falsch; ein stiller Durchlauf wäre die Fail-open-Richtung,
    die #1751 geschlossen hat.
    """
    d, b = _s(datum)[:10], _s(bezug)[:10]
    if not d or not b or d >= b:
        return []
    return [befund(
        bid, feld=feld, nr=nr, art="widerspruch",
        wirkung=WIRKUNG_BESTAETIGUNG, confirm=confirm,
        text=f"{was} ist auf {d} datiert, {bezug_label} liegt am {b}.",
        hinweis="Ein Dokument, das vor seinem Bezugszeitpunkt datiert, "
                "behauptet die Prüfung eines Zustands, der zu diesem "
                "Zeitpunkt nicht feststand.")]


def blockierend(befunde: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(b) for b in befunde if b.get("wirkung") == WIRKUNG_BLOCKIERT]


def bestaetigungen(befunde: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(b) for b in befunde
            if b.get("wirkung") == WIRKUNG_BESTAETIGUNG]


def offene_bestaetigungen(befunde: Iterable[Mapping[str, Any]],
                          bestaetigt: Iterable[str]) -> list[dict[str, Any]]:
    gegeben = {str(s) for s in (bestaetigt or ())}
    return [b for b in bestaetigungen(befunde)
            if b.get("confirm") not in gegeben]


def katalog_zuordnung(angaben: Iterable[Any], *,
                      zusatz: Mapping[str, tuple[int, str]] | None = None
                      ) -> tuple[dict[str, int], dict[str, str]]:
    """Feld → Nummer und Feld → Beschriftung aus einem Anhang-Katalog.

    ``angaben`` sind Objekte mit ``nr``, ``bezeichnung`` und ``felder`` — die
    Form, die ``cra.doc_export.ANHANG_V`` und ``ai_act.doc_export.ANHANG_V``
    teilen. ``zusatz`` ergänzt Felder, die der Katalog nicht als eigene Angabe
    führt.
    """
    nummern: dict[str, int] = {}
    labels: dict[str, str] = {}
    for a in angaben:
        for feld in getattr(a, "felder", ()) or ():
            nummern.setdefault(str(feld), int(getattr(a, "nr", 0) or 0))
            labels.setdefault(str(feld), str(getattr(a, "bezeichnung", feld)))
    for feld, (nr, label) in (zusatz or {}).items():
        nummern.setdefault(str(feld), int(nr))
        labels.setdefault(str(feld), str(label))
    return nummern, labels


__all__ = ["WIRKUNG_BLOCKIERT", "WIRKUNG_BESTAETIGUNG", "WIRKUNG_HINWEIS",
           "MUSTER_BLOCKIEREND", "MUSTER_HINWEIS", "SHA_VOLL", "SHA_ANFANG",
           "VERSION_IM_KONTEXT", "VERSION_FREI", "FormularUnstimmig",
           "BestaetigungErforderlich", "befund", "texte",
           "versionen_im_kontext", "version_nummer", "platzhalter_befunde",
           "digest_befunde", "version_befunde", "versions_konflikt_befunde",
           "unbelegte_angaben_befunde", "datum_vor_befund",
           "blockierend", "bestaetigungen", "offene_bestaetigungen",
           "katalog_zuordnung"]
