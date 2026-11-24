"""Website-Crawler mit konfigurierbaren Limits (Impressum-first)."""
from __future__ import annotations

import re
import time
from collections import deque
from html.parser import HTMLParser
from typing import Callable, NamedTuple
from urllib.parse import urljoin, urlparse

from evidence.web_fetch import WebFetchError, fetch_page, is_binary_url


class CrawlPage(NamedTuple):
    url: str
    title: str
    text: str


# Pfade die bevorzugt gecrawlt werden (Impressum-first)
_PRIORITY_PATTERNS = [
    r"/impressum",
    r"/datenschutz",
    r"/kontakt",
    r"/ueber[-_]?uns",
    r"/ueber$",
    r"/agb",
    r"/nutzungsbedingungen",
    r"/rechtliches",
    r"/about",
]

_PRIORITY_RE = re.compile("|".join(_PRIORITY_PATTERNS), re.IGNORECASE)


def _priority_score(url: str) -> int:
    """Lower score = higher priority. 0 = matches Impressum-first patterns."""
    path = urlparse(url).path
    if _PRIORITY_RE.search(path):
        return 0
    # Prefer shorter paths (likely main nav pages)
    return len(path)


# ── Link extraction ───────────────────────────────────────────────────────────

class _LinkExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self._base = base_url
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                abs_url = urljoin(self._base, value.strip())
                # Strip fragment
                abs_url = abs_url.split("#")[0]
                if abs_url:
                    self.links.append(abs_url)


def _extract_links(html: str, base_url: str) -> list[str]:
    parser = _LinkExtractor(base_url)
    try:
        parser.feed(html)
    except Exception:
        pass
    return parser.links


# ── Fetcher that also returns raw HTML for link extraction ─────────────────

def _fetch_with_links(url: str, timeout: int) -> tuple[CrawlPage, list[str]]:
    """Fetch page, return (CrawlPage, list_of_links)."""
    from evidence.web_fetch import _HEADERS, html_to_text
    from shared.net_validation import safe_get

    # #741 (SSRF): safe_get validiert URL + jeden Redirect-Hop (blockt
    # Loopback/RFC1918/Link-Local/Cloud-Metadata 169.254.169.254).
    resp = safe_get(url, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        raise WebFetchError(f"Kein HTML: {url}")
    html = resp.text
    title, text = html_to_text(html)
    links = _extract_links(html, resp.url)
    return CrawlPage(url=resp.url, title=title, text=text), links


# ── Crawler ───────────────────────────────────────────────────────────────────

def crawl(
    seed_url: str,
    *,
    max_pages: int = 20,
    timeout: int = 15,
    delay: float = 0.5,
    same_host_only: bool = True,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> list[CrawlPage]:
    """Crawl a website starting from seed_url.

    Args:
        seed_url:       Start URL.
        max_pages:      Maximum number of pages to fetch.
        timeout:        HTTP request timeout in seconds.
        delay:          Delay between requests in seconds.
        same_host_only: Restrict crawl to same hostname.
        on_progress:    Callback(fetched_count, queued_count, current_url).

    Returns:
        List of CrawlPage (url, title, text) in discovery order.
    """
    parsed_seed = urlparse(seed_url)
    seed_host = parsed_seed.netloc.lower()

    visited: set[str] = set()
    results: list[CrawlPage] = []

    # Queue entries: (priority_score, url)
    queue: list[tuple[int, str]] = [(0, seed_url)]
    seen_queue: set[str] = {seed_url}

    def _enqueue(url: str) -> None:
        norm = url.split("?")[0].rstrip("/") or url
        if norm in seen_queue:
            return
        if is_binary_url(url):
            return
        if same_host_only:
            host = urlparse(url).netloc.lower()
            if host != seed_host:
                return
        seen_queue.add(norm)
        score = _priority_score(url)
        queue.append((score, url))
        queue.sort(key=lambda x: x[0])

    import requests  # type: ignore

    while queue and len(results) < max_pages:
        _, url = queue.pop(0)

        norm = url.split("?")[0].rstrip("/") or url
        if norm in visited:
            continue
        visited.add(norm)

        if on_progress:
            on_progress(len(results), len(queue), url)

        try:
            page, links = _fetch_with_links(url, timeout)
        except (WebFetchError, requests.exceptions.RequestException, Exception):
            continue

        if not page.text.strip():
            continue

        results.append(page)

        for link in links:
            _enqueue(link)

        if delay > 0 and len(results) < max_pages:
            time.sleep(delay)

    return results
