#!/usr/bin/env python3
"""Draggable editor tabs above the code area, independent of workspace docking."""
import sys
from textual.app import App, ComposeResult
from textual.containers import Horizontal, HorizontalScroll
from textual.widgets import Static, Button
from textual import on
import core
import layout
import editor_tabs


class EditorTab(Static):
    def __init__(self,pane):
        super().__init__(pane['name'],markup=False,classes='editor-tab')
        self.pane_id=pane['id']
    def on_mouse_down(self,event):
        if event.button!=1: return
        self.origin=(event.screen_x,event.screen_y)
        self.capture_mouse(); event.stop()
    def on_mouse_up(self,event):
        if not hasattr(self,'origin'): return
        self.release_mouse(); event.stop()
        origin=self.origin; del self.origin
        position=(event.screen_x,event.screen_y)
        if position==origin:
            self.app.perform('select',self.pane_id)
            return
        for key,direction in [('split-right','right'),('split-below','below')]:
            if self.app.query_one('#'+key).region.contains(*position):
                self.app.perform('split',self.pane_id,direction)
                return
        for tab in self.app.query(EditorTab):
            if tab.region.contains(*position):
                self.app.perform('reorder',self.pane_id,tab.pane_id)
                return


class EditorTabs(App):
    CSS='''
    Screen { background: #252525; color: #d6d6d6; }
    #bar { height: 3; }
    #tabs { height: 3; width: 1fr; scrollbar-size: 1 1; }
    .editor-tab { width: auto; min-width: 10; height: 3; padding: 0 1; margin-right: 1; content-align: center middle; background: #252525; border: round #4b514d; border-bottom: none; }
    .editor-tab.selected { background: #303a32; border: round #a3bea8; border-bottom: none; color: #edf4ef; }
    .editor-tab:hover { background: #353a36; }
    Button { height: 3; width: 8; min-width: 8; border: none; padding: 0; background: #303530; color: #d6d6d6; content-align: center middle; }
    Button:hover { background: #465448; }
    Screen.compact Button { width: 5; min-width: 5; }
    '''
    def __init__(self,project):
        super().__init__(); self.project=project; self.signature=None; self.selected=None
    def compose(self)->ComposeResult:
        with Horizontal(id='bar'):
            yield HorizontalScroll(id='tabs')
            yield Button('↔ 옆',id='split-right',tooltip='Click to split selected tab, or drag a tab here')
            yield Button('↕ 아래',id='split-below',tooltip='Click to split selected tab below, or drag a tab here')
            yield Button('× 닫기',id='close',tooltip='Close selected tab; preserve editor contents')
    def on_mount(self):
        self.refresh_tabs()
        self.set_interval(.6,self.refresh_tabs)
    def on_resize(self,event):
        compact=event.size.width<60
        self.screen.set_class(compact,'compact')
        for key,label in [('split-right','↔ 옆'),('split-below','↕ 아래'),('close','× 닫기')]:
            self.query_one('#'+key,Button).label=label[0] if compact else label
    def refresh_tabs(self):
        try:
            session=core.session_id(self.project['id'])
            if core.tmux_checked('show-options','-qv','-t',session,'@tmw_layout_busy')=='1': return
            panes=editor_tabs.ordered(self.project)
            selected=core.tmux_checked('show-options','-qv','-t',session,'@tmw_selected_tab')
            active=core.tmux_checked('display-message','-p','-t',session,'#{pane_id}')
            if active in {p['id'] for p in panes}:
                if selected!=active:
                    core.tmux_checked('set-option','-t',session,'@tmw_selected_tab',active)
                    current=next(p for p in panes if p['id']==active)
                    core.tmux_checked('set-option','-t',session,'@tmw_chat_project',current.get('project') or self.project['id'])
                selected=active
            previous_selected=self.selected
            self.selected=selected if selected in {p['id'] for p in panes} else next((p['id'] for p in panes if p['primary']),None)
            signature=tuple((p['id'],p['name']) for p in panes)
            if signature!=self.signature:
                self.signature=signature
                container=self.query_one('#tabs',HorizontalScroll)
                container.remove_children()
                container.mount(*(EditorTab(p) for p in panes))
            for tab in self.query(EditorTab): tab.set_class(tab.pane_id==self.selected,'selected')
            self.call_after_refresh(self.paint_selection)
            if self.selected!=previous_selected: self.call_after_refresh(self.reveal_selected)
        except (OSError,RuntimeError,ValueError): pass
    def paint_selection(self):
        for tab in self.query(EditorTab): tab.set_class(tab.pane_id==self.selected,'selected')
    def reveal_selected(self):
        tab=next((tab for tab in self.query(EditorTab) if tab.pane_id==self.selected),None)
        if tab: tab.scroll_visible(animate=False)
    def perform(self,action,*args):
        try:
            getattr(editor_tabs,action)(self.project,*args)
            self.refresh_tabs()
        except (OSError,RuntimeError,ValueError) as error:
            core.tmux('display-message',str(error))
    @on(Button.Pressed)
    def pressed(self,event):
        if not self.selected: return
        if event.button.id=='close': self.perform('close',self.selected)
        else: self.perform('split',self.selected,'right' if event.button.id=='split-right' else 'below')


if __name__=='__main__':
    project=next((p for p in core.projects() if p['id']==sys.argv[1]),None)
    if project: EditorTabs(project).run()
