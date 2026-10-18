#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v tmux >/dev/null || { echo 'tmux required'; exit 1; }
python="$PWD/.venv/bin/python"
[ -x "$python" ] || { echo 'Create .venv and install requirements.txt first'; exit 1; }
"$python" -c 'import textual' || { echo 'Install requirements.txt into .venv'; exit 1; }
export TMW_SOCKET="${TMW_SOCKET:-tmux-ui-preview}"
first="$("$python" - <<'PY'
import core
items=core.projects()
print(items[0]['id'] if items else '')
PY
)"
[ -n "$first" ] || { echo 'Register a project with core.py add first'; exit 1; }
if [ ! -t 0 ] || [ ! -t 1 ]; then
  echo 'Run ./launch.sh from an interactive terminal.'
  exit 1
fi
exec "$python" core.py open "$first" --attach
