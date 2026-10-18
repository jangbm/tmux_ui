"""Editor strip mouse interactions and parity of top-docked navigation."""
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch
from subprocess import CompletedProcess
import core
from sidebar import Sidebar
from textual.widgets import Tree

bar_module=runpy.run_path(str(core.ROOT/'editor-tabs.py'))
EditorTabs=bar_module['EditorTabs']; EditorTab=bar_module['EditorTab']


class EditorTabUITests(unittest.IsolatedAsyncioTestCase):
    async def test_click_reorder_and_drag_to_two_split_targets(self):
        project={'id':'workspace','name':'Workspace'}
        tabs=[{'id':'%1','name':'MyProject','primary':True},
              {'id':'%2','name':'Demo Web','primary':False}]
        with patch.object(core,'tmux_checked',return_value=''), patch('editor_tabs.ordered',return_value=tabs):
            app=EditorTabs(project)
            async with app.run_test(size=(100,3)) as pilot:
                await pilot.pause()
                widgets=list(app.query(EditorTab))
                with patch('editor_tabs.select') as choose:
                    await pilot.click(widgets[1],offset=(2,1))
                    choose.assert_called_once_with(project,'%2')
                with patch('editor_tabs.reorder') as reorder:
                    await pilot.mouse_down(widgets[1],offset=(2,1))
                    await pilot.mouse_up(widgets[0],offset=(2,1))
                    reorder.assert_called_once_with(project,'%2','%1')
                with patch('editor_tabs.split') as split:
                    for target,direction in [('split-right','right'),('split-below','below')]:
                        await pilot.mouse_down(widgets[1],offset=(2,1))
                        await pilot.mouse_up('#'+target,offset=(2,1))
                        self.assertEqual(split.call_args.args,(project,'%2',direction))

    async def test_narrow_strip_tracks_focused_editor_and_reveals_tab(self):
        project={'id':'workspace','name':'Workspace'}
        tabs=[{'id':f'%{i}','name':f'Project {i}','primary':i==1} for i in range(1,9)]
        def tmux(*args):
            return '%8' if args[0]=='display-message' else ''
        with patch.object(core,'tmux_checked',side_effect=tmux),patch('editor_tabs.ordered',return_value=tabs):
            app=EditorTabs(project)
            async with app.run_test(size=(32,3)) as pilot:
                await pilot.pause()
                self.assertEqual(app.selected,'%8')
                self.assertTrue(app.screen.has_class('compact'))
                self.assertGreater(app.query_one('#tabs').scroll_x,0)
                self.assertEqual(app.query_one('#split-right').region.width,5)
                await pilot.resize_terminal(100,3)
                await pilot.pause()
                self.assertFalse(app.screen.has_class('compact'))
                self.assertEqual(str(app.query_one('#split-right').label),'↔ 옆')

    async def test_live_project_shows_actual_agents_and_unavailable_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            record=dict(id='live-control',name='control · LIVE',path=tmp,kind='tmux-live',source_agents={'claude':1,'codex':1},agents={'claude':False,'codex':False})
            with patch.object(core,'CONFIG',root/'projects.json'),patch.dict(os.environ,{'TMW_PROJECT':''}),patch('watcher.refresh'),patch('live_tmux.refresh_connections'):
                core.atomic(core.CONFIG,[record])
                app=Sidebar()
                async with app.run_test(size=(50,35)) as pilot:
                    await pilot.pause()
                    tree=app.query_one('#tree',Tree)
                    labels=[str(node.label) for node in tree.root.children[0].children]
                    self.assertTrue(any('Claude' in label for label in labels))
                    self.assertTrue(any('Codex' in label for label in labels))
                    record['source_agents_error']='unavailable'
                    core.atomic(core.CONFIG,[record]); app.refresh_projects(force=True)
                    await pilot.pause()
                    self.assertIn('확인 불가',str(tree.root.children[0].children[0].label))

    async def test_top_navigation_keeps_agent_tree_and_compact_footer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(core,'CONFIG',root/'projects.json'),patch.dict(os.environ,{'TMW_PROJECT':'owner'}), \
                 patch('watcher.refresh',return_value=False), \
                 patch.object(core,'tmux',return_value=CompletedProcess([],0,'top','')):
                core.add('MyProject',root/'project',key='owner')
                app=Sidebar()
                async with app.run_test(size=(160,16)) as pilot:
                    await pilot.pause()
                    self.assertTrue(app.screen.has_class('top'))
                    tree=app.query_one('#tree',Tree)
                    self.assertTrue(tree.display)
                    self.assertGreater(tree.region.height,0)
                    self.assertEqual(len(app.nodes),2)
                    self.assertEqual(app.query_one('#dock-top').region.height,1)
                    with patch('editor_tabs.open_project') as open_tab:
                        app.open_project('owner')
                        open_tab.assert_called_once()
                    self.assertTrue(app.screen.has_class('top'))
