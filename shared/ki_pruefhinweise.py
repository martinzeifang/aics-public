"""Was an einem KI-Entwurf auffällig ist — gerechnet, nicht erfragt (#1862).

DER BEFUND
Human-in-Control heißt heute: Der Mensch liest jeden KI-Entwurf und entscheidet.
Bei 257 WiBA-Prüffragen oder 130 CRA-Anforderungen ist genau das der Engpass —
und er wird schlimmer, je mehr die KI erzeugt. Ein plausibel aussehender
falscher Entwurf ist **aufwendiger** zu prüfen als ein leeres Feld: Beim leeren
Feld weiß man, dass man ran muss.

Was fehlt, ist nicht mehr Material, sondern der Satz davor: „Schau hier genauer
hin, und zwar deshalb."

WARUM OHNE KI-LAUF
Jeder Hinweis hier steht schon im Ergebnis des Laufs und in seinem Umfeld — er
wird nur niemandem gesagt. Eine zweite Anfrage an das Modell („prüfe deine
eigene Antwort") wäre teuer, langsam und eine **zweite Wahrheit** über denselben
Vorgang; dieselbe Regel wie bei den zwei Berichts-Renderern in #1726/#1727.
Was gerechnet werden kann, wird gerechnet.

DIE GRENZE
Die Hinweise sagen **nicht**, ob der Entwurf richtig ist — nur, woran man
zweifeln sollte. Ein Hinweis, der wie ein Urteil gelesen wird, nimmt dem
Menschen die Entscheidung ab, und das ist das Gegenteil des Zwecks. Deshalb
sind die Texte beschreibend („ohne Beleg“), nicht wertend („falsch“).

UND: EIN HINWEIS, DER IMMER ERSCHEINT, IST KEINER
Der Normalfall bekommt **nichts** — kein „alles in Ordnung“. Ein Entwurf mit
Belegen, vollständiger Antwort und übereinstimmenden Läufen erzeugt eine leere
Liste. Dieselbe Regel wie bei den gerechneten Prüfpunkten, die bei richtigem
Verhalten nicht anschlagen dürfen (#1774): Wer bei allem anschlägt, wird
abgeschaltet.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

#: Ab welcher Bewertung ein Entwurf **Erfüllung behauptet** (0–5-Module).
#:
#: Dieselbe Schwelle wie ``cra/konformitaet_gate._ERFUELLT_AB`` („Bewertung ≥ 4
#: = überwiegend/vollständig umgesetzt", #1612). Sie steht hier ein zweites Mal,
#: weil ``shared`` nicht von einem Fachmodul abhängen darf — die Richtung wäre
#: verkehrt. Damit daraus keine stille Drift wird (die Fehlerklasse aus
#: #1731/#1735), hält ``tests/test_ki_pruefhinweise_1862.py`` beide Werte
#: gegeneinander.
ERFUELLUNG_AB = 4

#: Gewichte. Nur drei Stufen, und sie bedeuten etwas:
#: 1 = beiläufig · 2 = genauer ansehen · 3 = sehr wahrscheinlich nachzuarbeiten.
#: Eine feinere Skala wäre eine Genauigkeit, die hier niemand hat.
BEILAEUFIG, ANSEHEN, NACHARBEIT = 1, 2, 3


@dataclass(frozen=True)
class Hinweis:
    """Ein Grund, bei diesem Entwurf genauer hinzusehen."""

    art: str
    text: str
    gewicht: int = ANSEHEN

    def as_dict(self) -> dict:
        return {"art": self.art, "text": self.text, "gewicht": self.gewicht}


def erfuellung_behauptet(*, score: int | float | None = None,
                         wiba_status: str = "",
                         risiko_label: str = "") -> bool | None:
    """Behauptet dieser Entwurf, dass etwas erfüllt / in Ordnung ist?

    Die Frage ist über die Module hinweg dieselbe, die **Antwort** steht in drei
    verschiedenen Wertetypen (Score 0–5 · BSI-Antwortmodell · Risikostufe).
    Deshalb hier **eine** Stelle: Stünde die Schwelle in jedem Adapter, wäre sie
    die nächste Spiegel-Liste.

    ``None`` heißt „nicht entscheidbar“ und ist keine Behauptung — ein
    unbewertetes Objekt soll keinen Hinweis erzeugen.
    """
    if score is not None:
        try:
            return float(score) >= ERFUELLUNG_AB
        except (TypeError, ValueError):
            return None
    status = (wiba_status or "").strip().lower()
    if status:
        # `nicht_relevant` behauptet keine Erfüllung, sondern Nicht-Betroffenheit
        # — fachlich eine andere Aussage, und sie braucht ihren eigenen Beleg
        # (deshalb hier bewusst wie „ja“ behandelt: beides ist eine Aussage über
        # das Produkt, die ohne Nachweis nicht belegt ist).
        if status in ("ja", "nicht_relevant"):
            return True
        if status in ("nein",):
            return False
        return None
    label = (risiko_label or "").strip().lower()
    if label:
        # Ein als niedrig bewertetes Risiko ist die Entsprechung zu „erfüllt“:
        # Es behauptet, dass hier nichts zu tun ist.
        if label in ("niedrig", "gering", "low"):
            return True
        return False
    return None


def hinweise(
    *,
    nachweise_im_prompt: Sequence[str] | None = None,
    genutzte_nachweise: Sequence[str] = (),
    behauptet_erfuellung: bool | None = None,
    einig: bool | None = None,
    abgeschnitten: bool = False,
    nicht_abbildbar: Sequence[str] = (),
    veralteter_nachweis: str = "",
) -> list[Hinweis]:
    """Die Prüfhinweise zu **einem** Entwurf.

    Args:
      nachweise_im_prompt: ``sources`` aus ``evidence_block_for`` (#1485) —
        was dem Modell an Belegen vorlag. **Drei Zustände, und der Unterschied
        ist wichtig:** ``None`` heißt „dieser Weg kennt keine Nachweise“ (z. B.
        OWASP-Kontrollen) und erzeugt **keinen** Beleg-Hinweis; ``[]`` heißt
        „gesucht und nichts gefunden“ und erzeugt ihn. Ohne diese Unterscheidung
        würde der Hinweis in den Modulen ohne Nachweis-Mechanismus bei **jeder**
        positiven Bewertung feuern — und ein Hinweis, der immer erscheint, ist
        keiner (#1774).
      genutzte_nachweise: was es laut eigener Antwort angerechnet hat (#1485).
      behauptet_erfuellung: Ergebnis von :func:`erfuellung_behauptet`.
      einig: ob mehrere Läufe zum selben Wert kamen (#1863); ``None`` = es gab
        nur einen Lauf, das ist kein Befund.
      abgeschnitten: ``KiErgebnis.abgeschnitten`` (#1588).
      nicht_abbildbar: ``KiErgebnis.nicht_abbildbar`` (#1841/E3).
      veralteter_nachweis: Freitext, falls der Beleg älter ist als der
        bewertete Stand (Muster aus #1824); leer = kein Befund.

    Reihenfolge: schwerste zuerst. Der Mensch liest von oben.
    """
    #: ``None`` = der Weg kennt keine Nachweise → beide Beleg-Hinweise entfallen.
    nachweise_gesucht = nachweise_im_prompt is not None
    vorlagen = [r for r in (nachweise_im_prompt or []) if r]
    genutzt = [r for r in (genutzte_nachweise or []) if r]
    out: list[Hinweis] = []

    # 1) Der wertvollste Hinweis des ganzen Katalogs: Erfüllung behauptet, und
    #    nichts in der Akte stützt sie. Genau diese Entwürfe gehen sonst
    #    unbemerkt in einen Nachweis, der einem Prüfer vorgelegt wird.
    if not nachweise_gesucht:
        pass
    elif behauptet_erfuellung and not vorlagen:
        out.append(Hinweis(
            "erfuellung_ohne_beleg",
            "Der Entwurf geht von Erfüllung aus, es lag aber kein Nachweis aus "
            "der Akte vor.",
            NACHARBEIT))
    elif behauptet_erfuellung and not genutzt:
        # Belege waren da und wurden nicht angerechnet. Das ist schwächer als
        # oben (das Modell *kann* sie für unpassend gehalten haben), aber es
        # heißt: Die Bewertung steht auf dem Katalogtext, nicht auf der Akte.
        out.append(Hinweis(
            "beleg_nicht_angerechnet",
            f"{len(vorlagen)} Nachweis(e) lagen vor, der Entwurf nennt keinen "
            "davon als Grundlage.",
            ANSEHEN))

    # 2) Zwei Läufe, zwei Ergebnisse (#1863). Bewusst kein Mehrheitsentscheid —
    #    die Abweichung ist das Signal für den Menschen, nicht der Anlass für
    #    eine dritte Meinung der Maschine.
    if einig is False:
        out.append(Hinweis(
            "streuung",
            "Zwei Läufe kamen zu verschiedenen Ergebnissen — die Bewertung ist "
            "an dieser Stelle nicht stabil.",
            NACHARBEIT))

    # 3) Technische Einschränkungen des Laufs. Sie sagen nichts über die
    #    Fachlichkeit, aber alles über die Verlässlichkeit der Antwort.
    if abgeschnitten:
        out.append(Hinweis(
            "abgeschnitten",
            "Die Antwort wurde am Ausgabelimit abgeschnitten und ist "
            "unvollständig.",
            NACHARBEIT))
    for p in nicht_abbildbar or []:
        out.append(Hinweis(
            "nicht_abbildbar",
            f"Der gewählte KI-Anbieter konnte „{p}“ nicht umsetzen; die "
            "Antwortform hing allein am Prompt.",
            BEILAEUFIG))

    if veralteter_nachweis:
        out.append(Hinweis("nachweis_veraltet", veralteter_nachweis, ANSEHEN))

    return out


def als_liste(hs: Sequence[Hinweis]) -> list[dict]:
    """Für die JSON-Antwort der Endpunkte (additives Feld ``pruefhinweise``)."""
    return [h.as_dict() for h in hs or []]


def schwerstes_gewicht(hs: Sequence[Hinweis]) -> int:
    """0, wenn es keinen Hinweis gibt — die Arbeitsliste sortiert danach."""
    return max((h.gewicht for h in hs or []), default=0)


__all__ = [
    "ANSEHEN",
    "BEILAEUFIG",
    "ERFUELLUNG_AB",
    "Hinweis",
    "NACHARBEIT",
    "als_liste",
    "erfuellung_behauptet",
    "hinweise",
    "schwerstes_gewicht",
]
