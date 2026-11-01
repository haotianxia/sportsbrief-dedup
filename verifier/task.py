"""The filter-duplicates verdict: 11 constraints, in order, judged against the answer key re-derived
from the pinned corpus (never a stored answer)."""

from . import rules
from .checks import f1, fail, hold, listed, plain, shown, skip, verdict
from .compare import read_receipt
from .pin import key_problem

TEXT = {
    "answer-key": "The answer key is pinned for this task",
    "answer-key-data": "The pinned corpus is the bundled corpus and the pinned answer follows the rules on it",
    "task-echo": "The submission names the task's corpus, shingle size and threshold",
    "agent-read": "compare_reports was called in this run for this corpus and shingle size, on the pinned corpus",
    "ids-known": "Every report id is in the corpus, no report is listed twice, and no report duplicates itself",
    "partition": "Every report is listed, as redundant or as kept",
    "redundant-complete": "Every redundant report is listed as redundant",
    "no-extra-redundant": "No kept report is listed as redundant",
    "duplicate-of-exact": "Each redundant report names the earliest report it duplicates",
    "similarity-exact": "Each redundant report's similarity is the pair's, as compare_reports gave it",
    "order": "The redundant and kept reports are in publication order",
}
INTEGRITY = ("answer-key", "answer-key-data", "task-echo", "agent-read")  # a failure here scores 0


def entry_key(entry):
    return (entry["report"], entry["duplicate_of"], entry["similarity_percent"])


def verify_task(arguments, output, reference, workspace):
    checks = []
    task, given = plain(arguments), plain(output)
    pin = None if reference is None else plain(reference)
    names = {"corpus": task["corpus"], "shingle_size": task["shingle_size"], "min_similarity_percent": task["min_similarity_percent"]}

    # 1 answer-key
    if pin is None:
        fail(checks, "answer-key", TEXT["answer-key"], "No answer key: pin_duplicates was not run for this task.", expected=names)
    elif any(pin[name] != value for name, value in names.items()):
        pinned = {name: pin[name] for name in names}
        fail(checks, "answer-key", TEXT["answer-key"], f"The answer key is for another task: {pinned}, not {names}.", expected=names, actual=pinned)
    else:
        hold(checks, "answer-key", TEXT["answer-key"], expected=names, actual=names)
    if not checks[-1]["ok"]:
        for name in list(TEXT)[1:]:
            skip(checks, name, TEXT[name], "answer-key")
        return verdict(checks, 0.0, "", expected=None, f1=0.0, kept_overlap=0.0)

    # 2 answer-key-data
    problem = key_problem(pin)
    if problem:
        fail(checks, "answer-key-data", TEXT["answer-key-data"], f"{problem[0].upper()}{problem[1:]}.", expected=pin["corpus_sha256"])
        for name in list(TEXT)[2:]:
            skip(checks, name, TEXT[name], "answer-key-data")
        return verdict(checks, 0.0, "", expected=None, f1=0.0, kept_overlap=0.0)
    hold(checks, "answer-key-data", TEXT["answer-key-data"], expected=pin["corpus_sha256"], actual=pin["corpus_sha256"])

    reports = pin["reports"]
    found = rules.pairs(reports, task["shingle_size"])
    expected_redundant, expected_kept = rules.duplicates(reports, found, task["min_similarity_percent"])
    expected = {"redundant": expected_redundant, "kept": expected_kept}
    ids = [report["id"] for report in rules.ordered(reports)]
    position = {report_id: index for index, report_id in enumerate(ids)}

    # 3 task-echo
    echoed = {name: given[name] for name in names}
    if echoed != names:
        fail(checks, "task-echo", TEXT["task-echo"], f"The submission is for {echoed}, not the task {names}.", expected=names, actual=echoed)
    else:
        hold(checks, "task-echo", TEXT["task-echo"], expected=names, actual=echoed)

    # 4 agent-read
    receipt, problem = read_receipt(workspace, task["corpus"], task["shingle_size"])
    if problem:
        fail(checks, "agent-read", TEXT["agent-read"], f"{problem[0].upper()}{problem[1:]}.", expected=pin["corpus_sha256"])
    elif receipt["corpus_sha256"] != pin["corpus_sha256"] or receipt["reports"] != reports:
        fail(
            checks,
            "agent-read",
            TEXT["agent-read"],
            "The corpus compare_reports read is not the pinned corpus.",
            expected=pin["corpus_sha256"],
            actual=receipt["corpus_sha256"],
        )
    elif receipt["written_at"] < pin["pinned_at"]:
        fail(
            checks,
            "agent-read",
            TEXT["agent-read"],
            f"The receipt was written at {receipt['written_at']}, before the answer key was pinned at {pin['pinned_at']}: it is left over "
            "from an earlier run. Call compare_reports in this run.",
            expected=pin["pinned_at"],
            actual=receipt["written_at"],
        )
    else:
        hold(checks, "agent-read", TEXT["agent-read"], expected=pin["corpus_sha256"], actual=receipt["corpus_sha256"])

    # 5 ids-known
    submitted_redundant = given["redundant"]
    submitted_kept = given["kept"]
    mentioned = [entry["report"] for entry in submitted_redundant] + [entry["duplicate_of"] for entry in submitted_redundant] + submitted_kept
    unknown = sorted({report_id for report_id in mentioned if report_id not in position})
    placed = [entry["report"] for entry in submitted_redundant] + submitted_kept
    twice = sorted({report_id for report_id in placed if placed.count(report_id) > 1})
    selfish = [entry["report"] for entry in submitted_redundant if entry["report"] == entry["duplicate_of"]]
    if unknown or twice or selfish:
        problems = []
        if unknown:
            problems.append(f"{listed(unknown)} {'is' if len(unknown) == 1 else 'are'} not in the corpus (ids are r01, r02, ...)")
        if twice:
            problems.append(f"{listed(twice)} {'is' if len(twice) == 1 else 'are'} listed more than once")
        if selfish:
            problems.append(f"{listed(selfish)} {'is' if len(selfish) == 1 else 'are'} listed as a duplicate of itself")
        fail(checks, "ids-known", TEXT["ids-known"], "The submission is malformed: " + "; ".join(problems) + ".", expected=shown(ids), actual=shown(mentioned))
        for name in list(TEXT)[5:]:
            skip(checks, name, TEXT[name], "ids-known")
        return verdict(checks, 0.0, "", expected=expected, f1=0.0, kept_overlap=0.0)
    hold(checks, "ids-known", TEXT["ids-known"], expected=shown(ids), actual=shown(mentioned))

    # 6 partition
    missing = [report_id for report_id in ids if report_id not in placed]
    if missing:
        fail(
            checks,
            "partition",
            TEXT["partition"],
            f"{len(missing)} of the {len(ids)} reports {'is' if len(missing) == 1 else 'are'} listed neither as redundant nor as kept: {listed(missing)}.",
            expected=shown(ids),
            actual=shown(placed),
        )
    else:
        hold(checks, "partition", TEXT["partition"], expected=shown(ids), actual=shown(placed))

    # 7 redundant-complete
    redundant_ids = [entry["report"] for entry in submitted_redundant]
    expected_ids = [entry["report"] for entry in expected_redundant]
    by_report = {entry["report"]: entry for entry in expected_redundant}
    not_listed = [report_id for report_id in expected_ids if report_id not in redundant_ids]
    if not_listed:
        first = by_report[not_listed[0]]
        fail(
            checks,
            "redundant-complete",
            TEXT["redundant-complete"],
            f"{first['report']} is redundant but is not listed as redundant: it is a near-duplicate of {first['duplicate_of']} "
            f"(similarity {first['similarity_percent']}, same numbers)."
            + (f" Also missing: {listed(not_listed[1:])}." if len(not_listed) > 1 else ""),
            expected=shown(expected_ids),
            actual=shown(redundant_ids),
        )
    else:
        hold(checks, "redundant-complete", TEXT["redundant-complete"], expected=shown(expected_ids), actual=shown(redundant_ids))

    # 8 no-extra-redundant
    extra = [report_id for report_id in redundant_ids if report_id not in by_report]
    if extra:
        first = extra[0]
        entry = next(entry for entry in submitted_redundant if entry["report"] == first)
        pair = next((pair for pair in found if {pair["first"], pair["second"]} == {first, entry["duplicate_of"]}), None)
        if pair is None:
            why = f"{entry['duplicate_of']} is not another report of the corpus"
        elif pair["first"] == first:
            why = f"{entry['duplicate_of']} was published after it, so it cannot duplicate it"
        elif not pair["same_numbers"]:
            why = f"the numbers in {first} and {entry['duplicate_of']} differ, so {first} carries a changed fact"
        else:
            why = f"its similarity to {entry['duplicate_of']} is {pair['similarity_percent']}, under {task['min_similarity_percent']}"
        fail(
            checks,
            "no-extra-redundant",
            TEXT["no-extra-redundant"],
            f"{first} is listed as redundant but is kept: {why}." + (f" Also wrong: {listed(extra[1:])}." if len(extra) > 1 else ""),
            expected=shown(expected_kept),
            actual=shown(extra),
        )
    else:
        hold(checks, "no-extra-redundant", TEXT["no-extra-redundant"], expected=shown(expected_kept), actual=shown(submitted_kept))

    # 9 duplicate-of-exact and 10 similarity-exact, over the reports both sides call redundant
    judged = [entry for entry in submitted_redundant if entry["report"] in by_report]
    wrong_of = [entry for entry in judged if entry["duplicate_of"] != by_report[entry["report"]]["duplicate_of"]]
    if wrong_of:
        first = wrong_of[0]
        fail(
            checks,
            "duplicate-of-exact",
            TEXT["duplicate-of-exact"],
            f"{first['report']} is listed as a duplicate of {first['duplicate_of']}, but the earliest report it duplicates is "
            f"{by_report[first['report']]['duplicate_of']}." + (f" Also wrong: {listed(entry['report'] for entry in wrong_of[1:])}." if len(wrong_of) > 1 else ""),
            expected=shown(f"{entry['report']}<-{entry['duplicate_of']}" for entry in expected_redundant),
            actual=shown(f"{entry['report']}<-{entry['duplicate_of']}" for entry in submitted_redundant),
        )
    else:
        hold(
            checks,
            "duplicate-of-exact",
            TEXT["duplicate-of-exact"],
            expected=shown(f"{entry['report']}<-{entry['duplicate_of']}" for entry in expected_redundant),
            actual=shown(f"{entry['report']}<-{entry['duplicate_of']}" for entry in submitted_redundant),
        )
    wrong_similarity = [entry for entry in judged if entry["similarity_percent"] != by_report[entry["report"]]["similarity_percent"]]
    if wrong_similarity:
        first = wrong_similarity[0]
        fail(
            checks,
            "similarity-exact",
            TEXT["similarity-exact"],
            f"{first['report']}'s similarity is given as {first['similarity_percent']}, but compare_reports gave "
            f"{by_report[first['report']]['similarity_percent']} (copy it exactly, never rounded)."
            + (f" Also wrong: {listed(entry['report'] for entry in wrong_similarity[1:])}." if len(wrong_similarity) > 1 else ""),
            expected=shown(f"{entry['report']}={entry['similarity_percent']}" for entry in expected_redundant),
            actual=shown(f"{entry['report']}={entry['similarity_percent']}" for entry in submitted_redundant),
        )
    else:
        hold(
            checks,
            "similarity-exact",
            TEXT["similarity-exact"],
            expected=shown(f"{entry['report']}={entry['similarity_percent']}" for entry in expected_redundant),
            actual=shown(f"{entry['report']}={entry['similarity_percent']}" for entry in submitted_redundant),
        )

    # 11 order
    redundant_positions = [position[report_id] for report_id in redundant_ids]
    kept_positions = [position[report_id] for report_id in submitted_kept]
    if redundant_positions != sorted(redundant_positions) or kept_positions != sorted(kept_positions):
        which = "redundant" if redundant_positions != sorted(redundant_positions) else "kept"
        fail(
            checks,
            "order",
            TEXT["order"],
            f"The {which} reports are not in publication order (by published time, then id).",
            expected=shown(sorted(redundant_ids if which == "redundant" else submitted_kept, key=position.get)),
            actual=shown(redundant_ids if which == "redundant" else submitted_kept),
        )
    else:
        hold(checks, "order", TEXT["order"], expected=shown(ids), actual=shown(redundant_ids + submitted_kept))

    # The score: 0 when the data or the submission's integrity fails; otherwise half the F1 of the
    # redundant entries (an entry counts only when it is exactly right) and half the overlap of the kept sets.
    entries_f1 = f1([entry_key(entry) for entry in expected_redundant], [entry_key(entry) for entry in submitted_redundant])
    kept_union = set(expected_kept) | set(submitted_kept)
    kept_overlap = len(set(expected_kept) & set(submitted_kept)) / len(kept_union) if kept_union else 1.0
    score = 0.0 if any(check["ok"] is False for check in checks if check["id"] in INTEGRITY) else 0.5 * entries_f1 + 0.5 * kept_overlap
    summary = (
        f"{len(expected_redundant)} of the {len(ids)} reports of {task['corpus']} are redundant copies and {len(expected_kept)} are kept, "
        f"at shingle size {task['shingle_size']} and {task['min_similarity_percent']}% similarity."
    )
    return verdict(checks, score, summary, expected=expected, f1=entries_f1, kept_overlap=kept_overlap)
