"""Web-Seiten abrufen und als Klartext extrahieren (DE-Websites)."""
from __future__ import annotations

import re
import time
from html.parser import HTMLParser
from typing import NamedTuple
from urllib.parse import urljoin, urlparse


class WebFetchError(RuntimeError):
    pass


class FetchResult(NamedTuple):
    url: str          # final URL after redirects
    title: str
    text: str


# ── HTML → Text ───────────────────────────────────────────────────────────────

class _TextExtractor(HTMLParser):
    """Extracts readable text from HTML, skipping navigation/chrome elements."""

    _SKIP = frozenset({
        "script", "style", "noscript", "nav", "header", "footer",
        "aside", "form", "button", "select", "option", "iframe",
        "svg", "canvas", "template", "dialog",
    })
    _BLOCK = frozenset({
        "p", "div", "section", "article", "main", "h1", "h2", "h3",
        "h4", "h5", "h6", "li", "dt", "dd", "td", "th", "br",
        "blockquote", "pre", "figure", "figcaption", "address",
    })

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._title_depth = 0
        self._parts: list[str] = []
        self._pending_break = False
        self.title = ""

    def handle_starttag(self, tag: str, attrs: list) -> None:
        t = tag.lower()
        if t in self._SKIP:
            self._skip_depth += 1
        elif t == "title":
            self._title_depth += 1
        elif t in self._BLOCK and self._skip_depth == 0:
            self._pending_break = True

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in self._SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif t == "title":
            self._title_depth = max(0, self._title_depth - 1)
        elif t in self._BLOCK and self._skip_depth == 0:
            self._pending_break = True

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        text = data.strip()
        if not text:
            return
        if self._title_depth > 0 and not self.title:
            self.title = text
            return
        if self._pending_break:
            self._parts.append("")
            self._pending_break = False
        self._parts.append(text)

    def get_text(self) -> str:
        raw = "\n".join(self._parts)
        # collapse runs of 3+ blank lines to 2
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def html_to_text(html: str) -> tuple[str, str]:
    """Parse HTML and return (title, plain_text)."""
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass
    return parser.title, parser.get_text()


# ── HTTP fetch ────────────────────────────────────────────────────────────────

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AI-Compliance-Suite/1.0; "
        "+https://github.com/martinzeifang/AI_Compliance_Suite)"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
}

_BINARY_EXTS = frozenset({
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
    ".zip", ".rar", ".gz", ".tar",
    ".xls", ".xlsx", ".doc", ".docx", ".ppt", ".pptx",
    ".mp3", ".mp4", ".avi", ".mov",
    ".exe", ".msi", ".dmg",
})


def is_binary_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    for ext in _BINARY_EXTS:
        if path.endswith(ext):
            return True
    return False


def fetch_page(url: str, *, timeout: int = 15) -> FetchResult:
    """Fetch a URL and return extracted title + plain text."""
    try:
        import requests  # type: ignore
    except ImportError as exc:
        raise WebFetchError("requests nicht installiert. pip install requests") from exc

    if is_binary_url(url):
        raise WebFetchError(f"Binäre URL übersprungen: {url}")

    try:
        resp = requests.get(
            url,
            headers=_HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        raise WebFetchError(f"Timeout beim Abrufen von {url}")
    except requests.exceptions.ConnectionError as e:
        raise WebFetchError(f"Verbindungsfehler bei {url}: {e}")
    except requests.exceptions.HTTPError as e:
        raise WebFetchError(f"HTTP-Fehler bei {url}: {e}")
    except Exception as e:
        raise WebFetchError(f"Fehler beim Abrufen von {url}: {e}")

    content_type = resp.headers.get("Content-Type", "")
    if "text/html" not in content_type and "text/plain" not in content_type:
        raise WebFetchError(f"Kein Text/HTML-Inhalt bei {url} (Content-Type: {content_type})")

    # Encoding: use detected or chardet fallback
    try:
        html = resp.text
    except Exception as e:
        raise WebFetchError(f"Kodierungsfehler bei {url}: {e}")

    title, text = html_to_text(html)
    final_url = resp.url

    if not text.strip():
        raise WebFetchError(f"Kein lesbarer Text extrahierbar von {url}")

    return FetchResult(url=final_url, title=title, text=text)
