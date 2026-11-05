"""Normen und Spezifikationen für Anhang V Nr. 6 — als Auswahl, nicht als Behauptung (#1884).

WARUM DIESE DATEI EXISTIERT
---------------------------
Anhang V Nr. 6 verlangt den Verweis auf die angewandten harmonisierten Normen
bzw. gemeinsamen Spezifikationen — oder, wenn keine angewandt wurden, die
Spezifikationen, mit denen die Anforderungen aus Anhang I nachgewiesen wurden.
Bis v8.2.2 war das ein leeres Freitextfeld, und eine leere Angabe druckte
``_wert()`` als Gedankenstrich. Das ist in einem unterschriebenen Dokument
**keine Aussage**: Der Leser kann nicht unterscheiden, ob nichts angewandt
wurde oder ob die Angabe schlicht fehlt.

DIE UNTERSCHEIDUNG, DIE DIESE DATEI TRÄGT
-----------------------------------------
Eine **harmonisierte Norm**, deren Fundstelle im Amtsblatt steht, trägt
Konformitätsvermutung (Art. 27). Eine **sonstige technische Spezifikation**
(ISO/IEC 27001, IEC 62443-4-1, OWASP, BSI-Grundschutz …) trägt sie nicht — sie
ist ein Nachweismittel, kein Vermutungstatbestand. Eine Auswahlliste, die
beides in einen Topf wirft, lässt die Erklärung eine Rechtswirkung behaupten,
die nicht besteht. Darum zwei getrennte Gruppen, und :data:`HARMONISIERT` ist
**leer**: Für die Verordnung (EU) 2024/2847 ist nach heutigem Stand keine
harmonisierte Norm im Amtsblatt veröffentlicht. Diese Tatsache ist selbst
Inhalt der Erklärung und keine Lücke dieses Katalogs.

KEINE ERFUNDENEN FUNDSTELLEN
----------------------------
Die Lehre aus #1763/#1792 gilt hier unmittelbar, weil die Angabe gedruckt und
unterschrieben wird. Deshalb trägt **kein** Eintrag eine Amtsblatt-Fundstelle;
genannt wird die **Bezeichnung**, unter der eine Norm im Verkehr ist. Auch die
**Ausgabe** (Jahr, Version) steht bewusst nicht hier: Sie ändert sich, und eine
veraltete Jahreszahl in einer Konformitätserklärung ist eine Falschangabe. Die
Auswahl fügt die Bezeichnung in das Feld ein; welche Ausgabe das Haus angewandt
hat, ergänzt der Unterzeichner.

Wird eine harmonisierte Norm für die CRA veröffentlicht, kommt sie mit ihrer
Amtsblatt-Fundstelle in :data:`HARMONISIERT` und :data:`STAND` wird
nachgezogen. Bis dahin ist die leere Gruppe die richtige Aussage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Stand der Pflege dieses Katalogs. Er wird in der Oberfläche genannt, damit
#: der Anwender weiß, wie alt die Aussage „keine harmonisierten Normen" ist —
#: eine Liste ohne Datum behauptet Zeitlosigkeit.
STAND = "2026-10-30"

GRUPPE_HARMONISIERT = "harmonisiert"
GRUPPE_SPEZIFIKATION = "spezifikation"


@dataclass(frozen=True)
class Norm:
    """Ein wählbarer Eintrag für Anhang V Nr. 6.

    ``vermutung`` ist der rechtlich entscheidende Teil: Nur eine im Amtsblatt
    gelistete harmonisierte Norm löst die Konformitätsvermutung nach Art. 27
    aus. Das Feld steht hier und nicht in der Oberfläche, damit die Zuordnung
    nicht an der Darstellung hängt.
    """

    id: str
    bezeichnung: str
    zweck: str
    gruppe: str = GRUPPE_SPEZIFIKATION
    vermutung: bool = False
    hinweis: str = ""
    #: Schlüssel, unter denen die Akte diesen Eintrag selbst belegt (siehe
    #: ``cra/doc_vorschlag.normen_kandidaten``). Leer = nicht herleitbar.
    belege: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "bezeichnung": self.bezeichnung,
                "zweck": self.zweck, "gruppe": self.gruppe,
                "vermutung": self.vermutung, "hinweis": self.hinweis}


#: Harmonisierte Normen zur Verordnung (EU) 2024/2847 — **bewusst leer**.
#:
#: Die Kommission hat den Normungsauftrag erteilt; veröffentlicht ist nach
#: unserem Stand (:data:`STAND`) keine. Ein Eintrag hier wäre eine erfundene
#: Rechtsgrundlage, und er würde in der Erklärung eine Vermutungswirkung
#: behaupten, die der Marktaufsicht nicht vorgelegt werden kann.
HARMONISIERT: tuple[Norm, ...] = ()

#: Sonstige technische Spezifikationen — Nachweismittel ohne Vermutungswirkung.
SPEZIFIKATIONEN: tuple[Norm, ...] = (
    Norm("iec-62443-4-1", "IEC 62443-4-1",
         "Anforderungen an einen sicheren Produktentwicklungs-Lebenszyklus",
         hinweis="Deckt Anhang I Teil II (Prozesse) breit ab."),
    Norm("iec-62443-4-2", "IEC 62443-4-2",
         "Technische Sicherheitsanforderungen an Komponenten",
         hinweis="Deckt Anhang I Teil I (Produkteigenschaften) breit ab."),
    Norm("etsi-en-303-645", "ETSI EN 303 645",
         "Cybersicherheit für vernetzte Verbraucherprodukte"),
    # Bewusst **ohne** Beleg aus einem verknüpften WiBA-Projekt: WiBA ist das
    # BSI-Vorgehen zur Basis-Absicherung und kein Nachweis einer ISO-27001-
    # Anwendung. Eine solche Herleitung wäre genau die Art stiller Behauptung,
    # die in einer Konformitätserklärung nichts zu suchen hat.
    Norm("iso-iec-27001", "ISO/IEC 27001",
         "Managementsystem für Informationssicherheit",
         hinweis="Organisatorischer Rahmen; belegt Anhang I nicht allein."),
    Norm("iso-iec-27002", "ISO/IEC 27002",
         "Maßnahmenkatalog zur Informationssicherheit"),
    Norm("iso-iec-15408", "ISO/IEC 15408 (Common Criteria)",
         "Kriterien für die Bewertung der IT-Sicherheit"),
    Norm("en-18031", "EN 18031-1 / -2 / -3",
         "Cybersicherheitsanforderungen an funkgestützte Produkte",
         hinweis="Harmonisiert unter der Funkanlagen-Richtlinie 2014/53/EU "
                 "(Delegierte Verordnung (EU) 2022/30) — **nicht** unter der "
                 "Verordnung (EU) 2024/2847. Für die CRA deshalb eine "
                 "Spezifikation ohne Vermutungswirkung."),
    Norm("nist-ssdf", "NIST SP 800-218 (SSDF)",
         "Secure Software Development Framework"),
    Norm("owasp-asvs", "OWASP Application Security Verification Standard",
         "Prüfbare Anforderungen an die Anwendungssicherheit"),
    Norm("owasp-pc", "OWASP Proactive Controls",
         "Secure-by-Design-Kontrollen für die Entwicklung",
         belege=("owasp",),
         hinweis="In diesem Modul als Register geführt — der Stand dort ist "
                 "der Nachweis der Anwendung."),
    Norm("bsi-grundschutz", "BSI IT-Grundschutz",
         "Vorgehen und Bausteine des BSI",
         belege=("wiba",),
         hinweis="Bei verknüpftem WiBA-Projekt belegt der dortige Stand die "
                 "Anwendung des Vorgehens."),
    Norm("spdx", "SPDX",
         "Austauschformat für Stücklisten (SBOM)",
         belege=("sbom_spdx",),
         hinweis="Anhang I Teil II Nr. 1 verlangt eine SBOM; das Format ist "
                 "der angewandte Standard."),
    Norm("cyclonedx", "CycloneDX",
         "Austauschformat für Stücklisten (SBOM)",
         belege=("sbom_cyclonedx",)),
    Norm("stride", "STRIDE",
         "Vorgehen der Bedrohungsmodellierung",
         belege=("threat_stride",),
         hinweis="Methodik, keine Norm — nennenswert, wenn das "
                 "Bedrohungsmodell darauf beruht."),
)

ALLE: tuple[Norm, ...] = HARMONISIERT + SPEZIFIKATIONEN

_NACH_ID: dict[str, Norm] = {n.id: n for n in ALLE}


def nach_id(norm_id: str) -> Norm | None:
    return _NACH_ID.get(str(norm_id or "").strip())


def katalog() -> dict[str, Any]:
    """Der Katalog für die Oberfläche — zwei Gruppen, nie eine Liste.

    Die Gruppen getrennt auszuliefern ist der Punkt: Ein Frontend, das sie
    zusammenwirft, kann die Vermutungswirkung nicht mehr auseinanderhalten.
    """
    return {
        "stand": STAND,
        "gruppen": [
            {
                "id": GRUPPE_HARMONISIERT,
                "titel": "Harmonisierte Normen (Art. 27 — Konformitätsvermutung)",
                "hinweis": (
                    "Für die Verordnung (EU) 2024/2847 ist nach unserem Stand "
                    f"({STAND}) keine harmonisierte Norm im Amtsblatt "
                    "veröffentlicht. Solange das so ist, gehört in Nr. 6 die "
                    "ausdrückliche Feststellung, dass keine angewandt wurden."),
                "normen": [n.as_dict() for n in HARMONISIERT],
            },
            {
                "id": GRUPPE_SPEZIFIKATION,
                "titel": "Sonstige technische Spezifikationen (ohne Vermutungswirkung)",
                "hinweis": (
                    "Nachweismittel für die Anforderungen aus Anhang I. Sie "
                    "lösen keine Konformitätsvermutung aus; genannt werden "
                    "sollen die Spezifikationen, die das Haus tatsächlich "
                    "angewandt hat. Die Ausgabe (Jahr/Version) ergänzt der "
                    "Unterzeichner — sie ändert sich, und eine veraltete "
                    "Jahreszahl wäre eine Falschangabe."),
                "normen": [n.as_dict() for n in SPEZIFIKATIONEN],
            },
        ],
    }


# ── Anhang V Nr. 5 — weiteres Unionsrecht ───────────────────────────────────
#
# Art. 28 Abs. 2 erlaubt **eine** Erklärung für mehrere Rechtsakte. Welche das
# sind, kann diese Anwendung nicht herleiten: Ob ein Produkt unter die
# Funkanlagen-Richtlinie fällt, hängt davon ab, ob es funkt — und das steht
# nirgends in der Akte. Deshalb eine **Auswahl** und keine Ableitung; eine
# geratene Rechtsgrundlage in einer Konformitätserklärung wäre schlimmer als
# ein leeres Feld.
#
# Genannt werden nur die Rechtsakte, für die eine EU-Konformitätserklärung
# überhaupt vorgesehen ist. Die DSGVO und die NIS-2-Richtlinie stehen bewusst
# **nicht** hier: Sie sind keine Harmonisierungsrechtsvorschriften mit
# CE-Konformitätserklärung, und sie dort zu nennen hieße, eine Erklärung über
# etwas abzugeben, das nicht erklärt wird.
UNIONSRECHT: tuple[dict[str, str], ...] = (
    {"id": "red", "bezeichnung": "Richtlinie 2014/53/EU (Funkanlagen, RED)",
     "zweck": "Funkgestützte Produkte"},
    {"id": "emv", "bezeichnung": "Richtlinie 2014/30/EU (EMV)",
     "zweck": "Elektromagnetische Verträglichkeit"},
    {"id": "niederspannung", "bezeichnung": "Richtlinie 2014/35/EU (Niederspannung)",
     "zweck": "Elektrische Betriebsmittel"},
    {"id": "maschinen", "bezeichnung": "Verordnung (EU) 2023/1230 (Maschinen)",
     "zweck": "Maschinen und zugehörige Produkte"},
    {"id": "ai-act", "bezeichnung": "Verordnung (EU) 2024/1689 (KI-Verordnung)",
     "zweck": "KI-Systeme — bei Hochrisiko-Systemen Art. 47"},
    {"id": "mdr", "bezeichnung": "Verordnung (EU) 2017/745 (Medizinprodukte)",
     "zweck": "Medizinprodukte"},
    {"id": "funk-ce", "bezeichnung": "Verordnung (EU) 2019/881 (Cybersecurity Act)",
     "zweck": "Europäisches Zertifizierungsschema (EUCC)"},
)


def unionsrecht_katalog() -> dict[str, Any]:
    return {
        "hinweis": ("Nur Rechtsakte nennen, für die das Produkt tatsächlich "
                    "eine Konformitätserklärung abgibt (Art. 28 Abs. 2 "
                    "erlaubt eine gemeinsame Erklärung). Ob ein Rechtsakt "
                    "greift, hängt vom Produkt ab und wird hier nicht "
                    "hergeleitet."),
        "eintraege": [dict(e) for e in UNIONSRECHT],
    }


__all__ = ["STAND", "GRUPPE_HARMONISIERT", "GRUPPE_SPEZIFIKATION", "Norm",
           "HARMONISIERT", "SPEZIFIKATIONEN", "ALLE", "nach_id", "katalog",
           "UNIONSRECHT", "unionsrecht_katalog"]
