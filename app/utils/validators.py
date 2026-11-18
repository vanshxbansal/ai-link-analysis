import ipaddress
import socket
from urllib.parse import urlparse


BLOCKED_HOSTS = {
    "localhost", "127.0.0.1", "0.0.0.0", "::1",
    "metadata.google.internal", "169.254.169.254",
}

PRIVATE_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def is_private_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return any(addr in net for net in PRIVATE_RANGES)
    except ValueError:
        return False


def validate_url(url: str) -> tuple[bool, str]:
    """Validate URL and check for SSRF risks. Returns (is_valid, error_message)."""
    if not url:
        return False, "URL is required"

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"

    if not parsed.scheme or not parsed.netloc:
        return False, "Invalid URL: missing scheme or host"

    if parsed.scheme not in ("http", "https"):
        return False, "Only HTTP and HTTPS URLs are allowed"

    host = parsed.hostname or ""

    if host.lower() in BLOCKED_HOSTS:
        return False, "Access to this host is not allowed"

    # Resolve hostname and check IP
    try:
        ip = socket.gethostbyname(host)
        if is_private_ip(ip):
            return False, "Access to private or internal network addresses is not allowed"
    except socket.gaierror:
        return False, f"Cannot resolve host: {host}"

    return True, ""


def normalize_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url
