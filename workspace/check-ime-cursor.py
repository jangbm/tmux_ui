#!/usr/bin/env python3
"""Check focused input cursor at a real isolated tmux pane, without AI sessions."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time

with tempfile.TemporaryDirectory(prefix='tmw-ime-') as tmp:
    root=Path(tmp);socket=str(root/'tmux.sock');outer_socket=str(root/'terminal.sock');workspace=Path(__file__).resolve().parent
    def tmux(*args,check=True): return subprocess.run(['tmux','-S',socket,*args],capture_output=True,text=True,check=check).stdout.strip()
    def outer(*args,check=True): return subprocess.run(['tmux','-S',outer_socket,*args],capture_output=True,text=True,check=check).stdout.strip()
    script=root/'app.py'
    script.write_text('''import json,runpy,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import core
from desk_state import DeskState
root=Path(sys.argv[2]);core.CONFIG=root/'projects.json';core.STATE=root/'state'
project=dict(id='synthetic',name='Synthetic',path=str(root),agents={'claude':True,'codex':True})
core.atomic(core.CONFIG,[project]);state=DeskState();state.open(project['id'])
Desktop=runpy.run_path(str(core.ROOT/'desktop-app.py'))['Desktop']
class Demo(Desktop):
 def on_mount(self):
  super().on_mount();self.phase=-1;self.set_interval(.1,self.tick_demo)
 def tick_demo(self):
  try: phase=int((root/'phase').read_text())
  except (OSError,ValueError): return
  composers=list(self.query('.composer'))
  if len(composers)!=2: return
  if phase!=self.phase:
   self.phase=phase;self.target=composers[phase%2]
   self.target.focus();self.target.load_text('한글 입력' if phase%2 else '')
   # Exercise a nonfocused input update and a repaint in the same frame.
   composers[1-phase%2].load_text('Background draft')
   if phase==3: self.query_one('.thread').focus()
   self.refresh()
  self.call_after_refresh(self.report)
 def report(self):
  if not hasattr(self,'target'): return
  pos=self.target.cursor_screen_offset
  core.atomic(root/'expected.json',dict(phase=self.phase,x=pos.x,y=pos.y))
Demo(project,state.value,publish=False).run()
''')
    try:
        tmux('-f','/dev/null','new-session','-d','-s','ime','-x','120','-y','32','sleep 60')
        tmux('set-option','-g','status','off')
        pane=tmux('split-window','-h','-p','80','-t','ime','-P','-F','#{pane_id}',shlex.join([sys.executable,str(script),str(workspace),str(root)]))
        # A second disposable server acts as a terminal emulator for the real client.
        outer('-f','/dev/null','new-session','-d','-s','terminal','-x','120','-y','32',shlex.join(['env','-u','TMUX','tmux','-S',socket,'attach-session','-t','ime']))
        outer('set-option','-g','status','off')
        for phase,(width,height) in enumerate(((120,32),(90,25),(140,40),(120,32))):
            outer('resize-window','-t','terminal','-x',str(width),'-y',str(height))
            tmux('resize-window','-t','ime','-x',str(width),'-y',str(height));(root/'phase').write_text(str(phase))
            deadline=time.monotonic()+8;last=None
            while time.monotonic()<deadline:
                time.sleep(.1)
                try: expected=json.loads((root/'expected.json').read_text())
                except (OSError,ValueError): continue
                actual=tuple(map(int,tmux('display-message','-p','-t',pane,'#{cursor_x} #{cursor_y}').split()))
                offset=tuple(map(int,tmux('display-message','-p','-t',pane,'#{pane_left} #{pane_top}').split()))
                delivered=tuple(map(int,outer('display-message','-p','-t','terminal','#{cursor_x} #{cursor_y}').split()))
                visible=tmux('display-message','-p','-t',pane,'#{cursor_flag}')
                delivered_visible=outer('display-message','-p','-t','terminal','#{cursor_flag}')
                last=(expected,actual,delivered,offset,visible,delivered_visible)
                if phase==3 and expected['phase']==3 and visible=='0' and delivered_visible=='0': break
                if expected['phase']==phase and actual==(expected['x'],expected['y']) and delivered==(expected['x']+offset[0],expected['y']+offset[1]) and visible=='1' and delivered_visible=='1': break
            else: raise AssertionError(f'Input cursor did not reach tmux: {last}')
        print('PASS: real tmux cursor follows focused Korean input across panels, background draft updates and resize; native caret visible only during input; no AI input.')
    finally:
        tmux('kill-server',check=False)
        outer('kill-server',check=False)
