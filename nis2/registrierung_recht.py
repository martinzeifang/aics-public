"""Welche Fundstelle die NIS-2-Registrierung trägt (#2004).

``nis2/registrierung_db.py`` nannte **Art. 27 Abs. 2** als Grundlage der sechs
Pflichtangaben — und zwar für jedes Projekt, unabhängig vom Sektor. Das ist für
die Mehrheit der Einrichtungen falsch, und der Text wird in den Nachweis
gedruckt.

**Gegen die amtliche Fassung gelesen** (Richtlinie (EU) 2022/2555,
``data/nis2_resources/32022L2555_DEU.pdf``):

* **Art. 27 Abs. 2** verlangt die sechs Angaben von „den in **Absatz 1**
  genannten Einrichtungen". Absatz 1 zählt sie auf: DNS-Diensteanbieter,
  TLD-Namenregister, Domänennamen-Registrierungsdienste, Cloud-Computing,
  Rechenzentrumsdienste, Inhaltszustellnetze, verwaltete Dienste, verwaltete
  Sicherheitsdienste, Online-Marktplätze, Online-Suchmaschinen und Plattformen
  für Dienste sozialer Netzwerke. **Ein Energieversorger ist nicht darunter.**
* **Art. 3 Abs. 4** verlangt von *allen* wesentlichen und wichtigen
  Einrichtungen — „für die Zwecke der Erstellung der in Absatz 3 genannten
  Liste" — mindestens: Name (a), Anschrift und aktuelle Kontaktdaten
  einschließlich E-Mail-Adressen, IP-Adressbereiche und Telefonnummern (b),
  gegebenenfalls Sektor und Teilsektor (c), gegebenenfalls die Mitgliedstaaten
  der Diensteerbringung (d).

Das ist zum sechsten Mal dieselbe Klasse (#1763, #1792, #1884, #1953, #2003):
Nichts schlägt fehl, es steht nur eine falsche Nummer an der Stelle, an der ein
Prüfer sie liest.

**Was dieses Modul NICHT tut:** die Feldmenge verkleinern. Die sechs Felder
decken beide Artikel ab; sie zu beschneiden würde einen unvollständigen
Datensatz als vollständig ausweisen, und das ist die falsche Richtung (#1751).
Geändert wird die **Aussage über die Grundlage**, nicht die Prüfung.

**Und es erfindet keine nationale Fundstelle.** Die Übermittlung geht an die
zuständige nationale Behörde; die Paragrafen des umsetzenden Gesetzes stehen
hier nicht, weil ich sie nicht gegen den Gesetzestext geprüft habe — eine
geratene Nummer wäre schlimmer als keine (die Lehre aus #1763).
"""
from __future__ import annotations

from typing import Any

#: Die Einrichtungsarten aus **Art. 27 Abs. 1** — wörtlich aus dem Amtsblatt,
#: je mit den Stichwörtern, an denen sie in den Freitextfeldern des Projekts
#: erkennbar sind.
#:
#: **Nicht** über ``nis2.dvo2690.is_dvo_relevant`` entschieden: Dessen
#: Stichwortliste enthält „vertrauensdienst" und „kommunikation" — beide stehen
#: in Art. 27 Abs. 1 *nicht*. Zwei verschiedene Rechtslisten, und sie
#: zusammenzuführen hieße, eine Pflicht auf Einrichtungen auszudehnen, die sie
#: nicht trifft.
ART27_ABS1: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("DNS-Diensteanbieter", ("dns-dienst", "dns dienst", "dns-anbieter", "dns-resolver")),
    ("TLD-Namenregister", ("tld", "namenregister", "top-level-domain", "registry")),
    ("Domänennamen-Registrierungsdienste",
     ("domänennamen-registrierung", "domainnamen-registrierung", "registrar")),
    ("Anbieter von Cloud-Computing-Diensten", ("cloud-computing", "cloud computing", "cloud-dienst")),
    ("Anbieter von Rechenzentrumsdiensten",
     ("rechenzentrumsdienst", "rechenzentrums-dienst", "colocation", "data center", "datacenter")),
    ("Betreiber von Inhaltszustellnetzen",
     ("inhaltszustellnetz", "content delivery", "cdn")),
    ("Anbieter von verwalteten Diensten", ("verwaltete dienste", "managed service")),
    ("Anbieter von verwalteten Sicherheitsdiensten",
     ("verwaltete sicherheitsdienste", "managed security")),
    ("Anbieter von Online-Marktplätzen", ("online-marktplatz", "online marktplatz", "marktplatz")),
    ("Online-Suchmaschinen", ("suchmaschine", "search engine")),
    ("Plattformen für Dienste sozialer Netzwerke",
     ("soziale netzwerke", "sozialer netzwerke", "social network", "social media")),
)

ART27 = "Art. 27 Abs. 2"
ART3 = "Art. 3 Abs. 4"

#: Fundstelle je Feld — je Artikel, weil die Aufzählungen verschieden
#: gegliedert sind. Art. 3 Abs. 4 Buchst. b bündelt Anschrift, Kontaktdaten,
#: IP-Bereiche und Telefonnummern in **einer** Angabe.
FUNDSTELLE: dict[str, dict[str, str]] = {
    ART27: {
        "name": "Art. 27 Abs. 2 Buchst. a",
        "sektor": "Art. 27 Abs. 2 Buchst. b",
        "subsektor": "Art. 27 Abs. 2 Buchst. b",
        "einrichtungsart": "Art. 27 Abs. 2 Buchst. b",
        "anschrift": "Art. 27 Abs. 2 Buchst. c",
        "eu_niederlassungen": "Art. 27 Abs. 2 Buchst. c",
        "kontakt_email": "Art. 27 Abs. 2 Buchst. d",
        "kontakt_telefon": "Art. 27 Abs. 2 Buchst. d",
        "mitgliedstaaten": "Art. 27 Abs. 2 Buchst. e",
        "ip_bereiche": "Art. 27 Abs. 2 Buchst. f",
    },
    ART3: {
        "name": "Art. 3 Abs. 4 Buchst. a",
        "anschrift": "Art. 3 Abs. 4 Buchst. b",
        "kontakt_email": "Art. 3 Abs. 4 Buchst. b",
        "kontakt_telefon": "Art. 3 Abs. 4 Buchst. b",
        "ip_bereiche": "Art. 3 Abs. 4 Buchst. b",
        "sektor": "Art. 3 Abs. 4 Buchst. c",
        "subsektor": "Art. 3 Abs. 4 Buchst. c",
        "mitgliedstaaten": "Art. 3 Abs. 4 Buchst. d",
    },
}

#: Felder, die **nur** Art. 27 Abs. 2 verlangt. Eine Einrichtung nach
#: Art. 3 Abs. 4 soll nicht aufgefordert werden, Angaben zu machen, die die
#: Richtlinie von ihr nicht verlangt — „Art der Einrichtung" (Buchst. b) und
#: die sonstigen Unionsniederlassungen bzw. der Vertreter nach Art. 26 Abs. 3
#: (Buchst. c) stehen dort nicht.
NUR_ART27: tuple[str, ...] = ("einrichtungsart", "eu_niederlassungen")


def _passt(text: str, stichwoerter: tuple[str, ...]) -> bool:
    t = (text or "").strip().lower()
    return bool(t) and any(k in t for k in stichwoerter)


def art27_einrichtung(sektor: str = "", subsektor: str = "",
                      einrichtungsart: str = "") -> str:
    """Name der Art-27-Abs.-1-Einrichtungsart — leer, wenn keine passt."""
    for bezeichnung, stichwoerter in ART27_ABS1:
        for feld in (einrichtungsart, subsektor, sektor):
            if _passt(feld, stichwoerter):
                return bezeichnung
    return ""


def grundlage(daten: dict[str, Any] | None = None) -> dict[str, Any]:
    """Welcher Artikel trägt die Übermittlungspflicht dieses Datensatzes?

    Drei Ausgänge, und der dritte ist wichtig: Ist nichts erfasst, wird
    **nicht geraten**. Eine fehlende Angabe beweist nicht, dass die Einrichtung
    nicht unter Art. 27 Abs. 1 fällt — sie beweist nur, dass es niemand
    eingetragen hat.
    """
    d = dict(daten or {})
    treffer = art27_einrichtung(str(d.get("sektor") or ""),
                               str(d.get("subsektor") or ""),
                               str(d.get("einrichtungsart") or ""))
    if treffer:
        return {"artikel": ART27, "unbestimmt": False, "treffer": treffer,
                "fundstellen": dict(FUNDSTELLE[ART27]),
                "nur_art27_felder": list(NUR_ART27),
                "hinweis": (f"{treffer} — Einrichtung nach Art. 27 Abs. 1; "
                            f"die Angaben folgen {ART27}.")}
    etwas_erfasst = any(str(d.get(f) or "").strip()
                        for f in ("sektor", "subsektor", "einrichtungsart"))
    if etwas_erfasst:
        return {"artikel": ART3, "unbestimmt": False, "treffer": "",
                "fundstellen": dict(FUNDSTELLE[ART3]),
                "nur_art27_felder": [],
                "hinweis": (f"Keine Einrichtungsart nach Art. 27 Abs. 1 — die "
                            f"Übermittlungspflicht folgt {ART3} (Liste der "
                            f"wesentlichen und wichtigen Einrichtungen). "
                            f"„Art der Einrichtung“ und die sonstigen "
                            f"Unionsniederlassungen verlangt die Richtlinie "
                            f"hier nicht.")}
    return {"artikel": "", "unbestimmt": True, "treffer": "",
            "fundstellen": {}, "nur_art27_felder": [],
            "hinweis": ("Sektor und Einrichtungsart sind nicht erfasst — ohne "
                        "sie steht nicht fest, ob Art. 27 Abs. 2 (bestimmte "
                        "digitale Einrichtungen) oder Art. 3 Abs. 4 (alle "
                        "wesentlichen und wichtigen Einrichtungen) gilt.")}


def aenderungsfrist_fundstelle(daten: dict[str, Any] | None = None) -> str:
    """Fundstelle der Änderungsmeldung — für die Wiedervorlage.

    Art. 27 Abs. 3 verlangt die Meldung einer Änderung „unverzüglich, in jedem
    Fall aber innerhalb von drei Monaten". **Art. 27 Abs. 4 ist es nicht** —
    der regelt die Weiterleitung durch die zentrale Anlaufstelle an die ENISA
    und richtet sich nicht an die Einrichtung.

    Für Einrichtungen nach Art. 3 Abs. 4 nennt die Richtlinie keine eigene
    Frist für die Einrichtung; Art. 3 Abs. 3 verpflichtet die **Mitgliedstaaten**
    zur Überprüfung der Liste mindestens alle zwei Jahre. Eine jährliche
    Bestätigung ist nationale Ausgestaltung — und sie wird hier nicht mit einer
    erfundenen Paragrafennummer belegt.
    """
    g = grundlage(daten)
    if g["artikel"] == ART27:
        return "Art. 27 Abs. 3"
    if g["artikel"] == ART3:
        return "Art. 3 Abs. 3 (Überprüfung der Liste durch den Mitgliedstaat)"
    return "NIS-2 (Fundstelle abhängig von der Einrichtungsart)"
