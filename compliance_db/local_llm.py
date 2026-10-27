from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

import requests

from shared.net_validation import enforce_loopback_base_url


@dataclass
class ContextItem:
    i: int
    framework: str
    doc_name: str
    section_ref: str
    title: str
    text: str


class OllamaError(RuntimeError):
    pass


def _ollama_tags(*, base_url: str, timeout_s: int) -> list[dict]:
    url = base_url.rstrip("/") + "/api/tags"
    try:
        r = requests.get(url, timeout=timeout_s)
    except requests.exceptions.RequestException as e:
        raise OllamaError(
            "Ollama ist nicht erreichbar. Bitte pruefen:\n"
            f"- Laeuft Ollama? (Service/Tray)\n"
            f"- URL: {base_url}\n\n"
            "Tipp: ollama starten und dann erneut versuchen."
        ) from e
    if r.status_code >= 400:
        raise OllamaError(
            f"Ollama antwortet mit HTTP {r.status_code} auf /api/tags.\nURL: {base_url}\n\n{r.text[:800]}"
        )
    try:
        data = r.json()
    except Exception as e:
        raise OllamaError(
            f"Ollama /api/tags liefert kein JSON. URL: {base_url}\n\n{r.text[:800]}"
        ) from e
    models = data.get("models")
    return models if isinstance(models, list) else []


def _ensure_model_present(*, base_url: str, model: str, timeout_s: int) -> None:
    want = (model or "").strip()
    if not want:
        raise OllamaError("Kein Ollama-Modell konfiguriert.")

    tags = _ollama_tags(base_url=base_url, timeout_s=timeout_s)
    names = [str(m.get("name", "")) for m in tags if isinstance(m, dict)]

    # Ollama commonly stores as "model:tag" (e.g. "llama3.1:latest").
    if ":" in want:
        ok = any(n == want for n in names)
    else:
        ok = any(n == want or n.startswith(want + ":") for n in names)

    if not ok:
        sample = "\n".join(f"- {n}" for n in names[:20]) or "(keine Modelle gefunden)"
        raise OllamaError(
            "Ollama laeuft, aber das Modell ist nicht vorhanden:\n"
            f"- Konfiguriert: {want}\n\n"
            "Installiere es z.B. mit:\n"
            f"  ollama pull {want}\n\n"
            "Vorhandene Modelle:\n" + sample
        )


def _build_prompt(question: str, ctx: list[ContextItem]) -> str:
    blocks: list[str] = []
    blocks.append(
        "Du bist ein IT-Compliance-Analyst. Beantworte die Frage NUR anhand des bereitgestellten KONTEXTS. "
        "Wenn die Information nicht im Kontext steht, sage das explizit. Erfinde nichts."
    )
    blocks.append(
        "Antworte auf Deutsch. Zitiere relevante Textpassagen WÖRTLICH als eingerückte Blockzitate "
        "(mit > am Zeilenanfang). Kennzeichne jedes Zitat und jede Aussage mit [n]. "
        "Nenne am Ende eine Quellenliste: [n] Framework | Dokument | Referenz | Titel."
    )
    blocks.append("")
    blocks.append("KONTEXT:")
    for c in ctx:
        header = f"[{c.i}] Framework={c.framework} | Dokument={c.doc_name} | Referenz={c.section_ref}".strip()
        if c.title:
            header += f" | Titel={c.title}"
        blocks.append(header)
        blocks.append(c.text.strip())
        blocks.append("")
    blocks.append("FRAGE:")
    blocks.append(question.strip())
    blocks.append("")
    blocks.append("AUSGABEFORMAT:")
    blocks.append("- Antwort: ...")
    blocks.append("- Quellen: [n] ...")
    return "\n".join(blocks).strip()


def generate_ollama(
    *,
    base_url: str,
    model: str,
    question: str,
    context: list[ContextItem],
    timeout_s: int,
    cancel_event=None,
) -> Iterable[str]:
    """Yields text chunks from Ollama /api/generate (streaming)."""
    enforce_loopback_base_url(base_url, context="compliance_db.ollama", allow_nonlocal=False)
    _ensure_model_present(base_url=base_url, model=model, timeout_s=min(int(timeout_s), 15))
    prompt = _build_prompt(question, context)
    url = base_url.rstrip("/") + "/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
    }

    try:
        r = requests.post(url, json=payload, stream=True, timeout=timeout_s)
    except requests.exceptions.RequestException as e:
        raise OllamaError(
            "Ollama Anfrage ist fehlgeschlagen.\n"
            f"- URL: {base_url}\n"
            f"- Modell: {model}\n\n"
            f"Details: {e}"
        ) from e

    with r:
        if r.status_code >= 400:
            # Try to surface Ollama error messages.
            try:
                j = r.json()
                msg = str(j.get("error", "")) if isinstance(j, dict) else ""
            except Exception:
                msg = ""
            details = (msg or r.text or "").strip()[:800]
            raise OllamaError(
                "Ollama konnte keine Antwort generieren.\n"
                f"HTTP {r.status_code} | Modell: {model} | URL: {base_url}\n\n{details}"
            )
        for line in r.iter_lines(decode_unicode=True):
            if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                return
            if not line:
                continue
            try:
                msg = json.loads(line)
            except Exception:
                continue
            chunk = msg.get("response", "")
            if chunk:
                yield chunk
