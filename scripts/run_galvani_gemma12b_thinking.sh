#!/bin/bash
# Submit from the frozen snapshot root with private account/partition flags.
#SBATCH --job-name=passgame-gemma12b-think
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=08:00:00
set -euo pipefail
: "${SLURM_SUBMIT_DIR:?Submit this script from the frozen snapshot root}"
export VLLM_EXTRA_ARGS="--tensor-parallel-size 1 --reasoning-parser gemma4"
exec bash "$SLURM_SUBMIT_DIR/scripts/run_galvani_fixed_start.sh"
