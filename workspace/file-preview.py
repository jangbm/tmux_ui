#!/usr/bin/env python3
"""Read-only file viewer for an isolated tmux popup."""
import sys
from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import Static, TextArea
import core


class FilePreview(App):
    CSS='''
    Screen { background: #181818; color: #d6d6d6; }
    #title { height: 3; padding: 1 2; background: #202020; color: #b7cdb9; }
    TextArea { height: 1fr; border: none; background: #181818; }
    #help { height: 1; padding: 0 2; background: #202020; color: #a0a0a0; }
    '''
    BINDINGS=[('escape','quit','Close'),('ctrl+q','quit','Close')]

    def __init__(self,root,path):
        super().__init__()
        self.path=Path(path).resolve()
        self.root=Path(root).resolve()
        self.text=core.preview_text(self.root,self.path)

    def compose(self)->ComposeResult:
        yield Static(str(self.path.relative_to(self.root)),id='title',markup=False)
        yield TextArea(self.text,read_only=True,show_line_numbers=True,
                       show_cursor=False,soft_wrap=False,id='contents')
        yield Static('READ ONLY  ·  Esc Close  ·  Arrow keys Scroll',id='help')


if __name__=='__main__':
    try:
        FilePreview(sys.argv[1],sys.argv[2]).run()
    except (OSError,ValueError) as error:
        print(error,file=sys.stderr)
        sys.exit(1)
