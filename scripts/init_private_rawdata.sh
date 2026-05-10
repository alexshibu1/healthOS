#!/usr/bin/env bash
# Create a local rawdata/ skeleton (gitignored). Safe to run multiple times.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RD="$ROOT/rawdata"

mkdir -p "$RD/amazfit helio/SLEEP"
mkdir -p "$RD/amazfit helio/SLEEP_MINUTE"
mkdir -p "$RD/amazfit helio/HEARTRATE_AUTO"
mkdir -p "$RD/amazfit helio/ACTIVITY"
mkdir -p "$RD/amazfit helio/ACTIVITY_MINUTE"
mkdir -p "$RD/amazfit helio/ACTIVITY_STAGE"
mkdir -p "$RD/amazfit helio/BODY"
mkdir -p "$RD/strava"
mkdir -p "$RD/blood_panels"
mkdir -p "$RD/notes"

cat >"$RD/README.txt" <<'EOF'
healthOS — private rawdata (not committed; see .gitignore)

• Drop Amazfit/Zepp CSV exports under: amazfit helio/
• Strava: strava/activities.csv
• Labs: blood_panels/*.md (frontmatter + tables per src/ingest/blood_panels/)
• Optional narrative-only files: notes/  (not ingested by load_all)

Committed guide: docs/private-rawdata-layout.md
Public mirror for shape reference: data/examples/alex_demo/

Pipeline env example:
  export RAWDATA_ROOT="/full/path/to/healthOS/rawdata"
  export HEALTHOS_PROFILE="$RAWDATA_ROOT/profile.yaml"
  export CONTEXT_FLAGS="$RAWDATA_ROOT/context_flags.yaml"
EOF

echo "Created $RD (see README.txt inside). Next: copy exports from your devices, or cp -R data/examples/alex_demo/. rawdata/ then replace files."
