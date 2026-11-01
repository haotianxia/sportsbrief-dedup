"""The rules: words, shingles, similarity, the numbers guard and the redundant/kept split; and the
verifier's copy of them is byte-for-byte the tools'."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from plugin import rules

ROOT = Path(__file__).resolve().parents[1]


def test_the_verifier_runs_the_very_rules_the_tools_use() -> None:
    assert (ROOT / "verifier" / "rules.py").read_bytes() == (ROOT / "src" / "plugin" / "rules.py").read_bytes()


def test_words_are_lower_cased_runs_of_letters_or_digits() -> None:
    assert rules.words("The Lynx won 104-97; Okafor's 31 points!") == ["the", "lynx", "won", "104", "97", "okafor", "s", "31", "points"]


def test_shingles_of_a_short_or_empty_text() -> None:
    assert rules.shingles("one two three four", 2) == {("one", "two"), ("two", "three"), ("three", "four")}
    assert rules.shingles("one two", 3) == {("one", "two")}  # shorter than the shingle: one shingle
    assert rules.shingles("one two three", 3) == {("one", "two", "three")}
    assert rules.shingles("...", 3) == set()


def test_jaccard_is_exact_and_zero_on_empty_sets() -> None:
    assert rules.jaccard({1, 2, 3}, {2, 3, 4}) == Fraction(1, 2)
    assert rules.jaccard({1}, {1}) == 1
    assert rules.jaccard({1}, {2}) == 0
    assert rules.jaccard(set(), set()) == 0


def test_percent_truncates_and_never_rounds() -> None:
    assert rules.percent(Fraction(2, 3)) == 66.6666
    assert rules.percent(Fraction(1, 2)) == 50.0
    assert rules.percent(Fraction(1)) == 100.0
    assert rules.percent(Fraction(0)) == 0.0
    assert rules.percent(Fraction(99999, 100000)) == 99.999


def test_numbers_are_runs_of_digits() -> None:
    assert rules.numbers("won 104-97 on 2026-10-21, 4.2 million") == {"104", "97", "2026", "10", "21", "4", "2"}
    assert rules.numbers("no digits here") == set()


def report(report_id: str, published: str, text: str) -> dict:
    return {"id": report_id, "published": published, "source": "Test", "text": text}


CHAIN = [
    report("r01", "2026-01-01T00:00:00Z", "alpha beta gamma delta epsilon zeta"),
    report("r02", "2026-01-01T00:10:00Z", "alpha beta gamma delta epsilon zeta eta"),  # 5 of 6 shingles shared with r01
    report("r03", "2026-01-01T00:20:00Z", "beta gamma delta epsilon zeta eta theta"),  # 5 of 7 with r02, 4 of 7 with r01
    report("r04", "2026-01-01T00:30:00Z", "unrelated words entirely"),
]


def test_pairs_cover_every_pair_in_publication_order() -> None:
    found = rules.pairs(CHAIN, 2)
    assert [(pair["first"], pair["second"]) for pair in found] == [("r01", "r02"), ("r01", "r03"), ("r01", "r04"), ("r02", "r03"), ("r02", "r04"), ("r03", "r04")]
    by_pair = {(pair["first"], pair["second"]): pair for pair in found}
    assert (by_pair["r01", "r02"]["shared"], by_pair["r01", "r02"]["total"]) == (5, 6)
    assert by_pair["r01", "r02"]["similarity_percent"] == 83.3333
    assert by_pair["r02", "r03"]["similarity_percent"] == 71.4285
    assert by_pair["r01", "r03"]["similarity_percent"] == 57.1428
    assert by_pair["r03", "r04"]["similarity_percent"] == 0.0 and by_pair["r03", "r04"]["same_numbers"] is True


def test_a_report_duplicates_the_earliest_qualifying_partner() -> None:
    found = rules.pairs(CHAIN, 2)
    redundant, kept = rules.duplicates(CHAIN, found, 50)
    assert [(entry["report"], entry["duplicate_of"]) for entry in redundant] == [("r02", "r01"), ("r03", "r01")]
    assert kept == ["r01", "r04"]
    redundant, kept = rules.duplicates(CHAIN, found, 60)  # r03 is under 60 with r01 (57.14) but not with r02 (71.42), so it duplicates r02
    assert [(entry["report"], entry["duplicate_of"]) for entry in redundant] == [("r02", "r01"), ("r03", "r02")]
    assert kept == ["r01", "r04"]
    redundant, kept = rules.duplicates(CHAIN, found, 90)
    assert redundant == [] and kept == ["r01", "r02", "r03", "r04"]


def test_the_threshold_is_compared_exactly() -> None:
    pair = {"first": "a", "second": "b", "shared": 1, "total": 3, "similarity_percent": 33.3333, "same_numbers": True}
    assert rules.qualifies(pair, 33) is True
    assert rules.qualifies(pair, 34) is False
    assert rules.qualifies({**pair, "same_numbers": False}, 1) is False
    assert rules.qualifies({**pair, "shared": 0, "total": 0, "similarity_percent": 0.0}, 1) is False


def test_a_changed_number_keeps_a_rewrite_apart() -> None:
    reports = [
        report("r01", "2026-01-01T00:00:00Z", "the lynx won 104-97 on tuesday night"),
        report("r02", "2026-01-01T00:05:00Z", "the lynx won 104-96 on tuesday night"),
        report("r03", "2026-01-01T00:05:00Z", "the lynx won 104-97 on tuesday night"),
    ]
    found = rules.pairs(reports, 2)
    redundant, kept = rules.duplicates(reports, found, 50)
    assert [(entry["report"], entry["duplicate_of"], entry["similarity_percent"]) for entry in redundant] == [("r03", "r01", 100.0)]
    assert kept == ["r01", "r02"]


def test_reports_published_at_the_same_time_order_by_id() -> None:
    reports = [report("r02", "2026-01-01T00:00:00Z", "same words here"), report("r01", "2026-01-01T00:00:00Z", "same words here")]
    assert [entry["id"] for entry in rules.ordered(reports)] == ["r01", "r02"]
    redundant, kept = rules.duplicates(reports, rules.pairs(reports, 2), 100)
    assert [(entry["report"], entry["duplicate_of"]) for entry in redundant] == [("r02", "r01")] and kept == ["r01"]


def test_a_stamp_is_an_ascii_utc_time() -> None:
    assert rules.stamp_problem("2026-10-21T02:10:00Z") is None
    assert rules.stamp_problem("2026-10-21T02:10:00") == "'2026-10-21T02:10:00' is not a UTC time YYYY-MM-DDTHH:MM:SSZ"
    assert rules.stamp_problem("2026-02-30T02:10:00Z") == "'2026-02-30T02:10:00Z' is not a calendar day"
    assert rules.stamp_problem("2026-10-21T24:10:00Z") == "'2026-10-21T24:10:00Z' is not a time of day"
    assert rules.stamp_problem("2026-10-21T02:10:0０Z") is not None, "a full-width digit is not a digit here"
    assert rules.stamp_problem(None) is not None
    assert rules.REPORT_ID.fullmatch("r0１") is None


def test_corpus_problem_names_what_is_wrong() -> None:
    assert rules.corpus_problem("week-09", []) == "'week-09' is not a bundled corpus"
    assert rules.corpus_problem("week-01", []) == "the corpus holds no report"
    good = report("r01", "2026-01-01T00:00:00Z", "words")
    assert rules.corpus_problem("week-01", [good, dict(good)]) == "a report id appears twice"
    assert rules.corpus_problem("week-01", [{**good, "id": "x1"}]) == "'x1' is not a report id (r followed by two digits)"
    assert "not a UTC time" in rules.corpus_problem("week-01", [{**good, "published": "2026-01-01 00:00"}])
    assert rules.corpus_problem("week-01", [{**good, "text": "!!"}]) == "r01 has no words"
    later = report("r02", "2025-01-01T00:00:00Z", "earlier but listed later")
    assert rules.corpus_problem("week-01", [good, later]) == "the reports are not in publication order"
    assert rules.corpus_problem("week-01", [good]).startswith("the reports are not the bundled corpus week-01: sha256 ")
