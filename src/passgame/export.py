"""Export human-readable versioned rules and an unsigned audit worksheet."""

import argparse
import csv
import json
from pathlib import Path

from .constraints import Rule
from .generate import load_jsonl, verify_manifest
from .protocol import render


def descriptions(rules):
    return [f"{r['id']}: {Rule.from_dict(r).describe()}" for r in rules]


def export(directory: Path, output: Path):
    manifest = verify_manifest(directory)
    cases = load_jsonl(directory/"pairs.jsonl")
    episodes = load_jsonl(directory/"episodes.jsonl")
    audit = load_jsonl(directory/"audit-sample.jsonl")
    output.mkdir(parents=True, exist_ok=True)
    fields = ["kind", "id", "split", "family", "load", "offline_interference_degree", "order",
              "initial", "independent_state", "interfering_state", "new_only_distance", "full_distance_interfering",
              "minimum_old_rules_broken", "maximum_old_rules_broken", "minimum_break_witness",
              "minimum_break_rule_ids", "full_witness", "rules_in_order"]
    with (output/"passgame-v2-rules.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for case in cases:
            cert = case["certificates"]["interfering"]
            writer.writerow({"kind": "offline_pair", "id": case["pair_id"], "split": case["split"],
                             "family": case["family"], "load": case["load"], "offline_interference_degree": case["interference_degree"],
                             "independent_state": case["states"]["independent"], "interfering_state": case["states"]["interfering"],
                             "new_only_distance": cert["d_new"], "full_distance_interfering": cert["d_full"],
                             "minimum_old_rules_broken": cert["min_old_rules_broken"], "maximum_old_rules_broken": cert["max_old_rules_broken"],
                             "minimum_break_witness": cert["min_break_witness"], "minimum_break_rule_ids": json.dumps(cert["min_break_rule_ids"]),
                             "full_witness": cert["witness"], "rules_in_order": "\n".join(descriptions(case["old_rules"]+[case["new_rule"]]))})
        for episode in episodes:
            writer.writerow({"kind": episode["track"]+"_episode", "id": episode["episode_id"], "split": episode["split"],
                             "family": episode["family"], "load": len(episode["rules"]), "order": episode["order"],
                             "initial": episode["initial"], "full_witness": episode["witness"],
                             "rules_in_order": "\n".join(descriptions(episode["rules"]))})
    guide = ["# PassGame version 2 rules and sequential protocol", "",
             "LLM episodes reveal one new rule per user turn. Original conversation history is retained, including the model's actual answers. The main pilot sets remind_previous_rules: true and repeats every earlier rule in each latest message. The optional history-only comparison leaves those rules in their original turns. The model generates every intermediate password; the evaluator checks all active rules and stops the game at the first failure.", "",
             "The rules CSV is an evaluator/reviewer reference, not an LLM prompt. Episode degree fields are empty because actual interference depends on the model's incoming password. Offline pair degrees are minimum breakage over all shortest new-only repairs.", "",
             "## Multiple-rule example", "",
             "Current password `5991`. Previously introduced rules, one per earlier turn:", "",
             "1. Exactly four digits.", "2. Digit sum at most 24.", "3. Exactly one occurrence of `1`.",
             "4. Exactly four characters.", "5. Contains `91`.", "",
             "The main pilot's next user message is:", "", "```text",
             render("5991", Rule("new", "char_at", "8", position=4),
                    [Rule("digits", "digit_count", 4), Rule("sum", "digit_sum", 24, "le"),
                     Rule("ones", "char_count", "1", count=1), Rule("length", "length", 4),
                     Rule("pattern", "contains", "91")], remind_previous_rules=True), "```", "",
             "Changing to `5998` satisfies the new rule but breaks three old rules: sum (31), one-occurrence count (zero), and required substring (absent). Inserting instead, `59981`, breaks four old rules. Both are one edit away. Coordinated repair `5918` satisfies every rule in two edits. Under the same rules, `9159` has a safe one-edit repair `9158`.", "",
             "## Certificate columns", "",
             "- New-only distance: minimum edits satisfying only the new rule.",
             "- Full distance: minimum edits satisfying all active rules.",
             "- Minimum/maximum old rules broken: extrema over all shortest new-only repairs.",
             "- Minimum-break witness and IDs: one shortest repair with the minimum breakage and its failed old rules.",
             "- Full-valid one-edit candidates: distinct one-edit strings satisfying all active rules.",
             "- Possibly/necessarily affected rule IDs (JSON certificates): union/intersection of broken IDs over shortest new-only repairs. The minimum count can exceed the size of the intersection because different repairs break different rules.", "",
             "The evaluator also records actual old-rule regressions for each response. Only rules satisfied on the incoming password count as newly broken; invalid output has unknown breakage count.", "",
             f"Dataset version {manifest['version']}: {len(cases)} pairs and {len(episodes)} episodes. Human audit remains {manifest['human_audit_status']}. No LLM evaluation has been performed in this implementation validation."]
    (output/"passgame-v2-rules-guide.md").write_text("\n".join(guide)+"\n")
    lines = ["# PassGame version 2 human audit worksheet", "",
             "Status: pending. This worksheet has not been reviewed or signed by a researcher.", "",
             "Review both states, all old/new rules, full witnesses, and the complete shortest new-only neighborhood. Verify multiple-rule guarantees including insertions/deletions; do not assume the same IDs break for every repair.", "",
             "| Pair | Family | Active rules | Guaranteed old rules broken | Independent state | Interfering state |",
             "| --- | --- | ---: | ---: | --- | --- |"]
    for case in audit:
        lines.append(f"| {case['pair_id']} | {case['family']} | {case['load']} | {case['interference_degree']} | `{case['states']['independent']}` | `{case['states']['interfering']}` |")
    for case in audit:
        lines.extend(["", f"## {case['pair_id']}", "", "Old rules:", ""])
        lines.extend(f"- {description}" for description in descriptions(case["old_rules"]))
        lines.extend(["", "New rule: "+Rule.from_dict(case["new_rule"]).describe(), "",
                      "| State type | Input | New-only/full distance | Full-valid one-edit candidates | Min/max old rules broken | Minimum-break repair | Broken rule IDs | Full witness |",
                      "| --- | --- | --- | ---: | --- | --- | --- | --- |"])
        for condition in ("independent", "interfering"):
            cert = case["certificates"][condition]
            lines.append(f"| {condition} | `{case['states'][condition]}` | {cert['d_new']} / {cert['d_full']} | {cert['one_edit_full_valid']} | {cert['min_old_rules_broken']} / {cert['max_old_rules_broken']} | `{cert['min_break_witness']}` | {', '.join(cert['min_break_rule_ids']) or 'none'} | `{cert['witness']}` |")
        lines.extend(["", "Reviewer: __________ Date: __________ Verified: [ ] Discrepancies/resolution: __________"])
    (output/"passgame-v2-audit-worksheet.md").write_text("\n".join(lines)+"\n")
    return {"pairs": len(cases), "episodes": len(episodes), "audit_pairs": len(audit), "output": str(output)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.dataset, args.output)))
