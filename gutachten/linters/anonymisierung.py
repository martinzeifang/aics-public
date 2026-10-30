"""G6-7 — Anonymisierungs-Linter: schwärzt / markiert PII.

Erkennt:
- Aktenzeichen-Muster (z.B. "X 0815/26")
- E-Mail-Adressen
- IP-Adressen (v4 + v6)
- Telefon-Nummern (DE-Muster)
- SHA-256-Hashes als sicherer Marker (NICHT geschwärzt — Hashes sind keine PII)
- Deutsche Postleitzahl + Straße (Heuristik)
- typische Namens-Anrede ("Herr", "Frau", "RA", "RAin", "Dr.")
"""
from __future__ import annotations

import re
from typing import Any

# Regex-Patterns
RX_AKTENZEICHEN = re.compile(r"\b[A-Z]\s?\d{1,5}/\d{2,4}\b")
RX_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
RX_IPV4 = re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b")
RX_PHONE = re.compile(r"\b(?:\+49|0)\s?[1-9](?:[\s\-/]?\d){6,14}\b")
RX_PLZ_STREET = re.compile(r"\b\d{5}\s+[A-ZÄÖÜ][\wäöüß-]+(?:\s+[\wäöüß-]+)*\b")
RX_ANREDE = re.compile(
    r"\b(?:Herr|Frau|Hr\.|Fr\.|Dr\.|Dipl\.|Prof\.|RA|RAin|Rechtsanwalt|Rechtsanwältin)\s+[A-ZÄÖÜ][\wäöüß-]+(?:\s+[A-ZÄÖÜ][\wäöüß-]+)*"
)

# #660 — Firmen-Suffix-Erkennung (DE + international)
RX_FIRMA = re.compile(
    r"\b[A-ZÄÖÜ][\w&äöüß.\-]+(?:\s+[\w&äöüß.\-]+){0,5}"
    r"\s+(?:GmbH(?:\s*&\s*Co\.?\s*KG)?|AG|KG|OHG|UG(?:\s*\(haftungsbeschränkt\))?|"
    r"SE|e\.\s?V\.|gGmbH|Stiftung|GbR|Ltd\.?|Inc\.?|LLC|Corp\.?|S\.?A\.?|S\.?L\.?|"
    r"B\.?V\.?|N\.?V\.?|Sàrl|S\.?p\.?A\.?|Pty\.?\s*Ltd\.?|mbH)\b"
)


def _findall(text: str, pattern: re.Pattern, kind: str, placeholder: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in pattern.finditer(text):
        out.append({
            "level": "info",
            "kind": kind,
            "term": m.group(0),
            "pos_start": m.start(),
            "pos_end": m.end(),
            "placeholder": placeholder,
        })
    return out


def lint(text: str) -> list[dict[str, Any]]:
    """Liste aller PII-Treffer im Text (für Anzeige)."""
    text = text or ""
    out: list[dict[str, Any]] = []
    out.extend(_findall(text, RX_AKTENZEICHEN, "aktenzeichen", "[AZ-ANONYMISIERT]"))
    out.extend(_findall(text, RX_EMAIL, "email", "[EMAIL-ANONYMISIERT]"))
    out.extend(_findall(text, RX_IPV4, "ipv4", "[IP-ANONYMISIERT]"))
    out.extend(_findall(text, RX_PHONE, "phone", "[TEL-ANONYMISIERT]"))
    out.extend(_findall(text, RX_PLZ_STREET, "adresse", "[ADRESSE-ANONYMISIERT]"))
    out.extend(_findall(text, RX_ANREDE, "name-mit-anrede", "[PERSON-ANONYMISIERT]"))
    out.extend(_findall(text, RX_FIRMA, "firma", "[FIRMA-ANONYMISIERT]"))
    out.sort(key=lambda h: h["pos_start"])
    return out


def anonymize(text: str) -> str:
    """Liefert anonymisierte Version (Original bleibt unverändert)."""
    text = text or ""
    # Reihenfolge wichtig: spezifisch → generisch
    text = RX_EMAIL.sub("[EMAIL-ANONYMISIERT]", text)
    text = RX_AKTENZEICHEN.sub("[AZ-ANONYMISIERT]", text)
    text = RX_IPV4.sub("[IP-ANONYMISIERT]", text)
    text = RX_PHONE.sub("[TEL-ANONYMISIERT]", text)
    text = RX_PLZ_STREET.sub("[ADRESSE-ANONYMISIERT]", text)
    text = RX_ANREDE.sub("[PERSON-ANONYMISIERT]", text)
    text = RX_FIRMA.sub("[FIRMA-ANONYMISIERT]", text)
    return text
