# Near-Duplicate Report Filter

A `nanoagent.plugin/v0001` plugin with the structure of NanoAgent's reference
plugin, [arxiv-source](https://github.com/zeyuyang8/arxiv-source). Its task,
`filter-duplicates`, gives an agent a bundled corpus of short sports reports, a
shingle size and a similarity threshold. The agent must find every report that
is a redundant copy of an earlier one, a near-duplicate by word-shingle Jaccard
similarity that carries the same numbers, and say which report each one
duplicates. The answer key pins the very corpus the agent reads, and a
rule-based verifier re-derives every pair from it: 11 constraints, every one of
which must hold. Nothing leaves the machine: the data is bundled and the plugin
declares no network host.

## Tools

| Tool | Does | Code |
|---|---|---|
| `pin_duplicates` | The answer key. Pins the corpus (with its sha256), every pair's exact similarity, and the redundant and kept reports the rules give at the task's shingle size and threshold | `src/plugin/dedup.py`, `src/plugin/rules.py` |
| `list_reports` | A bundled corpus, in publication order, with its sha256 | `src/plugin/dedup.py` |
| `compare_reports` | Every pair of a corpus at a shingle size: shared and total shingles, the similarity in percent truncated to 4 decimals, and whether both texts carry the same numbers. Writes a receipt of the corpus it read to `dedup/<corpus>-k<shingle_size>.json` | `src/plugin/dedup.py` |

### Tasks

| Task | Does | Runner |
|---|---|---|
| `filter-duplicates` | Finds every redundant report and the earliest report it duplicates, and submits them with the kept reports | `agent`, with `compare_reports`; reference `pin_duplicates` |
| `list-reports` | Lists a corpus so a person can read the reports the filter judges | `tool` (`list_reports`) |

## The task

Before the agent starts, NanoAgent runs `pin_duplicates` with the task input in
a scratch workspace the agent never sees, and pins its output. The agent then
has `compare_reports` and `submit`, and two steps: `compare_reports` once with
the task's corpus and shingle size, then `submit`.

The tool computes; the agent judges. A pair is a near-duplicate when its
`similarity_percent` is at least `min_similarity_percent` (compared as given:
50.0 is at least 50, 49.9999 is not) and its `same_numbers` is true. A report
is redundant when at least one earlier report forms a near-duplicate pair with
it; its `duplicate_of` is the earliest such report and its `similarity_percent`
is that pair's value, copied exactly. Every other report is kept. Both lists
are in publication order (by published time, then id).

## Ground truth

The ground truth is the pinned corpus, never a stored answer. The rules in
`src/plugin/rules.py` (`verifier/rules.py` is a byte-for-byte copy, enforced
by a test) define everything the verifier re-derives:

- **Words** are runs of letters or digits, lower-cased. A report's **shingles**
  are its runs of `shingle_size` consecutive words; a report shorter than that
  is one shingle.
- **Similarity** is the Jaccard index of two shingle sets, an exact `Fraction`,
  reported in percent truncated to 4 decimals. The threshold is compared
  against the exact fraction, which agrees with comparing the truncated value
  to an integer threshold.
- **Numbers** are runs of digits. A pair with different number sets is never a
  near-duplicate: a corrected score, an added stat or a new date makes that
  pair no near-duplicate (the later report can still be redundant through
  another pair with an earlier report).
- **This run's receipt.** The answer key records when it was pinned and
  `compare_reports` records when it wrote its receipt, both UTC times; a
  receipt written before the answer key was pinned is an earlier run's and
  fails `agent-read`.
- **Order** is `(published, id)`. The earlier report of a qualifying pair is
  the original; the later one is redundant.
- Each bundled corpus's canonical-JSON sha256 is recorded in the rules, so a
  pinned or received corpus that is not the bundled one is refused.

The three corpora (`src/plugin/data.py`) are fictional: an invented league,
invented teams, players, outlets and scores. Each mixes exact syndicated
copies, light rewrites, updates that change a number, a three-report chain
where the third duplicates the second but not the first, and pairs that sit
exactly on a threshold (50.0 and 75.0 at shingle size 3).

## Constraints

`verifier/task.py` judges the submission against 11 constraints, in order.
Every entry of the verdict's `details.constraints` has the keys
`{id, constraint, ok, expected, actual, message}`; `ok` is `true`, `false`, or
`null` when a check it needs did not hold.

| # | id | What it checks |
|---|---|---|
| 1 | `answer-key` | The answer key is pinned for this task's corpus, shingle size and threshold |
| 2 | `answer-key-data` | The pinned corpus is the bundled one (sha256) and the pinned pairs, redundant and kept reports follow the rules on it |
| 3 | `task-echo` | The submission names the task's corpus, shingle size and threshold |
| 4 | `agent-read` | `compare_reports` was called in this run for this corpus and shingle size: its receipt holds the pinned corpus and was written after the answer key was pinned |
| 5 | `ids-known` | Every id is in the corpus, no report is listed twice, no report duplicates itself |
| 6 | `partition` | Every report is listed, as redundant or as kept |
| 7 | `redundant-complete` | Every redundant report is listed as redundant |
| 8 | `no-extra-redundant` | No kept report is listed as redundant (the message says why it is kept) |
| 9 | `duplicate-of-exact` | Each redundant report names the earliest report it duplicates |
| 10 | `similarity-exact` | Each redundant report's similarity is the pair's, as `compare_reports` gave it |
| 11 | `order` | Both lists are in publication order |

Valid only when all 11 hold, with score 1.0. Any failure among 1 to 4 scores
0; a malformed submission (5) scores 0; otherwise the score is half the F1 of
the redundant entries (an entry counts only when report, `duplicate_of` and
similarity are all right) plus half the overlap of the kept sets, at most 0.99.
Every tool call is checked as well: `verify_input` refuses a shingle size or
threshold out of range, and `verify_output` holds `compare_reports`'s pairs to
the rules applied to its own receipt and the answer key to the rules applied to
the pinned corpus.

## Limitations

- **Fixed corpora.** Only the three bundled corpora can be judged; a corpus
  the person pastes would need a hash the verifier knows.
- **The receipt is tied to the run by the clock, not by a run id.** A receipt
  written before the answer key was pinned is refused, so a receipt an earlier
  task left in the workspace no longer passes; two runs of the same input in
  the same second could still share one. A host-given run id would close that.
- **The plan is guidance.** The verdict judges the submission and the receipt,
  not how many tool calls were made: an agent that calls `compare_reports`
  twice and submits the right answer passes.
- **Shingles over words only.** Punctuation, case and hyphens are ignored, and
  a changed word that is not a number (a name, a verb) is judged by similarity
  alone.
- **Small corpora.** 8 to 10 reports each, so every pair fits one tool answer
  and the agent's reasoning; a larger corpus would need MinHash or LSH
  candidates, which this task does not use.

## Layout

```text
.
├── nanoagent.yaml   # manifest (a slimconfig ManifestConfig): id, runtime, permissions (no hosts), tools, tasks
├── contract.py      # each tool's and task's typed input and output: slimconfig Output classes
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env             # environment variable NAMEs this plugin needs (none)
├── src/plugin/      # the MCP server (__main__.py), the tools (dedup.py), the rules (rules.py) and the corpora (data.py)
├── tests/           # the rules, the tools, the data's hashes, and the verifier on gold, broken, malformed and boundary runs
├── ui/              # how the page draws the outputs: renderers.js and renderers.css (the schema drawing)
├── product/         # the product page a catalog shows: product.yaml and icon.svg
└── verifier/        # deterministic verifier: one module per tool, the task's 11 constraints in task.py
```

## Develop and run

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

NanoAgent passes the folder the plugin may write to as `NANOAGENT_WORKSPACE`.
`compare_reports` writes its receipt there, under `dedup/`, so a run that went
wrong can be read back. Run the tool task from NanoAgent with a config naming
`task: list-reports` and a JSON file `{"corpus": "week-01"}` as its
`arguments`; run the agent task with `nanoagent plugin agent` and a JSON file
such as `{"corpus": "week-02", "shingle_size": 3, "min_similarity_percent": 50}`.
