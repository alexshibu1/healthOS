"""
src/ingest/config.py — central ingest configuration.

These are the only values a loader is allowed to read from outside
its own source file.  No loader hard-codes paths or timezones inline.

Timezone note
─────────────
JeFit SETTING.zonedifference = -4 (static, UTC-4).
Cross-checking SLEEP start/stop (UTC) against SLEEP_MINUTE local timestamps
shows UTC-5 in January is the internally consistent offset, which means
the user is on Eastern Time (EST = UTC-5 in winter, EDT = UTC-4 in summer).
"America/New_York" handles the DST boundary automatically.

If you are not on ET, override USER_TZ here before running any loader.
"""

from pathlib import Path

# IANA timezone for sources that record local time without an inline offset.
# Applies to: Amazfit SLEEP_MINUTE, Amazfit HEARTRATE_AUTO, Amazfit ACTIVITY_MINUTE.
# See schema.md §Timezone handling rule.
USER_TZ: str = "America/New_York"

# Absolute path to the rawdata/ directory.
# Loaders use this to compute source_file as a relative path (schema.md §provenance).
RAWDATA_ROOT: Path = Path(__file__).resolve().parent.parent.parent / "rawdata"
