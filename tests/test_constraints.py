import itertools
import pytest
from passgame.audit import reference_check, reference_domain
from passgame.constraints import Rule, in_domain, pattern_count


def test_independent_checker_exhaustive_small_domain():
    rules = [Rule("n", "length", 3, op="le"), Rule("d", "digit_count", 2),
             Rule("s", "digit_sum", 1, op="ge"), Rule("a", "char_count", "A", count=2),
             Rule("p", "contains", "AB"), Rule("f", "forbids", "AA"),
             Rule("t", "substring_count", "AA", count=2), Rule("x", "char_at", "B", position=2),
             Rule("b", "balanced", "()[]")]
    for length in range(5):
        for chars in itertools.product("01AB()[]", repeat=length):
            text = "".join(chars)
            assert in_domain(text) == reference_domain(text)
            for rule in rules:
                assert rule.check(text) == reference_check(text, rule.to_dict())


def test_exact_semantics_and_boundaries():
    assert not in_domain("é") and not in_domain("A\n")
    assert not in_domain("") and in_domain("A"*32) and not in_domain("A"*33)
    assert Rule("d", "digit_sum", 18).check("a99")
    assert not Rule("p", "char_at", "A", position=2).check("A")
    assert Rule("b", "balanced", "()[]").check("A([x])")
    assert not Rule("b", "balanced", "()[]").check("([)]")
    assert pattern_count("AAAA", "AA") == 3
    with pytest.raises(ValueError):
        Rule("p", "char_at", "A", position=0)
    with pytest.raises(ValueError):
        Rule("d", "digit_count", True)
    with pytest.raises(ValueError):
        Rule("f", "contains", "")
