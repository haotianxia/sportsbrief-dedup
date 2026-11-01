"""The tools: the answer key (pin_duplicates), the corpus (list_reports) and the pairwise similarities
the agent judges from (compare_reports), each a function of the bundled data and the rules."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from contract import (
    CompareInput,
    CompareOutput,
    DedupInput,
    DedupOutput,
    ListInput,
    ListOutput,
    Pair,
    PinOutput,
    Redundant,
    Report,
    Stamp,
)
from plugin import rules
from plugin.data import CORPORA


def corpus(name: str) -> list[dict]:
    """The bundled corpus ``name``, checked against its recorded hash."""
    reports = [dict(report) for report in CORPORA[name]]
    problem = rules.corpus_problem(name, reports)
    if problem:
        raise ValueError(f"corpus {name}: {problem}")
    return reports


def check_shingle(size: int) -> None:
    if not rules.MIN_SHINGLE <= size <= rules.MAX_SHINGLE:
        raise ValueError(f"shingle_size must be {rules.MIN_SHINGLE} to {rules.MAX_SHINGLE}, not {size}")


def check_threshold(threshold: int) -> None:
    if not rules.MIN_PERCENT <= threshold <= rules.MAX_PERCENT:
        raise ValueError(f"min_similarity_percent must be {rules.MIN_PERCENT} to {rules.MAX_PERCENT}, not {threshold}")


def receipt_path(workspace: Path, name: str, size: int) -> Path:
    return workspace / rules.RECEIPTS / f"{name}-k{size}.json"


def now() -> str:
    """The clock, a UTC time YYYY-MM-DDTHH:MM:SSZ: the answer key records when it was pinned and a receipt when it was
    written, so the verifier can tell a receipt of this run from one an earlier run left in the workspace."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def list_reports(given: ListInput, workspace: Path) -> ListOutput:
    reports = corpus(given.corpus.value)
    return ListOutput(corpus=given.corpus, corpus_sha256=rules.sha256(reports), reports=[Report(**report) for report in reports])


def compare_reports(given: CompareInput, workspace: Path) -> CompareOutput:
    """Every pair's similarity at the shingle size, with a receipt of the corpus it read under the workspace."""
    check_shingle(given.shingle_size)
    reports = corpus(given.corpus.value)
    digest = rules.sha256(reports)
    receipt = {"corpus": given.corpus.value, "shingle_size": given.shingle_size, "corpus_sha256": digest, "reports": reports, "written_at": now()}
    path = receipt_path(workspace, given.corpus.value, given.shingle_size)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rules.canonical(receipt) + "\n", encoding="utf-8")
    return CompareOutput(
        corpus=given.corpus,
        shingle_size=given.shingle_size,
        corpus_sha256=digest,
        reports=[Stamp(id=report["id"], published=report["published"], source=report["source"]) for report in reports],
        pairs=[Pair(**pair) for pair in rules.pairs(reports, given.shingle_size)],
    )


def pin_duplicates(given: DedupInput, workspace: Path) -> PinOutput:
    """The answer key: the corpus, every pair, and the redundant and kept reports the rules give."""
    check_shingle(given.shingle_size)
    check_threshold(given.min_similarity_percent)
    reports = corpus(given.corpus.value)
    found = rules.pairs(reports, given.shingle_size)
    redundant, kept = rules.duplicates(reports, found, given.min_similarity_percent)
    return PinOutput(
        corpus=given.corpus,
        shingle_size=given.shingle_size,
        min_similarity_percent=given.min_similarity_percent,
        pinned_at=now(),
        corpus_sha256=rules.sha256(reports),
        reports=[Report(**report) for report in reports],
        pairs=[Pair(**pair) for pair in found],
        redundant=[Redundant(**entry) for entry in redundant],
        kept=kept,
    )


def expected_output(given: DedupInput) -> DedupOutput:
    """What a correct filter-duplicates submission is: the rules applied to the corpus (used by tests)."""
    pinned = pin_duplicates(given, Path("."))
    return DedupOutput(
        corpus=pinned.corpus,
        shingle_size=pinned.shingle_size,
        min_similarity_percent=pinned.min_similarity_percent,
        redundant=pinned.redundant,
        kept=pinned.kept,
    )
