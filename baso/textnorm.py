import re


_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^0-9a-zA-Z\u00c0-\u024f\u1e00-\u1eff\s]+", re.UNICODE)


def normalize_text(s: str) -> str:
    """Normalization used for fuzzy matching.

    Keeps basic latin + common european letters; drops punctuation; collapses spaces.
    """
    if s is None:
        return ""
    s = str(s)
    s = s.casefold()
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s
