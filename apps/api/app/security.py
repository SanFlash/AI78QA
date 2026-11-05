import ipaddress
import socket
from urllib.parse import urlparse

class UnsafeTarget(ValueError):
    pass

def validate_target_url(value: str) -> str:
    """Conservative SSRF guard. Production must also enforce egress policy at network level."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeTarget("Target must be an HTTP(S) URL with a hostname.")
    if parsed.username or parsed.password:
        raise UnsafeTarget("Credentials embedded in target URLs are not allowed.")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "metadata.google.internal"} or host.endswith(".localhost"):
        raise UnsafeTarget("Local and metadata hostnames are blocked.")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, None)}
    except socket.gaierror:
        raise UnsafeTarget("Target hostname could not be resolved.") from None
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise UnsafeTarget("Target resolves to a non-public IP address.")
    return host
