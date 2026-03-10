#!/bin/bash
# ── Ollama Model Init ────────────────────────────────────────
# Pulls the configured model into Ollama if not already present.
# Used as a one-shot init container in Docker Compose.
# ──────────────────────────────────────────────────────────────

set -e

MODEL="${OLLAMA_MODEL_ID:-qwen3.5:4b}"
HOST="${OLLAMA_HOST:-http://bms-ollama:11434}"

echo "⏳ Waiting for Ollama at ${HOST}..."
until curl -sf "${HOST}/api/tags" > /dev/null 2>&1; do
  sleep 2
done
echo "✅ Ollama is ready"

# Check if model is already pulled
if curl -sf "${HOST}/api/tags" | grep -q "\"${MODEL}\""; then
  echo "✅ Model '${MODEL}' already available"
else
  echo "⬇️  Pulling model '${MODEL}'..."
  ollama pull "${MODEL}"
  echo "✅ Model '${MODEL}' pulled successfully"
fi
