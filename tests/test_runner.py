import json
from pathlib import Path
import pytest
import yaml
from passgame.generate import build, digest
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
    assert first["record_count"] == 36
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
    config = {"split":"test", "models":[model], "tracks":["controlled"],"budget_usd":0}
    with pytest.raises(ValueError, match="positive API spending ceiling"):
        validate_config(config, {"human_audit_status":"pending"})
    config["budget_usd"] = 1
    with pytest.raises(ValueError, match="human audit"):
        validate_config(config, {"human_audit_status":"pending"})
    config["split"] = "development"
    validate_config(config, {"human_audit_status":"pending"})


def test_uncertain_paid_request_blocks_duplicate_replay(tmp_path):
    data, output = tmp_path/"data", tmp_path/"output"
    small_dataset(data)
    config = {"study":"test-fixture", "dataset_dir":str(data), "split":"development", "tracks":["controlled"], "models":[{"name":"unchanged","adapter":"diagnostic"}], "output_dir":str(output), "budget_usd":0,"bootstrap_repetitions":20,"seed":1}
    path = tmp_path/"config.yaml"
    path.write_text(yaml.safe_dump(config))
    execute(path)
    with (output/"events.jsonl").open("a") as f:
        f.write(json.dumps({"event":"started","request_key":"unknown-paid","paid":True})+"\n")
    with pytest.raises(ValueError, match="unknown outcome"):
        execute(path)
