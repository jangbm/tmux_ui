"""User-triggered input to the exact registered tmux AI pane shown by the UI.

No background input or automatic retries. Read-only polling lives in live_tmux.
"""
import fcntl
import hashlib
import re
import subprocess
import time
import uuid
import core
import live_tmux
from watcher import detect, pane_agent, styled_line, PROMPT


def targets(project,agent):
    if project.get('kind')!='tmux-live' or agent not in core.AGENTS:
        raise ValueError('연결된 tmux 프로젝트가 아닙니다.')
    rows=live_tmux.read(project['source_socket'],'list-panes','-s','-t','='+project['source_session'],'-F',
        '#{session_name}|#{pane_id}|#{pane_pid}|#{pane_current_command}|#{pane_dead}|#{cursor_y}|#{window_index}|#{pane_index}')
    result=[]
    for row in rows.splitlines():
        session,pane,pid,command,dead,cursor,window,index=row.split('|')
        if session!=project['source_session'] or dead=='1': continue
        if pane_agent(command,int(pid))==agent:
            result.append(dict(id=pane,pid=pid,cursor=int(cursor),label=f'{window}.{index} {agent.title()} {pane}'))
    return result


def suggestion(screen,cursor):
    """Ghost text must be faint ANSI text on the current prompt, not real input."""
    lines=screen.splitlines()
    for row in sorted(range(max(0,cursor-1),min(len(lines),cursor+2)),key=lambda n:abs(n-cursor)):
        plain,dim=styled_line(lines[row]); match=PROMPT.match(plain)
        if not match: continue
        text=plain[match.start(1):]; flags=dim[match.start(1):]
        if text.strip() and all(faint or char.isspace() for char,faint in zip(text,flags)):
            return text.strip()
    return ''


def menu_open(screen,state,detail):
    if state=='waiting' and detail in ('choice','confirmation','menu'): return True
    plain=styled_line(screen)[0]
    selected=bool(re.search(r'^\s*[❯›>]\s+\S',plain,re.M))
    hints=bool(re.search(r'enter to (?:confirm|select)|press enter to select',plain,re.I))
    return selected and hints


def snapshot(project,agent,pane=None,expected_pid=None):
    options=targets(project,agent)
    target=next((p for p in options if p['id']==pane),None) if pane else (options[0] if len(options)==1 else None)
    if not target:
        raise ValueError('AI 창이 여러 개입니다. 위에서 전송할 창을 선택해 주세요.' if options and not pane else '선택한 AI 창이 종료되었거나 연결이 바뀌었습니다.')
    if expected_pid and target['pid']!=expected_pid: raise ValueError('AI 창이 다시 시작되었습니다. 연결을 확인한 뒤 다시 보내 주세요.')
    screen=live_tmux.capture(project['source_socket'],target['id'])
    state,detail=detect(screen,target['cursor'])
    menu=menu_open(screen,state,detail)
    if menu: state,detail='waiting','menu'
    plain=styled_line(screen)[0]
    footer='\n'.join(plain.rstrip().splitlines()[-8:]).lower()
    mode=next((label for pattern,label in [('plan mode','Plan'),('auto mode','Auto'),('accept edits','편집 허용'),('bypass permissions','권한 우회'),('manual mode','Manual')] if pattern in footer),'')
    return dict(**target,screen=screen,state=state,detail=detail,suggestion='' if menu else suggestion(screen,target['cursor']),mode=mode,menu=menu)


def _command(project,*args,input=None):
    result=subprocess.run(['tmux','-S',project['source_socket'],*args],input=input,text=True,capture_output=True,timeout=2)
    if result.returncode: raise RuntimeError(result.stderr.strip() or 'tmux 전송 실패')


def send(project,agent,pane,pid,message):
    message=message.replace('\r\n','\n').replace('\r','\n')
    if not message.strip(): raise ValueError('메시지를 입력해 주세요.')
    if any(ord(c)<32 and c not in '\n\t' for c in message) or '\x7f' in message:
        raise ValueError('메시지에 터미널 제어 문자가 포함되어 있습니다.')
    core.STATE.mkdir(parents=True,exist_ok=True)
    key=hashlib.sha256((project['source_socket']+pane).encode()).hexdigest()[:24]
    with (core.STATE/f'session-input-{key}.lock').open('a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('이 AI 창에 다른 메시지를 전송 중입니다.')
        current=snapshot(project,agent,pane,pid)
        if current['state']!='idle':
            raise ValueError('tmux 입력창이 비어 있는 준비 상태에서 보내 주세요. 작업·질문 대기 중이거나 작성 중인 입력이 있습니다.')
        buffer='tmw-message-'+uuid.uuid4().hex
        try:
            _command(project,'load-buffer','-b',buffer,'-',input=message)
            # Revalidate after buffer creation. No shell command is ever constructed from the message.
            current=snapshot(project,agent,pane,pid)
            if current['state']!='idle': raise ValueError('전송 직전에 tmux 상태가 바뀌었습니다. 다시 확인해 주세요.')
            _command(project,'paste-buffer','-p','-r','-d','-b',buffer,'-t',pane)
            time.sleep(.12)
            # Do not press Enter if the CLI was replaced by a shell during the paste.
            if not any(p['id']==pane and p['pid']==pid for p in targets(project,agent)):
                raise ValueError('붙여넣기 후 AI 연결이 바뀌었습니다. tmux 입력창을 확인해 주세요.')
            _command(project,'send-keys','-t',pane,'Enter')
            live_tmux.acknowledge_input(project,pane)
        finally:
            try: _command(project,'delete-buffer','-b',buffer)
            except (OSError,RuntimeError,subprocess.TimeoutExpired): pass


def control(project,agent,pane,pid,action):
    current=snapshot(project,agent,pane,pid)
    if action=='mode':
        if agent!='claude': raise ValueError('모드 전환은 Claude에서 사용합니다.')
        if current['state']!='idle': raise ValueError('Claude 입력창이 준비 상태일 때 모드를 변경해 주세요.')
        key='BTab'
    elif action=='stop':
        if current['state']!='busy': raise ValueError('현재 응답 중인 작업이 없습니다.')
        key='Escape'
    elif action in ('Up','Down','Left','Right','Enter','Escape'):
        if not current.get('menu'): raise ValueError('선택 메뉴가 열려 있을 때만 사용할 수 있습니다.')
        key=action
    else: raise ValueError('지원하지 않는 조작입니다.')
    _command(project,'send-keys','-t',pane,key)


def shutdown(project,agent,pane,pid):
    """User-confirmed graceful CLI exit; retain its tmux pane, never kill a session."""
    current=snapshot(project,agent,pane,pid)
    if current['state']!='idle':
        raise ValueError('작업을 중지하거나 승인 메뉴를 취소한 뒤, 입력창이 빈 준비 상태에서 종료해 주세요.')
    _command(project,'set-option','-p','-t',pane,'remain-on-exit','on')
    send(project,agent,pane,pid,'/exit')
    deadline=time.monotonic()+4
    while time.monotonic()<deadline:
        if not any(p['id']==pane and p['pid']==pid for p in targets(project,agent)): return True
        time.sleep(.1)
    return False
