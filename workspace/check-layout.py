#!/usr/bin/env python3
"""Integration checks; explicitly limited to the disposable tmux-ui-test server."""
import fcntl
import atexit
import os
from pathlib import Path
import pty
import re
import runpy
import select
import signal
import struct
import subprocess
import tempfile
import termios
import time
import core
import layout

if core.SOCKET!='tmux-ui-test':
    raise SystemExit('Run with TMW_SOCKET=tmux-ui-test; never use a live workspace')
if core.tmux('list-sessions').returncode==0: raise SystemExit('Test socket already in use; refusing to reuse it')
atexit.register(lambda:core.tmux('kill-server'))

PTY_FD=None

def drain():
    if PTY_FD is None: return
    while select.select([PTY_FD],[],[],0)[0]:
        try:
            if not os.read(PTY_FD,65536): break
        except OSError: break

def poll(predicate):
    deadline=time.monotonic()+4
    while time.monotonic()<deadline:
        drain()
        busy=core.tmux('show-options','-qv','-t','tw-layout-check','@tmw_layout_busy').stdout.strip()
        if busy=='1':
            time.sleep(.04)
            continue
        if predicate(): return
        time.sleep(.04)
    messages=core.tmux('show-messages').stdout
    print('\n'.join(line for line in messages.splitlines() if ' key ' in line)[:3000],flush=True)
    raise AssertionError('Timed out waiting for terminal state')


def geometry(session):
    rows=core.tmux_checked('list-panes','-s','-t',session,'-F',
                           '#{pane_id}|#{pane_left}|#{pane_top}|#{pane_width}|#{pane_height}|#{pane_pid}')
    return {p:dict(zip(('x','y','w','h','pid'),map(int,values)))
            for p,*values in (row.split('|') for row in rows.splitlines())}


def drag(fd,x,y,dx,dy):
    os.write(fd,f'\x1b[<0;{x+1};{y+1}M'.encode())
    time.sleep(.08)
    os.write(fd,f'\x1b[<32;{x+dx+1};{y+dy+1}M'.encode())
    time.sleep(.08)
    os.write(fd,f'\x1b[<0;{x+dx+1};{y+dy+1}m'.encode())


def click(fd,x,y):
    os.write(fd,f'\x1b[<0;{x+1};{y+1}M'.encode())
    time.sleep(.08)
    os.write(fd,f'\x1b[<0;{x+1};{y+1}m'.encode())


with tempfile.TemporaryDirectory(prefix='tmux-ui-layout-') as tmp:
    core.CONFIG=Path(tmp)/'projects.json'
    core.STATE=Path(tmp)/'state'
    single=core.add('Claude only',Path(tmp)/'single',key='claude-only',codex=False)
    core.create_session(single)
    single_panes=layout.panes(core.session_id(single['id']))
    assert len(single_panes)==3 and not any(p['agent']=='codex' for p in single_panes)
    print('New Claude-only project: no Codex pane created',flush=True)
    project=core.add('Layout test',Path(tmp)/'project',key='layout-check')
    core.create_session(project)
    core.tmux_checked('source-file',str(core.ROOT/'preview.conf'))
    session,window,items,sidebar,editor=layout.context(project)
    codex=next(p for p in items if p['agent']=='codex')
    codex_pid=geometry(session)[codex['id']]['pid']
    layout.set_agents(project,{'claude':True,'codex':False})
    visible=[p for p in layout.panes(session) if p['window']==window]
    assert len(visible)==3
    assert next(p for p in visible if p['agent']=='claude')['width']==next(p for p in visible if p['role']=='editor')['width']
    layout.set_agents(project,{'claude':False,'codex':False})
    assert len([p for p in layout.panes(session) if p['window']==window])==2
    layout.set_agents(project,{'claude':False,'codex':True})
    assert len([p for p in layout.panes(session) if p['window']==window])==3
    layout.set_agents(project,{'claude':True,'codex':True})
    assert geometry(session)[codex['id']]['pid']==codex_pid
    print('Agent visibility: all combinations; original Codex PID preserved',flush=True)
    layout.show_terminal(project,new=True)
    terminal=layout.terminals(project)[0]
    rects=geometry(session)
    ai=[p for p in layout.panes(session) if p['agent'] and p['window']==window]
    assert rects[terminal['id']]['y']>max(rects[p['id']]['y']+rects[p['id']]['h'] for p in ai)
    assert rects[terminal['id']]['w']==rects[editor['id']]['w']
    terminal_pid=geometry(session)[terminal['id']]['pid']
    layout.show_terminal(project,toggle=True)
    assert not layout.terminals(project)[0]['visible']
    layout.show_terminal(project)
    assert geometry(session)[terminal['id']]['pid']==terminal_pid
    layout.show_terminal(project,new=True)
    assert len(layout.terminals(project))==2
    layout.show_terminal(project,pane_id=terminal['id'])
    assert next(p for p in layout.terminals(project) if p['visible'])['id']==terminal['id']
    layout.show_terminal(project,toggle=True)
    print('Terminal drawer: create, hide, restore, switch; shell PID preserved',flush=True)
    for kind in ('cmd','powershell'):
        executable=layout.SHELLS[kind][1][0]
        probe=[executable,'/c','exit','0'] if kind=='cmd' else [executable,'-NoProfile','-Command','exit 0']
        try: available=subprocess.run(probe,capture_output=True,timeout=5).returncode==0
        except (OSError,subprocess.TimeoutExpired): available=False
        if not available:
            print('SKIP: '+kind+' requires working Windows/WSL interop',flush=True)
            continue
        layout.show_terminal(project,kind=kind,new=True)
        def shell_alive():
            current=next(p for p in layout.terminals(project) if p['visible'])
            assert not current['dead'],kind+' exited unexpectedly'
            output=core.tmux_checked('capture-pane','-p','-t',current['id'])
            return bool(re.search(r'(?m)^[A-Z]:\\[^\n]*>',output)) if kind=='cmd' else 'PS ' in output and '>' in output
        poll(shell_alive)
        print(kind+' shell running in its own persistent terminal pane',flush=True)
        layout.show_terminal(project,toggle=True)

    master,slave=pty.openpty()
    PTY_FD=master
    fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',48,160,0,0))
    def setup_tty():
        os.setsid()
        fcntl.ioctl(0,termios.TIOCSCTTY,0)
    env={k:v for k,v in os.environ.items() if k not in ('TMUX','TMUX_PANE')}
    env['TERM']='xterm-256color'
    client=subprocess.Popen(['tmux','-L',core.SOCKET,'attach-session','-t',session],
                            stdin=slave,stdout=slave,stderr=slave,env=env,preexec_fn=setup_tty)
    os.close(slave)
    try:
        def attached():
            ready=select.select([master],[],[],.05)[0]
            if ready: os.read(master,65536)
            return bool(core.tmux_checked('list-clients','-F','#{client_name}'))
        poll(attached)
        before=geometry(session)
        side=before[sidebar['id']]
        drag(master,side['x']+side['w'],10,8,0)
        poll(lambda: geometry(session)[sidebar['id']]['w']>side['w'])
        before=geometry(session)
        edit=before[editor['id']]
        drag(master,edit['x']+10,edit['y']+edit['h'],0,3)
        poll(lambda: geometry(session)[editor['id']]['h']>edit['h'])
        items=layout.panes(session)
        claude=next(p for p in items if p['agent']=='claude')
        before=geometry(session); left=before[claude['id']]
        drag(master,left['x']+left['w'],left['y']+2,5,0)
        poll(lambda: geometry(session)[claude['id']]['w']>left['w'])
        print('Mouse drags: sidebar width, AI height, Claude/Codex widths: OK',flush=True)
        os.write(master,b'\x1b[96;5u')
        poll(lambda: any(p['visible'] for p in layout.terminals(project)))
        os.write(master,b'\x1b[96;5u')
        poll(lambda: not any(p['visible'] for p in layout.terminals(project)))
        print('Ctrl+grave CSI-u shortcut: show/hide: OK',flush=True)
        count=len(layout.terminals(project))
        os.write(master,b'\x1b[96;6u')
        poll(lambda: len(layout.terminals(project))==count+1)
        print('Ctrl+Shift+grave shortcut: new terminal: OK',flush=True)
        current=next(p for p in layout.terminals(project) if p['visible'])
        before=geometry(session); term=before[current['id']]
        # With bottom labels the AI border directly precedes the terminal pane.
        drag(master,term['x']+8,term['y']-1,0,-2)
        poll(lambda: geometry(session)[current['id']]['h']>term['h'])
        print('Terminal drawer height drag: OK',flush=True)
        term=geometry(session)[current['id']]
        saved_pid=term['pid']
        count=len(layout.terminals(project))
        toolbar=next(p for p in layout.panes(session) if p['role']=='terminal-toolbar' and p['window']==window)
        bar=geometry(session)[toolbar['id']]
        click(master,bar['x']+bar['w']-2,bar['y'])
        poll(lambda: not any(p['visible'] for p in layout.terminals(project)))
        assert geometry(session)[current['id']]['pid']==saved_pid
        layout.show_terminal(project,toggle=True)
        bar=geometry(session)[toolbar['id']]
        click(master,bar['x']+bar['w']-8,bar['y'])
        poll(lambda: len(layout.terminals(project))==count+1)
        print('Right-edge × hides without stopping shell; + creates new terminal: OK',flush=True)
        bar=geometry(session)[toolbar['id']]
        click(master,bar['x']+bar['w']-5,bar['y'])
        time.sleep(.3); drain()
        os.write(master,b'c')
        poll(lambda: any(p['visible'] and p['shell']=='cmd' for p in layout.terminals(project)))
        print('Right-edge shell dropdown: CMD selected and opened: OK',flush=True)
        layout.show_terminal(project,hide=True)
        layout.set_agents(project,{'claude':False,'codex':False})
        original=geometry(session)[editor['id']]['pid']
        layout.dock_workspace(project,'top')
        before=geometry(session); side=before[sidebar['id']]
        assert side['w']==160 and side['x']==0 and side['y']==0
        drag(master,10,side['h'],0,2)
        poll(lambda: geometry(session)[sidebar['id']]['h']>side['h'])
        print('Top workspace: full-width tabs, mouse height resize: OK',flush=True)
        right=layout.split_project(project,single,'right')
        rect=geometry(session)
        assert rect[right]['x']>rect[editor['id']]['x'] and rect[right]['y']==rect[editor['id']]['y']
        right_pid=rect[right]['pid']
        layout.close_split(project)
        assert geometry(session)[right]['pid']==right_pid
        below=layout.split_project(project,single,'below')
        assert below==right and geometry(session)[below]['pid']==right_pid
        rect=geometry(session)
        assert rect[below]['y']>rect[editor['id']]['y'] and rect[below]['x']==rect[editor['id']]['x']
        layout.dock_workspace(project,'left')
        rect=geometry(session)
        assert rect[sidebar['id']]['w']==34 and rect[sidebar['id']]['h']>30
        assert rect[editor['id']]['pid']==original
        layout.close_split(project)
        print('Project splits: right/below, dock relocation, original editor PID preserved: OK',flush=True)
        client_name=core.tmux_checked('list-clients','-F','#{client_name}').splitlines()[0]
        core.tmux_checked('switch-client','-c',client_name,'-t',core.session_id(single['id']))
        assert core.tmux_checked('list-clients','-F','#{session_name}')==core.session_id(single['id'])
        core.tmux_checked('switch-client','-c',client_name,'-t',session)
        print('Project tabs: switch between live project sessions and return: OK',flush=True)

    finally:
        core.tmux('detach-client','-s',session)
        poll(lambda: client.poll() is not None)
        os.close(master)
        PTY_FD=None
    before=geometry(session)
    shell_ids=[p['id'] for p in layout.panes(session) if p['agent'] or p['role']=='terminal']
    runpy.run_path(str(core.ROOT/'refresh-style.py'))['refresh']()
    after=geometry(session)
    assert all(before[p]['pid']==after[p]['pid'] for p in shell_ids)
    print('Refresh existing UI: toolbar present and all shell/agent PIDs preserved',flush=True)
print('Layout integration checks passed',flush=True)
