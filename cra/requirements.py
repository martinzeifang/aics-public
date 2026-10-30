"""CRA-Anforderungskatalog – Regulation (EU) 2024/2847, Annex I + Art. 13/14.

Jede Anforderung ist mit dem exakten Artikelverweis versehen, um wissenschaftliche
Transparenz und Nachvollziehbarkeit im Bericht sicherzustellen.
"""
from __future__ import annotations

from typing import Any

# ── Produktklassen (Annex III / IV) ───────────────────────────────────────────
PRODUKTKLASSEN = {
    "default": {
        "label": "Default (nicht gelistet)",
        "farbe": "#2e7d32",
        "konformitaet": "Selbstbewertung (Art. 32 Abs. 1)",
        "beschreibung": (
            "Ca. 90% aller Produkte mit digitalen Elementen. "
            "Konformitätsbewertung durch Selbstdeklaration des Herstellers."
        ),
        "referenz": "Regulation (EU) 2024/2847, Art. 32 Abs. 1",
        "kurzlabel": "Standard (nicht in Annex III/IV gelistet)",
    },
    "important_i": {
        "label": "Important Class I (Annex III)",
        "farbe": "#f57f17",
        "konformitaet": "Selbstbewertung mit harmonisierten Normen (Art. 32 Abs. 2)",
        "beschreibung": (
            "Umfasst u.a. Identity-Management-Systeme, Passwort-Manager, "
            "PAM-Software, Firewalls, NAS-Produkte (Heimbereich), Betriebssysteme "
            "für Allgemeinzwecke (nicht unternehmenskritisch)."
        ),
        "referenz": "Regulation (EU) 2024/2847, Annex III Abs. 1",
        "kurzlabel": "Annex III Klasse I (Wichtig Klasse 1)",
    },
    "important_ii": {
        "label": "Important Class II (Annex III)",
        "farbe": "#e65100",
        "konformitaet": "Drittpartei-Konformitätsbewertung (Art. 32 Abs. 3)",
        "beschreibung": (
            "Umfasst u.a. Hypervisoren, Firewalls für den Unternehmenseinsatz, "
            "Betriebssysteme für kritische Infrastrukturen, Industrie-Netzwerke, "
            "Hardware-Sicherheitsmodule (HSM)."
        ),
        "referenz": "Regulation (EU) 2024/2847, Annex III Abs. 2",
        "kurzlabel": "Annex III Klasse II (Wichtig Klasse 2)",
    },
    "critical": {
        "label": "Critical (Annex IV)",
        "farbe": "#7b0000",
        "konformitaet": "EUCC-Zertifizierung durch Konformitätsbewertungsstelle (Art. 32 Abs. 4)",
        "beschreibung": (
            "Umfasst u.a. Smart-Meter-Gateways, sichere kryptografische Prozessoren, "
            "Chipkarten und vergleichbare sichere Elemente."
        ),
        "referenz": "Regulation (EU) 2024/2847, Annex IV",
        "kurzlabel": "Annex IV (Kritisch)",
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
#: davon hängt ab, ob ein Abschluss ohne Kennnummer/Vertrauensniveau überhaupt
#: eine Aussage ist (#1759, Punkt 4).
BEWERTUNGSWEGE: dict[str, dict[str, Any]] = {
    "A": {
        "label": "Modul A — interne Fertigungskontrolle (Selbstbewertung)",
        "notifizierte_stelle": False,
        "referenz": "Regulation (EU) 2024/2847, Art. 32 Abs. 1 lit. a, Anhang VIII",
    },
    "B+C": {
        "label": "Modul B+C — EU-Baumusterprüfung und Konformität mit dem Baumuster",
        "notifizierte_stelle": True,
        "referenz": "Regulation (EU) 2024/2847, Art. 32 Abs. 1 lit. b, Anhang VIII",
    },
    "H": {
        "label": "Modul H — umfassende Qualitätssicherung",
        "notifizierte_stelle": True,
        "referenz": "Regulation (EU) 2024/2847, Art. 32 Abs. 1 lit. c, Anhang VIII",
    },
    "EUCC": {
        "label": ("Europäisches Cybersicherheits-Zertifikat, Vertrauensniveau "
                  "mindestens „substanziell“"),
        "notifizierte_stelle": True,
        "referenz": ("Regulation (EU) 2024/2847, Art. 27 i.V.m. Art. 32 Abs. 4; "
                     "Verordnung (EU) 2019/881"),
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
        "referenz": "Regulation (EU) 2024/2847, Art. 32 Abs. 1",
        "begruendung": (
            "Nicht in Anhang III oder IV gelistet: Die Selbstbewertung nach "
            "Modul A genügt; die übrigen Verfahren stehen zur Wahl."),
    },
    "important_i": {
        "wege": ("A", "B+C", "H", "EUCC"),
        "bedingt": {
            "A": ("nur bei vollständiger Anwendung harmonisierter Normen, "
                  "gemeinsamer Spezifikationen oder eines europäischen "
                  "Cybersicherheits-Zertifizierungsschemas (Vertrauensniveau "
                  "mindestens „substanziell“) — sonst Modul B+C oder Modul H"),
        },
        "referenz": "Regulation (EU) 2024/2847, Art. 32 Abs. 2",
        "begruendung": (
            "Anhang III Klasse I: Modul A nur, soweit die einschlägigen "
            "harmonisierten Normen oder gemeinsamen Spezifikationen vollständig "
            "angewandt wurden; andernfalls Modul B+C oder Modul H."),
    },
    "important_ii": {
        "wege": ("B+C", "H", "EUCC"),
        "bedingt": {},
        "referenz": "Regulation (EU) 2024/2847, Art. 32 Abs. 3",
        "begruendung": (
            "Anhang III Klasse II verlangt die Beteiligung einer dritten Stelle: "
            "Modul B+C oder Modul H. Die Selbstbewertung nach Modul A ist "
            "ausgeschlossen — auch bei vollständig angewandten Normen."),
    },
    "critical": {
        "wege": ("EUCC", "B+C", "H"),
        "bedingt": {},
        "referenz": "Regulation (EU) 2024/2847, Art. 32 Abs. 4 i.V.m. Abs. 3",
        "begruendung": (
            "Anhang IV: europäisches Cybersicherheits-Zertifikat mit "
            "Vertrauensniveau mindestens „substanziell“, soweit ein Rechtsakt "
            "nach Art. 8 das verlangt; ansonsten die Verfahren nach Art. 32 "
            "Abs. 3 (Modul B+C oder Modul H). Modul A ist in keinem Fall "
            "zulässig."),
    },
}

#: Produktklassen nach aufsteigender Strenge. Grundlage von
#: ``strengste_klasse`` — und der Grund, warum eine abgeschwächte Angabe im
#: Konformitäts-Record die Prüfung nicht aushebeln kann.
KLASSEN_STRENGE: tuple[str, ...] = ("default", "important_i", "important_ii", "critical")


def _klassen_regel(klasse: str) -> dict[str, Any]:
    """Die Matrix-Zeile einer Klasse. Unbekannte Klasse → ``default``-Zeile.

    Eine unbekannte Klasse als ``default`` zu behandeln ist die mildere Annahme
    und damit die riskantere; sie kommt nur bei Daten vor, die diese Anwendung
    nie geschrieben hat (``PRODUKTKLASSEN`` ist geschlossen, und ein Test hält
    Matrix und Klassenliste zusammen).
    """
    return KLASSEN_BEWERTUNGSWEGE.get(klasse or "default",
                                      KLASSEN_BEWERTUNGSWEGE["default"])


def klasse_label(klasse: str) -> str:
    """Kurzbezeichnung der Produktklasse für Meldungen und Prompts."""
    eintrag = PRODUKTKLASSEN.get(klasse or "default") or {}
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
                f"gelten, solange das Vertrauensniveau des Zertifikats fehlt "
                f"(mindestens „substanziell“, {referenz}).")
    if str(nb_kennnummer or "").strip():
        return ""
    return (f"Bewertungsweg „{weg_label(weg)}“ kann nicht als abgeschlossen "
            f"gelten, solange die Kennnummer der notifizierten Stelle fehlt "
            f"({referenz}).")

# ── Kapitel / Domänen ─────────────────────────────────────────────────────────
KAPITEL = {
    "AI1": {
        "titel": "Annex I – Teil I: Produktsicherheitsanforderungen",
        "untertitel": "Security by Design & Default",
        "farbe": "#1565c0",
        "soft": "#e3f2fd",
        "referenz": "Regulation (EU) 2024/2847, Annex I, Part I",
        "beschreibung": (
            "Sicherheitsanforderungen, die bei Konzeption, Entwicklung und Produktion "
            "von Produkten mit digitalen Elementen erfüllt sein müssen (Art. 6 Abs. 1 i.V.m. Annex I)."
        ),
    },
    "AI2": {
        "titel": "Annex I – Teil II: Schwachstellenhandhabung",
        "untertitel": "Vulnerability Handling Process",
        "farbe": "#4a148c",
        "soft": "#f3e5f5",
        "referenz": "Regulation (EU) 2024/2847, Annex I, Part II",
        "beschreibung": (
            "Prozessanforderungen für den gesamten Lebenszyklus des Produkts, "
            "insbesondere für Schwachstellenmanagement und Sicherheitsupdates."
        ),
    },
    "ART13": {
        "titel": "Art. 13 – Herstellerpflichten",
        "untertitel": "Manufacturer Obligations",
        "farbe": "#00695c",
        "soft": "#e0f2f1",
        "referenz": "Regulation (EU) 2024/2847, Art. 13",
        "beschreibung": (
            "Allgemeine Pflichten des Herstellers: Risikoabschätzung, CE-Kennzeichnung, "
            "technische Dokumentation, SBOM und Meldepflichten."
        ),
    },
    "ART14": {
        "titel": "Art. 14 – Meldepflichten",
        "untertitel": "Reporting Obligations (ab 11.09.2026)",
        "farbe": "#bf360c",
        "soft": "#fbe9e7",
        "referenz": "Regulation (EU) 2024/2847, Art. 14",
        "beschreibung": (
            "Meldepflichten bei aktiv ausgenutzten Schwachstellen und schwerwiegenden "
            "Cybersicherheitsvorfällen. Gilt ab 11. September 2026."
        ),
    },
    "IMPL": {
        "titel": "Implementierungsbereitschaft & Prozesse",
        "untertitel": "Organisational & Process Readiness",
        "farbe": "#2c3e50",
        "soft": "#ecf0f1",
        "referenz": "Regulation (EU) 2024/2847, Erwägungsgründe + Art. 13",
        "beschreibung": (
            "Organisatorische Reife: interne Prozesse, Verantwortlichkeiten, "
            "Schulungen und Lieferkettensicherheit."
        ),
    },
}

# ── Bewertungsskala ───────────────────────────────────────────────────────────
BEWERTUNG_SKALA = {
    0: {"label": "Nicht bewertet", "farbe": "#9e9e9e", "reife_pct": 0},
    1: {"label": "Nicht vorhanden", "farbe": "#c62828", "reife_pct": 0},
    2: {"label": "In Planung", "farbe": "#e65100", "reife_pct": 25},
    3: {"label": "Teilweise umgesetzt", "farbe": "#f57f17", "reife_pct": 50},
    4: {"label": "Überwiegend umgesetzt", "farbe": "#2e7d32", "reife_pct": 75},
    5: {"label": "Vollständig umgesetzt", "farbe": "#1b5e20", "reife_pct": 100},
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
        "ref": "Annex I, Part I, Abs. 1",
        "titel": "Risikobasierte Cybersicherheit – Design & Entwicklung",
        "beschreibung": (
            "Produkte müssen so konzipiert, entwickelt und produziert werden, dass "
            "ein angemessenes Cybersicherheitsniveau in Bezug auf die Risiken "
            "gewährleistet wird. Grundlage: Security by Design."
        ),
        "hinweise": (
            "Dokumentierter Threat-Modeling-Prozess (z.B. STRIDE, TARA) vor Designbeginn; "
            "Security Requirements als Teil der Produktspezifikation; "
            "Risikobewertung nach ISO/IEC 27005 oder IEC 62443."
        ),
        "gewichtung": 3,
    },
    {
        "id": "AI1-02",
        "kapitel": "AI1",
        "ref": "Annex I, Part I, Abs. 2 lit. a",
        "titel": "Keine bekannten ausnutzbaren Schwachstellen bei Markteinführung",
        "beschreibung": (
            "Produkte dürfen keine bekannten ausnutzbaren Schwachstellen aufweisen, "
            "wenn sie auf dem Markt bereitgestellt werden."
        ),
        "hinweise": (
            "Regelmäßige Schwachstellen-Scans (SAST/DAST/SCA) vor Release; "
            "CVE-Abgleich aller Komponenten; Penetrationstests; "
            "SBOM-basierte Abhängigkeitsanalyse."
        ),
        "gewichtung": 3,
    },
    {
        "id": "AI1-03",
        "kapitel": "AI1",
        "ref": "Annex I, Part I, Abs. 2 lit. b",
        "titel": "Sicherheit durch Standardeinstellungen (Secure by Default)",
        "beschreibung": (
            "Produkte müssen mit sicheren Standardkonfigurationen ausgeliefert werden: "
            "kein Standard-Passwort, minimale Angriffsfläche, Least-Privilege-Prinzip."
        ),
        "hinweise": (
            "Keine voreingestellten oder leicht erratbaren Passwörter; "
            "Deaktivierung nicht benötigter Dienste und Ports im Auslieferungszustand; "
            "Dokumentation der Standardkonfiguration."
        ),
        "gewichtung": 3,
    },
    {
        "id": "AI1-04",
        "kapitel": "AI1",
        "ref": "Annex I, Part I, Abs. 2 lit. c",
        "titel": "Vertraulichkeit – Schutz gespeicherter und übertragener Daten",
        "beschreibung": (
            "Produkte müssen gespeicherte, übertragene oder anderweitig verarbeitete "
            "Daten durch geeignete kryptografische Verfahren schützen."
        ),
        "hinweise": (
            "Verschlüsselung ruhender Daten (AES-256 o.ä.); "
            "TLS 1.2+ für alle Netzwerkverbindungen; "
            "Sichere Schlüsselverwaltung; "
            "Keine Hardcoded-Credentials."
        ),
        "gewichtung": 3,
    },
    {
        "id": "AI1-05",
        "kapitel": "AI1",
        "ref": "Annex I, Part I, Abs. 2 lit. d",
        "titel": "Integrität – Schutz vor unautorisierten Änderungen",
        "beschreibung": (
            "Produkte müssen Mechanismen enthalten, die unberechtigte Änderungen "
            "an Daten, Software oder Konfiguration verhindern oder erkennen."
        ),
        "hinweise": (
            "Code-Signing für Software-Updates; "
            "Secure Boot für eingebettete Systeme; "
            "Integritätsprüfung der Firmware; "
            "Audit-Trail für Konfigurationsänderungen."
        ),
        "gewichtung": 3,
    },
    {
        "id": "AI1-06",
        "kapitel": "AI1",
        "ref": "Annex I, Part I, Abs. 2 lit. e",
        "titel": "Minimale Angriffsfläche – Reduzierung externer Schnittstellen",
        "beschreibung": (
            "Produkte müssen so gestaltet sein, dass die Angriffsfläche, "
            "einschließlich externer Schnittstellen, minimiert wird."
        ),
        "hinweise": (
            "Inventar aller externen Schnittstellen (APIs, Ports, Protokolle); "
            "Abschaltung ungenutzter Schnittstellen; "
            "Netzwerksegmentierung; "
            "Input-Validierung an allen Schnittstellen."
        ),
        "gewichtung": 2,
    },
    {
        "id": "AI1-07",
        "kapitel": "AI1",
        "ref": "Annex I, Part I, Abs. 2 lit. f",
        "titel": "Verfügbarkeit – Schutz wesentlicher Funktionen",
        "beschreibung": (
            "Produkte müssen so konzipiert sein, dass wesentliche Funktionen auch "
            "nach einem Vorfall verfügbar bleiben; Schutz vor DoS-Angriffen."
        ),
        "hinweise": (
            "Rate-Limiting und DoS-Mitigationsmaßnahmen; "
            "Graceful Degradation im Fehlerfall; "
            "Business-Continuity-Tests; "
            "Failover- und Redundanzkonzepte."
        ),
        "gewichtung": 2,
    },
    {
        "id": "AI1-08",
        "kapitel": "AI1",
        "ref": "Annex I, Part I, Abs. 2 lit. g",
        "titel": "Sicherheitsrelevantes Logging & Monitoring",
        "beschreibung": (
            "Produkte müssen sicherheitsrelevante interne Aktivitäten aufzeichnen "
            "und/oder überwachen können."
        ),
        "hinweise": (
            "Audit-Logs für Authentifizierung, Autorisierung, Konfigurationsänderungen; "
            "Manipulationsschutz der Logs; "
            "Definierter Aufbewahrungszeitraum; "
            "SIEM-Integration (wo anwendbar)."
        ),
        "gewichtung": 2,
    },
    {
        "id": "AI1-09",
        "kapitel": "AI1",
        "ref": "Annex I, Part I, Abs. 2 lit. h",
        "titel": "Updatefähigkeit – Sicherheitsupdates ermöglichen",
        "beschreibung": (
            "Produkte müssen so gestaltet sein, dass Schwachstellen durch "
            "Sicherheitsupdates behoben werden können."
        ),
        "hinweise": (
            "OTA-Update-Mechanismus mit Signaturprüfung; "
            "Automatische Sicherheitsupdates als Standardeinstellung (opt-out möglich); "
            "Trennung von Sicherheits- und Funktionsupdates; "
            "Update-Kanal-Authentifizierung."
        ),
        "gewichtung": 3,
    },
    {
        "id": "AI1-10",
        "kapitel": "AI1",
        "ref": "Annex I, Part I, Abs. 2 lit. i",
        "titel": "Datenschutz by Design",
        "beschreibung": (
            "Produkte müssen mit datenschutzfreundlichen Voreinstellungen und "
            "technischen Maßnahmen zum Schutz personenbezogener Daten entwickelt werden."
        ),
        "hinweise": (
            "Datenminimierung (nur notwendige Daten erheben); "
            "Privacy by Default als Konfigurationsstandard; "
            "Kompatibilität mit DSGVO-Anforderungen (Art. 25 DSGVO); "
            "Dokumentation der Datenflüsse."
        ),
        "gewichtung": 2,
    },
    # ── Annex I Teil II: Schwachstellenhandhabung ─────────────────────────────
    {
        "id": "AI2-01",
        "kapitel": "AI2",
        "ref": "Annex I, Part II, Abs. 1",
        "titel": "Schwachstellenidentifikation und -verfolgung",
        "beschreibung": (
            "Hersteller müssen Schwachstellen in Produkten und Komponenten "
            "systematisch identifizieren, dokumentieren und verfolgen."
        ),
        "hinweise": (
            "Schwachstellen-Tracking-System (Issue Tracker, CVE-Datenbank); "
            "Regelmäßige Scans und Penetrationstests; "
            "Bug-Bounty-Programm oder verantwortungsvolle Offenlegung; "
            "SLA für Schwachstellenbehebung definieren."
        ),
        "gewichtung": 3,
    },
    {
        "id": "AI2-02",
        "kapitel": "AI2",
        "ref": "Annex I, Part II, Abs. 2",
        "titel": "SBOM – Software Bill of Materials",
        "beschreibung": (
            "Hersteller müssen eine maschinenlesbare Stückliste aller Softwarekomponenten "
            "(SBOM) erstellen und pflegen, die mindestens alle Top-Level-Abhängigkeiten enthält."
        ),
        "hinweise": (
            "SBOM in standardisiertem Format (CycloneDX, SPDX oder SWID); "
            "Automatische SBOM-Generierung im Build-Prozess (z.B. Syft, CycloneDX-CLI); "
            "Regelmäßige Aktualisierung bei Komponentenänderungen; "
            "Nicht zwingend öffentlich, aber auf Anfrage der Marktüberwachungsbehörde bereitstellen."
        ),
        "gewichtung": 3,
    },
    {
        "id": "AI2-03",
        "kapitel": "AI2",
        "ref": "Annex I, Part II, Abs. 3",
        "titel": "Schnelle Behebung von Schwachstellen – Security Patches",
        "beschreibung": (
            "Hersteller müssen Schwachstellen unverzüglich, auch durch Bereitstellung "
            "von Sicherheitsupdates, beheben."
        ),
        "hinweise": (
            "Definierter Patch-Prozess mit klaren Eskalationspfaden; "
            "SLA je nach CVSS-Score (z.B. Kritisch: 24h, Hoch: 7d, Mittel: 30d); "
            "Kostenfreie Sicherheitsupdates während des Support-Zeitraums; "
            "Separater Sicherheits-Update-Kanal."
        ),
        "gewichtung": 3,
    },
    {
        "id": "AI2-04",
        "kapitel": "AI2",
        "ref": "Annex I, Part II, Abs. 4",
        "titel": "Regelmäßige Sicherheitstests und -überprüfungen",
        "beschreibung": (
            "Hersteller müssen regelmäßige Tests und Überprüfungen der "
            "Sicherheit ihrer Produkte durchführen."
        ),
        "hinweise": (
            "Jährliche Penetrationstests durch unabhängige Dritte; "
            "Automatisierte SAST/DAST in der CI/CD-Pipeline; "
            "Fuzz-Testing für kritische Schnittstellen; "
            "Ergebnisse dokumentieren und Maßnahmen nachverfolgen."
        ),
        "gewichtung": 2,
    },
    {
        "id": "AI2-05",
        "kapitel": "AI2",
        "ref": "Annex I, Part II, Abs. 5",
        "titel": "Koordinierte Schwachstellenoffenlegung (CVD-Policy)",
        "beschreibung": (
            "Hersteller müssen eine Policy für die koordinierte Offenlegung von "
            "Schwachstellen (Coordinated Vulnerability Disclosure) einrichten und durchsetzen."
        ),
        "hinweise": (
            "Öffentliche CVD-Policy (z.B. security.txt auf der Website); "
            "Dedizierter Kontaktweg für Sicherheitsforscher; "
            "Klare Zeitpläne für Reaktion und Behebung; "
            "Einhaltung von ISO/IEC 29147 und ISO/IEC 30111."
        ),
        "gewichtung": 2,
    },
    {
        "id": "AI2-06",
        "kapitel": "AI2",
        "ref": "Annex I, Part II, Abs. 6",
        "titel": "Öffentliche Offenlegung behobener Schwachstellen",
        "beschreibung": (
            "Nach Bereitstellung eines Sicherheitsupdates müssen Informationen über "
            "die behobene Schwachstelle öffentlich zugänglich gemacht werden."
        ),
        "hinweise": (
            "Security Advisories / CVE-Einträge bei ENISA oder nationalen Stellen; "
            "Mindestangaben: Beschreibung, betroffene Versionen, CVSS-Score, Patch-Anleitung; "
            "Responsible Disclosure: Veröffentlichung erst nach Patch-Verfügbarkeit."
        ),
        "gewichtung": 2,
    },
    {
        "id": "AI2-07",
        "kapitel": "AI2",
        "ref": "Annex I, Part II, Abs. 7",
        "titel": "Mechanismen für sichere Software-Updates",
        "beschreibung": (
            "Hersteller müssen technische Mechanismen für die sichere Verteilung "
            "und Installation von Software-Updates bereitstellen."
        ),
        "hinweise": (
            "Signierte Update-Pakete mit Zertifikatsvalidierung; "
            "Rollback-Funktion bei fehlgeschlagenem Update; "
            "Integrity-Check vor Installation; "
            "Automatische Updates als Standard (Annex I, Part I, Abs. 2 lit. i)."
        ),
        "gewichtung": 3,
    },
    {
        "id": "AI2-08",
        "kapitel": "AI2",
        "ref": "Annex I, Part II, Abs. 8",
        "titel": "Informationsaustausch zu Schwachstellen in Drittkomponenten",
        "beschreibung": (
            "Hersteller müssen den Informationsaustausch über Schwachstellen "
            "in verwendeten Drittkomponenten fördern."
        ),
        "hinweise": (
            "Aktive Teilnahme an ISAC/CERT-Meldeplattformen; "
            "Regelmäßiger Abgleich mit NVD, OSV, VEX-Feeds; "
            "Interne Prozesse für Drittkomponenten-Monitoring; "
            "Benachrichtigung nachgelagerter Zulieferer bei bekannten Schwachstellen."
        ),
        "gewichtung": 2,
    },
    # ── Art. 13 – Herstellerpflichten ─────────────────────────────────────────
    {
        "id": "ART13-01",
        "kapitel": "ART13",
        "ref": "Art. 13 Abs. 1",
        "titel": "Durchführung einer Cybersicherheits-Risikoabschätzung",
        "beschreibung": (
            "Hersteller müssen eine Cybersicherheits-Risikoabschätzung für ihr Produkt "
            "durchführen und dokumentieren. Diese informiert alle Entwicklungsphasen."
        ),
        "hinweise": (
            "Risikoabschätzung nach ISO/IEC 27005 oder IEC 62443-3-2; "
            "TARA (Threat Analysis & Risk Assessment) gemäß ISO/SAE 21434 für vernetzte Produkte; "
            "Dokumentation der identifizierten Bedrohungen, Schwachstellen und Maßnahmen; "
            "Regelmäßige Aktualisierung bei wesentlichen Produktänderungen."
        ),
        "gewichtung": 3,
    },
    {
        "id": "ART13-02",
        "kapitel": "ART13",
        "ref": "Art. 13 Abs. 2",
        "titel": "Technische Dokumentation und EU-Konformitätserklärung",
        "beschreibung": (
            "Hersteller müssen eine technische Dokumentation erstellen und "
            "eine EU-Konformitätserklärung ausstellen (CE-Kennzeichnung)."
        ),
        "hinweise": (
            "Technische Dokumentation gemäß Annex V: Produktbeschreibung, Risikoabschätzung, "
            "angewandte Normen, Konformitätsbewertungsverfahren, SBOM, Testberichte; "
            "Aufbewahrungspflicht: 10 Jahre nach Markteinführung oder Support-Ende; "
            "EU-Konformitätserklärung nach Annex VI."
        ),
        "gewichtung": 3,
    },
    {
        "id": "ART13-03",
        "kapitel": "ART13",
        "ref": "Art. 13 Abs. 8",
        "titel": "Definition und Kommunikation des Support-Zeitraums",
        "beschreibung": (
            "Hersteller müssen den Support-Zeitraum festlegen und kommunizieren. "
            "Sicherheitsupdates müssen mindestens 5 Jahre oder die erwartete "
            "Produktlebensdauer lang bereitgestellt werden."
        ),
        "hinweise": (
            "Support-Zeitraum muss mindestens der erwarteten Nutzungsdauer entsprechen; "
            "Mindestens 5 Jahre (sofern Nutzungsdauer nicht kürzer); "
            "Klare Kommunikation an Nutzer über Ende des Support-Zeitraums; "
            "End-of-Life-Policy veröffentlichen."
        ),
        "gewichtung": 3,
    },
    {
        "id": "ART13-04",
        "kapitel": "ART13",
        "ref": "Art. 13 Abs. 3",
        "titel": "Sicherheitshinweise und Benutzerinformationen",
        "beschreibung": (
            "Hersteller müssen klare, verständliche Sicherheitshinweise und "
            "Bedienungsanleitungen in der Sprache des Markts bereitstellen."
        ),
        "hinweise": (
            "Benutzerhandbuch mit Sicherheitskonfigurationsanleitungen; "
            "Hinweise zur sicheren Installation und Konfiguration; "
            "Kontaktdaten für Sicherheitsmeldungen; "
            "Informationen über bekannte Einschränkungen der Cybersicherheit."
        ),
        "gewichtung": 2,
    },
    {
        "id": "ART13-05",
        "kapitel": "ART13",
        "ref": "Art. 13 Abs. 5",
        "titel": "Marktüberwachungs-Kooperation",
        "beschreibung": (
            "Hersteller müssen mit Marktüberwachungsbehörden kooperieren und auf "
            "begründete Anfragen alle notwendigen Informationen bereitstellen."
        ),
        "hinweise": (
            "Prozess für Anfragen der Marktüberwachungsbehörde (BSI in Deutschland); "
            "Bereitstellung technischer Dokumentation auf Anfrage (binnen 10 Tagen); "
            "Dokumentation der Kommunikation mit Behörden; "
            "Benennung eines Ansprechpartners für Behördenkontakte."
        ),
        "gewichtung": 2,
    },
    # ── Art. 14 – Meldepflichten ──────────────────────────────────────────────
    {
        "id": "ART14-01",
        "kapitel": "ART14",
        "ref": "Art. 14 Abs. 1 (gilt ab 11.09.2026)",
        "titel": "Meldung aktiv ausgenutzter Schwachstellen an ENISA",
        "beschreibung": (
            "Hersteller müssen ENISA (und ggf. nationale CSIRT) innerhalb von 24 Stunden "
            "informieren, sobald eine aktiv ausgenutzte Schwachstelle bekannt wird."
        ),
        "hinweise": (
            "Vorfrühwarnung (Early Warning) innerhalb 24h nach Kenntnisnahme; "
            "Vollständiger Bericht innerhalb 72h; "
            "Abschlussbericht innerhalb 14 Tagen; "
            "Meldekanalinrichtung: ENISA Single Reporting Platform; "
            "Gilt ab 11. September 2026."
        ),
        "gewichtung": 3,
    },
    {
        "id": "ART14-02",
        "kapitel": "ART14",
        "ref": "Art. 14 Abs. 2 (gilt ab 11.09.2026)",
        "titel": "Meldung schwerwiegender Cybersicherheitsvorfälle",
        "beschreibung": (
            "Hersteller müssen schwerwiegende Cybersicherheitsvorfälle, die die "
            "Sicherheit ihres Produkts beeinträchtigen, unverzüglich melden."
        ),
        "hinweise": (
            "Incident-Response-Plan mit definierten Eskalationspfaden; "
            "Klare Kriterien für die Einstufung als 'schwerwiegend'; "
            "Enge Abstimmung mit NIS2-Meldepflichten (sofern anwendbar); "
            "Meldeprozess dokumentieren und regelmäßig testen."
        ),
        "gewichtung": 3,
    },
    {
        "id": "ART14-03",
        "kapitel": "ART14",
        "ref": "Art. 14 Abs. 3",
        "titel": "Kooperation mit CSIRT und Behörden",
        "beschreibung": (
            "Hersteller müssen mit nationalen CSIRTs und zuständigen Behörden "
            "bei der Vorfallsbearbeitung kooperieren."
        ),
        "hinweise": (
            "Kontakte zu BSI-CERT (Deutschland) und ENISA aufbauen; "
            "Benennung eines Security-Ansprechpartners (24/7 erreichbar); "
            "Übergabe von technischen Details und Kompromittierungsindikatoren (IoC); "
            "Regelmäßige Teilnahme an Cybersicherheitsübungen."
        ),
        "gewichtung": 2,
    },
    # ── Implementierungsbereitschaft ──────────────────────────────────────────
    {
        "id": "IMPL-01",
        "kapitel": "IMPL",
        "ref": "Art. 13 Abs. 1 + Erwägungsgrund 34",
        "titel": "Governance und Verantwortlichkeiten für Cybersicherheit",
        "beschreibung": (
            "Im Unternehmen müssen klare Verantwortlichkeiten und Governance-Strukturen "
            "für die CRA-Compliance etabliert sein."
        ),
        "hinweise": (
            "Benennung eines CRA-Verantwortlichen (z.B. CISO, Security Lead); "
            "Management-Commitment zur Cybersicherheit; "
            "Budget und Ressourcen für Sicherheitsmaßnahmen; "
            "Regelmäßige Berichterstattung an Geschäftsführung."
        ),
        "gewichtung": 2,
    },
    {
        "id": "IMPL-02",
        "kapitel": "IMPL",
        "ref": "Art. 13 Abs. 1 + Annex I, Part II",
        "titel": "Sicherer Entwicklungsprozess (Secure SDLC)",
        "beschreibung": (
            "Im Entwicklungsprozess müssen Cybersicherheitsanforderungen "
            "systematisch berücksichtigt werden (Security by Design)."
        ),
        "hinweise": (
            "Security Gates im SDLC (Requirements → Design → Code → Test → Release); "
            "Threat Modeling als fester Bestandteil der Design-Phase; "
            "Security Code Reviews und automatisierte Prüfungen (SAST/DAST); "
            "Security-Schulungen für Entwickler."
        ),
        "gewichtung": 3,
    },
    {
        "id": "IMPL-03",
        "kapitel": "IMPL",
        "ref": "Art. 13 Abs. 1 + Erwägungsgrund 37",
        "titel": "Lieferkettensicherheit (Supply Chain Security)",
        "beschreibung": (
            "Hersteller müssen die Sicherheit ihrer Lieferkette, insbesondere "
            "von Drittkomponenten und Open-Source-Software, gewährleisten."
        ),
        "hinweise": (
            "Sicherheitsbewertung von Zulieferern und Softwarelieferanten; "
            "Vertragliche Cybersicherheitsanforderungen an Lieferanten; "
            "SBOM-Anforderung an Zulieferer; "
            "Monitoring von Drittkomponenten auf bekannte Schwachstellen."
        ),
        "gewichtung": 2,
    },
    {
        "id": "IMPL-04",
        "kapitel": "IMPL",
        "ref": "Art. 13 Abs. 1 + Annex I",
        "titel": "Produktklassifizierung und Konformitätsbewertungsweg",
        "beschreibung": (
            "Das Unternehmen muss seine Produkte korrekt klassifizieren "
            "(Default / Important I+II / Critical) und den entsprechenden "
            "Konformitätsbewertungsweg identifizieren."
        ),
        "hinweise": (
            "Mapping aller Produkte gegen Annex III (Important) und Annex IV (Critical); "
            "Dokumentation der Klassifizierungsentscheidung mit Begründung; "
            "Bei Important Class II / Critical: frühzeitige Kontaktaufnahme mit "
            "Konformitätsbewertungsstellen; "
            "Überprüfung bei wesentlichen Produktänderungen."
        ),
        "gewichtung": 3,
    },
    {
        "id": "IMPL-05",
        "kapitel": "IMPL",
        "ref": "Art. 13 Abs. 2 + Annex V",
        "titel": "Technische Dokumentation – Lebenszyklus und Archivierung",
        "beschreibung": (
            "Alle sicherheitsrelevanten technischen Dokumente müssen vollständig "
            "und für mindestens 10 Jahre nach Markteinführung verfügbar sein."
        ),
        "hinweise": (
            "Dokumentenmanagement-System mit Versionierung; "
            "Archivierung: Risikoabschätzung, SBOM, Testberichte, Konformitätserklärung; "
            "Regelmäßige Überprüfung der Vollständigkeit; "
            "Zugriffsschutz und Backup-Konzept für technische Dokumentation."
        ),
        "gewichtung": 2,
    },
    {
        "id": "IMPL-06",
        "kapitel": "IMPL",
        "ref": "Erwägungsgründe + Art. 13",
        "titel": "Schulung und Awareness – Cybersicherheitskultur",
        "beschreibung": (
            "Mitarbeiter in Entwicklung und Betrieb müssen über die CRA-Anforderungen "
            "und relevante Cybersicherheitspraktiken geschult sein."
        ),
        "hinweise": (
            "Jährliche Pflichtschulung zu Cybersicherheit und CRA; "
            "Spezifische Trainings für Entwickler (Secure Coding), Operations (Incident Response); "
            "Phishing-Simulationen und Security-Awareness-Kampagnen; "
            "Dokumentation der Schulungsnachweise."
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


def load_merged_anforderungen(db_path: "Path | None" = None) -> list[dict[str, Any]]:
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
    return sorted(base.values(), key=lambda r: (kap_order.get(r.get("kapitel", "IMPL"), 99), r["id"]))


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
