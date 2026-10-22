"""Zentrale Ollama-Konfiguration.

Reihenfolge der Priorität (Issue #410):
  1. Werte aus `ai_compliance_suite.config.json` (`ai.on_prem.base_url` etc.) — was der User im UI gewählt hat
  2. ENV-Variablen (`OLLAMA_BASE_URL`, `OLLAMA_DEFAULT_MODEL`) — Bootstrap-Default für Docker
  3. Hard-coded Defaults

D. h. die User-Auswahl im UI ist authoritativ. Die ENV greift nur, wenn
in der Config noch nichts gesetzt ist (z.B. ganz frisches Docker-Setup).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str
    model: str
    timeout_s: int
    source: str  # 'env' / 'config' / 'default' — für bessere Fehlermeldungen


def get_ollama_config() -> OllamaConfig:
    """Ermittelt die effektive Ollama-Konfiguration.

    Config hat Vorrang vor ENV (#410): wenn der User im UI ein Modell
    gewählt hat, gilt das. ENV greift nur als Bootstrap-Default für
    Docker-Setups, bei denen die Config noch leer ist.
    """
    env_url = os.environ.get('OLLAMA_BASE_URL', '').strip()
    env_model = os.environ.get('OLLAMA_DEFAULT_MODEL', '').strip()

    cfg_url = ''
    cfg_model = ''
    cfg_timeout = 60
    try:
        from ai_compliance_suite.config import load_config

        cfg = load_config()
        on_prem = (cfg.get('ai') or {}).get('on_prem') or {}
        cfg_url = str(on_prem.get('base_url') or '').strip()
        cfg_model = str(on_prem.get('model') or '').strip()
        # Default 300s — CPU-Inferenz braucht oft 60-180s pro Anfrage,
        # erstes Modell-Loaden bei knappem RAM kann noch länger dauern.
        cfg_timeout = int(on_prem.get('timeout_s') or 300)
    except Exception:
        pass

    # User-Auswahl (Config) gewinnt — ENV ist nur Fallback
    base_url = cfg_url or env_url or 'http://127.0.0.1:11434'
    model = cfg_model or env_model or 'llama3.1:8b'
    source = 'config' if cfg_model else ('env' if env_model else 'default')
    return OllamaConfig(base_url=base_url, model=model, timeout_s=cfg_timeout, source=source)


def has_ollama_available() -> bool:
    """True wenn entweder ENV oder Config einen base_url + model liefern."""
    cfg = get_ollama_config()
    return bool(cfg.base_url and cfg.model)
