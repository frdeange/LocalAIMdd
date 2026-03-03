# ── BMS API — FastAPI + MAF Workflow + Frontends ─────────────
FROM python:3.13-slim

WORKDIR /app

# Install git (needed for MAF pip install from GitHub)
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Install MAF dependencies (agent core)
COPY requirements.txt ./requirements-maf.txt
RUN pip install --no-cache-dir -r requirements-maf.txt

# Install BMS API dependencies
COPY bms_api/requirements.txt ./requirements-api.txt
RUN pip install --no-cache-dir -r requirements-api.txt

# Copy application code
COPY src/ ./src/
COPY bms_api/ ./bms_api/
COPY mcp_services/__init__.py ./mcp_services/__init__.py
COPY frontend/ ./frontend/

ENV PYTHONUNBUFFERED=1
ENV API_HOST=0.0.0.0
ENV API_PORT=8000

EXPOSE 8000

CMD ["python", "-m", "bms_api.main"]
