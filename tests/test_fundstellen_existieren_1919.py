"""Jede zitierte Stelle der Verordnung muss es geben (#1919).

**Warum dieser Test und nicht nur eine Tabelle.** #1913 hat die 32 Fundstellen
des Anforderungskatalogs gegen den amtlichen Text gesetzt und mit einer
geprüften Tabelle festgenagelt. Danach fanden sich **zwei weitere Blöcke**, die
diese Tabelle nicht erfasst:

* ``cra/annex_vii.py`` nannte für Testberichte „Anhang VII (4)", während
  ``cra/sicherheitstests.py`` für denselben Sachverhalt korrekt „Anhang VII
  Nr. 6" zitierte — zwei Stellen, zwei Nummern, dieselbe Sache.
* ``cra/owasp_proactive_controls.py`` zitierte zehnmal „Anhang I **Part** I
  Nr. 3" bis „Nr. 7". Anhang I Teil I hat **Nr. 1 und Nr. 2**, und Nr. 2 ist in
  Buchstaben gegliedert. Die Nummern 3 bis 7 gibt es dort nicht. Gedruckt wurde
  das in der CRA-Oberfläche an jeder OWASP-Kontrolle.

Eine Tabelle je Katalog wäre die dritte Spiegel-Liste gewesen (#1731/#1735).
Dieser Test prüft stattdessen die **Struktur**: Zitiert eine Stelle eine Nummer,
muss es diese Nummer im Verordnungstext geben. Das fängt die erfundene Nummer
unabhängig davon, in welcher Datei sie steht — auch in einer, die es heute noch
nicht gibt.

**Die Grenzen sind gemessen, nicht geschätzt** — am 2. November 2026 aus
``data/cra_resources/32024R2847_DEU.pdf`` (ABl. L vom 20.11.2024) ausgezählt.
Der Test kann nicht prüfen, ob die Verordnung geändert wurde; dafür steht die
jährliche Durchsicht in ``docs/cra/produktklassifizierung.md``. Was er
verhindert, ist die erfundene Fundstelle — und die ist in einer Nachweisakte
schlimmer als eine fehlende, weil sie sich wie eine Feststellung liest.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent

#: Zitat-Vorsilbe -> zulässige Nummern. Gemessen am amtlichen Text.
GLIEDERUNG: dict[str, set[int]] = {
    # Anhang I Teil I: Nr. 1 (risikobasierte Konzeption) und Nr. 2 (Buchstaben)
    "Anhang I Teil I Nr.": {1, 2},
    # Anhang I Teil II: Nr. 1 bis 8 (Behandlung von Schwachstellen)
    "Anhang I Teil II Nr.": set(range(1, 9)),
    # Anhang II: Nr. 1 bis 9 (Informationen und Anleitungen für den Nutzer)
    "Anhang II Nr.": set(range(1, 10)),
    # Anhang V: Nr. 1 bis 8 (EU-Konformitätserklärung)
    "Anhang V Nr.": set(range(1, 9)),
    # Anhang VII: Nr. 1 bis 8 (Inhalt der technischen Dokumentation)
    "Anhang VII Nr.": set(range(1, 9)),
    # Art. 13 (Pflichten der Hersteller): Abs. 1 bis 25
    "Art. 13 Abs.": set(range(1, 26)),
    # Art. 14 (Meldepflichten): Abs. 1 bis 10
    "Art. 14 Abs.": set(range(1, 11)),
    # Art. 3 (Begriffsbestimmungen): Nr. 1 bis 51
    "Art. 3 Nr.": set(range(1, 52)),
}

#: Anhang I Teil I Nr. 2 ist in die Buchstaben a bis m gegliedert.
#: Der deutsche Text überspringt keinen Buchstaben.
TEIL_I_BUCHSTABEN = set("abcdefghijklm")

#: Wo nach Zitaten gesucht wird. Die Modul-Dokumentation gehört dazu: Das
#: CRA-Dossier zitiert die Verordnung, und es ist öffentlich.
QUELLEN = ("cra/*.py", "docs/cra/*.md")

#: Eine Zahlenaufzählung hinter der Vorsilbe: „4", „2 und 8", „3, 4 und 5",
#: „1–4", „9 und 13".
_ZAHLEN = r"\d+(?:\s*(?:–|-|,|und|bis)\s*\d+)*"


def _dateien() -> list[Path]:
    aus: list[Path] = []
    for muster in QUELLEN:
        aus.extend(sorted(WURZEL.glob(muster)))
    assert aus, "keine Quellen gefunden — Pfade geprüft?"
    return aus


def _zahlen(text: str) -> list[int]:
    """Alle Zahlen einer Aufzählung, Bereiche ausgeschrieben."""
    aus: list[int] = []
    teile = re.split(r"\s*(?:,|und|bis)\s*", text)
    for teil in teile:
        grenzen = [int(x) for x in re.findall(r"\d+", teil)]
        if len(grenzen) == 2 and re.search(r"–|-", teil):
            aus.extend(range(min(grenzen), max(grenzen) + 1))
        else:
            aus.extend(grenzen)
    return aus


@pytest.mark.parametrize("vorsilbe", sorted(GLIEDERUNG))
def test_zitierte_nummern_gibt_es(vorsilbe: str):
    erlaubt = GLIEDERUNG[vorsilbe]
    muster = re.compile(re.escape(vorsilbe) + r"\s*(" + _ZAHLEN + r")")
    treffer: list[str] = []
    for datei in _dateien():
        text = datei.read_text(encoding="utf-8")
        for m in muster.finditer(text):
            for n in _zahlen(m.group(1)):
                if n not in erlaubt:
                    zeile = text[:m.start()].count("\n") + 1
                    treffer.append(
                        f"{datei.relative_to(WURZEL)}:{zeile} — "
                        f"„{vorsilbe} {m.group(1)}“ (Nr./Abs. {n} gibt es nicht; "
                        f"zulässig: {min(erlaubt)}–{max(erlaubt)})")
    assert not treffer, (
        "Zitat auf eine Stelle, die die Verordnung nicht hat:\n  "
        + "\n  ".join(treffer))


def test_buchstaben_von_anhang_i_teil_i_nr_2_gibt_es():
    """Die Buchstaben sind der Fall, der #1913 ausgelöst hat.

    Sieben Anforderungen trugen einen Buchstaben, der einen anderen Inhalt
    bezeichnet als den, den sie beschreiben — die Vertraulichkeit stand auf
    ``Buchst. c``, dort steht die Updatefähigkeit. **Dieser Test kann das nicht
    finden**: Er prüft nur, dass der Buchstabe existiert. Die inhaltliche
    Zuordnung hält ``test_fundstellen_cra_1913`` mit dem Belegsatz fest.
    """
    muster = re.compile(r"Anhang I Teil I Nr\. 2 Buchst\.\s*([a-z])(?:\s+und\s+([a-z]))?")
    treffer: list[str] = []
    for datei in _dateien():
        text = datei.read_text(encoding="utf-8")
        for m in muster.finditer(text):
            for b in (m.group(1), m.group(2)):
                if b and b not in TEIL_I_BUCHSTABEN:
                    zeile = text[:m.start()].count("\n") + 1
                    treffer.append(f"{datei.relative_to(WURZEL)}:{zeile} — Buchst. {b}")
    assert not treffer, (
        "Buchstabe, den Anhang I Teil I Nr. 2 nicht hat (zulässig a–m):\n  "
        + "\n  ".join(treffer))


def test_keine_englische_gliederung_in_zitaten():
    """„Anhang I Part I" und „Annex I, Part II" sind nicht zitierfähig.

    Der OWASP-Katalog trug zehnmal „Anhang I **Part** I" — eine Mischung, die
    in einem Dokument für eine deutsche Marktüberwachungsbehörde nichts zu
    suchen hat. Geprüft wird der **kommentarfreie** Text: In Kommentaren und
    Docstrings darf der alte Zustand zitiert werden, sonst wird der Wächter
    rot, weil jemand ihn erklärt (die Lehre aus #1834/#1867/#1878).
    """
    schlecht = re.compile(r"\bAnhang [IV]+,? Part\b|\bAnnex [IV]+,? Part\b")
    treffer: list[str] = []
    for datei in _dateien():
        if datei.suffix != ".py":
            continue
        for nr, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1):
            ohne_kommentar = zeile.split("#", 1)[0]
            if schlecht.search(ohne_kommentar):
                treffer.append(f"{datei.relative_to(WURZEL)}:{nr} — {zeile.strip()[:80]}")
    assert not treffer, "Englische Gliederung im Zitat:\n  " + "\n  ".join(treffer)


def test_der_fall_der_ihn_ausgeloest_hat_wird_gefunden():
    """Der Wächter muss rot werden können — hier ist der Nachweis.

    Nachgebaut wird der echte alte Stand des OWASP-Katalogs. Ein Wächter, von
    dem niemand gesehen hat, wie er anschlägt, ist eine Behauptung.
    """
    muster = re.compile(re.escape("Anhang I Teil I Nr.") + r"\s*(" + _ZAHLEN + r")")
    alt = '"cra_articles": ["Anhang I Teil I Nr. 7", "Art. 13 Abs. 3"],'
    gefunden = [n for m in muster.finditer(alt) for n in _zahlen(m.group(1))
                if n not in GLIEDERUNG["Anhang I Teil I Nr."]]
    assert gefunden == [7], gefunden


#: Anhang VII Punkt -> (Fundstelle, Belegsatz). Wie die Tabelle in
#: ``test_fundstellen_cra_1913``: Der Belegsatz macht die Zuordnung ohne das
#: PDF nachvollziehbar, und wer ihn mitändern muss, hat nachgelesen.
GEPRUEFT_ANHANG_VII: dict[str, tuple[str, str]] = {
    "beschreibung": ("Anhang VII Nr. 1",
                     "eine allgemeine Beschreibung des Produkts mit digitalen "
                     "Elementen, einschließlich …"),
    "design_entwicklung": ("Anhang VII Nr. 2 Buchst. a",
                           "erforderlicher Informationen über die Konzeption und "
                           "Entwicklung …, Beschreibung der Systemarchitektur"),
    "schwachstellenbehandlung": ("Anhang VII Nr. 2 Buchst. b",
                                 "Verfahren zur Behandlung von Schwachstellen, "
                                 "einschließlich der Software-Stückliste, des "
                                 "Konzepts für die koordinierte Offenlegung …"),
    "essentielle_anforderungen": ("Anhang VII Nr. 3; Anhang I Teil I",
                                  "einschließlich der Frage, inwieweit die "
                                  "grundlegenden Cybersicherheitsanforderungen "
                                  "gemäß Anhang I Teil I Anwendung finden"),
    "risikobewertung": ("Anhang VII Nr. 3",
                        "eine Bewertung der Cybersicherheitsrisiken, die bei der "
                        "Konzeption … nach Artikel 13 berücksichtigt werden"),
    "support_zeitraum": ("Anhang VII Nr. 4; Art. 13 Abs. 8",
                         "einschlägige Informationen, die bei der Festlegung des "
                         "Unterstützungszeitraums … berücksichtigt wurden"),
    "normen": ("Anhang VII Nr. 5",
               "eine Aufstellung der vollständig oder teilweise angewandten "
               "harmonisierten Normen …"),
    "testberichte": ("Anhang VII Nr. 6",
                     "Berichte über die Tests und Prüfungen, die durchgeführt "
                     "wurden, um die Konformität … zu überprüfen"),
    "konformitaetserklaerung_ref": ("Anhang VII Nr. 7",
                                    "ein Exemplar der EU-Konformitätserklärung"),
    "sbom": ("Anhang VII Nr. 8; Anhang I Teil II Nr. 1",
             "gegebenenfalls auf begründetes Verlangen der "
             "Marktüberwachungsbehörde die Software-Stückliste"),
    "anleitung": ("Anhang VII Nr. 1 Buchst. d; Anhang II",
                  "Informationen und Anleitungen für die Nutzer gemäß Anhang II"),
}


def test_anhang_vii_fundstellen_entsprechen_dem_amtlichen_text():
    """Der zweite Block aus #1919 — und der auffälligste Widerspruch darin.

    ``annex_vii.py`` nannte für Testberichte „Anhang VII (4)", während
    ``sicherheitstests.py`` dieselbe Sache als „Anhang VII Nr. 6" zitierte.
    Richtig ist Nr. 6; Nr. 4 ist der Unterstützungszeitraum. Zwei Stellen mit
    zwei Nummern für denselben Sachverhalt sind die Fehlerklasse aus
    #1731/#1735 — nur dass sie hier in ein Dokument geht, das eine Behörde
    liest.
    """
    from cra.annex_vii import PUNKTE

    ist = {p.key: p.rechtsbezug for p in PUNKTE}
    assert set(ist) == set(GEPRUEFT_ANHANG_VII), (
        "Punkt ohne geprüfte Fundstelle: "
        f"{sorted(set(ist) ^ set(GEPRUEFT_ANHANG_VII))}")
    for key, (erwartet, beleg) in GEPRUEFT_ANHANG_VII.items():
        assert ist[key] == erwartet, (
            f"{key}: Fundstelle ist {ist[key]!r}, geprüft ist {erwartet!r}.\n"
            f"Belegsatz: „{beleg}“")


def test_sbom_ist_nur_auf_verlangen_pflichtinhalt():
    """Anhang VII Nr. 8 sagt „gegebenenfalls auf begründetes Verlangen".

    Die Stückliste ist damit kein unbedingter Inhalt der technischen
    Dokumentation — anders als die zehn übrigen Punkte. ``pflicht=False`` ist
    hier also die richtige Aussage und kein Versehen; wer sie auf ``True``
    stellt, erfindet eine Pflicht.

    Dass die Stückliste **ohnehin** geführt wird (Anhang I Teil II Nr. 1),
    ändert daran nichts: Das ist eine Pflicht des Verfahrens, nicht ein
    Inhalt dieses Dokuments.
    """
    from cra.annex_vii import PUNKTE

    nach_key = {p.key: p for p in PUNKTE}
    assert nach_key["sbom"].pflicht is False
    for key in ("beschreibung", "testberichte", "konformitaetserklaerung_ref",
                "anleitung"):
        assert nach_key[key].pflicht is True, key


def test_die_produktklassen_haben_eine_quelle():
    """Der schwerste Fund von #1919 — ein stilles Fail-Open.

    Es gab **zwei** Schlüsselsätze für die Produktklasse:

    * ``cra/requirements.py`` kannte ``default``, ``important_i``,
      ``important_ii`` und ``critical``.
    * ``server/api/cra`` ließ zusätzlich ``critical_i`` und ``critical_ii``
      zu, ``server/api/firmen`` ließ **nur** diese beiden zu und kannte
      ``critical`` überhaupt nicht — und das Auswahlfeld der Oberfläche bot
      für kritische Produkte **ausschließlich** die beiden an.

    Beide gibt es in der Verordnung nicht: **Anhang IV ist nicht in Klassen
    gegliedert.** Er ist eine Liste von drei Positionen (Hardwaregeräte mit
    Sicherheitsboxen, Smart-Meter-Gateways, Chipkarten) — anders als
    Anhang III mit „Klasse I" und „Klasse II".

    Die Folge war die schlimmste Form eines stillen Fehlers: Ein als
    ``critical_i`` erfasstes Produkt fiel in ``_klassen_regel`` auf die
    ``default``-Zeile. Der Konformitätsnachweis nannte es „Standardprodukt",
    und ``weg_zulaessig('critical_i', 'A')`` ergab **True** — die
    Selbstbewertung nach Modul A galt als zulässig, obwohl die Verordnung für
    kritische Produkte eine Zertifizierung verlangt. Nichts schlug fehl.
    """
    from cra.requirements import (
        KLASSEN_BEWERTUNGSWEGE,
        LEGACY_PRODUKTKLASSEN,
        PRODUKTKLASSEN,
        normalisiere_klasse,
        weg_zulaessig,
    )

    # Eine Quelle: jede Klasse der Matrix steht im Katalog und umgekehrt.
    assert set(PRODUKTKLASSEN) == set(KLASSEN_BEWERTUNGSWEGE), (
        set(PRODUKTKLASSEN) ^ set(KLASSEN_BEWERTUNGSWEGE))

    # Die Alt-Schlüssel bilden auf eine bekannte Klasse ab …
    for alt, ziel in LEGACY_PRODUKTKLASSEN.items():
        assert ziel in PRODUKTKLASSEN, (alt, ziel)
        assert normalisiere_klasse(alt) == ziel

    # … und der eigentliche Schaden ist weg: Modul A ist für ein kritisches
    # Produkt unzulässig, auch wenn es unter dem Alt-Schlüssel gespeichert ist.
    for k in ("critical", *LEGACY_PRODUKTKLASSEN):
        assert weg_zulaessig(k, "A") is False, (
            f"Modul A gilt für {k!r} als zulässig — das ist der Fail-Open aus "
            "#1919. Für kritische Produkte verlangt Art. 32 eine "
            "Zertifizierung; die Selbstbewertung genügt nicht.")


def test_die_rest_schichten_pruefen_gegen_den_katalog():
    """Keine Literal-Liste von Klassen neben dem Katalog.

    Vier Stellen führten je ihre eigene: der Katalog, die CRA-API, die
    Firmen-API und zwei Auswahlfelder. Sie waren auseinandergelaufen, und die
    Firmen-API ließ die **richtige** Klasse nicht zu. Das ist die
    Spiegel-Listen-Fehlerklasse aus #1731/#1735 — hier mit einer
    Konformitätsaussage am Ende.
    """
    quellen = {
        "server/api/cra/__init__.py": "cra-api",
        "server/api/firmen.py": "firmen-api",
        "frontend/src/views/cra/CRAView.vue": "auswahlfeld",
        "frontend/src/components/sidebars/CRASidebar.vue": "seitenleiste",
    }
    # Zwei Fehlalarme beim ersten Anlauf, beide lehrreich:
    #   * ``\b`` ist Pflicht — ``critical_issues`` ist ein anderes Feld, und
    #     ein Teilstring-Treffer darauf meldet funktionierenden Code.
    #   * HTML-Kommentare gehen über mehrere Zeilen; ``split("//")`` fasst sie
    #     nicht. Die Begründung IM Kommentar nennt die Alt-Schlüssel, und der
    #     Wächter schlug auf seine eigene Erklärung an — dieselbe Falle wie in
    #     #1834/#1867/#1878.
    # Ein Prüfer, dessen Ausgabe man nicht mehr liest, prüft nichts.
    muster = re.compile(r"\bcritical_(?:i|ii)\b")
    treffer: list[str] = []
    for datei in quellen:
        text = (WURZEL / datei).read_text(encoding="utf-8")
        # HTML-Kommentare ausblenden, Zeilennummern erhalten.
        text = re.sub(r"<!--.*?-->",
                      lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)
        for nr, zeile in enumerate(text.splitlines(), 1):
            ohne = zeile.split("#", 1)[0].split("//", 1)[0]
            if muster.search(ohne):
                treffer.append(f"{datei}:{nr} — {zeile.strip()[:72]}")
    assert not treffer, (
        "Erfundene Produktklasse außerhalb von LEGACY_PRODUKTKLASSEN:\n  "
        + "\n  ".join(treffer)
        + "\nAnhang IV hat keine Klassen. Der Schlüssel heißt 'critical'; die "
          "Alt-Schlüssel gehören ausschließlich in die Abbildungstabelle.")

    # Die Firmen-API muss die Klassen aus dem Katalog nehmen.
    firmen = (WURZEL / "server/api/firmen.py").read_text(encoding="utf-8")
    assert "ALLOWED_PRODUKTKLASSEN = set(_PRODUKTKLASSEN)" in firmen, (
        "Die Firmen-API führt wieder eine eigene Klassenliste — vorher fehlte "
        "dort 'critical', ein kritisches Produkt war nicht erfassbar")


def test_die_anzahl_der_anforderungen_steht_nur_einmal():
    """Die Zahl im Frontend war eine Spiegel-Liste (#1920).

    ``CRAView.vue`` nannte „32 Anforderungen" an zwei Stellen als Literal —
    in der Kopfzeile und im Hinweis zum Excel-Export. Als der Katalog mit
    #1920 auf 36 wuchs (Art. 13 Abs. 15, 16, 21, 23), hätte die Oberfläche
    weiter 32 behauptet, ohne dass etwas fehlschlägt.

    Dieselbe Fehlerklasse wie #1731/#1735, nur harmlos in der Wirkung und
    deshalb besonders leicht zu übersehen: Niemand bemerkt eine falsche Zahl
    in einer Unterzeile, bis ein Kunde sie gegen die Liste hält.
    """
    from cra.requirements import CRA_ANFORDERUNGEN

    datei = WURZEL / "frontend/src/views/cra/CRAView.vue"
    text = datei.read_text(encoding="utf-8")
    zahlen = {int(m) for m in re.findall(r"(\d+)\s+Anforderungen", text)}
    assert zahlen, "keine Angabe „N Anforderungen“ in CRAView.vue gefunden"
    assert zahlen == {len(CRA_ANFORDERUNGEN)}, (
        f"CRAView.vue nennt {sorted(zahlen)} Anforderungen, der Katalog hat "
        f"{len(CRA_ANFORDERUNGEN)}. Beide Stellen nachziehen — oder besser, "
        "die Zahl aus dem Profil laden statt sie zu tippen.")


def test_die_vier_pflichten_aus_1920_sind_im_katalog():
    """Art. 13 Abs. 15, 16, 21 und 23 hatten keine Anforderung.

    Sie stehen im Verordnungstext und waren im Katalog nicht abgebildet — eine
    Lücke, die kein Prüfpunkt melden konnte, weil nichts fehlschlug: Der
    Reifegrad rechnete einfach über 32 statt 36 Anforderungen.

    Bei Abs. 21 und 23 wird bewertet, ob der **Ablauf festgelegt** ist, nicht
    ob er schon gebraucht wurde — genauso hält es der Katalog bei den
    Meldepflichten nach Art. 14.
    """
    from cra.requirements import CRA_ANFORDERUNGEN

    nach_ref = {str(a["id"]): str(a["ref"]) for a in CRA_ANFORDERUNGEN}
    for rid, ref in (("ART13-06", "Art. 13 Abs. 15"),
                     ("ART13-07", "Art. 13 Abs. 16"),
                     ("ART13-08", "Art. 13 Abs. 21"),
                     ("ART13-09", "Art. 13 Abs. 23")):
        assert nach_ref.get(rid) == ref, (rid, nach_ref.get(rid), ref)
    # Jede Anforderung braucht ein Gewicht — ohne das zählt sie im Reifegrad
    # nicht mit und wäre eine Anforderung ohne Wirkung (#1805/#1840).
    ohne = [str(a["id"]) for a in CRA_ANFORDERUNGEN
            if not int(a.get("gewichtung") or 0)]
    assert not ohne, f"Anforderung ohne Gewichtung: {ohne}"


def test_zahlenaufzaehlungen_werden_richtig_gelesen():
    """Sonst wäre der Wächter ein Teppich aus Fehlalarmen.

    Die Zitate im Bestand nennen Bereiche und Aufzählungen: „Abs. 9 und 13",
    „Nr. 2 und 8", „Abs. 1–4", „Abs. 3, 4 und 5". Liest der Test sie falsch,
    meldet er funktionierende Stellen — und ein Prüfer, dessen Ausgabe man
    nicht mehr liest, prüft nichts.
    """
    assert _zahlen("4") == [4]
    assert _zahlen("2 und 8") == [2, 8]
    assert _zahlen("3, 4 und 5") == [3, 4, 5]
    assert _zahlen("1–4") == [1, 2, 3, 4]
    assert _zahlen("9 und 13") == [9, 13]
    assert _zahlen("1 bis 8") == [1, 8]      # „bis" ist eine Aufzählung, kein Bereich
