#!/usr/bin/env python3
"""Project sidebar; each tmux session has a view of one shared registry/status store."""
import asyncio, os, shlex, sys
from pathlib import Path
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal, VerticalScroll, ScrollableContainer
from textual.widgets import Tree, Static, Input, Button, Checkbox, TabbedContent, TabPane, DirectoryTree
from textual import on, work
import core
import layout
import editor_tabs
import desktop
import watcher
import live_tmux
from textual.widgets import Select, OptionList
from textual.widgets.option_list import Option
SPINNER='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
AGENT_COLORS={'claude':'#d9a07e','codex':'#83b6d8'}

class ProjectTab(Static):
    def __init__(self,project,active=False,compact=False):
        badge=(' · '+(' / '.join(a.title() for a in core.AGENTS if project.get('source_agents',{}).get(a)) or 'AI 없음')) if project.get('kind')=='tmux-live' else ''
        if project.get('source_agents_error'): badge=' · AI 확인 불가'
        super().__init__(('● ' if active else '◇ ')+project['name']+('' if compact else badge),markup=False,classes='project-tab')
        self.tooltip=project['name']+badge
        self.project_id=project['id']
    def on_mouse_down(self,event):
        if event.button!=1: return
        self.start=(event.screen_x,event.screen_y)
        self.capture_mouse()
        event.stop()
    def on_mouse_up(self,event):
        if not hasattr(self,'start'): return
        self.release_mouse()
        origin=self.start; del self.start
        event.stop()
        if abs(event.screen_x-origin[0])+abs(event.screen_y-origin[1])>0:
            for tab in self.app.query(ProjectTab):
                if tab.region.contains(event.screen_x,event.screen_y):
                    keys=[p['id'] for p in core.projects()]
                    if self.project_id in keys and tab.project_id in keys:
                        core.reorder_project(self.project_id,tab.project_id,after=keys.index(tab.project_id)>keys.index(self.project_id))
                    self.app.refresh_projects(force=True)
                    break
        else: self.app.open_project(self.project_id)


class ProjectFiles(DirectoryTree):
    ICON_NODE=''
    ICON_NODE_EXPANDED=''
    ICON_FILE=''
    SKIP={'.git','.venv','venv','node_modules','__pycache__','Library','Temp','obj'}

    def filter_paths(self,paths):
        return [path for path in paths if path.name not in self.SKIP and not path.is_symlink()]

class ProjectTree(Tree):
    def render_label(self,node,base_style,style):
        label=super().render_label(node,base_style,style)
        start=label.plain.find('결과')
        if start>=0: label.stylize('bold #f08080',start)
        return label


class Sidebar(App):
    def __init__(self,*args,**kwargs):
        os.environ.pop('NO_COLOR',None)
        super().__init__(*args,**kwargs)
    TITLE='Workspace'
    CSS='''
    Screen { background: #202020; color: #d6d6d6; }
    #identity { display: none; }
    #project-tabs { display: none; layout: vertical; height: auto; max-height: 6; overflow: auto auto; scrollbar-size: 1 1; }
    .project-tab { height: 1; width: 100%; padding: 0 1; color: #93b9d2; }
    .project-tab:hover { background: #2b3741; }
    #dock-tools { height: 1; padding: 0 1; background: #252b30; }
    #dock-label { width: 1fr; height: 1; color: #798996; }
    #dock-tools Button { height: 1; min-width: 8; width: 8; padding: 0; border: none; background: transparent; color: #8c9ba7; }
    #dock-tools Button:hover { background: #35424d; color: #dfedf6; }
    #dock-tools Button.selected { background: #2d3b47; color: #a8cee8; }
    Screen.top #project-tabs { display: block; layout: horizontal; height: 3; max-height: 3; }
    Screen.top .project-tab { width: auto; min-width: 10; height: 3; margin-right: 1; padding: 0 1; content-align: center middle; border: round #4b514d; border-bottom: none; }
    Screen.top #identity, Screen.top #summary { display: none; }
    Screen.top #section { height: 1; }
    Screen.top #tree { display: block; }
    #identity { height: 3; padding: 0 2; border-bottom: solid #303030; }
    #wordmark { color: #e8e8e8; text-style: bold; height: 1; }
    #active-project { color: #a0a0a0; height: 1; }
    #section { height: 1; padding: 0 1 0 2; align-vertical: middle; }
    #section-title { width: 1fr; color: #a0a0a0; height: 1; }
    #section Button { min-width: 3; width: 3; height: 1; border: none; background: #202020; color: #93b9d2; }
    #section Button:hover { background: #353535; color: #ffffff; }
    Tree { height: 1fr; background: #202020; padding: 0 1; scrollbar-size: 1 1; }
    Tree:focus { background-tint: #202020 0%; }
    Tree > .tree--guides { color: #414141; }
    Tree > .tree--guides-hover { color: #707070; }
    Tree > .tree--guides-selected { color: #707070; }
    Tree > .tree--cursor { background: #303030; text-style: none; }
    Tree:focus > .tree--cursor { background: #2b3741; color: #eeeeee; text-style: none; }
    Tree > .tree--highlight-line { background: #2a2a2a; }
    DirectoryTree > .directory-tree--folder { color: #c8c8c8; }
    DirectoryTree > .directory-tree--file { color: #b8b8b8; }
    DirectoryTree > .directory-tree--extension { color: #a6bfd8; text-style: none; }
    TabbedContent { height: 1fr; }
    TabPane { padding: 0; }
    Tabs { background: #202020; }
    Tab { padding: 0 1; color: #a0a0a0; background: #202020; }
    Tab.-active { color: #93b9d2; background: #2a2d2a; }
    Underline > .underline--bar { color: #8fbd9b; background: #303030; }
    #git-scroll { padding: 1 2; }
    #git-status { color: #c8c8c8; height: auto; }
    #no-project { color: #a0a0a0; padding: 1 2; height: auto; }
    #summary { height: 1; margin: 0 2; color: #a0a0a0; }
    #form { display: none; height: auto; max-height: 75%; overflow-y: auto; padding: 1 2; background: #252525; border-bottom: solid #414141; }
    #form.visible { display: block; }
    #form-title { color: #e8e8e8; text-style: bold; margin-bottom: 1; }
    Input { margin-bottom: 1; background: #181818; border: tall #414141; color: #eeeeee; }
    Input:focus { border: tall #9cb49f; }
    Input > .input--placeholder { color: #999999; }
    Checkbox { background: #252525; border: none; padding: 0; height: 3; }
    Checkbox:focus { background: #303030; }
    #actions { height: 3; margin-top: 1; }
    #actions Button { min-width: 10; height: 3; border: none; margin-right: 1; background: #353535; color: #d6d6d6; }
    #actions #create { background: #8fbd9b; color: #171b18; text-style: bold; }
    #actions Button:hover { tint: #ffffff 10%; }
    #agent-form { display: none; height: auto; max-height: 80%; overflow-y: auto; padding: 1 2; background: #252525; }
    #agent-form.visible { display: block; }
    #agent-title { height: 1; color: #93b9d2; }
    #agent-actions { height: 3; }
    #agent-actions Button { min-width: 10; height: 3; border: none; background: #353535; margin-right: 1; }
    #terminal-tools { height: auto; padding: 1; }
    #terminal-tools Button { height: 1; width: 3; min-width: 3; border: none; background: #353535; }
    #terminal-actions { height: 1; align-horizontal: right; }
    Select { background: #252525; }
    #terminal-list { height: 1fr; border: none; background: #202020; color: #d6d6d6; }
    #terminal-help { height: auto; padding: 1 2; color: #a0a0a0; }
    '''
    BINDINGS=[('n','new_project','New'),('i','import_project','Import'),('a','agent_settings','Agents'),('r','refresh','Refresh'),('escape','cancel_form','Cancel'),('q','quit','Close')]
    def compose(self)->ComposeResult:
        with Vertical(id='identity'):
            yield Static('◇  WORKSPACE',id='wordmark')
            yield Static('Projects & agents',id='active-project',markup=False)
        yield ScrollableContainer(id='project-tabs')
        with TabbedContent(initial='projects-view',id='views'):

            with TabPane('Projects',id='projects-view'):
                with Horizontal(id='section'):
                    yield Static('PROJECTS',id='section-title')
                    yield Button('⋯',id='agent-settings')
                    yield Button('+',id='new-project')
                with Vertical(id='agent-form'):
                    yield Static('Project agents',id='agent-title')
                    yield Checkbox('Claude',id='show-claude',value=True)
                    yield Checkbox('Codex',id='show-codex',value=True)
                    with Horizontal(id='agent-actions'):
                        yield Button('Apply',id='apply-agents')
                        yield Button('Cancel',id='cancel-agents')
                with Vertical(id='form'):
                    yield Static('New project',id='form-title')
                    yield Input(placeholder='Project name',id='name')
                    yield Input(placeholder='ID (optional, e.g. my-project)',id='project-id')
                    yield Input(placeholder='New folder: ~/Projects/demo',id='path')
                    yield Checkbox('Use existing folder',id='existing')
                    yield Checkbox('Initialize Git',id='git',value=True)
                    yield Checkbox('Use Claude',id='use-claude',value=True)
                    yield Checkbox('Use Codex',id='use-codex',value=True)
                    yield Checkbox('Launch AI CLIs',id='agents',value=False)
                    with Horizontal(id='actions'):
                        yield Button('Create',id='create',variant='primary')
                        yield Button('Cancel',id='cancel')
                yield ProjectTree('PROJECTS',id='tree')
            with TabPane('Files',id='files-view'):
                yield Static('Open a project to browse files.',id='no-project')
                yield ProjectFiles(core.ROOT/'data',id='files')
            with TabPane('Git',id='git-view'):
                with VerticalScroll(id='git-scroll'):
                    yield Static('Open a project to see Git changes.',id='git-status',markup=False)
            with TabPane('Terminal',id='terminal-view'):
                with Vertical(id='terminal-tools'):
                    yield Select([(label,key) for key,(label,_) in layout.SHELLS.items()],value='bash',allow_blank=False,id='shell-kind')
                    with Horizontal(id='terminal-actions'):
                        yield Button('+',id='new-terminal',tooltip='New terminal with selected shell')
                        yield Button('↥',id='toggle-terminal',tooltip='Show or hide terminal')
                        yield Button('×',id='hide-terminal',tooltip='Hide terminal; keep shell running')
                yield OptionList(id='terminal-list')
                yield Static('Select a terminal to restore it.\nCtrl+` toggles the bottom panel.',id='terminal-help')
        yield Static('',id='summary')
        with Horizontal(id='dock-tools'):
            yield Static('배치',id='dock-label')
            yield Button('▤ 상단',id='dock-top',tooltip='프로젝트 목록을 상단에 배치')
            yield Button('▥ 왼쪽',id='dock-left',tooltip='프로젝트 목록을 왼쪽에 배치')
    def on_mount(self):
        self.frame=0; self.nodes={}; self.live_nodes={}; self.project_nodes={}; self.registry_signature=None
        self.status_summary=self.query_one('#summary',Static)
        self.active_project=os.environ.get('TMW_PROJECT','')
        self.dock_position=None
        self.dock_tick=0
        self.sync_dock()
        self.query_one('#tree',Tree).show_root=False
        self.query_one('#new-project',Button).tooltip='New project (n)'
        self.query_one('#agent-settings',Button).tooltip='Project agents (a)'
        self.refresh_projects()
        self.query_one('#tree',Tree).focus()
        self.spin_timer=self.set_interval(.22,self.tick)
        self.poll_timer=self.set_interval(8,self.poll_git)
        self.status_timer=self.set_interval(watcher.INTERVAL,self.collect_status)
        self.collect_status()
    def on_unmount(self):
        self.spin_timer.stop()
        self.poll_timer.stop()
        self.status_timer.stop()
    @work(exclusive=True,group='status')
    async def collect_status(self):
        await asyncio.to_thread(watcher.refresh)
        await asyncio.to_thread(live_tmux.refresh_connections)
    @on(Button.Pressed,'#new-project')
    def new_project(self): self.action_new_project()
    def action_new_project(self):
        self.query_one('#agent-form').remove_class('visible')
        self.query_one('#views',TabbedContent).active='projects-view'
        self.query_one('#existing',Checkbox).value=False
        self.query_one('#form').add_class('visible')
        self.call_after_refresh(self.query_one('#name',Input).focus)
    def action_import_project(self):
        self.action_new_project()
        self.query_one('#existing',Checkbox).value=True
    @on(Checkbox.Changed,'#existing')
    def import_mode(self,event):
        importing=event.value
        self.query_one('#form-title',Static).update('Import project' if importing else 'New project')
        self.query_one('#git',Checkbox).disabled=importing
        self.query_one('#create',Button).label='Register' if importing else 'Create'
        self.query_one('#path',Input).placeholder='Existing folder path' if importing else 'New folder: ~/Projects/demo'
    @on(Button.Pressed,'#cancel')
    def cancel(self): self.action_cancel_form()
    def action_cancel_form(self):
        self.query_one('#form').remove_class('visible')
        self.query_one('#agent-form').remove_class('visible')
        self.query_one('#tree',Tree).focus()
    @on(Button.Pressed,'#agent-settings')
    def agent_settings(self): self.action_agent_settings()
    def action_agent_settings(self):
        project=self.current_project()
        if not project:
            self.notify('Open a project first'); return
        self.query_one('#views',TabbedContent).active='projects-view'
        self.query_one('#form').remove_class('visible')
        self.query_one('#agent-form').add_class('visible')
        grouped=desktop.enabled(project)
        target=core.chat_project(project) if grouped else project
        self.settings_context_id=target['id']
        available=target.get('source_agents',{}) if target.get('kind')=='tmux-live' else target.get('agents',{})
        self.query_one('#agent-title',Static).update(target['name']+' · 대화창 표시')
        for agent in core.AGENTS:
            checkbox=self.query_one('#show-'+agent,Checkbox)
            checkbox.disabled=bool(grouped and target.get('kind')=='tmux-live' and not available.get(agent))
            checkbox.value=bool(available.get(agent,not grouped))
        self.call_after_refresh(self.query_one('#show-claude',Checkbox).focus)
    @on(Button.Pressed,'#cancel-agents')
    def cancel_agents(self): self.action_cancel_form()
    @on(Button.Pressed,'#apply-agents')
    def apply_agents(self):
        project=self.current_project()
        if not project: return
        try:
            enabled={a:self.query_one('#show-'+a,Checkbox).value for a in core.AGENTS}
            if desktop.enabled(project): desktop.request(project,'agent_visibility',project=getattr(self,'settings_context_id',project['id']),enabled=enabled)
            else: layout.set_agents(project,enabled)
            self.action_cancel_form()
            self.refresh_projects(force=True)
        except (OSError,ValueError,RuntimeError) as error:
            self.notify(str(error),severity='error',timeout=8)
    @on(Button.Pressed,'#create')
    def create(self):
        name=self.query_one('#name',Input).value.strip()
        path=self.query_one('#path',Input).value.strip()
        if not name or not path:
            self.notify('Name and path are required',severity='error');return
        try:
            key=self.query_one('#project-id',Input).value.strip() or None
            mode='import' if self.query_one('#existing',Checkbox).value else 'create'
            obj=core.add(name,path,key=key,mode=mode,git=self.query_one('#git',Checkbox).value,
                         claude=self.query_one('#use-claude',Checkbox).value,codex=self.query_one('#use-codex',Checkbox).value)
            self.action_cancel_form()
            for field in ('name','project-id','path'): self.query_one('#'+field,Input).value=''
            self.refresh_projects(force=True)
            self.notify('Project registered: '+name)
        except Exception as e: self.notify(str(e),severity='error',timeout=6)
        else:
            try:
                workspace=self.current_project()
                if workspace and desktop.enabled(workspace): desktop.request(workspace,'open',project=obj['id'])
                else:
                    core.create_session(obj,launch_agents=self.query_one('#agents',Checkbox).value)
                    editor_tabs.initialize(obj)
            except Exception as e: self.notify('Registered; could not open session: '+str(e),severity='error',timeout=8)
    def current_project(self):
        return next((p for p in core.projects() if p['id']==self.active_project),None)
    def refresh_files(self):
        workspace=self.current_project()
        project=core.chat_project(workspace) if workspace else None
        tree=self.query_one('#files',ProjectFiles)
        tree.display=bool(project)
        self.query_one('#no-project').display=not project
        if project: tree.path=Path(project['path'])
    def action_refresh(self):
        self.refresh_projects(force=True)
        self.query_one('#files',ProjectFiles).reload()
        self.refresh_git()
    @on(TabbedContent.TabActivated)
    def view_changed(self,event):
        if event.pane.id=='git-view': self.refresh_git()
        if event.pane.id=='terminal-view': self.refresh_terminals()
    def poll_git(self):
        if self.query_one('#views',TabbedContent).active=='git-view': self.refresh_git()
        if self.query_one('#views',TabbedContent).active=='terminal-view': self.refresh_terminals()
    @work(exclusive=True,group='terminals')
    async def refresh_terminals(self):
        project=self.current_project()
        if not project: return
        try:
            items=await asyncio.to_thread(layout.terminals,project)
            options=self.query_one('#terminal-list',OptionList)
            options.clear_options()
            options.add_options([Option(Text(('● ' if p['visible'] else '○ ')+p['label']+' '+p['id']+(' · exited' if p['dead'] else '')),id=p['id']) for p in items])
        except (OSError,ValueError,RuntimeError) as error:
            self.notify(str(error),severity='error')
    @on(Button.Pressed,'#new-terminal')
    def new_terminal(self): self.terminal_action(new=True)
    @on(Button.Pressed,'#toggle-terminal')
    def toggle_terminal(self): self.terminal_action(toggle=True)
    @on(Button.Pressed,'#hide-terminal')
    def hide_terminal(self): self.terminal_action(hide=True)
    def terminal_action(self,**options):
        project=self.current_project()
        if not project: return
        try:
            layout.show_terminal(project,kind=self.query_one('#shell-kind',Select).value,**options)
            self.refresh_terminals()
        except (OSError,ValueError,RuntimeError) as error:
            self.notify(str(error),severity='error',timeout=8)
    @on(OptionList.OptionSelected,'#terminal-list')
    def choose_terminal(self,event): self.terminal_action(pane_id=event.option.id)
    @work(exclusive=True,group='git')
    async def refresh_git(self):
        project=self.current_project()
        if not project: return
        snapshot=await asyncio.to_thread(core.git_snapshot,project['path'])
        if 'error' in snapshot:
            text=snapshot['error']
        else:
            text=f"{snapshot['branch']}\n\n"
            text+=f"{snapshot['staged']} staged · {snapshot['modified']} modified\n"
            text+=f"{snapshot['untracked']} untracked · {snapshot['conflicts']} conflicts\n\n"
            text+='\n'.join(f'{code} {name}' for code,name in snapshot['files']) or 'Working tree clean'
            if len(snapshot['files'])==200: text+='\n\nShowing up to 200 paths'
        self.query_one('#git-status',Static).update(text)
    @on(DirectoryTree.FileSelected,'#files')
    async def file_selected(self,event):
        project=self.current_project()
        if not project: return
        try:
            await asyncio.to_thread(core.preview_text,project['path'],event.path)
            command=shlex.join([sys.executable,str(core.ROOT/'file-preview.py'),project['path'],str(event.path)])
            result=await asyncio.to_thread(core.tmux,'display-popup','-E','-w','85%','-h','85%',command)
            if result.returncode: raise RuntimeError(result.stderr.strip())
        except (OSError,ValueError,RuntimeError) as error:
            self.notify(str(error),severity='error')
    def refresh_projects(self,force=False):
        items=[p for p in core.projects() if not p.get('navigation_hidden')]
        signature=tuple((p['id'],p['name'],tuple(k for k,v in p.get('agents',{}).items() if v),tuple(sorted(p.get('source_agents',{}).items())),p.get('source_agents_error','')) for p in items)
        if not force and signature==self.registry_signature: return
        self.registry_signature=signature
        tabs=self.query_one('#project-tabs',ScrollableContainer)
        tabs.remove_children()
        tabs.mount(*(ProjectTab(p,p['id']==self.active_project,compact=self.dock_position=='top') for p in items))
        tree=self.query_one('#tree',Tree)
        tree.root.remove_children(); self.nodes={}; self.live_nodes={}; self.project_nodes={}
        current=next((p for p in items if p['id']==self.active_project),None)
        if current: self.query_one('#active-project',Static).update(core.chat_project(current)['name'])
        self.query_one('#section-title',Static).update(f'PROJECTS  {len(items):02}')
        for project in items:
            label=Text(project['name'],style='bold #e8e8e8')
            if project['id']==self.active_project: label.append('  •',style='#8fbd9b')
            node=tree.root.add(label,data=('project',project['id']),expand=True)
            self.project_nodes[project['id']]=node
            if project.get('kind')=='tmux-live':
                connected=project.get('source_agents',{})
                if project.get('source_agents_error'):
                    node.add_leaf(Text('AI 연결 확인 불가',style='#d9bc88'),data=('project',project['id']))
                elif connected:
                    for agent in core.AGENTS:
                        if connected.get(agent):
                            count=connected[agent]
                            leaf=node.add_leaf(agent.title(),data=('project',project['id']))
                            self.live_nodes[(project['id'],agent)]=(leaf,count)
                else:
                    node.add_leaf(Text('○ 실행 중인 AI 없음',style='#a0a0a0'),data=('project',project['id']))

            for agent in core.AGENTS:
                if project.get('agents',{}).get(agent,True):
                    leaf=node.add_leaf(agent.title(),data=('agent',project['id'],agent))
                    self.nodes[(project['id'],agent)]=leaf
        tree.root.expand()
        self.paint_status()
        self.refresh_files()
    def sync_dock(self):
        if not self.active_project: return
        result=core.tmux('show-options','-qv','-t',core.session_id(self.active_project),'@tmw_dock')
        position=result.stdout.strip() or 'left'
        if position!=self.dock_position:
            self.dock_position=position
            self.registry_signature=None
            self.screen.set_class(position=='top','top')
            self.query_one('#dock-top',Button).set_class(position=='top','selected')
            self.query_one('#dock-left',Button).set_class(position=='left','selected')
    @on(Button.Pressed,'#dock-tools Button')
    def workspace_action(self,event):
        project=self.current_project()
        if not project: return
        try:
            layout.dock_workspace(project,event.button.id.removeprefix('dock-'))
            self.sync_dock()
        except (OSError,ValueError,RuntimeError) as error: self.notify(str(error),severity='error')
    def open_project(self,key):
        obj=next((p for p in core.projects() if p['id']==key),None)
        if not obj: return
        try:
            project=self.current_project()
            if not project: return
            if desktop.enabled(project): desktop.request(project,'open',project=obj['id'])
            else: editor_tabs.open_project(project,obj)
        except (OSError,ValueError,RuntimeError) as error: self.notify(str(error),severity='error')
    def sync_project_label(self):
        workspace=self.current_project()
        if not workspace: return
        selected=core.chat_project(workspace)
        if selected.get('kind')=='tmux-live' and not selected.get('source_agents_error'):
            enabled={agent:bool(selected.get('source_agents',{}).get(agent)) for agent in core.AGENTS}
        else: enabled={agent:bool(selected.get('agents',{}).get(agent,True)) for agent in core.AGENTS}
        signature=(selected['id'],tuple(enabled.items()))
        if signature!=getattr(self,'ai_context_signature',None):
            if not desktop.enabled(workspace) and core.tmux('has-session','-t','='+core.session_id(workspace['id'])).returncode==0:
                try: layout.set_agents(workspace,enabled,persist=False)
                except (ValueError,RuntimeError,OSError): pass
            self.ai_context_signature=signature
        if selected['id']!=getattr(self,'display_project_id',None):
            self.display_project_id=selected['id']
            self.query_one('#active-project',Static).update(selected['name'])
            self.refresh_files()
    def tick(self):
        self.dock_tick+=1
        if self.dock_tick%10==0: self.sync_dock()
        if self.dock_tick%3==0: self.sync_project_label()
        self.frame=(self.frame+1)%len(SPINNER)
        self.refresh_projects()
        self.paint_status()
    def paint_status(self):
        all_status=core.status()
        projects={p['id']:p for p in core.projects()}
        for (key,agent),(node,count) in self.live_nodes.items():
            record=projects.get(key,{})
            raw=record.get('source_states',{}).get(agent,{})
            state=raw.get('state','unknown')
            icon,color,caption={
                'busy':(SPINNER[self.frame],'#83b6d8','작업 중'),
                'waiting':('◆','#e3bb73','입력 대기'),
                'idle':('✓','#8fbd9b','준비'),
                'error':('!','#de8f91','확인 필요'),
            }.get(state,('●' if self.frame<5 else '○','#879cae','실행 중'))
            if record.get('source_agents_error'): icon,color,caption='?','#e3bb73','확인 불가'
            pending=raw.get('pending')
            if pending:
                icon,color,caption='!','#f08080','결과 · 승인 대기' if pending=='approval' else '결과'
            label=Text(f'{icon} ',style=color)
            label.append(agent.title(),style=AGENT_COLORS[agent])
            label.append(' '+caption+(f' · {count}개' if count>1 else ''),style=color)
            node.set_label(label)
        for key,node in self.project_nodes.items():
            record=projects.get(key,{})
            label=Text(record.get('name',key),style='bold #e8e8e8')
            if any(s.get('pending') for s in record.get('source_states',{}).values()):
                label.append('  결과',style='bold #f08080')
            node.set_label(label)
        waiting=busy=0
        for (project,agent),node in self.nodes.items():
            raw=all_status.get(project,{}).get(agent,{})
            state=raw.get('state','unknown') if isinstance(raw,dict) else raw
            waiting+=state=='waiting'; busy+=state=='busy'
            icon,color,caption={
                'done':('✓','#8fbd9b','완료'),
                'busy':(SPINNER[self.frame],'#a6bfd8','작업 중'),
                'waiting':('!','#d9bc88','입력 대기'),
                'error':('×','#dc9999','Error'),
                'idle':('○','#a0a0a0','준비'),
                'unknown':('·','#a0a0a0','Unknown'),
            }.get(state,('·','#a0a0a0','Unknown'))
            if state=='unknown' and isinstance(raw,dict) and raw.get('detail')=='not-running':
                icon,caption='○','Not started'
            if state=='idle' and isinstance(raw,dict) and raw.get('detail')=='chat-ready':
                caption='채팅 준비'
            if state=='waiting' and isinstance(raw,dict) and raw.get('detail')=='draft':
                caption='Draft'
            label=Text(f'{icon} ',style=color)
            label.append(f'{agent.title():7}',style=AGENT_COLORS[agent])
            label.append(f' {caption}',style=color)
            if isinstance(raw,dict) and state in ('done','waiting','error') and not raw.get('seen',True):
                label.append(' •',style='#d9bc88')
            node.set_label(label)
        live_count=sum(sum(p.get('source_agents',{}).values()) for p in core.projects() if p.get('kind')=='tmux-live')
        summary=f'운영 AI · {live_count}개 실행 중'
        if waiting: summary+=f' · {waiting} waiting'
        elif busy: summary+=f' · {busy} working'
        self.status_summary.update(summary)
    @on(Tree.NodeSelected,'#tree')
    def selected(self,event):
        data=event.node.data
        if not data:return
        kind,key,*extra=data
        obj=next((p for p in core.projects() if p['id']==key),None)
        if not obj:return
        if kind=='project' or (self.current_project() and desktop.enabled(self.current_project())):
            self.open_project(key)
            return
        try:
            sess=core.create_session(obj)
            if kind=='agent':
                agent=extra[0]
                # Persistent pane options survive shell title changes.
                r=core.tmux('list-panes','-t',sess,'-F','#{pane_id}|#{@tmw_agent}')
                for line in r.stdout.splitlines():
                    pane,_,title=line.partition('|')
                    if title.lower()==agent:
                        core.tmux_checked('select-pane','-t',pane)
                        break
                core.mark_seen(key,agent)
            core.tmux_checked('switch-client','-t',sess)
        except Exception as e: self.notify(str(e),severity='error')

if __name__=='__main__': Sidebar().run()
