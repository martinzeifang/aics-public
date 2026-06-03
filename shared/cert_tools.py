"""Zertifikats-Werkzeuge — Self-Signed-Generator + CSR (für PKI-Einreichung).

Reine Krypto-Funktionen auf Basis von `cryptography`. Keine Flask-/IO-Abhängigkeit
außer optionalem Schreiben von Dateien. Korrekte SAN-Behandlung: Hostnamen als
DNSName, IP-Adressen als IPAddress (der alte server/ssl.py-Generator trug IPs
fälschlich als DNSName ein → Browser akzeptierten sie nicht als IP-SAN).
"""

from __future__ import annotations

import ipaddress
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

VALID_KEY_SIZES = (2048, 3072, 4096)
_HOSTNAME_RE = re.compile(
    r'^(?=.{1,253}$)(\*\.)?([a-zA-Z0-9_](?:[a-zA-Z0-9_-]{0,61}[a-zA-Z0-9_])?)'
    r'(\.[a-zA-Z0-9_](?:[a-zA-Z0-9_-]{0,61}[a-zA-Z0-9_])?)*$'
)


# ─────────────────────────────────────────────────────────────────────────────
# Hilfen
# ─────────────────────────────────────────────────────────────────────────────

def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def classify_san(entries: list[str]) -> tuple[list[str], list[str]]:
    """Teilt eine gemischte Liste in (dns_names, ip_addresses) auf."""
    dns: list[str] = []
    ips: list[str] = []
    for raw in entries or []:
        v = (raw or '').strip()
        if not v:
            continue
        (ips if _is_ip(v) else dns).append(v)
    return dns, ips


def validate_san_inputs(dns_names: list[str], ip_addresses: list[str]) -> str | None:
    """Validiert SAN-Eingaben. Returns Fehlertext oder None (ok)."""
    for d in dns_names:
        if not _HOSTNAME_RE.match(d):
            return f"Ungültiger Hostname: {d!r}"
    for ip in ip_addresses:
        if not _is_ip(ip):
            return f"Ungültige IP-Adresse: {ip!r}"
    if not dns_names and not ip_addresses:
        return "Mindestens ein Hostname oder eine IP-Adresse ist erforderlich."
    return None


def _build_san(dns_names: list[str], ip_addresses: list[str]) -> x509.SubjectAlternativeName:
    sans: list[x509.GeneralName] = [x509.DNSName(d) for d in dns_names]
    sans += [x509.IPAddress(ipaddress.ip_address(ip)) for ip in ip_addresses]
    return x509.SubjectAlternativeName(sans)


def _build_subject(common_name: str, *, org: str = '', ou: str = '',
                   country: str = '', state: str = '', locality: str = '',
                   email: str = '') -> x509.Name:
    attrs = [x509.NameAttribute(NameOID.COMMON_NAME, common_name)]
    if org:
        attrs.append(x509.NameAttribute(NameOID.ORGANIZATION_NAME, org))
    if ou:
        attrs.append(x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, ou))
    if country:
        # X.509 verlangt 2-Buchstaben-Ländercode
        attrs.append(x509.NameAttribute(NameOID.COUNTRY_NAME, country[:2].upper()))
    if state:
        attrs.append(x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, state))
    if locality:
        attrs.append(x509.NameAttribute(NameOID.LOCALITY_NAME, locality))
    if email:
        attrs.append(x509.NameAttribute(NameOID.EMAIL_ADDRESS, email))
    return x509.Name(attrs)


def _key_to_pem(key: rsa.RSAPrivateKey) -> bytes:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Self-Signed-Zertifikat
# ─────────────────────────────────────────────────────────────────────────────

def generate_self_signed(
    common_name: str,
    dns_names: list[str] | None = None,
    ip_addresses: list[str] | None = None,
    validity_days: int = 397,
    key_size: int = 3072,
    organization: str = 'AI Compliance Suite',
) -> dict[str, bytes]:
    """Erzeugt ein selbstsigniertes Server-Zertifikat (mit korrekten SANs).

    #742-Defaults (secure-by-default):
    - key_size=3072 (statt 2048) — RSA-3072 ≈ 128-Bit-Sicherheitsniveau.
    - validity_days=397 — entspricht dem CA/Browser-Forum-Maximum (~13 Monate);
      kürzere Laufzeit begrenzt das Risiko kompromittierter Schlüssel.
      RENEWAL-HINT: Self-Signed-Certs rechtzeitig vor Ablauf erneuern
      (z.B. via Cert-Wizard /self-signed/generate) und mit /apply aktivieren.

    Returns {'cert_pem': bytes, 'key_pem': bytes}.
    """
    common_name = (common_name or '').strip()
    if not common_name:
        raise ValueError("common_name (Hostname) ist erforderlich")
    if key_size not in VALID_KEY_SIZES:
        raise ValueError(f"key_size muss eine von {VALID_KEY_SIZES} sein")
    if not (1 <= int(validity_days) <= 3650):
        raise ValueError("validity_days muss zwischen 1 und 3650 liegen")

    dns_names = list(dns_names or [])
    ip_addresses = list(ip_addresses or [])
    # CN immer als SAN aufnehmen (moderne Browser ignorieren CN ohne SAN-Match)
    if _is_ip(common_name):
        if common_name not in ip_addresses:
            ip_addresses.insert(0, common_name)
    elif common_name not in dns_names:
        dns_names.insert(0, common_name)

    err = validate_san_inputs(dns_names, ip_addresses)
    if err:
        raise ValueError(err)

    key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    subject = issuer = _build_subject(common_name, org=organization, country='DE')
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=int(validity_days)))
        .add_extension(_build_san(dns_names, ip_addresses), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, key_encipherment=True, content_commitment=False,
                data_encipherment=False, key_agreement=False, key_cert_sign=False,
                crl_sign=False, encipher_only=False, decipher_only=False,
            ), critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    return {
        'cert_pem': cert.public_bytes(serialization.Encoding.PEM),
        'key_pem': _key_to_pem(key),
    }


# ─────────────────────────────────────────────────────────────────────────────
# CSR (Certificate Signing Request) — für PKI-Einreichung
# ─────────────────────────────────────────────────────────────────────────────

def generate_csr(
    common_name: str,
    dns_names: list[str] | None = None,
    ip_addresses: list[str] | None = None,
    key_size: int = 3072,  # #742: RSA-3072 als secure-by-default
    organization: str = '',
    organizational_unit: str = '',
    country: str = '',
    state: str = '',
    locality: str = '',
    email: str = '',
) -> dict[str, bytes]:
    """Erzeugt Schlüsselpaar + CSR (PKCS#10) zur Einreichung bei einer PKI.

    Returns {'csr_pem': bytes, 'key_pem': bytes}.
    """
    common_name = (common_name or '').strip()
    if not common_name:
        raise ValueError("common_name (Hostname) ist erforderlich")
    if key_size not in VALID_KEY_SIZES:
        raise ValueError(f"key_size muss eine von {VALID_KEY_SIZES} sein")

    dns_names = list(dns_names or [])
    ip_addresses = list(ip_addresses or [])
    if _is_ip(common_name):
        if common_name not in ip_addresses:
            ip_addresses.insert(0, common_name)
    elif common_name not in dns_names:
        dns_names.insert(0, common_name)

    err = validate_san_inputs(dns_names, ip_addresses)
    if err:
        raise ValueError(err)

    key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    subject = _build_subject(
        common_name, org=organization, ou=organizational_unit,
        country=country, state=state, locality=locality, email=email,
    )
    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(subject)
        .add_extension(_build_san(dns_names, ip_addresses), critical=False)
        .sign(key, hashes.SHA256())
    )
    return {
        'csr_pem': csr.public_bytes(serialization.Encoding.PEM),
        'key_pem': _key_to_pem(key),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Parsen / Validieren
# ─────────────────────────────────────────────────────────────────────────────

def _san_strings(cert_or_csr) -> list[str]:
    try:
        ext = cert_or_csr.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    except x509.ExtensionNotFound:
        return []
    out: list[str] = []
    for gn in ext.value:
        if isinstance(gn, x509.DNSName):
            out.append(gn.value)
        elif isinstance(gn, x509.IPAddress):
            out.append(str(gn.value))
    return out


def parse_cert_info(cert_pem: bytes) -> dict[str, Any]:
    """Liest Metadaten eines Zertifikats (PEM) aus — für die UI-Anzeige."""
    cert = x509.load_pem_x509_certificate(cert_pem)
    try:
        cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    except (IndexError, x509.ExtensionNotFound):
        cn = ''
    try:
        issuer_cn = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    except (IndexError, x509.ExtensionNotFound):
        issuer_cn = ''
    fp = cert.fingerprint(hashes.SHA256()).hex(':').upper()
    return {
        'common_name': cn,
        'issuer_cn': issuer_cn,
        'self_signed': cert.issuer == cert.subject,
        'sans': _san_strings(cert),
        'not_before': cert.not_valid_before_utc.isoformat(),
        'not_after': cert.not_valid_after_utc.isoformat(),
        'serial': format(cert.serial_number, 'x'),
        'sha256_fingerprint': fp,
        'key_size': getattr(cert.public_key(), 'key_size', None),
    }


def parse_csr_info(csr_pem: bytes) -> dict[str, Any]:
    csr = x509.load_pem_x509_csr(csr_pem)
    try:
        cn = csr.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    except IndexError:
        cn = ''
    return {
        'common_name': cn,
        'sans': _san_strings(csr),
        'signature_valid': csr.is_signature_valid,
    }


def cert_matches_key(cert_pem: bytes, key_pem: bytes) -> bool:
    """Prüft, ob ein (von der PKI signiertes) Zertifikat zum privaten Schlüssel passt."""
    try:
        cert = x509.load_pem_x509_certificate(cert_pem)
        key = serialization.load_pem_private_key(key_pem, password=None)
    except Exception:
        return False
    cert_pub = cert.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    key_pub = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return cert_pub == key_pub


def is_valid_cert_pem(cert_pem: bytes) -> bool:
    try:
        x509.load_pem_x509_certificate(cert_pem)
        return True
    except Exception:
        return False
