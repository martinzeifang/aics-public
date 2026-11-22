"""Generischer, prompt-basierter KI-Streamer (Sprint #35, #1408).

Verallgemeinert das RB-Streaming (risikobewertung.prompts.generate_llm_with_meta)
auf beliebige Prompts, damit ALLE Module die KI live mitverfolgen können
(Token-Stream + Kennzahlen). Respektiert den konfigurierten Provider:

- **on_prem (Ollama):** echtes Token-Streaming (``/api/generate stream=True``).
- **cloud:** echtes Token-Streaming über ``dispatch.stream_text`` (#1588; vorher
  blockierender Volltext → Timeout/Abbruch bei langen Antworten).

Lange Antworten (#1588): Abschneiden am Token-Limit wird erkannt (``truncated`` im
``done``-Event), bei Ollama wird ``num_ctx`` passend zu Prompt + Ausgabe gewählt.

Event-Typen (dict):
  {"kind": "chunk", "text": str}
  {"kind": "stats", "tokens": int, "elapsed_s": float, "t_per_s": float}
  {"kind": "done", "total_tokens": int, "elapsed_s": float, "eval_count": int,
   "load_duration_s": float, "provider": str, "truncated": bool}
  {"kind": "error", "error": str, "provider": str}
"""
from __future__ import annotations

import json
import time
from typing import Iterable


def auto_num_ctx(prompt_chars: int, num_predict: int, requested: int | None = None) -> int | None:
    """Kontextfenster für Ollama (#1588): Prompt (~3 Zeichen/Token) + Ausgabe + Reserve,
    gestuft auf 8k/16k/32k/…, damit das Modell nicht bei jeder Anfrage neu lädt.
    ``None`` = Ollama-Default reicht (kurze Anfragen)."""
    from ai_compliance_suite.ai.dispatch import max_num_ctx

    need = int(prompt_chars) // 3 + int(num_predict) + 512
    if requested:
        need = max(need, int(requested))
    if need <= 4096:
        return int(requested) if requested else None
    cap = max_num_ctx()
    size = 8192
    while size < need and size < cap:
        size *= 2
    return min(size, cap)


def stream_generate(system: str, prompt: str, *, temperature: float = 0.2,
                    num_predict: int = 1024, force_json: bool = False,
                    num_ctx: int | None = None) -> Iterable[dict]:
    """Streamt die KI-Antwort auf ``system``/``prompt`` als Event-Dicts.

    ``num_ctx`` (nur on_prem): Mindest-Kontextfenster (#1583); wird bei Bedarf
    automatisch vergrößert (#1588)."""
    from ai_compliance_suite.ai.dispatch import current_provider_name, is_cloud_provider

    provider = current_provider_name()
    if is_cloud_provider():
        yield from _cloud(system, prompt, temperature=temperature,
                          num_predict=num_predict, force_json=force_json)
        return

    # on_prem (Ollama) — echtes Token-Streaming
    import urllib.error
    import urllib.request

    from shared.net_validation import enforce_loopback_base_url
    from shared.ollama_config import get_ollama_config

    oc = get_ollama_config()
    if not oc.model:
        yield {"kind": "error", "error": "Kein Ollama-Modell konfiguriert", "provider": provider}
        return
    enforce_loopback_base_url(oc.base_url, context="ai.streaming.generate")

    full_prompt = ((system or "").strip() + "\n\n" + (prompt or "").strip()).strip()
    body = {"model": oc.model, "prompt": full_prompt, "stream": True,
            "keep_alive": "10m",
            "options": {"temperature": float(temperature), "num_predict": int(num_predict),
                        "top_p": 0.9}}
    ctx = auto_num_ctx(len(full_prompt), int(num_predict), num_ctx)
    if ctx:
        body["options"]["num_ctx"] = int(ctx)
    if force_json:
        body["format"] = "json"
    req = urllib.request.Request(  # nosec — loopback geprüft
        oc.base_url.rstrip("/") + "/api/generate",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")

    started = time.monotonic()
    tokens = 0
    last_emit = started
    stream_timeout = max(int(oc.timeout_s or 60), 1800)  # kein Cold-Start-Kill
    # AI-Act Art. 12 / AIA-HR-04 (#1550): jeder KI-Aufruf wird protokolliert — wie
    # ``ai.on_prem.request`` im Nicht-Streaming-Pfad. Nur Metadaten, KEINE Inhalte.
    meta = {"base_url": oc.base_url, "model": oc.model, "prompt_chars": len(full_prompt),
            "force_json": bool(force_json), "stream": True, "num_ctx": ctx,
            "num_predict": int(num_predict)}
    _audit("start", meta)
    finished = False
    try:
        with urllib.request.urlopen(req, timeout=stream_timeout) as resp:  # nosec
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                chunk = obj.get("response", "")
                if chunk:
                    tokens += 1
                    yield {"kind": "chunk", "text": chunk}
                    now = time.monotonic()
                    if (now - last_emit) >= 1.0:
                        el = now - started
                        yield {"kind": "stats", "tokens": tokens, "elapsed_s": round(el, 1),
                               "t_per_s": round(tokens / el, 1) if el > 0 else 0}
                        last_emit = now
                if obj.get("done"):
                    el = time.monotonic() - started
                    finished = True
                    truncated = obj.get("done_reason") == "length"
                    _audit("success", {**meta, "tokens": tokens, "elapsed_s": round(el, 1),
                                       "truncated": truncated})
                    yield {"kind": "done", "total_tokens": tokens, "elapsed_s": round(el, 1),
                           "eval_count": obj.get("eval_count", tokens),
                           "load_duration_s": round((obj.get("load_duration", 0) or 0) / 1e9, 2),
                           "provider": provider, "truncated": truncated,
                           "num_predict": int(num_predict)}
                    return
    except (urllib.error.HTTPError, OSError) as exc:
        finished = True
        _audit("fail", {**meta, "error": str(exc)[:300], "tokens": tokens})
        yield {"kind": "error", "error": f"Ollama: {exc}", "provider": provider}
    finally:
        if not finished:  # Abbruch durch Client / Stream ohne done-Marker
            _audit("aborted", {**meta, "tokens": tokens,
                               "elapsed_s": round(time.monotonic() - started, 1)})


def _audit(outcome: str, details: dict) -> None:
    """Best-effort Audit-Eintrag ``ai.on_prem.stream`` (darf den Stream nie brechen)."""
    try:
        from shared.audit import audit_event
        audit_event("ai.on_prem.stream", module="ai", outcome=outcome, details=details)
    except Exception:  # noqa: BLE001
        pass


def _cloud(system: str, prompt: str, *, temperature: float, num_predict: int,
           force_json: bool = False) -> Iterable[dict]:
    """Cloud-Token-Streaming (#1588). Kennzahlen wie bei Ollama (Chunks ≈ Tokens)."""
    from ai_compliance_suite.ai.dispatch import stream_text
    started = time.monotonic()
    last_emit = started
    tokens = 0
    truncated = False
    try:
        for ev in stream_text(system=system, prompt=prompt, temperature=temperature,
                              max_output_tokens=max(int(num_predict), 512),
                              force_json=force_json):
            if ev.get("kind") == "chunk":
                tokens += 1
                yield {"kind": "chunk", "text": ev["text"]}
                now = time.monotonic()
                if (now - last_emit) >= 1.0:
                    el = now - started
                    yield {"kind": "stats", "tokens": tokens, "elapsed_s": round(el, 1),
                           "t_per_s": round(tokens / el, 1) if el > 0 else 0}
                    last_emit = now
            elif ev.get("kind") == "end":
                truncated = bool(ev.get("truncated"))
    except Exception as e:  # noqa: BLE001 — Egress/Key/Netz
        yield {"kind": "error", "error": f"{type(e).__name__}: {e}", "provider": "cloud"}
        return
    el = round(time.monotonic() - started, 1)
    yield {"kind": "done", "total_tokens": tokens, "elapsed_s": el, "eval_count": tokens,
           # #1573: einheitlich „cloud" (resp.provider ist der Anbietername, z. B.
           # „anthropic" — das Frontend zeigte dafür fälschlich „🖥️ Lokal").
           "load_duration_s": 0, "provider": "cloud", "truncated": truncated,
           "num_predict": int(num_predict)}
