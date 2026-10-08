# PassGame

A synthetic, deterministically checked benchmark for constraint-preserving string repair. LLMs receive one new rule per conversation turn and generate every intermediate password themselves. Matched offline cases certify interference with one, two or three old rules; native trajectories and fixed-order permutations measure behavior on the model's own states.

## Reproduce the validation

```sh
uv sync --locked
uv run --locked pytest
uv run --locked python -m passgame.run --config configs/experiment.yaml
```

The checked-in default uses three **diagnostic algorithms**, not language models: a reference witness, an unchanged-string baseline, and a one-edit new-rule-only baseline. None calls an external service. Run experimental evaluations through the project's experiment launcher; these commands document the fixed recipe and local tests.

## Dataset and semantics

`data/manifest.json` records dataset hashes, split sizes and audit status. Version 2 has 32 development pairs and 160 held-out pairs across six families. The original four use 3/5/8 active rules; two-rule numeric interference uses 5/8, and three-rule numeric interference uses 6/8. Each pair has independent and interfering states under identical constraints. The 60 held-out native episodes and 80 order variants have eight turns each and include all six families. Controlled prefixes are offline scripted diagnostics; configuration validation forbids them for LLM adapters. Native initial strings are `seed0!` and `seed9!`, shared across models per instance.

The interference degree is the minimum number of old rules broken across **every shortest edit satisfying only the new rule**. Certificates record minimum/maximum breakage, a count histogram, affected rule IDs, and a minimum-break witness. All focal new-only distances are one; independent full distances are one and interfering full distances are two. Additional affected rules do not automatically require additional edits. The multi-rule families use distinct digit-count, sum, character-count, length and adjacency constraints.

Strings use ASCII letters/digits and `!_-()[]`, length 1–32. Matching is case sensitive; positions are one-based; all digit occurrences count in digit sums. Substring counts include overlaps. Balanced-bracket semantics are implemented and tested but bracket-specific generated cases are deferred. Unit edit distance permits insertion, deletion and substitution. The generator certifies one-edit new-only distance and full distance one or two. Unknown search outcomes are never labeled interfering.

`src/passgame/audit.py` independently reimplements checks. Automated exhaustive checks supplement a planned human audit; they do not impersonate one. `data/audit-sample.jsonl` provides 20 stratified examples for that review. Held-out API evaluation refuses to start until the manifest records a completed human audit.

## Evaluate actual models

Use `configs/pilot.example.yaml` on a child experiment, fill exact model IDs, endpoint, verified pricing, token limits and the agreed spending ceiling, and store credentials in the named environment variable. Pilot on development data before freezing the main model configurations. The adapter supports the chat-completions request schema; other providers require a compatible endpoint or a new, tested adapter. The schema follows the [official API reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create).

LLM configurations must select only `native` and/or `order`. Each user message supplies the current password and exactly one new rule. Earlier rules remain in their original conversation messages; the runner never repeats a cumulative list. All assistant turns are the model's actual responses, including incorrect responses. Rule lists, certificates and final witnesses are retained privately by the evaluator and never sent to the provider. The default `controlled` track and legacy `fresh` track are diagnostic-only and fail preflight if selected for a chat adapter.

For open-weight models on an SSH machine, use `configs/ssh-pilot.example.yaml` and `docs/ssh-evaluation.md`. Run the evaluator in the remote execution environment and point it at that environment's compatible model server. `deployment: self_hosted` with explicit zero token prices permits `budget_usd: 0`; that ledger tracks API token spend rather than GPU accounting. API credentials are optional when the server has authentication disabled. Development pilots are allowed immediately; the existing human-review requirement still applies to held-out model evaluation.

```sh
uv run --locked python -m passgame.run --config configs/experiment.yaml --preflight
```

Preflight verifies data hashes, certificates, model configuration and credential presence without sending requests. No credentials, model choices or provider prices are inferred. Provider-enforced JSON mode and tool use are disabled. The response must be exactly `{"password":"..."}`. Wrong semantic answers, malformed answers and token-truncated answers are scored once. Only transient transport/HTTP failures are retried, under a fixed cap.

Parsed domain-valid strings become the next state even when they violate a rule. Format/domain failures preserve the previous state and still count as failed turns. Infrastructure failures stop that episode and remain missing evidence. Retention covers only old rules satisfied by the incoming artifact and is undefined when none were satisfied. All-old validity is reported separately. Valid full rewrites count as success.

The budget reserves the configured conservative prompt-token bound and completion cap for every attempt, including retries; reservations are persisted and never refunded. This is intentionally conservative and depends on correct, verified provider pricing and token-bound assumptions. It is not a replacement for provider-side account limits. Interrupted paid requests with unknown outcomes block automatic replay. Cached responses are isolated by code/data/config/request hashes. Inspect `budget.json`, `events.jsonl`, and `records.jsonl` together when resuming.

Evidence includes exact prompts, raw provider responses, before/after checks, state-relative certificates, model configuration, usage, hashes, and failure status. `analysis.json` and `summary.csv` report denominators and paired bootstrap intervals; turns and order permutations are not treated as independent scenario blocks. Intervals are descriptive; no confirmatory p-values or equivalence claims are produced.

`old_rules_broken` counts previously satisfied rules newly violated by a valid response; `newly_violated_old_rule_ids` identifies them. Invalid responses have unknown breakage counts rather than zero. `interference-summary.csv` stratifies offline diagnostics by intended degree, and model trajectories by the degree certified from the actual incoming state. Incoming states already violating old rules remain `unknown` for full-set distance certification; observable regressions are still scored. On-policy interference strata are descriptive, not paired controlled H1 effects. See `docs/preregistration.md` for the revised design.

## Limits of this release

The six interaction families are parameterized templates; new-parameter success does not establish unseen-template generalization. Additional old rules constrain the same artifact but some are easy or redundant, so active-rule count is not a calibrated information-complexity scale. Interference-degree comparisons across templates can include family and load differences. A model may avoid a certified interfering artifact through its own choices; the generator cannot guarantee the same interference degree along autonomous trajectories. Order contrasts measure a total order effect, including different intermediate repair loads. The reference algorithm sees a supplied witness and is only an upper-bound diagnostic. The new-only baseline searches radius one, prefers same-length candidates, then breaks ties lexicographically, without inspecting old rules.

## Files

- `src/passgame/constraints.py`, `audit.py`, `oracle.py`: semantics and certificates.
- `src/passgame/generate.py`: reproducible dataset construction.
- `src/passgame/protocol.py`, `models.py`, `run.py`: prompts, adapters, evidence and state transitions.
- `src/passgame/analyze.py`: blocked paired estimates and trajectory summaries.
- `docs/preregistration.md`: frozen design and inference scope.
- `tests/`: exhaustive, boundary, protocol, budget and missing-evidence checks.

Regenerate the dataset during preparation with `uv run --locked python -m passgame.generate --output data`. This overwrites data and resets human audit status; never regenerate a frozen evaluated experiment in place.
