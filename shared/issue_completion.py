"""Gemeinsame Logik für die automatische Vervollständigung von Anforderungen,
deren verknüpftes Issue erfolgreich gelöst wurde (#833).

Wird von CRA, NIS2 und AI-Act gleichermaßen genutzt. Diese Module besitzen
kein "resolved"-Flag pro Anforderung; stattdessen wird eine vollständig
bearbeitete Anforderung dadurch sichtbar gemacht, dass ihr Score auf den
Maximalwert (5 = "vollständig erfüllt") gesetzt und eine Notiz an den
Kommentar angehängt wird.

Alle Funktionen hier sind rein (keine Netzwerk-/DB-Zugriffe). Der Lösungsstatus
wird ausschließlich aus dem PERSISTIERTEN ``linked_issues``-Snapshot gelesen
(Felder ``state``/``state_reason``).
"""

from __future__ import annotations

from typing import Any

from shared.issue_sync import is_successfully_resolved

#: Maximaler Score = "vollständig erfüllt".
COMPLETION_SCORE = 5

#: Stabiler Marker, an dem eine bereits gesetzte Auto-Notiz erkannt wird.
COMPLETION_MARKER = "✅ Vollständig bearbeitet – gelöst durch"

#: #1526/#1520: Stabiler Marker „Neubewertung erforderlich". Wird gesetzt, sobald sich
#: ein verknüpftes Issue **schließt** (statt der nicht-compliance-konformen Auto-Erfüllung)
#: oder **wieder öffnet**. Die Bewertung (Score) wird dabei NICHT automatisch geändert —
#: ein Mensch muss neu bewerten.
NEEDS_REASSESS_MARKER = "⚠️ Neubewertung erforderlich – verknüpftes Issue geändert"


def _link_get(link: Any, attr: str, default: Any = None) -> Any:
    """Liest ein Feld aus einem Link (Objekt mit Attribut oder dict)."""
    if isinstance(link, dict):
        return link.get(attr, default)
    return getattr(link, attr, default)


def first_resolved_link(links: list[Any]) -> Any | None:
    """Liefert den ersten Link, dessen (persistierter) Status als erfolgreich
    gelöst gilt – oder ``None``.

    Nutzt ``is_successfully_resolved`` auf ``state``/``state_reason`` des
    persistierten Snapshots. Es werden KEINE Netzwerkaufrufe gemacht.
    """
    for li in links or []:
        state = str(_link_get(li, "state", "") or "")
        state_reason = str(_link_get(li, "state_reason", "") or "")
        if is_successfully_resolved(state=state, state_reason=state_reason, labels=[]):
            return li
    return None


def completion_note(link: Any, previous_score: int) -> str:
    """Erzeugt die Auto-Notiz für eine vollständig bearbeitete Anforderung.

    GitHub (mit Nummer): ``… – gelöst durch #<number>``;
    GitLab / ohne Nummer: ``… – gelöst durch <url>``.
    Der vorherige Score wird zur Nachvollziehbarkeit angehängt.
    """
    number = _link_get(link, "issue_number", None)
    url = str(_link_get(link, "url", "") or "").strip()
    if number:
        ref = f"#{int(number)}"
    else:
        ref = url or "(Issue)"
    return f"{COMPLETION_MARKER} {ref} (vorheriger Score: {int(previous_score)})"


def already_completed(kommentar: str) -> bool:
    """True, wenn der Kommentar bereits eine Auto-Notiz enthält."""
    return COMPLETION_MARKER in str(kommentar or "")


def is_assessed(bewertung: int, kommentar: str) -> bool:
    """True, wenn die Anforderung bereits bewertet wurde.

    Kriterium: Score > 0 ODER ein nicht-leerer Kommentar – wobei eine zuvor
    angehängte Auto-Notiz ignoriert wird (sie zählt nicht als manuelle
    Bewertung).
    """
    try:
        score = int(bewertung or 0)
    except (TypeError, ValueError):
        score = 0
    if score > 0:
        return True
    rest = _strip_completion_note(kommentar)
    return bool(rest.strip())


def _strip_completion_note(kommentar: str) -> str:
    """Entfernt zuvor angehängte Auto-Notiz-Zeilen (Completion ODER Reassessment)
    aus dem Kommentar."""
    text = str(kommentar or "")
    lines = [ln for ln in text.splitlines()
             if COMPLETION_MARKER not in ln and NEEDS_REASSESS_MARKER not in ln]
    return "\n".join(lines).strip()


def merge_completion_note(kommentar: str, note: str) -> str:
    """Hängt die Auto-Notiz idempotent an den Kommentar an.

    Eine bereits vorhandene Auto-Notiz wird zuvor entfernt, sodass mehrfaches
    Anwenden den Kommentar nicht aufbläht und der vorherige Score korrekt
    bleibt.
    """
    base = _strip_completion_note(kommentar)
    note = str(note or "").strip()
    if not note:
        return base
    if base:
        return f"{base}\n\n{note}"
    return note


# ── #1526/#1520: „Neubewertung erforderlich" (score-neutral) ────────────────────

def needs_reassessment_note(link: Any, reason: str = "geschlossen") -> str:
    """Erzeugt die „Neubewertung erforderlich"-Notiz mit Issue-Referenz."""
    number = _link_get(link, "issue_number", None)
    url = str(_link_get(link, "url", "") or "").strip()
    ref = f"#{int(number)}" if number else (url or "(Issue)")
    return f"{NEEDS_REASSESS_MARKER} ({ref}, {reason})"


def already_needs_reassessment(kommentar: str) -> bool:
    """True, wenn der Kommentar bereits eine Neubewertungs-Notiz enthält."""
    return NEEDS_REASSESS_MARKER in str(kommentar or "")


def reassessment_kommentar(links: list[Any], kommentar: str) -> str | None:
    """Liefert den aktualisierten Kommentar mit „Neubewertung erforderlich"-Marker,
    oder ``None``, wenn keine Änderung nötig ist.

    #1526: Anstelle der nicht-compliance-konformen Auto-Erfüllung (Score → 5) wird die
    Kontrolle markiert, sobald sich ein verknüpftes Issue **geschlossen** hat — der Score
    bleibt unverändert, ein Mensch bewertet neu.
    #1520: Auch ein **Reopen** (bzw. ein Alt-Datensatz mit Completion-Marker, dessen Issue
    nicht mehr gelöst ist) löst die Markierung aus.

    Trigger:
      - ein verknüpftes Issue ist aktuell gelöst/geschlossen (`first_resolved_link`), ODER
      - der Kommentar trägt noch einen Alt-Completion-Marker, aber kein Link ist gelöst
        (= Reopen / Migration).
    Idempotent: liegt der Marker schon (ohne Alt-Completion-Marker) vor, gibt es keine
    Änderung.
    """
    resolved = first_resolved_link(links)
    legacy_completed = already_completed(kommentar)
    if resolved is not None:
        ref_link, reason = resolved, "geschlossen"
    elif legacy_completed:
        ref_link = (links or [None])[0]
        reason = "wieder geöffnet"
    else:
        return None  # kein Trigger

    if already_needs_reassessment(kommentar) and not legacy_completed:
        return None  # schon korrekt markiert

    note = needs_reassessment_note(ref_link, reason) if ref_link is not None else NEEDS_REASSESS_MARKER
    base = _strip_completion_note(kommentar)  # entfernt Completion- UND Reassess-Marker
    new = f"{base}\n\n{note}" if base else note
    return new if new != str(kommentar or "") else None
