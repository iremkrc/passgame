import json
from pathlib import Path
import pytest
import yaml
from passgame.constraints import Rule
from passgame.generate import build, digest, load_jsonl
from passgame.models import InfrastructureError, Response
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


def test_eight_rule_selection_filters_cases_and_plans_without_losing_families(tmp_path):
    from collections import Counter
    data, output = tmp_path/"data", tmp_path/"output"
    small_dataset(data)
    config = {"study":"eight-rule-fixture", "dataset_dir":str(data), "split":"development",
              "tracks":["fixed_start","controlled","fresh"], "rule_count":8,
              "models":[{"name":"reference_oracle","adapter":"diagnostic"}],
              "output_dir":str(output), "budget_usd":0, "bootstrap_repetitions":20, "seed":1}
    path = tmp_path/"config.yaml"
    path.write_text(yaml.safe_dump(config))
    plan = execute(path, preflight_only=True)
    assert plan["selection"]["rule_count"] == 8 and plan["selection"]["pairs"] == 6
    assert plan["planned_episodes"] == 12
    assert plan["planned_records"] == 12*8+12+6
    result = execute(path)
    rows = load_jsonl(output/"records.jsonl")
    games = [r for r in rows if r["track"] == "fixed_start"]
    assert len(games) == 96 and {r["horizon"] for r in games} == {8}
    assert {r["family"] for r in games} == {"numeric","position_count","substring_position","forbidden_position","numeric_multi_2","numeric_multi_3"}
    starts = [r for r in games if r["turn"] == 1]
    assert Counter(r["initial_condition"] for r in starts) == {"independent":6,"interfering":6}
    assert Counter(r["intended_interference_degree"] for r in starts) == {1:8,2:2,3:2}
    assert all(len(r["old_rules"])+1 == 8 for r in rows if r["track"] != "fixed_start")
    assert result["record_count"] == plan["planned_records"]
    assert json.loads((output/"completion.json").read_text())["complete"] is True
    assert {e["horizon"] for e in result["episodes"]} == {8}
    # An unavailable length must not silently produce a successful empty run.
    config["rule_count"] = 7
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError, match="No cases or episodes match"):
        execute(path, preflight_only=True)
    config["rule_count"] = True
    with pytest.raises(ValueError, match="positive integer"):
        validate_config(config, {})


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


@pytest.mark.parametrize("value", ["true", "false", 1, None])
def test_reminder_setting_rejects_non_boolean_values(value):
    config = {"split":"development", "models":[{"name":"reference_oracle","adapter":"diagnostic"}],
              "tracks":["fixed_start"], "remind_previous_rules":value}
    with pytest.raises(ValueError, match="remind_previous_rules must be a boolean"):
        validate_config(config, {})


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


@pytest.mark.parametrize("remind_previous_rules", [False, True])
def test_fixed_start_carries_successes_and_terminates_on_first_failure(tmp_path, monkeypatch, remind_previous_rules):
    from collections import defaultdict
    data, output = tmp_path/"data", tmp_path/"output"
    manifest = small_dataset(data)
    calls = []

    class FakeChat:
        def __init__(self, config, *args):
            self.name = config["name"]
        def complete(self, messages, context):
            turn = sum(m["role"] == "user" for m in messages)
            failure_turn = 3 if self.name == "wrong" else 2
            if turn < failure_turn:
                raw = json.dumps({"password":context["witness"]})
            else:
                raw = {"malformed":"not JSON", "domain":'{"password":"bad space"}', "wrong":'{"password":"Z"}'}[self.name]
            calls.append((self.name, messages))
            return Response(raw, {}, 1, 0, {})
        def close(self):
            pass

    monkeypatch.setattr("passgame.run.ChatAdapter", FakeChat)
    models = [{"name":name, "adapter":"chat", "deployment":"self_hosted", "model_id":name,
               "base_url":"http://127.0.0.1:8000/v1", "input_price_per_million":0,
               "output_price_per_million":0, "pricing_verified_on":"2026-10-22",
               "max_input_tokens":32768} for name in ("malformed", "domain", "wrong")]
    config = {"study":"fixed-start-fixture", "dataset_dir":str(data), "split":"development",
              "tracks":["fixed_start"], "models":models, "output_dir":str(output),
              "remind_previous_rules":remind_previous_rules,
              "budget_usd":0, "bootstrap_repetitions":20, "seed":1}
    path = tmp_path/"config.yaml"
    path.write_text(yaml.safe_dump(config))
    result = execute(path)
    cases = {c["pair_id"]:c for c in load_jsonl(data/"pairs.jsonl") if c["split"] == "development"}
    rows = load_jsonl(output/"records.jsonl")
    expected_per_model = 2*sum(c["load"] for c in cases.values())
    expected_requests = 2*len(cases)*(2+2+3)
    assert len(rows) == result["record_count"] == expected_requests
    completion = json.loads((output/"completion.json").read_text())
    assert completion["complete"] is True
    prompt_version = "cumulative_rule_reminders_v1" if remind_previous_rules else "history_only_v1"
    assert completion["prompt_protocol"] == {"version":prompt_version, "remind_previous_rules":remind_previous_rules}
    assert json.loads((output/"metadata.json").read_text())["prompt_protocol"] == completion["prompt_protocol"]
    assert completion["skipped_after_failure"] == len(models)*expected_per_model-len(rows)
    assert completion["expected_records"] == len(rows)
    assert completion["completed_episodes"] == completion["terminated_on_failure"] == 2*len(cases)*len(models)
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["model"], row["episode_id"])].append(row)
    for group in grouped.values():
        failure_turn = 3 if group[0]["model"] == "wrong" else 2
        assert len(group) == failure_turn
        assert all(r["full_success"] == 1 for r in group[:-1])
        assert group[-1]["full_success"] == 0
        assert group[-1]["episode_terminal"] is True
        assert group[-1]["next_state"] is None
        assert group[-1]["episode_end_reason"] == {"wrong":"rule_failure", "malformed":"format_failure", "domain":"domain_failure"}[group[0]["model"]]
        for row in group:
            case = cases[row["pair_id"]]
            initial = case["states"][row["initial_condition"]]
            assert row["initial"] == initial
            assert group[0]["current"] == initial
            expected = initial if row["turn"] == 1 else group[row["turn"]-2]["next_state"]
            assert row["current"] == expected
            if row["turn"] > 1:
                assert row["current"] == case["final_witness"] and row["current"] != initial
            assert all(row["before_checks"].values())
            assert row["state_policy"] == "model_responses"
            assert row["termination_policy"] == "first_failure"
            assert row["remind_previous_rules"] is remind_previous_rules
            assert row["prompt_protocol_version"] == prompt_version
            assert ("with_rule_reminders" in row["protocol_version"]) == remind_previous_rules
            assert row["state_source"] == ("predefined_case" if row["turn"] == 1 else "previous_next_state")
            assert "condition" not in row and "interference_degree" not in row
            users = [m["content"] for m in row["messages"] if m["role"] == "user"]
            assistants = [m["content"] for m in row["messages"] if m["role"] == "assistant"]
            assert len(users) == row["turn"]
            assert assistants == [r["raw_response"] for r in group[:row["turn"]-1]]
            assert all("reset" not in prompt for prompt in users)
            assert all(prompt.count("\nNew rule: ") == 1 for prompt in users)
            for prior in group[:row["turn"]]:
                assert users[prior["turn"]-1] == prior["messages"][-1]["content"]
            latest = users[-1]
            assert ("Previous rules (still binding):" in latest) == remind_previous_rules
            if remind_previous_rules:
                previous, introduced = latest.split("\nNew rule: ")
                for rule in row["old_rules"]:
                    description = f"{rule['id']}: {Rule.from_dict(rule).describe()}"
                    assert previous.count(description) == 1
                for future in (case["old_rules"]+[case["new_rule"]])[row["turn"]:]:
                    assert f"{future['id']}: {Rule.from_dict(future).describe()}" not in latest
            assert "witness" not in " ".join(users)
    focal = [r for r in rows if r["phase"] == "focal"]
    assert focal and all(r["model"] == "wrong" and r["horizon"] == 3 for r in focal)
    assert all(r["dynamic_certificate"]["label"] == "no_op" for r in focal)
    for name in ("malformed", "domain", "wrong"):
        summary = [s for s in result["summary"] if s["model"] == name]
        assert len(summary) == 1 and summary[0]["condition"] == "all"
        expected_observed = (3 if name == "wrong" else 2)*2*len(cases)
        assert summary[0]["records"] == summary[0]["full_success"]["denominator"] == expected_observed
        assert next(h for h in result["h1"] if h["model"] == name)["blocks"] == 0
        assert len([e for e in result["episodes"] if e["model"] == name]) == 2*len(cases)
        assert all(e["complete"] and e["terminated_on_failure"] and e["whole_episode_success"] == e["final_success"] == 0
                   for e in result["episodes"] if e["model"] == name)
    assert result["legacy_reset_prefix_records"] == 0
    assert sum(s["records"] for s in result["state_certification"]) == len(rows)
    count = len(calls)
    assert execute(path)["record_count"] == len(rows)
    assert len(calls) == count  # Replay does not repeat inference.
    config["remind_previous_rules"] = not remind_previous_rules
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError, match="different code/data/config"):
        execute(path)
    assert len(calls) == count  # Changing the prompt cannot append to an existing study.
    config["split"] = "test"
    with pytest.raises(ValueError, match="human audit"):
        validate_config(config, manifest)


@pytest.mark.parametrize("track", ["native", "order"])
@pytest.mark.parametrize("infrastructure", [False, True])
@pytest.mark.parametrize("remind_previous_rules", [False, True])
def test_llm_episode_uses_actual_responses_and_stops_before_next_rule(tmp_path, monkeypatch, track, infrastructure, remind_previous_rules):
    data, output = tmp_path/"data", tmp_path/"output"
    small_dataset(data)
    episodes = load_jsonl(data/"episodes.jsonl")
    episode = next(e for e in episodes if e["track"] == track and e["split"] == "development" and e["family"] == "forbidden_position")
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
            turn = len(sent)+1
            # Real, changing successful prefixes, then an invalid fourth answer.
            artifact = context["witness"][:-1]+("a" if turn % 2 else "b") if turn < 4 else "Z4"
            raw = json.dumps({"password": artifact})
            sent.append(messages)
            if turn == 4 and infrastructure:
                raise InfrastructureError("test provider unavailable")
            returned.append(raw)
            return Response(raw=raw, provider_response={}, attempts=1, latency_seconds=0, usage={}, cost_reserved=0)
        def close(self):
            pass
    monkeypatch.setattr("passgame.run.ChatAdapter", FakeChat)
    model = {"name":"mock-llm", "adapter":"chat", "model_id":"mock", "base_url":"https://example.com/v1",
             "input_price_per_million":1,"output_price_per_million":1,"pricing_verified_on":"2026-10-08","max_input_tokens":1000}
    config = {"study":"sequential-fixture", "dataset_dir":str(data), "split":"development", "tracks":[track],
              "models":[model], "output_dir":str(output), "budget_usd":1,"bootstrap_repetitions":20,"seed":1,
              "remind_previous_rules":remind_previous_rules}
    path = tmp_path/"config.yaml"
    path.write_text(yaml.safe_dump(config))
    if infrastructure:
        with pytest.raises(SystemExit) as error:
            execute(path)
        assert error.value.code == 2
    else:
        execute(path)
    rows = load_jsonl(output/"records.jsonl")
    assert len(episode["rules"]) == 8
    assert len(sent) == len(rows) == 4
    assert all(r["full_success"] for r in rows[:3])
    assert rows[-1]["full_success"] == (None if infrastructure else 0)
    assert rows[-1]["episode_terminal"] and rows[-1]["next_state"] is None
    completion = json.loads((output/"completion.json").read_text())
    assert completion["complete"] == (not infrastructure)
    assert completion["skipped_after_failure"] == (0 if infrastructure else 4)
    for i, (messages, row) in enumerate(zip(sent, rows)):
        users = [m["content"] for m in messages if m["role"] == "user"]
        assistants = [m["content"] for m in messages if m["role"] == "assistant"]
        assert len(users) == i+1
        assert assistants == returned[:i]
        assert row["prefix_source"] == "model_responses"
        assert row["current"] == (episode["initial"] if i == 0 else json.loads(returned[i-1])["password"])
        for j, prompt in enumerate(users):
            assert prompt.count("\nNew rule: ") == 1
            assert "New rule: "+episode["rules"][j]["id"]+": " in prompt
            assert ("Previous rules (still binding):" in prompt) == remind_previous_rules
            if remind_previous_rules:
                previous = prompt.split("\nNew rule: ")[0]
                for old in episode["rules"][:j]:
                    assert f"{old['id']}: {Rule.from_dict(old).describe()}" in previous
                for future in episode["rules"][j+1:]:
                    assert f"{future['id']}: {Rule.from_dict(future).describe()}" not in prompt
            assert prompt == sent[j][-1]["content"]  # Original turns remain unchanged in history.


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
