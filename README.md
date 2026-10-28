# PassGame

PassGame evaluates whether language models preserve accumulated constraints while updating a string. Each turn introduces one new rule. The model generates the next password, and the game ends at the first failed response. The study compares four rule orders for 24 development games across 19 model conditions.

## Repository contents

The submission contains the study implementation, configurations, dependency requirements, generated study data, and recorded responses and analyses.

| Path | Contents |
| --- | --- |
| [src/passgame/](src/passgame/README.md) | Python implementation: data generation, independent rule checkers, prompts, model adapters, evaluation, and analysis |
| [scripts/](scripts/README.md) and [run-cluster.sh](run-cluster.sh) | Model discovery, source packaging, cluster serving, scheduling, and job monitoring |
| [configs/](configs/README.md) | Seven hosted API and twelve self-hosted model conditions, plus a private cluster-settings template |
| [requirements.txt](requirements.txt) | Pinned evaluator and test dependencies with package hashes; exported from [uv.lock](uv.lock) |
| [pyproject.toml](pyproject.toml) | Python version, package metadata, runtime dependencies, and development dependencies |
| [data/](data/README.md) | Project-generated synthetic games, readable rules, and validation manifest |
| [results/](results/README.md) | Submitted raw model responses, provenance, completion accounting, and per-run analyses; [RUNS.md](results/RUNS.md) maps all conditions to evidence |
| [docs/](docs/) | [Protocol and scoring](docs/protocol.md), [reproduction instructions](docs/reproducibility.md), [reported results](docs/results.md), tables, and a figure |
| [tests/](tests/) | Checks for rules, data generation, protocol, model adapters, analysis, and cluster launchers |

Model weights and serving containers must be obtained separately and kept outside the submission. No external dataset is required: the included dataset was created by this project. Unmodified third-party datasets or model files must not be added to the submitted repository. New runs write to ignored `outputs/` directories; submitted study evidence is under `results/`.

## Setup

Use Python 3.11+, Git, and [uv](https://docs.astral.sh/uv/getting-started/installation/). Run commands from the repository root:

```sh
uv sync --locked
```

For pip, create a Python 3.11+ virtual environment, activate it, then run:

```sh
python -m pip install --require-hashes -r requirements.txt
python -m pip install --no-deps -e .
```

The evaluator uses `httpx` and `PyYAML`; the development dependencies include `pytest`. Analysis and data generation run locally without a GPU or API key. Self-hosted inference additionally needs a GPU environment and the separate vLLM serving container described below.

## Study entry points

Run each command with `uv run --locked` after setup, or use `python` directly in the activated pip environment.

| Command or script | Purpose |
| --- | --- |
| `python -m passgame.generate` | Generate and validate the synthetic dataset and write its hash manifest |
| `python -m passgame.run --config PATH` | Run the study, save requests/responses and provenance, and analyze results automatically |
| `python -m passgame.analyze RECORDS --output PATH` | Recompute scores, survival summaries, and paired bootstrap order comparisons from saved responses |
| `python scripts/mlcloud_models.py` | List hosted model IDs accessible to the configured account |
| `python scripts/package_cluster.py` | Freeze code, configuration, and data for a cluster run |
| `bash scripts/cluster/serve_and_eval.sh` | Start vLLM on an allocated GPU node, evaluate, and stop the server |

## Obtain or regenerate the dataset

The supplied [data/episodes.jsonl](data/episodes.jsonl) contains the 24 base games used in the study, each with one seeded episode and four order variants: 120 episodes in total. The reported study selects `split: development`, `tracks: [order]`, and eight rules, giving 96 conversations per model condition.

To regenerate the supplied data without replacing it:

```sh
uv run --locked python -m passgame.generate --seed 20261024 --output outputs/generated-data
```

The generator also writes games that were not evaluated. Keeping only the `"split": "development"` lines of the generated `episodes.jsonl` reproduces [data/episodes.jsonl](data/episodes.jsonl) byte for byte, and `development-games.txt` matches directly; compare both with the hashes in [data/manifest.json](data/manifest.json):

```sh
grep '"split": "development"' outputs/generated-data/episodes.jsonl | sha256sum
```

## Analyze the submitted results

The [saved evidence](results/README.md) contains 1,824 conversations and 10,919 attempted responses. Reproduce a run's analysis without downloading models or making API requests:

```sh
uv run --locked python -m passgame.analyze \
  results/runs/qwen3.6-35b-a3b-nonthinking-16k/records.jsonl \
  --output outputs/analysis/qwen3.6-35b-a3b-nonthinking-16k \
  --repetitions 2000 --seed 20261008
```

Use another run's `records.jsonl` to analyze that condition. The [reproducibility guide](docs/reproducibility.md#data-analysis-and-saved-evidence) also provides a loop over all submitted runs. The study uses 2,000 bootstrap resamples and seed 20261008, separately from the dataset-generation seed.

Analysis writes `analysis.json`, `summary.csv`, `interference-summary.csv`, `order-summary.csv`, `order-effects.csv`, and `order-survival.csv`. Archived analysis JSON may also contain legacy diagnostic fields that the current analyzer omits; compare study scores and tables rather than JSON bytes. See [docs/results.md](docs/results.md) for reported comparisons and [results/RUNS.md](results/RUNS.md) for model conditions and available provenance.

## Run through an API

The seven [API configurations](configs/api/) access provider-hosted models through the Tübingen ML Cloud endpoint; no local model download is needed. Obtain an authorised account and API key, then list the model IDs available to that account:

```sh
export TUEBINGEN_API_KEY="YOUR_API_KEY"
uv run --locked python scripts/mlcloud_models.py
```

Check the selected configuration's model access, token prices, and spending ceiling, then run preflight and evaluation:

```sh
uv run --locked python -m passgame.run --config configs/api/qwen3.6-35b-a3b-nonthinking-16k.yaml --preflight
uv run --locked python -m passgame.run --config configs/api/qwen3.6-35b-a3b-nonthinking-16k.yaml
```

For another compatible API, copy a configuration and edit its endpoint, model ID, credential environment-variable name, prices, and budget. Use a fresh output directory. Preflight checks configuration, data, and adapter settings without sending model requests; it does not verify live model availability. Credentials are read from the named environment variable; `.env` files are not loaded automatically.

## Run on a cluster

The twelve [cluster configurations](configs/cluster/) use separately obtained checkpoints. Download the matching weights and vLLM container on a machine with internet access, keeping both outside this repository. For example, the Qwen2.5-7B checkpoint revision used by the source packager can be obtained with:

```sh
# Install the download utility in a separate environment if needed.
python -m pip install huggingface_hub
hf download Qwen/Qwen2.5-7B-Instruct \
  --revision a09a35458c702b33eeacc393d103063234e8bc28 \
  --local-dir ../passgame-models/Qwen2.5-7B-Instruct
apptainer pull ../passgame-models/vllm-v0.24.0.sif docker://vllm/vllm-openai:v0.24.0
```

For other checkpoints, use the original model repository and the revision listed in [results/RUNS.md](results/RUNS.md) where available. Match the recorded precision, quantisation, tokenizer, chat template, and reasoning mode. A served model alias in YAML may differ from its download repository ID. Gated models require access approval and authentication with `hf auth login`. The [reproducibility guide](docs/reproducibility.md#cluster-evaluation) links the download and serving documentation and explains model-specific settings.

On a GPU cluster with Apptainer, `nvidia-smi`, `curl`, Git, and `uv`, transfer the weights and image, then prepare the Slurm serving/evaluation script:

```sh
mkdir -p scripts/local logs
cp scripts/cluster/slurm.example.sbatch scripts/local/evaluate.sbatch
```

Set your scheduler partition/account, model and image paths, served model name, and configuration in the copied script. Submit from the repository root:

```sh
sbatch scripts/local/evaluate.sbatch
```

The script starts vLLM, waits for readiness, evaluates the model, and stops the server. Model-specific `.sbatch` files provide resource and parser examples. The [reproducibility guide](docs/reproducibility.md) also covers direct GPU-shell execution and the source-snapshot workflow using `package_cluster.py` and `run-cluster.sh`.

## Obtain new results

Each API or cluster evaluation saves these artifacts to its configured `output_dir` under `outputs/`:

| Artifact | Contents |
| --- | --- |
| `records.jsonl` | Requests, raw responses, rule scores, and response provenance |
| `metadata.json` | Effective configuration and code, configuration, and dataset hashes |
| `events.jsonl`, `budget.json` | Request lifecycle and spending accounting |
| `completion.json` | Planned and observed games/responses, skipped turns, and completion status |
| `analysis.json` and CSV files | Automatically computed scores and paired bootstrap estimates |

Use the same analysis command above with the new run's `records.jsonl` to recompute its statistics. A game ends at its first model failure; later turns are unattempted. Check `completion.json` to distinguish completed games from infrastructure or budget interruptions. Use a fresh output directory when changing code, data, or configuration, and keep the submitted evidence directories intact.

Historical checkpoint revisions or complete serving details that were unavailable are marked in the run index. Provider-managed models may change, so new inference is not guaranteed to produce the recorded responses.

## Checks

```sh
uv run --locked pytest -q
```
