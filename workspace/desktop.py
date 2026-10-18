"""Mount the grouped project chat UI in the isolated preview tmux server."""
import json
import shlex
import sys
import time
import core
import layout
from desk_state import DeskState


def enabled(project):
    return core.tmux('show-options','-qv','-t',core.session_id(project['id']),'@tmw_desktop').stdout.strip()=='1'


def request(workspace,action,**values):
    payload={'action':action,**values,'nonce':time.time_ns()}
    core.tmux_checked('set-option','-t',core.session_id(workspace['id']),'@tmw_desktop_request',json.dumps(payload))


def ensure_running(project):
    session,window,items,_,editor=layout.context(project)
    if editor['dead']:
        core.tmux_checked('respawn-pane','-k','-t',editor['id'],
                          shlex.join([sys.executable,str(core.ROOT/'desktop-app.py'),project['id']]))



@layout.serialized
def initialize(project):
    if enabled(project):
        ensure_running(project)
        return
    import editor_tabs
    session,window,items,sidebar,editor=layout.context(project)
    tabs=editor_tabs.ordered(project)
    state=DeskState()
    known={p['id'] for p in core.projects()}
    for tab in tabs:
        if tab['project'] in known: state.open(tab['project'])
    primary=editor.get('project') or project['id']
    first=state.open(primary if primary in known else project['id'])
    visible=next((p for p in items if p['window']==window and p['role']=='project-view' and p.get('project') in known),None)
    if visible and visible['project']!=first['project']:
        other=next((t for t in state.group()['tabs'] if t['project']==visible['project']),None) or state.open(visible['project'])
        state.split(other['id'],'right')
    core.atomic(core.STATE/f"desktop-{project['id']}.json",state.value)
    pane=core.tmux_checked('split-window','-d','-h','-t',editor['id'],'-P','-F','#{pane_id}',
        shlex.join([sys.executable,str(core.ROOT/'desktop-app.py'),project['id']]))
    core.tmux_checked('set-option','-p','-t',pane,'@tmw_role','project-view')
    # Every old editor, source mirror, agent process and draft stays alive in its own saved pane.
    for old in items:
        if old['window']!=window or old['id']==sidebar['id'] or old['role'] in ('terminal','terminal-toolbar'): continue
        layout.park(old)
        if old['agent']:
            core.tmux_checked('set-option','-p','-t',old['id'],'@tmw_saved_agent',old['agent'])
            core.tmux_checked('set-option','-pu','-t',old['id'],'@tmw_agent')
        core.tmux_checked('set-option','-p','-t',old['id'],'@tmw_role','saved-content')
    core.tmux_checked('set-option','-p','-t',pane,'@tmw_role','editor')
    core.tmux_checked('select-pane','-t',pane,'-T','Projects')
    core.tmux_checked('set-option','-t',session,'@tmw_desktop','1')
    layout.arrange(project)
    core.tmux_checked('select-window','-t',window)
    core.tmux_checked('select-pane','-t',pane)


@layout.serialized
def upgrade(project):
    """Reload only the preview UI after drafts settle and own CLI turns finish."""
    import fcntl
    session,window,items,sidebar,editor=layout.context(project)
    command=core.tmux_checked('display-message','-p','-t',editor['id'],'#{pane_start_command}')
    if 'desktop-app.py' not in command: raise ValueError('Expected the grouped Desktop UI')
    handles=[]
    try:
        paths=list((core.STATE/'chats').glob('*.lock'))+list(core.STATE.glob('session-input-*.lock'))
        for path in paths:
            handle=path.open('a'); handles.append(handle)
            try: fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError: raise ValueError('별도 대화가 응답 중이므로 UI 교체를 잠시 기다려 주세요.')
        # The running UI saves every draft after 0.4 s; retain its visible screen as recovery evidence too.
        time.sleep(.6)
        screen=core.tmux('capture-pane','-p','-t',editor['id']).stdout
        core.atomic(core.STATE/'desktop-before-reload.json',{'screen':screen,'time':time.time()})
        core.tmux_checked('respawn-pane','-k','-t',editor['id'],
            shlex.join([sys.executable,str(core.ROOT/'desktop-app.py'),project['id']]))
        time.sleep(.8)
        if core.tmux_checked('display-message','-p','-t',editor['id'],'#{pane_dead}')=='1':
            raise RuntimeError('새 UI 시작 실패; 저장된 탭과 입력을 확인해 주세요.')
        return editor['id']
    finally:
        for handle in handles: handle.close()
