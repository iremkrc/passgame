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


def test_historical_reset_analysis_is_labelled_separately():
    def row(key, track, condition, full, new, retention, **extra):
        return {"request_key":key, "model":"m", "track":track, "base_id":"same-pair",
                "condition":condition, "status":"response", "full_success":full,
                "new_success":new, "retention":retention, "outcome":"full_success" if full else "new_success_old_failure",
                "interference_degree":2, "state_policy":"reset_each_turn" if track == "fixed_start" else "scripted", **extra}
    rows = [row("prefix", "fixed_start", "interfering", 1, 1, 1, phase="prefix"),
            row("fi", "fixed_start", "independent", 1, 1, 1, phase="focal", load=5),
            row("ff", "fixed_start", "interfering", 0, 1, 0, phase="focal", load=5),
            row("ci", "controlled", "independent", 1, 1, 1),
            row("cf", "controlled", "interfering", 1, 1, 1)]
    result = analyze(rows, repetitions=20)
    assert result["record_count"] == 5 and result["legacy_reset_prefix_records"] == 1
    assert {(h["track"], h["estimate"], h["blocks"]) for h in result["h1"]} == {("controlled", 0, 1), ("legacy_reset", 1, 1)}
    assert {(h["track"], h["estimate"]) for h in result["h2"]} == {("controlled", 0), ("legacy_reset", 1)}
    summary = next(s for s in result["summary"] if s["track"] == "legacy_reset" and s["condition"] == "interfering")
    assert summary["records"] == 1 and summary["full_success"]["rate"] == 0
    assert {b["track"] for b in result["interference_breakdowns"]} == {"controlled", "legacy_reset"}


def test_fixed_start_survival_excludes_episodes_that_have_already_ended():
    rows = []
    for episode, horizon in (("short", 1), ("long", 2)):
        for turn in range(1, horizon+1):
            rows.append({"request_key":f"{episode}-{turn}", "model":"m", "track":"fixed_start",
                         "episode_id":episode, "base_id":episode, "final_set_id":episode,
                         "order":"original", "turn":turn, "load":turn, "horizon":horizon,
                         "status":"response", "full_success":1, "new_success":1, "retention":None,
                         "outcome":"full_success", "state_policy":"model_responses"})
    result = analyze(rows, repetitions=20)
    assert result["summary"][0]["records"] == 3
    assert [(s["turn"],s["numerator"],s["denominator"]) for s in result["survival"]] == [(1,2,2),(2,1,1)]
    assert all(h["blocks"] == 0 for h in result["h1"])


@pytest.mark.parametrize("infrastructure", [False, True])
def test_early_rule_failure_is_completed_but_infrastructure_is_missing(infrastructure):
    rows = []
    for turn in (1, 2):
        rows.append({"request_key":str(turn), "model":"m", "track":"fixed_start",
                     "episode_id":"e", "base_id":"e", "final_set_id":"e", "order":"original",
                     "turn":turn, "load":turn, "horizon":3, "state_policy":"model_responses",
                     "termination_policy":"first_failure", "status":"response", "full_success":int(turn == 1),
                     "new_success":1, "retention":int(turn == 1),
                     "outcome":"full_success" if turn == 1 else "new_success_old_failure"})
    if infrastructure:
        rows[-1].update(status="infrastructure_failure", full_success=None, new_success=None, retention=None)
    result = analyze(rows, repetitions=20)
    episode = result["episodes"][0]
    assert result["record_count"] == 2
    assert episode["turns_observed"] == 2 and not episode["reached_horizon"]
    assert episode["complete"] == episode["terminated_on_failure"] == (not infrastructure)
    if infrastructure:
        assert episode["final_success"] is None and result["infrastructure_failures"] == 1
        assert episode["termination_reason"] == "infrastructure_failure"
    else:
        assert episode["whole_episode_success"] == episode["final_success"] == 0
        assert episode["first_failure"] == 2 and result["infrastructure_failures"] == 0
        assert [(s["turn"],s["at_risk"],s["numerator"]) for s in result["survival"]] == [(1,1,1),(2,1,0),(3,0,0)]
