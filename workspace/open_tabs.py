"""Searchable, group-aware list of already open tabs; no session operations."""
from rich.text import Text
from textual import on
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

class OpenTabs(ModalScreen):
    DEFAULT_CSS='''
    OpenTabs { align: center top; background: #00000070; padding: 1; }
    OpenTabs > Vertical { width: 72; max-width: 100%; height: 80%; background: #24272c; border: round #78a9d1; }
    OpenTabs Input { height: 3; margin: 0; }
    OpenTabs OptionList { height: 1fr; background: #24272c; border: none; }
    OpenTabs Static { height: auto; padding: 0 1; color: #acb6c4; }
    '''
    BINDINGS=[Binding('escape','cancel',priority=True),Binding('up','move(-1)',priority=True),Binding('down','move(1)',priority=True),Binding('enter','choose',priority=True)]
    def __init__(self,rows,active):
        super().__init__(); self.rows=rows; self.active=active; self.matches=[]
    def compose(self):
        with Vertical():
            yield Static('열린 탭 · 그룹별 목록')
            yield Input(placeholder='프로젝트 이름으로 검색',id='tab-search')
            yield OptionList(id='open-tab-list')
            yield Static('',id='tab-list-help')
    def on_mount(self): self.filter(''); self.query_one(Input).focus()
    @on(Input.Changed)
    def changed(self,event): self.filter(event.value)
    def filter(self,query):
        self.matches=[row for row in self.rows if query.casefold().strip() in row['name'].casefold()]
        listing=self.query_one(OptionList);listing.clear_options()
        listing.add_options([Option(Text(('● ' if row['id']==self.active else '  ')+('◆ ' if row['pinned'] else '')+row['name']+f"  · 그룹 {row['group']}",no_wrap=True,overflow='ellipsis'),id=row['id']) for row in self.matches])
        listing.highlighted=next((i for i,r in enumerate(self.matches) if r['id']==self.active),0) if self.matches else None
        self.query_one('#tab-list-help',Static).update(f'{len(self.matches)}개 · ↑↓ 이동 · Enter 열기 · Esc 닫기' if self.matches else '일치하는 열린 탭이 없습니다.')
    def action_move(self,step):
        listing=self.query_one(OptionList)
        if self.matches: listing.highlighted=((listing.highlighted or 0)+step)%len(self.matches)
    def action_choose(self):
        index=self.query_one(OptionList).highlighted
        if index is not None and index<len(self.matches): self.dismiss(self.matches[index]['id'])
    @on(OptionList.OptionSelected)
    def clicked(self,event): event.stop();self.dismiss(event.option.id)
    def action_cancel(self): self.dismiss(None)
