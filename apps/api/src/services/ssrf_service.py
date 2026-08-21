import ipaddress
import logging
import socket
from urllib.parse import urlsplit

from apps.api.src.core.exceptions import ValidationException

logger = logging.getLogger("ai_knowledge_assistant.security.ssrf")

# Restricted hostnames (Docker services, cloud metadata, local hostnames)
RESTRICTED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
    "host.docker.internal",
    "gateway.docker.internal",
    "metadata.google.internal",
    "metadata.aws.internal",
    "instance-data",
    # Docker compose internal service names
    "postgres",
    "redis",
    "backend",
    "worker",
    "frontend",
}

# Custom private/restricted networks to strictly forbid
RESTRICTED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),  # Current network
    ipaddress.ip_network("10.0.0.0/8"),  # RFC 1918 Private
    ipaddress.ip_network("100.64.0.0/10"),  # Carrier-grade NAT
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback
    ipaddress.ip_network(
        "169.254.0.0/16"
    ),  # Link-local / AWS / GCP / Azure metadata (169.254.169.254)
    ipaddress.ip_network(
        "172.16.0.0/12"
    ),  # RFC 1918 Private (Docker default bridge: 172.17 - 172.28)
    ipaddress.ip_network("192.0.0.0/24"),  # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),  # Documentation (TEST-NET-1)
    ipaddress.ip_network("192.168.0.0/16"),  # RFC 1918 Private
    ipaddress.ip_network("198.18.0.0/15"),  # Network benchmark tests
    ipaddress.ip_network("198.51.100.0/24"),  # Documentation (TEST-NET-2)
    ipaddress.ip_network("203.0.113.0/24"),  # Documentation (TEST-NET-3)
    ipaddress.ip_network("224.0.0.0/4"),  # Multicast
    ipaddress.ip_network("240.0.0.0/4"),  # Reserved for future use
    ipaddress.ip_network("255.255.255.255/32"),  # Broadcast
    # IPv6 Networks
    ipaddress.ip_network("::/128"),  # Unspecified
    ipaddress.ip_network("::1/128"),  # Loopback
    ipaddress.ip_network("fc00::/7"),  # Unique local address (ULA)
    ipaddress.ip_network("fe80::/10"),  # Link-local unicast
    ipaddress.ip_network("ff00::/8"),  # Multicast
    ipaddress.ip_network("::ffff:0:0/96"),  # IPv4-mapped IPv6
]


class SSRFService:
    """
    Service providing comprehensive Server-Side Request Forgery (SSRF) validation
    for user-submitted URLs and HTTP redirect targets.
    """

    @staticmethod
    def is_ip_restricted(ip_str: str) -> bool:
        """Check if an IP string is private, loopback, link-local, or restricted."""
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            return True

        if (
            ip_obj.is_loopback
            or ip_obj.is_private
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_unspecified
            or ip_obj.is_reserved
        ):
            return True

        for net in RESTRICTED_NETWORKS:
            if ip_obj in net:
                return True

        return False

    @staticmethod
    def validate_url(url: str) -> str:
        """
        Validate URL scheme, structure, and resolved DNS destination IP.
        Raises ValidationException if the URL violates SSRF safety constraints.
        Returns normalized URL string.
        """
        if not url or not isinstance(url, str):
            raise ValidationException("URL must be a non-empty string.")

        clean_url = url.strip()
        parsed = urlsplit(clean_url)

        # 1. Scheme Validation (Strictly http or https)
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            raise ValidationException(
                f"Unsupported URL scheme '{parsed.scheme}'. Only 'http://' and 'https://' are allowed."
            )

        # 2. Hostname Validation
        hostname = parsed.hostname
        if not hostname:
            raise ValidationException("Invalid URL: Missing hostname.")

        hostname_lower = hostname.lower().strip(".")

        # Check explicit blacklist
        if hostname_lower in RESTRICTED_HOSTNAMES:
            logger.warning(f"Blocked SSRF attempt targeting restricted hostname: {hostname}")
            raise ValidationException(
                f"Access to hostname '{hostname}' is restricted for security (SSRF protection)."
            )

        # 3. Direct IP Address Validation
        try:
            ip_direct = ipaddress.ip_address(hostname_lower)
            if SSRFService.is_ip_restricted(str(ip_direct)):
                logger.warning(f"Blocked SSRF attempt targeting restricted direct IP: {ip_direct}")
                raise ValidationException(
                    f"Access to IP address '{hostname}' is restricted for security (SSRF protection)."
                )
            return clean_url
        except ValueError:
            # Not a raw IP literal, proceed to DNS resolution
            pass

        # 4. DNS Resolution & Resolved Destination Check
        port = parsed.port or (80 if scheme == "http" else 443)
        try:
            addr_info = socket.getaddrinfo(hostname_lower, port, proto=socket.IPPROTO_TCP)
            if not addr_info:
                raise ValidationException(f"Failed to resolve DNS for hostname '{hostname}'.")

            for addr in addr_info:
                sockaddr = addr[4]
                ip_resolved = sockaddr[0]
                if SSRFService.is_ip_restricted(ip_resolved):
                    logger.warning(
                        f"Blocked SSRF attempt: Hostname '{hostname}' resolved to restricted IP: {ip_resolved}"
                    )
                    raise ValidationException(
                        f"Access to '{hostname}' is restricted: resolved address '{ip_resolved}' is not a public destination."
                    )
        except socket.gaierror as e:
            logger.warning(f"DNS resolution failure for '{hostname}': {e}")
            raise ValidationException(f"Could not resolve hostname '{hostname}'.") from None
        except Exception as e:
            if isinstance(e, ValidationException):
                raise
            logger.error(f"Unexpected error during SSRF validation of '{url}': {e}")
            raise ValidationException(f"Failed to validate URL security: {e}") from None

        return clean_url
