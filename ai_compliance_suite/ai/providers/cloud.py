from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from typing import Any, Iterator
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

    def _prepare(self, req: AITextRequest, *, stream: bool = False,
                 max_tokens: int | None = None) -> dict[str, Any]:
        """Baut URL/Header/Payload für Anthropic (Messages-API) bzw. OpenAI-kompatibel."""
        api_key = self._resolve_api_key()
        base_url = str(self.cfg.get("base_url", "https://api.openai.com/v1")).rstrip("/")
        model = str(self.cfg.get("model", "")).strip()
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
        mt = int(max_tokens or req.max_output_tokens)
        if is_anthropic:
            payload: dict[str, Any] = {
                "model": model,
                "max_tokens": mt,
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
                "max_tokens": mt,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        if stream:
            payload["stream"] = True
        return {"url": url, "payload": payload, "headers": headers, "base_url": base_url,
                "host": host, "model": model, "redact": redact, "is_anthropic": is_anthropic}

    def _read_timeout(self) -> int:
        # #1588: lange Antworten (Massenbewertung) brauchen deutlich mehr als 60 s.
        return max(int(self.cfg.get("timeout_s", 60) or 60), 300)

    def _post(self, prep: dict[str, Any], *, stream: bool):
        """POST mit Rückfall auf kleinere ``max_tokens``, falls das Modell das
        angeforderte Ausgabebudget nicht unterstützt (HTTP 400 „max_tokens …“)."""
        payload = dict(prep["payload"])
        budgets = [int(payload["max_tokens"])] + [b for b in (8192, 4096)
                                                  if b < int(payload["max_tokens"])]
        last = None
        for mt in budgets:
            payload["max_tokens"] = mt
            r = requests.post(prep["url"], json=payload, headers=prep["headers"], stream=stream,
                              timeout=(30, self._read_timeout()))
            if r.status_code == 400 and "max_tokens" in (r.text or "").lower() and mt != budgets[-1]:
                last = r
                continue
            return r
        return last

    def generate_text(self, req: AITextRequest) -> AITextResponse:
        self.healthcheck()
        prep = self._prepare(req)
        base_url, host, model = prep["base_url"], prep["host"], prep["model"]
        is_anthropic = prep["is_anthropic"]
        audit_event(
            "ai.cloud.request",
            module="ai",
            outcome="start",
            details={"base_url": base_url, "host": host, "model": model, "redact": bool(prep["redact"])},
        )

        try:
            r = self._post(prep, stream=False)
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
                # Anthropic: {"content": [{"type":"text","text":"…"}, …], ...} — alle
                # Text-Blöcke zusammenfügen (#1588; vorher nur der erste).
                blocks = data.get("content")
                msg = "".join(b.get("text", "") for b in blocks
                              if isinstance(b, dict) and b.get("type", "text") == "text") \
                    if isinstance(blocks, list) else ""
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
        return AITextResponse(text=str(msg or ""), provider=self.name)

    def stream_text(self, req: AITextRequest) -> Iterator[dict[str, Any]]:
        """Echtes Token-Streaming (#1588) — Anthropic-SSE bzw. OpenAI ``stream=true``.

        Liefert ``{"kind": "chunk", "text"}`` und zum Schluss
        ``{"kind": "end", "stop_reason", "truncated"}``. Der Read-Timeout greift so
        nur noch zwischen zwei Tokens statt für die gesamte Generierung."""
        self.healthcheck()
        prep = self._prepare(req, stream=True)
        base_url, host, model = prep["base_url"], prep["host"], prep["model"]
        is_anthropic = prep["is_anthropic"]
        audit_event("ai.cloud.request", module="ai", outcome="start",
                    details={"base_url": base_url, "host": host, "model": model,
                             "redact": bool(prep["redact"]), "stream": True})
        try:
            r = self._post(prep, stream=True)
        except requests.exceptions.RequestException as e:
            audit_event("ai.cloud.request", module="ai", outcome="fail",
                        details={"base_url": base_url, "host": host, "model": model,
                                 "error": str(e), "stream": True})
            raise CloudProviderError(f"Cloud request failed: {e}") from e
        if r.status_code >= 400:
            details = (r.text or "").strip()[:1000]
            audit_event("ai.cloud.request", module="ai", outcome="fail",
                        details={"base_url": base_url, "host": host, "model": model,
                                 "http": int(r.status_code), "stream": True})
            raise CloudProviderError(f"Cloud provider returned HTTP {r.status_code}:\n\n{details}")

        stop_reason = ""
        try:
            for raw in r.iter_lines(decode_unicode=False):
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    obj = json.loads(data_str)
                except Exception:
                    continue
                if is_anthropic:
                    typ = obj.get("type")
                    if typ == "content_block_delta":
                        delta = obj.get("delta") or {}
                        if delta.get("type", "text_delta") == "text_delta" and delta.get("text"):
                            yield {"kind": "chunk", "text": delta["text"]}
                    elif typ == "message_delta":
                        stop_reason = (obj.get("delta") or {}).get("stop_reason") or stop_reason
                    elif typ == "error":
                        err = (obj.get("error") or {}).get("message") or str(obj)[:300]
                        raise CloudProviderError(f"Cloud-Stream-Fehler: {err}")
                    elif typ == "message_stop":
                        break
                else:
                    for ch in obj.get("choices") or []:
                        txt = ((ch.get("delta") or {}).get("content")) or ""
                        if txt:
                            yield {"kind": "chunk", "text": txt}
                        if ch.get("finish_reason"):
                            stop_reason = ch["finish_reason"]
        except requests.exceptions.RequestException as e:
            audit_event("ai.cloud.request", module="ai", outcome="fail",
                        details={"base_url": base_url, "host": host, "model": model,
                                 "error": str(e), "stream": True})
            raise CloudProviderError(f"Cloud-Stream unterbrochen: {e}") from e
        finally:
            r.close()

        truncated = stop_reason in ("max_tokens", "length")
        audit_event("ai.cloud.request", module="ai", outcome="success",
                    details={"base_url": base_url, "host": host, "model": model, "stream": True,
                             "stop_reason": stop_reason, "truncated": truncated})
        yield {"kind": "end", "stop_reason": stop_reason, "truncated": truncated}
