#!/usr/bin/env python3
"""Exercise ANSI capture on a disposable server using a fake agent, without typing keys."""
import json
from pathlib import Path
import shlex
import sys
import tempfile
import time
import core
import watcher

if core.SOCKET!='tmux-ui-test': raise SystemExit('Requires TMW_SOCKET=tmux-ui-test')
if core.tmux('list-sessions').returncode==0: raise SystemExit('Test socket already in use; refusing to reuse it')

with tempfile.TemporaryDirectory(prefix='tmux-ui-capture-') as tmp:
    root=Path(tmp)
    core.CONFIG=root/'projects.json'; core.STATE=root/'state'
    project=core.add('Capture test',root/'project',key='status-check',claude=False)
    mode=root/'mode.json'; mode.write_text(json.dumps('idle'))
    fixture=root/'codex'
    fixture.write_text('''import json,sys,time
from pathlib import Path
path=Path(sys.argv[1]); previous=None
while True:
    try: mode=json.loads(path.read_text())
    except (OSError,ValueError): time.sleep(.03); continue
    if mode!=previous:
        previous=mode
        screens={
            'idle':'› \\x1b[2mSuggested next step\\x1b[0m',
            'busy':'Working…\\nesc to interrupt',
            'waiting':'Do you want to allow this?\\n❯ 1. Yes\\n  2. No\\x1b[2;1H',
            'draft':'› My actual input\\x1b[2m suggestion\\x1b[0m',
        }
        sys.stdout.write('\\x1b[2J\\x1b[H'+screens[mode]); sys.stdout.flush()
    time.sleep(.03)
''')
    command=shlex.join([sys.executable,str(fixture),str(mode)])
    pane=core.tmux_checked('new-session','-d','-s','tw-status-check','-x','100','-y','30',
                           '-P','-F','#{pane_id}',command)
    core.tmux_checked('set-option','-p','-t',pane,'@tmw_agent','codex')
    try:
        for requested,expected in (('idle','idle'),('busy','busy'),('waiting','waiting'),('draft','waiting'),('idle','idle')):
            mode.write_text(json.dumps(requested))
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                watcher.refresh(force=True)
                record=core.status().get('status-check',{}).get('codex',{})
                expected_detail='draft' if requested=='draft' else 'choice' if requested=='waiting' else None
                if record.get('state')==expected and (expected_detail is None or record.get('detail')==expected_detail): break
                time.sleep(.05)
            else: raise AssertionError((requested,record))
            print(f'ANSI capture: {requested} → {record["state"]} ({record["detail"]})',flush=True)
        elapsed=watcher.read_snapshot()['elapsed']
        assert elapsed<1,elapsed
        print(f'Shared collector elapsed: {elapsed:.4f}s; no keys sent',flush=True)
    finally:
        # Only this explicitly disposable server may be stopped.
        core.tmux('kill-server')
print('Live capture checks passed',flush=True)
