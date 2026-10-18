#!/usr/bin/env python3
"""Claude/Codex chat composer, replacing shell prompts in the preview workspace."""
import asyncio
import sys
import os
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static, TextArea, Button
import core
from chat_backend import Conversation


class Composer(TextArea):
    BINDINGS=[Binding('enter','send','보내기',priority=True),Binding('shift+enter','newline','줄바꿈',priority=True)]
    def action_send(self): self.app.send_message()
    def action_newline(self): self.insert('\n')


class Chat(App):
    CSS='''
    Screen { background: #181818; color: #d6d6d6; }
    #header { height: 1; padding: 0 1; background: #252b26; color: #b7cdb9; }
    #conversation { height: 1fr; scrollbar-size: 1 1; padding: 0 1; }
    #messages { height: auto; }
    #compose { height: 5; padding: 0 1; }
    #message { width: 1fr; height: 5; border: round #596b5e; background: #222723; color: #eeeeee; }
    #message:focus { border: round #a3bea8; }
    #compose-actions { width: 3; height: 5; margin-left: 1; align-vertical: middle; }
    #send, #stop { width: 3; min-width: 3; height: 1; padding: 0; border: none; background: #91ab98; color: #17231b; text-style: none; }
    #send { margin-bottom: 1; }
    #send:hover { background: #bdcebf; }
    #stop { background: #252a26; color: #b4bcb5; }
    #stop:hover { background: #3a302d; color: #e2b6a6; }
    #send:disabled, #stop:disabled { background: #202420; color: #59635b; }
    #hint { height: 1; padding: 0 1; color: #a0a0a0; }
    Screen.compact #compose, Screen.compact #message { height: 3; }
    Screen.compact #compose-actions { height: 3; }
    Screen.tiny #hint, Screen.tiny #header { display: none; }
    '''
    def __init__(self,project,agent,conversation=None):
        super().__init__(); self.workspace=project; self.project=project; self.agent=agent; self.drafts={}
        self.conversation=conversation or Conversation(project,agent)
        self.reply=''; self.error=''; self.busy=False
    def compose(self)->ComposeResult:
        yield Static(self.agent.title()+' · '+self.project['name']+' · 채팅',id='header',markup=False)
        with VerticalScroll(id='conversation'):
            yield Static('',id='messages')
        with Horizontal(id='compose'):
            yield Composer('',id='message',soft_wrap=True,show_line_numbers=False,placeholder='메시지를 입력하세요…')
            with Vertical(id='compose-actions'):
                yield Button('↑',id='send',tooltip='보내기 · Enter')
                yield Button('■',id='stop',disabled=True,tooltip='응답 중지')
        yield Static('Enter 보내기 · Shift+Enter 줄바꿈',id='hint')
    def on_mount(self):
        self.sync_context()
        self.set_interval(.7,self.sync_context)
        self.paint(); self.query_one('#message').focus()
    def sync_context(self):
        selected=core.chat_project(self.workspace)
        if selected['id']==self.project['id'] or self.busy: return
        composer=self.query_one('#message',Composer)
        self.drafts[self.project['id']]=composer.text
        self.project=selected
        self.conversation=Conversation(selected,self.agent)
        composer.load_text(self.drafts.get(selected['id'],''))
        self.reply=''; self.error=''
        self.query_one('#header',Static).update(self.agent.title()+' · '+selected['name']+' · 채팅')
        self.paint()
    def on_resize(self,event):
        self.screen.set_class(event.size.height<12,'compact')
        self.screen.set_class(event.size.height<7,'tiny')
    def report_busy(self,value):
        pane=os.environ.get('TMUX_PANE')
        if pane: core.tmux('set-option','-p','-t',pane,'@tmw_chat_busy','1' if value else '0')
    def paint(self):
        text=Text()
        for message in self.conversation.messages:
            text.append(('나' if message['role']=='user' else self.agent.title())+'\n',style='bold #b7cdb9' if message['role']=='user' else 'bold #a6bfd8')
            text.append(message['text']+'\n\n',style='#dedede')
        if not self.conversation.messages: text.append('어떤 작업을 도와드릴까요?\n메시지를 입력하면 대화를 시작합니다.',style='#9aab9e')
        if self.busy:
            text.append(self.agent.title()+' · 답변 중…\n',style='#a6bfd8')
            text.append(self.reply)
        if self.error: text.append('\n'+self.error,style='#dc9999')
        self.query_one('#messages',Static).update(text)
        self.call_after_refresh(self.query_one('#conversation').scroll_end,animate=False)
    @on(Button.Pressed,'#send')
    def pressed_send(self): self.send_message()
    def send_message(self):
        if self.busy: return
        composer=self.query_one('#message',Composer)
        message=composer.text.strip()
        if not message: return
        self.report_busy(True)
        self.busy=True; self.reply=''; self.error=''; composer.load_text('')
        self.query_one('#send',Button).disabled=True
        self.query_one('#stop',Button).disabled=False
        self.paint(); self.run_turn(message)
    def progress(self,text): self.reply=text; self.paint()
    @work(exclusive=True,group='chat')
    async def run_turn(self,message):
        try:
            core.set_status(self.project['id'],self.agent,'busy','chat-response')
            await self.conversation.send(message,self.progress)
            core.set_status(self.project['id'],self.agent,'done','chat-response')
        except asyncio.CancelledError:
            self.error='응답을 중지했습니다.'
            core.set_status(self.project['id'],self.agent,'idle','chat-stopped')
        except (OSError,RuntimeError,ValueError) as error:
            self.error=str(error)
            core.set_status(self.project['id'],self.agent,'error',self.error[:150])
        finally:
            self.report_busy(False)
            self.busy=False; self.reply=''
            self.query_one('#send',Button).disabled=False; self.query_one('#stop',Button).disabled=True
            self.paint()
    @on(Button.Pressed,'#stop')
    def stop(self):
        self.conversation.stop()
        self.workers.cancel_group(self,'chat')
    def on_unmount(self): self.conversation.stop()


if __name__=='__main__':
    project=next((p for p in core.projects() if p['id']==sys.argv[1]),None)
    if project: Chat(project,sys.argv[2]).run()
