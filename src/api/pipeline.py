"""Run ingest → scorers → snapshot for ``rawdata/universal.csv`` workflows."""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml


class PipelineError(Exception):
    """Non-zero exit from a pipeline subprocess."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_rawdata_support_files(repo: Path) -> None:
    """Copy demo fixtures next to universal.csv when the user has none yet.

    ``systemic_daily.csv`` is episodic lab context for bio-age / trends and is
    independent of wearable rows in ``universal.csv``; replace with your own CSV
    when you have panels—uploading universal alone does not rebuild labs.
    """
    rd = repo / "rawdata"
    demo = repo / "data" / "examples" / "alex_demo"
    if not demo.is_dir():
        return
    rd.mkdir(parents=True, exist_ok=True)
    for name in ("profile.yaml", "context_flags.yaml", "systemic_daily.csv"):
        dest = rd / name
        src = demo / name
        if not dest.exists() and src.is_file():
            shutil.copy(src, dest)


def infer_until_date(universal_csv: Path) -> date:
    """Latest ``date`` column value in universal.csv."""
    if not universal_csv.is_file():
        raise PipelineError("rawdata/universal.csv missing after save")
    max_d: date | None = None
    with open(universal_csv, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise PipelineError("CSV has no header row")
        headers = {_normalize_header(h) for h in reader.fieldnames}
        if "date" not in headers:
            raise PipelineError('CSV must include a "date" column')
        for row in reader:
            raw = _get_cell(row, "date")
            if raw is None or str(raw).strip() == "":
                continue
            s = str(raw).strip()[:10]
            try:
                d = date.fromisoformat(s)
            except ValueError:
                continue
            if max_d is None or d > max_d:
                max_d = d
    if max_d is None:
        raise PipelineError("No rows with a valid ISO date (YYYY-MM-DD) in the date column")
    return max_d


def _normalize_header(h: str) -> str:
    return h.strip().lower()


def _get_cell(row: dict[str, str], canonical: str) -> str | None:
    for hk, hv in row.items():
        if _normalize_header(hk) == canonical.lower():
            return hv if hv is not None else ""
    return None


def run_health_pipeline(repo: Path) -> None:
    """
    Mirror ``Makefile`` ``demo-pipeline`` ordering with ``RAWDATA_ROOT=<repo>/rawdata``.
    """
    ensure_rawdata_support_files(repo)
    rd = repo / "rawdata"
    univ = rd / "universal.csv"
    until_d = infer_until_date(univ)
    until_s = until_d.isoformat()
    since_d = until_d - timedelta(days=120)
    since_s = since_d.isoformat()
    month_s = until_d.strftime("%Y-%m")

    profile = rd / "profile.yaml"
    cfg_profile = str(profile.resolve()) if profile.is_file() else str(
        (repo / "data/examples/alex_demo/profile.yaml").resolve()
    )
    ctx = rd / "context_flags.yaml"
    cfg_ctx = str(ctx.resolve()) if ctx.is_file() else str(
        (repo / "data/examples/alex_demo/context_flags.yaml").resolve()
    )
    daily = rd / "systemic_daily.csv"
    daily_csv = str(daily.resolve()) if daily.is_file() else str(
        (repo / "data/examples/alex_demo/systemic_daily.csv").resolve()
    )

    chrono = 30
    try:
        raw_p = yaml.safe_load(Path(cfg_profile).read_text(encoding="utf-8"))
        if isinstance(raw_p, dict) and isinstance(raw_p.get("age"), int):
            chrono = raw_p["age"]
    except Exception:
        pass

    base = os.environ.copy()
    base["RAWDATA_ROOT"] = str(rd.resolve())
    base["CONTEXT_FLAGS"] = cfg_ctx
    base["HEALTHOS_PROFILE"] = cfg_profile

    def sh(cmd: list[str], env: dict[str, str] | None = None) -> None:
        e = base if env is None else env
        r = subprocess.run(
            cmd,
            cwd=str(repo),
            env=e,
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            msg = r.stderr.strip() or r.stdout.strip() or f"exit {r.returncode}"
            raise PipelineError(f"{' '.join(cmd)}\n{msg}")

    py = sys.executable
    sh([py, "-m", "src.ingest.load_all", "--since", since_s])
    sh([py, "-m", "src.score.nlr_hrv_readiness", "--since", since_s, "--until", until_s])
    sh([py, "-m", "src.score.sri", "--since", since_s, "--until", until_s])
    sh([py, "-m", "src.score.aerobic_decoupling", "--since", since_s, "--until", until_s])

    comp_env = {k: v for k, v in os.environ.items() if k != "RAWDATA_ROOT"}
    comp_env["CONTEXT_FLAGS"] = cfg_ctx
    comp_env["HEALTHOS_PROFILE"] = cfg_profile
    sh(
        [py, "-m", "src.score.composite", "--since", since_s, "--until", until_s],
        env=comp_env,
    )

    bio_env = {k: v for k, v in os.environ.items() if k != "RAWDATA_ROOT"}
    bio_env["HEALTHOS_PROFILE"] = cfg_profile
    sh(
        [
            py,
            "-m",
            "src.score.bio_age",
            "--daily-csv",
            daily_csv,
            "--chronological-age",
            str(chrono),
        ],
        env=bio_env,
    )

    tr_env = {k: v for k, v in os.environ.items() if k != "RAWDATA_ROOT"}
    sh(
        [py, "-m", "src.trends", "--month", month_s, "--csv", daily_csv],
        env=tr_env,
    )

    int_env = {k: v for k, v in os.environ.items() if k != "RAWDATA_ROOT"}
    int_env["HEALTHOS_PROFILE"] = cfg_profile
    int_env["CONTEXT_FLAGS"] = cfg_ctx
    sh([py, "-m", "src.interventions", "--date", until_s], env=int_env)

    out_snap = repo / "web" / "src" / "data" / "snapshot.json"
    snap_env = {k: v for k, v in os.environ.items() if k != "RAWDATA_ROOT"}
    snap_env["CONTEXT_FLAGS"] = cfg_ctx
    snap_env["HEALTHOS_PROFILE"] = cfg_profile
    sh(
        [
            py,
            "-m",
            "src.report.snapshot_builder",
            "--date",
            until_s,
            "--out",
            str(out_snap.resolve()),
        ],
        env=snap_env,
    )
