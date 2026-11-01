"""The tools: the corpus, the pairs and their receipt, and the answer key, built into their contract classes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from slimconfig import build_output, plain_output

from contract import CompareInput, CompareOutput, Corpus, DedupInput, ListInput, ListOutput, PinOutput
from plugin import rules
from plugin.dedup import compare_reports, list_reports, pin_duplicates, receipt_path


def test_list_reports_gives_the_bundled_corpus_with_its_hash(tmp_path: Path) -> None:
    listed = list_reports(build_output({"corpus": "week-01"}, ListInput), tmp_path)
    build_output(plain_output(listed), ListOutput)
    assert listed.corpus is Corpus.WEEK_01 and len(listed.reports) == 9
    assert listed.corpus_sha256 == rules.DATA_SHA256["week-01"]
    assert [report.id for report in listed.reports] == [f"r0{index}" for index in range(1, 10)]


def test_compare_reports_gives_every_pair_and_writes_its_receipt(tmp_path: Path) -> None:
    compared = compare_reports(build_output({"corpus": "week-02", "shingle_size": 3}, CompareInput), tmp_path)
    build_output(plain_output(compared), CompareOutput)
    assert len(compared.pairs) == 8 * 7 // 2 and len(compared.reports) == 8
    receipt = json.loads(receipt_path(tmp_path, "week-02", 3).read_text())
    assert receipt["corpus"] == "week-02" and receipt["shingle_size"] == 3
    assert receipt["corpus_sha256"] == compared.corpus_sha256 == rules.sha256(receipt["reports"]) == rules.DATA_SHA256["week-02"]
    assert [report["id"] for report in receipt["reports"]] == [stamp.id for stamp in compared.reports]
    first = compared.pairs[0]
    assert (first.first, first.second, first.shared, first.total, first.similarity_percent, first.same_numbers) == ("r01", "r02", 10, 20, 50.0, True)


def test_pin_duplicates_gives_the_rules_answer(tmp_path: Path) -> None:
    pinned = pin_duplicates(build_output({"corpus": "week-01", "shingle_size": 3, "min_similarity_percent": 70}, DedupInput), tmp_path)
    build_output(plain_output(pinned), PinOutput)
    assert [(entry.report, entry.duplicate_of, entry.similarity_percent) for entry in pinned.redundant] == [
        ("r02", "r01", 89.4736),
        ("r06", "r01", 100.0),
        ("r08", "r07", 75.0),
    ]
    assert pinned.kept == ["r01", "r03", "r04", "r05", "r07", "r09"]
    assert pinned.corpus_sha256 == rules.DATA_SHA256["week-01"] and len(pinned.pairs) == 36
    assert not list(tmp_path.iterdir()), "the answer key writes nothing"


@pytest.mark.parametrize("size", [0, 6])
def test_a_shingle_size_out_of_range_is_refused(tmp_path: Path, size: int) -> None:
    with pytest.raises(ValueError, match="shingle_size must be 1 to 5"):
        compare_reports(build_output({"corpus": "week-01", "shingle_size": size}, CompareInput), tmp_path)
    with pytest.raises(ValueError, match="shingle_size must be 1 to 5"):
        pin_duplicates(build_output({"corpus": "week-01", "shingle_size": size, "min_similarity_percent": 50}, DedupInput), tmp_path)


@pytest.mark.parametrize("threshold", [0, 101])
def test_a_threshold_out_of_range_is_refused(tmp_path: Path, threshold: int) -> None:
    with pytest.raises(ValueError, match="min_similarity_percent must be 1 to 100"):
        pin_duplicates(build_output({"corpus": "week-01", "shingle_size": 3, "min_similarity_percent": threshold}, DedupInput), tmp_path)


def test_an_unknown_corpus_is_refused_by_the_contract(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not a valid Corpus"):
        build_output({"corpus": "week-09"}, ListInput)
