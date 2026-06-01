"""Impressum-Parser: extrahiert Firmendaten aus deutschem Website-Impressum."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass
class ImpressumData:
    company_name: str = ""
    legal_form: str = ""
    street: str = ""
    zip_city: str = ""
    country: str = ""
    representative: str = ""
    email: str = ""
    phone: str = ""
    vat_id: str = ""
    hrb: str = ""
    raw_address: str = ""
    source_url: str = ""
    all_urls: list[str] = field(default_factory=list)

    def as_beschreibung(self) -> str:
        """Formatierter Beschreibungstext für das Kunden-Formular."""
        parts: list[str] = []
        if self.raw_address:
            parts.append(f"Adresse: {self.raw_address}")
        if self.representative:
            parts.append(f"Vertreter: {self.representative}")
        if self.email:
            parts.append(f"E-Mail: {self.email}")
        if self.phone:
            parts.append(f"Telefon: {self.phone}")
        if self.vat_id:
            parts.append(f"USt-IdNr.: {self.vat_id}")
        if self.hrb:
            parts.append(f"Registernr.: {self.hrb}")
        if self.source_url:
            parts.append(f"Quelle: {self.source_url}")
        return "\n".join(parts)


# ── Regex-Muster ───────────────────────────────────────────────────────────────

_LEGAL_FORMS = [
    "GmbH & Co\\.? KG", "GmbH & Co\\.? KGaA",
    "GmbH & Co\\.? OHG",
    "GmbH", "AG", r"UG \(haftungsbeschränkt\)", "UG",
    r"KGaA", "KG", "OHG", "GbR", r"e\.?V\.", r"e\.?K\.",
    "SE", "Ltd\\.", "Stiftung", "Verein",
]
_LEGAL_FORM_RE = re.compile(
    r"(" + "|".join(_LEGAL_FORMS) + r")",
    re.IGNORECASE,
)

_COMPANY_RE = re.compile(
    r"([A-ZÄÖÜ][^\n,]{2,60}?)\s+(?:GmbH|AG|KG|OHG|GbR|UG|SE|e\.V\.|e\.K\.|Ltd\.|Stiftung)",
    re.IGNORECASE,
)

_ZIP_CITY_RE = re.compile(r"\b(\d{5})\s+([A-ZÄÖÜ][a-zäöüß\s\-]+?)(?:\n|,|$)")
_STREET_RE = re.compile(
    r"([A-ZÄÖÜ][a-zäöüßA-Z \-]{3,40}(?:straße|str\.|gasse|weg|allee|platz|ring|chaussee)\.?)[ \t]*(\d+[ \t]*[a-zA-Z]?)",
    re.IGNORECASE,
)

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(
    r"(?:Tel\.?(?:efon)?|Fon|Rufnummer|Phone):?\s*((?:\+49|0\d)[\d\s\(\)\-\/]{5,18})",
    re.IGNORECASE,
)
_VAT_RE = re.compile(
    r"(?:USt\.?-?Id\.?(?:Nr\.?)?|Umsatzsteuer-?(?:Identifikations)?nummer):?\s*(DE\s?\d{9})",
    re.IGNORECASE,
)
_HRB_RE = re.compile(
    r"\b(?:HRB|HRA)\s+(\d[\d\s]*?)(?:\s+Amtsgericht|\n|,|;|$)",
    re.IGNORECASE,
)
_REP_RE = re.compile(
    r"(?:Geschäftsführer(?:in)?|Vorstand|Inhaber(?:in)?|Vertreter(?:in)?|"
    r"Managing Director|Vorstandsvorsitzender?):?\s*([^\n,;]{3,80})",
    re.IGNORECASE,
)


def parse_impressum(text: str, source_url: str = "") -> ImpressumData:
    """Extrahiert Firmendaten aus dem Klartext einer Impressum-Seite."""
    data = ImpressumData(source_url=source_url)

    # Firma + Rechtsform
    m = _COMPANY_RE.search(text)
    if m:
        full = m.group(0).strip()
        lf_m = _LEGAL_FORM_RE.search(full)
        if lf_m:
            data.legal_form = lf_m.group(0)
            # Name = alles vor der Rechtsform
            data.company_name = full[: lf_m.start()].strip().rstrip(",").strip()
            data.company_name = f"{data.company_name} {data.legal_form}".strip()
        else:
            data.company_name = full

    # Straße
    m = _STREET_RE.search(text)
    if m:
        data.street = f"{m.group(1).strip()} {m.group(2).strip()}"

    # PLZ + Ort
    m = _ZIP_CITY_RE.search(text)
    if m:
        data.zip_city = f"{m.group(1)} {m.group(2).strip()}"

    if data.street and data.zip_city:
        data.raw_address = f"{data.street}, {data.zip_city}"
    elif data.street:
        data.raw_address = data.street
    elif data.zip_city:
        data.raw_address = data.zip_city

    # Vertreter / Geschäftsführer
    m = _REP_RE.search(text)
    if m:
        data.representative = m.group(1).strip()

    # E-Mail
    m = _EMAIL_RE.search(text)
    if m:
        data.email = m.group(0)

    # Telefon
    for m in _PHONE_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group(1))
        if len(digits) >= 7:
            data.phone = m.group(1).strip()
            break

    # USt-IdNr
    m = _VAT_RE.search(text)
    if m:
        data.vat_id = m.group(1)

    # Handelsregister
    m = _HRB_RE.search(text)
    if m:
        data.hrb = m.group(1).strip()

    return data


def bootstrap_from_url(url: str, max_pages: int = 10) -> ImpressumData:
    """Crawlt eine Website und extrahiert Impressum-Daten.

    Sucht bevorzugt Seiten mit /impressum, /kontakt, /datenschutz.
    """
    from evidence.crawler import crawl as ev_crawl

    pages = ev_crawl(url, max_pages=max_pages, delay=0.3)

    # Impressum-Seiten bevorzugen
    impressum_pages = [
        p for p in pages
        if re.search(r"/impressum|/kontakt|/ueber[-_]?uns|/about", p.url, re.IGNORECASE)
    ]
    ordered = impressum_pages + [p for p in pages if p not in impressum_pages]

    best = ImpressumData(source_url=url, all_urls=[p.url for p in pages])

    for page in ordered:
        candidate = parse_impressum(page.text, source_url=page.url)
        # Merge: use best available data
        if not best.company_name and candidate.company_name:
            best.company_name = candidate.company_name
            best.legal_form = candidate.legal_form
        if not best.raw_address and candidate.raw_address:
            best.raw_address = candidate.raw_address
            best.street = candidate.street
            best.zip_city = candidate.zip_city
        if not best.representative and candidate.representative:
            best.representative = candidate.representative
        if not best.email and candidate.email:
            best.email = candidate.email
        if not best.phone and candidate.phone:
            best.phone = candidate.phone
        if not best.vat_id and candidate.vat_id:
            best.vat_id = candidate.vat_id
        if not best.hrb and candidate.hrb:
            best.hrb = candidate.hrb

        if best.company_name and best.raw_address and best.email:
            break

    return best
