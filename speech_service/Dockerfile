# ── Speech Service (STT + TTS, GPU) ──────────────────────────
# Uses NVIDIA CUDA runtime for GPU-accelerated Whisper inference
FROM nvidia/cuda:12.6.3-runtime-ubuntu24.04

# Install Python 3
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv curl && \
    ln -sf /usr/bin/python3 /usr/bin/python && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies
COPY speech_service/requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

# Download Piper Spanish voice model during build
RUN mkdir -p models && \
    curl -sL -o models/es_ES-davefx-medium.onnx \
        "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx" && \
    curl -sL -o models/es_ES-davefx-medium.onnx.json \
        "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx.json"

# Pre-download Whisper model during build (avoids runtime download)
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')" || true

# Copy application code
COPY speech_service/__init__.py ./speech_service/__init__.py
COPY speech_service/config.py ./speech_service/config.py
COPY speech_service/telemetry.py ./speech_service/telemetry.py
COPY speech_service/main.py ./speech_service/main.py

ENV PYTHONUNBUFFERED=1
ENV SPEECH_HOST=0.0.0.0
ENV SPEECH_PORT=8092
ENV WHISPER_MODEL=small
ENV WHISPER_DEVICE=cuda
ENV WHISPER_COMPUTE=float16
ENV PIPER_MODEL_PATH=/app/models/es_ES-davefx-medium.onnx

EXPOSE 8092

CMD ["python", "-m", "uvicorn", "speech_service.main:app", "--host", "0.0.0.0", "--port", "8092"]
