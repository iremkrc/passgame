"""Check authenticated discovery without contacting the hosted service."""

import importlib.util
import json
from pathlib import Path

import httpx
import pytest


spec = importlib.util.spec_from_file_location(
    "mlcloud_models", Path(__file__).resolve().parents[1]/"scripts/mlcloud_models.py"
)
mlcloud = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mlcloud)


def test_discovery_uses_key_in_header_and_only_requests_model_ids(monkeypatch):
    monkeypatch.setenv("TEST_MLCLOUD_KEY", "private-test-key")
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"data": [{"id": "model-b"}, {"id": "model-a"}, {"id": "model-a"}]})

    assert mlcloud.list_models("TEST_MLCLOUD_KEY", transport=httpx.MockTransport(handler)) == ["model-a", "model-b"]
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert str(requests[0].url) == mlcloud.BASE_URL + "/models"
    assert requests[0].headers["Authorization"] == "Bearer private-test-key"
    assert requests[0].content == b""


def test_missing_key_stops_before_network(monkeypatch):
    monkeypatch.delenv("TEST_MLCLOUD_KEY", raising=False)

    def handler(request):
        pytest.fail("Discovery must not contact the service without a key")

    with pytest.raises(ValueError, match="TEST_MLCLOUD_KEY"):
        mlcloud.list_models("TEST_MLCLOUD_KEY", transport=httpx.MockTransport(handler))


@pytest.mark.parametrize("status, body", [
    (401, {"error": "private-test-key"}),
    (200, {"data": None}),
    (200, {"data": [{"id": None}]}),
    (200, {"data": [{"unexpected": "private-test-key"}]}),
    (200, "invalid json private-test-key"),
])
def test_invalid_discovery_response_does_not_expose_body(monkeypatch, status, body):
    monkeypatch.setenv("TEST_MLCLOUD_KEY", "private-test-key")
    transport = httpx.MockTransport(lambda request: httpx.Response(status, text=body if isinstance(body, str) else json.dumps(body)))
    with pytest.raises(ValueError) as error:
        mlcloud.list_models("TEST_MLCLOUD_KEY", transport=transport)
    assert "private-test-key" not in str(error.value)
