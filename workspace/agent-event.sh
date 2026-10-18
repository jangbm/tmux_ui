#!/usr/bin/env bash
# Usage: agent-event.sh PROJECT_ID claude|codex idle|busy|done|waiting|error|unknown
set -euo pipefail
cd "$(dirname "$0")"
exec python3 core.py status "$@"
