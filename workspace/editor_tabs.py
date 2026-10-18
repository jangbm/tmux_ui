"""Editor tabs within one workspace; hidden panes retain unsaved Vim buffers."""
import json
from pathlib import Path
import shlex
import shutil
import sys
import core
import layout


def ordered(project):
    session,window,items,_,editor=layout.context(project)
    raw=core.tmux_checked('show-options','-qv','-t',session,'@tmw_editor_tabs')
    try: keys=json.loads(raw) if raw else [editor['id'],*[p['id'] for p in items if p['role']=='project-view' and p['window']==window]]
    except ValueError: keys=[editor['id']]
    if not isinstance(keys,list): keys=[editor['id']]
    keys=list(dict.fromkeys(key for key in keys if isinstance(key,str)))
    if editor['id'] not in keys: keys.insert(0,editor['id'])
    candidates={p['id']:p for p in items if p['role'] in ('editor','project-view')}
    result=[]
    for key in keys:
        if key not in candidates: continue
        pane=candidates[key]
        identity=pane['project'] or project['id']
        record=next((p for p in core.projects() if p['id']==identity),{'name':identity})
        result.append(dict(pane,name=record['name'],project=identity,visible=pane['window']==window,primary=key==editor['id']))
    return result


def save_order(project,keys):
    core.tmux_checked('set-option','-t',core.session_id(project['id']),'@tmw_editor_tabs',json.dumps(keys))


def ensure(project):
    session,window,items,_,editor=layout.context(project)
    if not editor['project']:
        core.tmux_checked('set-option','-p','-t',editor['id'],'@tmw_project',project['id'])
    save_order(project,[p['id'] for p in ordered(project)])
    bar=next((p for p in items if p['role']=='editor-tabs'),None)
    if bar and bar['window']!=window:
        layout.restore(bar,editor)
    if not bar:
        pane=core.tmux_checked('split-window','-d','-v','-b','-l','3','-t',editor['id'],
            '-P','-F','#{pane_id}',shlex.join([sys.executable,str(core.ROOT/'editor-tabs.py'),project['id']]))
        core.tmux_checked('set-option','-p','-t',pane,'@tmw_role','editor-tabs')
        core.tmux_checked('select-pane','-t',pane,'-T','Editor tabs')


def spawn(project,target):
    _,_,_,_,editor=layout.context(project)
    root=Path(target['path']).resolve()
    if target.get('kind')=='tmux-live':
        command=[sys.executable,str(core.ROOT/'live-view.py'),target['id']]
    else:
        executable=shutil.which('vim') or shutil.which('vi')
        if not executable: raise ValueError('Vim is required')
        file=root/target['entry'] if target.get('entry') else next((p for p in sorted(root.iterdir()) if p.is_file() and not p.name.startswith('.')),None)
        if file and not file.resolve().is_relative_to(root): raise ValueError('Entry outside project')
        command=[executable,'-u',str(core.ROOT/'editor.vim')]
        if file: command+=['--',str(file)]
    pane=core.tmux_checked('split-window','-d','-h','-t',editor['id'],'-c',str(root),'-P','-F','#{pane_id}',shlex.join(command))
    core.tmux_checked('set-option','-p','-t',pane,'@tmw_role','project-view')
    core.tmux_checked('set-option','-p','-t',pane,'@tmw_project',target['id'])
    core.tmux_checked('select-pane','-t',pane,'-T',target['name'])
    return next(p for p in layout.panes(core.session_id(project['id'])) if p['id']==pane)


def activate(project,pane):
    session,window,items,_,editor=layout.context(project)
    if pane['window']!=window:
        layout.restore(pane,editor)
        core.tmux_checked('set-option','-p','-t',editor['id'],'@tmw_role','project-view')
        core.tmux_checked('set-option','-p','-t',pane['id'],'@tmw_role','editor')
        layout.park(editor)
    core.tmux_checked('set-option','-t',session,'@tmw_selected_tab',pane['id'])
    core.tmux_checked('set-option','-t',session,'@tmw_chat_project',pane.get('project') or project['id'])
    core.tmux_checked('select-window','-t',window)
    core.tmux_checked('select-pane','-t',pane['id'])


@layout.serialized
def open_project(project,target):
    session,window,items,_,_=layout.context(project)
    previous=layout.sizes(items,window)
    ensure(project)
    tabs=ordered(project)
    pane=next((p for p in tabs if p['project']==target['id'] and not p['dead']),None)
    if not pane:
        pane=next((p for p in layout.panes(session) if p['role']=='project-view' and p['project']==target['id'] and not p['dead']),None)
        if not pane: pane=spawn(project,target)
        save_order(project,[p['id'] for p in tabs]+[pane['id']])
        # New tabs replace the primary group, rather than creating a split.
        if pane['window']==window:
            _,_,_,_,editor=layout.context(project)
            core.tmux_checked('set-option','-p','-t',editor['id'],'@tmw_role','project-view')
            core.tmux_checked('set-option','-p','-t',pane['id'],'@tmw_role','editor')
            layout.park(editor)
    activate(project,pane)
    layout.arrange(project,previous)
    return pane['id']


@layout.serialized
def select(project,pane_id):
    tabs=ordered(project)
    pane=next((p for p in tabs if p['id']==pane_id),None)
    if not pane: raise ValueError('Tab no longer open')
    _,window,items,_,_=layout.context(project)
    previous=layout.sizes(items,window)
    activate(project,pane)
    layout.arrange(project,previous)


@layout.serialized
def split(project,pane_id,direction):
    if direction not in ('right','below'): raise ValueError('Unknown split direction')
    session,window,items,_,editor=layout.context(project)
    previous=layout.sizes(items,window)
    tabs=ordered(project)
    pane=next((p for p in tabs if p['id']==pane_id),None)
    if not pane: raise ValueError('Tab no longer open')
    groups=[p for p in items if p['role']=='project-view' and p['window']==window]
    adding=pane['id']==editor['id'] or pane['window']!=window
    if adding and len(groups)>=2: raise ValueError('Close a split before adding another group')
    rows=core.tmux_checked('list-panes','-t',window,'-F','#{pane_id}|#{pane_left}|#{pane_top}|#{pane_width}|#{pane_height}')
    editor_ids={editor['id'],*[p['id'] for p in groups]}
    cells=[list(map(int,parts[1:])) for row in rows.splitlines() if (parts:=row.split('|'))[0] in editor_ids]
    axis=0 if direction=='right' else 1
    extent=max(c[axis]+c[axis+2]+1 for c in cells)-min(c[axis] for c in cells)
    count=1+len(groups)+int(adding)
    if extent<count*4+count-1: raise ValueError('Make the code area larger before splitting')
    if pane['id']==editor['id']:
        replacement=next((p for p in tabs if not p['visible'] and not p['dead']),None)
        if not replacement:
            target=next(p for p in core.projects() if p['id']==pane['project'])
            replacement=spawn(project,target)
            save_order(project,[p['id'] for p in tabs]+[replacement['id']])
        elif replacement['window']!=window: layout.restore(replacement,editor)
        core.tmux_checked('set-option','-p','-t',editor['id'],'@tmw_role','project-view')
        core.tmux_checked('set-option','-p','-t',replacement['id'],'@tmw_role','editor')
    elif pane['window']!=window:
        if len(groups)>=2: raise ValueError('Close a split before adding another group')
        layout.restore(pane,editor)
    core.tmux_checked('set-option','-t',session,'@tmw_split',direction)
    layout.arrange(project,previous)
    core.tmux_checked('set-option','-t',session,'@tmw_selected_tab',pane_id)
    core.tmux_checked('set-option','-t',session,'@tmw_chat_project',pane.get('project') or project['id'])
    core.tmux_checked('select-pane','-t',pane_id)


@layout.serialized
def reorder(project,source,target):
    keys=[p['id'] for p in ordered(project)]
    if source==target or source not in keys or target not in keys: return
    after=keys.index(source)<keys.index(target)
    keys.remove(source); keys.insert(keys.index(target)+int(after),source)
    save_order(project,keys)


@layout.serialized
def close(project,pane_id):
    session,window,items,_,editor=layout.context(project)
    previous=layout.sizes(items,window)
    tabs=ordered(project)
    if len(tabs)<2: raise ValueError('Keep at least one editor tab open')
    pane=next((p for p in tabs if p['id']==pane_id),None)
    if not pane: return
    if pane_id==editor['id']:
        replacement=next((p for p in tabs if p['id']!=pane_id and not p['dead']),None)
        if not replacement: raise ValueError('Open another live editor before closing this tab')
        if replacement['window']!=window: layout.restore(replacement,editor)
        core.tmux_checked('set-option','-p','-t',replacement['id'],'@tmw_role','editor')
        core.tmux_checked('set-option','-p','-t',pane_id,'@tmw_role','project-view')
    if pane['window']==window: layout.park(pane)
    save_order(project,[p['id'] for p in tabs if p['id']!=pane_id])
    layout.arrange(project,previous)
    _,_,_,_,current=layout.context(project)
    core.tmux_checked('set-option','-t',session,'@tmw_selected_tab',current['id'])
    core.tmux_checked('set-option','-t',session,'@tmw_chat_project',current.get('project') or project['id'])
    core.tmux_checked('select-pane','-t',current['id'])


@layout.serialized
def initialize(project):
    import desktop
    if desktop.enabled(project):
        desktop.ensure_running(project)
        return
    session,window,items,_,_=layout.context(project)
    previous=layout.sizes(items,window)
    existing=next((p for p in items if p['role']=='editor-tabs' and p['window']==window),None)
    ensure(project)
    if existing: return
    try: layout.arrange(project,previous)
    except Exception:
        bar=next((p for p in layout.panes(session) if p['role']=='editor-tabs' and p['window']==window),None)
        if bar: layout.park(bar)
        layout.arrange(project,previous)
        raise
