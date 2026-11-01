"""The near-duplicate rules: pure functions of the corpus, shared by the tools and the verifier.

verifier/rules.py is a byte-for-byte copy of this file (tests/test_rules.py enforces it), so the
verifier re-derives every pair, every redundant report and every hash with the very code the
tools used, importing only pure standard-library modules. Values are plain JSON values here;
the tools build them into contract classes, and the verifier takes contract instances apart.
"""

import hashlib
import json
import re
from decimal import ROUND_DOWN, Decimal
from fractions import Fraction

WORD = re.compile(r"[a-z0-9]+")  # a word: a run of letters or digits, lower-cased
NUMBER = re.compile(r"[0-9]+")  # a number: a run of digits, the key facts a rewrite must keep
REPORT_ID = re.compile(r"^r[0-9]{2}$")
MIN_SHINGLE, MAX_SHINGLE = 1, 5
MIN_PERCENT, MAX_PERCENT = 1, 100
DECIMALS = Decimal("0.0001")  # similarity_percent is truncated to 4 decimals
RECEIPTS = "dedup"  # compare_reports records what it read under <workspace>/dedup/<corpus>-k<shingle_size>.json
# sha256 of each bundled corpus's canonical JSON (src/plugin/data.py); tests/test_data.py keeps them current.
DATA_SHA256 = {
    "week-01": "4f5fb43e528d78a45c32baf1ca71727bb64410cccefb43adf97a6a248d6b6146",
    "week-02": "89ec7f4944a5fb39a46cbeea73f36249e871cefadee3ca0f303618e7bd5d0d21",
    "week-03": "f734894b9a57602b5a0f0fec324b81316beb478d436342bc8f313e1617d09b4f",
}

STAMP = re.compile(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})Z$")  # a UTC time, comparable as text


def is_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def days_in_month(year, month):
    if month == 2:
        return 29 if is_leap(year) else 28
    return 30 if month in (4, 6, 9, 11) else 31


def stamp_problem(text):
    """Why ``text`` is not a UTC time YYYY-MM-DDTHH:MM:SSZ, or None. Such times compare as text."""
    found = STAMP.fullmatch(text) if isinstance(text, str) else None
    if not found:
        return f"{text!r} is not a UTC time YYYY-MM-DDTHH:MM:SSZ"
    year, month, day, hour, minute, second = (int(part) for part in found.groups())
    if not 1 <= month <= 12 or not 1 <= day <= days_in_month(year, month):
        return f"{text!r} is not a calendar day"
    if hour > 23 or minute > 59 or second > 59:
        return f"{text!r} is not a time of day"
    return None


def canonical(value):
    """``value`` as canonical JSON: sorted keys, no spaces, ASCII only."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def words(text):
    return WORD.findall(text.lower())


def shingles(text, size):
    """The set of ``size``-word runs of ``text``; a text shorter than ``size`` words is one shingle,
    and an empty text has none."""
    found = words(text)
    if len(found) <= size:
        return {tuple(found)} if found else set()
    return {tuple(found[start : start + size]) for start in range(len(found) - size + 1)}


def numbers(text):
    return set(NUMBER.findall(text))


def jaccard(first, second):
    """|first & second| / |first | second| as an exact Fraction; 0 when both are empty."""
    union = first | second
    return Fraction(len(first & second), len(union)) if union else Fraction(0)


def percent(fraction):
    """``fraction`` in percent, truncated to 4 decimals, as the float the tools report."""
    exact = Decimal(fraction.numerator * 100) / Decimal(fraction.denominator)
    return float(exact.quantize(DECIMALS, rounding=ROUND_DOWN))


def order_key(report):
    return (report["published"], report["id"])


def ordered(reports):
    """The reports in publication order: by published, then by id."""
    return sorted(reports, key=order_key)


def pairs(reports, size):
    """Every pair of ``reports`` (plain dicts) with its similarity, ordered by first then second."""
    found = []
    seen = ordered(reports)
    sets = {report["id"]: shingles(report["text"], size) for report in seen}
    counts = {report["id"]: numbers(report["text"]) for report in seen}
    for index, first in enumerate(seen):
        for second in seen[index + 1 :]:
            shared = len(sets[first["id"]] & sets[second["id"]])
            total = len(sets[first["id"]] | sets[second["id"]])
            found.append(
                {
                    "first": first["id"],
                    "second": second["id"],
                    "shared": shared,
                    "total": total,
                    "similarity_percent": percent(Fraction(shared, total) if total else Fraction(0)),
                    "same_numbers": counts[first["id"]] == counts[second["id"]],
                }
            )
    return found


def qualifies(pair, threshold):
    """Whether ``pair`` makes a near-duplicate at ``threshold`` percent: similarity at least the
    threshold, compared exactly, and the same numbers in both texts."""
    if not pair["total"]:
        return False
    return pair["same_numbers"] and Fraction(pair["shared"], pair["total"]) >= Fraction(threshold, 100)


def duplicates(reports, found, threshold):
    """``(redundant, kept)`` for the pairs ``found`` of ``reports``: a report is redundant when an
    earlier report makes a near-duplicate with it, and it duplicates the earliest such report."""
    partners = {}
    for pair in found:
        if qualifies(pair, threshold):
            partners.setdefault(pair["second"], []).append(pair)
    redundant, kept = [], []
    for report in ordered(reports):
        earlier = partners.get(report["id"])
        if earlier:
            redundant.append(
                {"report": report["id"], "duplicate_of": earlier[0]["first"], "similarity_percent": earlier[0]["similarity_percent"]}
            )
        else:
            kept.append(report["id"])
    return redundant, kept


def corpus_problem(name, reports):
    """What is wrong with ``reports`` as the bundled corpus ``name``, or None."""
    if name not in DATA_SHA256:
        return f"{name!r} is not a bundled corpus"
    if not reports:
        return "the corpus holds no report"
    ids = [report["id"] for report in reports]
    if len(set(ids)) != len(ids):
        return "a report id appears twice"
    for report in reports:
        if not REPORT_ID.fullmatch(report["id"]):
            return f"{report['id']!r} is not a report id (r followed by two digits)"
        if not STAMP.fullmatch(report["published"]):
            return f"{report['id']}'s published time {report['published']!r} is not a UTC time YYYY-MM-DDTHH:MM:SSZ"
        if not words(report["text"]):
            return f"{report['id']} has no words"
    if [report["id"] for report in reports] != [report["id"] for report in ordered(reports)]:
        return "the reports are not in publication order"
    if sha256(reports) != DATA_SHA256[name]:
        return f"the reports are not the bundled corpus {name}: sha256 {sha256(reports)} instead of {DATA_SHA256[name]}"
    return None
