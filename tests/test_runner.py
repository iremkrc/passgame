"""Final study configuration, request persistence, and API integration checks."""

import json
from pathlib import Path
import httpx
import pytest
import yaml
from passgame.generate import digest, load_jsonl, write_dataset
from passgame.models import ChatAdapter
from passgame.run import execute, validate_config


def small_dataset(directory: Path):
    return write_dataset(directory, dev_per_family=1, test_per_family=1)


def test_paid_preflight_blocks_unreviewed_test_and_zero_budget():
    model = {"name":"m", "adapter":"chat", "model_id":"test-model", "base_url":"https://example.com/v1", "input_price_per_million":1,"output_price_per_million":1,"pricing_verified_on":"2026-10-08","max_input_tokens":1000}
    config = {"split":"test", "models":[model], "tracks":["order"],"budget_usd":0}
    with pytest.raises(ValueError, match="positive API spending ceiling"):
        validate_config(config, {"version":3,"human_audit_status":"pending"})
    config["budget_usd"] = 1
    with pytest.raises(ValueError, match="human audit"):
        validate_config(config, {"version":3,"human_audit_status":"pending"})
    config["split"] = "development"
    validate_config(config, {"version":3,"human_audit_status":"pending"})


@pytest.mark.parametrize("value", ["true", "false", 1, None])
def test_reminder_setting_rejects_non_boolean_values(value):
    config = {"split":"development", "models":[{"name":"reference_oracle","adapter":"diagnostic"}],
              "tracks":["order"], "remind_previous_rules":value}
    with pytest.raises(ValueError, match="remind_previous_rules must be a boolean"):
        validate_config(config, {"version":3})


@pytest.mark.parametrize("value", ["true", "false", 1, None])
def test_markdown_fence_setting_rejects_non_boolean_values(value):
    config = {"split":"development", "models":[{"name":"reference_oracle","adapter":"diagnostic"}],
              "tracks":["order"], "allow_markdown_fences":value}
    with pytest.raises(ValueError, match="allow_markdown_fences must be a boolean"):
        validate_config(config, {"version":3})


@pytest.mark.parametrize("tracks", [["unknown"], [], ["order", "unknown"]])
def test_llm_tracks_reject_scripted_prefixes_and_all_at_once(tracks):
    config = {"split":"development", "models":[{"name":"m","adapter":"chat"}],
              "tracks":tracks, "budget_usd":1}
    with pytest.raises(ValueError, match="seeded or order"):
        validate_config(config, {"version":3})


def test_self_hosted_zero_api_budget_keeps_sequential_protocol_and_audit():
    model = {"name":"open-model", "adapter":"chat", "deployment":"self_hosted", "model_id":"test-open-model",
             "base_url":"http://127.0.0.1:8000/v1", "input_price_per_million":0,"output_price_per_million":0,
             "pricing_verified_on":"2026-10-08","max_input_tokens":32768}
    config = {"split":"development", "models":[model], "tracks":["order"], "budget_usd":0}
    validate_config(config, {"version":3,"human_audit_status":"pending"})
    config["split"] = "test"
    with pytest.raises(ValueError, match="human audit"):
        validate_config(config, {"version":3,"human_audit_status":"pending"})
    validate_config(config, {"version":3,"human_audit_status":"complete"})
    config["tracks"] = ["unknown"]
    with pytest.raises(ValueError, match="seeded or order"):
        validate_config(config, {"version":3,"human_audit_status":"complete"})
    config["tracks"] = ["order"]
    model["input_price_per_million"] = 1
    with pytest.raises(ValueError, match="explicit zero API token prices"):
        validate_config(config, {"version":3,"human_audit_status":"complete"})


@pytest.mark.parametrize("started", [{"paid":True}, {"paid":False,"model_request":True}])
def test_uncertain_model_request_blocks_duplicate_replay(tmp_path, started):
    data, output = tmp_path/"data", tmp_path/"output"
    small_dataset(data)
    config = {"study":"test-fixture", "dataset_dir":str(data), "split":"development", "tracks":["seeded"], "models":[{"name":"reference_oracle","adapter":"diagnostic"}], "output_dir":str(output), "budget_usd":0,"bootstrap_repetitions":20,"seed":1}
    path = tmp_path/"config.yaml"
    path.write_text(yaml.safe_dump(config))
    execute(path)
    with (output/"events.jsonl").open("a") as f:
        f.write(json.dumps({"event":"started","request_key":"unknown-model",**started})+"\n")
    with pytest.raises(ValueError, match="unknown outcome"):
        execute(path)



@pytest.mark.parametrize("deployment", ["provider", "self_hosted"])
@pytest.mark.parametrize("response_mode", ["success", "model_failure", "infrastructure_failure"])
def test_api_and_cluster_endpoint_evaluation_and_resumption(tmp_path, monkeypatch, deployment, response_mode):
    """Exercise real request serialization and scoring through the chat adapter."""
    data, output = tmp_path/"data", tmp_path/"output"
    small_dataset(data)
    episodes = load_jsonl(data/"episodes.jsonl")
    base = episodes[0]["base_id"]
    selected = [episode for episode in episodes if episode["base_id"] == base]
    (data/"episodes.jsonl").write_text("".join(json.dumps(episode)+"\n" for episode in selected))
    import hashlib
    manifest = json.loads((data/"manifest.json").read_text())
    manifest["files"]["episodes.jsonl"] = hashlib.sha256((data/"episodes.jsonl").read_bytes()).hexdigest()
    (data/"manifest.json").write_text(json.dumps(manifest))
    ordered = [episode for episode in selected if episode["track"] == "order"]
    sent, game = [], -1
    monkeypatch.setenv("TEST_PASSGAME_KEY", "fixture-secret")

    def handler(request):
        nonlocal game
        payload = json.loads(request.content)
        turn = sum(message["role"] == "user" for message in payload["messages"])
        if turn == 1:
            game += 1
        sent.append(payload)
        assert request.url.path == "/v1/chat/completions"
        assert (request.headers.get("authorization") == "Bearer fixture-secret") == (deployment == "provider")
        assert set(payload) == {"model", "messages", "stream", "max_tokens", "temperature"}
        assert "reference_outputs" not in request.content.decode()
        if response_mode == "infrastructure_failure":
            return httpx.Response(503)
        answer = "invalid JSON" if response_mode == "model_failure" and turn == 3 else json.dumps({"password": ordered[game]["witness"]})
        return httpx.Response(200, json={"choices": [{"message": {"content": answer}, "finish_reason": "stop"}]})

    def adapter(config, budget, reserve_callback=None):
        return ChatAdapter(config, budget, reserve_callback, transport=httpx.MockTransport(handler))

    monkeypatch.setattr("passgame.run.ChatAdapter", adapter)
    paid = deployment == "provider"
    config = {"study": "endpoint-test", "dataset_dir": str(data), "split": "development",
              "tracks": ["order"], "rule_count": 8, "remind_previous_rules": True,
              "output_dir": str(output), "budget_usd": 10 if paid else 0,
              "bootstrap_repetitions": 20, "seed": 1, "models": [{
                  "name": "model", "adapter": "chat", "deployment": deployment, "model_id": "served-model",
                  "base_url": "https://api.example/v1" if paid else "http://127.0.0.1:8000/v1",
                  "api_key_env": "TEST_PASSGAME_KEY" if paid else None,
                  "input_price_per_million": 1 if paid else 0, "output_price_per_million": 1 if paid else 0,
                  "pricing_verified_on": "2026-10-27", "max_input_tokens": 32768,
                  "parameters": {"max_tokens": 1024, "temperature": 0}, "transport_retries": 0,
              }]}
    path = tmp_path/"config.yaml"
    path.write_text(yaml.safe_dump(config))
    assert execute(path, preflight_only=True)["planned_episodes"] == 4
    assert not sent
    if response_mode == "infrastructure_failure":
        with pytest.raises(SystemExit) as error:
            execute(path)
        assert error.value.code == 2
    else:
        execute(path)
    rows = load_jsonl(output/"records.jsonl")
    completion = json.loads((output/"completion.json").read_text())
    per_game = {"success": 8, "model_failure": 3, "infrastructure_failure": 1}[response_mode]
    assert len(sent) == len(rows) == 4*per_game
    assert completion["complete"] is (response_mode != "infrastructure_failure")
    assert (completion["reserved_usd"] > 0) is paid
    assert "fixture-secret" not in (output/"records.jsonl").read_text()
    if response_mode == "model_failure":
        assert completion["skipped_after_failure"] == 20
        assert sum(row["episode_terminal"] for row in rows) == 4
    if response_mode != "infrastructure_failure":
        recorded = (output/"records.jsonl").read_bytes()
        execute(path)
        assert len(sent) == 4*per_game
        assert (output/"records.jsonl").read_bytes() == recorded
