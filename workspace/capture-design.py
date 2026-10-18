#!/usr/bin/env python3
"""Synthetic-only design captures; never connects to an operating tmux server."""
import asyncio
from pathlib import Path
import runpy
import sys
import os
import subprocess
import tempfile
from unittest.mock import patch
import core
from desk_state import DeskState
Desktop=runpy.run_path(str(core.ROOT/'desktop-app.py'))['Desktop']

async def main():
    label=sys.argv[1] if len(sys.argv)>1 else 'after'
    if label not in ('before','after'): raise SystemExit('Use before or after')
    with tempfile.TemporaryDirectory(prefix='tmw-design-') as tmp,patch.object(core,'CONFIG',Path(tmp)/'projects.json'),patch.object(core,'STATE',Path(tmp)/'state'):
        projects=[dict(id=key,name=name,path=tmp,kind='tmux-live',source_session=key,source_socket='/tmp/synthetic-only',source_agents={'claude':1,'codex':1},agents={}) for key,name in [('sample','Sample workspace'),('long','긴 프로젝트 이름 디자인 검토'),('notes','Notes')]]
        core.atomic(core.CONFIG,projects); state=DeskState()
        for project in projects: state.open(project['id'])
        state.value['groups'][0]['tabs'][0]['pinned']=True
        snap=dict(id='%1',pid='1',label='Synthetic AI',screen='● 디자인 검토를 완료했습니다.\n\n  탭과 입력창의 간격을 확인해 주세요.\n  이 화면은 합성 예시이며 운영 대화가 아닙니다.\n\n❯ \x1b[2m다음 작업을 알려 주세요\x1b[0m',cursor=5,state='idle',detail='empty-prompt',suggestion='다음 작업을 알려 주세요',mode='Auto',menu=False)
        with patch('session_input.targets',return_value=[snap]),patch('session_input.snapshot',return_value=snap),patch('session_input.send') as send,patch('session_input.control') as control:
            app=Desktop(projects[0],state.value,publish=False)
            async with app.run_test(size=(120,32)) as pilot:
                await pilot.pause(1)
                for width,height in ((120,32),(48,24)):
                    await pilot.resize_terminal(width,height); await pilot.pause(.4)
                    assert all(view.region.right<=width and view.region.bottom<=height for view in app.views.values() if view.display)
                    for view in app.views.values():
                        if view.display:
                            for composer in view.query('.composer'):
                                assert composer.region.bottom<=height, 'Composer clipped by terminal resize'
                    app.save_screenshot(f'design-{label}-{width}.svg',path=str(core.ROOT/'previews'))
                snap.update(state='waiting',detail='choice',menu=True,screen='승인 요청 · 합성 예시\n\n❯ 1. 허용\n  2. 취소\n\n↑↓ 이동 · Enter 선택',cursor=2)
                for panel in app.query('.chat-panel'):
                    panel.queue.add('다음 작업을 검토해 주세요', '%1', '1')
                    panel.queue.pause(); panel.render_queue()
                await pilot.pause(.8)
                app.save_screenshot(f'design-{label}-approval.svg',path=str(core.ROOT/'previews'))
                send.assert_not_called(); control.assert_not_called()
                assert app._exception is None
                print('Synthetic design captures saved:',label)
    from sidebar import Sidebar
    with tempfile.TemporaryDirectory(prefix='tmw-design-sidebar-') as tmp,patch.object(core,'CONFIG',Path(tmp)/'projects.json'),patch.object(core,'STATE',Path(tmp)/'state'),patch.dict(os.environ,{'TMW_PROJECT':'sample'}),patch('live_tmux.refresh_connections',return_value=False),patch('watcher.refresh',return_value=False),patch.object(core,'tmux',return_value=subprocess.CompletedProcess([],0,'','')),patch('layout.terminals',return_value=[]):
        projects=[dict(id=key,name=name,path=tmp,kind='tmux-live',source_agents={'claude':1},source_states={'claude':status},agents={'claude':False,'codex':False}) for key,name,status in [('sample','Sample',{'state':'busy'}),('review','Review',{'state':'waiting','pending':'approval'}),('notes','Notes',{'state':'idle','pending':'result'})]]
        core.atomic(core.CONFIG,projects)
        app=Sidebar()
        async with app.run_test(size=(30,32)) as pilot:
            await pilot.pause(.5)
            app.save_screenshot(f'design-{label}-sidebar.svg',path=str(core.ROOT/'previews'))
            app.query_one('#project-search').value='missing'
            await pilot.pause(.3)
            assert app.query_one('#project-empty').display
            app.save_screenshot(f'design-{label}-empty.svg',path=str(core.ROOT/'previews'))
            for name in ('files','git','terminal'):
                app.query_one('#views').active=name+'-view'
                await pilot.pause(.3)
                app.save_screenshot(f'design-{label}-{name}.svg',path=str(core.ROOT/'previews'))
            assert app._exception is None
if __name__=='__main__': asyncio.run(main())
