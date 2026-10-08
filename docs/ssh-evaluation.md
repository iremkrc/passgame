# Open-weight model evaluation over SSH

Preparation status: code and configuration template are ready; host, exact models, GPU availability and serving environment are pending. No SSH connection, model download, server launch or remote model call has been attempted.

## Execution layout

Run the committed evaluator on the SSH execution machine. It sends conversation messages to a chat-completions-compatible model server in that same execution environment, such as vLLM. The template uses `http://127.0.0.1:8000/v1`; localhost refers to the remote execution environment, not the laptop. The server must be reachable from that environment. A host server and an evaluator inside a container do not necessarily share localhost.

vLLM documents a compatible frontend, chat-template selection and host/port configuration in its [serve reference](https://docs.vllm.ai/en/latest/cli/serve/). Serving-engine choice and version will be finalized against the selected model and GPU environment. Keep the benchmark's lightweight evaluation dependencies separate from the GPU serving environment.

## Pilot configuration

Use `configs/ssh-pilot.example.yaml` as the basis for `configs/experiment.yaml` on this preparation branch. Replace the model-ID placeholder with the exact served model name and confirm the endpoint, server context capacity and decoding settings. The template's 256 output tokens and temperature zero are proposed pilot settings, not established settings for an unspecified model. Reasoning models may require a larger completion budget; freeze it before the held-out study.

Select `deployment: self_hosted`, with both API token prices zero and `budget_usd: 0`. The ledger accounts for API token charges only. Set `api_key_env` to the name of a credential environment variable if server authentication is enabled; otherwise null is supported. Never place credentials in the config or URL.

Only native/order tracks are available to LLMs. Each turn reveals one new rule; original earlier turns and actual model responses stay in history. The evaluator tracks cumulative rules and interference privately. No scripted initial valid prefixes, cumulative rule reminder lists or all-at-once LLM prompts.

The development suite contains 12 native and 24 order episodes, each eight turns: 288 planned requests per model. Semantically incorrect answers are scored once, then carried forward when domain-valid. Transport retries have a fixed cap. The first pilot should establish serving compatibility, strict-format behavior, context fit, and runtime before committing the held-out model settings.

## Remote prerequisites and provenance

Confirm the target has an allocated GPU execution environment, Bash, tar, uv and a Python version compatible with the locked project (3.11 or newer). If the supplied SSH alias is a cluster login node, identify the GPU allocation and scheduler workflow before choosing the execution host. Confirm whether evaluation runs on the host or inside an existing container. Environment setup and any future server-startup recipe must live in committed scripts invoked by the existing fixed run contract.

Before launching, record the model weight revision, serving-engine version, chat template, precision/quantization, GPU type/count, context and completion limits, decoding settings and any reasoning mode. The runner logs exact messages and raw provider responses, including provider metadata, to preserve the measured conversation. GPU/model fit has not yet been verified.

Launch the recorded source snapshot through the project's SSH experiment backend. It reconstructs benchmark dependencies with `uv sync --locked`, then executes the existing configured command. Do not change the fixed command or run a model study directly from a mutable checkout. No remote inference has been launched during preparation.

The human review remains pending for the held-out model study. Zero API token charges do not mark the audit complete. This requirement does not prevent a development pilot.
