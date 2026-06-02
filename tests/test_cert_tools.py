"""Tests für shared/cert_tools.py — Self-Signed + CSR + Parsen + Key-Match."""

import ipaddress

import pytest
from cryptography import x509
from cryptography.x509.oid import NameOID

from shared import cert_tools as ct


class TestClassifyAndValidate:
    def test_classify_san(self):
        dns, ips = ct.classify_san(['host.local', '192.168.1.10', '', 'a.b.c', '::1'])
        assert dns == ['host.local', 'a.b.c']
        assert ips == ['192.168.1.10', '::1']

    def test_validate_ok(self):
        assert ct.validate_san_inputs(['host.local'], ['10.0.0.1']) is None

    def test_validate_bad_ip(self):
        assert 'IP' in ct.validate_san_inputs([], ['999.1.1.1'])

    def test_validate_bad_host(self):
        assert 'Hostname' in ct.validate_san_inputs(['bad host!'], [])

    def test_validate_empty(self):
        assert ct.validate_san_inputs([], []) is not None


class TestSelfSigned:
    def test_basic(self):
        out = ct.generate_self_signed('aics.intern.local', key_size=2048, validity_days=365)
        assert out['cert_pem'].startswith(b'-----BEGIN CERTIFICATE-----')
        assert out['key_pem'].startswith(b'-----BEGIN RSA PRIVATE KEY-----')
        info = ct.parse_cert_info(out['cert_pem'])
        assert info['common_name'] == 'aics.intern.local'
        assert info['self_signed'] is True
        assert 'aics.intern.local' in info['sans']
        assert info['key_size'] == 2048

    def test_ip_san_is_iptype(self):
        """IP muss als echte IPAddress-SAN gespeichert sein, nicht als DNSName."""
        out = ct.generate_self_signed('aics.example.com', ip_addresses=['10.0.0.5'])
        cert = x509.load_pem_x509_certificate(out['cert_pem'])
        ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        ip_sans = ext.value.get_values_for_type(x509.IPAddress)
        assert ipaddress.ip_address('aics.example.com') in ip_sans
        assert ipaddress.ip_address('10.0.0.5') in ip_sans

    def test_hostname_plus_ip(self):
        out = ct.generate_self_signed('aics.local', dns_names=['www.aics.local'],
                                      ip_addresses=['192.168.1.50'])
        info = ct.parse_cert_info(out['cert_pem'])
        assert {'aics.local', 'www.aics.local', '192.168.1.50'} <= set(info['sans'])

    def test_key_matches_cert(self):
        out = ct.generate_self_signed('host.local')
        assert ct.cert_matches_key(out['cert_pem'], out['key_pem']) is True

    def test_invalid_key_size(self):
        with pytest.raises(ValueError):
            ct.generate_self_signed('host.local', key_size=1024)

    def test_invalid_validity(self):
        with pytest.raises(ValueError):
            ct.generate_self_signed('host.local', validity_days=99999)

    def test_empty_cn(self):
        with pytest.raises(ValueError):
            ct.generate_self_signed('')


class TestCSR:
    def test_basic_csr(self):
        out = ct.generate_csr('aics.example.com', organization='ACME GmbH',
                              country='DE', email='admin@acme.de')
        assert out['csr_pem'].startswith(b'-----BEGIN CERTIFICATE REQUEST-----')
        info = ct.parse_csr_info(out['csr_pem'])
        assert info['common_name'] == 'aics.example.com'
        assert info['signature_valid'] is True
        assert 'aics.example.com' in info['sans']

    def test_csr_subject_fields(self):
        out = ct.generate_csr('h.local', organization='Org', organizational_unit='IT',
                             country='DE', state='BW', locality='KA')
        csr = x509.load_pem_x509_csr(out['csr_pem'])
        assert csr.subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)[0].value == 'Org'
        assert csr.subject.get_attributes_for_oid(NameOID.COUNTRY_NAME)[0].value == 'DE'

    def test_csr_ip_san(self):
        out = ct.generate_csr('10.0.0.9')
        csr = x509.load_pem_x509_csr(out['csr_pem'])
        ext = csr.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        assert ipaddress.ip_address('10.0.0.9') in ext.value.get_values_for_type(x509.IPAddress)


class TestMatching:
    def test_cert_matches_correct_key(self):
        out = ct.generate_self_signed('a.local')
        assert ct.cert_matches_key(out['cert_pem'], out['key_pem'])

    def test_cert_mismatch_other_key(self):
        a = ct.generate_self_signed('a.local')
        b = ct.generate_self_signed('b.local')
        assert ct.cert_matches_key(a['cert_pem'], b['key_pem']) is False

    def test_is_valid_cert_pem(self):
        out = ct.generate_self_signed('a.local')
        assert ct.is_valid_cert_pem(out['cert_pem']) is True
        assert ct.is_valid_cert_pem(b'not a cert') is False
