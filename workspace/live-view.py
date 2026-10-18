#!/usr/bin/env python3
"""Mirror a running tmux screen without attaching a client or sending input."""
import asyncio
import os
import sys
import subprocess
from rich.text import Text
from terminal_render import chat_terminal_text
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static, Select
import core
import live_tmux


class LiveView(App):
    CSS='''
    Screen { background: #181818; color: #d6d6d6; }
    #title { height: 1; padding: 0 1; background: #303a32; color: #dce7de; }
    #pane { height: 3; margin: 0; }
    #screen { height: 1fr; scrollbar-size: 1 1; }
    #output { width: auto; min-width: 100%; height: auto; padding: 0 1; }
    #help { height: 1; padding: 0 1; color: #a0a0a0; background: #202020; }
    '''
    def __init__(self,project):
        os.environ.pop('NO_COLOR',None)
        super().__init__(); self.project=project; self.pane=project.get('source_pane'); self.last=None
    def compose(self)->ComposeResult:
        yield Static('LIVE · '+self.project['source_session']+' · 보기 전용',id='title',markup=False)
        yield Select([],prompt='실행 중인 창 / 패널 선택',id='pane')
        with VerticalScroll(id='screen'):
            yield Static('실행 중인 화면을 연결하고 있습니다…',id='output',markup=False)
        yield Static('실시간 화면 · 원래 세션에 키 입력을 보내지 않습니다',id='help')
    def on_mount(self):
        self.refresh_source()
        self.set_interval(1.5,self.refresh_source)
        self.set_interval(8,self.refresh_panes)
    @work(exclusive=True,group='source')
    async def refresh_source(self):
        try:
            if not self.last: await self.load_panes()
            output=await asyncio.to_thread(live_tmux.capture,self.project['source_socket'],self.pane)
            if output!=self.last:
                self.last=output
                self.query_one('#output',Static).update(chat_terminal_text(output.rstrip('\n')))
        except (OSError,RuntimeError,ValueError,subprocess.TimeoutExpired) as error:
            self.query_one('#output',Static).update('화면을 읽을 수 없습니다.\n'+str(error))
    async def load_panes(self):
        items=await asyncio.to_thread(live_tmux.source_panes,self.project['source_socket'],self.project['source_session'])
        if not items: raise ValueError('실행 중인 패널이 없습니다')
        select=self.query_one('#pane',Select)
        if self.pane not in {p['id'] for p in items}: self.pane=next((p['id'] for p in items if p['active']),items[0]['id'])
        select.set_options([(f"{p['window']} {p['name']} · {p['command']} {p['id']}",p['id']) for p in items])
        select.value=self.pane
    @work(exclusive=True,group='panes')
    async def refresh_panes(self):
        try: await self.load_panes()
        except (OSError,RuntimeError,ValueError,subprocess.TimeoutExpired): pass
    @on(Select.Changed,'#pane')
    def choose(self,event):
        if isinstance(event.value,str) and event.value!=self.pane:
            self.pane=event.value; self.last=None; self.refresh_source()


if __name__=='__main__':
    project=next((p for p in core.projects() if p['id']==sys.argv[1]),None)
    if project and project.get('kind')=='tmux-live': LiveView(project).run()
