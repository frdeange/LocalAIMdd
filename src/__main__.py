"""Allow ``python -m src`` to run the BMS Operations system."""

import src.telemetry  # noqa: F401 — configure OTel before any MAF imports

from src.runner import cli

cli()
