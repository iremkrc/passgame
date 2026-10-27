#!/bin/bash
# Frozen 16,384-token condition; one request at a time, 24 hours per repetition.
# Limit CUDA graph batch sizes to the evaluator's actual concurrency.
#SBATCH --job-name=passgame-qwen27b-16k
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:a100:2
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=24:00:00
set -euo pipefail
: "${SLURM_SUBMIT_DIR:?Submit this script from the frozen snapshot root}"
export VLLM_EXTRA_ARGS="--tensor-parallel-size 2 --reasoning-parser qwen3 --language-model-only --max-num-seqs 1"
exec bash "$SLURM_SUBMIT_DIR/scripts/cluster/run_evaluation.sh"
