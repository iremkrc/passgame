import json
import httpx
import pytest
from passgame.analyze import analyze, paired_interval
from passgame.models import Budget, BudgetExceeded, ChatAdapter, InfrastructureError


def configuration():
    return {"model_id":"test-model", "base_url":"http://localhost:1234/v1", "api_key_env":None,
            "max_input_tokens":1000, "input_price_per_million":1, "output_price_per_million":2,
            "parameters":{"max_completion_tokens":20}, "transport_retries":0}


def test_budget_stops_before_network_and_reserves_response_cost():
    sent = []
    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"choices":[{"message":{"content":"{\"password\":\"A\"}"}}], "usage":{"prompt_tokens":10,"completion_tokens":8}})
    adapter = ChatAdapter(configuration(), Budget(.001), transport=httpx.MockTransport(handler))
    with pytest.raises(BudgetExceeded):
        adapter.complete([{"role":"user","content":"test"}], {})
    assert sent == []
    adapter.close()
    budget = Budget(.1)
    adapter = ChatAdapter(configuration(), budget, transport=httpx.MockTransport(handler))
    response = adapter.complete([{"role":"user","content":"test"}], {})
    assert sent[0]["max_completion_tokens"] == 20
    assert response.usage["prompt_tokens"] == 10
    assert budget.reserved == pytest.approx(.00104)
    adapter.close()


def test_transport_failure_retains_reservation():
    def handler(request):
        raise httpx.ReadTimeout("test timeout")
    budget = Budget(.1)
    adapter = ChatAdapter(configuration(), budget, transport=httpx.MockTransport(handler))
    with pytest.raises(InfrastructureError):
        adapter.complete([{"role":"user","content":"test"}], {})
    assert budget.reserved > 0
    adapter.close()


def test_missing_infrastructure_is_not_model_failure():
    rows = [{"request_key":"a", "model":"m", "track":"controlled", "base_id":"p", "condition":"independent", "status":"response", "full_success":1, "new_success":1, "retention":1, "outcome":"full_success"},
            {"request_key":"b", "model":"m", "track":"controlled", "base_id":"p", "condition":"interfering", "status":"infrastructure_failure", "full_success":None,"new_success":None,"retention":None}]
    result = analyze(rows, repetitions=50)
    assert result["h1"][0]["blocks"] == 0
    assert result["infrastructure_failures"] == 1
    assert result["summary"][1]["full_success"]["denominator"] == 0
    assert paired_interval([0, 1], 100, 1) == paired_interval([0, 1], 100, 1)


def test_self_hosted_endpoint_works_without_api_credentials_or_spend():
    sent = []
    def handler(request):
        sent.append(request)
        return httpx.Response(200, json={"choices":[{"message":{"content":"{\"password\":\"A\"}"}}]})
    config = configuration()
    config.update({"deployment":"self_hosted", "input_price_per_million":0,"output_price_per_million":0,
                   "parameters":{"max_tokens":20,"temperature":0}})
    budget = Budget(0)
    adapter = ChatAdapter(config, budget, transport=httpx.MockTransport(handler))
    response = adapter.complete([{"role":"user","content":"one new rule"}], {"witness":"PRIVATE_EVALUATOR_WITNESS"})
    assert response.raw == '{"password":"A"}' and budget.reserved == 0
    assert 'authorization' not in sent[0].headers
    payload = json.loads(sent[0].content)
    assert payload["max_tokens"] == 20 and payload["temperature"] == 0
    assert 'PRIVATE_EVALUATOR_WITNESS' not in sent[0].content.decode()
    adapter.close()
