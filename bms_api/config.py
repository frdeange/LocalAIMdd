"""
BMS API Configuration
=====================
Environment-driven settings for the BMS REST API.
"""

import os

# ── Database ──────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://bms_ops:BmsOps2026@localhost:5432/bms_ops",
)

# ── Server ────────────────────────────────────────────────────
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))
