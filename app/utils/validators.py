"""URL validation and SSRF protection."""

import ipaddress
import socket
from typing import List, Tuple
from urllib.parse import urlparse

BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata",
    "instance-data",
}

BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home.arpa")

ALLOWED_PORTS = {None, 80, 443, 8080, 8443}

# Ranges not covered by ipaddress' is_private / is_reserved flags on older Pythons
EXTRA_BLOCKED_NETWORKS = [
    ipaddress.ip_network("100.64.0.0/10"),  # carrier-grade NAT
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("198.18.0.0/15"),  # benchmarking
]


def is_private_ip(ip: str) -> bool:
    """Return True if the IP address is not publicly routable."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False

    # Unwrap IPv4-mapped / 6to4 style IPv6 addresses (e.g. ::ffff:127.0.0.1)
    if isinstance(addr, ipaddress.IPv6Address):
        if addr.ipv4_mapped:
            addr = addr.ipv4_mapped
        elif addr.sixtofour:
            addr = addr.sixtofour

    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
        or not addr.is_global
    ):
        return True

    return any(addr in net for net in EXTRA_BLOCKED_NETWORKS if net.version == addr.version)


def resolve_host(host: str) -> List[str]:
    """Resolve a hostname to all of its IPv4/IPv6 addresses."""
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return sorted({info[4][0] for info in infos})


def validate_url(url: str) -> Tuple[bool, str]:
    """Validate URL and check for SSRF risks. Returns (is_valid, error_message)."""
    if not url or not url.strip():
        return False, "URL is required"

    url = url.strip()
    if len(url) > 2048:
        return False, "URL is too long"

    if "://" not in url:
        url = "https://" + url

    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError:
        return False, "Invalid URL format"

    if parsed.scheme not in ("http", "https"):
        return False, "Only HTTP and HTTPS URLs are allowed"

    if not parsed.netloc or not parsed.hostname:
        return False, "Invalid URL: missing host"

    if parsed.username or parsed.password:
        return False, "URLs with embedded credentials are not allowed"

    if port not in ALLOWED_PORTS:
        return False, "Only standard web ports (80, 443, 8080, 8443) are allowed"

    host = parsed.hostname.lower().rstrip(".")

    if host in BLOCKED_HOSTS or host.endswith(BLOCKED_SUFFIXES):
        return False, "Access to this host is not allowed"

    # Literal IP address in the URL
    try:
        ipaddress.ip_address(host)
        if is_private_ip(host):
            return False, "Access to private or internal network addresses is not allowed"
        return True, ""
    except ValueError:
        pass

    if "." not in host:
        return False, "Invalid URL: host must be a fully qualified domain name"

    # Resolve the hostname and make sure *every* address is public
    try:
        addresses = resolve_host(host)
    except (socket.gaierror, UnicodeError):
        return False, f"Cannot resolve host: {host}"

    if not addresses:
        return False, f"Cannot resolve host: {host}"

    if any(is_private_ip(ip) for ip in addresses):
        return False, "Access to private or internal network addresses is not allowed"

    return True, ""


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if url and "://" not in url:
        return "https://" + url
    return url
