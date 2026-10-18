"""Sidebar-only actions and restoration; never manage source processes."""
from rich.text import Text
from textual import on
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, Button, OptionList
from textual.widgets.option_list import Option

class ProjectMenu(ModalScreen):
    DEFAULT_CSS='''
    ProjectMenu { align: center middle; background: #00000070; padding: 1; }
    ProjectMenu > Vertical { width: 42; max-width: 100%; height: auto; padding: 1; background: #24272c; border: round #78a9d1; }
    ProjectMenu Static { height: auto; margin-bottom: 1; }
    ProjectMenu Button { width: 1fr; min-width: 1; height: 3; border: none; }
    '''
    BINDINGS=[('escape','cancel','취소')]
    def __init__(self,name): super().__init__();self.project_name=name
    def compose(self):
        with Vertical():
            yield Static(self.project_name,markup=False)
            yield Button('사이드바에서 숨기기',id='hide-project',tooltip='사이드바에서만 숨기기 · 세션과 프로세스 유지')
            yield Button('대화창 설정',id='configure-project')
            yield Button('취소',id='cancel-project')
    def on_mount(self): self.compact_labels()
    def on_resize(self,event): self.compact_labels()
    def compact_labels(self):
        for button in self.query(Button):
            if button.id=='hide-project': button.label='숨기기' if self.size.width<32 else '사이드바에서 숨기기'
            elif button.id=='configure-project': button.label='대화창' if self.size.width<32 else '대화창 설정'
    def action_cancel(self): self.dismiss(None)
    @on(Button.Pressed)
    def choose(self,event): event.stop();self.dismiss(event.button.id)

class HiddenProjects(ModalScreen):
    DEFAULT_CSS='''
    HiddenProjects { align: center middle; background: #00000070; padding: 1; }
    HiddenProjects > Vertical { width: 64; max-width: 100%; height: 70%; background: #24272c; border: round #78a9d1; }
    HiddenProjects Static { height: auto; padding: 0 1; }
    HiddenProjects OptionList { height: 1fr; border: none; background: #24272c; }
    '''
    BINDINGS=[('escape','cancel','닫기')]
    def __init__(self,rules): super().__init__();self.rules=rules
    def compose(self):
        with Vertical():
            yield Static('숨긴 항목 · 선택하면 다시 표시')
            yield OptionList(*(Option(Text(item['name']+(' · '+item['socket'].rsplit('/',1)[-1] if item.get('socket') else ''),no_wrap=True,overflow='ellipsis'),id=key) for key,item in self.rules.items()))
            yield Static('↑↓ 이동 · Enter 복원 · Esc 닫기\n원본 세션이 없으면 재발견 후 표시됩니다.')
    def on_mount(self): self.query_one(OptionList).focus()
    def action_cancel(self): self.dismiss(None)
    @on(OptionList.OptionSelected)
    def restore(self,event): event.stop();self.dismiss(event.option.id)
