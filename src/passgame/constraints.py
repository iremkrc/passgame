"""Primary deterministic verifier and human-readable constraint language."""

from dataclasses import asdict, dataclass
import string

ALPHABET = string.ascii_letters + string.digits + "!_-()[]"
MAX_LENGTH = 32
DIGITS = frozenset(string.digits)


def in_domain(value: object) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= MAX_LENGTH and all(c in ALPHABET for c in value)


@dataclass(frozen=True)
class Rule:
    id: str
    kind: str
    value: str | int
    op: str = "eq"
    position: int | None = None
    count: int | None = None

    def __post_init__(self):
        kinds = {"length", "digit_count", "digit_sum", "char_count", "contains", "forbids", "substring_count", "char_at", "balanced"}
        if not isinstance(self.id, str) or not self.id or self.kind not in kinds or self.op not in {"eq", "le", "ge"}:
            raise ValueError("Unsupported rule kind or operator")
        if self.kind in {"length", "digit_count", "digit_sum"}:
            if type(self.value) is not int or self.value < 0:
                raise ValueError("Numeric rule values must be nonnegative integers")
        if self.kind == "char_count":
            if not isinstance(self.value, str) or len(self.value) != 1 or self.value not in ALPHABET or type(self.count) is not int or self.count < 0:
                raise ValueError("Character count requires one character and a nonnegative count")
        if self.kind == "char_at" and (not isinstance(self.value, str) or len(self.value) != 1 or self.value not in ALPHABET or type(self.position) is not int or self.position < 1):
            raise ValueError("Positions are positive one-based integers")
        if self.kind in {"contains", "forbids"} and (not isinstance(self.value, str) or not self.value or any(c not in ALPHABET for c in self.value)):
            raise ValueError("Patterns must be nonempty domain strings")
        if self.kind == "substring_count" and (not isinstance(self.value, str) or not self.value or any(c not in ALPHABET for c in self.value) or type(self.count) is not int or self.count < 0):
            raise ValueError("Substring count requires a nonempty pattern and a nonnegative count")
        if self.kind in {"contains", "forbids", "char_at", "balanced"} and self.op != "eq":
            raise ValueError("This rule kind does not use a numeric comparison")
        if self.kind == "balanced" and self.value not in {"()", "[]", "()[]"}:
            raise ValueError("Unsupported bracket vocabulary")

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)

    def to_dict(self):
        return asdict(self)

    def check(self, text: str) -> bool:
        if self.kind == "length":
            return compare(len(text), self.op, self.value)
        if self.kind == "digit_count":
            return compare(sum(c in DIGITS for c in text), self.op, self.value)
        if self.kind == "digit_sum":
            return compare(sum(int(c) for c in text if c in DIGITS), self.op, self.value)
        if self.kind == "char_count":
            return compare(text.count(self.value), self.op, self.count)
        if self.kind == "substring_count":
            return compare(pattern_count(text, self.value), self.op, self.count)
        if self.kind == "contains":
            return self.value in text
        if self.kind == "forbids":
            return self.value not in text
        if self.kind == "char_at":
            return self.position <= len(text) and text[self.position - 1] == self.value
        if self.kind == "balanced":
            stack = []
            closes = {b: a for a, b in [tuple(pair) for pair in ("()", "[]") if pair in self.value]}
            for c in text:
                if c in closes.values():
                    stack.append(c)
                elif c in closes:
                    if not stack or stack.pop() != closes[c]:
                        return False
            return not stack
        raise AssertionError(self.kind)

    def describe(self) -> str:
        relation = {"eq": "exactly", "le": "at most", "ge": "at least"}[self.op]
        if self.kind == "length":
            return f"Length must be {relation} {self.value} characters."
        if self.kind == "digit_count":
            return f"There must be {relation} {self.value} ASCII digits."
        if self.kind == "digit_sum":
            return f"The sum of all digit occurrences must be {relation} {self.value}."
        if self.kind == "char_count":
            return f"Character {self.value!r} must occur {relation} {self.count} times."
        if self.kind == "substring_count":
            return f"Substring {self.value!r} must occur {relation} {self.count} times, counting overlapping occurrences."
        if self.kind == "contains":
            return f"The string must contain the case-sensitive substring {self.value!r}."
        if self.kind == "forbids":
            return f"The string must not contain the case-sensitive substring {self.value!r}."
        if self.kind == "char_at":
            return f"Character at one-based position {self.position} must be {self.value!r}."
        return f"Brackets from {self.value!r} must be correctly nested and balanced; other characters are ignored."


def compare(actual: int, op: str, expected: int) -> bool:
    return {"eq": actual == expected, "le": actual <= expected, "ge": actual >= expected}[op]


def pattern_count(text: str, pattern: str) -> int:
    """Count overlapping occurrences; empty patterns are undefined."""
    if not pattern:
        raise ValueError("Empty pattern")
    return sum(text.startswith(pattern, i) for i in range(len(text)))


def checks(text: str, rules: list[Rule]) -> dict[str, bool]:
    if len({r.id for r in rules}) != len(rules):
        raise ValueError("Rule IDs must be unique")
    return {r.id: r.check(text) for r in rules}


def satisfies(text: str, rules: list[Rule]) -> bool:
    return in_domain(text) and all(checks(text, rules).values())
