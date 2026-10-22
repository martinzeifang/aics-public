from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from ..provider import AIProvider, AITextRequest, AITextResponse
from shared.audit import audit_event
from shared.net_validation import enforce_loopback_base_url


class OnPremProviderError(RuntimeError):
    pass


def _ollama_get_tags(*, base_url: str, timeout_s: int) -> list[dict[str, Any]]:
    url = base_url.rstrip("/") + "/api/tags"
    try:
        r = requests.get(url, timeout=max(1, int(timeout_s)))
    except requests.exceptions.RequestException as e:
        raise OnPremProviderError(
            "Ollama is not reachable. Please verify:\n"
            f"- Is Ollama running?\n- URL: {base_url}\n\n"
            "Tip: start Ollama and try again."
        ) from e
    if r.status_code >= 400:
        raise OnPremProviderError(
            f"Ollama returned HTTP {r.status_code} for /api/tags. URL: {base_url}\n\n{r.text[:800]}"
        )
    try:
        data = r.json()
    except Exception as e:
        raise OnPremProviderError(
            f"Ollama /api/tags did not return JSON. URL: {base_url}\n\n{r.text[:800]}"
        ) from e
    models = data.get("models")
    return models if isinstance(models, list) else []


def _ensure_model_present(*, base_url: str, model: str, timeout_s: int) -> None:
    want = (model or "").strip()
    if not want:
        raise OnPremProviderError(
            "No on-prem model configured. Set `ai.on_prem.model` (e.g. `llama3.1:latest`)."
        )

    tags = _ollama_get_tags(base_url=base_url, timeout_s=min(int(timeout_s), 15))
    names = [str(m.get("name", "")) for m in tags if isinstance(m, dict)]

    if ":" in want:
        ok = any(n == want for n in names)
    else:
        ok = any(n == want or n.startswith(want + ":") for n in names)

    if not ok:
        sample = "\n".join(f"- {n}" for n in names[:20]) or "(no models found)"
        raise OnPremProviderError(
            "Ollama is running, but the configured model is not present:\n"
            f"- Configured: {want}\n\n"
            "Install it with:\n"
            f"  ollama pull {want}\n\n"
            "Available models:\n" + sample
        )


@dataclass
class OnPremProvider(AIProvider):
    """On-prem AI provider using Ollama."""

    cfg: dict[str, Any]
    name: str = "on_prem"

    def healthcheck(self) -> None:
        base_url = str(self.cfg.get("base_url", "http://127.0.0.1:11434"))
        enforce_loopback_base_url(
            base_url,
            context="ai.on_prem.healthcheck",
            allow_nonlocal=bool(self.cfg.get("allow_nonlocal_base_url", False)),
        )
        timeout_s = int(self.cfg.get("timeout_s", 60))
        _ollama_get_tags(base_url=base_url, timeout_s=timeout_s)

    def list_models(self) -> list[str]:
        """Installierte Ollama-Modelle abrufen (``GET /api/tags``)."""
        base_url = str(self.cfg.get("base_url", "http://127.0.0.1:11434"))
        enforce_loopback_base_url(
            base_url,
            context="ai.on_prem.list_models",
            allow_nonlocal=bool(self.cfg.get("allow_nonlocal_base_url", False)),
        )
        tags = _ollama_get_tags(base_url=base_url, timeout_s=min(int(self.cfg.get("timeout_s", 60)), 15))
        return [str(m.get("name")) for m in tags if isinstance(m, dict) and m.get("name")]

    def generate_text(self, req: AITextRequest) -> AITextResponse:
        base_url = str(self.cfg.get("base_url", "http://127.0.0.1:11434"))
        enforce_loopback_base_url(
            base_url,
            context="ai.on_prem.generate_text",
            allow_nonlocal=bool(self.cfg.get("allow_nonlocal_base_url", False)),
        )
        model = str(self.cfg.get("model", ""))
        timeout_s = int(self.cfg.get("timeout_s", 60))

        _ensure_model_present(base_url=base_url, model=model, timeout_s=timeout_s)

        url = base_url.rstrip("/") + "/api/generate"
        prompt = (req.system or "").strip() + "\n\n" + (req.prompt or "").strip()
        payload = {
            "model": model,
            "prompt": prompt.strip(),
            "stream": False,
            "options": {
                "temperature": float(req.temperature),
            },
        }

        audit_event(
            "ai.on_prem.request",
            module="ai",
            outcome="start",
            details={"base_url": base_url, "model": model},
        )

        try:
            r = requests.post(url, json=payload, timeout=max(1, int(timeout_s)))
        except requests.exceptions.RequestException as e:
            audit_event(
                "ai.on_prem.request",
                module="ai",
                outcome="fail",
                details={"base_url": base_url, "model": model, "error": str(e)},
            )
            raise OnPremProviderError(
                "Ollama request failed.\n"
                f"- URL: {base_url}\n- Model: {model}\n\n"
                f"Details: {e}"
            ) from e

        if r.status_code >= 400:
            audit_event(
                "ai.on_prem.request",
                module="ai",
                outcome="fail",
                details={"base_url": base_url, "model": model, "http": int(r.status_code)},
            )
            details = (r.text or "").strip()[:800]
            raise OnPremProviderError(
                "Ollama could not generate a response.\n"
                f"HTTP {r.status_code} | Model: {model} | URL: {base_url}\n\n{details}"
            )

        try:
            data = r.json()
        except Exception as e:
            audit_event(
                "ai.on_prem.request",
                module="ai",
                outcome="fail",
                details={"base_url": base_url, "model": model, "error": "non_json"},
            )
            raise OnPremProviderError(f"Ollama response is not JSON:\n\n{(r.text or '')[:800]}") from e

        text = str(data.get("response", ""))
        audit_event(
            "ai.on_prem.request",
            module="ai",
            outcome="success",
            details={"base_url": base_url, "model": model},
        )
        return AITextResponse(text=text, provider=self.name)
