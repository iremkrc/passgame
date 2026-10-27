# PassGame experiments and run guide

This guide covers the **version-3 progressive experiment**. Run commands from the repository root. From the directory containing your checkout:

```sh
cd passgame
```

Use your checkout directory name if it differs. Personal paths and account details belong only in your ignored local configuration.

## 1. What the experiment measures

PassGame tests whether a model can update a persistent string to satisfy a new rule while preserving every earlier rule. No training is performed. Rule checking is deterministic; there is no LLM judge.

Each original episode follows this procedure:

1. Start from the predefined seed stored in the dataset, shared across models for that episode.
2. Introduce one new rule. Include the current string, previous-rule reminders, and the complete real conversation history.
3. Ask the model to return exactly `{"password":"..."}`.
4. Check its answer against **every active rule**.
5. If it passes, use that exact returned string as the next input.
6. If it fails any rule, JSON-format requirement, or string-domain requirement, save the failure and end the game immediately.

There are eight scheduled rules per game. Failure may end a game earlier. There are no per-turn resets, evaluator repairs, or retries of a semantically incorrect answer. Transport retries have a separate fixed cap; exhausted infrastructure failures are recorded as missing evidence.

Strings contain 1–32 characters from ASCII letters, digits, and `!_-()[]`. Matching is case sensitive, and positions are one-based. Any answer satisfying the active rules is accepted. Full rewrites are allowed; minimum edit distance is used for interference analysis, not as an output requirement. Returning an unchanged string is valid when it already satisfies every active rule.

## 2. What changed from earlier pilots

The previous v2 `fixed_start` experiment used strings that were already valid under the first seven rules. They had originally been constructed as incoming states for a final repair challenge. Reusing them as whole-episode starts made early turns mostly preservation checks.

V3 has explicit neutral starts such as `abc1`. The first rule requires a change. Private example paths require a repair at every step and establish that every cumulative rule set has a valid solution. These paths demonstrate interference earlier in the game.

Historical v2 data, source snapshots, and results remain preserved. Their results must be reported separately from v3. The historical configuration is [dev-qwen2.5-7b-prevalidated-starts.yaml](../configs/dev-qwen2.5-7b-prevalidated-starts.yaml). The old reset protocol is also separate and is labelled `legacy_reset` during reanalysis.

## 3. Dataset, families, and an example

| Suite | Development games | Held-out games | Maximum requests per model |
| --- | ---: | ---: | --- |
| Main `seeded` | 24 | 120 | 192 development / 960 held-out |
| Optional `order` | 96 | 480 | 768 development / 3,840 held-out |

The main development suite contains **24 distinct games**, four per family. They are individual episodes, not 12 independent/interfering pairs. The held-out suite contains twenty original games per family. Final rule sets are disjoint across the two splits.

| Family | Interaction demonstrated by its private example path |
| --- | --- |
| `numeric` | Digit count and sum interact with a required digit or position |
| `position_count` | Character multiplicity interacts with a positional change |
| `substring_position` | A required substring interacts with positional changes |
| `forbidden_position` | A positional edit can create a forbidden substring |
| `numeric_multi_2` | An early shortest new-only repair necessarily breaks at least two old rules |
| `numeric_multi_3` | An early shortest new-only repair necessarily breaks at least three old rules |

The suffixes `_2` and `_3` count disrupted old constraints, not total game rules or required edits. Both families have eight rules. Their early reference challenges occur at turns 4 and 5; degree-one examples appear by turn 3.

Game 1 has this possible successful trajectory:

| Turn | Current string | New rule | Example valid output |
| --- | --- | --- | --- |
| 1 | `abc1` | Exactly two digits | `abc12` |
| 2 | `abc12` | Digit sum equals 11 | `abc47` |
| 3 | `abc47` | Contains `8` | `abc38` |
| 4 | `abc38` | Exactly six characters | `abc38_` |
| 5 | `abc38_` | Contains `!` | `abc38!` |
| 6 | `abc38!` | First character is `X` | `Xbc38!` |
| 7 | `Xbc38!` | Second character is `A` | `XAc38!` |
| 8 | `XAc38!` | Fourth character is `8` | `XAc83!` |

At turn 3, changing `abc47` to `abc48` satisfies the new rule but breaks the sum. Changing to `abc38` preserves both old constraints in two edits.

**These example outputs are private validation data. They are never inserted as assistant messages in an LLM run.** Models generate their own answers and never receive future rules or witnesses. Every actual input is certified again; a model can satisfy a future rule early, so example interference does not guarantee observed interference.

Useful files:

- [All 24 development games and example paths](../data/sequential-v3/development-games.txt).
- [Episode definitions](../data/sequential-v3/episodes.jsonl): starts, rules, private reference paths, and order variants.
- [Manifest](../data/sequential-v3/manifest.json): version, hashes, validation, and audit status.
- [Main configuration](../configs/dev-qwen2.5-7b-eight-rules.yaml).
- [Generator and validator](../src/passgame/sequential.py).

## 4. Install and check locally

Prerequisites are Python 3.11 or newer, `uv`, and Git. GPU dependencies are separate from the lightweight evaluator.

```sh
uv sync --locked
uv run --locked pytest -q
```

Check the main configuration without sending model requests:

```sh
uv run --locked python -m passgame.run \
  --config configs/dev-qwen2.5-7b-eight-rules.yaml --preflight
```

Expect `PREFLIGHT passed`, 24 planned episodes, and 192 maximum records. Preflight checks the dataset, configuration, and adapter initialization. It does not prove that a model server is running or that weights fit on the selected GPU.

The dataset is already checked in. To reproduce its default generation before freezing a study:

```sh
uv run --locked python -m passgame.sequential --output data/sequential-v3
```

Generation rewrites the v3 files and sets human-audit status to pending. Preserve evaluated datasets and signed audit records; use a new dataset version for substantive changes.

To export readable references and an unsigned audit worksheet:

```sh
uv run --locked python -m passgame.export \
  --dataset data/sequential-v3 --output outputs/readable-v3
```

## 5. Run the main Qwen pilot on Galvani

This route starts the server, evaluates, monitors the Slurm job, and downloads results. It uses the prepared Qwen2.5-7B-Instruct weights and vLLM 0.24.0 container in your privately configured cluster workspace.

Your SSH alias must be configured for your access. The launcher reads it, your scheduler account, and the partition from private settings. Its default resource request is one A100, four CPUs, 48 GB host RAM, and a 30-minute limit. These site/account settings are specific to your environment.

Create a private settings file once on each machine:

```sh
cp configs/cluster.example.env configs/cluster.local.env
chmod 600 configs/cluster.local.env
```

Edit `configs/cluster.local.env` locally with your SSH alias, workspace, scheduler account/partition, container path, and model path/revision. Use literal values and quote values containing spaces. The file is git-ignored and excluded from source snapshots. Environment variables can supply settings when no local file overrides them; `PASSGAME_CLUSTER_CONFIG` selects an alternative private file. Keep these values out of shared documentation and screenshots.

Generated runtime settings, run metadata, archives and logs may contain private execution paths. They remain local artifacts; do not publish them without reviewing them.

From a fresh checkout, or after changing the code, data, configuration, or packaged documentation, build a snapshot:

```sh
uv run --locked python scripts/package_pilot.py
```

Packaging creates a frozen Git snapshot, includes the batch wrapper, records hashes and runtime choices, and runs preflight inside the snapshot. It does not submit a GPU job or download model weights. Its archive and manifest are generated under ignored `outputs/`; a fresh checkout can reconstruct them with this command.

Check the package, then start the new experiment:

```sh
bash run-pilot.sh --check
bash run-pilot.sh --new
```

`--check` does not connect to Galvani. `--new` starts a new experiment, so use it once per intended run. Enter any SSH verification code privately in Terminal when prompted.

If Terminal closes, resume monitoring the same job:

```sh
bash run-pilot.sh
```

Leave the code, configuration, and selected package unchanged when resuming. Repackaging creates a new snapshot; the launcher rejects an existing saved job belonging to another snapshot. Do not use `--new` merely to reconnect to a running job.

The main result directory is:

```text
outputs/pilot-results-JOB_ID/dev-qwen2.5-7b-progressive-eight-rules-v3/
```

The local `outputs/pilot-last-run.json` records the job ID, remote run directory, and snapshot commit. The package manifest is `outputs/pilot-stop-on-failure-snapshot.json`.

## 6. Run another open model

Create one configuration per model and experimental condition:

```sh
cp configs/dev-qwen2.5-7b-eight-rules.yaml configs/dev-my-model.yaml
```

Edit the copied file, retaining the v3 dataset, `seeded` track, eight-rule selection, and reminder setting:

| Field | Example value |
| --- | --- |
| `study` | `dev-my-model-progressive-v3` |
| `models[0].name` | `my-model` |
| `models[0].model_id` | `my-model` |
| `output_dir` | `outputs/dev-my-model-progressive-v3` |

Keep the cases and prompt protocol identical across models. Record decoding settings, context/completion limits, chat template, precision, model revision, and any reasoning mode. Choose a workable completion budget during development and freeze it before the main study; document any model-specific differences.

For the packaged Galvani route, stage the weights on Galvani first. Replace both placeholders in the following command:

```sh
uv run --locked python scripts/package_pilot.py \
  --config configs/dev-my-model.yaml \
  --model-dir /path/to/cluster/model-weights \
  --model-revision WEIGHT_REVISION
bash run-pilot.sh --check
bash run-pilot.sh --new
```

Changing only `model_id` does not change weights. The packager requires an explicit remote model directory and revision for a different model, and derives the served name from the configuration. The packaged endpoint must be `http://127.0.0.1:<port>/v1`; the packager freezes and exports that port to the server. Use separate ports for jobs that may share a compute node.

The convenience launcher keeps its one-A100 allocation and fixed container. A model requiring a different GPU layout or runtime needs an appropriate batch wrapper; [serve_and_eval.sh](../scripts/serve_and_eval.sh) and [slurm.example.sbatch](../scripts/slurm.example.sbatch) provide the generic route.

### Evaluate an already running endpoint

Run these on the machine where the configuration's endpoint is reachable. `127.0.0.1` refers to that machine, not automatically to Galvani or your laptop.

```sh
uv run --locked python -m passgame.run --config configs/dev-my-model.yaml --preflight
uv run --locked python -m passgame.run --config configs/dev-my-model.yaml
```

The server's model name must match `model_id`. Self-hosted configurations use zero API token prices and `budget_usd: 0`; GPU accounting is separate. For authentication, set `api_key_env` to a credential environment-variable name rather than putting a key in YAML.

### Start a server on an allocated GPU node

With the container and local weights already available, set paths appropriate to that node:

```sh
export SIF=/path/to/vllm-v0.24.0.sif
export MODEL_DIR=/path/to/model-weights
export SERVED_NAME=my-model
export CONFIG=configs/dev-my-model.yaml
uv sync --locked
bash scripts/serve_and_eval.sh
```

This requires Apptainer, `nvidia-smi`, `curl`, and `uv`. Submit through your scheduler or use an allocated GPU shell. The default port is 8000, context length is 32,768, precision is bfloat16, and the default driver check expects CUDA 13 compatibility. This helper stops its server when evaluation exits. See [the SSH guide](ssh-evaluation.md) for the prepared Galvani setup.

## 7. Optional experimental conditions

### Previous-rule reminders versus history only

The main condition repeats earlier rules in each latest message. The comparison retains the full original conversation but sets `remind_previous_rules: false`.

Against a running Qwen endpoint:

```sh
uv run --locked python -m passgame.run \
  --config configs/dev-qwen2.5-7b-eight-rules-no-reminders.yaml --preflight
uv run --locked python -m passgame.run \
  --config configs/dev-qwen2.5-7b-eight-rules-no-reminders.yaml
```

Alternatively, use the generic serving helper with that file as `CONFIG`. The Galvani packager/launcher requires reminders enabled for either `seeded` or `order`, so it does not package the no-reminder comparison condition.

### Rule-order experiment

Use [configs/dev-qwen2.5-7b-v3-order.yaml](../configs/dev-qwen2.5-7b-v3-order.yaml). It selects `tracks: [order]`, keeps the same model settings and reminder policy, and writes to `outputs/dev-qwen2.5-7b-v3-order`.

Every one of the 24 development rule sets is evaluated in four fixed orders:

| Variant | Sequence |
| --- | --- |
| `original` | Original rule sequence |
| `reverse` | Exact reverse sequence |
| `random_1` | First seeded random permutation |
| `random_2` | Second seeded random permutation |

The random permutations are stored in the dataset and reused across models. Each variant starts a fresh game from the same original seed and ends with the same eight-rule set. Within each game, successful outputs still feed the next turn and the first failure terminates it. Rule IDs identify constraints and stay unchanged when their disclosure order changes. The first disclosed rule in a permutation can already be satisfied by the seed.

The development experiment contains **96 games**, 24 per order, and at most **768 requests per model**. The held-out order suite contains 480 games and at most 3,840 requests; its audit gate still applies.

On Galvani, build and submit the separate order experiment:

```sh
uv run --locked python scripts/package_pilot.py --config configs/dev-qwen2.5-7b-v3-order.yaml
bash run-pilot.sh --check
bash run-pilot.sh --new
```

Results download under `outputs/pilot-results-JOB_ID/dev-qwen2.5-7b-v3-order/`. Packaging selects which experiment the launcher submits; to switch back to the main 24-game experiment, rebuild with the default packaging command. Do not repackage when merely resuming monitoring of an existing job.

Against an already running Qwen endpoint, use:

```sh
uv run --locked python -m passgame.run --config configs/dev-qwen2.5-7b-v3-order.yaml --preflight
uv run --locked python -m passgame.run --config configs/dev-qwen2.5-7b-v3-order.yaml
```

For another model, copy the order configuration, change model name/ID and study/output names, and pass its explicit weights/revision to the packager as in section 6.

Order-specific outputs are:

- `order-summary.csv`: whole-game success, mean successfully completed turns, reached-horizon counts, and incomplete episodes for each order.
- `order-survival.csv`: survival, at-risk counts, and first failures at each turn, separately for each order.
- `order-effects.csv`: original-minus-reverse and original-minus-each-random differences, for whole-game success and successfully completed turns, with paired bootstrap intervals and block counts.

Pairs require the same final rule set, initial string, and scheduled horizon. Incomplete infrastructure histories are excluded from paired estimates and counted separately in summaries. A positive difference favors the original order; a negative difference favors the comparison order. The original-versus-reverse comparison is primary; the two random comparisons are secondary descriptive checks, without confirmatory p-values.

The legacy `h3` entries retain original-versus-reverse final/whole-game success. Under first-failure termination, those two binary endpoints coincide. The new progress comparisons remain informative when both orders fail: for example, failure at turn 4 versus turn 2 means three versus one successfully completed turns, a difference of two.

## 8. Read and interpret results

| File | Contents |
| --- | --- |
| `completion.json` | Planned/observed records, skipped turns, episode completion, and run status |
| `records.jsonl` | Exact messages, responses, strings, active rules, scores, and actual-state certificates |
| `metadata.json` | Effective configuration, selection, dataset version, and code/config/data hashes |
| `analysis.json` | Per-game outcomes, survival, certification coverage, metrics, and supported contrasts |
| `summary.csv` | Aggregate attempted-turn scores |
| `interference-summary.csv` | Scores stratified by certified actual interference degree |
| `order-summary.csv`, `order-effects.csv`, `order-survival.csv` | Per-order outcomes, paired contrasts, and survival; populated for the `order` track |
| `events.jsonl`, `budget.json` | Request lifecycle and API-token spending reservations |

The principal measures are full active-rule success, new-rule success, retention of previously satisfied rules, whole-game success, and successfully completed turns before failure. Report new-rule success with regression as a distinct outcome.

The per-episode `turns_observed` field includes a failing terminal turn. `turns_completed` counts successful turns before the first failure: `first_failure - 1`, or eight when the entire game passes. It is null for incomplete histories.

`completion.json` containing `complete: true` means the experiment accounted for every planned episode, including episodes ending in model failure. **It does not mean the model passed every game.** `skipped_after_failure` counts scheduled later turns that were intentionally never requested.

Actual incoming states are classified as:

- `no_op`: the current string already satisfies the new rule.
- `independent`: a one-edit repair satisfies both the new rule and every earlier rule.
- `interfering`: the new rule has a one-edit repair, every such repair breaks old constraints, and a full-valid two-edit repair is certified.
- `unknown`: the bounded certifier cannot establish the required distances. This can include new rules needing more than one edit or an unsuccessful bounded witness search. It is not itself a model failure.

Report counts for all four labels. Interference degree is the minimum number of old rules broken over **all** shortest new-only repairs, including insertions and deletions. A model's game need not retain its reference path's classification.

Autonomous H1/H2 comparisons are descriptive because different models choose different intermediate strings. The current `seeded` run does not produce a controlled matched LLM interference contrast. A zero-block/null legacy H1 entry is not evidence of zero interference effect. If no certified interfering turns were attempted, report that the intended effect could not be evaluated.

To regenerate analysis without contacting the model, replace `PATH_TO_RUN`:

```sh
uv run --locked python -m passgame.analyze \
  PATH_TO_RUN/records.jsonl --output outputs/reanalysis-v3
```

That CLI uses the default 2,000 bootstrap repetitions and seed 20261008, matching the supplied main configuration. Use the recorded settings explicitly through the Python analysis API if evaluating a configuration with different analysis settings.

Rerunning the same code/data/config/output directory reuses saved responses. Changes to protected hashes require a new output directory. An interrupted model request with an uncertain outcome requires reconciliation before resuming; the evaluator refuses to silently repeat it.

## 9. Held-out evaluation

The 24-game development set is a pilot. The 120-game held-out set is available for a later frozen evaluation. Neither count guarantees adequate precision for every model or subgroup comparison.

The v3 manifest currently requires a human quality audit before any held-out chat-model run, including self-hosted models. Follow [audit-instructions.md](audit-instructions.md) for the 12-game audit sample. Exporting the worksheet or passing automated tests does not complete the human review.

After signed review and configuration freeze, copy the main configuration and give the test study a unique `study`/`output_dir`, with `split: test`. Package and preflight that configuration as a new experiment. Do not bypass the audit gate or present the development-driven protocol changes as pre-pilot preregistration.

## 10. Troubleshooting and files to preserve

| Symptom | Action |
| --- | --- |
| Missing local archive/manifest | Run `uv run --locked python scripts/package_pilot.py` |
| Code or configuration changed after packaging | Rebuild once for the new experiment, then launch with `--new` |
| Saved job belongs to another snapshot | Use its original snapshot to resume, or `--new` for an intentionally new run |
| Model ID not found or wrong weights selected | Match the served name and explicitly select the correct weight directory |
| vLLM fails to start or runs out of GPU memory | Inspect the server/job logs and use a compatible model, container, and allocation |
| Format failure or truncated answer | Inspect the raw response and provider finish reason; establish token/reasoning settings during development |
| Output directory belongs to different code/data/config | Choose a new output directory |
| Complete run but zero whole-game passes | Inspect first-failure turns and actual errors; `complete` describes execution accounting |
| Zero certified interference | Inspect actual state coverage and stage reach; do not apply reference labels to model outputs |
| Held-out run awaits human audit | Complete the documented human review |

Commit source, tests, configurations, the v3 dataset and readable reference, documentation, lockfile, and packaging/batch scripts. New generated results, archives, caches, local environments, logs, and credentials remain outside the source commit. Preserve raw research evidence separately, together with the frozen source and serving/model provenance.

The main implementation entry points are [run.py](../src/passgame/run.py), [protocol.py](../src/passgame/protocol.py), [oracle.py](../src/passgame/oracle.py), [analyze.py](../src/passgame/analyze.py), and [the packaging script](../scripts/package_pilot.py). Historical design amendments and interpretation limits are recorded in [preregistration.md](preregistration.md).
