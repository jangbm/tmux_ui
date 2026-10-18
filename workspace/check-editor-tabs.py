#!/usr/bin/env python3
"""Real editor tab checks, confined to an otherwise empty disposable server."""
from pathlib import Path
import tempfile
from unittest.mock import patch
import time
import fcntl, os, pty, select, struct, subprocess, sys, termios
import core
import layout
import editor_tabs
import live_tmux

if core.SOCKET!='tmux-ui-test': raise SystemExit('Use TMW_SOCKET=tmux-ui-test')
if core.tmux('list-sessions').returncode==0: raise SystemExit('Test socket already in use; stop the disposable test server first')


def rects(project):
    rows=core.tmux_checked('list-panes','-s','-t',core.session_id(project['id']),'-F',
        '#{pane_id}|#{pane_left}|#{pane_top}|#{pane_width}|#{pane_height}|#{pane_pid}')
    return {p:list(map(int,values)) for p,*values in (row.split('|') for row in rows.splitlines())}


def mouse_check(project,web_id,python_id,bar_id):
    """Exercise tmux's real SGR mouse routing, rather than calling UI handlers."""
    session=core.session_id(project['id'])
    master,slave=pty.openpty()
    fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',48,160,0,0))
    def setup():
        os.setsid(); fcntl.ioctl(0,termios.TIOCSCTTY,0)
    env={k:v for k,v in os.environ.items() if k not in ('TMUX','TMUX_PANE')}
    env['TERM']='xterm-256color'
    client=subprocess.Popen(['tmux','-L',core.SOCKET,'attach-session','-t',session],
        stdin=slave,stdout=slave,stderr=slave,env=env,preexec_fn=setup)
    os.close(slave)
    def drain():
        while select.select([master],[],[],0)[0]:
            try: os.read(master,65536)
            except OSError: break
    def poll(predicate):
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            drain()
            if core.tmux_checked('show-options','-qv','-t',session,'@tmw_layout_busy')!='1' and predicate(): return
            time.sleep(.04)
        raise AssertionError('Mouse action did not complete')
    def location(label):
        box=rects(project)[bar_id]
        rows=core.tmux_checked('capture-pane','-p','-t',bar_id).splitlines()
        y,line=next((y,line) for y,line in enumerate(rows) if label in line)
        return box[0]+line.index(label)+2,box[1]+y
    def drag(source,destination):
        x,y=source; dx,dy=destination
        os.write(master,f'\x1b[<0;{x+1};{y+1}M'.encode()); time.sleep(.08)
        os.write(master,f'\x1b[<32;{dx+1};{dy+1}M'.encode()); time.sleep(.08)
        os.write(master,f'\x1b[<0;{dx+1};{dy+1}m'.encode())
    try:
        poll(lambda: bool(core.tmux_checked('list-clients','-t',session,'-F','#{client_name}')))
        time.sleep(.7); drain()
        box=rects(project)[bar_id]
        drag(location('Demo Web'),(box[0]+box[2]-22,box[1]+1))
        def right():
            geometry=rects(project); main=layout.context(project)[4]['id']
            return geometry[web_id][0]>geometry[main][0] and geometry[web_id][1]==geometry[main][1]
        poll(right)
        box=rects(project)[bar_id]
        drag(location('Demo Web'),(box[0]+box[2]-14,box[1]+1))
        def below():
            geometry=rects(project); main=layout.context(project)[4]['id']
            return geometry[web_id][1]>geometry[main][1] and geometry[web_id][0]==geometry[main][0]
        poll(below)
        time.sleep(.7); drain()
        drag(location('Demo Web'),location('Workspace'))
        poll(lambda: editor_tabs.ordered(project)[0]['id']==web_id)
        print('Native tmux mouse: tab drag right / below / reorder all passed',flush=True)
    finally:
        core.tmux('detach-client','-s',session)
        deadline=time.monotonic()+3
        while client.poll() is None and time.monotonic()<deadline:
            drain(); time.sleep(.03)
        if client.poll() is None:
            client.kill(); client.wait(timeout=3)
        os.close(master)


with tempfile.TemporaryDirectory(prefix='tmux-editor-tabs-') as tmp:
    core.CONFIG=Path(tmp)/'projects.json'; core.STATE=Path(tmp)/'state'
    owner=core.add('Workspace',Path(tmp)/'owner',claude=True,codex=True)
    web=core.add('Demo Web',Path(tmp)/'web',claude=False,codex=False)
    python=core.add('Demo Python',Path(tmp)/'python',claude=False,codex=False)
    (Path(web['path'])/'index.html').write_text('<h1>Hello tabs</h1>')
    (Path(python['path'])/'main.py').write_text('print("Hello tabs")')
    try:
        core.create_session(owner)
        session,window,items,sidebar,original=layout.context(owner)
        original_pid=rects(owner)[original['id']][-1]
        web_id=editor_tabs.open_project(owner,web)
        assert layout.context(owner)[4]['id']==web_id
        assert len(editor_tabs.ordered(owner))==2
        assert rects(owner)[original['id']][-1]==original_pid
        python_id=editor_tabs.open_project(owner,python)
        assert layout.context(owner)[4]['id']==python_id
        assert len(editor_tabs.ordered(owner))==3
        assert core.tmux('has-session','-t',core.session_id(web['id'])).returncode!=0
        web_pid=rects(owner)[web_id][-1]
        editor_tabs.select(owner,web_id)
        assert layout.context(owner)[4]['id']==web_id and rects(owner)[web_id][-1]==web_pid
        print('Project clicks open real tabs in one workspace; select restores original editor PID',flush=True)
        editor_tabs.split(owner,web_id,'right')
        main=layout.context(owner)[4]['id']; geometry=rects(owner)
        assert geometry[web_id][0]>geometry[main][0] and geometry[web_id][1]==geometry[main][1]
        editor_tabs.split(owner,web_id,'below')
        geometry=rects(owner)
        assert geometry[web_id][1]>geometry[main][1] and geometry[web_id][0]==geometry[main][0]
        print('The same open tab moves to right or below group',flush=True)
        editor_tabs.reorder(owner,web_id,python_id)
        assert [p['id'] for p in editor_tabs.ordered(owner)][-1]==web_id
        editor_tabs.close(owner,web_id)
        assert web_id not in [p['id'] for p in editor_tabs.ordered(owner)]
        assert editor_tabs.open_project(owner,web)==web_id and rects(owner)[web_id][-1]==web_pid
        print('Reorder, close and reopen preserve hidden editor process',flush=True)
        editor_tabs.close(owner,web_id)
        layout.dock_workspace(owner,'top')
        geometry=rects(owner)
        assert geometry[sidebar['id']][2]==160
        editor_tabs.open_project(owner,web)
        assert core.tmux_checked('show-options','-qv','-t',session,'@tmw_dock')=='top'
        assert len([p for p in layout.panes(session) if p['agent'] and p['window']==window])==2
        assert any(p['role']=='editor-tabs' and p['window']==window for p in layout.panes(session))
        print('Top dock remains open after project click, both agents and editor tabs retained',flush=True)
        bar=next(p for p in layout.panes(session) if p['role']=='editor-tabs')
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            output=core.tmux_checked('capture-pane','-p','-t',bar['id'])
            if 'Demo Web' in output and '옆' in output: break
            time.sleep(.04)
        else: raise AssertionError('Editor strip did not render: '+repr(output))
        assert '╭' in output and '╮' in output,'Rounded tab edges missing'
        print('Live editor strip renders rounded tabs, side borders and labelled split controls',flush=True)
        mouse_check(owner,web_id,python_id,bar['id'])
        fresh=core.add('Fresh',Path(tmp)/'fresh',claude=False,codex=False)
        env={**os.environ,'TMW_CONFIG':str(core.CONFIG),'TMW_STATE':str(core.STATE),'TMW_SOCKET':core.SOCKET}
        result=core.run([sys.executable,str(core.ROOT/'core.py'),'open',fresh['id']],env=env)
        assert result.returncode==0,result.stderr
        fresh_session,fresh_window,fresh_items,_,fresh_editor=layout.context(fresh)
        fresh_bar=next(p for p in fresh_items if p['role']=='editor-tabs')
        layout.park(fresh_bar)
        core.tmux_checked('resize-window','-t',fresh_window,'-x','80','-y','8')
        try: editor_tabs.initialize(fresh)
        except ValueError: pass
        else: raise AssertionError('Too-small strip should report its size requirement')
        assert not any(p['role']=='editor-tabs' and p['window']==fresh_window for p in layout.panes(fresh_session))
        core.tmux_checked('resize-window','-t',fresh_window,'-x','160','-y','48')
        editor_tabs.initialize(fresh)
        assert next(p for p in layout.panes(fresh_session) if p['role']=='editor-tabs')['id']==fresh_bar['id'],(fresh_bar,layout.panes(fresh_session))
        print('New project CLI initializes tabs; small-window failure restores layout and retries safely',flush=True)
        socket=core.tmux_checked('display-message','-p','#{socket_path}')
        imported=live_tmux.register(socket)
        source=next(p for p in imported if p['source_session']==fresh_session)
        mirror=editor_tabs.open_project(owner,source)
        source_pid=rects(fresh)[fresh_editor['id']][-1]
        deadline=time.monotonic()+4
        while time.monotonic()<deadline:
            output=core.tmux_checked('capture-pane','-p','-t',mirror)
            if 'LIVE' in output and fresh_session in output: break
            time.sleep(.04)
        else: raise AssertionError('Live mirror failed to render')
        assert rects(fresh)[fresh_editor['id']][-1]==source_pid
        assert live_tmux.source_panes(socket,fresh_session)
        print('Existing tmux session imported as a live tab; source process retained',flush=True)
        legacy=core.add('Legacy agent',Path(tmp)/'legacy',codex=False)
        with patch.object(core,'agent_command',return_value='/bin/bash'):
            core.create_session(legacy)
        legacy_session,legacy_window,legacy_items,_,_=layout.context(legacy)
        old_agent=next(p for p in legacy_items if p['agent']=='claude')
        old_pid=rects(legacy)[old_agent['id']][-1]
        core.tmux_checked('set-option','-pu','-t',old_agent['id'],'@tmw_agent_ui')
        layout.ensure_chat_panels(legacy)
        new_agent=next(p for p in layout.panes(legacy_session) if p['agent']=='claude')
        assert new_agent['id']!=old_agent['id']
        assert rects(legacy)[old_agent['id']][-1]==old_pid
        assert next(p for p in layout.panes(legacy_session) if p['id']==old_agent['id'])['window']!=legacy_window
        deadline=time.monotonic()+4
        while time.monotonic()<deadline:
            output=core.tmux_checked('capture-pane','-p','-t',new_agent['id'])
            if '보내기' in output and '메시지' in output: break
            time.sleep(.04)
        else: raise AssertionError('Chat composer failed to render')
        print('Legacy agent shell preserved; new chat composer renders without sending AI requests',flush=True)




    finally:
        core.tmux('kill-server')
print('Editor tab integration checks passed',flush=True)
