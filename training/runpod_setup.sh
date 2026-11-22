#!/usr/bin/env bash
# ==============================================================================
# RunPod 1-Command Automated Setup & Training for Lensetek Edge-Loop-3B
# ==============================================================================

set -e

echo "=== [1/3] Installing Unsloth & High-Performance Dependencies ==="
pip install --upgrade --no-cache-dir pip
pip install --no-deps "unsloth[cu121-ampere-torch240] @ git+https://github.com/unslothai/unsloth.git"
pip install datasets trl bitsandbytes transformers accelerate huggingface_hub

echo "=== [2/3] Verifying GPU Environment ==="
nvidia-smi

echo "=== [3/3] Starting Training Pipeline ==="
# Ensure HF_TOKEN is exported before running
python train_runpod.py
