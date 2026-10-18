"""Read-only access to existing tmux servers; never sends commands to their panes."""
from pathlib import Path
import subprocess
import time
import fcntl
import hashlib
import json
import re
import os
import core


def read(socket,*args,timeout=1):
    allowed={'list-sessions','list-panes','capture-pane'}
    if not args or args[0] not in allowed: raise ValueError('Read-only tmux command required')
    result=subprocess.run(['tmux','-S',str(socket),*args],text=True,capture_output=True,timeout=timeout,errors='replace')
    if result.returncode: raise RuntimeError(result.stderr.strip() or 'tmux source unavailable')
    return result.stdout


def source_panes(socket,session):
    rows=read(socket,'list-panes','-s','-t','='+session,'-F',
        '#{pane_id}|#{window_index}|#{window_name}|#{window_active}|#{pane_active}|#{pane_current_command}|#{pane_current_path}')
    result=[]
    for row in rows.splitlines():
        pane,index,name,window_active,active,command,path=row.split('|',6)
        result.append(dict(id=pane,window=index,name=name,active=window_active=='1' and active=='1',command=command,path=path))
    return result


def capture(socket,pane):
    # Current visible screen only. No history or terminal input is copied.
    if not pane.startswith('%') or not pane[1:].isdigit(): raise ValueError('Invalid pane ID')
    return read(socket,'capture-pane','-p','-e','-t',pane)


def connections(socket,deadline=None):
    """Find real CLI processes per source session without reading terminal text."""
    from watcher import pane_agent
    rows=read(socket,'list-panes','-a','-F',
              '#{session_name}|#{pane_current_command}|#{pane_pid}|#{pane_dead}',timeout=.4)
    found={}
    for row in rows.splitlines():
        session,command,pid,dead=row.split('|')
        agents=found.setdefault(session,{})
        if dead=='1': continue
        if deadline and time.monotonic()>deadline: raise TimeoutError('AI connection scan timed out')
        agent=pane_agent(command,int(pid))
        if agent: agents[agent]=agents.get(agent,0)+1
    return found


def pending_result(screen,cursor,state,detail,previous):
    """Viewing is not acknowledgement: keep a result until a new turn begins."""
    from watcher import styled_line, PROMPT
    plain=styled_line(screen)[0]
    lines=plain.splitlines()
    prompts=[i for i,line in enumerate(lines) if abs(i-cursor)<=2 and PROMPT.match(line)]
    body='\n'.join(lines[:max(prompts)] if prompts else lines)
    digest=hashlib.sha256(body.encode()).hexdigest()
    has_reply=bool(re.search(r'^\s*[●•]\s+\S|Worked for \d',body,re.M))
    pending=previous.get('pending','')
    if state=='busy': pending=''
    elif state=='waiting' and detail in ('choice','confirmation'): pending='approval'
    elif state=='idle':
        if previous.get('state')=='busy' or (has_reply and (not previous or digest!=previous.get('digest'))): pending='result'
    return {'state':state,'digest':digest,'pending':pending}


def acknowledge_input(project,pane):
    key=project['source_socket']+'|'+pane
    def update(cache):
        if key in cache:
            cache[key]['pending']=''
            # Keep the current body digest so the ensuing reply can create a fresh result.
            cache[key]['state']='idle'
    core.locked_update(core.STATE/'source-pending.json',update)


def activity(socket,deadline):
    """Read current CLI footers within the shared scan budget; never infer busy from a PID."""
    from watcher import pane_agent, detect
    remaining=deadline-time.monotonic()
    if remaining<=0: return {}
    rows=read(socket,'list-panes','-a','-F',
              '#{session_name}|#{pane_id}|#{pane_current_command}|#{pane_pid}|#{pane_dead}|#{cursor_y}',timeout=min(.2,remaining))
    found={}; observations=[]
    try: previous=json.loads((core.STATE/'source-pending.json').read_text())
    except (OSError,ValueError): previous={}
    priority={'unknown':0,'idle':1,'busy':2,'waiting':3,'error':4}
    for row in rows.splitlines():
        session,pane,command,pid,dead,cursor=row.split('|')
        if dead=='1': continue
        owner=pane_agent(command,int(pid))
        agents=[owner] if owner else []
        if not agents: continue
        remaining=deadline-time.monotonic()
        if remaining<=0: break
        try:
            screen=read(socket,'capture-pane','-p','-e','-t',pane,timeout=min(.12,remaining))
            state,reason=detect(screen,int(cursor))
        except (OSError,RuntimeError,subprocess.TimeoutExpired): continue
        key=socket+'|'+pane
        old=previous.get(key,{})
        if old.get('pid')!=pid: old={}
        attention=pending_result(screen,int(cursor),state,reason,old)
        observations.append((key,{**attention,'pid':pid}))
        target=found.setdefault(session,{})
        for agent in agents:
            pending=target.get(agent,{}).get('pending','')
            if attention['pending']=='approval' or (attention['pending'] and not pending): pending=attention['pending']
            if priority[state]>=priority.get(target.get(agent,{}).get('state'),-1):
                target[agent]={'state':state,'detail':reason}
            target[agent]['pending']=pending
    if observations:
        def update(cache):
            for key,value in observations:
                if cache.get(key,{})==previous.get(key,{}): cache[key]=value
        core.locked_update(core.STATE/'source-pending.json',update)
    return found


def discover(socket,deadline):
    """Read all source sessions in one call; never create or start an AI."""
    remaining=deadline-time.monotonic()
    if remaining<=0: return []
    rows=read(socket,'list-panes','-a','-F',
        '#{session_name}|#{pane_id}|#{window_active}|#{pane_active}|#{pane_current_path}',timeout=min(.2,remaining))
    found={}
    for row in rows.splitlines():
        name,pane,window_active,pane_active,path=row.split('|',4)
        if name not in found or (window_active=='1' and pane_active=='1'):
            found[name]=dict(name=name,path=path,agents={'claude':False,'codex':False},kind='tmux-live',
                source_socket=str(socket),source_session=name,source_pane=pane)
    return list(found.values())


def merge_discovered(records,found):
    for item in found:
        identity=(item['source_socket'],item['source_session'])
        existing=next((p for p in records if p.get('kind')=='tmux-live' and
            (p.get('source_socket'),p.get('source_session'))==identity),None)
        if existing: continue  # Keep names, order, visibility, and pinned targets.
        key='live-'+core.slug(item['source_session'])
        if any(p['id']==key for p in records):
            key+='-'+hashlib.sha256(repr(identity).encode()).hexdigest()[:12]
        suffix=key;number=2
        while any(p['id']==key for p in records):
            key=f'{suffix}-{number}';number+=1
        records.append({**item,'id':key})


def refresh_connections(force=False):
    """One bounded source scan shared by all project sidebars every eight seconds."""
    records=[p for p in core.projects() if p.get('kind')=='tmux-live']
    sockets={p['source_socket'] for p in records}
    default=Path(os.environ.get('TMUX_TMPDIR','/tmp'))/f'tmux-{os.getuid()}'/'default'
    if not sockets and default.exists(): sockets.add(str(default))
    if not sockets: return False
    core.STATE.mkdir(parents=True,exist_ok=True)
    with (core.STATE/'live-connections.lock').open('a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return False
        path=core.STATE/'live-connections.json'
        try: last=__import__('json').loads(path.read_text()).get('updated',0)
        except (OSError,ValueError): last=0
        if not force and time.time()-last<8: return False
        deadline=time.monotonic()+.8
        observed={}; errors={}; states={}; discovered=[]
        for socket in sorted(sockets):
            try: discovered.extend(discover(socket,deadline))
            except (OSError,RuntimeError,ValueError,TimeoutError,subprocess.TimeoutExpired): pass
            try: observed[socket]=connections(socket,deadline)
            except (OSError,RuntimeError,ValueError,TimeoutError,subprocess.TimeoutExpired): errors[socket]='unavailable'
            try: states[socket]=activity(socket,deadline)
            except (OSError,RuntimeError,ValueError,TimeoutError,subprocess.TimeoutExpired): pass
        now=time.time()
        def update(items):
            merge_discovered(items,discovered)
            for project in items:
                if project.get('kind')!='tmux-live': continue
                socket=project['source_socket']; session=project['source_session']
                project['source_agents_error']=errors.get(socket,'')
                if socket in observed:
                    project['source_agents']=observed[socket].get(session,{})
                    project['source_agents_updated']=now
                    project['source_states']=states.get(socket,{}).get(session,{})
        core.locked_update(core.CONFIG,update)
        core.atomic(path,{'updated':now})
        return True


def register(socket):
    names=read(socket,'list-sessions','-F','#{session_name}').splitlines()
    found=[]
    for name in names:
        items=source_panes(socket,name)
        if not items: continue
        active=next((p for p in items if p['active']),items[0])
        key='live-'+core.slug(name)
        found.append(dict(id=key,name=name,path=active['path'],
            agents={'claude':False,'codex':False},kind='tmux-live',
            source_socket=str(socket),source_session=name,source_pane=active['id']))
    def update(records):
        merge_discovered(records,found)
    core.locked_update(core.CONFIG,update)
    refresh_connections(force=True)
    return [p for p in core.projects() if p.get('kind')=='tmux-live']


if __name__=='__main__':
    result=subprocess.run(['tmux','display-message','-p','#{socket_path}'],text=True,capture_output=True,timeout=1)
    if result.returncode: raise SystemExit(result.stderr.strip())
    socket=Path(result.stdout.strip())
    for item in register(socket): print(item['id']+'  '+item['name'])
