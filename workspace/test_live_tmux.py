"""The live source adapter only reads; the mirror never forwards keyboard input."""
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import core
import live_tmux

LiveView=runpy.run_path(str(core.ROOT/'live-view.py'))['LiveView']


class SourceTests(unittest.TestCase):
    def test_unicode_sessions_and_expired_budget(self):
        import time
        records=[]
        item=dict(name='시험',source_session='시험',source_socket='/tmp/source',kind='tmux-live')
        live_tmux.merge_discovered(records,[item]);live_tmux.merge_discovered(records,[item])
        self.assertEqual(len(records),1);self.assertTrue(records[0]['id'].startswith('live-'))
        with patch('live_tmux.read') as read:
            with self.assertRaises(TimeoutError): live_tmux.connections('/tmp/source',time.monotonic()-1)
            read.assert_not_called()
    def test_removed_session_is_hidden_and_recreation_restores_without_losing_metadata(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'CONFIG',Path(tmp)/'projects.json'),patch.object(core,'STATE',Path(tmp)/'state'):
            original=dict(id='live-test',name='test',kind='tmux-live',source_socket='/tmp/source',source_session='test',path='/projects/test')
            core.atomic(core.CONFIG,[original])
            other=dict(name='test2',kind='tmux-live',source_socket='/tmp/source',source_session='test2')
            with patch('live_tmux.discover',return_value=[other]),patch('live_tmux.connections',return_value={'test2':{}}),patch('live_tmux.activity',return_value={}):
                live_tmux.refresh_connections(force=True)
            self.assertTrue(core.projects()[0]['source_missing'])
            self.assertFalse(core.projects()[1]['source_missing'])
            with patch('live_tmux.discover',side_effect=TimeoutError),patch('live_tmux.connections',return_value={}),patch('live_tmux.activity',return_value={}):
                live_tmux.refresh_connections(force=True)
            self.assertFalse(core.projects()[1]['source_missing'])
            with patch('live_tmux.discover',return_value=[original,other]),patch('live_tmux.connections',return_value={'test':{},'test2':{}}),patch('live_tmux.activity',return_value={}):
                live_tmux.refresh_connections(force=True)
            self.assertFalse(core.projects()[0]['source_missing'])
            self.assertEqual(core.projects()[0]['path'],'/projects/test')
            self.assertEqual(len(core.projects()),2)

    def test_new_session_is_discovered_with_both_agents_during_poll(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'CONFIG',Path(tmp)/'projects.json'),patch.object(core,'STATE',Path(tmp)/'state'):
            original=dict(id='live-control',name='Control custom',kind='tmux-live',source_socket='/tmp/source',source_session='control',source_pane='%1',navigation_hidden=True)
            core.atomic(core.CONFIG,[original])
            rows='control|%1|1|1|/projects/control\ntest|%24|1|1|/projects/test\ntest|%25|0|1|/projects/test\n'
            with patch('live_tmux.read',return_value=rows) as read,patch('live_tmux.connections',return_value={'test':{'claude':1,'codex':1}}),patch('live_tmux.activity',return_value={}):
                live_tmux.refresh_connections(force=True)
                live_tmux.refresh_connections(force=True)
            records=core.projects();self.assertEqual(len(records),2)
            self.assertEqual(records[0]['name'],'Control custom');self.assertTrue(records[0]['navigation_hidden'])
            self.assertEqual(records[1]['id'],'live-test')
            self.assertEqual(records[1]['source_pane'],'%24')
            self.assertEqual(records[1]['source_agents'],{'claude':1,'codex':1})
            self.assertTrue(all(c.args[1]=='list-panes' for c in read.call_args_list))

    def test_discovery_collision_preserves_local_and_other_server_projects(self):
        records=[{'id':'live-test','name':'Local'}]
        found=[dict(name='test',source_session='test',source_socket=s,kind='tmux-live') for s in ('/tmp/a','/tmp/b')]
        live_tmux.merge_discovered(records,found);live_tmux.merge_discovered(records,found)
        self.assertEqual(len(records),3)
        self.assertEqual(len({p['id'] for p in records}),3)
        self.assertEqual(records[0],{'id':'live-test','name':'Local'})

    def test_failed_discovery_preserves_registry(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'CONFIG',Path(tmp)/'projects.json'),patch.object(core,'STATE',Path(tmp)/'state'):
            original=dict(id='live-test',kind='tmux-live',source_socket='/tmp/source',source_session='test',source_agents={'claude':1})
            core.atomic(core.CONFIG,[original])
            with patch('live_tmux.read',side_effect=RuntimeError('offline')):
                live_tmux.refresh_connections(force=True)
            result=core.projects();self.assertEqual(len(result),1)
            self.assertEqual(result[0]['source_agents'],{'claude':1})
            self.assertEqual(result[0]['source_agents_error'],'unavailable')

    def test_only_read_commands_are_accepted(self):
        with patch('subprocess.run',return_value=subprocess.CompletedProcess([],0,'screen','')) as run:
            self.assertEqual(live_tmux.capture('/tmp/source','%3'),'screen')
            self.assertEqual(run.call_args.args[0],['tmux','-S','/tmp/source','capture-pane','-p','-e','-t','%3'])
            for command in ('send-keys','kill-server','join-pane','resize-pane','attach-session'):
                with self.assertRaises(ValueError): live_tmux.read('/tmp/source',command)
            with self.assertRaises(ValueError): live_tmux.capture('/tmp/source','session; shell')
            self.assertEqual(run.call_count,1)

    def test_registration_is_repeatable_and_keeps_project_order(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'CONFIG',Path(tmp)/'projects.json'),patch.object(core,'STATE',Path(tmp)/'state'):
            core.atomic(core.CONFIG,[{'id':'existing','name':'Existing'}])
            panes=[dict(id='%3',active=True,path=tmp)]
            with patch('live_tmux.read',return_value='control\nunity\n'),patch('live_tmux.source_panes',return_value=panes),patch('live_tmux.connections',return_value={'control':{'claude':1,'codex':1},'unity':{'claude':1}}):
                live_tmux.register('/tmp/source'); live_tmux.register('/tmp/source')
            self.assertEqual([p['id'] for p in core.projects()],['existing','live-control','live-unity'])
            self.assertFalse(core.projects()[1]['agents']['codex'])
            self.assertEqual(core.projects()[1]['source_agents'],{'claude':1,'codex':1})

    def test_activity_distinguishes_work_wait_idle_and_respects_budget(self):
        import time
        rows='work|%1|codex|1|0|1\nwait|%2|claude|2|0|1\nready|%3|claude|3|0|1\n'
        screens={'%1':'Running\nesc to interrupt','%2':'Permission\n❯ 1. Yes','%3':'Ready\n❯ '}
        def read(socket,*args,**kwargs):
            return rows if args[0]=='list-panes' else screens[args[-1]]
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'STATE',Path(tmp)),patch('live_tmux.read',side_effect=read) as reader,patch('watcher.running_agent',side_effect=lambda a,c,p:a==c):
            states=live_tmux.activity('/tmp/source',time.monotonic()+.8)
            self.assertEqual(states['work']['codex']['state'],'busy')
            self.assertEqual(states['wait']['claude']['state'],'waiting')
            self.assertEqual(states['ready']['claude']['state'],'idle')
            self.assertTrue(all(call.args[1] in ('list-panes','capture-pane') for call in reader.call_args_list))
            reader.reset_mock()
            self.assertEqual(live_tmux.activity('/tmp/source',time.monotonic()-1),{})
            reader.assert_not_called()

    def test_result_remains_until_reply_and_permission_is_red_candidate(self):
        screen='● Finished result\n❯ '
        pending=live_tmux.pending_result(screen,1,'idle','empty-prompt',{})
        self.assertEqual(pending['pending'],'result')
        self.assertEqual(live_tmux.pending_result(screen,1,'idle','empty-prompt',pending)['pending'],'result')
        busy=live_tmux.pending_result('Working\nesc to interrupt',1,'busy','interrupt-hint',pending)
        self.assertEqual(busy['pending'],'')
        self.assertEqual(live_tmux.pending_result(screen,1,'idle','empty-prompt',busy)['pending'],'result')
        acknowledged={**pending,'pending':''}
        self.assertEqual(live_tmux.pending_result(screen,1,'idle','empty-prompt',acknowledged)['pending'],'')
        self.assertEqual(live_tmux.pending_result('● New reply\n❯ ',1,'idle','empty-prompt',acknowledged)['pending'],'result')
        self.assertEqual(live_tmux.pending_result('Permission\n❯ 1. Allow',1,'waiting','choice',{})['pending'],'approval')

    def test_nested_codex_worker_is_not_a_second_claude_terminal(self):
        # Simulate Claude spawning Codex: both process searches would succeed.
        with patch('live_tmux.read',return_value='unity|claude|10|0\n'),patch('watcher.running_agent',return_value=True) as search:
            self.assertEqual(live_tmux.connections('/tmp/source'),{'unity':{'claude':1}})
            search.assert_not_called()
        from watcher import pane_agent
        with patch('watcher.running_agent',return_value=True):
            self.assertIsNone(pane_agent('bash',10))
            self.assertEqual(pane_agent('codex',10),'codex')

    def test_shell_background_ai_is_not_an_interactive_pane(self):
        from watcher import pane_agent
        with patch('pathlib.Path.read_bytes',return_value=b'bash\0'),patch('watcher.running_agent',return_value=True) as descendants:
            self.assertIsNone(pane_agent('bash',42))
            descendants.assert_not_called()
        with patch('pathlib.Path.read_bytes',return_value=b'claude\0-u\0fake.py\0'):
            self.assertEqual(pane_agent('python3',42),'claude')

    def test_live_connections_distinguish_cli_wrapper_and_dead_processes(self):
        rows='control|claude|1|0\ncontrol|codex|2|0\nwrapper|bash|3|0\nempty|bash|4|0\ndead|codex|5|1\n'
        with patch('live_tmux.read',return_value=rows),patch('watcher.pane_agent',side_effect=lambda c,p: c if c in core.AGENTS else ('claude' if p==3 else None)):
            found=live_tmux.connections('/tmp/source')
        self.assertEqual(found['control'],{'claude':1,'codex':1})
        self.assertEqual(found['wrapper'],{'claude':1})
        self.assertEqual(found['empty'],{})
        self.assertEqual(found['dead'],{})


class LiveViewTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_refresh_pane_choice_and_keyboard_are_read_only(self):
        project=dict(source_session='control',source_socket='/tmp/source',source_pane='%3')
        panes=[dict(id='%3',window='1',name='Main',active=True,command='claude'),
               dict(id='%4',window='2',name='Tools',active=False,command='bash')]
        with patch('live_tmux.source_panes',return_value=panes),patch('live_tmux.capture',return_value='\x1b[32mLIVE MARKER\x1b[0m') as capture:
            app=LiveView(project)
            async with app.run_test(size=(80,20)) as pilot:
                await pilot.pause()
                self.assertIn('LIVE MARKER',str(app.query_one('#output').render()))
                await pilot.press('x','enter','ctrl+c')
                self.assertIsNone(app._exception)
                app.query_one('#pane').value='%4'
                await pilot.pause()
                self.assertEqual(capture.call_args.args,('/tmp/source','%4'))
