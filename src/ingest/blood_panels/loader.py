"""
src/ingest/blood_panels/loader.py

One-off loader for blood panel markdown files in this repository.
This is intentionally format-specific (not a generic markdown parser).
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Optional

from src.ingest.config import RAWDATA_ROOT
from src.ingest.schema import Observation, Reject, make_observation_id, validate_observation

_SOURCE = "blood_panel"
_METRIC_ANALYTE = "blood_panel_analyte"

# Superscript digits in lab unit strings (e.g. x10⁹/L, x10¹²/L)
_SUPER_TO_DIGIT: dict[str, str] = {
    "⁰": "0",
    "¹": "1",
    "²": "2",
    "³": "3",
    "⁴": "4",
    "⁵": "5",
    "⁶": "6",
    "⁷": "7",
    "⁸": "8",
    "⁹": "9",
}

_SECTION_ALIASES: dict[str, str] = {
    "cbc": "cbc",
    "complete blood count (cbc)": "cbc",
    "white blood cell differential": "white_blood_cell_differential",
    "white blood cell differential (relative)": "white_blood_cell_differential",
    "absolute cell counts": "absolute_cell_counts",
    "kidney & metabolic panel": "kidney_metabolic_panel",
    "electrolytes": "electrolytes",
}

_REQUIRED_COLUMNS = ("marker", "value", "reference range", "status")

_VALUE_RE = re.compile(r"^\s*([<>~]?)\s*([-+]?\d+(?:\.\d+)?)\s*(.*?)\s*$")


def raise_if_blood_panel_frontmatter_rejected(panel_md: Path, rejects: list[Reject]) -> None:
    """
    Used by load_all: missing or invalid YAML frontmatter is a hard failure.

    Why: draw_date and quality_flags are required for provenance; continuing
    with silent rejects would drop entire panels without surfacing a config error.
    """
    for r in rejects:
        if r.source_row_id == "frontmatter":
            raise ValueError(
                f"blood panel frontmatter invalid ({panel_md}): {r.reasons!r}"
            )


def load(
    panel_md: Path,
    rawdata_root: Optional[Path] = None,
) -> tuple[list[Observation], list[Reject]]:
    """
    Load one blood panel markdown file.

    Returns
    -------
    observations, rejects
        Parent draw row + analyte rows, and parse/validation rejects.
    """
    root = rawdata_root or RAWDATA_ROOT
    rel_path = _rel(panel_md, root)
    observations: list[Observation] = []
    rejects: list[Reject] = []

    text = panel_md.read_text(encoding="utf-8")
    frontmatter_lines, body_lines, fm_error = _split_frontmatter(text)
    if fm_error:
        rejects.append(
            Reject(
                source=_SOURCE,
                source_file=rel_path,
                source_row_id="frontmatter",
                raw_row={"file": rel_path},
                reasons=[fm_error],
            )
        )
        return observations, rejects

    fm, parse_err = _parse_frontmatter(frontmatter_lines)
    if parse_err:
        rejects.append(
            Reject(
                source=_SOURCE,
                source_file=rel_path,
                source_row_id="frontmatter",
                raw_row={"file": rel_path, "frontmatter": "\n".join(frontmatter_lines)},
                reasons=[parse_err],
            )
        )
        return observations, rejects

    draw_date_raw = str(fm.get("draw_date", "")).strip()
    quality_flags_raw = fm.get("quality_flags")
    if not draw_date_raw:
        rejects.append(
            Reject(
                source=_SOURCE,
                source_file=rel_path,
                source_row_id="frontmatter",
                raw_row=fm,
                reasons=["frontmatter missing required field: draw_date"],
            )
        )
        return observations, rejects

    if not isinstance(quality_flags_raw, list):
        rejects.append(
            Reject(
                source=_SOURCE,
                source_file=rel_path,
                source_row_id="frontmatter",
                raw_row=fm,
                reasons=["frontmatter missing required field: quality_flags(list)"],
            )
        )
        return observations, rejects

    try:
        draw_date = date.fromisoformat(draw_date_raw)
    except ValueError:
        rejects.append(
            Reject(
                source=_SOURCE,
                source_file=rel_path,
                source_row_id="frontmatter",
                raw_row=fm,
                reasons=[f"draw_date is not ISO YYYY-MM-DD: {draw_date_raw!r}"],
            )
        )
        return observations, rejects

    ts_utc = datetime.combine(draw_date, time(0, 0), tzinfo=timezone.utc)
    base_flags = _dedupe([str(f).strip() for f in quality_flags_raw if str(f).strip()])

    sections = _collect_section_lines(body_lines)
    parent_source_row_id = f"{draw_date_raw}:panel"
    parent_observation_id = make_observation_id(
        _SOURCE,
        rel_path,
        None,
        parent_source_row_id,
        "blood_panel_draw",
    )

    parent_payload = {
        "draw_date": draw_date_raw,
        "sections_present": sorted(sections.keys()),
    }
    for k, v in fm.items():
        if k not in ("draw_date", "quality_flags"):
            parent_payload[k] = v

    parent = Observation(
        observation_id=parent_observation_id,
        source=_SOURCE,
        source_file=rel_path,
        source_section=None,
        source_row_id=parent_source_row_id,
        cadence_kind="event",
        metric_kind="blood_panel_draw",
        ts_utc=ts_utc,
        tz_original="UTC",
        ts_original=draw_date_raw,
        source_confidence=1.0,
        quality_flags=list(base_flags),
        payload=parent_payload,
    )
    parent_errors = validate_observation(parent)
    if parent_errors:
        rejects.append(
            Reject(
                source=_SOURCE,
                source_file=rel_path,
                source_row_id=parent_source_row_id,
                raw_row=fm,
                reasons=parent_errors,
            )
        )
        return observations, rejects
    observations.append(parent)

    for section_slug, section_lines in sections.items():
        rows, table_err = _parse_section_table(section_lines)
        if table_err:
            rejects.append(
                Reject(
                    source=_SOURCE,
                    source_file=rel_path,
                    source_row_id=f"{draw_date_raw}:{section_slug}:header",
                    raw_row={"section": section_slug, "lines": section_lines},
                    reasons=[table_err],
                )
            )
            continue

        for row in rows:
            marker_display = row.get("marker", "").strip()
            if not marker_display:
                continue

            value_raw = row.get("value", "").strip()
            (
                value_numeric,
                value_text,
                value_unit,
                original_unit,
                row_flags,
                value_qualifier,
            ) = _parse_value(value_raw)

            marker_slug = _snake_case(marker_display)
            if value_numeric is not None and value_unit is None:
                value_unit = _infer_unit(section_slug, marker_slug)
            source_row_id = f"{draw_date_raw}:{section_slug}:{marker_slug}"
            observation_id = make_observation_id(
                _SOURCE,
                rel_path,
                section_slug,
                source_row_id,
                _METRIC_ANALYTE,
            )

            payload = {
                "analyte_slug": marker_slug,
                "marker_display_name": marker_display,
                "reference_range": row.get("reference range", "").strip() or None,
                "status_label": row.get("status", "").strip() or None,
                "original_unit": original_unit,
                "original_value_str": value_raw or None,
                "value_qualifier": value_qualifier,
            }

            obs = Observation(
                observation_id=observation_id,
                parent_event_id=parent_observation_id,
                source=_SOURCE,
                source_file=rel_path,
                source_section=section_slug,
                source_row_id=source_row_id,
                cadence_kind="event",
                metric_kind=_METRIC_ANALYTE,
                ts_utc=ts_utc,
                tz_original="UTC",
                ts_original=draw_date_raw,
                value_numeric=value_numeric,
                value_unit=value_unit,
                value_text=value_text,
                source_confidence=1.0,
                quality_flags=_dedupe(list(base_flags) + row_flags),
                payload=payload,
            )
            errors = validate_observation(obs)
            if errors:
                rejects.append(
                    Reject(
                        source=_SOURCE,
                        source_file=rel_path,
                        source_row_id=source_row_id,
                        raw_row=row,
                        reasons=errors,
                    )
                )
            else:
                observations.append(obs)

    return observations, rejects


def _split_frontmatter(text: str) -> tuple[list[str], list[str], Optional[str]]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return [], [], "missing leading YAML frontmatter delimiter '---'"

    end_idx: Optional[int] = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return [], [], "missing closing YAML frontmatter delimiter '---'"

    return lines[1:end_idx], lines[end_idx + 1 :], None


def _parse_frontmatter(lines: list[str]) -> tuple[dict, Optional[str]]:
    data: dict = {}
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped:
            i += 1
            continue
        if ":" not in raw:
            return {}, f"invalid frontmatter line (no key:value): {raw!r}"
        key, raw_val = raw.split(":", 1)
        key = key.strip()
        value = raw_val.strip()

        if value == "":
            # One-off expectation: empty value means a YAML list block.
            list_items: list[str] = []
            i += 1
            while i < len(lines):
                nxt = lines[i].strip()
                if not nxt:
                    i += 1
                    continue
                if nxt.startswith("- "):
                    list_items.append(_strip_quotes(nxt[2:].strip()))
                    i += 1
                    continue
                break
            data[key] = list_items
            continue

        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if not inner:
                data[key] = []
            else:
                data[key] = [_strip_quotes(v.strip()) for v in inner.split(",")]
            i += 1
            continue

        data[key] = _strip_quotes(value)
        i += 1

    return data, None


def _collect_section_lines(body_lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = defaultdict(list)
    current: Optional[str] = None
    for line in body_lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            heading = stripped[3:].strip().lower()
            current = _SECTION_ALIASES.get(heading)
            continue
        if current:
            sections[current].append(line)
    return sections


def _parse_section_table(lines: list[str]) -> tuple[list[dict[str, str]], Optional[str]]:
    header_cells: Optional[list[str]] = None
    out_rows: list[dict[str, str]] = []

    for raw in lines:
        stripped = raw.strip()
        if "|" not in stripped:
            continue
        cells = _split_pipe_row(stripped)
        if not cells:
            continue
        if _is_separator_row(cells):
            continue

        if header_cells is None:
            normalized_header = [c.lower() for c in cells]
            if not all(col in normalized_header for col in _REQUIRED_COLUMNS):
                return [], "section table header missing required columns"
            header_cells = normalized_header
            continue

        row = {header_cells[idx]: cells[idx] if idx < len(cells) else "" for idx in range(len(header_cells))}
        out_rows.append(row)

    if header_cells is None:
        return [], "no markdown table header found in section"
    return out_rows, None


def _split_pipe_row(line: str) -> list[str]:
    row = line.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [c.strip() for c in row.split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    if not cells:
        return False
    for c in cells:
        candidate = c.replace(":", "").replace(" ", "")
        if candidate and set(candidate) != {"-"}:
            return False
    return True


def _parse_value(raw: str) -> tuple[Optional[float], Optional[str], Optional[str], Optional[str], list[str], Optional[str]]:
    value = raw.strip()
    if not value:
        return None, None, None, None, ["empty_value"], None

    match = _VALUE_RE.match(value)
    if not match:
        return None, value, None, None, ["non_numeric_value"], None

    qualifier = match.group(1) or None
    number = float(match.group(2))
    unit_raw = (match.group(3) or "").strip() or None
    unit_norm = _normalize_unit(unit_raw) if unit_raw else None

    row_flags: list[str] = []
    if qualifier in (">", "<", "~"):
        row_flags.append("qualified_numeric_value")

    return number, None, unit_norm, unit_raw, row_flags, qualifier


def _normalize_unit(unit: str) -> str:
    normalized = unit.replace("×", "x")

    def repl_x10_super(m: re.Match[str]) -> str:
        sup = m.group(1)
        digits = "".join(_SUPER_TO_DIGIT.get(ch, ch) for ch in sup)
        return f"10^{digits}"

    # x10⁹/L, x10¹²/L → 10^9/L, 10^12/L
    normalized = re.sub(r"x10([⁰¹²³⁴⁵⁶⁷⁸⁹]+)", repl_x10_super, normalized)
    normalized = re.sub(r"\bx10\^([0-9]+)\b", r"10^\1", normalized)
    return normalized.strip()


def _infer_unit(section_slug: str, marker_slug: str) -> Optional[str]:
    """
    Fill a canonical unit when Value has a numeric value but no explicit unit.

    Why: schema validation requires value_numeric -> value_unit. This one-off
    loader can infer known units from section/marker for this fixed panel format.
    """
    if section_slug == "white_blood_cell_differential":
        return "ratio"
    if section_slug == "absolute_cell_counts":
        return "10^9/L"

    marker_units: dict[str, str] = {
        "hematocrit": "ratio",
        "anion_gap": "mmol/L",
        "egfr": "mL/min/1.73m2",
    }
    return marker_units.get(marker_slug)


def _snake_case(text: str) -> str:
    lower = text.strip().lower()
    lower = lower.replace("co₂", "co2")
    lower = re.sub(r"[^a-z0-9]+", "_", lower)
    lower = re.sub(r"_+", "_", lower)
    return lower.strip("_")


def _strip_quotes(s: str) -> str:
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            out.append(item)
            seen.add(item)
    return out


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()
