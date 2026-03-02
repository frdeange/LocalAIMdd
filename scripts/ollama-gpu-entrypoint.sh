#!/bin/bash
# ──────────────────────────────────────────────────────────────
# GPU Entrypoint for Ollama
# ──────────────────────────────────────────────────────────────
# WSL2 + Docker Desktop can be slow to initialize CUDA on first
# access, causing Ollama's 30-second GPU discovery to timeout.
#
# This script "warms up" the CUDA runtime by calling nvidia-smi
# before starting Ollama, so the GPU is already initialized when
# Ollama's discovery runs.
# ──────────────────────────────────────────────────────────────

echo "=== Warming up CUDA runtime ==="

# Try nvidia-smi up to 3 times to ensure CUDA is initialized
for i in 1 2 3; do
    if nvidia-smi > /dev/null 2>&1; then
        echo "✓ CUDA runtime ready (attempt $i)"
        nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null
        break
    else
        echo "⏳ Waiting for CUDA (attempt $i/3)..."
        sleep 5
    fi
done

echo "=== Starting Ollama ==="
exec /bin/ollama serve
