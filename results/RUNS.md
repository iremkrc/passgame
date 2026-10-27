# Run index

| Condition | Route | Configuration | Evidence |
| --- | --- | --- | --- |
| DeepSeek-V4.1-Flash / Off / 16384 tokens | API | [YAML](../configs/api/deepseek-v4.1-flash-nonthinking-16k.yaml) | [deepseek-v4.1-flash-nonthinking-16k](runs/deepseek-v4.1-flash-nonthinking-16k/) |
| DeepSeek-V4.1-Flash / On / 4096 tokens | API | [YAML](../configs/api/deepseek-v4.1-flash-thinking-4k.yaml) | [deepseek-v4.1-flash-thinking-4k](runs/deepseek-v4.1-flash-thinking-4k/) |
| Gemma 4-12B / Off / 4096 tokens | Cluster | [YAML](../configs/cluster/gemma4-12b-nonthinking-4k.yaml) | [gemma4-12b-nonthinking-4k](runs/gemma4-12b-nonthinking-4k/) |
| Gemma 4-12B / On / 16384 tokens | Cluster | [YAML](../configs/cluster/gemma4-12b-thinking-16k.yaml) | [gemma4-12b-thinking-16k](runs/gemma4-12b-thinking-16k/) |
| Gemma 4-12B / On / 4096 tokens | Cluster | [YAML](../configs/cluster/gemma4-12b-thinking-4k.yaml) | [gemma4-12b-thinking-4k](runs/gemma4-12b-thinking-4k/) |
| Gemma 4-26B-A4B / Off / 4096 tokens | Cluster | [YAML](../configs/cluster/gemma4-26b-a4b-nonthinking-4k.yaml) | [gemma4-26b-a4b-nonthinking-4k](runs/gemma4-26b-a4b-nonthinking-4k/) |
| Gemma 4-31B / Off / 16384 tokens | API | [YAML](../configs/api/gemma4-31b-nonthinking-16k.yaml) | [gemma4-31b-nonthinking-16k](runs/gemma4-31b-nonthinking-16k/) |
| Gemma 4-31B / On / 4096 tokens | API | [YAML](../configs/api/gemma4-31b-thinking-4k.yaml) | [gemma4-31b-thinking-4k](runs/gemma4-31b-thinking-4k/) |
| Qwen2.5-14B / Default / 256 tokens | Cluster | [YAML](../configs/cluster/qwen2.5-14b-default-256.yaml) | [qwen2.5-14b-default-256](runs/qwen2.5-14b-default-256/) |
| Qwen2.5-32B / Default / 256 tokens | Cluster | [YAML](../configs/cluster/qwen2.5-32b-default-256.yaml) | [qwen2.5-32b-default-256](runs/qwen2.5-32b-default-256/) |
| Qwen2.5-7B / Default / 256 tokens | Cluster | [YAML](../configs/cluster/qwen2.5-7b-default-256.yaml) | [qwen2.5-7b-default-256](runs/qwen2.5-7b-default-256/) |
| Qwen3.5-27B / Off / 256 tokens | Cluster | [YAML](../configs/cluster/qwen3.5-27b-nonthinking-256.yaml) | [qwen3.5-27b-nonthinking-256](runs/qwen3.5-27b-nonthinking-256/) |
| Qwen3.5-9B / Off / 256 tokens | Cluster | [YAML](../configs/cluster/qwen3.5-9b-nonthinking-256.yaml) | [qwen3.5-9b-nonthinking-256](runs/qwen3.5-9b-nonthinking-256/) |
| Qwen3.6-27B / Off / 16384 tokens | Cluster | [YAML](../configs/cluster/qwen3.6-27b-nonthinking-16k.yaml) | [qwen3.6-27b-nonthinking-16k](runs/qwen3.6-27b-nonthinking-16k/) |
| Qwen3.6-27B / On / 16384 tokens | Cluster | [YAML](../configs/cluster/qwen3.6-27b-thinking-16k.yaml) | [qwen3.6-27b-thinking-16k](runs/qwen3.6-27b-thinking-16k/) |
| Qwen3.6-27B / On / 4096 tokens | Cluster | [YAML](../configs/cluster/qwen3.6-27b-thinking-4k.yaml) | [qwen3.6-27b-thinking-4k](runs/qwen3.6-27b-thinking-4k/) |
| Qwen3.6-35B-A3B / Off / 16384 tokens | API | [YAML](../configs/api/qwen3.6-35b-a3b-nonthinking-16k.yaml) | [qwen3.6-35b-a3b-nonthinking-16k](runs/qwen3.6-35b-a3b-nonthinking-16k/) |
| Qwen3.6-35B-A3B / On / 16384 tokens | API | [YAML](../configs/api/qwen3.6-35b-a3b-thinking-16k.yaml) | [qwen3.6-35b-a3b-thinking-16k](runs/qwen3.6-35b-a3b-thinking-16k/) |
| Qwen3.6-35B-A3B / On / 4096 tokens | API | [YAML](../configs/api/qwen3.6-35b-a3b-thinking-4k.yaml) | [qwen3.6-35b-a3b-thinking-4k](runs/qwen3.6-35b-a3b-thinking-4k/) |

## Execution provenance

Unavailable checkpoint revisions or complete serving settings are marked explicitly. Exact request parameters and code/configuration/data hashes are in each run's metadata and the manifest.

### gemma4-12b-nonthinking-4k

- Checkpoint revision: `1d2c2d7f2466070e69d6fb3fd5ce9a7d75f2f6ee`
- Source commit: `6cabe0c387dda9420a14b0eca52428c53eb2732e`
- Serving image: `vllm/vllm-openai:v0.24.0`
- Additional server arguments: unavailable.
- Responses: 2026-10-24T15:26:14.176987+00:00 to 2026-10-24T15:27:46.735906+00:00.

### gemma4-26b-a4b-nonthinking-4k

- Checkpoint revision: `4d7ae4984b7db7de8f8457170b3f1a419ee76d52`
- Source commit: `4883fb94e359d7ec1b32a0f1d86f5729d070aa1e`
- Serving image: `vllm/vllm-openai:v0.24.0`
- Additional server arguments: unavailable.
- Responses: 2026-10-24T15:52:33.551310+00:00 to 2026-10-24T15:54:15.119471+00:00.

### gemma4-12b-thinking-16k

- Checkpoint revision: `1d2c2d7f2466070e69d6fb3fd5ce9a7d75f2f6ee`
- Source commit: `2ec340f9d034356ee8d66ee091f2adb471f3282e`
- Serving image: `vllm/vllm-openai:v0.24.0`
- Additional server arguments: `--tensor-parallel-size 1 --reasoning-parser gemma4 --max-num-seqs 1`
- Responses: 2026-10-25T00:20:41.435184+00:00 to 2026-10-25T04:29:51.468806+00:00.

### qwen3.6-27b-thinking-16k

- Checkpoint revision: `6a9e13bd6fc8f0983b9b99948120bc37f49c13e9`
- Source commit: `632b15a447ff73abe9c57acb62a0d33b7d149078`
- Serving image: `vllm/vllm-openai:v0.24.0`
- Additional server arguments: `--tensor-parallel-size 2 --reasoning-parser qwen3 --language-model-only --max-num-seqs 1`
- Responses: 2026-10-25T02:30:54.288934+00:00 to 2026-10-25T09:07:42.634271+00:00.

### qwen3.6-27b-nonthinking-16k

- Checkpoint revision: `6a9e13bd6fc8f0983b9b99948120bc37f49c13e9`
- Source commit: `67e7d0c9e94f0e378e071efb60e25be4b4d982f7`
- Serving image: `vllm/vllm-openai:v0.24.0`
- Additional server arguments: `--tensor-parallel-size 2 --reasoning-parser qwen3 --language-model-only --max-num-seqs 1`
- Responses: 2026-10-25T10:13:07.309061+00:00 to 2026-10-25T10:16:36.438406+00:00.

### gemma4-31b-thinking-4k

- Checkpoint revision: unavailable.
- Source commit: unavailable.
- Serving image: unavailable.
- Additional server arguments: unavailable.
- Responses: 2026-10-24T14:23:25.375862+00:00 to 2026-10-24T16:20:52.746602+00:00.

### qwen3.6-35b-a3b-thinking-4k

- Checkpoint revision: unavailable.
- Source commit: unavailable.
- Serving image: unavailable.
- Additional server arguments: unavailable.
- Responses: 2026-10-24T14:23:25.375849+00:00 to 2026-10-24T17:45:10.818482+00:00.

### deepseek-v4.1-flash-thinking-4k

- Checkpoint revision: unavailable.
- Source commit: unavailable.
- Serving image: unavailable.
- Additional server arguments: unavailable.
- Responses: 2026-10-24T14:23:25.375885+00:00 to 2026-10-24T14:44:23.290789+00:00.

### gemma4-31b-nonthinking-16k

- Checkpoint revision: unavailable.
- Source commit: unavailable.
- Serving image: unavailable.
- Additional server arguments: unavailable.
- Responses: 2026-10-25T12:50:23.428116+00:00 to 2026-10-25T14:24:32.825714+00:00.

### qwen3.6-35b-a3b-nonthinking-16k

- Checkpoint revision: unavailable.
- Source commit: unavailable.
- Serving image: unavailable.
- Additional server arguments: unavailable.
- Responses: 2026-10-25T12:50:23.428153+00:00 to 2026-10-25T12:56:47.699164+00:00.

### deepseek-v4.1-flash-nonthinking-16k

- Checkpoint revision: unavailable.
- Source commit: unavailable.
- Serving image: unavailable.
- Additional server arguments: unavailable.
- Responses: 2026-10-25T12:50:23.428079+00:00 to 2026-10-25T12:57:13.737839+00:00.

### qwen3.6-35b-a3b-thinking-16k

- Checkpoint revision: unavailable.
- Source commit: unavailable.
- Serving image: unavailable.
- Additional server arguments: unavailable.
- Responses: 2026-10-24T22:07:55.622077+00:00 to 2026-10-25T02:21:22.336197+00:00.

### qwen2.5-7b-default-256

- Checkpoint revision: unavailable.
- Source commit: unavailable.
- Serving image: unavailable.
- Additional server arguments: unavailable.
- Responses: 2026-10-25T18:15:57.739619+00:00 to 2026-10-25T18:16:42.821963+00:00.

### qwen2.5-14b-default-256

- Checkpoint revision: unavailable.
- Source commit: unavailable.
- Serving image: unavailable.
- Additional server arguments: unavailable.
- Responses: 2026-10-25T18:19:18.058181+00:00 to 2026-10-25T18:20:55.532759+00:00.

### qwen2.5-32b-default-256

- Checkpoint revision: unavailable.
- Source commit: unavailable.
- Serving image: unavailable.
- Additional server arguments: unavailable.
- Responses: 2026-10-25T23:51:55.960755+00:00 to 2026-10-25T23:54:22.104032+00:00.

### qwen3.5-9b-nonthinking-256

- Checkpoint revision: unavailable.
- Source commit: unavailable.
- Serving image: unavailable.
- Additional server arguments: unavailable.
- Responses: 2026-10-25T18:20:14.283122+00:00 to 2026-10-25T18:21:55.125700+00:00.

### qwen3.5-27b-nonthinking-256

- Checkpoint revision: unavailable.
- Source commit: unavailable.
- Serving image: unavailable.
- Additional server arguments: unavailable.
- Responses: 2026-10-25T18:23:47.034489+00:00 to 2026-10-25T18:27:20.560319+00:00.

### qwen3.6-27b-thinking-4k

- Checkpoint revision: `6a9e13bd6fc8f0983b9b99948120bc37f49c13e9`
- Source commit: `0c31be9a8bf3d750ab443618112c01564c1f361b`
- Serving image: `vllm/vllm-openai:v0.24.0`
- Additional server arguments: unavailable.
- Responses: 2026-10-24T16:07:23.817507+00:00 to 2026-10-24T20:28:25.862500+00:00.

### gemma4-12b-thinking-4k

- Checkpoint revision: `1d2c2d7f2466070e69d6fb3fd5ce9a7d75f2f6ee`
- Source commit: `2ecda875e8f21345f08e8318f000cf38b824ef9d`
- Serving image: `vllm/vllm-openai:v0.24.0`
- Additional server arguments: unavailable.
- Responses: 2026-10-24T17:50:15.009039+00:00 to 2026-10-24T20:50:09.092197+00:00.

