#!/usr/bin/env bash
# run_pipeline.sh — Bash wrapper for launchd scheduling.
#
# Usage:
#   bash agent/run_pipeline.sh              # manual test
#   launchctl start com.finanalyst.pipeline  # via launchd
#
# To set up the launchd job:
#   1. Copy plist template and fill in PROJECT_DIR:
#      cp agent/scheduler/macos/com.finanalyst.pipeline.plist.template \
#         ~/Library/LaunchAgents/com.finanalyst.pipeline.plist
#      sed -i '' "s|<PROJECT_DIR>|$(pwd)/agent|g" \
#         ~/Library/LaunchAgents/com.finanalyst.pipeline.plist
#   2. Load:
#      launchctl load ~/Library/LaunchAgents/com.finanalyst.pipeline.plist
#   3. Test immediately:
#      launchctl start com.finanalyst.pipeline
#   4. Check logs:
#      tail -f agent/logs/pipeline.log

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure log directory exists
mkdir -p "$SCRIPT_DIR/logs"

LOG_FILE="$SCRIPT_DIR/logs/pipeline.log"

echo "" >> "$LOG_FILE"
echo "══════════════════════════════════════════" >> "$LOG_FILE"
echo "🚀 Pipeline started at $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "══════════════════════════════════════════" >> "$LOG_FILE"

# Prefer uv if available, fall back to python3
if command -v uv &>/dev/null; then
    exec uv run python "$SCRIPT_DIR/run_pipeline.py" >> "$LOG_FILE" 2>&1
else
    exec python3 "$SCRIPT_DIR/run_pipeline.py" >> "$LOG_FILE" 2>&1
fi
