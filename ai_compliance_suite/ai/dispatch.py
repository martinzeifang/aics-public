"""Gemeinsame Provider-Dispatch-Schicht für KI-Textgenerierung (#1342 Defekt B).

Hintergrund
-----------
Die Provider-Abstraktion (``ai_compliance_suite/ai/provider.py`` +
``providers/on_prem.py`` + ``providers/cloud.py``) wurde bisher nicht durchgängig
genutzt: Risikobewertung und SOC riefen fest verdrahtet Ollama auf und ignorierten
die Cloud-Einstellung. Dieses Modul stellt **eine** Stelle bereit, über die alle
KI-Aufrufe laufen — sie respektiert ``ai.provider`` aus den globalen Settings.

Trennung von Prompt-Bau und Transport
-------------------------------------
Aufrufer bauen ihren Prompt weiterhin selbst (``build_*_prompt``) und übergeben ihn
hier — derselbe Prompt geht an Ollama **oder** Cloud, je nach Konfiguration.

Wichtige Garantien
------------------
- ``provider=cloud`` ohne ``allow_data_egress`` → harter Stopp (``CloudProviderError``
  aus dem Healthcheck), **kein** stiller Ollama-Fallback.
- ``provider=cloud`` → Redaction + Audit (``ai.cloud.request``) über ``CloudProvider``.
- ``provider=on_prem`` → unverändertes Ollama-Verhalten inkl. SSRF-Guard (#741), das
  Streaming bleibt im jeweiligen Modul (siehe ``is_cloud_provider``).
"""

from __future__ import annotations

from typing import Any

from .provider import AIProvider, AITextRequest, AITextResponse, provider_from_config


def _load_ai_config() -> dict[str, Any]:
    """Lädt die globale Suite-Config (mit ``ai``-Sektion).

    Fällt bei Fehlern auf eine on_prem-Default-Config zurück, damit der Aufrufer
    nicht crasht, sondern den (lokalen) Ollama-Pfad nutzt.
    """
    try:
        from ai_compliance_suite.config import load_config

        cfg = load_config()
        if isinstance(cfg, dict) and isinstance(cfg.get("ai"), dict):
            return cfg
    except Exception:
        pass
    return {"ai": {"provider": "on_prem"}}


def current_provider_name() -> str:
    """Name des aktuell konfigurierten Providers (``on_prem`` | ``cloud``)."""
    ai = _load_ai_config().get("ai") or {}
    return str(ai.get("provider", "on_prem"))


def is_cloud_provider() -> bool:
    """True, wenn ``ai.provider == 'cloud'``.

    Streaming-Endpunkte nutzen dies, um zu entscheiden, ob sie den (lokalen)
    Token-Stream fahren (on_prem) oder den Cloud-Volltext als „ein Chunk + done"
    abbilden.
    """
    return current_provider_name() == "cloud"


def build_provider() -> AIProvider:
    """Baut den konfigurierten Provider aus der Live-Config.

    Wirft ``ValueError`` bei unbekanntem Provider. Der eigentliche Egress-/
    Konfig-Check passiert erst im ``generate_text``/``healthcheck`` des Providers.
    """
    return provider_from_config(_load_ai_config())


def generate_text(
    *,
    system: str,
    prompt: str,
    temperature: float = 0.2,
    max_output_tokens: int = 1200,
) -> AITextResponse:
    """Erzeugt Text über den **konfigurierten** Provider (on_prem ODER cloud).

    Derselbe Prompt geht an beide Provider. Der Provider übernimmt:
      - on_prem: SSRF-Guard (#741), Ollama-Call, Audit ``ai.on_prem.request``.
      - cloud:  Egress-Pflicht (``allow_data_egress``), Redaction,
                Audit ``ai.cloud.request`` (weist den genutzten Provider aus).

    Bei ``cloud`` ohne ``allow_data_egress`` wirft ``CloudProvider.generate_text``
    (via ``healthcheck``) ``CloudProviderError`` — **kein** stiller Fallback auf
    Ollama.
    """
    provider = build_provider()
    return provider.generate_text(
        AITextRequest(
            system=system,
            prompt=prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
    )


__all__ = [
    "AITextRequest",
    "AITextResponse",
    "build_provider",
    "current_provider_name",
    "generate_text",
    "is_cloud_provider",
]
