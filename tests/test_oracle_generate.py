from collections import Counter
from passgame.constraints import Rule
from passgame.generate import build, digest, validate_cases
from passgame.oracle import certify, distance, one_edits


def test_proposal_exact_sum_repair_and_matched_bound_example():
    count = Rule("count", "digit_count", 2)
    exact = Rule("sum", "digit_sum", 11)
    bound = Rule("sum", "digit_sum", 11, "le")
    new = Rule("new", "contains", "8")
    assert certify("A47x!", [count, exact], new, "A38x!")["d_full"] == 2
    assert certify("A29x!", [count, bound], new)["label"] == "independent"
    assert certify("A47x!", [count, bound], new, "A38x!")["label"] == "interfering"
    assert certify("A47x!", [count, bound], new)["label"] == "unknown"
    assert certify("A38x!", [count, exact], new)["label"] == "no_op"
    assert certify("A4x!", [count, exact], new)["reason"] == "incoming_state_not_fully_valid"


def test_neighborhood_exhaustiveness_and_distance():
    expected = {"a", "b", "bb", "aa", "aab", "bab", "abb", "aba"}
    actual = set(one_edits("ab", alphabet="ab", maximum=3))
    assert actual == expected
    assert all(distance("ab", x) == 1 for x in actual)
    assert distance("ab", "ba") == 2
    assert distance("", "abc") == 3


def test_generator_matches_rules_and_split_blocks():
    cases, episodes = build(dev_per_cell=1, test_per_cell=1)
    assert len(cases) == 24
    assert validate_cases(cases)["independent_checker_passed"]
    assert build(dev_per_cell=1, test_per_cell=1) == (cases, episodes)
    assert len({c["base_id"] for c in cases}) == len(cases)
    for case in cases:
        assert case["certificates"]["independent"]["d_new"] == case["certificates"]["interfering"]["d_new"] == 1
        assert len(case["states"]["independent"]) == len(case["states"]["interfering"])
    order_sets = {}
    for episode in episodes:
        if episode["track"] != "order":
            continue
        canonical = digest(sorted(episode["rules"], key=lambda r:r["id"]))
        if episode["final_set_id"] in order_sets:
            assert order_sets[episode["final_set_id"]] == (canonical, episode["initial"])
        order_sets[episode["final_set_id"]] = canonical, episode["initial"]
    assert all(n == 4 for n in Counter(e["final_set_id"] for e in episodes if e["track"] == "order").values())
