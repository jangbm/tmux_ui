#!/usr/bin/env python3
"""Register two editable demos without overwriting existing project files."""
from pathlib import Path
import argparse
import shutil
import core


def setup(start=False):
    for key,name,entry in [('demo-web','Demo Web','index.html'),
                           ('demo-python','Demo Python','main.py')]:
        existing=next((p for p in core.projects() if p['id']==key),None)
        if existing:
            project=existing
        else:
            destination=core.ROOT/'data'/key
            if destination.exists():
                raise ValueError(f'Unregistered folder already exists: {destination}')
            shutil.copytree(core.ROOT/'examples'/key,destination)
            project=core.add(name,destination,key=key,mode='import',claude=False,codex=False)
            def set_entry(records):
                next(p for p in records if p['id']==key)['entry']=entry
            core.locked_update(core.CONFIG,set_entry)
            project['entry']=entry
        if start: core.create_session(project)
        print(f"{project['name']}: {project['path']}")


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--start',action='store_true')
    setup(parser.parse_args().start)
