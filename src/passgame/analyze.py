"""Blocked bootstrap summaries from complete response evidence, with denominators."""

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import random
import statistics


def mean(values):
    return statistics.fmean(values) if values else None


def quantile(sorted_values: list[float], fraction: float):
    at = (len(sorted_values)-1)*fraction
    low = int(at)
    high = min(low+1, len(sorted_values)-1)
    return sorted_values[low] + (at-low)*(sorted_values[high]-sorted_values[low])


def paired_interval(differences: list[float], repetitions: int, seed: int) -> dict:
    if not differences:
        return {"estimate": None, "ci95": None, "blocks": 0}
    rng = random.Random(seed)
    draws = sorted(statistics.fmean(rng.choices(differences, k=len(differences))) for _ in range(repetitions))
    return {"estimate": mean(differences), "ci95": [quantile(draws, .025), quantile(draws, .975)], "blocks": len(differences)}


def rate(rows, field):
    values = [r.get(field) for r in rows if r.get(field) is not None]
    return {"numerator": sum(values), "denominator": len(values), "rate": mean(values)}




def analyze_orders(episodes: list[dict], models: list[str], repetitions: int, seed: int) -> dict:
    """Pair orders by final rules, actual initial string, and scheduled horizon."""
    h3, summaries, effects, survival = [], [], [], []
    for model in models:
        group = [e for e in episodes if e["model"] == model and e["track"] == "order"]
        blocks = defaultdict(dict)
        for episode in group:
            key = (episode["final_set_id"], episode["initial"], episode["horizon"])
            if episode["order"] in blocks[key]:
                raise ValueError("Repeated order variant in a comparison block; analyze separate runs separately")
            blocks[key][episode["order"]] = episode
        pairs = [p for p in blocks.values() if all(label in p and p[label]["complete"] for label in ("original","reverse"))]
        for endpoint in ("final_success","whole_episode_success"):
            differences = [p["original"][endpoint]-p["reverse"][endpoint] for p in pairs]
            h3.append({"model":model,"endpoint":endpoint,"contrast":"original_minus_reverse",
                       **paired_interval(differences,repetitions,seed+2)})
        for order in sorted({e["order"] for e in group}):
            observed = [e for e in group if e["order"] == order]
            complete = [e for e in observed if e["complete"]]
            summaries.append({"model":model,"order":order,"games":len(observed),
                              "completed_episodes":len(complete),"incomplete_episodes":len(observed)-len(complete),
                              "whole_episode_success":rate(complete,"whole_episode_success"),
                              "mean_turns_completed":mean([e["turns_completed"] for e in complete]),
                              "reached_horizon":sum(e["reached_horizon"] for e in complete),
                              "first_failure_histogram":dict(Counter(str(e["first_failure"]) if e["first_failure"] is not None else "passed" for e in complete))})
            for turn in range(1,max((e["horizon"] for e in complete),default=0)+1):
                eligible = [e for e in complete if e["horizon"] >= turn]
                passed = sum(e["turns_completed"] >= turn for e in eligible)
                survival.append({"model":model,"order":order,"turn":turn,"numerator":passed,
                                 "denominator":len(eligible),"rate":passed/len(eligible) if eligible else None,
                                 "at_risk":sum(e["first_failure"] is None or e["first_failure"] >= turn for e in eligible),
                                 "failures_at_turn":sum(e["first_failure"] == turn for e in eligible)})
        if group:
            for i, other in enumerate(("reverse","random_1","random_2")):
                pairs = [p for p in blocks.values() if all(label in p and p[label]["complete"] for label in ("original",other))]
                for j, endpoint in enumerate(("whole_episode_success","turns_completed")):
                    differences = [p["original"][endpoint]-p[other][endpoint] for p in pairs]
                    effects.append({"model":model,"endpoint":endpoint,"contrast":"original_minus_"+other,
                                    **paired_interval(differences,repetitions,seed+10+2*i+j)})
    return {"h3":h3,"order_summary":summaries,"order_effects":effects,"order_survival":survival}


def analyze(rows: list[dict], repetitions: int = 2000, seed: int = 20261008) -> dict:
    if repetitions < 1:
        raise ValueError("Bootstrap repetitions must be positive")
    if len({r["request_key"] for r in rows}) != len(rows):
        raise ValueError("Duplicate request rows")
    if any(row["track"] not in {"order", "seeded"} for row in rows):
        raise ValueError("Expected seeded or order response evidence")
    scored = rows
    groups = defaultdict(list)
    for row in scored:
        groups[(row["model"], row["track"], row.get("condition", "all"))].append(row)
    summaries = []
    for (model, track, condition), group in sorted(groups.items()):
        usable = [r for r in group if r["status"] == "response"]
        eligible = [r for r in usable if r.get("retention") is not None]
        new_pass = [r for r in eligible if r["new_success"]]
        summaries.append({"model": model, "track": track, "condition": condition, "records": len(group),
                          "missing_infrastructure": len(group)-len(usable), "full_success": rate(usable, "full_success"),
                          "new_success": rate(usable, "new_success"), "retention": rate(usable, "retention"), "all_old_success": rate(usable, "all_old_success"), "fractional_retention": rate(usable, "fractional_retention"),
                          "new_success_with_regression": {"numerator": sum(r["new_success"] == 1 and r["retention"] == 0 for r in eligible), "denominator": len(eligible)},
                          "regression_given_new_success": {"numerator": sum(r["retention"] == 0 for r in new_pass), "denominator": len(new_pass)},
                          "old_rules_broken": rate(usable, "old_rules_broken"),
                          "outcomes": dict(Counter(r["outcome"] for r in usable))})
    models = sorted({row["model"] for row in rows})
    trajectories = defaultdict(list)
    for row in rows:
        if row["track"] in {"order", "seeded"}:
            trajectories[(row["model"], row["episode_id"])].append(row)
    episode_results = []
    for (model, episode_id), group in sorted(trajectories.items()):
        group.sort(key=lambda r: r["turn"])
        horizon = group[0]["horizon"]
        last = group[-1]
        stop_on_failure = any(r.get("termination_policy") == "first_failure" for r in group)
        if stop_on_failure and any(r["status"] != "response" or not r["full_success"] for r in group[:-1]):
            raise ValueError("Episode contains a response after a terminal failure")
        contiguous = [r["turn"] for r in group] == list(range(1, len(group)+1))
        reached_horizon = contiguous and len(group) == horizon
        terminated_on_failure = stop_on_failure and last["status"] == "response" and last["full_success"] == 0
        complete = contiguous and all(r["status"] == "response" for r in group) and (reached_horizon or terminated_on_failure)
        first_failure = next((r["turn"] for r in group if r["status"] == "response" and not r["full_success"]), None)
        recovery = any(r["turn"] > first_failure and r["full_success"] for r in group if r["status"] == "response") if first_failure is not None else False
        episode_results.append({"model": model, "episode_id": episode_id, "base_id": group[0]["base_id"], "final_set_id": group[0]["final_set_id"], "track": group[0]["track"], "order": group[0]["order"], "initial_condition": group[0].get("initial_condition"), "horizon": horizon, "complete": complete,
                                "initial":group[0].get("initial",group[0].get("current")),
                                "turns_observed": len(group), "reached_horizon": reached_horizon, "terminated_on_failure": terminated_on_failure,
                                "turns_completed":(first_failure-1 if first_failure is not None else horizon) if complete else None,
                                "termination_reason": last.get("episode_end_reason") or ("infrastructure_failure" if last["status"] != "response" else ("rule_failure" if terminated_on_failure else ("horizon_reached" if reached_horizon else "incomplete"))),
                                "first_failure": first_failure, "right_censored": complete and first_failure is None,
                                "whole_episode_success": int(first_failure is None) if complete else None,
                                "final_success": group[-1]["full_success"] if complete else None, "recovered": recovery if complete else None})
    order_results = analyze_orders(episode_results,models,repetitions,seed)
    survival = []
    for model in models:
        for track in ("order", "seeded"):
            complete = [e for e in episode_results if e["model"] == model and e["track"] == track and e["complete"]]
            for turn in range(1, max((e["horizon"] for e in complete), default=0)+1):
                eligible = [e for e in complete if e["horizon"] >= turn]
                survival.append({"model": model, "track": track, "turn": turn, "numerator": sum(e["first_failure"] is None or e["first_failure"] > turn for e in eligible), "denominator": len(eligible),
                                 "at_risk": sum(e["first_failure"] is None or e["first_failure"] >= turn for e in eligible),
                                 "failures_at_turn": sum(e["first_failure"] == turn for e in eligible)})
    degree_groups = defaultdict(list)
    certification_groups = defaultdict(list)
    for row in scored:
        track = row["track"]
        if track in {"order", "seeded"}:
            certificate = row.get("dynamic_certificate", {})
            certification_groups[(row["model"], row["track"], row.get("family"), row.get("load", row["turn"]))].append(row)
            degree = certificate.get("min_old_rules_broken")
            if certificate.get("label") in {"independent", "interfering"} and degree is not None:
                degree_groups[(row["model"], row["track"], degree, "on_policy_"+row["track"])].append(row)
    interference = []
    for (model, track, degree, condition), group in sorted(degree_groups.items()):
        usable = [r for r in group if r["status"] == "response"]
        interference.append({"model": model, "track": track, "degree": degree, "condition": condition, "records": len(group),
                             "full_success": rate(usable, "full_success"), "new_success": rate(usable, "new_success"),
                             "retention": rate(usable, "retention"), "old_rules_broken": rate(usable, "old_rules_broken"),
                             "broken_count_histogram": dict(sorted(Counter(str(r.get("old_rules_broken")) for r in usable if r.get("old_rules_broken") is not None).items()))})
    state_certification = []
    for (model, track, family, load), group in sorted(certification_groups.items()):
        labels = dict(sorted(Counter(r.get("dynamic_certificate", {}).get("label", "unknown") for r in group).items()))
        usable = [r for r in group if r["status"] == "response"]
        state_certification.append({"model": model, "track": track, "family": family, "load": load,
                                    "records": len(group), "incoming_certificate_counts": labels,
                                    "full_success": rate(usable, "full_success"), "new_success": rate(usable, "new_success"),
                                    "retention": rate(usable, "retention"), "old_rules_broken": rate(usable, "old_rules_broken")})
    return {"record_count": len(rows), "response_count": sum(r["status"] == "response" for r in rows), "infrastructure_failures": sum(r["status"] != "response" for r in rows), "summary": summaries, "interference_breakdowns": interference, "state_certification": state_certification, **order_results, "episodes": episode_results, "survival": survival,
            "inference": "Successful model outputs carry forward; the first format, domain, or rule failure ends the conversation. Later turns are unattempted. Infrastructure failures leave the game incomplete. Interference strata are descriptive; order comparisons pair final rule sets, starting strings, and horizons."}



def write_analysis(rows: list[dict], output: Path, repetitions=2000, seed=20261008) -> dict:
    result = analyze(rows, repetitions, seed)
    output.mkdir(parents=True, exist_ok=True)
    (output/"analysis.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    with (output/"interference-summary.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["model", "track", "degree", "condition", "records", "full_rate", "new_rate", "retention_rate", "mean_old_rules_broken", "broken_count_denominator"])
        writer.writeheader()
        for r in result["interference_breakdowns"]:
            writer.writerow({**{k:r[k] for k in ("model", "track", "degree", "condition", "records")},
                             "full_rate": r["full_success"]["rate"], "new_rate": r["new_success"]["rate"],
                             "retention_rate": r["retention"]["rate"], "mean_old_rules_broken": r["old_rules_broken"]["rate"],
                             "broken_count_denominator": r["old_rules_broken"]["denominator"]})
    with (output/"summary.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["model", "track", "condition", "records", "missing_infrastructure", "full_numerator", "full_denominator", "full_rate", "new_rate", "retention_rate"])
        writer.writeheader()
        for r in result["summary"]:
            writer.writerow({**{k:r[k] for k in ("model", "track", "condition", "records", "missing_infrastructure")}, "full_numerator": r["full_success"]["numerator"], "full_denominator": r["full_success"]["denominator"], "full_rate": r["full_success"]["rate"], "new_rate": r["new_success"]["rate"], "retention_rate": r["retention"]["rate"]})
    with (output/"order-summary.csv").open("w",newline="") as f:
        fields = ["model","order","games","completed_episodes","incomplete_episodes","whole_passes","whole_denominator","whole_rate","mean_turns_completed","reached_horizon"]
        writer = csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        for row in result["order_summary"]:
            writer.writerow({**{k:row[k] for k in fields if k in row},
                             "whole_passes":row["whole_episode_success"]["numerator"],
                             "whole_denominator":row["whole_episode_success"]["denominator"],
                             "whole_rate":row["whole_episode_success"]["rate"]})
    with (output/"order-effects.csv").open("w",newline="") as f:
        writer = csv.DictWriter(f,fieldnames=["model","contrast","endpoint","blocks","estimate","ci95_low","ci95_high"])
        writer.writeheader()
        for row in result["order_effects"]:
            writer.writerow({**{k:row[k] for k in ("model","contrast","endpoint","blocks","estimate")},
                             "ci95_low":row["ci95"][0] if row["ci95"] else None,
                             "ci95_high":row["ci95"][1] if row["ci95"] else None})
    with (output/"order-survival.csv").open("w",newline="") as f:
        writer = csv.DictWriter(f,fieldnames=["model","order","turn","numerator","denominator","rate","at_risk","failures_at_turn"])
        writer.writeheader()
        writer.writerows(result["order_survival"])
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("records", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20261008)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.records.read_text().splitlines() if line]
    print(json.dumps(write_analysis(rows, args.output, repetitions=args.repetitions, seed=args.seed), indent=2))
