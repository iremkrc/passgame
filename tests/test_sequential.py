"""Regression checks for genuine progressive games, not pre-solved prefixes."""

from collections import Counter
import copy
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from passgame.audit import reference_check
from passgame.constraints import Rule
from passgame.generate import load_jsonl
from passgame.models import Response
from passgame.oracle import certify, one_edits
from passgame.protocol import SYSTEM, render
from passgame.run import execute, validate_config
from passgame.sequential import FAMILIES, build, validate_episodes, write_dataset


@pytest.fixture(scope="module")
def episodes():
    return build(dev_per_family=1, test_per_family=1)


def test_progressive_data_is_reproducible_disjoint_and_not_pre_solved(episodes):
    assert episodes == build(dev_per_family=1, test_per_family=1)
    assert validate_episodes(episodes)["neutral_initials_passed"] is True
    base = [e for e in episodes if e["track"] == "seeded"]
    assert len(base) == 12 and {e["family"] for e in base} == set(FAMILIES)
    assert Counter(e["split"] for e in base) == {"development":6,"test":6}
    assert len({e["final_set_id"] for e in base}) == 12
    for e in base:
        assert not reference_check(e["initial"],e["rules"][0])
        current = e["initial"]
        for turn, output in enumerate(e["reference_outputs"],1):
            assert not reference_check(current,e["rules"][turn-1])
            assert all(reference_check(output,r) for r in e["rules"][:turn])
            current = output
        assert min(map(int,e["reference_challenges"])) <= 5
        # Independently audit every shortest new-only edit at each example challenge.
        for t, degree in e["reference_challenges"].items():
            turn = int(t)
            old, new = e["rules"][:turn-1], e["rules"][turn-1]
            broken = [sum(not reference_check(s,r) for r in old)
                      for s in one_edits(e["reference_outputs"][turn-2]) if reference_check(s,new)]
            assert min(broken) == degree > 0
    orders = [e for e in episodes if e["track"] == "order"]
    assert len(orders) == 4*len(base)
    for original in base:
        variants = [e for e in orders if e["base_id"] == original["base_id"]]
        assert {e["order"] for e in variants} == {"original","reverse","random_1","random_2"}
        assert all(e["initial"] == original["initial"] for e in variants)
        assert all(sorted(e["rules"],key=lambda r:r["id"]) == original["rules"] for e in variants)


def test_discussed_example_is_in_the_dataset_and_has_early_interference(episodes):
    e = next(e for e in episodes if e["episode_id"] == "seeded-v3-development-numeric-000")
    assert e["initial"] == "abc1"
    assert e["reference_outputs"] == ["abc12","abc47","abc38","abc38_","abc38!","Xbc38!","XAc38!","XAc83!"]
    assert e["reference_challenges"] == {"3":1,"8":1}
    assert all(c["d_new"] == 1 and c["d_full"] == 2 for c in e["reference_certificates"].values())


def test_validator_rejects_pre_solved_initial_and_missing_progress(episodes):
    original = next(e for e in episodes if e["track"] == "seeded")
    e = copy.deepcopy(original)
    e["initial"] = e["witness"]
    with pytest.raises(ValueError,match="first rule must require"):
        validate_episodes([e])
    e = copy.deepcopy(original)
    e["reference_outputs"][0] = e["reference_outputs"][1]
    with pytest.raises(ValueError,match="repair at every turn"):
        validate_episodes([e])
    e = copy.deepcopy(original)
    e["reference_challenges"] = {"8":1}
    e["reference_certificates"] = {"8":e["reference_certificates"]["8"]}
    with pytest.raises(ValueError,match="early challenge"):
        validate_episodes([e])
    leaked = copy.deepcopy(original)
    leaked.update({"episode_id":"leaked-test-id","base_id":"leaked-base","split":"test"})
    with pytest.raises(ValueError,match="leakage"):
        validate_episodes([original,leaked])


def test_writer_preserves_historical_data_and_keeps_human_audit_pending(tmp_path):
    old = tmp_path/"historical"
    old.mkdir()
    raw = '{"version":2}'
    (old/"manifest.json").write_text(raw)
    with pytest.raises(ValueError,match="historical datasets"):
        write_dataset(old,dev_per_family=1,test_per_family=1)
    assert (old/"manifest.json").read_text() == raw
    new = tmp_path/"v3"
    manifest = write_dataset(new,dev_per_family=1,test_per_family=1)
    assert manifest["human_audit_status"] == "pending"
    assert "6 individual development games" in (new/"development-games.txt").read_text()
    assert all(hashlib.sha256((new/name).read_bytes()).hexdigest() == value for name,value in manifest["files"].items())
    config = {"split":"development","models":[{"name":"reference_oracle","adapter":"diagnostic"}],
              "tracks":["fixed_start"]}
    with pytest.raises(ValueError,match="explicit seeded/order episodes"):
        validate_config(config,manifest)
    config["tracks"] = ["seeded"]
    with pytest.raises(ValueError,match="version-3 sequential dataset"):
        validate_config(config,{"version":2})


@pytest.mark.parametrize("allow_markdown_fences", [False, True])
def test_seeded_runner_uses_real_outputs_stops_and_recertifies_actual_state(tmp_path,monkeypatch,allow_markdown_fences):
    data, output = tmp_path/"data", tmp_path/"results"
    write_dataset(data,dev_per_family=1,test_per_family=1)
    episode = next(e for e in load_jsonl(data/"episodes.jsonl") if e["episode_id"] == "seeded-v3-development-numeric-000")
    (data/"episodes.jsonl").write_text(json.dumps(episode)+"\n")
    manifest = json.loads((data/"manifest.json").read_text())
    manifest["files"]["episodes.jsonl"] = hashlib.sha256((data/"episodes.jsonl").read_bytes()).hexdigest()
    (data/"manifest.json").write_text(json.dumps(manifest))
    calls = []

    class FakeChat:
        def __init__(self,config,*args):
            self.name = config["name"]
        def complete(self,messages,context):
            turn = sum(m["role"] == "user" for m in messages)
            answer = episode["reference_outputs"][turn-1]
            if self.name == "anticipates" and turn <= 3:
                answer = "abc38"  # A different, valid model trajectory, already satisfying rule 3.
            if self.name == "fails" and turn == 3:
                answer = "abc48"
            calls.append((self.name,messages))
            raw = json.dumps({"password":answer})
            if allow_markdown_fences:
                raw = f"```json\n{raw}\n```"
            return Response(raw,{},1,0,{})
        def close(self):
            pass

    monkeypatch.setattr("passgame.run.ChatAdapter",FakeChat)
    models = [{"name":name,"adapter":"chat","deployment":"self_hosted","model_id":name,
               "base_url":"http://127.0.0.1:8000/v1","input_price_per_million":0,
               "output_price_per_million":0,"pricing_verified_on":"2026-10-24","max_input_tokens":32768}
              for name in ("succeeds","anticipates","fails")]
    config = {"study":"v3-fixture","dataset_dir":str(data),"split":"development","tracks":["seeded"],
              "rule_count":8,"remind_previous_rules":True,"allow_markdown_fences":allow_markdown_fences,
              "models":models,"output_dir":str(output),
              "budget_usd":0,"bootstrap_repetitions":20,"seed":1}
    path = tmp_path/"config.yaml"
    path.write_text(yaml.safe_dump(config))
    plan = execute(path,preflight_only=True)
    assert plan["planned_records"] == 24 and plan["planned_episodes"] == 3
    assert plan["selection"] == {"rule_count":8,"pairs":0,"seeded_episodes":1,"native_order_episodes":0}
    result = execute(path)
    rows = load_jsonl(output/"records.jsonl")
    assert len(rows) == 19 and sum(e["whole_episode_success"] for e in result["episodes"]) == 2
    completion = json.loads((output/"completion.json").read_text())
    assert completion["complete"] is True and completion["skipped_after_failure"] == 5
    response_protocol = {"version":"optional_markdown_fence_v1" if allow_markdown_fences else "strict_json_v1",
                         "allow_markdown_fences":allow_markdown_fences}
    assert completion["response_protocol"] == plan["response_protocol"] == response_protocol
    assert json.loads((output/"metadata.json").read_text())["response_protocol"] == response_protocol
    assert result["infrastructure_failures"] == 0
    for name in ("succeeds","anticipates","fails"):
        group = [r for r in rows if r["model"] == name]
        assert len(group) == (3 if name == "fails" else 8)
        history = [{"role":"system","content":SYSTEM}]
        current = "abc1"
        for turn,row in enumerate(group,1):
            assert row["markdown_fence_removed"] is allow_markdown_fences
            assert row["strict_parse_error"] == ("format_failure" if allow_markdown_fences else None)
            assert row["response_protocol_version"] == response_protocol["version"]
            assert row["allow_markdown_fences"] is allow_markdown_fences
            assert row["current"] == current and row["initial"] == "abc1"
            assert "initial_condition" not in row and "pair_id" not in row
            old = [Rule.from_dict(r) for r in row["old_rules"]]
            new = Rule.from_dict(row["new_rule"])
            history.append({"role":"user","content":render(current,new,old,remind_previous_rules=True)})
            assert row["messages"] == history
            assert row["phase"] == "sequential" and row["state_policy"] == "model_responses"
            assert row["dynamic_certificate"] == certify(current,old,new)
            for future in episode["rules"][turn:]:
                assert f"{future['id']}: {Rule.from_dict(future).describe()}" not in history[-1]["content"]
            current = row["artifact"]
            history.append({"role":"assistant","content":row["raw_response"]})
        third = group[2]
        assert third["reference_challenge_turn"] is True
        assert third["dynamic_certificate"]["label"] == ("no_op" if name == "anticipates" else "interfering")
        if name == "fails":
            assert third["episode_terminal"] and third["next_state"] is None
            assert third["episode_end_reason"] == "rule_failure"
    assert any(x["track"] == "seeded" and x["degree"] == 1 for x in result["interference_breakdowns"])
    count = len(calls)
    execute(path)
    assert len(calls) == count
    config["allow_markdown_fences"] = not allow_markdown_fences
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError,match="different code/data/config"):
        execute(path)
    assert len(calls) == count
    config["split"] = "test"
    with pytest.raises(ValueError,match="human audit"):
        validate_config(config,manifest)


def test_order_runner_restarts_only_between_games_and_preserves_each_permutation(tmp_path,monkeypatch):
    data,output = tmp_path/"data",tmp_path/"results"
    write_dataset(data,dev_per_family=1,test_per_family=1)
    original = next(e for e in load_jsonl(data/"episodes.jsonl") if e["episode_id"] == "seeded-v3-development-numeric-000")
    selected = [e for e in load_jsonl(data/"episodes.jsonl") if e["base_id"] == original["base_id"]]
    (data/"episodes.jsonl").write_text("".join(json.dumps(e)+"\n" for e in selected))
    manifest = json.loads((data/"manifest.json").read_text())
    manifest["files"]["episodes.jsonl"] = hashlib.sha256((data/"episodes.jsonl").read_bytes()).hexdigest()
    (data/"manifest.json").write_text(json.dumps(manifest))
    variants = [e for e in selected if e["track"] == "order"]
    failures = {"original":3,"reverse":1,"random_1":5,"random_2":None}
    calls = []

    class FakeChat:
        def __init__(self,*args):
            self.game = -1
        def complete(self,messages,context):
            turn = sum(m["role"] == "user" for m in messages)
            if turn == 1:
                self.game += 1
            failure = failures[variants[self.game]["order"]]
            answer = "Z" if turn == failure else original["witness"]
            calls.append(messages)
            return Response(json.dumps({"password":answer}),{},1,0,{})
        def close(self):
            pass

    monkeypatch.setattr("passgame.run.ChatAdapter",FakeChat)
    config = {"study":"order-fixture","dataset_dir":str(data),"split":"development","tracks":["order"],
              "rule_count":8,"remind_previous_rules":True,"output_dir":str(output),"budget_usd":0,
              "bootstrap_repetitions":20,"seed":1,"models":[{"name":"m","adapter":"chat",
              "deployment":"self_hosted","model_id":"m","base_url":"http://127.0.0.1:8000/v1",
              "input_price_per_million":0,"output_price_per_million":0,"pricing_verified_on":"2026-10-24",
              "max_input_tokens":32768}]}
    path = tmp_path/"config.yaml"
    path.write_text(yaml.safe_dump(config))
    result = execute(path)
    rows = load_jsonl(output/"records.jsonl")
    assert len(rows) == len(calls) == 17
    completion = json.loads((output/"completion.json").read_text())
    assert completion["complete"] is True and completion["skipped_after_failure"] == 15
    assert completion["planned_episodes"] == 4
    for e in variants:
        group = [r for r in rows if r["episode_id"] == e["episode_id"]]
        assert group[0]["current"] == original["initial"]
        history = [{"role":"system","content":SYSTEM}]
        current = original["initial"]
        for turn,row in enumerate(group,1):
            assert row["new_rule"] == e["rules"][turn-1]
            assert row["old_rules"] == e["rules"][:turn-1]
            old = [Rule.from_dict(r) for r in row["old_rules"]]
            history.append({"role":"user","content":render(current,Rule.from_dict(row["new_rule"]),old,remind_previous_rules=True)})
            assert row["messages"] == history and row["current"] == current
            current = row["artifact"]
            history.append({"role":"assistant","content":row["raw_response"]})
        assert len(group) == (failures[e["order"]] or 8)
        if failures[e["order"]]:
            assert group[-1]["next_state"] is None and group[-1]["episode_terminal"]
    assert {r["order"]:r["mean_turns_completed"] for r in result["order_summary"]} == {
        "original":2,"reverse":0,"random_1":4,"random_2":8}
    effect = next(r for r in result["order_effects"] if r["contrast"] == "original_minus_reverse" and r["endpoint"] == "turns_completed")
    assert effect["estimate"] == 2 and effect["blocks"] == 1
