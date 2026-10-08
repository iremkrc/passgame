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


def analyze(rows: list[dict], repetitions: int = 2000, seed: int = 20261008) -> dict:
    if repetitions < 1:
        raise ValueError("Bootstrap repetitions must be positive")
    if len({r["request_key"] for r in rows}) != len(rows):
        raise ValueError("Duplicate request rows")
    groups = defaultdict(list)
    for row in rows:
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
                          "outcomes": dict(Counter(r["outcome"] for r in usable))})
    h1, h2 = [], []
    models = sorted({r["model"] for r in rows})
    for model in models:
        paired = defaultdict(dict)
        for r in rows:
            if r["model"] == model and r["track"] == "controlled" and r["status"] == "response":
                if r["condition"] in paired[r["base_id"]]:
                    raise ValueError("Repeated controlled conditions need explicit nested-repeat analysis")
                paired[r["base_id"]][r["condition"]] = r
        complete = [p for p in paired.values() if set(p) == {"independent", "interfering"}]
        contrasts = [p["independent"]["full_success"]-p["interfering"]["full_success"] for p in complete]
        h1.append({"model": model, "contrast": "independent_minus_interfering", **paired_interval(contrasts, repetitions, seed)})
        regressions = [int(p["interfering"]["new_success"] and p["interfering"]["retention"] == 0)-int(p["independent"]["new_success"] and p["independent"]["retention"] == 0) for p in complete]
        h2.append({"model": model, "contrast": "interfering_minus_independent_unconditional_regression", **paired_interval(regressions, repetitions, seed+1)})
    trajectories = defaultdict(list)
    for row in rows:
        if row["track"] in {"native", "order"}:
            trajectories[(row["model"], row["episode_id"])].append(row)
    episode_results = []
    for (model, episode_id), group in sorted(trajectories.items()):
        group.sort(key=lambda r: r["turn"])
        horizon = group[0]["horizon"]
        complete = len(group) == horizon and all(r["status"] == "response" for r in group)
        first_failure = next((r["turn"] for r in group if r["status"] == "response" and not r["full_success"]), None)
        recovery = any(r["turn"] > first_failure and r["full_success"] for r in group if r["status"] == "response") if first_failure is not None else False
        episode_results.append({"model": model, "episode_id": episode_id, "base_id": group[0]["base_id"], "final_set_id": group[0]["final_set_id"], "track": group[0]["track"], "order": group[0]["order"], "horizon": horizon, "complete": complete, "first_failure": first_failure, "right_censored": complete and first_failure is None,
                                "whole_episode_success": int(first_failure is None) if complete else None,
                                "final_success": group[-1]["full_success"] if complete else None, "recovered": recovery if complete else None})
    h3 = []
    for model in models:
        orders = defaultdict(dict)
        for ep in episode_results:
            if ep["model"] == model and ep["track"] == "order" and ep["complete"]:
                orders[ep["final_set_id"]][ep["order"]] = ep
        complete = [p for p in orders.values() if "original" in p and "reverse" in p]
        for endpoint in ("final_success", "whole_episode_success"):
            diffs = [p["original"][endpoint]-p["reverse"][endpoint] for p in complete]
            h3.append({"model": model, "endpoint": endpoint, "contrast": "original_minus_reverse", **paired_interval(diffs, repetitions, seed+2)})
    survival = []
    for model in models:
        for track in ("native", "order"):
            complete = [e for e in episode_results if e["model"] == model and e["track"] == track and e["complete"]]
            for turn in range(1, max((e["horizon"] for e in complete), default=0)+1):
                survival.append({"model": model, "track": track, "turn": turn, "numerator": sum(e["first_failure"] is None or e["first_failure"] > turn for e in complete), "denominator": len(complete)})
    breakdowns = []
    subgroups = defaultdict(list)
    for r in rows:
        if r["track"] == "controlled":
            subgroups[(r["model"], r.get("family"), r.get("load"), r.get("condition"))].append(r)
    for (model, family, load, condition), group in sorted(subgroups.items()):
        usable = [r for r in group if r["status"] == "response"]
        breakdowns.append({"model": model, "family": family, "load": load, "condition": condition, "records": len(group), "full_success": rate(usable, "full_success"), "new_success": rate(usable, "new_success"), "retention": rate(usable, "retention")})
    return {"record_count": len(rows), "response_count": sum(r["status"] == "response" for r in rows), "infrastructure_failures": sum(r["status"] != "response" for r in rows), "summary": summaries, "breakdowns": breakdowns, "h1": h1, "h2": h2, "h3": h3, "episodes": episode_results, "survival": survival,
            "inference": "Paired bootstrap by base scenario for H1/H2; final-set blocks for H3. Intervals only; no confirmatory p-values or equivalence claims."}


def write_analysis(rows: list[dict], output: Path, repetitions=2000, seed=20261008) -> dict:
    result = analyze(rows, repetitions, seed)
    output.mkdir(parents=True, exist_ok=True)
    (output/"analysis.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    with (output/"summary.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["model", "track", "condition", "records", "missing_infrastructure", "full_numerator", "full_denominator", "full_rate", "new_rate", "retention_rate"])
        writer.writeheader()
        for r in result["summary"]:
            writer.writerow({**{k:r[k] for k in ("model", "track", "condition", "records", "missing_infrastructure")}, "full_numerator": r["full_success"]["numerator"], "full_denominator": r["full_success"]["denominator"], "full_rate": r["full_success"]["rate"], "new_rate": r["new_success"]["rate"], "retention_rate": r["retention"]["rate"]})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("records", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.records.read_text().splitlines() if line]
    print(json.dumps(write_analysis(rows, args.output), indent=2))
