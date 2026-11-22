"""CRA-Anforderungskatalog – Verordnung (EU) 2024/2847, Annex I + Art. 13/14.

Jede Anforderung ist mit dem exakten Artikelverweis versehen, um wissenschaftliche
Transparenz und Nachvollziehbarkeit im Bericht sicherzustellen.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from shared import katalog_sprache as _ks

if TYPE_CHECKING:  # #1896: nur für die Annotation, nicht zur Laufzeit
    from pathlib import Path

# ── Produktklassen (Annex III / IV) ───────────────────────────────────────────
PRODUKTKLASSEN = {
    "default": {
        "label": "Standardprodukt (nicht gelistet)",
        "label_en": "Default product (not listed)",
        "farbe": "#2e7d32",
        "konformitaet": "Selbstbewertung (Art. 32 Abs. 1)",
        "beschreibung": (
            "Ca. 90% aller Produkte mit digitalen Elementen. "
            "Konformitätsbewertung durch Selbstdeklaration des Herstellers."
        ),
        "beschreibung_en": (
            "Roughly 90% of all products with digital elements. Conformity "
            "assessment by self-declaration of the manufacturer."),
        "referenz": "Verordnung (EU) 2024/2847, Art. 32 Abs. 1",
        "referenz_en": "Regulation (EU) 2024/2847, Art. 32(1)",
        "kurzlabel": "Standardprodukt (nicht in Anhang III/IV gelistet)",
        "kurzlabel_en": "Default product (not listed in Annex III/IV)",
    },
    "important_i": {
        "label": "Wichtiges Produkt Klasse I (Anhang III)",
        "label_en": "Important product class I (Annex III)",
        "farbe": "#f57f17",
        "konformitaet": "Selbstbewertung mit harmonisierten Normen (Art. 32 Abs. 2)",
        "beschreibung": (
            "Umfasst u.a. Identity-Management-Systeme, Passwort-Manager, "
            "PAM-Software, Firewalls, NAS-Produkte (Heimbereich), Betriebssysteme "
            "für Allgemeinzwecke (nicht unternehmenskritisch)."
        ),
        "beschreibung_en": (
            "Includes identity management systems, password managers, PAM "
            "software, firewalls, NAS products (home use) and general-purpose "
            "operating systems (not business-critical)."),
        "referenz": "Verordnung (EU) 2024/2847, Anhang III Klasse I",
        "referenz_en": "Regulation (EU) 2024/2847, Annex III class I",
        "kurzlabel": "Anhang III Klasse I (wichtiges Produkt)",
        "kurzlabel_en": "Annex III class I (important product)",
    },
    "important_ii": {
        "label": "Wichtiges Produkt Klasse II (Anhang III)",
        "label_en": "Important product class II (Annex III)",
        "farbe": "#e65100",
        "konformitaet": "Drittpartei-Konformitätsbewertung (Art. 32 Abs. 3)",
        "beschreibung": (
            "Umfasst u.a. Hypervisoren, Firewalls für den Unternehmenseinsatz, "
            "Betriebssysteme für kritische Infrastrukturen, Industrie-Netzwerke, "
            "Hardware-Sicherheitsmodule (HSM)."
        ),
        "beschreibung_en": (
            "Includes hypervisors, firewalls for business use, operating "
            "systems for critical infrastructure, industrial networks and "
            "hardware security modules (HSM)."),
        "referenz": "Verordnung (EU) 2024/2847, Anhang III Klasse II",
        "referenz_en": "Regulation (EU) 2024/2847, Annex III class II",
        "kurzlabel": "Anhang III Klasse II (wichtiges Produkt)",
        "kurzlabel_en": "Annex III class II (important product)",
    },
    "critical": {
        "label": "Kritisches Produkt (Anhang IV)",
        "label_en": "Critical product (Annex IV)",
        "farbe": "#7b0000",
        "konformitaet": "EUCC-Zertifizierung durch Konformitätsbewertungsstelle (Art. 32 Abs. 4)",
        "beschreibung": (
            "Umfasst u.a. Smart-Meter-Gateways, sichere kryptografische Prozessoren, "
            "Chipkarten und vergleichbare sichere Elemente."
        ),
        "beschreibung_en": (
            "Includes smart meter gateways, secure cryptographic processors, "
            "smart cards and comparable secure elements."),
        "referenz": "Verordnung (EU) 2024/2847, Anhang IV",
        "referenz_en": "Regulation (EU) 2024/2847, Annex IV",
        "kurzlabel": "Anhang IV (kritisches Produkt)",
        "kurzlabel_en": "Annex IV (critical product)",
    },
}

# ── Konformitätsbewertungswege (Art. 32 i.V.m. Anhang VIII) ───────────────────
#
# #1759: Welcher Weg offensteht, entscheidet die **Produktklasse**. Diese Regel
# war im Code schon formuliert — als Kommentar in ``cra/doc_export.py`` („Die
# Klasse sagt, welcher Weg zulässig ist") und als Hinweistext für die KI-Prompts
# in ``cra/ai_wizards.py`` — nur angewandt hat sie niemand: Ein als ``critical``
# klassifiziertes Produkt ließ sich über Modul A selbstdeklarieren, eine
# EU-Konformitätserklärung ausstellen und bekam im Release-Check eine grüne
# Ampel. Das Werkzeug bestätigte einen unzulässigen Weg.
#
# Sie steht deshalb **hier**, neben ``PRODUKTKLASSEN``, und nicht ein zweites Mal
# daneben: Zwei Orte mit einer Wahrheit sind die Fehlerklasse, die dieses Projekt
# in #1731 (fünf Kopien der Adapter-Verdrahtung) und #1735 (sechs Kopien der
# Modul→DB-Zuordnung) schon bezahlt hat.
#
# **Nicht** gerechnet wird die Klassifizierung selbst: Anhang III und IV sind
# Produktlisten, kein Rechenweg — die Einordnung bleibt die Entscheidung des
# Anwenders. Geprüft wird nur ihre Folge.

#: Die vier Wege aus Anhang VIII in der Reihenfolge, in der die Oberfläche sie
#: anbietet. ``notifizierte_stelle`` sagt, ob eine Stelle Dritter beteiligt ist —
#: davon hängt ab, ob ein Abschluss ohne Kennnummer/Vertrauenswürdigkeitsstufe
#: eine Aussage ist (#1759, Punkt 4).
BEWERTUNGSWEGE: dict[str, dict[str, Any]] = {
    "A": {
        "label": "Modul A — interne Fertigungskontrolle (Selbstbewertung)",
        "notifizierte_stelle": False,
        "referenz": "Verordnung (EU) 2024/2847, Art. 32 Abs. 1 Buchst. a, Anhang VIII",
    },
    "B+C": {
        "label": "Modul B+C — EU-Baumusterprüfung und Konformität mit dem Baumuster",
        "notifizierte_stelle": True,
        "referenz": "Verordnung (EU) 2024/2847, Art. 32 Abs. 1 Buchst. b, Anhang VIII",
    },
    "H": {
        "label": "Modul H — umfassende Qualitätssicherung",
        "notifizierte_stelle": True,
        "referenz": "Verordnung (EU) 2024/2847, Art. 32 Abs. 1 Buchst. c, Anhang VIII",
    },
    "EUCC": {
        # #2048: Der amtliche Begriff ist „Vertrauenswürdigkeitsstufe „mittel““
        # (Art. 32 Abs. 2 und Abs. 3 Buchst. c, Art. 8 Abs. 1). „Vertrauensniveau“
        # und „substanziell“ kommen im deutschen Amtsblatt **0×** vor — das ist
        # die Terminologie der Vorgänger-Entwürfe, und sie wird in den
        # Konformitätsbericht gedruckt.
        "label": ("Europäisches Cybersicherheits-Zertifikat, "
                  "Vertrauenswürdigkeitsstufe mindestens „mittel“"),
        "notifizierte_stelle": True,
        # #2058: Die alte Angabe („Art. 27 i.V.m. Art. 32 Abs. 4“) warf zwei
        # Verweisketten zusammen. Richtig ist Art. 32 Abs. 1 Buchst. d bzw.
        # Abs. 3 Buchst. c i.V.m. Art. 27 Abs. 9; für Anhang-IV-Produkte
        # Art. 32 Abs. 4 Buchst. a i.V.m. Art. 8 Abs. 1.
        #
        # **Zum Etikett „EUCC“, richtiggestellt:** Der Begriff steht im deutschen
        # Amtsblatt der CRA **viermal** — in den Erwägungsgründen und einer
        # Fußnote, mit Verweis auf die Durchführungsverordnung (EU) 2024/482 —,
        # aber in **keinem Artikel**. Die operativen Vorschriften sprechen von
        # einem „europäischen Schema für die Cybersicherheitszertifizierung“
        # nach VO (EU) 2019/881. Die frühere Notiz „die CRA nennt EUCC nirgends“
        # war zu scharf; gezählt am Text (09.11.2026).
        "referenz": ("Verordnung (EU) 2024/2847, Art. 32 Abs. 1 Buchst. d bzw. "
                     "Abs. 3 Buchst. c i.V.m. Art. 27 Abs. 9; für Anhang-IV-"
                     "Produkte Art. 32 Abs. 4 Buchst. a i.V.m. Art. 8 Abs. 1; "
                     "Schema nach Verordnung (EU) 2019/881 "
                     "(EUCC: Durchführungsverordnung (EU) 2024/482)"),
    },
}

#: Produktklasse → zulässige Bewertungswege, je Zeile mit Rechtsbezug.
#:
#: ``bedingt`` nennt Wege, die nur unter einer Bedingung offenstehen, die diese
#: Anwendung nicht entscheiden kann (Modul A bei Anhang III Klasse I setzt die
#: **vollständige** Anwendung harmonisierter Normen voraus). Solche Wege gelten
#: als zulässig — die Bedingung wird dem Anwender als Hinweis gesagt, nicht als
#: Ablehnung. Eine Anwendung, die hier abweist, entscheidet über die Arbeitsweise
#: statt über die Konformität.
#:
#: Strengere Wege bleiben überall zulässig: Art. 32 Abs. 1 stellt die Verfahren
#: zur Wahl, und ein Hersteller, der freiwillig eine notifizierte Stelle
#: einschaltet, wird dafür nicht abgewiesen. Unzulässig ist nur der umgekehrte
#: Fall — die Selbstbewertung dort, wo das Gesetz eine dritte Stelle verlangt.
KLASSEN_BEWERTUNGSWEGE: dict[str, dict[str, Any]] = {
    "default": {
        "wege": ("A", "B+C", "H", "EUCC"),
        "bedingt": {},
        "referenz": "Verordnung (EU) 2024/2847, Art. 32 Abs. 1",
        "begruendung": (
            "Nicht in Anhang III oder IV gelistet: Die Selbstbewertung nach "
            "Modul A genügt; die übrigen Verfahren stehen zur Wahl."),
    },
    "important_i": {
        "wege": ("A", "B+C", "H", "EUCC"),
        "bedingt": {
            "A": ("nur bei vollständiger Anwendung harmonisierter Normen, "
                  "gemeinsamer Spezifikationen oder eines europäischen "
                  "Cybersicherheits-Zertifizierungsschemas "
                  "(Vertrauenswürdigkeitsstufe mindestens „mittel“) — sonst "
                  "Modul B+C oder Modul H"),   # #2048
        },
        "referenz": "Verordnung (EU) 2024/2847, Art. 32 Abs. 2",
        "begruendung": (
            "Anhang III Klasse I: Modul A nur, soweit die einschlägigen "
            "harmonisierten Normen oder gemeinsamen Spezifikationen vollständig "
            "angewandt wurden; andernfalls Modul B+C oder Modul H."),
    },
    "important_ii": {
        "wege": ("B+C", "H", "EUCC"),
        "bedingt": {},
        "referenz": "Verordnung (EU) 2024/2847, Art. 32 Abs. 3",
        "begruendung": (
            "Anhang III Klasse II verlangt die Beteiligung einer dritten Stelle: "
            "Modul B+C oder Modul H. Die Selbstbewertung nach Modul A ist "
            "ausgeschlossen — auch bei vollständig angewandten Normen."),
    },
    "critical": {
        "wege": ("EUCC", "B+C", "H"),
        "bedingt": {},
        "referenz": "Verordnung (EU) 2024/2847, Art. 32 Abs. 4 i.V.m. Abs. 3",
        "begruendung": (
            "Anhang IV: europäisches Cybersicherheits-Zertifikat mit "
            "Vertrauenswürdigkeitsstufe mindestens „mittel“, soweit ein Rechtsakt "
            "nach Art. 8 das verlangt; ansonsten die Verfahren nach Art. 32 "
            "Abs. 3 (Modul B+C oder Modul H). Modul A ist in keinem Fall "
            "zulässig."),
    },
}

#: Produktklassen nach aufsteigender Strenge. Grundlage von
#: ``strengste_klasse`` — und der Grund, warum eine abgeschwächte Angabe im
#: Konformitäts-Record die Prüfung nicht aushebeln kann.
KLASSEN_STRENGE: tuple[str, ...] = ("default", "important_i", "important_ii", "critical")


#: Schlüssel, die diese Anwendung geschrieben hat, die die Verordnung aber
#: nicht kennt (#1919).
#:
#: **Anhang IV hat keine Klassen.** Er ist eine Liste von drei Positionen
#: (Hardwaregeräte mit Sicherheitsboxen, Smart-Meter-Gateways, Chipkarten) —
#: anders als Anhang III, der in „Klasse I" und „Klasse II" gegliedert ist.
#: ``critical_i`` und ``critical_ii`` waren also erfundene Produktklassen.
#:
#: Sie werden **abgebildet und nicht abgewiesen**: Ein Bestandsdatensatz soll
#: nicht unspeicherbar werden (die Lehre aus #1779 und #1905), und inhaltlich
#: haben die beiden Schlüssel nie etwas Verschiedenes bedeutet.
LEGACY_PRODUKTKLASSEN: dict[str, str] = {
    "critical_i": "critical",
    "critical_ii": "critical",
}


def normalisiere_klasse(klasse: str | None) -> str:
    """Produktklasse auf einen Schlüssel bringen, den der Katalog kennt.

    Leer bleibt leer — „keine Klasse angegeben" ist ein eigener Zustand und
    nicht dasselbe wie „Standardprodukt". Erst :func:`_klassen_regel` setzt
    daraus ``default``, und zwar für die Matrix-Zeile, nicht für die Anzeige.
    """
    k = str(klasse or "").strip()
    return LEGACY_PRODUKTKLASSEN.get(k, k)


def _klassen_regel(klasse: str) -> dict[str, Any]:
    """Die Matrix-Zeile einer Klasse. Unbekannte Klasse → ``default``-Zeile.

    **Der Befund, der das hierher gebracht hat (#1919):** Die Begründung für
    den Rückfall lautete, eine unbekannte Klasse komme „nur bei Daten vor, die
    diese Anwendung nie geschrieben hat". Das war falsch. Die CRA-API ließ
    ``critical_i`` und ``critical_ii`` ausdrücklich zu, und die Oberfläche bot
    **ausschließlich** diese beiden für kritische Produkte an — ``critical``
    stand im Auswahlfeld überhaupt nicht.

    Die Folge war die schlimmste Form eines stillen Fehlers: Ein kritisches
    Produkt fiel auf die ``default``-Zeile, der Nachweis nannte es
    „Standardprodukt", und ``erlaubte_wege`` hielt die Selbstbewertung nach
    Modul A für zulässig. Fail-open an der Stelle, an der die Verordnung eine
    notifizierte Stelle verlangt.

    Deshalb geht die Klasse jetzt durch :func:`normalisiere_klasse`. Der
    Rückfall auf ``default`` bleibt — für wirklich fremde Daten ist er die
    mildere und damit riskantere Annahme, aber er ist nicht mehr der Weg, auf
    dem die eigenen Schlüssel landen.
    """
    k = normalisiere_klasse(klasse)
    return KLASSEN_BEWERTUNGSWEGE.get(k or "default",
                                      KLASSEN_BEWERTUNGSWEGE["default"])


#: Bezeichnung der Produktklasse auf Englisch (#1954) — für Dokumente, die das
#: Haus verlassen. Die Fundstellen bleiben wörtlich: „Annex III" ist die
#: amtliche englische Bezeichnung derselben Anlage, die deutsch „Anhang III"
#: heißt; die **Nummer** wird nicht angefasst (Lehre aus #1763/#1792).
KLASSE_LABEL_EN: dict[str, str] = {
    "default": "Standard product (not listed in Annex III/IV)",
    "important_i": "Important product class I (Annex III)",
    "important_ii": "Important product class II (Annex III)",
    "critical": "Critical product (Annex IV)",
}


def klasse_label(klasse: str, *, sprache: str | None = None) -> str:
    """Kurzbezeichnung der Produktklasse für Meldungen und Prompts.

    Geht über :func:`normalisiere_klasse` — sonst zeigte ein als
    ``critical_i`` gespeichertes Produkt den Rohwert statt einer Bezeichnung
    (#1919).
    """
    from shared import sprache as _sp

    k = normalisiere_klasse(klasse) or "default"
    if _sp.oder_standard(sprache) == "en" and k in KLASSE_LABEL_EN:
        return KLASSE_LABEL_EN[k]
    eintrag = PRODUKTKLASSEN.get(k) or {}
    return str(eintrag.get("kurzlabel") or eintrag.get("label") or klasse or "default")


def weg_label(weg: str) -> str:
    return str((BEWERTUNGSWEGE.get(weg) or {}).get("label") or weg)


def zulaessige_wege(klasse: str) -> tuple[str, ...]:
    """Die für diese Produktklasse zulässigen Bewertungswege."""
    return tuple(_klassen_regel(klasse)["wege"])


def weg_zulaessig(klasse: str, weg: str) -> bool:
    return str(weg or "") in zulaessige_wege(klasse)


def weg_bedingung(klasse: str, weg: str) -> str:
    """Bedingung, unter der dieser Weg offensteht (leer = unbedingt zulässig)."""
    return str(_klassen_regel(klasse)["bedingt"].get(str(weg or ""), ""))


def weg_regel_referenz(klasse: str) -> str:
    return str(_klassen_regel(klasse)["referenz"])


def weg_ablehnung(klasse: str, weg: str) -> str:
    """Klartext-Begründung, falls der Weg für die Klasse **nicht** zulässig ist.

    Leerer String heißt zulässig. Die Meldung nennt beides, was der Anwender
    braucht, um weiterzukommen: die Klasse, an der es liegt, und die Wege, die
    offenstehen — plus die Rechtsstelle, damit die Ablehnung prüfbar ist.
    """
    weg = str(weg or "")
    if weg_zulaessig(klasse, weg):
        return ""
    regel = _klassen_regel(klasse)
    return (
        f"Bewertungsweg „{weg_label(weg)}“ ist für die Produktklasse "
        f"„{klasse_label(klasse)}“ nicht zulässig. "
        f"Zulässig sind: {', '.join(zulaessige_wege(klasse))}. "
        f"{regel['begruendung']} "
        f"({regel['referenz']}). "
        f"Die Klassifizierung selbst bleibt Ihre Entscheidung — ändern Sie "
        f"entweder den Bewertungsweg oder die Produktklasse."
    )


def weg_hinweis(klasse: str) -> str:
    """Eine Zeile „Welche Wege stehen dieser Klasse offen?“ — für Prompts und UI.

    Einzige Quelle für die Hinweistexte in ``cra/ai_wizards.py``; dort stand die
    Zuordnung vorher als freier Text neben der Matrix (#1759).
    """
    regel = _klassen_regel(klasse)
    teile = [f"{klasse_label(klasse)}: zulässig sind "
             f"{', '.join(zulaessige_wege(klasse))} ({regel['referenz']})"]
    for weg, bedingung in regel["bedingt"].items():
        teile.append(f"{weg} {bedingung}")
    nicht = [w for w in BEWERTUNGSWEGE if w not in zulaessige_wege(klasse)]
    if nicht:
        teile.append(f"nicht zulässig: {', '.join(nicht)}")
    return " — ".join(teile)


def klasse_nb_moeglich(klasse: str) -> bool:
    """Kann/muss bei dieser Klasse eine notifizierte Stelle beteiligt sein?

    Wahr überall, wo die Selbstbewertung nach Modul A **nicht uneingeschränkt**
    offensteht: bei Anhang III Klasse I nur bedingt, bei Klasse II und Anhang IV
    gar nicht. Ersetzt die handgeführte Klassenliste in ``cra/ai_wizards.py``.
    """
    regel = _klassen_regel(klasse)
    return "A" not in regel["wege"] or "A" in regel["bedingt"]


def weg_braucht_notifizierte_stelle(weg: str) -> bool:
    return bool((BEWERTUNGSWEGE.get(str(weg or "")) or {}).get("notifizierte_stelle"))


def strengste_klasse(*klassen: Any) -> str:
    """Die strengste der übergebenen Produktklassen (leere Angaben zählen nicht).

    Gebraucht, weil die Klasse an **zwei** Stellen liegt: auf dem Projekt
    (``cra_projekte.produktklasse``, dort entscheidet sie der Anwender) und als
    Kopie im Konformitäts-Record. Die Oberfläche schickt beim Speichern des
    Records keine Klasse mit, die Kopie steht dort also meist auf ``default`` —
    gegen die Kopie allein zu prüfen hieße, die Prüfung mit einem leeren Feld
    aushebeln zu können.
    """
    rang = -1
    gewinner = "default"
    for k in klassen:
        key = str(k or "").strip()
        if key not in KLASSEN_STRENGE:
            continue
        if KLASSEN_STRENGE.index(key) > rang:
            rang = KLASSEN_STRENGE.index(key)
            gewinner = key
    return gewinner


def abschluss_mangel(weg: str, nb_kennnummer: str = "", eucc_level: str = "") -> str:
    """Was fehlt, damit dieser Bewertungsweg als abgeschlossen gelten kann?

    #1759, Punkt 4: Bei ``B+C``, ``H`` und ``EUCC`` ist eine dritte Stelle
    beteiligt. „Bewertungsweg abgeschlossen" ohne jede Angabe zu dieser Stelle
    ist keine Aussage, sondern ein Haken — und er trägt anschließend Freigabe,
    EU-Konformitätserklärung und CE-Kennzeichnung. Leerer String = kein Mangel.
    """
    weg = str(weg or "")
    if not weg_braucht_notifizierte_stelle(weg):
        return ""
    referenz = str((BEWERTUNGSWEGE.get(weg) or {}).get("referenz") or "")
    if weg == "EUCC":
        if str(eucc_level or "").strip():
            return ""
        return (f"Bewertungsweg „{weg_label(weg)}“ kann nicht als abgeschlossen "
                f"gelten, solange die Vertrauenswürdigkeitsstufe des Zertifikats "
                f"fehlt (mindestens „mittel“, {referenz}).")   # #2048
    if str(nb_kennnummer or "").strip():
        return ""
    return (f"Bewertungsweg „{weg_label(weg)}“ kann nicht als abgeschlossen "
            f"gelten, solange die Kennnummer der notifizierten Stelle fehlt "
            f"({referenz}).")

# ── Kapitel / Domänen ─────────────────────────────────────────────────────────
KAPITEL = {
    "AI1": {
        "titel": "Anhang I Teil I: Produktsicherheitsanforderungen",
        "titel_en": "Annex I Part I: product security requirements",
        "untertitel": "Security by Design & Default",
        "untertitel_en": "Security by design & default",
        "farbe": "#1565c0",
        "soft": "#e3f2fd",
        "referenz": "Verordnung (EU) 2024/2847, Anhang I Teil I",
        "referenz_en": "Regulation (EU) 2024/2847, Annex I Part I",
        "beschreibung": (
            "Sicherheitsanforderungen, die bei Konzeption, Entwicklung und Produktion "
            "von Produkten mit digitalen Elementen erfüllt sein müssen (Art. 6 Abs. 1 i. V. m. Anhang I)."
        ),
        "beschreibung_en": (
            "Security requirements that must be met when products with digital "
            "elements are designed, developed and produced (Art. 6(1) in "
            "conjunction with Annex I)."),
    },
    "AI2": {
        "titel": "Anhang I Teil II: Schwachstellenhandhabung",
        "titel_en": "Annex I Part II: vulnerability handling",
        "untertitel": "Vulnerability Handling Process",
        "untertitel_en": "Vulnerability handling process",
        "farbe": "#4a148c",
        "soft": "#f3e5f5",
        "referenz": "Verordnung (EU) 2024/2847, Anhang I Teil II",
        "referenz_en": "Regulation (EU) 2024/2847, Annex I Part II",
        "beschreibung": (
            "Prozessanforderungen für den gesamten Lebenszyklus des Produkts, "
            "insbesondere für Schwachstellenmanagement und Sicherheitsupdates."
        ),
        "beschreibung_en": (
            "Process requirements for the entire life cycle of the product, in "
            "particular for vulnerability management and security updates."),
    },
    "ART13": {
        "titel": "Art. 13 – Herstellerpflichten",
        "titel_en": "Art. 13 – obligations of manufacturers",
        "untertitel": "Manufacturer Obligations",
        "untertitel_en": "Manufacturer obligations",
        "farbe": "#00695c",
        "soft": "#e0f2f1",
        "referenz": "Verordnung (EU) 2024/2847, Art. 13",
        "referenz_en": "Regulation (EU) 2024/2847, Art. 13",
        "beschreibung": (
            "Allgemeine Pflichten des Herstellers: Risikoabschätzung, CE-Kennzeichnung, "
            "technische Dokumentation, SBOM und Meldepflichten."
        ),
        "beschreibung_en": (
            "General obligations of the manufacturer: cybersecurity risk "
            "assessment, CE marking, technical documentation, SBOM and "
            "reporting obligations."),
    },
    "ART14": {
        "titel": "Art. 14 – Meldepflichten",
        "titel_en": "Art. 14 – reporting obligations",
        "untertitel": "Reporting Obligations (ab 11.09.2026)",
        "untertitel_en": "Reporting obligations (from 11.09.2026)",
        "farbe": "#bf360c",
        "soft": "#fbe9e7",
        "referenz": "Verordnung (EU) 2024/2847, Art. 14",
        "referenz_en": "Regulation (EU) 2024/2847, Art. 14",
        "beschreibung": (
            "Meldepflichten bei aktiv ausgenutzten Schwachstellen und schwerwiegenden "
            "Cybersicherheitsvorfällen. Gilt ab 11. September 2026."
        ),
        "beschreibung_en": (
            "Reporting obligations for actively exploited vulnerabilities and "
            "severe incidents. Applies from 11 September 2026."),
    },
    "IMPL": {
        "titel": "Implementierungsbereitschaft & Prozesse",
        "titel_en": "Implementation readiness & processes",
        "untertitel": "Organisational & Process Readiness",
        "untertitel_en": "Organisational & process readiness",
        "farbe": "#2c3e50",
        "soft": "#ecf0f1",
        "referenz": "Verordnung (EU) 2024/2847, Erwägungsgründe; Art. 13",
        "referenz_en": "Regulation (EU) 2024/2847, recitals; Art. 13",
        "beschreibung": (
            "Organisatorische Reife: interne Prozesse, Verantwortlichkeiten, "
            "Schulungen und Lieferkettensicherheit."
        ),
        "beschreibung_en": (
            "Organisational maturity: internal processes, responsibilities, "
            "training and supply chain security."),
    },
}

# ── Bewertungsskala ───────────────────────────────────────────────────────────
BEWERTUNG_SKALA = {
    0: {"label": "Nicht bewertet", "label_en": "Not assessed", "farbe": "#9e9e9e", "reife_pct": 0},
    1: {"label": "Nicht vorhanden", "label_en": "Not in place", "farbe": "#c62828", "reife_pct": 0},
    2: {"label": "In Planung", "label_en": "Planned", "farbe": "#e65100", "reife_pct": 25},
    3: {"label": "Teilweise umgesetzt", "label_en": "Partly implemented", "farbe": "#f57f17", "reife_pct": 50},
    4: {"label": "Überwiegend umgesetzt", "label_en": "Largely implemented", "farbe": "#2e7d32", "reife_pct": 75},
    5: {"label": "Vollständig umgesetzt", "label_en": "Fully implemented", "farbe": "#1b5e20", "reife_pct": 100},
}

BEWERTUNG_LABELS = [v["label"] for v in BEWERTUNG_SKALA.values()]

# ── Anforderungskatalog ───────────────────────────────────────────────────────
# Jede Anforderung hat:
#   id, kapitel, ref (genaue Artikel-/Absatzreferenz), titel, beschreibung,
#   hinweise (praktische Umsetzungshinweise), gewichtung (1-3)

CRA_ANFORDERUNGEN: list[dict[str, Any]] = [
    # ── Annex I Teil I: Produktsicherheitsanforderungen ───────────────────────
    {
        "id": "AI1-01",
        "kapitel": "AI1",
        "ref": "Anhang I Teil I Nr. 1",
        "ref_en": "Annex I Part I No. 1",
        "titel": "Risikobasierte Cybersicherheit – Design & Entwicklung",
        "titel_en": "Risk-based cybersecurity – design and development",
        "beschreibung": (
            "Produkte müssen so konzipiert, entwickelt und produziert werden, dass "
            "ein angemessenes Cybersicherheitsniveau in Bezug auf die Risiken "
            "gewährleistet wird. Grundlage: Security by Design."
        ),
        "beschreibung_en": (
            "Products with digital elements must be designed, developed and "
            "produced in such a way that they ensure an appropriate level of "
            "cybersecurity based on the risks. Basis: security by design."
        ),
        "hinweise": (
            "Dokumentierter Threat-Modeling-Prozess (z.B. STRIDE, TARA) vor Designbeginn; "
            "Security Requirements als Teil der Produktspezifikation; "
            "Risikobewertung nach ISO/IEC 27005 oder IEC 62443."
        ),
        "hinweise_en": (
            "Documented threat modelling process (e.g. STRIDE, TARA) before "
            "design starts; security requirements as part of the product "
            "specification; risk assessment in accordance with ISO/IEC 27005 or "
            "IEC 62443."
        ),
        "gewichtung": 3,
    },
    {
        "id": "AI1-02",
        "kapitel": "AI1",
        "ref": "Anhang I Teil I Nr. 2 Buchst. a",
        "ref_en": "Annex I Part I No. 2(a)",
        "titel": "Keine bekannten ausnutzbaren Schwachstellen bei Markteinführung",
        "titel_en": "No known exploitable vulnerabilities when placed on the market",
        "beschreibung": (
            "Produkte dürfen keine bekannten ausnutzbaren Schwachstellen aufweisen, "
            "wenn sie auf dem Markt bereitgestellt werden."
        ),
        "beschreibung_en": (
            "Products must not have any known exploitable vulnerabilities when "
            "they are made available on the market."
        ),
        "hinweise": (
            "Regelmäßige Schwachstellen-Scans (SAST/DAST/SCA) vor Release; "
            "CVE-Abgleich aller Komponenten; Penetrationstests; "
            "SBOM-basierte Abhängigkeitsanalyse."
        ),
        "hinweise_en": (
            "Regular vulnerability scans (SAST/DAST/SCA) before release; CVE "
            "matching for all components; penetration tests; SBOM-based "
            "dependency analysis."
        ),
        "gewichtung": 3,
    },
    {
        "id": "AI1-03",
        "kapitel": "AI1",
        "ref": "Anhang I Teil I Nr. 2 Buchst. b",
        "ref_en": "Annex I Part I No. 2(b)",
        "titel": "Sicherheit durch Standardeinstellungen (Secure by Default)",
        "titel_en": "Secure by default configuration",
        "beschreibung": (
            "Produkte müssen mit sicheren Standardkonfigurationen ausgeliefert werden: "
            "kein Standard-Passwort, minimale Angriffsfläche, Least-Privilege-Prinzip."
        ),
        "beschreibung_en": (
            "Products must be made available with a secure default "
            "configuration: no default password, minimal attack surface, "
            "least-privilege principle."
        ),
        "hinweise": (
            "Keine voreingestellten oder leicht erratbaren Passwörter; "
            "Deaktivierung nicht benötigter Dienste und Ports im Auslieferungszustand; "
            "Dokumentation der Standardkonfiguration."
        ),
        "hinweise_en": (
            "No preset or easily guessable passwords; services and ports that "
            "are not needed are disabled in the delivered state; documentation "
            "of the default configuration."
        ),
        "gewichtung": 3,
    },
    {
        "id": "AI1-04",
        "kapitel": "AI1",
        "ref": "Anhang I Teil I Nr. 2 Buchst. e",
        "ref_en": "Annex I Part I No. 2(e)",
        "titel": "Vertraulichkeit – Schutz gespeicherter und übertragener Daten",
        "titel_en": "Confidentiality – protection of stored and transmitted data",
        "beschreibung": (
            "Produkte müssen gespeicherte, übertragene oder anderweitig verarbeitete "
            "Daten durch geeignete kryptografische Verfahren schützen."
        ),
        "beschreibung_en": (
            "Products must protect stored, transmitted or otherwise processed "
            "data by appropriate cryptographic means."
        ),
        "hinweise": (
            "Verschlüsselung ruhender Daten (AES-256 o.ä.); "
            "TLS 1.2+ für alle Netzwerkverbindungen; "
            "Sichere Schlüsselverwaltung; "
            "Keine Hardcoded-Credentials."
        ),
        "hinweise_en": (
            "Encryption of data at rest (AES-256 or similar); TLS 1.2+ for all "
            "network connections; secure key management; no hard-coded "
            "credentials."
        ),
        "gewichtung": 3,
    },
    {
        "id": "AI1-05",
        "kapitel": "AI1",
        "ref": "Anhang I Teil I Nr. 2 Buchst. f",
        "ref_en": "Annex I Part I No. 2(f)",
        "titel": "Integrität – Schutz vor unautorisierten Änderungen",
        "titel_en": "Integrity – protection against unauthorised modification",
        "beschreibung": (
            "Produkte müssen Mechanismen enthalten, die unberechtigte Änderungen "
            "an Daten, Software oder Konfiguration verhindern oder erkennen."
        ),
        "beschreibung_en": (
            "Products must contain mechanisms that prevent or detect "
            "unauthorised modification of data, software or configuration."
        ),
        "hinweise": (
            "Code-Signing für Software-Updates; "
            "Secure Boot für eingebettete Systeme; "
            "Integritätsprüfung der Firmware; "
            "Audit-Trail für Konfigurationsänderungen."
        ),
        "hinweise_en": (
            "Code signing for software updates; secure boot for embedded "
            "systems; integrity check of the firmware; audit trail for "
            "configuration changes."
        ),
        "gewichtung": 3,
    },
    {
        "id": "AI1-06",
        "kapitel": "AI1",
        "ref": "Anhang I Teil I Nr. 2 Buchst. j",
        "ref_en": "Annex I Part I No. 2(j)",
        "titel": "Minimale Angriffsfläche – Reduzierung externer Schnittstellen",
        "titel_en": "Minimal attack surface – limiting external interfaces",
        "beschreibung": (
            "Produkte müssen so gestaltet sein, dass die Angriffsfläche, "
            "einschließlich externer Schnittstellen, minimiert wird."
        ),
        "beschreibung_en": (
            "Products must be designed in such a way that the attack surface, "
            "including external interfaces, is limited."
        ),
        "hinweise": (
            "Inventar aller externen Schnittstellen (APIs, Ports, Protokolle); "
            "Abschaltung ungenutzter Schnittstellen; "
            "Netzwerksegmentierung; "
            "Input-Validierung an allen Schnittstellen."
        ),
        "hinweise_en": (
            "Inventory of all external interfaces (APIs, ports, protocols); "
            "unused interfaces switched off; network segmentation; input "
            "validation at all interfaces."
        ),
        "gewichtung": 2,
    },
    {
        "id": "AI1-07",
        "kapitel": "AI1",
        "ref": "Anhang I Teil I Nr. 2 Buchst. h",
        "ref_en": "Annex I Part I No. 2(h)",
        "titel": "Verfügbarkeit – Schutz wesentlicher Funktionen",
        "titel_en": "Availability – protection of essential functions",
        "beschreibung": (
            "Produkte müssen so konzipiert sein, dass wesentliche Funktionen auch "
            "nach einem Vorfall verfügbar bleiben; Schutz vor DoS-Angriffen."
        ),
        "beschreibung_en": (
            "Products must be designed in such a way that essential functions "
            "remain available also after an incident; protection against "
            "denial-of-service attacks."
        ),
        "hinweise": (
            "Rate-Limiting und DoS-Mitigationsmaßnahmen; "
            "Graceful Degradation im Fehlerfall; "
            "Business-Continuity-Tests; "
            "Failover- und Redundanzkonzepte."
        ),
        "hinweise_en": (
            "Rate limiting and denial-of-service mitigation measures; graceful "
            "degradation in the event of a fault; business continuity tests; "
            "failover and redundancy concepts."
        ),
        "gewichtung": 2,
    },
    {
        "id": "AI1-08",
        "kapitel": "AI1",
        "ref": "Anhang I Teil I Nr. 2 Buchst. l",
        "ref_en": "Annex I Part I No. 2(l)",
        "titel": "Sicherheitsrelevantes Logging & Monitoring",
        "titel_en": "Recording and monitoring of security-relevant activity",
        "beschreibung": (
            "Produkte müssen sicherheitsrelevante interne Aktivitäten aufzeichnen "
            "und/oder überwachen können."
        ),
        "beschreibung_en": (
            "Products must be able to record and/or monitor security-relevant "
            "internal activity."
        ),
        "hinweise": (
            "Audit-Logs für Authentifizierung, Autorisierung, Konfigurationsänderungen; "
            "Manipulationsschutz der Logs; "
            "Definierter Aufbewahrungszeitraum; "
            "SIEM-Integration (wo anwendbar)."
        ),
        "hinweise_en": (
            "Audit logs for authentication, authorisation and configuration "
            "changes; tamper protection for the logs; defined retention period; "
            "SIEM integration (where applicable)."
        ),
        "gewichtung": 2,
    },
    {
        "id": "AI1-09",
        "kapitel": "AI1",
        "ref": "Anhang I Teil I Nr. 2 Buchst. c",
        "ref_en": "Annex I Part I No. 2(c)",
        "titel": "Updatefähigkeit – Sicherheitsupdates ermöglichen",
        "titel_en": "Updatability – enabling security updates",
        "beschreibung": (
            "Produkte müssen so gestaltet sein, dass Schwachstellen durch "
            "Sicherheitsupdates behoben werden können."
        ),
        "beschreibung_en": (
            "Products must be designed in such a way that vulnerabilities can "
            "be addressed through security updates."
        ),
        "hinweise": (
            "OTA-Update-Mechanismus mit Signaturprüfung; "
            "Automatische Sicherheitsupdates als Standardeinstellung (opt-out möglich); "
            "Trennung von Sicherheits- und Funktionsupdates; "
            "Update-Kanal-Authentifizierung."
        ),
        "hinweise_en": (
            "Over-the-air update mechanism with signature verification; "
            "automatic security updates enabled as a default setting (opt-out "
            "possible); separation of security updates and functionality "
            "updates; authentication of the update channel."
        ),
        "gewichtung": 3,
    },
    {
        "id": "AI1-10",
        "kapitel": "AI1",
        "ref": "Anhang I Teil I Nr. 2 Buchst. g",
        "ref_en": "Annex I Part I No. 2(g)",
        "titel": "Datenschutz by Design",
        "titel_en": "Data protection by design",
        "beschreibung": (
            "Produkte müssen mit datenschutzfreundlichen Voreinstellungen und "
            "technischen Maßnahmen zum Schutz personenbezogener Daten entwickelt werden."
        ),
        "beschreibung_en": (
            "Products must be developed with privacy-friendly default settings "
            "and with technical measures for the protection of personal data."
        ),
        "hinweise": (
            "Datenminimierung (nur notwendige Daten erheben); "
            "Privacy by Default als Konfigurationsstandard; "
            "Kompatibilität mit DSGVO-Anforderungen (Art. 25 DSGVO); "
            "Dokumentation der Datenflüsse."
        ),
        "hinweise_en": (
            "Data minimisation (collect only the data that are necessary); "
            "privacy by default as the configuration standard; compatibility "
            "with GDPR requirements (Art. 25 GDPR); documentation of the data "
            "flows."
        ),
        "gewichtung": 2,
    },
    # ── Annex I Teil II: Schwachstellenhandhabung ─────────────────────────────
    {
        "id": "AI2-01",
        "kapitel": "AI2",
        "ref": "Anhang I Teil II Nr. 1",
        "ref_en": "Annex I Part II No. 1",
        "titel": "Schwachstellenidentifikation und -verfolgung",
        "titel_en": "Identification and tracking of vulnerabilities",
        "beschreibung": (
            "Hersteller müssen Schwachstellen in Produkten und Komponenten "
            "systematisch identifizieren, dokumentieren und verfolgen."
        ),
        "beschreibung_en": (
            "Manufacturers must systematically identify, document and track "
            "vulnerabilities in products and components."
        ),
        "hinweise": (
            "Schwachstellen-Tracking-System (Issue Tracker, CVE-Datenbank); "
            "Regelmäßige Scans und Penetrationstests; "
            "Bug-Bounty-Programm oder verantwortungsvolle Offenlegung; "
            "SLA für Schwachstellenbehebung definieren."
        ),
        "hinweise_en": (
            "Vulnerability tracking system (issue tracker, CVE database); "
            "regular scans and penetration tests; bug bounty programme or "
            "responsible disclosure; define an SLA for remediating "
            "vulnerabilities."
        ),
        "gewichtung": 3,
    },
    {
        "id": "AI2-02",
        "kapitel": "AI2",
        "ref": "Anhang I Teil II Nr. 1",
        "ref_en": "Annex I Part II No. 1",
        "titel": "SBOM – Software Bill of Materials",
        "titel_en": "SBOM – software bill of materials",
        "beschreibung": (
            "Hersteller müssen eine maschinenlesbare Stückliste aller Softwarekomponenten "
            "(SBOM) erstellen und pflegen, die mindestens alle Top-Level-Abhängigkeiten enthält."
        ),
        "beschreibung_en": (
            "Manufacturers must draw up and maintain a machine-readable bill of "
            "materials of all software components (SBOM) covering at the very "
            "least all top-level dependencies."
        ),
        "hinweise": (
            "SBOM in standardisiertem Format (CycloneDX, SPDX oder SWID); "
            "Automatische SBOM-Generierung im Build-Prozess (z.B. Syft, CycloneDX-CLI); "
            "Regelmäßige Aktualisierung bei Komponentenänderungen; "
            "Nicht zwingend öffentlich, aber auf Anfrage der Marktüberwachungsbehörde bereitstellen."
        ),
        "hinweise_en": (
            "SBOM in a standardised format (CycloneDX, SPDX or SWID); automatic "
            "SBOM generation in the build process (e.g. Syft, CycloneDX CLI); "
            "regular update when components change; not necessarily public, but "
            "to be provided upon request of the market surveillance authority."
        ),
        "gewichtung": 3,
    },
    {
        "id": "AI2-03",
        "kapitel": "AI2",
        "ref": "Anhang I Teil II Nr. 2 und 8",
        "ref_en": "Annex I Part II No. 2 and 8",
        "titel": "Schnelle Behebung von Schwachstellen – Security Patches",
        "titel_en": "Prompt remediation of vulnerabilities – security patches",
        "beschreibung": (
            "Hersteller müssen Schwachstellen unverzüglich, auch durch Bereitstellung "
            "von Sicherheitsupdates, beheben."
        ),
        "beschreibung_en": (
            "Manufacturers must address and remediate vulnerabilities without "
            "delay, including by providing security updates."
        ),
        "hinweise": (
            "Definierter Patch-Prozess mit klaren Eskalationspfaden; "
            "SLA je nach CVSS-Score (z.B. Kritisch: 24h, Hoch: 7d, Mittel: 30d); "
            "Kostenfreie Sicherheitsupdates während des Support-Zeitraums; "
            "Separater Sicherheits-Update-Kanal."
        ),
        "hinweise_en": (
            "Defined patch process with clear escalation paths; SLA depending "
            "on the CVSS score (e.g. critical: 24h, high: 7d, medium: 30d); "
            "security updates free of charge during the support period; "
            "separate channel for security updates."
        ),
        "gewichtung": 3,
    },
    {
        "id": "AI2-04",
        "kapitel": "AI2",
        "ref": "Anhang I Teil II Nr. 3",
        "ref_en": "Annex I Part II No. 3",
        "titel": "Regelmäßige Sicherheitstests und -überprüfungen",
        "titel_en": "Regular security tests and reviews",
        "beschreibung": (
            "Hersteller müssen regelmäßige Tests und Überprüfungen der "
            "Sicherheit ihrer Produkte durchführen."
        ),
        "beschreibung_en": (
            "Manufacturers must carry out regular tests and reviews of the "
            "security of their products."
        ),
        "hinweise": (
            "Jährliche Penetrationstests durch unabhängige Dritte; "
            "Automatisierte SAST/DAST in der CI/CD-Pipeline; "
            "Fuzz-Testing für kritische Schnittstellen; "
            "Ergebnisse dokumentieren und Maßnahmen nachverfolgen."
        ),
        "hinweise_en": (
            "Annual penetration tests by independent third parties; automated "
            "SAST/DAST in the CI/CD pipeline; fuzz testing for critical "
            "interfaces; document the results and track the measures."
        ),
        "gewichtung": 2,
    },
    {
        "id": "AI2-05",
        "kapitel": "AI2",
        "ref": "Anhang I Teil II Nr. 5",
        "ref_en": "Annex I Part II No. 5",
        "titel": "Koordinierte Schwachstellenoffenlegung (CVD-Policy)",
        "titel_en": "Coordinated vulnerability disclosure (CVD policy)",
        "beschreibung": (
            "Hersteller müssen eine Policy für die koordinierte Offenlegung von "
            "Schwachstellen (Coordinated Vulnerability Disclosure) einrichten und durchsetzen."
        ),
        "beschreibung_en": (
            "Manufacturers must put in place and enforce a policy on "
            "coordinated vulnerability disclosure."
        ),
        "hinweise": (
            "Öffentliche CVD-Policy (z.B. security.txt auf der Website); "
            "Dedizierter Kontaktweg für Sicherheitsforscher; "
            "Klare Zeitpläne für Reaktion und Behebung; "
            "Einhaltung von ISO/IEC 29147 und ISO/IEC 30111."
        ),
        "hinweise_en": (
            "Public CVD policy (e.g. security.txt on the website); dedicated "
            "contact channel for security researchers; clear timelines for "
            "response and remediation; compliance with ISO/IEC 29147 and "
            "ISO/IEC 30111."
        ),
        "gewichtung": 2,
    },
    {
        "id": "AI2-06",
        "kapitel": "AI2",
        "ref": "Anhang I Teil II Nr. 4",
        "ref_en": "Annex I Part II No. 4",
        "titel": "Öffentliche Offenlegung behobener Schwachstellen",
        "titel_en": "Public disclosure of fixed vulnerabilities",
        "beschreibung": (
            "Nach Bereitstellung eines Sicherheitsupdates müssen Informationen über "
            "die behobene Schwachstelle öffentlich zugänglich gemacht werden."
        ),
        "beschreibung_en": (
            "Once a security update has been made available, information about "
            "the fixed vulnerability must be made publicly accessible."
        ),
        "hinweise": (
            "Security Advisories / CVE-Einträge bei ENISA oder nationalen Stellen; "
            "Mindestangaben: Beschreibung, betroffene Versionen, CVSS-Score, Patch-Anleitung; "
            "Responsible Disclosure: Veröffentlichung erst nach Patch-Verfügbarkeit."
        ),
        "hinweise_en": (
            "Security advisories / CVE entries with ENISA or national bodies; "
            "minimum information: description, affected versions, CVSS score, "
            "patch instructions; responsible disclosure: publication only once "
            "a patch is available."
        ),
        "gewichtung": 2,
    },
    {
        "id": "AI2-07",
        "kapitel": "AI2",
        "ref": "Anhang I Teil II Nr. 7",
        "ref_en": "Annex I Part II No. 7",
        "titel": "Mechanismen für sichere Software-Updates",
        "titel_en": "Mechanisms for the secure distribution of software updates",
        "beschreibung": (
            "Hersteller müssen technische Mechanismen für die sichere Verteilung "
            "und Installation von Software-Updates bereitstellen."
        ),
        "beschreibung_en": (
            "Manufacturers must provide for technical mechanisms for the secure "
            "distribution and installation of software updates."
        ),
        "hinweise": (
            "Signierte Update-Pakete mit Zertifikatsvalidierung; "
            "Rollback-Funktion bei fehlgeschlagenem Update; "
            "Integrity-Check vor Installation; "
            "Automatische Updates als Standard, soweit anwendbar "
            "(Anhang I Teil I Nr. 2 Buchst. c)."
        ),
        "hinweise_en": (
            "Signed update packages with certificate validation; rollback "
            "function if an update fails; integrity check before installation; "
            "automatic updates as the default, where applicable (Annex I Part I "
            "No. 2(c))."
        ),
        "gewichtung": 3,
    },
    {
        "id": "AI2-08",
        "kapitel": "AI2",
        "ref": "Anhang I Teil II Nr. 6; Art. 13 Abs. 6",
        "ref_en": "Annex I Part II No. 6; Art. 13(6)",
        "titel": "Informationsaustausch zu Schwachstellen in Drittkomponenten",
        "titel_en": "Sharing of information on vulnerabilities in third-party components",
        "beschreibung": (
            "Hersteller müssen den Informationsaustausch über Schwachstellen "
            "in verwendeten Drittkomponenten fördern."
        ),
        "beschreibung_en": (
            "Manufacturers must facilitate the sharing of information about "
            "vulnerabilities in the third-party components they use."
        ),
        "hinweise": (
            "Aktive Teilnahme an ISAC/CERT-Meldeplattformen; "
            "Regelmäßiger Abgleich mit NVD, OSV, VEX-Feeds; "
            "Interne Prozesse für Drittkomponenten-Monitoring; "
            "Benachrichtigung nachgelagerter Zulieferer bei bekannten Schwachstellen."
        ),
        "hinweise_en": (
            "Active participation in ISAC/CERT reporting platforms; regular "
            "matching against NVD, OSV and VEX feeds; internal processes for "
            "monitoring third-party components; notification of downstream "
            "suppliers in the event of known vulnerabilities."
        ),
        "gewichtung": 2,
    },
    # ── Art. 13 – Herstellerpflichten ─────────────────────────────────────────
    {
        "id": "ART13-01",
        "kapitel": "ART13",
        "ref": "Art. 13 Abs. 2 und 3",
        "ref_en": "Art. 13(2) and (3)",
        "titel": "Durchführung einer Cybersicherheits-Risikoabschätzung",
        "titel_en": "Carrying out a cybersecurity risk assessment",
        "beschreibung": (
            "Hersteller müssen eine Cybersicherheits-Risikoabschätzung für ihr Produkt "
            "durchführen und dokumentieren. Diese informiert alle Entwicklungsphasen."
        ),
        "beschreibung_en": (
            "Manufacturers must undertake and document a cybersecurity risk "
            "assessment for their product. It informs all development phases."
        ),
        "hinweise": (
            "Risikoabschätzung nach ISO/IEC 27005 oder IEC 62443-3-2; "
            "TARA (Threat Analysis & Risk Assessment) gemäß ISO/SAE 21434 für vernetzte Produkte; "
            "Dokumentation der identifizierten Bedrohungen, Schwachstellen und Maßnahmen; "
            "Regelmäßige Aktualisierung bei wesentlichen Produktänderungen."
        ),
        "hinweise_en": (
            "Cybersecurity risk assessment in accordance with ISO/IEC 27005 or "
            "IEC 62443-3-2; TARA (threat analysis and risk assessment) in "
            "accordance with ISO/SAE 21434 for connected products; "
            "documentation of the identified threats, vulnerabilities and "
            "measures; regular update in the event of substantial modifications "
            "of the product."
        ),
        "gewichtung": 3,
    },
    {
        "id": "ART13-02",
        "kapitel": "ART13",
        "ref": "Art. 13 Abs. 12 und 20; Art. 28, Art. 31",
        "ref_en": "Art. 13(12) and (20); Art. 28, Art. 31",
        "titel": "Technische Dokumentation und EU-Konformitätserklärung",
        "titel_en": "Technical documentation and EU declaration of conformity",
        "beschreibung": (
            "Hersteller müssen eine technische Dokumentation erstellen und "
            "eine EU-Konformitätserklärung ausstellen (CE-Kennzeichnung)."
        ),
        "beschreibung_en": (
            "Manufacturers must draw up technical documentation and issue an EU "
            "declaration of conformity (CE marking)."
        ),
        "hinweise": (
            "Technische Dokumentation gemäß Anhang VII: Produktbeschreibung, Risikoabschätzung, "
            "angewandte Normen, Konformitätsbewertungsverfahren, SBOM, Testberichte; "
            "Aufbewahrungspflicht: 10 Jahre nach Markteinführung oder Support-Ende; "
            "EU-Konformitätserklärung nach Anhang V (Art. 28)."
        ),
        "hinweise_en": (
            "Technical documentation in accordance with Annex VII: product "
            "description, cybersecurity risk assessment, standards applied, "
            "conformity assessment procedure, SBOM, test reports; retention "
            "obligation: 10 years after the placing on the market or after the "
            "end of the support period; EU declaration of conformity in "
            "accordance with Annex V (Art. 28)."
        ),
        "gewichtung": 3,
    },
    {
        "id": "ART13-03",
        "kapitel": "ART13",
        "ref": "Art. 13 Abs. 8 und 19",
        "ref_en": "Art. 13(8) and (19)",
        "titel": "Definition und Kommunikation des Support-Zeitraums",
        "titel_en": "Determining and communicating the support period",
        "beschreibung": (
            "Hersteller müssen den Support-Zeitraum festlegen und kommunizieren. "
            "Sicherheitsupdates müssen mindestens 5 Jahre oder die erwartete "
            "Produktlebensdauer lang bereitgestellt werden."
        ),
        "beschreibung_en": (
            "Manufacturers must determine and communicate the support period. "
            "Security updates must be provided for at least 5 years or for the "
            "expected product lifetime."
        ),
        "hinweise": (
            "Support-Zeitraum muss mindestens der erwarteten Nutzungsdauer entsprechen; "
            "Mindestens 5 Jahre (sofern Nutzungsdauer nicht kürzer); "
            "Klare Kommunikation an Nutzer über Ende des Support-Zeitraums; "
            "End-of-Life-Policy veröffentlichen."
        ),
        "hinweise_en": (
            "The support period must correspond at least to the expected time "
            "of use; at least 5 years (unless the time of use is shorter); "
            "clear communication to users about the end of the support period; "
            "publish an end-of-life policy."
        ),
        "gewichtung": 3,
    },
    {
        "id": "ART13-04",
        "kapitel": "ART13",
        "ref": "Art. 13 Abs. 18; Anhang II",
        "ref_en": "Art. 13(18); Annex II",
        "titel": "Sicherheitshinweise und Benutzerinformationen",
        "titel_en": "Security instructions and information to users",
        "beschreibung": (
            "Hersteller müssen klare, verständliche Sicherheitshinweise und "
            "Bedienungsanleitungen in der Sprache des Markts bereitstellen."
        ),
        "beschreibung_en": (
            "Manufacturers must provide clear and understandable security "
            "instructions and user instructions in the language of the market."
        ),
        "hinweise": (
            "Benutzerhandbuch mit Sicherheitskonfigurationsanleitungen; "
            "Hinweise zur sicheren Installation und Konfiguration; "
            "Kontaktdaten für Sicherheitsmeldungen; "
            "Informationen über bekannte Einschränkungen der Cybersicherheit."
        ),
        "hinweise_en": (
            "User manual with instructions for the security configuration; "
            "guidance on secure installation and configuration; contact details "
            "for reporting security issues; information on known cybersecurity "
            "limitations."
        ),
        "gewichtung": 2,
    },
    {
        "id": "ART13-05",
        "kapitel": "ART13",
        "ref": "Art. 13 Abs. 22",
        "ref_en": "Art. 13(22)",
        "titel": "Marktüberwachungs-Kooperation",
        "titel_en": "Cooperation with market surveillance authorities",
        "beschreibung": (
            "Hersteller müssen mit Marktüberwachungsbehörden kooperieren und auf "
            "begründete Anfragen alle notwendigen Informationen bereitstellen."
        ),
        "beschreibung_en": (
            "Manufacturers must cooperate with market surveillance authorities "
            "and, upon reasoned request, provide all the necessary information."
        ),
        "hinweise": (
            # #2049: „binnen 10 Tagen“ stand hier und steht **nicht** in der
            # Verordnung. Art. 13 Abs. 22 verlangt die Übermittlung „auf deren
            # begründetes Verlangen“ — ohne Frist; gezählt am deutschen
            # Amtsblatt: „zehn Tage“, „10 Tage“, „zehn Arbeitstage“ je **0×**.
            # Die Frist setzt die Behörde im Einzelfall (vgl. Art. 54 Abs. 1
            # Unterabs. 2: „innerhalb einer von der Marktüberwachungsbehörde
            # vorgeschriebenen, der Art des Cybersicherheitsrisikos angemessenen
            # Frist“). Eine erfundene gesetzliche Frist ist schlimmer als keine:
            # Danach richtet jemand seinen Prozess aus.
            "Prozess für Anfragen der Marktüberwachungsbehörde (BSI in Deutschland); "
            "Bereitstellung technischer Dokumentation und Informationen auf "
            "begründetes Verlangen (Frist setzt die Behörde im Einzelfall); "
            "Dokumentation der Kommunikation mit Behörden; "
            "Benennung eines Ansprechpartners für Behördenkontakte."
        ),
        "hinweise_en": (
            "Process for requests from the market surveillance authority (BSI "
            "in Germany); provision of the technical documentation upon request "
            "(within 10 days); documentation of the communication with "
            "authorities; designation of a contact person for dealings with "
            "authorities."
        ),
        "gewichtung": 2,
    },
    # ── Art. 13 – die vier Pflichten, die der Katalog bis 8.3.0 nicht führte ──
    # #1920: Sie stehen im Verordnungstext und hatten hier keine Anforderung.
    # Zwei sind formale Produktangaben (Abs. 15/16), zwei sind Abläufe für
    # einen Fall, der hoffentlich nicht eintritt (Abs. 21/23). Bewertet wird
    # bei den beiden Letzteren, ob der Ablauf **festgelegt** ist — nicht, ob
    # er schon gebraucht wurde; genauso hält es der Katalog bei den
    # Meldepflichten nach Art. 14.
    {
        "id": "ART13-06",
        "kapitel": "ART13",
        "ref": "Art. 13 Abs. 15",
        "ref_en": "Art. 13(15)",
        "titel": "Kennzeichnung zur Identifikation des Produkts",
        "titel_en": "Marking for the identification of the product",
        "beschreibung": (
            "Das Produkt trägt eine Typen-, Chargen- oder Seriennummer oder ein "
            "anderes Kennzeichen zu seiner Identifikation. Ist das nicht möglich, "
            "steht die Angabe auf der Verpackung oder in einer Begleitunterlage."
        ),
        "beschreibung_en": (
            "The product bears a type, batch or serial number or another "
            "element allowing its identification. Where that is not possible, "
            "the information is given on the packaging or in a document "
            "accompanying the product."
        ),
        "hinweise": (
            "Bei Software ist das die Fassungsangabe **in der Anwendung selbst** — "
            "nicht nur in einem Dokument daneben; "
            "zusätzlich als Metadatum im ausgelieferten Artefakt; "
            "der Digest des Abbilds als eindeutige technische Kennung; "
            "die Angabe muss ohne Rückfrage beim Hersteller auffindbar sein."
        ),
        "hinweise_en": (
            "For software this is the version information **in the application "
            "itself** — not only in a document alongside it; in addition as "
            "metadata in the delivered artefact; the digest of the image as a "
            "unique technical identifier; the information must be findable "
            "without asking the manufacturer."
        ),
        "gewichtung": 1,
    },
    {
        "id": "ART13-07",
        "kapitel": "ART13",
        "ref": "Art. 13 Abs. 16",
        "ref_en": "Art. 13(16)",
        "titel": "Herstellerangaben am Produkt",
        "titel_en": "Manufacturer details on the product",
        "beschreibung": (
            "Name, eingetragener Handelsname oder eingetragene Marke, Postanschrift, "
            "E-Mail-Adresse oder andere digitale Kontaktangabe und, soweit vorhanden, "
            "die Website stehen auf dem Produkt, der Verpackung oder in einer "
            "Begleitunterlage."
        ),
        "beschreibung_en": (
            "The name, registered trade name or registered trade mark, the "
            "postal address, the email address or other digital contact details "
            "and, where available, the website are given on the product, on its "
            "packaging or in a document accompanying the product."
        ),
        "hinweise": (
            "Bei Software: Angaben in der Anwendung erreichbar (Impressum oder "
            "Über-Dialog); dieselben Angaben in den Anhang-II-Informationen und in "
            "der EU-Konformitätserklärung — eine Abweichung zwischen den drei "
            "Stellen fällt einer Behörde auf; "
            "eine **Postanschrift** ist Pflicht, ein Postfach genügt nicht."
        ),
        "hinweise_en": (
            "For software: the details are reachable within the application "
            "(imprint or about dialog); the same details in the Annex II "
            "information and in the EU declaration of conformity — a "
            "discrepancy between the three places is noticed by an authority; a "
            "**postal address** is mandatory, a post-office box is not "
            "sufficient."
        ),
        "gewichtung": 1,
    },
    {
        "id": "ART13-08",
        "kapitel": "ART13",
        "ref": "Art. 13 Abs. 21",
        "ref_en": "Art. 13(21)",
        "titel": "Korrekturmaßnahmen bei Nicht-Konformität",
        "titel_en": "Corrective measures in the event of non-conformity",
        "beschreibung": (
            "Ab dem Inverkehrbringen und während des Unterstützungszeitraums: Wer "
            "weiß oder Grund zu der Annahme hat, dass das Produkt oder die "
            "festgelegten Verfahren zur Schwachstellenbehandlung den Anforderungen "
            "nicht entsprechen, ergreift unverzüglich Korrekturmaßnahmen — bis zur "
            "Einstellung der Bereitstellung."
        ),
        "beschreibung_en": (
            "From the placing on the market and during the support period: "
            "whoever knows or has reason to believe that the product or the "
            "processes put in place for handling vulnerabilities do not comply "
            "with the requirements immediately takes corrective measures — up "
            "to ceasing to make the product available."
        ),
        "hinweise": (
            "Festgelegter Ablauf in dieser Reihenfolge: korrigierte Fassung "
            "bereitstellen, Betreiber unterrichten, bei Gefährdung die "
            "Bereitstellung der betroffenen Fassung einstellen; "
            "Zuständigkeit namentlich benannt; "
            "Unterrichtung der Marktüberwachungsbehörde, soweit ein Risiko besteht; "
            "bei Software ist ein „Rückruf\u201c die Aufforderung zum Fassungswechsel "
            "samt Einstellung der alten — ein Entfernen aus der Installation des "
            "Betreibers kann der Hersteller nicht bewirken und sollte es nicht "
            "zusagen."
        ),
        "hinweise_en": (
            "A defined procedure, in this order: make a corrected version "
            "available, inform the operators and, where there is a danger, "
            "cease making the affected version available; responsibility "
            "assigned by name; informing the market surveillance authority "
            "where a risk exists; for software a ‘recall’ is the request to "
            "change version together with ceasing to make the old one available "
            "— removing it from the operator’s installation is something the "
            "manufacturer cannot bring about and should not promise."
        ),
        "gewichtung": 2,
    },
    {
        "id": "ART13-09",
        "kapitel": "ART13",
        "ref": "Art. 13 Abs. 23",
        "ref_en": "Art. 13(23)",
        "titel": "Unterrichtung bei Einstellung der Betriebstätigkeit",
        "titel_en": "Information in the event of ceasing operations",
        "beschreibung": (
            "Wer die Betriebstätigkeit einstellt und die Verordnung deshalb nicht "
            "mehr erfüllen kann, unterrichtet **vor** dem Wirksamwerden die "
            "einschlägigen Marktüberwachungsbehörden sowie — mit allen verfügbaren "
            "Mitteln — die Nutzer des Produkts."
        ),
        "beschreibung_en": (
            "Whoever ceases operations and is therefore no longer able to "
            "comply with the Regulation informs **before** that takes effect "
            "the relevant market surveillance authorities as well as — by all "
            "means available — the users of the product."
        ),
        "hinweise": (
            "Vorlauffrist gegenüber den Betreibern zugesagt und veröffentlicht; "
            "Adressbestand der Betreiber gepflegt — ohne ihn ist „mit allen "
            "verfügbaren Mitteln\u201c eine leere Zusage; "
            "Abwägung über den Quellstand (Übergabe, Veröffentlichung, Einstellung) "
            "festgehalten, auch wenn die Verordnung sie nicht verlangt; "
            "der Fall tritt einmal ein oder nie — der Ablauf muss vorher stehen, "
            "sonst wird er im Ernstfall nicht mehr geschrieben."
        ),
        "hinweise_en": (
            "A lead time towards the operators promised and published; the "
            "address records of the operators kept up to date — without them "
            "‘by all means available’ is an empty promise; the decision about "
            "the state of the source code (handover, publication, "
            "discontinuation) recorded, even though the Regulation does not "
            "require it; the case occurs once or never — the procedure must be "
            "in place beforehand, otherwise it will no longer be written when "
            "it matters."
        ),
        "gewichtung": 1,
    },
    # ── Art. 14 – Meldepflichten ──────────────────────────────────────────────
    {
        "id": "ART14-01",
        "kapitel": "ART14",
        "ref": "Art. 14 Abs. 1 und 2 (gilt ab 11.09.2026)",
        "ref_en": "Art. 14(1) and (2) (applies from 11.09.2026)",
        "titel": "Meldung aktiv ausgenutzter Schwachstellen an ENISA",
        "titel_en": "Reporting actively exploited vulnerabilities to ENISA",
        "beschreibung": (
            "Hersteller müssen den als Koordinator benannten CSIRT **und** ENISA "
            "gleichzeitig innerhalb von 24 Stunden informieren, sobald eine aktiv "
            "ausgenutzte Schwachstelle bekannt wird."
        ),
        "beschreibung_en": (
            "Manufacturers must inform the CSIRT designated as coordinator **and** "
            "ENISA simultaneously within 24 hours as soon as they become aware of "
            "an actively exploited vulnerability."
        ),
        "hinweise": (
            "Vorfrühwarnung (Early Warning) innerhalb 24h nach Kenntnisnahme; "
            "Vollständiger Bericht innerhalb 72h; "
            "Abschlussbericht innerhalb 14 Tagen ab Verfügbarkeit der "
            "Korrekturmaßnahme; "
            "Meldekanalinrichtung: ENISA Single Reporting Platform; "
            "Gilt ab 11. September 2026."
        ),
        "hinweise_en": (
            "Early warning within 24h of becoming aware; full report within "
            "72h; final report within 14 days of the corrective measure becoming "
            "available; reporting channel: ENISA single "
            "reporting platform; applies from 11 September 2026."
        ),
        "gewichtung": 3,
    },
    {
        "id": "ART14-02",
        "kapitel": "ART14",
        "ref": "Art. 14 Abs. 3, 4 und 5 (gilt ab 11.09.2026)",
        "ref_en": "Art. 14(3), (4) and (5) (applies from 11.09.2026)",
        "titel": "Meldung schwerwiegender Cybersicherheitsvorfälle",
        "titel_en": "Reporting severe cybersecurity incidents",
        "beschreibung": (
            "Hersteller müssen schwerwiegende Cybersicherheitsvorfälle, die die "
            "Sicherheit ihres Produkts beeinträchtigen, unverzüglich melden."
        ),
        "beschreibung_en": (
            "Manufacturers must report without delay any severe cybersecurity "
            "incident having an impact on the security of their product."
        ),
        "hinweise": (
            "Incident-Response-Plan mit definierten Eskalationspfaden; "
            "Klare Kriterien für die Einstufung als 'schwerwiegend'; "
            "Enge Abstimmung mit NIS2-Meldepflichten (sofern anwendbar); "
            "Meldeprozess dokumentieren und regelmäßig testen."
        ),
        "hinweise_en": (
            "Incident response plan with defined escalation paths; clear "
            "criteria for classifying an incident as ‘severe’; close alignment "
            "with the NIS2 reporting obligations (where applicable); document "
            "the reporting process and test it regularly."
        ),
        "gewichtung": 3,
    },
    {
        "id": "ART14-03",
        "kapitel": "ART14",
        "ref": "Art. 14 Abs. 6, 7 und 8 (gilt ab 11.09.2026)",
        "ref_en": "Art. 14(6), (7) and (8) (applies from 11.09.2026)",
        "titel": "Kooperation mit CSIRT und Behörden",
        "titel_en": "Cooperation with CSIRTs and authorities",
        "beschreibung": (
            "Hersteller müssen mit nationalen CSIRTs und zuständigen Behörden "
            "bei der Vorfallsbearbeitung kooperieren."
        ),
        "beschreibung_en": (
            "Manufacturers must cooperate with the national CSIRTs and the "
            "competent authorities in handling incidents."
        ),
        "hinweise": (
            "Kontakte zu BSI-CERT (Deutschland) und ENISA aufbauen; "
            "Benennung eines Security-Ansprechpartners (24/7 erreichbar); "
            "Übergabe von technischen Details und Kompromittierungsindikatoren (IoC); "
            "Regelmäßige Teilnahme an Cybersicherheitsübungen."
        ),
        "hinweise_en": (
            "Establish contacts with BSI-CERT (Germany) and ENISA; designate a "
            "security contact person (reachable 24/7); hand over technical "
            "details and indicators of compromise (IoC); regular participation "
            "in cybersecurity exercises."
        ),
        "gewichtung": 2,
    },
    # ── Implementierungsbereitschaft ──────────────────────────────────────────
    {
        "id": "IMPL-01",
        "kapitel": "IMPL",
        # #2056: „Erwägungsgrund 34" stand hier und ist der **Lieferketten**-
        # Erwägungsgrund („von Dritten bezogene Komponenten … Sorgfalt"). Für
        # Governance gibt es **keine** Fundstelle: „Governance" kommt im
        # amtlichen CRA-Text **0×** vor, und die Verordnung kennt keine
        # Vorschrift zu Governance-Strukturen. EG 34 ist deshalb zu streichen,
        # nicht zu ersetzen — tragfähig bleibt Art. 13 Abs. 1.
        "ref": "Art. 13 Abs. 1",
        "ref_en": "Art. 13(1)",   # #2056: recital 34 belongs to IMPL-03
        "titel": "Governance und Verantwortlichkeiten für Cybersicherheit",
        "titel_en": "Governance and responsibilities for cybersecurity",
        "beschreibung": (
            "Im Unternehmen müssen klare Verantwortlichkeiten und Governance-Strukturen "
            "für die CRA-Compliance etabliert sein."
        ),
        "beschreibung_en": (
            "Clear responsibilities and governance structures for CRA "
            "compliance must be established in the organisation."
        ),
        "hinweise": (
            "Benennung eines CRA-Verantwortlichen (z.B. CISO, Security Lead); "
            "Management-Commitment zur Cybersicherheit; "
            "Budget und Ressourcen für Sicherheitsmaßnahmen; "
            "Regelmäßige Berichterstattung an Geschäftsführung."
        ),
        "hinweise_en": (
            "Designation of a person responsible for the CRA (e.g. CISO, "
            "security lead); management commitment to cybersecurity; budget and "
            "resources for security measures; regular reporting to the "
            "management."
        ),
        "gewichtung": 2,
    },
    {
        "id": "IMPL-02",
        "kapitel": "IMPL",
        "ref": "Art. 13 Abs. 1; Anhang I Teil II",
        "ref_en": "Art. 13(1); Annex I Part II",
        "titel": "Sicherer Entwicklungsprozess (Secure SDLC)",
        "titel_en": "Secure development process (secure SDLC)",
        "beschreibung": (
            "Im Entwicklungsprozess müssen Cybersicherheitsanforderungen "
            "systematisch berücksichtigt werden (Security by Design)."
        ),
        "beschreibung_en": (
            "Cybersecurity requirements must be taken into account "
            "systematically in the development process (security by design)."
        ),
        "hinweise": (
            "Security Gates im SDLC (Requirements → Design → Code → Test → Release); "
            "Threat Modeling als fester Bestandteil der Design-Phase; "
            "Security Code Reviews und automatisierte Prüfungen (SAST/DAST); "
            "Security-Schulungen für Entwickler."
        ),
        "hinweise_en": (
            "Security gates in the SDLC (requirements → design → code → test → "
            "release); threat modelling as an integral part of the design "
            "phase; security code reviews and automated checks (SAST/DAST); "
            "security training for developers."
        ),
        "gewichtung": 3,
    },
    {
        "id": "IMPL-03",
        "kapitel": "IMPL",
        # #2056: Hier fehlte der Erwägungsgrund, der tatsächlich zur
        # Lieferkette gehört — er stand bei IMPL-01 (Governance). Der Ringtausch
        # ist damit aufgelöst.
        "ref": "Art. 13 Abs. 5; Erwägungsgrund 34",
        "ref_en": "Art. 13(5); recital 34",   # #2056
        "titel": "Lieferkettensicherheit (Supply Chain Security)",
        "titel_en": "Supply chain security",
        "beschreibung": (
            "Hersteller müssen die Sicherheit ihrer Lieferkette, insbesondere "
            "von Drittkomponenten und Open-Source-Software, gewährleisten."
        ),
        "beschreibung_en": (
            "Manufacturers must ensure the security of their supply chain, in "
            "particular of third-party components and open-source software."
        ),
        "hinweise": (
            "Sicherheitsbewertung von Zulieferern und Softwarelieferanten; "
            "Vertragliche Cybersicherheitsanforderungen an Lieferanten; "
            "SBOM-Anforderung an Zulieferer; "
            "Monitoring von Drittkomponenten auf bekannte Schwachstellen."
        ),
        "hinweise_en": (
            "Security assessment of suppliers and software vendors; contractual "
            "cybersecurity requirements for suppliers; SBOM requirement for "
            "suppliers; monitoring of third-party components for known "
            "vulnerabilities."
        ),
        "gewichtung": 2,
    },
    {
        "id": "IMPL-04",
        "kapitel": "IMPL",
        "ref": "Art. 7 und 32; Anhang III und IV",
        "ref_en": "Art. 7 and 32; Annex III and IV",
        "titel": "Produktklassifizierung und Konformitätsbewertungsweg",
        "titel_en": "Product classification and conformity assessment procedure",
        "beschreibung": (
            "Das Unternehmen muss seine Produkte korrekt klassifizieren "
            "(Default / Important I+II / Critical) und den entsprechenden "
            "Konformitätsbewertungsweg identifizieren."
        ),
        "beschreibung_en": (
            "The organisation must classify its products correctly (default / "
            "important I+II / critical) and identify the corresponding "
            "conformity assessment procedure."
        ),
        "hinweise": (
            "Zuordnung aller Produkte gegen Anhang III (wichtige Produkte) und "
            "Anhang IV (kritische Produkte); "
            "Dokumentation der Klassifizierungsentscheidung mit Begründung; "
            "Bei wichtigen Produkten der Klasse II und kritischen Produkten: "
            "frühzeitige Kontaktaufnahme mit "
            "Konformitätsbewertungsstellen; "
            "Überprüfung bei wesentlichen Produktänderungen."
        ),
        "hinweise_en": (
            "Mapping of all products against Annex III (important products) and "
            "Annex IV (critical products); documentation of the classification "
            "decision with its reasons; for important products of class II and "
            "for critical products: contact conformity assessment bodies early; "
            "review in the event of substantial modifications of the product."
        ),
        "gewichtung": 3,
    },
    {
        "id": "IMPL-05",
        "kapitel": "IMPL",
        "ref": "Art. 13 Abs. 13; Anhang VII",
        "ref_en": "Art. 13(13); Annex VII",
        "titel": "Technische Dokumentation – Lebenszyklus und Archivierung",
        "titel_en": "Technical documentation – life cycle and archiving",
        "beschreibung": (
            "Alle sicherheitsrelevanten technischen Dokumente müssen vollständig "
            "und für mindestens 10 Jahre nach Markteinführung verfügbar sein."
        ),
        "beschreibung_en": (
            "All security-relevant technical documents must be complete and "
            "available for at least 10 years after the placing on the market."
        ),
        "hinweise": (
            "Dokumentenmanagement-System mit Versionierung; "
            "Archivierung: Risikoabschätzung, SBOM, Testberichte, Konformitätserklärung; "
            "Regelmäßige Überprüfung der Vollständigkeit; "
            "Zugriffsschutz und Backup-Konzept für technische Dokumentation."
        ),
        "hinweise_en": (
            "Document management system with versioning; archiving: "
            "cybersecurity risk assessment, SBOM, test reports, declaration of "
            "conformity; regular review of completeness; access protection and "
            "backup concept for the technical documentation."
        ),
        "gewichtung": 2,
    },
    {
        "id": "IMPL-06",
        "kapitel": "IMPL",
        "ref": "Art. 13 Abs. 1; Erwägungsgründe",
        "ref_en": "Art. 13(1); recitals",
        "titel": "Schulung und Awareness – Cybersicherheitskultur",
        "titel_en": "Training and awareness – cybersecurity culture",
        "beschreibung": (
            "Mitarbeiter in Entwicklung und Betrieb müssen über die CRA-Anforderungen "
            "und relevante Cybersicherheitspraktiken geschult sein."
        ),
        "beschreibung_en": (
            "Staff in development and operations must be trained on the CRA "
            "requirements and on relevant cybersecurity practices."
        ),
        "hinweise": (
            "Jährliche Pflichtschulung zu Cybersicherheit und CRA; "
            "Spezifische Trainings für Entwickler (Secure Coding), Operations (Incident Response); "
            "Phishing-Simulationen und Security-Awareness-Kampagnen; "
            "Dokumentation der Schulungsnachweise."
        ),
        "hinweise_en": (
            "Mandatory annual training on cybersecurity and the CRA; specific "
            "training for developers (secure coding) and operations (incident "
            "response); phishing simulations and security awareness campaigns; "
            "documentation of the training records."
        ),
        "gewichtung": 1,
    },
]


_STANDARD_IDS: frozenset[str] = frozenset(r["id"] for r in CRA_ANFORDERUNGEN)


def anforderungen_by_kapitel() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict]] = {k: [] for k in KAPITEL}
    for req in CRA_ANFORDERUNGEN:
        result[req["kapitel"]].append(req)
    return result


def load_merged_anforderungen(db_path: Path | None = None, *,
                              sprache: str | None = None,
                              ) -> list[dict[str, Any]]:
    """Gibt den vollständigen Anforderungskatalog zurück.

    Standardanforderungen werden durch DB-Einträge überschrieben (gleiche ID),
    neue DB-Einträge werden am Ende des jeweiligen Kapitels angefügt.
    Jeder Eintrag bekommt ein Feld ``_quelle``: ``'standard'``, ``'override'`` oder ``'custom'``.
    """
    base: dict[str, dict[str, Any]] = {
        r["id"]: dict(r, _quelle="standard") for r in CRA_ANFORDERUNGEN
    }

    if db_path is not None:
        try:
            from cra.db import load_custom_anforderungen
            for custom in load_custom_anforderungen(db_path):
                rid = custom["id"]
                quelle = "override" if custom.get("ist_override") else "custom"
                entry = {
                    "id": rid,
                    "kapitel": custom["kapitel"],
                    "ref": custom["ref"],
                    "titel": custom["titel"],
                    "beschreibung": custom["beschreibung"],
                    "hinweise": custom["hinweise"],
                    "gewichtung": int(custom["gewichtung"]),
                    "_quelle": quelle,
                }
                base[rid] = entry
        except Exception:
            pass

    # Reihenfolge: Kapitel-Reihenfolge aus KAPITEL, innerhalb alphabetisch nach ID
    kap_order = {k: i for i, k in enumerate(KAPITEL)}
    aus = sorted(base.values(),
                 key=lambda r: (kap_order.get(r.get("kapitel", "IMPL"), 99),
                                r["id"]))
    # #1954: Übersetzt werden nur titel/beschreibung/hinweise. Selbst
    # angelegte Anforderungen tragen keine englische Fassung und bleiben
    # deshalb so stehen, wie der Anwender sie getippt hat.
    return _ks.uebersetze_viele(aus, sprache or "")


def berechne_reifegrad(
    bewertungen: dict[str, int],
    anforderungen: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Berechnet den Reifegrad aus einem Bewertungs-Dict {req_id: bewertung 0-5}.

    Gibt zurück: gesamt_pct, kapitel_pct, ampel-Farbe, bewertete_count, gesamt_count.
    """
    if anforderungen is None:
        anforderungen = CRA_ANFORDERUNGEN

    by_kapitel: dict[str, list[float]] = {k: [] for k in KAPITEL}
    total_pct: list[float] = []

    for req in anforderungen:
        rid = req["id"]
        gewichtung = req.get("gewichtung", 1)
        bew = bewertungen.get(rid, 0)
        if bew == 0:
            continue  # nicht bewertet → nicht in Reifegrad einrechnen
        reife_pct = BEWERTUNG_SKALA[bew]["reife_pct"]
        by_kapitel.setdefault(req["kapitel"], []).extend([reife_pct] * gewichtung)
        total_pct.extend([reife_pct] * gewichtung)

    gesamt_pct = (sum(total_pct) / len(total_pct)) if total_pct else 0.0
    kapitel_pct = {
        k: (sum(vals) / len(vals)) if vals else 0.0
        for k, vals in by_kapitel.items()
    }

    if gesamt_pct >= 70:
        ampel = "gruen"
    elif gesamt_pct >= 40:
        ampel = "orange"
    else:
        ampel = "rot"

    bewertete = sum(1 for rid in bewertungen if bewertungen[rid] > 0)

    return {
        "gesamt_pct": round(gesamt_pct, 1),
        "kapitel_pct": {k: round(v, 1) for k, v in kapitel_pct.items()},
        "ampel": ampel,
        "bewertete_count": bewertete,
        "gesamt_count": len(CRA_ANFORDERUNGEN),
    }


# #920: CRA-Anforderungen, die eine Cybersicherheits-Risikoabschätzung erwarten.
# Reihenfolge = Anzeige-Reihenfolge im Nachweis-Abschnitt. ART13-01/AI1-01 =
# Durchführung/Designgrundlage; ART13-02/IMPL-05 = Teil der techn. Doku;
# IMPL-02 = Secure SDLC nutzt sie.
RISK_ASSESSMENT_REQUIREMENT_IDS = ["ART13-01", "AI1-01", "ART13-02", "IMPL-02", "IMPL-05"]


def get_anforderungen_dict(db_path=None) -> dict:
    """Liefert {anforderung_id: anforderung_dict} (Standard + Custom + Override).

    Stabiler Lookup für die CRA↔Risikobewertung-Verknüpfung (#885). Ohne DB-Pfad
    nur die Standard-Anforderungen; mit Pfad die zusammengeführte Liste."""
    if db_path is None:
        items = CRA_ANFORDERUNGEN
    else:
        try:
            items = load_merged_anforderungen(db_path)
        except Exception:
            items = CRA_ANFORDERUNGEN
    return {str(a.get("id")): a for a in items if a.get("id")}
