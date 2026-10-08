"""Exact edit neighborhoods and completed minimal-distance certificates."""

from .constraints import ALPHABET, MAX_LENGTH, Rule, in_domain, satisfies


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


def certify(text: str, old: list[Rule], new: Rule, witness: str | None = None) -> dict:
    if not satisfies(text, old):
        return {"label": "unknown", "reason": "incoming_state_not_fully_valid"}
    if new.check(text):
        return {"label": "no_op", "d_new": 0, "d_full": 0, "witness": text}
    neighborhood = one_edits(text)
    new_candidates = [s for s in neighborhood if new.check(s)]
    full_candidates = [s for s in new_candidates if satisfies(s, old)]
    common = {"d_new": 1 if new_candidates else None, "one_edit_candidates": len(neighborhood), "one_edit_new_valid": len(new_candidates), "one_edit_full_valid": len(full_candidates), "search_complete": True}
    if full_candidates:
        return {**common, "label": "independent", "d_full": 1, "witness": full_candidates[0]}
    if new_candidates and witness is not None and satisfies(witness, old + [new]) and distance(text, witness) == 2:
        return {**common, "label": "interfering", "d_full": 2, "witness": witness}
    return {**common, "label": "unknown", "reason": "no_exact_upper_bound", "d_full": None}


def new_only(text: str, rule: Rule) -> str:
    if rule.check(text):
        return text
    for candidate in sorted(one_edits(text), key=lambda s: (len(s) != len(text), s)):
        if rule.check(candidate):
            return candidate
    return text  # The local baseline explicitly stops at radius one.
