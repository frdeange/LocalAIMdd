"""
Speech Service Configuration
=============================
"""

import os

# ── Server ────────────────────────────────────────────────────
SPEECH_HOST: str = os.getenv("SPEECH_HOST", "0.0.0.0")
SPEECH_PORT: int = int(os.getenv("SPEECH_PORT", "8092"))

# ── Whisper STT ───────────────────────────────────────────────
WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "small")
WHISPER_DEVICE: str = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE: str = os.getenv("WHISPER_COMPUTE", "int8")
WHISPER_LANGUAGE: str = os.getenv("WHISPER_LANGUAGE", "es")

# ── Piper TTS ─────────────────────────────────────────────────
PIPER_MODEL_PATH: str = os.getenv(
    "PIPER_MODEL_PATH",
    os.path.join(os.path.dirname(__file__), "models", "es_ES-davefx-medium.onnx"),
)
