"""Workspace panes, persistent terminal drawers, and agent visibility."""
import os
from pathlib import Path
import shlex
import subprocess
import sys
import shutil
import fcntl
from functools import wraps
import core

SHELLS={
    'bash':('Ubuntu · Bash',['/bin/bash']),
    'powershell':('PowerShell',['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoLogo','-NoProfile','-NoExit']),
    'cmd':('Windows CMD',['/mnt/c/Windows/System32/cmd.exe','/D','/Q']),
}


def serialized(function):
    @wraps(function)
    def apply(project,*args,**kwargs):
        core.STATE.mkdir(parents=True,exist_ok=True)
        with (core.STATE/('layout-'+project['id']+'.lock')).open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            session=core.session_id(project['id'])
            core.tmux_checked('set-option','-t',session,'@tmw_layout_busy','1')
            try: return function(project,*args,**kwargs)
            finally:
                core.tmux('set-option','-t',session,'@tmw_layout_busy','0')
                fcntl.flock(lock,fcntl.LOCK_UN)
    return apply


def panes(session):
    rows=core.tmux_checked('list-panes','-s','-t',session,'-F',
        '#{pane_id}|#{window_id}|#{@tmw_role}|#{@tmw_agent}|#{@tmw_shell}|#{pane_width}|#{pane_height}|#{pane_dead}|#{@tmw_project}')
    result=[]
    for row in rows.splitlines():
        pane,window,role,agent,shell,width,height,dead,project=row.split('|')
        result.append(dict(id=pane,window=window,role=role,agent=agent,shell=shell,
                           width=int(width),height=int(height),dead=dead=='1',project=project))
    return result


def context(project):
    session=core.session_id(project['id'])
    items=panes(session)
    sidebar=next((p for p in items if p['role']=='sidebar'),None)
    if not sidebar: raise ValueError('Workspace sidebar not found')
    window=sidebar['window']
    editor=next((p for p in items if p['role']=='editor' and p['window']==window),None)
    if not editor:
        # Migrate sessions created before explicit editor roles were added.
        candidates=[p for p in items if p['window']==window and p['id']!=sidebar['id'] and not p['agent'] and not p['shell']]
        if len(candidates)!=1: raise ValueError('Cannot identify workspace editor')
        editor=candidates[0]
        core.tmux_checked('set-option','-p','-t',editor['id'],'@tmw_role','editor')
    return session,window,items,sidebar,editor


def park(pane):
    # Moving a pane to another window preserves its process and scrollback.
    session=core.tmux_checked('display-message','-p','-t',pane['id'],'#{session_name}')
    core.tmux_checked('break-pane','-d','-s',pane['id'],'-t',session+':','-n',
                      'saved-'+(pane['agent'] or pane['shell'] or 'terminal'))
    core.tmux_checked('set-option','-w','-t',pane['id'],'@tmw_parked','1')


def restore(pane,editor):
    core.tmux_checked('join-pane','-d','-v','-s',pane['id'],'-t',editor['id'])


def layout_string(body):
    checksum=0
    for value in body.encode():
        checksum=((checksum>>1)|((checksum&1)<<15))
        checksum=(checksum+value)&0xffff
    return f'{checksum:04x},{body}'


def arrange(project,previous=None):
    session,window,items,sidebar,editor=context(project)
    visible=[p for p in items if p['window']==window]
    agents=[next((p for p in visible if p['agent']==a),None) for a in core.AGENTS]
    agents=[p for p in agents if p]
    terminals=[p for p in visible if p['role']=='terminal']
    toolbars=[p for p in visible if p['role']=='terminal-toolbar']
    groups=[p for p in visible if p['role']=='project-view']
    tab_bars=[p for p in visible if p['role']=='editor-tabs']
    known=[sidebar,editor,*groups,*agents,*terminals,*toolbars,*tab_bars]
    if len(known)!=len(visible) or len(terminals)>1 or len(toolbars)>1:
        raise ValueError('Workspace contains extra panes; automatic layout was skipped')
    width,height=map(int,core.tmux_checked('display-message','-p','-t',window,
                                          '#{window_width}|#{window_height}').split('|'))
    top=core.tmux_checked('show-options','-qv','-t',session,'@tmw_dock')=='top'
    side_height=min(max(12,(previous or {}).get('dock_height',sidebar['height'])),max(12,height-16)) if top else height
    side_width=width if top else min(max(16,(previous or {}).get('dock_width',sidebar['width'])),max(16,width-21))
    right_width=width if top else width-side_width-1
    full_height=height
    height=height-side_height-1 if top else height
    origin_y=side_height+1 if top else 0
    sections=1+bool(agents)+bool(terminals)+bool(toolbars)+bool(tab_bars)
    if right_width<12 or height<sections*4+sections-1:
        raise ValueError('Make the terminal window larger to show these panes')
    ai_height=max(4,(previous or {}).get('ai_height',max(5,height//3))) if agents else 0
    terminal_height=max(4,(previous or {}).get('terminal_height',max(5,height//4))) if terminals else 0
    toolbar_height=1 if toolbars else 0
    tab_height=3 if tab_bars else 0
    budget=height-(sections-1)-4-toolbar_height-tab_height
    if ai_height+terminal_height>budget:
        ai_height=min(ai_height,budget-(4 if terminals else 0))
        terminal_height=min(terminal_height,budget-ai_height)
    editor_height=height-ai_height-terminal_height-toolbar_height-tab_height-(sections-1)
    x=0 if top else side_width+1
    placements={}
    def leaf(p,w,h,x,y):
        placements[p['id']]=(x,y)
        return f"{w}x{h},{x},{y},{p['id'][1:]}"
    tab_origin_y=origin_y
    origin_y+=tab_height+1 if tab_bars else 0
    editors=[editor,*groups]
    orientation=core.tmux_checked('show-options','-qv','-t',session,'@tmw_split') or 'right'
    if len(editors)==1:
        editor_body=leaf(editor,right_width,editor_height,x,origin_y)
    else:
        horizontal=orientation=='right'
        extent=right_width if horizontal else editor_height
        count=len(editors)
        if extent<count*4+count-1: raise ValueError('Enlarge the window before adding another split')
        unit=(extent-count+1)//count
        offset=0; cells=[]
        for index,pane in enumerate(editors):
            size=unit if index<count-1 else extent-offset
            cells.append(leaf(pane,size if horizontal else right_width,editor_height if horizontal else size,
                              x+offset if horizontal else x,origin_y if horizontal else origin_y+offset))
            offset+=size+1
        editor_body=f'{right_width}x{editor_height},{x},{origin_y}'+('{' if horizontal else '[')+','.join(cells)+('}' if horizontal else ']')
    children=([leaf(tab_bars[0],right_width,tab_height,x,tab_origin_y)] if tab_bars else [])+[editor_body]
    y=origin_y+editor_height+1
    if agents:
        if len(agents)==1:
            children.append(leaf(agents[0],right_width,ai_height,x,y))
        else:
            fraction=(previous or {}).get('ai_fraction',.5)
            left_width=max(4,min(right_width-5,round((right_width-1)*fraction)))
            row=leaf(agents[0],left_width,ai_height,x,y)+','+leaf(agents[1],right_width-left_width-1,ai_height,x+left_width+1,y)
            children.append(f'{right_width}x{ai_height},{x},{y}'+'{'+row+'}')
        y+=ai_height+1
    if toolbars:
        children.append(leaf(toolbars[0],right_width,toolbar_height,x,y))
        y+=toolbar_height+1
    if terminals: children.append(leaf(terminals[0],right_width,terminal_height,x,y))
    right=children[0] if len(children)==1 else f'{right_width}x{height},{x},{tab_origin_y}['+','.join(children)+']'
    body=f'{width}x{full_height},0,0'+('[' if top else '{')+leaf(sidebar,side_width,side_height,0,0)+','+right+(']' if top else '}')
    core.tmux_checked('select-layout','-t',window,layout_string(body))
    # tmux assigns layout leaves in its pane-list order, ignoring serialized IDs.
    # Restore the intended roles to each rectangle while keeping processes alive.
    for pane_id,position in placements.items():
        rows=core.tmux_checked('list-panes','-t',window,'-F','#{pane_id}|#{pane_left}|#{pane_top}')
        occupant=next(p for p,px,py in (row.split('|') for row in rows.splitlines())
                      if (int(px),int(py))==position)
        if occupant!=pane_id:
            core.tmux_checked('swap-pane','-d','-s',pane_id,'-t',occupant)


def sizes(items,window):
    current=[p for p in items if p['window']==window]
    ai=[p for p in current if p['agent']]
    claude=next((p for p in ai if p['agent']=='claude'),None)
    fraction=claude['width']/sum(p['width'] for p in ai) if len(ai)==2 and claude else .5
    return {'ai_height':next((p['height']+1 for p in current if p['agent']),16),
            'terminal_height':next((p['height']+1 for p in current if p['role']=='terminal'),10),
            'ai_fraction':fraction}


@serialized
def set_agents(project,enabled,persist=True):
    session,window,items,sidebar,editor=context(project)
    old_sizes=sizes(items,window)
    for agent in core.AGENTS:
        pane=next((p for p in items if p['agent']==agent),None)
        if enabled.get(agent,False):
            if pane and pane['window']!=window: restore(pane,editor)
            elif not pane:
                pane_id=core.tmux_checked('split-window','-d','-v','-t',editor['id'],
                     '-c',project['path'],'-P','-F','#{pane_id}',core.agent_command(project,agent))
                core.tmux_checked('set-option','-p','-t',pane_id,'@tmw_agent',agent)
                core.tmux_checked('set-option','-p','-t',pane_id,'@tmw_agent_ui','chat')
                core.tmux_checked('select-pane','-t',pane_id,'-T',agent.title())
        elif pane and pane['window']==window:
            park(pane)
    arrange(project,old_sizes)
    core.tmux_checked('select-window','-t',window)
    if not persist: return
    def update(records):
        record=next(p for p in records if p['id']==project['id'])
        record['agents']={agent:bool(enabled.get(agent,False)) for agent in core.AGENTS}
    core.locked_update(core.CONFIG,update)


def shell_command(kind,path):
    if kind not in SHELLS: raise ValueError('Unknown terminal profile')
    label,command=SHELLS[kind]
    if not Path(command[0]).is_file(): raise ValueError(label+' is not installed')
    if kind!='bash':
        converted=subprocess.run(['wslpath','-w',str(Path(path).resolve())],text=True,capture_output=True,timeout=2)
        if converted.returncode: raise ValueError('Could not convert the project path for Windows')
        location=converted.stdout.strip()
        if kind=='cmd':
            # pushd maps UNC WSL paths to a temporary drive; cmd cannot cd to UNC.
            # Escape command metacharacters rather than treating paths as shell source.
            if any(c in location for c in '\r\n"%!^&|<>'):
                raise ValueError('This project path is not supported by CMD; use Bash or PowerShell')
            command=[*command,'/K','pushd',location]
        else:
            command=[*command,'-Command',"Set-Location -LiteralPath '"+location.replace("'","''")+"'"]
    return label,shlex.join(command)


def terminals(project):
    session,window,items,_,_=context(project)
    return [dict(p,visible=p['window']==window,label=SHELLS.get(p['shell'],(p['shell'],))[0])
            for p in items if p['role']=='terminal']


@serialized
def show_terminal(project,pane_id=None,kind='bash',new=False,toggle=False,hide=False):
    session,window,items,sidebar,editor=context(project)
    old_sizes=sizes(items,window)
    current=next((p for p in items if p['role']=='terminal' and p['window']==window),None)
    target=next((p for p in items if p['id']==pane_id and p['role']=='terminal'),None) if pane_id else None
    if pane_id and not target: raise ValueError('Terminal no longer exists')
    if hide and not current: return
    if (toggle or hide) and current:
        core.tmux_checked('set-option','-t',session,'@tmw_last_terminal',current['id'])
        park(current)
        for toolbar in items:
            if toolbar['role']=='terminal-toolbar' and toolbar['window']==window: park(toolbar)
        arrange(project,old_sizes)
        core.tmux_checked('select-pane','-t',editor['id'])
        return
    if not target and not new:
        if toggle:
            last=core.tmux_checked('show-options','-qv','-t',session,'@tmw_last_terminal')
            target=next((p for p in items if p['id']==last and p['role']=='terminal' and not p['dead']),None)
    if not target and not new:
        target=next((p for p in items if p['role']=='terminal' and p['shell']==kind and not p['dead']),None)
    if not target: label,command=shell_command(kind,project['path'])
    if current and (not target or current['id']!=target['id']): park(current)
    if target:
        if target['window']!=window: restore(target,editor)
        pane=target['id']
    else:
        cwd='/mnt/c/Windows' if kind=='cmd' else project['path']
        pane=core.tmux_checked('split-window','-d','-v','-t',editor['id'],'-c',cwd,
                               '-P','-F','#{pane_id}',command)
        core.tmux_checked('set-option','-p','-t',pane,'@tmw_role','terminal')
        core.tmux_checked('set-option','-p','-t',pane,'@tmw_shell',kind)
        core.tmux_checked('select-pane','-t',pane,'-T',label)
    toolbar=next((p for p in items if p['role']=='terminal-toolbar'),None)
    if toolbar:
        if toolbar['window']!=window: restore(toolbar,editor)
    else:
        bar=core.tmux_checked('split-window','-d','-v','-t',editor['id'],'-c',project['path'],
                             '-P','-F','#{pane_id}',shlex.join([sys.executable,str(core.ROOT/'terminal-toolbar.py'),project['id']]))
        core.tmux_checked('set-option','-p','-t',bar,'@tmw_role','terminal-toolbar')
        core.tmux_checked('select-pane','-t',bar,'-T','Terminal controls')
    arrange(project,old_sizes)
    core.tmux_checked('set-option','-t',session,'@tmw_last_terminal',pane)
    selected_kind=target['shell'] if target else kind
    core.tmux_checked('set-option','-t',session,'@tmw_default_shell',selected_kind)
    core.tmux_checked('select-window','-t',window)
    core.tmux_checked('select-pane','-t',pane)




@serialized
def dock_workspace(project,position):
    if position not in ('left','top'): raise ValueError('Unknown workspace position')
    session,window,items,sidebar,editor=context(project)
    previous=sizes(items,window)
    old_position=core.tmux_checked('show-options','-qv','-t',session,'@tmw_dock') or 'left'
    core.tmux_checked('set-option','-t',session,'@tmw_dock',position)
    try: arrange(project,{**previous,'dock_height':16,'dock_width':34})
    except Exception:
        core.tmux_checked('set-option','-t',session,'@tmw_dock',old_position)
        arrange(project,previous)
        raise



@serialized
def split_project(project,target,direction='right'):
    if direction not in ('right','below'): raise ValueError('Unknown split direction')
    session,window,items,sidebar,editor=context(project)
    previous=sizes(items,window)
    groups=[p for p in items if p['role']=='project-view' and p['window']==window]
    if len(groups)>=2: raise ValueError('Up to three editor groups; close a split first')
    saved=next((p for p in items if p['role']=='project-view' and p['project']==target['id']
                and p['window']!=window and not p['dead']),None)
    old_direction=core.tmux_checked('show-options','-qv','-t',session,'@tmw_split') or 'right'
    if saved:
        restore(saved,editor)
        core.tmux_checked('set-option','-t',session,'@tmw_split',direction)
        try: arrange(project,previous)
        except Exception:
            park(saved)
            core.tmux_checked('set-option','-t',session,'@tmw_split',old_direction)
            arrange(project,previous)
            raise
        core.tmux_checked('select-pane','-t',saved['id'])
        return saved['id']
    executable=shutil.which('vim') or shutil.which('vi')
    if not executable: raise ValueError('Vim is required for project splits')
    root=Path(target['path'])
    entry=target.get('entry')
    file=(root/entry) if entry else next((p for p in sorted(root.iterdir()) if p.is_file() and not p.name.startswith('.')),None)
    if file and not file.resolve().is_relative_to(root.resolve()): raise ValueError('Entry must be inside project')
    command=[executable,'-u',str(core.ROOT/'editor.vim')]
    if file: command+=['--',str(file)]
    pane=core.tmux_checked('split-window','-d','-h' if direction=='right' else '-v','-t',editor['id'],
                           '-c',str(root),'-P','-F','#{pane_id}',shlex.join(command))
    core.tmux_checked('set-option','-p','-t',pane,'@tmw_role','project-view')
    core.tmux_checked('set-option','-p','-t',pane,'@tmw_project',target['id'])
    core.tmux_checked('select-pane','-t',pane,'-T',target['name'])
    core.tmux_checked('set-option','-t',session,'@tmw_split',direction)
    try: arrange(project,previous)
    except Exception:
        park(next(p for p in panes(session) if p['id']==pane))
        core.tmux_checked('set-option','-t',session,'@tmw_split',old_direction)
        arrange(project,previous)
        raise
    core.tmux_checked('select-pane','-t',pane)
    return pane


@serialized
def close_split(project):
    session,window,items,sidebar,editor=context(project)
    groups=[p for p in items if p['role']=='project-view' and p['window']==window]
    if not groups: return
    previous=sizes(items,window)
    park(groups[-1])
    arrange(project,previous)
    core.tmux_checked('select-pane','-t',editor['id'])


@serialized
def ensure_chat_panels(project):
    session,window,items,_,editor=context(project)
    previous=sizes(items,window)
    changed=False
    for agent in core.AGENTS:
        if not project.get('agents',{}).get(agent,True): continue
        old=next((p for p in items if p['agent']==agent),None)
        if not old: continue
        if core.tmux_checked('show-options','-pqv','-t',old['id'],'@tmw_agent_ui')=='chat': continue
        visible=old['window']==window
        # Park the original process; never respawn or inject input into an AI/shell.
        if visible: park(old)
        pane=core.tmux_checked('split-window','-d','-v','-t',editor['id'],'-c',project['path'],
            '-P','-F','#{pane_id}',core.agent_command(project,agent))
        core.tmux_checked('set-option','-p','-t',pane,'@tmw_agent',agent)
        core.tmux_checked('set-option','-p','-t',pane,'@tmw_agent_ui','chat')
        core.tmux_checked('select-pane','-t',pane,'-T',agent.title()+' Chat')
        core.tmux_checked('set-option','-p','-t',old['id'],'@tmw_saved_agent',agent)
        core.tmux_checked('set-option','-pu','-t',old['id'],'@tmw_agent')
        core.tmux_checked('set-option','-p','-t',old['id'],'@tmw_role','saved-agent')
        if not visible: park(next(p for p in panes(session) if p['id']==pane))
        changed=True
    if changed: arrange(project,previous)
