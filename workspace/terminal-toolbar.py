#!/usr/bin/env python3
"""Compact terminal toolbar, separate from shell input and resize borders."""
import os
import shlex
import sys
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static, Button
from textual import on
import core
import layout


class TerminalToolbar(App):
    CSS='''
    Screen { background: #282828; color: #c8c8c8; }
    Horizontal { height: 1; }
    #label { width: 1fr; height: 1; padding-left: 1; }
    Button { min-width: 3; width: 3; height: 1; padding: 0; border: none; background: #282828; color: #d6d6d6; }
    Button:hover { background: #414141; color: #ffffff; }
    Button:focus { background: #353a36; }
    '''

    def __init__(self,project):
        super().__init__()
        self.project=project

    def compose(self)->ComposeResult:
        with Horizontal():
            yield Static('TERMINAL',id='label')
            yield Button('+',id='new',tooltip='New terminal')
            yield Button('▾',id='profiles',tooltip='Select shell profile')
            yield Button('×',id='close',tooltip='Hide terminal; keep shell running')

    def kind(self):
        return core.tmux_checked('show-options','-qv','-t',core.session_id(self.project['id']),
                                 '@tmw_default_shell') or 'bash'

    @on(Button.Pressed,'#new')
    def new_terminal(self):
        self.perform(new=True)

    @on(Button.Pressed,'#close')
    def close_terminal(self):
        self.perform(hide=True)

    def perform(self,**options):
        try:
            layout.show_terminal(self.project,kind=self.kind(),**options)
        except (OSError,ValueError,RuntimeError) as error:
            core.tmux('display-message',str(error))

    @on(Button.Pressed,'#profiles')
    def profiles(self):
        session=core.session_id(self.project['id'])
        try:
            clients=core.tmux_checked('list-clients','-t',session,'-F','#{client_activity}|#{client_name}').splitlines()
            if not clients: return
            client=max(clients,key=lambda row:int(row.partition('|')[0])).partition('|')[2]
            menu=[]
            for shell,(label,_) in layout.SHELLS.items():
                command=shlex.join(['env',f'TMW_SOCKET={core.SOCKET}',f'TMW_CONFIG={core.CONFIG}',
                    f'TMW_STATE={core.STATE}',sys.executable,str(core.ROOT/'terminal-control.py'),
                    session,'--new','--kind',shell])
                menu.extend([label,shell[0],'run-shell -b '+shlex.quote(command)])
            core.tmux_checked('display-menu','-c',client,'-t',os.environ['TMUX_PANE'],
                              '-T','New terminal','-x','R','-y','P',*menu)
        except (OSError,ValueError,RuntimeError) as error:
            core.tmux('display-message',str(error))


if __name__=='__main__':
    key=sys.argv[1] if len(sys.argv)>1 else os.environ.get('TMW_PROJECT')
    project=next((p for p in core.projects() if p['id']==key),None)
    if project: TerminalToolbar(project).run()
