"""Build a deterministic LLM handoff prompt from snapshot + profile + health reasoning skill."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import textwrap
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import calendar
import yaml

_WRAP_WIDTH = 92


def _parse_scoring_date(snapshot: dict[str, Any]) -> date:
    mt = snapshot.get("monthlyTrajectory") or {}
    month_label = str(mt.get("month", "")).strip()
    dom = int(mt.get("todayDayOfMonth", 1))
    m = re.match(r"^([A-Za-z]+)\s+(\d{4})$", month_label)
    if not m:
        raise ValueError(f"Cannot parse monthlyTrajectory.month: {month_label!r}")
    month_name, year_s = m.group(1), int(m.group(2))
    month_num = list(calendar.month_name).index(month_name)
    if month_num == 0:
        raise ValueError(f"Unknown month name: {month_name!r}")
    last = calendar.monthrange(year_s, month_num)[1]
    day = min(dom, last)
    return date(year_s, month_num, day)


def _confidence_from_today_reasoning(today_reasoning: str) -> str:
    m = re.search(r"confidence\s*`([0-9.]+)`", today_reasoning)
    if m:
        return m.group(1)
    return "unavailable"


def _wrap_fill(text: str, width: int = _WRAP_WIDTH) -> str:
    """Hard-wrap long lines for plain-text LLM prompts (readability in any client)."""
    if not text.strip():
        return text
    return "\n".join(
        textwrap.fill(
            text,
            width=width,
            break_long_words=True,
            break_on_hyphens=False,
        ).splitlines()
    )


def _nlr_reading(fh: dict[str, Any]) -> str:
    disp = fh.get("displayScore")
    score = fh.get("score")
    tier = str(fh.get("tier", "unknown"))
    age = fh.get("dataAgeDays", "—")
    if isinstance(disp, str) and disp.strip() and disp.strip() != "—":
        primary = disp.strip()
    elif tier == "unknown":
        primary = "— (wedge not numerically available)"
    elif score is None:
        primary = "—"
    else:
        primary = str(score)
    return "\n".join(
        [
            "Lens 1 — NLR × HRV  (inflammation + autonomic / training-readiness wedge)",
            f"  Headline value:  {primary}",
            f"  Tier:            {tier}",
            f"  Data age:        {age}d  (staleness for blood-anchored or HRV context)",
        ]
    )


def _sri_reading(fh: dict[str, Any]) -> str:
    score = fh.get("score", "—")
    tier = str(fh.get("tier", "unknown"))
    win = fh.get("windowDays", "—")
    return "\n".join(
        [
            "Lens 2 — Sleep Regularity Index  (circadian timing consistency)",
            f"  Score (0–100):   {score}",
            f"  Tier:            {tier}",
            f"  Rolling window:  {win} days",
        ]
    )


def _decoup_reading(fh: dict[str, Any]) -> str:
    z = fh.get("displayZscore")
    if z is None:
        z = fh.get("zscore")
    tier = str(fh.get("tier", "unknown"))
    win = fh.get("windowDays", "—")
    return "\n".join(
        [
            "Lens 3 — Aerobic decoupling trend  (pace:HR economy vs fatigue)",
            f"  Z-score / band:  {z}",
            f"  Tier:            {tier}",
            f"  Rolling window:  {win} days",
        ]
    )


def _three_lenses_block(snap: dict[str, Any]) -> str:
    fs = snap.get("flagship") or {}
    nlr = fs.get("nlrHrv") or {}
    sri = fs.get("sri") or {}
    dec = fs.get("decoupling") or {}
    return "\n\n".join(
        [_nlr_reading(nlr), _sri_reading(sri), _decoup_reading(dec)]
    )


def _active_divergence_block(snap: dict[str, Any]) -> str:
    div = snap.get("divergence") or {}
    if not div.get("triggered"):
        return (
            "No pattern flagged — either lenses agree, or the divergence chapter "
            "is inactive for this scoring date."
        )
    pat = str(div.get("pattern", "")).strip()
    reasoning = str(div.get("reasoning", "")).strip()
    lines: list[str] = [f"Pattern name:  {pat or '—'}"]
    if reasoning:
        lines.append("")
        lines.append("What it means (from the report):")
        lines.append(_wrap_fill(reasoning))
    drivers = div.get("drivers") or []
    if drivers:
        lines.append("")
        lines.append("Contributing signals:")
        for d in drivers:
            sig = str(d.get("signal", "")).strip()
            val = str(d.get("value", "")).strip()
            note = str(d.get("note", "")).strip()
            if note and val:
                item = f"  • {sig}: {val}  |  {note}"
            elif val:
                item = f"  • {sig}: {val}"
            else:
                item = f"  • {sig}"
            lines.append(item)
    return "\n".join(lines).strip()


def _window_overlaps(
    start: date, end: date, window_start: date, window_end: date
) -> bool:
    return window_end >= start and window_start <= end


def _recent_context_lines(scoring_date: date, repo_root: Path) -> list[str]:
    """Bulleted context flags for the last 14 days; uses CONTEXT_FLAGS if set."""
    path_s = os.environ.get("CONTEXT_FLAGS")
    if not path_s:
        return []
    path = Path(path_s).expanduser()
    if not path.is_file():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    start = scoring_date - timedelta(days=14)
    bullets: list[str] = []

    for key, label in (
        ("illness_windows", "Illness"),
        ("travel_windows", "Travel"),
        ("injury_windows", "Injury"),
    ):
        for w in raw.get(key) or []:
            try:
                ws = date.fromisoformat(str(w.get("start", ""))[:10])
                we = date.fromisoformat(str(w.get("end", ""))[:10])
            except ValueError:
                continue
            if not _window_overlaps(start, scoring_date, ws, we):
                continue
            note = str(w.get("note", "")).strip()
            bullets.append(
                f"{label}: {ws.isoformat()} – {we.isoformat()}"
                + (f" — {note}" if note else "")
            )
    return bullets


def _extract_framework(skill_text: str) -> str:
    """Operational logic from Section 4 only (no citation blocks)."""
    m = re.search(
        r"(## Section 4: How these three integrate.*?)(?=\n## Section 5:)",
        skill_text,
        flags=re.DOTALL,
    )
    if not m:
        return (
            "(Framework excerpt missing — check skills/health-reasoning.md "
            "Section 4.)"
        )
    block = m.group(1).strip()
    # Drop the divergence matrix table — keep narrative / convergence rules only.
    cut = re.search(r"\n### 4\.1 Divergence matrix\n", block)
    if cut:
        block = block[: cut.start()].strip()
    # Avoid duplicating an LLM-section heading; body starts at the narrative.
    block = re.sub(
        r"^## Section 4: How these three integrate\s*\n+",
        "",
        block,
        count=1,
    )
    return block.strip()


def _profile_paragraph(profile: dict[str, Any]) -> str:
    age = profile.get("age", "—")
    sex = profile.get("sex", "—")
    mod = profile.get("primary_training_modality", profile.get("training_modality", "—"))
    goal = profile.get("primary_goal", "—")
    return (
        f"Age {age}, sex {sex}. Training modality: {mod}. Primary goal: {goal}."
    )


def build_recommendation_prompt(
    snapshot_path: Path,
    profile_path: Path,
    skill_path: Path,
) -> str:
    snap = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    profile = yaml.safe_load(Path(profile_path).read_text(encoding="utf-8")) or {}
    skill_text = Path(skill_path).read_text(encoding="utf-8")

    scoring_date = _parse_scoring_date(snap)
    date_s = scoring_date.isoformat()

    state = str(snap.get("state", "unknown"))
    score = snap.get("score", 0)
    tr = str(snap.get("todayReasoning", "")).strip()
    conf = _confidence_from_today_reasoning(tr)

    repo_root = Path(snapshot_path).resolve().parent.parent.parent.parent
    recent_bullets = _recent_context_lines(scoring_date, repo_root)
    recent_block = (
        "\n".join(f"- {b}" for b in recent_bullets)
        if recent_bullets
        else "No flagged windows"
    )

    framework = _extract_framework(skill_text)

    subline = str(snap.get("subline", "")).strip()
    action_hint = str(snap.get("action", "")).strip()
    dashboard_bits: list[str] = []
    # Avoid repeating the card subline when it is already embedded in todayReasoning.
    if subline and subline not in tr:
        dashboard_bits.append(f"Dashboard card subline: {_wrap_fill(subline)}")
    if action_hint:
        dashboard_bits.append(f"Dashboard suggested stance: {_wrap_fill(action_hint)}")
    dashboard_extra = ""
    if dashboard_bits:
        dashboard_extra = "\n\n" + "\n\n".join(dashboard_bits)

    reading_body = "\n".join(
        [
            f"Snapshot date:           {date_s}",
            f"Composite state label:    {state}",
            f"Composite score (0–100): {score}   (interpret alongside label — may be withheld)",
            f"Model confidence:        {conf}",
            "",
            "Scorer rationale (verbatim):",
            _wrap_fill(tr),
            dashboard_extra,
        ]
    ).strip()

    parts: list[str] = [
        "## Health Intelligence Report — Recommendation Request",
        "",
        "Paste this entire message into your assistant as **user context**. The sections below",
        "are intentionally redundant where helpful — prefer the labeled \"Today's reading\"",
        "block when interpreting headline severity.",
        "",
        "---",
        "",
        "## Your role",
        "",
        "You are a sports physician and decision-theory analyst reviewing a personal health",
        "intelligence report exported from the user's healthOS dashboard.",
        "",
        "Task:",
        "  • Recommend exactly **three** interventions for the **next 14 days**.",
        "  • Rank them by **impact per unit of effort** (not raw difficulty alone).",
        "  • Tie each recommendation to **one or more** of the three flagship lenses",
        "    (NLR×HRV, SRI, aerobic decoupling) using **specific numbers from this prompt**.",
        "  • Be concrete enough that the user could start tomorrow morning without guessing.",
        "",
        "## The user",
        "",
        _profile_paragraph(profile),
        "",
        f"## Today's reading ({date_s})",
        "",
        reading_body,
        "",
        "## Three flagship lenses",
        "",
        "Interpret each lens independently first; then consider convergence vs divergence",
        "(see Active divergence). Units match the user's dashboard export.",
        "",
        _three_lenses_block(snap),
        "",
        "## Active divergence",
        "",
        _active_divergence_block(snap),
        "",
        "## Recent context",
        "",
        "Annotated calendar windows from context_flags (overlap with last 14 days of snapshot date):",
        "",
        recent_block,
        "",
        "## The framework you should reason within",
        "",
        "Use this operational framing (not legal/medical advice — illustrative physiology layer):",
        "",
        framework,
        "",
        "## Output format",
        "",
        "Follow this contract exactly so the response is scannable in any chat client.",
        "",
        "1) Emit **exactly 3** interventions, numbered 1–3.",
        "2) Sort by **impact ÷ effort** (descending): intervention #1 = best ROI.",
        "",
        "For **each** intervention, copy these labels on their own lines:",
        "",
        "**ACTION** — One sentence; actionable tomorrow without new equipment unless unavoidable.",
        "**WHY** — Name the lens (NLR×HRV / SRI / aerobic decoupling) and cite **which field**",
        "           above supports this (e.g. tier, score, z-score, divergence pattern).",
        "**EFFORT** — Integer **1** (trivial) through **5** (heavy lifestyle lift).",
        "**EXPECTED IMPACT** — Which metric moves, in **what direction**, over roughly **how long**.",
        "",
        "After item 3, add:",
        "",
        "**CLARIFYING QUESTION** — One question whose answer would materially sharpen your next pass.",
        "",
        "Do not add extra sections beyond what is listed above.",
    ]
    return "\n".join(parts) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Write LLM recommendation prompt to a file.")
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--profile", type=Path, default=None)
    ap.add_argument("--skill", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    rr = Path(args.snapshot).resolve().parent.parent.parent.parent
    profile = args.profile or Path(
        os.environ.get("HEALTHOS_PROFILE", rr / "profile.yaml")
    )
    skill = args.skill or rr / "skills" / "health-reasoning.md"

    try:
        text = build_recommendation_prompt(args.snapshot, profile, skill)
    except Exception as err:  # noqa: BLE001 — CLI surfaces build failures
        print(str(err), file=sys.stderr)
        sys.exit(1)

    outp = args.out.expanduser().resolve()
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(text, encoding="utf-8")
    print(f"Wrote {outp}")


if __name__ == "__main__":
    main()
