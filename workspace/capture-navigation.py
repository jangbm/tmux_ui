#!/usr/bin/env python3
"""Synthetic navigation captures. Optional baseline source directory is read-only."""
import asyncio
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
from unittest.mock import patch
import core
from desk_state import DeskState

async def main():
    baseline=Path(sys.argv[1]) if len(sys.argv)>1 else None
    source=baseline or core.ROOT
    label='before' if baseline else 'after'
    Desktop=runpy.run_path(str(source/'desktop-app.py'))['Desktop']
    Sidebar=runpy.run_path(str(source/'sidebar.py'))['Sidebar']
    with tempfile.TemporaryDirectory(prefix='tmw-nav-capture-') as tmp,patch.object(core,'CONFIG',Path(tmp)/'projects.json'),patch.object(core,'STATE',Path(tmp)/'state'),patch('live_tmux.refresh_connections',return_value=False),patch('watcher.refresh',return_value=False),patch.object(core,'tmux',return_value=subprocess.CompletedProcess([],0,'','')),patch('session_input.send') as send,patch('session_input.control') as control:
        root=Path(tmp)/'sample-files'
        for name in ('src/ui/components','src/services/api','tests/unit','docs/guides'):
            (root/name).mkdir(parents=True);(root/name/'sample.txt').write_text('Synthetic example only')
        projects=[dict(id=f'sample-{i}',name=f'Sample project {i:02}',path=str(root),agents={'claude':False,'codex':False}) for i in range(14)]
        core.atomic(core.CONFIG,projects);state=DeskState()
        for project in projects: state.open(project['id'])
        state.groups[0]['tabs'][0]['pinned']=True
        app=Desktop(projects[0],state.value,publish=False)
        async with app.run_test(size=(80,25)) as pilot:
            await pilot.pause(.5)
            if not baseline: await pilot.press('ctrl+p');await pilot.pause()
            app.save_screenshot(f'navigation-{label}-tabs.svg',path=str(core.ROOT/'previews'))
        with patch.dict(os.environ,{'TMW_PROJECT':projects[0]['id']}),patch('core.chat_project',return_value=projects[0]):
            app=Sidebar()
            async with app.run_test(size=(42,30)) as pilot:
                app.query_one('#views').active='files-view';await pilot.pause(.5)
                tree=app.query_one('#files');tree.move_cursor(tree.root)
                if not baseline: await tree.expand_levels().wait();await pilot.pause()
                app.save_screenshot(f'navigation-{label}-files.svg',path=str(core.ROOT/'previews'))
        send.assert_not_called();control.assert_not_called()
        print('Synthetic navigation captures:',label)
if __name__=='__main__': asyncio.run(main())
