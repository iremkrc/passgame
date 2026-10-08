import json
from pathlib import Path
import pytest
import yaml
from passgame.generate import build, digest, load_jsonl
from passgame.models import Response
from passgame.run import execute, validate_config


def small_dataset(directory: Path):
    cases, episodes = build(dev_per_cell=1, test_per_cell=1)
    directory.mkdir()
    import hashlib
    for name, records in (("pairs.jsonl", cases), ("episodes.jsonl", episodes)):
        (directory/name).write_text("".join(json.dumps(r)+"\n" for r in records))
    manifest = {"human_audit_status":"pending", "files":{name:hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in ("pairs.jsonl","episodes.jsonl")}}
    (directory/"manifest.json").write_text(json.dumps(manifest))
    return manifest


def test_runner_evidence_resume_and_config_isolation(tmp_path):
    data, output = tmp_path/"data", tmp_path/"output"
    small_dataset(data)
    config = {"study":"test-fixture", "dataset_dir":str(data), "split":"development", "tracks":["controlled","fresh"], "models":[{"name":"reference_oracle","adapter":"diagnostic"}], "output_dir":str(output), "budget_usd":0, "bootstrap_repetitions":20,"seed":1}
    path = tmp_path/"config.yaml"
    path.write_text(yaml.safe_dump(config))
    first = execute(path)
    assert first["record_count"] == 48
    raw = (output/"records.jsonl").read_bytes()
    second = execute(path)
    assert second["record_count"] == first["record_count"]
    assert (output/"records.jsonl").read_bytes() == raw
    rows = [json.loads(line) for line in raw.splitlines()]
    assert all(r["retention"] is None and r["edit_distance"] is None for r in rows if r["track"] == "fresh")
    config["study"] = "changed"
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError, match="different code/data/config"):
        execute(path)


def test_paid_preflight_blocks_unreviewed_test_and_zero_budget():
    model = {"name":"m", "adapter":"chat", "model_id":"test-model", "base_url":"https://example.com/v1", "input_price_per_million":1,"output_price_per_million":1,"pricing_verified_on":"2026-10-08","max_input_tokens":1000}
    config = {"split":"test", "models":[model], "tracks":["native"],"budget_usd":0}
    with pytest.raises(ValueError, match="positive API spending ceiling"):
        validate_config(config, {"human_audit_status":"pending"})
    config["budget_usd"] = 1
    with pytest.raises(ValueError, match="human audit"):
        validate_config(config, {"human_audit_status":"pending"})
    config["split"] = "development"
    validate_config(config, {"human_audit_status":"pending"})


@pytest.mark.parametrize("tracks", [["controlled"], ["fresh"], ["native", "controlled"], ["order", "fresh"]])
def test_llm_tracks_reject_scripted_prefixes_and_all_at_once(tracks):
    config = {"split":"development", "models":[{"name":"m","adapter":"chat"}],
              "tracks":tracks, "budget_usd":1}
    with pytest.raises(ValueError, match="model-generated prefixes"):
        validate_config(config, {})


def test_self_hosted_zero_api_budget_keeps_sequential_protocol_and_audit():
    model = {"name":"open-model", "adapter":"chat", "deployment":"self_hosted", "model_id":"test-open-model",
             "base_url":"http://127.0.0.1:8000/v1", "input_price_per_million":0,"output_price_per_million":0,
             "pricing_verified_on":"2026-10-08","max_input_tokens":32768}
    config = {"split":"development", "models":[model], "tracks":["native","order"], "budget_usd":0}
    validate_config(config, {"human_audit_status":"pending"})
    config["split"] = "test"
    with pytest.raises(ValueError, match="human audit"):
        validate_config(config, {"human_audit_status":"pending"})
    validate_config(config, {"human_audit_status":"complete"})
    config["tracks"] = ["controlled"]
    with pytest.raises(ValueError, match="model-generated prefixes"):
        validate_config(config, {"human_audit_status":"complete"})
    config["tracks"] = ["native"]
    model["input_price_per_million"] = 1
    with pytest.raises(ValueError, match="explicit zero API token prices"):
        validate_config(config, {"human_audit_status":"complete"})


def test_llm_episode_uses_actual_responses_and_original_single_rule_turns(tmp_path, monkeypatch):
    data, output = tmp_path/"data", tmp_path/"output"
    small_dataset(data)
    episodes = load_jsonl(data/"episodes.jsonl")
    episode = next(e for e in episodes if e["track"] == "native" and e["split"] == "development")
    (data/"episodes.jsonl").write_text(json.dumps(episode)+"\n")
    manifest = json.loads((data/"manifest.json").read_text())
    import hashlib
    manifest["files"]["episodes.jsonl"] = hashlib.sha256((data/"episodes.jsonl").read_bytes()).hexdigest()
    (data/"manifest.json").write_text(json.dumps(manifest))
    sent, returned = [], []
    class FakeChat:
        def __init__(self, *args):
            pass
        def complete(self, messages, context):
            # Deliberately invalid relative to constraints, but valid in the string domain.
            raw = json.dumps({"password": "Z"+str(len(sent)+1)})
            sent.append(messages)
            returned.append(raw)
            return Response(raw=raw, provider_response={}, attempts=1, latency_seconds=0, usage={}, cost_reserved=0)
        def close(self):
            pass
    monkeypatch.setattr("passgame.run.ChatAdapter", FakeChat)
    model = {"name":"mock-llm", "adapter":"chat", "model_id":"mock", "base_url":"https://example.com/v1",
             "input_price_per_million":1,"output_price_per_million":1,"pricing_verified_on":"2026-10-08","max_input_tokens":1000}
    config = {"study":"sequential-fixture", "dataset_dir":str(data), "split":"development", "tracks":["native"],
              "models":[model], "output_dir":str(output), "budget_usd":1,"bootstrap_repetitions":20,"seed":1}
    path = tmp_path/"config.yaml"
    path.write_text(yaml.safe_dump(config))
    execute(path)
    rows = load_jsonl(output/"records.jsonl")
    assert len(sent) == len(episode["rules"]) == 8
    for i, (messages, row) in enumerate(zip(sent, rows)):
        users = [m["content"] for m in messages if m["role"] == "user"]
        assistants = [m["content"] for m in messages if m["role"] == "assistant"]
        assert len(users) == i+1
        assert assistants == returned[:i]
        assert row["prefix_source"] == "model_responses"
        assert row["current"] == (episode["initial"] if i == 0 else "Z"+str(i))
        for j, prompt in enumerate(users):
            assert prompt.count("\nNew rule: ") == 1
            assert "New rule: "+episode["rules"][j]["id"]+": " in prompt
            assert "All active rules" not in prompt
            assert prompt == sent[j][-1]["content"]  # No rewriting or later reminders.


@pytest.mark.parametrize("started", [{"paid":True}, {"paid":False,"model_request":True}])
def test_uncertain_model_request_blocks_duplicate_replay(tmp_path, started):
    data, output = tmp_path/"data", tmp_path/"output"
    small_dataset(data)
    config = {"study":"test-fixture", "dataset_dir":str(data), "split":"development", "tracks":["controlled"], "models":[{"name":"unchanged","adapter":"diagnostic"}], "output_dir":str(output), "budget_usd":0,"bootstrap_repetitions":20,"seed":1}
    path = tmp_path/"config.yaml"
    path.write_text(yaml.safe_dump(config))
    execute(path)
    with (output/"events.jsonl").open("a") as f:
        f.write(json.dumps({"event":"started","request_key":"unknown-model",**started})+"\n")
    with pytest.raises(ValueError, match="unknown outcome"):
        execute(path)
