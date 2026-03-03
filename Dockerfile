# ── BMS Operations — Multi-Agent System ──────────────────────
FROM python:3.13-slim

WORKDIR /app

# Install git (needed for pip install from git repos)
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Default env (overridden by K8s ConfigMap/env)
ENV OLLAMA_HOST=http://ollama.shared-services.svc.cluster.local:11434
ENV OLLAMA_MODEL_ID=qwen2.5:7b
ENV PYTHONUNBUFFERED=1

# Entry point — demo mode by default; override CMD for interactive
ENTRYPOINT ["python", "-m", "src"]
CMD ["--demo"]
