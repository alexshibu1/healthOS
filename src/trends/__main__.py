"""CLI: build ``data/trends/<YYYY-MM>.json`` from a systemic daily CSV."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from src.trends.mom import build_trends_from_daily_csv


def main() -> None:
    ap = argparse.ArgumentParser(description="Month-over-month trends JSON.")
    ap.add_argument("--month", required=True, help="Target month YYYY-MM.")
    ap.add_argument(
        "--csv",
        type=Path,
        required=True,
        help="Systemic daily CSV (see data/examples/systemic_daily_mock.csv).",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default HEALTHOS_TRENDS_DIR or data/trends).",
    )
    args = ap.parse_args()

    out = args.out_dir
    if out is None:
        env = os.environ.get("HEALTHOS_TRENDS_DIR")
        out = Path(env).expanduser().resolve() if env else None

    _, path = build_trends_from_daily_csv(
        args.csv,
        month_yyyy_mm=args.month,
        out_dir=out,
    )
    print(path)


if __name__ == "__main__":
    main()
