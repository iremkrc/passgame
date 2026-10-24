"""Version 3: eight-rule games with neutral starts and progressive repairs.

Reference paths prove satisfiability and demonstrate possible interference.
They are private validation data, never assistant messages in an LLM game.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import string

from .audit import reference_check, reference_domain
from .constraints import Rule
from .generate import digest
from .oracle import certify

FAMILIES = ("numeric", "position_count", "substring_position", "forbidden_position",
            "numeric_multi_2", "numeric_multi_3")
SEED = 20261024
SUITE = "progressive_seeded_v1"


def make_episode(rng: random.Random, family: str, split: str, index: int) -> dict:
    # Seeds contain no case-specific target letters or prepared repair state.
    a, x, y, z, b = rng.sample(string.ascii_uppercase, 5)
    if family == "numeric":
        if split == "development" and index == 0:
            left, right, target, x, y = 4, 7, 8, "X", "A"
        else:
            left, right, target = rng.choice([(u, v, q) for u in range(1, 9)
                for v in range(1, 10) for q in range(2, 10)
                if u != v and q not in (u, v) and 0 <= u+v-q <= 9
                and u+v-q != q and u+v != 3])
        repaired = left+right-target
        initial = "abc1"
        specs = [("digit_count", 2, {}), ("digit_sum", left+right, {}),
                 ("contains", str(target), {}), ("length", 6, {}), ("contains", "!", {}),
                 ("char_at", x, {"position":1}), ("char_at", y, {"position":2}),
                 ("char_at", str(target), {"position":4})]
        core = f"{repaired}{target}"
        outputs = ["abc12", f"abc{left}{right}", "abc"+core, "abc"+core+"_",
                   "abc"+core+"!", x+"bc"+core+"!", x+y+"c"+core+"!",
                   x+y+"c"+f"{target}{repaired}!" ]
        challenges = {3:1, 8:1}
    elif family == "position_count":
        initial = "abcd1"
        specs = [("char_count", a, {"count":2}), ("length", 6, {}),
                 ("char_at", x, {"position":1}), ("digit_count", 0, {}),
                 ("contains", "!", {}), ("char_at", y, {"position":3}),
                 ("contains", z, {}), ("char_at", z, {"position":2})]
        outputs = [a+a+"cd1", a+a+"cd1_", x+a+"cd1"+a, x+a+"cd_"+a,
                   x+a+"cd!"+a, x+a+y+"d!"+a, x+a+y+z+"!"+a, x+z+y+a+"!"+a]
        challenges = {3:1, 8:1}
    elif family == "substring_position":
        initial = "abcd1"
        specs = [("contains", a+a, {}), ("length", 6, {}),
                 ("char_at", x, {"position":1}), ("digit_count", 0, {}),
                 ("contains", "!", {}), ("char_at", y, {"position":4}),
                 ("contains", z, {}), ("char_at", z, {"position":5})]
        outputs = [a+a+"cd1", a+a+"cd1_", x+a+a+"d1_", x+a+a+"d__",
                   x+a+a+"d!_", x+a+a+y+"!_", x+a+a+y+"!"+z, x+a+a+y+z+"!"]
        challenges = {3:1, 8:1}
    elif family == "forbidden_position":
        initial = "abc1"
        specs = [("length", 6, {}), ("forbids", a+b, {}),
                 ("char_at", b, {"position":2}), ("digit_count", 0, {}),
                 ("contains", "!", {}), ("char_at", y, {"position":3}),
                 ("contains", z, {}), ("char_at", z, {"position":5})]
        outputs = [a+b+"cd1_", a+x+"cd1_", x+b+"cd1_", x+b+"cd__",
                   x+b+"cd!_", x+b+y+"d!_", x+b+y+z+"!_", x+b+y+z+z+"!"]
        challenges = {3:1, 8:1}
    elif family in {"numeric_multi_2", "numeric_multi_3"}:
        q = rng.randrange(3, 9)
        p = rng.randrange(1, q)
        h = rng.randrange(q+1, 10)
        d = rng.choice([v for v in range(h) if v not in (p, q)])
        initial = "abc1"
        if family == "numeric_multi_2":
            specs = [("digit_count", 3, {}), ("digit_sum", d+h+p, {"op":"le"}),
                     ("char_count", str(p), {"count":1}), ("char_at", str(q), {"position":6}),
                     ("length", 7, {}), ("contains", "!", {}),
                     ("char_at", x, {"position":1}), ("char_at", str(p), {"position":4})]
            outputs = [f"abc{h}{h}{p}", f"abc{d}{h}0", f"abc{d}{h}{p}",
                       f"abc{d}{p}{q}", f"abc{d}{p}{q}_", f"abc{d}{p}{q}!",
                       f"{x}bc{d}{p}{q}!", f"{x}bc{p}0{q}!"]
            challenges = {4:2, 8:1}
        else:
            specs = [("digit_count", 4, {}), ("digit_sum", d+2*h+p, {"op":"le"}),
                     ("char_count", str(p), {"count":1}), ("contains", f"{h}{p}", {}),
                     ("char_at", str(q), {"position":7}), ("length", 8, {}),
                     ("contains", "!", {}), ("char_at", x, {"position":1})]
            outputs = [f"abc{h}{h}{h}{p}", f"abc{d}{h}{h}0", f"abc{d}{h}0{p}",
                       f"abc{d}{h}{h}{p}", f"abc{d}{h}{p}{q}", f"abc{d}{h}{p}{q}_",
                       f"abc{d}{h}{p}{q}!", f"{x}bc{d}{h}{p}{q}!"]
            challenges = {5:3}
    else:
        raise ValueError(f"Unknown sequential family: {family}")
    rules = [Rule(f"r{i}", kind, value, **options) for i, (kind, value, options) in enumerate(specs, 1)]
    certificates = {str(t):certify(outputs[t-2], rules[:t-1], rules[t-1], outputs[t-1]) for t in challenges}
    if family == "numeric_multi_2":
        # The later relocation may break the sum bound as well as multiplicity.
        challenges[8] = certificates["8"]["min_old_rules_broken"]
    base = f"v3-{split}-{family}-{index:03d}"
    return {"episode_id":"seeded-"+base, "base_id":base, "final_set_id":digest([r.to_dict() for r in rules])[:20],
            "family":family, "split":split, "track":"seeded", "order":"original", "suite":SUITE,
            "initial":initial, "rules":[r.to_dict() for r in rules], "witness":outputs[-1],
            "reference_outputs":outputs, "reference_challenges":{str(t):degree for t,degree in challenges.items()},
            "reference_certificates":certificates}


def validate_episodes(episodes: list[dict]) -> dict:
    ids, base_splits, final_splits, originals = set(), {}, {}, {}
    counts, challenges = Counter(), Counter()
    for episode in episodes:
        if episode["episode_id"] in ids:
            raise ValueError("Duplicate episode ID")
        ids.add(episode["episode_id"])
        if episode.get("suite") != SUITE or episode["track"] not in {"seeded", "order"}:
            raise ValueError("Unknown version-3 episode suite or track")
        rules = [Rule.from_dict(r) for r in episode["rules"]]
        if len(rules) != 8 or len({r.id for r in rules}) != 8:
            raise ValueError("Sequential games need eight distinct rule IDs")
        canonical = sorted(episode["rules"], key=lambda r:r["id"])
        fingerprint = digest(canonical)
        if episode["final_set_id"] != fingerprint[:20]:
            raise ValueError("Final rule-set hash mismatch")
        for key, mapping in ((episode["base_id"], base_splits), (fingerprint, final_splits)):
            if mapping.setdefault(key, episode["split"]) != episode["split"]:
                raise ValueError("Scenario leakage across development and test")
        predicates = [digest({k:v for k,v in r.items() if k != "id"}) for r in canonical]
        if len(set(predicates)) != 8:
            raise ValueError("Duplicate predicates in a sequential game")
        if not reference_domain(episode["initial"]) or not reference_domain(episode["witness"]):
            raise ValueError("Invalid initial string or final witness")
        if not all(reference_check(episode["witness"], r.to_dict()) for r in rules):
            raise ValueError("Final witness does not prove prefix satisfiability")
        if episode["track"] == "seeded":
            if fingerprint in originals:
                raise ValueError("Duplicate seeded rule set")
            originals[fingerprint] = episode
            if rules[0].check(episode["initial"]):
                raise ValueError("The first rule must require a repair from the seed")
            outputs = episode.get("reference_outputs", [])
            planned = episode.get("reference_challenges", {})
            if (len(outputs) != 8 or not planned or min(map(int, planned)) > 5
                    or not set(planned) <= {str(t) for t in range(2,9)}
                    or any(type(degree) is not int or not 1 <= degree <= 3 for degree in planned.values())
                    or set(episode.get("reference_certificates", {})) != set(planned)):
                raise ValueError("Missing progressive reference path or early challenge")
            current = episode["initial"]
            for turn, (new, output) in enumerate(zip(rules, outputs), 1):
                if not reference_domain(output) or not all(reference_check(output, r.to_dict()) for r in rules[:turn]):
                    raise ValueError("Reference output violates active rules")
                if reference_check(current, new.to_dict()):
                    raise ValueError("Reference path must introduce a repair at every turn")
                if str(turn) in planned:
                    certificate = certify(current, rules[:turn-1], new, output)
                    if (certificate != episode["reference_certificates"].get(str(turn))
                            or certificate["label"] != "interfering"
                            or certificate["min_old_rules_broken"] != planned[str(turn)]):
                        raise ValueError("Reference interference certificate mismatch")
                    challenges[f"{episode['split']}/turn_{turn}/degree_{planned[str(turn)]}"] += 1
                current = output
            if current != episode["witness"]:
                raise ValueError("Final witness differs from reference endpoint")
        counts[f"{episode['split']}/{episode['track']}/{episode['family']}"] += 1
    # Order variants must actually describe permutations of the same original game.
    for episode in episodes:
        if episode["track"] == "order":
            original = originals.get(digest(sorted(episode["rules"], key=lambda r:r["id"])))
            if original is None or (episode["initial"], episode["base_id"], episode["family"]) != (original["initial"], original["base_id"], original["family"]):
                raise ValueError("Order variant does not match its original game")
    return {"episodes":len(episodes), "independent_checker_passed":True,
            "progressive_reference_paths_passed":True, "neutral_initials_passed":True,
            "counts":dict(sorted(counts.items())), "reference_challenges":dict(sorted(challenges.items()))}


def build(seed: int = SEED, dev_per_family: int = 4, test_per_family: int = 20) -> list[dict]:
    if min(dev_per_family, test_per_family) < 1:
        raise ValueError("Both splits need at least one game per family")
    rng, episodes, seen = random.Random(seed), [], set()
    for split, count in (("development", dev_per_family), ("test", test_per_family)):
        for family in FAMILIES:
            for index in range(count):
                for _ in range(1000):
                    episode = make_episode(rng, family, split, index)
                    if episode["final_set_id"] not in seen:
                        break
                else:
                    raise ValueError("Could not generate a distinct rule set")
                seen.add(episode["final_set_id"])
                episodes.append(episode)
    ordered = []
    for original in episodes:
        permutations = [list(range(8)), list(reversed(range(8)))]
        order_rng = random.Random(seed+int(digest(original["base_id"])[:8],16))
        while len(permutations) < 4:
            perm = order_rng.sample(range(8),8)
            if perm not in permutations:
                permutations.append(perm)
        for label, perm in zip(("original", "reverse", "random_1", "random_2"), permutations):
            ordered.append({k:v for k,v in original.items() if not k.startswith("reference_")} | {
                "track":"order", "order":label, "episode_id":"order-"+original["base_id"]+"-"+label,
                "rules":[original["rules"][i] for i in perm]})
    return episodes+ordered


def readable_reference(episodes: list[dict], split: str = "development") -> str:
    selected = [e for e in episodes if e["split"] == split and e["track"] == "seeded"]
    lines = [f"PassGame v3: {len(selected)} individual {split} games", "",
             "Each game has a neutral starting string and eight ordered rules.",
             "Reference outputs below are private validation examples, NOT model answers or LLM prompts.",
             "Reference challenge labels apply only to these example inputs; real model inputs are recertified.", ""]
    for number, episode in enumerate(selected,1):
        lines.extend([f"GAME {number} OF {len(selected)}: {episode['episode_id']}",
                      f"Family: {episode['family']}", f"Starting string: {episode['initial']}"])
        for turn, (data, output) in enumerate(zip(episode["rules"], episode["reference_outputs"]),1):
            lines.append(f"  Turn {turn}: {Rule.from_dict(data).describe()}")
            lines.append(f"    Example valid output: {output}")
            if str(turn) in episode["reference_challenges"]:
                lines.append(f"    Certified example interference degree: {episode['reference_challenges'][str(turn)]}")
        lines.extend(["", "-"*72, ""])
    return "\n".join(lines)+"\n"


def write_dataset(output: Path, seed: int = SEED, dev_per_family: int = 4, test_per_family: int = 20):
    manifest_path = output/"manifest.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text()).get("version") != 3:
        raise ValueError("Use a new directory; historical datasets must remain unchanged")
    episodes = build(seed,dev_per_family,test_per_family)
    validation = validate_episodes(episodes)
    output.mkdir(parents=True,exist_ok=True)
    audit = [e for e in episodes if e["track"] == "seeded" and e["split"] == "test"]
    audit = [e for family in FAMILIES for e in [x for x in audit if x["family"] == family][:2]]
    for name, rows in (("episodes.jsonl",episodes),("audit-sample.jsonl",audit)):
        (output/name).write_text("".join(json.dumps(r,sort_keys=True)+"\n" for r in rows))
    (output/"development-games.txt").write_text(readable_reference(episodes))
    files = ("episodes.jsonl","audit-sample.jsonl","development-games.txt")
    manifest = {"version":3, "suite":SUITE, "seed":seed, "human_audit_status":"pending",
                "domain":"ASCII letters, digits and !_-()[]; length 1-32",
                "split_policy":"distinct final rule sets across splits; order variants stay in their split",
                "llm_protocol":"neutral initial once; actual successful outputs; reminders; stop on first failure",
                "reference_paths":"private satisfiability proofs, not scripted LLM prefixes or required outputs",
                "validation":validation,
                "files":{name:hashlib.sha256((output/name).read_bytes()).hexdigest() for name in files}}
    manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=Path("data/sequential-v3"))
    parser.add_argument("--seed",type=int,default=SEED)
    args = parser.parse_args()
    print(json.dumps(write_dataset(args.output,args.seed),indent=2))
