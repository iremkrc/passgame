"""Order comparisons must retain progress differences and respect paired evidence."""

import csv
import json

import pytest

from passgame.analyze import analyze,write_analysis


def episode_rows(block,order,failure=None,initial="abc1",infrastructure=False):
    rows = []
    for turn in range(1,(failure or 8)+1):
        passed = failure is None or turn < failure
        row = {"request_key":f"{block}-{order}-{initial}-{turn}","model":"m","track":"order",
               "episode_id":f"{block}-{order}-{initial}","base_id":block,"final_set_id":block,
               "order":order,"initial":initial,"horizon":8,"turn":turn,"load":turn,
               "termination_policy":"first_failure","status":"response","full_success":int(passed),
               "new_success":int(passed),"retention":None,"outcome":"full_success" if passed else "rule_failure"}
        if infrastructure and turn == failure:
            row.update(status="infrastructure_failure",full_success=None,new_success=None)
        rows.append(row)
    return rows


def test_order_progress_comparison_remains_informative_when_both_orders_fail(tmp_path):
    rows = episode_rows("a","original",3)+episode_rows("a","reverse",1)
    rows += episode_rows("a","random_1",5)+episode_rows("a","random_2")
    rows += episode_rows("b","original",2)+episode_rows("b","reverse",2,infrastructure=True)
    result = write_analysis(rows,tmp_path,repetitions=50,seed=1)
    effects = {(r["contrast"],r["endpoint"]):r for r in result["order_effects"]}
    progress = effects[("original_minus_reverse","turns_completed")]
    assert progress["blocks"] == 1 and progress["estimate"] == 2 and progress["ci95"] == [2,2]
    assert effects[("original_minus_reverse","whole_episode_success")]["estimate"] == 0
    assert effects[("original_minus_random_1","turns_completed")]["estimate"] == -2
    assert effects[("original_minus_random_2","turns_completed")]["estimate"] == -6
    assert effects[("original_minus_random_2","whole_episode_success")]["estimate"] == -1
    reverse = next(r for r in result["order_summary"] if r["order"] == "reverse")
    assert reverse["games"] == 2 and reverse["completed_episodes"] == reverse["incomplete_episodes"] == 1
    assert reverse["whole_episode_success"]["denominator"] == 1 and reverse["mean_turns_completed"] == 0
    assert next(e for e in result["episodes"] if e["base_id"] == "b" and e["order"] == "reverse")["turns_completed"] is None
    original = next(r for r in result["order_summary"] if r["order"] == "original")
    assert original["mean_turns_completed"] == 1.5
    reverse_survival = [r for r in result["order_survival"] if r["order"] == "reverse"]
    assert all(r["denominator"] == 1 and r["numerator"] == 0 for r in reverse_survival)
    assert reverse_survival[0]["at_risk"] == reverse_survival[0]["failures_at_turn"] == 1
    assert reverse_survival[1]["at_risk"] == 0
    assert len(list(csv.DictReader((tmp_path/"order-summary.csv").open()))) == 4
    assert len(list(csv.DictReader((tmp_path/"order-effects.csv").open()))) == 6
    assert len(list(csv.DictReader((tmp_path/"order-survival.csv").open()))) == 32
    assert json.loads((tmp_path/"analysis.json").read_text())["order_effects"] == result["order_effects"]


def test_order_comparison_does_not_pair_different_initial_strings():
    rows = episode_rows("a","original",3,initial="abc1")+episode_rows("a","reverse",1,initial="xyz1")
    result = analyze(rows,repetitions=20)
    assert all(r["blocks"] == 0 and r["estimate"] is None for r in result["order_effects"]+result["h3"])


def test_duplicate_order_variants_are_rejected_instead_of_overwritten():
    rows = episode_rows("a","original",3)
    duplicate = episode_rows("a","original",2)
    for row in duplicate:
        row["request_key"] += "-duplicate"
        row["episode_id"] += "-duplicate"
    with pytest.raises(ValueError,match="Repeated order variant"):
        analyze(rows+duplicate,repetitions=20)
