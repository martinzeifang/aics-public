"""Generischer, prompt-basierter KI-Streamer (Sprint #35, #1408).

Verallgemeinert das RB-Streaming (risikobewertung.prompts.generate_llm_with_meta)
auf beliebige Prompts, damit ALLE Module die KI live mitverfolgen können
(Token-Stream + Kennzahlen). Respektiert den konfigurierten Provider:

- **on_prem (Ollama):** echtes Token-Streaming (``/api/generate stream=True``).
- **cloud:** Volltext als „ein chunk + done" (Cloud-Provider streamt hier nicht).

Event-Typen (dict):
  {"kind": "chunk", "text": str}
  {"kind": "stats", "tokens": int, "elapsed_s": float, "t_per_s": float}
  {"kind": "done", "total_tokens": int, "elapsed_s": float, "eval_count": int,
   "load_duration_s": float, "provider": str}
  {"kind": "error", "error": str, "provider": str}
"""
from __future__ import annotations

import json
import time
from typing import Iterable


def stream_generate(system: str, prompt: str, *, temperature: float = 0.2,
                    num_predict: int = 1024, force_json: bool = False) -> Iterable[dict]:
    """Streamt die KI-Antwort auf ``system``/``prompt`` als Event-Dicts."""
    from ai_compliance_suite.ai.dispatch import current_provider_name, is_cloud_provider

    provider = current_provider_name()
    if is_cloud_provider():
        yield from _cloud(system, prompt, temperature=temperature, num_predict=num_predict)
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
                    yield {"kind": "done", "total_tokens": tokens, "elapsed_s": round(el, 1),
                           "eval_count": obj.get("eval_count", tokens),
                           "load_duration_s": round((obj.get("load_duration", 0) or 0) / 1e9, 2),
                           "provider": provider}
                    return
    except (urllib.error.HTTPError, OSError) as exc:
        yield {"kind": "error", "error": f"Ollama: {exc}", "provider": provider}


def _cloud(system: str, prompt: str, *, temperature: float, num_predict: int) -> Iterable[dict]:
    from ai_compliance_suite.ai.dispatch import generate_text
    started = time.monotonic()
    try:
        resp = generate_text(system=system, prompt=prompt, temperature=temperature,
                             max_output_tokens=max(int(num_predict), 512))
    except Exception as e:  # noqa: BLE001 — Egress/Key/Netz
        yield {"kind": "error", "error": f"{type(e).__name__}: {e}", "provider": "cloud"}
        return
    text = getattr(resp, "text", "") or ""
    el = round(time.monotonic() - started, 1)
    if text:
        yield {"kind": "chunk", "text": text}
    yield {"kind": "done", "total_tokens": 0, "elapsed_s": el, "eval_count": 0,
           "load_duration_s": 0, "provider": getattr(resp, "provider", "cloud")}
