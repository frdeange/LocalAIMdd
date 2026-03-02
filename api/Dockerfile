FROM python:3.13-slim

WORKDIR /app

# Install system dependencies (curl for healthcheck, git for MAF)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl git && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN opentelemetry-bootstrap -a install

# Copy API server code
COPY api/ ./api/

# Copy shared src/ package (agents, workflows, config, telemetry)
COPY src/ ./src/

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=15s \
    CMD curl -f http://localhost:8000/api/health || exit 1

# OTel-instrumented uvicorn
ENTRYPOINT ["opentelemetry-instrument", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
