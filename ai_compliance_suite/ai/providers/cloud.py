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

    def _resolve_api_key(self) -> str:
        """API-Key auflösen: direkter ``api_key`` (in der Config) hat Vorrang, sonst
        die in ``api_key_env`` benannte Umgebungsvariable. Wirft mit klarer, KEY-freier
        Meldung, wenn nichts Brauchbares vorliegt (kein Key-Leak)."""
        direct = str(self.cfg.get("api_key", "") or "").strip()
        if direct:
            return direct
        api_key_env = str(self.cfg.get("api_key_env", "AI_CLOUD_API_KEY") or "").strip()
        if api_key_env and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", api_key_env):
            # Gültiger Variablen-NAME → Wert aus der Umgebung.
            key = (os.environ.get(api_key_env) or "").strip()
            if key:
                return key
            raise CloudProviderError(
                f"Kein API-Key: Umgebungsvariable '{api_key_env}' ist nicht gesetzt. "
                "Bitte in den Einstellungen einen Key hinterlegen.")
        if api_key_env:
            # Kein gültiger Variablenname → der Nutzer hat den Key direkt in das
            # Env-Feld eingetragen. Tolerant als Key verwenden (NIE echoen).
            return api_key_env
        raise CloudProviderError(
            "Kein Cloud-API-Key konfiguriert. Bitte in den Einstellungen einen Key "
            "eintragen (oder eine gesetzte Umgebungsvariable benennen).")

    def list_models(self) -> list[str]:
        """Verfügbare Modelle vom Provider abrufen (Anthropic/OpenAI ``GET /models``)."""
        api_key = self._resolve_api_key()
        base_url = str(self.cfg.get("base_url", "https://api.openai.com/v1")).rstrip("/")
        host = (urlparse(base_url).hostname or "").lower()
        is_anthropic = "anthropic.com" in host
        headers = ({"x-api-key": api_key, "anthropic-version": "2023-06-01"}
                   if is_anthropic else {"Authorization": f"Bearer {api_key}"})
        try:
            r = requests.get(base_url + "/models", headers=headers,
                             timeout=max(1, int(self.cfg.get("timeout_s", 30))))
        except requests.exceptions.RequestException as e:
            raise CloudProviderError(f"Modell-Liste nicht abrufbar: {e}") from e
        if r.status_code >= 400:
            raise CloudProviderError(
                f"Modell-Liste: HTTP {r.status_code}: {(r.text or '')[:300]}")
        data = r.json() if r.content else {}
        items = data.get("data") if isinstance(data, dict) else None
        return [str(m.get("id")) for m in (items or []) if isinstance(m, dict) and m.get("id")]

    def healthcheck(self) -> None:
        if not bool(self.cfg.get("allow_data_egress", False)):
            raise CloudProviderError("Cloud mode requires explicit consent: ai.cloud.allow_data_egress = true")
        self._resolve_api_key()

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

        api_key = self._resolve_api_key()
        base_url = str(self.cfg.get("base_url", "https://api.openai.com/v1")).rstrip("/")
        model = str(self.cfg.get("model", "")).strip()
        timeout_s = int(self.cfg.get("timeout_s", 60))
        redact = bool(self.cfg.get("redact", True))

        system = (req.system or "").strip()
        prompt = (req.prompt or "").strip()
        if redact:
            system = _redact_text(system)
            prompt = _redact_text(prompt)

        host = urlparse(base_url).hostname or ""
        # Anthropic spricht NICHT das OpenAI-Protokoll: eigene Messages-API
        # (/v1/messages, x-api-key, anthropic-version) statt /chat/completions+Bearer.
        is_anthropic = "anthropic.com" in host.lower()
        url = base_url + ("/messages" if is_anthropic else "/chat/completions")
        audit_event(
            "ai.cloud.request",
            module="ai",
            outcome="start",
            details={"base_url": base_url, "host": host, "model": model, "redact": bool(redact)},
        )
        if is_anthropic:
            payload = {
                "model": model,
                "max_tokens": int(req.max_output_tokens),
                "temperature": float(req.temperature),
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            }
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
        else:
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
            if is_anthropic:
                # Anthropic: {"content": [{"type":"text","text":"…"}], ...}
                blocks = data.get("content")
                msg = blocks[0].get("text", "") if isinstance(blocks, list) and blocks else ""
            else:
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
