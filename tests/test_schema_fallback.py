import pytest
import requests

from cmakepresets import schema as schema_mod


def test_get_schema_uses_local_fallback_on_download_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate requests.get failing with OSError and then a RequestException on retry.

    Under pytest the module checks sys.modules and will use the local fallback
    schema when downloads fail. Ensure get_schema() returns the fallback schema
    (which contains a 'oneOf' top-level key) instead of raising.
    """

    call_count = {"n": 0}

    def fake_get(*args: object, **kwargs: object) -> object:
        # First call raises OSError (simulating certifi CA bundle path problem)
        # Second call raises a generic requests exception (retry failure).
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise OSError("simulated certifi CA bundle missing")
        raise requests.RequestException("simulated download failure")

    monkeypatch.setattr(requests, "get", fake_get)

    # Should not raise; should return the local fallback schema
    schema = schema_mod.get_schema(4)

    assert isinstance(schema, dict)
    # Our fallback schema is minimal and contains a top-level 'oneOf'
    assert "oneOf" in schema
