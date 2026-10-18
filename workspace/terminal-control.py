#!/usr/bin/env python3
"""Entry point for tmux terminal shortcut bindings."""
import argparse
import core
import layout


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('session')
    parser.add_argument('--new',action='store_true')
    parser.add_argument('--hide',action='store_true')
    parser.add_argument('--kind',choices=layout.SHELLS)
    args=parser.parse_args()
    project=next((p for p in core.projects() if core.session_id(p['id'])==args.session),None)
    if not project: return
    try:
        kind=args.kind or core.tmux_checked('show-options','-qv','-t',args.session,'@tmw_default_shell') or 'bash'
        layout.show_terminal(project,kind=kind,new=args.new,hide=args.hide,toggle=not(args.new or args.hide))
    except (ValueError,RuntimeError,OSError) as error:
        core.tmux('display-message',str(error))


if __name__=='__main__': main()
