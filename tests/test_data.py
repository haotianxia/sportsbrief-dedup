"""The bundled corpora: well formed, hashed as the rules record, and holding the cases the task is about."""

from __future__ import annotations

import pytest

from plugin import rules
from plugin.data import CORPORA


@pytest.mark.parametrize("name", sorted(CORPORA))
def test_each_corpus_is_well_formed_and_matches_its_recorded_hash(name: str) -> None:
    assert rules.corpus_problem(name, CORPORA[name]) is None
    assert rules.sha256(CORPORA[name]) == rules.DATA_SHA256[name]
    assert set(rules.DATA_SHA256) == set(CORPORA)


def pair(name: str, size: int, first: str, second: str) -> dict:
    return next(entry for entry in rules.pairs(CORPORA[name], size) if (entry["first"], entry["second"]) == (first, second))


def test_week_01_holds_a_copy_a_rewrite_a_corrected_stat_and_a_pair_exactly_at_75() -> None:
    assert pair("week-01", 3, "r01", "r06")["similarity_percent"] == 100.0  # a syndicated copy
    assert pair("week-01", 3, "r01", "r02")["same_numbers"] is True  # a rewrite with the same facts
    assert pair("week-01", 3, "r01", "r03")["same_numbers"] is False  # 33 points instead of 31
    assert pair("week-01", 3, "r01", "r03")["similarity_percent"] > 80
    boundary = pair("week-01", 3, "r07", "r08")
    assert (boundary["shared"], boundary["total"], boundary["similarity_percent"]) == (18, 24, 75.0)


def test_week_02_holds_a_pair_exactly_at_50_and_an_added_stat() -> None:
    boundary = pair("week-02", 3, "r01", "r02")
    assert (boundary["shared"], boundary["total"], boundary["similarity_percent"], boundary["same_numbers"]) == (10, 20, 50.0, True)
    assert pair("week-02", 3, "r05", "r06")["same_numbers"] is False  # 7 assists added
    assert pair("week-02", 3, "r05", "r07")["similarity_percent"] == 100.0


def test_week_03_holds_a_chain_whose_third_report_duplicates_the_second_but_not_the_first() -> None:
    assert pair("week-03", 3, "r01", "r02")["similarity_percent"] == 71.1111
    assert pair("week-03", 3, "r02", "r03")["similarity_percent"] == 63.2653
    assert pair("week-03", 3, "r01", "r03")["similarity_percent"] == 42.5925
    redundant, _kept = rules.duplicates(CORPORA["week-03"], rules.pairs(CORPORA["week-03"], 3), 60)
    assert [(entry["report"], entry["duplicate_of"]) for entry in redundant] == [("r02", "r01"), ("r03", "r02"), ("r05", "r04"), ("r08", "r07")]
    redundant, _kept = rules.duplicates(CORPORA["week-03"], rules.pairs(CORPORA["week-03"], 3), 70)
    assert [(entry["report"], entry["duplicate_of"]) for entry in redundant] == [("r02", "r01"), ("r05", "r04"), ("r08", "r07")]
