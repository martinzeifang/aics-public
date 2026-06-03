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


def collect_issue_feedback(
    links: list[Any],
    *,
    gitlab_token_env: str = "GITLAB_TOKEN",
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
    return feedback_text, sources


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
