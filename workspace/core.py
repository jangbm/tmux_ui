#!/usr/bin/env python3
"""Workspace controller: project registry, tmux sessions, status, and safe project creation."""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, time, fcntl, shlex
from pathlib import Path
ROOT = Path(__file__).resolve().parent
CONFIG = Path(os.environ.get('TMW_CONFIG', ROOT/'data/projects.json')).expanduser()
STATE = Path(os.environ.get('TMW_STATE', ROOT/'data/state')).expanduser()
# Never inherit the production tmux socket.
SOCKET = os.environ.get('TMW_SOCKET', 'tmux-ui-preview')
if not re.fullmatch(r'tmux-ui-[a-zA-Z0-9_-]+', SOCKET):
    raise ValueError('TMW_SOCKET must start with tmux-ui- and contain only letters, numbers, _ or -')
AGENTS = ('claude', 'codex')
STATES = ('idle','busy','done','waiting','error','unknown')

def run(cmd, **kw):
    return subprocess.run(cmd, text=True, capture_output=True, **kw)

def atomic(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.tmp-', dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:
            json.dump(obj,f,ensure_ascii=False,indent=2)
            f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def locked_update(path, fn):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path)+'.lock','a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            try: obj=json.loads(path.read_text())
            except (OSError,ValueError): obj={} if path != CONFIG else []
            result=fn(obj)
            atomic(path,obj)
            return result
        finally: fcntl.flock(lock,fcntl.LOCK_UN)

def projects():
    try:
        value=json.loads(CONFIG.read_text())
        return value if isinstance(value,list) else []
    except (OSError,ValueError): return []

def status():
    try: manual=json.loads((STATE/'status.json').read_text())
    except (OSError,ValueError): manual={}
    if not isinstance(manual,dict): manual={}
    from watcher import effective_status
    return effective_status(manual)

def session_id(key): return 'tw-'+key

def slug(name):
    value=re.sub('[^a-z0-9_-]+','-',name.lower()).strip('-')
    if not value: raise ValueError('Project name must contain Latin letters or numbers; use --id for other names')
    return value[:48]

def git_snapshot(path):
    """Read working-tree counts without refreshing the index or changing files."""
    env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}
    try:
        result=run(['git','-C',str(path),'status','--porcelain=v1','-z',
                    '--untracked-files=normal','--','.'],env=env,timeout=1,errors='replace')
        if result.returncode:
            return {'error':'Git unavailable or folder is not a repository'}
        branch=run(['git','-C',str(path),'symbolic-ref','--quiet','--short','HEAD'],
                   env=env,timeout=1)
        snapshot={'branch':branch.stdout.strip() or 'Detached HEAD',
                  'staged':0,'modified':0,'untracked':0,'conflicts':0,'files':[]}
        tracking=run(['git','-C',str(path),'rev-parse','--abbrev-ref','@{upstream}'],env=env,timeout=1)
        snapshot['upstream']=tracking.stdout.strip() if tracking.returncode==0 else None
        if snapshot['upstream']:
            counts=run(['git','-C',str(path),'rev-list','--left-right','--count','HEAD...@{upstream}'],env=env,timeout=1)
            if counts.returncode==0:
                snapshot['ahead'],snapshot['behind']=map(int,counts.stdout.split())
        entries=result.stdout.split('\0')
        index=0
        while index<len(entries):
            entry=entries[index]; index+=1
            if len(entry)<3: continue
            code,name=entry[:2],entry[3:]
            if 'R' in code or 'C' in code:
                index+=1  # -z puts the old path after the new path.
            if code=='??': snapshot['untracked']+=1
            elif 'U' in code or code in ('AA','DD'): snapshot['conflicts']+=1
            else:
                snapshot['staged']+=code[0]!=' '
                snapshot['modified']+=code[1]!=' '
            if len(snapshot['files'])<200:
                snapshot['files'].append((code,name))
        return snapshot
    except subprocess.TimeoutExpired:
        return {'error':'Git timed out. Press r to try again.'}
    except OSError:
        return {'error':'Git is not available'}

def preview_text(root,path):
    """Bound file reads and keep previews inside the registered project."""
    root=Path(root).resolve(); path=Path(path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Select a file inside this project')
    with path.open('rb') as handle:
        data=handle.read(256*1024+1)
    if b'\0' in data:
        raise ValueError('Binary files cannot be previewed')
    truncated=len(data)>256*1024
    text=data[:256*1024].decode('utf-8',errors='replace')
    if truncated: text+='\n\n[Preview limited to 256 KiB]'
    return text

def add(name, path, key=None, mode='create', git=False, claude=True, codex=True, url=None):
    key=key or slug(name)
    if not re.fullmatch('[a-zA-Z0-9_-]{1,48}',key): raise ValueError('Invalid project id')
    dest=Path(path).expanduser().resolve()
    if any(p['id']==key or Path(p['path']).resolve()==dest for p in projects()): raise ValueError('Project id/path already registered')
    if mode=='create':
        if dest.exists(): raise ValueError('Destination exists; use import instead')
        dest.mkdir(parents=True)
        if git:
            r=run(['git','-C',str(dest),'init']);
            if r.returncode: raise RuntimeError(r.stderr)
    elif mode=='import':
        if not dest.is_dir(): raise ValueError('Import path is not a directory')
    elif mode=='clone':
        if not url or not (url.startswith('https://') or url.startswith('git@')): raise ValueError('Clone requires HTTPS or git@ URL')
        if dest.exists(): raise ValueError('Clone destination exists')
        r=run(['git','clone','--',url,str(dest)])
        if r.returncode: raise RuntimeError(r.stderr)
    record={'id':key,'name':name,'path':str(dest),'agents':{'claude':bool(claude),'codex':bool(codex)}}
    def update(obj):
        if any(p['id']==key or p['path']==str(dest) for p in obj): raise ValueError('Project already registered')
        obj.append(record)
    locked_update(CONFIG,update)
    return record

def tmux(*args): return run(['tmux','-L',SOCKET,'-f',str(ROOT/'preview.conf'),*args])

def tmux_checked(*args):
    r=tmux(*args)
    if r.returncode: raise RuntimeError(r.stderr.strip() or 'tmux command failed')
    return r.stdout.strip()

def agent_command(project,agent,launch=False):
    if launch and shutil.which(agent): return shlex.join([agent])
    return shlex.join([sys.executable,str(ROOT/'agent-chat.py'),project['id'],agent])


def chat_project(workspace):
    """Current editor project, independent of the tmux workspace's original name."""
    session=session_id(workspace['id'])
    result=tmux('show-options','-qv','-t',session,'@tmw_chat_project')
    if result.returncode: return workspace
    key=result.stdout.strip()
    if not key:
        selected=tmux('show-options','-qv','-t',session,'@tmw_selected_tab').stdout.strip()
        if selected.startswith('%') and selected[1:].isdigit():
            key=tmux('show-options','-pqv','-t',selected,'@tmw_project').stdout.strip()
    return next((p for p in projects() if p['id']==key),workspace)


def create_session(project, launch_agents=False):
    key=project['id']; sess=session_id(key); cwd=project['path']
    if tmux('has-session','-t',sess).returncode==0:
        ready=tmux_checked('show-options','-qv','-t',sess,'@tmw_ready')
        if ready!='1': raise RuntimeError('Incomplete preview session: '+sess)
        return sess
    if not Path(cwd).is_dir(): raise ValueError('Project directory missing: '+cwd)
    editor_bin=shutil.which('nvim') or shutil.which('vim') or shutil.which('vi')
    shell=os.environ.get('SHELL') or '/bin/bash'
    environment=[]
    for name,value in [('TMW_SOCKET',SOCKET),('TMW_CONFIG',str(CONFIG)),('TMW_STATE',str(STATE)),('TMW_PROJECT',key)]:
        environment.extend(['-e',f'{name}={value}'])
    editor_command=([sys.executable,str(ROOT/'live-view.py'),key] if project.get('kind')=='tmux-live'
                    else [editor_bin,'-u',str(ROOT/'editor.vim'),*(['--',str(Path(cwd)/project['entry'])] if project.get('entry') else [])] if editor_bin else [shell])
    # Start programs directly, without injecting keystrokes into shells.
    editor=tmux_checked('new-session','-d','-s',sess,'-n','work','-c',cwd,
                        '-x','160','-y','48',*environment,'-P','-F','#{pane_id}',
                        shlex.join(editor_command))
    try:
        tmux_checked('set-option','-t',sess,'mouse','on')
        tmux_checked('select-pane','-t',editor,'-T','Editor')
        tmux_checked('set-option','-p','-t',editor,'@tmw_role','editor')
        first_ai=None
        for agent in AGENTS:
            if not project.get('agents',{}).get(agent,True): continue
            split=['-h','-p','50','-t',first_ai] if first_ai else ['-v','-p','36','-t',editor]
            pane=tmux_checked('split-window','-d',*split,'-c',cwd,'-P','-F','#{pane_id}',agent_command(project,agent,launch_agents))
            tmux_checked('select-pane','-t',pane,'-T',agent.title())
            tmux_checked('set-option','-p','-t',pane,'@tmw_agent',agent)
            if not launch_agents: tmux_checked('set-option','-p','-t',pane,'@tmw_agent_ui','chat')
            first_ai=first_ai or pane
        # Full-height sidebar beside the editor and both agent panes.
        command=shlex.join([sys.executable,str(ROOT/'sidebar.py')])
        sidebar=tmux_checked('split-window','-d','-h','-f','-b','-l','34','-t',editor,'-c',cwd,'-P','-F','#{pane_id}',command)
        tmux_checked('select-pane','-t',sidebar,'-T','Projects')
        tmux_checked('set-option','-p','-t',sidebar,'@tmw_role','sidebar')
        tmux_checked('select-pane','-t',editor)
        tmux_checked('set-option','-t',sess,'@tmw_ready','1')
    except Exception as exc:
        raise RuntimeError(f'Preview setup incomplete ({sess}); panes preserved: {exc}') from exc
    return sess

def set_status(project, agent, state, detail=''):
    if agent not in AGENTS or state not in STATES: raise ValueError('Invalid agent/status')
    if not any(p['id']==project for p in projects()): raise ValueError('Unknown project')
    def update(obj):
        obj.setdefault(project,{})[agent]={'state':state,'detail':detail[:250],'updated':time.time(),'seen':False}
    locked_update(STATE/'status.json',update)

def mark_seen(project,agent):
    def update(obj):
        record=obj.setdefault(project,{}).setdefault(agent,{})
        record['seen']=True
        record['seen_at']=time.time()
    locked_update(STATE/'status.json',update)

def reorder_project(source,target,after=False):
    """Move one project before another, retaining concurrent registry additions."""
    def update(records):
        item=next((p for p in records if p['id']==source),None)
        if not item or source==target or not any(p['id']==target for p in records): return
        records.remove(item)
        records.insert(next(i for i,p in enumerate(records) if p['id']==target)+int(after),item)
    locked_update(CONFIG,update)


def main():
    p=argparse.ArgumentParser(description='tmux workspace v3')
    sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('add'); a.add_argument('name'); a.add_argument('path'); a.add_argument('--id'); a.add_argument('--mode',choices=['create','import','clone'],default='create'); a.add_argument('--url'); a.add_argument('--git',action='store_true'); a.add_argument('--no-claude',action='store_true'); a.add_argument('--no-codex',action='store_true'); a.add_argument('--start',action='store_true'); a.add_argument('--auto-launch-agents',action='store_true')
    a=sub.add_parser('open'); a.add_argument('id'); a.add_argument('--launch-agents',action='store_true'); a.add_argument('--attach',action='store_true')
    sub.add_parser('list')
    a=sub.add_parser('status'); a.add_argument('id'); a.add_argument('agent',choices=AGENTS); a.add_argument('state',choices=STATES); a.add_argument('--detail',default='')
    a=sub.add_parser('seen'); a.add_argument('id'); a.add_argument('agent',choices=AGENTS)
    a=sub.add_parser('diff'); a.add_argument('id')
    args=p.parse_args()
    try:
        if args.cmd=='add':
            obj=add(args.name,args.path,args.id,args.mode,args.git,not args.no_claude,not args.no_codex,args.url)
            print('Registered:',obj['name'],obj['path'])
            if args.start: print('Session:',create_session(obj,args.auto_launch_agents))
        elif args.cmd=='open':
            obj=next((p for p in projects() if p['id']==args.id),None)
            if not obj: raise ValueError('Unknown project')
            sess=create_session(obj,args.launch_agents)
            from editor_tabs import initialize
            initialize(obj)
            if args.attach:
                os.environ.pop('TMUX',None)
                os.execvp('tmux',['tmux','-L',SOCKET,'attach-session','-t',sess])
            else: print('Session:',sess)
        elif args.cmd=='list':
            for obj in projects(): print(f"{obj['id']:20} {obj['name']:25} {obj['path']}")
        elif args.cmd=='status': set_status(args.id,args.agent,args.state,args.detail)
        elif args.cmd=='seen': mark_seen(args.id,args.agent)
        elif args.cmd=='diff':
            obj=next((p for p in projects() if p['id']==args.id),None)
            if not obj: raise ValueError('Unknown project')
            for cmd in (['git','-C',obj['path'],'status','--short'],['git','-C',obj['path'],'diff','--stat']):
                r=run(cmd); print(r.stdout or r.stderr)
    except (ValueError,RuntimeError,OSError) as e:
        print('Error:',e,file=sys.stderr); sys.exit(1)
if __name__=='__main__': main()
