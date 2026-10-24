# Open-weight model evaluation over SSH

Galvani has prepared Qwen2.5-7B-Instruct weights and a vLLM 0.24.0 container. Jobs 2993023 and 2996659 are historical v2 studies. The current v3 study uses neutral seeds, progressive eight-rule games, previous-rule reminders and first-failure termination. Its model pilot has not yet been launched.

## Execution layout

Run the committed evaluator on the SSH execution machine. It sends conversation messages to a chat-completions-compatible model server in that same execution environment, such as vLLM. The template uses `http://127.0.0.1:8000/v1`; localhost refers to the remote execution environment, not the laptop. The server must be reachable from that environment. A host server and an evaluator inside a container do not necessarily share localhost.

vLLM documents a compatible frontend, chat-template selection and host/port configuration in its [serve reference](https://docs.vllm.ai/en/latest/cli/serve/). Serving-engine choice and version will be finalized against the selected model and GPU environment. Keep the benchmark's lightweight evaluation dependencies separate from the GPU serving environment.

## Pilot configuration

Copy `configs/cluster.example.env` to `configs/cluster.local.env` and configure it privately on each machine. It supplies the SSH alias, remote workspace, scheduler account/partition, container, and model paths. The local file and generated runtime settings are git-ignored; the private source file is excluded from snapshots. Use placeholders in shared instructions and review generated archives/logs before sharing them.

Use `configs/ssh-pilot.example.yaml` as the basis for `configs/experiment.yaml` on this preparation branch. Replace the model-ID placeholder with the exact served model name and confirm the endpoint, server context capacity and decoding settings. The template's 256 output tokens and temperature zero are proposed pilot settings, not established settings for an unspecified model. Reasoning models may require a larger completion budget; freeze it before the held-out study.

Select `deployment: self_hosted`, with both API token prices zero and `budget_usd: 0`. The ledger accounts for API token charges only. Set `api_key_env` to the name of a credential environment variable if server authentication is enabled; otherwise null is supported. Never place credentials in the config or URL.

The v3 dataset supports seeded/order tracks. Legacy v2 native/order/fixed_start tracks remain for historical comparisons. Each turn reveals one new rule; original earlier turns and actual model responses stay in history. With remind_previous_rules: true, the latest message also repeats every earlier rule using its original ID and description. Future rules, reference outputs and certificates remain private. Scripted assistant prefixes and all-at-once LLM prompts remain excluded. The optional configs/dev-qwen2.5-7b-eight-rules-no-reminders.yaml disables reminders and writes to a separate output directory.

Use configs/dev-qwen2.5-7b-eight-rules.yaml with dataset_dir data/sequential-v3, track seeded, rule_count: 8 and remind_previous_rules: true. Initialize from the explicit neutral seed once, then carry successful model outputs forward. Stop on the first rule, format, or domain failure before the next request. There are 24 distinct development games and at most 192 requests; held-out has 120 games and at most 960 requests. Private valid example paths have certified early challenges by turns 3–5; actual model inputs are independently certified and need not follow those examples. Results go to outputs/dev-qwen2.5-7b-progressive-eight-rules-v3. Held-out audit requirements still apply.

From a fresh checkout, build the archive with uv run --locked python scripts/package_pilot.py. This packages the tracked scripts/run_galvani_fixed_start.sh wrapper and a generated, shell-quoted configs/pilot-runtime.env, freezes a Git commit and runs preflight inside that snapshot. No prior ignored archive is required. Then run bash run-pilot.sh --check and bash run-pilot.sh --new. The launcher verifies v3 neutral initialization, eight rules and reminders. It preserves previous job state/results and rejects incompatible snapshots.

For another model, copy the main config, change name/model_id/output_dir, and call the packager with --config configs/YOUR-CONFIG.yaml --model-dir /absolute/Galvani/weights --model-revision REVISION. The packager derives SERVED_NAME from model_id and requires explicit weights/revision for a different model, preventing an alias change from silently continuing to serve Qwen. Container/uv/weights must already exist on Galvani. The generic scripts/serve_and_eval.sh remains available for other sites and GPU layouts.

The v3 order suite has a ready configuration, configs/dev-qwen2.5-7b-v3-order.yaml. It contains 96 development and 480 held-out games, four permutations per original episode, using the same seed/final set and separate fresh conversations. Package it with uv run --locked python scripts/package_pilot.py --config configs/dev-qwen2.5-7b-v3-order.yaml, then run bash run-pilot.sh --check and bash run-pilot.sh --new. The packager accepts seeded or order with reminders enabled. The order run has its own output directory, dev-qwen2.5-7b-v3-order. Failed model answers terminate their episode; infrastructure missingness remains separate. Per-order summary, survival and paired success/progress contrasts are saved as order-summary.csv, order-survival.csv and order-effects.csv.

## Remote prerequisites and provenance

Confirm the target has an allocated GPU execution environment, Bash, tar, uv and a Python version compatible with the locked project (3.11 or newer). If the supplied SSH alias is a cluster login node, identify the GPU allocation and scheduler workflow before choosing the execution host. Confirm whether evaluation runs on the host or inside an existing container. Environment setup and any future server-startup recipe must live in committed scripts invoked by the existing fixed run contract.

Before launching a new model, record its weight revision, serving-engine version, chat template, precision/quantization, GPU type/count, context and completion limits, decoding settings and any reasoning mode. The runner logs exact messages and raw provider responses. The pinned Qwen configuration has been exercised on Galvani; other model/GPU combinations need development validation.

Launch the recorded source snapshot with run-pilot.sh. It reconstructs dependencies with uv sync --locked, then executes the packaged configuration. Keep historical snapshots immutable; the new v3 study needs a new snapshot and output directory.

The human review remains pending for the held-out model study. Zero API token charges do not mark the audit complete. This requirement does not prevent a development pilot.
