"""Server-Sent-Events-Helfer für Live-KI-Streaming (Sprint #35, #1408).

**Seit #1841 nur noch eine Hülle über :func:`shared.ki_engine.ki_lauf_sse`.**

Die Funktion war bis dahin selbst der Transport und damit eine von vielen:
Die Bestandsaufnahme #1836 fand 47 Stellen, die eigenständig mit der KI
sprechen, mit eigenen Budgets, Parsern und Audit-Entscheidungen. Statt acht
Aufrufer gleichzeitig umzubauen, bleibt die Schnittstelle hier stehen und
reicht an die Engine durch — der Umbau wirkt sofort überall, und die
vorhandenen Tests sind der Regressionsschutz.

Neue Aufrufer sollten `ki_lauf_sse` **direkt** nutzen: Nur dort lassen sich
Herkunft (#1765), Aufgabenart und Vertraulichkeit angeben, und genau die
fehlen hier zwangsläufig.

SSE-Events (unverändert): ``phase`` · ``chunk`` {text} · ``progress``
{tokens,elapsed_s,t_per_s} · ``done`` {ok, …finalize…, error?}.
"""
from __future__ import annotations

from typing import Callable


def stream_ai_sse(system: str, prompt: str, *, finalize: Callable[[str], dict] | None = None,
                  force_json: bool = False, temperature: float = 0.2,
                  num_predict: int = 1024, num_ctx: int | None = None):
    """Liefert eine Flask-Response (SSE), die die KI-Generierung live streamt.

    Args:
      system/prompt: an die KI.
      finalize: optional ``finalize(full_text) -> dict`` — Ergebnis (z. B. {score,
        kommentar, saved}) wird ins ``done``-Event gemischt. Exceptions → ok=False.
      force_json: strukturierte Antwort erzwingen (soweit der Provider es kann;
        was er nicht kann, meldet die Engine als ``nicht_abbildbar``).
      num_predict: maximales Ausgabebudget; eine am Limit abgeschnittene Antwort
        endet mit ``done {ok: False, truncated: True}`` (#1588).
    """
    from shared import prompt_zusatz as _pz
    from shared.ki_engine import OHNE_OBJEKT, KiAuftrag, ki_lauf_sse

    auftrag = KiAuftrag(
        prompt=prompt,
        # Die alte Schnittstelle kennt das Fachobjekt nicht — sie bekam nie
        # eines mitgegeben. Das ist der Grund, warum der Herkunftsvermerk in
        # ≥ 36 Wegen fehlt (#1765/#1836). Hier steht es ausdrücklich, damit es
        # beim Umzug eines Aufrufers auf die Engine auffällt.
        herkunft=OHNE_OBJEKT,
        system=system,
        antwortform="json" if force_json else "prosa",
        temperatur=temperature,
        budget=num_predict,
        num_ctx=num_ctx,
        modul=_pz.modul_aus_pfad(),
        kontext="stream_ai_sse",
        # #1836/E2: Hier geht wirklich etwas hinaus, also wird es bestätigt.
        # Bis v8.1.1 verlangten das genau ZWEI von 47 sendenden Wegen
        # (`run-stream`, Pentest); die Masken zeigten eine Daten-Vorschau und
        # schickten ihre Zustimmung nicht mit — der Anwender klickte etwas
        # weg, das nirgends ankam und nirgends protokolliert wurde (#1840).
        # Umgelegt wurde erst, nachdem jede sendende Maske `confirmed`
        # mitschickt; `tests/test_egress_wirksam_1840.py` hält das fest.
        egress_pflicht=True,
    )
    return ki_lauf_sse(auftrag, finalize=finalize)
