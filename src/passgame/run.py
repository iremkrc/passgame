"""Resumable fixed-contract evaluation. Evidence is flushed before progress prints."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import yaml

from .analyze import write_analysis
from .constraints import Rule, checks
from .generate import digest, load_jsonl, validate_cases, verify_manifest
from .models import Budget, BudgetExceeded, ChatAdapter, DiagnosticAdapter, InfrastructureError
from .oracle import certify
from .protocol import SYSTEM, controlled_messages, fresh_messages, render, score
from .sequential import validate_episodes


def source_hash() -> str:
    h = hashlib.sha256()
    root = Path(__file__).resolve().parents[2]
    for path in sorted(Path(__file__).parent.glob("*.py")) + [root/"pyproject.toml", root/"uv.lock"]:
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def append(path: Path, record: dict):
    with path.open("a") as f:
        f.write(json.dumps(record, sort_keys=True)+"\n")
        f.flush()
        import os
        os.fsync(f.fileno())


def validate_config(config: dict, manifest: dict):
    if config.get("split") not in {"development", "test"}:
        raise ValueError("Select development or test split explicitly")
    if not config.get("models") or len({m["name"] for m in config["models"]}) != len(config["models"]):
        raise ValueError("Model names must be unique and nonempty")
    if any(m["adapter"] not in {"diagnostic", "chat"} for m in config["models"]):
        raise ValueError("Unknown model adapter")
    allowed = {"name", "adapter", "deployment", "model_id", "base_url", "api_key_env", "max_input_tokens", "input_price_per_million", "output_price_per_million", "pricing_verified_on", "parameters", "transport_retries", "timeout_seconds"}
    if any(set(m)-allowed for m in config["models"]):
        raise ValueError("Unsupported model fields; credentials must use environment variables")
    if not set(config["tracks"]) <= {"controlled", "native", "order", "fresh", "fixed_start", "seeded"} or not config["tracks"]:
        raise ValueError("Unknown or empty evaluation tracks")
    if manifest.get("version") == 3 and not set(config["tracks"]) <= {"seeded", "order"}:
        raise ValueError("Version 3 uses explicit seeded/order episodes, not fixed focal states")
    if "seeded" in config["tracks"] and manifest.get("version") != 3:
        raise ValueError("The seeded track requires the version-3 sequential dataset")
    rule_count = config.get("rule_count")
    if rule_count is not None and (type(rule_count) is not int or rule_count < 1):
        raise ValueError("rule_count must be a positive integer")
    if type(config.get("remind_previous_rules", False)) is not bool:
        raise ValueError("remind_previous_rules must be a boolean")
    chat = [m for m in config["models"] if m["adapter"] == "chat"]
    if any(m.get("deployment", "provider") not in {"provider", "self_hosted"} for m in chat):
        raise ValueError("Unknown deployment; select provider or self_hosted")
    for model in chat:
        if model.get("deployment") == "self_hosted" and any(model.get(k) != 0 for k in ("input_price_per_million", "output_price_per_million")):
            raise ValueError("Self-hosted endpoints require explicit zero API token prices")
    paid = [m for m in chat if m.get("deployment", "provider") != "self_hosted"]
    if chat and not set(config["tracks"]) <= {"native", "order", "fixed_start", "seeded"}:
        raise ValueError("LLM evaluation requires native/order/fixed_start/seeded conversations with one new rule per turn and model-generated prefixes; controlled/fresh are offline diagnostics only")
    if paid and config["budget_usd"] <= 0:
        raise ValueError("Set an explicit positive API spending ceiling before model calls")
    for model in chat:
        for key in ("model_id", "base_url", "input_price_per_million", "output_price_per_million", "pricing_verified_on", "max_input_tokens"):
            if model.get(key) is None:
                raise ValueError(f"Model {model['name']} needs {key}")
        if model["model_id"].startswith("SET_"):
            raise ValueError("Replace placeholder model ID")
        datetime.fromisoformat(model["pricing_verified_on"])
    audit_required = config.get("human_audit_required_for_model_test", config.get("human_audit_required_for_paid_test", True))
    if chat and config["split"] == "test" and audit_required and manifest.get("human_audit_status") != "complete":
        raise ValueError("Held-out evaluation awaits the preregistered human audit; use development for the pilot")


def execute(config_path: Path, preflight_only: bool = False):
    config = yaml.safe_load(config_path.read_text())
    data_dir = Path(config["dataset_dir"])
    manifest = verify_manifest(data_dir)
    validate_config(config, manifest)
    remind_previous_rules = config.get("remind_previous_rules", False)
    prompt_protocol = {"version": "cumulative_rule_reminders_v1" if remind_previous_rules else "history_only_v1",
                       "remind_previous_rules": remind_previous_rules}
    if manifest.get("version") == 3:
        cases = []
        episodes = load_jsonl(data_dir/"episodes.jsonl")
        validation = validate_episodes(episodes)
    else:
        cases = load_jsonl(data_dir/"pairs.jsonl")
        validation = validate_cases(cases)
        episodes = load_jsonl(data_dir/"episodes.jsonl")
    cases = [c for c in cases if c["split"] == config["split"]]
    episodes = [e for e in episodes if e["split"] == config["split"]]
    rule_count = config.get("rule_count")
    if rule_count is not None:
        cases = [c for c in cases if len(c["old_rules"])+1 == rule_count]
        episodes = [e for e in episodes if len(e["rules"]) == rule_count]
    unique_cases = {c["final_set_id"]: c for c in cases}
    per_model = (2*len(cases) if "controlled" in config["tracks"] else 0) + sum(len(e["rules"]) for e in episodes if e["track"] in config["tracks"]) + (len(unique_cases) if "fresh" in config["tracks"] else 0)
    if "fixed_start" in config["tracks"]:
        per_model += 2*sum(len(c["old_rules"])+1 for c in cases)
    per_model_episodes = sum(e["track"] in config["tracks"] for e in episodes)
    if "fixed_start" in config["tracks"]:
        per_model_episodes += 2*len(cases)
    if per_model == 0:
        raise ValueError("No cases or episodes match the selected split, tracks, and rule_count")
    effective = {"config": config, "config_hash": digest(config), "code_hash": source_hash(), "dataset_hash": digest(manifest["files"]), "planned_records": per_model*len(config["models"]),
                 "planned_records_are_upper_bound": True, "planned_episodes": per_model_episodes*len(config["models"]),
                 "selection": {"rule_count": rule_count, "pairs": len(cases), "native_order_episodes": sum(e["track"] in config["tracks"] for e in episodes)},
                 "episode_termination_policy": "first_failure", "prompt_protocol": prompt_protocol, "validation": validation}
    if manifest.get("version") == 3:
        effective["selection"] = {"rule_count":rule_count, "pairs":0,
                                  "seeded_episodes":sum(e["track"] == "seeded" for e in episodes if e["track"] in config["tracks"]),
                                  "native_order_episodes":sum(e["track"] == "order" for e in episodes if e["track"] in config["tracks"])}
        effective.update({"dataset_version":3, "episode_suite":manifest["suite"]})
    print("CONFIG " + json.dumps({k:v for k,v in effective.items() if k != "validation"}, sort_keys=True), flush=True)
    print("VALIDATION " + json.dumps(validation, sort_keys=True), flush=True)
    output = Path(config["output_dir"]).resolve()
    if preflight_only:
        budget = Budget(float(config["budget_usd"]))
        for model in config["models"]:
            if model["adapter"] == "chat":
                adapter = ChatAdapter(model, budget)
                adapter.close()
            elif model["adapter"] == "diagnostic":
                DiagnosticAdapter(model["name"])
            else:
                raise ValueError("Unknown adapter")
        print("PREFLIGHT passed; no model requests sent", flush=True)
        return effective
    output.mkdir(parents=True, exist_ok=True)
    metadata = output/"metadata.json"
    if metadata.exists():
        previous = json.loads(metadata.read_text())
        if any(previous[k] != effective[k] for k in ("config_hash", "code_hash", "dataset_hash")):
            raise ValueError("Output directory belongs to different code/data/config; use a new directory")
    else:
        metadata.write_text(json.dumps(effective, indent=2, sort_keys=True)+"\n")
    records_path, events_path, ledger_path = (output/n for n in ("records.jsonl", "events.jsonl", "budget.json"))
    rows = load_jsonl(records_path) if records_path.exists() else []
    cache = {r["request_key"]: r for r in rows}
    if len(cache) != len(rows):
        raise ValueError("Duplicate evidence rows")
    reserved = json.loads(ledger_path.read_text())["reserved_usd"] if ledger_path.exists() else 0.0
    budget = Budget(float(config["budget_usd"]), reserved)
    def ledger(value):
        temporary = ledger_path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"reserved_usd": value, "limit_usd": budget.limit})+"\n")
        temporary.replace(ledger_path)
    ledger(reserved)
    events = load_jsonl(events_path) if events_path.exists() else []
    closed_without_response = {e["request_key"] for e in events if e["event"] == "budget_stopped"}
    uncertain = {e["request_key"] for e in events if e["event"] == "started" and (e.get("paid") or e.get("model_request"))} - set(cache) - closed_without_response
    if uncertain:
        raise ValueError("An interrupted model request has an unknown outcome; reconcile it before resuming")
    adapters = {}
    stopped = None
    skipped_after_failure = 0
    try:
        for model in config["models"]:
            adapters[model["name"]] = DiagnosticAdapter(model["name"]) if model["adapter"] == "diagnostic" else ChatAdapter(model, budget, ledger)
        def request(model, meta, messages, context, old, new):
            key = digest({"model": model, "metadata": meta, "messages": messages, "config": effective["config_hash"], "code": effective["code_hash"], "data": effective["dataset_hash"]})
            if key in cache:
                return cache[key]
            stamp = datetime.now(timezone.utc).isoformat()
            base = {**meta, "model": model["name"], "model_config": model, "request_key": key, "timestamp": stamp, "messages": messages,
                    "current": context["current"], "old_rules": [r.to_dict() for r in old], "new_rule": new.to_dict(),
                    "config_hash": effective["config_hash"], "code_hash": effective["code_hash"], "dataset_hash": effective["dataset_hash"]}
            # Preserve duplicate-request protection for self-hosted inference too.
            append(events_path, {"event": "started", "request_key": key, "timestamp": stamp,
                                 "paid": model["adapter"] == "chat" and model.get("deployment", "provider") != "self_hosted",
                                 "model_request": model["adapter"] == "chat"})
            try:
                response = adapters[model["name"]].complete(messages, context)
            except BudgetExceeded:
                append(events_path, {"event": "budget_stopped", "request_key": key, "timestamp": datetime.now(timezone.utc).isoformat()})
                raise
            except InfrastructureError as error:
                row = {**base, "status": "infrastructure_failure", "failure_reason": str(error), "raw_response": None,
                       "full_success": None, "new_success": None, "retention": None, "next_state": context["current"]}
                if meta.get("termination_policy") == "first_failure":
                    row.update({"episode_terminal": True, "episode_end_reason": "infrastructure_failure", "next_state": None})
            else:
                metrics = score(context["current"], response.raw, old, new)
                if meta["track"] == "fresh":
                    metrics.update({"retention": None, "all_old_success": None, "fractional_retention": None, "retention_eligible": False, "previously_satisfied": [], "before_checks": None, "new_was_noop": None, "edit_distance": None,
                                    "newly_violated_old_rule_ids": None, "old_rules_broken": None})
                row = {**base, **metrics, "status": "response", "raw_response": response.raw,
                       "provider_response": response.provider_response, "attempts": response.attempts,
                       "latency_seconds": response.latency_seconds, "usage": response.usage, "reserved_cost_usd": response.cost_reserved,
                       "diagnostic_not_llm": model["adapter"] == "diagnostic"}
                if meta.get("termination_policy") == "first_failure":
                    failed = not metrics["full_success"]
                    row["episode_terminal"] = failed or meta["turn"] == meta["horizon"]
                    row["episode_end_reason"] = (metrics["parse_error"] or "rule_failure") if failed else ("horizon_reached" if row["episode_terminal"] else None)
                    if failed:
                        row["next_state"] = None
            append(records_path, row)
            cache[key] = row
            rows.append(row)
            if len(rows) % 100 == 0:
                print(f"PROGRESS records={len(rows)} reserved_usd={budget.reserved:.6f}", flush=True)
            return row
        for model in config["models"]:
            for case in cases if "controlled" in config["tracks"] else []:
                old, new = [Rule.from_dict(r) for r in case["old_rules"]], Rule.from_dict(case["new_rule"])
                for condition in ("independent", "interfering"):
                    context = {"current": case["states"][condition], "witness": case["certificates"][condition]["witness"], "new_rule": new.to_dict()}
                    meta = {"track": "controlled", "pair_id": case["pair_id"], "base_id": case["base_id"], "final_set_id": case["final_set_id"], "family": case["family"], "load": case["load"], "condition": condition, "turn": case["load"], "split": case["split"], "certificate": case["certificates"][condition],
                            "interference_degree": case["interference_degree"], "prefix_source": "scripted_oracle"}
                    request(model, meta, controlled_messages(case, condition), context, old, new)
            for case in cases if "fixed_start" in config["tracks"] else []:
                rules = [Rule.from_dict(r) for r in case["old_rules"]+[case["new_rule"]]]
                for condition in ("independent", "interfering"):
                    initial = current = case["states"][condition]
                    history = [{"role": "system", "content": SYSTEM}]
                    for turn, new in enumerate(rules, 1):
                        old, focal = rules[:turn-1], turn == len(rules)
                        # Standardize the initial state only. Every later input
                        # follows the actual response and normal parse policy.
                        history.append({"role": "user", "content": render(current, new, old, remind_previous_rules=remind_previous_rules)})
                        certificate = certify(current, old, new)
                        meta = {"track": "fixed_start", "phase": "focal" if focal else "prefix",
                                "episode_id": f"fixed-start-{case['pair_id']}-{condition}",
                                "pair_id": case["pair_id"], "base_id": case["base_id"],
                                "final_set_id": case["final_set_id"], "family": case["family"],
                                "initial_condition": condition, "initial": initial,
                                "turn": turn, "load": turn, "horizon": len(rules),
                                "order": "original", "split": case["split"],
                                "intended_interference_degree": case["interference_degree"],
                                "dynamic_certificate": certificate,
                                "rule_disclosure": "one_new_rule_per_turn",
                                "remind_previous_rules": remind_previous_rules,
                                "prompt_protocol_version": prompt_protocol["version"],
                                "prefix_source": "model_responses" if model["adapter"] == "chat" else "diagnostic_responses",
                                "state_source": "predefined_case" if turn == 1 else "previous_next_state",
                                "state_policy": "model_responses",
                                "termination_policy": "first_failure",
                                "protocol_version": ("predefined_start_then_model_outputs_with_rule_reminders_stop_on_failure_v3"
                                                     if remind_previous_rules else "predefined_start_then_model_outputs_stop_on_failure_v2")}
                        context = {"current": current, "witness": case["final_witness"], "new_rule": new.to_dict()}
                        row = request(model, meta, history[:], context, old, new)
                        if row["status"] != "response":
                            break
                        if not row["full_success"]:
                            skipped_after_failure += len(rules)-turn
                            break
                        current = row["next_state"]
                        history.append({"role": "assistant", "content": row["raw_response"]})
            for episode in episodes:
                if episode["track"] not in config["tracks"]:
                    continue
                current = episode["initial"]
                active, history = [], [{"role": "system", "content": SYSTEM}]
                rules = [Rule.from_dict(r) for r in episode["rules"]]
                for turn, new in enumerate(rules, 1):
                    old = active[:]
                    active.append(new)
                    history.append({"role": "user", "content": render(current, new, old, remind_previous_rules=remind_previous_rules)})
                    dynamic = certify(current, old, new)
                    meta = {k:episode[k] for k in ("episode_id", "base_id", "final_set_id", "family", "track", "order", "split")}
                    meta.update({"turn": turn, "load": len(active), "horizon": len(rules), "dynamic_certificate": dynamic,
                                 "rule_disclosure": "one_new_rule_per_turn", "prefix_source": "model_responses" if model["adapter"] == "chat" else "diagnostic_responses",
                                 "remind_previous_rules": remind_previous_rules, "prompt_protocol_version": prompt_protocol["version"],
                                 "termination_policy": "first_failure", "protocol_version": ("sequential_with_rule_reminders_stop_on_failure_v2"
                                                                                            if remind_previous_rules else "sequential_stop_on_failure_v1")})
                    witness = episode["witness"]
                    if manifest.get("version") == 3:
                        meta.update({"initial":episode["initial"], "state_policy":"model_responses",
                                     "state_source":"neutral_seed" if turn == 1 else "previous_next_state",
                                     "phase":"sequential", "dataset_version":3, "episode_suite":episode["suite"],
                                     "protocol_version":"neutral_seed_model_outputs_stop_on_failure_v1",
                                     "reference_challenge_turn":str(turn) in episode.get("reference_challenges", {})})
                        # Only the offline reference algorithm uses this private path.
                        # ChatAdapter receives the actual conversation messages alone.
                        if model["adapter"] == "diagnostic" and episode["track"] == "seeded":
                            witness = episode["reference_outputs"][turn-1]
                    context = {"current": current, "witness": witness, "new_rule": new.to_dict()}
                    row = request(model, meta, history[:], context, old, new)
                    if row["status"] != "response":
                        break  # Do not fabricate a conversation response after infrastructure failure.
                    if not row["full_success"]:
                        skipped_after_failure += len(rules)-turn
                        break
                    current = row["next_state"]
                    history.append({"role": "assistant", "content": row["raw_response"]})
            if "fresh" in config["tracks"]:
                for case in unique_cases.values():
                    old, new = [Rule.from_dict(r) for r in case["old_rules"]], Rule.from_dict(case["new_rule"])
                    meta = {"track": "fresh", "base_id": case["base_id"], "final_set_id": case["final_set_id"], "family": case["family"], "split": case["split"], "turn": 1}
                    context = {"current": "seed0!", "witness": case["final_witness"], "new_rule": new.to_dict()}
                    request(model, meta, fresh_messages(old+[new]), context, old, new)
    except BudgetExceeded as error:
        stopped = str(error)
    finally:
        for adapter in adapters.values():
            if hasattr(adapter, "close"):
                adapter.close()
    result = write_analysis(rows, output, config["bootstrap_repetitions"], config["seed"])
    diagnostic = all(m["adapter"] == "diagnostic" for m in config["models"])
    completed_episodes = sum(e["complete"] for e in result["episodes"])
    completion = {"study": config["study"], "diagnostic_only": diagnostic, "record_count": len(rows), "planned_records": effective["planned_records"],
                  "prompt_protocol": prompt_protocol,
                  "planned_records_are_upper_bound": True, "skipped_after_failure": skipped_after_failure,
                  "expected_records": effective["planned_records"]-skipped_after_failure,
                  "planned_episodes": effective["planned_episodes"], "completed_episodes": completed_episodes,
                  "terminated_on_failure": sum(e["terminated_on_failure"] for e in result["episodes"]),
                  "complete": len(rows)+skipped_after_failure == effective["planned_records"] and completed_episodes == effective["planned_episodes"] and result["infrastructure_failures"] == 0 and stopped is None,
                  "reserved_usd": budget.reserved, "stopped": stopped, "output_dir": str(output)}
    for summary in result["summary"]:
        print("METRIC " + json.dumps(summary, sort_keys=True), flush=True)
    for label in ("h1", "h2", "h3"):
        print(label.upper() + " " + json.dumps(result[label], sort_keys=True), flush=True)
    if not completion["complete"]:
        (output/"completion.json").write_text(json.dumps(completion, indent=2)+"\n")
        print("SUMMARY " + json.dumps(completion, sort_keys=True), flush=True)
        raise SystemExit(2)
    if diagnostic:
        for r in rows:
            if r["model"] == "reference_oracle" and r["full_success"] != 1:
                raise AssertionError("Reference witness failed a rule")
            if r["track"] == "controlled" and r["model"] == "unchanged" and (r["full_success"], r["new_success"], r["retention"]) != (0, 0, 1):
                raise AssertionError("Unchanged baseline failed the focal-input contract")
            if r["track"] == "controlled" and r["model"] == "new_only":
                if r["new_success"] != 1 or r["edit_distance"] != 1:
                    raise AssertionError("New-only baseline did not exhibit the certified diagnostic behavior")
                if r["condition"] == "interfering" and (r["full_success"], r["retention"]) != (0, 0):
                    raise AssertionError("A one-edit interfering repair unexpectedly preserved old rules")
                if r["condition"] == "interfering" and r["old_rules_broken"] < r["interference_degree"]:
                    raise AssertionError("New-only repair broke fewer old rules than certified")
        print("DIAGNOSTIC_CONTRACT passed; these algorithmic results are not LLM evidence", flush=True)
    print("INTERFERENCE " + json.dumps(result["interference_breakdowns"], sort_keys=True), flush=True)
    sequential = [r for r in rows if r["track"] in {"native", "order", "fixed_start", "seeded"}]
    for row in sequential:
        users = [m["content"] for m in row["messages"] if m["role"] == "user"]
        expected_prompt = render(row["current"], Rule.from_dict(row["new_rule"]),
                                 [Rule.from_dict(r) for r in row["old_rules"]],
                                 remind_previous_rules=remind_previous_rules)
        if (len(users) != row["turn"] or any(message.count("\nNew rule: ") != 1 for message in users)
                or row["messages"][-1] != {"role": "user", "content": expected_prompt}
                or row["remind_previous_rules"] != remind_previous_rules):
            raise AssertionError("Sequential disclosure contract violated")
    print("SEQUENTIAL_PROTOCOL " + json.dumps({"verified_records": len(sequential), "new_rules_per_user_turn": 1,
                                               "cumulative_rule_reminders": remind_previous_rules,
                                               "prompt_protocol_version": prompt_protocol["version"], "scripted_llm_prefixes": False,
                                               "history": "original user turns and actual adapter responses"}, sort_keys=True), flush=True)
    (output/"completion.json").write_text(json.dumps(completion, indent=2)+"\n")
    print("SUMMARY " + json.dumps(completion, sort_keys=True), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    execute(args.config, args.preflight)
