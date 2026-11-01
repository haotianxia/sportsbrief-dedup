"""pin_duplicates, the filter-duplicates reference: its input is in range and its answer key follows the rules."""

from . import rules
from .checks import plain, result


def input_problem(value):
    if not rules.MIN_SHINGLE <= value.shingle_size <= rules.MAX_SHINGLE:
        return f"shingle_size must be {rules.MIN_SHINGLE} to {rules.MAX_SHINGLE}, not {value.shingle_size}"
    if not rules.MIN_PERCENT <= value.min_similarity_percent <= rules.MAX_PERCENT:
        return f"min_similarity_percent must be {rules.MIN_PERCENT} to {rules.MAX_PERCENT}, not {value.min_similarity_percent}"
    return None


def key_problem(pin):
    """What is wrong with the plain answer key ``pin``, or None: its corpus is the bundled one and its
    pairs, redundant and kept reports are what the rules give on it."""
    problem = rules.stamp_problem(pin["pinned_at"])
    if problem:
        return f"the pinned time is not a UTC time: {problem}"
    problem = rules.corpus_problem(pin["corpus"], pin["reports"])
    if problem:
        return f"the pinned corpus is not the bundled {pin['corpus']}: {problem}"
    if pin["corpus_sha256"] != rules.sha256(pin["reports"]):
        return "the pinned corpus does not match its own sha256"
    found = rules.pairs(pin["reports"], pin["shingle_size"])
    if pin["pairs"] != found:
        return "the pinned pairs are not the similarities the rules give on the pinned corpus"
    if [pin["redundant"], pin["kept"]] != list(rules.duplicates(pin["reports"], found, pin["min_similarity_percent"])):
        return "the pinned redundant and kept reports are not what the rules give on the pinned pairs"
    return None


def verify_input(value):
    problem = input_problem(value)
    return result(False, problem) if problem else result(True, "input is valid")


def verify_output(input_value, output_value, workspace):
    given, pin = plain(input_value), plain(output_value)
    for name in ("corpus", "shingle_size", "min_similarity_percent"):
        if pin[name] != given[name]:
            return result(False, f"the answer key's {name} is {pin[name]!r}, not the task's {given[name]!r}")
    problem = key_problem(pin)
    if problem:
        return result(False, problem)
    return result(True, "the answer key follows the rules", redundant=len(pin["redundant"]), kept=len(pin["kept"]))
