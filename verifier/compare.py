"""compare_reports: its pairs are the rules applied to the corpus its receipt records."""

from pathlib import Path

from . import rules
from .checks import plain, read_json, result

RECEIPT_KEYS = ("corpus", "shingle_size", "corpus_sha256", "reports", "written_at")


def receipt_path(workspace, corpus, shingle_size):
    return Path(workspace) / rules.RECEIPTS / f"{corpus}-k{shingle_size}.json"


def receipt_problem(receipt, corpus, shingle_size):
    """What is wrong with ``receipt`` as compare_reports's record of reading ``corpus`` at ``shingle_size``, or None."""
    if not isinstance(receipt, dict) or sorted(receipt) != sorted(RECEIPT_KEYS):
        return "the receipt does not hold exactly corpus, shingle_size, corpus_sha256, reports and written_at"
    if receipt["corpus"] != corpus or receipt["shingle_size"] != shingle_size:
        return f"the receipt is for {receipt['corpus']!r} at shingle size {receipt['shingle_size']!r}"
    problem = rules.stamp_problem(receipt["written_at"])
    if problem:
        return f"the receipt's written_at is not a UTC time: {problem}"
    reports = receipt["reports"]
    if not isinstance(reports, list) or not all(
        isinstance(report, dict) and sorted(report) == ["id", "published", "source", "text"] and all(isinstance(value, str) for value in report.values())
        for report in reports
    ):
        return "the receipt's reports are not records of id, published, source and text"
    problem = rules.corpus_problem(corpus, reports)
    if problem:
        return f"the receipt's reports are not the bundled {corpus}: {problem}"
    if receipt["corpus_sha256"] != rules.sha256(reports):
        return "the receipt's reports do not match its own sha256"
    return None


def read_receipt(workspace, corpus, shingle_size):
    """``(receipt, problem)``: the receipt compare_reports wrote for the corpus and shingle size, or why there is none."""
    path = receipt_path(workspace, corpus, shingle_size)
    receipt = read_json(path)
    if receipt is None:
        return None, f"no readable receipt at {rules.RECEIPTS}/{path.name}: compare_reports was not called for this corpus and shingle size"
    problem = receipt_problem(receipt, corpus, shingle_size)
    if problem:
        return None, f"the receipt {rules.RECEIPTS}/{path.name} was altered after compare_reports: {problem}"
    return receipt, None


def verify_input(value):
    if not rules.MIN_SHINGLE <= value.shingle_size <= rules.MAX_SHINGLE:
        return result(False, f"shingle_size must be {rules.MIN_SHINGLE} to {rules.MAX_SHINGLE}, not {value.shingle_size}")
    return result(True, "input is valid")


def verify_output(input_value, output_value, workspace):
    given, made = plain(input_value), plain(output_value)
    if made["corpus"] != given["corpus"] or made["shingle_size"] != given["shingle_size"]:
        return result(False, "the output is not for the requested corpus and shingle size")
    receipt, problem = read_receipt(workspace, given["corpus"], given["shingle_size"])
    if problem:
        return result(False, problem)
    if made["corpus_sha256"] != receipt["corpus_sha256"]:
        return result(False, "corpus_sha256 is not the receipt's")
    stamps = [{"id": report["id"], "published": report["published"], "source": report["source"]} for report in receipt["reports"]]
    if made["reports"] != stamps:
        return result(False, "the reports listed are not the receipt's, in publication order")
    if made["pairs"] != rules.pairs(receipt["reports"], given["shingle_size"]):
        return result(False, "the pairs are not the similarities the rules give on the receipt's reports")
    return result(True, "the pairs follow the rules", pairs=len(made["pairs"]))
