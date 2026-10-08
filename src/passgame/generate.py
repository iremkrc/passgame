"""Deterministic, split-safe matched cases and full trajectory specifications."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import string

from .audit import reference_check, reference_domain
from .constraints import Rule, satisfies
from .oracle import certify, distance, one_edits

FAMILIES = ("numeric", "position_count", "substring_position", "forbidden_position")
LEVELS = (3, 5, 8)
MULTI_LEVELS = {"numeric_multi_2": (5, 8), "numeric_multi_3": (6, 8)}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def make_pair(rng: random.Random, family: str, load: int, split: str, index: int) -> dict:
    prefix = "".join(rng.choices(string.ascii_lowercase, k=rng.randint(2, 5)))
    suffix = "".join(rng.choices(string.ascii_lowercase, k=3))
    if family == "numeric":
        choices = [(a, b, q, v) for q in range(3, 9) for a in range(q) for b in range(q) for v in range(q + 1, 10) if q <= a + b and 0 <= a + b - v <= 9]
        a, b, q, v = rng.choice(choices)
        total = a + b
        cores = {"independent": f"{total-v}{v}", "interfering": f"{a}{b}"}
        full = f"{total-q}{q}"
        old = [Rule("r1", "digit_count", 2), Rule("r2", "digit_sum", total, "le")]
        new = Rule("new", "contains", str(q))
    else:
        a, b, c, d, e = rng.sample(string.ascii_uppercase[:-1], 5)
        if family == "position_count":
            cores = {"independent": a+a+c+d+e, "interfering": a+c+a+d+e}
            full = a+a+b+d+e
            old = [Rule("r1", "char_count", a, count=2)]
        elif family == "substring_position":
            cores = {"independent": a+b+a+d, "interfering": a+a+b+d}
            full = a+b+c+d
            old = [Rule("r1", "contains", a+b)]
            b = c
        else:
            cores = {"independent": a+c+d+e, "interfering": c+a+d+e}
            full = c+c+b+e
            old = [Rule("r1", "forbids", a+b)]
        length = len(prefix + cores["independent"] + "!" + suffix)
        old.append(Rule("r2", "length", length))
        new = Rule("new", "char_at", b, position=len(prefix)+3)
    states = {condition: prefix+core+"!"+suffix for condition, core in cores.items()}
    witness = prefix+full+"!"+suffix
    extras = [
        Rule("r3", "length", len(witness)) if family == "numeric" else Rule("r3", "digit_count", 0),
        Rule("r4", "contains", "!"),
        Rule("r5", "char_at", prefix[0], position=1),
        Rule("r6", "forbids", "Z"),
        Rule("r7", "contains", suffix),
    ]
    all_old = old + extras
    active_old = all_old[:load-1]
    pair_id = f"{split}-{family}-{load}-{index:03d}"
    case = {"pair_id": pair_id, "base_id": pair_id, "split": split, "family": family, "load": load,
            "old_rules": [r.to_dict() for r in active_old], "all_old_rules": [r.to_dict() for r in all_old],
            "new_rule": new.to_dict(), "states": states, "final_witness": witness,
            "interference_degree": 1,
            "controlled_initials": states.copy(), "prefix_policy": "unchanged_valid_oracle_artifact"}
    case["certificates"] = {condition: certify(s, active_old, new, witness) for condition, s in states.items()}
    for condition in states:
        if case["certificates"][condition]["label"] != condition:
            raise AssertionError(f"Invalid generated label: {pair_id} {condition}")
    case["final_set_id"] = digest(case["old_rules"] + [case["new_rule"]])[:20]
    return case


def make_multi_pair(rng: random.Random, family: str, load: int, split: str, index: int) -> dict:
    """Distinct digit, sum, multiplicity and adjacency constraints; no copied rules."""
    if family not in MULTI_LEVELS or load not in MULTI_LEVELS[family]:
        raise ValueError("Unsupported multi-rule family/load")
    degree = 2 if family == "numeric_multi_2" else 3
    prefix = "".join(rng.choices(string.ascii_lowercase, k=rng.randint(2, 5)))
    suffix = "".join(rng.choices(string.ascii_lowercase, k=3))
    q = rng.randrange(3, 9)
    p = rng.randrange(q)
    h = rng.randrange(q + 1, 10)
    d = rng.choice([v for v in range(10) if v not in (p, q, h)])
    if degree == 2:
        cores = {"independent": f"{p}{d}{h}", "interfering": f"{d}{h}{p}"}
        full = f"{d}{p}{q}"
    else:
        cores = {"independent": f"{h}{p}{d}{h}", "interfering": f"{d}{h}{h}{p}"}
        full = f"{d}{h}{p}{q}"
    states = {condition: prefix+core+"!"+suffix for condition, core in cores.items()}
    witness = prefix+full+"!"+suffix
    core = cores["interfering"]
    old = [Rule("r1", "digit_count", len(core)),
           Rule("r2", "digit_sum", sum(map(int, core)), "le"),
           Rule("r3", "char_count", str(p), count=1),
           Rule("r4", "length", len(witness))]
    if degree == 3:
        old.append(Rule("r5", "contains", f"{h}{p}"))
    extras = [("contains", "!", None), ("char_at", prefix[0], 1), ("contains", suffix, None)]
    for kind, value, position in extras[:7-len(old)]:
        old.append(Rule(f"r{len(old)+1}", kind, value, position=position))
    active = old[:load-1]
    new = Rule("new", "char_at", str(q), position=len(prefix)+len(core))
    pair_id = f"{split}-{family}-{load}-{index:03d}"
    case = {"pair_id": pair_id, "base_id": pair_id, "split": split, "family": family, "load": load,
            "interference_degree": degree, "old_rules": [r.to_dict() for r in active],
            "all_old_rules": [r.to_dict() for r in old], "new_rule": new.to_dict(),
            "states": states, "final_witness": witness, "controlled_initials": states.copy(),
            "prefix_policy": "unchanged_valid_oracle_artifact"}
    case["certificates"] = {condition: certify(state, active, new, witness) for condition, state in states.items()}
    for condition, certificate in case["certificates"].items():
        expected = 0 if condition == "independent" else degree
        if certificate["label"] != condition or certificate["min_old_rules_broken"] != expected:
            raise AssertionError(f"Invalid multi-rule certificate: {pair_id} {condition}")
    case["final_set_id"] = digest(case["old_rules"]+[case["new_rule"]])[:20]
    return case


def validate_cases(cases: list[dict]) -> dict:
    ids, content = set(), set()
    counts, degrees = Counter(), Counter()
    for case in cases:
        if case["pair_id"] in ids:
            raise AssertionError("Duplicate pair ID")
        ids.add(case["pair_id"])
        fingerprint = digest({k: case[k] for k in ("old_rules", "new_rule", "states")})
        if fingerprint in content:
            raise AssertionError("Duplicate base scenario across splits")
        content.add(fingerprint)
        old = [Rule.from_dict(r) for r in case["old_rules"]]
        if len({digest({k:v for k,v in r.to_dict().items() if k != "id"}) for r in old}) != len(old):
            raise AssertionError("Repeated equivalent rule cannot inflate interference degree")
        new = Rule.from_dict(case["new_rule"])
        full = [Rule.from_dict(r) for r in case["all_old_rules"]] + [new]
        witness = case["final_witness"]
        if not reference_domain(witness) or not all(reference_check(witness, r.to_dict()) for r in full):
            raise AssertionError("Independent witness audit failed")
        for condition, state in case["states"].items():
            if not satisfies(state, old) or new.check(state):
                raise AssertionError("Focal input must be old-valid and new-invalid")
            if not reference_domain(state) or not all(reference_check(state, r.to_dict()) for r in old):
                raise AssertionError("Independent input audit failed")
            certificate = certify(state, old, new, witness)
            if certificate != case["certificates"][condition]:
                raise AssertionError("Certificate mismatch")
            if distance(state, certificate["witness"]) != certificate["d_full"]:
                raise AssertionError("Witness distance mismatch")
            # Audit the complete radius-one new-valid neighborhood using the independent checker.
            ref_broken = [[r.id for r in old if not reference_check(candidate, r.to_dict())]
                          for candidate in one_edits(state) if reference_check(candidate, new.to_dict())]
            histogram = dict(sorted(Counter(str(len(ids)) for ids in ref_broken).items()))
            if histogram != certificate["old_rules_broken_histogram"]:
                raise AssertionError("Independent multi-rule neighborhood audit failed")
            expected = 0 if condition == "independent" else case["interference_degree"]
            if certificate["min_old_rules_broken"] != expected:
                raise AssertionError("Interference degree differs from certified minimum")
            counts[f"{case['split']}/{case['family']}/{case['load']}/{condition}"] += 1
        degrees[f"{case['split']}/{case['interference_degree']}"] += 1
    return {"pairs": len(cases), "states": 2*len(cases), "independent_checker_passed": True,
            "multi_rule_neighborhood_audit_passed": True, "interference_degree_counts": dict(sorted(degrees.items())),
            "counts": dict(sorted(counts.items()))}


def build(seed: int = 20261008, dev_per_cell: int = 2, test_per_cell: int = 10) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    cases = [make_pair(rng, family, load, split, i) for split, n in (("development", dev_per_cell), ("test", test_per_cell)) for family in FAMILIES for load in LEVELS for i in range(n)]
    # Separate stream preserves the original cases' rules and incoming states.
    multi_rng = random.Random(seed+1)
    cases.extend(make_multi_pair(multi_rng, family, load, split, i)
                 for split, n in (("development", dev_per_cell), ("test", test_per_cell))
                 for family, levels in MULTI_LEVELS.items() for load in levels for i in range(n))
    validate_cases(cases)
    episodes = []
    for split in ("development", "test"):
        eligible = [c for c in cases if c["split"] == split and c["load"] == 8]
        # Interleave families so subset selection remains approximately balanced.
        eligible.sort(key=lambda c: (int(c["pair_id"].rsplit("-", 1)[1]), c["family"]))
        native = eligible[:30 if split == "test" else 6]
        for case in native:
            final = case["all_old_rules"] + [case["new_rule"]]
            for variant, initial in enumerate(("seed0!", "seed9!")):
                episodes.append({"episode_id": f"native-{case['pair_id']}-{variant}", "base_id": case["base_id"], "final_set_id": digest(final)[:20], "family": case["family"], "split": split, "track": "native", "order": "original", "initial": initial, "rules": final, "witness": case["final_witness"]})
        for case in eligible[:20 if split == "test" else 6]:
            final = case["all_old_rules"] + [case["new_rule"]]
            permutations = [list(range(8)), list(reversed(range(8)))]
            order_rng = random.Random(seed + int(digest(case["base_id"])[:8], 16))
            while len(permutations) < 4:
                perm = order_rng.sample(range(8), 8)
                if perm not in permutations:
                    permutations.append(perm)
            for label, perm in zip(("original", "reverse", "random_1", "random_2"), permutations):
                episodes.append({"episode_id": f"order-{case['pair_id']}-{label}", "base_id": case["base_id"], "final_set_id": digest(final)[:20], "family": case["family"], "split": split, "track": "order", "order": label, "initial": "seed0!", "rules": [final[i] for i in perm], "witness": case["final_witness"]})
    return cases, episodes


def write_dataset(output: Path, seed: int = 20261008):
    cases, episodes = build(seed)
    output.mkdir(parents=True, exist_ok=True)
    for name, records in (("pairs.jsonl", cases), ("episodes.jsonl", episodes)):
        (output/name).write_text("".join(json.dumps(r, sort_keys=True)+"\n" for r in records))
    audit = sorted((c for c in cases if c["split"] == "test"), key=lambda c: (int(c["pair_id"].rsplit("-",1)[1]), c["family"], c["load"]))[:20]
    (output/"audit-sample.jsonl").write_text("".join(json.dumps(c, sort_keys=True)+"\n" for c in audit))
    manifest = {"version": 2, "seed": seed, "domain": "ASCII letters, digits and !_-()[]; length 1-32", "split_policy": "base scenario disjoint; variants stay in one split", "prefix_policy": "scripted oracle prefixes are offline diagnostics only; LLM prefixes use the model's own responses", "llm_protocol": "one new rule per user turn; original conversation history; native/order only", "interference_degree_definition": "minimum number of old rules broken across all shortest new-only edits of the certified focal state", "human_audit_status": "pending", "validation": validate_cases(cases), "files": {name: hashlib.sha256((output/name).read_bytes()).hexdigest() for name in ("pairs.jsonl", "episodes.jsonl", "audit-sample.jsonl")}, "episode_counts": dict(Counter(f"{e['split']}/{e['track']}" for e in episodes))}
    (output/"manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True)+"\n")
    return manifest


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def verify_manifest(directory: Path):
    manifest = json.loads((directory/"manifest.json").read_text())
    for name, expected in manifest["files"].items():
        if hashlib.sha256((directory/name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Dataset hash mismatch: {name}")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data"))
    args = parser.parse_args()
    print(json.dumps(write_dataset(args.output), indent=2))
