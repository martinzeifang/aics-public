"""Server-seitige HTML-Sanitisierung (Defense-in-Depth, Issue #740, WP-07).

Konservativer Allowlist-Sanitizer auf Basis der Standardbibliothek
(``html.parser``) — KEINE neue Abhängigkeit, damit CI/Bandit stabil bleiben.

Die Allowlist entspricht der Frontend-Allowlist (Tiptap StarterKit + Underline,
siehe ``frontend/src/utils/sanitizeHtml.ts``). Gefährliche Elemente wie
``<img>``, ``<script>``, Event-Handler (``onerror``/``onclick``…) und das
``style``-Attribut werden entfernt; ``javascript:``/``data:``-URLs gestrippt.

OWASP A03 (Injection) / A07.
"""
from __future__ import annotations

from html.parser import HTMLParser
from html import escape

# Erlaubte Tags (deckungsgleich mit Frontend-Allowlist).
ALLOWED_TAGS = frozenset({
    'p', 'br',
    'strong', 'b', 'em', 'i', 'u', 's',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li',
    'blockquote', 'code', 'pre',
    'a', 'span',
})

# Pro Tag erlaubte Attribute. Bewusst eng gehalten — KEIN style, KEIN on*.
ALLOWED_ATTRS = {
    'a': frozenset({'href', 'target', 'rel'}),
    '*': frozenset({'class'}),
}

# Void-Elemente, die keinen schließenden Tag bekommen.
VOID_TAGS = frozenset({'br'})

# Raw-Text-Elemente: nicht nur das Tag verwerfen, sondern auch ihren Inhalt
# (sonst landet z. B. der Skript-Body als Text im Output).
RAW_TEXT_TAGS = frozenset({'script', 'style', 'noscript', 'template'})

# Erlaubte URL-Schemata für href.
_SAFE_URL_SCHEMES = ('http:', 'https:', 'mailto:', 'tel:')


def _safe_url(value: str) -> bool:
    """True, wenn die URL kein gefährliches Schema (javascript:/data:) nutzt."""
    v = value.strip().lower()
    # Relative URLs und Anker sind unkritisch.
    if v.startswith(('/', '#', '?')) or v == '':
        return True
    if ':' not in v.split('/')[0]:
        # Kein Schema (z. B. "foo/bar") → relativ, erlaubt.
        return True
    return v.startswith(_SAFE_URL_SCHEMES)


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        # Tiefe innerhalb von Raw-Text-Elementen (script/style/…), deren
        # Inhalt komplett verworfen werden muss.
        self._raw_depth = 0

    def _filter_attrs(self, tag: str, attrs):
        allowed = ALLOWED_ATTRS.get(tag, frozenset()) | ALLOWED_ATTRS['*']
        result = []
        for name, value in attrs:
            name = name.lower()
            if name not in allowed:
                continue
            if name.startswith('on'):
                continue
            value = value or ''
            if name == 'href' and not _safe_url(value):
                continue
            result.append((name, value))
        return result

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in RAW_TEXT_TAGS:
            self._raw_depth += 1
            return
        if tag not in ALLOWED_TAGS:
            return
        safe = self._filter_attrs(tag, attrs)
        attr_str = ''.join(
            f' {name}="{escape(value, quote=True)}"' for name, value in safe
        )
        if tag in VOID_TAGS:
            self.out.append(f'<{tag}{attr_str} />')
        else:
            self.out.append(f'<{tag}{attr_str}>')

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        if tag not in ALLOWED_TAGS:
            return
        safe = self._filter_attrs(tag, attrs)
        attr_str = ''.join(
            f' {name}="{escape(value, quote=True)}"' for name, value in safe
        )
        self.out.append(f'<{tag}{attr_str} />')

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in RAW_TEXT_TAGS:
            if self._raw_depth > 0:
                self._raw_depth -= 1
            return
        if tag not in ALLOWED_TAGS or tag in VOID_TAGS:
            return
        self.out.append(f'</{tag}>')

    def handle_data(self, data):
        if self._raw_depth > 0:
            return
        self.out.append(escape(data, quote=False))

    # Kommentare, Deklarationen, Processing-Instructions komplett verwerfen.
    def handle_comment(self, data):
        pass

    def handle_decl(self, decl):
        pass

    def handle_pi(self, data):
        pass


def sanitize_html(dirty: str | None) -> str:
    """Bereinige unsicheres HTML zu einem sicheren Teilset.

    :param dirty: potenziell unsicheres HTML (z. B. aus einem Request-Body)
    :return: bereinigtes HTML; leerer String bei None/leer.
    """
    if not dirty:
        return ''
    parser = _Sanitizer()
    parser.feed(str(dirty))
    parser.close()
    return ''.join(parser.out)
