"""The filter-duplicates verdict: a gold run holds every constraint on every corpus, and each of the 11
constraints fails on its own case with its own message; plus the per-call checks."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from slimconfig import build_output, plain_output

import verifier
from contract import CompareInput, CompareOutput, DedupInput, DedupOutput, ListInput, ListOutput, PinOutput
from plugin.dedup import compare_reports, expected_output, list_reports, pin_duplicates, receipt_path
from verifier.task import TEXT


class Run:
    """A filter-duplicates run: the answer key pinned, compare_reports called in the workspace (its
    receipt written), and the correct submission ready to be judged or broken."""

    def __init__(self, workspace: Path, corpus: str = "week-01", shingle_size: int = 3, threshold: int = 70, read: bool = True) -> None:
        self.workspace = workspace
        self.task = {"corpus": corpus, "shingle_size": shingle_size, "min_similarity_percent": threshold}
        self.given = build_output(self.task, DedupInput)
        self.pin = plain_output(pin_duplicates(self.given, workspace / "scratch"))
        if read:
            self.compared = plain_output(compare_reports(build_output({"corpus": corpus, "shingle_size": shingle_size}, CompareInput), workspace))
        self.gold = plain_output(expected_output(self.given))

    def verdict(self, submission: dict | None = None, pin: dict | None = None, reference: bool = True) -> dict:
        submission = self.gold if submission is None else submission
        pinned = None if not reference else build_output(self.pin if pin is None else pin, PinOutput)
        return verifier.verify_task("filter-duplicates", self.given, build_output(submission, DedupOutput), pinned, str(self.workspace))


def failed(found: dict) -> list[str]:
    return [check["id"] for check in found["details"]["constraints"] if check["ok"] is False]


def unchecked(found: dict) -> list[str]:
    return [check["id"] for check in found["details"]["constraints"] if check["ok"] is None]


def redundant_ids(submission: dict) -> list[str]:
    return [entry["report"] for entry in submission["redundant"]]


@pytest.mark.parametrize("corpus", ["week-01", "week-02", "week-03"])
@pytest.mark.parametrize("shingle_size", [1, 2, 3, 5])
@pytest.mark.parametrize("threshold", [50, 60, 75, 80, 100])
def test_a_gold_run_holds_every_constraint(tmp_path: Path, corpus: str, shingle_size: int, threshold: int) -> None:
    run = Run(tmp_path, corpus, shingle_size, threshold)
    found = run.verdict()
    assert found["valid"], found["message"]
    assert found["score"] == 1.0 and found["message"].startswith("All 11 checks hold")
    assert [check["ok"] for check in found["details"]["constraints"]] == [True] * 11
    assert [check["id"] for check in found["details"]["constraints"]] == list(TEXT)
    assert found["details"]["expected"] == {"redundant": run.gold["redundant"], "kept": run.gold["kept"]}
    assert len(json.dumps(found)) < 6000, "the verdict lands in the chat's context: keep it small"


def test_the_gold_answers_are_the_documented_ones(tmp_path: Path) -> None:
    assert [(e["report"], e["duplicate_of"]) for e in Run(tmp_path / "a", "week-01", 3, 70).gold["redundant"]] == [("r02", "r01"), ("r06", "r01"), ("r08", "r07")]
    assert [(e["report"], e["duplicate_of"]) for e in Run(tmp_path / "b", "week-02", 3, 50).gold["redundant"]] == [("r02", "r01"), ("r04", "r03"), ("r07", "r05")]
    assert [(e["report"], e["duplicate_of"]) for e in Run(tmp_path / "c", "week-03", 3, 60).gold["redundant"]] == [
        ("r02", "r01"),
        ("r03", "r02"),
        ("r05", "r04"),
        ("r08", "r07"),
    ]


def test_a_pair_exactly_at_the_threshold_is_a_duplicate_and_one_percent_more_is_not(tmp_path: Path) -> None:
    at = Run(tmp_path / "at", "week-02", 3, 50)
    assert ("r02", "r01", 50.0) in [(e["report"], e["duplicate_of"], e["similarity_percent"]) for e in at.gold["redundant"]]
    assert at.verdict()["valid"]
    above = Run(tmp_path / "above", "week-02", 3, 51)
    assert "r02" in above.gold["kept"] and above.verdict()["valid"]
    # The two submissions are not interchangeable: each fails the other's task.
    wrong = above.verdict(at.gold)
    assert failed(wrong) == ["task-echo", "no-extra-redundant"] and wrong["message"].endswith("(+1 more)")
    extra = next(check for check in wrong["details"]["constraints"] if check["id"] == "no-extra-redundant")
    assert extra["message"] == "r02 is listed as redundant but is kept: its similarity to r01 is 50.0, under 51."


def test_no_answer_key_fails_first_and_scores_zero(tmp_path: Path) -> None:
    run = Run(tmp_path)
    found = run.verdict(reference=False)
    assert not found["valid"] and found["score"] == 0.0
    assert failed(found) == ["answer-key"] and "pin_duplicates was not run" in found["message"]
    assert unchecked(found) == list(TEXT)[1:]


def test_an_answer_key_for_another_task_fails_answer_key(tmp_path: Path) -> None:
    run = Run(tmp_path)
    other = plain_output(pin_duplicates(build_output({**run.task, "min_similarity_percent": 80}, DedupInput), tmp_path / "other"))
    found = run.verdict(pin=other)
    assert failed(found) == ["answer-key"] and found["score"] == 0.0 and "another task" in found["message"]


def test_a_tampered_pinned_corpus_fails_answer_key_data(tmp_path: Path) -> None:
    run = Run(tmp_path)
    pin = copy.deepcopy(run.pin)
    pin["reports"][0]["text"] += " extra"
    found = run.verdict(pin=pin)
    assert failed(found) == ["answer-key-data"] and found["score"] == 0.0
    assert "The pinned corpus is not the bundled week-01: the reports are not the bundled corpus week-01: sha256" in found["message"]
    assert unchecked(found) == list(TEXT)[2:]


def test_a_pinned_answer_that_breaks_the_rules_fails_answer_key_data(tmp_path: Path) -> None:
    run = Run(tmp_path)
    pin = copy.deepcopy(run.pin)
    pin["redundant"] = pin["redundant"][1:]
    found = run.verdict(pin=pin)
    assert failed(found) == ["answer-key-data"] and "not what the rules give" in found["message"]


def test_a_submission_for_another_task_fails_task_echo(tmp_path: Path) -> None:
    run = Run(tmp_path)
    found = run.verdict({**run.gold, "min_similarity_percent": 71})
    assert failed(found) == ["task-echo"] and found["score"] == 0.0
    assert "task-echo: The submission is for {'corpus': 'week-01', 'shingle_size': 3, 'min_similarity_percent': 71}, not the task" in found["message"]


def test_submitting_without_calling_compare_reports_fails_agent_read(tmp_path: Path) -> None:
    run = Run(tmp_path, read=False)
    found = run.verdict()
    assert failed(found) == ["agent-read"] and found["score"] == 0.0
    assert "agent-read: No readable receipt at dedup/week-01-k3.json: compare_reports was not called" in found["message"]
    assert [check["ok"] for check in found["details"]["constraints"]][4:] == [True] * 7, "the submission itself is still judged"


def test_a_receipt_for_another_shingle_size_does_not_count(tmp_path: Path) -> None:
    run = Run(tmp_path, read=False)
    compare_reports(build_output({"corpus": "week-01", "shingle_size": 2}, CompareInput), tmp_path)
    assert failed(run.verdict()) == ["agent-read"]


def test_a_receipt_altered_after_compare_reports_fails_agent_read(tmp_path: Path) -> None:
    run = Run(tmp_path)
    path = receipt_path(tmp_path, "week-01", 3)
    receipt = json.loads(path.read_text())
    receipt["reports"][2]["text"] = receipt["reports"][2]["text"].replace("33", "31")
    path.write_text(json.dumps(receipt))
    found = run.verdict()
    assert failed(found) == ["agent-read"] and "was altered after compare_reports" in found["message"]
    path.write_text("{not json")
    assert failed(run.verdict()) == ["agent-read"]
    path.write_text(json.dumps({"corpus": "week-01"}))
    found = run.verdict()
    assert failed(found) == ["agent-read"] and "does not hold exactly corpus, shingle_size, corpus_sha256, reports and written_at" in found["message"]
    path.write_text("[" * 50000 + "]" * 50000)  # nested past the decoder's depth: not JSON the verifier can read
    assert "No readable receipt" in run.verdict()["message"]


def test_a_receipt_left_by_an_earlier_run_fails_agent_read(tmp_path: Path) -> None:
    run = Run(tmp_path)
    path = receipt_path(tmp_path, "week-01", 3)
    receipt = json.loads(path.read_text())
    receipt["written_at"] = "2026-10-01T00:00:00Z"  # before this task's answer key was pinned
    path.write_text(json.dumps(receipt))
    found = run.verdict()
    assert failed(found) == ["agent-read"] and found["score"] == 0.0
    assert "was written at 2026-10-01T00:00:00Z, before the answer key was pinned at" in found["message"] and "Call compare_reports in this run." in found["message"]
    receipt["written_at"] = "2026-10-01T00:00:00"
    path.write_text(json.dumps(receipt))
    assert "the receipt's written_at is not a UTC time" in run.verdict()["message"]
    pin = copy.deepcopy(run.pin)
    pin["pinned_at"] = "not a time"
    found = run.verdict(pin=pin)
    assert failed(found) == ["answer-key-data"] and "The pinned time is not a UTC time" in found["message"]


def test_an_unknown_id_fails_ids_known_and_stops_the_judgement(tmp_path: Path) -> None:
    run = Run(tmp_path)
    found = run.verdict({**run.gold, "kept": [*run.gold["kept"], "r99"]})
    assert failed(found) == ["ids-known"] and found["score"] == 0.0
    assert "r99 is not in the corpus" in found["message"] and unchecked(found) == list(TEXT)[5:]


def test_a_report_listed_twice_or_as_its_own_duplicate_fails_ids_known(tmp_path: Path) -> None:
    run = Run(tmp_path)
    found = run.verdict({**run.gold, "kept": [*run.gold["kept"], "r02"]})
    assert failed(found) == ["ids-known"] and "r02 is listed more than once" in found["message"]
    twisted = copy.deepcopy(run.gold)
    twisted["redundant"][0]["duplicate_of"] = twisted["redundant"][0]["report"]
    found = run.verdict(twisted)
    assert failed(found) == ["ids-known"] and "listed as a duplicate of itself" in found["message"]


def test_a_missing_report_fails_partition(tmp_path: Path) -> None:
    run = Run(tmp_path)
    found = run.verdict({**run.gold, "kept": [report_id for report_id in run.gold["kept"] if report_id != "r04"]})
    assert failed(found) == ["partition"]
    assert "partition: 1 of the 9 reports is listed neither as redundant nor as kept: r04." in found["message"]
    assert 0 < found["score"] < 1


def test_a_redundant_report_left_out_fails_redundant_complete(tmp_path: Path) -> None:
    run = Run(tmp_path)
    kept_instead = {**run.gold, "redundant": run.gold["redundant"][1:], "kept": sorted([*run.gold["kept"], "r02"])}
    found = run.verdict(kept_instead)
    assert failed(found) == ["redundant-complete"]
    assert "redundant-complete: r02 is redundant but is not listed as redundant: it is a near-duplicate of r01 (similarity 89.4736, same numbers)." in found["message"]
    assert found["score"] == pytest.approx(0.5 * 0.8 + 0.5 * 6 / 7)


def test_an_empty_submission_fails_redundant_complete_with_two_more(tmp_path: Path) -> None:
    run = Run(tmp_path)
    found = run.verdict({**run.gold, "redundant": [], "kept": [f"r0{index}" for index in range(1, 10)]})
    assert failed(found) == ["redundant-complete"] and "Also missing: r06, r08." in found["message"]
    assert found["score"] == pytest.approx(0.5 * 0.0 + 0.5 * 6 / 9)


def test_a_kept_report_listed_as_redundant_fails_no_extra_redundant_and_says_why(tmp_path: Path) -> None:
    run = Run(tmp_path)
    extra = {"report": "r03", "duplicate_of": "r01", "similarity_percent": 83.7837}
    found = run.verdict({**run.gold, "redundant": sorted([*run.gold["redundant"], extra], key=lambda e: e["report"]), "kept": [k for k in run.gold["kept"] if k != "r03"]})
    assert failed(found) == ["no-extra-redundant"]
    assert "no-extra-redundant: r03 is listed as redundant but is kept: the numbers in r03 and r01 differ, so r03 carries a changed fact." in found["message"]
    low = {"report": "r09", "duplicate_of": "r07", "similarity_percent": 10.0}  # neither text has a number, so only the similarity is low
    found = run.verdict({**run.gold, "redundant": sorted([*run.gold["redundant"], low], key=lambda e: e["report"]), "kept": [k for k in run.gold["kept"] if k != "r09"]})
    assert "r09 is listed as redundant but is kept: its similarity to r07 is 0.0, under 70." in found["message"]
    backwards = {"report": "r01", "duplicate_of": "r06", "similarity_percent": 100.0}
    found = run.verdict({**run.gold, "redundant": [backwards, *run.gold["redundant"]], "kept": [k for k in run.gold["kept"] if k != "r01"]})
    assert "r01 is listed as redundant but is kept: r06 was published after it" in found["message"]


def test_the_wrong_original_fails_duplicate_of_exact(tmp_path: Path) -> None:
    run = Run(tmp_path)
    twisted = copy.deepcopy(run.gold)
    twisted["redundant"][1]["duplicate_of"] = "r02"  # r06 duplicates r02 too, but r01 is earlier
    twisted["redundant"][1]["similarity_percent"] = 89.4736
    found = run.verdict(twisted)
    assert failed(found) == ["duplicate-of-exact", "similarity-exact"]
    assert "duplicate-of-exact: r06 is listed as a duplicate of r02, but the earliest report it duplicates is r01. (+1 more)" == found["message"]


def test_a_rounded_similarity_fails_similarity_exact(tmp_path: Path) -> None:
    run = Run(tmp_path)
    twisted = copy.deepcopy(run.gold)
    twisted["redundant"][0]["similarity_percent"] = 89.4737
    found = run.verdict(twisted)
    assert failed(found) == ["similarity-exact"]
    assert "similarity-exact: r02's similarity is given as 89.4737, but compare_reports gave 89.4736 (copy it exactly, never rounded)." == found["message"]
    assert found["score"] == pytest.approx(0.5 * (2 * (2 / 3) * (2 / 3) / (4 / 3)) + 0.5)


def test_reports_out_of_publication_order_fail_order(tmp_path: Path) -> None:
    run = Run(tmp_path)
    found = run.verdict({**run.gold, "kept": list(reversed(run.gold["kept"]))})
    assert failed(found) == ["order"] and "The kept reports are not in publication order" in found["message"]
    found = run.verdict({**run.gold, "redundant": list(reversed(run.gold["redundant"]))})
    assert failed(found) == ["order"] and "The redundant reports are not in publication order" in found["message"]


def test_every_constraint_entry_has_the_same_keys_and_is_json(tmp_path: Path) -> None:
    run = Run(tmp_path)
    found = run.verdict({**run.gold, "redundant": [], "kept": list(reversed([f"r0{index}" for index in range(1, 10)]))})
    for check in found["details"]["constraints"]:
        assert list(check) == ["id", "constraint", "ok", "expected", "actual", "message"]
        assert check["ok"] in (True, False, None)
    json.dumps(found)


# Every tool call is checked too.
def test_verify_input_refuses_values_out_of_range() -> None:
    assert verifier.verify_input("compare_reports", build_output({"corpus": "week-01", "shingle_size": 6}, CompareInput))["valid"] is False
    assert verifier.verify_input("compare_reports", build_output({"corpus": "week-01", "shingle_size": 5}, CompareInput))["valid"] is True
    bad = build_output({"corpus": "week-01", "shingle_size": 3, "min_similarity_percent": 0}, DedupInput)
    assert "min_similarity_percent must be 1 to 100" in verifier.verify_input("pin_duplicates", bad)["message"]
    assert verifier.verify_input("list_reports", build_output({"corpus": "week-03"}, ListInput))["valid"] is True


def test_verify_output_holds_each_tool_to_the_rules(tmp_path: Path) -> None:
    given = build_output({"corpus": "week-01", "shingle_size": 3}, CompareInput)
    compared = build_output(plain_output(compare_reports(given, tmp_path)), CompareOutput)
    assert verifier.verify_output("compare_reports", given, compared, str(tmp_path))["valid"] is True
    bent = plain_output(compared)
    bent["pairs"][0]["similarity_percent"] = 1.0
    assert "not the similarities the rules give" in verifier.verify_output("compare_reports", given, build_output(bent, CompareOutput), str(tmp_path))["message"]
    assert "no readable receipt" in verifier.verify_output("compare_reports", given, compared, str(tmp_path / "elsewhere"))["message"]

    asked = build_output({"corpus": "week-02"}, ListInput)
    listed = build_output(plain_output(list_reports(asked, tmp_path)), ListOutput)
    assert verifier.verify_output("list_reports", asked, listed, str(tmp_path))["valid"] is True
    assert verifier.verify_task("list-reports", asked, listed, None, str(tmp_path))["valid"] is True
    bent = plain_output(listed)
    bent["reports"][0]["source"] = "Someone Else"
    assert verifier.verify_output("list_reports", asked, build_output(bent, ListOutput), str(tmp_path))["valid"] is False
    assert verifier.verify_task("list-reports", asked, build_output(bent, ListOutput), None, str(tmp_path))["valid"] is False

    task = build_output({"corpus": "week-03", "shingle_size": 2, "min_similarity_percent": 60}, DedupInput)
    pinned = build_output(plain_output(pin_duplicates(task, tmp_path)), PinOutput)
    assert verifier.verify_output("pin_duplicates", task, pinned, str(tmp_path))["valid"] is True
    bent = plain_output(pinned)
    bent["kept"] = bent["kept"][1:]
    assert verifier.verify_output("pin_duplicates", task, build_output(bent, PinOutput), str(tmp_path))["valid"] is False
