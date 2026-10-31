"""Kataloge und gerechnete Hinweise für das VVT (Art. 30) — #1890.

WAS HIER ZUTRIFFT UND WAS NICHT
-------------------------------
Das Issue #1890 behauptete, die Rechtsgrundlagen seien Freitext. **Das war zu
scharf:** ``DSGVOPflichtDokuPanel.vue`` zeigt für Art. 6 Abs. 1 und Art. 9
Abs. 2 längst Auswahlfelder. Richtig bleibt dreierlei, und das ist der
Gegenstand dieser Datei:

1. **Die Auswahl für Art. 9 Abs. 2 ist unvollständig.** Sie führte a, b, c, g,
   h, i, j — **d, e und f fehlten**. Eine Verarbeitung auf Grundlage von
   Art. 9 Abs. 2 lit. e (vom Betroffenen offensichtlich öffentlich gemachte
   Daten) ließ sich nicht erfassen; der Anwender musste eine falsche
   Grundlage wählen oder das Feld leer lassen. Eine unvollständige
   Positivliste ist schlimmer als ein Freitextfeld: Sie sieht abschließend
   aus.
2. **Die Liste stand im Frontend.** Damit war sie eine Spiegel-Liste
   (#1731/#1735) — gepflegt wird eine, und Berichte, Prüfungen und Masken
   lesen verschiedene Stände. Sie liegt jetzt hier, und die Maske holt sie.
3. **``tom_ref`` und ``loeschfrist_ref`` sind wirklich Freitext**
   (Platzhalter „z.B. TOM-003, TOM-011"), obwohl die Suite beide Register
   führt (``dsgvo_tom_katalog`` #1103, ``dsgvo_loeschkonzept`` #1110).
   Getippt verwaist der Verweis beim Umbenennen, und niemand merkt es.
4. **``dsfa_trigger`` ist ein Häkchen**, obwohl Art. 35 Abs. 3 die drei Fälle
   nennt und die Eingaben dafür in derselben Zeile stehen.

DIE GRENZE
----------
Diese Datei **rechnet Hinweise, keine Entscheidungen**. Ob eine DSFA
erforderlich ist, beurteilt die oder der Datenschutzbeauftragte — Art. 35
Abs. 3 nennt Regelbeispiele („insbesondere"), keine Tatbestandsautomatik. Ein
gerechneter Vorschlag überschreibt deshalb **nie** eine getroffene
Entscheidung (#1769/#1773).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from shared import formular_pruefung as fp

DB_PATH = Path("data/db/dsgvo.sqlite")

#: Art. 6 Abs. 1 — die Rechtsgrundlagen der Verarbeitung, **abschließend**.
#: Der Schlüssel ist der Buchstabe; der angezeigte Wert bleibt die gewohnte
#: Schreibweise, damit Bestandsdaten lesbar bleiben (die Linie aus #1713:
#: Bestand nicht anfassen, wenn es nicht nötig ist).
ART6: tuple[dict[str, str], ...] = (
    {"lit": "a", "wert": "Art. 6(1)(a)", "label": "Einwilligung"},
    {"lit": "b", "wert": "Art. 6(1)(b)", "label": "Vertrag oder Vertragsanbahnung"},
    {"lit": "c", "wert": "Art. 6(1)(c)", "label": "Rechtliche Verpflichtung"},
    {"lit": "d", "wert": "Art. 6(1)(d)", "label": "Lebenswichtige Interessen"},
    {"lit": "e", "wert": "Art. 6(1)(e)", "label": "Öffentliches Interesse / öffentliche Gewalt"},
    {"lit": "f", "wert": "Art. 6(1)(f)", "label": "Berechtigte Interessen"},
)

#: Art. 9 Abs. 2 — die Ausnahmen für besondere Kategorien, **vollständig**.
#: d, e und f fehlten in der Maske; siehe Punkt 1 im Modul-Docstring.
ART9: tuple[dict[str, str], ...] = (
    {"lit": "a", "wert": "Art. 9(2)(a)", "label": "Ausdrückliche Einwilligung"},
    {"lit": "b", "wert": "Art. 9(2)(b)", "label": "Arbeits-, Sozial- und Sozialschutzrecht"},
    {"lit": "c", "wert": "Art. 9(2)(c)", "label": "Lebenswichtige Interessen"},
    {"lit": "d", "wert": "Art. 9(2)(d)",
     "label": "Verarbeitung durch Stiftung, Vereinigung oder sonstige "
              "Einrichtung ohne Gewinnerzielungsabsicht"},
    {"lit": "e", "wert": "Art. 9(2)(e)",
     "label": "Von der betroffenen Person offensichtlich öffentlich gemacht"},
    {"lit": "f", "wert": "Art. 9(2)(f)",
     "label": "Geltendmachung, Ausübung oder Verteidigung von Rechtsansprüchen"},
    {"lit": "g", "wert": "Art. 9(2)(g)", "label": "Erhebliches öffentliches Interesse"},
    {"lit": "h", "wert": "Art. 9(2)(h)", "label": "Gesundheitsvorsorge, Arbeitsmedizin"},
    {"lit": "i", "wert": "Art. 9(2)(i)", "label": "Öffentliche Gesundheit"},
    {"lit": "j", "wert": "Art. 9(2)(j)",
     "label": "Archiv-, Forschungs- und Statistikzwecke"},
)

#: Ab welcher Zahl Betroffener eine Verarbeitung „umfangreich" im Sinne des
#: Art. 35 Abs. 3 lit. b sein **kann**. Die Verordnung nennt keine Zahl; diese
#: ist unsere Auslegung und wirkt deshalb nur als Hinweis — wie die 18 Monate
#: in #1824. Sie steht hier und nicht in der Maske, damit sie eine Stelle hat.
UMFANGREICH_AB = 500

#: Wortfelder für die Regelbeispiele des Art. 35 Abs. 3. Sie **begründen einen
#: Hinweis**, sie entscheiden nicht: Eine Wortliste ist keine Rechtsanwendung.
PROFILING_WOERTER: tuple[str, ...] = (
    "profiling", "profil", "scoring", "score", "bewertung persönlicher",
    "automatisierte entscheid", "bonität", "kreditwürdig", "prognose",
)
UEBERWACHUNG_WOERTER: tuple[str, ...] = (
    "überwachung", "videoüberwach", "kamera", "ortung", "tracking",
    "standortdaten", "öffentlich zugänglich",
)


def _s(wert: Any) -> str:
    return "" if wert is None else str(wert).strip()


def katalog() -> dict[str, Any]:
    """Die Kataloge für die Maske — **eine** Quelle (#1731/#1735)."""
    return {
        "art6": [dict(e) for e in ART6],
        "art9": [dict(e) for e in ART9],
        "art9_hinweis": (
            "Nur bei besonderen Kategorien nach Art. 9 Abs. 1 (Gesundheit, "
            "Religion, Biometrie, Gewerkschaft, politische Meinung, "
            "Sexualleben, ethnische Herkunft, genetische Daten)."),
        "umfangreich_ab": UMFANGREICH_AB,
    }


# ── Verweise auf die eigenen Register ───────────────────────────────────────

def referenz_optionen(db_path: Path | str = DB_PATH,
                      projekt_name: str = "") -> dict[str, Any]:
    """Was für ``tom_ref`` und ``loeschfrist_ref`` zur Auswahl steht.

    Beide zeigen auf Register, die die Suite selbst führt. Getippt verwaist der
    Verweis beim Umbenennen — und ein verwaister Verweis in einem VVT sieht aus
    wie eine Zuordnung.

    Best effort je Register: Ein leeres oder nicht angelegtes Register darf die
    VVT-Maske nicht lahmlegen; dann bleibt das Feld Freitext wie bisher.
    """
    db_path = Path(db_path)
    tom: list[dict[str, str]] = []
    loesch: list[dict[str, str]] = []
    try:
        from dsgvo import tom_katalog as tk

        for m in tk.list_massnahmen(db_path, projekt_name) or []:
            key = _s(m.get("massnahme_key")) or _s(m.get("key"))
            if key:
                tom.append({"wert": key,
                            "label": _s(m.get("titel")) or _s(m.get("massnahme"))
                            or key})
    except Exception:  # noqa: BLE001 — Register leer oder nicht angelegt
        tom = []
    try:
        from dsgvo import loeschkonzept_db as lk

        for r in lk.list_regeln(db_path, projekt_name) or []:
            key = _s(r.get("regel_id")) or _s(r.get("id"))
            if key:
                loesch.append({"wert": key,
                               "label": _s(r.get("datenart"))
                               or _s(r.get("bezeichnung")) or key})
    except Exception:  # noqa: BLE001
        loesch = []
    return {"tom": tom, "loeschkonzept": loesch}


def verweis_befunde(eintrag: dict[str, Any], optionen: dict[str, Any]
                    ) -> list[dict[str, Any]]:
    """Verweise, die auf nichts zeigen.

    Geprüft wird nur, **wenn das Register etwas enthält**: Bei leerem Register
    wäre jeder Verweis „verwaist", und ein Prüfer, der immer anschlägt, wird
    abgeschaltet (#1774/#1877).
    """
    out: list[dict[str, Any]] = []
    for feld, schluessel, name in (("tom_ref", "tom", "TOM-Katalog"),
                                   ("loeschfrist_ref", "loeschkonzept",
                                    "Löschkonzept")):
        bekannt = {_s(o.get("wert")) for o in (optionen.get(schluessel) or [])}
        if not bekannt:
            continue
        genannt = [t.strip() for t in _s(eintrag.get(feld)).replace(";", ",")
                   .split(",") if t.strip()]
        unbekannt = [t for t in genannt if t not in bekannt]
        if unbekannt:
            out.append(fp.befund(
                "verweis_unbekannt", feld=feld, nr=30, art="widerspruch",
                wirkung=fp.WIRKUNG_HINWEIS,
                text=f"Der Verweis „{', '.join(unbekannt)}“ steht nicht im "
                     f"{name}.",
                hinweis="Ein Verweis, der auf nichts zeigt, sieht aus wie eine "
                        "Zuordnung. Wähle den Eintrag aus dem Register."))
    return out


# ── Art. 35 Abs. 3 — der gerechnete Hinweis ─────────────────────────────────

def dsfa_befund(eintrag: dict[str, Any]) -> dict[str, Any]:
    """Spricht etwas für eine DSFA-Pflicht nach Art. 35 Abs. 3?

    Liefert ``{indiz, faelle, gruende, vorschlag, erfasst, widerspruch}``.
    Die drei Regelbeispiele:

    * **lit. a** — systematische umfassende Bewertung persönlicher Aspekte auf
      automatisierter Grundlage, einschließlich Profiling.
    * **lit. b** — umfangreiche Verarbeitung besonderer Kategorien (Art. 9
      Abs. 1) oder von Daten über strafrechtliche Verurteilungen (Art. 10).
    * **lit. c** — systematische umfangreiche Überwachung öffentlich
      zugänglicher Bereiche.

    **Es ist ein Indiz, keine Feststellung.** Art. 35 Abs. 3 sagt
    „insbesondere"; die Liste der Aufsichtsbehörden (Art. 35 Abs. 4) kennt
    weitere Fälle, und die Beurteilung liegt bei der oder dem
    Datenschutzbeauftragten.
    """
    eintrag = dict(eintrag or {})
    text = " ".join((_s(eintrag.get("zweck")), _s(eintrag.get("name")),
                     _s(eintrag.get("datenfluss")),
                     _s(eintrag.get("beschreibung")))).lower()
    anzahl = int(eintrag.get("betroffene_anzahl") or 0)
    art9 = bool(_s(eintrag.get("art9_grundlage")))

    faelle: list[str] = []
    gruende: list[str] = []

    treffer_profil = sorted({w for w in PROFILING_WOERTER if w in text})
    if treffer_profil:
        faelle.append("a")
        gruende.append(
            "Art. 35 Abs. 3 lit. a — der Zweck deutet auf eine systematische "
            f"Bewertung persönlicher Aspekte hin ({', '.join(treffer_profil)})")
    if art9:
        faelle.append("b")
        gruende.append(
            "Art. 35 Abs. 3 lit. b — es werden besondere Kategorien nach "
            f"Art. 9 verarbeitet (Grundlage {_s(eintrag.get('art9_grundlage'))})"
            + (f"; erfasste Betroffene: {anzahl}" if anzahl else
               "; ob die Verarbeitung „umfangreich“ ist, ist nicht erfasst"))
    treffer_ueberw = sorted({w for w in UEBERWACHUNG_WOERTER if w in text})
    if treffer_ueberw:
        faelle.append("c")
        gruende.append(
            "Art. 35 Abs. 3 lit. c — der Zweck deutet auf eine systematische "
            "Überwachung öffentlich zugänglicher Bereiche hin "
            f"({', '.join(treffer_ueberw)})")

    indiz = bool(faelle)
    erfasst = bool(int(eintrag.get("dsfa_trigger") or 0))
    widerspruch: list[dict[str, Any]] = []
    if indiz and not erfasst:
        widerspruch.append(fp.befund(
            "dsfa_indiz_nicht_vermerkt", feld="dsfa_trigger", nr=35,
            art="widerspruch", wirkung=fp.WIRKUNG_HINWEIS,
            text="Die erfassten Angaben sprechen für eine DSFA-Pflicht; der "
                 "Haken ist nicht gesetzt.",
            hinweis="; ".join(gruende) + ". Die Beurteilung liegt bei der "
                    "Datenschutzbeauftragten oder dem Datenschutzbeauftragten "
                    "— Art. 35 Abs. 3 nennt Regelbeispiele."))
    # Die Gegenrichtung ist **kein** Widerspruch: Wer eine DSFA durchführt,
    # obwohl kein Regelbeispiel greift, tut nichts Falsches. Sie zu
    # beanstanden hieße, von einer DSFA abzuraten.

    return {
        "indiz": indiz,
        "faelle": faelle,
        "gruende": gruende,
        "erfasst": erfasst,
        "umfangreich_ab": UMFANGREICH_AB,
        # Nur setzen, nie zurücknehmen (#1769/#1773).
        "vorschlag": {"dsfa_trigger": 1} if indiz else {},
        "widerspruch": widerspruch,
    }


def enrich_vvt(eintrag: dict[str, Any],
               optionen: dict[str, Any] | None = None) -> dict[str, Any]:
    """Reichert einen VVT-Eintrag um ``dsfa`` und ``befunde`` an.

    Dieselbe Bauform wie ``datenpannen_frist.enrich_panne`` und
    ``meldepflicht.enrich_panne`` — damit die Anreicherungen nebeneinander
    laufen können, ohne sich zu kennen.
    """
    d = dict(eintrag)
    d["dsfa"] = dsfa_befund(d)
    befunde = list(d["dsfa"].get("widerspruch") or [])
    if optionen:
        befunde += verweis_befunde(d, optionen)
    d["befunde"] = befunde
    return d


__all__ = ["ART6", "ART9", "UMFANGREICH_AB", "PROFILING_WOERTER",
           "UEBERWACHUNG_WOERTER", "katalog", "referenz_optionen",
           "verweis_befunde", "dsfa_befund", "enrich_vvt"]
