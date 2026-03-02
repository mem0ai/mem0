"""
Tests for URL Security utilities (SSRF prevention).
"""

import ipaddress
import pytest
from unittest.mock import patch, MagicMock

from embedchain.utils.url_security import (
    SSRFSecurityError,
    is_ip_blocked,
    is_hostname_blocked,
    validate_url,
    get_allowed_url,
)


class TestIsIPBlocked:
    """Tests for is_ip_blocked function."""

    def test_private_ipv4_10_range(self):
        """Test that 10.0.0.0/8 range is blocked."""
        assert is_ip_blocked("10.0.0.1") is True
        assert is_ip_blocked("10.255.255.255") is True
        assert is_ip_blocked("10.123.45.67") is True

    def test_private_ipv4_172_range(self):
        """Test that 172.16.0.0/12 range is blocked."""
        assert is_ip_blocked("172.16.0.1") is True
        assert is_ip_blocked("172.31.255.255") is True
        assert is_ip_blocked("172.20.0.1") is True
        # 172.15.x.x and 172.32.x.x should NOT be blocked
        assert is_ip_blocked("172.15.0.1") is False
        assert is_ip_blocked("172.32.0.1") is False

    def test_private_ipv4_192_range(self):
        """Test that 192.168.0.0/16 range is blocked."""
        assert is_ip_blocked("192.168.0.1") is True
        assert is_ip_blocked("192.168.255.255") is True
        assert is_ip_blocked("192.168.100.50") is True

    def test_loopback_ipv4(self):
        """Test that 127.0.0.0/8 range is blocked."""
        assert is_ip_blocked("127.0.0.1") is True
        assert is_ip_blocked("127.0.0.255") is True
        assert is_ip_blocked("127.255.255.255") is True

    def test_link_local_ipv4(self):
        """Test that 169.254.0.0/10 range is blocked (includes cloud metadata)."""
        assert is_ip_blocked("169.254.0.1") is True
        assert is_ip_blocked("169.254.169.254") is True  # Cloud metadata
        assert is_ip_blocked("169.254.255.255") is True

    def test_ipv6_loopback(self):
        """Test that IPv6 loopback is blocked."""
        assert is_ip_blocked("::1") is True

    def test_ipv6_link_local(self):
        """Test that IPv6 link-local is blocked."""
        assert is_ip_blocked("fe80::1") is True
        assert is_ip_blocked("fe80::ffff") is True

    def test_public_ips_not_blocked(self):
        """Test that public IPs are not blocked."""
        assert is_ip_blocked("8.8.8.8") is False  # Google DNS
        assert is_ip_blocked("1.1.1.1") is False  # Cloudflare DNS
        assert is_ip_blocked("93.184.216.34") is False  # example.com

    def test_invalid_ip(self):
        """Test that invalid IPs are treated as blocked."""
        assert is_ip_blocked("not-an-ip") is True
        assert is_ip_blocked("256.256.256.256") is True

    def test_custom_blocked_ranges(self):
        """Test custom blocked ranges."""
        custom_ranges = [ipaddress.ip_network("1.2.3.0/24")]
        assert is_ip_blocked("1.2.3.4", custom_ranges) is True
        assert is_ip_blocked("1.2.4.1", custom_ranges) is False


class TestIsHostnameBlocked:
    """Tests for is_hostname_blocked function."""

    def test_localhost_blocked(self):
        """Test that localhost is blocked."""
        assert is_hostname_blocked("localhost") is True

    def test_localhost_variants_blocked(self):
        """Test that localhost variants are blocked."""
        assert is_hostname_blocked("localhost.localdomain") is True
        assert is_hostname_blocked("local") is True
        assert is_hostname_blocked("ip6-localhost") is True

    def test_internal_hostnames_blocked(self):
        """Test that internal hostnames are blocked."""
        assert is_hostname_blocked("metadata.google.internal") is True
        assert is_hostname_blocked("kubernetes.default") is True

    def test_local_suffix_blocked(self):
        """Test that hostnames ending in .local are blocked."""
        assert is_hostname_blocked("myserver.local") is True
        assert is_hostname_blocked("test.localhost") is True
        assert is_hostname_blocked("something.internal") is True

    def test_public_hostnames_not_blocked(self):
        """Test that public hostnames are not blocked."""
        assert is_hostname_blocked("example.com") is False
        assert is_hostname_blocked("google.com") is False
        assert is_hostname_blocked("github.com") is False


class TestValidateUrl:
    """Tests for validate_url function."""

    def test_valid_http_url(self):
        """Test that valid HTTP URLs pass validation."""
        url = "http://example.com/path"
        assert validate_url(url) == url

    def test_valid_https_url(self):
        """Test that valid HTTPS URLs pass validation."""
        url = "https://example.com/path"
        assert validate_url(url) == url

    def test_invalid_scheme(self):
        """Test that non-HTTP(S) schemes are blocked."""
        with pytest.raises(SSRFSecurityError) as exc_info:
            validate_url("file:///etc/passwd")
        assert "scheme" in str(exc_info.value).lower()

        with pytest.raises(SSRFSecurityError) as exc_info:
            validate_url("ftp://example.com/file")
        assert "scheme" in str(exc_info.value).lower()

    def test_localhost_blocked(self):
        """Test that localhost URLs are blocked."""
        with pytest.raises(SSRFSecurityError):
            validate_url("http://localhost/admin")

        with pytest.raises(SSRFSecurityError):
            validate_url("http://127.0.0.1/admin")

    def test_private_ip_blocked(self):
        """Test that private IP URLs are blocked."""
        with pytest.raises(SSRFSecurityError):
            validate_url("http://192.168.1.1/")

        with pytest.raises(SSRFSecurityError):
            validate_url("http://10.0.0.1/")

        with pytest.raises(SSRFSecurityError):
            validate_url("http://172.16.0.1/")

    def test_cloud_metadata_blocked(self):
        """Test that cloud metadata endpoints are blocked."""
        with pytest.raises(SSRFSecurityError):
            validate_url("http://169.254.169.254/latest/meta-data/")

    def test_allowed_hosts_bypass(self):
        """Test that allowed_hosts bypass security checks."""
        url = "http://localhost:8080/api"
        # Should raise without allowed_hosts
        with pytest.raises(SSRFSecurityError):
            validate_url(url)

        # Should pass with allowed_hosts
        assert validate_url(url, allowed_hosts=["localhost"]) == url

    def test_allow_private_ips_flag(self):
        """Test that allow_private_ips flag allows private IPs."""
        url = "http://192.168.1.1/api"

        # Should raise by default
        with pytest.raises(SSRFSecurityError):
            validate_url(url)

        # Should pass with allow_private_ips
        assert validate_url(url, allow_private_ips=True) == url

    def test_missing_hostname(self):
        """Test that URLs without hostname are rejected."""
        with pytest.raises(SSRFSecurityError):
            validate_url("http:///path")


class TestGetAllowedUrl:
    """Tests for get_allowed_url function."""

    @patch("embedchain.utils.url_security.requests.Session")
    def test_successful_request(self, mock_session_class):
        """Test successful request to allowed URL."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"test content"
        mock_response.url = "https://example.com/"
        mock_response.history = []
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        response = get_allowed_url("https://example.com/", session=mock_session)
        assert response.status_code == 200

    @patch("embedchain.utils.url_security.requests.Session")
    def test_blocked_url_raises_error(self, mock_session_class):
        """Test that blocked URLs raise SSRFSecurityError."""
        with pytest.raises(SSRFSecurityError):
            get_allowed_url("http://localhost/admin")

    @patch("embedchain.utils.url_security.requests.Session")
    def test_redirect_to_blocked_url_blocked(self, mock_session_class):
        """Test that redirects to blocked URLs are blocked."""
        mock_session = MagicMock()

        # First response (redirect)
        redirect_response = MagicMock()
        redirect_response.status_code = 302
        redirect_response.headers = {"Location": "http://169.254.169.254/"}
        redirect_response.url = "https://attacker.com/"

        # Final response
        final_response = MagicMock()
        final_response.status_code = 200
        final_response.url = "http://169.254.169.254/"
        final_response.history = [redirect_response]

        mock_session.get.return_value = final_response

        with pytest.raises(SSRFSecurityError):
            get_allowed_url("https://attacker.com/redirect", session=mock_session)


class TestSSRFSecurityError:
    """Tests for SSRFSecurityError exception."""

    def test_error_message(self):
        """Test that error message is properly formatted."""
        error = SSRFSecurityError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)


class TestIntegration:
    """Integration tests for SSRF protection."""

    def test_web_page_loader_blocks_ssrf(self):
        """Test that WebPageLoader blocks SSRF attempts."""
        from embedchain.loaders.web_page import WebPageLoader

        loader = WebPageLoader()

        with pytest.raises(SSRFSecurityError):
            loader.load_data("http://169.254.169.254/latest/meta-data/")

        with pytest.raises(SSRFSecurityError):
            loader.load_data("http://localhost/admin")

    def test_web_page_loader_allows_public_urls_with_mock(self):
        """Test that WebPageLoader allows public URLs."""
        from embedchain.loaders.web_page import WebPageLoader

        loader = WebPageLoader()

        with patch.object(loader, "_session") as mock_session:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b"<html><body>Test</body></html>"
            mock_response.url = "https://example.com/"
            mock_response.history = []
            mock_session.get.return_value = mock_response

            # This should not raise
            result = loader.load_data("https://example.com/")
            assert "doc_id" in result
            assert "data" in result
