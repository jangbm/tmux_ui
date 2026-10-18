# tmux Workspace v3 — terminal-native prototype

**Status: runnable prototype, not production-ready.** Linux/macOS with tmux, Python 3.10+, Textual, and preferably Neovim. `claude` and `codex` are optional and must be installed/authenticated separately. Tested with Python syntax, shell syntax and registry/status smoke tests; tmux/Textual/AI CLI integration was **not** exercised in this environment.

## Install

```bash
unzip tmux-workspace-v3.zip
cd tmux-workspace-v3
python3 -m venv .venv
source .venv/bin/activate
pip install 'textual>=0.80,<8'
# macOS: brew install tmux neovim; Ubuntu: sudo apt install tmux neovim
python3 core.py add 'Unity 교육앱' "$HOME/Projects/unity-edu" --id unity-edu --git --start
./launch.sh
```

`n` in sidebar opens a **New Project** form; specify a *nonexistent* destination folder. Check Git init and optional AI CLI launch. The new project gets a tmux session with left Textual sidebar, upper-right Neovim, lower-right Claude and Codex **separate panes**, visible simultaneously. Drag tmux pane borders with the mouse (terminal must support mouse reporting). Sidebar clicks switch projects, preserving detached tmux sessions. Pane sizes are tmux-managed and are **not persisted across server restart**. This is not VS Code-style drag-and-drop tab docking.

### CLI project management

```bash
python3 core.py add 'Website' "$HOME/Projects/website" --id website --git --start
python3 core.py add 'Existing Unity' "$HOME/existing-unity" --id existing --mode import --start
python3 core.py add 'Cloned' "$HOME/Projects/cloned" --id cloned --mode clone --url https://example.com/repo.git --start
python3 core.py open unity-edu --attach
python3 core.py open website --launch-agents --attach
python3 core.py list
python3 core.py diff unity-edu
```

`--launch-agents` starts `claude` and `codex` only if binaries are installed, in the project directory. The normal `--start` path creates their shells but **does not automatically launch** the CLIs. This avoids unintentional permissions/auth prompts and background resource usage. To start manually, focus a lower pane and type `claude` or `codex`. First-run authorization must be completed by the user; no bypass flags are used. `git init` is only applied to a newly created directory, never silently to an imported directory. Clone accepts only HTTPS or SSH `git@` URLs.

### Agent status

Each project/agent has independent state: `idle` ○, `busy` rotating ◐◓◑◒, `done` green ✓, `waiting` yellow !, `error` red ✕, `unknown` ?. An unread status adds a dot. The sidebar reads a shared, lock-protected atomic JSON status store. Example:

```bash
./agent-event.sh unity-edu claude busy
./agent-event.sh unity-edu claude done
./agent-event.sh unity-edu codex waiting
```

**Automatic AI status detection is NOT included.** Hook adapters for Claude Code and Codex must be verified against installed CLI versions. Do not equate lack of terminal output with completion. For Claude, wire documented hooks (e.g. appropriate start/stop/notification events) to `agent-event.sh`, carefully distinguish approval from stop events, and pass the correct project id. For Codex, verify the installed version's supported notification/event mechanism before wiring. Until verified, the UI only reflects manually/externally reported events. Events may become stale after a crash; use `unknown` when uncertain. The spinner is a Textual label updated about 4 times per second, not an SVG spinner.

### Current limitations and safety

- Sidebar is instantiated once **per active project session**, but registry/status are shared; a single status **store** is not a daemon. An always-running central service is not yet implemented.
- Project sessions survive terminal detachment while tmux server runs; **reboot recovery** of processes, layouts and AI state is not implemented. The registry persists and `launch.sh` recreates missing sessions.
- Sidebar project selection switches tmux client to the selected session. The sidebar is not a floating overlay.
- Each project shows Claude and Codex side by side at the bottom. These are separate panes rather than draggable tabs.
- Project file tree in sidebar, automatic Git diff badges, Git worktree creation/merge, LSP setup, notifications, AI turn-history search and workspace templates are **not yet implemented**. Neovim's own explorer/plugins can provide file browsing.
- Do not let Claude and Codex edit the same file simultaneously without coordination; use separate Git worktrees when appropriate. For Unity, test asset/meta file handling before introducing worktrees.
- This is a **single-user local tool**. Do not expose tmux socket or status/config paths to untrusted users. Do not run the app with elevated privileges.
- Unicode glyph rendering, mouse dragging and pane dimensions vary by terminal; a sufficiently wide terminal is needed.

### Planned next milestones

1. Version-verified Claude/Codex event adapters and stale-state reconciliation.
2. Project import/clone via TUI, project templates and safe project deletion.
3. Git diff panel, worktree workflow, external file change warnings.
4. Saved pane layouts and opt-in reboot recovery, then drag-and-drop UX refinements.
