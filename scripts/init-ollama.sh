#!/bin/bash
# ──────────────────────────────────────────────────────────────
# Ollama Model Initialization Script
# ──────────────────────────────────────────────────────────────
# Waits for the Ollama server to be ready, then pulls the model.
# Used as a one-shot init container in Docker Compose.
#
# Environment Variables:
#   OLLAMA_HOST      - Ollama server URL (default: http://ollama:11434)
#   OLLAMA_MODEL_ID  - Model to pull (default: phi4-mini)
# ──────────────────────────────────────────────────────────────

set -e

OLLAMA_HOST="${OLLAMA_HOST:-http://ollama:11434}"
OLLAMA_MODEL_ID="${OLLAMA_MODEL_ID:-qwen2.5:3b}"

echo "══════════════════════════════════════════════════════════"
echo "  Ollama Model Initialization"
echo "  Host:  ${OLLAMA_HOST}"
echo "  Model: ${OLLAMA_MODEL_ID}"
echo "══════════════════════════════════════════════════════════"

# ── Wait for Ollama server to be ready ────────────────────────
echo "⏳ Waiting for Ollama server at ${OLLAMA_HOST}..."

MAX_RETRIES=60
RETRY_INTERVAL=5
RETRIES=0

until ollama list > /dev/null 2>&1; do
    RETRIES=$((RETRIES + 1))
    if [ "$RETRIES" -ge "$MAX_RETRIES" ]; then
        echo "✘ Ollama server not ready after $((MAX_RETRIES * RETRY_INTERVAL))s — aborting"
        exit 1
    fi
    echo "  Retry ${RETRIES}/${MAX_RETRIES}..."
    sleep "$RETRY_INTERVAL"
done

echo "✓ Ollama server is ready"

# ── Check if model is already available ───────────────────────
if ollama list | grep -q "${OLLAMA_MODEL_ID}"; then
    echo "✓ Model '${OLLAMA_MODEL_ID}' is already available — skipping pull"
    exit 0
fi

# ── Pull the model ────────────────────────────────────────────
echo "📥 Pulling model '${OLLAMA_MODEL_ID}'... (this may take several minutes)"
ollama pull "${OLLAMA_MODEL_ID}"

echo "✓ Model '${OLLAMA_MODEL_ID}' pulled successfully"
echo "══════════════════════════════════════════════════════════"
