#!/usr/bin/env python3
"""Reload preview styles and restart only this workspace's sidebar processes."""
import shlex
import argparse
import sys
import os
import subprocess
import time
from pathlib import Path
import core
import layout
import editor_tabs
import desktop


def deferred_chat(pane,expected_pid):
    """Redraw one chat only after its current turn and draft are finished."""
    deadline=time.monotonic()+3600
    while time.monotonic()<deadline:
        result=core.tmux('display-message','-p','-t',pane,'#{pane_pid}|#{pane_start_command}')
        if result.returncode: return
        pid,_,command=result.stdout.strip().partition('|')
        if pid!=str(expected_pid): return
        args=shlex.split(command)
        if len(args)==1: args=shlex.split(args[0])
        if len(args)!=4 or Path(args[1]).resolve()!=core.ROOT/'agent-chat.py': return
        busy=core.tmux_checked('show-options','-pqv','-t',pane,'@tmw_chat_busy')
        screen=core.tmux_checked('capture-pane','-p','-t',pane)
        if busy!='1' and '메시지를 입력하세요' in screen:
            core.tmux_checked('respawn-pane','-k','-t',pane,shlex.join(args))
            core.tmux('set-option','-pu','-t',pane,'@tmw_chat_style_job')
            return
        time.sleep(2)


def queue_chat_refresh(pane):
    old=core.tmux_checked('show-options','-pqv','-t',pane,'@tmw_chat_style_job')
    if old.isdigit():
        try: os.kill(int(old),0); return
        except OSError: pass
    pid=core.tmux_checked('display-message','-p','-t',pane,'#{pane_pid}')
    env={**os.environ,'TMW_SOCKET':core.SOCKET,'TMW_CONFIG':str(core.CONFIG),'TMW_STATE':str(core.STATE)}
    process=subprocess.Popen([sys.executable,str(core.ROOT/'refresh-style.py'),'--chat-pane',pane,'--expected-pid',pid],
        env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    core.tmux_checked('set-option','-p','-t',pane,'@tmw_chat_style_job',str(process.pid))


def refresh(chat_style=False):
    # core always targets the isolated tmux-ui-* socket.
    core.tmux_checked('source-file', str(core.ROOT/'preview.conf'))
    rows=core.tmux_checked('list-panes','-a','-F',
                          '#{pane_id}\t#{session_name}\t#{pane_start_command}')
    count=0
    for row in rows.splitlines():
        pane,session,command=row.split('\t',2)
        if not session.startswith('tw-'):
            continue
        args=shlex.split(command)
        # tmux quotes a single shell-command argument when formatting it.
        if len(args)==1:
            args=shlex.split(args[0])
        workspace=next((p for p in core.projects() if core.session_id(p['id'])==session),None)
        grouped=bool(workspace and desktop.enabled(workspace))
        if grouped and len(args)>1 and Path(args[1]).name in ('editor-tabs.py','agent-chat.py'): continue
        if chat_style and len(args)==4 and Path(args[0]).resolve()==Path(sys.executable).resolve() and Path(args[1]).resolve()==core.ROOT/'agent-chat.py':
            busy=core.tmux_checked('show-options','-pqv','-t',pane,'@tmw_chat_busy')
            screen=core.tmux_checked('capture-pane','-p','-t',pane)
            # Idle composers with no draft are safe to redraw; preserve active turns and drafts.
            if busy!='1' and '메시지를 입력하세요' in screen:
                core.tmux_checked('respawn-pane','-k','-t',pane,shlex.join(args))
                print(f'{session}: {args[-1]} chat buttons refreshed')
            else:
                queue_chat_refresh(pane)
                print(f'{session}: {args[-1]} chat refresh queued; active turn/draft preserved')
            continue
        # Never restart editors, shells or AI agents, even if the title changes.
        if len(args) not in (2,3) or Path(args[0]).resolve()!=Path(sys.executable).resolve():
            continue
        script=Path(args[1]).resolve()
        if script not in (core.ROOT/'sidebar.py',core.ROOT/'editor-tabs.py'):
            continue
        core.tmux_checked('respawn-pane','-k','-t',pane,
                          '-e','TMW_PROJECT='+session.removeprefix('tw-'),
                          shlex.join([sys.executable,str(script),*([session.removeprefix('tw-')] if script.name=='editor-tabs.py' else [])]))
        core.tmux_checked('set-option','-p','-t',pane,'@tmw_role','sidebar' if script.name=='sidebar.py' else 'editor-tabs')
        core.tmux_checked('select-pane','-t',pane,'-T','Projects' if script.name=='sidebar.py' else 'Editor tabs')
        count+=1
    print(f'{core.SOCKET}: styles loaded, {count} navigation panel(s) refreshed')
    # Upgrade existing visible terminals without replacing their shell processes.
    for project in core.projects():
        session=core.session_id(project['id'])
        if core.tmux('has-session','-t',session).returncode: continue
        if not desktop.enabled(project):
            editor_tabs.initialize(project)
            layout.ensure_chat_panels(project)
        terminal=next((p for p in layout.terminals(project) if p['visible']),None)
        if not terminal: continue
        previous=core.tmux_checked('display-message','-p','-t',session,'#{window_id}|#{pane_id}')
        layout.show_terminal(project,pane_id=terminal['id'])
        window,pane=previous.split('|')
        core.tmux_checked('select-window','-t',window)
        core.tmux_checked('select-pane','-t',pane)
        print(f'{session}: terminal toolbar ready; existing shell preserved')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--chat-style',action='store_true')
    parser.add_argument('--chat-pane')
    parser.add_argument('--expected-pid')
    options=parser.parse_args()
    if options.chat_pane: deferred_chat(options.chat_pane,options.expected_pid)
    else: refresh(chat_style=options.chat_style)
