# Open-weight model evaluation over SSH

Galvani has a prepared Qwen2.5-7B-Instruct revision and vLLM 0.24.0 container. A corrected mixed-length, stop-on-first-failure pilot completed as job 2993023. The current study selects eight-rule games and repeats previous rules on each turn. It uses a fresh source snapshot and output directory; earlier history-only and reset studies remain separate.

## Execution layout

Run the committed evaluator on the SSH execution machine. It sends conversation messages to a chat-completions-compatible model server in that same execution environment, such as vLLM. The template uses `http://127.0.0.1:8000/v1`; localhost refers to the remote execution environment, not the laptop. The server must be reachable from that environment. A host server and an evaluator inside a container do not necessarily share localhost.

vLLM documents a compatible frontend, chat-template selection and host/port configuration in its [serve reference](https://docs.vllm.ai/en/latest/cli/serve/). Serving-engine choice and version will be finalized against the selected model and GPU environment. Keep the benchmark's lightweight evaluation dependencies separate from the GPU serving environment.

## Pilot configuration

Use `configs/ssh-pilot.example.yaml` as the basis for `configs/experiment.yaml` on this preparation branch. Replace the model-ID placeholder with the exact served model name and confirm the endpoint, server context capacity and decoding settings. The template's 256 output tokens and temperature zero are proposed pilot settings, not established settings for an unspecified model. Reasoning models may require a larger completion budget; freeze it before the held-out study.

Select `deployment: self_hosted`, with both API token prices zero and `budget_usd: 0`. The ledger accounts for API token charges only. Set `api_key_env` to the name of a credential environment variable if server authentication is enabled; otherwise null is supported. Never place credentials in the config or URL.

Native/order and fixed_start tracks are available to LLMs. Each turn reveals one new rule; original earlier turns and actual model responses stay in history. With remind_previous_rules: true, the latest message also repeats every earlier rule using its original ID and description. Future rules and certificates remain private. Scripted assistant prefixes and all-at-once LLM prompts remain excluded. The optional configs/dev-qwen2.5-7b-eight-rules-no-reminders.yaml disables reminders and writes to a separate output directory.

Use configs/dev-qwen2.5-7b-eight-rules.yaml with rule_count: 8 and remind_previous_rules: true. Initialize each conversation once, then carry successful model outputs forward without resets. Stop on the first rule, format, or domain failure and do not reveal the next rule. There are 24 development games with eight scheduled rules each and at most 192 requests per model; held-out has 120 games and at most 960 requests. All six families and intended interference degrees one/two/three are retained. Recompute interference from actual incoming states; initial-case labels and reminders do not guarantee later interference. Results go to outputs/dev-qwen2.5-7b-eight-rules-reminders-stop-on-failure. Held-out audit requirements still apply.

The current packaged launcher verifies eight-rule selection and the cumulative-rule-reminder protocol, and reads its configuration/result paths from the snapshot manifest. On the Mac, run bash run-pilot.sh --check to validate the package, then bash run-pilot.sh --new to submit a fresh study. This reuses the prepared weights/container and preserves prior results; do not launch from an archived source snapshot with another prompt condition.

The development suite contains 12 native and 24 order episodes with an eight-turn maximum: at most 288 requests per model. Failed model answers are scored once and terminate that episode; later stages remain unattempted. Infrastructure missingness is reported separately. Transport retries have a fixed cap. The first pilot should establish serving compatibility, strict-format behavior, context fit, and runtime before committing held-out settings.

## Remote prerequisites and provenance

Confirm the target has an allocated GPU execution environment, Bash, tar, uv and a Python version compatible with the locked project (3.11 or newer). If the supplied SSH alias is a cluster login node, identify the GPU allocation and scheduler workflow before choosing the execution host. Confirm whether evaluation runs on the host or inside an existing container. Environment setup and any future server-startup recipe must live in committed scripts invoked by the existing fixed run contract.

Before launching, record the model weight revision, serving-engine version, chat template, precision/quantization, GPU type/count, context and completion limits, decoding settings and any reasoning mode. The runner logs exact messages and raw provider responses, including provider metadata, to preserve the measured conversation. GPU/model fit has not yet been verified.

Launch the recorded source snapshot through the project's SSH experiment backend. It reconstructs benchmark dependencies with `uv sync --locked`, then executes the existing configured command. Do not change the fixed command or run a model study directly from a mutable checkout. No remote inference has been launched during preparation.

The human review remains pending for the held-out model study. Zero API token charges do not mark the audit complete. This requirement does not prevent a development pilot.
