import ipaddress
import socket
from urllib.parse import parse_qsl, urlparse

class UnsafeTarget(ValueError):
    pass

def validate_target_url(value: str) -> str:
    """Conservative SSRF guard. Production must also enforce egress policy at network level."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeTarget("Target must be an HTTP(S) URL with a hostname.")
    if parsed.username or parsed.password:
        raise UnsafeTarget("Credentials embedded in target URLs are not allowed.")
    sensitive_keys = {"token", "access_token", "refresh_token", "id_token", "code", "key",
                      "api_key", "secret", "password", "session", "sessionid", "auth",
                      "signature", "sig", "state", "nonce"}
    if any(key.lower() in sensitive_keys for key, _ in parse_qsl(parsed.query, keep_blank_values=True)):
        raise UnsafeTarget("Sensitive authentication parameters are not allowed in target URLs.")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "metadata.google.internal"} or host.endswith(".localhost"):
        raise UnsafeTarget("Local and metadata hostnames are blocked.")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, None)}
    except (socket.gaierror, OSError):
        raise UnsafeTarget("Target hostname could not be resolved.") from None
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise UnsafeTarget("Target resolves to a non-public IP address.")
    return host
