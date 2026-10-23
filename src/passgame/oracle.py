"""Exact edit neighborhoods and completed minimal-distance certificates."""

from itertools import chain

from .constraints import ALPHABET, MAX_LENGTH, Rule, in_domain, satisfies

MAX_WITNESS_CANDIDATES = 100_000


def distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def one_edits(text: str, alphabet: str = ALPHABET, maximum: int = MAX_LENGTH) -> list[str]:
    candidates = set()
    for i in range(len(text)):
        if len(text) > 1:
            candidates.add(text[:i] + text[i + 1:])
        for c in alphabet:
            if c != text[i]:
                candidates.add(text[:i] + c + text[i + 1:])
    if len(text) < maximum:
        for i in range(len(text) + 1):
            for c in alphabet:
                candidates.add(text[:i] + c + text[i:])
    return sorted(candidates)


def _adaptive_witness(text, old, new, neighborhood, new_candidates, limit):
    """Look for a two-edit witness from this state, with bounded deterministic work.

    Try repairs of new-valid neighbors first, then all other intermediates:
    a valid two-edit solution need not satisfy the new rule after its first edit.
    Only distinct radius-two candidates count toward the limit.
    """
    seen = set(neighborhood)
    seen.add(text)
    preferred = set(new_candidates)
    intermediates = chain(new_candidates, (s for s in neighborhood if s not in preferred))
    examined = 0
    rules = [new] + old
    for intermediate in intermediates:
        for candidate in one_edits(intermediate):
            if candidate in seen:
                continue
            if examined >= limit:
                return None, {"witness_search_candidates": examined, "witness_search_status": "candidate_limit"}
            seen.add(candidate)
            examined += 1
            if all(rule.check(candidate) for rule in rules):
                return candidate, {"witness_search_candidates": examined, "witness_search_status": "found"}
    return None, {"witness_search_candidates": examined, "witness_search_status": "exhausted"}


def certify(text: str, old: list[Rule], new: Rule, witness: str | None = None,
            *, witness_search_limit: int = MAX_WITNESS_CANDIDATES) -> dict:
    """Certify this incoming state; an optional stored witness is only a hint."""
    if type(witness_search_limit) is not int or witness_search_limit < 0:
        raise ValueError("Witness search limit must be a nonnegative integer")
    if not satisfies(text, old):
        return {"label": "unknown", "reason": "incoming_state_not_fully_valid"}
    if new.check(text):
        return {"label": "no_op", "d_new": 0, "d_full": 0, "witness": text, **breakage_profile([text], old)}
    neighborhood = one_edits(text)
    new_candidates = [s for s in neighborhood if new.check(s)]
    full_candidates = [s for s in new_candidates if satisfies(s, old)]
    common = {"d_new": 1 if new_candidates else None, "one_edit_candidates": len(neighborhood), "one_edit_new_valid": len(new_candidates), "one_edit_full_valid": len(full_candidates), "search_complete": True,
              **breakage_profile(new_candidates, old)}
    if full_candidates:
        return {**common, "label": "independent", "d_full": 1, "witness": full_candidates[0]}
    if new_candidates and witness is not None and satisfies(witness, old + [new]) and distance(text, witness) == 2:
        return {**common, "label": "interfering", "d_full": 2, "witness": witness}
    if new_candidates:
        adaptive, search = _adaptive_witness(text, old, new, neighborhood, new_candidates, witness_search_limit)
        common.update(search)
        if adaptive is not None:
            return {**common, "label": "interfering", "d_full": 2, "witness": adaptive}
    return {**common, "label": "unknown", "reason": "no_exact_upper_bound", "d_full": None}


def breakage_profile(candidates: list[str], old: list[Rule]) -> dict:
    """Count broken old rules over every shortest new-only repair, not one choice."""
    from collections import Counter
    broken = [(s, [r.id for r in old if not r.check(s)]) for s in candidates]
    if not broken:
        return {"min_old_rules_broken": None, "max_old_rules_broken": None,
                "old_rules_broken_histogram": {}, "possibly_affected_old_rule_ids": [],
                "necessarily_affected_old_rule_ids": [], "min_break_witness": None, "min_break_rule_ids": []}
    smallest = min(broken, key=lambda item: (len(item[1]), item[0]))
    sets = [set(ids) for _, ids in broken]
    return {"min_old_rules_broken": len(smallest[1]), "max_old_rules_broken": max(map(len, sets)),
            "old_rules_broken_histogram": dict(sorted(Counter(str(len(ids)) for ids in sets).items())),
            "possibly_affected_old_rule_ids": sorted(set.union(*sets)),
            "necessarily_affected_old_rule_ids": sorted(set.intersection(*sets)),
            "min_break_witness": smallest[0], "min_break_rule_ids": smallest[1]}


def new_only(text: str, rule: Rule) -> str:
    if rule.check(text):
        return text
    for candidate in sorted(one_edits(text), key=lambda s: (len(s) != len(text), s)):
        if rule.check(candidate):
            return candidate
    return text  # The local baseline explicitly stops at radius one.
