import json
import pytest
from passgame.constraints import Rule
from passgame.protocol import parse, score


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
