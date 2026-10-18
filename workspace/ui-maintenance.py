#!/usr/bin/env python3
"""Explicit maintenance entry point shared by UI developers and control."""
import argparse
import json
import core
import desktop
import live_tmux


def main():
    parser=argparse.ArgumentParser(description='Inspect, discover projects, or reload the preview UI only.')
    parser.add_argument('action',choices=['status','discover','reload'])
    parser.add_argument('--workspace',default='myproject',help='Registered preview owner ID')
    args=parser.parse_args()
    if args.action=='discover':
        live_tmux.refresh_connections(force=True)
    elif args.action=='reload':
        owner=next((p for p in core.projects() if p['id']==args.workspace),None)
        if owner is None: raise SystemExit('Unknown workspace owner: '+args.workspace)
        print('Reloaded preview Desktop:',desktop.upgrade(owner))
        return
    for project in core.projects():
        if project.get('kind')=='tmux-live':
            print(json.dumps({key:project.get(key) for key in
                ('id','name','path','source_session','source_agents','source_agents_error')},ensure_ascii=False))


if __name__=='__main__': main()
