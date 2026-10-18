#!/usr/bin/env python3
"""Verify application OSC52 reaches a real tmux client's PTY, never the user's clipboard."""
import base64
import fcntl
import os
from pathlib import Path
import pty
import select
import shlex
import struct
import subprocess
import sys
import tempfile
import termios
import time

with tempfile.TemporaryDirectory(prefix='tmw-clipboard-') as temp:
    root=Path(temp);socket=str(root/'tmux.sock')
    def tmux(*args,check=True):
        return subprocess.run(['tmux','-S',socket,*args],capture_output=True,check=check)
    master,slave=pty.openpty();client=None
    fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',24,100,0,0))
    payload=base64.b64encode('한글 복사\nsecond line'.encode())
    script=root/'emit.py'
    script.write_text('import os,time\nfrom pathlib import Path\np=Path('+repr(str(root/'trigger'))+')\nwhile True:\n if p.exists():\n  p.unlink();os.write(1,'+repr(b'\x1b]52;c;'+payload+b'\a')+')\n time.sleep(.02)\n')
    def collect(seconds):
        end=time.monotonic()+seconds;result=b''
        while time.monotonic()<end:
            if select.select([master],[],[],.05)[0]: result+=os.read(master,65536)
        return result
    try:
        tmux('-f',str(Path(__file__).with_name('preview.conf')),'new-session','-d','-s','copy',shlex.join([sys.executable,str(script)]))
        client=subprocess.Popen(['tmux','-S',socket,'attach-session','-t','copy'],stdin=slave,stdout=slave,stderr=slave,env={**os.environ,'TERM':'xterm-256color'})
        collect(.5)
        tmux('set-option','-s','set-clipboard','external')
        (root/'trigger').touch();assert payload not in collect(.3),'external unexpectedly forwarded application clipboard'
        tmux('source-file',str(Path(__file__).with_name('preview.conf')))
        assert tmux('show-options','-sv','set-clipboard').stdout.strip()==b'on'
        (root/'trigger').touch();output=collect(.5)
        assert b'\x1b]52;' in output and payload in output,'Clipboard sequence did not reach client PTY'
        assert tmux('show-buffer').stdout.decode()=='한글 복사\nsecond line'
        print('PASS: external blocks application copy; preview config forwards Korean multiline OSC52 through tmux to client PTY.')
    finally:
        tmux('kill-server',check=False)
        if client:
            client.wait(timeout=3)
        os.close(master);os.close(slave)
