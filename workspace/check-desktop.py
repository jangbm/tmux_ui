#!/usr/bin/env python3
"""Grouped project UI migration and terminal integration, on a disposable server."""
import json
import tempfile
import time
import fcntl,os,pty,select,struct,subprocess,termios
from pathlib import Path
from rich.cells import cell_len
import core
import desktop
import layout

if core.SOCKET!='tmux-ui-test': raise SystemExit('Use TMW_SOCKET=tmux-ui-test')
if core.tmux('list-sessions').returncode==0: raise SystemExit('Test socket already in use')


def pids(session):
    result=core.tmux_checked('list-panes','-s','-t',session,'-F','#{pane_id}|#{pane_pid}')
    return dict(row.split('|') for row in result.splitlines())


def wait(predicate):
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        if predicate(): return
        time.sleep(.04)
    raise AssertionError('Desktop state did not settle')


def native_mouse(owner,main,state_path):
    session=core.session_id(owner['id'])
    master,slave=pty.openpty()
    fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',54,210,0,0))
    def setup():
        os.setsid(); fcntl.ioctl(0,termios.TIOCSCTTY,0)
    env={k:v for k,v in os.environ.items() if k not in ('TMUX','TMUX_PANE')}; env['TERM']='xterm-256color'
    client=subprocess.Popen(['tmux','-L',core.SOCKET,'attach-session','-t',session],stdin=slave,stdout=slave,stderr=slave,env=env,preexec_fn=setup)
    os.close(slave)
    def drain():
        while select.select([master],[],[],0)[0]:
            try: os.read(master,65536)
            except OSError: break
    def poll(predicate):
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            drain()
            if predicate(): return
            time.sleep(.04)
        raise AssertionError('Native desktop mouse action did not settle')
    def state(): return json.loads(state_path.read_text())
    def rows(): return core.tmux('capture-pane','-p','-t',main).stdout.splitlines()
    def location(label,header=False):
        x,y=map(int,core.tmux_checked('display-message','-p','-t',main,'#{pane_left}|#{pane_top}').split('|'))
        row,line=next((i,line) for i,line in enumerate(rows()[:3] if header else rows()) if label in line)
        return x+cell_len(line[:line.index(label)])+1,y+row
    def drag(start,end):
        x,y=start; dx,dy=end
        os.write(master,f'\x1b[<0;{x+1};{y+1}M'.encode()); time.sleep(.08)
        os.write(master,f'\x1b[<32;{dx+1};{dy+1}M'.encode()); time.sleep(.08)
        os.write(master,f'\x1b[<0;{dx+1};{dy+1}m'.encode())
    def click(x,y):
        os.write(master,f'\x1b[<0;{x+1};{y+1}M'.encode()); time.sleep(.08)
        os.write(master,f'\x1b[<0;{x+1};{y+1}m'.encode())
    try:
        poll(lambda: bool(core.tmux_checked('list-clients','-t',session,'-F','#{client_name}')))
        time.sleep(.5); drain()
        drag(location('unity',True),location('control',True))
        poll(lambda:any({'unity','control'}.issubset({t['project'] for t in g['tabs']}) for g in state()['groups']))
        time.sleep(.3); drain()
        drag(location('unity',True),location('Workspace',True))
        poll(lambda:any(g['active'] and next(t['project'] for t in g['tabs'] if t['id']==g['active'])=='unity' for g in state()['groups']) and all(not {'unity','control'}.issubset({t['project'] for t in g['tabs']}) for g in state()['groups']))
        poll(lambda:any('Codex' in line for line in rows()))
        # State is persisted before layout/resize settles; click the final coordinates.
        previous=None; stable=0
        def settled():
            nonlocal previous,stable
            current=rows()
            stable=stable+1 if current==previous else 0
            previous=current
            return stable>=5
        poll(settled)
        x,y=map(int,core.tmux_checked('display-message','-p','-t',main,'#{pane_left}|#{pane_top}').split('|'))
        row,line=next((i,line) for i,line in enumerate(rows()) if 'Codex' in line and '×' in line)
        click(x+cell_len(line[:line.rfind('×')]),y+row)
        poll(lambda:any('codex' in t.get('hidden',[]) for g in state()['groups'] for t in g['tabs'] if t['project']=='control'))
        print('Native mouse: move tabs between group headers; Codex × closes only its own panel',flush=True)
    finally:
        core.tmux('detach-client','-s',session)
        deadline=time.monotonic()+3
        while client.poll() is None and time.monotonic()<deadline: drain(); time.sleep(.03)
        if client.poll() is None: client.kill(); client.wait(timeout=3)
        os.close(master)


with tempfile.TemporaryDirectory(prefix='tmux-desktop-') as tmp:
    core.CONFIG=Path(tmp)/'projects.json'; core.STATE=Path(tmp)/'state'
    owner=core.add('Workspace',Path(tmp)/'owner')
    one=core.add('unity',Path(tmp)/'unity',codex=False)
    both=core.add('control',Path(tmp)/'control')
    try:
        session=core.create_session(owner)
        core.tmux_checked('resize-window','-t',session,'-x','210','-y','54')
        before=pids(session)
        desktop.initialize(owner)
        assert desktop.enabled(owner)
        assert all(pids(session).get(pane)==pid for pane,pid in before.items())
        _,window,items,_,main=layout.context(owner)
        assert len([p for p in items if p['window']==window])==2
        assert not any(p['agent'] and p['window']==window for p in items)
        print('Migration: old editors/drafts/agents preserved; no separate bottom AI panes',flush=True)
        path=core.STATE/f"desktop-{owner['id']}.json"
        def state(): return json.loads(path.read_text())
        desktop.request(owner,'open',project=one['id'])
        wait(lambda:any(t['project']==one['id'] and t['id']==g['active'] for g in state()['groups'] for t in g['tabs']))
        desktop.request(owner,'split',project=both['id'],direction='right')
        wait(lambda:len(state()['groups'])==2)
        wait(lambda:'Codex' in core.tmux_checked('capture-pane','-p','-t',main['id']))
        text=core.tmux_checked('capture-pane','-p','-t',main['id'])
        assert 'unity' in text and 'control' in text and 'Claude' in text
        assert 'Traceback' not in text
        print('Two independent tab strips; unity owns one composer, control owns two',flush=True)
        native_mouse(owner,main['id'],path)
        old_main=main['id'];old_pid=pids(session)[old_main]
        desktop.upgrade(owner)
        _,window,items,_,main=layout.context(owner)
        assert main['id']==old_main and pids(session)[old_main]!=old_pid
        assert all(pids(session).get(pane)==pid for pane,pid in before.items())
        print('UI reload preserves saved state and original editor/AI processes',flush=True)
        main_pid=pids(session)[main['id']]
        layout.show_terminal(owner,new=True)
        assert any(t['visible'] for t in layout.terminals(owner))
        layout.show_terminal(owner,hide=True)
        assert pids(session)[main['id']]==main_pid
        assert all(pids(session).get(pane)==pid for pane,pid in before.items())
        print('Terminal drawer works; grouped chat UI and all original processes retained',flush=True)
    finally: core.tmux('kill-server')
print('Desktop integration checks passed',flush=True)
