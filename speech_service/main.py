"""
Speech Service — STT + TTS (FastAPI)
=====================================
Offline speech processing: faster-whisper (STT) + Piper TTS.

Endpoints:
- POST /stt  — audio file → transcribed text (Spanish)
- POST /tts  — text → synthesised WAV audio (Spanish)
- GET  /health — health check
- GET  /metrics — Prometheus metrics
"""

import io
import logging
import time
import wave
from contextlib import asynccontextmanager

from speech_service.telemetry import configure_telemetry

configure_telemetry()

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from prometheus_client import (
    Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST,
)

from speech_service.config import (
    SPEECH_HOST, SPEECH_PORT,
    WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE, WHISPER_LANGUAGE,
    PIPER_MODEL_PATH,
)

logger = logging.getLogger(__name__)

# ── Prometheus Metrics ────────────────────────────────────────

stt_requests = Counter("speech_stt_requests_total", "STT transcription requests")
stt_errors = Counter("speech_stt_errors_total", "STT transcription errors")
stt_duration = Histogram(
    "speech_stt_duration_seconds", "STT transcription duration",
    buckets=[0.1, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0],
)

tts_requests = Counter("speech_tts_requests_total", "TTS synthesis requests")
tts_errors = Counter("speech_tts_errors_total", "TTS synthesis errors")
tts_duration = Histogram(
    "speech_tts_duration_seconds", "TTS synthesis duration",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
)

# ── Model holders (lazy loaded) ──────────────────────────────

_whisper_model = None
_piper_voice = None


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        logger.info("Loading Whisper model: %s (device=%s, compute=%s)",
                     WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE)
        _whisper_model = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE,
                                       compute_type=WHISPER_COMPUTE)
        logger.info("Whisper model loaded")
    return _whisper_model


def _get_piper():
    global _piper_voice
    if _piper_voice is None:
        from piper import PiperVoice
        logger.info("Loading Piper voice: %s", PIPER_MODEL_PATH)
        _piper_voice = PiperVoice.load(PIPER_MODEL_PATH)
        logger.info("Piper voice loaded (sample_rate=%d)", _piper_voice.config.sample_rate)
    return _piper_voice


# ── Lifespan ──────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-load models on startup
    _get_piper()
    logger.info("Speech service ready (Whisper loads on first request)")
    yield
    logger.info("Speech service stopped")


app = FastAPI(
    title="BMS Speech Service",
    version="0.1.0",
    description="Offline STT (faster-whisper) + TTS (Piper) for Spanish",
    lifespan=lifespan,
)


# ── Health ────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "speech-service",
        "stt_model": WHISPER_MODEL,
        "tts_model": PIPER_MODEL_PATH.split("/")[-1],
        "language": WHISPER_LANGUAGE,
    }


# ── Metrics ───────────────────────────────────────────────────

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ── STT: Audio → Text ────────────────────────────────────────

class STTResponse(BaseModel):
    text: str
    language: str
    confidence: float
    duration_seconds: float


@app.post("/stt", response_model=STTResponse)
async def speech_to_text(audio: UploadFile = File(...)):
    """Transcribe audio file to text using faster-whisper (Spanish)."""
    stt_requests.inc()
    start = time.perf_counter()

    try:
        # Save uploaded file to temp
        audio_bytes = await audio.read()
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            model = _get_whisper()
            segments, info = model.transcribe(
                tmp_path,
                language=WHISPER_LANGUAGE,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )
            text = " ".join(seg.text.strip() for seg in segments)
        finally:
            os.unlink(tmp_path)

        elapsed = time.perf_counter() - start
        stt_duration.observe(elapsed)

        return STTResponse(
            text=text,
            language=info.language,
            confidence=round(info.language_probability, 3),
            duration_seconds=round(elapsed, 3),
        )

    except Exception as e:
        stt_errors.inc()
        logger.error("STT error: %s", e)
        raise HTTPException(status_code=500, detail=f"STT error: {e}")


# ── TTS: Text → Audio ────────────────────────────────────────

class TTSRequest(BaseModel):
    text: str


@app.post("/tts")
async def text_to_speech(body: TTSRequest):
    """Synthesise text to WAV audio using Piper TTS (Spanish)."""
    tts_requests.inc()
    start = time.perf_counter()

    try:
        voice = _get_piper()

        buf = io.BytesIO()
        wav_file = wave.open(buf, "wb")
        voice.synthesize_wav(body.text, wav_file)
        wav_file.close()

        elapsed = time.perf_counter() - start
        tts_duration.observe(elapsed)

        return Response(
            content=buf.getvalue(),
            media_type="audio/wav",
            headers={
                "X-Duration-Seconds": str(round(elapsed, 3)),
                "X-Text-Length": str(len(body.text)),
            },
        )

    except Exception as e:
        tts_errors.inc()
        logger.error("TTS error: %s", e)
        raise HTTPException(status_code=500, detail=f"TTS error: {e}")


# ── Entry point ──────────────────────────────────────────────

def main():
    import uvicorn
    uvicorn.run(
        "speech_service.main:app",
        host=SPEECH_HOST,
        port=SPEECH_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
