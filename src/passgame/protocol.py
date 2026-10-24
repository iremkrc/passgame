"""Frozen prompts, strict parsing, retention scoring and artifact transitions."""

import json
import re
from .constraints import Rule, checks, in_domain
from .oracle import distance

SYSTEM = (
    "Update a persistent artificial string to satisfy every active rule. "
    "Earlier rules remain binding. You may rewrite any part of the string. "
    "Strings must have 1-32 characters drawn only from ASCII letters, ASCII digits, and !_-()[]. "
    "There is no whitespace in the string. Matching is case sensitive. "
    "Return exactly one JSON object with exactly one field named password whose value is the updated string. "
    "Do not include markdown or explanations."
)


def render(current: str, new: Rule, old: list[Rule] | None = None, *,
           remind_previous_rules: bool = False) -> str:
    """Introduce one rule, optionally repeating the exact previously active rules."""
    if not remind_previous_rules:
        return f"Current string: {json.dumps(current)}\nNew rule: {new.id}: {new.describe()}\nReturn the updated string as JSON."
    previous = "\n".join(f"{rule.id}: {rule.describe()}" for rule in (old or []))
    return (f"Current string: {json.dumps(current)}\nPrevious rules (still binding):\n"
            f"{previous or '(none; this is the first turn)'}\n\n"
            f"New rule: {new.id}: {new.describe()}\n"
            "Return the updated string satisfying all active rules as JSON.")


def controlled_messages(case: dict, condition: str) -> list[dict]:
    """Offline diagnostic fixture; never sent to an LLM (enforced in the runner)."""
    old = [Rule.from_dict(r) for r in case["old_rules"]]
    new = Rule.from_dict(case["new_rule"])
    current = case["states"][condition]
    messages = [{"role": "system", "content": SYSTEM}]
    for rule in old:
        messages.append({"role": "user", "content": render(current, rule)})
        messages.append({"role": "assistant", "content": json.dumps({"password": current})})
    messages.append({"role": "user", "content": render(current, new)})
    return messages


def fresh_messages(rules: list[Rule]) -> list[dict]:
    """Legacy offline diagnostic only; all-at-once prompts are forbidden for LLMs."""
    listing = "\n".join(f"{r.id}: {r.describe()}" for r in rules)
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Create a string satisfying these rules. No current artifact is supplied.\n{listing}"}]


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


_MARKDOWN_FENCE = re.compile(
    r'[ \t\r\n]*```(?:json)?[ \t]*\r?\n(.*?)\r?\n```[ \t\r\n]*',
    re.DOTALL | re.IGNORECASE,
)


def _unwrap_markdown_fence(raw: str, allowed: bool) -> tuple[str, bool]:
    match = _MARKDOWN_FENCE.fullmatch(raw) if allowed and isinstance(raw, str) else None
    return (match.group(1), True) if match else (raw, False)


def parse(raw: str, *, allow_markdown_fences: bool = False) -> tuple[str | None, str | None]:
    raw, _ = _unwrap_markdown_fence(raw, allow_markdown_fences)
    try:
        data = json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, TypeError):
        return None, "format_failure"
    if not isinstance(data, dict) or set(data) != {"password"} or not isinstance(data["password"], str):
        return None, "format_failure"
    if not in_domain(data["password"]):
        return None, "domain_failure"
    return data["password"], None


def score(current: str, raw: str, old: list[Rule], new: Rule, *,
          allow_markdown_fences: bool = False) -> dict:
    before = checks(current, old)
    retained_ids = [rid for rid, passed in before.items() if passed]
    artifact, strict_error = parse(raw)
    normalized, fence_removed = _unwrap_markdown_fence(raw, allow_markdown_fences)
    artifact, error = parse(normalized) if fence_removed else (artifact, strict_error)
    after = checks(artifact, old+[new]) if artifact is not None else None
    full = int(after is not None and all(after.values()))
    new_success = int(after is not None and after[new.id])
    all_old = int(after is not None and all(after[r.id] for r in old)) if old else None
    retention = int(after is not None and all(after[rid] for rid in retained_ids)) if retained_ids else None
    fractional = sum(after[rid] for rid in retained_ids)/len(retained_ids) if after is not None and retained_ids else (0.0 if retained_ids else None)
    broken = [rid for rid in retained_ids if not after[rid]] if after is not None else None
    if error:
        outcome = error
    elif full:
        outcome = "full_success"
    elif new_success:
        outcome = "new_success_old_failure"
    elif all_old:
        outcome = "new_failure_old_retained"
    else:
        outcome = "new_and_old_failure"
    return {"artifact": artifact, "parse_error": error, "strict_parse_error": strict_error,
            "markdown_fence_removed": fence_removed, "full_success": full, "new_success": new_success,
            "all_old_success": all_old, "retention": retention, "fractional_retention": fractional,
            "retention_eligible": bool(retained_ids), "previously_satisfied": retained_ids,
            "newly_violated_old_rule_ids": broken, "old_rules_broken": len(broken) if broken is not None else None,
            "before_checks": before, "after_checks": after, "outcome": outcome,
            "new_was_noop": new.check(current), "edit_distance": distance(current, artifact) if artifact is not None else None,
            "next_state": artifact if artifact is not None else current}
