import json
import pytest
from passgame.constraints import Rule
from passgame.protocol import parse, render, score


@pytest.mark.parametrize("raw", ['```json\n{"password":"A"}\n```', '{"password":"A","extra":1}', '{"password":1}', '["A"]', '{"password":"A","password":"B"}', 'answer: A'])
def test_parser_rejects_invalid_formats(raw):
    assert parse(raw) == (None, "format_failure")


def test_parser_domain_and_literal_whitespace():
    assert parse('{"password":" A"}') == (None, "domain_failure")
    assert parse('{"password":"\\u0041"}') == ("A", None)
    assert parse(' {"password":"A"} \n') == ("A", None)


def test_retention_only_tracks_incoming_satisfied_rules():
    old = [Rule("count", "digit_count", 2), Rule("sum", "digit_sum", 11)]
    new = Rule("new", "contains", "8")
    regression = score("A47x!", json.dumps({"password":"A48x!"}), old, new)
    assert regression["new_success"] == 1 and regression["retention"] == 0 and regression["full_success"] == 0
    assert regression["outcome"] == "new_success_old_failure"
    inherited = score("A4x!", '{"password":"A8x!"}', old, new)
    assert inherited["retention"] is None and inherited["all_old_success"] == 0
    assert inherited["previously_satisfied"] == []


def test_invalid_artifact_does_not_replace_state_or_get_retention_credit():
    old, new = [Rule("d", "digit_count", 2)], Rule("n", "contains", "8")
    for raw in ("invalid", '{"password":"A 38x!"}'):
        result = score("A47x!", raw, old, new)
        assert result["next_state"] == "A47x!"
        assert result["full_success"] == result["new_success"] == result["retention"] == 0
        assert result["after_checks"] is None
        assert result["old_rules_broken"] is None


def test_single_rule_disclosure_and_multiple_old_rule_regressions():
    old = [Rule("digits", "digit_count", 4), Rule("sum", "digit_sum", 24, "le"),
           Rule("ones", "char_count", "1", count=1), Rule("length", "length", 4),
           Rule("pattern", "contains", "91")]
    new = Rule("new", "char_at", "8", position=4)
    prompt = render("5991", new)
    assert prompt.count("\nNew rule: ") == 1
    assert new.describe() in prompt
    assert all(r.describe() not in prompt for r in old)
    result = score("5991", '{"password":"5998"}', old, new)
    assert result["old_rules_broken"] == 3
    assert result["newly_violated_old_rule_ids"] == ["sum", "ones", "pattern"]
    # Previously failed rules do not become newly violated rules.
    inherited = score("5998", '{"password":"5998"}', old, new)
    assert inherited["old_rules_broken"] == 0
    assert inherited["newly_violated_old_rule_ids"] == []


def test_reminders_list_each_previous_rule_and_introduce_only_the_new_rule():
    old = [Rule("r1", "digit_count", 2), Rule("r2", "digit_sum", 5, "le")]
    new = Rule("r3", "length", 9)
    prompt = render("x2e!hau3", new, old, remind_previous_rules=True)
    previous, introduced = prompt.split("\nNew rule: ")
    assert 'Current string: "x2e!hau3"' in previous
    assert "Previous rules (still binding):" in previous
    for rule in old:
        assert previous.count(f"{rule.id}: {rule.describe()}") == 1
        assert rule.describe() not in introduced
    assert new.describe() not in previous
    assert introduced.startswith(f"{new.id}: {new.describe()}")
    assert "satisfying all active rules" in introduced
    # The comparison condition preserves the exact original prompt.
    assert render("x2e!hau3", new, old) == render("x2e!hau3", new)


def test_first_turn_reminder_prompt_has_no_previous_rules():
    new = Rule("r1", "digit_count", 2)
    prompt = render("xue32!hau", new, [], remind_previous_rules=True)
    assert "(none; this is the first turn)" in prompt
    assert prompt.count(f"{new.id}: {new.describe()}") == 1
