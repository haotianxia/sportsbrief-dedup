"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    PIN_DUPLICATES = "pin_duplicates"
    LIST_REPORTS = "list_reports"
    COMPARE_REPORTS = "compare_reports"


class Task(Enum):
    FILTER_DUPLICATES = "filter-duplicates"
    LIST_REPORTS = "list-reports"


class Corpus(Enum):
    WEEK_01 = "week-01"
    WEEK_02 = "week-02"
    WEEK_03 = "week-03"


CORPUS = "One of the bundled report corpora: week-01, week-02 or week-03"
SHINGLE = "Words per shingle, 1 to 5: each report becomes the set of its runs of this many consecutive words"
THRESHOLD = "The least similarity, in percent (1 to 100), at which two reports count as near-duplicates"
REPORT_ID = "A report's id as the corpus lists it, e.g. r03"
PERCENT = "Jaccard similarity of the two reports' shingle sets, in percent, truncated (never rounded) to 4 decimals"
STAMP = "When the report was published, a UTC time YYYY-MM-DDTHH:MM:SSZ"


@dataclass
class DedupInput(Output):
    corpus: Annotated[Corpus, CORPUS]
    shingle_size: Annotated[int, SHINGLE]
    min_similarity_percent: Annotated[int, THRESHOLD]


@dataclass
class Report(Output):
    id: Annotated[str, REPORT_ID]
    published: Annotated[str, STAMP]
    source: Annotated[str, "The outlet that published it"]
    text: Annotated[str, "The report's text"]


@dataclass
class Pair(Output):
    first: Annotated[str, "The earlier report's id (the smaller id when both were published at the same time)"]
    second: Annotated[str, "The later report's id"]
    shared: Annotated[int, "How many shingles the two reports share"]
    total: Annotated[int, "How many distinct shingles the two reports have together"]
    similarity_percent: Annotated[float, PERCENT]
    same_numbers: Annotated[
        bool, "Whether both texts carry the same set of numbers (runs of digits): a changed score, date or count makes it false"
    ]


@dataclass
class Redundant(Output):
    report: Annotated[str, "The redundant report's id"]
    duplicate_of: Annotated[str, "The earliest earlier report it is a near-duplicate of"]
    similarity_percent: Annotated[float, "Their similarity_percent, exactly as compare_reports gave it"]


@dataclass
class DedupOutput(Output):
    corpus: Annotated[Corpus, "The task's corpus, as given"]
    shingle_size: Annotated[int, "The task's shingle size, as given"]
    min_similarity_percent: Annotated[int, "The task's threshold, as given"]
    redundant: Annotated[list[Redundant], "Every redundant report, in publication order; [] for none"]
    kept: Annotated[list[str], "Every other report's id, in publication order"]


@dataclass
class PinOutput(Output):
    corpus: Annotated[Corpus, CORPUS]
    shingle_size: Annotated[int, SHINGLE]
    min_similarity_percent: Annotated[int, THRESHOLD]
    pinned_at: Annotated[str, "When the answer key was pinned, a UTC time YYYY-MM-DDTHH:MM:SSZ: a receipt written earlier is another run's"]
    corpus_sha256: Annotated[str, "sha256 of the corpus's canonical JSON"]
    reports: Annotated[list[Report], "The corpus, in publication order"]
    pairs: Annotated[list[Pair], "Every pair of reports with its similarity, ordered by first then second"]
    redundant: Annotated[list[Redundant], "The redundant reports the rules give, in publication order"]
    kept: Annotated[list[str], "The reports kept, in publication order"]


@dataclass
class ListInput(Output):
    corpus: Annotated[Corpus, CORPUS]


@dataclass
class ListOutput(Output):
    corpus: Annotated[Corpus, CORPUS]
    corpus_sha256: Annotated[str, "sha256 of the corpus's canonical JSON"]
    reports: Annotated[list[Report], "The corpus, in publication order"]


@dataclass
class CompareInput(Output):
    corpus: Annotated[Corpus, CORPUS]
    shingle_size: Annotated[int, SHINGLE]


@dataclass
class Stamp(Output):
    id: Annotated[str, REPORT_ID]
    published: Annotated[str, STAMP]
    source: Annotated[str, "The outlet that published it"]


@dataclass
class CompareOutput(Output):
    corpus: Annotated[Corpus, CORPUS]
    shingle_size: Annotated[int, SHINGLE]
    corpus_sha256: Annotated[str, "sha256 of the corpus's canonical JSON"]
    reports: Annotated[list[Stamp], "Every report's id, publication time and source, in publication order"]
    pairs: Annotated[list[Pair], "Every pair of reports with its similarity, ordered by first then second"]


TOOLS = {
    Tool.PIN_DUPLICATES: (DedupInput, PinOutput),
    Tool.LIST_REPORTS: (ListInput, ListOutput),
    Tool.COMPARE_REPORTS: (CompareInput, CompareOutput),
}
TASKS = {
    Task.FILTER_DUPLICATES: (DedupInput, DedupOutput),
    Task.LIST_REPORTS: (ListInput, ListOutput),
}
