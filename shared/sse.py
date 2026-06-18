"""Server-Sent-Events-Helfer für Live-KI-Streaming (Sprint #35, #1408).

Wickelt den generischen KI-Streamer (``ai_compliance_suite.ai.streaming.stream_generate``)
in eine Flask-``text/event-stream``-Response. Module bekommen so mit einer Zeile einen
Live-Stream-Endpoint (Token-für-Token + Kennzahlen), inkl. optionalem ``finalize``,
das den Volltext am Ende parst/speichert und ins ``done``-Event mischt.

SSE-Events: ``phase`` · ``chunk`` {text} · ``progress`` {tokens,elapsed_s,t_per_s} ·
``done`` {ok, ...finalize..., error?}.
"""
from __future__ import annotations

import json
from typing import Any, Callable


def stream_ai_sse(system: str, prompt: str, *, finalize: Callable[[str], dict] | None = None,
                  force_json: bool = False, temperature: float = 0.2,
                  num_predict: int = 1024):
    """Liefert eine Flask-Response (SSE), die die KI-Generierung live streamt.

    Args:
      system/prompt: an die KI.
      finalize: optional ``finalize(full_text) -> dict`` — Ergebnis (z. B. {score,
        kommentar, saved}) wird ins ``done``-Event gemischt. Exceptions → ok=False.
      force_json: Ollama ``format=json`` erzwingen (für strukturierte Antworten).
    """
    from flask import Response, stream_with_context
    from ai_compliance_suite.ai.streaming import stream_generate

    @stream_with_context
    def _gen():
        def _ev(name: str, data: dict) -> str:
            return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"

        chunks: list[str] = []
        provider = ""
        done_stats: dict[str, Any] = {}
        try:
            yield _ev("phase", {"phase": "connect", "message": "Verbinde mit KI …"})
            for ev in stream_generate(system, prompt, temperature=temperature,
                                      num_predict=num_predict, force_json=force_json):
                kind = ev.get("kind")
                if kind == "chunk":
                    chunks.append(ev["text"])
                    yield _ev("chunk", {"text": ev["text"]})
                elif kind == "stats":
                    yield _ev("progress", {"tokens": ev.get("tokens", 0),
                                           "elapsed_s": ev.get("elapsed_s", 0),
                                           "t_per_s": ev.get("t_per_s", 0)})
                elif kind == "done":
                    provider = ev.get("provider", "")
                    done_stats = ev
                elif kind == "error":
                    yield _ev("done", {"ok": False, "error": ev.get("error", "KI-Fehler"),
                                       "provider": ev.get("provider", "")})
                    return

            full = "".join(chunks)
            payload: dict[str, Any] = {"ok": True, "provider": provider,
                                       "tokens": done_stats.get("total_tokens", 0),
                                       "elapsed_s": done_stats.get("elapsed_s", 0)}
            if finalize is not None:
                try:
                    payload.update(finalize(full) or {})
                except Exception as e:  # noqa: BLE001
                    yield _ev("done", {"ok": False, "error": f"Antwort nicht verwertbar: {e}",
                                       "raw_preview": full[:400]})
                    return
            else:
                payload["text"] = full
            yield _ev("done", payload)
        except Exception as e:  # noqa: BLE001
            yield _ev("done", {"ok": False, "error": f"{type(e).__name__}: {e}"})

    return Response(_gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
