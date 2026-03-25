"""Unit tests for Serverless.get_ssl_context – specifically the VERIFY_X509_STRICT fix."""
import datetime
import ssl
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from vastai.serverless.client.client import Serverless

_NOW = datetime.datetime.now(datetime.UTC)


def _generate_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _dummy_cert_bytes() -> bytes:
    """A self-signed PEM cert used only to satisfy load_verify_locations."""
    key = _generate_key()
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_NOW)
        .not_valid_after(_NOW + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM)


def _make_ca_and_leaf_without_key_cert_sign():
    """Create a CA cert that has BasicConstraints(ca=True, path_length=0) but
    no Key Usage extension at all — mimicking the Vast.ai root CA that
    OpenSSL 3.x rejects under VERIFY_X509_STRICT with:
    "Path length given without key usage keyCertSign".

    Returns (ca_pem_bytes, leaf_pem_bytes, leaf_key_pem_bytes).
    """
    ca_key = _generate_key()
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test CA (no keyCertSign)")])

    # BasicConstraints says "I am a CA" with pathlen=0, but there is no
    # Key Usage extension → VERIFY_X509_STRICT considers this invalid.
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_NOW)
        .not_valid_after(_NOW + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )

    leaf_key = _generate_key()
    leaf_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    leaf_cert = (
        x509.CertificateBuilder()
        .subject_name(leaf_name)
        .issuer_name(ca_name)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_NOW)
        .not_valid_after(_NOW + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )

    ca_pem = ca_cert.public_bytes(serialization.Encoding.PEM)
    leaf_pem = leaf_cert.public_bytes(serialization.Encoding.PEM)
    leaf_key_pem = leaf_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    return ca_pem, leaf_pem, leaf_key_pem


def _verify_leaf_with_ca(ca_pem: bytes, leaf_pem: bytes, *, strict: bool) -> None:
    """Verify a leaf cert against a CA using OpenSSL's X509Store.

    Raises X509StoreContextError if verification fails.
    """
    from cryptography.x509 import load_pem_x509_certificate
    from OpenSSL.crypto import (
        X509,
        X509Store,
        X509StoreContext,
        X509StoreFlags,
    )

    # Convert cryptography certs to pyOpenSSL X509 objects
    def _to_openssl(pem: bytes) -> X509:
        c = load_pem_x509_certificate(pem)
        return X509.from_cryptography(c)

    store = X509Store()
    store.add_cert(_to_openssl(ca_pem))
    if strict:
        store.set_flags(X509StoreFlags.X509_STRICT)

    ctx = X509StoreContext(store, _to_openssl(leaf_pem))
    ctx.verify_certificate()  # raises X509StoreContextError on failure


@pytest.fixture
def cert_bytes():
    return _dummy_cert_bytes()


def _mock_cert_download(cert_bytes: bytes):
    """Return a patch that makes the cert-download GET return cert_bytes."""
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.read = AsyncMock(return_value=cert_bytes)

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_session_ctx)

    mock_session_outer = AsyncMock()
    mock_session_outer.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_outer.__aexit__ = AsyncMock(return_value=False)

    return patch("vastai.serverless.client.client.aiohttp.ClientSession", return_value=mock_session_outer)


class TestGetSslContextClearsX509Strict:
    """Verify that get_ssl_context clears VERIFY_X509_STRICT on the SSL context."""

    @pytest.mark.asyncio
    async def test_verify_x509_strict_is_cleared(self, cert_bytes: bytes) -> None:
        """The SSL context returned by get_ssl_context must NOT have VERIFY_X509_STRICT set."""
        client = Serverless(api_key="test-key")

        with _mock_cert_download(cert_bytes):
            ctx = await client.get_ssl_context()

        assert not (ctx.verify_flags & ssl.VERIFY_X509_STRICT), (
            "VERIFY_X509_STRICT should be cleared so the Vast.ai root CA is accepted"
        )

    @pytest.mark.asyncio
    async def test_ssl_context_still_verifies_certs(self, cert_bytes: bytes) -> None:
        """Clearing X509_STRICT must not disable certificate verification entirely."""
        client = Serverless(api_key="test-key")

        with _mock_cert_download(cert_bytes):
            ctx = await client.get_ssl_context()

        assert ctx.verify_mode == ssl.CERT_REQUIRED
        assert ctx.check_hostname is True

    @pytest.mark.asyncio
    async def test_ssl_context_is_cached(self, cert_bytes: bytes) -> None:
        """get_ssl_context should return the same context on subsequent calls."""
        client = Serverless(api_key="test-key")

        with _mock_cert_download(cert_bytes):
            ctx1 = await client.get_ssl_context()
            ctx2 = await client.get_ssl_context()

        assert ctx1 is ctx2


class TestCaWithoutKeyCertSign:
    """Verify that a CA cert with BasicConstraints(ca=True, path_length=0) but
    *without* keyCertSign in Key Usage is accepted when VERIFY_X509_STRICT is
    cleared — reproducing the exact condition of the Vast.ai root CA."""

    @pytest.fixture
    def ca_chain(self):
        return _make_ca_and_leaf_without_key_cert_sign()

    def test_strict_rejects_ca_without_key_cert_sign(self, ca_chain) -> None:
        """With X509_STRICT, OpenSSL rejects the CA that lacks keyCertSign."""
        from OpenSSL.crypto import X509StoreContextError

        ca_pem, leaf_pem, _leaf_key_pem = ca_chain

        with pytest.raises(X509StoreContextError, match="keyCertSign|invalid CA"):
            _verify_leaf_with_ca(ca_pem, leaf_pem, strict=True)

    def test_non_strict_accepts_ca_without_key_cert_sign(self, ca_chain) -> None:
        """Without X509_STRICT the same CA+leaf chain is accepted — this is
        the behaviour that get_ssl_context enables by clearing the flag."""
        ca_pem, leaf_pem, _leaf_key_pem = ca_chain

        # Should not raise
        _verify_leaf_with_ca(ca_pem, leaf_pem, strict=False)

    @pytest.mark.asyncio
    async def test_get_ssl_context_accepts_ca_without_key_cert_sign(self, ca_chain) -> None:
        """get_ssl_context clears VERIFY_X509_STRICT, so the context won't
        have the strict flag that would reject this CA."""
        ca_pem, _leaf_pem, _leaf_key_pem = ca_chain

        client = Serverless(api_key="test-key")
        with _mock_cert_download(ca_pem):
            ctx = await client.get_ssl_context()

        assert not (ctx.verify_flags & ssl.VERIFY_X509_STRICT)
