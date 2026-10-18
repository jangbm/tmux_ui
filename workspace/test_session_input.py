"""Only user actions write to the selected existing AI; suggestions stay inert."""
import asyncio
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch
import core
import session_input
from desk_state import DeskState

PROJECT=dict(id='live-video',name='video',kind='tmux-live',source_session='video',source_socket='/tmp/source',source_agents={'claude':1},path='/tmp')
SNAP=dict(id='%3',pid='10',cursor=1,screen='Reply\n❯ \x1b[2m추천 문구\x1b[22m',state='idle',detail='empty-prompt',suggestion='추천 문구',mode='Auto')

class RoutingTests(unittest.TestCase):
    def test_blocked_send_explains_actual_reason(self):
        for current,expected in [({'state':'busy'},'작업 중'),({'state':'waiting','menu':True},'승인 메뉴'),({'state':'waiting','detail':'draft'},'작성 중인 글'),({'state':'unknown','detail':'unrecognized-screen'},'준비 상태를 확인하지 못')]:
            self.assertIn(expected,session_input.blocked_reason(current))

    def test_nested_worker_cannot_receive_input_through_parent_pane(self):
        project={**PROJECT,'source_session':'unity'}
        with patch('live_tmux.read',return_value='unity|%2|10|claude|0|1|1|1\n'),patch('watcher.running_agent',return_value=True):
            self.assertEqual(session_input.targets(project,'codex'),[])
            self.assertEqual(session_input.targets(project,'claude')[0]['id'],'%2')
            with patch('session_input._command') as command:
                with self.assertRaises(ValueError): session_input.control(project,'codex','%2','10','Enter')
                command.assert_not_called()

    def test_suggestion_is_only_dim_prompt_text(self):
        self.assertEqual(session_input.suggestion(SNAP['screen'],1),'추천 문구')
        self.assertEqual(session_input.suggestion('Reply\n❯ 사용자 입력',1),'')
        self.assertEqual(session_input.suggestion('Reply\n❯ \x1b[2mhint\x1b[22m real',1),'')
    def test_literal_multiline_only_goes_to_pinned_pane(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'STATE',Path(tmp)),patch('session_input.snapshot',return_value=SNAP),patch('session_input.targets',return_value=[SNAP]),patch('session_input._command') as command:
            session_input.send(PROJECT,'claude','%3','10','안녕\n$(do-not-run)')
            calls=command.call_args_list
            self.assertEqual(calls[0].kwargs['input'],'안녕\n$(do-not-run)')
            self.assertIn(('send-keys','-t','%3','Enter'),[c.args[1:] for c in calls])
            self.assertTrue(all(c.args[0] is PROJECT for c in calls))
    def test_busy_or_draft_or_unknown_does_not_write(self):
        for state in ('busy','waiting','unknown'):
            with tempfile.TemporaryDirectory() as tmp,patch.object(core,'STATE',Path(tmp)),patch('session_input.snapshot',return_value={**SNAP,'state':state}),patch('session_input._command') as command:
                with self.assertRaises(ValueError): session_input.send(PROJECT,'claude','%3','10','hi')
                command.assert_not_called()
    def test_changed_pane_cannot_fall_back_to_another_agent(self):
        with patch('session_input.targets',return_value=[{**SNAP,'id':'%4'}]):
            with self.assertRaises(ValueError): session_input.snapshot(PROJECT,'claude','%3','10')
        with patch('session_input.targets',return_value=[{**SNAP,'pid':'11'}]):
            with self.assertRaises(ValueError): session_input.snapshot(PROJECT,'claude','%3','10')
    def test_menu_detection_and_keys_require_an_open_menu(self):
        self.assertTrue(session_input.menu_open('Select model\n› gpt-model\nEnter to confirm','unknown','unrecognized-screen'))
        self.assertFalse(session_input.menu_open('› write a message\nesc to interrupt','busy','interrupt-hint'))
        for key in ('Up','Down','Enter','Escape'):
            with patch('session_input.snapshot',return_value={**SNAP,'menu':True}),patch('session_input._command') as command:
                session_input.control(PROJECT,'claude','%3','10',key)
                self.assertEqual(command.call_args.args[1:],('send-keys','-t','%3',key))
            with patch('session_input.snapshot',return_value={**SNAP,'menu':False}),patch('session_input._command') as command:
                with self.assertRaises(ValueError): session_input.control(PROJECT,'claude','%3','10',key)
                command.assert_not_called()

    def test_mode_and_stop_use_only_expected_key(self):
        with patch('session_input.snapshot',return_value=SNAP),patch('session_input._command') as command:
            session_input.control(PROJECT,'claude','%3','10','mode')
            self.assertEqual(command.call_args.args[1:],('send-keys','-t','%3','BTab'))
        with patch('session_input.snapshot',return_value={**SNAP,'state':'busy'}),patch('session_input._command') as command:
            session_input.control(PROJECT,'claude','%3','10','stop')
            self.assertEqual(command.call_args.args[1:],('send-keys','-t','%3','Escape'))

    def test_shutdown_rejects_busy_menu_and_changed_target(self):
        for state in ('busy','waiting','unknown'):
            with patch('session_input.snapshot',return_value={**SNAP,'state':state}),patch('session_input._command') as command,patch('session_input.send') as send:
                with self.assertRaises(ValueError): session_input.shutdown(PROJECT,'claude','%3','10')
                command.assert_not_called();send.assert_not_called()
        with patch('session_input.targets',return_value=[{**SNAP,'pid':'11'}]),patch('session_input._command') as command:
            with self.assertRaises(ValueError): session_input.shutdown(PROJECT,'claude','%3','10')
            command.assert_not_called()

Desktop=runpy.run_path(str(core.ROOT/'desktop-app.py'))['Desktop']
class LiveUITests(unittest.IsolatedAsyncioTestCase):
    async def test_busy_message_queues_once_then_dispatches_and_keeps_new_draft(self):
        current={**SNAP,'menu':False,'state':'busy','detail':'interrupt-hint'}
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'CONFIG',Path(tmp)/'projects.json'),patch.object(core,'STATE',Path(tmp)/'state'),patch('session_input.targets',return_value=[{**SNAP,'label':'Claude %3'}]),patch('session_input.snapshot',side_effect=lambda *a:dict(current)),patch('session_input.send') as send:
            core.atomic(core.CONFIG,[PROJECT]);state=DeskState();tab=state.open(PROJECT['id'])
            app=Desktop(PROJECT,state.value,publish=False)
            async with app.run_test(size=(100,30)) as pilot:
                await pilot.pause(.7)
                panel=app.views[tab['id']].panels['claude'];composer=panel.query_one('.composer')
                composer.focus();composer.load_text('다음 작업')
                await pilot.press('enter');await pilot.pause(.2)
                send.assert_not_called();self.assertEqual(len(panel.queue.items),1)
                composer.load_text('작성 중인 새 초안')
                current.update(state='idle',detail='empty-prompt')
                panel.refresh_source();await pilot.pause(.8)
                send.assert_called_once_with(PROJECT,'claude','%3','10','다음 작업')
                self.assertEqual(composer.text,'작성 중인 새 초안')
                self.assertEqual(panel.queue.items,[])
                await pilot.pause(.7);self.assertEqual(send.call_count,1)
                await pilot.press('ctrl+f');await pilot.pause()
                self.assertTrue(panel.query_one('.thread-search').display)
                panel.query_one('.thread-search').value='Reply';await pilot.pause()
                self.assertEqual(panel.search_term,'Reply')
                await pilot.press('escape');await pilot.pause()
                self.assertFalse(panel.query_one('.thread-search').display)

    async def test_source_click_routes_arrows_and_drag_copies_without_stopping(self):
        current={**SNAP,'menu':True,'state':'waiting','screen':'Approval menu\n❯ 1. Allow\n  2. Deny'}
        project={**PROJECT,'source_agents':{'claude':1,'codex':1}}
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'CONFIG',Path(tmp)/'projects.json'),patch.object(core,'STATE',Path(tmp)/'state'),patch('session_input.targets',return_value=[{**SNAP,'label':'AI %3'}]),patch('session_input.snapshot',side_effect=lambda p,a,*args:dict(current) if a=='claude' else {**SNAP,'menu':False}),patch('session_input.control') as control,patch('shutil.which',return_value=None):
            core.atomic(core.CONFIG,[project]);state=DeskState();tab=state.open(project['id'])
            app=Desktop(project,state.value,publish=False)
            async with app.run_test(size=(120,30)) as pilot:
                await pilot.pause(.7)
                panel=app.views[tab['id']].panels['claude'];source=panel.query_one('.source-message')
                await pilot.click(source,offset=(2,0))
                await pilot.press('down','up','left','right');await pilot.pause(.3)
                self.assertEqual([c.args[-1] for c in control.call_args_list],['Down','Up','Left','Right'])
                control.reset_mock()
                await pilot.mouse_down(source,offset=(0,0))
                await pilot.hover(source,offset=(8,0))
                await pilot.mouse_up(source,offset=(8,0));await pilot.pause(.2)
                self.assertEqual(app.clipboard,'Approval')
                await pilot.press('ctrl+c');await pilot.pause(.1)
                control.assert_not_called()
                app.select_tab(tab['id']);await pilot.pause(.2)
                await pilot.press('down');await pilot.pause(.2)
                control.assert_called_once_with(project,'claude','%3','10','Down')
                self.assertEqual(app.clipboard,'Approval')
                control.reset_mock()
                codex=app.views[tab['id']].panels['codex']
                await pilot.click(codex.query_one('.source-message'),offset=(1,0))
                await pilot.press('down');await pilot.pause(.1)
                control.assert_not_called()

    async def test_shutdown_cancel_and_confirm_pin_the_selected_ai(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'CONFIG',Path(tmp)/'projects.json'),patch.object(core,'STATE',Path(tmp)/'state'),patch('session_input.targets',return_value=[{**SNAP,'label':'video Claude %3'}]),patch('session_input.snapshot',return_value=SNAP),patch('session_input.shutdown',return_value=True) as shutdown,patch('live_tmux.refresh_connections'):
            core.atomic(core.CONFIG,[PROJECT]);state=DeskState();tab=state.open(PROJECT['id'])
            app=Desktop(PROJECT,state.value,publish=False)
            async with app.run_test(size=(100,30)) as pilot:
                await pilot.pause(.7)
                panel=app.views[tab['id']].panels['claude']
                await pilot.click(panel.query_one('.shutdown-ai'));await pilot.pause(.1)
                await pilot.press('escape');await pilot.pause(.1)
                shutdown.assert_not_called()
                await pilot.click(panel.query_one('.shutdown-ai'));await pilot.pause(.1)
                await pilot.click('#confirm-shutdown');await pilot.pause(.3)
                shutdown.assert_called_once_with(PROJECT,'claude','%3','10')

    async def test_tab_accepts_without_sending_enter_routes_and_shift_tab_changes_mode(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'CONFIG',Path(tmp)/'projects.json'),patch.object(core,'STATE',Path(tmp)/'state'),patch('session_input.targets',return_value=[{**SNAP,'label':'video Claude %3'}]),patch('session_input.snapshot',return_value=SNAP),patch('session_input.send') as send,patch('session_input.control') as control,patch('chat_backend.Conversation.send') as separate:
            core.atomic(core.CONFIG,[PROJECT])
            core.atomic(core.STATE/'chats'/'live-video-claude.json',{'messages':[{'role':'assistant','text':'OLD SEPARATE CHAT'}]})
            state=DeskState();tab=state.open(PROJECT['id'])
            app=Desktop(PROJECT,state.value,publish=False)
            async with app.run_test(size=(100,30)) as pilot:
                await pilot.pause(2.2)
                panel=app.views[tab['id']].panels['claude']; composer=panel.query_one('.composer')
                self.assertEqual(composer.placeholder,'추천 문구')
                self.assertFalse(panel.query_one('.messages').display)
                composer.focus(); await pilot.press('tab'); await pilot.pause()
                self.assertEqual(composer.text,'추천 문구'); send.assert_not_called()
                await pilot.press('enter'); await pilot.pause(.2)
                send.assert_called_once_with(PROJECT,'claude','%3','10','추천 문구')
                self.assertEqual(composer.text,''); separate.assert_not_called()
                await pilot.press('shift+tab'); await pilot.pause(.2)
                control.assert_called_once_with(PROJECT,'claude','%3','10','mode')

    async def test_slash_command_opens_menu_and_navigation_keeps_local_draft(self):
        current={**SNAP,'menu':False}
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'CONFIG',Path(tmp)/'projects.json'),patch.object(core,'STATE',Path(tmp)/'state'),patch('session_input.targets',return_value=[{**SNAP,'label':'video Claude %3'}]),patch('session_input.snapshot',side_effect=lambda *a:dict(current)),patch('session_input.send') as send,patch('session_input.control') as control:
            core.atomic(core.CONFIG,[PROJECT]);state=DeskState();tab=state.open(PROJECT['id'])
            app=Desktop(PROJECT,state.value,publish=False)
            async with app.run_test(size=(100,30)) as pilot:
                await pilot.pause(.7)
                panel=app.views[tab['id']].panels['claude'];composer=panel.query_one('.composer')
                composer.focus();composer.load_text('/model')
                await pilot.press('enter');await pilot.pause(.2)
                send.assert_called_once_with(PROJECT,'claude','%3','10','/model')
                current.update(menu=True,state='waiting',detail='menu',suggestion='')
                panel.refresh_source();await pilot.pause(.2)
                self.assertTrue(panel.query_one('.menu-controls').display)
                composer.load_text('보존할 초안')
                await pilot.press('enter');await pilot.pause(.1)
                control.assert_not_called();self.assertEqual(send.call_count,1)
                await pilot.press('down');await pilot.pause(.1)
                await pilot.click(next(b for b in panel.query('.menu-key') if b.name=='Enter'))
                composer.focus();await pilot.press('escape');await pilot.pause(.6)
                self.assertEqual([c.args[-1] for c in control.call_args_list],['Down','Enter','Escape'])
                self.assertEqual(composer.text,'보존할 초안')
                self.assertEqual(send.call_count,1)
