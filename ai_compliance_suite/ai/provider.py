from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class AITextRequest:
    """Provider-agnostic text generation request."""

    system: str
    prompt: str
    temperature: float = 0.2
    max_output_tokens: int = 1200


@dataclass(frozen=True)
class AITextResponse:
    """Provider-agnostic text generation response."""

    text: str
    # Provider name/id for diagnostics (never include secrets).
    provider: str


class AIProvider(Protocol):
    """Minimal provider interface used by the app.

    Keep this narrow; add methods only when we have a concrete usage.
    """

    name: str

    def generate_text(self, req: AITextRequest) -> AITextResponse:
        raise NotImplementedError

    def healthcheck(self) -> None:
        """Raise on misconfiguration or unreachable backend."""
        raise NotImplementedError


def provider_from_config(cfg: dict[str, Any]) -> AIProvider:
    """Factory for the configured provider.

    Concrete implementations are added in later issues.
    """

    ai_cfg = cfg.get("ai") if isinstance(cfg, dict) else None
    if not isinstance(ai_cfg, dict):
        raise ValueError("Missing 'ai' config section")

    provider = ai_cfg.get("provider", "on_prem")
    if provider == "on_prem":
        from .providers.on_prem import OnPremProvider

        return OnPremProvider(ai_cfg.get("on_prem") if isinstance(ai_cfg.get("on_prem"), dict) else {})
    if provider == "cloud":
        from .providers.cloud import CloudProvider

        return CloudProvider(ai_cfg.get("cloud") if isinstance(ai_cfg.get("cloud"), dict) else {})

    raise ValueError(f"Unknown AI provider: {provider!r}")
