#!/bin/bash
# Frozen 16,384-token condition; one request at a time, 24 hours per repetition.
# Limit CUDA graph batch sizes to the evaluator's actual concurrency.
#SBATCH --job-name=passgame-gemma12b-16k
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=24:00:00
set -euo pipefail
: "${SLURM_SUBMIT_DIR:?Submit this script from the frozen snapshot root}"
export VLLM_EXTRA_ARGS="--tensor-parallel-size 1 --reasoning-parser gemma4 --max-num-seqs 1"
exec bash "$SLURM_SUBMIT_DIR/scripts/cluster/run_evaluation.sh"
