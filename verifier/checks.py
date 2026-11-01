"""Shared verdict helpers: a result, plain forms of contract instances, workspace files, and the
ordered constraint list a task verdict carries. Pure functions of their arguments and the files they read."""

import dataclasses
import enum
import json
from pathlib import Path

MOST = 8  # list entries a constraint's expected or actual shows
MAX_FILE_BYTES = 1_000_000  # far above any receipt the tools write


def result(valid, message, *, score=None, **details):
    return {
        "valid": valid,
        "score": float(valid) if score is None else score,
        "message": message,
        "details": details,
    }


def plain(value):
    """A contract instance, or any value inside one, as JSON: Enum members as their values."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        value = dataclasses.asdict(value)
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [plain(item) for item in value]
    return value


def read_json(path):
    """The JSON value the file ``path`` holds, or None when it is missing, unreadable, too large or not JSON."""
    path = Path(path)
    try:
        if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):  # unreadable, not JSON, or nested past the decoder's depth
        return None


def shown(values):
    """A list cut to what a message can show."""
    values = list(values)
    if len(values) <= MOST:
        return values
    return [*values[:MOST], f"... and {len(values) - MOST} more"]


def listed(values):
    """Up to a few values in a sentence: 'r02, r06 and 3 more'."""
    values = [str(value) for value in values]
    if len(values) <= 3:
        return ", ".join(values)
    return f"{', '.join(values[:3])} and {len(values) - 3} more"


def hold(checks, name, constraint, expected=None, actual=None):
    checks.append({"id": name, "constraint": constraint, "ok": True, "expected": expected, "actual": actual, "message": ""})
    return True


def fail(checks, name, constraint, message, expected=None, actual=None):
    checks.append({"id": name, "constraint": constraint, "ok": False, "expected": expected, "actual": actual, "message": message})
    return False


def skip(checks, name, constraint, needs):
    checks.append(
        {"id": name, "constraint": constraint, "ok": None, "expected": None, "actual": None, "message": f"Not checked: {needs} did not hold."}
    )


def verdict(checks, score, summary, **details):
    """The verdict the constraints ``checks`` give: valid, with score 1, only when every one holds;
    otherwise the first failing constraint names the problem and the score is at most 0.99."""
    failing = [check for check in checks if check["ok"] is False]
    if not failing:
        return result(True, f"All {len(checks)} checks hold: {summary}", score=1.0, constraints=checks, **details)
    first = failing[0]
    more = len(failing) - 1
    message = f"{first['id']}: {first['message']}" + (f" (+{more} more)" if more else "")
    return result(False, message, score=min(max(score, 0.0), 0.99), constraints=checks, **details)


def f1(expected, actual):
    """The F1 of two sets of entries; 1 when both are empty."""
    expected, actual = set(expected), set(actual)
    if not expected and not actual:
        return 1.0
    right = len(expected & actual)
    if not right:
        return 0.0
    precision, recall = right / len(actual), right / len(expected)
    return 2 * precision * recall / (precision + recall)
