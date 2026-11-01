"""list_reports, and the list-reports task: the reports are the bundled corpus, unchanged."""

from . import rules
from .checks import plain, result


def output_problem(given, made):
    if made["corpus"] != given["corpus"]:
        return f"the reports are for {made['corpus']!r}, not the requested {given['corpus']!r}"
    problem = rules.corpus_problem(made["corpus"], made["reports"])
    if problem:
        return problem
    if made["corpus_sha256"] != rules.sha256(made["reports"]):
        return "corpus_sha256 is not the sha256 of the reports"
    return None


def verify_input(value):
    return result(True, "input is valid")


def verify_output(input_value, output_value, workspace):
    problem = output_problem(plain(input_value), plain(output_value))
    if problem:
        return result(False, problem)
    return result(True, "the reports are the bundled corpus", reports=len(output_value.reports))


def verify_task(arguments, output, reference, workspace):
    problem = output_problem(plain(arguments), plain(output))
    if problem:
        return result(False, problem)
    return result(True, f"the {len(output.reports)} reports of {output.corpus.value} are listed, unchanged", reports=len(output.reports))
