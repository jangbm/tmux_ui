#!/usr/bin/env python3
"""Add explicit Windows Terminal key sequences, backing up the original settings."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

ROOT=Path(__file__).resolve().parent
DEFAULT=Path('/mnt/c/Users/jang/AppData/Local/Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json')
BINDINGS=(('ctrl+`','Workspace.ToggleTerminal','\x1b[96;5u'),
          ('ctrl+shift+`','Workspace.NewTerminal','\x1b[96;6u'))


def proposed(original):
    settings=json.loads(original.decode('utf-8-sig'))
    for keys,identifier,sequence in BINDINGS:
        for binding in settings.get('keybindings',[]):
            bound=binding.get('keys',[])
            if isinstance(bound,str): bound=[bound]
            if keys in bound and binding.get('id')!=identifier:
                raise ValueError(f'{keys} already has a different binding')
        actions=settings.setdefault('actions',[])
        actions[:]=[a for a in actions if a.get('id')!=identifier]
        actions.append({'id':identifier,'name':identifier,'command':{'action':'sendInput','input':sequence}})
        bindings=settings.setdefault('keybindings',[])
        bindings[:]=[b for b in bindings if b.get('id')!=identifier]
        bindings.append({'id':identifier,'keys':keys})
    return (json.dumps(settings,ensure_ascii=False,indent=4)+'\n').encode('utf-8')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--settings',type=Path,default=DEFAULT)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    original=args.settings.read_bytes()
    updated=proposed(original)
    if not args.apply:
        print('Ready: add Ctrl+grave toggle and Ctrl+Shift+grave new-terminal bindings')
        return
    backup=ROOT/'data/backups'/('windows-terminal-'+hashlib.sha256(original).hexdigest()[:12]+'.json')
    backup.parent.mkdir(parents=True,exist_ok=True)
    if not backup.exists(): backup.write_bytes(original)
    if args.settings.read_bytes()!=original:
        raise RuntimeError('Settings changed; retry to preserve the latest version')
    descriptor,temporary=tempfile.mkstemp(prefix='.tmux-ui-',suffix='.json',dir=args.settings.parent)
    try:
        with os.fdopen(descriptor,'wb') as stream:
            stream.write(updated); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary,args.settings)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    print('Installed two shortcuts. Original settings backup:',backup)


if __name__=='__main__': main()
