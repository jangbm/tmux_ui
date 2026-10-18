#!/usr/bin/env python3
"""Headless idle/resize benchmark with synthetic screens; no operating-session writes."""
import asyncio
import json
from pathlib import Path
import runpy
import tempfile
import time
from unittest.mock import patch
import core
from desk_state import DeskState

Desktop=runpy.run_path(str(core.ROOT/'desktop-app.py'))['Desktop']

async def main():
    with tempfile.TemporaryDirectory(prefix='tmw-audit-') as tmp,patch.object(core,'CONFIG',Path(tmp)/'projects.json'),patch.object(core,'STATE',Path(tmp)/'state'):
        project=dict(id='audit',name='Audit',path=tmp,kind='tmux-live',source_session='audit',source_socket='/tmp/fake',source_agents={'claude':1,'codex':1},agents={})
        snap=dict(id='%1',pid='1',label='Synthetic AI',screen='● 합성 시험 응답\n❯ \x1b[2m다음 작업\x1b[0m',cursor=1,state='idle',detail='empty-prompt',suggestion='다음 작업',mode='',menu=False)
        core.atomic(core.CONFIG,[project]);state=DeskState();state.open(project['id'])
        with patch('session_input.targets',return_value=[snap]) as targets,patch('session_input.snapshot',return_value=snap) as snapshots,patch('session_input.send') as send,patch('session_input.control') as control:
            app=Desktop(project,state.value,publish=False)
            async with app.run_test(size=(160,45)) as pilot:
                await pilot.pause(.8)
                targets.reset_mock();snapshots.reset_mock()
                wall=time.monotonic();cpu=time.process_time()
                await asyncio.sleep(5)
                elapsed=time.monotonic()-wall;used=time.process_time()-cpu
                print(json.dumps(dict(wall_seconds=round(elapsed,3),python_cpu_seconds=round(used,3),one_core_percent=round(100*used/elapsed,1),target_queries=targets.call_count,snapshots=snapshots.call_count,visible_panels=2),ensure_ascii=False))
                for size in ((24,10),(80,24),(180,50),(40,15)):
                    await pilot.resize_terminal(*size);await pilot.pause(.1)
                assert app._exception is None
                send.assert_not_called();control.assert_not_called()
                assert snapshots.call_count<40,'Polling runaway'
                print('PASS: idle polling bounded; tiny/large resize stable; no AI input.')

if __name__=='__main__': asyncio.run(main())
