#!/usr/bin/env python3
from __future__ import annotations

"""DORA downloader

Why this exists:
- Direct PDF links on eur-lex.europa.eu are currently protected by an AWS WAF
  challenge (often returning HTTP 202 + HTML). This breaks simple "GET PDF"
  downloaders.
- The Publications Office (publications.europa.eu) exposes the same documents
  via a SPARQL endpoint + stable Cellar item URLs that serve the PDF directly.

This script downloads:
- The DORA base regulation (default: CELEX 32022R2554)
- All *regulations* that are legally based on that act (delegated/implementing
  regulations incl. RTS/ITS), discovered via SPARQL.

The PDFs include the annexes/attachments as part of the official publication.
"""

import os
import re
import sys
import time
import shutil
import subprocess
import json
import hashlib
import argparse
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from typing import Any

import requests


@dataclass
class Doc:
    title: str
    celex: str
    kind: str  # DORA | Derived
    lang: str = "DEU"  # Publications Office language codes, e.g. DEU, ENG
    pdf_item_url: str | None = None
    publication_date: str | None = None  # YYYY-MM-DD


@dataclass
class DownloadResult:
    celex: str
    lang: str
    title: str
    publication_date: str | None
    url: str
    out_path: str
    bytes_written: int
    sha256: str
    ok: bool
    error: str | None = None


@dataclass
class ExtraResource:
    name: str
    url: str
    filename: str
    headers: dict | None = None


@dataclass
class ExtraDownloadResult:
    name: str
    url: str
    out_path: str
    bytes_written: int
    sha256: str
    ok: bool
    error: str | None = None


SPARQL_ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"
CELEX_BASE = "http://publications.europa.eu/resource/celex/"
LANG_BASE = "http://publications.europa.eu/resource/authority/language/"


def safe_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[^\w\-\.]+", "_", name, flags=re.UNICODE)
    name = re.sub(r"_+", "_", name)
    return name.strip("_")


def is_pdf_bytes(b: bytes) -> bool:
    return len(b) >= 5 and b[:5] == b"%PDF-"


def is_zip_bytes(b: bytes) -> bool:
    # XLSX is a ZIP container.
    return len(b) >= 4 and b[:4] == b"PK\x03\x04"


def looks_like_celex(s: str) -> bool:
    return bool(re.fullmatch(r"3\d{4}[A-Z]\d{4}", s.strip()))


def normalize_lang(lang: str) -> str:
    lang = (lang or "").strip().upper()
    if lang in {"DE", "DEU"}:
        return "DEU"
    if lang in {"EN", "ENG"}:
        return "ENG"
    return lang


def _ascii_fold(s: str) -> str:
    # Best-effort ASCII fold for filenames and matching.
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = s.replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")
    s = unicodedata.normalize("NFKD", s)
    return s.encode("ascii", "ignore").decode("ascii")


def slug_token(s: str, max_len: int = 64) -> str:
    s = _ascii_fold(s)
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if len(s) > max_len:
        s = s[:max_len].rstrip("_")
    return s


def parse_act_header_from_title(title: str) -> tuple[str, str] | None:
    """Extract (act_type_code, year_num) from title.

    Returns e.g. ("DelVO", "2024_1772").
    """
    t = _ascii_fold(title)
    # Common German forms
    m = re.search(
        r"\b(Delegierte\s+Verordnung|Durchfuehrungsverordnung|Verordnung|Richtlinie)\s*\(EU\)\s*(\d{4})/(\d{1,4})\b",
        t,
    )
    if not m:
        return None
    kind = m.group(1).lower()
    year = m.group(2)
    num = m.group(3).zfill(4)
    if kind.startswith("delegierte"):
        code = "DelVO"
    elif kind.startswith("durchf"):
        code = "DurchfVO"
    elif kind.startswith("richtl"):
        code = "RL"
    else:
        code = "VO"
    return code, f"{year}_{num}"


def infer_topic_token(title: str, celex: str) -> str:
    # Use a non-truncated normalized string for matching; titles can be very long.
    t = _ascii_fold(title).lower()
    # Keep the most important words; explicit patterns for known DORA derived acts.
    if "digitale operationale resilienz" in t or celex == "32022R2554":
        return "dora"
    if "nis 2" in t or "nis2" in t or celex == "32022L2555":
        return "nis2"
    if "cyber resilience act" in t or celex == "32024R2847":
        return "cra"
    if "ueberwachungsgebuehren" in t or "ueberwachungsgebuhren" in t:
        return "oversight_gebuehren"
    if "klassifizierung" in t and ("ikt" in t or "cyber" in t):
        return "ikt_vorfaelle_klassifizierung"
    if "vertrag" in t and ("ikt" in t or "drittdienst" in t):
        return "ikt_drittparteien_vertragsinhalte"
    if "ikt-risikomanagement" in t or "ikt risikomanagement" in t:
        return "ikt_risikomanagement"
    if "untervergabe" in t or "subcontract" in t:
        return "subcontracting"
    # "kritisch" appears in several titles ("kritischer oder wichtiger Funktionen").
    # Only map to the "critical ICT third-party" criteria when the title is about classification.
    if "einstufung" in t and "kritisch" in t and ("ikt-drittdienst" in t or "ikt drittdienst" in t):
        return "kriterien_kritische_ikt_drittdienstleister"
    if ("erstmeldung" in t or "zwischenmeldung" in t or "abschlussmeldung" in t) and ("ikt" in t or "cyber" in t):
        return "incident_reporting_inhalte_fristen"
    if "standardformulare" in t and ("vorfall" in t or "cyberbedrohung" in t):
        return "incident_reporting_formulare"
    if "harmonisierung" in t and "ueberwachung" in t:
        return "oversight_harmonisierung"
    if "untersuchungsteam" in t or "jet" in t:
        return "joint_examination_teams"
    if "penetrationstest" in t or "tlpt" in t:
        return "tlpt"
    if "informationsregister" in t:
        return "informationsregister_vorlagen"

    # Fallback: take the end of the title, it usually contains the subject.
    tail = slug_token(title, max_len=1000)
    for cut in ("zur_ergaenzung_der_verordnung", "zur_festlegung", "im_hinblick_auf", "durch_technische"):
        if cut in tail:
            tail = tail.split(cut, 1)[-1]
    tail = re.sub(r"^(der|die|das|des|den|dem)_+", "", tail)
    tail = re.sub(r"^(festlegung|spezifizierung|praezisierung)_+", "", tail)
    tail = tail.strip("_")
    if not tail:
        return "unknown_topic"
    return tail[:60].rstrip("_")


def extract_publication_date_from_sameas(uris: list[str]) -> str | None:
    # Many item URLs have the OJ issue date embedded, e.g. "...l_33320221227de0001....pdf".
    for u in uris:
        m = re.search(r"(19\d{2}|20\d{2})(\d{2})(\d{2})", u)
        if not m:
            continue
        y = int(m.group(1))
        mm = int(m.group(2))
        dd = int(m.group(3))
        if 1900 <= y <= 2100 and 1 <= mm <= 12 and 1 <= dd <= 31:
            return f"{y:04d}-{mm:02d}-{dd:02d}"
    return None


def resolve_publication_date_for_celex(session: requests.Session, celex: str) -> str | None:
    celex_uri = CELEX_BASE + celex
    q = "\n".join(
        [
            "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>",
            "PREFIX owl: <http://www.w3.org/2002/07/owl#>",
            "SELECT ?pub WHERE {",
            "  ?work owl:sameAs <" + celex_uri + "> .",
            "  { ?work cdm:official-journal-act_date_publication ?pub }",
            "  UNION",
            "  { ?work cdm:work_date_creation_legacy ?pub }",
            "} LIMIT 1",
        ]
    )
    rows = sparql_select(session, q)
    if not rows:
        return None
    v = rows[0].get("pub")
    if not v:
        return None
    # Typically already YYYY-MM-DD
    m = re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.strip())
    return v.strip() if m else None


def compute_logical_filename(doc: Doc) -> str:
    pub = doc.publication_date or "unknown-date"
    head = parse_act_header_from_title(doc.title)
    if head:
        act_code, year_num = head
    else:
        act_code, year_num = ("VO", f"{doc.celex[1:5]}_{doc.celex[-4:]}")
    topic = infer_topic_token(doc.title, doc.celex)
    # Example: 2024-07-15_EU_2024_1772_DelVO_ikt_vorfaelle_klassifizierung_DEU.pdf
    return safe_filename(f"{pub}_EU_{year_num}_{act_code}_{topic}_{doc.lang}.pdf")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def get_winhttp_proxy() -> str | None:
    """
    Reads WinHTTP proxy: `netsh winhttp show proxy`
    Returns proxy string like "http://proxy:8080" or None if direct/unknown.
    """
    try:
        p = subprocess.run(
            ["netsh", "winhttp", "show", "proxy"],
            capture_output=True,
            text=True,
            check=False,
        )
        out = (p.stdout or "") + "\n" + (p.stderr or "")
        out = out.strip()
        if not out:
            return None
        # Typical outputs:
        # "Direct access (no proxy server)."
        # "Current WinHTTP proxy settings:\n    Proxy Server(s) :  http=proxy:8080;https=proxy:8080\n    Bypass List     :  ..."
        if "Direct access" in out:
            return None

        m = re.search(r"Proxy Server\(s\)\s*:\s*(.+)", out)
        if not m:
            return None
        proxy_raw = m.group(1).strip()

        # Handle "http=...;https=..." format. Prefer https if present.
        # Example: "http=proxy:8080;https=proxy:8080"
        parts = {}
        for seg in proxy_raw.split(";"):
            seg = seg.strip()
            if "=" in seg:
                k, v = seg.split("=", 1)
                parts[k.strip().lower()] = v.strip()
            else:
                # single proxy like "proxy:8080"
                parts["all"] = seg

        proxy = parts.get("https") or parts.get("http") or parts.get("all")
        if not proxy:
            return None

        # Ensure scheme
        if not proxy.startswith(("http://", "https://")):
            proxy = "http://" + proxy
        return proxy
    except Exception:
        return None


def build_requests_session() -> requests.Session:
    s = requests.Session()
    # Let requests use env vars if set
    s.trust_env = True

    # If no env proxy is set, try WinHTTP proxy and apply
    env_has_proxy = any(os.environ.get(k) for k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"))
    if not env_has_proxy:
        winproxy = get_winhttp_proxy()
        if winproxy:
            s.proxies.update({"http": winproxy, "https": winproxy})
    return s


def sparql_select(session: requests.Session, query: str, timeout: int = 60, retries: int = 3) -> list[dict[str, str]]:
    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI Compliance Suite",
    }

    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            r = session.get(
                SPARQL_ENDPOINT,
                headers=headers,
                params={"query": query},
                timeout=timeout,
                allow_redirects=True,
            )
            r.raise_for_status()
            payload: dict[str, Any] = r.json()
            bindings = payload.get("results", {}).get("bindings", [])
            out: list[dict[str, str]] = []
            for b in bindings:
                row: dict[str, str] = {}
                for k, v in b.items():
                    if isinstance(v, dict) and "value" in v:
                        row[k] = str(v["value"])
                if row:
                    out.append(row)
            return out
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.0 * attempt)
    raise RuntimeError(f"SPARQL request failed after {retries} attempts: {last_err}")


def resolve_work_uri_for_celex(session: requests.Session, celex: str) -> str:
    celex_uri = CELEX_BASE + celex
    q = "\n".join(
        [
            "PREFIX owl: <http://www.w3.org/2002/07/owl#>",
            "SELECT ?work WHERE { ?work owl:sameAs <" + celex_uri + "> . } LIMIT 1",
        ]
    )
    rows = sparql_select(session, q)
    if not rows or "work" not in rows[0]:
        raise RuntimeError(f"No Publications Office work found for CELEX {celex}")
    return rows[0]["work"]


def discover_regulations_based_on(session: requests.Session, base_work_uri: str) -> list[str]:
    q = "\n".join(
        [
            "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>",
            "PREFIX owl: <http://www.w3.org/2002/07/owl#>",
            "SELECT DISTINCT ?celex WHERE {",
            "  ?w cdm:resource_legal_based_on_resource_legal <" + base_work_uri + "> .",
            "  ?w owl:sameAs ?celex .",
            "  FILTER(REGEX(STR(?celex), '/resource/celex/3[0-9]{4}R'))",
            "} ORDER BY ?celex",
        ]
    )
    rows = sparql_select(session, q)
    out: list[str] = []
    for r in rows:
        u = r.get("celex")
        if not u:
            continue
        m = re.search(r"/resource/celex/(3\d{4}R\d{4})$", u)
        if m:
            out.append(m.group(1))
    return out


def resolve_pdf_item_and_title(session: requests.Session, celex: str, lang: str) -> tuple[str, str]:
    lang = normalize_lang(lang)
    celex_uri = CELEX_BASE + celex
    lang_uri = LANG_BASE + lang
    q = "\n".join(
        [
            "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>",
            "PREFIX owl: <http://www.w3.org/2002/07/owl#>",
            "SELECT DISTINCT ?item ?title ?mtype WHERE {",
            "  ?work owl:sameAs <" + celex_uri + "> .",
            "  ?expr cdm:expression_belongs_to_work ?work ;",
            "        cdm:expression_uses_language <" + lang_uri + "> ;",
            "        cdm:expression_title ?title .",
            "  ?man  cdm:manifestation_manifests_expression ?expr ;",
            "        cdm:manifestation_type ?mtype .",
            "  FILTER(STRSTARTS(LCASE(STR(?mtype)), 'pdf'))",
            "  ?item cdm:item_belongs_to_manifestation ?man .",
            "} LIMIT 5",
        ]
    )
    rows = sparql_select(session, q)
    if not rows:
        raise RuntimeError(f"No PDF item found for CELEX {celex} lang={lang}")
    item = rows[0].get("item")
    title = rows[0].get("title") or f"CELEX {celex}"
    if not item:
        raise RuntimeError(f"No PDF item URL returned for CELEX {celex} lang={lang}")
    if item.startswith("http://publications.europa.eu/"):
        item = "https://publications.europa.eu/" + item[len("http://publications.europa.eu/") :]
    return item, title


def resolve_item_sameas(session: requests.Session, item_url: str) -> list[str]:
    item = item_url.replace("https://", "http://")
    q = "\n".join(
        [
            "PREFIX owl: <http://www.w3.org/2002/07/owl#>",
            "SELECT ?same WHERE { <" + item + "> owl:sameAs ?same . } LIMIT 20",
        ]
    )
    rows = sparql_select(session, q)
    out: list[str] = []
    for r in rows:
        v = r.get("same")
        if v:
            out.append(v)
    return out


def download_via_curl(url: str, out_path: Path) -> None:
    curl = shutil.which("curl") or shutil.which("curl.exe")
    if not curl:
        raise RuntimeError("curl.exe not found (needed for fallback).")

    # curl typically handles corporate proxy setups better. We keep it simple:
    # -L follow redirects, --fail on HTTP errors, --retry transient issues.
    cmd = [
        curl,
        "-L",
        "--fail",
        "--retry", "3",
        "--retry-delay", "1",
        "--connect-timeout", "30",
        "--max-time", "180",
        "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI Compliance Suite",
        "-H", "Accept: application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
        "-H", "Accept-Language: de-DE,de;q=0.9,en;q=0.7",
        "-H", "Accept-Encoding: identity",
        "-o", str(out_path),
        url,
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"curl failed (rc={p.returncode}): {p.stderr.strip() or p.stdout.strip()}")
    # Sanity check
    data = out_path.read_bytes()
    if not is_pdf_bytes(data):
        raise RuntimeError("curl downloaded a non-PDF response (proxy portal/error page?)")


def download_via_curl_any(url: str, out_path: Path, *, expect: str | None) -> None:
    curl = shutil.which("curl") or shutil.which("curl.exe")
    if not curl:
        raise RuntimeError("curl.exe not found (needed for fallback).")

    cmd = [
        curl,
        "-L",
        "--fail",
        "--retry",
        "3",
        "--retry-delay",
        "1",
        "--connect-timeout",
        "30",
        "--max-time",
        "180",
        "-A",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI Compliance Suite",
        "-H",
        "Accept: application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/octet-stream;q=0.9,*/*;q=0.8",
        "-H",
        "Accept-Language: de-DE,de;q=0.9,en;q=0.7",
        "-H",
        "Accept-Encoding: identity",
        "-o",
        str(out_path),
        url,
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"curl failed (rc={p.returncode}): {p.stderr.strip() or p.stdout.strip()}")

    head = out_path.read_bytes()[:16]
    if expect == "pdf" and not is_pdf_bytes(head):
        raise RuntimeError("curl downloaded a non-PDF response (proxy portal/error page?)")
    if expect == "xlsx" and not is_zip_bytes(head):
        raise RuntimeError("curl downloaded a non-XLSX response (proxy portal/error page?)")


def download_streaming_requests(
    session: requests.Session,
    url: str,
    out_path: Path,
    timeout_connect: int = 30,
    timeout_read: int = 120,
    retries: int = 3,
) -> None:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI Compliance Suite",
        "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.7",
        "Accept-Encoding": "identity",
        "Connection": "close",
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".part")

    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            if tmp.exists():
                tmp.unlink()
            with session.get(
                url,
                headers=headers,
                stream=True,
                timeout=(timeout_connect, timeout_read),
                allow_redirects=True,
            ) as r:
                r.raise_for_status()
                with tmp.open("wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            f.write(chunk)
            # quick sanity check
            with tmp.open("rb") as f:
                head = f.read(16)
            if not is_pdf_bytes(head):
                raise RuntimeError("Downloaded response is not a PDF (maybe proxy/WAF HTML)")
            tmp.replace(out_path)
            return
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.0 * attempt)

    raise RuntimeError(f"requests streaming failed after {retries} attempts: {last_err}")


def download_streaming_requests_any(
    session: requests.Session,
    url: str,
    out_path: Path,
    *,
    expect: str | None,
    timeout_connect: int = 30,
    timeout_read: int = 120,
    retries: int = 3,
    extra_headers: dict | None = None,
) -> None:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.7",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    if extra_headers:
        headers.update(extra_headers)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".part")

    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            if tmp.exists():
                tmp.unlink()
            with session.get(
                url,
                headers=headers,
                stream=True,
                timeout=(timeout_connect, timeout_read),
                allow_redirects=True,
            ) as r:
                r.raise_for_status()
                with tmp.open("wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            f.write(chunk)

            with tmp.open("rb") as f:
                head = f.read(16)
            if expect == "pdf" and not is_pdf_bytes(head):
                raise RuntimeError("Downloaded response is not a PDF (maybe proxy/WAF HTML)")
            if expect == "xlsx" and not is_zip_bytes(head):
                raise RuntimeError("Downloaded response is not an XLSX (maybe proxy/WAF HTML)")

            tmp.replace(out_path)
            return
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.0 * attempt)

    raise RuntimeError(f"requests streaming failed after {retries} attempts: {last_err}")


def download_extra_resource(session: requests.Session, r: ExtraResource, out_dir: Path, *, force: bool) -> ExtraDownloadResult:
    out_path = out_dir / safe_filename(r.filename)
    expect: str | None
    suffix = out_path.suffix.lower().lstrip(".")
    expect = suffix if suffix in {"pdf", "xlsx"} else None

    if out_path.exists() and not force:
        try:
            with out_path.open("rb") as f:
                head = f.read(16)
            if expect == "pdf" and not is_pdf_bytes(head):
                raise RuntimeError("Existing file is not a PDF")
            if expect == "xlsx" and not is_zip_bytes(head):
                raise RuntimeError("Existing file is not an XLSX")
            size = out_path.stat().st_size
            return ExtraDownloadResult(
                name=r.name,
                url=r.url,
                out_path=str(out_path),
                bytes_written=size,
                sha256=sha256_file(out_path),
                ok=True,
            )
        except Exception:
            # fall through to re-download
            pass

    if force and out_path.exists():
        try:
            out_path.unlink()
        except Exception:
            pass
        part = out_path.with_suffix(out_path.suffix + ".part")
        if part.exists():
            try:
                part.unlink()
            except Exception:
                pass

    last_err: Exception | None = None
    tmp = out_path.with_suffix(out_path.suffix + ".part")
    try:
        download_streaming_requests_any(session, r.url, out_path, expect=expect, extra_headers=r.headers)
    except Exception as e:
        last_err = e
        try:
            if tmp.exists():
                tmp.unlink()
            download_via_curl_any(r.url, tmp, expect=expect)
            tmp.replace(out_path)
        except Exception as e2:
            # Don't leave error HTML behind as ".part".
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass
            return ExtraDownloadResult(
                name=r.name,
                url=r.url,
                out_path=str(out_path),
                bytes_written=0,
                sha256="",
                ok=False,
                error=f"Download failed via requests and curl. requests={last_err}; curl={e2}",
            )

    size = out_path.stat().st_size
    return ExtraDownloadResult(
        name=r.name,
        url=r.url,
        out_path=str(out_path),
        bytes_written=size,
        sha256=sha256_file(out_path),
        ok=True,
    )


def download_doc(session: requests.Session, doc: Doc, out_path: Path) -> DownloadResult:
    url = doc.pdf_item_url
    if not url:
        url, title = resolve_pdf_item_and_title(session, doc.celex, doc.lang)
        doc.pdf_item_url = url
        doc.title = title
        # Publication date is best read from the work metadata.
        try:
            doc.publication_date = resolve_publication_date_for_celex(session, doc.celex) or doc.publication_date
        except Exception:
            doc.publication_date = doc.publication_date
        # Fallback from item sameAs if needed.
        if not doc.publication_date:
            try:
                sameas = resolve_item_sameas(session, url)
                doc.publication_date = extract_publication_date_from_sameas(sameas)
            except Exception:
                doc.publication_date = doc.publication_date

    if out_path.exists():
        try:
            with out_path.open("rb") as f:
                head = f.read(16)
            if is_pdf_bytes(head):
                size = out_path.stat().st_size
                return DownloadResult(
                    celex=doc.celex,
                    lang=doc.lang,
                    title=doc.title,
                    publication_date=doc.publication_date,
                    url=url,
                    out_path=str(out_path),
                    bytes_written=size,
                    sha256=sha256_file(out_path),
                    ok=True,
                )
        except Exception:
            # fall through to re-download
            pass

    last_err: Exception | None = None
    try:
        download_streaming_requests(session, url, out_path)
    except Exception as e:
        last_err = e
        try:
            tmp = out_path.with_suffix(out_path.suffix + ".part")
            if tmp.exists():
                tmp.unlink()
            download_via_curl(url, tmp)
            tmp.replace(out_path)
        except Exception as e2:
            raise RuntimeError(f"Download failed via requests and curl. requests={last_err}; curl={e2}")

    size = out_path.stat().st_size
    return DownloadResult(
        celex=doc.celex,
        lang=doc.lang,
        title=doc.title,
        publication_date=doc.publication_date,
        url=url,
        out_path=str(out_path),
        bytes_written=size,
        sha256=sha256_file(out_path),
        ok=True,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Download DORA regulations (incl. annexes) as PDFs")
    ap.add_argument("out_dir", nargs="?", default="dora_downloads", help="Output directory (default: dora_downloads)")
    ap.add_argument("--base-celex", default="32022R2554", help="Base act CELEX to start from (default: 32022R2554)")
    ap.add_argument("--lang", default="DEU", help="Language code (DEU, ENG, ...). Default: DEU")
    ap.add_argument(
        "--pinned",
        action="store_true",
        help="Only download the base CELEX (no discovery of derived acts)",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if the PDF already exists",
    )
    ap.add_argument(
        "--all",
        action="store_true",
        help="Download everything (DORA + ISO27001 + NIS2 + CRA; include NIS2UmsG if --nis2umsg-url is set)",
    )
    ap.add_argument(
        "--iso27001",
        action="store_true",
        help="Also download ISO/IEC 27001 audit/readiness questionnaires (PDF/XLSX)",
    )
    ap.add_argument(
        "--nis2",
        action="store_true",
        help="Also download NIS2 resources (EU NIS2 directive + optional DE BSIG PDF)",
    )
    ap.add_argument(
        "--nist2",
        action="store_true",
        help="Alias for --nis2 (common typo)",
    )
    ap.add_argument(
        "--cra",
        action="store_true",
        help="Also download CRA resources (EU Cyber Resilience Act regulation)",
    )
    ap.add_argument(
        "--nis2umsg",
        action="store_true",
        help="Also download NIS2 implementation act (NIS2UmsG) PDF (requires --nis2umsg-url)",
    )
    ap.add_argument(
        "--nis2umsg-url",
        default="",
        help="Direct PDF URL for the final NIS2UmsG publication (e.g. BGBl/official source)",
    )
    ap.add_argument(
        "--no-dora",
        action="store_true",
        help="Skip DORA downloads (useful with --iso27001/--nis2/--cra)",
    )
    args = ap.parse_args()

    if args.all:
        if args.no_dora:
            print("Invalid flag combination: --all cannot be used with --no-dora")
            return 2
        args.iso27001 = True
        args.nis2 = True
        args.cra = True
        if (args.nis2umsg_url or "").strip():
            args.nis2umsg = True
        else:
            # We cannot reliably discover the final PDF URL automatically.
            print("NOTE: --all does not download NIS2UmsG without --nis2umsg-url")

    if args.nist2 and not args.nis2:
        args.nis2 = True

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    base_celex = args.base_celex.strip().upper()
    if not args.no_dora:
        if not looks_like_celex(base_celex):
            print(f"Invalid CELEX format: {base_celex} (expected e.g. 32022R2554)")
            return 2

    lang = normalize_lang(args.lang)

    print(f"Downloading into: {out_dir.resolve()}")
    if not args.no_dora:
        print(f"Base CELEX:        {base_celex}")
        print(f"Language:          {lang}")

    session = build_requests_session()
    req_proxies = session.proxies or {}
    if req_proxies:
        print(f"(requests proxies) {req_proxies}")

    manifest_path = out_dir / "dora_manifest.json"
    results: list[DownloadResult] = []
    nis2_doc_results: list[DownloadResult] = []
    cra_doc_results: list[DownloadResult] = []
    ok = 0
    total = 0

    if not args.no_dora:
        # Discover derived acts (delegated/implementing regulations based on the base act)
        celexes: list[str] = [base_celex]
        if not args.pinned:
            try:
                base_work = resolve_work_uri_for_celex(session, base_celex)
                derived = discover_regulations_based_on(session, base_work)
                for c in derived:
                    if c not in celexes:
                        celexes.append(c)
            except Exception as e:
                print(f"WARNING: discovery failed, falling back to base only: {e}")

        docs: list[Doc] = []
        for c in celexes:
            kind = "DORA" if c == base_celex else "Derived"
            docs.append(Doc(title=f"CELEX {c}", celex=c, kind=kind, lang=lang))

        total += len(docs)

        for doc in docs:
            # First resolve metadata so we can compute a logical filename (incl. publication date)
            try:
                if not doc.pdf_item_url:
                    url, title = resolve_pdf_item_and_title(session, doc.celex, doc.lang)
                    doc.pdf_item_url = url
                    doc.title = title
                if not doc.publication_date:
                    doc.publication_date = resolve_publication_date_for_celex(session, doc.celex)
                if not doc.publication_date:
                    sameas = resolve_item_sameas(session, doc.pdf_item_url)
                    doc.publication_date = extract_publication_date_from_sameas(sameas)
            except Exception:
                # We'll still attempt download with a fallback filename.
                pass

            desired_name = compute_logical_filename(doc)
            out_path = out_dir / desired_name

            # Backward compatibility: if an older CELEX_LANG.pdf exists, rename it to the new name.
            legacy = out_dir / safe_filename(f"{doc.celex}_{doc.lang}.pdf")
            if legacy.exists() and not out_path.exists():
                try:
                    with legacy.open("rb") as f:
                        head = f.read(16)
                    if is_pdf_bytes(head):
                        legacy.replace(out_path)
                except Exception:
                    pass
            if args.force and out_path.exists():
                try:
                    out_path.unlink()
                except Exception:
                    pass
                part = out_path.with_suffix(out_path.suffix + ".part")
                if part.exists():
                    try:
                        part.unlink()
                    except Exception:
                        pass

            print(f"\n- [{doc.kind}] {doc.celex} ({doc.lang})")
            try:
                res = download_doc(session, doc, out_path)
                size_mb = res.bytes_written / (1024 * 1024)
                print(f"  {doc.title}")
                print(f"  -> {out_path}")
                print(f"  DONE ({size_mb:.2f} MB)")
                results.append(res)
                ok += 1
            except Exception as e:
                print(f"  FAILED: {e}")
                results.append(
                    DownloadResult(
                        celex=doc.celex,
                        lang=doc.lang,
                        title=doc.title,
                        publication_date=doc.publication_date,
                        url=doc.pdf_item_url or "",
                        out_path=str(out_path),
                        bytes_written=0,
                        sha256="",
                        ok=False,
                        error=str(e),
                    )
                )

    iso_results: list[ExtraDownloadResult] = []
    if args.iso27001:
        iso_dir = out_dir / "iso27001_questionnaires"
        iso_dir.mkdir(parents=True, exist_ok=True)
        resources: list[ExtraResource] = [
            ExtraResource(
                name="NQA ISO 27001 Gap Analysis (PDF)",
                url="https://www.nqa.com/medialibraries/NQA/NQA-Media-Library/PDFs/Final-27001-Gap-Analysis.pdf",
                filename="NQA_ISO27001_Gap_Analysis.pdf",
            ),
            ExtraResource(
                name="NSAI ISO/IEC 27001:2022 Readiness Questionnaire (XLSX)",
                url="https://www.nsai.ie/images/uploads/general/AD-27-05_-_NSAI_ISO_27001.2022_Readiness_Questionnaire_-_Rev_1_.01.xlsx",
                filename="NSAI_ISO27001_2022_Readiness_Questionnaire.xlsx",
            ),
            ExtraResource(
                name="Sprinto ISO 27001 Audit Checklist (PDF)",
                url="https://sprinto.com/wp-content/uploads/2025/09/Prepkit-ISO-27001-Audit-Checklist-LM.pdf",
                filename="Sprinto_ISO27001_Audit_Checklist.pdf",
            ),
            ExtraResource(
                name="SafetyCulture ISO 27001 Checklist Sample PDF Report (PDF)",
                url="https://assets.ctfassets.net/ueprkma36dz5/3ouQ2BmUcAFnuAbREOUFsB/c00fa46ed99db99c5f35cf8811b893c7/ISO_27001_Checklist_Sample_PDF_Report.pdf",
                filename="SafetyCulture_ISO27001_Checklist_Sample_Report.pdf",
            ),
        ]

        print("\nDownloading ISO/IEC 27001 resources into: " + str(iso_dir.resolve()))
        total += len(resources)
        for r in resources:
            print(f"\n- [ISO27001] {r.name}")
            res = download_extra_resource(session, r, iso_dir, force=bool(args.force))
            if res.ok:
                size_mb = res.bytes_written / (1024 * 1024)
                print(f"  -> {res.out_path}")
                print(f"  DONE ({size_mb:.2f} MB)")
                ok += 1
            else:
                print(f"  FAILED: {res.error}")
            iso_results.append(res)

    nis2_extra_results: list[ExtraDownloadResult] = []
    if args.nis2:
        nis2_dir = out_dir / "nis2_resources"
        nis2_dir.mkdir(parents=True, exist_ok=True)

        docs = [Doc(title="CELEX 32022L2555", celex="32022L2555", kind="NIS2", lang=lang)]
        total += len(docs)
        print("\nDownloading NIS2 resources into: " + str(nis2_dir.resolve()))
        for doc in docs:
            # Reuse the Publications Office flow to avoid EUR-Lex WAF challenges.
            out_path = nis2_dir / safe_filename(f"{doc.celex}_{doc.lang}.pdf")
            print(f"\n- [NIS2] {doc.celex} ({doc.lang})")
            try:
                res = download_doc(session, doc, out_path)
                size_mb = res.bytes_written / (1024 * 1024)
                print(f"  {doc.title}")
                print(f"  -> {out_path}")
                print(f"  DONE ({size_mb:.2f} MB)")
                nis2_doc_results.append(res)
                ok += 1
            except Exception as e:
                print(f"  FAILED: {e}")
                nis2_doc_results.append(
                    DownloadResult(
                        celex=doc.celex,
                        lang=doc.lang,
                        title=doc.title,
                        publication_date=doc.publication_date,
                        url=doc.pdf_item_url or "",
                        out_path=str(out_path),
                        bytes_written=0,
                        sha256="",
                        ok=False,
                        error=str(e),
                    )
                )

        # Germany: BSIG consolidated PDF (useful for NIS2 context).
        extras: list[ExtraResource] = [
            ExtraResource(
                name="DE BSIG (gesetze-im-internet.de) consolidated PDF",
                url="https://www.gesetze-im-internet.de/bsig_2025/BSIG.pdf",
                filename="DE_BSIG_2025.pdf",
            )
        ]
        total += len(extras)
        for r in extras:
            print(f"\n- [NIS2] {r.name}")
            res = download_extra_resource(session, r, nis2_dir, force=bool(args.force))
            if res.ok:
                size_mb = res.bytes_written / (1024 * 1024)
                print(f"  -> {res.out_path}")
                print(f"  DONE ({size_mb:.2f} MB)")
                ok += 1
            else:
                print(f"  FAILED: {res.error}")
            nis2_extra_results.append(res)

    if args.cra:
        cra_dir = out_dir / "cra_resources"
        cra_dir.mkdir(parents=True, exist_ok=True)

        docs = [Doc(title="CELEX 32024R2847", celex="32024R2847", kind="CRA", lang=lang)]
        total += len(docs)
        print("\nDownloading CRA resources into: " + str(cra_dir.resolve()))
        for doc in docs:
            # Reuse the Publications Office flow to avoid EUR-Lex WAF challenges.
            out_path = cra_dir / safe_filename(f"{doc.celex}_{doc.lang}.pdf")
            print(f"\n- [CRA] {doc.celex} ({doc.lang})")
            try:
                res = download_doc(session, doc, out_path)
                size_mb = res.bytes_written / (1024 * 1024)
                print(f"  {doc.title}")
                print(f"  -> {out_path}")
                print(f"  DONE ({size_mb:.2f} MB)")
                cra_doc_results.append(res)
                ok += 1
            except Exception as e:
                print(f"  FAILED: {e}")
                cra_doc_results.append(
                    DownloadResult(
                        celex=doc.celex,
                        lang=doc.lang,
                        title=doc.title,
                        publication_date=doc.publication_date,
                        url=doc.pdf_item_url or "",
                        out_path=str(out_path),
                        bytes_written=0,
                        sha256="",
                        ok=False,
                        error=str(e),
                    )
                )

    nis2umsg_results: list[ExtraDownloadResult] = []
    if args.nis2umsg:
        nis2umsg_dir = out_dir / "nis2umsg_resources"
        nis2umsg_dir.mkdir(parents=True, exist_ok=True)
        print("\nDownloading NIS2UmsG resources into: " + str(nis2umsg_dir.resolve()))

        url = (args.nis2umsg_url or "").strip()
        if not url:
            total += 1
            nis2umsg_results.append(
                ExtraDownloadResult(
                    name="DE NIS2UmsG final publication (PDF)",
                    url="",
                    out_path=str(nis2umsg_dir / "DE_NIS2UmsG.pdf"),
                    bytes_written=0,
                    sha256="",
                    ok=False,
                    error="Missing --nis2umsg-url (direct PDF URL required)",
                )
            )
        else:
            r = ExtraResource(
                name="DE NIS2UmsG final publication (PDF)",
                url=url,
                filename="DE_NIS2UmsG.pdf",
            )
            total += 1
            print(f"\n- [NIS2UmsG] {r.name}")
            res = download_extra_resource(session, r, nis2umsg_dir, force=bool(args.force))
            if res.ok:
                size_mb = res.bytes_written / (1024 * 1024)
                print(f"  -> {res.out_path}")
                print(f"  DONE ({size_mb:.2f} MB)")
                ok += 1
            else:
                print(f"  FAILED: {res.error}")
            nis2umsg_results.append(res)

    # Write manifest (best-effort)
    try:
        payload: dict[str, Any] = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "dora": {
                "enabled": (not args.no_dora),
                "base_celex": base_celex,
                "lang": lang,
                "results": [r.__dict__ for r in results],
            },
            "iso27001": {
                "enabled": bool(args.iso27001),
                "results": [r.__dict__ for r in iso_results],
            },
            "nis2": {
                "enabled": bool(args.nis2),
                "lang": lang,
                "docs": [r.__dict__ for r in nis2_doc_results],
                "extras": [r.__dict__ for r in nis2_extra_results],
            },
            "cra": {
                "enabled": bool(args.cra),
                "lang": lang,
                "docs": [r.__dict__ for r in cra_doc_results],
            },
            "nis2umsg": {
                "enabled": bool(args.nis2umsg),
                "results": [r.__dict__ for r in nis2umsg_results],
            },
        }
        manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
        print(f"\nManifest: {manifest_path}")
    except Exception as e:
        print(f"\nWARNING: could not write manifest: {e}")

    print(f"\nFinished: {ok}/{total} files downloaded.")
    return 0 if ok == total else 2


if __name__ == "__main__":
    raise SystemExit(main())
