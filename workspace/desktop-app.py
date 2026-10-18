#!/usr/bin/env python3
"""Grouped project tabs and integrated conversations in a single tmux editor pane."""
import asyncio
import os
import json
import sys
import subprocess
import time
import shutil
from pathlib import Path
from rich.text import Text
from rich.cells import cell_len
from terminal_render import chat_terminal_text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.containers import Horizontal, HorizontalScroll, Vertical, VerticalScroll
from textual.widgets import Static, Button, TextArea, Markdown, Select, Input
from message_queue import MessageQueue
from open_tabs import OpenTabs
from chat_backend import Conversation
from desk_state import DeskState
import core
import live_tmux
import session_input


class Composer(TextArea):
    def on_resize(self,event):
        self.call_after_refresh(self.app.sync_ime_cursor)

    BINDINGS=[Binding('enter','send','보내기',priority=True),Binding('shift+enter','newline','줄바꿈',priority=True),Binding('tab','suggestion','추천 입력',priority=True),Binding('shift+tab','mode','Claude 모드',priority=True),*[Binding(key,f"menu_key('{key}')",show=False,priority=True) for key in ('up','down','left','right','escape')]]
    def action_send(self):
        panel=self.parent.parent
        if panel.is_live and panel.source_menu and not self.text.strip(): panel.run_control('Enter')
        else: panel.send_message()
    def action_menu_key(self,key):
        panel=self.parent.parent
        if panel.is_live and panel.source_menu: panel.run_control(key.title())
        elif key!='escape': getattr(self,'action_cursor_'+key)()
    def action_newline(self): self.insert('\n')
    def action_suggestion(self):
        panel=self.parent.parent
        if not self.text and panel.suggestion:
            self.insert(panel.suggestion)
        else: self.app.screen.focus_next()
    def action_mode(self):
        panel=self.parent.parent
        if panel.is_live and panel.agent=='claude': panel.run_control('mode')
        else: self.app.screen.focus_previous()


class Thread(VerticalScroll):
    BINDINGS=[Binding(key,f"menu_key('{key}')",show=False,priority=True) for key in ('up','down','left','right','enter','escape')]
    following=True
    def check_action(self,action,parameters):
        if action=='menu_key': return self.parent.is_live and self.parent.source_menu
        return True
    def action_menu_key(self,key): self.parent.run_control(key.title())
    def on_mouse_down(self,event):
        if event.button==1: self.focus(scroll_visible=False)
    def on_mouse_up(self,event):
        if event.button==1: self.call_after_refresh(self.copy_selection)
    def copy_selection(self):
        text=self.screen.get_selected_text()
        if text:
            self.parent.last_selection=text
            self.app.copy_to_clipboard(text)
    def watch_virtual_size(self,old,new):
        if self.following: self.call_after_refresh(self.scroll_end,animate=False)
    def watch_scroll_y(self,old,new):
        super().watch_scroll_y(old,new)
        if new>=self.max_scroll_y-1: self.following=True
        elif new<old: self.following=False
        if self.parent.is_mounted:
            self.parent.query_one('.jump-latest').display=not self.following


class MessageCard(Vertical):
    def __init__(self,message,agent):
        super().__init__(classes='message-card '+('user-message' if message['role']=='user' else 'assistant-message'))
        self.message=message; self.agent=agent
    def compose(self)->ComposeResult:
        user=self.message['role']=='user'
        yield Static('나' if user else self.agent.title(),classes='message-role')
        if user: yield Static(self.message['text'],classes='message-body',markup=False)
        else: yield Markdown(self.message['text'],classes='message-body')


class ShutdownConfirm(ModalScreen):
    DEFAULT_CSS='''
    ShutdownConfirm { align: center middle; background: #00000099; }
    ShutdownConfirm > Vertical { width: 58; height: auto; padding: 1 2; border: round #b97864; background: #242424; }
    ShutdownConfirm Horizontal { height: 3; align-horizontal: right; margin-top: 1; }
    ShutdownConfirm Button { min-width: 10; margin-left: 1; }
    '''
    BINDINGS=[Binding('escape','cancel',show=False)]
    def __init__(self,label): super().__init__(); self.label=label
    def compose(self):
        with Vertical():
            yield Static(self.label+' 종료',markup=False)
            yield Static('선택한 AI를 종료합니다. 연결된 하위 작업도 끝날 수 있습니다. tmux 창은 유지됩니다.')
            with Horizontal():
                yield Button('취소',id='cancel-shutdown')
                yield Button('AI 종료',id='confirm-shutdown',variant='error')
    def on_mount(self): self.query_one('#cancel-shutdown').focus()
    def action_cancel(self): self.dismiss(False)
    @on(Button.Pressed)
    def button(self,event):
        event.stop(); self.dismiss(event.button.id=='confirm-shutdown')


class TabActions(ModalScreen):
    DEFAULT_CSS='''
    TabActions { align: center middle; background: #00000070; }
    TabActions > Vertical { width: 34; height: auto; padding: 1; background: #24272c; border: round #596471; }
    TabActions Button { width: 1fr; height: 1; border: none; margin: 0 0 1 0; background: #2d3239; }
    '''
    BINDINGS=[Binding('escape','cancel',show=False)]
    def __init__(self,pinned): super().__init__();self.pinned=pinned
    def compose(self):
        with Vertical():
            for key,label in [('pin','고정 해제' if self.pinned else '탭 고정'),('right','오른쪽으로 분할'),('below','아래로 분할'),('move','다른 그룹으로 이동'),('others','다른 탭 닫기 (고정 탭 유지)'),('close','이 탭 닫기')]:
                yield Button(label,name=key)
    def action_cancel(self): self.dismiss(None)
    @on(Button.Pressed)
    def choose(self,event): event.stop();self.dismiss(event.button.name)


class ChatPanel(Vertical):
    def __init__(self,project,agent,tab_id):
        super().__init__(classes='chat-panel')
        self.project=project; self.agent=agent; self.tab_id=tab_id
        self.conversation=Conversation(project,agent)
        self.busy=False; self.reply=''; self.error=''; self.source=''; self.source_pane=None
        self.is_live=project.get('kind')=='tmux-live'
        self.source_pid=None; self.suggestion=''; self.target_options=None; self.source_menu=False
        self.current_source={};self.queue=MessageQueue();self.search_term='';self.last_selection=''
        self.rendered_messages=None
        self.history_signature=None; self.draft_timer=None; self.control_lock=asyncio.Lock()
        self.draft_path=core.STATE/'desk-drafts'/f"{project['id']}-{agent}-{tab_id}.json"
    def compose(self)->ComposeResult:
        with Horizontal(classes='chat-heading'):
            yield Static(('◉  ' if self.agent=='claude' else '◇  ')+self.agent.title(),classes='agent-name '+self.agent)
            yield Static('tmux 연결 중…' if self.is_live else '새 대화',classes='chat-status')
            yield Button('⧉',classes='copy-selection',tooltip='선택한 글 복사 · Ctrl+C')
            if self.is_live and self.agent=='claude':
                yield Button('모드',classes='mode-toggle',tooltip='Shift+Tab · 기존 Claude 모드 전환')
            if self.is_live: yield Button('⏻',classes='shutdown-ai',tooltip='선택한 AI 종료')
            yield Button('×',classes='close-chat',tooltip='이 대화창 닫기')
        yield Input(placeholder='현재 화면에서 찾기 · Esc 닫기',classes='thread-search')
        if self.is_live:
            yield Select([],prompt='연결할 AI 창 선택',classes='source-target')
        with Thread(classes='thread'):
            yield Static('',classes='source-message',markup=False)
            yield Vertical(classes='messages')
            yield Static('',classes='pending-reply',markup=False)
            yield Static('',classes='chat-error',markup=False)
        yield Button('↓ 최신 내용',classes='jump-latest')
        if self.is_live:
            with Horizontal(classes='menu-controls'):
                for label,key in [('↑','Up'),('↓','Down'),('←','Left'),('→','Right'),('선택','Enter'),('취소','Escape')]:
                    yield Button(label,name=key,classes='menu-key',tooltip=key+' · 현재 tmux 선택 메뉴')
            with Horizontal(classes='queue-bar'):
                yield Static('',classes='queue-summary',markup=False)
                yield Button('▶',classes='queue-toggle',tooltip='대기열 시작 / 일시정지')
                yield Button('수정',classes='queue-edit',tooltip='첫 메시지를 입력창으로 가져오기')
                yield Button('×',classes='queue-cancel',tooltip='첫 대기 메시지 취소')
        with Horizontal(classes='composer-box'):
            yield Composer('',classes='composer',placeholder=self.agent.title()+'에게 메시지 보내기…',show_line_numbers=False,soft_wrap=True)
            with Vertical(classes='composer-actions'):
                yield Button('↑',classes='send',tooltip='현재 tmux 세션에 보내기 · Enter' if self.is_live else '보내기 · Enter')
                yield Button('■',classes='stop',tooltip='응답 중지',disabled=True)
        yield Static(('Enter 전송 · Tab 추천 · ⇧Tab 모드' if self.agent=='claude' else 'Enter 전송 · Tab 추천') if self.is_live else 'Enter 전송 · Shift+Enter 줄바꿈',classes='composer-hint')
    def on_mount(self):
        try:
            saved=json.loads(self.draft_path.read_text())
            self.query_one('.composer',Composer).load_text(saved.get('text',''))
            self.queue=MessageQueue(saved.get('queue',[]))
        except (OSError,ValueError): pass
        self.query_one('.thread-search').display=False
        self.query_one('.jump-latest').display=False
        self.render_queue()
        if self.is_live: self.query_one('.source-target').display=False
        self.query_one('.source-message').display=False
        self.render_messages()
        self.refresh_source()
        self.set_interval(.5,self.refresh_source)
        self.set_interval(1,self.sync_history)
    def on_unmount(self):
        if self.draft_timer: self.draft_timer.stop()
        self.save_draft()
        self.conversation.stop()
    @on(TextArea.Changed)
    def draft_changed(self,event):
        event.stop()
        self.size_composer()
        if self.draft_timer: self.draft_timer.stop()
        self.draft_timer=self.set_timer(.4,self.save_draft)
    def save_draft(self):
        composer=next(iter(self.query('.composer')),None)
        if composer: core.atomic(self.draft_path,{'text':composer.text,'queue':self.queue.items})
    def on_resize(self,event):
        self.set_class(event.size.height<14,'compact-chat')
        self.set_class(event.size.width<38,'narrow-chat')
        for button in self.query('.menu-key'):
            if button.name in ('Enter','Escape'):
                button.label=({'Enter':'↵','Escape':'×'} if event.size.width<40 else {'Enter':'선택','Escape':'취소'})[button.name]
        if list(self.query('.composer')): self.size_composer()
    def size_composer(self):
        composer=self.query_one('.composer',Composer)
        width=max(10,composer.content_size.width)
        lines=min(4,max(1,sum(max(1,(cell_len(line)+width-1)//width) for line in composer.text.split('\n'))))
        self.set_class(lines==1,'single-line')
        composer.styles.height=lines
        self.query_one('.composer-box').styles.height=lines+2
    def latest(self):
        thread=self.query_one('.thread',Thread)
        thread.following=True
        self.query_one('.jump-latest').display=False
        self.call_after_refresh(thread.scroll_end,animate=False)
    def render_queue(self):
        if not self.is_live: return
        self.query_one('.queue-bar').display=bool(self.queue.items)
        if self.queue.items:
            first=self.queue.items[0]['text'].replace('\n',' ')
            self.query_one('.queue-summary',Static).update(f"대기 {len(self.queue.items)} · "+('자동' if self.queue.armed else '일시정지')+' · '+first[:50])
        self.query_one('.queue-toggle',Button).label='Ⅱ' if self.queue.armed else '▶'
    def queue_message(self):
        composer=self.query_one('.composer',Composer);message=composer.text.strip()
        if not message or not self.source_pane or not self.source_pid: return
        was_empty=not self.queue.items
        self.queue.add(message,self.source_pane,self.source_pid)
        if was_empty and self.current_source.get('state')=='busy':
            self.queue.armed=True;self.queue.saw_busy=True
        composer.load_text('');self.save_draft();self.render_queue()
        self.app.notify('응답이 끝난 뒤 보낼 대기열에 추가했습니다.',timeout=2)
    def edit_queued(self):
        if not self.queue.items or self.busy: return
        composer=self.query_one('.composer',Composer)
        if composer.text.strip():
            self.app.notify('현재 초안을 먼저 보내거나 비워 주세요.',timeout=3);return
        self.queue.pause();composer.load_text(self.queue.items.pop(0)['text'])
        composer.focus();self.save_draft();self.render_queue()
    def render_source_text(self):
        text=chat_terminal_text(self.source.rstrip())
        if self.search_term: text.highlight_words([self.search_term],style='bold black on #d9bd72',case_sensitive=False)
        self.query_one('.source-message',Static).update(text)
    @on(Input.Changed,'.thread-search')
    def search_changed(self,event):
        event.stop();self.search_term=event.value
        if self.is_live: self.render_source_text()
    def on_key(self,event):
        if event.key=='escape' and self.query_one('.thread-search').has_focus:
            event.stop();self.query_one('.thread-search').display=False
            self.search_term='';self.render_source_text();self.query_one('.thread').focus()
    def sync_history(self):
        if self.busy or self.is_live: return
        try:
            stamp=self.conversation.path.stat().st_mtime_ns
            if stamp!=self.history_signature:
                self.history_signature=stamp
                stored=Conversation(self.project,self.agent)
                self.conversation.messages=stored.messages; self.conversation.session=stored.session
                self.render_messages()
        except OSError: pass
    def render_messages(self):
        if self.is_live:
            self.query_one('.messages').display=False
            self.query_one('.pending-reply').display=False
            error=self.query_one('.chat-error',Static)
            error.display=bool(self.error); error.update(self.error)
            return
        signature=tuple((m['role'],m['text']) for m in self.conversation.messages)
        if signature!=self.rendered_messages:
            self.rendered_messages=signature
            box=self.query_one('.messages',Vertical)
            box.remove_children()
            if signature: box.mount(*(MessageCard(m,self.agent) for m in self.conversation.messages))
            elif not self.source:
                box.mount(Static('무엇을 도와드릴까요?',classes='welcome-title'),
                          Static(self.project['name']+' 프로젝트의 '+self.agent.title()+' 대화입니다.',classes='welcome-note',markup=False))
        reply=self.query_one('.pending-reply',Static)
        reply.display=self.busy
        if self.busy: reply.update(Text(self.agent.title()+' · 답변 중\n'+(self.reply or '생각하고 있습니다…'),style='#b8c9df'))
        error=self.query_one('.chat-error',Static); error.display=bool(self.error)
        error.update(self.error)
        self.latest()
    @on(Select.Changed,'.source-target')
    def target_changed(self,event):
        event.stop()
        if event.value is Select.BLANK: return
        if self.source_pane and self.source_pane!=str(event.value):
            self.queue.pause();self.render_queue()
        self.source_pane=str(event.value); self.source_pid=None; self.suggestion=''
        self.refresh_source()
    @work(exclusive=True,group='source')
    async def refresh_source(self):
        if not self.is_live or (not self.is_on_screen and not self.queue.armed): return
        try:
            options=await asyncio.to_thread(session_input.targets,self.project,self.agent)
            if self.source_pane and not any(p['id']==self.source_pane for p in options) and len(options)==1:
                self.queue.pause();self.source_pane=options[0]['id'];self.source_pid=None
            choices=tuple((p['label'],p['id']) for p in options)
            selector=self.query_one('.source-target',Select)
            if choices!=self.target_options:
                self.target_options=choices; selector.set_options(list(choices))
                selector.display=len(options)>1 or bool(self.source_pane and not any(p['id']==self.source_pane for p in options))
                if self.source_pane and any(p['id']==self.source_pane for p in options): selector.value=self.source_pane
            if not self.source_pane and len(options)==1: self.source_pane=options[0]['id']
            current=await asyncio.to_thread(session_input.snapshot,self.project,self.agent,self.source_pane,None,options)
            self.current_source=current
            self.source_pane=current['id']; self.source_pid=current['pid']
            self.source_menu=current.get('menu',False)
            self.query_one('.menu-controls').display=self.source_menu
            hint=('승인·선택 대기 · ↑↓ 이동 · Enter 선택 · Esc 취소' if self.source_menu else
                '작업 중 · Enter로 다음 메시지 대기열에 추가' if current['state']=='busy' else
                '원본 입력 남음 · 원본에서 전송하거나 지워 주세요' if current.get('detail')=='draft' else
                '질문·확인 대기 · 원본 안내를 처리해 주세요' if current['state']=='waiting' else
                '연결·준비 상태 확인 중 · 초안은 보관됩니다' if current['state']!='idle' else
                '준비 · Enter 전송 · Tab 추천'+(' · ⇧Tab 모드' if self.agent=='claude' else ''))
            self.query_one('.composer-hint',Static).update(hint)
            self.set_class(current['state']=='busy','source-busy')
            self.set_class(current['state']=='waiting','source-waiting')
            self.suggestion=current['suggestion']
            self.query_one('.composer',Composer).placeholder=self.suggestion or self.agent.title()+'에게 메시지 보내기…'
            state={'busy':'작업 중','idle':'준비','waiting':'입력 대기','unknown':'상태 확인 중','error':'확인 필요'}.get(current['state'],'연결됨')
            label=self.project['source_session']+' · '+state+(' · '+current['mode'] if current['mode'] else '')
            self.query_one('.chat-status',Static).update(label)
            self.query_one('.send',Button).disabled=self.busy or current['state'] not in ('idle','busy')
            self.query_one('.send',Button).label='+' if current['state']=='busy' else '↑'
            self.query_one('.send',Button).tooltip='다음 메시지 대기열에 추가' if current['state']=='busy' else '현재 tmux 세션에 보내기 · Enter'
            self.query_one('.stop',Button).disabled=self.busy or current['state']!='busy'
            if self.agent=='claude': self.query_one('.mode-toggle',Button).disabled=self.busy or current['state']!='idle'
            output=current['screen']
            # Keep the selected text stable while dragging/copying a live reply.
            selecting=self.screen._selecting or self.query_one('.source-message') in self.screen.selections
            if output!=self.source and not selecting:
                self.source=output
                self.query_one('.source-message').display=bool(output.strip())
                thread=self.query_one('.thread',VerticalScroll)
                follow=thread.scroll_y>=thread.max_scroll_y-2 or not thread.max_scroll_y
                self.render_source_text()
                if follow: self.latest()
                else:
                    self.query_one('.jump-latest',Button).label='↓ 새 내용 · 최신으로'
                    self.query_one('.jump-latest').display=True
            if not self.busy and self.queue.ready(current):
                self.busy=True;self.queue.saw_busy=False
                self.send_to_source(self.queue.items[0]['text'],queued=True)
            self.render_queue()
        except (OSError,ValueError,RuntimeError,asyncio.TimeoutError,subprocess.TimeoutExpired) as error:
            self.current_source={};self.queue.pause();self.render_queue()
            self.source_menu=False; self.query_one('.menu-controls').display=False
            self.source=''; self.source_pid=None
            self.query_one('.source-message',Static).update('')
            self.query_one('.source-message').display=False
            self.suggestion=''; self.query_one('.composer',Composer).placeholder='연결할 AI 창을 확인해 주세요'
            self.query_one('.chat-status',Static).update(str(error))
            self.query_one('.send',Button).disabled=True
            self.query_one('.stop',Button).disabled=True

    def stop_response(self):
        self.queue.pause();self.render_queue()
        if self.is_live: self.run_control('stop')
        else: self.conversation.stop(); self.workers.cancel_group(self,'turn')
    def confirm_shutdown(self):
        if self.busy or not self.source_pane or not self.source_pid: return
        self.queue.pause();self.render_queue()
        pane,pid=self.source_pane,self.source_pid
        label=f"{self.project['source_session']} · {self.agent.title()} · {pane}"
        self.app.push_screen(ShutdownConfirm(label),lambda confirmed:self.shutdown_ai(pane,pid) if confirmed else None)
    @work(exclusive=True,group='live-shutdown')
    async def shutdown_ai(self,pane,pid):
        if self.busy: return
        self.busy=True
        try:
            async with self.control_lock:
                stopped=await asyncio.to_thread(session_input.shutdown,self.project,self.agent,pane,pid)
            self.app.notify(self.agent.title()+(' 종료를 확인했습니다.' if stopped else ' 종료를 요청했습니다. 원본 화면을 확인해 주세요.'))
            await asyncio.to_thread(live_tmux.refresh_connections,force=True)
            self.app.update_projects()
        except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as error:
            self.error=str(error); self.render_messages()
        finally: self.busy=False; self.refresh_source()
    @work(group='live-control')
    async def run_control(self,action):
        if not self.is_live or self.busy: return
        try:
            if not self.source_pane or not self.source_pid: raise ValueError('먼저 AI 창을 연결해 주세요.')
            async with self.control_lock:
                await asyncio.to_thread(session_input.control,self.project,self.agent,self.source_pane,self.source_pid,action)
            self.error=''
            await asyncio.sleep(.15); self.refresh_source()
        except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as error: self.error=str(error)
        self.render_messages()
    @work(exclusive=True,group='live-send')
    async def send_to_source(self,message,queued=False):
        composer=self.query_one('.composer',Composer)
        try:
            if not self.source_pane or not self.source_pid: raise ValueError('먼저 AI 창을 연결해 주세요.')
            pane,pid=self.source_pane,self.source_pid
            if queued:
                item=self.queue.items[0];pane,pid=item['pane'],item['pid']
                item['attempted']=True;self.save_draft()
            await asyncio.to_thread(session_input.send,self.project,self.agent,pane,pid,message)
            if queued: self.queue.items.pop(0)
            elif composer.text.strip()==message: composer.load_text('')
            self.save_draft();self.render_queue()
            self.app.notify(self.project['source_session']+' · '+self.agent.title()+'에 전송했습니다',timeout=2)
            self.error=''
            self.latest()
        except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as error:
            self.error=str(error)
            if queued:
                self.queue.pause();self.save_draft();self.render_queue()
        finally:
            self.busy=False; self.render_messages(); self.refresh_source()

    @on(Button.Pressed)
    def button(self,event):
        event.stop()
        if event.button.has_class('close-chat'): self.app.hide_chat(self.tab_id,self.agent)
        elif event.button.has_class('shutdown-ai'): self.confirm_shutdown()
        elif event.button.has_class('send'): self.send_message()
        elif event.button.has_class('stop'): self.stop_response()
        elif event.button.has_class('mode-toggle'): self.run_control('mode')
        elif event.button.has_class('menu-key'): self.run_control(event.button.name)
        elif event.button.has_class('jump-latest'): self.screen.clear_selection();self.latest();self.refresh_source()
        elif event.button.has_class('copy-selection'):
            selection=self.screen.get_selected_text() or self.last_selection
            if selection: self.app.copy_to_clipboard(selection)
            else: self.app.notify('내용창에서 복사할 글을 드래그해 주세요.',timeout=2)
        elif event.button.has_class('queue-edit'): self.edit_queued()
        elif event.button.has_class('queue-cancel'):
            if self.queue.items and not self.busy:
                self.queue.items.pop(0);self.save_draft();self.render_queue()
        elif event.button.has_class('queue-toggle'):
            if self.busy: return
            try:
                if self.queue.armed: self.queue.pause()
                else: self.queue.resume(self.current_source)
                self.render_queue()
            except ValueError as error: self.error=str(error);self.render_messages()
    def send_message(self):
        if self.busy: return
        if self.is_live and self.current_source.get('state')=='busy':
            self.queue_message();return
        if self.is_live and self.source_menu:
            self.error='선택 메뉴가 열려 있습니다. 선택/취소 버튼으로 먼저 닫아 주세요. 작성 중인 입력은 보관됩니다.'
            self.render_messages(); return
        composer=self.query_one('.composer',Composer)
        message=composer.text.strip()
        if not message: return
        if self.is_live:
            self.busy=True; self.error=''
            self.query_one('.send',Button).disabled=True
            self.send_to_source(message)
            return
        composer.load_text(''); self.busy=True; self.reply=''; self.error=''
        self.query_one('.send',Button).disabled=True; self.query_one('.stop',Button).disabled=False
        self.render_messages(); self.run_turn(message)
    def progress(self,text): self.reply=text; self.render_messages()
    @work(exclusive=True,group='turn')
    async def run_turn(self,message):
        try:
            core.set_status(self.project['id'],self.agent,'busy','project-chat')
            request=asyncio.create_task(self.conversation.send(message,self.progress))
            await asyncio.sleep(0)
            self.render_messages()
            await request
            core.set_status(self.project['id'],self.agent,'done','project-chat')
        except asyncio.CancelledError:
            if 'request' in locals(): request.cancel(); await asyncio.gather(request,return_exceptions=True)
            self.error='응답을 중지했습니다.'
        except (OSError,ValueError,RuntimeError) as error:
            self.error=str(error)
        finally:
            self.busy=False; self.reply=''
            self.query_one('.send',Button).disabled=False; self.query_one('.stop',Button).disabled=True
            self.render_messages()


class AgentGrip(Static):
    def on_mouse_down(self,event):
        self.capture_mouse(); event.stop()
    def on_mouse_move(self,event):
        if self.app.mouse_captured is self:
            view=self.parent
            extent=view.size.height if view.has_class('stacked') else view.size.width
            offset=event.screen_y-view.region.y if view.has_class('stacked') else event.screen_x-view.region.x
            view.ratio=max(.2,min(.8,offset/max(1,extent))); view.size_panels()
    def on_mouse_up(self,event): self.release_mouse(); event.stop()


class ProjectView(Horizontal):
    def __init__(self,project,entry):
        super().__init__(classes='project-view')
        self.project=project; self.entry=entry; self.ratio=.5; self.panels={}
        available=project.get('source_agents',{}) if project.get('kind')=='tmux-live' else project.get('agents',{})
        self.agents=[a for a in core.AGENTS if available.get(a)]
    def compose(self)->ComposeResult:
        for index,agent in enumerate(self.agents):
            if index: yield AgentGrip('',classes='agent-grip')
            panel=ChatPanel(self.project,agent,self.entry['id']); self.panels[agent]=panel; yield panel
        with Vertical(classes='empty-project'):
            yield Static('◇',classes='empty-symbol')
            yield Static(self.project['name'],classes='empty-title',markup=False)
            yield Static('대화창이 닫혀 있습니다.' if self.agents else '실행 중인 AI가 없습니다. 원본 세션에서 AI를 시작하면 자동 연결됩니다.',classes='empty-note')
            with Horizontal(classes='restore-buttons'):
                for agent in self.agents: yield Button(agent.title()+' 열기',name=agent,classes='restore-chat')
    def on_mount(self): self.size_panels()
    def sync_project(self,project):
        self.project=project
        available=project.get('source_agents',{}) if project.get('kind')=='tmux-live' else project.get('agents',{})
        agents=[a for a in core.AGENTS if available.get(a)]
        if agents==self.agents: return
        self.agents=agents
        empty=self.query_one('.empty-project')
        for agent in agents:
            if agent not in self.panels:
                if self.panels and not list(self.query(AgentGrip)): self.mount(AgentGrip('',classes='agent-grip'),before=empty)
                panel=ChatPanel(project,agent,self.entry['id']); self.panels[agent]=panel; self.mount(panel,before=empty)
        buttons=self.query_one('.restore-buttons')
        buttons.remove_children(); buttons.mount(*(Button(a.title()+' 열기',name=a,classes='restore-chat') for a in agents))
        self.query_one('.empty-note',Static).update('대화창이 닫혀 있습니다.' if agents else '실행 중인 AI가 없습니다. 원본 세션에서 AI를 시작하면 자동 연결됩니다.')
        self.call_after_refresh(self.size_panels)
    def on_resize(self,event):
        self.set_class(event.size.width<64,'stacked'); self.size_panels()
    def size_panels(self):
        visible=[a for a in self.agents if a not in self.entry.get('hidden',[])]
        for agent,panel in self.panels.items(): panel.display=agent in visible
        self.query_one('.empty-project').display=not visible
        for grip in self.query(AgentGrip): grip.display=len(visible)>1
        if len(visible)==1:
            panel=self.panels[visible[0]]; panel.styles.width='1fr'; panel.styles.height='1fr'
        elif len(visible)==2:
            stacked=self.has_class('stacked'); extent=(self.size.height if stacked else self.size.width)-1
            first=max(1,int(extent*self.ratio)); second=max(1,extent-first)
            for agent,size in zip(visible,[first,second]):
                self.panels[agent].styles.width='1fr' if stacked else size
                self.panels[agent].styles.height=size if stacked else '1fr'
    def latest(self):
        for panel in self.panels.values():
            if panel.display: panel.latest()
    @on(Button.Pressed,'.restore-chat')
    def restore(self,event):
        event.stop(); self.app.show_chat(self.entry['id'],event.button.name)


class TabLabel(Static):
    def on_mouse_down(self,event):
        if event.button!=1: return
        self.origin=(event.screen_x,event.screen_y); self.dragged=False; self.capture_mouse(); event.stop()
    def on_mouse_move(self,event):
        if self.app.mouse_captured is not self or not hasattr(self,'origin'): return
        if abs(event.screen_x-self.origin[0])+abs(event.screen_y-self.origin[1])>1:
            self.dragged=True; self.parent.add_class('dragging'); self.app.preview_drop(event.screen_x,event.screen_y)
    def on_mouse_up(self,event):
        if not hasattr(self,'origin'): return
        self.release_mouse(); event.stop()
        tab=self.parent
        if self.dragged: self.app.drop_tab(tab.tab_id,event.screen_x,event.screen_y)
        else: self.app.select_tab(tab.tab_id)
        tab.remove_class('dragging')
        del self.origin; self.app.clear_drop()


class TabChip(Horizontal):
    def __init__(self,entry,project,active):
        super().__init__(classes='tab-chip'+(' selected' if active else '')+(' pinned' if entry.get('pinned') else ''))
        self.tooltip=project['name']+' · 탭 우클릭으로 고정·이동·닫기'
        self.tab_id=entry['id']
        self.project=project
        self.pinned=entry.get('pinned',False)
    def compose(self)->ComposeResult:
        pending=any(s.get('pending') for s in self.project.get('source_states',{}).values())
        yield TabLabel(Text(('◆ ' if self.pinned else '')+self.project['name']+(' ●' if pending else ''),no_wrap=True,overflow='ellipsis'),classes='tab-label',markup=False)
        yield Button('×',classes='close-tab',tooltip='탭 닫기')
    def on_mount(self):
        if self.has_class('selected'): self.call_after_refresh(self.scroll_visible,animate=False)
    @on(Button.Pressed,'.close-tab')
    def close(self,event): event.stop(); self.app.close_tab(self.tab_id)
    def on_mouse_down(self,event):
        if event.button==3: event.stop();self.app.tab_menu(self.tab_id)


class EditorGroup(Vertical):
    def __init__(self,group):
        super().__init__(classes='editor-group'); self.group_id=group['id']; self.signature=None
    def compose(self)->ComposeResult:
        with Horizontal(classes='group-header'):
            yield HorizontalScroll(classes='group-tabs')
            yield Button('◉',classes='restore-agents',tooltip='닫은 대화창 다시 열기')
            yield Button('◫',classes='split-right',tooltip='편집 그룹을 오른쪽으로 분할')
            yield Button('⊟',classes='split-below',tooltip='편집 그룹을 아래로 분할')
            yield Button('⌄',classes='open-tabs',tooltip='열린 탭 목록 · Ctrl+P')
            yield Button('⋯',classes='tab-actions',tooltip='탭 메뉴 · 탭 우클릭')
        yield Static('',classes='group-body')
    def on_mount(self):
        self.rebuild(self.app.state.group(self.group_id))
        self.call_after_refresh(self.app.finish_render)
    def on_resize(self,event):
        self.set_class(event.size.width<48,'narrow-group')
        self.call_after_refresh(self.reveal_selected)
    def reveal_selected(self):
        selected=next(iter(self.query('.tab-chip.selected')),None)
        if selected: selected.scroll_visible(animate=False)
    def rebuild(self,group):
        if not list(self.query('.group-tabs')): return
        signature=(group['active'],tuple((t['id'],t['project'],t.get('pinned',False),any(s.get('pending') for s in self.app.projects.get(t['project'],{}).get('source_states',{}).values())) for t in group['tabs']))
        if signature==self.signature: return
        self.signature=signature
        strip=self.query_one('.group-tabs',HorizontalScroll)
        strip.remove_children()
        strip.mount(*(TabChip(t,self.app.projects[t['project']],t['id']==group['active']) for t in group['tabs'] if t['project'] in self.app.projects))
    @on(Button.Pressed)
    def button(self,event):
        event.stop()
        group=self.app.state.group(self.group_id)
        if event.button.has_class('open-tabs'):
            self.app.action_open_tabs();return
        if not group['active']: return
        if event.button.has_class('tab-actions'):
            self.app.tab_menu(group['active']);return
        if event.button.has_class('restore-agents'):
            _,tab=self.app.state.locate(group['active'])
            tab['hidden']=[]
            self.app.views[tab['id']].size_panels(); self.app.persist()
        else: self.app.split_tab(group['active'],'below' if event.button.has_class('split-below') else 'right',copy=True)


class GroupGrip(Static):
    def on_mouse_down(self,event): self.capture_mouse(); event.stop()
    def on_mouse_move(self,event):
        if self.app.mouse_captured is not self: return
        stage=self.parent; stacked=self.app.state.value['axis']=='below'
        offset=event.screen_y-stage.region.y if stacked else event.screen_x-stage.region.x
        total=stage.size.height if stacked else stage.size.width
        self.app.state.value['ratio']=max(.2,min(.8,offset/max(1,total))); self.app.place_groups()
    def on_mouse_up(self,event):
        self.release_mouse(); event.stop(); self.app.persist()


class Stage(Vertical):
    def on_resize(self,event):
        # App resize arrives before the stage has its new content dimensions.
        self.call_after_refresh(self.app.place_groups)


class Desktop(App):
    CSS_PATH=core.ROOT/'desktop.tcss'
    BINDINGS=[Binding('ctrl+p','open_tabs','열린 탭',priority=True),Binding('ctrl+pageup','previous_tab','이전 탭',priority=True),
              Binding('ctrl+pagedown','next_tab','다음 탭',priority=True),
              Binding('ctrl+f','find_text','대화 찾기',priority=True),
              Binding('ctrl+c','stop_active','응답 중지',priority=True)]
    def __init__(self,workspace,state=None,publish=True):
        os.environ.pop('NO_COLOR',None)
        super().__init__(watch_css=publish); self.workspace=workspace; self.publish=publish
        self.path=core.STATE/f"desktop-{workspace['id']}.json"
        if state is None:
            try: state=json.loads(self.path.read_text())
            except (OSError,ValueError): state=None
        self.state=DeskState(state); self.projects={p['id']:p for p in core.projects()}
        self.focus_tab=None
        self.groups={}; self.views={}; self.closed={t['id']:t for t in self.state.value.get('closed',[])}; self.request_nonce=None; self.rectangles={}
    def compose(self)->ComposeResult:
        with Stage(id='stage'):
            yield GroupGrip('',id='group-grip')
            yield Static('',id='drop-preview')
    def _display(self,screen,renderable):
        # Textual 7.5 emits the terminal CUP during this call. Correcting the
        # property after refresh is too late until another frame is painted.
        self.sync_ime_cursor()
        super()._display(screen,renderable)
        if renderable is not None and self._driver and not self.is_headless and self._running and not self._closed and not self._batch_count:
            if isinstance(self.focused,Composer) and self.focused.region.width and self.focused.region.height:
                x,y=screen.outer_size.clamp_offset(self.focused.cursor_screen_offset)
                # Expose a native caret for terminal IMEs instead of only drawing a cell.
                self._driver.write(f'\x1b[{y+1};{x+1}H\x1b[6 q\x1b[?25h')
            else:
                self._driver.write('\x1b[0 q\x1b[?25l')
    def sync_ime_cursor(self):
        composer=self.focused
        if isinstance(composer,Composer) and composer.region.width and composer.region.height:
            self.cursor_position=composer.cursor_screen_offset
    @on(TextArea.SelectionChanged)
    def sync_input_cursor(self,event):
        self.call_after_refresh(self.sync_ime_cursor)
    def action_open_tabs(self):
        if len(self.screen_stack)>1: return
        rows=[dict(id=t['id'],name=self.projects.get(t['project'],{}).get('name',t['project']),group=i+1,pinned=t.get('pinned',False)) for i,g in enumerate(self.state.groups) for t in g['tabs']]
        self.push_screen(OpenTabs(rows,self.state.group()['active']),lambda tab:self.select_tab(tab) if tab and any(t['id']==tab for g in self.state.groups for t in g['tabs']) else None)
    def action_previous_tab(self): self.step_tab(-1)
    def action_next_tab(self): self.step_tab(1)
    def action_find_text(self):
        if len(self.screen_stack)>1: return
        focused=self.focused
        panel=next((p for p in focused.ancestors_with_self if isinstance(p,ChatPanel)),None) if focused else None
        if panel is None:
            view=self.views.get(self.state.group()['active'])
            panel=next((p for p in view.panels.values() if p.display),None) if view else None
        if panel and panel.is_live:
            search=panel.query_one('.thread-search',Input);search.display=True;search.focus()
    def tab_menu(self,tab_id):
        _,tab=self.state.locate(tab_id)
        self.push_screen(TabActions(tab.get('pinned',False)),lambda action:self.apply_tab_action(tab_id,action))
    def apply_tab_action(self,tab_id,action):
        if not action: return
        group,tab=self.state.locate(tab_id)
        if action=='pin':
            tab['pinned']=not tab.get('pinned',False)
            group['tabs'].sort(key=lambda t:not t.get('pinned',False));self.render_state()
        elif action in ('right','below'): self.split_tab(tab_id,action,copy=True)
        elif action=='move':
            other=next((g for g in self.state.groups if g['id']!=group['id']),None)
            if other: self.state.move(tab_id,other['id']);self.render_state()
            else: self.split_tab(tab_id,'right')
        elif action=='close': self.close_tab(tab_id)
        elif action=='others':
            for item in list(group['tabs']):
                if item['id']!=tab_id and not item.get('pinned'): self.closed[item['id']]=self.state.close(item['id'])
            self.render_state()
    def step_tab(self,offset):
        group=self.state.group()
        if group['tabs']:
            keys=[t['id'] for t in group['tabs']]
            index=keys.index(group['active']) if group['active'] in keys else 0
            self.select_tab(keys[(index+offset)%len(keys)])
    def action_stop_active(self):
        if isinstance(self.focused,TextArea) and self.focused.selected_text:
            self.copy_to_clipboard(self.focused.selected_text)
            return
        if len(self.screen_stack)>1: return
        selection=self.screen.get_selected_text()
        if selection:
            self.copy_to_clipboard(selection)
            return
        focused=self.focused
        if focused:
            panel=next((p for p in focused.ancestors if isinstance(p,ChatPanel)),None)
            if panel and (panel.busy or panel.is_live): panel.stop_response()
    def copy_to_clipboard(self,text):
        super().copy_to_clipboard(text)
        self.notify('선택한 글의 복사를 요청했습니다.',timeout=2)
        if shutil.which('clip.exe'): self.copy_windows(text)
    @work(exclusive=True,group='clipboard')
    async def copy_windows(self,text):
        try:
            result=await asyncio.to_thread(subprocess.run,['clip.exe'],input=text.encode('utf-16'),capture_output=True,timeout=3)
            # OSC52 above is the primary route through tmux. clip.exe is optional
            # because WSL interop may be unavailable in the UI process.
        except (OSError,subprocess.TimeoutExpired):
            pass
    def on_mount(self):
        self.render_state()
        self.set_interval(.25,self.poll_request)
        self.set_interval(2,self.update_projects)
    def on_resize(self,event): self.call_after_refresh(self.place_groups)
    def update_projects(self):
        self.projects={p['id']:p for p in core.projects()}
        for view in self.views.values():
            if view.project['id'] in self.projects: view.sync_project(self.projects[view.project['id']])
        for group in self.state.groups:
            if group['id'] in self.groups: self.groups[group['id']].rebuild(group)
    def persist(self):
        self.state.value['closed']=list(self.closed.values())
        core.atomic(self.path,self.state.value)
        if self.publish:
            group=self.state.group()
            if group['active']:
                _,tab=self.state.locate(group['active'])
                core.tmux('set-option','-t',core.session_id(self.workspace['id']),'@tmw_chat_project',tab['project'])
    def render_state(self):
        stage=self.screen_stack[0].query_one('#stage')
        for group_id,widget in list(self.groups.items()):
            if not any(g['id']==group_id for g in self.state.groups): widget.remove(); del self.groups[group_id]
        for group in self.state.groups:
            if group['id'] not in self.groups:
                widget=EditorGroup(group); self.groups[group['id']]=widget; stage.mount(widget)
            for tab in group['tabs']:
                if tab['id'] not in self.views and tab['project'] in self.projects:
                    view=ProjectView(self.projects[tab['project']],tab); self.views[tab['id']]=view; stage.mount(view)
        self.call_after_refresh(self.finish_render)
        self.persist()
    def finish_render(self):
        for group in self.state.groups:
            self.groups[group['id']].rebuild(group)
        active={g['active'] for g in self.state.groups}
        for tab_id,view in self.views.items(): view.display=tab_id in active
        self.place_groups()
        self.call_after_refresh(self.reveal_active)
        if self.focus_tab:
            view=self.views.get(self.focus_tab)
            self.focus_tab=None
            if view:
                panel=next((p for p in view.panels.values() if p.display),None)
                if panel: panel.query_one('.thread').focus(scroll_visible=False)
    def place_groups(self):
        if not self.is_mounted: return
        stage=self.screen_stack[0].query_one('#stage'); width,height=stage.size
        if width<1 or height<4: return
        groups=self.state.groups; stacked=self.state.value['axis']=='below'
        ratio=self.state.value.get('ratio',.5)
        rects=[(0,0,width,height)]
        grip=self.screen_stack[0].query_one('#group-grip'); grip.display=len(groups)==2
        if len(groups)==2:
            extent=(height if stacked else width)-1; first=max(4,min(extent-4,int(extent*ratio))); second=extent-first
            rects=[(0,0,width,first),(0,first+1,width,second)] if stacked else [(0,0,first,height),(first+1,0,second,height)]
            grip.styles.offset=(0,first) if stacked else (first,0)
            grip.styles.width=width if stacked else 1; grip.styles.height=1 if stacked else height
            grip.set_class(stacked,'horizontal-grip')
        self.rectangles={}
        for group,rect in zip(groups,rects):
            x,y,w,h=rect; widget=self.groups.get(group['id'])
            self.rectangles[group['id']]=rect
            if widget:
                widget.styles.offset=(x,y); widget.styles.width=w; widget.styles.height=h
                widget.set_class(group['id']==self.state.value['active_group'],'active-group')
            if group['active'] in self.views:
                view=self.views[group['active']]
                view.styles.offset=(x,y+3); view.styles.width=w; view.styles.height=max(1,h-3)
        self.call_after_refresh(self.sync_ime_cursor)
    def reveal_active(self):
        for group in self.state.groups:
            view=self.views.get(group['active'])
            if view and view.display: view.latest()
            widget=self.groups.get(group['id'])
            if widget:
                chip=next((t for t in widget.query(TabChip) if t.tab_id==group['active']),None)
                if chip: chip.scroll_visible(animate=False)
    def open_project(self,project_id,group=None):
        if project_id not in self.projects: return
        target=self.state.group(group)
        existing=next((t for t in target['tabs'] if t['project']==project_id),None)
        saved=next((entry for entry in self.closed.values() if entry['project']==project_id),None)
        if existing: self.state.select(existing['id'])
        elif saved:
            self.closed.pop(saved['id']); target['tabs'].append(saved); self.state.select(saved['id'])
        else: self.state.open(project_id,target['id'])
        self.focus_tab=target['active']
        self.render_state()
    def select_tab(self,tab_id):
        self.state.select(tab_id); self.focus_tab=tab_id; self.render_state()
    def close_tab(self,tab_id):
        self.closed[tab_id]=self.state.close(tab_id); self.render_state()
    def split_tab(self,tab_id,direction,copy=False):
        self.state.split(tab_id,direction,copy); self.render_state()
    def hide_chat(self,tab_id,agent):
        _,entry=self.state.locate(tab_id)
        if agent not in entry['hidden']: entry['hidden'].append(agent)
        self.views[tab_id].size_panels(); self.persist()
    def show_chat(self,tab_id,agent):
        _,entry=self.state.locate(tab_id)
        if agent in entry['hidden']: entry['hidden'].remove(agent)
        self.views[tab_id].size_panels(); self.persist(); self.views[tab_id].latest()
    def poll_request(self):
        if not self.publish: return
        try:
            raw=core.tmux('show-options','-qv','-t',core.session_id(self.workspace['id']),'@tmw_desktop_request').stdout.strip()
            if not raw: return
            request=json.loads(raw)
            if request.get('nonce')==self.request_nonce: return
            self.request_nonce=request.get('nonce')
            self.update_projects()
            if request['action']=='open': self.open_project(request['project'])
            elif request['action']=='split':
                self.open_project(request['project']); group=self.state.group()
                self.split_tab(group['active'],request.get('direction','right'),copy=False)
            elif request['action']=='agent_visibility':
                group=self.state.group()
                if group['active']:
                    _,tab=self.state.locate(group['active'])
                    if tab['project']==request['project']:
                        tab['hidden']=[a for a in core.AGENTS if not request.get('enabled',{}).get(a)]
                        self.views[tab['id']].size_panels(); self.persist()
            elif request['action']=='close_group':
                group=self.state.group()
                for tab in list(group['tabs']): self.close_tab(tab['id'])
        except (OSError,ValueError,RuntimeError,KeyError): pass
    def hit_group(self,x,y):
        stage=self.screen_stack[0].query_one('#stage'); x-=stage.region.x; y-=stage.region.y
        for key,(gx,gy,w,h) in self.rectangles.items():
            if gx<=x<gx+w and gy<=y<gy+h: return key,x-gx,y-gy,w,h
        return None
    def drop_target(self,x,y):
        hit=self.hit_group(x,y)
        if not hit: return None
        key,lx,ly,w,h=hit
        if ly<3:
            for chip in self.groups[key].query(TabChip):
                if chip.region.contains(x,y): return key,'tab',chip.tab_id,x>chip.region.center[0]
            return key,'tab',None,False
        if lx<w*.23: edge='left'
        elif lx>w*.77: edge='right'
        elif ly<3+(h-3)*.22: edge='above'
        elif ly>h-(h-3)*.22: edge='below'
        else: edge='center'
        return key,edge,None,False
    def preview_drop(self,x,y):
        target=self.drop_target(x,y); overlay=self.screen_stack[0].query_one('#drop-preview')
        if not target or target[1]=='tab': overlay.display=False; return
        key,edge,_,_=target; gx,gy,w,h=self.rectangles[key]; gy+=3; h-=3
        if edge=='left': w=max(1,w//2)
        elif edge=='right': gx+=w//2; w=max(1,w-w//2)
        elif edge=='above': h=max(1,h//2)
        elif edge=='below': gy+=h//2; h=max(1,h-h//2)
        overlay.styles.offset=(gx,gy); overlay.styles.width=w; overlay.styles.height=h; overlay.display=True
    def clear_drop(self): self.screen_stack[0].query_one('#drop-preview').display=False
    def drop_tab(self,tab_id,x,y):
        target=self.drop_target(x,y)
        if not target: return
        key,edge,before,after=target
        if edge=='tab': self.state.move(tab_id,key,before,after)
        elif edge=='center' or len(self.state.groups)==2: self.state.move(tab_id,key)
        else: self.state.split(tab_id,edge)
        self.render_state()


if __name__=='__main__':
    workspace=next((p for p in core.projects() if p['id']==sys.argv[1]),None)
    if workspace: Desktop(workspace).run()
