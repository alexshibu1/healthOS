"""Shared paths for score outputs (parquet). Override with HEALTHOS_SCORES_DIR."""

from __future__ import annotations

import os
from pathlib import Path


def scores_dir() -> Path:
    env = os.environ.get("HEALTHOS_SCORES_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "data" / "scores"
