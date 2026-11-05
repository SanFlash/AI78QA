import pytest
from app.security import validate_target_url, UnsafeTarget

def test_rejects_localhost():
    with pytest.raises(UnsafeTarget):
        validate_target_url("http://localhost:3000")

def test_rejects_non_http():
    with pytest.raises(UnsafeTarget):
        validate_target_url("file:///etc/passwd")
