"""Safe JSON import helpers for manual answer pasting.

Risk #195 mitigation goals:
- bound input size
- reject non-JSON / wrong root types
- basic schema/type validation utilities
- audit logging for parse failures (without leaking content)
"""

from __future__ import annotations

import json
import re
from typing import Any

from shared.audit import audit_event
from shared.redaction import redact_secrets
from security_utils import sanitize_untrusted_text


MAX_JSON_CHARS_DEFAULT = 2 * 1024 * 1024  # 2MB


def safe_read_json_file(path: str | Any, *, context: str, max_bytes: int = 2 * 1024 * 1024) -> Any:
    """Read JSON file with size bounds and safe parsing."""
    from pathlib import Path

    p = Path(path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(str(p))
    if p.stat().st_size > max_bytes:
        audit_event(
            "json.import",
            module="json_io",
            outcome="fail",
            details={"context": context, "reason": "file_too_large", "path": str(p), "bytes": int(p.stat().st_size)},
        )
        raise ValueError(f"JSON-Datei zu groß: {p.stat().st_size} Bytes (max {max_bytes})")
    raw = p.read_text(encoding="utf-8", errors="replace")
    return safe_json_loads(raw, context=context, max_chars=max_bytes)


def _strip_code_fences(text: str) -> str:
    t = (text or "").strip()
    # remove ```json ... ``` wrappers
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"```\s*$", "", t)
    return t.strip()


def _escape_innere_anfuehrungszeichen(text: str) -> tuple[str, int]:
    """Unescapte ``"`` **innerhalb** einer Zeichenkette escapen (#2006).

    Der gemeldete Fall: Das Modell schreibt ``wird als „Wahrscheinlich"
    eingestuft`` — typografisch geöffnet, mit einem **geraden**
    Anführungszeichen geschlossen. Innerhalb eines JSON-Strings beendet das die
    Zeichenkette, und alles danach ist Syntaxmüll. Eine fertige Bewertung von
    2300 Zeichen ging an einem Zeichen verloren.

    **Das Kriterium ist präzise, nicht geraten:** Ein ``"`` beendet die
    Zeichenkette nur, wenn das nächste Zeichen nach Leerraum ``,``, ``}``,
    ``]``, ``:`` oder das Ende ist. Sonst steht es mitten im Text und wird
    escapt.

    **Die Grenze der Heuristik, offen benannt:** Ein Zitat, dem ein Komma
    folgt (``… sagte "ja", dann …``), ist von einem Zeichenkettenende nicht zu
    unterscheiden. Dieser Fall bleibt unauflösbar — die Reparatur macht ihn
    nicht schlimmer, sie löst ihn nur nicht.
    """
    aus: list[str] = []
    i = 0
    im_string = False
    repariert = 0
    n = len(text)
    while i < n:
        c = text[i]
        if not im_string:
            aus.append(c)
            if c == '"':
                im_string = True
            i += 1
            continue
        if c == "\\":
            aus.append(text[i:i + 2])
            i += 2
            continue
        if c == '"':
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            naechstes = text[j] if j < n else ""
            if naechstes in (",", "}", "]", ":", ""):
                aus.append('"')
                im_string = False
            else:
                aus.append('\\"')
                repariert += 1
            i += 1
            continue
        aus.append(c)
        i += 1
    return "".join(aus), repariert


def _schliesse_abgeschnittenes(text: str) -> tuple[str, bool]:
    """Abgeschnittenes JSON schließen (Token-Limit).

    Übernommen aus ``server/services/anforderung_prompt._repair_truncated_json``
    (#1419) — dort lag die Reparatur nur für **einen** Pfad, während die
    Risikobewertung über ``safe_json_loads`` ging und gar keine hatte.
    """
    t = text.rstrip().rstrip(",")
    verändert = t != text.rstrip()
    if len(re.findall(r'(?<!\\)"', t)) % 2 == 1:
        t += '"'
        verändert = True
    offen_eckig = max(0, t.count("[") - t.count("]"))
    offen_rund = max(0, t.count("{") - t.count("}"))
    if offen_eckig or offen_rund:
        t += "]" * offen_eckig + "}" * offen_rund
        verändert = True
    neu_t = re.sub(r",\s*([}\]])", r"\1", t)
    if neu_t != t:
        t = neu_t
        verändert = True
    return t, verändert


def repariere(text: str) -> tuple[str, list[str]]:
    """Beide bekannten Beschädigungen einer KI-JSON-Antwort beheben.

    Gibt den reparierten Text und die Liste der Eingriffe zurück. **Die Liste
    ist der Punkt:** Eine Reparatur, die wie ein glatter Treffer aussieht, ist
    eine Lüge — der Aufrufer muss erfahren, dass am Text gearbeitet wurde, und
    der Prüfhinweis am Entwurf (#1862) soll es sagen.
    """
    berichte: list[str] = []
    t = text
    t, anzahl = _escape_innere_anfuehrungszeichen(t)
    if anzahl:
        berichte.append(
            f"{anzahl} unescaptes Anführungszeichen in einer Zeichenkette escapt")
    t2, abgeschnitten = _schliesse_abgeschnittenes(t)
    if abgeschnitten:
        t = t2
        berichte.append("abgeschnittene Antwort geschlossen")
    return t, berichte


def lade_mit_bericht(
    raw: str,
    *,
    context: str,
    max_chars: int = MAX_JSON_CHARS_DEFAULT,
) -> tuple[Any, list[str]]:
    """Wie :func:`safe_json_loads`, aber mit Reparatur **und** Bericht (#2006).

    Erst der glatte Versuch — eine gültige Antwort wird nie angefasst. Nur bei
    einem Parse-Fehler wird repariert, und was dabei geschah, kommt mit zurück.
    """
    try:
        return safe_json_loads(raw, context=context, max_chars=max_chars), []
    except ValueError:
        pass
    text = _strip_code_fences(raw or "")
    # **Nicht vorher zuschneiden.** Der erste Entwurf schnitt von der ersten
    # ``{`` bis zur letzten ``}`` — bei einer **abgeschnittenen** Antwort ist
    # die letzte ``}`` die eines inneren Objekts, und der Schnitt warf den Rest
    # weg. Der Test mit der mitten im Satz endenden Begründung hat das gefunden.
    kandidaten: list[str] = [text]
    i, j = text.find("{"), text.rfind("}")
    if i != -1 and j > i and text[i:j + 1] != text:
        kandidaten.append(text[i:j + 1])

    for k in kandidaten:
        # **Nur Objekte reparieren.** Dieselbe Schranke wie in
        # `_repair_truncated_json` (#1419), und sie ist nötig: ``[[[`` wird vom
        # Klammerausgleich zu ``[[[]]]`` — gültiges JSON ohne jeden Inhalt.
        # Eine Reparatur, die aus Müll eine gültige leere Struktur macht, ist
        # schlimmer als ein Fehler: Der Aufrufer rechnet damit weiter.
        if k.lstrip()[:1] != "{":
            continue
        kandidat, berichte = repariere(k)
        if not berichte:
            continue
        try:
            wert = safe_json_loads(kandidat, context=f"{context}:repariert",
                                   max_chars=max_chars)
        except ValueError:
            continue
        if not isinstance(wert, dict):
            continue
        break
    else:
        # Nichts zu reparieren oder nichts Brauchbares heraus → der
        # ursprüngliche Fehler ist der richtige.
        return safe_json_loads(raw, context=context, max_chars=max_chars), []
    audit_event("json.import", module="json_io", outcome="repaired",
                details={"context": context, "reparaturen": berichte})
    return wert, berichte


def safe_json_loads(
    raw: str,
    *,
    context: str,
    max_chars: int = MAX_JSON_CHARS_DEFAULT,
) -> Any:
    """Parse JSON from untrusted string with size bounds and audit logging."""
    if raw is None:
        raise ValueError("JSON fehlt")
    if len(raw) > max_chars:
        audit_event(
            "json.import",
            module="json_io",
            outcome="fail",
            details={"context": context, "reason": "too_large", "chars": len(raw)},
        )
        raise ValueError(f"JSON zu groß: {len(raw)} Zeichen (max {max_chars})")

    text = _strip_code_fences(raw)
    try:
        return json.loads(text)
    except Exception as exc:
        # Log only a redacted/truncated excerpt
        excerpt = sanitize_untrusted_text(redact_secrets(text), max_len=300)
        audit_event(
            "json.import",
            module="json_io",
            outcome="fail",
            details={"context": context, "reason": "parse_error", "error": str(exc), "excerpt": excerpt},
        )
        raise ValueError(f"JSON Parsing fehlgeschlagen: {exc}") from exc


def require_object(v: Any, *, what: str = "JSON") -> dict[str, Any]:
    if not isinstance(v, dict):
        raise ValueError(f"{what} muss ein JSON-Objekt sein")
    return v


def require_array(v: Any, *, what: str = "JSON") -> list[Any]:
    if not isinstance(v, list):
        raise ValueError(f"{what} muss ein JSON-Array sein")
    return v
