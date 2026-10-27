# Reproducing the study

Reproduction uses the evaluation runner with either a hosted API or a model served
on a GPU cluster. Both routes send the same conversations and use the same
checker. Install the locked dependencies as described in the [README](../README.md).

## Study settings

The study uses 24 development base games, eight rules per game, and four fixed
orders: original, reverse, random_1, and random_2. Each model condition therefore
has 96 conversations and at most 768 responses. Earlier rules are repeated in
each latest message, and only successful model answers advance the game.

[Configurations](../configs/README.md) record the model ID, endpoint, parsing policy,
temperature, completion-token cap, thinking settings, API prices/budget, and
analysis seed. Keep model conditions separate. Completion limits include reasoning
and the final answer. The [run index](../results/RUNS.md) links each reported
condition to its configuration, checkpoint revision, serving details, and evidence.

## API evaluation

The supplied API configurations target the Tübingen ML Cloud chat-completions
endpoint and require an authorised account. Set `TUEBINGEN_API_KEY` in the shell:

```sh
export TUEBINGEN_API_KEY="YOUR_API_KEY"
uv run --locked python scripts/mlcloud_models.py
uv run --locked python -m passgame.run --config configs/api/qwen3.6-35b-a3b-nonthinking-16k.yaml --preflight
uv run --locked python -m passgame.run --config configs/api/qwen3.6-35b-a3b-nonthinking-16k.yaml
```

Check that the model is available to your account. Confirm current token prices
and set `budget_usd` before running. Reservations conservatively cover configured
input/output limits, including transport retries. No semantic retries are made.
Credentials are read from the environment variable named by `api_key_env` and are
not stored in configuration files. `.env` files are not loaded automatically.

To use another chat-completions API:

```sh
cp configs/api/qwen3.6-35b-a3b-nonthinking-16k.yaml configs/api.local.yaml
```

Edit `base_url`, `model_id`, `api_key_env`, verified prices/date, and spending ceiling.
Set a unique `study` and `output_dir`. Preserve the intended dataset, order track,
reminders, response policy, and generation parameters. Provider-specific reasoning
or chat-template fields must be supported by that endpoint. Run the same preflight
and evaluation commands with `--config configs/api.local.yaml`.

## Cluster evaluation

Use an allocated GPU node with Apptainer, `nvidia-smi`, `curl`, Git, and `uv`.
Serving libraries are contained in the vLLM image and are separate from the
lightweight evaluator requirements.

Download weights on a machine with internet access. The Qwen2.5-7B example uses the
recorded checkpoint revision:

```sh
# Use a separate download environment if needed.
python -m pip install huggingface_hub
hf download Qwen/Qwen2.5-7B-Instruct \
  --revision a09a35458c702b33eeacc393d103063234e8bc28 \
  --local-dir ../passgame-models/Qwen2.5-7B-Instruct
apptainer pull ../passgame-models/vllm-v0.24.0.sif docker://vllm/vllm-openai:v0.24.0
```

The [model repository](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct) and
[download CLI guide](https://huggingface.co/docs/huggingface_hub/en/guides/cli)
provide acquisition details. For another model, use its original repository,
recorded revision, tokenizer, and chat template. Served aliases in YAML are not
necessarily repository IDs. Obtain access and use `hf auth login` for gated weights.
Weights and unmodified third-party datasets stay outside the submitted repository.

On the cluster, point to the transferred weights and image:

```sh
export SIF=/absolute/path/to/vllm-v0.24.0.sif
export MODEL_DIR=/absolute/path/to/Qwen2.5-7B-Instruct
export SERVED_NAME=qwen2.5-7b-instruct
export CONFIG=configs/cluster/qwen2.5-7b-default-256.yaml
uv sync --locked
bash scripts/cluster/serve_and_eval.sh
```

This command requires an allocated GPU shell. For Slurm:

```sh
mkdir -p scripts/local logs
cp scripts/cluster/slurm.example.sbatch scripts/local/evaluate.sbatch
# Edit scheduler account/partition, GPU allocation, SIF, MODEL_DIR, SERVED_NAME, and CONFIG.
sbatch scripts/local/evaluate.sbatch
```

The serving helper starts vLLM, waits for its health endpoint, runs evaluation,
and stops the server when finished. It records runtime and GPU information in
logs. Match `PORT` to the YAML endpoint and `SERVED_NAME` to `model_id`. Set
`VLLM_EXTRA_ARGS` for tensor parallelism and the model's reasoning parser.
The model-specific `.sbatch` files show resource/parser settings used for the study;
[the run index](../results/RUNS.md) records available per-condition provenance.

Match the model's precision, quantisation, chat template, reasoning mode, context
length, completion budget, and GPU layout. The supplied image uses CUDA 13; use a
compatible driver/runtime. The [vLLM server guide](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html)
explains serving options. GPU requirements differ across models.

To evaluate an already running service, set the endpoint and served name in the
chosen cluster configuration and run `python -m passgame.run --config ...`.
Preflight does not establish server readiness or available GPU memory.

### Freeze and launch a cluster snapshot

The existing source packager and SSH launcher provide a reproducible source
snapshot when using the configured cluster workspace:

```sh
cp configs/cluster.example.env configs/cluster.local.env
chmod 600 configs/cluster.local.env
```

Fill in private SSH/workspace, scheduler, image, and model settings. Then:

```sh
uv run --locked python scripts/package_cluster.py \
  --config configs/cluster/qwen2.5-7b-default-256.yaml
bash run-cluster.sh --check
bash run-cluster.sh --new
```

For other weights, also pass `--model-dir /absolute/remote/weights` and
`--model-revision REVISION`. Set `PASSGAME_VLLM_EXTRA_ARGS` in the private settings,
or pass `--serving-args='--tensor-parallel-size 2 --reasoning-parser qwen3'` as
appropriate for the model. These arguments are recorded and forwarded to vLLM.
Set `PASSGAME_GPU_RESOURCE`, `PASSGAME_CPUS_PER_TASK`, `PASSGAME_MEMORY`, and
`PASSGAME_TIME_LIMIT` to match the allocation required by the condition.
The packager freezes code/config/data hashes and
preflights the snapshot. `--check` is local. `--new` submits a new job; running
`bash run-cluster.sh` without it resumes monitoring the same job. Configure the
scheduler resource request for the chosen model. Private settings are excluded.

## Data, analysis, and saved evidence

The synthetic dataset is included. Recreate it separately with seed 20261024:

```sh
uv run --locked python -m passgame.generate --seed 20261024 --output outputs/generated-data
```

Compare generated files with [data/manifest.json](../data/manifest.json). Random
orders are fixed per base identifier and shared across models. The generator uses
a separately seeded random-number stream for each base game.

Evaluation automatically writes `records.jsonl`, `metadata.json`, `completion.json`,
`analysis.json`, and CSV summaries into its configured output directory. To rerun
analysis with the study's 2,000 resamples and seed 20261008:

```sh
uv run --locked python -m passgame.analyze \
  outputs/qwen3.6-35b-a3b-nonthinking-16k/records.jsonl \
  --output outputs/analysis --repetitions 2000 --seed 20261008
```

Submitted evidence can be analyzed with the same module:

```sh
for run in results/runs/*; do
  uv run --locked python -m passgame.analyze "$run/records.jsonl" \
    --output "outputs/analysis/$(basename "$run")" --repetitions 2000 --seed 20261008 || break
done
```

Order effects pair final rule set, starting string, and horizon. Intervals are
percentile 95% paired bootstrap intervals. Offset `seed + 10 + 2*i + j` uses
comparison index `i = 0,1,2` for reverse/random_1/random_2 and endpoint `j = 0,1`
for whole-game success/successful turns. Stable episode ordering is retained.

Whole-game success requires all eight turns. Progress counts successful turns
before the first failure. Turn scores include all attempted answers, with explicit
retention/regression denominators. A complete execution includes failed games;
unrequested later turns are not fabricated. Infrastructure failures leave game
outcomes incomplete.

Each run preserves raw requests/responses and hashes. Reruns reuse responses only
under matching source, data, configuration, and request identities. Changed settings
require a fresh output directory. An interrupted request with an uncertain outcome
must be reconciled before resuming to avoid duplicate requests.

The reported study uses development games. Held-out model evaluation requires the
[human audit](audit-instructions.md), currently pending. Exact model revisions or
complete serving details that are unavailable are marked in the run index;
provider-managed models may change. Record the selected runtime and revision for
any new evaluation rather than assuming identical live inference.

## Dependency maintenance

After an intentional dependency update:

```sh
uv export --locked --all-groups --no-emit-project --format requirements-txt --output-file requirements.txt
```
