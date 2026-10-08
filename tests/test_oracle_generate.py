from collections import Counter
from passgame.constraints import Rule
from passgame.generate import build, digest, validate_cases
from passgame.oracle import certify, distance, new_only, one_edits


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


def test_independence_does_not_guarantee_greedy_choice_is_safe():
    old = [Rule("count", "digit_count", 2), Rule("sum", "digit_sum", 11, "le")]
    new = Rule("new", "contains", "8")
    assert certify("A29x!", old, new)["label"] == "independent"
    greedy = new_only("A29x!", new)
    assert new.check(greedy) and distance("A29x!", greedy) == 1
    assert not all(r.check(greedy) for r in old)


def test_generator_matches_rules_and_split_blocks():
    cases, episodes = build(dev_per_cell=1, test_per_cell=1)
    assert len(cases) == 32
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


def test_two_and_three_rule_interference_includes_insertions():
    base = [Rule("digits", "digit_count", 3), Rule("sum", "digit_sum", 15, "le"),
            Rule("ones", "char_count", "1", count=1), Rule("length", "length", 3)]
    new = Rule("new", "char_at", "8", position=3)
    certificate = certify("591", base, new, "518")
    assert certificate["min_old_rules_broken"] == 2
    assert certificate["max_old_rules_broken"] == 3  # Inserting 8 also exceeds length/digit count.
    assert certificate["old_rules_broken_histogram"] == {"2": 1, "3": 1}
    assert certify("159", base, new)["min_old_rules_broken"] == 0
    old = [Rule("digits", "digit_count", 4), Rule("sum", "digit_sum", 24, "le"),
           Rule("ones", "char_count", "1", count=1), Rule("length", "length", 4),
           Rule("pattern", "contains", "91")]
    new = Rule("new", "char_at", "8", position=4)
    certificate = certify("5991", old, new, "5918")
    assert certificate["label"] == "interfering" and certificate["d_full"] == 2
    assert certificate["min_old_rules_broken"] == 3 and certificate["max_old_rules_broken"] == 4
    assert certificate["min_break_rule_ids"] == ["sum", "ones", "pattern"]
    assert certificate["necessarily_affected_old_rule_ids"] == ["pattern", "sum"]
    assert certify("9159", old, new)["min_old_rules_broken"] == 0
    # Each old constraint is necessary, even with the new rule binding.
    isolated_violations = {"digits": "91A8", "sum": "9198", "ones": "9118",
                           "length": "5918A", "pattern": "1958"}
    for rule_id, artifact in isolated_violations.items():
        assert new.check(artifact)
        assert [r.id for r in old if not r.check(artifact)] == [rule_id]


def test_generated_degree_certifies_every_shortest_repair():
    cases, _ = build(dev_per_cell=1, test_per_cell=1)
    for case in cases:
        old = [Rule.from_dict(r) for r in case["old_rules"]]
        new = Rule.from_dict(case["new_rule"])
        state = case["states"]["interfering"]
        counts = [sum(not r.check(candidate) for r in old)
                  for candidate in one_edits(state) if new.check(candidate)]
        assert min(counts) == case["interference_degree"]
        assert case["certificates"]["interfering"]["min_old_rules_broken"] == min(counts)
