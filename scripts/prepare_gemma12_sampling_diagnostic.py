"""Freeze an outcome-independent, six-game development decoding diagnostic."""

import argparse
import hashlib
import json
from pathlib import Path
import random

from passgame.generate import digest, load_jsonl, verify_manifest
from passgame.sequential import FAMILIES, readable_reference, validate_episodes


def prepare(source: Path, output: Path, selection_seed: int = 20261024):
    source_manifest = verify_manifest(source)
    episodes = load_jsonl(source/"episodes.jsonl")
    rng = random.Random(selection_seed)
    selected = []
    for family in FAMILIES:
        candidates = sorted((e for e in episodes if e["split"] == "development"
                             and e["track"] == "seeded" and e["family"] == family),
                            key=lambda e:e["episode_id"])
        selected.append(rng.choice(candidates))
    bases = {e["base_id"] for e in selected}
    subset = selected + [e for e in episodes if e["base_id"] in bases
                         and e["track"] == "order" and e["order"] == "original"]
    assert len(subset) == 12 and all(e["split"] == "development" for e in subset)
    validation = validate_episodes(subset)
    contents = {"episodes.jsonl":"".join(json.dumps(e,sort_keys=True)+"\n" for e in subset),
                "development-games.txt":readable_reference(subset)}
    manifest = {"version":3,"suite":source_manifest["suite"],"seed":source_manifest["seed"],
                "human_audit_status":"pending","development_only":True,
                "purpose":"separate decoding diagnostic; not main-study replacement",
                "source_manifest_files_hash":digest(source_manifest["files"]),
                "selection":{"seed":selection_seed,"method":"one seeded random development base per family; original order only",
                             "outcomes_used":False,"base_ids":sorted(bases)},
                "primary_diagnostic_endpoints":["completion-cap hit rate","nonempty final-answer rate","format-valid final-answer rate"],
                "secondary_descriptive_endpoints":["rule success","whole-game success","successful steps"],
                "promotion_policy":"no automatic promotion or full-success target; main protocol requires an explicit user decision",
                "files":{name:hashlib.sha256(text.encode()).hexdigest() for name,text in contents.items()},
                "validation":validation}
    contents["manifest.json"] = json.dumps(manifest,indent=2,sort_keys=True)+"\n"
    output.mkdir(parents=True,exist_ok=True)
    for name,text in contents.items():
        path = output/name
        if path.exists() and path.read_text() != text:
            raise ValueError("Diagnostic dataset differs; select a new output directory")
    for name,text in contents.items():
        if not (output/name).exists():
            (output/name).write_text(text)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,default=Path("data/sequential-v3"))
    parser.add_argument("--output",type=Path,default=Path("data/diagnostics/gemma12-sampling-v1"))
    args = parser.parse_args()
    manifest = prepare(args.source,args.output)
    print(json.dumps(manifest["selection"],indent=2))
