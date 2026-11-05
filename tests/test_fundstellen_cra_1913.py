"""Die Fundstellen des CRA-Katalogs halten, was sie behaupten (#1913).

**Der Befund:** 17 der 32 ``ref``-Angaben in :mod:`cra.requirements` waren
falsch — kein Ausrutscher, sondern ein verschobener Block. Anhang I Teil I
Nr. 2 war über sieben Anforderungen hinweg um mehrere Buchstaben versetzt
(Vertraulichkeit stand auf ``lit. c``, dort steht die Updatefähigkeit), und in
Anhang I Teil II war die Nummerierung durchgehend um eins bis zwei verschoben
(die Veröffentlichungspflicht stand auf Nr. 6, sie ist Nr. 4).

**Warum ein Test und nicht nur eine Korrektur:** Diese Angaben werden in den
**Konformitätsnachweis** gedruckt (``cra/konformitaet_report.py`` baut daraus
die Rechtsgrundlage je Anforderung) und in den Anforderungsbericht
(``cra/report_export.py``). Eine falsche Fundstelle in einer Nachweisakte liest
sich wie eine Feststellung — dieselbe Lehre wie #1763 und #1792. Dort wurden
die Fundstellen der *Release-Checkliste* korrigiert; dieser Katalog wurde
damals nicht mitgeprüft, und genau deshalb fiel es erst zwei Jahre später auf.

**Wogegen dieser Test nicht schützt:** Er prüft die Zuordnung gegen eine
Tabelle, die am 2. November 2026 gegen den **amtlichen deutschen Text** geprüft
wurde (``data/cra_resources/32024R2847_DEU.pdf``, ABl. L vom 20.11.2024, in der
Installation vorhanden). Er kann nicht prüfen, ob der Verordnungstext geändert
wurde — dafür steht die jährliche Durchsicht in
``docs/cra/produktklassifizierung.md``. Was er verhindert, ist der stille
Drift: dass jemand eine Fundstelle anpasst, ohne nachzusehen.

Die Tabelle trägt den **Belegsatz** aus dem Verordnungstext mit, damit sich die
Zuordnung ohne das PDF nachvollziehen lässt. Wer sie ändert, muss den Satz
mitändern — und wer den Satz mitändert, hat nachgelesen.
"""
from __future__ import annotations

import re

import pytest

from cra.requirements import CRA_ANFORDERUNGEN

#: id -> (Fundstelle, Belegsatz aus dem amtlichen deutschen Text)
#:
#: Geprüft am 02.11.2026 gegen 32024R2847_DEU.pdf (Anhang I ab Seite 68,
#: Art. 13 ab Seite 35, Art. 14 ab Seite 38).
GEPRUEFT: dict[str, tuple[str, str]] = {
    # ── Anhang I Teil I: grundlegende Anforderungen an das Produkt ──────
    "AI1-01": ("Anhang I Teil I Nr. 1",
               "Produkte … werden so konzipiert, entwickelt und hergestellt, "
               "dass sie angesichts der Risiken ein angemessenes "
               "Cybersicherheitsniveau bieten"),
    "AI1-02": ("Anhang I Teil I Nr. 2 Buchst. a",
               "ohne bekannte ausnutzbare Schwachstellen auf dem Markt "
               "bereitgestellt werden"),
    "AI1-03": ("Anhang I Teil I Nr. 2 Buchst. b",
               "mit einer sicheren Standardkonfiguration auf dem Markt "
               "bereitgestellt werden"),
    "AI1-04": ("Anhang I Teil I Nr. 2 Buchst. e",
               "die Vertraulichkeit gespeicherter, übermittelter oder "
               "anderweitig verarbeiteter … Daten schützen, z. B. durch "
               "Verschlüsselung relevanter Daten"),
    "AI1-05": ("Anhang I Teil I Nr. 2 Buchst. f",
               "die Integrität gespeicherter, übermittelter oder anderweitig "
               "verarbeiteter Daten …, Befehle, Programme und Konfigurationen"),
    "AI1-06": ("Anhang I Teil I Nr. 2 Buchst. j",
               "so konzipiert … dass sie — auch bei externen Schnittstellen — "
               "möglichst geringe Angriffsflächen bieten"),
    "AI1-07": ("Anhang I Teil I Nr. 2 Buchst. h",
               "die Verfügbarkeit wesentlicher und grundlegender Funktionen, "
               "auch nach einem Sicherheitsvorfall, einschließlich … "
               "Eindämmungsmaßnahmen gegen Überlastungsangriffe"),
    "AI1-08": ("Anhang I Teil I Nr. 2 Buchst. l",
               "sicherheitsbezogene Informationen durch Aufzeichnung und/oder "
               "Überwachung einschlägiger interner Vorgänge"),
    "AI1-09": ("Anhang I Teil I Nr. 2 Buchst. c",
               "sicherstellen, dass Schwachstellen durch "
               "Sicherheitsaktualisierungen behoben werden können"),
    "AI1-10": ("Anhang I Teil I Nr. 2 Buchst. g",
               "die Verarbeitung personenbezogener oder sonstiger Daten auf "
               "solche … auf das für die Zweckbestimmung … notwendige Maß "
               "beschränken"),
    # ── Anhang I Teil II: Umgang mit Schwachstellen ─────────────────────
    # Nr. 1 trägt zwei Anforderungen: das Ermitteln der Schwachstellen und
    # Komponenten UND die Stückliste („u. a. durch Erstellung einer
    # Software-Stückliste"). Zwei Einträge auf dieselbe Nummer sind hier
    # richtig und kein Fehler.
    "AI2-01": ("Anhang I Teil II Nr. 1",
               "Schwachstellen und Komponenten der Produkte … ermitteln und "
               "dokumentieren"),
    "AI2-02": ("Anhang I Teil II Nr. 1",
               "u. a. durch Erstellung einer Software-Stückliste in einem "
               "gängigen maschinenlesbaren Format"),
    "AI2-03": ("Anhang I Teil II Nr. 2 und 8",
               "unverzüglich Schwachstellen behandeln und beheben (2); "
               "Sicherheitsaktualisierungen … unverzüglich und … kostenlos "
               "verbreitet (8)"),
    "AI2-04": ("Anhang I Teil II Nr. 3",
               "die Sicherheit des Produkts … regelmäßig und wirksam testen "
               "und überprüfen"),
    "AI2-05": ("Anhang I Teil II Nr. 5",
               "eine Strategie für die koordinierte Offenlegung von "
               "Schwachstellen aufstellen und umsetzen"),
    "AI2-06": ("Anhang I Teil II Nr. 4",
               "sobald eine Sicherheitsaktualisierung bereitgestellt worden "
               "ist, Informationen über beseitigte Schwachstellen teilen und "
               "veröffentlichen"),
    "AI2-07": ("Anhang I Teil II Nr. 7",
               "Mechanismen für die sichere Verbreitung von Aktualisierungen "
               "… bereitstellen"),
    "AI2-08": ("Anhang I Teil II Nr. 6; Art. 13 Abs. 6",
               "Maßnahmen ergreifen, um den Austausch von Informationen über "
               "mögliche Schwachstellen in ihrem Produkt … und darin "
               "enthaltenen Komponenten Dritter zu erleichtern (Nr. 6); "
               "Meldung an den Hersteller der Komponente (Art. 13 Abs. 6)"),
    # ── Art. 13: Pflichten der Hersteller ───────────────────────────────
    "ART13-01": ("Art. 13 Abs. 2 und 3",
                 "führen die Hersteller eine Bewertung der "
                 "Cybersicherheitsrisiken durch (2); wird … dokumentiert und "
                 "gegebenenfalls aktualisiert (3)"),
    "ART13-02": ("Art. 13 Abs. 12 und 20; Art. 28, Art. 31",
                 "erstellen die Hersteller die in Artikel 31 genannte "
                 "technische Dokumentation (12); fügen … eine Kopie der "
                 "EU-Konformitätserklärung … bei (20)"),
    "ART13-03": ("Art. 13 Abs. 8 und 19",
                 "Unterstützungszeitraum (8); Enddatum … zum Zeitpunkt des "
                 "Kaufs (19)"),
    "ART13-04": ("Art. 13 Abs. 18; Anhang II",
                 "gewährleisten, dass den Produkten … die in Anhang II "
                 "genannten Informationen und Anleitungen … beigefügt sind"),
    "ART13-05": ("Art. 13 Abs. 22",
                 "übermitteln der Marktüberwachungsbehörde auf deren "
                 "begründetes Verlangen … alle Informationen und Unterlagen"),
    # #1920: vier Pflichten, die der Katalog bis 8.3.0 nicht führte
    "ART13-06": ("Art. 13 Abs. 15",
                 "gewährleisten, dass ihre Produkte … eine Typen-, Chargen- "
                 "oder Seriennummer oder ein anderes Kennzeichen zu ihrer "
                 "Identifikation tragen"),
    "ART13-07": ("Art. 13 Abs. 16",
                 "geben den Namen, den eingetragenen Handelsnamen … die "
                 "Postanschrift, die E-Mail-Adresse oder andere digitale "
                 "Kontaktangaben … an"),
    "ART13-08": ("Art. 13 Abs. 21",
                 "Ab dem Inverkehrbringen und während des "
                 "Unterstützungszeitraums ergreifen die Hersteller, denen "
                 "bekannt ist oder die Grund zu der Annahme haben, dass das "
                 "Produkt … nicht entspricht [Korrekturmaßnahmen]"),
    "ART13-09": ("Art. 13 Abs. 23",
                 "Ein Hersteller, der seine Betriebstätigkeit einstellt … "
                 "unterrichtet vor dem Wirksamwerden der Betriebseinstellung "
                 "die einschlägigen Marktüberwachungsbehörden sowie … die "
                 "Nutzer"),
    # ── Art. 14: Meldepflichten ─────────────────────────────────────────
    "ART14-01": ("Art. 14 Abs. 1 und 2 (gilt ab 11.09.2026)",
                 "meldet jede aktiv ausgenutzte Schwachstelle … gleichzeitig "
                 "dem … CSIRT und der ENISA (1); Frühwarnung/Meldung/"
                 "Abschlussbericht (2)"),
    "ART14-02": ("Art. 14 Abs. 3, 4 und 5 (gilt ab 11.09.2026)",
                 "meldet jeden schwerwiegenden Sicherheitsvorfall (3); Stufen "
                 "(4); gilt als schwerwiegend, wenn … (5)"),
    "ART14-03": ("Art. 14 Abs. 6, 7 und 8 (gilt ab 11.09.2026)",
                 "Zwischenbericht auf Aufforderung des CSIRT (6); Meldung über "
                 "den Endpunkt des als Koordinator benannten CSIRT (7); "
                 "informiert er die betroffenen Nutzer (8)"),
    # ── Querschnitt: keine einzelne Fundstelle, bewusst allgemein ───────
    "IMPL-01": ("Art. 13 Abs. 1; Erwägungsgrund 34", "Querschnitt"),
    "IMPL-02": ("Art. 13 Abs. 1; Anhang I Teil II", "Querschnitt"),
    "IMPL-03": ("Art. 13 Abs. 5; Erwägungsgrund 37",
                "lassen die Hersteller die gebotene Sorgfalt walten [bei "
                "Komponenten Dritter]"),
    "IMPL-04": ("Art. 7 und 32; Anhang III und IV",
                "Wichtige Produkte mit digitalen Elementen (Art. 7); "
                "Konformitätsbewertungsverfahren (Art. 32)"),
    "IMPL-05": ("Art. 13 Abs. 13; Anhang VII",
                "bewahren die technische Dokumentation und die "
                "EU-Konformitätserklärung … auf"),
    "IMPL-06": ("Art. 13 Abs. 1; Erwägungsgründe", "Querschnitt"),
}


def _katalog() -> dict[str, dict]:
    return {str(a["id"]): a for a in CRA_ANFORDERUNGEN}


def test_jede_anforderung_steht_in_der_geprueften_tabelle():
    """Eine neue Anforderung ohne geprüfte Fundstelle fällt auf.

    Sonst wäre der Test ein Teppich: Er würde genau die Einträge prüfen, die
    schon geprüft sind, und jeden neuen durchlassen.
    """
    katalog = set(_katalog())
    tabelle = set(GEPRUEFT)
    assert katalog - tabelle == set(), (
        "Anforderung(en) ohne geprüfte Fundstelle: "
        f"{sorted(katalog - tabelle)}. Die Fundstelle gegen den amtlichen "
        "Text prüfen (data/cra_resources/32024R2847_DEU.pdf) und mit "
        "Belegsatz in GEPRUEFT aufnehmen.")
    assert tabelle - katalog == set(), (
        f"Tabelle nennt unbekannte Anforderung(en): {sorted(tabelle - katalog)}")


@pytest.mark.parametrize("rid", sorted(GEPRUEFT))
def test_fundstelle_entspricht_dem_amtlichen_text(rid: str):
    erwartet, beleg = GEPRUEFT[rid]
    ist = str(_katalog()[rid].get("ref") or "")
    assert ist == erwartet, (
        f"{rid}: Fundstelle ist {ist!r}, geprüft ist {erwartet!r}.\n"
        f"Belegsatz aus dem Verordnungstext: „{beleg}“\n"
        "Wenn die Änderung richtig ist, den Belegsatz in GEPRUEFT mitändern — "
        "wer den Satz mitändert, hat nachgelesen.")


def test_keine_englische_mischform():
    """„Annex I, Part I, Abs. 2 lit. c" zitiert keine deutsche Behörde.

    Die Angabe wird in ein Dokument gedruckt, das einer Marktüberwachungs-
    behörde vorgelegt wird. Eine Mischung aus englischer Gliederung und
    deutschen Abkürzungen ist dort nicht zitierfähig.
    """
    schlecht = re.compile(r"\bAnnex\b|\bPart\b|\blit\.|\s\+\s")
    treffer = {rid: a["ref"] for rid, a in _katalog().items()
               if schlecht.search(str(a.get("ref") or ""))}
    assert not treffer, (
        "Englische Mischform in der Fundstelle: "
        + "; ".join(f"{k} = {v!r}" for k, v in sorted(treffer.items())))


def test_die_verschiebung_von_1913_kommt_nicht_zurueck():
    """Die sieben Buchstaben, die im Block verschoben waren.

    Kein zweiter Weg zur selben Aussage, sondern der Fall aus dem Issue
    namentlich: Wer die Tabelle oben versehentlich auf den alten Stand
    zurücksetzt, bekommt hier den Grund genannt.
    """
    # Beide Schreibweisen, denn der alte Katalog schrieb „lit. c". Beim ersten
    # Anlauf prüfte dieser Test nur „Buchst. c" — und blieb damit grün, als ich
    # zur Gegenprobe genau den alten Wert zurückbaute. Ein Wächter, der nur
    # eine Schreibweise der Regression kennt, ist ein halber Wächter.
    falsch_war = {
        "AI1-04": "c", "AI1-05": "d", "AI1-06": "e", "AI1-07": "f",
        "AI1-08": "g", "AI1-09": "h", "AI1-10": "i",
    }
    katalog = _katalog()
    for rid, buchstabe in falsch_war.items():
        ist = str(katalog[rid].get("ref") or "")
        for schreibweise in (f"Buchst. {buchstabe}", f"lit. {buchstabe}"):
            assert schreibweise not in ist, (
                f"{rid} trägt wieder {schreibweise!r} — das war die "
                "Verschiebung aus #1913. In Anhang I Teil I Nr. 2 ist "
                "Buchst. c die Updatefähigkeit, Buchst. d der Zugriffsschutz, "
                "Buchst. e die Vertraulichkeit.")


def test_art14_nennt_den_geltungsbeginn():
    """Art. 14 gilt seit 11.09.2026 — früher als der übrige CRA.

    Der Hinweis steht in der Fundstelle, weil er im Bericht neben der
    Anforderung erscheint. Ohne ihn liest sich die Meldepflicht wie etwas,
    das erst 2027 beginnt.
    """
    for rid in ("ART14-01", "ART14-02", "ART14-03"):
        assert "11.09.2026" in str(_katalog()[rid].get("ref") or ""), (
            f"{rid}: Geltungsbeginn fehlt in der Fundstelle")
