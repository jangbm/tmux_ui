#!/usr/bin/env python3
"""Exercise input routing against fake CLIs on a disposable tmux server only."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time
import core
import session_input

SOCKET='tmux-ui-input-test'
def tmux(*args):
    return subprocess.run(['tmux','-L',SOCKET,*args],text=True,capture_output=True,check=True).stdout.strip()
if subprocess.run(['tmux','-L',SOCKET,'list-sessions'],capture_output=True).returncode==0:
    raise SystemExit('Test socket already exists; refusing to reuse it')
FAKE=r'''
import os,sys,tty,json
from pathlib import Path
tty.setraw(0)
path=Path(sys.argv[1]); messages=[]; mode='Auto'; incoming=b''; draft=b''; paste=False; menu=False; selected=0
path.write_text('[]')
def draw():
    if menu:
        text='\x1b[2J\x1b[HSelect model\r\n'+('❯ 1. Alpha\r\n  2. Beta' if selected==0 else '  1. Alpha\r\n❯ 2. Beta')+'\r\nEnter to select · Esc to cancel\x1b['+str(selected+2)+';1H'
        os.write(1,text.encode());return
    text='\x1b[?2004h\x1b[2J\x1b[H'+''.join('USER: '+m+'\r\n● ACK: '+m+'\r\n' for m in messages)
    text+='❯ \x1b[2mSuggested next step\x1b[22m\r\n'+mode.lower()+' mode on'
    text+='\x1b[1A\r\x1b[2C'
    os.write(1,text.encode())
draw()
while True:
    incoming+=os.read(0,4096)
    while incoming:
        if incoming.startswith(b'\x1b[200~'): paste=True; incoming=incoming[6:]; continue
        if incoming.startswith(b'\x1b[201~'): paste=False; incoming=incoming[6:]; continue
        if incoming.startswith(b'\x1b[Z'):
            mode='Plan' if mode=='Auto' else 'Auto';incoming=incoming[3:];draw();continue
        if incoming[:3] in (b'\x1b[B',b'\x1bOB'):
            selected=1;incoming=incoming[3:];draw();continue
        if incoming.startswith(b'\x1b') and len(incoming)<6: break
        c=incoming[:1];incoming=incoming[1:]
        if c==b'\r' and not paste:
            if menu:
                messages.append('MODEL:'+('Alpha' if selected==0 else 'Beta'));menu=False
            else:
                message=draft.decode();messages.append(message);menu=message=='/model'
                if message=='/exit': sys.exit(0)
            draft=b'';path.write_text(json.dumps(messages));draw()
        else: draft+=c
'''
with tempfile.TemporaryDirectory(prefix='tmw-source-check-') as temp:
    root=Path(temp);core.STATE=root/'state'
    fake=root/'fake.py'; fake.write_text(FAKE)
    try:
        for name in ('video','other'):
            command='exec -a claude '+shlex.join([sys.executable,'-u',str(fake),str(root/(name+'.json'))])
            tmux('new-session','-d','-s',name,'-x','100','-y','30','bash -c '+shlex.quote(command))
        socket=tmux('display-message','-p','-t','video','#{socket_path}')
        project=dict(kind='tmux-live',source_socket=socket,source_session='video')
        deadline=time.monotonic()+5
        while True:
            try:
                snap=session_input.snapshot(project,'claude')
                if snap['state']=='idle': break
            except (ValueError,RuntimeError): pass
            if time.monotonic()>deadline: raise AssertionError('Fake CLI did not become ready')
            time.sleep(.05)
        assert snap['suggestion']=='Suggested next step'
        message='안녕\nsecond line $(literal)'
        session_input.send(project,'claude',snap['id'],snap['pid'],message)
        deadline=time.monotonic()+3
        while json.loads((root/'video.json').read_text())!=[message]:
            if time.monotonic()>deadline: raise AssertionError('Message missing from target: '+(root/'video.json').read_text())
            time.sleep(.05)
        assert json.loads((root/'other.json').read_text())==[]
        screen=session_input.snapshot(project,'claude',snap['id'])
        assert '● ACK: 안녕' in screen['screen']
        session_input.control(project,'claude',snap['id'],snap['pid'],'mode')
        time.sleep(.15)
        assert session_input.snapshot(project,'claude',snap['id'])['mode']=='Plan'
        assert json.loads((root/'video.json').read_text())==[message]
        session_input.send(project,'claude',snap['id'],snap['pid'],'/model')
        time.sleep(.1)
        assert session_input.snapshot(project,'claude',snap['id'])['menu']
        session_input.control(project,'claude',snap['id'],snap['pid'],'Down')
        session_input.control(project,'claude',snap['id'],snap['pid'],'Enter')
        time.sleep(.1)
        assert json.loads((root/'video.json').read_text())==[message,'/model','MODEL:Beta']
        assert json.loads((root/'other.json').read_text())==[]
        assert session_input.shutdown(project,'claude',snap['id'],snap['pid'])
        assert tmux('display-message','-p','-t',snap['id'],'#{pane_dead}')=='1'
        assert tmux('has-session','-t','=video')==''
        assert json.loads((root/'other.json').read_text())==[]
        print('PASS: Korean multiline paste reaches only video; literal text preserved; response visible in tmux; suggestion extracted; Shift+Tab switches to Plan without sending another message; /model menu opens and Down/Enter selects Beta.')
        print('PASS: graceful AI exit retains original pane/session; other AI remains running.')
    finally:
        subprocess.run(['tmux','-L',SOCKET,'kill-server'],capture_output=True)
