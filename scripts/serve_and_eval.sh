#!/bin/bash
# Serve one open-weight model with vLLM (apptainer image) on this GPU node and
# run the PassGame evaluator against it. Scheduler- and site-independent: call
# it from an interactive GPU shell or from a batch wrapper such as
# scripts/slurm.example.sbatch. The config's base_url must point at
# http://127.0.0.1:$PORT/v1 and its model_id must equal $SERVED_NAME.
#
# Required environment:
#   SIF          vLLM apptainer image, e.g. built from docker://vllm/vllm-openai:<tag>
#   MODEL_DIR    local model weights (compute nodes may have no internet)
#   SERVED_NAME  name vLLM serves the model under (= model_id in CONFIG)
#   CONFIG       evaluator config, e.g. configs/dev-qwen2.5-7b.yaml; several
#                space-separated configs run one after another on the same server
# Optional:
#   LOG_DIR         where the vLLM server log goes   (default: <repo>/logs)
#   MAX_MODEL_LEN   vLLM context length, >= max_input_tokens in CONFIG (default: 32768)
#   PORT            server port                       (default: 8000)
#   MIN_CUDA_MAJOR  CUDA major version the image's torch needs; 0 skips the check
#                   (default: 13, for vLLM 0.24.0 / torch cu130)
#   BIND_PATHS      extra comma-separated paths to bind into the container
#   VLLM_EXTRA_ARGS extra arguments for `vllm serve`, e.g. "--tensor-parallel-size 2"
# Requires apptainer, curl, nvidia-smi and uv on PATH; run `uv sync --locked` first.
set -euo pipefail

: "${SIF:?set SIF}" "${MODEL_DIR:?set MODEL_DIR}" "${SERVED_NAME:?set SERVED_NAME}" "${CONFIG:?set CONFIG}"
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
LOG_DIR=${LOG_DIR:-$REPO/logs}
MAX_MODEL_LEN=${MAX_MODEL_LEN:-32768}
PORT=${PORT:-8000}
MIN_CUDA_MAJOR=${MIN_CUDA_MAJOR:-13}
VLLM_CACHE_ROOT=${VLLM_CACHE_ROOT:-${XDG_CACHE_HOME:-$HOME/.cache}/vllm}
read -r -a CONFIGS <<< "$CONFIG"
RUN_TAG=$(basename "${CONFIGS[0]}" .yaml)-${SLURM_JOB_ID:-manual}-$(date +%Y%m%d-%H%M%S)
VLLM_LOG=$LOG_DIR/vllm-$RUN_TAG.log
mkdir -p "$LOG_DIR" "$VLLM_CACHE_ROOT"

BINDS="$MODEL_DIR,$VLLM_CACHE_ROOT${BIND_PATHS:+,$BIND_PATHS}"

echo "[job] node=$(hostname) model=$MODEL_DIR served=$SERVED_NAME sif=$SIF config=$CONFIG vllm_log=$VLLM_LOG"

# 0) GPU and driver check: an image built for a newer CUDA than the driver
#    supports dies during engine init, so fail early with a clear message.
nvidia-smi -L
DRIVER_CUDA=$(nvidia-smi | sed -n 's/.*CUDA Version: *\([0-9.]*\).*/\1/p' | head -1)
echo "[job] driver $(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1) supports CUDA $DRIVER_CUDA"
if [ "${DRIVER_CUDA%%.*}" -lt "$MIN_CUDA_MAJOR" ]; then
    echo "[job] driver too old for $SIF (needs CUDA >= $MIN_CUDA_MAJOR); use an older image or another node"; exit 1
fi
apptainer exec --nv --cleanenv "$SIF" nvidia-smi -L

# 1) Start vLLM in the background. --cleanenv keeps host-only settings (such
#    as SSL_CERT_FILE) out of the container; pass through only what it needs.
# shellcheck disable=SC2086  # VLLM_EXTRA_ARGS is intentionally word-split
apptainer exec --nv --cleanenv --bind "$BINDS" \
    --env HF_HUB_OFFLINE=1 --env TRANSFORMERS_OFFLINE=1 \
    --env VLLM_CACHE_ROOT="$VLLM_CACHE_ROOT" --env PYTHONUNBUFFERED=1 \
    "$SIF" \
    vllm serve "$MODEL_DIR" \
        --served-model-name "$SERVED_NAME" \
        --host 127.0.0.1 --port "$PORT" \
        --dtype bfloat16 --max-model-len "$MAX_MODEL_LEN" \
        --seed 20261008 ${VLLM_EXTRA_ARGS:-} \
    > "$VLLM_LOG" 2>&1 &
VLLM_PID=$!
trap 'kill $VLLM_PID 2>/dev/null || true; wait $VLLM_PID 2>/dev/null || true' EXIT

# 2) Wait for the server (up to 15 minutes).
for _ in $(seq 1 180); do
    if curl -sf "http://127.0.0.1:$PORT/health" >/dev/null; then break; fi
    if ! kill -0 "$VLLM_PID" 2>/dev/null; then
        echo "[job] vLLM exited during startup; tail of $VLLM_LOG:"; tail -50 "$VLLM_LOG"; exit 1
    fi
    sleep 5
done
curl -sf "http://127.0.0.1:$PORT/v1/models" || { echo "[job] vLLM not ready after 15 min"; exit 1; }
echo

# 3) Provenance for the report.
apptainer exec --cleanenv "$SIF" python3 -c "import vllm, torch; print('[job] vllm', vllm.__version__, 'torch', torch.__version__)"
echo "[job] git $(git -C "$REPO" rev-parse HEAD) dirty=$(git -C "$REPO" status --porcelain | wc -l)"

# 4) Run the evaluator once per config. Exit code 2 = handled incomplete run
#    (see completion.json); the job exits with the highest status seen.
cd "$REPO"
STATUS=0
for config in "${CONFIGS[@]}"; do
    set +e
    uv run --locked python -m passgame.run --config "$config"
    status=$?
    set -e
    echo "[job] evaluator exit $status for $config"
    if [ "$status" -gt "$STATUS" ]; then STATUS=$status; fi
done
exit $STATUS
