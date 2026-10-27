#!/bin/bash
# Template Slurm wrapper for scripts/cluster/serve_and_eval.sh. Copy it to
# scripts/local/<anything>.sbatch (gitignored), fill in the placeholders for
# your cluster and account, and submit from the repository root:
#
#   mkdir -p scripts/local logs && cp scripts/cluster/slurm.example.sbatch scripts/local/mine.sbatch
#   sbatch scripts/local/mine.sbatch
#   CONFIG=configs/cluster/qwen2.5-7b-default-256.yaml sbatch scripts/local/mine.sbatch
#
# One GPU with 40 GB fits models up to ~14B in bf16; set --gres=gpu:2 and
# VLLM_EXTRA_ARGS="--tensor-parallel-size 2" for larger ones.
#SBATCH --job-name=passgame
#SBATCH --partition=YOUR_GPU_PARTITION
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --output=logs/%x-%j.out
set -euo pipefail

# Slurm runs a copy of this file, so locate the repo from the submit directory.
cd "$SLURM_SUBMIT_DIR"

export SIF=${SIF:-/path/to/vllm-v0.24.0.sif}
export MODEL_DIR=${MODEL_DIR:-/path/to/models/Qwen2.5-7B-Instruct}
export SERVED_NAME=${SERVED_NAME:-qwen2.5-7b-instruct}
export CONFIG=${CONFIG:-configs/cluster/qwen2.5-7b-default-256.yaml}
export LOG_DIR=${LOG_DIR:-$PWD/logs}
# export UV_CACHE_DIR=/path/to/large/storage/.cache/uv
# export PATH="$HOME/.local/bin:$PATH"   # if uv is installed there

exec bash scripts/cluster/serve_and_eval.sh
