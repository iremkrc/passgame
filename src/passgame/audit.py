"""Independent reference checker: intentionally no primary-checker calls."""

import re


def reference_check(text: str, data: dict) -> bool:
    kind, value, op, position = (data[k] for k in ("kind", "value", "op", "position"))
    if kind == "length":
        actual = len(list(text))
    elif kind == "digit_count":
        actual = len(re.findall(r"[0-9]", text))
    elif kind == "digit_sum":
        actual = sum(map(int, re.findall(r"[0-9]", text)))
    elif kind == "char_count":
        actual, value = len(re.findall(re.escape(value), text)), data["count"]
    elif kind == "substring_count":
        actual, value = len(re.findall(f"(?={re.escape(value)})", text)), data["count"]
    elif kind == "contains":
        return re.search(re.escape(value), text) is not None
    elif kind == "forbids":
        return re.search(re.escape(value), text) is None
    elif kind == "char_at":
        return len(text) >= position and text[position - 1:position] == value
    elif kind == "balanced":
        filtered = "".join(c for c in text if c in value)
        while True:
            reduced = filtered
            for pair in ("()", "[]"):
                if pair in value:
                    reduced = reduced.replace(pair, "")
            if reduced == filtered:
                return not filtered
            filtered = reduced
    else:
        raise ValueError(kind)
    if op == "eq":
        return actual == value
    if op == "le":
        return actual <= value
    if op == "ge":
        return actual >= value
    raise ValueError(op)


def reference_domain(text: str) -> bool:
    return re.fullmatch(r"[A-Za-z0-9!_()\[\]-]{1,32}", text) is not None
