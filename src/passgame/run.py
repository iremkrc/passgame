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
    allowed = {"name", "adapter", "model_id", "base_url", "api_key_env", "max_input_tokens", "input_price_per_million", "output_price_per_million", "pricing_verified_on", "parameters", "transport_retries", "timeout_seconds"}
    if any(set(m)-allowed for m in config["models"]):
        raise ValueError("Unsupported model fields; credentials must use environment variables")
    if not set(config["tracks"]) <= {"controlled", "native", "order", "fresh"} or not config["tracks"]:
        raise ValueError("Unknown or empty evaluation tracks")
    paid = [m for m in config["models"] if m["adapter"] == "chat"]
    if paid and not set(config["tracks"]) <= {"native", "order"}:
        raise ValueError("LLM evaluation requires native/order trajectories with one new rule per turn and model-generated prefixes; controlled/fresh are offline diagnostics only")
    if paid and config["budget_usd"] <= 0:
        raise ValueError("Set an explicit positive API spending ceiling before model calls")
    for model in paid:
        for key in ("model_id", "base_url", "input_price_per_million", "output_price_per_million", "pricing_verified_on", "max_input_tokens"):
            if model.get(key) is None:
                raise ValueError(f"Model {model['name']} needs {key}")
        if model["model_id"].startswith("SET_"):
            raise ValueError("Replace placeholder model ID")
        datetime.fromisoformat(model["pricing_verified_on"])
    if paid and config["split"] == "test" and config.get("human_audit_required_for_paid_test", True) and manifest.get("human_audit_status") != "complete":
        raise ValueError("Held-out evaluation awaits the preregistered human audit; use development for the pilot")


def execute(config_path: Path, preflight_only: bool = False):
    config = yaml.safe_load(config_path.read_text())
    data_dir = Path(config["dataset_dir"])
    manifest = verify_manifest(data_dir)
    validate_config(config, manifest)
    cases = load_jsonl(data_dir/"pairs.jsonl")
    validation = validate_cases(cases)
    cases = [c for c in cases if c["split"] == config["split"]]
    episodes = [e for e in load_jsonl(data_dir/"episodes.jsonl") if e["split"] == config["split"]]
    unique_cases = {c["final_set_id"]: c for c in cases}
    per_model = (2*len(cases) if "controlled" in config["tracks"] else 0) + sum(len(e["rules"]) for e in episodes if e["track"] in config["tracks"]) + (len(unique_cases) if "fresh" in config["tracks"] else 0)
    effective = {"config": config, "config_hash": digest(config), "code_hash": source_hash(), "dataset_hash": digest(manifest["files"]), "planned_records": per_model*len(config["models"]), "validation": validation}
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
    uncertain = {e["request_key"] for e in events if e["event"] == "started" and e.get("paid")} - set(cache) - closed_without_response
    if uncertain:
        raise ValueError("An interrupted paid request has an unknown outcome; reconcile it before resuming")
    adapters = {}
    stopped = None
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
            append(events_path, {"event": "started", "request_key": key, "timestamp": stamp, "paid": model["adapter"] == "chat"})
            try:
                response = adapters[model["name"]].complete(messages, context)
            except BudgetExceeded:
                append(events_path, {"event": "budget_stopped", "request_key": key, "timestamp": datetime.now(timezone.utc).isoformat()})
                raise
            except InfrastructureError as error:
                row = {**base, "status": "infrastructure_failure", "failure_reason": str(error), "raw_response": None,
                       "full_success": None, "new_success": None, "retention": None, "next_state": context["current"]}
            else:
                metrics = score(context["current"], response.raw, old, new)
                if meta["track"] == "fresh":
                    metrics.update({"retention": None, "all_old_success": None, "fractional_retention": None, "retention_eligible": False, "previously_satisfied": [], "before_checks": None, "new_was_noop": None, "edit_distance": None,
                                    "newly_violated_old_rule_ids": None, "old_rules_broken": None})
                row = {**base, **metrics, "status": "response", "raw_response": response.raw,
                       "provider_response": response.provider_response, "attempts": response.attempts,
                       "latency_seconds": response.latency_seconds, "usage": response.usage, "reserved_cost_usd": response.cost_reserved,
                       "diagnostic_not_llm": model["adapter"] == "diagnostic"}
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
            for episode in episodes:
                if episode["track"] not in config["tracks"]:
                    continue
                current = episode["initial"]
                active, history = [], [{"role": "system", "content": SYSTEM}]
                rules = [Rule.from_dict(r) for r in episode["rules"]]
                for turn, new in enumerate(rules, 1):
                    old = active[:]
                    active.append(new)
                    history.append({"role": "user", "content": render(current, new)})
                    dynamic = certify(current, old, new, episode["witness"])
                    meta = {k:episode[k] for k in ("episode_id", "base_id", "final_set_id", "family", "track", "order", "split")}
                    meta.update({"turn": turn, "load": len(active), "horizon": len(rules), "dynamic_certificate": dynamic,
                                 "rule_disclosure": "one_new_rule_per_turn", "prefix_source": "model_responses" if model["adapter"] == "chat" else "diagnostic_responses"})
                    context = {"current": current, "witness": episode["witness"], "new_rule": new.to_dict()}
                    row = request(model, meta, history[:], context, old, new)
                    if row["status"] != "response":
                        break  # Do not fabricate a conversation response after infrastructure failure.
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
    completion = {"study": config["study"], "diagnostic_only": diagnostic, "record_count": len(rows), "planned_records": effective["planned_records"], "complete": len(rows) == effective["planned_records"] and result["infrastructure_failures"] == 0, "reserved_usd": budget.reserved, "stopped": stopped, "output_dir": str(output)}
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
    sequential = [r for r in rows if r["track"] in {"native", "order"}]
    for row in sequential:
        users = [m["content"] for m in row["messages"] if m["role"] == "user"]
        if len(users) != row["turn"] or any(message.count("\nNew rule: ") != 1 or "All active rules" in message for message in users):
            raise AssertionError("Sequential disclosure contract violated")
    print("SEQUENTIAL_PROTOCOL " + json.dumps({"verified_records": len(sequential), "new_rules_per_user_turn": 1,
                                               "cumulative_rule_reminders": False, "scripted_llm_prefixes": False,
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
