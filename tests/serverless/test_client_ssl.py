"""Unit tests for Serverless.get_ssl_context – specifically the VERIFY_X509_STRICT fix."""
import ssl

import pytest
from cryptography.x509 import load_pem_x509_certificate
from OpenSSL.crypto import (
    X509,
    X509Store,
    X509StoreContext,
    X509StoreFlags,
)

from vastai.serverless.client.client import Serverless


def _verify_leaf_with_ca(ca_pem: bytes, leaf_pem: bytes, *, strict: bool) -> None:
    """Verify a leaf cert against a CA using OpenSSL's X509Store (raises on failure)."""

    def _to_openssl(pem: bytes) -> X509:
        c = load_pem_x509_certificate(pem)
        return X509.from_cryptography(c)

    store = X509Store()
    store.add_cert(_to_openssl(ca_pem))
    if strict:
        store.set_flags(X509StoreFlags.X509_STRICT)

    ctx = X509StoreContext(store, _to_openssl(leaf_pem))
    ctx.verify_certificate()


class TestGetSslContextClearsX509Strict:
    """Verify that get_ssl_context clears VERIFY_X509_STRICT on the SSL context."""

    @pytest.mark.asyncio
    async def test_verify_x509_strict_is_cleared(
        self,
        serverless_ssl_self_signed_cert_pem,
        patch_serverless_ssl_cert_download,
    ) -> None:
        """The SSL context returned by get_ssl_context must NOT have VERIFY_X509_STRICT set."""
        client = Serverless(api_key="test-key")

        with patch_serverless_ssl_cert_download(serverless_ssl_self_signed_cert_pem):
            ctx = await client.get_ssl_context()

        assert not (ctx.verify_flags & ssl.VERIFY_X509_STRICT), (
            "VERIFY_X509_STRICT should be cleared so the Vast.ai root CA is accepted"
        )

    @pytest.mark.asyncio
    async def test_ssl_context_still_verifies_certs(
        self,
        serverless_ssl_self_signed_cert_pem,
        patch_serverless_ssl_cert_download,
    ) -> None:
        """Clearing X509_STRICT must not disable certificate verification entirely."""
        client = Serverless(api_key="test-key")

        with patch_serverless_ssl_cert_download(serverless_ssl_self_signed_cert_pem):
            ctx = await client.get_ssl_context()

        assert ctx.verify_mode == ssl.CERT_REQUIRED
        assert ctx.check_hostname is True

    @pytest.mark.asyncio
    async def test_ssl_context_is_cached(
        self,
        serverless_ssl_self_signed_cert_pem,
        patch_serverless_ssl_cert_download,
    ) -> None:
        """get_ssl_context should return the same context on subsequent calls."""
        client = Serverless(api_key="test-key")

        with patch_serverless_ssl_cert_download(serverless_ssl_self_signed_cert_pem):
            ctx1 = await client.get_ssl_context()
            ctx2 = await client.get_ssl_context()

        assert ctx1 is ctx2


class TestCaWithoutKeyCertSign:
    """Verify that a CA cert with BasicConstraints(ca=True, path_length=0) but
    *without* keyCertSign in Key Usage is accepted when VERIFY_X509_STRICT is
    cleared — reproducing the exact condition of the Vast.ai root CA."""

    def test_strict_rejects_ca_without_key_cert_sign(
        self, serverless_ssl_ca_chain_without_key_cert_sign
    ) -> None:
        """With X509_STRICT, OpenSSL rejects the CA that lacks keyCertSign."""
        from OpenSSL.crypto import X509StoreContextError

        ca_pem, leaf_pem, _leaf_key_pem = serverless_ssl_ca_chain_without_key_cert_sign

        with pytest.raises(X509StoreContextError, match="keyCertSign|invalid CA"):
            _verify_leaf_with_ca(ca_pem, leaf_pem, strict=True)

    def test_non_strict_accepts_ca_without_key_cert_sign(
        self, serverless_ssl_ca_chain_without_key_cert_sign
    ) -> None:
        """Without X509_STRICT the same CA+leaf chain is accepted — this is
        the behaviour that get_ssl_context enables by clearing the flag."""
        ca_pem, leaf_pem, _leaf_key_pem = serverless_ssl_ca_chain_without_key_cert_sign

        _verify_leaf_with_ca(ca_pem, leaf_pem, strict=False)

    @pytest.mark.asyncio
    async def test_get_ssl_context_accepts_ca_without_key_cert_sign(
        self,
        serverless_ssl_ca_chain_without_key_cert_sign,
        patch_serverless_ssl_cert_download,
    ) -> None:
        """get_ssl_context clears VERIFY_X509_STRICT, so the context won't
        have the strict flag that would reject this CA."""
        ca_pem, _leaf_pem, _leaf_key_pem = serverless_ssl_ca_chain_without_key_cert_sign

        client = Serverless(api_key="test-key")
        with patch_serverless_ssl_cert_download(ca_pem):
            ctx = await client.get_ssl_context()

        assert not (ctx.verify_flags & ssl.VERIFY_X509_STRICT)
