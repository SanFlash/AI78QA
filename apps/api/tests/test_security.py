import pytest
from app.security import validate_target_url, UnsafeTarget

def test_rejects_localhost():
    with pytest.raises(UnsafeTarget):
        validate_target_url("http://localhost:3000")

def test_rejects_non_http():
    with pytest.raises(UnsafeTarget):
        validate_target_url("file:///etc/passwd")


def test_rejects_credential_bearing_query():
    with pytest.raises(UnsafeTarget):
        validate_target_url("https://demo.example/path?access_token=secret")


def test_rejects_non_global_dns_result(monkeypatch):
    monkeypatch.setattr(
        "app.security.socket.getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("10.0.0.5", 443))],
    )
    with pytest.raises(UnsafeTarget):
        validate_target_url("https://internal.example")
