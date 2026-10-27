# Implementation map

| Module | Responsibility |
| --- | --- |
| `constraints.py`, `audit.py` | Primary and independently implemented rule checkers |
| `generate.py` | Synthetic games, order variants, validation, file hashes, and readable references |
| `oracle.py` | Edit distances and bounded interference certificates |
| `protocol.py` | Prompts, parsing, scores, and state transitions |
| `models.py` | Chat-completions/diagnostic adapters, transport retries, and budgets |
| `run.py` | Evaluation, preflight, response caching, and evidence persistence |
| `analyze.py` | Scores, game outcomes, survival, and paired bootstrap comparisons |
| `export.py` | Readable rules and unsigned human-audit worksheet |
| `cluster.py` | Literal private deployment settings |

The evaluation uses the same chat adapter for hosted APIs and self-hosted services.
Private witnesses are available only to diagnostic algorithms. Model requests
contain conversation messages and configured decoding parameters.
