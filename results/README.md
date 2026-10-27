# Study results

`manifest.json` lists the 19 reported conditions and their evidence under `runs/`.
Each condition covers 96 development conversations. Together they contain 1,824
conversations and 10,919 attempted responses. [RUNS.md](RUNS.md) maps conditions to
API/cluster configurations, dates, model revisions, and serving details.

| Artifact | Contents |
| --- | --- |
| `records.jsonl` | Exact messages, final answers, provider responses, rules, scores, and hash identities |
| `metadata.json` | Recorded effective configuration and code/config/data hashes |
| `completion.json` | Planned/observed responses, game accounting, and skipped turns |
| `analysis.json` | Scores, per-game outcomes, survival, and paired estimates |
| `summary.csv`, `interference-summary.csv` | Turn scores and descriptive actual-state strata |
| `order-summary.csv`, `order-effects.csv`, `order-survival.csv` | Per-order outcomes, paired effects, and stage summaries |
| `events.jsonl`, `budget.json` | Request lifecycle and spending accounting |

Important record fields are `episode_id`, `turn`, `current`, `old_rules`,
`new_rule`, `raw_response`, `artifact`, `full_success`, `new_success`, `retention`,
`outcome`, `provider_response`, and `dynamic_certificate`. Null retention means no
old satisfied rules were eligible; it is excluded from retention denominators.
Separate reasoning is saved but not scored as the final answer.

Raw responses retain their bytes. Published completion paths are repository-relative;
original and published hashes and changed fields are recorded in the manifest.
The model configurations target fresh runs; exact recorded configurations remain
in metadata. Do not resume inference into a submitted evidence directory.

Use `python -m passgame.analyze` on any run's `records.jsonl`, writing to a separate
output directory. The [reproducibility guide](../docs/reproducibility.md) gives the
commands to obtain new results through an API or cluster and analyze them.
