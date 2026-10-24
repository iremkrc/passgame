# PassGame

PassGame is a synthetic benchmark for **preserving accumulated constraints while updating a string**. An LLM receives one new rule per conversation turn and produces the next password itself. A deterministic evaluator checks whether the response satisfies the new rule and preserves earlier rules.

For experiment definitions and step-by-step local/Galvani commands, read the [experiment and run guide](docs/experiment-guide.md).

The central question is whether a model can coordinate repairs when the easiest change for a new rule would break several old rules. The current **version 3** suite uses simple starting strings and eight progressive rules, with validated example interference challenges at turns 3–5. Version 2 focal pairs and historical studies remain unchanged.

## Contents

- [Implementation status](#implementation-status)
- [Quick start](#quick-start)
- [Repository map](#repository-map)
- [Sequential model protocol](#sequential-model-protocol)
- [String domain and rule language](#string-domain-and-rule-language)
- [Interference and distance certificates](#interference-and-distance-certificates)
- [Dataset and evaluation tracks](#dataset-and-evaluation-tracks)
- [Running an LLM evaluation](#running-an-llm-evaluation)
- [Configuration reference](#configuration-reference)
- [Scores and analysis](#scores-and-analysis)
- [Outputs, caching, and resumption](#outputs-caching-and-resumption)
- [Inspecting rules and completing the audit](#inspecting-rules-and-completing-the-audit)
- [Development and reproducibility](#development-and-reproducibility)
- [Troubleshooting](#troubleshooting)
- [Research limitations](#research-limitations)

## Implementation status

| Component | Status |
| --- | --- |
| Deterministic rule checker and independent audit checker | Implemented |
| Version 2 dataset and exact focal distance certificates | Generated and automatically validated |
| Multiple-rule interference | Certified degree-two and degree-three families included |
| Sequential native/order conversations | Implemented; each new user message introduces exactly one rule |
| Progressive `seeded` conversations | Implemented; neutral initial once, actual successful outputs, first-failure termination |
| Diagnostic algorithms and analysis | Implemented and exercised in a completed validation run |
| Chat-completions adapter and self-hosted configuration | Implemented |
| Human audit of the held-out sample | Pending in the checked-in manifest |
| Actual LLM evaluation | Historical Qwen pilots completed; the corrected v3 model pilot is pending |
| Galvani GPU serving environment and exact model selection | Qwen runtime prepared; reproducible packaging and explicit model-weight selection implemented |

The completed version 2 diagnostic validation produced 4,320 records, including 3,360 native/order requests, with zero API spending. The diagnostic contracts and sequential-disclosure checks passed. These checks establish behavior of the benchmark implementation and its algorithms; they do not measure an LLM.

The checked-in [default configuration](configs/experiment.yaml) still selects diagnostic algorithms. The [provider pilot](configs/pilot.example.yaml) and [SSH pilot](configs/ssh-pilot.example.yaml) are templates with model choices still to fill in. Dataset versions `2`/`3` and Python package version `0.1.0` are separate version numbers.

## Quick start

Run commands from the repository root. The evaluator requires **Python 3.11 or newer** and uses `uv` with the committed [lockfile](uv.lock). GPU libraries are separate from the evaluator's lightweight dependencies.

```sh
# Install the locked evaluator and development dependencies.
uv sync --locked

# Check the implementation.
uv run --locked pytest

# Validate the default data/configuration without model requests.
uv run --locked python -m passgame.run \
  --config configs/experiment.yaml --preflight
```

The fixed evaluation recipe is:

```sh
uv sync --locked && uv run --locked python -m passgame.run --config configs/experiment.yaml
```

Launch recorded experiments through the project's experiment launcher, which executes this recipe from a committed source snapshot. Keep model studies on their own preparation/experiment branch and commit their configuration before launch. Local tests and preflight can use the worktree; an experimental result should be tied to the recorded snapshot.

With the current default configuration, the recipe makes **no external model calls**. It evaluates three diagnostic algorithms on the test split and writes to `outputs/multi-rule-sequential-validation/`. See [running an LLM evaluation](#running-an-llm-evaluation) to configure actual inference.

## Repository map

| Path | Purpose |
| --- | --- |
| [pyproject.toml](pyproject.toml), [uv.lock](uv.lock) | Package metadata, dependencies, and dependency lock |
| [configs/experiment.yaml](configs/experiment.yaml) | Configuration read by the fixed evaluation command |
| [configs/pilot.example.yaml](configs/pilot.example.yaml) | Paid/provider development-pilot template |
| [configs/ssh-pilot.example.yaml](configs/ssh-pilot.example.yaml) | Open-weight, self-hosted development-pilot template |
| [configs/dev-qwen2.5-7b-fixed-start.yaml](configs/dev-qwen2.5-7b-fixed-start.yaml) | Open-weight pilot with the same predefined initial strings across models |
| [configs/dev-qwen2.5-7b-eight-rules.yaml](configs/dev-qwen2.5-7b-eight-rules.yaml) | Current v3 pilot: neutral starts, progressive eight-rule games, reminders and first-failure termination |
| [data/sequential-v3/development-games.txt](data/sequential-v3/development-games.txt) | All 24 individual pilot games, starting strings, rules, and private example paths |
| [src/passgame/sequential.py](src/passgame/sequential.py) | Version-3 generation, validation, and readable references |
| [scripts/package_pilot.py](scripts/package_pilot.py) | Build the Galvani snapshot from a clean checkout |
| [data/manifest.json](data/manifest.json) | Dataset version, hashes, counts, validation, and human-audit status |
| [data/pairs.jsonl](data/pairs.jsonl) | Matched independent/interfering offline cases and certificates |
| [data/episodes.jsonl](data/episodes.jsonl) | Native and order episodes, initial strings, ordered rules, and private witnesses |
| [data/audit-sample.jsonl](data/audit-sample.jsonl) | Twenty paired cases selected for human review |
| [src/passgame/constraints.py](src/passgame/constraints.py) | Primary rule representation, descriptions, and checks |
| [src/passgame/audit.py](src/passgame/audit.py) | Separately implemented rule checks for automated cross-checking |
| [src/passgame/oracle.py](src/passgame/oracle.py) | Edit distance, full one-edit neighborhoods, and certificates |
| [src/passgame/generate.py](src/passgame/generate.py) | Dataset generation, validation, and manifest verification |
| [src/passgame/protocol.py](src/passgame/protocol.py) | Prompts, strict output parsing, scoring, and state transitions |
| [src/passgame/models.py](src/passgame/models.py) | Diagnostic/chat adapters, transport handling, and budget ledger |
| [src/passgame/run.py](src/passgame/run.py) | Preflight, evaluation, request caching, and evidence persistence |
| [src/passgame/analyze.py](src/passgame/analyze.py) | Scores, paired bootstrap contrasts, and episode summaries |
| [src/passgame/export.py](src/passgame/export.py) | Readable rules CSV, rule guide, and unsigned audit worksheet |
| [docs/preregistration.md](docs/preregistration.md) | Version 2 design and interpretation of research endpoints |
| [docs/audit-instructions.md](docs/audit-instructions.md) | Human review and signoff procedure |
| [docs/ssh-evaluation.md](docs/ssh-evaluation.md) | SSH execution layout and serving provenance requirements |
| [tests/](tests/) | Semantics, certificates, protocol, adapter, budget, and runner checks |

`outputs/` and `.venv/` are ignored by Git. Credentials belong in environment variables; `.env` is ignored but is **not automatically loaded** by the runner.

## Sequential model protocol

A v3 `seeded` episode starts from its explicit neutral `initial` string, such as `abc1`. Legacy v2 native/order episodes use `seed0!` or `seed9!`. Each turn proceeds as follows:

1. Append a user message containing the current string and **one new rule**. In the main reminder condition, also list every previously introduced rule with its original ID and description.
2. Send the system message and the complete original conversation history to the model.
3. Parse and score the model's response against the cumulative rules privately.
4. If every active rule passes, carry the returned string and exact response into the next turn. Otherwise save the failed response and terminate the conversation before revealing another rule.

The main pilot sets `remind_previous_rules: true`. Each latest message repeats the exact earlier rules under `Previous rules (still binding)` and introduces one new rule. Future rules, witnesses, and certificates are not disclosed. Full original history and actual assistant responses are retained. Only outputs satisfying every active rule advance to the next stage; a rule, format, or domain failure ends the episode. The current `seeded` track standardizes only the initial string; historical `fixed_start` uses the v2 focal-state starts. Because the endpoint is stateless, the client resends the original history on each request.

The optional history-only comparison sets `remind_previous_rules: false`; omitted settings also default to false for compatibility with earlier configurations. In that condition, earlier rules appear only in their original user turns. Configurations, record protocol versions, and output directories distinguish the conditions; do not pool their scores.

For example, the latest user message can be:

```text
Current string: "x2e!hau3"
Previous rules (still binding):
r1: There must be exactly 2 ASCII digits.
r2: The sum of all digit occurrences must be at most 5.

New rule: r3: Length must be exactly 9 characters.
Return the updated string satisfying all active rules as JSON.
```

The model must satisfy both the previous rules and the new rule. The required response is a JSON object with exactly one string field:

```json
{"password":"x2e!hau3_"}
```

The evaluator accepts **any** domain-valid string satisfying the active constraints. It does not require the stored witness, a particular repair, or a minimum number of edits. Full rewrites are allowed.

### Parsing and state transitions

| Response/event | Score and next state |
| --- | --- |
| Valid JSON, allowed string, all active rules satisfied | Full success; use the returned string next turn |
| Valid JSON and allowed string, but any old or new rule is violated | Semantic failure; record the answer and terminate the episode |
| Invalid JSON, duplicate keys, extra fields, wrong type, prose, or Markdown fences | Format failure; record the answer and terminate the episode |
| JSON with an empty, overlong, whitespace-containing, or otherwise out-of-domain string | Domain failure; record the answer and terminate the episode |
| Transport/provider infrastructure failure after allowed retries | Missing evidence; stop that episode without fabricating an assistant turn |

Outer whitespace around JSON is allowed. Whitespace inside the password is forbidden. JSON escapes are decoded before domain checks. Incorrect, malformed, and truncated model answers are scored once and retained in evidence; there is no semantic retry, corrective feedback, or subsequent stage after a failed answer. Terminal failures have `next_state: null` and record `episode_end_reason`.

The chat request contains the model ID, messages, `stream: false`, and configured decoding parameters. Full rule lists, certificates, and witnesses are evaluator data and are not additional request fields. Provider-enforced JSON mode, tools, and tool-assisted solving are disabled. See [protocol.py](src/passgame/protocol.py) and [models.py](src/passgame/models.py) for the exact contract.

## String domain and rule language

Strings contain 1–32 characters drawn from ASCII letters `a-z`, `A-Z`, digits `0-9`, and:

```text
!_-()[]
```

Matching is case sensitive. Positions are **one-based**. Digit count and digit sum include every ASCII digit occurrence, including repeated digits. There is no Unicode normalization or whitespace in the password.

Rules have a unique `id`, a `kind`, and a `value`. Numeric comparisons use `op: eq`, `le`, or `ge`, meaning exactly, at most, or at least; the default is `eq`. Character/substr counts use the additional `count` field, and positional rules use `position`.

| Kind | Meaning | Example JSON |
| --- | --- | --- |
| `length` | Compare total character count | `{"id":"len","kind":"length","value":4}` |
| `digit_count` | Compare number of ASCII digits | `{"id":"digits","kind":"digit_count","value":4}` |
| `digit_sum` | Compare sum of all digit occurrences | `{"id":"sum","kind":"digit_sum","value":24,"op":"le"}` |
| `char_count` | Compare occurrences of one character | `{"id":"ones","kind":"char_count","value":"1","count":1}` |
| `substring_count` | Compare occurrences of a substring, including overlaps | `{"id":"aa","kind":"substring_count","value":"AA","count":3}` |
| `contains` | Require a case-sensitive substring | `{"id":"pattern","kind":"contains","value":"91"}` |
| `forbids` | Require a case-sensitive substring to be absent | `{"id":"ban","kind":"forbids","value":"AB"}` |
| `char_at` | Require a character at a one-based position | `{"id":"new","kind":"char_at","value":"8","position":4}` |
| `balanced` | Require proper nesting for a selected bracket vocabulary | `{"id":"brackets","kind":"balanced","value":"()[]"}` |

`contains`, `forbids`, `char_at`, and `balanced` use only `op: eq`. A position beyond the string's length fails. For overlapping counts, `AAAA` contains three occurrences of `AA`. A balanced rule accepts `()`, `[]`, or `()[]` as its vocabulary and ignores other characters; with both bracket types selected, `([)]` fails.

All nine rule kinds are implemented. The current generated dataset uses six interaction families; a bracket-specific generated family is deferred. Rule support and dataset coverage are distinct.

## Interference and distance certificates

Edit distance is unit-cost Levenshtein distance: one insertion, deletion, or substitution costs one. Swapping characters is not a primitive edit.

For an incoming string that satisfies every old rule:

- **New-only distance**, `d_new`, is the fewest edits needed to satisfy the new rule alone.
- **Full distance**, `d_full`, is the fewest edits needed to satisfy all old rules and the new rule together.
- **Interference degree** is the minimum number of distinct old rules broken across all shortest new-only repairs. A certified degree of `k` means every such repair breaks at least `k` old rules, and at least one breaks exactly `k`.

The failing rule IDs can vary between shortest repairs. Degree is a guaranteed count of broken old rules, not necessarily a common set of `k` rule IDs and not the edit distance of the full repair.

### How labels are certified

The checker exhaustively enumerates distinct, domain-valid strings at distance one, including insertions and deletions.

| Label | Condition and certificate |
| --- | --- |
| `no_op` | The incoming string satisfies old and new rules already; `d_new = d_full = 0` |
| `independent` | At least one one-edit string satisfies all active rules; `d_new = d_full = 1` |
| `interfering` | At least one one-edit string satisfies the new rule, none satisfies all rules, and a verified full-valid witness is exactly two edits away; `d_new = 1`, `d_full = 2` |
| `unknown` | Incoming old-rule validity fails, or the bounded search/witness does not prove the exact full distance |

The two-edit witness proves an upper bound; the complete one-edit search proves the matching lower bound. Native/order certificates search adaptively from the actual incoming string using only the currently active rules. They do not use the episode's fixed final witness. The search tries second edits from new-valid one-edit neighbors first, then other one-edit neighbors, because a valid two-edit repair may satisfy the new rule only after its second edit. It checks at most 100,000 distinct radius-two candidates per call. Offline dataset validation can still supply a known witness as a hint, which is accepted only after checking its validity and distance from the incoming string.

The checker does not search arbitrary distances. `search_complete: true` means the **radius-one neighborhood** was completely searched. Adaptive searches also record `witness_search_candidates` and `witness_search_status` (`found`, `candidate_limit`, or `exhausted`). Reaching the candidate limit or exhausting radius two without a witness leaves the exact full distance unknown; it does not prove unsatisfiability. Unknown outcomes are never relabeled interfering merely because a repair was not found.

Independent means a safe shortest repair **exists**. It does not mean every shortest new-only repair is safe, so a greedy new-only algorithm can still choose an unsafe repair in an independent case.

### Example: one old rule affected

Old rules require exactly two digits and a digit sum at most 11. The new rule requires `8` somewhere in the string.

| Condition | Incoming | Repair satisfying only the new rule | Repair satisfying all rules | New-only/full distance |
| --- | --- | --- | --- | --- |
| Independent | `A29x!` | `A28x!` | `A28x!` | `1 / 1` |
| Interfering | `A47x!` | `A48x!` breaks the sum budget | `A38x!` | `1 / 2` |

For the interfering input, substituting `8` for an existing digit exceeds the sum budget; inserting `8` also violates the exact digit count. A coordinated two-edit repair satisfies both old constraints.

### Example: two old rules affected

Old rules require exactly three digits, a digit sum at most 15, exactly one `1`, and length three. The new rule requires `8` at position three.

| Incoming | One-edit repair | Old rules broken | Full-valid repair |
| --- | --- | --- | --- |
| Independent `159` | `158` | None | `158`, one edit |
| Interfering `591` | `598` | Sum budget and count of `1` | `518`, two edits |

The alternative one-edit insertion `5981` breaks three old rules: digit count, length, and sum. Considering **all** shortest repairs gives minimum breakage two and maximum three.

### Example: three old rules affected

Old rules require exactly four digits, a digit sum at most 24, exactly one `1`, length four, and substring `91`. The new rule requires `8` at position four.

| Incoming | One-edit repair | Old rules broken | Full-valid repair |
| --- | --- | --- | --- |
| Independent `9159` | `9158` | None | `9158`, one edit |
| Interfering `5991` | `5998` | Sum budget, count of `1`, and required `91` | `5918`, two edits |

Inserting instead gives `59981`, breaking four old rules. The certified minimum is three. Only the sum and substring rules fail under every shortest repair; other failed IDs vary. Thus the intersection of affected IDs can have size two even when the guaranteed minimum count is three.

The main pilot repeats the previously introduced rules in each latest-turn prompt, alongside one new rule, as described in the [protocol](#sequential-model-protocol). The optional history-only comparison leaves those rules in their original conversation turns.

### Certificate and worksheet column glossary

| Field or column | Meaning |
| --- | --- |
| `d_new` / New-only distance | Minimum edits satisfying only the new rule |
| `d_full` / Full distance | Minimum edits satisfying the complete active rule set |
| New-only/full distance, such as `1 / 2` | The two distances above, in that order |
| `one_edit_candidates` | Number of distinct domain-valid strings exactly one edit away |
| `one_edit_new_valid` | Number of those strings satisfying the new rule |
| `one_edit_full_valid` / Full-valid one-edit candidates | Number satisfying every old rule and the new rule |
| `min_old_rules_broken`, `max_old_rules_broken` | Minimum/maximum old-rule failures over all shortest new-only candidates |
| `old_rules_broken_histogram` | Mapping from broken-rule count to number of shortest candidates with that count; JSON keys are strings |
| `min_break_witness` / Minimum-break repair | One shortest new-only repair attaining the minimum breakage; it may violate old rules |
| `min_break_rule_ids` / Broken rule IDs | Old rules failed by that particular minimum-break repair |
| `possibly_affected_old_rule_ids` | Union of failed old-rule IDs over all shortest new-only repairs |
| `necessarily_affected_old_rule_ids` | Intersection of those failed-ID sets |
| `witness` / Full witness | An example string satisfying all active rules, used to certify the upper bound |
| `search_complete` | Whether radius-one enumeration was complete; not a global search-completeness claim |

Certificates describe the incoming state and candidate space. The separate response metric `old_rules_broken` measures what the evaluated model actually broke.

## Dataset and evaluation tracks

The authoritative sizes and SHA-256 hashes are in [data/manifest.json](data/manifest.json). Version 2 preserves the original four template families and appends two multiple-rule families.

| Family | Offline interfering degree | Active-rule counts |
| --- | ---: | --- |
| `numeric` | 1 | 3, 5, 8 |
| `position_count` | 1 | 3, 5, 8 |
| `substring_position` | 1 | 3, 5, 8 |
| `forbidden_position` | 1 | 3, 5, 8 |
| `numeric_multi_2` | 2 | 5, 8 |
| `numeric_multi_3` | 3 | 6, 8 |

Load counts the old rules **plus the new rule** in an offline case. Additional rules can be easy or redundant; load is not a calibrated complexity scale. The multiple-rule guarantees come from distinct predicates, rather than duplicate copies of one rule.

### Historical version-2 split sizes and request counts

| Item | Development | Held-out test | Total |
| --- | ---: | ---: | ---: |
| Matched offline pairs | 32 | 160 | 192 |
| Focal states: two per pair | 64 | 320 | 384 |
| Degree-one pairs | 24 | 120 | 144 |
| Degree-two pairs | 4 | 20 | 24 |
| Degree-three pairs | 4 | 20 | 24 |
| Native episodes | 12 | 60 | 72 |
| Order episodes | 24 | 80 | 104 |
| Native requests per model | 96 | 480 | 576 |
| Order requests per model | 192 | 640 | 832 |
| Combined native/order requests per model | **288** | **1,120** | **1,408** |
| Eight-rule pairs in the historical fixed-start subset | **12** | **60** | **72** |
| Eight-rule fixed-start games per model | **24** | **120** | **144** |
| Eight-rule fixed-start requests per model, maximum | **192** | **960** | **1,152** |

The historical fixed-start configuration sets `rule_count: 8`, selecting cases and episodes by their actual rule-list length. Native/order episodes already have eight scheduled turns. Every selected fixed-start game also has eight scheduled rules; earlier failure can still end it before turn eight. Request counts are upper bounds, and transport retries can cause additional HTTP attempts. The versioned dataset retains its other rule counts for historical reproducibility, but they are excluded from the current pilot.

Base scenarios are disjoint across development/test, and variants remain in the same split. Offline pair members share the same old/new constraints and input length. Multiple-rule pairs also match character multiplicities. Final witnesses establish that every episode prefix is satisfiable.

### Track definitions

| Track | What it evaluates | Available to chat models? |
| --- | --- | --- |
| `native` | Eight sequential turns starting from shared initial strings; every intermediate response comes from the evaluated model | Yes |
| `order` | The same final constraint sets under original, reverse, and two seeded random orders, each with the same initial string | Yes |
| `seeded` | V3 neutral seed followed by eight progressive rules and actual model responses | Yes; current main track |
| `fixed_start` | Historical v2 focal-state starts; first seven rules are initially satisfied | Yes; historical comparison only |
| `controlled` | Matched focal independent/interfering states with scripted offline prefixes; one recorded focal response per state | No; diagnostic only |
| `fresh` | Legacy all-at-once solving diagnostic | No; diagnostic only, absent from the default configuration |

The test native suite uses 30 base sets with two initial strings per set. The test order suite uses 20 final sets with four permutations per set. Actual interference in a native/order episode is recomputed from the model's incoming string; an offline template label is not copied onto its trajectory.

### Progressive eight-rule evaluation (version 3)

The current [configuration](configs/dev-qwen2.5-7b-eight-rules.yaml) selects `dataset_dir: data/sequential-v3`, `tracks: [seeded]`, `rule_count: 8`, and `remind_previous_rules: true`.

There are **24 distinct development games**, four per family, and **120 held-out games**, twenty per family. These are individual episodes, not 12 independent/interfering pairs. Each game has a simple neutral seed shared across models and eight fixed rules. The first rule requires a change from the seed. Reference paths require a repair at every turn and prove that every prefix is satisfiable; the final witness also satisfies every rule. Example challenge degrees one/two/three appear by turns 3/4/5. These are conditional proofs about the private reference paths, not guaranteed labels for actual model trajectories.

[Read all 24 pilot games](data/sequential-v3/development-games.txt). Game 1 starts at `abc1` and has the possible path `abc12 → abc47 → abc38 → abc38_ → abc38! → Xbc38! → XAc38! → XAc83!`. Interference is certified at turns 3 and 8 on that example path. Reference outputs, witnesses and certificates are never supplied as LLM assistant replies or required answers.

Only actual successful model outputs advance the state. The current string, exact original conversation, earlier rule reminders, and one new rule are sent each turn. Any rule, format or domain failure is recorded once and ends the game before another rule is introduced. There are no resets, semantic retries or oracle repairs. Every attempted input is certified independently; a model can already satisfy a planned challenge. Record actual no-op, independent, interfering and unknown coverage and do not assign persistent independent/interfering labels to games. All v3 rows use `phase: sequential`; the final turn is not the sole focal step.

Maximum requests per model are **192 development** and **960 held-out**. The v3 dataset also contains original/reverse/two random order variants of each game: selecting `order` instead gives 96 development or 480 held-out games. Each permutation retains the same initial string and final rule set. Use a distinct configuration and output directory for order evaluation. The held-out human-audit gate remains pending; v3 has its own 12-game audit sample.

The ready [order-sensitivity configuration](configs/dev-qwen2.5-7b-v3-order.yaml) runs all four orders (96 development games, at most 768 requests). It is supported by the Galvani packager:

```sh
uv run --locked python scripts/package_pilot.py --config configs/dev-qwen2.5-7b-v3-order.yaml
bash run-pilot.sh --check
bash run-pilot.sh --new
```

The order run writes to `outputs/dev-qwen2.5-7b-v3-order/` within its snapshot. `order-summary.csv` reports success and mean successful prefix length per order; `order-survival.csv` reports stage-by-stage reach; `order-effects.csv` compares original against reverse and each random variant for success and completed turns, paired by final rules, initial string and horizon. Progress excludes the failed terminal turn; incomplete infrastructure histories are counted separately and excluded from paired estimates. Original-versus-reverse is primary, with random comparisons as secondary descriptive checks. See the [run guide](docs/experiment-guide.md#rule-order-experiment).

Regenerate the checked-in suite and export references:

```sh
uv run --locked python -m passgame.sequential --output data/sequential-v3
uv run --locked python -m passgame.export --dataset data/sequential-v3 --output outputs/readable-v3
```

With a compatible server already running:

```sh
uv run --locked python -m passgame.run --config configs/dev-qwen2.5-7b-eight-rules.yaml --preflight
uv run --locked python -m passgame.run --config configs/dev-qwen2.5-7b-eight-rules.yaml
```

For cluster execution, copy `configs/cluster.example.env` to the git-ignored `configs/cluster.local.env` and fill in machine-specific values privately. Shared source and documentation use placeholders. The private file is excluded from source snapshots; generated runtime settings and run artifacts should remain private.

To build and launch on Galvani from a configured checkout:

```sh
uv run --locked python scripts/package_pilot.py
bash run-pilot.sh --check
bash run-pilot.sh --new
```

Packaging creates a fresh Git snapshot, runs its preflight, includes the tracked batch wrapper and records code/config/data hashes. Ignored archives are reconstructed locally, not prerequisites for cloning. Old snapshots and job state remain preserved. A changed snapshot requires `--new`; running without it resumes monitoring the matching saved job. The default Qwen weights and container must already be prepared on Galvani. For other models, pass a copied configuration with a unique model name/output plus `--model-dir /absolute/remote/weights --model-revision REVISION` to the packager. Merely changing the model ID does not switch weights.

The [no-reminder configuration](configs/dev-qwen2.5-7b-eight-rules-no-reminders.yaml) uses the same v3 games and model settings in a separate output directory. Run it directly against an existing endpoint; the packaged launcher supports `seeded` or `order` with reminders enabled.

**Historical design correction (2026-10-24):** v2 `fixed_start` reused certified pre-repair focal states as episode starts. Those states already satisfied the first seven rules. Its earlier 24-game reminder study, job 2996659, is preserved as evidence for that older design. [The historical config](configs/dev-qwen2.5-7b-prevalidated-starts.yaml), original data and frozen snapshots remain available. V3 replaces this initialization design and writes to `outputs/dev-qwen2.5-7b-progressive-eight-rules-v3/`. Neither historical reset results nor prevalidated-start results are merged with the new study. The earlier reset protocol was also an incorrect interpretation of shared initial strings; it remains explicitly labelled `legacy_reset` by historical reanalysis.

### Diagnostic algorithms

- `reference_oracle` returns a privileged valid witness. For v3 seeded diagnostics it follows the private reference path, one valid example per turn; for legacy/order diagnostics it returns the full-valid witness. It is an implementation check and upper-bound diagnostic with privileged information.
- `unchanged` returns the current string.
- `new_only` searches distance one using the new rule only, preferring same-length candidates and then lexicographic order. It does not inspect old rules and stops at radius one.

The default selects 320 controlled states plus 480 native and 640 order requests per algorithm: 1,440 records per algorithm, or 4,320 across all three.

## Running an LLM evaluation

Use the development split first. The evaluator is an HTTP client; it does not download weights, allocate GPUs, install a serving engine, or start a model server. A compatible endpoint must already be reachable from its execution environment.

### Open-weight models over SSH

On a provisional model-preparation branch:

```sh
cp configs/ssh-pilot.example.yaml configs/experiment.yaml
```

Edit the copied file before committing it. Its essential structure is:

```yaml
study: ssh-open-weight-development-pilot
dataset_dir: data
split: development
tracks: [native, order]
models:
  - name: open-weight-model
    adapter: chat
    deployment: self_hosted
    model_id: SET_EXACT_SERVED_MODEL_ID
    base_url: http://127.0.0.1:8000/v1
    api_key_env: null
    max_input_tokens: 32768
    input_price_per_million: 0
    output_price_per_million: 0
    pricing_verified_on: '2026-10-08'
    parameters:
      max_tokens: 256
      temperature: 0
    transport_retries: 2
    timeout_seconds: 180
output_dir: outputs/ssh-open-weight-development-pilot
budget_usd: 0
bootstrap_repetitions: 2000
seed: 20261008
human_audit_required_for_model_test: true
```

Replace the placeholder with the exact ID exposed by the server. Confirm the engine supports the model's chat template and selected parameters. The template's context bound, 256 completion tokens, and temperature zero are proposed pilot settings, not verified settings for an unspecified model. Reasoning models may need a larger completion cap; choose and freeze it before held-out evaluation.

A serving command can look like the following **inside an allocated GPU environment with vLLM already installed**:

```sh
vllm serve MODEL_ID --host 127.0.0.1 --port 8000
```

`MODEL_ID` is a placeholder, and model-specific engine options may be required. Follow the [vLLM serve reference](https://docs.vllm.ai/en/latest/cli/serve/) for the engine version in use. Keep serving dependencies separate from the benchmark environment.

Check reachability from the evaluator's execution environment:

```sh
curl --fail http://127.0.0.1:8000/v1/models
```

For an authenticated server, include the appropriate authorization header and set `api_key_env` to the credential environment-variable name. Credentials are never config values or URL components. A `/v1/models` response checks connectivity and advertised IDs; a development pilot is still needed to establish chat-completion compatibility.

`127.0.0.1` refers to the machine/container running the evaluator. An SSH login shell, a GPU compute node, and a container can have different localhost endpoints. Place the evaluator and server in a reachable execution layout before launch.

Next, validate locally in that prepared environment:

```sh
uv sync --locked
uv run --locked python -m passgame.run \
  --config configs/experiment.yaml --preflight
```

Preflight sends no model requests. It validates data, certificates, configuration, credential presence, and adapter construction. It does **not** contact the server, verify model/GPU fit, check its chat template, or run inference. Commit the finalized config and serving/startup recipe, then launch the recorded experiment through the project's launcher using the existing fixed run contract.

With `deployment: self_hosted` and both API token prices explicitly zero, `budget_usd: 0` is allowed. This records zero API-token billing. It does not track or cap GPU charges, scheduler accounting, electricity, or execution time.

### Galvani execution layout

The selected SSH alias is `galvani`. Checks on **2026-10-08** identified it as a Slurm login host; the checked login environment had no usable `uv` command or system-Python vLLM installation, and its localhost port 8000 was not serving the model endpoint. These are dated observations of that environment, not a statement about every compute node or container.

For a Galvani pilot:

1. Select exact model weights/revision, serving engine, decoding settings, and GPU requirements.
2. Obtain a scheduled GPU execution environment following the cluster's [Slurm guide](https://portal.mlcloud.uni-tuebingen.de/user-guide/galvani/galvani_slurm/) and [system architecture](https://portal.mlcloud.uni-tuebingen.de/user-guide/galvani/galvani_system_architecture/).
3. Prepare Python/`uv` for the fixed evaluator recipe and a separate suitable serving environment or container.
4. Start the server on the allocated GPU node, make it reachable from the evaluator, and verify its served model ID.
5. Record the environment/startup recipe in the experiment snapshot, run preflight, then launch the development evaluation.

The current repository does not contain a finished Galvani allocation/server-startup script. Actual GPU inference belongs on an allocated compute node. SSH access alone does not make the model pilot ready. See [SSH evaluation notes](docs/ssh-evaluation.md) for provenance requirements and execution-layout details.

### Provider-hosted models

Use [configs/pilot.example.yaml](configs/pilot.example.yaml) on a model-preparation branch. Fill the exact model ID, compatible HTTPS endpoint, supported decoding parameters, verified input/output token prices and verification date, prompt bound, and positive spending ceiling. Export the credential under the configured `api_key_env` name before preflight and execution.

The adapter uses the [chat-completions request schema](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create). A provider with a different schema needs a compatible frontend or a separately implemented adapter. Do not assume every endpoint supports the same token-limit or temperature parameters.

### Moving to held-out evaluation

The checked-in manifest records `human_audit_status: pending`. The current runner requires human-audit completion for **all held-out chat-model evaluations**, including self-hosted models with zero API prices, when the configured audit requirement is enabled. Development pilots and diagnostic validation are allowed while review is pending.

After the pilot, freeze model settings and serving provenance, complete the [human audit](#inspecting-rules-and-completing-the-audit), and prepare a new committed test configuration and output directory. Changing `split` to `test` alone does not fulfill the audit requirement. A design change to the review requirement must be explicit and documented; automation cannot mark a human review complete.

## Configuration reference

Paths are resolved relative to the process's working directory, so use the repository root. The fixed recipe reads `configs/experiment.yaml`; preflight accepts another config path for preparation checks.

### Top-level settings

| Setting | Meaning |
| --- | --- |
| `study` | Name recorded with this evaluation |
| `dataset_dir` | Dataset manifest and episode files; v2 additionally contains focal pairs |
| `split` | Explicitly `development` or `test` |
| `tracks` | V3 permits `seeded` and `order`; legacy v2 additionally permits `native`/`fixed_start` for chat |
| `rule_count` | Optional exact number of scheduled rules; the current pilot sets `8`. Cases and episodes with other lengths are excluded before planning or requests; an empty selection is rejected |
| `models` | Model/algorithm configurations with unique names |
| `output_dir` | Evidence directory; choose a new path for changed code/data/config |
| `budget_usd` | Conservative API-token spending ceiling; positive for provider deployment |
| `bootstrap_repetitions` | Paired-bootstrap resamples; templates use 2,000 |
| `seed` | Analysis random seed; templates use `20261008` |
| `human_audit_required_for_model_test` | Held-out chat-model audit gate; defaults to enabled |
| `human_audit_required_for_paid_test` | Legacy gate key used if the newer key is absent; current code applies it to all chat models |

### Chat-model settings

| Setting | Meaning |
| --- | --- |
| `name` | Unique local label for records and comparisons |
| `adapter` | `chat` for an endpoint; `diagnostic` for the three supplied algorithms |
| `deployment` | `provider` by default, or `self_hosted` with explicit zero token prices |
| `model_id` | Exact non-placeholder served/provider model identifier |
| `base_url` | API base ending in `/v1` for the example servers; adapter appends `/chat/completions` |
| `api_key_env` | Name of an existing environment variable; null/omitted permits unauthenticated endpoints |
| `max_input_tokens` | Configured conservative input bound for guard/budget calculations |
| `input_price_per_million` | Verified nonnegative input-token price in USD per million tokens |
| `output_price_per_million` | Verified nonnegative output-token price in USD per million tokens |
| `pricing_verified_on` | ISO-formatted pricing/accounting verification date |
| `parameters` | Endpoint-supported decoding settings, including a positive `max_tokens` or `max_completion_tokens` cap |
| `transport_retries` | Additional retries for transient transport, HTTP 429, and HTTP 5xx failures; default two |
| `timeout_seconds` | HTTP request timeout |

Remote endpoints require HTTPS. HTTP is accepted only for localhost/loopback addresses. URLs containing credentials, query strings, or fragments are rejected. `parameters` cannot override `model`, `messages`, `stream`, `n`, `tools`, or `response_format`.

The input guard uses a conservative UTF-8 byte bound with message overhead, not the selected model's tokenizer. Confirm that the real conversation and completion cap fit the model/server context capacity. Exact weight revision, engine version, chat template, precision/quantization, GPU type/count, and reasoning mode should be recorded alongside the committed serving recipe; `model_id` alone does not capture all of them.

## Scores and analysis

Scoring is deterministic, with no LLM judge. Old-rule checks are made on the incoming string and on the parsed response. Retention concerns the subset of old rules that were true **before this response**; pre-existing failures are not counted as new regressions.

| Record field | Definition |
| --- | --- |
| `full_success` | 1 if the returned string satisfies every active rule, otherwise 0 |
| `new_success` | 1 if it satisfies the newly introduced rule, otherwise 0 |
| `all_old_success` | 1 if every old rule is true afterward; null when there are no old rules |
| `retention` | 1 if all previously satisfied old rules remain true; null if there were none |
| `fractional_retention` | Fraction of previously satisfied old rules retained; null if ineligible |
| `retention_eligible` | Whether at least one old rule was true on the incoming string |
| `previously_satisfied` | IDs eligible for retention scoring |
| `newly_violated_old_rule_ids` | Previously satisfied old rules now false; null for invalid output |
| `old_rules_broken` | Count of those newly violated rules; null for invalid output |
| `before_checks`, `after_checks` | Per-rule Boolean checks; after checks are null for invalid output |
| `new_was_noop` | Whether the new rule was already true on the incoming string |
| `edit_distance` | Incoming-to-response edit distance; null for invalid output |
| `certificate` / `dynamic_certificate` | Offline / actual incoming-state distance and breakage certificate |

Format/domain failures contribute zero full/new success and zero retention/fractional retention when eligible. They have **unknown**, not zero, broken-rule counts. Infrastructure failures are missing evidence, reported separately from model errors and excluded from response-rate denominators. A state with existing old-rule failures can still be scored for new-rule success and further regressions even when its distance certificate is `unknown`.

For example, if only two of five old rules are true on input and both remain true, retention is 1 even if the other three remain false. `all_old_success` distinguishes that case from preserving a fully valid old state.

### Aggregate and episode metrics

`analysis.json` reports denominators alongside scores. Null values are excluded from the relevant metric's denominator; an undefined rate is not zero. In JSON, `old_rules_broken.rate` is a **mean count**, which can exceed one. The CSV calls it `mean_old_rules_broken`.

The regression summaries are:

- `new_success_with_regression`: new-rule success with retention failure, divided by all retention-eligible responses.
- `regression_given_new_success`: retention failures among new-rule-successful, retention-eligible responses.

Episode summaries record the first failure, observed turn count, termination reason, and whether the horizon was reached. A first rule/format/domain failure is a completed episode outcome with zero whole-episode and final success, even if later rules were never revealed. Later stages remain unattempted; no synthetic response rows are written. Infrastructure failures and interrupted episodes have unknown episode endpoints. Historical continue-after-failure runs retain their original recovery semantics. Survival summaries include early failed episodes as failures at their observed turn, with `at_risk` and `failures_at_turn` counts; shorter successful episodes are excluded from later denominators.

### Research endpoints and interpretation

| Endpoint | Current analysis scope |
| --- | --- |
| H1: constraint interference | Paired independent-minus-interfering full-success contrast for controlled diagnostics; native/order/fixed-start actual-state strata are descriptive and state-dependent |
| H2: new-rule success with regression | Paired interfering-minus-independent regression contrast for controlled diagnostics; native/order/fixed-start trajectories report observed regression rates and broken-rule counts |
| H3: rule order | Original-minus-reverse final and whole-episode success, paired by final rule set and shared initial string; random orders are descriptive |

The configured analysis uses 2,000 seeded paired-bootstrap resamples for 95% intervals on the supported paired contrasts. It produces no confirmatory p-values or equivalence conclusions. Turns and order variants are not treated as independent scenario blocks.

In native/order-only LLM runs, the legacy `h1`/`h2` paired entries have zero blocks and null estimates because there are no controlled responses. Use trajectory summaries, `interference_breakdowns`, `state_certification`, and H3 as applicable. See the [prespecified design](docs/preregistration.md) for interpretation.

`interference-summary.csv` includes a `track` column. Controlled diagnostic rows use the family's intended offline degree, including independent members. Native/order/fixed-start rows use the **actual incoming state's** certified minimum breakage; independent states can have degree zero. Unknown/no-op states are counted separately in `state_certification`. Autonomous degree strata do not establish a causal interference effect. Archived per-turn-reset data is explicitly separated as `legacy_reset`; only that historical protocol retains focal-only scoring and paired contrasts. `legacy_reset_prefix_records` counts its excluded setup rows.

## Outputs, caching, and resumption

An evaluation writes the following under its configured `output_dir`:

| File | Contents |
| --- | --- |
| `metadata.json` | Effective configuration, code/data/config hashes, planned records, and validation |
| `records.jsonl` | One evidence record per completed response or infrastructure failure: exact messages, response, private checks/rules/certificates, model settings, usage, attempts, and latency |
| `events.jsonl` | Request-start and budget-stop events for interrupted-request protection |
| `budget.json` | Persisted reserved API-token spending and ceiling |
| `analysis.json` | Full summaries, denominators, contrasts, episodes, survival, and certificate strata |
| `summary.csv` | Compact model/track/condition success and retention summaries |
| `interference-summary.csv` | Degree-stratified success, retention, and mean broken-rule counts |
| `completion.json` | Normal completion or handled partial-run status, planned/observed records, spending, and stop reason |

Errors before execution, or unexpected crashes, may occur before completion/analysis files are written. Exit code 2 indicates a handled incomplete run, including budget exhaustion or infrastructure missingness. A model's terminal failure is an observed outcome and does not itself make execution incomplete. `planned_records` is an upper bound; `skipped_after_failure` counts later turns intentionally not requested. Successful execution has `record_count + skipped_after_failure == planned_records`, all planned conversations ended normally or on a model failure, and no infrastructure missingness or budget stop. Replaying cached terminal failures does not request later stages.

The runner also emits structured stdout lines prefixed `CONFIG`, `VALIDATION`, `PROGRESS`, `METRIC`, `H1`/`H2`/`H3`, `INTERFERENCE`, `SEQUENTIAL_PROTOCOL`, and `SUMMARY`. Diagnostic runs add `DIAGNOSTIC_CONTRACT` checks. Raw evidence, not a status badge alone, supports interpretation.

### API spending

Before each HTTP attempt, including retries, the budget reserves:

```text
(max_input_tokens * input_price_per_million
 + completion_cap * output_price_per_million) / 1,000,000
```

Reservations are conservative, persisted, and never refunded. The ledger is not an actual provider invoice; correct prices and bounds matter. Provider-side spending controls remain useful. A self-hosted run reserves zero API spend while still recording model requests.

### Resuming safely

Completed responses are cached using model/settings, messages, metadata, and code/data/config hashes. Re-executing the same snapshot/config with its original output directory reuses these records. Changing any protected hash requires a new output directory; changing `output_dir` itself changes the configuration hash.

A request-start event without a matching cached outcome blocks automatic replay for **all chat-model requests**, including zero-priced self-hosted requests. Inspect `events.jsonl`, `records.jsonl`, and the ledger and reconcile the unknown outcome before resuming. There is no automatic reconciliation command. Cached infrastructure failures are evidence records too; do not silently delete them to make an incomplete study appear complete.

### Reanalyzing saved evidence

For default bootstrap settings, analysis can be regenerated without contacting a model:

```sh
uv run --locked python -m passgame.analyze \
  outputs/multi-rule-sequential-validation/records.jsonl \
  --output outputs/reanalysis
```

Substitute the actual evidence path for another study. This CLI uses 2,000 repetitions and seed `20261008`; for a run with different settings, use `write_analysis` with the recorded values rather than assuming the CLI will read its configuration. The analysis command writes the three analysis files, not a replacement request log or completion record.

## Inspecting rules and completing the audit

For current v3 games, use [the readable reference](data/sequential-v3/development-games.txt) or `uv run --locked python -m passgame.export --dataset data/sequential-v3 --output outputs/readable-v3`. It produces a rules CSV, both split references and an unsigned audit worksheet. The following instructions describe the preserved v2 dataset. Its machine-readable rules are in [pairs.jsonl](data/pairs.jsonl) and [episodes.jsonl](data/episodes.jsonl). Export the legacy reference with:

```sh
uv run --locked python -m passgame.export \
  --dataset data --output outputs/readable-v2
```

This produces:

- `passgame-v2-rules.csv`: 192 offline-pair rows and 176 episode rows, with ordered human-readable rule descriptions.
- `passgame-v2-rules-guide.md`: protocol explanation, examples, and certificate terminology.
- `passgame-v2-audit-worksheet.md`: unsigned review worksheet for the 20 sampled pairs, covering 40 focal states.

The reference CSV lists all rules for researchers; it is **not an LLM prompt**. Offline rows contain incoming states and degree/distance columns. Episode degree fields are blank because interference depends on the model's intermediate states. A full witness is an example valid answer, not an answer the model must reproduce.

The audit worksheet supports independent human verification of input validity, the new-rule violation, exact distances, all shortest new-only repairs, minimum/maximum breakage, matching, and alternative valid answers. It is separate from automated checks, which compare the primary checker with [audit.py](src/passgame/audit.py).

Follow [docs/audit-instructions.md](docs/audit-instructions.md). A human reviewer records their name, date, sample hash, discrepancies, and resolutions in a new `docs/audit-signoff.md` on a provisional preparation branch. Only after actual signed review should `human_audit_status` become `complete`. The export/generator never signs the audit. Keep evaluated snapshots unchanged.

## Development and reproducibility

### Dataset regeneration

To inspect a fresh deterministic generation without overwriting the checked-in dataset:

```sh
uv run --locked python -m passgame.generate --output outputs/regenerated-data
```

Generation uses seed `20261008`; appended multi-rule families use a separate stream seeded `20261009` to preserve the original cases. The generator writes pairs, episodes, an audit sample, and the manifest, validates certificates with the independent checker, and resets human-audit status to pending. Running it with `--output data` overwrites the benchmark data; do that only during preparation of an explicitly versioned change, never on a frozen evaluated baseline.

The runner verifies dataset file hashes before evaluation. Duplicate case IDs/content and duplicate predicates used to inflate interference degree are rejected during case validation. For reproducibility, preserve the commit, lockfile, effective configuration, dataset hashes, exact prompts/responses, and external serving provenance.

### Testing and extending the benchmark

```sh
uv run --locked pytest
```

The suite checks rule boundaries and overlap/nesting semantics, exact edit neighborhoods, generated certificates, multiple-rule lower bounds, sequential disclosure, strict parsing/state transitions, adapter payload isolation, budget/retry behavior, audit gating, and interrupted/incomplete evidence handling.

To add a rule kind, implement its validation, semantics, and description in `constraints.py`, independently implement its audit semantics, and verify boundary cases. To add a family, provide distinct constraints, matched states, a full-valid witness, and a complete shortest-neighborhood certificate; update generation, split/audit coverage, and the versioned design. To add a model adapter, preserve the sequential history and evidence contracts, budget behavior, and missing-evidence distinction.

Completed experiment snapshots remain immutable. Make benchmark or model-setting changes on a new preparation/child branch, commit them, and use a new output directory. Repository documentation changes do not substitute for a new validation when semantics or data change.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Preflight passes but no LLM was evaluated | Preflight sends no requests; the default configuration also uses diagnostics |
| Placeholder-model or missing-price error | Fill the pilot template with the exact ID, prices/accounting date, input bound, and completion cap |
| Zero-budget error for a local model | Select `deployment: self_hosted` and explicitly set both token prices to zero |
| Held-out audit error | Use `development` for the pilot; complete the signed review before test evaluation |
| `controlled`/`fresh` rejected for a model | Use `native`, `order`, or `fixed_start` with `adapter: chat`; the scripted diagnostic prefixes remain unavailable to chat models |
| Missing credential environment variable | Export the exact configured variable; `.env` is not loaded automatically |
| Connection refused or request timeout | Verify the server from the evaluator's node/container and its endpoint/port; preflight does not connect |
| Unsupported parameter or bad chat template | Match token-limit/decoding fields and serving template to the selected model/engine |
| Input-bound or context-limit failure | Check full history, conservative byte bound, model context, and completion cap |
| Many format failures | Inspect raw replies for prose, fences, duplicate/extra keys, truncation, or unsupported output settings |
| Many `unknown` certificates | Inspect incoming old-rule validity and bounded-search reasons; retain these states as separate evidence |
| Output-directory mismatch | Use a new directory for changed code/data/config; preserve the earlier evidence |
| Interrupted-model-request error | Reconcile outstanding start events and outcomes; do not blindly replay or clear the ledger |
| `uv` or serving engine missing on Galvani | Prepare the allocated execution environment/container for the fixed recipe and model server |

## Research limitations

- The six families are parameterized templates. Held-out parameters do not establish generalization to unseen rule templates.
- Active-rule count is not a calibrated information-complexity measure; some additional predicates are easy or redundant.
- Degree comparisons across families can include family and load differences. Observed LLM strata depend on the model's own choices.
- Autonomous models can avoid the fixed offline interfering state. The evaluator cannot guarantee every model encounters the same degree at the same turn.
- State certification is exact only within its proven cases: no-op, safe one-edit repair, or a one-edit lower bound plus two-edit witness. Larger or already-invalid states can remain unknown.
- Order contrasts include changes in intermediate repair demands as well as presentation order; they measure a total order effect.
- The reference diagnostic sees a private witness, and the new-only diagnostic searches only radius one. Neither is evidence about LLM reasoning.
- Human audit, model selection, serving environment, and actual LLM measurements remain separate prerequisites for the main study.
