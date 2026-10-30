"""SSL/TLS Certificate Generation & Management.

Auto-generates self-signed certificates for development/testing.
For production, use real certificates from a CA.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timedelta
import logging

try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID, ExtensionOID
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PrivateFormat, NoEncryption, PublicFormat
    )
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


logger = logging.getLogger(__name__)


def generate_self_signed_cert(
    cert_dir: Path,
    validity_days: int = 365,
    common_name: str = "localhost",
) -> tuple[Path, Path]:
    """Generate self-signed certificate and private key.

    Args:
        cert_dir: Directory to store certificates
        validity_days: Certificate validity period
        common_name: Certificate common name (usually domain)

    Returns:
        Tuple of (cert_path, key_path)

    Raises:
        RuntimeError: If cryptography not installed
    """
    if not CRYPTO_AVAILABLE:
        raise RuntimeError(
            "cryptography library required for certificate generation. "
            "Install with: pip install cryptography"
        )

    cert_dir.mkdir(parents=True, exist_ok=True)
    cert_path = cert_dir / "certificate.crt"
    key_path = cert_dir / "private.key"

    logger.info(f"Generating self-signed certificate for {common_name}...")

    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Generate certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AI Compliance Suite"),
        x509.NameAttribute(NameOID.COUNTRY_NAME, "DE"),
    ])

    # Subject Alternative Names
    san = x509.SubjectAlternativeName([
        x509.DNSName("localhost"),
        x509.DNSName("127.0.0.1"),
        x509.DNSName("*.localhost"),
        x509.DNSName(common_name),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=validity_days))
        .add_extension(san, critical=False)
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .sign(private_key, hashes.SHA256())
    )

    # Write private key
    with open(key_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=NoEncryption(),
        ))
    key_path.chmod(0o600)  # Only readable by owner
    logger.info(f"✓ Private key: {key_path}")

    # Write certificate
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(Encoding.PEM))
    logger.info(f"✓ Certificate: {cert_path}")

    return cert_path, key_path


def ensure_ssl_certs(
    cert_dir: Path,
    regenerate: bool = False,
) -> tuple[Path, Path]:
    """Ensure SSL certificates exist, generate if missing.

    Args:
        cert_dir: Directory for certificates
        regenerate: Force regeneration even if exists

    Returns:
        Tuple of (cert_path, key_path)
    """
    cert_dir.mkdir(parents=True, exist_ok=True)
    cert_path = cert_dir / "certificate.crt"
    key_path = cert_dir / "private.key"

    if cert_path.exists() and key_path.exists() and not regenerate:
        logger.info(f"✓ Using existing certificates")
        return cert_path, key_path

    if regenerate:
        logger.info("Regenerating certificates...")
        cert_path.unlink(missing_ok=True)
        key_path.unlink(missing_ok=True)

    return generate_self_signed_cert(cert_dir)


def verify_cert_validity(cert_path: Path) -> bool:
    """Check if certificate is still valid.

    Args:
        cert_path: Path to certificate file

    Returns:
        True if valid, False if expired or missing
    """
    if not cert_path.exists():
        return False

    if not CRYPTO_AVAILABLE:
        logger.warning("cryptography not available, skipping cert validation")
        return True

    try:
        with open(cert_path, "rb") as f:
            cert_data = f.read()
        cert = x509.load_pem_x509_certificate(cert_data)
        return cert.not_valid_after > datetime.utcnow()
    except Exception as e:
        logger.error(f"Certificate validation failed: {e}")
        return False
