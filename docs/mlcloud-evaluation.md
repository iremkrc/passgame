# Tübingen ML Cloud experiments

PassGame can call the Tübingen ML Cloud LiteLLM gateway through its existing
chat adapter. The gateway publishes its API at
[llm.mlcloud.uni-tuebingen.de](https://llm.mlcloud.uni-tuebingen.de/), including
`GET /v1/models` and `POST /v1/chat/completions`. Inference runs on the service;
run the evaluator locally with the existing locked dependencies.

Run these commands from the repository root:

```sh
uv sync --locked
```

## Enter the key privately and discover models

In a local **zsh** terminal, enter the key at the hidden prompt:

```sh
read -rs 'TUEBINGEN_API_KEY?ML Cloud API key: '
echo
export TUEBINGEN_API_KEY
uv run --locked python scripts/mlcloud_models.py
```

The key stays in that shell's environment for subsequent commands. Do not put
it in YAML, a URL, source control, or chat. The runner does not automatically
load `.env` files. If the key already lives in a different environment variable,
use `--api-key-env VARIABLE_NAME` for discovery and set the same `api_key_env`
in your configuration.

Discovery lists the exact model IDs available to the key and makes no inference
requests. Model availability can differ by key and change over time. A listed
ID still needs a development run to establish decoding compatibility.

## Configure the development experiment

```sh
cp configs/mlcloud.example.yaml configs/dev-mlcloud.yaml
```

Edit the copied file:

- Set `name` to a unique readable label and `model_id` to an exact discovered ID.
- Fill both token prices in USD per million tokens and `pricing_verified_on`
  (`'YYYY-MM-DD'`) from the gateway/account's current accounting. Record zero
  prices only if zero API token billing is confirmed; model discovery does not
  establish pricing.
- Set a positive `budget_usd` spending ceiling. Provider configurations require
  a positive ceiling even when confirmed token prices are zero. The ceiling
  controls conservative reservations rather than reporting an invoice.
- Verify the model's context window against `max_input_tokens` plus its output
  cap, and confirm whether it accepts `max_tokens` or `max_completion_tokens`.
  The proposed 256-token cap may need increasing for reasoning models. Choose
  and record decoding/reasoning settings during development.
- Give each study a distinct `study` and `output_dir`.

This configuration keeps the current v3 protocol: **24 development games**, eight
progressive rules, earlier-rule reminders, and termination at the first failed
answer. It makes at most **192 requests per model before transport retries**.
For the order comparison, use a separate configuration/output directory with
`tracks: [order]`: 96 games and at most 768 requests per model before retries.

For a comparison, add another entry under `models` with its exact ID, unique
`name`, accounting, and supported decoding parameters. All entries share the
top-level budget and the same games. Conservative reservations per attempt are:

```text
(max_input_tokens * input_price_per_million
 + completion_token_cap * output_price_per_million) / 1,000,000
```

Each retry reserves again; the default allows two retries after the initial
attempt. Use the maximum request count and this reservation to size the ceiling.

## Validate and run

```sh
uv run --locked python -m passgame.run --config configs/dev-mlcloud.yaml --preflight
uv run --locked python -m passgame.run --config configs/dev-mlcloud.yaml
```

Preflight checks credentials, configuration, and data without contacting the
gateway. The second command runs inference. For a recorded experiment, follow
the repository's committed-snapshot convention: prepare a model-study branch,
commit the finalized configuration and source, and execute these commands from
that snapshot with the credential supplied separately. The existing
`run-pilot.sh` launcher starts a Galvani GPU server; use the local evaluator
commands above for this hosted API.

Inspect `completion.json`, `summary.csv`, `analysis.json`, and `records.jsonl`
under the configured output directory. A complete experiment includes games
ending in model failure. Keep code/configuration/output paths stable to resume
cached work, and use a new output directory when protected hashes change.
The existing human-audit requirement still applies to held-out model runs.

## Accepting optional Markdown fences on a rerun

The completed three-model pilot used strict bare JSON. The separate
[fence-tolerant configuration](../configs/dev-mlcloud-three-models-fence-tolerant.yaml)
sets `allow_markdown_fences: true` for all three models and selects a new study
and output directory. Its model settings, original-order games, token caps, and
spending ceiling match the strict pilot, so this comparison changes only the
response parser.

With that option, a single outer triple-backtick block, either unlabelled or
labelled `json`, is accepted. Everything inside must still be valid JSON with
exactly one string field named `password`; domain errors and rule violations
still end the game. There is no repair, corrective feedback, or model retry for
formatting. Prose around the block and multiple answer blocks remain invalid.

The evaluator preserves the original raw reply in the evidence and conversation
history. `markdown_fence_removed` records whether it removed a wrapper for
scoring, and `strict_parse_error` preserves what the strict parser would report
for that observed response. `response_protocol` in metadata/completion identifies
this condition. Strict-compliance flags from a tolerant trajectory do not
reconstruct a separate strict-model run, because the strict game would have
ended at its first fenced answer.

Validate the prepared configuration with the credential loaded:

```sh
source configs/mlcloud.local.env
uv run --locked python -m passgame.run \
  --config configs/dev-mlcloud-three-models-fence-tolerant.yaml --preflight
```

Freeze a new source snapshot before launching the next recorded experiment.
The completed strict study and its snapshot remain the original evidence.

Remove the credential from the shell when finished:

```sh
unset TUEBINGEN_API_KEY
```
