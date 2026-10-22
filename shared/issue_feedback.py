"""Gemeinsame Logik, um Inhalte verknüpfter Issues in eine Bewertung
(Kommentar-/Notizfeld) zurückzuspielen (#830).

Wird von CRA, NIS2 und AI-Act gleichermaßen genutzt — analog zum
``import-issue``-Mechanismus der Risikobewertung. Modul-spezifisch bleibt nur
das Laden der Links und das Speichern der Bewertung; das Abrufen + Zusammenführen
des Issue-Inhalts ist hier zentralisiert.
"""

from __future__ import annotations

from typing import Any

from shared.issue_sync import fetch_issue_content_by_url

_HEADER = "## Issue-Feedback (aus GitHub/GitLab)"

#: Ab dieser Länge wird langes Issue-Feedback bei der Übernahme KI-verdichtet,
#: statt es später im Bewertungs-Prompt hart abzuschneiden (Inhaltsverlust).
_CONDENSE_THRESHOLD = 9000


def condense_feedback(feedback_text: str, *, max_chars: int = _CONDENSE_THRESHOLD) -> str:
    """Verdichtet langes Issue-Feedback **verlustfrei inhaltlich** per KI (statt es
    später hart abzuschneiden). Kurzer Text bleibt unverändert; schlägt die KI fehl
    oder ist kein Provider verfügbar, wird der **vollständige** Originaltext
    zurückgegeben (es gehen nie Inhalte verloren).

    Die KI bekommt den ausdrücklichen Auftrag, jeden inhaltlichen Punkt zu erhalten
    (Anforderungen, Befunde, Entscheidungen, Begründungen, Status) und nur Redundanz/
    Formatierung zu entfernen. Das Ergebnis ist als KI-verdichtet gekennzeichnet.
    """
    text = str(feedback_text or "").strip()
    if len(text) <= max_chars:
        return text
    try:
        from ai_compliance_suite.ai.dispatch import generate_text
        system = (
            "Du verdichtest Issue-/Review-Feedback als Grundlage einer Compliance-"
            "Bewertung. Gib ALLE inhaltlichen Punkte wieder — jede Anforderung, jeden "
            "Befund, jede Entscheidung, jede Begründung und jeden Status. Entferne "
            "ausschließlich Redundanz, Formatierung und Wiederholungen. Erfinde nichts "
            "und lasse nichts Inhaltliches weg."
        )
        prompt = (
            "Verdichte das folgende Issue-Feedback verlustfrei (alle Punkte erhalten) "
            "in kompakte, vollständige Stichpunkte:\n\n" + text
        )
        resp = generate_text(system=system, prompt=prompt, temperature=0.1,
                             max_output_tokens=4096)
        out = (getattr(resp, "text", "") or "").strip()
        if out:
            return (f"🤖 KI-verdichtet (verlustfrei zusammengefasst; Originalumfang "
                    f"{len(text)} Zeichen):\n\n{out}")
    except Exception:  # noqa: BLE001 — Provider fehlt/Cloud ohne Egress/Netzfehler
        pass
    return text  # Fallback: vollständiger Originaltext (kein Inhaltsverlust)


def collect_issue_feedback(
    links: list[Any],
    *,
    gitlab_token_env: str = "GITLAB_TOKEN",
    condense: bool = True,
) -> tuple[str, list[dict]]:
    """Holt für jede verknüpfte Issue-URL den Live-Inhalt (Titel/Status/Body/
    Kommentare) und fügt ihn zu einem Markdown-Block zusammen.

    ``links`` sind Objekte mit Attribut ``url`` (z. B. aus ``issue_links.list_links``).
    Rückgabe: (feedback_text, sources) — ``sources`` listet je Issue ``{url, ok, error?}``.
    """
    blocks: list[str] = []
    sources: list[dict] = []
    for li in links:
        url = getattr(li, "url", "") or (li.get("url") if isinstance(li, dict) else "")
        url = str(url or "").strip()
        if not url:
            continue
        try:
            details = fetch_issue_content_by_url(url, gitlab_token_env=gitlab_token_env)
            combined = str(details.get("combined", "") or "").strip()
            if combined:
                blocks.append(f"### {url}\n\n{combined}")
            sources.append({"url": url, "ok": True})
        except Exception as exc:  # einzelner Fehler darf den Rest nicht stoppen
            sources.append({"url": url, "ok": False, "error": str(exc)})
    feedback_text = ("\n\n".join(blocks)).strip()
    # Langes Feedback bei der Übernahme verlustfrei verdichten, damit später im
    # Bewertungs-Prompt nichts hart abgeschnitten wird (sonst falsche Ergebnisse).
    if condense and feedback_text:
        feedback_text = condense_feedback(feedback_text)
    return feedback_text, sources


def collect_object_feedback(db_path, projekt_name: str, object_kind: str, object_id,
                            *, gitlab_token_env: str = "GITLAB_TOKEN") -> str:
    """#1521: Live-Feedback ALLER verknüpften Issues eines einzelnen Objekts
    (Anforderung/OWASP/Control) als Markdown-Text — oder ``""`` (best-effort, wirft nie).

    Für „Neubewertung mit Issue-Feedback": das Backend sammelt das Feedback selbst,
    sodass das Frontend nur ``use_issue_feedback`` setzen muss."""
    try:
        from shared.issue_links import list_links, ensure_tables
        ensure_tables(db_path)
        links = list_links(db_path, projekt_name=projekt_name,
                           object_kind=object_kind, object_id=str(object_id))
        if not links:
            return ""
        text, _sources = collect_issue_feedback(links, gitlab_token_env=gitlab_token_env)
        return text
    except Exception:
        return ""


def group_links_by_object(links: list[Any]) -> dict[str, list[Any]]:
    """Gruppiert eine Link-Liste nach ``object_id`` (Anforderung/Risiko)."""
    groups: dict[str, list[Any]] = {}
    for li in links:
        oid = getattr(li, "object_id", None)
        if oid is None and isinstance(li, dict):
            oid = li.get("object_id")
        if oid is None:
            continue
        groups.setdefault(str(oid), []).append(li)
    return groups


def merge_feedback_into_comment(existing_comment: str, feedback_text: str) -> str:
    """Hängt einen Issue-Feedback-Block an einen bestehenden Bewertungskommentar an.

    Ein bereits vorhandener Feedback-Block wird ersetzt (idempotent), damit
    mehrfaches Importieren den Kommentar nicht aufbläht.
    """
    existing = str(existing_comment or "").strip()
    # Vorhandenen Feedback-Block (falls bereits importiert) abtrennen.
    if _HEADER in existing:
        existing = existing.split(_HEADER, 1)[0].rstrip()
    block = f"{_HEADER}\n\n{feedback_text}".strip()
    if existing:
        return f"{existing}\n\n{block}"
    return block
