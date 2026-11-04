"""G3-1 + G6-5 — Sprach-Linter: Jura-Sperre + Slogans + AI-Stilwörter."""
from __future__ import annotations

import re
from typing import Any


# Jura-Sperre: Rechtsbegriffe, die ein technischer SV NICHT verwenden darf (§ 407a — Beurteilung dem Richter überlassen).
JURA_SPERRE: dict[str, str] = {
    "vertragsbruch": "Abweichung vom geschuldeten Leistungsumfang",
    "vertraglich geschuldet": "Aus informationstechnischer Sicht erwartet",
    "schuldhaft": "aus informationstechnischer Sicht zurechenbar",
    "arglistig": "(Würdigung dem Gericht vorbehalten)",
    "grob fahrlässig": "(Würdigung dem Gericht vorbehalten)",
    "fahrlässig": "(Würdigung dem Gericht vorbehalten)",
    "mangelhaft im rechtssinne": "Abweichung vom Stand der Technik",
    "rechtswidrig": "(rechtliche Würdigung dem Gericht vorbehalten)",
    "unzulässig": "aus informationstechnischer Sicht nicht zulässig",
    "verschulden": "(Würdigung dem Gericht vorbehalten)",
    "haftbar": "(rechtliche Würdigung dem Gericht vorbehalten)",
    "schuldig": "(Würdigung dem Gericht vorbehalten)",
}

# Slogans + Marketing-Phrasen
SLOGANS: dict[str, str] = {
    "revolutionär": "(Werbesprache — bitte sachlich umformulieren)",
    "bahnbrechend": "(Werbesprache — bitte sachlich umformulieren)",
    "naturgemäß": "(unscharf — bitte konkretisieren)",
    "selbstredend": "(unscharf — bitte begründen)",
    "selbstverständlich": "(unscharf — bitte begründen)",
    "natürlich": "(unscharf — bitte konkretisieren oder weglassen)",
    "offensichtlich": "(unscharf — bitte konkret belegen)",
    "klar": "(unscharf — bitte konkret belegen)",
    "eindeutig": "(unscharf — bitte konkret belegen)",
    "höchste qualität": "(Werbesprache)",
    "state-of-the-art": "Stand der Technik",
}

# Typische AI-Stilwörter / Floskeln
AI_PHRASEN: dict[str, str] = {
    "es ist wichtig zu beachten": "(Floskel — bitte direkt formulieren oder weglassen)",
    "in der heutigen schnelllebigen welt": "(Floskel — bitte streichen)",
    "wie bereits erwähnt": "(redundant — direkt formulieren)",
    "wie wir gesehen haben": "(Floskel — direkt formulieren)",
    "insgesamt lässt sich sagen": "(Floskel — direkt zur Schlussfolgerung)",
    "es lässt sich festhalten": "(Floskel — direkt formulieren)",
    "im rahmen dieser": "(Floskel — bitte konkretisieren)",
    "darüber hinaus": "(Füllwort — prüfen ob nötig)",
    "letzten endes": "(Floskel — direkt formulieren)",
    "im wesentlichen": "(Floskel — direkt formulieren)",
    "tiefgreifend": "(Adjektiv-Inflation — bitte streichen)",
    "umfassend": "(Adjektiv-Inflation — bitte streichen oder belegen)",
}

# Wertende Begriffe für Kap. IV (Befunderhebung MUSS tatsachen-only sein)
KAP_IV_WERTUNGEN: dict[str, str] = {
    "mangelhaft": "(Bewertung — gehört nach Kap. V)",
    "fehlerhaft": "(Bewertung — gehört nach Kap. V)",
    "unzureichend": "(Bewertung — gehört nach Kap. V)",
    "unsauber": "(Bewertung — gehört nach Kap. V)",
    "unprofessionell": "(Bewertung — gehört nach Kap. V)",
    "schlecht programmiert": "(Bewertung — gehört nach Kap. V)",
    "katastrophal": "(Bewertung — gehört nach Kap. V)",
    "skandalös": "(Bewertung — gehört nach Kap. V)",
    "nicht akzeptabel": "(Bewertung — gehört nach Kap. V)",
}


def _findall(text: str, dictionary: dict[str, str], level: str, kind: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    lower = text.lower()
    for term, vorschlag in dictionary.items():
        idx = 0
        while True:
            pos = lower.find(term.lower(), idx)
            if pos < 0:
                break
            out.append({
                "level": level,
                "kind": kind,
                "term": term,
                "vorschlag": vorschlag,
                "pos_start": pos,
                "pos_end": pos + len(term),
            })
            idx = pos + len(term)
    return out


def lint(text: str, context: str = "gerichts", kapitel: str | None = None) -> list[dict[str, Any]]:
    """Prüft Text nach Sprach-Regeln.

    context: 'gerichts' (streng) | 'audit' (mild — weniger Jura-Sperre)
    kapitel: optional 'IV' (Befunderhebung — extra streng auf Wertungen)
    """
    text = text or ""
    hints: list[dict[str, Any]] = []

    # Jura-Sperre: in Gerichtsgutachten generell aktiv, in Audit-Bericht nur als Hinweis
    jura_level = "warn" if context == "gerichts" else "info"
    hints.extend(_findall(text, JURA_SPERRE, jura_level, "jura-sperre"))

    # Slogans & AI-Phrasen — immer
    hints.extend(_findall(text, SLOGANS, "info", "slogan"))
    hints.extend(_findall(text, AI_PHRASEN, "info", "ai-phrase"))

    # Kap. IV Wertungen: nur wenn ausdrücklich Kap. IV oder Befund-Kontext
    if kapitel == "IV":
        hints.extend(_findall(text, KAP_IV_WERTUNGEN, "warn", "wertung-in-kap-iv"))

    # Sortiere nach Position
    hints.sort(key=lambda h: h["pos_start"])
    return hints


def lint_befund(text: str, context: str = "gerichts") -> list[dict[str, Any]]:
    """Convenience: für Befund-Editor (Kap. IV) — extra-strikt."""
    return lint(text, context=context, kapitel="IV")


def lint_beurteilung(text: str, context: str = "gerichts") -> list[dict[str, Any]]:
    """Convenience: für Beurteilungs-Editor (Kap. V) — Jura-Sperre aktiv."""
    return lint(text, context=context)
