from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Any
from urllib.parse import urlparse

import requests

from ..provider import AIProvider, AITextRequest, AITextResponse
from shared.audit import audit_event
from shared.redaction import redact_secrets


class CloudProviderError(RuntimeError):
    pass


_RE_APIKEY = re.compile(r"\b(sk-[A-Za-z0-9]{10,})\b")
_RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def _redact_text(s: str) -> str:
    # Best-effort redaction to avoid leaking obvious secrets/PII.
    s = redact_secrets(s)
    s = _RE_APIKEY.sub("[REDACTED_API_KEY]", s)
    s = _RE_EMAIL.sub("[REDACTED_EMAIL]", s)
    return s


@dataclass
class CloudProvider(AIProvider):
    """Cloud AI provider using an OpenAI-compatible API."""

    cfg: dict[str, Any]
    name: str = "cloud"

    def healthcheck(self) -> None:
        if not bool(self.cfg.get("allow_data_egress", False)):
            raise CloudProviderError("Cloud mode requires explicit consent: ai.cloud.allow_data_egress = true")

        api_key_env = str(self.cfg.get("api_key_env", "AI_CLOUD_API_KEY"))
        api_key = (os.environ.get(api_key_env) or "").strip()
        if not api_key:
            raise CloudProviderError(f"Missing API key environment variable: {api_key_env}")

        base_url = str(self.cfg.get("base_url", "https://api.openai.com/v1")).rstrip("/")
        if not base_url:
            raise CloudProviderError("Missing ai.cloud.base_url")
        u = urlparse(base_url)
        if u.scheme != "https":
            raise CloudProviderError("Cloud base_url must use https")

        model = str(self.cfg.get("model", "")).strip()
        if not model:
            raise CloudProviderError("Missing ai.cloud.model")

    def generate_text(self, req: AITextRequest) -> AITextResponse:
        self.healthcheck()

        api_key_env = str(self.cfg.get("api_key_env", "AI_CLOUD_API_KEY"))
        api_key = (os.environ.get(api_key_env) or "").strip()
        base_url = str(self.cfg.get("base_url", "https://api.openai.com/v1")).rstrip("/")
        model = str(self.cfg.get("model", "")).strip()
        timeout_s = int(self.cfg.get("timeout_s", 60))
        redact = bool(self.cfg.get("redact", True))

        system = (req.system or "").strip()
        prompt = (req.prompt or "").strip()
        if redact:
            system = _redact_text(system)
            prompt = _redact_text(prompt)

        url = base_url + "/chat/completions"

        host = urlparse(base_url).hostname or ""
        audit_event(
            "ai.cloud.request",
            module="ai",
            outcome="start",
            details={"base_url": base_url, "host": host, "model": model, "redact": bool(redact)},
        )
        payload = {
            "model": model,
            "temperature": float(req.temperature),
            "max_tokens": int(req.max_output_tokens),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            r = requests.post(url, json=payload, headers=headers, timeout=max(1, int(timeout_s)))
        except requests.exceptions.RequestException as e:
            audit_event(
                "ai.cloud.request",
                module="ai",
                outcome="fail",
                details={"base_url": base_url, "host": host, "model": model, "error": str(e)},
            )
            raise CloudProviderError(f"Cloud request failed: {e}") from e

        if r.status_code >= 400:
            details = (r.text or "").strip()[:1000]
            audit_event(
                "ai.cloud.request",
                module="ai",
                outcome="fail",
                details={"base_url": base_url, "host": host, "model": model, "http": int(r.status_code)},
            )
            raise CloudProviderError(f"Cloud provider returned HTTP {r.status_code}:\n\n{details}")

        try:
            data = r.json()
        except Exception as e:
            audit_event(
                "ai.cloud.request",
                module="ai",
                outcome="fail",
                details={"base_url": base_url, "host": host, "model": model, "error": "non_json"},
            )
            raise CloudProviderError(f"Cloud response is not JSON:\n\n{(r.text or '')[:1000]}") from e

        try:
            choices = data.get("choices")
            msg = choices[0]["message"]["content"] if isinstance(choices, list) and choices else ""
        except Exception:
            msg = ""

        audit_event(
            "ai.cloud.request",
            module="ai",
            outcome="success",
            details={"base_url": base_url, "host": host, "model": model},
        )
        return AITextResponse(text=str(msg), provider=self.name)
