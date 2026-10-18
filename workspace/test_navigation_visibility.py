import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from textual.widgets import OptionList
from textual import events
import core
import live_tmux
import navigation_visibility as visibility
from sidebar import Sidebar

class VisibilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_hide_restore_menu_and_recreation_without_source_writes(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'CONFIG',Path(tmp)/'projects.json'),patch.object(core,'STATE',Path(tmp)/'state'),patch.dict(os.environ,{'TMW_PROJECT':'owner'}),patch('live_tmux.refresh_connections',return_value=False),patch('watcher.refresh',return_value=False),patch('desktop.enabled',return_value=True),patch.object(core,'tmux',return_value=subprocess.CompletedProcess([],0,'','')) as tmux,patch.object(core,'tmux_checked') as checked:
            owner=dict(id='owner',name='Workspace',path=tmp,agents={},navigation_hidden=True)
            item=dict(id='live-loop',name='loop',kind='tmux-live',source_socket='/tmp/synthetic-source',source_session='loop',path=tmp,agents={'claude':False,'codex':False},source_agents={})
            core.atomic(core.CONFIG,[owner,item]);app=Sidebar()
            async with app.run_test(size=(40,30)) as pilot:
                await pilot.pause()
                node=app.project_nodes[item['id']]
                await pilot._post_mouse_events([events.MouseDown,events.MouseUp,events.Click],'#tree',offset=(5,node.line),button=3)
                await pilot.pause()
                await pilot.resize_terminal(22,30);await pilot.pause()
                self.assertEqual(str(app.screen.query_one('#hide-project').label),'숨기기')
                await pilot.click('#hide-project');await pilot.pause()
                self.assertNotIn(item['id'],app.project_nodes)
                self.assertTrue(app.query_one('#hidden-projects').display)
                app.refresh_projects(force=True);self.assertNotIn(item['id'],app.project_nodes)
                # New registry object/ID and pane after rediscovery, same source identity.
                records=[owner];live_tmux.merge_discovered(records,[dict(item,id='replacement',source_pane='%99')])
                recreated=records[1];core.atomic(core.CONFIG,records);app.refresh_projects(force=True)
                self.assertNotIn(recreated['id'],app.project_nodes)
                self.assertTrue(visibility.hidden(recreated))
                self.assertFalse(visibility.hidden(dict(recreated,source_socket='/tmp/another-server')))
                await pilot.click('#hidden-projects');await pilot.pause()
                await pilot.press('enter');await pilot.pause()
                self.assertIn(recreated['id'],app.project_nodes)
                self.assertFalse(visibility.rules())
                # Three-dot menu targets the selected project without opening it.
                app.query_one('#tree').move_cursor(app.project_nodes[recreated['id']])
                await pilot.click('#agent-settings');await pilot.pause()
                self.assertIn('loop',str(app.screen.query_one('Static').render()))
                await pilot.press('escape');await pilot.pause()
                checked.assert_not_called()
                self.assertTrue(all(c.args[0] in ('show-options',) for c in tmux.call_args_list))
            visibility.hide(recreated)
            # Read back from disk, as a new Sidebar process would do.
            self.assertTrue(visibility.hidden(dict(recreated,id='brand-new-id')))
