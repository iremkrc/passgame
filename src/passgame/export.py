"""Export readable rules, example games, and an unsigned audit worksheet."""

import argparse
import csv
import json
from pathlib import Path
from .constraints import Rule
from .generate import load_jsonl, verify_manifest, readable_reference, validate_episodes


def descriptions(rules):
    return [f"{r['id']}: {Rule.from_dict(r).describe()}" for r in rules]


def export(directory: Path, output: Path):
    manifest = verify_manifest(directory)
    episodes = load_jsonl(directory/"episodes.jsonl")
    validate_episodes(episodes)
    output.mkdir(parents=True,exist_ok=True)
    fields = ["episode_id","split","family","track","order","initial","rules_in_order","reference_challenges"]
    with (output/"passgame-rules.csv").open("w",newline="") as f:
        writer = csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        for e in episodes:
            writer.writerow({**{k:e[k] for k in fields[:6]},
                             "rules_in_order":"\n".join(descriptions(e["rules"])),
                             "reference_challenges":json.dumps(e.get("reference_challenges",{}),sort_keys=True)})
    for split in ("development","test"):
        (output/f"passgame-{split}-games.txt").write_text(readable_reference(episodes,split))
    audit = load_jsonl(directory/"audit-sample.jsonl")
    worksheet = ["PassGame human quality audit", f"Recorded status: {manifest['human_audit_status']}",
                 "This generated worksheet is unsigned. Exporting does not complete the audit.",
                 "Verify seeds, all eight prefixes, final witnesses, and the example interference certificates.", ""]
    for e in audit:
        worksheet.extend([e["episode_id"], "Initial: "+e["initial"], *descriptions(e["rules"]),
                          "Reference outputs: "+json.dumps(e["reference_outputs"]),
                          "Reference challenge degrees: "+json.dumps(e["reference_challenges"]),
                          "Reviewer: __________ Date: __________ Verified: [ ] Notes: __________", ""])
    (output/"passgame-audit-worksheet.txt").write_text("\n".join(worksheet)+"\n")
    return {"dataset_version":3,"episodes":len(episodes),"audit_games":len(audit),"output":str(output)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.dataset, args.output)))
