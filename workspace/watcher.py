"""Bounded, shared status polling for the isolated workspace server."""
import argparse
import fcntl
import json
from pathlib import Path
import re
import subprocess
import time
import core

INTERVAL=8
MAX_AGE=24
ANSI=re.compile(r'\x1b\[([0-9;:]*)m|\x1b\[[0-?]*[ -/]*[@-~]')
PROMPT=re.compile(r'^\s*[│┃║]?\s*[❯›>]\s?(.*)$')
SELECTED=re.compile(r'^\s*[│┃║]?\s*[❯›>]\s*(?:\d+[.)]|yes\b|allow\b|approve\b|continue\b|accept\b)',re.I)


def styled_line(line):
    """Return display characters and dim flags without mistaking RGB zeros for SGR reset."""
    text=[]; dim=[]; position=0; faint=False
    for match in ANSI.finditer(line):
        segment=line[position:match.start()]
        text.extend(segment); dim.extend([faint]*len(segment))
        params=match.group(1)
        if params is not None:
            values=[int(value or 0) for value in params.replace(':',';').split(';')]
            i=0
            while i<len(values):
                value=values[i]
                if value in (38,48,58) and i+1<len(values):
                    i+=5 if values[i+1]==2 else 3
                    continue
                if value in (0,22): faint=False
                elif value==2: faint=True
                i+=1
        position=match.end()
    segment=line[position:]
    text.extend(segment); dim.extend([faint]*len(segment))
    return ''.join(text),dim


def detect(screen,cursor_y,agent_running=True,dead=False):
    if dead: return 'error','pane-exited'
    if not agent_running: return 'unknown','not-running'
    plain,flags=styled_line(screen)
    parsed=[]; offset=0
    for line in plain.splitlines(keepends=True):
        content=line.rstrip('\r\n')
        parsed.append((content,flags[offset:offset+len(content)]))
        offset+=len(line)
    cursor_y=max(0,min(cursor_y,len(parsed)-1))
    near=[plain for plain,_ in parsed[max(0,cursor_y-8):cursor_y+8]]
    if any(SELECTED.match(line) for row,(line,_) in enumerate(parsed) if abs(row-cursor_y)<=3):
        return 'waiting','choice'
    nearby='\n'.join(near).lower()
    if re.search(r'\[(?:y/n|yes/no)\]|\((?:y/n|yes/no)\)|press enter to continue',nearby):
        return 'waiting','confirmation'
    prompts=[]
    for row,(plain,dim) in enumerate(parsed):
        match=PROMPT.match(plain)
        if match and abs(row-cursor_y)<=2:
            draft=''.join(char for char,faint in zip(plain[match.start(1):],dim[match.start(1):]) if not faint).strip()
            prompts.append((row,draft))
    # Footer markers are strong evidence; text in the input itself is not.
    last=max((row for row,(plain,_) in enumerate(parsed) if plain.strip()),default=0)
    footer='\n'.join(plain for row,(plain,_) in enumerate(parsed)
                     if row>=max(0,last-8) and not PROMPT.match(plain)).lower()
    if re.search(r'esc(?:ape)? to interrupt|esc to cancel',footer): return 'busy','interrupt-hint'
    if prompts:
        _,draft=min(prompts,key=lambda item:abs(item[0]-cursor_y))
        return ('waiting','draft') if draft else ('idle','empty-prompt')
    return 'unknown','unrecognized-screen'


def running_agent(agent,command,pid):
    if command.lower().split('/')[-1] in (agent,agent+'.exe'): return True
    queue=[pid]; visited=set()
    while queue and len(visited)<32:
        current=queue.pop()
        if current in visited: continue
        visited.add(current)
        try:
            args=(Path('/proc')/str(current)/'cmdline').read_bytes().split(b'\0')
            for raw in args[:3]:
                arg=raw.decode(errors='replace')
                if Path(arg).name in (agent,agent+'.exe') or f'@openai/{agent}' in arg or f'@anthropic-ai/{agent}-code' in arg:
                    return True
            children=(Path('/proc')/str(current)/'task'/str(current)/'children').read_text()
            queue.extend(int(value) for value in children.split())
        except (OSError,ValueError): continue
    return False


def pane_agent(command,pid):
    """One terminal has one foreground AI; nested workers do not own its input."""
    foreground=command.lower().rsplit('/',1)[-1].removesuffix('.exe')
    if foreground in core.AGENTS: return foreground
    # Only the pane process itself may identify a launcher. Background jobs in a
    # shell's descendants have no independently addressable interactive screen.
    try:
        args=(Path('/proc')/str(pid)/'cmdline').read_bytes().split(b'\0')[:3]
    except OSError: return None
    for raw in args:
        arg=raw.decode(errors='replace')
        if not arg or any(c.isspace() for c in arg): continue
        for agent,package in (('claude','@anthropic-ai/claude-code'),('codex','@openai/codex')):
            if Path(arg).name in (agent,agent+'.exe') or (arg.startswith('/') and package+'/' in arg):
                return agent
    return None


def observed_path(): return core.STATE/f'observed-{core.SOCKET}.json'


def read_snapshot():
    try:
        value=json.loads(observed_path().read_text())
        if not isinstance(value,dict) or not isinstance(value.get('updated'),(int,float)): return {}
        projects=value.get('projects')
        if not isinstance(projects,dict): return {}
        value['projects']={key:{agent:record for agent,record in agents.items()
                               if agent in core.AGENTS and isinstance(record,dict)}
                           for key,agents in projects.items() if isinstance(agents,dict)}
        return value
    except (OSError,ValueError): return {}


def refresh(force=False):
    """One collector per socket; other sidebars use the cached result."""
    core.STATE.mkdir(parents=True,exist_ok=True)
    with (core.STATE/f'observed-{core.SOCKET}.lock').open('a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return False
        old=read_snapshot()
        if not force and time.time()-old.get('updated',0)<INTERVAL: return False
        started=time.monotonic(); deadline=started+.8
        now=time.time(); observations={}
        records={core.session_id(p['id']):p for p in core.projects()}
        try:
            result=core.run(['tmux','-L',core.SOCKET,'list-panes','-a','-F',
                '#{session_name}|#{pane_id}|#{@tmw_agent}|#{pane_current_command}|#{pane_pid}|#{cursor_y}|#{pane_dead}|#{@tmw_agent_ui}|#{@tmw_chat_busy}'],timeout=.2)
            if result.returncode: return False
            for row in result.stdout.splitlines():
                fields=row.split('|')
                session,pane,agent,command,pid,cursor,dead=fields[:7]
                ui,busy=(fields[7:9] if len(fields)>=9 else ('',''))
                project=records.get(session)
                if not project or agent not in core.AGENTS or not project.get('agents',{}).get(agent,True): continue
                state,reason='unknown','budget-exceeded'
                if ui=='chat' and dead!='1':
                    state,reason=('busy','chat-response') if busy=='1' else ('idle','chat-ready')
                elif time.monotonic()<deadline:
                    alive=running_agent(agent,command,int(pid))
                    if dead=='1': state,reason='error','pane-exited'
                    elif not alive: state,reason='unknown','not-running'
                    else:
                        try:
                            capture=core.run(['tmux','-L',core.SOCKET,'capture-pane','-p','-e','-t',pane],
                                             timeout=max(.01,min(.15,deadline-time.monotonic())))
                            if capture.returncode==0: state,reason=detect(capture.stdout,int(cursor))
                            else: state,reason='unknown','capture-failed'
                        except subprocess.TimeoutExpired: state,reason='unknown','capture-timeout'
                previous=old.get('projects',{}).get(project['id'],{}).get(agent,{})
                unchanged=(previous.get('state'),previous.get('detail'),previous.get('pane'))==(state,reason,pane)
                changed=previous.get('changed_at',now) if unchanged else now
                observations.setdefault(project['id'],{})[agent]={
                    'state':state,'detail':reason,'pane':pane,'updated':now,'changed_at':changed,'source':'screen'}
        except (OSError,ValueError,subprocess.TimeoutExpired): return False
        core.atomic(observed_path(),{'updated':now,'projects':observations,'elapsed':round(time.monotonic()-started,4)})
        return True


def effective_status(manual,now=None):
    now=time.time() if now is None else now
    snapshot=read_snapshot()
    if not snapshot: return manual
    fresh=0<=now-snapshot.get('updated',0)<=MAX_AGE
    result={}
    projects=set(manual)|set(snapshot.get('projects',{}))
    for project in projects:
        result[project]={}
        explicit_agents=manual.get(project,{})
        if not isinstance(explicit_agents,dict): explicit_agents={}
        for agent in core.AGENTS:
            explicit=explicit_agents.get(agent,{})
            observed=snapshot.get('projects',{}).get(project,{}).get(agent,{})
            if not isinstance(explicit,dict): explicit={}
            if not observed:
                if explicit.get('state') in core.STATES:
                    if 0<=now-explicit.get('updated',0)<60: result[project][agent]=explicit
                    else: result[project][agent]={'state':'unknown','detail':'missing-pane','source':'screen'}
                continue
            manual_age=now-explicit.get('updated',0)
            if explicit.get('state') in core.STATES and 0<=manual_age<60 and explicit.get('updated',0)>=observed.get('changed_at',0):
                result[project][agent]=explicit
            else:
                value=dict(observed)
                if not fresh: value.update(state='unknown',detail='stale-monitor')
                value['seen']=explicit.get('seen_at',0)>=value.get('changed_at',now)
                result[project][agent]=value
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--force',action='store_true')
    args=parser.parse_args()
    refresh(force=args.force)
